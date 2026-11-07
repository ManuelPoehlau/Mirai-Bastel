"""AD-030 §13: das Morph-Panel, headless - die neuen `Application`-Wege (Ziel wählen, Umbenennen / Löschen per Ziel,
leiser Regler, Solo, Alle 0 %) und das Panel-Modell (`gui.morph_model`). Das Fenster selbst: `test_gui_imgui_window.py`."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from gui import morph_model as mm
from mirai.interaction import commands
from tests.test_application_delete_dissolve import _app, _grid_vertex, _select
from tests.test_morph_multi import TAB, V, _shown_equals_definition, _targets, _view_is_base_plus


def _weights(app) -> dict:
    return {lid: w for lid, _, w, _ in app.morph_target_rows()}


def test_rows_in_display_order_with_the_current_one():
    app = _app(4)
    assert app.morph_target_rows() == []
    lids = _targets(app, 3)
    rows = app.morph_target_rows()
    assert [r[0] for r in rows] == lids
    assert [r[1] for r in rows] == ["Target 1", "Target 2", "Target 3"]
    assert [r[3] for r in rows] == [False, False, True]  # a new target becomes current


def test_select_target_is_view_state_and_follows_the_editing_view():
    app = _app(4)
    lids = _targets(app, 3, seed=3, every=2)
    depth = len(app.history._undo_stack)
    assert app.select_morph_target(lids[0])
    assert app.morph_current_target == lids[0]
    assert not app.select_morph_target(lids[0])  # already current: nothing to do
    assert app.key_press(TAB)
    assert app.select_morph_target(lids[2])
    _view_is_base_plus(app, lids[2])
    assert app._morph.view.view_obj.name.endswith("Target 3")
    assert app.key_press(TAB)
    assert len(app.history._undo_stack) == depth  # no Undo step for choosing


def test_rename_and_delete_a_target_that_is_not_current_with_undo():
    app = _app(4)
    lids = _targets(app, 3)
    mesh = app.scene.mesh
    assert app.rename_morph_target("  Lächeln ", lids[0])
    assert mesh.point_layer_info(lids[0]).name == "Lächeln"
    assert app.morph_current_target == lids[2]  # renaming does not switch
    assert not app.rename_morph_target("Target 2", lids[0])  # taken
    assert not app.rename_morph_target("   ", lids[0])  # empty
    assert not app.rename_morph_target("x" * 65, lids[0])
    assert app.delete_morph_target(lids[1])
    assert app.morph_current_target == lids[2]  # deleting another keeps the current one
    assert [r[0] for r in app.morph_target_rows()] == [lids[0], lids[2]]
    app.dispatch_command(commands.UNDO)
    assert [r[0] for r in app.morph_target_rows()] == lids
    app.dispatch_command(commands.UNDO)
    assert mesh.point_layer_info(lids[0]).name == "Target 1"


def test_quiet_weight_sets_no_status_and_no_undo_step():
    app = _app(4)
    lids = _targets(app, 2)
    app.set_status("vorher")
    assert app.set_morph_weight(37, lids[0], quiet=True)
    assert app.status_message == "vorher"
    assert _weights(app)[lids[0]] == 37
    _shown_equals_definition(app)
    assert app.set_morph_weight(40, lids[0])
    assert "Target 1" in app.status_message and "40 %" in app.status_message


def test_solo_shows_one_target_and_restores_the_weights():
    app = _app(4)
    lids = _targets(app, 3)
    app.set_morph_weight(30, lids[0])
    app.set_morph_weight(60, lids[2])
    assert app.solo_morph_target(lids[1])  # at 0 %: solo shows it at 100 %
    assert _weights(app) == {lids[0]: 0, lids[1]: 100, lids[2]: 0}
    assert app.morph_solo_target == lids[1]
    _shown_equals_definition(app)
    assert app.solo_morph_target(lids[0])  # solo moves to another target: the memory is the one before any solo
    assert _weights(app) == {lids[0]: 30, lids[1]: 0, lids[2]: 0}
    assert app.solo_morph_target(lids[0])  # again: the weights as before
    assert _weights(app) == {lids[0]: 30, lids[1]: 0, lids[2]: 60}
    assert app.morph_solo_target is None
    _shown_equals_definition(app)


def test_a_weight_change_ends_the_solo():
    app = _app(4)
    lids = _targets(app, 2)
    app.set_morph_weight(50, lids[0])
    assert app.solo_morph_target(lids[1])
    app.set_morph_weight(20, lids[0], quiet=True)
    assert app.morph_solo_target is None
    assert app.solo_morph_target(lids[1])  # a fresh solo (not a restore)
    assert app.morph_solo_target == lids[1]


def test_zero_all_keeps_the_ab_memory():
    app = _app(4)
    lids = _targets(app, 2)
    app.set_morph_weight(70, lids[1])
    app.set_morph_weight(20, lids[0])
    assert app.zero_morph_weights()
    assert set(_weights(app).values()) == {0}
    _shown_equals_definition(app)
    app.dispatch_command(commands.MORPH_WEIGHT_DRAG)  # the tap: back to the current target's last weight
    assert _weights(app)[lids[1]] == 70


def test_panel_state_without_targets_on_the_base_on_the_view_and_in_mode_4():
    app = _app(4)
    st = mm.state(app)
    assert not st.has_targets and st.can_create and st.current is None
    lids = _targets(app, 2)
    _select(app, V, {_grid_vertex(app, 1, 1)})
    st = mm.state(app)
    assert st.has_targets and st.can_lifecycle and st.can_edit and st.count_text == "2 / 64 Ziele"
    assert st.current.lid == lids[1] and st.header.endswith("Basis")
    assert app.key_press(TAB)
    st = mm.state(app)
    assert st.view_open and not st.can_lifecycle and not st.can_create
    assert [r.editing for r in st.rows] == [False, True]
    assert "'Target 2' daneben" in st.header
    assert app.key_press(TAB)
    app.dispatch_command(commands.SET_OBJECT_MODE)
    st = mm.state(app)
    assert st.object_mode and not st.can_edit
    app.set_morph_weight(10, lids[0])
    app.solo_morph_target(lids[0])
    assert [r.solo for r in mm.state(app).rows] == [True, False]
