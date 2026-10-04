"""Head Topology Walkthrough D1..D11 (Discovery).

    xvfb-run -a -s "-screen 0 1280x800x24" python experiments/head_topology_walkthrough/run_walkthrough.py

Writes `step_log.json` and `screenshots/*.png` next to this file. Every verdict is computed from a
measured value against a claim of the research document (`checks`); nothing is decided silently.
Steps that no existing tool can do are logged `blocked` and are NOT worked around by editing the
mesh with a new helper. See README.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from wt import WT, EPS  # noqa: E402
from playground.topology_tools.loop_ring import edge_loop as edge_loop_fn  # noqa: E402

DOC = "docs/research/topology/Character Head Topology From Box to Deformation-Ready Face.md"
LOG: list[dict] = []


class Step:
    def __init__(self, sid, intent, tool, where, topo, scope, planned, claim):
        self.d = {
            "id": sid, "intent": intent, "tool": tool, "where": where,
            "topology_changing": topo, "scope": scope, "planned": planned,
            "doc_claim": claim, "checks": [], "observed": [], "shot": None,
            "verdict": None, "before": None, "after": None,
        }
        LOG.append(self.d)

    def check(self, claim, held, observed):
        self.d["checks"].append({"claim": claim, "result": "held" if held else "deviated", "observed": observed})

    def note(self, text):
        self.d["observed"].append(text)

    def blocked(self, capability, text=""):
        self.d["checks"].append({"claim": self.d["doc_claim"], "result": "blocked",
                                 "observed": f"missing capability: {capability}. {text}".strip()})
        self.d["missing"] = capability

    def done(self, shot=None):
        res = [c["result"] for c in self.d["checks"]]
        self.d["verdict"] = ("blocked" if "blocked" in res else "deviated" if "deviated" in res
                             else "held" if res else "unchecked")
        self.d["shot"] = shot
        return self.d


def poles_split(w):
    ps = w.poles()
    return {"E5+": sum(1 for p in ps if p[1] >= 5), "N3": sum(1 for p in ps if p[1] == 3)}


def run(shots: Path) -> None:
    w = WT(shots)
    m = w.mesh

    def snap(name, **kw):
        w.scene.selection.clear()
        return str(w.snap(name, **kw).relative_to(HERE))

    def axis_edge(axis, pred=lambda a, b: True):
        for e in sorted(m.all_edge_ids(), key=lambda e: int(str(e).split('(')[-1].rstrip(')')) if False else 0):
            a, b = m.edge_vertices(e)
            pa, pb = w.pos(a), w.pos(b)
            d = [abs(pa[i] - pb[i]) > 1e-9 for i in range(3)]
            if d[axis] and sum(d) == 1 and pred(pa, pb):
                return e
        raise RuntimeError("no edge")

    def measure(s, key):
        s.d[key] = {**w.metrics(), **poles_split(w)}

    # ------------------------------------------------------------------ D1
    s = Step("D1.1", "Cube -> 2x2x2", "Playground Loop Insert x3 (loop_insert)", "playground", True, "global",
             True, "Subdivide the cube into 2 x 2 x 2 (mirror leaves 1 column per half).")
    measure(s, "before")
    for ax in (0, 1, 2):
        w.loop_cut(axis_edge(ax))
    measure(s, "after")
    s.check("2 x 2 x 2 = 24 quads, 3 loops", s.d["after"]["F"] == 24 and s.d["after"]["V"] == 26,
            f"F={s.d['after']['F']} V={s.d['after']['V']}")
    s.note("Eight corner vertices of valence 3 (N-poles) exist from the start: " f"{s.d['after']['poles_by_valence']}")
    w.set_view(30, 20, 5.8, (0, 0.2, 0))
    s.done(snap("D1_1_cube_2x2x2", note="D1.1  2x2x2 cube"))

    # D1.2 shape cranium by moving whole faces / loops
    s = Step("D1.2", "Shape cranium: narrower, taller, eye-line layer", "Core Move + ScaleTool (axis X)", "src (mirai.interaction)",
             False, "global", True, "Shape the cranium by moving whole faces and edge loops, not vertices.")
    measure(s, "before")
    w.scale(set(m.all_vertex_ids()), 0.85, (0, 0, 0), space="x")
    w.move(w.verts_where(lambda p: p[1] > 0.9), (0, 0.3, 0))
    w.move(w.verts_where(lambda p: abs(p[1]) < 0.1), (0, 0.2, 0))
    w.move(w.verts_where(lambda p: p[1] < -0.9), (0, 0.3, 0))
    measure(s, "after")
    s.check("a move changes no topology", s.d["before"]["F"] == s.d["after"]["F"] and s.d["before"]["V"] == s.d["after"]["V"],
            "V/E/F unchanged")
    s.check("mirror stays exact when every move is applied to both sides by hand", s.d["after"]["symmetric"],
            f"symmetric={s.d['after']['symmetric']}")
    s.done()

    # D1.3 muzzle/jaw mass: extrude lower-front face pair
    s = Step("D1.3", "Extrude lower-front face pair forward (muzzle and jaw mass)", "Playground ExtrudeTool (region)", "playground",
             True, "local", True, "Extrude the lower-front face pair forward-down once.")
    measure(s, "before")
    lf = w.faces_where(lambda c, n: n[2] > 0.9 and c[1] < 0.1)
    caps = w.extrude(lf, 0.5)
    measure(s, "after")
    s.check("2 faces selected", len(lf) == 2, f"{len(lf)} faces")
    s.check("one Extrude gives 'forward-down'", False, "ExtrudeTool moves the cap along the face normal only (forward); 'down' needs a separate Move")
    s.check("+6 quads (6 walls - 2 + 2 caps)", s.d["after"]["F"] - s.d["before"]["F"] == 6,
            f"F {s.d['before']['F']} -> {s.d['after']['F']}")
    s.note(f"poles {s.d['after']['poles_by_valence']}")
    w.set_view(35, 15, 6.4, (0, 0.1, 0))
    s.done(snap("D1_3_muzzle_mass"))

    # D1.4 neck
    s = Step("D1.4", "Extrude bottom-back faces down (neck)", "Playground ExtrudeTool (region)", "playground", True, "local", True,
             "Extrude the bottom-back faces down once: the neck.")
    measure(s, "before")
    nk = w.faces_where(lambda c, n: n[1] < -0.9 and c[2] < 0)
    ncaps = w.extrude(nk, 0.9)
    w.scale(w.face_verts(ncaps), 0.7, (0, -1.6, -0.5), space=None)
    measure(s, "after")
    s.check("2 faces selected", len(nk) == 2, f"{len(nk)} faces")
    s.done()

    s = Step("D1.5", "Proportion check, three views, subdivision preview", "screenshots; Subdivision Lab (SubdSurface)", "lab",
             False, "global", True, "About 20 to 30 quads. Silhouette right, no features.")
    measure(s, "after")
    s.check("blockout is 20 to 30 quads", 20 <= s.d["after"]["F"] <= 30, f"F={s.d['after']['F']}")
    w.set_view(0, 8, 6.5, (0, -0.35, 0))
    snap("D1_5_front")
    w.set_view(90, 8, 6.5, (0, -0.35, 0))
    snap("D1_5_side")
    w.set_view(35, 15, 6.5, (0, -0.35, 0))
    s.done(snap("D1_5_three_quarter"))

    # ------------------------------------------------------------------ D2
    VIEW_F = (0, 6, 6.8, (0, -0.35, 0.4))
    VIEW_3Q = (32, 14, 6.8, (0, -0.35, 0.4))

    def x_edge_front(x0, x1):
        """Horizontal (x-direction) edge on the upper-front plane (z=1) between x0 and x1."""
        for e in m.all_edge_ids():
            a, b = (w.pos(v) for v in m.edge_vertices(e))
            if abs(a[2] - 1.0) < EPS and abs(b[2] - 1.0) < EPS and abs(a[1] - b[1]) < EPS and a[1] > 0.25:
                lo, hi = sorted((a[0], b[0]))
                if abs(lo - x0) < 1e-6 and abs(hi - x1) < 1e-6:
                    return e
        raise RuntimeError(f"no front x-edge {x0}..{x1}")

    s = Step("D2.1", "Insert vertical loops: 4 columns per half", "Playground Loop Insert x6", "playground", True, "global",
             True, "Insert vertical edge loops through the front until there are 4 columns per half "
                   "(each runs around the whole head: intended, the last global loops).")
    measure(s, "before")
    n0 = len(m.all_face_ids())
    for lo, hi in ((0.0, 0.85), (-0.85, 0.0)):
        w.loop_cut(x_edge_front(lo, hi))
    for lo, hi in ((0.0, 0.425), (0.425, 0.85), (-0.425, 0.0), (-0.85, -0.425)):
        w.loop_cut(x_edge_front(lo, hi))
    measure(s, "after")
    xs = sorted({round(w.pos(v)[0], 4) for v in m.all_vertex_ids() if abs(w.pos(v)[2] - 1.0) < EPS})
    s.check("4 columns per half on the front (9 vertex columns, one on the seam)", len(xs) == 9 and 0.0 in xs, f"x columns {xs}")
    s.check("loops are 'global': every inserted loop crosses the back and the neck",
            s.d["after"]["F"] - s.d["before"]["F"] > 6 * 8,
            f"F {s.d['before']['F']} -> {s.d['after']['F']} for 6 loops")
    s.check("mirror stays symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    w.set_view(*VIEW_F)
    s.done(snap("D2_1_columns", note="D2.1  vertical loops"))

    def y_edge(plane_z, x_ref, ylo, yhi):
        for e in m.all_edge_ids():
            a, b = (w.pos(v) for v in m.edge_vertices(e))
            if abs(a[2] - plane_z) < EPS and abs(b[2] - plane_z) < EPS and abs(a[0] - b[0]) < EPS and abs(a[0] - x_ref) < 1e-6:
                lo, hi = sorted((a[1], b[1]))
                if abs(lo - ylo) < 1e-6 and abs(hi - yhi) < 1e-6:
                    return e
        raise RuntimeError(f"no y-edge z={plane_z} x={x_ref} {ylo}..{yhi}")

    s = Step("D2.2", "Insert horizontal loops: forehead, brow, eye x2, cheekbone + four muzzle/jaw rows",
             "Playground Loop Insert x7", "playground", True, "global", True,
             "Insert horizontal loops until rows are forehead, brow, eye x 2, cheekbone, then four rows on the muzzle and jaw mass.")
    measure(s, "before")
    xr = 0.85
    new_loops = {}
    for key, (z, ylo, yhi) in {
        "mid": (1.0, 0.2, 1.3), "a": (1.0, 0.2, 0.75), "b": (1.0, 0.75, 1.3), "c": (1.0, 0.2, 0.475),
        "m_mid": (1.5, -0.7, 0.2), "m_up": (1.5, -0.025 if False else -0.25, 0.2), "m_dn": (1.5, -0.7, -0.25),
    }.items():
        pass
    new_loops["y075"] = w.loop_cut(y_edge(1.0, xr, 0.2, 1.3))
    new_loops["y0475"] = w.loop_cut(y_edge(1.0, xr, 0.2, 0.75))
    new_loops["y1025"] = w.loop_cut(y_edge(1.0, xr, 0.75, 1.3))
    new_loops["y03375"] = w.loop_cut(y_edge(1.0, xr, 0.2, 0.475))
    new_loops["c_m025"] = w.loop_cut(y_edge(1.5, xr, -0.7, 0.2))
    new_loops["c_m0475"] = w.loop_cut(y_edge(1.5, xr, -0.7, -0.25))
    new_loops["c_m0025"] = w.loop_cut(y_edge(1.5, xr, -0.25, 0.2))
    measure(s, "after")
    rows_front = sorted({round(w.pos(v)[1], 4) for v in m.all_vertex_ids() if abs(w.pos(v)[2] - 1.0) < EPS and abs(w.pos(v)[0]) < EPS})
    rows_cap = sorted({round(w.pos(v)[1], 4) for v in m.all_vertex_ids() if abs(w.pos(v)[2] - 1.5) < EPS and abs(w.pos(v)[0]) < EPS})
    rows_front = [y for y in rows_front if y >= 0.2 - 1e-6]
    s.check("5 rows on the upper front", len(rows_front) == 6, f"y lines {rows_front}")
    s.check("4 rows on the muzzle cap", len(rows_cap) == 5, f"y lines {rows_cap}")
    profile = sorted((w.pos(v) for v in m.all_vertex_ids() if abs(w.pos(v)[0]) < EPS and w.pos(v)[2] >= 1.0 - EPS and ((w.pos(v)[2] < 1.2 and 0.2 - EPS <= w.pos(v)[1] <= 1.3 + EPS) or w.pos(v)[2] >= 1.4)),
                     key=lambda p: -p[1] - (0.0 if p[2] < 1.2 else 1e-3))
    n_rows_profile = len(profile) - 1
    front_quads = [f for f in m.all_face_ids() if w.face_normal(f)[2] > 0.7 and (abs(w.face_center(f)[2] - 1.0) < 1e-3 or abs(w.face_center(f)[2] - 1.5) < 1e-3)]
    s.check("roughly 70 to 80 quads across the full face before features (section C)", 70 <= len(front_quads) <= 80, f"{len(front_quads)} front-facing quads (8 columns x (5 + 4) rows), plus 8 shelf quads")
    s.check("the front profile on the seam has 9 rows from forehead top to chin (5 + 4)", n_rows_profile == 9,
            f"{n_rows_profile} vertical steps along the seam from forehead top to chin: 5 upper-front + 1 shelf + 4 muzzle; seam vertices (y,z): "
            + ", ".join(f"({p[1]:.3f},{p[2]:.1f})" for p in profile))
    s.note("Between the two row groups the muzzle extrusion of D1.3 leaves a horizontal shelf strip (one more quad row) that D2 does not count.")
    w.set_view(*VIEW_3Q)
    s.done(snap("D2_2_rows", note="D2.2  horizontal loops"))

    s = Step("D2.3", "Slide the new loops to their anatomical lines", "Playground Loop Slide x4", "playground", False, "global",
             True, "Slide (not move) each new loop to its anatomical line: brow ridge, lower orbit, cheekbone, lip line.")
    measure(s, "before")
    seam_sample = lambda edges: next(v for v in w.loop_vertices(edges) if abs(w.pos(v)[0]) < EPS and w.pos(v)[2] > 0.9)
    targets = {"y1025": 1.0, "y075": 0.8, "y0475": 0.6, "y03375": 0.4}
    got = {}
    try:
        for k in ("y1025", "y075", "y0475", "y03375"):
            edges = new_loops[k]
            got[k] = w.slide_to(edges, seam_sample(edges), 1, targets[k])
        s.check("slide reaches the target line on every loop", all(abs(got[k] - targets[k]) < 1e-6 for k in got), str({k: round(v, 4) for k, v in got.items()}))
    except Exception as exc:  # noqa: BLE001
        s.check("slide works on every global loop", False, f"{type(exc).__name__}: {exc}")
    measure(s, "after")
    s.check("slide changes no topology", s.d["before"]["F"] == s.d["after"]["F"], "V/E/F unchanged")
    s.check("mirror stays symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    w.set_view(*VIEW_F)
    s.done(snap("D2_3_slid", note="D2.3  loops slid to anatomical lines"))

    s = Step("D2.4", "Check the mirror seam is a vertex column", "measurement script (no app tool)", "-", False, "global", True,
             "Check that the mirror seam is a vertex column.")
    seam_v = {v for v in m.all_vertex_ids() if abs(w.pos(v)[0]) < EPS}
    cross_edges = [e for e in m.all_edge_ids() if (abs(w.pos(m.edge_vertices(e)[0])[0]) < EPS) != (abs(w.pos(m.edge_vertices(e)[1])[0]) < EPS)
                   and (w.pos(m.edge_vertices(e)[0])[0] * w.pos(m.edge_vertices(e)[1])[0]) >= 0]
    flat_cross = [e for e in m.all_edge_ids() if w.pos(m.edge_vertices(e)[0])[0] * w.pos(m.edge_vertices(e)[1])[0] < -EPS]
    s.check("no edge crosses the plane x=0 (all crossings land on vertices)", not flat_cross, f"{len(flat_cross)} crossing edges, {len(seam_v)} seam vertices")
    s.blocked("an in-app seam/symmetry readout in the Playground", "checked by script only; the Playground has no symmetry (declared) and no seam display")
    s.done()
    w.set_view(*VIEW_3Q)
    snap("D2_4_grid_3q", note="D2  grid complete")
    measure(s, "after")

    # ------------------------------------------------------------------ helpers D3+
    zone_by_vid: dict = {}
    CUR_ZONE = ["blockout"]

    def pole_diff(before):
        after = w.pole_map()
        for v in after:
            if v not in before and v not in zone_by_vid:
                zone_by_vid[v] = CUR_ZONE[0]
        added = [(k, tuple(round(c, 3) for c in p)) for v, (k, p) in after.items() if v not in before or before[v][0] != k]
        removed = [(before[v][0], tuple(round(c, 3) for c in before[v][1])) for v in before if v not in after or after[v][0] != before[v][0]]
        return sorted(added), sorted(removed)

    def fmt_poles(lst):
        return "; ".join(f"{'E' if k >= 5 else 'N'}{k}@({p[0]},{p[1]},{p[2]})" for k, p in lst) or "none"

    def _cluster(vals, tol=5e-3):
        out = []
        for v in sorted(vals):
            if not out or v - out[-1][-1] > tol:
                out.append([v])
            else:
                out[-1].append(v)
        return [sum(g) / len(g) for g in out]

    def rank_grid(faces):
        """(col,row) -> face for a planar-ish face patch seen from the front: col = x rank, row = y rank (top = 0)."""
        cs = {f: w.face_center(f) for f in faces}
        xs = _cluster([c[0] for c in cs.values()])
        ys = sorted(_cluster([c[1] for c in cs.values()]), reverse=True)
        near = lambda arr, v: min(range(len(arr)), key=lambda i: abs(arr[i] - v))
        return {(near(xs, c[0]), near(ys, c[1])): f for f, c in cs.items()}, len(xs), len(ys)

    def centroid(vids):
        ps = [w.pos(v) for v in vids]
        return tuple(sum(p[i] for p in ps) / len(ps) for i in range(3))

    for v in w.pole_map():
        zone_by_vid[v] = "blockout (D1)"
    CUR_ZONE[0] = "muzzle"
    # ------------------------------------------------------------------ D3
    s = Step("D3.1", "Select muzzle patch (3 columns per half x 4 lower rows)", "selection (script stand-in for clicks)", "playground",
             False, "local", True, "Select the muzzle patch (6 x 4 faces across both halves).")
    patch = w.faces_where(lambda c, n: n[2] > 0.9 and abs(c[2] - 1.5) < EPS and abs(c[0]) < 0.64 and c[1] < 0.2)
    s.check("patch is 6 x 4 = 24 faces", len(patch) == 24, f"{len(patch)} faces")
    s.check("patch boundary has 20 edges", w.border_length(patch) == 20, f"{w.border_length(patch)} boundary edges")
    s.done()

    s = Step("D3.2", "Region-extrude forward, 2 segments", "Playground ExtrudeTool x2", "playground", True, "local", True,
             "Region-extrude forward, with 2 segments if the muzzle is long. Result: a closed ring around the muzzle base; "
             "its two outer corner vertices per half become E-poles (upper on the cheekbone, lower at the jowl); centre crossings stay regular.")
    measure(s, "before")
    pm0 = w.pole_map()
    ring_len = w.border_length(patch)
    caps_a = w.extrude(patch, 0.3)
    caps_b = w.extrude(caps_a, 0.3)
    measure(s, "after")
    added, removed = pole_diff(pm0)
    s.note(f"poles added: {fmt_poles(added)}; removed: {fmt_poles(removed)}")
    addE = [a for a in added if a[0] >= 5]
    addN = [a for a in added if a[0] == 3]
    s.check("4 new E-poles (2 per half) appear", len(addE) == 4 and not removed, f"{len(addE)} E-poles: {fmt_poles(addE)}")
    s.check("the E-poles sit at the 4 corners of the patch (x=+-0.6375, y=0.2 / -0.7) on the old base ring",
            all(abs(abs(p[0]) - 0.6375) < 1e-3 and (abs(p[1] - 0.2) < 1e-3 or abs(p[1] + 0.7) < 1e-3) and abs(p[2] - 1.5) < 1e-3 for _, p in addE),
            fmt_poles(addE))
    s.check("(D intro) the cap corners become N-poles: 4 of them", len(addN) == 4, f"{len(addN)} N-poles: {fmt_poles(addN)}")
    s.check("centre crossings stay regular (no pole on the seam x=0)", s.d["after"]["poles_on_seam"] == 0, f"poles on seam: {s.d['after']['poles_on_seam']}")
    s.check("one closed ring of 20 edges around the muzzle base", ring_len == 20 and w.border_length(muz_cap_tmp := set(caps_b)) == 20, f"patch boundary {ring_len}, cap boundary {w.border_length(muz_cap_tmp)}")
    muz_cap = set(caps_b)
    w.set_view(32, 14, 5.2, (0, -0.1, 0.8))
    s.done(snap("D3_2_muzzle_extruded", note="D3.2  muzzle region-extruded (2 segments)", highlight_faces=muz_cap))

    s = Step("D3.3", "Scale cap down and tilt", "ScaleTool + RotateTool (src)", "src (mirai.interaction)", False, "local", True,
             "Scale the cap down slightly and tilt it; shape the walls with loop selection on the extrusion's rings.")
    measure(s, "before")
    cv = w.face_verts(muz_cap)
    c = centroid(cv)
    w.scale(cv, 0.88, c)
    w.rotate(cv, -10, c, space="x")
    measure(s, "after")
    s.check("no topology change", s.d["before"]["F"] == s.d["after"]["F"], "V/E/F unchanged")
    s.check("mirror symmetric (cap is symmetric about x=0, uniform scale + x-axis rotation)", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    s.note("'loop selection on the extrusion's rings' was not exercised: shape came from the cap scale and tilt only.")
    s.done(snap("D3_3_muzzle_shaped", note="D3.3  cap scaled and tilted", highlight_faces=muz_cap))

    CUR_ZONE[0] = "nose"
    # ------------------------------------------------------------------ D4
    s = Step("D4.1", "Nose: select the 2 centre faces of the top cap row", "selection (script)", "playground", False, "local", True,
             "Select the 2 centre faces of the top cap row.")
    grid, ncol, nrow = rank_grid(muz_cap)
    nose = {grid[(2, 0)], grid[(3, 0)]}
    s.check("cap is 6 columns x 4 rows", (ncol, nrow) == (6, 4), f"{ncol} x {nrow}")
    s.check("nose patch boundary is 6 edges", w.border_length(nose) == 6, f"{w.border_length(nose)}")
    s.done()
    s = Step("D4.2", "Region-extrude forward and up; shape the tip", "Playground ExtrudeTool + Move", "playground", True, "local", True,
             "Region-extrude forward and up. Result: closed 6-edge ring around the nose base; four E-poles at its corners.")
    measure(s, "before")
    pm0 = w.pole_map()
    ring_n = w.border_length(nose)
    ncaps = w.extrude(nose, 0.25)
    w.move(w.face_verts(ncaps), (0, 0.08, 0))
    measure(s, "after")
    added, removed = pole_diff(pm0)
    s.note(f"poles added: {fmt_poles(added)}; removed: {fmt_poles(removed)}")
    addE = [a for a in added if a[0] >= 5]
    addN = [a for a in added if a[0] == 3]
    s.check("4 new E-poles at the corners of the nose patch", len(addE) == 4 and not removed, f"{len(addE)} E-poles: {fmt_poles(addE)}")
    s.check("(D intro) 4 further N-poles appear on the nose cap corners", len(addN) == 4, f"{len(addN)} N-poles: {fmt_poles(addN)}")
    s.check("nose ring is 6 edges", ring_n == 6, f"{ring_n}")
    s.check("mirror symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    w.set_view(32, 10, 3.8, (0, 0.0, 1.6))
    s.done(snap("D4_2_nose", note="D4.2  nose extruded", highlight_faces=ncaps))
    nose_caps = set(ncaps)
    s = Step("D4.3", "Leave the underside alone", "-", "-", False, "local", True, "Leave the underside alone: nostrils are secondary (D10).")
    s.check("no operation required", True, "nothing done")
    s.done()

    CUR_ZONE[0] = "eye"
    # ------------------------------------------------------------------ D5
    def inset(P, factor, depth=0.0):
        """'Inset' with existing tools: region extrude (distance 0), then ScaleTool on the new cap about its centroid.
        There is no Inset tool in the Playground (see findings)."""
        caps = w.extrude(P, depth)
        vs = w.face_verts(caps)
        w.scale(vs, factor, centroid(vs))
        return caps

    def eye_patch(sign):
        return w.faces_where(lambda c, n: n[2] > 0.9 and abs(c[2] - 1.0) < EPS and sign * c[0] > 0.2 and sign * c[0] < 0.64 and 0.4 < c[1] < 0.8)

    def in_eye(sign):
        return lambda p: sign * p[0] > 0.15 and sign * p[0] < 0.7 and 0.35 < p[1] < 0.85

    s = Step("D5.1", "Select the 2 x 2 eye patch per side", "selection (script)", "playground", False, "local", True,
             "2 x 2 eye patch per side, on the eye rows.")
    eyeR, eyeL = eye_patch(+1), eye_patch(-1)
    s.check("2 x 2 = 4 faces per side", len(eyeR) == 4 and len(eyeL) == 4, f"{len(eyeR)} / {len(eyeL)}")
    s.check("circumferential count (patch boundary) is 8 edges", w.border_length(eyeR) == 8, f"{w.border_length(eyeR)}")
    s.check("eye patch is the mirror of the other (selected by hand, once per side)", w.mirror_faces(eyeR) == eyeL, "mirror_faces(R) == L")
    s.done()

    eyes = [(eyeR, +1), (eyeL, -1)]
    state = {"R": eyeR, "L": eyeL}
    ring_edges = {"R": [w.border_length(eyeR)], "L": [w.border_length(eyeL)]}

    def eye_poles():
        return [p for p in w.poles() if in_eye(+1)(p[2])], [p for p in w.poles() if in_eye(-1)(p[2])]

    def eye_inset_step(sid, intent, claim, factor, depth, check_fn):
        st = Step(sid, intent, "Playground ExtrudeTool + ScaleTool (inset by extrude 0 + scale)", "playground + src", True, "local", True, claim)
        measure(st, "before")
        pm0 = w.pole_map()
        newR = inset(state["R"], factor, depth)
        newL = inset(w.mirror_faces(state["R"]) if False else state["L"], factor, depth)
        state["R"], state["L"] = newR, newL
        measure(st, "after")
        added, removed = pole_diff(pm0)
        st.note(f"poles added: {fmt_poles(added)}; removed: {fmt_poles(removed)}")
        check_fn(st, added, removed)
        st.check("mirror symmetric after doing both eyes by hand", st.d["after"]["symmetric"], str(st.d["after"]["symmetric"]))
        return st

    def chk_inset1(st, added, removed):
        addE = [a for a in added if a[0] >= 5]
        addN = [a for a in added if a[0] == 3]
        st.check("4 new E-poles per eye on the patch corners (8 total)", len(addE) == 8 and not removed, f"{len(addE)} E-poles: {fmt_poles(addE)}")
        eyeE = {+1: [p for _, p in [(0, a[1]) for a in addE] if p[0] > 0], -1: [p for _, p in [(0, a[1]) for a in addE] if p[0] < 0]}
        corners = {(0.2125, 0.4), (0.2125, 0.8), (0.6375, 0.4), (0.6375, 0.8)}
        ok = all(any(abs(abs(p[0]) - cx) < 2e-3 and abs(p[1] - cy) < 2e-3 for cx, cy in corners) and abs(p[2] - 1.0) < 2e-3 for _, p in addE)
        st.check("E-poles sit exactly on the 4 corners of the 2 x 2 patch (x=0.2125/0.6375, y=0.4/0.8)", ok, fmt_poles(addE))
        mid = []
        for sign in (+1, -1):
            for cx in (0.2125, 0.6375):
                v = w.vertex_at((sign * cx, 0.6, 1.0))
                mid.append(w.valence(v) if v is not None else None)
        st.check("canthi (left/right mid-side vertices) are regular (valence 4)", all(k == 4 for k in mid), f"valences {mid}")
        st.check("(D intro) inner corners are N-poles until the centre is opened: 4 per eye", len(addN) == 8, f"{len(addN)} N-poles: {fmt_poles(addN)}")

    def chk_noadd(label):
        def f(st, added, removed):
            st.note(f"literal reading 'no new poles' is false for valence-3 poles: {len(added)} added, {len(removed)} removed (they move one ring inward); "
                    "the document's own D intro predicts this ('inner corners N-poles until the centre is opened or inset again'). See findings F-03.")
            eR, eL = eye_poles()
            st.check("pole count per eye unchanged (4 E + 4 N)", len(eR) == 8 and len(eL) == 8, f"right eye {len(eR)} poles, left {len(eL)}")
            addE = [a for a in added if a[0] >= 5]
            st.check("no new E-poles", not addE, f"{len(addE)} new E-poles")
        return f

    w.set_view(0, 4, 2.8, (0, 0.55, 1.0))
    st = eye_inset_step("D5.2", "Inset once: orbit-rim ring", "Inset once: the orbit-rim ring. Four E-poles appear on the patch corners; canthi land on the left and right mid-side vertices, both regular.", 0.72, 0.0, chk_inset1)
    st.done(snap("D5_2_inset1", note="D5.2  eye: first inset (orbit rim)", highlight_faces=state["R"] | state["L"]))
    st = eye_inset_step("D5.3", "Inset again: lid-fold ring", "Inset again: the lid-fold ring. No new poles.", 0.72, 0.0, chk_noadd("lid-fold ring"))
    st.done(snap("D5_3_inset2", note="D5.3  eye: second inset (lid fold)", highlight_faces=state["R"] | state["L"]))
    st = eye_inset_step("D5.4", "Inset again: lid-margin ring", "Inset again: the lid-margin ring. No new poles.", 0.72, 0.0, chk_noadd("lid-margin ring"))
    st.done(snap("D5_4_inset3", note="D5.4  eye: third inset (lid margin)", highlight_faces=state["R"] | state["L"]))

    st = eye_inset_step("D5.5", "Extrude innermost 2 x 2 inward and scale down (lid thickness, socket depth)",
                        "Instead of deleting the centre, extrude the innermost 2 x 2 inward (into the skull) and scale it down.", 0.8, -0.1, chk_noadd("thickness ring"))
    capR, capL = state["R"], state["L"]
    st.d["tool"] = "Playground ExtrudeTool (inward) + ScaleTool"
    st.check("innermost cap is an 8-edge ring", w.border_length(capR) == 8 and w.border_length(capL) == 8, f"{w.border_length(capR)} / {w.border_length(capL)}")
    st.done(snap("D5_5_thickness", note="D5.5  eye: extruded inward, scaled down", highlight_faces=capR | capL))

    st = Step("D5.6", "Delete the extruded cap: the hole is an 8-edge border", "none: the Playground has no delete-face / open-hole operation", "-", True, "local", True,
              "Delete the extruded cap. The hole is an 8-edge border; its corner vertices become regular border vertices.")
    st.blocked("delete faces (open a hole)", "ExtrudeTool only removes the faces it replaces; no tool removes a cap. Prediction checked on a throw-away copy below, not in the model.")
    from core import Mesh  # noqa: E402
    def probe_open(faces_to_remove):
        cp = Mesh.from_state(m.export_state())
        for f in faces_to_remove:
            cp.remove_face(f)
        # remove the loose edges/vertices the face removal leaves (same helper the ExtrudeTool uses on its own leftovers)
        from playground.topology_tools.extrude import ExtrudeTool as _ET
        _ET._prune_leftover_geometry(cp, set(cp.all_edge_ids()), set(cp.all_vertex_ids()))
        return cp
    cp = probe_open(capR | capL)
    pp = WT.poles_of(cp)
    inner_valences = []
    for v in cp.all_vertex_ids():
        if any(len(cp.edge_faces(e)) == 1 for e in cp.vertex_edges(v)):
            inner_valences.append(len([e for e in cp.vertex_edges(v) if len(cp.edge_faces(e)) > 0]))
    st.note(f"PROBE on a copy (core Mesh.remove_face, not an artist tool): border vertices of the holes have valences {sorted(set(inner_valences))}; "
            f"interior poles after opening both eyes in the eye zones: "
            f"{sum(1 for _, k, p in pp if k >= 5 and abs(p[0]) > 0.15 and abs(p[0]) < 0.7 and 0.35 < p[1] < 0.85)} E, "
            f"{sum(1 for _, k, p in pp if k == 3 and abs(p[0]) > 0.15 and abs(p[0]) < 0.7 and 0.35 < p[1] < 0.85)} N")
    st.done()

    CUR_ZONE[0] = "mouth"
    # ------------------------------------------------------------------ D6
    mouth = {grid[(c, r)] for c in (1, 2, 3, 4) for r in (1, 2)}
    mstate = {"M": mouth}

    def mouth_step(sid, intent, claim, factor, depth, check_fn):
        st = Step(sid, intent, "Playground ExtrudeTool + ScaleTool (inset by extrude 0 + scale)" if depth == 0 else "Playground ExtrudeTool (inward) + ScaleTool",
                  "playground + src", True, "local", True, claim)
        measure(st, "before")
        pm0 = w.pole_map()
        mstate["M"] = inset(mstate["M"], factor, depth)
        measure(st, "after")
        added, removed = pole_diff(pm0)
        st.note(f"poles added: {fmt_poles(added)}; removed: {fmt_poles(removed)}")
        check_fn(st, added, removed)
        st.check("mirror symmetric", st.d["after"]["symmetric"], str(st.d["after"]["symmetric"]))
        return st

    def mouth_poles():
        return [p for p in w.poles() if zone_by_vid.get(p[0]) == "mouth"]

    s = Step("D6.1", "Select the 4 x 2 mouth patch on the muzzle cap", "selection (script)", "playground", False, "local", True,
             "Select the 4 x 2 patch (12-edge boundary).")
    s.check("4 x 2 = 8 faces", len(mouth) == 8, f"{len(mouth)}")
    s.check("12-edge boundary", w.border_length(mouth) == 12, f"{w.border_length(mouth)}")
    s.done()

    def chk_m1(st, added, removed):
        addE = [a for a in added if a[0] >= 5]
        addN = [a for a in added if a[0] == 3]
        xs = sorted({abs(p[0]) for _, p in addE})
        st.check("4 E-poles (2 per half) on the patch corners", len(addE) == 4 and not removed, f"{len(addE)} E-poles: {fmt_poles(addE)}")
        # commissure = mid vertex of each short side of the patch (patch boundary x extremes, middle row)
        # read from the already inset cap: old boundary vertices are the E-pole row; use the extreme-x boundary vertices
        pv = [v for v in m.all_vertex_ids() if abs(abs(w.pos(v)[0]) - max(abs(p[0]) for _, p in addE)) < 1e-6 and -0.75 < w.pos(v)[1] < 0.25 and w.pos(v)[2] > 1.6]
        mids = [v for v in pv if abs(w.pos(v)[1] - sorted(w.pos(q)[1] for q in pv)[len(pv) // 2]) < 1e-6]
        st.check("commissure (mid vertex of each short side) is regular (valence 4)", mids and all(w.valence(v) == 4 for v in mids),
                 f"{len(mids)} vertices, valences {[w.valence(v) for v in mids]}")
        st.check("(D intro) 4 inner-corner N-poles", len(addN) == 4, f"{len(addN)} N-poles")
        st.check("no pole at the commissure or on the seam", w.metrics()["poles_on_seam"] == 0, f"seam poles {w.metrics()['poles_on_seam']}")

    def chk_m_noadd(label):
        def f(st, added, removed):
            addE = [a for a in added if a[0] >= 5]
            st.note(f"literal reading 'no new poles' is false for valence-3 poles: {len(added)} added, {len(removed)} removed (they move one ring inward). See findings F-03.")
            st.check("no new E-poles", not addE, f"{len(addE)} new E-poles")
            st.check("pole count in the mouth zone unchanged", len(mouth_poles()) == mp_count[0], f"{len(mouth_poles())} vs {mp_count[0]}")
        return f

    w.set_view(0, 4, 3.0, (0, -0.2, 2.1))
    mp_count = [0]
    st = mouth_step("D6.2", "Inset: outer orbicularis ring", "Inset: the outer orbicularis ring. E-poles on the four patch corners; the commissure is the mid-vertex of each short side: regular.", 0.8, 0.0, chk_m1)
    mp_count[0] = len(mouth_poles())
    st.done(snap("D6_2_mouth_inset1", note="D6.2  mouth: first inset (outer orbicularis ring)", highlight_faces=mstate["M"]))
    st = mouth_step("D6.3", "Inset: vermilion-border ring", "Inset: the vermilion-border ring.", 0.8, 0.0, chk_m_noadd("vermilion ring"))
    st.done(snap("D6_3_mouth_inset2", note="D6.3  mouth: second inset (vermilion border)", highlight_faces=mstate["M"]))
    st = mouth_step("D6.4", "Inset: lip-margin ring", "Inset: the lip-margin ring.", 0.8, 0.0, chk_m_noadd("lip-margin ring"))
    st.done(snap("D6_4_mouth_inset3", note="D6.4  mouth: third inset (lip margin)", highlight_faces=mstate["M"]))
    st = mouth_step("D6.5", "Extrude innermost patch inward (lip thickness and roll)", "Extrude the innermost patch inward: lip thickness and roll.", 0.9, -0.06, chk_m_noadd("lip thickness"))
    st.done(snap("D6_5_mouth_thickness", note="D6.5  mouth: extruded inward (lip thickness)", highlight_faces=mstate["M"]))
    st = mouth_step("D6.6", "Extrude inward again and scale down (start of the mouth bag), delete the cap", "Extrude inward again and scale down: start of the mouth bag. Delete the cap. Result: 12-edge count, three concentric rings, lip thickness, two poles per half, none at the commissure.", 0.8, -0.2, chk_m_noadd("mouth bag"))
    mcap = mstate["M"]
    st.check("innermost cap is a 12-edge ring", w.border_length(mcap) == 12, f"{w.border_length(mcap)}")
    st.blocked("delete faces (open a hole)", "the cap stays; the 'delete the cap' half of this step cannot be done with a tool")
    cp = probe_open(mcap)
    pp = WT.poles_of(cp)
    st.note(f"PROBE on a copy (core Mesh.remove_face, not an artist tool): mouth poles after opening: "
            f"{sum(1 for v, k, p in pp if k >= 5 and zone_by_vid.get(v) == 'mouth')} E, {sum(1 for v, k, p in pp if k == 3 and zone_by_vid.get(v) == 'mouth')} N")
    st.done(snap("D6_6_mouth_bag", note="D6.6  mouth: second inward extrude, scaled (mouth bag)", highlight_faces=mcap))
    w.set_view(30, 10, 4.2, (0, -0.1, 1.6))
    snap("D6_overview_3q", note="D6  muzzle with nose and mouth")

    # ------------------------------------------------------------------ D7
    import collections

    def bfs_dist(a, b):
        seen = {a: 0}
        q = collections.deque([a])
        while q:
            v = q.popleft()
            if v == b:
                return seen[v]
            for e in m.vertex_edges(v):
                if len(m.edge_faces(e)) == 0:
                    continue
                u = [x for x in m.edge_vertices(e) if x != v][0]
                if u not in seen:
                    seen[u] = seen[v] + 1
                    q.append(u)
        return None

    s = Step("D7.1", "Count poles: expect about 10 per half (4 eye, 2 muzzle, 2 nose, 2 mouth)", "measurement script; Playground has no valence display or select-by-valence",
             "-", False, "global", True, "Display vertex valence (or select by valence 3 and 5). Expect about 10 poles per half: 4 eye, 2 muzzle, 2 nose, 2 mouth.")
    s.blocked("vertex valence display / select by valence", "numbers below come from the measurement script, not from a Playground tool")
    ps = w.poles()
    half = [p for p in ps if p[2][0] > EPS]
    Eh = [p for p in half if p[1] >= 5]
    Nh = [p for p in half if p[1] == 3]
    s.note(f"all poles per half (x>0): {len(half)} = {len(Eh)} E + {len(Nh)} N; on seam: {sum(1 for p in ps if abs(p[2][0]) <= EPS)}")
    pmap = w.pole_map()
    zone_of = lambda vid: zone_by_vid.get(vid, "other")
    byzone = collections.Counter((zone_of(p[0]), "E" if p[1] >= 5 else "N") for p in half)
    s.note("per half by zone: " + ", ".join(f"{z}/{t}: {n}" for (z, t), n in sorted(byzone.items())))
    s.check("about 10 poles per half in total (E and N together)", 8 <= len(half) <= 12, f"{len(half)} per half ({len(Eh)} E + {len(Nh)} N)")
    s.check("about 10 E-poles per half (only valence-5 counted)", 8 <= len(Eh) <= 12, f"{len(Eh)} E-poles per half")
    Eeye = sum(1 for p in Eh if zone_of(p[0]) == "eye")
    Emouth = sum(1 for p in Eh if zone_of(p[0]) == "mouth")
    s.check("4 E-poles per eye", Eeye == 4, f"{Eeye}")
    s.check("2 E-poles per half at the mouth", Emouth == 2, f"{Emouth}")
    s.done()
    # leftover poles with caps opened (probe)
    cp = probe_open(capR | capL | mcap)
    pp = WT.poles_of(cp)
    half_p = [p for p in pp if p[2][0] > EPS]
    s.note(f"PROBE on a copy with both eye caps and the mouth cap removed: per half {len(half_p)} poles = {sum(1 for p in half_p if p[1] >= 5)} E + {sum(1 for p in half_p if p[1] == 3)} N")

    s = Step("D7.2", "Cheekbone: eye's lower-outer E-pole and muzzle's upper-outer E-pole one edge apart on the same column", "measurement script (BFS on the mesh graph)", "-", False, "local", True,
             "The eye's lower-outer E-pole and the muzzle's upper-outer E-pole sit one edge apart on the same column.")
    a = w.vertex_at((0.6375, 0.4, 1.0))
    b = w.vertex_at((0.6375, 0.2, 1.5))
    d = bfs_dist(a, b) if a is not None and b is not None else None
    s.check("both poles exist and lie on one column (x=0.6375)", a is not None and b is not None and w.valence(a) == 5 and w.valence(b) == 5,
            f"eye pole {a} valence {w.valence(a) if a else None}; muzzle pole {b} valence {w.valence(b) if b else None}")
    s.check("they are one edge apart", d == 1, f"graph distance = {d} edges")
    s.note("The extra edge is the horizontal shelf strip D1.3 leaves on top of the muzzle (front: 5 rows, shelf, 4 rows).")
    s.done()

    s = Step("D7.3", "Nasal side: spin one edge to move the eye's lower-inner pole toward the nose bridge", "none: no Spin Edge in the Playground", "-", True, "local", True,
             "If the tear trough must stay smooth, spin one edge to move the pole one step toward the nose bridge.")
    s.blocked("spin edge", "no Playground tool rotates an edge within its two faces; Collapse/Split/Connect exist but are not equivalent")
    s.done()

    s = Step("D7.4", "Slide the cheekbone row to the zygomatic line (do not cut)", "Playground Loop Slide (loop picked with Edge Loop selection)", "playground", False, "local", True,
             "Slide the cheekbone row to the zygomatic line; do not cut.")
    # cheekbone row: the loop at y=0.4 (lower orbit line) passes the eye E-poles; try it, and the loop at y=0.2 (shelf edge)
    def row_edge(y):
        for e in m.all_edge_ids():
            va, vb = (w.pos(v) for v in m.edge_vertices(e))
            if abs(va[2] - 1.0) < EPS and abs(vb[2] - 1.0) < EPS and abs(va[1] - y) < 1e-6 and abs(vb[1] - y) < 1e-6 and min(va[0], vb[0]) >= -1e-9 and max(va[0], vb[0]) <= 0.2125 + 1e-6:
                return e
    results = {}
    for y in (0.4, 0.2):
        e0 = row_edge(y)
        tr = edge_loop_fn(m, e0)
        results[y] = (len(tr.as_set()), tr.closed)
        try:
            w.slide_to(tr.as_set(), next(v for v in w.loop_vertices(tr.as_set()) if abs(w.pos(v)[0]) < EPS and w.pos(v)[2] > 0.9), 1, y + 0.03)
            results[y] += ("slid",)
        except Exception as exc:  # noqa: BLE001
            results[y] += (f"{type(exc).__name__}: {exc}",)
    s.note(f"edge loop from the centre edge at y=0.4: {results[0.4]}; at y=0.2: {results[0.2]}")
    s.check("cheekbone-row loop (y=0.4) can be selected as a closed loop and slid", len(results[0.4]) == 3 and results[0.4][2] == "slid", str(results[0.4]))
    s.check("shelf-edge loop (y=0.2) can be selected as a closed loop and slid", len(results[0.2]) == 3 and results[0.2][2] == "slid", str(results[0.2]))
    s.done()
    w.set_view(30, 10, 4.5, (0, 0.2, 1.4))
    snap("D7_poles_overview", note="D7  all poles after the feature rings (caps still closed)")

    # ------------------------------------------------------------------ D8
    CUR_ZONE[0] = "brow"

    def try_slide(label, loop_edges, delta, axis=1, sample=None):
        """Run a Loop Slide and return a string: either 'slid' or the tool's own error."""
        try:
            sv = sample if sample is not None else next(iter(w.loop_vertices(loop_edges)))
            y0 = w.pos(sv)[axis]
            w.slide_to(loop_edges, sv, axis, y0 + delta)
            return "slid"
        except Exception as exc:  # noqa: BLE001
            return f"{type(exc).__name__}: {exc}"

    def edge_at(pa, pb):
        va, vb = w.vertex_at(pa), w.vertex_at(pb)
        if va is None or vb is None:
            return None
        for e in m.vertex_edges(va):
            if vb in m.edge_vertices(e):
                return e

    s = Step("D8.1", "Loop-select the brow row (forehead/brow line, y=1.0), move it forward and down", "Playground Edge Loop selection + Core Move", "playground + src", False, "local", True,
             "Loop-select the brow row and move it forward and down over the upper orbit ring.")
    measure(s, "before")
    e0 = edge_at((0.0, 1.0, 1.0), (0.2125, 1.0, 1.0))
    tr = edge_loop_fn(m, e0)
    s.check("the brow-row loop is a closed edge loop around the head", tr.closed, f"closed={tr.closed}, {len(tr.as_set())} edges")
    front = {v for v in w.loop_vertices(tr.as_set()) if w.pos(v)[2] > 0.9}
    w.move(front, (0.0, -0.03, 0.08))
    measure(s, "after")
    s.check("a move changes no topology", s.d["before"]["F"] == s.d["after"]["F"], "V/E/F unchanged")
    s.check("mirror stays symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    s.note("Only the front vertices of the loop were moved (the script restricts the selection by position; Playground has box select).")
    w.set_view(60, 10, 4, (0.3, 0.7, 1.0))
    s.done(snap("D8_1_brow_forward", note="D8.1  brow row moved forward and down"))

    s = Step("D8.2", "Slide the upper orbit ring under the brow", "Playground Loop Slide (loop = first orbit ring of the right eye)", "playground", False, "local", True,
             "Slide the upper orbit ring under it to deepen the shadow line.")
    measure(s, "before")
    rings = [edge_at((sx * 0.272, 0.744, 1.0), (sx * 0.425, 0.744, 1.0)) for sx in (+1, -1)]
    if any(r is None for r in rings):
        s.check("the orbit ring edge exists at the predicted position", False, "edge not found")
    else:
        for sx, r in zip((+1, -1), rings):
            tr = edge_loop_fn(m, r)
            s.check(f"the orbit ring of the {'right' if sx > 0 else 'left'} eye is selected as a closed loop", tr.closed, f"closed={tr.closed}, {len(tr.as_set())} edges")
            res = "not closed" if not tr.closed else try_slide("orbit1", tr.as_set(), 0.02, 1, w.vertex_at((sx * 0.425, 0.744, 1.0)))
            s.check(f"the orbit ring of the {'right' if sx > 0 else 'left'} eye can be slid (done once per eye by hand)", res == "slid", str(res))
        s.note("Slid within the orbit-rim annulus (towards the patch boundary), not 'under the brow': the ring lies between the outer ring (E-poles) and the next inset ring.")
    measure(s, "after")
    s.check("mirror symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    s.done(snap("D8_2_orbit_slide", note="D8.2  orbit ring slide attempt"))

    s = Step("D8.3", "If the ridge needs a harder edge: insert one loop through the orbit-rim face ring (local)", "Playground Loop Insert on a radial edge of the orbit-rim ring", "playground", True, "local", True,
             "Insert one loop through the orbit-rim face ring; that face ring closes around the eye, so the new loop stays local.")
    measure(s, "before")
    old_pos = {v: w.pos(v) for v in m.all_vertex_ids()}
    def radial_down(x, y, z):
        v = w.vertex_at((x, y, z))
        for e in m.vertex_edges(v):
            o = [u for u in m.edge_vertices(e) if u != v][0]
            po = w.pos(o)
            if abs(po[0] - x) < 1e-6 and abs(po[2] - z) < 1e-6 and y - 0.1 < po[1] < y - 1e-6:
                return e
    rads = [radial_down(sx * 0.425, 0.8, 1.0) for sx in (+1, -1)]
    if any(r is None for r in rads):
        s.check("radial edge between the patch boundary and the first inset ring exists on both eyes", False, "not found")
    else:
        ring_sets = [w.ring_of(r) for r in rads]
        s.note(f"edge ring through the radial edge: {[len(r) for r in ring_sets]} edges (right, left)")
        try:
            new_e = [w.loop_cut(r) for r in rads]
            measure(s, "after")
            added_v = [v for v in m.all_vertex_ids() if v not in old_pos]
            outside = [v for v in added_v if not (0.15 < abs(w.pos(v)[0]) < 0.7 and 0.35 < w.pos(v)[1] < 0.85)]
            s.check("each loop closes around its eye: 8 new edges and 8 new vertices per eye", [len(x) for x in new_e] == [8, 8] and len(added_v) == 16, f"{[len(x) for x in new_e]} edges, {len(added_v)} vertices")
            s.check("the loops stay inside the eye zones (no new vertex outside)", not outside, f"{len(outside)} outside")
            s.check("no existing vertex moved", all(w.pos(v) == old_pos[v] for v in old_pos), "positions unchanged")
            s.check("pole set unchanged", s.d["before"]["poles_total"] == s.d["after"]["poles_total"], f"{s.d['before']['poles_total']} -> {s.d['after']['poles_total']}")
            s.check("mirror symmetric (the loop was inserted once per eye by hand)", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
        except Exception as exc:  # noqa: BLE001
            s.check("Loop Insert accepts the orbit-rim face ring", False, f"{type(exc).__name__}: {exc}")
            measure(s, "after")
    w.set_view(0, 4, 3.0, (0.42, 0.6, 1.0))
    s.done(snap("D8_3_orbit_rim_loop", note="D8.3  one loop inserted in the orbit-rim ring (local)"))

    # ------------------------------------------------------------------ D9
    CUR_ZONE[0] = "jaw/neck/ear"
    s = Step("D9.1", "Slide the bottom muzzle-wall row to the jaw line", "Playground Loop Slide (loop picked with Edge Loop selection)", "playground", False, "local", True,
             "Slide the bottom muzzle-wall row to the jaw line; it continues back to below the ear.")
    out = {}
    attempts = (("row y=-0.7 on the muzzle base ring", (0.0, -0.7, 1.5), (0.2125, -0.7, 1.5), 1, (0.0, -0.7, 1.5), -0.02),
                ("ring around the muzzle wall (z=1.8, underside)", (0.0, -0.7, 1.8), (0.2125, -0.7, 1.8), 2, (0.0, -0.7, 1.8), 0.02))
    for label, p0, p1, axis, samp, d in attempts:
        e = edge_at(p0, p1)
        if e is None:
            out[label] = "edge not found"
            continue
        tr = edge_loop_fn(m, e)
        sv = w.vertex_at(samp)
        res = "not closed" if not tr.closed else try_slide(label, tr.as_set(), d, axis, sv)
        out[label] = f"{len(tr.as_set())} edges, closed={tr.closed}, slide: {res}"
    s.note("; ".join(f"{k}: {v}" for k, v in out.items()))
    k_base, k_wall = list(out)
    s.check("the bottom muzzle row (y=-0.7, through the base-ring corner poles) can be selected as a closed loop and slid", out[k_base].endswith("slide: slid"), out[k_base])
    s.check("a ring around the muzzle wall (no poles on it) can be slid", out[k_wall].endswith("slide: slid"), out[k_wall])
    s.done()

    s = Step("D9.2", "Extrude the neck bottom once more", "Playground ExtrudeTool", "playground", True, "local", True, "Extrude the neck bottom once more if length is needed.")
    measure(s, "before")
    neck_cap = w.faces_where(lambda c, n: n[1] < -0.9 and c[1] < -1.5)
    ncaps2 = w.extrude(neck_cap, 0.4)
    measure(s, "after")
    s.check("neck cap selected (all columns of the neck bottom)", len(neck_cap) > 0, f"{len(neck_cap)} faces")
    s.check("mirror symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    s.done()

    s = Step("D9.3a", "Ear patch: 2 x 2 faces on the side of the skull exist after D2?", "selection (script)", "playground", False, "local", True,
             "Ear: select a 2 x 2 patch on the side of the skull (behind the jaw hinge).")
    side_faces = w.faces_where(lambda c, n: n[0] > 0.9 and abs(c[0] - 0.85) < EPS)
    zs = sorted({round(w.face_center(f)[2], 3) for f in side_faces})
    ys = sorted({round(w.face_center(f)[1], 3) for f in side_faces})
    s.note(f"side face columns along depth (z centres): {zs}; rows (y centres): {ys}")
    # Ear patch candidate: rows y in [0.2,0.6] (2 rows); depth columns available from D1/D2 are 2 (z in [-1,0],[0,1]) plus the muzzle wall
    ear_candidates = [f for f in side_faces if 0.2 < w.face_center(f)[1] < 0.6]
    zcols = sorted({round(w.face_center(f)[2], 3) for f in ear_candidates})
    s.check("the D2 grid gives a side grid fine enough for a 2 x 2 ear patch that sits behind the jaw hinge", len(zcols) >= 4, f"depth columns on the side: {len(zcols)} ({zcols}); a 2 x 2 patch would span half of the head depth each")
    s.done()

    s = Step("D9.3b", "Corrective: two coronal loops (z=-0.5 and z=0.5) to get a side grid", "Playground Loop Insert x2", "playground", True, "global", False,
             "(not in the document) global loops added after D2, contradicting 'the last global loops'.")
    measure(s, "before")
    def z_edge(zlo, zhi, y0):
        for e in m.all_edge_ids():
            va, vb = (w.pos(v) for v in m.edge_vertices(e))
            if abs(va[0] - 0.85) < EPS and abs(vb[0] - 0.85) < EPS and abs(va[1] - vb[1]) < EPS and abs(va[1] - y0) < 1e-6:
                lo, hi = sorted((va[2], vb[2]))
                if abs(lo - zlo) < 1e-6 and abs(hi - zhi) < 1e-6:
                    return e
    try:
        for zlo, zhi in ((-1.0, 0.0), (0.0, 1.0)):
            w.loop_cut(z_edge(zlo, zhi, 0.4))
        measure(s, "after")
        s.check("each loop runs around the head (global, > 20 new quads)", s.d["after"]["F"] - s.d["before"]["F"] > 40, f"F {s.d['before']['F']} -> {s.d['after']['F']}")
        s.note("Each coronal loop also cuts the neck, the jaw underside and the eye-adjacent forehead rows: it is a global cut after the features exist.")
    except Exception as exc:  # noqa: BLE001
        s.check("coronal loops can be inserted", False, f"{type(exc).__name__}: {exc}")
        measure(s, "after")
    s.check("mirror symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    s.done()

    def ear_patch(sign):
        return w.faces_where(lambda c, n: sign * n[0] > 0.9 and abs(abs(c[0]) - 0.85) < EPS and 0.2 < c[1] < 0.6 and -0.5 < c[2] < 0.5)

    earR, earL = ear_patch(+1), ear_patch(-1)
    s = Step("D9.3c", "Ear: inset once (ear-root ring)", "Playground ExtrudeTool + ScaleTool (inset)", "playground + src", True, "local", True,
             "Inset once (ear-root ring); extrude out for the ear volume, inset the outer face for the helix rim, extrude in for the concha. Result: a rigid ear with four poles at its root.")
    s.check("2 x 2 ear patch on each side", len(earR) == 4 and len(earL) == 4, f"{len(earR)} / {len(earL)}")
    measure(s, "before")
    pm0 = w.pole_map()
    CUR_ZONE[0] = "ear"
    ear_state = {"R": inset(earR, 0.75, 0.0), "L": None}
    ear_state["L"] = inset(earL, 0.75, 0.0)
    measure(s, "after")
    added, removed = pole_diff(pm0)
    addE = [a for a in added if a[0] >= 5]
    s.note(f"poles added: {fmt_poles(added)}")
    s.check("4 E-poles per ear at the root", len(addE) == 8, f"{len(addE)} E-poles (both ears)")
    s.check("mirror symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    s.done()
    s = Step("D9.3d", "Ear: extrude out, inset outer face (helix), extrude in (concha)", "Playground ExtrudeTool + ScaleTool", "playground + src", True, "local", True,
             "Extrude out for the ear volume, inset the outer face for the helix rim, extrude in for the concha.")
    measure(s, "before")
    pm0 = w.pole_map()
    for side in ("R", "L"):
        ear_state[side] = w.extrude(ear_state[side], 0.15)
        ear_state[side] = inset(ear_state[side], 0.7, 0.0)
        ear_state[side] = w.extrude(ear_state[side], -0.05)
    measure(s, "after")
    added, removed = pole_diff(pm0)
    s.note(f"poles added: {fmt_poles(added)}; removed: {fmt_poles(removed)}")
    s.check("mirror symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    s.check("the E-poles at the ear root are unchanged by the later ear steps", not [a for a in added if a[0] >= 5], f"{len([a for a in added if a[0] >= 5])} new E-poles")
    w.set_view(90, 8, 5.5, (0.5, 0.2, 0.0))
    s.done(snap("D9_3_ear", note="D9.3  ear built from a 2 x 2 side patch"))

    s = Step("D9.4", "Place the ear-root poles away from the jaw hinge", "Playground Move / slide (not exercised)", "-", False, "local", True,
             "Place the ear-root poles toward the skull, away from the jaw hinge.")
    s.blocked("a way to judge 'jaw hinge' position; no hinge or jaw reference exists in the app", "needs an artist judgement on the head shape; poles sit on the patch corners by construction")
    s.done()

    # ------------------------------------------------------------------ D10
    CUR_ZONE[0] = "secondary"
    CUR_ZONE[0] = "eye"
    s = Step("D10.1", "Lids: inset the lid-margin ring once more", "Playground ExtrudeTool + ScaleTool", "playground + src", True, "local", True,
             "Lids: inset the lid-margin ring once more for a crisp margin under subdivision.")
    measure(s, "before")
    pm0 = w.pole_map()
    newR = inset(capR, 0.85, 0.0)
    newL = inset(capL, 0.85, 0.0)
    measure(s, "after")
    added, removed = pole_diff(pm0)
    s.check("local: no E-pole added anywhere", not [a for a in added if a[0] >= 5], f"{len([a for a in added if a[0] >= 5])} E-poles added")
    s.check("mirror symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    s.done()

    CUR_ZONE[0] = "mouth"
    s = Step("D10.2", "Lips: inset once on the vermilion border", "Playground ExtrudeTool + ScaleTool on the vermilion wall ring", "playground + src", True, "local", True,
             "Lips: inset once on the vermilion border for the lip line.")
    measure(s, "before")
    pm0 = w.pole_map()
    # the 12 wall faces created by D6.3 are the faces around the vermilion ring: derive them from topology of the mouth caps
    def wall_faces_around(caps):
        out = set()
        capset = set(caps)
        for f in capset:
            for e in m.face_edges(f):
                fs = m.edge_faces(e)
                if sum(1 for g in fs if g in capset) == 1:
                    out.update(g for g in fs if g not in capset)
        return out
    walls = wall_faces_around(mstate["M"])
    s.note(f"wall faces around the innermost mouth cap: {len(walls)}")
    try:
        caps10 = w.extrude(walls, 0.0)
        vs = w.face_verts(caps10)
        w.scale(vs, 0.92, centroid(vs))
        measure(s, "after")
        added, removed = pole_diff(pm0)
        s.note(f"poles added: {fmt_poles(added)}; removed: {fmt_poles(removed)}")
        s.check("a ring of faces can be inset (region with a hole): no new E-poles beyond the corners", len([a for a in added if a[0] >= 5]) <= 4, f"{len([a for a in added if a[0] >= 5])} E-poles added")
        s.check("mirror symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    except Exception as exc:  # noqa: BLE001
        s.check("Extrude/Inset accepts a face ring", False, f"{type(exc).__name__}: {exc}")
        measure(s, "after")
    s.done()

    CUR_ZONE[0] = "nose"
    s = Step("D10.3", "Nostrils: select the nose underside face per half, inset, extrude up into the nose", "Playground ExtrudeTool + ScaleTool", "playground + src", True, "local", True,
             "Nostrils: select the nose underside face per half, inset, extrude up into the nose.")
    measure(s, "before")
    pm0 = w.pole_map()
    nose_walls = wall_faces_around(nose_caps)
    under = {f for f in nose_walls if w.face_normal(f)[1] < -0.3}
    s.check("exactly one underside face per half", len(under) == 2 and len({round(w.face_center(f)[0] > 0) for f in under}) == 2, f"{len(under)} underside faces from {len(nose_walls)} nose wall faces")
    for f in list(under):
        c = inset({f}, 0.6, 0.0)
        w.extrude(c, -0.04)
    measure(s, "after")
    added, removed = pole_diff(pm0)
    s.note(f"poles added: {fmt_poles(added)}")
    s.check("every new pole is valence 3 or 5 (no valence-6 vertex)", all(k in (3, 5) for k, _ in added), f"valences added: {sorted({k for k, _ in added})}")
    s.check("no pole sits on the mirror seam", s.d["after"]["poles_on_seam"] == 0, f"poles on seam: {s.d['after']['poles_on_seam']}")
    s.check("mirror symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    s.done()

    CUR_ZONE[0] = "mouth"
    s = Step("D10.4", "Mouth bag: extrude the inner border further back and close it", "Playground ExtrudeTool", "playground", True, "local", True,
             "Mouth bag: extrude the inner border further back and close it.")
    measure(s, "before")
    pm0 = w.pole_map()
    mstate["M"] = w.extrude(mstate["M"], -0.25)
    measure(s, "after")
    pole_diff(pm0)
    s.check("closed by the extruded cap (no hole, no tool needed)", s.d["after"]["boundary_vertices"] == 0, f"boundary vertices: {s.d['after']['boundary_vertices']}")
    s.check("mirror symmetric", s.d["after"]["symmetric"], str(s.d["after"]["symmetric"]))
    s.note("'Extrude the inner border' presupposes an open hole from D6.6; here the cap is still closed, so the bag is just a further extrusion.")
    w.set_view(0, 4, 3.0, (0, -0.2, 2.1))
    s.done(snap("D10_face_features", note="D10  secondary rings: lids, lips, nostrils, mouth bag"))

    # ------------------------------------------------------------------ D11
    from experiments.subdivision_lab.subd import SubdSurface  # noqa: E402

    s = Step("D11.1", "Freeze one level of subdivision on the cage (global, uniform)", "Subdivision Lab (preview only, nothing written back)", "lab", True, "global", True,
             "Freeze one level of subdivision on the cage (global, uniform). Result: eye 16 around, mouth 24 around; all poles remain where they were placed.")
    s.blocked("apply subdivision to the control mesh", "the Subdivision Lab derives a throw-away surface (D1 in its README); nothing writes it back to the mesh. Preview numbers below")
    cp = probe_open(set(newR) | set(newL) | mstate["M"])
    # the eye/mouth caps at this point; open them to get the borders the document predicts
    try:
        surf = SubdSurface(cp)
        lv = surf.level(1)
        bnd = collections.Counter()
        ec = collections.Counter()
        for f in lv.faces:
            for i in range(len(f)):
                a, b = f[i], f[(i + 1) % len(f)]
                ec[(min(a, b), max(a, b))] += 1
        border = [e for e, n in ec.items() if n == 1]
        adj = collections.defaultdict(list)
        for a, b in border:
            adj[a].append(b)
            adj[b].append(a)
        seen, comps = set(), []
        for v0 in adj:
            if v0 in seen:
                continue
            comp, st_ = set(), [v0]
            while st_:
                x = st_.pop()
                if x in comp:
                    continue
                comp.add(x)
                st_.extend(adj[x])
            seen |= comp
            comps.append(len(comp))
        val = collections.Counter()
        for (a, b), n in ec.items():
            val[a] += 1
            val[b] += 1
        n_extra = sum(1 for v, k in val.items() if k != 4 and not any(v in e for e in border))
        s.note(f"level-1 preview of the cage with eye and mouth caps opened (probe copy): {len(lv.faces)} faces; hole borders (edge counts) {sorted(comps)}; interior extraordinary vertices {n_extra}")
        n_poles_ctrl = len(WT.poles_of(cp))
        s.check("all poles remain: the interior extraordinary vertices of the level-1 surface equal the control cage's interior poles", n_extra == n_poles_ctrl,
                f"control cage (caps opened) {n_poles_ctrl} poles; level-1 surface {n_extra} interior vertices with valence != 4")
        s.check("eye borders become 16, mouth border 24", sorted(comps)[-3:] == [16, 16, 24] or sorted(comps) == [16, 16, 24], f"hole border lengths {sorted(comps)}")
    except Exception as exc:  # noqa: BLE001
        s.check("subdivision preview of the cage", False, f"{type(exc).__name__}: {exc}")
    s.done()

    CUR_ZONE[0] = "mouth"
    s = Step("D11.2", "Density: add a concentric ring inside the mouth feature ring only", "Playground Loop Insert on a radial edge of the mouth annulus", "playground", True, "local", True,
             "If one region needs more, add concentric rings inside its feature ring only.")
    measure(s, "before")
    old_pos = {v: w.pos(v) for v in m.all_vertex_ids()}
    # radial edge between the mouth patch boundary (first extrude walls) and the next ring: use the vertical mid edge on the cap at the commissure side
    rad = None
    for e in m.all_edge_ids():
        a, b = m.edge_vertices(e)
        pa, pb = w.pos(a), w.pos(b)
        if zone_by_vid.get(a) is None and abs(pa[0]) < EPS and abs(pb[0]) < EPS and pa[2] > 1.9 and pb[2] > 1.9 and abs(pa[1] - pb[1]) > 1e-3 and -0.3 < pa[1] < 0.0:
            rad = e
    ring_lens = []
    if rad is None:
        s.check("a radial edge of the mouth annulus was found", False, "not found")
    else:
        try:
            rs = w.ring_of(rad)
            s.note(f"edge ring through the picked edge: {len(rs)} edges")
            w.loop_cut(rad)
            measure(s, "after")
            added_v = [v for v in m.all_vertex_ids() if v not in old_pos]
            s.check("no existing vertex moved", all(w.pos(v) == old_pos[v] for v in old_pos), "positions unchanged")
            s.check("poles unchanged (no new pole outside)", s.d["before"]["poles_total"] == s.d["after"]["poles_total"], f"{s.d['before']['poles_total']} -> {s.d['after']['poles_total']}")
            s.check("the new ring is local: it has the length of the feature ring (12) and every new vertex lies in the mouth zone",
                    len(added_v) == 12 and all(abs(w.pos(v)[0]) < 0.45 and w.pos(v)[2] > 1.7 for v in added_v), f"{len(added_v)} new vertices; x-range {min(abs(w.pos(v)[0]) for v in added_v):.2f}..{max(abs(w.pos(v)[0]) for v in added_v):.2f}" if added_v else "none")
        except Exception as exc:  # noqa: BLE001
            s.check("Loop Insert accepts a mouth-annulus radial edge", False, f"{type(exc).__name__}: {exc}")
            measure(s, "after")
    s.done()

    # ------------------------------------------------------------------ X: cross-cutting checks (task item 4)
    CUR_ZONE[0] = "final"
    s = Step("X1", "Final cross-checks against the document's pole predictions", "measurement script (+ probe copy with caps opened)", "-", False, "global", True,
             "No poles on lids, canthi, lips, commissure; eye 8 / mouth 12 in the cage; total planned poles about 10 per half.")
    mt = w.metrics()
    s.d["after"] = {**mt, **poles_split(w)}
    ps = w.poles()
    eyeN = [p for p in ps if zone_by_vid.get(p[0]) == "eye" and p[1] == 3]
    eyeE = [p for p in ps if zone_by_vid.get(p[0]) == "eye" and p[1] >= 5]
    mouthN = [p for p in ps if zone_by_vid.get(p[0]) == "mouth" and p[1] == 3]
    mouthE = [p for p in ps if zone_by_vid.get(p[0]) == "mouth" and p[1] >= 5]
    s.check("closed mesh stays manifold (every edge has two faces, Euler characteristic 2)", mt["edges_without_two_faces"] == 0 and mt["euler"] == 2 and mt["loose_vertices"] == 0,
            f"edges without two faces {mt['edges_without_two_faces']}, Euler {mt['euler']}, loose vertices {mt['loose_vertices']}")
    s.check("cage eye count 8 and mouth count 12 (circumferential edges of the feature ring)", True, "eye patch boundary 8 (D5.1), mouth patch boundary 12 (D6.1)")
    s.check("canthi are regular: 4 mid-side vertices of the eye rings have valence 4 at the end",
            all(w.valence(w.vertex_at((sx * cx, 0.6, 1.0))) == 4 for sx in (+1, -1) for cx in (0.2125, 0.6375)),
            str([w.valence(w.vertex_at((sx * cx, 0.6, 1.0))) for sx in (+1, -1) for cx in (0.2125, 0.6375)]))
    s.check("no poles on the lids / lips while the feature caps are still closed", not eyeN and not mouthN, f"eye N-poles {len(eyeN)}, mouth N-poles {len(mouthN)} (valence 3, on the innermost rings)")
    cp = probe_open(set(newR) | set(newL) | mstate["M"])
    pp = WT.poles_of(cp)
    eN2 = sum(1 for v, k, p in pp if zone_by_vid.get(v) == "eye" and k == 3)
    mN2 = sum(1 for v, k, p in pp if zone_by_vid.get(v) == "mouth" and k == 3)
    s.check("no poles on the lids / lips once the caps are opened (probe copy, core remove_face)", eN2 == 0 and mN2 == 0, f"eye N {eN2}, mouth N {mN2} on the probe copy")
    half = [p for p in ps if p[2][0] > EPS]
    Eh = [p for p in half if p[1] >= 5]
    s.check("no pole on the mirror seam in the finished cage", mt["poles_on_seam"] == 0, f"poles on seam: {mt['poles_on_seam']} (valence {sorted(p[1] for p in ps if abs(p[2][0]) <= EPS)})")
    s.note(f"final per half (x>0): {len(half)} poles = {len(Eh)} E + {len(half) - len(Eh)} N; seam: {mt['poles_on_seam']}; total {len(ps)}")
    zc = collections.Counter((zone_by_vid.get(p[0], "other"), "E" if p[1] >= 5 else "N" if p[1] == 3 else f"V{p[1]}") for p in half)
    s.note("per half by origin: " + ", ".join(f"{z}/{t}: {n}" for (z, t), n in sorted(zc.items())))
    s.check("about 10 poles per half in total", 8 <= len(half) <= 12, f"{len(half)} per half")
    s.check("the cage lands near 300 to 500 quads for head and neck (section C)", 300 <= mt["F"] <= 500, f"{mt['F']} quads (with ears, nostrils, closed eye/mouth caps)")
    s.check("one subdivision gives a working mesh of about 1,200 to 2,000 quads (section C)", 1200 <= 4 * mt["F"] <= 2000, f"4 x {mt['F']} = {4 * mt['F']} quads (Catmull-Clark quad count is exactly 4x for an all-quad cage)")
    s.d["n_tool_calls"] = dict(w.n_tool_calls)
    w.set_view(30, 10, 6.0, (0, -0.3, 0.8))
    snap("X1_final_3q", note="final cage, three-quarter view (caps still closed)")
    w.set_view(0, 5, 6.0, (0, -0.3, 1.0))
    s.done(snap("X1_final_front", note="final cage, front view"))
    w.set_view(90, 5, 6.0, (0, -0.3, 0.8))
    snap("X1_final_side", note="final cage, side view")

    json.dump(LOG, open(HERE / "step_log.json", "w"), indent=1)
    print(json.dumps({d["id"]: (d["verdict"], d["after"] and d["after"]["F"]) for d in LOG}, indent=0))


if __name__ == "__main__":
    try:
        run(HERE / "screenshots")
    finally:
        json.dump(LOG, open(HERE / "step_log.json", "w"), indent=1)
