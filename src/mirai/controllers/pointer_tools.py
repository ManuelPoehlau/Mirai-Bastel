"""PointerToolsController (AD-027 §3.4): what the pointer does under a held key - the Working Pivot (P), the Lasso
(Q) and the light drag (L) as hold keys in the slot (`PivotHold`, `LassoHold`, `LightHold`) - and the Working Pivot
itself (a sticky setting: placed, on / off, of one object).

Behaviour as it was inside `Application` (AD-027 M4 moves it, nothing else). Hold keys are a lighter kind than
sessions (AD-027 §3.1): several may be held, a session may start while one is held, each ends with its own key
release (the pivot also on Cancel). Their precedence is the slot's fixed rank: Pivot, Lasso, Light (then the Morph
weight): the pivot claims its LMB press / drag / release, Cancel and the hover *before* the running session (V1,
V3, V7); the light drag takes the motion only *after* it (V5) and before the Morph weight (V4).
"""

from __future__ import annotations

from core import SelectionMode

from ..interaction import commands
from ..interaction.session import PASS, Command, Drag, Hover, Motion, Outcome, Press, Release
from ..interaction.tools import resolve_selection_vertices
from ..interaction.tools.selection_helpers import selection_pivot
from ..pivot import WorkingPivot, place_pivot, snap_to_plane
from ..viewport.look_controls import DRAG_DEGREES_PER_PIXEL
from .services import AppServices


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


class PointerToolsController:
    """The hold keys of the pointer tools and the Working Pivot (`working_pivot`: None = never placed; also while
    off or on another object)."""

    def __init__(self, services: AppServices) -> None:
        self.services = services
        self.working_pivot: WorkingPivot | None = None
        self.pivot = PivotHold(self)
        self.lasso = LassoHold(self)
        self.light = LightHold(self)
