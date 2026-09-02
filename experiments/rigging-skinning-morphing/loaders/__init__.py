"""Asset-Loader für das Rigging/Skinning/Morphing-Experiment.

Bewusst experimentell: Die Loader sind reine Parser ohne Core-, Viewport-
oder pyglet-Abhängigkeit und damit headless testbar. Die Überführung in das
Core-Mesh passiert im Viewport-Adapter (siehe viewport_adapter.py).
"""

from .obj_loader import ObjLoadError, ObjMeshData, load_obj, parse_obj

__all__ = ["ObjLoadError", "ObjMeshData", "load_obj", "parse_obj"]
