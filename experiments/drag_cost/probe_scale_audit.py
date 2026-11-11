"""Scale audit probe (2026-11-10): where one deformation step goes, and what a stage costs once, on a dense mesh.

Usage (from the repo root, Windows and Linux alike; opens a hidden pyglet window):
    python experiments/drag_cost/probe_scale_audit.py
    python experiments/drag_cost/probe_scale_audit.py --assets examples/meshes/gollum_20k.obj --regions 5 15
    python experiments/drag_cost/probe_scale_audit.py --only split
    python experiments/drag_cost/probe_scale_audit.py --verify-dense    # regenerates the dense fixture, compares bytes
    python experiments/drag_cost/probe_scale_audit.py --make-dense      # rewrites the dense fixture, no window

Headless container: prefix with `xvfb-run -a`.

Report: `docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md`. Two blocks per asset, both in the
window's own chain (`Application` -> `Viewport` -> `GLRenderStore`, the `GL_TYPES` of `src/main.py`):

- `split`  one pose step (pose mode, E held, one mouse move + `update_viewport`) of a jaw-like region (the rule of
           `probe_morph_gl.rig_region`), first with the wire overlay off, then on, split by wrapping functions from
           the outside (nothing under `src/` is changed): the skin evaluation, the parts of
           `RenderMesh._sync_geometry` (neighbourhood sets, face normals, vertex normals, positions + normals,
           face rows), the whole-mesh wire rebuild, and the bytes handed to the store per step.
- `chain`  what happens once: load + first frame, save, parse, the first weight step (builds the mix surface), the
           first pose step (builds the skin surface), each with the process memory after it, and whether the SubD
           preview accepts the mesh.

The dense asset (`fixtures/gollum_87k.obj`, 87 500 V / 87 500 quads) is `gollum_20k.obj` after one Catmull-Clark step
of the production evaluator, committed as a test fixture since 2026-11-11 (Manu D5; provenance in `fixtures/README.md`).
`--verify-dense` regenerates it in a temporary file and compares the bytes; `--make-dense` rewrites it.

Numbers from a container must be labelled as such (`docs/architecture/REFERENCE_HARDWARE.md` §4); the reference PC
decides. Output is plain ASCII so it pastes cleanly from a Windows console.
"""

from __future__ import annotations

import argparse
import gc
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import EXPERIMENT_DIR, REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

GOLLUM_20K = "examples/meshes/gollum_20k.obj"
DENSE = EXPERIMENT_DIR / "fixtures" / "gollum_87k.obj"
DENSE_NAME = "dense"
DEFAULT_ASSETS = (GOLLUM_20K, DENSE_NAME)
DEFAULT_REGIONS = (15, 100)
DEFAULT_STEPS = 20
WARMUP_STEPS = 6
BLOCKS = ("split", "chain")

SPLIT_ROWS = (
    "1 skin evaluation (LBS + Mesh writes)",
    "2 RenderMesh._sync_geometry, total",
    "2a  neighbourhood sets",
    "2b  face normals",
    "2c  vertex normals",
    "2d  positions + normals -> mirror -> store",
    "2e  face rows (36 floats per face) -> store",
    "3 wire segments (whole mesh)",
    "4 face-data glBufferSubData at draw",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--assets", nargs="+", default=list(DEFAULT_ASSETS),
                        help=f"OBJ paths (relative to the repo root) or '{DENSE_NAME}' for the generated 87.5k mesh")
    parser.add_argument("--regions", nargs="+", type=int, default=list(DEFAULT_REGIONS),
                        help="weighted share of the points in percent, per split row")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="pose steps per split row")
    parser.add_argument("--only", choices=BLOCKS, help="run one block only")
    parser.add_argument("--make-dense", action="store_true", help="rewrite the dense fixture and stop")
    parser.add_argument("--verify-dense", action="store_true",
                        help="regenerate the dense fixture in a temporary file, compare it with the committed one, stop")
    return parser


def make_dense(target: Path = DENSE) -> Path:
    """`gollum_20k.obj` after one Catmull-Clark step (production evaluator), as an OBJ at `target`."""
    from loaders.obj_loader import load_obj
    from mirai.scene_factory import mesh_from_positions_and_faces
    from mirai.subdivision.catmull_clark import SubdSurface

    data = load_obj(REPO_ROOT / GOLLUM_20K)
    mesh = mesh_from_positions_and_faces(data.vertices, data.faces)
    surface = SubdSurface(mesh)
    level = surface.level(1)
    positions = level.apply_full([mesh.vertex_position(v) for v in surface.topology.vertex_ids])
    target.parent.mkdir(parents=True, exist_ok=True)
    # "\n" on every platform: the fixture's bytes (and sha256) must not depend on where it was generated.
    with open(target, "w", encoding="ascii", newline="\n") as fh:
        for p in positions:
            fh.write(f"v {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
        for face in level.faces:
            fh.write("f " + " ".join(str(i + 1) for i in face) + "\n")
    return target


def verify_dense() -> int:
    """Regenerates the dense fixture into a temporary file and compares it byte for byte with `DENSE` (D5
    reproducibility): 0 = identical."""
    import hashlib

    with tempfile.TemporaryDirectory() as tmp:
        fresh = make_dense(Path(tmp) / DENSE.name).read_bytes()
    committed = DENSE.read_bytes() if DENSE.is_file() else b""
    for label, data in (("committed", committed), ("regenerated", fresh)):
        print(f"{label:<12} {hashlib.sha256(data).hexdigest()}  {len(data)} bytes")
    same = fresh == committed
    print("identical" if same else "DIFFERENT")
    return 0 if same else 1


def resolve_asset(name: str) -> Path:
    if name == DENSE_NAME:
        return DENSE if DENSE.is_file() else make_dense()
    path = Path(name)
    path = path if path.is_absolute() else REPO_ROOT / path
    if not path.is_file():
        raise SystemExit(f"no such mesh: {name} (an OBJ path, or '{DENSE_NAME}')")
    return path


def process_memory_mib() -> float | None:
    """Resident memory of this process in MiB (working set on Windows); None where it cannot be read."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in (
                        "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                        "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]

            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                return None
            return counters.WorkingSetSize / 2**20
        with open("/proc/self/status", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("VmRSS"):
                    return int(line.split()[1]) / 1024.0
    except Exception:  # noqa: BLE001 - a missing counter must not end a measurement run
        return None
    return None


# -- split ---------------------------------------------------------------------------------------------


class _Wrappers:
    """Timing wrappers on class attributes, removed again by `remove()`."""

    def __init__(self) -> None:
        import viewport.derived as derived
        import viewport.gl_render_store as gl_store
        import viewport.render_mesh as render_mesh
        import viewport.viewport as viewport
        from mirai.skinning import SkinSurface

        self.acc: dict[str, float] = {}
        self.bytes = 0
        self._undo: list = []
        rows = SPLIT_ROWS
        for cls, name, label in (
            (SkinSurface, "_recompute", rows[0]),
            (render_mesh.RenderMesh, "_sync_geometry", rows[1]),
            (derived.DerivedGeometry, "affected_neighborhood", rows[2]),
            (derived.DerivedGeometry, "update_face_normals", rows[3]),
            (derived.DerivedGeometry, "update_vertex_normals", rows[4]),
            (render_mesh.RenderMesh, "_upload_vec3", rows[5]),
            (render_mesh.RenderMesh, "_upload_rows", rows[6]),
            (viewport.Viewport, "_sync_edges", rows[7]),
            (gl_store.GLRenderStore, "_flush_face_data", rows[8]),
        ):
            self._time(cls, name, label)
        original = gl_store.GLRenderStore.update

        def counting(store, name, offset, data, nbytes):
            self.bytes += nbytes
            return original(store, name, offset, data, nbytes)

        gl_store.GLRenderStore.update = counting
        self._undo.append((gl_store.GLRenderStore, "update", original))

    def _time(self, cls, name: str, label: str) -> None:
        original = getattr(cls, name)
        acc = self.acc

        def timed(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                acc[label] = acc.get(label, 0.0) + (time.perf_counter() - start) * 1000.0

        setattr(cls, name, timed)
        self._undo.append((cls, name, original))

    def reset(self) -> None:
        self.acc.clear()
        self.bytes = 0

    def remove(self) -> None:
        for cls, name, original in reversed(self._undo):
            setattr(cls, name, original)
        self._undo.clear()


def split_rows(path: Path, share: int, steps: int) -> list[str]:
    from pyglet import gl

    from drag_cost.probe_morph_gl import _key, build_app, rig_region

    wrappers = _Wrappers()
    lines: list[str] = []
    try:
        window, app = build_app(path)
        count = rig_region(app, share)
        points = len(app.scene.mesh.all_vertex_ids())
        e = _key("e")
        for wire in (False, True):
            if wire:
                app.viewport.set_display(True, True, False)
            app.pointer_motion(560, 300, 0.0, 0.0)
            app.key_press(_key("5"))
            app.key_press(e)
            app.pointer_motion(560, 296, 0.0, -4.0)
            app.update_viewport(0.0)
            app.viewport.render()
            gl.glFinish()
            for i in range(WARMUP_STEPS):  # the first steps after a build run slower (caches, allocator)
                app.pointer_motion(560, 296, 0.0, 4.0 if i % 2 else -4.0)
                app.update_viewport(0.0)
            samples: dict[str, list[float]] = {row: [] for row in SPLIT_ROWS}
            totals, draws, sent = [], [], []
            for i in range(steps):
                dy = -4.0 if (i // 20) % 2 == 0 else 4.0
                wrappers.reset()
                start = time.perf_counter()
                app.pointer_motion(560, 296, 0.0, dy)
                app.update_viewport(0.0)
                synced = time.perf_counter()
                app.viewport.render()
                gl.glFinish()
                done = time.perf_counter()
                totals.append((synced - start) * 1000.0)
                draws.append((done - synced) * 1000.0)
                sent.append(wrappers.bytes)
                for row in SPLIT_ROWS:
                    samples[row].append(wrappers.acc.get(row, 0.0))
            if not app.posed:
                raise RuntimeError(f"split rows: not posed ({app.status_message})")
            app.key_release(e)
            app.key_press(_key("6"))
            app.key_press(_key("5"))
            app.update_viewport(0.0)
            total = statistics.median(totals)
            p95 = sorted(totals)[min(len(totals) - 1, int(len(totals) * 0.95))]
            lines.append(
                f"[{path.stem}] {points} V, region {share} % = {count} V, wire {'ON' if wire else 'off'}, "
                f"{steps} pose steps, p50 ms"
            )
            lines.append(f"  step (pointer_motion + update_viewport)       {total:9.2f}  100 %   (p95 {p95:.2f})")
            for row in SPLIT_ROWS:
                value = statistics.median(samples[row])
                if value == 0.0 and row == SPLIT_ROWS[7] and not wire:
                    continue
                lines.append(f"  {row:<45} {value:9.2f}  {100.0 * value / total:5.1f} %")
            lines.append(f"  draw + glFinish                               {statistics.median(draws):9.2f}")
            lines.append(
                f"  bytes handed to the store per step            {int(statistics.median(sent)):>9}"
                f"  ({statistics.median(sent) / max(count, 1):.0f} per weighted vertex)"
            )
        window.close()
    finally:
        wrappers.remove()
    return lines


# -- chain ---------------------------------------------------------------------------------------------


def chain_rows(path: Path) -> list[str]:
    from core.serialization import scene_from_json
    from drag_cost.probe_morph_gl import _key, build_app, fill_target, frame, rig_region

    lines: list[str] = []
    last = [process_memory_mib()]

    def memory() -> str:
        """Process memory now and its change since the previous row (run one asset per process for clean totals)."""
        now, before = process_memory_mib(), last[0]
        last[0] = now
        return "memory n/a" if now is None or before is None else f"process {now:7.0f} MiB ({now - before:+7.0f})"

    def row(label: str, fn) -> None:
        gc.collect()
        start = time.perf_counter()
        fn()
        ms = (time.perf_counter() - start) * 1000.0
        gc.collect()
        lines.append(f"  {label:<56} {ms:9.0f} ms   {memory()}")

    start = time.perf_counter()
    window, app = build_app(path)
    frame(app)
    ms = (time.perf_counter() - start) * 1000.0
    mesh = app.scene.mesh
    lines.append(f"[{path.stem}] {len(mesh.all_vertex_ids())} V / {len(mesh.all_face_ids())} F, once per session or stage")
    lines.append(f"  {'load OBJ + scene + first frame':<56} {ms:9.0f} ms   {memory()}")
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "scene.mirai.json"
        row("save scene file", lambda: app.save_scene_file(target))
        lines.append(f"    file size {os.path.getsize(target) / 2**20:.1f} MiB")
        text = target.read_text(encoding="utf-8")
        row("parse scene file (scene_from_json, no viewport)", lambda: scene_from_json(text))
        del text

    app.key_press(_key("n", "ctrl"))
    row("write one target, offsets on 15 % of the points", lambda: fill_target(app, 15, app.morph_current_target))

    def weight(percent: int):
        def run() -> None:
            app.set_morph_weight(percent)
            frame(app)
        return run

    row("first weight step 0 -> 60 % (builds the mix surface)", weight(60))
    row("next weight step (patch) + frame", weight(61))
    row("rig + weights on 15 % of the points", lambda: rig_region(app, 15))
    frame(app)
    e = _key("e")

    def first_pose() -> None:
        app.pointer_motion(560, 300, 0.0, 0.0)
        app.key_press(_key("5"))
        app.key_press(e)
        app.pointer_motion(560, 296, 0.0, -4.0)
        frame(app)

    def next_pose() -> None:
        app.pointer_motion(560, 296, 0.0, -4.0)
        frame(app)

    row("first pose step (builds the skin surface)", first_pose)
    row("next pose step (patch, morph + skin) + frame", next_pose)
    app.key_release(e)
    app.key_press(_key("6"))
    app.key_press(_key("5"))
    frame(app)
    shown = app.subdivision.set_view("cage")
    frame(app)
    on = shown and app.subdivision.provider.surface_mesh is not None
    lines.append(f"  SubD preview: {'on, level ' + str(app.subdivision.level) if on else 'refused'} ({app.status_message})")
    window.close()
    return lines


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.make_dense:
        print(f"wrote {make_dense()}")
        return 0
    if args.verify_dense:
        return verify_dense()
    import pyglet

    from drag_cost.probe_drag_gl import machine_info

    probe = pyglet.window.Window(width=64, height=64, visible=False)
    info = machine_info(pyglet.gl.gl_info.get_version_string(), pyglet.gl.gl_info.get_renderer())
    probe.close()
    print("Scale audit probe (2026-11-10): pose-step split and one-time stage costs")
    for line in info:
        print(line)
    for name in args.assets:
        path = resolve_asset(name)
        if args.only in (None, "split"):
            for share in args.regions:
                print()
                for line in split_rows(path, share, args.steps):
                    print(line)
        if args.only in (None, "chain"):
            print()
            for line in chain_rows(path):
                print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
