"""The LookDev panel's logic (`gui.lookdev_model`, AD-038 §7), headless like the `paint_model` tests: the SPACE row,
the state the panel draws, the material section's targets and the eye note."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from gui import lookdev_model as lm
from mirai.application import Application


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


def test_state_reflects_the_session_studio(app):
    app.open_lookdev()
    st = lm.state(app)
    assert st.open and not st.preparing and st.status == lm.NOT_SAVED
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
