"""The evaluation and the provider without `Application` (review CLAUDE-001 F-1, F-8, R-7).

`blend` is exact at 0 % and 100 % and wherever base and target agree, and exactly mirrored; the
provider never writes base or target, never wakes itself with its own status post, and switches
off instead of drawing a surface for diverged topology.
"""

from __future__ import annotations

import random

from core.ids import ObjectId
from core.mesh import Mesh
from core.scene import Scene, SceneObject
from mirai.scene_factory import mesh_from_positions_and_faces

from morph_lab.morph import (
    MESSAGE_JAW_REGION,
    MESSAGE_TOPOLOGY,
    MorphSurfaceProvider,
    blend,
    evaluate,
    jaw_weights,
    pose_jaw,
    topology_signature,
)


def _grid() -> Mesh:
    positions = [(float(x), float(y), 0.0) for y in range(3) for x in range(-1, 2)]
    faces = [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]]
    return mesh_from_positions_and_faces(positions, faces)


def _pair():
    base = _grid()
    target = Mesh.from_state(base.export_state())
    for vid in target.all_vertex_ids():
        x, y, z = target.vertex_position(vid)
        target.set_vertex_position(vid, (x * 1.3, y + 0.1 * x * x, z + 0.37 * y))
    scene = Scene.from_objects(
        [SceneObject(ObjectId(0), base, name="b"), SceneObject(ObjectId(1), target, name="t")],
        edit_object_id=ObjectId(0),
        object_id_counter=2,
    )
    return scene, base, target


class _Status:
    def __init__(self) -> None:
        self.serial = 0
        self.posts: list[str] = []

    def post(self, text: str) -> None:
        self.posts.append(text)
        self.serial += 1


def _provider(scene, status=None):
    status = status or _Status()
    return MorphSurfaceProvider(scene, ObjectId(0), ObjectId(1), post=status.post, serial=lambda: status.serial), status


def _random_point(rng) -> tuple:
    return tuple(rng.uniform(-1.0, 1.0) * 10.0 ** rng.randint(-6, 1) for _ in range(3))


def test_blend_is_exact_at_both_ends_and_where_base_equals_target():
    rng = random.Random(7)
    for _ in range(5000):
        b, t = _random_point(rng), _random_point(rng)
        assert blend(b, t, 0) == b
        assert blend(b, t, 100) == t
        for k in (1, 33, 50, 99):
            assert blend(b, b, k) == b


def test_blend_is_exactly_mirrored():
    rng = random.Random(11)
    for _ in range(5000):
        b, t = _random_point(rng), _random_point(rng)
        k = rng.randint(0, 100)
        mb, mt = (-b[0], b[1], b[2]), (-t[0], t[1], t[2])
        p, q = blend(b, t, k), blend(mb, mt, k)
        assert q == (-p[0], p[1], p[2])


def test_signature_ignores_container_order_and_catches_divergence():
    base = _grid()
    copy = Mesh.from_state(base.export_state())
    assert topology_signature(copy) == topology_signature(base)
    edge = sorted(copy.all_edge_ids())[0]
    copy.split_edge(edge)
    assert topology_signature(copy) != topology_signature(base)
    # The same split on the base hands out the same new IDs: signatures agree again, which is
    # correct - the topology is ID-identical (review R-3).
    base.split_edge(edge)
    assert topology_signature(copy) == topology_signature(base)


def test_provider_shows_the_formula_and_never_writes_base_or_target():
    scene, base, target = _pair()
    before = (base.export_state(), target.export_state())
    provider, _status = _provider(scene)
    assert provider.sync(base, None) == set()
    assert provider.surface_mesh is None  # 0 %: the base is drawn as itself (F-3)
    for k in (100, 37, 1, 100, 0, 64):
        provider.set_weight(k)
        provider.sync(base, None)
        if k == 0:
            assert provider.surface_mesh is None
            continue
        want = evaluate(base, target, k)
        surface = provider.surface_mesh
        assert {v: surface.vertex_position(v) for v in surface.all_vertex_ids()} == want
    assert (base.export_state(), target.export_state()) == before


def test_provider_returns_only_changed_vertices():
    scene, base, target = _pair()
    keep = sorted(base.all_vertex_ids())[0]
    target.set_vertex_position(keep, base.vertex_position(keep))
    provider, _status = _provider(scene)
    provider.set_weight(40)
    provider.sync(base, None)  # builds the surface
    provider.set_weight(70)
    moved = provider.sync(base, None)
    differ = {v for v in base.all_vertex_ids() if base.vertex_position(v) != target.vertex_position(v)}
    assert keep not in differ and len(differ) > 3
    assert moved == differ
    assert provider.sync(base, None) == set()


def test_diverged_topology_is_reported_once_and_never_wakes_the_provider_itself():
    scene, base, target = _pair()
    target.split_edge(sorted(target.all_edge_ids())[0])
    provider, status = _provider(scene)
    provider.set_weight(50)
    provider.sync(base, None)
    assert status.posts == [MESSAGE_TOPOLOGY]
    assert not provider.dirty  # its own post is no wake-up (review F-1)
    for _ in range(30):
        if provider.dirty:
            provider.sync(base, None)
    assert provider.surface_mesh is None
    assert status.posts == [MESSAGE_TOPOLOGY]
    assert not provider.dirty


def test_a_foreign_status_wakes_the_provider_and_rereads_the_target():
    scene, base, target = _pair()
    provider, status = _provider(scene)
    provider.set_weight(100)
    provider.sync(base, None)
    vid = sorted(target.all_vertex_ids())[0]
    target.set_vertex_position(vid, (5.0, 5.0, 5.0))  # e.g. Apply/Undo on the non-edit target
    provider.sync(base, None)
    assert provider.surface_mesh.vertex_position(vid) != (5.0, 5.0, 5.0)  # not re-read yet
    status.post("Undo")
    assert provider.dirty
    provider.sync(base, None)
    assert provider.surface_mesh.vertex_position(vid) == (5.0, 5.0, 5.0)


def test_editing_the_target_shows_it_as_itself():
    scene, base, target = _pair()
    provider, _status = _provider(scene)
    provider.set_weight(50)
    provider.sync(target, None)
    assert provider.surface_mesh is None and provider.editing == "target"


def test_target_is_relative_to_the_base_it_was_shaped_against():
    scene, base, target = _pair()
    vids = sorted(base.all_vertex_ids())
    for vid in vids[:4]:  # the target: a smile on top of the original base
        x, y, z = target.vertex_position(vid)
        target.set_vertex_position(vid, (x, y + 0.5, z))
    provider, _status = _provider(scene)
    provider.sync(base, None)  # 0 %: the reference is taken here, before the base changes
    original = {v: base.vertex_position(v) for v in vids}
    for vid in vids[2:6]:  # the base is edited afterwards
        x, y, z = base.vertex_position(vid)
        base.set_vertex_position(vid, (x + 0.25, y, z))
    provider.set_weight(100)
    provider.sync(base, None)
    surface = provider.surface_mesh
    for vid in vids:
        b, t, o = base.vertex_position(vid), target.vertex_position(vid), original[vid]
        want = t if b == o else tuple(bi + (ti - oi) for bi, ti, oi in zip(b, t, o))
        assert surface.vertex_position(vid) == want


def test_reshaping_the_target_takes_a_new_reference():
    scene, base, target = _pair()
    provider, _status = _provider(scene)
    provider.set_weight(100)
    provider.sync(base, None)
    vid = sorted(base.all_vertex_ids())[0]
    x, y, z = base.vertex_position(vid)
    base.set_vertex_position(vid, (x + 1.0, y, z))
    provider.sync(target, None)  # the artist now edits the target ...
    target.set_vertex_position(vid, (x + 1.0, y + 0.5, z))  # ... against the base as it is now
    provider.sync(base, None)
    assert provider.surface_mesh.vertex_position(vid) == target.vertex_position(vid)


# -- jaw pose --------------------------------------------------------------------------


def _jaw_scene():
    """The grid as a 'head' whose two lower faces (y 0..1) are the jaw group."""
    from core.mesh import FaceRegion, FaceRegions

    scene, base, target = _pair()
    jaw = frozenset(f for f in base.all_face_ids() if max(base.vertex_position(v)[1] for v in base.face_vertices(f)) <= 1.0)
    base.face_regions = FaceRegions((FaceRegion("Kiefer", jaw),))
    return scene, base, target, jaw


def _row(mesh, y):
    return [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[1] == y]


def test_pose_jaw_turns_about_the_x_axis_and_opens_a_plus_z_jaw():
    pivot = (0.0, 1.0, 0.0)
    assert pose_jaw((0.5, 1.0, 0.0), pivot, 30, 1.0) == (0.5, 1.0, 0.0)
    x, y, z = pose_jaw((0.5, 1.0, 2.0), pivot, 90, 1.0)
    assert (x, round(y, 9), round(z, 9)) == (0.5, 1.0 - 2.0, 0.0)  # front of the jaw swings down
    assert pose_jaw((0.5, 1.0, 2.0), pivot, 90, 0.0) == (0.5, 1.0, 2.0)


def test_jaw_weights_are_one_in_the_group_and_fall_off_outside():
    _scene, base, _target, jaw = _jaw_scene()
    weights = jaw_weights(base, next(r for r in base.face_regions.regions if r.faces == jaw))
    in_group = {v for f in jaw for v in base.face_vertices(f)}
    assert all(weights[v] == 1.0 for v in in_group)
    top = _row(base, 2.0)
    assert all(0.0 < weights[v] < 1.0 for v in top)


def test_without_a_pose_or_a_weight_there_is_no_surface_and_the_pose_needs_the_group():
    scene, base, _target, _jaw = _jaw_scene()
    provider, status = _provider(scene)
    assert provider.sync(base, None) == set() and provider.surface_mesh is None
    base.face_regions = None
    provider.set_jaw_angle(20)
    provider.sync(base, None)
    assert provider.message == MESSAGE_JAW_REGION
    assert all(provider.surface_mesh.vertex_position(v) == base.vertex_position(v) for v in base.all_vertex_ids())
    assert status.posts == [MESSAGE_JAW_REGION]


def test_pose_moves_the_jaw_only_and_never_writes_the_base():
    scene, base, target, jaw = _jaw_scene()
    before = {v: base.vertex_position(v) for v in base.all_vertex_ids()}
    provider, _status = _provider(scene)
    provider.set_jaw_angle(30)
    provider.set_jaw_pivot((0.0, 2.0, 0.0))
    provider.sync(base, None)
    surface = provider.surface_mesh
    assert surface is not None
    assert {v: base.vertex_position(v) for v in base.all_vertex_ids()} == before
    for v in _row(base, 0.0):
        assert surface.vertex_position(v) != before[v]
    for v in _row(base, 2.0):  # outside the group but in the falloff: weights < 1, still moved
        assert surface.vertex_position(v)[0] == before[v][0]
    provider.set_jaw_angle(0)
    provider.sync(base, None)
    assert provider.surface_mesh is None


def test_pose_rides_on_the_morph_not_the_other_way_round():
    scene, base, target, _jaw = _jaw_scene()
    provider, _status = _provider(scene)
    provider.set_jaw_pivot((0.0, 2.0, 0.0))
    provider.set_weight(100)
    provider.sync(base, None)
    morphed = {v: provider.surface_mesh.vertex_position(v) for v in base.all_vertex_ids()}
    assert morphed == {v: target.vertex_position(v) for v in base.all_vertex_ids()}
    provider.set_jaw_angle(25)
    provider.sync(base, None)
    for v in _row(base, 0.0):
        expected = pose_jaw(morphed[v], (0.0, 2.0, 0.0), 25, 1.0)
        assert provider.surface_mesh.vertex_position(v) == expected
