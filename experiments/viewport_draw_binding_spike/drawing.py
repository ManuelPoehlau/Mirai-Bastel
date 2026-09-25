"""Shared draw-call helpers used by `run.py`, `run_bench.py` and the pixel
smoke test — kept in one place so the tests exercise exactly what the
window draws, not a parallel path (the whole point of this spike, see
README "Why not a parallel path")."""

from __future__ import annotations

LIGHT_DIR = (0.4, 0.6, 0.7)


def apply_camera_uniforms(program, store) -> None:
    data = store.uniform_data("camera_uniforms")
    if len(data) != 32:
        return
    program["u_view"] = tuple(data[0:16])
    program["u_proj"] = tuple(data[16:32])


def draw_frame(program, store) -> None:
    from pyglet import gl

    program.use()
    apply_camera_uniforms(program, store)
    program["u_light_dir"] = LIGHT_DIR

    vlist = store.vertex_list()
    if vlist is None:
        return
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_CULL_FACE)
    gl.glCullFace(gl.GL_BACK)
    vlist.draw(gl.GL_TRIANGLES)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glDisable(gl.GL_DEPTH_TEST)


def read_pixels_rgb(window) -> bytes:
    from pyglet import gl

    width, height = window.width, window.height
    buf = (gl.GLubyte * (width * height * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, width, height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    return bytes(buf)
