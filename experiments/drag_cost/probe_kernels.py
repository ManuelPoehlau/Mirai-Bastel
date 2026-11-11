"""Kernel probe (2026-11-10): the production evaluation code against the same computation on packed arrays.

Usage (from the repo root; no window, no GL):
    python experiments/drag_cost/probe_kernels.py
    python experiments/drag_cost/probe_kernels.py --assets examples/meshes/gollum_20k.obj dense
    python experiments/drag_cost/probe_kernels.py --no-native

Report: `docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md` §6. A measurement of where the
time is, not an implementation proposal. Per asset, the CPU side only (`TraceStore`, no upload):

- `visible`  making a position change of a region visible: the production `RenderMesh` geometry sync (1-ring face
             and vertex normals, positions, normals and face rows as buffer data) against the same normals on
             int slots (`flat`: pure Python, no face rows), on NumPy arrays and in native C.
- `skin`     linear blend skinning of a weighted region: `SkinSurface.update` against NumPy / native C.
- `morph`    one weight step of one target: `MixSurface.update` against NumPy / native C.
- `subd`     one Catmull-Clark level of the mesh as the cage: `SubdLevel.apply_full` against NumPy / native C.

Every array kernel is checked against the production values before it is timed (the printed `max diff`).

Optional parts, each skipped with a line when unavailable:
- **NumPy** - not a project dependency. On the reference PC only a NumPy built without the x86-64-v2 baseline
  imports (`REFERENCE_HARDWARE.md` §2: 2.2.6 under Python 3.12). Runtime SIMD dispatch above the baseline is
  switched off for this run (`NPY_DISABLE_CPU_FEATURES`), so a modern CPU does not use AVX here.
- **native C** - `kernels_native.c`, compiled on the fly with `cc` / `gcc` / `clang` (`-O2 -march=core2`) and
  loaded through `ctypes`. Needs NumPy for the buffers and a compiler on PATH.

Numbers from a container must be labelled as such (`docs/architecture/REFERENCE_HARDWARE.md` §4).
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from array import array
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import EXPERIMENT_DIR, ensure_paths  # noqa: E402

ensure_paths()

GOLLUM_20K = "examples/meshes/gollum_20k.obj"
DEFAULT_ASSETS = (GOLLUM_20K,)
VISIBLE_REGIONS = (1, 5, 15, 100)
SKIN_REGIONS = (5, 15, 100)
MORPH_SHARES = (15, 100)
NATIVE_SOURCE = EXPERIMENT_DIR / "kernels_native.c"
REPS = 7
#: above this share of moved vertices the NumPy variant recomputes all normals instead of gathering a 1-ring
FULL_NORMALS_SHARE = 0.25


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--assets", nargs="+", default=list(DEFAULT_ASSETS),
                        help="OBJ paths (relative to the repo root) or 'dense' (see probe_scale_audit.py)")
    parser.add_argument("--no-numpy", action="store_true", help="skip the NumPy and native columns")
    parser.add_argument("--no-native", action="store_true", help="skip the native C column")
    return parser


def timed(fn, reps: int = REPS) -> float:
    samples = []
    for _ in range(reps):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return statistics.median(samples)


def cell(value: float | None) -> str:
    return f"{'-':>10}" if value is None else f"{value:>10.3f}"


def region(mesh, share: int) -> list:
    """The lowest-Y `share` % of the points (the region rule of `probe_morph_gl.rig_region`)."""
    ids = sorted(mesh.all_vertex_ids(), key=lambda v: (mesh.vertex_position(v)[1], int(v)))
    return ids[: max(1, len(ids) * share // 100)]


def load_numpy():
    """NumPy with its runtime SIMD dispatch switched off (baseline instructions only), or (None, reason)."""
    note = ""
    if "NPY_DISABLE_CPU_FEATURES" not in os.environ:
        query = "from numpy._core._multiarray_umath import __cpu_dispatch__ as d; print(' '.join(d))"
        try:
            found = subprocess.run([sys.executable, "-c", query], capture_output=True, text=True, timeout=60)
            if found.returncode == 0 and found.stdout.strip():
                os.environ["NPY_DISABLE_CPU_FEATURES"] = found.stdout.strip()
                note = " (runtime dispatch off: baseline instructions only)"
        except Exception:  # noqa: BLE001 - the query is a convenience; the import below decides
            pass
    try:
        import numpy
    except Exception as exc:  # noqa: BLE001 - an ImportError, or the x86-64-v2 RuntimeError of the reference PC
        return None, f"NumPy not usable: {type(exc).__name__}: {exc}"
    return numpy, f"NumPy {numpy.__version__}{note}"


def load_native(np):
    """The compiled kernels as a ctypes library, or (None, reason)."""
    compiler = next((c for c in ("cc", "gcc", "clang") if shutil.which(c)), None)
    if compiler is None:
        return None, "native C skipped: no cc / gcc / clang on PATH"
    suffix = ".dll" if sys.platform == "win32" else ".so"
    target = Path(tempfile.mkdtemp(prefix="mirai_kernels_")) / f"kernels_native{suffix}"
    command = [compiler, "-O2", "-shared", "-o", str(target), str(NATIVE_SOURCE)]
    if platform.machine().lower() in ("x86_64", "amd64"):
        command.insert(2, "-march=core2")
    if sys.platform != "win32":
        command[2:2] = ["-fPIC"]
        command.append("-lm")
    try:
        subprocess.run(command, check=True, capture_output=True)
        lib = ctypes.CDLL(str(target))
    except Exception as exc:  # noqa: BLE001
        return None, f"native C skipped: {type(exc).__name__}: {exc}"
    p, i, d = ctypes.c_void_p, ctypes.c_int64, ctypes.c_double
    lib.all_normals.argtypes = [p, i, i, p, p, p, p, p, p]
    lib.patch_normals.argtypes = [p, i, i, p, p, p, p, p, p, p, i, p, p, p, p, p, p, p]
    lib.patch_normals.restype = ctypes.c_int64
    lib.lbs.argtypes = [p, p, i, p, p, p, p]
    lib.morph.argtypes = [p, p, i, p, d, p]
    lib.stencils.argtypes = [p, p, p, p, i, p]
    for fn in (lib.all_normals, lib.lbs, lib.morph, lib.stencils):
        fn.restype = None
    flags = " ".join(part for part in command[1:] if part.startswith("-") and part != "-o")
    return lib, f"native C: {compiler} {flags}, loaded through ctypes"


def ptr(a):
    return a.ctypes.data_as(ctypes.c_void_p)


# -- the flat pure-Python variant ------------------------------------------------------------------------


class FlatPython:
    """The 1-ring normal patch on int slots and flat lists: no `VertexId` dicts, no face rows."""

    def __init__(self, positions, faces) -> None:
        self.P = [tuple(p) for p in positions]
        self.F = [tuple(f) for f in faces]
        self.v2f: list[list[int]] = [[] for _ in positions]
        for i, face in enumerate(self.F):
            for v in face:
                self.v2f[v].append(i)
        self.FN = [(0.0, 0.0, 0.0)] * len(self.F)
        self.pos_mirror = array("f", [c for p in self.P for c in p])
        self.nrm_mirror = array("f", bytes(4 * 3 * len(self.P)))

    def patch(self, moved) -> tuple[bytes, bytes]:
        P, F, v2f, FN = self.P, self.F, self.v2f, self.FN
        sqrt = math.sqrt
        faces: set[int] = set()
        for v in moved:
            faces.update(v2f[v])
        verts: set[int] = set()
        for f in faces:
            verts.update(F[f])
            pts = [P[v] for v in F[f]]
            nx = ny = nz = 0.0
            for (ax, ay, az), (bx, by, bz) in zip(pts, pts[1:] + pts[:1]):
                nx += (ay - by) * (az + bz)
                ny += (az - bz) * (ax + bx)
                nz += (ax - bx) * (ay + by)
            length = sqrt(nx * nx + ny * ny + nz * nz)
            FN[f] = (0.0, 0.0, 0.0) if length < 1e-12 else (nx / length, ny / length, nz / length)
        nm, pm = self.nrm_mirror, self.pos_mirror
        for v in verts:
            x = y = z = 0.0
            for f in v2f[v]:
                fx, fy, fz = FN[f]
                x += fx
                y += fy
                z += fz
            length = sqrt(x * x + y * y + z * z)
            i = 3 * v
            if length < 1e-12:
                nm[i] = nm[i + 1] = nm[i + 2] = 0.0
            else:
                nm[i], nm[i + 1], nm[i + 2] = x / length, y / length, z / length
        for v in moved:
            i = 3 * v
            pm[i], pm[i + 1], pm[i + 2] = P[v]
        lo, hi = min(verts), max(verts) + 1
        return pm[3 * lo:3 * hi].tobytes(), nm[3 * lo:3 * hi].tobytes()


# -- the packed form (NumPy arrays; the native kernels read the same buffers) ------------------------------


class Packed:
    """Corner arrays of a polygon mesh (any face size) plus the vertex -> faces adjacency, both CSR."""

    def __init__(self, np, positions, faces) -> None:
        self.np = np
        V, F = len(positions), len(faces)
        self.V, self.F = V, F
        self.P = np.ascontiguousarray(positions, dtype=np.float64)
        sizes = np.fromiter((len(f) for f in faces), dtype=np.int64, count=F)
        self.face_ptr = np.zeros(F + 1, dtype=np.int64)
        np.cumsum(sizes, out=self.face_ptr[1:])
        corners = int(self.face_ptr[-1])
        self.cv = np.fromiter((v for f in faces for v in f), dtype=np.int32, count=corners)
        self.corner_face = np.repeat(np.arange(F, dtype=np.int32), sizes)
        nxt = np.arange(1, corners + 1, dtype=np.int64)
        nxt[self.face_ptr[1:] - 1] = self.face_ptr[:-1]
        self.corner_next = nxt
        order = np.argsort(self.cv, kind="stable")
        self.vf = np.ascontiguousarray(self.corner_face[order])
        self.vf_ptr = np.zeros(V + 1, dtype=np.int64)
        np.cumsum(np.bincount(self.cv, minlength=V), out=self.vf_ptr[1:])
        self.FN = np.zeros((F, 3))
        self.VN = np.zeros((V, 3))
        self.pos32 = self.P.astype(np.float32)
        self.nrm32 = np.zeros((V, 3), dtype=np.float32)
        # scratch of the native patch
        self.fmark, self.vmark = np.zeros(F, dtype=np.uint8), np.zeros(V, dtype=np.uint8)
        self.fscratch, self.vscratch = np.zeros(F, dtype=np.int32), np.zeros(V, dtype=np.int32)
        self.lo_hi = np.zeros(2, dtype=np.int64)

    def nbytes(self) -> int:
        return sum(a.nbytes for a in (self.P, self.face_ptr, self.cv, self.vf, self.vf_ptr, self.FN, self.VN,
                                      self.pos32, self.nrm32))

    def _unit(self, n):
        np = self.np
        length = np.sqrt((n * n).sum(axis=1))
        np.divide(n, length[:, None], out=n, where=length[:, None] >= 1e-12)
        n[length < 1e-12] = 0.0
        return n

    def _terms(self, corners):
        a = self.P[self.cv[corners]]
        b = self.P[self.cv[self.corner_next[corners]]]
        d, s = a - b, a + b
        return self.np.stack((d[:, 1] * s[:, 2], d[:, 2] * s[:, 0], d[:, 0] * s[:, 1]), axis=1)

    def numpy_all_normals(self) -> None:
        np = self.np
        terms = self._terms(np.arange(len(self.cv)))
        self.FN = self._unit(np.add.reduceat(terms, self.face_ptr[:-1], axis=0))
        self.VN = self._unit(np.add.reduceat(self.FN[self.vf], self.vf_ptr[:-1], axis=0))

    def _rows(self, ptr_array, items):
        """The CSR positions of `items` rows, concatenated, and each row's start in that list."""
        np = self.np
        counts = ptr_array[items + 1] - ptr_array[items]
        starts = np.zeros(len(items), dtype=np.int64)
        np.cumsum(counts[:-1], out=starts[1:])
        where = np.repeat(ptr_array[items] - starts, counts) + np.arange(int(counts.sum()))
        return where, starts

    def numpy_patch(self, moved) -> tuple[bytes, bytes]:
        """The `RenderMesh._sync_geometry` neighbourhood, O(touched): faces of the moved vertices, then the
        vertices of those faces, their normals from the incident faces."""
        np = self.np
        if len(moved) > FULL_NORMALS_SHARE * self.V:
            self.numpy_all_normals()  # a whole-mesh pass is cheaper than gathering most of the mesh
            return self.P.astype(np.float32).tobytes(), self.VN.astype(np.float32).tobytes()
        where, _ = self._rows(self.vf_ptr, moved)
        faces = np.unique(self.vf[where])
        corners, starts = self._rows(self.face_ptr, faces)
        self.FN[faces] = self._unit(np.add.reduceat(self._terms(corners), starts, axis=0))
        verts = np.unique(self.cv[corners])
        where, starts = self._rows(self.vf_ptr, verts)
        self.VN[verts] = self._unit(np.add.reduceat(self.FN[self.vf[where]], starts, axis=0))
        lo, hi = int(verts[0]), int(verts[-1]) + 1
        return self.P[lo:hi].astype(np.float32).tobytes(), self.VN[lo:hi].astype(np.float32).tobytes()

    def native_all_normals(self, lib) -> None:
        lib.all_normals(ptr(self.P), self.V, self.F, ptr(self.face_ptr), ptr(self.cv), ptr(self.vf_ptr),
                        ptr(self.vf), ptr(self.FN), ptr(self.VN))

    def native_patch(self, lib, moved) -> tuple[bytes, bytes]:
        lib.patch_normals(ptr(self.P), self.V, self.F, ptr(self.face_ptr), ptr(self.cv), ptr(self.vf_ptr),
                          ptr(self.vf), ptr(self.FN), ptr(self.VN), ptr(moved), len(moved), ptr(self.fmark),
                          ptr(self.vmark), ptr(self.fscratch), ptr(self.vscratch), ptr(self.pos32),
                          ptr(self.nrm32), ptr(self.lo_hi))
        lo, hi = int(self.lo_hi[0]), int(self.lo_hi[1])
        return self.pos32[lo:hi].tobytes(), self.nrm32[lo:hi].tobytes()


# -- blocks ----------------------------------------------------------------------------------------------


def visible_block(mesh, positions, faces, render_mesh, np, lib, packed) -> list[str]:
    vids = mesh.all_vertex_ids()
    index = {v: i for i, v in enumerate(vids)}
    flat = FlatPython(positions, faces)
    lines = ["-- visible: 1-ring normals + buffer data for a moved region, ms per step (CPU side, no upload)",
             f"{'region':>8} {'V moved':>8} | {'production':>10} {'flat Py':>10} {'NumPy':>10} {'native C':>10}"]
    if packed is not None:
        packed.numpy_all_normals()
        normals = render_mesh.derived.vertex_normals
        worst = max(max(abs(a - b) for a, b in zip(normals[v], packed.VN[i])) for v, i in index.items())
        lines.insert(1, f"   check: max |production vertex normal - packed| = {worst:.1e}; all normals of the "
                        f"mesh: NumPy {timed(packed.numpy_all_normals):.2f} ms"
                        + ("" if lib is None else f", native C {timed(lambda: packed.native_all_normals(lib)):.3f} ms"))
    for share in VISIBLE_REGIONS:
        moved_ids = set(region(mesh, share))
        slots = sorted(index[v] for v in moved_ids)

        def production() -> None:
            render_mesh.mark_vertices_dirty(moved_ids)
            render_mesh.sync()

        numpy_ms = native_ms = None
        if packed is not None:
            moved = np.asarray(slots, dtype=np.int64)
            numpy_ms = timed(lambda: packed.numpy_patch(moved))
            if lib is not None:
                native_ms = timed(lambda: packed.native_patch(lib, moved))
        lines.append(f"{share:>6} % {len(slots):>8} | {timed(production, 5):>10.2f} "
                     f"{timed(lambda: flat.patch(slots), 5):>10.2f} {cell(numpy_ms)} {cell(native_ms)}")
    return lines


def skin_block(positions, faces, np, lib) -> list[str]:
    from core import PointLayerInfo
    from core.mesh import LayerKind
    from core.rig import Rig
    from mirai.scene_factory import mesh_from_positions_and_faces
    from mirai.skinning import BonePose, SkinSurface, _flat, object_transforms, skin_transforms

    def rot_x(angle: float):
        c, s = math.cos(angle), math.sin(angle)
        return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))

    lines = ["-- skin: linear blend skinning of a weighted region, ms per pose step (evaluation only)",
             f"{'region':>8} {'V':>8} | {'production':>10} {'NumPy':>10} {'native C':>10}   max diff"]
    for share in SKIN_REGIONS:
        mesh = mesh_from_positions_and_faces(positions, faces)
        reg = region(mesh, share)
        pts = [mesh.vertex_position(v) for v in reg]
        centre = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
        top, low = max(p[1] for p in pts), min(p[1] for p in pts)
        span = max(top - low, 1e-3)
        rig, jaw = Rig().with_new_bone("Jaw", (centre[0], top + 0.3 * span, centre[2]), centre)
        rig, tip = rig.with_new_bone("Tip", centre, (centre[0], low, centre[2] + 0.2 * span), parent=jaw)
        lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
        full = len(reg) * 70 // 100
        for i, v in enumerate(reg):
            mesh.set_layer_value(lid, v, ((int(jaw), 1.0),) if i < full else ((int(jaw), 0.5), (int(tip), 0.5)))
        surface = SkinSurface(mesh, mesh)
        poses = [{jaw: BonePose(rotation=rot_x(0.01 * (k + 1)))} for k in range(REPS + 2)]
        surface.update(rig, poses[0], None)
        steps = iter(poses[1:])
        production = timed(lambda: surface.update(rig, next(steps), None), REPS)
        last = poses[REPS]
        numpy_ms = native_ms = diff = None
        if np is not None:
            ids = mesh.all_vertex_ids()
            index = {v: i for i, v in enumerate(ids)}
            rows = np.fromiter((index[v] for v in reg), dtype=np.int64)
            keys = np.full((len(reg), 4), -1, dtype=np.int32)
            weights = np.zeros((len(reg), 4))
            for r, v in enumerate(reg):
                for k, (key, w) in enumerate(mesh.layer_value(lid, v)):
                    keys[r, k], weights[r, k] = key, w
            rest = np.ascontiguousarray([mesh.vertex_position(v) for v in ids])
            out = rest.copy()
            safe_keys = np.where(keys < 0, 0, keys)

            def matrices():
                flat = _flat(object_transforms(skin_transforms(rig, last), None))
                a = np.zeros((max(flat) + 1, 12))
                for key, row in flat.items():
                    a[key] = row
                return a

            def with_numpy() -> None:
                a = matrices().reshape(-1, 3, 4)[safe_keys]
                p = rest[rows]
                posed = np.einsum("nkij,nj->nki", a[..., :3], p) + a[..., 3]
                out[rows] = np.einsum("nk,nki->ni", weights, posed) + (1.0 - weights.sum(axis=1))[:, None] * p

            with_numpy()
            diff = max(max(abs(a - b) for a, b in zip(surface.mesh.vertex_position(v), out[index[v]])) for v in reg)
            numpy_ms = timed(with_numpy)
            if lib is not None:
                def with_native() -> None:
                    a = matrices()
                    lib.lbs(ptr(rest), ptr(rows), len(rows), ptr(keys), ptr(weights), ptr(a), ptr(out))

                with_native()
                diff = max(diff, max(
                    max(abs(a - b) for a, b in zip(surface.mesh.vertex_position(v), out[index[v]])) for v in reg))
                native_ms = timed(with_native)
        lines.append(f"{share:>6} % {len(reg):>8} | {production:>10.2f} {cell(numpy_ms)} {cell(native_ms)}   "
                     + ("-" if diff is None else f"{diff:.1e}"))
        surface.close()
    return lines


def morph_block(positions, faces, np, lib) -> list[str]:
    from core import PointLayerInfo
    from mirai.morph_mix import MixSurface
    from mirai.scene_factory import mesh_from_positions_and_faces

    lines = ["-- morph: one weight step of one target, ms (evaluation only)",
             f"{'offsets':>8} {'V':>8} | {'production':>10} {'NumPy':>10} {'native C':>10}   max diff"]
    for share in MORPH_SHARES:
        mesh = mesh_from_positions_and_faces(positions, faces)
        reg = region(mesh, share)
        lid = mesh.add_point_layer(PointLayerInfo("T"))
        for i, v in enumerate(reg):
            mesh.set_layer_value(lid, v, (0.0, 0.01 + 1e-6 * (i % 7), 0.02))
        mix = MixSurface(mesh)
        mix.update({lid: 40})
        weights = iter(range(41, 42 + REPS))
        production = timed(lambda: mix.update({lid: next(weights)}), REPS)
        last = (40 + REPS) / 100.0
        numpy_ms = native_ms = diff = None
        if np is not None:
            ids = mesh.all_vertex_ids()
            index = {v: i for i, v in enumerate(ids)}
            rows = np.fromiter((index[v] for v in reg), dtype=np.int64)
            offsets = np.ascontiguousarray([mesh.layer_value(lid, v) for v in reg])
            base = np.ascontiguousarray([mesh.vertex_position(v) for v in ids])
            shown = base.copy()

            def with_numpy() -> None:
                shown[rows] = base[rows] + last * offsets

            with_numpy()
            diff = max(max(abs(a - b) for a, b in zip(mix.mesh.vertex_position(v), shown[index[v]])) for v in reg)
            numpy_ms = timed(with_numpy)
            if lib is not None:
                native_ms = timed(lambda: lib.morph(ptr(base), ptr(rows), len(rows), ptr(offsets), last, ptr(shown)))
        lines.append(f"{share:>6} % {len(reg):>8} | {production:>10.2f} {cell(numpy_ms)} {cell(native_ms)}   "
                     + ("-" if diff is None else f"{diff:.1e}"))
        mix.close()
    return lines


def subd_block(mesh, np, lib) -> list[str]:
    from mirai.subdivision.catmull_clark import SubdSurface, SubdUnsupportedError

    start = time.perf_counter()
    try:
        surface = SubdSurface(mesh)
        level = surface.level(1)
    except SubdUnsupportedError as exc:
        return [f"-- subd: refused ({exc})"]
    build = time.perf_counter() - start
    control = [mesh.vertex_position(v) for v in surface.topology.vertex_ids]
    production = timed(lambda: level.apply_full(control), 3)
    numpy_ms = native_ms = diff = None
    if np is not None:
        sp = np.zeros(len(level.stencils) + 1, dtype=np.int64)
        np.cumsum([len(ix) for ix, _ in level.stencils], out=sp[1:])
        entries = int(sp[-1])
        idx = np.fromiter((i for ix, _ in level.stencils for i in ix), dtype=np.int32, count=entries)
        w = np.fromiter((x for _, ws in level.stencils for x in ws), dtype=np.float64, count=entries)
        cp = np.ascontiguousarray(control)
        reference = np.asarray(level.apply_full(control))
        diff = float(np.abs(reference - np.add.reduceat(w[:, None] * cp[idx], sp[:-1], axis=0)).max())
        numpy_ms = timed(lambda: np.add.reduceat(w[:, None] * cp[idx], sp[:-1], axis=0))
        if lib is not None:
            out = np.zeros((level.n_verts, 3))
            lib.stencils(ptr(cp), ptr(sp), ptr(idx), ptr(w), level.n_verts, ptr(out))
            diff = max(diff, float(np.abs(reference - out).max()))
            native_ms = timed(lambda: lib.stencils(ptr(cp), ptr(sp), ptr(idx), ptr(w), level.n_verts, ptr(out)))
    return [
        f"-- subd: level 1 of this mesh as the cage = {level.n_verts} V / {len(level.faces)} F, "
        f"{level.stencil_entries} stencil entries; topology + stencil build {build:.2f} s",
        f"{'':>17} | {'production':>10} {'NumPy':>10} {'native C':>10}   max diff",
        f"{'apply_full':>17} | {production:>10.2f} {cell(numpy_ms)} {cell(native_ms)}   "
        + ("-" if diff is None else f"{diff:.1e}"),
    ]


def run_asset(path: Path, np, lib) -> list[str]:
    from core import Mesh
    from loaders.obj_loader import load_obj
    from mirai.scene_factory import mesh_from_positions_and_faces
    from viewport.render_mesh import RenderMesh
    from viewport.resource_store import TraceStore

    data = load_obj(path)
    positions, faces = data.vertices, data.faces
    lines = ["", f"=== {path.name}: {len(positions)} V, {len(faces)} F ==="]
    gc.collect()
    start = time.perf_counter()
    mesh = mesh_from_positions_and_faces(positions, faces)
    built = time.perf_counter()
    render_mesh = RenderMesh(mesh, store_type=TraceStore)
    rendered = time.perf_counter()
    state = mesh.export_state()
    exported = time.perf_counter()
    Mesh.from_state(state)
    loaded = time.perf_counter()
    del state
    lines.append(f"production, once: core.Mesh from arrays {(built - start) * 1000:.0f} ms, RenderMesh full build "
                 f"{(rendered - built) * 1000:.0f} ms, export_state {(exported - rendered) * 1000:.0f} ms, "
                 f"Mesh.from_state {(loaded - exported) * 1000:.0f} ms")
    packed = None
    if np is not None:
        start = time.perf_counter()
        packed = Packed(np, positions, faces)
        packed.numpy_all_normals()
        lines.append(f"packed, once: arrays + adjacency + all normals {(time.perf_counter() - start) * 1000:.0f} ms, "
                     f"{packed.nbytes() / 2**20:.1f} MiB")
    lines += visible_block(mesh, positions, faces, render_mesh, np, lib, packed)
    lines += skin_block(positions, faces, np, lib)
    lines += morph_block(positions, faces, np, lib)
    lines += subd_block(mesh, np, lib)
    return lines


def main(argv: list[str] | None = None) -> int:
    from drag_cost.probe_drag_gl import cpu_name
    from drag_cost.probe_scale_audit import resolve_asset

    args = build_parser().parse_args(argv)
    np, numpy_note = (None, "NumPy skipped (--no-numpy)") if args.no_numpy else load_numpy()
    lib, native_note = None, "native C skipped (needs NumPy for the buffers)"
    if np is not None:
        lib, native_note = (None, "native C skipped (--no-native)") if args.no_native else load_native(np)
    print("Kernel probe (2026-11-10): production code vs. packed arrays, CPU side only")
    print(f"Platform: {platform.platform()}")
    print(f"CPU: {cpu_name()} ({os.cpu_count()} logical cores)")
    print(f"Python: {platform.python_version()} ({platform.python_implementation()})")
    print(numpy_note)
    print(native_note)
    for name in args.assets:
        for line in run_asset(resolve_asset(name), np, lib):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
