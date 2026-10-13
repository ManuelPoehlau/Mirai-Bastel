"""State machine of the Mehlsack Lab (pyglet-free, GL-free; precedent `subdivision_lab/lab_state.py`).

Everything a key or wheel event changes and everything the HUD shows lives here, so the
whole interaction is testable without a window. The window resolves nothing itself: it
hands raw names (`"X"`, `{"ctrl"}`, scroll values) to `key()` / `key_release()` / `wheel()`,
keeps `hover_target` current, hands the LMB drag's target and world deltas to
`begin_drag()` / `drag_step()` and the mouse motion of a held W/E/R to `hold_motion()`, and
reacts to the returned `Outcome` (rebuild the box, resync the mesh, re-pick the hover,
zoom, quit).

Hold gestures (Slice 2b E16, AD-016 hold-key-hover with the hover target): `W`/`E`/`R`
down arms Move/Rotate/Scale on the target hovered at that moment (frozen); the first
non-zero mouse motion begins the gesture — constraint, weights and formula are read
there, as `Application._transform_step` reads them at `begin()`; release commits;
`Esc`/RMB cancels; a tap without motion does nothing. A second hold key while one is held
is ignored. Undo/Redo while a gesture runs is ignored; while only armed it disarms first.

Mapping (E17): read from `RotateTool` / `ScaleTool` (no copied numbers), pixels accumulated
like the tools (chunking-independent): Rotate `θ = RADIANS_PER_PIXEL · Σdx` about the view
axis at `begin()` or `_resolve_space(space, for_rotation=True)`; Scale
`F = max(MIN_SCALE, 1 + SCALE_PER_PIXEL · Σ(dx + dy))`, uniform or masked by
`_resolve_space(space)`; Move as the LMB drag (image-plane delta at the anchor seed, masked).

Constraint (E18, B4.1): one sticky state for X/Y/Z and Shift+X/Y/Z (Shift+X = "yz" …);
same key again = off, another replaces; read at `begin()`, fixed for the gesture.

Selection (Slice 3, E23–E31): a Core `Selection` (never in the History), changed by
`click()` (the window picks the hit with `pick_component`), `1`/`2`/`3` (mode; clears it like
the app) and Shift+L / Shift+R (add the hovered edge's Loop / Ring, `lab_selection`). Target
rule E26: `active_target` is the selection's target when it resolves to vertices, else the
hover target — W/E/R arm on it, the LMB drag takes it (`gesture_target`). A selection change
never ends Nachführen (E30: it changes no geometry); Undo/Redo keep the selection, a new box
clears it; while a gesture is armed, running or an LMB press is undecided (`busy`), selection
input is ignored (E31).

Slice 3b (Manu 2026-10-13): the hover is the component under the cursor (`hover_target` is
then a `component_target`); `L` switches the Loop/Ring mode on/off, where hover and clicks
take whole Loops/Rings (`click_loop`). A double click on the mesh (`double_click`, detected by
the window) selects an edge's loop, Shift+double click a loop section from the previous
click's edge or the face loop towards the neighbouring face (`_prev_anchor` = the handle of
the click before the double click). Shift+`1`/`2`/`3` convert the selection (touching).

Phases: `create` (wheel builds the box, `Enter` commits) → `edit` (Loop/Ring drag).
Settings are sticky and survive gestures, Undo and a new box: Loop/Ring mode, axis,
radius step, metric, curve, bands, preview, Nachführen. Defaults: geodesic, Smooth, 15 %
(Artist 2026-10-11, AD-020 E5); Nachführen on (handoff E7); surface preview off (Slice 2a A9).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from core import Selection, SelectionMode
from mirai.interaction.tools.rotate import RotateTool
from mirai.interaction.tools.scale import ScaleTool
from mirai.interaction.tools.transform import _resolve_space
from mirai.soft_selection import METRICS
from mirai.soft_selection.settings import (
    DEFAULT_METRIC,
    DEFAULT_RADIUS_STEP,
    RADIUS_STEPS_PERCENT,
)

from . import lab_bindings as lb
from .box import BoxParams, box_rims, build_box_mesh
from .edit_session import KIND_LABELS, MOVE, ROTATE, SCALE, EditSession
from .lab_selection import (
    MODE_NAMES,
    add_loop_ring,
    apply_click,
    apply_click_elements,
    convert_selection,
    face_loop,
    loop_elements,
    loop_segment,
    selection_target,
)
from .signed_curve import DEFAULT_CURVE, PRESET_HAT, PRESET_SMOOTH, SignedCurve
from .signed_ops import SCALE_FORMULAS, collapsed_count
from .targets import MODE_LABELS, MODE_LOOP, MODE_RING, Target

# Outcome effects (what the window has to do after an event)
BOX_CHANGED = "box_changed"          # creation phase: rebuild the preview mesh
PHASE_CHANGED = "phase_changed"      # new mesh / new phase: rebuild scene objects
MESH_CHANGED = "mesh_changed"        # positions changed (`Outcome.changed`): resync, re-pick hover
REPICK = "repick"                    # positions may differ from the last pick (drag release)
GESTURE_BEGAN = "gesture_began"      # a hold gesture began: show its weights
PREVIEW_CHANGED = "preview_changed"  # mode/radius/metric/curve: recompute hover target + bands
DISPLAY_CHANGED = "display_changed"  # bands/preview visibility, help, HUD text only
SELECTION_CHANGED = "selection_changed"  # the selection overlay must be rebuilt
QUIT = "quit"

FRAME_EMA = 0.1

#: Constraint keys → `space` strings of `_resolve_space` (Shift+axis excludes that axis, B4.1).
_SPACES = {lb.AXIS_X: "x", lb.AXIS_Y: "y", lb.AXIS_Z: "z",
           lb.PLANE_YZ: "yz", lb.PLANE_XZ: "xz", lb.PLANE_XY: "xy"}
_SPACE_LABELS = {None: "frei", "x": "X", "y": "Y", "z": "Z",
                 "yz": "Ebene YZ", "xz": "Ebene XZ", "xy": "Ebene XY"}
_PRESETS = {lb.PRESET_1: PRESET_SMOOTH, lb.PRESET_2: PRESET_HAT}
_SELECTION_MODES = {lb.MODE_VERTEX: SelectionMode.VERTEX, lb.MODE_EDGE: SelectionMode.EDGE,
                    lb.MODE_FACE: SelectionMode.FACE, lb.CONVERT_VERTEX: SelectionMode.VERTEX,
                    lb.CONVERT_EDGE: SelectionMode.EDGE, lb.CONVERT_FACE: SelectionMode.FACE}
#: PROVISIONAL default Scale formula: the app's (`SoftScaleOperation` default).
DEFAULT_SCALE_FORMULA = "linear"


def space_mask(space: Optional[str]) -> tuple[float, float, float]:
    """Move/Scale mask of a constraint space: all axes free, or `_resolve_space(space)`."""
    return (1.0, 1.0, 1.0) if space is None else _resolve_space(space, for_rotation=False)


@dataclass
class Hold:
    """An armed W/E/R (E16): the target frozen at the key press; `begun` after the first
    motion; the tool-like pixel accumulation."""

    key: str
    kind: str
    target: Target
    begun: bool = False
    space: Optional[str] = None
    axis: Optional[tuple] = None
    mask: tuple = (1.0, 1.0, 1.0)
    pixels: float = 0.0
    applied: float = 0.0


@dataclass
class Outcome:
    effects: set = field(default_factory=set)
    #: Zoom notches for the camera (edit phase wheel).
    zoom_steps: int = 0
    #: With MESH_CHANGED: the vertices whose positions changed (None = possibly all).
    changed: Optional[set] = None
    action: Optional[str] = None

    def __contains__(self, effect: str) -> bool:
        return effect in self.effects


@dataclass(frozen=True)
class HudLine:
    text: str
    #: "title" | "normal" | "active" | "inactive" | "warning" (colours live in the window)
    style: str


class LabState:
    def __init__(self, box: Optional[BoxParams] = None) -> None:
        self.phase = lb.PHASE_CREATE
        self.box = box if box is not None else BoxParams()
        self.session: Optional[EditSession] = None
        self.mode = MODE_LOOP
        #: Sticky constraint space: None, "x"/"y"/"z" or a plane "yz"/"xz"/"xy" (E18).
        self.axis: Optional[str] = None
        self.scale_formula = DEFAULT_SCALE_FORMULA
        #: The window keeps this current (the hover target W/E/R arm on).
        self.hover_target: Optional[Target] = None
        self.hold: Optional[Hold] = None
        #: Slice 3: the Core selection (E23; mode sticky like the other settings, Core default).
        self.selection = Selection()
        #: The window sets this while an LMB press is still undecided (click or drag, E24).
        self.pointer_pending = False
        #: Slice 3b: Loop/Ring mode (`L`, O13) — off: the hover is the component under the cursor.
        self.loop_mode = False
        #: The window may set the edge under the cursor for one Shift+L/R (Vertex/Face hover).
        self.edge_under_cursor = None
        #: Handles of the last and the previous click (Shift+double click, Slice 3b).
        self._anchor = None
        self._prev_anchor = None
        #: Linear Scale: vertices with g <= 0 in the running / last Scale gesture (E20).
        self.collapsed: Optional[int] = None
        self.radius_step = DEFAULT_RADIUS_STEP
        self.metric = DEFAULT_METRIC
        self.curve: SignedCurve = DEFAULT_CURVE
        self.bands_visible = True
        self.preview_visible = False
        self.nachfuehren = True
        self.help_visible = False
        self.confirm_new_box = False
        self.note: Optional[str] = None
        #: Timings for the HUD (ms): last hover update, last drag step, last Nachführen.
        self.hover_ms: Optional[float] = None
        self.drag_ms: Optional[float] = None
        self.retune_ms: Optional[float] = None
        self.gl_version = "?"
        self.gl_renderer = "?"
        #: Bumped on every change a HUD line depends on (frame time aside).
        self.revision = 0

    def _touch(self) -> None:
        self.revision += 1

    # -- derived ------------------------------------------------------------------------

    @property
    def dragging(self) -> bool:
        return self.session is not None and self.session.dragging

    @property
    def radius_percent(self) -> int:
        return RADIUS_STEPS_PERCENT[self.radius_step]

    @property
    def world_radius(self) -> float:
        return 0.0 if self.session is None else self.session.world_radius(self.radius_step)

    @property
    def armed(self) -> bool:
        return self.hold is not None

    @property
    def busy(self) -> bool:
        """A gesture is armed or running, or an LMB press is undecided (E31)."""
        return self.dragging or self.hold is not None or self.pointer_pending

    @property
    def selection_target(self) -> Optional[Target]:
        if self.session is None:
            return None
        return selection_target(self.session.mesh, self.selection)

    @property
    def active_target(self) -> Optional[Target]:
        """E26: the selection's target when it resolves to vertices, else the hover target."""
        target = self.selection_target
        return target if target is not None else self.hover_target

    def gesture_target(self, over_mesh: bool) -> Optional[Target]:
        """The target of an LMB drag pressed now: with a selection only when pressed over the
        mesh (E26), without one the hover target exactly as before."""
        target = self.selection_target
        if target is not None:
            return target if over_mesh else None
        return self.hover_target

    @property
    def axis_mask(self) -> tuple[float, float, float]:
        return space_mask(self.axis)

    def masked(self, delta, mask=None) -> tuple[float, float, float]:
        """AD-009 component mask on the image-plane delta (as `MoveTool._on_update`)."""
        if mask is None:
            if self.axis is None:
                return (float(delta[0]), float(delta[1]), float(delta[2]))
            mask = self.axis_mask
        return (delta[0] * mask[0], delta[1] * mask[1], delta[2] * mask[2])

    def preview_weights(self, target: Optional[Target]) -> dict:
        """Signed influence of `target` with the current settings (hover bands)."""
        if target is None or self.session is None:
            return {}
        return self.session.influence(target.seeds, self.world_radius, self.metric, self.curve)

    # -- input --------------------------------------------------------------------------

    def key(self, symbol_name: str, modifiers=frozenset()) -> Outcome:
        action = lb.resolve_key(self.phase, symbol_name, frozenset(modifiers))
        if action is None:
            return Outcome()
        return self.apply(action)

    def wheel(self, scroll_x: float, scroll_y: float, modifiers=frozenset()) -> Outcome:
        modifiers = frozenset(modifiers)
        steps = lb.wheel_steps(scroll_x, scroll_y, modifiers)
        if steps == 0:
            return Outcome()
        action = lb.resolve_wheel(self.phase, modifiers)
        if action is None:
            return Outcome()
        return self.apply(action, steps)

    def key_release(self, symbol_name: str) -> Outcome:
        """A released key: ends a hold gesture if it is the held key (commit / tap = no-op)."""
        hold = self.hold
        if hold is None or symbol_name != hold.key:
            return Outcome()
        out = Outcome(action=lb.resolve_hold_release(self.phase, symbol_name))
        self.hold = None
        if hold.begun and self.dragging:
            committed = self.end_drag()
            out.effects.update(committed.effects)
            self.note = f"{KIND_LABELS[hold.kind]} fertig" if self.session.last is not None else \
                f"{KIND_LABELS[hold.kind]}: keine Änderung"
        else:
            self.note = f"{KIND_LABELS[hold.kind]}: keine Bewegung, nichts geändert"
        out.effects.update({REPICK, PREVIEW_CHANGED})
        self._touch()
        return out

    def hold_motion(self, dx: float, dy: float, width: int, height: int, camera) -> Outcome:
        """Mouse motion while W/E/R is held (module docstring). Returns MESH_CHANGED with the
        moved vertices; GESTURE_BEGAN on the first motion."""
        hold = self.hold
        out = Outcome()
        if hold is None or self.session is None:
            return out
        if not hold.begun:
            if dx == 0 and dy == 0:
                return out  # a zero step is no motion (AD-016)
            self._begin_hold(hold, camera)
            out.effects.add(GESTURE_BEGAN)
        session = self.session
        started = time.perf_counter()
        if hold.kind == MOVE:
            anchor = session.mesh.vertex_position(hold.target.anchor)
            delta = camera.screen_delta_to_world(anchor, dx, dy, width, height)
            session.step(self.masked(delta, hold.mask))
        elif hold.kind == ROTATE:
            hold.pixels += dx
            target_angle = RotateTool.RADIANS_PER_PIXEL * hold.pixels
            step = target_angle - hold.applied
            if step == 0.0:
                return out
            session.step(step)
            hold.applied = target_angle
        else:
            hold.pixels += dx + dy
            target_scale = max(ScaleTool.MIN_SCALE, 1.0 + ScaleTool.SCALE_PER_PIXEL * hold.pixels)
            step = target_scale / hold.applied
            if step == 1.0:
                return out
            session.step(tuple(step if m else 1.0 for m in hold.mask))
            hold.applied = target_scale
            operation = session.drag.operation
            self.collapsed = collapsed_count(operation.weights, operation.total_factor,
                                             operation.scale_formula)
        self.drag_ms = (time.perf_counter() - started) * 1000.0
        out.effects.add(MESH_CHANGED)
        out.changed = set(session.drag.weights)
        self._touch()
        return out

    def _begin_hold(self, hold: Hold, camera) -> None:
        """First motion: constraint, weights, axis/formula are read now (as the app's `begin()`)."""
        hold.space = self.axis
        hold.mask = space_mask(self.axis)
        if hold.kind == ROTATE:
            hold.axis = (tuple(camera.basis()[0]) if self.axis is None
                         else _resolve_space(self.axis, for_rotation=True))
        hold.applied = 1.0 if hold.kind == SCALE else 0.0
        self.collapsed = None
        self.session.begin_gesture(hold.kind, hold.target, self.world_radius, self.metric, self.curve,
                                   axis=hold.axis, formula=self.scale_formula)
        hold.begun = True
        self.confirm_new_box = False
        self.note = None

    def apply(self, action: str, steps: int = 0) -> Outcome:
        out = Outcome(action=action)
        if self.confirm_new_box and action not in (lb.NEW_BOX,):
            self.confirm_new_box = False  # any other input cancels the confirmation
            self.note = None
            out.effects.add(DISPLAY_CHANGED)
            if action == lb.ESCAPE:
                self._touch()
                return out
        handler = _HANDLERS.get(action)
        if handler is not None:
            handler(self, out, steps)
        self._touch()
        return out

    # -- creation phase -------------------------------------------------------------------

    def _box(self, out: Outcome, box: BoxParams) -> None:
        if box != self.box:
            self.box = box
            out.effects.add(BOX_CHANGED)

    def commit_box(self) -> EditSession:
        """`Enter`: the box becomes the edit mesh (also without extra divisions); its rims go
        along for the rim-loop override (E15)."""
        mesh = build_box_mesh(self.box)
        self.session = EditSession(mesh, box_rims(mesh, self.box))
        self.phase = lb.PHASE_EDIT
        self.note = None
        return self.session

    # -- edit phase: selection (Slice 3) ------------------------------------------------------

    def click(self, command: str, hit) -> Outcome:
        """A selection click (E25) with the handle the window picked in the active mode
        (None = empty space). Ignored while `busy` (E31) and outside the edit phase."""
        out = Outcome(action=command)
        if self.phase != lb.PHASE_EDIT or self.busy:
            return out
        if self.confirm_new_box:
            self.confirm_new_box = False
            self.note = None
            out.effects.add(DISPLAY_CHANGED)
        if apply_click(self.selection, command, hit):
            self.note = None
            out.effects.update({SELECTION_CHANGED, PREVIEW_CHANGED})
        self._prev_anchor, self._anchor = self._anchor, hit
        self._touch()
        return out

    def click_loop(self, command: str, target: Optional[Target]) -> Outcome:
        """A click in the `L` mode: the whole hovered Loop/Ring (`target`, None = empty space)."""
        out = Outcome(action=command)
        if self.phase != lb.PHASE_EDIT or self.busy:
            return out
        self.confirm_new_box = False
        elements = None if target is None else loop_elements(self.selection, target)
        if target is not None and elements is None:
            self.note = "L-Modus: im Flächenmodus gibt es keinen Loop/Ring einer Kante (offene Frage)"
            out.effects.add(DISPLAY_CHANGED)
        elif apply_click_elements(self.selection, command, elements):
            self.note = None
            out.effects.update({SELECTION_CHANGED, PREVIEW_CHANGED})
        self._prev_anchor = self._anchor = None
        self._touch()
        return out

    def double_click(self, action: Optional[str], command: str, hit) -> Outcome:
        """The second click of a double click on the mesh (Slice 3b). Where the double click
        means nothing (other modes, other modifiers, the L mode) it is an ordinary click."""
        mode = self.selection.mode
        session = self.session
        applies = (not self.loop_mode and session is not None and hit is not None and not self.busy
                   and ((action == lb.DOUBLE_LOOP and mode is SelectionMode.EDGE)
                        or (action == lb.DOUBLE_PART and mode in (SelectionMode.EDGE, SelectionMode.FACE))))
        if not applies:
            return self.click(command, hit)
        out = Outcome(action=action)
        if action == lb.DOUBLE_LOOP:
            loop = session.target(hit, MODE_LOOP)
            self.selection.set(set(loop.edges))
            self.note = f"Edge Loop: {len(loop.edges)} Kanten" + (", geschlossen" if loop.closed else "")
        elif mode is SelectionMode.EDGE:
            part = loop_segment(session.finder, self._prev_anchor, hit)
            if part is None:
                self.note = "Teilstück: die zuletzt geklickte Kante liegt nicht im selben Loop"
            else:
                self.selection.add(set(part))
                self.note = f"Loop-Teilstück: {len(part)} Kanten dazu"
        else:
            faces = face_loop(session.finder, self._prev_anchor, hit)
            if faces is None:
                self.note = "Face Loop: die zuletzt geklickte Fläche ist keine Nachbarfläche"
            else:
                self.selection.add(set(faces))
                self.note = f"Face Loop: {len(faces)} Flächen dazu"
        out.effects.update({SELECTION_CHANGED, PREVIEW_CHANGED, DISPLAY_CHANGED})
        self._touch()
        return out

    # -- edit phase: gesture ----------------------------------------------------------------

    def begin_drag(self, target: Target) -> dict:
        if self.session is None:
            raise RuntimeError("no edit session")
        self.confirm_new_box = False
        self.note = None
        self.collapsed = None
        self._touch()
        return self.session.begin_drag(target, self.world_radius, self.metric, self.curve)

    def drag_step(self, world_delta) -> None:
        self.session.drag_step(self.masked(world_delta))

    def end_drag(self) -> Outcome:
        out = Outcome()
        if self.dragging:
            self.session.commit()
            out.effects.update({REPICK, PREVIEW_CHANGED})
            self._touch()
        return out

    def cancel_drag(self) -> Outcome:
        """Esc / RMB: cancels the running gesture (LMB drag or hold) exactly; an armed hold
        without motion is only disarmed."""
        out = Outcome()
        if self.hold is not None and not self.dragging:
            self.hold = None
            self.note = "abgebrochen"
            out.effects.update({REPICK, PREVIEW_CHANGED})
            self._touch()
            return out
        self.hold = None
        if self.dragging:
            self.session.cancel()
            self.note = "Zug abgebrochen"
            out.effects.update({MESH_CHANGED, PREVIEW_CHANGED})
            out.changed = self.session.last_changed
            self._touch()
        return out

    # -- edit phase: settings -----------------------------------------------------------------

    def set_curve(self, curve: SignedCurve) -> Outcome:
        out = Outcome()
        if curve != self.curve or curve.preset != self.curve.preset:
            shape_changed = curve.shape != self.curve.shape
            self.curve = curve
            if shape_changed:
                self._settings_changed(out)
            else:
                out.effects.add(DISPLAY_CHANGED)  # only a handle mode (aligned/corner) changed
            self._touch()
        return out

    def _settings_changed(self, out: Outcome) -> None:
        """Preview always (E7 a); Nachführen of the last gesture when on (E7 b)."""
        out.effects.add(PREVIEW_CHANGED)
        session = self.session
        if session is None or not self.nachfuehren or not session.can_retune:
            return
        started = time.perf_counter()
        if session.retune(self.world_radius, self.metric, self.curve, self.scale_formula):
            out.effects.add(MESH_CHANGED)
            out.changed = session.last_changed
            last = session.last
            if last is not None and last.kind == SCALE:
                self.collapsed = collapsed_count(last.weights, last.total, last.formula)
        self.retune_ms = (time.perf_counter() - started) * 1000.0

    # -- HUD -------------------------------------------------------------------------------------

    def status_text(self) -> str:
        if self.phase == lb.PHASE_CREATE:
            b = self.box
            v, e, f = b.counts()
            return (f"Box: Höhe {b.height:g} · Breite {b.width:g} · Tiefe {b.depth:g} · Loops {b.loops} (h={b.h}) · "
                    f"rundum n={b.n} · V {v} / E {e} / F {f}")
        axis = _SPACE_LABELS[self.axis]
        hover = f"L-Modus {MODE_LABELS[self.mode]}" if self.loop_mode else f"Hover {MODE_NAMES[self.selection.mode]}"
        return (f"{hover} · Auswahl {MODE_NAMES[self.selection.mode]} · Achse {axis} · "
                f"Scale {self.scale_formula} · "
                f"Radius {self.radius_percent} % "
                f"({self.world_radius:.2f}) · {self.metric} · Kurve {self.curve.label} · "
                f"Nachführen {'an' if self.nachfuehren else 'aus'} · "
                f"Punkte {'an' if self.bands_visible else 'aus'} · "
                f"Vorschau {'an' if self.preview_visible else 'aus'}")

    def hud_lines(self, frame_ms: Optional[float]) -> list[HudLine]:
        lines = [HudLine("Mehlsack Lab — Slice 3b (Hover, L-Modus, Doppelklick) · nicht Artist-validiert", "title")]
        if self.phase == lb.PHASE_CREATE:
            lines.append(HudLine("BOX BAUEN: Mausrad Höhe · Alt+Rad Breite · Alt+Shift+Rad Tiefe · "
                                 "Shift+Rad Loops · Ctrl+Rad rundum · Enter = Bearbeiten", "active"))
            lines.append(HudLine("(Mausrad zoomt hier nicht — es gehört der Box)", "inactive"))
        else:
            lines.append(HudLine("BEARBEITEN: LMB ziehen oder W/E/R halten · Klick = Auswahl (Shift/Ctrl/Alt) · "
                                 "1/2/3 Modus · L Loop/Ring-Modus · X/Y/Z, Shift = Ebene · H Hilfe", "active"))
            lines.append(self._selection_line())
            hold = self.hold
            if hold is not None:
                state = "läuft" if hold.begun else "scharf — Maus bewegen"
                lines.append(HudLine(f"{KIND_LABELS[hold.kind]} ({hold.key} gehalten): {state} · "
                                     f"loslassen = fertig, Esc/RMB = abbrechen", "warning"))
            if self.collapsed is not None:
                lines.append(HudLine(f"Scale linear: {self.collapsed} Vertices mit g ≤ 0 "
                                     "(auf den Mittelpunkt gefallen oder durchgeklappt)",
                                     "warning" if self.collapsed else "inactive"))
        lines.append(HudLine(self.status_text(), "normal"))
        if self.session is not None:
            s = self.session
            v, e, f = len(s.mesh.all_vertex_ids()), len(s.finder.index.edges), len(s.mesh.all_face_ids())
            last = s.last
            retune = "—" if last is None else f"letzter Zug nachführbar ({last.retunes}× angepasst)"
            lines.append(HudLine(
                f"Mesh V {v} / E {e} / F {f} · History {len(s.history)} · {retune}", "normal"))

        def ms(value):
            return "—" if value is None else f"{value:.1f} ms"

        frame = "—" if frame_ms is None else f"{frame_ms:.1f} ms"
        lines.append(HudLine(
            f"Hover {ms(self.hover_ms)} · Drag-Schritt {ms(self.drag_ms)} · Nachführen "
            f"{ms(self.retune_ms)} · Frame {frame}", "inactive"))
        lines.append(HudLine(f"GL {self.gl_version} · {self.gl_renderer}", "inactive"))
        if self.confirm_new_box:
            lines.append(HudLine("Neue Box? Noch einmal B = ja (History wird gelöscht), "
                                 "andere Taste = nein", "warning"))
        elif self.note:
            lines.append(HudLine(self.note, "warning"))
        return lines

    def _selection_line(self) -> HudLine:
        sel = self.selection
        count = len({SelectionMode.VERTEX: sel.vertices, SelectionMode.EDGE: sel.edges,
                     SelectionMode.FACE: sel.faces}[sel.mode])
        target = self.selection_target
        if target is None:
            hovered = f"den gehoverten {MODE_LABELS[self.mode]}" if self.loop_mode else "das gehoverte Element"
            return HudLine(f"Auswahl ({MODE_NAMES[sel.mode]}): leer → Gesten wirken auf {hovered}", "inactive")
        return HudLine(f"Auswahl ({MODE_NAMES[sel.mode]}): {count} gewählt, {len(target.seeds)} Vertices → "
                       "alle Gesten wirken auf die Auswahl · Klick ins Leere = zurück zum Hover", "active")

    def help_lines(self) -> list[str]:
        return ["Tasten (alle lab-lokal PROVISIONAL, außer Artist Input Truth):"] + lb.overrides_table(self.phase)


# -- action handlers --------------------------------------------------------------------------


def _h_box_height(state: LabState, out: Outcome, steps: int) -> None:
    state._box(out, state.box.with_height_steps(steps))


def _h_box_width(state: LabState, out: Outcome, steps: int) -> None:
    state._box(out, state.box.with_width_steps(steps))


def _h_box_depth(state: LabState, out: Outcome, steps: int) -> None:
    state._box(out, state.box.with_depth_steps(steps))


def _h_box_loops(state: LabState, out: Outcome, steps: int) -> None:
    state._box(out, state.box.with_h_steps(steps))


def _h_box_around(state: LabState, out: Outcome, steps: int) -> None:
    state._box(out, state.box.with_n_steps(steps))


def _h_commit_box(state: LabState, out: Outcome, steps: int) -> None:
    state.commit_box()
    out.effects.update({PHASE_CHANGED, PREVIEW_CHANGED})


def _h_zoom(state: LabState, out: Outcome, steps: int) -> None:
    out.zoom_steps = steps


def _h_radius(state: LabState, out: Outcome, steps: int) -> None:
    step = max(0, min(len(RADIUS_STEPS_PERCENT) - 1, state.radius_step + steps))
    if step != state.radius_step:
        state.radius_step = step
        state._settings_changed(out)


def _h_toggle_mode(state: LabState, out: Outcome, steps: int) -> None:
    state.mode = MODE_RING if state.mode == MODE_LOOP else MODE_LOOP
    out.effects.add(PREVIEW_CHANGED)


def _h_axis(state: LabState, out: Outcome, steps: int) -> None:
    space = _SPACES[out.action]
    state.axis = None if state.axis == space else space  # same key again = off (app B4.1)
    out.effects.add(DISPLAY_CHANGED)


def _h_hold(state: LabState, out: Outcome, steps: int) -> None:
    """W/E/R down: arm on the active target (E16, E26: the selection, else the hover target);
    ignored without a target, while another hold, an LMB drag or an undecided LMB press runs."""
    if state.busy or state.session is None:
        return
    target = state.active_target
    kind = lb.HOLD_KINDS[out.action]
    if target is None:
        state.note = f"{KIND_LABELS[kind]}: nichts ausgewählt oder gehovert"
        out.effects.add(DISPLAY_CHANGED)
        return
    key = next(b.value for b in lb.LAB_OVERRIDES if b.action == out.action)
    state.hold = Hold(key=key, kind=kind, target=target)
    state.confirm_new_box = False
    state.note = None
    out.effects.add(DISPLAY_CHANGED)


def _h_formula(state: LabState, out: Outcome, steps: int) -> None:
    state.scale_formula = SCALE_FORMULAS[(SCALE_FORMULAS.index(state.scale_formula) + 1) % len(SCALE_FORMULAS)]
    state._settings_changed(out)


def _h_metric(state: LabState, out: Outcome, steps: int) -> None:
    names = list(METRICS)
    state.metric = names[(names.index(state.metric) + 1) % len(names)]
    state._settings_changed(out)


def _h_bands(state: LabState, out: Outcome, steps: int) -> None:
    state.bands_visible = not state.bands_visible
    out.effects.add(DISPLAY_CHANGED)


def _h_preview(state: LabState, out: Outcome, steps: int) -> None:
    state.preview_visible = not state.preview_visible
    out.effects.add(DISPLAY_CHANGED)


def _h_nachfuehren(state: LabState, out: Outcome, steps: int) -> None:
    state.nachfuehren = not state.nachfuehren
    if state.session is not None:
        state.session.end_retune()  # the last gesture stays as it is now
    out.effects.add(DISPLAY_CHANGED)


def _h_preset(state: LabState, out: Outcome, steps: int) -> None:
    curve = SignedCurve.from_preset(_PRESETS[out.action])
    if curve != state.curve or curve.preset != state.curve.preset:
        state.curve = curve
        state._settings_changed(out)


def _disarm_unbegun(state: LabState) -> None:
    """Undo/Redo while W/E/R is only armed: disarm first (as the app); a running gesture
    makes the session refuse Undo/Redo anyway."""
    if state.hold is not None and not state.hold.begun:
        state.hold = None


def _h_undo(state: LabState, out: Outcome, steps: int) -> None:
    _disarm_unbegun(state)
    if not state.dragging:
        state.collapsed = None  # the counted Scale is no longer the last gesture
    if state.session is not None and state.session.undo():
        out.effects.update({MESH_CHANGED, PREVIEW_CHANGED})


def _h_redo(state: LabState, out: Outcome, steps: int) -> None:
    _disarm_unbegun(state)
    if not state.dragging:
        state.collapsed = None  # the counted Scale is no longer the last gesture
    if state.session is not None and state.session.redo():
        out.effects.update({MESH_CHANGED, PREVIEW_CHANGED})


def _h_new_box(state: LabState, out: Outcome, steps: int) -> None:
    if state.busy:
        return
    if not state.confirm_new_box:
        state.confirm_new_box = True
        out.effects.add(DISPLAY_CHANGED)
        return
    state.confirm_new_box = False
    state.session = None  # History goes with the session
    state.hover_target = None
    state.selection.clear()  # E31: a new box starts without a selection (the mode stays)
    state.collapsed = None
    state.phase = lb.PHASE_CREATE
    state.note = None
    out.effects.update({PHASE_CHANGED, BOX_CHANGED, SELECTION_CHANGED})


def _h_selection_mode(state: LabState, out: Outcome, steps: int) -> None:
    """`1`/`2`/`3` (Artist Input Truth): set the mode and clear the selection, also for the
    active mode — as the app's `_set_selection_mode` (Playground behaviour). Ignored while busy."""
    if state.busy:
        return
    mode = _SELECTION_MODES[out.action]
    state.selection.mode = mode
    state.selection.clear()
    state.selection.hovered = None
    state._prev_anchor = state._anchor = None
    state.note = f"Auswahlmodus: {MODE_NAMES[mode]}"
    out.effects.update({SELECTION_CHANGED, PREVIEW_CHANGED})


def _h_convert(state: LabState, out: Outcome, steps: int) -> None:
    """Shift+`1`/`2`/`3` (Manu O15): convert the selection to the touching components of that
    mode (an empty selection just switches the mode). Ignored while busy."""
    if state.busy or state.session is None:
        return
    mode = _SELECTION_MODES[out.action]
    convert_selection(state.session.mesh, state.session.finder.index, state.selection, mode)
    state.selection.hovered = None
    state._prev_anchor = state._anchor = None
    count = len({SelectionMode.VERTEX: state.selection.vertices, SelectionMode.EDGE: state.selection.edges,
                 SelectionMode.FACE: state.selection.faces}[mode])
    state.note = f"Auswahl umgerechnet: {count} {MODE_NAMES[mode]}"
    out.effects.update({SELECTION_CHANGED, PREVIEW_CHANGED})


def _h_loop_mode(state: LabState, out: Outcome, steps: int) -> None:
    """`L` (Manu O13): Loop/Ring mode on/off (sticky). Ignored while busy."""
    if state.busy:
        return
    state.loop_mode = not state.loop_mode
    state.selection.hovered = None
    state._prev_anchor = state._anchor = None
    state.note = ("L-Modus an: Hover und Klick nehmen ganze Loops/Ringe (Tab = Loop/Ring)" if state.loop_mode
                  else "L-Modus aus: Hover zeigt einzelne Elemente")
    out.effects.update({SELECTION_CHANGED, PREVIEW_CHANGED})


def _h_loop_ring_select(state: LabState, out: Outcome, steps: int) -> None:
    """Shift+L / Shift+R (E27): add the Loop / Ring of the hovered edge. Ignored while busy."""
    if state.busy or state.session is None:
        return
    kind = MODE_LOOP if out.action == lb.LOOP_SELECT else MODE_RING
    edge, state.edge_under_cursor = state.edge_under_cursor, None
    if edge is None and state.hover_target is not None:
        edge = state.hover_target.edge
    changed, state.note = add_loop_ring(state.selection, state.session.finder, edge, kind)
    out.effects.add(DISPLAY_CHANGED)
    if changed:
        out.effects.update({SELECTION_CHANGED, PREVIEW_CHANGED})


def _h_help(state: LabState, out: Outcome, steps: int) -> None:
    state.help_visible = not state.help_visible
    out.effects.add(DISPLAY_CHANGED)


def _h_escape(state: LabState, out: Outcome, steps: int) -> None:
    if state.dragging or state.hold is not None:
        cancelled = state.cancel_drag()
        out.effects.update(cancelled.effects)
        out.changed = cancelled.changed
    else:
        out.effects.add(QUIT)


_HANDLERS = {
    lb.BOX_HEIGHT: _h_box_height,
    lb.BOX_WIDTH: _h_box_width,
    lb.BOX_DEPTH: _h_box_depth,
    lb.BOX_LOOPS: _h_box_loops,
    lb.BOX_AROUND: _h_box_around,
    lb.COMMIT_BOX: _h_commit_box,
    lb.ZOOM: _h_zoom,
    lb.RADIUS: _h_radius,
    lb.TOGGLE_MODE: _h_toggle_mode,
    lb.AXIS_X: _h_axis,
    lb.AXIS_Y: _h_axis,
    lb.AXIS_Z: _h_axis,
    lb.PLANE_YZ: _h_axis,
    lb.PLANE_XZ: _h_axis,
    lb.PLANE_XY: _h_axis,
    lb.HOLD_MOVE: _h_hold,
    lb.HOLD_ROTATE: _h_hold,
    lb.HOLD_SCALE: _h_hold,
    lb.SCALE_FORMULA: _h_formula,
    lb.METRIC: _h_metric,
    lb.BANDS: _h_bands,
    lb.PREVIEW: _h_preview,
    lb.NACHFUEHREN: _h_nachfuehren,
    lb.PRESET_1: _h_preset,
    lb.PRESET_2: _h_preset,
    lb.UNDO: _h_undo,
    lb.REDO: _h_redo,
    lb.NEW_BOX: _h_new_box,
    lb.MODE_VERTEX: _h_selection_mode,
    lb.MODE_EDGE: _h_selection_mode,
    lb.MODE_FACE: _h_selection_mode,
    lb.CONVERT_VERTEX: _h_convert,
    lb.CONVERT_EDGE: _h_convert,
    lb.CONVERT_FACE: _h_convert,
    lb.LOOP_MODE: _h_loop_mode,
    lb.LOOP_SELECT: _h_loop_ring_select,
    lb.RING_SELECT: _h_loop_ring_select,
    lb.HELP: _h_help,
    lb.ESCAPE: _h_escape,
}
