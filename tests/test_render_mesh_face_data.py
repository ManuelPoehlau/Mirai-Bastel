"""Face data of `RenderMesh` (AD-018 addenda 2026-10-15 and 2026-11-11, O2), headless on `TraceStore`.

`triangle_faces` maps every triangle of the index buffer to its face row. Per face row, `face_normals` holds one vec4
(Newell normal, corner count) and `face_corners` two vec4 (the vertex slots of the first four corners; the region
tint). The fragment shader reads the corners' positions and normals from the vertex group's own buffers through those
slots (Flat per polygon, bilinear Smooth). A move rewrites only the `face_normals` rows of the faces around the moved
vertices; the rows must stay equal to a fresh build while vertices move and after topology changes.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from mirai.scene_factory import create_cube
from viewport.render_mesh import (
    FACE_CORNER_FLOATS,
    FACE_CORNERS,
    FACE_NORMAL_FLOATS,
    FACE_NORMALS,
    TRIANGLE_FACES,
    RenderMesh,
)
from viewport.resource_store import TraceStore


def _rows(rm: RenderMesh, name: str = FACE_NORMALS) -> list[list[float]]:
    width = FACE_NORMAL_FLOATS if name == FACE_NORMALS else FACE_CORNER_FLOATS
    data = rm.store.data(name)
    return [data[i:i + width] for i in range(0, len(data), width)]


def _corner_vertices(rm: RenderMesh, face_id) -> list:
    """The vertices a face's `face_corners` row points at (through the slot layout)."""
    row = _rows(rm, FACE_CORNERS)[rm._face_row[face_id]]
    count = int(_rows(rm)[rm._face_row[face_id]][3])
    return [rm._slot_vertex[int(slot)] for slot in row[:min(count, 4)]]


def _close(a, b, tol=1e-9) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def test_every_triangle_points_at_its_face_row():
    mesh = create_cube()
    rm = RenderMesh(mesh, store_type=TraceStore)
    tri_rows = [int(r) for r in rm.store.data(TRIANGLE_FACES)]
    indices = rm.store.data("indices")
    assert len(tri_rows) * 3 == len(indices)
    assert len(_rows(rm)) == len(_rows(rm, FACE_CORNERS)) == len(mesh.all_face_ids())
    by_index = {rm.vertex_index_of(v): v for v in mesh.all_vertex_ids()}
    for t, row in enumerate(tri_rows):
        face_id = mesh.all_face_ids()[row]
        corners = {by_index[int(i)] for i in indices[3 * t:3 * t + 3]}
        assert corners <= set(mesh.face_vertices(face_id))


def test_row_layout_normal_count_and_corner_slots():
    mesh = create_cube()
    rm = RenderMesh(mesh, store_type=TraceStore)
    corners = _rows(rm, FACE_CORNERS)
    for face_id, row in zip(mesh.all_face_ids(), _rows(rm)):
        boundary = mesh.face_vertices(face_id)
        assert _close(row[0:3], rm.derived.face_normals[face_id])
        assert row[3] == len(boundary) == 4
        corner_row = corners[rm._face_row[face_id]]
        assert corner_row[:4] == [float(rm.vertex_index_of(v)) for v in boundary]
        assert corner_row[4:] == [0.0] * 4  # no region tint
        assert _corner_vertices(rm, face_id) == list(boundary)


def test_the_slots_address_the_vertex_buffers_the_shader_reads():
    """What the shader reads for a corner (positions / normals at the corner's slot) is that vertex's position and
    vertex normal - the values the pre-O2 rows held as copies."""
    mesh = create_cube()
    rm = RenderMesh(mesh, store_type=TraceStore)
    positions, normals = rm.store.data("positions"), rm.store.data("normals")
    for face_id in mesh.all_face_ids():
        for k, slot in enumerate(_rows(rm, FACE_CORNERS)[rm._face_row[face_id]][:4]):
            v = mesh.face_vertices(face_id)[k]
            s = int(slot)
            assert _close(positions[3 * s:3 * s + 3], mesh.vertex_position(v))
            assert _close(normals[3 * s:3 * s + 3], rm.derived.vertex_normals[v])


def test_triangle_rows_are_padded():
    from core import Mesh

    mesh = Mesh()
    ids = [mesh.add_vertex(p) for p in ((0, 0, 0), (1, 0, 0), (0, 1, 0))]
    mesh.add_face(ids)
    rm = RenderMesh(mesh, store_type=TraceStore)
    assert _rows(rm)[0][3] == 3
    assert _rows(rm, FACE_CORNERS)[0][3] == 0.0
    assert _corner_vertices(rm, mesh.all_face_ids()[0]) == ids


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
    for name in (FACE_NORMALS, FACE_CORNERS):
        for got, want in zip(_rows(rm, name), _rows(fresh, name)):
            assert _close(got, want, 1e-6)  # a patch goes through the float32 mirror, like positions
    # Partial: rows were patched in place, the resources keep their identity.
    assert rm.benchmark_counters["face_data_uploads"] > 0
    assert rm.benchmark_counters["structural_rebuilds"] == 1


def test_moving_one_vertex_rewrites_only_the_normals_of_its_faces():
    """O2: a move rewrites the `face_normals` rows of the faces around the moved vertex - their Newell normal changed -
    and nothing of `face_corners`; the 1-ring's new vertex normals reach the shader through the vertex buffer. (Before
    O2 every face around a vertex with a new normal got its 36-float row rewritten: all six faces of the cube.)"""
    mesh = create_cube()
    rm = RenderMesh(mesh, store_type=TraceStore)
    ids_before = rm.resource_ids()
    corner_updates = rm.store.resource(FACE_CORNERS).updates
    vid = mesh.all_vertex_ids()[0]
    x, y, z = mesh.vertex_position(vid)
    mesh.set_vertex_position(vid, (x, y, z + 0.3))
    rm.mark_vertices_dirty({vid})
    rm.sync()
    assert rm.resource_ids() == ids_before
    assert rm.benchmark_counters["face_data_uploads"] == len(rm.derived.vertex_to_faces[vid]) == 3
    assert rm.store.resource(FACE_CORNERS).updates == corner_updates


def test_a_move_hands_four_floats_per_face_to_the_store():
    """Bytes of a move: positions of the moved vertices, normals of the 1-ring, one vec4 per face around the moved
    vertices (in merged ranges) - no corner copies."""
    from tests.soft_selection_fixtures import HEAD_OBJ
    from loaders.obj_loader import load_obj
    from mirai.scene_factory import mesh_from_positions_and_faces

    data = load_obj(HEAD_OBJ)
    mesh = mesh_from_positions_and_faces(data.vertices, data.faces)
    rm = RenderMesh(mesh, store_type=TraceStore)
    moved = set(mesh.all_vertex_ids()[:40])
    for v in moved:
        x, y, z = mesh.vertex_position(v)
        mesh.set_vertex_position(v, (x, y + 0.01, z))
    before = {name: rm.store.resource(name).bytes_uploaded for name in (FACE_NORMALS, FACE_CORNERS, "positions")}
    rm.mark_vertices_dirty(moved)
    rm.sync()
    sent = {name: rm.store.resource(name).bytes_uploaded - before[name] for name in before}
    faces = set().union(*(rm.derived.vertex_to_faces[v] for v in moved))
    assert sent[FACE_CORNERS] == 0
    assert 16 * len(faces) <= sent[FACE_NORMALS] < 16 * len(mesh.all_face_ids())
    assert sent["positions"] >= 12 * len(moved)


def test_topology_change_rebuilds_face_data():
    mesh = create_cube()
    rm = RenderMesh(mesh, store_type=TraceStore)
    edge = mesh.all_edge_ids()[0]
    mesh.split_edge(edge)
    rm.mark_topology_dirty()
    rm.sync()
    fresh = RenderMesh(mesh, store_type=TraceStore)
    assert rm.store.data(TRIANGLE_FACES) == fresh.store.data(TRIANGLE_FACES)
    for name in (FACE_NORMALS, FACE_CORNERS):
        for got, want in zip(_rows(rm, name), _rows(fresh, name)):
            assert _close(got, want, 1e-6)


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
    assert _corner_vertices(rm, mesh.all_face_ids()[0]) == ids[:4]
    assert [int(r) for r in rm.store.data(TRIANGLE_FACES)] == [0] * (n - 2)
