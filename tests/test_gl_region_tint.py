"""Region colours in the real GL path (Manu 2026-10-25): a tinted face is drawn in its region colour (shaded, desaturated),
untinted faces are bit-identical to an untinted draw, and the switch is a uniform only (same VertexList, no upload).

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_region_tint.py`); skips without."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Mesh  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.render_mesh import RenderMesh  # noqa: E402

SIZE = 160


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _plane() -> Mesh:
    """2x2 planar quads facing +Z."""
    mesh = Mesh()
    ids = {(i, j): mesh.add_vertex((i - 1.0, j - 1.0, 0.0)) for j in range(3) for i in range(3)}
    for j in range(2):
        for i in range(2):
            mesh.add_face([ids[i, j], ids[i + 1, j], ids[i + 1, j + 1], ids[i, j + 1]])
    return mesh


def _draw(gl_window, rm, camera) -> bytes:
    from pyglet import gl

    gl_window.switch_to()
    gl.glViewport(0, 0, *gl_window.get_framebuffer_size())
    gl.glClearColor(0.0, 0.0, 0.0, 1.0)
    gl_window.clear()
    rm.render(camera)
    gl.glFinish()
    buf = (gl.GLubyte * (SIZE * SIZE * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def _pixel(pixels: bytes, x: int, y: int) -> tuple[int, int, int]:
    i = (y * SIZE + x) * 3
    return pixels[i], pixels[i + 1], pixels[i + 2]


def _build(gl_window):
    gl_window.switch_to()
    mesh = _plane()
    rm = RenderMesh(mesh, store_type=GLRenderStore)
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=0.0)
    rm.bind_camera(camera)
    rm.mark_camera_dirty(aspect=1.0)
    rm.sync()
    return mesh, rm, camera


def test_a_tinted_face_is_drawn_in_its_colour_and_the_others_are_unchanged(gl_window):
    mesh, rm, camera = _build(gl_window)
    plain = _draw(gl_window, rm, camera)
    face = mesh.all_face_ids()[0]  # the lower-left quad (x, y in [-1, 0]): left half, lower half on screen
    rm.set_face_tints({face: (0.95, 0.55, 0.55)})
    rm.store.set_region_tint(True)
    tinted = _draw(gl_window, rm, camera)
    left, right = SIZE // 2 - 20, SIZE // 2 + 20
    low, high = SIZE // 2 - 20, SIZE // 2 + 20  # GL origin is bottom-left
    r, g, b = _pixel(tinted, left, low)
    assert r > g + 30 and r > b + 30  # reddish: the region colour won over the grey-blue base
    assert _pixel(plain, left, low) != (r, g, b)
    # the other three quads are the same pixels as without any tint
    for x, y in ((right, low), (left, high), (right, high)):
        assert _pixel(tinted, x, y) == _pixel(plain, x, y)
    rm.store.release()


def test_the_switch_is_one_uniform_and_changes_nothing_on_the_gpu(gl_window):
    mesh, rm, camera = _build(gl_window)
    rm.set_face_tints({mesh.all_face_ids()[0]: (0.95, 0.55, 0.55)})
    rm.store.set_region_tint(True)
    on = _draw(gl_window, rm, camera)
    vlist, uploaded = rm.store.vertex_list(), rm.stats.uploaded_bytes
    rm.store.set_region_tint(False)
    off = _draw(gl_window, rm, camera)
    assert rm.store.vertex_list() is vlist and rm.stats.uploaded_bytes == uploaded
    assert on != off
    # off looks exactly like a mesh that never had a tint
    mesh2, rm2, camera2 = _build(gl_window)
    assert off == _draw(gl_window, rm2, camera2)
    rm.store.release()
    rm2.store.release()
