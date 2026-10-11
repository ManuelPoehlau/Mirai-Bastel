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

Scenarios are one function each (`SCENARIOS`); S2b adds a soft drag as another entry.
`plain_w`: the selection is the region of N vertices grown from the front-most vertex,
then W + `--moves` mouse moves, W release. The default sizes are the influenced-vertex
counts of FINDINGS.md §2.2 (head 9 / 36 / 68, body 18 / 76 / 112).

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
                        help="selection sizes in vertices (default: FINDINGS 2.2 sizes per asset)")
    parser.add_argument("--moves", type=_positive_int, default=DEFAULT_MOVES,
                        help=f"measured mouse moves per row (default: {DEFAULT_MOVES})")
    parser.add_argument("--warmup", type=_non_negative_int, default=DEFAULT_WARMUP,
                        help=f"unmeasured moves before each row (default: {DEFAULT_WARMUP})")
    parser.add_argument("--scenarios", nargs="+", default=["plain_w"],
                        help="scenario names (see --list; default: plain_w)")
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
    return args


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


#: One function per scenario (S2b adds the soft drag here).
SCENARIOS: dict[str, Callable[[Rig, int, int, int], ScenarioResult]] = {
    "plain_w": scenario_plain_w,
}


def run_probe(
    assets: list[str],
    sizes: list[int] | None,
    moves: int,
    warmup: int,
    scenarios: list[str],
    src_main,
) -> tuple[list[ScenarioResult], tuple[str, str]]:
    results: list[ScenarioResult] = []
    gl_info = ("?", "?")
    for asset in assets:
        rig = build_rig(asset, src_main)
        try:
            from pyglet.gl import gl_info as info

            gl_info = (info.get_version_string(), info.get_renderer())
            for name in scenarios:
                for size in sizes_for(asset, sizes):
                    results.append(SCENARIOS[name](rig, size, moves, warmup))
        finally:
            rig.window.close()
    return results, gl_info


# -- report -----------------------------------------------------------------


def report_lines(results: list[ScenarioResult], gl_info: tuple[str, str], moves: int) -> list[str]:
    lines = ["Drag cost with the GL backend (WP-VIEW-PATCH-01), ms per mouse move"]
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
        lines.append(f"  selection {r.selected:4d} V  ({r.updates_per_move.p50:.0f} store.update calls/move) {verdict}")
        lines.append(f"    move       {r.stats('move').text()}")
        lines.append(f"    transform  {r.stats('transform').text()}")
        lines.append(f"    sync       {r.stats('sync').text()}")
        lines.append(f"      update   {r.stats('update').text()}")
        lines.append(f"      rest     {r.stats('sync_rest').text()}")
        lines.append(f"    (draw      {r.stats('draw').text()}  not in 'move')")
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
        args.assets, args.sizes, args.moves, args.warmup, args.scenarios, src_main
    )
    for line in report_lines(results, gl_info, args.moves):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
