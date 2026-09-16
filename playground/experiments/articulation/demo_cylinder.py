"""Deterministic all-quad cylinder — the EX-A test body.

The Head-Basemesh has 52 poles (measured: 30 valence-3, 22 valence-5 out of
326 vertices) and is deliberately NOT used for H01. Poles are exactly where
several existing topology tools (Loop Select, Loop Slide, Connect Edges
kind "v") already refuse to operate — see H03. Testing articulation on the
head would confound "does bending help?" with "does the topology toolchain
reach this vertex at all?". A simple cylinder isolates the articulation
question (per handoff: "einfachen länglichen Körper/Zylinder").

Fully deterministic: same vertex/face layout every call. Two poles only
(top and bottom cap centers), everywhere else regular quad topology —
Loop Select / Loop Slide / Connect Edges all work along the body.
"""

from __future__ import annotations

import math

from core.mesh import Mesh


def build_cylinder(
    segments: int = 12,
    rings: int = 6,
    radius: float = 0.5,
    height: float = 3.0,
) -> Mesh:
    """Build an all-quad cylinder (sides) with two triangle-fan caps.

    Axis is Y (matches the Playground's up axis used elsewhere in the repo,
    e.g. demo_mesh.py's head convention of y > 0 = up).

    Args:
        segments: vertices per ring (>=3).
        rings: number of rings along the height (>=2). More rings = more
            quads along the bend axis, giving the falloff something to
            act on.
        radius: cylinder radius.
        height: full height, centered on the origin (y in [-height/2, height/2]).

    Returns:
        Mesh with `segments * rings` body vertices + 2 cap-center vertices.
    """
    if segments < 3:
        raise ValueError("segments must be >= 3")
    if rings < 2:
        raise ValueError("rings must be >= 2")

    mesh = Mesh()

    ring_vertex_ids: list[list] = []
    for r in range(rings):
        y = -height / 2.0 + height * (r / (rings - 1))
        row = []
        for s in range(segments):
            angle = 2.0 * math.pi * s / segments
            x = radius * math.cos(angle)
            z = radius * math.sin(angle)
            row.append(mesh.add_vertex((x, y, z)))
        ring_vertex_ids.append(row)

    # Side quads between consecutive rings.
    for r in range(rings - 1):
        for s in range(segments):
            s_next = (s + 1) % segments
            v0 = ring_vertex_ids[r][s]
            v1 = ring_vertex_ids[r][s_next]
            v2 = ring_vertex_ids[r + 1][s_next]
            v3 = ring_vertex_ids[r + 1][s]
            mesh.add_face([v0, v1, v2, v3])

    # Caps: triangle fan from a center vertex (the only poles in this mesh).
    bottom_center = mesh.add_vertex((0.0, -height / 2.0, 0.0))
    top_center = mesh.add_vertex((0.0, height / 2.0, 0.0))
    for s in range(segments):
        s_next = (s + 1) % segments
        mesh.add_face([bottom_center, ring_vertex_ids[0][s_next], ring_vertex_ids[0][s]])
        mesh.add_face([top_center, ring_vertex_ids[-1][s], ring_vertex_ids[-1][s_next]])

    return mesh
