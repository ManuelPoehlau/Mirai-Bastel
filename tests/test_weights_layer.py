"""T-1 (AD-028 §12): the WEIGHTS point-layer kind in the Core (CORE_V1_FREEZE §7.1 2026-11-02).

W1-W4 validation and canonical form; the one per-kind combiner against an independent exact oracle
(`fractions.Fraction`: convex per key, keep four with ties, renormalize, snap, negatives dropped); each
primitive's rule; refusals with mesh and counters unchanged; layered random journal sequences with a
weights layer (L1-L5 and W1-W4 after every step, Undo / Redo against the snapshot oracle); the file
round trip order-sensitive on the JSON text, non-canonical values refused; `PackedWeights` against a
dict oracle; and the no-weights equivalence (the vector arithmetic bit-identical to AD-025 Phase 2,
export keys and file versions unchanged).
"""

from __future__ import annotations

import json
import math
import random
import struct
from fractions import Fraction

import pytest

import tests._bootstrap  # noqa: F401

from core import BoneId, HistoryStack, LayerKind, PointLayerInfo, Scene, VertexId
from core.layer_storage import LayerSlots, PackedWeights
from core.mesh import Mesh, MeshError, combine_values
from core.operations import MeshDeltaCommand, record_mesh_change
from core.operations.collapse import collapse_elements
from core.serialization import scene_from_json, scene_to_dict, scene_to_json
from tests.mesh_invariants import assert_layer_invariants, assert_weights_value
from tests.test_mesh_change_journal import _body, _grid, _random_layer_op, _snapshot

W = LayerKind.WEIGHTS
SKIN = PointLayerInfo("Skin", LayerKind.WEIGHTS)


def _counters(mesh: Mesh) -> tuple:
    state = mesh.export_state()
    return tuple(state[k] for k in sorted(state) if k.endswith("_counter"))


def _random_weights(rng: random.Random, keys=range(8), *, full: float | None = None) -> tuple:
    """A canonical value: 1-4 random keys; Σw = 1 (`full`), or a random share under 1."""
    chosen = sorted(rng.sample(list(keys), rng.randint(1, 4)))
    raw = [rng.random() + 0.01 for _ in chosen]
    total = sum(raw)
    scale = (1.0 if rng.random() < 0.5 else rng.uniform(0.2, 0.95)) if full is None else full
    value = tuple((k, w / total * scale) for k, w in zip(chosen, raw))
    return combine_values(W, ((value, 1.0),))  # canonical through the Core's own rule


def _weighted_grid(n: int, rng: random.Random, *, density: float = 0.7) -> tuple[Mesh, object]:
    mesh = _grid(n)
    lid = mesh.add_point_layer(SKIN)
    for vid in mesh.all_vertex_ids():
        if rng.random() < density:
            mesh.set_layer_value(lid, vid, _random_weights(rng))
    return mesh, lid


# -- the oracle --------------------------------------------------------------------------------


def _oracle(sources) -> list:
    """AD-028 §3.5 in exact rational arithmetic, independent of the Core's code."""
    acc: dict = {}
    for value, a in sources:
        for key, w in value:
            acc[key] = acc.get(key, Fraction(0)) + Fraction(a) * Fraction(w)
    pairs = [(k, w) for k, w in acc.items() if w > 0]
    if len(pairs) > 4:
        ranked = sorted(pairs, key=lambda kw: (-kw[1], kw[0]))
        dropped = sum(w for _, w in ranked[4:])
        pairs = [(k, w / (1 - dropped)) for k, w in ranked[:4]]
    total = sum(w for _, w in pairs)
    if total > 1 or total >= 1 - Fraction(1e-12):
        pairs = [(k, w / total) for k, w in pairs]
    return sorted((k, float(w)) for k, w in pairs)


def _close(value, expected, tol=1e-15) -> bool:
    return [k for k, _ in value] == [k for k, _ in expected] and all(
        abs(a - b) <= tol for (_, a), (_, b) in zip(value, expected)
    )


# -- W1-W4 --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        ((1, -0.1),), ((1, math.nan),), ((1, math.inf),), ((-1, 0.5),), ((2**31, 0.5),), ((1.0, 0.5),),
        ((True, 0.5),), ((1, True),), ((1, 0.5), (1, 0.25)), ((1, 0.6), (2, 0.6)),
        tuple((k, 0.1) for k in range(5)), ((1, 0.5, 0.0),), ((1,),), (5,), "ab", ((1, "x"),),
    ],
)
def test_invalid_values_are_refused_with_mesh_and_counters_unchanged(bad):
    mesh, lid = _weighted_grid(2, random.Random(1))
    before, counters = _snapshot(mesh), _counters(mesh)
    with pytest.raises(MeshError):
        mesh.set_layer_value(lid, mesh.all_vertex_ids()[0], bad)
    assert _snapshot(mesh) == before and _counters(mesh) == counters


def test_canonical_form():
    mesh, lid = _weighted_grid(1, random.Random(0), density=0.0)
    v = mesh.all_vertex_ids()[0]

    def written(value):
        mesh.set_layer_value(lid, v, value)
        return mesh.layer_value(lid, v)

    assert written([(3, 0.25), (1, 0.5)]) == ((1, 0.5), (3, 0.25))  # sorted
    assert written([(3, 0.25), (1, 0.0), (2, 0.0)]) == ((3, 0.25),)  # zeros dropped
    assert written([[2, 1]]) == ((2, 1.0),) and type(mesh.layer_value(lid, v)[0][1]) is float
    assert written(((BoneId(4), 0.5),)) == ((4, 0.5),) and type(mesh.layer_value(lid, v)[0][0]) is int
    value = written(((1, 0.5), (2, 0.5 + 4e-10)))  # Σw <= 1 + 1e-9: divided, proportions kept
    assert math.fsum(w for _, w in value) == 1.0 and abs(value[1][1] / value[0][1] - (0.5 + 4e-10) / 0.5) < 1e-15
    assert written(((1, 0.3), (2, 0.7 - 1e-13))) != ((1, 0.3), (2, 0.7 - 1e-13))  # snapped to 1
    assert math.fsum(w for _, w in mesh.layer_value(lid, v)) == 1.0
    assert written(((1, 0.3), (2, 0.6))) == ((1, 0.3), (2, 0.6))  # a partial share stays
    assert written(()) == () and v not in dict(mesh.layer_items(lid))  # W3: the default is not stored
    assert written([(1, 0.0)]) == ()
    assert mesh.layer_value(lid, mesh.all_vertex_ids()[1]) == ()


def test_canonical_form_is_idempotent_and_snaps_exactly():
    """Σw (fsum) is exactly 1.0 or below 1 - 1e-12 after every write, and re-writing a stored value
    changes nothing - the property the file's canonical-only check relies on."""
    rng = random.Random(5)
    mesh, lid = _weighted_grid(1, rng, density=0.0)
    v = mesh.all_vertex_ids()[0]
    for _ in range(20000):
        keys = rng.sample(range(10), rng.randint(1, 4))
        raw = [rng.random() for _ in keys]
        total = sum(raw)
        mode = rng.random()
        if mode < 0.4:
            raw = [w / total for w in raw]
        elif mode < 0.6:
            raw = [w / total * (1 - rng.random() * 1e-12) for w in raw]
        elif mode < 0.7:
            raw = [w / total * (1 + rng.random() * 1e-9) for w in raw]
        else:
            raw = [w / total * rng.random() for w in raw]
        mesh.set_layer_value(lid, v, list(zip(keys, raw)))
        value = mesh.layer_value(lid, v)
        if value:
            assert_weights_value(value)
        mesh.set_layer_value(lid, v, value)
        assert mesh.layer_value(lid, v) == value


# -- the combiner ---------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(4))
def test_combiner_against_the_exact_oracle(seed):
    rng = random.Random(seed)
    for _ in range(3000):
        n = rng.randint(1, 6)
        values = [() if rng.random() < 0.15 else _random_weights(rng, range(12)) for _ in range(n)]
        raw = [rng.random() + 1e-3 for _ in values]
        factors = [w / sum(raw) for w in raw]
        sources = list(zip(values, factors))
        got = combine_values(W, sources)
        if got:
            assert_weights_value(got)
        assert _close(list(got), _oracle(sources)), (sources, got, _oracle(sources))
        # source order is not semantic (fsum per key, keys sorted)
        assert combine_values(W, list(reversed(sources))) == got


def test_combiner_keeps_full_binding_full_and_copies_bit_exact():
    rng = random.Random(9)
    for _ in range(2000):
        a, b = _random_weights(rng, full=1.0), _random_weights(rng, full=1.0)
        t = rng.random()
        got = combine_values(W, ((a, 1.0 - t), (b, t)))
        assert math.fsum(w for _, w in got) == 1.0  # (1 - t)·1 + t·1 = 0.9999999999999999 snapped
        assert combine_values(W, ((a, 1.0),)) == a  # a copy is bit-exact
        assert combine_values(W, ((a, 0.5), (a, 0.5)), "midpoint") == a
    assert combine_values(W, ((((3, 1.0),), 0.7), (((3, 1.0),), 0.3))) == ((3, 1.0),)


def test_combiner_keeps_the_four_largest_with_ties_to_the_smaller_key():
    a = ((1, 0.25), (2, 0.25), (3, 0.25), (4, 0.25))
    b = ((5, 0.25), (6, 0.25), (7, 0.25), (8, 0.25))
    got = combine_values(W, ((a, 0.5), (b, 0.5)))
    assert got == ((1, 0.25), (2, 0.25), (3, 0.25), (4, 0.25))  # eight equal: the four smaller keys
    c = ((1, 0.1), (2, 0.2), (3, 0.3), (4, 0.4))
    d = ((5, 0.5), (6, 0.3), (7, 0.1), (8, 0.1))
    got = combine_values(W, ((c, 0.5), (d, 0.5)))
    # per key: 1 .05, 2 .1, 3 .15, 4 .2, 5 .25, 6 .15, 7 .05, 8 .05 -> keep 5, 4, 3, 6 (3 before 6 at .15)
    assert [k for k, _ in got] == [3, 4, 5, 6]
    assert math.fsum(w for _, w in got) == 1.0  # renormalized: the dropped .3 went to the kept ones
    assert _close(list(got), [(3, 0.15 / 0.75), (4, 0.2 / 0.75), (5, 0.25 / 0.75), (6, 0.15 / 0.75)], 1e-15)
    # with an object share: the survivors keep their proportions, the share scales with them
    e = ((1, 0.1), (2, 0.1), (3, 0.1), (4, 0.1))  # r = 0.6
    f = ((5, 0.2), (6, 0.2), (7, 0.2), (8, 0.2))  # r = 0.2
    got = combine_values(W, ((e, 0.5), (f, 0.5)))  # 5-8 get 0.1, 1-4 0.05: keep 5-8; r 0.4 -> 0.5
    assert [k for k, _ in got] == [5, 6, 7, 8]
    assert _close(list(got), [(k, 0.125) for k in (5, 6, 7, 8)]) and _close(list(got), _oracle(((e, 0.5), (f, 0.5))))
    g = ((1, 0.1), (2, 0.1), (3, 0.1))  # r = 0.7
    h = ((4, 0.1), (5, 0.1), (6, 0.1))  # r = 0.7
    got = combine_values(W, ((g, 0.5), (h, 0.5)))  # six ties at 0.05: the four smaller keys, r 0.7 kept
    assert [k for k, _ in got] == [1, 2, 3, 4]
    assert _close(list(got), [(k, 0.05 / 0.9) for k in (1, 2, 3, 4)])


def test_combiner_drops_negative_results():
    a, b = ((1, 0.5), (2, 0.5)), ((1, 1.0),)
    got = combine_values(W, ((a, 1.5), (b, -0.5)))  # key 1: 0.25, key 2: 0.75 -> fine
    assert _close(list(got), [(1, 0.25), (2, 0.75)])
    got = combine_values(W, ((b, 1.5), (a, -0.5)))  # key 1: 1.25, key 2: -0.25 dropped -> 1.25 snapped to 1
    assert got == ((1, 1.0),)
    assert combine_values(W, ()) == ()


def test_vector_branch_is_the_phase_2_arithmetic_bit_for_bit():
    """The vector arithmetic moved into the combiner unchanged: compared bit-wise (struct) with the
    AD-025 Phase 2 expressions, copied here verbatim, incl. -0.0, subnormals and large values."""
    rng = random.Random(3)
    specials = (0.0, -0.0, 5e-324, -5e-324, 1e-310, 1e308, -1e308, 0.1, 1.0)

    def c():
        return rng.choice(specials) if rng.random() < 0.3 else rng.uniform(-2, 2)

    def bits(v):
        return struct.pack("3d", *v)

    for _ in range(5000):
        vals = [(c(), c(), c()) for _ in range(rng.randint(1, 5))]
        ws = [rng.uniform(-0.5, 1.5) for _ in vals]
        # _origin_values of Phase 2
        total = None
        for v, w in zip(vals, ws):
            term = (w * v[0], w * v[1], w * v[2])
            total = term if total is None else (total[0] + term[0], total[1] + term[1], total[2] + term[2])
        assert bits(combine_values(LayerKind.VECTOR, list(zip(vals, ws)))) == bits(total)
        # _blend_values of Phase 2
        a, b, t = vals[0], vals[-1], rng.random()
        s = 1.0 - t
        old = (a[0] * s + b[0] * t, a[1] * s + b[1] * t, a[2] * s + b[2] * t)
        assert bits(combine_values(LayerKind.VECTOR, ((a, s), (b, t)))) == bits(old)
        # collapse_edge of Phase 2
        old = tuple((x + y) / 2.0 for x, y in zip(a, b))
        assert bits(combine_values(LayerKind.VECTOR, ((a, 0.5), (b, 0.5)), "midpoint")) == bits(old)
        # collapse.py _mean of Phase 2
        n = len(vals)
        old = (sum(p[0] for p in vals) / n, sum(p[1] for p in vals) / n, sum(p[2] for p in vals) / n)
        assert bits(combine_values(LayerKind.VECTOR, [(v, 1.0 / n) for v in vals], "mean")) == bits(old)


# -- each primitive's rule -----------------------------------------------------------------------


@pytest.mark.parametrize("t", [0.5, 0.25, 0.731, 1e-3])
def test_split_edge_blends_per_key(t):
    mesh, lid = _weighted_grid(2, random.Random(2))
    for eid in list(mesh.all_edge_ids())[:8]:
        v0, v1 = mesh.edge_vertices(eid)
        a, b = mesh.layer_value(lid, v0), mesh.layer_value(lid, v1)
        mid, _, _ = mesh.split_edge(eid, t)
        expected = combine_values(W, ((a, 1.0 - t), (b, t)))
        assert mesh.layer_value(lid, mid) == expected
        assert _close(list(expected), _oracle(((a, 1.0 - t), (b, t))))
    assert_layer_invariants(mesh)


def test_collapse_edge_averages_and_drops_the_removed_value():
    mesh, lid = _weighted_grid(2, random.Random(3), density=1.0)
    eid = mesh.all_edge_ids()[0]
    v0, v1 = mesh.edge_vertices(eid)
    a, b = mesh.layer_value(lid, v0), mesh.layer_value(lid, v1)
    survivor = mesh.collapse_edge(eid)
    assert survivor == v0
    assert mesh.layer_value(lid, survivor) == combine_values(W, ((a, 0.5), (b, 0.5)), "midpoint")
    assert _close(list(mesh.layer_value(lid, survivor)), _oracle(((a, 0.5), (b, 0.5))))
    assert v1 not in dict(mesh.layer_items(lid))
    assert_layer_invariants(mesh)


def test_collapse_elements_gives_the_group_mean_of_the_original_values():
    mesh, lid = _weighted_grid(3, random.Random(4), density=1.0)
    vertices = mesh.all_vertex_ids()
    group = [vertices[0], vertices[1], vertices[5], vertices[4]]  # a face of the grid
    originals = [mesh.layer_value(lid, v) for v in group]
    survivors = collapse_elements(mesh, group)
    value = mesh.layer_value(lid, survivors[0])
    assert value == combine_values(W, [(o, 0.25) for o in originals], "mean")
    assert _close(list(value), _oracle([(o, 0.25) for o in originals]))
    assert len(value) <= 4
    assert_layer_invariants(mesh)


def test_add_vertex_origin_copy_and_combination():
    mesh, lid = _weighted_grid(2, random.Random(5), density=1.0)
    a, b, c = mesh.all_vertex_ids()[:3]
    copy = mesh.add_vertex((5.0, 5.0, 5.0), origin=((a, 1.0),))
    assert mesh.layer_value(lid, copy) == mesh.layer_value(lid, a)  # bit-exact
    origin = ((a, 0.2), (b, 0.3), (c, 0.5))
    mixed = mesh.add_vertex((5.0, 5.0, 6.0), origin=origin)
    sources = [(mesh.layer_value(lid, v), w) for v, w in origin]
    assert mesh.layer_value(lid, mixed) == combine_values(W, sources)
    assert _close(list(mesh.layer_value(lid, mixed)), _oracle(sources))
    none = mesh.add_vertex((5.0, 6.0, 6.0), origin=())
    assert mesh.layer_value(lid, none) == ()  # no source: unbound


def test_split_face_origins_apply_to_the_weights_layer():
    mesh, lid = _weighted_grid(2, random.Random(6), density=1.0)
    f = mesh.all_face_ids()[0]
    corners = mesh.face_vertices(f)
    origins = [((corners[0], 0.2), (corners[1], 0.3), (corners[2], 0.5)), ((corners[3], 1.0),)]
    positions = [(0.4, 0.4, 0.0), (0.6, 0.6, 0.0)]
    new, _, _, _ = mesh.split_face(f, corners[0], corners[2], positions, origins=origins)
    for vid, origin in zip(new, origins):
        sources = [(mesh.layer_value(lid, v), w) for v, w in origin]
        assert mesh.layer_value(lid, vid) == combine_values(W, sources)
    assert mesh.layer_value(lid, new[1]) == mesh.layer_value(lid, corners[3])
    assert_layer_invariants(mesh)


@pytest.mark.parametrize(
    "origin", [None, ((VertexId(999), 1.0),), ((VertexId(0), 0.5),), ((VertexId(0), math.nan),)]
)
def test_origin_refusals_on_a_weights_mesh_leave_mesh_and_counters_unchanged(origin):
    mesh, _ = _weighted_grid(1, random.Random(7), density=1.0)
    before, counters = _snapshot(mesh), _counters(mesh)
    with pytest.raises(MeshError):
        mesh.add_vertex((1.0, 2.0, 3.0), origin=origin)
    f = mesh.all_face_ids()[0]
    corners = mesh.face_vertices(f)
    with pytest.raises(MeshError):
        mesh.split_face(f, corners[0], corners[2], [(0.5, 0.5, 0.0)], origins=None if origin is None else [origin])
    assert _snapshot(mesh) == before and _counters(mesh) == counters


def test_delete_removes_the_weights_of_removed_vertices_and_undo_restores_them():
    mesh, lid = _weighted_grid(2, random.Random(8), density=1.0)
    before = dict(mesh.layer_items(lid))
    delta, _ = record_mesh_change(mesh, lambda: mesh.delete_vertices([mesh.all_vertex_ids()[4]]))
    assert set(dict(mesh.layer_items(lid))) <= set(mesh.all_vertex_ids())
    assert_layer_invariants(mesh)
    mesh.apply_delta(delta, reverse=True)
    assert dict(mesh.layer_items(lid)) == before


def test_map_vector_layers_leaves_weights_unchanged():
    mesh, lid = _weighted_grid(2, random.Random(9))
    vec = mesh.add_point_layer(PointLayerInfo("Smile"))
    mesh.set_layer_value(vec, mesh.all_vertex_ids()[0], (1.0, 2.0, 3.0))
    before = mesh.layer_items(lid)
    mesh.map_vector_layers(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
    assert mesh.layer_items(lid) == before
    assert mesh.layer_value(vec, mesh.all_vertex_ids()[0]) == (-2.0, 1.0, 3.0)


# -- journal: layered random sequences with a weights layer ----------------------------------------


def _random_weights_op(mesh: Mesh, rng: random.Random, counter: list) -> None:
    """Every layer operation of AD-025 T-1 plus weights writes; the weights layer comes and goes."""
    weights = [lid for lid in mesh.point_layer_ids() if mesh.point_layer_info(lid).kind is W]
    vertices = mesh.all_vertex_ids()
    kind = rng.random()
    if kind < 0.25 and weights and vertices:
        lid = rng.choice(weights)
        for vid in rng.sample(vertices, min(len(vertices), rng.randint(1, 4))):
            mesh.set_layer_value(lid, vid, () if rng.random() < 0.15 else _random_weights(rng))
    elif kind < 0.3 and not weights:
        counter[0] += 1
        lid = mesh.add_point_layer(PointLayerInfo(f"S{counter[0]}", W))
        for vid in rng.sample(vertices, min(len(vertices), 5)):
            mesh.set_layer_value(lid, vid, _random_weights(rng))
    elif kind < 0.33 and weights:
        mesh.remove_point_layer(rng.choice(weights))
    else:
        _random_layer_op(mesh, rng, counter)


def _export_text(mesh: Mesh) -> str:
    return json.dumps(mesh.export_state()["point_layers"])


@pytest.mark.parametrize("seed,steps", [(seed, 30) for seed in range(10)] + [(77, 250)])
def test_weights_random_sequences_undo_redo_match_snapshots(seed, steps):
    rng = random.Random(2000 + seed)
    mesh, _ = _weighted_grid(4, rng)
    vec = mesh.add_point_layer(PointLayerInfo("Smile"))
    for vid in rng.sample(mesh.all_vertex_ids(), 6):
        mesh.set_layer_value(vec, vid, (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
    kinds: dict = {}
    counter = [0]
    history = HistoryStack()
    snapshots = [(_snapshot(mesh), _export_text(mesh))]
    for _ in range(steps):
        before, counters = _snapshot(mesh), _counters(mesh)
        try:
            delta = record_mesh_change(mesh, lambda: _random_weights_op(mesh, rng, counter))[0]
        except MeshError:
            assert _snapshot(mesh) == before
            assert_layer_invariants(mesh, kinds=kinds)
            continue
        assert_layer_invariants(mesh, kinds=kinds)
        assert _counters(mesh) >= counters
        assert not set(delta.layer_values) & set(delta.layer_whole)
        if delta.empty:
            assert _body(mesh) == before[0]
            continue
        history.push(MeshDeltaCommand(mesh, delta, "op"))
        snapshots.append((_snapshot(mesh), _export_text(mesh)))
    for expected in reversed(snapshots[:-1]):
        history.undo()
        assert (_snapshot(mesh), _export_text(mesh)) == expected
        assert_layer_invariants(mesh, kinds=kinds)
    for expected in snapshots[1:]:
        history.redo()
        assert (_snapshot(mesh), _export_text(mesh)) == expected
        assert_layer_invariants(mesh, kinds=kinds)


@pytest.mark.parametrize("seed", range(4))
def test_weights_nested_rollback_restores_exactly(seed):
    rng = random.Random(3000 + seed)
    mesh, _ = _weighted_grid(3, rng)
    counter = [0]
    start = (_snapshot(mesh), _export_text(mesh))
    outer = mesh.begin_change()
    for _ in range(6):
        try:
            _random_weights_op(mesh, rng, counter)
        except MeshError:
            pass
    middle = (_snapshot(mesh), _export_text(mesh))
    inner = mesh.begin_change()
    for _ in range(6):
        try:
            _random_weights_op(mesh, rng, counter)
        except MeshError:
            pass
    mesh.rollback_change(inner)
    assert (_snapshot(mesh), _export_text(mesh)) == middle
    mesh.rollback_change(outer)
    assert (_snapshot(mesh), _export_text(mesh)) == start
    assert_layer_invariants(mesh)


def test_a_weights_write_is_journaled_and_a_watch_sees_the_key():
    mesh, lid = _weighted_grid(2, random.Random(10), density=0.0)
    watch = mesh.watch()
    vid = mesh.all_vertex_ids()[3]
    delta, _ = record_mesh_change(mesh, lambda: mesh.set_layer_value(lid, vid, ((2, 0.5),)))
    assert delta.layer_values == {lid: {vid: (None, ((2, 0.5),))}}
    assert watch.peek().layer_values == {lid: {vid: None}}
    mesh.apply_delta(delta, reverse=True)
    assert mesh.layer_value(lid, vid) == ()


def test_load_state_of_an_unrelated_state_with_another_kind_under_a_journal():
    """A state that reuses a LayerId with the other kind replaces the layer whole (rollback exact)."""
    a = _grid(1)
    vec = a.add_point_layer(PointLayerInfo("A"))
    a.set_layer_value(vec, a.all_vertex_ids()[0], (1.0, 2.0, 3.0))
    b = _grid(1)
    w = b.add_point_layer(PointLayerInfo("A", W))
    b.set_layer_value(w, b.all_vertex_ids()[0], ((1, 1.0),))
    assert vec == w
    start = json.dumps(a.export_state())
    change = a.begin_change()
    a.load_state(b.export_state())
    assert json.dumps(a.export_state()) == json.dumps(b.export_state())
    a.rollback_change(change)
    assert json.dumps(a.export_state()) == start


# -- file -----------------------------------------------------------------------------------------


def test_file_round_trip_is_bit_exact_and_order_sensitive():
    rng = random.Random(12)
    mesh, lid = _weighted_grid(3, rng)
    vec = mesh.add_point_layer(PointLayerInfo("Smile"))
    mesh.set_layer_value(vec, mesh.all_vertex_ids()[2], (0.1, -0.0, 3.0))
    mesh.set_point_layer_order([vec, lid])
    text = json.dumps(mesh.export_state())
    entry = json.loads(text)["point_layers"][1]
    assert entry["kind"] == "weights" and all(isinstance(v, list) for v in entry["values"].values())
    loaded = Mesh.from_state(json.loads(text))
    assert json.dumps(loaded.export_state()) == text
    assert loaded.layer_items(lid) == mesh.layer_items(lid)
    assert isinstance(loaded._layer_values[lid], PackedWeights)


@pytest.mark.parametrize(
    "value",
    [[[3, 0.5], [1, 0.5]], [[1, 0.0]], [], [[1, 0.6], [2, 0.6]], [[1, 0.5], [2, 0.5 - 1e-14]], [[1.0, 1.0]],
     [[1, 0.1], [2, 0.1], [3, 0.1], [4, 0.1], [5, 0.1]], [[1, 0.5], [1, 0.5]], [1, 0.5], "x", [[1, -0.5]]],
)
def test_non_canonical_file_values_are_refused_and_the_mesh_is_unchanged(value):
    mesh, lid = _weighted_grid(2, random.Random(13))
    state = json.loads(json.dumps(mesh.export_state()))
    state["point_layers"][0]["values"][str(int(mesh.all_vertex_ids()[0]))] = value
    target, _ = _weighted_grid(2, random.Random(14))
    before = json.dumps(target.export_state())
    with pytest.raises(ValueError):
        target.load_state(state)
    assert json.dumps(target.export_state()) == before
    with pytest.raises(ValueError):
        Mesh.from_state(state)


def test_scene_file_versions():
    scene = Scene()
    scene.mesh = _grid(1)
    assert scene_to_dict(scene)["version"] == 4
    lid = scene.mesh.add_point_layer(SKIN)
    assert scene_to_dict(scene)["version"] == 7  # a weights layer, even empty
    scene.mesh.set_layer_value(lid, scene.mesh.all_vertex_ids()[0], ((0, 1.0),))
    text = scene_to_json(scene)
    assert scene_to_json(scene_from_json(text)) == text
    scene.mesh.remove_point_layer(lid)
    assert scene_to_dict(scene)["version"] == 4
    scene.mesh.add_point_layer(PointLayerInfo("Smile"))
    assert scene_to_dict(scene)["version"] == 5


# -- PackedWeights ----------------------------------------------------------------------------------


def test_packed_weights_behave_like_a_dict_through_random_operations():
    rng = random.Random(4)
    slots = LayerSlots()
    layers = [PackedWeights(slots) for _ in range(3)]
    oracles: list[dict] = [{} for _ in layers]
    for _ in range(4000):
        k = rng.randrange(3)
        packed, oracle = layers[k], oracles[k]
        vid = VertexId(rng.randrange(150))
        op = rng.random()
        if op < 0.5:
            value = _random_weights(rng, range(2**31 - 5, 2**31)) if rng.random() < 0.1 else _random_weights(rng)
            packed[vid] = value
            oracle[vid] = value
        elif op < 0.8:
            assert packed.pop(vid, None) == oracle.pop(vid, None)
        elif op < 0.9:
            copy = packed.copy()
            assert copy == packed and copy == oracle
            copy[VertexId(999)] = ((1, 1.0),)
            assert VertexId(999) not in packed
        else:
            layers[k] = packed.copy()
        packed = layers[k]
        assert len(packed) == len(oracle) and bool(packed) == bool(oracle)
        assert packed == oracle and dict(packed) == oracle
        assert sorted(packed.items()) == sorted(oracle.items())
        assert set(packed) == set(oracle) == set(packed.keys())
        assert packed.get(vid) == oracle.get(vid) and (vid in packed) == (vid in oracle)
        for i, other in enumerate(layers):
            assert (other == packed) == (oracles[i] == oracle)
    # values come back bit-exact (float64)
    v = ((0, 0.1), (5, 1 / 3), (2**31 - 1, 5e-324))
    layers[0][VertexId(7)] = v
    assert struct.pack("3d", *(w for _, w in layers[0][VertexId(7)])) == struct.pack("3d", *(w for _, w in v))


def test_packed_weights_memory_per_slot():
    slots = LayerSlots()
    packed = PackedWeights(slots)
    n = 2000
    for i in range(n):
        packed[VertexId(i)] = ((1, 0.5), (2, 0.5))
    assert packed.nbytes() <= 49 * n * 1.15  # array over-allocation
    assert packed.nbytes() >= 49 * n


# -- no weights, no change -----------------------------------------------------------------------


def test_meshes_without_weights_export_the_same_keys():
    mesh = _grid(2)
    state = mesh.export_state()
    assert list(state)[-3:] == ["layer_id_counter", "point_layers", "face_uvs"]
    vec = mesh.add_point_layer(PointLayerInfo("A"))
    mesh.set_layer_value(vec, mesh.all_vertex_ids()[0], (1.0, 2.0, 3.0))
    entry = mesh.export_state()["point_layers"][0]
    assert entry == {"id": 1, "name": "A", "kind": "vector", "new_point": "interpolate", "values": {0: [1.0, 2.0, 3.0]}}
