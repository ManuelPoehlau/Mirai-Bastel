"""One placement's stamp cluster: the projection of the tip onto the surface (AD-037 §12 Phase 4a; proposal §4.1-§4.4).

`evaluate(surface, placement, radius, settings, definition)` returns `(texels, coverage, unique)` for
`PaintStroke.dab`:

- **Round tip:** exactly the Phase 2 dab (`PaintRoomController._dab` until 4a): the footprint within the world radius on
  triangles facing the hit's way, the falloff, and its mirror across the symmetry plane. Pinned bit for bit
  (`tests/test_paint_alpha.py`).
- **Alpha tip:** per placement a **tangent frame** `(t, b, n)` at the centre `c`:
  1. **gather** the texels within `R = r * reach` (`AlphaImage.reach`: where the alpha paints at all, at most the
     rectangle's corners `r * |half extents|`, so a rotated rectangle is not clipped), on triangles facing the hit's way
     (`surface.FACING_MIN`, as the round tip);
  2. **normal** `n`: the area-weighted mean of the triangle normals inside the **inner disc** (`INNER_DISC` r) - not
     the hit facet's normal (it jumps from facet to facet on the cage and SubD 1) and not the whole stamp's (a stamp
     over the nose ridge would tilt its own frame);
  3. **tangent** `t`: the placement's path direction projected into the plane ⟂ `n` ("Strich folgen", P-21), else the
     view's up (a click without movement); rotated by the brush's angle offset; `b = n × t`;
  4. every texel's local coordinates `a = (p−c)·t / r`, `β = (p−c)·b / r`, `h = (p−c)·n / r`.
  Coverage = `alpha(a, β)` (bilinear on the mip level whose size fits the stamp's diameter in texels) × the **depth
  window** (`|h| ≤ DEPTH_MAX`, soft from `DEPTH_SOFT`: the lower lip under the upper lip, a nostril wing over the
  cheek) × the **facing fade** (`smoothstep(FADE_FROM, FADE_TO, n · n_tri)`: where the planar projection would smear by
  1/cos it fades out instead) × [Kreismaske: the round falloff]. Texels with no coverage are not written.
  The mirror cluster uses the **reflected frame** (the reflection flips its handedness, so an asymmetric alpha appears
  mirrored) at the reflected centre; a texel in both counts once with the larger coverage (as the round tip).
- **Wrap projection** (the §4.3 fallback, built in 4a; from `WRAP_FROM_PERCENT` brush radius on, AD-037 §12.7): where
  the planar projection is *convexly stressed* - more than `WRAP_STRESS` of the rectangle's texels lie below the plane
  beyond the depth window's full part or on triangles the facing fade dims, and no more than `SADDLE` rise above it
  (in a crease or saddle, the mouth corner, a geodesic disc grows beyond π r² and the planar stamp stays closer to the
  ideal) - the local coordinates are **geodesic polar coordinates** instead (a discrete exponential map, [E] Schmidt et al. 2006 "decal" maps, Substance's "Tangent | Wrap"): from the corners of
  the centre's triangle, the shortest edge paths over the triangles within the reach (Bellman-Ford rounds, vectorised
  over the edges) make a tree; each vertex's 2D coordinate is its parent's plus the edge projected into the frame
  turned onto the parent's tangent plane (length kept), summed along the tree by pointer jumping, and every texel
  interpolates its triangle's corners. The stamp then wraps around the curve instead of being cut or smeared; a
  triangle not connected to the centre within the reach gets nothing (no leak). Rounds bounded by the paths' hop count
  and log2 of the tree's depth per placement, vectorised; no loop per texel or vertex. The mirror uses the main stamp's
  projection.

Only arrays over the gathered texels; no loop per texel. A stamp is evaluated on the shown surface's own texel points,
so cage, SubD, a morph mix and a pose all work alike.

**Phase 4b** (AD-037 §13): `paint(stroke, ...)` is what the room does with a placement. A brush without randomness
(`StrokeDynamics.random` False) goes through `evaluate` and `PaintStroke.dab` exactly as in 4a (pinned bit for bit
against a frozen copy, `tests/test_paint_dynamics.py`); the orientation modes Ansicht / Fläche only choose another
tangent (`orientation_tangent`). With randomness, `cluster` evaluates the placement's stamps from the stroke's seed
(`dynamics.random_values`, counter-based) and writes them in **one** `PaintStroke.dab_product`:

- **scatter** moves the placement along / across the stroke line (in its tangent plane, at most `SCATTER_MAX` radii)
  and puts it back on the surface with a ray along the hit normal (`_scattered`); off the object nothing is painted;
- **single:** one stamp, jittered in rotation, size and flow - the alpha tip through `alpha_stamp` (its frame, mip,
  depth window, fade and projection choice as in 4a), the round tip through the footprint and falloff;
- **spray:** `spray_density` stamps inside the brush disc (`dynamics.spray_positions`), each `spray_size` radii (times
  its size jitter), rotated by the angle offset plus its jitter, at `flow * spray_intensity * flow jitter`. **One**
  gather for the whole cluster, one frame (as `alpha_stamp`'s), the depth window and facing fade once per texel; the
  stamps' bounding squares as one (stamps x texels) mask (K <= `SPRAY_MAX`), the alpha (or the round falloff) read only
  on the selected (stamp, texel) pairs - one read per mip level -, multiplied into the cluster's `prod(1 - flow_k * c_k)`
  in stamp order (`np.multiply.at`). No loop per texel, and none per stamp either.
  The stamps lie in the placement's tangent plane (the proposal's planar approximation; no wrap for spray stamps).
- **mirror:** the reflected cluster uses the **same** random values in the reflected frame (its handedness flipped): a
  scattered stamp lands at the mirrored place, an asymmetric alpha appears mirrored. A texel in both keeps the smaller
  product (the larger coverage), as the 4a dab merges its mirror.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import alpha as alpha_api
from .brush import BrushSettings, falloff
from . import dynamics as dynamics_api
from .dynamics import Placement
from .surface import FACING_MIN, PaintSurface, mirror

#: The inner disc of the frame normal, in radii (`PROVISIONAL`, proposal §4.1).
INNER_DISC = 0.5
#: The depth window in radii: full up to `DEPTH_SOFT`, 0 from `DEPTH_MAX` (`PROVISIONAL`, §4.2).
DEPTH_MAX = 0.5
DEPTH_SOFT = 0.35
#: The facing fade: `smoothstep(FADE_FROM, FADE_TO, n · n_tri)` (`PROVISIONAL`, §4.2).
FADE_FROM, FADE_TO = 0.2, 0.5
#: The planar projection is stressed - the wrap projection takes over - when more than this fraction of the stamp's
#: texels lie *below* the plane beyond `DEPTH_SOFT` or on triangles with `n · n_tri < FADE_TO` (convex: the surface
#: falls away; `PROVISIONAL`, tuned on §4.3's probes).
WRAP_STRESS = 0.08
#: The wrap is considered from this brush radius (P-7 percent of the object's bounding radius) on (`PROVISIONAL`,
#: measured on the Gollum head, AD-037 §12.7): at 3 % the planar stamp meets every §4.3 gate and paints through nothing,
#: and where both reach their limit (the nostril wing, curved as tightly as the stamp) the wrap is no rounder; from 4 %
#: the planar stamp reaches the lower lip (88 texels at 4 %, 435 at 5 % on the cage) and smears the wing, nose tip and
#: lid, which the wrap fixes. Below it a placement costs what a planar stamp costs (the 3 % reference-PC gate).
WRAP_FROM_PERCENT = 4.0
#: Below this stress within the alpha's own reach a placement stays planar without looking further (`PROVISIONAL`):
#: the wrap decision's larger gather is paid only where the surface bends at all.
PRECHECK = 0.02
#: The wrap's triangles reach this much beyond the gathered texels (paths may bend out of the gather's sphere;
#: `PROVISIONAL`).
WRAP_MARGIN = 1.1
#: ... unless more than this fraction rises *above* the plane beyond `DEPTH_SOFT` too: a crease or saddle (the mouth
#: corner), where a geodesic disc grows beyond π r² and the planar stamp stays closer to the ideal (`PROVISIONAL`).
SADDLE = 0.04
#: Iteration bound of the wrap's shortest-path rounds and pointer jumping (a stamp spans far fewer edge hops).
WRAP_ITERATIONS = 64
PLANAR, WRAP = "planar", "wrap"

__all__ = ["PLANAR", "WRAP", "WRAP_FROM_PERCENT", "Frame", "Placement", "SprayStamp", "Stamp", "alpha_stamp", "cluster",
           "combine", "evaluate", "frame_tangent", "orientation_tangent", "paint", "projection_for", "reflect",
           "surface_tangent"]


@dataclass(frozen=True, eq=False)
class Frame:
    centre: np.ndarray
    t: np.ndarray
    b: np.ndarray
    n: np.ndarray


@dataclass(frozen=True, eq=False)
class Stamp:
    """One alpha stamp's result: texels with coverage > 0, the frame, the mip level, and the diameter in texels."""

    texels: np.ndarray
    coverage: np.ndarray
    frame: Frame | None
    level: int = 0
    diameter: float = 0.0
    projection: str = PLANAR
    stress: float = 0.0  # the stress the projection was chosen by (0 where none was chosen)


_EMPTY = (np.zeros(0, np.int64), np.zeros(0, np.float32))


def _smoothstep(lo: float, hi: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - np.float32(lo)) / np.float32(hi - lo), 0.0, 1.0)
    return t * t * (np.float32(3.0) - np.float32(2.0) * t)


def reflect(definition, vector) -> np.ndarray:
    """A direction reflected across the symmetry plane of `definition`."""
    n = np.asarray(definition.plane_normal, dtype=np.float64)
    v = np.asarray(vector, dtype=np.float64)
    return v - 2.0 * np.dot(v, n) * n


def frame_tangent(n: np.ndarray, tangent, fallback) -> np.ndarray:
    """`tangent` projected into the plane ⟂ `n` (unit); `fallback` when it is None or parallel to `n`; any
    perpendicular as the last resort."""
    for candidate in (tangent, fallback, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
        if candidate is None:
            continue
        v = np.asarray(candidate, dtype=np.float64)
        v = v - np.dot(v, n) * n
        length = float(np.linalg.norm(v))
        if length > 1e-6:
            return v / length
    raise AssertionError("unreachable: two axes cannot both be parallel to n")


def alpha_stamp(surface: PaintSurface, centre, facing, radius: float, image: alpha_api.AlphaImage, *, tangent=None,
                view_up=None, angle: float = 0.0, settings: BrushSettings | None = None,
                frame: Frame | None = None, projection: str | None = None) -> Stamp:
    """One alpha stamp at `centre` (module docstring). `frame` given (the mirror): it is used as it is, `tangent`,
    `view_up` and `angle` are not read. `projection` None chooses planar or wrap by the stress; given, it is used."""
    hw, hh = image.half_extents
    r = float(radius)
    corners = math.hypot(hw, hh)  # the rectangle's corners: the stress statistic's and the wrap region's extent
    # painted only where the alpha paints (its `reach`; the Kreismaske ends at the radius), the inner disc at least
    extent = min(image.reach, corners)
    if settings is not None and settings.tip.kreismaske:
        extent = min(extent, 1.0)
    extent = max(extent, INNER_DISC)
    gathered = surface.gather(centre, r * extent, facing)
    if gathered is None:
        return Stamp(*_EMPTY, frame)
    d2 = gathered.d2 * np.float32(extent * extent)  # (d / r)²
    if frame is None:
        frame = _frame(surface, gathered, d2, centre, facing, tangent, view_up, angle)
    local = _Local(surface, gathered, frame, r, hw, hh)
    stress = 0.0
    if projection is None:
        stress, rising = local.stats()
        if stress > PRECHECK and extent < corners:
            # the decision as over the whole rectangle (`WRAP_STRESS` is tuned on it); only for a stamp that shows
            # stress at all within its reach - a flat placement does not pay for the larger gather
            whole = surface.gather(centre, r * corners, facing)
            if whole is not None:
                stress, rising = _Local(surface, whole, frame, r, hw, hh).stats()
        projection = WRAP if stress > WRAP_STRESS and rising <= SADDLE else PLANAR
    within = min(extent, 1.0)  # the stamp's diameter in texels from the disc the gather holds whole
    diameter = 2.0 * math.sqrt(float(np.count_nonzero(d2 < np.float32(within * within))) / math.pi) / within
    level = image.level_for(diameter)
    if projection == WRAP:
        uv = _wrap(surface, centre, facing, r * min(corners, extent * WRAP_MARGIN), frame, gathered)
        if uv is not None:
            a = uv[:, 0] / np.float32(r)
            beta = uv[:, 1] / np.float32(r)
            keep = np.flatnonzero(np.isfinite(a) & (np.abs(a) < np.float32(hw)) & (np.abs(beta) < np.float32(hh)))
            if keep.size == 0:
                return Stamp(*_EMPTY, frame, level, diameter, WRAP, stress)
            coverage = image.sample_local(level, a[keep], beta[keep])
            return _finish(gathered, keep, coverage, d2, settings, frame, level, diameter, WRAP, stress)
    keep = np.flatnonzero(local.in_rect & (local.h < np.float32(DEPTH_MAX)))
    if keep.size == 0:
        return Stamp(*_EMPTY, frame, level, diameter, PLANAR, stress)
    coverage = image.sample_local(level, local.a[keep], local.beta[keep])
    h = local.h[keep]
    if float(h.max()) > DEPTH_SOFT:  # (most stamps lie inside the window's full part: no work for it)
        coverage *= np.float32(1.0) - _smoothstep(DEPTH_SOFT, DEPTH_MAX, h)
    facing_n = local.facing(keep)
    if float(facing_n.min()) < FADE_TO:
        coverage *= _smoothstep(FADE_FROM, FADE_TO, facing_n)
    return _finish(gathered, keep, coverage, d2, settings, frame, level, diameter, PLANAR, stress)


def _frame(surface, gathered, d2, centre, facing, tangent, view_up, angle) -> Frame:
    """The placement's frame (module docstring): the inner disc's area-weighted normal, the tangent, the angle."""
    inner = d2 < np.float32(INNER_DISC * INNER_DISC)
    n = None
    if inner.any():
        s = gathered.slots[inner]
        n = (surface._tri_normal[s] * surface._texel_area[s][:, None]).sum(axis=0)
        length = float(np.linalg.norm(n))
        n = n / length if length > 1e-300 else None
    if n is None:
        n = np.asarray(facing, dtype=np.float64)
        n = n / max(float(np.linalg.norm(n)), 1e-300)
    t = frame_tangent(n, tangent, view_up)
    if angle:
        b0 = _cross3(n, t)
        th = math.radians(angle)
        t = math.cos(th) * t + math.sin(th) * b0
    return Frame(np.asarray(centre, dtype=np.float64), t, _cross3(n, t), n)


class _Local:
    """The gathered texels in a frame: `a`, `beta`, `h` (|height|), inside the rectangle; `facing(keep)` the facing
    `n · n_tri`; `stats()` the stress statistics of the projection choice (module docstring) - only where a choice is
    made (a planar-only brush does not pay for them)."""

    def __init__(self, surface, gathered, frame: Frame, r: float, hw: float, hh: float) -> None:
        self._surface, self._gathered, self._frame = surface, gathered, frame
        basis = np.stack((frame.t, frame.b, frame.n), axis=1).astype(np.float32) / np.float32(r)
        local = gathered.rel @ basis
        self.a, self.beta, self._height = local[:, 0], local[:, 1], local[:, 2]
        self.h = np.abs(self._height)
        self.in_rect = (np.abs(self.a) < np.float32(hw)) & (np.abs(self.beta) < np.float32(hh))

    def facing(self, keep=None) -> np.ndarray:
        slots = self._gathered.slots if keep is None else self._gathered.slots[keep]
        return self._surface._tri_normal32[slots] @ self._frame.n.astype(np.float32)

    def stats(self) -> tuple[float, float]:
        """(stress, rising) over the texels inside the rectangle."""
        in_rect = self.in_rect
        count = int(np.count_nonzero(in_rect))
        if not count:
            return 0.0, 0.0
        below = self._height < 0.0
        deep = self.h > np.float32(DEPTH_SOFT)
        # convex stress only: the surface falling away below the plane (a bulb, the wing, a lip over the other); in a
        # concave crease (the mouth corner) the planar stamp stays closer to the ideal than a geodesic one
        stressed = in_rect & below & (deep | (self.facing() < np.float32(FADE_TO)))
        return (float(np.count_nonzero(stressed)) / count,
                float(np.count_nonzero(in_rect & ~below & deep)) / count)


def _finish(gathered, keep, coverage, d2, settings, frame, level, diameter, projection, stress) -> Stamp:
    if settings is not None and settings.tip.kreismaske:
        coverage = coverage * falloff(np.sqrt(d2[keep]), settings.hardness, settings.curve).astype(np.float32)
    painted = np.flatnonzero(coverage > 0.0)
    return Stamp(gathered.texels[keep[painted]], coverage[painted].astype(np.float32), frame, level, diameter,
                 projection, stress)


def _wrap(surface: PaintSurface, centre, facing, reach: float, frame: Frame, gathered) -> np.ndarray | None:
    """Geodesic polar coordinates (world units, (n, 2) float32; inf where unreachable) of the gathered texels around
    `centre` in `frame` (module docstring: the wrap projection); None when the centre's triangle is not found."""
    c = np.asarray(centre, dtype=np.float64)
    slots = surface._slot_clusters.box(c - reach, c + reach)
    near = np.all(surface._lo[slots] <= c + reach, axis=1) & np.all(surface._hi[slots] >= c - reach, axis=1)
    near &= surface._live[slots] & ~surface._slot_hidden[slots]
    if facing is not None:
        near &= surface._tri_normal[slots] @ np.asarray(facing, dtype=np.float64) > FACING_MIN
    slots = np.sort(slots[near])
    if slots.size == 0:
        return None
    vertices, inverse = np.unique(surface._tri_rows[slots], return_inverse=True)
    tri = inverse.reshape(-1, 3)
    x = surface._p[vertices]
    # vertex normals of the local, facing triangles (area-weighted): the tangent planes the frame is turned onto - not
    # the whole mesh's (a nostril wing's would lean towards the nostril's underside: aspect 1.40 instead of 1.29)
    cross = _cross_rows(x[tri[:, 1]] - x[tri[:, 0]], x[tri[:, 2]] - x[tri[:, 0]])
    vn = np.zeros_like(x)
    for k in range(3):
        np.add.at(vn, tri[:, k], cross)
    vn /= np.maximum(np.linalg.norm(vn, axis=1), 1e-300)[:, None]
    src = tri[:, (0, 1, 2, 1, 2, 0)].T.reshape(-1)
    dst = tri[:, (1, 2, 0, 0, 1, 2)].T.reshape(-1)
    length = np.linalg.norm(x[dst] - x[src], axis=1)
    # the seed: the corners of the triangle of the gathered texel nearest to the centre, planar around the centre
    nearest = int(np.argmin(np.einsum("ij,ij->i", gathered.rel, gathered.rel)))
    at = np.searchsorted(slots, gathered.slots[nearest])
    if at >= slots.size or slots[at] != gathered.slots[nearest]:
        return None
    t, b, n = frame.t, frame.b, frame.n
    hand = 1.0 if float(np.dot(_cross3(n, t), b)) >= 0.0 else -1.0  # a mirrored frame keeps its handedness
    # the tree: shortest edge paths from the seeds (Bellman-Ford rounds, each vectorised over the edges; the rounds are
    # the paths' hop count), then each vertex's parent is its neighbour on its shortest path
    seeds = tri[at]
    is_seed = np.zeros(vertices.size, dtype=bool)
    is_seed[seeds] = True
    dist = np.full(vertices.size, np.inf)
    dist[seeds] = np.linalg.norm(x[seeds] - c, axis=1)
    for _ in range(WRAP_ITERATIONS):
        relaxed = dist.copy()
        np.minimum.at(relaxed, dst, dist[src] + length)
        if np.array_equal(relaxed, dist):
            break
        dist = relaxed
    tight = np.isfinite(dist[src]) & ~is_seed[dst]
    cost = dist[src[tight]] + length[tight]
    order = np.lexsort((cost, dst[tight]))
    to, via = dst[tight][order], src[tight][order]
    first = np.r_[True, to[1:] != to[:-1]] if to.size else np.zeros(0, dtype=bool)
    parent = np.full(vertices.size, -1, dtype=np.int64)
    parent[to[first]] = via[first]
    # each vertex's step from its parent in the frame turned onto the parent's tangent plane; the seeds around the centre
    acc = np.zeros((vertices.size, 2))
    acc[seeds] = _kept_length(x[seeds] - c, t, b)
    has = np.flatnonzero(parent >= 0)
    p = parent[has]
    npn = vn[p]  # the root frame projected onto the parent's tangent plane (its handedness kept)
    tp = t[None, :] - (npn @ t)[:, None] * npn
    tp /= np.maximum(np.linalg.norm(tp, axis=1), 1e-300)[:, None]
    bp = hand * _cross_rows(npn, tp)
    acc[has] = _kept_length(x[has] - x[p], tp, bp)
    # the coordinates are the steps summed along the tree (pointer jumping: log2 of the depth rounds)
    up = parent.copy()
    root = np.arange(vertices.size)
    for _ in range(WRAP_ITERATIONS):
        going = up >= 0
        if not going.any():
            break
        ancestor = np.where(going, up, 0)
        acc = acc + np.where(going[:, None], acc[ancestor], 0.0)
        root = np.where(going, root[ancestor], root)
        up = np.where(going, up[ancestor], -1)
    uv = np.where(is_seed[root][:, None], acc, np.inf)
    # every gathered texel: its triangle's corners interpolated
    corner = tri[np.searchsorted(slots, gathered.slots)]
    w = surface.map.bary[gathered.texels]
    w0 = (1.0 - w[:, 0] - w[:, 1]).astype(np.float64)
    with np.errstate(invalid="ignore"):
        out = uv[corner[:, 0]] * w0[:, None] + uv[corner[:, 1]] * w[:, 0:1] + uv[corner[:, 2]] * w[:, 1:2]
    return out.astype(np.float32)


def _cross3(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """`u × v` of two 3-vectors (`np.cross` costs ~20 µs of overhead per call; a placement makes several)."""
    return np.array((u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]))


def _cross_rows(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Row-wise `u × v` of two (k, 3) arrays."""
    out = np.empty_like(u)
    out[:, 0] = u[:, 1] * v[:, 2] - u[:, 2] * v[:, 1]
    out[:, 1] = u[:, 2] * v[:, 0] - u[:, 0] * v[:, 2]
    out[:, 2] = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
    return out


def _kept_length(e: np.ndarray, t: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Edges `e` (n, 3) projected onto the plane of `t`, `b` ((3,) or (n, 3)) and scaled back to their own length."""
    if t.ndim == 1:
        proj = np.stack((e @ t, e @ b), axis=1)
    else:
        proj = np.stack((np.einsum("ij,ij->i", e, t), np.einsum("ij,ij->i", e, b)), axis=1)
    full = np.linalg.norm(e, axis=1)
    flat = np.linalg.norm(proj, axis=1)
    return proj * np.where(flat > 1e-300, full / np.maximum(flat, 1e-300), 0.0)[:, None]


def projection_for(radius_percent: float) -> str | None:
    """The projection a brush of this radius (P-7 percent) may use: below `WRAP_FROM_PERCENT` always planar, from it
    chosen per placement (None)."""
    return None if radius_percent >= WRAP_FROM_PERCENT - 1e-9 else PLANAR


def evaluate(surface: PaintSurface, placement: Placement, radius: float, settings: BrushSettings, definition=None,
             *, view_up=None, image: alpha_api.AlphaImage | None = None, stamps: list | None = None):
    """`(texels, coverage, unique)` of one placement and its mirror (`definition`: the symmetry plane, None = no
    mirror) for `PaintStroke.dab` (module docstring). `image` overrides the tip's alpha; `stamps` (a list) receives the
    alpha stamps evaluated (tests, the probe)."""
    if image is None:
        image = alpha_api.resolve(settings.tip.alpha)
    if image is None:  # the round tip: the Phase 2 dab, operation for operation
        texels, x = surface.footprint(placement.point, radius, placement.normal)
        parts_t, parts_c = [texels], [falloff(x, settings.hardness, settings.curve)]
        if definition is not None:
            point, normal = mirror(definition, placement.point, placement.normal)
            texels, x = surface.footprint(point, radius, normal)
            parts_t.append(texels)
            parts_c.append(falloff(x, settings.hardness, settings.curve))
        return np.concatenate(parts_t), np.concatenate(parts_c), len(parts_t) == 1
    angle = settings.dynamics.angle
    tangent = orientation_tangent(surface, placement, settings.dynamics.orientation, radius, view_up)
    main = alpha_stamp(surface, placement.point, placement.normal, radius, image, tangent=tangent,
                       view_up=view_up, angle=angle, settings=settings,
                       projection=projection_for(settings.radius_percent))
    parts = [main]
    if definition is not None and main.frame is not None:
        point, normal = mirror(definition, placement.point, placement.normal)
        f = main.frame
        reflected = Frame(np.asarray(point), reflect(definition, f.t), reflect(definition, f.b), reflect(definition, f.n))
        parts.append(alpha_stamp(surface, point, normal, radius, image, settings=settings, frame=reflected,
                                 projection=main.projection))
    if stamps is not None:
        stamps.extend(parts)
    texels = np.concatenate([p.texels for p in parts])
    coverage = np.concatenate([p.coverage for p in parts])
    return texels, coverage, len(parts) == 1


def combine(texels: list[np.ndarray], coverages: list[np.ndarray], flows) -> tuple[np.ndarray, np.ndarray]:
    """K stamps of one cluster as `(unique texels, prod(1 - flow_k * c_k))` for `PaintStroke.dab_product` (proposal
    §5.6; a loop over stamps, never over texels)."""
    if not texels:
        return _EMPTY
    all_t = np.concatenate([np.asarray(t, dtype=np.int64) for t in texels])
    factors = np.concatenate([np.float32(1.0) - np.float32(f) * np.asarray(c, dtype=np.float32)
                              for c, f in zip(coverages, flows)])
    if all_t.size == 0:
        return _EMPTY
    unique, inverse = np.unique(all_t, return_inverse=True)
    product = np.ones(unique.size, dtype=np.float32)
    np.multiply.at(product, inverse, factors)
    return unique, product


# -- Phase 4b: orientation, jitter, scatter, spray ---------------------------------------------------------------------


def surface_tangent(surface: PaintSurface, point, facing, radius: float) -> np.ndarray | None:
    """The UV-u tangent `∂p/∂u` (unit, world) of the triangle under `point` (the nearest texel's within a quarter
    radius), None where there is none or the triangle's UVs are degenerate (orientation "Fläche", proposal §5.3)."""
    gathered = surface.gather(point, 0.25 * radius, facing)
    if gathered is None:
        return None
    slot = int(gathered.slots[int(np.argmin(gathered.d2))])
    p = surface._p[surface._tri_rows[slot]]
    uv = surface.map.tri_uvs[slot]
    e1, e2 = p[1] - p[0], p[2] - p[0]
    (du1, dv1), (du2, dv2) = uv[1] - uv[0], uv[2] - uv[0]
    det = du1 * dv2 - du2 * dv1
    if abs(det) < 1e-18:
        return None
    t = (e1 * dv2 - e2 * dv1) / det
    length = float(np.linalg.norm(t))
    return t / length if length > 1e-300 else None


def orientation_tangent(surface: PaintSurface, placement: Placement, orientation: str, radius: float, view_up):
    """The stamp's "up" before the angle offset (proposal §5.3): the path's direction ("stroke", 4a), the view's up
    ("view", and the base of "random", whose turn is a random value), the UV-u tangent ("surface"). None falls back to
    the view's up in the frame."""
    if orientation == "stroke":
        return placement.tangent
    if orientation == "surface":
        return surface_tangent(surface, placement.point, placement.normal, radius)
    return view_up


@dataclass(frozen=True, eq=False)
class SprayStamp:
    """One stamp of a randomised cluster (tests, the probe): its world centre, its frame's `t` (turned by its angle),
    its radius, its flow and whether it is the mirror's."""

    centre: np.ndarray
    t: np.ndarray
    radius: float
    flow: float
    mirrored: bool = False


def _scattered(surface: PaintSurface, placement: Placement, radius: float, offset, view_up):
    """The placement moved by `offset` (along, across) radii in its tangent plane (along = the path's direction, else
    the view's up) and put back on the surface: the hit of a ray along `-normal` from one radius above. None when it
    leaves the object, faces away, or lands farther than the offset allows (another sheet)."""
    along, across = offset
    n = np.asarray(placement.normal, dtype=np.float64)
    n = n / max(float(np.linalg.norm(n)), 1e-300)
    t = frame_tangent(n, placement.tangent, view_up)
    b = _cross3(n, t)
    target = np.asarray(placement.point, dtype=np.float64) + radius * (along * t + across * b)
    hit = surface.hit(target + radius * n, -n)
    if hit is None or float(np.dot(hit.normal, n)) <= FACING_MIN:
        return None
    if float(np.linalg.norm(np.asarray(hit.point) - target)) > radius * dynamics_api.SCATTER_MAX:
        return None
    return Placement(placement.index, np.asarray(hit.point, dtype=np.float64), np.asarray(hit.normal, dtype=np.float64),
                     placement.tangent)


def _merge_min(texels: np.ndarray, product: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Duplicate texels (a cluster and its mirror at the plane) merged to their smallest product (largest coverage)."""
    order = np.lexsort((product, texels))
    texels, product = texels[order], product[order]
    keep = np.r_[True, texels[1:] != texels[:-1]] if texels.size else np.zeros(0, dtype=bool)
    return texels[keep], product[keep]


def cluster(surface: PaintSurface, placement: Placement, radius: float, settings: BrushSettings, definition=None, *,
            view_up=None, image: alpha_api.AlphaImage | None = None, seed: int = 0,
            stamps: list | None = None) -> tuple[np.ndarray, np.ndarray]:
    """`(unique texels, prod(1 - flow_k * c_k))` of one randomised placement and its mirror for
    `PaintStroke.dab_product` (module docstring, Phase 4b). `stamps` (a list) receives a `SprayStamp` per stamp."""
    dyn = settings.dynamics
    k = dyn.spray_density if dyn.spray else 1
    values = dynamics_api.random_values(seed, placement.index, [*range(k), dynamics_api.PLACEMENT_ROW])
    if dyn.scattered:
        placement = _scattered(surface, placement, radius, dynamics_api.scatter_offset(dyn, values[k]), view_up)
        if placement is None:
            return _EMPTY
    angles, sizes, flows = dynamics_api.stamp_jitter(dyn, values[:k])
    angles = angles + dyn.angle
    flows = np.minimum(settings.flow * flows * (dyn.spray_intensity if dyn.spray else 1.0), 1.0)
    if dyn.spray:
        parts = _spray(surface, placement, radius, settings, definition, view_up, image, values[:k], angles, sizes,
                       flows, stamps)
    else:
        parts = _single(surface, placement, radius, settings, definition, view_up, image, float(angles[0]),
                        float(sizes[0]), float(flows[0]), stamps)
    parts = [p for p in parts if p[0].size]
    if not parts:
        return _EMPTY
    if len(parts) == 1:
        return parts[0]
    return _merge_min(np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts]))


def _single(surface, placement, radius, settings, definition, view_up, image, angle, size, flow, stamps):
    """One jittered stamp (and its mirror) as `[(texels, 1 - flow * c)]` parts."""
    r = radius * size
    f = np.float32(flow)
    if image is None:  # the round tip: the footprint and falloff at the jittered size (rotation does not show)
        texels, x = surface.footprint(placement.point, r, placement.normal)
        parts = [(texels, np.float32(1.0) - f * falloff(x, settings.hardness, settings.curve).astype(np.float32))]
        if stamps is not None:
            stamps.append(SprayStamp(np.asarray(placement.point), np.zeros(3), r, flow))
        if definition is not None:
            point, normal = mirror(definition, placement.point, placement.normal)
            texels, x = surface.footprint(point, r, normal)
            parts.append((texels, np.float32(1.0) - f * falloff(x, settings.hardness, settings.curve).astype(np.float32)))
            if stamps is not None:
                stamps.append(SprayStamp(point, np.zeros(3), r, flow, True))
        return parts
    tangent = orientation_tangent(surface, placement, settings.dynamics.orientation, radius, view_up)
    main = alpha_stamp(surface, placement.point, placement.normal, r, image, tangent=tangent, view_up=view_up,
                       angle=angle, settings=settings, projection=projection_for(settings.radius_percent * size))
    parts = [(main.texels, np.float32(1.0) - f * main.coverage)]
    if stamps is not None and main.frame is not None:
        stamps.append(SprayStamp(main.frame.centre, main.frame.t, r, flow))
    if definition is not None and main.frame is not None:
        point, normal = mirror(definition, placement.point, placement.normal)
        fr = main.frame
        reflected = Frame(np.asarray(point), reflect(definition, fr.t), reflect(definition, fr.b), reflect(definition, fr.n))
        other = alpha_stamp(surface, point, normal, r, image, settings=settings, frame=reflected,
                            projection=main.projection)
        parts.append((other.texels, np.float32(1.0) - f * other.coverage))
        if stamps is not None:
            stamps.append(SprayStamp(reflected.centre, reflected.t, r, flow, True))
    return parts


def _spray(surface, placement, radius, settings, definition, view_up, image, values, angles, sizes, flows, stamps):
    """The spray cluster (module docstring) and its mirror as `[(texels, product)]` parts."""
    dyn = settings.dynamics
    positions = dynamics_api.spray_positions(dyn, values)
    scales = dyn.spray_size * sizes  # each stamp's radius in brush radii
    if image is None:
        reach = 1.0
    else:
        reach = image.reach
        if settings.tip.kreismaske:
            reach = min(reach, 1.0)
    extent = max(float((np.hypot(positions[:, 0], positions[:, 1]) + scales * reach).max()), INNER_DISC)
    tangent = orientation_tangent(surface, placement, dyn.orientation, radius, view_up)
    main = _spray_cluster(surface, placement.point, placement.normal, radius, extent, settings, image, positions,
                          scales, reach, angles, flows, tangent=tangent, view_up=view_up)
    if main is None:
        return []
    texels, product, frame = main
    parts = [(texels, product)]
    if stamps is not None:
        stamps.extend(_spray_records(frame, radius, positions, scales, angles, flows, False))
    if definition is not None:
        point, normal = mirror(definition, placement.point, placement.normal)
        reflected = Frame(np.asarray(point), reflect(definition, frame.t), reflect(definition, frame.b),
                          reflect(definition, frame.n))
        other = _spray_cluster(surface, point, normal, radius, extent, settings, image, positions, scales, reach, angles,
                               flows, frame=reflected)
        if other is not None:
            parts.append(other[:2])
            if stamps is not None:
                stamps.extend(_spray_records(reflected, radius, positions, scales, angles, flows, True))
    return parts


def _spray_records(frame: Frame, radius, positions, scales, angles, flows, mirrored) -> list:
    records = []
    for (x, y), s, a, f in zip(positions, scales, angles, flows):
        th = math.radians(float(a))
        records.append(SprayStamp(frame.centre + radius * (x * frame.t + y * frame.b),
                                  math.cos(th) * frame.t + math.sin(th) * frame.b, radius * float(s), float(f),
                                  mirrored))
    return records


def _spray_cluster(surface, centre, facing, radius, extent, settings, image, positions, scales, reach, angles, flows, *,
                   tangent=None, view_up=None, frame: Frame | None = None):
    """One gather around `centre`, the frame (given: the mirror's), then per stamp its mask and coverage multiplied into
    the cluster's product. Returns (texels, product, frame) or None."""
    r = float(radius)
    gathered = surface.gather(centre, r * extent, facing)
    if gathered is None:
        return None
    d2 = gathered.d2 * np.float32(extent * extent)  # (d / r)²
    if frame is None:
        frame = _frame(surface, gathered, d2, centre, facing, tangent, view_up, 0.0)
    basis = np.stack((frame.t, frame.b, frame.n), axis=1).astype(np.float32) / np.float32(r)
    local = gathered.rel @ basis
    a, beta, h = local[:, 0], local[:, 1], np.abs(local[:, 2])
    # the depth window and the facing fade once per texel of the cluster (its plane)
    window = np.ones(a.size, dtype=np.float32)
    if float(h.max()) > DEPTH_SOFT:
        window = np.float32(1.0) - _smoothstep(DEPTH_SOFT, DEPTH_MAX, h)
    facing_n = surface._tri_normal32[gathered.slots] @ frame.n.astype(np.float32)
    if float(facing_n.min()) < FADE_TO:
        window = window * _smoothstep(FADE_FROM, FADE_TO, facing_n)
    # the brush disc's diameter in texels (the mip level of each stamp follows its share of it)
    within = min(extent, 1.0)
    disc = 2.0 * math.sqrt(float(np.count_nonzero(d2 < np.float32(within * within))) / math.pi) / within
    # every stamp's bounding square at once (stamps x texels; K <= `SPRAY_MAX`): the (stamp, texel) pairs it holds
    x = positions[:, 0].astype(np.float32)[:, None]
    y = positions[:, 1].astype(np.float32)[:, None]
    e = (scales * reach).astype(np.float32)[:, None]
    dx = a[None, :] - x
    dy = beta[None, :] - y
    k, sel = np.nonzero((np.abs(dx) < e) & (np.abs(dy) < e))
    product = np.ones(a.size, dtype=np.float32)
    if k.size == 0:
        return gathered.texels[:0], product[:0], frame
    dx, dy = dx[k, sel], dy[k, sel]
    th = np.radians(np.asarray(angles, dtype=np.float64))
    cos, sin = np.cos(th).astype(np.float32)[k], np.sin(th).astype(np.float32)[k]
    inv = (1.0 / scales).astype(np.float32)[k]
    u = (dx * cos + dy * sin) * inv  # the texel in the stamp's own frame (turned by its angle), in stamp radii
    v = (dy * cos - dx * sin) * inv
    if image is None:
        coverage = falloff(np.sqrt(u * u + v * v), settings.hardness, settings.curve).astype(np.float32)
    else:
        hw, hh = image.half_extents
        inside = np.flatnonzero((np.abs(u) < np.float32(hw)) & (np.abs(v) < np.float32(hh)))
        k, sel, u, v = k[inside], sel[inside], u[inside], v[inside]
        coverage = np.empty(k.size, dtype=np.float32)
        # each stamp's mip level from its share of the disc's diameter in texels; one read per level
        levels = np.array([image.level_for(disc * float(s)) for s in scales], dtype=np.int64)[k]
        used = np.unique(levels)
        for level in used:
            at = slice(None) if used.size == 1 else np.flatnonzero(levels == level)
            coverage[at] = image.sample_local(int(level), u[at], v[at])
        if settings.tip.kreismaske:
            coverage *= falloff(np.sqrt(u * u + v * v), settings.hardness, settings.curve).astype(np.float32)
    flows = np.asarray(flows, dtype=np.float32)
    np.multiply.at(product, sel, np.float32(1.0) - flows[k] * coverage * window[sel])
    painted = np.flatnonzero(product < np.float32(1.0))
    return gathered.texels[painted], product[painted], frame


def paint(stroke, surface: PaintSurface, placement: Placement, radius: float, settings: BrushSettings, definition=None,
          *, view_up=None, image: alpha_api.AlphaImage | None = None, seed: int = 0, stamps: list | None = None) -> int:
    """One placement into `stroke` (a `PaintStroke`; module docstring, Phase 4b): without randomness exactly 4a's
    `evaluate` + `dab`, else `cluster` + one `dab_product`. Returns the texels written."""
    if image is None:
        image = alpha_api.resolve(settings.tip.alpha)
    if not settings.dynamics.random:
        texels, coverage, unique = evaluate(surface, placement, radius, settings, definition, view_up=view_up,
                                            image=image, stamps=stamps)
        return stroke.dab(texels, coverage, unique=unique)
    texels, product = cluster(surface, placement, radius, settings, definition, view_up=view_up, image=image, seed=seed,
                              stamps=stamps)
    return stroke.dab_product(texels, product)
