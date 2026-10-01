"""DISCOVERY PROBE — Face Holes: what a closed shape inside a face is in Mirai today.

Evidence for `docs/research/topology/FACE_HOLES_DISCOVERY.md` (Q2, Q3).
Not a tool, not wired anywhere, no Core change, no Lab change. Uses only the public
Core API plus existing read-only consumers (fan triangulation, `pick_face`, the
Playground ExtrudeTool) and the Knife Face Cut Lab's stand-in functions
(`playground/experiments/knife_face/engine.py` when written; since WP-KNIFE-01 S1 in
`src/mirai/topology/knife_resolve.py`, built from `Mesh.split_face`), imported unchanged.

Scene: 3x3 grid of unit quads in z = 0, faces CCW seen from +Z; the closed shape is a
triangle inside the centre quad (1,1)-(2,2) — the shape of Lab task 5 / discovery FC6.

Constructions of "triangle inside a quad" (H0 = bridged storage):
  lab-ccw   Lab D stand-in (select_bridge + close_loop_with_bridges), loop clicked CCW
  lab-cw    same, loop clicked CW
  fc6       discovery FC6 "2 bridges" (two split_face_path calls from the quad's corners)
and, for comparison, what any *current* consumer would see of a holed face if the Core
kept `face_vertices()` = outer loop only:
  outer     outer quad unchanged + inner triangle face on top (= FC6 "0 bridges")

Measured per construction: invariants, IDs, orientation consistency, per-face polygon
validity, fan-triangulation coverage of the quad (what render + pick_face use), the face
`pick_face` returns inside the triangle, delete-inner / delete-ring / extrude-ring, and
what happens to an EdgeId-keyed "hidden bridge" flag (H2) after one more split.

Run:  python experiments/topology/face_holes_probe.py
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import Mesh, Scene  # noqa: E402
from core.mesh import MeshError  # noqa: E402
from core.selection import SelectionMode  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from mirai.viewport.picking import pick_face  # noqa: E402
from viewport.derived import DerivedGeometry, triangulate_mesh_face  # noqa: E402

from mirai.topology.knife_resolve import (  # noqa: E402  (moved from the Lab engine, WP-KNIFE-01 S1)
    close_loop_with_bridges,
    select_bridge,
    split_face_path,
)
from playground.topology_tools.extrude import ExtrudeTool  # noqa: E402

TRI_CCW = [(1.3, 1.3, 0.0), (1.7, 1.3, 0.0), (1.5, 1.7, 0.0)]  # Lab test's click order
TRI_CW = [TRI_CCW[0], TRI_CCW[2], TRI_CCW[1]]
TRI_CENTROID = (1.5, (1.3 + 1.3 + 1.7) / 3.0, 0.0)
WING_POINT = (1.1, 1.8, 0.0)  # inside the centre quad, outside the triangle


# -- scene ------------------------------------------------------------------------------

def _grid(n=3):
    scene, p = Scene(), {}
    m = scene.mesh
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = m.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            m.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return scene, p


def _face_with(m, *vs):
    return next(f for f in sorted(m.all_face_ids(), key=int)
                if all(v in m.face_vertices(f) for v in vs))


def _xy(m, v):
    x, y, _ = m.vertex_position(v)
    return x, y


def _check(m, label):
    try:
        assert_mesh_invariants(m, context=label)
        return "invariants OK"
    except AssertionError as exc:
        return f"INVARIANT VIOLATION: {str(exc)[:80]}"


def _sizes(m):
    return dict(sorted(collections.Counter(len(m.face_vertices(f)) for f in m.all_face_ids()).items()))


def _euler(m):
    return len(m.all_vertex_ids()) - len(m.all_edge_ids()) + len(m.all_face_ids())


# -- constructions ------------------------------------------------------------------------

def build(kind):
    """Returns (scene, info) with info = {inner, ring (list), bridges, loop_edges, centre}."""
    scene, p = _grid()
    m = scene.mesh
    centre = _face_with(m, p[(1, 1)], p[(2, 2)])
    info = {"centre": centre, "maxima": tuple(max(int(x) for x in ids) for ids in
                                               (m.all_vertex_ids(), m.all_edge_ids(), m.all_face_ids())),
            "outer_edges": set(m.face_edges(centre))}
    if kind in ("lab-ccw", "lab-cw"):
        loop = TRI_CCW if kind == "lab-ccw" else TRI_CW
        boundary = m.face_vertices(centre)
        i1, bv1, i2, bv2 = select_bridge(m, boundary, loop)
        loop_vs, f_inner, f_a, f_b, loop_edges = close_loop_with_bridges(m, centre, loop, i1, bv1, i2, bv2)
        bridges = [_edge(m, bv1, loop_vs[i1]), _edge(m, bv2, loop_vs[i2])]
        info.update(inner=f_inner, ring=[f_a, f_b], bridges=bridges, loop_edges=loop_edges, loop_vs=loop_vs)
    elif kind == "fc6":
        c0, c2 = p[(1, 1)], p[(2, 2)]
        (p1, p3), _f1, _f2, _ = split_face_path(m, centre, c0, c2, [TRI_CCW[0], TRI_CCW[2]])
        g = _face_with(m, p1, p3, p[(1, 2)])
        (p2,), _g1, _g2, _ = split_face_path(m, g, p1, p3, [TRI_CCW[1]])
        loop_vs = [p1, p2, p3]
        inner = next(f for f in m.all_face_ids() if set(m.face_vertices(f)) == set(loop_vs))
        ring = [f for f in m.all_face_ids() if f not in _grid_faces_except(m, p, centre) and f != inner]
        info.update(inner=inner, ring=ring, bridges=[_edge(m, c0, p1), _edge(m, c2, p3)],
                    loop_edges=[_edge(m, p1, p2), _edge(m, p2, p3), _edge(m, p3, p1)], loop_vs=loop_vs)
    elif kind == "outer":
        loop_vs = [m.add_vertex(x) for x in TRI_CCW]
        inner = m.add_face(loop_vs)
        info.update(inner=inner, ring=[centre], bridges=[], loop_edges=m.face_edges(inner), loop_vs=loop_vs)
    else:
        raise ValueError(kind)
    return scene, info


def _grid_faces_except(m, p, centre):
    return {f for f in m.all_face_ids() if f != centre and len(m.face_vertices(f)) == 4
            and all(v in p.values() for v in m.face_vertices(f))}


def _edge(m, a, b):
    return next(e for e in m.all_edge_ids() if set(m.edge_vertices(e)) == {a, b})


# -- geometry helpers (2D, the grid is in z = 0) -----------------------------------------------

def _signed_area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                     for i in range(len(pts)))


def _segments_cross(a, b, c, d):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return (orient(a, b, c) * orient(a, b, d) < 0) and (orient(c, d, a) * orient(c, d, b) < 0)


def _is_simple(pts):
    n = len(pts)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if _segments_cross(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n]):
                return False
    return True


def _in_tri(pt, a, b, c):
    s1 = (b[0] - a[0]) * (pt[1] - a[1]) - (b[1] - a[1]) * (pt[0] - a[0])
    s2 = (c[0] - b[0]) * (pt[1] - b[1]) - (c[1] - b[1]) * (pt[0] - b[0])
    s3 = (a[0] - c[0]) * (pt[1] - c[1]) - (a[1] - c[1]) * (pt[0] - c[0])
    return (s1 > 0 and s2 > 0 and s3 > 0) or (s1 < 0 and s2 < 0 and s3 < 0)


def face_report(m, f):
    vs = m.face_vertices(f)
    pts = [_xy(m, v) for v in vs]
    area = _signed_area(pts)
    tris = triangulate_mesh_face(m, f)
    tri_areas = [_signed_area([_xy(m, v) for v in t]) for t in tris]
    flipped = sum(1 for a in tri_areas if a * area < 0)
    first_tri_up = tri_areas[0] > 0
    return {
        "n": len(vs),
        "area": round(abs(area), 4),
        "normal": "+Z" if area > 0 else "-Z",
        "simple": _is_simple(pts),
        "fan_flipped": flipped,
        "fan_overshoot": round(sum(abs(a) for a in tri_areas) - abs(area), 4),
        "derived_normal": "+Z" if first_tri_up else "-Z",
    }


def orientation_mismatches(m):
    """Interior edges whose two faces traverse them in the same direction (inconsistent winding)."""
    directed = collections.defaultdict(list)
    for f in m.all_face_ids():
        b = m.face_vertices(f)
        for i in range(len(b)):
            directed[frozenset((b[i], b[(i + 1) % len(b)]))].append((b[i], b[(i + 1) % len(b)]))
    return sum(1 for uses in directed.values() if len(uses) == 2 and uses[0] == uses[1])


def _in_polygon(pt, pts):
    """Even-odd ray test — the face as a true polygon, independent of any triangulation."""
    inside = False
    for i in range(len(pts)):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
        if (y1 > pt[1]) != (y2 > pt[1]) and pt[0] < x1 + (pt[1] - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def coverage(m, n=40):
    """Sample the centre quad (offsets chosen off every edge and fan diagonal) and count per
    point how many faces cover it — (a) as true polygons, (b) as fan triangles, which is
    exactly what the RenderMesh index buffer and pick_face iterate over."""
    polys = [[_xy(m, v) for v in m.face_vertices(f)] for f in m.all_face_ids()]
    tris = [[_xy(m, v) for v in t] for f in m.all_face_ids() for t in triangulate_mesh_face(m, f)]
    poly_hist, fan_hist = collections.Counter(), collections.Counter()
    for i in range(n):
        for j in range(n):
            pt = (1.0 + (i + 0.437) / n, 1.0 + (j + 0.291) / n)
            poly_hist[min(sum(1 for p in polys if _in_polygon(pt, p)), 2)] += 1
            fan_hist[min(sum(1 for t in tris if _in_tri(pt, *t)), 2)] += 1
    total = n * n

    def fmt(h):
        return "/".join(f"{100.0 * h.get(k, 0) / total:.1f}%" for k in (0, 1, 2))
    return fmt(poly_hist), fmt(fan_hist)


def covering_faces(m, point):
    as_poly = sorted(int(f) for f in m.all_face_ids()
                     if _in_polygon(point[:2], [_xy(m, v) for v in m.face_vertices(f)]))
    as_fan = sorted(int(f) for f in m.all_face_ids()
                    if any(_in_tri(point[:2], *[_xy(m, v) for v in t]) for t in triangulate_mesh_face(m, f)))
    return f"polygons {as_poly}, fan {as_fan}"


def picked(m, point):
    cam = OrbitCamera(target=(1.5, 1.5, 0.0), distance=6.0, yaw=0.0, pitch=0.0)
    w = h = 400
    sx, sy = cam.project_to_screen(point, w, h)
    f = pick_face(cam, m, sx, sy, w, h)
    return None if f is None else int(f)


# -- scenarios -----------------------------------------------------------------------------------

def report(kind):
    scene, info = build(kind)
    m = scene.mesh
    inner, ring = info["inner"], info["ring"]
    print(f"\n== {kind} ==")
    print(f"  structure : {_check(m, kind)}; sizes={_sizes(m)}; faces={len(m.all_face_ids())} "
          f"(grid had 9); V-E+F={_euler(m)} (grid: 1)")
    print(f"  ring faces: {[int(f) for f in ring]} sizes={[len(m.face_vertices(f)) for f in ring]}; "
          f"inner face {int(inner)}; bridge edges {[int(e) for e in info['bridges']]} "
          f"edge_faces={[len(m.edge_faces(e)) for e in info['bridges']]}")
    if kind != "outer":
        mv, me, mf = info["maxima"]
        new_ids_ok = (all(int(v) > mv for v in info["loop_vs"]) and all(int(f) > mf for f in ring + [inner]))
        print(f"  IDs       : centre face {int(info['centre'])} valid={m.is_valid_face(info['centre'])}; "
              f"new V/F above previous maxima: {new_ids_ok}; old boundary edges kept: "
              f"{info['outer_edges'] <= set(m.all_edge_ids())}")
    print(f"  winding   : {orientation_mismatches(m)} interior edge(s) with inconsistent winding; "
          f"sum of ring+inner polygon areas = "
          f"{round(sum(face_report(m, f)['area'] for f in ring + [inner]), 4)} (centre quad = 1.0)")
    for f in ring + [inner]:
        r = face_report(m, f)
        role = "inner" if f == inner else "ring "
        print(f"  {role} F{int(f):<3}: n={r['n']} area={r['area']} normal={r['normal']} simple={r['simple']} "
              f"fan: flipped tris={r['fan_flipped']} overshoot area={r['fan_overshoot']} "
              f"derived normal={r['derived_normal']}")
    poly_cov, fan_cov = coverage(m)
    print(f"  coverage  : centre quad, 40x40 samples, faces per point 0 (gap) / 1 / >=2 (overlap): "
          f"as polygons {poly_cov}; as fan triangles {fan_cov}")
    print(f"  at triangle centroid: covered by faces {covering_faces(m, TRI_CENTROID)}, "
          f"pick_face -> {picked(m, TRI_CENTROID)} (inner is {int(inner)})")
    print(f"  in ring area {WING_POINT[:2]}: covered by faces {covering_faces(m, WING_POINT)}, "
          f"pick_face -> {picked(m, WING_POINT)}")
    return scene, info


def delete_and_extrude(kind):
    print(f"  -- {kind}: Silo comparison (delete / extrude) --")
    scene, info = build(kind)
    m = scene.mesh
    m.remove_face(info["inner"])
    free = [e for e in m.all_edge_ids() if not m.edge_faces(e)]
    print(f"  delete inner : {_check(m, 'del-inner')}; free edges={len(free)}; "
          f"loop edges now 1-face: {all(len(m.edge_faces(e)) == 1 for e in info['loop_edges'])}")

    scene, info = build(kind)
    m = scene.mesh
    for f in info["ring"]:
        m.remove_face(f)
    free = [e for e in m.all_edge_ids() if not m.edge_faces(e)]
    print(f"  delete ring  : {_check(m, 'del-ring')}; free edges left={sorted(int(e) for e in free)} "
          f"(bridges {[int(e) for e in info['bridges']]}) — remove_face keeps edges (mesh.py:261-272)")

    scene, info = build(kind)
    m = scene.mesh
    before = len(m.all_face_ids())
    tool = ExtrudeTool(scene, camera=None)
    scene.selection.mode = SelectionMode.FACE
    scene.selection.set(set(info["ring"]))
    tool.activate()
    tool.begin(face_ids=set(info["ring"]))
    tool.commit()
    walls = len(m.all_face_ids()) - before  # +caps -originals cancel for the ring faces
    print(f"  extrude ring : {_check(m, 'extrude-ring')}; side walls={walls} "
          f"(outer loop 4 + inner loop 3 = 7 expected, bridges internal); caps={len(tool.new_face_ids)}; "
          f"winding mismatches after={orientation_mismatches(m)}")
    tool.deactivate()


def h2_flag_fragility():
    print("\n== H2: an EdgeId-keyed 'hidden bridge' flag across one more mutation ==")
    scene, info = build("fc6")
    m = scene.mesh
    hidden = set(info["bridges"])
    before = m.export_state()
    b0 = info["bridges"][0]
    v, e_a, e_b = m.split_edge(b0, 0.5)  # e.g. a later Knife click on the (invisible) bridge
    print(f"  split_edge(bridge {int(b0)}) -> halves {int(e_a)}, {int(e_b)}; flagged ids still valid: "
          f"{sorted(int(e) for e in hidden if m.is_valid_edge(e))}; halves flagged: "
          f"{e_a in hidden or e_b in hidden} -> the hidden edge becomes 2 visible edges "
          f"unless every primitive propagates the flag")
    m.load_state(before)
    print(f"  after load_state(before) (= Undo): flagged ids valid again: "
          f"{sorted(int(e) for e in hidden if m.is_valid_edge(e))} "
          f"(a side table stays correct only if Undo restores it together with the mesh)")
    d = DerivedGeometry(m)
    rim = [e for e in m.all_edge_ids() if len(m.edge_faces(e)) == 2]
    print(f"  topology alone cannot tell a bridge from any other interior edge: "
          f"{len(rim)} interior edges, bridges among them: "
          f"{sum(1 for e in info['bridges'] if e in rim)}; face normals of the two ring faces equal: "
          f"{d.face_normals[info['ring'][0]] == d.face_normals[info['ring'][1]]}")


if __name__ == "__main__":
    for k in ("lab-ccw", "lab-cw", "fc6", "outer"):
        report(k)
    print()
    for k in ("lab-ccw", "fc6"):
        delete_and_extrude(k)
    h2_flag_fragility()
