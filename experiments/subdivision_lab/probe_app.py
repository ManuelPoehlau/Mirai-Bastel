"""SubD on the Production app path: what one W-drag move and one topology change cost (2026-10-23).

Usage (repo root; opens a hidden pyglet window; headless: prefix `xvfb-run -a`):
    python experiments/subdivision_lab/probe_app.py
    python experiments/subdivision_lab/probe_app.py --assets head_basemesh --levels 2 3 --moves 60

Builds `Application` with `src/main.py`'s `GL_TYPES` (real `GLRenderStore` + GL overlays), switches
the SubD preview on (view `cage`, then `iso` for the frame rows), selects the front-most vertex and
drags it with W. Per move, separately (median / p95 over `--moves`):

- transform  `pointer_motion` (Move step on the control mesh)
- provider   `SubdSurfaceProvider.sync` inside `Viewport.sync` (journal + stencils + derived mesh writes)
- upload     the surface `RenderMesh.sync` (GPU buffer patches of the moved derived vertices)
- sync       the whole `Viewport.sync` (includes provider, upload, control mesh, overlays)
- frame      `Viewport.render()` + `glFinish()` (software rasteriser in a container)

Once per row: a topology change (`apply_mesh_change` splitting one edge) — provider rebuild
(topology + stencils + derived mesh) and the surface's GPU rebuild, and the level switch.
Numbers from a container are not reference-PC numbers (`docs/architecture/REFERENCE_HARDWARE.md` §4).
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

from subdivision_lab._paths import ensure_paths  # noqa: E402

ensure_paths()


def _stats(samples: list[float]) -> str:
    s = sorted(samples)
    p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
    return f"{statistics.median(s):8.2f} {p95:8.2f}"


def _wrap_timer(obj, name: str, bucket: list):
    original = getattr(obj, name)

    def timed(*args, **kwargs):
        t = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            bucket.append((time.perf_counter() - t) * 1000.0)

    setattr(obj, name, timed)


def run(asset: str, level: int, moves: int, src_main) -> list[str]:
    from pyglet import gl

    from loaders.assets import asset_path
    from mirai.application import Application
    from mirai.interaction.input import Input

    window = run.window
    W, H = window.width, window.height
    app = Application()
    app.init_scene("obj", obj_path=asset_path(asset), **src_main.GL_TYPES)
    app.frame_scene()
    app.set_viewport_size(W, H)
    vp = app.viewport
    app.key_press(Input("key", "v"))
    vp.sync()  # first build at the default level, so the face limit below is known
    refusal = app.subdivision.provider.set_level(level)
    vp.sync()
    if refusal:
        return [f"| {asset} | {level} | {refusal} |"]
    provider_ms: list = []
    _wrap_timer(app.subdivision.provider, "sync", provider_ms)

    mesh = vp.mesh
    front = max(mesh.all_vertex_ids(), key=lambda v: mesh.vertex_position(v)[2])
    app.selection.set({front})
    vp.on_selection_changed()
    vp.sync()
    surface_rm = vp.surface_render_mesh
    upload_ms: list = []
    _wrap_timer(surface_rm, "sync", upload_ms)

    rows = {"transform": [], "provider": [], "upload": [], "sync": [], "frame": []}
    x, y = W / 2, H / 2
    app.key_press(Input("key", "w"))
    for i in range(moves + 3):
        provider_ms.clear()
        upload_ms.clear()
        t0 = time.perf_counter()
        app.pointer_motion(x + 2, y, 2, 0)
        x += 2
        t1 = time.perf_counter()
        vp.sync()
        t2 = time.perf_counter()
        window.clear()
        vp.render()
        gl.glFinish()
        t3 = time.perf_counter()
        if i >= 3:  # warm-up: begin() of the gesture
            rows["transform"].append((t1 - t0) * 1000)
            rows["sync"].append((t2 - t1) * 1000)
            rows["frame"].append((t3 - t2) * 1000)
            rows["provider"].append(sum(provider_ms))
            rows["upload"].append(sum(upload_ms))
    app.key_release(Input("key", "w"))
    vp.sync()
    assert vp.surface_render_mesh is surface_rm, "a position-only drag rebuilt the surface"

    counts = app.subdivision.provider.derived_counts
    out = [f"| {asset} | {level} | {counts[1]} | " + " | ".join(
        _stats(rows[k]).replace("  ", " ").strip().replace(" ", " / ", 1) for k in rows) + " |"]

    # one topology change (split an edge through the app's host hook, one Undo step)
    edge = next(iter(mesh.all_edge_ids()))
    provider_ms.clear()
    t = time.perf_counter()
    app.apply_mesh_change("Split (probe)", lambda: (mesh.split_edge(edge), None)[1])
    vp.sync()
    window.clear()
    vp.render()
    gl.glFinish()
    total = (time.perf_counter() - t) * 1000
    patched = "patched in place" if vp.surface_render_mesh is surface_rm else "fresh surface"
    out.append(f"|   topology change (split edge, {patched}): provider {sum(provider_ms):.1f} ms, "
               f"level build {app.subdivision.provider.last_build_ms:.1f} ms, whole step incl. frame {total:.1f} ms |")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--assets", nargs="+", default=["head_basemesh", "man_with_shoes_basemesh"])
    parser.add_argument("--levels", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--moves", type=int, default=60)
    parser.add_argument("--host", default="unlabeled")
    args = parser.parse_args(argv)

    import importlib

    import pyglet

    src_main = importlib.import_module("main")
    run.window = pyglet.window.Window(width=1280, height=800, visible=False)
    from pyglet import gl

    print(f"Host: {args.host} · GL_VERSION {gl.gl_info.get_version_string()} · GL_RENDERER {gl.gl_info.get_renderer()}")
    print(f"{args.moves} W-drag moves per row, ms as median / p95, 1280x800 hidden window")
    print("| asset | level | faces | transform | provider | upload | sync | frame |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for asset in args.assets:
        for level in args.levels:
            for line in run(asset, level, args.moves, src_main):
                print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
