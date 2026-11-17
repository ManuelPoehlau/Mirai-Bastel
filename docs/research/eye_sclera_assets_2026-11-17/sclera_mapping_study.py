"""Sclera mapping study (research only, 2026-11-17): renders a unit eyeball under three candidate mappings with an
emulated mip selection (screen-space derivatives -> LOD, as the GPU does), builds a synthetic sclera texture in the
front-disc layout, a layout template, and prints the distortion numbers used in the report. NumPy + PIL only."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

LIMBUS_R = 0.49                      # DEFAULT_EYE.limbus_radius (eye-local, sclera radius 1)
THETA_L = math.asin(LIMBUS_R)        # 29.34 deg
THETA_MAX = math.radians(130.0)      # proposed rim of the front disc
R_L = 0.25                           # proposed: limbus circle at a quarter of the half width
LID_UPPER, LID_LOWER = 0.37, -0.47   # DEFAULT_LOOK.lid_upper / lid_lower (rest frame, eye-local y)
CANTHUS_DEG = 75.0                   # ESTIMATE: horizontal extent of the open fissure on the globe
MM = 12.0                            # sclera radius in mm at the reference eye


# --------------------------------------------------------------------------------------------- mappings (eye-local)
def theta_of(p):
    return np.arctan2(np.hypot(p[..., 0], p[..., 1]), p[..., 2])


def map_a1(p):  # axis-polar equirectangular, seam at 6 o'clock
    phi = np.arctan2(p[..., 1], p[..., 0])
    u = np.mod((phi + np.pi / 2) / (2 * np.pi), 1.0)
    return np.stack([u, 1.0 - theta_of(p) / np.pi], -1)


def map_a2(p):  # lat-long, poles up/down, seam behind
    lon = np.arctan2(p[..., 0], p[..., 2])
    lat = np.arcsin(np.clip(p[..., 1], -1, 1))
    return np.stack([0.5 + lon / (2 * np.pi), 0.5 + lat / np.pi], -1)


def disc_radius(theta, theta_l=THETA_L):
    inner = R_L * theta / theta_l
    outer = R_L + (1.0 - R_L) * (theta - theta_l) / (THETA_MAX - theta_l)
    return np.minimum(np.where(theta < theta_l, inner, outer), 1.0)


def map_b(p):  # limbus-anchored azimuthal equidistant front disc
    rho = np.hypot(p[..., 0], p[..., 1])
    r = disc_radius(theta_of(p))
    k = np.where(rho > 1e-9, r / np.maximum(rho, 1e-9), 0.0)
    return np.stack([0.5 + 0.5 * p[..., 0] * k, 0.5 + 0.5 * p[..., 1] * k], -1)


MAPPINGS = {"A1 axis-polar strip": map_a1, "A2 lat-long (poles up/down)": map_a2, "B front disc (proposed)": map_b}


# --------------------------------------------------------------------------------------------- textures
def checker(w, h, cells_u, cells_v, rings=False):
    v, u = np.mgrid[0:h, 0:w]
    u = (u + 0.5) / w
    v = (v + 0.5) / h
    c = ((np.floor(u * cells_u) + np.floor(v * cells_v)) % 2).astype(np.float32)
    rgb = np.empty((h, w, 3), np.float32)
    rgb[...] = np.array([0.93, 0.89, 0.82])
    rgb[c > 0.5] = np.array([0.62, 0.70, 0.86])
    if rings:  # B: grey outside the disc, the limbus ring and the 90 deg ring
        r = np.hypot(u - 0.5, v - 0.5) * 2
        rgb[r > 1.0] = np.array([0.5, 0.5, 0.5])
        for radius in (R_L, float(disc_radius(np.array(np.pi / 2)))):
            rgb[np.abs(r - radius) < 0.006] = np.array([0.8, 0.15, 0.1])
    return rgb


def pyramid(tex):
    levels = [tex]
    while min(levels[-1].shape[:2]) > 1:
        t = levels[-1]
        h, w = t.shape[0] // 2 * 2, t.shape[1] // 2 * 2
        t = t[:h, :w]
        levels.append(0.25 * (t[0::2, 0::2] + t[1::2, 0::2] + t[0::2, 1::2] + t[1::2, 1::2]))
    return levels


def bilinear(t, uv, wrap_u):
    h, w = t.shape[:2]
    x = uv[..., 0] * w - 0.5
    y = (1.0 - uv[..., 1]) * h - 0.5  # image rows run top-down, v up
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]

    def at(xi, yi):
        xi = np.mod(xi, w) if wrap_u else np.clip(xi, 0, w - 1)
        return t[np.clip(yi, 0, h - 1), xi]

    return ((1 - fx) * (1 - fy) * at(x0, y0) + fx * (1 - fy) * at(x0 + 1, y0)
            + (1 - fx) * fy * at(x0, y0 + 1) + fx * fy * at(x0 + 1, y0 + 1))


def sample_mip(levels, uv, valid):
    """Trilinear-ish (nearest of the two levels blended) with the LOD from screen-space derivatives of the raw uv, as
    `texture()` does: an atan2 jump in u gives a huge derivative and drops that pixel quad to a coarse level."""
    h, w = levels[0].shape[:2]
    du_x = np.zeros(uv.shape[:2]); du_y = np.zeros(uv.shape[:2])
    dv_x = np.zeros(uv.shape[:2]); dv_y = np.zeros(uv.shape[:2])
    du_x[:, :-1] = np.diff(uv[..., 0], axis=1); du_y[:-1] = np.diff(uv[..., 0], axis=0)
    dv_x[:, :-1] = np.diff(uv[..., 1], axis=1); dv_y[:-1] = np.diff(uv[..., 1], axis=0)
    rho = np.maximum(np.hypot(du_x * w, dv_x * h), np.hypot(du_y * w, dv_y * h))
    lod = np.clip(np.log2(np.maximum(rho, 1e-6)), 0, len(levels) - 1)
    lo = np.floor(lod).astype(int)
    f = (lod - lo)[..., None]
    out = np.zeros(uv.shape[:2] + (3,), np.float32)
    for level in range(len(levels)):
        mask = valid & ((lo == level) | (lo + 1 == level))
        if not mask.any():
            continue
        c = bilinear(levels[level], uv[mask], wrap_u=True)
        weight = np.where(lo[mask] == level, 1 - f[mask][:, 0], f[mask][:, 0])[:, None]
        out[mask] += weight * c
    return out


# --------------------------------------------------------------------------------------------- rendering
def rot_y(deg):
    a = math.radians(deg)
    return np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])


def render(tex_levels, mapping, view_deg, size=300, gaze_deg=0.0, lids=False, iris=True, light=True):
    """Orthographic view of the unit eyeball from `view_deg` yaw (0 = frontal). The eye turns by `gaze_deg` yaw
    (drawn frame); the lids stay in the rest frame."""
    d = rot_y(view_deg) @ np.array([0.0, 0.0, 1.0])
    right = np.cross([0.0, 1.0, 0.0], d); right /= np.linalg.norm(right)
    up = np.cross(d, right)
    s = np.linspace(-1.08, 1.08, size)
    sx, sy = np.meshgrid(s, -s)
    rr = sx ** 2 + sy ** 2
    valid = rr < 1.0
    z = np.sqrt(np.clip(1 - rr, 0, 1))
    world = sx[..., None] * right + sy[..., None] * up + z[..., None] * d   # rest frame == world here
    g = rot_y(gaze_deg)
    local = world @ g  # inverse rotation (g orthonormal): eye-local point
    uv = mapping(local)
    col = sample_mip(tex_levels, uv, valid)
    if iris:
        th = theta_of(local)
        col[valid & (th < THETA_L)] = np.array([0.30, 0.24, 0.12])
        col[valid & (th < 0.16 / 0.49 * THETA_L)] = np.array([0.03, 0.03, 0.03])
    if light:
        key = np.array([-0.45, 0.55, 0.70]); key /= np.linalg.norm(key)
        lam = np.clip(world @ key, 0, 1)
        col = col * (0.45 + 0.65 * lam)[..., None]
    if lids:
        hidden = (world[..., 1] > LID_UPPER) | (world[..., 1] < LID_LOWER) | \
                 (np.degrees(theta_of(world)) > CANTHUS_DEG)
        col[valid & hidden] *= 0.28
    img = np.ones((size, size, 3), np.float32) * 0.16
    img[valid] = col[valid]
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def label(img, text):
    im = Image.fromarray(img)
    ImageDraw.Draw(im).text((6, 4), text, fill=(255, 255, 255))
    return np.asarray(im)


def grid(rows):
    return np.concatenate([np.concatenate(r, axis=1) for r in rows], axis=0)


# --------------------------------------------------------------------------------------------- synthetic sclera
def smooth_noise(rng, size, sigma):
    im = Image.fromarray((rng.random((size, size)) * 255).astype(np.uint8))
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(sigma)), np.float32) / 255.0
    return (a - a.mean()) / (a.std() + 1e-6)


def synthetic_sclera(size=1024, seed=7):
    """A painted-style test map in the front-disc layout: an off-white base with low-frequency warm / pink / grey
    variation, more colour toward the rim and at 3 / 9 o'clock, and fine branching vessels from the rim toward the
    limbus that stop ~1.5 mm short of it. Generated, so it carries no third-party rights."""
    rng = np.random.default_rng(seed)
    v, u = np.mgrid[0:size, 0:size]
    x = (u + 0.5) / size * 2 - 1
    y = 1 - (v + 0.5) / size * 2
    r = np.hypot(x, y)
    base = np.array([0.86, 0.82, 0.74], np.float32)  # warmer than SCLERA_COLOUR, Gollum-leaning (agent choice)
    n1, n2, n3 = (smooth_noise(rng, size, s) for s in (60, 28, 9))
    rgb = np.empty((size, size, 3), np.float32)
    rgb[...] = base
    rim = np.clip((r - R_L) / (1 - R_L), 0, 1)
    side = np.abs(x) / np.maximum(r, 1e-6)  # 3 / 9 o'clock (interpalpebral) emphasis
    rim = np.minimum(rim, 1.0)
    pink = 0.012 * n1 + 0.03 * rim ** 1.5 + 0.02 * side * rim
    yellow = 0.012 * n2
    grey = 0.006 * n3
    rgb[..., 0] += 0.4 * pink - grey
    rgb[..., 1] += -0.6 * pink - 0.2 * yellow - grey
    rgb[..., 2] += -0.5 * pink - 0.9 * yellow - grey
    img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))

    ss = 2  # supersampled vessels
    layer = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    stop = R_L + 0.06  # ~1.5 mm before the limbus

    def vessel(px, py, angle, width, depth, deep):
        steps = 0
        while depth >= 0 and steps < 400:
            steps += 1
            rr = math.hypot(px, py)
            if rr < stop or rr > 1.02:
                return
            inward = math.atan2(-py, -px)
            angle += 0.25 * math.sin(inward - angle) + rng.normal(0, 0.16)
            step = 0.012
            nx, ny = px + step * math.cos(angle), py + step * math.sin(angle)
            fade = min(1.0, (rr - stop) / 0.12)
            colour = (128, 72, 92) if deep else (176, 66, 58)
            alpha = int(255 * (0.30 if deep else 0.42) * fade * min(1.0, width / 2.2 + 0.35))
            to_px = lambda a, b: ((a + 1) / 2 * size * ss, (1 - b) / 2 * size * ss)  # noqa: E731
            draw.line([to_px(px, py), to_px(nx, ny)], fill=colour + (alpha,), width=max(1, int(width * ss)))
            px, py = nx, ny
            width *= 0.985
            if rng.random() < 0.03 and depth > 0:
                vessel(px, py, angle + rng.choice([-1, 1]) * rng.uniform(0.7, 1.3), width * 0.65, depth - 1, deep)
            if width < 0.6:
                return

    for i in range(70):
        a = rng.uniform(0, 2 * math.pi)
        weight = 1.0 + 0.8 * abs(math.cos(a))  # more vessels toward the canthi
        if rng.random() > weight / 1.8:
            continue
        deep = rng.random() < 0.3
        start = rng.uniform(0.8, 1.0)
        vessel(start * math.cos(a), start * math.sin(a), a + math.pi + rng.normal(0, 0.3),
               rng.uniform(1.6, 3.4) * (1.4 if deep else 1.0), 2, deep)
    layer = layer.resize((size, size), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    return np.asarray(img, np.float32) / 255.0


def template(size=1024):
    """The layout guide for painters (front disc): limbus ring, 2 mm rings, the 90 deg ring, the rim, the rest lid band
    and fissure, and the region that becomes visible with gaze up to 50 deg sideways / 30 deg up and down."""
    v, u = np.mgrid[0:size, 0:size]
    x = (u + 0.5) / size * 2 - 1
    y = 1 - (v + 0.5) / size * 2
    r = np.hypot(x, y)
    # invert the disc radius -> theta
    theta = np.where(r < R_L, r / R_L * THETA_L, THETA_L + (r - R_L) / (1 - R_L) * (THETA_MAX - THETA_L))
    phi = np.arctan2(y, x)
    p = np.stack([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)], -1)

    def visible_at_rest(q):
        return (q[..., 1] <= LID_UPPER) & (q[..., 1] >= LID_LOWER) & (np.degrees(theta_of(q)) <= CANTHUS_DEG)

    rest = visible_at_rest(p)
    gaze = np.zeros_like(rest)
    for yaw in range(-50, 51, 10):
        for pitch in (-40, -30, -15, 0, 15, 30, 40):
            a, b = math.radians(yaw), math.radians(pitch)
            if math.degrees(math.acos(math.cos(a) * math.cos(b))) > 50.0 + 1e-6:
                continue  # MAX_GAZE_DEGREES caps the total swing
            ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
            rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
            gaze |= visible_at_rest(p @ (ry @ rx).T)
    img = np.ones((size, size, 3), np.float32) * 0.35
    img[r <= 1] = 0.55
    img[gaze & (r <= 1)] = np.array([0.72, 0.78, 0.86])
    img[rest & (r <= 1)] = np.array([0.95, 0.93, 0.88])
    img[r < R_L] = np.array([0.30, 0.24, 0.12])
    im = Image.fromarray((img * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    c = size / 2

    def ring(rad, colour, w=2):
        d.ellipse([c - rad * c, c - rad * c, c + rad * c, c + rad * c], outline=colour, width=w)

    for mm in range(2, 26, 2):  # every 2 mm of arc from the limbus
        t = THETA_L + mm / MM
        if t < THETA_MAX:
            ring(float(disc_radius(np.array(t))), (150, 150, 150), 1)
    ring(R_L, (200, 40, 30), 3)
    ring(float(disc_radius(np.array(np.pi / 2))), (40, 90, 200), 2)
    ring(1.0, (0, 0, 0), 3)
    d.line([(c, 0), (c, size)], fill=(120, 120, 120)); d.line([(0, c), (size, c)], fill=(120, 120, 120))
    for text, pos in (("limbus (0 mm)", (c + R_L * c * 0.72 + 4, c - R_L * c * 0.72 - 14)),
                      ("90 deg (equator of the globe)", (c + 6, c - 0.752 * c - 16)),
                      ("rim = 130 deg from the front pole", (c + 6, 8)),
                      ("+X (image right)", (size - 120, c + 6)), ("+Y (image up)", (c + 6, 30)),
                      ("white: open fissure at rest (lids from the default look)", (10, size - 46)),
                      ("blue: visible with gaze up to 50 deg (any direction); grey rings = 2 mm arc", (10, size - 28))):
        d.text(pos, text, fill=(0, 0, 0))
    return im, rest, gaze, r


def main():
    # 1. distortion numbers ------------------------------------------------------------------------------------------
    print("theta_l = %.2f deg, rim = %.0f deg, R_L = %.3f" % (math.degrees(THETA_L), math.degrees(THETA_MAX), R_L))
    print("B (1024^2): radial px/mm inner %.1f, outer %.1f" % (
        R_L * 512 / (THETA_L * MM), (1 - R_L) * 512 / ((THETA_MAX - THETA_L) * MM)))
    print("theta  B_tan_px/mm  B_aniso   A2_px/mm(1448x724) at lat 0 / 40  A1_tan_aniso(1024x1024 eq-mem)")
    for deg in (29.34, 45, 60, 75, 90, 105, 120, 130):
        t = math.radians(deg)
        rb = float(disc_radius(np.array(t)))
        tan = rb * 512 / (MM * math.sin(t))
        rad = (1 - R_L) * 512 / ((THETA_MAX - THETA_L) * MM)
        a1_tan = 1024 / (2 * math.pi * MM * math.sin(t)); a1_rad = 1024 / (math.pi * MM)
        print(f"{deg:6.1f}  {tan:10.1f}  {tan / rad:8.2f}   {1448 / (2 * math.pi * MM):.1f} / "
              f"{1448 / (2 * math.pi * MM * math.cos(math.radians(40))):.1f}            {a1_tan / a1_rad:6.2f}")

    # 2. mapping renders with a diagnostic checker -------------------------------------------------------------------
    checkers = {"A1 axis-polar strip": pyramid(checker(1024, 512, 24, 12)),
                "A2 lat-long (poles up/down)": pyramid(checker(1024, 512, 24, 12)),
                "B front disc (proposed)": pyramid(checker(1024, 1024, 16, 16, rings=True))}
    rows = []
    for name, mapping in MAPPINGS.items():
        tiles = [label(render(checkers[name], mapping, view), f"{name}: {vname}")
                 for view, vname in ((0, "frontal"), (45, "3/4"), (90, "side"), (180, "back"))]
        # seam of A1 from below: tilt the camera by turning the eye 70 deg up (shows the 6 o'clock meridian)
        rows.append(tiles)
    Image.fromarray(grid(rows)).save(OUT / "mapping_renders.png", optimize=True)

    # A1 seam from below (the 6 o'clock meridian) and A2 pole from above, emulated mip selection
    def render_pitch(levels, mapping, pitch_deg, size=300):
        b = math.radians(pitch_deg)
        rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
        return render(levels, lambda p: mapping(p @ rx.T), 0, size)

    seam = [label(render_pitch(checkers["A1 axis-polar strip"], map_a1, -60), "A1: eye turned 60 deg up (6 o'clock seam)"),
            label(render_pitch(checkers["A2 lat-long (poles up/down)"], map_a2, -75), "A2: eye turned 75 deg up (lower pole)"),
            label(render_pitch(checkers["B front disc (proposed)"], map_b, -60), "B: eye turned 60 deg up (no seam)")]
    Image.fromarray(grid([seam])).save(OUT / "mapping_seams.png", optimize=True)

    # 3. synthetic sclera + renders ----------------------------------------------------------------------------------
    sclera = synthetic_sclera()
    Image.fromarray((sclera * 255 + 0.5).astype(np.uint8)).save(OUT / "synthetic_sclera_front_disc_1024.png",
                                                               optimize=True)
    levels = pyramid(sclera)
    views = [label(render(levels, map_b, 0, lids=True), "frontal, lids (rest)"),
             label(render(levels, map_b, 0, gaze_deg=30, lids=True), "frontal, gaze 30 deg (map turns with eye)"),
             label(render(levels, map_b, 45, lids=True), "3/4, lids"),
             label(render(levels, map_b, 90), "side (no lids)")]
    Image.fromarray(grid([views])).save(OUT / "synthetic_sclera_renders.png", optimize=True)

    # 4. template --------------------------------------------------------------------------------------------------
    im, rest, gaze, r = template()
    im.save(OUT / "front_disc_template_1024.png", optimize=True)
    disc = r <= 1
    print("template: share of the image in the disc %.1f %%, visible at rest %.1f %%, with gaze %.1f %%" % (
        100 * disc.mean(), 100 * (rest & disc).mean(), 100 * (gaze & disc).mean()))
    rmax_rest = r[rest & disc].max(); rmax_gaze = r[gaze & disc].max()
    print("largest visible disc radius: rest %.3f (%.0f deg), gaze %.3f (%.0f deg)" % (
        rmax_rest, math.degrees(THETA_L + (rmax_rest - R_L) / (1 - R_L) * (THETA_MAX - THETA_L)),
        rmax_gaze, math.degrees(THETA_L + (rmax_gaze - R_L) / (1 - R_L) * (THETA_MAX - THETA_L))))
    # A2: share of a 2:1 image visible with gaze (sample the sphere)
    rng = np.random.default_rng(1)
    q = rng.normal(size=(400000, 3)); q /= np.linalg.norm(q, axis=1)[:, None]
    vis = np.zeros(len(q), bool)
    for yaw in range(-50, 51, 10):
        for pitch in (-40, -30, -15, 0, 15, 30, 40):
            a, b = math.radians(yaw), math.radians(pitch)
            if math.degrees(math.acos(math.cos(a) * math.cos(b))) > 50.0 + 1e-6:
                continue  # MAX_GAZE_DEGREES caps the total swing
            ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
            rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
            w = q @ (ry @ rx).T
            vis |= (w[:, 1] <= LID_UPPER) & (w[:, 1] >= LID_LOWER) & (np.degrees(theta_of(w)) <= CANTHUS_DEG)
    vis &= theta_of(q) >= THETA_L
    uv = map_a2(q)
    hist = np.zeros((64, 128), bool)
    hist[np.clip((uv[vis, 1] * 64).astype(int), 0, 63), np.clip((uv[vis, 0] * 128).astype(int), 0, 127)] = True
    print("A2: share of the 2:1 image visible with gaze %.1f %%; sphere share visible with gaze %.1f %%, max theta %.0f"
          % (100 * hist.mean(), 100 * vis.mean(), np.degrees(theta_of(q[vis])).max()))


if __name__ == "__main__":
    main()
