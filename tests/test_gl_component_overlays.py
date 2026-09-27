"""Edge-/Face-Highlight im echten GL-Pfad (WP-06 B5b): `GLTriangleOverlay`
und die Hover-/Selected-Layer von `GLLineOverlay`.

Needs a real GL context (Xvfb or a real display) - run via
`xvfb-run -a python3 -m pytest tests/test_gl_component_overlays.py`. Skips
cleanly when no context is available (same pattern as
`tests/test_gl_line_overlay.py`).
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import SelectionMode  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction import commands as cmd  # noqa: E402
from mirai.viewport import vecmath as v  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import SELECTED_COLOR, GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402

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


@pytest.fixture
def app(gl_window) -> Application:
    app = Application()
    app.init_scene(
        "cube",
        store_type=GLRenderStore,
        point_overlay_type=GLPointOverlay,
        line_overlay_type=GLLineOverlay,
        face_overlay_type=GLTriangleOverlay,
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


def _is_selected(rgb) -> bool:
    return all(abs(c - round(e * 255)) <= TOL for c, e in zip(rgb, SELECTED_COLOR[:3]))


def _selected_pixel_count(pixels: bytes) -> int:
    return sum(1 for i in range(0, len(pixels), 3) if _is_selected(pixels[i:i + 3]))


def _screen(app, point) -> tuple[float, float]:
    return app.camera.project_to_screen(point, app.viewport_width, app.viewport_height)


def _faces_by_facing(app) -> list:
    """Face IDs sorted from facing the camera most to facing away most."""
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

    return sorted(mesh.all_face_ids(), key=facing, reverse=True)


def _face_samples(app, fid) -> list[tuple[int, int]]:
    """Screen pixels well inside the face: centroid and 60 % towards each corner."""
    mesh = app.scene.mesh
    corners = [_screen(app, mesh.vertex_position(vid)) for vid in mesh.face_vertices(fid)]
    cx = sum(p[0] for p in corners) / len(corners)
    cy = sum(p[1] for p in corners) / len(corners)
    points = [(cx, cy)] + [(cx + 0.6 * (x - cx), cy + 0.6 * (y - cy)) for x, y in corners]
    return [(int(x), int(y)) for x, y in points]


def _select_face(app, fid) -> None:
    app.selection.mode = SelectionMode.FACE
    app.selection.set({fid})
    app.viewport.on_selection_changed()


@pytest.mark.parametrize(
    "display",
    [(), (cmd.TOGGLE_WIREFRAME_OVERLAY,), (cmd.SET_FLAT_SHADED,), (cmd.SET_WIREFRAME,)],
)
def test_selected_front_face_is_filled_yellow(gl_window, app, display):
    for command in display:
        app.dispatch_command(command)
    fid = _faces_by_facing(app)[0]
    _select_face(app, fid)
    pixels = _render(gl_window, app)
    for x, y in _face_samples(app, fid):
        assert _is_selected(_pixel(pixels, x, y))


def test_selected_back_face_is_hidden_by_depth_but_shows_in_wireframe(gl_window, app):
    fid = _faces_by_facing(app)[-1]
    _select_face(app, fid)
    assert _selected_pixel_count(_render(gl_window, app)) == 0
    app.dispatch_command(cmd.SET_WIREFRAME)
    assert _selected_pixel_count(_render(gl_window, app)) > 0


def test_hovered_face_tints_without_replacing_the_shading(gl_window, app):
    fid = _faces_by_facing(app)[0]
    plain = _render(gl_window, app)
    app.selection.mode = SelectionMode.FACE
    app.selection.hovered = fid
    app.viewport.on_selection_changed()
    hovered = _render(gl_window, app)
    for x, y in _face_samples(app, fid):
        before, after = _pixel(plain, x, y), _pixel(hovered, x, y)
        assert after != before
        assert not _is_selected(after)  # translucent, not the selection fill


def test_selected_edge_is_drawn_as_a_yellow_line(gl_window, app):
    mesh = app.scene.mesh
    front = mesh.face_vertices(_faces_by_facing(app)[0])
    a, b = front[0], front[1]
    eid = next(
        e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b}
    )
    app.selection.mode = SelectionMode.EDGE
    app.selection.set({eid})
    app.viewport.on_selection_changed()
    pixels = _render(gl_window, app)
    pa, pb = mesh.vertex_position(a), mesh.vertex_position(b)
    sx, sy = _screen(app, tuple((pa[i] + pb[i]) / 2.0 for i in range(3)))
    assert any(
        _is_selected(_pixel(pixels, int(sx) + dx, int(sy) + dy))
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
    )
    # Eine Linie, keine Fläche.
    assert 0 < _selected_pixel_count(pixels) < 4 * SIZE


def test_deselect_removes_the_fill(gl_window, app):
    fid = _faces_by_facing(app)[0]
    _select_face(app, fid)
    assert _selected_pixel_count(_render(gl_window, app)) > 0
    app.selection.clear()
    app.viewport.on_selection_changed()
    assert _selected_pixel_count(_render(gl_window, app)) == 0
