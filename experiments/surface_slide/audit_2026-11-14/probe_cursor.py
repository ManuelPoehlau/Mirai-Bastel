"""Probe: cursor mapping by ray / pivot-tangent-plane intersection (M2) vs the Move-tool screen-plane delta (M1)."""
import sys, numpy as np
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
for _p in (REPO / "src", REPO / "examples", REPO / "experiments"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
from surface_slide import algorithms as A, scenarios as S, harness as H, metrics as M

def m2_delta(n0, p0, cursor_xy, k_max):
    # ortho front view: ray (p0.xy + c, z) along -z; intersect plane n0.(q - p0) = 0
    c = np.asarray(cursor_xy, float)
    nz = n0[2]
    dz = -(n0[0] * c[0] + n0[1] * c[1]) / nz if abs(nz) > 1e-12 else 0.0
    t = np.array([c[0], c[1], dz])
    lim = k_max * np.linalg.norm(c)
    L = np.linalg.norm(t)
    if L > lim > 0:
        t *= lim / L
    return t

rows = []
for which in ("cage", "hires"):
    for scn in S.gollum_scenarios(which):
        if "_loop" in scn.name or "_rigid" in scn.name:
            continue
        p = scn.setup.pivot
        n0, p0 = scn.setup.n0[p], scn.setup.p0[p]
        drag = scn.path[-1][:2]
        out = {"name": scn.name, "nz": float(n0 @ np.array([0, 0, 1.0]))}
        for label, k in (("M1", None), ("M2_k3", 3.0), ("M2_k10", 10.0)):
            cand = A.GeodesicPursuit("transport")
            cand.begin(scn.setup)
            prev_pos = scn.setup.p0.copy(); prev_c = np.zeros(2); ratios = []; resid = []
            for d in scn.path:
                c = d[:2]
                delta = d if k is None else m2_delta(n0, p0, c, k)
                r = cand.update(delta)
                step = np.linalg.norm(r.pos[p] - prev_pos[p]); cs = np.linalg.norm(c - prev_c)
                if cs > 0: ratios.append(step / cs)
                resid.append(np.linalg.norm((r.pos[p] - p0)[:2] - c) / scn.ref.mean_edge)
                prev_pos = r.pos; prev_c = c
            move = (r.pos[p] - p0)[:2]
            out[label] = (float(move @ drag / (drag @ drag)), float(max(ratios)), float(np.mean(resid)),
                          int(np.sum(r.flags & (A.geo.FLAG_BOUNDARY)) > 0))
        rows.append(out)
print(f"{'scenario':28s} {'n.view':>6s} | {'M1 follow':>9s} {'ratio':>6s} {'res/h':>6s} | {'M2k3 fol':>8s} {'ratio':>6s} {'res/h':>6s} | {'M2k10':>6s} {'ratio':>6s} {'res/h':>6s}")
for o in rows:
    a, b, c = o["M1"], o["M2_k3"], o["M2_k10"]
    print(f"{o['name']:28s} {o['nz']:6.2f} | {a[0]:9.2f} {a[1]:6.2f} {a[2]:6.2f} | {b[0]:8.2f} {b[1]:6.2f} {b[2]:6.2f} | {c[0]:6.2f} {c[1]:6.2f} {c[2]:6.2f}")
for lab in ("M1", "M2_k3", "M2_k10"):
    f = np.array([o[lab][0] for o in rows])
    print(lab, "within 10% of cursor:", int(np.sum(np.abs(f - 1) <= 0.1)), "/", len(f), " within 25%:", int(np.sum(np.abs(f - 1) <= 0.25)), " median follow", float(np.median(f)))
