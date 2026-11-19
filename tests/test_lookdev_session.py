"""The LookDev session studio and materials (AD-038 §6, §7, §15), headless: four studio presets with Portrait the default,
six material presets with Neutral the fallback, luminance Reinhard by default with Clamp as the diagnostic; the setters
change session state only (no Undo step, nothing saved); a deleted object loses its row."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from mirai import lookdev_material as lm
from mirai import lookdev_presets as lp
from mirai.application import Application
from mirai.interaction import commands
from viewport import lookdev_optics as lo


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    app.frame_scene()
    return app


def test_the_presets():
    assert lp.PRESET_NAMES == ("Neutral Inspection", "Portrait", "Soft Studio", "Dramatic")
    assert lp.DEFAULT_PRESET == "Portrait"
    assert lm.PRESET_NAMES == ("Creature Skin", "Wet Skin", "Zähne", "Mundinneres", "Organisch", "Neutral")
    for name, state in lp.PRESETS.items():
        assert state.preset == name and state.tone_curve == "reinhard" and not state.follow_camera
        assert len(state.studio.softboxes) <= 4
    neutral = lm.PRESETS[lm.NEUTRAL]
    assert (neutral.roughness, neutral.f0, neutral.wrap, neutral.backscatter) == (0.6, 0.04, 0.0, 0.0)
    skin = lm.PRESETS["Creature Skin"]
    assert skin.wrap_rgb()[0] > skin.wrap_rgb()[1] >= skin.wrap_rgb()[2]  # wider in red (§9.1)
    with pytest.raises(ValueError):
        lm.LookMaterial("x", (0.5, 0.5, 0.5), roughness=1.5)


def test_sh9_band_limit_of_the_presets():
    """SH9 is low-frequency by definition (§6): against the exact irradiance of each preset's environment it stays
    within 8 % of that environment's largest irradiance (the near-black Dramatic dome at the top: about 7 %, 2026-11-19);
    the projection itself is within 1 % (`test_lookdev_optics.py`, E6)."""
    d = lo.fibonacci_directions(200_000)
    normals = lo.fibonacci_directions(150)
    weight = np.maximum(d @ normals.T, 0.0) * (4.0 * math.pi / len(d)) / math.pi
    for state in lp.PRESETS.values():
        exact = weight.T @ lo.ld_studio(d, 0.0, state.studio)
        got = lo.sh9_eval(lo.sh9_project(state.studio), normals)
        assert np.abs(got - exact).max() <= 0.08 * exact.max(), state.preset


def test_tone_curve_default_and_diagnostic(app):
    app.open_lookdev()
    assert app.lookdev.studio.tone_curve == "reinhard"
    assert lo.frame_uniforms(app.lookdev.studio)["u_ld_tone"] == 0
    assert app.set_lookdev_studio(tone_curve="clamp") and app.viewport.lookdev_state.tone_curve == "clamp"
    assert app.set_lookdev_studio(tone_curve="filmic") is False and "tone curve" in app.status_message


def test_studio_setters_are_session_state(app, tmp_path):
    history = len(app.history)
    app.open_lookdev()
    assert app.lookdev.studio.preset == "Portrait"
    assert app.set_lookdev_studio_preset("Dramatic") and app.viewport.lookdev_state.preset == "Dramatic"
    assert app.set_lookdev_studio_preset("Dramatic") is False
    assert app.set_lookdev_studio_preset("Nope") is False and "no preset" in app.status_message
    studio = app.lookdev.studio.studio
    assert app.set_lookdev_studio(rotation=30.0, env_intensity=0.5, exposure=1.0, follow_camera=True)
    assert app.lookdev.studio.studio is studio  # the content is the same: SH9 is not projected again
    assert app.set_lookdev_studio(exposure=9.0) is False and "exposure" in app.status_message
    assert app.set_lookdev_studio(background=((0.1, 0.1, 0.1), (0.3, 0.3, 0.3)), background_gradient=True)
    assert app.set_lookdev_light("key", intensity=2.0, azimuth=60.0, kelvin=4500.0, size=0.2)
    assert app.set_lookdev_light("rim", on=False)
    assert app.lookdev.studio.rim.on is False and app.viewport.lookdev_state.key.azimuth == 60.0
    assert app.set_lookdev_light("bounce", on=True) is False
    assert app.set_lookdev_light("key", elevation=120.0) is False
    assert len(app.history) == history  # no Undo step
    app.close_lookdev()
    assert app.open_lookdev() and app.lookdev.studio.preset == "Dramatic"  # kept for the session
    path = tmp_path / "s.mirai.json"
    assert app.save_scene_file(path)
    assert "Dramatic" not in path.read_text() and "lookdev" not in json.loads(path.read_text())["view"]


def test_material_setters_targets_and_rows(app):
    history = len(app.history)
    app.open_lookdev()
    edit = app.scene.edit_object
    assert app.lookdev.material(edit).preset == lm.NEUTRAL  # §15 Q3: Neutral until a preset is picked
    assert app.set_lookdev_material("Creature Skin")
    assert app.lookdev.materials[edit.id].preset == "Creature Skin"
    assert app.viewport._edit_look.roughness == lm.PRESETS["Creature Skin"].roughness
    assert app.set_lookdev_material("Creature Skin") is False
    assert app.set_lookdev_material_values(roughness=0.4)
    row = app.lookdev.materials[edit.id]
    assert row.preset == "Creature Skin" and row.adjusted and row.roughness == 0.4
    assert app.set_lookdev_material_values(roughness=2.0) is False and "roughness" in app.status_message
    assert app.set_lookdev_material_values(albedo_source="color")
    assert app.viewport._edit_look.albedo is None
    assert len(app.history) == history


def test_material_applies_to_the_selected_objects_but_never_an_eye(app):
    eye = app.add_eye()  # selected in mode 4
    app.open_lookdev()
    assert app.set_lookdev_material("Zähne") is False and "Auge" in app.status_message  # an eye keeps its panel
    assert not app.lookdev.materials
    app.select_objects([app.scene.edit_object_id, eye.id])
    assert app.set_lookdev_material("Zähne") is True
    assert eye.id not in app.lookdev.materials and app.scene.edit_object_id in app.lookdev.materials


def test_a_deleted_object_loses_its_row(app):
    eye_free = app.scene.edit_object_id
    app.open_lookdev()
    app.lookdev.materials[12345] = lm.PRESETS["Organisch"]  # an id no object has (a deleted one)
    app._objects.sync_views()
    assert 12345 not in app.lookdev.materials and eye_free not in app.lookdev.materials
