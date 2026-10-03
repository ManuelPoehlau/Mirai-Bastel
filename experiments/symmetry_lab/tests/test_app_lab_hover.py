"""Move-Ziel aus dem Hover unter Symmetrie auf dem App-Pfad (WP-SYM-LAB-03 Slice 5).

Ports der vier „port"-Zeilen aus dem gelöschten `test_lab_hover.py` (Plan A2, Tabelle
`test_lab_hover.py`). Die Ziel-Regel A4/E7/E8 und das Neu-Picken des Hovers (E9) sind
App-Regeln (`Application`, WP-06 B3); der Slice-4-KEEP wurde aber am Lab gegeben, und
die App-Tests prüfen diese Fälle ohne Symmetrie bzw. nur in Kombination. Hier laufen
sie mit Symmetrie X, Tasten über `lab_key_press`, Maus über die öffentlichen Eingänge
von `Application` — wie im Fenster. Headless wie `_app_lab_support`.
"""

from __future__ import annotations

import pytest

from mirai.interaction.tools.move import MoveTool
from mirai.symmetry import CorrespondenceState, mirror_position, vertex_correspondence

from symmetry_lab.lab_symmetry import AXIS_NORMALS, ORIGIN

from ._app_lab_support import (  # noqa: F401
    ESC,
    SHIFT_S,
    W,
    forbid_lab_calls,
    make_lab,
    press,
    screen,
    visible,
)

DRAGS = [(6, 2), (5, -3), (4, 7)]


@pytest.fixture
def symmetric():
    """`subd_cube`, Symmetrie X über die Lab-Taste, leere Auswahl."""
    app, lab = make_lab("subd_cube")
    assert press(app, lab, SHIFT_S) and lab.axis == "X"
    assert app.selection.is_empty()
    return app, lab


def visible_pairs(app) -> list[tuple]:
    """Sichtbare (per Hover pickbare) gepaarte Vertices mit ihrem Partner."""
    corr = vertex_correspondence(app.scene.mesh)
    return [
        (v, corr[v].partner) for v in visible(app) if corr[v].state is CorrespondenceState.PAIRED
    ]


def hover_on(app, vid) -> None:
    app.pointer_motion(*screen(app, vid))
    assert app.selection.hovered == vid


def move_mouse(app, start=(400.0, 300.0)) -> None:
    """Mausbewegung ohne gedrückte Taste, während W gehalten wird."""
    x, y = start
    for dx, dy in DRAGS:
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, float(dx), float(dy))


def test_hover_target_moves_mirrored_and_leaves_the_selection_empty(symmetric):
    """A4 + E8: leere Auswahl, Hover auf einem gepaarten Vertex, W halten + bewegen →
    der Hover-Vertex und sein Partner bewegen sich gespiegelt; ein History-Eintrag;
    die Auswahl ist vorher und nachher leer."""
    app, lab = symmetric
    mesh = app.scene.mesh
    vid, partner = visible_pairs(app)[0]
    hover_on(app, vid)
    history_before = len(app.history)
    p0, q0 = mesh.vertex_position(vid), mesh.vertex_position(partner)

    assert press(app, lab, W)
    assert app.transform_target == {vid}
    move_mouse(app)
    tool = app.tool_manager.active_tool
    assert isinstance(tool, MoveTool) and tool.moves == {vid, partner}
    assert app.key_release(W)

    p1, q1 = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert p1 != p0 and q1 != q0
    assert mirror_position(p1, ORIGIN, AXIS_NORMALS["X"]) == q1
    assert len(app.history) == history_before + 1
    assert app.selection.is_empty()
    assert app.transform_command is None


def test_target_fixed_at_w_press_cursor_over_other_vertex_does_not_retarget(symmetric):
    """E7: das Ziel steht beim W-Druck fest. Steht der Cursor danach über einem anderen
    Vertex, wird weder neu gehovert noch umgezielt; der andere Vertex bleibt, wo er ist."""
    app, lab = symmetric
    mesh = app.scene.mesh
    pairs = visible_pairs(app)
    vid, partner = pairs[0]
    other = next(v for v, _p in pairs if v not in (vid, partner))
    hover_on(app, vid)

    assert press(app, lab, W)
    assert app.transform_target == {vid}
    assert app.selection.hovered is None  # Hover-Ziel: Hover-Punkt gelöscht
    app.pointer_motion(*screen(app, other))  # ohne Delta: kein Move-Schritt, kein Hover
    assert app.selection.hovered is None
    assert app.transform_target == {vid}

    other_before = mesh.vertex_position(other)
    move_mouse(app)
    assert app.tool_manager.active_tool.moves == {vid, partner}
    assert app.key_release(W)
    assert mesh.vertex_position(other) == other_before


def test_esc_during_drag_with_hover_target_restores_exactly(symmetric):
    """E8 + exaktes Abbrechen: Hover-Ziel, W halten, bewegen, Esc → Mesh bitgleich wie
    vorher, kein History-Eintrag, Auswahl leer, kein aktives Tool."""
    app, lab = symmetric
    mesh = app.scene.mesh
    vid, _partner = visible_pairs(app)[0]
    hover_on(app, vid)
    state_before = mesh.export_state()
    history_before = len(app.history)

    assert press(app, lab, W)
    move_mouse(app)
    assert mesh.export_state() != state_before
    assert press(app, lab, ESC) is True

    assert mesh.export_state() == state_before
    assert len(app.history) == history_before
    assert app.selection.is_empty()
    assert app.transform_command is None
    assert app.tool_manager.active_tool is None


def test_hover_is_repicked_after_a_tap(symmetric):
    """E9, Antippen: W über einem Vertex drücken (Hover-Ziel, Hover gelöscht) und ohne
    Bewegung loslassen → nichts bewegt, kein History-Eintrag, der Hover ist am Cursor
    wieder da. (Der Abbruch-Fall: `tests/test_application_move.py::test_hover_is_repicked_after_cancel`.)"""
    app, lab = symmetric
    vid, _partner = visible_pairs(app)[0]
    hover_on(app, vid)
    state_before = app.scene.mesh.export_state()

    assert press(app, lab, W)
    assert app.selection.hovered is None
    assert app.key_release(W)  # Antippen: entschärft
    assert app.transform_command is None
    assert app.selection.hovered == vid
    assert app.scene.mesh.export_state() == state_before
    assert len(app.history) == 1  # nur der Shift+S-Schritt
