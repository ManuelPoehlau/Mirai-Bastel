"""The eye panel's pure logic (AD-033 §6), headless: what it shows for the selection and that its actions take the
`Application` paths (view state without Undo, values with Undo)."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from gui import eye_model as em
from mirai.application import Application
from mirai.eye_object import DEFAULT_EYE


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def test_state_shows_the_selected_eyes_and_the_view(app):
    st = em.state(app)
    assert not st.has_eyes and "Kein Auge" in st.header and st.preview and st.reflection == "studio"
    eye = app.add_eye()
    st = em.state(app)
    assert st.eyes == (eye,) and st.spec == DEFAULT_EYE and eye.name in st.header
    assert st.image_text == "Iris: berechnet (kein eigenes Bild)"
    app.selection.objects = {app.scene.edit_object_id}
    assert not em.state(app).has_eyes


def test_actions_take_the_application_paths(app):
    eye = app.add_eye()
    assert em.set_value(app, "limbus_level", 2) is True and eye.eye.limbus_level == 2
    assert em.set_value(app, "overlap_mm", 0.3) is True
    assert em.set_view(app, reflection="key") is True and app.display.eye_reflection == "key"
    with pytest.raises(ValueError):
        em.set_view(app, refraction="V9")
    assert em.set_value(app, "pupil_radius", 0.9) is False  # refused by EyeSpec, reason in the status line


def test_every_slider_field_is_an_eye_value_within_its_range():
    for field, _label, lo, hi, _fmt in em.SLIDERS:
        assert hasattr(DEFAULT_EYE, field) and lo <= getattr(DEFAULT_EYE, field) <= hi
    assert len(em.LEVEL_LABELS) == 4
