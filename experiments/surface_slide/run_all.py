"""Run every scenario with every candidate and write `results/scenarios.json` (+ a console table).

    python experiments/surface_slide/run_all.py [--only A B C D] [--no-hires]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402

from surface_slide import algorithms as A  # noqa: E402
from surface_slide import harness as H  # noqa: E402
from surface_slide import scenarios as S  # noqa: E402

RESULTS = HERE / "results"


def candidates_for(scn: H.Scenario) -> list[A.Candidate]:
    view = S.VIEW_FRONT if scn.tags.get("view") == "front" else None
    out = A.standard_candidates(view)
    if scn.setup.transport is not None:
        out += [A.GeodesicWalk("transport"), A.GeodesicAbs("transport"), A.GeodesicPursuit("transport"),
                A.GeodesicPursuit("transport", evaluator="phong", alpha=0.5)]
    return out


def short(run: H.Run) -> str:
    m = run.metrics
    e = m.get("edges", {})
    r = m.get("edges_rigid", {})
    c = m["continuity"]
    ana = m["dev_analytic"]["max"] if "dev_analytic" in m else float("nan")
    flags = {k: v for k, v in m["flags"].items() if v}
    return (f"{run.candidate:34s} trk {m['dev_tracked_max_over_frames']:.1e} ana {ana:.1e} "
            f"edge {e.get('mean_abs_rel', float('nan')):.3f}/{e.get('max_abs_rel', float('nan')):.3f} "
            f"rigid {r.get('mean_abs_rel', float('nan')):.3f}/{r.get('max_abs_rel', float('nan')):.3f} "
            f"fold {m.get('folded_tris', '-')}({m.get('folded_tris_free_move', '-')}) ratio {c['max_step_ratio']:.2f} jumps {c['region_jumps']} "
            f"wrong {m.get('wrong_region_any_frame', '-')} ms {m['update_ms_mean']:.2f} {flags if flags else ''}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None, help="scenario name prefixes, e.g. A C D_cage")
    parser.add_argument("--no-hires", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    RESULTS.mkdir(exist_ok=True)
    out = {}
    t0 = time.time()
    for scn in S.all_scenarios(include_hires=not args.no_hires):
        if args.only and not any(scn.name.startswith(p) for p in args.only):
            continue
        if not args.quiet:
            print(f"\n== {scn.name}  n={scn.setup.n} frames={len(scn.path)}  {scn.notes}")
        entry = {"notes": scn.notes, "n_points": scn.setup.n, "frames": len(scn.path),
                 "mean_edge": scn.ref.mean_edge, "bbox_diag": scn.ref.bbox_diag, "nv": scn.ref.nv, "nt": scn.ref.nt,
                 "drag": [float(x) for x in scn.path[-1]], "drag_max_rel_edge":
                     float(np.max(np.linalg.norm(scn.path, axis=1)) / scn.ref.mean_edge), "candidates": {}}
        for cand in candidates_for(scn):
            run = H.run(scn, cand)
            entry["candidates"][run.candidate] = run.metrics
            if not args.quiet:
                print("  ", short(run))
        out[scn.name] = entry
    path = RESULTS / ("scenarios.json" if not args.only else "scenarios_partial.json")
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\n{len(out)} scenarios, {time.time() - t0:.1f} s -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
