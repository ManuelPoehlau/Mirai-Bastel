"""The bone chain tool (Bone tool 01, 2026-11-17; AD-028 addendum 2026-11-17, `PROVISIONAL` names, texts, look).

Bones are placed by hand as a click chain (Maya / 3ds Max style): the first click sets the head, every further click
sets a tail and starts the next bone, whose parent is the previous one. The session ends on Esc or the panel's button
(`Application.end_bone_chain`). It is entered from the panel or a menu - no key (the hotkey map is full) - and the
`Ctrl+J` family (region -> selection -> Working Pivot) keeps working unchanged.

- **One session in the slot** (`owner "bonechain"`, not exclusive): it grabs the plain and the Shift LMB press, its
  drag steps and its release (a click under `CLICK_THRESHOLD_PX` places a point, a drag does nothing, as the Knife),
  hover (the app's coalesced re-pick: the preview costs one ray cast per frame, not per mouse event), leave and Shift held; Alt+LMB (orbit / pan), the wheel and the view keys go on as they were. `allows`
  lets only Cancel, Undo / Redo, navigation and view state through; everything else is refused silently - a tool does
  not run underneath the chain.
- **Where a click lands** (`BoneChainSession.point_at`), in this order: (1) the nearest object pivot or bone head /
  tail within `pivot.POINT_SNAP_PX` on screen (an object's pivot is a plain origin, `object_space.pivot_world`; for an
  eye it is the eyeball's centre; depth plays no part); (2) `pivot.place_pivot` - Shift = the vertex / edge under the
  cursor (the Knife's pick), else the middle of the mesh under the cursor (the Working Pivot's "inside" rule), else
  the plane facing the camera through the pending head - and with symmetry on a point within `PIVOT_PLANE_SNAP_PX` of
  the plane lands exactly on it (V-3), so a chain down the middle is symmetric to the last bit.
- **Parent:** the first bone's parent is the current bone (branching: select the skull, then start - jaw and eyes hang
  off it), or none (`root`); a first click that snaps onto an existing bone's *tail* makes that bone the parent and
  starts exactly at its tail. Every further bone's parent is the previous one.
- **Undo: one step per bone** (`RigCommand`, as `BONE_ADD`). Reason: each click shows its bone at once, so Ctrl+Z takes
  back what the last click made, one step each way (Maya's joint tool); one step per chain would let one Undo remove
  a spine. After an Undo / Redo the pending head follows the history (`resync`): the bone taken back leaves its head
  as the pending point, a Redo continues from the bone's tail. A pending head with no bone yet is no history entry, so
  Undo drops it first (`drop_head`) instead of taking back an earlier step.
- **Refused to start:** while an interaction runs, while the rig is posed (a bone is placed at rest while the
  display shows the pose; the click would aim on the pose: AD-028 §7.1), in a morph target's editing view, without a viewport.
"""

from __future__ import annotations

import math
from typing import Optional

from core import Bone, BoneId

from .. import object_space
from ..interaction import commands
from ..interaction.pointer import CLICK_THRESHOLD_PX
from ..interaction.session import (
    PASS,
    SILENT,
    Drag,
    Hover,
    Leave,
    Modifiers,
    Outcome,
    Press,
    Refusal,
    Release,
    RunContext,
)
from ..pivot import PIVOT_PLANE_SNAP_PX, nearest_screen_point, place_pivot, snap_candidates, snap_to_plane
from ..viewport import gizmo as _gizmo

#: What the chain lets through from outside (it owns the pointer, not the camera): Cancel (ends it), Undo / Redo (the
#: bones are history steps), navigation and view state. Everything else is refused silently.
CHAIN_ALLOWS = frozenset(
    {
        commands.CANCEL,
        commands.UNDO,
        commands.REDO,
        commands.ORBIT,
        commands.PAN,
        commands.ZOOM,
        commands.TOGGLE_ORTHO,
        commands.WEIGHT_VIEW_TOGGLE,
        *commands.DISPLAY_COMMANDS,
        *commands.LOOK_COMMANDS,
        *commands.WINDOW_COMMANDS,
    }
)

#: Preview look (`PROVISIONAL`): the pending bone's band and the marker where the next click lands.
COLOR_PENDING = (0.95, 0.85, 0.3, 0.7)
COLOR_MARK = (1.0, 0.95, 0.6, 1.0)
COLOR_MARK_PIVOT = (0.3, 0.9, 1.0, 1.0)
COLOR_MARK_BONE = (0.45, 1.0, 0.5, 1.0)
COLOR_MARK_PLANE = (1.0, 0.45, 0.85, 1.0)
PENDING_LINE_WIDTH = 2.5
MARK_RATIO = 0.18  # a marker's arm, in gizmo sizes

#: What a point was taken from: its colour and its words for the status line.
KIND_COLORS = {
    "point": COLOR_MARK,
    "plane": COLOR_MARK_PLANE,
    "pivot": COLOR_MARK_PIVOT,
    "tail": COLOR_MARK_BONE,
    "head": COLOR_MARK_BONE,
}


class ChainPoint:
    """Where a click would land: `world` position, `kind` ("point" | "plane" | "pivot" | "tail" | "head"), the `bone` of
    a "tail" / "head" snap and a `note` for the status line (None for a plain point)."""

    __slots__ = ("world", "kind", "bone", "note")

    def __init__(self, world, kind: str, bone: Optional[BoneId] = None, note: Optional[str] = None) -> None:
        self.world = tuple(float(c) for c in world)
        self.kind = kind
        self.bone = bone
        self.note = note

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, ChainPoint)
            and (self.world, self.kind, self.bone, self.note) == (other.world, other.kind, other.bone, other.note)
        )


class BoneChainSession:
    """A running chain. `parent` = the pending bone's parent, `anchor` = its head (world; None = no head yet), `trail` =
    the bones this chain made, in order (`Bone` values: `resync` compares them with the rig after an Undo / Redo),
    `preview` = the point under the cursor, `gesture` / `moved` / `gesture_shift` = the held LMB press (click rule)."""

    owner = "bonechain"
    label = "Bone chain"
    exclusive = False

    def __init__(self, skeleton, parent: Optional[BoneId]) -> None:
        self.skeleton = skeleton
        self.services = skeleton.services
        self.start_parent = parent
        self.parent = parent
        self.anchor = None
        self.trail: list[Bone] = []
        self.preview: Optional[ChainPoint] = None
        self.gesture = False
        self.moved = 0.0
        self.gesture_shift = False
        self._noted: Optional[str] = None  # the snap note the status line shows now

    # -- the slot protocol ---------------------------------------------------------------------------

    def grabs(self, event) -> bool:
        if isinstance(event, Press):
            input = event.input
            return input.kind == "mouse" and input.value == "LEFT" and not self.gesture and input.modifiers <= {"shift"}
        if isinstance(event, Drag):
            return event.command is None and self.gesture
        if isinstance(event, Release):
            return event.raw and self.gesture and event.button == "LEFT"
        return isinstance(event, (Hover, Leave, Modifiers))

    def allows(self, command: str, ctx: RunContext) -> Optional[Refusal]:
        return None if command in CHAIN_ALLOWS else SILENT

    def handle(self, event) -> Outcome:
        if not self.grabs(event):
            return PASS
        services = self.services
        if isinstance(event, Press):
            self.gesture = True
            self.moved = 0.0
            self.gesture_shift = "shift" in event.input.modifiers
            return True
        if isinstance(event, Drag):
            self.moved += abs(event.dx) + abs(event.dy)
            return False
        if isinstance(event, Release):
            moved, shift = self.moved, self.gesture_shift
            self.gesture = False
            self.moved = 0.0
            if moved >= CLICK_THRESHOLD_PX:
                services.refresh_hover()
                return False
            return self.click(event.x, event.y, shift)
        if isinstance(event, Hover):
            return False if self.gesture else self.hover(event.x, event.y)
        if isinstance(event, Modifiers):
            cursor = services.cursor
            return False if self.gesture or cursor is None else self.hover(*cursor)
        return False if self.gesture else self.clear_preview()  # Leave

    def cancel(self) -> bool:
        """Esc: the chain ends. The bones it made stay - each was one Undo step - and only the pending head is dropped."""
        return self.end()

    def commit(self) -> bool:
        return self.end()

    # -- where a click lands -------------------------------------------------------------------------

    def point_at(self, x: float, y: float, mesh_snap: bool = False) -> Optional[ChainPoint]:
        """The point a click at (x, y) would place (module docstring); None = nothing under the cursor."""
        services = self.services
        width, height = (int(v) for v in services.viewport_size)
        if self.skeleton.chain_snap:
            hit = nearest_screen_point(
                services.camera, snap_candidates(services.scene, self.anchor), x, y, width, height
            )
            if hit is not None:
                (kind, ident, name), point = hit
                if kind == "pivot":
                    return ChainPoint(point, "pivot", note=f"pivot of {name!r}")
                return ChainPoint(point, kind, bone=ident, note=f"{kind} of bone {name!r}")
        edit = services.scene.edit_object
        mesh = services.scene.mesh
        camera = services.edit_camera
        anchor = None if self.anchor is None else object_space.to_object(edit, self.anchor)
        point = place_pivot(
            camera, mesh, x, y, width, height,
            snap=mesh_snap, anchor=anchor, cache=services.pick_cache, occlusion=services.display.show_faces,
        )
        if point is None:
            return None
        definition = mesh.symmetry_definition
        kind = "point"
        note = None
        if definition is not None:
            point, on_plane = snap_to_plane(
                camera, point, definition.plane_point, definition.plane_normal, width, height, PIVOT_PLANE_SNAP_PX,
            )
            if on_plane:
                kind, note = "plane", "on the symmetry plane"
        return ChainPoint(object_space.to_world(edit, point), kind, note=note)

    # -- clicks --------------------------------------------------------------------------------------

    def click(self, x: float, y: float, shift: bool) -> bool:
        """A click: the head if there is none yet, else a tail - one bone, one History step, and the next bone's head."""
        services = self.services
        skeleton = self.skeleton
        target = self.point_at(x, y, mesh_snap=shift)
        if target is None:
            services.status("Bone chain: no point under the cursor")
            services.refresh_hover()
            return False
        if self.anchor is None:
            if target.kind == "tail":
                self.parent = target.bone  # a chain that starts on a bone's tail continues that bone
            self.anchor = target.world
            parent = self.parent
            under = f", child of {skeleton.bone_name(parent)!r}" if parent is not None else ", no parent"
            services.status(f"Bone chain: head set{under} - click the tail (Esc = end)")
            self.preview = None
            services.refresh_hover()
            return True
        if math.dist(self.anchor, target.world) <= max(1e-9, 1e-9 * max(abs(c) for c in self.anchor)):
            services.status("Bone chain: that is the head - a bone needs a length")
            services.refresh_hover()
            return False
        done = skeleton.add_chain_bone(self.anchor, target.world, self.parent)
        if done is None:
            services.refresh_hover()
            return False
        bone = done
        self.trail = self.trail[: self._alive()] + [bone]
        self.anchor = bone.tail
        self.parent = bone.id
        self.preview = None
        n = len(self.trail)
        services.status(
            f"Bone chain: {bone.name!r} placed ({n} in this chain, Ctrl+Z takes it back) - click the next tail, Esc = end"
        )
        services.refresh_hover()
        return True

    # -- history -------------------------------------------------------------------------------------

    def _alive(self) -> int:
        """How many of the chain's first bones the rig still holds exactly as the chain made them."""
        rig = self.skeleton.rig
        alive = 0
        for bone in self.trail:
            if rig is not None and rig.has_bone(bone.id) and rig.bone(bone.id) == bone:
                alive += 1
            else:
                break
        return alive

    def resync(self) -> None:
        """After an Undo / Redo: the pending head follows the history (module docstring). A bone the chain made that is
        gone leaves its head (and its parent) as the pending point; all of them present, the chain continues from the
        last tail."""
        trail = self.trail
        if not trail:
            return
        alive = self._alive()
        if alive == len(trail):
            self.anchor, self.parent = trail[-1].tail, trail[-1].id
        else:
            gone = trail[alive]
            self.anchor, self.parent = gone.head, gone.parent
        self.preview = None

    @property
    def head_only(self) -> bool:
        """A head is set and no bone of this chain is in the rig: Undo drops the head (no history entry for it)."""
        return self.anchor is not None and self._alive() == 0

    def drop_head(self) -> bool:
        """Undo with only a head pending: forget the head (and the chain's dead trail), keep the parent choice."""
        if not self.head_only:
            return False
        self.anchor = None
        self.trail = []
        self.parent = self.start_parent
        self.preview = None
        self.services.status("Bone chain: head dropped - click a new head")
        return True

    # -- the preview ---------------------------------------------------------------------------------

    def hover(self, x: float, y: float) -> bool:
        return self._set_preview(self.point_at(x, y, mesh_snap=self.services.modifiers[0]))

    def hint(self) -> str:
        if self.anchor is None:
            parent = self.parent
            under = f"child of {self.skeleton.bone_name(parent)!r}" if parent is not None else "no parent"
            return f"Bone chain: click the head ({under}; Shift = vertex / edge, Esc = end)"
        return "Bone chain: click the next tail (Esc = end)"

    def clear_preview(self) -> bool:
        return self._set_preview(None)

    def _set_preview(self, point: Optional[ChainPoint]) -> bool:
        changed = point != self.preview
        self.preview = point
        note = None if point is None or point.note is None else f"Bone chain: next point = {point.note}"
        if note != self._noted:  # once per change of what it snaps to, not on every mouse move
            self._noted = note
            self.services.status(note if note is not None else self.hint())
        return changed

    def items(self, camera, scale: float) -> list:
        """Draw items (world space): the pending head's marker, the pending bone as a band from the head to the point
        under the cursor, and a marker there (coloured by what it snapped to)."""
        items = []
        anchor = self.anchor
        if anchor is not None:
            items += _cross(camera, anchor, scale, COLOR_PENDING)
        point = self.preview
        if point is None:
            return items
        if anchor is not None:
            items.append(_gizmo.DrawItem((*anchor, *point.world), COLOR_PENDING, "lines", PENDING_LINE_WIDTH))
        items += _cross(camera, point.world, scale, KIND_COLORS[point.kind], ratio=MARK_RATIO)
        return items

    # -- the end -------------------------------------------------------------------------------------

    def end(self, quiet: bool = False) -> bool:
        services = self.services
        self.skeleton.finish_chain(self)
        if not quiet:
            n = len(self.trail)
            made = f"{n} bone{'s' if n != 1 else ''} made" if n else "no bone made"
            services.status(f"Bone chain ended ({made}; each is one Undo step)")
            services.refresh_hover()
        return True


def _cross(camera, point, scale: float, color, ratio: float = 0.15) -> list:
    arm = _gizmo.gizmo_size(camera, point, scale) * ratio
    lines = []
    for _, d in _gizmo.WORLD_AXES:
        lines += [point[0] - d[0] * arm, point[1] - d[1] * arm, point[2] - d[2] * arm,
                  point[0] + d[0] * arm, point[1] + d[1] * arm, point[2] + d[2] * arm]
    return [_gizmo.DrawItem(tuple(lines), color, "lines", PENDING_LINE_WIDTH)]
