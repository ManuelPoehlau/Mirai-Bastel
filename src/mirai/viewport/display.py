"""Prozess-/Display-State für den Viewport-Praxistest (pyglet-frei).

Trennung nach WP-01A: Nur Zustand + gültige Übergänge. Die tatsächliche
Darstellung (Face-/Edge-Geometrie, Shader) entscheidet die Viewport-Schicht
in `app.py` anhand von `show_faces`/`show_edges` — hier wird bewusst KEIN
Renderer-/Material-Stack entworfen.

Sinnvolle Kombinationen (Ziel: "Flat Shaded + Wireframe" als wichtigster
praktischer Topology-Checkmodus):

    Shaded
    Shaded + Wireframe Overlay
    Flat Shaded
    Flat Shaded + Wireframe Overlay
    Wireframe
"""

from __future__ import annotations

from enum import Enum, auto

from viewport.light_rig import (
    APP_PRESET_ORDER,
    DEFAULT_PRESET,
    PRESETS,
    SPACE_CAMERA,
    SPACE_WORLD,
    LightRig,
)
from viewport.material import DEFAULT_FINISH, SurfaceFinish

#: Anzeige-Namen der Bezugsräume in der Statuszeile.
_SPACE_LABELS = {SPACE_CAMERA: "Kamera", SPACE_WORLD: "Welt"}

# Bevorzugte Anzeige-Reihenfolge für die Cycle-Aktion.
_MODE_CYCLE: tuple["DisplayMode", ...]


class DisplayMode(Enum):
    SHADED = auto()
    FLAT_SHADED = auto()
    WIREFRAME = auto()


_MODE_CYCLE = (DisplayMode.SHADED, DisplayMode.FLAT_SHADED, DisplayMode.WIREFRAME)


class DisplayState:
    def __init__(
        self,
        mode: DisplayMode = DisplayMode.SHADED,
        wireframe_overlay: bool = False,
    ) -> None:
        self.mode = DisplayMode(mode)
        self.wireframe_overlay = bool(wireframe_overlay)
        # Worklight (2026-10-15): Preset-Name und ein Bezugsraum, den der Artist umgeschaltet
        # hat (None = der des Presets). Der Umschalter bleibt beim Preset-Wechsel stehen.
        self.light_preset = DEFAULT_PRESET
        self.light_space: str | None = None
        # Glanz der Flächen (2026-10-23, `viewport.material`): Specular-Stärke, Glossiness und
        # Fill-Specular, `PROVISIONAL` Defaults. Ansichts-Zustand wie das Licht, keine Taste
        # (kein Material-Editor): `set_surface_finish(...)` ist die Schnittstelle.
        self.surface_finish: SurfaceFinish = DEFAULT_FINISH

    # -- Übergänge ----------------------------------------------------------

    def set_mode(self, mode: DisplayMode) -> None:
        """Setzt den Display-Modus; ungültige Werte werden abgelehnt."""
        self.mode = DisplayMode(mode)

    def cycle(self) -> None:
        """Wechselt in der Reihenfolge Shaded → Flat Shaded → Wireframe → ..."""
        index = _MODE_CYCLE.index(self.mode)
        self.mode = _MODE_CYCLE[(index + 1) % len(_MODE_CYCLE)]

    def toggle_wireframe_overlay(self) -> None:
        self.wireframe_overlay = not self.wireframe_overlay

    def set_wireframe_overlay(self, on: bool) -> None:
        self.wireframe_overlay = bool(on)

    def cycle_light_preset(self) -> None:
        """Raitt 2:1 → Softbox → Warm/Kalt → Heute → ..."""
        index = APP_PRESET_ORDER.index(self.light_preset)
        self.light_preset = APP_PRESET_ORDER[(index + 1) % len(APP_PRESET_ORDER)]

    def toggle_light_space(self) -> None:
        """Licht folgt der Kamera <-> steht in der Welt."""
        self.light_space = SPACE_WORLD if self.light_rig.space == SPACE_CAMERA else SPACE_CAMERA

    def set_surface_finish(self, **changes) -> SurfaceFinish:
        """Ändert `specular`, `glossiness` und/oder `fill_specular` (je 0..1, geklemmt)."""
        self.surface_finish = self.surface_finish.with_(**changes)
        return self.surface_finish

    @property
    def light_rig(self) -> LightRig:
        rig = PRESETS[self.light_preset]
        return rig if self.light_space is None else rig.with_(space=self.light_space)

    @property
    def light_label(self) -> str:
        return f"{self.light_preset} · {_SPACE_LABELS[self.light_rig.space]}"

    # -- Ableitungen für die Darstellung ------------------------------------

    @property
    def show_faces(self) -> bool:
        """Faces nur in Shaded/Flat Shaded (im Wireframe-Modus bleiben sie aus)."""
        return self.mode is not DisplayMode.WIREFRAME

    @property
    def show_edges(self) -> bool:
        """Edges im Wireframe-Modus oder bei aktivem Wireframe Overlay."""
        return self.mode is DisplayMode.WIREFRAME or bool(self.wireframe_overlay)

    @property
    def label(self) -> str:
        mode_label = {
            DisplayMode.SHADED: "Shaded",
            DisplayMode.FLAT_SHADED: "Flat Shaded",
            DisplayMode.WIREFRAME: "Wireframe",
        }[self.mode]
        if self.wireframe_overlay and self.mode is not DisplayMode.WIREFRAME:
            mode_label += " + Wire"
        return mode_label