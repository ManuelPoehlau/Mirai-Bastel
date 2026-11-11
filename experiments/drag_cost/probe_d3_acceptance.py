"""D3 acceptance probe (2026-11-11): the complete interaction frame of a jaw-sized deformation, Morph and Skin active.

Usage (from the repo root, Windows and Linux alike; opens a hidden 1024x768 pyglet window):
    python experiments/drag_cost/probe_d3_acceptance.py
    python experiments/drag_cost/probe_d3_acceptance.py --asset examples/meshes/gollum_20k.obj --steps 60
    python experiments/drag_cost/probe_d3_acceptance.py --no-panels

Headless container: prefix with `xvfb-run -a`.

The bar is Manu's decision D3 (`docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md`,
"Decisions (Manu, 2026-11-11)"): about 100k base faces, a jaw-sized region of about 15 % of the vertices, Morph and
Skin active together, the complete interaction frame (evaluation, viewport synchronisation, overlays, drawing), wire
ON and OFF; minimum p95 <= 33.3 ms (30 FPS), preferred p95 <= 16.7 ms (60 FPS), on the reference PC.

Scenario (the same for both wire states):
- mesh: `fixtures/gollum_87k.obj` (87 500 V / 87 500 quads, Manu D5); the numbers are for 87.5k, not scaled to 100k;
- rig: the jaw rule of `probe_morph_gl.rig_region` (lowest-Y 15 % of the points; 70 % of them on the jaw bone, 30 %
  shared with its child), the same rig as the scale audit's pose-step rows;
- morph: one target whose offsets lie on exactly those points ("jaw open"), dialled in at 60 %;
- `pose`: pose mode, E held, one mouse move per frame - the skin stage re-evaluates the region every frame;
- `weight`: posed (after the pose rows), N held, one mouse move per frame (one weight percent) - the mix changes on
  the region and the skin stage follows.

One frame = the input event (`Application.pointer_motion`, what the window's mouse handler calls) + the window tick
(`Application.update_viewport`: stage evaluation + `Viewport.sync`) + the window's own `on_draw` of `src/main.py`
(`install_handlers`: viewport sync + render with the overlays, bones / gizmo, HUD, triad and, unless `--no-panels`,
the panel layer) + `glFinish`. Reported per row: the frame p50 / p95 / max, its three parts, the split of the tick
(stage evaluation, `RenderMesh._sync_geometry`, the face-data part of it), the split of `on_draw` (viewport render,
gizmo / bones, HUD, triad, panels, the rest incl. the GPU wait in `glFinish`; added 2026-11-11 after the reference-PC
run showed `on_draw` at 35-64 ms) and the bytes handed to the GL store per frame by resource group. No `flip` (hidden
window, no vsync wait).

The output names the commit and whether the working tree had changes (audit addendum 2026-11-10: "record those on
the next baseline run"). Numbers from a container are not reference-PC numbers (`REFERENCE_HARDWARE.md` §4); llvmpipe
draws on the CPU. Plain ASCII.
"""

from __future__ import annotations

import argparse
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import EXPERIMENT_DIR, REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

DENSE = EXPERIMENT_DIR / "fixtures" / "gollum_87k.obj"
DEFAULT_REGION = 15
DEFAULT_STEPS = 60
WARMUP_STEPS = 6
MORPH_WEIGHT = 60
INTERACTIONS = ("pose", "weight")
BAR_MIN_P95_MS = 33.3
BAR_PREFERRED_P95_MS = 16.7

#: Timed methods: (module, class, method, row). A method missing in the checked-out code is skipped, so the same probe
#: measures the code before and after a change of the face-data layout (O2: `_upload_rows` -> `_upload_face_normals`).
TIMED = (
    ("mirai.morph_mix", "MixSurface", "_recompute", "eval"),
    ("mirai.skinning", "SkinSurface", "_recompute", "eval"),
    ("viewport.render_mesh", "RenderMesh", "_sync_geometry", "sync_geometry"),
    ("viewport.render_mesh", "RenderMesh", "_upload_rows", "face_data"),
    ("viewport.render_mesh", "RenderMesh", "_upload_face_normals", "face_data"),
    ("viewport.viewport", "Viewport", "_sync_edges", "wire"),
    ("viewport.gl_render_store", "GLRenderStore", "_flush_face_data", "face_flush"),
    # Inside the window's `on_draw` (`src/main.py`); `None` = a module-level function of that module.
    ("viewport.viewport", "Viewport", "render", "draw_viewport"),
    ("mirai.application", "Application", "gizmo_items", "draw_gizmo"),
    ("mirai.application", "Application", "pivot_marker_items", "draw_gizmo"),
    ("mirai.application", "Application", "bone_items", "draw_gizmo"),
    ("main", None, "draw_gizmo", "draw_gizmo"),
    ("hud", "Hud", "update", "draw_hud"),
    ("hud", "Hud", "draw", "draw_hud"),
    ("hud", "OrientationTriad", "draw", "draw_triad"),
    ("gui.imgui_layer", "ImguiLayer", "draw", "draw_panels"),
)
#: The parts of `on_draw` reported under it; the rest of the column is the clear, the second `Viewport.sync` and the
#: wait for the GPU in `glFinish`.
DRAW_ROWS = {
    "draw_viewport": "viewport render (faces, wire, overlays)",
    "draw_gizmo": "gizmo / bones",
    "draw_hud": "HUD",
    "draw_triad": "triad",
    "draw_panels": "panels",
}
VERTEX_RESOURCES = frozenset({"positions", "normals", "indices"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--asset", default=str(DENSE.relative_to(REPO_ROOT)),
                        help="OBJ path relative to the repo root (default: the 87.5k fixture)")
    parser.add_argument("--region", type=int, default=DEFAULT_REGION, help="share of the points in percent")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="measured frames per row")
    parser.add_argument("--interactions", nargs="+", choices=INTERACTIONS, default=list(INTERACTIONS))
    parser.add_argument("--no-panels", action="store_true", help="draw without the panel layer (imgui)")
    return parser


def resolve_asset(name: str) -> Path:
    path = Path(name)
    path = path if path.is_absolute() else REPO_ROOT / path
    if not path.is_file():
        raise SystemExit(f"no such mesh: {name}")
    return path


def source_state() -> str:
    """Commit and working-tree state of the checkout the probe imports (`git` absent = 'unknown')."""
    try:
        head = subprocess.run(["git", "rev-parse", "--short=10", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO_ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "commit unknown (no git)"
    return f"commit {head}, working tree {'MODIFIED' if dirty else 'clean'}"


def percentile(samples: list[float], q: float) -> float:
    """Nearest-rank percentile (as `probe_drag_gl.Stats`)."""
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))]


def verdict(p95: float) -> str:
    if p95 <= BAR_PREFERRED_P95_MS:
        return "meets 16.7 (60 FPS)"
    if p95 <= BAR_MIN_P95_MS:
        return "meets 33.3 (30 FPS), not 16.7"
    return "OVER 33.3"


def resource_group(name: str) -> str:
    if name in VERTEX_RESOURCES:
        return "vertex"
    if name.startswith(("face_", "triangle_")):
        return "face"
    return "other"


class Meter:
    """Timing wrappers on class methods and a byte counter on `GLRenderStore.update`, removed by `remove()`."""

    def __init__(self) -> None:
        import importlib

        self.ms: dict[str, float] = {}
        self.bytes: dict[str, int] = {}
        self.present: set[str] = set()
        self._undo: list = []
        self._depth: dict[str, int] = {}
        for module, cls_name, method, row in TIMED:
            try:
                owner = importlib.import_module(module)
            except ImportError:  # e.g. the panel layer without imgui-bundle
                continue
            owner = owner if cls_name is None else getattr(owner, cls_name)
            if hasattr(owner, method):
                self._time(owner, method, row)
                self.present.add(f"{cls_name or module}.{method}")
        from viewport.gl_render_store import GLRenderStore

        original = GLRenderStore.update
        sent = self.bytes

        def counting(store, name, offset, data, nbytes):
            group = resource_group(name)
            sent[group] = sent.get(group, 0) + nbytes
            return original(store, name, offset, data, nbytes)

        GLRenderStore.update = counting
        self._undo.append((GLRenderStore, "update", original))

    def _time(self, cls, name: str, row: str) -> None:
        original = getattr(cls, name)
        acc = self.ms
        depth = self._depth  # per row: a recursive or nested call of the same row counts once

        def timed(*args, **kwargs):
            depth[row] = depth.get(row, 0) + 1
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                depth[row] -= 1
                if depth[row] == 0:
                    acc[row] = acc.get(row, 0.0) + (time.perf_counter() - start) * 1000.0

        setattr(cls, name, timed)
        self._undo.append((cls, name, original))

    def reset(self) -> None:
        self.ms.clear()
        self.bytes.clear()

    def remove(self) -> None:
        for cls, name, original in reversed(self._undo):
            setattr(cls, name, original)
        self._undo.clear()


def jaw_morph(app, share: int) -> int:
    """A new morph target with offsets on exactly the points `rig_region(app, share)` weights ("jaw open": down and
    forward, strongest at the bottom), dialled in at `MORPH_WEIGHT` %. Returns the number of points it moves."""
    from drag_cost.probe_morph_gl import _key

    mesh = app.scene.mesh
    ids = sorted(mesh.all_vertex_ids(), key=lambda v: (mesh.vertex_position(v)[1], int(v)))
    region = ids[: max(1, len(ids) * share // 100)]
    ys = [mesh.vertex_position(v)[1] for v in region]
    low, top = min(ys), max(ys)
    span = max(top - low, 1e-3)
    app.key_press(_key("n", "ctrl"))  # a new target (the host entry of the panel's "+")
    lid = app.morph_current_target

    def write():
        for v in region:
            t = (top - mesh.vertex_position(v)[1]) / span  # 1 at the chin, 0 at the region's top
            mesh.set_layer_value(lid, v, (0.0, -0.08 * span * t - 1e-6, 0.04 * span * t + 1e-6))

    app.apply_mesh_change("probe jaw target", lambda: write() or set())
    app.set_morph_weight(MORPH_WEIGHT)
    return len(region)


class Frame:
    """One window frame as `src/main.py` runs it: input, tick, `on_draw`, `glFinish`."""

    def __init__(self, window, app) -> None:
        self.window, self.app = window, app

    def __call__(self, motion: tuple[float, float, float, float] | None) -> tuple[float, float, float]:
        from pyglet import gl
        from pyglet.event import EventDispatcher

        app = self.app
        t0 = time.perf_counter()
        if motion is not None:
            app.pointer_motion(*motion)
        t1 = time.perf_counter()
        app.update_viewport(1.0 / 60.0)
        t2 = time.perf_counter()
        # Straight to the handlers: `Window.dispatch_event` only queues while no event loop runs.
        EventDispatcher.dispatch_event(self.window, "on_draw")
        gl.glFinish()
        t3 = time.perf_counter()
        return (t1 - t0) * 1000.0, (t2 - t1) * 1000.0, (t3 - t2) * 1000.0


def build(path: Path, share: int, panels: bool):
    """The window, `Application`, the window's handlers and draw (`install_handlers` with HUD, triad, panels), the
    jaw rig and the jaw morph target at `MORPH_WEIGHT` %. Returns (window, app, frame, weighted, morphed, panels)."""
    import main as src_main
    from drag_cost.probe_morph_gl import build_app, rig_region
    from hud import Hud, OrientationTriad

    window, app = build_app(path)
    gui = src_main.make_gui(window, app) if panels else None
    src_main.install_handlers(window, app, hud=Hud(app.bindings), triad=OrientationTriad(), gui=gui)
    app.gizmo_enabled = True  # the window draws the gizmo / bones (src/main.py `main`)
    weighted = rig_region(app, share)
    morphed = jaw_morph(app, share)
    frame = Frame(window, app)
    frame(None)
    return window, app, frame, weighted, morphed, gui is not None


def run_rows(path: Path, share: int, steps: int, interactions, panels: bool) -> list[str]:
    from drag_cost.probe_morph_gl import _key
    from mirai.morph_targets import DRAG_PIXELS_PER_PERCENT

    meter = Meter()
    lines: list[str] = []
    try:
        window, app, frame, weighted, morphed, panels_on = build(path, share, panels)
        mesh = app.scene.mesh
        lines.append(
            f"[{path.stem}] {len(mesh.all_vertex_ids())} V / {len(mesh.all_face_ids())} F; region {share} %: "
            f"{weighted} V weighted, {morphed} V in the morph target at {app.morph_weight} %; "
            f"panels {'on' if panels_on else 'off'}"
        )
        lines.append("  timed: " + ", ".join(sorted(meter.present)))
        e, n = _key("e"), _key("n")
        for wire in (False, True):
            app.viewport.set_display(True, wire, False)
            for interaction in interactions:
                if interaction == "pose":
                    app.pointer_motion(560, 300, 0.0, 0.0)
                    if not app.pose_mode:
                        app.key_press(_key("5"))
                    app.key_press(e)
                    app.pointer_motion(560, 296, 0.0, -4.0)

                    def motion(i):
                        return 560, 296, 0.0, -4.0 if (i // 20) % 2 == 0 else 4.0
                else:
                    if not app.posed:
                        raise RuntimeError("weight rows need the pose of the pose rows (run 'pose' first)")
                    app.key_press(n)
                    app.pointer_motion(400, 300, DRAG_PIXELS_PER_PERCENT, 0.0)
                    direction = [1.0]

                    def motion(i):
                        if app.morph_weight >= 95:
                            direction[0] = -1.0
                        elif app.morph_weight <= 30:
                            direction[0] = 1.0
                        return 400, 300, direction[0] * DRAG_PIXELS_PER_PERCENT, 0.0
                frame(None)
                for i in range(WARMUP_STEPS):  # the first frames after a build run slower (caches, allocator)
                    frame(motion(i))
                totals, parts, rows, sent = [], [], {}, {}
                for i in range(steps):
                    meter.reset()
                    inp, tick, draw = frame(motion(WARMUP_STEPS + i))
                    totals.append(inp + tick + draw)
                    parts.append((inp, tick, draw))
                    for row in ("eval", "sync_geometry", "face_data", "wire", "face_flush", *DRAW_ROWS):
                        rows.setdefault(row, []).append(meter.ms.get(row, 0.0))
                    rows.setdefault("draw_rest", []).append(draw - sum(meter.ms.get(row, 0.0) for row in DRAW_ROWS))
                    for group in ("vertex", "face", "other"):
                        sent.setdefault(group, []).append(meter.bytes.get(group, 0))
                if interaction == "pose":
                    app.key_release(e)
                    if not app.posed:
                        raise RuntimeError(f"pose rows: not posed ({app.status_message})")
                else:
                    app.key_release(n)
                lines.extend(report(interaction, wire, totals, parts, rows, sent, weighted))
        window.close()
    finally:
        meter.remove()
    return lines


def report(interaction, wire, totals, parts, rows, sent, weighted) -> list[str]:
    p50, p95, top = statistics.median(totals), percentile(totals, 0.95), max(totals)
    out = [
        "",
        f"  {interaction:<6} wire {'ON ' if wire else 'off'}  frame  p50 {p50:8.2f}  p95 {p95:8.2f}  max {top:8.2f} ms"
        f"   [{verdict(p95)}]",
    ]
    for k, label in enumerate(("input (pointer_motion)", "tick (update_viewport)", "on_draw + glFinish")):
        values = [p[k] for p in parts]
        out.append(f"    {label:<40} p50 {statistics.median(values):8.2f}  p95 {percentile(values, 0.95):8.2f}")
    labels = {
        "eval": "  tick: stage evaluation (mix + skin)",
        "sync_geometry": "  tick: RenderMesh._sync_geometry",
        "face_data": "    of it: face data -> store",
        "wire": "  tick: wire segments rebuild",
    }
    for row, label in DRAW_ROWS.items():
        labels[row] = "  draw: " + label
        if row == "draw_viewport":
            labels["face_flush"] = "    of it: face-data upload"
    labels["draw_rest"] = "  draw: rest (clear, sync, GPU wait)"
    for row, label in labels.items():
        values = rows.get(row, [])
        if not values or (row in ("wire", *DRAW_ROWS) and not any(values)):
            continue
        out.append(f"    {label:<40} p50 {statistics.median(values):8.2f}  p95 {percentile(values, 0.95):8.2f}")
    total_bytes = [sum(v) for v in zip(*sent.values())]
    face = statistics.median(sent.get("face", [0]))
    vertex = statistics.median(sent.get("vertex", [0]))
    out.append(
        f"    bytes to the GL store per frame          {int(statistics.median(total_bytes)):>9}"
        f"  (vertex {int(vertex)}, face data {int(face)}; {statistics.median(total_bytes) / max(weighted, 1):.0f}"
        f" per region vertex)"
    )
    return out


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = resolve_asset(args.asset)
    import pyglet

    from drag_cost.probe_drag_gl import HEIGHT, WIDTH, machine_info

    probe = pyglet.window.Window(width=64, height=64, visible=False)
    info = machine_info(pyglet.gl.gl_info.get_version_string(), pyglet.gl.gl_info.get_renderer())
    probe.close()
    print("D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active")
    for line in info:
        print(line)
    print(f"Source: {source_state()}")
    print(
        f"Run: hidden {WIDTH}x{HEIGHT} window, {args.steps} frames per row after {WARMUP_STEPS} unmeasured; "
        f"bar (D3): p95 <= {BAR_MIN_P95_MS} ms minimum, <= {BAR_PREFERRED_P95_MS} ms preferred"
    )
    print()
    for line in run_rows(path, args.region, args.steps, args.interactions, not args.no_panels):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
