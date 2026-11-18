"""Paint Room probes (AD-037, audit 2026-11-18 §8.5): P-A ... P-F on the Gollum head - Phase 1e, since Phase 2 with
the real dab and on the SubD surface.

Usage (from the repo root; opens a hidden pyglet window for the GL rows):
    python experiments/drag_cost/probe_paint.py                 # all probes, 2048², cage and SubD 1 / 2
    python experiments/drag_cost/probe_paint.py --size 1024
    python experiments/drag_cost/probe_paint.py --no-gl         # only the CPU rows (P-A CPU part, P-D, P-F)
    python experiments/drag_cost/probe_paint.py --surfaces cage # P-A / P-D on the cage only

Set the NVIDIA driver to "prefer maximum performance" first (as for `probe_shading_gpu.py`).

The fixture: the head of `scenes/Gollum_Head_rigging_test.mirai.json` (2,234 faces, UVs, its ZBrush texture 2048²).

- **P-D** room enter: the paint surface's build (`mirai.paint.surface.PaintSurface`: the texel map, batched since
  Phase 2, plus the hit / footprint tables) once per object, topology and shown surface - on the cage, on SubD level 1
  (what the app's preview shows on the head: `MAX_DERIVED_FACES` 25,000 caps level 2's 36,008 faces) and on SubD level 2
  (AD-037 §8 (a)). Bar: <= 2 s.
- **P-A** one dab + composite + upload per frame, radius 1 / 3 / 5 / 10 % of the bounding radius, with the Phase 2 dab
  (`controllers.paint_room`: the ray hit on the surface, the footprint and its mirror across the head's symmetry plane,
  the falloff, the stroke buffer `brush.PaintStroke`), the touched tiles composited over the base
  (`PaintStore.composite`) into a `viewport.live_texture.LiveTexture`, then one frame (that surface drawn with the
  texture, `glFinish`). Rows: dab (CPU), composite (CPU), frame (upload + draw + finish), total, per surface.
  Bars: p95 <= 16.7 ms at 3 %, <= 33 ms at 5 % (the D3 bars); "P-A with SubD on" is an AD-037 §8 (c) acceptance row.
- **P-B** mip policy during a stroke: the same 3 % stroke with `mipmaps` = frame / deferred / none (frame time).
- **P-C** orbit frame with the live 2048² texture against the file texture (the camera turned 2 degrees per frame).
  Bar: no regression > 1 ms p50.
- **P-E** a Modeller frame (the file texture) before and after a live texture existed elsewhere: same image (bytes
  compared), same time.
- **P-F** save of a 4-layer stack (`mirai.paint.files.prepare_save`: four PNGs + the flattened image into a temporary
  folder) and the second save without changes. Bar: <= 2 s; the second writes nothing. Since the reference-PC run of
  2026-11-18 (7.4 / 9.4 s) the first save is split into reading the base, flattening, encoding and writing the files
  (`texture_files.store`, which includes the file system and any virus scanner on the new file).

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
SURFACES = ("cage", "subd1", "subd2")
DEFAULT_DABS = 40
WINDOW = (1280, 720)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--size", type=int, default=2048, help="paint image side in pixels (default 2048)")
    parser.add_argument("--dabs", type=int, default=DEFAULT_DABS, help="dabs per stroke (default 40)")
    parser.add_argument("--no-gl", action="store_true", help="CPU rows only (no window)")
    parser.add_argument("--surfaces", default="cage,subd1,subd2",
                        help="surfaces for P-D / P-A: cage, subd1, subd2 (comma separated; default all three)")
    args = parser.parse_args(argv)
    args.surfaces = [name.strip() for name in args.surfaces.split(",") if name.strip()]
    if not args.surfaces or any(name not in SURFACES for name in args.surfaces):
        parser.error(f"--surfaces: from {', '.join(SURFACES)}")
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


def surface_mesh(head, kind: str):
    """The mesh the room paints on for `kind`: the head itself, or its SubD level 1 / 2 as the preview derives it."""
    if kind == "cage":
        return head.mesh
    from mirai.scene_factory import mesh_from_positions_and_faces
    from mirai.subdivision.catmull_clark import SubdSurface, refine_face_uvs

    mesh = head.mesh
    level = int(kind[4:])
    surface = SubdSurface(mesh)
    derived = surface.level(level)
    control = [tuple(mesh.vertex_position(v)) for v in surface.topology.vertex_ids]
    uvs = refine_face_uvs([mesh.face_uvs(f) for f in surface.topology.face_ids], surface.topology.face_sizes, level)
    return mesh_from_positions_and_faces(derived.apply_full(control), derived.faces, uvs)


class Phase2Dab:
    """The room's dab (`controllers.paint_room.PaintRoomController._dab`) without the app: hit, footprint (+ mirror),
    falloff, the stroke buffer."""

    def __init__(self, surface, store, obj, definition) -> None:
        from mirai.paint import brush

        self.brush = brush
        self.surface, self.store, self.obj, self.definition = surface, store, obj, definition
        self.settings = brush.BrushSettings(colour=(0.7, 0.16, 0.16), opacity=0.6)
        self.stroke = None

    def begin(self, radius: float) -> None:
        self.radius = radius
        recorder = self.store.begin_stroke(self.obj, self.obj.paint.layers[0].name)
        self.stroke = self.brush.PaintStroke(recorder, self.settings)

    def footprint(self, ray):
        import numpy as np

        from mirai.paint.surface import mirror

        hit = self.surface.hit(*ray)
        if hit is None:
            return np.zeros(0, np.int64), np.zeros(0, np.float32)
        texels, x = self.surface.footprint(hit.point, self.radius, hit.normal)
        parts_t, parts_x = [texels], [x]
        if self.definition is not None:
            point, normal = mirror(self.definition, hit.point, hit.normal)
            texels, x = self.surface.footprint(point, self.radius, normal)
            parts_t.append(texels)
            parts_x.append(x)
        texels = np.concatenate(parts_t)
        self.unique = len(parts_t) == 1
        return texels, self.brush.falloff(np.concatenate(parts_x), self.settings.hardness, self.settings.curve)

    def dab(self, ray) -> int:
        texels, coverage = self.footprint(ray)
        return self.stroke.dab(texels, coverage, unique=self.unique)

    def cancel(self) -> None:
        self.stroke.recorder.cancel()


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


def stroke_rays(centres, bounding: float):
    """A ray from the front (+Z, where the face looks) through each centre: what the cursor's ray is in a front view."""
    import numpy as np

    direction = np.array([0.0, 0.0, -1.0])
    return [(np.asarray(c, float) + np.array([0.0, 0.0, 3.0 * bounding]), direction) for c in centres]


def run_stroke(store, obj, dab, rays, radius, base, live, frame):
    """One stroke with the Phase 2 dab (cancelled at the end: every stroke starts from the same pixels); per dab
    (dab ms, composite ms, frame ms)."""
    import numpy as np  # noqa: F401

    from mirai.paint.store import tile_box

    dab.begin(radius)
    rows = []
    for ray in rays:
        t0 = time.perf_counter()
        dab.dab(ray)
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
    dab.cancel()
    store.take_changed(obj)
    return rows


def main(argv=None) -> int:
    args = parse_args(argv)
    import numpy as np

    from core import PaintLayer, PaintStack
    from mirai.paint import files
    from mirai.paint.store import PaintStore
    from mirai.paint.surface import PaintSurface

    size = args.size
    print(f"Paint probe (AD-037 Phase 1e / 2) - {source_state()}")
    print(f"python {sys.version.split()[0]}, numpy {np.__version__}, size {size}^2, {args.dabs} dabs per stroke")
    head = load_head()
    definition = head.mesh.symmetry_definition
    print(f"fixture: {head.name}, {len(head.mesh.all_face_ids())} faces, texture {Path(head.texture).name},"
          f" mirrored dab {'on' if definition is not None else 'off (no symmetry plane)'}")

    print("\nP-D room enter: paint surface build (texel map + tables), ms        bar <= 2000 ms")
    surfaces = {}
    for kind in args.surfaces:
        mesh = surface_mesh(head, kind)
        t0 = time.perf_counter()
        surface = PaintSurface(mesh, size, size, kind)
        build = time.perf_counter() - t0
        surfaces[kind] = surface
        texel_map = surface.map
        mib = (texel_map.slot.nbytes + texel_map.bary.nbytes) / 2**20
        print(f"  {kind:6s} {len(mesh.all_face_ids()):6,} faces  {build * 1e3:6.0f} ms"
              f"  ({texel_map.mapped().size:,} texels, {mib:.0f} MiB)  {'PASS' if build <= 2.0 else 'FAIL'}")
    head.paint = PaintStack(size, size, (PaintLayer("Paint 1", None),))
    store = PaintStore()
    base = files.read_base(head, size, size)
    centres, pts = stroke_centres(head, args.dabs)
    bounding = float(np.linalg.norm(pts - pts.mean(axis=0), axis=1).max())
    rays = stroke_rays(centres, bounding)

    window = camera = None
    meshes = {}
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
        centre = pts.mean(axis=0)
        camera = OrbitCamera(target=tuple(centre), distance=2.6 * bounding, yaw=0.0, pitch=0.0)
        current = {"rm": None}

        def render_mesh(kind):
            rm = meshes.get(kind)
            if rm is None:
                rm = meshes[kind] = RenderMesh(surfaces[kind].mesh if kind in surfaces else head.mesh,
                                               store_type=GLRenderStore)
                rm.bind_camera(camera)
            rm.mark_camera_dirty(aspect=WINDOW[0] / WINDOW[1])
            current["rm"] = rm
            return rm

        def frame() -> float:
            rm = current["rm"]
            t = time.perf_counter()
            window.switch_to()
            gl.glViewport(0, 0, *window.get_framebuffer_size())
            gl.glClearColor(0.1, 0.1, 0.1, 1.0)
            window.clear()
            rm.sync()
            rm.render(camera)
            gl.glFinish()
            return (time.perf_counter() - t) * 1e3

        def show(texture, kind="cage") -> None:
            rm = render_mesh(kind)
            rm.bind_material(Material((0.72, 0.75, 0.82), texture=texture))
            rm.mark_material_dirty()
            frame()
            frame()

        def new_live(policy):
            rgba = np.ascontiguousarray(store.composite(head, base))
            return LiveTexture(rgba, mipmaps=policy)
    else:
        frame = None

    live = new_live("deferred") if window is not None else None
    for kind, surface in surfaces.items():
        dab = Phase2Dab(surface, store, head, definition)
        if live is not None:
            show(live, kind)
        print(f"\nP-A dab + composite + frame per dab, {kind}, {size}^2, ms      p50      p95      max")
        for pct in RADII:
            radius = bounding * pct / 100.0
            run_stroke(store, head, dab, rays[:3], radius, base, live, frame)  # warm-up
            rows = run_stroke(store, head, dab, rays, radius, base, live, frame)
            dab.radius = radius
            texels = int(np.mean([dab.footprint(ray)[0].size for ray in rays[:5]]))
            total = [a + b + c for a, b, c in rows]
            bar = 16.7 if pct == 3.0 else 33.0 if pct == 5.0 else None
            verdict = "" if bar is None else (f"  bar p95 <= {bar}: "
                                              f"{'PASS' if sorted(total)[int(0.95 * len(total)) - 1] <= bar else 'FAIL'}")
            print(f"  radius {pct:4.1f} % (~{texels:,} texels with the mirror)")
            print(f"    dab        {stats([r[0] for r in rows])}")
            print(f"    composite  {stats([r[1] for r in rows])}")
            if window is not None:
                print(f"    frame      {stats([r[2] for r in rows])}")
            print(f"    total      {stats(total)}{verdict}")

    if window is not None:
        dab = Phase2Dab(surfaces.get("cage") or next(iter(surfaces.values())), store, head, definition)
        kind = "cage" if "cage" in surfaces else next(iter(surfaces))
        print(f"\nP-B mip policy, 3 % stroke ({kind}), frame ms      p50      p95      max")
        for policy in ("frame", "deferred", "none"):
            trial = new_live(policy)
            show(trial, kind)
            rows = run_stroke(store, head, dab, rays, bounding * 0.03, base, trial, frame)
            end = frame()  # the stroke's end: "deferred" regenerates here
            print(f"  {policy:9s}  {stats([r[2] for r in rows])}   stroke-end frame {end:.2f}")
            trial.release()
        rm = render_mesh("cage")

        print("\nP-C orbit frame, ms                              p50      p95      max")
        results = {}
        for name, texture in (("file texture", head.texture), ("live texture", live)):
            show(texture, "cage")
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
        show(head.texture, "cage")

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
        for mesh_rm in meshes.values():
            mesh_rm.store.release()
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
    parts: dict[str, list[float]] = {}

    def timed(module, name, label):
        original = getattr(module, name)

        def wrapper(*a, **k):
            t = time.perf_counter()
            try:
                return original(*a, **k)
            finally:
                parts.setdefault(label, []).append((time.perf_counter() - t) * 1e3)

        setattr(module, name, wrapper)
        return original

    from mirai import texture_files

    originals = [(files, "read_base", timed(files, "read_base", "read base")),
                 (files, "flatten", timed(files, "flatten", "flatten (base + composite)")),
                 (files, "encode_layer", timed(files, "encode_layer", "  of it: layers")),
                 (files, "encode_png", timed(files, "encode_png", "PNG encode (all files)")),
                 (texture_files, "store", timed(texture_files, "store", "write file"))]
    with tempfile.TemporaryDirectory() as tmp:
        scene_path = Path(tmp) / "probe.mirai.json"
        t = time.perf_counter()
        plan = files.prepare_save([head], four, scene_path)
        first = time.perf_counter() - t
        for module, name, original in originals:
            setattr(module, name, original)
        plan.apply(four)
        t = time.perf_counter()
        again = files.prepare_save([head], four, scene_path)
        second = time.perf_counter() - t
        written = sum(p.stat().st_size for p in (scene_path.parent / "probe_textures").iterdir())
        print(f"  first save {first * 1e3:.0f} ms ({plan.written} layers + {len(plan.flats)} flat, {written / 2**20:.1f}"
              f" MiB)  bar <= 2000 ms: {'PASS' if first <= 2.0 else 'FAIL'}")
        for label, values in parts.items():
            print(f"    {label:28s} {sum(values):8.0f} ms in {len(values)} call{'s' if len(values) != 1 else ''}"
                  f" (max {max(values):.0f})")
        print(f"  second save {second * 1e3:.0f} ms ({again.written} layers, {len(again.flats)} flat)"
              f"  nothing written: {'PASS' if again.written == 0 and not again.flats else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
