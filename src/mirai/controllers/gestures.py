"""GestureController (AD-027 §3.4): the hold-key gestures as sessions in the slot (`GestureSession`, one kind per
gesture), their sticky constraint settings and the Soft live radius / flow of a running gesture.

A gesture is armed by its key (W/E/R, T, G, S / Alt+S, I in face mode, Ctrl+B) or by an LMB drag (a gizmo handle,
the `Tweak` drag command: `TWEAK_KEY`); nothing moves before the first motion (AD-016); the release of its key (or
of the LMB) commits at most one History entry, Esc restores the exact prior state. While it runs it is the slot's
session (owner `"transform"`): its `allows` is `can_run` stage 6 (a held gesture refuses the mode, placement and
topology commands, the other hold keys and the drag selections silently).

Behaviour as it was inside `Application` (AD-027 M6 moves it, nothing else). The kinds:

- `TransformGesture` - Move / Rotate / Scale on components through the `ToolManager` (also from the gizmo / Tweak);
- `ExtrudeGesture` - Extrude (hold T) through the `ToolManager`;
- `LoopSlideGesture`, `VertexSlideGesture` - hold G in edge / vertex mode, a journal from the first motion.

The axis / plane constraint, its mode (one-shot / sticky) and the transform space (World / Normal) are sticky
settings of this controller (AD-027 §3.1): a gesture reads them at `begin()`, the gizmo shows them.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Optional

from core import EdgeId, FaceId, ObjectId, Selection, SelectionMode, VertexId
from core.mesh import MeshChange
from core.operations import MeshDeltaCommand
from core.operations.transform import SeamConstraintError

from .. import symmetry_declarations, transform_space
from ..interaction import commands
from ..interaction.dial import PRECISION_GAIN
from ..interaction.session import (
    PASS,
    SILENT,
    Command,
    KeyRelease,
    Modifiers,
    Motion,
    Outcome,
    Refusal,
    RunContext,
)
from ..interaction.tools import resolve_selection_vertices
from ..mask import unblocked
from ..morph_targets import MORPH_COMMANDS
from ..soft_selection import RADIUS_STEPS_PERCENT, SoftSettings, SoftSymmetryRefusal
from ..symmetric_ops import SymmetryRefusal
from ..topology.connect_per_face import TopologyToolError
from ..topology.loop_slide import LOOP_SLIDE_LABEL, LoopSlideRefused, SlidePlan, plan_loop_slide, slide_positions
from ..topology.vertex_slide import (
    VERTEX_SLIDE_LABEL,
    VertexSlidePlan,
    VertexSlideRefused,
    best_neighbour,
    plan_vertex_slide,
    vertex_slide_positions,
)
from .services import AppServices

#: WP-06 B4 (E28): the hold-key gestures. Values: (label, verb, participle) for the status lines (E34, `PROVISIONAL`).
TRANSFORM_COMMANDS: dict[str, tuple[str, str, str]] = {
    commands.MOVE: ("Move", "move", "moved"),
    commands.ROTATE: ("Rotate", "rotate", "rotated"),
    commands.SCALE: ("Scale", "scale", "scaled"),
    commands.EXTRUDE: ("Extrude", "extrude", "extruded"),
    # 2026-10-15 (loop tools promoted): hold G, the same hold-key family as T.
    commands.LOOP_SLIDE: ("Loop Slide", "slide", "slid"),
    # WP Toolbox Gaps C2: hold S / Alt+S, same family (a tap is one step).
    commands.SMOOTH: ("Smooth", "smooth", "smoothed"),
    commands.RELAX: ("Relax", "relax", "relaxed"),
    # 2026-10-29 (Manu: Inset, Bevel, Grundfunktion): hold I in face mode / hold Ctrl+B, the T family.
    commands.INSET: ("Inset", "inset", "inset"),
    commands.BEVEL: ("Bevel", "bevel", "beveled"),
}

#: The width gestures: topology built once when the drag starts, then only the new vertices move.
OFFSET_COMMANDS = (commands.INSET, commands.BEVEL)
#: WP Toolbox Gaps C2: the two hold keys of `mirai.topology.smooth`.
SMOOTH_COMMANDS = (commands.SMOOTH, commands.RELAX)
#: The transforms the gizmo drag (and the hold-key Tweak) can use (`Application.tweak_command`).
TWEAK_TRANSFORMS = (commands.MOVE, commands.ROTATE, commands.SCALE)

#: The pseudo key an LMB-drag transform (a gizmo handle drag; the `Tweak` drag command, unbound since 2026-10-28)
#: arms the gesture with; no key has this value, so a key release never ends it - the LMB release does. Not the
#: user-facing "Tweak", which is the hold-key gesture (Manu A2, 2026-10-28).
TWEAK_KEY = "LMB-tweak"

#: How long an axis / plane constraint lives (2026-10-28, Manu A1 + E1, `PROVISIONAL`; the switch is a session
#: setting for the comparison, `commands.CONSTRAINT_MODE_TOGGLE`, not saved). One-shot: the constraint applies to the
#: next Move / Rotate / Scale gesture (also when pressed while the key is armed) and its commit clears it; Esc keeps
#: it. Sticky: the B4.1 behaviour until 2026-10-28 - it stays until toggled off.
CONSTRAINT_ONE_SHOT = "one-shot"
CONSTRAINT_STICKY = "sticky"
CONSTRAINT_MODES = (CONSTRAINT_ONE_SHOT, CONSTRAINT_STICKY)

#: WP-06 B9 (E3, PROVISIONAL, agent-set): Extrude (and Inset / Bevel) mutate the topology when they begin, so unlike
#: Move/Rotate/Scale (AD-016: first motion begins) the pointer's net displacement since the arm must reach this many
#: logical pixels first; a tap or a hand tremble below it does nothing at all.
EXTRUDE_BEGIN_PX = 4.0
#: WP-06 B9 (E3, PROVISIONAL, agent-set): at release an Extrude whose |total distance| (an Inset / Bevel whose
#: width) is below this (world units) counts as cancelled - exact prior state, no history.
EXTRUDE_MIN_DISTANCE = 1e-6

#: WP-06 B4 (E32): constraint command -> `space` string (AD-012, `transform._resolve_space`).
CONSTRAINT_SPACES: dict[str, str] = {
    commands.CONSTRAIN_AXIS_X: "x",
    commands.CONSTRAIN_AXIS_Y: "y",
    commands.CONSTRAIN_AXIS_Z: "z",
    commands.CONSTRAIN_PLANE_XY: "xy",
    commands.CONSTRAIN_PLANE_XZ: "xz",
    commands.CONSTRAIN_PLANE_YZ: "yz",
}

#: AD-027 §3.3 stage 6: what a held W/E/R/T/G/S/I/Ctrl+B (armed or begun) refuses underneath it, silently (the
#: Playground session gate, AD-SYM-04 R-4, AD-021 M2-3): the mode, placement and topology commands, the other hold
#: keys, the morph keys and the drag selections. A second gesture key is refused by `GestureController.arm`, after
#: `Application` set `tweak_command` (so the HUD tool follows, as before).
GESTURE_REFUSES = frozenset(
    {
        *MORPH_COMMANDS,
        commands.LASSO_ARM,
        commands.PIVOT_PLACE,
        commands.LIGHT_DRAG,
        *commands.MODE_COMMANDS,
        commands.APPLY_TRANSFORM,
        commands.CLEAR_TRANSFORM,
        commands.TOGGLE_REFERENCE,
        commands.CONNECT,
        commands.COLLAPSE,
        commands.BORDER_SELECT,
        commands.CAP,
        commands.SYMMETRY_CYCLE,
        commands.RESYMMETRIZE,
        *commands.MASK_COMMANDS,
        *commands.HIDE_COMMANDS,
        *commands.POLYGROUP_COMMANDS,
        *commands.REMOVAL_COMMANDS,
        *commands.LOOP_COMMANDS,
        *commands.SELECTION_STEP_COMMANDS,
        commands.SELECT_DRAG,
        commands.SELECT_DRAG_ADD,
    }
)
#: ... and once it has begun: Undo/Redo (E23; only armed, the key disarms first) and `K` (its frame is fixed).
BEGUN_GESTURE_REFUSES = frozenset({commands.UNDO, commands.REDO, commands.TOGGLE_TRANSFORM_SPACE})
#: The gestures that ignore the constraint keys: Extrude is normal-only, Loop Slide runs along its edges, Smooth /
#: Relax and Inset / Bevel have no axis - neither the gesture nor the pending constraint changes.
UNCONSTRAINED_GESTURES = frozenset({commands.EXTRUDE, commands.LOOP_SLIDE, *SMOOTH_COMMANDS, *OFFSET_COMMANDS})


def element_vertices(mesh, element) -> set[VertexId]:
    """The vertices of one vertex / edge / face (the hover fallback of a gesture's target). A handle `mesh` no
    longer knows (a topology change since) gives an empty set instead of a `KeyError` - the viewport overlay's rule."""
    if isinstance(element, VertexId):
        return {element} if mesh.is_valid_vertex(element) else set()
    if isinstance(element, EdgeId):
        return set(mesh.edge_vertices(element)) if mesh.is_valid_edge(element) else set()
    if isinstance(element, FaceId):
        return set(mesh.face_vertices(element)) if mesh.is_valid_face(element) else set()
    return set()


def active_selection_contains(selection: Selection, element) -> bool:
    """Is `element` in the selection of the active mode (Playground `_sel_contains_hovered`)? The type is checked
    too - IDs are int subclasses."""
    kind, members = {
        SelectionMode.VERTEX: (VertexId, selection.vertices),
        SelectionMode.EDGE: (EdgeId, selection.edges),
        SelectionMode.FACE: (FaceId, selection.faces),
        SelectionMode.OBJECT: (ObjectId, selection.objects),
    }[selection.mode]
    return isinstance(element, kind) and element in members


def constraint_label(space: str | None) -> str:
    """Status text of a constraint: "X", "YZ plane", "none"."""
    if space is None:
        return "none"
    return space.upper() if len(space) == 1 else f"{space.upper()} plane"


def constraint_suffix(space: str | None) -> str:
    return "" if space is None else f" (constraint {constraint_label(space)})"


def commit_hint(key: str) -> str:
    """The arm line's instruction; the hold-key gesture is named "Tweak" there (Manu A2)."""
    if key == TWEAK_KEY:
        return " - move the mouse, release the mouse button to commit"
    return f" - Tweak: move the mouse, release {key.upper()} to commit"


class GestureSession:
    """A held gesture (armed or begun) in the slot. The common part of every kind: `key` = the key that armed it
    (its release commits; compared by value, because the modifiers may change between press and release, e.g. Alt
    for orbit while W is held), `command`, `target` (the vertices fixed at the arm), `begun` (the first motion
    started it), `space` (the constraint it began with, None = free), `retouched` (a constraint key was pressed
    while it ran: that one is for the next gesture), the dial's press point and virtual cursor (`rotate_press`,
    `rotate_virtual`: the press point plus the summed deltas, so the window may warp the pointer across the
    viewport edge without a jump), `ctrl_snap_ok` (a Tweak that starts with Ctrl down snaps only after Ctrl was let
    go once), the Soft settings of a running Soft gesture (`soft`; `soft_reference` = the bounding radius its
    percent steps refer to, fixed for the gesture) and the display state it owns (`soft_op_running`: the influence
    shown is the op's own; `soft_shown`: the gesture put it there, so its end resumes the preview).

    A kind implements `step`, `release` (its part of the commit), `abort` (its part of Esc) and `cleanup`."""

    owner = "transform"
    exclusive = False
    #: Esc ends this kind with `abort()` and "cancelled" also before it began (Smooth / Relax).
    cancel_unbegun = False

    def __init__(self, controller: "GestureController", command: str, key: str, target, origin) -> None:
        self._controller = controller
        self.services: AppServices = controller.services
        self.command = command
        self.key = key
        self.target: frozenset[VertexId] = frozenset(target)
        self.begun = False
        self.space: str | None = None
        self.retouched = False
        self.rotate_press, self.ctrl_snap_ok = origin
        self.rotate_virtual = self.rotate_press
        self.soft: SoftSettings | None = None
        self.soft_reference = 0.0
        self.soft_op_running = False
        self.soft_shown = False

    @property
    def label(self) -> str:
        return TRANSFORM_COMMANDS[self.command][0]

    # -- the session protocol ------------------------------------------------------------------------

    def grabs(self, event) -> bool:
        return False

    def allows(self, command: str, ctx: RunContext) -> Optional[Refusal]:
        if command in GESTURE_REFUSES:
            return SILENT
        if self.begun and command in BEGUN_GESTURE_REFUSES:
            return SILENT
        if command in CONSTRAINT_SPACES and self.command in UNCONSTRAINED_GESTURES:
            return SILENT
        return None

    def handle(self, event) -> Outcome:
        if isinstance(event, Motion):
            return self.motion(event.dx, event.dy)
        if isinstance(event, KeyRelease):
            if event.input.value != self.key:
                return PASS
            self.commit()
            return True
        if isinstance(event, Modifiers):
            return self.ctrl_changed(event.ctrl)
        if isinstance(event, Command) and event.command == commands.CANCEL:
            return self.cancel()
        return PASS

    def commit(self) -> bool:
        """End the gesture: commit after motion, else just disarm. The release of its key or, for an LMB-drag
        gesture, of the LMB. A one-shot constraint is cleared by the commit of the Move / Rotate / Scale gesture
        that used it."""
        services = self.services
        consumed = self.begun and self.command in TWEAK_TRANSFORMS
        self.release()
        if consumed and self._controller.consume_constraint(self):
            services.status(f"{services.status_message} · free again (one-shot)")
        self.end()
        services.refresh_hover()
        return True

    def cancel(self) -> bool:
        """Esc: begun -> the exact prior state without History; only armed -> disarmed."""
        services = self.services
        label = self.label
        if self.begun or self.cancel_unbegun:
            self.abort()
            services.status(f"{label} cancelled")
        else:
            services.status(f"{label} disarmed")
        self.end()
        services.refresh_hover()
        return True

    # -- the common lifecycle ------------------------------------------------------------------------

    def motion(self, dx: float, dy: float, force: bool = False) -> bool:
        """A pointer motion while the gesture is held. The first one begins it (no threshold for Move / Rotate /
        Scale, AD-016); a zero step does not count as motion. Shift = precision (Rotate scales its own angle)."""
        if dx == 0 and dy == 0 and not force:
            return False
        if self.rotate_virtual is not None:
            self.rotate_virtual = (self.rotate_virtual[0] + dx, self.rotate_virtual[1] + dy)
        if not force and self.services.modifiers[0] and self.command in (commands.MOVE, commands.SCALE, *OFFSET_COMMANDS):
            dx, dy = dx * PRECISION_GAIN, dy * PRECISION_GAIN
        return self.step(dx, dy)

    def ctrl_changed(self, held: bool) -> bool:
        """Ctrl = snap in a running Rotate; it shows at once. True = the gesture changed."""
        if not held:
            self.ctrl_snap_ok = True
        if not self.begun or self.command != commands.ROTATE or self.rotate_virtual is None:
            return False
        return self.motion(0.0, 0.0, force=True)

    def snap_held(self) -> bool:
        return self.services.modifiers[1] and self.ctrl_snap_ok

    def end(self) -> None:
        """The gesture leaves the slot: tool deactivated, journals released; the Soft preview resumes when the
        gesture had put its bands there."""
        resume_preview = self.soft_shown
        self.soft_op_running = False
        self.soft_shown = False
        self.soft = None
        self._controller.tool_manager.deactivate()
        self.services.interaction.end(self)
        self.cleanup()
        if resume_preview:
            self.services.soft_preview_refresh()

    def refused(self, text: str) -> bool:
        """A refusal while it begins (seam, symmetric Soft, ...): the gesture ends visibly, nothing changed."""
        self.end()
        self.services.status(text)
        self.services.refresh_hover()
        return False

    # -- what a kind implements ----------------------------------------------------------------------

    def step(self, dx: float, dy: float) -> bool:
        raise NotImplementedError

    def release(self) -> None:
        raise NotImplementedError

    def abort(self) -> None:
        raise NotImplementedError

    def cleanup(self) -> None:
        """A gesture that ended without release / abort stops its recording here (the mesh stays)."""

    # -- Soft live radius / flow (AD-020) ------------------------------------------------------------

    def live_tool(self):
        """The tool of a begun Soft Move / Rotate / Scale, else None."""
        return None

    def soft_live(self) -> bool:
        """The running gesture takes Soft radius / flow steps live."""
        return False

    def reweight(self, settings: SoftSettings) -> None:
        """Continue with `settings`' influence (only while `soft_live`)."""
        raise NotImplementedError

    def show_weights(self, weights) -> None:
        """The display shows the gesture's own weights (`weights` None = nothing): the gesture's display settings,
        also while hidden - the gesture owns the display, it just has nothing to show (S2d E7)."""
        display = self.soft or self.services.soft_settings
        if self.services.show_soft_weights(weights if display.bands_visible else None, display.view_mode):
            self.soft_op_running = True
            self.soft_shown = True


class TransformGesture(GestureSession):
    """Move / Rotate / Scale on components (W/E/R held, a gizmo handle drag, the `Tweak` drag): the `ToolManager`'s
    tool, `begin()` at the first motion."""

    def step(self, dx: float, dy: float) -> bool:
        services = self.services
        tool_manager = self._controller.tool_manager
        if not self.begun and not self._begin():
            return False
        width, height = services.viewport_size
        update = {"dx": float(dx), "dy": float(dy), "width": width, "height": height}
        if self.command == commands.ROTATE:
            update["precise"], update["snap"] = services.modifiers[0], self.snap_held()
            if self.rotate_mode() == "dial":
                update["x"], update["y"] = self.rotate_virtual
        tool_manager.update(**update)
        services.invalidate_picks()
        services.notify_vertices_moved(self.moved_vertex_ids())
        return True

    def _begin(self) -> bool:
        """`begin()` with the sticky settings read now (constraint, Soft, mask, Working Pivot, space, dial). WP-SYM-LAB-03
        H5: a start the tool refuses under symmetry (`SeamConstraintError`, INV-8: a seam vertex would leave the
        plane) or symmetric Soft refuses (AD-SYM-04 SS2: D-2, the open O-1 cases) ends the gesture visibly, without
        History and with the mesh unchanged (the tool aborts exactly by itself)."""
        controller = self._controller
        services = self.services
        self.space = controller.axis_constraint
        soft_settings = services.soft_settings
        soft = soft_settings if soft_settings.enabled else None
        begin_context = {
            "scene": services.scene,
            "camera": services.edit_camera,
            "vertex_ids": set(self.target),
            "space": self.space,
        }
        if soft is not None:
            begin_context["soft"] = soft  # absent when off: today's payload, unchanged
        mask = services.mask_values(self.target)
        if mask:
            begin_context["mask"] = mask  # absent without a mask: today's payload, unchanged
        pivot = services.active_pivot if self.command in (commands.ROTATE, commands.SCALE) else None
        if pivot is not None:
            begin_context["pivot"] = pivot  # Working Pivot (U-1); Move and pivot off: today's payload
        if controller.orientation == transform_space.NORMAL and self.space is not None:
            refusal, normal_context = self._normal_space_context()
            if refusal is not None:
                return self.refused(f"{self.label}: refused — {refusal}")
            begin_context.update(normal_context)
        rotate_gizmo = self.rotate_mode()
        if rotate_gizmo is not None:
            width, height = services.viewport_size
            begin_context["gizmo"] = {"mode": rotate_gizmo, "press": self.rotate_press, "size": (int(width), int(height))}
        try:
            controller.tool_manager.begin_current_interaction(begin_context)
        except (SeamConstraintError, SoftSymmetryRefusal) as exc:
            hint = ""
            if pivot is not None and isinstance(exc, SeamConstraintError):
                hint = " (the Working Pivot is off the symmetry plane: place it on the plane or tap P to turn it off)"
            # Status text PROVISIONAL, like the other transform status lines.
            return self.refused(f"{self.label}: refused — {exc}{hint}")
        self.begun = True
        if soft is not None:
            self.soft = soft
            self.soft_reference = soft.world_radius * 100.0 / soft.radius_percent
            self.show_op_weights()
        return True

    def _normal_space_context(self) -> tuple[str | None, dict]:
        """(refusal, begin parameters) of a constrained gesture in Normal space: `space="normal"` with the
        constraint as `axis`, and the selection's current normals as `derived_geometry` (the tools' frame is the
        gizmo's frame, `transform_space`)."""
        services = self.services
        normals = transform_space.SelectionNormals(services.scene.mesh, services.selection)
        frame = transform_space.normal_frame(services.scene.mesh, services.selection, normals)
        refusal = transform_space.normal_refusal(frame, self.space, scale=self.command == commands.SCALE)
        return refusal, {"space": transform_space.NORMAL, "axis": self.space, "derived_geometry": normals}

    def rotate_mode(self) -> str | None:
        """How the running Rotate follows the pointer: `trackball` (gizmo centre), `dial` (every other cursor
        gesture: gizmo ring, R/E key, Tweak), None without a command or a cursor (dx fallback)."""
        if self.command != commands.ROTATE or self.rotate_press is None:
            return None
        gizmo = self.services.gizmo_press
        return "trackball" if gizmo is not None and gizmo.handle_id == "center" else "dial"

    def moved_vertex_ids(self) -> set[VertexId]:
        """The vertices the running tool moves (E29): `MoveTool.moves` (with the symmetry partners) or
        `TransformTool.vertex_ids` - deliberately not unified, MoveTool does not inherit from TransformTool."""
        tool = self._controller.tool_manager.active_tool
        moves = getattr(tool, "moves", None)
        return moves if moves is not None else tool.vertex_ids

    def release(self) -> None:
        services = self.services
        label, _, participle = TRANSFORM_COMMANDS[self.command]
        if not self.begun:
            services.status(f"{label}: tool set (no motion, nothing {participle})")
            return
        before = services.selection_snapshot()
        command = self._controller.tool_manager.commit()
        if command is not None:
            # Move/Rotate/Scale never change the selection itself, only vertex positions: before and after are the
            # same snapshot.
            services.record_selection_history(before)
        outcome = f"{label} committed" if command is not None else f"{label}: no change"
        services.status(outcome + constraint_suffix(self.space))

    def abort(self) -> None:
        services = self.services
        moved = self.moved_vertex_ids()
        self._controller.tool_manager.cancel()
        services.invalidate_picks()
        services.notify_vertices_moved(moved)

    def live_tool(self):
        if self.soft is None or not self.begun:
            return None
        tool = self._controller.tool_manager.active_tool
        return tool if getattr(tool, "is_soft_gesture", False) else None

    def soft_live(self) -> bool:
        return self.live_tool() is not None

    def reweight(self, settings: SoftSettings) -> None:
        """Cancel, begin again on the start geometry with the same seeds / pivot and the new influence, replay
        the intent (`reweight`); the display shows the new weights."""
        services = self.services
        self.soft = settings
        touched = self.live_tool().reweight(settings)
        services.invalidate_picks()
        services.notify_vertices_moved(touched)
        self.show_op_weights()

    def show_op_weights(self) -> None:
        """At `begin()` (and after a live step): the display becomes the op's own weights (E4), so the preview and
        the gesture cannot disagree; nothing is computed. Under symmetry the op's weights are the symmetric field,
        both sides (AD-SYM-04 D-5)."""
        tool = self._controller.tool_manager.active_tool
        display = self.soft or self.services.soft_settings
        self.show_weights(tool.operation.context.params["influence"] if display.bands_visible else None)


class ExtrudeGesture(GestureSession):
    """Extrude (WP-06 B9, hold T; `PROVISIONAL` baseline, key T = Artist Input Truth `topology.extrude` "for now",
    Manu 2026-10-09; the hold-key-hover activation and the hover fallback are engineering proposals). The W/E/R
    lifecycle with these differences: face mode only, the target is faces (`faces`), `begin()` mutates the topology
    (hence EXTRUDE_BEGIN_PX: `travel` = the net displacement since the arm), the viewport is told about a topology
    change, a zero extrusion is cancelled, and the selection-history `before` is the snapshot taken ahead of `begin()`
    (the tool remaps the selection to the caps during `begin()`)."""

    def __init__(self, controller: "GestureController", key: str, faces, origin) -> None:
        mesh = controller.services.scene.mesh
        target = (vid for f in faces for vid in element_vertices(mesh, f))
        super().__init__(controller, commands.EXTRUDE, key, target, origin)
        self.faces: frozenset[FaceId] = frozenset(faces)
        self.travel: tuple[float, float] = (0.0, 0.0)
        self.selection_before: tuple | None = None

    def step(self, dx: float, dy: float) -> bool:
        """Net displacement since the arm until EXTRUDE_BEGIN_PX, then `begin()`; the first update gets all of it,
        so the distance follows the pointer from where T went down."""
        services = self.services
        tool_manager = self._controller.tool_manager
        if not self.begun:
            px, py = self.travel[0] + dx, self.travel[1] + dy
            self.travel = (px, py)
            if math.hypot(px, py) < EXTRUDE_BEGIN_PX:
                return False
            if not self._begin():
                return False
            dx, dy = px, py
        width, height = services.viewport_size
        tool_manager.update(dx=float(dx), dy=float(dy), width=width, height=height)
        services.invalidate_picks()
        tool = tool_manager.active_tool
        moves = getattr(tool, "moves", None)
        services.notify_vertices_moved(moves if moves is not None else tool.vertex_ids)
        return True

    def _begin(self) -> bool:
        """Start the Extrude (topology changes here). False = refused, the gesture ended.

        AD-SYM-03 slice 7: whenever a symmetry definition is set the declared planner
        (`symmetry_declarations.EXTRUDE_COORDINATORS`, D-b - the declaration is the only switch) runs first, in MARK
        as in BLOCK (H2 amendment, "Runtime refusals are not G-3"): it refuses before any mutation (`SymmetryRefusal`:
        status text, mesh / history / selection untouched) or returns the plan - selection plus mirror partners as
        one intent - that the unchanged tool is handed. Without a definition the tool runs exactly as in B9."""
        services = self.services
        self.selection_before = services.selection_snapshot()
        faces = set(self.faces)
        mesh = services.scene.mesh
        context = {"scene": services.scene, "camera": services.edit_camera}
        planner = (
            symmetry_declarations.EXTRUDE_COORDINATORS.get(commands.EXTRUDE)
            if mesh.symmetry_definition is not None
            else None
        )
        if planner is not None:
            try:
                plan = planner(mesh, faces)
            except SymmetryRefusal as exc:
                return self.refused(str(exc))
            faces = set(plan.face_ids)
            context["symmetric_plan"] = plan
        context["face_ids"] = faces
        try:
            self._controller.tool_manager.begin_current_interaction(context)
        except TopologyToolError as exc:
            return self.refused(f"Extrude: refused — {exc}")
        self.begun = True
        self._controller.topology_changed()
        return True

    def release(self) -> None:
        """Commit, or - tap, jitter below EXTRUDE_BEGIN_PX, or a total distance below EXTRUDE_MIN_DISTANCE - leave
        everything exactly as it was."""
        services = self.services
        tool_manager = self._controller.tool_manager
        if not self.begun:
            services.status("Extrude: no change")
            return
        if abs(tool_manager.active_tool.total_distance) < EXTRUDE_MIN_DISTANCE:
            self.abort()
            services.status("Extrude: no change")
            return
        tool = tool_manager.active_tool
        tool_manager.commit()
        if tool.refusal is not None:
            # A symmetric commit the coordinator refused (delta): the tool has taken everything back, no history
            # entry. Same exact prior state as an abort, with the refusal as the visible status.
            services.restore_selection(self.selection_before)
            self._controller.topology_changed()
            services.status(tool.refusal)
            return
        services.record_selection_history(self.selection_before)
        self._controller.topology_changed()
        services.status("Extrude committed")

    def abort(self) -> None:
        """A begun Extrude: exact prior mesh (tool), exact prior selection, no history."""
        self._controller.tool_manager.cancel()
        self.services.restore_selection(self.selection_before)
        self._controller.topology_changed()


class _SlideGesture(GestureSession):
    """Hold G (2026-10-15, loop tools promoted): the plan is fixed at the arm, nothing moves before the first motion;
    from it the mesh records into a journal (`before`, with the selection snapshot `selection_before`): the release
    commits it as one entry, Esc rolls it back."""

    def __init__(self, controller: "GestureController", key: str, plan, origin) -> None:
        super().__init__(controller, commands.LOOP_SLIDE, key, plan.vertex_ids, origin)
        self.plan = plan
        self.before: MeshChange | None = None
        self.selection_before: tuple | None = None

    def _record(self) -> None:
        if not self.begun:
            self.before = self.services.scene.mesh.begin_change()
            self.selection_before = self.services.selection_snapshot()
            self.begun = True

    def _write(self, positions: dict) -> None:
        mesh = self.services.scene.mesh
        for vid, position in positions.items():
            mesh.set_vertex_position(vid, position)
        self.services.invalidate_picks()
        self.services.notify_vertices_moved(set(positions))

    def release(self) -> None:
        services = self.services
        mesh = services.scene.mesh
        before = self.before
        label = self.label
        if not self.begun or before is None:
            services.status(f"{label}: no change")
            return
        self.before = None
        delta = mesh.end_change(before)
        if delta.empty:
            services.status(f"{label}: no change")
            return
        services.history.push(MeshDeltaCommand(mesh=mesh, delta=delta, description=label))
        services.record_selection_history(self.selection_before)
        services.soft_preview_refresh()
        services.status(f"{label} committed")

    def abort(self) -> None:
        before = self.before
        if before is None:
            return
        self.before = None
        self.services.scene.mesh.rollback_change(before)
        self.services.invalidate_picks()
        self.services.notify_vertices_moved(set(self.plan.vertex_ids))

    def cleanup(self) -> None:
        if self.before is not None:
            self.services.scene.mesh.release_change(self.before)
            self.before = None


class LoopSlideGesture(_SlideGesture):
    """Loop Slide (G in edge mode): the selected (else the hovered) edges slide along their side edges; `t` = the
    slide amount, `direction` = the screen direction of side A (px per unit t; None = fall back to horizontal)."""

    @property
    def label(self) -> str:
        return LOOP_SLIDE_LABEL

    def __init__(self, controller: "GestureController", key: str, plan: SlidePlan, origin) -> None:
        super().__init__(controller, key, plan, origin)
        self.t = 0.0
        self.direction = self._screen_direction()

    def _screen_direction(self) -> tuple[float, float] | None:
        """Mean screen vector from each driven vertex to its side-A target (px for t = 1)."""
        camera = self.services.edit_camera
        width, height = self.services.viewport_size
        sx = sy = 0.0
        n = 0
        for orig, side_a, _ in self.plan.slides.values():
            a = camera.project_to_screen(orig, width, height)
            b = camera.project_to_screen(side_a, width, height)
            if a is None or b is None:
                continue
            sx += b[0] - a[0]
            sy += b[1] - a[1]
            n += 1
        if n == 0 or math.hypot(sx / n, sy / n) < 1.0:
            return None
        return (sx / n, sy / n)

    def step(self, dx: float, dy: float) -> bool:
        plan = self.plan
        self._record()
        direction = self.direction
        if direction is None:
            # Edges seen end-on: the Playground's mapping (horizontal motion).
            self.t += dx / self.services.viewport_size[0] * 2.0
        else:
            self.t += (dx * direction[0] + dy * direction[1]) / (direction[0] ** 2 + direction[1] ** 2)
        self.t = max(-plan.max_t, min(plan.max_t, self.t))
        self._write(slide_positions(plan, self.t))
        return True


class VertexSlideGesture(_SlideGesture):
    """Vertex Slide (G in vertex mode, 2026-10-29): which edge each vertex takes is decided by the drag. `px` = the
    screen positions of each driven vertex and its candidate neighbours at the press, `drag` = the net drag since
    the press."""

    @property
    def label(self) -> str:
        return VERTEX_SLIDE_LABEL

    def __init__(self, controller: "GestureController", key: str, plan: VertexSlidePlan, px: dict, origin) -> None:
        super().__init__(controller, key, plan, origin)
        self.px = px
        self.drag: tuple[float, float] = (0.0, 0.0)

    def step(self, dx: float, dy: float) -> bool:
        """Every motion: each driven vertex takes the edge whose screen direction best matches the net drag since
        the press; the drag along the mean of those directions is the common amount (0 = start, 1 = on the
        neighbour). Recomputed from the press state, so dragging back restores it."""
        plan = self.plan
        self._record()
        drag = (self.drag[0] + dx, self.drag[1] + dy)
        self.drag = drag
        chosen: dict[VertexId, VertexId] = {}
        sx = sy = 0.0
        for vid in plan.origins:
            origin_px, candidates_px = self.px[vid]
            i = best_neighbour(origin_px, candidates_px, drag)
            if i is None:
                continue
            chosen[vid] = plan.candidates[vid][i][0]
            sx += candidates_px[i][0] - origin_px[0]
            sy += candidates_px[i][1] - origin_px[1]
        t = 0.0
        if chosen:
            sx, sy = sx / len(chosen), sy / len(chosen)
            length2 = sx * sx + sy * sy
            if length2 >= 1.0:
                t = max(0.0, min(plan.max_amount, (drag[0] * sx + drag[1] * sy) / length2))
                if t < 1e-9:
                    t = 0.0  # back at the press point (float sums of the motion): exactly the start
        self._write(vertex_slide_positions(plan, chosen, t))
        self.services.status(f"{VERTEX_SLIDE_LABEL}: {t * 100.0:.0f} %")
        return True


class GestureController:
    """Arms the gestures, owns the constraint settings (`axis_constraint`: None = free; `constraint_mode`;
    `orientation`: World / Normal, WP Toolbox Gaps C1) and the Soft live steps of the running gesture."""

    def __init__(self, services: AppServices, tool_manager) -> None:
        self.services = services
        self.tool_manager = tool_manager
        # WP-06 B4.1 (Manu 2026-09-27, Playground WP-AP-INPUT-FIX-03 1:1): independent of the armed tool, survives
        # Cancel / a new arm and is read at every `begin()`. 2026-10-28 (Manu A1): one-shot by default - the commit
        # of the gesture that used it clears it; `sticky` keeps the B4.1 behaviour (session only).
        self.axis_constraint: str | None = None
        self.constraint_mode: str = CONSTRAINT_ONE_SHOT
        # WP Toolbox Gaps C1 (`PROVISIONAL`): what the constraints mean - world axes or the selection's normal frame
        # (`mirai.transform_space`). Sticky (never one-shot), read at `begin()` and by the gizmo; not saved.
        self.orientation: str = transform_space.WORLD

    @property
    def session(self) -> GestureSession | None:
        session = self.services.interaction.session
        return session if isinstance(session, GestureSession) else None

    # -- arming --------------------------------------------------------------------------------------

    def origin(self, key: str) -> tuple:
        """(dial press point, `ctrl_snap_ok`) of a gesture armed now: the cursor; for an LMB-drag gesture the
        handle's press point, else the press point of the LMB gesture (a Tweak that starts with Ctrl down snaps
        only after Ctrl was let go once)."""
        services = self.services
        gizmo = services.gizmo_press
        if key == TWEAK_KEY:
            press = (None if gizmo is None else gizmo.press_xy) or services.press_point or services.cursor
        else:
            press = services.cursor
        press = None if press is None else (float(press[0]), float(press[1]))
        return press, not (services.modifiers[1] and key == TWEAK_KEY and gizmo is None)

    def arm_transform(self, command: str, key: str, origin) -> bool:
        """Move / Rotate / Scale (E21/E28): target = the resolved selection, else the vertices of the hovered
        element (vertex / edge / face, B5b), else refused. The tool is active, `begin()` waits for the motion."""
        services = self.services
        label, verb, _ = TRANSFORM_COMMANDS[command]
        selection = services.selection
        mesh = services.scene.mesh
        target = resolve_selection_vertices(mesh, selection, selection.mode)
        hovered = selection.hovered
        from_hover = not target and hovered is not None
        if from_hover:
            target = element_vertices(mesh, hovered)
        if not target:
            noun = selection.mode.name.lower()
            services.status(f"{label}: nothing to {verb} (select or hover a {noun})")
            return False
        if not unblocked(target, services.mask_values(target)):
            services.status(f"{label}: all selected points are masked (Ctrl+M unmasks)")
            return False
        services.flush_hover()  # (the ungated command path this activation took picked a stale hover first)
        self.tool_manager.activate(command)
        session = TransformGesture(self, command, key, target, origin)
        services.interaction.start(session)
        # No hover highlight on what is about to move (Playground WP-STAB-11 clear-on-arm).
        if from_hover or active_selection_contains(selection, hovered):
            services.set_hovered(None)
        if from_hover and services.soft_preview_refresh():
            session.soft_shown = True  # F11: a hover-armed gesture shows its bands once, here (no preview from hover)
        count = len(session.target)
        noun = "vertex" if count == 1 else "vertices"
        around = " around the Working Pivot" if command != commands.MOVE and services.active_pivot is not None else ""
        services.status(f"{label}: {count} {noun}{around}{constraint_suffix(self.axis_constraint)}{commit_hint(key)}")
        return True

    def arm_extrude(self, key: str, origin) -> bool:
        """Extrude: face mode with >= 1 selected face, else the hovered face, else refused with a status line. The
        tool is active, `begin()` waits for the pointer."""
        services = self.services
        selection = services.selection
        mesh = services.scene.mesh
        if selection.mode is not SelectionMode.FACE:
            services.status("Extrude: face mode needed")
            return False
        faces = {f for f in selection.faces if mesh.is_valid_face(f)}
        hovered = selection.hovered
        from_hover = not faces and isinstance(hovered, FaceId) and mesh.is_valid_face(hovered)
        if from_hover:
            faces = {hovered}
        if not faces:
            services.status("Extrude: select or hover a face")
            return False
        services.flush_hover()  # (as `arm_transform`)
        self.tool_manager.activate(commands.EXTRUDE)
        services.interaction.start(ExtrudeGesture(self, key, faces, origin))
        # Same clear-on-arm as the transforms: no hover highlight on what is extruded.
        if from_hover or active_selection_contains(selection, hovered):
            services.set_hovered(None)
        count = len(faces)
        services.status(f"Extrude: {count} {'face' if count == 1 else 'faces'} - move the mouse, release {key.upper()} to commit")
        return True

    def arm_slide(self, key: str, origin) -> bool:
        """Hold G: plan the slide of the selected (else the hovered) edges now; refusals are posted at the press,
        before anything moves. In vertex mode G is Vertex Slide."""
        services = self.services
        if services.selection.mode is SelectionMode.VERTEX:
            return self._arm_vertex_slide(key, origin)
        edges = services.loop_seed_edges(LOOP_SLIDE_LABEL)
        if edges is None:
            return False
        try:
            plan = plan_loop_slide(services.scene.mesh, edges)
        except LoopSlideRefused as exc:
            services.status(str(exc))
            return False
        services.interaction.start(LoopSlideGesture(self, key, plan, origin))
        services.set_hovered(None)
        services.status(f"{LOOP_SLIDE_LABEL}: {len(plan.vertex_ids)} vertices - move the mouse, release {key.upper()} to commit")
        return True

    def _arm_vertex_slide(self, key: str, origin) -> bool:
        """Hold G in vertex mode: plan the slide of the selected (else the hovered) vertices now; refusals are
        posted at the press."""
        services = self.services
        mesh = services.scene.mesh
        selection = services.selection
        vertices = {v for v in selection.vertices if mesh.is_valid_vertex(v)}
        hovered = selection.hovered
        if not vertices and isinstance(hovered, VertexId) and mesh.is_valid_vertex(hovered):
            vertices = {hovered}
        if not vertices:
            services.status(f"{VERTEX_SLIDE_LABEL}: select or hover a vertex")
            return False
        try:
            plan = plan_vertex_slide(
                mesh, vertices, blocked=frozenset(services.hidden_vertices()), mask=services.mask_values(vertices)
            )
        except VertexSlideRefused as exc:
            services.status(str(exc))
            return False
        camera = services.edit_camera
        w, h = services.viewport_size
        px = {
            vid: (
                camera.project_to_screen(start, w, h),
                tuple(camera.project_to_screen(p, w, h) for _, p in plan.candidates[vid]),
            )
            for vid, start in plan.origins.items()
        }
        services.interaction.start(VertexSlideGesture(self, key, plan, px, origin))
        services.set_hovered(None)
        count = len(plan.vertex_ids)
        noun = "vertex" if count == 1 else "vertices"
        services.status(
            f"{VERTEX_SLIDE_LABEL}: {count} {noun} - move the mouse towards an edge, release {key.upper()} to commit"
        )
        return True

    def topology_changed(self) -> None:
        """After a topology gesture's begin / commit / cancel: caches, viewport and a dead-ID sweep (B6 lesson: a
        stale hovered / selected ID after a topology change crashed the draw loop)."""
        services = self.services
        services.invalidate_picks()
        services.prune_selection()
        if services.viewport is not None:
            services.viewport.on_topology_changed()
            services.viewport.on_selection_changed()
        services.soft_preview_refresh()

    # -- constraints and space -----------------------------------------------------------------------

    def constrain(self, space: str) -> bool:
        """A constraint key (B4.1, as the Playground): the same key again -> free, another replaces it. Works without
        an armed gesture too; while a gesture runs only the setting changes - its `space` is fixed from `begin()`,
        the new value is for the next gesture (one-shot: that one's commit clears it, not this one's)."""
        self.axis_constraint = None if self.axis_constraint == space else space
        session = self.session
        if session is not None and session.begun:
            session.retouched = True
        self.services.status(self.constraint_status())
        return True

    def constraint_status(self) -> str:
        if self.axis_constraint is None:
            return "Constraint: none"
        return f"Constraint: {constraint_label(self.axis_constraint)} ({self.constraint_mode})"

    def consume_constraint(self, session: GestureSession) -> bool:
        """One-shot (Manu A1, E1): the committed gesture used the constraint, so it goes - unless a constraint key
        was pressed during the gesture (that one is for the next gesture) or the gesture ignored it. True = cleared."""
        if (
            self.constraint_mode != CONSTRAINT_ONE_SHOT
            or session.retouched
            or self.axis_constraint is None
            or session.space is None  # not used: object Scale is always uniform
        ):
            return False
        self.axis_constraint = None
        return True

    def toggle_constraint_mode(self) -> bool:
        """One-shot <-> sticky constraints (2026-10-28 practical-test switch, not saved)."""
        index = CONSTRAINT_MODES.index(self.constraint_mode)
        self.constraint_mode = CONSTRAINT_MODES[(index + 1) % len(CONSTRAINT_MODES)]
        self.services.status(f"Constraints: {self.constraint_mode} (session setting)")
        return True

    def toggle_orientation(self) -> bool:
        """`K` (WP Toolbox Gaps C1, the Playground's key, `PROVISIONAL`): World <-> Normal. Clears the constraint like
        the Playground: the same letter is another direction in the other frame. Not during a begun gesture (its
        frame is fixed at `begin()`); an armed one takes the new value."""
        session = self.session
        if session is not None and session.begun:
            return False
        self.orientation = transform_space.NORMAL if self.orientation == transform_space.WORLD else transform_space.WORLD
        self.axis_constraint = None
        self.services.status(f"Transform space: {self.orientation.capitalize()} (constraint none)")
        return True

    # -- Soft live radius / flow (AD-020 "Live radius", "Loop / Ring flow", `PROVISIONAL`) -----------

    def live_tool(self):
        """The tool of a begun Soft Move / Rotate / Scale (key hold, Tweak or gizmo drag), else None."""
        session = self.session
        return None if session is None else session.live_tool()

    def soft_live(self) -> bool:
        """A running Soft gesture takes radius / flow steps live: a begun Soft W/E/R, or a held Smooth / Relax with
        Soft on (C2)."""
        session = self.session
        return session is not None and session.soft_live()

    def radius_live(self, delta: int) -> bool:
        """One radius step for the running Soft gesture: it is re-evaluated from its start geometry with the new
        influence, the display shows the new weights, and the sticky setting takes the same step. Clamped, no wrap;
        False at the end of the list (nothing recomputed). Metric, curve and display stay those of the gesture."""
        session = self.session
        settings = session.soft
        step = max(0, min(settings.radius_step + delta, len(RADIUS_STEPS_PERCENT) - 1))
        if step == settings.radius_step:
            return False
        settings = settings.with_radius_step(step, session.soft_reference)
        services = self.services
        services.set_soft_settings(
            dataclasses.replace(services.soft_settings, radius_step=step, world_radius=settings.world_radius)
        )
        session.reweight(settings)
        return True

    def flow_live(self, delta: int) -> bool:
        """One Loop / Ring balance step for the running Soft gesture: the same re-evaluation as a live radius step;
        the sticky setting takes the same step. Clamped, no wrap; False at the end of the list."""
        session = self.session
        settings = session.soft.with_flow_step(delta)
        if settings == session.soft:
            return False
        services = self.services
        services.set_soft_settings(dataclasses.replace(services.soft_settings, flow_step=settings.flow_step))
        session.reweight(settings)
        return True
