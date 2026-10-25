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

from .look_controls import LIGHT_FIELDS, clamp_light

#: Anzeige-Namen der Bezugsräume in der Statuszeile.
_SPACE_LABELS = {SPACE_CAMERA: "Kamera", SPACE_WORLD: "Welt"}
#: Wie im Shading Lab: nach einer Werte-Änderung heißt das Licht so (das Preset steht dahinter).
EDITED_LABEL = "angepasst"

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
        # AD-024 §8: die bearbeiteten Werte (None = die des Presets); ein Preset-Wechsel verwirft sie.
        self.light_edit: LightRig | None = None
        # Glanz der Flächen (2026-10-23, `viewport.material`): Specular-Stärke, Glossiness und
        # Fill-Specular, `PROVISIONAL` Defaults. Ansichts-Zustand wie das Licht, keine Taste
        # (kein Material-Editor): `set_surface_finish(...)` ist die Schnittstelle.
        self.surface_finish: SurfaceFinish = DEFAULT_FINISH
        # Saved regions (2026-10-25): their face colours show (Ctrl+Alt+D toggles).
        self.region_tint: bool = True

    # -- Übergänge ----------------------------------------------------------

    def set_mode(self, mode: DisplayMode) -> None:
        """Setzt den Display-Modus; ungültige Werte werden abgelehnt."""
        self.mode = DisplayMode(mode)

    def cycle(self) -> None:
        """Wechselt in der Reihenfolge Shaded → Flat Shaded → Wireframe → ..."""
        index = _MODE_CYCLE.index(self.mode)
        self.mode = _MODE_CYCLE[(index + 1) % len(_MODE_CYCLE)]

    def toggle_region_tint(self) -> None:
        self.region_tint = not self.region_tint

    def toggle_wireframe_overlay(self) -> None:
        self.wireframe_overlay = not self.wireframe_overlay

    def set_wireframe_overlay(self, on: bool) -> None:
        self.wireframe_overlay = bool(on)

    def cycle_light_preset(self) -> None:
        """Raitt 2:1 → Softbox → Warm/Kalt → Heute → ..."""
        index = APP_PRESET_ORDER.index(self.light_preset)
        self.light_preset = APP_PRESET_ORDER[(index + 1) % len(APP_PRESET_ORDER)]
        self.light_edit = None

    def toggle_light_space(self) -> None:
        """Licht folgt der Kamera <-> steht in der Welt."""
        self.light_space = SPACE_WORLD if self.light_rig.space == SPACE_CAMERA else SPACE_CAMERA

    def set_surface_finish(self, **changes) -> SurfaceFinish:
        """Ändert `specular`, `glossiness` und/oder `fill_specular` (je 0..1, geklemmt)."""
        self.surface_finish = self.surface_finish.with_(**changes)
        return self.surface_finish

    def set_light(self, **changes) -> LightRig:
        """Ändert Werte des Worklights (jedes `LightRig`-Feld; in den Bereich des Shading Lab
        geklemmt, AD-024 §8). Ein geänderter Bezugsraum bleibt wie `toggle_light_space` über
        Preset-Wechsel stehen. Gibt das Licht danach zurück."""
        unknown = set(changes) - LIGHT_FIELDS
        if unknown:
            raise KeyError(f"unknown light parameter(s) {sorted(unknown)}; expected {sorted(LIGHT_FIELDS)}")
        rig = clamp_light(self.light_rig.with_(**changes))
        if "space" in changes:
            self.light_space = rig.space
        if rig != self.light_rig:
            self.light_edit = rig
        return self.light_rig

    @property
    def light_edited(self) -> bool:
        """True, wenn Werte vom Preset abweichen (der Bezugsraum zählt nicht, er ist ein Umschalter)."""
        if self.light_edit is None:
            return False
        return self.light_edit.with_(space=PRESETS[self.light_preset].space) != PRESETS[self.light_preset]

    @property
    def light_rig(self) -> LightRig:
        rig = self.light_edit if self.light_edit is not None else PRESETS[self.light_preset]
        return rig if self.light_space is None else rig.with_(space=self.light_space)

    @property
    def light_label(self) -> str:
        name = f"{self.light_preset} {EDITED_LABEL}" if self.light_edited else self.light_preset
        return f"{name} · {_SPACE_LABELS[self.light_rig.space]}"

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