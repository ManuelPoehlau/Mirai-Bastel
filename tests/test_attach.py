"""AD-031 P2: Attach through `Application` (§15) - one Undo step over the mesh and the objects, every refusal of
§15.3 changing nothing, the D1 variant, the O-5 refusal and override (and O-5b), O-7, D4 (PARTIAL reported, new and
worsened AMBIGUOUS refused), D3, D11 (the dial state of undone carried targets), mirror pairs, group leaves, skinning
invariance under a pose and save / load. Headless (`Application` with its trace viewport)."""

from __future__ import annotations

import random

import pytest

import tests._bootstrap  # noqa: F401
from core import FaceRegion, FaceRegions, LayerKind, ObjectState, ObjectTransform, PointLayerInfo, SelectionMode
from mirai import object_space, skinning
from mirai.application import Application
from mirai.attach import OVERRIDE_LABEL
from mirai.interaction import commands
from mirai.mesh_assembly import NAME_SEPARATOR as SEP, extract_faces
from mirai.object_space import axis_angle_rotation
from mirai.scene_factory import create_cube
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_axis import definition_for_axis
from tests.mesh_invariants import assert_layer_invariants, assert_mesh_invariants
from tests.test_skinning import _random_pose, _rig

PLACED = ObjectTransform(
    translation=(3.0, 0.5, -1.0), rotation=axis_angle_rotation((0.0, 1.0, 0.0), 0.7), scale=0.6
)


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _part(app: Application, name: str, transform: ObjectTransform | None = None, mesh=None):
    """A Normal object beside the edit cube (no Undo step: test setup)."""
    obj = app.scene.add_object(mesh if mesh is not None else create_cube(0.5), name=name)
    obj.transform = transform if transform is not None else ObjectTransform(translation=(3.0, 0.0, 0.0))
    app._objects.sync_views()
    return obj


def _select(app: Application, *objects) -> None:
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.selection.objects = {obj.id for obj in objects}


def _body(mesh) -> dict:
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}


def _world(obj) -> list:
    return sorted(object_space.to_world(obj, obj.mesh.vertex_position(v)) for v in obj.mesh.all_vertex_ids())


def _snapshot(app: Application) -> tuple:
    scene = app.scene
    return (
        _body(scene.mesh), sorted(int(i) for i in scene.objects), tuple(scene.mirror_pairs), len(app.history),
        frozenset(app.selection.objects), app.selection.mode, scene.edit_object_id,
    )


def _with_target(mesh, name: str, seed: int = 1):
    rng = random.Random(seed)
    lid = mesh.add_point_layer(PointLayerInfo(name))
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(lid, v, tuple(rng.uniform(-0.2, 0.2) for _ in range(3)))
    return lid


def _bind(mesh, bone) -> None:
    """A weights layer with every point fully on `bone` (AD-028: keys are the rig's BoneIds)."""
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(lid, v, ((int(bone), 1.0),))


def _rigged_app() -> tuple[Application, object]:
    """The edit cube bound to a rig at rest (AD-028 §7.1 "bound")."""
    app = _app()
    rig = _rig()
    app.scene.rig = rig
    bone = rig.bone_ids()[0]
    _bind(app.scene.mesh, bone)
    return app, bone


# -- the step ------------------------------------------------------------------------------------------------------


def test_attach_is_one_step_and_undo_redo_are_exact():
    app = _app()
    dst = app.scene.edit_object
    a = _part(app, "Ear", PLACED)
    _with_target(a.mesh, "Wiggle")
    a.mesh.face_regions = FaceRegions((FaceRegion("Lobe", frozenset(sorted(a.mesh.all_face_ids())[:2])),))
    b = _part(app, "Horn", ObjectTransform(translation=(-3.0, 1.0, 0.0)))
    worlds = _world(a) + _world(b) + _world(dst)
    _select(app, a, b)
    before, a_state, b_state = _snapshot(app), a.mesh.export_state(), b.mesh.export_state()
    history = len(app.history)

    assert app.dispatch_command(commands.ATTACH), app.status_message

    assert len(app.history) == history + 1
    assert a.id not in app.scene.objects and b.id not in app.scene.objects
    assert app.scene.edit_object is dst and app.selection.objects == {dst.id}
    assert app.selection.mode is SelectionMode.OBJECT
    assert app.status_message.startswith("Attached 'Ear', 'Horn' to")
    for p, q in zip(sorted(worlds), _world(dst)):  # the world shape of every part is kept
        assert p == pytest.approx(q, abs=1e-12)
    names = [r.name for r in dst.mesh.face_regions.regions]
    assert names == ["Lobe", "Ear", "Horn"]  # carried region, then O-7 for the ungrouped faces (§3.3 order)
    assert [dst.mesh.point_layer_info(lid).name for lid in dst.mesh.point_layer_ids()] == [f"Ear{SEP}Wiggle"]
    assert a.id not in app.viewport.object_entries and b.id not in app.viewport.object_entries
    assert_mesh_invariants(dst.mesh)
    assert_layer_invariants(dst.mesh)
    after = dst.mesh.export_state()

    assert app.dispatch_command(commands.UNDO)
    assert _snapshot(app) == before
    assert app.scene.objects[a.id] is a and app.scene.objects[b.id] is b  # the same instances
    assert a.mesh.export_state() == a_state and b.mesh.export_state() == b_state
    assert a.id in app.viewport.object_entries

    assert app.dispatch_command(commands.REDO)
    assert dst.mesh.export_state() == after
    assert a.id not in app.scene.objects and app.selection.objects == {dst.id}


def test_a_source_without_mesh_data_is_removed_in_one_step():
    """An empty mesh changes nothing in the destination: the step holds only the object removal, and the selection
    still ends on the destination."""
    from core import Mesh

    app = _app()
    empty = _part(app, "Empty", mesh=Mesh())
    _select(app, empty)
    history, mesh = len(app.history), _body(app.scene.mesh)
    assert app.attach_objects(), app.status_message
    assert empty.id not in app.scene.objects and app.selection.objects == {app.scene.edit_object_id}
    assert len(app.history) == history + 1 and _body(app.scene.mesh) == mesh
    app.dispatch_command(commands.UNDO)
    assert app.scene.objects[empty.id] is empty


def test_attach_objects_is_the_same_command():
    app = _app()
    part = _part(app, "Part")
    _select(app, part)
    assert app.attach_objects()
    assert part.id not in app.scene.objects


# -- refusals: nothing changes ---------------------------------------------------------------------------------------


def _refusal_case(app: Application, case: str):
    dst = app.scene.edit_object
    part = _part(app, "Part")
    _select(app, part)
    if case == "component mode":
        app.dispatch_command(commands.SET_FACE_MODE)
    elif case == "no source":
        app.selection.objects = {dst.id}
    elif case == "reference":
        part.state = ObjectState.REFERENCE
    elif case == "dial on the destination":
        lid = app.create_morph_target("Smile")
        assert app.set_morph_weight(40, lid)
    elif case == "dial on a source":
        lid = _with_target(part.mesh, "Wiggle")
        app._morph.display.provider.set_weight(part.id, 30, lid)
    elif case == "look":
        part.texture = "skin.png"
    elif case == "two weights layers":
        part.mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
        part.mesh.add_point_layer(PointLayerInfo("Skin B", LayerKind.WEIGHTS))
    elif case == "editing view":
        app.dispatch_command(commands.SET_FACE_MODE)
        assert app.create_morph_target("Smile") is not None, app.status_message
        assert app.edit_morph_target(), app.status_message
        app.selection.mode = SelectionMode.OBJECT
        app.selection.objects = {part.id}
    return part


@pytest.mark.parametrize("case, text", [
    ("component mode", "press 4"),
    ("no source", "none selected"),
    ("reference", "is a Reference"),
    ("dial on the destination", "dialled in"),
    ("dial on a source", "dialled in"),
    ("look", "another texture"),
    ("two weights layers", "more than one weights layer"),
    ("editing view", "on the base only"),
])
def test_a_refusal_changes_nothing(case, text):
    app = _app()
    part = _refusal_case(app, case)
    before, state = _snapshot(app), part.mesh.export_state()
    assert app.dispatch_command(commands.ATTACH) is False
    assert _snapshot(app) == before
    assert app.attach_objects() is False
    assert text in app.status_message and app.status_message.startswith("Attach")
    assert _snapshot(app) == before and part.mesh.export_state() == state
    assert app.attach_plan().refusal is not None


def test_posed_rig_with_a_bound_mesh_is_refused():
    app, bone = _rigged_app()
    part = _part(app, "Part")
    _select(app, part)
    app._skeleton.set_pose(_random_pose(random.Random(3), app.scene.rig, share=1.0))
    assert app.posed
    before = _snapshot(app)
    assert app.attach_objects() is False
    assert "is posed" in app.status_message and _snapshot(app) == before
    app._skeleton.set_pose({})
    assert app.attach_objects(accept_unweighted=True), app.status_message


# -- D1: look --------------------------------------------------------------------------------------------------------


def test_take_destination_look_attaches_and_undo_restores_the_source_look():
    app = _app()
    part = _part(app, "Part")
    part.texture = "skin.png"
    _select(app, part)
    assert app.dispatch_command(commands.ATTACH) is False and "another texture" in app.status_message
    assert app.dispatch_command(commands.ATTACH_TAKE_LOOK), app.status_message
    assert "took" in app.status_message and "'Part' (texture)" in app.status_message
    assert app.scene.edit_object.texture is None  # the destination's look is unchanged
    app.dispatch_command(commands.UNDO)
    assert app.scene.objects[part.id] is part and part.texture == "skin.png"


# -- O-5: unweighted geometry into a bound mesh ----------------------------------------------------------------------


def test_unweighted_geometry_into_a_bound_mesh_is_refused_with_the_count_and_the_override_attaches_it():
    app, bone = _rigged_app()
    dst = app.scene.edit_object
    skin = skinning.skin_layer(dst.mesh)
    own = dst.mesh.layer_items(skin)
    part = _part(app, "Part")
    count = len(part.mesh.all_vertex_ids())
    _select(app, part)
    plan = app.attach_plan()
    assert plan.override_only and plan.needs_override and plan.unweighted == count
    before = _snapshot(app)
    assert app.dispatch_command(commands.ATTACH) is False
    assert f"{count} point(s) without skin weights" in app.status_message and OVERRIDE_LABEL in app.status_message
    assert _snapshot(app) == before

    assert app.attach_objects(accept_unweighted=True), app.status_message
    assert f"{count} point(s) without skin weights" in app.status_message
    assert dst.mesh.layer_items(skin) == own  # no weights made, the destination's unchanged
    assert [lid for lid in dst.mesh.point_layer_ids()] == [skin]


def test_weighted_geometry_needs_no_override_and_follows_the_rig_like_before():
    app, bone = _rigged_app()
    dst = app.scene.edit_object
    dst.transform = ObjectTransform(translation=(0.2, -0.1, 0.4), rotation=axis_angle_rotation((0, 1, 0), 0.3))
    rig = app.scene.rig
    part_mesh = create_cube(0.5)
    jaw = rig.bone_ids()[1]
    skin = part_mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for i, v in enumerate(sorted(part_mesh.all_vertex_ids())):
        part_mesh.set_layer_value(skin, v, ((int(bone), 0.25), (int(jaw), 0.5)) if i % 2 else ((int(jaw), 1.0),))
    part = _part(app, "Part", PLACED, part_mesh)
    pose = _random_pose(random.Random(11), rig, share=1.0)
    expected = sorted(
        object_space.to_world(part, p)
        for p in skinning.evaluate(part_mesh, None, rig, pose, skinning.placement_of(part)).values()
    )
    _select(app, part)
    plan = app.attach_plan()
    assert plan.refusal is None and plan.unweighted == 0
    vertices = set(dst.mesh.all_vertex_ids())
    assert app.attach_objects(), app.status_message
    new = set(dst.mesh.all_vertex_ids()) - vertices
    posed = skinning.evaluate(dst.mesh, None, rig, pose, skinning.placement_of(dst))
    got = sorted(object_space.to_world(dst, posed[v]) for v in new)
    for g, e in zip(got, expected):
        assert g == pytest.approx(e, abs=1e-9)  # skinning is placement-invariant (AD-028 §3.2)


def test_an_unbound_destination_gets_the_skin_layer_without_a_prompt_o5b():
    """O-5b (open): the destination was not bound before, so the O-5 refusal does not apply (the decided §3.2 rule
    creates the skin layer); the status line states the unweighted count."""
    app = _app()
    app.scene.rig = _rig()
    bone = app.scene.rig.bone_ids()[0]
    weighted = create_cube(0.5)
    _bind(weighted, bone)
    a = _part(app, "Bound", mesh=weighted)
    b = _part(app, "Plain", ObjectTransform(translation=(-3.0, 0.0, 0.0)))
    _select(app, a, b)
    assert app.attach_plan().refusal is None
    assert app.attach_objects(), app.status_message
    assert f"{len(b.mesh.all_vertex_ids())} point(s) without skin weights" in app.status_message
    assert skinning.skin_layer(app.scene.mesh) is not None


# -- D4: symmetry ----------------------------------------------------------------------------------------------------


def _symmetric_app() -> Application:
    app = _app()
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    assert symmetry_state(mesh) is SymmetryState.VALID
    return app


def test_a_one_sided_part_is_attached_and_reported_partial():
    app = _symmetric_app()
    part = _part(app, "Part")  # at x = 3: no partner on the other side
    _select(app, part)
    assert app.attach_objects(), app.status_message
    assert "symmetry partial" in app.status_message
    assert app.scene.mesh.symmetry_definition is not None


def test_a_part_that_would_make_the_symmetry_ambiguous_is_refused_and_rolled_back():
    app = _symmetric_app()
    mesh = app.scene.mesh
    twin = _part(app, "Twin", ObjectTransform(), extract_faces(mesh, mesh.all_face_ids()).mesh)  # on top: coincident
    _select(app, twin)
    before = _snapshot(app)
    assert app.attach_objects() is False
    assert "ambiguous" in app.status_message and _snapshot(app) == before
    assert app.scene.objects[twin.id] is twin


# -- D11: dial state of carried targets ------------------------------------------------------------------------------


def test_undo_drops_the_dial_of_a_carried_target_and_redo_shows_it_at_zero():
    app = _app()
    dst = app.scene.edit_object
    part = _part(app, "Ear", PLACED)
    _with_target(part.mesh, "Wiggle")
    _select(app, part)
    assert app.attach_objects(), app.status_message
    rows = app.morph_target_rows()
    assert [(name, weight) for _, name, weight, _ in rows] == [(f"Ear{SEP}Wiggle", 0)]  # listed at once, 0 %
    lid = rows[0][0]
    assert app.set_morph_weight(40, lid)
    provider = app._morph.display.provider
    assert provider.weight(dst.id, lid) == 40
    app.dispatch_command(commands.UNDO)
    assert lid not in provider.weights.get(dst.id, {})
    app.dispatch_command(commands.REDO)
    assert provider.weight(dst.id, lid) == 0


def test_another_operation_keeps_its_hidden_dial_across_undo_redo_f13():
    app = _app()
    lid = app.create_morph_target("Smile")
    assert lid is not None and app.set_morph_weight(30, lid)
    app.dispatch_command(commands.UNDO)
    app.dispatch_command(commands.REDO)
    assert app._morph.display.provider.weight(app.scene.edit_object_id, lid) == 30  # unchanged behaviour (F13)


# -- objects: pairs, groups, file ------------------------------------------------------------------------------------


def test_mirror_pairs_with_a_source_are_removed_and_undo_restores_them():
    app = _app()
    left = _part(app, "eye.L", PLACED)
    _select(app, left)
    right = app.mirror_copy("X")
    assert right is not None and app.scene.mirror_pairs
    pairs = tuple(app.scene.mirror_pairs)
    _select(app, left, right)
    assert app.attach_objects(), app.status_message
    assert not app.scene.mirror_pairs and "mirror pair" in app.status_message
    app.dispatch_command(commands.UNDO)
    assert tuple(app.scene.mirror_pairs) == pairs


def test_a_selected_group_stands_for_its_visible_leaves_and_stays():
    app = _app()
    a, b = _part(app, "A"), _part(app, "B", ObjectTransform(translation=(-3.0, 0.0, 0.0)))
    _select(app, a, b)
    assert app.dispatch_command(commands.GROUP_OBJECTS), app.status_message
    group = next(obj for obj in app.scene.objects.values() if obj.state is ObjectState.GROUP)
    _select(app, group)
    assert app.attach_objects(), app.status_message
    assert a.id not in app.scene.objects and b.id not in app.scene.objects
    assert group.id in app.scene.objects  # only the leaves are sources (AD-031 §2.1)


def test_save_and_load_keep_the_attached_data(tmp_path):
    app = _app()
    part = _part(app, "Ear", PLACED)
    _with_target(part.mesh, "Wiggle")
    _select(app, part)
    assert app.attach_objects(), app.status_message
    mesh = app.scene.mesh
    layers = {mesh.point_layer_info(lid): dict(mesh.layer_items(lid)) for lid in mesh.point_layer_ids()}
    regions = mesh.face_regions
    path = tmp_path / "attached.mirai.json"
    assert app.save_scene_file(path)
    app.load_scene("file", scene_path=path)
    loaded = app.scene.mesh
    assert {loaded.point_layer_info(lid): dict(loaded.layer_items(lid)) for lid in loaded.point_layer_ids()} == layers
    assert loaded.face_regions == regions
