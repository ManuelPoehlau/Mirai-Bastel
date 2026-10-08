"""Cost probe for Soft Selection, headless (WP-SOFT-01 S1).

Usage (from the repo root, Windows and Linux alike; no window, no GL):
    python experiments/soft_selection/probe_cost.py
    python experiments/soft_selection/probe_cost.py --steps 200
    python experiments/soft_selection/probe_cost.py --assets head_basemesh

Measures, per asset, radius (5 / 15 / 30 % of the mesh bounding radius) and metric:

- influence ms   median wall time of one `compute_influence()` call (`--repeat` runs)
- influenced     number of vertices with w > 0 (the operation's vertex set)
- move/rotate/scale ms   mean wall time of one `update()` over `--steps` steps
- core move ms   plain Core `MoveOperation` on the same vertex set (all w = 1), for scale

Seeds: the front-most vertex (max z) and its one-ring - a small, typical primary
selection. Curve `smooth` throughout (the curve does not change which vertices are
influenced, only their weights). Every gesture ends with `cancel()`, so all rows see
the unmodified asset. Only the CPU side of the operation is measured; there is no
viewport sync, buffer upload or draw in this number. Numbers from a container must
be labelled as such (`docs/architecture/REFERENCE_HARDWARE.md` §4); the reference PC
decides. Output is plain ASCII so it pastes cleanly from a Windows console.
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Stage 0 (script start): experiments/ on sys.path, as in symmetry_lab/run.py.
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from soft_selection._paths import ensure_paths  # noqa: E402

ensure_paths()

from core import HistoryStack, MoveOperation, OperationContext, VertexId  # noqa: E402
from loaders.assets import asset_names, asset_path  # noqa: E402
from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402

from soft_selection.influence import compute_influence, primary_pivot  # noqa: E402
from soft_selection.weighted_ops import (  # noqa: E402
    SoftMoveOperation,
    SoftRotateOperation,
    SoftScaleOperation,
    _InfluenceView,
)

DEFAULT_ASSETS = ("head_basemesh", "man_with_shoes_basemesh")
DEFAULT_STEPS = 60
DEFAULT_REPEAT = 5
RADIUS_FRACTIONS = (0.05, 0.15, 0.30)
METRICS = ("euclidean", "geodesic")
#: Per-step gesture inputs: small, so 60 steps stay a plausible drag.
MOVE_STEP = (0.001, 0.0005, 0.0)
ROTATE_AXIS = (0.0, 1.0, 0.0)
ROTATE_STEP = 0.005  # rad
SCALE_STEP = 1.002


@dataclass(frozen=True)
class Row:
    fraction: float
    radius: float
    metric: str
    influence_ms: float
    influenced: int
    move_ms: float
    rotate_ms: float
    scale_ms: float
    core_move_ms: float


@dataclass(frozen=True)
class AssetResult:
    asset: str
    vertex_count: int
    bounding_radius: float
    seeds: int
    seed_vertex: VertexId
    rows: list[Row]


def cpu_name() -> str:
    """CPU model name: Windows registry, Linux /proc/cpuinfo, else `platform.processor()`.
    (Pattern copied from `symmetry_lab/probe_drag_cost.py`, not imported.)"""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            ) as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def machine_info() -> list[str]:
    return [
        f"Platform: {platform.platform()}",
        f"CPU: {cpu_name()} ({os.cpu_count()} logical cores)",
        f"Python: {platform.python_version()} ({platform.python_implementation()})",
    ]


def pick_seeds(mesh) -> tuple[VertexId, set[VertexId]]:
    """Front-most vertex (max z, lowest id on ties) plus its one-ring."""
    front = max(mesh.all_vertex_ids(), key=lambda v: (mesh.vertex_position(v)[2], -int(v)))
    seeds = {front}
    for eid in mesh.vertex_edges(front):
        seeds.update(mesh.edge_vertices(eid))
    return front, seeds


def _per_update_ms(op, steps: int, **update_kwargs) -> float:
    op.begin()
    start = time.perf_counter()
    for _ in range(steps):
        op.update(**update_kwargs)
    elapsed = time.perf_counter() - start
    op.cancel()
    return elapsed * 1000.0 / steps


def probe_asset(asset: str, steps: int, repeat: int) -> AssetResult:
    mesh = build_core_scene_from_obj(asset_path(asset)).mesh
    _, bounding_radius = mesh_center_and_radius(mesh)
    front, seeds = pick_seeds(mesh)
    pivot = primary_pivot(mesh, seeds)
    history = HistoryStack()
    rows: list[Row] = []
    for fraction in RADIUS_FRACTIONS:
        radius = fraction * bounding_radius
        for metric in METRICS:
            samples = []
            influence: dict = {}
            for _ in range(repeat):
                t0 = time.perf_counter()
                influence = compute_influence(mesh, seeds, radius, metric=metric, curve="smooth")
                samples.append((time.perf_counter() - t0) * 1000.0)

            def ctx(**params) -> OperationContext:
                return OperationContext(
                    target=mesh,
                    selection=_InfluenceView(set(influence)),
                    history=history,
                    params={"influence": influence, "pivot": pivot, **params},
                )

            move_ms = _per_update_ms(SoftMoveOperation(ctx()), steps, delta=MOVE_STEP)
            rotate_ms = _per_update_ms(
                SoftRotateOperation(ctx()), steps, axis=ROTATE_AXIS, angle=ROTATE_STEP
            )
            scale_ms = _per_update_ms(SoftScaleOperation(ctx()), steps, factor=SCALE_STEP)
            core_ms = _per_update_ms(
                MoveOperation(
                    OperationContext(
                        target=mesh, selection=_InfluenceView(set(influence)), history=history
                    )
                ),
                steps,
                delta=MOVE_STEP,
            )
            rows.append(
                Row(
                    fraction, radius, metric, statistics.median(samples), len(influence),
                    move_ms, rotate_ms, scale_ms, core_ms,
                )
            )
    return AssetResult(
        asset, len(mesh.all_vertex_ids()), bounding_radius, len(seeds), front, rows
    )


def format_result(result: AssetResult, steps: int) -> list[str]:
    lines = [
        f"Asset {result.asset}: {result.vertex_count} vertices, bounding radius "
        f"{result.bounding_radius:.4f}, seeds {result.seeds} (vertex {int(result.seed_vertex)} "
        f"+ one-ring), {steps} update steps per gesture",
        "  radius          metric     influence_ms  influenced  move_ms  rotate_ms"
        "  scale_ms  core_move_ms",
    ]
    for r in result.rows:
        lines.append(
            f"  {r.fraction * 100:3.0f}% {r.radius:8.4f}  {r.metric:<9}  {r.influence_ms:12.3f}"
            f"  {r.influenced:10d}  {r.move_ms:7.3f}  {r.rotate_ms:9.3f}  {r.scale_ms:8.3f}"
            f"  {r.core_move_ms:12.3f}"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--assets", nargs="+", default=list(DEFAULT_ASSETS),
                        help=f"asset names (registry: {', '.join(asset_names())})")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS,
                        help=f"update() steps per gesture (default {DEFAULT_STEPS})")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT,
                        help=f"influence computations per row, median reported (default {DEFAULT_REPEAT})")
    args = parser.parse_args(argv)
    unknown = [a for a in args.assets if a not in asset_names()]
    if unknown:
        parser.error(f"unknown asset(s) {unknown}; valid: {', '.join(asset_names())}")
    if args.steps < 1 or args.repeat < 1:
        parser.error("--steps and --repeat must be >= 1")

    print("Soft Selection cost probe (WP-SOFT-01 S1), CPU only, times in ms")
    for line in machine_info():
        print(line)
    for asset in args.assets:
        print()
        for line in format_result(probe_asset(asset, args.steps, args.repeat), args.steps):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
