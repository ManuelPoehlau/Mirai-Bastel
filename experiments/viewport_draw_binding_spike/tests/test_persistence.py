"""§7 "Persistence": camera, selection and position updates keep the same
VertexList object, the same resource IDs, and `gpu_resource_creations`
unchanged (V02 architecture invariant §7)."""

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
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport.overlay import SelectionOverlay  # noqa: E402
from viewport.render_mesh import RenderMesh  # noqa: E402

import pytest  # noqa: E402

from spike_gl_store import SpikeGLStore  # noqa: E402


def _rm(gl_window):
    mesh = create_cube(size=2.0)
    selection = Selection()
    overlay = SelectionOverlay(selection)
    rm = RenderMesh(mesh, overlay=overlay, store_type=SpikeGLStore)
    return mesh, selection, rm


def test_camera_orbit_does_not_touch_vertex_list_or_ids(gl_window):
    mesh, selection, rm = _rm(gl_window)
    camera = OrbitCamera(distance=6.0)
    rm.bind_camera(camera)
    rm.mark_camera_dirty(aspect=1.0)
    rm.sync()  # establishes camera_uniforms once, before the baseline snapshot

    vlist_before = rm.store.vertex_list()
    ids_before = rm.resource_ids()
    creations_before = rm.benchmark_counters["gpu_resource_creations"]

    for _ in range(10):
        camera.orbit(0.05, 0.02)
        rm.mark_camera_dirty(aspect=1.0)
        rm.sync()

    assert rm.store.vertex_list() is vlist_before
    assert rm.resource_ids() == ids_before
    assert rm.benchmark_counters["gpu_resource_creations"] == creations_before
    assert rm.benchmark_counters.get("geometry_uploads", 0) == 0


def test_selection_change_does_not_touch_base_mesh_ids(gl_window):
    mesh, selection, rm = _rm(gl_window)
    ids_before = rm.resource_ids()
    positions_before = list(rm.store.vertex_list().position[:])

    v0 = next(iter(mesh.all_vertex_ids()))
    selection.add({v0})
    rm.mark_selection_dirty()
    rm.sync()

    ids_after = rm.resource_ids()
    assert ids_after["positions"] == ids_before["positions"]
    assert ids_after["normals"] == ids_before["normals"]
    assert list(rm.store.vertex_list().position[:]) == positions_before
    assert rm.benchmark_counters.get("geometry_uploads", 0) == 0


def test_single_vertex_move_is_same_object_and_id(gl_window):
    mesh, selection, rm = _rm(gl_window)
    vlist_before = rm.store.vertex_list()
    ids_before = rm.resource_ids()

    v0 = next(iter(mesh.all_vertex_ids()))
    mesh.set_vertex_position(v0, (0.9, 0.1, -0.4))
    rm.mark_vertices_dirty({v0})
    rm.sync()

    assert rm.store.vertex_list() is vlist_before
    assert rm.resource_ids() == ids_before
    idx = rm.vertex_index_of(v0)
    got = tuple(vlist_before.position[idx * 3: idx * 3 + 3])
    assert got == pytest.approx((0.9, 0.1, -0.4), abs=1e-6)
