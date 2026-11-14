"""P1b probe: corneal refraction on the GPU (2026-11-14). `run_refraction.py --probe` runs it.

Sections (plain ASCII, the header as P1's probe):
- [M] the CPU ray model (`optics_report.report`): geometry, magnification, virtual pupil, visibility, per-view pixel
      displacements V1 / V2 / V3 (skip with --no-optics; it takes a while on an old CPU);
- [P] parity: every ray function of `refraction_shaders.REFRACTION_LIB_SRC` against `cornea_optics` (float32 inputs);
- [K] the GPU's per-pixel ray class (iris / pupil / limbal tissue, `DEBUG_KIND`) against the CPU model's, per view;
- [D] the opaque cornea pass: GL state after it (blend off, depth mask on), the depth it writes at the cornea's centre
      against the analytic anterior surface and the iris behind it, an identical image with the iris mesh drawn under
      it, and the image with the eye's parts drawn in reverse order;
- [V] GPU time per frame (clear + background + eye, eye ~50 % of the frame), 1024x768 and 1920x1080, three views:
      T-C V1 C2 (P1's baseline) and V1 C1, T-C / T-B / T-D x V2 / V3, background alone;
- screenshots: the three views per variant, contact sheets (cornea crop: V1 | V2 | V3 | |V3 - V2| x 8);
- [R] hygiene.
"""

from __future__ import annotations

import argparse
import statistics
import sys
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
from . import optics_report
from . import probe_eye
from . import refraction_gl as rg
from . import refraction_parity as rp
from ._paths import CACHE_DIR, OUT_DIR

PROBE_NAME = "Lookdev P1b corneal refraction probe (2026-11-14)"
SHOT_SIZE = (1024, 768)
#: (technique, refraction, cornea treatment for V1)
RUNS = (("T-C", "V1", "C2"), ("T-C", "V1", "C1"), ("T-C", "V2", "C2"), ("T-C", "V3", "C2"),
        ("T-B", "V2", "C2"), ("T-B", "V3", "C2"), ("T-D", "V2", "C2"), ("T-D", "V3", "C2"))
SHEET_RUNS = (("T-C", "V1", "C2"), ("T-C", "V2", "C2"), ("T-C", "V3", "C2"))
#: A supplementary view between 3/4 and profile (yaw, pitch): at the profile preset (90 degrees) and close-up distance
#: no ray through the cornea reaches the iris in any variant; refraction matters most just before that.
STEEP_VIEW = ("steep_75", 75.0, 0.0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=PROBE_NAME)
    p.add_argument("--draws", type=int, default=probe_eye.DEFAULT_DRAWS)
    p.add_argument("--sizes", nargs="+", default=[f"{w}x{h}" for w, h in probe_eye.SIZES])
    p.add_argument("--views", nargs="+", default=list(ls.VIEW_ORDER), choices=ls.VIEW_ORDER)
    p.add_argument("--images", default=str(OUT_DIR / "refraction"), help="folder for screenshots ('' = none)")
    p.add_argument("--no-optics", action="store_true", help="skip the CPU ray model section [M]")
    p.add_argument("--optics-sizes", nargs="+", default=[f"{w}x{h}" for w, h in probe_eye.SIZES])
    return p


def name_of(run) -> str:
    tech, refraction, cornea = run
    return f"{tech} {refraction}" + (f" {cornea}" if refraction == "V1" else "")


def apply_run(state: rg.RefractionState, run) -> None:
    state.technique, state.refraction, state.cornea = run


def project(camera, point, width: int, height: int) -> tuple[float, float, float]:
    """(column, row from the top, window depth) of a world point with the camera's own matrices."""
    view = np.array(camera.build_view_matrix()).reshape(4, 4).T
    proj = np.array(camera.build_projection_matrix(width / height)).reshape(4, 4).T
    clip = proj @ view @ np.array([*point, 1.0])
    ndc = clip[:3] / clip[3]
    return (ndc[0] + 1.0) * 0.5 * width, (1.0 - ndc[1]) * 0.5 * height, (ndc[2] + 1.0) * 0.5


def cornea_crop(camera, image: np.ndarray, size: int = 560) -> np.ndarray:
    """A square crop centred on the limbus centre's projection (clamped to the frame)."""
    h, w = image.shape[:2]
    size = min(size, h, w)
    x, y, _ = project(camera, (0.0, 0.0, geo.LIMBUS_Z), w, h)
    x0 = int(np.clip(round(x) - size // 2, 0, w - size))
    y0 = int(np.clip(round(y) - size // 2, 0, h - size))
    return image[y0:y0 + size, x0:x0 + size]


class RefractionProbe(probe_eye.Probe):
    def optics(self) -> None:
        sizes = [pg.parse_size(s) for s in self.args.optics_sizes]
        for line in optics_report.report(sizes, self.args.views):
            self.add(line)
        self.add("")

    def parity(self, res: pg.Resources) -> None:
        pp = rg.RefractionParityPass(self.gl, res)
        self.add(f"[P] refraction GLSL vs cornea_optics (refraction_parity.py, float32 inputs; read-back {pp.status})")
        self.add(f"  {'function':<16} {'max abs err':>12} {'failed':>7} {'compared':>9} {'tolerance':>22}")
        ok = True
        for case in rp.cases():
            err, bad, compared = case.errors(pp.run(case.func, case.inputs))
            ok &= bad == 0
            tol = f"{case.abs_tol:g}" + (f" + {case.rel_tol:g}|x|" if case.rel_tol else "")
            exact = " + class equal" if case.exact_channel is not None else ""
            self.add(f"  {case.func:<16} {err:>12.3g} {bad:>7} {compared:>9} {tol + exact:>22}")
        errors = pg.drain_errors(self.gl)
        pp.release()
        status = cm.PASS if ok and not errors else cm.FAIL
        self.add(f"  -> {status}{'; GL errors ' + ', '.join(errors) if errors else ''}")
        self.verdict("P refraction parity", status)
        self.add("")

    def kinds(self, scene, res: pg.Resources) -> None:
        gl = self.gl
        state = scene.renderer.state
        width, height = SHOT_SIZE
        target = gl_lab.Target(gl, res, width, height)
        distance = lab_scene.close_up_distance(width, height)
        self.add(f"[K] ray class per pixel, GPU (DEBUG_KIND) vs CPU model, {width}x{height}, eye ~50 %; pixels where "
                 "both see the cornea")
        ok = True
        scene.renderer.debug_kind = True
        state.technique, state.show_references = "T-C", False
        for view in self.args.views:
            scene.apply_view(view, distance)
            scene.set_aspect(width, height)
            scene.camera_moved()
            eye, dirs = co.camera_rays(scene.camera, width, height)
            blocked = co.sclera_occludes(eye, dirs)
            for variant in ("V2", "V3"):
                state.refraction = variant
                self._frame(scene, target)
                img = target.read_rgb().astype(int)
                gl_kind = np.full(img.shape[:2], -1)
                for kind, colour in ((co.IRIS, (255, 0, 0)), (co.PUPIL, (0, 255, 0)), (co.LIMBUS, (0, 0, 255))):
                    gl_kind[np.all(img == colour, axis=-1)] = kind
                cpu = np.where(blocked, co.MISS, co.trace(eye, dirs, variant).kind)
                both = (gl_kind >= 0) & (cpu != co.MISS)
                agree = gl_kind[both] == cpu[both]
                share = float(np.mean(agree)) if both.any() else 1.0
                ok &= share >= 0.999
                self.add(f"  {view:<14} {variant}: GPU cornea px {int((gl_kind >= 0).sum())}, CPU {int((cpu != co.MISS).sum())}, "
                         f"compared {int(both.sum())}, same class {100.0 * share:.3f} % ({int((~agree).sum())} differ)")
        scene.renderer.debug_kind = False
        target.release()
        errors = pg.drain_errors(gl)
        status = cm.PASS if ok and not errors else cm.FAIL
        self.add(f"  -> {status} (threshold 99.9 %: border pixels may fall either way in float32)")
        self.verdict("K GPU ray classes = CPU model", status)
        self.add("")

    def depth(self, scene, res: pg.Resources) -> None:
        import ctypes

        gl = self.gl
        state = scene.renderer.state
        width, height = SHOT_SIZE
        target = gl_lab.Target(gl, res, width, height)
        scene.apply_view("three_quarter", lab_scene.close_up_distance(width, height))
        scene.set_aspect(width, height)
        scene.camera_moved()
        state.technique, state.refraction, state.show_references = "T-C", "V2", False
        self.add("[D] the opaque cornea pass (T-C V2, 3/4 view)")
        self._frame(scene, target)
        blend = bool(gl.glIsEnabled(gl.GL_BLEND))
        mask = gl.GLboolean()
        gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK, ctypes.byref(mask))
        base = target.read_rgb()
        # Depth at the pixel through the cornea's centre (the limbus centre's projection).
        x, y, _ = project(scene.camera, (0.0, 0.0, geo.CORNEA_APEX_Z), width, height)
        col, row = int(x), int(y)
        eye, dirs = co.camera_rays(scene.camera, width, height)
        tr = co.trace(eye, dirs[row:row + 1, col:col + 1], "V2")
        expected = project(scene.camera, tr.entry[0, 0], width, height)[2]
        behind = project(scene.camera, tr.hit[0, 0], width, height)[2]
        straight = co.trace(eye, dirs[row:row + 1, col:col + 1], "V1")
        iris_depth = project(scene.camera, straight.hit[0, 0], width, height)[2]
        value = np.zeros(1, dtype=np.float32)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, target.fbo)
        gl.glReadPixels(col, height - 1 - row, 1, 1, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, value.ctypes.data)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
        depth = float(value[0])
        depth_ok = abs(depth - expected) < 1e-4 and depth < iris_depth
        self.add(f"  after the frame: GL_BLEND {'on' if blend else 'off'}, depth write mask "
                 f"{'on' if mask.value else 'off'} (expected off / on)")
        self.add(f"  depth at the cornea centre pixel ({col}, {row}): {depth:.6f}; analytic anterior surface "
                 f"{expected:.6f}; the iris straight behind {iris_depth:.6f}; the refracted iris point {behind:.6f}")
        scene.renderer.keep_iris_mesh = True
        self._frame(scene, target)
        with_iris = target.read_rgb()
        scene.renderer.keep_iris_mesh = False
        same_with_iris = np.array_equal(with_iris, base)
        self.add(f"  iris mesh drawn under the cornea: image {'identical' if same_with_iris else 'DIFFERENT'} "
                 f"({int(np.sum(np.any(with_iris != base, axis=-1)))} px differ)")
        # Reverse order: the same frame with the stores drawn cornea first.
        viewport = scene.viewport
        stores = [viewport.object_entries[k].store for k in ("cornea", "chrome", "iris", "sclera")]
        stores.append(viewport.render_mesh.store)
        target.bind()
        gl.glViewport(0, 0, width, height)
        gl.glClearColor(0.1, 0.1, 0.11, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        scene.renderer.draw_background(width, height)
        viewport.sync()
        for store in stores:
            store.draw()
        gl.glUseProgram(0)
        target.unbind()
        reverse = target.read_rgb()
        differ = int(np.sum(np.any(reverse != base, axis=-1)))
        reverse_ok = differ <= 0.001 * width * height
        self.add(f"  parts drawn in reverse order (cornea first): {differ} px differ "
                 f"({100.0 * differ / (width * height):.4f} % of the frame; ties along the shared limbus ring)")
        target.release()
        errors = pg.drain_errors(gl)
        ok = not blend and bool(mask.value) and depth_ok and same_with_iris and reverse_ok and not errors
        status = cm.PASS if ok else cm.FAIL
        self.add(f"  -> {status}{'; GL errors ' + ', '.join(errors) if errors else ''}")
        self.verdict("D opaque cornea: depth, blending, order", status)
        self.add("")

    def variants(self, scene, res: pg.Resources) -> None:
        gl = self.gl
        state = scene.renderer.state
        state.show_references = False
        self.query = res.query()
        shots: dict = {}
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
                runs = list(RUNS) + [("background", None, None)]
                gpu = {run: [] for run in runs}
                cpu = {run: [] for run in runs}
                errors = {run: [] for run in runs}
                last = {}
                for round_ in range(probe_eye.WARMUP + self.args.draws):
                    for run in runs:
                        if run[0] == "background":
                            apply_run(state, ("T-C", "V1", "C2"))
                            scene.renderer.only_parts = set()
                        else:
                            apply_run(state, run)
                            scene.renderer.only_parts = None
                        g, c = self._frame(scene, target)
                        errors[run] += pg.drain_errors(gl)
                        if round_ >= probe_eye.WARMUP:
                            gpu[run].append(g)
                            cpu[run].append(c)
                        if round_ == probe_eye.WARMUP + self.args.draws - 1:
                            last[run] = target.read_rgb()
                scene.renderer.only_parts = None
                self.add(f"    view {view}")
                self.add(f"    {'run':<12} {'GPU p50':>8} {'p95':>8} {'min':>8} {'max':>8} {'CPU p50':>8}  "
                         f"{'px != T-C V1 C2':>15}  GL errors")
                base = last[("T-C", "V1", "C2")]
                for run in runs:
                    name = "background" if run[0] == "background" else name_of(run)
                    diff = int(np.sum(np.any(last[run] != base, axis=-1)))
                    self.add(f"    {name:<12} {probe_eye._rows_ms(gpu[run])} {statistics.median(cpu[run]):8.2f}  "
                             f"{diff:>15}  {', '.join(sorted(set(errors[run]))) or 'none'}")
                    if errors[run]:
                        self.verdict(f"V GL errors {name} {view} {text}", cm.FAIL)
                if text == self.args.sizes[0]:
                    shots[view] = {run: img for run, img in last.items() if run[0] != "background"}
                    shots[view]["camera"] = (scene.camera.yaw, scene.camera.pitch, scene.camera.distance)
            target.release()
        if not any(check.startswith("V ") for check, _ in self.verdicts):
            self.verdict("V every run renders without GL error", cm.PASS)
        self.add("")
        if self.args.images and shots:
            self.write_shots(Path(self.args.images), shots, scene)

    def write_shots(self, folder: Path, shots: dict, scene) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        rows = []
        for view, runs in shots.items():
            yaw, pitch, distance = runs.pop("camera")
            scene.camera.yaw, scene.camera.pitch, scene.camera.distance = yaw, pitch, distance
            for run, img in runs.items():
                cm.write_png(folder / f"refraction_{view}_{name_of(run).replace(' ', '_')}.png", img / 255.0)
            crops = [cornea_crop(scene.camera, runs[run]) for run in SHEET_RUNS]
            diff = np.clip(np.abs(crops[2].astype(int) - crops[1].astype(int)) * 8, 0, 255).astype(np.uint8)
            row = np.concatenate(crops + [diff], axis=1)
            cm.write_png(folder / f"refraction_sheet_{view}.png", row / 255.0)
            rows.append(row)
        rows.append(self.steep_row(scene, folder))
        cm.write_png(folder / "refraction_sheet.png", np.concatenate(rows, axis=0) / 255.0)
        self.add(f"Screenshots: {folder} - refraction_<view>_<run>.png ({self.args.sizes[0]}); "
                 "refraction_sheet_<view>.png and refraction_sheet.png: cornea crops 560^2, columns T-C V1 C2 (P1) | "
                 "T-C V2 | T-C V3 | |V3 - V2| x 8, rows front / 3/4 / profile / steep 75 (supplementary)")
        self.add("")


def _steep_row(self, scene, folder: Path) -> np.ndarray:
    """The sheet's supplementary row at `STEEP_VIEW` (the screenshot size, eye ~50 %) plus the CPU model's counts."""
    import math

    gl = self.gl
    state = scene.renderer.state
    width, height = pg.parse_size(self.args.sizes[0])  # the same frame size as the other screenshots
    name, yaw, pitch = STEEP_VIEW
    target = gl_lab.Target(gl, scene.renderer.res, width, height)
    scene.camera.set_view(math.radians(yaw), math.radians(pitch))
    scene.camera.distance = lab_scene.close_up_distance(width, height)
    scene.set_aspect(width, height)
    scene.camera_moved()
    images = {}
    for run in SHEET_RUNS:
        apply_run(state, run)
        self._frame(scene, target)
        images[run] = target.read_rgb()
        cm.write_png(folder / f"refraction_{name}_{name_of(run).replace(' ', '_')}.png", images[run] / 255.0)
    target.release()
    eye, d = co.camera_rays(scene.camera, width, height)
    blocked = co.sclera_occludes(eye, d)
    counts = []
    for variant in co.VARIANTS:
        kind = np.where(blocked, co.MISS, co.trace(eye, d, variant).kind)
        counts.append(f"{variant} pupil {int(np.sum(kind == co.PUPIL))} / iris {int(np.sum(kind == co.IRIS))}")
    self.add(f"Supplementary view {name} (yaw {yaw:g}, {width}x{height}, eye ~50 %), CPU model px: " + ", ".join(counts))
    crops = [cornea_crop(scene.camera, images[run]) for run in SHEET_RUNS]
    diff = np.clip(np.abs(crops[2].astype(int) - crops[1].astype(int)) * 8, 0, 255).astype(np.uint8)
    row = np.concatenate(crops + [diff], axis=1)
    cm.write_png(folder / f"refraction_sheet_{name}.png", row / 255.0)
    return row


RefractionProbe.steep_row = _steep_row


def run(args) -> list[str]:
    probe = RefractionProbe(args)
    gl = probe.gl
    probe.header()
    probe.lines[0] = f"{PROBE_NAME}: ray model, parity, ray classes, depth / blending, timings, screenshots"
    before = pg.snapshot(gl)
    state = rg.RefractionState()
    scene = None
    res = pg.Resources(gl)
    try:
        if not args.no_optics:
            probe.guarded("M", probe.optics)
        scene = rg.build_scene(state, OUT_DIR, CACHE_DIR, *SHOT_SIZE)
        probe.query = res.query()  # `_frame` times every frame, also in [K] / [D]
        probe.guarded("P", probe.parity, res)
        probe.guarded("K", probe.kinds, scene, scene.renderer.res)
        probe.guarded("D", probe.depth, scene, scene.renderer.res)
        probe.guarded("V", probe.variants, scene, scene.renderer.res)
    except Exception:  # noqa: BLE001
        probe.failures.append("setup")
        probe.add("ERROR in setup:")
        probe.add("  " + traceback.format_exc().strip().replace("\n", "\n  "))
    finally:
        made, leaks_scene = "", None
        if scene is not None:
            made = scene.renderer.res.counts()
            leaks_scene = scene.renderer.res
            scene.release()
        res.release_all()
        gl.glFinish()
        pg.restore(gl, before)
        gl.glClearColor(*before["GL_COLOR_CLEAR_VALUE"])
        gl.glDepthMask(gl.GL_TRUE)
        leaks = res.leaks() + (leaks_scene.leaks() if leaks_scene is not None else [])
        diff = cm.state_diff(before, pg.snapshot(gl))
        final_errors = pg.drain_errors(gl)
        probe.window.close()
    hygiene = cm.PASS if not leaks and not diff and not final_errors else cm.FAIL
    probe.add("[R] resources and GL state")
    probe.add(f"  lab objects: {made or 'none'}; probe objects: {res.counts() or 'none'}")
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
                                      "--images", images, "--no-optics"])


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for line in run(args):
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
