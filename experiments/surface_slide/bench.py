"""Performance probe: setup cost, per-update cost and memory at about 5k / 20k / 100k vertices (cube spheres) and on
the two dense Gollum meshes (21 875 and 87 500 vertices). Writes `results/bench.json`.

    python experiments/surface_slide/bench.py [--quick]

A drag is simulated as it happens: from zero out to `distance` in frames of half a mean edge, each frame one
`update`. Reported per candidate: the mean and the worst frame. Times are wall clock on whatever machine runs this;
the container is about 2x faster than the reference PC for Python / NumPy code (REFERENCE_HARDWARE.md).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402

from surface_slide import algorithms as A  # noqa: E402
from surface_slide import geometries as G  # noqa: E402
from surface_slide import harness as H  # noqa: E402
from surface_slide import mirai_io  # noqa: E402
from surface_slide.fields import EdgeGraph, soft_weights, transport_frames  # noqa: E402
from surface_slide.refsurf import RefSurface, triangulate  # noqa: E402

RESULTS = HERE / "results"


def _best(fn, repeat: int = 3) -> float:
    best = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best * 1e3


def radius_for(graph: EdgeGraph, seed: int, target: int, h: float) -> float:
    lo, hi = h, 400.0 * h
    for _ in range(18):
        mid = 0.5 * (lo + hi)
        if len(graph.dijkstra([seed], mid)[0]) < target:
            lo = mid
        else:
            hi = mid
    return hi


def bench_mesh(name: str, V: np.ndarray, faces: list, affected_targets, distances, quick: bool) -> dict:
    out: dict = {"name": name}
    t0 = time.perf_counter()
    T, tri_face = triangulate(V, faces)
    out["triangulate_ms"] = (time.perf_counter() - t0) * 1e3
    tracemalloc.start()
    t0 = time.perf_counter()
    ref = RefSurface(V, T, tri_face, faces)
    out["refsurface_build_ms"] = (time.perf_counter() - t0) * 1e3
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    out["refsurface_build_peak_mb"] = peak / 1e6
    out["refsurface_build_ms_best"] = _best(lambda: RefSurface(V, T, tri_face, faces), 2 if quick else 3)
    t0 = time.perf_counter()
    ref.build_grid()
    out["closest_grid_build_ms"] = (time.perf_counter() - t0) * 1e3
    out.update({"nv": ref.nv, "nt": ref.nt, "mean_edge": ref.mean_edge,
                "bytes_tracer_arrays": ref.tracer_nbytes(), "bytes_all_arrays": ref.nbytes(),
                "bytes_closest_grid": ref.grid_bytes(),
                "bytes_per_vertex_tracer": ref.tracer_nbytes() / ref.nv})
    t0 = time.perf_counter()
    graph = EdgeGraph(ref.nv, ref.edges, ref.V)
    out["edge_graph_ms"] = (time.perf_counter() - t0) * 1e3
    h = ref.mean_edge
    seed = int(np.argmax(ref.V[:, 2] - 0.3 * np.abs(ref.V[:, 0]) - 0.3 * np.abs(ref.V[:, 1])))
    out["cases"] = []
    for target in affected_targets:
        if target > ref.nv // 2:
            continue
        radius = radius_for(graph, seed, target, h)
        t0 = time.perf_counter()
        verts, w = soft_weights(graph, [seed], radius)
        t_weights = (time.perf_counter() - t0) * 1e3
        pivot = int(np.flatnonzero(verts == seed)[0])
        t0 = time.perf_counter()
        frames_ = transport_frames(ref, graph, seed, verts)
        t_transport = (time.perf_counter() - t0) * 1e3
        setup = A.SlideSetup.from_vertices(ref, verts, w, pivot, frames_)
        n0 = setup.n0[pivot]
        e1 = np.cross(n0, [0.0, 1.0, 0.25])
        e1 /= np.linalg.norm(e1)
        case = {"affected": int(len(verts)), "radius_rel_edge": radius / h, "weights_dijkstra_ms": t_weights,
                "transport_frames_ms": t_transport, "updates": {}}
        cands = [A.GeodesicPursuit("transport"), A.GeodesicPursuit("transport", evaluator="phong", alpha=0.5),
                 A.GeodesicAbs("transport"), A.GeodesicWalk("transport"), A.GeodesicInc(), A.TangentLocal(),
                 A.ClosestLocal(), A.ClosestGlobal()]
        for cand in cands:
            per_dist = {}
            for dist in distances:
                # the prototype's closest-point grid falls back to brute force for targets far off the surface; the
                # global projection is therefore only timed where that does not dominate
                if cand.name == "closest_global" and (dist > 10.0 or len(verts) > 2000):
                    continue
                frames = max(2, int(round(dist / 0.5)))
                path = H.line_path(dist * h * e1, frames)
                t0 = time.perf_counter()
                cand.begin(setup)
                t_begin = (time.perf_counter() - t0) * 1e3
                times = []
                passes = 0
                for delta in path:
                    t0 = time.perf_counter()
                    r = cand.update(delta)
                    times.append((time.perf_counter() - t0) * 1e3)
                    passes = max(passes, r.passes)
                per_dist[f"{dist:g}"] = {"begin_ms": t_begin, "update_ms_mean": float(np.mean(times)),
                                         "update_ms_last": float(times[-1]), "update_ms_max": float(np.max(times)),
                                         "us_per_vertex_last": float(times[-1] * 1e3 / len(verts)),
                                         "max_passes": int(passes)}
            case["updates"][cand.label] = per_dist
        out["cases"].append(case)
        print(f"  {name}: affected {len(verts)} done", flush=True)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="smaller meshes only (for the test suite)")
    args = parser.parse_args(argv)
    RESULTS.mkdir(exist_ok=True)
    meshes = []
    if args.quick:
        geo = G.cube_sphere_for(5000)
        meshes.append((f"cube_sphere_{len(geo.V)}", geo.V, geo.faces))
    else:
        for target in (5000, 20000, 100000):
            geo = G.cube_sphere_for(target)
            meshes.append((f"cube_sphere_{len(geo.V)}", geo.V, geo.faces))
        for loader in (mirai_io.gollum_hires, mirai_io.gollum_87k):
            m = loader()
            meshes.append((f"{m.name}_{len(m.V)}", m.V, m.faces))
    targets = (100, 1000) if args.quick else (100, 1000, 10000)
    distances = (2.0, 10.0) if args.quick else (2.0, 10.0, 30.0)
    out = {"numpy": np.__version__, "python": sys.version.split()[0], "meshes": []}
    for name, V, faces in meshes:
        print(name, flush=True)
        out["meshes"].append(bench_mesh(name, V, faces, targets, distances, args.quick))
        (RESULTS / "bench_partial.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    path = RESULTS / ("bench_quick.json" if args.quick else "bench.json")
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    (RESULTS / "bench_partial.json").unlink(missing_ok=True)
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
