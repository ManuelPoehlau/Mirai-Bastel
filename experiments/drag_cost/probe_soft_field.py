"""Soft field and Smooth-stroke dab cost (Brush research 2026-11-18 §4.1 / §8.4, phases 1 and 2). Headless, no GL.

Usage (from the repo root):
    python experiments/drag_cost/probe_soft_field.py                       # gollum_20k and the 87.5k fixture
    python experiments/drag_cost/probe_soft_field.py --assets examples/meshes/gollum_20k.obj --radii 5 10
    python experiments/drag_cost/probe_soft_field.py --repeats 20

Rows per asset and radius (percent of the mesh bounding radius, the unit of `SoftSettings`):

- **field**: `compute_influence` geodesic / smooth from one seed (the front-most vertex, deterministic) - what every
  Soft press (W/E/R, S, Shift+I, J) and every hover-preview change pays once.
- **dab**: one Smooth-stroke dab as the app runs it (`mirai.topology.smooth_stroke.dab`: the field around the hit
  face's points, `plan_smooth`, the positions at `DAB_AMOUNT`, the writes into an open change journal). Bars (the D3
  bars, research §7): p95 <= 16.7 ms at 5 % on gollum_20k, <= 33 ms on the 87.5k fixture - on the reference PC; a
  container figure x3 is the estimate (2026-11-10 audit).
- **symmetry setup** (once per press / stroke): `vertex_correspondence` + `SymmetryIndex` with a definition at x = 0.

Plain ASCII output; prints the commit and working-tree state (`_paths.source_state`).
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drag_cost._paths import REPO_ROOT, ensure_paths, source_state  # noqa: E402

ensure_paths()

DEFAULT_ASSETS = ("examples/meshes/gollum_20k.obj", "experiments/drag_cost/fixtures/gollum_87k.obj")
DEFAULT_RADII = (3, 5, 10, 15, 25)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--assets", nargs="+", default=list(DEFAULT_ASSETS))
    parser.add_argument("--radii", nargs="+", type=float, default=list(DEFAULT_RADII))
    parser.add_argument("--repeats", type=int, default=9)
    return parser


def _load(path: str):
    from loaders.obj_loader import load_obj
    from mirai.scene_factory import mesh_from_positions_and_faces

    data = load_obj(REPO_ROOT / path)
    return mesh_from_positions_and_faces(data.vertices, data.faces)


def _stats(samples: list[float]) -> str:
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
    return f"p50 {statistics.median(ordered):8.2f} ms  p95 {p95:8.2f} ms"


def _time(fn, repeats: int) -> list[float]:
    out = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000.0)
    return out


def run_asset(path: str, radii: list[float], repeats: int) -> None:
    from core.mesh import SymmetryDefinition
    from mirai.mesh_geometry import mesh_center_and_radius
    from mirai.soft_selection.influence import compute_influence
    from mirai.soft_selection.settings import SoftSettings
    from mirai.symmetry_coordination import SymmetryIndex
    from mirai.symmetry import vertex_correspondence

    t0 = time.perf_counter()
    mesh = _load(path)
    print(f"\n{path}: {len(mesh.all_vertex_ids())} V, {len(mesh.all_face_ids())} F "
          f"(load {time.perf_counter() - t0:.1f} s)")
    _, bounding = mesh_center_and_radius(mesh)
    seed = max(mesh.all_vertex_ids(), key=lambda v: (mesh.vertex_position(v)[2], int(v)))
    face = min(f for e in mesh.vertex_edges(seed) for f in mesh.edge_faces(e))
    seeds = set(mesh.face_vertices(face))  # a dab's seeds: the points of the hit face

    try:
        from mirai.topology.smooth_stroke import DAB_AMOUNT, dab
    except ImportError:  # before phase 2 (the baseline run): the field rows only
        dab = None

    for percent in radii:
        radius = bounding * percent / 100.0
        weights = compute_influence(mesh, {seed}, radius, metric="geodesic", curve="smooth")
        field = _time(lambda: compute_influence(mesh, {seed}, radius, metric="geodesic", curve="smooth"), repeats)
        print(f"  {percent:5.1f} %  {len(weights):6d} V  field {_stats(field)}")
        if dab is not None:
            soft = SoftSettings(world_radius=radius)
            before = mesh.begin_change()
            try:
                samples = _time(lambda: dab(mesh, seeds, soft, relax=False), repeats)
            finally:
                mesh.rollback_change(before)
            print(f"  {'':5s}    {'':6s}    dab   {_stats(samples)}  (DAB_AMOUNT {DAB_AMOUNT})")

    t0 = time.perf_counter()
    mesh.symmetry_definition = SymmetryDefinition(plane_point=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0))
    t1 = time.perf_counter()
    correspondence = vertex_correspondence(mesh)
    t2 = time.perf_counter()
    SymmetryIndex(mesh)
    t3 = time.perf_counter()
    paired = sum(1 for c in correspondence.values() if c.partner is not None)
    print(f"  symmetry setup: vertex_correspondence {(t2 - t1) * 1000:.0f} ms, SymmetryIndex(mesh) (its own pairing "
          f"included) {(t3 - t2) * 1000:.0f} ms ({paired} paired; set {(t1 - t0) * 1000:.0f} ms)")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(f"probe_soft_field - {source_state()} - Python {sys.version.split()[0]}")
    for path in args.assets:
        run_asset(path, args.radii, args.repeats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
