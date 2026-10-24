"""Symmetry display in the Production app: plane outline and problem markers (AD-SYM-04 slice A2).

Q-2 = S-2: status line (A1) plus the plane outline and the problem markers - seam, without partner,
ambiguous - and no partner markers. Headless (TraceStore) with the real GL sink type
`GLSymmetryOverlay` (its data needs no GL; only `draw` does), passed as `src/main.py` does it
through `GL_TYPES`. Ported from the Symmetry Lab, where the overlay lived until A2
(`experiments/symmetry_lab/tests/test_app_lab_cycle.py` and `test_app_lab_partners.py`):

- the outline lies in the plane and encloses the bounds; markers = the report;
- rebuild after Shift+S, after Undo/Redo and after a Move commit (viewport notifications, K-3);
- the plan-A3 deferral while W/E/R runs (no report run per move, the markers follow, the commit
  frame catches up), Esc restores without a run, a definition change right before arming is
  never deferred; hover and selection changes cost nothing;
- wiring: no display without `symmetry_overlay_type`, `load_scene` rebinds it, draw order.
"""

from __future__ import annotations

import sys

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

_EXAMPLES = _REPO_ROOT / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from loaders.assets import asset_path  # noqa: E402
from mirai import symmetry_display  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.mesh_geometry import mesh_bounds  # noqa: E402
from mirai.soft_selection import GLSoftBandOverlay  # noqa: E402
from mirai.symmetry import CorrespondenceState, vertex_correspondence  # noqa: E402
from mirai.symmetry_axis import AXIS_INDEX, current_axis  # noqa: E402
from mirai.symmetry_display import SymmetryDisplay, symmetry_report  # noqa: E402
from mirai.viewport.picking import pick_nearest_vertex  # noqa: E402
from viewport import gl_symmetry_overlay as sink_module  # noqa: E402
from viewport.gl_point_overlay import SELECTED_POINT_SIZE  # noqa: E402
from viewport.gl_symmetry_overlay import (  # noqa: E402
    AMBIGUOUS_LAYER,
    MARKER_LAYERS,
    SEAM_LAYER,
    UNPAIRED_LAYER,
    GLSymmetryOverlay,
)

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)

SHIFT_S = Input("key", "s", frozenset({"shift"}))
W = Input("key", "w")
ESC = Input("key", "ESCAPE")
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))
LMB = Input("mouse", "LEFT")


def make_app(asset: str = "subd_cube", **types) -> Application:
    types.setdefault("symmetry_overlay_type", GLSymmetryOverlay)
    app = Application()
    app.init_scene("obj", obj_path=asset_path(asset), **types)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.pointer_motion(*MISS)
    app.viewport.sync()
    return app


def symmetric_app(asset: str = "subd_cube") -> Application:
    app = make_app(asset)
    assert app.key_press(SHIFT_S) and current_axis(app.scene.mesh) == "X"
    app.viewport.sync()
    return app


def cycle_to(app: Application, axis: str) -> None:
    for _ in range(4):
        if current_axis(app.scene.mesh) == axis:
            return
        assert app.key_press(SHIFT_S)
    raise AssertionError(axis)


def display(app: Application) -> SymmetryDisplay:
    shown = app.symmetry_display
    assert isinstance(shown, SymmetryDisplay)
    return shown


def sink(app: Application) -> GLSymmetryOverlay:
    shown = display(app).sink
    assert isinstance(shown, GLSymmetryOverlay)
    return shown


def screen(app: Application, vid):
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT)


def visible(app: Application) -> list:
    mesh = app.scene.mesh
    return [
        vid
        for vid in sorted(mesh.all_vertex_ids(), key=int)
        if pick_nearest_vertex(app.camera, mesh, *screen(app, vid), WIDTH, HEIGHT, occlusion=True)
        == vid
    ]


def click(app: Application, vid) -> None:
    x, y = screen(app, vid)
    app.pointer_motion(x, y)
    app.pointer_press(LMB, x, y)
    app.pointer_release(LMB.value, x, y)


def in_state(app: Application, state) -> list:
    corr = vertex_correspondence(app.scene.mesh)
    return [v for v in visible(app) if corr[v].state is state]


def pos(app: Application, vid):
    return app.scene.mesh.vertex_position(vid)


def counts(app: Application) -> tuple[int, int]:
    return display(app).plane_recomputes, display(app).recomputes


def drag_w(app: Application) -> None:
    assert app.key_press(W)
    app.pointer_motion(400, 300, 12.0, 7.0)
    assert app.key_release(W)


# == Wiring ========================================================================================


def test_no_display_without_a_symmetry_overlay_type():
    """Headless default (`init_scene` without the type): no display and no derivation at all."""
    app = Application()
    app.init_scene("obj", obj_path=asset_path("subd_cube"))
    assert app.symmetry_display is None
    assert app.viewport.extra_overlays == []
    assert app.key_press(SHIFT_S)
    app.viewport.sync()


def test_the_display_hangs_after_the_soft_bands_as_an_extra_overlay():
    """`init_scene` attaches the bands first, then the symmetry display (draw order: the bands are
    hidden under a definition anyway, AD-020 §8)."""
    app = make_app(soft_overlay_type=GLSoftBandOverlay)
    bands, shown = app.viewport.extra_overlays
    assert isinstance(bands, GLSoftBandOverlay)
    assert shown is display(app)


def test_load_scene_binds_a_fresh_display_to_the_new_viewport():
    app = symmetric_app()
    old = display(app)
    app.load_scene("obj", obj_path=asset_path("subd_cube"), symmetry_overlay_type=GLSymmetryOverlay)
    assert display(app) is not old
    assert app.viewport.extra_overlays == [display(app)]
    app.viewport.sync()
    assert sink(app).segments() == []
    assert all(sink(app).points(layer) == [] for layer in MARKER_LAYERS)


def test_display_draws_outline_then_markers_before_the_app_points(monkeypatch):
    """Extra overlays come after the tool lines and before the Viewport's own point overlay, so the
    app's hover and selection stay on top; inside the sink the outline comes before the markers."""
    pytest.importorskip("pyglet", reason="Viewport.render imports pyglet.gl (requirements-dev.txt)")
    app = symmetric_app()
    log = []

    class AppPoints:
        def set_points(self, layer, positions):
            pass

        def draw(self, camera_uniforms):
            log.append("app points")

    app.viewport.point_overlay = AppPoints()
    shown = sink(app)
    monkeypatch.setattr(shown._lines, "draw", lambda uniforms: log.append("plane"))
    monkeypatch.setattr(shown._markers, "draw", lambda uniforms: log.append("markers"))
    app.viewport.sync()
    app.viewport.render()
    assert log == ["plane", "markers", "app points"]


def test_sink_look_is_the_lab_legend():
    """PROVISIONAL look, taken over from the Lab README colour legend: light-blue outline with depth
    test, green seam, magenta without partner, white ambiguous, 7 px points; no partner layer."""
    styles = GLSymmetryOverlay.LAYER_STYLES
    assert styles[sink_module.PLANE_LAYER] == ((0.4, 0.75, 1.0, 1.0), 1.0)
    assert styles[SEAM_LAYER] == ((0.2, 0.9, 0.3, 1.0), 7.0)
    assert styles[UNPAIRED_LAYER] == ((0.95, 0.2, 0.85, 1.0), 7.0)
    assert styles[AMBIGUOUS_LAYER] == ((1.0, 1.0, 1.0, 1.0), 7.0)
    assert MARKER_LAYERS == (SEAM_LAYER, UNPAIRED_LAYER, AMBIGUOUS_LAYER)
    assert set(styles) == {
        sink_module.PLANE_LAYER,
        *MARKER_LAYERS,
        *sink_module.PREVIEW_POINT_LAYERS,
        *sink_module.PREVIEW_LINE_LAYERS,
    }
    assert sink_module._PlaneLines.NO_DEPTH_LAYERS == frozenset()


def test_preview_look_is_the_lab_legend():
    """A3: the Re-Symmetrize preview keeps the Lab's colours (values pinned in the Lab at `065508c`):
    blue = moves, light green = seam into the plane, light red = stays; points at the app's selection
    size, lines 1 px without depth test."""
    styles = GLSymmetryOverlay.LAYER_STYLES
    assert styles[sink_module.RESYM_MOVE_LAYER] == ((0.25, 0.5, 1.0, 1.0), SELECTED_POINT_SIZE)
    assert styles[sink_module.RESYM_SEAM_LAYER] == ((0.75, 1.0, 0.1, 1.0), SELECTED_POINT_SIZE)
    assert styles[sink_module.RESYM_KEEP_LAYER] == ((1.0, 0.55, 0.55, 1.0), SELECTED_POINT_SIZE)
    assert styles[sink_module.RESYM_MOVE_LINE_LAYER] == ((0.25, 0.5, 1.0, 1.0), 1.0)
    assert styles[sink_module.RESYM_SEAM_LINE_LAYER] == ((0.75, 1.0, 0.1, 1.0), 1.0)
    assert sink_module._PreviewLines.NO_DEPTH_LAYERS == frozenset(sink_module.PREVIEW_LINE_LAYERS)


# == What is shown ================================================================================


def test_empty_while_symmetry_off():
    app = make_app()
    assert sink(app).segments() == []
    for layer in MARKER_LAYERS:
        assert sink(app).points(layer) == []


@pytest.mark.parametrize("axis", ["X", "Y", "Z"])
def test_plane_outline_lies_in_plane_and_encloses_bounds(axis):
    app = make_app("head_basemesh")
    cycle_to(app, axis)
    app.viewport.sync()
    segments = sink(app).segments()
    assert len(segments) == 4
    points = [p for seg in segments for p in seg]
    i = AXIS_INDEX[axis]
    assert all(p[i] == 0.0 for p in points)
    lo, hi = mesh_bounds(app.scene.mesh)
    for j in (j for j in range(3) if j != i):
        assert min(p[j] for p in points) < lo[j]
        assert max(p[j] for p in points) > hi[j]


@pytest.mark.parametrize(
    "asset,axis,seam,unpaired",
    [
        ("subd_cube", "X", 8, 0),  # 8 seam edges = one ring of 8 vertices
        ("subd_cube", "Y", 0, 26),
        ("man_with_shoes_basemesh", "X", None, 54),
    ],
)
def test_markers_match_the_report(asset, axis, seam, unpaired):
    """Markers = `symmetry_report` (Lab README characterisation, E4: 54 without partner)."""
    app = make_app(asset)
    cycle_to(app, axis)
    app.viewport.sync()
    mesh = app.scene.mesh
    report = symmetry_report(mesh)
    for layer, ids in (
        (SEAM_LAYER, report.seam),
        (UNPAIRED_LAYER, report.unpaired),
        (AMBIGUOUS_LAYER, report.ambiguous),
    ):
        assert sink(app).points(layer) == [mesh.vertex_position(v) for v in sorted(ids)]
    assert len(sink(app).points(UNPAIRED_LAYER)) == unpaired
    if seam is not None:
        assert len(sink(app).points(SEAM_LAYER)) == seam
    assert display(app).report == report


def test_no_partner_markers_in_the_app():
    """S-2: hovering and selecting a paired vertex shows no partner - only the three problem layers
    exist, and they do not change with hover or selection."""
    app = symmetric_app()
    vid = in_state(app, CorrespondenceState.PAIRED)[0]
    before = {layer: sink(app).points(layer) for layer in MARKER_LAYERS}
    click(app, vid)
    app.viewport.sync()
    assert app.selection.vertices == {vid}
    assert {layer: sink(app).points(layer) for layer in MARKER_LAYERS} == before


# == Rebuild (K-3) ================================================================================


def test_rebuild_after_shift_s_via_viewport_notification():
    app = make_app()
    assert app.key_press(SHIFT_S)
    assert not display(app).dirty
    app.viewport.sync()
    assert not display(app).dirty
    assert len(sink(app).segments()) == 4
    assert len(sink(app).points(SEAM_LAYER)) == 8
    cycle_to(app, "Y")
    app.viewport.sync()
    assert sink(app).points(SEAM_LAYER) == []
    assert len(sink(app).points(UNPAIRED_LAYER)) == 26
    cycle_to(app, None)
    app.viewport.sync()
    assert sink(app).segments() == []
    assert all(sink(app).points(layer) == [] for layer in MARKER_LAYERS)


def test_rebuild_after_undo_redo_of_the_definition():
    app = symmetric_app()
    assert app.key_press(CTRL_Z)
    assert not display(app).dirty
    app.viewport.sync()
    assert sink(app).segments() == []
    assert sink(app).points(SEAM_LAYER) == []
    assert app.key_press(CTRL_Y)
    app.viewport.sync()
    assert len(sink(app).segments()) == 4
    assert len(sink(app).points(SEAM_LAYER)) == 8


def test_markers_follow_a_committed_move_and_its_undo_redo():
    app = symmetric_app()
    vid = in_state(app, CorrespondenceState.SEAM)[0]
    before = pos(app, vid)
    click(app, vid)
    drag_w(app)
    app.viewport.sync()
    moved = pos(app, vid)
    assert moved != before
    assert moved in sink(app).points(SEAM_LAYER)
    assert app.key_press(CTRL_Z)
    app.viewport.sync()
    assert before in sink(app).points(SEAM_LAYER) and moved not in sink(app).points(SEAM_LAYER)
    assert app.key_press(CTRL_Y)
    app.viewport.sync()
    assert moved in sink(app).points(SEAM_LAYER)


# == Cost (plan A3) ===============================================================================


def test_hover_and_selection_changes_recompute_nothing():
    app = symmetric_app()
    before = counts(app)
    for vid in visible(app)[:4]:
        app.pointer_motion(*screen(app, vid))
        app.viewport.sync()
    for vid in visible(app)[:3]:
        click(app, vid)
        app.viewport.sync()
    app.selection.clear()
    app.viewport.on_selection_changed()
    app.viewport.sync()
    assert counts(app) == before


@pytest.mark.parametrize("step", ["w_commit", "ctrl_z", "shift_s"])
def test_plane_and_markers_recompute_once_after_a_mesh_change(step):
    app = symmetric_app()
    click(app, in_state(app, CorrespondenceState.PAIRED)[0])
    if step == "ctrl_z":
        drag_w(app)
    app.viewport.sync()
    before = counts(app)
    if step == "w_commit":
        drag_w(app)
    elif step == "ctrl_z":
        assert app.key_press(CTRL_Z)
    else:
        assert app.key_press(SHIFT_S)
    app.viewport.sync()
    assert counts(app) == (before[0] + 1, before[1] + 1)
    report = display(app).report
    assert report == symmetry_report(app.scene.mesh)
    assert sorted(sink(app).points(SEAM_LAYER)) == sorted(pos(app, v) for v in report.seam)


def test_drag_defers_the_report_and_moves_the_markers():
    """While W runs no report and no outline per move; the markers follow anyway; the frame after
    the commit catches up although the commit reports nothing to the viewport (`dirty` stays set)."""
    app = symmetric_app()
    seam = in_state(app, CorrespondenceState.SEAM)[0]
    click(app, seam)
    app.viewport.sync()
    before = counts(app)
    outline = sink(app).segments()
    assert app.key_press(W)
    for step in range(5):
        app.pointer_motion(400 + step, 300, 4.0, 2.0)
        app.viewport.sync()
        assert counts(app) == before
        assert pos(app, seam) in sink(app).points(SEAM_LAYER)
        assert sink(app).segments() == outline
        assert display(app).dirty
    assert app.key_release(W)
    app.viewport.sync()
    assert counts(app) == (before[0] + 1, before[1] + 1)
    assert not display(app).dirty
    assert display(app).report.seam == frozenset(
        v for v, c in vertex_correspondence(app.scene.mesh).items()
        if c.state is CorrespondenceState.SEAM
    )


def test_esc_during_drag_restores_markers_without_a_report_run():
    app = symmetric_app()
    vid = in_state(app, CorrespondenceState.SEAM)[0]
    click(app, vid)
    app.viewport.sync()
    shown = sink(app).points(SEAM_LAYER)
    runs = counts(app)
    assert app.key_press(W)
    app.pointer_motion(400, 300, 12.0, 7.0)
    app.viewport.sync()
    assert sink(app).points(SEAM_LAYER) != shown
    assert app.key_press(ESC)
    app.viewport.sync()
    assert sink(app).points(SEAM_LAYER) == shown
    # Geometry as before the drag: the signature matches again, no new run needed.
    assert counts(app) == runs


def test_definition_change_right_before_arming_is_never_deferred():
    """Only a pure position change is deferred while a transform runs: Shift+S and W right after
    it, without a frame in between -> the next sync shows the new symmetry anyway."""
    app = make_app()
    vid = next(v for v in visible(app) if pos(app, v)[0] > 0.0)
    click(app, vid)
    app.viewport.sync()
    assert app.key_press(SHIFT_S)
    assert app.key_press(W) and app.interaction_owner == "transform"
    app.viewport.sync()
    assert display(app).report.axis == "X"
    assert len(sink(app).segments()) == 4
    assert len(sink(app).points(SEAM_LAYER)) == 8
    assert not display(app).dirty


def test_a_drag_without_symmetry_derives_nothing(monkeypatch):
    """Symmetry off: the display stays empty and costs a drag no geometry signature per move."""
    app = make_app()
    click(app, visible(app)[0])
    app.viewport.sync()
    calls = []
    original = symmetry_display.geometry_signature

    def counting(mesh):
        calls.append(1)
        return original(mesh)

    monkeypatch.setattr(symmetry_display, "geometry_signature", counting)
    assert app.key_press(W)
    for step in range(3):
        app.pointer_motion(400 + step, 300, 4.0, 2.0)
        app.viewport.sync()
    assert app.key_release(W)
    app.viewport.sync()
    assert calls == []
    assert sink(app).segments() == []
    assert app.key_press(SHIFT_S)
    app.viewport.sync()
    assert calls and len(sink(app).segments()) == 4
