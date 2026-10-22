"""Face shading of the influence: weights -> per-corner colours (2026-10-22, `PROVISIONAL`).

Headless data behind the second influence display mode (the first are the vertex bands, `bands`).
Every face with at least one influenced vertex is fan-triangulated like `RenderMesh`
(`viewport.derived.triangulate_mesh_face`) and each triangle corner carries the colour of its
vertex's weight; GL interpolates it across the face. The display idea is the one of the Mehlsack
Lab's surface preview (`experiments/mehlsack_lab/lab_preview.py`, not imported); Soft Selection's
weights stay `0 < w <= 1` (no signed weights) and nothing here computes influence.

Look: the hue runs through the four band colours (strong red .. weak blue, so both display modes
mean the same), the alpha stays low and grows with the weight, so the surface, its lighting,
wire and the selection / hover cues remain readable below and above it.
"""

from __future__ import annotations

from typing import Mapping

from core import Mesh, VertexId
from viewport.derived import triangulate_mesh_face

from .bands import BAND_COUNT

RGBA = tuple[float, float, float, float]
Position = tuple[float, float, float]
Triangle = tuple[VertexId, VertexId, VertexId]

#: PROVISIONAL hue stops, weakest (w -> 0) .. strongest (w = 1); the band colours of `gl_bands`.
SHADING_HUES: tuple[tuple[float, float, float], ...] = (
    (0.25, 0.45, 1.0),
    (0.15, 0.78, 0.70),
    (1.0, 0.50, 0.08),
    (1.0, 0.22, 0.15),
)
#: PROVISIONAL alpha at w -> 0+ and at w = 1 (seeds).
SHADING_ALPHA_MIN = 0.12
SHADING_ALPHA_MAX = 0.45
assert len(SHADING_HUES) == BAND_COUNT


def shading_color(weight: float) -> RGBA:
    """Corner colour of one weight: transparent for `w <= 0`, else the hue ramp at `w` with an
    alpha between `SHADING_ALPHA_MIN` and `SHADING_ALPHA_MAX`."""
    if not weight > 0.0:
        return (*SHADING_HUES[0], 0.0)
    w = min(1.0, weight)
    position = w * (len(SHADING_HUES) - 1)
    lower = min(int(position), len(SHADING_HUES) - 2)
    t = position - lower
    a, b = SHADING_HUES[lower], SHADING_HUES[lower + 1]
    rgb = tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
    return (*rgb, SHADING_ALPHA_MIN + (SHADING_ALPHA_MAX - SHADING_ALPHA_MIN) * w)  # type: ignore[return-value]


def shaded_triangles(mesh: Mesh, weights: Mapping[VertexId, float]) -> list[Triangle]:
    """The fan triangles (vertex ids) of every face with a vertex of positive weight, in face-id
    order. Depends on topology and weights only - not on positions."""
    if not weights:
        return []
    triangles: list[Triangle] = []
    for face in mesh.all_face_ids():
        boundary = mesh.face_vertices(face)
        if any(weights.get(v, 0.0) > 0.0 for v in boundary):
            triangles.extend(triangulate_mesh_face(mesh, face))
    return triangles


def triangle_positions(mesh: Mesh, triangles: list[Triangle]) -> list[tuple[Position, Position, Position]]:
    """World positions of `triangles` at the mesh's current positions (so the shading follows a drag)."""
    position = mesh.vertex_position
    return [(position(a), position(b), position(c)) for a, b, c in triangles]


def triangle_colors(weights: Mapping[VertexId, float], triangles: list[Triangle]) -> list[tuple[RGBA, RGBA, RGBA]]:
    colour = {}
    result = []
    for tri in triangles:
        corner = []
        for v in tri:
            w = weights.get(v, 0.0)
            if w not in colour:
                colour[w] = shading_color(w)
            corner.append(colour[w])
        result.append(tuple(corner))
    return result  # type: ignore[return-value]
