"""Subdivision Mini-Lab bench (handoff §6): what does a level cost?

Usage (from the repo root):
    xvfb-run -a python experiments/subdivision_lab/bench.py --host "sandbox-llvmpipe"
    python experiments/subdivision_lab/bench.py --host "Manu-PC" --visible     # Windows, real GPU

The same measurements run in the window with F9 (`LabWindow.run_bench`).
Prints a Markdown report; every table states the host label and whether it
ran headless/hidden or in a visible window. **Headless numbers never replace
a measurement on the reference PC** (`docs/architecture/REFERENCE_HARDWARE.md`
§4): software GL (llvmpipe) and a different CPU say nothing about the
Q9550 / GeForce 9800 GTX. Nothing here is optimized — slowness is a result.

Measurement IDs (handoff §6), min / median / max in milliseconds:

    M1  subd topology + stencil build (fresh: control topology read + levels 1..L)
    M2  derived `core.Mesh` build + first `RenderMesh` allocation
    M3  `apply_full` (all derived positions)
    M4  `apply_local` for one control vertex (valence 4; and a pole if present)
    M5  GPU sync after a FULL position update (`mark_vertices_dirty(all)` + `sync()`)
    M6  GPU sync after a LOCAL update (same, only the affected derived vertices)
    M7  cage + isoline segment refresh
    M8  one frame `draw()` + `glFinish` (V-BOTH; V-CAGE and V-ISO as M8c / M8i)

Time budget: a row stops early after `--budget` seconds (default 60; 0 = unlimited)
but never before 3 samples, and the table then says "n von N (Budget)" — so the
bench stays usable on a slow host instead of running for hours. Rows that were
cut are less reliable; they are never silently shortened.

Additions (not in the handoff table, so a total can be read off): M5w / M6w
write the derived positions into the lab's `core.Mesh` (full / local); D1 is one
complete drag step (`LabScene.move_control_vertex`), D2 the same step followed
by a frame. Frame times include whatever the GL implementation does at
`glFinish`; in a visible window the driver may still pace to vsync outside it.
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Callable, Optional

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from subdivision_lab._paths import ensure_paths  # noqa: E402

ensure_paths()

from mirai.scene_factory import mesh_from_positions_and_faces  # noqa: E402

from subdivision_lab.lab_scene import (  # noqa: E402
    LabScene,
    gl_info_strings,
    load_control_mesh,
    resolve_asset_name,
)
from subdivision_lab.lab_state import MAX_DERIVED_FACES, VIEW_BOTH, VIEW_CAGE, VIEW_ISO  # noqa: E402
from subdivision_lab.subd import SubdSurface  # noqa: E402

DEFAULT_RUNS = 30
DRAG_STEPS = 100
#: Wall-clock budget per table row in seconds (0 = unlimited). A row that hits it stops
#: early and reports its smaller n — see `timed()`.
DEFAULT_BUDGET_S = 60.0
MIN_BUDGET_RUNS = 3
DEFAULT_PLAN = (
    ("head_basemesh", (1, 2, 3)),
    ("man_with_shoes_basemesh", (1, 2, 3)),
)
BENCH_WIDTH, BENCH_HEIGHT = 1280, 800

MODE_HIDDEN = "headless/unsichtbares Fenster (Xvfb oder EGL)"
MODE_VISIBLE = "sichtbares Fenster"


def stats_ms(samples: list[float]) -> tuple[float, float, float]:
    return min(samples), statistics.median(samples), max(samples)


def timed(
    fn: Callable[[], object],
    runs: int,
    before: Optional[Callable[[int], object]] = None,
    budget_s: Optional[float] = None,
) -> list[float]:
    """Runs `fn` up to `runs` times, `before(i)` untimed; returns milliseconds per run.

    `budget_s`: wall-clock budget for the whole row (incl. the untimed `before`).
    Once it is exceeded — but never before `MIN_BUDGET_RUNS` samples — the row
    stops early; the report then shows the smaller n and a footnote. Needed
    because a full GPU sync at level 3 costs seconds on a slow host (README,
    "Beobachtung") and 30 such runs per row would take hours."""
    samples: list[float] = []
    started = time.perf_counter()
    for i in range(runs):
        if before is not None:
            before(i)
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
        if budget_s and len(samples) >= MIN_BUDGET_RUNS and time.perf_counter() - started > budget_s:
            break
    return samples


def control_valences(topology) -> list[int]:
    valence = [0] * len(topology.vertex_ids)
    for a, b in topology.edges:
        valence[a] += 1
        valence[b] += 1
    return valence


def pick_probe_vertices(topology) -> dict[str, tuple[int, int]]:
    """`{"Valenz 4": (index, valence), "Pol": (index, valence)}` — a regular
    vertex and an extraordinary one (valence != 4), if present."""
    valence = control_valences(topology)
    probes: dict[str, tuple[int, int]] = {}
    for index, v in enumerate(valence):
        if v == 4 and "Valenz 4" not in probes:
            probes["Valenz 4"] = (index, v)
        if v not in (4, 2) and "Pol" not in probes:
            probes["Pol"] = (index, v)
    return probes


def _gl_error() -> int:
    from pyglet import gl

    return int(gl.glGetError())


def _frame(scene: LabScene, mode: str, level: int) -> None:
    from pyglet import gl

    scene.draw(mode, level, True)
    gl.glFinish()


class BenchResult:
    """Sections of rows; a row is `(id, label, samples_ms, expected_n)`."""

    def __init__(self, host: str, window_mode: str, gl_version: str, gl_renderer: str, runs: int,
                 budget_s: float = 0.0) -> None:
        self.host = host
        self.window_mode = window_mode
        self.gl_version = gl_version
        self.gl_renderer = gl_renderer
        self.runs = runs
        self.budget_s = budget_s
        self.sections: list[dict] = []

    def section(self, asset: str, level: int, title: str) -> dict:
        sec = {"asset": asset, "level": level, "title": title, "rows": [], "notes": []}
        self.sections.append(sec)
        return sec

    def format(self) -> str:
        budget = f"{self.budget_s:.0f} s" if self.budget_s else "unbegrenzt"
        out = [
            "## Subdivision-Lab — Messung",
            "",
            f"- Host-Label: **{self.host}**",
            f"- Modus: **{self.window_mode}**",
            f"- GL_VERSION: `{self.gl_version}`",
            f"- GL_RENDERER: `{self.gl_renderer}`",
            f"- Python {platform.python_version()} auf {platform.platform()}",
            f"- Läufe pro Zeile: {self.runs} (Drag: {DRAG_STEPS} Schritte), Zeitbudget pro Zeile: {budget}; "
            "Zeiten in ms (min / Median / max)",
            "- Headless-Zahlen ersetzen keine Messung auf dem Referenz-PC "
            "(`docs/architecture/REFERENCE_HARDWARE.md` §4).",
            "",
        ]
        for sec in self.sections:
            out.append(f"### {sec['title']}")
            out.append("")
            if sec["rows"]:
                out.append("| ID | Was | min | Median | max | n |")
                out.append("|---|---|---:|---:|---:|---:|")
                short = False
                for rid, label, samples, expected in sec["rows"]:
                    lo, mid, hi = stats_ms(samples)
                    if len(samples) < expected:
                        short = True
                        n_text = f"{len(samples)} von {expected} (Budget)"
                    else:
                        n_text = str(len(samples))
                    out.append(f"| {rid} | {label} | {lo:.3f} | {mid:.3f} | {hi:.3f} | {n_text} |")
                out.append("")
                if short:
                    out.append(
                        f"- Zeilen mit „n von N (Budget)“ haben das Zeitbudget ({budget} pro Zeile) erreicht und vorzeitig "
                        "aufgehört: weniger Läufe als gefordert, die Spanne ist weniger belastbar."
                    )
                    out.append("")
            for note in sec["notes"]:
                out.append(f"- {note}")
            if sec["notes"]:
                out.append("")
        return "\n".join(out)


def _bench_level(result: BenchResult, scene: LabScene, asset: str, level: int, runs: int, log) -> None:
    topology = scene.topology
    surface = scene.surface
    budget = result.budget_s
    n_faces = surface.predicted_face_count(level)
    sec = result.section(asset, level, f"{asset} — Stufe {level}")
    rows = sec["rows"]

    def T(fn, before=None):
        return timed(fn, runs, before, budget)

    def add(rid: str, label: str, samples: list[float], expected: int = runs) -> None:
        rows.append((rid, label, samples, expected))

    if n_faces > MAX_DERIVED_FACES:
        sec["notes"].append(
            f"Stufe {level} abgelehnt (Lab-Limit): {n_faces} Flächen > {MAX_DERIVED_FACES} — nicht gemessen."
        )
        return

    # M1 — fresh topology read + all levels up to `level`
    log(f"{asset} L{level}: M1")
    mesh = scene.control_mesh
    m1 = T(lambda: SubdSurface(mesh).level(level))

    view, _ms, _ = scene.ensure_level(level)
    derived = view.derived
    sec["notes"].append(
        f"Fläche: {derived.n_verts} V / {len(derived.faces)} F; Stencil-Einträge: {derived.stencil_entries}; "
        f"Control: {len(topology.vertex_ids)} V / {len(topology.faces)} F."
    )
    add("M1", "Topologie + Stencils bauen (einmalig pro Stufe, ab Control)", m1)

    # M2 — derived core.Mesh + first RenderMesh allocation
    log(f"{asset} L{level}: M2")
    base_positions = derived.apply_full(scene.control_positions)
    holder: list = []

    def build_mesh_and_rm():
        m = mesh_from_positions_and_faces(base_positions, derived.faces)
        holder.append(scene._make_render_mesh(m))

    m2 = T(build_mesh_and_rm, before=lambda i: _free(holder))
    _free(holder)
    add("M2", "abgeleitetes core.Mesh + erste RenderMesh-Allokation (einmalig pro Stufe)", m2)

    # M3 — apply_full
    log(f"{asset} L{level}: M3")
    add("M3", "apply_full (alle abgeleiteten Positionen)", T(lambda: derived.apply_full(scene.control_positions)))

    # M5 — full position update + GPU sync
    log(f"{asset} L{level}: M5")
    all_ids = set(view.vertex_ids)

    def prepare_full(_i):
        view.positions = derived.apply_full(scene.control_positions)

    m5w = T(lambda: scene.write_positions(view), before=prepare_full)
    m5 = T(lambda: (view.render_mesh.mark_vertices_dirty(all_ids), view.render_mesh.sync()),
           before=lambda i: scene.write_positions(view))
    add("M5w", "alle abgeleiteten Positionen ins core.Mesh schreiben", m5w)
    add("M5", "GPU-Sync nach VOLLEM Update (mark_vertices_dirty(alle) + sync())", m5)

    # M4 / M6 — local update for the probe vertices
    for name, (index, valence) in pick_probe_vertices(topology).items():
        log(f"{asset} L{level}: M4/M6 {name}")
        affected = derived.inverse[index]
        label = f"{name} (Valenz {valence}, {len(affected)} abgeleitete Vertices betroffen)"
        base = scene.control_positions[index]
        touched: list = []

        def nudge(i, _index=index, _base=base):
            scene.control_positions[_index] = (_base[0] + 0.001 * (i + 1), _base[1], _base[2])

        def local_prepare(i, _index=index):
            nudge(i)
            derived.apply_local(_index, scene.control_positions, view.positions)

        def write_local(i, _affected=affected):
            local_prepare(i)
            touched[:] = scene.write_positions(view, _affected)

        m4 = T(lambda: derived.apply_local(index, scene.control_positions, view.positions), before=nudge)
        m6w = T(lambda: scene.write_positions(view, affected), before=local_prepare)
        m6 = T(lambda: (view.render_mesh.mark_vertices_dirty(set(touched)), view.render_mesh.sync()),
               before=write_local)
        scene.control_positions[index] = base
        view.positions = derived.apply_full(scene.control_positions)
        scene.write_positions(view)
        view.render_mesh.mark_vertices_dirty(all_ids)
        view.render_mesh.sync()
        add("M4", f"apply_local — {label}", m4)
        add("M6w", f"lokale Positionen ins core.Mesh schreiben — {name}", m6w)
        add("M6", f"GPU-Sync nach LOKALEM Update — {name}", m6)

    # M7 — cage + isoline segment refresh
    log(f"{asset} L{level}: M7")
    add("M7", "Käfig- + Isolinien-Segmente neu bauen",
        T(lambda: scene.refresh_lines(level), before=_bump(scene)))

    # M8 — frames
    log(f"{asset} L{level}: M8")
    for _ in range(2):
        _frame(scene, VIEW_BOTH, level)  # warm-up (shader compile, first uploads)
    add("M8", "ein Frame V-BOTH (draw + glFinish)", T(lambda: _frame(scene, VIEW_BOTH, level)))
    add("M8i", "ein Frame V-ISO (draw + glFinish)", T(lambda: _frame(scene, VIEW_ISO, level)))
    add("M8c", "ein Frame V-CAGE (Control-Mesh, draw + glFinish)", T(lambda: _frame(scene, VIEW_CAGE, level)))

    # D — simulated drag
    probes = pick_probe_vertices(topology)
    if "Valenz 4" in probes:
        _bench_drag(sec, scene, level, probes["Valenz 4"][0], budget, log)
    _restore_control(scene)


def _bump(scene: LabScene):
    def before(_i):
        scene.version += 1

    return before


def _free(holder: list) -> None:
    while holder:
        rm = holder.pop()
        vlist = rm.store.vertex_list()
        if vlist is not None:
            vlist.delete()


def _restore_control(scene: LabScene) -> None:
    """Control mesh + positions back to the loaded state (also bumps the version)."""
    topology = scene.topology
    scene.control_positions[:] = scene.surface.initial_positions
    for i, p in enumerate(scene.surface.initial_positions):
        scene.control_mesh.set_vertex_position(topology.vertex_ids[i], p)
    scene.version += 1


def _bench_drag(sec: dict, scene: LabScene, level: int, index: int, budget: float, log) -> None:
    log(f"{sec['asset']} L{level}: Drag-Simulation")
    vid = scene.topology.vertex_ids[index]
    view = scene.views[level]
    _restore_control(scene)
    scene.refresh_full(view)
    _frame(scene, VIEW_BOTH, level)

    rm = view.render_mesh
    before_counters = dict(rm.benchmark_counters)
    before_ids = dict(rm.resource_ids())
    base = scene.control_positions[index]
    step_ms, frame_ms = [], []
    started = time.perf_counter()
    for step in range(DRAG_STEPS):
        pos = (base[0] + 0.0005 * (step + 1), base[1] + 0.0003 * (step + 1), base[2])
        step_ms.append(scene.move_control_vertex(vid, pos, level))
        t0 = time.perf_counter()
        _frame(scene, VIEW_BOTH, level)
        frame_ms.append((time.perf_counter() - t0) * 1000.0)
        if budget and len(step_ms) >= MIN_BUDGET_RUNS and time.perf_counter() - started > budget:
            break
    after_counters = dict(rm.benchmark_counters)
    after_ids = dict(rm.resource_ids())

    sec["rows"].append(("D1", "ein kompletter Drag-Schritt (Valenz 4)", step_ms, DRAG_STEPS))
    sec["rows"].append(("D2", "ein Frame direkt nach dem Drag-Schritt (draw + glFinish)", frame_ms, DRAG_STEPS))
    keys = ("structural_rebuilds", "topology_updates", "vertex_updates", "geometry_uploads", "bounds_recalculations")
    deltas = {k: after_counters.get(k, 0) - before_counters.get(k, 0) for k in keys}
    unchanged = "unverändert" if before_ids == after_ids else "VERÄNDERT"
    sec["notes"].append(
        f"Drag ({len(step_ms)} Schritte) benchmark_counters-Delta: {deltas}; resource_ids {unchanged}; "
        f"glGetError = {_gl_error()}."
    )
    _restore_control(scene)
    scene.refresh_full(view)


def run_bench(
    host_label: str = "unlabeled",
    runs: int = DEFAULT_RUNS,
    plan=DEFAULT_PLAN,
    window_mode: str = MODE_HIDDEN,
    width: int = BENCH_WIDTH,
    height: int = BENCH_HEIGHT,
    budget_s: float = DEFAULT_BUDGET_S,
    log: Callable[[str], None] = lambda text: print(text, file=sys.stderr, flush=True),
) -> BenchResult:
    """Runs the measurements in the CURRENT GL context (the caller owns the
    window) and returns the result; `result.format()` is the Markdown report."""
    version, renderer = gl_info_strings()
    result = BenchResult(host_label, window_mode, version, renderer, runs, budget_s)
    for asset, levels in plan:
        resolve_asset_name(asset)
        scene = LabScene(asset, aspect=width / height, control_mesh=load_control_mesh(asset))
        try:
            for level in levels:
                _bench_level(result, scene, asset, level, runs, log)
        finally:
            scene.release()
    return result


def open_bench_window(visible: bool, width: int = BENCH_WIDTH, height: int = BENCH_HEIGHT):
    import pyglet

    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        pyglet.options["headless"] = True
    window = pyglet.window.Window(width=width, height=height, visible=visible, caption="Subdivision-Lab Bench")
    window.switch_to()
    from pyglet import gl

    fb_width, fb_height = window.get_framebuffer_size()
    gl.glViewport(0, 0, fb_width, fb_height)
    return window


def _tolerate_unencodable_output() -> None:
    """German text + arrows must not crash a redirected stdout with a legacy
    code page (Windows `> file`): replace what cannot be encoded."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mirai-Bastel Subdivision-Lab: Bench (§6)")
    parser.add_argument("--host", default="unlabeled", help="Wo wird gemessen? (Host-Label, steht in jeder Tabelle)")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help=f"Läufe pro Zeile (Default {DEFAULT_RUNS})")
    parser.add_argument("--budget", type=float, default=DEFAULT_BUDGET_S,
                        help=f"Zeitbudget pro Tabellenzeile in Sekunden (Default {DEFAULT_BUDGET_S:.0f}, 0 = unbegrenzt); "
                             "eine Zeile, die es erreicht, meldet ihr kleineres n")
    parser.add_argument("--visible", action="store_true", help="sichtbares Fenster statt unsichtbarem/headless")
    parser.add_argument("--assets", nargs="*", help="nur diese Assets (Default: head + man_with_shoes, Stufen 1-3)")
    _tolerate_unencodable_output()
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs muss >= 1 sein")
    plan = DEFAULT_PLAN
    if args.assets:
        try:
            plan = tuple((resolve_asset_name(name), (1, 2, 3)) for name in args.assets)
        except LookupError as exc:
            print(exc, file=sys.stderr)
            return 2
    window = open_bench_window(visible=args.visible)
    try:
        result = run_bench(args.host, args.runs, plan,
                           MODE_VISIBLE if args.visible else MODE_HIDDEN, budget_s=args.budget)
    finally:
        window.close()
    print(result.format())
    return 0


if __name__ == "__main__":
    sys.exit(main())
