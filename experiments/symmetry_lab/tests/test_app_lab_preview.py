"""Die Re-Symmetrize-Vorschau der App im Lab (AD-SYM-04 Slice A3, 2026-10-24).

Bis A3 war die Vorschau eine Lab-Interaktion (WP-SYM-LAB-03 Slice 3: Gate-Zeile „preview open",
`hover_suspended`, D1). Seit A3 gehört sie `Application` (§10 R-a, `interaction_owner`
"resymmetrize"); ihr Verhalten (Ablehnungen, ausführen/Esc, ein Undo-Schritt, Modalität, Hover,
Fuzz, Overlay) testet `tests/test_application_resymmetrize.py`. Hier bleibt, was das Lab dazu tut:

- unter BLOCK (Default) ist Re-Symmetrize benannt erlaubt (K-6, wie Shift+S), unter MARK und bei
  Symmetrie aus läuft es ohnehin;
- solange die Vorschau offen ist, installiert das Lab keine Zeile (H2-R2: eine
  `Application`-Interaktion) und lehnt Shift+B mit dem Owner-Text ab;
- die blaue Vorschau-Zeile liest die offene Vorschau der App;
- Start-Liste ohne Vorschau-Zeile und ohne D1, mit der App-Taste;
- Zeichenreihenfolge: das Overlay der App (Ebene, Marker, Vorschau) vor den Partnern des Labs.
"""

from __future__ import annotations

import pytest

from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_topology import topology_report
from mirai.viewport.picking import pick_nearest_vertex

from symmetry_lab.lab_app import (
    GateMode,
    block_row,
    gate_row_for,
    gate_rows,
    lab_key_press,
    preview_text,
    startup_listing,
)
from symmetry_lab.lab_overlays import LabPointOverlay

from ._app_lab_support import (  # noqa: F401
    ESC,
    HEIGHT,
    WIDTH,
    SHIFT_B,
    SHIFT_S,
    W,
    click,
    forbid_lab_calls,
    make_lab,
    press,
    screen,
)

ALT_M = Input("key", "m", frozenset({"alt"}))


def _symmetric(asset: str = "man_with_shoes_basemesh"):
    app, lab = make_lab(asset)
    assert press(app, lab, SHIFT_S) and lab.axis == "X"
    return app, lab


def _first_visible(app, ids):
    mesh = app.scene.mesh
    for vid in sorted(ids, key=int):
        sx, sy = screen(app, vid)
        if pick_nearest_vertex(app.camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) == vid:
            return vid
    raise AssertionError("kein sichtbarer Vertex")


def _select_side_vertex(app, side: int = 0):
    sides = topology_report(app.scene.mesh).sides
    vid = _first_visible(app, [v for v, s in sides.vertex_side.items() if s == side])
    click(app, *screen(app, vid))
    assert app.selection.vertices == {vid}
    return vid


@pytest.fixture
def previewing():
    app, lab = _symmetric()
    _select_side_vertex(app)
    assert app.command_gate == block_row().gate  # E5-Default BLOCK
    assert press(app, lab, ALT_M) is True
    assert app.interaction_owner == "resymmetrize"
    return app, lab


def test_block_row_names_the_app_resymmetrize():
    assert block_row().gate.refusal(cmd.RESYMMETRIZE) is None


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK])
def test_the_preview_opens_and_executes_through_the_lab_path(mode):
    app, lab = _symmetric()
    if mode is GateMode.MARK:
        assert press(app, lab, SHIFT_B) and lab.gate_mode is GateMode.MARK
    _select_side_vertex(app)
    history = len(app.history)
    assert press(app, lab, ALT_M) is True
    assert app.resymmetrize_preview is not None
    assert press(app, lab, ALT_M) is True
    assert app.resymmetrize_preview is None
    assert len(app.history) == history + 1
    assert symmetry_state(app.scene.mesh) is SymmetryState.VALID
    assert app.command_gate == gate_row_for(lab.axis, mode).gate


def test_the_lab_installs_no_row_while_the_preview_is_open(previewing):
    app, lab = previewing
    gate = app.command_gate
    assert lab.sync_gate() is False
    assert press(app, lab, W) is False  # the app's preview refuses, the Lab keeps its row
    assert app.command_gate is gate
    assert app.hover_suspended is False  # the Lab no longer writes the hover flag


def test_shift_b_is_refused_with_the_owner_text(previewing):
    app, lab = previewing
    serial = app.status_serial
    assert press(app, lab, SHIFT_B) is False
    assert app.status_serial == serial + 1
    assert app.status_message == "E5-Modus (Shift+B) abgelehnt — Re-Symmetrize-Vorschau offen"
    assert lab.gate_mode is GateMode.BLOCK


def test_esc_reaches_the_app_and_the_row_comes_back(previewing):
    app, lab = previewing
    forwarded = []

    def forward(inp):
        forwarded.append(inp)
        return app.key_press(inp)

    assert lab_key_press(app, lab, ESC, forward=forward) is True
    assert forwarded == [ESC]
    assert app.resymmetrize_preview is None
    assert app.command_gate == block_row().gate


def test_preview_text_reads_the_apps_preview(previewing):
    app, lab = previewing
    plan = app.resymmetrize_preview
    text = preview_text(lab)
    assert f"Quelle {plan.source_label} → Ziel {plan.target_label}" in text
    assert "bewegt 27" in text
    assert "Alt+M = ausführen, ESC = abbrechen" in text
    assert press(app, lab, ESC)
    assert preview_text(lab) == ""


def test_startup_listing_has_no_preview_row_and_names_the_app_key():
    text = "\n".join(startup_listing())
    assert len(gate_rows()) == 3
    assert "Vorschau offen" not in text
    assert "Cancel (Esc)" not in text
    assert "hover_suspended" not in text
    assert "Alt+M -> ReSymmetrize" in text
    assert "key:m -> ReSymmetrize" not in text


def test_lab_overlay_holds_only_the_partners():
    app, lab = make_lab()
    assert [type(o) for o in lab.overlays] == [LabPointOverlay]
    assert LabPointOverlay.LAYERS == ("symmetry_hover_partner", "symmetry_selection_partner")


def test_app_display_with_the_preview_is_drawn_before_the_lab_partners(previewing, monkeypatch):
    """Ebene, Zustands-Marker und Vorschau zeichnet die App (ihr Overlay hängt `init_scene` vor dem
    Lab-Overlay an), dann die Partner des Labs, dann Hover und Auswahl der App."""
    app, lab = previewing
    (partners,) = lab.overlays
    log = []

    class AppPoints:
        def set_points(self, layer, positions):
            pass

        def draw(self, camera_uniforms):
            log.append("app points")

    app.viewport.point_overlay = AppPoints()
    monkeypatch.setattr(app.symmetry_display, "draw", lambda uniforms: log.append("app display"))
    monkeypatch.setattr(partners, "draw", lambda uniforms: log.append("lab partners"))
    app.viewport.sync()
    app.viewport.render()
    assert log == ["app display", "lab partners", "app points"]
