"""Knife Face Lab — Variant Q5: segment planner (one screen segment -> visible crossings).

Adapted (not imported) from `experiments/topology/knife_cross_face_probe.py`
(WALK / PLANE planners, evidence base: `docs/research/topology/
KNIFE_CROSS_FACE_DISCOVERY.md` §2). Lab code, no Core change: it only reads the
mesh and returns the ordered crossings — `{"kind": "edge", "edge_id", "t"}` /
`{"kind": "vertex", "vertex_id"}` — between two path points as seen from one
camera. Turning them into path entries, pieces and gaps is the engine's job
(`engine_q5.py`).

Choice (Lab default, cost in decision.md): WALK first — walk face to face along
the 2D screen line (Wings-like, local, ~0.5 ms on `head`) — and PLANE only when
the walk fails or crosses a hidden surface: every edge is intersected with the
plane (eye, A, B) and only *visible* hits are kept (Blender-like, B8 occlusion
test). Where both succeed they cut identically (discovery §2.2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from mirai.topology.knife_pick import _edge_t_3d
from mirai.viewport.picking import DEPTH_TOLERANCE, edge_point_occluded, point_occluded, vertex_occluded

Position = tuple[float, float, float]

# Blender's KNIFE_FLT_EPS_PX_VERT (discovery §4): a vertex whose projection lies
# this close to the screen segment is a vertex hit, not two slivers next to it.
VERTEX_TOL_PX = 0.5
# An edge hit this close to the edge's end (in t) is a hit on the end vertex.
END_T_EPS = 1e-9


@dataclass
class View:
    """Everything camera-dependent the planner and the snap need. `cache` is the
    app's shared `PickCache` (optional; headless tests pass none)."""

    camera: object
    width: int
    height: int
    cache: object | None = None
    occlusion: bool = True
    _memo: dict = field(default_factory=dict, repr=False)

    def prepare(self, mesh) -> None:
        self._memo = {}
        if self.cache is not None:
            self.cache.refresh(self.camera, mesh, self.width, self.height)

    def p2(self, world: Position):
        s = self.camera.project_to_screen(world, self.width, self.height)
        return None if s is None else (s[0], s[1])

    def v2(self, mesh, vid):
        if self.cache is not None:
            s = self.cache.vertex_screen.get(vid)
            return None if s is None else (s[0], s[1])
        if vid not in self._memo:
            self._memo[vid] = self.p2(mesh.vertex_position(vid))
        return self._memo[vid]

    def edge_point_hidden(self, mesh, eid, t) -> bool:
        return bool(self.occlusion and edge_point_occluded(
            self.camera, mesh, self.cache, eid, t, self.width, self.height, DEPTH_TOLERANCE))

    def vertex_hidden(self, mesh, vid) -> bool:
        return bool(self.occlusion and vertex_occluded(
            self.camera, mesh, self.cache, vid, self.width, self.height, DEPTH_TOLERANCE))

    def point_hidden(self, mesh, world: Position, exclude_faces) -> bool:
        return bool(self.occlusion and point_occluded(
            self.camera, mesh, self.cache, world, self.width, self.height, exclude_faces, DEPTH_TOLERANCE))


@dataclass
class Crossings:
    crossings: list[dict]      # visible crossings in line order (may be empty)
    method: str                # "walk" | "plane" | "none"
    hidden: int = 0            # plane hits dropped by the occlusion test
    note: str = ""             # why the walk was not used ("" if it was)


# -- small helpers ---------------------------------------------------------------------

def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _cross3(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _lerp(a, b, t):
    return tuple(x + t * (y - x) for x, y in zip(a, b))


def point_position(mesh, p: dict) -> Position:
    """World position of a path point of any kind."""
    kind = p["kind"]
    if kind == "vertex":
        return mesh.vertex_position(p["vertex_id"])
    if kind == "face":
        return p["position"]
    va, vb = mesh.edge_vertices(p["edge_id"])
    return _lerp(mesh.vertex_position(va), mesh.vertex_position(vb), p["t"])


def point_faces(mesh, p: dict) -> set:
    kind = p["kind"]
    if kind == "face":
        return {p["face_id"]}
    if kind == "edge":
        return set(mesh.edge_faces(p["edge_id"]))
    return {f for e in mesh.vertex_edges(p["vertex_id"]) for f in mesh.edge_faces(e)}


def _point_in_poly(pt, poly) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > pt[1]) != (y2 > pt[1]):
            if x1 + (pt[1] - y1) * (x2 - x1) / (y2 - y1) > pt[0]:
                inside = not inside
    return inside


def _face_poly2(view, mesh, fid):
    pts = [view.v2(mesh, v) for v in mesh.face_vertices(fid)]
    return None if any(p is None for p in pts) else pts


def _pick_face_at(view, mesh, candidates, pt2):
    for f in sorted(candidates, key=int):
        poly = _face_poly2(view, mesh, f)
        if poly and _point_in_poly(pt2, poly):
            return f
    return None


def _face_in_direction(view, mesh, vid, candidates, dirn):
    """Face around `vid` whose screen-space corner at `vid` contains `dirn`."""
    v2 = view.v2(mesh, vid)
    for f in sorted(candidates, key=int):
        bd = mesh.face_vertices(f)
        i = bd.index(vid)
        u2, w2 = view.v2(mesh, bd[i - 1]), view.v2(mesh, bd[(i + 1) % len(bd)])
        if v2 is None or u2 is None or w2 is None:
            continue
        e1, e2 = _sub(u2, v2), _sub(w2, v2)
        c12 = _cross2(e1, e2)
        if abs(c12) < 1e-12:
            continue
        sign = 1.0 if c12 > 0 else -1.0
        if _cross2(e1, dirn) * sign > 0 and _cross2(dirn, e2) * sign > 0:
            return f
    return None


# -- WALK ------------------------------------------------------------------------------

@dataclass
class _Walk:
    ok: bool = False
    reason: str = ""
    crossings: list = field(default_factory=list)


def walk(view: View, mesh, a: dict, b: dict, *, vertex_tol_px=VERTEX_TOL_PX, max_steps=400) -> _Walk:
    res = _Walk()
    A2, B2 = view.p2(point_position(mesh, a)), view.p2(point_position(mesh, b))
    if A2 is None or B2 is None:
        res.reason = "end behind camera"
        return res
    d2 = _sub(B2, A2)
    L = math.hypot(*d2)
    if L < 1.0:
        res.reason = "segment < 1px"
        return res
    step_px = min(1.0, L / 4)
    dirn = (d2[0] / L, d2[1] / L)

    def target_in(face):
        if b["kind"] == "face":
            return face == b["face_id"]
        if b["kind"] == "edge":
            return b["edge_id"] in mesh.face_edges(face)
        return b["vertex_id"] in mesh.face_vertices(face)

    candidates = point_faces(mesh, a)
    probe = (A2[0] + dirn[0] * step_px, A2[1] + dirn[1] * step_px)
    cur = next(iter(candidates)) if len(candidates) == 1 else _pick_face_at(view, mesh, candidates, probe)
    if cur is None:
        res.reason = "start face ambiguous (line leaves along an edge or off the mesh)"
        return res
    s_cur = 0.0
    entry_edge = a["edge_id"] if a["kind"] == "edge" else None
    used_vertices = {a["vertex_id"]} if a["kind"] == "vertex" else set()

    def next_exit(face, s_from):
        best = None  # (s, kind, element)
        for v in mesh.face_vertices(face):
            if v in used_vertices:
                continue
            v2 = view.v2(mesh, v)
            if v2 is None:
                continue
            s = _dot(_sub(v2, A2), d2) / (L * L)
            if abs(_cross2(d2, _sub(v2, A2))) / L <= vertex_tol_px and s_from + 1e-9 < s and (best is None or s < best[0]):
                best = (s, "vertex", v)
        for e in mesh.face_edges(face):
            if e == entry_edge:
                continue
            va, vb = mesh.edge_vertices(e)
            if va in used_vertices or vb in used_vertices:
                continue
            pa2, pb2 = view.v2(mesh, va), view.v2(mesh, vb)
            if pa2 is None or pb2 is None:
                continue
            q = _sub(pb2, pa2)
            den = _cross2(d2, q)
            if abs(den) < 1e-12:
                continue
            ca = _sub(pa2, A2)
            s = _cross2(ca, q) / den
            u = _cross2(ca, d2) / den
            if not (-1e-9 <= u <= 1.0 + 1e-9) or s <= s_from + 1e-9:
                continue
            if best is None or s < best[0] - 1e-12:
                best = (s, "edge", e)
        return best

    for _ in range(max_steps):
        best = next_exit(cur, s_cur)
        if target_in(cur):
            # Stop only if the line does not leave this face before the target
            # (a concave face can be left and re-entered).
            if best is None or best[0] >= 1.0 - 1e-6:
                res.ok = True
                return res
        elif best is None:
            res.reason = "no exit edge found"
            return res
        elif best[0] >= 1.0 - 1e-6:
            res.reason = "segment ends before the target face is reached"
            return res
        s, kind, el = best
        x2 = (A2[0] + d2[0] * s, A2[1] + d2[1] * s)
        if kind == "edge":
            for vv in mesh.edge_vertices(el):
                vv2 = view.v2(mesh, vv)
                if vv2 is not None and math.hypot(vv2[0] - x2[0], vv2[1] - x2[1]) <= vertex_tol_px:
                    kind, el = "vertex", vv  # an edge hit that close to an end is a vertex hit
                    break
        if kind == "vertex":
            res.crossings.append({"kind": "vertex", "vertex_id": el})
            if b["kind"] == "vertex" and b["vertex_id"] == el:
                res.ok = True
                return res
            around = {f for e in mesh.vertex_edges(el) for f in mesh.edge_faces(e)} - {cur}
            nxt = _face_in_direction(view, mesh, el, around, dirn)
            if nxt is None:
                res.reason = "at a vertex: no face continues the line (border, silhouette or along an edge)"
                return res
            used_vertices.add(el)
            entry_edge, cur, s_cur = None, nxt, s
        else:
            va, vb = mesh.edge_vertices(el)
            origin, direction = view.camera.screen_to_ray(x2[0], x2[1], view.width, view.height)
            t = _edge_t_3d(origin, direction, mesh.vertex_position(va), mesh.vertex_position(vb))
            res.crossings.append({"kind": "edge", "edge_id": el, "t": t})
            others = [f for f in mesh.edge_faces(el) if f != cur]
            if not others:
                res.reason = "mesh border edge crossed"
                return res
            entry_edge, cur, s_cur = el, others[0], s
    res.reason = "step limit"
    return res


# -- PLANE -----------------------------------------------------------------------------

def plane_hits(view: View, mesh, a: dict, b: dict, *, vertex_tol_px=VERTEX_TOL_PX):
    """Visible hits of every edge with the plane (eye, A, B) whose projection lies
    on the screen segment; vertices within `vertex_tol_px` first (edges incident
    to a vertex hit are skipped — Blender's order). Returns (crossings, hidden)."""
    eye = view.camera.eye()
    pa, pb = point_position(mesh, a), point_position(mesh, b)
    A2, B2 = view.p2(pa), view.p2(pb)
    if A2 is None or B2 is None:
        return [], 0
    d2 = _sub(B2, A2)
    LL = _dot(d2, d2)
    if LL < 1.0:
        return [], 0
    L = math.sqrt(LL)
    n = _cross3(_sub(pa, eye), _sub(pb, eye))
    skip_edges = {q.get("edge_id") for q in (a, b) if q["kind"] == "edge"}
    skip_verts = {q["vertex_id"] for q in (a, b) if q["kind"] == "vertex"}
    for q in (a, b):
        if q["kind"] == "edge":
            skip_verts.update(mesh.edge_vertices(q["edge_id"]))
    lo_x, hi_x = min(A2[0], B2[0]) - 1.0, max(A2[0], B2[0]) + 1.0
    lo_y, hi_y = min(A2[1], B2[1]) - 1.0, max(A2[1], B2[1]) + 1.0

    hits, hidden, vhit = [], 0, set()
    for v in mesh.all_vertex_ids():
        if v in skip_verts:
            continue
        v2 = view.v2(mesh, v)
        if v2 is None or not (lo_x <= v2[0] <= hi_x and lo_y <= v2[1] <= hi_y):
            continue
        s = _dot(_sub(v2, A2), d2) / LL
        if not (1e-6 < s < 1.0 - 1e-6) or abs(_cross2(d2, _sub(v2, A2))) / L > vertex_tol_px:
            continue
        if view.vertex_hidden(mesh, v):
            hidden += 1
            continue
        vhit.add(v)
        hits.append((s, {"kind": "vertex", "vertex_id": v}))
    for e in mesh.all_edge_ids():
        if e in skip_edges:
            continue
        va, vb = mesh.edge_vertices(e)
        if va in vhit or vb in vhit:
            continue
        a2, b2 = view.v2(mesh, va), view.v2(mesh, vb)
        if a2 is not None and b2 is not None and (
            max(a2[0], b2[0]) < lo_x or min(a2[0], b2[0]) > hi_x
            or max(a2[1], b2[1]) < lo_y or min(a2[1], b2[1]) > hi_y
        ):
            continue  # projected edge never meets the segment's bbox (cheap prefilter)
        p0, p1 = mesh.vertex_position(va), mesh.vertex_position(vb)
        d0, d1 = _dot(n, _sub(p0, eye)), _dot(n, _sub(p1, eye))
        if d0 * d1 > 0.0 or d0 == d1:
            continue
        lam = d0 / (d0 - d1)
        if not (0.0 < lam < 1.0):
            continue
        if lam < END_T_EPS or lam > 1.0 - END_T_EPS:
            # A hit at the edge's end is a hit on that vertex (integrity finding R4): as an edge
            # hit it would become a second vertex on top of it. The segment's own end vertices
            # (and the ones of its end edges) are not tested as vertex hits above, so do it here.
            w = va if lam < 0.5 else vb
            own = {q["vertex_id"] for q in (a, b) if q["kind"] == "vertex"}
            if w in own or w in vhit:
                continue
            w2 = view.v2(mesh, w)
            if w2 is None:
                continue
            s = _dot(_sub(w2, A2), d2) / LL
            if not (1e-6 < s < 1.0 - 1e-6):
                continue
            if view.vertex_hidden(mesh, w):
                hidden += 1
                continue
            vhit.add(w)
            hits.append((s, {"kind": "vertex", "vertex_id": w}))
            continue
        x2 = view.p2(_lerp(p0, p1, lam))
        if x2 is None:
            continue
        s = _dot(_sub(x2, A2), d2) / LL
        if not (1e-6 < s < 1.0 - 1e-6):
            continue
        if view.edge_point_hidden(mesh, e, lam):
            hidden += 1
            continue
        hits.append((s, {"kind": "edge", "edge_id": e, "t": lam}))
    hits.sort(key=lambda h: h[0])
    return [h[1] for h in hits], hidden


# -- public entry ----------------------------------------------------------------------

def _walk_hidden(view: View, mesh, crossings) -> bool:
    for c in crossings:
        if c["kind"] == "edge":
            if view.edge_point_hidden(mesh, c["edge_id"], c["t"]):
                return True
        elif view.vertex_hidden(mesh, c["vertex_id"]):
            return True
    return False


def plan_crossings(view: View, mesh, a: dict, b: dict) -> Crossings:
    """Visible crossings between path points `a` and `b` under `view`'s camera.

    Calls `view.prepare(mesh)` — one refresh per plan; the mesh does not change
    during a session (Variant D's virtual path), so cached projections stay valid."""
    view.prepare(mesh)
    w = walk(view, mesh, a, b)
    if w.ok and not _walk_hidden(view, mesh, w.crossings):
        return Crossings(w.crossings, "walk")
    note = w.reason if not w.ok else "walk crossed a hidden surface"
    if w.reason in ("end behind camera", "segment < 1px"):
        return Crossings([], "none", 0, w.reason)
    hits, hidden = plane_hits(view, mesh, a, b)
    return Crossings(hits, "plane", hidden, note)
