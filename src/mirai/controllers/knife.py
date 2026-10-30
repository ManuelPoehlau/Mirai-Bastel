"""KnifeController (AD-027 §3.4): the Knife session (AD-017; WP-06 B7, WP-KNIFE-01, AD-SYM-03 slice 6c) as a
session in the slot, the provisional mirror-preview variant and the injectable double-click clock.

Behaviour as it was inside `Application` (AD-027 M3 moves it, nothing else). The session is exclusive
(`interaction_owner` "knife"): it resolves every key in the `knife` context itself, and its `allows` alone answers
`can_run` - its own commands, Cancel, Undo/Redo (into its isolated history, AD-017) and view state (display, Look,
Ortho). It grabs the plain and Shift LMB and the KnifeLift button (press, drag, release), motion, hover, Shift
held, the Soft wheel steps, leave, every release after the pointer resolver, and Undo/Redo from the API.

Click-only (Artist decision Manu 2026-09-28, after the B7 window test): a press only starts the click-threshold
gesture, the release under the threshold is the click. WP-KNIFE-01 S2-S4: a click adds a point to the session's
path (the mesh is cut at commit only), a far click is planned across faces with the camera of that click, a click
outside the mesh is a point in space (Manu 2026-10-02, Blender).
"""

from __future__ import annotations

import dataclasses
import math
import time
from typing import Callable, Optional

from ..interaction import commands
from ..interaction.input import KNIFE_CONTEXT
from ..interaction.pointer import CLICK_THRESHOLD_PX
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
from ..subdivision.preview import key_label
from ..symmetric_knife import KnifeRefusal, SymmetricKnifeView
from ..topology.face_geometry import GEO_EPS
from ..topology.knife import CLOSE_NEEDS, EARLIER_INTERIOR, TOO_CLOSE, KnifeTool
from ..topology.knife_pick import knife_pick, snap_own_point, space_point
from ..topology.knife_preview import KnifeRenderData, build_knife_render_data
from viewport.overlay import (
    TOOL_ACTIVE_LAYER,
    TOOL_CLIPPED_LAYER,
    TOOL_MIRROR_DIM_LAYER,
    TOOL_MIRROR_LAYER,
    TOOL_MIRROR_PREVIEW_LAYER,
    TOOL_PREVIEW_LAYER,
    TOOL_REFUSED_LAYER,
)
from .services import AppServices

# WP-KNIFE-01 S3 (PROVISIONAL wording, decision.md "One Knife S3"): status for a refused Knife click
# by the tool's reason - the S3 cases are named, every other refusal keeps the S2 text.
KNIFE_REFUSED = {
    TOO_CLOSE: "Knife: too close to an edge - click on the edge or further inside the face",
    CLOSE_NEEDS: "Knife: closing a shape needs at least 3 points",
    EARLIER_INTERIOR: "Knife: an earlier point inside a face cannot be clicked again (not yet)",
}

# WP-KNIFE-01 UX2 (D7, decision.md "WP-KNIFE-01 UX2"): two Knife clicks this close in time (s) and
# place (px) are a double-click.
KNIFE_DOUBLE_CLICK_S = 0.35
KNIFE_DOUBLE_CLICK_PX = 4.0

# AD-SYM-03 slice 6c (PROVISIONAL, the Artist's call in the 6c practical test, removed or kept in 6d): the three
# looks of the mirror side in a symmetric Knife session, switched inside the session by one provisional key.
# V-a: drawn like the working side's own preview (path lines depth-tested, points through); V-b: always
# visible (no depth test), dimmed; V-c: the mirror's points only. Default V-b: from a side camera every
# mirror point is hidden (KD 2.7), so V-a can show nothing there.
KNIFE_MIRROR_VARIANTS = ("V-a", "V-b", "V-c")
KNIFE_MIRROR_VARIANT_DEFAULT = "V-b"
KNIFE_MIRROR_VARIANT_LABELS = {
    "V-a": "wie die eigene Vorschau, verdeckt",
    "V-b": "immer sichtbar, gedimmt",
    "V-c": "nur Punkte",
}
#: The provisional variant key (`bindings.KNIFE_MIRROR_VARIANT_KEY`) is the default of `commands.KNIFE_MIRROR_VARIANT` in
#: `KNIFE_CONTEXT` since 2026-10-28 (AD-013 addendum, K-1; a literal before).

#: What a Knife session lets through from outside its own key map (AD-017; AD-027 §3.3: its commands, Cancel,
#: Undo/Redo into its isolated history, view state). Its keys never ask: the session resolves them itself.
KNIFE_ALLOWS = frozenset(
    {
        commands.KNIFE_COMMIT,
        commands.KNIFE_LIFT,
        commands.KNIFE_MIRROR_VARIANT,
        commands.CANCEL,
        commands.UNDO,
        commands.REDO,
        commands.TOGGLE_ORTHO,
        *commands.DISPLAY_COMMANDS,
        *commands.LOOK_COMMANDS,
    }
)

# The preview builder ends a chain at a "closed" break only; a pen lift is drawn the same way.
_DRAWN_LIFT = {"kind": "break", "reason": "closed", "cyclic": False}


def knife_notes(res) -> list[str]:
    """What the commit joined or dropped (`KnifeResolution`), for the status line. Nothing of it is
    shown while cutting (Artist, 2026-09-30: the join to the nearest corner is made at commit only)."""
    if res is None:
        return []
    notes = []
    if res.joined:
        notes.append(f"{res.joined} last point(s) inside a face joined to the nearest corner")
    if res.dropped_tail:
        notes.append("a last point inside a face could not be joined to a corner - dropped")
    if res.dropped_lead:
        notes.append("first point(s) inside a face before any edge or vertex dropped")
    rejected = [shape for shape in res.closed_shapes if not shape.built]
    if rejected:
        notes.append(f"{len(rejected)} closed shape(s) could not be built")
    if res.short_shapes:
        notes.append(f"{len(res.short_shapes)} shape(s) inside a face with fewer than 3 points dropped")
    if res.skipped_shapes:
        notes.append(f"{res.skipped_shapes} closed shape(s) skipped - their face was already cut")
    for reason, n in sorted(res.loops_dropped.items()):
        notes.append(f"{n} loop(s) closed at a point dropped ({reason})")
    if res.lost_continuation:
        notes.append("the cut on from an interior start point dropped")
    return notes


def knife_plan_notes(plan) -> list[str]:
    """What a click's segment across faces left uncut (WP-KNIFE-01 S4, PROVISIONAL wording)."""
    notes = []
    if plan.hidden:
        notes.append(f"{plan.hidden} hidden crossing(s) not cut")
    if "gap" in plan.skipped:
        notes.append("skipped: over a hole, border or hidden part")
    if plan.method and "edge" in plan.skipped:
        notes.append("skipped: along an existing edge")
    return notes


class KnifeSession:
    """A running Knife session: `KnifeTool` holds the mesh steps, the start and the path; here is the interaction
    state - the valid prospective target (None = none or invalid), the highlighted (hovered) edge, the hovered
    segment's crossings (S4), a refused hover target and its text (slice 6c, F3 = A), the held click-threshold
    gesture (its button: LMB = a point, RMB = pen lift; Shift at the press = midpoint snap, fixed at the press,
    AD-019) and the last LMB click (time, x, y) for the double-click. `selection_before` is the snapshot before the
    session for the selection mirror at commit; `view` the symmetric session view (None = no definition at begin:
    the Knife as it always was)."""

    owner = "knife"
    label = "Knife"
    exclusive = True

    def __init__(self, controller: "KnifeController", tool: KnifeTool, view, selection_before: tuple) -> None:
        self._controller = controller
        self.tool = tool
        self.view: SymmetricKnifeView | None = view
        self.selection_before = selection_before
        self.target: dict | None = None
        self.highlight_edge = None
        self.hover_crossings: tuple = ()
        self.refused: dict | None = None
        self.refused_text: str | None = None
        self.gesture = False
        self.gesture_moved = 0.0
        self.gesture_button = "LEFT"
        self.gesture_midpoint = False
        self.last_click: tuple[float, float, float] | None = None

    # -- the slot protocol ---------------------------------------------------------------------------

    def grabs(self, event) -> bool:
        if isinstance(event, Press):
            return self._owns_press(event.input)
        if isinstance(event, Drag):
            return event.command is None and self.gesture
        if isinstance(event, Release):
            # Its own press's release before the resolver; after it every release (the session gate).
            return not event.raw or (self.gesture and event.button == self.gesture_button)
        if isinstance(event, Wheel):
            return event.command is not None  # the Soft wheel steps do nothing in a session (zoom is navigation)
        if isinstance(event, Command):
            return event.command in (commands.UNDO, commands.REDO)
        return isinstance(event, (KeyPress, Motion, Hover, Modifiers, Leave))

    def allows(self, command: str, ctx: RunContext) -> Optional[Refusal]:
        return None if command in KNIFE_ALLOWS else SILENT

    def handle(self, event) -> Outcome:
        if not self.grabs(event):
            return PASS  # stage 3 of the routing: the Knife takes only what it grabs
        controller = self._controller
        if isinstance(event, KeyPress):
            return self._key(event.input)
        if isinstance(event, Press):
            self._press(event.input)
            return True
        if isinstance(event, Drag):
            # LMB held and moved: only tracks distance for the click threshold (B7.1, no slide) - a drag past
            # the threshold neither locks nor cuts.
            self.gesture_moved += abs(event.dx) + abs(event.dy)
            return False
        if isinstance(event, Release):
            if event.raw:
                return self._release(event.x, event.y)
            # Session gate (B7): navigation is over or a modified click fell - the click itself does nothing
            # during the session (no selection change), the preview picks again.
            controller.services.refresh_hover()
            return False
        if isinstance(event, (Motion, Hover)):
            return False if self.gesture else self.hover(event.x, event.y)
        if isinstance(event, Modifiers):
            # WP-KNIFE-01 UX2b: the hover preview at the known cursor follows Shift at once (the midpoint before
            # the click); a click keeps deciding by its press modifiers (A2, AD-019).
            return False if self.gesture else self.hover(*controller.services.cursor)
        if isinstance(event, Leave):
            return False if self.gesture else self.clear_preview()
        if isinstance(event, Wheel):
            return False
        if isinstance(event, Command):
            return self._history_step(event.command)
        return PASS

    def cancel(self) -> bool:
        return self._controller.end(self, commit=False)

    def commit(self) -> bool:
        return self._controller.end(self, commit=True)

    # -- keys, clicks ----------------------------------------------------------------------------------

    def _key(self, input) -> bool:
        """Session gate: only commit, cancel, the pen lift, the mirror variant, the in-session Undo/Redo and the
        Ortho toggle (view state) pass; every other key (W/R, 1/2/3, D/Shift+D, C, X/Y/Z, ...) is ignored."""
        controller = self._controller
        command = controller.services.bindings.command_for(input, KNIFE_CONTEXT)
        self.last_click = None  # a key between two clicks is no double-click
        if command == commands.KNIFE_MIRROR_VARIANT:
            return controller.cycle_variant() if self.view is not None else False
        if command == commands.CANCEL:
            return self.cancel()
        if command == commands.KNIFE_COMMIT:
            return self.commit()
        if command == commands.KNIFE_LIFT:
            return False if self.gesture else self.lift()
        if command in (commands.UNDO, commands.REDO):
            return self._history_step(command)
        if command == commands.TOGGLE_ORTHO:
            # View state like the orbit, which the session allows; the planner plans with the live camera.
            return controller.services.toggle_ortho()
        return False

    def _owns_press(self, input) -> bool:
        # The unmodified and the Shift-only LMB (midpoint snap, UX2 D11) are the Knife's, and a button bound to
        # KnifeLift (RMB); Alt+LMB (orbit / pan), Ctrl+LMB and the other buttons keep going through the pointer
        # gestures. (The app routes a press only while no pointer gesture is active.)
        if input.kind != "mouse" or self.gesture:
            return False
        if input.value == "LEFT" and input.modifiers <= {"shift"}:
            return True
        return self._controller.services.bindings.command_for(input, KNIFE_CONTEXT) == commands.KNIFE_LIFT

    def _press(self, input) -> None:
        """Press: only starts the click-threshold gesture (B7.1); the preview is recomputed with the press's own
        Shift (the click decides by the press modifiers, AD-019) - with a held Shift the hover showed the same
        midpoint already (UX2b)."""
        self.gesture = True
        self.gesture_moved = 0.0
        self.gesture_button = input.value
        self.gesture_midpoint = input.value == "LEFT" and "shift" in input.modifiers
        cursor = self._controller.services.cursor
        if cursor is None or input.value != "LEFT":
            return
        self.set_preview(self._controller.pick(*cursor, midpoint=self.gesture_midpoint))

    def _release(self, x: float, y: float) -> bool:
        """Release: press+release under the click threshold is a click - LMB adds the point at the cursor, the
        second LMB click of a double-click finishes the chain, an RMB click lifts the pen; a press that moved
        past the threshold is not a click and does nothing (Playground click rule, B7.1). A click outside the
        mesh adds a point in space (S4); it never commits."""
        controller = self._controller
        services = controller.services
        knife = self.tool
        moved = self.gesture_moved
        self.gesture = False
        self.gesture_moved = 0.0
        last, self.last_click = self.last_click, None
        if moved >= CLICK_THRESHOLD_PX:
            services.refresh_hover()
            return False
        if self.gesture_button != "LEFT":
            return self.lift()
        now = controller.clock()
        if (
            last is not None
            and now - last[0] <= KNIFE_DOUBLE_CLICK_S
            and math.hypot(x - last[1], y - last[2]) <= KNIFE_DOUBLE_CLICK_PX
            and knife.plan_lift(close=True).ok
        ):
            return self.lift(finish=True)
        target = controller.pick(x, y, midpoint=self.gesture_midpoint)
        self.last_click = (now, x, y)
        if not knife.click(target):
            plan = knife.last_plan
            # A symmetric refusal (F3 = A) carries its own status text; the click was ignored.
            services.status(plan.reason if plan.refused
                            else KNIFE_REFUSED.get(plan.reason, "Knife: no valid cut target here"))
            services.refresh_hover()
            return False
        # WP-KNIFE-01 S2: a click only adds a point to the session's path - the mesh (and with it the pick
        # cache) is unchanged until commit.
        plan = knife.last_plan
        cuts = len(knife.cut_segments)
        segments = f"{cuts} path {'segment' if cuts == 1 else 'segments'}"
        crossings = f"{len(plan.crossings)} crossing(s)" if plan.crossings else "the line crosses nothing"
        if plan.start:
            where = " on an earlier point" if plan.earlier else " in space" if target["kind"] == "space" else ""
            status = "Knife: start point set" + where
        elif plan.closing:
            status = f"Knife: shape closed - the next click cuts on from its start ({segments})"
        elif plan.skip:
            status = f"Knife: along an existing edge - nothing to cut ({segments})"
        elif target["kind"] == "space":
            status = f"Knife: point in space - {crossings} ({segments})"
        elif plan.method:
            status = f"Knife: cut across {crossings} ({segments})"
        else:
            status = f"Knife: cut ({segments})"
        self.say("; ".join([status] + knife_plan_notes(plan)))
        services.refresh_hover()
        return True

    def lift(self, finish: bool = False) -> bool:
        """Pen lift (`E` / RMB click), or close + lift (`finish`, the double-click): the chain ends, nothing is
        committed, the next click starts a new chain (UX2)."""
        services = self._controller.services
        knife = self.tool
        self._controller.set_view()  # the close may run across faces (S4)
        if not (knife.finish_chain() if finish else knife.lift()):
            services.status("Knife: nothing to lift")
            return False
        plan = knife.last_plan
        what = "shape closed, pen lifted" if plan.closing or plan.replaces else plan.reason
        self.say(f"Knife: {what} - the next click starts a new cut")
        services.refresh_hover()
        return True

    def _history_step(self, command: str) -> bool:
        """In-session Undo/Redo (AD-017 DECIDED): only the session's own steps, never the global history - from
        a key and from the API alike. Ignored while the Knife's LMB is held."""
        if self.gesture:
            return False
        services = self._controller.services
        undo = command == commands.UNDO
        done = self.tool.undo_step() if undo else self.tool.redo_step()
        if not done:
            services.status(f"Knife: nothing to {'undo' if undo else 'redo'}")
            return False
        self.say("Knife: last cut undone" if undo else "Knife: cut redone")
        services.refresh_hover()
        return True

    def say(self, message: str) -> None:
        """A Knife status message; a symmetric session names its mirror preview variant in it."""
        if self.view is not None:
            message += f" [Spiegel {self._controller.mirror_variant}]"
        self._controller.services.status(message)

    # -- the preview -----------------------------------------------------------------------------------

    def hover(self, x: float, y: float) -> bool:
        return self.set_preview(self._controller.pick(x, y, midpoint=self._controller.services.modifiers[0]))

    def set_preview(self, target: dict) -> bool:
        """Prospective target = `target` only if the click would be accepted (`KnifeTool.plan`, the same rules
        as `accepts`); invalid → no point, no line (`PROVISIONAL`); S4: with the segment's planned crossings.
        True = changed."""
        plan = self.tool.plan(target)
        prospective = target if plan.ok else None
        highlight = target["edge_id"] if plan.ok and target.get("kind") == "edge" else None
        crossings = tuple(tuple(c) for c in plan.crossings) if plan.ok else ()
        refused = target if plan.refused else None
        changed = (prospective, highlight, crossings, refused) != (
            self.target, self.highlight_edge, self.hover_crossings, self.refused)
        self.target = prospective
        self.highlight_edge = highlight
        self.hover_crossings = crossings
        self.refused = refused
        self._refusal_status(plan.reason if plan.refused else None)
        self._controller.sync_overlay()
        return changed

    def _refusal_status(self, text: str | None) -> None:
        """Hover refusal (F3 = A): the refused target's reason is shown while it is hovered - once, not on
        every mouse move - and the status returns to the session's note when the hover leaves it."""
        if text == self.refused_text:
            return
        self.refused_text = text
        self._controller.services.status(text if text is not None else f"Knife: {self._controller.mirror_text()}")

    def clear_preview(self) -> bool:
        changed = self.target is not None or self.highlight_edge is not None or self.refused is not None
        self.target = None
        self.highlight_edge = None
        self.hover_crossings = ()
        self.refused = None
        self._refusal_status(None)
        self._controller.sync_overlay()
        return changed

    def render_data(self) -> KnifeRenderData:
        knife = self.tool
        data = build_knife_render_data(
            self._controller.services.scene.mesh,
            [_DRAWN_LIFT if p.get("reason") == "lift" else p for p in knife.path],
            self.target,
            self.highlight_edge,
            self.hover_crossings,
            symmetry=self.view,
            refused=self.refused,
            pen_up=self.view is not None and knife.last_point is None,
        )
        if self.view is None and knife.last_point is None:
            # After a pen lift no point starts the next segment: no start marker, no rubber band.
            data = dataclasses.replace(data, start_point=None, line_preview=None)
        return data


class KnifeController:
    """`C` with an empty selection begins a session (`begin`); the mirror preview variant (kept across sessions
    of this app) and the double-click clock (`clock`, injectable for headless tests) are its settings."""

    def __init__(self, services: AppServices) -> None:
        self.services = services
        self.mirror_variant: str = KNIFE_MIRROR_VARIANT_DEFAULT
        self.clock: Callable[[], float] = time.monotonic

    @property
    def session(self) -> KnifeSession | None:
        session = self.services.interaction.session
        return session if isinstance(session, KnifeSession) else None

    @property
    def tool(self) -> KnifeTool | None:
        """The running session's `KnifeTool`, None without a session."""
        session = self.session
        return None if session is None else session.tool

    def render_data(self) -> KnifeRenderData | None:
        session = self.session
        return None if session is None else session.render_data()

    # -- begin / end -----------------------------------------------------------------------------------

    def begin(self, coordinator) -> bool:
        """AD-SYM-03 slice 6c: whenever a symmetry definition is set the session runs the declared coordinator
        (`coordinator`, from `mirai.symmetry_declarations`; D-b - the declaration is the only switch) and gets the
        session view that previews and refuses with the commit's own rules. A plane the coordinator cannot handle
        starts no session at all."""
        services = self.services
        if services.viewport is None:
            return False
        view = None
        if coordinator is not None:
            try:
                view = SymmetricKnifeView(services.scene.mesh)
            except KnifeRefusal as exc:
                services.status(str(exc))
                return False
        before = services.selection_snapshot()
        knife = KnifeTool()
        knife.activate()
        knife.begin(mesh=services.scene.mesh, scene=services.scene, selection=services.selection,
                    **({} if view is None else {"symmetric_commit": coordinator, "symmetric_view": view}))
        services.interaction.start(KnifeSession(self, knife, view, before))
        # R-SEL-2 (as in the Playground): the Knife draws its own preview, the selection hover must not stay drawn
        # underneath it.
        services.set_hovered(None)
        services.refresh_hover()
        services.status(
            "Knife: click on vertices, edges, inside faces or outside the mesh to cut - a far click cuts"
            " across faces, Shift+click = edge midpoint, E / right-click = new cut (pen lift),"
            " double-click = close + lift, Enter = commit, Esc = cancel, Ctrl+Z / Ctrl+Y = undo / redo"
            + ("" if view is None else f" - {self.mirror_text()}")
        )
        return True

    def end(self, session: KnifeSession, commit: bool) -> bool:
        """Enter = commit (exactly one history entry, residue = path edges selected, Edge mode); Esc = cancel
        (mesh, selection and history exactly as before the session)."""
        services = self.services
        knife = session.tool
        if commit:
            command = knife.commit()
        else:
            knife.cancel()
            command = None
        knife.deactivate()
        services.interaction.end(session)
        notes = knife_notes(knife.last_resolution) if commit else []
        if command is not None:
            services.record_selection_history(session.selection_before)
            count = len(services.selection.edges)
            status = f"Knife committed ({count} path {'edge' if count == 1 else 'edges'} selected)"
            res = knife.last_resolution
            if res is not None and res.applied < res.runs:
                # Valid while clicking, dropped at commit (the run would have left its face) - the Q5 "N-1/N"
                # note (WP-KNIFE-01 S2).
                status += f" - {res.runs - res.applied} of {res.runs} cuts dropped"
            services.status("; ".join([status] + notes))
        elif commit and knife.last_problem is not None:
            services.status(f"Knife: result taken back ({knife.last_problem}), nothing committed")
        elif commit:
            services.status("Knife: no cuts made, nothing committed" + (f" ({'; '.join(notes)})" if notes else ""))
        else:
            services.status("Knife cancelled")
        services.invalidate_picks()
        services.viewport.set_tool_overlay()
        services.viewport.on_topology_changed()
        services.viewport.on_selection_changed()
        services.soft_preview_refresh()
        services.refresh_hover()
        return True

    def shutdown(self) -> None:
        """A running session is discarded (as Esc)."""
        session = self.session
        if session is not None:
            session.cancel()

    # -- the mirror preview variant (slice 6c) ---------------------------------------------------------

    def mirror_text(self) -> str:
        """The symmetric session's note in the status line: the active mirror preview variant and its key."""
        variant = self.mirror_variant
        # The bound key, not a literal (as `SymmetryController.summary`): a keymap.json rebinding shows up here.
        bound = [inp for inp in self.services.bindings.inputs_for(commands.KNIFE_MIRROR_VARIANT, KNIFE_CONTEXT)
                 if inp.kind == "key"]
        return (f"Spiegelvorschau {variant} ({KNIFE_MIRROR_VARIANT_LABELS[variant]}), "
                f"Taste {key_label(bound[0]) if bound else '?'} wechselt V-a / V-b / V-c")

    def cycle_variant(self) -> bool:
        """The provisional variant key: V-a -> V-b -> V-c -> V-a (symmetric session only)."""
        order = KNIFE_MIRROR_VARIANTS
        self.mirror_variant = order[(order.index(self.mirror_variant) + 1) % len(order)]
        self.sync_overlay()
        self.services.status(f"Knife: {self.mirror_text()}")
        return True

    # -- picking and drawing ---------------------------------------------------------------------------

    def pick(self, x: float, y: float, midpoint: bool = False) -> dict:
        """WP-06 B8: same cache/occlusion as the app's pick - a hidden edge/vertex cannot be a Knife target
        while faces are shown. WP-KNIFE-01 S2: then the session's own edge points (`snap_own_point`) - a click
        on one reaches that point again, as the real-cut Knife's split vertex did. UX2 `midpoint` (Shift): an
        edge target moves to t = 0.5 - after the own-point snap, which wins - or to an own point already there.
        S4: the knife gets the live view first (the planner plans with the camera of this hover / click);
        outside the mesh the target is a point in space. Without a session: the raw `knife_pick` target."""
        services = self.services
        cache = services.pick_cache
        show_faces = services.display.show_faces
        mesh = services.scene.mesh
        camera = services.edit_camera
        kwargs = {"cache": cache, "occlusion": show_faces}
        size = services.viewport_size
        if show_faces:
            # One Knife pick runs several occlusion tests (vertex, edge, face, own points): build the
            # screen grid at once instead of after `GRID_AFTER_SCANS` whole-mesh scans.
            cache.refresh(camera, mesh, *size)
            cache.face_grid(mesh, batch=True)
        target = knife_pick(camera, mesh, x, y, *size, **kwargs)
        knife = self.tool
        if knife is None:
            return target
        self.set_view()
        # Also over "outside": the real-cut Knife's split vertex was caught by the
        # 14 px vertex pick just off the silhouette too.
        target = snap_own_point(camera, mesh, x, y, *size, knife.snap_points, target, **kwargs)
        if target.get("kind") == "outside":
            return {"kind": "space", "position": space_point(camera, x, y, *size)}
        if not midpoint or target.get("kind") != "edge":
            return target
        eid = target["edge_id"]
        own = next((p for p in knife.snap_points if p["kind"] == "edge" and p["edge_id"] == eid
                    and abs(p["t"] - 0.5) <= GEO_EPS), None)
        return {"kind": "point", "pid": own["pid"]} if own is not None else dict(target, t=0.5)

    def set_view(self) -> None:
        """The live camera for the planner (S4) - set before every hover / click plan."""
        services = self.services
        width, height = services.viewport_size
        self.tool.set_view(services.edit_camera, width, height,
                           cache=services.pick_cache, occlusion=services.display.show_faces)

    def sync_overlay(self) -> None:
        """Knife render data → viewport tool layers: prospective point, target edge and line preview in the
        hover style, the placed points (the start among them) and the segments commit will cut in the selected
        style (no new look; WP-KNIFE-01 S2: drawn from the path, the mesh is not cut before commit).

        A symmetric session (slice 6c) adds the layers of the mirror, of the part that will not be cut and of
        the refused hover (`render_data`'s fields; the mirror per variant, `KNIFE_MIRROR_VARIANTS`). Without a
        symmetry view only the two layers above are passed, exactly as before."""
        viewport = self.services.viewport
        session = self.session
        if viewport is None or session is None:
            return
        data = session.render_data()
        points = {
            TOOL_PREVIEW_LAYER: [p for p in (data.prospective_point,) if p is not None]
            + list(data.prospective_crossings),
            TOOL_ACTIVE_LAYER: list(data.placed_points),
        }
        segments = {
            TOOL_PREVIEW_LAYER: [
                s for s in (data.target_edge, data.line_preview) if s is not None
            ],
            TOOL_ACTIVE_LAYER: list(data.path_segments),
        }
        if session.view is not None:
            mirror_points = list(data.mirror_placed_points)
            mirror_hover_points = [p for p in (data.mirror_prospective_point,) if p is not None] + list(
                data.mirror_prospective_crossings)
            mirror_path = list(data.mirror_path_segments)
            mirror_hover = [s for s in (data.mirror_target_edge, data.mirror_line_preview) if s is not None]
            variant = self.mirror_variant
            if variant == "V-a":       # like the working side's own preview
                points[TOOL_MIRROR_LAYER] = mirror_points
                points[TOOL_MIRROR_PREVIEW_LAYER] = mirror_hover_points
                segments[TOOL_MIRROR_LAYER] = mirror_path
                segments[TOOL_MIRROR_PREVIEW_LAYER] = mirror_hover
            elif variant == "V-b":     # always visible, dimmed
                points[TOOL_MIRROR_DIM_LAYER] = mirror_points + mirror_hover_points
                segments[TOOL_MIRROR_DIM_LAYER] = mirror_path + mirror_hover
            else:                      # V-c: the mirror's points only
                points[TOOL_MIRROR_LAYER] = mirror_points + mirror_hover_points
            points[TOOL_CLIPPED_LAYER] = list(data.clipped_points) + list(data.clipped_hover_points)
            segments[TOOL_CLIPPED_LAYER] = list(data.clipped_segments) + list(data.clipped_hover_segments)
            points[TOOL_REFUSED_LAYER] = list(data.refused_points)
            segments[TOOL_REFUSED_LAYER] = list(data.refused_segments)
        viewport.set_tool_overlay(points=points, segments=segments)
