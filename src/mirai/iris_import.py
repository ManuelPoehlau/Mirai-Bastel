"""The iris image import of the Eye Lab (Eye LookDev phase 5, Manu 2026-11-16; assessment §C.3, AD-033 §19). NumPy, no
GL, no imgui: everything happens once, at import; nothing here runs while drawing.

An artist's image becomes a **copy** that the eye pass reads as it reads any iris image (the object's texture, AD-026)
with the radial fit (`EyeSpec.fit_pupil` / `fit_limbus`):
1. **Landmarks.** Two circles in the source image's pixels: the pupil edge and the iris edge (the visible limbus), each
   with its own centre. `estimate` suggests them (the eye lab's profile method, `experiments/lookdev_eye_lab/iris_fit`,
   extended by a centre); the artist corrects both in the Eye Lab.
2. **The copy** (`build_copy`): square, centred on the iris edge's circle, its iris edge at `TARGET_SHARE` of half its
   width. A pupil off the iris centre is moved onto it smoothly (the centre blends from the pupil's at the pupil edge to
   the iris edge's at the iris edge), because the eye's pupil is centred.
   - **flat / painted** ("flat"), or a photo without the correction: the source radius is scaled linearly; the fit pins
     the copy's pupil edge and iris edge as the hand-written JSON did (`fit_pupil` / `fit_limbus`).
   - **frontal photo with the correction** ("photo", `correct`): a photo taken through a cornea shows the iris
     magnified (1.14 x at the pupil edge, 1.05 x at the visible limbus, `eye_optics.trace`). The copy undoes this with
     the eye's own ray model: a copy pixel stands for a true iris radius r; `trace` gives the apparent radius A(r) a
     frontal view sees it at; the source pixel is the one the photo shows at A(r) (linear in the apparent radius
     between the two landmarks). Drawn through the cornea again, the photo's apparent layout comes back - no double
     refraction. Exact for the anatomy at import; the fit keeps both landmarks pinned if the anatomy changes later.
3. **Height in alpha.** The accepted phase 4 derivation (`eye_optics.iris_height`, Manu "2 go") on the copy's colour, 8
   bit, so "Höhe aus Alpha" shows what "Höhe aus Helligkeit" showed; or, with `keep_alpha`, the source's own alpha
   (resampled like the colour).
4. **A frontal photo must be radially symmetric** (`edge_check`): an iris edge that is an ellipse (an oblique photo) or
   a pupil far off the iris centre is reported; the correction assumes a frontal view.

`frontal_error` measures the result in the frontal model (§H row 5: landmark error after the fit <= 1.5 % of the iris
radius): which source radius the eye shows at its own pupil edge and visible limbus, against the landmarks.
"""

from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from viewport import eye_optics as eo

SOURCES = ("photo", "flat")
#: Where the copy's iris edge lies: a share of half the copy's width (the lab's Gollum fit used 0.88).
TARGET_SHARE = 0.88
COPY_MIN, COPY_MAX = 256, 2048
#: §H row 5's limit, a share of the iris radius.
MAX_LANDMARK_ERROR = 0.015
#: `edge_check`: above these the photo is not frontal enough for the correction (hints, `PROVISIONAL`).
MAX_ELLIPTICITY = 0.03
MAX_CENTRE_OFFSET = 0.12
LUMA = np.array([0.2126, 0.7152, 0.0722])


@dataclass(frozen=True)
class Circle:
    x: float  # centre, image pixels from the left
    y: float  # centre, image pixels from the top
    r: float

    def moved(self, **changes) -> "Circle":
        values = {"x": self.x, "y": self.y, "r": self.r} | changes
        return Circle(float(values["x"]), float(values["y"]), max(1.0, float(values["r"])))


@dataclass(frozen=True)
class Landmarks:
    pupil: Circle
    iris: Circle

    def problem(self) -> str:
        """"" when usable, else why not."""
        p, i = self.pupil, self.iris
        if not (p.r > 0.0 and i.r > 0.0):
            return "a circle has no radius"
        if p.r >= i.r:
            return "the pupil circle must be smaller than the iris circle"
        if math.hypot(p.x - i.x, p.y - i.y) + p.r >= i.r:
            return "the pupil circle must lie inside the iris circle"
        return ""


@dataclass(frozen=True)
class ImportResult:
    rgba: np.ndarray  # (n, n, 4) uint8, top row first
    fit_pupil: float
    fit_limbus: float
    hold_outer_color: bool
    note: str = ""


# -- PNG files (8-bit RGBA written; read by pyglet, else by `decode_png`) ---------------------------------------------


def encode_png(rgba: np.ndarray, level: int = 6) -> bytes:
    """An 8-bit RGBA PNG (top row first), every row with the "Up" filter (vectorized, compresses smooth images).
    `level` is zlib's (the paint files use 1: about a quarter of the time for a 2048² image, AD-037 §5)."""
    rgba = np.ascontiguousarray(rgba, dtype=np.uint8)
    h, w = rgba.shape[:2]
    rows = rgba.reshape(h, w * 4)
    up = np.empty_like(rows)
    up[0] = rows[0]
    up[1:] = rows[1:] - rows[:-1]  # uint8: wraps modulo 256 as the filter wants
    raw = np.concatenate([np.full((h, 1), 2, np.uint8), up], axis=1).tobytes()

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    header = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, level)) + chunk(b"IEND", b"")


class SlowPNG(ValueError):
    """The PNG has Average / Paeth rows, which the own decoder reconstructs byte by byte in Python (the reference PC:
    6.5 s for a 2048² RGBA texture, AD-037 §10.8c) - `decode_png(..., slow=False)` refuses it so the caller can take a
    native decoder first."""


def _unfilter(raw: bytes, width: int, height: int, bpp: int, slow: bool = True) -> np.ndarray:
    stride = width * bpp
    data = np.frombuffer(raw, dtype=np.uint8)
    if data.size < height * (stride + 1):
        raise ValueError("PNG data shorter than the image")
    rows = data[:height * (stride + 1)].reshape(height, stride + 1)
    kinds, rows = rows[:, 0], rows[:, 1:].copy()
    if np.all(kinds == 0):
        return rows
    if not slow and np.any((kinds == 3) | (kinds == 4)):
        raise SlowPNG(f"{int(np.sum((kinds == 3) | (kinds == 4)))} Average / Paeth rows")
    prev = np.zeros(stride, dtype=np.uint8)
    for y in range(height):
        kind, line = int(kinds[y]), rows[y]
        if kind == 1:
            line = np.cumsum(line.reshape(width, bpp), axis=0, dtype=np.uint8).reshape(stride)
        elif kind == 2:
            line = line + prev
        elif kind in (3, 4):  # sequential within the row
            out, up = bytearray(line.tobytes()), prev.tobytes()
            for i in range(stride):
                a = out[i - bpp] if i >= bpp else 0
                if kind == 3:
                    pred = (a + up[i]) >> 1
                else:
                    b, c = up[i], up[i - bpp] if i >= bpp else 0
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                out[i] = (out[i] + pred) & 0xFF
            line = np.frombuffer(bytes(out), dtype=np.uint8)
        elif kind != 0:
            raise ValueError(f"unknown PNG filter {kind}")
        rows[y] = line
        prev = rows[y]
    return rows


def decode_png(data: bytes, slow: bool = True) -> np.ndarray:
    """(h, w, 4) uint8 RGBA, top row first, from a non-interlaced 8- or 16-bit PNG (16 bit keeps the high byte).
    `slow` False: `SlowPNG` instead of the per-byte reconstruction of Average / Paeth rows."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, palette, header = 8, [], None, None
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = np.frombuffer(body, dtype=np.uint8).reshape(-1, 3)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    if header is None:
        raise ValueError("PNG without IHDR")
    width, height, depth, colour, _c, _f, interlace = header
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colour)
    if interlace or channels is None or depth not in (8, 16) or (colour == 3 and depth != 8):
        raise ValueError("an interlaced or low-bit PNG (save it as 8-bit, not interlaced)")
    size = depth // 8
    px = _unfilter(zlib.decompress(b"".join(idat)), width, height, channels * size, slow)
    px = px.reshape(height, width, channels * size)[..., ::size] if size == 2 else px.reshape(height, width, channels)
    out = np.empty((height, width, 4), dtype=np.uint8)
    out[..., 3] = 255
    if colour == 3:
        if palette is None:
            raise ValueError("a palette PNG without its palette")
        out[..., :3] = palette[px[..., 0]]
    elif colour in (0, 4):
        out[..., :3] = px[..., :1]
        if colour == 4:
            out[..., 3] = px[..., 1]
    else:
        out[..., :channels] = px
    return out


def _rgba_of(data) -> np.ndarray:
    """A pyglet `ImageData` as (h, w, 4) uint8 RGBA, top row first. The pixels are taken in the decoder's own format and
    reordered here: pyglet's own conversion (`get_data("RGBA")`) runs a regular expression over the bytes - 1.1 s for a
    2048² RGB image in the container, the ~5 s of the reference PC's BGRA (WIC) texture (AD-037 §10.8d)."""
    fmt, pitch = data.format, data.pitch
    width, height = data.width, data.height
    channels = len(fmt)
    if channels not in (1, 2, 3, 4) or any(c not in "RGBAL" for c in fmt):
        raw = data.get_data("RGBA", width * 4)
        return np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)[::-1].copy()
    raw = np.frombuffer(data.get_data(fmt, pitch), dtype=np.uint8)
    rows = raw.reshape(height, abs(pitch))[:, :width * channels].reshape(height, width, channels)
    if pitch > 0:
        rows = rows[::-1]  # pyglet: a positive pitch is bottom-up
    out = np.empty((height, width, 4), dtype=np.uint8)
    out[..., 3] = 255
    for i, name in enumerate(fmt):
        if name == "L":
            out[..., :3] = rows[..., i:i + 1]
        else:
            out[..., "RGBA".index(name)] = rows[..., i]
    return out


def read_rgba(path: str | Path) -> np.ndarray:
    """(h, w, 4) uint8 RGBA, top row first. pyglet's decoders first (what the viewport shows, also JPEG and the rest
    the system can read); without a display, or when pyglet refuses, `decode_png`. `ValueError` / `OSError`."""
    path = Path(path)
    try:
        from pyglet import image

        data = image.load(str(path)).get_image_data()
        return _rgba_of(data)
    except Exception:  # no display, no decoder: pyglet raises its own types
        pass
    return decode_png(path.read_bytes())


def has_alpha(rgba: np.ndarray) -> bool:
    return bool(np.any(rgba[..., 3] < 255))


# -- landmarks: the estimate and the symmetry check -------------------------------------------------------------------


def luminance(rgba: np.ndarray) -> np.ndarray:
    return rgba[..., :3].astype(np.float64) / 255.0 @ LUMA


def _profile(lum: np.ndarray, cx: float, cy: float, step: float, count: int) -> np.ndarray:
    h, w = lum.shape
    y, x = np.meshgrid(np.arange(h) + 0.5, np.arange(w) + 0.5, indexing="ij")
    ring = np.floor(np.hypot(x - cx, y - cy) / step).astype(int)
    inside = ring < count
    sums = np.bincount(ring[inside], lum[inside], count)
    n = np.bincount(ring[inside], minlength=count)
    return np.where(n > 0, sums / np.maximum(n, 1), np.nan)


def estimate(rgba: np.ndarray) -> tuple[Landmarks | None, str]:
    """A suggestion for both circles (the eye lab's profile method: mean luminance per ring, pupil edge = first ring
    brighter than 0.15, iris edge = first ring beyond it brighter than 0.85 - a white background - else the steepest
    brightness change of the outer profile), centred on the dark pupil's centroid. (landmarks, "") or (None, why)."""
    lum = luminance(rgba)
    h, w = lum.shape
    half = 0.5 * min(h, w)
    y, x = np.meshgrid(np.arange(h) + 0.5, np.arange(w) + 0.5, indexing="ij")
    cx, cy = 0.5 * w, 0.5 * h
    dark = (lum < 0.15) & (np.hypot(x - cx, y - cy) < 0.5 * half)
    if dark.sum() < 12:
        return None, "no dark pupil near the image centre"
    step = max(half / 200.0, 0.5)
    count = int(half / step)
    pupil_r = None
    for _ in range(3):  # the centroid of the dark pixels inside the pupil found so far
        cx, cy = float(x[dark].mean()), float(y[dark].mean())
        profile = _profile(lum, cx, cy, step, count)
        above = np.nonzero(profile > 0.15)[0]
        if not len(above):
            return None, "no pupil edge (the image is dark throughout)"
        pupil_r = float(above[0] * step)
        dark = (lum < 0.15) & (np.hypot(x - cx, y - cy) < max(pupil_r * 1.1, 2.0))
        if dark.sum() < 12:
            break
    start = int(math.ceil(1.6 * pupil_r / step))
    outer = profile[start:]
    bright = np.nonzero(outer > 0.85)[0]
    if len(bright):
        iris_r = float((start + bright[0]) * step)
    else:
        valid = np.nan_to_num(outer, nan=0.0)
        smooth = np.convolve(valid, np.ones(5) / 5.0, mode="same")
        change = np.abs(np.gradient(smooth))
        if len(change) < 6 or float(change.max()) < 0.01:
            return None, "no iris edge found"
        iris_r = float((start + int(np.argmax(change[2:-2])) + 2) * step)
    pupil, iris = Circle(cx, cy, pupil_r), Circle(cx, cy, iris_r)
    marks = Landmarks(pupil, iris)
    problem = marks.problem()
    return (None, problem) if problem else (marks, "")


def edge_radii(lum: np.ndarray, iris: Circle, directions: int = 48) -> tuple[np.ndarray, np.ndarray]:
    """(angles, the iris edge's radius per direction): the strongest brightness change between 0.7 and 1.3 iris radii
    from the iris circle's centre (bilinear samples). NaN where the image ends."""
    angles = np.arange(directions) * (2.0 * math.pi / directions)
    radii = iris.r * np.linspace(0.7, 1.3, 121)
    px = iris.x + np.cos(angles)[:, None] * radii[None, :]
    py = iris.y + np.sin(angles)[:, None] * radii[None, :]
    samples = _bilinear(lum[..., None], px, py)[..., 0]
    h, w = lum.shape
    outside = (px < 0) | (py < 0) | (px > w) | (py > h)
    smooth = np.apply_along_axis(lambda v: np.convolve(v, np.ones(5) / 5.0, mode="same"), 1, samples)
    change = np.abs(np.gradient(smooth, axis=1))
    change[:, :3] = change[:, -3:] = 0.0
    found = radii[np.argmax(change, axis=1)]
    return angles, np.where(outside.any(axis=1), np.nan, found)


def edge_check(rgba: np.ndarray, marks: Landmarks) -> tuple[float, float, str]:
    """(ellipticity, centre offset, hint): how far the iris edge is from a circle (the cos 2θ part of its radius over
    the mean; an oblique photo of a round iris is an ellipse) and the pupil's offset from the iris centre, both as
    shares of the iris radius. The hint is "" for a frontal-looking photo."""
    angles, radii = edge_radii(luminance(rgba), marks.iris)
    ok = np.isfinite(radii)
    ellipticity = 0.0
    if ok.sum() >= 12:
        a = np.stack([np.ones(ok.sum()), np.cos(2 * angles[ok]), np.sin(2 * angles[ok])], axis=1)
        r = radii[ok]
        coef = np.linalg.lstsq(a, r, rcond=None)[0]
        keep = np.abs(r - a @ coef) < 0.06 * marks.iris.r  # lids and lashes: refit without the outliers
        if keep.sum() >= 12:
            coef = np.linalg.lstsq(a[keep], r[keep], rcond=None)[0]
        ellipticity = float(math.hypot(coef[1], coef[2]) / max(coef[0], 1e-9))
    offset = math.hypot(marks.pupil.x - marks.iris.x, marks.pupil.y - marks.iris.y) / marks.iris.r
    hints = []
    if ellipticity > MAX_ELLIPTICITY:
        hints.append(f"Irisrand nicht rund (Ellipse {100 * ellipticity:.1f} %)")
    if offset > MAX_CENTRE_OFFSET:
        hints.append(f"Pupille {100 * offset:.0f} % neben der Irismitte")
    if hints:
        hints.append("Foto schräg? Nicht radialsymmetrisch - die Brechungskorrektur setzt ein frontales Foto voraus.")
    return ellipticity, offset, " ".join(hints)


# -- the copy ----------------------------------------------------------------------------------------------------------


def _bilinear(img: np.ndarray, x, y) -> np.ndarray:
    """`img` (h, w, c) sampled at pixel coordinates (centres at +0.5), clamped to the edge."""
    h, w = img.shape[:2]
    fx = np.clip(np.asarray(x, dtype=np.float64) - 0.5, 0.0, w - 1.0)
    fy = np.clip(np.asarray(y, dtype=np.float64) - 0.5, 0.0, h - 1.0)
    x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    tx, ty = (fx - x0)[..., None], (fy - y0)[..., None]
    top = img[y0, x0] * (1.0 - tx) + img[y0, x1] * tx
    bottom = img[y1, x0] * (1.0 - tx) + img[y1, x1] * tx
    return top * (1.0 - ty) + bottom * ty


@lru_cache(maxsize=16)
def apparent_table(g: eo.EyeGeometry, refraction: str = "V2") -> tuple[np.ndarray, np.ndarray]:
    """(true iris radius, apparent radius) in a frontal view, increasing, out to the last ray that still reaches the
    iris or pupil (the visible limbus): `eye_optics.trace` from far in front along -Z."""
    rho = np.linspace(0.0, g.limbus_radius, 2001)
    eye = np.stack([rho, np.zeros_like(rho), np.full_like(rho, 10.0)], axis=-1)
    hit = eo.trace(eye, np.broadcast_to([0.0, 0.0, -1.0], eye.shape), refraction, g)
    seen = (hit.kind == eo.IRIS) | (hit.kind == eo.PUPIL)
    last = int(np.nonzero(seen)[0][-1])
    true = np.hypot(hit.hit[: last + 1, 0], hit.hit[: last + 1, 1])
    return true, rho[: last + 1]


def apparent_radius(r, g: eo.EyeGeometry, refraction: str = "V2") -> np.ndarray:
    """A(r): where a frontal view sees the true iris radius r (beyond the visible limbus: clamped to it)."""
    true, rho = apparent_table(g, refraction)
    return np.interp(np.asarray(r, dtype=np.float64), true, rho)


def visible_limbus(g: eo.EyeGeometry, refraction: str = "V2") -> float:
    """The apparent radius of the visible iris edge in a frontal view."""
    return float(apparent_table(g, refraction)[1][-1])


def copy_size(marks: Landmarks) -> int:
    half = marks.iris.r / TARGET_SHARE
    return int(min(COPY_MAX, max(COPY_MIN, 2 * round(half))))


def _source_radius(sigma, marks: Landmarks, mode: str, g: eo.EyeGeometry | None, refraction: str):
    """Copy share (of half the copy's width) -> radius in the source image (pixels), for the copy's mapping."""
    P, L = marks.pupil.r, marks.iris.r
    sigma = np.asarray(sigma, dtype=np.float64)
    if mode != "corrected":
        return sigma * (L / TARGET_SHARE)
    lab_t = g.limbus_radius / g.iris_radius
    s_p, s_l = corrected_fit(g)
    s = np.where(sigma < s_l, sigma * (lab_t / s_l), lab_t + (sigma - s_l) * ((1.0 - lab_t) / (1.0 - s_l)))
    a = apparent_radius(s * g.iris_radius, g, refraction)
    a_p, a_l = float(apparent_radius(g.pupil_radius, g, refraction)), visible_limbus(g, refraction)
    rho = np.where(a < a_p, a * (P / a_p), P + (a - a_p) * ((L - P) / (a_l - a_p)))
    return np.minimum(rho, L)


def corrected_fit(g: eo.EyeGeometry) -> tuple[float, float]:
    """The corrected copy's (fit_pupil, fit_limbus): a true-radius layout, the limbus at `TARGET_SHARE`."""
    return TARGET_SHARE * g.pupil_radius / g.limbus_radius, TARGET_SHARE


def _warp(rgba_f: np.ndarray, marks: Landmarks, n: int, radius_of) -> np.ndarray:
    """Resample the source onto the copy: copy share -> source radius (`radius_of`), the angle kept, the centre
    blending from the pupil's (at the pupil edge and inside) to the iris edge's (at the iris edge and beyond)."""
    c = (np.arange(n) + 0.5) / n * 2.0 - 1.0
    y, x = np.meshgrid(c, c, indexing="ij")
    sigma = np.hypot(x, y)
    rho = radius_of(sigma)
    P, L = marks.pupil.r, marks.iris.r
    blend = np.clip((L - rho) / (L - P), 0.0, 1.0)  # 1 at the pupil edge and inside, 0 at the iris edge
    cx = marks.iris.x + (marks.pupil.x - marks.iris.x) * blend
    cy = marks.iris.y + (marks.pupil.y - marks.iris.y) * blend
    safe = np.where(sigma > 1e-9, sigma, 1.0)
    return _bilinear(rgba_f, cx + rho * x / safe, cy + rho * y / safe)


def build_copy(rgba: np.ndarray, marks: Landmarks, source: str, spec=None, correct: bool = False,
               keep_alpha: bool = False, hold_outer_color: bool = True, refraction: str = "V2") -> ImportResult:
    """The import's copy and its fit (see the module). `spec` (an `EyeSpec`, the eye's anatomy) is needed for the
    correction. `ValueError` for unusable landmarks or options."""
    if source not in SOURCES:
        raise ValueError(f"source: one of {SOURCES}")
    problem = marks.problem()
    if problem:
        raise ValueError(problem)
    corrected = source == "photo" and correct
    if corrected and spec is None:
        raise ValueError("the correction needs the eye's anatomy")
    g = eo.EyeGeometry.from_values(spec) if corrected else None
    n = copy_size(marks)
    mode = "corrected" if corrected else "linear"
    out = _warp(rgba.astype(np.float64), marks, n, lambda s: _source_radius(s, marks, mode, g, refraction))
    out = np.clip(np.round(out), 0, 255).astype(np.uint8)
    if corrected:
        fit_pupil, fit_limbus = corrected_fit(g)
        hold = False  # beyond the visible limbus the copy holds the photo's edge colour itself
    else:
        fit_pupil, fit_limbus = TARGET_SHARE * marks.pupil.r / marks.iris.r, TARGET_SHARE
        hold = bool(hold_outer_color)
    note = ""
    if keep_alpha and not has_alpha(rgba):
        keep_alpha, note = False, "the image has no alpha channel: the height is derived from its brightness"
    if not keep_alpha:
        heights = eo.iris_height(out[..., :3] / 255.0, fit_pupil, fit_limbus)
        out[..., 3] = np.clip(np.round(heights * 255.0), 0, 255).astype(np.uint8)
    return ImportResult(out, fit_pupil, fit_limbus, hold, note)


def frontal_error(result: ImportResult, marks: Landmarks, source: str, spec, correct: bool,
                  refraction: str = "V2") -> float:
    """§H row 5, the landmark error after the fit in the frontal model, as a share of the iris radius (the larger of
    the two landmarks). The eye's path to the source: a radius on the iris -> the fit (`eye_optics.share_map`, the
    shader's twin) -> the copy -> the source (the copy's own mapping).
    - a photo shows the iris through a cornea: at the eye's own apparent pupil edge and visible limbus (a frontal view,
      `trace`) the photo's pupil and iris landmarks should be seen;
    - a flat image is the iris itself: at the eye's true pupil radius and limbus radius."""
    g = eo.EyeGeometry.from_values(spec)
    if source == "photo":
        true, rho = apparent_table(g, refraction)
        a_pupil = float(apparent_radius(g.pupil_radius, g, refraction))
        radii = np.interp([a_pupil, rho[-1]], rho, true)
    else:
        radii = np.array([g.pupil_radius, g.limbus_radius])
    spec_fit = type("Fit", (), dict(fit_pupil=result.fit_pupil, fit_limbus=result.fit_limbus,
                                    hold_outer_color=result.hold_outer_color))()
    sigma = eo.share_map(radii / g.iris_radius, *eo.fit_knots(spec_fit, g))
    mode = "corrected" if source == "photo" and correct else "linear"
    shown = _source_radius(sigma, marks, mode, g, refraction)
    return float(np.max(np.abs(shown - np.array([marks.pupil.r, marks.iris.r]))) / marks.iris.r)
