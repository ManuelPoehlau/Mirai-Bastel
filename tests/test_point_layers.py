"""Contract tests for the Core point layers (AD-025 §4.1–§4.3, CORE_V1_FREEZE §7.1 2026-10-27):
the origin rule per primitive (T-3), byte-identical behaviour without layers (T-4), the file
(T-5) and `map_vector_layers` (T-8). The journal sequences (T-1 / T-2) live in
`test_mesh_change_journal.py`."""

from __future__ import annotations

import json
import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import HistoryStack, LayerId, LayerKind, PointLayerInfo, Scene, VertexId
from core.mesh import Mesh, MeshError
from core.operations import MeshDeltaCommand, record_mesh_change
from core.operations.collapse import collapse_elements
from core.serialization import scene_from_dict, scene_from_json, scene_to_dict, scene_to_json
from tests.mesh_invariants import assert_layer_invariants
from tests.test_mesh_change_journal import _grid, _random_op, _snapshot

ZERO = (0.0, 0.0, 0.0)


def _layered(n: int = 2, *, seed: int = 0, rule: str = "interpolate", dense: bool = True) -> tuple[Mesh, LayerId]:
    rng = random.Random(seed)
    mesh = _grid(n)
    lid = mesh.add_point_layer(PointLayerInfo("A", new_point=rule))
    vertices = mesh.all_vertex_ids()
    for vid in vertices if dense else vertices[::3]:
        mesh.set_layer_value(lid, vid, (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
    return mesh, lid


def _counters(mesh: Mesh) -> tuple:
    state = mesh.export_state()
    return tuple(state[k] for k in sorted(state) if k.endswith("_counter"))


# -- T-3: rule per primitive -------------------------------------------------------------------


@pytest.mark.parametrize("t", [0.5, 0.25, 0.731, 1e-3])
def test_split_edge_value_is_the_position_expression(t):
    mesh, lid = _layered(seed=1)
    for eid in mesh.all_edge_ids()[:6]:
        v0, v1 = mesh.edge_vertices(eid)
        a, b = mesh.layer_value(lid, v0), mesh.layer_value(lid, v1)
        mid, _, _ = mesh.split_edge(eid, t)
        assert mesh.layer_value(lid, mid) == tuple(x * (1.0 - t) + y * t for x, y in zip(a, b))
    assert_layer_invariants(mesh)


def test_split_edge_with_one_absent_end_and_zero_rule():
    mesh = _grid(1)
    a = mesh.add_point_layer(PointLayerInfo("A"))
    z = mesh.add_point_layer(PointLayerInfo("Z", new_point="zero"))
    eid = mesh.all_edge_ids()[0]
    v0, v1 = mesh.edge_vertices(eid)
    for lid in (a, z):
        mesh.set_layer_value(lid, v0, (1.0, -2.0, 4.0))
    mid, _, _ = mesh.split_edge(eid, 0.25)
    assert mesh.layer_value(a, mid) == (0.75, -1.5, 3.0)
    assert mesh.layer_value(z, mid) == ZERO and dict(mesh.layer_items(z)).get(mid) is None


def test_collapse_edge_averages_and_drops_the_removed_value():
    mesh, lid = _layered(seed=2)
    eid = mesh.all_edge_ids()[3]
    v0, v1 = mesh.edge_vertices(eid)
    a, b = mesh.layer_value(lid, v0), mesh.layer_value(lid, v1)
    survivor = mesh.collapse_edge(eid)
    assert survivor == v0
    assert mesh.layer_value(lid, v0) == tuple((x + y) / 2.0 for x, y in zip(a, b))
    assert v1 not in dict(mesh.layer_items(lid))
    assert_layer_invariants(mesh)


def test_collapse_elements_gives_the_group_mean_of_the_original_values():
    mesh, lid = _layered(3, seed=3)
    z = mesh.add_point_layer(PointLayerInfo("Z", new_point="zero"))
    vertices = mesh.all_vertex_ids()
    group = [vertices[5], vertices[6], vertices[9], vertices[10]]  # one quad of the 3x3 grid
    mesh.set_layer_value(z, group[0], (4.0, 0.0, 0.0))
    originals = [mesh.layer_value(lid, v) for v in group]
    expected = tuple(sum(p[i] for p in originals) / 4 for i in range(3))
    (survivor,) = collapse_elements(mesh, group)
    assert mesh.layer_value(lid, survivor) == expected
    assert mesh.layer_value(z, survivor) == (1.0, 0.0, 0.0)  # merges average in every layer (H3)
    assert_layer_invariants(mesh)


def test_add_vertex_origin_rules():
    mesh, lid = _layered(seed=4)
    v, w = mesh.all_vertex_ids()[:2]
    mesh.set_layer_value(lid, v, (-0.0, 0.1, 3.0))
    copy = mesh.add_vertex((5.0, 5.0, 5.0), origin=((v, 1.0),))
    assert mesh.layer_value(lid, copy) == (-0.0, 0.1, 3.0)
    assert math.copysign(1.0, mesh.layer_value(lid, copy)[0]) == -1.0  # bit-exact copy
    a, b = mesh.layer_value(lid, v), mesh.layer_value(lid, w)
    blend = mesh.add_vertex((0.0, 0.0, 0.0), origin=((v, 0.3), (w, 0.7)))
    assert mesh.layer_value(lid, blend) == tuple(0.3 * x + 0.7 * y for x, y in zip(a, b))
    none = mesh.add_vertex((0.0, 0.0, 0.0), origin=())
    assert mesh.layer_value(lid, none) == ZERO
    assert_layer_invariants(mesh)


@pytest.mark.parametrize(
    "origin",
    [None, ((VertexId(9999), 1.0),), ((VertexId(0), 0.5),), ((VertexId(0), float("nan")),), "x"],
)
def test_add_vertex_refusals_leave_mesh_and_counters_unchanged(origin):
    mesh, _ = _layered(seed=5)
    before, counters = _snapshot(mesh), _counters(mesh)
    with pytest.raises(MeshError):
        mesh.add_vertex((1.0, 1.0, 1.0), origin=origin)
    assert _snapshot(mesh) == before and _counters(mesh) == counters


def test_add_vertex_without_layers_ignores_origin():
    mesh = _grid(1)
    vid = mesh.add_vertex((1.0, 2.0, 3.0))
    other = mesh.add_vertex((1.0, 2.0, 3.0), origin=((VertexId(12345), 7.0),))
    assert mesh.vertex_position(vid) == mesh.vertex_position(other)


def test_split_face_interior_points_without_origins_refuse_on_a_layered_mesh():
    """The Core backstop (AD-025 §4.4): interior points on a layered mesh need `origins=`."""
    mesh, _ = _layered(seed=6)
    face = mesh.all_face_ids()[0]
    a, _, c, _ = mesh.face_vertices(face)
    before, counters = _snapshot(mesh), _counters(mesh)
    with pytest.raises(MeshError):
        mesh.split_face(face, a, c, [(0.5, 0.5, 0.0)])
    assert _snapshot(mesh) == before and _counters(mesh) == counters
    _, _, f1, f2 = mesh.split_face(face, a, c)  # k = 0 has no layer effect
    assert mesh.is_valid_face(f1) and mesh.is_valid_face(f2)


def test_split_face_origins_apply_per_layer():
    """Phase 5 (CORE_V1_FREEZE §7.1 2026-10-27): each interior vertex gets the affine combination of
    its origin's values in every `interpolate` layer, bit for bit `add_vertex`'s arithmetic; a `zero`
    layer stores nothing; `()` stores defaults; the corners keep their values."""
    mesh, lid = _layered(seed=11)
    z = mesh.add_point_layer(PointLayerInfo("Z", new_point="zero"))
    face = mesh.all_face_ids()[0]
    a, b, c, d = mesh.face_vertices(face)
    for v in (a, b, c, d):
        mesh.set_layer_value(z, v, (1.0, 1.0, 1.0))
    corners = {v: mesh.layer_value(lid, v) for v in (a, b, c, d)}
    origins = [((a, 0.2), (b, 0.5), (c, 0.3)), ((c, 0.6), (d, 0.15), (a, 0.25)), ()]
    positions = [(0.4, 0.3, 0.0), (0.6, 0.7, 0.0), (0.7, 0.8, 0.0)]
    new, _, _, _ = mesh.split_face(face, a, c, positions, origins=origins)
    for vid, origin in zip(new, origins):
        expected = None
        for src, w in origin:
            term = tuple(w * x for x in corners[src])
            expected = term if expected is None else tuple(p + q for p, q in zip(expected, term))
        assert mesh.layer_value(lid, vid) == (expected or ZERO)
        assert mesh.layer_value(z, vid) == ZERO
    assert {v: mesh.layer_value(lid, v) for v in (a, b, c, d)} == corners
    assert_layer_invariants(mesh)


@pytest.mark.parametrize(
    "origins",
    [
        [((VertexId(9999), 1.0),)],                      # unknown source
        [((VertexId(0), 0.5),)],                         # weights do not sum to 1
        [((VertexId(0), float("inf")), (VertexId(1), 0.0))],
        [((VertexId(0), 1.0),), ((VertexId(1), 1.0),)],  # one origin too many
        [],                                              # one too few
        ["x"],
    ],
)
def test_split_face_origin_refusals_leave_mesh_and_counters_unchanged(origins):
    mesh, _ = _layered(seed=12)
    face = mesh.all_face_ids()[0]
    a, _, c, _ = mesh.face_vertices(face)
    before, counters = _snapshot(mesh), _counters(mesh)
    with pytest.raises(MeshError):
        mesh.split_face(face, a, c, [(0.5, 0.5, 0.0)], origins=origins)
    assert _snapshot(mesh) == before and _counters(mesh) == counters


def test_split_face_origins_without_layers_are_ignored_but_counted():
    plain, other = _grid(2), _grid(2)
    face = plain.all_face_ids()[0]
    a, _, c, _ = plain.face_vertices(face)
    plain.split_face(face, a, c, [(0.5, 0.5, 0.0)])
    other.split_face(face, a, c, [(0.5, 0.5, 0.0)], origins=[((VertexId(4242), 3.0),)])
    assert plain.export_state() == other.export_state()
    with pytest.raises(MeshError):
        other.split_face(other.all_face_ids()[0], *other.face_vertices(other.all_face_ids()[0])[::2],
                         [(0.1, 0.1, 0.0)], origins=[])


def test_split_face_origins_undo_redo_exact():
    mesh, lid = _layered(seed=13, dense=False)
    face = mesh.all_face_ids()[1]
    a, b, c, _ = mesh.face_vertices(face)
    before = _snapshot(mesh)
    history = HistoryStack()
    delta, _ = record_mesh_change(
        mesh, lambda: mesh.split_face(face, a, c, [(0.3, 0.3, 0.0)], origins=[((a, 0.5), (b, 0.25), (c, 0.25))])
    )
    after = _snapshot(mesh)
    history.push(MeshDeltaCommand(mesh=mesh, delta=delta, description="cut"))
    history.undo()
    assert _snapshot(mesh) == before
    history.redo()
    assert _snapshot(mesh) == after


@pytest.mark.parametrize(
    "op",
    [
        lambda m: m.delete_vertices(m.all_vertex_ids()[4:5]),
        lambda m: m.delete_faces(m.all_face_ids()[:2]),
        lambda m: m.dissolve_vertex(m.all_vertex_ids()[4]),
        lambda m: m.dissolve_faces(m.all_face_ids()[:2], cleanup=True),
        lambda m: m.dissolve_edges(m.all_edge_ids()[1:2], cleanup=True),
    ],
)
def test_delete_and_dissolve_remove_values_of_removed_vertices(op):
    mesh, lid = _layered(seed=7)
    before = set(mesh.all_vertex_ids())
    delta, _ = record_mesh_change(mesh, lambda: op(mesh))
    gone = before - set(mesh.all_vertex_ids())
    assert not gone & set(dict(mesh.layer_items(lid)))
    assert_layer_invariants(mesh)
    mesh.apply_delta(delta, reverse=True)
    assert set(mesh.all_vertex_ids()) == before
    assert len(mesh.layer_items(lid)) == len(before)  # dense layer back in full


def test_layer_info_validation():
    with pytest.raises(MeshError):
        PointLayerInfo("")
    with pytest.raises(MeshError):
        PointLayerInfo("A", new_point="keep")
    with pytest.raises(MeshError):
        PointLayerInfo("W", LayerKind.WEIGHTS, "zero")  # a weights layer only interpolates
    PointLayerInfo("W", LayerKind.WEIGHTS)
    mesh = _grid(1)
    with pytest.raises(MeshError):
        mesh.add_point_layer(PointLayerInfo("W", LayerKind.WEIGHTS))  # not built before Phase 6
    lid = mesh.add_point_layer(PointLayerInfo("A"))
    with pytest.raises(MeshError):
        mesh.add_point_layer(PointLayerInfo("A"))
    other = mesh.add_point_layer(PointLayerInfo("B"))
    with pytest.raises(MeshError):
        mesh.set_point_layer_info(other, PointLayerInfo("A"))
    with pytest.raises(MeshError):
        mesh.set_point_layer_info(lid, PointLayerInfo("A", LayerKind.WEIGHTS))
    with pytest.raises(MeshError):
        mesh.set_point_layer_order([lid])
    with pytest.raises(MeshError):
        mesh.set_layer_value(lid, mesh.all_vertex_ids()[0], (1.0, float("inf"), 0.0))
    with pytest.raises(MeshError):
        mesh.set_layer_value(lid, VertexId(999), (1.0, 0.0, 0.0))
    with pytest.raises(MeshError):
        mesh.set_layer_value(LayerId(999), mesh.all_vertex_ids()[0], (1.0, 0.0, 0.0))
    mesh.set_point_layer_order([other, lid])
    assert mesh.point_layer_ids() == [other, lid]
    mesh.remove_point_layer(other)
    assert mesh.add_point_layer(PointLayerInfo("B")) not in (lid, other)  # LayerIds never reused


def test_set_layer_value_default_is_not_stored():
    mesh = _grid(1)
    lid = mesh.add_point_layer(PointLayerInfo("A"))
    vid = mesh.all_vertex_ids()[0]
    mesh.set_layer_value(lid, vid, (1, 2, 3))
    assert mesh.layer_items(lid) == [(vid, (1.0, 2.0, 3.0))]
    mesh.set_layer_value(lid, vid, (0.0, -0.0, 0.0))
    assert mesh.layer_items(lid) == []


# -- T-4: no layers, no change ------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(6))
def test_layer_free_sequences_export_the_same_plus_two_keys(seed):
    """Without layers the mesh is byte-identical: the export carries only the two additive keys
    with their neutral values (checked against the key set of the pre-AD-025 export)."""
    rng = random.Random(seed)
    mesh = _grid(3)
    for _ in range(30):
        try:
            _random_op(mesh, rng)
        except MeshError:
            pass
        state = mesh.export_state()
        assert state["point_layers"] is None and state["layer_id_counter"] == 1
        assert list(state)[-2:] == ["layer_id_counter", "point_layers"]


def test_scene_without_layers_stays_version_4():
    scene = Scene()
    scene.mesh = _grid(1)
    assert scene_to_dict(scene)["version"] == 4
    scene.mesh.add_point_layer(PointLayerInfo("A"))
    assert scene_to_dict(scene)["version"] == 5
    scene.mesh.remove_point_layer(scene.mesh.point_layer_ids()[0])
    assert scene_to_dict(scene)["version"] == 4


# -- T-5: file ------------------------------------------------------------------------------------


def _many_layers() -> Mesh:
    rng = random.Random(11)
    mesh = _grid(3)
    vertices = mesh.all_vertex_ids()
    for name, rule in (("Smile", "interpolate"), ("Blink", "zero"), ("Jaw", "interpolate")):
        lid = mesh.add_point_layer(PointLayerInfo(name, new_point=rule))
        for vid in rng.sample(vertices, 7):
            mesh.set_layer_value(lid, vid, (rng.uniform(-1, 1) / 3, 1e-300 * rng.random(), rng.uniform(-9, 9)))
    mesh.set_point_layer_order(list(reversed(mesh.point_layer_ids())))
    mesh.remove_point_layer(mesh.add_point_layer(PointLayerInfo("tmp")))  # the counter runs ahead
    return mesh


def test_export_json_load_is_bit_exact_and_order_sensitive():
    mesh = _many_layers()
    text = json.dumps(mesh.export_state())
    loaded = Mesh.from_state(json.loads(text))
    assert json.dumps(loaded.export_state()) == text  # values, ids, names, order, rule, counter
    for lid in mesh.point_layer_ids():
        assert loaded.layer_items(lid) == mesh.layer_items(lid)
        assert loaded.point_layer_info(lid) == mesh.point_layer_info(lid)
    assert loaded.export_state()["layer_id_counter"] == mesh.export_state()["layer_id_counter"] == 5
    assert loaded.add_point_layer(PointLayerInfo("new")) == LayerId(5)


def test_scene_file_round_trip_with_layers():
    scene = Scene()
    scene.mesh = _many_layers()
    text = scene_to_json(scene)
    assert json.loads(text)["version"] == 5
    assert scene_to_json(scene_from_json(text)) == text
    for version in (2, 3, 4):
        data = scene_to_dict(scene)
        data["version"] = version
        assert scene_from_dict(data).mesh.point_layer_ids() == scene.mesh.point_layer_ids()


def test_a_file_without_the_keys_loads():
    mesh = _grid(1)
    state = mesh.export_state()
    del state["point_layers"], state["layer_id_counter"]
    loaded = Mesh.from_state(state)
    assert not loaded.has_point_layers() and loaded.export_state()["layer_id_counter"] == 1


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda layers: layers[0].update(kind="bones"),
        lambda layers: layers[0].update(kind="weights"),
        lambda layers: layers[0].update(new_point="keep"),
        lambda layers: layers[1].update(name=layers[0]["name"]),
        lambda layers: layers[1].update(id=layers[0]["id"]),
        lambda layers: layers[0]["values"].update({"9999": [1.0, 0.0, 0.0]}),
        lambda layers: layers[0]["values"].update({"0": [1.0, 0.0]}),
        lambda layers: layers[0]["values"].update({"0": [1.0, "NaN", 0.0]}),
        lambda layers: layers[0].pop("name"),
    ],
)
def test_invalid_layers_make_the_file_invalid_and_leave_the_mesh_unchanged(corrupt):
    mesh = _many_layers()
    state = json.loads(json.dumps(mesh.export_state()))
    corrupt(state["point_layers"])
    target = _grid(2)
    target.add_point_layer(PointLayerInfo("keep me"))
    before = json.dumps(target.export_state())
    with pytest.raises(ValueError):
        target.load_state(state)
    assert json.dumps(target.export_state()) == before
    watched = _grid(2)
    change = watched.begin_change()
    with pytest.raises(ValueError):
        watched.load_state(state)
    watched.rollback_change(change)


def test_non_journal_load_drops_stale_layers():
    mesh = _many_layers()
    plain = _grid(3).export_state()
    mesh.load_state(plain)
    assert not mesh.has_point_layers()
    assert mesh.export_state()["point_layers"] is None
    assert mesh.export_state()["layer_id_counter"] == 5  # counters stay forward


def test_load_under_a_journal_records_only_differing_values():
    mesh = _many_layers()
    start = mesh.export_state()
    lid = mesh.point_layer_ids()[0]
    vid = mesh.all_vertex_ids()[0]
    mesh.set_layer_value(lid, vid, (5.0, 5.0, 5.0))
    dropped = mesh.point_layer_ids()[1]
    mesh.remove_point_layer(dropped)
    mesh.add_point_layer(PointLayerInfo("extra"))
    after = json.dumps(mesh.export_state())
    delta, _ = record_mesh_change(mesh, lambda: mesh.load_state(start))
    assert json.dumps(mesh.export_state()["point_layers"]) == json.dumps(start["point_layers"])
    assert delta.layer_values == {lid: {vid: ((5.0, 5.0, 5.0), mesh.layer_value(lid, vid) if mesh.layer_value(lid, vid) != ZERO else None)}}
    assert dropped in delta.layer_whole  # a layer that comes back: a whole-layer record
    mesh.apply_delta(delta, reverse=True)
    assert json.dumps(mesh.export_state()) == after
    assert_layer_invariants(mesh)


# -- T-8: map_vector_layers ------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(8))
def test_map_vector_layers_on_random_matrices(seed):
    rng = random.Random(seed)
    mesh, lid = _layered(3, seed=seed, dense=bool(seed % 2))
    zero_rule = mesh.add_point_layer(PointLayerInfo("Z", new_point="zero"))
    mesh.set_layer_value(zero_rule, mesh.all_vertex_ids()[0], (1.0, 2.0, 3.0))
    m = tuple(tuple(rng.uniform(-2, 2) for _ in range(3)) for _ in range(3))
    old = {l: dict(mesh.layer_items(l)) for l in mesh.point_layer_ids()}
    history = HistoryStack()
    before = json.dumps(mesh.export_state())
    change = mesh.begin_change()
    mesh.map_vector_layers(m)
    assert change.layer_values == {} and set(change.layer_whole) == set(old)
    delta = mesh.end_change(change)
    history.push(MeshDeltaCommand(mesh, delta, "map"))
    for l, values in old.items():
        for vid, (x, y, z) in values.items():
            assert mesh.layer_value(l, vid) == tuple(r[0] * x + r[1] * y + r[2] * z for r in m)
    after = json.dumps(mesh.export_state())
    history.undo()
    assert json.dumps(mesh.export_state()) == before
    history.redo()
    assert json.dumps(mesh.export_state()) == after
    assert_layer_invariants(mesh)


def test_identity_map_records_nothing_and_axis_mirror_is_exact():
    mesh, lid = _layered(seed=9)
    delta, _ = record_mesh_change(mesh, lambda: mesh.map_vector_layers(((1, 0, 0), (0, 1, 0), (0, 0, 1))))
    assert delta.empty
    values = dict(mesh.layer_items(lid))
    mesh.map_vector_layers(((-1, 0, 0), (0, 1, 0), (0, 0, 1)))
    assert all(mesh.layer_value(lid, v) == (-x, y, z) for v, (x, y, z) in values.items())
    with pytest.raises(MeshError):
        mesh.map_vector_layers(((1, 0), (0, 1)))
    with pytest.raises(MeshError):
        mesh.map_vector_layers(((float("nan"), 0, 0), (0, 1, 0), (0, 0, 1)))


def test_singular_map_keeps_the_canonical_form():
    mesh, lid = _layered(seed=10)
    mesh.map_vector_layers(((0, 0, 0), (0, 0, 0), (0, 0, 0)))
    assert mesh.layer_items(lid) == []
    assert_layer_invariants(mesh)
