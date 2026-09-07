"""Integrationsgrenze Core → Render (Adapter):

    src.core.Mesh -> V0.2-Render-Mesh (Triangulierung + Index-Map)

Geprüft: Vertexanzahl, Faces, Triangulierung (Quad → 2 Tris), exakte
Positionsübertragung und die Index-Map-Eindeutigkeit.
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parents[1]
for _p in (str(_LAB), str(_LAB.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from adapters.core_to_render import (  # noqa: E402
    build_render_mesh,
    render_triangle_count,
)
from adapters.obj_to_core import (  # noqa: E402
    DEFAULT_HEAD_ASSET,
    build_core_scene_from_obj,
)
from scene.scene_objects import build_cube_scene  # noqa: E402

from loaders.obj_loader import load_obj  # noqa: E402


def test_cube_render_representation():
    core_mesh = build_cube_scene().mesh
    vmesh, index_map = build_render_mesh(core_mesh)
    # 8 Vertices, 6 Quads -> 12 Render-Tris
    assert len(vmesh.positions) == 8
    assert len(vmesh.triangles) == 12
    assert render_triangle_count(core_mesh) == 12
    assert len(index_map) == 8


def test_cube_positions_transferred_one_to_one():
    core_mesh = build_cube_scene().mesh
    vmesh, index_map = build_render_mesh(core_mesh)
    for i, vid in enumerate(core_mesh.all_vertex_ids()):
        assert vmesh.positions[i] == core_mesh.vertex_position(vid)
        assert index_map.index(vid) == i
        assert index_map.vertex(i) == vid


def test_head_triangles_consistent_with_polygon_formula():
    core_mesh = build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh
    vmesh, _ = build_render_mesh(core_mesh)
    # Anzahl Render-Tris == Summe(n-2) über alle Polygone.
    assert len(vmesh.triangles) == render_triangle_count(core_mesh)
    assert len(vmesh.positions) == len(core_mesh.all_vertex_ids())
    for tri in vmesh.triangles:
        assert 0 <= tri[0] < len(vmesh.positions)
        assert 0 <= tri[1] < len(vmesh.positions)
        assert 0 <= tri[2] < len(vmesh.positions)


def test_head_index_map_is_bijective():
    core_mesh = build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh
    _, index_map = build_render_mesh(core_mesh)
    n = len(core_mesh.all_vertex_ids())
    assert sorted(index_map.index(v) for v in core_mesh.all_vertex_ids()) == list(range(n))
    for i in range(n):
        vid = index_map.vertex(i)
        assert index_map.index(vid) == i


def test_head_face_counts_render_side():
    data = load_obj(DEFAULT_HEAD_ASSET)
    core_mesh = build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh
    tris = render_triangle_count(core_mesh)
    # Abschätzung: nur Quads wäre 2*face_count; das Asset ist fast nur Quads.
    assert tris >= 2 * data.face_count - data.face_count  # mind. flach
    assert tris <= 4 * data.face_count