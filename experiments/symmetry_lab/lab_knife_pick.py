"""Knife-Picking des Labs: Cursor → Knife-Ziel. GL-frei.

Handoff WP-SYM-LAB-01 Slice 7, E27. Herkunft (Präzedenz AD-010 wie E16):
kopiert und adaptiert — nicht importiert — aus
`playground/topology_tools/knife_pick.py` (`knife_pick`, `_edge_t_3d`,
`ENDPOINT_THRESHOLD`), Stand `649fff5`. Das Playground-Original bleibt
unverändert. Benutzt nur `mirai.viewport.picking` (unverändert, wie die
Vorlage).

Abweichung von der Vorlage: kein `debug`-Parameter — das Lab hat kein
Äquivalent zu den `[KNIFE]`-Konsolen-Traces des Playground.

Reihenfolge wie die Vorlage: Vertex-Treffer zuerst; sonst Edge-Treffer mit
perspektivisch korrektem 3D-`t` (nächster Punkt zwischen Sichtstrahl und
Edge-Segment im Weltraum); `t` innerhalb `ENDPOINT_THRESHOLD` an einem Ende →
dieser Endpunkt als Vertex; sonst Face-Treffer → „auf dem Mesh, kein Ziel";
sonst „außerhalb".
"""

from __future__ import annotations

from mirai.viewport.picking import pick_face, pick_nearest_edge, pick_nearest_vertex

#: `t` so nah an 0 oder 1 rastet auf den Endpunkt ein (Wert wie die Vorlage).
ENDPOINT_THRESHOLD = 0.05

_Vec3 = tuple[float, float, float]


def _dot3(a: _Vec3, b: _Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub3(a: _Vec3, b: _Vec3) -> _Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _edge_t_3d(origin: _Vec3, direction: _Vec3, p0: _Vec3, p1: _Vec3) -> float:
    """Segment-Parameter `t` in [0, 1] des Punkts auf p0→p1, der dem Sichtstrahl
    am nächsten liegt (Ericson §5.1.8). Hier ist `a` das Segment- und `c` das
    Strahl-Skalarprodukt — daher `(c * d_val - b * e)`; das umgekehrte
    Vorzeichen liefert den negierten Parameter (Vorlage, dort dokumentiert)."""
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
    t = (c * d_val - b * e) / denom
    return max(0.0, min(1.0, t))


def knife_pick(camera, mesh, sx: float, sy: float, width: int, height: int) -> dict:
    """Cursor → eines von:

      {"kind": "vertex", "vertex_id": vid}
      {"kind": "edge", "edge_id": eid, "t": float}  — t in (THRESHOLD, 1-THRESHOLD)
      {"kind": "face", "face_id": fid}               — auf dem Mesh, kein Ziel
      {"kind": "outside"}
    """
    vid = pick_nearest_vertex(camera, mesh, sx, sy, width, height)
    if vid is not None:
        return {"kind": "vertex", "vertex_id": vid}

    eid = pick_nearest_edge(camera, mesh, sx, sy, width, height)
    if eid is not None:
        origin, direction = camera.screen_to_ray(sx, sy, width, height)
        va, vb = mesh.edge_vertices(eid)
        t = _edge_t_3d(origin, direction, mesh.vertex_position(va), mesh.vertex_position(vb))
        if t <= ENDPOINT_THRESHOLD:
            return {"kind": "vertex", "vertex_id": va}
        if t >= 1.0 - ENDPOINT_THRESHOLD:
            return {"kind": "vertex", "vertex_id": vb}
        return {"kind": "edge", "edge_id": eid, "t": t}

    fid = pick_face(camera, mesh, sx, sy, width, height)
    if fid is not None:
        return {"kind": "face", "face_id": fid}
    return {"kind": "outside"}
