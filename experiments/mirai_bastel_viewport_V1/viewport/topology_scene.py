"""Kontrollierte Testszene für Topologie-Experimente im V1-Viewport."""

from __future__ import annotations

from mirai_bastel_core import Scene


def build_topology_scene(cells: int = 3, size: float = 3.0) -> Scene:
    """Erzeugt ein flaches Quad-Grid mit klaren inneren und Rand-Edges."""
    if cells < 1:
        raise ValueError("cells muss >= 1 sein")

    scene = Scene()
    mesh = scene.mesh
    step = size / cells
    start = -size / 2.0

    vertices = []
    for row in range(cells + 1):
        current_row = []
        y = start + row * step
        for col in range(cells + 1):
            x = start + col * step
            current_row.append(mesh.add_vertex((x, y, 0.0)))
        vertices.append(current_row)

    for row in range(cells):
        for col in range(cells):
            v00 = vertices[row][col]
            v10 = vertices[row][col + 1]
            v11 = vertices[row + 1][col + 1]
            v01 = vertices[row + 1][col]
            mesh.add_face([v00, v10, v11, v01])

    return scene
