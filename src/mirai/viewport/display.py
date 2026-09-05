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