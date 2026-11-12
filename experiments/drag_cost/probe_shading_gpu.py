"""GPU cost of one full shaded pass (2026-11-11): the O2 face-data layout against the pre-O2 one, on the GPU timer.

Usage (from the repo root; opens a hidden pyglet window):
    python experiments/drag_cost/probe_shading_gpu.py
    python experiments/drag_cost/probe_shading_gpu.py --size 1920 1080 --flat

Set the NVIDIA driver to "prefer maximum performance" first (control panel, "Manage 3D settings", "Power management
mode"): at lower clock states the same pass took about four times as long on the reference PC
(`RESULTS_O2_REFERENCE_PC_2026-11-11.md`, rounds 2 and 3), which would make variants incomparable.

Why: the D3 probe showed the O2 shaded pass at 11.3 ms GPU time at full clock on the GeForce 9800 GTX against 1.9 ms
without face data, while the navigation probe's orbit had shown only 0.76 -> 2.76 ms - that probe did not clear the
depth buffer before drawing (fixed 2026-11-11), so most fragments were never shaded. This probe measures the full pass
for each layout in the same view as the D3 probe (`probe_morph_gl.build_app`: the fixture, `frame_scene`, the app's
light and surface finish), cleared before every draw like the window's `on_draw`:

- `off`     no face data: the per-triangle vertex-normal shading (the floor);
- `pre-o2`  the pre-O2 path, frozen as the test oracle (`tests/gl_pre_o2_shading.py`: the old shader and 36-float rows;
            the rows are uploaded once, not per draw);
- `o2`      production (corner slots + the VertexList's position / normal buffers as R32F buffer textures);
- `o2-rgba` candidate: the same shader reading positions / normals as one RGBA32F texel per vertex from padded copies
            (8 fetches per smooth-quad fragment instead of 24; the copies are made once, so this measures the fetches,
            not an upload).

The variants are drawn in turn, `--draws` rounds after 5 unmeasured ones; per variant the GL_TIME_ELAPSED p50 / min /
max of the draw and whether its image equals `o2` byte for byte (`pre-o2` and `o2-rgba` must). Plain ASCII.
"""

from __future__ import annotations

import argparse
import ctypes
import statistics
import sys
import time
from array import array
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import EXPERIMENT_DIR, REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

DENSE = EXPERIMENT_DIR / "fixtures" / "gollum_87k.obj"
VARIANTS = ("off", "pre-o2", "o2", "o2-rgba")
WARMUP_ROUNDS = 5
DEFAULT_DRAWS = 40
#: The O2 fetch of one vertex value (three R32F texels) and its RGBA32F replacement in `o2-rgba`.
R32F_FETCH = """vec3 vertex_value(samplerBuffer values, int slot) {
    int i = (u_vertex_base + slot) * 3;
    return vec3(texelFetch(values, i).r, texelFetch(values, i + 1).r, texelFetch(values, i + 2).r);
}"""
RGBA_FETCH = """vec3 vertex_value(samplerBuffer values, int slot) {
    return texelFetch(values, u_vertex_base + slot).xyz;
}"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--asset", default=str(DENSE.relative_to(REPO_ROOT)), help="OBJ path relative to the repo root")
    parser.add_argument("--size", nargs=2, type=int, default=[1024, 768], metavar=("W", "H"), help="window size")
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS, help="measured rounds")
    parser.add_argument("--flat", action="store_true", help="Flat instead of Smooth")
    return parser


def resolve_asset(name: str) -> Path:
    path = Path(name)
    path = path if path.is_absolute() else REPO_ROOT / path
    if not path.is_file():
        raise SystemExit(f"no such mesh: {name}")
    return path


def rgba_fragment_source() -> str:
    from viewport.gl_render_store import FRAGMENT_SRC

    if R32F_FETCH not in FRAGMENT_SRC:
        raise SystemExit("the production shader has no R32F vertex fetch to replace (code before O2?)")
    return FRAGMENT_SRC.replace(R32F_FETCH, RGBA_FETCH)


def load_oracle():
    """`tests/gl_pre_o2_shading.py` by its path: as a script, `experiments/drag_cost/` is on `sys.path`, and its own
    `tests` package would shadow the repo's `tests` directory."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("gl_pre_o2_shading", REPO_ROOT / "tests" / "gl_pre_o2_shading.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def store_classes():
    """(`OffStore`, `CachedPreO2Store`, `RgbaStore`) - built lazily: they need pyglet and the test oracle."""
    from pyglet import gl
    from pyglet.graphics.shader import Shader, ShaderProgram

    from viewport.gl_render_store import VERTEX_SRC, GLRenderStore, _register_sampler_buffer_uniform

    oracle = load_oracle()
    PreO2Store, pre_o2_rows = oracle.PreO2Store, oracle.pre_o2_rows

    def texture_buffer(values: array, fmt) -> tuple[int, int]:
        buffer, texture = gl.GLuint(), gl.GLuint()
        gl.glGenBuffers(1, ctypes.byref(buffer))
        gl.glGenTextures(1, ctypes.byref(texture))
        gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, buffer.value)
        gl.glBufferData(gl.GL_TEXTURE_BUFFER, len(values) * 4, values.buffer_info()[0], gl.GL_STATIC_DRAW)
        gl.glBindTexture(gl.GL_TEXTURE_BUFFER, texture.value)
        gl.glTexBuffer(gl.GL_TEXTURE_BUFFER, fmt, buffer.value)
        gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, 0)
        gl.glBindTexture(gl.GL_TEXTURE_BUFFER, 0)
        return buffer.value, texture.value

    class OffStore(GLRenderStore):
        def _flush_face_data(self) -> bool:
            return False

    class CachedPreO2Store(PreO2Store):
        """The oracle with its rows uploaded once (the oracle itself re-uploads them per draw)."""

        def _flush_face_data(self) -> bool:
            ready = GLRenderStore._flush_face_data(self)
            if self._rows_gl is None:
                self._rows_gl = texture_buffer(pre_o2_rows(self.source), gl.GL_RGBA32F)
            gl.glActiveTexture(gl.GL_TEXTURE0 + 1)
            gl.glBindTexture(gl.GL_TEXTURE_BUFFER, self._rows_gl[1])
            gl.glActiveTexture(gl.GL_TEXTURE0)
            return ready

    class RgbaStore(GLRenderStore):
        """O2 with one RGBA32F texel per vertex value, from padded copies of the RenderMesh's mirrors."""

        _program = None
        _textured_program = None

        def __init__(self, stats) -> None:
            super().__init__(stats)
            self.source = None
            self._copies: dict[str, int] = {}

        @classmethod
        def program(cls):
            if cls._program is None:
                _register_sampler_buffer_uniform()
                cls._program = ShaderProgram(Shader(VERTEX_SRC, "vertex"), Shader(rgba_fragment_source(), "fragment"))
            return cls._program

        def _bind_vertex_textures(self, vlist) -> bool:
            from viewport.gl_render_store import _VERTEX_TEXTURES

            for name, mirror in (("position", "positions"), ("normal", "normals")):
                if name not in self._copies:
                    values = self.source._mirror[mirror]
                    if hasattr(values, "reshape"):  # since O3 stage 1 a float32 array (slots x 3), before an array('f')
                        values = array("f", values.reshape(-1).tobytes())
                    padded = array("f", bytes(4 * 4 * (len(values) // 3)))
                    for k in range(3):
                        padded[k::4] = values[k::3]
                    self._copies[name] = texture_buffer(padded, gl.GL_RGBA32F)[1]
                unit = _VERTEX_TEXTURES[name][0]
                gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
                gl.glBindTexture(gl.GL_TEXTURE_BUFFER, self._copies[name])
            gl.glActiveTexture(gl.GL_TEXTURE0)
            return True

        def _set_face_samplers(self, program, textured: bool, vlist) -> None:
            super()._set_face_samplers(program, textured, vlist)
            program["u_vertex_base"] = 0  # the copies are indexed by slot

    return OffStore, CachedPreO2Store, RgbaStore


def measure(path: Path, size: tuple[int, int], draws: int, flat: bool) -> list[str]:
    import pyglet
    from pyglet import gl

    import drag_cost.probe_drag_gl as drag_gl
    from drag_cost.probe_morph_gl import build_app
    from viewport.gl_render_store import GLRenderStore
    from viewport.render_mesh import RenderMesh

    drag_gl.WIDTH, drag_gl.HEIGHT = size  # `build_app` opens its window at this size
    import drag_cost.probe_morph_gl as morph_gl

    morph_gl.WIDTH, morph_gl.HEIGHT = size
    window, app = build_app(path)
    viewport, camera, mesh = app.viewport, app.camera, app.scene.mesh
    light = viewport.light_uniforms()
    material = viewport.render_mesh.material
    off_store, pre_store, rgba_store = store_classes()
    meshes = {}
    for name, store_type in zip(VARIANTS, (off_store, pre_store, GLRenderStore, rgba_store)):
        rm = RenderMesh(mesh, store_type=store_type)
        if hasattr(rm.store, "source"):
            rm.store.source = rm
        rm.bind_camera(camera)
        rm.mark_camera_dirty(aspect=size[0] / size[1])
        if material is not None:
            rm.bind_material(material)
            rm.mark_material_dirty()
        rm.sync()
        rm.store.set_draw_style(flat=flat, polygon_offset=False)
        rm.store.set_light_uniforms(light)
        meshes[name] = rm
    width, height = window.get_framebuffer_size()
    query = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(query))
    samples: dict[str, list[float]] = {name: [] for name in VARIANTS}
    cpu: dict[str, list[float]] = {name: [] for name in VARIANTS}
    images: dict[str, bytes] = {}
    for round_ in range(WARMUP_ROUNDS + draws):
        for name, rm in meshes.items():
            window.switch_to()
            gl.glViewport(0, 0, width, height)
            gl.glClearColor(0.1, 0.1, 0.11, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            gl.glFinish()
            start = time.perf_counter()
            gl.glBeginQuery(gl.GL_TIME_ELAPSED, query.value)
            rm.render(camera)
            gl.glEndQuery(gl.GL_TIME_ELAPSED)
            gl.glFinish()
            elapsed = (time.perf_counter() - start) * 1000.0
            value = ctypes.c_uint64()
            gl.glGetQueryObjectui64v(query.value, gl.GL_QUERY_RESULT, ctypes.byref(value))
            if round_ >= WARMUP_ROUNDS:
                samples[name].append(value.value / 1e6)
                cpu[name].append(elapsed)
            if round_ == WARMUP_ROUNDS + draws - 1:
                buf = (gl.GLubyte * (width * height * 3))()
                gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
                gl.glReadPixels(0, 0, width, height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
                images[name] = bytes(buf)
    background = images["o2"][0:3]
    covered = sum(1 for i in range(0, len(images["o2"]), 3) if images["o2"][i:i + 3] != background)
    lines = [
        f"[{path.stem}] {len(mesh.all_vertex_ids())} V / {len(mesh.all_face_ids())} F, {width}x{height}, "
        f"{'Flat' if flat else 'Smooth'}, {covered} px covered, {draws} rounds after {WARMUP_ROUNDS}",
        f"  {'variant':<9} {'GPU p50':>9} {'min':>8} {'max':>8}   {'draw+finish p50':>15}   image vs o2",
    ]
    for name in VARIANTS:
        gpu = samples[name]
        same = images[name] == images["o2"]
        differing = 0 if same else sum(
            1 for i in range(0, len(images[name]), 3) if images[name][i:i + 3] != images["o2"][i:i + 3]
        )
        verdict = "identical" if same else f"{differing} px differ" + ("" if name == "off" else "  <-- MUST BE IDENTICAL")
        lines.append(
            f"  {name:<9} {statistics.median(gpu):9.2f} {min(gpu):8.2f} {max(gpu):8.2f}   "
            f"{statistics.median(cpu[name]):15.2f}   {verdict}"
        )
    if max(max(v) for v in samples.values()) > 2.5 * min(min(v) for v in samples.values() if min(v) > 0.5) \
            and min(min(v) for v in samples.values()) > 0.5:
        lines.append("  NOTE the GPU times vary a lot: is the driver set to maximum performance?")
    for rm in meshes.values():
        rm.store.release()
    window.close()
    return lines


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = resolve_asset(args.asset)
    import pyglet

    from drag_cost.probe_d3_acceptance import source_state
    from drag_cost.probe_drag_gl import machine_info

    probe = pyglet.window.Window(width=64, height=64, visible=False)
    info = machine_info(pyglet.gl.gl_info.get_version_string(), pyglet.gl.gl_info.get_renderer())
    probe.close()
    print("Shading GPU probe (2026-11-11): one full shaded pass per face-data layout, GL_TIME_ELAPSED, ms")
    for line in info:
        print(line)
    print(f"Source: {source_state()}")
    print()
    for line in measure(path, tuple(args.size), args.draws, args.flat):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
