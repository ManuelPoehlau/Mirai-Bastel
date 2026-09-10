"""Scene-Ebene des Integration Labs: Testobjekte und Auswahl.

- `scene_objects` erzeugt die beiden Zielobjekte: Cube (kontrolliertes
  Testobjekt) und das reale Head-Basemesh (Rigging-Experiment-Asset).
- `scene` hält die Lab-Szene mit mehreren unabhängigen `src.core.Scene`s
  und der Objekt-Auswahl (aktiv vs. inaktiv).
"""

from .scene import LabObject, LabScene
from .scene_objects import build_cube_scene, build_head_scene, build_lab_scene

__all__ = [
    "LabObject",
    "LabScene",
    "build_cube_scene",
    "build_head_scene",
    "build_lab_scene",
]