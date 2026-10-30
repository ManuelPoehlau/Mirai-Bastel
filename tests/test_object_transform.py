"""AD-021 M2-2 — move / rotate / scale objects in mode `4` (E-11 gesture, E-12 command).

Headless (TraceStore), no pyglet. The object gesture is driven through the real key and
pointer path (`key_press` W/E/R, `pointer_motion`, `key_release`, Esc); the expected
transforms are computed from the rules of the handoff (E-11): Move = camera-plane delta through
the pivot, masked by the world constraint; Rotate = `Q(axis, π/400 · Σdx) · R_start` about the
view direction or the world axis; Scale = `s_start · (1 + 0.005 · Σ(dx + dy))`, always uniform.
Also: L-1 (no mesh is touched), Q-1/RF-4 (References locked), Q-3 (one Undo step), Q-6
(status line), component work and symmetry on a placed edit object, serialization.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from core import ObjectState, ObjectTransform, SelectionMode, VertexId
from core.scene import IDENTITY_TRANSFORM
from core.serialization import scene_from_dict, scene_to_dict
from mirai import object_space
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.interaction.tools.rotate import RotateTool
from mirai.interaction.tools.scale import ScaleTool
from mirai.symmetry import symmetry_state, vertex_correspondence
from mirai.symmetry_axis import set_symmetry_axis
from mirai.viewport.picking import pick_nearest_vertex

WIDTH, HEIGHT = 800, 600
HEAD_OBJ = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


W, E, R, ESC = _key("w"), _key("e"), _key("r"), _key("ESCAPE")
ONE, FOUR = _key("1"), _key("4")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")


def _app(obj_path=None) -> Application:
    app = Application()
    if obj_path is None:
        app.init_scene("cube")
    else:
        app.init_scene("obj", obj_path=obj_path)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _object_mode(app: Application, *objects) -> None:
    """Mode `4` with exactly these objects selected (the click path is tested in M1)."""
    app.key_press(FOUR)
    app.selection.objects = {obj.id for obj in objects}


def _gesture(app: Application, key: Input, steps=((24.0, 9.0),), constraint: Input | None = None):
    if constraint is not None:
        app.key_press(constraint)
    assert app.key_press(key), app.status_message
    for dx, dy in steps:
        app.pointer_motion(400, 300, dx, dy)
    app.key_release(key)
    if constraint is not None:
        app.key_press(constraint)  # sticky toggle back off


def _close(a, b, tol=1e-9) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _flat(m):
    return [c for row in m for c in row]


def _states(app: Application) -> dict:
    return {oid: obj.mesh.export_state() for oid, obj in app.scene.objects.items()}


def _normal_second_cube(app: Application):
    other = app.add_reference("cube", name="other")
    other.state = ObjectState.NORMAL
    app._objects.sync_views()
    return other


# -- Move (W) ---------------------------------------------------------------------------


def test_free_move_translates_by_the_camera_plane_delta_through_the_pivot():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    meshes = _states(app)
    expected = app.camera.screen_delta_to_world(
        object_space.to_world(cube, cube.pivot), 24.0, 9.0, WIDTH, HEIGHT
    )
    _gesture(app, W)
    assert _close(cube.transform.translation, expected, 1e-12)
    assert cube.transform.rotation == IDENTITY_TRANSFORM.rotation and cube.transform.scale == 1.0
    assert _states(app) == meshes  # L-1: only the placement changed
    assert app.status_message == "Object 'cube': moved (object level)"
    assert app.interaction_owner is None


def test_move_along_x_and_in_the_xz_plane_are_world_masks():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    app.key_press(_key("x"))
    _gesture(app, W)
    assert "(constraint X)" in app.status_message
    app.key_press(_key("x"))
    t = cube.transform.translation
    assert abs(t[0]) > 1e-3 and t[1] == 0.0 and t[2] == 0.0
    _gesture(app, W, steps=((10.0, 30.0),), constraint=_key("y", "shift"))  # Shift+Y = XZ plane
    t2 = cube.transform.translation
    assert t2[1] == 0.0 and abs(t2[2]) > 1e-3


def test_several_motions_add_up_and_each_step_redraws_without_a_rebuild():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    assert app.key_press(W)
    assert app.interaction_owner == "transform"
    app.pointer_motion(400, 300, 10.0, 0.0)
    first = cube.transform
    assert app.viewport.model_matrix == object_space.model_matrix(cube)
    app.pointer_motion(400, 300, 10.0, 0.0)
    assert cube.transform != first
    assert app.viewport.model_matrix == object_space.model_matrix(cube)
    app.key_release(W)
    app.viewport.sync()
    assert app.viewport.render_mesh.benchmark_counters.get("topology_updates", 0) == 0
    assert len(app._selection_undo_stack) == 1  # one gesture, one Undo step (Q-3)


# -- Rotate (E) -------------------------------------------------------------------------


def test_free_rotate_turns_about_the_view_direction_and_keeps_the_pivot():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    forward = app.camera.basis()[0]
    _gesture(app, E, steps=((30.0, 5.0), (20.0, -3.0)))  # Rotate reads dx only
    angle = RotateTool.RADIANS_PER_PIXEL * 50.0
    expected = object_space.axis_angle_rotation(forward, angle)
    assert _close(_flat(cube.transform.rotation), _flat(expected), 1e-12)
    assert cube.transform.translation == (0.0, 0.0, 0.0)  # the pivot's world position t + c stays
    assert app.status_message == "Object 'cube': rotated (object level)"


def test_rotate_about_world_z_keeps_world_z():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    _gesture(app, E, steps=((60.0, 0.0),), constraint=_key("z"))
    rot = cube.transform.rotation
    assert _close(object_space.axis_to_world(cube, (0.0, 0.0, 1.0)), (0.0, 0.0, 1.0), 1e-12)
    assert abs(rot[0][0] - math.cos(RotateTool.RADIANS_PER_PIXEL * 60.0)) < 1e-12


def test_rotation_stays_valid_after_many_gestures():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    for i in range(150):
        constraint = (None, _key("x"), _key("y"), _key("z"))[i % 4]
        _gesture(app, E, steps=((37.0 + i % 11, 0.0), (-13.0, 0.0)), constraint=constraint)
    rot = cube.transform.rotation
    for i in range(3):
        for j in range(3):
            dot = sum(rot[i][k] * rot[j][k] for k in range(3))
            assert abs(dot - (1.0 if i == j else 0.0)) < 1e-12
    ObjectTransform(rotation=rot)  # the Core's own check (ROTATION_TOLERANCE)
    assert len(app._selection_undo_stack) == 150


# -- Scale (R) --------------------------------------------------------------------------


def test_scale_is_uniform_even_with_an_axis_constraint():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    app.key_press(_key("x"))
    app.key_press(R)
    assert "uniform - X/Y/Z do not apply" in app.status_message
    app.pointer_motion(400, 300, 30.0, 10.0)
    app.key_release(R)
    assert cube.transform.scale == 1.0 + ScaleTool.SCALE_PER_PIXEL * 40.0
    assert cube.transform.translation == (0.0, 0.0, 0.0)
    assert app.status_message == "Object 'cube': scaled (object level)"
    assert app.axis_constraint == "x"  # the sticky constraint is untouched


def test_scale_never_reaches_zero():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    _gesture(app, R, steps=((-5000.0, 0.0),))
    assert cube.transform.scale == ScaleTool.MIN_SCALE


# -- Esc, tap, Undo/Redo ------------------------------------------------------------------


@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_esc_restores_the_start_transform_exactly(key):
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    _gesture(app, W)  # a placement to start from
    start = cube.transform
    app.key_press(key)
    app.pointer_motion(400, 300, 40.0, 12.0)
    assert cube.transform != start
    assert app.key_press(ESC)
    assert cube.transform is start
    assert app.viewport.model_matrix == object_space.model_matrix(cube)
    assert len(app._selection_undo_stack) == 1
    assert "cancelled" in app.status_message
    app.key_release(key)  # the release after Esc does nothing
    assert cube.transform is start


def test_a_tap_records_nothing():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    app.key_press(W)
    app.key_release(W)
    assert cube.transform is IDENTITY_TRANSFORM
    assert not app.history.can_undo()
    assert "no motion" in app.status_message


def test_undo_and_redo_restore_the_transform_matrices_and_picking():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    _gesture(app, W, steps=((80.0, 30.0),))
    placed = cube.transform
    app.key_press(ONE)
    mesh = app.scene.mesh
    mesh_state = mesh.export_state()

    def visible_vertex() -> tuple[VertexId, tuple[float, float]]:
        cam = app._objects.edit_camera
        for vid in sorted(mesh.all_vertex_ids()):
            x, y = cam.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
            if pick_nearest_vertex(cam, mesh, x, y, WIDTH, HEIGHT, occlusion=True) == vid:
                return vid, (x, y)
        raise AssertionError("no visible vertex")

    vid, placed_screen = visible_vertex()
    assert app._pick(*placed_screen) == vid  # fills the pick cache at the placed position
    assert app.key_press(CTRL_Z)
    assert cube.transform is IDENTITY_TRANSFORM
    assert app.viewport.model_matrix is None
    _, plain_screen = visible_vertex()
    assert app._pick(*plain_screen) is not None  # the cache re-projected, not stale
    assert app._pick(*placed_screen) != vid or plain_screen == placed_screen
    assert app.key_press(CTRL_Y)
    assert cube.transform is placed
    assert app.viewport.model_matrix == object_space.model_matrix(cube)
    assert app._pick(*placed_screen) == vid
    assert mesh.export_state() == mesh_state  # Undo/Redo of a placement never touch the mesh


def test_undo_of_a_reference_entry_placement_updates_its_matrix():
    app = _app()
    other = _normal_second_cube(app)
    _object_mode(app, other)
    _gesture(app, W)
    app.viewport.sync()
    entry = app.viewport.object_entries[other.id]
    assert entry.store.data("model_uniforms") == object_space.model_matrix(other)
    app.key_press(CTRL_Z)
    app.viewport.sync()
    assert other.transform is IDENTITY_TRANSFORM
    assert entry.model_matrix is None


def test_an_object_step_and_a_mesh_step_undo_in_order():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    _gesture(app, W)
    mesh = app.scene.mesh
    vid = sorted(mesh.all_vertex_ids())[0]
    before = mesh.vertex_position(vid)

    def bump():
        x, y, z = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (x + 0.25, y, z))
        return {vid}

    assert app.apply_mesh_change("nudge", bump)
    app.key_press(CTRL_Z)
    assert mesh.vertex_position(vid) == before and cube.transform is not IDENTITY_TRANSFORM
    app.key_press(CTRL_Z)
    assert cube.transform is IDENTITY_TRANSFORM


# -- Refusals and References (Q-1, RF-4) ------------------------------------------------------


def test_nothing_selected_refuses():
    app = _app()
    app.key_press(FOUR)
    assert app.key_press(W) is False
    assert app.interaction_owner is None
    assert "no object selected" in app.status_message


def test_only_a_reference_selected_refuses_with_the_lock():
    app = _app()
    ref = app.add_reference("cube", name="plate")
    _object_mode(app, ref)
    for key in (W, E, R):
        assert app.key_press(key) is False
        assert "'plate' is a Reference - locked" in app.status_message
    assert ref.transform is IDENTITY_TRANSFORM


def test_a_reference_in_a_mixed_selection_stays_and_the_status_says_so():
    app = _app()
    cube = app.scene.edit_object
    ref = app.add_reference("cube", name="plate")
    _object_mode(app, cube, ref)
    app.key_press(W)
    assert "Reference 'plate' stays (locked)" in app.status_message
    app.pointer_motion(400, 300, 20.0, 0.0)
    app.key_release(W)
    assert cube.transform is not IDENTITY_TRANSFORM
    assert ref.transform is IDENTITY_TRANSFORM
    assert app.status_message == (
        "Object 'cube': moved (object level) - Reference 'plate' stays (locked)"
    )


def test_extrude_stays_component_work_in_object_mode():
    app = _app()
    _object_mode(app, app.scene.edit_object)
    assert app.key_press(_key("t")) is False
    assert "press 1/2/3" in app.status_message


def test_the_gesture_holds_the_keys():
    app = _app()
    cube = app.scene.edit_object
    ref = app.add_reference("cube", name="plate")
    _object_mode(app, cube)
    app.key_press(W)
    app.pointer_motion(400, 300, 20.0, 0.0)
    assert app.key_press(ONE) is False and app.selection.mode is SelectionMode.OBJECT
    assert app.key_press(CTRL_Z) is False
    assert app.add_reference("cube") is None
    # a click underneath the held key neither selects nor switches a state
    app.pointer_press(Input("mouse", "LEFT", frozenset()), 400, 300)
    app.pointer_release("LEFT", 400, 300)
    assert app.selection.objects == {cube.id} and ref.state is ObjectState.REFERENCE
    app.key_release(W)
    assert app.interaction_owner is None


# -- Several objects --------------------------------------------------------------------------


def test_two_objects_move_by_the_same_delta_and_turn_about_their_own_pivots():
    app = _app()
    cube = app.scene.edit_object
    other = _normal_second_cube(app)
    other.transform = ObjectTransform(translation=(3.0, 0.0, 0.0))
    other.pivot = (0.5, 0.0, 0.0)
    app._objects.placement_changed()
    _object_mode(app, cube, other)
    _gesture(app, W)
    delta = cube.transform.translation
    assert _close(other.transform.translation, (3.0 + delta[0], delta[1], delta[2]), 1e-12)
    assert app.status_message == "Objects 'cube', 'other': moved (object level)"
    pivots = [object_space.to_world(o, o.pivot) for o in (cube, other)]
    _gesture(app, E, steps=((45.0, 0.0),))
    assert cube.transform.rotation == other.transform.rotation
    for o, p in zip((cube, other), pivots):
        assert _close(object_space.to_world(o, o.pivot), p, 1e-12)
    app.key_press(CTRL_Z)
    app.key_press(CTRL_Z)
    assert cube.transform is IDENTITY_TRANSFORM
    assert other.transform == ObjectTransform(translation=(3.0, 0.0, 0.0))


# -- Level marker (Q-6) and component work on the placed edit object ---------------------------


def test_mode_switch_names_the_placed_edit_object():
    app = _app()
    _object_mode(app, app.scene.edit_object)
    _gesture(app, R)
    app.key_press(ONE)
    # M2-4 (Q-5) names the edit object when the selected one already is it.
    assert app.status_message == "Mode: Vertex · editing 'cube' · object 'cube' is placed (object level)"
    app.key_press(CTRL_Z)
    app.key_press(_key("2"))
    assert app.status_message == "Mode: Edge · editing 'cube'"  # no "placed" after the Undo


def _visible_vertex(app: Application) -> tuple[VertexId, tuple[float, float]]:
    mesh, cam = app.scene.mesh, app._objects.edit_camera
    for vid in sorted(mesh.all_vertex_ids()):
        x, y = cam.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
        if pick_nearest_vertex(cam, mesh, x, y, WIDTH, HEIGHT, occlusion=True) == vid:
            return vid, (x, y)
    raise AssertionError("no visible vertex")


def _click(app: Application, x: float, y: float) -> None:
    app.pointer_press(Input("mouse", "LEFT", frozenset()), x, y)
    app.pointer_release("LEFT", x, y)


def test_component_move_and_knife_work_on_the_placed_edit_object():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    _gesture(app, W, steps=((60.0, -20.0),))
    _gesture(app, E, steps=((70.0, 0.0),))
    _gesture(app, R, steps=((-40.0, 0.0),))
    app.key_press(ONE)
    mesh = app.scene.mesh
    vid, screen = _visible_vertex(app)
    _click(app, *screen)
    assert app.selection.vertices == {vid}
    world_before = object_space.to_world(cube, mesh.vertex_position(vid))
    expected = app.camera.screen_delta_to_world(world_before, 15.0, 6.0, WIDTH, HEIGHT)
    _gesture(app, W, steps=((15.0, 6.0),))
    world_after = object_space.to_world(cube, mesh.vertex_position(vid))
    assert _close([world_after[i] - world_before[i] for i in range(3)], expected, 1e-9)
    # Knife: C with an empty selection starts a session; the edge pick is at its placed position.
    app.key_press(ONE)
    cam = app._objects.edit_camera
    assert app.key_press(_key("c")) and app.knife_active
    for eid in sorted(mesh.all_edge_ids()):
        a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
        mid = tuple((a[i] + b[i]) / 2 for i in range(3))
        hit = app._knife.pick(*cam.project_to_screen(mid, WIDTH, HEIGHT))
        if hit.get("kind") == "edge" and hit["edge_id"] == eid:
            break
    else:
        raise AssertionError("no knife-pickable edge on the placed cube")
    app.key_press(ESC)
    assert not app.knife_active


@pytest.mark.skipif(not HEAD_OBJ.is_file(), reason="head_basemesh fehlt (examples/meshes/)")
def test_a_turned_symmetric_head_stays_exactly_symmetric_under_a_symmetric_move():
    """P-2 through the M2-2 gesture (Q-7: the plane turns with the object)."""
    app = _app(obj_path=HEAD_OBJ)
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    head = app.scene.edit_object
    _object_mode(app, head)
    _gesture(app, E, steps=((66.0, 0.0),), constraint=_key("y"))
    _gesture(app, W, steps=((25.0, -10.0),))
    assert head.transform.rotation != IDENTITY_TRANSFORM.rotation
    assert symmetry_state(mesh).value == "valid"
    app.key_press(ONE)
    app.frame_scene()
    cam = app._objects.edit_camera
    vid = next(
        v for v in sorted(mesh.all_vertex_ids())
        if mesh.vertex_position(v)[0] > 0.1
        and app._pick(*cam.project_to_screen(mesh.vertex_position(v), WIDTH, HEIGHT)) == v
    )
    _click(app, *cam.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT))
    _gesture(app, W, steps=((17.0, -11.0),))
    partner = vertex_correspondence(mesh)[vid].partner
    a, b = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert (b[0], b[1], b[2]) == (-a[0], a[1], a[2])  # bit-exact in object space
    assert symmetry_state(mesh).value == "valid"


def test_a_placed_object_survives_a_serialization_roundtrip():
    app = _app()
    cube = app.scene.edit_object
    _object_mode(app, cube)
    _gesture(app, W)
    _gesture(app, E, steps=((33.0, 0.0),))
    _gesture(app, R, steps=((12.0, 3.0),))
    loaded = scene_from_dict(scene_to_dict(app.scene))
    assert loaded.edit_object.transform == cube.transform
    assert loaded.edit_object.mesh.export_state() == cube.mesh.export_state()


# -- E-11 helpers ---------------------------------------------------------------------------


def test_orthonormalize_repairs_drift_beyond_the_core_tolerance():
    turn = object_space.axis_angle_rotation((0.0, 0.6, 0.8), 0.7)
    drifted = tuple(tuple(c * (1.0 + 1e-7 * (i + 1)) + 1e-7 * j for j, c in enumerate(row))
                    for i, row in enumerate(turn))
    with pytest.raises(ValueError):
        ObjectTransform(rotation=drifted)
    repaired = object_space.orthonormalize(drifted)
    ObjectTransform(rotation=repaired)
    assert _close(_flat(repaired), _flat(turn), 1e-6)


def test_axis_angle_rotation_matches_the_core_rotation_direction():
    """Same right-hand rule as `core.operations.transform` (component Rotate)."""
    q = object_space.axis_angle_rotation((0.0, 0.0, 1.0), math.pi / 2)
    assert _close(object_space._rotate(q, (1.0, 0.0, 0.0)), (0.0, 1.0, 0.0), 1e-15)
    assert object_space.axis_angle_rotation((1.0, 0.0, 0.0), 0.0) == IDENTITY_TRANSFORM.rotation
