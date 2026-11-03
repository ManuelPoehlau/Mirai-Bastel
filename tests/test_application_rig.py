"""AD-028 T-6: the skeleton through `Application` (slice 3) - the bone commands with exact Undo (the weights rewrite
included), both weight gestures (Esc exact, commit = one step, Soft, symmetry on- and off-centre, mask), the three
stage-7 policies (every position and topology command refused untouched while posed and running at rest; pose
mode; placement), the rest <-> pose toggle, bone picking, the keys, the HUD row and the gate changes.

Headless, in the AD-027 scenario driver (`tests/interaction_trace.py`) on the head basemesh with symmetry X
(`tests/rig_support.py`). The weights' values are checked against the write rule (`skin_weights`) computed
independently from the press values and the Soft field.
"""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

import tests._bootstrap  # noqa: F401
from core.mesh import LayerKind, PointLayerInfo
from hud import hud_rows, hud_state, key_hints
from mirai import layer_declarations as gate
from mirai.controllers.skeleton import POSE_MODE_ALLOWS, POSE_MODE_REFUSAL, BoneGesture
from mirai.interaction import commands
from mirai.interaction.bindings import KEYMAP_PATH
from mirai.interaction.input import GLOBAL_CONTEXT, KNIFE_CONTEXT, MORPH_CONTEXT, SUBD_CONTEXT, WINDOW_CONTEXT, Input
from mirai.interaction.session import RunContext
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.skin_weights import parent_function, set_bone_weight, soft_target
from mirai.skinning import evaluate, skin_layer
from mirai.soft_selection import RADIUS_STEPS_PERCENT, compute_influence, symmetric_influence
from mirai.symmetry import vertex_correspondence
from tests.interaction_trace import CTRL_Y, CTRL_Z, ESC, HEIGHT, WIDTH, key
from tests.mesh_invariants import assert_layer_invariants
from tests.rig_support import (
    BONE_ADD, BONE_DELETE, BONE_NEXT, BONE_PREVIOUS, BONE_RENAME, E, FALLOFF, O, POSE_MODE, POSE_RESET, POSE_TOGGLE,
    WEIGHT, head_driver, hinge_point, hold, jaw_faces, place_pivot, rig_head, select_faces, weights,
)

TEST_KEY = Input("key", "f12")


def _state(app) -> tuple:
    """Mesh (ID counters aside: they only move forward, AD-001), rig and History depth."""
    mesh = {k: v for k, v in app.scene.mesh.export_state().items() if not k.endswith("_counter")}
    return mesh, app.scene.rig, len(app.history)


def _posed_rig():
    """The head rigged, weighted from its group and posed (E held in pose mode)."""
    d = head_driver()
    rig_head(d)
    hold(d, FALLOFF)
    d.tap(POSE_MODE)
    hold(d, E, ((30, 5), (10, 0)))
    assert d.app.posed
    return d


def _canon(value) -> tuple:
    """A weights value in the Core's canonical form (W4: as `set_layer_value` stores it)."""
    from core import Mesh

    mesh = Mesh()
    v = mesh.add_vertex((0.0, 0.0, 0.0))
    lid = mesh.add_point_layer(PointLayerInfo("w", LayerKind.WEIGHTS))
    mesh.set_layer_value(lid, v, value)
    return mesh.layer_value(lid, v)


def _rule(press, bone, x, parent_of) -> tuple:
    return _canon(set_bone_weight(press, bone, x, parent_of))


def _field(mesh, seeds, percent: float, soft) -> dict:
    """The falloff field, independently of the gesture: the Soft settings' metric and curve at `percent` of the
    bounding radius (the symmetric field under a definition)."""
    _, radius = mesh_center_and_radius(mesh)
    r = radius * percent / 100.0
    if mesh.symmetry_definition is None:
        return compute_influence(mesh, seeds, r, metric=soft.metric, curve=soft.curve, curve_power=soft.curve_power,
                                 flow_ratio=soft.flow_ratio)
    return symmetric_influence(mesh, seeds, r, metric=soft.metric, curve=soft.curve, curve_power=soft.curve_power,
                               correspondence=vertex_correspondence(mesh), flow_ratio=soft.flow_ratio).weights


# -- bone commands ------------------------------------------------------------------------------------------


def test_bone_add_rename_and_delete_are_one_exact_undo_step_each() -> None:
    d = head_driver()
    app = d.app
    rig_head(d)
    rig = app.scene.rig
    (bone,) = rig.bones
    assert bone.name == "Bone 1" and bone.parent is None and app.current_bone == bone.id
    assert tuple(bone.head) == tuple(app.active_pivot) and abs(bone.head[0]) <= 1e-12  # the pivot, on the plane
    assert len(app.history) == 3  # symmetry X, the group, the bone
    d.tap(BONE_RENAME)
    assert app.scene.rig.bone(bone.id).name == "Jaw" and len(app.history) == 4
    # a child: the selection's centre again, the pivot moved
    place_pivot(d, (0.0, hinge_point(app.scene.mesh)[1] * 0.7, 0.2))
    d.tap(BONE_ADD)
    child = app.scene.rig.bones[-1]
    assert child.parent == bone.id and app.current_bone == child.id and child.name == "Bone 2"
    hold(d, FALLOFF)
    mesh = app.scene.mesh
    before = mesh.export_state()
    rig_before = app.scene.rig
    expected = {v: _rule(value, child.id, 0.0, parent_function(rig_before)) for v, value in weights(mesh).items()}
    history = len(app.history)
    d.tap(BONE_DELETE)
    assert len(app.history) == history + 1
    assert not app.scene.rig.has_bone(child.id) and app.current_bone == bone.id
    assert weights(mesh) == {v: x for v, x in expected.items() if x}  # the child's share went to the jaw
    assert all(k == bone.id for value in weights(mesh).values() for k, _ in value)
    assert_layer_invariants(mesh)
    after = mesh.export_state()
    d.tap(CTRL_Z)
    assert mesh.export_state() == before and app.scene.rig == rig_before
    d.tap(CTRL_Y)
    assert mesh.export_state() == after and not app.scene.rig.has_bone(child.id)
    # back to the start: every step undone exactly, then redone
    total = len(app.history)
    for _ in range(total):
        d.tap(CTRL_Z)
    assert app.scene.rig is None and skin_layer(mesh) is None
    for _ in range(total):
        d.tap(CTRL_Y)
    assert mesh.export_state() == after and app.scene.rig.bone_ids() == [bone.id]


def test_bone_add_refusals_change_nothing() -> None:
    d = head_driver()
    app = d.app
    select_faces(d, jaw_faces(app.scene.mesh))
    state = _state(app)
    d.tap(BONE_ADD)
    assert app.status_message == "Add bone: place the pivot (P) in the joint first" and _state(app) == state
    place_pivot(d, hinge_point(app.scene.mesh))
    app.selection.faces = set()
    state = _state(app)
    d.tap(BONE_ADD)
    assert app.status_message.startswith("Add bone: select the points / faces") and _state(app) == state
    d.tap(key("4"))
    d.tap(BONE_ADD)
    assert app.status_message.startswith("Add bone: works from points/edges/faces") and _state(app) == state


def test_next_previous_and_the_hud_row() -> None:
    d = head_driver()
    app = d.app
    assert hud_state(app).rig is None and "Rig" not in [r.label for r in hud_rows(hud_state(app), {})]
    rig_head(d)
    place_pivot(d, (0.0, 1.0, 0.3))
    d.tap(BONE_ADD)
    first, second = app.scene.rig.bone_ids()
    history = len(app.history)
    d.tap(BONE_NEXT)
    assert app.current_bone == first and len(app.history) == history  # view state
    d.tap(BONE_PREVIOUS)
    assert app.current_bone == second
    state = hud_state(app)
    assert state.rig == "'Bone 2' · 2 bones · rest"
    rows = {r.label: r for r in hud_rows(state, key_hints(app.bindings))}
    assert rows["Rig"].keys == "5/6/Ctrl+J/7/8" and not rows["Rig"].on
    d.tap(POSE_MODE)
    assert hud_state(app).rig == "'Bone 2' · 2 bones · rest · pose mode"


# -- the weight gestures -------------------------------------------------------------------------------------


def test_falloff_from_the_group_follows_the_rule_esc_is_exact_and_a_tap_is_the_start_width() -> None:
    d = head_driver()
    app = d.app
    rig_head(d)
    mesh = app.scene.mesh
    bone = app.current_bone
    soft = app.soft_settings
    start = RADIUS_STEPS_PERCENT[soft.radius_step]
    seeds = {v for f in jaw_faces(mesh) for v in mesh.face_vertices(f)}
    state = _state(app)
    d.key_down(FALLOFF)
    d.nudge(20, 0)
    assert app.interaction_owner == "transform" and app.posed is False
    assert d.key_down(ESC)
    assert _state(app) == state and skin_layer(mesh) is None  # rolled back, the layer too
    d.key_up("ESCAPE")
    d.key_up("7")
    # a drag: start + 20 px / 2 px per percent
    hold(d, FALLOFF, ((20, 0),))
    assert len(app.history) == state[2] + 1 and app.status_message.endswith("committed (Ctrl+Z takes it back)")
    field = _field(mesh, seeds, start + 10.0, soft)
    expected = set(field)
    got = weights(mesh)
    assert set(got) == set(expected)
    for v, value in got.items():
        assert value == _rule((), bone, field[v], parent_function(app.scene.rig))
    assert all(got[v] == ((bone, 1.0),) for v in seeds)
    assert_layer_invariants(mesh)
    # a narrower run replaces the bone's weights (the wider field leaves no trace); a tap = the start width
    hold(d, FALLOFF, ())
    field = _field(mesh, seeds, start, soft)
    assert set(weights(mesh)) == set(field)
    d.tap(CTRL_Z)
    assert set(weights(mesh)) == set(expected)
    d.tap(CTRL_Z)
    assert skin_layer(mesh) is None and _state(app)[0] == state[0]


def test_falloff_refusals() -> None:
    d = head_driver()
    app = d.app
    rig_head(d, group=False)
    state = _state(app)
    d.key_down(FALLOFF)
    assert app.status_message == "Weights from group: make a group first (Ctrl+G on the faces)"
    d.key_up("7")
    assert _state(app) == state and app.interaction_owner is None


def test_set_weight_on_the_selection_with_snap_soft_and_mask() -> None:
    d = head_driver()
    app = d.app
    rig_head(d)
    hold(d, FALLOFF)
    mesh = app.scene.mesh
    bone = app.current_bone
    d.tap(key("1"))
    seed = next(v for v, value in sorted(weights(mesh).items()) if value[0][1] < 1.0 and mesh.vertex_position(v)[0] > 0)
    app.selection.vertices = {seed}
    partner = vertex_correspondence(mesh)[seed].partner
    press = weights(mesh)
    start = press[seed][0][1]
    state = _state(app)
    d.key_down(WEIGHT)
    d.nudge(30, 0)  # +0.1
    d.key_down(ESC)
    assert _state(app) == state
    d.key_up("ESCAPE")
    d.key_up("8")
    # Ctrl snaps to 0.1; the partner gets the same value (the bone is on the plane)
    d.key_down(WEIGHT)
    d.nudge(40, 0)
    d.set_modifier("ctrl", True)
    d.nudge(1, 0)
    d.set_modifier("ctrl", False)
    d.set_modifier("ctrl", True)
    d.nudge(1, 0)
    x = round((start + 42 / 300.0) / 0.1) * 0.1
    d.key_up("8")
    d.set_modifier("ctrl", False)
    assert len(app.history) == state[2] + 1
    parent_of = parent_function(app.scene.rig)
    assert weights(mesh)[seed] == _rule(press[seed], bone, x, parent_of)
    assert weights(mesh)[partner] == _rule(press[partner], bone, x, parent_of)
    assert {v for v in weights(mesh) if weights(mesh)[v] != press.get(v)} == {seed, partner}
    d.tap(CTRL_Z)
    assert weights(mesh) == press
    # Soft on: the change falls off outside the selection by the Soft field (s(v) · (x - old))
    d.tap(O)
    soft = app.soft_settings
    field = symmetric_influence(mesh, {seed}, soft.world_radius, metric=soft.metric, curve=soft.curve,
                                curve_power=soft.curve_power, correspondence=vertex_correspondence(mesh),
                                flow_ratio=soft.flow_ratio).weights
    assert len(field) > 2
    hold(d, WEIGHT, ((60, 0),))
    x = min(1.0, start + 60 / 300.0)
    for v, s in field.items():
        old = dict(press.get(v, ())).get(bone, 0.0)
        assert weights(mesh).get(v, ()) == _rule(press.get(v, ()), bone, soft_target(old, x, s), parent_of), v
    d.tap(CTRL_Z)
    d.tap(O)
    # mask: a masked vertex keeps its value
    app.selection.vertices = {seed}
    d.tap(key("m", "ctrl"))
    app.selection.vertices = {seed, partner}
    d.key_down(WEIGHT)
    assert app.status_message == "Set weight: all selected points are masked (Ctrl+M unmasks)"  # the pair is masked
    d.key_up("8")
    assert weights(mesh) == press


def test_weights_under_symmetry_need_a_bone_on_the_plane() -> None:
    d = head_driver()
    app = d.app
    rig_head(d)
    mesh = app.scene.mesh
    hold(d, FALLOFF)
    corr = vertex_correspondence(mesh)
    w = weights(mesh)
    for v, value in w.items():  # pair-exact: the partner holds the same value
        partner = getattr(corr[v], "partner", None)
        if partner is not None:
            assert w.get(partner) == value, v
    # an off-centre bone is refused (fail-closed) - with symmetry off it is allowed
    select_faces(d, jaw_faces(mesh))
    app._pointer_tools.working_pivot = dataclasses.replace(app.working_pivot, position=(0.4, 1.5, 0.2))
    d.tap(BONE_ADD)
    state = _state(app)
    d.key_down(FALLOFF)
    assert "off the symmetry plane - it needs its mirror bone (not yet)" in app.status_message
    d.key_up("7")
    d.key_down(WEIGHT)
    assert "off the symmetry plane" in app.status_message
    d.key_up("8")
    assert _state(app) == state


# -- the pose ------------------------------------------------------------------------------------------------


def test_the_pose_is_view_state_esc_restores_it_and_the_surface_is_the_definition() -> None:
    d = head_driver()
    app = d.app
    rig_head(d)
    hold(d, FALLOFF)
    history = len(app.history)
    d.tap(POSE_MODE)
    assert app.pose_mode
    d.key_down(E)
    assert isinstance(app._gestures.session, BoneGesture)
    d.nudge(30, 5)
    assert app.posed
    d.key_down(ESC)
    assert app.pose == {} and not app.posed
    d.key_up("ESCAPE")
    d.key_up("e")
    hold(d, E, ((30, 5), (10, -2)))
    pose = app.pose
    assert app.posed and len(app.history) == history  # no History entry
    app.update_viewport(0)
    surface = app.skin.provider.surface_mesh
    mesh = app.scene.mesh
    expected = evaluate(mesh, None, app.scene.rig, pose, None)
    assert all(tuple(surface.vertex_position(v)) == expected[v] for v in mesh.all_vertex_ids())
    assert any(expected[v] != tuple(mesh.vertex_position(v)) for v in mesh.all_vertex_ids())
    # W translates, R scales; Undo never touches the pose
    hold(d, key("w"), ((5, 5),))
    hold(d, key("r"), ((10, 0),))
    assert app.pose != pose and len(app.history) == history
    d.tap(CTRL_Z)
    assert app.posed and app.scene.rig is not None
    # Alt+6 = the current bone to rest; 6 toggles rest <-> the last pose
    d.tap(CTRL_Y)
    posed = app.pose
    d.tap(POSE_TOGGLE)
    assert not app.posed and app.status_message == "Rest pose (6 = back to the pose)"
    d.tap(POSE_TOGGLE)
    assert app.pose == posed
    d.tap(POSE_RESET)
    assert app.pose == {} and not app.posed


def test_rotation_about_the_head_keeps_the_head_and_a_child_follows_its_parent() -> None:
    d = head_driver()
    app = d.app
    rig_head(d)
    jaw = app.current_bone
    place_pivot(d, (0.0, 1.0, 0.3))
    d.tap(BONE_ADD)
    child = app.current_bone
    d.tap(BONE_PREVIOUS)
    d.tap(POSE_MODE)
    d.tap(key("x"))
    hold(d, E, ((40, 0),))
    segments = {b: (h, t) for b, h, t in app._skeleton.posed_segments()}
    rig = app.scene.rig
    assert segments[jaw][0] == pytest.approx(rig.bone(jaw).head, abs=1e-12)  # turned about its head
    assert segments[jaw][1] != pytest.approx(rig.bone(jaw).tail)
    assert segments[child][0] != pytest.approx(rig.bone(child).head)  # the child rides along
    # its length is kept (a rotation)
    length = math.dist(rig.bone(jaw).head, rig.bone(jaw).tail)
    assert math.dist(*segments[jaw]) == pytest.approx(length, rel=1e-12)


def test_a_click_in_pose_mode_picks_the_nearest_bone() -> None:
    d = head_driver()
    app = d.app
    rig_head(d)
    jaw = app.current_bone
    place_pivot(d, (0.0, 1.0, 0.3))
    d.tap(BONE_ADD)
    child = app.current_bone
    d.tap(POSE_MODE)
    app.gizmo_enabled = False  # its handles at the current bone's head win a press there (AD-016 D3)
    app.camera.set_view(0.9, 0.2)  # from the side: the two bones (both on the plane) apart on screen
    app.set_viewport_size(WIDTH, HEIGHT)
    rig = app.scene.rig
    b = rig.bone(jaw)
    near_head = tuple(p + 0.1 * (q - p) for p, q in zip(b.head, b.tail))
    x, y = app.camera.project_to_screen(near_head, WIDTH, HEIGHT)
    selection = app._selection_snapshot()
    d.click(x, y)
    assert app.current_bone == jaw and app._selection_snapshot() == selection
    d.click(3.0, 3.0)  # far from every bone: nothing changes
    assert app.current_bone == jaw
    b = rig.bone(child)
    x, y = app.camera.project_to_screen(b.head, WIDTH, HEIGHT)
    d.click(x + 3, y)
    assert app.current_bone == child
    items = app.bone_items()
    assert len(items) == 4 and items[2].color[3] == 1.0  # line + cross per bone, not dimmed in pose mode
    d.tap(key("1"))
    assert not app.pose_mode and app.bone_items()[0].color[3] < 1.0


# -- the policies --------------------------------------------------------------------------------------------


_EDITING = sorted(c for c in gate.COMMAND_CLASSES if gate.edits_positions_or_topology(c))


def test_the_editing_classes_are_the_gates() -> None:
    assert commands.APPLY_TRANSFORM not in _EDITING
    for c in (commands.MOVE, commands.LOOP_INSERT, commands.CONNECT, commands.EXTRUDE, commands.SMOOTH,
              commands.TWEAK, commands.COLLAPSE, commands.DELETE, commands.SPLIT_EDGE):
        assert c in _EDITING
    for c in (*commands.RIG_COMMANDS, commands.MORPH_NEW, commands.UNDO, commands.SELECT, commands.MASK_TOGGLE):
        assert c not in _EDITING
    assert gate.edits_positions_or_topology("apply_mesh_change") and gate.edits_positions_or_topology("unknown")


@pytest.mark.parametrize("command", _EDITING)
def test_every_position_and_topology_command_is_refused_untouched_while_posed(command) -> None:
    d = _posed_rig()
    app = d.app
    d.tap(key("2"))  # out of pose mode, the pose stays
    assert app.posed and not app.pose_mode
    refusal = app.can_run(command, RunContext("key", TEST_KEY))
    if gate.COMMAND_CLASSES[command] == gate.LOCKED:  # refused by the layer gate already (stage 3)
        assert refusal is not None and "locked" in refusal.text, refusal
    else:
        assert refusal is not None and refusal.text.endswith(": the mesh is posed (6 = rest pose)"), refusal
    app.bindings.bind(TEST_KEY, command)
    state = _state(app)
    assert app.key_press(TEST_KEY) is False
    app.key_release(TEST_KEY)
    assert _state(app) == state and app.interaction_owner is None
    # at rest the policy lets it through
    d.tap(POSE_TOGGLE)
    refusal = app.can_run(command, RunContext("key", TEST_KEY))
    assert refusal is None or "posed" not in (refusal.text or "")


def test_what_runs_while_posed_and_the_host_entry() -> None:
    d = _posed_rig()
    app = d.app
    d.tap(key("1"))
    for command in (*commands.RIG_COMMANDS, commands.MORPH_NEW, commands.UNDO, commands.REDO, commands.SELECT,
                    commands.CYCLE_DISPLAY_MODE, commands.MASK_TOGGLE, commands.APPLY_TRANSFORM):
        refusal = app.can_run(command, RunContext("key", TEST_KEY))
        assert refusal is None or "posed" not in (refusal.text or ""), command
    state = _state(app)
    assert app.apply_mesh_change("Host edit", lambda: set()) is False
    assert app.status_message == "Host edit: the mesh is posed (6 = rest pose)" and _state(app) == state
    # a morph target is shaped while posed (its editing view is an unbound copy)
    d.tap(key("n", "ctrl"))
    d.tap(key("tab"))
    assert app.morph_view_open
    assert app.can_run(commands.MOVE, RunContext("key", TEST_KEY)) is None
    assert app.can_run(commands.BONE_DELETE, RunContext("key", TEST_KEY)).text.endswith("on the base only (Tab returns to it)")
    assert app.can_run(commands.POSE_TOGGLE_REST, RunContext("key", TEST_KEY)) is None


def test_pose_mode_runs_only_pose_rig_and_view_commands() -> None:
    d = head_driver()
    app = d.app
    state = _state(app)
    d.tap(POSE_MODE)
    assert not app.pose_mode and app.status_message == "Pose mode: no bone yet (Ctrl+J adds one)"
    rig_head(d)
    d.tap(POSE_MODE)
    every = {v for n, v in vars(commands).items() if n.isupper() and isinstance(v, str)}
    for command in sorted(every):
        refusal = app.can_run(command, RunContext("key", TEST_KEY))
        if command in POSE_MODE_ALLOWS:
            assert refusal is None or refusal.text != POSE_MODE_REFUSAL, command
        else:
            assert refusal is not None and refusal.text == POSE_MODE_REFUSAL, command
    state = _state(app)
    d.tap(key("i"))
    assert app.status_message == POSE_MODE_REFUSAL and _state(app) == state
    d.tap(key("3"))
    assert not app.pose_mode


def test_a_bound_objects_placement_is_locked_apply_transform_runs() -> None:
    d = head_driver(symmetric=False)
    app = d.app
    rig_head(d)
    hold(d, FALLOFF)
    edit = app.scene.edit_object
    d.tap(key("4"))
    app.selection.objects = {edit.id}
    for command in (commands.MOVE, commands.ROTATE, commands.SCALE, commands.TWEAK, commands.CLEAR_TRANSFORM):
        refusal = app.can_run(command, RunContext("key", TEST_KEY))
        assert refusal is not None and refusal.text.endswith(f"{edit.name!r} is locked while bound to the rig"), command
    assert app.can_run(commands.APPLY_TRANSFORM, RunContext("key", TEST_KEY)) is None
    assert app.can_run(commands.MOVE, RunContext("ui", operands=False)) is None  # the HUD skips the operand stages
    state = _state(app)
    d.key_down(key("w"))
    d.nudge(10, 0)
    d.key_up("w")
    assert _state(app) == state and edit.transform == app.scene.edit_object.transform
    # a mirror partner's follow: an unbound object paired with a bound one is locked too
    app.selection.objects = set()
    other = app.add_primitive("cube")
    app.selection.objects = {other.id}
    copy = app.mirror_copy("X")
    lid = copy.mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    copy.mesh.set_layer_value(lid, sorted(copy.mesh.all_vertex_ids())[0], ((int(app.current_bone), 1.0),))
    app.selection.objects = {other.id}
    refusal = app.can_run(commands.MOVE, RunContext("key", TEST_KEY))
    assert refusal is not None and refusal.text.endswith(f"{copy.name!r} is locked while bound to the rig")


def test_mirror_copy_of_a_mesh_with_weights_is_refused_untouched() -> None:
    from mirai.object_mirror import mirror_mesh

    d = head_driver(symmetric=False)
    app = d.app
    rig_head(d)
    hold(d, FALLOFF)
    edit = app.scene.edit_object
    d.tap(key("4"))
    app.selection.objects = {edit.id}
    objects = set(app.scene.objects)
    state = _state(app)
    assert app.mirror_copy("X") is None
    assert app.status_message == "Mirror copy: locked while this mesh has skin weights (bones cannot be mirrored yet)"
    assert set(app.scene.objects) == objects and _state(app) == state
    with pytest.raises(ValueError, match="weights layer cannot be mirrored"):
        mirror_mesh(edit.mesh, (1.0, 0.0, 0.0))
    # vector layers alone still mirror (the gate is kind-aware, not a lock)
    assert gate.kind_refusal("mirror_copy", [app.add_primitive("cube").mesh]) is None


def test_bound_is_cached_and_follows_the_weights_journal() -> None:
    d = head_driver()
    app = d.app
    rig_head(d)
    skeleton = app._skeleton
    mesh = app.scene.mesh
    assert skeleton.bound(mesh) is False
    hold(d, FALLOFF)
    assert skeleton.bound(mesh) is True
    calls = []
    import mirai.controllers.skeleton as module

    real = module.has_stored_weights
    module.has_stored_weights = lambda m: calls.append(m) or real(m)
    try:
        for _ in range(5):
            assert skeleton.bound(mesh) is True
        assert calls == []  # no layer scan while the layers did not change
        d.tap(CTRL_Z)
        assert skeleton.bound(mesh) is False and len(calls) == 1
    finally:
        module.has_stored_weights = real


# -- keys ----------------------------------------------------------------------------------------------------

#: The Morph Lab's keys (`experiments/morph_lab/lab_app.py` LAB_KEYS; tests do not import experiments): no rig key may
#: be bound to one of them in the global context (the Lab's start-up check, H2-R1).
MORPH_LAB_KEYS = {
    ("up", ("alt",)), ("down", ("alt",)), ("up", ("alt", "shift")), ("down", ("alt", "shift")), ("up", ("ctrl",)),
    ("down", ("ctrl",)), ("m", ()), ("b", ("alt",)), ("right", ("alt",)), ("left", ("alt",)),
    ("right", ("alt", "shift")), ("left", ("alt", "shift")), ("j", ()), ("j", ("shift",)), ("comma", ()),
    ("period", ()),
}


def test_the_rig_keys_are_free_in_every_context_and_not_in_the_keymap() -> None:
    d = head_driver()
    bindings = d.app.bindings
    keymap = json.loads(KEYMAP_PATH.read_text(encoding="utf-8"))
    taken = {(e["input"]["value"], tuple(sorted(e["input"]["modifiers"]))) for e in keymap["bindings"]}
    for command in commands.RIG_COMMANDS:
        (inp,) = [i for i in bindings.inputs_for(command) if i.kind == "key"]
        mods = tuple(sorted(inp.modifiers))
        assert (inp.value, mods) not in taken, command
        assert (inp.value, mods) not in MORPH_LAB_KEYS, command
        assert bindings.command_for(inp, GLOBAL_CONTEXT) == command
        for context in (KNIFE_CONTEXT, SUBD_CONTEXT, MORPH_CONTEXT, WINDOW_CONTEXT):
            assert bindings.command_for(inp, context) in (None, command), (command, context)
    assert {commands.WEIGHTS_FROM_GROUP, commands.WEIGHT_SET} <= commands.HOLD_COMMANDS


def test_a_weight_gesture_is_computed_from_its_press_values_whatever_its_path() -> None:
    """§8.4 (no drift): wide then narrow inside one gesture gives the narrow result, and a value dragged up and back
    gives the value's result - each step is a pure function of the press values and the current gesture value."""
    results = []
    for steps in (((40, 0), (-30, 0)), ((10, 0),)):
        d = head_driver()
        rig_head(d)
        d.app._gestures.axis_constraint = None
        hold(d, FALLOFF, steps)
        results.append(weights(d.app.scene.mesh))
    assert results[0] == results[1]
    results = []
    for steps in (((90, 0), (-60, 0)), ((30, 0),)):
        d = head_driver()
        rig_head(d)
        hold(d, FALLOFF)
        mesh = d.app.scene.mesh
        d.tap(key("1"))
        d.app.selection.vertices = {v for v, value in weights(mesh).items() if value[0][1] < 1.0}
        d.tap(O)
        hold(d, WEIGHT, steps)
        results.append(weights(mesh))
    assert results[0] == results[1]
