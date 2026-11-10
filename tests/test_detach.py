"""AD-031 P3: Detach and Select Linked through `Application` (§2.2, §17) - one Undo step over the source mesh and the
new object, exact Undo / Redo, placement and look, every point layer, UVs and regions carried, the symmetric expansion
(Delete's path) and the new object's derived definition (VALID only), the crossing-plane part with a usable seam and
the part without one, every refusal changing nothing, O-8 (`PROVISIONAL`), save / load; Select Linked under the cursor
(the island, other islands untouched, no hover, the modes, symmetry not mirrored, the menu seed). Headless
(`Application` with its trace viewport). The kernel itself is `test_mesh_assembly.py`; the layer rules with morph
targets and weights are `test_layer_topology_ops.py` / `test_weights_topology_ops.py`."""

from __future__ import annotations

import random

import pytest

import tests._bootstrap  # noqa: F401
from core import (
    FaceRegion,
    FaceRegions,
    LayerKind,
    Mesh,
    ObjectMaterial,
    ObjectTransform,
    PointLayerInfo,
    SelectionMode,
)
from mirai import object_space
from mirai.application import Application
from mirai.detach import LinkedSeed
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.object_space import axis_angle_rotation
from mirai.resymmetrize import ResymmetrizeRejected, plan_resymmetrize
from mirai.scene_factory import create_cube, create_plane
from mirai.symmetric_ops import TEXT_UNPAIRED
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_axis import definition_for_axis
from mirai.symmetry_topology import topological_sides
from tests.mesh_invariants import assert_layer_invariants, assert_mesh_invariants, assert_uv_invariants
from tests.test_skinning import _random_pose, _rig
from tests.test_symmetric_ops import make_app, plus_x_quad

F = SelectionMode.FACE
WIDTH, HEIGHT = 800, 600
PLACED = ObjectTransform(translation=(3.0, 0.5, -1.0), rotation=axis_angle_rotation((0.0, 1.0, 0.0), 0.7), scale=0.6)


def _islands() -> Mesh:
    """A 3x3 plane (y = 0) and a cube beside it: two islands."""
    mesh = create_plane(2.0, 3)
    cube = create_cube(0.5)
    ids = {v: mesh.add_vertex(tuple(p + d for p, d in zip(cube.vertex_position(v), (3.0, 0.0, 0.0))))
           for v in cube.all_vertex_ids()}
    for f in cube.all_face_ids():
        mesh.add_face([ids[v] for v in cube.face_vertices(f)])
    return mesh


def _app(mesh: Mesh | None = None) -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state((mesh if mesh is not None else _islands()).export_state())
    app.viewport.on_topology_changed()
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _plane_faces(mesh) -> list:
    return sorted(f for f in mesh.all_face_ids() if all(mesh.vertex_position(v)[1] == 0.0 for v in mesh.face_vertices(f)))


def _cube_faces(mesh) -> list:
    return sorted(f for f in mesh.all_face_ids() if mesh.vertex_position(mesh.face_vertices(f)[0])[0] > 2.0)


def _select_faces(app: Application, faces) -> None:
    app.dispatch_command(commands.SET_FACE_MODE)
    app.selection.clear()
    app.selection.faces = set(faces)


def _body(mesh) -> dict:
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}


def _snapshot(app: Application) -> tuple:
    scene, selection = app.scene, app.selection
    return (
        _body(scene.mesh), sorted(int(i) for i in scene.objects), len(app.history), selection.mode,
        frozenset(selection.faces), frozenset(selection.vertices), frozenset(selection.edges),
        frozenset(selection.objects), scene.edit_object_id,
    )


def _new_object(app: Application, objects: set):
    (new_id,) = set(app.scene.objects) - objects
    return app.scene.objects[new_id]


def _world(obj, vertices=None) -> list:
    mesh = obj.mesh
    ids = mesh.all_vertex_ids() if vertices is None else vertices
    return sorted(object_space.to_world(obj, mesh.vertex_position(v)) for v in ids)


def _detach(app: Application) -> object:
    objects = set(app.scene.objects)
    assert app.dispatch_command(commands.DETACH), app.status_message
    return _new_object(app, objects)


# -- the step ------------------------------------------------------------------------------------------------------


def test_detach_is_one_step_and_undo_redo_are_exact():
    app = _app()
    src = app.scene.edit_object
    mesh = src.mesh
    cube = _cube_faces(mesh)
    _select_faces(app, cube)
    before = _snapshot(app)
    history = len(app.history)

    obj = _detach(app)

    assert len(app.history) == history + 1
    assert app.scene.edit_object is src and app.selection.mode is F  # O-8: component mode, the same edit object
    assert app.selection.faces == set() and app.selection.objects == before[7]  # the extracted ids are gone
    assert sorted(mesh.all_face_ids()) == _plane_faces(mesh) and len(obj.mesh.all_face_ids()) == 6
    assert obj.name == "cube.001" and app.status_message.startswith("Detached 6 face(s) of 'cube' as 'cube.001'")
    assert obj.id in app.viewport.object_entries
    assert_mesh_invariants(mesh)
    assert_mesh_invariants(obj.mesh)
    after_src, after_new = _body(mesh), obj.mesh.export_state()

    assert app.dispatch_command(commands.UNDO)
    assert _snapshot(app) == before  # the source mesh, the selection (the faces) and the mode come back
    assert obj.id not in app.scene.objects and obj.id not in app.viewport.object_entries

    assert app.dispatch_command(commands.REDO)
    assert app.scene.objects[obj.id] is obj  # the same instance and id (AD-001)
    assert _body(mesh) == after_src and obj.mesh.export_state() == after_new
    assert app.selection.faces == set() and app.scene.edit_object is src
    assert obj.id in app.viewport.object_entries


def test_detach_faces_is_the_same_command_and_several_faces_detach_together():
    app = _app()
    mesh = app.scene.mesh
    chosen = _plane_faces(mesh)[:2] + _cube_faces(mesh)[:1]
    _select_faces(app, chosen)
    objects = set(app.scene.objects)
    assert app.detach_faces(), app.status_message
    obj = _new_object(app, objects)
    assert len(obj.mesh.all_face_ids()) == 3 and not any(mesh.is_valid_face(f) for f in chosen)


def test_the_new_object_keeps_the_world_placement_and_look():
    app = _app()
    src = app.scene.edit_object
    src.transform, src.pivot = PLACED, (0.25, -0.5, 1.0)
    src.material = ObjectMaterial((0.2, 0.4, 0.6), 0.3, 0.7)
    src.texture = "skin.png"
    mesh = src.mesh
    cube = _cube_faces(mesh)
    world = _world(src, {v for f in cube for v in mesh.face_vertices(f)})
    _select_faces(app, cube)
    obj = _detach(app)
    assert (obj.transform, obj.pivot, obj.material, obj.texture, obj.state, obj.hidden, obj.parent) == (
        src.transform, src.pivot, src.material, src.texture, src.state, src.hidden, src.parent
    )
    assert _world(obj) == world  # same object space: bit-identical positions under the same placement


def test_targets_weights_uvs_and_regions_are_carried():
    mesh = _islands()
    cube = _cube_faces(mesh)
    rng = random.Random(4)
    smile = mesh.add_point_layer(PointLayerInfo("Smile"))
    skin = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(smile, v, tuple(rng.uniform(-0.2, 0.2) for _ in range(3)))
        if int(v) % 2:
            mesh.set_layer_value(skin, v, ((0, 0.25), (1, 0.75)))
    for i, f in enumerate(cube[:4]):
        mesh.set_face_uvs(f, tuple((0.1 * i + c, 0.05 * c) for c in range(4)))
    plane = _plane_faces(mesh)
    mesh.face_regions = FaceRegions((
        FaceRegion("Ear", frozenset(cube[:3])), FaceRegion("Lobe", frozenset(cube[3:] + plane[:1])),
        FaceRegion("Cheek", frozenset(plane[1:])),
    ))
    app = _app(mesh)
    src = app.scene.edit_object
    mesh = src.mesh
    corners = {f: (mesh.face_vertices(f), mesh.face_uvs(f)) for f in cube}
    values = {lid: dict(mesh.layer_items(lid)) for lid in mesh.point_layer_ids()}
    _select_faces(app, cube)
    obj = _detach(app)
    out = obj.mesh
    assert [out.point_layer_info(l) for l in out.point_layer_ids()] == [
        PointLayerInfo("Smile"), PointLayerInfo("Skin", LayerKind.WEIGHTS)
    ]
    # Every extracted face has its corner UVs exactly (never inferred: the two without UVs stay without).
    assert sorted(map(repr, (out.face_uvs(g) for g in out.all_face_ids()))) == sorted(
        map(repr, (uvs for _, uvs in corners.values()))
    )
    names = [r.name for r in out.face_regions.regions]
    assert names == ["Ear", "Lobe"]  # restricted to the extracted faces; "Cheek" stays with the source
    assert [len(r.faces) for r in out.face_regions.regions] == [3, 3]
    assert [r.name for r in mesh.face_regions.regions] == ["Ear", "Lobe", "Cheek"]  # the source keeps its regions
    assert_layer_invariants(out)
    assert_uv_invariants(out)
    assert out.symmetry_definition is None  # the source has none
    for lid_src, lid_out in zip(mesh.point_layer_ids(), out.point_layer_ids()):
        got = sorted(out.layer_items(lid_out))
        assert sorted(v for _, v in got) == sorted(
            values[lid_src][v] for v in {u for f in cube for u in corners[f][0]} if v in values[lid_src]
        )


# -- symmetry (D5, §3.5) -------------------------------------------------------------------------------------------


def test_a_symmetric_detach_takes_the_mirror_face_and_runs_delete_s_coordinator():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    face = plus_x_quad(mesh, touching_seam=False)
    _select_faces(app, {face})
    before = _snapshot(app)
    obj = _detach(app)
    assert len(obj.mesh.all_face_ids()) == 2 and "(with 1 mirror face(s))" in app.status_message
    assert symmetry_state(mesh) is SymmetryState.VALID  # the source stays symmetric (Delete's delta check)
    out = obj.mesh
    assert out.symmetry_definition is not None and out.symmetry_definition.seam_edges == frozenset()
    assert symmetry_state(out) is SymmetryState.VALID
    assert "no seam (Re-Symmetrize not available there)" in app.status_message
    with pytest.raises(ResymmetrizeRejected, match="keine Seam"):  # the expected limitation (§3.5)
        plan_resymmetrize(out, out.all_vertex_ids()[0])
    assert app.dispatch_command(commands.UNDO) and _snapshot(app) == before


def _seam_band(mesh) -> set:
    """The +X faces touching the seam (a ring around subd_cube)."""
    seam = {v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)}
    return {
        f for f in mesh.all_face_ids()
        if seam & set(mesh.face_vertices(f)) and max(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0
    }


def test_a_part_crossing_the_plane_derives_a_usable_seam():
    """§9.3 P3: VALID, symmetric operations work on the detached part, Re-Symmetrize works (the seam splits it in two)."""
    app = make_app("subd_cube")
    src = app.scene.edit_object
    band = _seam_band(src.mesh)
    _select_faces(app, band)
    obj = _detach(app)
    out = obj.mesh
    definition = out.symmetry_definition
    assert definition is not None and definition.seam_edges
    assert symmetry_state(out) is SymmetryState.VALID
    assert topological_sides(out).component_count == 2
    assert f"symmetry X on {obj.name!r}" in app.status_message

    # Edit the detached part: a symmetric Delete takes the mirror face too.
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.selection.objects = {obj.id}
    assert app.dispatch_command(commands.SET_FACE_MODE)
    assert app.scene.edit_object is obj, app.status_message
    one = next(f for f in sorted(out.all_face_ids()) if min(out.vertex_position(v)[0] for v in out.face_vertices(f)) >= 0)
    faces = len(out.all_face_ids())
    _select_faces(app, {one})
    assert app.dispatch_command(commands.DELETE), app.status_message
    assert len(out.all_face_ids()) == faces - 2 and symmetry_state(out) is SymmetryState.VALID
    assert app.dispatch_command(commands.UNDO)

    # Re-Symmetrize: one side moved, the plan mirrors it back.
    side = topological_sides(out)
    moved = next(v for v, s in sorted(side.vertex_side.items()) if s == 0)
    plan = plan_resymmetrize(out, next(v for v, s in sorted(side.vertex_side.items()) if s == 1))
    assert plan.unmatched == frozenset()
    x, y, z = out.vertex_position(moved)
    out.set_vertex_position(moved, (x, y + 0.1, z))  # test setup: one side out of symmetry
    source = next(v for v, s in sorted(side.vertex_side.items()) if s == 1)
    assert [c.vertex for c in plan_resymmetrize(out, source).moves] == [moved]
    app.dispatch_command(commands.SET_VERTEX_MODE)
    app.selection.clear()
    app.selection.vertices = {source}
    history = len(app.history)
    alt_m = Input("key", "m", frozenset({"alt"}))
    assert app.bindings.command_for(alt_m) == commands.RESYMMETRIZE
    assert app.key_press(alt_m), app.status_message  # opens the preview: "bewegt 1"
    assert "bewegt 1" in app.status_message
    assert app.key_press(alt_m), app.status_message  # executes it
    assert len(app.history) == history + 1
    assert out.vertex_position(moved) == (x, y, z)


def test_the_new_object_gets_no_definition_unless_valid(monkeypatch):
    """§3.5: never an invalid definition - when the derived one is not VALID the object has none, and the status says so."""
    import mirai.application as application_module

    monkeypatch.setattr(application_module, "derived_symmetry", lambda mesh, axis: None)
    app = make_app("subd_cube")
    _select_faces(app, {plus_x_quad(app.scene.mesh, touching_seam=False)})
    obj = _detach(app)
    assert obj.mesh.symmetry_definition is None
    assert f"symmetry off on {obj.name!r} (not symmetric about X)" in app.status_message


def test_an_unpaired_face_is_refused_and_nothing_changes():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    face = plus_x_quad(mesh, touching_seam=False)
    v = mesh.face_vertices(face)[0]
    x, y, z = mesh.vertex_position(v)
    mesh.set_vertex_position(v, (x + 0.01, y, z))  # its mirror point no longer matches: the face has no partner
    _select_faces(app, {face})
    before = _snapshot(app)
    assert app.dispatch_command(commands.DETACH) is False
    assert app.status_message == TEXT_UNPAIRED and _snapshot(app) == before


def test_the_detached_part_has_no_mirror_pair():
    app = make_app("subd_cube")
    _select_faces(app, {plus_x_quad(app.scene.mesh, touching_seam=False)})
    obj = _detach(app)
    assert app.scene.mirror_pair_of(obj.id) is None


# -- refusals: nothing changes --------------------------------------------------------------------------------------


def _refusal(app: Application, case: str) -> None:
    mesh = app.scene.mesh
    if case == "vertex mode":
        app.dispatch_command(commands.SET_VERTEX_MODE)
        app.selection.vertices = set(mesh.all_vertex_ids()[:3])
    elif case == "object mode":
        app.dispatch_command(commands.SET_OBJECT_MODE)
    elif case == "nothing selected":
        app.selection.clear()
    elif case == "every face":
        app.selection.faces = set(mesh.all_face_ids())
    elif case == "dial":
        lid = app.create_morph_target("Smile")
        assert lid is not None and app.set_morph_weight(40, lid)
        _select_faces(app, _cube_faces(mesh))
    elif case == "editing view":
        assert app.create_morph_target("Smile") is not None, app.status_message
        assert app.edit_morph_target(), app.status_message
        _select_faces(app, _cube_faces(mesh))
    elif case == "hidden":
        cube = _cube_faces(mesh)
        _select_faces(app, cube[:1])
        assert app.dispatch_command(commands.HIDE_SELECTION)
        corners = set(mesh.face_vertices(cube[0]))
        _select_faces(app, [next(f for f in cube[1:] if corners & set(mesh.face_vertices(f)))])  # touches it


@pytest.mark.parametrize("case, text", [
    ("vertex mode", "press 3"),
    ("object mode", "press 3"),
    ("nothing selected", "none selected"),
    ("every face", "nothing would stay"),
    ("dial", "dialled in"),
    ("editing view", "on the base only"),
    ("hidden", "hidden geometry in the way"),
])
def test_a_refusal_changes_nothing(case, text):
    app = _app()
    _select_faces(app, _cube_faces(app.scene.mesh))
    _refusal(app, case)
    before, objects = _snapshot(app), set(app.scene.objects)
    assert app.detach_faces() is False
    assert text in app.status_message, app.status_message
    assert _snapshot(app) == before and set(app.scene.objects) == objects
    assert app.dispatch_command(commands.DETACH) is False
    assert _snapshot(app) == before and set(app.scene.objects) == objects
    assert app.detach_plan().refusal is not None


def test_posed_rig_with_a_bound_mesh_is_refused():
    app = _app()
    rig = _rig()
    app.scene.rig = rig
    mesh = app.scene.mesh
    skin = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(skin, v, ((int(rig.bone_ids()[0]), 1.0),))
    _select_faces(app, _cube_faces(mesh))
    app._skeleton.set_pose(_random_pose(random.Random(3), rig, share=1.0))
    assert app.posed
    before = _snapshot(app)
    assert app.detach_faces() is False
    assert "is posed" in app.status_message and _snapshot(app) == before
    assert app.dispatch_command(commands.DETACH) is False and _snapshot(app) == before
    app._skeleton.set_pose({})
    obj = _detach(app)
    assert obj.mesh.point_layer_ids()  # the weights came along: the new object is bound at rest


def test_a_refused_symmetric_deletion_rolls_back_and_adds_no_object(monkeypatch):
    """The one check inside the step (Delete's delta check): rolled back exactly, no object, no history entry."""
    from mirai import symmetry_declarations
    from mirai.symmetric_ops import SymmetryRefusal

    def refuse(mesh, mode, ids):
        mesh.delete_faces(sorted(ids))
        raise SymmetryRefusal("Symmetrie: refused for the test")

    app = make_app("subd_cube")
    _select_faces(app, {plus_x_quad(app.scene.mesh, touching_seam=False)})
    before, objects = _snapshot(app), set(app.scene.objects)
    table = dict(symmetry_declarations.REMOVAL_COORDINATORS)
    table[commands.DELETE] = refuse
    monkeypatch.setattr(symmetry_declarations, "REMOVAL_COORDINATORS", table)
    assert app.detach_faces() is False
    assert app.status_message == "Symmetrie: refused for the test"
    assert _snapshot(app) == before and set(app.scene.objects) == objects


# -- file -----------------------------------------------------------------------------------------------------------


def test_save_and_load_keep_both_objects(tmp_path):
    mesh = _islands()
    lid = mesh.add_point_layer(PointLayerInfo("Smile"))
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(lid, v, (0.0, 0.1 * int(v), 0.0))
    mesh.face_regions = FaceRegions((FaceRegion("Ear", frozenset(_cube_faces(mesh))),))
    app = _app(mesh)
    app.scene.edit_object.transform = PLACED
    _select_faces(app, _cube_faces(app.scene.mesh))
    obj = _detach(app)
    states = {o.name: (o.mesh.export_state(), o.transform) for o in app.scene.objects.values()}
    path = tmp_path / "detached.mirai.json"
    assert app.save_scene_file(path)
    app.load_scene("file", scene_path=path)
    loaded = {o.name: (o.mesh.export_state(), o.transform) for o in app.scene.objects.values()}
    assert loaded == states and obj.name in loaded


# -- Select Linked ---------------------------------------------------------------------------------------------------


def _hover_face(app: Application, face) -> bool:
    """Moves the pointer over the centre of `face` (a real pick); True when the face is hovered."""
    mesh = app.scene.mesh
    corners = [mesh.vertex_position(v) for v in mesh.face_vertices(face)]
    centre = tuple(sum(c) / len(corners) for c in zip(*corners))
    x, y = app.camera.project_to_screen(centre, WIDTH, HEIGHT)
    app.pointer_motion(x, y)
    app.flush_hover()
    return app.selection.hovered == face


def _visible_face(app: Application, faces) -> object:
    for f in sorted(faces):
        if _hover_face(app, f):
            return f
    raise AssertionError("no face of the island can be hovered")


def test_select_linked_selects_the_island_under_the_cursor_only():
    app = _app()
    mesh = app.scene.mesh
    app.dispatch_command(commands.SET_FACE_MODE)
    _visible_face(app, _plane_faces(mesh))
    history = len(app.history)
    assert app.dispatch_command(commands.SELECT_LINKED), app.status_message
    assert app.selection.faces == set(_plane_faces(mesh))  # the cube island stays unselected
    assert len(app.history) == history  # a selection change, no Undo step (like Shift+L)
    assert app.status_message == "Select Linked: a part of 9 face(s) - 9 face(s) selected (+9)"
    _visible_face(app, _cube_faces(mesh))
    assert app.select_linked()  # adds the second island
    assert app.selection.faces == set(mesh.all_face_ids())


def test_select_linked_then_detach_takes_the_whole_island():
    app = _app()
    mesh = app.scene.mesh
    app.dispatch_command(commands.SET_FACE_MODE)
    _visible_face(app, _cube_faces(mesh))
    assert app.select_linked(), app.status_message
    obj = _detach(app)
    assert len(obj.mesh.all_face_ids()) == 6 and sorted(mesh.all_face_ids()) == _plane_faces(mesh)
    assert topological_sides(obj.mesh).component_count == 1


@pytest.mark.parametrize("mode, kind", [(commands.SET_VERTEX_MODE, "vertices"), (commands.SET_EDGE_MODE, "edges")])
def test_select_linked_in_vertex_and_edge_mode_selects_the_island_s_elements(mode, kind):
    app = _app()
    mesh = app.scene.mesh
    cube = _cube_faces(mesh)
    app.dispatch_command(mode)
    app.selection.hovered = mesh.face_vertices(cube[0])[0] if kind == "vertices" else mesh.face_edges(cube[0])[0]
    assert app.select_linked(), app.status_message
    expected = (
        {v for f in cube for v in mesh.face_vertices(f)} if kind == "vertices" else {e for f in cube for e in mesh.face_edges(f)}
    )
    assert getattr(app.selection, kind) == expected


def test_select_linked_without_a_hovered_face_is_refused():
    app = _app()
    app.dispatch_command(commands.SET_FACE_MODE)
    app.pointer_motion(2.0, 2.0)  # empty space
    app.flush_hover()
    assert app.selection.hovered is None
    before = _snapshot(app)
    assert app.select_linked() is False
    assert app.status_message == "Select Linked: nothing under the cursor - point at a face of the part"
    assert _snapshot(app) == before
    app.dispatch_command(commands.SET_OBJECT_MODE)
    assert app.select_linked() is False and "press 1/2/3" in app.status_message


def test_select_linked_from_a_remembered_seed_and_a_stale_seed():
    """The SPACE menu's path: the element under the cursor when the menu opened (`linked_seed`), checked against the edit
    object and the mode when the entry is chosen - the hover is gone by then (`pointer_leave`)."""
    app = _app()
    mesh = app.scene.mesh
    app.dispatch_command(commands.SET_FACE_MODE)
    face = _visible_face(app, _cube_faces(mesh))
    seed = app.linked_seed()
    assert seed == LinkedSeed(app.scene.edit_object_id, F, face)
    app.pointer_leave()  # the pointer reaches the menu
    assert app.selection.hovered is None
    assert app.select_linked(seed), app.status_message
    assert app.selection.faces == set(_cube_faces(mesh))
    app.dispatch_command(commands.SET_EDGE_MODE)
    before = _snapshot(app)
    assert app.select_linked(seed) is False and "changed since" in app.status_message
    assert _snapshot(app) == before
    app.dispatch_command(commands.SET_OBJECT_MODE)
    assert app.linked_seed() is None


def _mirrored_islands() -> Mesh:
    """A plane across X = 0 (seam along it) and two cubes at x = +3 / -3: symmetric about X, three islands."""
    mesh = create_plane(2.0, 2)
    cube = create_cube(0.5)
    for dx in (3.0, -3.0):
        ids = {v: mesh.add_vertex(tuple(p + d for p, d in zip(cube.vertex_position(v), (dx, 0.0, 0.0))))
               for v in cube.all_vertex_ids()}
        for f in cube.all_face_ids():
            mesh.add_face([ids[v] for v in cube.face_vertices(f)])
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    assert symmetry_state(mesh) is SymmetryState.VALID
    return mesh


def test_select_linked_is_not_mirrored_under_symmetry_and_detach_adds_the_mirror_island():
    """The existing selection rule (no selection command mirrors); Detach's expansion takes the mirror island, the new
    object derives an empty seam (VALID) - the documented limitation for parts away from the plane."""
    app = _app(_mirrored_islands())
    mesh = app.scene.mesh
    plus = {f for f in mesh.all_face_ids() if mesh.vertex_position(mesh.face_vertices(f)[0])[0] > 2.0}
    minus = {f for f in mesh.all_face_ids() if mesh.vertex_position(mesh.face_vertices(f)[0])[0] < -2.0}
    app.dispatch_command(commands.SET_FACE_MODE)
    app.selection.hovered = min(plus)
    assert app.select_linked(), app.status_message
    assert app.selection.faces == plus  # the mirror island stays unselected
    obj = _detach(app)
    assert len(obj.mesh.all_face_ids()) == 12 and not any(mesh.is_valid_face(f) for f in plus | minus)
    assert obj.mesh.symmetry_definition is not None and obj.mesh.symmetry_definition.seam_edges == frozenset()
    assert symmetry_state(obj.mesh) is SymmetryState.VALID
    assert symmetry_state(mesh) is SymmetryState.VALID


@pytest.mark.parametrize("make", ["detach", "duplicate"])
@pytest.mark.parametrize("load", ["primitive", "file"])
def test_a_scene_with_a_group_member_newer_than_its_group_can_be_replaced(make, load, tmp_path):
    """Practical test P3 (Manu 2026-11-10, "Objekt 21 hat Mitglieder"): Detach - like Duplicate - keeps the source's
    group, so the group has a member with a higher id than itself; loading another scene removed the old objects in id
    order and `Scene.remove_object` refused the group. Members now go first (`scene_objects._remove_objects`)."""
    from core import ObjectState

    app = _app()
    src = app.scene.edit_object
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.selection.objects = {src.id}
    assert app.dispatch_command(commands.GROUP_OBJECTS), app.status_message
    group = next(o for o in app.scene.objects.values() if o.state is ObjectState.GROUP)
    if make == "detach":
        _select_faces(app, _cube_faces(app.scene.mesh))
        obj = _detach(app)
    else:
        app.selection.objects = {src.id}
        objects = set(app.scene.objects)
        assert app.dispatch_command(commands.DUPLICATE_OBJECTS), app.status_message
        obj = _new_object(app, objects)
    assert obj.parent == group.id and int(obj.id) > int(group.id)
    path = tmp_path / "grouped.mirai.json"
    assert app.save_scene_file(path)
    names = sorted((o.name, o.parent is not None) for o in app.scene.objects.values())
    if load == "primitive":
        app.load_scene("cube")
        assert len(app.scene.objects) == 1
    else:
        app.load_scene("file", scene_path=path)
        assert sorted((o.name, o.parent is not None) for o in app.scene.objects.values()) == names
