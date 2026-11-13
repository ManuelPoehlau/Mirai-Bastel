"""Debug pictures for the report (`results/img/*.png`, Pillow). They illustrate measured results; they prove nothing.

    python experiments/surface_slide/make_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from surface_slide import algorithms as A  # noqa: E402
from surface_slide import debug_view as dv  # noqa: E402
from surface_slide import harness as H  # noqa: E402
from surface_slide import scenarios as S  # noqa: E402

IMG = HERE / "results" / "img"
BLUE, RED, GREY, INK = (40, 100, 200), (205, 60, 40), (150, 150, 150), (40, 40, 40)


def u_profile_figure() -> None:
    """The U seen along its extrusion: where one row of wall-A vertices ends, per candidate."""
    scn = next(s for s in S.u_scenarios() if s.name == "C1_u_gap3cells_into_gap_60deg")
    an = scn.analytic
    runs = {"closest_global": H.run(scn, A.ClosestGlobal()), "geodesic_pursuit": H.run(scn, A.GeodesicPursuit("project"))}
    w, h_ = 1100, 700
    img = Image.new("RGB", (w, h_), "white")
    draw = ImageDraw.Draw(img)
    for col, (name, run) in enumerate(runs.items()):
        ox = 140 + col * 540
        scale = 280.0

        def px(x, z):
            return ox + (x + 0.15) * scale * 3.0, 640 - (z + 0.2) * scale

        prof = an.profile
        draw.line([px(x, z) for x, z in prof], fill=GREY, width=3)
        colour = RED if name == "closest_global" else BLUE
        rows = [i for i in range(scn.setup.n) if abs(scn.setup.p0[i, 1]) < 1e-9]
        for i in rows:
            trail = [px(p[0], p[2]) for p in run.pos[:, i]]
            draw.line(trail, fill=colour, width=2)
            x0, y0 = trail[0]
            draw.ellipse([x0 - 4, y0 - 4, x0 + 4, y0 + 4], outline=INK)
            x1, y1 = trail[-1]
            draw.ellipse([x1 - 4, y1 - 4, x1 + 4, y1 + 4], fill=colour)
            free = scn.setup.p0[i] + scn.path[-1]
            xf, yf = px(free[0], free[2])
            draw.line([(x0, y0), (xf, yf)], fill=(200, 200, 200), width=1)
        draw.text((ox - 60, 20), f"{name}: wrong wall {run.metrics['wrong_region_final']} / {scn.setup.n}", fill=INK)
        draw.text((ox - 60, 38), "open circle = start, dot = end, thin line = free move", fill=INK)
    img.save(IMG / "u_into_gap_60deg.png")


def gollum_figure(name: str, view: str = "front") -> None:
    scn = next(s for s in S.gollum_scenarios("cage") if s.name == name)
    ref = scn.ref
    runs = {"closest_global": (H.run(scn, A.ClosestGlobal()), RED),
            "geodesic_pursuit[transport]": (H.run(scn, A.GeodesicPursuit("transport")), BLUE)}
    tiles = []
    for label, (run, colour) in runs.items():
        V1 = ref.V.copy()
        V1[scn.setup.verts] = run.pos[-1]
        img, cam, depth = dv.render(V1, ref.T, view=view, size=760, wire_edges=ref.edges)
        for i in range(scn.setup.n):
            dv.draw_segments(img, cam, depth, run.pos[:-1, i], run.pos[1:, i], colour, 2, tol=0.02)
        dv.draw_points(img, cam, depth, scn.setup.p0, INK, 2, tol=0.02)
        c = run.metrics["continuity"]
        ImageDraw.Draw(img).text((12, 10), f"{label}: max step ratio {c['max_step_ratio']:.1f}, region jumps "
                                           f"{c['region_jumps']}, edge max {run.metrics['edges']['max_abs_rel']:.2f}",
                                 fill=INK)
        # crop around the patch
        S2 = cam.project(scn.setup.p0)
        cx, cy = S2[:, 0].mean(), S2[:, 1].mean()
        half = 230
        box = (int(max(cx - half, 0)), int(max(cy - half, 0)), int(min(cx + half, 760)), int(min(cy + half, 760)))
        tiles.append(img.crop(box).resize((560, 560)))
    sheet = Image.new("RGB", (1130, 600), "white")
    for k, tile in enumerate(tiles):
        sheet.paste(tile, (5 + 565 * k, 35))
        ImageDraw.Draw(sheet).text((10 + 565 * k, 10), list(runs)[k] + f"  -  {name}", fill=INK)
    sheet.save(IMG / f"{name}.png")


def main() -> int:
    IMG.mkdir(parents=True, exist_ok=True)
    u_profile_figure()
    for name in ("D_cage_lip_down", "D_cage_brow_into_socket", "D_cage_nose_to_cheek"):
        gollum_figure(name)
    print("->", IMG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
