"""Object lifecycle in the production `Application` (Track A, 2026-10-23): Add Mesh primitives and
object deletion in mode `4`.

Headless (TraceStore), no pyglet. A1: `Application.add_primitive` - a Normal object at the origin,
the sole object selection, mode `4`, the edit object untouched, one Undo step. A2: `Delete` in `4` -
`_delete_objects_command`, separate from the component Delete/Dissolve; the edit object moves to a
surviving Normal object, the last object / "only References left" is refused, Undo/Redo bring the
same instances (same ids), the selection and the edit object back. The command classes
(`AddObjectCommand` with an edit-object transition, `DeleteObjectsCommand`, `plan_object_delete`)
are tested on a bare `Scene`, too.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import (
    Mesh,
    ObjectId,
    ObjectState,
    ObjectTransform,
    Scene,
    SelectionMode,
    scene_from_json,
    scene_to_json,
)
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.scene_factory import PRIMITIVES, create_cube, primitive_names
from mirai.scene_objects import (
    AddObjectCommand,
    DeleteObjectsCommand,
    DeleteRefused,
    plan_object_delete,
    unique_object_name,
)

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


ONE, FOUR = _key("1"), _key("4")
W, DELETE, BACKSPACE = _key("w"), _key("delete"), _key("backspace")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _click(app: Application, x: float, y: float, *modifiers: str) -> None:
    app.pointer_press(Input("mouse", "LEFT", frozenset(modifiers)), x, y)
    app.pointer_release("LEFT", x, y)


def _undo(app: Application) -> None:
    assert app.key_press(CTRL_Z)


def _redo(app: Application) -> None:
    assert app.key_press(CTRL_Y)


def _select(app: Application, *objects) -> None:
    """Object mode with exactly these objects selected (the click path is tested separately)."""
    app.key_press(FOUR)
    app.selection.objects = {obj.id for obj in objects}


def _extra(app: Application, kind: str = "sphere", name: str | None = None):
    """A primitive added and then deselected - the starting point of most delete tests."""
    obj = app.add_primitive(kind, name=name)
    app.selection.objects = set()
    return obj


def _assert_views_match_scene(app: Application) -> None:
    """The viewport, the pick caches and the highlight follow the scene (A2: stale state)."""
    scene, viewport = app.scene, app.viewport
    others = {oid for oid in scene.objects if oid != scene.edit_object_id}
    assert viewport.mesh is scene.mesh
    assert set(viewport.object_entries) == others
    assert set(app._objects.pick_caches) <= others
    assert set(app._objects.cameras) <= set(scene.objects)
    assert app.selection.objects <= set(scene.objects)
    assert app._objects.highlighted() <= set(scene.objects)
    hovered = app.selection.hovered
    assert not isinstance(hovered, ObjectId) or hovered in scene.objects


# -- A1: Add Mesh -----------------------------------------------------------------------------


@pytest.mark.parametrize("kind", primitive_names())
def test_add_primitive_makes_a_selected_normal_object(kind):
    app = _app()
    edit_id, depth = app.scene.edit_object_id, len(app.history)

    obj = app.add_primitive(kind)

    assert obj is not None and obj.id in app.scene.objects
    assert obj.state is ObjectState.NORMAL  # not a Reference
    assert len(obj.mesh.all_vertex_ids()) == len(PRIMITIVES[kind]().all_vertex_ids())
    assert obj.id != edit_id and app.scene.edit_object_id == edit_id  # the edit object stays
    assert app.selection.mode is SelectionMode.OBJECT
    assert app.selection.objects == {obj.id}
    assert obj.id in app._objects.highlighted()  # visibly selected (tint)
    assert obj.id in app.viewport.object_entries
    assert len(app.history) == depth + 1  # one logical step
    assert obj.name.startswith(kind) and f"Added {obj.name!r}" in app.status_message
    _assert_views_match_scene(app)


def test_add_primitive_rejects_unknown_kinds_and_a_running_gesture():
    app = _app()
    with pytest.raises(ValueError):
        app.add_primitive("teapot")
    _select(app, app.scene.edit_object)
    app.key_press(W)  # armed: the object gesture owns the keys
    assert app.interaction_owner == "transform"
    depth = len(app.history)
    assert app.add_primitive("sphere") is None
    assert "not while the transform interaction runs" in app.status_message
    assert len(app.history) == depth and len(app.scene.objects) == 1


def test_new_objects_get_unique_names():
    app = _app()
    first = app.add_primitive("cube")
    second = app.add_primitive("cube")
    sphere = app.add_primitive("sphere")
    assert [o.name for o in (app.scene.edit_object, first, second, sphere)] == [
        "cube", "cube.001", "cube.002", "sphere",
    ]
    assert unique_object_name(app.scene, "cube") == "cube.003"


def test_add_from_a_component_mode_enters_object_mode_and_undo_restores_the_selection():
    app = _app()
    app.key_press(ONE)
    app.selection.vertices = {sorted(app.scene.mesh.all_vertex_ids())[0]}
    vertices = set(app.selection.vertices)

    obj = app.add_primitive("sphere")

    assert app.selection.mode is SelectionMode.OBJECT
    assert app.selection.vertices == set()  # component ids belong to the edit mesh, mode 4 shows none
    _undo(app)
    assert obj.id not in app.scene.objects
    assert app.selection.mode is SelectionMode.VERTEX
    assert app.selection.vertices == vertices
    assert app.selection.objects == set()
    _assert_views_match_scene(app)
    _redo(app)
    assert app.selection.mode is SelectionMode.OBJECT and app.selection.objects == {obj.id}
    _assert_views_match_scene(app)


def test_add_undo_redo_keeps_the_same_instance_and_id_and_never_reuses_it():
    app = _app()
    obj = app.add_primitive("cylinder")
    mesh, oid = obj.mesh, obj.id
    _undo(app)
    assert oid not in app.scene.objects and oid not in app.viewport.object_entries
    _redo(app)
    assert app.scene.objects[oid] is obj and obj.mesh is mesh
    _undo(app)
    other = app.add_primitive("plane")  # a new add after Undo gets a fresh id (AD-001)
    assert int(other.id) > int(oid)
    _assert_views_match_scene(app)


def test_the_new_object_is_usable_in_the_object_workflow():
    """Placed with W in `4`, then edited with 1 (Q-5), component Delete unchanged on its mesh."""
    app = _app()
    obj = app.add_primitive("sphere")
    # object level: W moves the selected sphere (one Undo step on top of the add)
    app.key_press(W)
    app.pointer_motion(400.0, 300.0, 0.0, 0.0)
    app.pointer_motion(450.0, 300.0, 50.0, 0.0)
    app.key_release(W)
    assert obj.transform.translation != (0.0, 0.0, 0.0)
    assert app.scene.edit_object_id != obj.id  # moving it does not make it the edit object
    # component level: 1 makes it the edit object, the cube becomes an object entry
    app.key_press(ONE)
    assert app.scene.edit_object_id == obj.id and app.scene.mesh is obj.mesh
    _assert_views_match_scene(app)
    faces_before = len(obj.mesh.all_face_ids())
    app.selection.faces = set()
    app.key_press(_key("3"))
    app.selection.faces = {sorted(obj.mesh.all_face_ids())[0]}
    assert app.key_press(DELETE)  # the component Delete, unchanged outside mode 4
    assert len(obj.mesh.all_face_ids()) == faces_before - 1
    assert obj.id in app.scene.objects


def test_undo_of_an_add_whose_object_became_the_edit_object():
    """Add, `4`/click/`1` (the new object is the edit object, no history step), Undo: the add is
    taken back, the edit role returns to the object that had it, the view follows - a bare
    `Scene.remove_object` would refuse the edit object."""
    app = _app()
    cube = app.scene.edit_object
    obj = app.add_primitive("sphere")
    app.key_press(ONE)  # Q-5: the one selected Normal object becomes the edit object
    assert app.scene.edit_object_id == obj.id

    _undo(app)

    assert obj.id not in app.scene.objects
    assert app.scene.edit_object_id == cube.id and app.scene.mesh is cube.mesh
    assert app.selection.mode is SelectionMode.VERTEX  # the mode before the add
    _assert_views_match_scene(app)
    _redo(app)
    assert obj.id in app.scene.objects
    assert app.selection.mode is SelectionMode.OBJECT and app.selection.objects == {obj.id}
    _assert_views_match_scene(app)


def test_add_command_with_an_edit_switch_undoes_and_redoes_the_state_change():
    """`AddObjectCommand` on a bare Scene when the add itself made the new object the edit object."""
    scene = Scene()
    first = scene.edit_object
    obj = scene.add_object(create_cube(), name="new")
    scene.edit_object_id = obj.id  # the add also switches the edit object
    command = AddObjectCommand(scene, obj, edit_before=first.id)
    scene.history.push(command)

    scene.history.undo()
    assert obj.id not in scene.objects and scene.edit_object_id == first.id
    scene.history.redo()
    assert scene.objects[obj.id] is obj and scene.edit_object_id == obj.id

    # an add that leaves the edit object alone must not touch it on Redo
    plain = scene.add_object(create_cube(), name="plain")
    scene.history.push(AddObjectCommand(scene, plain))
    scene.history.undo()
    scene.history.redo()
    assert scene.edit_object_id == obj.id
    with pytest.raises(ValueError):
        AddObjectCommand(scene, obj, edit_before=obj.id)


def test_primitive_survives_a_scene_file_roundtrip():
    app = _app()
    sphere = app.add_primitive("sphere", name="eye")
    sphere.transform = ObjectTransform(translation=(-2.0, 0.0, 0.0))
    loaded = scene_from_json(scene_to_json(app.scene))
    twin = next(o for o in loaded.objects.values() if o.name == "eye")
    assert twin.state is ObjectState.NORMAL
    assert twin.transform == sphere.transform
    assert len(twin.mesh.all_vertex_ids()) == len(sphere.mesh.all_vertex_ids())
    assert len(twin.mesh.all_face_ids()) == len(sphere.mesh.all_face_ids())


# -- A2: delete objects ------------------------------------------------------------------------


def test_delete_removes_the_selected_object_and_cleans_every_dependent_state():
    app = _app()
    sphere = _extra(app)
    app._objects.pick(WIDTH / 2, HEIGHT / 2)  # populates the per-object pick caches
    assert sphere.id in app._objects.pick_caches
    _select(app, sphere)
    app.selection.hovered = sphere.id
    depth = len(app.history)

    assert app.key_press(DELETE)

    assert sphere.id not in app.scene.objects
    assert app.selection.objects == set() and app.selection.hovered is None
    assert sphere.id not in app._objects.pick_caches
    assert len(app.history) == depth + 1
    assert app.status_message == "Deleted 'sphere'"
    assert app.scene.edit_object_id == app.scene.edit_object.id
    _assert_views_match_scene(app)


def test_delete_undo_redo_brings_back_the_same_instance_selection_and_mode():
    app = _app()
    app.key_press(ONE)
    sphere = _extra(app)
    mesh, oid = sphere.mesh, sphere.id
    sphere.transform = ObjectTransform(translation=(2.0, 0.0, 0.0))
    _select(app, sphere)

    app.key_press(DELETE)
    _undo(app)

    assert app.scene.objects[oid] is sphere and sphere.mesh is mesh
    assert sphere.transform.translation == (2.0, 0.0, 0.0)
    assert app.selection.objects == {oid} and app.selection.mode is SelectionMode.OBJECT
    assert oid in app.viewport.object_entries and oid in app._objects.highlighted()
    _assert_views_match_scene(app)
    _redo(app)
    assert oid not in app.scene.objects and app.selection.objects == set()
    _assert_views_match_scene(app)
    # ids run on: the deleted id is never handed out again
    assert int(app.add_primitive("cube").id) > int(oid)


def test_delete_several_objects_is_one_undo_step():
    app = _app()
    a, b, c = _extra(app, "sphere"), _extra(app, "cube"), _extra(app, "cylinder")
    _select(app, a, c)
    depth = len(app.history)

    app.key_press(DELETE)

    assert set(app.scene.objects) == {app.scene.edit_object_id, b.id}
    assert len(app.history) == depth + 1
    assert app.status_message == "Deleted 'sphere', 'cylinder'"
    _undo(app)
    assert set(app.scene.objects) == {app.scene.edit_object_id, a.id, b.id, c.id}
    assert app.selection.objects == {a.id, c.id}
    assert list(app.scene.objects) == sorted(app.scene.objects)  # creation order restored
    _assert_views_match_scene(app)
    _redo(app)
    assert set(app.scene.objects) == {app.scene.edit_object_id, b.id}
    _assert_views_match_scene(app)


def test_delete_a_reference_and_bring_it_back():
    app = _app()
    ref = app.add_reference("cube", name="guide")
    ref.transform = ObjectTransform(translation=(5.0, 0.0, 0.0))
    _select(app, ref)

    app.key_press(DELETE)
    assert ref.id not in app.scene.objects
    _assert_views_match_scene(app)
    _undo(app)
    assert app.scene.objects[ref.id] is ref and ref.state is ObjectState.REFERENCE
    assert ref.transform.translation == (5.0, 0.0, 0.0)
    assert app.selection.objects == {ref.id}
    _assert_views_match_scene(app)
    _redo(app)
    assert ref.id not in app.scene.objects


def test_delete_the_edit_object_hands_the_edit_role_to_a_surviving_normal_object():
    app = _app()
    cube = app.scene.edit_object
    sphere = _extra(app)
    app.key_press(ONE)
    app.selection.vertices = {sorted(cube.mesh.all_vertex_ids())[0]}
    _select(app, cube)

    assert app.key_press(DELETE)

    assert cube.id not in app.scene.objects
    assert app.scene.edit_object_id == sphere.id
    assert app.viewport.mesh is sphere.mesh  # the overlay entry moved with the edit object
    assert sphere.id not in app.viewport.object_entries
    assert app.selection.vertices == set() and app.selection.objects == set()
    assert app.status_message == "Deleted 'cube' - now editing 'sphere'"
    _assert_views_match_scene(app)

    _undo(app)
    assert app.scene.edit_object_id == cube.id and app.scene.mesh is cube.mesh
    assert app.viewport.mesh is cube.mesh and sphere.id in app.viewport.object_entries
    assert app.selection.objects == {cube.id}
    _assert_views_match_scene(app)
    _redo(app)
    assert app.scene.edit_object_id == sphere.id and app.viewport.mesh is sphere.mesh
    _assert_views_match_scene(app)
    # the survivor is a normal edit object again: component work runs on it
    app.key_press(ONE)
    assert app.scene.mesh is sphere.mesh


def test_deleting_the_edit_object_undoes_in_order_with_its_mesh_edits():
    """A mesh step on the edit object, then its deletion: Undo twice restores object and edit."""
    app = _app()
    cube = app.scene.edit_object
    mesh = cube.mesh
    vid = sorted(mesh.all_vertex_ids())[0]
    before = mesh.vertex_position(vid)

    def bump():
        x, y, z = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (x + 0.5, y, z))
        return {vid}

    assert app.apply_mesh_change("nudge", bump)
    sphere = _extra(app)
    _select(app, cube)
    app.key_press(DELETE)
    assert app.scene.edit_object_id == sphere.id
    _undo(app)
    assert app.scene.mesh is mesh and mesh.vertex_position(vid) != before
    _undo(app)  # the add of the sphere: the edit role is on the cube already
    assert sphere.id not in app.scene.objects
    _undo(app)
    assert mesh.vertex_position(vid) == before
    _assert_views_match_scene(app)


def test_the_replacement_edit_object_is_the_nearest_normal_one_never_a_reference():
    app = _app()
    cube = app.scene.edit_object  # id 0
    ref = app.add_reference("cube", name="guide")  # id 1
    far = _extra(app, "sphere")  # id 2
    near = _extra(app, "cylinder")  # id 3
    scene = app.scene
    assert plan_object_delete(scene, {cube.id}) == ([cube], far.id)  # the Reference (id 1) is skipped
    assert plan_object_delete(scene, {cube.id, far.id}) == ([cube, far], near.id)
    _select(app, cube, far)
    app.key_press(DELETE)
    assert app.scene.edit_object_id == near.id and ref.id in app.scene.objects
    _assert_views_match_scene(app)


def test_the_last_object_is_refused_and_nothing_changes():
    app = _app()
    cube = app.scene.edit_object
    _select(app, cube)
    depth = len(app.history)
    state = cube.mesh.export_state()

    assert app.key_press(DELETE) is False

    assert "at least one object" in app.status_message
    assert app.scene.objects[cube.id] is cube and app.scene.edit_object_id == cube.id
    assert len(app.history) == depth and cube.mesh.export_state() == state
    assert app.selection.objects == {cube.id}  # the selection is left as it was
    _assert_views_match_scene(app)


def test_only_references_left_is_refused_but_deleting_around_the_edit_object_is_fine():
    app = _app()
    cube = app.scene.edit_object
    ref_a = app.add_reference("cube", name="guide_a")
    ref_b = app.add_reference("cube", name="guide_b")
    _select(app, cube)
    assert app.key_press(DELETE) is False
    assert "only References would remain" in app.status_message
    assert cube.id in app.scene.objects

    _select(app, ref_a, ref_b)  # everything but the edit object may go
    assert app.key_press(DELETE)
    assert set(app.scene.objects) == {cube.id}
    _undo(app)
    assert set(app.scene.objects) == {cube.id, ref_a.id, ref_b.id}
    _assert_views_match_scene(app)


def test_delete_with_nothing_selected_does_nothing():
    app = _app()
    app.key_press(FOUR)
    depth = len(app.history)
    assert app.key_press(DELETE) is False
    assert "no object selected" in app.status_message
    assert len(app.history) == depth and len(app.scene.objects) == 1


def test_delete_is_refused_while_a_gesture_runs():
    app = _app()
    sphere = _extra(app)
    _select(app, sphere)
    app.key_press(W)  # armed
    depth = len(app.history)
    assert app.dispatch_command(commands.DELETE) is False
    assert sphere.id in app.scene.objects and len(app.history) == depth


def test_a_click_selection_then_delete_works_end_to_end():
    app = _app()
    sphere = app.add_primitive("sphere")
    sphere.transform = ObjectTransform(translation=(3.0, 0.0, 0.0))
    app._objects.placement_changed()
    x, y = app.camera.project_to_screen((3.0, 0.0, 0.0), WIDTH, HEIGHT)
    app.selection.objects = set()
    _click(app, x, y)
    assert app.selection.objects == {sphere.id}
    app.key_press(DELETE)
    assert sphere.id not in app.scene.objects
    _assert_views_match_scene(app)


# -- Component Delete/Dissolve stays what it was ----------------------------------------------


def test_backspace_has_no_object_meaning_and_stays_refused_in_mode_4():
    app = _app()
    sphere = _extra(app)
    _select(app, sphere)
    assert app.key_press(BACKSPACE) is False
    assert "work on points/edges/faces" in app.status_message
    assert sphere.id in app.scene.objects


@pytest.mark.parametrize("mode_key", ["1", "2", "3"])
def test_component_delete_outside_mode_4_leaves_the_objects_alone(mode_key):
    app = _app()
    sphere = _extra(app)
    cube = app.scene.edit_object
    app.key_press(_key(mode_key))
    mesh = cube.mesh
    sets = {"1": "vertices", "2": "edges", "3": "faces"}
    ids = {
        "1": sorted(mesh.all_vertex_ids()),
        "2": sorted(mesh.all_edge_ids()),
        "3": sorted(mesh.all_face_ids()),
    }[mode_key]
    setattr(app.selection, sets[mode_key], {ids[0]})
    faces = len(mesh.all_face_ids())

    assert app.key_press(DELETE)

    assert len(mesh.all_face_ids()) < faces  # the component Delete ran on the edit mesh
    assert set(app.scene.objects) == {cube.id, sphere.id}  # no object was deleted
    assert app.scene.edit_object_id == cube.id


def test_delete_objects_command_is_pure_scene_state_and_redo_switches_the_edit_object_first():
    scene = Scene()
    first = scene.edit_object
    second = scene.add_object(create_cube(), name="second")
    command = DeleteObjectsCommand(scene, [first], edit_before=first.id, edit_after=second.id)
    scene.edit_object_id = second.id
    scene.remove_object(first.id)
    scene.history.push(command)

    scene.history.undo()
    assert scene.objects[first.id] is first and scene.edit_object_id == first.id
    scene.history.redo()  # first is the edit object again - Redo must move the role before removing
    assert first.id not in scene.objects and scene.edit_object_id == second.id


def test_plan_object_delete_refusals():
    scene = Scene()
    only = scene.edit_object
    with pytest.raises(DeleteRefused, match="at least one object"):
        plan_object_delete(scene, {only.id})
    ref = scene.add_object(Mesh(), name="r", state=ObjectState.REFERENCE)
    with pytest.raises(DeleteRefused, match="only References"):
        plan_object_delete(scene, {only.id})
    assert plan_object_delete(scene, {ref.id}) == ([ref], only.id)
    assert plan_object_delete(scene, set()) == ([], only.id)
