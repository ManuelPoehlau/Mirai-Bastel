"""Synthetic control meshes + an independent Catmull-Clark reference for the tests.

`reference_catmull_clark` works directly on positions (face point / edge point /
vertex point formulas), with its own topology bookkeeping and no stencils, so
it is a genuinely different code path from `subd.py` (A4).
"""

from __future__ import annotations

from mirai.scene_factory import mesh_from_positions_and_faces

CUBE_POSITIONS = [(x, y, z) for x in (-1.0, 1.0) for y in (-1.0, 1.0) for z in (-1.0, 1.0)]


def cube_mesh():
    """Closed cube spanning ±1: 8 vertices, 6 quads, outward winding."""
    index = {p: i for i, p in enumerate(CUBE_POSITIONS)}

    def quad(*points):
        return [index[p] for p in points]

    faces = [
        quad((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)),
        quad((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)),
        quad((-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1)),
        quad((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)),
        quad((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)),
        quad((-1, -1, -1), (-1, 1, -1), (1, 1, -1), (1, -1, -1)),
    ]
    return mesh_from_positions_and_faces(CUBE_POSITIONS, faces)


def single_quad_mesh():
    return mesh_from_positions_and_faces(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)], [[0, 1, 2, 3]])


def plane_2x2_mesh():
    """3x3 vertices (z = 0), 2x2 quads; vertex index = 3*row + column."""
    positions = [(float(c), float(r), 0.0) for r in range(3) for c in range(3)]
    faces = [[3 * r + c, 3 * r + c + 1, 3 * (r + 1) + c + 1, 3 * (r + 1) + c]
             for r in range(2) for c in range(2)]
    return mesh_from_positions_and_faces(positions, faces)


def triangle_mesh():
    return mesh_from_positions_and_faces([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], [[0, 1, 2]])


def pentagon_mesh():
    import math

    positions = [(math.cos(2 * math.pi * k / 5), math.sin(2 * math.pi * k / 5), 0.0) for k in range(5)]
    return mesh_from_positions_and_faces(positions, [[0, 1, 2, 3, 4]])


def edge_pairs(faces):
    """Unique undirected edges of a face list."""
    seen = set()
    for face in faces:
        n = len(face)
        for k in range(n):
            seen.add(frozenset((face[k], face[(k + 1) % n])))
    return seen


def _mean(points):
    n = len(points)
    return tuple(sum(p[i] for p in points) / n for i in range(3))


def reference_catmull_clark(positions, faces):
    """One Catmull-Clark level on positions. Returns `(positions, faces)`."""
    face_pts = [_mean([positions[v] for v in face]) for face in faces]

    edge_faces: dict = {}
    edge_order: list = []
    for f, face in enumerate(faces):
        n = len(face)
        for k in range(n):
            key = frozenset((face[k], face[(k + 1) % n]))
            if key not in edge_faces:
                edge_faces[key] = []
                edge_order.append(key)
            edge_faces[key].append(f)

    def midpoint(key):
        a, b = tuple(key)
        return _mean([positions[a], positions[b]])

    edge_pts = {}
    for key in edge_order:
        fs = edge_faces[key]
        a, b = tuple(key)
        if len(fs) == 2:
            edge_pts[key] = _mean([positions[a], positions[b], face_pts[fs[0]], face_pts[fs[1]]])
        else:
            edge_pts[key] = midpoint(key)

    vertex_pts = []
    for v in range(len(positions)):
        edges = [k for k in edge_order if v in k]
        incident_faces = [f for f, face in enumerate(faces) if v in face]
        boundary = [k for k in edges if len(edge_faces[k]) == 1]
        p = positions[v]
        if boundary:
            n1, n2 = (next(iter(k - {v})) for k in boundary)
            vertex_pts.append(tuple((positions[n1][i] + 6 * p[i] + positions[n2][i]) / 8 for i in range(3)))
        else:
            n = len(edges)
            f_avg = _mean([face_pts[f] for f in incident_faces])
            r_avg = _mean([midpoint(k) for k in edges])
            vertex_pts.append(tuple((f_avg[i] + 2 * r_avg[i] + (n - 3) * p[i]) / n for i in range(3)))

    new_positions = list(vertex_pts) + [edge_pts[k] for k in edge_order] + list(face_pts)
    edge_index = {k: len(positions) + i for i, k in enumerate(edge_order)}
    face_base = len(positions) + len(edge_order)
    new_faces = []
    for f, face in enumerate(faces):
        n = len(face)
        for k in range(n):
            new_faces.append([
                face[k],
                edge_index[frozenset((face[k], face[(k + 1) % n]))],
                face_base + f,
                edge_index[frozenset((face[k - 1], face[k]))],
            ])
    return new_positions, new_faces


def reference_levels(positions, faces, levels):
    for _ in range(levels):
        positions, faces = reference_catmull_clark(positions, faces)
    return positions, faces


def sorted_close(a, b, tolerance) -> bool:
    """Sorted point lists agree pairwise within `tolerance` (order-free comparison)."""
    if len(a) != len(b):
        return False
    sa, sb = sorted(a), sorted(b)
    return all(abs(p[i] - q[i]) <= tolerance for p, q in zip(sa, sb) for i in range(3))


def face_centroids(positions, faces):
    return [_mean([positions[v] for v in face]) for face in faces]
