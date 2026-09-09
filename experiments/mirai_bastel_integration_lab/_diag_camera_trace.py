"""WP-IL-01 — minimaler Camera->GL Render Trace (keine Architektur-Änderung).

Ziel ausschliesslich diagnostisch: eindeutig klären, ob und wo ein
echter Kamera-Orbit im laufenden Integration-Lab-Viewport am Mesh
vorbeiht. Es wird NICHTS an Production/Core geändert — nur beobachtet,
gezählt und verglichen.

Die fünf zu prüfenden Stellen (Station 1..5):

  1) Maus-Drag-Pfad: mutiert `on_mouse_drag` tatsächlich
     `camera.eye()/yaw/pitch/distance`?                 (Kamera-Änderung)
  2) Folgt daraus eine andere `build_view_matrix()`?    (View-Matrix-Änderung)
  3) Schreibt `on_draw` diese live-Matrix in `u_view`?   (Uniform-Sichtbarkeit)
  4) Wird diese Matrix beim `vlist.draw()` verwendet?    (Shader-Anwendung)
     -> indirekt messbar: unterscheidet sich das gerenderte Bild?
  5) Wenn State + Matrix korrekt wechseln:
     Wird `on_draw` überhaupt nach Maus-Drag neu getriggert?
       B == A  -> pyglet redrawt nach Drag nicht   (Kandidat-Root-Cause)
       C != A  -> gezwungener Redraw zeigt Bewegung (Matrix ist wirksam)

Messung: Framebuffer-Signatur (nonblack + Hash) über glReadPixels,
plus ein Spy auf `build_view_matrix`, der zählt und die letzte
übergebene Matrix speichert.

Reproduktion des echten Pfads (nicht des Probed-Pfads!):
    window.on_mouse_press(...)  ->  window.on_mouse_drag(...)
(Probe nutzte `clock.schedule_once(cam.orbit, ...)`, was andere
Redraw-Semantik hervorruft als der echte Event-Handler.)

Aufruf (echte GL nötig):
    python experiments/mirai_bastel_integration_lab/_diag_camera_trace.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import math
from pyglet import gl
from pyglet.window import key as _key
from pyglet.window import mouse as _mouse

import pyglet

_THIS_DIR = Path(__file__).resolve().parent
_REPO = _THIS_DIR.parent.parent
for _p in (str(_THIS_DIR), str(_REPO), str(_REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from integration.lab_viewport import IntegrationLabWindow  # noqa: E402
from scene.scene_objects import build_lab_scene  # noqa: E402

_STRIDE = 11


def _signature(window):
    """(nonblack_subsampled, hash) des aktuellen Default-Framebuffer."""
    gl.glFinish()
    w, h = window.width, window.height
    buf = (gl.GLubyte * (w * h * 3))()
    gl.glReadPixels(0, 0, w, h, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    nonblack = 0
    acc = 0
    for y in range(0, h, _STRIDE):
        base = y * w
        for x in range(0, w, _STRIDE):
            i = (base + x) * 3
            r, g, b = buf[i], buf[i + 1], buf[i + 2]
            if r or g or b:
                nonblack += 1
                acc = (acc * 131 + r + g * 3 + b * 7) & 0xFFFFFFFF
    return nonblack, acc


def main() -> int:
    lab = build_lab_scene()
    window = IntegrationLabWindow(lab)
    window.set_visible(True)
    cam = window.camera

    # --- Spy auf build_view_matrix (Kamera-Instanz, die on_draw liest) ----
    last_called = {"n": 0}
    last_uview = {"m": None}
    orig_bvm = type(cam).build_view_matrix  # Original-Methode der Klasse

    def _spy(self):
        m = orig_bvm(self)
        last_uview["m"] = list(m)
        last_called["n"] += 1
        return m

    cam.build_view_matrix = types.MethodType(_spy, cam)

    def _fmt(m):
        return m[:3] + ["..."] + m[12:]

    print(f"u_view[0:3]={_fmt(list(orig_bvm(cam)))[:4]}")

    # --- Zeitplan -----------------------------------------------------------
    plan = []

    def _step_initial(_dt):
        # A: erstes, gesteuertes Draw, damit der Framebuffer befüllt ist.
        window.dispatch_event("on_draw")
        plan.append(("A", _signature(window)))

    def _step_drag(_dt):
        # Reale Maus-Chain: press -> drag (Orbit). on_drag returned
        # EVENT_HANDLED und dispatcht KEIN on_draw selbst.
        ey0 = cam.eye()
        y0, p0, d0 = cam.yaw, cam.pitch, cam.distance
        m0 = list(orig_bvm(cam))  # View-Matrix VOR dem Drag
        window.on_mouse_press(400, 300, _mouse.LEFT, 0)
        window._drag_moved = 0.0
        ret = window.on_mouse_drag(400, 300, 10, 6, _mouse.LEFT, 0)
        ey1, y1, p1, d1 = cam.eye(), cam.yaw, cam.pitch, cam.distance
        m1 = list(orig_bvm(cam))  # View-Matrix NACH dem Drag (live, ungezeichnet)
        print("\n=== STATION 1: Kamera-Mutation durch on_mouse_drag ===")
        print(f"  eye      {ey0} -> {ey1}  diff={tuple(round(a-b,4) for a,b in zip(ey1,ey0))}")
        print(f"  yaw      {math.degrees(y0):.2f} -> {math.degrees(y1):.2f}")
        print(f"  pitch    {math.degrees(p0):.2f} -> {math.degrees(p1):.2f}")
        print(f"  distance {d0:.4f} -> {d1:.4f}")
        print(f"  drag returned EVENT_HANDLED={ret == pyglet.event.EVENT_HANDLED}")
        print(f"  _drag_moved={window._drag_moved}")
        print("\n=== STATION 2: build_view_matrix() ändert sich ====")
        print(f"  m0[:3]={m0[:3]}")
        print(f"  m1[:3]={m1[:3]}")
        print(f"  m0 != m1 : {m0 != m1}")
        print(f"  spy.on_draw-called so far (sollte 1 = A sein): {last_called['n']}")

    def _step_measure_b(_dt):
        # B: nach Maus-Drag -- WURDE on_draw neu getriggert (auto-redraw)?
        sig = _signature(window)
        plan.append(("B", sig))
        a = plan[0][1]
        b = sig
        print("\n=== STATION 5a: Redraw nach Maus-Drag (auto) ===")
        print(f"  A={a}  B={b}  A!=B (auto-redraw wirkt): {a != b}")

    def _step_forced(_dt):
        # C: gezwungener Redraw -> on_draw liest live build_view_matrix().
        draws_before = last_called["n"]
        uview_before = last_uview["m"]
        m_live = list(orig_bvm(cam))
        window.dispatch_event("on_draw")
        draws_after = last_called["n"]
        uview_after = last_uview["m"]
        plan.append(("C", _signature(window)))
        a = plan[0][1]
        c = plan[-1][1]
        print("\n=== STATION 3: on_draw schreibt live u_view ===")
        print(f"  on_draw build_view_matrix calls: {draws_before} -> {draws_after} (== +1: ja)")
        print(f"  live matrix != uview_before: {m_live != uview_before}")
        print(f"  uview_after == live matrix: {uview_after == m_live}")
        print("\n=== STATION 4/5b: Bild nach gezwungenem Redraw ===")
        print(f"  A={a}  C={c}  A!=C (Mesh bewegt sich sichtbar): {a != c}")

    def _finish(_dt):
        print("\n=== GESAMT-TRACE ===")
        a = plan[0][1]
        print(f"  A(nach Start)   ={a}")
        print(f"  B(nach Drag)    ={plan[1][1] if len(plan)>1 else 'n/a'}")
        print(f"  C(nach forced)  ={plan[2][1] if len(plan)>2 else 'n/a'}")
        if len(plan) >= 3:
            b = plan[1][1]
            c = plan[2][1]
            auto = (b != a)
            motion = (c != a)
            print(f"  auto_redraw nach Drag: {auto}")
            print(f"  motion nach forced redraw: {motion}")
            if auto:
                print("  -> Kamera-Update wirkt AUTOMATISCH (B!=A).")
                print("     Dann ist das 'Mesh bewegt sich nicht' ein")
                print("     Event-/Input-Fokus-Problem, NICHT Renderer.")
            else:
                if motion:
                    print("  >>> ROOT-CAUSE-KANDIDAT: on_mouse_drag returned")
                    print("       EVENT_HANDLED und loest KEIN Redraw aus.")
                    print("       u_view ist live (C!=A), aber das Bild bleibt")
                    print("       nach Drag stumm, weil pyglet nicht neu zeichnet.")
                    print("       Minimaler Fix-Vorschlag: am Ende von")
                    print("       on_mouse_drag/on_mouse_scroll/on_mouse_motion")
                    print("       `self._invalidate()` (oder")
                    print("       `self.dispatch_event('on_draw')`) setzen,")
                    print("       alternativ `window.set_auto_draw(True)` im Init.")
                else:
                    print("  >>> Matrix ist live UND draw wird getriggert, aber")
                    print("       C==A: Mesh bewegt sich trotzdem nicht ->")
                    print("       vlist.draw bindet u_view nicht, oder Shader")
                    print("       liest u_view nicht (weiter untersuchen).")
        window.close()
        pyglet.app.exit()

    pyglet.clock.schedule_once(_step_initial, 0.5)
    pyglet.clock.schedule_once(_step_drag, 0.7)
    pyglet.clock.schedule_once(_step_measure_b, 0.9)
    pyglet.clock.schedule_once(_step_forced, 1.1)
    pyglet.clock.schedule_once(_finish, 1.3)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
