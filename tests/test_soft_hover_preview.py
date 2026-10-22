"""Soft Selection influence display: hover preview, the two display modes and their visibility
(2026-10-22, `PROVISIONAL`; AD-020 "Hover preview and display modes").

Headless (TraceStore); the sinks are the real `GLSoftBandOverlay` and `GLSoftShadingOverlay`, whose
data side needs no GL context. Pins:

- the preview target: the explicit selection if there is one, else the hovered component (any
  selection mode), else nothing; hover never replaces or mutates the selection;
- a recompute only when the target (or a setting / the mesh) changes, not per pointer move;
- vertex bands and face shading are exclusive; `bands_visible` (Alt+O) hides whichever is active
  without touching Soft itself; the mode key (Alt+Shift+O) is a normal, rebindable binding;
- a running gesture keeps its own weights; the preview resumes for the current state afterwards;
- Symmetry and the influence semantics are the ones of the transform (same functions);
- the shading overlay follows positions, rescans only on a face change, and is cleaned up on
  scene load / Undo.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401  (puts examples/ on sys.path)
from tests.test_application_soft_bands import (
    ALT_O,
    CTRL_O,
    CTRL_Y,
    CTRL_Z,
    ESC,
    KEY_2,
    O,
    SHIFT_O,
    SHIFT_WHEEL_UP,
    W,
    WIDTH,
    HEIGHT,
    _front_vertices,
    _move,
    _screen,
)

from core import VertexId
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.soft_selection import (
    EMPTY_BANDS,
    VIEW_MODES,
    GLSoftBandOverlay,
    GLSoftShadingOverlay,
    SoftBands,
    SoftSettings,
    compute_influence,
    shading_color,
    symmetric_influence,
)
from mirai.symmetry import vertex_correspondence
from mirai.symmetry_axis import set_symmetry_axis

ALT_SHIFT_O = Input("key", "o", frozenset({"alt", "shift"}))
KEY_3 = Input("key", "3")
DELETE = Input("key", "delete")


def _make_app() -> Application:
    app = Application()
    app.init_scene(
        "obj",
        obj_path=HEAD_OBJ,
        soft_overlay_type=GLSoftBandOverlay,
        soft_shading_overlay_type=GLSoftShadingOverlay,
    )
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


@pytest.fixture
def app() -> Application:
    return _make_app()


@pytest.fixture
def influence_calls(monkeypatch) -> list[str]:
    """Every influence computation: the preview (`mirai.application`) and the tools' `begin()`."""
    calls: list[str] = []
    import mirai.application as application_module
    import mirai.interaction.tools.move as move_module
    import mirai.interaction.tools.transform as transform_module

    for module in (application_module, move_module, transform_module):
        original = module.compute_influence

        def spy(mesh, seeds, radius, *args, _where=module.__name__, _original=original, **kwargs):
            calls.append(_where)
            return _original(mesh, seeds, radius, *args, **kwargs)

        monkeypatch.setattr(module, "compute_influence", spy)
    return calls


def _preview_calls(calls) -> int:
    return calls.count("mirai.application")


def _weights(app, seeds) -> dict:
    soft = app.soft_settings
    return compute_influence(
        app.scene.mesh, seeds, soft.world_radius, soft.metric, soft.curve, soft.curve_power
    )


def _bands(app, seeds) -> SoftBands:
    return SoftBands.from_weights(_weights(app, seeds))


def _hover(app, vid: VertexId) -> None:
    x, y = _screen(app, vid)
    app.pointer_motion(x, y, 1.0, 1.0)
    assert app.selection.hovered == vid


def _hover_off_mesh(app) -> None:
    app.pointer_leave()
    assert app.selection.hovered is None


def _select(app, vid: VertexId) -> None:
    x, y = _screen(app, vid)
    assert app.select_at(cmd.SELECT, x, y)
    assert app.selection.vertices == {vid}


def _soft_on(app) -> None:
    assert app.key_press(O) and app.soft_settings.enabled
    assert app.pointer_scroll(SHIFT_WHEEL_UP)  # a larger radius: the field reaches neighbours


def _exclusive(app) -> str:
    """At most one display is non-empty; returns which ('bands', 'faces' or 'none')."""
    bands, shading = app.soft_bands != EMPTY_BANDS, bool(app.soft_shading)
    assert not (bands and shading), "bands and face shading are visible together"
    overlay_bands = app._soft_overlay.bands != EMPTY_BANDS
    overlay_shading = bool(app._soft_shading_overlay.weights)
    assert (bands, shading) == (overlay_bands, overlay_shading), "overlays differ from app state"
    return "bands" if bands else "faces" if shading else "none"


# -- preview target: hover without a selection ------------------------------------------------


def test_hover_without_selection_previews_the_hovered_vertex(app, influence_calls):
    _soft_on(app)
    assert app.soft_bands == EMPTY_BANDS  # nothing hovered, nothing selected
    vid = _front_vertices(app)[0]
    _hover(app, vid)
    assert app.selection.vertices == set()
    assert app.soft_bands == _bands(app, {vid}) and app.soft_bands.count > 0
    assert _preview_calls(influence_calls) == 1


def test_no_valid_hover_target_shows_nothing(app):
    _soft_on(app)
    _hover(app, _front_vertices(app)[0])
    assert _exclusive(app) == "bands"
    _hover_off_mesh(app)
    assert _exclusive(app) == "none"


def test_soft_off_shows_no_hover_preview(app, influence_calls):
    _hover(app, _front_vertices(app)[0])
    assert influence_calls == [] and _exclusive(app) == "none"


@pytest.mark.parametrize("mode_key, kind", [(KEY_2, "edge"), (KEY_3, "face")])
def test_hover_target_follows_the_selection_mode(app, mode_key, kind):
    _soft_on(app)
    assert app.key_press(mode_key)
    mesh = app.scene.mesh
    # Hover the visible element nearest the camera; the component picker decides what is under the cursor.
    eye = app.camera.eye()
    if kind == "edge":
        element = min(
            mesh.all_edge_ids(),
            key=lambda e: sum(
                (a - b) ** 2
                for a, b in zip(_mid(mesh, e), eye)
            ),
        )
        point = app.camera.project_to_screen(_mid(mesh, element), WIDTH, HEIGHT)
        element_vertices = set(mesh.edge_vertices(element))
    else:
        element = min(
            mesh.all_face_ids(),
            key=lambda f: sum((a - b) ** 2 for a, b in zip(_centroid(mesh, f), eye)),
        )
        point = app.camera.project_to_screen(_centroid(mesh, element), WIDTH, HEIGHT)
        element_vertices = set(mesh.face_vertices(element))
    app.pointer_motion(point[0], point[1], 1.0, 1.0)
    hovered = app.selection.hovered
    assert hovered is not None and type(hovered).__name__.lower().startswith(kind)
    vertices = (
        set(mesh.edge_vertices(hovered)) if kind == "edge" else set(mesh.face_vertices(hovered))
    )
    if hovered == element:
        assert vertices == element_vertices
    assert app.soft_bands == _bands(app, vertices)
    # The hovered element's own vertices are the seeds (w = 1), so they carry no band point.
    assert not (vertices & set(app.soft_bands.weights))


def _mid(mesh, edge):
    a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(edge))
    return tuple((p + q) / 2 for p, q in zip(a, b))


def _centroid(mesh, face):
    ps = [mesh.vertex_position(v) for v in mesh.face_vertices(face)]
    return tuple(sum(c) / len(ps) for c in zip(*ps))


# -- preview target: an explicit selection wins -----------------------------------------------


def test_explicit_selection_is_previewed_not_the_hover(app, influence_calls):
    _soft_on(app)
    near = _front_vertices(app)
    selected, other = near[0], near[40]
    _select(app, selected)
    shown = app.soft_bands
    assert shown == _bands(app, {selected})
    influence_calls.clear()

    _hover(app, other)
    assert app.selection.hovered == other  # the ordinary hover highlight is still there
    assert app.selection.vertices == {selected}  # and the selection is untouched
    assert app.soft_bands is shown and influence_calls == []  # no recompute for the hover
    assert app._soft_overlay.pushes == 1  # one push in total


def test_hover_never_changes_the_selection_or_history(app):
    _soft_on(app)
    near = _front_vertices(app)
    _select(app, near[0])
    undo_before = len(app._selection_undo_stack)
    for vid in near[10:14]:
        _hover(app, vid)
    assert app.selection.vertices == {near[0]}
    assert len(app._selection_undo_stack) == undo_before


def test_clearing_the_selection_hands_the_preview_to_the_hover(app):
    _soft_on(app)
    near = _front_vertices(app)
    _select(app, near[0])
    _hover(app, near[30])
    assert app.soft_bands == _bands(app, {near[0]})
    app.selection.clear()
    app.viewport.on_selection_changed()
    app._soft_preview_refresh()  # the trigger every selection change runs
    assert app.soft_bands == _bands(app, {near[30]})


# -- when the preview recomputes ---------------------------------------------------------------


def test_pointer_motion_over_the_same_component_does_not_recompute(app, influence_calls):
    _soft_on(app)
    vid = _front_vertices(app)[0]
    _hover(app, vid)
    assert _preview_calls(influence_calls) == 1
    x, y = _screen(app, vid)
    for dx in (1.0, 2.0, -1.0):
        app.pointer_motion(x + dx * 0.2, y, dx, 0.0)
    assert app.selection.hovered == vid
    assert _preview_calls(influence_calls) == 1

    _hover(app, _front_vertices(app)[25])  # a different component: one more
    assert _preview_calls(influence_calls) == 2


@pytest.mark.parametrize(
    "press, check",
    [
        (lambda a: a.pointer_scroll(SHIFT_WHEEL_UP), lambda s: s.radius_step),
        (lambda a: a.key_press(SHIFT_O), lambda s: s.curve),
        (lambda a: a.key_press(CTRL_O), lambda s: s.metric),
    ],
    ids=["radius", "curve", "metric"],
)
def test_settings_changes_update_the_hover_preview(app, influence_calls, press, check):
    _soft_on(app)
    vid = _front_vertices(app)[0]
    _hover(app, vid)
    before = (check(app.soft_settings), app.soft_bands)
    influence_calls.clear()
    assert press(app)
    assert check(app.soft_settings) != before[0]
    assert _preview_calls(influence_calls) == 1
    assert app.soft_bands == _bands(app, {vid}) != before[1]


def test_toggling_soft_clears_and_restores_the_hover_preview(app):
    _soft_on(app)
    vid = _front_vertices(app)[0]
    _hover(app, vid)
    assert app.key_press(O)  # off
    assert _exclusive(app) == "none"
    assert app.key_press(O)  # on again: the hover is still there
    assert app.soft_bands == _bands(app, {vid})


# -- display modes and visibility --------------------------------------------------------------


def test_default_display_is_vertex_bands(app):
    assert app.soft_settings.view_mode == "bands" == VIEW_MODES[0]
    assert app.soft_settings.bands_visible


def test_mode_key_switches_between_bands_and_faces_exclusively(app):
    _soft_on(app)
    vid = _front_vertices(app)[0]
    _hover(app, vid)
    weights = _weights(app, {vid})
    assert _exclusive(app) == "bands"

    assert app.key_press(ALT_SHIFT_O)
    assert app.soft_settings.view_mode == "faces"
    assert _exclusive(app) == "faces"
    assert app.soft_shading == weights  # the seeds too: the shading needs w = 1
    assert "faces on" in app.status_message

    assert app.key_press(ALT_SHIFT_O)
    assert app.soft_settings.view_mode == "bands"
    assert _exclusive(app) == "bands" and app.soft_bands == _bands(app, {vid})
    assert app.soft_shading == {}


def test_mode_switch_recomputes_the_hover_preview_once(app, influence_calls):
    _soft_on(app)
    _hover(app, _front_vertices(app)[0])
    influence_calls.clear()
    assert app.key_press(ALT_SHIFT_O)
    assert _preview_calls(influence_calls) == 1


@pytest.mark.parametrize("mode_presses", [0, 1], ids=["bands", "faces"])
def test_hiding_keeps_soft_working_and_leaves_no_preview(app, influence_calls, mode_presses):
    _soft_on(app)
    for _ in range(mode_presses):
        assert app.key_press(ALT_SHIFT_O)
    near = _front_vertices(app)
    selected = near[0]
    _select(app, selected)
    assert _exclusive(app) != "none"

    assert app.key_press(ALT_O)  # hide
    assert not app.soft_settings.bands_visible and app.soft_settings.enabled
    assert _exclusive(app) == "none"
    influence_calls.clear()
    _hover(app, near[40])
    assert _preview_calls(influence_calls) == 0 and _exclusive(app) == "none"

    # Soft still drives the transform: a vertex in the falloff moves, with weights < 1.
    neighbour = next(v for v, w in _weights(app, {selected}).items() if 0.0 < w < 1.0)
    before = app.scene.mesh.vertex_position(neighbour)
    stack = len(app.history._undo_stack) if hasattr(app.history, "_undo_stack") else None
    selection_before = set(app.selection.vertices)
    assert app.key_press(W)
    _move(app)
    weights = app.tool_manager.active_tool.operation.context.params["influence"]
    assert 0.0 < weights[neighbour] < 1.0
    assert _exclusive(app) == "none"  # the gesture has nothing to show while hidden
    assert app.key_release(W)
    assert app.scene.mesh.vertex_position(neighbour) != before
    assert app.selection.vertices == selection_before
    assert _exclusive(app) == "none"
    if stack is not None:
        assert len(app.history._undo_stack) == stack + 1

    assert app.key_press(ALT_O)  # show again, in the mode that was active
    assert _exclusive(app) == ("faces" if mode_presses else "bands")


def test_mode_switch_while_hidden_stays_hidden_and_applies_when_shown(app):
    _soft_on(app)
    _select(app, _front_vertices(app)[0])
    assert app.key_press(ALT_O) and _exclusive(app) == "none"
    assert app.key_press(ALT_SHIFT_O) and _exclusive(app) == "none"
    assert app.key_press(ALT_O) and _exclusive(app) == "faces"


def test_view_state_is_not_history_or_scene_state(app):
    _soft_on(app)
    _select(app, _front_vertices(app)[0])
    undo = len(app._selection_undo_stack)
    before = app.scene.mesh.export_state()
    assert app.key_press(ALT_SHIFT_O) and app.key_press(ALT_O)
    assert len(app._selection_undo_stack) == undo
    assert app.scene.mesh.export_state() == before
    assert not app.history.can_undo() or app.history.undo_description() != "SoftViewModeCycle"


def test_status_text_names_the_active_mode():
    s = SoftSettings()
    assert s.status_text().endswith("bands on · mono")
    faces = s.with_next_view_mode()
    assert faces.view_mode == "faces" and faces.status_text().endswith("faces on · mono")
    assert faces.with_bands_toggled().status_text().endswith("faces off · mono")
    assert faces.with_next_view_mode() == s
    with pytest.raises(ValueError):
        SoftSettings(view_mode="dots")


def test_mode_binding_is_provisional_and_rebindable():
    bindings = build_default_bindings()
    assert bindings.command_for(ALT_SHIFT_O) == cmd.SOFT_VIEW_MODE_CYCLE
    assert bindings.command_for(ALT_O) == cmd.SOFT_BANDS_TOGGLE  # unchanged
    bindings.set_default(Input("key", "m", frozenset({"alt"})), cmd.SOFT_VIEW_MODE_CYCLE)
    assert bindings.command_for(Input("key", "m", frozenset({"alt"}))) == cmd.SOFT_VIEW_MODE_CYCLE


# -- a running gesture owns the display ---------------------------------------------------------


@pytest.mark.parametrize("mode_presses", [0, 1], ids=["bands", "faces"])
def test_gesture_weights_stay_stable_then_follow_the_new_state(app, influence_calls, mode_presses):
    _soft_on(app)
    for _ in range(mode_presses):
        assert app.key_press(ALT_SHIFT_O)
    near = _front_vertices(app)
    selected, elsewhere = near[0], near[40]
    _select(app, selected)
    assert app.key_press(W)
    _move(app)
    gesture = dict(app.tool_manager.active_tool.operation.context.params["influence"])
    shown = lambda: app.soft_shading if mode_presses else dict(app.soft_bands.weights)  # noqa: E731
    expected = gesture if mode_presses else {v: w for v, w in gesture.items() if 0.0 < w < 1.0}
    assert shown() == expected

    # The hover moving mid-gesture, and a mode switch, must not change what the gesture shows.
    influence_calls.clear()
    app._set_hovered(elsewhere)
    assert app.key_press(ALT_SHIFT_O)
    assert influence_calls == [] and shown() == expected

    assert app.key_release(W)  # commit: the preview is recomputed for the new state
    assert app.selection.vertices == {selected}
    assert _exclusive(app) == ("bands" if mode_presses else "faces")  # the switch applied at the end
    now = app.soft_bands.weights if mode_presses else app.soft_shading
    fresh = _weights(app, {selected})
    assert now == ({v: w for v, w in fresh.items() if 0.0 < w < 1.0} if mode_presses else fresh)


def test_preview_resumes_after_cancel_and_undo(app):
    _soft_on(app)
    selected = _front_vertices(app)[0]
    _select(app, selected)
    pre = app.soft_bands
    assert app.key_press(W)
    _move(app)
    assert app.key_press(ESC)  # cancel
    assert app.soft_bands == pre == _bands(app, {selected})

    assert app.key_press(W)
    _move(app)
    assert app.key_release(W)
    committed = app.soft_bands
    assert committed == _bands(app, {selected}) != pre
    assert app.key_press(CTRL_Z)
    assert app.soft_bands == pre
    assert app.key_press(CTRL_Y)
    assert app.soft_bands == committed


def test_hover_armed_gesture_keeps_its_target_then_follows_the_hover(app):
    _soft_on(app)
    near = _front_vertices(app)
    _hover(app, near[0])
    assert app.key_press(W)  # armed on the hovered vertex
    _move(app)
    gesture = dict(app.tool_manager.active_tool.operation.context.params["influence"])
    assert {v: w for v, w in gesture.items() if 0.0 < w < 1.0} == dict(app.soft_bands.weights)
    app._set_hovered(near[40])  # must not retarget the running gesture
    assert {v: w for v, w in gesture.items() if 0.0 < w < 1.0} == dict(app.soft_bands.weights)
    assert app.key_release(W)
    hovered = app.selection.hovered
    assert app.soft_bands == (EMPTY_BANDS if hovered is None else _bands(app, {hovered}))


# -- Symmetry: the same field as the transform ----------------------------------------------------


def test_hover_preview_under_symmetry_is_the_symmetric_field(app):
    set_symmetry_axis(app.scene.mesh, "X")
    app.viewport.on_topology_changed()
    mesh = app.scene.mesh
    paired = [v for v, c in vertex_correspondence(mesh).items() if c.state.name == "PAIRED"]
    vid = min(paired)
    _soft_on(app)
    assert app.pointer_scroll(SHIFT_WHEEL_UP)
    assert app.key_press(ALT_SHIFT_O)  # face shading shows the same field
    app._set_hovered(vid)
    soft = app.soft_settings
    field = symmetric_influence(
        mesh, {vid}, soft.world_radius, metric=soft.metric, curve=soft.curve,
        curve_power=soft.curve_power,
    )
    assert app.soft_shading == dict(field.weights)
    assert len(app.soft_shading) > len(_weights_plain(app, {vid}))  # both sides, more than plain Soft
    assert app.key_press(ALT_SHIFT_O)
    assert app.soft_bands == SoftBands.from_weights(field.weights)


def _weights_plain(app, seeds):
    soft = app.soft_settings
    return compute_influence(
        app.scene.mesh, seeds, soft.world_radius, soft.metric, soft.curve, soft.curve_power
    )


# -- cleanup after scene / topology changes and Undo ----------------------------------------------


def test_scene_load_clears_a_hover_preview_in_both_modes(app):
    _soft_on(app)
    assert app.key_press(ALT_SHIFT_O)
    _hover(app, _front_vertices(app)[0])
    assert _exclusive(app) == "faces"
    app.load_scene(
        "obj", obj_path=HEAD_OBJ, soft_overlay_type=GLSoftBandOverlay,
        soft_shading_overlay_type=GLSoftShadingOverlay,
    )
    assert app.selection.hovered is None
    assert _exclusive(app) == "none"
    assert app.viewport.extra_overlays == [app._soft_overlay, app._soft_shading_overlay]
    assert app.soft_settings.view_mode == "faces"  # the view choice is sticky, like the other settings


def test_topology_change_and_undo_keep_the_shading_current(app):
    """A face removed next to the selection leaves the weights as they were, so only the overlay's
    `MeshWatch` can tell it to rescan; Undo brings the face (and its shading) back."""
    _soft_on(app)
    assert app.key_press(ALT_SHIFT_O)
    mesh = app.scene.mesh
    vid = _front_vertices(app)[0]
    _select(app, vid)
    overlay = app._soft_shading_overlay
    app.update_viewport(0.016)
    scans, before, weights = overlay.scans, overlay.triangles(), app.soft_shading
    face = next(f for f in mesh.all_face_ids() if vid in mesh.face_vertices(f))
    assert before

    assert app.apply_mesh_change("remove face", lambda: mesh.remove_face(face) and None)
    app.update_viewport(0.016)
    assert not mesh.is_valid_face(face)
    assert overlay.scans == scans + 1  # a face change makes the overlay rescan
    after = overlay.triangles()
    assert len(after) < len(before)
    assert app.soft_shading == _weights(app, {vid}) and _exclusive(app) == "faces"
    assert weights == app.soft_shading  # unchanged weights: the watch alone triggered the rescan

    assert app.key_press(CTRL_Z)
    app.update_viewport(0.016)
    assert mesh.is_valid_face(face)
    assert overlay.triangles() == before
    assert app.key_press(CTRL_Y)
    app.update_viewport(0.016)
    assert overlay.triangles() == after


# -- the shading overlay (data side) -----------------------------------------------------------------


def test_shading_overlay_follows_positions_and_rescans_only_on_faces(app):
    _soft_on(app)
    assert app.key_press(ALT_SHIFT_O)
    vid = _front_vertices(app)[0]
    _select(app, vid)
    overlay = app._soft_shading_overlay
    app.update_viewport(0.016)
    assert overlay.scans == 1 and overlay.triangles() and overlay.colors()
    assert len(overlay.colors()) // 4 == len(overlay.triangles()) // 3  # one RGBA per corner

    scans = overlay.scans
    _hover(app, _front_vertices(app)[30])  # a hover sync: the cached triangles are reused
    app.update_viewport(0.016)
    assert overlay.scans == scans

    positions = overlay.triangles()
    assert app.key_press(W)
    _move(app)
    app.update_viewport(0.016)
    assert overlay.scans == scans  # a drag moves the corners, no face scan
    assert overlay.triangles() != positions
    assert app.key_release(W)


def test_shading_color_is_translucent_and_grows_with_the_weight():
    assert shading_color(0.0)[3] == 0.0 and shading_color(-0.5)[3] == 0.0
    alphas = [shading_color(w)[3] for w in (0.05, 0.25, 0.5, 0.75, 1.0)]
    assert alphas == sorted(alphas) and 0.0 < alphas[0] < alphas[-1] <= 0.5
    # strong = warm (red high), weak = cold (blue high), like the band colours
    assert shading_color(1.0)[0] > shading_color(1.0)[2] and shading_color(0.05)[2] > shading_color(0.05)[0]


def test_shading_overlay_declares_it_is_drawn_under_the_highlights():
    assert GLSoftShadingOverlay.DRAW_UNDER_HIGHLIGHTS is True
    assert not getattr(GLSoftBandOverlay, "DRAW_UNDER_HIGHLIGHTS", False)
