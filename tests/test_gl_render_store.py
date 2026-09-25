"""GLRenderStore (AD-018 §5, Option B): real-GL draw path adapted from the
proven `experiments/viewport_draw_binding_spike/` mechanics (H1 CONFIRMED),
now driven by the explicit layout declaration/rebuild bracket instead of
inferred call order.

Needs a real GL context (Xvfb or a real display) - run via
`xvfb-run -a python3 -m pytest tests/test_gl_render_store.py`. Skips
cleanly (not fails) when no context is available, mirroring the spike's
own `conftest.py` rationale (live-GL behavior is not meaningfully fakeable
headless).
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Selection  # noqa: E402
from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import create_cube  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport.derived import triangulate_face  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.overlay import SelectionOverlay  # noqa: E402
from viewport.render_mesh import RenderMesh  # noqa: E402
from viewport.resource_store import TraceStore  # noqa: E402


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=128, height=128, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _build(gl_window, store_type=GLRenderStore):
    mesh = create_cube(size=2.0)
    selection = Selection()
    overlay = SelectionOverlay(selection)
    rm = RenderMesh(mesh, overlay=overlay, store_type=store_type)
    return mesh, selection, rm


# -- Persistence (V02 invariants, §7 of the handoff) -------------------------


def test_camera_orbit_does_not_touch_vertex_list_or_ids(gl_window):
    mesh, selection, rm = _build(gl_window)
    camera = OrbitCamera(distance=6.0)
    rm.bind_camera(camera)
    rm.mark_camera_dirty(aspect=1.0)
    rm.sync()

    vlist_before = rm.store.vertex_list()
    ids_before = rm.resource_ids()
    creations_before = rm.benchmark_counters["gpu_resource_creations"]
    uploads_before = rm.benchmark_counters.get("geometry_uploads", 0)

    for _ in range(10):
        camera.orbit(0.05, 0.02)
        rm.mark_camera_dirty(aspect=1.0)
        rm.sync()

    assert rm.store.vertex_list() is vlist_before
    assert rm.resource_ids() == ids_before
    assert rm.benchmark_counters["gpu_resource_creations"] == creations_before
    assert rm.benchmark_counters.get("geometry_uploads", 0) == uploads_before


def test_selection_change_does_not_touch_base_mesh_ids(gl_window):
    mesh, selection, rm = _build(gl_window)
    ids_before = rm.resource_ids()
    positions_before = list(rm.store.vertex_list().position[:])
    uploads_before = rm.benchmark_counters.get("geometry_uploads", 0)

    v0 = next(iter(mesh.all_vertex_ids()))
    selection.add({v0})
    rm.mark_selection_dirty()
    rm.sync()

    ids_after = rm.resource_ids()
    assert ids_after["positions"] == ids_before["positions"]
    assert ids_after["normals"] == ids_before["normals"]
    assert list(rm.store.vertex_list().position[:]) == positions_before
    assert rm.benchmark_counters.get("geometry_uploads", 0) == uploads_before


def test_single_vertex_move_is_same_object_and_id(gl_window):
    mesh, selection, rm = _build(gl_window)
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


# -- Topology (§7) -------------------------------------------------------


def test_edge_split_gives_new_ids_and_correct_indices(gl_window):
    mesh, selection, rm = _build(gl_window)

    ids_before = rm.resource_ids()
    vlist_before = rm.store.vertex_list()
    n_verts_before = len(list(mesh.all_vertex_ids()))

    edge_id = next(iter(mesh.all_edge_ids()))
    new_vertex, _e1, _e2 = mesh.split_edge(edge_id)
    rm.mark_topology_dirty()
    rm.sync()

    ids_after = rm.resource_ids()
    for name in ("positions", "normals", "indices", "highlight_flags"):
        assert ids_after[name] != ids_before[name], f"{name} resource id did not change"

    vlist_after = rm.store.vertex_list()
    assert vlist_after is not vlist_before

    n_verts_after = len(list(mesh.all_vertex_ids()))
    assert n_verts_after == n_verts_before + 1

    expected_triangle_count = sum(
        len(triangulate_face(mesh.face_vertices(fid))) for fid in mesh.all_face_ids()
    )
    assert len(vlist_after.indices[:]) == expected_triangle_count * 3

    new_idx = rm.vertex_index_of(new_vertex)
    expected_pos = tuple(mesh.vertex_position(new_vertex))
    got_pos = tuple(vlist_after.position[new_idx * 3: new_idx * 3 + 3])
    assert got_pos == expected_pos

    for i in vlist_after.indices[:]:
        assert 0 <= i < n_verts_after


# -- Content equality vs. TraceStore --------------------------------------


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
    trace_mesh, trace_selection, trace_rm = _build(gl_window, TraceStore)
    gl_mesh, gl_selection, gl_rm = _build(gl_window, GLRenderStore)

    if scenario in ("geometry", "selection", "topology"):
        v0_trace = next(iter(trace_mesh.all_vertex_ids()))
        v0_gl = next(iter(gl_mesh.all_vertex_ids()))
        assert v0_trace == v0_gl  # deterministic vertex-id assignment
        trace_mesh.set_vertex_position(v0_trace, (0.7, -0.3, 1.1))
        gl_mesh.set_vertex_position(v0_gl, (0.7, -0.3, 1.1))
        trace_rm.mark_vertices_dirty({v0_trace})
        gl_rm.mark_vertices_dirty({v0_gl})
        trace_rm.sync()
        gl_rm.sync()

    if scenario in ("selection", "topology"):
        v0_trace = next(iter(trace_mesh.all_vertex_ids()))
        v0_gl = next(iter(gl_mesh.all_vertex_ids()))
        trace_selection.add({v0_trace})
        gl_selection.add({v0_gl})
        trace_rm.mark_selection_dirty()
        gl_rm.mark_selection_dirty()
        trace_rm.sync()
        gl_rm.sync()

    if scenario == "topology":
        trace_edge = next(iter(trace_mesh.all_edge_ids()))
        gl_edge = next(iter(gl_mesh.all_edge_ids()))
        trace_mesh.split_edge(trace_edge)
        gl_mesh.split_edge(gl_edge)
        trace_rm.mark_topology_dirty()
        gl_rm.mark_topology_dirty()
        trace_rm.sync()
        gl_rm.sync()

    trace_content = {
        "positions": trace_rm.store.data("positions"),
        "normals": trace_rm.store.data("normals"),
        "highlight_flags": trace_rm.store.data("highlight_flags"),
        "indices": trace_rm.store.data("indices"),
    }
    gl_content = _vlist_content(gl_rm)

    for name in trace_content:
        assert gl_content[name] == pytest.approx(trace_content[name], abs=1e-5), (
            f"{scenario}: resource {name!r} diverges"
        )


# -- Pixel smoke test (real draw call, RenderMesh.render(camera)) -----------
#
# Uses the cube fixture (like the spike's own pixel-smoke test) - large,
# few triangles, so a single-vertex move reliably changes several pixels at
# 128x128. The head mesh's real-GL draw is separately covered by the
# practical viewport test (AD-018 handoff §4/§8), not this fast unit test:
# a single interior vertex on a 326V smooth mesh can move without changing
# any rasterized pixel at this resolution, which would make that assertion
# flaky rather than meaningful.


def _read_pixels_rgb(window):
    from pyglet import gl

    width, height = window.width, window.height
    buf = (gl.GLubyte * (width * height * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, width, height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    return bytes(buf)


def _render_via_render_mesh(gl_window, rm, camera):
    from pyglet import gl

    gl_window.switch_to()
    gl.glClearColor(0.05, 0.05, 0.08, 1.0)
    gl_window.clear()
    rm.render(camera)
    gl.glFinish()
    return _read_pixels_rgb(gl_window)


def test_cube_renders_and_vertex_move_changes_pixels(gl_window):
    mesh, selection, rm = _build(gl_window)

    camera = OrbitCamera()
    center, radius = mesh_center_and_radius(mesh)
    camera.frame_on_bounds(center, radius)
    rm.bind_camera(camera)
    rm.mark_camera_dirty(aspect=gl_window.width / gl_window.height)
    rm.sync()

    pixels_initial = _render_via_render_mesh(gl_window, rm, camera)
    background = bytes([12, 12, 20]) * (len(pixels_initial) // 3)
    assert pixels_initial != background, "framebuffer is empty - no silhouette rendered"

    v0 = next(iter(mesh.all_vertex_ids()))
    original_pos = mesh.vertex_position(v0)
    mesh.set_vertex_position(v0, tuple(c * 3.0 for c in (1.0, 1.0, 1.0)))
    rm.mark_vertices_dirty({v0})
    rm.sync()

    pixels_after_move = _render_via_render_mesh(gl_window, rm, camera)
    assert pixels_after_move != pixels_initial, "vertex move produced no visible pixel change"

    mesh.set_vertex_position(v0, original_pos)


def test_head_mesh_renders_visibly_through_new_store(gl_window):
    import os
    import sys

    mesh_path = os.path.join(
        os.path.dirname(__file__), "..", "examples", "meshes", "head_basemesh.obj"
    )
    if not os.path.exists(mesh_path):
        pytest.skip(f"reference mesh not found: {mesh_path}")

    examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
    if examples_dir not in sys.path:
        sys.path.insert(0, examples_dir)
    from mirai.scene_factory import build_core_scene_from_obj

    mesh = build_core_scene_from_obj(mesh_path).mesh
    selection = Selection()
    overlay = SelectionOverlay(selection)
    rm = RenderMesh(mesh, overlay=overlay, store_type=GLRenderStore)

    camera = OrbitCamera()
    center, radius = mesh_center_and_radius(mesh)
    camera.frame_on_bounds(center, radius)
    rm.bind_camera(camera)
    rm.mark_camera_dirty(aspect=gl_window.width / gl_window.height)
    rm.sync()

    pixels = _render_via_render_mesh(gl_window, rm, camera)
    background = bytes([12, 12, 20]) * (len(pixels) // 3)
    assert pixels != background, "framebuffer is empty - no head-mesh silhouette rendered"


if __name__ == "__main__":
    unittest.main()
