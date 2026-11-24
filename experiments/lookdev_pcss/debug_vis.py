"""Diagnostic frames (2026-11-24; disposable): the skin writes (vis, vis_wrap, n.l > 0) instead of its colour - red =
the key's visibility (Lambert / highlight), green = the lifted lookup's (the wrap's excess), blue = the lit side of the
terminator - for production and PCSS variants, at Manu's setting (AD-039 §23.6) or the study light.

    xvfb-run -a python experiments/lookdev_pcss/debug_vis.py --variants P,F,S16P16d --sizes 0,0.45 --out <dir>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compare as cp  # noqa: E402  (sets the paths)

import numpy as np  # noqa: E402

import area_glsl as ag  # noqa: E402
import pcss_glsl as pg  # noqa: E402
import run_compare as rc  # noqa: E402

ANCHOR_MAIN = "\nvoid main() {"
ANCHOR_LAMBERT = "        vec3 lambert = vec3(max(ndl, 0.0));"
ANCHOR_OUT = "    out_color = vec4(lookdev_output(colour), 1.0);"


def debug_fragment(fragment: str) -> str:
    if "#define SHADOW 1" not in fragment:
        return fragment
    out = ag._replace(fragment, ANCHOR_MAIN, "\nvec3 ldx_dbg = vec3(0.0);" + ANCHOR_MAIN, 1)
    out = ag._replace(out, ANCHOR_LAMBERT, "        ldx_dbg = vec3(vis, vis_wrap, step(0.0, ndl));\n" + ANCHOR_LAMBERT, 1)
    return ag._replace(out, ANCHOR_OUT, "    out_color = vec4(mix(ldx_dbg, lookdev_output(colour), 1e-9), 1.0);  // colour kept: no uniform optimized away", 1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--variants", default="P,F,S16P16d")
    parser.add_argument("--sizes", default="0,0.45")
    parser.add_argument("--view", default="manu")
    parser.add_argument("--material", default="Creature Skin*")
    parser.add_argument("--size", type=int, nargs=2, default=(1024, 768))
    args = parser.parse_args(argv)
    out = Path(args.out)
    from pyglet import gl  # noqa: F401
    from drag_cost.probe_lookdev import set_surface

    window, app = rc.build_app(rc.GOLLUM, args.size)
    set_surface(app, "subd1")
    capture = rc.Capture(window.get_framebuffer_size())
    rc.prepare(window, app, capture)
    cp.set_effects(app, False)
    (cp.light_manu if args.view == "manu" else cp.light_study)(app)
    cp.set_camera(app, "gollum", args.view)
    cp.set_material(app, args.material)
    original = pg.patch_shadow
    pg.patch_shadow = lambda frag, p: debug_fragment(original(frag, p))
    rows = []
    try:
        for size in (float(s) for s in args.sizes.split(",")):
            app.set_lookdev_light("key", size=size)
            rc.settle(window, app, capture)
            row = []
            for name in args.variants.split(","):
                p = cp.VARIANTS[name] or pg.Pcss(filter="production", full=False)
                img, mask = cp.render(window, app, capture, cp.DIFFUSE, p)
                row.append(np.clip(np.round(img * 255.0), 0, 255).astype(np.uint8) * mask[..., None])
            rows.append(row)
    finally:
        pg.patch_shadow = original
        pg.uninstall()
        ag.uninstall()
    box = rc.crop_box(rows[0][0].any(axis=2))
    rc.write_png(out / f"debug_{args.view}.png", rc.sheet([[rc.crop(i, box) for i in r] for r in rows]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
