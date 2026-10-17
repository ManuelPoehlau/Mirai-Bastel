"""Navigation and picking cost with the real GL backend (WP-VIEW-PERF-01, Discovery).

Usage (from the repo root, Windows and Linux alike; opens a hidden pyglet window):
    python experiments/drag_cost/probe_navigation_gl.py
    python experiments/drag_cost/probe_navigation_gl.py --assets examples/meshes/gollum.obj
    python experiments/drag_cost/probe_navigation_gl.py --scenarios direct
    python experiments/drag_cost/probe_navigation_gl.py --scenarios orbit zoom first_hover
    python experiments/drag_cost/probe_navigation_gl.py --list

Headless container: prefix with `xvfb-run -a`.

Question: where does the time go per input event and per frame when the Artist orbits, pans,
zooms, hovers and clicks on a high-resolution mesh? Same chain as `probe_drag_gl.py`
(`Application` -> `Viewport` -> `GLRenderStore` + the `GL_TYPES` overlays of `src/main.py`),
driven through the public `Application.pointer_*` / `key_*` entry points the window uses.

Per sample (one input event followed by one frame), in ms:

- event     the `Application` handler for the event (`pointer_drag`, `pointer_scroll`,
            `pointer_motion`, press + release for a click)
- pick      the part of `event` inside `pick_component` (the hover/click picker), of which
            `cache` = `PickCache.refresh` (counted as a rebuild when its signature changed) and
            `occl` = the occlusion tests (`vertex_occluded` / `edge_point_occluded`, with count)
- sync      `Viewport.sync()` (as `on_draw`)
- draw      `Viewport.render()` + `glFinish()` (CPU wall time; llvmpipe in a container is a
            software rasteriser, so this is not the reference PC's GPU time)
- gpu       GL_TIME_ELAPSED query around `Viewport.render()` (real GPU time on a real GPU)
- upload    bytes pyglet committed to GL buffers during the frame (dirty-region commits)
- frame     event + sync + draw

The instrumentation wraps functions from the outside (module attributes, one instance
attribute, one pyglet class method); nothing under `src/` is changed.

Extra scenarios: `orbit_wire` (orbit with the Shift+D wire overlay on, H5), `loop` (the real
`install_handlers` wiring inside a running `pyglet.app` loop with injected events: on_draw count
vs event count and the longest time without a frame, H3), `plain_w` / `soft_w` (the drag
scenarios of `probe_drag_gl.py`, reused, with this handoff's sizes). A cProfile top-N for orbit,
zoom and first hover runs on the last asset (`--profile-top 0` switches it off).

Scenario `direct` (WP-VIEW-PERF-01 Slice 1, step 0): the rows the 2026-10-17 audit measured in a
scratch probe, on the same rig, with the picking functions called directly (no frame): hover in
vertex / edge / face mode and the Knife hover (`knife_pick`) along the hover line, one Paint step
(30 px = 5 picks, `Application._paint_at`), Box Select 60 / 150 / 300 px in vertex and face mode
(`elements_in_rect`), the retopology snap query (`pick_face` + `face_hit_position`) with a valid
cache and after an orbit, a pick-cache rebuild and one `recompute_bounds` over all vertices.
The camera is framed again first (`frame_scene`), so the rows are comparable between runs.

Rows have a time budget (`--row-seconds`): on a mesh where one event costs a second, a row stops
after the budget with at least `--min-steps` samples; `n` says how many were taken.

Numbers from a container must be labelled as such (`docs/architecture/REFERENCE_HARDWARE.md` §4);
the reference PC decides. Output is plain ASCII so it pastes cleanly from a Windows console.
"""

from __future__ import annotations

import argparse
import contextlib
import cProfile
import io
import math
import pstats
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Stage 0 (script start): experiments/ on sys.path, as in probe_drag_gl.py.
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

from drag_cost import probe_drag_gl as drag  # noqa: E402

#: The 87 500 V Reference-mesh stress case (since 2026-10-13; selectable with --assets).
GOLLUM = "examples/meshes/gollum.obj"
#: The 21 875 V mesh of every reference-PC number so far (README "Audit at HEAD"): the default.
GOLLUM_20K = "examples/meshes/gollum_20k.obj"
DEFAULT_ASSETS = ("head_basemesh", "man_with_shoes_basemesh", GOLLUM_20K)
NAV_SCENARIOS = ("orbit", "pan", "zoom", "first_hover", "hover_move", "select_click", "orbit_wire")
SCENARIO_NAMES = NAV_SCENARIOS + ("direct", "loop", "plain_w", "soft_w")
DEFAULT_SCENARIOS = SCENARIO_NAMES
#: Handoff E2: plain W selection sizes (vertices) and soft W variants (radius %, metric).
PLAIN_SIZES = (36, 112, 500)
SOFT_VARIANTS = ((15, "geodesic"), (50, "geodesic"))
DEFAULT_STEPS = 40
DEFAULT_WARMUP = 3
DEFAULT_MIN_STEPS = 5
DEFAULT_ROW_SECONDS = 8.0
DEFAULT_DRAG_MOVES = 30
DEFAULT_PROFILE_TOP = 8
#: `loop`: seconds per phase and injected events per second.
LOOP_SECONDS = 2.0
LOOP_ORBIT_HZ = 240.0
LOOP_HOVER_HZ = 120.0
LOOP_ZOOM_HZ = 20.0
WIDTH, HEIGHT = drag.WIDTH, drag.HEIGHT
ORBIT_STEP_PX = 4.0
HOVER_STEP_PX = 3.0
HOVER_SPAN_PX = 60.0
#: `direct`: Box Select square sizes (px) and the Paint step length (px).
BOX_SIZES = (60, 150, 300)
PAINT_STEP_PX = 30.0
#: `direct`: orbit step (radians) before each "snap after an orbit" query.
SNAP_ORBIT_RAD = 0.01
#: One frame at 60 Hz - the budget the per-frame rows are read against (not a gate).
FRAME_BUDGET_MS = 1000.0 / 60.0


# -- argument handling (headless: no pyglet, no window) ---------------------


def resolve_asset(spec: str) -> tuple[str, Path]:
    """A registry name or a path to an `.obj` (relative to the working directory or the repo
    root) -> (label, path). Raises `ValueError` for anything else."""
    from loaders.assets import asset_names, asset_path

    if spec in asset_names():
        return spec, Path(asset_path(spec))
    candidate = Path(spec)
    for path in (candidate, REPO_ROOT / candidate):
        if path.suffix.lower() == ".obj" and path.is_file():
            return path.stem, path.resolve()
    raise ValueError(
        f"unknown asset {spec!r}: neither a registry name ({', '.join(asset_names())}) "
        "nor an existing .obj file"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Navigation and picking cost of the real GL chain (WP-VIEW-PERF-01)"
    )
    parser.add_argument("--assets", nargs="+", default=list(DEFAULT_ASSETS),
                        help="registry names or .obj paths (default: head_basemesh "
                             f"man_with_shoes_basemesh {GOLLUM_20K}; the 87.5k stress case: {GOLLUM})")
    parser.add_argument("--scenarios", nargs="+", default=list(DEFAULT_SCENARIOS),
                        help="scenario names (see --list; default: all)")
    parser.add_argument("--steps", type=drag._positive_int, default=DEFAULT_STEPS,
                        help=f"measured events per navigation row, at most (default: {DEFAULT_STEPS})")
    parser.add_argument("--min-steps", type=drag._positive_int, default=DEFAULT_MIN_STEPS,
                        help=f"samples per row even past the time budget (default: {DEFAULT_MIN_STEPS})")
    parser.add_argument("--row-seconds", type=float, default=DEFAULT_ROW_SECONDS,
                        help=f"time budget per row in seconds (default: {DEFAULT_ROW_SECONDS:g})")
    parser.add_argument("--warmup", type=drag._non_negative_int, default=DEFAULT_WARMUP,
                        help=f"unmeasured events before each row (default: {DEFAULT_WARMUP})")
    parser.add_argument("--drag-moves", type=drag._positive_int, default=DEFAULT_DRAG_MOVES,
                        help=f"plain_w / soft_w: measured mouse moves per row (default: {DEFAULT_DRAG_MOVES})")
    parser.add_argument("--profile-top", type=drag._non_negative_int, default=DEFAULT_PROFILE_TOP,
                        help="cProfile rows per profiled scenario on the last asset; 0 = no profile "
                             f"(default: {DEFAULT_PROFILE_TOP})")
    parser.add_argument("--list", action="store_true",
                        help="print scenario and asset names and exit")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parses and validates `argv`; invalid input exits with status 2 (argparse)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list:
        return args
    for spec in args.assets:
        try:
            resolve_asset(spec)
        except ValueError as exc:
            parser.error(str(exc))
    bad = [s for s in args.scenarios if s not in SCENARIO_NAMES]
    if bad:
        parser.error(f"unknown scenario {bad[0]!r}; known: {', '.join(SCENARIO_NAMES)}")
    if not (args.row_seconds > 0 and math.isfinite(args.row_seconds)):
        parser.error(f"--row-seconds must be a positive number, got {args.row_seconds}")
    if args.min_steps > args.steps:
        parser.error(f"--min-steps ({args.min_steps}) must not exceed --steps ({args.steps})")
    return args


# -- samples and statistics -------------------------------------------------


@dataclass(frozen=True)
class NavSample:
    """Milliseconds (and counts) of one input event plus the frame after it."""

    event: float
    pick: float
    cache: float
    cache_rebuilds: int
    occl: float
    occl_tests: int
    sync: float
    draw: float
    gpu: float  # NaN without a timer query
    upload_bytes: int
    hover_changed: bool = False

    @property
    def frame(self) -> float:
        return self.event + self.sync + self.draw


@dataclass(frozen=True)
class NavResult:
    scenario: str
    asset: str
    samples: tuple[NavSample, ...]
    note: str = ""

    def stats(self, name: str) -> drag.Stats:
        return drag.Stats.of([float(getattr(s, name)) for s in self.samples])

    def p50(self, name: str) -> float:
        return self.stats(name).p50


@dataclass(frozen=True)
class DirectResult:
    """`direct`: one row of direct function calls (no frame) - ms per call, occlusion tests."""

    name: str
    asset: str
    samples_ms: tuple[float, ...]
    occl_tests: tuple[int, ...]
    note: str = ""

    @property
    def stats(self) -> drag.Stats:
        return drag.Stats.of(list(self.samples_ms))


@dataclass(frozen=True)
class LoopResult:
    """`loop`: one phase of the real event loop with injected events (H3)."""

    asset: str
    phase: str
    seconds: float
    events: int
    draws: int
    syncs: int
    event_ms_mean: float
    draw_ms_mean: float
    max_gap_ms: float


@dataclass(frozen=True)
class AssetInfo:
    label: str
    path: Path
    vertices: int
    faces: int
    triangles: int
    load_ms: float


@dataclass
class AssetReport:
    info: AssetInfo
    nav: list[NavResult] = field(default_factory=list)
    direct: list[DirectResult] = field(default_factory=list)
    loops: list[LoopResult] = field(default_factory=list)
    drags: list[drag.ScenarioResult] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    profiles: list[tuple[str, list[str]]] = field(default_factory=list)


# -- instrumentation (outside `src/`) ---------------------------------------


class _Timer:
    def __init__(self) -> None:
        self.ms = 0.0
        self.calls = 0

    def reset(self) -> None:
        self.ms = 0.0
        self.calls = 0

    def wrap(self, fn: Callable) -> Callable:
        def timed(*args, **kwargs):
            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                self.ms += (time.perf_counter() - start) * 1000.0
                self.calls += 1

        timed.__wrapped__ = fn
        return timed


class Instruments:
    """Wraps the picker, the pick cache, the occlusion tests, pyglet's buffer commits and a
    GL timer query. Installed once per process (module/class level) plus once per rig
    (the `PickCache` instance)."""

    _installed = False
    pick = _Timer()
    occl = _Timer()
    upload_bytes = 0

    def __init__(self, app) -> None:
        self.cache = _Timer()
        self.cache_rebuilds = 0
        self._install_globals()
        cache = app._pick_cache
        original = cache.refresh

        def refresh(*args, **kwargs):
            before = cache._signature
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                self.cache.ms += (time.perf_counter() - start) * 1000.0
                self.cache.calls += 1
                if cache._signature != before:
                    self.cache_rebuilds += 1

        cache.refresh = refresh
        self._query = _gpu_query()

    @classmethod
    def _install_globals(cls) -> None:
        if cls._installed:
            return
        import mirai.application as application
        import mirai.viewport.box_select as box_select
        import mirai.viewport.picking as picking
        from pyglet.graphics.vertexbuffer import BackedBufferObject

        # `Application._pick` looks `pick_component` up in its module at call time; the
        # pickers look the occlusion helpers up in theirs.
        application.pick_component = cls.pick.wrap(application.pick_component)
        picking.vertex_occluded = cls.occl.wrap(picking.vertex_occluded)
        picking.edge_point_occluded = cls.occl.wrap(picking.edge_point_occluded)
        # Box Select bound its own names at import (before the lines above): wrap those too.
        for name in ("vertex_occluded", "edge_point_occluded", "point_occluded"):
            setattr(box_select, name, cls.occl.wrap(getattr(box_select, name)))

        commit = BackedBufferObject.commit

        def counted_commit(buffer):
            if buffer._dirty:
                Instruments.upload_bytes += max(0, buffer._dirty_max - buffer._dirty_min)
            return commit(buffer)

        BackedBufferObject.commit = counted_commit
        cls._installed = True

    def reset(self) -> None:
        Instruments.pick.reset()
        Instruments.occl.reset()
        Instruments.upload_bytes = 0
        self.cache.reset()
        self.cache_rebuilds = 0

    def gpu_begin(self) -> None:
        if self._query is not None:
            self._query.begin()

    def gpu_end_ms(self) -> float:
        return self._query.end_ms() if self._query is not None else float("nan")


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


def _gpu_query():
    try:
        return _TimerQuery()
    except Exception:  # GL 3.3 has GL_TIME_ELAPSED; a driver without it gives "n/a"
        return None


# -- rig ----------------------------------------------------------------------


@dataclass
class NavRig:
    drag_rig: drag.Rig
    instruments: Instruments
    info: AssetInfo

    @property
    def app(self):
        return self.drag_rig.app

    @property
    def viewport(self):
        return self.drag_rig.app.viewport

    def frame(self, event: Callable[[], object]) -> NavSample:
        """One input event, then the frame `on_draw` would draw."""
        from pyglet import gl

        app = self.app
        inst = self.instruments
        hovered_before = app.selection.hovered
        inst.reset()
        start = time.perf_counter()
        event()
        after_event = time.perf_counter()
        pick, occl, occl_n = inst.pick.ms, inst.occl.ms, inst.occl.calls
        cache, rebuilds = inst.cache.ms, inst.cache_rebuilds
        self.viewport.sync()
        after_sync = time.perf_counter()
        Instruments.upload_bytes = 0
        inst.gpu_begin()
        self.viewport.render()
        gpu = inst.gpu_end_ms()
        gl.glFinish()
        end = time.perf_counter()
        hovered_after = app.selection.hovered
        return NavSample(
            event=(after_event - start) * 1000.0,
            pick=pick,
            cache=cache,
            cache_rebuilds=rebuilds,
            occl=occl,
            occl_tests=occl_n,
            sync=(after_sync - after_event) * 1000.0,
            draw=(end - after_sync) * 1000.0,
            gpu=gpu,
            upload_bytes=Instruments.upload_bytes,
            hover_changed=not (
                type(hovered_before) is type(hovered_after) and hovered_before == hovered_after
            ),
        )

    def settle(self) -> None:
        """An unmeasured frame (after set-up steps)."""
        self.viewport.sync()
        self.viewport.render()


def build_nav_rig(label: str, path: Path, src_main) -> NavRig:
    """As `probe_drag_gl.build_rig`, but from a path (no registry entry needed) and timed."""
    import pyglet

    from mirai.application import Application

    window = pyglet.window.Window(width=WIDTH, height=HEIGHT, visible=False)
    app = Application()
    start = time.perf_counter()
    app.init_scene("obj", obj_path=path, **src_main.GL_TYPES)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.viewport.sync()
    load_ms = (time.perf_counter() - start) * 1000.0
    timer = drag._UpdateTimer(app.viewport.render_mesh.store)
    rig = drag.Rig(window=window, app=app, update_timer=timer, asset=label)
    mesh = app.scene.mesh
    info = AssetInfo(
        label=label,
        path=path,
        vertices=len(mesh.all_vertex_ids()),
        faces=len(mesh.all_face_ids()),
        triangles=len(app.viewport.render_mesh._triangle_indices),
        load_ms=load_ms,
    )
    return NavRig(drag_rig=rig, instruments=Instruments(app), info=info)


# -- navigation scenarios ---------------------------------------------------


def cursor_on_mesh(rig: NavRig) -> tuple[float, float]:
    """Screen position 2 px right of the front-most vertex (max z, as `probe_drag_gl`): on
    the mesh, in the dense part a hover/zoom happens over."""
    mesh = rig.app.scene.mesh
    seed, _ring = drag.seed_with_ring(mesh)
    x, y = rig.app.camera.project_to_screen(mesh.vertex_position(seed), WIDTH, HEIGHT)
    return x + 2.0, y


def _keys():
    from mirai.interaction.input import Input

    return {
        "orbit": Input("mouse", "LEFT", frozenset({"alt"})),
        "pan": Input("mouse", "LEFT", frozenset({"alt", "shift"})),
        "click": Input("mouse", "LEFT", frozenset()),
        "wheel_up": Input("wheel", "UP", frozenset()),
        "wheel_down": Input("wheel", "DOWN", frozenset()),
        "wire": Input("key", "d", frozenset({"shift"})),
    }


class _Budget:
    def __init__(self, steps: int, min_steps: int, seconds: float) -> None:
        self.steps, self.min_steps, self.seconds = steps, min_steps, seconds
        self.start = time.perf_counter()

    def more(self, taken: int) -> bool:
        if taken >= self.steps:
            return False
        if taken < self.min_steps:
            return True
        return time.perf_counter() - self.start < self.seconds


def _drag_gesture(rig: NavRig, button, cfg, scenario: str) -> NavResult:
    """Orbit / pan: press, `warmup` + N drag steps (direction reverses every 20 steps so the
    view oscillates), release."""
    app = rig.app
    x, y = cursor_on_mesh(rig)
    app.pointer_motion(x, y)
    rig.settle()
    app.pointer_press(button, x, y)
    for i in range(cfg.warmup + 2):  # +2: past the 5 px click threshold
        app.pointer_drag(ORBIT_STEP_PX, 0.0, x, y)
    rig.settle()
    samples: list[NavSample] = []
    budget = _Budget(cfg.steps, cfg.min_steps, cfg.row_seconds)
    i = 0
    while budget.more(len(samples)):
        dx = ORBIT_STEP_PX if (i // 20) % 2 == 0 else -ORBIT_STEP_PX
        samples.append(rig.frame(lambda: app.pointer_drag(dx, 0.5, x, y)))
        i += 1
    app.pointer_release(button.value, x, y)
    rig.settle()
    return NavResult(scenario, rig.info.label, tuple(samples))


def scenario_orbit(rig: NavRig, cfg) -> NavResult:
    return _drag_gesture(rig, _keys()["orbit"], cfg, "orbit")


def scenario_pan(rig: NavRig, cfg) -> NavResult:
    return _drag_gesture(rig, _keys()["pan"], cfg, "pan")


def scenario_orbit_wire(rig: NavRig, cfg) -> NavResult:
    """Orbit with the wire overlay on (Shift+D): the edge segments are built once when it is
    switched on; a camera-only frame must not rebuild them (H4) - the draw cost is H5."""
    app = rig.app
    keys = _keys()
    app.key_press(keys["wire"])
    rig.settle()
    try:
        result = _drag_gesture(rig, keys["orbit"], cfg, "orbit_wire")
    finally:
        app.key_press(keys["wire"])
        rig.settle()
    return result


def scenario_zoom(rig: NavRig, cfg) -> NavResult:
    """Wheel notches with the cursor resting on the mesh, alternating in/out (H1)."""
    app = rig.app
    keys = _keys()
    x, y = cursor_on_mesh(rig)
    app.pointer_motion(x, y)
    rig.settle()
    for i in range(cfg.warmup):
        app.pointer_scroll(keys["wheel_up" if i % 2 == 0 else "wheel_down"])
    if cfg.warmup % 2:
        app.pointer_scroll(keys["wheel_down"])
    rig.settle()
    samples: list[NavSample] = []
    budget = _Budget(cfg.steps, cfg.min_steps, cfg.row_seconds)
    while budget.more(len(samples)):
        wheel = keys["wheel_up" if len(samples) % 2 == 0 else "wheel_down"]
        samples.append(rig.frame(lambda: app.pointer_scroll(wheel)))
    if len(samples) % 2:
        app.pointer_scroll(keys["wheel_down"])
    rig.settle()
    return NavResult("zoom", rig.info.label, tuple(samples))


def _orbit_once(rig: NavRig, direction: float) -> None:
    """A short orbit gesture (unmeasured): press, one step past the click threshold, release."""
    app = rig.app
    button = _keys()["orbit"]
    x, y = cursor_on_mesh(rig)
    app.pointer_press(button, x, y)
    app.pointer_drag(6.0 * direction, 0.0, x, y)
    app.pointer_release(button.value, x, y)
    rig.settle()


def scenario_first_hover(rig: NavRig, cfg) -> NavResult:
    """The first plain mouse move after a camera change (H2): an orbit gesture (unmeasured),
    then one `pointer_motion` with the cursor on the mesh (measured)."""
    app = rig.app
    x, y = cursor_on_mesh(rig)
    samples: list[NavSample] = []
    for i in range(cfg.warmup):
        _orbit_once(rig, 1.0 if i % 2 == 0 else -1.0)
        app.pointer_motion(x, y)
        rig.settle()
    budget = _Budget(cfg.steps, cfg.min_steps, cfg.row_seconds)
    while budget.more(len(samples)):
        direction = 1.0 if len(samples) % 2 == 0 else -1.0
        _orbit_once(rig, direction)
        samples.append(rig.frame(lambda: app.pointer_motion(x + direction, y, direction, 0.0)))
    return NavResult("first_hover", rig.info.label, tuple(samples))


def scenario_hover_move(rig: NavRig, cfg) -> NavResult:
    """Plain mouse moves across the mesh, camera unchanged (pick cache valid)."""
    app = rig.app
    cx, cy = cursor_on_mesh(rig)
    app.pointer_motion(cx - HOVER_SPAN_PX, cy)
    rig.settle()
    samples: list[NavSample] = []
    budget = _Budget(cfg.steps, cfg.min_steps, cfg.row_seconds)
    x, direction, i = cx - HOVER_SPAN_PX, 1.0, 0
    while budget.more(len(samples)):
        if abs(x + direction * HOVER_STEP_PX - cx) > HOVER_SPAN_PX:
            direction = -direction
        x += direction * HOVER_STEP_PX
        sample = rig.frame(lambda: app.pointer_motion(x, cy, direction * HOVER_STEP_PX, 0.0))
        if i >= cfg.warmup:
            samples.append(sample)
        i += 1
    changed = sum(1 for s in samples if s.hover_changed)
    return NavResult("hover_move", rig.info.label, tuple(samples),
                     note=f"hover changed on {changed}/{len(samples)} moves")


def scenario_select_click(rig: NavRig, cfg) -> NavResult:
    """LMB click (press + release) alternating between the front-most vertex and a neighbour."""
    app = rig.app
    mesh = app.scene.mesh
    seed, ring = drag.seed_with_ring(mesh)
    neighbour = next(v for v in sorted(ring) if v != seed)
    spots = [
        app.camera.project_to_screen(mesh.vertex_position(v), WIDTH, HEIGHT)
        for v in (seed, neighbour)
    ]
    click = _keys()["click"]

    def click_at(x: float, y: float) -> None:
        app.pointer_press(click, x, y)
        app.pointer_release(click.value, x, y)

    samples: list[NavSample] = []
    budget = _Budget(cfg.steps, cfg.min_steps, cfg.row_seconds)
    i = 0
    while budget.more(len(samples)):
        sx, sy = spots[i % 2]
        sample = rig.frame(lambda: click_at(sx, sy))
        if i >= min(cfg.warmup, 1):
            samples.append(sample)
        i += 1
    app.selection.clear()
    rig.viewport.on_selection_changed()
    rig.settle()
    return NavResult("select_click", rig.info.label, tuple(samples))


NAV_RUNNERS: dict[str, Callable[[NavRig, argparse.Namespace], NavResult]] = {
    "orbit": scenario_orbit,
    "pan": scenario_pan,
    "zoom": scenario_zoom,
    "first_hover": scenario_first_hover,
    "hover_move": scenario_hover_move,
    "select_click": scenario_select_click,
    "orbit_wire": scenario_orbit_wire,
}


# -- direct rows (Slice 1 step 0: the audit's scratch-probe rows) -----------


def _hover_line(rig: NavRig) -> list[tuple[float, float]]:
    """The hover line of `hover_move`: +-HOVER_SPAN_PX around the cursor, HOVER_STEP_PX apart."""
    cx, cy = cursor_on_mesh(rig)
    n = int(HOVER_SPAN_PX / HOVER_STEP_PX)
    return [(cx + i * HOVER_STEP_PX, cy) for i in range(-n, n + 1)]


def _direct_row(rig: NavRig, cfg, name: str, call: Callable[[int], object], *,
                min_steps: int | None = None, note: str = "") -> DirectResult:
    """`call(i)` timed once per sample (i = sample index) until the row budget is spent."""
    inst = rig.instruments
    budget = _Budget(cfg.steps, min(cfg.min_steps, cfg.steps) if min_steps is None else min_steps,
                     cfg.row_seconds)
    times: list[float] = []
    tests: list[int] = []
    while budget.more(len(times)):
        inst.reset()
        start = time.perf_counter()
        call(len(times))
        times.append((time.perf_counter() - start) * 1000.0)
        tests.append(Instruments.occl.calls)
    return DirectResult(name, rig.info.label, tuple(times), tuple(tests), note)


def run_direct(rig: NavRig, cfg) -> list[DirectResult]:
    from core import SelectionMode
    from mirai.topology.knife_pick import knife_pick
    from mirai.viewport.box_select import elements_in_rect, stroke_samples
    from mirai.viewport.picking import face_hit_position, pick_component, pick_face

    app = rig.app
    # The rows before leave the camera where their (time-budgeted) gestures ended: frame it
    # again, so the cursor line and the boxes cover the same mesh part in every run.
    app.frame_scene()
    rig.settle()
    mesh = app.scene.mesh
    cache = app._pick_cache
    occlusion = app.display.show_faces
    line = _hover_line(rig)
    cx, cy = cursor_on_mesh(rig)
    out: list[DirectResult] = []

    def camera():
        return app._edit_camera

    # Warm the cache (camera unchanged since the last frame): the hover rows read a valid cache.
    cache.refresh(camera(), mesh, WIDTH, HEIGHT)
    for label, mode in (("vertex", SelectionMode.VERTEX), ("edge", SelectionMode.EDGE),
                        ("face", SelectionMode.FACE)):
        out.append(_direct_row(rig, cfg, f"hover {label}", lambda i, mode=mode: pick_component(
            camera(), mesh, mode, *line[i % len(line)], WIDTH, HEIGHT,
            cache=cache, occlusion=occlusion)))
    out.append(_direct_row(rig, cfg, "knife hover", lambda i: knife_pick(
        camera(), mesh, *line[i % len(line)], WIDTH, HEIGHT, cache=cache, occlusion=occlusion)))

    def paint(i: int) -> None:
        direction = 1.0 if i % 2 == 0 else -1.0
        start = (cx - direction * PAINT_STEP_PX / 2.0, cy)
        end = (cx + direction * PAINT_STEP_PX / 2.0, cy)
        app._paint_at(stroke_samples(start, end))

    app.selection.clear()
    out.append(_direct_row(rig, cfg, f"paint {PAINT_STEP_PX:.0f} px step", paint, min_steps=1,
                           note=f"{len(stroke_samples((0.0, 0.0), (PAINT_STEP_PX, 0.0)))} picks"))
    app.selection.clear()
    rig.viewport.on_selection_changed()
    rig.settle()

    for label, mode in (("vertex", SelectionMode.VERTEX), ("face", SelectionMode.FACE)):
        for size in BOX_SIZES:
            rect = (cx - size / 2.0, cy - size / 2.0, cx + size / 2.0, cy + size / 2.0)
            found: list[int] = []

            def box(i: int, mode=mode, rect=rect, found=found) -> None:
                found.append(len(elements_in_rect(camera(), mesh, mode, rect, WIDTH, HEIGHT,
                                                  cache=cache, occlusion=occlusion)))

            row = _direct_row(rig, cfg, f"box {size} px {label}", box, min_steps=1)
            out.append(DirectResult(row.name, row.asset, row.samples_ms, row.occl_tests,
                                    f"{found[0]} {'vertices' if label == 'vertex' else 'faces'} selected"))

    def snap(i: int) -> None:
        x, y = line[i % len(line)]
        fid = pick_face(camera(), mesh, x, y, WIDTH, HEIGHT, cache=cache)
        if fid is not None:
            face_hit_position(camera(), mesh, fid, x, y, WIDTH, HEIGHT)

    cache.refresh(camera(), mesh, WIDTH, HEIGHT)
    out.append(_direct_row(rig, cfg, "snap, valid cache", snap))

    def snap_after_orbit(i: int) -> None:
        app.camera.orbit(SNAP_ORBIT_RAD if i % 2 == 0 else -SNAP_ORBIT_RAD, 0.0)
        snap(i)

    out.append(_direct_row(rig, cfg, "snap after an orbit", snap_after_orbit, min_steps=2,
                           note="incl. the pick-cache rebuild"))

    def rebuild(i: int) -> None:
        cache.invalidate()
        cache.refresh(camera(), mesh, WIDTH, HEIGHT)

    out.append(_direct_row(rig, cfg, "cache rebuild", rebuild, min_steps=2))
    derived = rig.viewport.render_mesh.derived
    out.append(_direct_row(rig, cfg, "recompute_bounds (all V)",
                           lambda i: derived.recompute_bounds(mesh)))
    rig.settle()
    return out


# -- loop (H3): the real wiring in a running event loop ---------------------


def scenario_loop(rig: NavRig, src_main) -> list[LoopResult]:
    """`src_main.install_handlers` on the rig window, then `pyglet.app.run(1/60)` plus the
    1/60 s `update_viewport` tick, as `src_main.run` does (copied so both can be unscheduled
    again). Injected through `window.dispatch_event`, i.e. the handlers the window calls:
    phase `orbit` = Alt+LMB drag events at `LOOP_ORBIT_HZ`, phase `hover` = plain mouse moves
    across the mesh at `LOOP_HOVER_HZ`, phase `zoom` = wheel notches at `LOOP_ZOOM_HZ` with the
    cursor on the mesh. Counts on_draw vs events and the longest time without a frame (phase
    start and end count as frame boundaries)."""
    import pyglet
    from pyglet.window import key, mouse

    window, app = rig.drag_rig.window, rig.app
    src_main.install_handlers(window, app)
    cx, cy = cursor_on_mesh(rig)
    results: list[LoopResult] = []

    for phase, hz in (("orbit", LOOP_ORBIT_HZ), ("hover", LOOP_HOVER_HZ), ("zoom", LOOP_ZOOM_HZ)):
        state = {"events": 0, "event_ms": 0.0, "draws": 0, "draw_ms": 0.0, "syncs": 0,
                 "draw_start": None, "last_draw": None, "max_gap": 0.0, "dir": 1.0,
                 "x": cx}

        def on_draw():
            now = time.perf_counter()
            state["draw_start"] = now
            if state["last_draw"] is not None:
                state["max_gap"] = max(state["max_gap"], (now - state["last_draw"]) * 1000.0)
            state["last_draw"] = now
            # returns None: the installed on_draw below still runs

        original_flip = window.flip

        def flip():
            if state["draw_start"] is not None:
                state["draws"] += 1
                state["draw_ms"] += (time.perf_counter() - state["draw_start"]) * 1000.0
                state["draw_start"] = None
            return original_flip()

        window.push_handlers(on_draw=on_draw)
        window.flip = flip

        def tick(dt):
            state["syncs"] += 1
            app.update_viewport(dt)

        def inject(dt):
            start = time.perf_counter()
            if phase == "orbit":
                if state["events"] % 40 == 0:
                    state["dir"] = -state["dir"]
                window.dispatch_event("on_mouse_drag", int(cx), int(cy),
                                      int(ORBIT_STEP_PX * state["dir"]), 0, mouse.LEFT, key.MOD_ALT)
            elif phase == "hover":
                if abs(state["x"] + state["dir"] * HOVER_STEP_PX - cx) > HOVER_SPAN_PX:
                    state["dir"] = -state["dir"]
                step = state["dir"] * HOVER_STEP_PX
                state["x"] += step
                window.dispatch_event("on_mouse_motion", int(state["x"]), int(cy), int(step), 0)
            else:
                window.dispatch_event("on_mouse_scroll", int(cx), int(cy), 0.0,
                                      1.0 if state["events"] % 2 == 0 else -1.0)
            state["event_ms"] += (time.perf_counter() - start) * 1000.0
            state["events"] += 1

        def stop(dt):
            pyglet.app.exit()

        if phase == "orbit":
            window.dispatch_event("on_mouse_press", int(cx), int(cy), mouse.LEFT, key.MOD_ALT)
            for _ in range(2):  # past the click threshold, unmeasured
                window.dispatch_event("on_mouse_drag", int(cx), int(cy), 4, 0, mouse.LEFT, key.MOD_ALT)
        elif phase == "hover":
            pass  # the first injected move is a "first hover" after the orbit phase (cache rebuild)
        else:
            window.dispatch_event("on_mouse_motion", int(cx), int(cy), 0, 0)
        pyglet.clock.schedule_interval(tick, 1 / 60.0)
        pyglet.clock.schedule_interval(inject, 1.0 / hz)
        pyglet.clock.schedule_once(stop, LOOP_SECONDS)
        start = time.perf_counter()
        state["last_draw"] = start  # a phase without any frame is one long gap
        try:
            pyglet.app.run(1 / 60.0)
        finally:
            end = time.perf_counter()
            seconds = end - start
            state["max_gap"] = max(state["max_gap"], (end - state["last_draw"]) * 1000.0)
            pyglet.clock.unschedule(tick)
            pyglet.clock.unschedule(inject)
            pyglet.clock.unschedule(pyglet.app.event_loop._redraw_windows)
            window.pop_handlers()
            window.flip = original_flip
        if phase == "orbit":
            window.dispatch_event("on_mouse_release", int(cx), int(cy), mouse.LEFT, key.MOD_ALT)
        elif phase == "zoom":
            if state["events"] % 2:
                window.dispatch_event("on_mouse_scroll", int(cx), int(cy), 0.0, -1.0)
        rig.settle()
        results.append(LoopResult(
            asset=rig.info.label,
            phase=phase,
            seconds=seconds,
            events=state["events"],
            draws=state["draws"],
            syncs=state["syncs"],
            event_ms_mean=state["event_ms"] / max(state["events"], 1),
            draw_ms_mean=state["draw_ms"] / max(state["draws"], 1),
            max_gap_ms=state["max_gap"],
        ))
    return results


# -- drag scenarios (reused from probe_drag_gl) ------------------------------


def run_drags(rig: NavRig, cfg, scenarios: list[str]) -> tuple[list[drag.ScenarioResult], list[str]]:
    results: list[drag.ScenarioResult] = []
    skipped: list[str] = []
    vertices = rig.info.vertices
    if "plain_w" in scenarios:
        for size in PLAIN_SIZES:
            if size > vertices:
                skipped.append(f"plain_w {size} V: the mesh has {vertices} V")
                continue
            results.append(drag.scenario_plain_w(rig.drag_rig, size, cfg.drag_moves, cfg.warmup))
    if "soft_w" in scenarios:
        # The once-per-row extras of `scenario_soft_w` repeat clicks and preview recomputes
        # `PREVIEW_REPS` times; on a 20k-vertex mesh a click is seconds, so fewer here
        # (the click has its own row above: `select_click`).
        reps = drag.PREVIEW_REPS
        drag.PREVIEW_REPS = 3
        try:
            for variant in SOFT_VARIANTS:
                results.append(drag.scenario_soft_w(rig.drag_rig, variant, cfg.drag_moves, cfg.warmup))
        finally:
            drag.PREVIEW_REPS = reps
    return results, skipped


# -- profile --------------------------------------------------------------------


def _short(path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        parts = Path(path).parts
        return "/".join(parts[-2:]) if len(parts) >= 2 else path


def profile_lines(profile: cProfile.Profile, top: int) -> list[str]:
    stats = pstats.Stats(profile, stream=io.StringIO())
    total = stats.total_tt * 1000.0
    # The probe's own frames (the GPU-query wait, the profiler switch) are not the app's cost.
    here = str(Path(__file__).resolve().parent)
    rows = sorted(
        (
            item for item in stats.stats.items()
            if not item[0][0].startswith(here) and "_lsprof" not in item[0][2]
        ),
        key=lambda kv: kv[1][2],
        reverse=True,
    )[:top]
    lines = [f"    total {total:9.1f} ms (incl. GPU wait); top {top} app functions by own time: "
             "own ms / cum ms / calls / function"]
    for (filename, line, func), (_cc, ncalls, tottime, cumtime, _callers) in rows:
        where = f"{_short(filename)}:{line}" if line else filename
        lines.append(
            f"    {tottime * 1000.0:9.1f} {cumtime * 1000.0:9.1f} {ncalls:9d}  {func} ({where})"
        )
    return lines


def run_profiles(rig: NavRig, top: int) -> list[tuple[str, list[str]]]:
    """cProfile around a small orbit, zoom and first-hover run (the measured parts only)."""
    out: list[tuple[str, list[str]]] = []
    cfg = argparse.Namespace(steps=20, min_steps=2, row_seconds=1e9, warmup=0)
    for name, runner, cfg_steps in (
        ("orbit (20 drag steps + frames)", scenario_orbit, 20),
        ("zoom (4 notches + frames)", scenario_zoom, 4),
        ("first_hover (4 x orbit gesture, then 1 motion + frame; gesture unprofiled)",
         scenario_first_hover, 4),
    ):
        cfg.steps = cfg.min_steps = cfg_steps
        profile = cProfile.Profile()
        original = rig.frame

        def profiled(event, _orig=original):
            profile.enable()
            try:
                return _orig(event)
            finally:
                profile.disable()

        rig.frame = profiled
        try:
            runner(rig, cfg)
        finally:
            rig.frame = original
        out.append((name, profile_lines(profile, top)))
    return out


# -- driver -----------------------------------------------------------------


def progress(text: str) -> None:
    """One line on stderr: the run takes minutes on a large mesh, stdout is the report."""
    print(f"... {text}", file=sys.stderr, flush=True)


def run_probe(args, src_main) -> tuple[list[AssetReport], tuple[str, str]]:
    reports: list[AssetReport] = []
    gl_info = ("?", "?")
    nav = [s for s in args.scenarios if s in NAV_RUNNERS]
    for index, spec in enumerate(args.assets):
        label, path = resolve_asset(spec)
        progress(f"{label}: loading {path.name}")
        rig = build_nav_rig(label, path, src_main)
        report = AssetReport(info=rig.info)
        try:
            from pyglet.gl import gl_info as info

            gl_info = (info.get_version_string(), info.get_renderer())
            for name in nav:
                progress(f"{label}: {name}")
                report.nav.append(NAV_RUNNERS[name](rig, args))
            if "direct" in args.scenarios:
                progress(f"{label}: direct")
                report.direct.extend(run_direct(rig, args))
            if "plain_w" in args.scenarios or "soft_w" in args.scenarios:
                progress(f"{label}: plain_w / soft_w")
            drags, skipped = run_drags(rig, args, args.scenarios)
            report.drags.extend(drags)
            report.skipped.extend(skipped)
            if args.profile_top and index == len(args.assets) - 1:
                progress(f"{label}: profile")
                report.profiles = run_profiles(rig, args.profile_top)
            if "loop" in args.scenarios:  # last: it installs the window handlers
                progress(f"{label}: loop")
                report.loops = scenario_loop(rig, src_main)
        finally:
            rig.drag_rig.window.close()
        reports.append(report)
    return reports, gl_info


# -- report -----------------------------------------------------------------


def _kb(nbytes: float) -> str:
    return f"{nbytes / 1024.0:7.1f}"


def _gpu_text(result: NavResult) -> str:
    values = [s.gpu for s in result.samples if not math.isnan(s.gpu)]
    return f"{drag.Stats.of(values).p50:6.2f}" if values else "   n/a"


def nav_lines(result: NavResult) -> list[str]:
    frame, event = result.stats("frame"), result.stats("event")
    rebuilds = sum(s.cache_rebuilds for s in result.samples) / len(result.samples)
    occl_n = sum(s.occl_tests for s in result.samples) / len(result.samples)
    over = sum(1 for s in result.samples if s.frame > FRAME_BUDGET_MS)
    lines = [
        f"  {result.scenario:12s} n={len(result.samples):3d}  frame p50 {frame.p50:8.2f}  p95 {frame.p95:8.2f}"
        f"  max {frame.max:8.2f}   ({over}/{len(result.samples)} over {FRAME_BUDGET_MS:.1f} ms)",
        f"    event {event.p50:8.2f} (p95 {event.p95:8.2f})  pick {result.p50('pick'):8.2f}"
        f"  [cache {result.p50('cache'):7.2f}, {rebuilds:.1f} rebuilds/event;"
        f" occl {result.p50('occl'):8.2f}, {occl_n:.1f} tests/event]",
        f"    sync  {result.p50('sync'):8.2f}   draw {result.p50('draw'):6.2f}  gpu {_gpu_text(result)}"
        f"   upload {_kb(result.p50('upload_bytes'))} KB/frame",
    ]
    if result.note:
        lines.append(f"    {result.note}")
    return lines


def drag_lines(r: drag.ScenarioResult) -> list[str]:
    move, update, draw = r.stats("move"), r.stats("update"), r.stats("draw")
    if r.scenario == "soft_w":
        head = f"  soft_w {r.label}: seeds {r.selected} V, moving {r.influenced} V"
    else:
        head = f"  plain_w {r.selected} V"
    verdict = "OK" if move.p95 <= drag.THRESHOLD_P95_MS else "OVER"
    lines = [
        f"{head}  ({r.updates_per_move.p50:.0f} store.update calls/move) {verdict}",
        f"    move p50 {move.p50:8.2f}  p95 {move.p95:8.2f}  [transform {r.stats('transform').p50:7.2f}"
        f"  sync {r.stats('sync').p50:7.2f} (update {update.p50:7.2f})]  (draw {draw.p50:6.2f})",
    ]
    for name, stats in r.extras:
        lines.append(f"    once: {name:38s} p50 {stats.p50:9.2f}")
    return lines


def direct_lines(r: DirectResult) -> list[str]:
    stats = r.stats
    tests = sum(r.occl_tests) / len(r.occl_tests)
    note = f"  ({r.note})" if r.note else ""
    return [
        f"  direct {r.name:26s} n={len(r.samples_ms):3d}  p50 {stats.p50:9.2f}  p95 {stats.p95:9.2f}"
        f"  max {stats.max:9.2f}  [{tests:.1f} occl tests/call]{note}",
    ]


def loop_lines(r: LoopResult) -> list[str]:
    return [
        f"  loop {r.phase:5s} {r.seconds:4.1f} s: {r.events:4d} events ({r.events / r.seconds:5.1f}/s, "
        f"{r.event_ms_mean:8.2f} ms each), {r.draws:3d} on_draw ({r.draws / r.seconds:5.1f}/s, "
        f"{r.draw_ms_mean:6.2f} ms each), longest time without a frame {r.max_gap_ms:8.1f} ms",
    ]


def report_lines(reports: list[AssetReport], gl_info: tuple[str, str], args) -> list[str]:
    lines = [
        "Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame",
    ]
    lines.extend(drag.machine_info(*gl_info))
    lines.append(
        f"Run: hidden {WIDTH}x{HEIGHT} window; up to {args.steps} events per row "
        f"(at least {args.min_steps}, budget {args.row_seconds:g} s); frame = event + sync + draw; "
        f"one frame at 60 Hz = {FRAME_BUDGET_MS:.1f} ms"
    )
    for report in reports:
        info = report.info
        lines.append("")
        lines.append(
            f"[{info.label}] {info.vertices} V / {info.faces} F / {info.triangles} triangles; "
            f"load + first frame {info.load_ms:.0f} ms"
        )
        for result in report.nav:
            lines.extend(nav_lines(result))
        for result in report.direct:
            lines.extend(direct_lines(result))
        for result in report.drags:
            lines.extend(drag_lines(result))
        for note in report.skipped:
            lines.append(f"  skipped: {note}")
        for result in report.loops:
            lines.extend(loop_lines(result))
        for name, plines in report.profiles:
            lines.append(f"  profile {name}:")
            lines.extend(plines)
    return lines


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list:
        from loaders.assets import asset_names

        print("scenarios: " + ", ".join(SCENARIO_NAMES))
        print("assets: " + ", ".join(asset_names()) + f" (or any .obj path, e.g. {GOLLUM_20K}, {GOLLUM})")
        return 0

    import importlib

    # pyglet (via src/main.py) only here: --help, --list and argument errors need no window.
    src_main = importlib.import_module("main")
    if Path(src_main.__file__).resolve() != REPO_ROOT / "src" / "main.py":
        raise ImportError(f"'main' is not src/main.py but {src_main.__file__}")
    # `src_main.run` and status lines print to stdout; keep the report clean.
    with contextlib.redirect_stdout(io.StringIO()):
        reports, gl_info = run_probe(args, src_main)
    for line in report_lines(reports, gl_info, args):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
