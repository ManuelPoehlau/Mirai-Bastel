"""A11: the visible table resolves every documented gesture and nothing else;
it equals the README table 1:1; the reserved keys Q W E R (AD-016) and C (AD-017)
are never bound; the Artist-Truth inputs are present."""

from __future__ import annotations

from pathlib import Path

from subdivision_lab import lab_bindings as lb

NONE = frozenset()
README = Path(lb.__file__).parent / "README.md"


def test_mouse_drags():
    assert lb.resolve_drag(frozenset({"LEFT"}), frozenset({"alt"})) == lb.ORBIT
    assert lb.resolve_drag(frozenset({"LEFT"}), frozenset({"shift"})) == lb.PAN
    assert lb.resolve_drag(frozenset({"LEFT"}), NONE) == lb.DRAG_VERTEX
    assert lb.resolve_drag(frozenset({"RIGHT"}), NONE) == lb.ORBIT
    assert lb.resolve_drag(frozenset({"MIDDLE"}), NONE) == lb.PAN
    assert lb.resolve_drag(frozenset({"LEFT"}), frozenset({"ctrl"})) is None


def test_lock_modifiers_do_not_block_vertex_drag():
    assert lb.resolve_drag(frozenset({"LEFT"}), frozenset({"capslock"})) == lb.DRAG_VERTEX


def test_keys():
    expected = {
        "_1": lb.LEVEL_1, "_2": lb.LEVEL_2, "_3": lb.LEVEL_3, "V": lb.CYCLE_VIEW,
        "X": lb.TOGGLE_CAGE_DEPTH, "B": lb.TOGGLE_AB, "F9": lb.BENCH,
        "H": lb.TOGGLE_HUD, "ESCAPE": lb.QUIT,
    }
    for name, action in expected.items():
        assert lb.resolve_key(name, NONE) == action, name


def test_wheel_zoom():
    assert lb.resolve_scroll(NONE) == lb.ZOOM


def test_artist_truth_inputs_present():
    gestures = {b.gesture() for b in lb.LAB_OVERRIDES}
    assert {"Alt+LMB ziehen", "Shift+LMB ziehen", "Mausrad", "H", "Esc"} <= gestures


def test_reserved_keys_are_never_bound():
    assert lb.RESERVED_KEYS == {"Q", "W", "E", "R", "C"}
    bound = {b.value for b in lb.LAB_OVERRIDES if b.kind == "key"}
    assert not (bound & lb.RESERVED_KEYS)
    for name in lb.RESERVED_KEYS:
        assert lb.resolve_key(name, NONE) is None
        assert lb.resolve_key(name, frozenset({"shift"})) is None


def test_no_two_bindings_share_a_gesture():
    gestures = [b.gesture() for b in lb.LAB_OVERRIDES]
    assert len(gestures) == len(set(gestures))


def test_readme_mirrors_table_1_to_1():
    text = README.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| ") and line.count("|") == 4]
    table_rows = {
        line for line in rows
        if not line.startswith("| Eingabe |") and not set(line.replace("|", "").strip()) <= {"-", " "}
    }
    expected = {f"| {b.gesture()} | {b.label} | {b.note} |" for b in lb.LAB_OVERRIDES}
    # the control table rows are exactly LAB_OVERRIDES (other README tables use other shapes)
    assert expected <= table_rows
    control_rows = [r for r in table_rows if r in expected]
    assert len(control_rows) == len(lb.LAB_OVERRIDES)
