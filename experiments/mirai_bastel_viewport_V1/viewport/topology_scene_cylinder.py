"""Einfache Quad-Zylinder-Testszene für Topologie-Experimente."""

from __future__ import annotations

from math import cos, sin, tau

from mirai_bastel_core import Scene


def build_cylinder_scene(
    segments: int = 8,
    rings: int = 4,
    radius: float = 1.5,
    height: float = 3.0,
) -> Scene:
    """Erzeugt einen offenen Zylinder aus Quads ohne Caps.

    Die Zylinderenden bleiben offen. Jede horizontale Vertex-Reihe bildet
    einen geschlossenen Ring; die Mantelfläche besteht ausschließlich aus
    Quad-Faces. Die Szene ist bewusst klein und kontrolliert für Loop-/Ring-
    Detection und spätere Dissolve-Experimente.
    """
    if segments < 3:
        raise ValueError("segments muss >= 3 sein")
    if rings < 2:
        raise ValueError("rings muss >= 2 sein")
    if radius <= 0:
        raise ValueError("radius muss > 0 sein")
    if height <= 0:
        raise ValueError("height muss > 0 sein")

    scene = Scene()
    mesh = scene.mesh

    vertices = []
    for ring in range(rings):
        z = -height / 2.0 + (height * ring / (rings - 1))
        current_ring = []
        for segment in range(segments):
            angle = tau * segment / segments
            current_ring.append(
                mesh.add_vertex((radius * cos(angle), radius * sin(angle), z))
            )
        vertices.append(current_ring)

    for ring in range(rings - 1):
        for segment in range(segments):
            next_segment = (segment + 1) % segments
            v00 = vertices[ring][segment]
            v10 = vertices[ring][next_segment]
            v11 = vertices[ring + 1][next_segment]
            v01 = vertices[ring + 1][segment]
            mesh.add_face([v00, v10, v11, v01])

    return scene
