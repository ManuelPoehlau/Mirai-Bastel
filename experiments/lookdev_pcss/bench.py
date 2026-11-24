"""GPU cost of the PCSS variants of the key's shadow in the real LookDev frame (2026-11-24; disposable; for the
reference PC, AD-039 §23.6 / Q-S8-3).

    python experiments/lookdev_pcss/bench.py                         # 1024x768, cage + SubD 1, framed + face
    python experiments/lookdev_pcss/bench.py --size 1920 1080
    python experiments/lookdev_pcss/bench.py --rounds 2 --frames 1   # container: a function check only

Set the NVIDIA driver to "prefer maximum performance" first (REFERENCE_HARDWARE §2), as for the room probe.

The frame is `Viewport.render()` as `main.py` calls it (overlays, eyes in the "full" tier), Gollum_Head_05 as saved,
LookDev open with studio "Dramatic" (key 70 / 20, rim and fill as the preset), the P3 effects shadow, eye_shadow,
dual_lobe, thickness, cube and „Weiches Licht“ (area_diffuse) on - the full P3 frame without maps and regions - at the
key sizes `--key-sizes` (default 0.45 = Manu's finding, and 1). Rows (`compare.VARIANTS`):
- P        production today (3 x 3 PCF twice: the key and the lifted lookup; the map at its effective resolution);
- F        production's lookup with the map at full resolution (only the map changes);
- K<b>c/<p> the recommended PCSS (`compare.KC`: one blocker search of b raw fetches shared by both lookups, then p
           bilinear-compare fetches per lookup = b + 2p fetches where a blocker is found, b where none is: the early
           out); K16c = K16c/16; /9g a 3 x 3 grid PCF; -nb without the early out (always b + 2p); -eff on the effective
           map (the resolution of today).
Each variant's programs are compiled up front; the rows are interleaved (every round runs each variant `--frames`
times after one untimed frame, which re-renders the map when its resolution changes) and reported as the median of
all rounds; GPU by GL_TIME_ELAPSED. Prints the commit, the working-tree state and the GL renderer: a run in a
container (llvmpipe) is a function check, not a measurement of the 9800 GTX.
"""

from __future__ import annotations

import argparse
import ctypes
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compare as cp  # noqa: E402  (sets the paths)

import area_glsl as ag  # noqa: E402
import pcss_glsl as pg  # noqa: E402

ROWS = ("P", "F", "K8c/16", "K16c", "K24c/16", "K16c/32", "K16c/9g", "K16c-nb", "K16c-eff")
EFFECTS = ("shadow", "eye_shadow", "dual_lobe", "thickness", "cube", "area_diffuse")
AREA = ag.Variant("A")  # production's own diffuse (with area_diffuse on: S8's B) and specular
WARMUP = 5
FRAME_BUDGET_MS = 1000.0 / 30.0


def switch(window, size, query, app, name, programs) -> None:
    """Make `name` current: its patch (the map's resolution, unit 7) and its compiled programs; one untimed frame."""
    from drag_cost.probe_lookdev import timed_frame

    pg.install(AREA, cp.VARIANTS[name])
    app.viewport.lookdev_pass.programs = programs
    app.update_viewport(0.0)
    timed_frame(window, size, query, app.viewport.render)


def compile_all(window, size, query, app, names) -> dict:
    caches = {}
    for name in names:
        switch(window, size, query, app, name, {})
        for _ in range(2):
            switch(window, size, query, app, name, app.viewport.lookdev_pass.programs)
        caches[name] = app.viewport.lookdev_pass.programs
    return caches


def measure(window, size, query, app, caches, rounds: int, frames: int) -> dict:
    from drag_cost.probe_lookdev import timed_frame

    gpu = {name: [] for name in caches}
    wall = {name: [] for name in caches}
    for r in range(WARMUP + rounds):
        for name, programs in caches.items():
            switch(window, size, query, app, name, programs)
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
    parser.add_argument("--key-sizes", default="0.45,1")
    parser.add_argument("--variants", default=",".join(ROWS))
    args = parser.parse_args(argv)
    names = [n for n in args.variants.split(",") if n]
    if "P" not in names:
        names.insert(0, "P")

    from pyglet import gl

    from drag_cost._paths import source_state
    from drag_cost.probe_drag_gl import machine_info
    from drag_cost.probe_lookdev import build_app, set_surface, set_view, timed_frame, triangles
    from viewport.lookdev_optics import LookdevEffects

    window, app = build_app(tuple(args.size))
    size = window.get_framebuffer_size()
    print(f"lookdev_pcss bench, {size[0]}x{size[1]}, {args.rounds} rounds x {args.frames} frames per variant after "
          f"{WARMUP} (interleaved), key sizes {args.key_sizes}, effects {', '.join(EFFECTS)}")
    for line in machine_info(gl.gl_info.get_version_string(), gl.gl_info.get_renderer()):
        print(line)
    print(f"Source: {source_state()}")
    if any(s in gl.gl_info.get_renderer().lower() for s in ("llvmpipe", "softpipe")):
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
    for name in LookdevEffects.names():
        app.set_lookdev_effect(name, name in EFFECTS)
    errors = 0
    try:
        for surface in args.surfaces.split(","):
            if not set_surface(app, surface):
                print(f"[{surface}] could not be set - skipped")
                continue
            for view in args.views.split(","):
                set_view(app, view)
                for key_size in (float(k) for k in args.key_sizes.split(",")):
                    app.set_lookdev_light("key", size=key_size)
                    for _ in range(20):
                        app.update_viewport(0.0)
                        if not app.lookdev.preparing:
                            break
                        timed_frame(window, size, query, app.viewport.render)
                    caches = compile_all(window, size, query, app, names)
                    result = measure(window, size, query, app, caches, args.rounds, args.frames)
                    drawn = app.viewport.surface_render_mesh or app.viewport.render_mesh
                    print()
                    print(f"[{surface}, {view}, key size {key_size:g}] the head draws {triangles(drawn)} triangles")
                    base = result["P"][0]
                    for name, (p50, lo, hi, w) in result.items():
                        print(f"  {name:<7} GPU p50 {p50:7.3f} ms (min {lo:7.3f}, max {hi:7.3f})  "
                              f"{100.0 * p50 / FRAME_BUDGET_MS:5.1f} % of 33.3 ms  vs P {p50 - base:+7.3f} ms   "
                              f"CPU p50 {w:7.2f} ms")
                    for programs in caches.values():
                        for program in programs.values():
                            program.delete()
                    app.viewport.lookdev_pass.programs = {}
                    err = gl.glGetError()
                    errors += err != 0
                    if err:
                        print(f"  glGetError 0x{err:04X}")
    finally:
        pg.uninstall()
        ag.uninstall()
        app.close_lookdev()
    print()
    print(f"glGetError at the end: 0x{gl.glGetError():04X} ({errors} blocks with an error)")
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
