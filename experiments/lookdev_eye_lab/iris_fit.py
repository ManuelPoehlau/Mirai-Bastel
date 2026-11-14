"""Radial fit of the custom iris image (2026-11-14, Manu: approved in the handoff of that day, Task 1).

A custom iris image need not have its pupil edge and iris edge where the lab's geometry has them (Manu's texture:
pupil edge ≈ 0.22, iris edge ≈ 0.90 of half the image width; the lab: pupil 0.268, visible limbus 0.819). An optional
sidecar next to the image says where they are:

    out/iris_custom.json   {"pupil": 0.22, "limbus": 0.90}
                           {"pupil": 0.22, "limbus": 0.88, "hold_outer_color": true}   (Manu's choice "A+H")

Both numbers are shares of half the image width, measured from the image centre. The file is **only read** (like
`iris_source.CUSTOM_NAME`); it applies only to the custom image; without it the mapping is exactly the planar one of
`eye_geometry.iris_uv`. An invalid file is ignored and the reason is shown wherever `IrisSource.describe` is.

**The remap** (the standard pupil-dilation remap, so a later pupil-size control can reuse it): piecewise linear in the
lab's radius share s = r / `IRIS_RADIUS`, the angle kept:
`[0, s_pupil] -> [0, pupil]`, `[s_pupil, s_target] -> [pupil, limbus]`, `[s_target, 1] -> [limbus, outer]` (continued
with the same slope beyond 1). `s_pupil` = the lab's pupil edge (0.268); `s_target` = where the image's iris edge goes:
the visible limbus 0.819 (`DEFAULT_TARGET`, Manu 2026-11-14: "A"; the P1b chamber angle 0.779 stays in `TARGETS` for
comparisons). `outer` = 1.0 continues to the image edge (default); the optional key `"hold_outer_color": true` sets
`outer = limbus`, so beyond the target the image's iris-edge colour is held and no background shows where P1's
parallax (close-up: out to ~0.855) or P1b's tissue band looks past the target. Set `limbus` just inside the
background then (e.g. 0.88 for an iris edge at 0.90), or the held colour is the edge's blend with the background.

Twins: `share_map` / `uv` (NumPy, P1's mesh UVs via `eye_geometry.iris_mesh`) and `GLSL_SRC` (P1b's cornea pass,
compiled with `#define IRIS_FIT`); compared on the GPU by `refraction_parity.fit_case`.

`suggest_iris_fit.py [image.png]` estimates the two shares from an image (mean luminance per 1 % radius
ring: pupil = first ring brighter than 0.15, iris edge = first ring brighter than 0.85 beyond 0.5, for a white
background) and **prints** a suggestion; only the JSON file sets them.
"""

from __future__ import annotations

import json
import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import cornea_optics as co
from . import eye_geometry as geo

SIDECAR_NAME = "iris_custom.json"
KEYS = ("pupil", "limbus")
OPTIONAL_KEYS = ("hold_outer_color",)
#: The lab's pupil edge as a share of the iris disc (the image's pupil edge lands here).
LAB_PUPIL_SHARE = geo.PUPIL_RADIUS / geo.IRIS_RADIUS
#: Where the image's iris edge can land: P1's visible limbus, or P1b's chamber angle (beyond it P1b shows limbal tissue).
TARGETS = {"limbus": geo.LIMBUS_RADIUS / geo.IRIS_RADIUS, "angle": co.GEOMETRY.angle[0] / geo.IRIS_RADIUS}
#: Manu 2026-11-14: "A+H" - the image's iris edge on the visible limbus (with `hold_outer_color`, a sidecar setting).
DEFAULT_TARGET = "limbus"


@dataclass(frozen=True)
class IrisFit:
    pupil: float  # the image's pupil edge, share of half the image width
    limbus: float  # the image's iris edge
    target: str = DEFAULT_TARGET
    #: The image share the lab's iris root (share 1) samples: 1.0 = continue to the image edge; = `limbus` holds the
    #: image's iris-edge colour beyond the target (`"hold_outer_color": true` in the sidecar).
    outer: float = 1.0

    @property
    def hold(self) -> bool:
        return self.outer == self.limbus

    @property
    def lab_knots(self) -> tuple[float, float]:
        return LAB_PUPIL_SHARE, TARGETS[self.target]

    def describe(self) -> str:
        lp, lt = self.lab_knots
        return (f"radial fit {SIDECAR_NAME}: image pupil {self.pupil:.3f} -> {lp:.3f}, image iris edge "
                f"{self.limbus:.3f} -> {lt:.3f} ({self.target})" + (", outer colour held" if self.hold else ""))

    def uniforms(self) -> dict:
        lp, lt = self.lab_knots
        return {"u_fit_lab": (lp, lt), "u_fit_img": (self.pupil, self.limbus, self.outer)}


def validate(data) -> tuple[IrisFit | None, str]:
    """(fit, "") or (None, reason). The keys `pupil` and `limbus` (finite numbers, 0 < pupil < limbus <= 1) and
    optionally `hold_outer_color` (true / false; absent = false); no other key."""
    if not isinstance(data, dict):
        return None, "not a JSON object"
    unknown = sorted(set(data) - set(KEYS) - set(OPTIONAL_KEYS))
    if unknown:
        return None, f"unknown key {unknown[0]!r} (allowed: pupil, limbus, hold_outer_color)"
    missing = [k for k in KEYS if k not in data]
    if missing:
        return None, f"missing {missing[0]!r}"
    values = []
    for key in KEYS:
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None, f"{key!r} is not a number"
        values.append(float(value))
    pupil, limbus = values
    if not 0.0 < pupil < limbus <= 1.0:
        return None, f"needs 0 < pupil < limbus <= 1 (got pupil {pupil:g}, limbus {limbus:g})"
    hold = data.get("hold_outer_color", False)
    if not isinstance(hold, bool):
        return None, "'hold_outer_color' must be true or false"
    return IrisFit(pupil, limbus, outer=limbus if hold else 1.0), ""


def load(out_dir: Path) -> tuple[IrisFit | None, str]:
    """The sidecar next to the custom image: (fit, "") / (None, "") when absent / (None, reason) when invalid.
    Reads the file only."""
    path = Path(out_dir) / SIDECAR_NAME
    if not path.exists():
        return None, ""
    try:
        raw = path.read_bytes()  # read-only
        # Windows editors / PowerShell write UTF-8 with a BOM or UTF-16 (`>` / Out-File in Windows PowerShell 5.1).
        text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"cannot be read ({exc.__class__.__name__})"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"not valid JSON (line {exc.lineno}, column {exc.colno})"
    return validate(data)


# -- the remap (NumPy twin of GLSL_SRC) ------------------------------------------------------------------------------


def share_map(s, fit: IrisFit) -> np.ndarray:
    """Lab radius share -> image radius share (piecewise linear, see the module docstring)."""
    s = np.asarray(s, dtype=np.float64)
    lp, lt = fit.lab_knots
    inner = s * (fit.pupil / lp)
    middle = fit.pupil + (s - lp) * ((fit.limbus - fit.pupil) / (lt - lp))
    outer = fit.limbus + (s - lt) * ((fit.outer - fit.limbus) / (1.0 - lt))
    return np.where(s < lp, inner, np.where(s < lt, middle, outer))


def uv(xy, fit: IrisFit) -> np.ndarray:
    """Planar iris position(s) (..., 2) in eye units -> texture coordinates, the angle kept."""
    xy = np.asarray(xy, dtype=np.float64)
    s = np.linalg.norm(xy, axis=-1) / geo.IRIS_RADIUS
    safe = np.where(s > 1e-6, s, 1.0)
    scale = np.where(s > 1e-6, share_map(s, fit) / safe, fit.pupil / fit.lab_knots[0])
    return 0.5 + 0.5 * xy / geo.IRIS_RADIUS * scale[..., None]


def mesh_uv(fit: IrisFit):
    """`eye_geometry.iris_mesh`'s `uv` callable: (x, y) -> (u, v)."""
    def to_uv(x: float, y: float) -> tuple[float, float]:
        u, v = uv((x, y), fit)
        return float(u), float(v)
    return to_uv


def mesh_extra_radii(fit: IrisFit) -> tuple[float, ...]:
    """Rings the iris mesh needs so the remap's knots are mesh rings (a knot inside a ring band would be blurred into a
    straight chord by the UV interpolation)."""
    return tuple(k * geo.IRIS_RADIUS for k in fit.lab_knots)


GLSL_SRC = """
uniform vec2 u_fit_lab;  // the lab's pupil share, the target share (iris_fit.IrisFit.lab_knots)
uniform vec3 u_fit_img;  // the image's pupil share, iris-edge share, share at the lab's iris root
// iris_fit.share_map
float iris_fit_share(float s) {
    float inner = s * (u_fit_img.x / u_fit_lab.x);
    float middle = u_fit_img.x + (s - u_fit_lab.x) * ((u_fit_img.y - u_fit_img.x) / (u_fit_lab.y - u_fit_lab.x));
    float outer = u_fit_img.y + (s - u_fit_lab.y) * ((u_fit_img.z - u_fit_img.y) / (1.0 - u_fit_lab.y));
    return s < u_fit_lab.x ? inner : (s < u_fit_lab.y ? middle : outer);
}
// iris_fit.uv (u_iris_radius from REFRACTION_LIB_SRC)
vec2 iris_fit_uv(vec2 p) {
    float s = length(p) / u_iris_radius;
    float scale = s > 1e-6 ? iris_fit_share(s) / s : u_fit_img.x / u_fit_lab.x;
    return vec2(0.5) + 0.5 * p / u_iris_radius * scale;
}
"""


# -- the estimate from an image (a suggestion only) ------------------------------------------------------------------


def _unfilter(raw: bytes, width: int, height: int, bpp: int) -> np.ndarray:
    stride = width * bpp
    out = bytearray(height * stride)
    prev = bytearray(stride)
    pos = 0
    for row in range(height):
        kind = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if kind == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif kind == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif kind == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif kind == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif kind != 0:
            raise ValueError(f"unknown PNG filter {kind}")
        out[row * stride:(row + 1) * stride] = line
        prev = line
    return np.frombuffer(bytes(out), dtype=np.uint8).reshape(height, width, bpp)


def read_png_rgb(path: Path) -> np.ndarray:
    """(h, w, 3) floats in [0, 1] (sRGB values) from an 8-bit, non-interlaced PNG; reads the file only. Enough for the
    estimate; the lab's textures are loaded by the production loader."""
    data = Path(path).read_bytes()
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
        raise ValueError("no IHDR")
    width, height, depth, colour, _c, _f, interlace = header
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colour)
    if depth != 8 or interlace or channels is None:
        raise ValueError("the estimate reads 8-bit non-interlaced PNGs only")
    pixels = _unfilter(zlib.decompress(b"".join(idat)), width, height, channels)
    if colour == 3:
        rgb = palette[pixels[..., 0]]
    elif colour in (0, 4):
        rgb = np.repeat(pixels[..., :1], 3, axis=-1)
    else:
        rgb = pixels[..., :3]
    return rgb.astype(np.float64) / 255.0


def radial_profile(rgb: np.ndarray, step: float = 0.01) -> np.ndarray:
    """Mean luminance (Rec. 709 weights on the sRGB values) per ring of width `step`, from the centre out to the
    inscribed circle; entry k = the ring [k * step, (k + 1) * step)."""
    h, w = rgb.shape[:2]
    y, x = np.meshgrid((np.arange(h) + 0.5) / h * 2.0 - 1.0, (np.arange(w) + 0.5) / w * 2.0 - 1.0, indexing="ij")
    ring = np.floor(np.sqrt(x * x + y * y) / step).astype(int)
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
    count = int(round(1.0 / step))
    inside = ring < count
    sums = np.bincount(ring[inside], lum[inside], count)
    n = np.bincount(ring[inside], minlength=count)
    return sums / np.maximum(n, 1)


def estimate(rgb: np.ndarray, step: float = 0.01) -> tuple[float | None, float | None]:
    """(pupil, limbus) shares by the profile method of the module docstring; None where a threshold is never met."""
    profile = radial_profile(rgb, step)
    shares = np.arange(len(profile)) * step
    above = np.nonzero(profile > 0.15)[0]
    pupil = float(shares[above[0]]) if len(above) else None
    outer = np.nonzero((profile > 0.85) & (shares > 0.5))[0]
    limbus = float(shares[outer[0]]) if len(outer) else None
    return pupil, limbus
