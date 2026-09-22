"""Connect Lab — flaches Quad-Raster als Testkörper.

8×8 Quads in der XY-Ebene (Blickrichtung Front), zentriert um den Ursprung.
Nur Playground-Testgeometrie, kein Production-Asset.
"""

from __future__ import annotations

from core import Mesh


def build_grid(n: int = 8, size: float = 2.0) -> Mesh:
    mesh = Mesh()
    step = size / n
    half = size / 2.0
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((c * step - half, r * step - half, 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh
