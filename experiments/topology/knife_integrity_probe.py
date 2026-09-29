"""PROBE — Knife Face Q5: faces that "sit under a cut" (geometric integrity after commit).

Evidence for `playground/experiments/knife_face/decision.md`, "Q5 integrity findings (2026-09-29)".
Not a tool, not wired anywhere, no Core change. Drives the Knife Face Lab engines (Q5
`KnifeFaceCrossFace`, D `KnifeFaceCollected`, B `KnifeFaceImmediate`) through their public
interface only, the way `playground/window.py` does: a screen position -> `knife_face_pick`
(occlusion on) -> Q5 only: `set_view` + `snap_target` -> `click`; `commit()` at the end.

Geometric integrity (what `assert_mesh_invariants` does not see), per face, in the face's own
best-fit plane (dominant Newell axis, the same projection `viewport.derived.triangulate_face` uses):
  zero_area   |Newell| / 2 below 1e-9 x the mesh's squared size
  non_simple  two boundary edges intersect or touch (not at their shared corner), or the boundary
              folds back on itself (spike) — a bow-tie / self-overlapping face
  tri_area    sum of |triangle areas| of `triangulate_mesh_face` != polygon area (the render sees
              overlapping triangles — the Artist's "hatching")
and per mesh:
  winding     an edge traversed the same way by both of its faces (a flipped face next to a correct one)
  dangling    an edge with no face (a line ending in the middle of a face)
  coverage    planar reference surfaces only: every face lies in one reference plane, its normal points
              the plane's way, and the faces of each plane add up to the plane's area (no overlap, no gap)
              — `grid`: the z = 0 plane (16 unit quads); `cube`: the six sides (area 4 each)

Failing sessions are attributed to *path features* read before commit (see "path features" below).

Run:  python experiments/topology/knife_integrity_probe.py              # fuzz 400 grid + 400 cube (Q5)
      python experiments/topology/knife_integrity_probe.py --edge-only  # the same without face-interior clicks
      python experiments/topology/knife_integrity_probe.py --minimise   # + shrink failing sessions
      python experiments/topology/knife_integrity_probe.py --cases      # targeted hypothesis cases H-a..H-d
      python experiments/topology/knife_integrity_probe.py --variants   # the same seeds under D and B
      python experiments/topology/knife_integrity_probe.py --dropped    # dropped runs with / without crossings
      python experiments/topology/knife_integrity_probe.py --production # plain-chord cases on the Production Knife
"""

from __future__ import annotations

import argparse
import collections
import math
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests"),
           str(_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import Mesh, Scene  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402
from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import create_cube  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport.derived import triangulate_mesh_face  # noqa: E402

from playground.experiments.knife_face.engine import (  # noqa: E402
    KnifeFaceCollected,
    KnifeFaceImmediate,
    knife_face_pick,
)
from playground.experiments.knife_face.engine_q5 import KnifeFaceCrossFace  # noqa: E402

W, H = 1280, 800


# -- scenes ------------------------------------------------------------------------------

def build_grid(n: int = 4) -> Mesh:
    """n x n unit quads in z = 0 (same as `playground/tests/test_knife_face_q5.py::_grid`)."""
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


SCENES = {"grid": build_grid, "cube": create_cube}

# (axis, value, outward sign) of each reference plane and the area it must be covered by.
REFERENCE_PLANES = {
    "grid": ([(2, 0.0, 1.0)], 16.0),
    "cube": ([(a, s, s) for a in range(3) for s in (-1.0, 1.0)], 4.0),
}


def camera_for(mesh, yaw: float, pitch: float, dolly: float = 1.0) -> OrbitCamera:
    cam = OrbitCamera(yaw=math.radians(yaw), pitch=math.radians(pitch))
    center, radius = mesh_center_and_radius(mesh)
    cam.frame_on_bounds(center, radius, margin=1.4)
    if dolly != 1.0:
        cam.dolly(dolly)
    return cam


# -- geometry ----------------------------------------------------------------------------

def _newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return n


def _project(pts):
    """2D projection along the dominant Newell axis, mirrored so the boundary runs CCW
    (positive area) — same convention as `viewport.derived._polygon_plane_axes`."""
    n = _newell(pts)
    ax = max(range(3), key=lambda k: abs(n[k]))
    u, w = {0: (1, 2), 1: (2, 0), 2: (0, 1)}[ax]
    sign = 1.0 if n[ax] >= 0 else -1.0
    return [(sign * p[u], p[w]) for p in pts], n


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p, eps):
    return (min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
            and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps)


def _proper_cross(a, b, c, d, eps=1e-12) -> bool:
    """Open segments ab and cd cross at one point strictly inside both (no end on the other line)."""
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    return ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and \
           ((o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps))


def _segments_meet(a, b, c, d, eps) -> bool:
    """Closed segments ab and cd intersect or touch (collinear overlap included)."""
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    if ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and \
       ((o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)):
        return True
    return ((abs(o1) <= eps and _on_segment(a, b, c, eps)) or (abs(o2) <= eps and _on_segment(a, b, d, eps))
            or (abs(o3) <= eps and _on_segment(c, d, a, eps)) or (abs(o4) <= eps and _on_segment(c, d, b, eps)))


def polygon_is_simple(pts2, eps=1e-9) -> bool:
    n = len(pts2)
    for i in range(n):
        a, b, c = pts2[i - 1], pts2[i], pts2[(i + 1) % n]
        # Spike: the boundary turns back on itself at b (collinear, pointing backwards).
        if abs(_orient(a, b, c)) <= eps and ((a[0] - b[0]) * (c[0] - b[0]) + (a[1] - b[1]) * (c[1] - b[1])) > 0:
            return False
    for i in range(n):
        a, b = pts2[i], pts2[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or j == (i + 1) % n:
                continue  # adjacent edges share a corner
            c, d = pts2[j], pts2[(j + 1) % n]
            if _segments_meet(a, b, c, d, eps):
                return False
    return True


def _tri_area(p, q, r):
    u = (q[0] - p[0], q[1] - p[1], q[2] - p[2])
    v = (r[0] - p[0], r[1] - p[1], r[2] - p[2])
    c = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return 0.5 * math.sqrt(c[0] ** 2 + c[1] ** 2 + c[2] ** 2)


def face_issues(mesh, fid, *, area_eps=1e-9) -> list[str]:
    boundary = mesh.face_vertices(fid)
    pts = [mesh.vertex_position(v) for v in boundary]
    pts2, n = _project(pts)
    area = 0.5 * math.sqrt(sum(c * c for c in n))
    out = []
    if area < area_eps:
        out.append("zero_area")
    if not polygon_is_simple(pts2):
        out.append("non_simple")
    tri = sum(_tri_area(*(mesh.vertex_position(v) for v in t)) for t in triangulate_mesh_face(mesh, fid))
    if abs(tri - area) > 1e-6 * max(1.0, area):
        out.append("tri_area")
    return out


def _plane_of(pts, planes, eps=1e-6):
    for k, (axis, value, _sign) in enumerate(planes):
        if all(abs(p[axis] - value) <= eps for p in pts):
            return k
    return None


def integrity(mesh, scene: str) -> dict[str, list]:
    """{defect class: [details]} — empty dict = geometrically sound."""
    issues: dict[str, list] = collections.defaultdict(list)
    for fid in mesh.all_face_ids():
        for kind in face_issues(mesh, fid):
            issues[kind].append(fid)
    directed = collections.Counter()
    for fid in mesh.all_face_ids():
        b = mesh.face_vertices(fid)
        for i in range(len(b)):
            directed[(b[i], b[(i + 1) % len(b)])] += 1
    for (a, b), cnt in directed.items():
        if cnt > 1:  # both faces of the edge walk it the same way: one of them is flipped
            issues["winding"].append((a, b))
    for eid in mesh.all_edge_ids():
        if not mesh.edge_faces(eid):
            issues["dangling"].append(eid)
    if scene in REFERENCE_PLANES:
        planes, expected = REFERENCE_PLANES[scene]
        sums = [0.0] * len(planes)
        for fid in mesh.all_face_ids():
            pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
            k = _plane_of(pts, planes)
            if k is None:
                issues["coverage"].append(("off-plane face", fid))
                continue
            axis, _value, sign = planes[k]
            signed = 0.5 * _newell(pts)[axis] * sign
            if signed < -1e-12:
                issues["flipped"].append(fid)
            sums[k] += signed
        for k, s in enumerate(sums):
            if abs(s - expected) > 1e-6:
                issues["coverage"].append((planes[k], round(s, 6)))
    try:
        assert_mesh_invariants(mesh)
    except AssertionError as exc:
        issues["invariants"].append(str(exc))
    return dict(issues)


# -- path features (hypotheses, read from the virtual path before commit) --------------------
#
# D and Q5 do not touch the mesh before commit, so the session-start mesh is the mesh every click
# saw. A feature is a *pre-commit* property of the clicked path; the probe counts which features the
# failing sessions carry (and how often each occurs in sessions that stay clean).
#
#   cross   two segments of the session (not neighbours on the path) intersect inside one face (H-b)
#   stale   a run with interior points whose face is also cut by another segment of the session, and
#           whose two ends share a second face besides it (both ends on one edge / one fold) (H-a)
#   along   a straight segment that lies on the boundary of its shared face (both ends on one straight
#           boundary line, not adjacent because a vertex sits between them)
#   tzero   a planner crossing on an edge at t within 1e-9 of an end (a vertex hit reported as an edge hit)
#   leave   a straight segment between two points of a shared face that is not inside that face (the
#           face is concave — usually from an earlier session's cut)
#   multi   a straight segment that two shared faces could both take, only one of which contains it
#           (`connect_in_shared_face` takes the lowest face id, not the face the segment lies in)
#   fold    a run whose interior points lie in more than one face (H-c)

def _face_frame(mesh, fid):
    pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
    n = _newell(pts)
    ax = max(range(3), key=lambda k: abs(n[k]))
    u, w = {0: (1, 2), 1: (2, 0), 2: (0, 1)}[ax]
    sign = 1.0 if n[ax] >= 0 else -1.0
    return (lambda p: (sign * p[u], p[w])), [(sign * p[u], p[w]) for p in pts]


def _point_in_polygon(pt, poly, eps=1e-9) -> int:
    """1 inside, 0 on the boundary, -1 outside."""
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if abs(_orient(a, b, pt)) <= eps and _on_segment(a, b, pt, eps):
            return 0
    inside = False
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > pt[1]) != (y2 > pt[1]) and x1 + (pt[1] - y1) * (x2 - x1) / (y2 - y1) > pt[0]:
            inside = not inside
    return 1 if inside else -1


def _chord_inside(fr, pp, qp, mid) -> bool:
    """The straight segment pp-qp lies inside the face: its midpoint is inside and it crosses no
    boundary edge in between (touching the boundary only at its own two ends)."""
    pr, poly = fr
    if _point_in_polygon(pr(mid), poly) != 1:
        return False
    a, b = pr(pp), pr(qp)
    n = len(poly)
    for i in range(n):
        c, d = poly[i], poly[(i + 1) % n]
        if _proper_cross(a, b, c, d):
            return False
        for v in (c,):  # a boundary vertex strictly inside the segment
            if abs(_orient(a, b, v)) <= 1e-12 and _on_segment(a, b, v, 1e-12) and v not in (a, b) \
                    and min(math.dist(v, a), math.dist(v, b)) > 1e-9:
                return False
    return True


def _connectable_faces(mesh, p, q, fs) -> int:
    """How many shared faces hold both points as non-adjacent corners (vertex points only — an edge
    point becomes a vertex on both faces of its edge at commit)."""
    def corners(pt, f):
        if pt["kind"] == "vertex":
            return {pt["vertex_id"]}
        return set(mesh.edge_vertices(pt["edge_id"]))  # the new vertex will sit between these two

    n = 0
    for f in fs:
        b = mesh.face_vertices(f)
        cp, cq = corners(p, f), corners(q, f)
        if p["kind"] == q["kind"] == "vertex":
            i, j = b.index(p["vertex_id"]), b.index(q["vertex_id"])
            n += (i - j) % len(b) not in (1, len(b) - 1)
        else:
            n += not (cp & cq and (p["kind"] == "vertex" or q["kind"] == "vertex"))
    return n


def _segments(path):
    """[(p, q)] consecutive points of every chain (Q5: chains end at a 'closed' break, gaps break a
    chain's segments; a cyclic close adds last -> first)."""
    out, prev, first = [], None, None
    for p in path:
        if p["kind"] == "break":
            if p.get("reason") == "closed":
                if p.get("cyclic") and prev is not None and first is not None and prev is not first:
                    out.append((prev, first))
                first = None
            prev = None
            continue
        if prev is not None and prev is not p:
            out.append((prev, p))
        if first is None:
            first = p
        prev = p
    return out


def path_features(mesh, path) -> dict:
    from playground.experiments.knife_face.planner import point_faces, point_position

    segs = []
    for p, q in _segments(path):
        faces = point_faces(mesh, p) & point_faces(mesh, q)
        segs.append((p, q, faces, point_position(mesh, p), point_position(mesh, q)))
    feats = collections.Counter()
    frames = {}

    def frame(f):
        if f not in frames:
            frames[f] = _face_frame(mesh, f)
        return frames[f]

    for i, (p, q, fs, pp, qp) in enumerate(segs):
        interior = p["kind"] == "face" or q["kind"] == "face"
        if not fs:
            continue
        mid = tuple(0.5 * (pp[k] + qp[k]) for k in range(3))
        if interior:
            f = p["face_id"] if p["kind"] == "face" else q["face_id"]
            if not _chord_inside(frame(f), pp, qp, mid):
                feats["leave"] += 1
        else:
            if any(_point_in_polygon(frame(f)[0](mid), frame(f)[1]) == 0 for f in fs):
                feats["along"] += 1
            else:
                inside = [f for f in fs if _chord_inside(frame(f), pp, qp, mid)]
                if not inside:
                    feats["leave"] += 1
                elif len(inside) < len(fs) and _connectable_faces(mesh, p, q, fs) > 1:
                    feats["multi"] += 1
        for j in range(i + 1, len(segs)):
            p2, q2, fs2, pp2, qp2 = segs[j]
            if {id(p), id(q)} & {id(p2), id(q2)}:
                continue
            for f in fs & fs2:
                pr = frame(f)[0]
                if _proper_cross(pr(pp), pr(qp), pr(pp2), pr(qp2)):
                    feats["cross"] += 1
                    break
    for p in path:
        if p.get("crossing") and p["kind"] == "edge" and (p["t"] < 1e-9 or p["t"] > 1.0 - 1e-9):
            feats["tzero"] += 1
    # runs: boundary, interior+, boundary inside one chain stretch
    stretch: list = []
    for p in path + [{"kind": "break"}]:
        if p["kind"] != "break":
            stretch.append(p)
            continue
        cur: list = []
        for s in stretch:
            cur.append(s)
            if s["kind"] in ("vertex", "edge"):
                if len(cur) > 2 and cur[0]["kind"] != "face":
                    inner = cur[1:-1]
                    fids = {x["face_id"] for x in inner}
                    if len(fids) > 1:
                        feats["fold"] += 1
                    fid = inner[0]["face_id"]
                    others = (point_faces(mesh, cur[0]) & point_faces(mesh, cur[-1])) - {fid}
                    cut_same = sum(1 for (sp, sq, sfs, _a, _b) in segs
                                   if fid in sfs and not ({id(sp), id(sq)} <= {id(x) for x in cur}))
                    if others and cut_same:
                        feats["stale"] += 1
                cur = [s]
        stretch = []
    return dict(feats)


# -- sessions ----------------------------------------------------------------------------

def _random_click(rnd, mesh, cam, p_face, p_vertex):
    """A screen position aimed at a random face interior / edge point / vertex of the current mesh.
    Where it lands is decided by the real pick afterwards (occlusion, pick radii)."""
    r = rnd.random()
    if r < p_face:
        fid = rnd.choice(mesh.all_face_ids())
        tris = triangulate_mesh_face(mesh, fid)
        tri = rnd.choice(tris)
        u, v = rnd.random(), rnd.random()
        if u + v > 1.0:
            u, v = 1.0 - u, 1.0 - v
        a, b, c = (mesh.vertex_position(x) for x in tri)
        world = tuple(a[k] + u * (b[k] - a[k]) + v * (c[k] - a[k]) for k in range(3))
    elif r < p_face + p_vertex:
        world = mesh.vertex_position(rnd.choice(mesh.all_vertex_ids()))
    else:
        eid = rnd.choice(mesh.all_edge_ids())
        va, vb = mesh.edge_vertices(eid)
        t = rnd.uniform(0.1, 0.9)
        pa, pb = mesh.vertex_position(va), mesh.vertex_position(vb)
        world = tuple(pa[k] + t * (pb[k] - pa[k]) for k in range(3))
    s = cam.project_to_screen(world, W, H)
    if s is None:
        return None
    jitter = 2.0 if r >= p_face else 0.0
    return (s[0] + rnd.uniform(-jitter, jitter), s[1] + rnd.uniform(-jitter, jitter))


def new_session(cls, mesh):
    scene = Scene()
    scene.mesh = mesh
    knife = cls()
    knife.activate()
    knife.begin(mesh=mesh, scene=scene, selection=scene.selection)
    return knife, scene


def play(cls, mesh, clicks, cams, *, feats: dict | None = None, no_face=False) -> tuple[object, int, str]:
    """One session: `clicks` = [(cam_index, sx, sy)]. Returns (knife, accepted clicks, commit message).
    `feats` (optional) receives the path features of the session, read before commit. `no_face`: a click
    the pick resolves to a face interior is skipped (edge-only sessions)."""
    knife, _scene = new_session(cls, mesh)
    accepted = 0
    for ci, sx, sy in clicks:
        cam = cams[ci]
        target = knife_face_pick(cam, mesh, sx, sy, W, H, occlusion=True)
        if no_face and target.get("kind") == "face":
            continue
        if hasattr(knife, "set_view"):
            knife.set_view(cam, W, H, occlusion=True)
            target = knife.snap_target(target, sx, sy)
        if knife.click(target):
            accepted += 1
    if feats is not None and hasattr(knife, "path"):
        feats.update(path_features(mesh, knife.path))
    knife.commit()
    msg = knife.last_message
    knife.deactivate()
    return knife, accepted, msg


CAMS = {
    "grid": [(20.0, 35.0), (0.0, 89.0), (-30.0, 60.0), (45.0, 25.0)],
    "cube": [(35.0, 30.0), (-40.0, 25.0), (130.0, -30.0), (60.0, 55.0)],
}


def random_run(scene: str, seed: int, *, sessions=(1, 3), clicks=(2, 9), p_face=0.45, p_vertex=0.15,
               cls=KnifeFaceCrossFace):
    """A fresh mesh, 1-3 committed sessions with random clicks, checked after every commit.
    Returns (record, failing session index or None, its issues, features per session);
    record = [(clicks, state before the session, commit message)]."""
    rnd = random.Random(seed)
    mesh = SCENES[scene]()
    cams = [camera_for(mesh, y, p) for y, p in CAMS[scene]]
    record, feats = [], []
    for si in range(rnd.randint(*sessions)):
        before = mesh.export_state()
        ci = rnd.randrange(len(cams))
        cl = []
        for _ in range(rnd.randint(*clicks)):
            if rnd.random() < 0.2:
                ci = rnd.randrange(len(cams))  # orbit between clicks
            s = _random_click(rnd, mesh, cams[ci], p_face, p_vertex)
            if s is not None:
                cl.append((ci, s[0], s[1]))
        f: dict = {}
        _knife, _acc, msg = play(cls, mesh, cl, cams, feats=f, no_face=p_face == 0.0)
        record.append((cl, before, msg))
        feats.append(f)
        issues = integrity(mesh, scene)
        if issues:
            return record, si, issues, feats
    return record, None, {}, feats


def fuzz(scene: str, n: int, **kw):
    """[(seed, failing session, issue classes, features of that session)] and the feature counts of
    every clean session (for comparison)."""
    fails, clean = [], collections.Counter()
    for seed in range(n):
        _record, si, issues, feats = random_run(scene, seed, **kw)
        if si is not None:
            fails.append((seed, si, sorted(issues), feats[si]))
        for k, f in enumerate(feats):
            if k != si:
                clean[frozenset(f)] += 1
    return fails, clean


# -- minimising ----------------------------------------------------------------------------

def replay(scene, state, clicks, cls=KnifeFaceCrossFace, no_face=False):
    mesh = Mesh.from_state(state)
    cams = [camera_for(SCENES[scene](), y, p) for y, p in CAMS[scene]]
    _knife, _acc, msg = play(cls, mesh, clicks, cams, no_face=no_face)
    return mesh, integrity(mesh, scene), msg


def minimise(scene, state, clicks, klass: str, cls=KnifeFaceCrossFace):
    """Greedy one-at-a-time removal (ddmin with chunk 1): smallest click list that keeps `klass`."""
    cur = list(clicks)
    changed = True
    while changed:
        changed = False
        for i in range(len(cur)):
            trial = cur[:i] + cur[i + 1:]
            _m, iss, _msg = replay(scene, state, trial, cls)
            if klass in iss:
                cur = trial
                changed = True
                break
    return cur


def describe_clicks(scene, state, clicks, cls=KnifeFaceCrossFace):
    """What each click became (kind + world position), for the write-up."""
    mesh = Mesh.from_state(state)
    cams = [camera_for(SCENES[scene](), y, p) for y, p in CAMS[scene]]
    knife, _ = new_session(cls, mesh)
    out = []
    for ci, sx, sy in clicks:
        cam = cams[ci]
        t = knife_face_pick(cam, mesh, sx, sy, W, H, occlusion=True)
        if hasattr(knife, "set_view"):
            knife.set_view(cam, W, H, occlusion=True)
            t = knife.snap_target(t, sx, sy)
        ok = knife.click(t)
        desc = t.get("kind")
        if desc == "face":
            desc += " " + str(tuple(round(c, 3) for c in t["position"]))
        elif desc == "edge":
            a, b = mesh.edge_vertices(t["edge_id"])
            pa, pb = mesh.vertex_position(a), mesh.vertex_position(b)
            desc += " " + str(tuple(round(pa[k] + t["t"] * (pb[k] - pa[k]), 3) for k in range(3)))
        elif desc == "vertex":
            desc += " " + str(tuple(round(c, 3) for c in mesh.vertex_position(t["vertex_id"])))
        out.append((ci, round(sx, 1), round(sy, 1), desc, ok, knife.last_message))
    knife.cancel()
    knife.deactivate()
    return out


# -- targeted cases (hypotheses) -------------------------------------------------------------
#
# Direct targets instead of screen clicks (the minimal click lists, written as world positions):
# ("v", pos) vertex, ("e", pos_a, pos_b, t) edge point from a to b, ("f", pos) face interior.
# A case is a list of sessions, each a list of targets, played on a fresh `grid` / `cube`.

def _vid_at(mesh, pos):
    return next(v for v in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(v), pos) < 1e-9)


def target(mesh, spec) -> dict:
    kind = spec[0]
    if kind == "v":
        return {"kind": "vertex", "vertex_id": _vid_at(mesh, spec[1])}
    if kind == "e":
        # The point a + t (b - a), on whichever current edge holds it (B has already split edges).
        a, b, t = spec[1], spec[2], spec[3]
        pos = tuple(a[k] + t * (b[k] - a[k]) for k in range(3))
        for eid in mesh.all_edge_ids():
            p0, p1 = (mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
            d = [p1[k] - p0[k] for k in range(3)]
            dd = sum(c * c for c in d)
            u = sum((pos[k] - p0[k]) * d[k] for k in range(3)) / dd
            if 1e-9 < u < 1.0 - 1e-9 and math.dist(pos, tuple(p0[k] + u * d[k] for k in range(3))) < 1e-9:
                return {"kind": "edge", "edge_id": eid, "t": u}
        raise LookupError(f"no edge holds {pos}")
    pos = spec[1]
    for fid in mesh.all_face_ids():
        fr = _face_frame(mesh, fid)
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
        n = _newell(pts)
        nl = math.sqrt(sum(c * c for c in n)) or 1.0
        if abs(sum((pos[k] - pts[0][k]) * n[k] for k in range(3))) / nl > 1e-9:
            continue
        if _point_in_polygon(fr[0](pos), fr[1]) == 1:
            return {"kind": "face", "face_id": fid, "position": tuple(pos), "distance_px": 99.0}
    raise LookupError(f"no face holds {pos}")


def play_case(cls, scene, sessions, cam=None):
    """Returns (per session: commit message -> integrity, accepted/total clicks, issues after the last)."""
    mesh = SCENES[scene]()
    msgs, acc, tot = [], 0, 0
    for specs in sessions:
        knife, _ = new_session(cls, mesh)
        if cam is not None and hasattr(knife, "set_view"):
            knife.set_view(camera_for(mesh, *cam), W, H, occlusion=True)
        for spec in specs:
            tot += 1
            acc += bool(knife.click(target(mesh, spec)))
        knife.commit()
        iss = integrity(mesh, scene)
        msgs.append(f"{knife.last_message} -> {sorted(iss) or 'clean'}")
        knife.deactivate()
    return msgs, (acc, tot), iss


# name: (hypothesis, scene, camera (yaw, pitch) or None, sessions, what it shows)
CASES = {
    "HB1 chord crosses an earlier notch": (
        "H-b", "grid", None,
        [[("e", (0, 0, 0), (1, 0, 0), 0.2), ("f", (0.8, 0.5, 0)), ("e", (0, 0, 0), (1, 0, 0), 0.6),
          ("e", (0, 1, 0), (1, 1, 0), 0.5)]],
        "a later straight segment crosses an earlier segment of the same commit inside one quad"),
    "HB2 bent run crosses an earlier bent run": (
        "H-b", "grid", (0.0, 89.0),
        [[("e", (0, 0, 0), (0, 1, 0), 0.5), ("f", (0.5, 0.8, 0)), ("e", (1, 0, 0), (1, 1, 0), 0.5),
          ("f", (0.2, 0.9, 0)), ("e", (0, 1, 0), (1, 1, 0), 0.2)]],
        "both runs have interior points; the second crosses the first"),
    "HA1 stale face: notch on a shared edge": (
        "H-a", "grid", None,
        [[("e", (1, 1, 0), (1, 2, 0), 0.5), ("e", (2, 1, 0), (2, 2, 0), 0.5), ("e", (1, 1, 0), (2, 1, 0), 0.7),
          ("f", (1.5, 1.3, 0)), ("e", (1, 1, 0), (2, 1, 0), 0.3)]],
        "the notch's quad is already split by earlier runs; both notch ends also lie on the quad below"),
    "HA2 stale face across the cube's fold": (
        "H-a/H-c", "cube", (35.0, 30.0),
        [[("e", (-1, 1, 1), (1, 1, 1), 0.6), ("e", (1, 1, 1), (1, 1, -1), 0.4), ("f", (0.6, 1, -0.3)),
          ("e", (1, 1, 1), (1, 1, -1), 0.75)]],
        "a notch on the top side whose ends lie on the top/right fold edge, after the top was split"),
    "HC1 interior points on two sides": (
        "H-c", "cube", (35.0, 30.0),
        [[("e", (-1, 1, 1), (1, 1, 1), 0.5), ("f", (0.0, 1, 0.0)), ("f", (0.0, 0.0, 1)),
          ("e", (-1, -1, 1), (1, -1, 1), 0.5)]],
        "Q5 inserts a crossing on the fold edge between the two interior points (D refuses the second)"),
    "HD1 trailing interior point dropped": (
        "H-d", "grid", None,
        [[("e", (0, 0, 0), (0, 1, 0), 0.5), ("f", (0.5, 0.5, 0))]],
        "a dangling tail never reaches the resolver"),
    "HD2 run end leaves a collinear vertex, a later chord runs along it": (
        "H-d / along", "grid", None,
        [[("e", (1, 1, 0), (2, 1, 0), 0.5), ("e", (1, 2, 0), (2, 2, 0), 0.5)],
         [("v", (1, 1, 0)), ("e", (1.5, 1, 0), (2, 1, 0), 0.5)]],
        "session 1 is clean (the quad below gains a straight-angle vertex); session 2's chord runs along it"),
    "T0 planner edge hit at t = 0": (
        "tzero", "grid", (0.0, 89.0),
        [[("v", (3, 3, 0)), ("e", (1, 3, 0), (2, 3, 0), 0.514)]],
        "a line along a grid row: PLANE reports vertex (2,3) as an edge hit at t ~ 1e-15"),
    "L1 chord leaves a face made concave by an earlier session": (
        "leave", "grid", None,
        [[("e", (0, 0, 0), (1, 0, 0), 0.5), ("f", (0.5, 0.5, 0)), ("e", (0, 0, 0), (0, 1, 0), 0.5)],
         [("e", (0.5, 0, 0), (1, 0, 0), 0.6), ("e", (0, 0.5, 0), (0, 1, 0), 0.6)]],
        "session 2 connects two points of the L-shaped face straight across its missing corner"),
}


def run_cases():
    for name, (hyp, scene, cam, sessions, what) in CASES.items():
        print(f"[PROBE] case {name} ({hyp}): {what}")
        for label, cls in (("Q5", KnifeFaceCrossFace), ("D", KnifeFaceCollected), ("B", KnifeFaceImmediate)):
            try:
                msgs, (acc, tot), iss = play_case(cls, scene, sessions, cam)
            except LookupError as exc:
                print(f"      {label}: setup failed ({exc})")
                continue
            print(f"      {label}: {acc}/{tot} clicks accepted; " + " | ".join(msgs))


def run_variants(n):
    """Same seeds under D and B: the first session's clicks are identical; later sessions are drawn on
    each variant's own result. Each variant keeps only the clicks it accepts."""
    for scene in ("grid", "cube"):
        for label, cls in (("D", KnifeFaceCollected), ("B", KnifeFaceImmediate)):
            fails, clean = fuzz(scene, n, cls=cls)
            _summary(f"{scene} {label}", fails, clean, n)


def dropped_runs(scene, n, **kw):
    """Sessions whose commit message reports fewer applied cuts than runs ("N-1/N"), with and without
    the 'cross' feature — a crossing run that the resolver cannot connect is dropped silently."""
    import re
    tot = collections.Counter()
    for seed in range(n):
        record, si, _iss, feats = random_run(scene, seed, **kw)
        for k, (_c, _b, msg) in enumerate(record):
            m = re.search(r"(\d+)/(\d+) cut", msg)
            dropped = bool(m and int(m.group(1)) < int(m.group(2)))
            tot[("cross" in feats[k], dropped)] += 1
    print(f"[PROBE] {scene}: sessions with a dropped run — with 'cross': {tot[(True, True)]}/"
          f"{tot[(True, True)] + tot[(True, False)]}, without: {tot[(False, True)]}/"
          f"{tot[(False, True)] + tot[(False, False)]}")


def run_production():
    """Open point (handoff §8): the Production Knife (`src/mirai/topology/knife.py`, read-only here) connects
    every straight segment through `connect_in_shared_face` (lowest face id, no geometric check), like
    D/Q5's plain runs. Plays the plain-chord cases on it: HD2 (along) and L1 (leave)."""
    from mirai.topology.knife import KnifeTool

    for name in ("HD2 run end leaves a collinear vertex, a later chord runs along it",
                 "L1 chord leaves a face made concave by an earlier session"):
        _hyp, scene, _cam, sessions, _what = CASES[name]
        mesh = SCENES[scene]()
        out = []
        for k, specs in enumerate(sessions):
            cls = KnifeTool if k == len(sessions) - 1 else KnifeFaceCollected  # setup with the lab
            knife, _ = new_session(cls, mesh)
            acc = sum(bool(knife.click(target(mesh, spec))) for spec in specs)
            knife.commit()
            knife.deactivate()
            out.append(f"{cls.__name__} {acc}/{len(specs)} -> {sorted(integrity(mesh, scene)) or 'clean'}")
        print(f"[PROBE] production {name}: " + " | ".join(out))


# -- main ----------------------------------------------------------------------------------

def _summary(label, fails, clean, n):
    cls_count = collections.Counter(k for _s, _si, ks, _f in fails for k in ks)
    print(f"[PROBE] {label}: {len(fails)}/{n} runs with an integrity failure; by class: {dict(cls_count)}")
    by_feat = collections.Counter(frozenset(f) for *_x, f in fails)
    for fs, c in by_feat.most_common():
        print(f"    failing sessions with features {sorted(fs) or ['(none)']}: {c}")
    feat_any = collections.Counter(k for *_x, f in fails for k in f)
    clean_any = collections.Counter(k for fs, c in clean.items() for k in fs for _ in range(c))
    print(f"    feature present in failing sessions: {dict(feat_any)}; in clean sessions: {dict(clean_any)}"
          f" (clean sessions: {sum(clean.values())})")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=400)
    ap.add_argument("--minimise", action="store_true")
    ap.add_argument("--cases", action="store_true")
    ap.add_argument("--variants", action="store_true")
    ap.add_argument("--edge-only", action="store_true")
    ap.add_argument("--dropped", action="store_true")
    ap.add_argument("--production", action="store_true")
    args = ap.parse_args(argv)

    if args.production:
        run_production()
        return
    if args.cases:
        run_cases()
        return
    if args.variants:
        run_variants(args.n)
        return
    if args.dropped:
        for scene in ("grid", "cube"):
            dropped_runs(scene, args.n)
        return
    for scene in ("grid", "cube"):
        kw = {"p_face": 0.0} if args.edge_only else {}
        fails, clean = fuzz(scene, args.n, **kw)
        _summary(f"{scene} Q5{' edge-only' if args.edge_only else ''}", fails, clean, args.n)
        if args.minimise:
            seen = set()
            for seed, si, ks, _f in fails:
                for k in ks:
                    if k in seen:
                        continue
                    record, *_rest = random_run(scene, seed, **kw)
                    clicks, before, _msg = record[si]
                    small = minimise(scene, before, clicks, k)
                    _m, iss, msg = replay(scene, before, small)
                    print(f"  {scene} seed {seed} session {si}: class {k} -> {len(small)} click(s) ({msg})")
                    for row in describe_clicks(scene, before, small):
                        print("     ", row)
                    seen.add(k)


if __name__ == "__main__":
    main()
