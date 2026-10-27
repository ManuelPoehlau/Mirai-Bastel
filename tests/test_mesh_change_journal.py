"""Contract tests for the Core change journal (AD-023 H1, CORE_V1_FREEZE §7.1 2026-10-21):
`Mesh.begin_change` / `end_change` / `rollback_change` / `apply_delta`, `MeshDeltaCommand`,
`MeshWatch`, the vertex -> edge index and the ascending-ID order invariant.

The oracle is the whole-mesh snapshot (`export_state()` and the container key order), i.e.
exactly what `MeshStateCommand` guaranteed: after every recorded mutation, Undo and Redo of the
delta must reproduce the snapshot taken before / after it, including the iteration order of all
three containers, `edge.faces` order and the symmetry definition; ID counters only move forward.
Randomised sequences over every mutation method are the standing guard (AD-023 §3).
"""

from __future__ import annotations

import gc
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import HistoryStack, VertexId
from core.mesh import FaceRegion, FaceRegions, Mesh, MeshError, PointLayerInfo, SymmetryDefinition
from core.operations import MeshDeltaCommand, record_mesh_change
from core.operations.collapse import collapse_elements
from tests.mesh_invariants import assert_layer_invariants, assert_mesh_invariants


def _grid(n: int) -> Mesh:
    mesh = Mesh()
    ids = [[mesh.add_vertex((float(x), float(y), 0.0)) for x in range(n + 1)] for y in range(n + 1)]
    for y in range(n):
        for x in range(n):
            mesh.add_face([ids[y][x], ids[y][x + 1], ids[y + 1][x + 1], ids[y + 1][x]])
    return mesh


def _body(mesh: Mesh) -> dict:
    state = mesh.export_state()
    return {k: v for k, v in state.items() if not k.endswith("_counter")}


def _orders(mesh: Mesh) -> tuple:
    return (mesh.all_vertex_ids(), mesh.all_edge_ids(), mesh.all_face_ids())


def _snapshot(mesh: Mesh) -> tuple:
    return _body(mesh), _orders(mesh)


def _counters(mesh: Mesh) -> tuple:
    state = mesh.export_state()
    return (
        state["vertex_id_counter"], state["edge_id_counter"], state["face_id_counter"],
        state["layer_id_counter"],
    )


def _scan_vertex_edges(mesh: Mesh, vid) -> list:
    return [e for e in mesh.all_edge_ids() if vid in mesh.edge_vertices(e)]


# -- one random mutation per call ------------------------------------------------------------


def _random_op(mesh: Mesh, rng: random.Random) -> None:
    """One mutation through a public Mesh method; MeshError refusals are part of the sample."""
    faces, edges, vertices = mesh.all_face_ids(), mesh.all_edge_ids(), mesh.all_vertex_ids()
    kind = rng.choice(
        ["split_edge", "split_face", "connect", "dissolve_edges", "dissolve_faces",
         "dissolve_vertex", "delete_faces", "delete_edges", "delete_vertices", "move",
         "add_face", "symmetry", "collapse", "regions"]
    )
    if kind == "split_edge" and edges:
        mesh.split_edge(rng.choice(edges), rng.uniform(0.2, 0.8))
    elif kind in ("split_face", "connect") and faces:
        f = rng.choice(faces)
        boundary = mesh.face_vertices(f)
        if len(boundary) >= 4:
            a, b = rng.sample(boundary, 2)
            if kind == "connect":
                mesh.connect_vertices(f, a, b)
            else:
                pa, pb = mesh.vertex_position(a), mesh.vertex_position(b)
                mid = tuple((x + y) / 2 for x, y in zip(pa, pb))
                mesh.split_face(f, a, b, [mid])
    elif kind == "dissolve_edges" and edges:
        mesh.dissolve_edges(rng.sample(edges, min(len(edges), rng.randint(1, 3))), cleanup=rng.random() < 0.5)
    elif kind == "dissolve_faces" and faces:
        mesh.dissolve_faces(rng.sample(faces, min(len(faces), rng.randint(2, 4))), cleanup=rng.random() < 0.5)
    elif kind == "dissolve_vertex" and vertices:
        mesh.dissolve_vertex(rng.choice(vertices))
    elif kind == "delete_faces" and faces:
        mesh.delete_faces(rng.sample(faces, min(len(faces), rng.randint(1, 3))))
    elif kind == "delete_edges" and edges:
        mesh.delete_edges(rng.sample(edges, 1))
    elif kind == "delete_vertices" and vertices:
        mesh.delete_vertices(rng.sample(vertices, 1))
    elif kind == "move" and vertices:
        for vid in rng.sample(vertices, min(len(vertices), 3)):
            x, y, z = mesh.vertex_position(vid)
            mesh.set_vertex_position(vid, (x, y, z + rng.uniform(-0.3, 0.3)))
    elif kind == "add_face" and len(vertices) >= 3:
        new = [mesh.add_vertex((rng.random(), rng.random(), 2.0)) for _ in range(3)]
        mesh.add_face(new)
    elif kind == "symmetry":
        seam = frozenset(rng.sample(edges, min(len(edges), 2)))
        mesh.symmetry_definition = (
            None if mesh.symmetry_definition is not None
            else SymmetryDefinition((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), seam)
        )
    elif kind == "collapse" and edges:
        mesh.collapse_edge(rng.choice(edges))
    elif kind == "regions" and faces:
        # dead IDs stay in the value on purpose (AD-REGIONS-01): only readers filter
        mesh.face_regions = None if rng.random() < 0.2 else FaceRegions(
            (FaceRegion("A", frozenset(rng.sample(faces, min(len(faces), 3)))),
             FaceRegion("B", frozenset(rng.sample(faces, 1))))
        )


def _recorded_step(mesh: Mesh, rng: random.Random):
    try:
        return record_mesh_change(mesh, lambda: _random_op(mesh, rng))[0]
    except MeshError:
        return None


# -- tests -------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(12))
def test_random_sequences_undo_redo_match_snapshots(seed):
    rng = random.Random(seed)
    mesh = _grid(4)
    history = HistoryStack()
    snapshots = [_snapshot(mesh)]
    for _ in range(25):
        before = _snapshot(mesh)
        counters = _counters(mesh)
        delta = _recorded_step(mesh, rng)
        if delta is None:
            # A refusal through the journal leaves the mesh exactly as it was.
            assert _snapshot(mesh) == before
            continue
        if delta.empty:
            assert _body(mesh) == before[0]
            continue
        history.push(MeshDeltaCommand(mesh, delta, "op"))
        snapshots.append(_snapshot(mesh))
        assert _counters(mesh) >= counters
    # Undo to the start, checking every intermediate state, then Redo to the end.
    for expected in reversed(snapshots[:-1]):
        counters = _counters(mesh)
        history.undo()
        assert _snapshot(mesh) == expected
        assert _counters(mesh) == counters  # Undo never lowers a counter (AD-001)
    assert_mesh_invariants(mesh)  # the grid itself (collapse_edge may leave invalid meshes)
    for expected in snapshots[1:]:
        history.redo()
        assert _snapshot(mesh) == expected


@pytest.mark.parametrize("seed", range(6))
def test_rollback_restores_exactly_also_nested(seed):
    rng = random.Random(100 + seed)
    mesh = _grid(3)
    outer_start = _snapshot(mesh)
    outer = mesh.begin_change()
    for _ in range(4):
        try:
            _random_op(mesh, rng)
        except MeshError:
            pass
    middle = _snapshot(mesh)
    inner = mesh.begin_change()
    for _ in range(4):
        try:
            _random_op(mesh, rng)
        except MeshError:
            pass
    mesh.rollback_change(inner)
    assert _snapshot(mesh) == middle
    mesh.rollback_change(outer)
    assert _snapshot(mesh) == outer_start
    assert_mesh_invariants(mesh)


def test_rollback_on_exception_through_record_mesh_change():
    mesh = _grid(2)
    before = _snapshot(mesh)

    def broken():
        mesh.delete_faces(mesh.all_face_ids()[:1])
        mesh.split_edge(mesh.all_edge_ids()[0])
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        record_mesh_change(mesh, broken)
    assert _snapshot(mesh) == before
    assert not mesh._logs


def test_load_state_under_a_journal_is_recorded_exactly():
    """`load_state` inside a recording (old rollback code paths) writes only the differing
    elements, and the delta it produces undoes / redoes like any other."""
    mesh = _grid(3)
    start = mesh.export_state()
    start_snap = _snapshot(mesh)
    mesh.delete_faces(mesh.all_face_ids()[2:4])
    mesh.split_edge(mesh.all_edge_ids()[0])
    after_snap = _snapshot(mesh)
    delta, _ = record_mesh_change(mesh, lambda: mesh.load_state(start))
    assert _snapshot(mesh) == start_snap
    mesh.apply_delta(delta, reverse=True)
    assert _snapshot(mesh) == after_snap
    mesh.apply_delta(delta)
    assert _snapshot(mesh) == start_snap


def test_unchanged_mutation_gives_an_empty_delta():
    mesh = _grid(2)
    vid = mesh.all_vertex_ids()[0]
    p = mesh.vertex_position(vid)

    def wiggle():
        mesh.set_vertex_position(vid, (9.0, 9.0, 9.0))
        mesh.set_vertex_position(vid, p)

    delta, _ = record_mesh_change(mesh, wiggle)
    assert delta.empty


def test_delta_is_local():
    """A Delete of one face on a 20 x 20 grid records its neighbourhood, not the mesh."""
    mesh = _grid(20)
    face = mesh.all_face_ids()[210]
    delta, _ = record_mesh_change(mesh, lambda: mesh.delete_faces([face]))
    assert len(delta.faces) == 1
    assert len(delta.edges) <= 4
    assert len(delta.vertices) == 0


def test_vertex_edges_index_matches_the_scan():
    rng = random.Random(7)
    mesh = _grid(4)
    for _ in range(40):
        try:
            _random_op(mesh, rng)
        except MeshError:
            pass
        for vid in mesh.all_vertex_ids():
            assert mesh.vertex_edges(vid) == _scan_vertex_edges(mesh, vid)
    assert mesh.vertex_edges(VertexId(10_000)) == []


def test_containers_stay_ascending():
    rng = random.Random(3)
    mesh = _grid(4)
    history = HistoryStack()
    for _ in range(30):
        delta = _recorded_step(mesh, rng)
        if delta is not None and not delta.empty:
            history.push(MeshDeltaCommand(mesh, delta, "op"))
    while history.can_undo():
        history.undo()
        for ids in _orders(mesh):
            assert ids == sorted(ids)


def test_load_state_establishes_ascending_order():
    mesh = _grid(1)
    state = mesh.export_state()
    state["vertices"] = dict(reversed(list(state["vertices"].items())))
    other = Mesh.from_state(state)
    assert other.all_vertex_ids() == sorted(other.all_vertex_ids())
    assert _body(other) == _body(mesh)


def test_watch_records_everything_until_taken_and_detaches_on_gc():
    mesh = _grid(2)
    watch = mesh.watch()
    face = mesh.all_face_ids()[0]
    mesh.delete_faces([face])
    change = watch.take()
    assert face in change.faces and change.faces[face] is not None
    assert watch.peek().is_empty()
    vid = mesh.all_vertex_ids()[0]
    mesh.set_vertex_position(vid, (5.0, 5.0, 5.0))
    assert vid in watch.peek().vertices
    del watch
    gc.collect()
    assert not mesh._logs


def test_watch_sees_undo_redo_and_rollback():
    mesh = _grid(2)
    watch = mesh.watch()
    delta, _ = record_mesh_change(mesh, lambda: mesh.delete_faces(mesh.all_face_ids()[:1]))
    watch.take()
    mesh.apply_delta(delta, reverse=True)
    assert set(watch.take().faces) == set(delta.faces)
    change = mesh.begin_change()
    mesh.split_edge(mesh.all_edge_ids()[0])
    mesh.rollback_change(change)
    seen = watch.take()
    assert seen.vertices and seen.edges  # created and removed again: touched
    watch.close()
    assert not mesh._logs


def test_symmetry_definition_rides_in_the_delta():
    mesh = _grid(2)
    definition = SymmetryDefinition((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), frozenset())

    def set_it():
        mesh.symmetry_definition = definition

    delta, _ = record_mesh_change(mesh, set_it)
    assert delta.symmetry == (None, definition)
    mesh.apply_delta(delta, reverse=True)
    assert mesh.symmetry_definition is None
    mesh.apply_delta(delta)
    assert mesh.symmetry_definition == definition


def test_face_regions_ride_in_the_delta():
    mesh = _grid(2)
    faces = mesh.all_face_ids()
    regions = FaceRegions((FaceRegion("Brow", frozenset(faces[:2])),))

    def set_it():
        mesh.face_regions = regions

    delta, _ = record_mesh_change(mesh, set_it)
    assert delta.regions == (None, regions) and not delta.empty
    mesh.apply_delta(delta, reverse=True)
    assert mesh.face_regions is None
    mesh.apply_delta(delta)
    assert mesh.face_regions == regions
    # setting the same value again records nothing
    delta, _ = record_mesh_change(mesh, lambda: setattr(mesh, "face_regions", regions))
    assert delta.empty


def test_regions_survive_rollback_and_nested_checkpoints():
    mesh = _grid(2)
    faces = mesh.all_face_ids()
    first = FaceRegions((FaceRegion("A", frozenset(faces[:1])),))
    second = FaceRegions((FaceRegion("A", frozenset(faces[:3])), FaceRegion("B", frozenset(faces[3:]))))
    mesh.face_regions = first
    outer = mesh.begin_change()
    mesh.face_regions = second
    inner = mesh.begin_change()
    mesh.face_regions = None
    mesh.rollback_change(inner)
    assert mesh.face_regions == second
    mesh.rollback_change(outer)
    assert mesh.face_regions == first
    checkpoint = mesh.begin_change()
    mesh.face_regions = second
    mesh.revert_change(checkpoint)
    assert mesh.face_regions == first and checkpoint.is_empty()
    mesh.face_regions = second
    mesh.revert_change(checkpoint)
    assert mesh.face_regions == first
    mesh.release_change(checkpoint)


def test_regions_only_change_is_not_empty_for_a_watch():
    mesh = _grid(1)
    watch = mesh.watch()
    mesh.face_regions = FaceRegions((FaceRegion("A", frozenset(mesh.all_face_ids())),))
    change = watch.take()
    assert not change.is_empty() and change.regions_touched
    assert not (change.vertices or change.edges or change.faces)
    watch.close()


def test_regions_validation_and_empty_normalisation():
    mesh = _grid(1)
    face = mesh.all_face_ids()[0]
    with pytest.raises(MeshError):
        FaceRegion("", frozenset())
    with pytest.raises(MeshError):
        FaceRegion("A", frozenset({1}))
    with pytest.raises(MeshError):
        FaceRegions((FaceRegion("A"), FaceRegion("A")))
    with pytest.raises(MeshError):
        mesh.face_regions = "nope"
    mesh.face_regions = FaceRegions((FaceRegion("A", frozenset({face})),))
    mesh.face_regions = FaceRegions(())
    assert mesh.face_regions is None


def test_end_change_of_an_inactive_recording_is_refused():
    mesh = _grid(1)
    change = mesh.begin_change()
    mesh.end_change(change)
    with pytest.raises(MeshError):
        mesh.end_change(change)


# -- point layers (AD-025 §4.2, T-1 / T-2) ------------------------------------------------------


def _layered_grid(n: int, rng: random.Random) -> Mesh:
    """A grid with three layers: two sparse vector layers and one with the `zero` rule."""
    mesh = _grid(n)
    vertices = mesh.all_vertex_ids()
    for name, rule in (("A", "interpolate"), ("B", "interpolate"), ("Z", "zero")):
        lid = mesh.add_point_layer(PointLayerInfo(name, new_point=rule))
        for vid in rng.sample(vertices, len(vertices) // 3):
            mesh.set_layer_value(lid, vid, (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
    return mesh


def _random_value(rng: random.Random) -> tuple:
    return (0.0, 0.0, 0.0) if rng.random() < 0.15 else (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))


def _random_matrix(rng: random.Random) -> tuple:
    return tuple(tuple(rng.uniform(-1.5, 1.5) for _ in range(3)) for _ in range(3))


def _random_layer_op(mesh: Mesh, rng: random.Random, counter: list) -> None:
    """One mutation on a layered mesh: every primitive (through `_random_op`; `add_vertex` without
    an origin and `split_face` with interior points refuse there), plus `add_vertex(origin)`,
    `split_face(..., origins=...)` (AD-025 Phase 5: weights over the face's corners, as the Knife
    passes them), Collapse and every layer write."""
    layers = mesh.point_layer_ids()
    vertices = mesh.all_vertex_ids()
    kind = rng.choice(
        ["primitive", "primitive", "primitive", "origin", "split_face", "split_face", "collapse", "set", "set",
         "map", "map_then_set", "add_layer", "remove_layer", "rename", "reorder"]
    )
    if kind == "primitive":
        _random_op(mesh, rng)
    elif kind == "split_face" and mesh.all_face_ids():
        f = rng.choice(mesh.all_face_ids())
        boundary = mesh.face_vertices(f)
        if len(boundary) >= 3 and len(set(boundary)) == len(boundary):
            a, b = rng.sample(boundary, 2)
            positions, origins = [], []
            for _ in range(rng.randint(1, 3)):
                corners = rng.sample(boundary, 3)
                w = [rng.random() + 0.05 for _ in corners]
                w = [x / sum(w) for x in w]
                w[-1] = 1.0 - w[0] - w[1]
                positions.append(tuple(
                    sum(wi * mesh.vertex_position(c)[i] for wi, c in zip(w, corners)) for i in range(3)
                ))
                origins.append(() if rng.random() < 0.1 else tuple(zip(corners, w)))
            mesh.split_face(f, a, b, positions, origins=origins)
    elif kind == "origin" and len(vertices) >= 3:
        sources = rng.sample(vertices, rng.randint(1, 3))
        if len(sources) == 1:
            origin = ((sources[0], 1.0),)
        else:
            w = [rng.random() + 0.1 for _ in sources]
            origin = tuple((v, x / sum(w)) for v, x in zip(sources, w))
            origin = origin[:-1] + ((origin[-1][0], 1.0 - sum(x for _, x in origin[:-1])),)
        if rng.random() < 0.15:
            origin = ()
        new = [mesh.add_vertex((rng.random(), rng.random(), 2.0), origin=origin) for _ in range(3)]
        mesh.add_face(new)
    elif kind == "collapse" and vertices:
        v = rng.choice(vertices)
        group = [v] + [mesh.edge_vertices(e)[0] if mesh.edge_vertices(e)[1] == v else mesh.edge_vertices(e)[1]
                       for e in mesh.vertex_edges(v)[:rng.randint(1, 2)]]
        collapse_elements(mesh, group)
    elif kind == "set" and layers and vertices:
        lid = rng.choice(layers)
        for vid in rng.sample(vertices, min(len(vertices), rng.randint(1, 4))):
            mesh.set_layer_value(lid, vid, _random_value(rng))
    elif kind == "map":
        mesh.map_vector_layers(_random_matrix(rng))
    elif kind == "map_then_set" and layers and vertices:
        # sparse edits before and after a bulk write in the same recording
        lid = rng.choice(layers)
        mesh.set_layer_value(lid, rng.choice(vertices), _random_value(rng))
        mesh.map_vector_layers(_random_matrix(rng))
        mesh.set_layer_value(lid, rng.choice(vertices), _random_value(rng))
        if rng.random() < 0.5:
            mesh.remove_point_layer(lid)
    elif kind == "add_layer":
        counter[0] += 1
        lid = mesh.add_point_layer(PointLayerInfo(f"N{counter[0]}", new_point=rng.choice(["interpolate", "zero"])))
        for vid in rng.sample(vertices, min(len(vertices), 3)):
            mesh.set_layer_value(lid, vid, _random_value(rng))
    elif kind == "remove_layer" and layers:
        mesh.remove_point_layer(rng.choice(layers))
    elif kind == "rename" and layers:
        lid = rng.choice(layers)
        counter[0] += 1
        info = mesh.point_layer_info(lid)
        mesh.set_point_layer_info(lid, PointLayerInfo(f"R{counter[0]}", info.kind, rng.choice(["interpolate", "zero"])))
    elif kind == "reorder" and len(layers) > 1:
        mesh.set_point_layer_order(rng.sample(layers, len(layers)))


def _export_text(mesh: Mesh) -> str:
    import json

    return json.dumps(mesh.export_state()["point_layers"])


@pytest.mark.parametrize("seed,steps", [(seed, 25) for seed in range(12)] + [(99, 300)])
def test_layered_random_sequences_undo_redo_match_snapshots(seed, steps):
    """T-1: exactness contract (1)-(7) with point layers, copy-on-write included - a shared dict
    mutated by a later write would make an earlier Undo / Redo state differ from its snapshot."""
    rng = random.Random(1000 + seed)
    mesh = _layered_grid(4, rng)
    kinds: dict = {}
    counter = [0]
    history = HistoryStack()
    snapshots = [(_snapshot(mesh), _export_text(mesh))]
    for _ in range(steps):
        before = _snapshot(mesh)
        counters = _counters(mesh)
        try:
            delta = record_mesh_change(mesh, lambda: _random_layer_op(mesh, rng, counter))[0]
        except MeshError:
            assert _snapshot(mesh) == before
            assert_layer_invariants(mesh, kinds=kinds)
            continue
        assert_layer_invariants(mesh, kinds=kinds)
        assert _counters(mesh) >= counters
        # Per layer a delta holds per-element records or one whole-layer record, never both: that
        # is why the apply order of the two shapes cannot change the result (AD-025 §4.2).
        assert not set(delta.layer_values) & set(delta.layer_whole)
        if delta.empty:
            assert _body(mesh) == before[0]
            continue
        history.push(MeshDeltaCommand(mesh, delta, "op"))
        snapshots.append((_snapshot(mesh), _export_text(mesh)))
    for expected in reversed(snapshots[:-1]):
        counters = _counters(mesh)
        history.undo()
        assert (_snapshot(mesh), _export_text(mesh)) == expected
        assert _counters(mesh) == counters
        assert_layer_invariants(mesh, kinds=kinds)
    for expected in snapshots[1:]:
        history.redo()
        assert (_snapshot(mesh), _export_text(mesh)) == expected
        assert_layer_invariants(mesh, kinds=kinds)


@pytest.mark.parametrize("seed", range(6))
def test_layered_rollback_restores_exactly_also_nested(seed):
    """T-2: nested rollback with both record shapes (per element and whole layer)."""
    rng = random.Random(200 + seed)
    mesh = _layered_grid(3, rng)
    counter = [0]

    def some_ops():
        for _ in range(5):
            try:
                _random_layer_op(mesh, rng, counter)
            except MeshError:
                pass

    outer_start = (_snapshot(mesh), _export_text(mesh))
    outer = mesh.begin_change()
    some_ops()
    middle = (_snapshot(mesh), _export_text(mesh))
    inner = mesh.begin_change()
    some_ops()
    mesh.rollback_change(inner)
    assert (_snapshot(mesh), _export_text(mesh)) == middle
    mesh.rollback_change(outer)
    assert (_snapshot(mesh), _export_text(mesh)) == outer_start
    assert_layer_invariants(mesh)
    assert not mesh._logs


@pytest.mark.parametrize("seed", range(4))
def test_layered_checkpoints_revert_and_release(seed):
    """T-2: the Knife checkpoint pattern - a session recording with checkpoints that are reverted
    (several times) or released, ending in one delta that undoes / redoes exactly."""
    rng = random.Random(300 + seed)
    mesh = _layered_grid(3, rng)
    counter = [0]
    start = (_snapshot(mesh), _export_text(mesh))
    session = mesh.begin_change()
    for _ in range(4):
        checkpoint = mesh.begin_change()
        here = (_snapshot(mesh), _export_text(mesh))
        for _ in range(2):
            for _ in range(3):
                try:
                    _random_layer_op(mesh, rng, counter)
                except MeshError:
                    pass
            mesh.revert_change(checkpoint)
            assert (_snapshot(mesh), _export_text(mesh)) == here
            assert checkpoint.is_empty()
        for _ in range(3):
            try:
                _random_layer_op(mesh, rng, counter)
            except MeshError:
                pass
        mesh.release_change(checkpoint)
    end = (_snapshot(mesh), _export_text(mesh))
    delta = mesh.end_change(session)
    mesh.apply_delta(delta, reverse=True)
    assert (_snapshot(mesh), _export_text(mesh)) == start
    mesh.apply_delta(delta)
    assert (_snapshot(mesh), _export_text(mesh)) == end
    assert_layer_invariants(mesh)


def test_watch_sees_layer_changes_as_keys_without_values():
    """T-2: a watch records which layers / vertices changed, never their before-values."""
    rng = random.Random(5)
    mesh = _layered_grid(2, rng)
    lid = mesh.point_layer_ids()[0]
    vid = mesh.all_vertex_ids()[0]
    watch = mesh.watch()
    mesh.set_layer_value(lid, vid, (1.0, 2.0, 3.0))
    change = watch.take()
    assert not change.is_empty() and change.layers_touched
    assert change.layer_values == {lid: {vid: None}}
    assert not (change.vertices or change.edges or change.faces)
    mesh.map_vector_layers(((2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 2.0)))
    change = watch.take()
    assert set(change.layer_whole) == set(mesh.point_layer_ids())
    assert all(record == (None, None) for record in change.layer_whole.values())
    watch.close()


def test_layer_only_change_is_a_non_empty_delta():
    mesh = _grid(1)

    def add():
        lid = mesh.add_point_layer(PointLayerInfo("Smile"))
        mesh.set_layer_value(lid, mesh.all_vertex_ids()[0], (0.0, 0.5, 0.0))

    delta, _ = record_mesh_change(mesh, add)
    assert not delta.empty and not (delta.vertices or delta.edges or delta.faces)
    mesh.apply_delta(delta, reverse=True)
    assert not mesh.has_point_layers() and mesh.export_state()["point_layers"] is None
    mesh.apply_delta(delta)
    assert [v for _, v in mesh.layer_items(mesh.point_layer_ids()[0])] == [(0.0, 0.5, 0.0)]
    # writing the same value again records nothing
    lid = mesh.point_layer_ids()[0]
    delta, _ = record_mesh_change(mesh, lambda: mesh.set_layer_value(lid, mesh.all_vertex_ids()[0], (0.0, 0.5, 0.0)))
    assert delta.empty


def test_bulk_write_journals_o_layers_and_shares_dicts():
    """§4.2: a bulk operation records one old dict per layer (no per-element records), and the
    delta's dicts are never mutated by later writes (copy-on-write)."""
    mesh = _grid(6)
    lid = mesh.add_point_layer(PointLayerInfo("A"))
    for vid in mesh.all_vertex_ids():
        mesh.set_layer_value(lid, vid, (1.0, 1.0, 1.0))
    outer = mesh.begin_change()
    watch = mesh.watch()
    mesh.map_vector_layers(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
    assert outer.layer_values == {} and set(outer.layer_whole) == {lid}
    assert watch.peek().layer_whole == {lid: (None, None)}
    delta = mesh.end_change(outer)
    before, after = delta.layer_whole[lid]
    frozen_before, frozen_after = dict(before), dict(after)
    vid = mesh.all_vertex_ids()[0]
    mesh.set_layer_value(lid, vid, (9.0, 9.0, 9.0))  # must copy, not touch the delta's dict
    assert after == frozen_after and before == frozen_before
    mesh.apply_delta(delta, reverse=True)
    mesh.set_layer_value(lid, vid, (7.0, 7.0, 7.0))
    assert before == frozen_before
    watch.close()
