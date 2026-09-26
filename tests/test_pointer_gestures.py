"""`mirai.interaction.pointer.PointerGestures` — Klick vs. Drag (AD-019, WP-06 B2).

Headless: eigenes `BindingSet` mit Test-Commands, kein pyglet/Fenster.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from mirai.interaction.input import BindingSet, Input
from mirai.interaction.pointer import CLICK_THRESHOLD_PX, Click, DragStep, PointerGestures

CLICK = "TestClick"
DRAG = "TestDrag"
BOTH_CLICK = "TestBothClick"
BOTH_DRAG = "TestBothDrag"


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


def _drag(value: str, *modifiers: str) -> Input:
    return Input("drag", value, frozenset(modifiers))


@pytest.fixture
def gestures() -> PointerGestures:
    bs = BindingSet()
    bs.set_default(_drag("LEFT", "alt", "shift"), DRAG)  # nur Drag
    bs.set_default(_mouse("LEFT"), CLICK)  # nur Klick
    bs.set_default(_mouse("LEFT", "alt"), BOTH_CLICK)  # beides
    bs.set_default(_drag("LEFT", "alt"), BOTH_DRAG)
    return PointerGestures(bs)


def test_threshold_is_playground_value():
    assert CLICK_THRESHOLD_PX == 5.0


# -- nur Drag gebunden ---------------------------------------------------------


def test_drag_only_starts_on_press_without_dead_zone(gestures):
    gestures.press(_mouse("LEFT", "alt", "shift"))
    assert gestures.drag(1, 0) == DragStep(DRAG, 1, 0)
    assert gestures.drag(0, -2) == DragStep(DRAG, 0, -2)


def test_drag_only_release_is_no_click(gestures):
    gestures.press(_mouse("LEFT", "alt", "shift"))
    assert gestures.release("LEFT", 10, 10) is None
    assert not gestures.active


# -- nur Klick gebunden --------------------------------------------------------


def test_click_only_fires_on_release_below_threshold(gestures):
    gestures.press(_mouse("LEFT"))
    assert gestures.drag(2, 2) is None  # 4 px < 5
    assert gestures.release("LEFT", 30, 40) == Click(CLICK, 30, 40)
    assert not gestures.active


def test_click_only_discarded_at_threshold(gestures):
    gestures.press(_mouse("LEFT"))
    assert gestures.drag(3, 0) is None
    assert gestures.drag(0, -2) is None  # 5 px, Manhattan
    assert gestures.release("LEFT", 30, 40) is None


# -- beides gebunden -----------------------------------------------------------


def test_both_bound_resolves_to_drag_at_threshold_with_full_delta(gestures):
    gestures.press(_mouse("LEFT", "alt"))
    assert gestures.drag(1, 1) is None
    assert gestures.drag(-1, 1) is None  # 4 px, noch offen
    assert gestures.drag(1, 0) == DragStep(BOTH_DRAG, 1, 2)  # 5 px: Summe nachgereicht
    assert gestures.drag(2, -1) == DragStep(BOTH_DRAG, 2, -1)
    assert gestures.release("LEFT", 0, 0) is None


def test_both_bound_resolves_to_click_on_early_release(gestures):
    gestures.press(_mouse("LEFT", "alt"))
    assert gestures.drag(2, 1) is None
    assert gestures.release("LEFT", 7, 8) == Click(BOTH_CLICK, 7, 8)


# -- ungebunden / Fixierung / fremde Tasten ------------------------------------


def test_unbound_press_is_swallowed(gestures):
    gestures.press(_mouse("RIGHT"))
    assert gestures.active
    assert gestures.drag(20, 20) is None
    assert gestures.release("RIGHT", 0, 0) is None
    assert not gestures.active


def test_unbound_modifier_combination_is_swallowed(gestures):
    # Exaktes Modifier-Matching: Ctrl+Shift ist nicht gebunden.
    gestures.press(_mouse("LEFT", "ctrl", "shift"))
    assert gestures.drag(1, 0) is None
    assert gestures.release("LEFT", 0, 0) is None


def test_gesture_fixed_at_press_despite_modifier_change(gestures):
    gestures.press(_mouse("LEFT", "alt", "shift"))
    assert gestures.drag(1, 0) == DragStep(DRAG, 1, 0)
    # Release mit anderen Modifiern: nur die Taste zählt.
    assert gestures.release("LEFT", 0, 0) is None
    assert not gestures.active

    gestures.press(_mouse("LEFT"))
    gestures.drag(1, 0)
    assert gestures.release("LEFT", 5, 5) == Click(CLICK, 5, 5)


def test_foreign_button_press_ignored_while_gesture_runs(gestures):
    gestures.press(_mouse("LEFT", "alt", "shift"))
    gestures.press(_mouse("LEFT"))  # zweiter Press: ignoriert
    gestures.press(_mouse("MIDDLE"))
    assert gestures.active_button == "LEFT"
    assert gestures.drag(3, 0) == DragStep(DRAG, 3, 0)


def test_foreign_button_release_ignored(gestures):
    gestures.press(_mouse("LEFT"))
    gestures.press(_mouse("RIGHT"))
    assert gestures.release("RIGHT", 0, 0) is None
    assert gestures.active
    assert gestures.release("LEFT", 1, 2) == Click(CLICK, 1, 2)


def test_idle_drag_and_release_are_noops(gestures):
    assert gestures.drag(10, 10) is None
    assert gestures.release("LEFT", 0, 0) is None


def test_non_mouse_press_is_ignored(gestures):
    gestures.press(_drag("LEFT", "alt"))
    assert not gestures.active
