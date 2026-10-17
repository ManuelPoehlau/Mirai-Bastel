"""GPU ID-buffer picking vs the production CPU picker: same picks? what cost? (spike)

Usage (from the repo root, Windows and Linux alike; opens a hidden pyglet window):
    python experiments/gpu_picking_spike/probe_gpu_picking.py
    python experiments/gpu_picking_spike/probe_gpu_picking.py --assets examples/meshes/gollum.obj
    python experiments/gpu_picking_spike/probe_gpu_picking.py --cursors 100 --no-box

Headless container: prefix with `xvfb-run -a`.

Per asset, framed from the front and from the back (as `tests/test_picking_equivalence.py`):

- agreement: `--cursors` seeded integer cursor positions inside the mesh's screen bbox (the
  window delivers integer pixels), vertex / edge / face mode, Shaded (occlusion) and Wireframe.
  Production `pick_component` (with `PickCache`) against `GpuIdPicker`. A difference is
  `half-px` when the CPU picker gives the GPU's answer at the pixel centre (x + 0.5, y + 0.5) -
  where the GPU samples visibility - so only the sampling convention differs; else `real`
  (split into GPU none / CPU none / other element).
- box: 60 / 150 / 300 px around the mesh centre, all three modes, Shaded: production
  `elements_in_rect` against `GpuIdPicker.elements_in_rect` ("ids": the elements with a surviving
  ID pixel) and `elements_in_rect_depth` ("depth": CPU candidates, depth-buffer visibility); per
  variant the count, `-` = selected by the CPU only, `+` = by the GPU variant only.
  `vertex+depth` is the hover variant with the depth oracle (`pick_vertex_depth`).
- cost, ms p50: GPU build (per mesh state), render (per camera state; `gpu` = GL timer query),
  a pick after an orbit (render + read vs pick-cache rebuild + pick), a hover pick with a valid
  state, Box 300 px.

Changes nothing under `src/`. Numbers from a container (llvmpipe: the "GPU" is the CPU) must be
labelled as such (`docs/architecture/REFERENCE_HARDWARE.md` §4); the reference PC decides.
Output is plain ASCII so it pastes cleanly from a Windows console.
"""

from __future__ import annotations

import argparse
import math
import os
import platform
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from gpu_picking_spike._paths import REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

WIDTH, HEIGHT = 1024, 768
GOLLUM_20K = "examples/meshes/gollum_20k.obj"
GOLLUM = "examples/meshes/gollum.obj"
DEFAULT_ASSETS = ("head_basemesh", "man_with_shoes_basemesh", GOLLUM_20K)
DEFAULT_CURSORS = 300
DEFAULT_REPEATS = 15
BOX_SIZES = (60, 150, 300)
MODES = ("vertex", "edge", "face")
#: Agreement rows: (row name, CPU mode name, GPU picker method).
PICK_ROWS = (("vertex", "vertex", "pick_vertex"), ("vertex+depth", "vertex", "pick_vertex_depth"),
             ("edge", "edge", "pick_edge"), ("face", "face", "pick_face"))
ORBIT_RAD = 0.01


def resolve_asset(spec: str) -> tuple[str, Path]:
    from loaders.assets import asset_names, asset_path

    if spec in asset_names():
        return spec, Path(asset_path(spec))
    for path in (Path(spec), REPO_ROOT / spec):
        if path.suffix.lower() == ".obj" and path.is_file():
            return path.stem, path.resolve()
    raise ValueError(f"unknown asset {spec!r}: neither a registry name nor an existing .obj file")


def _positive_int(text: str) -> int:
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be positive, got {value}")
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GPU ID-buffer picking vs the CPU picker (spike)")
    parser.add_argument("--assets", nargs="+", default=list(DEFAULT_ASSETS),
                        help=f"registry names or .obj paths (default: head_basemesh man_with_shoes_basemesh "
                             f"{GOLLUM_20K}; the 87.5k stress case: {GOLLUM})")
    parser.add_argument("--cursors", type=_positive_int, default=DEFAULT_CURSORS,
                        help=f"cursor positions per camera for the agreement rows (default {DEFAULT_CURSORS})")
    parser.add_argument("--repeats", type=_positive_int, default=DEFAULT_REPEATS,
                        help=f"samples per cost row (default {DEFAULT_REPEATS})")
    parser.add_argument("--no-box", action="store_true", help="skip the Box rows")
    args = parser.parse_args(argv)
    for spec in args.assets:
        try:
            resolve_asset(spec)
        except ValueError as exc:
            parser.error(str(exc))
    return args


# -- agreement ------------------------------------------------------------------------


@dataclass
class Agreement:
    same: int = 0
    half_px: int = 0
    gpu_none: int = 0
    cpu_none: int = 0
    other: int = 0
    examples: list = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.same + self.half_px + self.gpu_none + self.cpu_none + self.other

    @property
    def real(self) -> int:
        return self.gpu_none + self.cpu_none + self.other

    def add(self, cpu, gpu, cpu_centre, where) -> None:
        if _same(cpu, gpu):
            self.same += 1
            return
        if _same(cpu_centre, gpu):
            self.half_px += 1
            return
        if gpu is None:
            self.gpu_none += 1
        elif cpu is None:
            self.cpu_none += 1
        else:
            self.other += 1
        if len(self.examples) < 3:
            self.examples.append((where, cpu, gpu))


def _same(a, b) -> bool:
    return type(a) is type(b) and a == b


def screen_bbox(camera, mesh) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for vid in mesh.all_vertex_ids():
        p = camera.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
        if p is not None:
            xs.append(p[0])
            ys.append(p[1])
    return (max(0.0, min(xs)), max(0.0, min(ys)), min(WIDTH - 1.0, max(xs)), min(HEIGHT - 1.0, max(ys)))


def cursors(camera, mesh, count: int, seed: int) -> list[tuple[int, int]]:
    x0, y0, x1, y1 = screen_bbox(camera, mesh)
    rng = random.Random(seed)
    return [(rng.randint(int(x0), int(x1)), rng.randint(int(y0), int(y1))) for _ in range(count)]


def framed_cameras(mesh):
    from mirai.mesh_geometry import mesh_center_and_radius
    from mirai.viewport.camera import OrbitCamera

    center, radius = mesh_center_and_radius(mesh)
    cameras = []
    for name, yaw, pitch in (("front", 30, 15), ("back", 210, -20)):
        camera = OrbitCamera(yaw=math.radians(yaw), pitch=math.radians(pitch))
        camera.frame_on_bounds(center, radius)
        cameras.append((name, camera))
    return cameras


def agreement_rows(mesh, gpu, cfg) -> dict:
    from core import SelectionMode
    from mirai.viewport.picking import pick_component
    from mirai.viewport.picking_cache import PickCache

    modes = {"vertex": SelectionMode.VERTEX, "edge": SelectionMode.EDGE, "face": SelectionMode.FACE}
    rows: dict = {}
    for cam_index, (cam_name, camera) in enumerate(framed_cameras(mesh)):
        points = cursors(camera, mesh, cfg.cursors, seed=100 + cam_index)
        for occlusion in (True, False):
            gpu.render(camera, occlusion=occlusion)
            cache = PickCache()
            for name, mode_name, method in PICK_ROWS:
                if mode_name == "face" and not occlusion:
                    continue  # a face pick has no occlusion switch: once is enough
                row = rows.setdefault((name, occlusion), Agreement())
                pick = getattr(gpu, method)
                for x, y in points:
                    cpu = pick_component(camera, mesh, modes[mode_name], x, y, WIDTH, HEIGHT,
                                         cache=cache, occlusion=occlusion)
                    got = pick(x, y)
                    centre = cpu
                    if not _same(cpu, got):
                        centre = pick_component(camera, mesh, modes[mode_name], x + 0.5, y + 0.5, WIDTH, HEIGHT,
                                                cache=cache, occlusion=occlusion)
                    row.add(cpu, got, centre, f"{cam_name} ({x},{y})")
    return rows


def box_rows(mesh, gpu) -> list[tuple]:
    from core import SelectionMode
    from mirai.mesh_geometry import mesh_center_and_radius
    from mirai.viewport.box_select import elements_in_rect
    from mirai.viewport.picking_cache import PickCache

    from gpu_picking_spike.id_picker import EDGES, FACES, VERTICES

    targets = {"vertex": (SelectionMode.VERTEX, VERTICES), "edge": (SelectionMode.EDGE, EDGES),
               "face": (SelectionMode.FACE, FACES)}
    out = []
    for cam_name, camera in framed_cameras(mesh):
        center, _radius = mesh_center_and_radius(mesh)
        cx, cy = camera.project_to_screen(center, WIDTH, HEIGHT)
        gpu.render(camera, occlusion=True)
        for size in BOX_SIZES:
            rect = (cx - size / 2.0, cy - size / 2.0, cx + size / 2.0, cy + size / 2.0)
            for name in MODES:
                mode, target = targets[name]
                cpu = elements_in_rect(camera, mesh, mode, rect, WIDTH, HEIGHT, cache=PickCache(), occlusion=True)
                got = gpu.elements_in_rect(target, rect)
                deep = gpu.elements_in_rect_depth(target, rect)
                out.append((cam_name, size, name, len(cpu), len(got), len(cpu - got), len(got - cpu),
                            len(deep), len(cpu - deep), len(deep - cpu)))
    return out


# -- cost -----------------------------------------------------------------------------


def _p50(values: list[float]) -> float:
    return statistics.median(values) if values else float("nan")


class _TimerQuery:
    def __init__(self) -> None:
        from pyglet import gl

        self._gl = gl
        self._id = gl.GLuint()
        gl.glGenQueries(1, self._id)

    def begin(self) -> None:
        self._gl.glBeginQuery(self._gl.GL_TIME_ELAPSED, self._id)

    def end_ms(self) -> float:
        gl = self._gl
        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        result = gl.GLuint64()
        gl.glGetQueryObjectui64v(self._id, gl.GL_QUERY_RESULT, result)
        return result.value / 1e6


def cost_rows(mesh, label: str, path: Path, cfg, gpu_build_ms: float, gpu) -> list[tuple[str, float, float | None]]:
    """(row, cpu ms, gpu ms) - the CPU column is the production picker."""
    from pyglet import gl

    from core import SelectionMode
    from mirai.viewport.box_select import elements_in_rect
    from mirai.viewport.picking import pick_component
    from mirai.viewport.picking_cache import PickCache

    from gpu_picking_spike.id_picker import VERTICES

    _name, camera = framed_cameras(mesh)[0]
    points = cursors(camera, mesh, cfg.repeats, seed=7)
    try:
        query = _TimerQuery()
    except Exception:  # a driver without GL_TIME_ELAPSED: no gpu column
        query = None
    rows: list[tuple[str, float, float | None]] = [("build (per mesh state)", float("nan"), gpu_build_ms)]

    render_ms, render_gpu = [], []
    for i in range(cfg.repeats):
        camera.orbit(ORBIT_RAD if i % 2 == 0 else -ORBIT_RAD, 0.0)
        start = time.perf_counter()
        if query is not None:
            query.begin()
        gpu.render(camera)
        if query is not None:
            render_gpu.append(query.end_ms())
        gl.glFinish()
        render_ms.append((time.perf_counter() - start) * 1000.0)
    rows.append(("render (per camera state), wall", float("nan"), _p50(render_ms)))
    if render_gpu:
        rows.append(("render, GL timer (GPU time)", float("nan"), _p50(render_gpu)))

    cache = PickCache()
    for name, mode, pick in (("vertex", SelectionMode.VERTEX, gpu.pick_vertex),
                             ("vertex+depth", SelectionMode.VERTEX, gpu.pick_vertex_depth),
                             ("edge", SelectionMode.EDGE, gpu.pick_edge),
                             ("face", SelectionMode.FACE, gpu.pick_face)):
        cpu_after, gpu_after, cpu_hover, gpu_hover = [], [], [], []
        for i, (x, y) in enumerate(points):
            camera.orbit(ORBIT_RAD if i % 2 == 0 else -ORBIT_RAD, 0.0)
            start = time.perf_counter()
            pick_component(camera, mesh, mode, x, y, WIDTH, HEIGHT, cache=cache, occlusion=True)
            cpu_after.append((time.perf_counter() - start) * 1000.0)
            start = time.perf_counter()
            gpu.render(camera)
            pick(x, y)
            gpu_after.append((time.perf_counter() - start) * 1000.0)
            start = time.perf_counter()
            pick_component(camera, mesh, mode, x + 1, y, WIDTH, HEIGHT, cache=cache, occlusion=True)
            cpu_hover.append((time.perf_counter() - start) * 1000.0)
            start = time.perf_counter()
            pick(x + 1, y)
            gpu_hover.append((time.perf_counter() - start) * 1000.0)
        rows.append((f"{name}: pick after an orbit", _p50(cpu_after), _p50(gpu_after)))
        rows.append((f"{name}: hover pick, valid state", _p50(cpu_hover), _p50(gpu_hover)))

    if not cfg.no_box:
        from mirai.mesh_geometry import mesh_center_and_radius

        center, _radius = mesh_center_and_radius(mesh)
        cx, cy = camera.project_to_screen(center, WIDTH, HEIGHT)
        rect = (cx - 150.0, cy - 150.0, cx + 150.0, cy + 150.0)
        cache = PickCache()
        cache.refresh(camera, mesh, WIDTH, HEIGHT)
        gpu.render(camera)
        cpu_box, gpu_box, deep_box = [], [], []
        for _ in range(max(1, min(cfg.repeats, 5))):
            start = time.perf_counter()
            elements_in_rect(camera, mesh, SelectionMode.VERTEX, rect, WIDTH, HEIGHT, cache=cache, occlusion=True)
            cpu_box.append((time.perf_counter() - start) * 1000.0)
            start = time.perf_counter()
            gpu.elements_in_rect(VERTICES, rect)
            gpu_box.append((time.perf_counter() - start) * 1000.0)
            start = time.perf_counter()
            gpu.elements_in_rect_depth(VERTICES, rect)
            deep_box.append((time.perf_counter() - start) * 1000.0)
        rows.append(("box 300 px vertex, valid state", _p50(cpu_box), _p50(gpu_box)))
        rows.append(("box 300 px vertex, depth variant", _p50(cpu_box), _p50(deep_box)))
    return rows


# -- driver + report ---------------------------------------------------------------------


def machine_lines(gl_version: str, gl_renderer: str) -> list[str]:
    cpu = platform.processor() or "unknown"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    return [
        f"Platform: {platform.platform()}",
        f"CPU: {cpu} ({os.cpu_count()} logical cores)",
        f"Python: {platform.python_version()}",
        f"GL_VERSION: {gl_version}",
        f"GL_RENDERER: {gl_renderer}",
    ]


def agreement_lines(rows: dict) -> list[str]:
    lines = []
    for (name, occlusion), row in rows.items():
        shade = "shaded" if occlusion else "wire  "
        pct = 100.0 * row.same / row.total if row.total else float("nan")
        lines.append(
            f"  agree {name:12s} {shade} n={row.total:4d}  same {row.same:4d} ({pct:5.1f}%)  half-px {row.half_px:3d}"
            f"  real {row.real:3d} [gpu none {row.gpu_none}, cpu none {row.cpu_none}, other {row.other}]"
        )
        for where, cpu, gpu in row.examples:
            lines.append(f"      e.g. {where}: cpu {cpu!r} gpu {gpu!r}")
    return lines


def box_lines(rows) -> list[str]:
    return [
        f"  box {cam:5s} {size:3d} px {name:6s} cpu {n_cpu:5d} | ids {n_gpu:5d} -{only_cpu:4d} +{only_gpu:4d}"
        f" | depth {n_deep:5d} -{deep_cpu:4d} +{deep_gpu:4d}"
        for cam, size, name, n_cpu, n_gpu, only_cpu, only_gpu, n_deep, deep_cpu, deep_gpu in rows
    ]


def cost_lines(rows) -> list[str]:
    def fmt(v):
        return "     -   " if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:9.2f}"

    return [f"  cost {name:34s} cpu {fmt(cpu)}  gpu {fmt(gpu)}" for name, cpu, gpu in rows]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    import pyglet

    from mirai.scene_factory import build_core_scene_from_obj

    from gpu_picking_spike.id_picker import GpuIdPicker

    window = pyglet.window.Window(width=WIDTH, height=HEIGHT, visible=False)
    from pyglet.gl import gl_info

    lines = ["GPU ID-buffer picking vs CPU picker (spike, WP-VIEW-PERF-02), ms p50"]
    lines += machine_lines(gl_info.get_version_string(), gl_info.get_renderer())
    lines.append(f"Run: hidden {WIDTH}x{HEIGHT} window, {args.cursors} cursors per camera (front, back), "
                 f"{args.repeats} samples per cost row")
    try:
        for spec in args.assets:
            label, path = resolve_asset(spec)
            print(f"... {label}", file=sys.stderr, flush=True)
            mesh = build_core_scene_from_obj(path).mesh
            start = time.perf_counter()
            gpu = GpuIdPicker(mesh, WIDTH, HEIGHT)
            build_ms = (time.perf_counter() - start) * 1000.0
            lines.append("")
            lines.append(f"[{label}] {len(mesh.all_vertex_ids())} V / {len(mesh.all_edge_ids())} E / "
                         f"{len(mesh.all_face_ids())} F")
            lines += agreement_lines(agreement_rows(mesh, gpu, args))
            if not args.no_box:
                lines += box_lines(box_rows(mesh, gpu))
            lines += cost_lines(cost_rows(mesh, label, path, args, build_ms, gpu))
            gpu.release()
    finally:
        window.close()
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
