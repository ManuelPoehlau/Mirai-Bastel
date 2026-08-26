"""Vertex-Picking für den V1-Viewport-Praxistest.

Bewusst Screen-Space-Picking (nächster projizierter Vertex zum Mausklick)
statt 3D-Ray/Sphere-Intersection: liefert unabhängig vom Blickwinkel eine
konstante Pixel-Toleranz, ist der Standardansatz für Vertex-Picking in
Modelern und braucht kein zusätzliches "Trefferradius in Weltkoordinaten"-
Konzept. Nur Vertex-Picking (kein Edge-/Face-Picking) - das reicht, um die
Pipeline Scene -> Mesh -> Selection -> Operation zu testen (siehe Scope-
Absprache im Chat vor diesem Milestone).
"""

from __future__ import annotations

import math

from mirai_bastel_core import Mesh, VertexId

from .camera import OrbitCamera


def pick_nearest_vertex(
    camera: OrbitCamera,
    mesh: Mesh,
    sx: float,
    sy: float,
    width: int,
    height: int,
    max_pixel_distance: float = 14.0,
) -> VertexId | None:
    best_id: VertexId | None = None
    best_dist = max_pixel_distance
    for vid in mesh.all_vertex_ids():
        projected = camera.project_to_screen(mesh.vertex_position(vid), width, height)
        if projected is None:
            continue
        px, py = projected
        dist = math.hypot(px - sx, py - sy)
        if dist < best_dist:
            best_dist = dist
            best_id = vid
    return best_id
