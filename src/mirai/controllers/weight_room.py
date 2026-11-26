"""WeightRoomController (AD-041 §4, slice 2): the Weight Room's session in the slot, its brush and its strokes. Texts,
values and the cursor look `PROVISIONAL`; no key (W-1: the SPACE row "Gewichte malen" and the Bone panel open it).

The room is a configuration of the same window, like the Paint Room (AD-037): `Application.open_weight_room` saves the
display state it changes (the weight view `9`, the Soft preview) and restores it on close; pose, morph, gaze and SubD are
never reset (AD-038 R-1). While it is open one **exclusive session** runs (`WeightRoomSession`, owner "weight"):

- **LMB drag paints** the current bone's share on the *shown* cage (posed and morphed, `services.query_mesh`), with the
  brush of the panel: Add / Subtract / Replace / Smooth (`weight_paint.BrushWeightStroke`), radius, strength (flow),
  hardness, opacity, "nur zusammenhängend", "nur Vorderseite". The press starts a recording (`Mesh.begin_change`; the
  "Skin" layer is created inside it when absent), the drag's rays are sampled along the surface in world arc length
  (`paint.dynamics.StrokeQueue`, spacing `SPACING` of the brush diameter) and evaluated in `frame()` within the frame
  budget; the release drains the rest and pushes one `MeshDeltaCommand` - one `Strg+Z` per stroke. `Esc` rolls the
  running stroke back exactly. A stroke that wrote nothing leaves no step.
- **The stroke's surface is frozen at the press** (`PROVISIONAL`, a deviation from the slice-1 note "refresh() per dab
  while posed"): positions, ray hits and footprints of one stroke all come from the cage as it was at the press. While
  posed the skin stage moves the painted vertices at once (AD-028 F-5) - the jaw follows the paint - but the brush does
  not chase vertices it just moved; the next stroke sees the new pose surface. Path-independence of Add / Subtract /
  Replace within a stroke stays exact.
- **Bone choice** (W-5): the panel's list; a click (press and release without moving) on a bone line makes it current
  instead of painting; Ctrl+LMB on the surface makes the bone with the largest share at the nearest vertex current.
- **Wheel**: Shift+wheel = radius (the Soft radius steps of the Paint Room), Alt+wheel = strength (the Paint Room's
  opacity wheel, `paint` context); the plain wheel zooms. Orbit / pan / zoom stay free (Alt+LMB).
- **Symmetry**: with the edit mesh's symmetry on, a bone on the plane paints both sides at once - every footprint
  vertex's partner gets the same coverage (`max` of both sides, exactly symmetric). An off-centre bone is refused under
  symmetry until slice 4 brings L/R pairs (AD-028 §8.4, as the `7` / `8` gestures).
- **Refusals** (`paint_blocker`, shown in the HUD and the status line): no bone; the edit object follows a bone (linked);
  an off-centre bone under symmetry. The room still opens - the heatmap shows what is there.

**Allowed while the room is open** (`WEIGHT_ALLOWS`): Undo / Redo (one step per stroke; not while a stroke runs), Esc,
the views and display state, the SubD keys, the symmetry cycle, rest <-> pose (`6`, Alt+`6`) and the bone keys (next /
previous). Everything else is silent.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Optional

import numpy as np

from core import PointLayerInfo, SelectionMode
from core.mesh import LayerKind
from core.operations import MeshDeltaCommand, record_mesh_change

from ..interaction import commands
from ..interaction.input import PAINT_CONTEXT
from ..interaction.session import (
    PASS,
    SILENT,
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
from ..mesh_geometry import circle_segments, mesh_center_and_radius
from ..paint import dynamics as dynamics_api
from ..paint.brush import CURVE_ARRAYS, OPACITY_STEPS_PERCENT, RADIUS_STEPS_PERCENT
from ..skin_weights import CLEAN_THRESHOLD, clean_weights
from ..skinning import skin_layer
from ..subdivision import SUBD_COMMANDS
from ..symmetry import vertex_correspondence
from ..weight_heatmap import WeightHeat
from ..weight_paint import (
    OP_ADD,
    OPERATION_LABELS,
    OPERATIONS,
    BrushWeightStroke,
    CageRays,
    Footprint,
    VertexCloud,
    WeightBrushSettings,
    footprint,
)
from viewport.overlay import TOOL_MIRROR_DIM_LAYER, TOOL_PREVIEW_LAYER
from .services import AppServices

#: The skin layer's name (as `skeleton.SKIN_LAYER_NAME`; one per bound mesh, AD-028 §3.3).
SKIN_LAYER_NAME = "Skin"
#: Placement spacing in brush diameters (`PROVISIONAL`; the Paint Room's round tip uses 0.125).
SPACING = 0.25
#: The default radius step: 10 % of the edit object's bounding radius (`PROVISIONAL`; a footprint holds vertices, so a
#: low-poly cage needs a wider brush than the Paint Room's texels).
DEFAULT_RADIUS_STEP = RADIUS_STEPS_PERCENT.index(10.0)
#: A press on a bone line becomes a stroke once the pointer moved this far (px); released before: the bone is chosen.
CLICK_SLOP_PX = 4.0

#: What the room lets through (module docstring).
WEIGHT_ALLOWS = frozenset(
    {
        commands.CANCEL,
        commands.UNDO,
        commands.REDO,
        commands.TOGGLE_ORTHO,
        commands.SYMMETRY_CYCLE,
        commands.SOFT_RADIUS_UP,
        commands.SOFT_RADIUS_DOWN,
        commands.POSE_TOGGLE_REST,
        commands.POSE_RESET_BONE,
        commands.BONE_NEXT,
        commands.BONE_PREVIOUS,
        *commands.DISPLAY_COMMANDS,
        *commands.LOOK_COMMANDS,
        *SUBD_COMMANDS,
    }
)
#: Refused while a stroke runs: History steps, the plane the mirrored dab reads, the pose, the bone, the shown surface.
_NOT_WHILE_STROKING = frozenset(
    {commands.UNDO, commands.REDO, commands.SYMMETRY_CYCLE, commands.POSE_TOGGLE_REST, commands.POSE_RESET_BONE,
     commands.BONE_NEXT, commands.BONE_PREVIOUS, *SUBD_COMMANDS}
)


@dataclasses.dataclass(frozen=True)
class WeightRoomBrush:
    """The room's brush (view state: not saved, no Undo; the panel and the wheel change it). `radius_step` indexes
    `paint.brush.RADIUS_STEPS_PERCENT` (percent of the edit object's bounding radius); `flow` is the strength."""

    operation: str = OP_ADD
    radius_step: int = DEFAULT_RADIUS_STEP
    flow: float = 0.5
    opacity: float = 1.0
    hardness: float = 0.0
    curve: str = "smooth"
    value: float = 1.0
    connected: bool = True
    front_only: bool = False

    def __post_init__(self) -> None:
        if self.operation not in OPERATIONS:
            raise ValueError(f"unknown weight brush operation: {self.operation!r}")
        if self.curve not in CURVE_ARRAYS:
            raise ValueError(f"unknown falloff curve: {self.curve!r}")
        if not 0 <= self.radius_step < len(RADIUS_STEPS_PERCENT):
            raise ValueError(f"radius step out of range: {self.radius_step}")
        for name in ("flow", "opacity", "hardness", "value"):
            x = getattr(self, name)
            if not (isinstance(x, (int, float)) and math.isfinite(x) and 0.0 <= x <= 1.0):
                raise ValueError(f"{name} lies in [0, 1]: {x!r}")

    @property
    def radius_percent(self) -> float:
        return RADIUS_STEPS_PERCENT[self.radius_step]

    def world_radius(self, bounding_radius: float) -> float:
        return bounding_radius * self.radius_percent / 100.0

    def with_(self, **changes) -> "WeightRoomBrush":
        for name in ("flow", "opacity", "hardness", "value"):
            if name in changes:
                changes[name] = float(min(max(changes[name], 0.0), 1.0))
        if "radius_step" in changes:
            changes["radius_step"] = max(0, min(int(changes["radius_step"]), len(RADIUS_STEPS_PERCENT) - 1))
        return dataclasses.replace(self, **changes)

    def with_flow_step(self, step: int) -> "WeightRoomBrush":
        """The strength one step of `OPACITY_STEPS_PERCENT` up (+1) or down (-1) from the current value."""
        steps = [p / 100.0 for p in OPACITY_STEPS_PERCENT]
        current = self.flow
        if step > 0:
            higher = [s for s in steps if s > current + 1e-9]
            return self.with_(flow=higher[0] if higher else steps[-1])
        lower = [s for s in steps if s < current - 1e-9]
        return self.with_(flow=lower[-1] if lower else steps[0])

    def settings(self, bounding_radius: float) -> WeightBrushSettings:
        return WeightBrushSettings(
            operation=self.operation, radius=max(self.world_radius(bounding_radius), 1e-12), flow=self.flow,
            opacity=self.opacity, hardness=self.hardness, curve=self.curve, value=self.value,
            connected=self.connected, front_only=self.front_only,
        )

    def label(self) -> str:
        op = OPERATION_LABELS[self.operation]
        if self.operation == "replace":
            op += f" {self.value:.2f}"
        return op

    def status_text(self) -> str:
        return (f"Weight Room: {self.label()}, Radius {self.radius_percent:g} %, Stärke {self.flow * 100:.0f} %,"
                f" Deckkraft {self.opacity * 100:.0f} %, Härte {self.hardness * 100:.0f} %")



class WeightRoomSession:
    """The room's session in the slot (module docstring)."""

    owner = "weight"
    label = "Weight Room"
    exclusive = True

    def __init__(self, controller: "WeightRoomController") -> None:
        self._controller = controller
        #: the room's own LMB press is down (its drags and its release are the room's)
        self.pressed = False
        #: a stroke runs
        self.stroking = False
        #: a plain press on a bone line, waiting: (x, y, bone) - a release chooses the bone, a drag starts the stroke
        self.pending: Optional[tuple] = None

    def grabs(self, event) -> bool:
        if isinstance(event, Press):
            return (event.input.kind == "mouse" and event.input.value == "LEFT" and not self.pressed
                    and event.input.modifiers in (frozenset(), frozenset({"ctrl"})))
        if isinstance(event, Drag):
            return event.command is None and self.pressed
        if isinstance(event, Release):
            return event.raw and self.pressed and event.button == "LEFT"
        if isinstance(event, Wheel):
            return event.command != commands.ZOOM  # zoom stays navigation
        if isinstance(event, KeyPress):
            return self._controller.services.bindings.command_for(event.input) == commands.CANCEL
        return isinstance(event, (Motion, Hover, Leave, Modifiers))

    def allows(self, command: str, ctx: RunContext) -> Optional[Refusal]:
        if command not in WEIGHT_ALLOWS:
            return SILENT
        if command in _NOT_WHILE_STROKING and self.stroking:
            return SILENT
        return None

    def handle(self, event) -> Outcome:
        if not self.grabs(event):
            return PASS
        controller = self._controller
        if isinstance(event, Press):
            x, y = (event.x, event.y) if event.x is not None else controller.services.cursor or (None, None)
            self.pressed = True
            if x is None:
                return True
            if event.input.modifiers:  # Ctrl+LMB: the bone with the largest share under the cursor
                controller.pick_dominant(x, y)
                return True
            bone = controller.bone_line_at(x, y)
            if bone is not None:
                self.pending = (x, y, bone)
                return True
            self.stroking = controller.begin(x, y)
            return True
        if isinstance(event, Drag):
            cursor = controller.services.cursor
            if cursor is None:
                return True
            if self.pending is not None:
                x, y, _ = self.pending
                if math.hypot(cursor[0] - x, cursor[1] - y) < CLICK_SLOP_PX:
                    return True
                self.pending = None
                self.stroking = controller.begin(x, y)
            if self.stroking:
                controller.step(*cursor)
            return True
        if isinstance(event, Release):
            self.pressed = False
            if self.pending is not None:
                _, _, bone = self.pending
                self.pending = None
                return controller.choose_bone(bone)
            if not self.stroking:
                return False
            self.stroking = False
            return controller.end()
        if isinstance(event, Wheel):
            return controller.wheel(event.input, event.command)
        if isinstance(event, KeyPress):
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
        """Esc: a running stroke is rolled back exactly (no History step); without one nothing happens."""
        self.pending = None
        if not self.stroking:
            return False
        self.stroking = False  # the press stays the room's until its release (no new stroke starts on it)
        return self._controller.cancel_stroke()

    def commit(self) -> bool:
        return False


class WeightRoomController:
    def __init__(self, services: AppServices, skeleton) -> None:
        self.services = services
        self.skeleton = skeleton
        self.brush = WeightRoomBrush()
        #: the heatmap model (the app hands it to the shading sink while the room is open)
        self.heat = WeightHeat()
        self.session: WeightRoomSession | None = None
        #: the display state the room restores when it closes (`Application`'s)
        self.saved_view: dict | None = None
        self.obj = None
        self._bounding_radius = 1.0
        # the running stroke
        self._stroke: BrushWeightStroke | None = None
        self._before = None
        self._selection_before = None
        self._queue: dynamics_api.StrokeQueue | None = None
        self._cloud: VertexCloud | None = None
        self._rays: CageRays | None = None
        self._settings: WeightBrushSettings | None = None
        self._partners: dict = {}
        self._toward: np.ndarray | None = None
        self._written = 0
        self._touched = 0  # footprint vertices of the stroke (0: the brush caught no vertex - too small for the cage)
        self._screen = None
        self._step_px = 2.0
        # the hover's surface (rebuilt when the shown cage or the heat's topology changed)
        self._hover_key = None
        self._hover_watch = None
        self._hover_cloud: VertexCloud | None = None
        self._hover_rays: CageRays | None = None
        #: dabs of the last stroke and of all strokes (tests, the probe)
        self.last_dabs = 0

    @property
    def stroking(self) -> bool:
        return self._stroke is not None

    # -- the room -------------------------------------------------------------------------------------------------

    def start(self, obj, saved_view: dict) -> None:
        """The room opened on `obj` (`Application.open_weight_room` checked it): the session starts, the heatmap shows."""
        self.obj = obj
        self.saved_view = saved_view
        _, radius = mesh_center_and_radius(obj.mesh)
        self._bounding_radius = radius or 1.0
        self.session = WeightRoomSession(self)
        self.services.interaction.start(self.session)
        self.show_heat()

    def stop(self) -> dict | None:
        """The room closes: a running stroke is rolled back, the session ends; returns the display state to restore."""
        if self.session is None:
            return None
        if self.session.stroking:
            self.session.cancel()
        self.services.interaction.end(self.session)
        self.session = None
        self.clear_cursor()
        self.heat.close()
        self._drop_hover()
        self.obj = None
        saved, self.saved_view = self.saved_view, None
        return saved

    def show_heat(self) -> None:
        """The heatmap's target now: the edit mesh, its skin layer, the current bone, the hidden faces (cheap when
        unchanged; once per frame from `Application.update_viewport`)."""
        if self.session is None:
            return
        services = self.services
        mesh = services.scene.mesh
        self.heat.show(mesh, skin_layer(mesh), self.skeleton.current_bone, services.hidden_faces())

    # -- what may be painted ----------------------------------------------------------------------------------------

    def paint_blocker(self) -> Optional[str]:
        """Why a stroke would be refused now (None = it can paint): no bone, a linked edit object, an off-centre bone
        under symmetry (slice 4 lifts the last one with L/R pairs)."""
        skeleton = self.skeleton
        bone = skeleton.current_bone
        if bone is None:
            return "kein Knochen – im Bone-Panel eine Kette starten"
        edit = self.services.scene.edit_object
        if edit.bone is not None:
            return (f"{edit.name!r} folgt dem Knochen {skeleton.bone_name(edit.bone)!r} – ein Teil folgt einem Knochen"
                    f" oder hat Gewichte, nicht beides (im Bone-Panel lösen)")
        definition = self.services.scene.mesh.symmetry_definition
        if definition is not None and not skeleton.bone_on_plane(bone, definition):
            return (f"{skeleton.bone_name(bone)!r} liegt nicht auf der Symmetrie-Ebene – braucht einen Spiegel-Knochen"
                    f" (kommt mit den L/R-Paaren); Shift+S schaltet Symmetrie aus")
        return None

    def hud_text(self) -> str:
        """The HUD's entry: "Weight Room · <bone> · <operation>" (or the reason it cannot paint)."""
        bone = self.skeleton.current_bone
        name = self.skeleton.bone_name(bone) if bone is not None else "kein Knochen"
        blocker = self.paint_blocker()
        text = f"Weight Room · {name} · {self.brush.label()}"
        return text if blocker is None or bone is None else f"{text} · gesperrt"

    # -- brush settings ---------------------------------------------------------------------------------------------

    def set_brush(self, **changes) -> bool:
        before = self.brush
        self.brush = before.with_(**changes)
        if self.brush != before:
            self.services.status(self.brush.status_text())
            self._redraw_cursor()
        return self.brush != before

    def wheel(self, input, command) -> bool:
        if command in (commands.SOFT_RADIUS_UP, commands.SOFT_RADIUS_DOWN):
            step = self.brush.radius_step + (1 if command == commands.SOFT_RADIUS_UP else -1)
            return self.set_brush(radius_step=step) or self._at_end()
        paint = self.services.bindings.command_for(input, PAINT_CONTEXT)
        if paint in (commands.PAINT_OPACITY_UP, commands.PAINT_OPACITY_DOWN):
            stepped = self.brush.with_flow_step(1 if paint == commands.PAINT_OPACITY_UP else -1)
            return self.set_brush(flow=stepped.flow) or self._at_end()
        return False  # zoom and the other wheel commands: the app's path (`pointer_scroll`)

    def _at_end(self) -> bool:
        self.services.status(self.brush.status_text())
        return False

    def radius(self) -> float:
        return self.brush.world_radius(self._bounding_radius)

    # -- the surface ------------------------------------------------------------------------------------------------

    def _surface(self) -> tuple[VertexCloud, CageRays]:
        """The shown cage's positions and its ray hit, matching the heatmap's rows and triangles (built at a press;
        reused by the hover while nothing changed)."""
        services = self.services
        shown = services.query_mesh  # the shown cage, brought up to date; else the edit mesh
        self.show_heat()
        self.heat.refresh()
        key = (id(shown), self.heat.topology_revision, self.heat.position_revision)
        watch = self._hover_watch
        moved = watch is not None and (lambda c: bool(c.vertices or c.edges or c.faces))(watch.peek())
        if key != self._hover_key or watch is None or moved:  # (a weight write alone keeps the surface)
            if watch is not None:
                watch.close()
            self._hover_watch = shown.watch()
            cloud = VertexCloud(shown)
            self._hover_cloud = cloud
            self._hover_rays = CageRays(cloud.P, self.heat.tris, self.heat.tri_face)
            self._hover_key = key
        return self._hover_cloud, self._hover_rays

    def _drop_hover(self) -> None:
        if self._hover_watch is not None:
            self._hover_watch.close()
        self._hover_watch = self._hover_key = self._hover_cloud = self._hover_rays = None

    def _ray(self, x: float, y: float):
        width, height = self.services.viewport_size
        return self.services.edit_camera.screen_to_ray(x, y, width, height)

    def hit(self, x: float, y: float):
        _, rays = self._surface()
        return rays.hit(*self._ray(x, y))

    # -- the cursor -------------------------------------------------------------------------------------------------

    def hover(self, x: float, y: float) -> None:
        if self.session is None:
            return
        self._show_cursor(self.hit(x, y))

    def _redraw_cursor(self) -> None:
        cursor = self.services.cursor
        if self.session is not None and cursor is not None and not self.stroking:
            self.hover(*cursor)

    def _show_cursor(self, hit) -> None:
        viewport = self.services.viewport
        if viewport is None:
            return
        if hit is None:
            viewport.set_tool_overlay()
            return
        radius = self.radius()
        segments = {TOOL_PREVIEW_LAYER: circle_segments(tuple(hit.point), tuple(hit.normal), radius)}
        definition = self._mirror_definition()
        if definition is not None:
            point, normal = _mirror(definition, hit.point, hit.normal)
            segments[TOOL_MIRROR_DIM_LAYER] = circle_segments(tuple(point), tuple(normal), radius)
        viewport.set_tool_overlay(segments=segments)

    def clear_cursor(self) -> None:
        viewport = self.services.viewport
        if viewport is not None:
            viewport.set_tool_overlay()

    def _mirror_definition(self):
        """The plane the stroke mirrors across (the edit mesh's symmetry, a bone on the plane), else None."""
        definition = self.services.scene.mesh.symmetry_definition
        if definition is None or self.paint_blocker() is not None:
            return None
        return definition

    # -- bone choice (W-5) ------------------------------------------------------------------------------------------

    def bone_line_at(self, x: float, y: float):
        """The bone line under a plain click (`skeleton.bone_at`), None if none is near."""
        return self.skeleton.bone_at(x, y)

    def choose_bone(self, bone) -> bool:
        skeleton = self.skeleton
        if not skeleton.select(bone):
            self.services.status(f"Weight Room: {skeleton.bone_name(bone)!r} ist schon der aktuelle Knochen")
            return False
        self.show_heat()
        self.services.status(f"Weight Room: Knochen {skeleton.bone_name(bone)!r}")
        return True

    def pick_dominant(self, x: float, y: float) -> bool:
        """Ctrl+LMB (W-5): the bone with the largest share at the vertex of the hit face nearest to the hit becomes
        current. A vertex with only the object's share chooses nothing."""
        services = self.services
        cloud, rays = self._surface()
        hit = rays.hit(*self._ray(x, y))
        if hit is None:
            services.status("Weight Room: nichts vom Objekt unter dem Cursor")
            return False
        mesh = services.scene.mesh
        lid = skin_layer(mesh)
        corners = mesh.face_vertices(hit.face)
        nearest = min(corners, key=lambda v: float(np.sum((cloud.position(v) - hit.point) ** 2)))
        value = mesh.layer_value(lid, nearest) if lid is not None else ()
        rig = services.scene.rig
        shown = [(w, k) for k, w in value if rig is not None and rig.has_bone(k)]
        if not shown:
            services.status("Weight Room: dieser Punkt hängt an keinem Knochen (nur am Objekt)")
            return False
        w, bone = max(shown)
        self.skeleton.select(bone)
        self.show_heat()
        services.status(f"Weight Room: Knochen {self.skeleton.bone_name(bone)!r} (Anteil {w:.2f} an diesem Punkt)")
        return True

    # -- strokes ----------------------------------------------------------------------------------------------------

    def _screen_radius(self, point, radius: float) -> float:
        camera = self.services.edit_camera
        width, height = self.services.viewport_size
        _, right, _ = camera.basis()
        a = camera.project_to_screen(tuple(point), width, height)
        b = camera.project_to_screen(tuple(np.asarray(point) + radius * np.asarray(right)), width, height)
        if a is None or b is None:
            return 8.0
        return max(1.0, math.hypot(b[0] - a[0], b[1] - a[1]))

    def begin(self, x: float, y: float) -> bool:
        """The press: the stroke's recording starts and its first ray is queued (evaluated in `frame`). True = a stroke
        runs (its drags and release follow)."""
        services = self.services
        if self.obj is None:
            return False
        blocker = self.paint_blocker()
        if blocker is not None:
            services.status(f"Weight Room: {blocker}")
            return False
        cloud, rays = self._surface()
        origin, direction = self._ray(x, y)
        hit = rays.hit(origin, direction)
        if hit is None:
            services.status("Weight Room: nichts vom Objekt unter dem Cursor")
            return False
        mesh = services.scene.mesh
        bone = self.skeleton.current_bone
        self._selection_before = services.selection_snapshot()
        self._before = mesh.begin_change()
        lid = skin_layer(mesh)
        if lid is None:
            lid = mesh.add_point_layer(PointLayerInfo(SKIN_LAYER_NAME, LayerKind.WEIGHTS))
        brush = self.brush
        radius = self.radius()
        self._settings = settings = brush.settings(self._bounding_radius)
        self._stroke = BrushWeightStroke(mesh, lid, bone, services.scene.rig, settings)
        self._cloud, self._rays = cloud, rays
        self._partners = {}
        if self._mirror_definition() is not None:
            self._partners = {v: c.partner for v, c in vertex_correspondence(mesh).items()
                              if getattr(c, "partner", None) is not None}
        camera = services.edit_camera
        eye = np.asarray(camera.eye(), dtype=np.float64)
        self._toward = eye - hit.point  # "front only": from the surface to the eye (perspective at the press)
        self._written = 0
        self._touched = 0
        spacing = SPACING * 2.0 * radius
        screen = self._screen_radius(hit.point, radius)
        self._step_px = min(max(SPACING * 2.0 * screen, 2.0), 6.0)
        jump = max(2.0 * radius, 6.0 * self._step_px * radius / screen)
        self._queue = dynamics_api.StrokeQueue(lambda o, d: rays.hit(o, d), spacing, jump, directed=False,
                                               evaluate=self._evaluate, radius=radius)
        self._queue.add_ray(origin, direction)
        self._screen = (x, y)
        self._show_cursor(hit)
        return True

    def step(self, x: float, y: float) -> None:
        """A drag event: its ray joins the stroke's path (sampled and evaluated in `frame`); the cursor follows."""
        queue = self._queue
        if queue is None or self._screen is None:
            return
        sx, sy = self._screen
        distance = math.hypot(x - sx, y - sy)
        if distance <= 0.0:
            return
        origin, direction = self._ray(x, y)
        queue.add_ray(origin, direction, samples=max(1, math.ceil(distance / self._step_px)))
        self._screen = (x, y)
        hit = self._rays.hit(origin, direction)
        if hit is not None:
            self._show_cursor(hit)

    def _evaluate(self, placement) -> None:
        fp = footprint(self._cloud, placement.point, self._settings, toward_viewer=self._toward)
        if self._partners and len(fp):
            fp = _mirrored(fp, self._partners)
        if not len(fp):
            return
        self._touched += len(fp)
        mask = self.services.mask_values(fp.vertices)
        self._written += len(self._stroke.dab(fp, mask))

    def frame(self) -> int:
        """Once per frame (`Application.update_viewport`): the running stroke's placements within the frame budget."""
        queue = self._queue
        if queue is None:
            return 0
        return queue.run(dynamics_api.frame_budget(queue, False))

    def end(self) -> bool:
        """The release: the rest of the path is evaluated now and the stroke becomes one History step (nothing
        written: no step)."""
        stroke, queue = self._stroke, self._queue
        if stroke is None or queue is None:
            return False
        queue.end_input()
        queue.run(None)
        services = self.services
        mesh = stroke.mesh
        before = self._clear()
        self.last_dabs = stroke.dabs
        name = self.skeleton.bone_name(stroke.bone)
        if not self._written:
            mesh.rollback_change(before)
            why = "nichts geändert" if self._touched else (
                "der Pinsel hat keinen Punkt erreicht – größer machen (Shift+Rad), er wirkt auf Punkte, nicht auf Flächen")
            services.status(f"Weight Room: {self.brush.label()} {name!r} – {why}")
            return False
        delta = mesh.end_change(before)
        description = f"Weight stroke {OPERATION_LABELS[stroke.settings.operation]} {name!r}"
        services.history.push(MeshDeltaCommand(mesh=mesh, delta=delta, description=description))
        services.record_selection_history(self._selection_before, mesh_step=False, focus=False)
        services.status(f"Weight Room: {self.brush.label()} {name!r} – {stroke.dabs} Tupfer, {len(stroke.press)}"
                        f" Punkte (Strg+Z nimmt den Strich zurück)")
        return True

    def cancel_stroke(self) -> bool:
        stroke = self._stroke
        if stroke is None:
            return False
        before = self._clear()
        stroke.mesh.rollback_change(before)
        self.services.status("Weight Room: Strich abgebrochen")
        return True

    def _clear(self):
        before = self._before
        self._stroke = self._queue = self._before = None
        self._settings = None
        self._partners = {}
        self._screen = None
        return before

    # -- "Aufräumen" (W-9) ------------------------------------------------------------------------------------------

    def clean(self, threshold: float = CLEAN_THRESHOLD) -> bool:
        """Every share below `threshold` to 0 by the write rule, all bones, the whole edit mesh - one Undo step;
        masked vertices keep theirs (`skin_weights.clean_weights`)."""
        services = self.services
        label = "Aufräumen"
        if self.stroking:
            services.status(f"{label}: nicht während eines Strichs")
            return False
        owner = services.interaction_owner
        if owner is not None and owner != "weight":
            services.status(f"{label}: not while the {owner} interaction runs")
            return False
        if services.selection.mode is SelectionMode.OBJECT:
            services.status(f"{label}: in 1/2/3")
            return False
        mesh = services.scene.mesh
        lid = skin_layer(mesh)
        rig = services.scene.rig
        if lid is None or rig is None:
            services.status(f"{label}: {services.scene.edit_object.name!r} hat keine Gewichte")
            return False
        threshold = float(threshold)
        if not 0.0 < threshold <= 1.0:
            services.status(f"{label}: Schwelle zwischen 0 und 1")
            return False
        mask = services.mask_values(mesh.all_vertex_ids())
        before = services.selection_snapshot()
        delta, count = record_mesh_change(mesh, lambda: clean_weights(mesh, lid, rig, threshold, mask))
        if not count:
            services.status(f"{label}: kein Anteil unter {threshold:g}")
            return False
        services.history.push(MeshDeltaCommand(mesh=mesh, delta=delta, description=f"Clean weights < {threshold:g}"))
        services.record_selection_history(before, mesh_step=False, focus=False)
        services.status(f"{label}: {count} Punkt{'e' if count != 1 else ''} bereinigt (Anteile unter {threshold:g};"
                        f" Strg+Z nimmt es zurück)")
        return True


def _mirror(definition, point, normal) -> tuple[np.ndarray, np.ndarray]:
    from ..paint.surface import mirror

    return mirror(definition, point, normal)


def _mirrored(fp: Footprint, partners: dict) -> Footprint:
    """The footprint and its mirror image as one: every vertex gets the larger coverage of itself and its partner, so
    the dab is exactly symmetric (module docstring)."""
    cover = dict(zip(fp.vertices, fp.coverage.tolist()))
    for v, c in list(cover.items()):
        p = partners.get(v)
        if p is not None and cover.get(p, 0.0) < c:
            cover[p] = c
    vertices = tuple(cover)
    return Footprint(vertices, np.fromiter(cover.values(), dtype=np.float64, count=len(vertices)))


__all__ = ["WEIGHT_ALLOWS", "WeightRoomBrush", "WeightRoomController", "WeightRoomSession"]
