"""The LookDev pass in the real GL path (AD-038): the store's two accesses (§4.2 / §4.3), the pass and its GL state,
the grey card (E7), the depth contract (E8), a selected painted head (E13), the GL state (E14).

Needs a real GL context, in its own process: `xvfb-run -a python -m pytest tests/test_gl_lookdev_pass.py -q`."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from gui.imgui_layer import snapshot_gl_state  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from tests.test_gl_texture import GREEN, RED, _live, _plane  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.material import Material  # noqa: E402
from viewport.render_mesh import TRIANGLE_UVS, RenderMesh  # noqa: E402

SIZE = 160


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _bound(unit: int, target) -> int:
    from pyglet import gl

    binding = {gl.GL_TEXTURE_BUFFER: gl.GL_TEXTURE_BINDING_BUFFER, gl.GL_TEXTURE_2D: gl.GL_TEXTURE_BINDING_2D}[target]
    value = gl.GLint()
    gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
    gl.glGetIntegerv(binding, value)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    return value.value


def _requested(gl_window, mesh, texture=None) -> RenderMesh:
    gl_window.switch_to()
    rm = RenderMesh(mesh, store_type=GLRenderStore)
    rm.bind_camera(OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=0.0))
    rm.mark_camera_dirty(aspect=1.0)
    rm.bind_material(Material((0.5, 0.5, 0.5), texture=texture))
    rm.mark_material_dirty()
    rm.set_uvs_requested(True)
    rm.sync()
    return rm


# -- §4.2 / §4.3: the store's two accesses --------------------------------------------------------------------------

def test_bind_triangle_uvs_uploads_and_binds_only_the_uvs(gl_window):
    from pyglet import gl

    rm = _requested(gl_window, _plane(uvs=True))
    store = rm.store
    before = snapshot_gl_state()
    assert store.bind_triangle_uvs(3)
    name = _bound(3, gl.GL_TEXTURE_BUFFER)
    assert name and store._face_gl[TRIANGLE_UVS][1] == name
    assert set(store._face_gl) == {TRIANGLE_UVS}  # nothing else of the face data went up
    assert snapshot_gl_state() == before  # unit 0 active again
    # the buffer holds the store's UVs (read back through a 1D buffer view)
    buffer_id = store._face_gl[TRIANGLE_UVS][0]
    data = (gl.GLfloat * len(store._face_cpu[TRIANGLE_UVS]))()
    gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, buffer_id)
    gl.glGetBufferSubData(gl.GL_TEXTURE_BUFFER, 0, len(data) * 4, data)
    gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, 0)
    assert list(data) == list(store._face_cpu[TRIANGLE_UVS])
    GLRenderStore.unbind_triangle_uvs(3)
    assert _bound(3, gl.GL_TEXTURE_BUFFER) == 0 and gl.glGetError() == gl.GL_NO_ERROR
    # a mesh without UVs has none to bind
    plain = _requested(gl_window, _plane(uvs=False))
    assert not plain.store.bind_triangle_uvs(3) and _bound(3, gl.GL_TEXTURE_BUFFER) == 0
    rm.store.release()
    plain.store.release()


def test_the_worklight_draw_after_a_uv_bind_is_unchanged(gl_window):
    """The Worklight draw of a requested mesh stays the untextured one, and a LookDev bind in between changes nothing."""
    from tests.test_gl_texture import _draw

    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=0.0)
    plain = _requested(gl_window, _plane(uvs=False))
    plain.set_uvs_requested(False)
    reference = _draw(gl_window, plain, camera)
    rm = _requested(gl_window, _plane(uvs=True))
    assert _draw(gl_window, rm, camera) == reference
    rm.store.bind_triangle_uvs(3)
    GLRenderStore.unbind_triangle_uvs(3)
    assert _draw(gl_window, rm, camera) == reference
    rm.store.release()
    plain.store.release()


def test_texture_binding_of_a_path_and_a_live_texture(gl_window, tmp_path):
    from pyglet import gl

    from tests.test_obj_uvs import write_png

    gl_window.switch_to()
    assert GLRenderStore.texture_binding(None) is None
    assert GLRenderStore.texture_binding(str(tmp_path / "missing.png")) is None
    path = tmp_path / "red.png"
    write_png(path, 4, 4, RED)
    target, name = GLRenderStore.texture_binding(str(path))
    texture = GLRenderStore.texture(str(path))
    assert (target, name) == (texture.target, texture.id)  # the shared cache: one upload
    live = _live(GREEN)
    assert live.gl_name is None
    target, name = GLRenderStore.texture_binding(live)
    assert target == gl.GL_TEXTURE_2D and name == live.gl_name and live.uploads == 1
    GLRenderStore.texture_binding(live)
    assert live.uploads == 1  # nothing pending: no second upload
    live.rgba[0:2, 0:2, :3] = RED
    live.mark(0, 0, 2, 2)
    live.finish()
    GLRenderStore.texture_binding(live)
    assert live.uploads == 2
    assert _bound(4, gl.GL_TEXTURE_2D) == 0 and gl.glGetError() == gl.GL_NO_ERROR  # the caller binds the unit
    live.release()
