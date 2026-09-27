"""Display-Modi im echten GL-Pfad (WP-06 B5a): Linien-Overlay, Wireframe,
Flat Shading über `u_flat`.

Needs a real GL context (Xvfb or a real display) - run via
`xvfb-run -a python3 -m pytest tests/test_gl_line_overlay.py`. Skips
cleanly when no context is available (same pattern as
`tests/test_gl_point_overlay.py`).
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from mirai.application import Application  # noqa: E402
from mirai.interaction import commands as cmd  # noqa: E402
from mirai.viewport import vecmath as v  # noqa: E402
from viewport.gl_line_overlay import EDGE_COLOR, GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402

SIZE = 128
BACKGROUND = (0.05, 0.05, 0.08)
TOL = 9  # see tests/test_gl_point_overlay.py (RGB565-like EGL framebuffer)


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _app(gl_window) -> Application:
    app = Application()
    app.init_scene(
        "cube",
        store_type=GLRenderStore,
        point_overlay_type=GLPointOverlay,
        line_overlay_type=GLLineOverlay,
    )
    app.frame_scene()
    app.set_viewport_size(gl_window.width, gl_window.height)
    return app


def _render(gl_window, app) -> bytes:
    from pyglet import gl

    gl_window.switch_to()
    app.viewport.sync()
    gl.glClearColor(*BACKGROUND, 1.0)
    gl_window.clear()
    app.viewport.render()
    gl.glFinish()
    buf = (gl.GLubyte * (gl_window.width * gl_window.height * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(
        0, 0, gl_window.width, gl_window.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf
    )
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def _pixel(pixels: bytes, x: int, y: int) -> tuple[int, int, int]:
    i = (y * SIZE + x) * 3
    return pixels[i], pixels[i + 1], pixels[i + 2]


def _close(rgb, expected) -> bool:
    return all(abs(c - round(e * 255)) <= TOL for c, e in zip(rgb, expected))


def _is_edge(rgb) -> bool:
    return _close(rgb, EDGE_COLOR[:3])


def _is_background(rgb) -> bool:
    return _close(rgb, BACKGROUND)


def _edge_pixel_count(pixels: bytes) -> int:
    return sum(
        1 for i in range(0, len(pixels), 3) if _is_edge(pixels[i:i + 3])
    )


def _screen(app, point) -> tuple[float, float]:
    return app.camera.project_to_screen(point, app.viewport_width, app.viewport_height)


def _front_face_corners(app) -> list[tuple[float, float, float]]:
    """Corner positions of the cube face turned most towards the camera."""
    mesh = app.scene.mesh
    center = [
        sum(mesh.vertex_position(vid)[i] for vid in mesh.all_vertex_ids()) / 8.0
        for i in range(3)
    ]
    to_eye = v.normalize(v.sub(app.camera.eye(), center))

    def facing(fid):
        corners = [mesh.vertex_position(vid) for vid in mesh.face_vertices(fid)]
        centroid = [sum(c[i] for c in corners) / len(corners) for i in range(3)]
        return v.dot(v.normalize(v.sub(centroid, center)), to_eye)

    fid = max(mesh.all_face_ids(), key=facing)
    return [mesh.vertex_position(vid) for vid in mesh.face_vertices(fid)]


def _face_samples(app) -> list[tuple[int, int]]:
    """Screen pixels well inside the front face: its centroid and points 60 %
    of the way from the centroid to each corner."""
    corners = [_screen(app, c) for c in _front_face_corners(app)]
    cx = sum(p[0] for p in corners) / len(corners)
    cy = sum(p[1] for p in corners) / len(corners)
    points = [(cx, cy)] + [(cx + 0.6 * (x - cx), cy + 0.6 * (y - cy)) for x, y in corners]
    return [(int(x), int(y)) for x, y in points]


def _front_edge_midpoints(app) -> list[tuple[float, float]]:
    corners = _front_face_corners(app)
    out = []
    for a, b in zip(corners, corners[1:] + corners[:1]):
        mid = tuple((a[i] + b[i]) / 2.0 for i in range(3))
        out.append(_screen(app, mid))
    return out


def _edge_near(pixels: bytes, sx: float, sy: float) -> bool:
    return any(
        _is_edge(_pixel(pixels, int(sx) + dx, int(sy) + dy))
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
    )


def test_shaded_default_draws_no_edges(gl_window):
    app = _app(gl_window)
    pixels = _render(gl_window, app)
    assert _edge_pixel_count(pixels) == 0
    assert app.viewport.line_overlay.vertex_list() is None


def test_wireframe_draws_edges_and_no_faces(gl_window):
    app = _app(gl_window)
    app.dispatch_command(cmd.SET_WIREFRAME)
    pixels = _render(gl_window, app)
    for x, y in _face_samples(app):
        assert _is_background(_pixel(pixels, x, y))
    for sx, sy in _front_edge_midpoints(app):
        assert _edge_near(pixels, sx, sy)


def test_wire_overlay_sits_on_faces_and_hides_back_edges(gl_window):
    app = _app(gl_window)
    app.dispatch_command(cmd.SET_WIREFRAME)
    wire_only = _edge_pixel_count(_render(gl_window, app))

    app.dispatch_command(cmd.SET_SHADED)
    app.dispatch_command(cmd.TOGGLE_WIREFRAME_OVERLAY)
    pixels = _render(gl_window, app)
    # Front edges win over their own faces (polygon offset, no z-fighting) ...
    for sx, sy in _front_edge_midpoints(app):
        assert _edge_near(pixels, sx, sy)
    # ... the face interior is shaded, not background or edge colour ...
    for x, y in _face_samples(app):
        rgb = _pixel(pixels, x, y)
        assert not _is_background(rgb) and not _is_edge(rgb)
    # ... and edges behind the cube are depth-tested away.
    assert 0 < _edge_pixel_count(pixels) < wire_only


def test_flat_shading_is_uniform_across_a_planar_face(gl_window):
    app = _app(gl_window)
    smooth = _render(gl_window, app)
    smooth_samples = {_pixel(smooth, x, y) for x, y in _face_samples(app)}
    # Smooth: averaged corner normals → the shade varies across the face.
    assert len(smooth_samples) > 1

    app.dispatch_command(cmd.SET_FLAT_SHADED)
    flat = _render(gl_window, app)
    flat_samples = [_pixel(flat, x, y) for x, y in _face_samples(app)]
    reference = flat_samples[0]
    for rgb in flat_samples:
        assert all(abs(a - b) <= 2 for a, b in zip(rgb, reference))
    assert not _is_background(reference)


def test_lines_follow_a_move_in_place(gl_window):
    app = _app(gl_window)
    app.dispatch_command(cmd.SET_WIREFRAME)
    before = _render(gl_window, app)
    overlay = app.viewport.line_overlay
    vlist = overlay.vertex_list()
    uploads = overlay.uploads

    mesh = app.scene.mesh
    vid = mesh.all_vertex_ids()[0]
    x, y, z = mesh.vertex_position(vid)
    mesh.set_vertex_position(vid, (x * 1.4, y * 1.4, z * 1.4))
    app.viewport.on_vertices_moved({vid})
    after = _render(gl_window, app)

    assert after != before
    assert overlay.uploads == uploads + 1
    # Same edge count → positions overwritten in the existing vertex list.
    assert overlay.vertex_list() is vlist
    assert list(vlist.position[:]) == pytest.approx(
        [c for seg in app.viewport.edge_segments for p in seg for c in p]
    )


def test_render_leaves_depth_func_and_polygon_offset_reset(gl_window):
    from pyglet import gl

    app = _app(gl_window)
    app.dispatch_command(cmd.TOGGLE_WIREFRAME_OVERLAY)
    _render(gl_window, app)
    func = gl.GLint()
    gl.glGetIntegerv(gl.GL_DEPTH_FUNC, func)
    assert func.value == gl.GL_LESS
    assert not gl.glIsEnabled(gl.GL_POLYGON_OFFSET_FILL)
    assert not gl.glIsEnabled(gl.GL_DEPTH_TEST)
