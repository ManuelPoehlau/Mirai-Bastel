"""Integrationsgrenze Core → Production-Render (Adapter, WP-IL-01):

    src.core.Mesh -> src.viewport.Viewport/RenderMesh (+ Index-Map)

Geprüft: Vertexanzahl, Faces, Triangulierung (Quad → 2 Tris, Production-Fan),
exakte Positionsübertragung und die Index-Map-Eindeutigkeit.
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parents[1]
_REPO = _LAB.parent.parent
for _p in (str(_LAB), str(_REPO), str(_REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from adapters.core_to_render import (  # noqa: E402
    CoreRenderBinding,
    CoreVertexIndexMap,
    render_triangle_count,
)
from adapters.obj_to_core import (  # noqa: E402
    DEFAULT_HEAD_ASSET,
    build_core_scene_from_obj,
)
from scene.scene_objects import build_cube_scene  # noqa: E402

from loaders.obj_loader import load_obj  # noqa: E402
from viewport.resource_store import TraceStore  # noqa: E402  (Production, Gate 5)


def test_cube_render_representation():
    core_mesh = build_cube_scene().mesh
    binding = CoreRenderBinding(core_mesh, store_type=TraceStore)
    # 8 Vertices, 6 Quads -> 12 Render-Tris
    assert binding.vertex_count == 8
    assert binding.triangle_count == 12
    assert render_triangle_count(core_mesh) == 12
    assert len(binding.index_map) == 8


def test_cube_positions_transferred_one_to_one():
    core_mesh = build_cube_scene().mesh
    binding = CoreRenderBinding(core_mesh, store_type=TraceStore)
    for i, vid in enumerate(core_mesh.all_vertex_ids()):
        assert binding.positions[i] == core_mesh.vertex_position(vid)
        assert binding.index_map.index(vid) == i
        assert binding.index_map.vertex(i) == vid


def test_head_triangles_consistent_with_polygon_formula():
    core_mesh = build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh
    binding = CoreRenderBinding(core_mesh, store_type=TraceStore)
    # Anzahl Render-Tris == Summe(n-2) über alle Polygone.
    assert binding.triangle_count == render_triangle_count(core_mesh)
    assert binding.vertex_count == len(core_mesh.all_vertex_ids())
    for tri in binding.triangle_indices:
        assert 0 <= tri[0] < binding.vertex_count
        assert 0 <= tri[1] < binding.vertex_count
        assert 0 <= tri[2] < binding.vertex_count


def test_head_index_map_is_bijective():
    core_mesh = build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh
    binding = CoreRenderBinding(core_mesh, store_type=TraceStore)
    n = len(core_mesh.all_vertex_ids())
    assert sorted(binding.index_map.index(v) for v in core_mesh.all_vertex_ids()) == list(range(n))
    for i in range(n):
        vid = binding.index_map.vertex(i)
        assert binding.index_map.index(vid) == i


def test_head_face_counts_render_side():
    data = load_obj(DEFAULT_HEAD_ASSET)
    core_mesh = build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh
    tris = render_triangle_count(core_mesh)
    # Abschätzung: nur Quads wäre 2*face_count; das Asset ist fast nur Quads.
    assert tris >= 2 * data.face_count - data.face_count  # mind. flach
    assert tris <= 4 * data.face_count


def test_core_vertex_index_map_standalone():
    """Die Standalone-Index-Map bleibt in all_vertex_ids-Reihenfolge."""
    core_mesh = build_cube_scene().mesh
    index_map = CoreVertexIndexMap(core_mesh.all_vertex_ids())
    assert len(index_map) == 8
    assert index_map.vertex_ids == core_mesh.all_vertex_ids()
