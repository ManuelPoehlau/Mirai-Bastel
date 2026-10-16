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
    MESSAGE_TOPOLOGY,
    MorphSurfaceProvider,
    blend,
    evaluate,
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
