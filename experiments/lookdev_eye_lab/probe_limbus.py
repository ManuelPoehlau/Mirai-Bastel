"""P1c soft-limbus probe (2026-11-14): parity, L0 = P1b identity, edge continuity numbers, GPU timings, contact sheet.

Sections:
- [P] parity: every function of `limbus_shaders.LIMBUS_LIB_SRC` against `limbus_model` (float32 inputs);
- [I] identity: L0 renders P1b V2 / V3 pixel for pixel (every technique T-B ... T-D, every view of the run);
- [C] continuity (numbers, no verdict): along 64 radial lines across the limbus ring (1.5 mm each side, on the
      analytic surfaces, front-facing samples only) the largest luminance step between neighbouring samples (0.05 mm
      apart), median / p95 over the lines, per level and view; plus a key-light sweep (azimuth -60 ... +60) in the 3/4
      view, where the highlight crosses the ring;
- [V] GPU time per frame per run (GL_TIME_ELAPSED, runs interleaved, as P1 / P1b);
- contact sheet: limbus crops, columns L0 | L1 | L2 | L3 | L3 + asymmetry | L3 image colour | L2 + overlap 0.3 mm |
  L2 + overlap 0.3 mm + asymmetry, rows front / 3/4 /
  profile / steep 75 / 3/4 with the key at azimuth -45 (the highlight on the ring);
- [R] resources and GL state left as found.
Every run uses the same lighting, exposure and camera per view (the lab defaults; printed in the header).
"""

from __future__ import annotations

import argparse
import math
import statistics
import traceback
from pathlib import Path

import numpy as np

from lookdev_gpu_probe import cube_math as cm
from lookdev_gpu_probe import probe_gl_caps as pg

from . import cornea_optics as co
from . import eye_geometry as geo
from . import gl_lab
from . import lab_scene
from . import lab_state as ls
from . import limbus_gl as lg
from . import limbus_model as lm
from . import limbus_parity as lp
from . import probe_eye
from . import refraction_gl as rg
from .probe_refraction import STEEP_VIEW, project
from ._paths import CACHE_DIR, OUT_DIR

PROBE_NAME = "Lookdev P1c soft limbus probe (2026-11-14)"
SHOT_SIZE = (1024, 768)
#: (technique, refraction, level, asymmetry, colour source[, overlap all round mm])
RUNS = (("T-C", "V2", "L0", False, "shader"), ("T-C", "V2", "L1", False, "shader"),
        ("T-C", "V2", "L2", False, "shader"), ("T-C", "V2", "L3", False, "shader"),
        ("T-C", "V2", "L3", True, "shader"), ("T-C", "V3", "L0", False, "shader"),
        ("T-C", "V3", "L3", False, "shader"), ("T-B", "V2", "L0", False, "shader"),
        ("T-B", "V2", "L3", False, "shader"), ("T-D", "V2", "L0", False, "shader"),
        ("T-D", "V2", "L3", False, "shader"), ("T-C", "V2", "L3", True, "shader", 0.3))
SHEET_RUNS = (("T-C", "V2", "L0", False, "shader"), ("T-C", "V2", "L1", False, "shader"),
              ("T-C", "V2", "L2", False, "shader"), ("T-C", "V2", "L3", False, "shader"),
              ("T-C", "V2", "L3", True, "shader"), ("T-C", "V2", "L3", False, "image"),
              ("T-C", "V2", "L2", False, "shader", 0.3), ("T-C", "V2", "L2", True, "shader", 0.3))
SWEEP_AZIMUTHS = (-60.0, -45.0, -30.0, -15.0, 0.0, 15.0, 30.0, 45.0, 60.0)
SHEET_KEY_AZIMUTH = -45.0
LINES, HALF_MM, STEP_MM = 64, 1.5, 0.05


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=PROBE_NAME)
    p.add_argument("--draws", type=int, default=probe_eye.DEFAULT_DRAWS)
    p.add_argument("--sizes", nargs="+", default=[f"{w}x{h}" for w, h in probe_eye.SIZES])
    p.add_argument("--views", nargs="+", default=list(ls.VIEW_ORDER), choices=ls.VIEW_ORDER)
    p.add_argument("--images", default=str(OUT_DIR / "limbus"), help="folder for screenshots ('' = none)")
    return p


def name_of(run) -> str:
    tech, refraction, level, asym, source = run[:5]
    overlap = run[5] if len(run) > 5 else 0.0
    return (f"{tech} {refraction} {level}" + (f" ov{overlap:g}" if overlap else "") + (" asym" if asym else "")
            + (" imgcol" if source == "image" else ""))


def apply_run(state: lg.LimbusState, run) -> None:
    state.technique, state.refraction, state.limbus_level, state.asym, state.colour_source = run[:5]
    state.overlap_mm = run[5] if len(run) > 5 else 0.0


def limbus_crop(camera, image: np.ndarray, scale: float = 1.35) -> np.ndarray:
    """A square crop around the limbus ring (its vertical extent x `scale`), clamped to the frame."""
    h, w = image.shape[:2]
    cx, cy, _ = project(camera, (0.0, 0.0, geo.LIMBUS_Z), w, h)
    _ux, uy, _ = project(camera, (0.0, geo.LIMBUS_RADIUS, geo.LIMBUS_Z), w, h)
    half = max(8, min(int(abs(uy - cy) * scale), h // 2, w // 2))
    x0 = int(np.clip(round(cx) - half, 0, w - 2 * half))
    y0 = int(np.clip(round(cy) - half, 0, h - 2 * half))
    return image[y0:y0 + 2 * half, x0:x0 + 2 * half]


def radial_samples(lines: int = LINES, half_mm: float = HALF_MM, step_mm: float = STEP_MM) -> np.ndarray:
    """(lines, samples, 3) world points across the ring: on the anterior cornea from `half_mm` inside the ring to the
    ring, then on the sclera along the sphere to `half_mm` outside (the limbus coordinate u from -half to +half)."""
    g = co.GEOMETRY
    u = np.arange(-half_mm, half_mm + 1e-9, step_mm) * lm.MM
    phi = np.linspace(0.0, 2.0 * math.pi, lines, endpoint=False)
    r_in = lm.RING_RADIUS + np.minimum(u, 0.0)
    z_in = g.anterior_z(r_in)
    theta = lm.THETA_RING + np.maximum(u, 0.0) / geo.SCLERA_RADIUS
    r_out, z_out = np.sin(theta) * geo.SCLERA_RADIUS, np.cos(theta) * geo.SCLERA_RADIUS
    r = np.where(u < 0.0, r_in, r_out)
    z = np.where(u < 0.0, z_in, z_out)
    return np.stack([r[None, :] * np.cos(phi)[:, None], r[None, :] * np.sin(phi)[:, None],
                     np.broadcast_to(z, (lines, len(u)))], -1)


def continuity(camera, image: np.ndarray) -> tuple[float, float, int, float]:
    """(median, p95 of the per-line largest luminance step, lines used, median position of that step in mm from the
    ring). Lines with a back-facing or off-frame sample are skipped."""
    h, w = image.shape[:2]
    pts = radial_samples()
    eye = np.asarray(camera.eye(), dtype=np.float64)
    normals = np.where((lm.cornea_u(pts) < 0.0)[..., None],
                       co.normalize(pts - np.array([0.0, 0.0, co.GEOMETRY.anterior_centre_z])), co.normalize(pts))
    facing = np.sum(normals * co.normalize(eye - pts), axis=-1) > 0.15
    lum = image.astype(np.float64) @ np.array([0.2126, 0.7152, 0.0722])
    steps, where = [], []
    u_mm = np.arange(-HALF_MM, HALF_MM + 1e-9, STEP_MM)
    for line, ok in zip(pts, facing):
        if not ok.all():
            continue
        xy = np.array([project(camera, p, w, h)[:2] for p in line])
        col, row = np.round(xy[:, 0]).astype(int), np.round(xy[:, 1]).astype(int)
        if col.min() < 0 or row.min() < 0 or col.max() >= w or row.max() >= h:
            continue
        jumps = np.abs(np.diff(lum[row, col]))
        steps.append(float(jumps.max()))
        k = int(np.argmax(jumps))
        where.append(0.5 * (u_mm[k] + u_mm[k + 1]))
    if not steps:
        return float("nan"), float("nan"), 0, float("nan")
    return float(np.median(steps)), float(np.percentile(steps, 95)), len(steps), float(np.median(where))


class LimbusProbe(probe_eye.Probe):
    def header(self) -> None:
        super().header()
        self.lines[0] = f"{PROBE_NAME}: parity, L0 identity, continuity, timings, contact sheet"

    def parity(self, res: pg.Resources) -> None:
        pp = lg.LimbusParityPass(self.gl, res, lp.PARAMS)
        self.add(f"[P] limbus GLSL vs limbus_model (limbus_parity.py, float32 inputs; read-back {pp.status})")
        self.add(f"  {'function':<16} {'max abs err':>12} {'failed':>7} {'compared':>9} {'tolerance':>12}")
        ok = True
        for case in lp.cases():
            err, bad, compared = lp.errors(case, pp.run(case.func, case.inputs))
            ok &= bad == 0 and compared > 0.9 * len(case.inputs)
            self.add(f"  {case.func:<16} {err:>12.3g} {bad:>7} {compared:>9} {case.abs_tol:>12g}")
        errors = pg.drain_errors(self.gl)
        pp.release()
        status = cm.PASS if ok and not errors else cm.FAIL
        self.add(f"  -> {status}{'; GL errors ' + ', '.join(errors) if errors else ''}")
        self.verdict("P limbus parity", status)
        self.add("")

    def identity(self, scene, refr, res: pg.Resources) -> None:
        width, height = 480, 360
        target = gl_lab.Target(self.gl, res, width, height)
        self.add(f"[I] L0 against P1b ({width}x{height}, every technique T-B ... T-D, V2 and V3, every view)")
        bad = []
        for tech in ("T-B", "T-C", "T-D"):
            for refraction in ("V2", "V3"):
                for view in self.args.views:
                    images = []
                    for s in (refr, scene):
                        s.renderer.state.technique, s.renderer.state.refraction = tech, refraction
                        s.apply_view(view, lab_scene.close_up_distance(width, height))
                        s.set_aspect(width, height)
                        s.camera_moved()
                        self._frame(s, target)
                        images.append(target.read_rgb())
                    if not np.array_equal(*images):
                        bad.append(f"{tech} {refraction} {view} ({int(np.sum(np.any(images[0] != images[1], -1)))} px)")
        target.release()
        status = cm.PASS if not bad else cm.FAIL
        self.add(f"  differing: {', '.join(bad) or 'none'}  -> {status}")
        self.verdict("I L0 = P1b pixel for pixel", status)
        self.add("")

    def continuity_section(self, scene, res: pg.Resources) -> None:
        width, height = SHOT_SIZE
        state = scene.renderer.state
        target = gl_lab.Target(self.gl, res, width, height)
        distance = lab_scene.close_up_distance(width, height)
        self.add(f"[C] continuity across the ring ({width}x{height}, eye ~50 %, T-C V2): largest luminance step "
                 f"(0..255) between samples {STEP_MM} mm apart within +-{HALF_MM} mm, per radial line; median / p95 "
                 f"over the lines, @ = median position of that step in mm from the ring (- = cornea side; the chamber "
                 f"angle is at {lm.U0 / lm.MM:+.2f}); n = lines fully facing the camera (0: none, e.g. profile). "
                 f"Numbers only - no verdict.")
        runs = [r for r in SHEET_RUNS]
        self.add(f"  {'view':<16}" + "".join(f"{name_of(r)[7:]:>22}" for r in runs))
        views = [(v, *ls.VIEWS[v]) for v in self.args.views] + [STEEP_VIEW]
        for name, yaw, pitch in views:
            scene.camera.set_view(math.radians(yaw), math.radians(pitch))
            scene.camera.distance = distance
            scene.set_aspect(width, height)
            scene.camera_moved()
            cells = []
            for run in runs:
                apply_run(state, run)
                self._frame(scene, target)
                med, p95, n, at = continuity(scene.camera, target.read_rgb())
                cells.append(f"{med:5.1f}/{p95:5.1f} @{at:+5.2f} n{n:<2d}")
            self.add(f"  {name:<16}" + "".join(f"{c:>22}" for c in cells))
        yaw, pitch = ls.VIEWS["three_quarter"]
        scene.camera.set_view(math.radians(yaw), math.radians(pitch))
        scene.camera.distance = distance
        scene.camera_moved()
        az0 = state.key_azimuth
        self.add(f"  key sweep, 3/4 view: per azimuth the p95 step (T-C V2)")
        self.add(f"  {'azimuth':<16}" + "".join(f"{name_of(r)[7:]:>16}" for r in runs[:4]))
        for az in SWEEP_AZIMUTHS:
            state.key_azimuth = az
            cells = []
            for run in runs[:4]:
                apply_run(state, run)
                self._frame(scene, target)
                cells.append(f"{continuity(scene.camera, target.read_rgb())[1]:5.1f}")
            self.add(f"  {az:<16.0f}" + "".join(f"{c:>16}" for c in cells))
        state.key_azimuth = az0
        target.release()
        self.add("")

    def timings(self, scene, res: pg.Resources) -> None:
        gl = self.gl
        state = scene.renderer.state
        self.query = res.query()
        self.add(f"[V] GPU time per frame (clear + background + eye), eye ~50 % of the frame, {self.args.draws} frames "
                 f"after {probe_eye.WARMUP}, runs interleaved; ms")
        for text in self.args.sizes:
            width, height = pg.parse_size(text)
            target = gl_lab.Target(gl, res, width, height)
            distance = lab_scene.close_up_distance(width, height)
            self.add(f"  {width}x{height}: target {target.status}")
            for view in self.args.views:
                scene.apply_view(view, distance)
                scene.set_aspect(width, height)
                scene.camera_moved()
                gpu = {run: [] for run in RUNS}
                cpu = {run: [] for run in RUNS}
                errors = {run: [] for run in RUNS}
                for round_ in range(probe_eye.WARMUP + self.args.draws):
                    for run in RUNS:
                        apply_run(state, run)
                        g, c = self._frame(scene, target)
                        errors[run] += pg.drain_errors(gl)
                        if round_ >= probe_eye.WARMUP:
                            gpu[run].append(g)
                            cpu[run].append(c)
                self.add(f"    view {view}")
                self.add(f"    {'run':<22} {'GPU p50':>8} {'p95':>8} {'min':>8} {'max':>8} {'CPU p50':>8}  GL errors")
                for run in RUNS:
                    self.add(f"    {name_of(run):<22} {probe_eye._rows_ms(gpu[run])} "
                             f"{statistics.median(cpu[run]):8.2f}  {', '.join(sorted(set(errors[run]))) or 'none'}")
                    if errors[run]:
                        self.verdict(f"V GL errors {name_of(run)} {view} {text}", cm.FAIL)
            target.release()
        if not any(check.startswith("V ") for check, _ in self.verdicts):
            self.verdict("V every run renders without GL error", cm.PASS)
        self.add("")

    def sheet(self, scene, res: pg.Resources) -> None:
        folder = Path(self.args.images)
        folder.mkdir(parents=True, exist_ok=True)
        width, height = SHOT_SIZE
        state = scene.renderer.state
        target = gl_lab.Target(self.gl, res, width, height)
        distance = lab_scene.close_up_distance(width, height)
        rows = []
        views = [(v, *ls.VIEWS[v], None) for v in self.args.views] + [(*STEEP_VIEW, None)]
        views.append(("three_quarter_key-45", *ls.VIEWS["three_quarter"], SHEET_KEY_AZIMUTH))
        az0 = state.key_azimuth
        for name, yaw, pitch, key_az in views:
            scene.camera.set_view(math.radians(yaw), math.radians(pitch))
            scene.camera.distance = distance
            scene.set_aspect(width, height)
            scene.camera_moved()
            state.key_azimuth = az0 if key_az is None else key_az
            crops = []
            for run in SHEET_RUNS:
                apply_run(state, run)
                self._frame(scene, target)
                img = target.read_rgb()
                cm.write_png(folder / f"limbus_{name}_{name_of(run).replace(' ', '_')}.png", img / 255.0)
                crop = limbus_crop(scene.camera, img)
                size = 400
                idx = (np.arange(size) * crop.shape[0] / size).astype(int)
                crops.append(crop[idx][:, idx])
            rows.append(np.concatenate(crops, axis=1))
        state.key_azimuth = az0
        target.release()
        cm.write_png(folder / "limbus_sheet.png", np.concatenate(rows, axis=0) / 255.0)
        self.add(f"Screenshots: {folder} - limbus_<view>_<run>.png ({width}x{height}); limbus_sheet.png: limbus crops "
                 "400^2, columns " + " | ".join(name_of(r) for r in SHEET_RUNS) + "; rows "
                 + " / ".join(v[0] for v in views))
        self.add("")


def run(args) -> list[str]:
    probe = LimbusProbe(args)
    gl = probe.gl
    probe.header()
    before = pg.snapshot(gl)
    state = lg.LimbusState(show_references=False)
    scene = refr = None
    res = pg.Resources(gl)
    try:
        scene = lg.build_scene(state, OUT_DIR, CACHE_DIR, *SHOT_SIZE)
        refr = rg.build_scene(rg.RefractionState(show_references=False, refraction="V2"), OUT_DIR, CACHE_DIR,
                              *SHOT_SIZE)
        s = state
        probe.add(scene.iris_source.describe())
        probe.add(f"Lighting / camera for every run: key az {s.key_azimuth:g} el {s.key_elevation:g} E "
                  f"{s.key_intensity:g}, environment {'on' if s.env_on else 'off'} yaw {s.env_yaw:g} x{s.env_intensity:g}, "
                  f"exposure {s.exposure_ev:+g} EV, tonemap {s.tonemap}; close-up distance per frame size")
        for line in lg.describe(state, scene.renderer):
            probe.add(line)
        probe.add("")
        probe.query = res.query()
        probe.guarded("P", probe.parity, res)
        probe.guarded("I", probe.identity, scene, refr, scene.renderer.res)
        probe.guarded("C", probe.continuity_section, scene, scene.renderer.res)
        probe.guarded("V", probe.timings, scene, scene.renderer.res)
        if args.images:
            probe.guarded("S", probe.sheet, scene, scene.renderer.res)
    except Exception:  # noqa: BLE001
        probe.failures.append("setup")
        probe.add("ERROR in setup:")
        probe.add("  " + traceback.format_exc().strip().replace("\n", "\n  "))
    finally:
        made, leaks_scene = "", []
        for s in (scene, refr):
            if s is not None:
                made += s.renderer.res.counts() + " "
                leaks_scene.append(s.renderer.res)
                s.release()
        res.release_all()
        gl.glFinish()
        pg.restore(gl, before)
        gl.glClearColor(*before["GL_COLOR_CLEAR_VALUE"])
        gl.glDepthMask(gl.GL_TRUE)
        leaks = res.leaks() + [x for r in leaks_scene for x in r.leaks()]
        diff = cm.state_diff(before, pg.snapshot(gl))
        final_errors = pg.drain_errors(gl)
        probe.window.close()
    hygiene = cm.PASS if not leaks and not diff and not final_errors else cm.FAIL
    probe.add("[R] resources and GL state")
    probe.add(f"  lab objects: {made.strip() or 'none'}; probe objects: {res.counts() or 'none'}")
    probe.add(f"  still alive after release: {', '.join(leaks) or 'none'}")
    probe.add(f"  GL state after vs before: {'identical' if not diff else 'DIFFERENT: ' + '; '.join(diff)}")
    probe.add(f"  glGetError at the end: {', '.join(final_errors) or 'none'}")
    probe.add(f"  -> {hygiene}")
    probe.verdict("R hygiene", hygiene)
    for title in probe.failures:
        probe.verdict(f"ERROR {title}", cm.FAIL)
    probe.add("")
    probe.add("Summary (raw verdicts - label them by machine in the results file):")
    for check, status in probe.verdicts:
        probe.add(f"  {status:<5} {check}")
    return probe.lines


def quick_args(images: str = "") -> argparse.Namespace:
    return build_parser().parse_args(["--draws", "2", "--sizes", "320x240", "--views", "front", "three_quarter",
                                      "--images", images])


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for line in run(args):
        print(line, flush=True)
    return 0
