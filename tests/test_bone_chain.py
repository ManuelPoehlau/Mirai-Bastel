"""Bone tool 01 (2026-11-17): the chain-click bone tool and the snap to an object's pivot (`mirai.controllers.bone_chain`,
`mirai.pivot.snap_candidates`, AD-028 addendum 2026-11-17), headless in the AD-027 scenario driver.

The click rule (head, then a tail per click; each bone one Undo step; parent = the previous bone), Undo / Redo with a
pending head, Esc, branching from the current bone / a bone's tail / a new root, the preview, what the session lets
through (navigation yes, other commands refused silently), the refusals to start, and the snap: object pivots (the
Gollum eyeball's centre, within tolerance), bone ends, Shift = mesh point, the symmetry plane, the Working Pivot's Ctrl.
"""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from core import SelectionMode
from mirai import object_space
from mirai.interaction import commands
from mirai.interaction.session import RunContext
from mirai.pivot import nearest_screen_point, snap_candidates
from tests.interaction_trace import CTRL_Y, CTRL_Z, ESC, HEIGHT, OVERLAYS, WIDTH, Driver, _frame, key
from tests.rig_support import E, POSE_MODE, head_driver, hold, rig_head


def _scene_driver(name: str) -> Driver:
    from pathlib import Path

    d = Driver("cube")
    app = d.app
    app.load_scene("file", scene_path=Path(__file__).resolve().parent.parent / "scenes" / f"{name}.mirai.json", **OVERLAYS)
    app.set_viewport_size(WIDTH, HEIGHT)
    _frame(app)
    app.camera.set_view(0.0, 0.0)
    app.update_viewport(0)
    return d


def _cube() -> Driver:
    d = Driver("cube")
    d.app.set_viewport_size(WIDTH, HEIGHT)
    _frame(d.app)
    d.app.camera.set_view(0.0, 0.0)
    d.app.update_viewport(0)
    return d


def _off_mesh_points(app, count: int, y: float = 0.0):
    """World points beside the cube at the camera target's depth: a click there hits no mesh and takes the plane facing the
    camera through the target (or the pending head), so it lands exactly where it projects."""
    mesh = app.scene.mesh
    xs = [mesh.vertex_position(v)[0] for v in mesh.all_vertex_ids()]
    z = app.camera.target[2]
    right = max(xs) * 1.8
    return [(right, y + 0.35 * i * max(xs), z) for i in range(count)]


def _click_world(d: Driver, point, modifiers=()) -> None:
    x, y = d.app.camera.project_to_screen(point, WIDTH, HEIGHT)
    d.motion(x, y)
    d.click(x, y, modifiers=modifiers)


# -- the click rule ----------------------------------------------------------------------------------------------


def test_each_click_makes_a_bone_one_undo_step_and_the_parent_is_the_previous_bone() -> None:
    d = _cube()
    app = d.app
    depth = len(app.history)
    assert app.start_bone_chain(root=True)
    assert app.interaction_owner == "bonechain" and app.bone_chain_active
    a, b, c = _off_mesh_points(app, 3)
    _click_world(d, a)
    assert app.scene.rig is None and len(app.history) == depth  # a head is no bone and no history entry
    _click_world(d, b)
    _click_world(d, c)
    first, second = app.scene.rig.bones
    assert (first.parent, second.parent) == (None, first.id)
    assert second.head == first.tail  # the next bone starts where the last one ended, to the bit
    assert math.dist(first.head, a) < 1e-6 and math.dist(first.tail, b) < 1e-6 and math.dist(second.tail, c) < 1e-6
    assert len(app.history) == depth + 2  # one step per bone
    assert app.current_bone == second.id
    assert app.rig_status_text().endswith("bone chain")
    from hud import hud_state

    assert hud_state(app).active == "Bone chain"
    d.tap(ESC)
    assert hud_state(app).active is None


def test_a_head_alone_is_dropped_by_undo_before_an_earlier_step_is_taken_back() -> None:
    d = _cube()
    app = d.app
    app.rename_object(next(iter(app.scene.objects)), "Kopf")  # an earlier history step the chain must not eat
    depth = len(app.history)
    app.start_bone_chain(root=True)
    a, b = _off_mesh_points(app, 2)
    _click_world(d, a)
    chain = app._skeleton.chain
    assert chain.anchor is not None and chain.head_only
    d.tap(CTRL_Z)
    assert chain.anchor is None and len(app.history) == depth  # the head went, no history step was undone
    assert app.status_message == "Bone chain: head dropped - click a new head"
    _click_world(d, a)
    _click_world(d, b)
    assert len(app.scene.rig.bones) == 1 and len(app.history) == depth + 1


def test_undo_and_redo_move_the_pending_head_with_the_history() -> None:
    d = _cube()
    app = d.app
    app.start_bone_chain(root=True)
    a, b, c = _off_mesh_points(app, 3)
    for p in (a, b, c):
        _click_world(d, p)
    chain = app._skeleton.chain
    first, second = app.scene.rig.bones
    d.tap(CTRL_Z)  # the second bone goes: its head (= the first tail) is the pending head again, the parent the first bone
    assert app.scene.rig.bones == (first,)
    assert chain.anchor == second.head and chain.parent == first.id
    d.tap(CTRL_Y)  # redone: the chain continues from its tail
    assert app.scene.rig.bones == (first, second)
    assert chain.anchor == second.tail and chain.parent == second.id
    d.tap(CTRL_Z)
    d.tap(CTRL_Z)  # both bones gone: the first bone's head is pending
    assert app.scene.rig is None or app.scene.rig.bones == ()
    assert chain.anchor == first.head and chain.head_only
    # a click now makes a new bone from that head; the redo stack of the old ones is gone with the history rules
    _click_world(d, b)
    (fresh,) = app.scene.rig.bones
    assert fresh.head == first.head and fresh.tail == pytest.approx(b, abs=1e-6)
    assert not app.history.can_redo()


def test_esc_ends_the_chain_the_bones_stay_and_the_pending_head_is_dropped() -> None:
    d = _cube()
    app = d.app
    app.start_bone_chain(root=True)
    a, b, c = _off_mesh_points(app, 3)
    for p in (a, b, c):
        _click_world(d, p)
    bones = app.scene.rig.bones
    d.tap(ESC)
    assert not app.bone_chain_active and app.interaction_owner is None
    assert app.scene.rig.bones == bones
    assert app.status_message == "Bone chain ended (2 bones made; each is one Undo step)"
    # the same through the panel's entry
    app.start_bone_chain(root=True)
    assert app.end_bone_chain() and not app.bone_chain_active
    assert not app.end_bone_chain()
    # the Undo steps are the bones: each one separately
    d.tap(CTRL_Z)
    d.tap(CTRL_Z)
    assert app.scene.rig is None or app.scene.rig.bones == ()


def test_a_click_on_the_head_is_refused_no_zero_length_bone() -> None:
    d = _cube()
    app = d.app
    app.start_bone_chain(root=True)
    (a,) = _off_mesh_points(app, 1)
    _click_world(d, a)
    _click_world(d, a)
    assert app.scene.rig is None and app.bone_chain_active
    assert app.status_message == "Bone chain: that is the head - a bone needs a length"


def test_a_drag_is_no_click_and_alt_drag_still_orbits() -> None:
    d = _cube()
    app = d.app
    app.start_bone_chain(root=True)
    a, b = _off_mesh_points(app, 2)
    x, y = app.camera.project_to_screen(a, WIDTH, HEIGHT)
    d.motion(x, y)
    d.press("LEFT")
    d.nudge(30, 0)  # past the click threshold
    d.release("LEFT")
    assert app._skeleton.chain.anchor is None  # no head from a drag
    yaw = app.camera.yaw if hasattr(app.camera, "yaw") else None
    view = app.camera.build_view_matrix() if hasattr(app.camera, "build_view_matrix") else None
    d.motion(WIDTH * 0.5, HEIGHT * 0.5)
    d.press("LEFT", ("alt",))
    d.motion(WIDTH * 0.5 + 90, HEIGHT * 0.5)
    d.release("LEFT")
    d.modifiers_to(())
    assert app._skeleton.chain.anchor is None and app.scene.rig is None  # navigation, no bone
    after = app.camera.build_view_matrix() if view is not None else None
    assert view is None or after != view, "Alt+LMB orbited the camera"
    assert app.bone_chain_active
    del yaw


# -- what runs underneath, what refuses to start ----------------------------------------------------------------------


def test_only_navigation_view_undo_and_cancel_run_underneath_everything_else_is_silent() -> None:
    d = _cube()
    app = d.app
    app.selection.mode = SelectionMode.VERTEX
    app.start_bone_chain(root=True)
    status = app.status_message
    for command in (commands.MOVE, commands.EXTRUDE, commands.DELETE, commands.POSE_MODE, commands.BONE_ADD,
                    commands.BONE_DELETE, commands.SELECT, commands.SELECT_LINKED, commands.SET_OBJECT_MODE):
        refusal = app.can_run(command, RunContext("api"))
        assert refusal is not None and refusal.text is None, command  # refused, silently
    for command in (commands.CANCEL, commands.UNDO, commands.REDO, commands.ORBIT, commands.PAN, commands.ZOOM,
                    commands.TOGGLE_ORTHO, commands.CYCLE_DISPLAY_MODE):
        assert app.can_run(command, RunContext("api")) is None, command
    d.tap(key("w"))  # a key: nothing starts, the status line is not touched
    d.key_up("w") if "w" in d.keys_down else None
    assert app.interaction_owner == "bonechain" and app.status_message == status


def test_the_chain_will_not_start_posed_nor_under_a_running_interaction_and_says_why() -> None:
    d = head_driver()
    rig_head(d)
    app = d.app
    assert app.bone_chain_blocker is None
    d.tap(POSE_MODE)
    hold(d, E, ((30, 5), (10, 0)))
    assert app.posed
    assert app.bone_chain_blocker == "the rig is posed - 6 = rest pose first"
    assert not app.start_bone_chain()
    assert app.status_message == "Bone chain: the rig is posed - 6 = rest pose first"
    d.tap(key("6"))
    assert app.bone_chain_blocker is None and app.start_bone_chain()
    assert app.bone_chain_blocker == "not while the bonechain interaction runs"
    assert not app.start_bone_chain()  # a second chain: refused, one session in the slot
    assert not app.save_scene_file("/tmp/never_written.mirai.json") and "bonechain" in app.status_message


def test_a_loaded_scene_and_a_shutdown_end_the_chain() -> None:
    d = _cube()
    app = d.app
    app.start_bone_chain(root=True)
    app.load_scene("cube", **OVERLAYS)
    assert not app.bone_chain_active and app.interaction_owner is None
    app.start_bone_chain(root=True)
    app.shutdown()
    assert not app.bone_chain_active


# -- the first bone's parent: the current bone, a bone's tail, a new root ---------------------------------------------


def _two_bones(d: Driver):
    app = d.app
    app.start_bone_chain(root=True)
    a, b, c = _off_mesh_points(app, 3)
    for p in (a, b, c):
        _click_world(d, p)
    d.tap(ESC)
    return app.scene.rig.bones, (a, b, c)


def test_branching_the_first_bone_is_a_child_of_the_current_bone_and_a_root_on_demand() -> None:
    d = _cube()
    app = d.app
    (first, second), (a, b, c) = _two_bones(d)
    assert app.select_bone(first.id)
    assert app.start_bone_chain()  # the current bone is the first: a new chain branches off it
    assert app._skeleton.chain.parent == first.id
    assert app.status_message.startswith("Bone chain: click the head (child of 'Bone 1'")
    d1, d2 = _off_mesh_points(app, 2, y=-1.2 * 0.35)
    _click_world(d, d1)
    _click_world(d, d2)
    branch = app.scene.rig.bones[-1]
    assert branch.parent == first.id and branch.head != first.tail  # a free head: a jaw hangs off the skull's hinge
    d.tap(ESC)
    assert app.start_bone_chain(root=True)
    assert app._skeleton.chain.parent is None
    d3, d4 = _off_mesh_points(app, 2, y=-2.0 * 0.35)
    _click_world(d, d3)
    _click_world(d, d4)
    assert app.scene.rig.bones[-1].parent is None
    d.tap(ESC)


def test_a_first_click_on_a_bones_tail_continues_that_bone_exactly() -> None:
    d = _cube()
    app = d.app
    (first, second), (a, b, c) = _two_bones(d)
    app.select_bone(first.id)  # the current bone is the first one - but the click is on the second one's tail
    assert app.start_bone_chain()
    chain = app._skeleton.chain
    assert chain.parent == first.id
    x, y = app.camera.project_to_screen(second.tail, WIDTH, HEIGHT)
    d.motion(x + 4, y + 3)  # near, not exact: it snaps
    assert chain.preview.kind == "tail" and chain.preview.bone == second.id
    d.click(x + 4, y + 3)
    assert chain.parent == second.id and chain.anchor == second.tail
    (nxt,) = _off_mesh_points(app, 1, y=1.05)  # (the third point of `_two_bones` was y=0.7: the pending head)
    _click_world(d, nxt)
    assert app.scene.rig.bones[-1].parent == second.id and app.scene.rig.bones[-1].head == second.tail


# -- the preview -------------------------------------------------------------------------------------------------------


def test_the_preview_shows_the_pending_bone_and_what_the_next_click_snaps_to() -> None:
    d = _cube()
    app = d.app
    app.start_bone_chain(root=True)
    a, b = _off_mesh_points(app, 2)
    d.leave()  # (the cursor of the driver starts in the window: begin already shows a marker there)
    plain = len(app.bone_items())
    assert plain == 0
    xa, ya = app.camera.project_to_screen(a, WIDTH, HEIGHT)
    d.motion(xa, ya)
    assert len(app.bone_items()) == plain + 1  # the marker where the head would go
    _click_world(d, a)
    xb, yb = app.camera.project_to_screen(b, WIDTH, HEIGHT)
    d.motion(xb, yb)
    items = app.bone_items()
    assert len(items) == plain + 3  # the head's cross, the band head -> cursor, the marker at the cursor
    band = [i for i in items if i.primitive == "lines" and len(i.positions) == 6][-1]
    assert band.positions[:3] == pytest.approx(a, abs=1e-6)
    d.leave()
    assert len(app.bone_items()) == plain + 1  # the cursor left the window: the head's cross stays, nothing else


# -- the snap: object pivots, bone ends, the mesh, the symmetry plane ------------------------------------------------------


@pytest.mark.parametrize("scene,eyes", [("Gollum_Head_03", ("Eye", "Eye.001")), ("Gollum_Head_01", ("Eye_L", "Eye_R"))])
def test_the_snap_to_an_eye_objects_pivot_is_the_eyeballs_centre(scene, eyes) -> None:
    """The acceptance of the handoff: with the Gollum eye objects the snapped point equals the eyeball centre within tolerance.
    Finding behind it: the eye objects carry pivot (0, 0, 0) and the placement in the transform; the eye mesh is built around
    its origin (a sphere of radius 1 - the iris eye's cornea bulges to +z only), so the pivot's world position IS the centre."""
    d = _scene_driver(scene)
    app = d.app
    assert app.start_bone_chain(root=True)
    chain = app._skeleton.chain
    for name in eyes:
        obj = next(o for o in app.scene.objects.values() if o.name == name)
        assert obj.pivot == (0.0, 0.0, 0.0)
        # the eyeball's centre by the mesh: the sphere's extent is symmetric about the origin in x, y and in -z
        pts = [obj.mesh.vertex_position(v) for v in obj.mesh.all_vertex_ids()]
        for axis in (0, 1):
            assert min(p[axis] for p in pts) == pytest.approx(-max(p[axis] for p in pts), abs=1e-6)
        assert min(p[2] for p in pts) == pytest.approx(-1.0, abs=1e-6)
        centre = object_space.to_world(obj, (0.0, 0.0, 0.0))
        assert centre == pytest.approx(obj.transform.translation, abs=1e-12)
        assert object_space.pivot_world(obj) == pytest.approx(centre, abs=1e-12)
        # a click a few pixels beside the centre lands exactly on it
        x, y = app.camera.project_to_screen(centre, WIDTH, HEIGHT)
        d.motion(x + 6, y - 5)
        assert chain.preview is not None and chain.preview.kind == "pivot"
        assert chain.preview.note == f"pivot of {name!r}"
        assert math.dist(chain.preview.world, centre) <= 1e-9
    # the head on the left eye, the tail on the right eye: a bone whose ends are the two eyeball centres
    left = next(o for o in app.scene.objects.values() if o.name == eyes[0])
    right = next(o for o in app.scene.objects.values() if o.name == eyes[1])
    for obj in (left, right):
        x, y = app.camera.project_to_screen(object_space.pivot_world(obj), WIDTH, HEIGHT)
        d.motion(x + 3, y + 2)
        d.click(x + 3, y + 2)
    d.tap(ESC)
    bone = app.scene.rig.bones[-1]
    assert math.dist(bone.head, object_space.pivot_world(left)) <= 1e-9
    assert math.dist(bone.tail, object_space.pivot_world(right)) <= 1e-9


def test_pivot_world_is_the_placement_matrix_applied_to_the_pivot_for_any_placement() -> None:
    """`pivot_world` = `placement_matrix(transform, pivot) · pivot`, also with a rotation, a scale and an off-origin pivot."""
    from core import ObjectTransform

    d = _cube()
    app = d.app
    obj = next(iter(app.scene.objects.values()))
    obj.pivot = (0.2, -0.1, 0.3)
    c, s = math.cos(0.7), math.sin(0.7)
    obj.transform = ObjectTransform(translation=(1.0, 2.0, -0.5), rotation=((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c)), scale=1.6)
    m = object_space.placement_matrix(obj.transform, obj.pivot)
    p = obj.pivot
    applied = tuple(m[0 + row] * p[0] + m[4 + row] * p[1] + m[8 + row] * p[2] + m[12 + row] for row in range(3))
    assert object_space.pivot_world(obj) == pytest.approx(applied, abs=1e-12)
    assert object_space.pivot_world(obj) == pytest.approx((1.2, 1.9, -0.2), abs=1e-12)  # translation + pivot


def test_teeth_and_groups_are_plain_origins_no_special_case() -> None:
    """A tooth's pivot is its object origin (its mesh is built around it), a group's is the origin of an empty object: both are
    candidates like any other, nothing is singled out."""
    d = _scene_driver("Gollum_Head_03")
    app = d.app
    kinds = {name: key_ for (key_, _id, name), _p in snap_candidates(app.scene)}
    assert kinds["tooth"] == "pivot" and kinds["Eyes"] == "pivot" and kinds["Eye"] == "pivot"
    groups = [o for o in app.scene.objects.values() if len(list(o.mesh.all_vertex_ids())) == 0]
    assert groups and all(object_space.pivot_world(g) == pytest.approx(g.transform.translation) for g in groups)


def test_the_snap_has_a_radius_depth_plays_no_part_and_it_can_be_switched_off() -> None:
    d = _scene_driver("Gollum_Head_03")
    app = d.app
    app.start_bone_chain(root=True)
    chain = app._skeleton.chain
    eye = next(o for o in app.scene.objects.values() if o.name == "Eye")
    x, y = app.camera.project_to_screen(object_space.pivot_world(eye), WIDTH, HEIGHT)
    assert chain.point_at(x + 11, y).kind == "pivot"  # inside 12 px
    assert chain.point_at(x + 30, y).kind != "pivot"  # outside
    app.bone_chain_snap = False
    assert not app.bone_chain_snap and chain.point_at(x + 3, y).kind != "pivot"
    app.bone_chain_snap = True
    # a hidden object offers no pivot (hiding is refused underneath a running chain, so end it first)
    assert not app.set_objects_hidden([eye.id], True)
    app.end_bone_chain()
    assert app.set_objects_hidden([eye.id], True)
    assert all(name != "Eye" for (_k, _i, name), _p in snap_candidates(app.scene))


def test_nearest_screen_point_takes_the_earlier_candidate_on_an_exact_tie() -> None:
    class Cam:
        def project_to_screen(self, p, w, h):
            return (p[0], p[1])

    hit = nearest_screen_point(Cam(), [("tail", (10.0, 10.0, 0)), ("pivot", (10.0, 10.0, 0)), ("far", (90.0, 0.0, 0))],
                               11.0, 10.0, 100, 100, radius_px=5.0)
    assert hit[0] == "tail"
    assert nearest_screen_point(Cam(), [("a", (10.0, 10.0, 0))], 20.0, 10.0, 100, 100, radius_px=5.0) is None


def test_on_the_symmetry_plane_a_click_lands_on_it_exactly_and_shift_takes_a_vertex() -> None:
    d = head_driver()  # symmetry X
    app = d.app
    mesh = app.scene.mesh
    app.start_bone_chain(root=True)
    chain = app._skeleton.chain
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    x, y = app.camera.project_to_screen((0.0, min(ys) + 0.5 * (max(ys) - min(ys)), 0.0), WIDTH, HEIGHT)
    point = chain.point_at(x + 4, y)  # a few pixels off the plane's projection: V-3 snaps onto it
    assert point.kind == "plane" and point.world[0] == 0.0
    assert point.note == "on the symmetry plane"
    # Shift = the vertex / edge under the cursor (the Knife's pick), exactly its position: a front vertex away from the plane
    front = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[2] > 0.3 and abs(mesh.vertex_position(v)[0]) > 0.25]
    v = front[len(front) // 2]
    vx, vy = app.camera.project_to_screen(mesh.vertex_position(v), WIDTH, HEIGHT)
    snapped = chain.point_at(vx, vy, mesh_snap=True)
    assert snapped is not None and math.dist(snapped.world, mesh.vertex_position(v)) <= 1e-9, (snapped.world, mesh.vertex_position(v))
    assert snapped.kind == "point"


def test_a_chain_down_the_middle_of_a_symmetric_head_is_exactly_on_the_plane() -> None:
    d = head_driver()
    app = d.app
    mesh = app.scene.mesh
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    lo, hi = min(ys), max(ys)
    app.start_bone_chain(root=True)
    for f in (0.2, 0.45, 0.7):
        _click_world(d, (0.0, lo + f * (hi - lo), 0.0))
    d.tap(ESC)
    assert len(app.scene.rig.bones) == 2
    assert all(b.head[0] == 0.0 and b.tail[0] == 0.0 for b in app.scene.rig.bones)


# -- the Working Pivot: Ctrl = object pivot / bone end ---------------------------------------------------------------


def test_the_working_pivot_places_exactly_on_an_object_pivot_with_ctrl() -> None:
    d = _scene_driver("Gollum_Head_03")
    app = d.app
    app.selection.mode = SelectionMode.VERTEX
    app.selection.clear()
    eye = next(o for o in app.scene.objects.values() if o.name == "Eye")
    centre = object_space.pivot_world(eye)
    x, y = app.camera.project_to_screen(centre, WIDTH, HEIGHT)
    p = key("p")
    d.key_down(p)
    d.click(x + 5, y + 4, modifiers=("ctrl",))
    d.key_up("p")
    pivot = app.working_pivot
    assert pivot is not None
    world = object_space.to_world(app.scene.edit_object, pivot.position)
    assert math.dist(world, centre) <= 1e-9
    # without Ctrl the same click places it inside the mesh under the cursor, not on the eyeball's centre
    d.key_down(p)
    d.click(x + 5, y + 4)
    d.key_up("p")
    world = object_space.to_world(app.scene.edit_object, app.working_pivot.position)
    assert math.dist(world, centre) > 1e-3
