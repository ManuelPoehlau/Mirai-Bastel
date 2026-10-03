"""Gespiegelte Partner von Auswahl und Hover, Zeichenreihenfolge und Overlay-Kosten
auf dem App-Pfad (WP-SYM-LAB-03 Slice 2, Inventar #13/#15, Plan A3).

Headless wie `_app_lab_support` (TraceStore, `run_app.build_app_lab`). Auswahl und
Hover entstehen über die öffentlichen Eingänge von `Application` (Klick,
`pointer_motion`), wie im Fenster. Die Partner kommen aus
`mirai.symmetry.mirrored_selection`; die Tests prüfen gegen `vertex_correspondence`,
nicht gegen eine eigene Paarung.
"""

from __future__ import annotations

import pytest

from core import VertexId
from mirai.interaction.input import Input
from mirai.symmetry import CorrespondenceState, vertex_correspondence
from mirai.viewport.picking import pick_nearest_vertex

from symmetry_lab.lab_overlays import (
    AMBIGUOUS_LAYER,
    HOVER_PARTNER_LAYER,
    MIRRORED_VERTEX_COLOR,
    SEAM_LAYER,
    SELECTION_PARTNER_LAYER,
    UNPAIRED_LAYER,
    SymmetryPlaneOverlay,
    SymmetryStateOverlay,
)

from ._app_lab_support import (  # noqa: F401
    HEIGHT,
    WIDTH,
    CTRL_Y,
    CTRL_Z,
    MISS,
    SHIFT_S,
    W,
    click,
    forbid_lab_calls,
    lab_app,
    make_lab,
    press,
    screen,
    visible,
)

KEY_EDGE_MODE = Input("key", "2")
KEY_FACE_MODE = Input("key", "3")
KEY_VERTEX_MODE = Input("key", "1")
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))


def _overlays(lab) -> tuple[SymmetryPlaneOverlay, SymmetryStateOverlay]:
    plane, state = lab.overlays
    return plane, state


def _in_state(app, state) -> list:
    corr = vertex_correspondence(app.scene.mesh)
    return [v for v in visible(app) if corr[v].state is state]


def _first_visible(app, ids):
    """Erster eindeutig anklickbarer Vertex aus `ids` — ohne `visible()` über das
    ganze Mesh (928 Picks mit Verdeckung auf `man_with_shoes_basemesh`)."""
    mesh = app.scene.mesh
    for vid in sorted(ids, key=int):
        sx, sy = screen(app, vid)
        if pick_nearest_vertex(app.camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) == vid:
            return vid
    raise AssertionError("kein sichtbarer Vertex")


def _partner(app, vid):
    return vertex_correspondence(app.scene.mesh)[vid].partner


def _pos(app, vid):
    return app.scene.mesh.vertex_position(vid)


def _hover(app, vid) -> None:
    app.pointer_motion(*screen(app, vid))
    assert app.selection.hovered == vid


def _symmetric(asset: str = "subd_cube"):
    app, lab = make_lab(asset)
    assert press(app, lab, SHIFT_S) and lab.axis == "X"
    app.viewport.sync()
    return app, lab


# -- Partner-Marker -----------------------------------------------------------------


def test_selection_partner_is_shown_turquoise():
    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    vid = _in_state(app, CorrespondenceState.PAIRED)[0]
    partner = _partner(app, vid)
    click(app, *screen(app, vid))
    app.viewport.sync()
    assert app.selection.vertices == {vid}
    assert state.selection_partners == {partner}
    assert state.points(SELECTION_PARTNER_LAYER) == [_pos(app, partner)]
    assert state.LAYER_STYLES[SELECTION_PARTNER_LAYER][0] == MIRRORED_VERTEX_COLOR


def test_hover_partner_is_shown_without_selecting():
    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    app.pointer_motion(*MISS)
    app.viewport.sync()
    vid = _in_state(app, CorrespondenceState.PAIRED)[0]
    _hover(app, vid)
    app.viewport.sync()
    assert app.selection.vertices == set()
    assert state.hover_partners == {_partner(app, vid)}
    assert state.points(HOVER_PARTNER_LAYER) == [_pos(app, _partner(app, vid))]
    assert state.points(SELECTION_PARTNER_LAYER) == []
    assert state.LAYER_STYLES[HOVER_PARTNER_LAYER][0] == MIRRORED_VERTEX_COLOR


def test_seam_vertex_is_its_own_partner_and_gets_no_marker():
    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    seam = _in_state(app, CorrespondenceState.SEAM)[0]
    _hover(app, seam)
    click(app, *screen(app, seam))
    app.viewport.sync()
    assert app.selection.vertices == {seam}
    assert seam in lab.report.seam
    assert state.points(SELECTION_PARTNER_LAYER) == []
    assert state.points(HOVER_PARTNER_LAYER) == []


def test_unpaired_vertex_has_no_partner_marker():
    app, lab = _symmetric("man_with_shoes_basemesh")
    _plane, state = _overlays(lab)
    unpaired = _first_visible(app, lab.report.unpaired)
    _hover(app, unpaired)
    app.viewport.sync()
    assert state.points(HOVER_PARTNER_LAYER) == []
    click(app, *screen(app, unpaired))
    app.viewport.sync()
    assert app.selection.vertices == {unpaired}
    assert state.points(SELECTION_PARTNER_LAYER) == []
    # Sichtbar bleibt er als „ohne Partner" (magenta), nicht als Partner.
    assert _pos(app, unpaired) in state.points(UNPAIRED_LAYER)


def test_selected_partner_is_not_shown_again_as_partner():
    """Beide Seiten ausgewählt: kein Partner-Marker (Auflösung in `mirrored_selection`)."""
    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    vid = next(
        v for v in _in_state(app, CorrespondenceState.PAIRED) if _partner(app, v) in visible(app)
    )
    partner = _partner(app, vid)
    click(app, *screen(app, vid))
    click(app, *screen(app, partner), SHIFT_LMB)
    app.viewport.sync()
    assert app.selection.vertices == {vid, partner}
    assert state.points(SELECTION_PARTNER_LAYER) == []


def test_partners_follow_selection_and_hover_changes():
    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    first, second = _in_state(app, CorrespondenceState.PAIRED)[:2]
    click(app, *screen(app, first))
    app.viewport.sync()
    assert state.selection_partners == {_partner(app, first)}
    click(app, *screen(app, second))
    app.viewport.sync()
    assert state.selection_partners == {_partner(app, second)}
    _hover(app, first)
    app.viewport.sync()
    assert state.hover_partners == {_partner(app, first)}
    app.pointer_motion(*MISS)
    app.viewport.sync()
    assert state.hover_partners == frozenset()
    assert state.points(HOVER_PARTNER_LAYER) == []


def test_partner_follows_w_commit_and_undo_redo():
    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    vid = _in_state(app, CorrespondenceState.PAIRED)[0]
    partner = _partner(app, vid)
    click(app, *screen(app, vid))
    app.viewport.sync()
    before = _pos(app, partner)
    assert press(app, lab, W)
    app.pointer_motion(400, 300, 12.0, 7.0)
    app.viewport.sync()
    assert state.points(SELECTION_PARTNER_LAYER) == [_pos(app, partner)] != [before]
    assert app.key_release(W)
    app.viewport.sync()
    moved = _pos(app, partner)
    assert moved != before
    assert state.selection_partners == {partner}
    assert state.points(SELECTION_PARTNER_LAYER) == [moved]
    assert press(app, lab, CTRL_Z)
    app.viewport.sync()
    assert state.points(SELECTION_PARTNER_LAYER) == [before]
    assert press(app, lab, CTRL_Y)
    app.viewport.sync()
    assert state.points(SELECTION_PARTNER_LAYER) == [moved]


def test_partner_follows_shift_s():
    """X → Y: anderer Partner (bzw. keiner); weiter bis aus: keine Marker."""
    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    vid = _in_state(app, CorrespondenceState.PAIRED)[0]
    click(app, *screen(app, vid))
    _hover(app, vid)
    app.viewport.sync()
    x_partner = _partner(app, vid)
    assert state.selection_partners == {x_partner}
    assert press(app, lab, SHIFT_S) and lab.axis == "Y"
    app.viewport.sync()
    corr = vertex_correspondence(app.scene.mesh)[vid]
    expected = {corr.partner} if corr.state is CorrespondenceState.PAIRED else set()
    assert state.selection_partners == expected
    assert expected != {x_partner}
    for _ in range(2):
        assert press(app, lab, SHIFT_S)
    assert lab.axis is None
    app.viewport.sync()
    assert state.points(SELECTION_PARTNER_LAYER) == []
    assert state.points(HOVER_PARTNER_LAYER) == []


def test_partner_follows_undo_of_shift_s(lab_app):
    """Auswahl vor Shift+S (Undo stellt die Auswahl von vor dem Schritt her)."""
    app, lab = lab_app
    _plane, state = _overlays(lab)
    vid = next(v for v in visible(app) if app.scene.mesh.vertex_position(v)[0] > 0.0)
    click(app, *screen(app, vid))
    assert press(app, lab, SHIFT_S) and lab.axis == "X"
    app.viewport.sync()
    assert state.selection_partners == {_partner(app, vid)} != {None}
    assert press(app, lab, CTRL_Z) and lab.axis is None
    app.viewport.sync()
    assert state.points(SELECTION_PARTNER_LAYER) == []
    assert press(app, lab, CTRL_Y) and lab.axis == "X"
    app.viewport.sync()
    assert state.selection_partners == {_partner(app, vid)}


def test_no_partner_markers_with_symmetry_off(lab_app):
    app, lab = lab_app
    _plane, state = _overlays(lab)
    vid = visible(app)[0]
    _hover(app, vid)
    click(app, *screen(app, vid))
    app.viewport.sync()
    assert lab.axis is None
    assert state.points(SELECTION_PARTNER_LAYER) == []
    assert state.points(HOVER_PARTNER_LAYER) == []


@pytest.mark.parametrize("mode_key", [KEY_EDGE_MODE, KEY_FACE_MODE])
def test_no_partner_markers_in_edge_or_face_mode(mode_key):
    """Plan „Not in any slice": Partner nur im Vertex-Modus. Hover und Auswahl
    sind dort Edge-/Face-IDs (auch ints) — es entsteht kein Marker."""
    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    vid = _in_state(app, CorrespondenceState.PAIRED)[0]
    click(app, *screen(app, vid))
    app.viewport.sync()
    assert state.points(SELECTION_PARTNER_LAYER) != []
    assert press(app, lab, mode_key)
    for x in range(200, 600, 10):  # irgendein Element unter dem Cursor
        app.pointer_motion(float(x), 300.0)
        if app.selection.hovered is not None:
            break
    assert app.selection.hovered is not None
    assert not isinstance(app.selection.hovered, VertexId)
    click(app, *app.camera.project_to_screen((0.0, 0.0, 0.0), 800, 600))
    app.viewport.sync()
    assert state.points(SELECTION_PARTNER_LAYER) == []
    assert state.points(HOVER_PARTNER_LAYER) == []
    assert press(app, lab, KEY_VERTEX_MODE)
    app.viewport.sync()
    # Zurück im Vertex-Modus gilt wieder die Vertex-Auswahl.
    assert state.selection_partners == {
        p for v in app.selection.vertices
        if (p := _partner(app, v)) is not None and p not in app.selection.vertices
    }


# -- Zeichenreihenfolge ---------------------------------------------------------------


def test_partner_layers_are_drawn_after_state_markers():
    assert SymmetryStateOverlay.LAYERS == (
        SEAM_LAYER,
        UNPAIRED_LAYER,
        AMBIGUOUS_LAYER,
        HOVER_PARTNER_LAYER,
        SELECTION_PARTNER_LAYER,
    )


def test_lab_overlays_are_drawn_before_the_app_point_overlay(lab_app, monkeypatch):
    """H1: Ebene, dann Lab-Punkte (Zustand + Partner), dann erst die Punkte der App
    (Hover/Auswahl gelb) — Hover und Auswahl liegen über den Lab-Markern."""
    app, lab = lab_app
    plane, state = _overlays(lab)
    log = []

    class AppPoints:
        def set_points(self, layer, positions):
            pass

        def draw(self, camera_uniforms):
            log.append("app points")

    app.viewport.point_overlay = AppPoints()
    monkeypatch.setattr(plane, "draw", lambda uniforms: log.append("lab plane"))
    monkeypatch.setattr(state, "draw", lambda uniforms: log.append("lab points"))
    app.viewport.sync()
    app.viewport.render()
    assert log == ["lab plane", "lab points", "app points"]


# -- Overlay-Kosten (Plan A3) --------------------------------------------------------


def _counts(lab) -> tuple[int, int]:
    plane, state = _overlays(lab)
    return plane.recomputes, state.recomputes


def test_hover_only_change_does_not_recompute_plane_or_state():
    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    before = _counts(lab)
    partner_runs = state.partner_recomputes
    for vid in visible(app)[:4]:
        _hover(app, vid)
        app.viewport.sync()
    assert _counts(lab) == before
    assert state.partner_recomputes > partner_runs  # nur die Partner folgen dem Hover


def test_hover_and_selection_changes_derive_no_correspondence(monkeypatch):
    """Plan A3 (Referenz-PC: 17 ms je Hover-Wechsel auf `man_with_shoes_basemesh`,
    fast alles in `vertex_correspondence`): die Partner kommen aus der Zuordnung
    des gecachten Befunds, ein Hover- oder Auswahl-Wechsel ordnet das Mesh nicht
    neu zu. Die Partner bleiben dieselben wie bei frischer Ableitung."""
    import mirai.symmetry as symmetry
    import symmetry_lab.lab_symmetry as lab_symmetry

    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    fresh = vertex_correspondence(app.scene.mesh)
    paired = [v for v in visible(app) if fresh[v].state is CorrespondenceState.PAIRED][:4]
    assert paired
    calls = []
    original = symmetry.vertex_correspondence

    def counting(mesh):
        calls.append(1)
        return original(mesh)

    monkeypatch.setattr(symmetry, "vertex_correspondence", counting)
    monkeypatch.setattr(lab_symmetry, "vertex_correspondence", counting)
    for vid in paired:
        _hover(app, vid)
        app.viewport.sync()
        assert state.hover_partners == {fresh[vid].partner}
    click(app, *screen(app, paired[0]))
    app.viewport.sync()
    assert state.selection_partners == {fresh[paired[0]].partner}
    assert calls == []


def test_selection_only_change_does_not_recompute_plane_or_state():
    app, lab = _symmetric()
    before = _counts(lab)
    for vid in visible(app)[:3]:
        click(app, *screen(app, vid))
        app.viewport.sync()
    app.selection.clear()
    app.viewport.on_selection_changed()
    app.viewport.sync()
    assert _counts(lab) == before


def test_hud_reads_the_cached_report_without_recomputing():
    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    report = lab.report
    runs = state.recomputes
    for _ in range(5):
        assert lab.report is report
    assert state.recomputes == runs


@pytest.mark.parametrize("step", ["w_commit", "ctrl_z", "shift_s"])
def test_plane_and_state_recompute_after_mesh_changes(step):
    app, lab = _symmetric()
    plane, state = _overlays(lab)
    vid = _in_state(app, CorrespondenceState.PAIRED)[0]
    click(app, *screen(app, vid))
    if step == "ctrl_z":
        assert press(app, lab, W)
        app.pointer_motion(400, 300, 12.0, 7.0)
        assert app.key_release(W)
    app.viewport.sync()
    before = _counts(lab)
    if step == "w_commit":
        assert press(app, lab, W)
        app.pointer_motion(400, 300, 12.0, 7.0)
        assert app.key_release(W)
    elif step == "ctrl_z":
        assert press(app, lab, CTRL_Z)
    else:
        assert press(app, lab, SHIFT_S)
    app.viewport.sync()
    after = _counts(lab)
    assert after[0] == before[0] + 1 and after[1] == before[1] + 1
    assert lab.report is state.reports.get(app.scene.mesh)
    assert sorted(state.points(SEAM_LAYER)) == sorted(
        _pos(app, v) for v in lab.report.seam
    )


def test_drag_defers_the_report_and_moves_the_markers():
    """Plan A3: während des Drags kein Befund-Lauf und keine Partner-Ableitung je
    Bewegung — die Marker wandern trotzdem mit; der Frame nach dem Commit holt nach,
    obwohl der Commit dem Viewport nichts meldet (`dirty` bleibt gesetzt)."""
    app, lab = _symmetric()
    plane, state = _overlays(lab)
    seam = _in_state(app, CorrespondenceState.SEAM)[0]
    click(app, *screen(app, seam))
    app.viewport.sync()
    before = _counts(lab)
    partner_runs = state.partner_recomputes
    assert press(app, lab, W)
    for step in range(5):
        app.pointer_motion(400 + step, 300, 4.0, 2.0)
        app.viewport.sync()
        assert _counts(lab) == before
        assert state.partner_recomputes == partner_runs
        assert _pos(app, seam) in state.points(SEAM_LAYER)
        assert plane.dirty and state.dirty
    assert app.key_release(W)
    app.viewport.sync()
    assert _counts(lab) == (before[0] + 1, before[1] + 1)
    assert not plane.dirty and not state.dirty
    assert lab.report.seam == frozenset(
        v for v, c in vertex_correspondence(app.scene.mesh).items()
        if c.state is CorrespondenceState.SEAM
    )


def test_esc_during_drag_restores_markers_without_a_report_run():
    app, lab = _symmetric()
    _plane, state = _overlays(lab)
    vid = _in_state(app, CorrespondenceState.PAIRED)[0]
    click(app, *screen(app, vid))
    app.viewport.sync()
    shown = state.points(SELECTION_PARTNER_LAYER)
    runs = _counts(lab)
    assert press(app, lab, W)
    app.pointer_motion(400, 300, 12.0, 7.0)
    app.viewport.sync()
    assert state.points(SELECTION_PARTNER_LAYER) != shown
    assert press(app, lab, Input("key", "ESCAPE"))
    app.viewport.sync()
    assert state.points(SELECTION_PARTNER_LAYER) == shown
    # Geometrie wie vor dem Drag: die Signatur passt wieder, kein neuer Lauf nötig.
    assert _counts(lab) == runs


def test_definition_change_right_before_arming_is_never_deferred(lab_app):
    """Nur eine reine Positionsänderung wird während eines Transforms aufgeschoben:
    Shift+S und gleich danach W, ohne Frame dazwischen → der nächste `sync()` zeigt
    trotzdem die neue Symmetrie (Befund, Ebene, Partner)."""
    app, lab = lab_app
    plane, state = _overlays(lab)
    vid = next(v for v in visible(app) if app.scene.mesh.vertex_position(v)[0] > 0.0)
    click(app, *screen(app, vid))
    app.viewport.sync()
    assert press(app, lab, SHIFT_S)
    assert press(app, lab, W) and app.interaction_owner == "transform"
    app.viewport.sync()
    assert lab.report.axis == "X"
    assert len(plane.segments()) == 4
    assert len(state.points(SEAM_LAYER)) == 8
    assert state.selection_partners == {_partner(app, vid)}
    assert not plane.dirty and not state.dirty
