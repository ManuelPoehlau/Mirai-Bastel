"""WP-IL-01 — Input Trace: OS→Win32→Pyglet→Python Event-Pfad

Unterscheidet Kandidat A (Fokus-Problem bei WM_MOUSEWHEEL) von
Kandidat B (HWND-Routing/Dispatch-Defekt bei WM_MOUSEMOVE/WM_LBUTTONDOWN).

Methode
-------
PostMessageW injiziert echte Win32-Nachrichten direkt in die HWNDs des
laufenden Lab-Fensters.  Das ist der *echte* Win32-Pfad:
    PostMessageW → system message queue → PeekMessageW (EventLoop.step)
    → DispatchMessageW → wndproc → _event_handlers dict → Python handler
Der einzige Unterschied zu physischen Maus-Events: kein HID-Stack und kein
Focus-Routing durch den OS.  Damit lässt sich der Focus-Faktor gezielt
isolieren.

Spy-Ebenen
----------
Ebene 1 (Win32-Handler-Dict): _view_event_handlers / _event_handlers werden
  für jeden relevanten Message-Code durch einen Wrapper ersetzt.  Damit ist
  nachgewiesen, ob der pyglet-interne Lowlevel-Handler überhaupt ausgeführt
  wird.

Ebene 2 (dispatch_event): window.dispatch_event wird als Instance-Attribut
  überschrieben; da _event_mousemove / _event_mousewheel intern
  self.dispatch_event(...) aufrufen, wird jeder Dispatch sichtbar.

Test-Ablauf
-----------
Phase 1: WM_LBUTTONDOWN  → _view_hwnd  (wie echter Klick in Client-Area)
Phase 2: WM_MOUSEMOVE    → _view_hwnd  + MK_LBUTTON (Drag)
Phase 3: WM_LBUTTONUP    → _view_hwnd
Phase 4: WM_MOUSEWHEEL   → _hwnd       (normaler Fokus-Pfad)
Phase 5: WM_MOUSEWHEEL   → _view_hwnd  (direkt, ohne Focus)

Interpretation
--------------
Kandidat A bestätigt:
  Phase 4 KEIN on_mouse_scroll, Phase 5 JA → Fokusproblem.

Kandidat B bestätigt:
  Phase 2 KEIN on_mouse_drag (trotz korrektem wParam) → Routing/Dispatch-Defekt.

Beide schlagen fehl:
  Spy-Level 1 zeigt keinen Aufruf → wndproc-Problem (eigene Kategorie).

Aufruf:
    python experiments/mirai_bastel_integration_lab/_diag_input_trace.py
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import io
import sys
import time
from pathlib import Path

# Windows consoles often default to cp1252; force UTF-8 so arrow chars work.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pyglet
from pyglet import gl

_THIS_DIR = Path(__file__).resolve().parent
_REPO = _THIS_DIR.parent.parent
for _p in (str(_THIS_DIR), str(_REPO), str(_REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from integration.lab_viewport import IntegrationLabWindow  # noqa: E402
from scene.scene_objects import build_lab_scene  # noqa: E402

# ---------------------------------------------------------------------------
# Win32-Konstanten
# ---------------------------------------------------------------------------
WM_MOUSEMOVE   = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP   = 0x0202
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP   = 0x0208
WM_MOUSEWHEEL  = 0x020A
MK_LBUTTON     = 0x0001
MK_MBUTTON     = 0x0010
WHEEL_DELTA    = 120       # eine Raste vorwärts

_user32 = ctypes.windll.user32

def _pack_lParam(x: int, y: int) -> int:
    """(x, y) als LPARAM für WM_MOUSE*-Nachrichten (Client-Koordinaten)."""
    return (y & 0xFFFF) << 16 | (x & 0xFFFF)

def _pack_wParam_wheel(delta: int, keys: int = 0) -> int:
    """WPARAM für WM_MOUSEWHEEL: high-word = delta, low-word = key-flags."""
    return ((delta & 0xFFFF) << 16) | (keys & 0xFFFF)

def _client_to_screen(hwnd, x: int, y: int) -> tuple[int, int]:
    pt = ctypes.wintypes.POINT(x, y)
    _user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y

# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------
_log: list[dict] = []

def _record(phase: str, level: str, event: str, detail: str = "") -> None:
    entry = {"phase": phase, "level": level, "event": event, "detail": detail}
    _log.append(entry)
    print(f"  [SPY {level}] {phase}: {event}  {detail}")

# ---------------------------------------------------------------------------
# Spy-Ebene 2: dispatch_event (Instance-Attribut-Override)
# ---------------------------------------------------------------------------
def _install_dispatch_spy(window: IntegrationLabWindow) -> None:
    from pyglet.window import BaseWindow as _BW

    _orig = _BW.dispatch_event

    def _spy_dispatch(*args):
        event_type = args[0] if args else "?"
        if event_type in (
            "on_mouse_press", "on_mouse_release",
            "on_mouse_drag", "on_mouse_motion",
            "on_mouse_scroll", "on_mouse_enter", "on_mouse_leave",
        ):
            _record(
                _current_phase[0],
                "dispatch_event",
                event_type,
                f"args[1:4]={args[1:4]}",
            )
        return _orig(window, *args)

    window.dispatch_event = _spy_dispatch  # Instance-Attribut überschreibt Methoden-Lookup

# ---------------------------------------------------------------------------
# Spy-Ebene 1: Win32-Handler-Dict
# ---------------------------------------------------------------------------
def _install_win32_spy(window: IntegrationLabWindow) -> None:
    """Ersetzt relevante Einträge in _view_event_handlers und _event_handlers."""

    def _make_spy(msg_name: str, msg_code: int, orig, is_view: bool) -> object:
        def _spy(msg, wParam, lParam):
            detail = (
                f"wParam=0x{wParam:08X}  lParam=0x{lParam:08X}"
                f"  MK_LB={bool(wParam & MK_LBUTTON)}"
                f"  MK_MB={bool(wParam & MK_MBUTTON)}"
            )
            if msg_code == WM_MOUSEWHEEL:
                delta = ctypes.c_short((wParam >> 16) & 0xFFFF).value
                detail += f"  wheel_delta={delta}"
            _record(_current_phase[0], "Win32-handler", msg_name, detail)
            return orig(msg, wParam, lParam)
        return _spy

    view_d = window._view_event_handlers
    main_d = window._event_handlers

    for msg_code, msg_name in (
        (WM_LBUTTONDOWN, "WM_LBUTTONDOWN"),
        (WM_LBUTTONUP,   "WM_LBUTTONUP"),
        (WM_MBUTTONDOWN, "WM_MBUTTONDOWN"),
        (WM_MOUSEMOVE,   "WM_MOUSEMOVE"),
    ):
        if msg_code in view_d:
            view_d[msg_code] = _make_spy(msg_name, msg_code, view_d[msg_code], True)
        else:
            print(f"  [WARN] {msg_name} (0x{msg_code:03X}) NICHT in _view_event_handlers!")

    for msg_code, msg_name in ((WM_MOUSEWHEEL, "WM_MOUSEWHEEL"),):
        if msg_code in main_d:
            main_d[msg_code] = _make_spy(msg_name, msg_code, main_d[msg_code], False)
        else:
            print(f"  [WARN] {msg_name} (0x{msg_code:03X}) NICHT in _event_handlers!")

# ---------------------------------------------------------------------------
# Hilfsfunktion: aktuelle Phase (Mutable, da schedule_once closures braucht)
# ---------------------------------------------------------------------------
_current_phase: list[str] = ["init"]

# ---------------------------------------------------------------------------
# Framebuffer-Signatur (für Bewegungsnachweis)
# ---------------------------------------------------------------------------
_STRIDE = 11

def _sig(window: IntegrationLabWindow) -> tuple[int, int]:
    gl.glFinish()
    w, h = window.width, window.height
    buf = (gl.GLubyte * (w * h * 3))()
    gl.glReadPixels(0, 0, w, h, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    nb, acc = 0, 0
    for y in range(0, h, _STRIDE):
        base = y * w
        for x in range(0, w, _STRIDE):
            i = (base + x) * 3
            r, g, b = buf[i], buf[i + 1], buf[i + 2]
            if r or g or b:
                nb += 1
                acc = (acc * 131 + r + g * 3 + b * 7) & 0xFFFFFFFF
    return nb, acc

# ---------------------------------------------------------------------------
# Hauptroutine
# ---------------------------------------------------------------------------
def main() -> int:
    lab = build_lab_scene()
    window = IntegrationLabWindow(lab)
    window.set_visible(True)

    hwnd      = window._hwnd
    view_hwnd = window._view_hwnd

    print(f"\n[INFO] hwnd      = 0x{hwnd:08X}")
    print(f"[INFO] view_hwnd = 0x{view_hwnd:08X}")
    print(f"[INFO] _mouse_scale = {getattr(window, '_mouse_scale', 'N/A')}")
    print(f"[INFO] _allow_dispatch_event = {window._allow_dispatch_event}")
    print(f"[INFO] _enable_event_queue   = {window._enable_event_queue}")

    _install_dispatch_spy(window)
    _install_win32_spy(window)

    results: dict[str, bool] = {}
    sigs: dict[str, tuple] = {}

    # Referenz-Framebuffer
    def _step_init(dt):
        _current_phase[0] = "init"
        fg = _user32.GetForegroundWindow()
        print(f"\n[INFO] GetForegroundWindow = 0x{fg:08X}  (hwnd=0x{hwnd:08X}  match={fg == hwnd})")
        window.dispatch_event("on_draw")
        sigs["A"] = _sig(window)
        print(f"[INFO] Sig A (Referenz) = {sigs['A']}")

    # Phase 1: WM_LBUTTONDOWN → view_hwnd
    def _step_lbutton_down(dt):
        _current_phase[0] = "P1_LBUTTONDOWN→view"
        print(f"\n--- Phase 1: PostMessage WM_LBUTTONDOWN → view_hwnd ---")
        x, y = 400, 300
        _user32.PostMessageW(view_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, _pack_lParam(x, y))

    # Phase 2: WM_MOUSEMOVE → view_hwnd + MK_LBUTTON (Drag)
    def _step_mousemove(dt):
        _current_phase[0] = "P2_MOUSEMOVE→view"
        print(f"\n--- Phase 2: PostMessage WM_MOUSEMOVE → view_hwnd + MK_LBUTTON ---")
        # 10 Pixel rechts, 6 Pixel runter (exakt wie _diag_camera_trace)
        _user32.PostMessageW(view_hwnd, WM_MOUSEMOVE, MK_LBUTTON, _pack_lParam(410, 306))
        _user32.PostMessageW(view_hwnd, WM_MOUSEMOVE, MK_LBUTTON, _pack_lParam(420, 312))
        _user32.PostMessageW(view_hwnd, WM_MOUSEMOVE, MK_LBUTTON, _pack_lParam(430, 318))

    # Phase 3: Ergebnis Drag messen
    def _step_measure_drag(dt):
        _current_phase[0] = "P3_measure"
        drag_dispatched = any(
            e["event"] == "on_mouse_drag" for e in _log
        )
        press_dispatched = any(
            e["event"] == "on_mouse_press" for e in _log
        )
        win32_move_called = any(
            e["level"] == "Win32-handler" and "WM_MOUSEMOVE" in e["event"]
            for e in _log
        )
        win32_down_called = any(
            e["level"] == "Win32-handler" and "WM_LBUTTONDOWN" in e["event"]
            for e in _log
        )
        print(f"\n--- Phase 3: Ergebnis Drag ---")
        print(f"  Win32 WM_LBUTTONDOWN handler aufgerufen : {win32_down_called}")
        print(f"  Win32 WM_MOUSEMOVE handler aufgerufen  : {win32_move_called}")
        print(f"  dispatch_event('on_mouse_press') aufger.: {press_dispatched}")
        print(f"  dispatch_event('on_mouse_drag') aufger. : {drag_dispatched}")
        print(f"  window._drag_button nach LBUTTONDOWN    : {window._drag_button}")
        sigs["B_drag"] = _sig(window)
        results["drag_win32_down"] = win32_down_called
        results["drag_win32_move"] = win32_move_called
        results["drag_press"]      = press_dispatched
        results["drag_dispatched"] = drag_dispatched
        results["drag_moved_sig"]  = sigs["B_drag"] != sigs["A"]

    # Phase 4: LButton loslassen
    def _step_lbutton_up(dt):
        _current_phase[0] = "P4_LBUTTONUP"
        _user32.PostMessageW(view_hwnd, WM_LBUTTONUP, 0, _pack_lParam(430, 318))

    # Phase 5: WM_MOUSEWHEEL → _hwnd (normaler Fokus-Pfad simuliert)
    def _step_wheel_main(dt):
        _current_phase[0] = "P5_WHEEL→hwnd"
        print(f"\n--- Phase 5: PostMessage WM_MOUSEWHEEL → _hwnd ---")
        sx, sy = _client_to_screen(hwnd, 400, 300)
        _user32.PostMessageW(hwnd, WM_MOUSEWHEEL,
                             _pack_wParam_wheel(WHEEL_DELTA), _pack_lParam(sx, sy))

    # Phase 6: WM_MOUSEWHEEL → view_hwnd (direct, Focus irrelevant)
    def _step_wheel_view(dt):
        _current_phase[0] = "P6_WHEEL→view_hwnd"
        print(f"\n--- Phase 6: PostMessage WM_MOUSEWHEEL → view_hwnd (direkt) ---")
        sx, sy = _client_to_screen(view_hwnd, 400, 300)
        _user32.PostMessageW(view_hwnd, WM_MOUSEWHEEL,
                             _pack_wParam_wheel(WHEEL_DELTA), _pack_lParam(sx, sy))

    # Phase 7: Ergebnis Scroll + Auswertung
    def _step_measure_scroll(dt):
        _current_phase[0] = "P7_measure"
        scroll_main = any(
            e["event"] == "on_mouse_scroll" and "P5" in e["phase"]
            for e in _log
        )
        scroll_view = any(
            e["event"] == "on_mouse_scroll" and "P6" in e["phase"]
            for e in _log
        )
        win32_wheel_main = any(
            e["level"] == "Win32-handler" and "WHEEL" in e["event"] and "P5" in e["phase"]
            for e in _log
        )
        win32_wheel_view = any(
            e["level"] == "Win32-handler" and "WHEEL" in e["event"] and "P6" in e["phase"]
            for e in _log
        )
        sigs["C_scroll"] = _sig(window)
        results["scroll_win32_hwnd"]  = win32_wheel_main
        results["scroll_win32_view"]  = win32_wheel_view
        results["scroll_dispatch_hwnd"] = scroll_main
        results["scroll_dispatch_view"] = scroll_view
        results["scroll_moved_sig"]   = sigs["C_scroll"] != sigs["A"]
        _print_verdict()

    def _print_verdict():
        print("\n" + "=" * 70)
        print("GESAMT-AUSWERTUNG  _diag_input_trace")
        print("=" * 70)
        for k, v in results.items():
            marker = "✓" if v else "✗"
            print(f"  {marker}  {k:35s} = {v}")

        print()
        # Kandidat-A-Test
        # WM_MOUSEWHEEL → _hwnd: wenn Fokus fehlt, würde OS den NICHT liefern.
        # PostMessageW umgeht Focus → wenn trotzdem kein on_mouse_scroll:
        #   Entweder Win32-Handler nicht in _event_handlers ODER Dispatch-Bug.
        a_partial = results.get("scroll_dispatch_hwnd") or results.get("scroll_dispatch_view")
        b_partial = results.get("drag_dispatched")
        win32_drag_ok = results.get("drag_win32_move")
        win32_scroll_ok = results.get("scroll_win32_hwnd") or results.get("scroll_win32_view")

        if not win32_drag_ok and not win32_scroll_ok:
            print(">>> BEFUND: Win32-Handler-Ebene NICHT erreicht (weder Drag noch Scroll).")
            print("    Ursache: _view_event_handlers/_event_handlers nicht korrekt befüllt,")
            print("    oder PostMessageW-Nachrichten werden von wndproc ignoriert.")
            print("    → NICHT Kandidat A oder B — eigene Kategorie: wndproc-Defekt.")
        elif win32_drag_ok and not b_partial:
            print(">>> BEFUND: Win32-Handler WM_MOUSEMOVE aufgerufen, aber")
            print("    dispatch_event('on_mouse_drag') NICHT ausgeführt.")
            print("    Root Cause: MK_LBUTTON korrekt gesetzt, aber ENTWEDER")
            print("      a) _drag_button ist None (WM_LBUTTONDOWN nicht dispatcht), ODER")
            print("      b) buttons-Check in _event_mousemove schlägt fehl.")
            print("    → KANDIDAT B teilweise bestätigt (Dispatch-Defekt).")
        elif not win32_drag_ok and win32_scroll_ok:
            print(">>> BEFUND: WM_MOUSEMOVE Win32-Handler NICHT aufgerufen,")
            print("    WM_MOUSEWHEEL Win32-Handler aber schon.")
            print("    Ursache: _view_event_handlers enthält WM_MOUSEMOVE nicht?")
            print("    → Prüfe _view_event_handlers-Inhalt (s. INFO oben).")
        elif b_partial and a_partial:
            print(">>> BEFUND: Beide Pfade funktionieren via PostMessageW.")
            print("    Root Cause ist ausschließlich Focus/OS-Routing:")
            print("      - WM_MOUSEWHEEL → OS sendet an fokussiertes Fenster.")
            print("        Wenn Lab-Fenster keinen Fokus hat, geht Scroll ans Terminal.")
            print("      - WM_LBUTTONDOWN/MOUSEMOVE → nach Klick müsste Orbit wirken.")
            print("    → KANDIDAT A bestätigt.")
            print("    Empfehlung: set_mouse_platform_visible(True) + Fokus prüfen,")
            print("    oder WM_MOUSEWHEEL alternativ über Raw Input abfangen.")
        elif b_partial and not a_partial:
            print(">>> BEFUND: Drag funktioniert, Scroll aber nicht via PostMessageW.")
            print("    WM_MOUSEWHEEL fehlt in _event_handlers oder Dispatch bricht ab.")
            print("    → Hybrider Root Cause: Scroll = eigene Kategorie.")
        else:
            print(">>> BEFUND: Unklares Ergebnis — manuell analysieren.")
        print("=" * 70)

    def _finish(dt):
        window.close()
        pyglet.app.exit()

    pyglet.clock.schedule_once(_step_init,         0.4)
    pyglet.clock.schedule_once(_step_lbutton_down, 0.6)
    pyglet.clock.schedule_once(_step_mousemove,    0.8)
    pyglet.clock.schedule_once(_step_measure_drag, 1.1)
    pyglet.clock.schedule_once(_step_lbutton_up,   1.3)
    pyglet.clock.schedule_once(_step_wheel_main,   1.5)
    pyglet.clock.schedule_once(_step_wheel_view,   1.7)
    pyglet.clock.schedule_once(_step_measure_scroll, 2.0)
    pyglet.clock.schedule_once(_finish,             2.3)

    pyglet.app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
