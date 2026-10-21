"""Incremental topology sync of `RenderMesh` (AD-023 V1, 2026-10-21): a journal patch must leave
the buffers holding, per element, what a fresh full build of the same mesh holds.

Oracle: a new `RenderMesh` on the same mesh (the full-rebuild path). Compared per live element,
because the patched layout keeps slots (dead slots, spare capacity) while the fresh one is compact:
positions and normals per vertex (normals within 1e-9: a vertex normal is a sum over a set of
faces whose iteration order may differ), the triangles of every face in order and their face row,
the face-data row, `triangle_faces`, highlight flags, adjacency; every other triangle slot is
degenerate and every free vertex slot holds `DEAD_POSITION`. Sequences mix every topology
operation with Undo / Redo through `MeshDeltaCommand` and positions-only moves between syncs.
"""

from __future__ import annotations

import random

import pytest

import tests._bootstrap  # noqa: F401

import viewport.render_mesh as render_mesh_module
from core import HistoryStack, Selection, SelectionMode
from core.mesh import Mesh, MeshError
from core.operations import MeshDeltaCommand, record_mesh_change
from viewport.overlay import SelectionOverlay
from viewport.render_mesh import (
    DEAD_POSITION, FACE_DATA, FACE_ROW_FLOATS, TRIANGLE_FACES, RenderMesh,
)
from viewport.resource_store import TraceStore


@pytest.fixture(autouse=True)
def _always_incremental(monkeypatch):
    # Small test meshes take the patch path too (production patches from 2048 elements on).
    monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 0)
    monkeypatch.setattr(render_mesh_module, "SPARE_FRACTION", 0.5)


def _grid(n: int) -> Mesh:
    mesh = Mesh()
    ids = [[mesh.add_vertex((float(x), float(y), 0.1 * ((x * y) % 3))) for x in range(n + 1)] for y in range(n + 1)]
    for y in range(n):
        for x in range(n):
            mesh.add_face([ids[y][x], ids[y][x + 1], ids[y + 1][x + 1], ids[y + 1][x]])
    return mesh


def _close(a, b, tol=1e-9) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b)) and len(a) == len(b)


def assert_equivalent(rm: RenderMesh) -> None:
    mesh = rm.mesh
    fresh = RenderMesh(mesh, overlay=rm.overlay, store_type=TraceStore)
    data, ref = rm.store.data, fresh.store.data
    positions, normals, indices = data("positions"), data("normals"), data("indices")
    rpos, rnorm = ref("positions"), ref("normals")

    live = set(mesh.all_vertex_ids())
    assert set(rm._vertex_index) == live
    for v in live:
        i, j = rm.vertex_index_of(v), fresh.vertex_index_of(v)
        assert positions[3 * i:3 * i + 3] == pytest.approx(rpos[3 * j:3 * j + 3], abs=1e-6)
        assert _close(normals[3 * i:3 * i + 3], rnorm[3 * j:3 * j + 3], 1e-6), v
        assert _close(rm.derived.vertex_normals[v], fresh.derived.vertex_normals[v])
    for slot, v in enumerate(rm._slot_vertex):
        if v is None:
            assert tuple(positions[3 * slot:3 * slot + 3]) == pytest.approx(DEAD_POSITION)

    assert rm.derived.vertex_to_faces == fresh.derived.vertex_to_faces
    assert set(rm._face_row) == set(mesh.all_face_ids())
    rows, ref_rows = data(TRIANGLE_FACES), ref(TRIANGLE_FACES)
    face_data, ref_face_data = data(FACE_DATA), ref(FACE_DATA)
    live_slots = set()
    for f in mesh.all_face_ids():
        mine = [rm._triangle_indices[t] for t in rm._face_triangles[f]]
        theirs = [fresh._triangle_indices[t] for t in fresh._face_triangles[f]]
        assert mine == theirs, f
        row, ref_row = rm._face_row[f], fresh._face_row[f]
        for t in rm._face_triangles[f]:
            live_slots.add(t)
            assert int(rows[t]) == row
            tri = rm._triangle_indices[t]
            assert indices[3 * t:3 * t + 3] == [float(rm.vertex_index_of(v)) for v in tri]
        assert _close(
            face_data[row * FACE_ROW_FLOATS:(row + 1) * FACE_ROW_FLOATS],
            ref_face_data[ref_row * FACE_ROW_FLOATS:(ref_row + 1) * FACE_ROW_FLOATS], 1e-6,
        ), f
        assert _close(rm.derived.face_normals[f], fresh.derived.face_normals[f])
    for t in range(len(indices) // 3):
        if t not in live_slots:
            assert indices[3 * t:3 * t + 3] == [0.0, 0.0, 0.0]
            assert rm._triangle_indices[t] is None
    assert len(rows) == len(rm._triangle_indices)
    # Edge slots (AD-022 B2): every live edge's slot holds its two vertex slots, every free slot (0, 0).
    assert set(rm._edge_slot) == set(mesh.all_edge_ids())
    edge_live = set()
    for e, slot in rm._edge_slot.items():
        edge_live.add(slot)
        a, b = mesh.edge_vertices(e)
        assert tuple(rm.edge_indices[2 * slot:2 * slot + 2]) == (rm.vertex_index_of(a), rm.vertex_index_of(b))
        assert rm.edge_of_slot(slot) == e
    for slot in range(len(rm.edge_indices) // 2):
        if slot not in edge_live:
            assert tuple(rm.edge_indices[2 * slot:2 * slot + 2]) == (0, 0)
    for t, tri in enumerate(rm._triangle_indices):
        face = rm.face_of_triangle(t)
        assert (face is None) == (tri is None)
        if face is not None:
            assert t in rm._face_triangles[face]
    flags, ref_flags = data("highlight_flags"), ref("highlight_flags")
    for v in live if rm.overlay is not None else ():
        assert flags[rm.vertex_index_of(v)] == ref_flags[fresh.vertex_index_of(v)]
    fresh._watch.close()


def _op(mesh: Mesh, rng: random.Random) -> None:
    faces, edges, vertices = mesh.all_face_ids(), mesh.all_edge_ids(), mesh.all_vertex_ids()
    kind = rng.choice(["split_edge", "split_face", "dissolve_edges", "dissolve_faces", "delete_faces",
                       "delete_vertices", "extrude_like", "move"])
    if kind == "split_edge" and edges:
        mesh.split_edge(rng.choice(edges), rng.uniform(0.2, 0.8))
    elif kind == "split_face" and faces:
        f = rng.choice(faces)
        b = mesh.face_vertices(f)
        if len(b) >= 4:
            a, c = b[0], b[2]
            pa, pc = mesh.vertex_position(a), mesh.vertex_position(c)
            mesh.split_face(f, a, c, [tuple((x + y) / 2 for x, y in zip(pa, pc))])
    elif kind == "dissolve_edges" and edges:
        mesh.dissolve_edges([rng.choice(edges)], cleanup=rng.random() < 0.5)
    elif kind == "dissolve_faces" and faces:
        mesh.dissolve_faces(rng.sample(faces, min(len(faces), 2)), cleanup=True)
    elif kind == "delete_faces" and faces:
        mesh.delete_faces(rng.sample(faces, min(len(faces), rng.randint(1, 3))))
    elif kind == "delete_vertices" and vertices:
        mesh.delete_vertices([rng.choice(vertices)])
    elif kind == "extrude_like" and faces:
        f = rng.choice(faces)
        b = mesh.face_vertices(f)
        top = [mesh.add_vertex(tuple(c + (0.5 if k == 2 else 0.0) for k, c in enumerate(mesh.vertex_position(v)))) for v in b]
        for i in range(len(b)):
            mesh.add_face([b[i], b[(i + 1) % len(b)], top[(i + 1) % len(b)], top[i]])
        mesh.add_face(top)
        mesh.remove_face(f)
    elif kind == "move" and vertices:
        for v in rng.sample(vertices, min(len(vertices), 4)):
            x, y, z = mesh.vertex_position(v)
            mesh.set_vertex_position(v, (x + rng.uniform(-0.4, 0.4), y, z + rng.uniform(-0.4, 0.4)))


@pytest.mark.parametrize("seed", range(10))
def test_random_ops_undo_redo_patch_equals_full_build(seed):
    rng = random.Random(seed)
    mesh = _grid(6)
    selection = Selection()
    rm = RenderMesh(mesh, overlay=SelectionOverlay(selection), store_type=TraceStore)
    history = HistoryStack()
    for step in range(30):
        roll = rng.random()
        if roll < 0.2 and history.can_undo():
            history.undo()
        elif roll < 0.3 and history.can_redo():
            history.redo()
        elif roll < 0.4:
            # A W drag: positions only, through the geometry path.
            moved = set(rng.sample(mesh.all_vertex_ids(), min(3, len(mesh.all_vertex_ids()))))
            for v in moved:
                x, y, z = mesh.vertex_position(v)
                mesh.set_vertex_position(v, (x + 0.3, y - 0.2, z + 0.1))
            rm.mark_vertices_dirty(moved)
            rm.sync()
            continue
        else:
            try:
                delta, _ = record_mesh_change(mesh, lambda: _op(mesh, rng))
            except MeshError:
                continue
            if not delta.empty:
                history.push(MeshDeltaCommand(mesh, delta, "op"))
        if mesh.all_vertex_ids() and rng.random() < 0.3:
            selection.mode = SelectionMode.VERTEX
            selection.set({rng.choice(mesh.all_vertex_ids())})
        rm.mark_topology_dirty()
        if rng.random() < 0.8:  # sometimes two changes before one sync
            rm.sync()
            assert_equivalent(rm)
    rm.mark_topology_dirty()
    rm.sync()
    assert_equivalent(rm)
    assert rm.stats.get("topology_patches") > 0


def test_a_small_change_patches_instead_of_rebuilding():
    mesh = _grid(8)
    rm = RenderMesh(mesh, overlay=SelectionOverlay(Selection()), store_type=TraceStore)
    ids = rm.resource_ids()
    rebuilds = rm.stats.get("structural_rebuilds")
    mesh.delete_faces(mesh.all_face_ids()[10:12])
    rm.mark_topology_dirty()
    rm.sync()
    assert rm.resource_ids() == ids
    assert rm.stats.get("structural_rebuilds") == rebuilds
    assert rm.stats.get("topology_patches") == 1
    assert_equivalent(rm)


def test_spare_capacity_exhausted_falls_back_to_a_full_rebuild(monkeypatch):
    monkeypatch.setattr(render_mesh_module, "SPARE_FRACTION", 0.0)
    mesh = _grid(4)
    rm = RenderMesh(mesh, store_type=TraceStore)
    rebuilds = rm.stats.get("structural_rebuilds")
    mesh.split_edge(mesh.all_edge_ids()[0])  # a new vertex, no free slot
    rm.mark_topology_dirty()
    rm.sync()
    assert rm.stats.get("structural_rebuilds") > rebuilds
    assert_equivalent(rm)


def test_unreported_structure_on_a_geometry_sync_is_still_synced():
    """A caller that reports a topology change as moved vertices does not leave stale buffers."""
    mesh = _grid(4)
    rm = RenderMesh(mesh, store_type=TraceStore)
    mesh.delete_faces(mesh.all_face_ids()[:1])
    rm.mark_vertices_dirty({mesh.all_vertex_ids()[5]})
    rm.sync()
    assert_equivalent(rm)


def test_small_meshes_keep_the_compact_full_rebuild(monkeypatch):
    monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 2048)
    mesh = _grid(3)
    rm = RenderMesh(mesh, store_type=TraceStore)
    assert len(rm.store.data("positions")) == 3 * len(mesh.all_vertex_ids())
    mesh.delete_faces(mesh.all_face_ids()[:1])
    rm.mark_topology_dirty()
    rm.sync()
    assert rm.stats.get("topology_patches") == 0
    assert len(rm.store.data("positions")) == 3 * len(mesh.all_vertex_ids())
