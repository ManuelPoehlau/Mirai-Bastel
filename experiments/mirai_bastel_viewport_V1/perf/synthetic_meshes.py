"""Synthetische Quad-Testmeshes für die Skalierungsmessung (Viewport-Perf-Research).

Einfachste mögliche Konstruktion: ein geschlossener Quad-Torus (rows x cols
Faces), über die reguläre Core-Mesh-API aufgebaut. Geschlossen/manifold/100 %
Quads — gleiche topologische Klasse wie der Head-Basemesh, aber ohne
realistische Form (bewusst, siehe Task §6: Skalierung, nicht Realismus).

    rows x cols = Faces;  V = rows*cols;  E = 2*rows*cols (manifold, geschlossen)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from mirai_bastel_core import Scene

# Standard-Größen für die Skalierungstabelle (Faces ≈ Zielwerte).
SCALING_TARGETS = {
    "324": (18, 18),      # 324 Faces  — Head-Baseline-Größe
    "1.3k": (36, 36),     # 1296 Faces
    "5k": (70, 71),       # 4970 Faces
    "20k": (141, 142),    # 20022 Faces
}


def build_torus_scene(rows: int, cols: int, major: float = 1.6, minor: float = 0.7) -> Scene:
    """Quad-Torus via regulärer Mesh-API (add_vertex/add_face)."""
    scene = Scene()
    mesh = scene.mesh
    vids = {}
    for i in range(rows):
        u = 2.0 * math.pi * i / rows
        for j in range(cols):
            w = 2.0 * math.pi * j / cols
            x = (major + minor * math.cos(w)) * math.cos(u)
            y = minor * math.sin(w)
            z = (major + minor * math.cos(w)) * math.sin(u)
            vids[(i, j)] = mesh.add_vertex((x, y, z))
    for i in range(rows):
        for j in range(cols):
            a = vids[(i, j)]
            b = vids[((i + 1) % rows, j)]
            c = vids[((i + 1) % rows, (j + 1) % cols)]
            d = vids[(i, (j + 1) % cols)]
            mesh.add_face([a, b, c, d])
    return scene


def build_scaling_scenes() -> dict[str, Scene]:
    scenes = {}
    for label, (rows, cols) in SCALING_TARGETS.items():
        scenes[label] = build_torus_scene(rows, cols)
    return scenes
