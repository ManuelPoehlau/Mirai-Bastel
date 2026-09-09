"""Scene-Ebene: Cube und Head existieren, unabhängige Auswahl, Framing.

Fokus (Boundary): Die Lab-Szene enthält beide Objekte als eigene
`src.core.Scene`s mit eigener Selection — eine Auswahl im Cube darf den
Head nicht beeinflussen.
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
from adapters.obj_to_core import mesh_bounds  # noqa: E402
from scene.scene import LabScene  # noqa: E402
from scene.scene_objects import build_cube_scene, build_head_scene, build_lab_scene  # noqa: E402

from viewport.resource_store import TraceStore  # noqa: E402  (Production, Gate 5)


def test_lab_scene_contains_cube_and_head():
    lab = build_lab_scene()
    assert lab.names() == ["Cube", "Head Basemesh"]


def test_objects_are_selectable_independently():
    lab = build_lab_scene()
    assert lab.active.name == "Cube"
    head = lab.select_by_name("Head Basemesh")
    assert head.name == "Head Basemesh"
    assert lab.active.name == "Head Basemesh"
    lab.select(0)
    assert lab.active.name == "Cube"


def test_selections_are_independent_per_object():
    lab = build_lab_scene()
    cube, head = lab.objects
    cube.scene.selection.set({cube.mesh.all_vertex_ids()[0]})
    assert head.scene.selection.is_empty()
    bindings = [
        CoreRenderBinding(o.scene.mesh, store_type=TraceStore) for o in lab.objects
    ]
    bindings[0].select_vertex(cube.mesh.all_vertex_ids()[0])
    assert len(bindings[1].selection.vertices) == 0


def test_head_bounds_are_frameable():
    head = build_head_scene()
    (min_x, min_y, min_z), (max_x, max_y, max_z) = mesh_bounds(head.mesh)
    extent = (max_x - min_x, max_y - min_y, max_z - min_z)
    # Nicht entartet und nicht exotisch groß — vernünftig rahmbar.
    assert all(0.1 < e < 1e3 for e in extent)


def test_both_objects_render_build_without_gpu():
    lab = build_lab_scene()
    for obj in lab.objects:
        binding = CoreRenderBinding(obj.scene.mesh, store_type=TraceStore)
        assert binding.vertex_count > 0
        assert binding.triangle_count > 0