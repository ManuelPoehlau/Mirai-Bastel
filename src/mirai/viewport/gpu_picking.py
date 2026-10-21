"""GPU-backed component picking for the window (AD-022 B2-out, 2026-10-21).

The ID buffers (`viewport.gpu_picker.GpuPicker`) say *which* elements are visible near the cursor; the decision
among those few stays the CPU picker's rule, so the two paths differ only where visibility or pixel sampling does
(AD-022 §4, the Artist's practical check):

- vertex: among the vertex IDs within `VERTEX_RADIUS_PX`, the nearest by exact screen distance
  (`camera.project_to_screen`, as `pick_nearest_vertex`), ties by ID;
- edge: among the edge IDs within `EDGE_RADIUS_PX`, the nearest by exact distance to the projected segment
  (as `pick_nearest_edge`), ties by ID;
- face: the face under the cursor's pixel (pixel-centre convention);
- Box (`elements_in_rect`): the CPU candidate rule (all corners inside the rectangle, `PickCache` projections)
  with the depth buffer as the visibility test instead of one ray test per element ("depth oracle", AD-022 §3).

Only the edit object's components in the window. The Knife (exact math, planner), object mode, the Box/Paint
start decision and every headless path keep the CPU picker (`picking.py`), which stays the reference.
"""

from __future__ import annotations

import math

from core import EdgeId, FaceId, Mesh, SelectionMode, VertexId

from .picking import _point_segment_distance
from .picking_cache import PickCache

VERTEX_RADIUS_PX = 14.0
EDGE_RADIUS_PX = 9.0


def gpu_pick_component(picker, render_mesh, camera, mesh: Mesh, mode, x: float, y: float,
                       width: int, height: int, *, occlusion: bool):
    """Element under the cursor in `mode` (vertex / edge / face), or None. `picker` must be prepared
    for this frame's buffers (`GpuPicker.prepare` is called here)."""
    from viewport.gpu_picker import EDGES, FACES, POINTS

    if mode is SelectionMode.FACE:
        picker.prepare(render_mesh, width, height, occlusion=occlusion, target=FACES)
        face = picker.face_at(render_mesh, x, y)
        return face if face is not None and mesh.is_valid_face(face) else None
    if mode is SelectionMode.VERTEX:
        picker.prepare(render_mesh, width, height, occlusion=occlusion, target=POINTS)
        best = None
        for vid in picker.vertices_near(render_mesh, x, y, VERTEX_RADIUS_PX):
            if not mesh.is_valid_vertex(vid):
                continue
            p = camera.project_to_screen(mesh.vertex_position(vid), width, height)
            if p is None:
                continue
            d = math.hypot(p[0] - x, p[1] - y)
            if d < VERTEX_RADIUS_PX and (best is None or (d, vid) < best):
                best = (d, vid)
        return None if best is None else VertexId(best[1])
    picker.prepare(render_mesh, width, height, occlusion=occlusion, target=EDGES)
    best = None
    for eid in picker.edges_near(render_mesh, x, y, EDGE_RADIUS_PX):
        if not mesh.is_valid_edge(eid):
            continue
        va, vb = mesh.edge_vertices(eid)
        a = camera.project_to_screen(mesh.vertex_position(va), width, height)
        b = camera.project_to_screen(mesh.vertex_position(vb), width, height)
        if a is None or b is None:
            continue
        d = _point_segment_distance(x, y, a[0], a[1], b[0], b[1])
        if d < EDGE_RADIUS_PX and (best is None or (d, eid) < best):
            best = (d, eid)
    return None if best is None else EdgeId(best[1])


def gpu_elements_in_rect(picker, render_mesh, camera, mesh: Mesh, mode, rect, width: int, height: int,
                         *, cache: PickCache, occlusion: bool) -> set:
    """Box Select: elements of `mode` whose corners all project into `rect` (as `box_select.elements_in_rect`)
    and, with `occlusion`, whose vertex / edge midpoint / face centroid is not behind the face depth."""
    from viewport.gpu_picker import FACES

    cache.refresh(camera, mesh, width, height)
    screen = cache.vertex_screen
    x0, y0, x1, y1 = rect
    inside = {
        vid for vid, p in screen.items()
        if p is not None and x0 <= p[0] <= x1 and y0 <= p[1] <= y1
    }
    visible = face_under = None
    if occlusion:
        picker.prepare(render_mesh, width, height, occlusion=True, target=FACES)
        visible = picker.visibility(x0, y0, x1, y1)
    position = mesh.vertex_position

    if mode is SelectionMode.VERTEX:
        return {VertexId(v) for v in inside if visible is None or visible(position(v))}

    if mode is SelectionMode.EDGE:
        edges = set()
        for eid in mesh.all_edge_ids():
            a, b = mesh.edge_vertices(eid)
            if a in inside and b in inside:
                if visible is not None:
                    pa, pb = position(a), position(b)
                    mid = (pa[0] + (pb[0] - pa[0]) * 0.5, pa[1] + (pb[1] - pa[1]) * 0.5,
                           pa[2] + (pb[2] - pa[2]) * 0.5)
                    if not visible(mid):
                        continue
                edges.add(EdgeId(eid))
        return edges

    if visible is not None:
        # A non-planar quad's centroid can lie behind its own triangles: the face's own ID at the
        # centroid's pixel counts as visible (the CPU test excludes the face itself).
        face_under = picker.face_lookup(render_mesh, x0, y0, x1, y1)
    faces = set()
    for fid in mesh.all_face_ids():
        corners = mesh.face_vertices(fid)
        if not all(v in inside for v in corners):
            continue
        if visible is not None:
            pts = [position(v) for v in corners]
            n = len(pts)
            centroid = (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)
            if not visible(centroid) and face_under(centroid) != fid:
                continue
        faces.add(FaceId(fid))
    return faces
