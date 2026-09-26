"""E13: the visible table resolves every documented gesture, and nothing else."""

from __future__ import annotations

from pathlib import Path

from viewport_shading_lab import lab_bindings as lb

NONE = frozenset()


def test_mouse_drags():
    assert lb.resolve_drag(frozenset({"LEFT"}), frozenset({"alt"})) == lb.ORBIT
    assert lb.resolve_drag(frozenset({"LEFT"}), frozenset({"shift"})) == lb.PAN
    assert lb.resolve_drag(frozenset({"LEFT"}), NONE) == lb.DRAG_LIGHT
    assert lb.resolve_drag(frozenset({"RIGHT"}), NONE) == lb.ORBIT
    assert lb.resolve_drag(frozenset({"MIDDLE"}), NONE) == lb.PAN
    assert lb.resolve_drag(frozenset({"LEFT"}), frozenset({"ctrl"})) is None


def test_lock_modifiers_do_not_block_light_drag():
    # Caps/Num Lock are not in KNOWN_MODIFIERS and never reach the resolver as names,
    # but an unknown name must not break exact matching either.
    assert lb.resolve_drag(frozenset({"LEFT"}), frozenset({"capslock"})) == lb.DRAG_LIGHT


def test_keys():
    expected = {
        "UP": lb.ROW_PREV, "DOWN": lb.ROW_NEXT, "LEFT": lb.VALUE_DEC, "RIGHT": lb.VALUE_INC,
        "F1": lb.PRESET_1, "F2": lb.PRESET_2, "F3": lb.PRESET_3, "F4": lb.PRESET_4,
        "B": lb.TOGGLE_AB, "H": lb.TOGGLE_HUD, "P": lb.CAPTURE, "ESCAPE": lb.QUIT,
    }
    for name, action in expected.items():
        assert lb.resolve_key(name, NONE) == action, name
    assert lb.resolve_key("RIGHT", frozenset({"shift"})) == lb.VALUE_INC
    assert lb.resolve_key("Q", NONE) is None  # Artist Truth: Q = move


def test_wheel_zoom():
    assert lb.resolve_scroll(NONE) == lb.ZOOM


def test_readme_mirrors_table():
    readme = (Path(lb.__file__).parent / "README.md").read_text(encoding="utf-8")
    for binding in lb.LAB_OVERRIDES:
        row = f"| {binding.gesture()} | {binding.label} | {binding.note} |"
        assert row in readme, row
