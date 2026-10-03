"""E5-Modus im Fenster-Adapter (WP-SYM-LAB-03 Slice 4).

Stellvertreter-Fenster aus `test_run` (kein GL), Label-Stellvertreter wie in
`test_app_lab_preview_window`. Geprüft: Shift+B über den pyglet-Handler
(`EVENT_HANDLED`, auch abgelehnt), `E5: <Modus>` in der HUD-Zeile und die orange
E5-Warnzeile über ihr, solange eine Knife-Session unter Symmetrie läuft.
"""

from __future__ import annotations

import pytest

from symmetry_lab import lab_app_window, run
from symmetry_lab.lab_app import KNIFE_ONE_SIDED_TEXT, GateMode, block_row

from ._app_lab_support import MISS, forbid_lab_calls  # noqa: F401
from ._pyglet_headless import import_pyglet
from .test_run import FakeWindow

pyglet = import_pyglet()
try:
    from pyglet.window import key  # noqa: E402
except Exception as exc:  # pragma: no cover - umgebungsabhängig (kein EGL)
    pytest.skip(f"pyglet.window nicht verfügbar: {exc}", allow_module_level=True)

HANDLED = pyglet.event.EVENT_HANDLED


class _FakeLabel:
    """Stellvertreter für `pyglet.text.Label` (kein GL): merkt Text, Lage, Farbe."""

    drawn: list = []

    def __init__(self, text, x, y, width, multiline, anchor_y, font_size, color) -> None:
        self.text, self.x, self.y, self.width, self.color = text, x, y, width, color
        self.content_height = 30

    def draw(self) -> None:
        _FakeLabel.drawn.append((self.text, self.y, self.color))


@pytest.fixture
def built():
    window = FakeWindow()
    app, lab, hud = run.build_lab(window, "subd_cube", run.load_src_main())
    assert window.dispatch("on_key_press", key.S, key.MOD_SHIFT) is HANDLED
    assert lab.axis == "X"
    return window, app, lab, hud


def test_shift_b_through_the_window_toggles_the_mode_and_the_hud(built):
    """Default BLOCK (Slice 5): C abgelehnt; Shift+B → MARK im HUD, Gate-Zeile leer."""
    window, app, lab, hud = built
    assert lab.gate_mode is GateMode.BLOCK
    assert app.command_gate == block_row().gate
    assert " | E5: BLOCK | " in hud.text()
    assert window.dispatch("on_key_press", key.C, 0) is HANDLED  # vom Gate abgelehnt
    assert not app.knife_active
    assert window.dispatch("on_key_press", key.B, key.MOD_SHIFT) is HANDLED
    assert lab.gate_mode is GateMode.MARK
    assert app.command_gate is None
    assert " | E5: MARK | " in hud.text()


def test_warning_line_is_drawn_above_the_hud_line_while_a_knife_runs(built, monkeypatch):
    window, app, lab, hud = built
    monkeypatch.setattr(pyglet.text, "Label", _FakeLabel)
    _FakeLabel.drawn = []
    hud.draw()
    assert [color for _t, _y, color in _FakeLabel.drawn] == [lab_app_window.HUD_COLOR]

    # Eine einseitige Knife-Session gibt es nur in MARK (Default seit Slice 5: BLOCK).
    assert window.dispatch("on_key_press", key.B, key.MOD_SHIFT) is HANDLED
    assert lab.gate_mode is GateMode.MARK
    app.pointer_motion(*MISS)
    app.selection.clear()
    assert window.dispatch("on_key_press", key.C, 0) is HANDLED
    assert app.knife_active
    assert window.dispatch("on_key_press", key.B, key.MOD_SHIFT) is HANDLED  # abgelehnt
    assert lab.gate_mode is GateMode.MARK
    _FakeLabel.drawn = []
    hud.draw()
    (status, status_y, _c), (line, line_y, colour) = _FakeLabel.drawn
    assert status == hud.text()
    assert line == KNIFE_ONE_SIDED_TEXT
    assert colour == lab_app_window.WARNING_COLOR
    assert line_y == status_y + 30 + lab_app_window.PREVIEW_GAP

    assert window.dispatch("on_key_press", key.ESCAPE, 0) is HANDLED
    assert not app.knife_active
    _FakeLabel.drawn = []
    hud.draw()
    assert [color for _t, _y, color in _FakeLabel.drawn] == [lab_app_window.HUD_COLOR]
