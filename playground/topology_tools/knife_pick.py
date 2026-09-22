"""Knife picking — resolve screen cursor to knife target (AD-017 §1.8).

Reuses src/mirai/viewport/picking.py without modification.
Priority order: vertex hit first; else edge hit with perspective-correct 3D t;
endpoint threshold → treat as vertex; else face hit → "on mesh, no target";
else "outside mesh".

The 3D t is computed as the closest point between the view ray and the edge
segment in world space (not screen space).
"""

from __future__ import annotations

from mirai.viewport.picking import pick_nearest_vertex, pick_nearest_edge, pick_face

ENDPOINT_THRESHOLD = 0.05  # t values within this threshold of 0 or 1 snap to vertex

_Vec3 = tuple[float, float, float]


def _dot3(a: _Vec3, b: _Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub3(a: _Vec3, b: _Vec3) -> _Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _edge_t_3d(origin: _Vec3, direction: _Vec3, p0: _Vec3, p1: _Vec3) -> float:
    """Perspective-correct t: closest point on edge segment to view ray.

    Returns t in [0, 1] where t=0 is p0, t=1 is p1.
    """
    d = _sub3(p1, p0)
    w = _sub3(origin, p0)
    a = _dot3(d, d)
    b = _dot3(d, direction)
    c = _dot3(direction, direction)
    d_val = _dot3(d, w)
    e = _dot3(direction, w)
    denom = a * c - b * b
    if abs(denom) < 1e-10:
        return 0.0
    t = (b * e - c * d_val) / denom
    return max(0.0, min(1.0, t))


def knife_pick(
    camera, mesh, sx: float, sy: float, width: int, height: int, debug: bool = False
) -> dict:
    """Resolve cursor position to a knife target.

    Returns one of:
      {"kind": "vertex", "vertex_id": vid}
      {"kind": "edge", "edge_id": eid, "t": float}  — t in (THRESHOLD, 1-THRESHOLD)
      {"kind": "face", "face_id": fid}               — "on mesh, no target"
      {"kind": "outside"}

    debug=True prints the temporary [KNIFE] pick trace (AD-017 diagnosis).
    Hover calls must pass debug=False to avoid flooding the console.
    """
    if debug:
        print(f"[KNIFE] pick cursor=({sx:.1f},{sy:.1f})")

    # Vertex hit first
    vid = pick_nearest_vertex(camera, mesh, sx, sy, width, height)
    if debug:
        print(f"[KNIFE] pick_nearest_vertex -> vertex:{int(vid)}" if vid is not None
              else "[KNIFE] pick_nearest_vertex -> None")
    if vid is not None:
        return {"kind": "vertex", "vertex_id": vid}

    # Edge hit with perspective-correct t
    eid = pick_nearest_edge(camera, mesh, sx, sy, width, height)
    if debug:
        print(f"[KNIFE] pick_nearest_edge -> edge:{int(eid)}" if eid is not None
              else "[KNIFE] pick_nearest_edge -> None")
    if eid is not None:
        origin, direction = camera.screen_to_ray(sx, sy, width, height)
        va, vb = mesh.edge_vertices(eid)
        p0 = mesh.vertex_position(va)
        p1 = mesh.vertex_position(vb)
        t = _edge_t_3d(origin, direction, p0, p1)
        if debug:
            print(f"[KNIFE] EdgePoint t={t:.6f} on edge:{int(eid)} "
                  f"({int(va)}-{int(vb)}), snap thresholds {ENDPOINT_THRESHOLD}/{1.0 - ENDPOINT_THRESHOLD}")
        if t <= ENDPOINT_THRESHOLD:
            if debug:
                print(f"[KNIFE] t<=threshold -> snap to vertex:{int(va)}")
            return {"kind": "vertex", "vertex_id": va}
        if t >= 1.0 - ENDPOINT_THRESHOLD:
            if debug:
                print(f"[KNIFE] t>=1-threshold -> snap to vertex:{int(vb)}")
            return {"kind": "vertex", "vertex_id": vb}
        return {"kind": "edge", "edge_id": eid, "t": t}

    # Face hit → "on mesh, no target"
    fid = pick_face(camera, mesh, sx, sy, width, height)
    if debug:
        print(f"[KNIFE] pick_face -> face:{int(fid)}" if fid is not None
              else "[KNIFE] pick_face -> None")
    if fid is not None:
        return {"kind": "face", "face_id": fid}

    if debug:
        print("[KNIFE] pick -> outside")
    return {"kind": "outside"}
