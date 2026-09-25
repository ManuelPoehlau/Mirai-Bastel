"""§7 "Content equality": GL buffer contents (read back) == TraceStore
contents for the same RenderMesh operations, run on two independent but
identically-constructed meshes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

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


def _build(store_type):
    mesh = create_cube(size=2.0)
    selection = Selection()
    overlay = SelectionOverlay(selection)
    rm = RenderMesh(mesh, overlay=overlay, store_type=store_type)
    return mesh, selection, rm


def _vlist_content(rm):
    vlist = rm.store.vertex_list()
    n = len(rm.store._cpu["positions"]) // 3  # noqa: SLF001 - test-internal readback
    return {
        "positions": list(vlist.position[: n * 3]),
        "normals": list(vlist.normal[: n * 3]),
        "highlight_flags": list(vlist.highlight_flag[:n]),
        "indices": [float(i) for i in vlist.indices[:]],
    }


@pytest.mark.parametrize("scenario", ["initial", "geometry", "selection", "topology"])
def test_content_matches_tracestore(gl_window, scenario):
    trace_mesh, trace_selection, trace_rm = _build(TraceStore)
    spike_mesh, spike_selection, spike_rm = _build(SpikeGLStore)

    if scenario in ("geometry", "selection", "topology"):
        v0_trace = next(iter(trace_mesh.all_vertex_ids()))
        v0_spike = next(iter(spike_mesh.all_vertex_ids()))
        assert v0_trace == v0_spike  # deterministic vertex-id assignment
        trace_mesh.set_vertex_position(v0_trace, (0.7, -0.3, 1.1))
        spike_mesh.set_vertex_position(v0_spike, (0.7, -0.3, 1.1))
        trace_rm.mark_vertices_dirty({v0_trace})
        spike_rm.mark_vertices_dirty({v0_spike})
        trace_rm.sync()
        spike_rm.sync()

    if scenario in ("selection", "topology"):
        v0_trace = next(iter(trace_mesh.all_vertex_ids()))
        v0_spike = next(iter(spike_mesh.all_vertex_ids()))
        trace_selection.add({v0_trace})
        spike_selection.add({v0_spike})
        trace_rm.mark_selection_dirty()
        spike_rm.mark_selection_dirty()
        trace_rm.sync()
        spike_rm.sync()

    if scenario == "topology":
        trace_edge = next(iter(trace_mesh.all_edge_ids()))
        spike_edge = next(iter(spike_mesh.all_edge_ids()))
        trace_mesh.split_edge(trace_edge)
        spike_mesh.split_edge(spike_edge)
        trace_rm.mark_topology_dirty()
        spike_rm.mark_topology_dirty()
        trace_rm.sync()
        spike_rm.sync()

    trace_content = {
        "positions": trace_rm.store.data("positions"),
        "normals": trace_rm.store.data("normals"),
        "highlight_flags": trace_rm.store.data("highlight_flags"),
        "indices": trace_rm.store.data("indices"),
    }
    spike_content = _vlist_content(spike_rm)

    for name in trace_content:
        assert spike_content[name] == pytest.approx(trace_content[name], abs=1e-5), (
            f"{scenario}: resource {name!r} diverges"
        )
