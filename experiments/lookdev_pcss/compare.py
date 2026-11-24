"""PCSS variants of the key's shadow against the 32-key area-light reference, through the real LookDev pass (2026-11-24;
disposable experiment for AD-039 §23.6 / Q-S8-3).

    xvfb-run -a python experiments/lookdev_pcss/compare.py                          # everything (slow in llvmpipe)
    xvfb-run -a python experiments/lookdev_pcss/compare.py --scene gollum --views manu --sizes 0.45 --ref 16

Nothing in `src/` changes; the scene files are only read. Built on `experiments/lookdev_diffuse_area/run_compare.py`
(the app, the RGBA32F capture, the NumPy tone curve, the material helpers):
- every image has „Weiches Licht“ (`area_diffuse`, S8) **on**, Schatten + Doppel-Glanz on, eyes hidden (`--eyes` shows
  them: the S2 check), and is captured linear and tone-mapped with production's twin;
- the variants (`VARIANTS`): `P` = production today (3 x 3 PCF, the map at its effective resolution
  1024 / (1 + 5 size)); `F` = the same lookup with the map at full resolution; `S<b>P<p><d|g>` = PCSS (`pcss_glsl.Pcss`:
  b blocker-search fetches, p PCF fetches, disc = Vogel spiral / grid), at full resolution unless `-eff`;
- `REF` = production at key size 0 (hard map at full resolution, point light) under `--ref` key directions spread over
  the emitter's cap (sin sigma = size x sin 40°, the S8 mapping), each x 2 / (1 + cos sigma), averaged in linear light:
  each direction casts its own hard shadow, so REF has the true distance-dependent penumbrae (contact shadows sharp,
  the nose's shadow on the cheek broad);
- diffuse-only (no specular) for the numbers, plus "beauty" (specular on) of P and `--beauty` for the look.

Lights (`--light`): "study" = run_compare's (Dramatic, key 70 / 20, rim off, fill size 0); views "face" / "framed" and
the shapes use it. View "manu" uses Manu's setting of AD-039 §23.6 instead: Dramatic rotated 5°, key 2.2 at 70 / 9,
4800 K, fill and rim off, the camera on the shadow side (azimuth -35°) on the face. Materials: Neutral and
"Creature Skin*" = Creature Skin adjusted as Manu's (roughness 0.5, gloss 0.35, wrap 0.5, backscatter 0); albedo "Farbe".

Outputs (`--out`, default `out/`): frames per (scene, view, material, size, variant), sheets (rows = sizes; columns =
the variants then REF; the diff sheet: signed difference to REF, red brighter / blue darker, x4), `metrics.json`,
`log.txt`. `analyze.py` reads the frames for the per-region numbers.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AREA = REPO / "experiments" / "lookdev_diffuse_area"
for p in (REPO / "src", REPO / "experiments", AREA, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

import area_glsl as ag  # noqa: E402
import area_math as am  # noqa: E402
import pcss_glsl as pg  # noqa: E402
import run_compare as rc  # noqa: E402

DIFFUSE = ag.Variant("A", spec=False, linear=True)  # with area_diffuse on the body calls production's B itself
BEAUTY_AREA = ag.Variant("A", linear=True)
#: the candidate family "K" (2026-11-24, after the variants below): blocker search with the cone test (a fetch is a
#: blocker 2 x |o| above the receiver), PCF against half the mean blocker height (no receiver plane), the PCF faded in
#: over the first 4 blockers, the lifted lookup + 0.15 R s²
K = dict(search_test="cone", cone=2.0, pcf_test="level", level=0.5, band_lift=0.15, fade=4.0)
#: the recommendation (2026-11-24, last): K plus the receiver plane within 1.5-3.75 texels of the centre, a search of
#: at least 2 texels and its fetches denser near the centre (thin contact blockers: a lip crease, a nostril's rim)
#: and the band lift 0.23 R s³ (as 0.15 R s² at size 1, smaller below: measured 2026-11-24, `K16c-s2` the s² one)
KC = dict(K, near=1.5, search_min=2.0, search_kind="centre", band_lift=0.23, band_power=3.0)
VARIANTS: dict[str, pg.Pcss | None] = {
    "K16c": pg.Pcss(16, 16, "disc", **KC),
    "K8c/16": pg.Pcss(8, 16, "disc", **KC),
    "K24c/16": pg.Pcss(24, 16, "disc", **KC),
    "K16c/32": pg.Pcss(16, 32, "disc", **KC),
    "K16c/9g": pg.Pcss(16, 9, "grid", **KC),
    "K16c-eff": pg.Pcss(16, 16, "disc", full=False, **KC),
    "K16c-nb": pg.Pcss(16, 16, "disc", early=False, **KC),
    "K16c-s2": pg.Pcss(16, 16, "disc", **{**KC, "band_lift": 0.15, "band_power": 2.0}),
    "K16c-s4": pg.Pcss(16, 16, "disc", **{**KC, "band_lift": 0.36, "band_power": 4.0}),
    "K16c-bl0": pg.Pcss(16, 16, "disc", **{**KC, "band_lift": 0.0}),
    # cost diagnostics and cheaper forms (2026-11-24, after the reference-PC run: the cost did not follow the fetches)
    "K16c-lean": pg.Pcss(16, 16, "disc", lean=True, **KC),
    "K16c-lean-nb": pg.Pcss(16, 16, "disc", lean=True, early=False, **KC),
    "K8c/8-lean-nb": pg.Pcss(8, 8, "disc", lean=True, early=False, **KC),
    "K16c-nofetch": pg.Pcss(16, 16, "disc", probe="nofetch", **KC),
    "K16c-nb-nofetch": pg.Pcss(16, 16, "disc", early=False, probe="nofetch", **KC),
    "K16c-search": pg.Pcss(16, 16, "disc", probe="search", **KC),
    "K16c-pcf": pg.Pcss(16, 16, "disc", probe="pcf", **KC),
    "K16c-uall": pg.Pcss(16, 16, "disc", unroll="all", **KC),
    "K16c-unone": pg.Pcss(16, 16, "disc", unroll="none", **KC),
    "K16c-cap12": pg.Pcss(16, 16, "disc", **{**KC, "max_texels": 12.0}),
    "P": None,
    "F": pg.Pcss(filter="production"),
    "S9P9g": pg.Pcss(9, 9, "grid"),
    "S16P16d": pg.Pcss(16, 16, "disc"),
    "S16P16g": pg.Pcss(16, 16, "grid"),
    "S16P32d": pg.Pcss(16, 32, "disc"),
    "S32P32d": pg.Pcss(32, 32, "disc"),
    "S16P16d-each": pg.Pcss(16, 16, "disc", search_at="each"),
    "S16P16d-eff": pg.Pcss(16, 16, "disc", full=False),
    "S16P16d-nb": pg.Pcss(16, 16, "disc", early=False),
    "S16P16d-nrm": pg.Pcss(16, 16, "disc", plane="normal"),
    "S16P16d-nrm-k100": pg.Pcss(16, 16, "disc", plane="normal", slope_max=100.0),
    "S16P16d-k100": pg.Pcss(16, 16, "disc", slope_max=100.0),
    "S16P16d-bf": pg.Pcss(16, 16, "disc", back_flat=True),
    "S16P16d-cone1": pg.Pcss(16, 16, "disc", search_test="cone", cone=1.0),
    "S16P16d-cone1-bf": pg.Pcss(16, 16, "disc", search_test="cone", cone=1.0, back_flat=True),
    "S16P16d-cone0.5-bf": pg.Pcss(16, 16, "disc", search_test="cone", cone=0.5, back_flat=True),
    # the "level" family (cone search, PCF against the blockers' level, no receiver plane): the candidate
    "L9g": pg.Pcss(9, 9, "grid", search_test="cone", pcf_test="level"),
    "L16g": pg.Pcss(16, 16, "grid", search_test="cone", pcf_test="level"),
    "L16": pg.Pcss(16, 16, "disc", search_test="cone", pcf_test="level"),
    "L16/32": pg.Pcss(16, 32, "disc", search_test="cone", pcf_test="level"),
    "L32": pg.Pcss(32, 32, "disc", search_test="cone", pcf_test="level"),
    "L8/16": pg.Pcss(8, 16, "disc", search_test="cone", pcf_test="level"),
    "L16-eff": pg.Pcss(16, 16, "disc", full=False, search_test="cone", pcf_test="level"),
    "L16-each": pg.Pcss(16, 16, "disc", search_at="each", search_test="cone", pcf_test="level"),
    "L16-c2": pg.Pcss(16, 16, "disc", search_test="cone", cone=2.0, pcf_test="level"),
    "L16-nb": pg.Pcss(16, 16, "disc", early=False, search_test="cone", pcf_test="level"),
    "Q16": pg.Pcss(16, 16, "disc", search_test="both", pcf_test="min", plane="normal", back_flat=True),
    "Q16d": pg.Pcss(16, 16, "disc", search_test="both", pcf_test="min", back_flat=True),
    "M16n": pg.Pcss(16, 16, "disc", search_test="cone", pcf_test="min", plane="normal", back_flat=True),
    "Q16-k30": pg.Pcss(16, 16, "disc", search_test="both", pcf_test="min", plane="normal", back_flat=True,
                       slope_max=30.0),
    "Q16-bl.15": pg.Pcss(16, 16, "disc", search_test="both", pcf_test="min", plane="normal", back_flat=True,
                         band_lift=0.15),
    "Q16-bl.3": pg.Pcss(16, 16, "disc", search_test="both", pcf_test="min", plane="normal", back_flat=True,
                        band_lift=0.3),
    "L16-bl.15": pg.Pcss(16, 16, "disc", search_test="cone", pcf_test="level", band_lift=0.15),
    "L16-bl.3": pg.Pcss(16, 16, "disc", search_test="cone", pcf_test="level", band_lift=0.3),
    "L16-bl.15-f4": pg.Pcss(16, 16, "disc", search_test="cone", pcf_test="level", band_lift=0.15, fade=4.0),
    "L16-bl.15-c2": pg.Pcss(16, 16, "disc", search_test="cone", cone=2.0, pcf_test="level", band_lift=0.15),
    "L16-bl.15-c2-f4": pg.Pcss(16, 16, "disc", search_test="cone", cone=2.0, pcf_test="level", band_lift=0.15,
                               fade=4.0),
    "L16-bl.15-l.75": pg.Pcss(16, 16, "disc", search_test="cone", pcf_test="level", level=0.75, band_lift=0.15),
    "K9g": pg.Pcss(9, 9, "grid", **K),
    "K16g": pg.Pcss(16, 16, "grid", **K),
    "K8/16": pg.Pcss(8, 16, "disc", **K),
    "K16": pg.Pcss(16, 16, "disc", **K),
    "K16/32": pg.Pcss(16, 32, "disc", **K),
    "K32": pg.Pcss(32, 32, "disc", **K),
    "K16-eff": pg.Pcss(16, 16, "disc", full=False, **K),
    "K16-each": pg.Pcss(16, 16, "disc", search_at="each", **K),
    "K16-nb": pg.Pcss(16, 16, "disc", early=False, **K),
    "K16-n1.5": pg.Pcss(16, 16, "disc", near=1.5, **K),
    "K16-n3": pg.Pcss(16, 16, "disc", near=3.0, **K),
    "K8/16-n1.5": pg.Pcss(8, 16, "disc", near=1.5, **K),
    "K16-n3-l.35": pg.Pcss(16, 16, "disc", near=3.0, **{**K, "level": 0.35}),
    "K16-n1.5-l.35": pg.Pcss(16, 16, "disc", near=1.5, **{**K, "level": 0.35}),
    "K16-n5": pg.Pcss(16, 16, "disc", near=5.0, **K),
    "K16-sm2": pg.Pcss(16, 16, "disc", near=1.5, search_min=2.0, **K),
    "K16-sm2.5": pg.Pcss(16, 16, "disc", near=1.5, search_min=2.5, **K),
    "C16": pg.Pcss(16, 16, "disc", near=1.5, chord=1.0, **{**K, "band_lift": 0.0}),
    "C16-ch2": pg.Pcss(16, 16, "disc", near=1.5, chord=2.0, **{**K, "band_lift": 0.0}),
    "C16-ch3": pg.Pcss(16, 16, "disc", near=1.5, chord=3.0, **{**K, "band_lift": 0.0}),
    "K16-bl0": pg.Pcss(16, 16, "disc", **{**K, "band_lift": 0.0}),
    "L.5": pg.Pcss(16, 16, "disc", search_test="cone", cone=1.0, pcf_test="level", level=0.5),
    "L.25": pg.Pcss(16, 16, "disc", search_test="cone", cone=1.0, pcf_test="level", level=0.25),
    "Lphys.5": pg.Pcss(16, 16, "disc", search_test="cone", cone=0.0, pcf_test="level", level=0.5),
    "M.5": pg.Pcss(16, 16, "disc", search_test="cone", cone=1.0, pcf_test="min", level=0.5),
    "M.5-bf": pg.Pcss(16, 16, "disc", search_test="cone", cone=1.0, pcf_test="min", level=0.5, back_flat=True),
}
DEFAULT_VARIANTS = ("P", "F", "K16", "K16c", "K8c/16", "K24c/16", "K16c/32", "K16c/9g", "K16c-eff", "K16c-s2",
                    "K16c-bl0")
SIZES = (0.0, 0.25, 0.45, 1.0)
MATERIALS = ("Neutral", "Creature Skin*")
MANU_KEY = (70.0, 9.0)


# -- setup ----------------------------------------------------------------------------------------------------------

def light_study(app) -> tuple[float, float]:
    app.set_lookdev_studio_preset(rc.STUDIO)
    app.set_lookdev_studio(rotation=0.0, follow_camera=False, exposure=0.0, tone_curve="reinhard")
    app.set_lookdev_light("rim", on=False)
    app.set_lookdev_light("fill", size=0.0)
    app.set_lookdev_light("key", azimuth=rc.KEY[0], elevation=rc.KEY[1], size=0.0)
    return rc.KEY


def light_manu(app) -> tuple[float, float]:
    app.set_lookdev_studio_preset(rc.STUDIO)
    app.set_lookdev_studio(rotation=5.0, follow_camera=False, exposure=0.0, tone_curve="reinhard")
    app.set_lookdev_light("rim", on=False)
    app.set_lookdev_light("fill", on=False)
    app.set_lookdev_light("key", intensity=2.2, azimuth=MANU_KEY[0], elevation=MANU_KEY[1], kelvin=4800.0, size=0.0)
    return MANU_KEY


def set_effects(app, eyes: bool, area: bool = True) -> None:
    from viewport.lookdev_optics import LookdevEffects

    on = {"shadow", "dual_lobe"} | ({"area_diffuse"} if area else set()) | ({"eye_shadow"} if eyes else set())
    for name in LookdevEffects.names():
        app.set_lookdev_effect(name, name in on)


def set_material(app, name: str) -> None:
    rc.set_material(app, name.rstrip("*"))
    if name.endswith("*"):
        from core import ObjectState

        ids = [oid for oid, obj in app.scene.objects.items()
               if obj.eye is None and obj.state is ObjectState.NORMAL and not obj.hidden]
        app.select_objects(ids)
        app.set_lookdev_material_values(roughness=0.5, specular=0.35, wrap=0.5, backscatter=0.0)
        app.select_objects([])


def set_camera(app, scene: str, view: str) -> None:
    if view != "manu":
        rc.set_camera(app, scene, view)
        return
    from drag_cost.probe_lookdev import world_bounds

    centre, radius = world_bounds(app)
    cam = app.camera
    cam.set_view(math.radians(-35.0), math.radians(4.0))
    cam.frame_on_bounds((centre[0], centre[1] + 0.05 * radius, centre[2] + 0.3 * radius), 0.5 * radius, 1.0)
    app.viewport.on_camera_changed()
    app.update_viewport(0.0)


def use(app, area: ag.Variant, pcss) -> None:
    pg.install(area, pcss)
    ag.reset_programs(app)


def render(window, app, capture, area, pcss):
    use(app, area, pcss)
    capture.render(window, app)  # compiles (and re-renders the map when its resolution changed)
    return capture.render(window, app)


def render_reference(window, app, capture, size: float, count: int, key_dir: tuple[float, float]):
    """REF: production at key size 0 under `count` hard keys on the emitter's cap around `key_dir`, averaged."""
    s = float(am.size_to_sin(size))
    use(app, DIFFUSE, None)
    key = app.lookdev.studio.key
    app.set_lookdev_light("key", size=0.0)
    if s < am.S_MIN:
        capture.render(window, app)
        img = capture.render(window, app)
        app.set_lookdev_light("key", size=size)
        return img
    base = key.intensity
    l0 = am.direction(*key_dir)
    right, up = am.frame_for(l0)
    norm = 2.0 / (1.0 + math.sqrt(1.0 - s * s))
    acc, mask = None, None
    app.set_lookdev_light("key", intensity=base * norm)
    for d in am.cap_directions(s, count):
        w = d[0] * right + d[1] * up + d[2] * l0
        el = math.degrees(math.asin(max(-1.0, min(1.0, w[1]))))
        az = math.degrees(math.atan2(w[0], w[2]))
        app.set_lookdev_light("key", azimuth=az, elevation=el)
        img, m = capture.render(window, app)
        acc = img if acc is None else acc + img
        mask = m if mask is None else (mask | m)
    app.set_lookdev_light("key", azimuth=key_dir[0], elevation=key_dir[1], intensity=base, size=size)
    return acc / count, mask


# -- the run --------------------------------------------------------------------------------------------------------

def views_for(scene: str, wanted) -> tuple:
    have = ("manu", "face", "framed") if scene == "gollum" else ("front",)
    return tuple(v for v in have if wanted is None or v in wanted)


def run_scene(scene: str, args, out: Path, log) -> dict:
    from drag_cost.probe_lookdev import set_surface

    path = rc.GOLLUM if scene == "gollum" else rc.shapes_scene(Path(tempfile.mkdtemp(prefix="ldx_pcss_")) / "s.mirai.json")
    window, app = rc.build_app(path, args.size)
    if scene == "gollum" and not set_surface(app, "subd1"):
        raise RuntimeError("SubD 1 could not be set")
    capture = rc.Capture(window.get_framebuffer_size())
    rc.prepare(window, app, capture)
    if args.eyes:
        app.set_eyes_shown(True)
    set_effects(app, args.eyes, not args.no_area)
    results = {}
    try:
        for view in views_for(scene, args.views):
            key_dir = light_manu(app) if view == "manu" else light_study(app)
            set_camera(app, scene, view)
            for material in args.materials:
                set_material(app, material)
                rc.settle(window, app, capture)
                grid, diffs, beauty, box = [], [], [], None
                mtag = f"{scene}_{view}_{material.replace(' ', '').replace('*', 'M')}"
                for size in args.sizes:
                    t0 = time.perf_counter()
                    app.set_lookdev_light("key", size=size)
                    rc.settle(window, app, capture)
                    images = {}
                    for name in args.variants:
                        img, mask = render(window, app, capture, DIFFUSE, VARIANTS[name])
                        images[name] = rc.display(img, mask)
                    for name in ("P",) + tuple(args.beauty):
                        img, mask = render(window, app, capture, BEAUTY_AREA, VARIANTS[name])
                        images[name + " beauty"] = rc.display(img, mask)
                    ref, rmask = render_reference(window, app, capture, size, args.ref, key_dir)
                    images["REF"] = rc.display(ref, rmask)
                    key = f"{scene}/{view}/{material}/size {size:g}"
                    results[key] = {name: rc.metrics(images[name], images["REF"], rmask) for name in args.variants}
                    log(f"{key}  ({time.perf_counter() - t0:.0f} s)")
                    for name in args.variants:
                        m = results[key][name]
                        log(f"    {name:<14} mae {m['mae']:5.2f}/255  brighter>8 {100 * m['brighter']:5.2f} %  "
                            f"darker>8 {100 * m['darker']:5.2f} %  max+ {m['max_brighter']:5.1f}")
                    tag = f"{mtag}_s{int(round(size * 100)):03d}"
                    if box is None:
                        box = rc.crop_box(rmask)
                    images = {k: rc.crop(img, box) for k, img in images.items()}
                    cmask = rc.crop(rmask, box)
                    for name, img in images.items():
                        rc.write_png(out / "frames" / f"{tag}_{name.replace(' ', '_').replace('/', '-')}.png", img)
                    grid.append([images[n] for n in args.variants] + [images["REF"]])
                    diffs.append([rc.diff_map(images[n], images["REF"], cmask) for n in args.variants])
                    beauty.append([images[n + " beauty"] for n in ("P",) + tuple(args.beauty)])
                rc.write_png(out / f"sheet_{mtag}.png", rc.sheet(grid))
                rc.write_png(out / f"diff_{mtag}.png", rc.sheet(diffs))
                rc.write_png(out / f"beauty_{mtag}.png", rc.sheet(beauty))
    finally:
        pg.uninstall()
        ag.uninstall()
        app.close_lookdev()
        window.close()
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(HERE / "out"))
    parser.add_argument("--scene", default="gollum,shapes")
    parser.add_argument("--views", default=None, help="gollum: manu,face,framed (default all)")
    parser.add_argument("--sizes", default=",".join(f"{s:g}" for s in SIZES))
    parser.add_argument("--materials", default=",".join(MATERIALS))
    parser.add_argument("--variants", default=",".join(DEFAULT_VARIANTS))
    parser.add_argument("--beauty", default="K16c", help="variants also rendered with specular (P always)")
    parser.add_argument("--ref", type=int, default=32, help="REF: key directions on the cap")
    parser.add_argument("--size", type=int, nargs=2, default=(1024, 768))
    parser.add_argument("--eyes", action="store_true", help="eyes shown, Augen-Schatten on (the S2 check)")
    parser.add_argument("--no-area", action="store_true", help="„Weiches Licht“ off (PCSS without S8's band)")
    parser.add_argument("--spec", action="store_true",
                        help="the numbers with specular on (variants and REF; needed with --no-area: diffuse-only "
                             "without the band leaves only u_ld_light_size[0] in use and pyglet cannot set the array)")
    args = parser.parse_args(argv)
    global DIFFUSE
    if args.spec:
        DIFFUSE = BEAUTY_AREA
    args.sizes = tuple(float(s) for s in args.sizes.split(","))
    args.variants = tuple(v for v in args.variants.split(",") if v)
    args.beauty = tuple(v for v in args.beauty.split(",") if v and v != "P")
    args.materials = tuple(m for m in args.materials.split(",") if m)
    args.views = None if args.views is None else tuple(args.views.split(","))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lines = []

    def log(text):
        print(text, flush=True)
        lines.append(text)

    from pyglet import gl  # noqa: F401 - opens the shadow context first

    from drag_cost._paths import source_state

    log(f"lookdev_pcss compare, {args.size[0]}x{args.size[1]}, REF {args.ref} directions, sigma(1) = "
        f"{float(am.sigma_degrees(1.0)):.1f} deg, eyes {'on' if args.eyes else 'off'}, "
        f"Weiches Licht {'off' if args.no_area else 'on'}")
    log(f"Source: {source_state()}")
    for name in args.variants:
        log(f"  {name:<14} {VARIANTS[name]}")
    results = {}
    for scene in args.scene.split(","):
        results.update(run_scene(scene, args, out, log))
    (out / "metrics.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    (out / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
