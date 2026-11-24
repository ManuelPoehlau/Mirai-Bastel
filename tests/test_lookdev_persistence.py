"""AD-038 §18 (LD-2): the LookDev material as document data and the studio in `view.lookdev`, headless.

E17 (application part): `SceneObject.look` survives save / load, travels with Duplicate, the mirror copy, Detach and
the scene reset, every change is one Undo step. E18: `view.lookdev` round trip, a bad value or an unknown preset skips
the section (the studio stays), a file without it keeps the current studio, and the documented compatibility
limitation (proposal §5.1): `capture` writes only the sections it knows, so a build that does not know `lookdev` drops
it on save - while the materials, being Core data (v15), are never silently lost.
"""

from __future__ import annotations

import json

import pytest

import tests._bootstrap  # noqa: F401

from core.serialization import LOOK_FORMAT_VERSION
from mirai import lookdev_material as lm
from mirai import view_state
from mirai.application import Application
from mirai.interaction import commands


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    app.frame_scene()
    return app


@pytest.fixture
def app() -> Application:
    return _app()


def _undo(app: Application) -> None:
    app.dispatch_command(commands.UNDO)
    app.update_viewport(0.0)


def _redo(app: Application) -> None:
    app.dispatch_command(commands.REDO)
    app.update_viewport(0.0)


def _load(path) -> Application:
    fresh = _app()
    fresh.load_scene("file", scene_path=path)
    return fresh


# -- E17: the material as document data ------------------------------------------------------------------------------


def test_a_look_is_saved_and_loaded_with_the_scene(app, tmp_path):
    app.open_lookdev()
    assert app.set_lookdev_material("Creature Skin") and app.set_lookdev_material_values(roughness=0.42)
    path = tmp_path / "skin.mirai.json"
    assert app.save_scene_file(path), app.status_message
    data = json.loads(path.read_text())
    assert data["version"] == LOOK_FORMAT_VERSION
    fresh = _load(path)
    look = fresh.scene.edit_object.look
    assert look == app.scene.edit_object.look and look.preset == "Creature Skin" and look.adjusted
    fresh.open_lookdev()
    assert fresh.viewport._edit_look.roughness == 0.42  # drawn from the file's material


def test_a_scene_without_looks_keeps_its_version(app, tmp_path):
    app.open_lookdev()
    path = tmp_path / "plain.mirai.json"
    assert app.save_scene_file(path)
    assert json.loads(path.read_text())["version"] < LOOK_FORMAT_VERSION
    assert all("look" not in raw for raw in json.loads(path.read_text())["objects"])


def test_every_material_change_is_one_undo_step_and_redo_puts_it_back(app):
    app.open_lookdev()
    edit = app.scene.edit_object
    app.set_lookdev_material("Wet Skin")
    app.set_lookdev_material_values(specular=0.8)
    assert edit.look.specular == 0.8
    _undo(app)
    assert edit.look == lm.PRESETS["Wet Skin"] and app.viewport._edit_look.specular == lm.PRESETS["Wet Skin"].specular
    _undo(app)
    assert edit.look is None and app.lookdev.material(edit).preset == lm.NEUTRAL
    _redo(app)
    _redo(app)
    assert edit.look.specular == 0.8 and app.viewport._edit_look.specular == 0.8


def test_undo_works_outside_the_room_too(app):
    app.open_lookdev()
    app.set_lookdev_material("Organisch")
    app.close_lookdev()
    _undo(app)
    assert app.scene.edit_object.look is None


def test_duplicate_and_mirror_copy_carry_the_look(app):
    app.open_lookdev()
    app.set_lookdev_material("Zähne")
    source = app.scene.edit_object
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.select_objects([source.id])
    before = set(app.scene.objects)
    assert app.duplicate_objects(), app.status_message
    (copy_id,) = set(app.scene.objects) - before
    assert app.scene.objects[copy_id].look == source.look
    app.select_objects([source.id])
    mirrored = app.mirror_copy("X")
    assert mirrored is not None, app.status_message
    assert mirrored.look == source.look


def test_detach_carries_the_look(app):
    from tests.test_detach import _app as detach_app, _cube_faces, _detach, _select_faces

    app = detach_app()
    src = app.scene.edit_object
    src.look = lm.PRESETS["Mundinneres"]
    _select_faces(app, _cube_faces(src.mesh))
    part = _detach(app)
    assert part.look == src.look


def test_a_scene_reset_takes_the_looks_of_the_file(app, tmp_path):
    app.open_lookdev()
    app.set_lookdev_material("Organisch")
    path = tmp_path / "o.mirai.json"
    app.save_scene_file(path)
    app.set_lookdev_material("Neutral")
    app.load_scene("file", scene_path=path)  # replace_scene: new ObjectIds, the file's looks
    assert app.scene.edit_object.look.preset == "Organisch" and not app.lookdev_open


# -- E18: view.lookdev -----------------------------------------------------------------------------------------------


def test_the_studio_survives_save_and_load(app, tmp_path):
    app.set_lookdev_studio_preset("Soft Studio")
    app.set_lookdev_studio(rotation=40.0, env_intensity=1.5, exposure=-0.5, tone_curve="clamp", follow_camera=True,
                           background=((0.2, 0.1, 0.1), (0.4, 0.4, 0.5)), background_gradient=True)
    app.set_lookdev_light("key", intensity=2.5, azimuth=-30.0, elevation=10.0, kelvin=4000.0, size=0.3)
    app.set_lookdev_light("rim", on=False)
    path = tmp_path / "studio.mirai.json"
    assert app.save_scene_file(path)
    fresh = _load(path)
    assert fresh.lookdev.studio == app.lookdev.studio
    assert not fresh.lookdev_open  # the room itself is not reopened by a load


def test_a_file_without_the_section_keeps_the_current_studio(app, tmp_path):
    path = tmp_path / "old.mirai.json"
    app.save_scene_file(path)
    data = json.loads(path.read_text())
    del data["view"]["lookdev"]
    path.write_text(json.dumps(data))
    other = _app()
    other.set_lookdev_studio_preset("Dramatic")
    other.load_scene("file", scene_path=path)
    assert other.lookdev.studio.preset == "Dramatic"


@pytest.mark.parametrize("edit", [
    lambda s: s.update(preset="Disco"),
    lambda s: s.update(exposure=40.0),
    lambda s: s.update(tone_curve="filmic"),
    lambda s: s.update(follow_camera="yes"),
    lambda s: s.update(background=[[0.1, 0.1, 0.1]]),
    lambda s: s.update(background=[[0.1, 0.1, 2.0], [0.1, 0.1, 0.1]]),
    lambda s: s["key"].update(kelvin=100.0),
    lambda s: s["fill"].update(on=1),
    lambda s: s.pop("rim"),
    lambda s: s.update(rotation="left"),
])
def test_a_bad_value_skips_the_section_and_the_studio_stays(app, edit):
    app.set_lookdev_studio_preset("Neutral Inspection")
    data = view_state.capture(app)
    edit(data["lookdev"])
    other = _app()
    other.set_lookdev_studio_preset("Dramatic")
    before = other.lookdev.studio
    skipped = view_state.apply(other, data)
    assert skipped == ["lookdev"] and other.lookdev.studio == before


def test_the_studio_is_view_state_without_undo(app):
    history = len(app.history)
    data = view_state.capture(app)
    data["lookdev"]["exposure"] = 1.5
    assert view_state.apply(app, data) == []
    assert app.lookdev.studio.exposure == 1.5 and len(app.history) == history


def test_an_older_build_drops_view_sections_it_does_not_know_but_never_the_materials(app, tmp_path):
    """Proposal §5.1, pinned: `capture` writes a fresh dict of its known sections, so a section the build does not
    know (here a future `view.future`, exactly as `view.lookdev` is for a build before LD-2) is dropped by a load and
    save. The LookDev materials are Core data (v15): an older build refuses the file instead of losing them."""
    app.set_lookdev_material("Creature Skin")
    path = tmp_path / "new.mirai.json"
    app.save_scene_file(path)
    data = json.loads(path.read_text())
    data["view"]["future"] = {"anything": 1}
    path.write_text(json.dumps(data))
    fresh = _load(path)
    again = tmp_path / "again.mirai.json"
    assert fresh.save_scene_file(again)
    saved = json.loads(again.read_text())
    assert "future" not in saved["view"] and "lookdev" in saved["view"]
    assert saved["version"] == LOOK_FORMAT_VERSION and saved["objects"][0]["look"]["preset"] == "Creature Skin"


# -- AD-039 §2.1 (T1-7): `view.lookdev.effects` ------------------------------------------------------------------------

def test_the_effects_survive_save_and_load(app, tmp_path):
    app.set_lookdev_studio_preset("Soft Studio")
    assert app.set_lookdev_effect("shadow", False)
    path = tmp_path / "effects.mirai.json"
    assert app.save_scene_file(path)
    assert json.loads(path.read_text())["view"]["lookdev"]["effects"] == {"shadow": False, "eye_shadow": True,
                                                                            "dual_lobe": True, "thickness": True,
                                                                            "cube": True, "regions": True, "maps": True,
                                                                            "area_diffuse": False}
    fresh = _load(path)
    assert fresh.lookdev.studio == app.lookdev.studio and not fresh.lookdev.studio.effects.shadow


def test_the_soft_light_survives_save_and_load_and_an_older_file_keeps_it_off(app, tmp_path):
    """AD-039 §23 (S8): `area_diffuse` is view state like the other effects; a file from before S8 has no entry for
    it and leaves it as it is (off by default)."""
    assert not app.lookdev.studio.effects.area_diffuse
    assert app.set_lookdev_effect("area_diffuse", True)
    path = tmp_path / "soft.mirai.json"
    assert app.save_scene_file(path)
    data = json.loads(path.read_text())
    assert data["view"]["lookdev"]["effects"]["area_diffuse"] is True
    assert _load(path).lookdev.studio.effects.area_diffuse
    del data["view"]["lookdev"]["effects"]["area_diffuse"]
    path.write_text(json.dumps(data))
    assert not _load(path).lookdev.studio.effects.area_diffuse


def test_an_ld2_file_without_effects_keeps_its_studio_and_the_current_effects(app):
    """A file written before S1 has no `effects`: its studio is read (the section is not skipped), the effects stay."""
    app.set_lookdev_studio_preset("Dramatic")
    app.set_lookdev_light("key", azimuth=-20.0)
    data = view_state.capture(app)
    del data["lookdev"]["effects"]
    other = _app()
    other.set_lookdev_effect("shadow", False)
    assert view_state.apply(other, data) == []
    assert other.lookdev.studio.preset == "Dramatic" and other.lookdev.studio.key.azimuth == -20.0
    assert not other.lookdev.studio.effects.shadow


@pytest.mark.parametrize("effects", ["on", ["shadow"], {"shadow": 1}, {"shadow": "yes"}, {"shadow": None}])
def test_a_bad_effects_value_skips_only_the_effects(app, effects):
    app.set_lookdev_studio_preset("Neutral Inspection")
    app.set_lookdev_studio(exposure=0.5)
    data = view_state.capture(app)
    data["lookdev"]["effects"] = effects
    other = _app()
    other.set_lookdev_effect("shadow", False)
    assert view_state.apply(other, data) == []
    assert other.lookdev.studio.preset == "Neutral Inspection" and other.lookdev.studio.exposure == 0.5
    assert not other.lookdev.studio.effects.shadow  # the effects stay as they were


def test_an_unknown_effect_name_is_ignored(app):
    data = view_state.capture(app)
    data["lookdev"]["effects"] = {"shadow": False, "raytracing": True}
    assert view_state.apply(app, data) == [] and not app.lookdev.studio.effects.shadow


def test_an_s1_file_without_eye_shadow_keeps_its_settings(app):
    """AD-039 §5: a file written by S1 has `effects` without `eye_shadow` - its shadow switch is read, the eye shadow
    stays as it is (on by default)."""
    data = view_state.capture(app)
    data["lookdev"]["effects"] = {"shadow": False}
    other = _app()
    assert view_state.apply(other, data) == []
    assert other.lookdev.studio.effects == lo_effects(shadow=False, eye_shadow=True)
    other.set_lookdev_effect("eye_shadow", False)
    data["lookdev"]["effects"] = {"shadow": True}
    assert view_state.apply(other, data) == []
    assert other.lookdev.studio.effects == lo_effects(shadow=True, eye_shadow=False)


def test_an_s2_file_without_dual_lobe_keeps_its_settings(app):
    """AD-039 §6: a file written by S2 has `effects` without `dual_lobe` - its switches are read, the dual lobe stays
    as it is (on by default)."""
    data = view_state.capture(app)
    data["lookdev"]["effects"] = {"shadow": False, "eye_shadow": False}
    other = _app()
    assert view_state.apply(other, data) == []
    assert other.lookdev.studio.effects == lo_effects(shadow=False, eye_shadow=False, dual_lobe=True)
    other.set_lookdev_effect("dual_lobe", False)
    assert view_state.apply(other, data) == []
    assert other.lookdev.studio.effects == lo_effects(shadow=False, eye_shadow=False, dual_lobe=False)


def test_an_s3_file_without_thickness_keeps_its_settings(app):
    """AD-039 §7: a file written by S3 has `effects` without `thickness` - it stays as it is (on by default)."""
    data = view_state.capture(app)
    data["lookdev"]["effects"] = {"shadow": True, "eye_shadow": True, "dual_lobe": False}
    other = _app()
    assert view_state.apply(other, data) == []
    assert other.lookdev.studio.effects == lo_effects(dual_lobe=False, thickness=True)
    other.set_lookdev_effect("thickness", False)
    assert view_state.apply(other, data) == []
    assert other.lookdev.studio.effects == lo_effects(dual_lobe=False, thickness=False)


def lo_effects(**kw):
    from viewport.lookdev_optics import LookdevEffects

    return LookdevEffects(**kw)
