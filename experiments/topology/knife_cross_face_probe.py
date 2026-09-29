"""DISCOVERY PROBE — Knife Q5: one segment across several faces (cross-face segments).

Evidence for `docs/research/topology/KNIFE_CROSS_FACE_DISCOVERY.md` (X2-X7).
Not a tool, not wired anywhere, no Core change, no Playground change.

What it uses:
  - public Core API (Mesh, Scene, split_edge / connect_vertices via the lab resolver);
  - existing read-only helpers: `OrbitCamera` (screen_to_ray / project_to_screen),
    `knife_face_pick` (lab picking), `_edge_t_3d` (Knife's perspective-correct edge t),
    B8's `_edge_point_occluded` / `_vertex_occluded` (the occlusion test the pickers use);
  - Variant D's session engine (`KnifeFaceCollected`) as the *existing resolver*, driven
    through `click()` / `commit()`. Two probe-local deviations, both marked where used:
      (a) `_DNoA5Lock` clears the A5 lock after every click — the Q5 variant's premise
          (X6); the engine file itself is not touched;
      (b) P7 "cyclic" assigns a rotated path list directly to test one resolution idea.

Two segment planners (probe-local; the question X2 compares them):
  WALK   Wings-like: walk face to face along the 2D screen line, crossing the edge the
         line leaves the current face through (vertex hit if within `vertex_tol_px`).
  PLANE  Blender-like: intersect every edge with the plane (eye, A, B), keep hits whose
         projection lies on the screen segment, optionally drop occluded ones (B8 test).

Run:  python experiments/topology/knife_cross_face_probe.py
"""

from __future__ import annotations

import collections
import math
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
# src/ last-inserted = first on sys.path: the top-level `viewport` must resolve to src/viewport.
for _p in (str(_ROOT / "tests"), str(_ROOT / "examples"), str(_ROOT), str(_ROOT / "src")):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from core import Mesh, Scene  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402
from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402
from mirai.topology.knife_pick import _edge_t_3d  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from mirai.viewport.picking import DEPTH_TOLERANCE, _edge_point_occluded, _vertex_occluded  # noqa: E402
from playground._paths import DEFAULT_HEAD_ASSET  # noqa: E402
from playground.experiments.knife_face.engine import KnifeFaceCollected, knife_face_pick  # noqa: E402

W, H = 1280, 800


# -- small vector helpers --------------------------------------------------------------

def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _scale(a, s):
    return tuple(x * s for x in a)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross3(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _len(a):
    return math.sqrt(_dot(a, a))


def _lerp(a, b, t):
    return tuple(x + t * (y - x) for x, y in zip(a, b))


# -- meshes / cameras -------------------------------------------------------------------

def _grid(n=4, hole=None):
    m, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = m.add_vertex((float(c), float(r), 0.0))
    faces = {}
    for r in range(n):
        for c in range(n):
            if (c, r) == hole:
                continue
            faces[(c, r)] = m.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return m, p, faces


def _l_mesh():
    """Concave L-hexagon + the square that fills its notch (X4 'segment re-enters a face')."""
    m = Mesh()
    v = {xy: m.add_vertex((float(xy[0]), float(xy[1]), 0.0))
         for xy in [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2), (2, 2)]}
    f_l = m.add_face([v[(0, 0)], v[(2, 0)], v[(2, 1)], v[(1, 1)], v[(1, 2)], v[(0, 2)]])
    f_sq = m.add_face([v[(1, 1)], v[(2, 1)], v[(2, 2)], v[(1, 2)]])
    return m, v, f_l, f_sq


def _head():
    return build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh


def _cam_for(mesh, yaw_deg, pitch_deg, margin=1.4):
    cam = OrbitCamera(yaw=math.radians(yaw_deg), pitch=math.radians(pitch_deg))
    center, radius = mesh_center_and_radius(mesh)
    cam.frame_on_bounds(center, radius, margin=margin)
    return cam


def _edge(m, a, b):
    return next(e for e in m.all_edge_ids() if set(m.edge_vertices(e)) == {a, b})


def _sizes(m):
    return dict(sorted(collections.Counter(len(m.face_vertices(f)) for f in m.all_face_ids()).items()))


def _check(m, label):
    try:
        assert_mesh_invariants(m, context=label)
        return "invariants OK"
    except AssertionError as exc:
        return f"INVARIANT VIOLATION: {str(exc)[:90]}"


# -- point helpers ----------------------------------------------------------------------

def _pos(m, p):
    k = p["kind"]
    if k == "vertex":
        return m.vertex_position(p["vertex_id"])
    if k == "face":
        return p["position"]
    va, vb = m.edge_vertices(p["edge_id"])
    return _lerp(m.vertex_position(va), m.vertex_position(vb), p["t"])


def _faces_of(m, p):
    k = p["kind"]
    if k == "face":
        return {p["face_id"]}
    if k == "edge":
        return set(m.edge_faces(p["edge_id"]))
    return {f for e in m.vertex_edges(p["vertex_id"]) for f in m.edge_faces(e)}


def _edge_pt(m, a, b, t_from_a):
    e = _edge(m, a, b)
    t = t_from_a if m.edge_vertices(e)[0] == a else 1.0 - t_from_a
    return {"kind": "edge", "edge_id": e, "t": t}


def _face_pt_from_world(cam, m, world):
    """Pick a face-interior point exactly as the window does: project, then knife_face_pick."""
    s = cam.project_to_screen(world, W, H)
    return knife_face_pick(cam, m, s[0], s[1], W, H, occlusion=True), s


def _proj2(cam, p):
    s = cam.project_to_screen(p, W, H)
    return None if s is None else (s[0], s[1])


def _point_in_poly(pt, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > pt[1]) != (y2 > pt[1]):
            x = x1 + (pt[1] - y1) * (x2 - x1) / (y2 - y1)
            if x > pt[0]:
                inside = not inside
    return inside


def _face_poly2(cam, m, f):
    pts = [_proj2(cam, m.vertex_position(v)) for v in m.face_vertices(f)]
    return None if any(p is None for p in pts) else pts


def _face_normal(m, f):
    vs = [m.vertex_position(v) for v in m.face_vertices(f)]
    n = [0.0, 0.0, 0.0]
    for i in range(len(vs)):
        a, b = vs[i], vs[(i + 1) % len(vs)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return tuple(n)


def _front_facing(cam, m, f):
    vs = [m.vertex_position(v) for v in m.face_vertices(f)]
    c = tuple(sum(p[k] for p in vs) / len(vs) for k in range(3))
    return _dot(_face_normal(m, f), _sub(cam.eye(), c)) > 0.0


def _pick_face_at(cam, m, candidates, pt2):
    for f in sorted(candidates, key=int):
        poly = _face_poly2(cam, m, f)
        if poly and _point_in_poly(pt2, poly):
            return f
    return None


# -- planner 1: WALK (Wings-like screen-line walk across edges) ------------------------

class WalkResult:
    def __init__(self):
        self.ok = False
        self.reason = ""
        self.crossings: list[dict] = []   # edge/vertex point dicts, in line order
        self.faces: list = []              # face sequence the walk passed through
        self.s: list[float] = []           # screen-line parameter of each crossing


def walk(cam, m, a, b, *, vertex_tol_px=0.5, max_steps=400) -> WalkResult:
    res = WalkResult()
    A2, B2 = _proj2(cam, _pos(m, a)), _proj2(cam, _pos(m, b))
    if A2 is None or B2 is None:
        res.reason = "end behind camera"
        return res
    d2 = _sub(B2, A2)
    L = _len(d2)
    if L < 1.0:
        res.reason = "segment < 1px"
        return res
    step_px = min(1.0, L / 4)
    dirn = _scale(d2, 1.0 / L)

    def target_in(face):
        k = b["kind"]
        if k == "face":
            return face == b["face_id"]
        if k == "edge":
            return b["edge_id"] in m.face_edges(face)
        return b["vertex_id"] in m.face_vertices(face)

    start_candidates = _faces_of(m, a)
    probe = _add(A2, _scale(dirn, step_px))
    cur = next(iter(start_candidates)) if len(start_candidates) == 1 else _pick_face_at(cam, m, start_candidates, probe)
    if cur is None:
        res.reason = "start face ambiguous (line leaves along an edge or off the mesh)"
        return res
    res.faces.append(cur)
    s_cur = 0.0
    entry_edge, entry_vertex = (a["edge_id"] if a["kind"] == "edge" else None), (a["vertex_id"] if a["kind"] == "vertex" else None)
    used_vertices = {entry_vertex} if entry_vertex is not None else set()

    def next_exit(face, s_from):
        best = None  # (s, kind, element)
        for v in m.face_vertices(face):
            if v in used_vertices:
                continue
            v2 = _proj2(cam, m.vertex_position(v))
            if v2 is None:
                continue
            s = _dot(_sub(v2, A2), d2) / (L * L)
            dist = abs(_cross2(d2, _sub(v2, A2))) / L
            if dist <= vertex_tol_px and s_from + 1e-9 < s and (best is None or s < best[0]):
                best = (s, "vertex", v)
        for e in m.face_edges(face):
            if e == entry_edge:
                continue
            va, vb = m.edge_vertices(e)
            if va in used_vertices or vb in used_vertices:
                continue
            pa2, pb2 = _proj2(cam, m.vertex_position(va)), _proj2(cam, m.vertex_position(vb))
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
            # Stop only if the line does not leave this face before reaching the target
            # (a concave face can be left and re-entered — P5).
            if best is None or best[0] >= 1.0 - 1e-6:
                res.ok = True
                return res
        elif best is None:
            res.reason = "no exit edge found"
            return res
        elif best[0] >= 1.0 - 1e-6:
            res.reason = "segment ends before the target face is reached (overshoot)"
            return res
        s, kind, el = best
        x2 = _add(A2, _scale(d2, s))
        if kind == "edge":
            va, vb = m.edge_vertices(el)
            # an edge hit within vertex_tol of an endpoint is a vertex hit (Blender rule)
            for vv in (va, vb):
                vv2 = _proj2(cam, m.vertex_position(vv))
                if _len(_sub(vv2, x2)) <= vertex_tol_px:
                    kind, el = "vertex", vv
                    break
        if kind == "vertex":
            v = el
            res.crossings.append({"kind": "vertex", "vertex_id": v})
            res.s.append(s)
            if b["kind"] == "vertex" and b["vertex_id"] == v:
                res.ok = True
                return res
            around = {f for e in m.vertex_edges(v) for f in m.edge_faces(e)} - {cur}
            nxt = _face_in_direction(cam, m, v, around, dirn)
            if nxt is None:
                res.reason = "at a vertex: no face continues the line (border, silhouette or along an edge)"
                return res
            used_vertices.add(v)
            entry_edge, cur, s_cur = None, nxt, s
        else:
            e = el
            va, vb = m.edge_vertices(e)
            origin, direction = cam.screen_to_ray(x2[0], x2[1], W, H)
            t = _edge_t_3d(origin, direction, m.vertex_position(va), m.vertex_position(vb))
            res.crossings.append({"kind": "edge", "edge_id": e, "t": t})
            res.s.append(s)
            others = [f for f in m.edge_faces(e) if f != cur]
            if not others:
                res.reason = "mesh border edge crossed"
                return res
            entry_edge, cur, s_cur = e, others[0], s
        res.faces.append(cur)
    res.reason = "step limit"
    return res


def _face_in_direction(cam, m, v, candidates, dirn):
    """Face around vertex `v` whose screen-space corner sector at `v` contains `dirn`
    (the smaller angle between v's two boundary neighbours in that face)."""
    v2 = _proj2(cam, m.vertex_position(v))
    for f in sorted(candidates, key=int):
        bd = m.face_vertices(f)
        i = bd.index(v)
        u2 = _proj2(cam, m.vertex_position(bd[i - 1]))
        w2 = _proj2(cam, m.vertex_position(bd[(i + 1) % len(bd)]))
        if u2 is None or w2 is None:
            continue
        e1, e2 = _sub(u2, v2), _sub(w2, v2)
        c12 = _cross2(e1, e2)
        if abs(c12) < 1e-12:
            continue
        sign = 1.0 if c12 > 0 else -1.0
        if _cross2(e1, dirn) * sign > 0 and _cross2(dirn, e2) * sign > 0:
            return f
    return None


# -- planner 2: PLANE (Blender-like: all edges vs the plane through eye, A, B) ---------

def plane_hits(cam, m, a, b, *, occlusion: bool, vertex_tol_px=0.5):
    """Returns ([(s, ('v'|'e', id), lam)], hidden_count). Vertex hits first (projected
    vertex within vertex_tol of the screen line); edges incident to a vertex hit are
    skipped (Blender's order in knife_find_line_hits)."""
    eye = cam.eye()
    pa, pb = _pos(m, a), _pos(m, b)
    n = _cross3(_sub(pa, eye), _sub(pb, eye))
    A2, B2 = _proj2(cam, pa), _proj2(cam, pb)
    d2 = _sub(B2, A2)
    LL = _dot(d2, d2)
    L = math.sqrt(LL)
    skip_edges = {a.get("edge_id"), b.get("edge_id")}
    skip_verts = {a.get("vertex_id"), b.get("vertex_id")}
    for q in (a, b):
        if q["kind"] == "edge":
            skip_verts.update(m.edge_vertices(q["edge_id"]))
    hits, hidden = [], 0
    vhit = set()
    for v in m.all_vertex_ids():
        if v in skip_verts:
            continue
        v2 = _proj2(cam, m.vertex_position(v))
        if v2 is None:
            continue
        s = _dot(_sub(v2, A2), d2) / LL
        if not (1e-6 < s < 1.0 - 1e-6) or abs(_cross2(d2, _sub(v2, A2))) / L > vertex_tol_px:
            continue
        if occlusion and _vertex_occluded(cam, m, None, v, W, H, DEPTH_TOLERANCE):
            hidden += 1
            continue
        vhit.add(v)
        hits.append((s, ("v", v), None))
    for e in m.all_edge_ids():
        if e in skip_edges:
            continue
        va, vb = m.edge_vertices(e)
        if va in vhit or vb in vhit:
            continue
        p0, p1 = m.vertex_position(va), m.vertex_position(vb)
        d0, d1 = _dot(n, _sub(p0, eye)), _dot(n, _sub(p1, eye))
        if d0 * d1 > 0.0 or d0 == d1:
            continue
        lam = d0 / (d0 - d1)
        if not (0.0 < lam < 1.0):
            continue
        x2 = _proj2(cam, _lerp(p0, p1, lam))
        if x2 is None:
            continue
        s = _dot(_sub(x2, A2), d2) / LL
        if not (1e-6 < s < 1.0 - 1e-6):
            continue
        if occlusion and _edge_point_occluded(cam, m, None, e, lam, W, H, DEPTH_TOLERANCE):
            hidden += 1
            continue
        hits.append((s, ("e", e), lam))
    hits.sort(key=lambda h: h[0])
    return hits, hidden


def _hit_points(hits):
    return [{"kind": "vertex", "vertex_id": el[1]} if el[0] == "v" else {"kind": "edge", "edge_id": el[1], "t": lam}
            for _s, el, lam in hits]


def _occluded_crossings(cam, m, crossings):
    out = 0
    for c in crossings:
        if c["kind"] == "edge":
            out += _edge_point_occluded(cam, m, None, c["edge_id"], c["t"], W, H, DEPTH_TOLERANCE)
        else:
            out += _vertex_occluded(cam, m, None, c["vertex_id"], W, H, DEPTH_TOLERANCE)
    return out


def _same_hits(wr: WalkResult, hits):
    """Walk crossings == plane hits (same elements, same order)? max |dt| over edge hits."""
    w = [("v", c["vertex_id"]) if c["kind"] == "vertex" else ("e", c["edge_id"]) for c in wr.crossings]
    p = [el for _s, el, _lam in hits]
    if w != p:
        return False, None
    dts = [abs(c["t"] - lam) for c, (_s, el, lam) in zip(wr.crossings, hits) if el[0] == "e"]
    return True, max(dts, default=0.0)


# -- applying a planned path through Variant D's resolver ------------------------------

class _DNoA5Lock(KnifeFaceCollected):
    """PROBE-LOCAL: Variant D with the A5 lock cleared after every click (X6 premise)."""

    def click(self, target):
        ok = super().click(target)
        self._face_cut_lock = False
        return ok


def _scene(mesh):
    sc = Scene()
    sc.mesh = mesh
    return sc


def _begin(cls, scene):
    k = cls()
    k.activate()
    k.begin(mesh=scene.mesh, scene=scene, selection=scene.selection)
    return k


def _ids(m):
    return (set(m.all_vertex_ids()), set(m.all_edge_ids()), set(m.all_face_ids()))


def _id_continuity(before, m):
    vb, eb, fb = before
    va, ea, fa = _ids(m)
    old_v_kept = vb <= va
    new_v = va - vb
    new_e = ea - eb
    new_f = fa - fb
    mono = (all(int(x) > max(map(int, vb)) for x in new_v)
            and all(int(x) > max(map(int, eb)) for x in new_e)
            and all(int(x) > max(map(int, fb)) for x in new_f))
    return (f"old vertices kept={old_v_kept}, +{len(new_v)} V / +{len(new_e)} E (net {len(ea) - len(eb):+d}) / "
            f"faces {len(fb)}->{len(fa)} ({len(fb - fa)} replaced), new ids above old maxima={mono}")


def _apply(cls, mesh, points, label):
    """Feed points to a D session via click(); commit; report. Returns (accepted, message)."""
    scene = _scene(mesh)
    before = _ids(mesh)
    sizes_before = _sizes(mesh)
    k = _begin(cls, scene)
    rejected_at = None
    for i, p in enumerate(points):
        if not k.click(p):
            rejected_at = i
            break
    if rejected_at is not None:
        k.cancel()
        k.deactivate()
        return f"{label}: click {rejected_at} ({points[rejected_at]['kind']}) REJECTED by accepts(); session cancelled"
    k.commit()
    msg = k.last_message
    k.deactivate()
    return (f"{label}: {msg} | {_check(mesh, label)} | sizes {sizes_before} -> {_sizes(mesh)} | "
            f"{_id_continuity(before, mesh)} | history={len(scene.history)}")


def _fmt_cross(wr):
    parts = []
    for c in wr.crossings:
        parts.append(f"v{int(c['vertex_id'])}" if c["kind"] == "vertex" else f"e{int(c['edge_id'])}@{c['t']:.4f}")
    return "[" + ", ".join(parts) + "]"


def _path(a, wr, b):
    return [a] + [dict(c) for c in wr.crossings] + [b]


# =======================================================================================

def p1_grid_straight():
    print("\n== P1  grid 4x4 — straight segment across 3 quads (edge -> edge), camera oblique ==")
    m, p, f = _grid()
    cam = _cam_for(m, yaw_deg=20, pitch_deg=35)
    a = _edge_pt(m, p[(1, 0)], p[(2, 0)], 0.3)          # left border, row 1
    b = _edge_pt(m, p[(1, 3)], p[(2, 3)], 0.6)          # vertical edge x=3, row 1
    wr = walk(cam, m, a, b)
    hits, hidden = plane_hits(cam, m, a, b, occlusion=True)
    same, dt = _same_hits(wr, hits)
    print(f"  WALK ok={wr.ok} crossings={_fmt_cross(wr)} faces={[int(x) for x in wr.faces]}")
    print(f"  PLANE visible hits={[(el[0] + str(int(el[1])), round(l, 4)) for _s, el, l in hits]} hidden={hidden}")
    print(f"  walk == plane: {same} (max |dt| = {dt:.2e})")
    print("  " + _apply(KnifeFaceCollected, m, _path(a, wr, b), "D as built"))
    m2, p2, _ = _grid()
    a2 = _edge_pt(m2, p2[(1, 0)], p2[(2, 0)], 0.3)
    b2 = _edge_pt(m2, p2[(1, 3)], p2[(2, 3)], 0.6)
    wr2 = walk(cam, m2, a2, b2)
    print("  " + _apply(_DNoA5Lock, m2, _path(a2, wr2, b2), "D without A5 lock"))


def mk2(cam, m, spec):
    kind, val = spec
    if kind == "F":
        return _face_pt_from_world(cam, m, val)[0]
    if kind == "E":
        return _edge_pt(m, *val)
    return {"kind": "vertex", "vertex_id": val}


def p2_grid_endpoint_kinds():
    print("\n== P2  grid — endpoint kinds (X4): face->face, face->edge, edge->face, vertex->edge, farther ==")
    cam_yaw, cam_pitch = 20, 35
    cases = [
        ("face->face (neighbour)", lambda m, p: ("F", (0.5, 1.5, 0.0)), lambda m, p: ("F", (1.5, 1.4, 0.0))),
        ("face->face (3 quads)", lambda m, p: ("F", (0.5, 1.5, 0.0)), lambda m, p: ("F", (2.5, 1.4, 0.0))),
        ("face->edge", lambda m, p: ("F", (0.5, 1.5, 0.0)), lambda m, p: ("E", (p[(1, 3)], p[(2, 3)], 0.5))),
        ("edge->face", lambda m, p: ("E", (p[(1, 0)], p[(2, 0)], 0.5)), lambda m, p: ("F", (2.5, 1.4, 0.0))),
        ("vertex->edge", lambda m, p: ("V", p[(1, 0)]), lambda m, p: ("E", (p[(1, 3)], p[(2, 3)], 0.5))),
        ("face->face, interior mid-click (F1->F3->F3->edge)", None, None),
    ]
    for label, fa, fb in cases:
        m, p, _f = _grid()
        cam = _cam_for(m, cam_yaw, cam_pitch)

        def mk(spec):
            kind, val = spec
            if kind == "F":
                return _face_pt_from_world(cam, m, val)[0]
            if kind == "E":
                return _edge_pt(m, *val)
            return {"kind": "vertex", "vertex_id": val}
        if fa is None:
            a = mk(("F", (0.5, 1.5, 0.0)))
            mid = mk(("F", (2.3, 1.3, 0.0)))
            mid2 = mk(("F", (2.6, 1.7, 0.0)))
            end = mk(("E", (p[(1, 3)], p[(2, 3)], 0.5)))
            w1 = walk(cam, m, a, mid)
            w2 = walk(cam, m, mid2, end)
            pts = _path(a, w1, mid)[:-1] + [mid, mid2] + [dict(c) for c in w2.crossings] + [end]
            print(f"  {label}: walk1 {_fmt_cross(w1)} walk2 {_fmt_cross(w2)}")
            print("    " + _apply(_DNoA5Lock, m, pts, "D without A5 lock"))
            continue
        a, b = mk(fa(m, p)), mk(fb(m, p))
        wr = walk(cam, m, a, b)
        print(f"  {label}: WALK ok={wr.ok} {_fmt_cross(wr)}")
        m0, p0, _ = _grid()
        a0, b0 = (mk2(cam, m0, fa(m0, p0)), mk2(cam, m0, fb(m0, p0)))
        print("    " + _apply(KnifeFaceCollected, m0, _path(a0, walk(cam, m0, a0, b0), b0), "D as built").split(" | sizes")[0])
        print("    " + _apply(_DNoA5Lock, m, _path(a, wr, b), "D without A5 lock"))


def p3_grid_through_vertex():
    print("\n== P3  grid — diagonal exactly through a vertex, and 'almost' through it (tolerance) ==")
    # the grid lies in z=0, world up is +y: (0, 0) = front view, (0, 80) = grazing view
    for yaw, pitch in ((0, 0), (20, 35), (0, 80)):
        for delta in (0.0, 0.002, 0.02):
            m, p, _f = _grid()
            cam = _cam_for(m, yaw, pitch)
            # (0.5+delta, 0) on the bottom border -> (1.5+delta, 2) on edge y=2: passes (1+delta, 1)
            a = _edge_pt(m, p[(0, 0)], p[(0, 1)], 0.5 + delta)
            b = _edge_pt(m, p[(2, 1)], p[(2, 2)], 0.5 + delta)
            v11 = _proj2(cam, (1.0, 1.0, 0.0))
            v_near = _proj2(cam, (1.0 + delta, 1.0, 0.0))
            px = _len(_sub(v11, v_near))
            for tol in (0.0, 0.5, 5.0):
                wr = walk(cam, m, a, b, vertex_tol_px=tol)
                short = min((min(c["t"], 1 - c["t"]) for c in wr.crossings if c["kind"] == "edge"), default=None)
                m2, p2, _ = _grid()
                a2 = _edge_pt(m2, p2[(0, 0)], p2[(0, 1)], 0.5 + delta)
                b2 = _edge_pt(m2, p2[(2, 1)], p2[(2, 2)], 0.5 + delta)
                wr2 = walk(cam, m2, a2, b2, vertex_tol_px=tol)
                applied = _apply(_DNoA5Lock, m2, _path(a2, wr2, b2), "D") if wr2.ok else "not applied"
                print(f"  cam yaw={yaw} pitch={pitch}  offset={delta} ({px:.2f}px from v(1,1))  "
                      f"vertex_tol={tol}px: ok={wr.ok} {_fmt_cross(wr)} shortest edge-t={short if short is None else round(short, 4)}"
                      f"{'' if wr.ok else ' reason=' + wr.reason}")
                print(f"      -> {applied.split(' | sizes')[0]} | sizes -> {_sizes(m2)}")
    m, p, _f = _grid()
    cam = _cam_for(m, 20, 35)
    a = {"kind": "vertex", "vertex_id": p[(1, 0)]}
    b = {"kind": "vertex", "vertex_id": p[(1, 3)]}
    wr = walk(cam, m, a, b)
    print(f"  collinear with grid edges v(0,1)->v(3,1): ok={wr.ok} {_fmt_cross(wr)} reason={wr.reason!r}")
    print("    " + _apply(_DNoA5Lock, m, _path(a, wr, b), "D without A5 lock").split(" | sizes")[0])


def p4_grid_border_and_hole():
    print("\n== P4  grid — mesh border / hole (empty space) ==")
    m, p, f = _grid(hole=(1, 1))
    cam = _cam_for(m, 20, 35)
    a = _edge_pt(m, p[(1, 0)], p[(2, 0)], 0.5)
    b = _edge_pt(m, p[(1, 3)], p[(2, 3)], 0.5)
    wr = walk(cam, m, a, b)
    hits, hidden = plane_hits(cam, m, a, b, occlusion=True)
    print(f"  across a hole (quad (1,1) missing): WALK ok={wr.ok} reason={wr.reason!r} partial={_fmt_cross(wr)}")
    print(f"  PLANE hits={[(int(el[1]), round(l, 4), 'faces', sorted(int(x) for x in m.edge_faces(el[1]))) for _s, el, l in hits]}")
    pts = [a] + _hit_points(hits) + [b]
    print("  plane hits fed to D: " + _apply(_DNoA5Lock, m, pts, "D without A5 lock").split(" | sizes")[0])
    m, p, f = _grid()
    cam = _cam_for(m, 20, 35)
    a, _s = _face_pt_from_world(cam, m, (3.5, 1.5, 0.0))
    out_world = (5.5, 1.5, 0.0)
    s_out = cam.project_to_screen(out_world, W, H)
    tgt = knife_face_pick(cam, m, s_out[0], s_out[1], W, H, occlusion=True)
    print(f"  face -> cursor beyond the border: knife_face_pick kind={tgt['kind']!r} "
          f"(D: 'outside' = commit, never a segment target)")


def p5_concave_reentry():
    print("\n== P5  concave L-face — segment leaves the face and re-enters it ==")
    m, v, f_l, f_sq = _l_mesh()
    cam = _cam_for(m, 0, 0)
    a = _edge_pt(m, v[(2, 0)], v[(2, 1)], 0.2)          # (2, 0.2)
    b = _edge_pt(m, v[(1, 2)], v[(0, 2)], 0.8)          # (0.2, 2)
    wr = walk(cam, m, a, b)
    print(f"  WALK ok={wr.ok} {_fmt_cross(wr)} faces={[('L' if x == f_l else 'SQ') for x in wr.faces]}")
    print("  " + _apply(_DNoA5Lock, m, _path(a, wr, b), "D without A5 lock"))
    m, v, f_l, f_sq = _l_mesh()
    a = _edge_pt(m, v[(2, 0)], v[(2, 1)], 0.2)
    b = _edge_pt(m, v[(1, 2)], v[(0, 2)], 0.8)
    scene = _scene(m)
    k = _begin(_DNoA5Lock, scene)
    k.click(a)
    ok = k.click(b)
    k.cancel()
    k.deactivate()
    print(f"  without crossings (a -> b directly, both on L): accepts()={ok} — the straight chord would run "
          f"through the notch square (outside L); D's resolver does no geometric in-face check")


def _head_candidates(cam, m, n=400, seed=7):
    import random
    rnd = random.Random(seed)
    pts = []
    xs = [cam.project_to_screen(m.vertex_position(v), W, H) for v in m.all_vertex_ids()]
    xs = [x for x in xs if x is not None]
    minx, maxx = min(x[0] for x in xs), max(x[0] for x in xs)
    miny, maxy = min(x[1] for x in xs), max(x[1] for x in xs)
    tries = 0
    while len(pts) < n and tries < n * 20:
        tries += 1
        sx, sy = rnd.uniform(minx, maxx), rnd.uniform(miny, maxy)
        t = knife_face_pick(cam, m, sx, sy, W, H, occlusion=True)
        if t["kind"] == "face" and t["distance_px"] >= 9.0:
            pts.append(((sx, sy), t))
    return pts


def p6_head_statistics():
    print("\n== P6  head (324 non-planar quads) — WALK vs PLANE on random visible face->face segments ==")
    m = _head()
    cam = _cam_for(m, 225, 25)           # PlaygroundCamera start view (yaw 225, pitch 25, margin 1.4)
    cands = _head_candidates(cam, m, n=160)
    import random
    rnd = random.Random(11)
    stats = collections.Counter()
    t_walk = t_plane = 0.0
    n = 0
    dts = []
    example = None
    for _ in range(3000):
        if n >= 150:
            break
        (s1, a), (s2, b) = rnd.sample(cands, 2)
        d = math.dist(s1, s2)
        if not (40 <= d <= 220) or a["face_id"] == b["face_id"]:
            continue
        n += 1
        t0 = time.perf_counter()
        wr = walk(cam, m, a, b)
        t1 = time.perf_counter()
        hits_vis, hidden = plane_hits(cam, m, a, b, occlusion=True)
        t2 = time.perf_counter()
        t_walk += t1 - t0
        t_plane += t2 - t1
        if hidden:
            stats["  (all) plane found hidden hits (other side of the head)"] += 1
        chain_ok = all(_faces_of(m, x) & _faces_of(m, y)
                       for x, y in zip([a] + _hit_points(hits_vis), _hit_points(hits_vis) + [b]))
        if not chain_ok:
            stats["  (all) plane(visible) hits do NOT form a face-connected chain (jumps a gap)"] += 1
        if not wr.ok:
            back = sum(1 for f in wr.faces if not _front_facing(cam, m, f))
            stats["walk failed: " + wr.reason + (" — after entering a back-facing face" if back else "")] += 1
            continue
        occ = _occluded_crossings(cam, m, wr.crossings)
        back = sum(1 for f in wr.faces if not _front_facing(cam, m, f))
        same, dt = _same_hits(wr, hits_vis)
        if not same:
            vhits = {c["vertex_id"] for c in wr.crossings if c["kind"] == "vertex"}
            reduced = [c for c in wr.crossings
                       if c["kind"] == "vertex" or not (set(m.edge_vertices(c["edge_id"])) & vhits)]
            rw = WalkResult()
            rw.crossings = reduced
            same_red, _ = _same_hits(rw, hits_vis)
        if same:
            stats["walk ok, == plane(visible)"] += 1
            dts.append(dt)
            if example is None and len(wr.crossings) >= 3 and all(c["kind"] == "edge" for c in wr.crossings):
                example = (a, b, wr)
        elif same_red:
            stats["walk ok, == plane(visible) except one extra edge hit next to a vertex hit"] += 1
        elif occ:
            stats["walk ok, walk crosses occluded edges (plane(visible) differs)"] += 1
        else:
            stats["walk ok, plane(visible) has extra/other hits"] += 1
        if back:
            stats["  (of ok) walk entered a back-facing face"] += 1
        if occ:
            stats["  (of ok) walk has a crossing hidden by the B8 occlusion test"] += 1
        stats["  (of ok) walks checked for hidden crossings (B8 test)"] += 1
        if any(c["kind"] == "vertex" for c in wr.crossings):
            stats["  (of ok) walk snapped to a vertex (0.5px)"] += 1
    print(f"  segments: {n} (screen length 40-220 px, both ends visible face points >= 9px from edges)")
    for k, c in sorted(stats.items(), key=lambda kv: kv[0].startswith("  ")):
        print(f"    {c:4d}  {k}")
    print(f"  identical crossings: max |dt| walk vs plane = {max(dts) if dts else float('nan'):.2e}")
    print(f"  cost per segment (pure Python, no cache): WALK {1000 * t_walk / n:.2f} ms, "
          f"PLANE+occlusion {1000 * t_plane / n:.2f} ms")
    return m, cam, example


def p7_head_apply(m, cam, example):
    print("\n== P7  head — one planned segment applied through D (non-planar quads) ==")
    a, b, wr = example
    print(f"  segment face {int(a['face_id'])} -> face {int(b['face_id'])}: crossings {_fmt_cross(wr)}")
    import copy as _copy
    m1 = _copy.deepcopy(m)
    print("  " + _apply(KnifeFaceCollected, m1, _path(a, wr, b), "D as built (A5 lock on)"))
    m2 = _copy.deepcopy(m)
    print("  " + _apply(_DNoA5Lock, m2, _path(a, wr, b), "D without A5 lock (face->face)"))
    m3 = _copy.deepcopy(m)
    pts = [dict(c) for c in wr.crossings]
    print("  " + _apply(_DNoA5Lock, m3, pts, "D without A5 lock (first..last crossing, edge->edge)"))


def _loop_points(cam, m, worlds):
    return [_face_pt_from_world(cam, m, w)[0] for w in worlds]


def _loop_path(cam, m, pts):
    """[P0, x01, P1, x12, ..., Pk] plus the closing crossings Pk -> P0 separately."""
    path = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        wr = walk(cam, m, a, b)
        assert wr.ok, wr.reason
        path += [dict(c) for c in wr.crossings] + [b]
    closing = walk(cam, m, pts[-1], pts[0])
    assert closing.ok, closing.reason
    return path, [dict(c) for c in closing.crossings]


def p8_closed_loops():
    print("\n== P8  closed loops across faces (X5) ==")
    loops = {
        "loop4 around vertex (2,2), 4 quads": [(1.5, 1.5, 0.0), (2.5, 1.5, 0.0), (2.5, 2.5, 0.0), (1.5, 2.5, 0.0)],
        "loop2 straddling edge x=2, 2 quads": [(1.6, 1.3, 0.0), (2.4, 1.5, 0.0), (1.6, 1.7, 0.0)],
    }
    for label, worlds in loops.items():
        print(f"  -- {label}")
        # (a) D as built: close-on-start click commits without adding the closing segment
        m, p, f = _grid()
        cam = _cam_for(m, 20, 35)
        pts = _loop_points(cam, m, worlds)
        path, closing = _loop_path(cam, m, pts)
        print("    (a) close-on-start (window commits, closing segment never added): "
              + _apply(_DNoA5Lock, m, path, "D").split(" | ")[0])
        # (b) closing by a *new* click at the start position (a second, separate point)
        m, p, f = _grid()
        cam = _cam_for(m, 20, 35)
        pts = _loop_points(cam, m, worlds)
        path, closing = _loop_path(cam, m, pts)
        again = _face_pt_from_world(cam, m, worlds[0])[0]
        print("    (b) closing segment + new click on the start position: "
              + _apply(_DNoA5Lock, m, path + closing + [again], "D").split(" | ")[0])
        # (c) PROBE-LOCAL cyclic resolution: rotate so the path starts and ends on the SAME crossing
        m, p, f = _grid()
        cam = _cam_for(m, 20, 35)
        pts = _loop_points(cam, m, worlds)
        path, closing = _loop_path(cam, m, pts)
        full = path + closing                   # P0 x.. P1 .. Pk x.. (back towards P0)
        first_b = next(i for i, q in enumerate(full) if q["kind"] != "face")
        rotated = full[first_b:] + full[:first_b] + [full[first_b]]   # same dict object closes the loop
        scene = _scene(m)
        before, sb = _ids(m), _sizes(m)
        k = _begin(_DNoA5Lock, scene)
        k._path = rotated                       # PROBE-LOCAL deviation (b), see module docstring
        k.commit()
        cut_edges = [e for e in k.path_edges if m.is_valid_edge(e)]
        touching_old = [e for e in cut_edges if set(m.edge_vertices(e)) & before[0]]
        print(f"    (c) cyclic (rotated to start/end on one crossing): {k.last_message} | {_check(m, label)} | "
              f"sizes {sb} -> {_sizes(m)} | {_id_continuity(before, m)}")
        print(f"        cut edges={len(cut_edges)}, of which reach an original vertex (= a bridge): {len(touching_old)}")
        k.deactivate()


def p9_orbit_between_clicks():
    print("\n== P9  camera dependency (X3): same A, B — crossings under different cameras ==")
    # grid (planar)
    m, p, f = _grid()
    cam1 = _cam_for(m, 20, 35)
    a = _face_pt_from_world(cam1, m, (0.4, 1.3, 0.0))[0]
    b = _face_pt_from_world(cam1, m, (3.4, 2.6, 0.0))[0]
    base = walk(cam1, m, a, b)
    for yaw, pitch in ((50, 20), (-30, 60)):
        c2 = _cam_for(m, yaw, pitch)
        w2 = walk(c2, m, a, b)
        same = [c.get("edge_id", c.get("vertex_id")) for c in base.crossings] == \
            [c.get("edge_id", c.get("vertex_id")) for c in w2.crossings]
        dt = max((abs(x["t"] - y["t"]) for x, y in zip(base.crossings, w2.crossings)
                  if x["kind"] == y["kind"] == "edge"), default=0.0)
        print(f"  grid: cam(20,35) {_fmt_cross(base)} vs cam({yaw},{pitch}) {_fmt_cross(w2)} same elements={same}"
              + (f" max|dt|={dt:.2e}" if same else ""))
        w0a, w0b = walk(cam1, m, a, b, vertex_tol_px=0.0), walk(c2, m, a, b, vertex_tol_px=0.0)
        dt0 = max(abs(x["t"] - y["t"]) for x, y in zip(w0a.crossings, w0b.crossings))
        print(f"        same with vertex_tol=0: {[c['edge_id'] for c in w0a.crossings] == [c['edge_id'] for c in w0b.crossings]}"
              f" max|dt|={dt0:.2e}")
    # head (non-planar)
    hm = _head()
    c1 = _cam_for(hm, 225, 25)
    cands = _head_candidates(c1, hm, n=160, seed=3)
    import random
    rnd = random.Random(5)
    shown = 0
    summary = collections.Counter()
    for _ in range(4000):
        (s1, a), (s2, b) = rnd.sample(cands, 2)
        if not (60 <= math.dist(s1, s2) <= 200):
            continue
        w1 = walk(c1, hm, a, b)
        if not w1.ok or len(w1.crossings) < 3 or _occluded_crossings(c1, hm, w1.crossings):
            continue
        for dyaw, dpitch in ((10, 0), (25, -10), (45, 10)):
            c2 = _cam_for(hm, 225 + dyaw, 25 + dpitch)
            w2 = walk(c2, hm, a, b)
            e1 = [c.get("edge_id", c.get("vertex_id")) for c in w1.crossings]
            e2 = [c.get("edge_id", c.get("vertex_id")) for c in w2.crossings] if w2.ok else None
            if e2 is None:
                key = f"orbit {dyaw}/{dpitch}: walk fails under new camera ({w2.reason})"
            elif e1 == e2:
                dt = max((abs(x["t"] - y["t"]) for x, y in zip(w1.crossings, w2.crossings)
                          if x["kind"] == y["kind"] == "edge"), default=0.0)
                key = f"orbit {dyaw}/{dpitch}: same edges, t moved (max|dt| {'>=0.05' if dt >= 0.05 else '<0.05'})"
            else:
                key = f"orbit {dyaw}/{dpitch}: different edge sequence"
            summary[key] += 1
            if shown < 2 and e2 is not None:
                pos1 = [_pos(hm, c) for c in w1.crossings]
                print(f"  head example {shown + 1}, orbit yaw+{dyaw} pitch{dpitch:+d}:")
                print(f"    click-time cam: {_fmt_cross(w1)}")
                print(f"    other cam     : {_fmt_cross(w2)}  occluded crossings now: "
                      f"{_occluded_crossings(c2, hm, w1.crossings)}/{len(w1.crossings)}")
                if e1 == e2:
                    pos2 = [_pos(hm, c) for c in w2.crossings]
                    print(f"    max 3D shift of a crossing: {max(math.dist(x, y) for x, y in zip(pos1, pos2)):.4f} "
                          f"(head radius 3.37)")
        shown += 1
        if sum(summary.values()) >= 90:
            break
    print("  head summary (30 segments x 3 orbits, crossings recomputed from the same A, B):")
    for k, c in sorted(summary.items()):
        print(f"    {c:3d}  {k}")
    print("  D's resolver takes no camera: stored (edge_id, t) crossings resolve identically at commit "
          "whatever the view (see P1/P7: commit runs with no camera argument).")


def main():
    print("Knife Q5 cross-face probe — public Core API + read-only helpers; D resolver driven via click()/commit()")
    p1_grid_straight()
    p2_grid_endpoint_kinds()
    p3_grid_through_vertex()
    p4_grid_border_and_hole()
    p5_concave_reentry()
    m, cam, example = p6_head_statistics()
    p7_head_apply(m, cam, example)
    p8_closed_loops()
    p9_orbit_between_clicks()


if __name__ == "__main__":
    main()
