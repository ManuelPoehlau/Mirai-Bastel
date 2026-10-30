"""SymmetryController (AD-027 §3.4): the symmetry definition cycle (Shift+S), the symmetry display and
its report cache, and the Re-Symmetrize preview as a session in the slot (AD-SYM-04 A1-A3).

Behaviour as it was inside `Application` (AD-027 M1 moves it, nothing else): the texts and rules are
AD-SYM-04's, the preview's precedence is AD-027 §1.1 V7 (it grabs keys, hover, select / region clicks,
select / Tweak drags and Soft wheel steps, and swallows the gizmo press - not the raw LMB press, so a
held Working Pivot still places under it).
"""

from __future__ import annotations

from typing import Optional

from core import Mesh

from ..interaction import commands
from ..interaction.session import (
    PASS,
    SILENT,
    Drag,
    Hover,
    KeyPress,
    Outcome,
    Press,
    Refusal,
    Release,
    RunContext,
    Wheel,
)
from ..resymmetrize import (
    ResymmetrizeRejected,
    ResymPlan,
    plan_description,
    plan_resymmetrize,
    plan_summary,
    set_plan_positions,
)
from ..subdivision.preview import key_label
from ..symmetry import CorrespondenceState, symmetry_state, vertex_correspondence
from ..symmetry_axis import current_axis, next_axis, set_symmetry_axis
from ..symmetry_display import ReportCache, SymmetryDisplay
from .services import AppServices

#: AD-SYM-04 A3: what an open Re-Symmetrize preview answers to every other bound key, click or
#: Soft step (the Lab's text, `PROVISIONAL`); the plan summary follows it so it stays readable.
RESYM_PREVIEW_HINT = "Vorschau aktiv — Befehl ignoriert"

#: The display commands that pass the preview (the Lab's preview row: display commands only), and
#: what it lets through from any source (AD-027 §3.3: its `allows`).
_PREVIEW_DISPLAY = frozenset(
    {
        commands.CYCLE_DISPLAY_MODE,
        commands.TOGGLE_WIREFRAME_OVERLAY,
        commands.SET_SHADED,
        commands.SET_FLAT_SHADED,
        commands.SET_WIREFRAME,
        commands.TOGGLE_REFERENCE_GHOST,
        commands.CYCLE_LIGHT_PRESET,
        commands.TOGGLE_LIGHT_SPACE,
        commands.TOGGLE_REGION_TINT,
        commands.TOGGLE_ORTHO,
    }
)
_PREVIEW_ALLOWS = _PREVIEW_DISPLAY | {commands.RESYMMETRIZE, commands.CANCEL}

_CLICKS = frozenset(
    {commands.SELECT, commands.SELECT_ADD, commands.SELECT_REMOVE, commands.SELECT_TOGGLE, commands.REGION_CLICK}
)
_DRAGS = frozenset({commands.SELECT_DRAG, commands.SELECT_DRAG_ADD, commands.TWEAK})


def symmetry_status_text(mesh: Mesh) -> str:
    """Status line after a symmetry cycle step (AD-SYM-04 Q-2 = S-2, its status part S-1; text
    `PROVISIONAL`): `Symmetrie X (valid)`, `Symmetrie X (partial, 54 ohne Partner)`,
    `Symmetrie aus`."""
    axis = current_axis(mesh)
    if axis is None:
        return "Symmetrie aus"
    states = [c.state for c in vertex_correspondence(mesh).values()]
    details = [symmetry_state(mesh).value]
    unpaired = states.count(CorrespondenceState.UNPAIRED)
    ambiguous = states.count(CorrespondenceState.AMBIGUOUS)
    if unpaired:
        details.append(f"{unpaired} ohne Partner")
    if ambiguous:
        details.append(f"{ambiguous} mehrdeutig")
    return f"Symmetrie {axis} ({', '.join(details)})"


class ResymPreview:
    """The open Re-Symmetrize preview (AD-SYM-04 A3, §10 R-a): the plan computed once when it opened,
    executed exactly as shown. An exclusive session (`interaction_owner` "resymmetrize")."""

    owner = "resymmetrize"
    label = "Re-Symmetrize"
    exclusive = True

    def __init__(self, controller: "SymmetryController", plan: ResymPlan) -> None:
        self._controller = controller
        self.plan = plan

    def grabs(self, event) -> bool:
        if isinstance(event, (KeyPress, Hover)):
            return True
        if isinstance(event, Release):
            return event.click in _CLICKS
        if isinstance(event, Drag):
            return event.command in _DRAGS
        if isinstance(event, Wheel):
            return event.command is not None  # only the Soft wheel steps reach the slot (zoom is navigation)
        return False

    def allows(self, command: str, ctx: RunContext) -> Optional[Refusal]:
        if command in _PREVIEW_ALLOWS:
            return None
        if ctx.source == "drag":
            return SILENT  # the select / Tweak drags never answered (navigation still runs)
        return Refusal(self._controller.preview_hint())

    def handle(self, event) -> Outcome:
        controller = self._controller
        if isinstance(event, KeyPress):
            # Keys while the preview is open: the Re-Symmetrize key executes, Cancel closes, the pure
            # display keys pass (to the key path); every other bound key is ignored with the hint.
            # Navigation is pointer input and never reaches here.
            command = controller.services.bindings.command_for(event.input)
            if command == commands.RESYMMETRIZE:
                return self.commit()
            if command == commands.CANCEL:
                self.cancel()
                controller.services.status("Re-Symmetrize abgebrochen")
                return True
            if command in _PREVIEW_DISPLAY:
                return PASS
            if command is not None:
                controller.refuse()
            return False
        if isinstance(event, Hover):
            # The Lab paused the hover through the host gate (`hover_suspended`); the preview does it itself.
            return controller.services.set_hovered(None)
        if isinstance(event, (Release, Wheel)):
            controller.refuse()
            return False
        if isinstance(event, Drag):
            return False  # the preview owns the mesh and the selection; navigation still runs
        if isinstance(event, Press):
            return False  # no gizmo press under the preview (the press itself goes on to the resolver)
        return PASS

    def cancel(self) -> bool:
        self._controller.close()
        return True

    def commit(self) -> bool:
        return self._controller.execute(self)


class SymmetryController:
    """Shift+S, the symmetry display (Shift+Ctrl+S) with its reports, and Re-Symmetrize (Alt+M)."""

    def __init__(self, services: AppServices) -> None:
        self.services = services
        # AD-SYM-04 A2 (Q-2 = S-2): plane outline and problem markers; None = headless (no
        # `symmetry_overlay_type`, no display work at all).
        self.display: SymmetryDisplay | None = None
        # AD-SYM-04 SS3 (`PROVISIONAL`): one symmetry report per geometry, shared by the display
        # and the soft preview, so the preview takes its correspondence from it instead of
        # pairing the mesh per trigger. Keyed by `geometry_signature` (definition, ids,
        # positions, seam), so Undo/Redo, topology, Shift+S and a scene load make it stale by
        # construction; `mirai.symmetry` stays cache-free (AR-1/INV-3) and the tools still pair
        # once per gesture start for the op itself. Fresh per scene (`reset_reports`).
        self.reports = ReportCache(defer=self.display_deferred)

    # -- scene lifecycle (`Application.init_scene`) ------------------------------------------------

    def reset_reports(self) -> None:
        self.reports = ReportCache(defer=self.display_deferred)

    def attach_display(self, overlay_type) -> None:
        """A new viewport: the old preview and display go; a new display when the host has a sink."""
        services = self.services
        session = services.interaction.session
        if isinstance(session, ResymPreview):
            services.interaction.end(session)
        self.display = None
        if overlay_type is not None:
            self.display = SymmetryDisplay(overlay_type(), reports=self.reports, preview=self.preview_plan)
            services.viewport.add_overlay(self.display)

    def display_deferred(self) -> bool:
        # Plan A3 of WP-SYM-LAB-03 (`mirai.symmetry_display`): while W/E/R/T is armed or running
        # a pure position change is not re-derived; the markers still follow the moved vertices.
        return self.services.interaction_owner == "transform"

    # -- Shift+S (AD-SYM-04 A1) --------------------------------------------------------------------

    def cycle(self) -> bool:
        """Shift+S (Q-1 = E-1): off → X → Y → Z → off, one Undo step per press (E2), E1 plane
        and E3 seam from `mirai.symmetry_axis`. Not while an interaction owns the keys (R-4): an
        armed W/E/R/T has resolved its partner set at arm/`begin()`, a Knife session its
        symmetry view at begin, and a changed definition must not slide in underneath them.
        The change is reported to the viewport as a topology change (K-3): a definition-only
        change moves nothing, but every overlay that reads the definition must re-derive, the
        soft bands too (the symmetric field under a definition, AD-SYM-04 D-5) - the same
        notification Undo of it gets."""
        services = self.services
        if services.interaction_owner is not None:
            return False
        mesh = services.scene.mesh
        axis = next_axis(current_axis(mesh))
        changed = services.mesh_transaction(
            f"Symmetry {axis or 'off'}", lambda mesh: set_symmetry_axis(mesh, axis)
        ).changed
        services.status(symmetry_status_text(services.scene.mesh))
        return changed

    # -- the display (Shift+Ctrl+S, AD-SYM-04 A2) --------------------------------------------------

    def toggle_display(self) -> bool | None:
        display = self.display
        if display is None:
            return None
        display.visible = not display.visible
        self.services.status(f"Symmetry display: {'on' if display.visible else 'off'}")
        return display.visible

    def _display_changed(self) -> None:
        # Opening and closing change no mesh and tell the viewport nothing: the display re-syncs.
        if self.display is not None:
            self.display.dirty = True

    # -- Re-Symmetrize (AD-SYM-04 A3, §10 R-a) ----------------------------------------------------

    def preview(self) -> ResymPreview | None:
        session = self.services.interaction.session
        return session if isinstance(session, ResymPreview) else None

    def preview_plan(self) -> ResymPlan | None:
        preview = self.preview()
        return None if preview is None else preview.plan

    def summary(self) -> str:
        # The bound key, not a literal (as the HUD hints): a `keymap.json` rebinding shows up here.
        bound = [inp for inp in self.services.bindings.inputs_for(commands.RESYMMETRIZE) if inp.kind == "key"]
        return plan_summary(self.preview_plan(), key_label(bound[0]) if bound else "?")

    def preview_hint(self) -> str:
        return f"{RESYM_PREVIEW_HINT} | {self.summary()}"

    def refuse(self) -> None:
        self.services.status(self.preview_hint())

    def open(self) -> bool:
        """Re-Symmetrize key without a preview (the Lab's KEEP behaviour, M / M / Esc): exactly one
        selected vertex is the source; its topological side is mirrored onto the other side and the
        seam laid into the plane (`mirai.resymmetrize`). The plan is computed once here and shown;
        the next press executes exactly it, Esc closes it. Refused with the Lab's reasons."""
        services = self.services
        if services.interaction_owner is not None:
            return False
        mesh = services.scene.mesh
        selected = services.selection.vertices
        try:
            if mesh.symmetry_definition is None:
                raise ResymmetrizeRejected("Symmetrie aus")
            if not selected:
                raise ResymmetrizeRejected("keine Auswahl")
            if len(selected) != 1:
                raise ResymmetrizeRejected("genau einen Vertex auswählen")
            plan = plan_resymmetrize(mesh, next(iter(selected)))
        except ResymmetrizeRejected as exc:
            services.status(f"Re-Symmetrize: {exc}")
            return False
        services.interaction.start(ResymPreview(self, plan))
        services.set_hovered(None)
        self._display_changed()
        services.status(self.summary())
        return True

    def execute(self, preview: ResymPreview) -> bool:
        """Sets exactly the shown plan: one Undo step (selection kept and restored with it); an
        empty plan records nothing. The preview is closed first, so the transaction's hover
        refresh picks again."""
        services = self.services
        plan = preview.plan
        self.close()
        changed = services.mesh_transaction(
            plan_description(plan),
            lambda mesh: set_plan_positions(mesh, plan),
            moved_of=lambda moved: moved,
        ).changed
        if changed:
            services.status(f"Re-Symmetrize ausgeführt: {len(plan.changes)} Änderungen")
        else:
            services.status("Re-Symmetrize: 0 Änderungen — kein Schritt")
        return True

    def close(self) -> None:
        preview = self.preview()
        if preview is None:
            return
        self.services.interaction.end(preview)
        self._display_changed()
        self.services.refresh_hover()
