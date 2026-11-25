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

- **P-H** (Phase 4a, AD-037 §12) one **alpha** placement + composite + frame: the test alpha "Poren" with the mirror,
  "Strich folgen", the planar/wrap projection chosen per placement (`mirai.paint.stamp.evaluate`), at 3 % and 5 %, per
  surface; the share of wrapped placements. Gates (reference PC): 3 % total p95 <= 16.7 ms, 5 % <= 33 ms.
- **P-I** (Phase 4a) a **2-s fast stroke** through the stamp queue (`mirai.paint.dynamics.StrokeQueue`, the room's
  budgets): the cursor crosses the face in 2 s at 60 frames/s with two input events per frame; per frame the queue's
  work, the composite of the touched tiles and the GL frame; then the release: the finishing frames until the queue is
  empty, the seam padding and the commit (`PaintRoomController._commit`'s work). Round tip (12.5 % spacing) and
  "Poren" (100 %), 3 %; and the same path as a flick in 10 frames, which leaves a backlog for the finishing. Gates:
  frame p95 <= 33 ms; release -> History <= 250 ms; no finishing frame > 50 ms.
- **P-J** (Phase 4b, AD-037 §13) one **spray** placement + composite + frame: 20 "Poren" stamps of 20 % size with
  rotation / size / flow jitter and the mirror (`mirai.paint.stamp.paint`, one gather per cluster), 3 %, per surface;
  the round spray (20 stamps) as information. Gate (reference PC): p95 <= 33 ms.
- **P-K** (Phase 4b) a **10-s spray stroke** through the stamp queue: the cursor crosses the face ten times in 10 s (600
  frames, two events per frame), the Poren spray of P-J at 50 % spacing, then the finishing. Gate: no frame > 50 ms.
P-H and P-I paint through `stamp.paint` too (the room's path): without jitter, scatter or spray it is 4a's, bit for bit
(`tests/test_paint_dynamics.py`), and its 3 % row must stay where 4a was (AD-037 §12.6: 0.7 ms margin on SubD 1).

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


def percentile95(values) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(math.ceil(0.95 * len(values))) - 1)]


def stats(values) -> str:
    return f"{statistics.median(values):8.2f} {percentile95(values):8.2f} {max(values):8.2f}"


def load_head():
    from core import scene_from_dict
    from mirai import texture_files

    scene = scene_from_dict(json.loads(SCENE.read_text(encoding="utf-8")))
    head = next(o for o in scene.objects.values() if o.texture and o.eye is None and o.mesh.has_face_uvs())
    head.texture = texture_files.resolve(head.texture, SCENE.parent)
    return head


def png_header(path) -> str:
    """IHDR and the row filters of a PNG (why a decode is slow: filters 3 / 4 take the own decoder's per-byte loop)."""
    import struct
    import zlib

    import numpy as np

    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return "not a PNG"
    pos, idat, header = 8, [], None
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
    width, height, depth, colour, _c, _f, interlace = header
    text = f"{width} x {height}, {depth} bit, colour type {colour}, interlace {interlace}"
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colour)
    if not interlace and channels:
        stride = width * channels * depth // 8 + 1
        raw = np.frombuffer(zlib.decompress(b"".join(idat)), np.uint8)
        counts = np.bincount(raw[:height * stride:stride], minlength=5)
        text += ", row filters " + " ".join(f"{name} {n}" for name, n in zip(("none", "sub", "up", "avg", "paeth"), counts))
    return text


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


class AlphaDab(Phase2Dab):
    """Phase 4a: one placement through `mirai.paint.stamp.paint` (the room's path; without randomness 4a's `evaluate` +
    `dab`) with the test alpha "Poren" (a fixed stroke direction across the face, as "Strich folgen" gives on this
    stroke)."""

    def __init__(self, surface, store, obj, definition, alpha_id="test/poren") -> None:
        super().__init__(surface, store, obj, definition)
        self.settings = self.brush.BrushSettings(colour=(0.7, 0.16, 0.16), opacity=0.6,
                                                 tip=self.brush.TipSettings(alpha_id))
        self.stamps = []
        self.index = 0

    def dab(self, ray) -> int:
        import numpy as np

        from mirai.paint import stamp

        hit = self.surface.hit(*ray)
        if hit is None:
            return 0
        placement = stamp.Placement(self.index, hit.point, hit.normal, np.array([1.0, 0.0, 0.0]))
        self.index += 1
        return stamp.paint(self.stroke, self.surface, placement, self.radius, self.settings, self.definition,
                           view_up=(0.0, 1.0, 0.0), seed=4711, stamps=self.stamps)


def spray_settings(brush, alpha_id: str | None = "test/poren", spacing: float = 0.5):
    """P-J / P-K's spray (module docstring): 20 stamps of 20 %, rotation ±180°, size ±30 %, flow ±30 %."""
    from mirai.paint import dynamics

    settings = brush.BrushSettings(colour=(0.7, 0.16, 0.16), opacity=0.6).with_tip(brush.TipSettings(alpha_id))
    return settings.with_(dynamics=dynamics.StrokeDynamics().with_(
        spacing=spacing, emitter="spray", spray_density=20, spray_size=0.2, jitter_rotation=180.0, jitter_size=0.3,
        jitter_flow=0.3))

    def footprint(self, ray):
        import numpy as np

        from mirai.paint import stamp

        hit = self.surface.hit(*ray)
        if hit is None:
            self.unique = True
            return np.zeros(0, np.int64), np.zeros(0, np.float32)
        placement = stamp.Placement(0, hit.point, hit.normal, np.array([1.0, 0.0, 0.0]))
        texels, coverage, self.unique = stamp.evaluate(self.surface, placement, self.radius, self.settings,
                                                       self.definition, view_up=(0.0, 1.0, 0.0), stamps=self.stamps)
        return texels, coverage


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


def probe_regions():
    """`tests/paint_alpha_regions.py` (the 4a probe placements; `experiments/drag_cost/tests` shadows `tests`)."""
    import importlib.util

    name = "paint_alpha_regions"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "tests" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def fast_stroke(head, store, surface, definition, base, live, frame, bounding, kind, label, alpha_id,
                frames_n: int = 120, settings=None, crossings: int = 1, row: str = "P-I") -> None:
    """P-I (module docstring): a 2-s stroke (`frames_n` 120; 10: a flick of 0.17 s that leaves a backlog for the
    finishing) across the face through the stamp queue with the room's budgets. P-K: `settings` (the spray), 600
    frames, `crossings` times across the face."""
    from mirai.paint import alpha, brush, dynamics, stamp
    from mirai.paint.store import tile_box
    from mirai.paint.surface import pad_width, seam_pad

    regions = probe_regions()

    radius = bounding * 0.03
    if settings is None:
        settings = brush.BrushSettings(colour=(0.7, 0.16, 0.16), opacity=0.6).with_tip(brush.TipSettings(alpha_id))
    image = alpha.resolve(alpha_id)
    recorder = store.begin_stroke(head, head.paint.layers[0].name)
    stroke = brush.PaintStroke(recorder, settings)

    def evaluate(placement):  # the room's `_evaluate`
        stamp.paint(stroke, surface, placement, radius, settings, definition, view_up=(0.0, 1.0, 0.0), image=image,
                    seed=4711)

    camera = regions.front_camera(head.mesh)
    spacing = settings.dynamics.spacing * 2.0 * radius
    directed = image is not None or settings.dynamics.scattered
    queue = dynamics.StrokeQueue(surface.hit, spacing, 4.0 * radius, directed, evaluate, radius=radius)
    events_per_frame = 2
    x0, x1, y = 300.0, 600.0, 470.0  # cheek - nose - cheek in the 900 px front view
    px_radius = radius / (2.2 * bounding * math.tan(math.radians(25.0))) * 450.0
    step = min(max(settings.dynamics.spacing * 2.0 * px_radius, 2.0), 6.0)

    def tiles():
        t = time.perf_counter()
        for tile in store.take_changed(head):
            bx0, by0, bx1, by1 = tile_box(tile, head.paint.width, head.paint.height)
            if live is not None:
                live.rgba[by0:by1, bx0:bx1] = store.composite(head, base, (bx0, by0, bx1, by1))
                live.mark(bx0, by0, bx1, by1)
            else:
                store.composite(head, base, (bx0, by0, bx1, by1))
        return time.perf_counter() - t

    def one_frame(finishing: bool) -> float:
        t = time.perf_counter()
        queue.run(dynamics.frame_budget(queue, finishing))
        tiles()
        if frame is not None:
            frame()
        return (time.perf_counter() - t) * 1e3

    last = None
    stroke_frames = []
    for f in range(frames_n):
        for e in range(events_per_frame):
            k = f * events_per_frame + e
            travel = crossings * k / (frames_n * events_per_frame - 1)  # in crossings: there and back
            phase = travel % 2.0
            x = x0 + (x1 - x0) * (phase if phase <= 1.0 else 2.0 - phase)
            samples = 1 if last is None else max(1, math.ceil(abs(x - last) / step))
            queue.add_ray(*regions.ray(camera, (x, y)), samples=samples)
            last = x
        stroke_frames.append(one_frame(False))
    release = time.perf_counter()
    queue.end_input()
    finishing = []
    while not queue.done:
        finishing.append(one_frame(True))
    t = time.perf_counter()
    boxes = [tile_box(tile, surface.width, surface.height) for tile in recorder.tiles]
    dst, src = seam_pad(surface.map, boxes, pad_width(surface.width))
    if dst.size:
        rgba = store.pixels(head, recorder.name).reshape(-1, 4)
        recorder.write_texels(dst, rgba[src].copy())
    command = recorder.commit()
    tiles()
    finishing.append((time.perf_counter() - t) * 1e3)
    to_history = (time.perf_counter() - release) * 1e3
    if command is not None:
        command.undo()
    store.take_changed(head)
    p95 = percentile95(stroke_frames)
    worst = max(finishing)
    if row == "P-K":
        everything = stroke_frames + finishing
        print(f"\nP-K 10-s spray stroke, {label}, 3 %, {kind}: {queue.evaluated} placements "
              f"({settings.dynamics.spacing * 100:.0f} % spacing, {settings.dynamics.spray_density} stamps each), "
              f"{len(stroke_frames)} frames + {len(finishing) - 1} finishing")
        print(f"  stroke frame ms  {stats(stroke_frames)}")
        print(f"  release -> History {to_history:6.1f} ms;  frames > 50 ms: "
              f"{sum(1 for t in everything if t > 50.0)}, max {max(everything):.1f} ms  bar no frame > 50: "
              f"{'PASS' if max(everything) <= 50.0 else 'FAIL'}")
        return
    name = "2-s fast stroke" if frames_n == 120 else f"flick ({frames_n} frames)"
    print(f"\nP-I {name}, {label}, 3 %, {kind}: {queue.evaluated} placements "
          f"({settings.dynamics.spacing * 100:.1f} % spacing), {len(stroke_frames)} frames + {len(finishing) - 1} finishing")
    gated = frames_n == 120  # the flick is information (P-27: it trails and catches up), not a gate

    def verdict(ok: bool, bar: str) -> str:
        return f"bar {bar}: {'PASS' if ok else 'FAIL'}" if gated else "(info, no bar)"

    print(f"  stroke frame ms  {stats(stroke_frames)}  {verdict(p95 <= 33.0, 'p95 <= 33')}")
    print(f"  release -> History {to_history:6.1f} ms  {verdict(to_history <= 250.0, '<= 250')};"
          f"  finishing frame max {worst:.1f} ms  bar <= 50: {'PASS' if worst <= 50.0 else 'FAIL'}")


def main(argv=None) -> int:
    args = parse_args(argv)
    import numpy as np

    from core import PaintLayer, PaintStack
    from mirai.paint import files
    from mirai.paint.store import PaintStore
    from mirai.paint.surface import PaintSurface

    size = args.size
    print(f"Paint probe (AD-037 Phase 1e / 2 / 4a / 4b) - {source_state()}")
    print(f"python {sys.version.split()[0]}, numpy {np.__version__}, size {size}^2, {args.dabs} dabs per stroke")
    head = load_head()
    definition = head.mesh.symmetry_definition
    print(f"fixture: {head.name}, {len(head.mesh.all_face_ids())} faces, texture {Path(head.texture).name},"
          f" mirrored dab {'on' if definition is not None else 'off (no symmetry plane)'}")

    print("\nP-G base image (the ZBrush texture the room reads; reference PC 2026-11-18: 6.35 s in P-F)")
    files.clear_image_cache()
    t0 = time.perf_counter()
    files.read_image(head.texture)
    total = time.perf_counter() - t0
    info = files.last_read
    print(f"  {Path(head.texture).name}: {info['bytes']:,} bytes, {png_header(head.texture)}")
    print(f"  file read {info['read_s'] * 1e3:.0f} ms, decode {info['decode_s'] * 1e3:.0f} ms ({info['decoder']}),"
          f" total {total * 1e3:.0f} ms")
    t0 = time.perf_counter()
    files.read_image(head.texture)
    print(f"  second read (cached) {(time.perf_counter() - t0) * 1e3:.1f} ms")
    t0 = time.perf_counter()
    Path(head.texture).read_bytes()
    print(f"  plain re-read of the file {(time.perf_counter() - t0) * 1e3:.1f} ms")

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
        parts = {**{f"map {k}": v for k, v in texel_map.build_seconds.items()}, "tables": surface.build_seconds["tables"]}
        print("         " + ", ".join(f"{name} {seconds * 1e3:.0f}" for name, seconds in parts.items()))
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

    for kind, surface in surfaces.items():
        if kind == "subd2":
            continue  # the head shows level 1 (the 25,000-face cap)
        dab = AlphaDab(surface, store, head, definition)
        if live is not None:
            show(live, kind)
        print(f"\nP-H alpha placement (Poren, mirror) + composite + frame, {kind}, {size}^2, ms   p50      p95      max")
        for pct in (3.0, 5.0):
            radius = bounding * pct / 100.0
            # the brush's own radius step: it decides whether a placement may wrap (`stamp.projection_for`)
            dab.settings = dab.settings.with_(radius_step=dab.brush.RADIUS_STEPS_PERCENT.index(pct))
            run_stroke(store, head, dab, rays[:3], radius, base, live, frame)  # warm-up
            dab.stamps.clear()
            rows = run_stroke(store, head, dab, rays, radius, base, live, frame)
            wrapped = sum(1 for st in dab.stamps if st.projection == "wrap") / max(len(dab.stamps), 1)
            texels = int(np.mean([st.texels.size for st in dab.stamps])) * 2
            total = [a + b + c for a, b, c in rows]
            bar = 16.7 if pct == 3.0 else 33.0
            p95 = percentile95(total)
            print(f"  radius {pct:4.1f} % (~{texels:,} texels with the mirror, {wrapped * 100:.0f} % wrapped)")
            print(f"    dab        {stats([r[0] for r in rows])}")
            print(f"    composite  {stats([r[1] for r in rows])}")
            if window is not None:
                print(f"    frame      {stats([r[2] for r in rows])}")
            print(f"    total      {stats(total)}  bar p95 <= {bar}: {'PASS' if p95 <= bar else 'FAIL'}")

    for kind, surface in surfaces.items():
        if kind == "subd2":
            continue
        if live is not None:
            show(live, kind)
        for label, alpha_id in (("round", None), ("Poren", "test/poren")):
            for frames_n in (120, 10):
                fast_stroke(head, store, surface, definition, base, live, frame, bounding, kind, label, alpha_id,
                            frames_n)

    from mirai.paint import brush as brush_api

    for kind, surface in surfaces.items():
        if kind == "subd2":
            continue
        if live is not None:
            show(live, kind)
        print(f"\nP-J spray placement (20 stamps, 20 %, jitter, mirror) + composite + frame, {kind}, {size}^2, 3 %, ms"
              "   p50      p95      max")
        radius = bounding * 0.03
        for label, alpha_id in (("Poren", "test/poren"), ("round", None)):
            dab = AlphaDab(surface, store, head, definition)
            dab.settings = spray_settings(brush_api, alpha_id)
            run_stroke(store, head, dab, rays[:3], radius, base, live, frame)  # warm-up
            dab.stamps.clear()
            rows = run_stroke(store, head, dab, rays, radius, base, live, frame)
            stamps = len(dab.stamps) / max(len(rays), 1)
            total = [a + b + c for a, b, c in rows]
            p95 = percentile95(total)
            gate = f"bar p95 <= 33: {'PASS' if p95 <= 33.0 else 'FAIL'}" if alpha_id else "(info, no bar)"
            print(f"  {label} spray ({stamps:.0f} stamps per placement with the mirror)")
            print(f"    dab        {stats([r[0] for r in rows])}")
            print(f"    composite  {stats([r[1] for r in rows])}")
            if window is not None:
                print(f"    frame      {stats([r[2] for r in rows])}")
            print(f"    total      {stats(total)}  {gate}")
        fast_stroke(head, store, surface, definition, base, live, frame, bounding, kind, "Poren spray", "test/poren",
                    600, settings=spray_settings(brush_api), crossings=10, row="P-K")

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

    print("\nP-F save of a 4-layer stack (base image cache cleared: a cold read, as at the first save of a session)")
    files.clear_image_cache()
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
