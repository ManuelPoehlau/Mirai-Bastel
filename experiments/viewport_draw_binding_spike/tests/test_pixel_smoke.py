"""§7 "Pixel smoke test": framebuffer readback not empty; mesh silhouette
present; a vertex move changes pixels."""

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

from drawing import draw_frame, read_pixels_rgb  # noqa: E402
from spike_gl_store import SpikeGLStore  # noqa: E402


def _background_color(window):
    from pyglet import gl

    gl.glClearColor(0.05, 0.05, 0.08, 1.0)
    window.clear()
    return bytes([12, 12, 20])  # approx 0.05*255, 0.08*255 in byte space


def _render(gl_window, rm, program):
    gl_window.switch_to()
    from pyglet import gl

    gl.glClearColor(0.05, 0.05, 0.08, 1.0)
    gl_window.clear()
    draw_frame(program, rm.store)
    gl.glFinish()
    return read_pixels_rgb(gl_window)


def test_head_silhouette_visible_and_vertex_move_changes_pixels(gl_window):
    from mirai.mesh_geometry import mesh_center_and_radius
    from spike_gl_store import SpikeGLStore as _Store

    mesh = create_cube(size=2.0)
    selection = Selection()
    overlay = SelectionOverlay(selection)
    rm = RenderMesh(mesh, overlay=overlay, store_type=_Store)

    camera = OrbitCamera()
    center, radius = mesh_center_and_radius(mesh)
    camera.frame_on_bounds(center, radius)
    rm.bind_camera(camera)
    rm.mark_camera_dirty(aspect=gl_window.width / gl_window.height)
    rm.sync()

    program = _Store.program()

    pixels_initial = _render(gl_window, rm, program)
    background = bytes([12, 12, 20]) * (len(pixels_initial) // 3)
    assert pixels_initial != background, "framebuffer is empty — no silhouette rendered"

    v0 = next(iter(mesh.all_vertex_ids()))
    original_pos = mesh.vertex_position(v0)
    mesh.set_vertex_position(v0, tuple(c * 3.0 for c in (1.0, 1.0, 1.0)))
    rm.mark_vertices_dirty({v0})
    rm.sync()

    pixels_after_move = _render(gl_window, rm, program)
    assert pixels_after_move != pixels_initial, "vertex move produced no visible pixel change"

    # restore for hygiene (no assertion needed — window/session-scoped mesh is local)
    mesh.set_vertex_position(v0, original_pos)
