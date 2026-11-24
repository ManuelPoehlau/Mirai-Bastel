"""GPU cost of the key's diffuse variants in the real LookDev frame (2026-11-24; disposable; for the reference PC).

    python experiments/lookdev_diffuse_area/bench.py                      # 1024x768, cage + SubD 1, framed + face
    python experiments/lookdev_diffuse_area/bench.py --size 1920 1080
    python experiments/lookdev_diffuse_area/bench.py --rounds 3           # container: a function check only

Set the NVIDIA driver to "prefer maximum performance" first (REFERENCE_HARDWARE §2), as for the room probe.

The frame is `Viewport.render()` as `main.py` calls it (overlays, eyes in the "full" tier), Gollum_Head_05 as saved,
LookDev open with studio "Dramatic" (key 70 / 20, key size 0.5 - the band is active - rim and fill as the preset) and
the P3 effects shadow, eye_shadow, dual_lobe, thickness and cube on (the full P3 frame without maps and regions).
Production's skin shader (A) against the variants, all compiled up front and swapped by the LookDev pass's program
cache, so a row measures shading only:
- A        production (`ld_wrap`);
- B        the quadratic horizon spline (one evaluation per light, the SHADOW block's key term included);
- B2       the exact sphere irradiance (acos, atan, three square roots per channel);
- C8, C16  8 / 16 directions on the emitter's cap;
- Ax16, Bx16  the same evaluated 16x per light (`Variant.repeat`): (Bx16 - Ax16) / 16 is B's own per-pixel cost with
           the timer noise divided by 16 - the number to trust when B - A is within the noise.
Rows are interleaved (every round runs each variant `--frames` times) and reported as the median of all rounds; GPU
by GL_TIME_ELAPSED. Prints the commit, the working-tree state and the GL renderer: a run in a container (llvmpipe)
is a function check, not a measurement of the 9800 GTX.
"""

from __future__ import annotations

import argparse
import ctypes
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (REPO / "src", REPO / "experiments", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import area_glsl as ag  # noqa: E402

VARIANTS = {"A": ag.Variant("A"), "B": ag.Variant("B"), "B2": ag.Variant("B2"),
            "C8": ag.Variant("C", samples=8), "C16": ag.Variant("C", samples=16),
            "Ax16": ag.Variant("A", repeat=16), "Bx16": ag.Variant("B", repeat=16)}
EFFECTS = ("shadow", "eye_shadow", "dual_lobe", "thickness", "cube")
KEY_SIZE = 0.5
WARMUP = 5
FRAME_BUDGET_MS = 1000.0 / 30.0


def compile_all(window, size, query, app, names) -> dict:
    """Each variant's skin programs, compiled by drawing frames with it installed; returns {name: program dict}."""
    from drag_cost.probe_lookdev import timed_frame

    passes = app.viewport.lookdev_pass
    caches = {}
    for name in names:
        ag.install(VARIANTS[name])
        passes.programs = {}
        for _ in range(3):
            app.update_viewport(0.0)
            timed_frame(window, size, query, app.viewport.render)
        caches[name] = passes.programs
    return caches


def measure(window, size, query, app, caches, rounds: int, frames: int) -> dict:
    from drag_cost.probe_lookdev import timed_frame

    passes = app.viewport.lookdev_pass
    gpu = {name: [] for name in caches}
    wall = {name: [] for name in caches}
    for r in range(WARMUP + rounds):
        for name, programs in caches.items():
            passes.programs = programs
            for _ in range(frames):
                app.update_viewport(0.0)
                g, w = timed_frame(window, size, query, app.viewport.render)
                if r >= WARMUP:
                    gpu[name].append(g)
                    wall[name].append(w)
    return {name: (statistics.median(gpu[name]), min(gpu[name]), max(gpu[name]), statistics.median(wall[name]))
            for name in caches}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--size", type=int, nargs=2, default=(1024, 768))
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--frames", type=int, default=3)
    parser.add_argument("--surfaces", default="cage,subd1")
    parser.add_argument("--views", default="framed,face")
    parser.add_argument("--variants", default=",".join(VARIANTS))
    args = parser.parse_args(argv)
    names = [n for n in args.variants.split(",") if n]
    if "A" not in names:
        names.insert(0, "A")

    from pyglet import gl

    from drag_cost._paths import source_state
    from drag_cost.probe_drag_gl import machine_info
    from drag_cost.probe_lookdev import build_app, set_surface, set_view, timed_frame, triangles
    from viewport.lookdev_optics import LookdevEffects

    window, app = build_app(tuple(args.size))
    size = window.get_framebuffer_size()
    print(f"lookdev_diffuse_area bench, {size[0]}x{size[1]}, {args.rounds} rounds x {args.frames} frames per variant "
          f"after {WARMUP} (interleaved), key size {KEY_SIZE}, effects {', '.join(EFFECTS)}")
    for line in machine_info(gl.gl_info.get_version_string(), gl.gl_info.get_renderer()):
        print(line)
    print(f"Source: {source_state()}")
    if "llvmpipe" in gl.gl_info.get_renderer().lower() or "softpipe" in gl.gl_info.get_renderer().lower():
        print("NOTE: software renderer - a function check, NOT a measurement of the reference GPU")
    query = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(query))
    app.open_lookdev()
    for _ in range(20):
        app.update_viewport(0.0)
        if not app.lookdev.preparing:
            break
        timed_frame(window, size, query, app.viewport.render)
    app.set_lookdev_studio_preset("Dramatic")
    app.set_lookdev_light("key", size=KEY_SIZE)
    for name in LookdevEffects.names():
        app.set_lookdev_effect(name, name in EFFECTS)
    try:
        for surface in args.surfaces.split(","):
            if not set_surface(app, surface):
                print(f"[{surface}] could not be set - skipped")
                continue
            for view in args.views.split(","):
                set_view(app, view)
                for _ in range(20):
                    app.update_viewport(0.0)
                    if not app.lookdev.preparing:
                        break
                    timed_frame(window, size, query, app.viewport.render)
                caches = compile_all(window, size, query, app, names)
                result = measure(window, size, query, app, caches, args.rounds, args.frames)
                drawn = app.viewport.surface_render_mesh or app.viewport.render_mesh
                print()
                print(f"[{surface}, {view}] the head draws {triangles(drawn)} triangles")
                base = result["A"][0]
                for name, (p50, lo, hi, w) in result.items():
                    print(f"  {name:<5} GPU p50 {p50:7.3f} ms (min {lo:7.3f}, max {hi:7.3f})  "
                          f"{100.0 * p50 / FRAME_BUDGET_MS:5.1f} % of 33.3 ms  vs A {p50 - base:+7.3f} ms   "
                          f"CPU p50 {w:7.2f} ms")
                if "Ax16" in result and "Bx16" in result:
                    per = (result["Bx16"][0] - result["Ax16"][0]) / 16.0
                    print(f"  B's own cost from the x16 rows: (Bx16 - Ax16) / 16 = {per:+.3f} ms per frame "
                          f"(x 4 evaluations per pixel: 3 lights + the key's shadow term)")
                for programs in caches.values():
                    for program in programs.values():
                        program.delete()
                app.viewport.lookdev_pass.programs = {}
    finally:
        ag.uninstall()
        app.close_lookdev()
    print()
    print(f"glGetError at the end: 0x{gl.glGetError():04X}")
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
