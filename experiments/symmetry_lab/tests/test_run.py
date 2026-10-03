"""`run` smoke test (bis Slice 5 `run_app`): Fenster-Aufbau headless, Handler aus `src/main.py` + Lab darüber.

Stellvertreter-Fenster wie `tests/test_main_wiring.py::FakeWindow` (zeichnet nichts,
kein GL), plus `push_handlers` als oberste Handler-Ebene wie bei pyglet. Gebaut wird
mit `run.build_lab` und dem echten `src/main.py` (`install_handlers`, H6), ohne
GL-Typen (TraceStore). Die pyglet-Tastenkonstanten brauchen `pyglet.window`
(`_pyglet_headless`, Skip ohne pyglet).
"""

from __future__ import annotations

import pytest

from symmetry_lab import run
from symmetry_lab.lab_app import block_row, hud_text

from ._app_lab_support import HEIGHT, WIDTH, forbid_lab_calls  # noqa: F401
from ._pyglet_headless import import_pyglet

pyglet = import_pyglet()
try:
    from pyglet.window import key  # noqa: E402
except Exception as exc:  # pragma: no cover - umgebungsabhängig (kein EGL)
    pytest.skip(f"pyglet.window nicht verfügbar: {exc}", allow_module_level=True)


class FakeWindow:
    """`event` (Basis-Ebene), `push_handlers` (oberste Ebene), Größe, `clear`."""

    def __init__(self) -> None:
        self.width = WIDTH
        self.height = HEIGHT
        self.handlers: dict = {}
        self.pushed: dict = {}
        self.cleared = 0

    def event(self, func):
        self.handlers[func.__name__] = func
        return func

    def push_handlers(self, **handlers) -> None:
        self.pushed.update(handlers)

    def clear(self) -> None:
        self.cleared += 1

    def dispatch(self, name: str, *args):
        """Wie pyglet: oberste Ebene zuerst, darunter nur, wenn nicht behandelt."""
        for layer in (self.pushed, self.handlers):
            handler = layer.get(name)
            if handler is not None and handler(*args) is pyglet.event.EVENT_HANDLED:
                return pyglet.event.EVENT_HANDLED
        return None


@pytest.fixture
def built():
    window = FakeWindow()
    src_main = run.load_src_main()
    app, lab, hud = run.build_lab(window, "subd_cube", src_main)
    return window, app, lab, hud


def test_load_src_main_is_the_production_entry():
    module = run.load_src_main()
    for name in ("create_window", "install_handlers", "run", "GL_TYPES"):
        assert hasattr(module, name)


def test_window_wiring_reuses_main_handlers_and_pushes_two(built):
    """Die Handler aus `main.py` liegen unten (alle), das Lab legt nur
    `on_key_press` und `on_draw` darüber."""
    window, app, lab, _hud = built
    assert {"on_key_press", "on_key_release", "on_mouse_press", "on_mouse_motion",
            "on_draw", "on_deactivate", "on_resize"} <= set(window.handlers)
    assert set(window.pushed) == {"on_key_press", "on_draw"}
    assert app.viewport.extra_overlays == lab.overlays
    assert app.viewport_width == WIDTH and app.viewport_height == HEIGHT


def test_one_key_event_through_lab_key_press(built):
    """Smoke: Shift+S über den pyglet-Handler → Lab-Zyklus, Gate-Zeile installiert,
    `EVENT_HANDLED`; eine weitergeleitete Taste (Esc) ebenfalls `EVENT_HANDLED`."""
    window, app, lab, _hud = built
    assert window.dispatch("on_key_press", key.S, key.MOD_SHIFT) is pyglet.event.EVENT_HANDLED
    assert lab.axis == "X"
    assert app.command_gate == block_row().gate  # E5-Default BLOCK (Slice 5)
    assert window.dispatch("on_key_press", key.ESCAPE, 0) is pyglet.event.EVENT_HANDLED
    assert window.dispatch("on_key_press", key.Z, key.MOD_CTRL) is pyglet.event.EVENT_HANDLED
    assert lab.axis is None
    assert app.command_gate is None


def test_main_shift_tracking_survives_the_lab_handler(built):
    """UX2b-Seiteneffekt aus `main.py` (Shift-Tracking für den Knife-Hover) bleibt:
    Shift-Press läuft durch den Lab-Handler in den `main.py`-Handler."""
    window, app, _lab, _hud = built
    window.dispatch("on_key_press", key.LSHIFT, key.MOD_SHIFT)
    assert app._shift_held is True
    window.dispatch("on_key_press", key.S, key.MOD_SHIFT)  # Lab-Taste
    assert app._shift_held is True
    window.dispatch("on_key_release", key.S, key.MOD_SHIFT)
    window.dispatch("on_key_release", key.LSHIFT, 0)
    assert app._shift_held is False


def test_forwarded_key_runs_main_handler_and_rederives_gate(built):
    """Eine Nicht-Lab-Taste läuft durch den `main.py`-Handler (`app.key_press`) und
    danach leitet das Lab die Gate-Zeile neu ab."""
    window, app, lab, _hud = built
    window.dispatch("on_key_press", key.S, key.MOD_SHIFT)
    calls = []
    original = app.key_press

    def spy(inp):
        calls.append(inp)
        return original(inp)

    app.key_press = spy
    window.dispatch("on_key_press", key.Z, key.MOD_CTRL)
    assert [c.value for c in calls] == ["z"]
    assert lab.axis is None and app.command_gate is None


def test_draw_runs_main_draw_first_then_the_hud(built, monkeypatch):
    """Der Lab-`on_draw` ruft erst den Draw aus `main.py`, dann die HUD-Zeile, und
    gibt `EVENT_HANDLED` zurück (sonst liefe der `main.py`-Draw ein zweites Mal)."""
    window, app, _lab, hud = built
    order = []
    # Kein GL-Kontext am Stellvertreter-Fenster: den einen GL-Aufruf aus main.py stilllegen.
    monkeypatch.setattr(pyglet.gl, "glClearColor", lambda *rgba: order.append("clear"))
    monkeypatch.setattr(app.viewport, "render", lambda: order.append("render"))
    monkeypatch.setattr(hud, "draw", lambda: order.append("hud"))
    assert window.dispatch("on_draw") is pyglet.event.EVENT_HANDLED
    assert order == ["clear", "render", "hud"]
    assert window.cleared == 1


def test_hud_label_text_is_the_full_lab_line(built):
    """Slice 2: das HUD-Label zeigt `hud_text` mit dem Asset-Namen aus `run`
    und dem Befund-Cache des Labs."""
    window, app, lab, hud = built
    window.dispatch("on_key_press", key.S, key.MOD_SHIFT)
    # Slice 4: mit dem E5-Modus des Labs (nur bei aktiver Symmetrie sichtbar),
    # seit Slice 5 Default BLOCK.
    assert hud.text() == hud_text(app, "subd_cube", lab.report, lab.gate_mode)
    assert " | E5: BLOCK | " in hud.text()
    assert hud.text().startswith("subd_cube | 26 V | Symmetrie: X (valid) | ohne Partner: 0")
