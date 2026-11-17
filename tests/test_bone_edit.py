"""Bone tool 01 (2026-11-17): editing a bone after binding, deleting by id and the weight operations as numbers (the panel's
entries) - `SkeletonController.edit_bone`, `delete_bone(bone)`, `weights_from_group_value`, `set_weight_value`; AD-028 addendum
2026-11-17.

A bone's name, parent, head, tail and roll change in the rest pose, one Undo step each (`RigCommand`); weights are keyed by
`BoneId` and stay; the mesh (the rest shape) is not touched, so the rest display is bit-identical; children keep their own rest
frames; while posed the edit is refused; a remembered pose is local to the bone's rest frame and follows it. The Core `Rig`
API suffices (`with_bone`): no `src/core` change.
"""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from core import Bone, BoneId, Rig
from core.rig import rest_frame
from mirai.application import Application
from mirai.interaction import commands
from mirai.skin_weights import bone_share
from mirai.skinning import evaluate, skin_layer
from tests.interaction_trace import CTRL_Y, CTRL_Z, key
from tests.rig_support import E, FALLOFF, POSE_MODE, POSE_TOGGLE, head_driver, hold, rig_head, weights


def _bones_app():
    """A cube with a three-bone chain (Root -> Spine -> Head), as `test_gui_bones`."""
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    bones = (
        Bone(BoneId(0), "Root", None, (0, 0, 0), (0, 1, 0)),
        Bone(BoneId(1), "Spine", BoneId(0), (0, 1, 0), (0, 2, 0)),
        Bone(BoneId(2), "Head", BoneId(1), (0, 2, 0), (0, 3, 0)),
    )
    app.scene.rig = Rig(bones=bones, bone_id_counter=3)
    return app, [b.id for b in bones]


def _weighted_head():
    d = head_driver()
    rig_head(d)
    hold(d, FALLOFF)
    return d


def _canon_mesh(mesh) -> dict:
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}


# -- what an edit does ---------------------------------------------------------------------------------------


def test_an_edit_changes_the_fields_asked_for_one_undo_step_and_undo_redo_are_exact() -> None:
    app, (root, spine, head) = _bones_app()
    before = app.scene.rig
    depth = len(app.history)
    assert app.edit_bone(spine, head=(0.0, 1.2, 0.1), tail=(0.0, 2.1, 0.0), roll=math.radians(30))
    b = app.scene.rig.bone(spine)
    assert (b.head, b.tail, b.roll, b.name, b.parent, b.id) == ((0.0, 1.2, 0.1), (0.0, 2.1, 0.0), math.radians(30), "Spine", root, spine)
    assert len(app.history) == depth + 1 and app.scene.rig.bone_id_counter == 3
    assert app.status_message.startswith("Bone 'Spine': head, tail, roll changed")
    after = app.scene.rig
    app.dispatch_command(commands.UNDO)
    assert app.scene.rig == before
    app.dispatch_command(commands.REDO)
    assert app.scene.rig == after


def test_children_keep_their_own_rest_frames_when_a_bone_moves() -> None:
    app, (root, spine, head) = _bones_app()
    child_before = app.scene.rig.bone(head)
    assert app.edit_bone(spine, head=(0.3, 1.0, 0.0), tail=(0.3, 1.9, 0.2))
    child = app.scene.rig.bone(head)
    assert child == child_before and rest_frame(child) == rest_frame(child_before)  # world-space rest: not dragged along


def test_a_change_that_changes_nothing_is_no_step() -> None:
    app, (root, spine, head) = _bones_app()
    depth = len(app.history)
    b = app.scene.rig.bone(spine)
    assert not app.edit_bone(spine, head=b.head, tail=b.tail, roll=b.roll, name="Spine", parent=root)
    assert not app.edit_bone(spine)
    assert len(app.history) == depth


def test_refusals_degenerate_non_finite_unknown_and_names() -> None:
    app, (root, spine, head) = _bones_app()
    rig = app.scene.rig
    depth = len(app.history)
    assert not app.edit_bone(spine, head=(0.0, 2.0, 0.0))  # = its tail: no length
    assert "degeneriert" in app.status_message or "Länge" in app.status_message or "Kopf" in app.status_message
    assert not app.edit_bone(spine, tail=(0.0, float("nan"), 0.0))
    assert not app.edit_bone(spine, roll=float("inf"))
    assert not app.edit_bone(BoneId(99), head=(1.0, 1.0, 1.0))
    assert app.status_message == "Edit bone: no such bone"
    assert not app.edit_bone(spine, name="Root")  # taken
    assert not app.edit_bone(spine, name="  ")
    assert not app.edit_bone(spine, name="x" * 65)
    assert app.status_message.endswith("is not a free name")
    assert app.scene.rig == rig and len(app.history) == depth
    assert app.edit_bone(spine, name="  Wirbel ")
    assert app.scene.rig.bone(spine).name == "Wirbel"  # trimmed


def test_reparent_with_cycle_refusal_and_a_root() -> None:
    app, (root, spine, head) = _bones_app()
    rig = app.scene.rig
    assert not app.edit_bone(root, parent=head)  # its own grandchild
    assert app.status_message == "Edit bone: 'Root' cannot be a child of its own child 'Head' (a bone hierarchy has no cycle)"
    assert not app.edit_bone(spine, parent=spine)
    assert app.status_message == "Edit bone: 'Spine' cannot be a child of itself (a bone hierarchy has no cycle)"
    assert not app.edit_bone(spine, parent=BoneId(99))
    assert app.scene.rig == rig
    assert app.edit_bone(head, parent=root)  # Head moves up to Root
    assert app.scene.rig.bone(head).parent == root and app.scene.rig.bone(head).head == rig.bone(head).head
    assert app.edit_bone(head, parent=None)  # and becomes a root
    assert app.scene.rig.bone(head).parent is None
    app.dispatch_command(commands.UNDO)
    app.dispatch_command(commands.UNDO)
    assert app.scene.rig == rig


# -- after binding -----------------------------------------------------------------------------------------------


def test_after_binding_the_weights_and_the_rest_shape_are_untouched_and_the_rest_display_is_bit_identical() -> None:
    """The stop point of the handoff ("stop if bone editing changes how existing weighted meshes evaluate at rest"): it does
    not. The mesh and its weights layer are not written at all (journal-exact), and at rest the evaluation of the new rig is the
    rest shape to the bit - the same as before the edit."""
    d = _weighted_head()
    app = d.app
    mesh = app.scene.mesh
    (bone,) = app.scene.rig.bones
    state, bound = _canon_mesh(mesh), weights(mesh)
    assert bound
    rest_before = evaluate(mesh, None, app.scene.rig, {}, None)
    for change in (dict(head=(0.0, bone.head[1] + 0.1, bone.head[2] + 0.05)), dict(tail=(0.0, bone.tail[1] - 0.05, bone.tail[2])),
                   dict(roll=0.9), dict(name="Kiefer")):
        assert app.edit_bone(bone.id, **change), (change, app.status_message)
        assert _canon_mesh(mesh) == state and weights(mesh) == bound
        assert evaluate(mesh, None, app.scene.rig, {}, None) == rest_before
    assert all(tuple(mesh.vertex_position(v)) == p for v, p in rest_before.items())
    assert skin_layer(mesh) is not None and all(k == bone.id for value in bound.values() for k, _ in value)  # keyed by BoneId


def test_the_posed_surface_follows_the_new_rest_frame_and_is_the_definition() -> None:
    """The deformation around a moved hinge is the new one - the pose evaluates in the new rest frame, as defined."""
    d = _weighted_head()
    app = d.app
    mesh = app.scene.mesh
    (bone,) = app.scene.rig.bones
    d.tap(POSE_MODE)
    hold(d, E, ((30, 5), (10, 0)))
    pose = dict(app.pose)
    assert app.posed
    d.tap(POSE_TOGGLE)  # rest
    assert not app.posed
    old_rig = app.scene.rig
    assert app.edit_bone(bone.id, head=(0.0, bone.head[1] + 0.08, bone.head[2]))
    d.tap(POSE_TOGGLE)  # the remembered pose comes back: its values are local to the bone's rest frame
    assert app.posed and dict(app.pose) == pose  # the very same local pose
    app.update_viewport(0)
    new = evaluate(mesh, None, app.scene.rig, app.pose, None)
    old = evaluate(mesh, None, old_rig, app.pose, None)
    surface = app.skin.provider.surface_mesh
    assert all(tuple(surface.vertex_position(v)) == new[v] for v in mesh.all_vertex_ids())
    assert any(new[v] != old[v] for v in mesh.all_vertex_ids())  # the hinge moved: the pose deforms differently


def test_the_edit_is_refused_while_posed_and_nothing_changes() -> None:
    d = _weighted_head()
    app = d.app
    (bone,) = app.scene.rig.bones
    d.tap(POSE_MODE)
    hold(d, E, ((30, 5), (10, 0)))
    assert app.posed and app.bone_edit_blocker == "the rig is posed - 6 = rest pose first (a bone's rest frame is edited at rest)"
    rig, depth = app.scene.rig, len(app.history)
    for change in (dict(head=(0.0, 1.0, 0.0)), dict(name="X"), dict(parent=None), dict(roll=1.0)):
        assert not app.edit_bone(bone.id, **change)
        assert app.status_message.startswith("Edit bone: the rig is posed - 6 = rest pose first")
    assert app.scene.rig == rig and len(app.history) == depth
    d.tap(POSE_TOGGLE)
    assert app.bone_edit_blocker is None and app.edit_bone(bone.id, roll=0.3)


def test_the_edit_is_refused_while_an_interaction_runs() -> None:
    app, (root, spine, head) = _bones_app()
    assert app.start_bone_chain()
    assert app.bone_edit_blocker == "not while the bonechain interaction runs"
    assert not app.edit_bone(spine, roll=0.5)
    assert not app.delete_bone(spine)
    app.end_bone_chain()
    assert app.edit_bone(spine, roll=0.5)


# -- delete by id, the weight values ---------------------------------------------------------------------------------


def test_delete_by_id_takes_that_bone_its_weights_go_to_the_parent_and_undo_brings_everything_back() -> None:
    d = _weighted_head()
    app = d.app
    mesh = app.scene.mesh
    (jaw,) = app.scene.rig.bones
    app.select_bone(jaw.id)
    # a second, unrelated bone is current: delete the jaw by id
    rig2, other = app.scene.rig.with_new_bone("Other", (0.0, 0.0, 0.0), (0.0, 0.2, 0.0))
    app.scene.rig = rig2
    app.select_bone(other)
    state, rig, bound = _canon_mesh(mesh), app.scene.rig, weights(mesh)
    assert app.delete_bone(jaw.id)
    assert not app.scene.rig.has_bone(jaw.id) and app.scene.rig.has_bone(other)
    assert all(bone_share(value, jaw.id) == 0.0 for value in weights(mesh).values())
    assert not app.delete_bone(BoneId(99))
    d.tap(CTRL_Z)
    assert _canon_mesh(mesh) == state and app.scene.rig == rig and weights(mesh) == bound
    d.tap(CTRL_Y)
    assert not app.scene.rig.has_bone(jaw.id)


def test_weights_from_the_group_as_a_number_equals_the_key_with_the_same_width() -> None:
    """The panel's "Anwenden" is the key's gesture with a number instead of the mouse: same stroke, one Undo step."""
    from mirai.controllers.skeleton import FALLOFF_PX_PER_PERCENT
    from mirai.soft_selection import RADIUS_STEPS_PERCENT

    via_key = head_driver()
    rig_head(via_key)
    hold(via_key, FALLOFF, ((30, 0),))
    expected = weights(via_key.app.scene.mesh)
    assert expected

    d = head_driver()
    rig_head(d)
    app = d.app
    percent = float(RADIUS_STEPS_PERCENT[app.soft_settings.radius_step]) + 30 / FALLOFF_PX_PER_PERCENT
    depth = len(app.history)
    assert app.weights_from_group_value(percent), app.status_message
    assert len(app.history) == depth + 1 and not app.interaction_owner
    assert weights(app.scene.mesh) == expected
    d.tap(CTRL_Z)
    assert weights(app.scene.mesh) == {}  # one step takes it back


def test_set_weight_as_a_number_writes_the_selection_and_refuses_like_the_key() -> None:
    d = _weighted_head()
    app = d.app
    mesh = app.scene.mesh
    (bone,) = app.scene.rig.bones
    d.tap(key("1"))
    assert not app.set_weight_value(0.5) and app.status_message == "Set weight: select points first"
    weighted = [v for v, value in weights(mesh).items() if 0.0 < bone_share(value, bone.id) < 1.0]
    picked = set(weighted[:3])
    app.selection.vertices = set(picked)
    depth = len(app.history)
    assert app.set_weight_value(0.4), app.status_message
    assert len(app.history) == depth + 1
    assert all(bone_share(weights(mesh)[v], bone.id) == pytest.approx(0.4, abs=1e-9) for v in picked)
    d.tap(CTRL_Z)
    assert len(app.history) == depth
    # no group: the same refusal as the key
    app2 = head_driver().app
    assert not app2.weights_from_group_value(20.0)
