"""AD-042 M2 in the app (§18), headless (TraceStore): the comparison (behind / in front / wipe / „Nur Foto“), the photo
fit pushed as corners, the dolly zoom, and the new values through the scene file (an M1 file reads with the defaults)."""

from __future__ import annotations

import json

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.iris_import import encode_png
from mirai.viewport import camera as camera_mod
from mirai.viewport import lens as L
from mirai.viewport import photo_fit as F
from viewport.backdrop import BEHIND, FRONT, gate_corners

WIDTH, HEIGHT = 800, 600


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _photo(tmp_path, w: int = 60, h: int = 40, name: str = "photo.png"):
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = np.arange(w, dtype=np.uint32)[None, :] % 256
    rgba[..., 3] = 255
    path = tmp_path / name
    path.write_bytes(encode_png(rgba))
    return path


def _with_photo(app, tmp_path, name: str = "photo.png") -> int:
    assert app.new_likeness_camera()
    index = len(app.likeness.cameras) - 1
    assert app.load_likeness_photo(index, _photo(tmp_path, name=name))
    for _ in range(3):
        app.update_viewport(0.0)
    assert app.likeness.cameras[index].photo is not None, app.status_message
    return index


def test_the_compare_modes_reach_the_backdrop(app, tmp_path):
    index = _with_photo(app, tmp_path)
    assert app.look_through(index)
    bd = app.viewport.backdrop
    assert (bd.placement, bd.wipe, bd.opacity) == (BEHIND, None, 1.0)  # M1's default
    assert app.set_likeness_view(photo_opacity=0.4, compare="front")
    bd = app.viewport.backdrop
    assert (bd.placement, bd.wipe, bd.opacity) == (FRONT, None, 0.4)
    assert app.set_likeness_view(compare="wipe", wipe=0.25)
    bd = app.viewport.backdrop
    hw = bd.gate[0]
    assert bd.placement == FRONT and bd.opacity == 1.0 and bd.wipe == pytest.approx(-hw + 0.5 * hw)
    assert app.set_likeness_view(wipe=7.0) and app.likeness.wipe == 1.0
    assert not app.set_likeness_view(compare="beside") and "unknown compare" in app.status_message
    assert app.likeness.compare == "wipe"
    with pytest.raises(TypeError):
        app.set_likeness_view(placement="front")


def test_nur_foto_while_held(app, tmp_path):
    index = _with_photo(app, tmp_path)
    assert not app.set_likeness_flip(True)  # only in the camera view
    assert app.look_through(index) and app.set_likeness_view(photo_opacity=0.3, photo_shown=False)
    assert app.viewport.backdrop.image is None
    revision = app.camera.camera_revision
    assert app.set_likeness_flip(True) and not app.set_likeness_flip(True)
    bd = app.viewport.backdrop
    assert bd.image is not None and (bd.placement, bd.opacity, bd.wipe) == (FRONT, 1.0, None)
    assert app.camera.camera_revision == revision  # a view of the photo, not of the camera
    assert app.set_likeness_flip(False) and app.viewport.backdrop.image is None
    assert app.set_likeness_flip(True) and app.leave_camera_view()
    assert not app.likeness.flip_held  # leaving releases it


def test_the_fit_is_sent_as_corners_and_moves_nothing_else(app, tmp_path):
    index = _with_photo(app, tmp_path)
    assert app.look_through(index)
    gate = app.viewport.backdrop.gate
    assert app.viewport.backdrop.corners == gate_corners(gate)
    before = (app.camera.camera_revision, app.camera.fov_degrees, app.camera.distance)
    assert app.set_likeness_photo_fit(index, rotation_deg=5.0, offset_x=0.1, offset_y=-0.05, mirror=True)
    fit = app.likeness.cameras[index].photo_fit
    assert app.viewport.backdrop.corners == F.photo_corners(gate, WIDTH / HEIGHT, fit)
    assert (app.camera.camera_revision, app.camera.fov_degrees, app.camera.distance) == before
    assert app.viewport.backdrop.gate == gate
    assert app.set_likeness_photo_fit(index, scale=0.5) and app.viewport.backdrop.corners == F.photo_corners(
        gate, WIDTH / HEIGHT, fit.__class__(5.0, 0.1, -0.05, False, 0.5, True))  # scale kept, not applied
    assert app.set_likeness_photo_fit(index, cropped=True)
    assert app.set_likeness_photo_fit(index, rotation_deg=400.0) and app.likeness.cameras[index].photo_fit.rotation_deg \
        == pytest.approx(40.0)
    assert not app.set_likeness_photo_fit(index, offset_x=float("nan")) and "Foto einpassen" in app.status_message
    with pytest.raises(TypeError):
        app.set_likeness_photo_fit(index, roll=1.0)
    assert app.reset_likeness_photo_fit(index) and app.viewport.backdrop.corners == gate_corners(gate)
    assert not app.reset_likeness_photo_fit(index)


def test_a_new_photo_fills_the_gate_and_the_same_file_keeps_its_fit(app, tmp_path):
    index = _with_photo(app, tmp_path, "a.png")
    assert app.set_likeness_photo_fit(index, rotation_deg=3.0)
    assert app.load_likeness_photo(index, tmp_path / "a.png")
    for _ in range(3):
        app.update_viewport(0.0)
    assert app.likeness.cameras[index].photo_fit.rotation_deg == 3.0
    assert app.load_likeness_photo(index, _photo(tmp_path, name="b.png"))
    for _ in range(3):
        app.update_viewport(0.0)
    assert app.likeness.cameras[index].photo_fit == F.PhotoFit()


def test_the_dolly_zoom_keeps_the_target_plane_and_changes_the_perspective(app):
    app.camera.set_view(0.0, 0.0)  # Front: the target plane is z = const
    assert app.new_likeness_camera() and app.look_through(0)
    cam = app.likeness.cameras[0]
    camera = app.camera
    target = tuple(camera.target)
    on_plane = (target[0] + 0.3, target[1] + 0.2, target[2])
    in_front = (target[0] + 0.3, target[1] + 0.2, target[2] + 0.8)
    assert abs(np.dot(np.subtract(on_plane, target), np.subtract(camera.eye(), target))) < 1e-12
    f0, d0 = cam.lens.focal_mm, cam.distance
    before = [camera.project_to_screen(p, WIDTH, HEIGHT) for p in (target, on_plane, in_front)]
    revision = camera.camera_revision
    assert app.dolly_zoom_likeness(0, f0 * 3.0)
    assert cam.lens.focal_mm == pytest.approx(f0 * 3.0) and cam.distance == pytest.approx(d0 * 3.0)
    assert cam.distance / cam.lens.focal_mm == pytest.approx(d0 / f0, rel=1e-12)
    assert camera.distance == cam.distance and camera.camera_revision > revision and tuple(camera.target) == target
    after = [camera.project_to_screen(p, WIDTH, HEIGHT) for p in (target, on_plane, in_front)]
    assert after[0] == pytest.approx(before[0], abs=1e-9)
    assert after[1] == pytest.approx(before[1], abs=1e-6)  # the target plane keeps its size in the gate
    assert np.hypot(*np.subtract(after[2], before[2])) > 5.0  # in front of it the perspective flattens


def test_the_dolly_zoom_keeps_the_ratio_at_the_limits(app):
    assert app.new_likeness_camera()
    cam = app.likeness.cameras[0]
    ratio = cam.distance / cam.lens.focal_mm
    assert app.dolly_zoom_likeness(0, 10_000.0)  # beyond both ranges: the tighter one decides
    assert cam.lens.focal_mm <= L.FOCAL_RANGE_MM[1] and cam.distance <= camera_mod.MAX_DISTANCE
    assert cam.distance / cam.lens.focal_mm == pytest.approx(ratio, rel=1e-12)
    assert app.dolly_zoom_likeness(0, 0.0)
    assert cam.lens.focal_mm >= L.FOCAL_RANGE_MM[0] and cam.distance >= camera_mod.MIN_DISTANCE
    assert cam.distance / cam.lens.focal_mm == pytest.approx(ratio, rel=1e-12)
    assert not app.dolly_zoom_likeness(0, cam.lens.focal_mm)
    assert not app.dolly_zoom_likeness(0, float("inf"))


def test_m2_values_round_trip_and_an_m1_file_reads_with_the_defaults(app, tmp_path):
    index = _with_photo(app, tmp_path)
    assert app.set_likeness_photo_fit(index, rotation_deg=-2.5, offset_x=0.03, cropped=True, scale=0.8, mirror=True)
    assert app.set_likeness_view(compare="wipe", wipe=0.3)
    fit = app.likeness.cameras[index].photo_fit
    scene = tmp_path / "scenes" / "head.mirai.json"
    assert app.save_scene_file(scene), app.status_message
    data = json.loads(scene.read_text(encoding="utf-8"))
    section = data["view"]["likeness"]
    assert section["format"] == 1 and section["compare"] == "wipe" and section["wipe"] == 0.3
    assert section["cameras"][0]["photo_fit"] == {"rotation_deg": -2.5, "offset_x": 0.03, "offset_y": 0.0,
                                                  "cropped": True, "scale": 0.8, "mirror": True}
    app.init_scene("cube")
    app.load_scene("file", scene_path=scene)
    assert app.likeness.cameras[0].photo_fit == fit and (app.likeness.compare, app.likeness.wipe) == ("wipe", 0.3)
    assert app.likeness.cameras[0].photo.oriented
    # the same file as M1 wrote it: no photo_fit, no compare / wipe, no `oriented`
    for cam in section["cameras"]:
        cam.pop("photo_fit")
        cam["photo"].pop("oriented")
    section.pop("compare")
    section.pop("wipe")
    m1 = tmp_path / "scenes" / "m1.mirai.json"
    m1.write_text(json.dumps(data), encoding="utf-8")
    app.load_scene("file", scene_path=m1)
    cam = app.likeness.cameras[0]
    assert cam.photo_fit == F.PhotoFit() and (app.likeness.compare, app.likeness.wipe) == ("behind", 0.5)
    assert cam.photo is not None and not cam.photo.oriented  # its quarter turns were set on the stored pixels
    assert app.save_scene_file(m1)
    again = json.loads(m1.read_text(encoding="utf-8"))["view"]["likeness"]["cameras"][0]["photo"]
    assert again["oriented"] is False  # kept as it was read


def test_a_broken_photo_fit_loads_the_scene_without_cameras(app, tmp_path):
    index = _with_photo(app, tmp_path)
    scene = tmp_path / "s.mirai.json"
    assert app.save_scene_file(scene)
    data = json.loads(scene.read_text(encoding="utf-8"))
    data["view"]["likeness"]["cameras"][index]["photo_fit"] = "tilted"
    scene.write_text(json.dumps(data), encoding="utf-8")
    app.load_scene("file", scene_path=scene)
    assert app.likeness.cameras == [] and "likeness" in app.status_message
