"""PaintRoomController (AD-037 §8 Phase 2): the Paint Room's session in the slot, the shown paint surface and the strokes.

The room is a configuration of the same window (P-2, the Eye Lab pattern; `Application.open_paint_room` saves and
restores the view state). While it is open one **exclusive session** runs (`PaintRoomSession`, `interaction_owner`
"paint", like the Knife): plain LMB drag paints (P-6 concept; the code default only, no keymap entry before Manu's "Taste
passt"), Alt+LMB still orbits and pans, the Soft radius wheel (Shift+wheel) steps the brush radius and Alt+wheel its
opacity (`commands.PAINT_OPACITY_UP` / `DOWN` in the `paint` binding context). Its `allows` lets through what the room
needs: Undo / Redo (one step per stroke; not while a stroke runs), Cancel, the views and display state, the SubD keys
(P-10: the room paints on whatever is shown), the symmetry cycle and saving.

**A stroke** (`begin` at the press, `step` per drag event, `end` at the release, `cancel` on Esc; Phase 4a, AD-037 §12):
the events only feed the cursor's rays into the stroke's `mirai.paint.dynamics.StrokeQueue`; the path is sampled on the
shown surface (`mirai.paint.surface.PaintSurface`: the SubD surface when SubD shows, else the cage) and placements lie
every `dynamics.spacing` of the stamp diameter in **world arc length** (P-18). `frame()` - once per frame, from
`Application.update_viewport` before the paint display's update - samples and evaluates within a time budget
(`dynamics.frame_budget`: 10 ms, raised by the excess while more than `BACKLOG_S` of work trails the cursor): each
placement is one `mirai.paint.stamp.evaluate` (the round tip exactly as the Phase 2 dab, or the alpha tip's projected
stamp) with its mirror across the mesh's symmetry plane, accumulated in the stroke buffer (`mirai.paint.brush.PaintStroke`).
**The release never evaluates in the event:** the stroke is *finishing* (`finishing`) and the next frames drain the rest
(`FINISH_BUDGET_S`); then the seams of the touched tiles are padded (`surface.seam_pad`) and one History step is pushed -
with the new paint stack, when the object had none (2048² by default, P-5; 1024² the fast option). While finishing,
Undo / Redo / Shift+S / the SubD keys, a new press, saving and closing the room first finish the stroke (`settle`: the
rest is bounded) and then run. Esc restores every touched tile exactly, while stroking and while finishing. Faces
without usable UVs hold no texel: the dab skips them (P-13) and the status line says so when the cursor is on one.

**Pick** (the eyedropper): the composite's colour at the hit's UV (the albedo, not the lit frame colour); then the
previous tool again (`PROVISIONAL`).

**Layers** (Phase 3, AD-037 §11): strokes paint on the active layer (`active_layer`; view state, the top one by default),
not on a hidden one; `layer_step` pushes a `mirai.paint.layers` step between strokes; a held opacity slider previews
(`preview_layer`) and makes its one step on release.
"""

from __future__ import annotations

import math
import time
from typing import Optional

import numpy as np

from core import PaintLayer, PaintStack

from ..interaction import commands
from ..interaction.input import PAINT_CONTEXT
from ..interaction.session import (
    PASS,
    SILENT,
    Command,
    Drag,
    Hover,
    KeyPress,
    Leave,
    Modifiers,
    Motion,
    Outcome,
    Press,
    Refusal,
    Release,
    RunContext,
    Wheel,
)
from ..mesh_geometry import mesh_center_and_radius
from ..paint import alpha as alpha_api
from ..paint import brush as brush_api
from ..paint import dynamics as dynamics_api
from ..paint import layers as layers_api
from ..paint import stamp as stamp_api
from ..paint.store import PaintError, PaintStackCommand, tile_box
from ..paint.surface import PaintSurface, mirror, pad_width, seam_pad
from ..scene_objects import CompositeCommand
from ..subdivision import SUBD_COMMANDS
from viewport.overlay import TOOL_MIRROR_DIM_LAYER, TOOL_PREVIEW_LAYER
from .services import AppServices

#: The name of the first layer of a new stack (`PROVISIONAL`).
FIRST_LAYER = "Ebene 1"
#: P-5 (Manu 2026-11-18): 2048² default, 1024² the fast option, 4096² not offered on the reference PC.
RESOLUTIONS = (2048, 1024)
DEFAULT_RESOLUTION = 2048
#: The path's sample step on screen: the spacing in pixels, clamped to this range (`PROVISIONAL`, Phase 4a).
SAMPLE_STEP_PX = (2.0, 6.0)

#: What the room lets through (module docstring); Undo / Redo are refused while a stroke runs (`allows`).
PAINT_ALLOWS = frozenset(
    {
        commands.CANCEL,
        commands.UNDO,
        commands.REDO,
        commands.TOGGLE_ORTHO,
        commands.SYMMETRY_CYCLE,
        commands.SOFT_RADIUS_UP,
        commands.SOFT_RADIUS_DOWN,
        *commands.DISPLAY_COMMANDS,
        *commands.LOOK_COMMANDS,
        *SUBD_COMMANDS,
    }
)


#: Refused while a stroke runs (its press is down): History steps, the plane the mirrored dab reads, the shown surface.
_NOT_WHILE_STROKING = frozenset({commands.UNDO, commands.REDO, commands.SYMMETRY_CYCLE, *SUBD_COMMANDS})


class PaintRoomSession:
    """The room's session in the slot (module docstring)."""

    owner = "paint"
    label = "Paint"
    exclusive = True

    def __init__(self, controller: "PaintRoomController") -> None:
        self._controller = controller
        #: the room's own LMB press is down (its drags and its release are the room's)
        self.pressed = False
        #: a stroke runs (a Pick press, or a press beside the object, has no stroke)
        self.stroking = False

    def grabs(self, event) -> bool:
        if isinstance(event, Press):
            return (event.input.kind == "mouse" and event.input.value == "LEFT" and not event.input.modifiers
                    and not self.pressed)
        if isinstance(event, Drag):
            return event.command is None and self.pressed
        if isinstance(event, Release):
            return event.raw and self.pressed and event.button == "LEFT"
        if isinstance(event, Wheel):
            return event.command != commands.ZOOM  # zoom stays navigation
        if isinstance(event, KeyPress):
            command = self._controller.services.bindings.command_for(event.input)
            # Esc; and while a stroke finishes the keys that wait for it (`handle` finishes it, the key goes on)
            return command == commands.CANCEL or (self._controller.finishing and command in _NOT_WHILE_STROKING)
        return isinstance(event, (Motion, Hover, Leave, Modifiers))

    def allows(self, command: str, ctx: RunContext) -> Optional[Refusal]:
        if command not in PAINT_ALLOWS:
            return SILENT
        if command in _NOT_WHILE_STROKING and (self.stroking or self._controller.finishing):
            return SILENT  # (a key for them while finishing first finishes the stroke in `handle`; `can_run` stays pure)
        return None

    def handle(self, event) -> Outcome:
        if not self.grabs(event):
            return PASS
        controller = self._controller
        if isinstance(event, Press):
            x, y = (event.x, event.y) if event.x is not None else controller.services.cursor or (None, None)
            self.pressed = True
            if x is not None:
                self.stroking = controller.begin(x, y)
            return True
        if isinstance(event, Drag):
            cursor = controller.services.cursor
            if cursor is not None and self.stroking:
                controller.step(*cursor)
            return True
        if isinstance(event, Release):
            self.pressed = False
            if not self.stroking:
                return False
            self.stroking = False
            return controller.end(event.x, event.y)
        if isinstance(event, Wheel):
            return controller.wheel(event.input, event.command)
        if isinstance(event, KeyPress):
            if controller.services.bindings.command_for(event.input) != commands.CANCEL:
                controller.settle()  # the stroke's bounded rest now, then the key's command runs (`can_run`)
                return PASS
            return self.cancel()
        if isinstance(event, (Motion, Hover)):
            if not self.stroking:
                controller.hover(event.x, event.y)
            return False
        if isinstance(event, Modifiers):
            return False
        if isinstance(event, Leave):
            if not self.stroking:
                controller.clear_cursor()
            return False
        return PASS

    def cancel(self) -> bool:
        """Esc: a running or finishing stroke is undone exactly (no History step); without one nothing happens."""
        if not self.stroking:
            return self._controller.cancel_stroke() if self._controller.finishing else False
        self.stroking = False  # the press stays the room's until its release (no new stroke starts on it)
        return self._controller.cancel_stroke()

    def commit(self) -> bool:
        return False


class PaintRoomController:
    def __init__(self, services: AppServices) -> None:
        self.services = services
        self.brush = brush_api.BrushSettings()
        #: size of a new paint stack (P-5)
        self.resolution = DEFAULT_RESOLUTION
        self.session: PaintRoomSession | None = None
        #: the view state the room restores when it closes (display mode, wire, texture, regions; `Application`'s)
        self.saved_view: dict | None = None
        self.obj = None
        self._surfaces: dict[tuple, PaintSurface] = {}
        self._bounding_radius = 1.0
        self._stroke = None
        self._stack_command = None
        #: the running stroke's sampler and queue (Phase 4a), its surface, alpha, radius, mirror plane, view up, sample
        #: step on screen and the last screen point
        self._queue: dynamics_api.StrokeQueue | None = None
        self._surface = None
        self._image = None
        self._radius = 0.0
        self._definition = None
        self._view_up = None
        self._step_px = SAMPLE_STEP_PX[0]
        self._screen = None
        #: the stroke was released and its rest is being evaluated over the next frames
        self.finishing = False
        self._previous_tool = brush_api.TOOL_PAINT
        #: (kind, build seconds) of the last surface built (status line, tests)
        self.last_build: tuple[str, float] | None = None
        #: dabs of the last stroke (tests, the probe)
        self.last_dabs = 0
        #: the layer strokes paint on (view state; `active_layer` falls back to the top one)
        self.active: str | None = None
        #: the stack before a held layer slider's first preview (`preview_layer`) and the stack it shows, None without one
        self._preview_before = None
        self._preview_shown = None

    @property
    def stroking(self) -> bool:
        """A stroke runs or is finishing (nothing else may change the layer, the stack or the shown surface)."""
        return self.finishing or (self.session is not None and self.session.stroking)

    # -- the room -------------------------------------------------------------------------------------------------

    def start(self, obj, saved_view: dict) -> None:
        """The room opened on `obj` (`Application.open_paint_room` checked it and set the room's view): the session
        starts, the surface is built; `saved_view` comes back from `stop`."""
        services = self.services
        self.obj = obj
        self.saved_view = saved_view
        self.active = None
        _, self._bounding_radius = mesh_center_and_radius(obj.mesh)
        self._bounding_radius = self._bounding_radius or 1.0
        self.session = PaintRoomSession(self)
        services.interaction.start(self.session)
        self.surface()

    def stop(self) -> dict | None:
        """The room closes: a running stroke is cancelled, the session ends; returns the view state to restore."""
        if self.session is None:
            return None
        if self.session.stroking:
            self.session.cancel()
        self.settle()
        self.end_preview()
        self.services.interaction.end(self.session)
        self.session = None
        self.clear_cursor()
        for surface in self._surfaces.values():
            surface.close()
        self._surfaces.clear()
        self.obj = None
        saved, self.saved_view = self.saved_view, None
        return saved

    def size(self) -> tuple[int, int]:
        stack = self.obj.paint if self.obj is not None else None
        return (stack.width, stack.height) if stack is not None else (self.resolution, self.resolution)

    def shown_kind(self) -> str:
        subdivision = self.services.subdivision
        return f"subd{subdivision.level}" if subdivision.active else "cage"

    def surface(self) -> PaintSurface | None:
        """The surface that is shown now (P-10): the SubD preview's derived mesh while it shows, else the edit mesh; built
        on first use per (mesh, size) and kept while the room is open."""
        services = self.services
        if self.obj is None:
            return None
        viewport = services.viewport
        if viewport is not None:
            viewport.sync_cage()  # a dirty SubD provider syncs first (same frame as the draw)
        subdivision = services.subdivision
        provider = subdivision.provider
        if subdivision.active and provider.surface_mesh is not None:
            mesh, kind, hidden = provider.surface_mesh, f"subd{subdivision.level}", provider.hidden_surface_faces()
        else:
            mesh, kind, hidden = services.scene.mesh, "cage", services.hidden_faces()
        width, height = self.size()
        key = (id(mesh), width, height)
        surface = self._surfaces.get(key)
        if surface is None or surface.mesh is not mesh:
            started = time.perf_counter()
            surface = PaintSurface(mesh, width, height, kind, hidden)
            self.last_build = (kind, time.perf_counter() - started)
            for old_key in [k for k, s in self._surfaces.items() if s.mesh is mesh or k[1:] != (width, height)]:
                self._surfaces.pop(old_key).close()
            self._surfaces[key] = surface
        else:
            surface.sync()
            surface.set_hidden(hidden)
        return surface

    def surface_text(self) -> str:
        kind = self.shown_kind()
        where = "dem Käfig" if kind == "cage" else f"der SubD-Fläche (Stufe {kind[4:]})"
        width, height = self.size()
        return f"malt auf {where}, {width}²" if width == height else f"malt auf {where}, {width} x {height}"

    # -- brush settings ---------------------------------------------------------------------------------------------

    def set_brush(self, **changes) -> bool:
        before = self.brush
        tool = changes.get("tool")
        if tool is not None and tool != before.tool and tool == brush_api.TOOL_PICK:
            self._previous_tool = before.tool
        self.brush = before.with_(**changes)
        if self.brush != before:
            self.services.status(self.brush.status_text())
            self._redraw_cursor()
        return self.brush != before

    def set_tip(self, alpha: str | None) -> bool:
        """The tip: None = round, else a test alpha's id (`mirai.paint.alpha.TEST_ALPHAS`); switching between round and
        alpha sets that kind's default spacing."""
        if alpha is not None and alpha not in alpha_api.TEST_ALPHAS:
            raise ValueError(f"unknown alpha {alpha!r}")
        tip = brush_api.TipSettings(alpha, self.brush.tip.kreismaske)
        before = self.brush
        self.brush = before.with_tip(tip)
        if self.brush != before:
            self.services.status(self.brush.status_text())
            self._redraw_cursor()
        return self.brush != before

    def set_resolution(self, size: int) -> bool:
        if size not in RESOLUTIONS:
            raise ValueError(f"resolution one of {RESOLUTIONS}, got {size!r}")
        if self.obj is not None and self.obj.paint is not None:
            self.services.status("Paint: the resolution is set when the first stroke makes the paint (the stack exists)")
            return False
        self.resolution = size
        if self.obj is not None:
            self.surface()
        return True

    def wheel(self, input, command) -> bool:
        if command in (commands.SOFT_RADIUS_UP, commands.SOFT_RADIUS_DOWN):
            step = self.brush.radius_step + (1 if command == commands.SOFT_RADIUS_UP else -1)
            return self.set_brush(radius_step=step) or self._at_end()
        paint = self.services.bindings.command_for(input, PAINT_CONTEXT)
        if paint in (commands.PAINT_OPACITY_UP, commands.PAINT_OPACITY_DOWN):
            stepped = self.brush.with_opacity_step(1 if paint == commands.PAINT_OPACITY_UP else -1)
            return self.set_brush(opacity=stepped.opacity) or self._at_end()
        return False  # zoom and the other wheel commands: the app's path (`pointer_scroll`)

    def _at_end(self) -> bool:
        self.services.status(self.brush.status_text())
        return False

    # -- layers (Phase 3) ---------------------------------------------------------------------------------------------

    def active_layer(self) -> str | None:
        """The layer the next stroke paints on: the chosen one while it is in the stack, else the top one (None: the
        object has no paint yet - the first stroke makes "Ebene 1")."""
        stack = self.obj.paint if self.obj is not None else None
        if stack is None:
            return None
        names = [layer.name for layer in stack.layers]
        return self.active if self.active in names else names[-1]

    def set_active_layer(self, name: str) -> bool:
        stack = self.obj.paint if self.obj is not None else None
        if stack is None or name not in [layer.name for layer in stack.layers] or self.stroking:
            return False
        changed = name != self.active_layer()
        self.active = name
        if changed:
            self.services.status(f"Paint: strokes paint on {name!r}")
        return changed

    def layer_step(self, make, active: str | None = None) -> bool:
        """Runs `make()` (a `mirai.paint.layers` function returning a step, or None for "nothing changes") and pushes the
        step as one History entry; `active` becomes the active layer. Refused between nothing and a stroke: while a
        stroke runs, and with a `PaintError` (the status line names it)."""
        services = self.services
        if self.obj is None:
            services.status("Paint layers: open the Paint Room first")
            return False
        if self.stroking:
            services.status("Paint layers: not while a stroke runs")
            return False
        self.end_preview()
        try:
            command = make()
        except PaintError as exc:
            services.status(f"Paint layers: {exc}")
            return False
        if command is None:
            return False
        if isinstance(command, tuple):
            command, active = command
        before = services.selection_snapshot()
        command.redo()
        services.history.push(command)
        services.record_selection_history(before, mesh_step=False, focus=False)
        if active is not None:
            self.active = active
        services.status(command.description)
        return True

    def preview_layer(self, name: str, **values) -> bool:
        """A held slider (opacity): the layer drawn with `values`, no History step until `set_layer_values` (the release)
        or `end_preview`."""
        obj = self.obj
        if obj is None or obj.paint is None or self.stroking:
            return False
        if self._preview_before is None or obj.paint is not self._preview_shown:
            self._preview_before = obj.paint  # a new preview, or the stack changed under it (an Undo): start from now
        try:
            obj.paint = self._preview_shown = layers_api.with_values(self._preview_before, name, **values)
        except PaintError as exc:
            self.services.status(f"Paint layers: {exc}")
            return False
        return True

    def end_preview(self) -> bool:
        """The preview ends without a step: the stack it started from again - unless something else changed the stack
        meanwhile (an Undo), which stays."""
        before, self._preview_before = self._preview_before, None
        shown, self._preview_shown = self._preview_shown, None
        if before is None or self.obj is None or self.obj.paint is not shown:
            return False
        self.obj.paint = before
        return True

    def set_layer_values(self, name: str, **values) -> bool:
        before = self._preview_before if self.obj is not None and self.obj.paint is self._preview_shown else None
        self.end_preview()
        obj = self.obj
        return self.layer_step(lambda: layers_api.set_values(obj, name, before, **values))

    # -- the cursor -------------------------------------------------------------------------------------------------

    def _ray(self, x: float, y: float):
        width, height = self.services.viewport_size
        return self.services.edit_camera.screen_to_ray(x, y, width, height)

    def hit(self, x: float, y: float):
        """(the shown surface, the hit at the screen point or None)."""
        surface = self.surface()
        if surface is None:
            return None, None
        return surface, self._hit_on(surface, x, y)

    def _hit_on(self, surface: PaintSurface, x: float, y: float):
        origin, direction = self._ray(x, y)
        return surface.hit(origin, direction)

    def radius(self) -> float:
        return self.brush.world_radius(self._bounding_radius)

    def hover(self, x: float, y: float) -> None:
        surface, hit = self.hit(x, y)
        self._show_cursor(surface, hit)

    def _redraw_cursor(self) -> None:
        cursor = self.services.cursor
        if self.session is not None and cursor is not None and not self.stroking:
            self.hover(*cursor)

    def _show_cursor(self, surface, hit) -> None:
        viewport = self.services.viewport
        if viewport is None:
            return
        if hit is None:
            viewport.set_tool_overlay()
            return
        radius = self.radius() if self.brush.tool != brush_api.TOOL_PICK else self.radius() * 0.25
        definition = self._mirror_definition()
        image = alpha_api.resolve(self.brush.tip.alpha) if self.brush.tool != brush_api.TOOL_PICK else None
        if image is None:
            segments = {TOOL_PREVIEW_LAYER: surface.circle(hit.point, hit.normal, radius)}
            if definition is not None:
                point, normal = mirror(definition, hit.point, hit.normal)
                segments[TOOL_MIRROR_DIM_LAYER] = surface.circle(point, normal, radius)
            viewport.set_tool_overlay(segments=segments)
            return
        # an alpha tip: its oriented rectangle, the circle dimmed (and the mirror's rectangle dimmed)
        normal = np.asarray(hit.normal, dtype=np.float64)
        tangent = self._queue.last_tangent if self._queue is not None else None
        t = stamp_api.frame_tangent(normal, tangent, self._camera_up())
        angle = math.radians(self.brush.dynamics.angle)
        t = math.cos(angle) * t + math.sin(angle) * np.cross(normal, t)
        b = np.cross(normal, t)
        dim = surface.circle(hit.point, hit.normal, radius)
        if definition is not None:
            point, _ = mirror(definition, hit.point, hit.normal)
            dim += _rectangle(point, stamp_api.reflect(definition, t), stamp_api.reflect(definition, b), radius, image)
        viewport.set_tool_overlay(segments={TOOL_PREVIEW_LAYER: _rectangle(hit.point, t, b, radius, image),
                                            TOOL_MIRROR_DIM_LAYER: dim})

    def _camera_up(self) -> np.ndarray:
        """The view's up in object space (the view-fixed rule of a click without movement)."""
        _, _, up = self.services.edit_camera.basis()
        return np.asarray(up, dtype=np.float64)

    def clear_cursor(self) -> None:
        viewport = self.services.viewport
        if viewport is not None:
            viewport.set_tool_overlay()

    def _mirror_definition(self):
        if not self.brush.mirror or self.brush.tool == brush_api.TOOL_PICK:
            return None
        return self.services.scene.mesh.symmetry_definition

    # -- strokes ----------------------------------------------------------------------------------------------------

    def _screen_radius(self, point, radius: float | None = None) -> float:
        """The brush radius in pixels at `point` (object space) - the path's sample step's unit."""
        services = self.services
        camera = services.edit_camera
        width, height = services.viewport_size
        _, right, _ = camera.basis()
        radius = self.radius() if radius is None else radius
        a = camera.project_to_screen(tuple(point), width, height)
        b = camera.project_to_screen(tuple(np.asarray(point) + radius * np.asarray(right)), width, height)
        if a is None or b is None:
            return 8.0
        return max(1.0, math.hypot(b[0] - a[0], b[1] - a[1]))

    def begin(self, x: float, y: float) -> bool:
        """The press: a Pick, or a stroke's first ray (its first placement is evaluated at the next frame). True = a
        stroke runs (its drags and release follow)."""
        services = self.services
        obj = self.obj
        if obj is None:
            return False
        self.settle()  # a press while the last stroke finishes: that one first
        surface, hit = self.hit(x, y)
        if hit is None:
            services.status("Paint: nothing of the object under the cursor")
            return False
        if self.brush.tool == brush_api.TOOL_PICK:
            return self._pick(surface, hit)
        self.end_preview()
        if hit.uv is None:
            services.status("Paint: this face has no UVs - it cannot be painted (UV check: SPACE)")
        self._stack_command = None
        if obj.paint is None:
            width, height = self.size()
            stack = PaintStack(width, height, (PaintLayer(FIRST_LAYER, None),))
            self._stack_command = PaintStackCommand(obj, None, stack, "Paint: new paint")
            obj.paint = stack
        layer = self.active_layer()
        spec = obj.paint.layers[layers_api.index_of(obj.paint, layer)]
        if not spec.visible:  # (a new stack's layer is visible)
            services.status(f"Paint: the layer {layer!r} is hidden - show it to paint on it")
            return False
        label = "Erase stroke" if self.brush.tool == brush_api.TOOL_ERASE else "Paint stroke"
        recorder = services.paint.begin_stroke(obj, layer, label)
        brush = self.brush
        self._stroke = brush_api.PaintStroke(recorder, brush)
        self._surface = surface
        self._image = alpha_api.resolve(brush.tip.alpha)
        self._radius = radius = self.radius()
        self._definition = self._mirror_definition()
        self._view_up = self._camera_up()
        spacing = brush.dynamics.spacing * 2.0 * radius
        screen = self._screen_radius(hit.point, radius)
        lo, hi = SAMPLE_STEP_PX
        self._step_px = min(max(brush.dynamics.spacing * 2.0 * screen, lo), hi)
        jump = max(2.0 * radius, 6.0 * self._step_px * radius / screen)  # a sample farther: a hit gap (silhouette)
        self._queue = dynamics_api.StrokeQueue(lambda o, d: surface.hit(o, d), spacing, jump,
                                               directed=self._image is not None, evaluate=self._evaluate,
                                               radius=radius)
        self._queue.add_ray(*self._ray(x, y))
        self._screen = (x, y)
        self._show_cursor(surface, hit)
        return True

    def step(self, x: float, y: float) -> None:
        """A drag event: its ray joins the stroke's path (sampled and evaluated in `frame`); the cursor follows."""
        queue = self._queue
        if queue is None or self._stroke is None or self.finishing or self._screen is None:
            return
        sx, sy = self._screen
        distance = math.hypot(x - sx, y - sy)
        if distance <= 0.0:
            return
        queue.add_ray(*self._ray(x, y), samples=max(1, math.ceil(distance / self._step_px)))
        self._screen = (x, y)
        hit = self._hit_on(self._surface, x, y)  # the stroke's surface: SubD and the view cannot change while it runs
        if hit is not None:
            self._show_cursor(self._surface, hit)

    def _evaluate(self, placement) -> None:
        texels, coverage, unique = stamp_api.evaluate(self._surface, placement, self._radius, self._stroke.settings,
                                                      self._definition, view_up=self._view_up, image=self._image)
        self._stroke.dab(texels, coverage, unique=unique)

    def frame(self) -> int:
        """Once per frame (`Application.update_viewport`): the running or finishing stroke's work within the frame
        budget; a finished stroke makes its History step. Returns the placements evaluated."""
        queue = self._queue
        if queue is None:
            return 0
        evaluated = queue.run(dynamics_api.frame_budget(queue, self.finishing))
        if self.finishing and queue.done:
            self._commit()
        return evaluated

    def end(self, x: float | None = None, y: float | None = None) -> bool:
        """The release: no evaluation here - the stroke is finishing; `frame` drains the rest and makes the History
        step."""
        if self._stroke is None or self._queue is None:
            return False
        self._queue.end_input()
        self.finishing = True
        return True

    def settle(self) -> bool:
        """A finishing stroke's rest evaluated now and its History step pushed (the rest is bounded); True = one was
        finishing."""
        if not self.finishing or self._queue is None:
            return False
        self._queue.run(None)
        self._commit()
        return True

    def _commit(self) -> bool:
        """The finished stroke: seams padded, one History step (with the new stack, if any)."""
        stroke, self._stroke = self._stroke, None
        self._queue = None
        self.finishing = False
        if stroke is None:
            return False
        services = self.services
        recorder = stroke.recorder
        surface = self._surface
        tiles = recorder.tiles
        if tiles:
            width, height = surface.width, surface.height
            boxes = [tile_box(tile, width, height) for tile in tiles]
            dst, src = seam_pad(surface.map, boxes, pad_width(width))
            if dst.size:
                rgba = services.paint.pixels(recorder.obj, recorder.name).reshape(-1, 4)
                recorder.write_texels(dst, rgba[src].copy())
        command = recorder.commit()
        self.last_dabs = stroke.dabs
        stack_command, self._stack_command = self._stack_command, None
        if command is None and stack_command is None:
            return False
        if command is None:
            recorder.obj.paint = stack_command.before  # nothing was painted: no stack either
            return False
        if stack_command is not None:
            command = CompositeCommand([stack_command, command], command.description)
        before = services.selection_snapshot()
        services.history.push(command)
        services.record_selection_history(before, mesh_step=False, focus=False)
        services.paint_display.finish(recorder.obj)
        services.status(f"{command.description}: {stroke.dabs} dab{'s' if stroke.dabs != 1 else ''}"
                        + (" (new paint, " + self._stack_text() + ")" if stack_command is not None else ""))
        return True

    def _stack_text(self) -> str:
        stack = self.obj.paint
        return f"{stack.width} x {stack.height}, layer {self.active_layer()!r}"

    def cancel_stroke(self) -> bool:
        stroke, self._stroke = self._stroke, None
        self._queue = None
        self.finishing = False
        if stroke is None:
            return False
        stroke.recorder.cancel()
        stack_command, self._stack_command = self._stack_command, None
        if stack_command is not None:
            stack_command.obj.paint = stack_command.before
        self.services.status("Paint stroke cancelled")
        return True

    def _pick(self, surface: PaintSurface, hit) -> bool:
        services = self.services
        if hit.uv is None:
            services.status("Pick: this face has no UVs")
            return False
        # the texel of the hit's own surface nearest to the hit (the UV square of the hit point can belong to another
        # island at an island's border)
        near, x = surface.footprint(hit.point, max(self.radius() * 0.25, 1e-9), hit.normal)
        texel = int(near[np.argmin(x)]) if near.size else surface.texel_of_uv(hit.uv)
        if texel < 0:
            services.status("Pick: the UV lies outside 0-1")
            return False
        colour = services.paint_display.colour_at(self.obj, texel) if self.obj.paint is not None else None
        if colour is None:
            colour = self._base_colour(texel)
        self.brush = self.brush.with_(colour=colour, tool=self._previous_tool)
        services.status(f"Pick: colour {tuple(round(c * 255) for c in colour)} - {brush_api.TOOL_LABELS[self.brush.tool]}")
        return False

    def _base_colour(self, texel: int) -> tuple[float, float, float]:
        from ..paint import files

        width, height = self.size()
        base = files.read_base(self.obj, width, height)
        if isinstance(base, np.ndarray):
            return tuple(float(c) / 255.0 for c in base.reshape(-1, 4)[texel][:3])
        return tuple(float(c) for c in base[:3])


def _rectangle(centre, t, b, radius: float, image) -> list[tuple]:
    """An alpha tip's cursor: its rectangle around `centre` spanned by `t` (width) and `b` (height), as segments."""
    hw, hh = image.half_extents
    c = np.asarray(centre, dtype=np.float64)
    corners = [tuple(float(v) for v in c + radius * (sx * hw * t + sy * hh * b))
               for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    return [(corners[i], corners[(i + 1) % 4]) for i in range(4)]
