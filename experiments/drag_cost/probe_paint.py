"""Paint Room Phase 1e (AD-037, audit 2026-11-18 §8.5): the reference-PC probes P-A ... P-F on the Gollum head.

Usage (from the repo root; opens a hidden pyglet window for the GL rows):
    python experiments/drag_cost/probe_paint.py                 # all probes, 2048²
    python experiments/drag_cost/probe_paint.py --size 1024
    python experiments/drag_cost/probe_paint.py --no-gl         # only the CPU rows (P-A CPU part, P-D, P-F)

Set the NVIDIA driver to "prefer maximum performance" first (as for `probe_shading_gpu.py`).

The fixture: the head of `scenes/Gollum_Head_rigging_test.mirai.json` (2,234 faces, UVs, its ZBrush texture 2048²).

- **P-D** room enter: `mirai.paint.texel_map.TexelMap` build (once per object and topology). Bar: <= 2 s.
- **P-A** one dab + composite + upload per frame, radius 1 / 3 / 5 / 10 % of the bounding radius: a *probe-only* dab
  (the Phase 2 dab is not built yet): texels of the triangles near the hit whose surface point lies within the radius,
  a smooth falloff, Normal blend into one layer through `PaintStore.begin_stroke` / `write_texels`, the touched tiles
  composited over the base (`PaintStore.composite`) into a `viewport.live_texture.LiveTexture`, then one frame (the
  head drawn with that texture, `glFinish`). Rows: dab (CPU), composite (CPU), frame (upload + draw + finish), total.
  Bars: p95 <= 16.7 ms at 3 %, <= 33 ms at 5 % (the D3 bars).
- **P-B** mip policy during a stroke: the same 3 % stroke with `mipmaps` = frame / deferred / none (frame time).
- **P-C** orbit frame with the live 2048² texture against the file texture (the camera turned 2 degrees per frame).
  Bar: no regression > 1 ms p50.
- **P-E** a Modeller frame (the file texture) before and after a live texture existed elsewhere: same image (bytes
  compared), same time.
- **P-F** save of a 4-layer stack (`mirai.paint.files.prepare_save`: four PNGs + the flattened image into a temporary
  folder) and the second save without changes. Bar: <= 2 s; the second writes nothing.

Plain ASCII output; prints the commit and working-tree state (`_paths.source_state`).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import tempfile
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import REPO_ROOT, ensure_paths, source_state  # noqa: E402

ensure_paths()

SCENE = REPO_ROOT / "scenes" / "Gollum_Head_rigging_test.mirai.json"
RADII = (1.0, 3.0, 5.0, 10.0)
DEFAULT_DABS = 40
WINDOW = (1280, 720)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--size", type=int, default=2048, help="paint image side in pixels (default 2048)")
    parser.add_argument("--dabs", type=int, default=DEFAULT_DABS, help="dabs per stroke (default 40)")
    parser.add_argument("--no-gl", action="store_true", help="CPU rows only (no window)")
    args = parser.parse_args(argv)
    if args.size < 64 or args.dabs < 2:
        parser.error("--size >= 64, --dabs >= 2")
    return args


def stats(values) -> str:
    values = sorted(values)
    p95 = values[min(len(values) - 1, int(math.ceil(0.95 * len(values))) - 1)]
    return f"{statistics.median(values):8.2f} {p95:8.2f} {max(values):8.2f}"


def load_head():
    from core import scene_from_dict
    from mirai import texture_files

    scene = scene_from_dict(json.loads(SCENE.read_text(encoding="utf-8")))
    head = next(o for o in scene.objects.values() if o.texture and o.eye is None and o.mesh.has_face_uvs())
    head.texture = texture_files.resolve(head.texture, SCENE.parent)
    return head


class ProbeDab:
    """The probe's stand-in for the Phase 2 dab (module docstring): candidates = texels of triangles whose 3D box meets
    the brush sphere; footprint = those within the radius; alpha = (1 - (d/r)²)²."""

    def __init__(self, texel_map) -> None:
        import numpy as np

        self.np = np
        self.map = texel_map
        mapped = texel_map.mapped()
        order = np.argsort(texel_map.slot[mapped], kind="stable")
        self.texels = mapped[order]
        slots = texel_map.slot[self.texels]
        self.starts = np.searchsorted(slots, np.arange(texel_map.tri_face.size))
        self.ends = np.searchsorted(slots, np.arange(texel_map.tri_face.size), side="right")
        mesh = texel_map.mesh
        corners = texel_map.tri_vertices.clip(min=0)
        table = {int(v): mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
        pts = np.array([[table.get(int(v), (0.0, 0.0, 0.0)) for v in row] for row in corners])
        self.lo, self.hi = pts.min(axis=1), pts.max(axis=1)
        self.live = texel_map.tri_face >= 0

    def footprint(self, centre, radius):
        np = self.np
        near = self.live & np.all(self.lo <= centre + radius, axis=1) & np.all(self.hi >= centre - radius, axis=1)
        slots = np.nonzero(near)[0]
        if slots.size == 0:
            return np.zeros(0, np.int64), np.zeros(0, np.float32)
        parts = [self.texels[self.starts[s]:self.ends[s]] for s in slots]
        cand = np.concatenate(parts)
        points = self.map.surface_points(cand)
        d2 = ((points - centre) ** 2).sum(axis=1) / (radius * radius)
        inside = d2 < 1.0
        return cand[inside], ((1.0 - d2[inside]) ** 2).astype(np.float32)


def stroke_centres(head, dabs: int):
    """`dabs` points along a cheek-height line across the front of the head (surface vertices, nearest per step)."""
    import numpy as np

    mesh = head.mesh
    ids = mesh.all_vertex_ids()
    pts = np.array([mesh.vertex_position(v) for v in ids])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    front = pts[pts[:, 2] > lo[2] + 0.7 * (hi[2] - lo[2])]
    y = lo[1] + 0.55 * (hi[1] - lo[1])
    xs = np.linspace(lo[0] + 0.3 * (hi[0] - lo[0]), lo[0] + 0.7 * (hi[0] - lo[0]), dabs)
    return [front[np.argmin(((front[:, :2] - (x, y)) ** 2).sum(axis=1))] for x in xs], pts


def run_stroke(store, obj, dab, centres, radius, base, live, frame):
    """One stroke; per dab (dab ms, composite ms, frame ms)."""
    import numpy as np

    from mirai.paint.store import tile_box

    layer = obj.paint.layers[0].name
    recorder = store.begin_stroke(obj, layer)
    rgba = store.pixels(obj, layer)
    flat = rgba.reshape(-1, 4)
    colour = np.array([180.0, 40.0, 40.0], np.float32)
    rows = []
    for centre in centres:
        t0 = time.perf_counter()
        texels, alpha = dab.footprint(centre, radius)
        if texels.size:
            old = flat[texels].astype(np.float32)
            a = alpha[:, None] * 0.6
            new = np.empty((texels.size, 4), np.uint8)
            new[:, :3] = np.rint(old[:, :3] + (colour - old[:, :3]) * a)
            new[:, 3] = np.maximum(old[:, 3], np.rint(255.0 * a[:, 0]))
            recorder.write_texels(texels, new)
        t1 = time.perf_counter()
        for tile in store.take_changed(obj):
            x0, y0, x1, y1 = tile_box(tile, obj.paint.width, obj.paint.height)
            if live is not None:
                live.rgba[y0:y1, x0:x1] = store.composite(obj, base, (x0, y0, x1, y1))
                live.mark(x0, y0, x1, y1)
            else:
                store.composite(obj, base, (x0, y0, x1, y1))
        t2 = time.perf_counter()
        frame_ms = frame() if frame is not None else 0.0
        rows.append(((t1 - t0) * 1e3, (t2 - t1) * 1e3, frame_ms))
    if live is not None:
        live.finish()
    recorder.cancel()
    return rows


def main(argv=None) -> int:
    args = parse_args(argv)
    import numpy as np

    from core import PaintLayer, PaintStack
    from mirai.paint import files
    from mirai.paint.store import PaintStore
    from mirai.paint.texel_map import TexelMap

    size = args.size
    print(f"Paint probe (AD-037 Phase 1e) - {source_state()}")
    print(f"python {sys.version.split()[0]}, numpy {np.__version__}, size {size}^2, {args.dabs} dabs per stroke")
    head = load_head()
    print(f"fixture: {head.name}, {len(head.mesh.all_face_ids())} faces, texture {Path(head.texture).name}")

    t0 = time.perf_counter()
    texel_map = TexelMap(head.mesh, size, size)
    build = time.perf_counter() - t0
    mib = (texel_map.slot.nbytes + texel_map.bary.nbytes) / 2**20
    print(f"\nP-D texel map build: {build * 1e3:.0f} ms ({texel_map.mapped().size:,} texels mapped, {mib:.0f} MiB)"
          f"  bar <= 2000 ms: {'PASS' if build <= 2.0 else 'FAIL'}")
    dab = ProbeDab(texel_map)
    head.paint = PaintStack(size, size, (PaintLayer("Paint 1", None),))
    store = PaintStore()
    base = files.read_base(head, size, size)
    centres, pts = stroke_centres(head, args.dabs)
    bounding = float(np.linalg.norm(pts - pts.mean(axis=0), axis=1).max())

    window = rm = camera = None
    if not args.no_gl:
        import pyglet
        from pyglet import gl

        from mirai.viewport.camera import OrbitCamera
        from viewport.gl_render_store import GLRenderStore
        from viewport.live_texture import LiveTexture
        from viewport.material import Material
        from viewport.render_mesh import RenderMesh

        window = pyglet.window.Window(width=WINDOW[0], height=WINDOW[1], visible=False)
        print(f"GL: {gl.gl_info.get_renderer()} / {gl.gl_info.get_version()}")
        rm = RenderMesh(head.mesh, store_type=GLRenderStore)
        centre = pts.mean(axis=0)
        camera = OrbitCamera(target=tuple(centre), distance=2.6 * bounding, yaw=0.0, pitch=0.0)
        rm.bind_camera(camera)
        rm.mark_camera_dirty(aspect=WINDOW[0] / WINDOW[1])

        def frame() -> float:
            t = time.perf_counter()
            window.switch_to()
            gl.glViewport(0, 0, *window.get_framebuffer_size())
            gl.glClearColor(0.1, 0.1, 0.1, 1.0)
            window.clear()
            rm.sync()
            rm.render(camera)
            gl.glFinish()
            return (time.perf_counter() - t) * 1e3

        def show(texture) -> None:
            rm.bind_material(Material((0.72, 0.75, 0.82), texture=texture))
            rm.mark_material_dirty()
            frame()
            frame()

        def new_live(policy):
            rgba = np.ascontiguousarray(store.composite(head, base))
            return LiveTexture(rgba, mipmaps=policy)
    else:
        frame = None

    print(f"\nP-A dab + composite + frame per dab, {size}^2, ms        p50      p95      max")
    live = new_live("deferred") if rm is not None else None
    if live is not None:
        show(live)
    for pct in RADII:
        radius = bounding * pct / 100.0
        run_stroke(store, head, dab, centres[:3], radius, base, live, frame)  # warm-up
        rows = run_stroke(store, head, dab, centres, radius, base, live, frame)
        texels = int(np.mean([dab.footprint(c, radius)[0].size for c in centres[:5]]))
        total = [a + b + c for a, b, c in rows]
        bar = 16.7 if pct == 3.0 else 33.0 if pct == 5.0 else None
        verdict = "" if bar is None else f"  bar p95 <= {bar}: {'PASS' if sorted(total)[int(0.95 * len(total)) - 1] <= bar else 'FAIL'}"
        print(f"  radius {pct:4.1f} % (~{texels:,} texels)")
        print(f"    dab        {stats([r[0] for r in rows])}")
        print(f"    composite  {stats([r[1] for r in rows])}")
        if rm is not None:
            print(f"    frame      {stats([r[2] for r in rows])}")
        print(f"    total      {stats(total)}{verdict}")

    if rm is not None:
        print("\nP-B mip policy, 3 % stroke, frame ms             p50      p95      max")
        for policy in ("frame", "deferred", "none"):
            trial = new_live(policy)
            show(trial)
            rows = run_stroke(store, head, dab, centres, bounding * 0.03, base, trial, frame)
            end = frame()  # the stroke's end: "deferred" regenerates here
            print(f"  {policy:9s}  {stats([r[2] for r in rows])}   stroke-end frame {end:.2f}")
            trial.release()

        print("\nP-C orbit frame, ms                              p50      p95      max")
        results = {}
        for name, texture in (("file texture", head.texture), ("live texture", live)):
            show(texture)
            times = []
            for i in range(40):
                camera.yaw += 2.0
                rm.mark_camera_dirty(aspect=WINDOW[0] / WINDOW[1])
                times.append(frame())
            results[name] = statistics.median(times)
            print(f"  {name:13s} {stats(times)}")
        diff = results["live texture"] - results["file texture"]
        print(f"  live - file p50 {diff:+.2f} ms  bar <= +1 ms: {'PASS' if diff <= 1.0 else 'FAIL'}")

        print("\nP-E Modeller frame (file texture) before / after a live texture existed")
        camera.yaw = 0.0
        rm.mark_camera_dirty(aspect=WINDOW[0] / WINDOW[1])
        show(head.texture)

        def grab() -> bytes:
            frame()
            w, h = window.get_framebuffer_size()
            buf = (gl.GLubyte * (w * h * 3))()
            gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
            gl.glReadPixels(0, 0, w, h, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
            return bytes(buf)

        before = grab()
        before_t = [frame() for _ in range(20)]
        live.release()
        after = grab()
        after_t = [frame() for _ in range(20)]
        print(f"  same image: {'PASS' if before == after else 'FAIL'};  p50 before {statistics.median(before_t):.2f}"
              f" ms, after {statistics.median(after_t):.2f} ms")
        rm.store.release()
        window.close()

    print("\nP-F save of a 4-layer stack")
    head.paint = PaintStack(size, size, tuple(PaintLayer(f"Layer {i + 1}", None) for i in range(4)))
    four = PaintStore()
    rng = np.random.default_rng(1)
    for i, spec in enumerate(head.paint.layers):
        rgba = np.zeros((size, size, 4), np.uint8)
        y0 = i * size // 8
        rgba[y0:y0 + size // 4, :, :3] = rng.integers(0, 255, 3)
        rgba[y0:y0 + size // 4, :, 3] = 180
        four.set_pixels(head, spec.name, rgba)
    with tempfile.TemporaryDirectory() as tmp:
        scene_path = Path(tmp) / "probe.mirai.json"
        t = time.perf_counter()
        plan = files.prepare_save([head], four, scene_path)
        first = time.perf_counter() - t
        plan.apply(four)
        t = time.perf_counter()
        again = files.prepare_save([head], four, scene_path)
        second = time.perf_counter() - t
        written = sum(p.stat().st_size for p in (scene_path.parent / "probe_textures").iterdir())
        print(f"  first save {first * 1e3:.0f} ms ({plan.written} layers + {len(plan.flats)} flat, {written / 2**20:.1f}"
              f" MiB)  bar <= 2000 ms: {'PASS' if first <= 2.0 else 'FAIL'}")
        print(f"  second save {second * 1e3:.0f} ms ({again.written} layers, {len(again.flats)} flat)"
              f"  nothing written: {'PASS' if again.written == 0 and not again.flats else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
