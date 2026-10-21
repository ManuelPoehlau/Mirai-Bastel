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
from core.mesh import Mesh, MeshError, SymmetryDefinition
from core.operations import MeshDeltaCommand, record_mesh_change
from tests.mesh_invariants import assert_mesh_invariants


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
    return state["vertex_id_counter"], state["edge_id_counter"], state["face_id_counter"]


def _scan_vertex_edges(mesh: Mesh, vid) -> list:
    return [e for e in mesh.all_edge_ids() if vid in mesh.edge_vertices(e)]


# -- one random mutation per call ------------------------------------------------------------


def _random_op(mesh: Mesh, rng: random.Random) -> None:
    """One mutation through a public Mesh method; MeshError refusals are part of the sample."""
    faces, edges, vertices = mesh.all_face_ids(), mesh.all_edge_ids(), mesh.all_vertex_ids()
    kind = rng.choice(
        ["split_edge", "split_face", "connect", "dissolve_edges", "dissolve_faces",
         "dissolve_vertex", "delete_faces", "delete_edges", "delete_vertices", "move",
         "add_face", "symmetry", "collapse"]
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


def test_end_change_of_an_inactive_recording_is_refused():
    mesh = _grid(1)
    change = mesh.begin_change()
    mesh.end_change(change)
    with pytest.raises(MeshError):
        mesh.end_change(change)
