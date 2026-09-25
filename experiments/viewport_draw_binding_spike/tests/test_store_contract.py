"""§7 "Store contract": allocate/update/destroy counters and resource IDs
behave like TraceStore for the same RenderMesh call sequence."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
for _p in (str(_ROOT / "src"), str(_ROOT / "examples"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import Selection  # noqa: E402
from mirai.scene_factory import create_cube  # noqa: E402
from viewport.overlay import SelectionOverlay  # noqa: E402
from viewport.render_mesh import RenderMesh  # noqa: E402
from viewport.resource_store import TraceStore  # noqa: E402

from spike_gl_store import SpikeGLStore  # noqa: E402

COUNTER_NAMES = (
    "gpu_resource_creations",
    "gpu_resource_destroys",
    "mesh_rebuilds",
    "structural_rebuilds",
    "topology_updates",
    "vertex_updates",
    "normal_recomputations",
    "bounds_recalculations",
    "selection_updates",
    "camera_updates",
)


def _drive(store_type, gl_window):
    mesh = create_cube(size=2.0)
    selection = Selection()
    overlay = SelectionOverlay(selection)
    rm = RenderMesh(mesh, overlay=overlay, store_type=store_type)

    all_vertices = list(mesh.all_vertex_ids())
    v0 = all_vertices[0]

    # Geometry: move one vertex.
    mesh.set_vertex_position(v0, (1.5, 1.5, 1.5))
    rm.mark_vertices_dirty({v0})
    rm.sync()

    # Selection.
    selection.add({v0})
    rm.mark_selection_dirty()
    rm.sync()

    # Topology: split one edge.
    edge_id = next(iter(mesh.all_edge_ids()))
    mesh.split_edge(edge_id)
    rm.mark_topology_dirty()
    rm.sync()

    return rm


def test_counters_match_tracestore(gl_window):
    trace_rm = _drive(TraceStore, gl_window)
    spike_rm = _drive(SpikeGLStore, gl_window)

    trace_counters = trace_rm.benchmark_counters
    spike_counters = spike_rm.benchmark_counters

    for name in COUNTER_NAMES:
        assert spike_counters.get(name, 0) == trace_counters.get(name, 0), (
            f"counter {name!r}: spike={spike_counters.get(name, 0)} "
            f"trace={trace_counters.get(name, 0)}"
        )


def test_resource_ids_present_for_all_named_resources(gl_window):
    rm = _drive(SpikeGLStore, gl_window)
    ids = rm.resource_ids()
    for name in ("positions", "normals", "indices", "highlight_flags"):
        assert name in ids
        assert isinstance(ids[name], int)


def test_vertex_list_exists_after_build(gl_window):
    mesh = create_cube(size=2.0)
    selection = Selection()
    overlay = SelectionOverlay(selection)
    rm = RenderMesh(mesh, overlay=overlay, store_type=SpikeGLStore)
    assert rm.store.vertex_list() is not None
