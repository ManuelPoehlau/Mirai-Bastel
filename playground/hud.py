"""PlaygroundHUD — Standalone-HUD-Klasse für das Artist Playground.

Zeigt drei Informationszeilen:
    1. Camera: Orbit yaw={:.1f} pitch={:.1f} dist={:.2f}
    2. Mesh: V:{} E:{} F:{}
    3. Experiment: [{id}] {name} {variant}

Bekannte pyglet-Constraints (aus WP-IL-01):
    - \\n ohne multiline=True → Text unsichtbar
    - program.stop() vor Label.draw() nötig (Shader-State)
    - width muss bei multiline=True gesetzt sein

Lazy-Init: pyglet wird erst beim ersten draw()-Aufruf importiert
(damit die Klasse in Headless-Tests ohne GL-Kontext konstruierbar ist).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playground.experiment import Experiment


class PlaygroundHUD:
    """Standalone-HUD für das Playground-Fenster.

    Konstruktion ist headless-sicher (kein pyglet-Import im __init__).
    pyglet.text.Label wird lazy beim ersten draw() erstellt.
    """

    def __init__(self, x: int = 10, y_bottom: int = 10, width: int = 800) -> None:
        self._x = x
        self._y_bottom = y_bottom
        self._width = width

        # Aktueller HUD-State (vor dem ersten draw() setzbar)
        self._camera_line = "Camera: —"
        self._mesh_line = "Mesh: —"
        self._experiment_line = "Experiment: [none] No Experiment"
        self._display_line = "Display: Shaded"
        self._selection_line = "Selection: none"

        # Lazy-init Label-Objekte
        self._label = None
        self._window_height = 600  # Fallback, wird von update_layout() gesetzt

    # -- State-Update ---------------------------------------------------------

    def update_camera(self, yaw: float, pitch: float, distance: float) -> None:
        """Kamera-Zeile aktualisieren (Winkel in Radiant → Grad für Anzeige)."""
        self._camera_line = (
            f"Camera: Orbit yaw={math.degrees(yaw):.1f} "
            f"pitch={math.degrees(pitch):.1f} dist={distance:.2f}"
        )
        self._invalidate()

    def update_mesh(self, vertex_count: int, edge_count: int, face_count: int) -> None:
        """Mesh-Info-Zeile aktualisieren."""
        self._mesh_line = f"Mesh: V:{vertex_count} E:{edge_count} F:{face_count}"
        self._invalidate()

    def update_display(self, label: str) -> None:
        """Display-Mode-Zeile aktualisieren (AP-02.5)."""
        self._display_line = f"Display: {label}"
        self._invalidate()

    def update_selection(self, n: int, mode_label: str = "", comp_label: str = "") -> None:
        """Selection-Zeile aktualisieren (AP-03 Phase 5)."""
        unit = comp_label.lower() if comp_label else "face"
        if n == 0:
            self._selection_line = "Selection: none"
        elif n == 1:
            self._selection_line = f"Selection: 1 {unit}"
        else:
            self._selection_line = f"Selection: {n} {unit}s"
        parts = [p for p in (comp_label, mode_label) if p]
        if parts:
            self._selection_line += f"  [{' | '.join(parts)}]"
        self._invalidate()

    def update_experiment(self, experiment: "Experiment", decision: str = "") -> None:
        """Experiment-Zeile aktualisieren.

        `decision` ist optional (WP-AP-02): z.B. "KEEP", "ITERATE", "REJECT".
        """
        variant = f" {experiment.variant}" if experiment.variant else ""
        status = f" [{decision}]" if decision and decision != "UNDECIDED" else ""
        self._experiment_line = (
            f"Experiment: [{experiment.id}] {experiment.name}{variant}{status}"
        )
        self._invalidate()

    def update_layout(self, window_width: int, window_height: int) -> None:
        """Fenster-Dimensionen übergeben (für Label-Positionierung)."""
        self._window_height = window_height
        self._width = window_width - 20
        if self._label is not None:
            self._label.width = self._width
        self._invalidate()

    # -- Lazy-Init + Zeichnung ------------------------------------------------

    def _invalidate(self) -> None:
        """Text-Cache invalidieren, damit draw() den Label neu setzt."""
        if self._label is not None:
            self._label.text = self._full_text()

    def _full_text(self) -> str:
        return (
            f"{self._camera_line}\n{self._mesh_line}\n"
            f"{self._experiment_line}\n{self._display_line}\n{self._selection_line}"
        )

    def _ensure_label(self) -> None:
        """Label lazy anlegen (erster draw()-Aufruf)."""
        import pyglet  # noqa: PLC0415 — lazy import für Headless-Sicherheit

        if self._label is None:
            self._label = pyglet.text.Label(
                self._full_text(),
                x=self._x,
                y=self._y_bottom,
                anchor_y="bottom",
                font_name="Consolas",
                font_size=12,
                color=(220, 235, 255, 255),
                multiline=True,
                width=self._width,
            )

    def draw(self) -> None:
        """HUD zeichnen.

        Muss nach program.stop() aufgerufen werden (Shader-State,
        bekannte Constraint aus WP-IL-01).
        """
        self._ensure_label()
        self._label.draw()

    # -- Lese-API für Tests ---------------------------------------------------

    @property
    def camera_line(self) -> str:
        return self._camera_line

    @property
    def mesh_line(self) -> str:
        return self._mesh_line

    @property
    def experiment_line(self) -> str:
        return self._experiment_line

    @property
    def display_line(self) -> str:
        return self._display_line

    @property
    def selection_line(self) -> str:
        return self._selection_line
