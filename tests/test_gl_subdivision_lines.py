"""SubD lines in the real GL path (2026-10-23): isolines, cage and highlight coherence.

The two observed defects and their causes (traced in `Viewport.render` / `_apply_draw_style`):

1. Isolines looked dashed and became solid after hovering an edge: the replacement surface got
   its polygon offset only while the wire overlay or an edge highlight was on, so the isolines —
   which lie exactly on the surface's triangle edges — z-fought with it (`GL_LEQUAL`). Pinned: the
   isolines cover the same pixels with and without a hovered edge, and the surface is always offset.
2. With cage + smooth surface no edge highlight was visible: the SubD cage was an extra overlay
   drawn after the app's hover/selected edge layers, at the same positions, so it painted over them.
   Pinned: a selected control edge shows the selection colour in cage mode — on the cage edge and on
   its isoline chain on the surface — and in iso mode.

Plus the hierarchy: in iso mode the cage is secondary (fainter than in cage mode), Shift+V shows
cage edges hidden by the surface, and hovering never uploads surface geometry.

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_subdivision_lines.py`).
"""

from __future__ import annotations

import pytest

import tests.subdivision_meshes  # noqa: F401  (examples/ on sys.path)

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import SelectionMode  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.subdivision import VIEW_CAGE, VIEW_ISO  # noqa: E402
from mirai.subdivision.gl_lines import GLSubdLineOverlay  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import SELECTED_COLOR, GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402

SIZE = 256
BACKGROUND = (0.05, 0.05, 0.08)
TOL = 12


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _app(gl_window, asset="subd_cube") -> Application:
    gl_window.switch_to()
    app = Application()
    app.init_scene(
        "obj",
        obj_path=asset_path(asset),
        store_type=GLRenderStore,
        point_overlay_type=GLPointOverlay,
        line_overlay_type=GLLineOverlay,
        face_overlay_type=GLTriangleOverlay,
        subd_overlay_type=GLSubdLineOverlay,
    )
    app.frame_scene()
    app.camera.orbit(25.0, -20.0)
    app.set_viewport_size(SIZE, SIZE)
    return app


def _view(app, view: str, level: int = 2) -> None:
    app.key_press(Input("key", str(level), frozenset({"ctrl"})))
    while app.subdivision.view != view:
        app.key_press(Input("key", "v"))


def _render(gl_window, app) -> bytes:
    from pyglet import gl

    gl_window.switch_to()
    gl.glViewport(0, 0, *gl_window.get_framebuffer_size())
    app.viewport.sync()
    gl.glClearColor(*BACKGROUND, 1.0)
    gl_window.clear()
    app.viewport.render()
    gl.glFinish()
    buf = (gl.GLubyte * (SIZE * SIZE * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def _count(pixels: bytes, rgb, tol: int = TOL) -> int:
    want = [round(c * 255) for c in rgb[:3]]
    return sum(
        1 for i in range(0, len(pixels), 3)
        if all(abs(pixels[i + k] - want[k]) <= tol for k in range(3))
    )


def _front_edge(app):
    """The control edge nearest the eye among those projecting near the image centre."""
    mesh = app.viewport.mesh
    eye = app.camera.eye()
    candidates = []
    for e in mesh.all_edge_ids():
        a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(e))
        mid = tuple((p + q) / 2 for p, q in zip(a, b))
        sx, sy = app.camera.project_to_screen(mid, SIZE, SIZE)
        if abs(sx - SIZE / 2) < SIZE / 4 and abs(sy - SIZE / 2) < SIZE / 4:
            candidates.append((sum((m - c) ** 2 for m, c in zip(mid, eye)), int(e), e))
    return min(candidates)[2]


def _select_edge(app, edge) -> None:
    app.selection.mode = SelectionMode.EDGE
    app.selection.set({edge})
    app.viewport.on_selection_changed()


def test_isolines_do_not_depend_on_hover(gl_window):
    app = _app(gl_window)
    _view(app, VIEW_ISO)
    iso = app.subdivision.lines.sink.LAYER_STYLES["subd_iso"][0]
    plain = _count(_render(gl_window, app), iso)
    app.selection.mode = SelectionMode.EDGE
    app.selection.hovered = _front_edge(app)
    app.viewport.on_selection_changed()
    hovered = _count(_render(gl_window, app), iso)
    assert plain > 300, plain
    # the hovered chain covers a few of the isoline pixels; everything else is unchanged
    assert abs(plain - hovered) <= 0.15 * plain, (plain, hovered)


def test_the_replacement_surface_is_always_offset(gl_window):
    app = _app(gl_window)
    _view(app, VIEW_ISO)
    app.viewport.sync()
    store = app.viewport.surface_render_mesh.store
    assert store.polygon_offset is True  # without wire and without any highlight
    app.key_press(Input("key", "d"))  # Flat
    app.viewport.sync()
    assert store.polygon_offset is True and store.flat is True


@pytest.mark.parametrize("view", [VIEW_CAGE, VIEW_ISO])
def test_a_selected_edge_is_visible_in_every_subd_view(gl_window, view):
    app = _app(gl_window)
    _view(app, view)
    _render(gl_window, app)
    before = _count(_render(gl_window, app), SELECTED_COLOR)
    _select_edge(app, _front_edge(app))
    after = _count(_render(gl_window, app), SELECTED_COLOR)
    assert before == 0
    assert after > 20, after


def test_the_highlight_covers_cage_edge_and_isoline_chain(gl_window):
    """Cage mode: the selected edge's chain on the surface is drawn too (pixels below the cage
    edge, where only the chain can be)."""
    app = _app(gl_window)
    _view(app, VIEW_CAGE)
    edge = _front_edge(app)
    _select_edge(app, edge)
    with_chain = _count(_render(gl_window, app), SELECTED_COLOR)
    app.subdivision.lines.sink.set_segments("subd_iso_selected", [])  # cage edge alone
    app.subdivision.lines._highlight_key = ("frozen",)  # keep the presentation from refilling it
    without_chain = _count(_render(gl_window, app), SELECTED_COLOR)
    assert with_chain > without_chain


def _change(a: bytes, b: bytes) -> tuple[int, float]:
    """(pixels that differ by more than 2 levels, their mean max-channel difference)."""
    diffs = [max(abs(a[i + k] - b[i + k]) for k in range(3)) for i in range(0, len(a), 3)]
    changed = [d for d in diffs if d > 2]
    return len(changed), (sum(changed) / len(changed) if changed else 0.0)


def test_iso_mode_draws_the_cage_secondary(gl_window):
    """The cage in the iso view changes the image visibly but much less than a full-strength cage."""
    app = _app(gl_window)
    _view(app, VIEW_ISO)
    preview = app.subdivision
    preview.set_secondary_strength(0.0)
    none = _render(gl_window, app)
    preview.set_secondary_strength(0.35)
    secondary = _render(gl_window, app)
    preview.set_secondary_strength(1.0)
    full = _render(gl_window, app)
    n_secondary, mean_secondary = _change(none, secondary)
    n_full, mean_full = _change(none, full)
    assert n_secondary > 100
    assert mean_secondary < 0.6 * mean_full, (mean_secondary, mean_full)


def test_shift_v_shows_cage_edges_hidden_by_the_surface(gl_window):
    app = _app(gl_window, "head_basemesh")
    _view(app, VIEW_CAGE, level=1)
    cage_rgb = app.subdivision.lines.sink.LAYER_STYLES["subd_cage"][0]
    hidden = _count(_render(gl_window, app), cage_rgb, tol=6)
    app.key_press(Input("key", "v", frozenset({"shift"})))
    always = _count(_render(gl_window, app), cage_rgb, tol=6)
    assert always > hidden * 1.2, (hidden, always)


def test_hover_changes_upload_no_surface_geometry(gl_window):
    app = _app(gl_window)
    _view(app, VIEW_ISO)
    _render(gl_window, app)
    rm = app.viewport.surface_render_mesh
    uploaded = rm.stats.uploaded_bytes
    vlist = rm.store.vertex_list()
    sink = app.subdivision.lines.sink
    lines_before = {layer: sink.vertex_list(layer) for layer in ("subd_cage", "subd_iso")}
    mesh = app.viewport.mesh
    app.selection.mode = SelectionMode.EDGE
    for e in sorted(mesh.all_edge_ids(), key=int)[:6]:
        app.selection.hovered = e
        app.viewport.on_selection_changed()
        _render(gl_window, app)
    assert rm.stats.uploaded_bytes == uploaded
    assert rm.store.vertex_list() is vlist
    assert {layer: sink.vertex_list(layer) for layer in lines_before} == lines_before
