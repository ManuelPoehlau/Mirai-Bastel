"""Object mirror pairs, B4: the partner follows the object gesture (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.4, §5.7).

Driven through the real key / pointer path (W/E/R in mode `4`, `pointer_motion`, release, Esc) and the
gizmo's object-level drag. The follower is `F(driver)` after every step (stateless), one
`ObjectTransformCommand` holds both objects, Esc restores both start instances. Refusals: a Reference
partner, an out-of-sync pair. Headless (TraceStore), no pyglet.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import ObjectState, ObjectTransform
from mirai import object_space
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.object_mirror import PLANES, in_sync, mirror_transform, pair_residual
from mirai.scene_objects import ObjectTransformCommand
from mirai.viewport import gizmo

WIDTH, HEIGHT = 800, 600
X = PLANES["X"][0]


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


W, E, R, ESC = _key("w"), _key("e"), _key("r"), _key("ESCAPE")
ONE, FOUR, KX = _key("1"), _key("4"), _key("x")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _pair(app: Application):
    """'eye.L' placed aside and turned, its mirror copy 'eye.R' across X = 0; nothing selected, mode 4."""
    a = app.add_primitive("sphere", name="eye.L")
    a.transform = ObjectTransform(
        translation=(2.0, 1.0, -0.5), rotation=object_space.axis_angle_rotation((0.0, 1.0, 0.0), 0.4), scale=0.5
    )
    a.pivot = (0.1, 0.2, 0.0)
    app._objects.placement_changed()
    b = app.mirror_copy("X")
    b.name = "eye.R"
    app.selection.objects = set()
    return a, b, app.scene.mirror_pairs[0]


def _gesture(app: Application, key: Input, steps=((24.0, 9.0),), *, release: bool = True):
    assert app.key_press(key), app.status_message
    for dx, dy in steps:
        app.pointer_motion(400, 300, dx, dy)
    if release:
        app.key_release(key)


@pytest.mark.parametrize("key", [W, E, R])
@pytest.mark.parametrize("side", ["a", "b"])
def test_either_side_drives_and_the_partner_follows_mirrored_in_one_step(key, side):
    app = _app()
    a, b, pair = _pair(app)
    driver, follower = (a, b) if side == "a" else (b, a)
    starts = (a.transform, b.transform)
    app.selection.objects = {driver.id}
    depth = len(app.history)

    _gesture(app, key, steps=((24.0, 9.0), (-7.0, 13.0)))

    assert driver.transform != starts[0 if side == "a" else 1]
    assert pair_residual(a, b, pair) == 0.0  # X = 0: bit-exact
    assert follower.transform == mirror_transform(driver.transform, X, 0.0)
    assert len(app.history) == depth + 1
    assert app.selection.objects == {driver.id}  # the partner is not selected
    assert f"{follower.name!r} mirrors {driver.name!r}" in app.status_message
    _undo = app.key_press(CTRL_Z)
    assert _undo and (a.transform, b.transform) == starts
    app.key_press(CTRL_Y)
    assert pair_residual(a, b, pair) == 0.0 and driver.transform != starts[0 if side == "a" else 1]


def test_the_command_holds_both_objects():
    app = _app()
    a, b, _ = _pair(app)
    app.selection.objects = {a.id}
    _gesture(app, W)
    command = app.history._undo_stack[-1]
    assert isinstance(command, ObjectTransformCommand)
    assert {obj.id for obj, _, _ in command.changes} == {a.id, b.id}


def test_move_reverses_the_normal_component_and_keeps_the_tangential_one():
    app = _app()
    a, b, _ = _pair(app)
    ta, tb = a.transform.translation, b.transform.translation
    app.selection.objects = {a.id}
    _gesture(app, W, steps=((30.0, -20.0),))
    da = [n - o for n, o in zip(a.transform.translation, ta)]
    db = [n - o for n, o in zip(b.transform.translation, tb)]
    assert db[0] == pytest.approx(-da[0]) and db[1:] == pytest.approx(da[1:])
    assert da[0] != pytest.approx(0.0)


def test_move_with_the_x_constraint_moves_the_partner_the_other_way_along_x():
    app = _app()
    a, b, _ = _pair(app)
    tb = b.transform.translation
    app.selection.objects = {a.id}
    app.key_press(KX)
    _gesture(app, W, steps=((40.0, 0.0),))
    app.key_press(KX)
    assert b.transform.translation[1:] == tb[1:]
    assert b.transform.translation[0] == -a.transform.translation[0]


def test_both_selected_is_one_unit_the_lower_id_drives():
    app = _app()
    a, b, pair = _pair(app)
    app.selection.objects = {a.id, b.id}
    assert app.key_press(W)
    assert "'eye.R' mirrors 'eye.L'" in app.status_message
    app.pointer_motion(400, 300, 25.0, 0.0)
    app.key_release(W)
    assert pair_residual(a, b, pair) == 0.0
    assert a.transform.translation[0] != 2.0  # A moved by the motion, B mirrored (not the same vector)


def test_a_third_object_moves_with_the_delta_while_the_partner_mirrors():
    app = _app()
    a, b, pair = _pair(app)
    c = app.add_primitive("cube", name="c")
    app.selection.objects = {a.id, c.id}
    ta = a.transform.translation
    _gesture(app, W, steps=((20.0, 5.0),))
    delta = [n - o for n, o in zip(a.transform.translation, ta)]
    assert c.transform.translation == pytest.approx(tuple(delta))
    assert pair_residual(a, b, pair) == 0.0


@pytest.mark.parametrize("key", [W, E, R])
def test_esc_restores_both_start_instances_exactly(key):
    app = _app()
    a, b, _ = _pair(app)
    starts = (a.transform, b.transform)
    app.selection.objects = {b.id}
    depth = len(app.history)
    _gesture(app, key, steps=((30.0, 10.0),), release=False)
    assert (a.transform, b.transform) != starts
    assert app.key_press(ESC)
    assert a.transform is starts[0] and b.transform is starts[1]
    assert len(app.history) == depth


def test_a_long_gesture_does_not_drift():
    app = _app()
    a, b, pair = _pair(app)
    app.selection.objects = {a.id}
    for key in (W, E, R):
        _gesture(app, key, steps=[(3.0, -1.0), (-2.0, 4.0), (5.0, 0.5)] * 70)
        assert pair_residual(a, b, pair) == 0.0
        assert in_sync(a, b, pair)


def test_a_tap_records_nothing_for_either():
    app = _app()
    a, b, _ = _pair(app)
    app.selection.objects = {a.id}
    depth = len(app.history)
    app.key_press(W)
    app.key_release(W)
    assert len(app.history) == depth


def test_a_reference_partner_locks_the_gesture():
    app = _app()
    a, b, _ = _pair(app)
    b.state = ObjectState.REFERENCE
    app._objects.sync_views()
    app.selection.objects = {a.id}
    start = a.transform
    assert app.key_press(W) is False
    assert "'eye.R' (mirror partner of 'eye.L') is a Reference - locked" in app.status_message
    assert app.interaction_owner is None
    app.pointer_motion(400, 300, 20.0, 0.0)
    assert a.transform is start


def test_an_out_of_sync_pair_refuses_the_gesture_until_re_synced():
    app = _app()
    a, b, pair = _pair(app)
    t = b.transform
    b.transform = ObjectTransform(translation=(t.translation[0] - 0.12, *t.translation[1:]), rotation=t.rotation, scale=t.scale)
    app.selection.objects = {a.id}
    assert app.key_press(W) is False
    assert "out of sync by 0.12" in app.status_message and "Re-sync" in app.status_message
    assert app.resync_mirror_pairs()
    assert app.key_press(W) is True
    app.key_release(W)


def test_a_mesh_edit_on_a_partner_leaves_the_pair_and_the_placements():
    app = _app()
    a, b, pair = _pair(app)
    placements = (a.transform, b.transform)
    app.selection.objects = {b.id}
    app.key_press(ONE)  # Q-5: b becomes the edit object
    assert app.scene.edit_object_id == b.id
    vid = sorted(b.mesh.all_vertex_ids())[0]
    app.selection.vertices = {vid}
    before = b.mesh.vertex_position(vid)
    _gesture(app, W, steps=((15.0, 0.0),))
    assert b.mesh.vertex_position(vid) != before
    assert app.scene.mirror_pairs == (pair,) and (a.transform, b.transform) == placements


# -- gizmo (object level, the same `_object_arm` path) ------------------------------------------


def _drag(app, start, delta, steps: int = 8, *, release: bool = True):
    inp = Input("mouse", "LEFT", frozenset())
    app.pointer_motion(*start)
    app.pointer_press(inp, *start)
    px, py = start
    for i in range(1, steps + 1):
        x, y = start[0] + delta[0] * i / steps, start[1] + delta[1] * i / steps
        app.pointer_drag(x - px, y - py, x, y)
        px, py = x, y
    if release:
        app.pointer_release("LEFT", px, py)


def _gizmo_app():
    app = _app()
    app.gizmo_enabled = True
    app.camera.yaw = 0.0
    app.camera.pitch = 0.0
    app.camera.camera_revision += 1
    return app


def test_a_gizmo_drag_moves_the_partner_mirrored_in_one_step():
    app = _gizmo_app()
    a, b, pair = _pair(app)
    app.selection.objects = {a.id}
    pivot = object_space.to_world(a, a.pivot)
    assert app.gizmo_items()[0].positions[:3] == pytest.approx(pivot)
    size = gizmo.gizmo_size(app.camera, pivot)
    start = app.camera.project_to_screen(tuple(pivot[i] + (0.0, 1.0, 0.0)[i] * size * 0.6 for i in range(3)), WIDTH, HEIGHT)
    depth, tb = len(app.history), b.transform.translation
    _drag(app, start, (0.0, -60.0))
    assert len(app.history) == depth + 1
    assert b.transform.translation[1] != tb[1] and pair_residual(a, b, pair) == 0.0


def test_with_both_selected_the_gizmo_sits_on_the_driver():
    app = _gizmo_app()
    a, b, _ = _pair(app)
    app.selection.objects = {a.id, b.id}
    assert app.gizmo_items()[0].positions[:3] == pytest.approx(object_space.to_world(a, a.pivot))
