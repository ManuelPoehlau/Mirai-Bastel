"""Re-Symmetrize-Vorschau im Fenster-Adapter (WP-SYM-LAB-03 Slice 3).

Stellvertreter-Fenster aus `test_run_app` (kein GL). Geprüft wird H2-R3 („the
pyglet handler returns EVENT_HANDLED in every branch", review N4) für M öffnen,
abgelehnte Taste, Esc schließt, M führt aus, und die blaue Vorschau-Zeile über der
HUD-Zeile (README Slice 5, Schritt 4; Farbe aus dem alten `lab_window`).
"""

from __future__ import annotations

import pytest

from symmetry_lab import lab_app_window, run_app
from symmetry_lab.lab_app import PREVIEW_HINT, ROW_MARK, ROW_PREVIEW, preview_text

from ._app_lab_preview_support import first_visible, side_vertices
from ._app_lab_support import click, forbid_lab_calls, screen  # noqa: F401
from ._pyglet_headless import import_pyglet
from .test_run_app import FakeWindow

pyglet = import_pyglet()
try:
    from pyglet.window import key  # noqa: E402
except Exception as exc:  # pragma: no cover - umgebungsabhängig (kein EGL)
    pytest.skip(f"pyglet.window nicht verfügbar: {exc}", allow_module_level=True)

HANDLED = pyglet.event.EVENT_HANDLED


@pytest.fixture
def built():
    window = FakeWindow()
    app, lab, hud = run_app.build_lab(window, "man_with_shoes_basemesh", run_app.load_src_main())
    assert window.dispatch("on_key_press", key.S, key.MOD_SHIFT) is HANDLED
    click(app, *screen(app, first_visible(app, side_vertices(app, 0))))
    return window, app, lab, hud


def test_every_branch_returns_event_handled(built):
    window, app, lab, _hud = built
    assert window.dispatch("on_key_press", key.M, 0) is HANDLED  # öffnet
    assert lab.preview_open and app.command_gate is ROW_PREVIEW.gate
    assert window.dispatch("on_key_press", key.W, 0) is HANDLED  # App-Gate lehnt ab
    assert app.status_message == PREVIEW_HINT and app.transform_command is None
    assert window.dispatch("on_key_release", key.W, 0) is HANDLED
    assert window.dispatch("on_key_press", key.S, key.MOD_SHIFT) is HANDLED  # Lab lehnt ab
    assert window.dispatch("on_key_press", key.ESCAPE, 0) is HANDLED  # D1: schließt
    assert not lab.preview_open and app.command_gate is ROW_MARK.gate
    history = len(app.history)
    assert window.dispatch("on_key_press", key.M, 0) is HANDLED
    assert window.dispatch("on_key_press", key.M, 0) is HANDLED  # führt aus
    assert not lab.preview_open
    assert len(app.history) == history + 1
    assert window.dispatch("on_key_press", key.ESCAPE, 0) is HANDLED  # ohne Vorschau: App


class _FakeLabel:
    """Stellvertreter für `pyglet.text.Label` (kein GL): merkt Text, Lage, Farbe."""

    drawn: list = []

    def __init__(self, text, x, y, width, multiline, anchor_y, font_size, color) -> None:
        self.text, self.x, self.y, self.width, self.color = text, x, y, width, color
        self.content_height = 30

    def draw(self) -> None:
        _FakeLabel.drawn.append((self.text, self.y, self.color))


def test_preview_line_is_drawn_above_the_hud_line_while_open(built, monkeypatch):
    window, app, lab, hud = built
    monkeypatch.setattr(pyglet.text, "Label", _FakeLabel)
    _FakeLabel.drawn = []
    hud.draw()
    assert [color for _text, _y, color in _FakeLabel.drawn] == [lab_app_window.HUD_COLOR]

    window.dispatch("on_key_press", key.M, 0)
    _FakeLabel.drawn = []
    hud.draw()
    (status, status_y, _c), (line, line_y, colour) = _FakeLabel.drawn
    assert status == hud.text()
    assert line == preview_text(lab) and "M = ausführen, ESC = abbrechen" in line
    assert colour == lab_app_window.PREVIEW_COLOR == (130, 170, 255, 255)
    assert line_y == status_y + 30 + lab_app_window.PREVIEW_GAP

    window.dispatch("on_key_press", key.ESCAPE, 0)
    _FakeLabel.drawn = []
    hud.draw()
    assert [color for _text, _y, color in _FakeLabel.drawn] == [lab_app_window.HUD_COLOR]
