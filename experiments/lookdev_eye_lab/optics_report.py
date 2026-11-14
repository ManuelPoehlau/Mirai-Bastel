"""P1b step 1: the corneal refraction measured on the CPU, before any shader (2026-11-14).

    python experiments/lookdev_eye_lab/optics_report.py            # 1024x768 and 1920x1080, all three views

Prints, per variant V1 / V2 / V3 (`cornea_optics`): the cornea's geometry and thickness profile, the front-view
magnification and the virtual pupil (traced and paraxial), how far off-axis the pupil and the iris stay visible, and
per view and frame size the pupil's apparent size / position and the displacement of iris features in pixels, plus
the difference of the iris albedo image between the variants. GL-free (NumPy); the same lines appear as section [M] of
`probe_refraction.py`. Plain ASCII.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from lookdev_eye_lab._paths import ensure_paths  # noqa: E402

ensure_paths()

from lookdev_eye_lab import cornea_optics as co  # noqa: E402
from lookdev_eye_lab import eye_geometry as geo  # noqa: E402
from lookdev_eye_lab import lab_scene  # noqa: E402
from lookdev_eye_lab import lab_state as ls  # noqa: E402

SIZES = ((1024, 768), (1920, 1080))


def report(sizes=SIZES, views=ls.VIEW_ORDER, g: co.CorneaGeometry = co.GEOMETRY) -> list[str]:
    from mirai.viewport.camera import OrbitCamera

    mm = 1.0 / co.MM
    out = ["[M] corneal refraction, CPU ray model (cornea_optics.py); 1 unit = 12 mm",
           f"  indices: air {co.N_AIR}, cornea {co.N_CORNEA}, aqueous {co.N_AQUEOUS}, V2 effective {co.N_EFFECTIVE}",
           f"  anterior r {g.anterior_radius * mm:.2f} mm, posterior r {g.posterior_radius * mm:.2f} mm, apex z "
           f"{g.apex_z:.4f}; chamber angle at r {g.angle[0] * mm:.2f} mm, z {g.angle[1]:.4f}; limbus r "
           f"{g.limbus_radius * mm:.2f} mm",
           "  thickness along the anterior normal (mm): " + ", ".join(
               f"r {r * mm:.1f}: {float(g.thickness_at(r)) * mm:.3f}" for r in (0.0, 0.2, 0.4, g.angle[0],
                                                                               g.limbus_radius)),
           f"  pupil: r {g.pupil_radius * mm:.2f} mm, {(g.apex_z - float(g.iris_z(g.pupil_radius))) * mm:.3f} mm "
           "behind the apex",
           f"  {'variant':<7} {'paraxial mag':>12} {'paraxial depth mm':>17} {'traced mag':>10} {'traced depth mm':>15} "
           f"{'pupil visible to':>16} {'iris visible to':>15}"]
    for v in co.VARIANTS:
        m, depth = co.paraxial_entrance_pupil(v, g)
        rv, zv = co.virtual_pupil(v, g)
        out.append(f"  {v:<7} {m:>12.4f} {depth * mm:>17.3f} {rv / g.pupil_radius:>10.4f} "
                   f"{(g.apex_z - zv) * mm:>15.3f} {co.visibility_limit(v, co.PUPIL, g=g):>14.1f} d "
                   f"{co.visibility_limit(v, co.IRIS, g=g):>13.1f} d")
    out.append("  (traced = virtual pupil edge triangulated from two on-axis cameras; visible to = largest angle off "
               "the eye's axis, sclera occlusion included, no lids)")
    image = geo.iris_image()  # always the procedural iris: these numbers depend on no file (iris_source)
    for width, height in sizes:
        distance = lab_scene.close_up_distance(width, height)
        out.append(f"  {width}x{height}, eye ~50 % of the frame (camera distance {distance:.3f}):")
        out.append(f"    {'view':<14} {'pair':<6} {'feature px med':>14} {'p95':>6} {'max':>6} {'pupil scale':>11} "
                   f"{'pupil shift px':>14} {'class changed px':>16} {'albedo diff mean':>16} {'p95':>4} {'max':>4} "
                   f"{'>2/255':>7}")
        for view in views:
            camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=distance)
            yaw, pitch = ls.VIEWS[view]
            camera.set_view(math.radians(yaw), math.radians(pitch))
            m = co.view_metrics(camera, width, height, image, g)
            counts = ", ".join(f"{v} pupil {m[v]['pupil_px']} / limbus {m[v]['limbus_px']}" for v in co.VARIANTS)
            out.append(f"    {view:<14} cornea {m['cornea_px']} px: {counts}")
            for pair in ("V1-V2", "V2-V3", "V1-V3"):
                r = m[pair]
                out.append(f"    {'':<14} {pair:<6} {r['disp_px_median']:>14.2f} {r['disp_px_p95']:>6.2f} "
                           f"{r['disp_px_max']:>6.2f} {r['pupil_scale']:>11.3f} {r['pupil_shift_px']:>14.2f} "
                           f"{r['kind_changed_px']:>16} {r['albedo_mean']:>16.2f} {r['albedo_p95']:>4.0f} "
                           f"{r['albedo_max']:>4.0f} {r['albedo_over_2_pct']:>6.2f}%")
    out.append("  feature px = how far an iris point moves on screen between the two variants (pixels where both see "
               "iris); class changed = pixels whose ray ends in a different class (iris / pupil / limbus); albedo "
               "diff = the iris image the rays see, 8-bit levels, no lighting")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="P1b corneal refraction, CPU ray model")
    p.add_argument("--sizes", nargs="+", default=[f"{w}x{h}" for w, h in SIZES])
    args = p.parse_args(argv)
    sizes = [tuple(int(v) for v in s.split("x")) for s in args.sizes]
    for line in report(sizes):
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
