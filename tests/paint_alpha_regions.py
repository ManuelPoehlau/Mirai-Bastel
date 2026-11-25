"""The probe placements and metrics of AD-037 §12 Phase 4a's curvature validation (proposal 2026-11-25 §4.3).

Shared by `tests/test_paint_alpha.py`, `experiments/drag_cost/probe_paint.py` and the contact sheet
(`experiments/drag_cost/contact_sheet_paint_4a.py`). The placements are rays of a fixed front view of the Gollum head
(`scenes/Gollum_Head_rigging_test.mirai.json`: the camera on +Z, 2.2 bounding radii away, 50° fov, a 900² view),
picked on a render of it; the metrics:

- **stretch** (`stretch`): the stamp's painted area `Σ c·A` (A = the texel's world area on its triangle) against the
  planar ideal `r² ∫∫ alpha`, and the aspect `√(λ1 / λ2)` of the coverage-weighted covariance of its surface points
  (a round alpha: 1);
- **leak** (`leaked`): painted texels on triangles not connected to the stamp centre's triangle through the triangles
  within the stamp's reach (another surface sheet: the other lip, the inside of a nostril);
- **frame jump** (`frame_jumps`): the angle between successive placements' frame normals and tangents - literally;
  crossing the nose at 100 % spacing the surface itself turns 30-60° per placement, which no frame can avoid. So
  `frame_excess` measures the frame's own error: the normal jump beyond the turn of a smooth reference surface (the same
  inner-disc estimator on SubD 2, `reference_normal`) between the same placements, and the tangent's angle from the stroke's own direction
  at each placement ("Strich folgen" follows the stroke).
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np

from mirai.paint.alpha import AlphaImage

VIEW = 900
#: name -> (German label, pixel (x, y) from the top left of the front view)
REGIONS: dict[str, tuple[str, tuple[float, float]]] = {
    "nose_tip": ("Nasenspitze", (450.0, 455.0)),
    "nose_ridge": ("Nasenrücken", (450.0, 405.0)),
    "nostril_wing": ("Nasenflügel", (418.0, 462.0)),
    "lip_edge": ("Lippenkante", (430.0, 546.0)),
    "mouth_corner": ("Mundwinkel", (372.0, 570.0)),
    "cheek": ("Wange", (330.0, 470.0)),
    "lid": ("Lid", (340.0, 362.0)),
    "uv_seam": ("UV-Naht (Kinn, Mitte)", (450.0, 615.0)),
}
#: Scripted strokes for the frame jump (front-view pixels): across the nose ridge, over the lip edge.
STROKES: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "across_nose": ((395.0, 420.0), (505.0, 420.0)),
    "over_lip": ((430.0, 520.0), (430.0, 585.0)),
    "along_ridge": ((450.0, 370.0), (450.0, 445.0)),
    "over_wing": ((395.0, 470.0), (440.0, 455.0)),
}


def front_camera(mesh):
    from mirai.viewport.camera import OrbitCamera

    pts = np.array([mesh.vertex_position(v) for v in mesh.all_vertex_ids()])
    centre = pts.mean(axis=0)
    bounding = float(np.linalg.norm(pts - centre, axis=1).max())
    return OrbitCamera(target=tuple(centre), distance=2.2 * bounding, yaw=0.0, pitch=0.0)


def ray(camera, pixel):
    x, y = pixel
    origin, direction = camera.screen_to_ray(x, VIEW - y, VIEW, VIEW)
    return np.asarray(origin, float), np.asarray(direction, float)


def region_hit(surface, camera, name: str):
    return surface.hit(*ray(camera, REGIONS[name][1]))


def disc_alpha(size: int = 128) -> AlphaImage:
    """A round test alpha (the stretch ideal: aspect 1), full inside 0.85 of the half extent, soft to 0.95."""
    y, x = np.mgrid[0:size, 0:size]
    d = np.hypot(x + 0.5 - size / 2, y + 0.5 - size / 2) / (size / 2)
    pixels = np.clip((0.95 - d) / 0.1, 0.0, 1.0)
    return AlphaImage.from_pixels("test/disc", "Scheibe", np.rint(pixels * 255).astype(np.uint8))


def ideal_area(image: AlphaImage, radius: float) -> float:
    hw, hh = image.half_extents
    return radius * radius * 4.0 * hw * hh * float(image.pixels.mean()) / 255.0


def stretch(surface, stamp, radius: float, image: AlphaImage) -> tuple[float, float]:
    """(painted area / planar ideal, principal aspect) of one stamp."""
    if stamp.texels.size < 3:
        return 0.0, float("inf")
    slots = surface.map.slot[stamp.texels]
    weight = stamp.coverage.astype(np.float64) * surface._texel_area[slots]
    area = float(weight.sum())
    points = surface.map.surface_points(stamp.texels)
    mean = (points * weight[:, None]).sum(axis=0) / weight.sum()
    rel = points - mean
    cov = (rel * weight[:, None]).T @ rel / weight.sum()
    eig = np.sort(np.linalg.eigvalsh(cov))[::-1]
    return area / ideal_area(image, radius), math.sqrt(eig[0] / max(eig[1], 1e-30))


def leaked(surface, stamp, centre, reach: float) -> int:
    """Painted texels on triangles not connected to the centre's triangle within `reach` (module docstring)."""
    if stamp.texels.size == 0:
        return 0
    c = np.asarray(centre, dtype=np.float64)
    slots = surface._slot_clusters.box(c - reach, c + reach)
    near = np.all(surface._lo[slots] <= c + reach, axis=1) & np.all(surface._hi[slots] >= c - reach, axis=1)
    slots = slots[near & surface._live[slots]]
    rows = surface._tri_rows[slots]
    by_vertex: dict[int, list[int]] = {}
    for i, tri in enumerate(rows.tolist()):
        for v in tri:
            by_vertex.setdefault(v, []).append(i)
    painted_slots = surface.map.slot[stamp.texels]
    points = surface.map.surface_points(stamp.texels)
    start_slot = int(painted_slots[np.argmin(np.linalg.norm(points - c, axis=1))])
    index = {int(s): i for i, s in enumerate(slots.tolist())}
    if start_slot not in index:
        return int(stamp.texels.size)
    seen = {index[start_slot]}
    todo = deque(seen)
    while todo:
        i = todo.popleft()
        for v in rows[i].tolist():
            for j in by_vertex[v]:
                if j not in seen:
                    seen.add(j)
                    todo.append(j)
    connected = {int(slots[i]) for i in seen}
    return int(sum(1 for s in painted_slots.tolist() if int(s) not in connected))


def angle(u, v) -> float:
    cosine = float(np.clip(np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v)), -1.0, 1.0))
    return math.degrees(math.acos(cosine))


def frame_jumps(frames) -> tuple[list[float], list[float]]:
    """Per successive pair of frames: (normal angle changes, tangent angle changes) in degrees."""
    normals = [angle(a.n, b.n) for a, b in zip(frames, frames[1:])]
    tangents = [angle(a.t, b.t) for a, b in zip(frames, frames[1:])]
    return normals, tangents


def reference_normal(reference, point, radius: float, facing) -> np.ndarray:
    """The frame normal's own estimator (`stamp.INNER_DISC`'s area-weighted triangle normals) on the smooth `reference`
    surface (SubD 2) around its point nearest to `point`: like is compared with like, so only the facets of the painted
    surface make a difference (at a crease - the lips' line - any point normal would differ from a disc's mean)."""
    from mirai.paint import stamp

    search = radius * 0.1
    gathered = None
    while gathered is None:
        gathered = reference.gather(point, search, facing)
        search *= 2.0
    nearest = np.asarray(point, dtype=np.float64) + gathered.rel[int(np.argmin(gathered.d2))]
    inner = reference.gather(nearest, stamp.INNER_DISC * radius, facing)
    n = (reference._tri_normal[inner.slots] * reference._texel_area[inner.slots][:, None]).sum(axis=0)
    return n / np.linalg.norm(n)


def _rotate(u, v, w):
    """`w` turned by the minimal rotation taking unit `u` to unit `v` (Rodrigues)."""
    k = np.cross(u, v)
    c = float(np.dot(u, v))
    return w * c + np.cross(k, w) + k * float(np.dot(k, w)) / (1.0 + c)


def frame_excess(frames, reference, radius: float, facings) -> tuple[list[float], list[float]]:
    """Per placement pair / placement: (the normal jump beyond the smooth `reference` surface's own turn between two
    successive placements, the tangent's angle from the stroke's own direction there - the central chord projected
    into the frame's plane) in degrees (module docstring). `facings`: the placements' hit normals."""
    refs = [reference_normal(reference, f.centre, radius, facing) for f, facing in zip(frames, facings)]
    normals = [angle(_rotate(ra, rb, a.n), b.n) for a, b, ra, rb in zip(frames, frames[1:], refs, refs[1:])]
    twists = []
    for k, f in enumerate(frames):
        before = frames[max(k - 1, 0)].centre
        after = frames[min(k + 1, len(frames) - 1)].centre
        path = after - before
        path = path - np.dot(path, f.n) * f.n
        if np.linalg.norm(path) > 0.0:
            twists.append(angle(path, f.t))
    return normals, twists
