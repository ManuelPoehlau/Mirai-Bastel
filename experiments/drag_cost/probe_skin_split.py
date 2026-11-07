"""M3 profiling split of one pose step on gollum_20k (AD-028 §5.4, handoff 2026-11-07).

Usage (from the repo root):
    python experiments/drag_cost/probe_skin_split.py
    python experiments/drag_cost/probe_skin_split.py --steps 60

Splits each pose step into four components:
  lbs           SkinSurface._recompute (pure LBS arithmetic + set_vertex_position writes)
  sync_geom     RenderMesh._sync_geometry (normal recomputation + GL uploads)
  draw          viewport.render() + glFinish()
  remainder     everything else: pointer_motion bone rotation, viewport.sync overhead,
                provider bookkeeping, dirty-flag plumbing
  total         sum of the above = one pointer_motion + update_viewport + render + glFinish
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

from drag_cost.probe_drag_gl import machine_info  # noqa: E402
from drag_cost.probe_morph_gl import build_app, rig_region, _key  # noqa: E402

STEPS = 60


def _stats(samples: list[float]) -> str:
    if not samples:
        return "n/a"
    p50 = statistics.median(samples)
    p95 = sorted(samples)[int(len(samples) * 0.95)]
    return f"p50={p50:.2f} p95={p95:.2f}"


def run_split(path: Path, share: int, steps: int) -> dict:
    """One case: build app, rig region, run `steps` pose steps, collect split."""
    from pyglet import gl

    import viewport.render_mesh as _rm_mod
    from mirai.skinning import SkinSurface

    window, app = build_app(path)
    rig_region(app, share)

    # -- monkeypatch accumulators (reset each step) ----------------------------
    _acc: dict[str, float] = {"lbs": 0.0, "sync_geom": 0.0}

    _orig_recompute = SkinSurface._recompute
    _orig_sync_geom = _rm_mod.RenderMesh._sync_geometry

    def _timed_recompute(self, candidates):
        t0 = time.perf_counter()
        result = _orig_recompute(self, candidates)
        _acc["lbs"] += (time.perf_counter() - t0) * 1000.0
        return result

    def _timed_sync_geom(self):
        t0 = time.perf_counter()
        _orig_sync_geom(self)
        _acc["sync_geom"] += (time.perf_counter() - t0) * 1000.0

    SkinSurface._recompute = _timed_recompute
    _rm_mod.RenderMesh._sync_geometry = _timed_sync_geom

    # warm up
    app.pointer_motion(560, 300, 0.0, 0.0)
    app.key_press(_key("5"))
    e = _key("e")
    app.key_press(e)
    app.pointer_motion(560, 296, 0.0, -4.0)
    app.update_viewport(0.0)
    app.viewport.render()
    gl.glFinish()

    lbs_s, sync_geom_s, draw_s, remainder_s, total_s = [], [], [], [], []

    for i in range(steps):
        _acc["lbs"] = 0.0
        _acc["sync_geom"] = 0.0
        dy = -4.0 if (i // 20) % 2 == 0 else 4.0

        t0 = time.perf_counter()
        app.pointer_motion(560, 296, 0.0, dy)
        t1 = time.perf_counter()
        app.update_viewport(0.0)
        t2 = time.perf_counter()
        app.viewport.render()
        gl.glFinish()
        t3 = time.perf_counter()

        t_pointer = (t1 - t0) * 1000.0
        t_update = (t2 - t1) * 1000.0
        t_draw = (t3 - t2) * 1000.0
        t_total = (t3 - t0) * 1000.0

        lbs = _acc["lbs"]
        sg = _acc["sync_geom"]
        # remainder = everything in pointer_motion + update_viewport that isn't lbs or sync_geom
        rem = t_pointer + t_update - lbs - sg

        lbs_s.append(lbs)
        sync_geom_s.append(sg)
        draw_s.append(t_draw)
        remainder_s.append(rem)
        total_s.append(t_total)

    app.key_release(e)
    app.key_press(_key("6"))
    app.key_press(_key("5"))

    # restore
    SkinSurface._recompute = _orig_recompute
    _rm_mod.RenderMesh._sync_geometry = _orig_sync_geom
    window.close()

    count = len(app.scene.mesh.all_vertex_ids())
    return {
        "label": f"{path.stem}  {count} V  region {share:>3} %",
        "lbs": lbs_s,
        "sync_geom": sync_geom_s,
        "draw": draw_s,
        "remainder": remainder_s,
        "total": total_s,
        "count": count,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=STEPS)
    args = ap.parse_args()

    path = REPO_ROOT / "examples" / "meshes" / "gollum_20k.obj"

    import pyglet

    window0 = pyglet.window.Window(width=1, height=1, visible=False)
    from pyglet.gl import gl_info
    header = machine_info(gl_info.get_version_string(), gl_info.get_renderer())
    window0.close()

    header.append(f"Pose-step split (AD-028 §5.4), {args.steps} steps per row")
    header.append(f"{'Component':<14} {'p50 ms':>8} {'p95 ms':>8}   (of total step p50)")
    print("\n".join(header))

    for share in (5, 15):
        r = run_split(path, share, args.steps)
        t50 = statistics.median(r["total"])
        print(f"\n{r['label']}")
        print(f"  total          p50={statistics.median(r['total']):.2f}  p95={sorted(r['total'])[int(len(r['total'])*0.95)]:.2f} ms")
        for key, label in (("lbs", "lbs"), ("sync_geom", "_sync_geometry"), ("draw", "gl draw"), ("remainder", "remainder")):
            vals = r[key]
            p50 = statistics.median(vals)
            p95 = sorted(vals)[int(len(vals) * 0.95)]
            pct = p50 / t50 * 100 if t50 > 0 else 0
            print(f"  {label:<16} p50={p50:.2f}  p95={p95:.2f} ms  ({pct:.0f} % of total p50)")


if __name__ == "__main__":
    main()
