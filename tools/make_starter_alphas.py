"""The built-in starter alphas (AD-037 §14 Phase 4c; proposal 2026-11-25 §6.5, P-22) - a deterministic generator and
its contact sheet.

Every alpha is made here from fixed seeds with NumPy only (our own work, the repository's terms); nothing external is
bundled (CC0 alphas only later, with source, licence text and date per file - Manu 2026-11-25). Each has a black border.
Categories and contents follow P-22: Organisch (pores, creases), Adern, Sprenkel, Schmutz, Schaden, Oberfläche, Formen.
Methods: pores and dots from jittered points with soft radial kernels; veins from a branching random walk with tapering
width; stains and grime from thresholded fBm noise; cracks from Voronoi cell edges with width noise; scratches from
noisy polylines; grain from band-limited noise.

**A contact sheet first** (review point 6): `--sheet DIR` (the default) writes one sheet per category - each alpha, a
stamped strip (Einzeln) and a spray strip across a neutral shaded sphere (the tangent-plane stamp of `mirai.paint.stamp`,
the 4b randomness for the spray) - and an overview. **Manu judges per category; only accepted categories are adopted**:
`--adopt organisch,adern` (or `all`) writes `assets/paint/alphas/<category>/<stem>.png`, `index.json` (names, hashes)
and `assets/paint/LICENSES.md`. Until then the library's built-ins are the six 4a test alphas.

Usage (repo root):
    python tools/make_starter_alphas.py                        # contact sheets -> docs/research/alpha_brush_4c_assets_2026-11-26/
    python tools/make_starter_alphas.py --adopt organisch,adern # write the accepted categories into assets/paint/
Labels on the sheets need Pillow (optional; without it the sheets are unlabelled and `contact_sheet.md` names the rows).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402

from mirai.paint import alpha as A  # noqa: E402  (the 4a helpers: noise, fBm, border, polylines, soft dots, walks)

DEFAULT_SHEETS = REPO / "docs" / "research" / "alpha_brush_4c_assets_2026-11-26"
ASSETS = REPO / "assets" / "paint"


def _radial(shape, inner: float = 0.75, outer: float = 0.98) -> np.ndarray:
    """1 inside `inner`, fading to 0 at `outer` (in half-sizes from the centre, elliptic for a rectangle)."""
    h, w = shape
    y, x = np.mgrid[0:h, 0:w]
    r = np.hypot((x + 0.5 - w / 2) / (w / 2), (y + 0.5 - h / 2) / (h / 2))
    return np.clip((outer - r) / (outer - inner), 0.0, 1.0)


def _jittered_points(rng, size: float, cells: int, jitter: float = 0.4):
    step = size / cells
    pts = []
    for gy in range(cells):
        for gx in range(cells):
            pts.append(((gx + 0.5 + rng.uniform(-jitter, jitter)) * step, (gy + 0.5 + rng.uniform(-jitter, jitter)) * step))
    return pts


# -- Organisch ---------------------------------------------------------------------------------------------------------


def pores_fine():
    rng = np.random.default_rng(1101)
    size = 512
    image = np.zeros((size, size))
    pts = [p for p in _jittered_points(rng, size, 18, 0.45) if math.hypot(p[0] - 256, p[1] - 256) < 236]
    A._soft_dots(image, pts, rng.uniform(3.0, 6.5, len(pts)), rng.uniform(0.45, 1.0, len(pts)))
    return A._border(image * _radial(image.shape, 0.7, 0.95), 8)


def pores_coarse():
    rng = np.random.default_rng(1102)
    size = 512
    image = np.zeros((size, size))
    pts = [p for p in _jittered_points(rng, size, 8, 0.4) if math.hypot(p[0] - 256, p[1] - 256) < 230]
    A._soft_dots(image, pts, rng.uniform(9.0, 18.0, len(pts)), rng.uniform(0.5, 1.0, len(pts)))
    return A._border(image * _radial(image.shape, 0.7, 0.95), 8)


def pores_cluster():
    rng = np.random.default_rng(1103)
    size = 512
    image = np.zeros((size, size))
    centres, radii, values = [], [], []
    for _ in range(6):
        cx, cy = rng.uniform(130, 382, 2)
        n = rng.integers(10, 22)
        spread = rng.uniform(30, 60)
        for _ in range(n):
            centres.append((cx + rng.normal(0, spread), cy + rng.normal(0, spread)))
            radii.append(rng.uniform(3.5, 9.0))
            values.append(rng.uniform(0.5, 1.0))
    A._soft_dots(image, centres, radii, values)
    return A._border(image * _radial(image.shape, 0.75, 0.97), 8)


def _crease(image, rng, start, angle, length, width, value, curl=0.04):
    steps = 30
    points = [start]
    for _ in range(steps):
        angle += rng.normal(0.0, curl)
        x, y = points[-1]
        points.append((x + length / steps * math.cos(angle), y + length / steps * math.sin(angle)))
    t = np.linspace(0.0, 1.0, len(points))
    taper = np.sin(np.pi * np.clip(t, 0.02, 0.98)) ** 0.7
    A._stroke_path(image, points, list(width * taper + 0.6), list(value * (0.6 + 0.4 * taper)))


def creases_short():
    rng = np.random.default_rng(1104)
    h, w = 256, 512
    image = np.zeros((h, w))
    for k in range(7):
        y = 50 + k * 26 + rng.uniform(-8, 8)
        x = rng.uniform(40, 140)
        _crease(image, rng, (x, y), rng.normal(0.0, 0.08), rng.uniform(180, 330), rng.uniform(2.5, 5.0),
                rng.uniform(0.6, 1.0))
    return A._border(image, 8)


def crows_foot():
    rng = np.random.default_rng(1105)
    h, w = 384, 512
    image = np.zeros((h, w))
    for k, angle in enumerate(np.linspace(-0.75, 0.75, 6)):
        _crease(image, rng, (40.0, h / 2 + rng.uniform(-10, 10)), angle + rng.normal(0, 0.05), rng.uniform(260, 420),
                rng.uniform(3.0, 5.5), rng.uniform(0.65, 1.0), curl=0.05)
    return A._border(image, 8)


# -- Adern -------------------------------------------------------------------------------------------------------------


def _branch(image, rng, start, angle, steps, step, width, value, depth):
    points, _ = A._walk(rng, start, angle, steps, step, 0.16)
    n = len(points)
    widths = np.linspace(width, max(width * 0.25, 0.8), n)
    A._stroke_path(image, points, list(widths), list(np.linspace(value, value * 0.7, n)))
    if depth <= 0:
        return
    for _ in range(rng.integers(2, 4)):
        at = int(rng.integers(n // 5, n - 2))
        side = rng.choice((-1.0, 1.0))
        _branch(image, rng, points[at], angle + side * rng.uniform(0.4, 0.9), max(steps // 2, 4), step * 0.85,
                widths[at] * 0.7, value * 0.9, depth - 1)


def veins_branching():
    rng = np.random.default_rng(1201)
    h, w = 256, 512
    image = np.zeros((h, w))
    _branch(image, rng, (16.0, h * 0.5), 0.0, 40, 12.0, 8.0, 1.0, 2)
    return A._border(image, 8)


def capillaries():
    rng = np.random.default_rng(1202)
    size = 512
    image = np.zeros((size, size))
    for _ in range(9):
        start = tuple(rng.uniform(60, 452, 2))
        _branch(image, rng, start, rng.uniform(0, 2 * math.pi), 18, 9.0, 2.6, rng.uniform(0.55, 0.9), 2)
    return A._border(image * _radial(image.shape, 0.7, 0.96), 8)


# -- Sprenkel ----------------------------------------------------------------------------------------------------------


def freckles():
    rng = np.random.default_rng(1301)
    size = 256
    image = np.zeros((size, size))
    n = 34
    pts = [(rng.normal(128, 52), rng.normal(128, 52)) for _ in range(n)]
    pts = [p for p in pts if math.hypot(p[0] - 128, p[1] - 128) < 108]
    radii = rng.uniform(2.5, 8.0, len(pts))
    A._soft_dots(image, pts, radii, rng.uniform(0.4, 0.95, len(pts)))
    blotch = A._fbm((size, size), 16, 3, rng)
    return A._border(image * (0.7 + 0.3 * blotch), 6)


def dots_scattered():
    rng = np.random.default_rng(1302)
    size = 256
    image = np.zeros((size, size))
    pts = [p for p in _jittered_points(rng, size, 6, 0.45) if rng.random() < 0.7]
    pts = [p for p in pts if math.hypot(p[0] - 128, p[1] - 128) < 110]
    y, x = np.mgrid[0:size, 0:size]
    for (cx, cy), r in zip(pts, rng.uniform(4.0, 10.0, len(pts))):
        d = np.hypot(x + 0.5 - cx, y + 0.5 - cy)
        image = np.maximum(image, np.clip(r + 0.75 - d, 0.0, 1.0))  # crisp edges (anti-aliased)
    return A._border(image, 6)


def speckle_soft():
    rng = np.random.default_rng(1303)
    size = 256
    n = A._fbm((size, size), 16, 4, rng)
    image = np.clip((n - 0.55) / 0.12, 0.0, 1.0)
    return A._border(image * _radial(image.shape, 0.6, 0.95), 6)


# -- Schmutz -----------------------------------------------------------------------------------------------------------


def stain():
    rng = np.random.default_rng(1401)
    size = 512
    n = A._fbm((size, size), 128, 6, rng)
    r = 1.0 - _radial((size, size), 0.0, 1.0)
    field = n * 0.9 + (1.0 - r) * 0.55
    image = np.clip((field - 0.62) / 0.18, 0.0, 1.0) * (0.6 + 0.4 * A._fbm((size, size), 32, 3, rng))
    return A._border(image, 10)


def grime():
    rng = np.random.default_rng(1402)
    size = 512
    coarse = A._fbm((size, size), 128, 4, rng)
    fine = A._fbm((size, size), 8, 3, rng)
    image = np.clip((coarse - 0.45) / 0.2, 0.0, 1.0) * np.clip((fine - 0.3) / 0.4, 0.0, 1.0)
    return A._border(image * _radial(image.shape, 0.65, 0.97), 10)


def deposit():
    rng = np.random.default_rng(1403)
    size = 512
    y, x = np.mgrid[0:size, 0:size]
    n = A._fbm((size, size), 64, 4, rng)
    r = np.hypot(x + 0.5 - 256, y + 0.5 - 256) / 200.0 + (n - 0.5) * 0.35
    ring = np.exp(-((r - 0.85) / 0.06) ** 2)  # the dried edge of a drop (a coffee ring)
    inside = np.clip((0.85 - r) / 0.2, 0.0, 1.0) * 0.25
    image = np.clip(ring + inside, 0.0, 1.0) * (0.7 + 0.3 * A._fbm((size, size), 16, 3, rng))
    return A._border(image, 10)


# -- Schaden -----------------------------------------------------------------------------------------------------------


def scratches():
    rng = np.random.default_rng(1501)
    h, w = 128, 512
    image = np.zeros((h, w))
    for k in range(5):
        y = rng.uniform(30, 98)
        x0, x1 = rng.uniform(10, 120), rng.uniform(380, 500)
        xs = np.linspace(x0, x1, 50)
        ys = y + np.cumsum(rng.normal(0.0, 0.3, xs.size)) + (xs - x0) * rng.normal(0, 0.03)
        fade = np.sin(np.linspace(0.1, math.pi - 0.1, xs.size)) ** 0.5
        A._stroke_path(image, list(zip(xs, ys)), list(rng.uniform(0.8, 2.6) * np.ones(xs.size)),
                       list(fade * rng.uniform(0.5, 1.0, xs.size)))
    return A._border(image, 6)


def scar():
    rng = np.random.default_rng(1502)
    h, w = 192, 512
    image = np.zeros((h, w))
    xs = np.linspace(40, 472, 60)
    ys = h / 2 + 18 * np.sin(np.linspace(0, 2.2, xs.size)) + np.cumsum(rng.normal(0, 0.6, xs.size))
    t = np.linspace(0, 1, xs.size)
    widths = 4.0 + 26.0 * np.sin(np.pi * t) ** 0.8
    A._stroke_path(image, list(zip(xs, ys)), list(widths), list(0.55 + 0.45 * np.sin(np.pi * t)))
    texture = A._fbm((h, w), 16, 3, rng)
    for k in range(9):  # the stitch marks across it
        i = int(6 + k * 6)
        nx, ny = -(ys[i + 1] - ys[i - 1]), xs[i + 1] - xs[i - 1]
        norm = math.hypot(nx, ny)
        half = widths[i] * 0.9
        a = (xs[i] - nx / norm * half, ys[i] - ny / norm * half)
        b = (xs[i] + nx / norm * half, ys[i] + ny / norm * half)
        A._stroke_path(image, [a, b], [2.2, 2.2], [0.9, 0.9])
    return A._border(np.clip(image * (0.75 + 0.35 * texture), 0.0, 1.0), 8)


def cracks():
    rng = np.random.default_rng(1503)
    size = 512
    pts = rng.uniform(0, size, (34, 2))
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.sqrt((x[..., None] + 0.5 - pts[:, 0]) ** 2 + (y[..., None] + 0.5 - pts[:, 1]) ** 2)
    d.sort(axis=-1)
    edge = (d[..., 1] - d[..., 0]) * 0.5
    width = 1.2 + 2.2 * A._fbm((size, size), 64, 3, rng)
    lines = np.clip((width - edge) / 1.5, 0.0, 1.0) * np.clip((A._fbm((size, size), 32, 3, rng) - 0.3) / 0.2, 0.0, 1.0)
    return A._border(lines * _radial((size, size), 0.55, 0.95), 8)


# -- Oberfläche --------------------------------------------------------------------------------------------------------


def grain():
    rng = np.random.default_rng(1601)
    size = 512
    n = A._fbm((size, size), 4, 2, rng) - A._fbm((size, size), 32, 2, rng) * 0.5  # band-limited: fine minus coarse
    n = (n - n.min()) / (n.max() - n.min())
    image = np.clip((n - 0.35) / 0.4, 0.0, 1.0)
    return A._border(image * _radial(image.shape, 0.75, 0.97), 8)


def noise_irregular():
    rng = np.random.default_rng(1602)
    size = 512
    n = A._fbm((size, size), 48, 5, rng)
    image = np.clip((n - 0.4) / 0.3, 0.0, 1.0) ** 1.5
    return A._border(image * _radial(image.shape, 0.7, 0.97), 8)


# -- Formen ------------------------------------------------------------------------------------------------------------


def circle():
    size = 256
    y, x = np.mgrid[0:size, 0:size]
    d = np.hypot(x + 0.5 - 128, y + 0.5 - 128)
    return np.clip(118.0 - d, 0.0, 1.0)


def square():
    size = 256
    edge = np.minimum(np.arange(size), np.arange(size)[::-1]) + 0.5
    ramp = np.clip((edge - 10.0) / 1.5, 0.0, 1.0)
    return np.minimum(ramp[:, None], ramp[None, :])


def ring_soft():
    size = 256
    y, x = np.mgrid[0:size, 0:size]
    d = np.hypot(x + 0.5 - 128, y + 0.5 - 128) / 128.0
    return A._border(np.exp(-((d - 0.65) / 0.14) ** 2), 4)


def line():
    h, w = 64, 512
    image = np.zeros((h, w))
    A._stroke_path(image, [(24.0, 32.0), (488.0, 32.0)], [14.0, 14.0], [1.0, 1.0])
    return A._border(image, 4)


#: category -> [(stem, German name, generator)]; the order of the sheets and of `index.json`.
STARTER = {
    "organisch": [("poren_fein", "Poren fein", pores_fine), ("poren_grob", "Poren grob", pores_coarse),
                  ("poren_gruppe", "Poren gruppiert", pores_cluster), ("falten_kurz", "Falten kurz", creases_short),
                  ("kraehenfuss", "Krähenfüße", crows_foot)],
    "adern": [("adern_verzweigt", "Adern verzweigt", veins_branching), ("kapillaren", "Kapillaren", capillaries)],
    "sprenkel": [("sommersprossen", "Sommersprossen", freckles), ("punkte_gestreut", "Punkte gestreut", dots_scattered),
                 ("sprenkel_weich", "Sprenkel weich", speckle_soft)],
    "schmutz": [("fleck", "Fleck", stain), ("schmutz", "Schmutz", grime), ("ablagerung", "Ablagerung", deposit)],
    "schaden": [("kratzer", "Kratzer", scratches), ("narbe", "Narbe", scar), ("risse", "Risse", cracks)],
    "oberflaeche": [("koernung", "Körnung", grain), ("rauschen", "Rauschen unregelmäßig", noise_irregular)],
    "formen": [("kreis", "Kreis", circle), ("quadrat", "Quadrat", square), ("ring_weich", "Ring weich", ring_soft),
               ("linie", "Linie", line)],
}


def generate(make) -> np.ndarray:
    return np.clip(np.rint(make() * 255.0), 0, 255).astype(np.uint8)


# -- the contact sheet: stamps on a shaded sphere ----------------------------------------------------------------------

CELL = 300
SPHERE = 135.0  # px radius of the sphere in a cell
BASE = np.array([150.0, 146.0, 140.0])
PAINT = np.array([95.0, 28.0, 24.0])


def _sphere_points():
    c = (np.arange(CELL) + 0.5 - CELL / 2) / SPHERE
    y, x = np.meshgrid(-c, c, indexing="ij")
    rr = x * x + y * y
    inside = rr < 1.0
    z = np.sqrt(np.clip(1.0 - rr, 0.0, 1.0))
    return np.stack((x, y, z), axis=-1), inside


def _path(radius: float, spacing: float):
    """Placements along a latitude band (y = 0.25) across the front, every `spacing` stamp diameters of arc."""
    y0 = 0.15
    r0 = math.sqrt(1 - y0 * y0)
    step = spacing * 2.0 * radius / r0
    thetas = np.arange(-1.05, 1.05 + 1e-9, step)
    return [(np.array([r0 * math.sin(t), y0, r0 * math.cos(t)]), np.array([math.cos(t), 0.0, -math.sin(t)]))
            for t in thetas]


def _stamp(cover, pts, inside, image, centre, tangent, radius, angle_deg, flow):
    n = centre / np.linalg.norm(centre)
    t = tangent - n * np.dot(tangent, n)
    t /= np.linalg.norm(t)
    b = np.cross(n, t)
    a = math.radians(angle_deg)
    t, b = math.cos(a) * t + math.sin(a) * b, math.cos(a) * b - math.sin(a) * t
    d = pts - centre
    la, lb, lh = d @ t / radius, d @ b / radius, d @ n / radius
    hw, hh = image.half_extents
    mask = inside & (np.abs(la) <= hw) & (np.abs(lb) <= hh) & (np.abs(lh) < 0.5)
    if not mask.any():
        return
    level = image.level_for(2.0 * radius * SPHERE)
    c = image.sample_local(level, la[mask].astype(np.float32), lb[mask].astype(np.float32))
    depth = np.clip((0.5 - np.abs(lh[mask])) / 0.15, 0.0, 1.0)
    cover[mask] = 1.0 - (1.0 - cover[mask]) * (1.0 - flow * c * depth)


def strip(image, spray: bool) -> np.ndarray:
    from mirai.paint import dynamics as D

    pts, inside = _sphere_points()
    cover = np.zeros(inside.shape)
    if spray:
        dyn = D.StrokeDynamics(spacing=0.5, emitter="spray", spray_density=12, spray_size=0.3, orientation="random",
                               jitter_size=0.3, jitter_flow=0.3)
        radius = 0.36
        for i, (p, tangent) in enumerate(_path(radius, dyn.spacing)):
            values = D.random_values(7, i, range(dyn.spray_density))
            pos = D.spray_positions(dyn, values)
            angles, sizes, flows = D.stamp_jitter(dyn, values)
            n = p / np.linalg.norm(p)
            b = np.cross(n, tangent)
            for (along, across), ang, size, flow in zip(pos, angles, sizes, flows):
                centre = p + (along * tangent + across * b) * radius
                centre /= np.linalg.norm(centre)  # back on the sphere
                _stamp(cover, pts, inside, image, centre, tangent, radius * dyn.spray_size * size, ang,
                       min(flow, 1.0))
    else:
        radius = 0.27
        for p, tangent in _path(radius, 1.0):
            _stamp(cover, pts, inside, image, p, tangent, radius, 0.0, 1.0)
    light = np.array([-0.4, 0.5, 0.77])
    shade = np.clip(pts @ (light / np.linalg.norm(light)), 0.0, 1.0) * 0.8 + 0.2
    colour = (BASE * (1.0 - cover[..., None]) + PAINT * cover[..., None]) * shade[..., None]
    out = np.full(inside.shape + (3,), 34.0)
    out[inside] = colour[inside]
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def alpha_cell(image) -> np.ndarray:
    value = A.fitted(image, CELL - 20)
    cell = np.full((CELL, CELL, 3), 34, np.uint8)
    cell[10:-10, 10:-10] = np.clip(np.rint(34 + value[..., None] * (240 - 34)), 0, 255).astype(np.uint8)
    return cell


def _label(sheet: np.ndarray, texts: list[tuple[int, int, str]]) -> np.ndarray:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return sheet
    picture = Image.fromarray(sheet)
    draw = ImageDraw.Draw(picture)
    try:
        font = ImageFont.load_default(size=15)
    except TypeError:
        font = ImageFont.load_default()
    for x, y, text in texts:
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss")):
            text = text.replace(a, b)  # the default bitmap font has no umlauts
        draw.text((x, y), text, fill=(235, 235, 235), font=font)
    return np.asarray(picture)


def write_png(path: Path, rgb: np.ndarray) -> None:
    from mirai.iris_import import encode_png

    rgba = np.concatenate((rgb, np.full(rgb.shape[:2] + (1,), 255, np.uint8)), axis=-1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_png(rgba))


def sheets(out: Path) -> list[Path]:
    from mirai.paint.library import CATEGORIES

    written, legend = [], ["# Starter-Alphas - Kontaktbogen (AD-037 §14)", "",
                           "Spalten: das Alpha | Einzeln (Abstand 100 %) | Spray (12 Stempel je Platzierung, Zufall) auf einer Kugel; Strich von links nach rechts.",
                           ""]
    header = 28
    overview = []
    for category, entries in STARTER.items():
        rows = []
        texts = [(8, 6, f"{CATEGORIES[category]}  -  Alpha | Einzeln | Spray")]
        legend.append(f"## {CATEGORIES[category]} (`{category}`)")
        for k, (stem, name, make) in enumerate(entries):
            pixels = generate(make)
            image = A.AlphaImage.from_pixels(f"builtin:{category}/{stem}", name, pixels)
            rows.append(np.concatenate((alpha_cell(image), strip(image, False), strip(image, True)), axis=1))
            texts.append((14, header + k * CELL + 12, f"{name}  ({pixels.shape[1]} x {pixels.shape[0]})"))
            legend.append(f"- {name} (`{stem}`, {pixels.shape[1]} x {pixels.shape[0]} px)")
            overview.append((name, image))
        legend.append("")
        body = np.concatenate(rows, axis=0)
        sheet = np.concatenate((np.full((header, body.shape[1], 3), 20, np.uint8), body), axis=0)
        path = out / f"contact_sheet_{category}.png"
        write_png(path, _label(sheet, texts))
        written.append(path)
    cols, cell = 6, 160
    rows_n = math.ceil(len(overview) / cols)
    grid = np.full((rows_n * (cell + 22), cols * cell, 3), 20, np.uint8)
    texts = []
    for i, (name, image) in enumerate(overview):
        r, c = divmod(i, cols)
        value = A.fitted(image, cell - 12)
        y0, x0 = r * (cell + 22) + 22, c * cell
        grid[y0 + 6:y0 + cell - 6, x0 + 6:x0 + cell - 6] = np.rint(34 + value[..., None] * 206).astype(np.uint8)
        texts.append((x0 + 6, y0 - 18, name))
    path = out / "contact_sheet_overview.png"
    write_png(path, _label(grid, texts))
    written.append(path)
    (out / "contact_sheet.md").write_text("\n".join(legend) + "\n", encoding="utf-8")
    return written


def adopt(categories: list[str]) -> list[Path]:
    """Write the accepted categories into `assets/paint/alphas/` (+ index.json, LICENSES.md)."""
    from mirai.paint.library import CATEGORIES, encode_grey_png

    root = ASSETS / "alphas"
    index_path = root / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {}
    written = []
    for category in categories:
        for stem, name, make in STARTER[category]:
            pixels = generate(make)
            path = root / category / f"{stem}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encode_grey_png(pixels, level=9))
            index[f"{category}/{stem}"] = {"name": name, "hash": A.pixel_hash(pixels)}
            written.append(path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Paint assets - sources and licences", "",
             "Every file below `alphas/` is generated by `tools/make_starter_alphas.py` (deterministic, NumPy, our own",
             "work; the repository's terms). No external image is bundled. CC0 alphas may be added later only with the",
             "source, the licence text and the date recorded per file (Manu 2026-11-25).", "",
             "| File | Source |", "|---|---|"]
    for key in sorted(index):
        category = key.split("/")[0]
        lines.append(f"| `alphas/{key}.png` ({CATEGORIES.get(category, category)}) | generated, "
                     f"`tools/make_starter_alphas.py` |")
    (ASSETS / "LICENSES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sheet", type=Path, default=DEFAULT_SHEETS, help="where the contact sheets go")
    parser.add_argument("--adopt", default="", help="comma-separated categories Manu accepted, or 'all'")
    args = parser.parse_args(argv)
    if args.adopt:
        names = list(STARTER) if args.adopt == "all" else [c.strip() for c in args.adopt.split(",") if c.strip()]
        unknown = [c for c in names if c not in STARTER]
        if unknown:
            parser.error(f"unknown categories {unknown}; one of {list(STARTER)}")
        for path in adopt(names):
            print(path.relative_to(REPO))
        return 0
    for path in sheets(args.sheet):
        print(path.relative_to(REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
