"""State machine of the Mehlsack Lab (pyglet-free, GL-free; precedent `subdivision_lab/lab_state.py`).

Everything a key or wheel event changes and everything the HUD shows lives here, so the
whole interaction is testable without a window. The window resolves nothing itself: it
hands raw names (`"X"`, `{"ctrl"}`, scroll values) to `key()` / `wheel()`, the hover
target and world deltas to `begin_drag()` / `drag_step()`, and reacts to the returned
`Outcome` (rebuild the box, resync the mesh, re-pick the hover, zoom, quit).

Phases: `create` (wheel builds the box, `Enter` commits) → `edit` (Loop/Ring drag).
Settings are sticky and survive gestures, Undo and a new box: Loop/Ring mode, axis,
radius step, metric, curve, bands, preview, Nachführen. Defaults: geodesic, Smooth, 15 %
(Artist 2026-10-11, AD-020 E5); Nachführen on (handoff E7); surface preview off (Slice 2a A9).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from mirai.soft_selection import METRICS
from mirai.soft_selection.settings import (
    DEFAULT_METRIC,
    DEFAULT_RADIUS_STEP,
    RADIUS_STEPS_PERCENT,
)

from . import lab_bindings as lb
from .box import BoxParams, box_rims, build_box_mesh
from .edit_session import EditSession
from .signed_curve import DEFAULT_CURVE, PRESET_HAT, PRESET_SMOOTH, SignedCurve
from .targets import MODE_LABELS, MODE_LOOP, MODE_RING, Target

# Outcome effects (what the window has to do after an event)
BOX_CHANGED = "box_changed"          # creation phase: rebuild the preview mesh
PHASE_CHANGED = "phase_changed"      # new mesh / new phase: rebuild scene objects
MESH_CHANGED = "mesh_changed"        # positions changed (`Outcome.changed`): resync, re-pick hover
REPICK = "repick"                    # positions may differ from the last pick (drag release)
PREVIEW_CHANGED = "preview_changed"  # mode/radius/metric/curve: recompute hover target + bands
DISPLAY_CHANGED = "display_changed"  # bands/preview visibility, help, HUD text only
QUIT = "quit"

FRAME_EMA = 0.1

_AXES = {lb.AXIS_X: "x", lb.AXIS_Y: "y", lb.AXIS_Z: "z"}
_MASKS = {None: (1.0, 1.0, 1.0), "x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
_PRESETS = {lb.PRESET_1: PRESET_SMOOTH, lb.PRESET_2: PRESET_HAT}


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
        self.axis: Optional[str] = None
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
    def axis_mask(self) -> tuple[float, float, float]:
        return _MASKS[self.axis]

    def masked(self, delta) -> tuple[float, float, float]:
        """AD-009 component mask on the image-plane delta (as `MoveTool._on_update`)."""
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

    # -- edit phase: gesture ----------------------------------------------------------------

    def begin_drag(self, target: Target) -> dict:
        if self.session is None:
            raise RuntimeError("no edit session")
        self.confirm_new_box = False
        self.note = None
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
        out = Outcome()
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
        if session.retune(self.world_radius, self.metric, self.curve):
            out.effects.add(MESH_CHANGED)
            out.changed = session.last_changed
        self.retune_ms = (time.perf_counter() - started) * 1000.0

    # -- HUD -------------------------------------------------------------------------------------

    def status_text(self) -> str:
        if self.phase == lb.PHASE_CREATE:
            b = self.box
            v, e, f = b.counts()
            return (f"Box: Höhe {b.height:g} · Breite {b.width:g} · Tiefe {b.depth:g} · Loops {b.loops} (h={b.h}) · "
                    f"rundum n={b.n} · V {v} / E {e} / F {f}")
        axis = self.axis.upper() if self.axis else "frei"
        return (f"{MODE_LABELS[self.mode]} · Achse {axis} · Radius {self.radius_percent} % "
                f"({self.world_radius:.2f}) · {self.metric} · Kurve {self.curve.label} · "
                f"Nachführen {'an' if self.nachfuehren else 'aus'} · "
                f"Punkte {'an' if self.bands_visible else 'aus'} · "
                f"Vorschau {'an' if self.preview_visible else 'aus'}")

    def hud_lines(self, frame_ms: Optional[float]) -> list[HudLine]:
        lines = [HudLine("Mehlsack Lab — Slice 2a (Move) · nicht Artist-validiert", "title")]
        if self.phase == lb.PHASE_CREATE:
            lines.append(HudLine("BOX BAUEN: Mausrad Höhe · Alt+Rad Breite · Alt+Shift+Rad Tiefe · "
                                 "Shift+Rad Loops · Ctrl+Rad rundum · Enter = Bearbeiten", "active"))
            lines.append(HudLine("(Mausrad zoomt hier nicht — es gehört der Box)", "inactive"))
        else:
            lines.append(HudLine("BEARBEITEN: Kante hovern, LMB ziehen · Tab Loop/Ring · X/Y/Z · "
                                 "Shift+Rad Radius · P Vorschau · H Hilfe", "active"))
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
    axis = _AXES[out.action]
    state.axis = None if state.axis == axis else axis  # same key again = off (app B4.1)
    out.effects.add(DISPLAY_CHANGED)


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


def _h_undo(state: LabState, out: Outcome, steps: int) -> None:
    if state.session is not None and state.session.undo():
        out.effects.update({MESH_CHANGED, PREVIEW_CHANGED})


def _h_redo(state: LabState, out: Outcome, steps: int) -> None:
    if state.session is not None and state.session.redo():
        out.effects.update({MESH_CHANGED, PREVIEW_CHANGED})


def _h_new_box(state: LabState, out: Outcome, steps: int) -> None:
    if state.dragging:
        return
    if not state.confirm_new_box:
        state.confirm_new_box = True
        out.effects.add(DISPLAY_CHANGED)
        return
    state.confirm_new_box = False
    state.session = None  # History goes with the session
    state.phase = lb.PHASE_CREATE
    state.note = None
    out.effects.update({PHASE_CHANGED, BOX_CHANGED})


def _h_help(state: LabState, out: Outcome, steps: int) -> None:
    state.help_visible = not state.help_visible
    out.effects.add(DISPLAY_CHANGED)


def _h_escape(state: LabState, out: Outcome, steps: int) -> None:
    if state.dragging:
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
    lb.METRIC: _h_metric,
    lb.BANDS: _h_bands,
    lb.PREVIEW: _h_preview,
    lb.NACHFUEHREN: _h_nachfuehren,
    lb.PRESET_1: _h_preset,
    lb.PRESET_2: _h_preset,
    lb.UNDO: _h_undo,
    lb.REDO: _h_redo,
    lb.NEW_BOX: _h_new_box,
    lb.HELP: _h_help,
    lb.ESCAPE: _h_escape,
}
