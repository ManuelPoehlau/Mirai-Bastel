"""AD-021 M2-4 — switching the edit object (Q-5 gesture, E-14, Q-8 Undo).

Headless (TraceStore), no pyglet. Q-5: in `4` select exactly one Normal object, then
`1`/`2`/`3` - it becomes the edit object (order §4.4: read `objects`, set the edit object,
clear the components); several objects or a Reference: no switch, the status line says why.
E-14: `ObjectController.set_edit_object` is the one place - viewport overlay entry
(`Viewport.set_edit_mesh`), object entries, pick caches, hover, soft radius. Q-8: Undo of a
step made on another object makes that object the edit object again. RF-5: a Reference never
becomes the edit object.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from core import ObjectState, ObjectTransform, SelectionMode, VertexId
from mirai import object_space
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_nearest_vertex

WIDTH, HEIGHT = 800, 600
HEAD_OBJ = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


ONE, TWO, FOUR = _key("1"), _key("2"), _key("4")
W, CTRL_Z, CTRL_Y = _key("w"), _key("z", "ctrl"), _key("y", "ctrl")


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _second(app: Application, name: str = "other", translation=(3.0, 0.0, 0.0), obj_path=None):
    if obj_path is None:
        obj = app.add_reference("cube", name=name)
    else:
        obj = app.add_reference("obj", obj_path=obj_path, name=name)
    app._objects.switch_state(obj.id, app._selection_snapshot())  # Normal, one Undo step
    obj.transform = ObjectTransform(translation=translation)
    app._objects.placement_changed()
    return obj


def _switch_to(app: Application, obj, key: Input = ONE) -> None:
    app.key_press(FOUR)
    app.selection.objects = {obj.id}
    app.key_press(key)


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


def _nudge(app: Application, vid: VertexId) -> None:
    mesh = app.scene.mesh

    def bump():
        x, y, z = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (x + 0.25, y, z))
        return {vid}

    assert app.apply_mesh_change("nudge", bump)


# -- Q-5 gesture and E-14 ----------------------------------------------------------------------


def test_one_selected_normal_object_becomes_the_edit_object_and_back():
    app = _app()
    cube = app.scene.edit_object
    other = _second(app)
    _switch_to(app, other)
    assert app.scene.edit_object_id == other.id
    assert app.selection.mode is SelectionMode.VERTEX
    assert app.selection.vertices == set() and app.selection.objects == {other.id}
    assert app.viewport.mesh is other.mesh and app.viewport.render_mesh.mesh is other.mesh
    assert app.viewport.model_matrix == object_space.model_matrix(other)
    assert set(app.viewport.object_entries) == {cube.id}
    assert app.viewport.object_entries[cube.id].mesh is cube.mesh
    assert app.status_message == (
        "Mode: Vertex · editing 'other' · object 'other' is placed (object level)"
    )
    assert app.last_edit_switch_seconds > 0.0
    _switch_to(app, cube, TWO)
    assert app.scene.edit_object_id == cube.id
    assert app.viewport.mesh is cube.mesh and app.viewport.model_matrix is None
    assert set(app.viewport.object_entries) == {other.id}
    assert app.status_message == "Mode: Edge · editing 'cube'"


def test_the_switch_is_no_undo_step():
    app = _app()
    other = _second(app)
    steps = len(app._selection_undo_stack)
    _switch_to(app, other)
    assert len(app._selection_undo_stack) == steps
    assert app.history.can_undo()  # the state switch of `_second`, nothing new


def test_several_objects_or_a_reference_do_not_switch():
    app = _app()
    cube = app.scene.edit_object
    other = _second(app)
    ref = app.add_reference("cube", name="plate")
    app.key_press(FOUR)
    app.selection.objects = {cube.id, other.id}
    app.key_press(ONE)
    assert app.scene.edit_object_id == cube.id
    assert app.status_message == "Mode: Vertex · 2 objects selected - still editing 'cube'"
    _switch_to(app, ref)
    assert app.scene.edit_object_id == cube.id
    assert app.status_message == "Mode: Vertex · 'plate' is a Reference - still editing 'cube'"
    assert ref.state is ObjectState.REFERENCE


def test_1_2_3_without_an_object_selection_keep_the_edit_object():
    app = _app()
    cube = app.scene.edit_object
    _second(app)
    app.key_press(FOUR)
    app.key_press(ONE)
    assert app.scene.edit_object_id == cube.id
    assert app.status_message == "Mode: Vertex"


def test_no_switch_while_an_interaction_owns_the_keys():
    app = _app()
    cube = app.scene.edit_object
    other = _second(app)
    app.key_press(FOUR)
    app.selection.objects = {other.id}
    app.key_press(W)
    app.pointer_motion(400, 300, 10.0, 0.0)
    assert app.key_press(ONE) is False  # the key gate
    assert "not while the transform" in app._objects.edit_from_selection()
    assert app.scene.edit_object_id == cube.id
    app.key_release(W)


# -- component work on the new edit object --------------------------------------------------------


def test_component_move_on_the_new_placed_edit_object_and_the_old_mesh_stays():
    app = _app()
    cube = app.scene.edit_object
    other = _second(app)
    other.transform = ObjectTransform(translation=(0.5, 1.0, 0.0), scale=0.8)
    app._objects.placement_changed()
    cube_state = cube.mesh.export_state()
    _switch_to(app, other)
    vid, screen = _visible_vertex(app)
    _click(app, *screen)
    assert app.selection.vertices == {vid}
    before = object_space.to_world(other, other.mesh.vertex_position(vid))
    expected = app.camera.screen_delta_to_world(before, 14.0, -6.0, WIDTH, HEIGHT)
    app.key_press(W)
    app.pointer_motion(400, 300, 14.0, -6.0)
    app.key_release(W)
    after = object_space.to_world(other, other.mesh.vertex_position(vid))
    assert all(abs(after[i] - before[i] - expected[i]) < 1e-9 for i in range(3))
    assert cube.mesh.export_state() == cube_state


def test_overlays_only_on_the_edit_object_with_colliding_ids():
    app = _app()
    cube = app.scene.edit_object
    other = _second(app)
    _switch_to(app, other)
    app.selection.vertices = {VertexId(0)}  # VertexId(0) exists in both cubes
    app.viewport.on_selection_changed()
    app.viewport.sync()
    assert app.viewport.point_positions["selected"] == [other.mesh.vertex_position(VertexId(0))]
    entry = app.viewport.object_entries[cube.id]
    assert entry.overlay is None and not entry.store.has("highlight_flags")
    assert app.viewport.render_mesh.overlay is app.viewport.overlay


def test_hover_and_pick_cache_follow_the_switch():
    """Both objects unplaced (the `OrbitCamera` itself, one camera revision), the second mesh
    shifted in its own coordinates: only an explicit invalidation keeps the cache honest."""
    app = _app()
    other = _second(app, translation=(0.0, 0.0, 0.0))
    mesh = other.mesh
    for v in mesh.all_vertex_ids():
        x, y, z = mesh.vertex_position(v)
        mesh.set_vertex_position(v, (x + 0.7, y + 0.4, z))
    app.key_press(ONE)
    vid, screen = _visible_vertex(app)
    app.pointer_motion(*screen)
    assert app.selection.hovered == vid  # fills the cube's pick cache
    _switch_to(app, other)
    assert app.selection.hovered is None
    other_vid, other_screen = _visible_vertex(app)
    app.pointer_motion(*other_screen)
    assert app.selection.hovered == other_vid
    _click(app, *other_screen)
    assert app.selection.vertices == {other_vid}
    assert app.scene.mesh is other.mesh


def test_the_knife_works_on_the_new_edit_object():
    app = _app()
    other = _second(app)
    _switch_to(app, other)
    assert app.key_press(_key("c")) and app.knife_active
    assert app.knife_render_data is not None
    app.key_press(_key("ESCAPE"))


@pytest.mark.skipif(not HEAD_OBJ.is_file(), reason="head_basemesh fehlt (examples/meshes/)")
def test_the_soft_radius_is_recomputed_for_the_new_edit_object():
    app = _app()
    head = _second(app, name="head", obj_path=HEAD_OBJ)
    app.key_press(_key("o"))  # Soft on
    cube_radius = app.soft_settings.world_radius
    _switch_to(app, head)
    assert app.soft_settings.world_radius != cube_radius
    from mirai.mesh_geometry import mesh_center_and_radius

    expected = app.soft_settings.with_bounding_radius(mesh_center_and_radius(head.mesh)[1])
    assert app.soft_settings == expected


# -- Q-8: Undo jumps back to the object of the step ------------------------------------------------


def test_undo_and_redo_switch_to_the_object_of_the_step():
    app = _app()
    cube = app.scene.edit_object
    other = _second(app)
    app.key_press(ONE)
    _nudge(app, VertexId(0))  # on the cube
    cube_after = cube.mesh.export_state()
    _switch_to(app, other)
    _nudge(app, VertexId(1))  # on the other cube
    other_after = other.mesh.export_state()
    assert app.key_press(CTRL_Z)
    assert app.scene.edit_object_id == other.id  # the step was made on `other`
    assert other.mesh.export_state() != other_after
    assert app.key_press(CTRL_Z)
    assert app.scene.edit_object_id == cube.id  # Q-8
    assert app.viewport.mesh is cube.mesh
    assert cube.mesh.export_state() != cube_after
    assert set(app.viewport.object_entries) == {other.id}
    assert app.key_press(CTRL_Y)
    assert app.scene.edit_object_id == cube.id and cube.mesh.export_state() == cube_after
    assert app.key_press(CTRL_Y)
    assert app.scene.edit_object_id == other.id and other.mesh.export_state() == other_after
    assert app.viewport.mesh is other.mesh


def test_undo_restores_the_component_selection_of_that_object():
    app = _app()
    other = _second(app)
    app.key_press(ONE)
    app.selection.vertices = {VertexId(2), VertexId(3)}
    _nudge(app, VertexId(2))
    _switch_to(app, other)
    app.key_press(CTRL_Z)
    assert app.selection.vertices == {VertexId(2), VertexId(3)}
    app.viewport.sync()
    cube_mesh = app.scene.mesh
    assert sorted(app.viewport.point_positions["selected"]) == sorted(
        cube_mesh.vertex_position(v) for v in (VertexId(2), VertexId(3))
    )


def test_undoing_add_and_state_after_a_switch_ends_on_the_first_object():
    app = _app()
    cube = app.scene.edit_object
    other = _second(app)
    _switch_to(app, other)
    app.key_press(CTRL_Z)  # the state switch (made while the cube was edited)
    assert app.scene.edit_object_id == cube.id
    assert other.state is ObjectState.REFERENCE
    app.key_press(CTRL_Z)  # the add
    assert list(app.scene.objects) == [cube.id]
    assert app.viewport.mesh is cube.mesh and app.viewport.object_entries == {}


def test_a_reference_never_becomes_the_edit_object_through_undo():
    """RF-5 in `_restore_selection`: a snapshot naming an object that is a Reference now."""
    app = _app()
    cube = app.scene.edit_object
    other = _second(app)
    snapshot = app._selection_snapshot()[:5] + (other.id,)
    other.state = ObjectState.REFERENCE
    app._restore_selection(snapshot)
    assert app.scene.edit_object_id == cube.id


def test_dispatch_of_a_mode_command_switches_too():
    app = _app()
    other = _second(app)
    app.key_press(FOUR)
    app.selection.objects = {other.id}
    assert app.dispatch_command(commands.SET_FACE_MODE)
    assert app.scene.edit_object_id == other.id and app.selection.mode is SelectionMode.FACE
