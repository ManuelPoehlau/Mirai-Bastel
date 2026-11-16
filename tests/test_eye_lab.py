"""Eye LookDev phase 2 (Manu 2026-11-16, I-1..I-3) on the app path, headless: live preview with one Undo step on
commit, eyes on / off as view state, the Eye Lab's isolation, framing and restore, the quality tier, look presets.
Phase 3 (I-5): the look values (`core.EyeLook`) with Undo, preview, file v10, presets, variation and rest frame."""

from __future__ import annotations

import dataclasses
import json

import pytest

import tests._bootstrap  # noqa: F401

from mirai import eye_presets
from mirai.application import Application
from mirai.eye_object import DEFAULT_EYE
from mirai.interaction.input import Input

CTRL_Z = Input("key", "z", frozenset({"ctrl"}))


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _depth(app) -> int:
    return len(app._selection_undo_stack)


def test_preview_draws_the_value_and_the_release_commits_one_undo_step(app):
    eye = app.add_eye()
    depth = _depth(app)
    assert app.preview_eye(pupil_radius=0.2) is True
    assert app.viewport._eye_entries[eye.id].spec.pupil_radius == 0.2
    assert eye.eye == DEFAULT_EYE and _depth(app) == depth  # nothing in the document, no Undo step
    assert app.preview_eye(pupil_radius=0.22) is True and app.preview_eye(pupil_radius=0.22) is False
    assert app.set_eye(pupil_radius=0.22) is True
    assert eye.eye.pupil_radius == 0.22 and _depth(app) == depth + 1 and not app._objects.eye_previews
    app.key_press(CTRL_Z)
    assert eye.eye == DEFAULT_EYE and app.viewport._eye_entries[eye.id].spec == DEFAULT_EYE


def test_preview_ends_without_a_change_and_never_outlives_an_undo(app):
    eye = app.add_eye()
    app.set_eye(limbus_level=1)
    app.preview_eye(strength=0.3)
    assert app.preview_eye() is True and app.viewport._eye_entries[eye.id].spec == eye.eye
    assert app.preview_eye() is False
    app.preview_eye(strength=0.3)
    app.key_press(CTRL_Z)  # the preview was made from the undone values: it is not drawn any more
    assert app.viewport._eye_entries[eye.id].spec == DEFAULT_EYE


def test_preview_of_the_anatomy_draws_a_new_shell_and_keeps_the_object_mesh(app):
    eye = app.add_eye()
    shell = eye.mesh
    assert app.preview_eye(cornea_radius=0.7) is True
    drawn = app.viewport.object_entries[eye.id].mesh
    assert drawn is not shell and eye.mesh is shell
    app.preview_eye(cornea_radius=0.7, pupil_radius=0.2)  # same shape: the preview's shell is reused
    assert app.viewport.object_entries[eye.id].mesh is drawn
    assert app.preview_eye(pupil_radius=0.9) is False and "Eye preview" in app.status_message  # refused
    assert app.viewport._eye_entries[eye.id].spec.cornea_radius == 0.7  # the last valid preview stays


def test_eyes_shown_is_view_state_and_removes_entry_and_pick_cache(app):
    eye = app.add_eye()
    depth = _depth(app)
    assert app.set_eyes_shown(False) is True
    assert eye.id not in app.viewport.object_entries and eye.id not in app._objects.pick_caches
    assert not eye.hidden and _depth(app) == depth  # not the per-object Hide, no Undo step
    assert app.set_eyes_shown(False) is False
    assert app.set_eyes_shown(True) is True and eye.id in app.viewport.object_entries


def test_isolate_draws_only_the_eyes_beside_the_edit_object(app):
    other = app.add_primitive("cube", "Teeth")
    eye = app.add_eye()
    assert app.set_eye_isolate(True) is True
    assert eye.id in app.viewport.object_entries and other.id not in app.viewport.object_entries
    assert other.id not in app._objects.pick_caches
    assert app.set_eye_isolate(False) is True and other.id in app.viewport.object_entries


def test_tier_is_view_state_and_reaches_the_viewport(app):
    assert app.display.eye_tier == "fast"
    assert app.set_eye_display(tier="full") is True and app.viewport.eye_display.tier == "full"
    assert app.set_eye_display(tier="ultra") is False and "Eye view" in app.status_message


def test_eye_lab_frames_the_eye_and_closing_restores_camera_isolation_and_tier(app):
    assert app.open_eye_lab() is False and not app.eye_lab_open  # no eye selected
    eye = app.add_eye()
    cam = app.camera
    before = (cam.target, cam.distance, cam.yaw, cam.pitch, cam.ortho)
    depth = _depth(app)
    assert app.open_eye_lab() is True and app.eye_lab_open
    assert app.display.eye_tier == "full" and cam.distance < before[1]
    assert cam.yaw == pytest.approx(0.0) and cam.pitch == pytest.approx(0.0)  # frontal: the eye looks down +Z
    assert max(abs(c) for c in cam.target[:2]) < 0.1
    app.set_eye_isolate(True)
    app.camera.orbit(0.3, 0.1)
    assert app.close_eye_lab() is True and not app.eye_lab_open
    assert (cam.target, cam.distance, cam.yaw, cam.pitch, cam.ortho) == before
    assert app.display.eye_tier == "fast" and app.display.eye_isolate is False
    assert _depth(app) == depth and eye.eye == DEFAULT_EYE
    assert app.close_eye_lab() is False


def test_loading_a_scene_ends_the_eye_lab(app):
    app.add_eye()
    app.open_eye_lab()
    app.set_eye_isolate(True)
    app.load_scene("cube")
    assert not app.eye_lab_open and app.display.eye_tier == "fast" and app.display.eye_isolate is False


@pytest.fixture
def preset_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(eye_presets, "PRESET_DIR", tmp_path)
    monkeypatch.setattr(eye_presets.load_presets, "__defaults__", (tmp_path,))
    monkeypatch.setattr(eye_presets.save_preset, "__defaults__", (tmp_path,))
    return tmp_path


def test_presets_save_load_apply_keep_the_iris_fit(app, preset_dir):
    eye = app.add_eye()
    app.set_eye(limbus_level=2, pupil_radius=0.2, fit_pupil=0.3, fit_limbus=0.9)
    assert app.save_eye_preset("Gollum nass") is True
    data = json.loads((preset_dir / "gollum_nass.json").read_text(encoding="utf-8"))
    assert data["name"] == "Gollum nass" and "fit_pupil" not in data["values"]
    assert [p.name for p in app.eye_presets()] == [eye_presets.BUILTIN_NAME, eye_presets.LOOK_START_NAME, "Gollum nass"]
    depth = _depth(app)
    assert app.apply_eye_preset(eye_presets.BUILTIN_NAME) is True and _depth(app) == depth + 1
    assert eye.eye.limbus_level == 0 and eye.eye.pupil_radius == DEFAULT_EYE.pupil_radius
    assert (eye.eye.fit_pupil, eye.eye.fit_limbus) == (0.3, 0.9)  # the image's fit stays
    assert app.apply_eye_preset("Gollum nass") is True and eye.eye.limbus_level == 2
    assert app.apply_eye_preset("missing") is False
    assert app.save_eye_preset(eye_presets.BUILTIN_NAME) is False and "built-in" in app.status_message
    assert app.save_eye_preset("  ") is False


def test_an_invalid_preset_file_is_skipped_with_its_reason(preset_dir):
    (preset_dir / "bad.json").write_text('{"name": "Bad", "values": {"pupil_radius": 0.9}}', encoding="utf-8")
    (preset_dir / "odd.json").write_text('{"name": "Odd", "values": {"fit_pupil": 0.3}}', encoding="utf-8")
    (preset_dir / "broken.json").write_text("{", encoding="utf-8")
    presets, problems = eye_presets.load_presets(preset_dir)
    assert [p.name for p in presets] == [eye_presets.BUILTIN_NAME, eye_presets.LOOK_START_NAME]
    assert len(problems) == 3 and any("unknown" in p for p in problems)


# -- Eye LookDev phase 3: the look on the app path (Manu I-5 / I-8 / I-10, 2026-11-16) ---------------------------------


def test_a_look_value_is_one_undo_step_previews_live_and_saves_as_v10(app, tmp_path):
    from mirai.eye_object import DEFAULT_LOOK

    eye = app.add_eye()
    depth = _depth(app)
    assert app.preview_eye(**{"look.wet_sclera": 0.4}) is True
    assert app.viewport._eye_entries[eye.id].spec.look.wet_sclera == 0.4 and eye.eye.look is None
    assert app.set_eye(**{"look.wet_sclera": 0.6}) is True and _depth(app) == depth + 1
    assert eye.eye.look == dataclasses.replace(DEFAULT_LOOK, wet_sclera=0.6)
    assert app.set_eye(**{"look.lid_band": 0.5}) is True  # merges into the eye's own look
    assert (eye.eye.look.wet_sclera, eye.eye.look.lid_band) == (0.6, 0.5)
    assert app.set_eye(**{"look.lid_upper": -0.9}) is False and "lid_lower" in app.status_message
    path = tmp_path / "look.mirai.json"
    assert app.save_scene_file(path) is True
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 10
    fresh = Application()
    fresh.init_scene("cube")
    fresh.load_scene("file", scene_path=path)
    assert [o.eye.look for o in fresh.scene.objects.values() if o.eye is not None] == [eye.eye.look]
    app.key_press(CTRL_Z)
    app.key_press(CTRL_Z)
    assert eye.eye.look is None and app.save_scene_file(path) is True
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 9  # no look: the file as before phase 3


def test_the_eye_entry_carries_its_variation_and_rest_frame(app):
    """The irregularity pattern is the object's own (two eyes, a mirror copy included, never share one), and with the
    gaze turning an eye that has a look the entry carries its own placement as the lid's rest frame."""
    from mirai import object_space

    eye = app.add_eye()
    app.set_eye(**{"look.lid_shadow": 0.4})
    app.selection.objects = {eye.id}
    copy = app.mirror_copy("X")
    assert copy is not None and copy.eye == eye.eye
    drawn = app.viewport._eye_entries
    assert (drawn[eye.id].variation, drawn[copy.id].variation) == (int(eye.id), int(copy.id))
    assert drawn[eye.id].rest_matrix is None  # no gaze: drawn = rest
    app.set_eye_gaze_angles(20.0, 10.0)
    drawn = app.viewport._eye_entries
    assert drawn[eye.id].rest_matrix == tuple(object_space.model_matrix(eye))
    assert app.viewport.object_entries[eye.id].model_matrix != list(drawn[eye.id].rest_matrix)


def test_presets_carry_the_look_and_the_starting_look_keeps_the_rest(app, preset_dir):
    eye = app.add_eye()
    app.set_eye(limbus_level=3, **{"look.wet_sclera": 0.5, "look.seed": 4})
    assert app.save_eye_preset("Nass") is True
    data = json.loads((preset_dir / "nass.json").read_text(encoding="utf-8"))
    assert data["values"]["look"]["wet_sclera"] == 0.5 and data["values"]["look"]["seed"] == 4
    app.set_eye(look=None, limbus_level=1)
    assert app.apply_eye_preset("Nass") is True and eye.eye.look.wet_sclera == 0.5 and eye.eye.limbus_level == 3
    assert app.apply_eye_preset(eye_presets.LOOK_START_NAME) is True
    assert eye.eye.limbus_level == 3 and eye.eye.look == eye_presets.LOOK_START["look"]  # only the look changed
    (preset_dir / "old.json").write_text('{"name": "Alt", "values": {"limbus_level": 2}}', encoding="utf-8")
    assert app.apply_eye_preset("Alt") is True and eye.eye.look == eye_presets.LOOK_START["look"]  # pre-phase-3 file
    (preset_dir / "bad.json").write_text('{"name": "Bad", "values": {"look": {"wet_sclera": 2}}}', encoding="utf-8")
    assert "Bad" not in [p.name for p in app.eye_presets()]
    assert app.apply_eye_preset(eye_presets.BUILTIN_NAME) is True and eye.eye.look is None


def test_eye_lab_look_controls(app):
    from gui import eye_model as em
    from mirai.eye_object import DEFAULT_LOOK

    eye = app.add_eye()
    for field, _label, lo, hi, _fmt in em.LOOK_SLIDERS:
        assert field.startswith("look.") and lo <= em.value(eye.eye, field) <= hi
    assert {row[0][5:] for row in em.LOOK_SLIDERS} | {"seed"} == set(DEFAULT_LOOK.to_dict())
    assert em.new_pattern(app) is True and eye.eye.look.seed == DEFAULT_LOOK.seed + 1
    assert em.set_value(app, "look.irregularity_deg", 0.8) is True and em.value(eye.eye, "look.irregularity_deg") == 0.8
    assert em.reset_look(app) is True and eye.eye.look is None
