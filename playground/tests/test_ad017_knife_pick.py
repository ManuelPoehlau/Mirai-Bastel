"""AD-017 regression: `_edge_t_3d()` segment-parameter contract (Knife edge pick).

Covers §1.8 of WP-AP-CUT_PLAN.md — "edge hit with perspective-correct 3D `t`
(closest point between the view ray and the edge segment; screen-space t is not
sufficient); t within a documented endpoint threshold → treat as that vertex".

Contract locked here (`playground/topology_tools/knife_pick.py`):
    t = 0.0 at the first endpoint (p0) · t ≈ 0.5 in the middle ·
    t = 1.0 at the second endpoint (p1), clamped to [0, 1] outside the edge.

Regression (AD-017, fixed 2026-09-22): the pre-fix code returned the negated
segment parameter, so every click in front of the camera produced a negative t
that the internal `max(0.0, min(1.0, t))` clamp turned into 0.0. Downstream
every edge hit therefore fell inside ENDPOINT_THRESHOLD and was reclassified as
a vertex hit on p0 — Knife never received a {"kind": "edge"} target, so
Vertex→Edge / Edge→Edge produced "no cuts made". The middle, offset-ray and
endpoint assertions below fail against the old formula, because the clamp pins
those values to 0.0.

Pure ray/segment math — no mesh, no camera, no GL.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT), str(_REPO_ROOT / "tests"),
           str(_REPO_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from playground.topology_tools.knife_pick import _edge_t_3d  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: a -Z view ray through (x, y, 5)
# ---------------------------------------------------------------------------

def _ray_through(x: float, y: float):
    """(origin, direction) of a -Z view ray through the point (x, y, 5).

    For an edge lying in the Z = 0 plane the resolved parameter is that of the
    edge point closest to (x, y). An offset in y that is no longer on the edge
    still resolves to the perpendicular foot, so this exercises the true 3D
    closest point rather than a mere crossing of the Z = 0 plane.
    """
    return (x, y, 5.0), (0.0, 0.0, -1.0)


# ---------------------------------------------------------------------------
# 1. Contract: 0.0 at p0 — 0.5 in the middle — 1.0 at p1
# ---------------------------------------------------------------------------

def test_t_is_zero_at_first_endpoint():
    p0, p1 = (0.0, 0.0, 0.0), (2.0, 0.0, 0.0)
    origin, direction = _ray_through(0.0, 0.0)  # straight through p0
    t = _edge_t_3d(origin, direction, p0, p1)
    assert math.isclose(t, 0.0, abs_tol=1e-9), f"t={t!r}, expected 0.0 at p0"


def test_t_is_half_in_the_middle():
    p0, p1 = (0.0, 0.0, 0.0), (2.0, 0.0, 0.0)
    origin, direction = _ray_through(1.0, 0.0)  # straight through the midpoint
    t = _edge_t_3d(origin, direction, p0, p1)
    assert math.isclose(t, 0.5, abs_tol=1e-9), f"t={t!r}, expected 0.5 mid-edge"


def test_t_is_one_at_second_endpoint():
    p0, p1 = (0.0, 0.0, 0.0), (2.0, 0.0, 0.0)
    origin, direction = _ray_through(2.0, 0.0)  # straight through p1
    t = _edge_t_3d(origin, direction, p0, p1)
    assert math.isclose(t, 1.0, abs_tol=1e-9), f"t={t!r}, expected 1.0 at p1"


# ---------------------------------------------------------------------------
# 2. Sign guard: the parameter is positive and grows along the edge
# ---------------------------------------------------------------------------

def test_t_increases_along_the_edge_and_is_never_negative():
    """The pre-fix formula returned -t; the clamp then hid it as 0.0."""
    p0, p1 = (0.0, 0.0, 0.0), (4.0, 0.0, 0.0)

    def t_at(x: float) -> float:
        origin, direction = _ray_through(x, 0.0)
        return _edge_t_3d(origin, direction, p0, p1)

    values = [t_at(1.0), t_at(2.0), t_at(3.0)]  # 0.25, 0.50, 0.75
    assert all(v > 0.0 for v in values), f"negative segment parameter(s): {values}"
    assert values == sorted(values), f"not increasing along the edge: {values}"
    for t, expected in zip(values, (0.25, 0.5, 0.75)):
        assert math.isclose(t, expected, abs_tol=1e-9), f"t={t!r}, expected {expected}"


def test_t_follows_the_p0_to_p1_order():
    """Swapping the endpoints mirrors the parameter (0.25 → 0.75)."""
    origin, direction = _ray_through(0.5, 0.0)
    forward = _edge_t_3d(origin, direction, (0.0, 0.0, 0.0), (2.0, 0.0, 0.0))
    backward = _edge_t_3d(origin, direction, (2.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    assert math.isclose(forward, 0.25, abs_tol=1e-9), f"t={forward!r}, expected 0.25"
    assert math.isclose(backward, 0.75, abs_tol=1e-9), f"t={backward!r}, expected 0.75"


# ---------------------------------------------------------------------------
# 3. Perspective-correct closest point (not a screen/plane crossing)
# ---------------------------------------------------------------------------

def test_t_uses_the_3d_closest_point_for_an_offset_ray():
    """A ray offset in y misses the edge yet resolves to the perpendicular foot."""
    p0, p1 = (0.0, 0.0, 0.0), (2.0, 0.0, 0.0)
    origin, direction = _ray_through(0.5, 0.5)
    t = _edge_t_3d(origin, direction, p0, p1)
    assert math.isclose(t, 0.25, abs_tol=1e-9), f"t={t!r}, expected 0.25"


def test_t_works_for_a_non_axis_aligned_edge():
    p0, p1 = (1.0, 1.0, 0.0), (3.0, 3.0, 0.0)  # diagonal in the Z = 0 plane
    origin, direction = _ray_through(2.0, 2.0)   # through its midpoint
    t = _edge_t_3d(origin, direction, p0, p1)
    assert math.isclose(t, 0.5, abs_tol=1e-9), f"t={t!r}, expected 0.5"


# ---------------------------------------------------------------------------
# 4. Clamping outside the edge (the caller's ENDPOINT_THRESHOLD relies on it)
# ---------------------------------------------------------------------------

def test_t_is_clamped_outside_the_edge():
    p0, p1 = (0.0, 0.0, 0.0), (2.0, 0.0, 0.0)
    before_origin, before_direction = _ray_through(-0.5, 0.0)  # before p0
    after_origin, after_direction = _ray_through(2.5, 0.0)     # beyond p1
    before = _edge_t_3d(before_origin, before_direction, p0, p1)
    after = _edge_t_3d(after_origin, after_direction, p0, p1)
    assert before == 0.0, f"expected saturation at 0.0 before p0, got {before!r}"
    assert after == 1.0, f"expected saturation at 1.0 beyond p1, got {after!r}"
