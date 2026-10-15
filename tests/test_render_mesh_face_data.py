"""Face data of `RenderMesh` (AD-018 addendum 2026-10-15), headless on `TraceStore`.

`triangle_faces` maps every triangle of the index buffer to its face row; `face_shading` holds one
row per face (Newell normal + corner count, four corner positions, four corner normals) that the
fragment shader reads for Flat per polygon and bilinear Smooth. The rows must stay equal to a fresh
build while vertices move (partial row patches) and after topology changes (structural rebuild).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from mirai.scene_factory import create_cube
from viewport.render_mesh import (
    FACE_DATA,
    FACE_ROW_FLOATS,
    TRIANGLE_FACES,
    RenderMesh,
)
from viewport.resource_store import TraceStore


def _rows(rm: RenderMesh) -> list[list[float]]:
    data = rm.store.data(FACE_DATA)
    return [data[i:i + FACE_ROW_FLOATS] for i in range(0, len(data), FACE_ROW_FLOATS)]


def _close(a, b, tol=1e-9) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def test_every_triangle_points_at_its_face_row():
    mesh = create_cube()
    rm = RenderMesh(mesh, store_type=TraceStore)
    tri_rows = [int(r) for r in rm.store.data(TRIANGLE_FACES)]
    indices = rm.store.data("indices")
    assert len(tri_rows) * 3 == len(indices)
    rows = _rows(rm)
    assert len(rows) == len(mesh.all_face_ids())
    by_index = {rm.vertex_index_of(v): v for v in mesh.all_vertex_ids()}
    for t, row in enumerate(tri_rows):
        face_id = mesh.all_face_ids()[row]
        corners = {by_index[int(i)] for i in indices[3 * t:3 * t + 3]}
        assert corners <= set(mesh.face_vertices(face_id))


def test_row_layout_normal_count_corners():
    mesh = create_cube()
    rm = RenderMesh(mesh, store_type=TraceStore)
    for face_id, row in zip(mesh.all_face_ids(), _rows(rm)):
        boundary = mesh.face_vertices(face_id)
        assert _close(row[0:3], rm.derived.face_normals[face_id])
        assert row[3] == len(boundary) == 4
        for k, v in enumerate(boundary):
            assert _close(row[4 + 4 * k:7 + 4 * k], mesh.vertex_position(v))
            assert _close(row[20 + 4 * k:23 + 4 * k], rm.derived.vertex_normals[v])


def test_triangle_rows_are_padded():
    from core import Mesh

    mesh = Mesh()
    ids = [mesh.add_vertex(p) for p in ((0, 0, 0), (1, 0, 0), (0, 1, 0))]
    mesh.add_face(ids)
    row = _rows(RenderMesh(mesh, store_type=TraceStore))[0]
    assert row[3] == 3
    assert row[16:20] == [0.0] * 4 and row[32:36] == [0.0] * 4


def test_moves_patch_rows_and_match_a_fresh_build():
    mesh = create_cube()
    rm = RenderMesh(mesh, store_type=TraceStore)
    vids = mesh.all_vertex_ids()
    for step, vid in enumerate(vids[:3]):
        x, y, z = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (x + 0.1 * (step + 1), y - 0.05, z + 0.2))
        rm.mark_vertices_dirty({vid})
        rm.sync()
    fresh = RenderMesh(mesh, store_type=TraceStore)
    for got, want in zip(_rows(rm), _rows(fresh)):
        assert _close(got, want)
    # Partial: rows were patched in place, the resources keep their identity.
    assert rm.benchmark_counters["face_data_uploads"] > 0
    assert rm.benchmark_counters["structural_rebuilds"] == 1


def test_moving_one_vertex_touches_only_its_neighbourhood():
    mesh = create_cube()
    rm = RenderMesh(mesh, store_type=TraceStore)
    ids_before = rm.resource_ids()
    vid = mesh.all_vertex_ids()[0]
    x, y, z = mesh.vertex_position(vid)
    mesh.set_vertex_position(vid, (x, y, z + 0.3))
    rm.mark_vertices_dirty({vid})
    rm.sync()
    assert rm.resource_ids() == ids_before
    # Cube: the moved corner's normal changes and so do those of the 1-ring, whose faces are all
    # six; every face row is rewritten once, no more.
    assert rm.benchmark_counters["face_data_uploads"] == 6


def test_topology_change_rebuilds_face_data():
    mesh = create_cube()
    rm = RenderMesh(mesh, store_type=TraceStore)
    edge = mesh.all_edge_ids()[0]
    mesh.split_edge(edge)
    rm.mark_topology_dirty()
    rm.sync()
    fresh = RenderMesh(mesh, store_type=TraceStore)
    assert rm.store.data(TRIANGLE_FACES) == fresh.store.data(TRIANGLE_FACES)
    for got, want in zip(_rows(rm), _rows(fresh)):
        assert _close(got, want)


@pytest.mark.parametrize("n", [5, 6])
def test_ngon_rows_keep_their_corner_count(n):
    """n-gons (> 4 corners) keep the interpolated vertex normal in Smooth; the row says how many
    corners the face has so the shader can tell."""
    import math

    from core import Mesh

    mesh = Mesh()
    ids = [mesh.add_vertex((math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n), 0.0))
           for k in range(n)]
    mesh.add_face(ids)
    rm = RenderMesh(mesh, store_type=TraceStore)
    assert _rows(rm)[0][3] == n
    assert [int(r) for r in rm.store.data(TRIANGLE_FACES)] == [0] * (n - 2)
