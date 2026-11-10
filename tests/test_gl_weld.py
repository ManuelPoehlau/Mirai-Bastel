"""AD-031 P4 in the real GL path: a Weld on a SubD edit object (level 2) - the subd_cube with its +X half detached and
attached back, so the seam's points are doubled and the SubD surface is open there - rebuilds the viewport and the
SubD surface (the seam closes), Undo draws exactly the frame of before and Redo exactly the frame after. No GL error on
the way.

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_weld.py`, own process); skips without."""

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


def test_weld_rebuilds_the_view_and_undo_redo_draw_the_frames_of_before_and_after(gl_window):
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
    vertices = len(mesh.all_vertex_ids())
    app.key_press(Input("key", "2", frozenset({"ctrl"})))  # SubD level 2 on the edit object
    app.frame_scene()
    app.dispatch_command(commands.SET_FACE_MODE)
    half = {f for f in mesh.all_face_ids() if min(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) >= 0.0}
    objects = set(app.scene.objects)
    app.selection.faces = set(half)
    assert app.dispatch_command(commands.DETACH), app.status_message
    (part,) = set(app.scene.objects) - objects
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.selection.objects = {part}
    assert app.attach_objects(), app.status_message
    doubled = len(mesh.all_vertex_ids()) - vertices
    assert doubled > 0
    app.dispatch_command(commands.SET_VERTEX_MODE)
    app.selection.vertices = set(mesh.all_vertex_ids())
    app.viewport.on_selection_changed()
    before = _render(gl_window, app)

    assert app.dispatch_command(commands.WELD), app.status_message
    assert len(mesh.all_vertex_ids()) == vertices
    after = _render(gl_window, app)
    assert after != before

    # The key path (Ctrl+Z / Ctrl+Y) rebuilds the edit object's view after a mesh step (E23, see test_gl_detach.py).
    assert app.key_press(Input("key", "z", frozenset({"ctrl"})))
    assert len(mesh.all_vertex_ids()) == vertices + doubled
    assert _render(gl_window, app) == before
    assert app.key_press(Input("key", "y", frozenset({"ctrl"})))
    assert _render(gl_window, app) == after


def test_a_single_pair_weld_draws_with_subd_and_undo_draws_the_frame_of_before(gl_window):
    """W5 allowed (Manu 2026-11-10, "Change W5"): one pair of the doubled seam welded alone leaves a point where two
    parts touch only there; the SubD level 2 surface and the overlays draw without a GL error, Undo draws exactly the
    frame of before."""
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
    app.key_press(Input("key", "2", frozenset({"ctrl"})))
    app.frame_scene()
    app.dispatch_command(commands.SET_FACE_MODE)
    half = {f for f in mesh.all_face_ids() if min(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) >= 0.0}
    objects = set(app.scene.objects)
    app.selection.faces = set(half)
    assert app.dispatch_command(commands.DETACH), app.status_message
    (part,) = set(app.scene.objects) - objects
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.selection.objects = {part}
    assert app.attach_objects(), app.status_message
    app.dispatch_command(commands.SET_VERTEX_MODE)
    by_position: dict = {}
    for v in mesh.all_vertex_ids():
        by_position.setdefault(tuple(mesh.vertex_position(v)), []).append(v)
    pair = next(vs for p, vs in sorted(by_position.items()) if len(vs) == 2)
    app.selection.vertices = set(pair)
    app.viewport.on_selection_changed()
    before = _render(gl_window, app)
    assert app.weld_vertices(1e-6), app.status_message
    assert "join parts at that point only" in app.status_message
    after = _render(gl_window, app)
    assert after != before
    assert app.key_press(Input("key", "z", frozenset({"ctrl"})))
    assert _render(gl_window, app) == before
