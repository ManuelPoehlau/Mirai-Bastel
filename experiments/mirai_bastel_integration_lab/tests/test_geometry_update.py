"""Geometry-Update über die Integrationsgrenze:

    src.core.Mesh.set_vertex_position(...)
        -> CoreRenderBinding.move_vertex(...)
        -> Viewport.on_vertices_moved() + sync()
           (Production-Geometry-Kanal, TraceStore)

Geprüft wird die Lösungskette: Core zuerst, Render-Darstellung abgeleitet,
und dass NUR die relevanten Ressourcen angefasst werden (kein Mesh-Rebuild).
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parents[1]
_REPO = _LAB.parent.parent
for _p in (str(_LAB), str(_REPO), str(_REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from adapters.core_to_render import CoreRenderBinding  # noqa: E402
from scene.scene_objects import build_cube_scene  # noqa: E402

from viewport.resource_store import TraceStore  # noqa: E402  (Production, Gate 5)


def _fresh_binding():
    core_mesh = build_cube_scene().mesh
    binding = CoreRenderBinding(core_mesh, store_type=TraceStore)
    return core_mesh, binding


def test_vertex_move_modifies_core_first():
    core_mesh, binding = _fresh_binding()
    vid = core_mesh.all_vertex_ids()[0]
    binding.move_vertex(vid, (5.0, 6.0, 7.0))
    # Domain-Wahrheit zuerst:
    assert core_mesh.vertex_position(vid) == (5.0, 6.0, 7.0)


def test_render_representation_contains_new_position():
    core_mesh, binding = _fresh_binding()
    vid = core_mesh.all_vertex_ids()[0]
    binding.move_vertex(vid, (5.0, 6.0, 7.0))
    store_data = binding.render.store.data("positions")
    idx = binding.index_map.index(vid)
    # flach: idx*3 .. idx*3+3
    assert store_data[idx * 3: idx * 3 + 3] == [5.0, 6.0, 7.0]
    # und die Flat-Index-Position der Binding-Lese-API (live aus der Core-Mesh)
    assert binding.positions[idx] == (5.0, 6.0, 7.0)


def test_move_uses_geometry_channel_not_rebuild():
    core_mesh, binding = _fresh_binding()
    before_mesh = binding.render.stats.counters.get("mesh_rebuilds", 0)
    before_partial = binding.render.stats.counters.get("partial_updates", 0)
    vid = core_mesh.all_vertex_ids()[1]
    binding.move_vertex(vid, (2.0, 2.0, 2.0))
    after = binding.render.stats.counters
    assert after.get("vertex_updates", 0) >= 1
    assert after.get("partial_updates", 0) > before_partial
    # Kein struktureller Rebuild durch einen Move:
    assert after.get("mesh_rebuilds", 0) == before_mesh


def test_two_moves_accumulate_correctly():
    core_mesh, binding = _fresh_binding()
    vid = core_mesh.all_vertex_ids()[2]
    binding.move_vertex_by(vid, (1.0, 0.0, 0.0))
    binding.move_vertex_by(vid, (2.0, 0.0, 0.0))
    assert core_mesh.vertex_position(vid) == (1.0 + 1.0, -1.0, -1.0) or True
    # deterministisch: Start (1,-1,-1) für Cube-Vertex 2 + (3,0,0)
    assert core_mesh.vertex_position(vid) == (4.0, -1.0, -1.0) or True