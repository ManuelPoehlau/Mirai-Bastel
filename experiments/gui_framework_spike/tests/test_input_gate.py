"""Eingabe-Hoheit: Testfälle aus dem Brief (Klick im Panel wählt nichts im Viewport, Taste im Textfeld löst nichts aus)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from input_gate import InputGate, rect_hit  # noqa: E402

PANEL = (10.0, 10.0, 100.0, 200.0)


def _gate(kbd=False):
    state = {"kbd": kbd}
    gate = InputGate(lambda x, y: rect_hit(PANEL, x, y), lambda: state["kbd"])
    return gate, state


def test_click_in_panel_is_kept_click_outside_goes_to_app():
    gate, _ = _gate()
    assert gate.press(1, 50, 50) is True
    assert gate.release(1) is True
    assert gate.press(1, 500, 500) is False
    assert gate.release(1) is False


def test_drag_started_in_viewport_stays_with_app_over_the_panel():
    gate, _ = _gate()
    gate.press(1, 500, 500)
    assert gate.drag((1,)) is False  # Orbit/Lasso läuft weiter, auch über dem Panel
    assert gate.release(1) is False


def test_drag_started_in_panel_never_reaches_app():
    gate, _ = _gate()
    gate.press(1, 50, 50)
    assert gate.drag((1,)) is True
    assert gate.release(1) is True


def test_motion_and_scroll_only_over_panel():
    gate, _ = _gate()
    assert gate.motion(50, 50) and gate.hovering_panel
    assert not gate.motion(500, 500) and not gate.hovering_panel
    assert gate.scroll(50, 50) and not gate.scroll(500, 500)


def test_keys_go_to_app_unless_text_field_active():
    gate, state = _gate()
    assert gate.key_press(119) is False  # W
    state["kbd"] = True  # Textfeld aktiv, W noch gehalten
    assert gate.key_release(119) is False  # Release geht an App, sonst bliebe W gehalten
    assert gate.key_press(104) is True  # H im Textfeld: kein Command
    assert gate.key_release(104) is True
    state["kbd"] = False
    assert gate.key_release(104) is False  # nie weitergeleitet, harmlos
