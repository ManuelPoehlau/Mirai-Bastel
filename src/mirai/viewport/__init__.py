"""Produktions-Viewport-State (window-frei, ohne Rendering).

Gate-3-Scope: Camera/Picking/Display sind reine Mathematik-/Zustands-
Komponenten ohne Fenster- oder GPU-Abhängigkeit. Rendering (RenderMesh,
persistente GPU-Ressourcen) gehört zu Gate 5 / src/viewport (v0.2).
"""

from .camera import OrbitCamera
from .display import DisplayMode, DisplayState
from .picking import pick_face, pick_nearest_edge, pick_nearest_vertex
from . import vecmath

__all__ = [
    "DisplayMode",
    "DisplayState",
    "OrbitCamera",
    "pick_face",
    "pick_nearest_edge",
    "pick_nearest_vertex",
    "vecmath",
]