"""The LookDev room in the app (AD-038 §2, §3.3, §4.1, §9), headless (TraceStore).

E10: the display values saved and restored; a save in the room writes the restored `view.display`; a load closes the
room and drops the session materials. E11: the refusals (an exclusive interaction, a held gesture, a paint stroke) and
the room order (Eye Lab refused inside, Paint Room <-> LookDev with P-8). E12b: the UV request reaches the SubD surface
and the entry surfaces, and goes again on closing. Also: no selection tint in the room, the LookDraw from the object,
the shader preparation behind the status line.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.interaction import commands
from mirai.lookdev_material import NEUTRAL, PRESETS
from mirai.viewport import DisplayMode
from viewport.render_mesh import TRIANGLE_UVS
from viewport.viewport import EDIT_KEY


def _uvs(mesh) -> None:
    for i, fid in enumerate(mesh.all_face_ids()):
        mesh.set_face_uvs(fid, [(i / 6 + du / 6, dv) for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1))])


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    _uvs(app.scene.mesh)
    app.frame_scene()
    return app


def _display(app) -> tuple:
    d = app.display
    return (d.mode, d.wireframe_overlay, d.region_tint, d.eye_tier, d.show_texture, d.light_rig)


# -- E10: the display ----------------------------------------------------------------------------------------------

def test_entering_sets_the_display_and_leaving_restores_it(app):
    app.display.set_mode(DisplayMode.FLAT_SHADED)
    app.display.set_wireframe_overlay(True)
    app.display.region_tint = True
    app.display.show_texture = False
    app._apply_display()
    before, camera = _display(app), (app.camera.target, app.camera.distance, app.camera.yaw, app.camera.pitch)
    history = len(app.history)
    assert app.open_lookdev() and app.lookdev_open and app.viewport.shading == "lookdev"
    d = app.display
    assert (d.mode, d.wireframe_overlay, d.region_tint, d.eye_tier) == (DisplayMode.SHADED, False, False, "full")
    assert d.show_texture is False and d.light_rig == before[5]  # LD-D4: textures and the light rig untouched
    assert app.open_lookdev() is True  # opening again changes nothing
    assert app.close_lookdev() and not app.lookdev_open and app.viewport.shading == "worklight"
    assert _display(app) == before
    assert (app.camera.target, app.camera.distance, app.camera.yaw, app.camera.pitch) == camera
    assert len(app.history) == history  # view state: no Undo step
    assert app.close_lookdev() is False


def test_a_save_in_the_room_writes_the_restored_view(app, tmp_path):
    app.display.set_mode(DisplayMode.FLAT_SHADED)
    app.display.set_wireframe_overlay(True)
    app.display.region_tint = True
    outside = tmp_path / "outside.mirai.json"
    assert app.save_scene_file(outside), app.status_message
    app.open_lookdev()
    inside = tmp_path / "inside.mirai.json"
    assert app.save_scene_file(inside), app.status_message
    assert app.lookdev_open  # saving does not end the room
    a, b = json.loads(outside.read_text()), json.loads(inside.read_text())
    assert b["view"]["display"] == a["view"]["display"]
    assert a["view"]["display"]["mode"] == "FLAT_SHADED"
    assert b["view"]["lookdev"] == a["view"]["lookdev"]  # LD-2: the studio is saved whether the room is open or not


def test_a_load_closes_the_room_and_drops_a_held_preview(app):
    app.open_lookdev()
    app.lookdev.preview[app.scene.edit_object_id] = PRESETS["Creature Skin"]
    app.init_scene("cube")
    assert not app.lookdev_open and app.viewport.shading == "worklight" and not app.lookdev.preview


# -- E11: refusals and the room order --------------------------------------------------------------------------

def test_refused_while_an_exclusive_interaction_runs(app):
    before = _display(app)
    app.interaction.session = SimpleNamespace(owner="knife", label="Knife")
    try:
        assert app.open_lookdev() is False and "knife" in app.status_message
    finally:
        app.interaction.session = None
    assert not app.lookdev_open and _display(app) == before and app.viewport.shading == "worklight"


def test_refused_while_a_gesture_is_held(app, monkeypatch):
    monkeypatch.setattr(type(app._gestures), "session", property(lambda self: object()))
    assert app.open_lookdev() is False and "gesture" in app.status_message and not app.lookdev_open


def test_refused_during_a_paint_stroke_and_closes_the_paint_room_between_strokes(app):
    from tests.test_paint_room import _stroke

    assert app.open_paint_room(), app.status_message
    _stroke(app, release=False)
    assert app.open_lookdev() is False and "stroke" in app.status_message
    assert app.paint_room_open and not app.lookdev_open
    app.pointer_release("LEFT", 400, 300)
    assert app.open_lookdev() and app.lookdev_open and not app.paint_room_open
    app.close_lookdev()
    assert app.display.mode is DisplayMode.SHADED  # the Paint Room's own restored display, then LookDev's


def test_eye_lab_closes_on_entry_and_is_refused_inside(app):
    app.add_eye()  # selected
    assert app.open_eye_lab() and app.eye_lab_open
    assert app.open_lookdev() and not app.eye_lab_open
    assert app.open_eye_lab() is False and app.status_message == "Eye Lab: erst LookDev schließen"
    app.close_lookdev()
    assert app.open_eye_lab()


def test_paint_room_from_the_room_closes_it_and_a_refusal_keeps_it_open(app):
    app.open_lookdev()
    assert app.open_paint_room() and app.paint_room_open and not app.lookdev_open
    assert app.viewport.shading == "worklight"
    app.close_paint_room()
    app.open_lookdev()
    mesh = app.scene.mesh
    for fid in mesh.all_face_ids():
        mesh.set_face_uvs(fid, None)  # the Paint Room refuses an object without UVs
    assert app.open_paint_room() is False and "UVs" in app.status_message
    assert app.lookdev_open and app.viewport.shading == "lookdev"


# -- the LookDraws, the tint, the UV request ----------------------------------------------------------------------

def test_lookdraw_from_the_object_without_tint_and_with_its_texture(app, tmp_path):
    from tests.test_obj_uvs import write_png

    texture = tmp_path / "skin.png"
    write_png(texture, 4, 4, (200, 120, 90))
    app.scene.edit_object.texture = str(texture)
    app.display.show_texture = False  # the Worklight's toggle does not decide the LookDev albedo
    app._objects.sync_views()
    assert app.viewport._edit_look is None  # nothing in the Worklight
    app.open_lookdev()
    look = app.viewport._edit_look
    assert look is not None and look.albedo == str(texture)
    neutral = PRESETS[NEUTRAL]
    assert (look.roughness, look.specular) == (neutral.roughness, neutral.specular)  # the Neutral fallback (§15 Q3)
    assert app.viewport.render_mesh.uvs_requested and app.viewport.render_mesh.store.has(TRIANGLE_UVS) is False
    app.viewport.sync()
    assert app.viewport.render_mesh.store.has(TRIANGLE_UVS)
    app.close_lookdev()
    app.viewport.sync()
    assert app.viewport._edit_look is None and not app.viewport.render_mesh.uvs_requested
    assert not app.viewport.render_mesh.store.has(TRIANGLE_UVS)


def test_no_selection_tint_in_the_room(app):
    eye = app.add_eye()  # selected (mode 4)
    app._objects.sync_views()
    vp = app.viewport
    assert vp._eye_entries[eye.id].sclera_tint[3] > 0.0  # tinted in the Worklight
    app.open_lookdev()
    assert vp._eye_entries[eye.id].sclera_tint == (0.0, 0.0, 0.0, 0.0)
    assert eye.id not in vp._entry_looks  # an eye keeps the eye pass, no organic LookDraw
    app.close_lookdev()
    assert vp._eye_entries[eye.id].sclera_tint[3] > 0.0


def test_uv_request_reaches_the_subd_surface_and_goes_on_close(app, tmp_path):
    from tests.test_obj_uvs import write_png

    write_png(tmp_path / "skin.png", 4, 4, (200, 120, 90))
    app.scene.edit_object.texture = str(tmp_path / "skin.png")
    app.display.show_texture = False  # no Worklight texture: only LookDev asks for the UVs
    app._objects.sync_views()
    assert app.subdivision.set_view("cage"), app.status_message
    app.update_viewport(1 / 60)
    vp = app.viewport
    surface = vp.surface_render_mesh
    assert surface is not None and not surface.store.has(TRIANGLE_UVS)
    app.open_lookdev()
    app.update_viewport(1 / 60)
    surface = vp.surface_render_mesh
    assert EDIT_KEY in vp._uv_requests and surface.uvs_requested and surface.store.has(TRIANGLE_UVS)
    app.dispatch_command(commands.SUBD_CYCLE_VIEW)  # another surface is created in the room: it gets the request too
    app.dispatch_command(commands.SUBD_CYCLE_VIEW)
    app.dispatch_command(commands.SUBD_CYCLE_VIEW)
    app.update_viewport(1 / 60)
    if vp.surface_render_mesh is not None:
        assert vp.surface_render_mesh.uvs_requested
    app.close_lookdev()
    app.update_viewport(1 / 60)
    assert not vp._uv_requests
    if vp.surface_render_mesh is not None:
        assert not vp.surface_render_mesh.uvs_requested and not vp.surface_render_mesh.store.has(TRIANGLE_UVS)


def test_shaders_are_prepared_behind_the_status_line(app, monkeypatch):
    compiled = []
    monkeypatch.setattr(app.viewport, "lookdev_prepare_needed", lambda: True)
    monkeypatch.setattr(app.viewport, "prepare_lookdev", lambda: compiled.append(1) or 3)
    assert app.open_lookdev()
    assert app.status_message == "LookDev: Shader werden vorbereitet …" and app.viewport.shading == "worklight"
    app.update_viewport(1 / 60)
    assert not compiled and app.viewport.shading == "worklight"  # one frame shows the status line first
    app.update_viewport(1 / 60)
    assert compiled == [1] and app.viewport.shading == "lookdev" and "3 Shader" in app.status_message
    app.update_viewport(1 / 60)
    assert compiled == [1]  # once
    app.close_lookdev()
    assert app.viewport.shading == "worklight"


def test_the_frame_dict_is_resolved_again_only_on_a_studio_change(app):
    app.open_lookdev()
    vp = app.viewport
    frame = vp.lookdev_frame()
    assert vp.lookdev_frame() is frame  # the same studio: no new dict
    app.camera.set_view(0.3, 0.2)
    assert vp.lookdev_frame() is frame  # fixed to the world: the camera does not matter
    app.set_lookdev_studio(follow_camera=True)
    followed = vp.lookdev_frame()
    assert followed is not frame and vp.lookdev_frame() is followed
    app.camera.set_view(0.9, 0.1)
    assert vp.lookdev_frame() is not followed  # "Licht folgt Kamera": a camera move resolves it again


# -- AD-039 §2.1: the effect switches (view state of the room) ---------------------------------------------------------

def test_set_lookdev_effect_is_view_state_and_a_preset_keeps_the_effects(app):
    history = len(app.history)
    assert app.lookdev.studio.effects.shadow  # S1 is built: on by default
    assert app.set_lookdev_effect("shadow", False) and not app.lookdev.studio.effects.shadow
    assert not app.set_lookdev_effect("shadow", False)  # unchanged
    assert app.set_lookdev_studio_preset("Dramatic") and not app.lookdev.studio.effects.shadow
    assert len(app.history) == history  # no Undo
    assert not app.set_lookdev_effect("bloom", True) and "no effect 'bloom'" in app.status_message
    app.open_lookdev()
    app.update_viewport(1 / 60)
    assert app.set_lookdev_effect("shadow", True) and app.viewport.lookdev_state.effects.shadow  # headless: at once
    assert app.lookdev_effect_reasons() == {"shadow": None, "eye_shadow": None}
    # AD-039 §5: the eye shadow is its own switch (on by default) and needs the shadow
    assert app.lookdev.studio.effects.eye_shadow and app.set_lookdev_effect("eye_shadow", False)
    assert not app.viewport.lookdev_state.effects.eye_shadow and len(app.history) == history
    assert app.set_lookdev_effect("eye_shadow", True) and app.set_lookdev_effect("shadow", False)
    assert app.lookdev_effect_reasons() == {"shadow": None, "eye_shadow": "braucht Schatten"}


def test_an_effect_that_needs_a_compile_keeps_the_frame_before(app, monkeypatch):
    app.open_lookdev()
    app.update_viewport(1 / 60)
    assert app.viewport.shading == "lookdev"
    shown = app.viewport.lookdev_state
    compiled = []
    monkeypatch.setattr(app.viewport, "lookdev_prepare_needed", lambda: True)
    monkeypatch.setattr(app.viewport, "prepare_lookdev", lambda: compiled.append(1) or 1)
    assert app.set_lookdev_effect("shadow", not shown.effects.shadow)
    assert app.status_message == "LookDev: Shader werden vorbereitet …"
    app.set_lookdev_studio(exposure=1.0)  # another change waits for the compile too
    app.update_viewport(1 / 60)
    assert not compiled and app.viewport.shading == "lookdev" and app.viewport.lookdev_state is shown
    app.update_viewport(1 / 60)
    assert compiled == [1] and app.viewport.lookdev_state == app.lookdev.studio
    assert app.viewport.lookdev_state.effects.shadow != shown.effects.shadow
    assert app.viewport.lookdev_state.exposure == 1.0
