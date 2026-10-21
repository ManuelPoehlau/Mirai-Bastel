"""Delete + Undo + Redo on `gollum_20k` with AD-023 stage 2 + AD-022 (prototype), p50 / p95 / max per column.

One command runs every configuration in its own Python process (so one run's memory and GC state cannot
colour the next), then the AD-022 B2 exactness check (`check_b2.py`), and prints a summary at the end:

    python experiments/topology_stage2_delete/probe_stage2.py                      # default: none stage1 H1,V1 all
    python experiments/topology_stage2_delete/probe_stage2.py --configs stage1 all --steps 10
    python experiments/topology_stage2_delete/probe_stage2.py --config all         # one configuration, this process

Configurations (`stage2.py`): `none` = today's code; `stage1` = V0,V2,V3,H0 (the previous measurement);
`H1,V1` = stage 1 + delta history + patched buffers, CPU picker; `all` = that + GPU picking (AD-022 B2-out).

Rows (camera framed close on the front-most vertex, as the drag_cost `topology` scenario; the cursor rests on
the first face of the patch): Delete 1 face (face mode, the drag_cost row), Delete 20 faces, Delete 1 vertex
(vertex mode), and - Manu's Blender comparison (2026-10-21) - **Box + Delete**: the mesh framed whole, a box over the
middle 40 % of the window in face mode (~6 500 faces on gollum_20k; Box Select is the unchanged CPU path in every
configuration), then Delete, Undo, Redo of that selection (`--no-box` skips this row). Per sample: the Delete as the Artist triggers it (Entf) + its frame, one plain mouse move + frame,
Ctrl+Z + frame, Ctrl+Y + frame, then an unmeasured Ctrl+Z so the next sample starts from the asset.

Columns (ms): `frame` = event + sync + draw. Inside the event: `op` (`apply_removal`, the Core op),
`history` (whole-mesh `export_state` / `load_state`, `history.push`, delta capture and delta apply),
`hover re-pick` (`Application._pick`: the CPU `PickCache` rebuild or the GPU ID render + read, and - GPU path
only - the RenderMesh sync it does first, shown as `of which sync`), `other` = the rest of the event (selection
upkeep, mirror stack, status). Then `viewport sync` (`Viewport.sync()` of the frame) and `draw`.

Other options: `--steps N` (default 20), `--row-seconds S` (default 120, budget per row), `--assets PATH`,
`--gc on|off` (default on, as the app), `--no-check` (skip the B2 check). Container numbers are not reference-PC
numbers. Copy the whole output.
"""

from __future__ import annotations

import argparse
import gc
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_EXPERIMENTS = Path(__file__).resolve().parents[1]
if str(_EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS))

from topology_stage2_delete._paths import REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

DEFAULT_CONFIGS = ("none", "stage1", "H1,V1", "all")
#: Box row: the box covers this fraction of the window's width and height, centred (mesh framed whole).
BOX_FRACTION = 0.4
GOLLUM_20K = "examples/meshes/gollum_20k.obj"


# -- timers ---------------------------------------------------------------------------------------------------


class Timer:
    def __init__(self) -> None:
        self.ms = 0.0

    def wrap(self, fn):
        timer = self

        def timed(*args, **kwargs):
            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                timer.ms += (time.perf_counter() - start) * 1000.0

        timed.__wrapped__ = fn
        return timed


TIMERS = {name: Timer() for name in ("op", "export", "load", "push", "capture", "apply", "pick", "pick_sync", "box")}
_in_pick = [False]


def install_timers() -> None:
    """Class / module level, after the configuration is installed (so the patched methods are wrapped)."""
    import mirai.application as application
    from core.history import HistoryStack
    from core.mesh import Mesh
    from viewport.render_mesh import RenderMesh

    from topology_stage2_delete import delta as delta_mod

    application.apply_removal = TIMERS["op"].wrap(application.apply_removal)
    application.elements_in_rect = TIMERS["box"].wrap(application.elements_in_rect)
    Mesh.export_state = TIMERS["export"].wrap(Mesh.export_state)
    Mesh.load_state = TIMERS["load"].wrap(Mesh.load_state)
    HistoryStack.push = TIMERS["push"].wrap(HistoryStack.push)
    delta_mod.capture_removal = TIMERS["capture"].wrap(delta_mod.capture_removal)
    delta_mod.apply_backward = TIMERS["apply"].wrap(delta_mod.apply_backward)
    delta_mod.apply_forward = TIMERS["apply"].wrap(delta_mod.apply_forward)
    pick = application.Application._pick
    pick_timer = TIMERS["pick"]

    def timed_pick(self, x, y):
        _in_pick[0] = True
        start = time.perf_counter()
        try:
            return pick(self, x, y)
        finally:
            pick_timer.ms += (time.perf_counter() - start) * 1000.0
            _in_pick[0] = False

    application.Application._pick = timed_pick
    sync = RenderMesh.sync
    sync_timer = TIMERS["pick_sync"]

    def timed_sync(self):
        if not _in_pick[0]:
            return sync(self)
        start = time.perf_counter()
        try:
            return sync(self)
        finally:
            sync_timer.ms += (time.perf_counter() - start) * 1000.0

    RenderMesh.sync = timed_sync


def reset_timers() -> None:
    for t in TIMERS.values():
        t.ms = 0.0


def phase() -> dict:
    t = {k: v.ms for k, v in TIMERS.items()}
    # capture contains the op it runs; the op is reported on its own.
    capture_only = t["capture"] - t["op"] if t["capture"] else 0.0
    return {
        "op": t["op"],
        "history": t["export"] + t["load"] + t["push"] + capture_only + t["apply"],
        "pick": t["pick"],
        "pick_sync": t["pick_sync"],
        "box": t["box"],
    }


# -- samples --------------------------------------------------------------------------------------------------


@dataclass
class Frame:
    event: float
    op: float
    history: float
    pick: float
    pick_sync: float
    sync: float
    draw: float
    box: float = 0.0

    @property
    def total(self) -> float:
        return self.event + self.sync + self.draw

    @property
    def other(self) -> float:
        return self.event - self.op - self.history - self.pick


@dataclass
class Sample:
    delete: Frame
    hover: Frame
    undo: Frame
    redo: Frame
    box: Frame | None = None


@dataclass
class Row:
    name: str
    samples: list = field(default_factory=list)


def measured_frame(rig, event) -> Frame:
    from pyglet import gl

    reset_timers()
    start = time.perf_counter()
    event()
    after_event = time.perf_counter()
    p = phase()
    rig.viewport.sync()
    after_sync = time.perf_counter()
    rig.viewport.render()
    gl.glFinish()
    end = time.perf_counter()
    return Frame((after_event - start) * 1000.0, p["op"], p["history"], p["pick"], p["pick_sync"],
                 (after_sync - after_event) * 1000.0, (end - after_sync) * 1000.0, p["box"])


def stats(values):
    from drag_cost import probe_drag_gl as drag

    return drag.Stats.of(list(values))


COLUMNS = (
    ("delete frame (op as triggered)", lambda s: s.delete.total),
    ("  op (Core delete)", lambda s: s.delete.op),
    ("  history", lambda s: s.delete.history),
    ("  hover re-pick", lambda s: s.delete.pick),
    ("    of which sync before pick", lambda s: s.delete.pick_sync),
    ("  other (selection, status)", lambda s: s.delete.other),
    ("  viewport sync", lambda s: s.delete.sync),
    ("  draw", lambda s: s.delete.draw),
    ("next hover frame", lambda s: s.hover.total),
    ("undo frame", lambda s: s.undo.total),
    ("  history", lambda s: s.undo.history),
    ("  hover re-pick (incl. sync)", lambda s: s.undo.pick),
    ("  other", lambda s: s.undo.other),
    ("  viewport sync", lambda s: s.undo.sync),
    ("redo frame", lambda s: s.redo.total),
    ("op + undo", lambda s: s.delete.total + s.undo.total),
)


BOX_COLUMNS = (
    ("box select frame (CPU, as today)", lambda s: s.box.total),
    ("  elements_in_rect", lambda s: s.box.box),
    ("  viewport sync (overlays)", lambda s: s.box.sync),
)


def row_lines(row: Row) -> list[str]:
    lines = [f"  {row.name:24s} n={len(row.samples):3d}"]
    columns = (BOX_COLUMNS + COLUMNS) if row.samples and row.samples[0].box is not None else COLUMNS
    for label, get in columns:
        st = stats(get(s) for s in row.samples)
        lines.append(f"    {label:32s} p50 {st.p50:9.2f}  p95 {st.p95:9.2f}  max {st.max:9.2f}")
    return lines


# -- the child: one configuration ------------------------------------------------------------------------------


def run_config(spec: str, args) -> int:
    import pyglet

    from topology_stage2_delete import stage2

    switches = stage2.install(spec)
    install_timers()
    from drag_cost import probe_drag_gl as drag
    from drag_cost import probe_navigation_gl as nav

    import main as src_main
    from core import FaceId, VertexId
    from mirai.interaction.input import Input

    asset = Path(args.assets) if args.assets else REPO_ROOT / GOLLUM_20K
    rig = nav.build_nav_rig(asset.stem, asset, src_main)
    from pyglet import gl

    print(f"configuration: {stage2.label(spec)}  (stage-2 switches: {','.join(sorted(switches)) or '-'})")
    for line in drag.machine_info(gl.gl_info.get_version(), gl.gl_info.get_renderer()):
        print(line)
    print(f"GC {args.gc}, threshold {gc.get_threshold()}")
    app, mesh = rig.app, rig.app.scene.mesh
    info = rig.info
    print(f"[{info.label}] {info.vertices} V / {info.faces} F / {info.triangles} triangles; load + first frame "
          f"{info.load_ms:.0f} ms")

    key = {name: Input("key", name) for name in ("1", "3", "delete")}
    ctrl_z, ctrl_y = Input("key", "z", frozenset({"ctrl"})), Input("key", "y", frozenset({"ctrl"}))
    seed, ring = drag.seed_with_ring(mesh)
    center = mesh.vertex_position(seed)
    radius = max(math.dist(center, mesh.vertex_position(v)) for v in ring) * 6.0
    app.camera.frame_on_bounds(center, radius)
    app._camera_changed()
    app.selection.clear()
    rig.viewport.on_selection_changed()
    rig.settle()
    patch20 = nav._face_patch(mesh, seed, 20)
    cx, cy = nav._screen_centroid(app, mesh, patch20[0])
    v_before = len(mesh.all_vertex_ids())
    if args.gc == "off":
        gc.disable()

    cursor = [cx, cy]

    def prepare(mode_key: str, ids) -> None:
        app.key_press(key[mode_key])
        app.selection.set(set(ids))
        rig.viewport.on_selection_changed()
        app.pointer_motion(*cursor)
        rig.settle()

    def sample(mode_key: str, ids, box=None) -> Sample:
        cx, cy = cursor
        box_frame = None
        if box is None:
            prepare(mode_key, ids)
        else:
            prepare(mode_key, ())
            box_frame = measured_frame(rig, box)
            if len(app.selection.faces) != len(ids):
                raise RuntimeError(f"box selected {len(app.selection.faces)} faces, expected {len(ids)}")
        deleted = measured_frame(rig, lambda: app.key_press(key["delete"]))
        if len(mesh.all_vertex_ids()) == v_before and mode_key == "1":
            raise RuntimeError(f"delete did nothing ({app.status_message})")
        hover = measured_frame(rig, lambda: app.pointer_motion(cx + 1.0, cy, 1.0, 0.0))
        undo = measured_frame(rig, lambda: app.key_press(ctrl_z))
        redo = measured_frame(rig, lambda: app.key_press(ctrl_y))
        app.key_press(ctrl_z)
        app.selection.clear()
        rig.viewport.on_selection_changed()
        rig.settle()
        if len(mesh.all_vertex_ids()) != v_before:
            raise RuntimeError(f"row did not undo cleanly ({app.status_message})")
        return Sample(deleted, hover, undo, redo, box_frame)

    def box_row():
        """Manu's Blender comparison (2026-10-21): Box-select thousands of faces on the whole mesh, delete, undo.
        The mesh is framed whole; the box is the middle of the window (`BOX_FRACTION` of each side); the pick
        cache is invalidated first, as after a camera move. Box Select is the unchanged CPU path in every
        configuration (AD-022 slice 2 is not in this prototype)."""
        from mirai.application import elements_in_rect
        from mirai.viewport.picking_cache import PickCache

        app.frame_scene()
        app._camera_changed()
        rig.settle()
        w, h = app.viewport_width, app.viewport_height
        fx = (1.0 - BOX_FRACTION) / 2.0
        rect = (w * fx, h * fx, w * (1.0 - fx), h * (1.0 - fx))
        app.key_press(key["3"])
        found = elements_in_rect(app._edit_camera, mesh, app.selection.mode, rect, w, h, cache=PickCache(),
                                 occlusion=app.display.show_faces)
        cursor[:] = [(rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0]

        def box() -> None:
            # What `_drag_select_finish` does for a box (selection.set, notify, soft refresh, status, re-pick).
            app._pick_cache.invalidate()
            hit = elements_in_rect(app._edit_camera, mesh, app.selection.mode, rect, w, h, cache=app._pick_cache,
                                   occlusion=app.display.show_faces)
            app.selection.set(hit)
            app.viewport.on_selection_changed()
            app._soft_preview_refresh()
            app._refresh_hover()

        return f"box + delete {len(found)} faces", "3", sorted(found), box

    rows = []
    plans = [("delete 1 face", "3", [FaceId(patch20[0])], None),
             ("delete 20 faces", "3", [FaceId(f) for f in patch20], None),
             ("delete 1 vertex", "1", [VertexId(seed)], None)]
    for index in range(len(plans) + (0 if args.no_box else 1)):
        name, mode_key, ids, box = plans[index] if index < len(plans) else box_row()
        row = Row(name)
        deadline = time.perf_counter() + args.row_seconds
        sample(mode_key, ids, box)  # warm-up (first ID render, first patch), not counted
        while len(row.samples) < args.steps and (len(row.samples) < 3 or time.perf_counter() < deadline):
            row.samples.append(sample(mode_key, ids, box))
        rows.append(row)
        for line in row_lines(row):
            print(line)
        sys.stdout.flush()
    if args.gc == "off":
        gc.enable()
    print("Counters (whole run incl. warm-up):")
    print(stage2.stats_text())
    print("SUMMARY " + stage2.label(spec) + " | " + " | ".join(
        f"{r.name}: frame {stats(s.delete.total for s in r.samples).p50:.0f}, undo "
        f"{stats(s.undo.total for s in r.samples).p50:.0f}, redo {stats(s.redo.total for s in r.samples).p50:.0f}"
        for r in rows))
    rig.drag_rig.window.close()
    return 0


# -- the driver -------------------------------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--configs", nargs="+", default=list(DEFAULT_CONFIGS))
    parser.add_argument("--config", help="run one configuration in this process (no summary, no check)")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--row-seconds", type=float, default=120.0)
    parser.add_argument("--assets")
    parser.add_argument("--gc", choices=("on", "off"), default="on")
    parser.add_argument("--no-check", action="store_true")
    parser.add_argument("--no-box", action="store_true", help="skip the Box + Delete row")
    args = parser.parse_args(argv)
    if args.config:
        return run_config(args.config, args)

    here = Path(__file__).resolve()
    passed = [a for a in ("--steps", str(args.steps), "--row-seconds", str(args.row_seconds), "--gc", args.gc)]
    if args.no_box:
        passed.append("--no-box")
    if args.assets:
        passed += ["--assets", args.assets]
    summary = []
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    for spec in args.configs:
        print(f"===== {spec} =====", flush=True)
        proc = subprocess.run([sys.executable, str(here), "--config", spec, *passed], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out = proc.stdout
        print(out, end="", flush=True)
        summary += [line[len("SUMMARY "):] for line in out.splitlines() if line.startswith("SUMMARY ")]
        if proc.returncode != 0:
            summary.append(f"{spec}: FAILED (exit {proc.returncode})")
    if not args.no_check:
        print("===== AD-022 B2 check =====", flush=True)
        check = here.with_name("check_b2.py")
        proc = subprocess.run([sys.executable, str(check), *(["--assets", args.assets] if args.assets else [])],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(proc.stdout, end="")
        summary += [line for line in proc.stdout.splitlines() if line.startswith("B2 RESULT")]
    print()
    print("===== summary (ms, p50) =====")
    for line in summary:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
