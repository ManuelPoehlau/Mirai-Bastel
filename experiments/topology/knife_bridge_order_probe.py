"""PROBE — Knife closed shape: does the bridge result depend on click order / direction?

Evidence for `playground/experiments/knife_face/decision.md` (Task A, 2026-09-29).
Not a tool, not wired anywhere, no Core change. Drives the Knife Face Lab engine
(`KnifeFaceCollected`, D — Q5 subclasses its resolver unchanged) through the public click/commit
interface only: k interior clicks inside ONE face, `commit()` (D's implicit close).

Matrix per surface: k = 3..8 loop points x every start rotation (k) x both directions (2)
x three loop shapes ("sym": regular k-gon centred in the face; "skew": off-centre, unequal radii,
convex and star-shaped around its centre; "tie", k = 4 only: the square (0.25..0.75)^2 in the face's
parameter square, whose distances to the four corners are *exactly* equal — the click-order tie case).
Surfaces: `grid` (unit quad, planar) and `head` (sampled quads of the head asset, not planar).

Measured per run (all positions rounded to 6 digits, so runs compare by geometry, not by id):
  bridges     edges between an original boundary vertex and a new loop vertex, as unordered position pairs
  partition   the resulting faces as cyclic position sequences (rotated to their lowest position,
              orientation kept) — the same set means the same topology *and* winding
  normals     per face: Newell normal . parent's Newell normal (agree = > 0)
  overlap     sum of |face areas| vs parent area (projected); and coverage of
              a 41x41 sample grid (offset by irrational fractions, so no sample sits exactly on an edge of a symmetric shape) over the parent's *projection* (onto the plane through its
              centroid, perpendicular to its Newell normal) — every sample must lie in exactly
              one face's projected polygon; non-planar `head` quads use this projected measure
  invariants  `tests/mesh_invariants.assert_mesh_invariants`
  winding     interior edges traversed in the same direction by both faces (inconsistent winding)

Run:  python experiments/topology/knife_bridge_order_probe.py [--head N]
"""

from __future__ import annotations

import collections
import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests"), str(_ROOT / "examples"),
           str(_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import Mesh, Scene  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402

from playground._paths import DEFAULT_HEAD_ASSET  # noqa: E402
from playground.experiments.knife_face.engine import KnifeFaceCollected  # noqa: E402

SAMPLES = 41
ROUND = 6


def _r(p):
    return tuple(round(c, ROUND) + 0.0 for c in p)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return tuple(n)


def _unit(v):
    L = math.sqrt(_dot(v, v)) or 1.0
    return (v[0] / L, v[1] / L, v[2] / L)


# -- scenes -----------------------------------------------------------------------------

def grid_scene():
    mesh = Mesh()
    vs = [mesh.add_vertex(p) for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0))]
    mesh.add_face(vs)
    scene = Scene()
    scene.mesh = mesh
    return scene


def _bilinear(corners, u, v):
    a, b, c, d = corners
    return tuple((1 - u) * (1 - v) * a[i] + u * (1 - v) * b[i] + u * v * c[i] + (1 - u) * v * d[i] for i in range(3))


def loop_points(corners, k, shape):
    """k loop points CCW in the face's (u, v) parameter square, mapped onto the (bilinear) quad."""
    pts = []
    for i in range(k):
        a = 2 * math.pi * i / k
        if shape == "tie":  # k = 4 only: a square loop, all distances to the corners exactly equal
            u, v = ((0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75))[i]
            pts.append(_bilinear(corners, u, v))
            continue
        if shape == "sym":
            ru, rv, cu, cv = 0.25, 0.25, 0.5, 0.5
        else:
            radius = 0.16 + 0.10 * ((i * 7) % 5) / 4.0
            ru = rv = radius
            cu, cv = 0.44, 0.58
        pts.append(_bilinear(corners, cu + ru * math.cos(a), cv + rv * math.sin(a)))
    return pts


# -- measures ---------------------------------------------------------------------------

def _basis(normal):
    n = _unit(normal)
    ref = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = _unit((n[1] * ref[2] - n[2] * ref[1], n[2] * ref[0] - n[0] * ref[2], n[0] * ref[1] - n[1] * ref[0]))
    v = (n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0])
    return u, v


def _in_poly(pt, poly):
    x, y = pt
    inside = False
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _area2d(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def _rotate_lowest(seq):
    i = min(range(len(seq)), key=lambda k: seq[k])
    return tuple(seq[i:] + seq[:i])


def winding_mismatches(mesh):
    directed = collections.defaultdict(list)
    for f in mesh.all_face_ids():
        b = mesh.face_vertices(f)
        for i in range(len(b)):
            directed[frozenset((b[i], b[(i + 1) % len(b)]))].append((b[i], b[(i + 1) % len(b)]))
    return sum(1 for uses in directed.values() if len(uses) == 2 and uses[0] == uses[1])


def run_case(make_scene, face_boundary_positions, loop):
    """One session: click `loop` in that order, commit. Returns the measured record."""
    scene = make_scene()
    mesh = scene.mesh
    fid = next(iter(mesh.all_face_ids()))
    parent = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
    parent_n = newell(parent)
    orig_vs = set(mesh.all_vertex_ids())

    knife = KnifeFaceCollected()
    knife.activate()
    knife.begin(mesh=mesh, scene=scene, selection=scene.selection)
    for p in loop:
        ok = knife.click({"kind": "face", "face_id": fid, "position": p, "distance_px": 50.0})
        assert ok
    knife.commit()
    knife.deactivate()

    rec = {"msg": knife.last_message}
    try:
        assert_mesh_invariants(mesh, context="probe")
        rec["invariants"] = True
    except AssertionError as exc:  # noqa: BLE001
        rec["invariants"] = False
        rec["invariant_error"] = str(exc)[:80]

    faces = list(mesh.all_face_ids())
    seqs, normals_ok, loop_face_ok = set(), True, None
    loop_pos = {_r(p) for p in loop}
    for f in faces:
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(f)]
        seqs.add(_rotate_lowest([_r(p) for p in pts]))
        agree = _dot(newell(pts), parent_n) > 0
        normals_ok &= agree
        if {_r(p) for p in pts} == loop_pos:
            loop_face_ok = agree
    rec["faces"] = len(faces)
    rec["partition"] = frozenset(seqs)
    rec["normals_agree"] = normals_ok
    rec["inner_normal_agrees"] = loop_face_ok
    rec["bridges"] = frozenset(
        frozenset(_r(mesh.vertex_position(v)) for v in mesh.edge_vertices(e))
        for e in mesh.all_edge_ids()
        if len(set(mesh.edge_vertices(e)) & orig_vs) == 1 and len(set(mesh.edge_vertices(e)) - orig_vs) == 1
    )
    rec["winding_mismatches"] = winding_mismatches(mesh)

    # overlap: projected coverage + area sum
    cen = tuple(sum(p[i] for p in parent) / len(parent) for i in range(3))
    u, v = _basis(parent_n)
    proj = lambda p: (_dot(_sub(p, cen), u), _dot(_sub(p, cen), v))  # noqa: E731
    parent2 = [proj(p) for p in parent]
    xs = [q[0] for q in parent2]
    ys = [q[1] for q in parent2]
    polys = [[proj(mesh.vertex_position(x)) for x in mesh.face_vertices(f)] for f in faces]
    rec["area_ratio"] = sum(abs(_area2d(pl)) for pl in polys) / abs(_area2d(parent2))
    bad = 0
    total = 0
    for i in range(SAMPLES):
        for j in range(SAMPLES):
            pt = (min(xs) + (max(xs) - min(xs)) * (i + 0.3183) / SAMPLES, min(ys) + (max(ys) - min(ys)) * (j + 0.2718) / SAMPLES)
            if not _in_poly(pt, parent2):
                continue
            total += 1
            if sum(1 for pl in polys if _in_poly(pt, pl)) != 1:
                bad += 1
    rec["coverage_bad"] = bad
    rec["coverage_total"] = total
    return rec


def matrix(make_scene, corners, ks=range(3, 9)):
    rows = []
    for shape in ("sym", "skew", "tie"):
        for k in ks:
            if shape == "tie" and k != 4:
                continue
            base = loop_points(corners, k, shape)
            recs = []
            for direction in (1, -1):
                seq = base if direction == 1 else list(reversed(base))
                for s in range(k):
                    recs.append(run_case(make_scene, None, seq[s:] + seq[:s]))
            rows.append((shape, k, recs))
    return rows


def summarize(label, rows):
    """Rows are (shape, k, recs) — several rows with the same (shape, k) (one per quad) are merged:
    the bridge-set / partition counts are the *maximum over quads* (1 = order-independent), the
    other columns are summed over quads."""
    print(f"\n== {label} ==")
    print(f"{'shape':5} {'k':>2} {'runs':>5} {'#bridge sets':>12} {'#partitions':>11} {'normal!=parent':>14} "
          f"{'inner flipped':>13} {'overlap runs':>12} {'sum|area|/parent min..max':>25} {'winding mism.':>13} {'inv fail':>8}")
    merged = collections.OrderedDict()
    for shape, k, recs in rows:
        merged.setdefault((shape, k), []).append(recs)
    totals = collections.Counter()
    for (shape, k), groups in merged.items():
        allr = [r for g in groups for r in g]
        nb = max(len({r["bridges"] for r in g}) for g in groups)
        npart = max(len({r["partition"] for r in g}) for g in groups)
        nn = sum(1 for r in allr if not r["normals_agree"])
        ninner = sum(1 for r in allr if r["inner_normal_agrees"] is False)
        nov = sum(1 for r in allr if r["coverage_bad"])
        rs = [r["area_ratio"] for r in allr]
        nw = sum(1 for r in allr if r["winding_mismatches"])
        ninv = sum(1 for r in allr if not r["invariants"])
        print(f"{shape:5} {k:>2} {len(allr):>5} {nb:>12} {npart:>11} {nn:>14} {ninner:>13} {nov:>12} "
              f"{min(rs):>11.4f}..{max(rs):<11.4f} {nw:>13} {ninv:>8}")
        totals.update(runs=len(allr), configs=len(groups), bridge_sets_gt1=int(nb > 1), partitions_gt1=int(npart > 1),
                      normal_bad=nn, overlap=nov, winding=nw, inv=ninv)
    print(f"  totals: {dict(totals)}")


def head_quads(mesh, n):
    quads = [f for f in sorted(mesh.all_face_ids(), key=int) if len(mesh.face_vertices(f)) == 4]
    step = max(1, len(quads) // n)
    return quads[::step][:n]


def single_face_scene(corners):
    def make():
        mesh = Mesh()
        mesh.add_face([mesh.add_vertex(c) for c in corners])
        scene = Scene()
        scene.mesh = mesh
        return scene
    return make


def main():
    n_head = 8
    if "--head" in sys.argv:
        n_head = int(sys.argv[sys.argv.index("--head") + 1])
    corners = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    summarize("grid (unit quad, planar)", matrix(grid_scene, corners))

    head = build_core_scene_from_obj(DEFAULT_HEAD_ASSET)
    faces = head_quads(head.mesh, n_head)
    all_rows = []
    for f in faces:
        corners_h = [head.mesh.vertex_position(v) for v in head.mesh.face_vertices(f)]
        all_rows.extend(matrix(single_face_scene(corners_h), corners_h, ks=(3, 4, 5, 8)))
    summarize(f"head ({len(faces)} sampled quads, non-planar; projected measure)", all_rows)


if __name__ == "__main__":
    main()
