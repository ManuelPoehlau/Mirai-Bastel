"""Scene-/Mesh-Factories für die Produktions-Application.

Extrahiert aus dem Viewport-V1-Experiment (`viewport/demo_scene.py`,
`build_cube_scene`). Baut ausschließlich über die öffentliche Core-Mutation-
API (`Mesh.add_vertex`/`add_face`), genau wie ein späteres Import-System das
tun würde — deshalb liegt der Factory-Code in `mirai` und nicht im
(gefrorenen) Core.
"""

from __future__ import annotations

from core import Mesh, Scene


def create_cube(size: float = 2.0) -> Mesh:
    """Erzeugt ein neues Mesh mit einem Würfel (8 Vertices, 6 Faces)."""
    mesh = Mesh()
    s = size / 2.0
    positions = [
        (-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),  # hinten (z-)
        (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s),      # vorne (z+)
    ]
    verts = [mesh.add_vertex(p) for p in positions]

    # Jede Boundary im Uhrzeigersinn von außen betrachtet.
    faces = [
        (0, 1, 2, 3),  # hinten
        (5, 4, 7, 6),  # vorne
        (4, 0, 3, 7),  # links
        (1, 5, 6, 2),  # rechts
        (3, 2, 6, 7),  # oben
        (4, 5, 1, 0),  # unten
    ]
    for a, b, c, d in faces:
        mesh.add_face([verts[a], verts[b], verts[c], verts[d]])
    return mesh


def build_cube_scene(size: float = 2.0) -> Scene:
    """Erzeugt eine fertige Scene mit einem Würfel-Mesh."""
    scene = Scene()
    scene.mesh = create_cube(size)
    return scene