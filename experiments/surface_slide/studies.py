"""Studies that need more than one run of a scenario: mesh density, repeated gestures, path dependence, symmetry,
soft-selection weights, cursor fidelity. Writes `results/studies.json`.

    python experiments/surface_slide/studies.py [density erosion drift symmetry weights cursor]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402

from surface_slide import algorithms as A  # noqa: E402
from surface_slide import geometries as G  # noqa: E402
from surface_slide import harness as H  # noqa: E402
from surface_slide import metrics as M  # noqa: E402
from surface_slide import scenarios as S  # noqa: E402
from surface_slide.fields import EdgeGraph, mirror, mirror_partners, soft_weights, transport_frames  # noqa: E402
from surface_slide.refsurf import RefSurface  # noqa: E402

RESULTS = HERE / "results"
_I = np.intp


# --- S1: mesh density on the sphere -------------------------------------------------------------------------------------

def density() -> dict:
    """Flat facets against Phong evaluation, against the analytic sphere, over five mesh densities."""
    rows = []
    for n in (4, 8, 16, 32, 64):
        geo = G.cube_sphere(n)
        ref = H.build_ref(geo.V, geo.faces)
        h = ref.mean_edge
        v = S.nearest_vertex(ref, (0.0, 0.0, 1.0))
        graph = EdgeGraph(ref.nv, ref.edges, ref.V)
        verts = np.array(sorted(graph.dijkstra([v], 3.5 * h)[0]), dtype=_I)
        pivot = int(np.flatnonzero(verts == v)[0])
        setup = A.SlideSetup.from_vertices(ref, verts, None, pivot, transport_frames(ref, graph, v, verts))
        n0 = setup.n0[pivot]
        e1 = np.cross(n0, [0.0, 1.0, 0.3])
        e1 /= np.linalg.norm(e1)
        scn = H.Scenario(f"density_n{n}", ref, setup, H.line_path(3.0 * h * e1, 12), geo.analytic)
        row = {"n": n, "nv": ref.nv, "mean_edge": h, "sag_h2_over_8R": h * h / 8.0, "patch_vertices": setup.n}
        for key, cand in (("flat", A.GeodesicPursuit("transport")),
                          ("phong_0.5", A.GeodesicPursuit("transport", evaluator="phong", alpha=0.5)),
                          ("phong_0.75", A.GeodesicPursuit("transport", evaluator="phong", alpha=0.75)),
                          ("closest_global", A.ClosestGlobal())):
            m = H.run(scn, cand).metrics
            row[key] = {"radial_dev_max": m["dev_analytic"]["max"], "radial_dev_mean": m["dev_analytic"]["mean"],
                        "radial_dev_max_rel_edge": m["dev_analytic"]["max"] / h,
                        "rigid_edge_mean": m["edges_rigid"]["mean_abs_rel"],
                        "rigid_edge_max": m["edges_rigid"]["max_abs_rel"]}
        rows.append(row)
    # the price of Phong evaluation where the reference is not smooth: the U with 1, 2 and 8 bend segments
    creases = []
    for scn in S.u_scenarios():
        if not scn.name.startswith(("C5_", "C3_u_gap3cells")):
            continue
        r = H.run(scn, A.GeodesicPursuit("project", evaluator="phong", alpha=0.5))
        creases.append({"scenario": scn.name, "phong_off_the_flat_reference_max_rel_edge":
                        r.metrics["dev_tracked_max_over_frames_rel_edge"]})
    return {"rows": rows, "creases": creases,
            "note": "disc of geodesic radius 3.5 edges, all weights 1, dragged 3 edges along the surface"}


# --- S2: repeated gestures (erosion) ------------------------------------------------------------------------------------

def _volume(P: np.ndarray, T: np.ndarray) -> float:
    return float(np.einsum("ij,ij->i", P[T[:, 0]], np.cross(P[T[:, 1]], P[T[:, 2]])).sum() / 6.0)


def _erosion_run(V0: np.ndarray, faces: list, mode: str, evaluator: str, gestures: int, seed: int) -> dict:
    """`mode` "resnapshot": every gesture slides on a fresh snapshot of the current mesh. "persistent": every
    gesture slides on the snapshot taken once, each vertex keeping its anchor on it between gestures."""
    rng = np.random.default_rng(seed)
    ref0 = H.build_ref(V0, faces)
    h = ref0.mean_edge
    P = V0.copy()
    anchor_tri, anchor_bary = ref0.vertex_anchor(np.arange(ref0.nv))
    on_vertex = np.ones(ref0.nv, dtype=bool)
    history = []
    alpha = 0.5
    for g in range(gestures):
        ref = ref0 if mode == "persistent" else H.build_ref(P, faces)
        graph = EdgeGraph(ref0.nv, ref0.edges, P)
        seed_v = int(rng.integers(ref0.nv))
        verts, w = soft_weights(graph, [seed_v], 3.0 * h)
        direction = rng.normal(size=3)
        if mode == "persistent":
            tri0, bary0 = anchor_tri[verts], anchor_bary[verts]
            n0 = np.where(on_vertex[verts][:, None], ref.VN[verts], ref.normal_at(tri0, bary0))
            setup = A.SlideSetup(ref, tri0, bary0, P[verts].copy(), n0, w, np.where(on_vertex[verts], verts, -1))
        else:
            setup = A.SlideSetup.from_vertices(ref, verts, w)
        pivot_n = setup.n0[int(np.flatnonzero(verts == seed_v)[0])]
        t = direction - (direction @ pivot_n) * pivot_n
        delta = 1.5 * h * t / np.linalg.norm(t)
        cand = A.GeodesicAbs("project", evaluator=evaluator, alpha=alpha)
        cand.begin(setup)
        r = cand.update(delta)
        P[verts] = r.pos
        if mode == "persistent":
            anchor_tri[verts], anchor_bary[verts] = r.tri, r.bary
            on_vertex[verts] &= np.all(r.bary == bary0, axis=1) & (r.tri == tri0)
        if (g + 1) % 10 == 0:
            history.append({"gestures": g + 1, "P": P.copy()})
    return {"history": history, "ref0": ref0}


def erosion() -> dict:
    out = {}
    cases = {"sphere_n8": G.cube_sphere(8), "sphere_n16": G.cube_sphere(16)}
    mesh, cage = S.gollum_cage_ref()
    for name, geo in cases.items():
        rows = {}
        ref = H.build_ref(geo.V, geo.faces)
        v0 = _volume(geo.V, ref.T)
        for mode, evaluator in (("resnapshot", "flat"), ("resnapshot", "phong"), ("persistent", "flat"),
                                ("persistent", "phong")):
            res = _erosion_run(geo.V, geo.faces, mode, evaluator, 60, seed=11)
            rows[f"{mode}/{evaluator}"] = [
                {"gestures": hrow["gestures"],
                 "mean_radius": float(np.linalg.norm(hrow["P"], axis=1).mean()),
                 "min_radius": float(np.linalg.norm(hrow["P"], axis=1).min()),
                 "max_radius": float(np.linalg.norm(hrow["P"], axis=1).max()),
                 "volume_ratio": _volume(hrow["P"], ref.T) / v0} for hrow in res["history"]]
        out[name] = {"mean_edge": ref.mean_edge, "start_volume_ratio_to_sphere": v0 / (4.0 / 3.0 * np.pi),
                     "rows": rows}
    rows = {}
    for mode, evaluator in (("resnapshot", "flat"), ("resnapshot", "phong"), ("persistent", "flat"),
                            ("persistent", "phong")):
        res = _erosion_run(mesh.V, mesh.faces, mode, evaluator, 60, seed=11)
        series = []
        for hrow in res["history"]:
            _, _, d = res["ref0"].closest_point(hrow["P"])
            moved = np.linalg.norm(hrow["P"] - mesh.V, axis=1) > 0
            series.append({"gestures": hrow["gestures"], "moved_vertices": int(moved.sum()),
                           "dist_to_original_mean_rel_edge": float(d[moved].mean() / cage.mean_edge),
                           "dist_to_original_max_rel_edge": float(d.max() / cage.mean_edge)})
        rows[f"{mode}/{evaluator}"] = series
    out["gollum_cage"] = {"mean_edge": cage.mean_edge, "rows": rows}
    # how much the flat surface itself depends on how the polygons are cut: the centroids of one triangulation
    # against the surface of another
    plain = H.build_ref(mesh.V, mesh.faces)
    fan_tris, fan_owner = [], []
    for i, f in enumerate(mesh.faces):
        if len(f) <= 4:
            fan_tris += [(f[0], f[k], f[k + 1]) for k in range(1, len(f) - 1)]
        else:
            first = int(np.searchsorted(plain.tri_face, i))
            fan_tris += plain.T[first:first + len(f) - 2].tolist()
    fan = RefSurface(mesh.V, np.array(fan_tris))
    diff = {}
    for label, a, b in (("shorter_diagonal_vs_mirrored", plain, cage), ("shorter_diagonal_vs_fan_from_first_corner", plain, fan)):
        centroids = a.V[a.T].mean(axis=1)
        d = b.closest_point(centroids)[2] / cage.mean_edge
        diff[label] = {"mean_rel_edge": float(d.mean()), "p95_rel_edge": float(np.percentile(d, 95)),
                       "max_rel_edge": float(d.max()), "triangles_differing": int(np.sum(d > 1e-9))}
    out["gollum_cage_triangulation_difference"] = diff
    out["note"] = ("60 gestures, each: random seed vertex, geodesic smooth falloff of radius 3 mean edges, drag of 1.5 "
                   "mean edges in a random tangent direction (geodesic_abs[project]); Phong alpha 0.5")
    return out


# --- S3: path dependence and drift ----------------------------------------------------------------------------------------

def _drift_candidates(view=None) -> list:
    out = [A.ClosestGlobal(), A.ClosestLocal(), A.TangentLocal(), A.GeodesicInc(), A.GeodesicWalk("transport"),
           A.GeodesicAbs("transport"), A.GeodesicPursuit("transport")]
    return out


def drift() -> dict:
    out = {}
    cases = []
    geo = S.sphere_geo(16)
    ref = S.ref_of(geo)
    v = S.nearest_vertex(ref, (0.0, 0.0, 1.0))
    cases.append(("sphere_n16_patch", ref, S.soft_setup(ref, [v], 0.6, v)))
    ugeo = S.u_geo(0.3, 8)
    uref = S.ref_of(ugeo)
    cases.append(("u_gap3cells_patch", uref, S.soft_setup(uref, [G.u_vertex(ugeo, 19, 10)], 0.6)))
    _, cage = S.gollum_cage_ref()
    for feat in ("cheek", "nose_side"):
        fv = S.front_vertex(cage, *S.CAGE_FEATURES[feat])
        cases.append((f"gollum_cage_{feat}", cage, S.soft_setup(cage, [fv], 0.09, fv)))
    _, hires = S.gollum_hires_ref()
    fv = S.front_vertex(hires, *S.HIRES_FEATURES["cheek"])
    cases.append(("gollum_hires_cheek", hires, S.soft_setup(hires, [fv], 0.09, fv)))
    for name, ref, setup in cases:
        h = ref.mean_edge
        n0 = setup.n0[setup.pivot]
        e1 = np.cross(n0, [0.0, 1.0, 0.2])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(n0, e1)
        target = 3.0 * h * (e1 + 0.6 * e2)
        paths = {
            "straight": H.line_path(target, 24),
            "dogleg": H.polyline_path([3.0 * h * e1, target], 12),
            "detour": H.polyline_path([-2.0 * h * e2, 3.0 * h * e1 - 2.0 * h * e2, target], 10),
        }
        rng = np.random.default_rng(3)
        steps = rng.normal(size=(300, 2)) * 0.25 * h
        walk = np.cumsum(steps, axis=0)
        walk -= np.linspace(0.0, 1.0, len(walk))[:, None] * walk[-1]          # a random walk that ends at zero
        jitter = walk[:, :1] * e1 + walk[:, 1:] * e2
        jitter[-1] = 0.0
        rows = {}
        absolute = A.GeodesicAbs("transport")
        absolute.begin(setup)
        ends_abs = ref.point(*(lambda r: (r.tri, r.bary))(absolute.update(target)))
        for cand in _drift_candidates():
            ends = {}
            ratio = 0.0
            for pname, path in paths.items():
                r = H.run(H.Scenario(f"{name}_{pname}", ref, setup, path), cand)
                ends[pname] = r.pos[-1]
                ratio = max(ratio, r.metrics["continuity"]["max_step_ratio"])
            spread = max(float(np.linalg.norm(ends[a] - ends["straight"], axis=1).max()) for a in ("dogleg", "detour"))
            rj = H.run(H.Scenario(f"{name}_jitter", ref, setup, jitter), cand)
            rows[cand.label] = {
                "path_spread_max_rel_edge": spread / h,
                "jitter_closure_max_rel_edge": rj.metrics["closure"]["max"] / h,
                "jitter_closure_mean_rel_edge": rj.metrics["closure"]["mean"] / h,
                "jitter_max_step_ratio": rj.metrics["continuity"]["max_step_ratio"],
                "jitter_p99_step_ratio": rj.metrics["continuity"]["p99_step_ratio"],
                "paths_max_step_ratio": ratio,
                "jitter_region_jumps": rj.metrics["continuity"]["region_jumps"],
            }
            # the jitter run a second time must give the same bits (determinism)
            rj2 = H.run(H.Scenario(f"{name}_jitter", ref, setup, jitter), cand)
            rows[cand.label]["deterministic"] = bool(np.array_equal(rj.pos, rj2.pos))
            if isinstance(cand, A.GeodesicPursuit):
                # the drag stops at the end of the detour: how many settle steps until every point has its target?
                cand.begin(setup)
                for delta in paths["detour"]:
                    cand.update(delta)
                lag0 = int(cand.lagging.sum())
                steps = 0
                while cand.lagging.any() and steps < 400:
                    r = cand.settle(0.25 * h)
                    steps += 1
                rows[cand.label].update({"lagging_when_drag_stops": lag0, "settle_steps_quarter_edge": steps,
                                         "still_lagging_after_settle": int(cand.lagging.sum()),
                                         "gap_to_absolute_after_settle_rel_edge":
                                             float(np.linalg.norm(cand._pos - ends_abs, axis=1).max() / h)})
        out[name] = {"n_points": setup.n, "mean_edge": h, "rows": rows}
    out["note"] = ("path spread: the same final drag (3.5 mean edges) reached straight, by a dog-leg and by a detour; "
                   "jitter: 300 random steps of about 0.35 mean edges ending at zero drag")
    return out


# --- S4: symmetry ----------------------------------------------------------------------------------------------------------

def _seam_barrier(ref: RefSurface, seam_edges: np.ndarray) -> np.ndarray:
    """The adjacency with the given edges cut."""
    nbr = ref.nbr.copy()
    key = set(map(tuple, np.sort(seam_edges, axis=1).tolist()))
    a = np.roll(ref.T, -1, axis=1)
    b = np.roll(ref.T, -2, axis=1)
    for t in range(ref.nt):
        for k in range(3):
            e = (int(min(a[t, k], b[t, k])), int(max(a[t, k], b[t, k])))
            if e in key:
                nbr[t, k] = -1
    return nbr


def _triangulation_asymmetry(ref: RefSurface, partner: np.ndarray) -> int:
    tris = {tuple(sorted(t)) for t in ref.T.tolist()}
    return int(sum(1 for t in ref.T.tolist() if tuple(sorted(int(partner[v]) for v in t)) not in tris))


def _symmetric_case(name: str, ref: RefSurface, seeds, radius: float, drag_dirs, seam_edges=None) -> dict:
    """Seeds on the +x side; compare (I) both halves solved independently with mirrored drags against (M) the driven
    half solved and the other half written as its mirror image."""
    h = ref.mean_edge
    partner = mirror_partners(ref.V)
    graph = S.graph_of(ref)
    seeds = [int(s) for s in seeds]
    both = sorted(set(seeds) | {int(partner[s]) for s in seeds})
    verts, w = soft_weights(graph, both, radius)
    x = ref.V[verts, 0]
    seam = partner[verts] == verts
    plus = np.flatnonzero((x > 0) | seam)
    minus = np.flatnonzero((x < 0) & ~seam)
    # pair-consistent weights (exact): the minus member takes its partner's
    row_of = {int(v): i for i, v in enumerate(verts)}
    pair_row = np.array([row_of.get(int(partner[verts[i]]), -1) for i in minus], dtype=_I)
    ok = pair_row >= 0
    weight_mismatch = float(np.max(np.abs(w[minus[ok]] - w[pair_row[ok]]), initial=0.0))
    w[minus[ok]] = w[pair_row[ok]]

    def setup_for(rows, pivot_vertex):
        v = verts[rows]
        pivot = int(np.flatnonzero(v == pivot_vertex)[0])
        return A.SlideSetup.from_vertices(ref, v, w[rows], pivot, transport_frames(ref, graph, pivot_vertex, v))

    sp = setup_for(plus, seeds[0])
    sm = setup_for(minus[ok], int(partner[seeds[0]]))
    seam_rows = np.flatnonzero(seam[plus])
    out = {"n_driven": int(len(plus)), "n_mirrored": int(ok.sum()), "n_seam": int(len(seam_rows)),
           "unpaired_in_falloff": int((~ok).sum()), "weight_mismatch_before_pairing": weight_mismatch,
           "triangles_without_mirror_image": _triangulation_asymmetry(ref, partner), "candidates": {}}
    flip = np.array([-1.0, 1.0, 1.0])
    rng = np.random.default_rng(5)
    for label, make in (("geodesic_abs[transport]", lambda: A.GeodesicAbs("transport")),
                        ("geodesic_pursuit[transport]", lambda: A.GeodesicPursuit("transport")),
                        ("geodesic_walk[transport]", lambda: A.GeodesicWalk("transport")),
                        ("geodesic_abs[project]", lambda: A.GeodesicAbs("project")),
                        ("geodesic_inc", lambda: A.GeodesicInc()),
                        ("closest_global", lambda: A.ClosestGlobal())):
        worst_line = 0.0
        worst_wiggle = 0.0
        seam_off = 0.0
        seam_snap_dev = 0.0
        for d in drag_dirs:
            d = np.asarray(d, dtype=np.float64)
            line = H.line_path(3.0 * h * d / np.linalg.norm(d), 12)
            wig = np.cumsum(rng.normal(size=(120, 3)) * 0.2 * h, axis=0) + np.linspace(0, 1, 120)[:, None] * line[-1]
            for path, kind in ((line, "line"), (wig, "wiggle")):
                cp, cm = make(), make()
                cp.begin(sp)
                cm.begin(sm)
                for delta in path:
                    rp = cp.update(delta)
                    rm = cm.update(delta * flip)
                mirrored = mirror(rp.pos)
                # row i of the minus setup is the partner of plus row j
                plus_row = {int(v): i for i, v in enumerate(sp.verts)}
                j = np.array([plus_row[int(partner[v])] for v in sm.verts], dtype=_I)
                asym = float(np.linalg.norm(rm.pos - mirrored[j], axis=1).max(initial=0.0))
                if kind == "line":
                    worst_line = max(worst_line, asym)
                else:
                    worst_wiggle = max(worst_wiggle, asym)
                if len(seam_rows):
                    seam_off = max(seam_off, float(np.abs(rp.pos[seam_rows, 0]).max()))
                    snapped = rp.pos[seam_rows].copy()
                    snapped[:, 0] = 0.0
                    seam_snap_dev = max(seam_snap_dev, float(M.tracked_deviation(ref, snapped, rp.tri[seam_rows]).max()))
        out["candidates"][label] = {"independent_vs_mirror_line_rel_edge": worst_line / h,
                                    "independent_vs_mirror_wiggle_rel_edge": worst_wiggle / h,
                                    "seam_off_plane_unconstrained_rel_edge": seam_off / h,
                                    "seam_dev_after_plane_snap_rel_edge": seam_snap_dev / h}
    # the seam handled properly: the drag of a seam vertex has no component across the plane (its start normal lies in
    # the plane on a symmetric mesh), walked, then x set to exactly 0
    cand = A.GeodesicPursuit("transport")
    sp_seam = A.SlideSetup(ref, sp.tri0, sp.bary0, sp.p0, sp.n0.copy(), sp.weights, sp.verts, sp.pivot, sp.transport)
    sp_seam.n0[seam_rows, 0] = 0.0
    sp_seam.n0[seam_rows] /= np.linalg.norm(sp_seam.n0[seam_rows], axis=1, keepdims=True)
    cand.begin(sp_seam)
    worst_off, worst_dev = 0.0, 0.0
    for d in drag_dirs:
        d = np.asarray(d, dtype=np.float64)
        for delta in H.line_path(3.0 * h * d / np.linalg.norm(d), 12):
            in_plane = delta * np.array([0.0, 1.0, 1.0])
            r = cand.update(in_plane)
            if len(seam_rows):
                worst_off = max(worst_off, float(np.abs(r.pos[seam_rows, 0]).max()))
                snapped = r.pos[seam_rows].copy()
                snapped[:, 0] = 0.0
                worst_dev = max(worst_dev, float(M.tracked_deviation(ref, snapped, r.tri[seam_rows]).max()))
    out["seam_in_plane_drag"] = {"off_plane_before_snap_rel_edge": worst_off / h,
                                 "dev_after_snap_rel_edge": worst_dev / h}
    # crossing the plane: drive the plus half towards -x, free and with the seam as a barrier
    if seam_edges is not None and len(seam_edges):
        nbr = _seam_barrier(ref, seam_edges)
        cross = {}
        for label, table in (("free", None), ("seam_barrier", nbr)):
            s2 = A.SlideSetup(ref, sp.tri0, sp.bary0, sp.p0, sp.n0, sp.weights, sp.verts, sp.pivot, sp.transport, table)
            cand = A.GeodesicPursuit("transport")
            cand.begin(s2)
            flags = np.zeros(s2.n, dtype=np.uint8)
            for delta in H.line_path((-6.0 * h, 0.5 * h, 0.0), 24):
                r = cand.update(delta)
                flags |= r.flags
            off_seam = np.setdiff1d(np.arange(s2.n), seam_rows)
            cross[label] = {"driven_now_on_minus_side": int(np.sum(r.pos[off_seam, 0] < 0.0)),
                            "driven_exactly_on_plane": int(np.sum(r.pos[off_seam, 0] == 0.0)),
                            "driven_within_1e-9_of_plane": int(np.sum(np.abs(r.pos[off_seam, 0]) < 1e-9)),
                            "stopped_at_barrier": int(np.sum((flags & (A.geo.FLAG_BOUNDARY | A.geo.FLAG_BLOCKED)) > 0)),
                            "tracked_dev_max_rel_edge": float(M.tracked_deviation(ref, r.pos, r.tri).max() / h)}
        out["crossing_the_plane"] = cross
    return out


def symmetry() -> dict:
    out = {}
    geo = S.sphere_geo(16)
    ref = S.ref_of(geo)
    v = S.nearest_vertex(ref, np.array([0.28, 0.1, 1.0]) / np.linalg.norm([0.28, 0.1, 1.0]))
    seam_edges = ref.edges[(ref.V[ref.edges[:, 0], 0] == 0.0) & (ref.V[ref.edges[:, 1], 0] == 0.0)]
    out["sphere_n16"] = _symmetric_case("sphere", ref, [v], 0.6, [(1, 0, 0), (0, 1, 0), (-0.7, 0.7, 0)], seam_edges)
    ugeo = G.u_shape(0.3, 2.0, 2.0, 0.1, 8)       # the U is mirror-symmetric in x by construction of its profile
    Vs, _ = G.symmetrize_x(ugeo.V)
    uref = H.build_ref(Vs, ugeo.faces)
    m = ugeo.meta["profile_nodes"]
    useed = G.u_vertex(ugeo, m - 1 - 17, 10)      # wall B (x > 0), 3 cells above the bend
    useam = uref.edges[(uref.V[uref.edges[:, 0], 0] == 0.0) & (uref.V[uref.edges[:, 1], 0] == 0.0)]
    out["u_gap3cells"] = _symmetric_case("u", uref, [useed], 0.6, [(0, 0, -1), (0, 1, -0.5), (0, 1, 0)], useam)
    mesh, cage = S.gollum_cage_ref()
    for feat in ("nose_side", "upper_lip", "forehead"):
        fv = S.front_vertex(cage, *S.CAGE_FEATURES[feat])
        out[f"gollum_cage_{feat}"] = _symmetric_case(feat, cage, [fv], 0.12, [(1, 0, 0), (0, 1, 0), (-0.7, -0.7, 0)],
                                                     mesh.seam_edges)
    # the same cage with the per-face triangulation rules (not mirrored): what an asymmetric reference costs
    mesh_a, cage_a = S.gollum_cage_ref(False)
    fv = S.front_vertex(cage_a, *S.CAGE_FEATURES["nose_side"])
    out["gollum_cage_nose_side_asymmetric_triangulation"] = _symmetric_case(
        "nose_side", cage_a, [fv], 0.12, [(1, 0, 0), (0, 1, 0), (-0.7, -0.7, 0)], mesh_a.seam_edges)
    tri_rows = {}
    for label, (m_, ref_) in (("per_face_rules", (mesh_a, cage_a)), ("mirrored", (mesh, cage))):
        worst = 0.0
        for feat in S.CAGE_FEATURES:
            v_ = S.front_vertex(ref_, *S.CAGE_FEATURES[feat])
            setup = S.soft_setup(ref_, [v_], 0.09, v_)
            cand = A.GeodesicPursuit("transport")
            cand.begin(setup)
            for d in ((0.05, 0.02, 0.0), (-0.03, 0.06, 0.0), (0.0, -0.07, 0.0)):
                r = cand.update(np.array(d))
                worst = max(worst, float(ref_.closest_point(mirror(r.pos))[2].max()))
        tri_rows[label] = {"triangles_without_mirror_image":
                               _triangulation_asymmetry(ref_, mirror_partners(ref_.V)), "triangles": ref_.nt,
                           "mirrored_result_off_reference_max_rel_edge": worst / ref_.mean_edge}
    out["gollum_cage_triangulation"] = tri_rows
    from surface_slide.seam import SeamCurve
    curve = SeamCurve(cage, mesh.seam_edges)
    worst_x, worst_gap, walks, ends = 0.0, 0.0, 0, 0
    for v_ in mesh.seam_vertices.tolist():
        for t in ((0.0, 0.05, 0.0), (0.0, -0.08, 0.02), (0.03, 0.02, 0.06), (0.0, 0.0, -0.4)):
            tri_, bary_, pos_, stopped = curve.slide(v_, np.array(t))
            worst_x = max(worst_x, abs(float(pos_[0])))
            worst_gap = max(worst_gap, float(np.linalg.norm(cage.point(np.array([tri_]), bary_[None])[0] - pos_)))
            walks += 1
            ends += int(stopped)
    out["gollum_cage_seam_curve_slide"] = {"walks": walks, "max_abs_plane_coordinate": worst_x,
                                           "max_distance_to_reference": worst_gap, "stopped_at_seam_end": ends}
    out["note"] = ("seed on the +x side, geodesic falloff reaching across the plane; I = both halves solved "
                   "independently (mirrored drag), M = driven half mirrored; drags of 3 mean edges")
    return out


# --- S5: soft-selection weights ---------------------------------------------------------------------------------------------

def _banded_setup(ref: RefSurface, centre: int) -> tuple:
    """Rings 0-1: weight 1, rings 2-3: 0.5, rings 4-5: 0.25, rings 6-7: 0 (in the set, must not move)."""
    graph = S.graph_of(ref)
    rings = [S.ring(ref, centre, d) for d in range(0, 8)]
    order = {}
    for d, r in enumerate(rings):
        for v in r.tolist():
            order.setdefault(v, d)
    verts = np.array(sorted(order), dtype=_I)
    depth = np.array([order[int(v)] for v in verts])
    w = np.select([depth <= 1, depth <= 3, depth <= 5], [1.0, 0.5, 0.25], 0.0)
    pivot = int(np.flatnonzero(verts == centre)[0])
    return A.SlideSetup.from_vertices(ref, verts, w, pivot, transport_frames(ref, graph, centre, verts)), depth


def weights() -> dict:
    out = {}
    cases = []
    geo = S.sphere_geo(16)
    ref = S.ref_of(geo)
    cases.append(("sphere_n16", ref, S.nearest_vertex(ref, (0, 0, 1.0)), geo.analytic, None))
    ugeo = S.u_geo(0.3, 8)
    uref = S.ref_of(ugeo)
    cases.append(("u_gap3cells_near_bend", uref, G.u_vertex(ugeo, 19, 10), None, (0.0, 0.0, -1.0)))
    _, cage = S.gollum_cage_ref()
    cases.append(("gollum_cage_cheek", cage, S.front_vertex(cage, *S.CAGE_FEATURES["cheek"]), None, (0.0, 1.0, 0.0)))
    cases.append(("gollum_cage_brow", cage, S.front_vertex(cage, *S.CAGE_FEATURES["brow"]), None, (0.0, -1.0, 0.0)))
    _, hires = S.gollum_hires_ref()
    cases.append(("gollum_hires_cheek", hires, S.front_vertex(hires, *S.HIRES_FEATURES["cheek"]), None, (0.0, 1.0, 0.0)))
    for name, ref, centre, analytic, drag in cases:
        setup, depth = _banded_setup(ref, centre)
        h = ref.mean_edge
        n0 = setup.n0[setup.pivot]
        if drag is None:
            drag = np.cross(n0, [0.0, 1.0, 0.3])
        drag = np.asarray(drag, dtype=np.float64)
        delta = 2.5 * h * drag / np.linalg.norm(drag)
        scn = H.Scenario(f"weights_{name}", ref, setup, H.line_path(delta, 15), analytic)
        rows = {}
        for cand in (A.GeodesicPursuit("transport"), A.GeodesicPursuit("project"), A.GeodesicAbs("transport"),
                     A.GeodesicWalk("transport"), A.ClosestGlobal(), A.ClosestLocal(),
                     A.Lerp(A.GeodesicAbs("transport")), A.Lerp(A.ClosestGlobal())):
            r = H.run(scn, cand)
            final = r.pos[-1]
            dev = M.tracked_deviation(ref, final, r.tri[-1])
            travel = np.linalg.norm(final - setup.p0, axis=1)
            full = travel[setup.weights == 1.0].mean()
            per = {}
            for wv in (0.0, 0.25, 0.5, 1.0):
                sel = setup.weights == wv
                per[f"{wv:g}"] = {
                    "n": int(sel.sum()),
                    "dev_max_rel_edge": float(dev[sel].max() / h),
                    "travel_mean_over_full": float(travel[sel].mean() / full) if full > 0 else 0.0,
                    "travel_min_over_full": float(travel[sel].min() / full) if full > 0 else 0.0,
                    "travel_max_over_full": float(travel[sel].max() / full) if full > 0 else 0.0,
                    "moved_bit_exact_none": bool(np.array_equal(final[sel], setup.p0[sel])),
                }
                if analytic is not None:
                    per[f"{wv:g}"]["analytic_dev_max_rel_edge"] = float(analytic.distance(final[sel]).max() / h)
            rows[cand.label] = {"per_weight": per, "edges_mean": r.metrics["edges"]["mean_abs_rel"],
                                "edges_max": r.metrics["edges"]["max_abs_rel"],
                                "edges_free_mean": r.metrics["edges_free_move"]["mean_abs_rel"],
                                "edges_free_max": r.metrics["edges_free_move"]["max_abs_rel"],
                                "folded": r.metrics["folded_tris"], "folded_free": r.metrics["folded_tris_free_move"],
                                "max_step_ratio": r.metrics["continuity"]["max_step_ratio"],
                                "region_jumps": r.metrics["continuity"]["region_jumps"]}
        out[name] = {"n_points": setup.n, "mean_edge": h, "drag_rel_edge": 2.5, "rows": rows}
    out["note"] = "weight bands by ring: 1 (rings 0-1), 0.5 (2-3), 0.25 (4-5), 0 (6-7); drag 2.5 mean edges"
    return out


# --- S6: how well the pivot follows the cursor ------------------------------------------------------------------------------

def _solve_pivot_under_cursor(ref: RefSurface, vertex: int, screen_path: np.ndarray) -> dict:
    """Find, frame by frame, the tangent drag of the pivot whose geodesic end point lies under the cursor (front
    view, orthographic: screen = x, y). Damped Newton on two unknowns with a finite-difference Jacobian, warm-started
    from the previous frame; the solve is local, so the pivot cannot jump to another surface part under the cursor."""
    setup = A.SlideSetup.from_vertices(ref, [vertex])
    cand = A.GeodesicAbs("project")
    cand.begin(setup)
    n0 = setup.n0[0]
    e1 = np.cross(n0, np.eye(3)[int(np.argmin(np.abs(n0)))])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n0, e1)
    h = ref.mean_edge
    evals = 0

    def screen(ab):
        nonlocal evals
        evals += 1
        return cand.update(ab[0] * e1 + ab[1] * e2).pos[0, :2]

    ab = np.zeros(2)
    start = setup.p0[0, :2]
    residuals, speed = [], []
    prev_cursor = np.zeros(2)
    for cursor_xy in screen_path:
        goal = start + cursor_xy
        before = ab.copy()
        for _ in range(4):
            f = screen(ab)
            res = goal - f
            if np.linalg.norm(res) < 1e-3 * h:
                break
            eps = 0.05 * h
            J = np.stack([(screen(ab + [eps, 0.0]) - f) / eps, (screen(ab + [0.0, eps]) - f) / eps], axis=1)
            step = np.linalg.solve(J, res) if abs(np.linalg.det(J)) > 0.05 else J.T @ res
            limit = 3.0 * np.linalg.norm(res)
            if np.linalg.norm(step) > limit:
                step *= limit / np.linalg.norm(step)
            for _ in range(4):
                if np.linalg.norm(goal - screen(ab + step)) < np.linalg.norm(res):
                    ab = ab + step
                    break
                step = step * 0.5
        residuals.append(float(np.linalg.norm(goal - screen(ab)) / h))
        move = np.linalg.norm(cursor_xy - prev_cursor)
        speed.append(float(np.linalg.norm(ab - before) / move) if move > 0 else 0.0)
        prev_cursor = cursor_xy
    end = screen(ab) - start
    drag = screen_path[-1]
    return {"screen_follow": float(end @ drag / (drag @ drag)),
            "residual_mean_rel_edge": float(np.mean(residuals)), "residual_max_rel_edge": float(np.max(residuals)),
            "surface_speed_over_cursor_speed_max": float(np.max(speed)),
            "traces_per_frame": evals / len(screen_path)}


def cursor() -> dict:
    """Front-view screen drags on the Gollum meshes: the pivot's movement on screen against the drag."""
    out = {}
    for scn in S.gollum_scenarios("cage") + S.gollum_scenarios("hires"):
        if "_loop" in scn.name or "_rigid" in scn.name:
            continue
        drag = scn.path[-1][:2]
        rows = {}
        cands = [A.GeodesicPursuit("transport"), A.GeodesicAbs("transport", length="full"), A.ClosestGlobal()]
        if scn.ref.nt < 10000:
            cands.append(A.RayView(S.VIEW_FRONT))
        for cand in cands:
            r = H.run(scn, cand)
            p = scn.setup.pivot
            move = (r.pos[-1, p] - scn.setup.p0[p])[:2]
            along = float(move @ drag / (drag @ drag))
            across = float(np.linalg.norm(move - along * drag) / np.linalg.norm(drag))
            rows[cand.label] = {"screen_follow": along, "screen_sideways": across}
        nz = scn.setup.n0[scn.setup.pivot] @ (-S.VIEW_FRONT)
        solved = _solve_pivot_under_cursor(scn.ref, int(scn.setup.verts[scn.setup.pivot]), scn.path[:, :2])
        out[scn.name] = {"pivot_normal_towards_viewer": float(nz), "rows": rows, "pivot_under_cursor_solve": solved}
    out["note"] = "screen_follow 1.0 = the pivot ends under the cursor; front view, orthographic"
    return out


STUDIES = {"density": density, "erosion": erosion, "drift": drift, "symmetry": symmetry, "weights": weights,
           "cursor": cursor}


def main(argv=None) -> int:
    names = (argv if argv is not None else sys.argv[1:]) or list(STUDIES)
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / "studies.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for name in names:
        t0 = time.time()
        data[name] = STUDIES[name]()
        print(f"{name}: {time.time() - t0:.1f} s")
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
