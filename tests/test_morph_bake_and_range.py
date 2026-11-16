"""Morph weights -100..200 %, saved sliders and the bake of the mix into the base (Manu 2026-11-16).

Headless. The range: negative and exaggerated weights follow the definition `b + Σ (wᵢ/100)·dᵢ` bit for bit, clamped
at the bounds. Saving: the sliders and the current target travel in the file's `"view"` section and come back on load;
unknown objects / targets are left out, a malformed section is skipped without breaking the load. Bake: the shown mix
becomes the rest shape, its weights go to 0 % (picture unchanged), the targets' offsets stay; one Undo step restores
positions *and* sliders, Redo bakes again; refused on the editing view and at all-zero.
"""

from __future__ import annotations

import json

import tests._bootstrap  # noqa: F401

from gui import morph_model
from mirai import morph_mix, morph_targets
from tests.test_morph_multi import CTRL_Y, CTRL_Z, TAB, V, _shown_equals_definition, _targets
from tests.test_application_delete_dissolve import _app, _select


def _positions(mesh) -> dict:
    return {v: tuple(mesh.vertex_position(v)) for v in mesh.all_vertex_ids()}


# -- range ------------------------------------------------------------------------------------------


def test_negative_and_exaggerated_weights_follow_the_definition():
    assert morph_mix.factor(150) == 1.5 and morph_mix.factor(-100) == -1.0 and morph_mix.factor(100) == 1.0
    b, d = (1.0, 2.0, 3.0), (0.5, -0.25, 1.0)
    assert morph_targets.blend(b, d, -100) == (0.5, 2.25, 2.0)
    assert morph_targets.blend(b, d, 200) == (2.0, 1.5, 5.0)
    assert morph_targets.blend(b, d, 0) == b
    app = _app()
    lids = _targets(app, 3)
    for lid, weight in zip(lids, (-60, 170, 35)):
        assert app.set_morph_weight(weight, lid)
    _shown_equals_definition(app)


def test_the_weight_is_clamped_to_the_range():
    app = _app()
    lid = _targets(app, 1)[0]
    app.set_morph_weight(500, lid)
    assert app.morph_weight == morph_targets.MAX_WEIGHT == 200
    app.set_morph_weight(-500, lid)
    assert app.morph_weight == morph_targets.MIN_WEIGHT == -100
    _shown_equals_definition(app)


def test_a_negative_weight_counts_as_on_for_the_tap_and_solo():
    app = _app()
    lid = _targets(app, 1)[0]
    app.set_morph_weight(-40, lid)
    assert app.morph.provider.object_weights(app.scene.edit_object_id) == {lid: -40}
    app._morph.toggle_ab()
    assert app.morph_weight == 0
    app._morph.toggle_ab()
    assert app.morph_weight == -40


# -- save / load --------------------------------------------------------------------------------------


def test_the_sliders_and_the_current_target_survive_save_and_load(tmp_path):
    app = _app()
    lids = _targets(app, 3)
    app.set_morph_weight(-70, lids[0])
    app.set_morph_weight(180, lids[2])
    app.select_morph_target(lids[1])
    path = tmp_path / "m.mirai.json"
    assert app.save_scene_file(path)
    fresh = _app()
    fresh.load_scene("file", scene_path=path)
    oid = fresh.scene.edit_object_id
    assert fresh.morph.provider.object_weights(oid) == {lids[0]: -70, lids[2]: 180}
    assert fresh.morph_current_target == lids[1]
    assert len(fresh.history) == 0
    _shown_equals_definition(fresh)


def test_unknown_entries_are_left_out_and_a_broken_section_is_skipped(tmp_path):
    app = _app()
    lids = _targets(app, 2)
    app.set_morph_weight(50, lids[0])
    path = tmp_path / "m.mirai.json"
    app.save_scene_file(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["view"]["morph"]["weights"] += [[0, 999, 40], [999, int(lids[1]), 40]]  # unknown target / object
    path.write_text(json.dumps(data), encoding="utf-8")
    fresh = _app()
    fresh.load_scene("file", scene_path=path)
    assert fresh.morph.provider.object_weights(fresh.scene.edit_object_id) == {lids[0]: 50}

    data["view"]["morph"]["weights"] = [["x", 1, 2]]
    path.write_text(json.dumps(data), encoding="utf-8")
    fresh = _app()
    fresh.load_scene("file", scene_path=path)
    assert fresh.morph.provider.object_weights(fresh.scene.edit_object_id) == {}
    assert "morph" in fresh.status_message


# -- bake ---------------------------------------------------------------------------------------------


def test_bake_makes_the_mix_the_rest_shape_and_undo_brings_back_both():
    app = _app()
    mesh = app.scene.mesh
    lids = _targets(app, 3, every=2)
    app.set_morph_weight(-50, lids[0])
    app.set_morph_weight(140, lids[1])
    oid = app.scene.edit_object_id
    weights = app.morph.provider.object_weights(oid)
    mix = morph_mix.evaluate(mesh, weights)
    before = _positions(mesh)
    offsets = {lid: mesh.layer_items(lid) for lid in lids}
    depth = len(app.history)

    assert app.bake_morph_mix(), app.status_message
    assert len(app.history) == depth + 1
    assert _positions(mesh) == mix  # bit for bit: the picture does not change
    assert app.morph.provider.object_weights(oid) == {}
    assert {lid: mesh.layer_items(lid) for lid in lids} == offsets  # targets stay, relative to the new base
    _shown_equals_definition(app)

    assert app.key_press(CTRL_Z)
    assert _positions(mesh) == before
    assert app.morph.provider.object_weights(oid) == weights
    _shown_equals_definition(app)

    assert app.key_press(CTRL_Y)
    assert _positions(mesh) == mix
    assert app.morph.provider.object_weights(oid) == {}
    _shown_equals_definition(app)


def test_bake_is_refused_at_zero_and_on_the_editing_view():
    app = _app()
    lid = _targets(app, 1)[0]
    depth = len(app.history)
    assert not app.bake_morph_mix()
    assert "nothing to bake" in app.status_message
    app.set_morph_weight(60, lid)
    _select(app, V, set())
    assert app.key_press(TAB) and app.morph_view_open
    assert not app.bake_morph_mix()
    assert len(app.history) == depth


def test_the_panel_offers_bake_only_on_the_base_with_a_weight():
    app = _app()
    lid = _targets(app, 1)[0]
    assert not morph_model.state(app).can_bake
    app.set_morph_weight(-20, lid)
    assert morph_model.state(app).can_bake
    _select(app, V, set())
    assert app.key_press(TAB)
    assert not morph_model.state(app).can_bake
