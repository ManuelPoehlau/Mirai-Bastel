"""One placement's stamp cluster: the projection of the tip onto the surface (AD-037 §12 Phase 4a; proposal §4.1-§4.4).

`evaluate(surface, placement, radius, settings, definition)` returns `(texels, coverage, unique)` for
`PaintStroke.dab`:

- **Round tip:** exactly the Phase 2 dab (`PaintRoomController._dab` until 4a): the footprint within the world radius on
  triangles facing the hit's way, the falloff, and its mirror across the symmetry plane. Pinned bit for bit
  (`tests/test_paint_alpha.py`).
- **Alpha tip:** per placement a **tangent frame** `(t, b, n)` at the centre `c`:
  1. **gather** the texels within `R = r * |half extents|` (a rotated rectangle's corners are not clipped), on triangles
     facing the hit's way (`surface.FACING_MIN`, as the round tip);
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
- **Wrap projection** (the §4.3 fallback, built in 4a because the nostril wing failed the stretch gate): where the
  planar projection is *convexly stressed* - more than `WRAP_STRESS` of the stamp's texels lie below the plane beyond
  the depth window's full part or on triangles the facing fade dims, and no more than `SADDLE` rise above it (in a
  crease or saddle, the mouth corner, a geodesic disc grows beyond π r² and the planar stamp stays closer to the
  ideal) - the local coordinates are **geodesic polar coordinates** instead (a
  discrete exponential map, [E] Schmidt et al. 2006 "decal" maps, Substance's "Tangent | Wrap"): from the corners of
  the centre's triangle, the shortest edge paths over the triangles within the reach (Bellman-Ford rounds, vectorised
  over the edges) make a tree; each vertex's 2D coordinate is its parent's plus the edge projected into the frame
  turned onto the parent's tangent plane (length kept), summed along the tree by pointer jumping, and every texel
  interpolates its triangle's corners. The stamp then wraps around the curve instead of being cut or smeared; a
  triangle not connected to the centre within the reach gets nothing (no leak). Rounds bounded by the paths' hop count
  and log2 of the tree's depth per placement, vectorised; no loop per texel or vertex. The mirror uses the main stamp's
  projection.

Only arrays over the gathered texels; no loop per texel. A stamp is evaluated on the shown surface's own texel points,
so cage, SubD, a morph mix and a pose all work alike.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import alpha as alpha_api
from .brush import BrushSettings, falloff
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
#: ... unless more than this fraction rises *above* the plane beyond `DEPTH_SOFT` too: a crease or saddle (the mouth
#: corner), where a geodesic disc grows beyond π r² and the planar stamp stays closer to the ideal (`PROVISIONAL`).
SADDLE = 0.04
#: Iteration bound of the wrap's shortest-path rounds and pointer jumping (a stamp spans far fewer edge hops).
WRAP_ITERATIONS = 64
PLANAR, WRAP = "planar", "wrap"

__all__ = ["PLANAR", "WRAP", "Frame", "Placement", "Stamp", "alpha_stamp", "combine", "evaluate", "frame_tangent",
           "reflect"]


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
    stress: float = 0.0


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
    reach = r * math.hypot(hw, hh)
    gathered = surface.gather(centre, reach, facing)
    if gathered is None:
        return Stamp(*_EMPTY, frame)
    rel, slots = gathered.rel, gathered.slots
    d2 = gathered.d2 * np.float32((reach / r) ** 2)  # (d / r)²
    if frame is None:
        inner = d2 < np.float32(INNER_DISC * INNER_DISC)
        n = None
        if inner.any():
            s = slots[inner]
            n = (surface._tri_normal[s] * surface._texel_area[s][:, None]).sum(axis=0)
            length = float(np.linalg.norm(n))
            n = n / length if length > 1e-300 else None
        if n is None:
            n = np.asarray(facing, dtype=np.float64)
            n = n / max(float(np.linalg.norm(n)), 1e-300)
        t = frame_tangent(n, tangent, view_up)
        if angle:
            b0 = np.cross(n, t)
            th = math.radians(angle)
            t = math.cos(th) * t + math.sin(th) * b0
        frame = Frame(np.asarray(centre, dtype=np.float64), t, np.cross(n, t), n)
    basis = np.stack((frame.t, frame.b, frame.n), axis=1).astype(np.float32) / np.float32(r)
    local = rel @ basis  # (a, β, h) per texel
    a, beta, below = local[:, 0], local[:, 1], local[:, 2] < 0.0
    h = np.abs(local[:, 2])
    facing_n = surface._tri_normal32[slots] @ frame.n.astype(np.float32)
    in_rect = (np.abs(a) < np.float32(hw)) & (np.abs(beta) < np.float32(hh))
    count = int(np.count_nonzero(in_rect))
    # convex stress only: the surface falling away below the plane (a bulb, the wing, a lip over the other); in a
    # concave crease (the mouth corner) the planar stamp stays closer to the ideal than a geodesic one
    stressed = in_rect & below & ((h > np.float32(DEPTH_SOFT)) | (facing_n < np.float32(FADE_TO)))
    stress = float(np.count_nonzero(stressed)) / count if count else 0.0
    rising = float(np.count_nonzero(in_rect & ~below & (h > np.float32(DEPTH_SOFT)))) / count if count else 0.0
    if projection is None:
        projection = WRAP if stress > WRAP_STRESS and rising <= SADDLE else PLANAR
    diameter = 2.0 * math.sqrt(float(np.count_nonzero(d2 < 1.0)) / math.pi)
    level = image.level_for(diameter)
    if projection == WRAP:
        uv = _wrap(surface, centre, facing, reach, frame, gathered)
        if uv is not None:
            a = uv[:, 0] / np.float32(r)
            beta = uv[:, 1] / np.float32(r)
            keep = np.flatnonzero(np.isfinite(a) & (np.abs(a) < np.float32(hw)) & (np.abs(beta) < np.float32(hh)))
            if keep.size == 0:
                return Stamp(*_EMPTY, frame, level, diameter, WRAP, stress)
            a, beta = a[keep], beta[keep]
            coverage = image.sample(level, np.float32(0.5) + a / np.float32(2.0 * hw),
                                    np.float32(0.5) - beta / np.float32(2.0 * hh))
            return _finish(gathered, keep, coverage, d2, settings, frame, level, diameter, WRAP, stress)
        projection = PLANAR
    keep = np.flatnonzero(in_rect & (h < np.float32(DEPTH_MAX)))
    if keep.size == 0:
        return Stamp(*_EMPTY, frame, level, diameter, PLANAR, stress)
    a, beta, h = a[keep], beta[keep], h[keep]
    coverage = image.sample(level, np.float32(0.5) + a / np.float32(2.0 * hw), np.float32(0.5) - beta / np.float32(2.0 * hh))
    coverage *= np.float32(1.0) - _smoothstep(DEPTH_SOFT, DEPTH_MAX, h)
    coverage *= _smoothstep(FADE_FROM, FADE_TO, facing_n[keep])
    return _finish(gathered, keep, coverage, d2, settings, frame, level, diameter, PLANAR, stress)


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
    # vertex normals of the local triangles (area-weighted): the tangent planes the frame is turned onto
    cross = np.cross(x[tri[:, 1]] - x[tri[:, 0]], x[tri[:, 2]] - x[tri[:, 0]])
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
    hand = 1.0 if float(np.dot(np.cross(n, t), b)) >= 0.0 else -1.0  # a mirrored frame keeps its handedness
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
    bp = hand * np.cross(npn, tp)
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


def _kept_length(e: np.ndarray, t: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Edges `e` (n, 3) projected onto the plane of `t`, `b` ((3,) or (n, 3)) and scaled back to their own length."""
    if t.ndim == 1:
        proj = np.stack((e @ t, e @ b), axis=1)
    else:
        proj = np.stack((np.einsum("ij,ij->i", e, t), np.einsum("ij,ij->i", e, b)), axis=1)
    full = np.linalg.norm(e, axis=1)
    flat = np.linalg.norm(proj, axis=1)
    return proj * np.where(flat > 1e-300, full / np.maximum(flat, 1e-300), 0.0)[:, None]


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
    main = alpha_stamp(surface, placement.point, placement.normal, radius, image, tangent=placement.tangent,
                       view_up=view_up, angle=angle, settings=settings)
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
