"""O3 stage 2 (AD-032 §11, 2026-11-13): the stages' position tables on arrays.

What is pinned here (the stages' results themselves stay pinned by the randomized oracles of `test_morph_multi.py` and
`test_skin_stage.py`, bit-identical to `morph_mix.evaluate` / `skinning.evaluate`):

- the journal of a `SurfacePositions` (§11.1): position writes as slot chunks, `change.vertices` the same dict a
  per-vertex journal held (checked against such a reference through random writes, topology edits and takes),
  `slot_moves()` only for pure moves under the current slot mapping, chunks resolving to their own vertices after a
  slot is reused, bounded memory for a watch nobody takes, `MovedVertices` as a lazy read-only set;
- the skin's table mirrors the mix's slots (§11.2), through weights, poses, topology edits and Undo / Redo;
- the hand-over (§11.3): a `RenderMesh` over a stage's table takes pure moves through its slot map - no
  `vertex_position`, no `_read_moved` - and still equals a fresh build after every step; in the app a pose step and a
  weight step read no position of a stage table one by one.
"""

from __future__ import annotations

import math
import random
import struct

import pytest

import tests._bootstrap  # noqa: F401

import viewport.render_mesh as render_mesh_module
from core import BoneId, LayerKind, PointLayerInfo
from core.mesh import MeshError
from core.operations.collapse import collapse_elements
from mirai import morph_mix, skinning
from mirai import surface_positions as sp
from mirai.morph_mix import MixSurface
from mirai.scene_factory import mesh_from_positions_and_faces
from mirai.skinning import BonePose, SkinSurface
from mirai.surface_positions import MovedVertices, SurfacePositions
from tests.test_application_delete_dissolve import _app
from tests.test_morph_multi import _targets
from tests.test_render_mesh_incremental import _grid, assert_equivalent
from tests.test_skin_stage import _bind, _bone_pose, _rig, _setup
from viewport.render_mesh import RenderMesh
from viewport.resource_store import TraceStore


def _write(view: SurfacePositions, rng: random.Random, share: float = 0.4) -> None:
    """A random owner write: new rows for a share of the held vertices (some equal to the old one)."""
    items = []
    for v in view.base.all_vertex_ids():
        if v in view._index and rng.random() < share:
            p = view.vertex_position(v)
            items.append((v, p if rng.random() < 0.2 else tuple(c + rng.uniform(-0.3, 0.3) for c in p)))
    rng.shuffle(items)
    view._owner_write(items)


class _Reference:
    """The journal of the tuple table (O1): per watch a dict, first record wins, before = the old position / None."""

    def __init__(self) -> None:
        self.vertices: dict = {}
        self.edges: dict = {}
        self.faces: dict = {}

    def merge(self, records: dict, edges=(), faces=()) -> None:
        for target, new in ((self.vertices, records), (self.edges, dict(edges)), (self.faces, dict(faces))):
            for k, r in new.items():
                target.setdefault(k, r)


def test_writes_are_slot_chunks_and_the_dict_is_built_on_demand():
    base = _grid(3)
    view = SurfacePositions(base)
    watch = view.watch()
    v0, v1, v2 = base.all_vertex_ids()[:3]
    p0, p1 = view.vertex_position(v0), view.vertex_position(v1)
    assert view._owner_write([(v1, (1.0, 2.0, 3.0)), (v0, (4.0, 5.0, 6.0)), (v2, view.vertex_position(v2))]) == {v0, v1}
    view._owner_write([(v0, (7.0, 8.0, 9.0))])
    change = watch.peek()
    assert len(change._entries) == 2 and all(isinstance(e, sp._Chunk) for e in change._entries)
    assert not change.is_empty() and len(change._entries) == 2  # is_empty builds no dict
    assert change.slot_moves().tolist() == sorted([view._index[v0], view._index[v1]])
    change = watch.take()
    assert change.vertices == {v0: p0, v1: p1}  # the position at the last take
    assert watch.peek().is_empty() and watch.peek().slot_moves().tolist() == []
    assert view.vertex_position(v0) == (7.0, 8.0, 9.0) and type(view.vertex_position(v0)[0]) is float
    assert view.position_array()[view._index[v0]].tolist() == [7.0, 8.0, 9.0]
    with pytest.raises(ValueError):
        view.position_array()[0, 0] = 1.0  # the hand-over is read-only


def test_the_journal_equals_a_per_vertex_journal_through_random_updates():
    rng = random.Random(11)
    base = _grid(4)
    view = SurfacePositions(base)
    watches = {0: view.watch(), 1: view.watch()}
    refs = {0: _Reference(), 1: _Reference()}
    for step in range(300):
        op = rng.randrange(6)
        before = view.positions()
        if op <= 2:
            _write(view, rng)
            after = view.positions()
            moved = {v: before[v] for v in after if after[v] != before[v]}
            for ref in refs.values():
                ref.merge(moved)
        elif op == 3:  # a topology edit: split or collapse, the table follows, new vertices are written
            keys = base.watch()
            try:
                if rng.random() < 0.5:
                    base.split_edge(rng.choice(base.all_edge_ids()), 0.5)
                else:
                    collapse_elements(base, base.edge_vertices(rng.choice(base.all_edge_ids())))
            except MeshError:
                continue
            change = keys.take()
            view._owner_follow_topology(change)
            gone = {v: before[v] for v in change.vertices if v in before and not base.is_valid_vertex(v)}
            new = [v for v in change.vertices if base.is_valid_vertex(v) and v not in before]
            view._owner_write([(v, base.vertex_position(v)) for v in new])
            for ref in refs.values():
                ref.merge(gone, change.edges, change.faces)
                ref.merge(dict.fromkeys(new))
        elif op == 4:  # a take
            key = rng.choice(list(watches))
            got = watches[key].take()
            ref = refs[key]
            moves = got.slot_moves()
            assert got.vertices == ref.vertices, step
            assert got.edges == ref.edges and got.faces == ref.faces
            if moves is not None:  # only pure moves of held vertices, under the current slot mapping
                assert not got.edges and not got.faces and all(b is not None for b in ref.vertices.values())
                assert sorted(view._slot_vertex[s] for s in moves.tolist()) == sorted(ref.vertices)
            refs[key] = _Reference()
        elif rng.random() < 0.3:  # a watch comes or goes
            key = max(watches) + 1
            watches[key], refs[key] = view.watch(), _Reference()
            if len(watches) > 3:
                old = min(watches)
                watches.pop(old).close()
                refs.pop(old)
    assert len(view._logs) == len(watches)


def test_a_chunk_resolves_to_its_own_vertices_after_its_slot_is_reused():
    base = _grid(3)
    view = SurfacePositions(base)
    watch = view.watch()
    inner = base.all_vertex_ids()[4]
    old = view.vertex_position(inner)
    view._owner_write([(inner, (9.0, 9.0, 9.0))])  # a chunk on inner's slot
    slot = view._index[inner]
    keys = base.watch()
    base.delete_vertices([inner])
    view._owner_follow_topology(keys.take())
    keys = base.watch()
    new_v, _, _ = base.split_edge(base.all_edge_ids()[0], 0.5)
    view._owner_follow_topology(keys.take())
    view._owner_write([(new_v, base.vertex_position(new_v))])
    assert view._index[new_v] == slot  # the freed slot is reused
    change = watch.take()
    assert change.slot_moves() is None  # records by id: the reader reads the dict
    assert change.vertices[inner] == old and change.vertices[new_v] is None


def test_a_vertex_new_and_gone_in_one_window_keeps_its_first_record():
    base = _grid(3)
    view = SurfacePositions(base)
    watch = view.watch()
    keys = base.watch()
    new_v, _, _ = base.split_edge(base.all_edge_ids()[0], 0.5)
    view._owner_follow_topology(keys.take())
    view._owner_write([(new_v, base.vertex_position(new_v))])  # recorded by id: None
    keys = base.watch()
    collapse_elements(base, base.edge_vertices(base.vertex_edges(new_v)[0]))
    change = keys.take()
    assert not base.is_valid_vertex(new_v)
    view._owner_follow_topology(change)  # gone: recorded by id with its last position - the first record wins
    got = watch.take()
    assert new_v in got.vertices and got.vertices[new_v] is None


def test_a_watch_nobody_takes_stays_bounded():
    base = _grid(3)
    view = SurfacePositions(base)
    lazy = view.watch()
    first = view.positions()
    rng = random.Random(3)
    ever: set = set()
    limit = max(view.capacity, 1024)
    for _ in range(600):  # far more chunk rows than the table has slots
        before = view.positions()
        _write(view, rng, share=0.9)
        ever |= {v for v, p in view.positions().items() if p != before[v]}
        change = lazy.peek()
        assert change._rows <= limit + view.capacity  # merged once past the limit: O(table), not O(writes)
    assert change.vertices == {v: first[v] for v in ever}


def test_moved_vertices_is_a_lazy_read_only_set():
    base = _grid(3)
    view = SurfacePositions(base)
    ids = base.all_vertex_ids()
    changed = view._owner_write([(ids[1], (1.0, 1.0, 1.0)), (ids[5], (2.0, 2.0, 2.0))])
    slots = sp.np.asarray(sorted(view._index[v] for v in changed))
    moved = view._owner_moved(slots)
    assert isinstance(moved, MovedVertices) and len(moved) == 2 and moved._ids is None  # len / bool build nothing
    assert moved and moved == {ids[1], ids[5]} and ids[1] in moved and set(moved) == {ids[1], ids[5]}
    assert not view._owner_moved(slots[:0])
    # the slot list it reads is never changed under it: the next mapping change copies it first
    keys = base.watch()
    base.delete_vertices([ids[4]])
    view._owner_follow_topology(keys.take())
    assert moved == {ids[1], ids[5]}


# -- the stages and the hand-over -------------------------------------------------------------------------


def _bits(p) -> bytes:
    return struct.pack("<3d", *p)


def test_signed_zeros_and_the_rules_summation_order_hold_bit_for_bit():
    """What `==` cannot see: the mix's first term is not added to 0.0 (b = -0.0, d = -0.0 stays -0.0), and the skin's
    rest weight is `1.0 - math.fsum(...)`, not a running sum (0.1 + 0.2 + 0.3 != fsum)."""
    mesh = mesh_from_positions_and_faces(
        [(-0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0)],
        [(0, 1, 2, 3), (1, 4, 5, 2)])
    ids = mesh.all_vertex_ids()
    lid = mesh.add_point_layer(PointLayerInfo("T", LayerKind.VECTOR))
    mesh.set_layer_value(lid, ids[0], (-0.0, 0.5, 0.0))
    mesh.set_layer_value(lid, ids[2], (0.25, -0.0, 0.5))
    mix = MixSurface(mesh)
    mix.update({lid: 100})
    expected = morph_mix.evaluate(mesh, {lid: 100})
    assert math.copysign(1.0, expected[ids[0]][0]) < 0  # the case exists
    for v in ids:
        assert _bits(mix.mesh.vertex_position(v)) == _bits(expected[v]), v
    rig = _rig(mesh)
    weights = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    mesh.set_layer_value(weights, ids[1], [(0, 0.1), (1, 0.2), (2, 0.3)])
    assert 1.0 - math.fsum((0.1, 0.2, 0.3)) != 1.0 - (0.1 + 0.2 + 0.3)
    skin = SkinSurface(mesh, mix.mesh)
    pose = {BoneId(b): _bone_pose(random.Random(b)) for b in range(3)}
    skin.update(rig, pose, None)
    expected = skinning.evaluate(mesh, morph_mix.evaluate(mesh, {lid: 100}), rig, pose)
    for v in ids:
        assert _bits(skin.mesh.vertex_position(v)) == _bits(expected[v]), v


def test_a_table_render_mesh_patches_faces_the_host_did_not_report(_incremental):
    """A face change on the table's journal that the host never marked (only moves later) is still patched: a change
    with element records is never taken for pure moves."""
    app = _app(4)
    mesh = app.scene.mesh
    lids = _targets(app, 1, seed=2, every=1)
    mix = MixSurface(mesh)
    mix.update({lids[0]: 40})
    rm = RenderMesh(mix.mesh, overlay=None, store_type=TraceStore)
    face = next(f for f in mesh.all_face_ids() if len(mesh.face_vertices(f)) >= 4)
    a, _, c = mesh.face_vertices(face)[:3]
    app.apply_mesh_change("connect", lambda: mesh.connect_vertices(face, a, c) and None)
    mix.update({lids[0]: 40})  # the table follows; the host reports nothing
    _, moved = mix.update({lids[0]: 70})
    assert moved
    rm.mark_vertices_dirty(moved)  # only moves reported
    rm.sync()
    assert_equivalent(rm)



@pytest.fixture
def _incremental(monkeypatch):
    monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 0)
    monkeypatch.setattr(render_mesh_module, "SPARE_FRACTION", 0.5)


def _assert_vertex_data(rm: RenderMesh) -> None:
    """Positions, vertex normals and face normals equal a fresh build's (bit for bit), whatever the triangulation."""
    fresh = RenderMesh(rm.mesh, overlay=None, store_type=TraceStore)
    data, ref = rm.store.data, fresh.store.data
    for name in ("positions", "normals"):
        mine, theirs = data(name), ref(name)
        for v in rm.mesh.all_vertex_ids():
            i, j = rm.vertex_index_of(v), fresh.vertex_index_of(v)
            assert mine[3 * i:3 * i + 3] == theirs[3 * j:3 * j + 3], (name, v)
    assert rm.derived.face_normals == fresh.derived.face_normals
    assert rm.derived.vertex_normals == fresh.derived.vertex_normals


def _assert_maps(rm: RenderMesh) -> None:
    """The table <-> render slot maps of a RenderMesh over a table name exactly its vertices."""
    table = rm.mesh
    for v, slot in rm._vertex_index.items():
        t = table._index[v]
        assert rm._table_render[t] == slot and rm._render_table[slot] == t
    mapped = sp.np.flatnonzero(rm._table_render >= 0)  # no entry left for a vertex that went
    assert sorted(rm._slot_vertex[s] for s in rm._table_render[mapped].tolist()) == sorted(rm._vertex_index)


@pytest.mark.parametrize("seed", range(4))
def test_the_skin_mirrors_the_mix_and_its_render_mesh_takes_moves_as_arrays(_incremental, monkeypatch, seed):
    app = _app(4)
    mesh = app.scene.mesh
    rng = random.Random(seed)
    _bind(mesh, rng)  # before the targets: an Undo of a target's creation keeps the weights layer
    lids = _targets(app, 2, seed=seed, every=1)
    rig = _rig(mesh)
    mix = MixSurface(mesh)
    mix.update({lids[0]: 60})
    skin = SkinSurface(mesh, mix.mesh)
    pose = {BoneId(1): _bone_pose(rng)}
    skin.update(rig, pose, None)
    rm = RenderMesh(skin.mesh, overlay=None, store_type=TraceStore)
    reads = {"vertex_position": 0, "read_moved": 0}
    original_position, original_read = SurfacePositions.vertex_position, RenderMesh._read_moved

    def counted_position(self, v):
        reads["vertex_position"] += 1
        return original_position(self, v)

    def counted_read(self, moved):
        reads["read_moved"] += 1
        return original_read(self, moved)

    monkeypatch.setattr(SurfacePositions, "vertex_position", counted_position)
    monkeypatch.setattr(RenderMesh, "_read_moved", counted_read)
    weights = {lids[0]: 60}
    pure_moves = 0
    for step in range(80):
        op = rng.randrange(8)
        if op <= 2:
            pose = {BoneId(b): _bone_pose(rng) if rng.random() < 0.8 else BonePose() for b in rng.sample(range(3), 2)}
        elif op == 3:
            weights = {lid: rng.choice((0, 30, 100)) for lid in lids}
        elif op == 4:
            app.apply_mesh_change("split", lambda: mesh.split_edge(rng.choice(mesh.all_edge_ids())) and None)
        elif op == 5:
            try:
                app.apply_mesh_change(
                    "collapse", lambda: collapse_elements(mesh, mesh.edge_vertices(rng.choice(mesh.all_edge_ids())))
                    and None)
            except Exception:  # noqa: BLE001 - a refused collapse changes nothing
                pass
        elif op == 6 and app.history.can_undo():
            app.history.undo()
        mix.update(weights)
        rebuilt, moved = skin.update(rig, pose, None)
        assert not rebuilt
        assert skin.mesh._index == mix.mesh._index  # the skin's table mirrors the mix's slots
        assert skin.mesh.positions() == skinning.evaluate(mesh, morph_mix.evaluate(mesh, mix.weights), rig, pose)
        reads["vertex_position"] = reads["read_moved"] = 0
        if skin.topology_changed:
            rm.mark_topology_dirty()
        elif moved:
            rm.mark_vertices_dirty(moved)
        pure = not skin.topology_changed and bool(moved) and rm._watch.peek().slot_moves() is not None
        rm.sync()
        if pure:
            pure_moves += 1
            assert reads == {"vertex_position": 0, "read_moved": 0}  # no read per vertex (§11.3)
        if skin.topology_changed:
            assert_equivalent(rm)  # the faces around every vertex moved since are re-triangulated now
        else:
            # A move does not re-triangulate (a pose can make a quad concave, "ein W-Drag trianguliert nicht"): the
            # vertex data equals a fresh build; the triangles follow at the next topology sync (checked whole then).
            _assert_vertex_data(rm)
        _assert_maps(rm)
        assert rm.stats.counters.get("table_map_misses", 0) == 0
    assert pure_moves > 10


def test_a_pose_step_and_a_weight_step_read_no_table_position_one_by_one(monkeypatch):
    """Through the app (the D3 scenario in small): Morph + Skin shown, a pose step and a morph weight step each sync
    the stages and the surface RenderMesh on arrays - no `vertex_position` of a stage table, no `_read_moved`."""
    app, mesh, lid, rng = _setup(5, seed=2)
    lids = _targets(app, 1, seed=4, every=1)
    app.set_morph_weight(60, lids[0])
    skin = app.skin.provider
    skin.set_pose({BoneId(1): _bone_pose(rng)})
    app.update_viewport(0.0)
    app.update_viewport(0.0)
    rm = app.viewport.surface_render_mesh
    assert rm is not None and rm.mesh is skin.surface_mesh and isinstance(rm.mesh, SurfacePositions)
    calls: list = []
    original_position, original_read = SurfacePositions.vertex_position, RenderMesh._read_moved

    def counted_position(self, v):
        calls.append("vertex_position")
        return original_position(self, v)

    def counted_read(self, moved):
        if isinstance(self.mesh, SurfacePositions):
            calls.append("read_moved")
        return original_read(self, moved)

    monkeypatch.setattr(SurfacePositions, "vertex_position", counted_position)
    monkeypatch.setattr(RenderMesh, "_read_moved", counted_read)
    vertex_updates = rm.stats.counters.get("vertex_updates", 0)
    for step in range(4):
        skin.set_pose({BoneId(1): _bone_pose(rng)})  # a pose step
        app.update_viewport(0.0)
        app.set_morph_weight(61 + step, lids[0])  # a weight step: the mix moves, the skin follows
        app.update_viewport(0.0)
    assert calls == []
    assert rm.stats.counters.get("vertex_updates", 0) > vertex_updates  # the surface did move
    assert app.viewport.surface_render_mesh is rm  # patched, not rebuilt
    weights = app.morph.provider.object_weights(app.scene.edit_object_id)
    assert skin.surface_mesh.positions() == skinning.evaluate(
        mesh, morph_mix.evaluate(mesh, weights), app.scene.rig, skin.pose, skinning.placement_of(app.scene.edit_object))
    assert_equivalent(rm)
