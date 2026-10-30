"""PointerToolsController (AD-027 §3.4): what the pointer does under a held key - the Working Pivot (P), the Lasso
(Q) and the light drag (L) as hold keys in the slot (`PivotHold`, `LassoHold`, `LightHold`) - the Working Pivot
itself (a sticky setting: placed, on / off, of one object), and the press sessions of an LMB press: Box / Paint /
Lasso (`DragSelect`), a press on a gizmo handle before the drag decides (`GizmoPress`) and a refused drag gesture
that swallows the rest of its drag (`SwallowedGesture`).

Behaviour as it was inside `Application` (AD-027 M4 / M5 move it, nothing else). Hold keys are a lighter kind than
sessions (AD-027 §3.1): several may be held, a session may start while one is held, each ends with its own key
release (the pivot also on Cancel). Their precedence is the slot's fixed rank: Pivot, Lasso, Light (then the Morph
weight): the pivot claims its LMB press / drag / release, Cancel and the hover *before* the running session (V1,
V3, V7); the light drag takes the motion only *after* it (V5) and before the Morph weight (V4).

The press sessions sit in the slot's press field (owner None): a session (the Knife, the Re-Symmetrize preview) may
start while one runs, as it always could, and the press keeps its own release. Until the held gestures move (AD-027
M6) the gizmo / Tweak origin that arms a gesture from a gizmo drag stays in `Application` and reads `GizmoPress`.
"""

from __future__ import annotations

import math
from typing import Optional

from core import SelectionMode

from ..interaction import commands
from ..interaction.session import (
    PASS,
    SILENT,
    Command,
    Drag,
    Hover,
    Motion,
    Outcome,
    Press,
    Refusal,
    Release,
    RunContext,
)
from ..interaction.tools import resolve_selection_vertices
from ..interaction.tools.selection_helpers import selection_pivot
from ..pivot import WorkingPivot, place_pivot, snap_to_plane
from ..subdivision import SUBD_COMMANDS
from ..viewport.box_select import normalized_rect, stroke_samples
from ..viewport.look_controls import DRAG_DEGREES_PER_PIXEL
from .services import AppServices

#: Pixels the pointer must move before the next Lasso outline point is added (`PROVISIONAL`).
LASSO_POINT_SPACING_PX = 3.0

_SELECT_DRAGS = frozenset({commands.SELECT_DRAG, commands.SELECT_DRAG_ADD})
#: The drag steps a refused LMB gesture swallows until its release: select drags, the Tweak drag (navigation runs).
_SWALLOWED_DRAGS = _SELECT_DRAGS | {commands.TWEAK}
#: What a running Box / Paint / Lasso drag lets through (it owns the selection until the LMB release).
DRAG_SELECT_ALLOWS = frozenset(
    {
        commands.CANCEL,
        commands.TOGGLE_ORTHO,
        *commands.DISPLAY_COMMANDS,
        *commands.LOOK_COMMANDS,
        commands.CONSTRAINT_MODE_TOGGLE,
        commands.GIZMO_SIZE_CYCLE,
        *SUBD_COMMANDS,
    }
)


class _Hold:
    """A hold key's common part: the key that holds it (None = not held), registered in the slot while held."""

    command: str = ""

    def __init__(self, controller: "PointerToolsController") -> None:
        self._controller = controller
        self.key: str | None = None

    def claims(self, event) -> Outcome:
        return PASS

    def background(self, event) -> Outcome:
        return PASS

    def _gesture_armed(self) -> bool:
        # A held W/E/R/T/G/S/I/Ctrl+B owns the pointer (`can_run` stage 6 refuses the hold keys under it first; the
        # arms keep the check of their own).
        return self._controller.services.interaction_owner == "transform"


class LassoHold(_Hold):
    """Q held (2026-10-21): LMB drags make a lasso until it is let go (`commands.LASSO_ARM`). A running Lasso drag
    runs to its LMB release."""

    command = commands.LASSO_ARM

    def arm(self, key: str) -> bool:
        """Not underneath a held W/E/R/T/G (the same gate as the mode keys) and not in a Knife session (which has
        its own key map and never gets here)."""
        services = self._controller.services
        if services.viewport is None or self._gesture_armed():
            return False
        if self.key is None:
            services.status("Lasso: drag with LMB (Shift adds, Esc cancels)")
        self.key = key
        services.interaction.hold(self)
        return True

    def release(self) -> bool:
        services = self._controller.services
        self.key = None
        services.interaction.unhold(self)
        services.status("Lasso off")
        return True


class LightHold(_Hold):
    """L held (AD-024 Q-L2): mouse motion turns the key light until it is let go. View state only."""

    command = commands.LIGHT_DRAG

    def arm(self, key: str) -> bool:
        """Not underneath a held W/E/R/T/G (the motion belongs to the gesture)."""
        services = self._controller.services
        if self._gesture_armed():
            return False
        if self.key is None:
            services.status("Light: move the mouse to turn the key light (release L to stop)")
        self.key = key
        services.interaction.hold(self)
        return True

    def background(self, event) -> Outcome:
        if not isinstance(event, Motion):
            return PASS
        # The Lab's light drag (E13): dx → key azimuth, dy → key elevation, in the light's space.
        services = self._controller.services
        rig = services.display.light_rig
        changed = services.set_light(
            key_azimuth=rig.key_azimuth + event.dx * DRAG_DEGREES_PER_PIXEL,
            key_elevation=rig.key_elevation + event.dy * DRAG_DEGREES_PER_PIXEL,
        )
        if changed:
            rig = services.display.light_rig
            services.status(f"Light: Key Azimut {rig.key_azimuth:+.1f}° · Höhe {rig.key_elevation:+.1f}°")
        return changed

    def release(self) -> bool:
        services = self._controller.services
        self.key = None
        services.interaction.unhold(self)
        services.status(f"Light: {services.display.light_label}")
        return True


class PivotHold(_Hold):
    """P held (2026-10-28, Manu U-1..U-4, `mirai.pivot`): LMB clicks place the Working Pivot until it is let go; a
    tap without a click switches it off / on. `before` = the pivot at the press (Esc restores it), `placed` = a
    click placed it during this hold, `dragging` = the running LMB placement (it continues past the key release
    to its LMB release, so the hold stays in the slot until both ended), `preview` = the hover preview point,
    `on_plane` = the last point (preview or placement) was snapped onto the symmetry plane (V-3)."""

    command = commands.PIVOT_PLACE

    def __init__(self, controller: "PointerToolsController") -> None:
        super().__init__(controller)
        self.before: WorkingPivot | None = None
        self.placed = False
        self.dragging = False
        self.preview = None
        self.on_plane = False

    def arm(self, key: str) -> bool:
        """Not underneath a held W/E/R/T/G (the same gate as Lasso); refused in mode `4`."""
        controller = self._controller
        services = controller.services
        if services.viewport is None or self._gesture_armed():
            return False
        if services.selection.mode is SelectionMode.OBJECT:
            services.status("Working Pivot: for points / edges / faces - press 1/2/3 (objects turn about their own pivot)")
            return False
        if self.key is None:
            self.before = controller.working_pivot
            self.placed = False
            services.status(
                f"Working Pivot: click to place (inside the mesh; Shift = vertex / edge), release {key.upper()} to"
                " finish, tap = off / on"
            )
        self.key = key
        services.interaction.hold(self)
        services.refresh_hover()
        return True

    def claims(self, event) -> Outcome:
        services = self._controller.services
        if isinstance(event, Press):
            # While the key is held an LMB press places the pivot; Alt+LMB keeps navigating. (The app routes a
            # press only while no pointer gesture is active.)
            input = event.input
            if (
                self.key is not None
                and input.kind == "mouse"
                and input.value == "LEFT"
                and "alt" not in input.modifiers
                and not self.dragging
                and services.cursor is not None
            ):
                self.place_at(*services.cursor, snap="shift" in input.modifiers)
                self.dragging = True
                return True
            return PASS
        if isinstance(event, Drag):
            if event.command is None and self.dragging:
                cursor = services.cursor
                return cursor is not None and self.place_at(*cursor, snap=services.modifiers[0])
            return PASS
        if isinstance(event, Release):
            if event.raw and self.dragging and event.button == "LEFT":
                self.dragging = False
                if self.key is None:
                    services.interaction.unhold(self)
                return True
            return PASS
        if isinstance(event, Hover):
            if self.key is None:
                return PASS
            # Placing the pivot: the marker preview shows where a click lands; no selection hover.
            self.preview = self.point_at(event.x, event.y, snap=services.modifiers[0])
            return services.set_hovered(None)
        if isinstance(event, Command) and event.command == commands.CANCEL and self.key is not None:
            return self.cancel()
        return PASS

    def anchor(self):
        """The depth for a click off the mesh: the current pivot of this object, else the selection centre."""
        services = self._controller.services
        pivot = self._controller.working_pivot
        if pivot is not None and pivot.object_id == services.scene.edit_object_id:
            return pivot.position
        mesh = services.scene.mesh
        selection = services.selection
        vertex_ids = resolve_selection_vertices(mesh, selection, selection.mode)
        return selection_pivot(mesh, vertex_ids) if vertex_ids else None

    def point_at(self, x: float, y: float, snap: bool):
        """The pivot point a click at (x, y) would place; with symmetry on, snapped onto the plane when it is
        within `PIVOT_PLANE_SNAP_PX` on screen (V-3, every placement mode, also the preview)."""
        services = self._controller.services
        width, height = (int(v) for v in services.viewport_size)
        camera = services.edit_camera
        mesh = services.scene.mesh
        point = place_pivot(
            camera, mesh, x, y, width, height,
            snap=snap, anchor=self.anchor(), cache=services.pick_cache, occlusion=services.display.show_faces,
        )
        self.on_plane = False
        definition = mesh.symmetry_definition
        if point is not None and definition is not None:
            point, self.on_plane = snap_to_plane(
                camera, point, definition.plane_point, definition.plane_normal, width, height,
            )
        return point

    def place_at(self, x: float, y: float, snap: bool) -> bool:
        """Places the pivot under (x, y) and switches it on - no History entry (U-3). True = placed."""
        controller = self._controller
        services = controller.services
        point = self.point_at(x, y, snap)
        if point is None:
            services.status("Working Pivot: no point under the cursor")
            return False
        controller.working_pivot = WorkingPivot(services.scene.edit_object_id, tuple(float(c) for c in point))
        self.placed = True
        self.preview = None
        where = " on the symmetry plane" if self.on_plane else ""
        services.status(f"Working Pivot placed{where} - E / R turn and scale around it")
        return True

    def release(self) -> bool:
        """The key went up: placement ends; a tap without a click switches the pivot off / on (U-1). A running
        LMB placement continues to its release."""
        controller = self._controller
        services = controller.services
        self.key = None
        self.preview = None
        if not self.dragging:
            services.interaction.unhold(self)
        pivot = controller.working_pivot
        if self.placed:
            pass  # the placing status line stays
        elif pivot is None or pivot.object_id != services.scene.edit_object_id:
            services.status("Working Pivot: none on this object - hold P and click to place one")
        else:
            controller.working_pivot = pivot.toggled()
            if controller.working_pivot.enabled:
                services.status("Working Pivot on - E / R turn and scale around it")
            else:
                services.status("Working Pivot off - E / R use the selection centre")
        services.refresh_hover()
        return True

    def cancel(self) -> bool:
        """Esc while the key is held: the pivot as it was at the press, placement ends."""
        controller = self._controller
        services = controller.services
        controller.working_pivot = self.before
        self.key = None
        self.preview = None
        self.dragging = False
        services.interaction.unhold(self)
        services.status("Working Pivot: placement cancelled")
        services.refresh_hover()
        return True


class DragSelect:
    """A running LMB drag selection (2026-10-15, Manu: "Startpunkt entscheidet"): `box` when the press was in empty
    space, else `paint`; with the Lasso key held (2026-10-21) `lasso` whatever the press point. `add` = Shift (adds)
    instead of replacing. `before` is the selection at the start (Esc restores it); `last` the last painted point;
    `points` the lasso outline so far (window pixels). Alt held at the release makes a box or lasso select through
    the mesh (WP Toolbox Gaps A2, Manu 2026-10-23); paint stays visible-only. Esc keeps it in the slot as
    `cancelled` until the LMB release. A press session (owner None)."""

    owner = None
    exclusive = False

    def __init__(self, controller: "PointerToolsController", kind: str, add: bool, start, end, before: tuple,
                 last, points: list) -> None:
        self._controller = controller
        self.kind = kind
        self.add = add
        self.start = start
        self.end = end
        self.before = before
        self.last = last
        self.cancelled = False
        self.points = points

    @property
    def label(self) -> str:
        return self.kind.capitalize()

    def grabs(self, event) -> bool:
        return False

    def allows(self, command: str, ctx: RunContext) -> Optional[Refusal]:
        if command in DRAG_SELECT_ALLOWS or ctx.source == "wheel":
            return None  # the Soft wheel steps were never held back by a drag
        return SILENT

    def handle(self, event) -> Outcome:
        if isinstance(event, Drag) and event.command in _SELECT_DRAGS:
            cursor = self._controller.services.cursor
            return False if cursor is None else self.step(cursor)
        if isinstance(event, Command) and event.command == commands.CANCEL:
            return self.cancel()
        return PASS

    def step(self, cursor) -> bool:
        if self.cancelled:
            return False
        self.end = cursor
        if self.kind == "paint":
            self._controller.paint_at(stroke_samples(self.last, cursor))
            self.last = cursor
        elif self.kind == "lasso":
            last = self.points[-1]
            if math.hypot(cursor[0] - last[0], cursor[1] - last[1]) >= LASSO_POINT_SPACING_PX:
                self.points.append(cursor)
        return True

    def cancel(self) -> bool:
        if self.cancelled:
            return False
        services = self._controller.services
        self.cancelled = True
        if self.kind == "paint":
            services.restore_selection(self.before)
            services.notify_selection_changed()
        services.status(f"{self.kind.capitalize()} cancelled")
        return True

    def commit(self) -> bool:
        """The LMB release: apply the box / lasso (paint selected as it went), one status line; a cancelled drag
        ends without a change."""
        controller = self._controller
        services = controller.services
        services.interaction.end_press(self)
        if self.cancelled:
            services.refresh_hover()
            return False
        selection = services.selection
        if self.kind == "lasso":
            return self._finish_lasso()
        occlusion = controller.region_occlusion()
        through = "" if occlusion or not services.display.show_faces else " (through)"
        if self.kind == "box":
            found = services.pick_in_rect(normalized_rect(self.start, self.end), occlusion)
            if self.add:
                selection.add(found)
            else:
                selection.set(found)
            label = "Box" + through
        else:
            label = "Paint"
        services.notify_selection_changed()
        services.soft_preview_refresh()
        services.status(f"{label}: {controller.selected_text()}")
        services.refresh_hover()
        return True

    def _finish_lasso(self) -> bool:
        """Apply a finished Lasso: the elements whose corners all lie inside the outline (as Box, with the same
        occlusion rule, Alt = through); fewer than three outline points select nothing and change nothing."""
        controller = self._controller
        services = controller.services
        selection = services.selection
        polygon = self.points
        if len(polygon) < 3:
            services.status("Lasso: draw a closed outline")
            services.refresh_hover()
            return True
        occlusion = controller.region_occlusion()
        through = "" if occlusion or not services.display.show_faces else " (through)"
        found = services.pick_in_polygon(polygon, occlusion)
        if self.add:
            selection.add(found)
        else:
            selection.set(found)
        services.notify_selection_changed()
        services.soft_preview_refresh()
        services.status(f"Lasso{through}: {controller.selected_text()}")
        services.refresh_hover()
        return True


class GizmoPress:
    """An LMB press without a modifier on a gizmo handle (AD-016 D3, 2026-10-21): it owns the gesture from the press;
    a click leaves just the constraint the press set, a drag arms the current tool along the handle (the gizmo /
    Tweak origin in `Application` until AD-027 M6). `handle_id` = the pressed handle, `press_xy` = the cursor at the press (the Rotate dial),
    `constraint_before` = the pending constraint before the press (one-shot: Esc on a handle drag restores it, E2),
    `refused` = the handle drag was refused or cancelled, the rest of it does nothing. A press session (owner None);
    it refuses nothing."""

    owner = None
    label = None
    exclusive = False

    def __init__(self, handle_id: str, press_xy, constraint_before) -> None:
        self.handle_id = handle_id
        self.press_xy = press_xy
        self.constraint_before = constraint_before
        self.refused = False

    def grabs(self, event) -> bool:
        return False

    def allows(self, command: str, ctx: RunContext) -> Optional[Refusal]:
        return None

    def handle(self, event) -> Outcome:
        if isinstance(event, Drag) and self.refused and event.command in _SWALLOWED_DRAGS:
            return False
        if isinstance(event, Press):
            return False  # its press runs to its release: no second gizmo press
        return PASS

    def cancel(self) -> bool:
        return False

    def commit(self) -> bool:
        return False


class SwallowedGesture:
    """A refused LMB drag gesture (a drag selection, a Tweak or a gizmo drag `can_run` or the gesture's own start
    refused, or a Tweak drag Esc cancelled): its further select / Tweak drag steps do nothing until its LMB release,
    and no gizmo press starts under it; navigation runs. A press session (owner None); it refuses nothing."""

    owner = None
    label = None
    exclusive = False

    def grabs(self, event) -> bool:
        return False

    def allows(self, command: str, ctx: RunContext) -> Optional[Refusal]:
        return None

    def handle(self, event) -> Outcome:
        if isinstance(event, Drag) and event.command in _SWALLOWED_DRAGS:
            return False
        if isinstance(event, Press):
            return False
        return PASS

    def cancel(self) -> bool:
        return False

    def commit(self) -> bool:
        return False


class PointerToolsController:
    """The hold keys of the pointer tools, the Working Pivot (`working_pivot`: None = never placed; also while off or
    on another object) and the press sessions."""

    def __init__(self, services: AppServices) -> None:
        self.services = services
        self.working_pivot: WorkingPivot | None = None
        self.pivot = PivotHold(self)
        self.lasso = LassoHold(self)
        self.light = LightHold(self)

    # -- the press sessions ----------------------------------------------------------------------------

    @property
    def drag_select(self) -> DragSelect | None:
        press = self.services.interaction.press
        return press if isinstance(press, DragSelect) else None

    @property
    def gizmo_press(self) -> GizmoPress | None:
        press = self.services.interaction.press
        return press if isinstance(press, GizmoPress) else None

    def press_gizmo(self, handle_id: str, press_xy, constraint_before) -> GizmoPress:
        press = GizmoPress(handle_id, press_xy, constraint_before)
        self.services.interaction.start_press(press)
        return press

    def swallow(self) -> None:
        """The rest of this LMB gesture does nothing until its release. A gizmo press keeps its own release (it only
        stops arming); a drag selection, which cannot be refused mid-drag, keeps running."""
        interaction = self.services.interaction
        press = interaction.press
        if isinstance(press, GizmoPress):
            press.refused = True
        elif press is None:
            interaction.start_press(SwallowedGesture())

    def end_swallowed(self) -> None:
        """The LMB went up: a swallowed gesture is over."""
        interaction = self.services.interaction
        if isinstance(interaction.press, SwallowedGesture):
            interaction.end_press(interaction.press)

    # -- Box / Paint / Lasso (2026-10-15, Playground tools promoted, Manu) ------------------------------
    #
    # Box: Selection Lab KEEP (`playground/experiments/selection/decision.md`). Paint: planned there ("Paint
    # Select"), first built here. Manu 2026-10-15: the press point decides - in empty space a box, on the mesh a
    # paint stroke; no modifier replaces, Shift adds. Like a click, neither is a History step. Not in mode `4`
    # (`PROVISIONAL`).

    def drag_select_refusal(self, command: str) -> Refusal | None:
        """Why a drag selection cannot start now (None = it can): `can_run` (a Knife session, a held gesture, the
        host gate), then the drag's own preconditions (no viewport; mode `4`)."""
        services = self.services
        refusal = services.can_run(command, RunContext("drag"))
        if refusal is not None:
            return refusal
        if services.viewport is None:
            return SILENT
        if services.selection.mode is SelectionMode.OBJECT:
            return Refusal("Box/Paint/Lasso: points, edges and faces only - press 1/2/3")
        return None

    def start_drag_select(self, command: str) -> bool:
        """The first select-drag step of an LMB gesture nothing else took: a box, paint or lasso starts at the press
        point (refused: the rest of the gesture is swallowed), and takes this step."""
        services = self.services
        cursor = services.cursor
        if cursor is None:
            return False
        refusal = self.drag_select_refusal(command)
        if refusal is not None:
            if refusal.text is not None:
                services.status(refusal.text)
            self.swallow()  # silence the rest of this gesture
            return False
        start = services.press_point if services.press_point is not None else cursor
        lasso = self.lasso.key is not None
        on_mesh = False if lasso else services.pick_face(start[0], start[1]) is not None
        drag = DragSelect(
            self,
            kind="lasso" if lasso else "paint" if on_mesh else "box",
            add=command == commands.SELECT_DRAG_ADD,
            start=start,
            end=cursor,
            before=services.selection_snapshot(),
            last=start,
            points=[start] if lasso else [],
        )
        services.interaction.start_press(drag)
        services.set_hovered(None)
        if drag.kind == "paint":
            if not drag.add:
                services.selection.clear()
                services.notify_selection_changed()
            self.paint_at([start])
        return drag.step(cursor)

    def paint_at(self, points) -> None:
        services = self.services
        hits = {hit for hit in (services.pick(x, y) for x, y in points) if hit is not None}
        before = len(self.active_selection_ids())
        services.selection.add(hits)
        if len(self.active_selection_ids()) != before:
            services.notify_selection_changed()

    def active_selection_ids(self) -> set:
        selection = self.services.selection
        if selection.mode is SelectionMode.VERTEX:
            return selection.vertices
        if selection.mode is SelectionMode.EDGE:
            return selection.edges
        return selection.faces

    def selected_text(self) -> str:
        count = len(self.active_selection_ids())
        noun = self.services.selection.mode.name.lower()
        if count != 1:
            noun = "vertices" if noun == "vertex" else noun + "s"
        return f"{count} {noun} selected"

    def region_occlusion(self) -> bool:
        """The occlusion rule of a Box / Lasso release: only what is visible while faces are shown, unless Alt is
        held (`Application.selection_through`)."""
        return self.services.display.show_faces and not self.services.modifiers[2]
