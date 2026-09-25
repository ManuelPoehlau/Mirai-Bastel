"""Throwaway evidence script for AD-018 §5 Implementation (Option B).

NOT a Production entry point (Q6 of the spike/handoff stays open - see
AD-018 §5 "Deliberately not decided here"). Loads the real head mesh
(`examples/meshes/head_basemesh.obj`), binds the Production `OrbitCamera`,
and draws it end to end through the new `viewport.gl_render_store.GLRenderStore`
via `RenderMesh.render(camera)` - the same pattern as the draw-binding
spike's `run.py`/`run_bench.py`, adapted to the declared-layout store
instead of `SpikeGLStore`.

Usage (Xvfb, this environment):
    xvfb-run -a python3 experiments/ad018_gl_render_store_verification/run.py

Prints resource IDs / VertexList identity across camera, selection,
position and topology events, and writes a PNG screenshot for visual
evidence (no on-screen display available here, see AD-018 §5 handoff §8).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT / "examples"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pyglet  # noqa: E402

from core import Selection  # noqa: E402
from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.overlay import SelectionOverlay  # noqa: E402
from viewport.render_mesh import RenderMesh  # noqa: E402

MESH_PATH = _ROOT / "examples" / "meshes" / "head_basemesh.obj"


def main() -> None:
    window = pyglet.window.Window(width=480, height=360, visible=False)

    mesh = build_core_scene_from_obj(str(MESH_PATH)).mesh
    selection = Selection()
    overlay = SelectionOverlay(selection)
    rm = RenderMesh(mesh, overlay=overlay, store_type=GLRenderStore)

    camera = OrbitCamera()
    center, radius = mesh_center_and_radius(mesh)
    camera.frame_on_bounds(center, radius)
    rm.bind_camera(camera)
    rm.mark_camera_dirty(aspect=window.width / window.height)
    rm.sync()

    n_verts = len(list(mesh.all_vertex_ids()))
    print(f"Loaded {MESH_PATH.name}: {n_verts} vertices")
    print("Initial resource_ids:", rm.resource_ids())

    def render_frame():
        window.switch_to()
        from pyglet import gl

        gl.glClearColor(0.05, 0.05, 0.08, 1.0)
        window.clear()
        rm.render(camera)
        gl.glFinish()

    # 1. Camera orbit — invariant: same VertexList, same resource IDs, no
    #    geometry_uploads.
    vlist_before = rm.store.vertex_list()
    ids_before = rm.resource_ids()
    for _ in range(20):
        camera.orbit(0.05, 0.01)
        rm.mark_camera_dirty(aspect=window.width / window.height)
        rm.sync()
    render_frame()
    print(
        "After 20x camera.orbit(): vertex_list identity unchanged =",
        rm.store.vertex_list() is vlist_before,
        "| resource_ids unchanged =",
        rm.resource_ids() == ids_before,
        "| geometry_uploads =",
        rm.benchmark_counters.get("geometry_uploads", 0),
    )

    # 2. Selection — invariant: base mesh untouched.
    v0 = next(iter(mesh.all_vertex_ids()))
    selection.add({v0})
    rm.mark_selection_dirty()
    rm.sync()
    render_frame()
    print(
        "After selection change: positions/normals ids unchanged =",
        rm.resource_ids()["positions"] == ids_before["positions"]
        and rm.resource_ids()["normals"] == ids_before["normals"],
    )

    # 3. Position update — invariant: same object/IDs, only content patched.
    original_pos = mesh.vertex_position(v0)
    mesh.set_vertex_position(v0, tuple(c + 0.15 for c in original_pos))
    rm.mark_vertices_dirty({v0})
    rm.sync()
    render_frame()
    idx = rm.vertex_index_of(v0)
    patched = tuple(rm.store.vertex_list().position[idx * 3: idx * 3 + 3])
    print(
        "After single-vertex move: same VertexList object =",
        rm.store.vertex_list() is vlist_before,
        "| patched position =",
        patched,
    )
    mesh.set_vertex_position(v0, original_pos)
    rm.mark_vertices_dirty({v0})
    rm.sync()

    # 4. Topology — invariant: new resource IDs, new VertexList.
    edge_id = next(iter(mesh.all_edge_ids()))
    new_vertex, _e1, _e2 = mesh.split_edge(edge_id)
    rm.mark_topology_dirty()
    rm.sync()
    render_frame()
    print(
        "After edge split: vertex_list identity changed =",
        rm.store.vertex_list() is not vlist_before,
        "| new vertex count =",
        len(list(mesh.all_vertex_ids())),
    )

    # Screenshot evidence.
    out_path = Path(__file__).parent / "head_mesh_render.png"
    pyglet.image.get_buffer_manager().get_color_buffer().save(str(out_path))
    print(f"Screenshot written to {out_path}")

    window.close()


if __name__ == "__main__":
    main()
