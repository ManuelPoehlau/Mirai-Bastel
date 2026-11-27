"""The likeness camera in the app (AD-042 §4, §5, §7.1, §8.1), headless (TraceStore): T-V1 ... T-V12 (T-V8, R-1, lives
in `test_room_rule.py`)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.interaction.input import Input
from mirai.iris_import import encode_png
from mirai.likeness import FreeView
from mirai.viewport import lens as L
from mirai.viewport import vecmath as v
from viewport.backdrop import gate_corners

WIDTH, HEIGHT = 800, 600
CENTRE = (WIDTH / 2.0, HEIGHT / 2.0)
U = Input("key", "u", frozenset())
WHEEL_UP = Input("wheel", "UP")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


def _drag(app, dx: float, dy: float, modifiers=("alt",), steps: int = 4, release: bool = True) -> None:
    app.pointer_motion(*CENTRE)
    app.pointer_press(_mouse("LEFT", *modifiers), *CENTRE)
    for _ in range(steps):
        app.pointer_drag(dx / steps, dy / steps, *CENTRE)
    if release:
        app.pointer_release("LEFT", *CENTRE)


def _fields(camera) -> tuple:
    return (tuple(camera.target), camera.distance, camera.yaw, camera.pitch, camera.fov_degrees, camera.ortho,
            camera.near, camera.far, camera.clip_follows_distance)


def _pose(record) -> tuple:
    return tuple(record.target), record.distance, record.yaw, record.pitch


def _cam_pose(camera) -> tuple:
    return tuple(camera.target), camera.distance, camera.yaw, camera.pitch


def _new(app) -> int:
    assert app.new_likeness_camera(), app.status_message
    return len(app.likeness.cameras) - 1


def _photo(tmp_path, w: int, h: int, name: str = "photo.png"):
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = np.arange(w, dtype=np.uint32)[None, :] % 256
    rgba[..., 1] = np.arange(h, dtype=np.uint32)[:, None] % 256
    rgba[..., 3] = 255
    path = tmp_path / name
    path.write_bytes(encode_png(rgba))
    return path


def _load_photo(app, index, path) -> None:
    assert app.load_likeness_photo(index, path)
    assert app.status_message == "Foto wird geladen …"
    for _ in range(5):
        app.update_viewport(1 / 60)
        if app.likeness.pending_photo is None:
            break


# -- T-V1: „Neu aus Ansicht“ ----------------------------------------------------------------------------------------

def test_new_from_view_reproduces_the_fov_and_the_pose(app):
    camera = app.camera
    fov, pose = camera.fov_degrees, _cam_pose(camera)
    index = _new(app)
    record = app.likeness.cameras[index]
    assert record.name == "Kamera 1" and app.likeness.active == index and not app.camera_view_open
    assert _pose(record) == pose and record.lens.sensor == "equiv35" and record.lens.fit == "diagonal"
    assert record.lens.focal_mm == pytest.approx(L.focal_from_fov(50.0, L.Lens(), 1.5, WIDTH / HEIGHT, 1.15))
    assert _cam_pose(camera) == pose and camera.fov_degrees == fov  # nothing else changed
    assert app.look_through(index)
    assert abs(camera.fov_degrees - fov) < 1e-9 and _cam_pose(camera) == pose
    assert app.camera_view_open and app.view_text.startswith("Kamera ›Kamera 1‹ · ")
    assert app.status_message.startswith("Kameraansicht ›Kamera 1‹") and app.status_message.endswith("mm KB")
    assert app.likeness.cameras[_new(app)].name == "Kamera 2"


def test_new_from_an_ortho_view_is_perspective(app):
    assert app.key_press(U) and app.camera.ortho
    index = _new(app)
    assert "(perspektivisch)" in app.status_message
    assert app.look_through(index) and not app.camera.ortho


# -- T-V2: enter / leave bit for bit --------------------------------------------------------------------------------

def test_enter_and_leave_restore_an_odd_free_view_bit_for_bit(app):
    camera = app.camera
    camera.target, camera.distance = (0.123456789, -1.000000001, 2.5e-7), 123.456789
    camera.yaw, camera.pitch, camera.fov_degrees = 1.2345678901, -0.3333333333, 47.123456789
    camera.follow_clip()
    camera.camera_revision += 1
    before = _fields(camera)
    assert before[6:8] == (camera.distance / 1000.0, 4.0 * camera.distance)
    index = _new(app)
    rev = camera.camera_revision
    assert app.look_through(index)
    assert camera.camera_revision > rev and not camera.clip_follows_distance
    record = app.likeness.cameras[index]
    assert (camera.near, camera.far) == (record.clip_near, record.clip_far)
    rev = camera.camera_revision
    assert app.leave_camera_view() and not app.camera_view_open
    assert _fields(camera) == before and camera.camera_revision > rev
    assert app.status_message == "Kameraansicht verlassen" and app.viewport.backdrop is None


def test_enter_and_leave_restore_a_snapped_front_ortho(app):
    camera = app.camera
    camera.set_view(0.1, 0.05)
    _drag(app, -10.0, 0.0, release=False)
    app.set_shift_held(True)
    _drag(app, -2.0, 0.0)
    app.set_shift_held(False)
    assert app.view_name == "Front" and camera.ortho and app._ortho_auto
    before, text = _fields(camera), app.view_text
    index = _new(app)
    assert app.look_through(index) and app.view_name is None and not camera.ortho
    assert app.leave_camera_view()
    assert _fields(camera) == before and app.view_name == "Front" and app._ortho_auto and app.view_text == text


def test_a_switch_keeps_the_saved_free_view(app):
    before = _fields(app.camera)
    first = _new(app)
    app.camera.orbit(0.4, 0.1)
    second = _new(app)
    app.camera.orbit(-0.4, -0.1)
    app.camera.yaw, app.camera.pitch = before[2], before[3]
    assert app.look_through(first) and app.look_through(second)
    assert _cam_pose(app.camera) == _pose(app.likeness.cameras[second]) and app.likeness.active == second
    assert app.look_through(second)  # the same camera: nothing to do
    assert app.leave_camera_view() and _fields(app.camera) == before
    assert app.toggle_camera_view() and app.likeness.view.index == second
    assert app.toggle_camera_view() and not app.camera_view_open


# -- T-V3 / T-V4: save and load -------------------------------------------------------------------------------------

def test_a_save_in_the_camera_view_writes_the_free_view(app, tmp_path):
    camera = app.camera
    free = {"target": list(camera.target), "distance": camera.distance, "yaw": camera.yaw, "pitch": camera.pitch,
            "fov_degrees": camera.fov_degrees, "ortho": camera.ortho}
    index = _new(app)
    assert app.set_likeness_lens(index, focal_mm=85.0)
    assert app.look_through(index)
    _drag(app, 30.0, 10.0)
    path = tmp_path / "scene.mirai.json"
    assert app.save_scene_file(path), app.status_message
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["view"]["camera"] == free
    assert "likeness" not in json.dumps(data) and "Kamera" not in json.dumps(data)
    assert app.camera_view_open  # saving changes nothing


def test_a_scene_load_leaves_the_camera_view_and_keeps_the_cameras(app, tmp_path):
    path = tmp_path / "scene.mirai.json"
    assert app.save_scene_file(path)
    index = _new(app)
    assert app.look_through(index)
    app.load_scene("file", scene_path=path)
    assert not app.camera_view_open and len(app.likeness.cameras) == 1 and app.viewport.backdrop is None
    assert app.camera.clip_follows_distance
    assert app.look_through(index) and app.viewport.backdrop is not None


# -- T-V5 / T-V6: navigation ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("focus", [False, True])
def test_navigation_moves_the_camera_and_the_record_follows(app, focus):
    app.dynamic_orbit_focus = focus
    if focus:
        app.set_orbit_focus_world((0.4, 0.3, 0.2), app.scene.edit_object_id)
    index = _new(app)
    assert app.look_through(index)
    record = app.likeness.cameras[index]
    clip = (record.clip_near, record.clip_far)
    for step in (lambda: _drag(app, 40.0, -15.0), lambda: _drag(app, 25.0, 12.0, ("alt", "shift")),
                 lambda: app.pointer_scroll(WHEEL_UP)):
        before = _cam_pose(app.camera)
        step()
        assert app.camera_view_open and _cam_pose(app.camera) != before
        assert _pose(record) == _cam_pose(app.camera)
        assert (app.camera.near, app.camera.far) == clip  # a not-fixed dolly keeps the record's clip


def test_a_fixed_camera_leaves_and_the_step_moves_the_free_view(app):
    index = _new(app)
    app.camera.orbit(0.3, 0.0)  # the free view differs from the camera
    record = app.likeness.cameras[index]
    assert app.set_likeness_fixed(index, True)
    for step in (lambda: _drag(app, 40.0, -15.0), lambda: _drag(app, 25.0, 12.0, ("alt", "shift")),
                 lambda: app.pointer_scroll(WHEEL_UP)):
        assert app.look_through(index) and "fixiert" in app.view_text
        pose = _pose(record)
        free = _cam_pose(app.likeness.view.saved)
        step()
        assert not app.camera_view_open and _pose(record) == pose
        assert app.status_message == "Kamera fixiert – freie Ansicht (Durchschauen kehrt zurück)"
        assert _cam_pose(app.camera) != free and _cam_pose(app.camera) != pose  # the step ran on the free view
    assert app.look_through(index) and _cam_pose(app.camera) == _pose(record)


def test_ortho_key_and_shift_snap_leave_then_act_on_the_free_view(app):
    camera = app.camera
    free_yaw = camera.yaw
    index = _new(app)
    assert app.look_through(index)
    assert app.key_press(U)
    assert not app.camera_view_open and camera.ortho and camera.yaw == free_yaw
    assert app.key_press(U) and not camera.ortho
    record = app.likeness.cameras[index]
    record.yaw += 0.6  # the camera looks from elsewhere than the free view
    assert app.look_through(index)
    _drag(app, -8.0, 0.0, release=False)  # an orbit gesture in the camera view (the record follows)
    followed = record.yaw
    app.set_shift_held(True)  # Shift mid-gesture: leave, then snap from the free view's angles
    assert not app.camera_view_open and camera.ortho
    from mirai.viewport.camera import nearest_standard_view

    assert app.view_name == nearest_standard_view(free_yaw, app._orbit_virtual[1])[0]
    assert app._orbit_virtual[0] == free_yaw and record.yaw == followed
    app.set_shift_held(False)
    app.pointer_release("LEFT", *CENTRE)


# -- T-V7: interplay and refusals ----------------------------------------------------------------------------------

def test_eye_lab_and_framing(app):
    app.add_eye()  # selected
    index = _new(app)
    assert app.look_through(index)
    assert app.frame_eye() is False and app.status_message == "Auge rahmen: erst Kameraansicht verlassen"
    pose = _cam_pose(app.camera)
    app.frame_lookdev(90.0, 0.0)
    assert _cam_pose(app.camera) == pose and app.status_message == "Kameraansicht: die Kamera ist die Rahmung"
    assert app.open_eye_lab() and app.eye_lab_open and not app.camera_view_open
    assert app.look_through(index) and not app.eye_lab_open and app.camera_view_open
    assert app.leave_camera_view()


def test_lookdev_opens_and_closes_in_the_camera_view(app):
    index = _new(app)
    assert app.look_through(index)
    assert app.open_lookdev() and app.camera_view_open
    assert app.close_lookdev() and app.camera_view_open


def test_entering_is_refused_during_a_knife_session_a_gesture_and_a_stroke(app, monkeypatch):
    index = _new(app)
    app.interaction.session = SimpleNamespace(owner="knife", label="Knife")
    try:
        assert app.look_through(index) is False and "knife" in app.status_message
    finally:
        app.interaction.session = None
    with monkeypatch.context() as m:
        m.setattr(type(app._gestures), "session", property(lambda self: object()))
        assert app.look_through(index) is False and "Geste" in app.status_message
    from tests.test_lookdev_room import _uvs
    from tests.test_paint_room import _stroke

    _uvs(app.scene.mesh)
    assert app.open_paint_room(), app.status_message
    _stroke(app, release=False)
    assert app.look_through(index) is False and "Strich" in app.status_message
    app.pointer_release("LEFT", *CENTRE)
    assert app.look_through(index) and app.paint_room_open
    assert not app.camera_view_open or app.leave_camera_view()
    assert app.look_through(99) is False


# -- T-V9: the pinhole invariant ------------------------------------------------------------------------------------

def _check_pinhole(app, record) -> None:
    camera = app.camera
    w, h = app.viewport_width, app.viewport_height
    a = L.frame_aspect(record.lens, None if record.photo is None else record.photo.size)
    tw, th = L.gate_tan_half(record.lens, a)
    half_w, half_h = L.gate_rect_ndc(a, w / h, app.likeness.overscan)
    eye = camera.eye()
    forward, right, up = camera.basis()
    for vid in app.scene.mesh.all_vertex_ids():
        p = app.scene.mesh.vertex_position(vid)
        rel = v.sub(p, eye)
        x, y, z = v.dot(rel, right), v.dot(rel, up), v.dot(rel, forward)
        sx, sy = camera.project_to_screen(p, w, h)
        ndc_x, ndc_y = 2.0 * sx / w - 1.0, 2.0 * sy / h - 1.0
        assert ndc_x / half_w == pytest.approx(x / (z * tw), rel=1e-12, abs=1e-12)
        assert ndc_y / half_h == pytest.approx(y / (z * th), rel=1e-12, abs=1e-12)


def test_the_model_keeps_its_place_in_the_gate(app):
    index = _new(app)
    assert app.set_likeness_lens(index, focal_mm=85.0)
    assert app.look_through(index)
    record = app.likeness.cameras[index]
    pose = _cam_pose(app.camera)
    _check_pinhole(app, record)
    for size in ((1600, 600), (500, 900), (800, 600)):  # wider and narrower than the frame
        app.set_viewport_size(*size)
        _check_pinhole(app, record)
    assert app.set_likeness_view(overscan=1.4)
    _check_pinhole(app, record)
    assert _cam_pose(app.camera) == pose
    gate = app.viewport.backdrop.gate
    assert gate == L.gate_rect_ndc(1.5, 800 / 600, 1.4)


def test_lens_setters_clamp_and_reapply(app):
    index = _new(app)
    assert app.look_through(index)
    rev = app.camera.camera_revision
    assert app.set_likeness_lens(index, focal_mm=5000.0)
    record = app.likeness.cameras[index]
    assert record.lens.focal_mm == 600.0 and app.camera.camera_revision > rev
    assert app.camera.fov_degrees == L.view_fov_degrees(record.lens, 1.5, WIDTH / HEIGHT, 1.15)
    assert app.set_likeness_lens(index, sensor="aps_c") and record.lens.fit == "auto"
    assert app.set_likeness_lens(index, sensor_w_mm=30.0) and record.lens.sensor == "custom"
    assert app.set_likeness_lens(index, fit="cover") is False and record.lens.fit == "auto"
    assert app.set_likeness_clip(index, near=2.0, far=1.0) is False
    assert app.set_likeness_clip(index, near=0.5, far=50.0) and (app.camera.near, app.camera.far) == (0.5, 50.0)
    assert app.set_likeness_view(overscan=9.0) and app.likeness.overscan == 1.5
    assert app.rename_likeness_camera(index, "  Anna 85  ") and record.name == "Anna 85"
    assert app.view_text.startswith("Kamera ›Anna 85‹ · 600 mm")
    assert app.rename_likeness_camera(index, " ") is False and app.rename_likeness_camera(index, "x" * 41) is False
    assert app.delete_likeness_camera(index) and not app.camera_view_open and not app.likeness.cameras
    assert app.likeness.active is None


# -- T-V10: the morph target's editing view -------------------------------------------------------------------------

def test_the_morph_editing_view_shift(app):
    from core import SelectionMode

    app.selection.mode = SelectionMode.VERTEX
    assert app.create_morph_target() is not None
    free = _fields(app.camera)
    index = _new(app)
    record = app.likeness.cameras[index]
    pose = _pose(record)
    assert app.look_through(index)
    assert app.edit_morph_target()
    shift = app._likeness_shift()
    assert shift != (0.0, 0.0, 0.0)
    assert _pose(record) == pose
    assert app.camera.target == tuple(pose[0][i] + shift[i] for i in range(3))
    _drag(app, 20.0, 0.0)  # navigation inside the editing view: the record holds the pose at the base
    assert tuple(record.target) == pytest.approx(tuple(app.camera.target[i] - shift[i] for i in range(3)))
    assert app.leave_morph_target()
    assert app.camera.target == pytest.approx(record.target) and _cam_pose(app.camera)[1:] == _pose(record)[1:]
    assert app.leave_camera_view() and _fields(app.camera) == free
    # leaving inside the editing view: the free view the single camera would have
    assert app.look_through(index) and app.edit_morph_target()
    assert app.leave_camera_view()
    assert app.camera.target == pytest.approx(tuple(free[0][i] + shift[i] for i in range(3)))
    assert app.leave_morph_target()
    assert app.camera.target == pytest.approx(free[0]) and _fields(app.camera)[1:] == free[1:]


# -- T-V11 / T-V12: the photo and the backdrop ----------------------------------------------------------------------

def test_photo_load_cap_turn_and_errors(app, tmp_path):
    index = _new(app)
    assert app.look_through(index)
    _load_photo(app, index, _photo(tmp_path, 300, 200))
    record = app.likeness.cameras[index]
    photo = record.photo
    assert photo is not None and photo.size == (300, 200) and photo.source_size == (300, 200)
    assert app.status_message.startswith("Foto ›photo.png‹: 300 × 200, ")
    big = _photo(tmp_path, 5000, 100, "wide.png")
    _load_photo(app, index, big)
    assert record.photo.size == (2500, 50) and record.photo.source_size == (5000, 100)
    assert "(aus 5000 × 100)" in app.status_message
    assert record.photo.serial > photo.serial
    _load_photo(app, index, _photo(tmp_path, 300, 200))
    fov = app.camera.fov_degrees
    serial = record.photo.serial
    assert app.turn_likeness_photo(index)
    assert record.photo.size == (200, 300) and record.photo.serial > serial and app.camera.fov_degrees != fov
    a = L.frame_aspect(record.lens, (200, 300))
    assert app.camera.fov_degrees == L.view_fov_degrees(record.lens, a, WIDTH / HEIGHT, app.likeness.overscan)
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    kept = record.photo
    _load_photo(app, index, bad)
    assert record.photo is kept and "nicht lesbar" in app.status_message
    _load_photo(app, index, _photo(tmp_path, 10, 10, "tiny.png"))
    assert record.photo is kept
    assert app.remove_likeness_photo(index) and record.photo is None


def test_the_backdrop_pushed_to_the_viewport(app, tmp_path):
    index = _new(app)
    assert app.viewport.backdrop is None
    assert app.look_through(index)
    backdrop = app.viewport.backdrop
    gate = L.gate_rect_ndc(1.5, WIDTH / HEIGHT, 1.15)
    assert backdrop.gate == gate and backdrop.image is None and backdrop.passepartout == 0.5
    _load_photo(app, index, _photo(tmp_path, 400, 300))
    backdrop = app.viewport.backdrop
    gate = L.gate_rect_ndc(4 / 3, WIDTH / HEIGHT, 1.15)
    assert backdrop.gate == gate and backdrop.corners == gate_corners(gate) and backdrop.image.shape == (300, 400, 4)
    assert backdrop.image_serial == app.likeness.cameras[index].photo.serial
    assert app.set_likeness_view(photo_opacity=0.4) and app.viewport.backdrop.opacity == 0.4
    assert app.set_likeness_view(photo_shown=False) and app.viewport.backdrop.image is None
    assert app.set_likeness_view(photo_shown=True) and app.viewport.backdrop.image is not None
    assert app.leave_camera_view() and app.viewport.backdrop is None


def test_free_view_record_is_frozen():
    with pytest.raises(Exception):
        FreeView((0.0, 0.0, 0.0), 1.0, 0.0, 0.0, 50.0, False, 0.05, 200.0, True, None, False).distance = 2.0
