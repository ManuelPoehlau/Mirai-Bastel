"""HUD-Zeile des Labs auf dem App-Pfad (WP-SYM-LAB-03 Slice 2, Inventar #27).

`lab_app.hud_text(app, asset_name, report)` ist eine reine Textfunktion (GL-frei),
gebaut nur aus öffentlichem `Application`-Zustand und dem Symmetrie-Befund.
Vorbild und Wortlaut: `lab_status.status_text` des alten Labs, ohne E5 (Slice 4),
ohne Vorschau-Zeile (Slice 3) und ohne die Auswahl-Liste. Ein Teil je Test; der
Test für das Hover-Ziel ist der Port von `test_lab_hover.py::
test_status_shows_move_target_label` (Plan A2: „port with the HUD").
"""

from __future__ import annotations

import pytest

from core import VertexId
from mirai.interaction.input import Input
from mirai.symmetry import CorrespondenceState, SymmetryState, vertex_correspondence

from symmetry_lab.lab_app import TRANSFORM_IDLE, constraint_label, hud_text
from symmetry_lab.lab_symmetry import SymmetryReport

from ._app_lab_support import (  # noqa: F401
    E,
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

KEY_X = Input("key", "x")
SHIFT_Z = Input("key", "z", frozenset({"shift"}))


def _hud(app, lab, asset: str = "subd_cube") -> str:
    return hud_text(app, asset, lab.report)


def _parts(text: str) -> list[str]:
    return text.split(" | ")


def _paired(app):
    corr = vertex_correspondence(app.scene.mesh)
    return next(v for v in visible(app) if corr[v].state is CorrespondenceState.PAIRED)


def test_asset_and_vertex_count_come_first(lab_app):
    app, lab = lab_app
    assert _parts(_hud(app, lab))[:2] == ["subd_cube", "26 V"]


def test_symmetry_off_and_on_with_state(lab_app):
    app, lab = lab_app
    assert "Symmetrie: aus (off)" in _parts(_hud(app, lab))
    assert press(app, lab, SHIFT_S)
    assert "Symmetrie: X (valid)" in _parts(_hud(app, lab))


def test_unpaired_count_only_while_symmetry_is_on():
    app, lab = make_lab("man_with_shoes_basemesh")
    assert not any(p.startswith("ohne Partner") for p in _parts(_hud(app, lab, "man")))
    assert press(app, lab, SHIFT_S)
    parts = _parts(_hud(app, lab, "man"))
    assert "Symmetrie: X (partial)" in parts
    assert "ohne Partner: 54" in parts


def test_ambiguous_count_is_appended_when_present(lab_app):
    """Kein Registry-Asset hat mehrdeutige Vertices; die reine Funktion bekommt
    deshalb einen Befund von Hand."""
    app, _lab = lab_app
    report = SymmetryReport(
        axis="X",
        state=SymmetryState.AMBIGUOUS,
        unpaired=frozenset({VertexId(1), VertexId(2)}),
        ambiguous=frozenset({VertexId(3)}),
    )
    parts = _parts(hud_text(app, "probe", report))
    assert "Symmetrie: X (ambiguous)" in parts
    assert "ohne Partner: 2, mehrdeutig: 1" in parts


def test_transform_idle(lab_app):
    app, lab = lab_app
    assert TRANSFORM_IDLE in _parts(_hud(app, lab))


def test_transform_armed_and_moving_with_selection_target(lab_app):
    app, lab = lab_app
    click(app, *screen(app, visible(app)[0]))
    assert press(app, lab, W)
    assert "Move: scharf (Auswahl)" in _parts(_hud(app, lab))
    app.pointer_motion(400, 300, 5.0, 2.0)
    assert "Move: bewegt (Auswahl)" in _parts(_hud(app, lab))
    assert app.key_release(W)
    assert TRANSFORM_IDLE in _parts(_hud(app, lab))


@pytest.mark.parametrize("key,label", [(W, "Move"), (E, "Rotate")])
def test_hover_target_when_the_selection_is_empty(lab_app, key, label):
    """A4/E7/E8: leere Auswahl → Ziel ist der Hover-Vertex, fix ab dem Tastendruck.
    `Application` löscht den Hover beim Scharfschalten (clear-on-arm), die Zeile
    zeigt das Ziel trotzdem — aus `transform_target`."""
    app, lab = lab_app
    assert press(app, lab, SHIFT_S)
    vid = _paired(app)
    app.pointer_motion(*screen(app, vid))
    assert app.selection.hovered == vid and app.selection.is_empty()
    assert press(app, lab, key)
    assert app.selection.hovered is None
    assert f"{label}: scharf (Hover v{int(vid)})" in _parts(_hud(app, lab))
    app.pointer_motion(*MISS, 6.0, 3.0)
    assert f"{label}: bewegt (Hover v{int(vid)})" in _parts(_hud(app, lab))
    assert app.key_release(key)
    assert app.selection.is_empty()  # E8: der Hover-Move wählt nichts aus


def _constraint_parts(app, lab) -> list[str]:
    """Der Constraint-Teil der Zeile — ohne die Statusmeldung der App am Ende,
    die nach jeder Constraint-Taste ebenfalls „Constraint: …" lautet."""
    return [p for p in _parts(_hud(app, lab))[:-1] if p.startswith("Constraint")]


def test_constraint_label_only_while_set(lab_app):
    app, lab = lab_app
    assert not any(p.startswith("Constraint") for p in _parts(_hud(app, lab)))
    assert press(app, lab, KEY_X)
    assert _constraint_parts(app, lab) == ["Constraint: X"]
    assert press(app, lab, SHIFT_Z)
    assert _constraint_parts(app, lab) == ["Constraint: XY-Ebene"]
    assert press(app, lab, SHIFT_Z)
    assert app.axis_constraint is None
    assert _constraint_parts(app, lab) == []
    assert _parts(_hud(app, lab))[-1] == "Constraint: none"  # Meldung der App


def test_constraint_label_words():
    assert constraint_label(None) == "frei"
    assert constraint_label("y") == "Y"
    assert constraint_label("yz") == "YZ-Ebene"


def test_status_message_comes_last(lab_app):
    app, lab = lab_app
    assert app.status_message == ""
    assert not _hud(app, lab).endswith(" | ")
    assert press(app, lab, SHIFT_S)
    assert _parts(_hud(app, lab))[-1] == "Shift+S: Symmetrie X"
    assert press(app, lab, KEY_X)
    assert _parts(_hud(app, lab))[-1] == app.status_message


def test_full_line_in_order(lab_app):
    app, lab = lab_app
    assert press(app, lab, SHIFT_S)
    assert press(app, lab, KEY_X)
    vid = _paired(app)
    click(app, *screen(app, vid))
    assert press(app, lab, W)
    assert _hud(app, lab) == " | ".join([
        "subd_cube",
        "26 V",
        "Symmetrie: X (valid)",
        "ohne Partner: 0",
        "Move: scharf (Auswahl)",
        "Constraint: X",
        app.status_message,
    ])
