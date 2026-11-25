"""Alpha images for the alpha tip (AD-037 §12 Phase 4a; proposal 2026-11-25 §4.4).

An **alpha** is an 8-bit grey image, white = paint, row 0 at the top. `AlphaImage` holds it with a **mip chain** (2x2 box
halving down to `MIP_MIN` px on the long side while the short side keeps 2 px, built once) so a large alpha stamped over
few texels does not alias into noise: a placement picks the level whose long side is closest to the stamp's diameter in texels (`level_for`). `sample`
reads one level **bilinearly**, vectorised over the gathered texels (one `take` of the four neighbours and a lerp; uint8
becomes float32 only for those texels); outside the image's rectangle the value is 0.

The stamp's world radius (P-7) is the half-extent of the alpha's **long** side; `half_extents` gives both half-extents
in units of that radius (the long one is 1); `reach` how far from the centre the alpha paints at all (the gather's
radius; a round pore patch ~1 instead of its square's √2).

**Test alphas** (4a only, no library yet: §9 "test-alpha chooser"): six procedural images (`TEST_ALPHAS`: Poren, Ader,
Kratzer, Fleck, Punkte, Quadrat), deterministic (fixed seeds, NumPy only, our own work), each with a black border,
generated on first use and cached (`generated_alpha`). The starter set, import and presets are 4c.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

#: The smallest mip level's long side in px (`PROVISIONAL`, proposal §4.4: "down to 4 px").
MIP_MIN = 4


def _halve(level: np.ndarray) -> np.ndarray:
    """A 2x2 box halving (an odd last row / column repeats the edge)."""
    h, w = level.shape
    if h % 2:
        level = np.concatenate((level, level[-1:]), axis=0)
    if w % 2:
        level = np.concatenate((level, level[:, -1:]), axis=1)
    f = level.astype(np.uint16)
    s = f[0::2, 0::2] + f[1::2, 0::2] + f[0::2, 1::2] + f[1::2, 1::2]
    return ((s + 2) // 4).astype(np.uint8)


@dataclass(frozen=True, eq=False)
class AlphaImage:
    id: str
    name: str
    pixels: np.ndarray  # (h, w) uint8, row 0 at the top
    mips: tuple[np.ndarray, ...] = field(default=())
    #: the farthest painting pixel's distance from the centre in units of the stamp radius (half a pixel added); the
    #: stamp gathers only within it - beyond, the alpha is 0 (a round pore patch needs ~1, its square's corners √2)
    reach: float = 0.0

    @classmethod
    def from_pixels(cls, id: str, name: str, pixels) -> "AlphaImage":
        pixels = np.ascontiguousarray(pixels, dtype=np.uint8)
        if pixels.ndim != 2 or min(pixels.shape) < 2:
            raise ValueError(f"an alpha is a 2D grey image, got shape {pixels.shape}")
        levels = [pixels]
        while max(levels[-1].shape) > MIP_MIN and min(levels[-1].shape) >= 4:  # every level at least 2 px wide
            levels.append(np.ascontiguousarray(_halve(levels[-1])))
        h, w = pixels.shape
        half = max(h, w) / 2.0
        ys, xs = np.nonzero(pixels)
        if ys.size:  # the farthest pixel's farthest corner from the centre
            dx = np.maximum(np.abs(xs - w / 2.0), np.abs(xs + 1.0 - w / 2.0))
            dy = np.maximum(np.abs(ys - h / 2.0), np.abs(ys + 1.0 - h / 2.0))
            reach = float(np.hypot(dx, dy).max()) / half
        else:
            reach = 0.0
        return cls(id, name, pixels, tuple(levels), reach)

    @property
    def size(self) -> int:
        """The long side in px (level 0)."""
        return max(self.pixels.shape)

    @property
    def half_extents(self) -> tuple[float, float]:
        """(half width, half height) in units of the stamp radius: the long side's is 1."""
        h, w = self.pixels.shape
        long = float(max(h, w))
        return w / long, h / long

    def level_for(self, diameter_texels: float) -> int:
        """The mip level whose long side is closest to a stamp `diameter_texels` across (log scale)."""
        if diameter_texels <= 0.0:
            return len(self.mips) - 1
        level = int(round(math.log2(max(self.size / diameter_texels, 1.0))))
        return min(max(level, 0), len(self.mips) - 1)

    def sample_local(self, level: int, a: np.ndarray, beta: np.ndarray) -> np.ndarray:
        """`sample` at a stamp's local coordinates (`a` along its width, `beta` up, in stamp radii; inside the rectangle
        - the caller has cut it): the image coordinates' affine map folded into the read."""
        image = self.mips[level]
        h, w = image.shape
        hw, hh = self.half_extents
        x = np.asarray(a, dtype=np.float32) * np.float32(w / (2.0 * hw)) + np.float32(w / 2.0 - 0.5)
        y = np.asarray(beta, dtype=np.float32) * np.float32(-h / (2.0 * hh)) + np.float32(h / 2.0 - 0.5)
        return self._bilinear(image, x, y)

    @staticmethod
    def _bilinear(image: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        h, w = image.shape
        x = np.clip(x, 0.0, np.float32(w - 1), out=x)
        y = np.clip(y, 0.0, np.float32(h - 1), out=y)
        x0 = np.minimum(x.astype(np.int64), w - 2)
        y0 = np.minimum(y.astype(np.int64), h - 2)
        fx = (x - x0)[:, None]
        fy = (y - y0)[:, None]
        corners = image.reshape(-1).take((y0 * w + x0)[:, None] + np.array((0, 1, w, w + 1))).astype(np.float32)
        top = corners[:, 0:1] + (corners[:, 1:2] - corners[:, 0:1]) * fx
        bottom = corners[:, 2:3] + (corners[:, 3:4] - corners[:, 2:3]) * fx
        return ((top + (bottom - top) * fy) * np.float32(1.0 / 255.0))[:, 0]

    def sample(self, level: int, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Bilinear coverage in [0, 1] (float32) at image coordinates `u` (0 left - 1 right), `v` (0 top - 1 bottom) on
        `level`; 0 outside [0, 1]². The edge texels extend to the border (the coordinate is clamped, which reads the
        same as clamping the four neighbours' indices); one `take` reads all four neighbours."""
        image = self.mips[level]
        h, w = image.shape
        u = np.asarray(u, dtype=np.float32)
        v = np.asarray(v, dtype=np.float32)
        value = self._bilinear(image, u * np.float32(w) - np.float32(0.5), v * np.float32(h) - np.float32(0.5))
        outside = (u < 0.0) | (u > 1.0) | (v < 0.0) | (v > 1.0)
        if outside.any():
            value[outside] = 0.0
        return value


# -- the test alphas (4a) ------------------------------------------------------------------------------------------


def _noise(shape: tuple[int, int], cell: int, rng: np.random.Generator) -> np.ndarray:
    """Value noise: a random grid every `cell` px, bilinearly interpolated, in [0, 1]."""
    h, w = shape
    gh, gw = h // cell + 2, w // cell + 2
    grid = rng.random((gh, gw))
    y = np.arange(h) / cell
    x = np.arange(w) / cell
    y0, x0 = y.astype(int), x.astype(int)
    fy, fx = (y - y0)[:, None], (x - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = grid[y0][:, x0]
    b = grid[y0][:, x0 + 1]
    c = grid[y0 + 1][:, x0]
    d = grid[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _fbm(shape, cell: int, octaves: int, rng) -> np.ndarray:
    total, amp, norm = np.zeros(shape), 1.0, 0.0
    for _ in range(octaves):
        total += amp * _noise(shape, max(cell, 1), rng)
        norm += amp
        amp *= 0.5
        cell //= 2
    return total / norm


def _border(image: np.ndarray, width: int) -> np.ndarray:
    """`image` faded to black within `width` px of its edge (every alpha gets a black border)."""
    h, w = image.shape
    y = np.minimum(np.arange(h), np.arange(h)[::-1])[:, None]
    x = np.minimum(np.arange(w), np.arange(w)[::-1])[None, :]
    edge = np.clip(np.minimum(x, y) / float(width), 0.0, 1.0)
    return image * edge


def _segment_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / max(dx * dx + dy * dy, 1e-12), 0.0, 1.0)
    return np.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _stroke_path(image, points, widths, values) -> None:
    """Draws a polyline with per-point width and value into `image` (max blend, soft edge)."""
    h, w = image.shape
    for i in range(len(points) - 1):
        (ax, ay), (bx, by) = points[i], points[i + 1]
        width = max(widths[i], widths[i + 1])
        x0, x1 = int(max(min(ax, bx) - width - 2, 0)), int(min(max(ax, bx) + width + 3, w))
        y0, y1 = int(max(min(ay, by) - width - 2, 0)), int(min(max(ay, by) + width + 3, h))
        if x0 >= x1 or y0 >= y1:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        d = _segment_distance(xs + 0.5, ys + 0.5, ax, ay, bx, by)
        half = 0.5 * (widths[i] + widths[i + 1]) * 0.5
        value = 0.5 * (values[i] + values[i + 1])
        part = value * np.clip((half + 0.75 - d) / 1.5, 0.0, 1.0)
        image[y0:y1, x0:x1] = np.maximum(image[y0:y1, x0:x1], part)


def _soft_dots(image, centres, radii, values) -> None:
    h, w = image.shape
    for (cx, cy), r, value in zip(centres, radii, values):
        x0, x1 = int(max(cx - r - 1, 0)), int(min(cx + r + 2, w))
        y0, y1 = int(max(cy - r - 1, 0)), int(min(cy + r + 2, h))
        ys, xs = np.mgrid[y0:y1, x0:x1]
        d = np.hypot(xs + 0.5 - cx, ys + 0.5 - cy) / r
        part = value * np.clip(1.0 - d * d, 0.0, 1.0) ** 2
        image[y0:y1, x0:x1] = np.maximum(image[y0:y1, x0:x1], part)


def _pores() -> np.ndarray:
    rng = np.random.default_rng(101)
    size, cells = 256, 7
    image = np.zeros((size, size))
    step = size / cells
    centres, radii, values = [], [], []
    for gy in range(cells):
        for gx in range(cells):
            cx = (gx + 0.5 + rng.uniform(-0.35, 0.35)) * step
            cy = (gy + 0.5 + rng.uniform(-0.35, 0.35)) * step
            if math.hypot(cx - size / 2, cy - size / 2) > size * 0.46:
                continue
            centres.append((cx, cy))
            radii.append(rng.uniform(5.0, 11.0))
            values.append(rng.uniform(0.55, 1.0))
    _soft_dots(image, centres, radii, values)
    return _border(image, 10)


def _walk(rng, start, angle, steps, step, turn):
    points = [start]
    for _ in range(steps):
        angle += rng.normal(0.0, turn)
        x, y = points[-1]
        points.append((x + step * math.cos(angle), y + step * math.sin(angle)))
    return points, angle


def _vein() -> np.ndarray:
    rng = np.random.default_rng(202)
    h, w = 112, 320
    image = np.zeros((h, w))
    points, _ = _walk(rng, (14.0, h * 0.55), 0.0, 36, 8.0, 0.18)
    n = len(points)
    widths = np.linspace(7.0, 1.5, n)
    _stroke_path(image, points, widths, np.linspace(1.0, 0.75, n))
    for at, side in ((10, -1.0), (19, 1.0), (27, -1.0)):
        branch, _ = _walk(rng, points[at], side * 0.7, 12, 6.0, 0.25)
        m = len(branch)
        _stroke_path(image, branch, np.linspace(widths[at] * 0.7, 1.0, m), np.linspace(0.9, 0.6, m))
    return _border(image, 6)


def _scratch() -> np.ndarray:
    rng = np.random.default_rng(303)
    h, w = 64, 320
    image = np.zeros((h, w))
    for k, (y, width, value) in enumerate(((26.0, 2.6, 1.0), (36.0, 1.6, 0.8), (31.0, 1.2, 0.6))):
        x0, x1 = 12.0 + 14 * k, w - 12.0 - 22 * k
        xs = np.linspace(x0, x1, 40)
        ys = y + np.cumsum(rng.normal(0.0, 0.35, xs.size))
        fade = np.sin(np.linspace(0.15, math.pi - 0.15, xs.size)) * value
        _stroke_path(image, list(zip(xs, ys)), [width] * xs.size, fade * rng.uniform(0.75, 1.0, xs.size))
    return _border(image, 6)


def _stain() -> np.ndarray:
    rng = np.random.default_rng(404)
    size = 256
    n = _fbm((size, size), 64, 5, rng)
    y, x = np.mgrid[0:size, 0:size]
    r = np.hypot(x + 0.5 - size / 2, y + 0.5 - size / 2) / (size / 2)
    field_ = n * 0.9 + (1.0 - r) * 0.6
    image = np.clip((field_ - 0.55) / 0.22, 0.0, 1.0) * (0.65 + 0.35 * _fbm((size, size), 16, 3, rng))
    return _border(image, 12)


def _dots() -> np.ndarray:
    rng = np.random.default_rng(505)
    size = 128
    image = np.zeros((size, size))
    centres = [(rng.uniform(22, size - 22), rng.uniform(22, size - 22)) for _ in range(7)]
    _soft_dots(image, centres, rng.uniform(5.0, 13.0, 7), rng.uniform(0.7, 1.0, 7))
    return _border(image, 6)


def _square() -> np.ndarray:
    size = 64
    edge = np.minimum(np.arange(size), np.arange(size)[::-1]) + 0.5
    ramp = np.clip((edge - 6.0) / 2.0, 0.0, 1.0)
    return np.minimum(ramp[:, None], ramp[None, :])


#: id -> (German name, generator); the 4a chooser's order.
TEST_ALPHAS: dict[str, tuple[str, object]] = {
    "test/poren": ("Poren", _pores),
    "test/ader": ("Ader", _vein),
    "test/kratzer": ("Kratzer", _scratch),
    "test/fleck": ("Fleck", _stain),
    "test/punkte": ("Punkte", _dots),
    "test/quadrat": ("Quadrat", _square),
}


@lru_cache(maxsize=None)
def generated_alpha(alpha_id: str) -> AlphaImage:
    """The generated test alpha `alpha_id` (one of `TEST_ALPHAS`), cached."""
    name, make = TEST_ALPHAS[alpha_id]
    pixels = np.clip(np.rint(make() * 255.0), 0, 255).astype(np.uint8)
    return AlphaImage.from_pixels(alpha_id, name, pixels)


def resolve(alpha_id: str | None) -> AlphaImage | None:
    """The alpha of a tip (`None`: the round tip; an unknown id is None too - the round tip paints, 4c says so)."""
    if alpha_id is None or alpha_id not in TEST_ALPHAS:
        return None
    return generated_alpha(alpha_id)


def alpha_name(alpha_id: str | None) -> str:
    if alpha_id is None:
        return "Rund"
    entry = TEST_ALPHAS.get(alpha_id)
    return entry[0] if entry is not None else alpha_id
