"""AD-031 P2 in the real GL path: after a large Attach (the head basemesh into a SubD cube) the viewport and the SubD
surface rebuild, Undo draws exactly the frame of before (the part back as its own object) and Redo exactly the frame
after the Attach. No GL error on the way. Timing on the reference PC is a measurement, not this test.

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_attach.py`, own process); skips without."""

from __future__ import annotations

import pytest

import tests.subdivision_meshes  # noqa: F401  (examples/ on sys.path)

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import ObjectTransform  # noqa: E402
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


def test_a_large_attach_rebuilds_the_view_and_undo_redo_draw_the_frames_of_before_and_after(gl_window):
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
    app.set_viewport_size(SIZE, SIZE)
    app.key_press(Input("key", "2", frozenset({"ctrl"})))  # SubD level 2 on the edit object
    head = app.import_obj(asset_path("head_basemesh"))
    assert head is not None, app.status_message
    head.transform = ObjectTransform(translation=(2.5, 0.0, 0.0), scale=0.02)
    app._objects.placement_changed()
    app.frame_scene()
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.selection.objects = {head.id}
    faces = len(app.scene.mesh.all_face_ids()) + len(head.mesh.all_face_ids())
    before = _render(gl_window, app)

    assert app.dispatch_command(commands.ATTACH), app.status_message
    assert len(app.scene.mesh.all_face_ids()) == faces
    after = _render(gl_window, app)
    assert after != before

    app.dispatch_command(commands.UNDO)
    assert _render(gl_window, app) == before
    app.dispatch_command(commands.REDO)
    assert _render(gl_window, app) == after
