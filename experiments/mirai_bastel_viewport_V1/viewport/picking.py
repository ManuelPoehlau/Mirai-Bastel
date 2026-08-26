"""Screen-space Picking für den isolierten Viewport-V1-Praxistest.

Die Picking-Funktionen arbeiten bewusst ohne pyglet/OpenGL. Sie benutzen die
öffentliche Mesh-Query-API und die testbare Kamera-Projektion. Die Toleranzen
sind V1-Testwerte, keine Produktionsentscheidung.
"""

from __future__ import annotations

import math

from mirai_bastel_core import EdgeId, FaceId, Mesh, VertexId

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


def _point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    qx, qy = ax + t * abx, ay + t * aby
    return math.hypot(px - qx, py - qy)


def pick_nearest_edge(
    camera: OrbitCamera,
    mesh: Mesh,
    sx: float,
    sy: float,
    width: int,
    height: int,
    max_pixel_distance: float = 9.0,
) -> EdgeId | None:
    best_id: EdgeId | None = None
    best_dist = max_pixel_distance
    for eid in mesh.all_edge_ids():
        va, vb = mesh.edge_vertices(eid)
        a = camera.project_to_screen(mesh.vertex_position(va), width, height)
        b = camera.project_to_screen(mesh.vertex_position(vb), width, height)
        if a is None or b is None:
            continue
        dist = _point_segment_distance(sx, sy, a[0], a[1], b[0], b[1])
        if dist < best_dist:
            best_dist = dist
            best_id = eid
    return best_id


def _ray_triangle_intersection(origin, direction, a, b, c):
    # Moller-Trumbore intersection. Returns ray distance t or None.
    eps = 1e-9
    edge1 = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    edge2 = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    h = (
        direction[1] * edge2[2] - direction[2] * edge2[1],
        direction[2] * edge2[0] - direction[0] * edge2[2],
        direction[0] * edge2[1] - direction[1] * edge2[0],
    )
    det = edge1[0] * h[0] + edge1[1] * h[1] + edge1[2] * h[2]
    if abs(det) < eps:
        return None
    inv_det = 1.0 / det
    s = (origin[0] - a[0], origin[1] - a[1], origin[2] - a[2])
    u = inv_det * (s[0] * h[0] + s[1] * h[1] + s[2] * h[2])
    if u < -eps or u > 1.0 + eps:
        return None
    q = (
        s[1] * edge1[2] - s[2] * edge1[1],
        s[2] * edge1[0] - s[0] * edge1[2],
        s[0] * edge1[1] - s[1] * edge1[0],
    )
    v = inv_det * (direction[0] * q[0] + direction[1] * q[1] + direction[2] * q[2])
    if v < -eps or u + v > 1.0 + eps:
        return None
    t = inv_det * (edge2[0] * q[0] + edge2[1] * q[1] + edge2[2] * q[2])
    return t if t > eps else None


def pick_face(
    camera: OrbitCamera,
    mesh: Mesh,
    sx: float,
    sy: float,
    width: int,
    height: int,
) -> FaceId | None:
    """Pick the nearest face hit by the camera ray through the cursor.

    Polygon faces are triangulated as a fan, matching the experimental
    renderer. The nearest positive triangle intersection wins, so overlapping
    projected faces resolve to the visible/front-most face.
    """
    origin, direction = camera.screen_to_ray(sx, sy, width, height)
    best_id: FaceId | None = None
    best_t = float("inf")
    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        if len(boundary) < 3:
            continue
        p0 = mesh.vertex_position(boundary[0])
        for i in range(1, len(boundary) - 1):
            p1 = mesh.vertex_position(boundary[i])
            p2 = mesh.vertex_position(boundary[i + 1])
            t = _ray_triangle_intersection(origin, direction, p0, p1, p2)
            if t is not None and t < best_t:
                best_t = t
                best_id = fid
    return best_id
