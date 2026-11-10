"""AD-031 P5 in the real GL path: a Bridge on a SubD edit object (level 2) - two rings, their inner borders joined
into a tube - rebuilds the viewport and the SubD surface, the new faces (without UVs) draw, Undo draws exactly the
frame of before and Redo exactly the frame after. No GL error on the way.

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_bridge.py`, own process); skips without."""

from __future__ import annotations

import pytest

import tests.subdivision_meshes  # noqa: F401  (examples/ on sys.path)

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from loaders.assets import asset_path  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction import commands  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.subdivision.gl_lines import GLSubdLineOverlay  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402

SIZE = 192


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _render(gl_window, app) -> bytes:
    from pyglet import gl

    gl_window.switch_to()
    gl.glViewport(0, 0, *gl_window.get_framebuffer_size())
    app.update_viewport(0)
    app.viewport.sync()
    gl.glClearColor(0.05, 0.05, 0.08, 1.0)
    gl_window.clear()
    app.viewport.render()
    gl.glFinish()
    buf = (gl.GLubyte * (SIZE * SIZE * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def test_bridge_rebuilds_the_view_and_undo_redo_draw_the_frames_of_before_and_after(gl_window):
    from tests.test_bridge import _rings

    gl_window.switch_to()
    app = Application()
    app.init_scene(
        "obj",
        obj_path=asset_path("subd_cube"),
        store_type=GLRenderStore,
        point_overlay_type=GLPointOverlay,
        line_overlay_type=GLLineOverlay,
        face_overlay_type=GLTriangleOverlay,
        subd_overlay_type=GLSubdLineOverlay,
    )
    rings, bottom, top = _rings(turn=0.2)
    app.scene.mesh.load_state(rings.export_state())
    app.viewport.on_topology_changed()
    app.set_viewport_size(SIZE, SIZE)
    mesh = app.scene.mesh
    app.key_press(Input("key", "2", frozenset({"ctrl"})))  # SubD level 2 on the edit object
    app.frame_scene()
    app.dispatch_command(commands.SET_VERTEX_MODE)
    app.selection.vertices = {bottom[0], top[0]}
    app.viewport.on_selection_changed()
    before = _render(gl_window, app)

    assert app.dispatch_command(commands.BRIDGE), app.status_message
    assert len(mesh.all_face_ids()) == 24
    after = _render(gl_window, app)
    assert after != before

    assert app.key_press(Input("key", "z", frozenset({"ctrl"})))
    assert len(mesh.all_face_ids()) == 16
    assert _render(gl_window, app) == before
    assert app.key_press(Input("key", "y", frozenset({"ctrl"})))
    assert _render(gl_window, app) == after
