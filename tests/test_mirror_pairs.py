"""Object mirror pairs, B1 + B3 (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.1, §5.5, §5.7).

B1 Core: `MirrorPair` (frozen value) and `Scene.mirror_pairs` with its invariants (a != b, both exist,
at most one pair per object, no removal of a paired object), scene file v3 (v2 reads with no pairs).
B3 commands: `MirrorPairCommand`, the mirror copy, pairing two objects, break, re-sync, Delete of a
partner, and `replace_scene` remapping pair ids. Headless (TraceStore), no pyglet.
"""

from __future__ import annotations

import json

import pytest

import tests._bootstrap  # noqa: F401

from core import (
    Mesh,
    MirrorPair,
    ObjectId,
    ObjectState,
    ObjectTransform,
    Scene,
    SceneObject,
    SelectionMode,
    scene_from_dict,
    scene_from_json,
    scene_to_dict,
    scene_to_json,
)
from mirai import object_space
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.object_mirror import PLANES, in_sync, mirror_placement, pair_residual
from mirai.scene_objects import (
    MirrorPairCommand,
    MirrorRefused,
    pair_existing_command,
    replace_scene,
    reset_scene,
)

WIDTH, HEIGHT = 800, 600
X = PLANES["X"][0]


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


FOUR, DELETE = _key("4"), _key("delete")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")
APPLY, CLEAR = _key("a", "ctrl"), _key("a", "alt", "shift")


def _scene_with(n: int) -> tuple[Scene, list[SceneObject]]:
    scene = Scene()
    objs = [scene.edit_object] + [scene.add_object(Mesh(), name=f"o{i}") for i in range(1, n)]
    return scene, objs


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _placed_sphere(app: Application, name: str = "eye.L"):
    """A sphere moved aside and rotated, selected in mode `4`."""
    obj = app.add_primitive("sphere", name=name)
    obj.transform = ObjectTransform(
        translation=(2.0, 1.0, -0.5),
        rotation=object_space.axis_angle_rotation((0.0, 1.0, 0.0), 0.4),
        scale=0.5,
    )
    app._objects.placement_changed()
    return obj


def _mirror_copy(app: Application, name: str = "eye.L"):
    a = _placed_sphere(app, name)
    b = app.mirror_copy("X")
    assert b is not None, app.status_message
    return a, b


def _undo(app: Application) -> None:
    assert app.key_press(CTRL_Z), app.status_message


def _redo(app: Application) -> None:
    assert app.key_press(CTRL_Y), app.status_message


# -- B1: Core data -----------------------------------------------------------------------------


def test_mirror_pair_is_a_validated_frozen_value():
    pair = MirrorPair(ObjectId(1), ObjectId(2), normal=[0.0, 1.0, 0.0], offset=0)
    assert pair.normal == (0.0, 1.0, 0.0) and pair.offset == 0.0
    assert pair.other(ObjectId(1)) == ObjectId(2) and pair.other(ObjectId(2)) == ObjectId(1)
    with pytest.raises(KeyError):
        pair.other(ObjectId(3))
    with pytest.raises(AttributeError):
        pair.a = ObjectId(5)  # type: ignore[misc]
    with pytest.raises(ValueError):
        MirrorPair(ObjectId(1), ObjectId(1))  # self
    with pytest.raises(TypeError):
        MirrorPair(1, ObjectId(2))  # an object id, never a bare int / element id
    with pytest.raises(ValueError):
        MirrorPair(ObjectId(1), ObjectId(2), normal=(1.0, 1.0, 0.0))  # not a unit vector
    with pytest.raises(ValueError):
        MirrorPair(ObjectId(1), ObjectId(2), offset=float("nan"))


def test_scene_pair_api_and_invariants():
    scene, (a, b, c) = _scene_with(3)
    assert scene.mirror_pairs == ()
    pair = MirrorPair(a.id, b.id)
    scene.add_mirror_pair(pair)
    assert scene.mirror_pairs == (pair,)
    assert scene.mirror_pair_of(a.id) is pair and scene.mirror_pair_of(b.id) is pair
    assert scene.mirror_pair_of(c.id) is None
    with pytest.raises(ValueError):
        scene.add_mirror_pair(MirrorPair(b.id, c.id))  # b already paired
    with pytest.raises(ValueError):
        scene.add_mirror_pair(MirrorPair(a.id, b.id))  # duplicate
    with pytest.raises(ValueError):
        scene.add_mirror_pair(MirrorPair(c.id, ObjectId(99)))  # missing object
    with pytest.raises(TypeError):
        scene.add_mirror_pair((c.id, a.id))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        scene.remove_object(b.id)  # a pair never points at a missing object
    scene.remove_mirror_pair(pair)
    with pytest.raises(ValueError):
        scene.remove_mirror_pair(pair)
    scene.remove_object(b.id)
    assert scene.mirror_pairs == ()


def test_file_roundtrip_keeps_pairs_and_ids():
    scene, (a, b, c) = _scene_with(3)
    pair = MirrorPair(a.id, c.id, normal=(0.0, 0.0, 1.0), offset=0.5)
    scene.add_mirror_pair(pair)
    data = scene_to_dict(scene)
    assert data["version"] == 4  # v4 since the object material (AD-024); the pairs place is v3's
    assert data["mirror_pairs"] == [{"a": int(a.id), "b": int(c.id), "normal": [0.0, 0.0, 1.0], "offset": 0.5}]
    restored = scene_from_json(scene_to_json(scene))
    assert restored.mirror_pairs == (pair,)
    # ids are never reused: the counter is above both
    assert restored.add_object(Mesh()).id not in (a.id, b.id, c.id)


def test_v2_file_loads_with_no_pairs():
    scene, _ = _scene_with(2)
    data = scene_to_dict(scene)
    data["version"] = 2
    del data["mirror_pairs"]
    restored = scene_from_dict(data)
    assert restored.mirror_pairs == () and len(restored.objects) == 2
    data["mirror_pairs"] = [{"a": 0, "b": 1, "normal": [1, 0, 0], "offset": 0}]
    assert scene_from_dict(data).mirror_pairs == ()  # v2 has no such place: not read


def test_invalid_pairs_in_a_file_are_refused():
    scene, (a, b) = _scene_with(2)
    data = scene_to_dict(scene)
    data["mirror_pairs"] = [{"a": int(a.id), "b": 42, "normal": [1, 0, 0], "offset": 0}]
    with pytest.raises(ValueError):
        scene_from_dict(data)
    data["mirror_pairs"] = [{"a": int(a.id), "b": int(a.id), "normal": [1, 0, 0], "offset": 0}]
    with pytest.raises(ValueError):
        scene_from_dict(data)


def test_from_objects_takes_pairs():
    objs = [SceneObject(ObjectId(i), Mesh()) for i in range(3)]
    pair = MirrorPair(ObjectId(0), ObjectId(2))
    scene = Scene.from_objects(objs, edit_object_id=ObjectId(0), object_id_counter=3, mirror_pairs=[pair])
    assert scene.mirror_pairs == (pair,)


# -- B3: commands on a bare Scene ----------------------------------------------------------


def test_mirror_pair_command_create_and_break_undo_redo():
    scene, (a, b) = _scene_with(2)
    pair = MirrorPair(a.id, b.id)
    scene.add_mirror_pair(pair)
    scene.history.push(MirrorPairCommand(scene, pair, create=True))
    scene.history.undo()
    assert scene.mirror_pairs == ()
    scene.history.redo()
    assert scene.mirror_pairs == (pair,)
    scene.remove_mirror_pair(pair)
    scene.history.push(MirrorPairCommand(scene, pair, create=False))
    scene.history.undo()
    assert scene.mirror_pairs == (pair,)
    scene.history.redo()
    assert scene.mirror_pairs == ()


def test_pair_existing_places_the_follower_and_is_one_step():
    scene, (a, b) = _scene_with(2)
    a.transform = ObjectTransform(translation=(1.0, 2.0, 3.0), scale=2.0)
    a.pivot = (0.5, 0.0, 0.0)
    b_before = (b.transform, b.pivot)
    scene.history.push(pair_existing_command(scene, a, b, X, 0.0))
    assert b.transform.translation == (-1.0, 2.0, 3.0) and b.transform.scale == 2.0
    assert b.pivot == (-0.5, 0.0, 0.0)
    assert in_sync(a, b, scene.mirror_pairs[0])
    scene.history.undo()
    assert (b.transform, b.pivot) == b_before and scene.mirror_pairs == ()
    scene.history.redo()
    assert in_sync(a, b, scene.mirror_pairs[0])


def test_pair_existing_refusals():
    scene, (a, b, c) = _scene_with(3)
    with pytest.raises(MirrorRefused):
        pair_existing_command(scene, a, a, X, 0.0)
    c.state = ObjectState.REFERENCE
    with pytest.raises(MirrorRefused, match="Reference"):
        pair_existing_command(scene, a, c, X, 0.0)
    pair_existing_command(scene, a, b, X, 0.0)
    c.state = ObjectState.NORMAL
    with pytest.raises(MirrorRefused, match="already belongs to a pair"):
        pair_existing_command(scene, c, b, X, 0.0)


def test_reset_and_replace_scene_drop_the_old_pairs():
    scene, (a, b) = _scene_with(2)
    scene.add_mirror_pair(MirrorPair(a.id, b.id))
    reset_scene(scene, Mesh(), "fresh")
    assert scene.mirror_pairs == () and len(scene.objects) == 1


def test_replace_scene_remaps_pair_ids():
    """`replace_scene` re-allocates ObjectIds; the pair must follow, not point at the file's ids."""
    source, (a, b, c) = _scene_with(3)
    a.transform = ObjectTransform(translation=(1.0, 0.0, 0.0))
    c.transform, c.pivot = mirror_placement(a, X, 0.0)
    source.add_mirror_pair(MirrorPair(a.id, c.id))
    loaded = scene_from_json(scene_to_json(source))

    target, _ = _scene_with(2)
    target.add_mirror_pair(MirrorPair(*target.objects))
    replace_scene(target, loaded)
    (pair,) = target.mirror_pairs
    assert pair.a not in (a.id, c.id) or pair.b not in (a.id, c.id)  # new ids
    pa, pb = target.objects[pair.a], target.objects[pair.b]
    assert (pa.name, pb.name) == (a.name, c.name)
    assert in_sync(pa, pb, pair)


# -- B3: mirror copy in the Application ----------------------------------------------------


def test_mirror_copy_creates_a_mirrored_paired_object_in_one_step():
    app = _app()
    depth = len(app.history)
    a, b = _mirror_copy(app)
    scene = app.scene
    assert b.name == "eye.L.001" and b.state is ObjectState.NORMAL
    assert scene.mirror_pairs == (MirrorPair(a.id, b.id, X, 0.0),)
    assert pair_residual(a, b, scene.mirror_pairs[0]) == 0.0
    assert b.mesh is not a.mesh and b.mesh.symmetry_definition is None
    va, vb = sorted(a.mesh.all_vertex_ids())[5], sorted(b.mesh.all_vertex_ids())[5]
    wa = object_space.to_world(a, a.mesh.vertex_position(va))
    assert object_space.to_world(b, b.mesh.vertex_position(vb)) == (-wa[0], wa[1], wa[2])
    assert app.selection.objects == {b.id} and app.selection.mode is SelectionMode.OBJECT
    assert b.id in app.viewport.object_entries
    assert len(app.history) == depth + 2  # the add of A, then the mirror copy
    assert "eye.L" in app.status_message and "X = 0" in app.status_message


def test_mirror_copy_undo_redo_same_instance_and_id():
    app = _app()
    a, b = _mirror_copy(app)
    _undo(app)
    assert b.id not in app.scene.objects and app.scene.mirror_pairs == ()
    assert app.selection.objects == {a.id}
    assert b.id not in app.viewport.object_entries
    _redo(app)
    assert app.scene.objects[b.id] is b
    assert app.scene.mirror_pairs == (MirrorPair(a.id, b.id, X, 0.0),)
    assert app.selection.objects == {b.id}


def test_mirror_copy_on_each_plane():
    for axis in PLANES:
        app = _app()
        a = _placed_sphere(app)
        b = app.mirror_copy(axis)
        assert b is not None and app.scene.mirror_pairs[0].normal == PLANES[axis][0]
        assert pair_residual(a, b, app.scene.mirror_pairs[0]) == 0.0


def test_mirror_copy_refusals():
    app = _app()
    edit = app.scene.edit_object
    assert app.mirror_copy("X") is None and "press 4" in app.status_message
    app.key_press(FOUR)
    assert app.mirror_copy("X") is None and "no object selected" in app.status_message
    ref = app.add_reference("cube", name="guide")
    app.key_press(FOUR)
    app.selection.objects = {ref.id}
    assert app.mirror_copy("X") is None and "Reference" in app.status_message
    app.selection.objects = {ref.id, edit.id}
    assert app.mirror_copy("X") is None and "select one object" in app.status_message
    a, b = _mirror_copy(app, "x")
    app.selection.objects = {a.id}
    depth = len(app.history)
    assert app.mirror_copy("X") is None and "already belongs to a pair" in app.status_message
    assert len(app.history) == depth
    app.selection.vertices = {sorted(app.scene.mesh.all_vertex_ids())[0]}
    app.selection.objects = {edit.id}
    app.key_press(_key("w"))  # gesture armed
    assert app.mirror_copy("X") is None and "not while" in app.status_message


# -- B3: pair two existing objects, break, re-sync ----------------------------------------------


def test_pair_selected_places_the_higher_id_at_the_mirror_of_the_lower():
    app = _app()
    a = _placed_sphere(app, "eye.L")
    b = app.add_primitive("sphere", name="eye.R")
    b.transform = ObjectTransform(translation=(-3.0, 0.0, 0.0))
    app.selection.objects = {a.id, b.id}
    depth = len(app.history)
    assert app.pair_selected("X"), app.status_message
    assert len(app.history) == depth + 1
    assert in_sync(a, b, app.scene.mirror_pairs[0]) and app.scene.mirror_pairs[0].a == a.id
    assert "'eye.R' is placed at the mirror of 'eye.L'" in app.status_message
    _undo(app)
    assert b.transform.translation == (-3.0, 0.0, 0.0) and app.scene.mirror_pairs == ()
    _redo(app)
    assert in_sync(a, b, app.scene.mirror_pairs[0])


def test_pair_selected_refusals():
    app = _app()
    a, b = _mirror_copy(app)
    c = app.add_primitive("cube", name="c")
    app.selection.objects = {c.id}
    assert not app.pair_selected("X") and "exactly two" in app.status_message
    app.selection.objects = {a.id, b.id}
    assert not app.pair_selected("X") and "already belongs to a pair" in app.status_message
    app.selection.objects = {b.id, c.id}
    assert not app.pair_selected("X") and "already belongs" in app.status_message
    ref = app.add_reference("cube", name="guide")
    app.key_press(FOUR)
    app.selection.objects = {c.id, ref.id}
    assert not app.pair_selected("X") and "Reference" in app.status_message


def test_break_pair_keeps_both_placements_and_undoes():
    app = _app()
    a, b = _mirror_copy(app)
    placements = (a.transform, b.transform)
    assert app.break_mirror_pairs(), app.status_message
    assert app.scene.mirror_pairs == () and (a.transform, b.transform) == placements
    assert "broken" in app.status_message
    assert not app.break_mirror_pairs() and "no selected object is in a mirror pair" in app.status_message
    _undo(app)
    assert app.scene.mirror_pairs == (MirrorPair(a.id, b.id, X, 0.0),)
    _redo(app)
    assert app.scene.mirror_pairs == ()


def test_resync_places_b_at_the_mirror_of_a():
    app = _app()
    a, b = _mirror_copy(app)
    app.selection.objects = {a.id}
    assert not app.resync_mirror_pairs() and "in sync - nothing to do" in app.status_message
    off = ObjectTransform(translation=(-1.0, 0.0, 0.0))
    b.transform = off  # out of sync, e.g. a hand-edited file
    assert app.resync_mirror_pairs(), app.status_message
    assert pair_residual(a, b, app.scene.mirror_pairs[0]) == 0.0
    _undo(app)
    assert b.transform == off
    b.state = ObjectState.REFERENCE
    assert not app.resync_mirror_pairs() and "Reference - locked" in app.status_message
    assert b.transform == off


# -- B3: Delete with a pair --------------------------------------------------------------------


def test_deleting_one_partner_breaks_the_pair_in_the_same_step_and_undo_restores_both():
    app = _app()
    a, b = _mirror_copy(app)
    app.selection.objects = {b.id}
    depth = len(app.history)
    assert app.key_press(DELETE)
    assert len(app.history) == depth + 1
    assert b.id not in app.scene.objects and app.scene.mirror_pairs == ()
    assert "Deleted 'eye.L.001' - mirror pair with 'eye.L' broken" in app.status_message
    _undo(app)
    assert app.scene.objects[b.id] is b
    assert app.scene.mirror_pairs == (MirrorPair(a.id, b.id, X, 0.0),)
    _redo(app)
    assert b.id not in app.scene.objects and app.scene.mirror_pairs == ()


def test_deleting_both_partners_removes_the_pair_with_them():
    app = _app()
    a, b = _mirror_copy(app)
    app.selection.objects = {a.id, b.id}
    assert app.key_press(DELETE)
    assert app.scene.mirror_pairs == () and "removed" in app.status_message
    _undo(app)
    assert len(app.scene.mirror_pairs) == 1 and {a.id, b.id} <= set(app.scene.objects)


# -- save / load ---------------------------------------------------------------------------


def test_save_load_keeps_the_pair_with_new_ids(tmp_path):
    app = _app()
    a, b = _mirror_copy(app)
    path = tmp_path / "pair.mirai.json"
    assert app.save_scene_file(path)
    assert json.loads(path.read_text())["mirror_pairs"]
    other = _app()
    other.init_scene("file", scene_path=path)
    (pair,) = other.scene.mirror_pairs
    pa, pb = other.scene.objects[pair.a], other.scene.objects[pair.b]
    assert (pa.name, pb.name) == ("eye.L", "eye.L.001")
    assert pair_residual(pa, pb, pair) == 0.0


# -- Apply / Clear on a paired object -----------------------------------------------------------


@pytest.mark.parametrize("key", [APPLY, CLEAR])
def test_apply_and_clear_transform_are_refused_on_a_paired_object(key):
    app = _app()
    a, b = _mirror_copy(app)
    app.selection.objects = {a.id}
    depth, placement = len(app.history), a.transform
    app.key_press(key)
    assert len(app.history) == depth and a.transform == placement
    assert "'eye.L' is in a mirror pair - break the pair first" in app.status_message


# -- Shift+M menu entries (src/scene_menu.py) -------------------------------------------------


def test_mirror_menu_entries_run_the_application_commands():
    from scene_menu import mirror_entries, run_mirror_entry

    entries = mirror_entries()
    assert entries[0] == "Mirror copy  X = 0" and "Break pair" in entries and "Re-sync pair" in entries
    app = _app()
    a = _placed_sphere(app)
    assert run_mirror_entry(app, "Mirror copy  Z = 0")
    assert app.scene.mirror_pairs[0].normal == (0.0, 0.0, 1.0)
    assert not run_mirror_entry(app, "Re-sync pair")  # in sync: nothing to do
    assert run_mirror_entry(app, "Break pair") and app.scene.mirror_pairs == ()
    app.selection.objects = {a.id}
    assert not run_mirror_entry(app, "Pair selected  X = 0")  # one object: refused
