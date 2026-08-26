"""Demo-Szene für den V1-Viewport-Praxistest: ein einfacher Würfel.

Bewusst simpel - Ziel dieses Milestones ist, den Core interaktiv zu
benutzen, nicht ein interessantes Modell zu zeigen. Baut ausschließlich
über die öffentliche Mesh-Mutation-API (add_vertex/add_face), genau wie
ein späteres Import-System das später tun würde.
"""

from __future__ import annotations

from mirai_bastel_core import Scene


def build_cube_scene(size: float = 2.0) -> Scene:
    scene = Scene()
    mesh = scene.mesh
    s = size / 2.0
    positions = [
        (-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),  # hinten (z-)
        (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s),      # vorne (z+)
    ]
    verts = [mesh.add_vertex(p) for p in positions]

    # Jede Boundary im Uhrzeigersinn von außen betrachtet - für V1 ohne
    # Backface-Culling nicht sicherheitsrelevant, aber sauberer Stil.
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

    return scene
