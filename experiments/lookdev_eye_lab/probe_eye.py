"""Probe mode of the Eye Proof (`run.py --probe`): everything audit §5.6 / §6.5 asks to measure, in one plain-ASCII
report for the results file.

Sections:
- header: platform, CPU, Python / NumPy / pyglet, source state (commit, `src/` tree), GL strings, limits,
  Lookdev-relevant extensions, video memory (`probe_gl_caps.context_info`), and the EVIDENCE line;
- [E] environment: CPU prefilter time per chain (fresh, not from the cache), upload time, driver-reported format,
  computed texture memory and the `GL_NVX_gpu_memory_info` drop, for 64 / 128 / 256 x RGBA16F / RGBM8;
- [S] seams: check D's smooth test pattern (`cube_math.smooth_pattern`) as the lab builds its cube - chain ending at
  2^2, corners equalized - against the probe's raw chain (to 1^2, not equalized), seamless on; RESULTS_REFERENCE_PC
  §8.3 predicted no seams (INFERRED); this confirms or refutes it on the driver;
- [Q5] sRGB: does an `GL_SRGB8_ALPHA8` texture decode as the shader's `srgb_decode` does (audit §5.7 Q5)?
- [P] parity: every `LIB_SRC` function against the NumPy reference (`parity.py`) on this driver;
- [V] variants: every (technique, cornea) at the three views and two frame sizes into an offscreen RGBA8 + DEPTH24
  target of exactly that size, the eye covering about 50 % of the frame; GL_TIME_ELAPSED p50 / p95 per frame
  (clear + background + the viewport's render), CPU p50 of the submission, the GL errors, and how many pixels differ
  from T-A; the background pass alone as a baseline;
- [W] roughness sweep: the chrome sphere under a softbox-only studio, T-C and T-D, roughness 0 ... 1; the spread
  (luminance-weighted variance) of the reflected softbox must grow monotonically (audit §5.5);
- screenshots: every variant at the three views (the first frame size, 1024 x 768) and one contact sheet per view;
- [R] hygiene: the lab's GL objects deleted, GL state as before, `glGetError` clean.
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from lookdev_gpu_probe import cube_math as cm
from lookdev_gpu_probe import probe_gl_caps as pg

from . import eye_math as em
from . import gl_lab
from . import lab_scene
from . import lab_state as ls
from . import parity
from . import studio_env as se
from ._paths import CACHE_DIR, OUT_DIR, REPO_ROOT

PROBE_NAME = "Lookdev P1 Eye Proof probe (2026-11-14)"
SIZES = ((1024, 768), (1920, 1080))
SHOT_SIZE = (1024, 768)
WARMUP = 5
DEFAULT_DRAWS = 30
SWEEP = (0.0, 0.1, 0.25, 0.5, 0.75, 1.0)
SEAM_SIZE = 64


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=PROBE_NAME)
    p.add_argument("--draws", type=int, default=DEFAULT_DRAWS, help="measured frames per variant (after 5 warm-up)")
    p.add_argument("--sizes", nargs="+", default=[f"{w}x{h}" for w, h in SIZES], help="frame sizes WxH")
    p.add_argument("--views", nargs="+", default=list(ls.VIEW_ORDER), choices=ls.VIEW_ORDER)
    p.add_argument("--images", default=str(OUT_DIR / "probe"), help="folder for screenshots ('' = none)")
    p.add_argument("--env-sizes", nargs="+", type=int, default=list(ls.ENV_SIZES), help="cube sizes for [E]")
    p.add_argument("--quick", action="store_true", help="tests: one view, few draws, 64^2 cube only")
    return p


def _rows_ms(values: list[float]) -> str:
    p50, p95, lo, hi = cm.timing_summary(values)
    return f"{p50:8.2f} {p95:8.2f} {lo:8.2f} {hi:8.2f}"


class Probe:
    def __init__(self, args) -> None:
        import pyglet
        from pyglet import gl

        self.args, self.gl, self.pyglet = args, gl, pyglet
        self.lines: list[str] = []
        self.verdicts: list[tuple[str, str]] = []
        self.failures: list[str] = []
        self.window = pyglet.window.Window(width=256, height=256, visible=False)
        self.window.switch_to()
        pg.drain_errors(gl)
        self.query = 0

    def add(self, line: str = "") -> None:
        self.lines.append(line)

    def verdict(self, check: str, status: str) -> None:
        self.verdicts.append((check, status))

    def guarded(self, title: str, fn, *fn_args) -> None:
        try:
            fn(*fn_args)
        except Exception:  # noqa: BLE001 - a broken section is reported, the others still run
            self.failures.append(title)
            self.add(f"  ERROR in {title}:")
            self.add("    " + traceback.format_exc().strip().replace("\n", "\n    "))
            pg.drain_errors(self.gl)

    # -- sections

    def header(self) -> None:
        gl, pyglet = self.gl, self.pyglet
        self.add(f"{PROBE_NAME}: environment, seams, sRGB, parity, variant timings, roughness sweep, screenshots")
        self.add(f"Platform: {platform.platform()}")
        self.add(f"CPU: {pg.cpu_name()} ({os.cpu_count()} logical cores)")
        self.add(f"Python: {platform.python_version()}, numpy {np.__version__}, pyglet {pyglet.version}")
        self.add(f"Interpreter: {sys.executable}")
        self.add(f"Source: {cm.source_state(REPO_ROOT)}")
        info, limits, self.extensions, _ = pg.context_info(gl, self.window, pyglet)
        for line in info:
            self.add(line)
        renderer = info[1].split(": ", 1)[1]
        if cm.software_renderer(renderer):
            self.add("EVIDENCE: SOFTWARE RENDERER - TESTED [C] at best; GL_TIME_ELAPSED here is not a GPU time.")
        else:
            self.add("EVIDENCE: hardware renderer - label the results MEASURED [RPC] or MEASURED [MAIN] by machine.")
        self.add("Limits: " + ", ".join(f"{k.replace('GL_MAX_', '')} {v}" for k, v in limits.items()))
        self.add("Extensions: " + ", ".join(name for name, _ in cm.RELEVANT_EXTENSIONS if name in self.extensions))
        memory = pg.memory_kib(gl, self.extensions)
        self.add("GPU memory (KiB): " + (", ".join(f"{k} {v}" for k, v in memory.items()) or "not exposed"))
        self.add("")

    def environment(self, renderer: gl_lab.EyeLabRenderer) -> None:
        self.add("[E] environment: CPU prefilter (fresh, not from the cache) and upload; chain ends at 2^2, corners "
                 "equalized")
        env = se.DEFAULT_ENV
        self.add(f"  studio {env.fingerprint()}: softbox az {env.key().azimuth} el {env.key().elevation}, "
                 f"{2 * env.key().half_width:.0f} x {2 * env.key().half_height:.0f} deg, radiance "
                 f"{env.key().radiance[0]}; strip radiance {env.lights[1].radiance[0]}")
        sky, ground = se.ambient_colours(env)
        self.add(f"  ambient (cosine-weighted mean radiance) sky {sky[0]:.4f}, ground {ground[0]:.4f}")
        self.add(f"  {'size':>4} {'mapping':>7} {'prefilter s':>11} {'samples per level':<40} roughness per level")
        cube = renderer.env_cube
        cube.info["extensions"] = self.extensions
        for size in self.args.env_sizes:
            for mapping in (0, 1):
                fresh = se.prefilter(env, size, mapping, CACHE_DIR, force=True)  # also refreshes the lab's cache
                cube.chains[(env.fingerprint(), size, mapping)] = fresh
                self.add(f"  {size:>4} {em.LOD_MAPPINGS[mapping]:>7} {fresh.seconds:>11.2f} "
                         f"{str(fresh.samples):<40} {[round(r, 3) for r in fresh.roughness]}")
        self.add(f"  {'size':>4} {'format':>8} {'upload ms':>9} {'computed':>10} {'NVX drop':>10}  driver, errors")
        for size in self.args.env_sizes:
            for fmt in ls.ENV_FORMATS:
                state = ls.LabState(env_size=size, env_format=fmt)
                cube.key = None
                cube.ensure(state)
                i = cube.info
                drop = f"{i['free_kib_drop'] / 1024:.2f} MiB" if i["free_kib_drop"] is not None else "n/a"
                self.add(f"  {size:>4} {fmt:>8} {1000 * i['upload_s']:>9.1f} {pg.mib(i['bytes']):>10} {drop:>10}  "
                         f"{i['driver']}, {', '.join(i['errors']) or 'no GL error'}")
        cube.key = None
        self.add("")

    def seams(self, res: pg.Resources) -> None:
        gl = self.gl
        sp = pg.SamplePass(gl, res)
        samples = cm.seam_samples()
        keys = ("a", "b", "ia", "ib")
        self.add(f"[S] seams, seamless on: check D's smooth {SEAM_SIZE}^2 pattern, RGBA16F; jump = largest RGB step "
                 "across the 12 edges")
        self.add(f"  {'level':>5} {'size':>5} {'raw chain (to 1^2)':>19} {'lab chain (to 2^2, equalized)':>30} "
                 f"{'tolerance':>10}")
        raw_levels = cm.smooth_pattern(SEAM_SIZE)
        lab_levels = [cm.equalize_corners(level) for level in raw_levels if level.shape[1] >= se.LAST_SIZE]
        jumps = {}
        for name, levels in (("raw", raw_levels), ("lab", lab_levels)):
            tex, errors, _ = pg.make_cube(gl, res, cm.RGBA16F, levels)
            per = len(samples["a"])
            dirs = np.concatenate([samples[k] for _ in levels for k in keys])
            lods = np.concatenate([np.full(per, float(lv)) for lv in range(len(levels)) for _ in keys])
            values, _ = sp.run(tex, dirs, lods, seamless=True)
            values = values.reshape(len(levels), len(keys), per, 4)
            jumps[name] = [(cm.max_jump(v[0], v[1]), cm.max_jump(v[2], v[3])) for v in values]
            res.delete("texture", tex)
            if errors:
                self.add(f"  GL errors ({name}): {', '.join(errors)}")
        ok = True
        for level, n in enumerate(cm.level_sizes(SEAM_SIZE)):
            raw = jumps["raw"][level][0]
            if level < len(jumps["lab"]):
                lab, interior = jumps["lab"][level]
                row = cm.SeamRow(level, n, cm.seam_step(cm.stored(lab_levels[level], cm.RGBA16F), samples), 0.0, lab,
                                 interior)
                tol = cm.seam_tolerance(row, 0.0)
                ok &= lab <= tol
                self.add(f"  {level:>5} {n:>5} {raw:>19.5f} {lab:>30.5f} {tol:>10.5f}{'' if lab <= tol else '  SEAM'}")
            else:
                self.add(f"  {level:>5} {n:>5} {raw:>19.5f} {'(not in the lab chain)':>30}")
        status = cm.PASS if ok else cm.FAIL
        self.add(f"  -> {status}: " + ("no seam at any level of the lab chain" if ok else "seams remain"))
        self.verdict("S seams (lab chain)", status)
        self.add("")

    def srgb(self, res: pg.Resources) -> None:
        """Q5: GL_SRGB8_ALPHA8 decode vs the shader decode, all 256 codes, read back through texelFetch."""
        gl = self.gl
        from pyglet.graphics.shader import Shader, ShaderProgram

        codes = np.arange(256, dtype=np.uint8)
        image = np.ascontiguousarray(np.stack([codes, codes, codes, np.full(256, 255, np.uint8)], axis=-1)[None])
        frag = ("#version 330 core\nuniform sampler2D u_tex;\nlayout(location = 0) out vec4 o;\n"
                "void main() { o = texelFetch(u_tex, ivec2(int(gl_FragCoord.x), 0), 0); }\n")
        program = ShaderProgram(Shader(pg.VERTEX_SRC, "vertex"), Shader(frag, "fragment"))
        vao = pg.fullscreen_triangle(gl, res)
        fbo, _rb, status = pg.colour_target(gl, res, gl.GL_RGBA32F, 256, 1)
        out = {}
        for name, internal in (("SRGB8_ALPHA8", gl.GL_SRGB8_ALPHA8), ("RGBA8", gl.GL_RGBA8)):
            tex = res.texture()
            values = np.zeros((1, 256, 4), dtype=np.float32)
            with pg.preserved(gl):
                gl.glActiveTexture(gl.GL_TEXTURE0 + pg.CUBE_UNIT)
                gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
                gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
                gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, internal, 256, 1, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
                                image.ctypes.data)
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
                gl.glViewport(0, 0, 256, 1)
                program.use()
                gl.glUniform1i(gl.glGetUniformLocation(program.id, pg.c_name("u_tex")), pg.CUBE_UNIT)
                gl.glBindVertexArray(vao)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
                gl.glReadPixels(0, 0, 256, 1, gl.GL_RGBA, gl.GL_FLOAT, values.ctypes.data)
            out[name] = values[0, :, 0].astype(np.float64)
            res.delete("texture", tex)
        program.delete()
        errors = pg.drain_errors(gl)
        reference = em.srgb_decode(codes / 255.0)
        shader_side = em.srgb_decode(out["RGBA8"])
        hw = np.abs(out["SRGB8_ALPHA8"] - reference)
        self.add(f"[Q5] sRGB decode, 256 codes (read-back target RGBA32F {status})")
        self.add(f"  GL_SRGB8_ALPHA8 vs the exact sRGB curve: max error {hw.max():.2e} (at code {int(hw.argmax())}); "
                 f"shader-side decode of RGBA8 vs exact: {np.abs(shader_side - reference).max():.2e}; "
                 f"GL errors: {', '.join(errors) or 'none'}")
        status = cm.PASS if hw.max() <= 2.0 / 255.0 and not errors else cm.FAIL
        self.add(f"  -> {status} (threshold 2/255: hardware decode may use an 8-bit table)")
        self.verdict("Q5 sRGB texture decode", status)
        self.add("")

    def parity(self, res: pg.Resources) -> None:
        pp = gl_lab.ParityPass(self.gl, res)
        self.add(f"[P] shader vs NumPy reference (parity.py, float32 inputs; read-back RGBA32F {pp.status})")
        self.add(f"  {'function':<18} {'max abs err':>12} {'err / tol':>10} {'failed':>7} {'compared':>9}")
        ok = True
        for case in parity.cases():
            measured = pp.run(case.func, case.inputs)
            err, ratio, bad = case.errors(measured)
            compared = int(case.mask.sum()) if case.mask is not None else len(measured)
            ok &= bad == 0
            self.add(f"  {case.func:<18} {err:>12.3g} {ratio:>10.3f} {bad:>7} {compared:>9}")
        errors = pg.drain_errors(self.gl)
        pp.release()
        status = cm.PASS if ok and not errors else cm.FAIL
        self.add(f"  -> {status}{'; GL errors ' + ', '.join(errors) if errors else ''}")
        self.verdict("P parity", status)
        self.add("")

    def _frame(self, scene, target: gl_lab.Target) -> tuple[float, float]:
        """One measured frame into `target`: (GPU ms, CPU submission ms)."""
        import ctypes

        gl = self.gl
        target.bind()
        gl.glFinish()
        start = time.perf_counter()
        gl.glBeginQuery(gl.GL_TIME_ELAPSED, self.query)
        scene.renderer.frame(scene.viewport, target.width, target.height)
        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        cpu = (time.perf_counter() - start) * 1000.0
        gl.glFinish()
        value = ctypes.c_uint64()
        gl.glGetQueryObjectui64v(self.query, gl.GL_QUERY_RESULT, ctypes.byref(value))
        target.unbind()
        return value.value / 1e6, cpu

    def variants(self, scene, res: pg.Resources) -> None:
        gl = self.gl
        state = scene.renderer.state
        state.show_references = False
        self.query = res.query()
        images = Path(self.args.images) if self.args.images else None
        shots: dict = {}
        self.add(f"[V] variants: frame = clear + background + viewport.render(); eye only, sclera disc ~ "
                 f"{lab_scene.CLOSE_UP_COVERAGE:.0%} of the frame; {self.args.draws} frames after {WARMUP}, variants "
                 "interleaved; GPU = GL_TIME_ELAPSED, CPU = submission (frame call without glFinish)")
        for text in self.args.sizes:
            width, height = pg.parse_size(text)
            target = gl_lab.Target(gl, res, width, height)
            distance = lab_scene.close_up_distance(width, height)
            self.add(f"  {width}x{height}: target {target.status}, camera distance {distance:.3f} "
                     f"(predicted coverage {em.sphere_coverage(distance, 1.0, scene.camera.fov_degrees, width, height):.1%})")
            for view in self.args.views:
                scene.apply_view(view, distance)
                scene.set_aspect(width, height)
                scene.camera_moved()
                runs = list(ls.VARIANTS) + [("background", None)]
                gpu = {run: [] for run in runs}
                cpu = {run: [] for run in runs}
                errors = {run: [] for run in runs}
                last = {}
                for round_ in range(WARMUP + self.args.draws):
                    for run in runs:
                        if run[0] == "background":
                            state.technique, state.cornea = "T-C", "C2"
                            scene.renderer.only_parts = set()
                        else:
                            state.technique, state.cornea = run
                            scene.renderer.only_parts = None
                        g, c = self._frame(scene, target)
                        errors[run] += pg.drain_errors(gl)
                        if round_ >= WARMUP:
                            gpu[run].append(g)
                            cpu[run].append(c)
                        if round_ == WARMUP + self.args.draws - 1:
                            last[run] = target.read_rgb()
                # The cleared colour as this driver stores it: the reference PC rounds 0.1 * 255 differently from
                # Mesa, and a hard-coded (26, 26, 28) made every pixel count as eye there (RPC run 2026-11-14).
                state.technique, scene.renderer.only_parts = "T-A", set()
                self._frame(scene, target)
                clear = target.read_rgb()[0, 0].copy()
                scene.renderer.only_parts = None
                reference = last[("T-A", "C1")]
                eye = np.any(reference != clear, axis=-1)
                covered = int(np.sum(eye))
                self.add(f"    view {view}: measured coverage (T-A C1, non-clear pixels) "
                         f"{covered / (width * height):.1%}")
                self.add(f"    {'variant':<12} {'GPU p50':>8} {'p95':>8} {'min':>8} {'max':>8} {'CPU p50':>8}  "
                         f"{'px != T-A C1':>16}  GL errors (px: eye only; T-A: frame)")
                for run in runs:
                    name = "background" if run[0] == "background" else f"{run[0]} {run[1]}"
                    # Lab variants draw their own background: compare the eye's pixels. T-A shares the clear colour:
                    # compare the frame (in profile the Ghost cornea lies outside the C1 silhouette).
                    mask = eye if run[0] not in ("T-A", "background") else np.ones_like(eye)
                    diff = int(np.sum(np.any(last[run] != reference, axis=-1) & mask))
                    self.add(f"    {name:<12} {_rows_ms(gpu[run])} {statistics.median(cpu[run]):8.2f}  "
                             f"{f'{diff} ({diff / max(int(mask.sum()), 1):.0%})':>16}  "
                             f"{', '.join(sorted(set(errors[run]))) or 'none'}")
                    if run[0] != "background":
                        if errors[run]:
                            self.verdict(f"V GL errors {name} {view} {text}", cm.FAIL)
                        if run != ("T-A", "C1") and diff == 0:
                            self.verdict(f"V image differs from T-A C1: {name} {view} {text}", cm.FAIL)
                if cm.timing_unstable({str(k): v for k, v in gpu.items()}):
                    self.add("    NOTE: one variant's GPU times spread > 2.5x - clocks changed? (power management)")
                if text == self.args.sizes[0]:  # screenshots at the first size (default 1024x768)
                    shots[view] = {run: img for run, img in last.items() if run[0] != "background"}
            target.release()
            self.add("")
        if not any(check.startswith("V ") for check, _ in self.verdicts):
            self.verdict("V every variant renders without GL error and differs from T-A", cm.PASS)
        if images is not None and shots:
            self.write_shots(images, shots)

    def write_shots(self, folder: Path, shots: dict) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        for view, runs in shots.items():
            for (tech, cornea), img in runs.items():
                cm.write_png(folder / f"eye_{view}_{tech}_{cornea}.png", img / 255.0)
            h, w = next(iter(runs.values())).shape[:2]
            blank = np.full((h, w, 3), 255, dtype=np.uint8)
            rows = []
            for tech in ls.TECHNIQUES:
                row = [runs.get((tech, cornea), blank) for cornea in ls.CORNEAS]
                rows.append(np.concatenate(row, axis=1))
            sheet = np.concatenate(rows, axis=0)[::2, ::2]  # half size
            cm.write_png(folder / f"sheet_{view}.png", sheet / 255.0)
        self.add(f"Screenshots: {folder} - eye_<view>_<technique>_<cornea>.png at {self.args.sizes[0]}; "
                 "sheet_<view>.png at half size: rows T-A..T-D, columns C1..C3 (T-A has C1 = no cornea, C2 = the "
                 "production Ghost; its C3 cell is blank)")
        self.add("")

    def sweep(self, scene, res: pg.Resources) -> None:
        gl = self.gl
        state = scene.renderer.state
        saved = state.copy()
        softbox = se.StudioEnv(lights=(se.DEFAULT_ENV.key(),))
        backdrop = se.StudioEnv(lights=())
        state.key_intensity, state.show_references, state.background = 0.0, True, "solid"
        state.tonemap, state.exposure_ev = 1, 0.0
        scene.renderer.only_parts = {"chrome"}
        target = gl_lab.Target(gl, res, 512, 512)
        scene.camera.target = geo_chrome()
        scene.apply_view("front", 1.9)
        scene.set_aspect(512, 512)
        scene.camera_moved()
        self.add("[W] roughness sweep: chrome sphere (F0 1), key light off, front view 512^2. Footprint = the "
                 "softbox's own reflection: linear luminance of a softbox-only studio minus a backdrop-only one "
                 "(Reinhard inverted); spread = its luminance-weighted variance in px^2")
        ok = True
        for tech in ("T-C", "T-D"):
            spreads = []
            for r in SWEEP:
                state.technique, state.chrome_roughness = tech, r
                lum = {}
                for name, env in (("softbox", softbox), ("backdrop", backdrop)):
                    state.env = env
                    self._frame(scene, target)
                    lum[name] = linear_luminance(target.read_rgb())
                spreads.append(weighted_variance(np.maximum(lum["softbox"] - lum["backdrop"], 0.0)))
            monotonic = all(b > a for a, b in zip(spreads, spreads[1:]))
            ok &= monotonic
            self.add(f"  {tech}: " + ", ".join(f"r {r:g}: {s:.0f}" for r, s in zip(SWEEP, spreads))
                     + f"  -> {'monotonic' if monotonic else 'NOT monotonic'}")
        errors = pg.drain_errors(gl)
        target.release()
        scene.renderer.only_parts = None
        scene.camera.target = (0.0, 0.0, 0.0)
        for name in ("env", "key_intensity", "show_references", "background", "technique", "chrome_roughness",
                     "tonemap", "exposure_ev"):
            setattr(state, name, getattr(saved, name))
        status = cm.PASS if ok and not errors else cm.FAIL
        self.add(f"  -> {status}{'; GL errors ' + ', '.join(errors) if errors else ''}")
        self.verdict("W roughness sweep monotonic", status)
        self.add("")


def geo_chrome():
    from . import eye_geometry as geo

    return geo.CHROME_CENTRE


def linear_luminance(img: np.ndarray) -> np.ndarray:
    """Scene-linear luminance of a frame drawn with Reinhard at 0 EV (the inverse of the colour path)."""
    y = np.clip(em.srgb_decode(img / 255.0), 0.0, 0.999)
    return (y / (1.0 - y)) @ np.array([0.2126, 0.7152, 0.0722])


def weighted_variance(w: np.ndarray) -> float:
    """Spatial variance (px^2) of the weights `w` around their centroid."""
    total = w.sum()
    if total <= 0.0:
        return 0.0
    y, x = np.indices(w.shape)
    cx, cy = (w * x).sum() / total, (w * y).sum() / total
    return float((w * ((x - cx) ** 2 + (y - cy) ** 2)).sum() / total)


def run(args) -> list[str]:
    probe = Probe(args)
    gl = probe.gl
    probe.header()
    before = pg.snapshot(gl)
    state = ls.LabState()
    out_dir = OUT_DIR
    scene = None
    res = pg.Resources(gl)
    try:
        scene = lab_scene.build_scene(state, out_dir, CACHE_DIR, *SHOT_SIZE)
        probe.guarded("E", probe.environment, scene.renderer)
        probe.guarded("S", probe.seams, res)
        probe.guarded("Q5", probe.srgb, res)
        probe.guarded("P", probe.parity, res)
        probe.guarded("V", probe.variants, scene, scene.renderer.res)
        probe.guarded("W", probe.sweep, scene, scene.renderer.res)
    except Exception:  # noqa: BLE001
        probe.failures.append("setup")
        probe.add("ERROR in setup:")
        probe.add("  " + traceback.format_exc().strip().replace("\n", "\n  "))
    finally:
        made = ""
        if scene is not None:
            made = scene.renderer.res.counts()
            leaks_scene = scene.renderer.res
            scene.release()
        else:
            leaks_scene = None
        res.release_all()
        gl.glFinish()
        pg.restore(gl, before)
        gl.glClearColor(*before["GL_COLOR_CLEAR_VALUE"])  # the lab clears with the production colour
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
    return build_parser().parse_args(["--quick", "--draws", "2", "--sizes", "160x120", "--views", "front",
                                      "--env-sizes", "64", "--images", images])


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for line in run(args):
        print(line, flush=True)
    return 0
