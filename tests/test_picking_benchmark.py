"""Picking speed benchmark (WP-06 B8), in the spirit of
`tests/test_benchmark_scenarios.py`: diagnostic timing, not a performance
claim (see that module's docstring) - the numbers are reported in the B8
handoff response, not asserted here as a hard threshold (machine-dependent).

Measures time per simulated pointer move on the head basemesh (`examples/
meshes/head_basemesh.obj`, ~326 vertices / 648 edges / 324 quad faces) for
vertex/edge/face hover and `knife_pick`, before (no cache - the pre-B8
exhaustive per-call path, still reachable via `cache=None`) and after
(a warm `PickCache`, refreshed once per simulated camera/mesh state instead
of once per move).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from mirai.viewport.camera import OrbitCamera
from mirai.viewport.picking import pick_face, pick_nearest_edge, pick_nearest_vertex
from mirai.viewport.picking_cache import PickCache
from mirai.topology.knife_pick import knife_pick

WIDTH, HEIGHT = 800, 600
N_MOVES = 200

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _REPO_ROOT / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))
_HEAD_ASSET = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"


def _load_head_mesh():
    from mirai.scene_factory import build_core_scene_from_obj

    return build_core_scene_from_obj(_HEAD_ASSET).mesh


def _move_positions(n=N_MOVES):
    """A pseudo-random but deterministic walk of cursor positions across the
    viewport, simulating a sequence of pointer moves at a fixed camera/mesh
    state (the realistic hover case B8 targets)."""
    import random

    rng = random.Random(1234)
    return [(rng.uniform(40, WIDTH - 40), rng.uniform(40, HEIGHT - 40)) for _ in range(n)]


def _time_per_move(fn, positions) -> float:
    start = time.perf_counter()
    for sx, sy in positions:
        fn(sx, sy)
    elapsed = time.perf_counter() - start
    return (elapsed / len(positions)) * 1000.0  # ms/move


@pytest.mark.skipif(not _HEAD_ASSET.is_file(), reason="head basemesh asset not found")
def test_report_picking_speed_before_and_after_cache():
    mesh = _load_head_mesh()
    camera = OrbitCamera(target=(0.0, 1.5, 0.0), distance=4.0)
    positions = _move_positions()
    cache = PickCache()
    cache.refresh(camera, mesh, WIDTH, HEIGHT)  # one warm-up, like a real hover session

    report = {}
    report["vertex_before_ms"] = _time_per_move(
        lambda sx, sy: pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT), positions
    )
    report["vertex_after_ms"] = _time_per_move(
        lambda sx, sy: pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache),
        positions,
    )
    report["edge_before_ms"] = _time_per_move(
        lambda sx, sy: pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT), positions
    )
    report["edge_after_ms"] = _time_per_move(
        lambda sx, sy: pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache),
        positions,
    )
    report["face_before_ms"] = _time_per_move(
        lambda sx, sy: pick_face(camera, mesh, sx, sy, WIDTH, HEIGHT), positions
    )
    report["face_after_ms"] = _time_per_move(
        lambda sx, sy: pick_face(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache), positions
    )
    report["knife_before_ms"] = _time_per_move(
        lambda sx, sy: knife_pick(camera, mesh, sx, sy, WIDTH, HEIGHT), positions
    )
    report["knife_after_ms"] = _time_per_move(
        lambda sx, sy: knife_pick(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache, occlusion=True),
        positions,
    )

    print("\n[B8 benchmark] head mesh, ms/pointer-move (diagnostic, not a performance claim):")
    for key, value in report.items():
        print(f"  {key}: {value:.4f} ms")

    # Generous sanity ceiling only - catches a catastrophic regression, not a
    # precision claim (machine-dependent; the PROVISIONAL 5 ms target from the
    # handoff is reported, not enforced, here).
    for key, value in report.items():
        assert value < 200.0, (key, value)
