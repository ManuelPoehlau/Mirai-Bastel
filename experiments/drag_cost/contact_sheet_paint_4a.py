"""Contact sheet of AD-037 Phase 4a's curvature probes (§12; proposal 2026-11-25 §4.3): the test alphas Poren, Ader and
Kratzer stamped at the eight probe regions of the Gollum head, on the cage and on SubD 1, rendered close up - for
Manu's visual check (feel and visual quality are the Artist's, AGENTS.md §7a).

Usage (from the repo root; a hidden pyglet window, headless with xvfb):
    xvfb-run -a python experiments/drag_cost/contact_sheet_paint_4a.py [--out DIR] [--size 2048] [--radius 3]

Per tile: a short stroke of three placements at 100 % spacing ("Strich folgen", left to right in the front view)
through the region's probe point, mirror off, on a neutral base, dark paint at 90 % opacity; the camera looks at the
point from between its normal and the front. The label names the region, the alpha and the projection the middle
placement chose ("eben" / "gewickelt", `mirai.paint.stamp`) and the stamps painted. Writes
`contact_sheet_cage_<radius>pct.png` and `contact_sheet_subd1_<radius>pct.png` (rows: regions; columns: alphas).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import REPO_ROOT, ensure_paths, source_state  # noqa: E402

ensure_paths()

TILE = 300
ALPHAS = (("test/poren", "Poren"), ("test/ader", "Ader"), ("test/kratzer", "Kratzer"))
PROJECTION_LABELS = {"planar": "eben", "wrap": "gewickelt"}
DEFAULT_OUT = REPO_ROOT / "docs" / "research" / "alpha_brush_4a_assets_2026-11-25"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--size", type=int, default=2048)
    parser.add_argument("--radius", type=float, default=3.0,
                        help="brush radius in %% of the bounding radius (a step of brush.RADIUS_STEPS_PERCENT)")
    args = parser.parse_args(argv)

    import numpy as np
    import pyglet
    from pyglet import gl

    from core import PaintLayer, PaintStack
    from drag_cost.probe_paint import load_head, probe_regions, surface_mesh
    from mirai.iris_import import encode_png
    from mirai.mesh_geometry import mesh_center_and_radius
    from mirai.paint import alpha, brush, dynamics, stamp
    from mirai.paint.store import PaintStore
    from mirai.paint.surface import PaintSurface
    from mirai.viewport.camera import OrbitCamera
    from viewport.gl_render_store import GLRenderStore
    from viewport.live_texture import LiveTexture
    from viewport.material import Material
    from viewport.render_mesh import RenderMesh

    regions = probe_regions()
    print(f"Contact sheet AD-037 4a - {source_state()}")
    head = load_head()
    size = args.size
    bounding = mesh_center_and_radius(head.mesh)[1]
    radius = bounding * args.radius / 100.0
    camera_front = regions.front_camera(head.mesh)
    head.paint = PaintStack(size, size, (PaintLayer("Paint", None),))
    store = PaintStore()
    base = np.zeros((size, size, 4), np.uint8)
    base[..., :3] = (196, 186, 176)
    base[..., 3] = 255
    window = pyglet.window.Window(width=TILE, height=TILE, visible=False)
    args.out.mkdir(parents=True, exist_ok=True)
    for kind in ("cage", "subd1"):
        mesh = surface_mesh(head, kind)
        surface = PaintSurface(mesh, size, size, kind)
        rm = RenderMesh(mesh, store_type=GLRenderStore)
        rows = []
        for name, (label, pixel) in regions.REGIONS.items():
            tiles = []
            for alpha_id, alpha_label in ALPHAS:
                # the brush's own radius step: it decides whether a placement may wrap (`stamp.projection_for`)
                settings = brush.BrushSettings(colour=(0.42, 0.07, 0.07), opacity=0.9,
                                               radius_step=brush.RADIUS_STEPS_PERCENT.index(args.radius)).with_tip(
                    brush.TipSettings(alpha_id))
                image = alpha.generated_alpha(alpha_id)
                recorder = store.begin_stroke(head, "Paint")
                stroke = brush.PaintStroke(recorder, settings)
                stamps: list = []

                def evaluate(placement, settings=settings, image=image, stroke=stroke, stamps=stamps):
                    texels, coverage, unique = stamp.evaluate(surface, placement, radius, settings, None,
                                                              view_up=(0.0, 1.0, 0.0), image=image, stamps=stamps)
                    stroke.dab(texels, coverage, unique=unique)

                spacing = 2.0 * radius
                queue = dynamics.StrokeQueue(surface.hit, spacing, 4.0 * radius, True, evaluate, radius=radius)
                px = radius / (camera_front.distance * math.tan(math.radians(25.0))) * 450.0  # radius in front px
                x, y = pixel
                for k in range(9):
                    queue.add_ray(*regions.ray(camera_front, (x - 2.2 * px + 4.4 * px * k / 8, y)), samples=4)
                queue.end_input()
                queue.run(None)
                hit = regions.region_hit(surface, camera_front, name)
                middle = stamps[len(stamps) // 2] if stamps else None
                projection = PROJECTION_LABELS.get(middle.projection, "?") if middle is not None else "-"
                rgba = np.ascontiguousarray(store.composite(head, base))
                recorder.cancel()
                store.take_changed(head)
                live = LiveTexture(rgba, mipmaps="frame")
                view = np.asarray(hit.normal) + np.array([0.0, 0.0, 1.0])
                view /= np.linalg.norm(view)
                camera = OrbitCamera(target=tuple(hit.point), distance=6.5 * radius,
                                     yaw=math.atan2(view[0], view[2]), pitch=math.asin(max(-1.0, min(1.0, view[1]))),
                                     near=0.005)
                rm.bind_camera(camera)
                rm.mark_camera_dirty(aspect=1.0)
                rm.bind_material(Material((0.72, 0.75, 0.82), texture=live))
                rm.mark_material_dirty()
                text = pyglet.text.Label(f"{label} - {alpha_label} - {projection} ({len(stamps)})", x=6, y=TILE - 16,
                                         font_size=10, color=(255, 255, 255, 255))
                for _ in range(2):
                    window.switch_to()
                    gl.glViewport(0, 0, *window.get_framebuffer_size())
                    gl.glClearColor(0.12, 0.12, 0.13, 1.0)
                    window.clear()
                    rm.sync()
                    rm.render(camera)
                    gl.glDisable(gl.GL_DEPTH_TEST)
                    text.draw()
                    gl.glEnable(gl.GL_DEPTH_TEST)
                    gl.glFinish()
                w, h = window.get_framebuffer_size()
                buf = (gl.GLubyte * (w * h * 4))()
                gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
                gl.glReadPixels(0, 0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, buf)
                tile = np.frombuffer(bytes(buf), np.uint8).reshape(h, w, 4)[::-1].copy()
                tile[..., 3] = 255
                tile[:2] = tile[-2:] = 40
                tile[:, :2] = tile[:, -2:] = 40
                tiles.append(tile[:TILE, :TILE])
                live.release()
            rows.append(np.concatenate(tiles, axis=1))
        sheet = np.concatenate(rows, axis=0)
        path = args.out / f"contact_sheet_{kind}_{args.radius:g}pct.png"
        path.write_bytes(encode_png(sheet))
        rm.store.release()
        surface.close()
        print(f"  {kind}: {path} ({sheet.shape[1]} x {sheet.shape[0]})")
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
