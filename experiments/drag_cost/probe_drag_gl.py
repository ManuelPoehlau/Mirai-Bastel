"""Drag-cost probe with the real GL backend (WP-VIEW-PATCH-01).

Usage (from the repo root, Windows and Linux alike; opens a hidden pyglet window):
    python experiments/drag_cost/probe_drag_gl.py
    python experiments/drag_cost/probe_drag_gl.py --moves 400
    python experiments/drag_cost/probe_drag_gl.py --assets head_basemesh --sizes 9 36
    python experiments/drag_cost/probe_drag_gl.py --list

Headless container: prefix with `xvfb-run -a`.

Measures what one mouse move of a held-W drag costs in the window's own chain: the
`GL_TYPES` backends of `src/main.py` (`GLRenderStore` + GL overlays) behind
`Application` -> `Viewport`, no `TraceStore` (a TraceStore proxy misses the buffer
copies, AD-020 review F1). Per move, separately:

- transform   `app.pointer_motion(...)`: the Move step (Core operation + dirty marks)
- sync        `Viewport.sync()` in total, one call as in `on_draw`
- update      the part of that sync spent inside `GLRenderStore.update` (summed over
              the move's calls; `updates` = how many calls)
- sync rest   sync - update (derived data, bounds, overlays, ...)
- draw        `Viewport.render()` + `glFinish()` (hidden window; on a software
              rasteriser this is not the reference PC's GPU time)
- move        transform + sync (the number the 8 ms bar of AD-020 §7 is about)

Scenarios are one entry each in `SCENARIOS` (a runner plus the variants it measures per asset).
`plain_w`: the selection is the region of N vertices grown from the front-most vertex,
then W + `--moves` mouse moves, W release. The default sizes are the influenced-vertex
counts of FINDINGS.md §2.2 (head 9 / 36 / 68, body 18 / 76 / 112).
`soft_w` (WP-SOFT-01 S2b): Soft Selection on, the window's band overlay attached (it is part of
`GL_TYPES`), seed = the front-most vertex + its one-ring, radius 5 / 15 / 30 / 50 % x both metrics
(`--sizes` = radius percents, `--metrics` = a subset), then the same W drag. Besides the
per-move rows it prints, once per row: the first move (`begin()` incl. influence + the first band
push), the commit frame (`key_release` + `sync`, which recomputes the preview), the preview
recompute itself (`compute_influence` + bands for the seed, standalone), a settings change
end to end (Shift+O key + `sync`) and a selection click (pick + preview, one vertex).
`soft_w_sym` (AD-SYM-04 SS3, D-4): the same rows under symmetry X (Shift+S, one Undo step, undone
after the row), seed = the front-most *paired* vertex on +X + its paired +X one-ring (off the
plane, so a radius step can cross it; the label counts the seam vertices the falloff reaches).
The preview is the symmetric field; its standalone row reuses the pairing as the app does for a
selection or settings trigger, and a separate row times the symmetry report a geometry change
(commit, Undo, Shift+S) adds once, shared with the symmetry display.

Numbers from a container must be labelled as such
(`docs/architecture/REFERENCE_HARDWARE.md` §4); the reference PC decides. Output is
plain ASCII so it pastes cleanly from a Windows console.
"""

from __future__ import annotations

import argparse
import math
import os
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Stage 0 (script start): experiments/ on sys.path, as in soft_selection/probe_cost.py.
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import ensure_paths  # noqa: E402

ensure_paths()

DEFAULT_ASSETS = ("head_basemesh", "man_with_shoes_basemesh")
#: FINDINGS.md §2.2 influenced-vertex counts (5 / 15 / 30 % radius, euclidean).
DEFAULT_SIZES = {
    "head_basemesh": (9, 36, 68),
    "man_with_shoes_basemesh": (18, 76, 112),
}
FALLBACK_SIZES = (9, 36, 112)
#: `soft_w`: radius steps in percent of the bounding radius (all are `RADIUS_STEPS_PERCENT` steps).
SOFT_RADIUS_PERCENTS = (5, 15, 30, 50)
#: Repetitions of the once-per-row preview timings.
PREVIEW_REPS = 15
DEFAULT_MOVES = 200
DEFAULT_WARMUP = 5
WIDTH, HEIGHT = 1024, 768  # the real window (src/main.py `create_window`)
#: Pixels per move; the direction reverses after half the moves so the region
#: stays in the picture.
STEP = (3.0, 1.0)
THRESHOLD_P95_MS = 8.0  # AD-020 §7 bar for a whole move


@dataclass(frozen=True)
class Stats:
    p50: float
    p95: float
    max: float

    @classmethod
    def of(cls, samples_ms: list[float]) -> "Stats":
        ordered = sorted(samples_ms)
        p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)  # nearest rank
        return cls(statistics.median(ordered), ordered[p95_index], ordered[-1])

    def text(self) -> str:
        return f"p50 {self.p50:7.2f}  p95 {self.p95:7.2f}  max {self.max:7.2f}"


@dataclass(frozen=True)
class MoveSample:
    """Milliseconds of one mouse move, plus the number of `store.update` calls."""

    transform: float
    sync: float
    update: float
    draw: float
    updates: int

    @property
    def sync_rest(self) -> float:
        return self.sync - self.update

    @property
    def move(self) -> float:
        return self.transform + self.sync


@dataclass(frozen=True)
class ScenarioResult:
    scenario: str
    asset: str
    vertex_count: int
    selected: int
    moves: int
    samples: tuple[MoveSample, ...]
    #: Short row label (e.g. `r 15 % euclidean`); empty for `plain_w`.
    label: str = ""
    #: Vertices that move (seeds + influenced); 0 = same as `selected`.
    influenced: int = 0
    #: Once-per-row timings in ms, in print order (`soft_w`: first move, commit frame, preview ...).
    extras: tuple[tuple[str, Stats], ...] = ()

    def stats(self, field: str) -> Stats:
        return Stats.of([getattr(s, field) for s in self.samples])

    @property
    def updates_per_move(self) -> Stats:
        return Stats.of([float(s.updates) for s in self.samples])


# -- argument handling (headless: no pyglet, no window) ---------------------


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {value}")
    return value


def _non_negative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {value}")
    return value


def known_assets() -> tuple[str, ...]:
    from loaders.assets import asset_names

    return tuple(asset_names())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Drag cost of the real GL chain (WP-VIEW-PATCH-01)"
    )
    parser.add_argument("--assets", nargs="+", default=list(DEFAULT_ASSETS),
                        help="registry names (default: head_basemesh man_with_shoes_basemesh)")
    parser.add_argument("--sizes", nargs="+", type=_positive_int, default=None,
                        help="plain_w: selection sizes in vertices (default: FINDINGS 2.2 sizes "
                             "per asset); soft_w: radius percents "
                             f"(default: {' '.join(map(str, SOFT_RADIUS_PERCENTS))})")
    parser.add_argument("--metrics", nargs="+", default=None,
                        help="soft_w: influence metrics (default: all)")
    parser.add_argument("--moves", type=_positive_int, default=DEFAULT_MOVES,
                        help=f"measured mouse moves per row (default: {DEFAULT_MOVES})")
    parser.add_argument("--warmup", type=_non_negative_int, default=DEFAULT_WARMUP,
                        help=f"unmeasured moves before each row (default: {DEFAULT_WARMUP})")
    parser.add_argument("--scenarios", nargs="+", default=["plain_w", "soft_w"],
                        help="scenario names (see --list; default: plain_w soft_w; "
                             "soft_w_sym = soft_w under symmetry X)")
    parser.add_argument("--list", action="store_true",
                        help="print scenario and asset names and exit")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parses and validates `argv`; invalid input exits with status 2 (argparse)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list:
        return args
    assets = known_assets()
    unknown = [a for a in args.assets if a not in assets]
    if unknown:
        parser.error(f"unknown asset {unknown[0]!r}; known: {', '.join(assets)}")
    bad = [s for s in args.scenarios if s not in SCENARIOS]
    if bad:
        parser.error(f"unknown scenario {bad[0]!r}; known: {', '.join(SCENARIOS)}")
    if any(s in SOFT_SCENARIOS for s in args.scenarios):
        steps, metrics = soft_choices()
        if args.sizes:
            bad_sizes = [p for p in args.sizes if p not in steps]
            if bad_sizes:
                parser.error(
                    f"soft_w: {bad_sizes[0]} is not a radius step in percent; known: "
                    + ", ".join(map(str, steps))
                )
        bad_metrics = [m for m in args.metrics or () if m not in metrics]
        if bad_metrics:
            parser.error(f"unknown metric {bad_metrics[0]!r}; known: {', '.join(metrics)}")
    elif args.metrics:
        parser.error("--metrics only applies to the soft_w scenarios")
    return args


def soft_choices() -> tuple[tuple[int, ...], tuple[str, ...]]:
    """The radius steps (percent) and metrics Soft Selection offers (from `src/`)."""
    from mirai.soft_selection import METRICS, RADIUS_STEPS_PERCENT

    return tuple(RADIUS_STEPS_PERCENT), tuple(METRICS)


def sizes_for(asset: str, requested: list[int] | None) -> tuple[int, ...]:
    return tuple(requested) if requested else DEFAULT_SIZES.get(asset, FALLBACK_SIZES)


# -- environment ------------------------------------------------------------


def cpu_name() -> str:
    """CPU model: Windows from the registry, Linux from /proc/cpuinfo."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            ) as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def machine_info(gl_version: str, gl_renderer: str) -> list[str]:
    return [
        f"Platform: {platform.platform()}",
        f"CPU: {cpu_name()} ({os.cpu_count()} logical cores)",
        f"Python: {platform.python_version()} ({platform.python_implementation()})",
        f"GL_VERSION: {gl_version}",
        f"GL_RENDERER: {gl_renderer}",
    ]


# -- measurement ------------------------------------------------------------


class _UpdateTimer:
    """Times `GLRenderStore.update` calls (instance-level wrapper)."""

    def __init__(self, store) -> None:
        self.elapsed = 0.0
        self.calls = 0
        original = store.update

        def timed(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                self.elapsed += time.perf_counter() - start
                self.calls += 1

        store.update = timed

    def reset(self) -> None:
        self.elapsed = 0.0
        self.calls = 0


@dataclass
class Rig:
    """The window-less part of `src/main.py` `main()`: `Application` + the `GL_TYPES`
    backends in a hidden window, plus the instrumentation the scenarios share."""

    window: object
    app: object
    update_timer: _UpdateTimer
    asset: str

    @property
    def viewport(self):
        return self.app.viewport

    def timed_frame(self, x: float, y: float, dx: float, dy: float) -> MoveSample:
        """One mouse move as the window sees it: motion event, then `on_draw`'s
        `sync()` and `render()`."""
        from pyglet import gl

        self.update_timer.reset()
        start = time.perf_counter()
        self.app.pointer_motion(x, y, dx, dy)
        after_step = time.perf_counter()
        self.viewport.sync()
        after_sync = time.perf_counter()
        self.viewport.render()
        gl.glFinish()
        end = time.perf_counter()
        return MoveSample(
            transform=(after_step - start) * 1000.0,
            sync=(after_sync - after_step) * 1000.0,
            update=self.update_timer.elapsed * 1000.0,
            draw=(end - after_sync) * 1000.0,
            updates=self.update_timer.calls,
        )


def build_rig(asset: str, src_main) -> Rig:
    """Hidden window first (GLRenderStore needs a GL context for its first
    `allocate()`), then the scene exactly as `src/main.py` does it."""
    import pyglet

    from loaders.assets import asset_path
    from mirai.application import Application

    window = pyglet.window.Window(width=WIDTH, height=HEIGHT, visible=False)
    app = Application()
    app.init_scene("obj", obj_path=asset_path(asset), **src_main.GL_TYPES)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    store = app.viewport.render_mesh.store
    timer = _UpdateTimer(store)
    rig = Rig(window=window, app=app, update_timer=timer, asset=asset)
    rig.viewport.sync()  # first frame builds the buffers; not part of any row
    return rig


def grow_region(mesh, count: int):
    """`count` vertices: the front-most vertex (max z) plus a breadth-first region
    over the mesh edges - a contiguous patch like an Artist's area selection."""
    ids = mesh.all_vertex_ids()
    if count > len(ids):
        raise ValueError(f"asked for {count} vertices, the mesh has {len(ids)}")
    seed = max(ids, key=lambda v: (mesh.vertex_position(v)[2], int(v)))
    region, queue = [seed], [seed]
    seen = {seed}
    while queue and len(region) < count:
        vid = queue.pop(0)
        for edge in mesh.vertex_edges(vid):
            for other in mesh.edge_vertices(edge):
                if other not in seen and len(region) < count:
                    seen.add(other)
                    region.append(other)
                    queue.append(other)
    return region


def select_region(rig: Rig, count: int) -> int:
    """Selects the region directly through the Selection (not by clicks: 112 picks
    would measure the picker). Returns the selection size."""
    app = rig.app
    region = grow_region(app.scene.mesh, count)
    app.selection.set(set(region))
    rig.viewport.on_selection_changed()
    rig.viewport.sync()
    return len(app.selection.vertices)


def _keys():
    from mirai.interaction.input import Input

    return Input("key", "w"), Input("key", "z", frozenset({"ctrl"}))


def scenario_plain_w(rig: Rig, selection_size: int, moves: int, warmup: int) -> ScenarioResult:
    """Plain (non-soft) W drag of a `selection_size`-vertex region."""
    app = rig.app
    selected = select_region(rig, selection_size)
    w, ctrl_z = _keys()
    if not app.key_press(w) or app.transform_command is None:
        raise RuntimeError(f"{rig.asset}: W did not arm ({app.status_message})")
    x, y = WIDTH / 2.0, HEIGHT / 2.0
    total = warmup + moves
    samples: list[MoveSample] = []
    for i in range(total):
        dx, dy = STEP if i < (total + 1) // 2 else (-STEP[0], -STEP[1])
        x, y = x + dx, y + dy
        sample = rig.timed_frame(x, y, dx, dy)
        if i >= warmup:
            samples.append(sample)
    app.key_release(w)
    # Undo the committed drag so every row starts from the unmodified asset.
    app.key_press(ctrl_z)
    rig.viewport.sync()
    app.selection.clear()
    rig.viewport.on_selection_changed()
    rig.viewport.sync()
    return ScenarioResult(
        scenario="plain_w",
        asset=rig.asset,
        vertex_count=len(app.scene.mesh.all_vertex_ids()),
        selected=selected,
        moves=moves,
        samples=tuple(samples),
    )


# -- soft_w (WP-SOFT-01 S2b) -------------------------------------------------


def seed_with_ring(mesh):
    """The front-most vertex (max z, as `grow_region`) and its one-ring neighbours."""
    ids = mesh.all_vertex_ids()
    seed = max(ids, key=lambda v: (mesh.vertex_position(v)[2], int(v)))
    ring = {other for edge in mesh.vertex_edges(seed) for other in mesh.edge_vertices(edge)}
    return seed, ring | {seed}


def _time_ms(fn) -> float:
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000.0


def configure_soft(app, radius_percent: int, metric: str) -> None:
    """Soft on, `radius_percent`, `metric`, curve smooth - only through the public entry
    points the window uses (O, Shift+wheel, Ctrl+O, Shift+O)."""
    from mirai.interaction.input import Input

    o, ctrl_o, shift_o = (
        Input("key", "o"),
        Input("key", "o", frozenset({"ctrl"})),
        Input("key", "o", frozenset({"shift"})),
    )
    wheel_up = Input("wheel", "UP", frozenset({"shift"}))
    wheel_down = Input("wheel", "DOWN", frozenset({"shift"}))
    if not app.soft_settings.enabled:
        app.key_press(o)
    for _ in range(16):  # more than the steps: terminates at the wanted one
        current = app.soft_settings.radius_percent
        if current == radius_percent:
            break
        app.pointer_scroll(wheel_up if current < radius_percent else wheel_down)
    for _ in range(4):
        if app.soft_settings.metric == metric:
            break
        app.key_press(ctrl_o)
    for _ in range(4):
        if app.soft_settings.curve == "smooth":
            break
        app.key_press(shift_o)
    soft = app.soft_settings
    if (soft.radius_percent, soft.metric, soft.curve) != (radius_percent, metric, "smooth"):
        raise RuntimeError(f"could not configure soft selection: {soft.status_text()}")


def seed_off_plane_with_ring(mesh):
    """`soft_w_sym`: a paired +X vertex next to the front-most seam vertex (off the plane but
    close to it, so the radius steps cross the middle) and its paired +X one-ring - the side
    the app's K-side rule calls plain. Without a seam: the front-most paired +X vertex."""
    from mirai.symmetry import CorrespondenceState, vertex_correspondence

    corr = vertex_correspondence(mesh)

    def front(vid):
        return (mesh.vertex_position(vid)[2], int(vid))

    def eligible(vid) -> bool:
        return corr[vid].state is CorrespondenceState.PAIRED and mesh.vertex_position(vid)[0] > 0.0

    def ring(vid):
        return {o for edge in mesh.vertex_edges(vid) for o in mesh.edge_vertices(edge) if eligible(o)}

    seam = [v for v, c in corr.items() if c.state is CorrespondenceState.SEAM]
    near = ring(max(seam, key=front)) if seam else set()
    candidates = near or {v for v in mesh.all_vertex_ids() if eligible(v)}
    if not candidates:
        raise RuntimeError("soft_w_sym: no paired vertex on +X")
    seed = max(candidates, key=front)
    return seed, ring(seed) | {seed}


def scenario_soft_w(rig: Rig, variant: tuple[int, str], moves: int, warmup: int) -> ScenarioResult:
    """Soft W drag: seed = front-most vertex + one-ring, `variant` = (radius percent, metric)."""
    return _soft_row(rig, variant, moves, warmup, symmetric=False)


def scenario_soft_w_sym(rig: Rig, variant: tuple[int, str], moves: int, warmup: int) -> ScenarioResult:
    """`soft_w` under symmetry X (AD-SYM-04 D-4): seeds off the plane (`seed_off_plane_with_ring`)."""
    return _soft_row(rig, variant, moves, warmup, symmetric=True)


def _soft_row(rig: Rig, variant: tuple[int, str], moves: int, warmup: int, symmetric: bool) -> ScenarioResult:
    from pyglet import gl

    from mirai.interaction import commands
    from mirai.interaction.input import Input
    from mirai.soft_selection import SoftBands, compute_influence, symmetric_influence
    from mirai.symmetry import CorrespondenceState
    from mirai.symmetry_axis import current_axis
    from mirai.symmetry_display import symmetry_report

    radius_percent, metric = variant
    app = rig.app
    mesh = app.scene.mesh
    w, ctrl_z = _keys()
    shift_o = Input("key", "o", frozenset({"shift"}))
    extras: list[tuple[str, Stats]] = []

    if symmetric:
        # Shift+S: off -> X, one Undo step (undone at the end of the row).
        app.key_press(Input("key", "s", frozenset({"shift"})))
        rig.viewport.sync()
        if current_axis(mesh) != "X":
            raise RuntimeError(f"{rig.asset}: Shift+S did not set symmetry X ({app.status_message})")
    configure_soft(app, radius_percent, metric)
    seed, seeds = seed_off_plane_with_ring(mesh) if symmetric else seed_with_ring(mesh)

    # Selection click (pick + preview of one vertex), only if the click lands on the seed.
    sx, sy = app.camera.project_to_screen(mesh.vertex_position(seed), WIDTH, HEIGHT)
    app.select_at(commands.SELECT, 1.0, 1.0)  # empty space: clears
    rig.viewport.sync()
    click_samples = []
    for _ in range(PREVIEW_REPS):
        click_ms = _time_ms(lambda: app.select_at(commands.SELECT, sx, sy))
        if app.selection.vertices == {seed}:
            click_samples.append(click_ms)
        rig.viewport.sync()
        app.select_at(commands.SELECT, 1.0, 1.0)
        rig.viewport.sync()
    if click_samples:
        extras.append(("selection click (pick + preview)", Stats.of(click_samples)))

    # The measured selection: seed + ring, set directly (as plain_w does).
    app.selection.set(set(seeds))
    rig.viewport.on_selection_changed()
    soft = app.soft_settings
    label = f"r {radius_percent:2d} % {metric}"

    if symmetric:
        report = symmetry_report(mesh)
        corr = report.correspondence

        def field():
            return symmetric_influence(
                mesh, seeds, soft.world_radius, metric=soft.metric, curve=soft.curve,
                correspondence=corr,
            )

        # Preview recompute as the app does it for a selection or settings trigger: the
        # pairing comes from the shared report of the unchanged geometry.
        preview_samples = [_time_ms(lambda: SoftBands.from_weights(field().weights))
                           for _ in range(PREVIEW_REPS)]
        extras.append(("preview recompute (sym field + bands)", Stats.of(preview_samples)))
        # What a geometry change (commit, Undo, Shift+S) adds once, shared with the display.
        report_samples = [_time_ms(lambda: symmetry_report(mesh)) for _ in range(PREVIEW_REPS)]
        extras.append(("symmetry report (per geometry change)", Stats.of(report_samples)))
        weights = field().weights
        seam = sum(1 for v in weights if corr[v].state is CorrespondenceState.SEAM)
        label += f" X, seam {seam:2d} V"
    else:
        # Preview recompute alone, the work `Application` does per triggering event.
        def preview():
            SoftBands.from_weights(
                compute_influence(mesh, seeds, soft.world_radius, metric=soft.metric, curve=soft.curve)
            )

        preview_samples = [_time_ms(preview) for _ in range(PREVIEW_REPS)]
        extras.append(("preview recompute (influence + bands)", Stats.of(preview_samples)))

    # Settings change end to end: Shift+O (curve) twice per rep, back at smooth; the second
    # press also leaves the preview computed for the measured selection.
    settings_samples = []
    for _ in range(PREVIEW_REPS):
        for _press in range(2):
            settings_samples.append(
                _time_ms(lambda: (app.key_press(shift_o), rig.viewport.sync()))
            )
    extras.append(("settings change (key + sync)", Stats.of(settings_samples)))
    if symmetric:
        influenced_preview = len(weights)  # seeds, partners and both sides' falloff
    else:
        influenced_preview = app.soft_bands.count + len(seeds)

    if not app.key_press(w) or app.transform_command is None:
        raise RuntimeError(f"{rig.asset}: W did not arm ({app.status_message})")
    x, y = WIDTH / 2.0, HEIGHT / 2.0
    total = warmup + moves
    samples: list[MoveSample] = []
    first_move = 0.0
    for i in range(total):
        dx, dy = STEP if i < (total + 1) // 2 else (-STEP[0], -STEP[1])
        x, y = x + dx, y + dy
        sample = rig.timed_frame(x, y, dx, dy)
        if i == 0:
            first_move = sample.move  # begin() incl. influence + the first band push
            if not app.transform_interacting:
                raise RuntimeError(f"{rig.asset}: the drag did not begin ({app.status_message})")
        if i >= warmup:
            samples.append(sample)

    def commit():
        app.key_release(w)
        rig.viewport.sync()
        rig.viewport.render()
        gl.glFinish()

    commit_ms = _time_ms(commit)
    extras.insert(0, ("commit frame (release + sync + draw)", Stats.of([commit_ms])))
    extras.insert(0, ("first move (begin + influence)", Stats.of([first_move])))

    app.key_press(ctrl_z)
    rig.viewport.sync()
    app.selection.clear()
    rig.viewport.on_selection_changed()
    app.key_press(Input("key", "o"))  # soft off again: the next row starts from today's state
    rig.viewport.sync()
    if symmetric:
        app.key_press(ctrl_z)  # the Shift+S step: symmetry off again
        rig.viewport.sync()
        if mesh.symmetry_definition is not None:
            raise RuntimeError(f"{rig.asset}: symmetry still on after the row")
    return ScenarioResult(
        scenario="soft_w_sym" if symmetric else "soft_w",
        asset=rig.asset,
        vertex_count=len(mesh.all_vertex_ids()),
        selected=len(seeds),
        moves=moves,
        samples=tuple(samples),
        label=label,
        influenced=influenced_preview,
        extras=tuple(extras),
    )


@dataclass(frozen=True)
class Scenario:
    """A runner plus the variants it measures per asset (`plain_w`: selection sizes,
    `soft_w`: (radius percent, metric))."""

    run: Callable[[Rig, object, int, int], ScenarioResult]
    variants: Callable[[str, list[int] | None, list[str] | None], list]


def _soft_variants(asset: str, sizes: list[int] | None, metrics: list[str] | None) -> list:
    percents = tuple(sizes) if sizes else SOFT_RADIUS_PERCENTS
    names = tuple(metrics) if metrics else soft_choices()[1]
    return [(percent, metric) for metric in names for percent in percents]


SCENARIOS: dict[str, Scenario] = {
    "plain_w": Scenario(scenario_plain_w, lambda asset, sizes, metrics: list(sizes_for(asset, sizes))),
    "soft_w": Scenario(scenario_soft_w, _soft_variants),
    "soft_w_sym": Scenario(scenario_soft_w_sym, _soft_variants),
}
#: Scenarios whose variants are (radius percent, metric).
SOFT_SCENARIOS = ("soft_w", "soft_w_sym")


def run_probe(
    assets: list[str],
    sizes: list[int] | None,
    moves: int,
    warmup: int,
    scenarios: list[str],
    src_main,
    metrics: list[str] | None = None,
) -> tuple[list[ScenarioResult], tuple[str, str]]:
    results: list[ScenarioResult] = []
    gl_info = ("?", "?")
    for asset in assets:
        rig = build_rig(asset, src_main)
        try:
            from pyglet.gl import gl_info as info

            gl_info = (info.get_version_string(), info.get_renderer())
            for name in scenarios:
                scenario = SCENARIOS[name]
                for variant in scenario.variants(asset, sizes, metrics):
                    results.append(scenario.run(rig, variant, moves, warmup))
        finally:
            rig.window.close()
    return results, gl_info


# -- report -----------------------------------------------------------------


def report_lines(results: list[ScenarioResult], gl_info: tuple[str, str], moves: int) -> list[str]:
    lines = ["Drag cost with the GL backend (WP-VIEW-PATCH-01, soft rows WP-SOFT-01 S2b), ms per mouse move"]
    lines.extend(machine_info(*gl_info))
    lines.append(
        f"Run: {moves} measured moves per row, hidden {WIDTH}x{HEIGHT} window; "
        f"bar for 'move' (transform + sync): p95 <= {THRESHOLD_P95_MS:.0f} ms"
    )
    current = None
    for r in results:
        if (r.scenario, r.asset) != current:
            current = (r.scenario, r.asset)
            lines.append("")
            lines.append(f"[{r.scenario}] {r.asset}: {r.vertex_count} vertices")
        verdict = "OK" if r.stats("move").p95 <= THRESHOLD_P95_MS else "OVER"
        if r.scenario in SOFT_SCENARIOS:
            lines.append(
                f"  {r.label}: seeds {r.selected:3d} V, moving {r.influenced:4d} V  "
                f"({r.updates_per_move.p50:.0f} store.update calls/move) {verdict}"
            )
        else:
            lines.append(f"  selection {r.selected:4d} V  ({r.updates_per_move.p50:.0f} store.update calls/move) {verdict}")
        lines.append(f"    move       {r.stats('move').text()}")
        lines.append(f"    transform  {r.stats('transform').text()}")
        lines.append(f"    sync       {r.stats('sync').text()}")
        lines.append(f"      update   {r.stats('update').text()}")
        lines.append(f"      rest     {r.stats('sync_rest').text()}")
        lines.append(f"    (draw      {r.stats('draw').text()}  not in 'move')")
        for name, stats in r.extras:
            lines.append(f"    once: {name:38s} {stats.text()}")
    return lines


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list:
        print("scenarios: " + ", ".join(SCENARIOS))
        print("assets: " + ", ".join(known_assets()))
        return 0

    import importlib

    # pyglet (via src/main.py) only here: --help, --list and argument errors need
    # no window system.
    src_main = importlib.import_module("main")
    if Path(src_main.__file__).resolve() != (Path(__file__).resolve().parents[2] / "src" / "main.py"):
        raise ImportError(f"'main' is not src/main.py but {src_main.__file__}")
    results, gl_info = run_probe(
        args.assets, args.sizes, args.moves, args.warmup, args.scenarios, src_main, args.metrics
    )
    for line in report_lines(results, gl_info, args.moves):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
