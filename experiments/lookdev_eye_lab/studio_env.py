"""Procedural studio environment of the Eye Proof (D-L4, Manu 2026-11-13: "reproduzierbar, keine HDRI-Dateien") and
its CPU prefilter into a cube mip chain (GL-free, NumPy only).

The recipe is the reference PC's reading for P1 (`lookdev_gpu_probe/RESULTS_REFERENCE_PC_2026-11-13.md` §8):

- **Face convention:** `lookdev_gpu_probe.cube_math` (GL 3.3 table 3.21, verified on the 9800 GTX by checks A and D's
  off path). Texel (i, j) of face f lies at `cube_math.texel_directions`; nothing here re-derives it.
- **Chain:** RGBA16F, edge `size` down to **2^2** (the 1^2 level is not built; `GL_TEXTURE_MAX_LEVEL` = last index),
  each level prefiltered for the roughness the active roughness -> LOD mapping assigns to it
  (`eye_math.lod_to_roughness`), so "roughness 1" lands on the 2^2 level.
- **Corners:** after prefiltering, `cube_math.equalize_corners` per level: the driver takes a corner tap from one face
  (§4 there); equal corner texels make that irrelevant (INFERRED there, confirmed by the lab's `--probe` seam check).

**Environment** (scene-linear, neutral; all parameters in `StudioEnv`): a backdrop gradient (floor, horizon,
zenith), one large rectangular softbox (the key's direction by default) and one tall strip light (rim / fill). The
rectangles are Gaussian-edged boxes in angular coordinates (`eye_math.rect_term`), the same function T-D evaluates in
the shader with a roughness-dependent edge.

**Prefilter** (Karis 2013 split sum, N = V = R): level 0 is the radiance box-filtered over each texel (2 x 2
sub-positions); level L > 0 integrates the radiance over GGX-importance-sampled directions (Hammersley, the same set for
every texel, sub-positions interleaved over the samples so the texel footprint is filtered too), weighted by N·L. The
radiance is evaluated analytically, so no source texture and no mip-of-source trick is needed. The result is cached as
`.npz` under `out/cache/` (ignored by git), keyed by every input.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import astuple, dataclass, field
from pathlib import Path

import numpy as np

from lookdev_gpu_probe import cube_math as cm

from . import eye_math as em

PREFILTER_VERSION = 1
#: Directions evaluated per prefiltered level at most (texels x samples); sets the sample count per level.
SAMPLE_BUDGET = 2_000_000
MIN_SAMPLES, MAX_SAMPLES = 64, 2048
LAST_SIZE = 2  # the chain ends at 2^2
RGBM_RANGE = 16.0


def local_direction(azimuth: float, elevation: float) -> np.ndarray:
    """`viewport.light_rig.local_direction` (az 0 / el 0 = +Z, the eye's front; az 90 = +X), as an array."""
    az, el = math.radians(azimuth), math.radians(elevation)
    return np.array([math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az)])


@dataclass(frozen=True)
class RectLight:
    """A rectangular area light seen from the eye: centre direction (az / el, degrees), angular half-sizes
    (degrees) and scene-linear radiance."""

    azimuth: float
    elevation: float
    half_width: float
    half_height: float
    radiance: tuple[float, float, float]

    def frame(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(centre, right, up) unit vectors; `up` is the world-up side of the light."""
        c = local_direction(self.azimuth, self.elevation)
        right = np.cross(np.array([0.0, 1.0, 0.0]), c)
        right /= np.linalg.norm(right)
        return c, right, np.cross(c, right)


@dataclass(frozen=True)
class StudioEnv:
    zenith: tuple[float, float, float] = (0.20, 0.20, 0.20)
    horizon: tuple[float, float, float] = (0.12, 0.12, 0.12)
    floor: tuple[float, float, float] = (0.035, 0.035, 0.035)
    horizon_width: float = 0.05
    #: The rectangles' own edge (radians): about one level-0 texel at 128^2 (90 deg / 128 = 0.70 deg).
    edge_sigma: float = math.radians(0.5)
    lights: tuple[RectLight, ...] = field(default_factory=lambda: (
        RectLight(35.0, 25.0, 18.0, 13.0, (8.0, 8.0, 8.0)),  # key softbox
        RectLight(-115.0, 10.0, 4.0, 32.0, (4.0, 4.0, 4.0)),  # strip (rim)
    ))

    def key(self) -> RectLight:
        return self.lights[0]

    def fingerprint(self) -> str:
        return hashlib.sha1(repr(astuple(self)).encode()).hexdigest()[:12]


DEFAULT_ENV = StudioEnv()


def radiance(d: np.ndarray, env: StudioEnv = DEFAULT_ENV, sigma: float | None = None,
             horizon_width: float | None = None) -> np.ndarray:
    """Scene-linear radiance (..., 3) toward unit directions `d` (..., 3), in environment space. `sigma` /
    `horizon_width` override the edges (T-D's blurred variant); default: the sharp environment."""
    d = np.asarray(d, dtype=np.float64)
    sigma = env.edge_sigma if sigma is None else sigma
    out = em.backdrop(d, env.zenith, env.horizon, env.floor,
                      env.horizon_width if horizon_width is None else horizon_width)
    for light in env.lights:
        c, r, u = light.frame()
        w = em.rect_term(d, c, r, u, math.radians(light.half_width), math.radians(light.half_height), sigma)
        out = out + w[..., None] * np.asarray(light.radiance)
    return out


def td_radiance(d: np.ndarray, roughness, env: StudioEnv = DEFAULT_ENV) -> np.ndarray:
    """T-D: the analytic environment as seen by a lobe of `roughness` (the shader's `td_env`)."""
    sigma = em.td_sigma(env.edge_sigma, roughness)
    width = math.sqrt(env.horizon_width ** 2 + float(em.td_lobe(roughness)) ** 2)
    return radiance(d, env, sigma=float(sigma), horizon_width=width)


def ambient_colours(env: StudioEnv = DEFAULT_ENV, n: int = 256) -> tuple[np.ndarray, np.ndarray]:
    """(sky, ground): the cosine-weighted mean radiance seen by a normal pointing up / down (irradiance / pi). The
    shaders' diffuse ambient is `mix(ground, sky, 0.5 + 0.5 N.y)` - the same for every technique, so the techniques
    differ only in their specular."""
    d = cm.equirect_directions(2 * n, n).reshape(-1, 3)
    lat = (0.5 - (np.arange(n) + 0.5) / n) * math.pi
    solid = np.repeat(np.cos(lat) * (math.pi / n) * (2.0 * math.pi / (2 * n)), 2 * n)
    rad = radiance(d, env)
    out = []
    for sign in (1.0, -1.0):
        cos = np.maximum(sign * d[:, 1], 0.0)
        out.append((rad * (cos * solid)[:, None]).sum(axis=0) / math.pi)
    return out[0], out[1]


# -- prefilter -------------------------------------------------------------------------------------------------------


def chain_sizes(size: int) -> list[int]:
    """`size` down to 2: 128 -> [128, 64, 32, 16, 8, 4, 2] (7 levels, last index 6)."""
    return [n for n in cm.level_sizes(size) if n >= LAST_SIZE]


def hammersley(count: int) -> np.ndarray:
    i = np.arange(count, dtype=np.uint32)
    bits = i.copy()
    bits = ((bits << 16) | (bits >> 16)) & 0xFFFFFFFF
    bits = ((bits & 0x55555555) << 1) | ((bits & 0xAAAAAAAA) >> 1)
    bits = ((bits & 0x33333333) << 2) | ((bits & 0xCCCCCCCC) >> 2)
    bits = ((bits & 0x0F0F0F0F) << 4) | ((bits & 0xF0F0F0F0) >> 4)
    bits = ((bits & 0x00FF00FF) << 8) | ((bits & 0xFF00FF00) >> 8)
    return np.stack([(i + 0.5) / count, bits.astype(np.float64) / 2.0 ** 32], axis=-1)


def _sub_directions(n: int) -> np.ndarray:
    """Directions through the 2 x 2 sub-positions of every texel, shape (4, 6, n, n, 3), unit length."""
    out = []
    for oj in (0.25, 0.75):
        for oi in (0.25, 0.75):
            t, s = np.meshgrid((np.arange(n) + oj) / n, (np.arange(n) + oi) / n, indexing="ij")
            d = np.stack([cm.face_st_to_direction(f, s, t) for f in range(6)])
            out.append(d / np.linalg.norm(d, axis=-1, keepdims=True))
    return np.stack(out)


def _frames(nrm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    up = np.where(np.abs(nrm[..., 2:3]) < 0.999, np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0]))
    tangent = np.cross(up, nrm)
    tangent /= np.linalg.norm(tangent, axis=-1, keepdims=True)
    return tangent, np.cross(nrm, tangent)


def samples_for(n: int) -> int:
    texels = 6 * n * n
    count = 1 << max(0, int(math.ceil(math.log2(max(SAMPLE_BUDGET / texels, 1.0)))))
    return int(min(MAX_SAMPLES, max(MIN_SAMPLES, count)))


def prefilter_level(env: StudioEnv, n: int, roughness: float, samples: int, chunk: int = 32) -> np.ndarray:
    """One level (6, n, n, 3): the N·L-weighted GGX average of the radiance around each texel direction."""
    subs = _sub_directions(n).reshape(4, -1, 3)
    if roughness <= 0.0:
        return radiance(subs, env).mean(axis=0).reshape(6, n, n, 3)
    alpha = roughness * roughness
    xi = hammersley(samples)
    frames = [_frames(subs[k]) for k in range(4)]
    acc = np.zeros((subs.shape[1], 3))
    weight = np.zeros(subs.shape[1])
    for k in range(4):
        tangent, bitangent = frames[k]
        nrm = subs[k]
        mine = xi[k::4]
        for start in range(0, len(mine), chunk):
            x = mine[start:start + chunk]
            phi = 2.0 * math.pi * x[:, 0]
            cos_t = np.sqrt((1.0 - x[:, 1]) / (1.0 + (alpha * alpha - 1.0) * x[:, 1]))
            sin_t = np.sqrt(1.0 - cos_t * cos_t)
            hx, hy, hz = sin_t * np.cos(phi), sin_t * np.sin(phi), cos_t
            h = (tangent[:, None, :] * hx[None, :, None] + bitangent[:, None, :] * hy[None, :, None]
                 + nrm[:, None, :] * hz[None, :, None])
            nh = np.sum(nrm[:, None, :] * h, axis=-1)
            light = 2.0 * nh[..., None] * h - nrm[:, None, :]
            nl = np.maximum(np.sum(nrm[:, None, :] * light, axis=-1), 0.0)
            acc += np.sum(radiance(light, env) * nl[..., None], axis=1)
            weight += nl.sum(axis=1)
    return (acc / np.maximum(weight, 1e-12)[:, None]).reshape(6, n, n, 3)


@dataclass
class Prefiltered:
    levels: list[np.ndarray]  # (6, n, n, 3) per level, corners equalized
    roughness: list[float]  # per level
    mapping: int
    seconds: float  # prefilter time (0 when read from the cache)
    from_cache: bool
    samples: list[int]

    @property
    def last_level(self) -> int:
        return len(self.levels) - 1

    @property
    def size(self) -> int:
        return self.levels[0].shape[1]


def prefilter(env: StudioEnv, size: int, mapping: int, cache_dir: Path | None = None,
              equalize: bool = True, force: bool = False) -> Prefiltered:
    """The full chain for `mapping` (0 linear, 1 sqrt), from the cache when present (`force`: computed anyway, for
    the probe's prefilter time, and written to the cache)."""
    sizes = chain_sizes(size)
    last = len(sizes) - 1
    roughness = [float(em.lod_to_roughness(level, mapping, last)) for level in range(len(sizes))]
    samples = [1 if r == 0.0 else samples_for(n) for n, r in zip(sizes, roughness)]
    key = f"env_{env.fingerprint()}_{size}_{em.LOD_MAPPINGS[mapping]}_{int(equalize)}_v{PREFILTER_VERSION}"
    path = cache_dir / f"{key}_{SAMPLE_BUDGET}.npz" if cache_dir is not None else None
    if path is not None and path.exists() and not force:
        with np.load(path) as data:
            levels = [data[f"level_{k}"] for k in range(len(sizes))]
        return Prefiltered(levels, roughness, mapping, 0.0, True, samples)
    start = time.perf_counter()
    levels = [prefilter_level(env, n, r, s) for n, r, s in zip(sizes, roughness, samples)]
    if equalize:
        levels = [cm.equalize_corners(level) for level in levels]
    seconds = time.perf_counter() - start
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **{f"level_{k}": level for k, level in enumerate(levels)})
    return Prefiltered(levels, roughness, mapping, seconds, False, samples)


# -- upload encodings ----------------------------------------------------------------------------------------------


def to_rgba(level: np.ndarray) -> np.ndarray:
    """(6, n, n, 3) -> (6, n, n, 4) with alpha 1 (the RGBA16F upload)."""
    return np.concatenate([level, np.ones(level.shape[:-1] + (1,))], axis=-1)


def rgbm_encode(level: np.ndarray, value_range: float = RGBM_RANGE) -> np.ndarray:
    """RGBA8 fallback (audit §5.8): rgb / (m · range) and m = max(rgb) / range rounded up to 1/255, as [0, 1] floats
    that `cube_math.to_upload(..., RGBA8)` quantises. Values above `range` clamp."""
    level = np.clip(level, 0.0, value_range)
    m = np.clip(np.max(level, axis=-1, keepdims=True) / value_range, 1.0 / 255.0, 1.0)
    m = np.ceil(m * 255.0) / 255.0
    rgb = np.round(np.clip(level / (m * value_range), 0.0, 1.0) * 255.0) / 255.0
    return np.concatenate([rgb, m], axis=-1)


def rgbm_decode(rgbm: np.ndarray, value_range: float = RGBM_RANGE) -> np.ndarray:
    return rgbm[..., :3] * rgbm[..., 3:4] * value_range


def chain_bytes(size: int, bytes_per_texel: int) -> int:
    """Texture memory of the chain `size` .. 2^2 (no driver padding)."""
    return 6 * bytes_per_texel * sum(n * n for n in chain_sizes(size))


def footprint_spread(level: np.ndarray, centre: np.ndarray, floor: float) -> float:
    """Radiance-weighted mean squared angle (rad^2) from `centre` of the energy above `floor` in one level: how wide
    the softbox's footprint is. The roughness sweep must make it grow monotonically (audit §5.5)."""
    n = level.shape[1]
    d = cm.texel_directions(n)
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    # Solid angle of a texel at (s, t): (2/n)^2 / (1 + sc^2 + tc^2)^(3/2), sc, tc in [-1, 1].
    c = (np.arange(n) + 0.5) / n * 2.0 - 1.0
    tc, sc = np.meshgrid(c, c, indexing="ij")
    solid = (2.0 / n) ** 2 / (1.0 + sc * sc + tc * tc) ** 1.5
    w = np.maximum(level.mean(axis=-1) - floor, 0.0) * solid[None]
    angle = np.arccos(np.clip(np.sum(d * centre, axis=-1), -1.0, 1.0))
    near = angle < math.radians(90.0)  # the key's hemisphere: the strip light stays out
    w = np.where(near, w, 0.0)
    return float(np.sum(w * angle * angle) / max(np.sum(w), 1e-12))
