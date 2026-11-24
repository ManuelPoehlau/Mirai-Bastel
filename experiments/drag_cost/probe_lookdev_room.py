"""LookDev room probe (AD-038 LD-1, 2026-11-19; AD-039 P3 rows since S1, 2026-11-22): what the built room costs in the
real app frame.

Usage (from the repo root; opens a hidden pyglet window):
    python experiments/drag_cost/probe_lookdev_room.py                 # 1024x768, 30 rounds
    python experiments/drag_cost/probe_lookdev_room.py --draws 5       # container: a function check
    python experiments/drag_cost/probe_lookdev_room.py --size 1920 1080
    python experiments/drag_cost/probe_lookdev_room.py --effects none  # the LD-1 rows only

Set the NVIDIA driver to "prefer maximum performance" first (as for `probe_lookdev.py`). The scene is
`scenes/Gollum_Head_05.mirai.json` as saved (the painted head is the edit object, two eyes; teeth and the older head
hidden), framed at the ¾ angle (`probe_lookdev.set_view("framed")`), surfaces `cage` (SubD off) and `subd1`.

Rows, `Viewport.render()` exactly as `main.py` calls it (overlays included), timed with GL_TIME_ELAPSED after 5
unmeasured rounds:
- `modelling`  the room closed: today's Worklight frame (the LD-D10 floor; compare with `probe_lookdev.py`'s
               `app render` and `probe_d3_acceptance.py` for E16);
- `lookdev`    the room open (`Application.open_lookdev`, Portrait, every object Neutral): background, the LookDev
               skin pass with the paint composite, the eyes' LOOKDEV variant in the "full" tier;
- `modelling after`  the room closed again: the Worklight frame must be what it was (LookDev leaves nothing behind).

P3 rows (AD-039 §4 / §11.2; `--effects` names the built effects to measure, default all, `none` = no P3 row). The room
is entered with the effects of `--effects` on; then every row switches the effects it needs (a switch that compiles
runs its preparation frames first, unmeasured):
- `lookdev`                every P3 effect off: the M1 frame (compare with the LD-1 room run);
- `lookdev +shadow`        S1, a still pose: the key's map renders once, the lookup every frame (skin and teeth; the
                           eyes unshadowed, `eye_shadow` off);
- `lookdev +shadow +eyes`  S2 (AD-039 §5): the same with the eyes in the key's shadow (`eye_shadow`; target <= +0.5 ms
                           against `lookdev +shadow`, §2.5);
- `lookdev +dual`          S3 (AD-039 §6): the skin's highlight from the three lights as two lobes, every other effect
                           off (target <= +0.5 ms against `lookdev`, §2.5);
- `lookdev +shadow +thick` S4 (AD-039 §7): the shadow with the thickness (the map's raw depth, a second fetch; target
                           <= +0.5 ms against `lookdev +shadow`, §2.5);
- `lookdev +cube`          S5 (AD-039 §8): the skin's studio reflection from the prefiltered cube instead of the
                           analytic studio, every other effect off (target <= +0.3 ms against `lookdev`, §2.5;
                           P3-0 run 5 measured it cheaper);
- `cube prefilter`         S5's event cost: each studio preset switched to in turn (and back to the first), the
                           cube's build wall ms (`EnvCube.last_ms`: GPU prefilter + read-back + upload) and the
                           frame that follows the room's preparation;
- `lookdev +maps`          S7 (AD-039 §10): the head's material with three generated 2048² maps (roughness, normal,
                           translucency; written to a temporary folder, set in memory - the file is not touched),
                           every other effect off (target <= +0.4 ms per map against `lookdev`, §2.5);
- `lookdev +regions`       S6 (AD-039 §9): the head with a region material - the probe names its first polygroup
                           "Mouth" (in memory; `Gollum_Head_05` has only unnamed groups) and gives it "Mundinneres",
                           every other effect off (target <= +0.3 ms against `lookdev`, §2.5);
- `lookdev +shadow drag`   S1 with a morph weight step on the head every frame (the map re-renders each frame: a slow
                           morph or pose drag). The edit object gets a probe target in memory (the file is not touched);
- `... drag flush`         the same with `KeyShadow.flush` (a `glFlush` after the depth pass, before the background);
- `... drag pingpong`      the same with two maps used alternately (`KeyShadow(maps=2)`);
each with `KeyShadow.renders` over the row's frames (warm-up included: every frame for a drag, 0 for a still pose).

Entering (first in the process, then once more):
- `open_lookdev` wall ms (display values, sync_views, the LookDraws);
- the shader preparation behind the status line (`Viewport.prepare_lookdev`): programs compiled and their ms - cold
  the first time, cached the second;
- the ticks until the first LookDev frame (`update_viewport`; the first one syncs the UV request on the head's drawn
  surface, `_triangle_uvs_flat`; the last one compiles);
- the first LookDev frame (GPU and wall ms).

Plain ASCII output; prints the commit and the working-tree state. Changes nothing in `src/`.
"""

from __future__ import annotations

import argparse
import ctypes
import statistics
import sys
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import ensure_paths  # noqa: E402

ensure_paths()

WARMUP_ROUNDS = 5
DEFAULT_DRAWS = 30
SURFACES = ("cage", "subd1")
FRAME_BUDGET_MS = 1000.0 / 30.0
#: A P3 effect's row: its label and the effects it switches on (an effect that needs another one switches both).
EFFECT_ROWS = {"shadow": ("lookdev +shadow", ("shadow",)),
               "eye_shadow": ("lookdev +shadow +eyes", ("shadow", "eye_shadow")),
               "dual_lobe": ("lookdev +dual", ("dual_lobe",)),
               "thickness": ("lookdev +shadow +thick", ("shadow", "thickness")),
               "cube": ("lookdev +cube", ("cube",)),
               "regions": ("lookdev +regions", ("regions",)),
               "maps": ("lookdev +maps", ("maps",)),
               "area_diffuse": ("lookdev +area", ("area_diffuse",)),
               "soft_shadow": ("lookdev +shadow +soft", ("shadow", "soft_shadow"))}
#: S6's probe region (AD-039 §9): the name the probe gives the edit object's first polygroup, and its material.
PROBE_REGION = "Mouth"
PROBE_REGION_MATERIAL = "Mundinneres"
#: S7's probe maps: their side in pixels (AD-039 §10: "three 2048² test maps, generated by the probe").
PROBE_MAP_SIZE = 2048


def probe_map_images(size: int = PROBE_MAP_SIZE) -> dict:
    """AD-039 §10: three test maps as (size, size, 4) uint8 RGBA - a roughness noise, a normal map of round bumps and
    a translucency gradient (deterministic)."""
    import numpy as np

    y, x = np.mgrid[0:size, 0:size].astype(np.float64) / size
    rng = np.random.default_rng(39)
    grey = np.clip(0.75 + 0.25 * rng.standard_normal((size // 16, size // 16)), 0.0, 1.0)
    grey = np.kron(grey, np.ones((16, 16)))
    cells = 32.0
    fx, fy = (x * cells) % 1.0 - 0.5, (y * cells) % 1.0 - 0.5
    bump = np.clip(1.0 - 4.0 * (fx * fx + fy * fy), 0.0, 1.0)
    tilt_x, tilt_y = -fx * bump, -fy * bump
    normal = np.stack([tilt_x, tilt_y, np.ones_like(x)], axis=-1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)

    def rgba(rgb):
        out = np.empty((size, size, 4), np.uint8)
        out[..., :3] = np.clip(np.round(rgb * 255.0), 0, 255)
        out[..., 3] = 255
        return out

    return {"roughness": rgba(np.repeat(grey[..., None], 3, axis=-1)),
            "normal": rgba(normal * (128.0 / 255.0) + 128.0 / 255.0),
            "translucency": rgba(np.repeat((0.3 + 0.7 * y)[..., None], 3, axis=-1))}


def probe_maps(app, folder: Path) -> list[str]:
    """Write the probe maps into `folder` and give them to the edit object's LookDev material (in memory, one Undo
    step each). Returns what was set."""
    from mirai.iris_import import encode_png

    folder.mkdir(parents=True, exist_ok=True)
    done = []
    for kind, image in probe_map_images().items():
        path = folder / f"probe_{kind}.png"
        path.write_bytes(encode_png(image))
        if app.set_lookdev_map(kind, path):
            done.append(kind)
    return done


def probe_region(app) -> str | None:
    """AD-039 §9: name the edit object's first polygroup `PROBE_REGION` and give it `PROBE_REGION_MATERIAL` (in memory:
    the regions value and one Undo step; the file is not touched). Returns what was done, None without a polygroup."""
    from mirai import regions as face_regions

    mesh = app.scene.edit_object.mesh
    if mesh.face_regions is None or not mesh.face_regions.regions:
        return None
    first = mesh.face_regions.regions[0]
    if first.name != PROBE_REGION:
        mesh.face_regions = face_regions.renamed(mesh.face_regions, first.name, PROBE_REGION)
    app.set_lookdev_area(PROBE_REGION)
    done = app.set_lookdev_material(PROBE_REGION_MATERIAL)
    app.set_lookdev_area(None)
    if not done:
        return None
    live = len(face_regions.live_faces(mesh, PROBE_REGION))
    return f"{first.name!r} -> {PROBE_REGION!r} ({live} faces), {PROBE_REGION_MATERIAL!r}"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--size", type=int, nargs=2, default=(1024, 768), metavar=("W", "H"))
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    parser.add_argument("--surfaces", default=",".join(SURFACES))
    parser.add_argument("--effects", default=None,
                        help="AD-039: the P3 effects to measure, comma separated, or 'none' (default: every built one)")
    args = parser.parse_args(argv)
    args.surfaces = tuple(s for s in args.surfaces.split(",") if s)
    if args.draws < 1 or not set(args.surfaces) <= set(SURFACES):
        parser.error("--draws >= 1, --surfaces from cage,subd1")
    from viewport.lookdev_optics import LookdevEffects

    built = LookdevEffects.names()
    if args.effects is None:
        args.effects = built
    elif args.effects == "none":
        args.effects = ()
    else:
        args.effects = tuple(e for e in args.effects.split(",") if e)
        if not set(args.effects) <= set(built):
            parser.error(f"--effects from {','.join(built)} or none")
    return args


def summary(values) -> tuple[float, float, float]:
    return statistics.median(values), min(values), max(values)


def frame(window, size, query, app) -> tuple[float, float]:
    """One cleared frame of `Viewport.render()` (as `main.on_draw` after its clear): (GPU ms, wall ms)."""
    from drag_cost.probe_lookdev import timed_frame

    return timed_frame(window, size, query, app.viewport.render)


def rounds(window, size, query, app, draws: int, step=None) -> tuple[list[float], list[float]]:
    """`draws` measured frames after `WARMUP_ROUNDS`; `step(i)` (a drag) runs before each frame's tick."""
    gpu, wall = [], []
    for i in range(WARMUP_ROUNDS + draws):
        if step is not None:
            step(i)
        app.update_viewport(0.0)
        g, w = frame(window, size, query, app)
        if i >= WARMUP_ROUNDS:
            gpu.append(g)
            wall.append(w)
    return gpu, wall


def row(name: str, gpu, wall, floor: float | None = None) -> str:
    p50, lo, hi = summary(gpu)
    text = (f"  {name:<29} GPU p50 {p50:7.2f} ms (min {lo:6.2f}, max {hi:6.2f})  {100.0 * p50 / FRAME_BUDGET_MS:5.1f} % "
            f"of 33.3 ms   CPU p50 {statistics.median(wall):7.2f} ms")
    if floor is not None:
        text += f"   vs modelling {p50 - floor:+6.2f} ms"
    return text


# -- AD-039 P3 rows -------------------------------------------------------------------------------------------------

def set_effects(window, size, query, app, names) -> None:
    """Switch the P3 effects to exactly `names`; a switch that compiles runs its preparation frames (not measured)."""
    from viewport.lookdev_optics import LookdevEffects

    for name in LookdevEffects.names():
        app.set_lookdev_effect(name, name in names)
    for _ in range(10):
        if not app.lookdev.preparing:
            break
        app.update_viewport(0.0)
        frame(window, size, query, app)
    assert not app.lookdev.preparing and app.viewport.lookdev_state.effects == app.lookdev.studio.effects


def shadow_renders(app) -> int:
    passes = app.viewport._lookdev_pass
    shadow = passes.shadow if passes is not None else None
    return shadow.renders if shadow is not None else 0


def probe_target(app):
    """A morph target on the edit object, in memory only: the lower half drops and comes forward (a jaw); the drag rows
    step its weight every frame."""
    from core import PointLayerInfo

    mesh = app.scene.edit_object.mesh
    lid = mesh.add_point_layer(PointLayerInfo("probe drag (AD-039 S1)"))
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    low, high = min(ys), max(ys)
    mid = (low + high) / 2.0
    for v in mesh.all_vertex_ids():
        y = mesh.vertex_position(v)[1]
        if y < mid:
            s = (mid - y) / (mid - low)
            mesh.set_layer_value(lid, v, (0.0, -0.08 * s * (high - low), 0.05 * s * (high - low)))
    return lid


def cube_rows(window, size, query, app) -> list[str]:
    """AD-039 §8 / §11.2: the cube's build on a studio preset switch (`cube` on alone): per preset the build's wall ms
    and the frame after the preparation."""
    from mirai.lookdev_presets import PRESET_NAMES

    set_effects(window, size, query, app, ("cube",))
    first = app.lookdev.studio.preset
    lines = []
    for name in [n for n in PRESET_NAMES if n != first] + [first]:
        cube = app.viewport.lookdev_pass.cube
        before = cube.prefilters if cube is not None else 0
        app.set_lookdev_studio_preset(name)
        for _ in range(10):
            if not app.lookdev.preparing:
                break
            app.update_viewport(0.0)
            frame(window, size, query, app)
        gpu, wall = frame(window, size, query, app)
        cube = app.viewport.lookdev_pass.cube
        lines.append(f"  cube prefilter {name:<12} build {cube.last_ms:7.2f} ms wall (prefilters "
                     f"+{cube.prefilters - before})   next frame GPU {gpu:6.2f} ms   CPU {wall:6.2f} ms")
    return lines


def p3_rows(window, size, query, app, draws: int, effects, floor: float, lid) -> list[str]:
    """AD-039 §11.2: `lookdev` (every effect off), one row per effect (with the effects it needs), the shadow's drag
    rows."""
    from viewport.lookdev_shadow import KeyShadow

    lines = []

    def measured(name, names, step=None, shadow=None):
        set_effects(window, size, query, app, names)
        passes = app.viewport.lookdev_pass
        if shadow is not None:
            if passes.shadow is not None:
                passes.shadow.release()
            passes.shadow = shadow
        before = shadow_renders(app)
        gpu, wall = rounds(window, size, query, app, draws, step)
        lines.append(row(name, gpu, wall, floor) + f"   KeyShadow.renders {shadow_renders(app) - before} in "
                     f"{WARMUP_ROUNDS + draws} frames")

    measured("lookdev", ())
    for name in effects:
        label, names = EFFECT_ROWS.get(name, (f"lookdev +{name}", (name,)))
        measured(label, names)
    if "cube" in effects:
        lines.extend(cube_rows(window, size, query, app))
    if "shadow" in effects:
        def step(i):
            app.set_morph_weight(20 + (i % 2) * 20 + (i // 2) % 3, lid, quiet=True)

        for suffix, shadow in (("", KeyShadow()), (" flush", KeyShadow(flush=True)),
                               (" pingpong", KeyShadow(maps=2))):
            measured(f"lookdev +shadow drag{suffix}", ("shadow",), step, shadow)
        app.set_morph_weight(0, lid, quiet=True)
        app.viewport.lookdev_pass.shadow.release()
        app.viewport.lookdev_pass.shadow = None
    set_effects(window, size, query, app, tuple(effects))
    return lines


def enter(window, size, query, app, label: str) -> list[str]:
    """Open the room and drive the ticks until its first LookDev frame; what each step costs."""
    viewport = app.viewport
    start = time.perf_counter()
    app.open_lookdev()
    open_ms = (time.perf_counter() - start) * 1e3
    needed = bool(app.lookdev.preparing)
    prepare_ms, compiled = 0.0, 0
    original = viewport.prepare_lookdev

    def timed():
        nonlocal prepare_ms, compiled
        t = time.perf_counter()
        compiled = original()
        prepare_ms = (time.perf_counter() - t) * 1e3
        return compiled

    viewport.prepare_lookdev = timed
    ticks = []
    while True:
        start = time.perf_counter()
        app.update_viewport(0.0)  # the first tick syncs the UV request (`Viewport.sync`, `_triangle_uvs_flat`)
        ticks.append((time.perf_counter() - start) * 1e3)
        if not app.lookdev.preparing:
            break
        frame(window, size, query, app)  # a frame that shows the status line (still the Worklight)
    del viewport.prepare_lookdev
    gpu, wall = frame(window, size, query, app)
    assert viewport.shading == "lookdev"
    tick_text = ", ".join(f"{t:.1f}" for t in ticks)
    return [f"  {label}: open_lookdev {open_ms:.1f} ms; ticks until the first LookDev frame [{tick_text}] ms (the "
            f"first holds the UV request); programs compiled {compiled} in {prepare_ms:.0f} ms "
            f"({'behind the status line' if needed else 'none needed'}); first LookDev frame GPU {gpu:.2f} ms, "
            f"wall {wall:.1f} ms"]


def main(argv=None) -> int:
    import pyglet
    from pyglet import gl

    from drag_cost._paths import source_state
    from drag_cost.probe_drag_gl import machine_info
    from drag_cost.probe_lookdev import SCENE, build_app, set_surface, set_view, triangles

    args = parse_args(argv)
    window, app = build_app(tuple(args.size))
    size = window.get_framebuffer_size()
    print(f"LookDev room probe (AD-038 LD-1, 2026-11-19; AD-039 S1-S7), {size[0]}x{size[1]}, {args.draws} rounds "
          f"after {WARMUP_ROUNDS}")
    for line in machine_info(gl.gl_info.get_version_string(), gl.gl_info.get_renderer()):
        print(line)
    print(f"Source: {source_state()}")
    print(f"Scene: {SCENE.name}, edit object {app.scene.edit_object.name!r}, view framed (3/4)")
    print(f"P3 effects (AD-039): {', '.join(args.effects) or 'none'}")
    lid = probe_target(app) if "shadow" in args.effects else None
    if "maps" in args.effects:
        import tempfile

        folder = Path(tempfile.mkdtemp(prefix="lookdev_maps_probe_"))
        print(f"S7 probe maps ({PROBE_MAP_SIZE}²) in {folder}: {', '.join(probe_maps(app, folder)) or 'none set'}")
    if "regions" in args.effects:
        print(f"S6 probe region: {probe_region(app) or 'none (no polygroup on the edit object)'}")
    for name in args.effects:  # the room opens with these on; every other built effect off
        app.set_lookdev_effect(name, True)
    from viewport.lookdev_optics import LookdevEffects

    for name in set(LookdevEffects.names()) - set(args.effects):
        app.set_lookdev_effect(name, False)
    query = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(query))
    first = True
    for surface in args.surfaces:
        if not set_surface(app, surface):
            print(f"[{surface}] could not set the surface - skipped")
            continue
        set_view(app, "framed")
        drawn = app.viewport.surface_render_mesh or app.viewport.render_mesh
        print()
        print(f"[{surface}] the head draws {triangles(drawn)} triangles")
        gpu, wall = rounds(window, size, query, app, args.draws)
        floor = summary(gpu)[0]
        lines = [row("modelling", gpu, wall)]
        entry = enter(window, size, query, app, "entry (first in this process)" if first else "entry")
        first = False
        gpu, wall = rounds(window, size, query, app, args.draws)
        lines.append(row("lookdev (as entered)" if args.effects else "lookdev", gpu, wall, floor))
        if args.effects:
            lines += p3_rows(window, size, query, app, args.draws, args.effects, floor, lid)
        app.close_lookdev()
        gpu, wall = rounds(window, size, query, app, args.draws)
        lines.append(row("modelling after", gpu, wall, floor))
        for line in entry + lines:
            print(line)
    print()
    print("Entering once more (programs cached in this process):")
    print(enter(window, size, query, app, "entry again")[0])
    app.close_lookdev()
    print()
    print(f"glGetError at the end: 0x{gl.glGetError():04X}")
    window.close()
    del pyglet
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
