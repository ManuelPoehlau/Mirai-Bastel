"""Morph-target cost probe with the real GL backend (AD-025 Phase 3 and Phase 5, 2026-10-27).

Usage (from the repo root, Windows and Linux alike; opens a hidden pyglet window):
    python experiments/drag_cost/probe_morph_gl.py
    python experiments/drag_cost/probe_morph_gl.py --assets head_basemesh --steps 300
    python experiments/drag_cost/probe_morph_gl.py --assets examples/meshes/gollum_20k.obj
    python experiments/drag_cost/probe_morph_gl.py --only-topology      # the Phase 5 rows only
    python experiments/drag_cost/probe_morph_gl.py --only-phase4        # Phase 4: 1 / 10 targets, with SubD
    python experiments/drag_cost/probe_morph_gl.py --memory             # Phase 4: layer memory, no window

Headless container: prefix with `xvfb-run -a`.

What it measures, in the window's own chain (`Application` -> `Viewport` -> `GLRenderStore`, the
`GL_TYPES` of `src/main.py`), per asset and per target occupancy (15 % / 100 % of the points carry an
offset; the offsets are a smooth bump):

- `weight step`  one +/-1 % weight step as the hold-N drag makes it: `pointer_motion` (sets the weight)
                 + `update_viewport` (claims the H7 slot, the provider patches the mix, `Viewport.sync`
                 uploads it). The Phase 3 bar: <= 16.7 ms p95 on head and man_with_shoes on the
                 reference PC; gollum_20k "usable" (H5c).
- `(draw)`       `Viewport.render()` + `glFinish()` of that frame (a software rasteriser is not GPU time).
- `first show`   the step from 0 % to 1 % (builds the evaluated surface once).
- `tap N`        0 % -> the last weight (the evaluated surface is kept; its GL buffers are rebuilt).
- `view commit`  Tab into the editing view, a W drag of the front-most region (36 points), and the
                 release: the time of the release (the offset write through `TranslatingHistory`) and
                 of the frame after it.
- `apply`        Ctrl+A in `4` on the placed base with its target (positions + `map_vector_layers`).
- `topology`     (Phase 5) Knife commit (Enter after edge -> interior -> interior -> edge on the front-most
                 quad), Loop Insert (`I` on its edge), Extrude (hold T, drag, release: the whole gesture)
                 and Collapse (its edge), each as the operation's own call and the frame after it, first
                 without a target, then with one target (offsets on 100 % of the points) dialled in at
                 60 % (the mix is rebuilt on the new topology in the frame after). Every run is undone.

- `targets`      (Phase 4) per asset, 1 and 10 targets with offsets on 15 % (each target its own region) or
                 100 % of the points, every target but the current one at 50 %: the hold-N weight step of the
                 current one, without SubD and with the SubD preview on (level 2, the stage chain morph ->
                 SubD of the mixed cage). gollum_20k: SubD refuses (> 25,000 faces at level 1).
- `memory`       (Phase 4, `--memory`, no window) the traced memory of 10 / 50 targets with offsets on 15 % / 100 %
                 of the points, a per-element write of one dense target under one recording, a bulk frame change
                 (`map_vector_layers`, the Apply-transform write) of all of them under one recording plus five
                 watches (time, traced peak, journal records) and its Undo. Defaults: gollum_20k and gollum.

Numbers from a container must be labelled as such (`docs/architecture/REFERENCE_HARDWARE.md` §4); only
the reference PC decides the 16.7 ms bar. Output is plain ASCII.
"""

from __future__ import annotations

import argparse
import gc
import math
import random
import sys
import time
import tracemalloc
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

from drag_cost.probe_drag_gl import HEIGHT, WIDTH, Stats, grow_region, machine_info  # noqa: E402

DEFAULT_ASSETS = ("head_basemesh", "man_with_shoes_basemesh", "examples/meshes/gollum_20k.obj")
MEMORY_ASSETS = ("examples/meshes/gollum_20k.obj", "examples/meshes/gollum.obj")
MEMORY_COUNTS = (10, 50)
PHASE4_COUNTS = (1, 10)
DEFAULT_STEPS = 200
DEFAULT_REPS = 5
TOPOLOGY_OPS = ("knife", "loop insert", "extrude", "collapse")
OCCUPANCIES = (15, 100)
THRESHOLD_P95_MS = 16.7


def resolve_mesh(name: str) -> Path:
    from loaders.assets import asset_names, asset_path

    if name in asset_names():
        return Path(asset_path(name))
    path = Path(name)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.is_file():
        raise SystemExit(f"unknown asset or file: {name!r}; known: {', '.join(asset_names())}")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Morph-target cost of the real GL chain (AD-025 Phases 3 and 5)")
    parser.add_argument("--assets", nargs="+", default=list(DEFAULT_ASSETS),
                        help="registry names or .obj paths (default: head, body, gollum_20k)")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="weight steps per row")
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS, help="runs per topology operation (Phase 5)")
    parser.add_argument("--only-topology", action="store_true", help="skip the Phase 3 weight / view rows")
    parser.add_argument("--only-phase4", action="store_true",
                        help="Phase 4 rows only: weight steps with 1 / 10 targets (15 / 100 %%), with and without SubD")
    parser.add_argument("--targets", type=int, nargs="+", default=list(PHASE4_COUNTS),
                        help="target counts of the Phase 4 rows (default 1 10)")
    parser.add_argument("--no-subd", action="store_true", help="Phase 4 rows without the SubD variant")
    parser.add_argument("--memory", action="store_true",
                        help="Phase 4: layer memory and journal cost only (no window; default assets gollum_20k, gollum)")
    return parser


def _key(value, *mods):
    from mirai.interaction.input import Input

    return Input("key", value, frozenset(mods))


def build_app(path: Path):
    import pyglet

    import main as src_main
    from mirai.application import Application

    window = pyglet.window.Window(width=WIDTH, height=HEIGHT, visible=False)
    app = Application()
    app.init_scene("obj", obj_path=path, **src_main.GL_TYPES)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.update_viewport(0.0)
    return window, app


def fill_target(app, occupancy: int, lid=None, rank: int = 0) -> int:
    """A smooth bump on `occupancy` % of the points (the ones nearest a seed point: the front-most one, or
    for `rank` k > 0 the k-th of the points sorted by z, x - another region per target)."""
    mesh = app.scene.mesh
    lid = mesh.point_layer_ids()[0] if lid is None else lid
    ids = mesh.all_vertex_ids()
    if rank:
        ordered_seeds = sorted(ids, key=lambda v: (mesh.vertex_position(v)[2], mesh.vertex_position(v)[0], int(v)))
        seed = ordered_seeds[(len(ordered_seeds) - 1 - rank * len(ordered_seeds) // 13) % len(ordered_seeds)]
    else:
        seed = max(ids, key=lambda v: (mesh.vertex_position(v)[2], int(v)))
    sp = mesh.vertex_position(seed)
    ordered = sorted(ids, key=lambda v: math.dist(mesh.vertex_position(v), sp))
    chosen = ordered[: max(1, len(ids) * occupancy // 100)]
    reach = math.dist(mesh.vertex_position(chosen[-1]), sp) or 1.0

    def write():
        for v in chosen:
            r = math.dist(mesh.vertex_position(v), sp) / reach
            mesh.set_layer_value(lid, v, (0.0, 0.02 * (1.0 - r * r) + 1e-6, 0.05 * (1.0 - r * r) + 1e-6))

    app.apply_mesh_change("probe offsets", lambda: write() or set())
    return len(chosen)


def frame(app):
    from pyglet import gl

    start = time.perf_counter()
    app.update_viewport(0.0)
    mid = time.perf_counter()
    app.viewport.render()
    gl.glFinish()
    return (mid - start) * 1000.0, (time.perf_counter() - mid) * 1000.0


def weight_rows(app, steps: int) -> tuple[Stats, Stats, float]:
    from mirai.morph_targets import DRAG_PIXELS_PER_PERCENT

    app.set_morph_weight(0)
    frame(app)
    n = _key("n")
    app.key_press(n)
    start = time.perf_counter()
    app.pointer_motion(400, 300, DRAG_PIXELS_PER_PERCENT, 0.0)
    _, draw = frame(app)
    first = (time.perf_counter() - start) * 1000.0 - draw
    samples, draws = [], []
    direction = 1.0
    for i in range(steps):
        if app.morph_weight >= 100:
            direction = -1.0
        elif app.morph_weight <= 1:
            direction = 1.0
        t0 = time.perf_counter()
        app.pointer_motion(400, 300, direction * DRAG_PIXELS_PER_PERCENT, 0.0)
        _, draw = frame(app)
        samples.append((time.perf_counter() - t0) * 1000.0 - draw)
        draws.append(draw)
    app.key_release(n)
    return Stats.of(samples), Stats.of(draws), first


def ab_row(app, reps: int = 4) -> Stats:
    """Tap N: 0 % -> the last weight (the surface is kept, its GL buffers are rebuilt)."""
    n = _key("n")
    samples = []
    app.set_morph_weight(60)
    frame(app)
    for _ in range(reps):
        for _ in range(2):
            t0 = time.perf_counter()
            app.key_press(n)
            app.key_release(n)
            _, draw = frame(app)
            if app.morph_weight:
                samples.append((time.perf_counter() - t0) * 1000.0 - draw)
    return Stats.of(samples)


def view_commit_row(app, reps: int = 5) -> tuple[Stats, Stats]:
    releases, frames = [], []
    for _ in range(reps):
        app.key_press(_key("tab"))
        frame(app)
        region = grow_region(app.scene.mesh, 36)
        app.selection.set(set(region))
        app.viewport.on_selection_changed()
        w = _key("w")
        app.key_press(w)
        for i in range(10):
            app.pointer_motion(400 + i, 300, 2.0, 1.0)
        frame(app)
        t0 = time.perf_counter()
        app.key_release(w)
        releases.append((time.perf_counter() - t0) * 1000.0)
        frames.append(frame(app)[0])
        app.key_press(_key("tab"))
        frame(app)
    return Stats.of(releases), Stats.of(frames)


def apply_row(app) -> float:
    from core import ObjectTransform
    from mirai import object_space

    obj = app.scene.edit_object
    obj.transform = ObjectTransform(
        translation=(0.3, 0.0, 0.0), rotation=object_space.axis_angle_rotation((0.0, 1.0, 0.0), 0.4), scale=1.5
    )
    app._placement_changed()
    app.key_press(_key("4"))
    app.selection.objects = {obj.id}
    t0 = time.perf_counter()
    ok = app.dispatch_command("ApplyTransform")
    elapsed = (time.perf_counter() - t0) * 1000.0
    if not ok:
        raise RuntimeError(app.status_message)
    app.key_press(_key("z", "ctrl"))
    app.key_press(_key("1"))
    return elapsed


# -- Phase 5: topology edits with a target ------------------------------------------------------------


def _front_quad(mesh):
    """The quad with the front-most centroid (deterministic)."""
    def key(f):
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(f)]
        return (sum(p[2] for p in pts) / len(pts), -int(f))

    return max((f for f in mesh.all_face_ids() if len(mesh.face_vertices(f)) == 4), key=key)


def _select(app, mode, ids):
    from core import SelectionMode

    sel = app.selection
    sel.mode = getattr(SelectionMode, mode)
    sel.clear()
    sel.add(set(ids))
    app.viewport.on_selection_changed()


def _run_op(app, op: str) -> float:
    """One operation through the app's keys; returns the ms of its own call (the Knife: Enter; Extrude:
    the whole hold-drag-release gesture). Raises when it did not push exactly one history entry."""
    mesh = app.scene.mesh
    face = _front_quad(mesh)
    edge = mesh.face_edges(face)[0]
    history = len(app.history)
    if op == "knife":
        # The session's clicks go to the tool directly (on small faces a screen click would snap to a
        # vertex); Enter then runs the app's commit: resolver, Core, check, history, residue, sync.
        from viewport.derived import triangulate_mesh_face

        edges = mesh.face_edges(face)
        centres = [tuple(sum(mesh.vertex_position(v)[k] for v in tri) / 3.0 for k in range(3))
                   for tri in triangulate_mesh_face(mesh, face)]
        app.selection.clear()
        app.key_press(_key("c"))
        knife = app._knife.tool
        targets = [{"kind": "edge", "edge_id": edges[0], "t": 0.4}]
        targets += [{"kind": "face", "face_id": face, "position": c, "distance_px": 100.0} for c in centres]
        targets.append({"kind": "edge", "edge_id": edges[2], "t": 0.6})
        for target in targets:
            if not knife.click(target):
                raise RuntimeError(f"knife: click refused ({knife.last_refusal if hasattr(knife, 'last_refusal') else target})")
        t0 = time.perf_counter()
        app.key_press(_key("enter"))
    elif op == "extrude":
        _select(app, "FACE", {face})
        t = _key("t")
        t0 = time.perf_counter()
        app.key_press(t)
        for i in range(6):
            app.pointer_motion(400 + 3 * i, 300 - 2 * i, 3.0, -2.0)
        app.key_release(t)
    else:
        _select(app, "EDGE", {edge})
        t0 = time.perf_counter()
        app.dispatch_command("LoopInsert" if op == "loop insert" else "Collapse")
    elapsed = (time.perf_counter() - t0) * 1000.0
    if len(app.history) != history + 1:
        raise RuntimeError(f"{op}: {app.status_message}")
    return elapsed


def topology_rows(app, reps: int) -> dict:
    """op -> (Stats of the call, Stats of the frame after); each run undone (Undo not timed). The cursor
    is over the viewport first, as in use: a commit then refreshes the hover with a GPU pick of the new
    topology, which is part of the call (≈ 20 ms on head in the container); without a cursor that pick
    is skipped and the rows are not comparable."""
    app.pointer_motion(WIDTH / 2, HEIGHT / 2, 0.0, 0.0)
    out = {}
    for op in TOPOLOGY_OPS:
        calls, frames = [], []
        for _ in range(reps):
            calls.append(_run_op(app, op))
            frames.append(sum(frame(app)))
            app.key_press(_key("z", "ctrl"))
            frame(app)
        out[op] = (Stats.of(calls), Stats.of(frames))
    return out


# -- Phase 4: weight steps with several targets, with and without SubD ---------------------------------


def phase4_rows(path: Path, steps: int, counts, subd: bool) -> list[str]:
    """Per target count and occupancy: a fresh app, `count` targets (each a bump on its own region, or on
    every point), every target but the current one dialled in at 50 %, then the hold-N drag of the current
    one (`weight_rows`) - without SubD and, when `subd`, with the SubD preview on (level 2, the stage chain
    morph -> SubD). A level the preview refuses (gollum_20k: > 25,000 faces already at level 1) is reported."""
    lines = []
    for count in counts:
        for occupancy in OCCUPANCIES:
            window, app = build_app(path)
            for _ in range(count):
                app.key_press(_key("n", "ctrl"))
            lids = app.scene.mesh.point_layer_ids()
            stored = sum(fill_target(app, occupancy, lid, rank) for rank, lid in enumerate(lids))
            for lid in lids[:-1]:
                app.set_morph_weight(50, lid)
            frame(app)
            label = f"{path.stem:<26} {len(app.scene.mesh.all_vertex_ids()):>6} V  {count:>2} target{'s' if count > 1 else ' '} x {occupancy:>3} % ({stored:>7})"
            for with_subd in (False, True) if subd else (False,):
                if with_subd:
                    if not app.subdivision.set_view("cage") or (frame(app) and app.subdivision.provider.surface_mesh is None):
                        lines.append(f"{label}  + SubD L{app.subdivision.level}: refused ({app.status_message})")
                        continue
                step, draw, first = weight_rows(app, steps)
                verdict = "ok" if step.p95 <= THRESHOLD_P95_MS else "OVER"
                what = f"+ SubD L{app.subdivision.level}" if with_subd else "no SubD  "
                lines.append(f"{label}  {what}  weight step {step.text()}  [{verdict}]  (draw p50 {draw.p50:.2f})")
            window.close()
    return lines


# -- Phase 4: memory of many targets (no window) --------------------------------------------------


def _support(mesh, occupancy: int, rng) -> list:
    """`occupancy` % of the points, a contiguous patch around a random point (a facial target is local)."""
    ids = mesh.all_vertex_ids()
    if occupancy >= 100:
        return ids
    seed = mesh.vertex_position(rng.choice(ids))
    ordered = sorted(ids, key=lambda v: math.dist(mesh.vertex_position(v), seed))
    return ordered[: max(1, len(ids) * occupancy // 100)]


def _traced() -> int:
    gc.collect()
    return tracemalloc.get_traced_memory()[0]


def memory_rows(path: Path) -> list[str]:
    from core import PointLayerInfo
    from core.operations import record_mesh_change
    from mirai.scene_factory import build_core_scene_from_obj

    mib = 1024.0 * 1024.0
    lines = []
    for count in MEMORY_COUNTS:
        for occupancy in OCCUPANCIES:
            mesh = build_core_scene_from_obj(path).mesh
            rng = random.Random(count * 1000 + occupancy)
            supports = [_support(mesh, occupancy, rng) for _ in range(count)]
            tracemalloc.start()
            before = _traced()
            lids = []
            for k, support in enumerate(supports):
                lid = mesh.add_point_layer(PointLayerInfo(f"T{k}"))
                lids.append(lid)
                for v in support:
                    mesh.set_layer_value(lid, v, (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
            held = _traced() - before
            tracemalloc.stop()  # timings untraced (tracing slows Python allocations several-fold)
            # a per-element write of one dense target under one recording (the editing view's commit, an import)
            values = [(v, (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) for v in mesh.all_vertex_ids()]
            t0 = time.perf_counter()
            delta, _ = record_mesh_change(mesh, lambda: [mesh.set_layer_value(lids[0], v, d) for v, d in values] and None)
            write_ms = (time.perf_counter() - t0) * 1000.0
            del delta, values
            # the bulk frame change (Apply transform) of every target under one recording + five watches
            watches = [mesh.watch() for _ in range(5)]
            rotate = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
            t0 = time.perf_counter()
            change = mesh.begin_change()
            mesh.map_vector_layers(rotate)
            delta = mesh.end_change(change)
            bulk_ms = (time.perf_counter() - t0) * 1000.0
            t0 = time.perf_counter()
            mesh.apply_delta(delta, reverse=True)
            undo_ms = (time.perf_counter() - t0) * 1000.0
            del delta
            for watch in watches:
                watch.take()
            tracemalloc.start()
            base = _traced()
            tracemalloc.reset_peak()
            change = mesh.begin_change()
            mesh.map_vector_layers(rotate)
            delta = mesh.end_change(change)
            peak = tracemalloc.get_traced_memory()[1] - base
            kept = _traced() - base
            tracemalloc.stop()
            records = sum(len(r) for r in delta.layer_values.values())
            for watch in watches:
                watch.close()
            stored = sum(len(s) for s in supports)
            lines.append(
                f"{path.stem:<12} {len(mesh.all_vertex_ids()):>6} V  {count:>2} targets x {occupancy:>3} %"
                f" ({stored:>8} values): held {held / mib:7.1f} MiB | one dense target written, 1 recording"
                f" {write_ms:7.1f} ms | bulk map {bulk_ms:7.1f} ms, peak {peak / mib:6.1f} MiB, kept {kept / mib:6.1f} MiB,"
                f" {len(delta.layer_whole)} whole + {records} per-element records | undo {undo_ms:6.1f} ms"
            )
            del mesh, delta, change
            gc.collect()
    return lines


def _header(args) -> list[str]:
    from pyglet.gl import gl_info

    lines = machine_info(gl_info.get_version_string(), gl_info.get_renderer())
    lines.append(f"Morph probe (AD-025 Phases 3, 4 and 5), {args.steps} weight steps per row; bar {THRESHOLD_P95_MS} ms p95;"
                 f" {args.reps} runs per topology row")
    return lines


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.memory:
        assets = args.assets if args.assets != list(DEFAULT_ASSETS) else list(MEMORY_ASSETS)
        lines = [f"Morph probe (AD-025 Phase 4): point-layer memory and journal cost, Python {sys.version.split()[0]}"]
        for path in (resolve_mesh(a) for a in assets):
            lines += memory_rows(path)
        print("\n".join(lines))
        return 0
    paths = [resolve_mesh(a) for a in args.assets]
    lines = []
    if args.only_phase4:
        for path in paths:
            rows = phase4_rows(path, args.steps, args.targets, not args.no_subd)
            if not lines:
                lines = _header(args)
            lines += rows
        print("\n".join(lines))
        return 0
    for path in paths:
        window, app = build_app(path)
        if not lines:
            lines = _header(args)
        count = len(app.scene.mesh.all_vertex_ids())
        plain = topology_rows(app, args.reps)
        app.key_press(_key("n", "ctrl"))
        for occupancy in () if args.only_topology else OCCUPANCIES:
            stored = fill_target(app, occupancy)
            step, draw, first = weight_rows(app, args.steps)
            verdict = "ok" if step.p95 <= THRESHOLD_P95_MS else "OVER"
            lines.append(
                f"{path.stem:<26} {count:>6} V  offsets {occupancy:>3} % ({stored:>6})  weight step {step.text()}"
                f"  [{verdict}]  (draw p50 {draw.p50:.2f})  first show {first:.1f} ms"
            )
        if not args.only_topology:
            lines.append(f"{path.stem:<26} tap N 0 % -> 60 %: {ab_row(app).text()}")
            release, after = view_commit_row(app)
            lines.append(f"{path.stem:<26} view commit (36 points): release {release.text()}  frame after {after.text()}")
            lines.append(f"{path.stem:<26} apply transform with one target: {apply_row(app):.1f} ms")
            lines += phase4_rows(path, args.steps, args.targets, not args.no_subd)
        stored = fill_target(app, 100)
        app.set_morph_weight(60)
        frame(app)
        layered = topology_rows(app, args.reps)
        for op in TOPOLOGY_OPS:
            (c0, f0), (c1, f1) = plain[op], layered[op]
            lines.append(
                f"{path.stem:<26} {op:<11} no target: call {c0.text()} frame {f0.p50:.1f}"
                f" | one target ({stored} offsets, 60 %): call {c1.text()} frame {f1.p50:.1f}"
            )
        window.close()
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
