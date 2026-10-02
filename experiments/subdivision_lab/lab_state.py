"""View state of the Subdivision Mini-Lab (GL-free).

Everything the HUD shows and everything a key press changes lives here, so it
is testable without a window. Level and view mode are **view state** (handoff
D8): not document state, no undo. Whether the level belongs to the document is
an open architecture question (research OF-3) — this lab does not answer it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .subd import predicted_face_count

VIEW_CAGE = "V-CAGE"
VIEW_BOTH = "V-BOTH"
VIEW_ISO = "V-ISO"
VIEW_ORDER = (VIEW_CAGE, VIEW_BOTH, VIEW_ISO)
VIEW_LABELS = {
    VIEW_CAGE: "Käfig (heutiger Stand)",
    VIEW_BOTH: "glatte Fläche + Käfig",
    VIEW_ISO: "glatte Fläche + Isolinien",
}

LEVELS = (1, 2, 3)
DEFAULT_LEVEL = 1
#: PROVISIONAL, agent-set (handoff §3.4): a level that would exceed this many
#: derived faces is refused. Not a measured limit of the reference PC.
MAX_DERIVED_FACES = 25_000

#: Frame-time smoothing (exponential moving average), precedent `viewport_shading_lab`.
FRAME_EMA = 0.1


@dataclass(frozen=True)
class HudLine:
    text: str
    #: "title" | "normal" | "active" | "inactive" | "warning" (colors live in the window)
    style: str


class LabState:
    def __init__(self, control_face_sizes, n_control_vertices: int = 0, host_label: str = "unlabeled") -> None:
        self.control_face_sizes = tuple(control_face_sizes)
        self.control_counts = (n_control_vertices, len(self.control_face_sizes))
        self.host_label = host_label
        self.view = VIEW_CAGE
        self.level = DEFAULT_LEVEL
        self.ab_active = False
        self.hud_visible = True
        self.cage_depth_test = True
        self.warning: Optional[str] = None
        #: (vertices, faces) of the currently displayed derived surface, or None
        self.derived_counts: Optional[tuple[int, int]] = None
        self.last_build_ms: Optional[float] = None
        self.last_drag_ms: Optional[float] = None
        self.gl_version = "?"
        self.gl_renderer = "?"
        self.note: Optional[str] = None
        #: Bumped on every change a HUD line depends on (frame time aside).
        self.revision = 0

    def _touch(self) -> None:
        self.revision += 1

    # -- derived views of the state -------------------------------------------------

    def effective_view(self) -> str:
        """The view actually drawn: A/B temporarily shows the control mesh only."""
        return VIEW_CAGE if self.ab_active else self.view

    def needs_surface(self) -> bool:
        return self.effective_view() != VIEW_CAGE

    def predicted_faces(self, level: int) -> int:
        return predicted_face_count(self.control_face_sizes, level)

    # -- commands (return nothing unless a refusal needs reporting) --------------------

    def cycle_view(self) -> str:
        self.view = VIEW_ORDER[(VIEW_ORDER.index(self.view) + 1) % len(VIEW_ORDER)]
        self.warning = None
        self._touch()
        return self.view

    def request_level(self, level: int) -> bool:
        """Switches to `level`; refuses (False, warning set, state untouched)
        when it would exceed `MAX_DERIVED_FACES` or is not a lab level."""
        if level not in LEVELS:
            self.warning = f"Stufe {level} gibt es nicht (Stufen: {', '.join(map(str, LEVELS))})."
            self._touch()
            return False
        faces = self.predicted_faces(level)
        if faces > MAX_DERIVED_FACES:
            faces_text = f"{faces:,}".replace(",", ".")
            limit_text = f"{MAX_DERIVED_FACES:,}".replace(",", ".")
            self.warning = (
                f"Stufe {level} abgelehnt: {faces_text} Flächen > Limit {limit_text} "
                "(provisorisch, vom Agent gesetzt)."
            )
            self._touch()
            return False
        self.level = level
        self.warning = None
        self._touch()
        return True

    def toggle_cage_depth(self) -> bool:
        self.cage_depth_test = not self.cage_depth_test
        self._touch()
        return self.cage_depth_test

    def toggle_ab(self) -> bool:
        self.ab_active = not self.ab_active
        self._touch()
        return self.ab_active

    def toggle_hud(self) -> bool:
        self.hud_visible = not self.hud_visible
        self._touch()
        return self.hud_visible

    def set_derived_counts(self, counts: Optional[tuple[int, int]]) -> None:
        if counts != self.derived_counts:
            self.derived_counts = counts
            self._touch()

    def record_build(self, ms: float) -> None:
        self.last_build_ms = ms
        self._touch()

    def record_drag(self, ms: float) -> None:
        self.last_drag_ms = ms
        self._touch()

    def set_gl_info(self, version: str, renderer: str) -> None:
        self.gl_version, self.gl_renderer = version, renderer
        self._touch()

    def set_note(self, note: Optional[str]) -> None:
        self.note = note
        self._touch()

    # -- HUD ------------------------------------------------------------------------------

    def hud_lines(self, frame_ms: Optional[float]) -> list[HudLine]:
        cv, cf = self.control_counts
        lines = [HudLine("Mirai — Subdivision-Mini-Lab (Nicht Artist-validiert)", "title")]
        view_text = f"Ansicht: {self.view} — {VIEW_LABELS[self.view]}"
        if self.ab_active:
            view_text += "   [A/B aktiv: zeigt Käfig]"
        lines.append(HudLine(view_text, "active"))
        lines.append(HudLine(f"Stufe: {self.level}   (Tasten 1 / 2 / 3)", "normal"))
        lines.append(HudLine(f"Control: {cv} V / {cf} F", "normal"))
        if self.derived_counts is None:
            lines.append(HudLine("Fläche: (nicht aufgebaut)", "inactive"))
        else:
            dv, df = self.derived_counts
            lines.append(HudLine(f"Fläche (Stufe {self.level}): {dv} V / {df} F", "normal"))
        depth = "an" if self.cage_depth_test else "aus (immer sichtbar)"
        style = "normal" if self.effective_view() == VIEW_BOTH else "inactive"
        lines.append(HudLine(f"Käfig-Tiefentest: {depth}   (Taste X)", style))
        lines.append(HudLine(
            "Aufbau/Refresh (letzter): " + (f"{self.last_build_ms:.1f} ms" if self.last_build_ms is not None else "—"),
            "normal"))
        lines.append(HudLine(
            "Drag-Update (letzter): " + (f"{self.last_drag_ms:.2f} ms" if self.last_drag_ms is not None else "—"),
            "normal"))
        if frame_ms is None:
            lines.append(HudLine("Frame: —", "normal"))
        else:
            lines.append(HudLine(f"Frame (gleitend): {frame_ms:.1f} ms ({1000.0 / frame_ms:.0f} FPS)", "normal"))
        lines.append(HudLine(f"GL_VERSION: {self.gl_version}", "normal"))
        lines.append(HudLine(f"GL_RENDERER: {self.gl_renderer}", "normal"))
        lines.append(HudLine(f"Host-Label: {self.host_label}", "inactive"))
        if self.note:
            lines.append(HudLine(self.note, "normal"))
        if self.warning:
            lines.append(HudLine(self.warning, "warning"))
        lines.append(HudLine("H: HUD aus   Esc: Beenden", "inactive"))
        return lines
