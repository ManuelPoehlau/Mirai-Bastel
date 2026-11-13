"""Debug pictures (PNG via Pillow, optional): an orthographic z-buffered render of a triangle mesh with per-vertex
colours, plus points and polylines on top. Only for looking at results; no measurement depends on it."""

from __future__ import annotations

import numpy as np


def _basis(view: str):
    table = {
        "front": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),      # looking down -z: x right, y up, +z towards the viewer
        "back": ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
        "right": ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
        "left": ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
        "top": ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
    }
    return tuple(np.array(a, dtype=np.float64) for a in table[view])


class View:
    def __init__(self, V: np.ndarray, view: str = "front", size: int = 900, pad: float = 0.04, axes=None) -> None:
        self.right, self.up, self.toward = _basis(view) if axes is None else axes
        xy = np.stack([V @ self.right, V @ self.up], axis=1)
        lo, hi = xy.min(axis=0), xy.max(axis=0)
        span = float(max(hi - lo)) * (1.0 + 2.0 * pad)
        self.scale = size / span
        self.origin = (lo + hi) / 2.0
        self.size = size

    def project(self, P: np.ndarray) -> np.ndarray:
        x = (P @ self.right - self.origin[0]) * self.scale + self.size / 2.0
        y = self.size / 2.0 - (P @ self.up - self.origin[1]) * self.scale
        return np.stack([x, y, P @ self.toward], axis=1)


def render(V: np.ndarray, T: np.ndarray, colors: np.ndarray | None = None, view: str = "front", size: int = 900,
           wire_edges: np.ndarray | None = None, axes=None):
    """-> `(PIL.Image, View, depth buffer)`; `colors` per vertex in 0..1 (default: grey, lit from the viewer)."""
    from PIL import Image

    cam = View(V, view, size, axes=axes)
    S = cam.project(V)
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
    light = np.abs(n @ cam.toward) * 0.75 + 0.25
    base = np.full((len(V), 3), 0.72) if colors is None else np.asarray(colors, dtype=np.float64)
    img = np.ones((size, size, 3))
    depth = np.full((size, size), -np.inf)
    for t in range(len(T)):
        a, b, c = S[T[t, 0]], S[T[t, 1]], S[T[t, 2]]
        x0 = max(int(np.floor(min(a[0], b[0], c[0]))), 0)
        x1 = min(int(np.ceil(max(a[0], b[0], c[0]))), size - 1)
        y0 = max(int(np.floor(min(a[1], b[1], c[1]))), 0)
        y1 = min(int(np.ceil(max(a[1], b[1], c[1]))), size - 1)
        if x0 > x1 or y0 > y1:
            continue
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        w1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        z = w0 * a[2] + w1 * b[2] + w2 * c[2]
        sub = depth[y0:y1 + 1, x0:x1 + 1]
        win = inside & (z > sub)
        if not np.any(win):
            continue
        col = (w0[..., None] * base[T[t, 0]] + w1[..., None] * base[T[t, 1]] + w2[..., None] * base[T[t, 2]]) * light[t]
        sub[win] = z[win]
        img[y0:y1 + 1, x0:x1 + 1][win] = col[win]
    image = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    if wire_edges is not None:
        draw_segments(image, cam, depth, V[wire_edges[:, 0]], V[wire_edges[:, 1]], (60, 60, 60), 1)
    return image, cam, depth


def _visible(cam: View, depth: np.ndarray, P: np.ndarray, tol: float) -> np.ndarray:
    S = cam.project(P)
    xi = np.clip(S[:, 0].astype(int), 0, cam.size - 1)
    yi = np.clip(S[:, 1].astype(int), 0, cam.size - 1)
    return S[:, 2] >= depth[yi, xi] - tol


def draw_segments(image, cam: View, depth, A: np.ndarray, B: np.ndarray, color, width: int = 1, tol: float | None = None):
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    tol = 0.02 * cam.size / cam.scale / 10.0 if tol is None else tol
    mid = (A + B) / 2.0
    vis = _visible(cam, depth, mid, tol)
    SA, SB = cam.project(A), cam.project(B)
    for i in np.flatnonzero(vis):
        draw.line([(SA[i, 0], SA[i, 1]), (SB[i, 0], SB[i, 1])], fill=tuple(color), width=width)


def draw_points(image, cam: View, depth, P: np.ndarray, color, radius: int = 3, tol: float | None = None,
                always: bool = False):
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    tol = 0.02 * cam.size / cam.scale / 10.0 if tol is None else tol
    vis = np.ones(len(P), dtype=bool) if always else _visible(cam, depth, P, tol)
    S = cam.project(P)
    colors = np.broadcast_to(np.asarray(color), (len(P), 3))
    for i in np.flatnonzero(vis):
        x, y = S[i, 0], S[i, 1]
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=tuple(int(c) for c in colors[i]))


def ramp(values: np.ndarray, vmax: float) -> np.ndarray:
    """0..vmax -> light grey .. orange .. dark red (one hue ramp, for error magnitudes)."""
    t = np.clip(np.asarray(values, dtype=np.float64) / max(vmax, 1e-300), 0.0, 1.0)[:, None]
    stops = np.array([[0.86, 0.86, 0.86], [0.98, 0.72, 0.35], [0.80, 0.22, 0.12], [0.35, 0.05, 0.08]])
    x = t * 3.0
    i = np.clip(x.astype(int), 0, 2)
    f = x - i
    return stops[i[:, 0]] * (1 - f) + stops[i[:, 0] + 1] * f
