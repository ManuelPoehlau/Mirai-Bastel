"""The visible table resolves every documented gesture; it equals the README table 1:1; the
reserved keys Q W E R (AD-016) and C (AD-017) are never bound; the Artist-Truth inputs are
present (navigation, X/Y/Z, Ctrl+Z/Ctrl+Y)."""

from __future__ import annotations

from pathlib import Path

from mehlsack_lab import lab_bindings as lb

NONE = frozenset()
README = Path(lb.__file__).parent / "README.md"
CREATE, EDIT = lb.PHASE_CREATE, lb.PHASE_EDIT


def test_drags():
    for phase in (CREATE, EDIT):
        assert lb.resolve_drag(phase, {"LEFT"}, {"alt"}) == lb.ORBIT
        assert lb.resolve_drag(phase, {"LEFT"}, {"alt", "shift"}) == lb.PAN
        assert lb.resolve_drag(phase, {"RIGHT"}, NONE) == lb.ORBIT
        assert lb.resolve_drag(phase, {"MIDDLE"}, NONE) == lb.PAN
    assert lb.resolve_drag(EDIT, {"LEFT"}, NONE) == lb.DRAG_TARGET
    assert lb.resolve_drag(CREATE, {"LEFT"}, NONE) is None
    assert lb.resolve_drag(EDIT, {"LEFT"}, {"shift"}) is None
    assert lb.resolve_drag(EDIT, {"LEFT"}, {"capslock"}) == lb.DRAG_TARGET


def test_panel_takes_lmb_and_never_reaches_the_mesh():
    assert lb.resolve_drag(EDIT, {"LEFT"}, NONE, in_panel=True) == lb.CURVE_POINT
    # Slice 2a E12: Alt+LMB in the panel breaks a handle (no orbit there); Alt+Shift still pans
    assert lb.resolve_drag(EDIT, {"LEFT"}, {"alt"}, in_panel=True) == lb.CURVE_BREAK
    assert lb.resolve_drag(EDIT, {"LEFT"}, {"alt"}, in_panel=False) == lb.ORBIT
    assert lb.resolve_drag(EDIT, {"LEFT"}, {"alt", "shift"}, in_panel=True) == lb.PAN
    assert lb.resolve_drag(EDIT, {"LEFT"}, {"shift"}, in_panel=True) is None
    assert lb.resolve_drag(CREATE, {"LEFT"}, NONE, in_panel=True) is None
    assert lb.resolve_double_click(EDIT, NONE, in_panel=True) == lb.CURVE_RESET
    assert lb.resolve_double_click(EDIT, NONE, in_panel=False) is None
    assert lb.resolve_double_click(EDIT, {"alt"}, in_panel=True) is None
    assert lb.resolve_double_click(CREATE, NONE, in_panel=True) is None
    assert lb.resolve_press_during_drag(EDIT, "RIGHT") == lb.CANCEL_PRESS
    assert lb.resolve_press_during_drag(EDIT, "MIDDLE") is None


def test_wheel_per_phase():
    assert lb.resolve_wheel(CREATE, NONE) == lb.BOX_HEIGHT
    assert lb.resolve_wheel(CREATE, {"alt"}) == lb.BOX_WIDTH
    assert lb.resolve_wheel(CREATE, {"alt", "shift"}) == lb.BOX_DEPTH  # Slice 2a A5
    assert lb.resolve_wheel(EDIT, {"alt", "shift"}) is None
    assert lb.resolve_wheel(CREATE, {"shift"}) == lb.BOX_LOOPS
    assert lb.resolve_wheel(CREATE, {"ctrl"}) == lb.BOX_AROUND
    assert lb.resolve_wheel(EDIT, NONE) == lb.ZOOM
    assert lb.resolve_wheel(EDIT, {"shift"}) == lb.RADIUS
    assert lb.resolve_wheel(EDIT, {"ctrl"}) is None and lb.resolve_wheel(EDIT, {"alt"}) is None


def test_keys():
    edit = {
        ("TAB", NONE): lb.TOGGLE_MODE, ("X", NONE): lb.AXIS_X, ("Y", NONE): lb.AXIS_Y,
        ("Z", NONE): lb.AXIS_Z, ("O", frozenset({"ctrl"})): lb.METRIC,
        ("O", frozenset({"alt"})): lb.BANDS, ("P", NONE): lb.PREVIEW, ("N", NONE): lb.NACHFUEHREN,
        ("K", NONE): lb.PRESET_1, ("K", frozenset({"shift"})): lb.PRESET_2,
        ("Z", frozenset({"ctrl"})): lb.UNDO, ("Y", frozenset({"ctrl"})): lb.REDO,
        ("B", NONE): lb.NEW_BOX, ("H", NONE): lb.HELP, ("ESCAPE", NONE): lb.ESCAPE,
        # Slice 2b: hold W/E/R, exclude-axis planes (B4.1, Artist Input Truth), formula
        ("W", NONE): lb.HOLD_MOVE, ("E", NONE): lb.HOLD_ROTATE, ("R", NONE): lb.HOLD_SCALE,
        ("X", frozenset({"shift"})): lb.PLANE_YZ, ("Y", frozenset({"shift"})): lb.PLANE_XZ,
        ("Z", frozenset({"shift"})): lb.PLANE_XY, ("M", NONE): lb.SCALE_FORMULA,
    }
    for (name, mods), action in edit.items():
        assert lb.resolve_key(EDIT, name, mods) == action, name
    assert lb.resolve_key(CREATE, "RETURN", NONE) == lb.COMMIT_BOX
    assert lb.resolve_key(CREATE, "ENTER", NONE) == lb.COMMIT_BOX
    assert lb.resolve_key(EDIT, "RETURN", NONE) is None
    assert lb.resolve_key(CREATE, "H", NONE) == lb.HELP
    assert lb.resolve_key(CREATE, "P", NONE) is None
    assert lb.resolve_key(CREATE, "R", NONE) is None
    # a release ends the hold whatever modifiers are held by then
    assert lb.resolve_hold_release(EDIT, "R") == lb.HOLD_SCALE and lb.resolve_hold_release(EDIT, "X") is None
    assert {b.gesture() for b in lb.LAB_OVERRIDES if b.kind == "hold"} == {"W halten", "E halten", "R halten"}


def test_artist_truth_inputs_present():
    rows = {(b.gesture(), b.note) for b in lb.LAB_OVERRIDES}
    for gesture in ("Alt+LMB ziehen", "Alt+Shift+LMB ziehen", "Mausrad", "X", "Y", "Z", "Ctrl+Z", "Ctrl+Y",
                    "Shift+X", "Shift+Y", "Shift+Z"):
        assert (gesture, "Artist Input Truth") in rows, gesture


def test_reserved_keys_are_never_bound():
    assert lb.RESERVED_KEYS == {"Q", "C"}  # W/E/R bound since Slice 2b, with their AD-016 meaning
    bound = {b.value for b in lb.LAB_OVERRIDES if b.kind in ("key", "hold")}
    assert not (bound & lb.RESERVED_KEYS)
    for phase in (CREATE, EDIT):
        for name in lb.RESERVED_KEYS:
            for mods in (NONE, frozenset({"shift"}), frozenset({"ctrl"}), frozenset({"alt"})):
                assert lb.resolve_key(phase, name, mods) is None


def test_no_two_bindings_share_a_gesture_in_one_phase():
    seen = {}
    for b in lb.LAB_OVERRIDES:
        phases = (CREATE, EDIT) if b.phase is None else (b.phase,)
        for phase in phases:
            key = (b.gesture(), phase)
            assert key not in seen, key
            seen[key] = b


def test_readme_mirrors_table_1_to_1():
    text = README.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| ") and line.count("|") == 5]
    expected = {f"| {b.gesture()} | {lb.PHASE_LABELS[b.phase]} | {b.label} | {b.note} |" for b in lb.LAB_OVERRIDES}
    assert expected <= set(rows), sorted(expected - set(rows))
    control_rows = [r for r in rows if r in expected]
    assert len(control_rows) == len(lb.LAB_OVERRIDES)


def test_printed_table_has_every_binding():
    lines = lb.overrides_table()
    assert len(lines) == len(lb.LAB_OVERRIDES)
    assert all(b.label in line for b, line in zip(lb.LAB_OVERRIDES, lines))
