"""Gespiegelter Knife im Lab-Fenster (Handoff Slice 7 §2 A8/A12/A13, E23–E30, §7).

Echte Production-`Application`, -`OrbitCamera` und `mirai.viewport.picking`
(über `lab_knife_pick`), Dispatcher, kein GL-Kontext. Positionen werden exakt
verglichen (A5: keine Toleranz). Screen-Punkte für ein bestimmtes Ziel werden
per Projektion gesucht und mit `knife_pick` bestätigt — Picking ist
verdeckungsfrei, eine Projektion allein garantiert das Ziel nicht.
"""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.interaction.input import Input
from mirai.symmetry import SymmetryState, mirror_position, symmetry_state

from symmetry_lab import lab_draw_data
from symmetry_lab.lab_bindings import apply_lab_bindings
from symmetry_lab.lab_dispatch import KNIFE_HINT, PREVIEW_HINT, Change, LabDispatcher
from symmetry_lab.lab_knife import CHECK_POSITION, LabKnifeTool, edge_between
from symmetry_lab.lab_knife_pick import ENDPOINT_THRESHOLD, knife_pick
from symmetry_lab.lab_knife_preview import (
    REASON_SEAM_CHORD,
    KnifeHoverPreview,
    edge_point,
    knife_hover_preview,
)
from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_status import knife_text, status_text
from symmetry_lab.lab_symmetry import current_axis, definition_for_axis, symmetry_report

from ._pyglet_headless import import_pyglet
from .test_lab_knife import content, plus_quad, quad_edges, seam_quad

W, H = 1280, 800
C = Input("key", "c")
M = Input("key", "m")
Q = Input("key", "q")
ESC = Input("key", "ESCAPE")
SHIFT_S = Input("key", "s", frozenset({"shift"}))
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))
LMB = Input("mouse", "LEFT")
ALT_LMB = Input("mouse", "LEFT", frozenset({"alt"}))
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))
MMB = Input("mouse", "MIDDLE")
WHEEL_UP = Input("wheel", "UP")
PLANE = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))


# -- Hilfen --------------------------------------------------------------------------


def make_app(asset: str = "subd_cube", axis: str | None = "X") -> Application:
    app = Application()
    apply_lab_bindings(app.bindings)
    load_asset_into(app, asset)
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition_for_axis(mesh, axis)
    return app


def start(app: Application) -> LabDispatcher:
    dispatcher = LabDispatcher(app, W, H)
    assert dispatcher.key(C) is True
    assert dispatcher.knife_active, dispatcher.message
    dispatcher.take_changes()
    return dispatcher


def pick(app, xy) -> dict:
    return knife_pick(app.camera, app.scene.mesh, xy[0], xy[1], W, H)


def to_screen(app, p):
    xy = app.camera.project_to_screen(p, W, H)
    assert xy is not None
    return xy


def vertex_xy(app, vid):
    xy = to_screen(app, app.scene.mesh.vertex_position(vid))
    assert pick(app, xy) == {"kind": "vertex", "vertex_id": vid}
    return xy


def edge_xy(app, eid):
    """Screen-Punkt, den `knife_pick` als diese Edge (nicht als Vertex) auflöst."""
    for t in (0.5, 0.4, 0.6, 0.3, 0.7):
        xy = to_screen(app, edge_point(app.scene.mesh, eid, t))
        target = pick(app, xy)
        if target["kind"] == "edge" and target["edge_id"] == eid:
            return xy
    return None


def any_edge_xy(app, edges):
    for eid in edges:
        xy = edge_xy(app, eid)
        if xy is not None:
            return eid, xy
    raise AssertionError("keine der Edges ist per Screen-Punkt erreichbar")


def face_xy(app):
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids(), key=int):
        ps = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
        centroid = tuple(sum(c) / len(ps) for c in zip(*ps))
        xy = app.camera.project_to_screen(centroid, W, H)
        if xy is not None and pick(app, xy)["kind"] == "face":
            return xy
    raise AssertionError("kein Face-Treffer")


OUTSIDE = (3.0, 3.0)


def click(dispatcher, xy):
    dispatcher.press(LMB)
    dispatcher.release("LEFT", *xy)


def plus_x(mesh, eid) -> bool:
    return all(mesh.vertex_position(v)[0] > 0 for v in mesh.edge_vertices(eid))


def next_edges(mesh, s):
    """Edges einer Face am Start, nicht am Start, beide Endpunkte auf +X."""
    faces = {f for e in mesh.vertex_edges(s) for f in mesh.edge_faces(e)}
    result = []
    for f in sorted(faces, key=int):
        vs = mesh.face_vertices(f)
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            eid = edge_between(mesh, a, b)
            if s not in (a, b) and plus_x(mesh, eid) and eid not in result:
                result.append(eid)
    return result


def mirror(p):
    return mirror_position(p, *PLANE)


# -- Binding und Start (E23, E24) --------------------------------------------------


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_c_starts_mirrored_knife_on_valid_two_sides(asset):
    app = make_app(asset)
    dispatcher = LabDispatcher(app, W, H)
    assert dispatcher.key(C) is True
    assert dispatcher.knife_active and dispatcher.knife.mirrored
    changes = dispatcher.take_changes()
    assert Change.HOVER in changes and Change.STATUS in changes
    assert "Knife: aktiv (kein Start)" in status_text(app, asset, dispatcher, symmetry_report(app.scene.mesh))


def test_c_with_symmetry_off_starts_unmirrored_session():
    app = make_app(axis=None)
    dispatcher = start(app)
    assert not dispatcher.knife.mirrored
    assert knife_text(dispatcher) == "Knife: aktiv (kein Start, ungespiegelt)"


@pytest.mark.parametrize("asset,axis", [("man_with_shoes_basemesh", "X"), ("subd_cube", "Y")])
def test_c_rejected_unless_valid_with_two_sides(asset, axis):
    app = make_app(asset, axis)
    before = content(app.scene.mesh)
    dispatcher = LabDispatcher(app, W, H)
    assert dispatcher.key(C) is True
    assert not dispatcher.knife_active
    assert "Knife nicht gestartet" in dispatcher.message
    assert content(app.scene.mesh) == before
    assert dispatcher.take_changes() == Change.STATUS


def test_c_rejected_while_move_armed_or_dragging():
    app = make_app()
    dispatcher = LabDispatcher(app, W, H)
    app.scene.selection.set({app.scene.mesh.all_vertex_ids()[0]})
    dispatcher.key(Q)
    dispatcher.key(C)
    assert not dispatcher.knife_active
    assert "nicht während Move (scharf)" in dispatcher.message
    dispatcher.press(LMB)
    dispatcher.drag(6, 2)
    dispatcher.key(C)
    assert not dispatcher.knife_active
    assert "nicht während Move (zieht)" in dispatcher.message
    dispatcher.key(ESC)


def test_c_rejected_while_resymmetrize_preview_open():
    app = make_app()
    dispatcher = LabDispatcher(app, W, H)
    app.scene.selection.set({app.scene.mesh.all_vertex_ids()[0]})
    dispatcher.key(M)
    assert dispatcher.resym_plan is not None
    assert dispatcher.key(C) is True
    assert not dispatcher.knife_active
    assert dispatcher.message == PREVIEW_HINT
    assert dispatcher.resym_plan is not None


def test_c_rejected_when_session_already_runs():
    app = make_app()
    dispatcher = start(app)
    knife = dispatcher.knife
    assert dispatcher.key(C) is True
    assert dispatcher.knife is knife
    assert dispatcher.message == "Knife: läuft bereits"


def test_move_and_resym_are_rejected_during_session():
    # Umgekehrte Richtung: Q/M während der Session sind ignoriert (E24).
    app = make_app()
    app.scene.selection.set({app.scene.mesh.all_vertex_ids()[0]})
    dispatcher = start(app)
    for inp in (Q, M):
        assert dispatcher.key(inp) is True
        assert dispatcher.message == KNIFE_HINT
    assert dispatcher.resym_plan is None
    assert dispatcher.move_state.value == "bereit"


# -- Dry-Run-Vorschau (E28) --------------------------------------------------------


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_hover_over_plus_x_edge_previews_exactly_what_the_click_creates(asset):
    app = make_app(asset)
    mesh = app.scene.mesh
    dispatcher = start(app)
    e1, _ = quad_edges(mesh, plus_quad(mesh))
    candidates = [e1] + [e for e in mesh.all_edge_ids() if plus_x(mesh, e)]
    eid, xy = any_edge_xy(app, candidates)

    dispatcher.motion(*xy)
    hover = dispatcher.knife_hover
    assert Change.HOVER in dispatcher.take_changes()
    assert hover.target["kind"] == "edge" and hover.target["edge_id"] == eid
    assert hover.resolvable and hover.clickable and hover.reason is None
    assert hover.mirror_position == mirror(hover.source_position)

    click(dispatcher, xy)
    knife = dispatcher.knife
    assert dispatcher.message == "Knife: Schritt angenommen"
    n = knife.start
    n2 = knife.intent_pairs[n]
    # Vorschau == echter Split, bitgenau (sonst zeigt die Vorschau etwas anderes).
    assert mesh.vertex_position(n) == hover.source_position
    assert mesh.vertex_position(n2) == hover.mirror_position
    assert knife_text(dispatcher) == f"Knife: aktiv (Start v{int(n)})"


def _sweep(knife, mesh, targets):
    """Vorschau vs. echter Klick für jedes Ziel; jeder angenommene Klick wird
    per In-Session-Undo zurückgenommen. Rückgabe: (angenommen, nur Klick abgelehnt)."""
    accepted = click_only_rejected = 0
    for target in targets:
        preview = knife_hover_preview(knife, target)
        path_before = knife.path_edges
        ok = knife.click(target)
        if not preview.clickable:
            assert not ok, (target, preview.reason)
            continue
        if not ok:
            click_only_rejected += 1  # Connect/Validierung: nicht Teil von E28
            continue
        accepted += 1
        if target["kind"] == "edge":
            n = knife.start
            assert mesh.vertex_position(n) == preview.source_position
            if preview.mirror_position is None:
                assert knife.intent_pairs[n] == n
            else:
                assert mesh.vertex_position(knife.intent_pairs[n]) == preview.mirror_position
        if preview.mirror_position is not None and len(knife.path_edges) > len(path_before) + 1:
            mirror_edge = knife.path_edges[-1]
            ends = [mesh.vertex_position(v) for v in mesh.edge_vertices(mirror_edge)]
            assert preview.mirror_position in ends
        assert knife.undo_step()
    return accepted, click_only_rejected


@pytest.mark.parametrize("asset,stride", [("subd_cube", 1), ("head_basemesh", 7)])
def test_preview_matches_click_for_every_first_edge_target(asset, stride):
    app = make_app(asset)
    mesh = app.scene.mesh
    knife = start(app).knife
    edges = sorted(mesh.all_edge_ids(), key=int)[::stride]
    accepted, rejected = _sweep(knife, mesh, [{"kind": "edge", "edge_id": e, "t": 0.3} for e in edges])
    assert accepted == len(edges) and rejected == 0


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_preview_matches_click_for_second_targets_around_the_start(asset):
    app = make_app(asset)
    mesh = app.scene.mesh
    knife = start(app).knife
    e1, _ = quad_edges(mesh, plus_quad(mesh))
    assert knife.click({"kind": "edge", "edge_id": e1, "t": 0.3})
    s = knife.start
    faces = {f for e in mesh.vertex_edges(s) for f in mesh.edge_faces(e)}
    targets = []
    for f in sorted(faces, key=int):
        vs = mesh.face_vertices(f)
        targets += [{"kind": "vertex", "vertex_id": v} for v in vs]
        targets += [
            {"kind": "edge", "edge_id": edge_between(mesh, vs[i], vs[(i + 1) % len(vs)]), "t": 0.6}
            for i in range(len(vs))
        ]
    accepted, _ = _sweep(knife, mesh, targets)
    assert accepted >= 2


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_hover_over_seam_edge_has_no_mirror_point(asset):
    app = make_app(asset)
    mesh = app.scene.mesh
    knife = start(app).knife
    seam_edge = min(mesh.symmetry_definition.seam_edges, key=int)
    preview = knife_hover_preview(knife, {"kind": "edge", "edge_id": seam_edge, "t": 0.37})
    assert preview.resolvable and preview.clickable
    assert preview.mirror_position is None and preview.reason is None
    assert preview.source_position[0] == 0.0
    assert knife.click({"kind": "edge", "edge_id": seam_edge, "t": 0.37})
    assert mesh.vertex_position(knife.start) == preview.source_position


def test_seam_chord_is_blocked_before_the_click():
    app = make_app()
    mesh = app.scene.mesh
    knife = start(app).knife
    seam = mesh.symmetry_definition.seam_edges
    _, seam_edge, _ = seam_quad(mesh)
    s1, _s2 = mesh.edge_vertices(seam_edge)
    assert knife.click({"kind": "vertex", "vertex_id": s1})
    other_seam_edge = next(e for e in sorted(seam, key=int) if s1 not in mesh.edge_vertices(e))
    other_seam_vertex = mesh.edge_vertices(other_seam_edge)[0]
    for target in (
        {"kind": "vertex", "vertex_id": other_seam_vertex},
        {"kind": "edge", "edge_id": other_seam_edge, "t": 0.5},
    ):
        preview = knife_hover_preview(knife, target)
        assert not preview.resolvable and not preview.clickable
        assert preview.reason == REASON_SEAM_CHORD and preview.mirror_position is None
        assert knife.click(target) is False
        if target["kind"] == "vertex":
            assert REASON_SEAM_CHORD in knife.last_message
        # Edge: der echte Klick prüft „teilt keine Face" vor der Seam-Sehne (E28
        # deckt nur Letztere ab) — beide sperren, der Grundtext kann abweichen.


def test_slice6_observation_existing_mirror_point_previews_ok_but_click_rejects():
    """§7 Schritt 6 / Slice-6-Befund: nach a → m (m auf der Seam) ist der
    Spiegelpartner von a' auflösbar (a) — die Vorschau zeigt ihn. Abgelehnt
    wird erst der Klick, weil m–a' schon existiert; das prüft E28 nicht."""
    app = make_app()
    mesh = app.scene.mesh
    knife = start(app).knife
    _, seam_edge, opposite = seam_quad(mesh)
    assert knife.click({"kind": "edge", "edge_id": opposite, "t": 0.3})
    a = knife.start
    a2 = knife.intent_pairs[a]
    assert knife.click({"kind": "edge", "edge_id": seam_edge, "t": 0.5})
    preview = knife_hover_preview(knife, {"kind": "vertex", "vertex_id": a2})
    assert preview.clickable and preview.mirror_position == mesh.vertex_position(a)
    assert knife.click({"kind": "vertex", "vertex_id": a2}) is False
    assert "existiert bereits" in knife.last_message


def test_unresolvable_partner_is_blocked_with_reason(monkeypatch):
    app = make_app()
    mesh = app.scene.mesh
    dispatcher = start(app)
    knife = dispatcher.knife
    eid, xy = any_edge_xy(app, [e for e in mesh.all_edge_ids() if plus_x(mesh, e)])
    a, _ = mesh.edge_vertices(eid)
    real_partner = LabKnifeTool.partner
    monkeypatch.setattr(
        LabKnifeTool, "partner", lambda self, v: None if v == a else real_partner(self, v)
    )
    dispatcher.motion(*xy)
    hover = dispatcher.knife_hover
    assert not hover.resolvable and hover.mirror_position is None
    assert hover.reason == f"kein Spiegelpartner für v{int(a)} (INV-5)"
    assert f"Ziel: {hover.reason}" in knife_text(dispatcher)
    before = content(mesh)
    click(dispatcher, xy)
    assert "Spiegelpartner" in dispatcher.message
    assert content(mesh) == before and knife.start is None


def test_edge_at_start_is_invalid_target():
    app = make_app()
    mesh = app.scene.mesh
    knife = start(app).knife
    v = mesh.all_vertex_ids()[0]
    assert knife.click({"kind": "vertex", "vertex_id": v})
    preview = knife_hover_preview(knife, {"kind": "edge", "edge_id": mesh.vertex_edges(v)[0], "t": 0.5})
    assert not preview.valid and not preview.clickable


def test_face_and_outside_have_no_preview():
    app = make_app()
    knife = start(app).knife
    assert knife_hover_preview(knife, {"kind": "face", "face_id": 0}) is None
    assert knife_hover_preview(knife, {"kind": "outside"}) is None
    assert knife_hover_preview(knife, None) is None


def test_unmirrored_preview_has_no_mirror_point():
    app = make_app(axis=None)
    mesh = app.scene.mesh
    knife = start(app).knife
    eid = mesh.all_edge_ids()[0]
    preview = knife_hover_preview(knife, {"kind": "edge", "edge_id": eid, "t": 0.3})
    assert preview.clickable and preview.mirror_position is None
    assert knife.click({"kind": "edge", "edge_id": eid, "t": 0.3})
    assert mesh.vertex_position(knife.start) == preview.source_position


# -- Klick-Routing, Commit, Cancel (E24, E25, E29, A12) -------------------------------


def test_click_outside_without_cut_ends_session_without_history():
    app = make_app()
    dispatcher = start(app)
    assert pick(app, OUTSIDE)["kind"] == "outside"
    click(dispatcher, OUTSIDE)
    assert not dispatcher.knife_active
    assert dispatcher.message == "Knife — keine Schnitte"
    assert not app.history.can_undo()
    assert Change.MESH in dispatcher.take_changes()
    assert knife_text(dispatcher) == ""


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_vertex_edge_outside_commits_one_history_entry(asset):
    app = make_app(asset)
    mesh = app.scene.mesh
    before = content(mesh)
    dispatcher = start(app)
    e1, _ = quad_edges(mesh, plus_quad(mesh))
    vertex_start = mesh.edge_vertices(e1)[0]
    click(dispatcher, vertex_xy(app, vertex_start))
    assert dispatcher.message == "Knife: Schritt angenommen"
    assert dispatcher.knife.start == vertex_start
    eid, xy = any_edge_xy(app, next_edges(mesh, vertex_start))
    click(dispatcher, xy)
    assert dispatcher.message == "Knife: Schritt angenommen", dispatcher.message
    assert len(dispatcher.knife.path_edges) == 2  # beide Seiten
    assert symmetry_state(mesh) is SymmetryState.VALID
    after = content(mesh)

    click(dispatcher, OUTSIDE)
    assert not dispatcher.knife_active
    assert dispatcher.message == "Knife committet"
    assert content(mesh) == after
    assert app.history.can_undo()
    app.history.undo()
    assert content(mesh) == before
    assert not app.history.can_undo()  # genau ein Eintrag


def test_click_on_face_is_a_no_op():
    app = make_app()
    mesh = app.scene.mesh
    dispatcher = start(app)
    xy = face_xy(app)
    dispatcher.message = "vorher"
    before = content(mesh)
    click(dispatcher, xy)
    assert dispatcher.knife_active and dispatcher.knife.start is None
    assert dispatcher.message == "vorher"
    assert dispatcher.take_changes() == Change.NONE
    assert content(mesh) == before


def test_drag_over_threshold_is_not_a_click():
    app = make_app()
    dispatcher = start(app)
    dispatcher.press(LMB)
    dispatcher.drag(4, 3)
    dispatcher.release("LEFT", *OUTSIDE)
    assert dispatcher.knife_active


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_esc_restores_mesh_before_c_without_history(asset):
    app = make_app(asset)
    mesh = app.scene.mesh
    before = content(mesh)
    dispatcher = start(app)
    e1, e2 = quad_edges(mesh, plus_quad(mesh))
    knife = dispatcher.knife
    assert knife.click({"kind": "edge", "edge_id": e1, "t": 0.3})
    assert knife.click({"kind": "edge", "edge_id": e2, "t": 0.6})
    assert content(mesh) != before
    assert dispatcher.key(ESC) is True
    assert not dispatcher.knife_active
    assert dispatcher.message == "Knife abgebrochen"
    assert Change.MESH in dispatcher.take_changes()
    assert content(mesh) == before
    assert not app.history.can_undo()
    # ESC danach ist wieder „nicht behandelt" (Fenster-Default).
    assert dispatcher.key(ESC) is False


def test_esc_while_lmb_held_ends_session_and_release_is_harmless():
    app = make_app()
    dispatcher = start(app)
    dispatcher.press(LMB)
    dispatcher.key(ESC)
    assert not dispatcher.knife_active and dispatcher.active_command is None
    dispatcher.release("LEFT", *OUTSIDE)
    assert dispatcher.message == "Knife abgebrochen"


def test_rejected_click_shows_failed_validation(monkeypatch):
    def split_via_one_minus_t(self, mirror_edge, source_vertex):
        return self._mesh.split_edge(mirror_edge, 1.0 - 0.3)[0]

    monkeypatch.setattr(LabKnifeTool, "_split_mirror_edge", split_via_one_minus_t)
    app = make_app()
    mesh = app.scene.mesh
    dispatcher = start(app)
    eid, xy = any_edge_xy(app, [e for e in mesh.all_edge_ids() if plus_x(mesh, e)])
    before = content(mesh)
    click(dispatcher, xy)
    knife = dispatcher.knife
    assert knife.start is None and content(mesh) == before
    assert not knife.last_validation.ok
    status = status_text(app, "subd_cube", dispatcher, symmetry_report(mesh))
    assert knife.last_validation.summary() in status
    assert CHECK_POSITION in status
    assert dispatcher.knife_active


# -- Während der Session gesperrt / erlaubt (E24) ------------------------------------


def test_other_commands_are_ignored_with_hint():
    app = make_app()
    mesh = app.scene.mesh
    app.scene.selection.set({mesh.all_vertex_ids()[0]})
    dispatcher = start(app)
    before = content(mesh)
    for inp in (SHIFT_S, Q, M, CTRL_Z, CTRL_Y):
        dispatcher.message = ""
        assert dispatcher.key(inp) is True
        assert dispatcher.message == KNIFE_HINT
    assert current_axis(mesh) == "X"
    assert not app.history.can_undo()
    assert content(mesh) == before
    assert dispatcher.knife_active
    # A13: Enter ist nicht belegt — `key_from_pyglet` liefert dafür kein Input.
    assert dispatcher.key(None) is False
    assert dispatcher.knife_active


def test_enter_has_no_lab_input():
    pyglet = import_pyglet()
    from mirai.pyglet_input import key_from_pyglet

    assert key_from_pyglet(pyglet.window.key.ENTER, 0) is None


def test_orbit_pan_zoom_work_during_session():
    app = make_app()
    dispatcher = start(app)
    camera = app.camera

    def view():
        return list(camera.build_view_matrix())

    for inp in (ALT_LMB, SHIFT_LMB, MMB):
        before = view()
        dispatcher.press(inp)
        assert dispatcher.active_command in ("Orbit", "Pan")
        dispatcher.drag(12, 7)
        dispatcher.release(inp.value, 0, 0)
        assert view() != before
        assert dispatcher.knife_active
    before = view()
    dispatcher.scroll(WHEEL_UP)
    assert view() != before
    assert dispatcher.knife_active


def test_vertex_hover_pauses_and_knife_hover_takes_over():
    app = make_app()
    mesh = app.scene.mesh
    vid = mesh.all_vertex_ids()[0]
    dispatcher = LabDispatcher(app, W, H)
    xy = vertex_xy(app, vid)
    dispatcher.motion(*xy)
    assert dispatcher.hover_vertex == vid
    dispatcher.key(C)
    assert dispatcher.hover_vertex is None
    dispatcher.motion(*xy)
    assert dispatcher.hover_vertex is None
    assert dispatcher.knife_hover.target == {"kind": "vertex", "vertex_id": vid}
    dispatcher.take_changes()
    dispatcher.motion(*xy)  # gleiche Stelle → keine Änderung
    assert dispatcher.take_changes() == Change.NONE
    dispatcher.motion(*OUTSIDE)
    assert dispatcher.knife_hover is None
    assert Change.HOVER in dispatcher.take_changes()
    dispatcher.key(ESC)
    assert dispatcher.knife_hover is None
    dispatcher.motion(*xy)
    assert dispatcher.hover_vertex == vid


# -- Picking (E27) -----------------------------------------------------------------


def test_knife_pick_resolves_vertex_edge_face_outside():
    app = make_app()
    mesh = app.scene.mesh
    vid = mesh.all_vertex_ids()[0]
    assert pick(app, vertex_xy(app, vid))["kind"] == "vertex"
    eid, xy = any_edge_xy(app, sorted(mesh.all_edge_ids(), key=int))
    target = pick(app, xy)
    assert target["edge_id"] == eid and ENDPOINT_THRESHOLD < target["t"] < 1.0 - ENDPOINT_THRESHOLD
    assert pick(app, face_xy(app))["kind"] == "face"
    assert pick(app, OUTSIDE) == {"kind": "outside"}


# -- Darstellung (E30) -------------------------------------------------------------


def test_knife_preview_data_markers():
    app = make_app()
    mesh = app.scene.mesh
    assert lab_draw_data.knife_preview_data(mesh, None, None) == lab_draw_data.KnifePreviewData(
        [], [], [], [], []
    )
    knife = start(app).knife
    e1, e2 = quad_edges(mesh, plus_quad(mesh))
    assert knife.click({"kind": "edge", "edge_id": e1, "t": 0.3})
    n = knife.start
    hover = knife_hover_preview(knife, {"kind": "edge", "edge_id": e2, "t": 0.6})
    data = lab_draw_data.knife_preview_data(mesh, knife, hover)
    assert data.start_points == list(mesh.vertex_position(n))
    assert data.start_mirror_points == list(mesh.vertex_position(knife.intent_pairs[n]))
    assert data.hover_points == list(hover.source_position)
    assert data.hover_mirror_points == list(hover.mirror_position)
    assert data.blocked_points == []

    blocked = KnifeHoverPreview(
        target={"kind": "vertex", "vertex_id": n},
        source_position=(1.0, 2.0, 3.0),
        mirror_position=None,
        resolvable=False,
        reason="x",
    )
    data = lab_draw_data.knife_preview_data(mesh, knife, blocked)
    assert data.blocked_points == [1.0, 2.0, 3.0]
    assert data.hover_points == [] and data.hover_mirror_points == []


def test_knife_preview_data_seam_start_has_no_mirror_marker():
    app = make_app()
    mesh = app.scene.mesh
    knife = start(app).knife
    seam_vertex = mesh.edge_vertices(min(mesh.symmetry_definition.seam_edges, key=int))[0]
    assert knife.click({"kind": "vertex", "vertex_id": seam_vertex})
    data = lab_draw_data.knife_preview_data(mesh, knife, None)
    assert data.start_points == list(mesh.vertex_position(seam_vertex))
    assert data.start_mirror_points == []


def test_knife_preview_data_unmirrored_start():
    app = make_app(axis=None)
    mesh = app.scene.mesh
    knife = start(app).knife
    assert knife.click({"kind": "vertex", "vertex_id": mesh.all_vertex_ids()[0]})
    data = lab_draw_data.knife_preview_data(mesh, knife, None)
    assert data.start_points and data.start_mirror_points == []
