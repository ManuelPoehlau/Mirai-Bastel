"""Box Select and Paint Select picking (promoted 2026-10-15, Manu: "die Playground-Werkzeuge in
Production einbauen"; Box verdict KEEP in `playground/experiments/selection/decision.md`).

Pure screen-space queries over `PickCache`; `Application` owns the gesture and the selection.

- Box: an element is inside when all its corners project into the rectangle (Playground
  `selector.pick_faces_in_rect`: "alle Vertices der Face müssen im Rechteck sein"), extended to
  vertices and edges. With `occlusion` (faces shown) hidden elements are skipped, with the same
  occlusion test the click picking uses (WP-06 B8) - a box selects what you see. WP-VIEW-PERF-01
  Slice 2: one `point_occlusion_test` per box (eye and projection once), and each test visits
  only the faces of its point's `PickCache.face_grid` cell - the same elements as one full
  `vertex_occluded` / `edge_point_occluded` / `point_occluded` per element
  (`tests/test_picking_equivalence.py`).
- Paint: `stroke_samples` spaces the pick points along one pointer step, so a fast stroke does not
  skip the thin targets between two motion events (the open performance point in the Selection
  decision: one pick per sample, cached projections).
"""

from __future__ import annotations

import math

from core import EdgeId, FaceId, Mesh, SelectionMode, VertexId

from .picking import _incident_faces_of_vertex, point_occlusion_test
from .picking_cache import PickCache

#: Pixels between two paint pick samples (`PROVISIONAL`, engineering default).
PAINT_SAMPLE_PX = 6.0


def normalized_rect(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float, float, float]:
    """(min x, min y, max x, max y) of the rectangle spanned by two corners."""
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def _inside(point, rect) -> bool:
    if point is None:
        return False
    x0, y0, x1, y1 = rect
    return x0 <= point[0] <= x1 and y0 <= point[1] <= y1


def elements_in_rect(
    camera,
    mesh: Mesh,
    mode: SelectionMode,
    rect: tuple[float, float, float, float],
    width: int,
    height: int,
    *,
    cache: PickCache,
    occlusion: bool,
) -> set:
    """Vertices / edges / faces (by `mode`) whose corners all lie in `rect` and, with
    `occlusion`, that are not hidden behind a nearer face."""
    cache.refresh(camera, mesh, width, height)
    screen = cache.vertex_screen
    inside_vertices = {vid for vid, point in screen.items() if _inside(point, rect)}
    occluded = point_occlusion_test(camera, mesh, cache, width, height) if occlusion else None

    if mode is SelectionMode.VERTEX:
        found: set = set(inside_vertices)
        if occluded is not None:
            position = mesh.vertex_position
            found = {
                vid for vid in found
                if not occluded(position(vid), _incident_faces_of_vertex(mesh, vid, cache), screen[vid])
            }
        return {VertexId(v) for v in found}

    if mode is SelectionMode.EDGE:
        edges = set()
        for eid in mesh.all_edge_ids():
            a, b = mesh.edge_vertices(eid)
            if a in inside_vertices and b in inside_vertices:
                if occluded is not None:
                    # The point `edge_point_occluded(..., t=0.5)` tests, computed the same way.
                    pa, pb = mesh.vertex_position(a), mesh.vertex_position(b)
                    midpoint = (
                        pa[0] + (pb[0] - pa[0]) * 0.5,
                        pa[1] + (pb[1] - pa[1]) * 0.5,
                        pa[2] + (pb[2] - pa[2]) * 0.5,
                    )
                    if occluded(midpoint, set(mesh.edge_faces(eid))):
                        continue
                edges.add(EdgeId(eid))
        return edges

    faces = set()
    for fid in mesh.all_face_ids():
        corners = mesh.face_vertices(fid)
        if not all(v in inside_vertices for v in corners):
            continue
        if occluded is not None:
            positions = [mesh.vertex_position(v) for v in corners]
            centroid = tuple(sum(p[i] for p in positions) / len(positions) for i in range(3))
            if occluded(centroid, {fid}):
                continue
        faces.add(FaceId(fid))
    return faces


def stroke_samples(
    start: tuple[float, float], end: tuple[float, float], spacing: float = PAINT_SAMPLE_PX
) -> list[tuple[float, float]]:
    """Points from `start` (exclusive) to `end` (inclusive), at most `spacing` px apart."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    steps = max(1, int(math.ceil(math.hypot(dx, dy) / spacing)))
    return [(start[0] + dx * i / steps, start[1] + dy * i / steps) for i in range(1, steps + 1)]
