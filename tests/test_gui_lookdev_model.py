"""The LookDev panel's logic (`gui.lookdev_model`, AD-038 §7), headless like the `paint_model` tests: the SPACE row,
the state the panel draws, the material section's targets and the eye note."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from gui import lookdev_model as lm
from mirai.application import Application
from mirai.interaction import commands


def _undo(app) -> bool:
    app.dispatch_command(commands.UNDO)
    app.update_viewport(0.0)  # the per-frame highlight check redraws the looks (they are in its signature)
    return True


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    app.frame_scene()
    return app


def test_the_space_row_opens_and_closes(app):
    assert lm.menu_label(app) == lm.MENU_OPEN == "LookDev öffnen"
    assert lm.toggle(app) and app.lookdev_open
    assert lm.menu_label(app) == lm.MENU_CLOSE == "LookDev schließen"
    assert lm.toggle(app) and not app.lookdev_open


def test_state_reflects_the_studio(app):
    app.open_lookdev()
    st = lm.state(app)
    assert st.open and not st.preparing and st.status == lm.SAVED
    assert st.studio_preset == "Portrait" and st.tone_curve == "reinhard" and not st.follow_camera
    assert [row.name for row in st.lights] == ["key", "fill", "rim"] and all(row.on for row in st.lights)
    app.set_lookdev_studio_preset("Dramatic")
    app.set_lookdev_light("fill", on=False)
    st = lm.state(app)
    assert st.studio_preset == "Dramatic" and not st.lights[1].on and lm.TONE_LABELS[st.tone_curve] == "Neutral"


def test_material_section(app):
    app.open_lookdev()
    row = lm.state(app).material
    assert row.targets == (app.scene.edit_object.name,) and row.preset == "Neutral" and not row.adjusted
    assert lm.material_label(row) == "Neutral" and row.albedo_label == "Textur (keine)"
    app.set_lookdev_material("Creature Skin")
    app.set_lookdev_material_values(roughness=0.3)
    row = lm.state(app).material
    assert lm.material_label(row) == "Creature Skin (angepasst)" and row.roughness == 0.3
    eye = app.add_eye()  # the selection is the eye alone
    row = lm.state(app).material
    assert row.targets == () and row.eye_selected and lm.targets_label(row) == lm.EYE_NOTE
    app.select_objects([app.scene.edit_object_id, eye.id])
    row = lm.state(app).material
    assert row.targets == (app.scene.edit_object.name,) and lm.EYE_NOTE in lm.targets_label(row)


def test_views_and_wire(app):
    app.open_lookdev()
    yaw, pitch = lm.VIEWS["Profil"]
    app.frame_lookdev(yaw, pitch)
    assert abs(app.camera.yaw - 1.5707963) < 1e-6
    assert app.set_lookdev_wire(True) and lm.state(app).wire
    app.close_lookdev()
    assert not app.display.wireframe_overlay  # the value from before the room


def test_closed_state_has_no_material_section(app):
    st = lm.state(app)
    assert not st.open and st.material is None


# -- LD-2 (AD-038 §18): the held control, Zurücksetzen ----------------------------------------------------------------

def test_a_held_slider_previews_and_its_release_is_one_undo_step(app):
    app.open_lookdev()
    edit = app.scene.edit_object
    history = len(app.history)
    held = lm.MaterialEdit()
    for value in (0.5, 0.4, 0.3):  # a drag: every frame a preview
        assert held.hold(app, roughness=value)
    assert edit.look is None and len(app.history) == history  # nothing in the document yet
    assert app.lookdev.material(edit).roughness == 0.3 and lm.state(app).material.roughness == 0.3
    assert app.viewport._edit_look.roughness == 0.3  # drawn with the held value
    held.hold(app, base_color=(0.2, 0.3, 0.4))
    assert held.release(app) and not held.held
    assert len(app.history) == history + 1 and not app.lookdev.preview  # one step for the whole hold
    assert edit.look.roughness == 0.3 and edit.look.base_color == (0.2, 0.3, 0.4) and edit.look.adjusted
    assert _undo(app) and edit.look is None and app.viewport._edit_look.roughness == 0.6  # Neutral again
    assert held.release(app) is False  # nothing held


def test_a_preview_the_app_ended_is_never_committed_late(app):
    app.open_lookdev()
    history = len(app.history)
    held = lm.MaterialEdit()
    held.hold(app, wrap=0.7)
    app.close_lookdev()  # the room ends the preview
    assert not app.lookdev.preview
    app.open_lookdev()
    assert held.release(app) is False and app.scene.edit_object.look is None and len(app.history) == history
    held.hold(app, wrap=0.2)
    held.drop(app)
    assert not app.lookdev.preview and app.scene.edit_object.look is None


def test_reset_removes_the_look(app):
    app.open_lookdev()
    assert lm.state(app).material.has_look is False
    assert app.reset_lookdev_material() is False  # nothing to reset
    app.set_lookdev_material("Wet Skin")
    assert lm.state(app).material.has_look
    history = len(app.history)
    assert app.reset_lookdev_material() and app.scene.edit_object.look is None and len(app.history) == history + 1
    assert lm.state(app).material.preset == "Neutral"
    assert _undo(app) and app.scene.edit_object.look.preset == "Wet Skin"


def test_the_effects_block(app):
    """AD-039 §2.1: one row per built P3 effect, its switch and its reason when greyed."""
    st = lm.state(app)
    assert [(r.name, r.label, r.on, r.available) for r in st.effects] == [("shadow", "Schatten", True, True),
                                                                          ("eye_shadow", "Augen-Schatten", True, True),
                                                                          ("dual_lobe", "Doppel-Glanz", True, True),
                                                                          ("thickness", "Durchleuchtung", True, True)]
    assert lm.EFFECTS_TITLE == "Effekte" and all(r.hint for r in st.effects)
    app.set_lookdev_effect("shadow", False)
    rows = lm.state(app).effects
    assert not rows[0].on
    # AD-039 §5: the eye shadow needs the shadow - greyed with the reason, its own switch kept
    assert rows[1].on and not rows[1].available and rows[1].reason == "braucht Schatten"
    app.set_lookdev_effect("shadow", True)
    app.set_lookdev_effect("eye_shadow", False)
    rows = lm.state(app).effects
    assert rows[0].on and not rows[1].on and rows[1].available
    # AD-039 §6: the dual lobe needs neither the shadow nor a feature
    app.set_lookdev_effect("shadow", False)
    app.set_lookdev_effect("dual_lobe", False)
    rows = lm.state(app).effects
    assert not rows[2].on and rows[2].available and rows[2].reason is None
    # AD-039 §7: the thickness needs the shadow (greyed with the reason, its own switch kept)
    assert rows[3].on and not rows[3].available and rows[3].reason == "braucht Schatten"
    app.set_lookdev_effect("dual_lobe", True)
    assert lm.state(app).effects[2].on and lm.state(app).effects[2].available
