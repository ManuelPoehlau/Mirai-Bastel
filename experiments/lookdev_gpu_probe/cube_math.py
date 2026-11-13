"""GL-free part of the Lookdev GL capability probe (2026-11-13): the cube-map face convention, the test patterns and
their expected values, the sample sets, the interpretation of the read-back numbers, and small helpers (PNG writer,
source state, software-renderer detection).

Everything here is NumPy / stdlib only, so it is tested headless (`tests/test_cube_math.py`). The GL side lives in
`probe_gl_caps.py`.

Cube-map convention: OpenGL 3.3 core spec, table 3.21 ("Selection of cube map images"): the major axis of the
direction picks the face, then
    +X: sc = -rz, tc = -ry        -X: sc = +rz, tc = -ry
    +Y: sc = +rx, tc = +rz        -Y: sc = +rx, tc = -rz
    +Z: sc = +rx, tc = -ry        -Z: sc = -rx, tc = -ry
and s = (sc / |ma| + 1) / 2, t = (tc / |ma| + 1) / 2. Face index k is `GL_TEXTURE_CUBE_MAP_POSITIVE_X + k` in the order
+X, -X, +Y, -Y, +Z, -Z. Texel (i, j) of an n x n face image is column i (along s) of row j (along t); row 0 is the
first row `glTexImage2D` reads. A CPU prefilter for the Eye Proof must lay its faces out the same way.
"""

from __future__ import annotations

import math
import os
import re
import struct
import subprocess
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

FACE_NAMES = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")
PASS, FAIL, OPEN, INFO = "PASS", "FAIL", "OPEN", "INFO"

# -- formats ---------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CubeFormat:
    """One texture format under test. `internal` is the sized internal format, `upload` the client data type."""

    label: str
    internal: str  # "RGBA8" | "RGBA16F" | "RGBA32F"
    upload: str  # "ubyte" | "half" | "float"
    bytes_per_texel: int

    @property
    def hdr(self) -> bool:
        return self.internal != "RGBA8"

    @property
    def quantum(self) -> float:
        """The storage step of a [0, 1] value (0 for float formats: their rounding is modelled by `stored`)."""
        return 1.0 / 255.0 if self.internal == "RGBA8" else 0.0


RGBA8 = CubeFormat("RGBA8", "RGBA8", "ubyte", 4)
RGBA16F = CubeFormat("RGBA16F", "RGBA16F", "half", 8)
RGBA16F_FLOAT_UPLOAD = CubeFormat("RGBA16F/float-upload", "RGBA16F", "float", 8)
RGBA32F = CubeFormat("RGBA32F", "RGBA32F", "float", 16)
#: Allocation + sampling (check A) runs every variant, the other checks the three storage formats.
ALLOCATION_FORMATS = (RGBA8, RGBA16F, RGBA16F_FLOAT_UPLOAD, RGBA32F)
FORMATS = (RGBA8, RGBA16F, RGBA32F)


def to_upload(values: np.ndarray, fmt: CubeFormat) -> np.ndarray:
    """The client array `glTexImage2D` receives for intended `values` (float)."""
    if fmt.upload == "ubyte":
        return np.round(np.clip(values, 0.0, 1.0) * 255.0).astype(np.uint8)
    if fmt.upload == "half":
        return values.astype(np.float16)
    return values.astype(np.float32)


def stored(values: np.ndarray, fmt: CubeFormat) -> np.ndarray:
    """What a correct driver holds in the texture for intended `values`, as float64."""
    if fmt.internal == "RGBA8":
        return np.round(np.clip(values, 0.0, 1.0) * 255.0) / 255.0
    if fmt.internal == "RGBA16F":
        return values.astype(np.float32).astype(np.float16).astype(np.float64)
    return values.astype(np.float32).astype(np.float64)


def level_sizes(size: int) -> list[int]:
    """Edge lengths of a full mip chain: 64 -> [64, 32, ..., 1]."""
    if size < 1 or size & (size - 1):
        raise ValueError(f"cube size must be a power of two, got {size}")
    return [size >> k for k in range(size.bit_length())]


def cube_bytes(size: int, bytes_per_texel: int, mips: bool = True) -> int:
    """Texture memory of a cube map (6 faces), with or without its full mip chain (driver padding not included)."""
    sizes = level_sizes(size) if mips else [size]
    return 6 * bytes_per_texel * sum(n * n for n in sizes)


# -- face convention -------------------------------------------------------------------------------------------------


def direction_to_face_st(d: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(face index, s, t) for directions `d` (..., 3), per the spec table in the module docstring. Ties between two
    axes go to the lower axis; the probe never samples exact ties."""
    d = np.asarray(d, dtype=np.float64)
    x, y, z = d[..., 0], d[..., 1], d[..., 2]
    ax, ay, az = np.abs(x), np.abs(y), np.abs(z)
    axis = np.where((ax >= ay) & (ax >= az), 0, np.where(ay >= az, 1, 2))
    neg = np.choose(axis, (x, y, z)) < 0
    face = 2 * axis + neg
    ma = np.choose(axis, (ax, ay, az))
    sc = np.choose(face, (-z, z, x, x, x, -x))
    tc = np.choose(face, (-y, -y, z, -z, -y, -y))
    return face, (sc / ma + 1.0) / 2.0, (tc / ma + 1.0) / 2.0


def face_st_to_direction(face, s, t) -> np.ndarray:
    """The (unnormalised) direction that `direction_to_face_st` maps to (face, s, t); broadcasts."""
    face, s, t = np.broadcast_arrays(np.asarray(face), np.asarray(s, dtype=np.float64), np.asarray(t, dtype=np.float64))
    sc, tc = 2.0 * s - 1.0, 2.0 * t - 1.0
    one = np.ones_like(sc)
    x = np.choose(face, (one, -one, sc, sc, sc, -sc))
    y = np.choose(face, (-tc, -tc, one, -one, -tc, -tc))
    z = np.choose(face, (-sc, sc, tc, -tc, one, -one))
    return np.stack([x, y, z], axis=-1)


def texel_directions(n: int) -> np.ndarray:
    """Directions through the texel centres of an n x n cube level, shape (6, n, n, 3) indexed [face, row j, col i]."""
    centres = (np.arange(n) + 0.5) / n
    t, s = np.meshgrid(centres, centres, indexing="ij")
    return np.stack([face_st_to_direction(f, s, t) for f in range(6)])


def bilinear_clamp(level: np.ndarray, d: np.ndarray) -> np.ndarray:
    """What a lookup into `level` (6, n, n, 4) returns for directions `d` (..., 3) WITHOUT seamless filtering: the
    face is chosen by the major axis, then plain bilinear filtering with CLAMP_TO_EDGE inside that face only (GL 3.3
    §3.8.10 / §3.8.11). This is the expected result of the seamless-off pass and the size of its edge seams."""
    n = level.shape[1]
    face, s, t = direction_to_face_st(d)
    x, y = s * n - 0.5, t * n - 0.5
    i0, j0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - i0)[..., None], (y - j0)[..., None]
    i1, j1 = np.clip(i0 + 1, 0, n - 1), np.clip(j0 + 1, 0, n - 1)
    i0, j0 = np.clip(i0, 0, n - 1), np.clip(j0, 0, n - 1)
    top = level[face, j0, i0] * (1.0 - fx) + level[face, j0, i1] * fx
    bottom = level[face, j1, i0] * (1.0 - fx) + level[face, j1, i1] * fx
    return top * (1.0 - fy) + bottom * fy


# -- patterns (intended values; one (6, n, n, 4) float64 array per mip level) ----------------------------------------


def quadrant_value(face: int, quadrant: int, hdr: bool) -> tuple[float, float, float, float]:
    """A value unique per (face, quadrant). Float formats carry values above 1 (up to 603) and down to 2^-10, which an
    8-bit store cannot keep; RGBA8 gets exact multiples of 1/255."""
    if hdr:
        return (face + 1.0 + 0.25 * quadrant, (quadrant + 1) * 2.0 ** -10, 100.0 * (face + 1) + quadrant,
                0.1 * (quadrant + 1))
    return ((40 * face + 10 * quadrant + 5) / 255.0, (250 - 40 * face - 10 * quadrant) / 255.0,
            17 * (quadrant + 1) / 255.0, (255 - 30 * quadrant) / 255.0)


def quadrant_pattern(size: int, hdr: bool) -> list[np.ndarray]:
    """Every level: four quadrants per face (q = [s >= 0.5] + 2 [t >= 0.5]) with `quadrant_value`."""
    table = np.array([[quadrant_value(f, q, hdr) for q in range(4)] for f in range(6)])
    levels = []
    for n in level_sizes(size):
        centres = (np.arange(n) + 0.5) / n
        q = (centres[None, :] >= 0.5).astype(int) + 2 * (centres[:, None] >= 0.5).astype(int)  # [row j, col i]
        levels.append(table[:, q])
    return levels


def quadrant_samples() -> tuple[np.ndarray, list[tuple[int, int]]]:
    """24 directions through the quadrant centres (s, t in {0.25, 0.75}) of every face, and their (face, quadrant)."""
    dirs, keys = [], []
    for f in range(6):
        for q in range(4):
            s, t = 0.25 + 0.5 * (q & 1), 0.25 + 0.5 * (q >> 1)
            dirs.append(face_st_to_direction(f, s, t))
            keys.append((f, q))
    return np.array(dirs), keys


def marker_value(level: int, face: int, hdr: bool) -> tuple[float, float, float, float]:
    """A value per (level, face): R steps linearly with the level, G names the face."""
    if hdr:
        return 1.0 + 1.5 * level, 0.5 + 0.25 * face, 0.5, 1.0
    return (20 + 30 * level) / 255.0, (30 + 40 * face) / 255.0, 128 / 255.0, 1.0


def marker_pattern(size: int, hdr: bool) -> list[np.ndarray]:
    """Every texel of level L, face f holds `marker_value(L, f)`."""
    return [np.broadcast_to(np.array([marker_value(level, f, hdr) for f in range(6)])[:, None, None, :],
                            (6, n, n, 4)).copy()
            for level, n in enumerate(level_sizes(size))]


def marker_directions() -> tuple[np.ndarray, np.ndarray]:
    """Face centres and one off-centre point per face (12 directions), and their face index."""
    dirs = [face_st_to_direction(f, 0.5, 0.5) for f in range(6)] + [face_st_to_direction(f, 0.3, 0.7) for f in range(6)]
    return np.array(dirs), np.array(list(range(6)) * 2)


def marker_mask(lod_count: int) -> np.ndarray:
    """Which channels of the `marker_directions` samples (repeated per lod) are compared: everything at the face
    centres, but G (the face marker) not at the off-centre points - at the 2x2 and 1x1 levels seamless filtering blends
    the neighbouring face into an off-centre lookup by design (GL 3.3 §3.8.10), so only R / B / A must hold there."""
    mask = np.ones((12, 4), dtype=bool)
    mask[6:, 1] = False
    return np.tile(mask, (lod_count, 1))


def marker_expected(lod: float, face: int, levels: int, hdr: bool, stored_fn) -> np.ndarray:
    """`textureLod` of the marker cube with LINEAR_MIPMAP_LINEAR: the lod clamps to [0, levels - 1] and blends the two
    neighbouring levels linearly (GL 3.3 §3.8.11). `stored_fn` maps intended to stored values."""
    lod = min(max(lod, 0.0), levels - 1.0)
    lower = int(math.floor(lod))
    upper = min(lower + 1, levels - 1)
    frac = lod - lower
    a = stored_fn(np.array(marker_value(lower, face, hdr)))
    b = stored_fn(np.array(marker_value(upper, face, hdr)))
    return (1.0 - frac) * a + frac * b


def marker_step(hdr: bool) -> float:
    """The R difference between two neighbouring levels of the marker cube."""
    return 1.5 if hdr else 30 / 255.0


def gradient_step(hdr: bool) -> float:
    return 0.25 if hdr else 16 / 255.0


def gradient_pattern(size: int, hdr: bool) -> list[np.ndarray]:
    """Level 0: R = step * column i, G = step * row j on every face (linear, so bilinear filtering reproduces it
    exactly inside the face); higher levels hold a constant (they are not sampled)."""
    step = gradient_step(hdr)
    levels = []
    for k, n in enumerate(level_sizes(size)):
        level = np.empty((6, n, n, 4))
        if k == 0:
            j, i = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
            level[..., 0] = step * i
            level[..., 1] = step * j
        else:
            level[..., 0] = level[..., 1] = step * (size - 1) / 2.0
        level[..., 2] = 0.5
        level[..., 3] = 1.0
        levels.append(level)
    return levels


def gradient_samples(size: int, hdr: bool) -> tuple[np.ndarray, np.ndarray]:
    """Directions at texel coordinates x in [2, n - 3] by fifths of a texel (on and between texel centres; fifths are
    not exact in a binary weight, so the error shows the hardware's weight precision), three rows, every face; and the
    expected (R, G) = step * (x, y) of linear filtering. Two texels from the face edges, so neither the clamp nor
    seamless filtering touches them."""
    step = gradient_step(hdr)
    xs = np.round(np.arange(2.0, size - 3.0 + 1e-9, 0.2), 6)
    ys = np.array([2.0, size / 2.0 - 0.5, size - 3.25])
    dirs, expected = [], []
    for f in range(6):
        for y in ys:
            for x in xs:
                dirs.append(face_st_to_direction(f, (x + 0.5) / size, (y + 0.5) / size))
                expected.append((step * x, step * y))
    return np.array(dirs), np.array(expected)


def smooth_value(d: np.ndarray) -> np.ndarray:
    """A smooth, non-symmetric function of the direction in [0.05, 0.95]: continuous across every cube edge, so any
    step the sampler shows at an edge is a filtering seam."""
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    rgb = 0.5 + 0.45 * np.sin(2.5 * d + np.array([0.0, 1.0, 2.0]))
    return np.concatenate([rgb, np.ones(d.shape[:-1] + (1,))], axis=-1)


def smooth_pattern(size: int) -> list[np.ndarray]:
    """Every level holds `smooth_value` at its own texel centres: a stand-in for a prefiltered environment."""
    return [smooth_value(texel_directions(n)) for n in level_sizes(size)]


# -- seams -----------------------------------------------------------------------------------------------------------

#: The 12 cube edges as (axis a, sign a, axis b, sign b): the edge where face (a, sa) meets face (b, sb).
EDGES = tuple((a, sa, b, sb) for a, b in ((0, 1), (0, 2), (1, 2)) for sa in (1, -1) for sb in (1, -1))
SEAM_DELTA = 1e-4
#: Positions along the edge in cube coordinates; chosen off the texel boundaries of every level of a 64^2 cube.
SEAM_POSITIONS = (-0.7, -0.45, -0.2, 0.05, 0.3, 0.55, 0.8)


def seam_samples(delta: float = SEAM_DELTA, positions=SEAM_POSITIONS) -> dict[str, np.ndarray]:
    """Direction pairs straddling each of the 12 edges (`a` just inside face A, `b` just inside face B, `delta` from the
    edge in cube coordinates) at several positions along the edge, and interior pairs on face A with the same
    separation (the natural change of the content over that distance)."""
    out = {"a": [], "b": [], "ia": [], "ib": []}
    for a, sa, b, sb in EDGES:
        c = 3 - a - b
        for p in positions:
            for key, ca, cb in (("a", 1.0, 1.0 - delta), ("b", 1.0 - delta, 1.0),
                                ("ia", 1.0, 0.5), ("ib", 1.0, 0.5 - 2.0 * delta)):
                d = np.zeros(3)
                d[a], d[b], d[c] = sa * ca, sb * cb, p
                out[key].append(d)
    return {key: np.array(value) for key, value in out.items()}


def seam_step(level: np.ndarray, samples: dict[str, np.ndarray]) -> float:
    """The largest edge jump a lookup without seamless filtering shows at this level (`bilinear_clamp` on both sides of
    every pair): what the seamless-off pass should measure, and the seam that seamless filtering has to remove."""
    return max_jump(bilinear_clamp(level, samples["a"]), bilinear_clamp(level, samples["b"]))


def max_jump(values_a: np.ndarray, values_b: np.ndarray) -> float:
    return float(np.max(np.abs(values_a[..., :3] - values_b[..., :3])))


@dataclass
class SeamRow:
    level: int
    size: int
    step: float  # expected jump without seamless filtering (`seam_step`)
    jump_off: float  # measured, GL_TEXTURE_CUBE_MAP_SEAMLESS disabled
    jump_on: float  # measured, enabled
    interior: float  # measured, same separation inside a face


def seam_tolerance(row: SeamRow, quantum: float) -> float:
    """The largest edge jump still counted as continuous: a tenth of the clamp step, the content's own change over the
    pair's separation, or the storage / read-back step."""
    return max(0.1 * row.step, 4.0 * row.interior, 3.0 * quantum, 1e-5)


def seam_verdict(rows: list[SeamRow], quantum: float) -> tuple[str, str]:
    """(status, reading) of the seam test for one format. Seamless on must be continuous at every level; the off pass
    is expected to show the clamp seams `seam_step` predicts (a driver that filters seamlessly regardless is fine)."""
    seamless_ok = all(r.jump_on <= seam_tolerance(r, quantum) for r in rows)
    telling = [r for r in rows if r.step > 6.0 * quantum + 1e-4]  # levels where a clamp seam is measurable
    off_seams = bool(telling) and all(r.jump_off >= 0.5 * r.step for r in telling)
    if seamless_ok and off_seams:
        return PASS, "seamless on: continuous at every level; off: the predicted clamp seams (the switch works)"
    if seamless_ok:
        return PASS, "continuous with the switch on AND off: this driver filters across faces regardless of the switch"
    if all(abs(r.jump_on - r.jump_off) <= seam_tolerance(r, quantum) for r in telling):
        return FAIL, ("GL_TEXTURE_CUBE_MAP_SEAMLESS has no effect: seams stay when enabled -> CPU edge fix-up of the "
                      "prefiltered mips needed")
    worst = max(rows, key=lambda r: r.jump_on - seam_tolerance(r, quantum))
    return FAIL, (f"seams with the switch on (worst: level {worst.level}, jump {worst.jump_on:.4g} "
                  f"vs step {worst.step:.4g})")


# -- comparisons and statistics --------------------------------------------------------------------------------------


def max_error(measured: np.ndarray, expected: np.ndarray, mask: np.ndarray | None = None) -> float:
    """Largest absolute difference over the compared channels (`mask`: True = compared)."""
    diff = np.abs(np.asarray(measured, dtype=np.float64) - np.asarray(expected, dtype=np.float64))
    return float(np.max(np.where(mask, diff, 0.0) if mask is not None else diff))


def within(measured: np.ndarray, expected: np.ndarray, abs_tol: float, rel_tol: float,
           mask: np.ndarray | None = None) -> np.ndarray:
    """Per-sample: every compared channel within abs_tol + rel_tol * |expected|."""
    measured = np.asarray(measured, dtype=np.float64)
    expected = np.asarray(expected, dtype=np.float64)
    ok = np.abs(measured - expected) <= abs_tol + rel_tol * np.abs(expected)
    return np.all(ok | ~mask if mask is not None else ok, axis=-1)


def clamp_diagnosis(measured: np.ndarray, expected: np.ndarray) -> str:
    """A hint when a float format behaves like a fixed-point one."""
    measured, expected = np.asarray(measured), np.asarray(expected)
    if np.max(expected) > 1.0 and np.max(measured) <= 1.0 + 1e-6:
        return "values above 1 come back clamped to 1: stored or read back as fixed point, not float"
    return ""


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    k = (len(ordered) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def timing_summary(samples: list[float]) -> tuple[float, float, float, float]:
    """(p50, p95, min, max)."""
    return percentile(samples, 0.5), percentile(samples, 0.95), min(samples), max(samples)


def timing_unstable(rows: dict[str, list[float]]) -> bool:
    """Same rule as `drag_cost/probe_shading_gpu.py`: the GPU times of one run spread by more than 2.5x (only when the
    times are large enough to mean something) - usually the driver's power management."""
    lows = [min(v) for v in rows.values() if v]
    highs = [max(v) for v in rows.values() if v]
    return bool(lows) and min(lows) > 0.5 and max(highs) > 2.5 * min(lows)


# -- environment and reporting helpers -------------------------------------------------------------------------------

_SOFTWARE_RENDERERS = ("llvmpipe", "softpipe", "swrast", "lavapipe", "swiftshader", "gdi generic",
                       "microsoft basic render", "software rasterizer")


def software_renderer(renderer: str) -> bool:
    """True for a CPU rasterizer: its results are TESTED [C]-class at best and its timer is not a GPU timer."""
    name = renderer.lower()
    return any(s in name for s in _SOFTWARE_RENDERERS)


#: Extensions worth recording for Lookdev, with the reason. Names follow the GL registry.
RELEVANT_EXTENSIONS = (
    ("GL_EXT_texture_filter_anisotropic", "anisotropic filtering (iris / skin textures at grazing angles)"),
    ("GL_ARB_texture_filter_anisotropic", "the same, ARB name (core in GL 4.6)"),
    ("GL_NVX_gpu_memory_info", "NVIDIA free / total video memory"),
    ("GL_ATI_meminfo", "AMD free video memory (main PC, if AMD)"),
    ("GL_ARB_seamless_cube_map", "seamless cube filtering (core since GL 3.2)"),
    ("GL_AMD_seamless_cubemap_per_texture", "per-texture seamless switch"),
    ("GL_ARB_seamless_cubemap_per_texture", "per-texture seamless switch"),
    ("GL_ARB_texture_cube_map_array", "cube map arrays (GL 4.0)"),
    ("GL_ARB_texture_float", "float textures (core since GL 3.0)"),
    ("GL_ARB_half_float_pixel", "half-float client data (core since GL 3.0)"),
    ("GL_EXT_packed_float", "R11F_G11F_B10F, a compact HDR format"),
    ("GL_EXT_texture_shared_exponent", "RGB9_E5, a compact HDR format"),
    ("GL_EXT_texture_sRGB", "sRGB textures (core since GL 2.1)"),
    ("GL_ARB_framebuffer_sRGB", "sRGB framebuffers (core since GL 3.0)"),
    ("GL_EXT_texture_sRGB_decode", "switchable sRGB decode"),
    ("GL_ARB_texture_query_lod", "textureQueryLod (GL 4.0)"),
    ("GL_ARB_texture_storage", "immutable texture storage (GL 4.2)"),
    ("GL_ARB_timer_query", "GL_TIME_ELAPSED (core since GL 3.3)"),
    ("GL_ARB_texture_buffer_object_rgb32", "RGB32F buffer textures (known absent on the reference PC)"),
    ("GL_ARB_texture_multisample", "multisample textures (core since GL 3.2)"),
    ("GL_ARB_sample_shading", "per-sample shading (GL 4.0)"),
    ("GL_ARB_debug_output", "driver debug messages"),
    ("GL_KHR_debug", "driver debug messages (GL 4.3)"),
    ("GL_EXT_texture_compression_s3tc", "BC1-3 compressed textures"),
    ("GL_ARB_texture_compression_bptc", "BC6H HDR / BC7 compressed textures (GL 4.2)"),
)


def state_diff(before: dict, after: dict) -> list[str]:
    """Names whose value differs between two GL state snapshots, as 'name: before -> after'."""
    return [f"{key}: {before.get(key)} -> {after.get(key)}" for key in sorted(set(before) | set(after))
            if before.get(key) != after.get(key)]


def equirect_directions(width: int, height: int) -> np.ndarray:
    """Directions for a lat-long panorama, row 0 at the top (+Y), longitude 0 at the image centre looking down +Z."""
    lon = ((np.arange(width) + 0.5) / width * 2.0 - 1.0) * math.pi
    lat = (0.5 - (np.arange(height) + 0.5) / height) * math.pi
    lat, lon = np.meshgrid(lat, lon, indexing="ij")
    return np.stack([np.cos(lat) * np.sin(lon), np.sin(lat), np.cos(lat) * np.cos(lon)], axis=-1)


def write_png(path: Path, rgb: np.ndarray) -> None:
    """An 8-bit RGB PNG from a (h, w, 3) array in [0, 1] (zlib + struct, as `tests/test_obj_uvs.write_png`)."""
    pixels = np.round(np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)
    h, w = pixels.shape[:2]
    raw = b"".join(b"\x00" + pixels[row].tobytes() for row in range(h))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True, env=env).stdout.strip()


def source_state(repo: Path) -> str:
    """Commit, `src/` tree id and working-tree state of the checkout. A modified tree names the id of `src/` as it is on
    disk (written through a scratch index, the real index untouched), so it can be matched to a later commit."""
    try:
        head = _git(repo, "rev-parse", "--short=10", "HEAD")
        src_tree = _git(repo, "rev-parse", "--short=10", "HEAD:src")
        dirty = _git(repo, "status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.CalledProcessError):
        return "commit unknown (no git)"
    if not dirty:
        return f"commit {head}, src/ tree {src_tree}, working tree clean"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))
            _git(repo, "read-tree", "HEAD", env=env)
            _git(repo, "add", "-A", "--", "src", env=env)
            disk = _git(repo, "write-tree", "--prefix=src/", env=env)[:10]
    except (OSError, subprocess.CalledProcessError):
        disk = "unknown"
    return f"commit {head}, src/ tree {src_tree} at HEAD / {disk} on disk, working tree MODIFIED"


_COVERED = re.compile(r", (\d+)x(\d+), .*?, (\d+) px covered")


def coverage(header_line: str) -> tuple[int, int, int] | None:
    """(width, height, covered px) from the first line `drag_cost/probe_shading_gpu.measure` returns."""
    match = _COVERED.search(header_line)
    return tuple(int(g) for g in match.groups()) if match else None
