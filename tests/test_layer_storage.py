"""AD-025 Phase 4: packed point-layer storage (`core.layer_storage`) behind the unchanged `Mesh` API.

The Mesh-level contract (journal, file, rules) is pinned by `test_point_layers.py` and the T-1 / T-2
oracles in `test_mesh_change_journal.py`, unchanged. This file pins the storage itself: dict semantics
against a plain-dict oracle through random operations, equality (also -0.0 and deleted slots), copy
independence, the append-only slot map, and the memory per value.
"""

from __future__ import annotations

import random

import tests._bootstrap  # noqa: F401

from core import PointLayerInfo
from core.ids import VertexId
from core.layer_storage import LayerSlots, PackedValues
from tests.test_mesh_change_journal import _grid


def _value(rng):
    return (rng.uniform(-1, 1), rng.choice((0.0, -0.0, rng.uniform(-1, 1))), rng.uniform(-1, 1))


def test_packed_values_behave_like_a_dict_through_random_operations():
    rng = random.Random(4)
    slots = LayerSlots()
    layers = [PackedValues(slots) for _ in range(3)]
    oracles = [{} for _ in layers]
    for step in range(3000):
        k = rng.randrange(3)
        packed, oracle = layers[k], oracles[k]
        vid = VertexId(rng.randrange(200))
        op = rng.random()
        if op < 0.5:
            value = _value(rng)
            packed[vid] = value
            oracle[vid] = value
        elif op < 0.8:
            assert packed.pop(vid, None) == oracle.pop(vid, None)
        elif op < 0.9:
            copy = packed.copy()
            assert copy == packed and copy == oracle
            copy[VertexId(999)] = (1.0, 2.0, 3.0)  # the copy is independent
            assert VertexId(999) not in packed
        else:
            layers[k] = packed.copy()
        packed = layers[k]
        assert len(packed) == len(oracle) and bool(packed) == bool(oracle)
        assert packed == oracle and dict(packed) == oracle
        assert sorted(packed.items()) == sorted(oracle.items())
        assert set(packed) == set(oracle) == set(packed.keys())
        assert sorted(packed.values()) == sorted(oracle.values())
        assert packed.get(vid) == oracle.get(vid) and (vid in packed) == (vid in oracle)
        for i, other in enumerate(layers):
            assert (other == packed) == (oracles[i] == oracle)


def test_equality_ignores_the_sign_of_zero_and_deleted_slots():
    slots = LayerSlots()
    a, b = PackedValues(slots), PackedValues(slots)
    a[VertexId(1)] = (0.0, 1.0, 2.0)
    b[VertexId(1)] = (-0.0, 1.0, 2.0)
    assert a == b  # as the dicts compared: -0.0 == 0.0
    a[VertexId(2)] = (5.0, 5.0, 5.0)
    del a[VertexId(2)]
    assert a == b and b == a  # a deleted slot holds nothing (its floats are reset)
    b[VertexId(7)] = (1.0, 1.0, 1.0)  # b grows past a's length
    assert a != b
    del b[VertexId(7)]
    assert a == b


def test_the_slot_map_is_append_only_and_shared_by_the_mesh_layers():
    mesh = _grid(3)
    a = mesh.add_point_layer(PointLayerInfo("A"))
    b = mesh.add_point_layer(PointLayerInfo("B"))
    ids = mesh.all_vertex_ids()
    mesh.set_layer_value(a, ids[3], (1.0, 0.0, 0.0))
    mesh.set_layer_value(b, ids[3], (0.0, 1.0, 0.0))
    slots = mesh._layer_slots
    assert len(slots) == 1 and mesh._layer_values[a].slots is mesh._layer_values[b].slots is slots
    mesh.set_layer_value(a, ids[3], (0.0, 0.0, 0.0))
    mesh.set_layer_value(b, ids[3], (0.0, 0.0, 0.0))
    mesh.set_layer_value(a, ids[5], (1.0, 1.0, 1.0))
    assert slots.index == {ids[3]: 0, ids[5]: 1}  # never freed, never reused


def test_a_plain_dict_handed_to_the_mesh_is_packed():
    mesh = _grid(3)
    lid = mesh.add_point_layer(PointLayerInfo("A"))
    v = mesh.all_vertex_ids()[0]
    mesh._bulk_set(lid, {v: (1.0, 2.0, 3.0)}, shared=False)
    assert isinstance(mesh._layer_values[lid], PackedValues) and mesh.layer_value(lid, v) == (1.0, 2.0, 3.0)


def test_a_dense_layer_costs_25_bytes_per_point():
    mesh = _grid(30)
    lid = mesh.add_point_layer(PointLayerInfo("A"))
    for i, v in enumerate(mesh.all_vertex_ids()):
        mesh.set_layer_value(lid, v, (float(i) + 0.5, 1.0, 2.0))
    n = len(mesh.all_vertex_ids())
    assert mesh._layer_values[lid].nbytes() <= 25 * n * 1.15  # array over-allocation
