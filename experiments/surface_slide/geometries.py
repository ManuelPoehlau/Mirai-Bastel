"""Test geometries with an analytic reference where one exists. Arrays only: `(V (n, 3), faces list of index tuples)`.

Every generator returns a `Geometry` whose `analytic` (when not None) knows the smooth surface the mesh samples:
`distance(P)` (unsigned distance to it) and, where meaningful, more (see each class).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

_I = np.intp


@dataclass
class Geometry:
    name: str
    V: np.ndarray
    faces: list
    analytic: object | None = None
    meta: dict = field(default_factory=dict)


def _weld(V: np.ndarray, faces: list, decimals: int = 9) -> tuple[np.ndarray, list]:
    key = np.round(V, decimals)
    _, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inverse = inverse.ravel()
    order = np.argsort(first)
    rank = np.empty_like(order)
    rank[order] = np.arange(len(order))
    remap = rank[inverse]
    out = []
    for f in faces:
        g = [int(remap[i]) for i in f]
        g = [a for a, b in zip(g, g[1:] + g[:1]) if a != b]
        if len(g) >= 3:
            out.append(tuple(g))
    return V[first[order]], out


# --- sphere ------------------------------------------------------------------------------------------------------------

class AnalyticSphere:
    def __init__(self, radius: float) -> None:
        self.radius = radius

    def distance(self, P: np.ndarray) -> np.ndarray:
        return np.abs(np.linalg.norm(P, axis=1) - self.radius)

    def radius_of(self, P: np.ndarray) -> np.ndarray:
        return np.linalg.norm(P, axis=1)

    def exp(self, P0: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Exponential map: from `P0` on the sphere along the tangent vectors `T` (great-circle arc of length |T|)."""
        r = self.radius
        length = np.linalg.norm(T, axis=1)
        theta = length / r
        unit_t = T / np.where(length > 0, length, 1.0)[:, None]
        return np.cos(theta)[:, None] * P0 + (r * np.sin(theta))[:, None] * unit_t

    def tangent(self, P0: np.ndarray, delta: np.ndarray) -> np.ndarray:
        n = P0 / np.linalg.norm(P0, axis=1, keepdims=True)
        return delta - np.einsum("ij,ij->i", delta, n)[:, None] * n


def cube_sphere(n: int, radius: float = 1.0) -> Geometry:
    """A cube with n x n quads per side pushed onto the sphere: all quads, eight valence-3 corners - the topology a
    subdivided box has. Coordinates are built so that the mesh is bit-exactly mirror-symmetric in x, y and z."""
    u = np.array([(2 * i - n) / n for i in range(n + 1)])
    verts = []
    faces = []
    index: dict = {}

    def vid(p):
        key = tuple(int(round(c * n)) for c in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(p)
        return index[key]

    for axis in range(3):
        for sign in (-1.0, 1.0):
            a, b = (axis + 1) % 3, (axis + 2) % 3
            for i in range(n):
                for j in range(n):
                    quad = []
                    for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        p = [0.0, 0.0, 0.0]
                        p[axis] = sign
                        p[a] = u[i + di]
                        p[b] = u[j + dj]
                        quad.append(vid(tuple(p)))
                    if sign < 0:
                        quad.reverse()
                    faces.append(tuple(quad))
    V = np.array(verts)
    # tan warp evens out the quad sizes; applied per coordinate, so the mirror symmetry stays exact
    W = np.tan(V * (math.pi / 4.0))
    W = np.where(np.abs(V) == 1.0, V, W)
    length = np.sqrt(W[:, 0] * W[:, 0] + W[:, 1] * W[:, 1] + W[:, 2] * W[:, 2])
    V = radius * W / length[:, None]
    return Geometry(f"cube_sphere_n{n}", V, faces, AnalyticSphere(radius), {"n": n, "radius": radius})


def cube_sphere_for(target_vertices: int, radius: float = 1.0) -> Geometry:
    n = max(2, int(round(math.sqrt((target_vertices - 2) / 6.0))))
    return cube_sphere(n, radius)


def uv_sphere(segments: int, rings: int, radius: float = 1.0) -> Geometry:
    """Latitude / longitude sphere: quads plus two triangle fans at the poles (high-valence vertices, thin quads)."""
    verts = [(0.0, radius, 0.0)]
    for r in range(1, rings):
        phi = math.pi * r / rings
        for s in range(segments):
            theta = 2.0 * math.pi * s / segments
            verts.append((radius * math.sin(phi) * math.cos(theta), radius * math.cos(phi),
                          radius * math.sin(phi) * math.sin(theta)))
    verts.append((0.0, -radius, 0.0))
    faces = []
    ring = lambda r, s: 1 + (r - 1) * segments + (s % segments)
    for s in range(segments):
        faces.append((0, ring(1, s + 1), ring(1, s)))
    for r in range(1, rings - 1):
        for s in range(segments):
            faces.append((ring(r, s), ring(r, s + 1), ring(r + 1, s + 1), ring(r + 1, s)))
    last = len(verts) - 1
    for s in range(segments):
        faces.append((last, ring(rings - 1, s), ring(rings - 1, s + 1)))
    return Geometry(f"uv_sphere_{segments}x{rings}", np.array(verts), faces, AnalyticSphere(radius),
                    {"segments": segments, "rings": rings, "radius": radius})


# --- cylinder / capsule ------------------------------------------------------------------------------------------------

class AnalyticCylinder:
    """Open tube around the y axis. `exp` unrolls: (arc, y) is a flat chart, a geodesic is a straight line in it."""

    def __init__(self, radius: float, y0: float, y1: float) -> None:
        self.radius, self.y0, self.y1 = radius, y0, y1

    def distance(self, P: np.ndarray) -> np.ndarray:
        return np.abs(np.hypot(P[:, 0], P[:, 2]) - self.radius)

    def tangent(self, P0: np.ndarray, delta: np.ndarray) -> np.ndarray:
        n = np.stack([P0[:, 0], np.zeros(len(P0)), P0[:, 2]], axis=1)
        n /= np.linalg.norm(n, axis=1, keepdims=True)
        return delta - np.einsum("ij,ij->i", delta, n)[:, None] * n

    def exp(self, P0: np.ndarray, T: np.ndarray) -> np.ndarray:
        r = self.radius
        theta0 = np.arctan2(P0[:, 2], P0[:, 0])
        circ = np.stack([-np.sin(theta0), np.zeros(len(P0)), np.cos(theta0)], axis=1)
        d_arc = np.einsum("ij,ij->i", T, circ)
        theta = theta0 + d_arc / r
        return np.stack([r * np.cos(theta), P0[:, 1] + T[:, 1], r * np.sin(theta)], axis=1)


def cylinder(segments: int, rows: int, radius: float = 1.0, height: float = 4.0) -> Geometry:
    """Open tube (no caps) around y: `segments` quads around, `rows` along."""
    verts = []
    for r in range(rows + 1):
        y = -height / 2.0 + height * r / rows
        for s in range(segments):
            a = 2.0 * math.pi * s / segments
            verts.append((radius * math.cos(a), y, radius * math.sin(a)))
    faces = []
    for r in range(rows):
        for s in range(segments):
            a, b = r * segments + s, r * segments + (s + 1) % segments
            faces.append((a, a + segments, b + segments, b))
    return Geometry(f"cylinder_{segments}x{rows}", np.array(verts), faces,
                    AnalyticCylinder(radius, -height / 2.0, height / 2.0),
                    {"segments": segments, "rows": rows, "radius": radius, "height": height})


class AnalyticCapsule:
    """Barrel of half-length `half` around y plus two hemispherical caps: curvature changes at |y| = half."""

    def __init__(self, radius: float, half: float) -> None:
        self.radius, self.half = radius, half

    def distance(self, P: np.ndarray) -> np.ndarray:
        yc = np.clip(P[:, 1], -self.half, self.half)
        return np.abs(np.sqrt(P[:, 0] ** 2 + (P[:, 1] - yc) ** 2 + P[:, 2] ** 2) - self.radius)

    def region(self, P: np.ndarray) -> np.ndarray:
        """0 = barrel, +1 / -1 = upper / lower cap."""
        return np.sign(P[:, 1]) * (np.abs(P[:, 1]) > self.half)


def capsule(segments: int, barrel_rows: int, cap_rings: int, radius: float = 1.0, half: float = 1.5) -> Geometry:
    profile = []  # (ring radius, y), top pole to bottom pole, poles excluded
    for i in range(1, cap_rings + 1):
        phi = (math.pi / 2.0) * i / cap_rings
        profile.append((radius * math.sin(phi), half + radius * math.cos(phi)))
    for i in range(1, barrel_rows + 1):
        profile.append((radius, half - 2.0 * half * i / barrel_rows))
    for i in range(1, cap_rings):
        phi = (math.pi / 2.0) * i / cap_rings
        profile.append((radius * math.cos(phi), -half - radius * math.sin(phi)))
    verts = [(0.0, half + radius, 0.0)]
    for rr, y in profile:
        for s in range(segments):
            a = 2.0 * math.pi * s / segments
            verts.append((rr * math.cos(a), y, rr * math.sin(a)))
    verts.append((0.0, -half - radius, 0.0))
    rings = len(profile)
    ring = lambda r, s: 1 + r * segments + (s % segments)
    faces = [(0, ring(0, s + 1), ring(0, s)) for s in range(segments)]
    for r in range(rings - 1):
        for s in range(segments):
            faces.append((ring(r, s), ring(r, s + 1), ring(r + 1, s + 1), ring(r + 1, s)))
    last = len(verts) - 1
    faces += [(last, ring(rings - 1, s), ring(rings - 1, s + 1)) for s in range(segments)]
    return Geometry(f"capsule_{segments}x{barrel_rows}+{cap_rings}", np.array(verts), faces,
                    AnalyticCapsule(radius, half),
                    {"segments": segments, "barrel_rows": barrel_rows, "cap_rings": cap_rings, "radius": radius,
                     "half": half})


# --- U shape (concave, developable) ------------------------------------------------------------------------------------

class UnrolledU:
    """The *polyhedral* U laid flat. The mesh is a strip bent only across its profile, so it unrolls without
    distortion: `s` is the arc length along the profile polyline (the mesh's own, not the smooth arc's), `y` the
    extrusion coordinate. On the mesh a geodesic is exactly a straight line in (s, y) - an exact ground truth for
    where a slide should end, and `wall(s)` says which part of the U a point is on."""

    def __init__(self, profile: np.ndarray, s_nodes: np.ndarray, vert_s: np.ndarray, wall_len: float, bend_len: float,
                 gap: float, length_y: float) -> None:
        self.profile = profile          # (m, 2) x, z of the profile polyline
        self.s_nodes = s_nodes          # (m,) arc length at each profile node
        self.vert_s = vert_s            # (nv,) arc length of each mesh vertex
        self.wall_len, self.bend_len, self.gap, self.length_y = wall_len, bend_len, gap, length_y
        self.s_max = float(s_nodes[-1])

    def anchor_sy(self, V: np.ndarray, T: np.ndarray, tri: np.ndarray, bary: np.ndarray) -> np.ndarray:
        """(s, y) of anchors: both are linear inside a triangle because the strip is flat there."""
        tv = T[tri]
        s = np.einsum("nk,nk->n", bary, self.vert_s[tv])
        y = np.einsum("nk,nk->n", bary, V[tv][:, :, 1])
        return np.stack([s, y], axis=1)

    def point(self, sy: np.ndarray) -> np.ndarray:
        s = np.clip(sy[:, 0], 0.0, self.s_max)
        i = np.clip(np.searchsorted(self.s_nodes, s, side="right") - 1, 0, len(self.s_nodes) - 2)
        f = (s - self.s_nodes[i]) / (self.s_nodes[i + 1] - self.s_nodes[i])
        xz = self.profile[i] + f[:, None] * (self.profile[i + 1] - self.profile[i])
        return np.stack([xz[:, 0], sy[:, 1], xz[:, 1]], axis=1)

    def wall(self, s: np.ndarray) -> np.ndarray:
        """0 = wall A (x < 0), 1 = bend, 2 = wall B."""
        return np.where(s < self.wall_len - 1e-12, 0, np.where(s > self.wall_len + self.bend_len + 1e-12, 2, 1))

    def frame(self, s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Unit 3D directions of increasing s and of increasing y at arc length s (piecewise constant)."""
        i = np.clip(np.searchsorted(self.s_nodes, s, side="right") - 1, 0, len(self.s_nodes) - 2)
        d = self.profile[i + 1] - self.profile[i]
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        e_s = np.stack([d[:, 0], np.zeros(len(s)), d[:, 1]], axis=1)
        e_y = np.tile(np.array([0.0, 1.0, 0.0]), (len(s), 1))
        return e_s, e_y

    def distance(self, P: np.ndarray) -> np.ndarray:
        """Unsigned distance to the profile polyline extruded along y (global; use `wall` for the region)."""
        a = self.profile[:-1][None, :, :]
        b = self.profile[1:][None, :, :]
        p = P[:, None, [0, 2]]
        ab = b - a
        t = np.clip(np.einsum("nmj,nmj->nm", p - a, np.broadcast_to(ab, (len(P),) + ab.shape[1:]))
                    / np.einsum("mj,mj->m", ab[0], ab[0])[None, :], 0.0, 1.0)
        q = a + t[..., None] * ab
        return np.sqrt(np.min(np.einsum("nmj,nmj->nm", p - q, p - q), axis=1))


def u_shape(gap: float = 0.3, depth: float = 2.0, length_y: float = 2.0, cell: float = 0.1,
            bend_segments: int = 8) -> Geometry:
    """A deep U: two parallel walls `gap` apart and `depth` high, joined by a half cylinder of radius gap/2, extruded
    along y. The walls face each other across the gap (normals pointing into it). `bend_segments` = 1 makes a flat
    bottom with two sharp 90 degree creases; 2 a sharp V-like fold."""
    r = gap / 2.0
    n_wall = max(1, int(round(depth / cell)))
    wall_len = depth
    nodes = [(-r, depth - depth * i / n_wall) for i in range(n_wall + 1)]            # wall A, top -> bottom (z = 0)
    for i in range(1, bend_segments + 1):
        a = math.pi * i / bend_segments
        nodes.append((-r * math.cos(a), -r * math.sin(a)))                             # bend below z = 0
    nodes += [(r, depth * i / n_wall) for i in range(1, n_wall + 1)]                  # wall B, bottom -> top
    profile = np.array(nodes)
    seg = np.linalg.norm(np.diff(profile, axis=0), axis=1)
    s_nodes = np.r_[0.0, np.cumsum(seg)]
    bend_len = float(s_nodes[n_wall + bend_segments] - s_nodes[n_wall])
    n_y = max(1, int(round(length_y / cell)))
    m = len(profile)
    verts = np.zeros((m * (n_y + 1), 3))
    vert_s = np.zeros(m * (n_y + 1))
    for j in range(n_y + 1):
        y = -length_y / 2.0 + length_y * j / n_y
        verts[j * m:(j + 1) * m] = np.stack([profile[:, 0], np.full(m, y), profile[:, 1]], axis=1)
        vert_s[j * m:(j + 1) * m] = s_nodes
    faces = []
    for j in range(n_y):
        for i in range(m - 1):
            a, b = j * m + i, j * m + i + 1
            # wound so that the normals point into the gap (towards the opposite wall)
            faces.append((a, b, b + m, a + m))
    analytic = UnrolledU(profile, s_nodes, vert_s, wall_len, bend_len, gap, length_y)
    return Geometry(f"u_gap{gap:g}_bend{bend_segments}", verts, faces, analytic,
                    {"gap": gap, "depth": depth, "length_y": length_y, "cell": cell, "bend_segments": bend_segments,
                     "profile_nodes": m, "rows": n_y + 1})


def u_vertex(geo: Geometry, profile_index: int, row: int) -> int:
    return row * geo.meta["profile_nodes"] + profile_index


# --- helpers ------------------------------------------------------------------------------------------------------------

def symmetrize_x(V: np.ndarray, decimals: int = 7) -> tuple[np.ndarray, np.ndarray]:
    """Make `V` bit-exactly mirror-symmetric about x = 0 -> `(V, partner)`; `partner[i] == i` on the plane, -1 for a
    vertex without a partner. Positions are matched within `decimals`, then the x >= 0 member is copied over."""
    V = V.copy()
    key = {tuple(np.round(p, decimals)): i for i, p in enumerate(V)}
    partner = np.full(len(V), -1, dtype=_I)
    for i, p in enumerate(V):
        q = np.round(p * np.array([-1.0, 1.0, 1.0]), decimals) + 0.0
        j = key.get(tuple(q))
        if j is None:
            continue
        partner[i] = j
    for i, j in enumerate(partner):
        if j == i:
            V[i, 0] = 0.0
        elif j >= 0 and (V[i, 0] > 0 or (V[i, 0] == 0 and i < j)):
            V[j] = V[i] * np.array([-1.0, 1.0, 1.0])
    return V, partner
