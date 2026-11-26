"""SkeletonController (AD-028 §6-§8, AD-027 §3.5): the scene rig's bones and their pose, the pose mode, the weight
gestures and the three stage-7 policies. Names, keys and texts `PROVISIONAL`.

- **Rig commands** (History entries, a `RigCommand` with the rig before / after): `BONE_ADD` (head = the Working
  Pivot, tail = the centre of the component selection, both to world; parent = the current bone; creates the rig if
  absent), `BONE_RENAME` (a name list), `BONE_DELETE` (a `CompositeCommand`: one `MeshDeltaCommand` per bound mesh -
  the bone's share to its parent, `skin_weights.delete_bone_weights` - and the rig without the bone).
- **Bone tool 01** (2026-11-17, AD-028 addendum): the chain-click tool (`bone_chain.BoneChainSession`, begun by
  `begin_chain`: no key), `edit_bone` (a bone's name, parent, head, tail, roll at rest, one Undo step; refused while
  posed), `delete_bone` by id, and the two weight operations as values (`weights_from_group_value`,
  `set_weight_value`: the gestures' own stroke, committed at once, for the panel).
- **Pose** (view state, §6; no History, not saved, a load starts at rest): `BoneId -> BonePose`, the current bone,
  the last pose (for the rest <-> pose toggle) and the pose mode. Written to the skin stage through
  `services.skin.provider.set_pose`. A deleted bone's pose channel goes with it and does not come back on Undo.
- **Gesture kinds** (`gestures.GestureSession` subclasses - the second user of the one controller dependency,
  AD-027 §7.1 M7): `BoneGesture` (W/E/R in pose mode, also the gizmo at the bone head), `FalloffGesture`
  (weights from the active group, mouse = falloff width) and `WeightGesture` (the current bone's weight on the
  selection, mouse = value). The two weight gestures run inside one open recording: release = one entry, Esc =
  `rollback_change`; every step is computed from the values at the press (`skin_weights.WeightStroke`).
- **Policies** (`can_run` stage 7, pure, in order): (1) pose mode - only pose, rig and view-state commands;
  (2) posed and bound - position and topology edits of the bound edit mesh refused (the gate's classification,
  `layer_declarations.edits_positions_or_topology`); (3) bound placement - object W/E/R, Clear transform and a mirror
  partner's follow refused for a bound object. "Bound" = a weights layer with a stored value and a rig; cached per
  mesh behind a `Mesh.watch()` (re-read only when that mesh's layers changed - never a layer scan per frame).
"""

from __future__ import annotations

import dataclasses
import math
import re
from typing import Optional

from core import Bone, BoneId, ObjectState, PointLayerInfo, SelectionMode
from core.mesh import LayerKind, MeshChange
from core.operations import MeshDeltaCommand, record_mesh_change
from core.operations.transform import SEAM_TOLERANCE
from core.rig import Rig, rest_frame

from .. import bone_links, eye_gaze, object_space, transform_space
from ..interaction import commands
from ..interaction.dial import DialAngle
from ..interaction.session import Refusal, RunContext
from ..interaction.tools import resolve_selection_vertices
from ..interaction.tools.rotate import RotateTool
from ..interaction.tools.scale import ScaleTool
from ..interaction.tools.selection_helpers import selection_pivot
from ..interaction.tools.transform import _resolve_space
from ..layer_declarations import edits_positions_or_topology
from ..mask import FULL as MASK_FULL
from ..mesh_geometry import mesh_center_and_radius
from ..morph_targets import WEIGHT_COMMANDS as MORPH_WEIGHT_COMMANDS
from ..regions import live_faces
from ..scene_objects import CompositeCommand, group_leaves
from ..skin_weights import WeightStroke, bone_share, delete_bone_weights, soft_target
from ..skinning import REST, BonePose, is_posed, skin_layer, skin_transforms
from ..soft_selection import RADIUS_STEPS_PERCENT, SoftSymmetryRefusal
from ..subdivision import SUBD_COMMANDS
from ..subdivision.preview import key_label
from ..symmetry import vertex_correspondence
from ..viewport import gizmo as _gizmo
from .bone_chain import AXIS_MODES, BoneChainSession
from .gestures import (
    TRANSFORM_COMMANDS,
    GestureController,
    GestureSession,
    commit_hint,
    constraint_suffix,
)
from .services import AppServices

#: The skin layer's name (AD-028 §3.3; one per bound mesh).
SKIN_LAYER_NAME = "Skin"
#: `BONE_RENAME` cycles these (the app has no text field yet), as the morph rename.
BONE_NAMES = ("Jaw", "Head", "Neck", "Spine", "Chest", "Eye L", "Eye R", "Tongue")
#: A click picks the nearest bone whose projected head-tail segment is this close (px, §8.4).
PICK_RADIUS_PX = 10.0
#: Weight gesture: pixels of mouse travel for the full 0 -> 1; Ctrl snaps to `WEIGHT_SNAP`.
WEIGHT_PX_PER_UNIT = 300.0
WEIGHT_SNAP = 0.1
#: Falloff gesture: pixels per percent of the mesh's bounding radius; the width stays in [0, `FALLOFF_MAX_PERCENT`].
FALLOFF_PX_PER_PERCENT = 2.0
FALLOFF_MAX_PERCENT = 200.0
#: The Soft display mode the weight gestures show the current bone's share in (face shading, §8.4).
SHARE_VIEW_MODE = "faces"

#: Bone line items (look `PROVISIONAL`): bone yellow, the current bone brighter and thicker, dimmed outside pose mode.
COLOR_BONE = (0.95, 0.85, 0.3, 1.0)
COLOR_BONE_CURRENT = (1.0, 0.55, 0.1, 1.0)
BONE_DIM_ALPHA = 0.45
BONE_LINE_WIDTH = 2.5
BONE_LINE_WIDTH_CURRENT = 4.0
BONE_CROSS_RATIO = 0.15

#: Commands that run in pose mode (§8.2 policy 1): the pose and rig commands except Add (component modes), the
#: transforms (the bone gesture; the gizmo drag), the constraint and space keys, view state (navigation, display,
#: Look, ortho, light, SubD view, the morph weight and target switch, Soft settings), the session switches, Undo /
#: Redo, Cancel, the mode keys (they leave pose mode) and the clicks (they pick a bone).
POSE_MODE_ALLOWS = frozenset(
    {
        *(c for c in commands.RIG_COMMANDS if c != commands.BONE_ADD),
        commands.MOVE, commands.ROTATE, commands.SCALE, commands.TWEAK,
        *commands.CONSTRAINT_COMMANDS, commands.TOGGLE_TRANSFORM_SPACE,
        commands.CONSTRAINT_MODE_TOGGLE, commands.GIZMO_SIZE_CYCLE,
        commands.ORBIT, commands.PAN, commands.ZOOM, commands.TOGGLE_ORTHO, commands.LIGHT_DRAG,
        *commands.DISPLAY_COMMANDS, *commands.LOOK_COMMANDS, *SUBD_COMMANDS,
        *MORPH_WEIGHT_COMMANDS, commands.MORPH_WEIGHT_DRAG, commands.MORPH_NEXT, commands.MORPH_PREVIOUS,
        commands.SOFT_TOGGLE, commands.SOFT_RADIUS_UP, commands.SOFT_RADIUS_DOWN, commands.SOFT_CURVE_CYCLE,
        commands.SOFT_METRIC_CYCLE, commands.SOFT_CURVE_SHAPE_ROUNDER, commands.SOFT_CURVE_SHAPE_SHARPER,
        commands.SOFT_BANDS_TOGGLE, commands.SOFT_VIEW_MODE_CYCLE, commands.SOFT_LOOK_CYCLE,
        commands.SOFT_FLOW_LOOP, commands.SOFT_FLOW_RING, commands.WEIGHT_VIEW_TOGGLE,
        commands.UNDO, commands.REDO, commands.CANCEL,
        *commands.MODE_COMMANDS,
        commands.SELECT, commands.SELECT_ADD, commands.SELECT_REMOVE, commands.SELECT_TOGGLE,
        *commands.WINDOW_COMMANDS,
    }
)
POSE_MODE_REFUSAL = "Pose mode: bones only (1/2/3 to model)"

#: §7.2: what a bound object's placement refuses (mode `4`).
_PLACEMENT_LABELS = {
    commands.MOVE: "Object Move",
    commands.ROTATE: "Object Rotate",
    commands.SCALE: "Object Scale",
    commands.TWEAK: "Object Tweak",
    commands.CLEAR_TRANSFORM: "Clear transform",
}

_I3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

#: `edit_bone`: a field left at this is not changed (None is a value: no parent).
KEEP = object()


# -- small vector maths (rows, as `object_space`) ------------------------------------------------------------


def _mul(m, v):
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def _t(m):
    return ((m[0][0], m[1][0], m[2][0]), (m[0][1], m[1][1], m[2][1]), (m[0][2], m[1][2], m[2][2]))


def _affine_point(affine, p):
    if affine is None:
        return tuple(p)
    m, c = affine
    q = _mul(m, p)
    return (q[0] + c[0], q[1] + c[1], q[2] + c[2])


def _linear_scale(m) -> float:
    """The uniform scale of a similarity's linear part (its first column's length)."""
    return math.sqrt(m[0][0] ** 2 + m[1][0] ** 2 + m[2][0] ** 2)


def _unit(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / n, v[1] / n, v[2] / n) if n > 0.0 else v


def command_label(key) -> str:
    """A command's name for a status line: the gesture labels, else the constant split into words ("LoopInsert" ->
    "Loop Insert"); a `CContext` by its name."""
    if isinstance(key, str):
        if key in TRANSFORM_COMMANDS:
            return TRANSFORM_COMMANDS[key][0]
        return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", key)
    return getattr(key, "name", str(key))


class RigCommand:
    """A rig change as one History entry: `Scene.rig` before / after (both immutable values)."""

    def __init__(self, scene, before: Optional[Rig], after: Optional[Rig], description: str) -> None:
        self.scene = scene
        self.before = before
        self.after = after
        self.description = description

    def undo(self) -> None:
        self.scene.rig = self.before

    def redo(self) -> None:
        self.scene.rig = self.after


class ObjectLinkCommand:
    """AD-036 §4.4: links of objects to bones as one History entry: `(object, before, after)` per object (`BoneId` or
    None each)."""

    def __init__(self, changes: list, description: str) -> None:
        self.changes = list(changes)
        self.description = description

    def undo(self) -> None:
        for obj, before, _ in self.changes:
            obj.bone = before

    def redo(self) -> None:
        for obj, _, after in self.changes:
            obj.bone = after


def has_stored_weights(mesh) -> bool:
    lid = skin_layer(mesh)
    return lid is not None and bool(mesh.layer_items(lid))


# -- gesture kinds -----------------------------------------------------------------------------------------


class _RigGesture(GestureSession):
    """What every rig gesture shares: the label, and the rig commands refused underneath it (`GESTURE_REFUSES`
    holds them for every gesture)."""

    def __init__(self, skeleton: "SkeletonController", command: str, key: str, origin) -> None:
        super().__init__(skeleton.gestures, command, key, (), origin)
        self.skeleton = skeleton


class BoneGesture(_RigGesture):
    """W/E/R in pose mode (§8.4; owner "transform"): E rotates the current bone about its posed head (constraint keys
    X/Y/Z; `K` = World / bone-local), W translates it on the camera plane, R scales it uniformly. Every step computes
    the bone's local pose from the press pose (no drift); release commits (no History entry: the pose is view
    state), Esc restores the press pose exactly."""

    def __init__(self, skeleton: "SkeletonController", command: str, key: str, origin, bone: BoneId) -> None:
        super().__init__(skeleton, command, key, origin)
        self.bone = bone
        self.pose_before = dict(skeleton.pose)
        self.local = skeleton.pose.get(bone, REST)
        rig = skeleton.rig
        b = rig.bone(bone)
        transforms = skin_transforms(rig, skeleton.pose)
        parent = transforms.get(b.parent) if b.parent is not None else None
        pm = _I3 if parent is None else parent[0]
        self.parent_scale = _linear_scale(pm)
        rp = tuple(tuple(x / self.parent_scale for x in row) for row in pm)
        rc, _ = rest_frame(b)
        # F maps the bone's local (rest-frame) directions to world through its parent's pose
        self.frame = object_space.matmul3(rp, rc)
        self.head = _affine_point(transforms.get(bone), b.head)
        self.axis = None
        self.mask = None  # Move: the constraint's mask in the constraint frame
        self.axes = None  # Move: the constraint frame (world columns), None = world
        self.move = (0.0, 0.0, 0.0)
        self.pixels = 0.0
        self.angle = 0.0
        self.dial: DialAngle | None = None

    @property
    def label(self) -> str:
        return f"Pose {TRANSFORM_COMMANDS[self.command][0]}"

    def _bone_axes(self):
        """The bone's current axes in world (columns of F·R_L): the bone-local frame of `K`."""
        return object_space.matmul3(self.frame, self.local.rotation)

    def step(self, dx: float, dy: float) -> bool:
        services = self.services
        camera = services.camera
        command = self.command
        controller = self._controller
        if not self.begun:
            space = None if command == commands.SCALE else controller.axis_constraint
            self.space = space
            local = controller.orientation == transform_space.NORMAL
            frame = self._bone_axes() if local else None
            if command == commands.ROTATE:
                if space is None:
                    self.axis = camera.basis()[0]
                else:
                    a = _resolve_space(space, for_rotation=True)
                    self.axis = _unit(_mul(frame, a)) if frame is not None else a
            elif command == commands.MOVE and space is not None:
                self.mask = _resolve_space(space, for_rotation=False)
                self.axes = frame
            self.begun = True
        if command == commands.MOVE:
            width, height = services.viewport_size
            delta = camera.screen_delta_to_world(self.head, dx, dy, width, height)
            if self.mask is not None:
                if self.axes is None:
                    delta = tuple(d * m for d, m in zip(delta, self.mask))
                else:
                    u = _mul(_t(self.axes), delta)
                    delta = _mul(self.axes, tuple(x * m for x, m in zip(u, self.mask)))
            self.move = tuple(self.move[i] + delta[i] for i in range(3))
        elif command == commands.ROTATE:
            self._rotate_angle(dx)
        else:
            self.pixels += dx + dy
        pose = dict(self.pose_before)
        pose[self.bone] = self._local_now()
        self.skeleton.set_pose(pose)
        return True

    def _rotate_angle(self, dx: float) -> None:
        services = self.services
        width, height = (int(v) for v in services.viewport_size)
        shift = services.modifiers[0]
        if self.rotate_virtual is None:
            self.angle += RotateTool.RADIANS_PER_PIXEL * dx * (0.2 if shift else 1.0)
            return
        if self.dial is None:
            self.dial = DialAngle(services.camera, self.head, self.axis, self.rotate_press, width, height)
        self.angle = self.dial.update(*self.rotate_virtual, width, height, shift, self.snap_held())

    def _local_now(self) -> BonePose:
        """The bone's local pose from the press pose `L = (R, t, s)` (AD-028 §5.1; F = the parent-posed rest frame,
        `s_p` the parent's scale): Rotate about the posed head, `R' = Fᵀ·Q·F·R`, `t` kept; Move, `t' = t + Fᵀ·d / s_p`;
        Scale about the posed head, `s' = f·s`. Exactly the press pose while nothing has accumulated."""
        local = self.local
        command = self.command
        if command == commands.MOVE:
            if self.move == (0.0, 0.0, 0.0):
                return local
            e = _mul(_t(self.frame), self.move)
            t = tuple(local.translation[i] + e[i] / self.parent_scale for i in range(3))
            return dataclasses.replace(local, translation=t)
        if command == commands.ROTATE:
            if self.angle == 0.0:
                return local
            q = object_space.axis_angle_rotation(self.axis, self.angle)
            f = self.frame
            rl = object_space.matmul3(object_space.matmul3(_t(f), q), f)
            rotation = object_space.orthonormalize(object_space.matmul3(rl, local.rotation))
            return dataclasses.replace(local, rotation=rotation)
        factor = max(ScaleTool.MIN_SCALE, 1.0 + ScaleTool.SCALE_PER_PIXEL * self.pixels)
        if factor == 1.0:
            return local
        return dataclasses.replace(local, scale=local.scale * factor)

    def release(self) -> None:
        services = self.services
        name = self.skeleton.rig.bone(self.bone).name if self.skeleton.rig.has_bone(self.bone) else "bone"
        if not self.begun:
            services.status(f"{self.label}: no motion, {name!r} unchanged")
            return
        what = {commands.MOVE: "moved", commands.ROTATE: "rotated", commands.SCALE: "scaled"}[self.command]
        extra = f" {math.degrees(self.angle):.1f}°" if self.command == commands.ROTATE else ""
        toggle = self.skeleton.key_text(commands.POSE_TOGGLE_REST)
        services.status(
            f"Pose: {name!r} {what}{extra}{constraint_suffix(self.space)} (view state, no Undo step;"
            f" {toggle} = rest pose)"
        )

    def abort(self) -> None:
        self.skeleton.set_pose(self.pose_before)


class _WeightsGesture(_RigGesture):
    """The weight gestures' common lifecycle (§8.4): nothing is written before the first motion; from it the mesh
    records into one journal (the "Skin" layer created inside it if absent) and every step writes
    `WeightStroke.step(targets)` from the press values; release = `end_change` -> one layer-only entry, Esc =
    `rollback_change`. Under symmetry the partners get the same target (the bone is on the plane, checked at the
    arm). Masked vertices keep their values; a partial mask scales the change."""

    def __init__(self, skeleton: "SkeletonController", command: str, key: str, origin, bone: BoneId) -> None:
        super().__init__(skeleton, command, key, origin)
        services = self.services
        self.bone = bone
        self.mesh = services.scene.mesh
        self.travel = 0.0
        self.before: MeshChange | None = None
        self.stroke: WeightStroke | None = None
        self.selection_before = services.selection_snapshot()
        lid = skin_layer(self.mesh)
        # the vertices that have the bone at the press (a narrowed field leaves no trace of a wider one)
        self.had_bone = (
            frozenset(v for v, value in self.mesh.layer_items(lid) if any(k == bone for k, _ in value))
            if lid is not None else frozenset()
        )
        self.partners = {}
        if self.mesh.symmetry_definition is not None:
            self.partners = {
                v: c.partner for v, c in vertex_correspondence(self.mesh).items()
                if getattr(c, "partner", None) is not None
            }

    @property
    def label(self) -> str:
        return "Weights from group" if self.command == commands.WEIGHTS_FROM_GROUP else "Set weight"

    # what a kind gives: the targets {vertex: x} for its current gesture value
    def targets(self) -> dict:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError

    def _record(self) -> None:
        if self.before is not None:
            return
        mesh = self.mesh
        self.before = mesh.begin_change()
        lid = skin_layer(mesh)
        if lid is None:
            lid = mesh.add_point_layer(PointLayerInfo(SKIN_LAYER_NAME, LayerKind.WEIGHTS))
        self.stroke = WeightStroke(mesh, lid, self.bone, self.skeleton.rig, ())
        self.begun = True

    def _masked(self, targets: dict) -> dict:
        """Mask (and Hide) protect: a fully masked vertex keeps its press value, a partial mask m scales the change by
        (1 - m) (`soft_target`)."""
        mask = self.services.mask_values(set(targets))
        if not mask:
            return targets
        stroke = self.stroke
        out = {}
        for v, x in targets.items():
            m = mask.get(v, 0.0)
            if m >= MASK_FULL:
                continue
            if m > 0.0:
                x = soft_target(stroke.press_share(v), x, 1.0 - m)
            out[v] = x
        return out

    def _write(self) -> None:
        self._record()
        stroke = self.stroke
        mesh = self.mesh
        targets = self.targets()
        if self.partners:
            for v, x in list(targets.items()):
                p = self.partners.get(v)
                if p is not None and p not in targets:
                    targets[p] = x
        for v in list(targets) + list(self.had_bone):
            if v not in stroke.press and mesh.is_valid_vertex(v):
                stroke.press[v] = mesh.layer_value(stroke.layer, v)  # untouched so far: the press value
        targets = {v: max(0.0, min(1.0, x)) for v, x in targets.items() if v in stroke.press}
        stroke.step(self._masked(targets))
        self._show_share()
        self.services.status(self.describe())

    def apply_once(self) -> bool:
        """A value that did not come from the mouse (the panel): one write from the press values, one History entry -
        the gesture's own stroke, committed at once."""
        try:
            self._write()
        except Exception:
            self.abort()
            self.end()
            raise
        return self.commit()

    def _show_share(self) -> None:
        """The current bone's share on the shading overlay (§8.4), so the width shows also at rest."""
        stroke = self.stroke
        shares = bone_shares(self.mesh, stroke.layer, self.bone, stroke.press)
        if self.services.show_soft_weights(shares, SHARE_VIEW_MODE):
            self.soft_op_running = True
            self.soft_shown = True

    def step(self, dx: float, dy: float) -> bool:
        if dx == 0:
            return False
        self.travel += dx
        self._write()
        return True

    def ctrl_changed(self, held: bool) -> bool:
        if not held:
            self.ctrl_snap_ok = True
        if not self.begun:
            return False
        self._write()
        return True

    def release(self) -> None:
        services = self.services
        if self.before is None:
            services.status(f"{self.label}: no change")
            return
        before, self.before = self.before, None
        mesh = self.mesh
        delta = mesh.end_change(before)
        if delta.empty:
            services.status(f"{self.label}: no change")
            return
        services.history.push(MeshDeltaCommand(mesh=mesh, delta=delta, description=self.label))
        services.record_selection_history(self.selection_before, mesh_step=False)
        services.status(f"{self.describe()} - committed (Ctrl+Z takes it back)")

    def abort(self) -> None:
        before, self.before = self.before, None
        if before is not None:
            self.mesh.rollback_change(before)

    def cleanup(self) -> None:
        # a weight gesture that ended without release / abort (refused, Undo while armed): nothing stays
        self.abort()


class FalloffGesture(_WeightsGesture):
    """Weights from the active group (§8.4, hold): seeds = the vertices of the group's live faces, the field from
    the Soft settings' metric and curve (`symmetric_influence` under symmetry), its width in % of the mesh's bounding
    radius (mouse left / right, starting at the Soft radius step). Each step sets the current bone to the field on
    the field ∪ the vertices that had the bone at the press - it replaces the bone's weights. A tap = the start
    width."""

    def __init__(self, skeleton, key, origin, bone, seeds, group: str) -> None:
        super().__init__(skeleton, commands.WEIGHTS_FROM_GROUP, key, origin, bone)
        services = self.services
        self.seeds = frozenset(seeds)
        self.group = group
        soft = services.soft_settings
        self.start_percent = float(RADIUS_STEPS_PERCENT[soft.radius_step])
        _, self.bounding_radius = mesh_center_and_radius(self.mesh)
        self.percent = self.start_percent
        self._cache: tuple | None = None
        self.field()  # raises SoftSymmetryRefusal at the arm (asymmetric group under symmetry)

    def field(self) -> dict:
        percent = self.percent
        if self._cache is not None and self._cache[0] == percent:
            return self._cache[1]
        soft = self.services.soft_settings
        settings = dataclasses.replace(soft, world_radius=self.bounding_radius * percent / 100.0)
        weights = self._controller.smooth_soft_weights(self.seeds, settings)
        self._cache = (percent, weights)
        return weights

    def targets(self) -> dict:
        self.percent = max(0.0, min(FALLOFF_MAX_PERCENT, self.start_percent + self.travel / FALLOFF_PX_PER_PERCENT))
        field = self.field()
        targets = {v: field.get(v, 0.0) for v in set(field) | set(self.had_bone)}
        return targets

    def describe(self) -> str:
        name = self.skeleton.bone_name(self.bone)
        return f"Weights from group {self.group!r} -> {name!r}: falloff {self.percent:.0f} %"

    def release(self) -> None:
        if self.before is None:  # a tap: the start width
            self._write()
        super().release()


class WeightGesture(_WeightsGesture):
    """Set the current bone's weight on the selection (§8.4, hold): mouse left / right = the value 0-1 (Ctrl snaps
    to 0.1), starting at the selection's mean share. With Soft on the change falls off outside the selection
    (`soft_target` with the Soft field; the wheel steps its radius live). A tap writes nothing."""

    def __init__(self, skeleton, key, origin, bone, seeds, field: dict) -> None:
        super().__init__(skeleton, commands.WEIGHT_SET, key, origin, bone)
        self.seeds = frozenset(seeds)
        self.field_weights = field
        mesh = self.mesh
        lid = skin_layer(mesh)
        shares = [bone_share(mesh.layer_value(lid, v), bone) if lid is not None else 0.0 for v in sorted(self.seeds)]
        self.start = math.fsum(shares) / len(shares)
        self.value = self.start
        if field is not None:
            self.soft = self.services.soft_settings
            self.soft_reference = self.soft.world_radius * 100.0 / self.soft.radius_percent

    def targets(self) -> dict:
        x = max(0.0, min(1.0, self.start + self.travel / WEIGHT_PX_PER_UNIT))
        if self.snap_held():
            x = round(x / WEIGHT_SNAP) * WEIGHT_SNAP
        self.value = x
        stroke = self.stroke
        mesh = self.mesh
        layer = stroke.layer
        if self.field_weights is None:
            return {v: x for v in self.seeds}
        out = {}
        for v, s in self.field_weights.items():
            old = bone_share(stroke.press[v] if v in stroke.press else mesh.layer_value(layer, v), self.bone)
            out[v] = soft_target(old, x, s)
        return out

    def describe(self) -> str:
        name = self.skeleton.bone_name(self.bone)
        soft = " (Soft)" if self.field_weights is not None else ""
        return f"Set weight {name!r}: {self.value:.2f} on {len(self.seeds)} points{soft}"

    def soft_live(self) -> bool:
        return self.field_weights is not None and self.soft is not None

    def reweight(self, settings) -> None:
        self.soft = settings
        try:
            self.field_weights = self._controller.smooth_soft_weights(self.seeds, settings)
        except SoftSymmetryRefusal:
            return
        if self.begun:
            self._write()


def bone_shares(mesh, layer, bone: BoneId, vertices=None) -> dict:
    """`{vertex: share > 0}` of `bone` in the weights `layer` - over `vertices`, or every stored value (a vertex at the
    layer default has no bone). What the weight display shows (§8.4; the weight view, GUI Phase A3)."""
    if vertices is None:
        items = mesh.layer_items(layer)
    else:
        items = ((v, mesh.layer_value(layer, v)) for v in vertices)
    shares = {}
    for v, value in items:
        w = bone_share(value, bone)
        if w > 0.0:
            shares[v] = w
    return shares


class ShareCache:
    """The weight view's share (GUI Phase A3): `bone_shares` of one (mesh, layer, bone), recomputed only when that key
    changed or the mesh's layers or topology changed since the last read (a `Mesh.watch()`); positions alone never
    recompute it. `computes` counts the recomputations (tests, probe)."""

    def __init__(self) -> None:
        self._watch = None
        self._key: tuple | None = None
        self.shares: dict = {}
        self.computes = 0

    def get(self, mesh, layer, bone: BoneId) -> dict:
        watch = self._watch
        if watch is None or watch.mesh is not mesh:
            if watch is not None:
                watch.close()
            self._watch = mesh.watch()
            self._key = None
        else:
            change = watch.take()
            if change.layers_touched or change.edges or change.faces:
                self._key = None
        key = (id(mesh), layer, bone)
        if self._key != key:
            self.shares = bone_shares(mesh, layer, bone)
            self._key = key
            self.computes += 1
        return self.shares

    def close(self) -> None:
        if self._watch is not None:
            self._watch.close()
        self._watch, self._key, self.shares = None, None, {}


# -- the controller ------------------------------------------------------------------------------------------


class SkeletonController:
    """The rig cluster (module docstring): `pose`, `last_pose`, `current` (the current bone's id, None = none
    chosen) and `pose_mode`; the bound cache."""

    def __init__(self, services: AppServices, gestures: GestureController) -> None:
        self.services = services
        self.gestures = gestures
        self.pose: dict = {}
        self.last_pose: dict = {}
        self.current: Optional[BoneId] = None
        self.pose_mode = False
        #: the chain tool snaps to object pivots and bone ends (view state, not saved; the panel's checkbox)
        self.chain_snap = True
        #: the chain tool's constraint for the tip (`bone_chain.AXIS_MODES`; view state, not saved; the panel's switch)
        self.chain_axis = "free"
        self._bound: dict = {}  # id(mesh) -> [mesh, watch, bound]
        #: AD-036 §5.2: the pose the skin stage and the links are shown - the user's `pose` with the gaze-driven eye
        #: bones' channels replaced (`ObjectController.shown_pose`); `pose` / `last_pose` stay the user's. Wired by the app.
        self.pose_filter = lambda pose: pose
        #: called after the shown pose changed (the app re-draws the linked objects)
        self.on_pose_shown = lambda: None
        #: the three stage-7 policies, in order (AD-028 §8.2)
        self.policies = (self.pose_mode_refusal, self.posed_refusal, self.placement_refusal)

    # -- reads ----------------------------------------------------------------------------------------

    @property
    def rig(self) -> Optional[Rig]:
        return self.services.scene.rig

    @property
    def hidden(self) -> frozenset:
        """The bones hidden by the outliner's eye (AD-030, 2026-11-07): `Bone.hidden`, saved with the scene and an
        Undo step. Not drawn, not picked, skipped by next / previous."""
        rig = self.rig
        return frozenset() if rig is None else rig.hidden_ids()

    @property
    def chain(self) -> Optional[BoneChainSession]:
        """The running bone chain session, None without one."""
        session = self.services.interaction.session
        return session if isinstance(session, BoneChainSession) else None

    @property
    def current_bone(self) -> Optional[BoneId]:
        """The current bone: the chosen one while the rig has it, else the rig's last bone; None without bones."""
        rig = self.rig
        if rig is None or not rig.bones:
            return None
        if self.current is not None and rig.has_bone(self.current):
            return self.current
        return rig.bones[-1].id

    def bone_name(self, bone) -> str:
        rig = self.rig
        return rig.bone(bone).name if rig is not None and rig.has_bone(bone) else "?"

    def posed(self) -> bool:
        return is_posed(self.rig, self.pose)

    def bound(self, mesh) -> bool:
        """AD-028 §7.1 "bound": a rig exists and the mesh has a weights layer with a stored value. Cached per mesh
        behind a watch: re-read only after that mesh's layers changed."""
        if self.rig is None:
            return False
        entry = self._bound.get(id(mesh))
        if entry is None or entry[0] is not mesh:
            objects = self.services.scene.objects
            live = {id(obj.mesh) for obj in objects.values()}
            for key in [k for k in self._bound if k not in live]:
                self._bound.pop(key)[1].close()
            entry = self._bound[id(mesh)] = [mesh, mesh.watch(), has_stored_weights(mesh)]
            return entry[2]
        watch = entry[1]
        if watch.peek().layers_touched:
            watch.take()
            entry[2] = has_stored_weights(mesh)
        return entry[2]

    def linked(self, obj) -> Optional[BoneId]:
        """AD-036 §4.1: the bone `obj` follows now (its link while the rig has the bone), None otherwise."""
        return bone_links.link_of(self.rig, obj)

    def key_text(self, command: str) -> str:
        """The first key bound to `command` (for the texts), or the command name."""
        for inp in self.services.bindings.inputs_for(command):
            if inp.kind == "key":
                return key_label(inp)
        return command

    # -- view state -----------------------------------------------------------------------------------

    def set_pose(self, pose) -> None:
        """The pose (identity entries dropped) - the controller's and, through `pose_filter`, the skin stage's (§6)."""
        self.pose = {b: p for b, p in pose.items() if not p.is_identity}
        self.show_pose()

    def show_pose(self) -> None:
        """AD-036 §5.2: hand the shown pose (the user's, the gaze-driven eye bones replaced) to the skin stage and the
        links. Also after a gaze or link change, which can change the shown pose without a pose step."""
        self.services.skin.provider.set_pose(self.pose_filter(self.pose))
        self.on_pose_shown()

    def reset(self) -> None:
        """A new scene: rest pose, no current bone, pose mode off (the pose is not saved, §6)."""
        chain = self.chain
        if chain is not None:
            chain.end(quiet=True)  # a loaded scene has no chain to continue
        self.pose, self.last_pose = {}, {}
        self.current = None
        self.pose_mode = False
        for entry in self._bound.values():
            entry[1].close()
        self._bound.clear()
        self.services.skin.provider.set_pose({})

    def _prune(self) -> None:
        """Pose channels of bones the rig no longer has go (they do not come back on Undo, §6)."""
        rig = self.rig
        has = (lambda b: False) if rig is None else rig.has_bone
        if any(not has(b) for b in self.pose):
            self.set_pose({b: p for b, p in self.pose.items() if has(b)})
        self.last_pose = {b: p for b, p in self.last_pose.items() if has(b)}
        if self.current_bone is None:
            self.pose_mode = False

    def after_history(self) -> None:
        """After Undo / Redo: the rig may have lost or regained bones; a running chain follows the history; a link step
        may change which eye bones the gaze drives (the shown pose)."""
        self._prune()
        self.show_pose()
        chain = self.chain
        if chain is not None:
            chain.resync()

    def leave_pose_mode(self) -> None:
        if self.pose_mode:
            self.pose_mode = False

    # -- commands -------------------------------------------------------------------------------------

    def command(self, command: str) -> bool:
        if command == commands.BONE_ADD:
            return self.add_bone()
        if command == commands.BONE_DELETE:
            return self.delete_bone()
        if command == commands.BONE_RENAME:
            return self.rename_bone()
        if command in (commands.BONE_NEXT, commands.BONE_PREVIOUS):
            return self.step_bone(1 if command == commands.BONE_NEXT else -1)
        if command == commands.POSE_MODE:
            return self.toggle_pose_mode()
        if command == commands.POSE_TOGGLE_REST:
            return self.toggle_rest()
        if command == commands.POSE_RESET_BONE:
            return self.reset_bone()
        return False

    def _busy(self, label: str) -> bool:
        owner = self.services.interaction_owner
        if owner is not None:
            self.services.status(f"{label}: not while the {owner} interaction runs")
            return True
        return False

    def _push_rig(self, after: Rig, description: str, extra: list = ()) -> None:
        services = self.services
        scene = services.scene
        before_selection = services.selection_snapshot()
        rig_command = RigCommand(scene, scene.rig, after, description)
        scene.rig = after
        command = rig_command if not extra else CompositeCommand([*extra, rig_command], description)
        services.history.push(command)
        services.record_selection_history(before_selection, mesh_step=False)

    def add_bone(self) -> bool:
        """`BONE_ADD` (§8.3): head = the Working Pivot, tail = the centre of the component selection (both to world),
        parent = the current bone, name `Bone n`, roll 0; creates the rig if absent; the new bone is current."""
        services = self.services
        label = "Add bone"
        if self._busy(label):
            return False
        selection = services.selection
        if selection.mode is SelectionMode.OBJECT:
            services.status(f"{label}: works from points/edges/faces - press 1/2/3")
            return False
        pivot = services.active_pivot
        if pivot is None:
            services.status(
                f"{label}: place the pivot ({self.key_text(commands.PIVOT_PLACE)}) in the joint first"
            )
            return False
        mesh = services.scene.mesh
        vertices = resolve_selection_vertices(mesh, selection, selection.mode)
        if not vertices:
            services.status(f"{label}: select the points / faces the bone points to (its tip goes to their centre)")
            return False
        edit = services.scene.edit_object
        head = object_space.to_world(edit, pivot)
        tail = object_space.to_world(edit, selection_pivot(mesh, vertices))
        if math.dist(head, tail) <= 1e-9 * max(1.0, max(abs(c) for c in head)):
            services.status(f"{label}: the pivot sits on the selection's centre - the bone would have no length")
            return False
        scene = services.scene
        rig = scene.rig if scene.rig is not None else Rig()
        name = self.free_bone_name(rig)
        parent = self.current_bone
        after, bid = rig.with_new_bone(name, head, tail, parent=parent)
        self._push_rig(after, f"Add bone {name!r}")
        self.current = bid
        under = f" under {self.bone_name(parent)!r}" if parent is not None else ""
        services.status(
            f"Bone {name!r} added{under} (pivot -> selection centre). {self.key_text(commands.WEIGHTS_FROM_GROUP)}"
            f" held = weights from the active group, {self.key_text(commands.POSE_MODE)} = pose mode"
        )
        return True

    def rename_bone(self, name: str | None = None, bone: BoneId | None = None) -> bool:
        """The current bone, or `bone` (the outliner's double click, AD-030), gets `name` (without: the next of
        `BONE_NAMES`). A name another bone has is refused (bone names are unique)."""
        services = self.services
        label = "Rename bone"
        if self._busy(label):
            return False
        if bone is None:
            bone = self.current_bone
        elif self.rig is None or not self.rig.has_bone(bone):
            return False
        if bone is None:
            services.status(f"{label}: no bone yet ({self.key_text(commands.BONE_ADD)} adds one)")
            return False
        rig = self.rig
        old = rig.bone(bone).name
        taken = {b.name for b in rig.bones} - {old}
        if name is None:
            start = BONE_NAMES.index(old) + 1 if old in BONE_NAMES else 0
            name = next(
                (BONE_NAMES[(start + i) % len(BONE_NAMES)] for i in range(len(BONE_NAMES))
                 if BONE_NAMES[(start + i) % len(BONE_NAMES)] not in taken
                 and BONE_NAMES[(start + i) % len(BONE_NAMES)] != old),
                None,
            )
        name = name.strip() if isinstance(name, str) else name
        if not name or name == old or name in taken or len(name) > 64 or not name.isprintable():
            services.status(f"{label}: {name!r} is not a free name")
            return False
        self._push_rig(rig.with_name(bone, name), f"Rename bone {old!r} {name!r}")
        services.status(f"Bone {old!r} is now {name!r} (again: next name)")
        return True

    def delete_bone(self, bone: Optional[BoneId] = None) -> bool:
        """`BONE_DELETE` (§8.3): the current bone (or `bone`, the panel's button); its weights to its parent (or the
        object) in every bound mesh (`skin_weights.delete_bone_weights`), its children re-parented; one entry for all of
        it. Its pose channel goes; the parent becomes current."""
        services = self.services
        label = "Delete bone"
        if self._busy(label):
            return False
        if bone is None:
            bone = self.current_bone
        elif self.rig is None or not self.rig.has_bone(bone):
            return False
        if bone is None:
            services.status(f"{label}: no bone")
            return False
        rig = self.rig
        gone = rig.bone(bone)
        parts = []
        seen = set()
        for obj in services.scene.objects.values():
            mesh = obj.mesh
            if id(mesh) in seen:
                continue
            seen.add(id(mesh))
            lid = skin_layer(mesh)
            if lid is None:
                continue
            delta, count = record_mesh_change(mesh, lambda mesh=mesh, lid=lid: delete_bone_weights(mesh, lid, bone, rig))
            if count:
                parts.append(MeshDeltaCommand(mesh=mesh, delta=delta, description=f"Delete bone weights {obj.name!r}"))
        # AD-036 §4.4: the objects linked to it follow its parent (a root's are unlinked); an eye is unlinked (its link is
        # its own eye bone, §5.1). Before the rig changes, so Undo restores the links with the bone.
        relinks = []
        for obj in services.scene.objects.values():
            if obj.bone == bone:
                after = None if obj.eye is not None else gone.parent
                relinks.append((obj, obj.bone, after))
        for obj, _, after in relinks:
            obj.bone = after
        if relinks:
            parts.append(ObjectLinkCommand(relinks, f"Delete bone {gone.name!r}: links"))
        self._push_rig(rig.without_bone(bone), f"Delete bone {gone.name!r}", parts)
        self.current = gone.parent
        self._prune()
        self.show_pose()
        to = repr(self.bone_name(gone.parent)) if gone.parent is not None else "the object"
        note = ""
        if relinks:
            moved = [o.name for o, _, a in relinks if a is not None]
            freed = [o.name for o, _, a in relinks if a is None]
            note = "".join([f"; {', '.join(map(repr, moved))} now follow {to}" if moved else "",
                            f"; {', '.join(map(repr, freed))} follow no bone" if freed else ""])
        services.status(f"Bone {gone.name!r} deleted; its weights went to {to}{note} (Ctrl+Z brings it back)")
        return True

    # -- AD-036 §4.4: links of rigid parts (Bone panel; names and texts PROVISIONAL, no key) ----------------------

    def link_blocker(self) -> Optional[str]:
        """Why Link / Unlink cannot run now (None = they can; the panel greys its buttons)."""
        owner = self.services.interaction_owner
        if owner is not None:
            return f"not while the {owner} interaction runs"
        if self.posed():
            return f"the rig is posed - links change in the rest pose ({self.key_text(commands.POSE_TOGGLE_REST)})"
        if self.services.selection.mode is not SelectionMode.OBJECT or not self.services.selection.objects:
            return "select the parts in mode 4 (or in the Outliner)"
        return None

    def _link_targets(self, label: str) -> Optional[list]:
        services = self.services
        reason = self.link_blocker()
        if reason is not None:
            services.status(f"{label}: {reason}")
            return None
        selected = group_leaves(services.scene, services.selection.objects)  # a group stands for its members
        targets = [obj for obj in selected if obj.state is not ObjectState.REFERENCE]
        if not targets:
            services.status(f"{label}: only References selected - they stay where they are")
            return None
        return targets

    def link_selected(self, bone: Optional[BoneId] = None) -> bool:
        """Every selected object (group leaves, not References) follows `bone` (default: the current bone) - one Undo
        step. Refused as a whole while posed, for a bound mesh (linked xor bound, §4.1) and for an eye whose centre is
        not the bone's head (§5.1). At rest nothing moves (the link is rest-relative, §4.2)."""
        services = self.services
        label = "Link to bone"
        if bone is None:
            bone = self.current_bone
        rig = self.rig
        if bone is None or rig is None or not rig.has_bone(bone):
            services.status(f"{label}: no bone yet (Bone panel: start a chain)")
            return False
        targets = self._link_targets(label)
        if targets is None:
            return False
        name = self.bone_name(bone)
        for obj in targets:
            if self.bound(obj.mesh):
                services.status(f"{label}: {obj.name!r} has weights - a part follows a bone or is weighted, not both")
                return False
            if obj.eye is not None and not bone_links.eye_fits_bone(obj, rig, bone):
                services.status(
                    f"{label}: {obj.name!r} is an eye - it follows its own eye bone (head at the eyeball's centre:"
                    f" Bone panel, snap to the eye); {name!r} is not one"
                )
                return False
        changes = [(obj, obj.bone, bone) for obj in targets if obj.bone != bone]
        if not changes:
            services.status(f"{label}: {', '.join(repr(o.name) for o in targets)} already follow {name!r}")
            return False
        self._push_links(changes, f"Link to bone {name!r}")
        services.status(f"{', '.join(repr(o.name) for o, _, _ in changes)} follow {name!r} (Ctrl+Z takes it back)")
        return True

    def unlink_selected(self) -> bool:
        """The selected objects follow no bone - one Undo step; refused while posed (the part would jump)."""
        services = self.services
        label = "Unlink"
        targets = self._link_targets(label)
        if targets is None:
            return False
        changes = [(obj, obj.bone, None) for obj in targets if obj.bone is not None]
        if not changes:
            services.status(f"{label}: {', '.join(repr(o.name) for o in targets)} follow no bone")
            return False
        self._push_links(changes, "Unlink from bone")
        services.status(f"{', '.join(repr(o.name) for o, _, _ in changes)} follow no bone (Ctrl+Z takes it back)")
        return True

    def _push_links(self, changes: list, description: str) -> None:
        services = self.services
        before = services.selection_snapshot()
        for obj, _, after in changes:
            obj.bone = after
        services.history.push(ObjectLinkCommand(changes, description))
        services.record_selection_history(before, mesh_step=False)
        self.show_pose()  # an eye's link changes which bones the gaze drives; the links redraw

    def step_bone(self, step: int) -> bool:
        services = self.services
        rig = self.rig
        if rig is None or not rig.bones:
            services.status(f"Bones: none yet ({self.key_text(commands.BONE_ADD)} adds one)")
            return False
        ids = rig.bone_ids()
        at = ids.index(self.current_bone)
        for i in range(1, len(ids) + 1):  # the next bone that is not hidden (the outliner's eye)
            candidate = ids[(at + step * i) % len(ids)]
            if candidate not in self.hidden:
                break
        else:
            services.status("Bones: all hidden (outliner eye)")
            return False
        self.current = candidate
        services.status(f"Current bone: {self.bone_name(self.current)!r} ({ids.index(self.current) + 1}/{len(ids)})")
        return True

    def select(self, bone: BoneId) -> bool:
        """The outliner's click on a bone row: it becomes the current bone (as a click in pose mode, in any mode)."""
        rig = self.rig
        if rig is None or not rig.has_bone(bone) or self.gestures.session is not None:
            return False
        if self.current == bone:
            return False
        self.current = bone
        self.services.status(f"Current bone: {self.bone_name(bone)!r}")
        return True

    def set_hidden(self, bones, hidden: bool) -> bool:
        """The outliner's eye on bones: hide / show these, one Undo step (the flag is part of the rig and of the scene
        file). True = something changed."""
        rig = self.rig
        label = "Hide bone" if hidden else "Show bone"
        if rig is None or self._busy(label):
            return False
        known = {b for b in bones if rig.has_bone(b)}
        changed = (known - self.hidden) if hidden else (known & self.hidden)
        if not changed:
            return False
        names = ", ".join(repr(self.bone_name(b)) for b in sorted(changed))
        self._push_rig(rig.with_hidden(changed, hidden), f"{label} {names}")
        self.services.status(f"{'Hidden' if hidden else 'Shown'} bone {names}")
        return True

    def toggle_pose_mode(self) -> bool:
        services = self.services
        if self.pose_mode:
            self.pose_mode = False
            services.status(f"Pose mode off (the pose stays shown; {self.key_text(commands.POSE_TOGGLE_REST)} = rest)")
            return True
        if self.current_bone is None:
            services.status(f"Pose mode: no bone yet ({self.key_text(commands.BONE_ADD)} adds one)")
            return False
        self.pose_mode = True
        services.set_hovered(None)
        services.status(
            f"Pose mode: {self.bone_name(self.current_bone)!r} - click a bone, hold"
            f" {self.key_text(commands.ROTATE)} / {self.key_text(commands.MOVE)} / {self.key_text(commands.SCALE)}"
            " and move the mouse (view state, no Undo step); 1/2/3 to model"
        )
        return True

    def toggle_rest(self) -> bool:
        """`POSE_TOGGLE_REST` (§6): the pose <-> rest; from rest back to the last pose."""
        services = self.services
        if self.posed():
            self.last_pose = dict(self.pose)
            self.set_pose({})
            services.status(f"Rest pose ({self.key_text(commands.POSE_TOGGLE_REST)} = back to the pose)")
            return True
        rig = self.rig
        last = {b: p for b, p in self.last_pose.items() if rig is not None and rig.has_bone(b)}
        if not last:
            services.status(
                f"Pose: no pose yet ({self.key_text(commands.POSE_MODE)}, click the bone,"
                f" hold {self.key_text(commands.ROTATE)})"
            )
            return False
        self.set_pose(last)
        services.status(f"Pose again ({self.key_text(commands.POSE_TOGGLE_REST)} = rest pose)")
        return True

    def reset_bone(self) -> bool:
        services = self.services
        bone = self.current_bone
        if bone is None or bone not in self.pose:
            services.status("Reset bone: the current bone is at rest")
            return False
        pose = dict(self.pose)
        del pose[bone]
        self.set_pose(pose)
        services.status(f"Bone {self.bone_name(bone)!r} back at rest")
        return True

    # -- Bone tool 01: the chain tool, editing a bone, the panel's weight values (2026-11-17) -------------------

    @staticmethod
    def free_bone_name(rig: Rig) -> str:
        """`Bone n`, the first not taken (n from the bone count + 1)."""
        names = {b.name for b in rig.bones}
        n = len(rig.bones) + 1
        while f"Bone {n}" in names:
            n += 1
        return f"Bone {n}"

    def chain_blocker(self) -> Optional[str]:
        """Why the chain tool cannot start now (pure; the panel greys its button with it), None = it can: an
        interaction runs, a selection drag runs, no viewport, a morph target's editing view, or the rig is posed."""
        services = self.services
        owner = services.interaction_owner
        if owner is not None:
            return f"not while the {owner} interaction runs"
        if services.drag_select is not None:
            return "not while a selection drag runs"
        if services.viewport is None:
            return "no viewport"
        if services.morph_view_shift is not None:
            return "on the base only (Tab returns to it)"
        if self.posed():
            return f"the rig is posed - {self.key_text(commands.POSE_TOGGLE_REST)} = rest pose first"
        return None

    def edit_blocker(self) -> Optional[str]:
        """Why a bone cannot be edited now (pure), None = it can: an interaction runs, or the rig is posed (a bone's
        rest frame is edited at rest)."""
        owner = self.services.interaction_owner
        if owner is not None:
            return f"not while the {owner} interaction runs"
        if self.posed():
            return f"the rig is posed - {self.key_text(commands.POSE_TOGGLE_REST)} = rest pose first (a bone's rest frame is edited at rest)"
        return None

    def axis_object(self, head=None):
        """The object whose axis the "object axis" constraint and the align button use (Bone tool 02): the one selected
        object, else - with `head` - the object whose pivot sits on `head`; None = none. Hidden objects count (they are
        still the one selected / the pivot the head was snapped to)."""
        services = self.services
        objects = services.scene.objects
        picked = [objects[o] for o in services.selection.objects if o in objects]
        if len(picked) == 1:
            return picked[0]
        if head is not None:
            for obj in objects.values():
                if math.dist(object_space.pivot_world(obj), head) <= 1e-9:
                    return obj
        return None

    def set_chain_axis(self, mode: str) -> None:
        if mode not in AXIS_MODES:
            raise ValueError(f"chain axis: one of {AXIS_MODES}, got {mode!r}")
        self.chain_axis = mode

    def align_blocker(self, bone: Optional[BoneId] = None) -> Optional[str]:
        """Why a bone cannot be aligned to an object's axis now (pure; the panel greys its button): `edit_blocker`, no
        bone, or not exactly one selected object."""
        reason = self.edit_blocker()
        if reason is not None:
            return reason
        rig = self.rig
        if bone is None:
            bone = self.current_bone
        if rig is None or bone is None or not rig.has_bone(bone):
            return "no bone"
        if self.axis_object() is None:
            return "select exactly one object (mode 4, outliner)"
        return None

    def align_bone_to_axis(self, bone: Optional[BoneId] = None, obj=None) -> bool:
        """Aligns a bone (default: the current one) with the axis of an object (default: the one selected; `obj` a
        `SceneObject`): its direction becomes the object's local +Z in world (`eye_gaze.rest_forward`, an eye's gaze axis),
        its **head and length stay**, its roll too; the tail moves. One Undo step through `edit_bone`, at rest only (the
        refusals of `edit_bone`). Children keep their own rest frames (a rest edit, AD-028 addendum 2026-11-17)."""
        services = self.services
        label = "Align bone"
        rig = self.rig
        if bone is None:
            bone = self.current_bone
        if rig is None or bone is None or not rig.has_bone(bone):
            services.status(f"{label}: no bone")
            return False
        if obj is None:
            obj = self.axis_object()
            if obj is None:
                services.status(f"{label}: select exactly one object first (mode 4, outliner click)")
                return False
        b = rig.bone(bone)
        direction = eye_gaze.rest_forward(obj)
        tail = tuple(b.head[i] + direction[i] * b.length for i in range(3))
        if math.dist(tail, b.tail) <= 1e-12 * max(1.0, b.length):  # (rounding of head + d * length is no change)
            services.status(f"{label}: {b.name!r} already lies on the axis of {obj.name!r}")
            return False
        if not self.edit_bone(bone, tail=tail):
            return False
        services.status(
            f"Bone {b.name!r} aligned to the axis of {obj.name!r} (head and length kept; Ctrl+Z takes it back)"
        )
        return True

    def begin_chain(self, root: bool = False) -> bool:
        """Starts the chain tool (`bone_chain`; the panel's button, no key). The first bone's parent is the current
        bone, or none for `root`. Refused (`chain_blocker`): while an interaction runs, while posed, in a morph target's
        editing view and without a viewport."""
        services = self.services
        reason = self.chain_blocker()
        if reason is not None:
            if services.viewport is not None:
                services.status(f"Bone chain: {reason}")
            return False
        self.leave_pose_mode()
        parent = None if root else self.current_bone
        session = BoneChainSession(self, parent)
        services.interaction.start(session)
        services.set_hovered(None)
        services.refresh_hover()
        services.status(session.hint())
        return True

    def end_chain(self) -> bool:
        """The panel's "end chain" (Esc does the same through `Application`). True = a chain ended."""
        chain = self.chain
        return chain is not None and chain.end()

    def finish_chain(self, session: BoneChainSession) -> None:
        """The session leaves the slot (`BoneChainSession.end`); the weight view shows the share of the bone that is
        current now."""
        self.services.interaction.end(session)
        self.services.soft_preview_refresh()

    def add_chain_bone(self, head, tail, parent: Optional[BoneId]) -> Optional[Bone]:
        """One chain click's bone: `head` -> `tail` (world) under `parent`, one History step (`BONE_ADD`'s
        `RigCommand`), current from now on. None (a status line says why) = nothing changed."""
        services = self.services
        scene = services.scene
        rig = scene.rig if scene.rig is not None else Rig()
        if parent is not None and not rig.has_bone(parent):
            parent = None  # an Undo went past the bone the chain was started under
            services.status("Bone chain: its parent bone is gone (Undo) - the new bone has no parent")
        name = self.free_bone_name(rig)
        try:
            after, bid = rig.with_new_bone(name, head, tail, parent=parent)
        except ValueError as exc:
            services.status(f"Bone chain: {exc}")
            return None
        self._push_rig(after, f"Add bone {name!r}")
        self.current = bid
        return after.bone(bid)

    def edit_bone(
        self, bone: BoneId, *, name=KEEP, parent=KEEP, head=KEEP, tail=KEEP, roll=KEEP
    ) -> bool:
        """Edit a bone's rest frame, name or parent - one Undo step, at rest only (a bone's rest frame under a pose
        would move the posed surface under the user's hands, AD-028 §7.1: "rest pose first").

        `head` / `tail` are world positions, `roll` radians, `parent` a `BoneId` or None (a root); a field left at `KEEP`
        stays. What it does to the rest of the scene (AD-028 addendum 2026-11-17):

        - **Weights** are keyed by `BoneId` and are not touched; the mesh and its rest shape are not touched either, so
          the rest display is bit-identical before and after. Only a later pose deforms around the new rest frame.
        - **Children** keep their own rest frames (world space): moving a bone does not drag its children; re-parenting
          changes the hierarchy only (`Rig.with_bone`).
        - **Pose values** are local to the bone's rest frame (`BonePose`): while posed the edit is refused, and a
          remembered pose (the rest <-> pose toggle) is applied in the new frame afterwards - the jaw opens about the
          new hinge by the same turn."""
        services = self.services
        label = "Edit bone"
        rig = self.rig
        if rig is None or not rig.has_bone(bone):
            services.status(f"{label}: no such bone")
            return False
        reason = self.edit_blocker()
        if reason is not None:
            services.status(f"{label}: {reason}")
            return False
        old = rig.bone(bone)
        changes = {}
        parts = []
        if name is not KEEP:
            taken = {b.name for b in rig.bones} - {old.name}
            clean = name.strip() if isinstance(name, str) else name
            if not clean or clean in taken or len(clean) > 64 or not clean.isprintable():
                services.status(f"{label}: {clean!r} is not a free name")
                return False
            if clean != old.name:
                changes["name"] = clean
                parts.append("name")
        if parent is not KEEP:
            if parent is not None and not rig.has_bone(parent):
                services.status(f"{label}: no such parent bone")
                return False
            if parent is not None and (parent == bone or bone in rig.ancestors(parent)):
                where = "itself" if parent == bone else f"its own child {rig.bone(parent).name!r}"
                services.status(f"{label}: {old.name!r} cannot be a child of {where} (a bone hierarchy has no cycle)")
                return False
            if parent != old.parent:
                changes["parent"] = parent
                parts.append("parent")
        for field, value in (("head", head), ("tail", tail)):
            if value is not KEEP:
                point = tuple(float(c) for c in value)
                if point != getattr(old, field):
                    changes[field] = point
                    parts.append(field)
        if roll is not KEEP and float(roll) != old.roll:
            changes["roll"] = float(roll)
            parts.append("roll")
        if not changes:
            return False
        try:
            new = dataclasses.replace(old, **changes)  # `Bone` validates: finite, a length > 0
            after = rig.with_bone(new)
        except (ValueError, TypeError) as exc:
            services.status(f"{label}: {exc}")
            return False
        self._push_rig(after, f"Edit bone {old.name!r}: {', '.join(parts)}")
        services.status(
            f"Bone {new.name!r}: {', '.join(parts)} changed (rest edit - weights stay, the rest shape is untouched;"
            f" Ctrl+Z takes it back)"
        )
        return True

    def _weight_work_ready(self, label: str) -> bool:
        """The panel's weight operations: no interaction running (a gesture, a chain), a viewport."""
        services = self.services
        if services.viewport is None or self._busy(label):
            return False
        return True

    def weights_from_group_value(self, percent: float) -> bool:
        """"Weights from group" with a width given as a number (the panel): the `FalloffGesture`'s stroke at `percent` of
        the mesh's bounding radius, committed at once - one History entry, the refusals of the key (§8.4)."""
        label = "Weights from group"
        if not self._weight_work_ready(label):
            return False
        gesture = self._falloff_gesture(label, None, (None, True))
        if gesture is None:
            return False
        gesture.start_percent = max(0.0, min(FALLOFF_MAX_PERCENT, float(percent)))
        gesture._cache = None
        self.services.interaction.start(gesture)
        return gesture.apply_once()

    def set_weight_value(self, value: float) -> bool:
        """"Set weight" with a value given as a number (the panel): the `WeightGesture`'s stroke - the selection, the
        Soft field if Soft is on - at `value` 0-1, committed at once; one History entry, the refusals of the key."""
        label = "Set weight"
        if not self._weight_work_ready(label):
            return False
        gesture = self._weight_gesture(label, None, (None, True))
        if gesture is None:
            return False
        gesture.start = gesture.value = max(0.0, min(1.0, float(value)))
        gesture.ctrl_snap_ok = False  # a number is not snapped to tenths
        self.services.interaction.start(gesture)
        return gesture.apply_once()

    # -- the gestures -------------------------------------------------------------------------------

    def arm_bone_gesture(self, command: str, key: str, origin) -> bool:
        services = self.services
        bone = self.current_bone
        if bone is None:
            services.status("Pose mode: no bone")
            return False
        session = BoneGesture(self, command, key, origin, bone)
        services.interaction.start(session)
        label = TRANSFORM_COMMANDS[command][0]
        space = None if command == commands.SCALE else self.gestures.axis_constraint
        services.status(f"Pose {label}: {self.bone_name(bone)!r}{constraint_suffix(space)}{commit_hint(key)}")
        return True

    def _weights_refusal(self, label: str) -> tuple | None:
        """(bone, mesh) the weight gestures act on, or None with the refusal posted: a current bone, component work
        on the base, and under symmetry a bone on the plane (§8.4: off-centre needs its mirror bone)."""
        services = self.services
        bone = self.current_bone
        if bone is None:
            services.status(f"{label}: no bone yet ({self.key_text(commands.BONE_ADD)} adds one)")
            return None
        if services.selection.mode is SelectionMode.OBJECT:
            services.status(f"{label}: works from points/edges/faces - press 1/2/3")
            return None
        mesh = services.scene.mesh
        edit = services.scene.edit_object
        if edit.bone is not None:
            services.status(
                f"{label}: {edit.name!r} follows bone {self.bone_name(edit.bone)!r} - a part follows a bone or is"
                f" weighted, not both (unlink it first: Bone panel)"
            )
            return None
        definition = mesh.symmetry_definition
        if definition is not None and not self._on_plane(bone, definition):
            services.status(
                f"{label}: {self.bone_name(bone)!r} is off the symmetry plane - it needs its mirror bone (not yet);"
                f" Shift+S turns symmetry off"
            )
            return None
        return bone, mesh

    def bone_on_plane(self, bone, definition) -> bool:
        """Head and tail of `bone` lie on the edit mesh's symmetry plane `definition` (§8.4; the Weight Room asks too)."""
        return self._on_plane(bone, definition)

    def _on_plane(self, bone, definition) -> bool:
        edit = self.services.scene.edit_object
        b = self.rig.bone(bone)
        _, radius = mesh_center_and_radius(edit.mesh)
        tolerance = SEAM_TOLERANCE * max(1.0, radius)
        n, o = definition.plane_normal, definition.plane_point
        for p in (b.head, b.tail):
            q = object_space.to_object(edit, p)
            if abs(sum((q[i] - o[i]) * n[i] for i in range(3))) > tolerance:
                return False
        return True

    def _falloff_gesture(self, label: str, key, origin) -> Optional[FalloffGesture]:
        """The `FalloffGesture` for the current bone and the active group, or None with the refusal posted (§8.4). Not
        yet in the slot."""
        services = self.services
        picked = self._weights_refusal(label)
        if picked is None:
            return None
        bone, mesh = picked
        group = services.active_region
        faces = live_faces(mesh, group) if group is not None else frozenset()
        if not faces:
            services.status(f"{label}: make a group first (Ctrl+G on the faces)")
            return None
        seeds = {v for f in faces for v in mesh.face_vertices(f)}
        try:
            return FalloffGesture(self, key, origin, bone, seeds, group)
        except SoftSymmetryRefusal as exc:
            services.status(f"{label}: refused - {exc}")
            return None

    def arm_falloff(self, key: str, origin) -> bool:
        services = self.services
        label = "Weights from group"
        gesture = self._falloff_gesture(label, key, origin)
        if gesture is None:
            return False
        services.interaction.start(gesture)
        services.set_hovered(None)
        services.status(
            f"{label} {gesture.group!r} -> {self.bone_name(gesture.bone)!r}: mouse left/right = falloff width"
            f" ({gesture.start_percent:.0f} %), release {key.upper()} to commit, Esc cancels"
        )
        return True

    def _weight_gesture(self, label: str, key, origin) -> Optional[WeightGesture]:
        """The `WeightGesture` for the current bone on the selection (the Soft field if Soft is on), or None with the
        refusal posted. Not yet in the slot."""
        services = self.services
        picked = self._weights_refusal(label)
        if picked is None:
            return None
        bone, mesh = picked
        selection = services.selection
        seeds = resolve_selection_vertices(mesh, selection, selection.mode)
        mask = services.mask_values(seeds)
        if not seeds:
            services.status(f"{label}: select points first")
            return None
        if mask and all(mask.get(v, 0.0) >= MASK_FULL for v in seeds):
            services.status(f"{label}: all selected points are masked (Ctrl+M unmasks)")
            return None
        soft = services.soft_settings
        field = None
        if soft.enabled:
            try:
                field = self.gestures.smooth_soft_weights(seeds, soft)
            except SoftSymmetryRefusal as exc:
                services.status(f"{label}: refused - {exc}")
                return None
        return WeightGesture(self, key, origin, bone, seeds, field)

    def arm_weight(self, key: str, origin) -> bool:
        services = self.services
        label = "Set weight"
        gesture = self._weight_gesture(label, key, origin)
        if gesture is None:
            return False
        services.interaction.start(gesture)
        services.set_hovered(None)
        soft_note = " (Soft: wheel = radius)" if gesture.field_weights is not None else ""
        services.status(
            f"{label} {self.bone_name(gesture.bone)!r}: {len(gesture.seeds)} points at {gesture.start:.2f}{soft_note} -"
            f" mouse left/right = value (Ctrl: steps of 0.1), release {key.upper()} to commit"
        )
        return True

    # -- picking and drawing ------------------------------------------------------------------------

    def posed_segments(self) -> list:
        """(BoneId, head, tail) per bone in its posed placement (world)."""
        rig = self.rig
        if rig is None:
            return []
        transforms = skin_transforms(rig, self.services.skin.provider.pose)  # the shown pose (a gaze-driven eye bone, AD-036)
        out = []
        for b in rig.bones:
            a = transforms.get(b.id)
            out.append((b.id, _affine_point(a, b.head), _affine_point(a, b.tail)))
        return out

    def pick_bone(self, x: float, y: float) -> bool:
        """A click in pose mode: the nearest bone whose projected head-tail segment is within `PICK_RADIUS_PX`
        becomes current. True = a bone was hit."""
        bone = self.bone_at(x, y)
        if bone is None:
            return False
        self.current = bone
        self.services.status(f"Current bone: {self.bone_name(bone)!r}")
        return True

    def bone_at(self, x: float, y: float) -> Optional[BoneId]:
        """The shown bone whose projected (posed) head-tail segment is nearest to the screen point and within
        `PICK_RADIUS_PX`, None if none is (pure; also the Weight Room's click on a bone line, AD-041 W-5)."""
        services = self.services
        camera = services.camera
        width, height = services.viewport_size
        best = None
        for bid, head, tail in self.posed_segments():
            if bid in self.hidden:
                continue
            a = camera.project_to_screen(head, width, height)
            b = camera.project_to_screen(tail, width, height)
            if a is None or b is None:
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            length2 = dx * dx + dy * dy
            t = 0.0 if length2 == 0.0 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / length2))
            d = math.hypot(a[0] + t * dx - x, a[1] + t * dy - y)
            if d <= PICK_RADIUS_PX and (best is None or d < best[0]):
                best = (d, bid)
        return None if best is None else best[1]

    def gizmo_pivot(self):
        """The gizmo in pose mode: at the current bone's posed head (world)."""
        bone = self.current_bone
        if bone is None:
            return None
        for bid, head, _ in self.posed_segments():
            if bid == bone:
                return head
        return None

    def bone_items(self, camera, scale: float) -> list:
        """Line items in world space (§8.5): a line head -> tail per bone in its posed placement and a small cross at
        its head; the current bone highlighted; dimmed outside pose mode."""
        segments = self.posed_segments()
        chain = self.chain
        current = self.current_bone
        items = []
        for bid, head, tail in segments:
            if bid in self.hidden:
                continue
            color = COLOR_BONE_CURRENT if bid == current else COLOR_BONE
            if not self.pose_mode and chain is None:  # (a bone chain draws them at full strength)
                color = color[:3] + (BONE_DIM_ALPHA,)
            width = BONE_LINE_WIDTH_CURRENT if bid == current else BONE_LINE_WIDTH
            arm = _gizmo.gizmo_size(camera, head, scale) * BONE_CROSS_RATIO
            cross = []
            for _, d in _gizmo.WORLD_AXES:
                cross += [head[0] - d[0] * arm, head[1] - d[1] * arm, head[2] - d[2] * arm,
                          head[0] + d[0] * arm, head[1] + d[1] * arm, head[2] + d[2] * arm]
            items.append(_gizmo.DrawItem((*head, *tail), color, "lines", width))
            items.append(_gizmo.DrawItem(tuple(cross), color, "lines", BONE_LINE_WIDTH))
        if chain is not None:
            items += chain.items(camera, scale)  # the pending bone and the marker under the cursor
        return items

    def status_text(self) -> str | None:
        """The HUD's "Rig" row (§8.5; only with a rig): current bone · n bones · rest / posed · pose mode."""
        rig = self.rig
        if rig is None:
            return None
        n = len(rig.bones)
        current = self.current_bone
        parts = [repr(self.bone_name(current)) if current is not None else "no bone",
                 f"{n} bone{'s' if n != 1 else ''}", "posed" if self.posed() else "rest"]
        if self.pose_mode:
            parts.append("pose mode")
        if self.chain is not None:
            parts.append("bone chain")
        return " · ".join(parts)

    # -- the stage-7 policies (pure) ----------------------------------------------------------------

    def pose_mode_refusal(self, command: str, ctx: RunContext) -> Refusal | None:
        """(1) In pose mode only pose, rig and view-state commands run (§8.2)."""
        if not self.pose_mode or command in POSE_MODE_ALLOWS:
            return None
        return Refusal(POSE_MODE_REFUSAL)

    def posed_text(self, key) -> str | None:
        """(2) §7.1: the refusal text if `key` (a command or a method name) would change the positions or topology of
        a posed, bound edit mesh; None otherwise. Pure."""
        services = self.services
        if not self.posed() or not edits_positions_or_topology(key):
            return None
        if not self.bound(services.scene.mesh) and self.linked(services.scene.edit_object) is None:
            return None  # AD-036 §4.5: a linked edit object is refused like a bound one
        return f"{command_label(key)}: the mesh is posed ({self.key_text(commands.POSE_TOGGLE_REST)} = rest pose)"

    def posed_refusal(self, command: str, ctx: RunContext) -> Refusal | None:
        if self.pose_mode and command in POSE_MODE_ALLOWS:
            return None  # W/E/R / the gizmo drag pose bones there
        if self.services.selection.mode is SelectionMode.OBJECT:
            return None  # object level (placement: policy 3; Delete removes objects)
        text = self.posed_text(command)
        return None if text is None else Refusal(text)

    def placement_refusal(self, command: str, ctx: RunContext) -> Refusal | None:
        """(3) §7.2: object W/E/R, Clear transform and a mirror partner's follow are refused for a bound object (mode
        `4`; reads the object selection, so only with `ctx.operands`)."""
        label = _PLACEMENT_LABELS.get(command)
        services = self.services
        if label is None or not ctx.operands or services.selection.mode is not SelectionMode.OBJECT:
            return None
        if self.pose_mode and command in POSE_MODE_ALLOWS:
            return None  # W/E/R pose the current bone there, not the selected objects (as `posed_refusal`)
        if self.rig is None:
            return None
        scene = services.scene
        for oid in sorted(services.selection.objects):
            obj = scene.objects.get(oid)
            if obj is None:
                continue
            candidates = [obj]
            pair = scene.mirror_pair_of(oid)
            if pair is not None and command != commands.CLEAR_TRANSFORM:
                partner = scene.objects.get(pair.other(oid))
                if partner is not None:
                    candidates.append(partner)
            for target in candidates:
                if self.bound(target.mesh):
                    return Refusal(f"{label}: {target.name!r} is locked while bound to the rig")
                linked = self.linked(target)
                if linked is not None and self.posed():
                    # AD-036 §4.5 (E3): a linked part moves at rest; in a pose it rides its bone
                    return Refusal(
                        f"{label}: {target.name!r} follows {self.bone_name(linked)!r} - the rig is posed"
                        f" ({self.key_text(commands.POSE_TOGGLE_REST)} = rest pose)"
                    )
        return None

