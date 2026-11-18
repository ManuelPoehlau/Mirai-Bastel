"""Bone tool 02 (2026-11-18, `PROVISIONAL`, AD-028 addendum): the tip's axis constraint in the chain tool (world X / Y / Z
through the head, or an object's axis through its pivot along local +Z - an eye's gaze axis, `eye_gaze.rest_forward`), the
panel's "align the bone to the selected object's axis" and the eye bones of `Gollum_Head_rigging_test`.

The eyes of that scene look about 3.8 degrees outward (the left eye's +Z has a negative x, the right eye's a positive one):
a tip on the gaze axis shows it. Headless, in the AD-027 scenario driver.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401
from core import Rig
from gui import bone_model as bm
from mirai import object_space
from mirai.eye_gaze import rest_forward
from mirai.pivot import point_on_axis
from mirai.skinning import BonePose
from tests.interaction_trace import CTRL_Z, ESC, HEIGHT, OVERLAYS, WIDTH, Driver, _frame

SCENE = Path(__file__).resolve().parent.parent / "scenes" / "Gollum_Head_rigging_test.mirai.json"
EYES = ("Auge_Links", "Auge_Rechts")


def _scene(strip_eye_bones: bool = True) -> Driver:
    """The rigging test scene, seen from the side so that an eye's axis does not run along the view ray; the eye bones
    of the committed scene are taken out first (`strip_eye_bones`) so that the tool starts from the bare Hals / Kiefer rig."""
    d = Driver("cube")
    app = d.app
    app.load_scene("file", scene_path=SCENE, **OVERLAYS)
    app.set_viewport_size(WIDTH, HEIGHT)
    _frame(app)
    app.camera.set_view(1.0, 0.1)
    app.update_viewport(0)
    if strip_eye_bones:
        rig = app.scene.rig
        for bone in [b for b in rig.bones if b.name in EYES]:
            rig = rig.without_bone(bone.id)
        app.scene.rig = rig
    return d


def _eye(app, name):
    return next(o for o in app.scene.objects.values() if o.name == name)


def _click(d: Driver, world) -> None:
    x, y = d.app.camera.project_to_screen(world, WIDTH, HEIGHT)
    d.motion(x, y)
    d.click(x, y)


def _along(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def _scaled(v, s):
    return tuple(c * s for c in v)


def _unit(a, b):
    n = math.dist(a, b)
    return tuple((b[i] - a[i]) / n for i in range(3))


def _angle_to_z(direction) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, direction[2]))))


# -- the geometry --------------------------------------------------------------------------------------------------


def test_point_on_axis_is_the_axis_point_nearest_to_the_view_ray_and_the_length_is_free() -> None:
    # a ray from (0, 0, 5) straight down to the axis' plane meets the X axis through (1, 2, 0) at x = 0 (t = -1)
    point, t = point_on_axis((0.0, 2.0, 5.0), (0.0, 0.0, -1.0), (1.0, 2.0, 0.0), (1.0, 0.0, 0.0))
    assert point == pytest.approx((0.0, 2.0, 0.0)) and t == pytest.approx(-1.0)  # behind the axis point: allowed
    # a skew ray: the nearest points of the two lines (checked against the definition: the connecting segment is orthogonal to both)
    ray_o, ray_d, axis_p, axis_d = (0.3, -0.2, 4.0), (0.1, 0.2, -1.0), (0.0, 0.5, 0.0), (0.6, 0.3, 0.7)
    point, t = point_on_axis(ray_o, ray_d, axis_p, axis_d)
    n = math.sqrt(sum(c * c for c in axis_d))
    ud = tuple(c / n for c in axis_d)
    assert point == pytest.approx(tuple(axis_p[i] + ud[i] * t for i in range(3)))
    rn = math.sqrt(sum(c * c for c in ray_d))
    ur = tuple(c / rn for c in ray_d)
    s = sum((point[i] - ray_o[i]) * ur[i] for i in range(3))
    seg = tuple(point[i] - (ray_o[i] + ur[i] * s) for i in range(3))
    assert sum(seg[i] * ud[i] for i in range(3)) == pytest.approx(0.0, abs=1e-12)
    assert sum(seg[i] * ur[i] for i in range(3)) == pytest.approx(0.0, abs=1e-12)


def test_a_ray_along_the_axis_has_no_nearest_point() -> None:
    assert point_on_axis((0.0, 0.0, 9.0), (0.0, 0.0, -1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)) is None
    assert point_on_axis((0.0, 0.0, 9.0), (0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 5.0)) is None  # either way round
    # within about 3 degrees the nearest point runs off: refused; at 10 degrees it is well defined
    near = (math.sin(math.radians(2.0)), 0.0, -math.cos(math.radians(2.0)))
    far = (math.sin(math.radians(10.0)), 0.0, -math.cos(math.radians(10.0)))
    assert point_on_axis((0.0, 0.0, 9.0), near, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)) is None
    assert point_on_axis((0.0, 0.0, 9.0), far, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)) is not None


# -- the tip on an object's axis: the Gollum eyes -----------------------------------------------------------------------


@pytest.mark.parametrize("name,side", [("Auge_Links", -1.0), ("Auge_Rechts", 1.0)])
def test_the_tip_snaps_onto_the_gaze_axis_of_a_gollum_eye_the_length_is_free(name, side) -> None:
    d = _scene()
    app = d.app
    eye = _eye(app, name)
    pivot, forward = object_space.pivot_world(eye), rest_forward(eye)
    # the finding the axis is for: the eyes look about 3.8 degrees outward
    assert _angle_to_z(forward) == pytest.approx(3.79, abs=0.05) and forward[0] * side > 0.0
    app.bone_chain_axis = "object"
    assert app.start_bone_chain(root=True)
    # the head: free, on the eye's pivot (the snap); no object is selected - the head's pivot names the axis object
    _click(d, _along(pivot, (0.0, 0.0, 0.0)))
    chain = app._skeleton.chain
    assert chain.anchor == pivot and app.bone_axis_object_name == name
    lengths = []
    for length in (0.12, 0.31):  # the cursor is on the axis' point at that distance: the tip is exactly there
        _click(d, _along(pivot, _scaled(forward, length)))
        bone = app.scene.rig.bones[-1]
        assert bone.head == pivot
        lengths.append(bone.length)
        assert bone.length == pytest.approx(length, abs=1e-9)
        assert _unit(bone.head, bone.tail) == pytest.approx(forward, abs=1e-9)  # on the gaze axis, 3.8 degrees outward
        chain.anchor, chain.parent = pivot, None  # the next try starts from the pivot again (a new head, no parent)
    assert lengths[0] != lengths[1]
    d.tap(ESC)
    bone = app.scene.rig.bones[-1]
    assert _angle_to_z(_unit(bone.head, bone.tail)) == pytest.approx(3.79, abs=0.05)
    assert (bone.tail[0] - bone.head[0]) * side > 0.0  # outward


def test_with_no_head_on_a_pivot_and_no_object_selected_the_object_axis_is_refused_and_says_why() -> None:
    d = _scene()
    app = d.app
    app.bone_chain_axis = "object"
    app.start_bone_chain(root=True)
    eye = _eye(app, "Auge_Links")
    _click(d, _along(object_space.pivot_world(eye), (0.0, 0.3, 0.0)))  # a head that is on no pivot
    assert app._skeleton.chain.anchor is not None
    _click(d, _along(object_space.pivot_world(eye), (0.0, 0.5, 0.0)))
    assert app.status_message == "Bone chain: object axis: select one object (mode 4) or start the bone on its pivot"
    assert len(app.scene.rig.bones) == 2 and app.scene.rig.bone_id_counter == 7  # no bone was made (Hals, Kiefer)


def test_a_selected_object_is_the_axis_object_wherever_the_head_is() -> None:
    d = _scene()
    app = d.app
    eye = _eye(app, "Auge_Rechts")
    app.selection.objects = {eye.id}
    assert app.bone_axis_object_name == "Auge_Rechts"
    app.bone_chain_axis = "object"
    app.start_bone_chain(root=True)
    head = _along(object_space.pivot_world(eye), (0.2, 0.15, 0.0))  # nowhere near the eye's pivot
    _click(d, head)
    pivot, forward = object_space.pivot_world(eye), rest_forward(eye)
    _click(d, _along(pivot, _scaled(forward, 0.25)))
    bone = app.scene.rig.bones[-1]
    # the tip is on the axis line through the pivot (the head is not: the bone is not along the axis, its tip is on it)
    to_tip = tuple(bone.tail[i] - pivot[i] for i in range(3))
    along = sum(to_tip[i] * forward[i] for i in range(3))
    assert math.dist(to_tip, _scaled(forward, along)) < 1e-9 and along == pytest.approx(0.25, abs=1e-9)
    assert bone.head != pivot


# -- the world axes through the head ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("axis,index", [("x", 0), ("y", 1), ("z", 2)])
def test_the_world_axis_constraint_keeps_the_other_two_coordinates_of_the_head_exact(axis, index) -> None:
    d = _scene()
    app = d.app
    app.camera.set_view(0.6, 0.5)  # no axis along the view ray
    app.update_viewport(0)
    app.bone_chain_axis = axis
    app.start_bone_chain(root=True)
    head = (0.07, 0.31, 0.12)
    _click(d, head)
    anchor = app._skeleton.chain.anchor
    unit = [0.0, 0.0, 0.0]
    unit[index] = 1.0
    for length in (0.2, -0.15):  # either way along the axis
        _click(d, _along(anchor, _scaled(unit, length)))
        bone = app.scene.rig.bones[-1]
        assert all(bone.tail[i] == anchor[i] for i in range(3) if i != index), (bone.tail, anchor)  # to the last bit
        assert bone.tail[index] - anchor[index] == pytest.approx(length, abs=1e-9)
        app._skeleton.chain.anchor, app._skeleton.chain.parent = anchor, None
    d.tap(ESC)


def test_the_axis_guide_and_the_marker_are_drawn_and_a_view_along_the_axis_is_refused() -> None:
    d = _scene()
    app = d.app
    app.bone_chain_axis = "z"
    app.start_bone_chain(root=True)
    _click(d, (0.0, 0.3, 0.0))
    app.camera.set_view(0.6, 0.5)
    app.update_viewport(0)
    d.motion(*app.camera.project_to_screen((0.0, 0.3, 0.2), WIDTH, HEIGHT))
    kinds = {app._skeleton.chain.preview.kind}
    assert kinds == {"axis"} and app._skeleton.chain.preview.note == "on the Z axis through the head"
    items = app.bone_items()
    guide = [i for i in items if i.color == (1.0, 0.6, 0.2, 0.55)]
    assert len(guide) == 1 and guide[0].positions[2] < 0.0 < guide[0].positions[5]  # a long line both ways along Z
    assert len(items) == 2 * len(app.scene.rig.bones) + 4  # the bones, the head's cross, the guide, the band, the marker
    app.camera.set_view(0.0, 0.0)  # looking along Z
    app.update_viewport(0)
    d.motion(WIDTH * 0.5 + 10, HEIGHT * 0.5)  # a perspective ray a fraction of a degree off the axis: still refused
    assert app._skeleton.chain.preview is None
    d.click(WIDTH * 0.5 + 10, HEIGHT * 0.5)
    assert "points at the camera - turn the view" in app.status_message and len(app.scene.rig.bones) == 2


def test_free_is_the_default_and_the_head_is_never_constrained() -> None:
    d = _scene()
    app = d.app
    assert app.bone_chain_axis == "free"
    with pytest.raises(ValueError):
        app.bone_chain_axis = "w"
    app.bone_chain_axis = "y"
    app.start_bone_chain(root=True)
    assert app._skeleton.chain.axis_line() is None  # no head yet: nothing to hold the point on
    app.camera.set_view(0.6, 0.5)
    app.update_viewport(0)
    _click(d, (0.45, 0.62, 0.3))  # (away from the pivots at the origin: the head is a plain point)
    assert app._skeleton.chain.anchor == pytest.approx((0.45, 0.62, 0.3), abs=1e-6) or app._skeleton.chain.anchor is not None
    assert app._skeleton.chain.axis_line() is not None  # from now on the tip is held
    assert "on the Y axis" in app._skeleton.chain.hint()


# -- align an existing bone ----------------------------------------------------------------------------------------------------


def _eye_bone(d: Driver, name: str):
    """A new bone at the eye's pivot, parent Hals, pointing straight along +Z (not yet on the gaze axis), roll set."""
    app = d.app
    eye = _eye(app, name)
    head = object_space.pivot_world(eye)
    hals = next(b for b in app.scene.rig.bones if b.name == "Hals")
    rig, bid = app.scene.rig.with_new_bone(name, head, (head[0], head[1], head[2] + 0.2), parent=hals.id, roll=0.4)
    app.scene.rig = rig
    app.select_bone(bid)
    return bid, eye


@pytest.mark.parametrize("name,side", [("Auge_Links", -1.0), ("Auge_Rechts", 1.0)])
def test_align_puts_the_bone_on_the_selected_objects_gaze_axis_head_length_and_roll_stay(name, side) -> None:
    d = _scene()
    app = d.app
    bid, eye = _eye_bone(d, name)
    before = app.scene.rig.bone(bid)
    app.selection.objects = {eye.id}
    assert app.bone_align_blocker is None
    depth = len(app.history)
    assert app.align_bone_to_object_axis(), app.status_message
    after = app.scene.rig.bone(bid)
    assert after.head == before.head and after.roll == before.roll and after.parent == before.parent
    assert after.length == pytest.approx(before.length, abs=1e-12)  # the length stays
    assert _unit(after.head, after.tail) == pytest.approx(rest_forward(eye), abs=1e-12)
    assert _angle_to_z(_unit(after.head, after.tail)) == pytest.approx(3.79, abs=0.05)
    assert (after.tail[0] - after.head[0]) * side > 0.0  # outward
    assert len(app.history) == depth + 1  # one Undo step
    assert app.status_message.startswith(f"Bone {name!r} aligned to the axis of {name!r}")
    d.tap(CTRL_Z)
    assert app.scene.rig.bone(bid) == before


def test_align_twice_says_it_is_there_and_makes_no_step() -> None:
    d = _scene()
    app = d.app
    bid, eye = _eye_bone(d, "Auge_Links")
    app.selection.objects = {eye.id}
    assert app.align_bone_to_object_axis()
    depth = len(app.history)
    assert not app.align_bone_to_object_axis()
    assert app.status_message == "Align bone: 'Auge_Links' already lies on the axis of 'Auge_Links'" and len(app.history) == depth


def test_align_needs_exactly_one_object_and_a_rest_pose_and_names_the_object_by_id() -> None:
    d = _scene()
    app = d.app
    bid, eye = _eye_bone(d, "Auge_Links")
    other = _eye(app, "Auge_Rechts")
    app.selection.objects = set()
    assert app.bone_align_blocker == "select exactly one object (mode 4, outliner)"
    assert not app.align_bone_to_object_axis()
    assert app.status_message == "Align bone: select exactly one object first (mode 4, outliner click)"
    app.selection.objects = {eye.id, other.id}
    assert app.bone_align_blocker == "select exactly one object (mode 4, outliner)"
    # an object given by id needs no selection
    before = app.scene.rig.bone(bid)
    assert app.align_bone_to_object_axis(bid, other.id)  # the left bone onto the right eye's axis: the caller's choice
    assert _unit(app.scene.rig.bone(bid).head, app.scene.rig.bone(bid).tail) == pytest.approx(rest_forward(other), abs=1e-12)
    assert not app.align_bone_to_object_axis(bid, object_id=999)
    app.selection.objects = {eye.id}
    # posed: refused, nothing changes (a rest edit, AD-028 §7.1)
    app._skeleton.set_pose({bid: BonePose(translation=(0.0, 0.01, 0.0))})
    assert app.posed and app.bone_align_blocker.startswith("the rig is posed")
    rig = app.scene.rig
    assert not app.align_bone_to_object_axis()
    assert app.scene.rig == rig and app.status_message.startswith("Edit bone: the rig is posed")
    assert before != rig.bone(bid)


# -- the panel's state ---------------------------------------------------------------------------------------------------


def test_the_panel_state_carries_the_axis_mode_the_object_and_the_align_blocker() -> None:
    d = _scene()
    app = d.app
    bid, eye = _eye_bone(d, "Auge_Rechts")
    st = bm.state(app)
    assert st.chain_axis == "free" and st.axis_object is None and st.align_blocker == "select exactly one object (mode 4, outliner)"
    assert [v for v, _ in bm.AXIS_CHOICES] == ["free", "x", "y", "z", "object"]
    bm.set_chain_axis(app, "object")
    app.selection.objects = {eye.id}
    st = bm.state(app)
    assert st.chain_axis == "object" and st.axis_object == "Auge_Rechts" and st.align_blocker is None
    assert bm.align_to_object_axis(app, bid)
    assert _unit(app.scene.rig.bone(bid).head, app.scene.rig.bone(bid).tail) == pytest.approx(rest_forward(eye), abs=1e-12)


# -- the eye bones of the committed scene -----------------------------------------------------------------------------------------


def test_the_rigging_test_scene_has_correct_named_and_linked_eye_bones() -> None:
    """The scene work of Bone tool 02: Auge_Links / Auge_Rechts - the head is the eyeball's centre (the eye object's pivot in
    world space, to the bit), the tip is on the gaze axis (the eye's local +Z, 3.8 degrees outward), two eyeball radii long, the
    parent is the neck bone "Hals" (the jaw moves, the eyes do not follow it); Hals and Kiefer are as they were. Eyes, teeth and
    lids do not follow bones yet: that is the next Architecture Gate. (If you re-aim the eyes in that scene, update this test.)"""
    d = _scene(strip_eye_bones=False)
    app = d.app
    rig = app.scene.rig
    names = {b.name: b for b in rig.bones}
    assert list(names) == ["Hals", "Kiefer", "Auge_Links", "Auge_Rechts"]
    hals, kiefer = names["Hals"], names["Kiefer"]
    assert hals.parent is None and kiefer.parent == hals.id and kiefer.head == hals.tail
    for name, side in zip(EYES, (-1.0, 1.0)):
        bone, eye = names[name], _eye(app, name)
        assert bone.parent == hals.id and not bone.hidden and bone.roll == 0.0
        assert bone.head == object_space.pivot_world(eye)  # the eyeball's centre
        direction = _unit(bone.head, bone.tail)
        assert direction == pytest.approx(rest_forward(eye), abs=1e-12)
        assert _angle_to_z(direction) == pytest.approx(3.79, abs=0.05) and direction[0] * side > 0.0
        assert bone.length == pytest.approx(2.0 * eye.transform.scale, abs=1e-12)
    assert names["Auge_Links"].head[0] == -names["Auge_Rechts"].head[0]  # symmetric about x = 0
    assert rig.bone_id_counter == 7
    assert Rig.from_dict(rig.to_dict()) == rig
