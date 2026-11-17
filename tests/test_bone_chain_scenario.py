"""Bone tool 01 (2026-11-17): the jaw scenario with the bone made by the chain tool - in the AD-027 scenario style (named,
readable steps, every step one or a few events through the public entry points, headless, the head basemesh with
symmetry X; `tests/test_jaw_scenario.py` is the pattern).

group "Jaw" -> the chain tool (hinge, chin) -> weights from the group (the panel's value path, falloff width) -> edit the
bone after binding (the hinge moves) -> rotate the jaw (E, X) -> Undo to the start and Redo to the end -> save -> load.

What holds: the bone is on the symmetry plane to the last bit (the symmetric weights allow it); the weights are keyed by
`BoneId` and are byte-identical before and after a bone edit; the rest display is bit-identical (the mesh is not touched);
the posed surface is `skinning.evaluate` of the new rest frame; Undo / Redo exact; rig, weights and bone survive save / load.
"""

from __future__ import annotations

import math

import tests._bootstrap  # noqa: F401
from core import Mesh
from mirai.skinning import evaluate
from tests.interaction_trace import CTRL_Y, CTRL_Z, ESC, HEIGHT, OVERLAYS, WIDTH, Driver, key
from tests.rig_support import E, POSE_MODE, POSE_TOGGLE, head_driver, hold, jaw_faces, select_faces, weights
from tests.test_jaw_scenario import (
    CTRL_ALT_N, CTRL_G, assert_symmetric_weights, assert_the_loop_follows_the_rules, mouth_corner,
)

X, I = key("x"), key("i")


# -- the steps ---------------------------------------------------------------------------------------------------


def group_jaw(d: Driver) -> set:
    app = d.app
    faces = jaw_faces(app.scene.mesh)
    select_faces(d, faces)
    d.tap(CTRL_G)
    while app.active_region != "Jaw":
        d.tap(CTRL_ALT_N)
    return faces


def _click_at(d: Driver, world_point) -> None:
    x, y = d.app.camera.project_to_screen(world_point, WIDTH, HEIGHT)
    d.motion(x, y)  # the preview follows the cursor first, as with a hand
    d.click(x, y)


def hinge_and_chin(mesh, faces) -> tuple:
    """Two points on the symmetry plane: the hinge at 45 % of the head's height and the jaw's centre (screen targets;
    the tool places them inside the mesh under the cursor, on the plane)."""
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    hinge = (0.0, min(ys) + 0.45 * (max(ys) - min(ys)), 0.0)
    pts = [mesh.vertex_position(v) for f in faces for v in mesh.face_vertices(f)]
    chin = (0.0, sum(p[1] for p in pts) / len(pts), sum(p[2] for p in pts) / len(pts))
    return hinge, chin


def place_the_jaw_bone_with_the_chain_tool(d: Driver, faces):
    """Start the chain as a root, click the hinge (head) and the chin (tail), Esc: one bone, one Undo step."""
    app = d.app
    depth = len(app.history)
    assert app.start_bone_chain(root=True), app.status_message
    hinge, chin = hinge_and_chin(app.scene.mesh, faces)
    _click_at(d, hinge)
    assert len(app.history) == depth, "the head alone is no history entry"
    _click_at(d, chin)
    d.tap(ESC)
    assert not app.bone_chain_active
    (bone,) = app.scene.rig.bones
    assert len(app.history) == depth + 1
    assert bone.name == "Bone 1" and bone.parent is None
    assert abs(bone.head[0]) <= 1e-12 and abs(bone.tail[0]) <= 1e-12  # on the plane: symmetric weights allowed
    return bone


def weights_from_the_group(d: Driver, width_percent: float = 15.0) -> None:
    assert d.app.weights_from_group_value(width_percent), d.app.status_message
    assert d.app.status_message.endswith("committed (Ctrl+Z takes it back)")


def edit_the_bone_after_binding(d: Driver, bone):
    """The hinge moves up and back by hand (the panel's numbers): the weights and the rest shape stay."""
    app = d.app
    mesh = app.scene.mesh
    before_weights = weights(mesh)
    before_mesh = mesh.export_state()
    head = (0.0, bone.head[1] + 0.05, bone.head[2] - 0.03)
    assert app.edit_bone(bone.id, head=head), app.status_message
    moved = app.scene.rig.bone(bone.id)
    assert moved.head == head and moved.tail == bone.tail and moved.id == bone.id
    assert weights(mesh) == before_weights, "weights are keyed by BoneId: a bone edit leaves them alone"
    assert mesh.export_state() == before_mesh, "the rest shape is untouched"
    return moved


def loop_insert_at_the_mouth_corner(d: Driver, bone) -> None:
    """A topology edit after the bone edit: `2`, an edge at the corner, I. The bone stays as it is, the new points get the
    weights by the rule (the midpoint blend, W1-W4), and the layer and the mesh stay valid."""
    app = d.app
    mesh = app.scene.mesh
    corner = mouth_corner(mesh)
    ref = Mesh.from_state(mesh.export_state())
    d.tap(key("2"))
    app.selection.edges = {max(mesh.vertex_edges(corner), key=lambda e: int(e))}
    d.tap(I)
    assert app.status_message.startswith("Loop Insert"), app.status_message
    assert assert_the_loop_follows_the_rules(ref, mesh) >= 2
    assert_symmetric_weights(mesh)
    assert app.scene.rig.bones == (bone,)
    d.tap(key("1"))


def rotate_the_jaw(d: Driver) -> None:
    """The view turned aside, pose mode, X, E held (as the jaw scenario)."""
    d.motion(WIDTH * 0.5, HEIGHT * 0.5)
    d.press("LEFT", ("alt",))
    d.motion(WIDTH * 0.5 + 120, HEIGHT * 0.5)
    d.release("LEFT")
    d.modifiers_to(())
    d.motion(WIDTH * 0.65, HEIGHT * 0.45)
    d.tap(POSE_MODE)
    d.tap(X)
    hold(d, E, ((0, -25), (4, -20)))
    assert d.app.posed and d.app.status_message.startswith("Pose: 'Bone 1' rotated"), d.app.status_message


def assert_the_posed_surface_is_the_definition(d: Driver) -> None:
    app = d.app
    app.update_viewport(0)
    mesh = app.scene.mesh
    expected = evaluate(mesh, None, app.scene.rig, app.pose, None)
    surface = app.skin.provider.surface_mesh
    assert surface is not None
    assert all(tuple(surface.vertex_position(v)) == expected[v] for v in mesh.all_vertex_ids())
    moved = [v for v in mesh.all_vertex_ids() if math.dist(expected[v], mesh.vertex_position(v)) > 1e-6]
    assert moved and all(v in weights(mesh) for v in moved)


# -- the scenario --------------------------------------------------------------------------------------------


def run_chain_jaw_scenario(tmp_path, make_driver=head_driver) -> None:
    d = make_driver()
    app = d.app
    mesh = app.scene.mesh
    start = ({k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}, app.scene.rig)
    start_depth = len(app.history)
    faces = group_jaw(d)
    bone = place_the_jaw_bone_with_the_chain_tool(d, faces)
    weights_from_the_group(d)
    assert_symmetric_weights(mesh)
    bound = weights(mesh)
    assert bound and all(k == bone.id for value in bound.values() for k, _ in value)

    # the rest display before the edit: the mesh itself, no skin surface
    rest_positions = {v: tuple(mesh.vertex_position(v)) for v in mesh.all_vertex_ids()}
    moved = edit_the_bone_after_binding(d, bone)
    assert {v: tuple(mesh.vertex_position(v)) for v in mesh.all_vertex_ids()} == rest_positions
    assert evaluate(mesh, None, app.scene.rig, {}, None) == rest_positions  # at rest the evaluation is the rest shape

    loop_insert_at_the_mouth_corner(d, moved)
    bound = weights(mesh)  # (with the new loop's points)
    rest_positions = {v: tuple(mesh.vertex_position(v)) for v in mesh.all_vertex_ids()}
    rotate_the_jaw(d)
    assert_the_posed_surface_is_the_definition(d)
    # a bone edit is refused while posed, and nothing changes
    rig_before = app.scene.rig
    assert not app.edit_bone(moved.id, head=(0.0, 1.0, 0.0))
    assert app.status_message.startswith("Edit bone: the rig is posed") and app.scene.rig == rig_before
    # the jaw posed as before, in the new rest frame: rest and back
    d.tap(POSE_TOGGLE)
    assert not app.posed
    d.tap(POSE_TOGGLE)
    assert app.posed
    assert_the_posed_surface_is_the_definition(d)
    d.tap(key("1"))

    # Undo to the start, Redo to the end: exact (the pose is view state and never part of it)
    end = ({k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}, app.scene.rig)
    depth = len(app.history) - start_depth
    assert depth >= 5  # symmetry, group, bone, weights, the edit, the loop
    for _ in range(depth):
        d.tap(CTRL_Z)
    assert ({k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}, app.scene.rig) == start
    for _ in range(depth):
        d.tap(CTRL_Y)
    assert ({k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}, app.scene.rig) == end
    assert weights(mesh) == bound and app.scene.rig.bones == (moved,)

    # save -> load: bit-exact, at rest
    path = tmp_path / "chain_jaw.mirai.json"
    assert app.save_scene_file(path), app.status_message
    state = mesh.export_state()
    app.load_scene("file", scene_path=path, **OVERLAYS)
    assert app.scene.mesh.export_state() == state and app.scene.rig == end[1]
    assert weights(app.scene.mesh) == bound and app.pose == {} and not app.posed


def test_the_chain_jaw_scenario(tmp_path) -> None:
    run_chain_jaw_scenario(tmp_path)


def test_can_run_is_pure_through_the_chain_jaw_scenario(tmp_path) -> None:
    """AD-027 E5 (iv) on this scenario: every command from every source asked twice after every event - the same answer,
    the same observation (also while the chain session runs)."""
    from tests.test_interaction_structure import _PurityDriver

    made = []

    def make():
        d = head_driver(driver=_PurityDriver)
        made.append(d)
        return d

    run_chain_jaw_scenario(tmp_path, make)
    assert isinstance(made[0], _PurityDriver)


# -- the Gollum head: neck -> skull, the jaw and both eyes branch off the skull --------------------------------------------


def _gollum(name: str):
    from tests.test_bone_chain import _scene_driver

    return _scene_driver(name)


def _click_on(d: Driver, point, jitter=(0.0, 0.0)) -> None:
    x, y = d.app.camera.project_to_screen(point, WIDTH, HEIGHT)
    d.motion(x + jitter[0], y + jitter[1])
    d.click(x + jitter[0], y + jitter[1])


def test_the_gollum_head_chain_neck_skull_with_jaw_and_both_eyes_off_the_skull(tmp_path) -> None:
    """Manu's test points 1, 2 and 5 on `Gollum_Head_03` (`"rig": null`), headless: a chain neck -> skull by clicks; the jaw and
    both eye bones start from the skull (the current bone) - the eye bones with their head snapped onto the eye object's pivot
    (the eyeball's centre); Undo to the start and Redo to the end exact; save -> load exact."""
    from mirai import object_space

    d = _gollum("Gollum_Head_03")
    app = d.app
    assert app.scene.rig is None
    mesh = app.scene.mesh
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    lo, span = min(ys), max(ys) - min(ys)

    def at(f, z=0.0):
        return (0.0, lo + f * span, z)

    # 1. the chain neck -> skull: three clicks, two bones, one Undo step each
    assert app.start_bone_chain(root=True)
    for f in (0.12, 0.3, 0.62):
        _click_on(d, at(f))
    d.tap(ESC)
    neck, skull = app.scene.rig.bones
    assert (neck.parent, skull.parent) == (None, neck.id) and skull.head == neck.tail
    assert app.current_bone == skull.id

    # 2. the jaw: the skull is current, so the chain hangs off it; its head is the hinge (free, not the skull's tail)
    assert app.start_bone_chain()
    assert app._skeleton.chain.parent == skull.id
    _click_on(d, at(0.4))
    _click_on(d, at(0.22))
    d.tap(ESC)
    jaw = app.scene.rig.bones[-1]
    assert jaw.parent == skull.id and jaw.head != skull.tail

    # 3. the eyes: back on the skull; the head snaps onto the eye object's pivot, a few pixels off is still the exact centre
    eyes = {}
    for name in ("Eye", "Eye.001"):
        obj = next(o for o in app.scene.objects.values() if o.name == name)
        app.select_bone(skull.id)
        assert app.start_bone_chain()
        centre = object_space.pivot_world(obj)
        _click_on(d, centre, jitter=(5.0, -4.0))
        assert app._skeleton.chain.anchor == centre
        _click_on(d, (centre[0], centre[1] + 0.12, centre[2]), jitter=(0.0, 0.0))
        d.tap(ESC)
        bone = app.scene.rig.bones[-1]
        assert bone.parent == skull.id and bone.head == centre and bone.tail != bone.head
        eyes[name] = bone
    assert eyes["Eye"].head[0] < 0.0 < eyes["Eye.001"].head[0]  # the two eyeball centres, left and right

    rig = app.scene.rig
    assert [b.parent for b in rig.bones] == [None, neck.id, skull.id, skull.id, skull.id]
    assert len(rig.bones) == 5 and len({b.name for b in rig.bones}) == 5
    start_depth = len(app.history) - 5

    # Undo to the start, Redo to the end: exact; the rig is gone and comes back as it was
    for _ in range(5):
        d.tap(CTRL_Z)
    assert app.scene.rig is None or app.scene.rig.bones == ()
    for _ in range(5):
        d.tap(CTRL_Y)
    assert app.scene.rig == rig and len(app.history) == start_depth + 5

    # save -> load: the rig survives bit-exact (the pose and the chain are not saved)
    path = tmp_path / "gollum_chain.mirai.json"
    assert app.save_scene_file(path), app.status_message
    app.load_scene("file", scene_path=path, **OVERLAYS)
    assert app.scene.rig == rig and not app.bone_chain_active and app.pose == {}


def test_a_scene_with_a_bone_continues_from_it_gollum_head_01_has_a_hidden_neck() -> None:
    """`Gollum_Head_01` has one (hidden) bone "Neck": the current bone is it, so a new chain is its child; the Neck's
    hidden flag is not touched; the new bones are visible."""
    d = _gollum("Gollum_Head_01")
    app = d.app
    (neck,) = app.scene.rig.bones
    assert neck.name == "Neck" and neck.hidden
    assert app.start_bone_chain()
    assert app._skeleton.chain.parent == neck.id
    mesh = app.scene.mesh
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    lo, span = min(ys), max(ys) - min(ys)
    _click_on(d, (0.0, lo + 0.5 * span, 0.0))
    _click_on(d, (0.0, lo + 0.8 * span, 0.0))
    d.tap(ESC)
    skull = app.scene.rig.bones[-1]
    assert skull.parent == neck.id and not skull.hidden and app.scene.rig.bone(neck.id) == neck
