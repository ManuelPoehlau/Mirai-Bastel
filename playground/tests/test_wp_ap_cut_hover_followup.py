"""WP-AP-CUT Hover Follow-up: headless tests for locked-edge projection (F1/F2).

Tests the _knife_project_locked_edge logic: given a locked edge and a cursor ray,
the projection onto the edge must apply the same ENDPOINT_THRESHOLD snap as
knife_pick() uses — returning a vertex target near the endpoints and an edge target
in the middle.

The function is replicated here as a pure function so it can be tested without
importing window.py (which would require a full GL context).  It shares the same
ENDPOINT_THRESHOLD constant and _edge_t_3d function from knife_pick.py, so there
is no duplicated threshold logic — only duplicated function structure for import
isolation purposes.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT), str(_REPO_ROOT / "tests"),
           str(_REPO_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from playground.topology_tools.knife_pick import (  # noqa: E402
    _edge_t_3d,
    ENDPOINT_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Pure-function replica of _knife_project_locked_edge for headless testing
# ---------------------------------------------------------------------------

class _FakeMesh:
    """Minimal mesh stub with two vertices."""
    def __init__(self, p0, p1, va_id=0, vb_id=1, edge_id=10):
        self._p0 = p0
        self._p1 = p1
        self._va = va_id
        self._vb = vb_id
        self._eid = edge_id

    def edge_vertices(self, eid):
        assert eid == self._eid
        return self._va, self._vb

    def vertex_position(self, vid):
        if vid == self._va:
            return self._p0
        if vid == self._vb:
            return self._p1
        raise KeyError(vid)


class _FakeCamera:
    """Minimal camera stub: screen_to_ray returns a fixed -Z ray through (x, y, 5)."""
    def screen_to_ray(self, x, y, width, height):
        return (float(x), float(y), 5.0), (0.0, 0.0, -1.0)


def _project_locked_edge(camera, mesh, x, y, width, height, locked_eid):
    """Local replica of window._knife_project_locked_edge for headless testing."""
    origin, direction = camera.screen_to_ray(x, y, width, height)
    va, vb = mesh.edge_vertices(locked_eid)
    p0 = mesh.vertex_position(va)
    p1 = mesh.vertex_position(vb)
    t = _edge_t_3d(origin, direction, p0, p1)
    if t <= ENDPOINT_THRESHOLD:
        return {"kind": "vertex", "vertex_id": va}
    if t >= 1.0 - ENDPOINT_THRESHOLD:
        return {"kind": "vertex", "vertex_id": vb}
    return {"kind": "edge", "edge_id": locked_eid, "t": t}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_horizontal_edge():
    """Edge from (0,0,0) to (2,0,0), camera rays shoot straight down -Z."""
    mesh = _FakeMesh((0.0, 0.0, 0.0), (2.0, 0.0, 0.0))
    camera = _FakeCamera()
    return mesh, camera, mesh._eid, mesh._va, mesh._vb


# ---------------------------------------------------------------------------
# 1. Mid-edge cursor → edge target with correct t
# ---------------------------------------------------------------------------

def test_mid_edge_returns_edge_kind():
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    result = _project_locked_edge(camera, mesh, 1.0, 0.0, 800, 600, eid)
    assert result["kind"] == "edge"
    assert result["edge_id"] == eid


def test_mid_edge_t_is_half():
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    result = _project_locked_edge(camera, mesh, 1.0, 0.0, 800, 600, eid)
    assert abs(result["t"] - 0.5) < 1e-6


def test_quarter_edge_t_is_quarter():
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    result = _project_locked_edge(camera, mesh, 0.5, 0.0, 800, 600, eid)
    assert result["kind"] == "edge"
    assert abs(result["t"] - 0.25) < 1e-6


# ---------------------------------------------------------------------------
# 2. Cursor near p0 endpoint → snaps to va
# ---------------------------------------------------------------------------

def test_near_p0_snaps_to_va():
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    # t = 0.0 at p0 — within ENDPOINT_THRESHOLD
    result = _project_locked_edge(camera, mesh, 0.0, 0.0, 800, 600, eid)
    assert result["kind"] == "vertex"
    assert result["vertex_id"] == va


def test_near_p0_just_inside_threshold():
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    # t = ENDPOINT_THRESHOLD * 2.0 = 0.02 * edge length (2.0) = 0.04 from p0
    x = ENDPOINT_THRESHOLD * 0.5 * 2.0  # half-threshold fraction * edge length
    result = _project_locked_edge(camera, mesh, x, 0.0, 800, 600, eid)
    assert result["kind"] == "vertex"
    assert result["vertex_id"] == va


# ---------------------------------------------------------------------------
# 3. Cursor near p1 endpoint → snaps to vb
# ---------------------------------------------------------------------------

def test_near_p1_snaps_to_vb():
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    result = _project_locked_edge(camera, mesh, 2.0, 0.0, 800, 600, eid)
    assert result["kind"] == "vertex"
    assert result["vertex_id"] == vb


def test_near_p1_just_inside_threshold():
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    x = 2.0 - ENDPOINT_THRESHOLD * 0.5 * 2.0
    result = _project_locked_edge(camera, mesh, x, 0.0, 800, 600, eid)
    assert result["kind"] == "vertex"
    assert result["vertex_id"] == vb


# ---------------------------------------------------------------------------
# 4. Cursor far off the mesh — projection still returns a valid result
# ---------------------------------------------------------------------------

def test_cursor_far_off_mesh_returns_edge():
    """Locked-edge projection is always defined regardless of cursor distance."""
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    # Cursor 1000 units above the mesh in screen X — projects to clamped t
    result = _project_locked_edge(camera, mesh, 500.0, 999.0, 800, 600, eid)
    # t should be clamped to 1.0 and thus snap to vb, or be a valid edge/vertex
    assert result["kind"] in ("edge", "vertex")


def test_cursor_below_p0_clamps_to_va():
    """Cursor off the left end: t < 0 is clamped to 0.0, snaps to va."""
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    result = _project_locked_edge(camera, mesh, -10.0, 0.0, 800, 600, eid)
    assert result["kind"] == "vertex"
    assert result["vertex_id"] == va


def test_cursor_past_p1_clamps_to_vb():
    """Cursor off the right end: t > 1 is clamped to 1.0, snaps to vb."""
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    result = _project_locked_edge(camera, mesh, 100.0, 0.0, 800, 600, eid)
    assert result["kind"] == "vertex"
    assert result["vertex_id"] == vb


# ---------------------------------------------------------------------------
# 5. Threshold boundary: just outside threshold → edge, just inside → vertex
# ---------------------------------------------------------------------------

def test_just_outside_threshold_from_p0_returns_edge():
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    # t = ENDPOINT_THRESHOLD + epsilon → should return edge
    x = (ENDPOINT_THRESHOLD + 0.001) * 2.0
    result = _project_locked_edge(camera, mesh, x, 0.0, 800, 600, eid)
    assert result["kind"] == "edge"


def test_just_outside_threshold_from_p1_returns_edge():
    mesh, camera, eid, va, vb = _make_horizontal_edge()
    x = 2.0 - (ENDPOINT_THRESHOLD + 0.001) * 2.0
    result = _project_locked_edge(camera, mesh, x, 0.0, 800, 600, eid)
    assert result["kind"] == "edge"
