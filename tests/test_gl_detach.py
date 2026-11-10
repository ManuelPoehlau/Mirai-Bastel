"""AD-031 P3 in the real GL path: after a Detach on a SubD edit object (level 2) - the symmetric subd_cube, a band
across the plane, which takes its mirror faces - the viewport and the SubD surface rebuild, Undo draws exactly the
frame of before (the faces back in the edit object and selected, the new object gone) and Redo exactly the frame after. No GL error
on the way.

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_detach.py`, own process); skips without."""

from __future__ import annotations

import pytest

import tests.subdivision_meshes  # noqa: F401  (examples/ on sys.path)

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import SelectionMode  # noqa: E402
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


def test_detach_rebuilds_the_view_and_undo_redo_draw_the_frames_of_before_and_after(gl_window):
    from mirai.symmetry_axis import definition_for_axis

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
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    app.key_press(Input("key", "2", frozenset({"ctrl"})))  # SubD level 2 on the edit object
    app.frame_scene()
    app.dispatch_command(commands.SET_FACE_MODE)
    band = {f for f in mesh.all_face_ids() if max(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0.0
            and min(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) == 0.0}
    assert band
    faces = len(mesh.all_face_ids())
    objects = set(app.scene.objects)
    app.selection.mode = SelectionMode.FACE
    app.selection.faces = set(band)
    app.viewport.on_selection_changed()
    before = _render(gl_window, app)  # with the band highlighted: Undo restores that selection too

    assert app.dispatch_command(commands.DETACH), app.status_message
    (new_id,) = set(app.scene.objects) - objects
    assert len(mesh.all_face_ids()) == faces - 2 * len(band)
    assert new_id in app.viewport.object_entries
    after = _render(gl_window, app)
    assert after != before

    # The key path (Ctrl+Z / Ctrl+Y) rebuilds the edit object's view after a mesh step (E23, `_undo_redo`); the API's
    # `dispatch_command(UNDO)` runs the step only - for Delete as well (observed 2026-11-10), so the frames use the keys.
    assert app.key_press(Input("key", "z", frozenset({"ctrl"})))
    assert app.selection.faces == band
    assert new_id not in app.viewport.object_entries
    assert _render(gl_window, app) == before
    assert app.key_press(Input("key", "y", frozenset({"ctrl"})))
    assert new_id in app.viewport.object_entries
    assert _render(gl_window, app) == after
