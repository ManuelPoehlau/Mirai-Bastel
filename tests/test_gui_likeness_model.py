"""The panel „Kamera“'s pure logic (AD-042 §8.2, `gui.likeness_model`), headless; plus the SPACE row, the LookDev
framing lock and the compact HUD entry (§5.7, §8.3)."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from gui import likeness_model as lm
from hud import hud_rows, hud_state, strip_rows
from mirai.application import Application


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(800, 600)
    return app


def test_without_a_camera_only_new_is_offered(app):
    st = lm.state(app)
    assert st.rows == () and not st.has_camera and st.lens is None and st.photo is None
    assert lm.menu_label(app) is None and not lm.framing_locked(app)


def test_rows_labels_and_the_camera_view(app):
    assert app.new_likeness_camera() and app.new_likeness_camera()
    st = lm.state(app)
    assert [r.name for r in st.rows] == ["Kamera 1", "Kamera 2"] and st.rows[1].active
    assert all(r.look_label == lm.LOOK for r in st.rows) and lm.menu_label(app) == lm.MENU_ENTER
    assert st.lens.sensor_label == "Kleinbild-Äquivalent" and st.photo.line == "kein Foto" and not st.photo.loaded
    assert st.distance_line.endswith("m bei 1 Einheit = 1 cm") and "°" in st.angles_line
    assert lm.toggle_row(app, 0)
    st = lm.state(app)
    assert st.viewing and st.rows[0].viewing and st.rows[0].look_label == lm.LEAVE and st.rows[0].active
    assert lm.menu_label(app) == lm.MENU_LEAVE and lm.framing_locked(app)
    assert app.set_likeness_fixed(0, True) and lm.state(app).fixed
    assert lm.toggle_row(app, 0) and not app.camera_view_open and not lm.framing_locked(app)


def test_angles_and_distance_lines():
    from mirai.viewport.lens import Lens

    assert lm.angles_line(Lens(focal_mm=85.0), None) == "16,1° × 23,9°"
    assert lm.distance_line(6.2) == "6,2 Einheiten · ≈ 0,06 m bei 1 Einheit = 1 cm"


def test_custom_sensor_row(app):
    assert app.new_likeness_camera()
    assert app.set_likeness_lens(0, sensor="custom")
    st = lm.state(app)
    assert st.lens.custom and st.lens.sensor_label == "eigene"


def test_the_compact_strip_names_the_camera_view(app):
    def labels():
        state = hud_state(app)
        return [r.label for r in strip_rows(hud_rows(state, {}), "compact")], state

    shown, state = labels()
    assert "Kamera" not in shown and state.camera is None
    assert app.new_likeness_camera() and app.look_through(0)
    shown, state = labels()
    assert "Kamera" in shown and state.camera.startswith("Kamera ›Kamera 1‹") and state.view == state.camera


# -- AD-042 M2 (§18.6) --------------------------------------------------------------------------------------------------

def test_m2_compare_fit_and_exif_rows(app, tmp_path, monkeypatch):
    import numpy as np

    from mirai import exif
    from mirai.iris_import import encode_png
    from mirai.viewport.photo_fit import PhotoFit

    assert lm.exif_line(None) == "" and lm.exif_line((26.0, True)) == "EXIF: 26 mm KB"
    assert lm.exif_line((4.25, False)) == "EXIF: 4,2 mm echt (Sensor prüfen)"
    assert app.new_likeness_camera()
    st = lm.state(app)
    assert (st.compare, st.wipe, st.flip_held) == ("behind", 0.5, False) and st.photo.exif_line == ""
    assert st.photo.fit == PhotoFit() and set(lm.COMPARE_LABELS) == {"behind", "front", "wipe"}
    path = tmp_path / "p.png"
    path.write_bytes(encode_png(np.full((20, 30, 4), 200, np.uint8)))
    monkeypatch.setattr(exif, "read_exif", lambda _p: exif.ExifInfo(focal_35mm=85.0))
    assert app.load_likeness_photo(0, path)
    for _ in range(3):
        app.update_viewport(0.0)
    assert app.set_likeness_photo_fit(0, mirror=True) and app.set_likeness_view(compare="wipe", wipe=0.2)
    st = lm.state(app)
    assert st.photo.exif_line == "EXIF: 85 mm KB" and st.photo.exif_adoptable and st.photo.fit.mirror
    assert (st.compare, st.wipe) == ("wipe", 0.2)
    assert app.adopt_likeness_exif(0) and not lm.state(app).photo.exif_adoptable
