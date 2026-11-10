"""AD-031 P1/P2: the assembly kernel `mirai.mesh_assembly` (`append_objects`, `extract_faces`, `look_differences`,
`incoming_unweighted`, `derived_symmetry`).

Headless and pure (no `Application`, no pyglet): positions and coordinate frames against an independent matrix oracle,
morph targets (new prefixed layers, never merged, the world-space mix preserved), skin weights (merged, `BoneId`s
unchanged, skinning invariant under a posed rig), corner UVs (carried, never inferred), regions (carried, collision-safe
names, the colour consequence, the O-7 region for ungrouped faces), symmetry (definition untouched, new or worsened
AMBIGUOUS refused and rolled back, PARTIAL reported, the mirrored pair), the O-5 pre-count, refusals and atomicity (nothing changes on any failure, standalone or inside an outer recording), the
Core invariants, and the extract side incl. the derived symmetry definition.
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import FaceRegion, FaceRegions, LayerKind, Mesh, ObjectMaterial, ObjectTransform, PointLayerInfo, Scene
from core.mesh import MeshError
from mirai import mesh_assembly, morph_mix, object_space, skinning
from mirai.mesh_assembly import (
    AssemblyRefused,
    append_objects,
    derived_symmetry,
    extract_faces,
    linked_faces,
    look_differences,
)
from mirai.object_mirror import mirror_mesh, mirror_placement
from mirai.object_space import axis_angle_rotation
from mirai.regions import slot_index
from mirai.scene_factory import create_cube, create_plane
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_axis import definition_for_axis
from tests.mesh_invariants import assert_layer_invariants, assert_mesh_invariants, assert_uv_invariants
from tests.test_skinning import _bound_mesh, _random_pose, _rig

X = (1.0, 0.0, 0.0)
SEP = mesh_assembly.NAME_SEPARATOR


# -- fixtures ---------------------------------------------------------------------------------------------------------


def _scene(dst_mesh: Mesh, *, transform=None, pivot=(0.0, 0.0, 0.0)):
    scene = Scene()
    dst = scene.edit_object
    dst.mesh, dst.name = dst_mesh, "Head"
    if transform is not None:
        dst.transform = transform
    dst.pivot = pivot
    return scene, dst


def _add(scene, mesh, name, transform=None, pivot=(0.0, 0.0, 0.0)):
    obj = scene.add_object(mesh, name=name)
    if transform is not None:
        obj.transform = transform
    obj.pivot = pivot
    return obj


def _ear() -> Mesh:
    """A cup: a cube without its -X face (an open border, like an ear's base)."""
    mesh = create_cube(0.4)
    minus_x = next(f for f in mesh.all_face_ids() if all(mesh.vertex_position(v)[0] < 0 for v in mesh.face_vertices(f)))
    mesh.delete_faces([minus_x])
    return mesh


def _transform(axis, angle, translation, scale) -> ObjectTransform:
    n = math.sqrt(sum(c * c for c in axis))
    return ObjectTransform(
        translation=translation, rotation=axis_angle_rotation(tuple(c / n for c in axis), angle), scale=scale
    )


ROTATED = _transform((0.3, 1.0, -0.2), 0.9, (1.5, -0.4, 2.0), 1.7)
EAR_PLACEMENT = _transform((0.0, 0.0, 1.0), 0.37, (4.0, 0.7, 0.2), 0.8)


def _body(mesh: Mesh) -> dict:
    """`export_state()` without the id counters (a rollback restores records; counters only move forward, AD-001)."""
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}


def _close(a, b, tol=1e-12) -> bool:
    return all(abs(x - y) <= tol * max(1.0, abs(x), abs(y)) for x, y in zip(a, b))


def _matrix_oracle(dst, src):
    """M = (s_src / s_dst)·R_dstᵀ·R_src, written out (independent of `object_space`)."""
    rd, rs = dst.transform.rotation, src.transform.rotation
    k = src.transform.scale / dst.transform.scale
    return [[k * sum(rd[r][i] * rs[r][j] for r in range(3)) for j in range(3)] for i in range(3)]


def _apply(m, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))


def _with_targets(mesh: Mesh, names, seed=1) -> list:
    rng = random.Random(seed)
    lids = [mesh.add_point_layer(PointLayerInfo(n)) for n in names]
    for lid in lids:
        for v in mesh.all_vertex_ids():
            if rng.random() < 0.7:
                mesh.set_layer_value(lid, v, tuple(rng.uniform(-0.2, 0.2) for _ in range(3)))
    return lids


# -- positions, topology, coordinate frames --------------------------------------------------------------------------


def test_append_keeps_the_world_shape_and_copies_topology():
    scene, dst = _scene(create_cube(2.0), transform=ROTATED, pivot=(0.2, -0.1, 0.3))
    source = _ear()
    loose_a = source.add_vertex((3.0, 0.0, 0.0))
    loose_b = source.add_vertex((3.0, 1.0, 0.0))
    source.add_edge(loose_a, loose_b)
    lonely = source.add_vertex((5.0, 5.0, 5.0))  # no edge at all
    ear = _add(scene, source, "Ear", EAR_PLACEMENT, (0.1, 0.2, 0.0))
    dst_before = _body(dst.mesh)
    src_before = source.export_state()
    old_vertices = set(dst.mesh.all_vertex_ids())

    result = append_objects(dst, [ear])

    vmap, fmap = result.vertex_maps[ear.id], result.face_maps[ear.id]
    assert set(vmap) == set(source.all_vertex_ids()) and lonely in vmap
    assert not set(vmap.values()) & old_vertices
    for v, w in vmap.items():
        assert _close(object_space.to_world(dst, dst.mesh.vertex_position(w)),
                      object_space.to_world(ear, source.vertex_position(v)))
    for f, g in fmap.items():
        assert dst.mesh.face_vertices(g) == [vmap[v] for v in source.face_vertices(f)]
    loose = [e for e in dst.mesh.all_edge_ids() if not dst.mesh.edge_faces(e)]
    assert [set(dst.mesh.edge_vertices(e)) for e in loose] == [{vmap[loose_a], vmap[loose_b]}]
    assert len(dst.mesh.all_face_ids()) == 6 + 5
    for key, value in dst_before.items():  # the destination's own elements are untouched
        if key in ("vertices", "edges", "faces"):
            assert all(dst.mesh.export_state()[key][k] == rec for k, rec in value.items())
    assert source.export_state() == src_before  # sources are only read
    assert dst.transform == ROTATED and dst.pivot == (0.2, -0.1, 0.3)
    assert_mesh_invariants(dst.mesh)


def test_equal_placement_copies_positions_and_offsets_bit_identically():
    scene, dst = _scene(create_cube(2.0), transform=ROTATED, pivot=(0.5, 0.0, 0.0))
    source = _ear()
    (lid,) = _with_targets(source, ["Wiggle"])
    ear = _add(scene, source, "Ear", ROTATED, (0.5, 0.0, 0.0))
    result = append_objects(dst, [ear])
    vmap = result.vertex_maps[ear.id]
    target = result.layer_maps[ear.id][lid]
    for v, w in vmap.items():
        assert dst.mesh.vertex_position(w) == source.vertex_position(v)
        assert dst.mesh.layer_value(target, w) == source.layer_value(lid, v)


def test_the_result_is_deterministic():
    def run():
        scene, dst = _scene(create_cube(2.0))
        b = _add(scene, create_cube(0.3), "B", EAR_PLACEMENT)
        a = _add(scene, _ear(), "A", ROTATED)
        _with_targets(a.mesh, ["T"])
        append_objects(dst, [b, a])  # the given order does not matter: ObjectId order
        return dst.mesh.export_state()

    assert run() == run()


# -- morph targets (VECTOR layers) -----------------------------------------------------------------------------------


def test_targets_become_new_prefixed_layers_and_are_never_merged():
    scene, dst = _scene(create_cube(2.0), transform=ROTATED)
    (smile,) = _with_targets(dst.mesh, ["Smile"])
    dst.mesh.add_point_layer(PointLayerInfo(f"Ear{SEP}Wiggle"))  # a taken name: the carried one gets " 2"
    own_values = dst.mesh.layer_items(smile)
    ear = _add(scene, _ear(), "Ear", EAR_PLACEMENT, (0.1, 0.2, 0.0))
    wiggle, ear_smile = _with_targets(ear.mesh, ["Wiggle", "Smile"], seed=2)
    ear.mesh.set_point_layer_info(ear_smile, PointLayerInfo("Smile", new_point="zero"))
    ear2 = _add(scene, mirror_mesh(ear.mesh, X), "Ear.001")
    ear2.transform, ear2.pivot = mirror_placement(ear, X, 0.0)

    result = append_objects(dst, [ear2, ear])

    mesh = dst.mesh
    infos = [mesh.point_layer_info(l) for l in mesh.point_layer_ids()]
    assert [i.name for i in infos] == [
        "Smile", f"Ear{SEP}Wiggle", f"Ear{SEP}Wiggle 2", f"Ear{SEP}Smile", f"Ear.001{SEP}Wiggle", f"Ear.001{SEP}Smile",
    ]
    assert all(i.kind is LayerKind.VECTOR for i in infos)
    assert infos[3].new_point == "zero" and infos[2].new_point == "interpolate"  # the rule travels with the target
    assert mesh.point_layer_ids()[0] == smile and mesh.layer_items(smile) == own_values  # own target untouched
    vmap = result.vertex_maps[ear.id]
    assert all(mesh.layer_value(smile, w) == (0.0, 0.0, 0.0) for w in vmap.values())  # default for the new points
    m = _matrix_oracle(dst, ear)
    for src_lid in (wiggle, ear_smile):
        target = result.layer_maps[ear.id][src_lid]
        assert {vmap[v] for v, _ in ear.mesh.layer_items(src_lid)} == {w for w, _ in mesh.layer_items(target)}
        for v, value in ear.mesh.layer_items(src_lid):
            assert _close(mesh.layer_value(target, vmap[v]), _apply(m, value))
    assert_layer_invariants(mesh)


def test_the_world_space_morph_mix_is_preserved():
    scene, dst = _scene(create_cube(2.0), transform=ROTATED, pivot=(0.3, 0.0, -0.2))
    ear = _add(scene, _ear(), "Ear", EAR_PLACEMENT, (0.1, 0.2, 0.0))
    lids = _with_targets(ear.mesh, ["Wiggle", "Smile"], seed=3)
    weights = {lids[0]: 60, lids[1]: 30}
    before = {v: object_space.to_world(ear, p) for v, p in morph_mix.evaluate(ear.mesh, weights).items()}
    result = append_objects(dst, [ear])
    carried = {result.layer_maps[ear.id][l]: w for l, w in weights.items()}
    after = morph_mix.evaluate(dst.mesh, carried)
    for v, w in result.vertex_maps[ear.id].items():
        assert _close(object_space.to_world(dst, after[w]), before[v], 1e-11)


def test_too_many_targets_are_refused(monkeypatch):
    monkeypatch.setattr(mesh_assembly, "MAX_TARGETS", 3)
    scene, dst = _scene(create_cube(2.0))
    _with_targets(dst.mesh, ["A", "B"])
    ear = _add(scene, _ear(), "Ear")
    _with_targets(ear.mesh, ["C", "D"])
    before = dst.mesh.export_state()
    with pytest.raises(AssemblyRefused, match="morph targets"):
        append_objects(dst, [ear])
    assert dst.mesh.export_state() == before


# -- skin weights (WEIGHTS layer) ------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(3))
def test_weights_merge_into_the_skin_layer_and_skinning_is_unchanged(seed):
    rng = random.Random(seed)
    rig = _rig()
    scene, dst = _scene(create_cube(2.0), transform=_transform((1, 2, 3), 0.4 + seed, (0.3, 0.0, 1.0), 1.3))
    source = _bound_mesh(rng)
    part = _add(scene, source, "Part", _transform((2, -1, 0.5), 1.1, (-1.0, 2.0, 0.0), 0.7), (0.4, 0.1, 0.0))
    pose = _random_pose(rng, rig)
    before = skinning.evaluate(source, None, rig, pose, skinning.placement_of(part))
    src_skin = skinning.skin_layer(source)

    result = append_objects(dst, [part])

    mesh = dst.mesh
    skin = skinning.skin_layer(mesh)
    assert mesh.point_layer_info(skin) == PointLayerInfo("Skin", LayerKind.WEIGHTS)
    assert result.layer_maps[part.id][src_skin] == skin
    vmap = result.vertex_maps[part.id]
    for v, w in vmap.items():
        assert mesh.layer_value(skin, w) == source.layer_value(src_skin, v)  # BoneId keys and weights unchanged
    assert result.unweighted == sum(1 for v in vmap if not source.layer_value(src_skin, v))
    after = skinning.evaluate(mesh, None, rig, pose, skinning.placement_of(dst))
    for v, w in vmap.items():
        assert _close(object_space.to_world(dst, after[w]), object_space.to_world(part, before[v]), 1e-10)
    assert_layer_invariants(mesh)


def test_unweighted_points_into_a_bound_destination_stay_unbound_and_are_counted():
    rng = random.Random(4)
    scene, dst = _scene(_bound_mesh(rng))
    skin = skinning.skin_layer(dst.mesh)
    own = dst.mesh.layer_items(skin)
    ear = _add(scene, _ear(), "Ear")
    result = append_objects(dst, [ear])
    assert skinning.skin_layer(dst.mesh) == skin and len(dst.mesh.point_layer_ids()) == 1
    assert dst.mesh.layer_items(skin) == own  # nothing new is weighted, nothing old changed
    assert result.unweighted == len(ear.mesh.all_vertex_ids())


def test_the_read_only_pre_count_equals_the_appended_unweighted_count():
    """O-5: `incoming_unweighted` is what the refusal shows before anything changes; it equals the append's count.
    Zero weights are stored as the empty value, so a point set to all-zero counts like a point without weights."""
    rng = random.Random(7)
    scene, dst = _scene(_bound_mesh(rng))
    bound_part = _bound_mesh(rng)
    skin = skinning.skin_layer(bound_part)
    some = sorted(bound_part.all_vertex_ids())[:3]
    key = next(k for v, value in bound_part.layer_items(skin) for k, _ in value)
    for v in some:
        bound_part.set_layer_value(skin, v, ((key, 0.0),))  # all-zero -> stored as ()
        assert bound_part.layer_value(skin, v) == ()
    part = _add(scene, bound_part, "Part")
    ear = _add(scene, _ear(), "Ear")
    states = [obj.mesh.export_state() for obj in (dst, part, ear)]
    expected = mesh_assembly.incoming_unweighted([part, ear])
    assert [obj.mesh.export_state() for obj in (dst, part, ear)] == states  # read-only
    assert expected >= len(some) + len(ear.mesh.all_vertex_ids())
    assert append_objects(dst, [part, ear]).unweighted == expected


def test_a_taken_skin_name_gets_a_suffix_but_stays_the_skin_layer():
    rng = random.Random(5)
    scene, dst = _scene(create_cube(2.0))
    dst.mesh.add_point_layer(PointLayerInfo("Skin"))  # a morph target named "Skin"
    part = _add(scene, _bound_mesh(rng), "Part")
    result = append_objects(dst, [part])
    skin = skinning.skin_layer(dst.mesh)
    assert dst.mesh.point_layer_info(skin).name == "Skin 2"
    assert set(result.layer_maps[part.id].values()) == {skin}


@pytest.mark.parametrize("where", ["destination", "source"])
def test_two_weights_layers_are_refused(where):
    rng = random.Random(6)
    scene, dst = _scene(create_cube(2.0))
    part = _add(scene, _bound_mesh(rng), "Part")
    holder = dst.mesh if where == "destination" else part.mesh
    if where == "destination":
        holder.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    holder.add_point_layer(PointLayerInfo("Skin B", LayerKind.WEIGHTS))
    before, src_before = dst.mesh.export_state(), part.mesh.export_state()
    with pytest.raises(AssemblyRefused, match="more than one weights layer"):
        append_objects(dst, [part])
    assert dst.mesh.export_state() == before and part.mesh.export_state() == src_before


# -- UVs ----------------------------------------------------------------------------------------------------------------


def test_corner_uvs_are_carried_and_never_inferred():
    scene, dst = _scene(create_plane(2.0, 2))
    for f in dst.mesh.all_face_ids():
        dst.mesh.set_face_uvs(f, ((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)))
    source = create_plane(1.0, 2)
    faces = sorted(source.all_face_ids())
    source.set_face_uvs(faces[0], ((0.1, 0.2), (0.3, 0.4), (0.5, 0.6), (0.7, 0.8)))
    part = _add(scene, source, "Part", EAR_PLACEMENT)
    result = append_objects(dst, [part])
    fmap = result.face_maps[part.id]
    assert dst.mesh.face_uvs(fmap[faces[0]]) == source.face_uvs(faces[0])
    assert all(dst.mesh.face_uvs(fmap[f]) is None for f in faces[1:])  # unmapped stays unmapped
    assert_uv_invariants(dst.mesh)


# -- regions --------------------------------------------------------------------------------------------------------------


def test_regions_survive_with_collision_safe_names():
    scene, dst = _scene(create_cube(2.0))
    hf = sorted(dst.mesh.all_face_ids())
    dst.mesh.face_regions = FaceRegions((FaceRegion("Brow", frozenset(hf[:2])), FaceRegion("Group 1", frozenset(hf[2:3]))))
    own = dst.mesh.face_regions.regions
    ear = _add(scene, _ear(), "Ear", EAR_PLACEMENT)
    ef = sorted(ear.mesh.all_face_ids())
    dead = type(ef[0])(999)
    ear.mesh.face_regions = FaceRegions((
        FaceRegion("Brow", frozenset(ef[:1])),
        FaceRegion("Group 1", frozenset(ef[1:3])),
        FaceRegion("Ear lobe", frozenset(ef[3:]) | {dead}),  # a dead id is not carried
        FaceRegion("Lost", frozenset({dead})),  # no live face: carried empty, the name is kept
    ))
    ear2 = _add(scene, mirror_mesh(ear.mesh, X), "Ear.001")
    ear2.transform, ear2.pivot = mirror_placement(ear, X, 0.0)
    ear2.mesh.face_regions = FaceRegions((FaceRegion("Brow", frozenset(sorted(ear2.mesh.all_face_ids())[:1])),))

    result = append_objects(dst, [ear, ear2])

    regions = dst.mesh.face_regions
    assert [r.name for r in regions.regions] == [
        "Brow", "Group 1", f"Ear{SEP}Brow", "Group 2", "Ear lobe", "Lost", f"Ear.001{SEP}Brow",
    ]
    assert regions.regions[:2] == own  # the destination's regions are untouched
    fmap = result.face_maps[ear.id]
    for src_region in ear.mesh.face_regions.regions:
        name = result.region_names[ear.id][src_region.name]
        assert regions.get(name).faces == {fmap[f] for f in src_region.faces if f in fmap}
    assert regions.get("Lost").faces == frozenset()
    # AD-031 §3.3: the tint follows the name, so a renamed region shows another colour
    assert slot_index(f"Ear{SEP}Brow") != slot_index("Brow")
    assert slot_index("Group 2") != slot_index("Group 1")


def test_without_the_option_ungrouped_faces_stay_ungrouped():
    scene, dst = _scene(create_cube(2.0))
    ear = _add(scene, _ear(), "Ear")
    result = append_objects(dst, [ear])
    assert dst.mesh.face_regions is None and result.ungrouped_regions == {}


def test_ungrouped_source_faces_get_a_region_named_after_the_source():
    """O-7 (Manu 2026-11-10): a source's faces in none of its regions join one new region named after the source,
    after that source's carried regions; grouped faces and every existing assignment stay as they are."""
    scene, dst = _scene(create_cube(2.0))
    hf = sorted(dst.mesh.all_face_ids())
    dst.mesh.face_regions = FaceRegions((FaceRegion("Brow", frozenset(hf[:2])),))
    own = dst.mesh.face_regions.regions
    ear = _add(scene, _ear(), "Ear", EAR_PLACEMENT)
    ef = sorted(ear.mesh.all_face_ids())
    ear.mesh.face_regions = FaceRegions((FaceRegion("Brow", frozenset(ef[:2])),))  # partly grouped
    plain = _add(scene, _ear(), "Lobe")  # no regions at all

    result = append_objects(dst, [ear, plain], ungrouped_region=True)

    regions = dst.mesh.face_regions
    assert [r.name for r in regions.regions] == ["Brow", f"Ear{SEP}Brow", "Ear", "Lobe"]
    assert regions.regions[:1] == own
    emap, pmap = result.face_maps[ear.id], result.face_maps[plain.id]
    assert regions.get(f"Ear{SEP}Brow").faces == {emap[f] for f in ef[:2]}
    assert regions.get("Ear").faces == {emap[f] for f in ef[2:]}
    assert regions.get("Lobe").faces == set(pmap.values())
    assert result.ungrouped_regions == {ear.id: "Ear", plain.id: "Lobe"}
    appended = set(emap.values()) | set(pmap.values())
    for face in appended:  # one region per appended face: nothing merged, nothing left out
        assert sum(face in r.faces for r in regions.regions) == 1


def test_a_fully_grouped_or_faceless_source_gets_no_extra_region():
    scene, dst = _scene(create_cube(2.0))
    ear = _add(scene, _ear(), "Ear")
    ear.mesh.face_regions = FaceRegions((FaceRegion("Ear lobe", frozenset(ear.mesh.all_face_ids())),))
    dot = Mesh()
    dot.add_vertex((5.0, 0.0, 0.0))
    point = _add(scene, dot, "Dot")
    result = append_objects(dst, [ear, point], ungrouped_region=True)
    assert [r.name for r in dst.mesh.face_regions.regions] == ["Ear lobe"]
    assert result.ungrouped_regions == {}


@pytest.mark.parametrize("taken, expected", [
    ("Ear", f"Ear{SEP}Ear"),  # any other taken name: prefixed (AD-031 §3.3)
    ("Group 1", "Group 2"),  # a taken automatic name: renumbered
])
def test_the_ungrouped_region_follows_the_collision_rule(taken, expected):
    scene, dst = _scene(create_cube(2.0))
    dst.mesh.face_regions = FaceRegions((FaceRegion(taken, frozenset(sorted(dst.mesh.all_face_ids())[:1])),))
    ear = _add(scene, _ear(), taken)
    result = append_objects(dst, [ear], ungrouped_region=True)
    assert result.ungrouped_regions == {ear.id: expected}
    assert [r.name for r in dst.mesh.face_regions.regions] == [taken, expected]


# -- symmetry -----------------------------------------------------------------------------------------------------------


def _symmetric_plane() -> Mesh:
    mesh = create_plane(2.0, 4)
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    assert mesh.symmetry_definition.seam_edges and symmetry_state(mesh) is SymmetryState.VALID
    return mesh


def _mirrored_ears(scene):
    ear = _add(scene, _ear(), "Ear", EAR_PLACEMENT, (0.1, 0.2, 0.0))
    ear2 = _add(scene, mirror_mesh(ear.mesh, X), "Ear.001")
    ear2.transform, ear2.pivot = mirror_placement(ear, X, 0.0)
    return ear, ear2


@pytest.mark.parametrize("transform, expected", [
    (None, SymmetryState.VALID),
    (ObjectTransform(translation=(0.0, 1.3, 0.0)), SymmetryState.VALID),
    (_transform((0.0, 1.0, 0.0), 0.2, (0.0, 0.0, 0.0), 1.1), SymmetryState.PARTIAL),
])
def test_mirrored_parts_keep_the_symmetry_exact_where_the_placement_allows(transform, expected):
    scene, dst = _scene(_symmetric_plane(), transform=transform)
    definition = dst.mesh.symmetry_definition
    result = append_objects(dst, list(_mirrored_ears(scene)))
    assert result.symmetry_before is SymmetryState.VALID and result.symmetry_after is expected
    assert dst.mesh.symmetry_definition == definition  # never edited


def test_one_sided_part_is_reported_partial_and_source_definitions_are_dropped():
    scene, dst = _scene(_symmetric_plane())
    definition = dst.mesh.symmetry_definition
    ear = _add(scene, _ear(), "Ear", EAR_PLACEMENT)
    ear.mesh.symmetry_definition = definition_for_axis(ear.mesh, "X")
    result = append_objects(dst, [ear])
    assert result.symmetry_after is SymmetryState.PARTIAL
    assert dst.mesh.symmetry_definition == definition


def test_a_newly_ambiguous_result_is_refused_and_rolled_back_exactly():
    scene, dst = _scene(_symmetric_plane())
    half = [f for f in dst.mesh.all_face_ids() if min(dst.mesh.vertex_position(v)[0] for v in dst.mesh.face_vertices(f)) >= 0]
    copy = _add(scene, extract_faces(dst.mesh, half).mesh, "Copy")  # exactly on top of the +X half
    before = _body(dst.mesh)
    outer = dst.mesh.begin_change()
    with pytest.raises(AssemblyRefused, match="ambiguous"):
        append_objects(dst, [copy])
    delta = dst.mesh.end_change(outer)
    assert delta.empty  # inside a caller's recording nothing remains either
    assert _body(dst.mesh) == before
    assert symmetry_state(dst.mesh) is SymmetryState.VALID


def test_existing_ambiguity_alone_is_no_reason_to_refuse():
    scene, dst = _scene(_symmetric_plane())
    some = sorted(dst.mesh.all_vertex_ids())[1]
    dst.mesh.add_vertex(dst.mesh.vertex_position(some))  # a coincident point already there
    assert symmetry_state(dst.mesh) is SymmetryState.AMBIGUOUS
    result = append_objects(dst, list(_mirrored_ears(scene)))
    assert result.symmetry_before is SymmetryState.AMBIGUOUS is result.symmetry_after


def test_worsening_an_existing_ambiguity_is_refused_and_rolled_back():
    """D4 (Manu 2026-11-10): an attached point at the mirror position of an already AMBIGUOUS point adds a candidate
    - the attached point itself is PAIRED, but the existing ambiguity gets worse: refused, nothing changed."""
    scene, dst = _scene(_symmetric_plane())
    mesh = dst.mesh
    v = next(v for v in sorted(mesh.all_vertex_ids()) if mesh.vertex_position(v)[0] > 0.1)
    x, y, z = mesh.vertex_position(v)
    mesh.add_vertex((-x, y, z))  # a second point at v's mirror: v is AMBIGUOUS already
    assert symmetry_state(mesh) is SymmetryState.AMBIGUOUS
    dot = Mesh()
    dot.add_vertex((-x, y, z))  # a third one
    part = _add(scene, dot, "Dot")
    before = _body(mesh)
    with pytest.raises(AssemblyRefused, match="ambiguous"):
        append_objects(dst, [part])
    assert _body(mesh) == before


def test_points_ambiguous_only_between_two_sources_are_refused():
    scene, dst = _scene(_symmetric_plane())

    def points(*positions):
        mesh = Mesh()
        for p in positions:
            mesh.add_vertex(p)
        return mesh

    pair, single = ((0.37, 0.11, 0.0), (-0.37, 0.11, 0.0)), ((0.37, 0.11, 0.0),)
    for alone in (pair, single):  # each source alone is fine
        other, target = _scene(_symmetric_plane())
        append_objects(target, [_add(other, points(*alone), "Part")])
    a, b = _add(scene, points(*pair), "A"), _add(scene, points(*single), "B")  # together: coincident
    before = _body(dst.mesh)
    with pytest.raises(AssemblyRefused, match="ambiguous"):
        append_objects(dst, [a, b])
    assert _body(dst.mesh) == before


# -- refusals and atomicity -------------------------------------------------------------------------------------------


def test_invalid_input_is_refused_without_any_change():
    scene, dst = _scene(create_cube(2.0))
    ear = _add(scene, _ear(), "Ear")
    twin = _add(scene, ear.mesh, "Twin")  # shares the ear's mesh
    before = dst.mesh.export_state()
    for sources, text in (([], "no source"), ([dst], "itself"), ([ear, ear], "twice"), ([ear, twin], "share")):
        with pytest.raises(AssemblyRefused, match=text):
            append_objects(dst, sources)
        assert dst.mesh.export_state() == before


def test_a_failure_during_the_writes_is_rolled_back_exactly(monkeypatch):
    scene, dst = _scene(create_cube(2.0))
    _with_targets(dst.mesh, ["Smile"])
    dst.mesh.face_regions = FaceRegions((FaceRegion("Brow", frozenset(sorted(dst.mesh.all_face_ids())[:1])),))
    ear = _add(scene, _ear(), "Ear", EAR_PLACEMENT)
    _with_targets(ear.mesh, ["Wiggle"])
    ear.mesh.face_regions = FaceRegions((FaceRegion("Brow", frozenset(ear.mesh.all_face_ids())),))
    before, src_before = _body(dst.mesh), ear.mesh.export_state()
    calls = {"n": 0}
    real = Mesh.add_face

    def failing(self, *args, **kwargs):
        calls["n"] += 1
        if self is dst.mesh and calls["n"] == 4:
            raise MeshError("injected failure")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Mesh, "add_face", failing)
    outer = dst.mesh.begin_change()
    with pytest.raises(MeshError, match="injected"):
        append_objects(dst, [ear])
    assert dst.mesh.end_change(outer).empty
    assert _body(dst.mesh) == before and ear.mesh.export_state() == src_before
    assert_mesh_invariants(dst.mesh)
    assert_layer_invariants(dst.mesh)


def test_inside_a_caller_recording_the_append_is_one_exact_delta():
    scene, dst = _scene(create_cube(2.0), transform=ROTATED)
    ear = _add(scene, _ear(), "Ear", EAR_PLACEMENT)
    _with_targets(ear.mesh, ["Wiggle"])
    before = dst.mesh.export_state()
    outer = dst.mesh.begin_change()
    append_objects(dst, [ear])
    delta = dst.mesh.end_change(outer)
    after = dst.mesh.export_state()
    dst.mesh.apply_delta(delta, reverse=True)
    assert _body(dst.mesh) == {k: v for k, v in before.items() if not k.endswith("_counter")}
    dst.mesh.apply_delta(delta)
    assert dst.mesh.export_state() == after


# -- look -----------------------------------------------------------------------------------------------------------------


def test_look_differences_name_the_sources_with_another_material_or_texture():
    scene, dst = _scene(create_cube(2.0))
    same = _add(scene, _ear(), "Same")
    other_material = _add(scene, _ear(), "Painted")
    other_material.material = ObjectMaterial((0.8, 0.2, 0.2), 0.3, 0.4)
    other_texture = _add(scene, _ear(), "Textured")
    other_texture.texture = "skin.png"
    assert look_differences(dst, [other_texture, same, other_material]) == (other_material, other_texture)
    dst.material = other_material.material
    assert look_differences(dst, [other_material]) == ()


# -- extract --------------------------------------------------------------------------------------------------------------


def _rich_mesh() -> Mesh:
    mesh = create_plane(2.0, 4)
    for i, f in enumerate(sorted(mesh.all_face_ids())):
        if i % 3:
            mesh.set_face_uvs(f, tuple((0.1 * i + c, 0.05 * c) for c in range(4)))
    rng = random.Random(7)
    _with_targets(mesh, ["Smile", "Blink"])
    skin = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in mesh.all_vertex_ids():
        if rng.random() < 0.6:
            mesh.set_layer_value(skin, v, ((rng.randrange(5), rng.uniform(0.1, 0.5)),))
    faces = sorted(mesh.all_face_ids())
    mesh.face_regions = FaceRegions((
        FaceRegion("Brow", frozenset(faces[:3])), FaceRegion("Jaw", frozenset(faces[10:])), FaceRegion("Lip", frozenset(faces[5:7]))
    ))
    return mesh


def test_extract_copies_the_faces_with_every_layer_uv_and_region():
    mesh = _rich_mesh()
    chosen = sorted(mesh.all_face_ids())[1:6]
    before = mesh.export_state()
    result = extract_faces(mesh, chosen)
    out, vmap, fmap = result.mesh, result.vertex_map, result.face_map
    assert mesh.export_state() == before  # the source is only read
    assert sorted(fmap) == chosen and len(out.all_face_ids()) == len(chosen)
    assert set(vmap) == {v for f in chosen for v in mesh.face_vertices(f)}
    for v, w in vmap.items():
        assert out.vertex_position(w) == mesh.vertex_position(v)  # same object space, bit-identical
    for f, g in fmap.items():
        assert out.face_vertices(g) == [vmap[v] for v in mesh.face_vertices(f)]
        assert out.face_uvs(g) == mesh.face_uvs(f)
    assert [out.point_layer_info(l) for l in out.point_layer_ids()] == [mesh.point_layer_info(l) for l in mesh.point_layer_ids()]
    for old, new in zip(mesh.point_layer_ids(), out.point_layer_ids()):
        assert out.layer_items(new) == sorted((vmap[v], val) for v, val in mesh.layer_items(old) if v in vmap)
    assert [(r.name, r.faces) for r in out.face_regions.regions] == [
        ("Brow", frozenset(fmap[f] for f in chosen[:2])), ("Lip", frozenset(fmap[f] for f in chosen[4:]))
    ]  # "Jaw" has no extracted face: it stays with the source only
    assert out.symmetry_definition is None
    assert_mesh_invariants(out)
    assert_layer_invariants(out)
    assert_uv_invariants(out)


def test_extract_shares_nothing_with_the_source():
    mesh = create_plane(2.0, 2)
    result = extract_faces(mesh, sorted(mesh.all_face_ids())[:1])
    before = mesh.export_state()
    for v in result.mesh.all_vertex_ids():
        result.mesh.set_vertex_position(v, (9.0, 9.0, 9.0))
    result.mesh.delete_faces(result.mesh.all_face_ids())
    assert mesh.export_state() == before


def test_extract_refuses_no_face_and_unknown_faces():
    mesh = create_plane(2.0, 2)
    with pytest.raises(AssemblyRefused, match="no face"):
        extract_faces(mesh, [])
    with pytest.raises(AssemblyRefused, match="unknown"):
        extract_faces(mesh, [type(mesh.all_face_ids()[0])(999)])


def test_extract_then_append_reproduces_the_part():
    """The Detach -> Attach round trip of the kernel: the same faces, positions, UVs and target offsets."""
    mesh = _rich_mesh()
    chosen = sorted(mesh.all_face_ids())[4:9]
    part = extract_faces(mesh, chosen)
    scene, dst = _scene(Mesh())
    holder = _add(scene, part.mesh, "Part")
    result = append_objects(dst, [holder])
    vmap = {v: result.vertex_maps[holder.id][w] for v, w in part.vertex_map.items()}
    for f in chosen:
        g = result.face_maps[holder.id][part.face_map[f]]
        assert dst.mesh.face_vertices(g) == [vmap[v] for v in mesh.face_vertices(f)]
        assert dst.mesh.face_uvs(g) == mesh.face_uvs(f)
    for v, w in vmap.items():
        assert dst.mesh.vertex_position(w) == mesh.vertex_position(v)
    smile = mesh.point_layer_ids()[0]
    carried = result.layer_maps[holder.id][part.mesh.point_layer_ids()[0]]
    assert dst.mesh.point_layer_info(carried).name == f"Part{SEP}Smile"  # identity is never assumed by name
    assert all(dst.mesh.layer_value(carried, w) == mesh.layer_value(smile, v) for v, w in vmap.items())


# -- derived symmetry (Detach's definition, AD-031 §3.5) -----------------------------------------------------------------


def test_derived_symmetry_follows_shift_s_and_requires_a_valid_result():
    mesh = _symmetric_plane()
    faces = sorted(mesh.all_face_ids())
    centre = [f for f in faces if any(mesh.vertex_position(v)[0] == 0.0 for v in mesh.face_vertices(f))]
    both = extract_faces(mesh, centre).mesh  # crosses the plane, symmetric
    definition = derived_symmetry(both, "X")
    assert definition is not None and definition.seam_edges
    assert definition == definition_for_axis(both, "X")
    assert both.symmetry_definition is None  # the mesh is left as it was
    one_side = extract_faces(mesh, [f for f in centre if max(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0]).mesh
    assert derived_symmetry(one_side, "X") is None
    assert derived_symmetry(both, None) is None


def test_derived_symmetry_of_a_mirrored_pair_away_from_the_plane_has_an_empty_seam():
    scene, dst = _scene(_symmetric_plane())
    ear, ear2 = _mirrored_ears(scene)
    result = append_objects(dst, [ear, ear2])
    islands = list(result.face_maps[ear.id].values()) + list(result.face_maps[ear2.id].values())
    pair = extract_faces(dst.mesh, islands).mesh
    definition = derived_symmetry(pair, "X")
    assert definition is not None and definition.seam_edges == frozenset()
    pair.symmetry_definition = definition
    assert symmetry_state(pair) is SymmetryState.VALID


# -- linked faces (Select Linked, Separate by Islands; AD-031 P3) --------------------------------------------------------


def test_linked_faces_follow_shared_edges_only():
    mesh = create_plane(2.0, 3)
    cube = create_cube(0.5)
    ids = {v: mesh.add_vertex(tuple(p + d for p, d in zip(cube.vertex_position(v), (3.0, 0.0, 0.0))))
           for v in cube.all_vertex_ids()}
    island = {mesh.add_face([ids[v] for v in cube.face_vertices(f)]) for f in cube.all_face_ids()}
    plane = set(mesh.all_face_ids()) - island
    before = mesh.export_state()
    assert linked_faces(mesh, [min(plane)]) == frozenset(plane)
    assert linked_faces(mesh, [min(plane), min(island)]) == frozenset(plane | island)
    assert linked_faces(mesh, []) == frozenset()
    assert linked_faces(mesh, [type(min(plane))(999)]) == frozenset()  # an invalid seed is ignored
    assert mesh.export_state() == before  # read-only
    corner = Mesh()  # two quads touching only at a corner: two islands
    a = [corner.add_vertex(p) for p in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))]
    b = [a[2]] + [corner.add_vertex(p) for p in ((2, 1, 0), (2, 2, 0), (1, 2, 0))]
    fa, fb = corner.add_face(a), corner.add_face(b)
    assert linked_faces(corner, [fa]) == frozenset({fa}) and linked_faces(corner, [fb]) == frozenset({fb})
