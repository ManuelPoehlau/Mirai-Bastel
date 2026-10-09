"""Application: Extrude on `T` (WP-06 B9), headless (TraceStore), no pyglet/window.

Same AD-016 hold-key-hover path as Move/Rotate/Scale (`test_application_transform.py`):
`key_press` arms (tool active, nothing begun) -> `pointer_motion(x, y, dx, dy)` ->
release commits. Differences pinned here: Face mode only, target = faces (selection,
else the hovered face), `begin()` mutates the topology so it waits for EXTRUDE_BEGIN_PX
of net pointer displacement, a zero extrusion at release is a cancel, and the Undo
mirror entry holds the selection from BEFORE `begin()`.

The key `T` and the hold activation are PROVISIONAL (engineering proposal, not an Artist
decision) - nothing here claims Artist validation.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import EdgeId, FaceId, SelectionMode, VertexId
from mirai.application import (
    EXTRUDE_BEGIN_PX,
    EXTRUDE_MIN_DISTANCE,
    Application,
    CommandGate,
)
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.interaction.tool import ToolState
from mirai.topology.extrude import ExtrudeTool, _compute_face_normal

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


T, W = _key("t"), _key("w")
ESC = _key("ESCAPE")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")
K1, K2, K3 = _key("1"), _key("2"), _key("3")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.key_press(K3)  # Face mode
    return app


def _state(app) -> dict:
    """`export_state()` without the monotonic ID counters (AD-001: only run forward)."""
    return {k: v for k, v in app.scene.mesh.export_state().items() if not k.endswith("_id_counter")}


def _faces(app) -> list[FaceId]:
    return sorted(app.scene.mesh.all_face_ids())


def _counts(app) -> tuple[int, int, int]:
    mesh = app.scene.mesh
    return len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())


def _select(app, *faces) -> None:
    app.selection.mode = SelectionMode.FACE
    app.selection.set(set(faces))


def _drag(app, dx: float = 30.0, dy: float = 0.0, steps: int = 4) -> None:
    x, y = app._cursor or (400.0, 300.0)
    for _ in range(steps):
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, dx, dy)


def _extrude(app, face=None, **drag) -> FaceId:
    """Select `face` (default the first), hold T, drag, release T."""
    face = face if face is not None else _faces(app)[0]
    _select(app, face)
    assert app.key_press(T)
    _drag(app, **drag)
    assert app.key_release(T)
    return face


def _visible_face(app) -> tuple[FaceId, float, float]:
    """A face the (occlusion-aware) pick returns at its own projected center."""
    mesh = app.scene.mesh
    for fid in _faces(app):
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
        c = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
        x, y = app.camera.project_to_screen(c, WIDTH, HEIGHT)
        if app._pick(x, y) == fid:
            return fid, x, y
    raise AssertionError("no visible face")


def _assert_no_dead_ids(app) -> None:
    mesh, sel = app.scene.mesh, app.selection
    assert all(mesh.is_valid_vertex(v) for v in sel.vertices)
    assert all(mesh.is_valid_edge(e) for e in sel.edges)
    assert all(mesh.is_valid_face(f) for f in sel.faces)
    h = sel.hovered
    if isinstance(h, VertexId):
        assert mesh.is_valid_vertex(h)
    elif isinstance(h, EdgeId):
        assert mesh.is_valid_edge(h)
    elif isinstance(h, FaceId):
        assert mesh.is_valid_face(h)


def _assert_idle(app) -> None:
    assert app.transform_command is None
    assert not app.transform_interacting
    assert app.interaction_owner is None
    assert app.tool_manager.active_tool is None


# -- Bindings (E10) -------------------------------------------------------------------


def test_t_is_bound_globally_to_extrude_and_alt_e_is_gone(app):
    assert app.bindings.command_for(T) == cmd.EXTRUDE
    assert app.bindings.command_for(_key("e", "alt")) is None


def test_the_extrude_tool_is_registered_in_the_tool_manager(app):
    assert app.tool_manager.registry[cmd.EXTRUDE] is ExtrudeTool


# -- Arming (E2) ----------------------------------------------------------------------


@pytest.mark.parametrize("mode_key", [K1, K2])
def test_outside_face_mode_arming_is_refused_with_a_status_line(app, mode_key):
    app.key_press(mode_key)
    before = _state(app)
    assert not app.key_press(T)
    assert app.status_message == "Extrude: face mode needed"
    _assert_idle(app)
    assert _state(app) == before


def test_nothing_selected_or_hovered_is_refused(app):
    assert app.selection.is_empty() and app.selection.hovered is None
    assert not app.key_press(T)
    assert app.status_message == "Extrude: select or hover a face"
    _assert_idle(app)


def test_arming_with_a_selection_activates_the_tool_but_begins_nothing(app):
    face = _faces(app)[0]
    _select(app, face)
    before = _state(app)
    assert app.key_press(T)
    assert app.transform_command == cmd.EXTRUDE
    assert app.interaction_owner == "transform"  # same hold-key family, no new H2 value
    assert not app.transform_interacting
    tool = app.tool_manager.active_tool
    assert isinstance(tool, ExtrudeTool) and tool.state is ToolState.ACTIVE
    assert app.status_message.startswith("Extrude: 1 face")
    assert _state(app) == before


def test_without_a_selection_the_hovered_face_is_extruded(app):
    face, x, y = _visible_face(app)
    app.pointer_motion(x, y)
    assert app.selection.hovered == face and app.selection.is_empty()
    assert app.key_press(T)
    assert app.selection.hovered is None  # clear-on-arm, like the transforms
    _drag(app)
    assert not app.scene.mesh.is_valid_face(face)  # topology changed
    assert app.key_release(T)
    assert len(app.history) == 1
    assert app.selection.faces and not app.selection.faces & {face}
    _assert_no_dead_ids(app)


def test_a_selection_wins_over_the_hovered_face(app):
    faces = _faces(app)
    hovered, x, y = _visible_face(app)
    chosen = next(f for f in faces if f != hovered)
    _select(app, chosen)
    app.pointer_motion(x, y)
    assert app.selection.hovered == hovered
    assert app.key_press(T)
    _drag(app)
    assert not app.scene.mesh.is_valid_face(chosen)
    assert app.scene.mesh.is_valid_face(hovered)
    app.key_release(T)


def test_a_second_hold_key_while_extrude_is_held_is_refused(app):
    _select(app, _faces(app)[0])
    app.key_press(T)
    assert not app.key_press(W)
    assert app.transform_command == cmd.EXTRUDE


# -- Tap / jitter = nothing (E3) ---------------------------------------------------------


def test_the_chosen_thresholds_are_small_and_documented():
    assert EXTRUDE_BEGIN_PX == 4.0
    assert EXTRUDE_MIN_DISTANCE == 1e-6


def test_tap_without_motion_does_nothing(app):
    _select(app, _faces(app)[0])
    before, sel = _state(app), set(app.selection.faces)
    assert app.key_press(T)
    assert app.key_release(T)
    assert _state(app) == before
    assert not app.history.can_undo()
    assert app.selection.faces == sel
    assert app.status_message == "Extrude: no change"
    _assert_idle(app)


def test_sub_threshold_jitter_does_nothing(app):
    _select(app, _faces(app)[0])
    before = _state(app)
    app.key_press(T)
    for dx, dy in [(1, 0), (-1, 0), (0, 2), (0, -2), (1, 1), (-1, -1), (0, 1)]:
        x, y = app._cursor or (400.0, 300.0)
        assert not app.pointer_motion(x + dx, y + dy, dx, dy)
    assert not app.transform_interacting
    assert _state(app) == before
    app.key_release(T)
    assert _state(app) == before
    assert not app.history.can_undo()  # Ctrl+Z must not bring back an empty step
    _assert_idle(app)


def test_back_and_forth_tremble_with_a_small_net_displacement_does_not_begin(app):
    _select(app, _faces(app)[0])
    before = _state(app)
    app.key_press(T)
    x, y = 400.0, 300.0
    for sign in (1, -1) * 10:  # path length 60 px, net displacement 0
        app.pointer_motion(x, y, 3.0 * sign, 0.0)
    assert not app.transform_interacting
    app.key_release(T)
    assert _state(app) == before and not app.history.can_undo()


def test_motion_beyond_the_threshold_begins_and_changes_the_topology(app):
    face = _faces(app)[0]
    _select(app, face)
    assert app.key_press(T)
    assert app.pointer_motion(404.0, 300.0, 4.0, 0.0)  # exactly the threshold
    assert app.transform_interacting
    assert _counts(app) == (12, 20, 10)
    assert not app.scene.mesh.is_valid_face(face)
    assert len(app.history) == 0  # not committed yet
    app.key_release(T)


def test_a_zero_total_distance_at_release_is_a_cancel(app):
    _select(app, _faces(app)[0])
    before = _state(app)
    app.key_press(T)
    _drag(app, dx=20.0, steps=3)
    assert app.transform_interacting and _state(app) != before
    _drag(app, dx=-20.0, steps=3)  # back to where it started
    assert app.key_release(T)
    assert _state(app) == before
    assert not app.history.can_undo()
    assert app.status_message == "Extrude: no change"
    _assert_idle(app)
    _assert_no_dead_ids(app)


# -- Commit / history / selection (E5, E8) ------------------------------------------------


def test_release_commits_exactly_one_history_entry_and_selects_the_caps(app):
    face = _faces(app)[0]
    _extrude(app, face)
    assert len(app.history) == 1
    assert _counts(app) == (12, 20, 10)
    assert app.status_message == "Extrude committed"
    assert app.selection.mode is SelectionMode.FACE
    assert len(app.selection.faces) == 1 and face not in app.selection.faces
    (cap,) = app.selection.faces
    assert app.scene.mesh.is_valid_face(cap)
    _assert_idle(app)


def _cap_offset_along_normal(dx: float) -> tuple[float, tuple[int, int, int]]:
    """Signed distance of the cap from the old face along its normal for a drag of `dx`
    px (fresh cube), and the resulting (V, E, F)."""
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.key_press(K3)
    face = _faces(app)[0]
    mesh = app.scene.mesh
    normal = _compute_face_normal(mesh, mesh.face_vertices(face))
    old_center = _center(mesh, mesh.face_vertices(face))
    _extrude(app, face, dx=dx)
    (cap,) = app.selection.faces
    new_center = _center(mesh, mesh.face_vertices(cap))
    return sum((n - o) * k for n, o, k in zip(new_center, old_center, normal)), _counts(app)


def _center(mesh, vertices):
    pts = [mesh.vertex_position(v) for v in vertices]
    return tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))


def test_the_distance_follows_the_pointer_in_both_directions_and_inward_is_a_pocket():
    out_offset, out_counts = _cap_offset_along_normal(40.0)
    in_offset, in_counts = _cap_offset_along_normal(-40.0)
    assert out_offset * in_offset < 0  # opposite drag directions, opposite signs
    assert abs(out_offset) > 0.01 and abs(in_offset) > 0.01
    # Negative distance = pocket with a floor: walls plus a cap, the same topology as outward
    # (no hole without a bottom).
    assert out_counts == in_counts == (12, 20, 10)


def test_undo_restores_mesh_selection_and_mode_redo_restores_the_cap_selection(app):
    face = _faces(app)[0]
    _select(app, face)
    before = _state(app)
    app.key_press(T)
    _drag(app)
    app.key_release(T)
    after = _state(app)
    caps = set(app.selection.faces)
    assert caps and face not in caps

    app.key_press(K1)  # Vertex mode, selection cleared
    assert app.selection.mode is SelectionMode.VERTEX

    assert app.key_press(CTRL_Z)
    assert _state(app) == before
    assert app.selection.mode is SelectionMode.FACE and app.selection.faces == {face}
    _assert_no_dead_ids(app)

    assert app.key_press(CTRL_Y)
    assert _state(app) == after
    assert app.selection.mode is SelectionMode.FACE and app.selection.faces == caps
    _assert_no_dead_ids(app)
    assert len(app.history) == 1  # one step in, one step back


def test_undo_after_a_hover_extrude_restores_the_empty_selection(app):
    face, x, y = _visible_face(app)
    app.pointer_motion(x, y)
    before = _state(app)
    app.key_press(T)
    _drag(app)
    app.key_release(T)
    app.key_press(CTRL_Z)
    assert _state(app) == before
    assert app.selection.is_empty()
    _assert_no_dead_ids(app)


def test_two_adjacent_faces_one_entry_one_undo(app):
    mesh = app.scene.mesh
    faces = _faces(app)
    a = faces[0]
    b = next(f for f in faces[1:] if set(mesh.face_edges(a)) & set(mesh.face_edges(f)))
    _select(app, a, b)
    before = _state(app)
    app.key_press(T)
    # Vertical: with the default camera a horizontal drag happens to be perpendicular to
    # the diagonal reference normal of these two faces (distance 0 = "no change").
    _drag(app, dx=0.0, dy=30.0)
    app.key_release(T)
    assert len(app.history) == 1
    assert len(app.selection.faces) == 2
    app.key_press(CTRL_Z)
    assert _state(app) == before
    assert app.selection.faces == {a, b}


def test_extrude_then_move_combine(app):
    _extrude(app)
    caps = set(app.selection.faces)
    mesh = app.scene.mesh
    cap_vertices = {v for f in caps for v in mesh.face_vertices(f)}
    old = {v: mesh.vertex_position(v) for v in cap_vertices}
    assert app.key_press(W)
    _drag(app, dx=25.0, dy=10.0)
    assert app.key_release(W)
    assert len(app.history) == 2
    assert any(mesh.vertex_position(v) != old[v] for v in cap_vertices)
    app.key_press(CTRL_Z)
    assert {v: mesh.vertex_position(v) for v in cap_vertices} == old


# -- Cancel (Esc) ---------------------------------------------------------------------------


def test_esc_mid_gesture_restores_everything_exactly(app):
    face = _faces(app)[0]
    _select(app, face)
    before = _state(app)
    app.key_press(T)
    _drag(app)
    assert app.transform_interacting and _state(app) != before
    assert app.key_press(ESC)
    assert _state(app) == before
    assert not app.history.can_undo()
    assert app.selection.mode is SelectionMode.FACE and app.selection.faces == {face}
    assert app.status_message == "Extrude cancelled"
    _assert_idle(app)
    _assert_no_dead_ids(app)
    app.key_release(T)  # the late release is harmless
    assert _state(app) == before


def test_esc_while_only_armed_disarms(app):
    _select(app, _faces(app)[0])
    app.key_press(T)
    assert app.key_press(ESC)
    assert app.status_message == "Extrude disarmed"
    _assert_idle(app)


def test_esc_after_a_hover_extrude_leaves_no_dead_hover(app):
    face, x, y = _visible_face(app)
    app.pointer_motion(x, y)
    app.key_press(T)
    _drag(app)
    app.key_press(ESC)
    assert app.selection.is_empty()
    _assert_no_dead_ids(app)


def test_a_refused_begin_disarms_visibly_and_changes_nothing(app):
    face = _faces(app)[0]
    _select(app, face)
    app.key_press(T)
    app.scene.mesh.remove_face(face)  # the armed face vanished before the first motion
    before = _state(app)
    _drag(app)
    assert app.status_message.startswith("Extrude: refused")
    assert _state(app) == before
    assert not app.history.can_undo()
    _assert_idle(app)


# -- Session gate (E6) -----------------------------------------------------------------------


@pytest.mark.parametrize("begun", [False, True])
def test_mode_keys_c_and_delete_are_ignored_while_t_is_held(app, begun):
    _select(app, _faces(app)[0])
    app.key_press(T)
    if begun:
        _drag(app)
    state, mode, sel = _state(app), app.selection.mode, set(app.selection.faces)
    for key in (K1, K2, K3, _key("c"), _key("delete"), _key("backspace"), _key("backspace", "ctrl")):
        assert not app.key_press(key)
    assert _state(app) == state
    assert app.selection.mode is mode and app.selection.faces == sel
    assert app.transform_command == cmd.EXTRUDE
    assert app.transform_interacting is begun
    app.key_release(T)


def test_undo_and_redo_are_ignored_while_extrude_runs(app):
    _extrude(app)  # one earlier step to undo
    _select(app, _faces(app)[0])
    app.key_press(T)
    _drag(app)
    state = _state(app)
    assert not app.key_press(CTRL_Z)
    assert not app.key_press(CTRL_Y)
    assert _state(app) == state and len(app.history) == 1
    app.key_press(ESC)


def test_undo_while_only_armed_disarms_first_then_undoes(app):
    _extrude(app)
    _select(app, _faces(app)[0])
    app.key_press(T)
    assert app.transform_command == cmd.EXTRUDE and not app.transform_interacting
    assert app.key_press(CTRL_Z)
    _assert_idle(app)
    assert not app.history.can_undo() and app.history.can_redo()
    assert _counts(app) == (8, 12, 6)


def test_display_keys_still_work_during_the_gesture(app):
    _select(app, _faces(app)[0])
    app.key_press(T)
    _drag(app)
    assert app.key_press(_key("d"))
    assert app.transform_interacting
    app.key_press(ESC)


# -- Axis constraints do not touch Extrude (E6) ---------------------------------------------------


CONSTRAINT_KEYS = [
    _key("x"), _key("y"), _key("z"),
    _key("x", "shift"), _key("y", "shift"), _key("z", "shift"),
]


@pytest.mark.parametrize("begun", [False, True])
def test_constraint_keys_do_nothing_and_leave_the_sticky_state_alone(app, begun):
    app.key_press(_key("x"))
    assert app.axis_constraint == "x"
    _select(app, _faces(app)[0])
    app.key_press(T)
    if begun:
        _drag(app)
    state, tool = _state(app), app.tool_manager.active_tool
    distance = tool.total_distance if begun else None
    for key in CONSTRAINT_KEYS:
        assert not app.key_press(key)  # no crash, nothing handled
    assert app.axis_constraint == "x"
    assert _state(app) == state
    if begun:
        assert tool.total_distance == distance
    app.key_press(ESC)


def test_constraint_keys_still_toggle_outside_an_extrude(app):
    assert app.key_press(_key("y"))
    assert app.axis_constraint == "y"
    _extrude(app)
    assert app.axis_constraint == "y"  # survives an Extrude gesture untouched


def test_extrude_status_carries_no_constraint_suffix(app):
    app.key_press(_key("z"))
    _select(app, _faces(app)[0])
    app.key_press(T)
    assert "constraint" not in app.status_message
    _drag(app)
    app.key_release(T)
    assert "constraint" not in app.status_message


# -- Viewport / caches (E7) ----------------------------------------------------------------------


def test_viewport_and_pick_cache_are_notified_at_begin_update_commit_and_cancel(app, monkeypatch):
    events: list[str] = []
    for name in ("on_topology_changed", "on_vertices_moved"):
        original = getattr(app.viewport, name)
        monkeypatch.setattr(
            app.viewport, name, lambda *a, _o=original, _n=name, **k: (events.append(_n), _o(*a, **k))[1]
        )
    original_invalidate = app._pick_cache.invalidate
    monkeypatch.setattr(
        app._pick_cache, "invalidate", lambda: (events.append("pick_cache"), original_invalidate())[1]
    )

    _select(app, _faces(app)[0])
    app.key_press(T)
    app.pointer_motion(440.0, 300.0, 40.0, 0.0)  # begin + first update
    begin_events = list(events)
    assert begin_events.index("on_topology_changed") < begin_events.index("on_vertices_moved")
    assert "pick_cache" in begin_events

    events.clear()
    app.pointer_motion(460.0, 300.0, 20.0, 0.0)  # a plain update
    assert "pick_cache" in events and "on_vertices_moved" in events

    events.clear()
    app.key_release(T)  # commit
    assert "pick_cache" in events and "on_topology_changed" in events

    events.clear()
    _select(app, _faces(app)[0])
    app.key_press(T)
    app.pointer_motion(440.0, 300.0, 40.0, 0.0)
    events.clear()
    app.key_press(ESC)  # cancel
    assert "pick_cache" in events and "on_topology_changed" in events


def test_the_first_update_moves_the_new_cap_vertices(app, monkeypatch):
    moved: list[set] = []
    original = app.viewport.on_vertices_moved
    monkeypatch.setattr(
        app.viewport, "on_vertices_moved", lambda ids: (moved.append(set(ids)), original(ids))[1]
    )
    face = _faces(app)[0]
    old = set(app.scene.mesh.face_vertices(face))
    _select(app, face)
    app.key_press(T)
    app.pointer_motion(440.0, 300.0, 40.0, 0.0)
    assert len(moved[-1]) == 4 and not moved[-1] & old


def test_no_dead_id_survives_commit_cancel_and_undo_even_with_a_stale_hover(app):
    face, x, y = _visible_face(app)
    for finish in ("commit", "cancel", "undo"):
        app.key_press(K3)
        app.pointer_motion(x, y)
        if app.selection.hovered is None:
            continue
        app.key_press(T)
        _drag(app)
        if finish == "cancel":
            app.key_press(ESC)
        else:
            app.key_release(T)
            if finish == "undo":
                app.key_press(CTRL_Z)
        _assert_no_dead_ids(app)
        app.pointer_motion(x, y)
        _assert_no_dead_ids(app)


# -- Command gate (E6, E9) ---------------------------------------------------------------------------


def test_the_command_gate_refuses_before_arming(app):
    app.command_gate = CommandGate(refused={cmd.EXTRUDE: "Extrude blocked"})
    _select(app, _faces(app)[0])
    before, serial = _state(app), app.status_serial
    assert not app.key_press(T)
    assert app.status_message == "Extrude blocked" and app.status_serial == serial + 1
    _assert_idle(app)
    assert _state(app) == before


def test_an_allow_list_without_extrude_refuses_it_too(app):
    app.command_gate = CommandGate(allowed=frozenset({cmd.UNDO}), not_allowed_text="nope")
    _select(app, _faces(app)[0])
    assert not app.key_press(T)
    assert app.status_message == "nope"
    _assert_idle(app)
