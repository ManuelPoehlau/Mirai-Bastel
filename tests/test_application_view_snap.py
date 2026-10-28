"""Views in the production app (WP Ortho / Views, Manu V-1..V-3 2026-10-28): Shift during an Alt+LMB orbit snaps
to the nearest standard view, orthographic; Shift up returns to the free orbit and perspective; a toggle key
switches Ortho <-> Persp at any time; picking, Box Select, occlusion, the gizmo and the Working Pivot work in ortho;
with symmetry on the pivot snaps onto the plane."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from hud import hud_state
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import FIXED_MODIFIER_RULES
from mirai.interaction.input import Input
from mirai.scene_factory import create_sphere
from mirai.viewport import gizmo
from mirai.viewport import vecmath as v

WIDTH, HEIGHT = 800, 600
QUARTER = math.pi / 2


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


U, P, K1, K2, K3, W, SHIFT_S = _key("u"), _key("p"), _key("1"), _key("2"), _key("3"), _key("w"), _key("s", "shift")
CENTRE = (WIDTH / 2.0, HEIGHT / 2.0)


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _orbit_press(app, modifiers=("alt",)):
    app.pointer_motion(*CENTRE)
    app.pointer_press(_mouse("LEFT", *modifiers), *CENTRE)


def _orbit_drag(app, dx: float, dy: float, steps: int = 4):
    x, y = CENTRE
    for _ in range(steps):
        app.pointer_drag(dx / steps, dy / steps, x, y)


def _release(app):
    app.pointer_release("LEFT", *CENTRE)


def _screen(app, point):
    return app.camera.project_to_screen(point, WIDTH, HEIGHT)


def _click(app, point, modifiers=()):
    x, y = _screen(app, point)
    app.pointer_motion(x, y)
    app.pointer_press(_mouse("LEFT", *modifiers), x, y)
    app.pointer_release("LEFT", x, y)


# -- V-1 / V-2: snap by Shift during the orbit -----------------------------------------------------------


def test_shift_during_the_orbit_snaps_to_the_nearest_view_and_ortho(app):
    app.camera.set_view(0.2, 0.15)
    _orbit_press(app)
    _orbit_drag(app, -40.0, 0.0)
    virtual = (app.camera.yaw, app.camera.pitch)
    assert app.set_shift_held(True)  # at once, before any further motion
    assert app.view_name == "Front" and app.camera.ortho
    assert (app.camera.yaw, app.camera.pitch) == (0.0, 0.0)
    assert app.status_message == "View: Front · Ortho" and hud_state(app).view == "Front · Ortho"
    _orbit_drag(app, 20.0, 0.0)  # still nearest Front: stays
    assert app.view_name == "Front" and app.camera.yaw == 0.0
    app.set_shift_held(False)
    assert app.view_name is None and not app.camera.ortho
    # Back on the virtual angles, which the motion under Shift kept following.
    assert app.camera.yaw == pytest.approx(virtual[0] - 20.0 * 0.005)
    assert app.camera.pitch == pytest.approx(virtual[1])
    _release(app)


def test_the_snap_follows_the_drag_to_the_next_view_and_reaches_top(app):
    app.camera.set_view(0.0, 0.0)
    _orbit_press(app)
    _orbit_drag(app, 6.0, 0.0)  # past the click threshold: the orbit gesture runs
    app.set_shift_held(True)
    assert app.view_name == "Front"
    _orbit_drag(app, -QUARTER / 0.005, 0.0)  # a quarter turn of yaw
    assert app.view_name == "Right" and app.camera.yaw == pytest.approx(QUARTER)
    _orbit_drag(app, 0.0, -1.2 / 0.005)  # pitch up past 45°
    assert app.view_name == "Top" and app.camera.pitch == QUARTER
    forward, right, up = app.camera.basis()
    assert forward == pytest.approx((0.0, -1.0, 0.0), abs=1e-12)
    _release(app)


def test_a_snapped_view_stays_after_release_and_a_free_orbit_leaves_ortho(app):
    _orbit_press(app)
    _orbit_drag(app, 10.0, 0.0)
    app.set_shift_held(True)
    _release(app)
    app.set_shift_held(False)  # after the release: no orbit gesture any more, the view stays
    assert app.view_name is not None and app.camera.ortho
    _orbit_press(app)
    _orbit_drag(app, 30.0, 0.0)
    _release(app)
    assert app.view_name is None and not app.camera.ortho  # V-2 Auto Perspective


def test_alt_shift_before_the_press_stays_pan(app):
    yaw, pitch, target = app.camera.yaw, app.camera.pitch, app.camera.target
    app.set_shift_held(True)
    _orbit_press(app, ("alt", "shift"))
    _orbit_drag(app, 40.0, 25.0)
    _release(app)
    assert (app.camera.yaw, app.camera.pitch) == (yaw, pitch)
    assert app.camera.target != target
    assert app.view_name is None and not app.camera.ortho


def test_shift_without_an_orbit_changes_nothing(app):
    rev = app.camera.camera_revision
    assert app.set_shift_held(True) is False
    assert app.camera.camera_revision == rev and app.view_name is None


def test_the_fixed_modifier_rule_lists_the_view_snap():
    assert any(mod == "Shift" and "Orbit" in rule and "ortho" in rule for mod, rule in FIXED_MODIFIER_RULES)


# -- V-2: the toggle key ---------------------------------------------------------------------------------------


def test_the_toggle_key_is_a_provisional_default_and_no_history_step(app):
    assert app.bindings.command_for(U) == cmd.TOGGLE_ORTHO
    history = len(app.history)
    rev = app.camera.camera_revision
    assert app.key_press(U) and app.camera.ortho and app.camera.camera_revision == rev + 1
    assert app.status_message == "View: Ortho"
    assert app.key_press(U) and not app.camera.ortho
    assert len(app.history) == history


def test_ortho_switched_on_by_hand_survives_leaving_a_snapped_view(app):
    app.key_press(U)
    _orbit_press(app)
    _orbit_drag(app, 10.0, 0.0)
    app.set_shift_held(True)
    app.set_shift_held(False)
    assert app.view_name is None and app.camera.ortho
    _release(app)


def test_the_toggle_in_a_snapped_view_keeps_the_view(app):
    _orbit_press(app)
    _orbit_drag(app, 10.0, 0.0)
    app.set_shift_held(True)
    _release(app)
    app.set_shift_held(False)
    assert app.key_press(U) and not app.camera.ortho and app.view_name is not None
    assert app.view_text.endswith("· Persp")


def test_the_toggle_works_during_a_held_transform_and_a_knife_session(app):
    app.key_press(K1)
    _click(app, (1.0, 1.0, 1.0))
    app.pointer_motion(*CENTRE)
    assert app.key_press(W)
    assert app.key_press(U) and app.camera.ortho
    app.key_release(W)
    app.key_press(_key("ESCAPE"))
    app.selection.clear()
    assert app.key_press(_key("c")) and app.knife_active
    assert app.key_press(U) and not app.camera.ortho
    assert app.knife_active


# -- picking, occlusion and the gizmo in ortho ------------------------------------------------------------------


def test_click_picking_in_ortho_for_vertex_edge_and_face(app):
    app.key_press(U)
    mesh = app.scene.mesh
    app.key_press(K1)
    corner = next(i for i in mesh.all_vertex_ids() if mesh.vertex_position(i) == (1.0, 1.0, 1.0))
    _click(app, (1.0, 1.0, 1.0))
    assert app.selection.vertices == {corner}
    app.key_press(K2)
    _click(app, (1.0, 1.0, 0.0))
    (edge,) = app.selection.edges
    ends = {tuple(mesh.vertex_position(i)) for i in mesh.edge_vertices(edge)}
    assert ends == {(1.0, 1.0, 1.0), (1.0, 1.0, -1.0)}
    app.key_press(K3)
    _click(app, (0.0, 0.0, 1.0))
    (face,) = app.selection.faces
    assert all(mesh.vertex_position(i)[2] == 1.0 for i in mesh.face_vertices(face))


@pytest.mark.parametrize("ortho", [False, True])
def test_box_select_hides_the_far_corner_in_both_projections(app, ortho):
    if ortho:
        app.key_press(U)
    app.key_press(K1)
    everything = ((2.0, 2.0), (WIDTH - 2.0, HEIGHT - 2.0))
    app.pointer_motion(*everything[0])
    app.pointer_press(_mouse("LEFT"), *everything[0])
    app.pointer_drag(everything[1][0] - everything[0][0], everything[1][1] - everything[0][1], *everything[1])
    app.pointer_release("LEFT", *everything[1])
    selected = {tuple(app.scene.mesh.vertex_position(i)) for i in app.selection.vertices}
    assert len(selected) == 7
    # The default view looks from (+x, +y, +z): the corner opposite to the eye is the hidden one.
    assert (-1.0, -1.0, -1.0) not in selected


def test_the_gizmo_keeps_its_screen_size_at_any_depth_in_ortho(app):
    app.key_press(U)
    near, far = (0.0, 0.0, 0.9), v.add((0.0, 0.0, 0.9), v.scale(app.camera.basis()[0], 3.0))
    assert gizmo.gizmo_size(app.camera, near) == gizmo.gizmo_size(app.camera, far)
    app.key_press(U)
    assert gizmo.gizmo_size(app.camera, near) < gizmo.gizmo_size(app.camera, far)


# -- the Working Pivot in ortho and the plane snap (V-3) ----------------------------------------------------


def _sphere_app(app):
    app.scene.mesh.load_state(create_sphere().export_state())
    app.frame_scene()
    app.camera.set_view(QUARTER, 0.0, ortho=True)  # Right view, ortho
    app._camera_changed()
    return app


def _place(app, point, modifiers=()):
    x, y = _screen(app, point)
    app.pointer_motion(x, y)
    assert app.key_press(P)
    app.pointer_press(_mouse("LEFT", *modifiers), x, y)
    app.pointer_release("LEFT", x, y)
    app.key_release(P)


def test_working_pivot_inside_lands_on_x0_in_the_ortho_side_view(app):
    _sphere_app(app)
    _place(app, (0.0, 0.5, 0.4))
    position = app.working_pivot.position
    assert abs(position[0]) < 1e-12
    assert position[1:] == pytest.approx((0.5, 0.4), abs=1e-9)


def test_with_symmetry_the_pivot_lands_exactly_on_the_plane_and_says_so(app):
    _sphere_app(app)
    # A perspective view near the side: the inside point drifts off x = 0, but only by a few pixels.
    app.camera.set_view(QUARTER - 0.15, 0.1, ortho=False)
    app._camera_changed()
    assert app.key_press(SHIFT_S)
    _place(app, (0.0, 0.5, 0.4))
    assert app.working_pivot.position[0] == 0.0
    assert "on the symmetry plane" in app.status_message


def test_without_symmetry_nothing_snaps(app):
    _sphere_app(app)
    app.camera.set_view(QUARTER - 0.15, 0.1, ortho=False)
    app._camera_changed()
    _place(app, (0.0, 0.5, 0.4))
    assert app.working_pivot.position[0] != 0.0
    assert "symmetry plane" not in app.status_message


def test_far_from_the_plane_the_pivot_is_not_snapped(app):
    _sphere_app(app)
    app.camera.set_view(0.0, 0.0, ortho=True)  # Front: the X plane is edge-on, distances are real
    app._camera_changed()
    assert app.key_press(SHIFT_S)
    _place(app, (0.5, 0.2, 0.0))
    assert app.working_pivot.position[0] == pytest.approx(0.5, abs=1e-6)
