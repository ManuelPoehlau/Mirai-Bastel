"""AD-027 §6 E1, lifecycle C1: the interaction scenarios as readable regression tests.

V1-V7 (the precedence facts of AD-027 §1.1) and Manu's test points (Knife, W/E/R with a constraint and the
modifiers, Box / Paint / Lasso, the gizmo, the Working Pivot, the morph view, Undo/Redo chains, object gestures with
a mirror pair, Re-Symmetrize, hidden geometry), driven through the public entry points by
`tests/interaction_trace.py` (one event per call, the window's frame tick after each). Each step asserts what matters
for that scenario; the values were recorded on the baseline `dfd6e5d` and held through the restructuring (E1, E2).
An intended behaviour change later edits the expectation here - there is no digest corpus to re-record.
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401
from mirai.interaction import commands
from tests.interaction_trace import (
    ALT_M, C, CTRL_SHIFT_Z, CTRL_Y, CTRL_Z, E, ENTER, ESC, L, N, P, Q, R, T, TAB, W, X, Driver, centre_face, first,
    hold_move, key, select_vertex,
)

#: The scripted scenarios run with this driver; E5 (iv) swaps in one that checks `can_run` at every step.
make_driver = Driver


def _history(app) -> tuple[int, bool]:
    """(Undo depth, a Redo is possible)."""
    return len(app.history), app.history.can_redo()


def _counts(app) -> tuple[int, int, int, int]:
    s = app.selection
    return len(s.vertices), len(s.edges), len(s.faces), len(s.objects)


# -- V1-V7: the precedence among interactions is fixed by kind, not by start order (AD-027 §1.1) ----------------


def test_v1_a_held_pivot_takes_esc_and_move_stays_armed() -> None:
    d = make_driver("subd_sym")
    app = d.app
    select_vertex(d, 2)
    assert d.key_down(P) and app.pivot_placing
    assert d.key_down(W) and app.interaction_owner == "transform" and app.transform_command == commands.MOVE
    assert d.key_down(ESC)
    assert app.status_message == "Working Pivot: placement cancelled"
    assert not app.pivot_placing and app.transform_command == commands.MOVE and not app.transform_interacting
    d.key_up("ESCAPE")
    d.nudge(10, 0)
    assert app.transform_interacting
    assert d.key_up("w") and app.status_message == "Move committed" and app.interaction_owner is None
    assert _history(app) == (2, False)
    d.key_up("p")
    assert app.working_pivot is None


def test_v2_p_under_an_armed_move_is_refused_silently() -> None:
    d = make_driver("subd_sym")
    app = d.app
    select_vertex(d, 2)
    assert d.key_down(W) and app.transform_command == commands.MOVE
    status = app.status_message
    assert d.key_down(P) is False
    assert not app.pivot_placing and app.status_message == status
    d.key_up("p")
    assert d.key_up("w") and app.status_message == "Move: tool set (no motion, nothing moved)"
    assert _history(app) == (1, False)


def test_v3_a_held_pivot_takes_the_click_while_move_stays_armed() -> None:
    d = make_driver("subd_sym")
    app = d.app
    select_vertex(d, 2)
    d.key_down(P)
    d.key_down(W)
    d.click(*centre_face(d))
    assert app.status_message == "Working Pivot placed - E / R turn and scale around it"
    assert app.working_pivot is not None and app.active_pivot is not None
    assert app.transform_command == commands.MOVE and app.pivot_placing
    assert d.key_up("w") and app.status_message == "Move committed"
    assert _history(app) == (2, False)
    assert d.key_up("p") and not app.pivot_placing and app.active_pivot is not None


def test_v4_the_light_beats_the_morph_weight_in_either_order() -> None:
    d = make_driver("morph")
    app = d.app
    assert app.morph_weight == 60
    assert d.key_down(L) and d.key_down(N)
    d.nudge(30, 5)
    assert app.status_message == "Light: Key Azimut -30.0° · Höhe +37.5°" and app.morph_weight == 60
    assert d.key_up("l") and app.status_message == "Light: Raitt 2:1 angepasst · Kamera"
    assert d.key_up("n") and app.status_message == "Morph: Target 2 · 0 % · base · 2/2"  # a tap of N: A/B
    d.key_down(N)
    d.key_down(L)
    d.nudge(-30, -5)
    assert app.status_message == "Light: Key Azimut -45.0° · Höhe +35.0°" and app.morph_weight == 0
    assert d.key_up("n") and app.status_message == "Morph: Target 2 · 60 % · base · 2/2"
    assert d.key_up("l") and app.status_message == "Light: Raitt 2:1 · Kamera"
    assert _history(app) == (2, False)


def test_v5_motion_drives_move_under_a_held_light_then_turns_the_light_again() -> None:
    d = make_driver("subd_sym")
    app = d.app
    select_vertex(d, 2)
    rig = app.display.light_rig
    d.key_down(L)
    d.key_down(W)
    d.nudge(15, 0)
    assert app.transform_interacting and app.display.light_rig == rig
    assert d.key_up("w") and app.status_message == "Move committed"
    d.nudge(15, 0)
    assert app.status_message == "Light: Key Azimut -37.5° · Höhe +35.0°"
    assert d.key_up("l") and app.status_message == "Light: Raitt 2:1 angepasst · Kamera"
    assert _history(app) == (2, False)


def test_v6_the_knife_takes_the_click_and_esc_while_p_stays_held() -> None:
    d = make_driver("cube")
    app = d.app
    d.key_down(P)
    d.tap(C)
    assert app.knife_active and app.interaction_owner == "knife" and app.pivot_placing
    d.click(*first(d.targets("edge", visible=True, limit=8)))
    assert app.status_message == "Knife: start point set" and app.working_pivot is None
    assert d.key_down(ESC) and app.status_message == "Knife cancelled"
    assert not app.knife_active and app.pivot_placing
    d.key_up("ESCAPE")
    assert d.key_up("p")
    assert app.status_message == "Working Pivot: none on this object - hold P and click to place one"
    assert _history(app) == (0, False)


def test_v7_a_held_pivot_takes_the_click_under_the_open_preview_and_esc_closes_the_preview() -> None:
    d = make_driver("basemesh")
    app = d.app
    select_vertex(d, 1)
    d.key_down(P)
    d.tap(ALT_M)
    assert app.interaction_owner == "resymmetrize" and app.resymmetrize_preview is not None and app.pivot_placing
    d.click(*centre_face(d))
    assert app.status_message == "Working Pivot placed on the symmetry plane - E / R turn and scale around it"
    assert app.interaction_owner == "resymmetrize" and app.active_pivot is not None
    assert d.key_down(ESC) and app.status_message == "Re-Symmetrize abgebrochen"
    assert app.resymmetrize_preview is None and app.pivot_placing
    d.key_up("ESCAPE")
    assert d.key_up("p") and not app.pivot_placing and app.active_pivot is not None
    assert _history(app) == (1, False)


# -- the test points --------------------------------------------------------------------------------------


def _knife_session(d: Driver, mirror: str = "") -> None:
    """Cut across faces, pen lift, a new start, in-session Undo / Redo, a double-click; the session history stays
    out of the app's until the commit."""
    app = d.app
    undo = _history(app)
    d.tap(C)
    assert app.knife_active and app.interaction_owner == "knife"
    edges = d.targets("edge", visible=True, limit=8)
    assert d.click(*edges[0]) and app.status_message == f"Knife: start point set{mirror}"
    d.click(*edges[1])
    assert app.status_message == f"Knife: cut (1 path segment){mirror}"
    d.click(*edges[2])
    assert app.status_message.startswith("Knife: cut across ")
    d.tap(key("e"))
    assert app.status_message == f"Knife: pen lifted - the next click starts a new cut{mirror}"
    d.click(*edges[3 % len(edges)])
    assert app.status_message == f"Knife: start point set{mirror}"
    d.tap(CTRL_Z)
    assert app.status_message == f"Knife: last cut undone{mirror}" and _history(app) == undo
    d.tap(CTRL_SHIFT_Z)
    assert app.status_message == f"Knife: cut redone{mirror}" and _history(app) == undo
    d.click(*edges[4 % len(edges)])
    d.tick(0.1)
    d.click(*edges[4 % len(edges)])  # double-click: close (needs three points) + lift
    assert app.status_message.startswith("Knife: pen lifted (not closed: closing needs at least 3 points)")
    assert app.knife_active and _history(app) == undo


def test_knife_session_commits_one_entry_and_a_second_session_cancels() -> None:
    d = make_driver("cube")
    app = d.app
    _knife_session(d)
    assert d.key_down(ENTER) and app.status_message == "Knife committed (4 path edges selected)"
    d.key_up("enter")
    assert not app.knife_active and _history(app) == (1, False)
    assert app.selection.mode.name == "EDGE" and _counts(app) == (0, 4, 0, 0)
    d.tap(C)  # four path edges selected: C connects them (Edge Connect), it starts no Knife
    assert app.status_message == "Connect Edges" and not app.knife_active and _history(app) == (2, False)
    d.click(*first(d.targets("edge", visible=True, limit=8)))
    d.tap(ESC)
    d.tap(CTRL_Z)
    assert app.status_message == "Undo" and _history(app) == (1, True) and _counts(app) == (0, 4, 0, 0)


def test_knife_session_under_symmetry() -> None:
    d = make_driver("subd_sym")
    app = d.app
    _knife_session(d, mirror=" [Spiegel V-b]")
    assert d.key_down(ENTER) and app.status_message == "Knife committed (6 path edges selected)"
    d.key_up("enter")
    assert _history(app) == (2, False) and _counts(app) == (0, 6, 0, 0)
    d.tap(C)
    assert app.status_message == "Keine verbindbaren Kanten: ausgewählte Kanten teilen sich keine Face."
    d.click(*first(d.targets("edge", visible=True, limit=8)))
    d.tap(ESC)
    d.tap(CTRL_Z)
    assert app.status_message == "Undo" and _history(app) == (1, True) and app.selection.mode.name == "VERTEX"


def test_wer_with_a_one_shot_constraint_ctrl_snap_shift_fine_and_alt_orbit() -> None:
    d = make_driver("subd_sym")
    app = d.app
    select_vertex(d, 0)
    d.tap(X)
    assert app.axis_constraint == "x" and app.status_message == "Constraint: X (one-shot)"
    d.key_down(W)
    assert app.status_message == "Move: 1 vertex (constraint X) - Tweak: move the mouse, release W to commit"
    d.nudge(12, 0)
    assert app.transform_interacting and app.transform_space == "x"
    d.nudge(12, 4)
    d.nudge(6, -3)
    assert d.key_up("w") and app.status_message == "Move committed (constraint X) · free again (one-shot)"
    assert app.axis_constraint is None and _history(app) == (2, False)
    d.key_down(E)  # Rotate, Ctrl = snap: the dial snaps back to no change
    assert app.tweak_command == commands.ROTATE
    d.set_modifier("ctrl", True)
    d.nudge(25, 10)
    assert app.transform_interacting and app.transform_command == commands.ROTATE
    d.set_modifier("ctrl", False)
    assert d.key_up("e") and app.status_message == "Rotate: no change"
    d.key_down(R)  # Scale: Shift fine, then Alt borrows the motion for the camera
    camera = d.app.camera.yaw
    d.set_modifier("shift", True)
    d.nudge(20, 0)
    d.set_modifier("shift", False)
    d.set_modifier("alt", True)
    d.nudge(20, 0)
    assert app.camera.yaw != camera and app.transform_command == commands.SCALE
    d.set_modifier("alt", False)
    d.nudge(5, 0)
    assert d.key_up("r") and app.status_message == "Scale: no change" and _history(app) == (2, False)
    d.key_down(W)
    d.nudge(9, 0)
    assert d.key_down(ESC) and app.status_message == "Move cancelled" and app.interaction_owner is None
    d.key_up("ESCAPE")
    d.key_up("w")
    d.tap(CTRL_Z)
    assert app.status_message == "Undo" and _history(app) == (1, True)
    d.tap(CTRL_Y)
    assert app.status_message == "Redo" and _history(app) == (2, False)


def test_box_paint_and_lasso_select_and_esc_cancels_a_box() -> None:
    d = make_driver("subd_sym")
    app = d.app
    d.motion(5, 5)
    d.press()
    for step in range(4):
        d.motion(5 + 100 * (step + 1), 5 + 80 * (step + 1))
    assert app.selection_box is not None and app.interaction_owner is None
    assert d.release() and app.status_message == "Box: 5 vertices selected" and _counts(app) == (5, 0, 0, 0)
    face = centre_face(d)
    d.motion(*face)
    d.press(modifiers=("shift",))
    d.motion(face[0] + 30, face[1] + 10)
    d.motion(face[0] + 60, face[1] + 5)
    assert d.release() and app.status_message == "Paint: 5 vertices selected"
    assert d.key_down(Q) and app.status_message == "Lasso: drag with LMB (Shift adds, Esc cancels)"
    d.motion(100, 100)
    d.press()
    for x, y in ((700, 120), (680, 520), (120, 500)):
        d.motion(x, y)
    assert app.selection_lasso is not None and not app.selection_through
    d.set_modifier("alt", True)
    assert app.selection_through
    assert d.release() and app.status_message == "Lasso (through): 22 vertices selected"
    d.set_modifier("alt", False)
    assert d.key_up("q") and app.status_message == "Lasso off"
    d.motion(5, 5)
    d.press()
    d.motion(300, 300)
    assert d.key_down(ESC) and app.status_message == "Box cancelled" and app.selection_box is None
    d.key_up("ESCAPE")
    assert d.release() is False and _counts(app) == (22, 0, 0, 0) and _history(app) == (1, False)


def test_gizmo_click_sets_the_constraint_a_drag_moves_and_esc_cancels() -> None:
    d = make_driver("subd_sym")
    app = d.app
    select_vertex(d, 4)
    d.tap(W)
    assert app.status_message == "Move: tool set (no motion, nothing moved)" and app.gizmo_items()
    points = d.targets("vertex", visible=True, limit=8)
    centre = points[4 % len(points)]
    d.click(*centre)  # the centre handle: no constraint
    assert app.status_message == "Constraint: none" and app.interaction_owner is None
    d.motion(*centre)
    d.press()
    d.motion(centre[0] + 20, centre[1])
    assert app.interaction_owner == "transform" and app.transform_interacting and not app.tweak_running
    assert app.status_message == "Move: 1 vertex - move the mouse, release the mouse button to commit"
    assert app.gizmo_items() == []  # hidden while the gesture runs
    d.motion(centre[0] + 40, centre[1] + 5)
    assert d.release() and app.status_message == "Move committed" and _history(app) == (2, False)
    d.motion(*centre)
    d.press()
    assert app.axis_constraint == "xz" and app.status_message == "Constraint: XZ plane (one-shot)"
    d.motion(centre[0] - 20, centre[1])
    assert app.status_message.startswith("Move: 1 vertex (constraint XZ plane)")
    assert d.key_down(ESC) and app.status_message == "Move cancelled"
    assert app.axis_constraint is None  # E2: Esc keeps what was pending before the press
    d.key_up("ESCAPE")
    assert d.release() is False and _history(app) == (2, False)
    d.motion(*centre_face(d))


def test_working_pivot_place_tap_off_on_esc_restores_and_rotate_turns_around_it() -> None:
    d = make_driver("subd_sym")
    app = d.app
    assert d.key_down(P) and app.pivot_placing
    d.click(*centre_face(d))
    assert app.status_message == "Working Pivot placed - E / R turn and scale around it"
    placed = app.working_pivot
    assert d.key_up("p") and app.active_pivot is not None
    d.tap(P)
    assert app.status_message == "Working Pivot off - E / R use the selection centre" and app.active_pivot is None
    d.tap(P)
    assert app.status_message == "Working Pivot on - E / R turn and scale around it" and app.active_pivot is not None
    d.key_down(P)
    d.click(*first(d.targets("vertex", visible=True, limit=8)), modifiers=("shift",))
    assert app.status_message == "Working Pivot placed - E / R turn and scale around it"
    assert app.working_pivot != placed
    assert d.key_down(ESC) and app.status_message == "Working Pivot: placement cancelled"
    assert app.working_pivot == placed and not app.pivot_placing
    d.key_up("ESCAPE")
    d.key_up("p")
    select_vertex(d, 3)
    d.key_down(E)
    assert app.status_message == (
        "Rotate: 1 vertex around the Working Pivot - Tweak: move the mouse, release E to commit"
    )
    for dx, dy in ((12, 0), (12, 4), (6, -3)):
        d.nudge(dx, dy)
    assert d.key_up("e") and app.status_message == "Rotate committed" and _history(app) == (2, False)


def test_morph_view_tab_w_n_drag_undo_and_back() -> None:
    d = make_driver("morph")
    app = d.app
    d.tap(TAB)
    assert app.morph_view_open and app.status_message.startswith("Editing morph target 'Target 2' beside the base")
    select_vertex(d, 2)
    hold_move(d, W)
    assert app.status_message == "Move committed" and _history(app) == (3, False)
    assert d.key_down(N) and app.status_message == "Morph: move the mouse left/right for the weight (60 %), release N"
    d.nudge(40, 0)
    assert app.morph_weight == 73 and app.interaction_owner is None
    d.key_up("n")
    d.tap(N)  # a tap: A/B
    assert app.status_message == "Morph: Target 2 · 0 % · editing target (beside the base) · 2/2"
    d.tap(CTRL_Z)
    assert app.status_message == "Undo" and _history(app) == (2, True) and app.morph_view_open
    d.tap(TAB)
    assert not app.morph_view_open and app.status_message == "Base 'SubD_Cube' (target 'Target 2' at 0 %)"
    d.tap(CTRL_Z)
    assert _history(app) == (1, True)
    d.tap(CTRL_Y)
    assert app.status_message == "Redo" and _history(app) == (2, True)


def test_undo_redo_chain_across_move_extrude_and_selection() -> None:
    d = make_driver("cube")
    app = d.app
    select_vertex(d, 1)
    hold_move(d, W)
    assert app.status_message == "Move committed" and _history(app) == (1, False)
    d.tap(key("3"))
    d.click(*centre_face(d))
    assert _counts(app) == (0, 0, 1, 0)
    assert d.key_down(T) and app.status_message == "Extrude: 1 face - move the mouse, release T to commit"
    for _ in range(3):
        d.nudge(4, -6)
    assert app.transform_interacting
    assert d.key_up("t") and app.status_message == "Extrude committed" and _history(app) == (2, False)
    d.tap(key("1"))
    select_vertex(d, 0)
    select_vertex(d, 5)
    d.tap(CTRL_Z)
    assert app.status_message == "Undo" and _history(app) == (1, True)
    assert app.selection.mode.name == "FACE" and _counts(app) == (0, 0, 1, 0)  # the selection of the step comes back
    d.tap(CTRL_Z)
    assert _history(app) == (0, True) and app.selection.mode.name == "VERTEX" and _counts(app) == (1, 0, 0, 0)
    d.tap(CTRL_Z)
    assert app.status_message == "Undo: nothing to undo"
    d.tap(CTRL_Y)
    assert app.status_message == "Redo" and _history(app) == (1, True)
    d.tap(CTRL_Y)
    assert _history(app) == (2, False) and app.selection.mode.name == "FACE"


def test_object_gestures_in_mode_4_with_a_mirror_pair() -> None:
    d = make_driver("objects")
    app = d.app
    d.tap(key("4"))
    assert app.status_message == "Mode: Object"
    points = d.object_points()
    d.click(*points[1 % len(points)])
    assert app.status_message == "Object 'cube' selected (being edited)"
    cube = app.scene.edit_object
    start = cube.transform
    assert d.key_down(W) and app.status_message == "Object Move: 'cube' - Tweak: move the mouse, release W to commit"
    assert app.interaction_owner == "transform"
    d.nudge(15, 0)
    d.nudge(10, 5)
    assert cube.transform != start
    assert d.key_up("w") and app.status_message == "Object 'cube': moved (object level)" and _history(app) == (4, False)
    hold_move(d, E, steps=((15, 0), (10, 5)))
    assert app.status_message == "Object 'cube': rotated (object level)" and _history(app) == (5, False)
    moved = cube.transform
    d.key_down(R)
    d.nudge(10, 0)
    assert cube.transform != moved
    assert d.key_down(ESC) and app.status_message == "Object Scale cancelled" and cube.transform is moved
    d.key_up("ESCAPE")
    d.key_up("r")
    d.tap(CTRL_Z)
    assert app.status_message == "Undo" and _history(app) == (4, True)
    d.tap(key("1"))
    assert app.status_message == "Mode: Vertex · editing 'cube' · object 'cube' is placed (object level)"


def test_resymmetrize_preview_refuses_keys_lets_display_through_closes_and_executes() -> None:
    d = make_driver("basemesh")
    app = d.app
    select_vertex(d, 1)
    d.tap(ALT_M)
    assert app.interaction_owner == "resymmetrize" and app.status_message.startswith("Re-Symmetrize Quelle")
    assert d.key_down(W) is False and app.status_message.startswith("Vorschau aktiv — Befehl ignoriert")
    d.key_up("w")
    d.click(*centre_face(d))
    d.scroll("UP", ("shift",))
    assert app.interaction_owner == "resymmetrize" and _counts(app) == (1, 0, 0, 0)
    d.tap(key("d"))
    assert app.status_message == "Display: Flat Shaded" and app.interaction_owner == "resymmetrize"
    d.tap(ESC)
    assert app.status_message == "Re-Symmetrize abgebrochen" and app.resymmetrize_preview is None
    select_vertex(d, 1)
    d.tap(ALT_M)
    d.tap(ALT_M)
    assert app.status_message == "Re-Symmetrize ausgeführt: 27 Änderungen" and _history(app) == (2, False)
    d.tap(CTRL_Z)
    assert app.status_message == "Undo" and _history(app) == (1, True)


def test_hidden_and_masked_geometry_refuse_and_the_undo_redo_chain_runs_out() -> None:
    """The Undo/Redo chain's steps on a mesh with hidden and masked parts: the hidden vertex is not picked, the
    Extrude next to hidden geometry is refused, and Undo / Redo run out visibly."""
    d = make_driver("hidden")
    app = d.app
    select_vertex(d, 1)  # hidden: the click selects nothing
    assert _counts(app) == (0, 0, 0, 0)
    assert d.key_down(W) is False and app.status_message == "Move: nothing to move (select or hover a vertex)"
    for dx, dy in ((12, 0), (12, 4), (6, -3)):
        d.nudge(dx, dy)
    d.key_up("w")
    d.tap(key("3"))
    d.click(*centre_face(d))
    assert _counts(app) == (0, 0, 1, 0)
    assert d.key_down(T) is False
    assert app.status_message == "Topology edit: hidden geometry in the way (Alt+H shows all)"
    assert app.interaction_owner is None
    for _ in range(3):
        d.nudge(4, -6)
    d.key_up("t")
    d.tap(key("1"))
    select_vertex(d, 0)
    select_vertex(d, 5)
    assert _counts(app) == (1, 0, 0, 0) and _history(app) == (1, False)
    d.tap(CTRL_Z)
    assert app.status_message == "Undo" and _history(app) == (0, True)
    d.tap(CTRL_Z)
    assert app.status_message == "Undo: nothing to undo"
    d.tap(CTRL_Z)
    d.tap(CTRL_Y)
    assert app.status_message == "Redo" and _history(app) == (1, False)
    d.tap(CTRL_Y)
    assert app.status_message == "Redo: nothing to redo"
