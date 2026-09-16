"""Headless tests for EX-A H01 (Articulation) — no GL, no window.

Covers verification items from the EX-A handoff that do not require a
display:

    2. Articulation mit Pivot + Falloff funktioniert
    5. Restore stellt die exakte Restpose wieder her
    6. Topology kann geaendert werden (setup unaffected by articulation)
    7. Danach kann erneut artikuliert werden
    9. Regression: bestehende Topology-Operationen bleiben unveraendert

Items 1, 3, 4 (window start, bent state survives gesture end, orbit/pan/
zoom during bent state) require pyglet + a real window and are explicitly
OUT of scope here — see H02 in the handoff.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
_RIGGING = _REPO_ROOT / "experiments" / "rigging-skinning-morphing"
_ARTICULATION = _REPO_ROOT / "playground" / "experiments" / "articulation"
for _p in (str(_REPO_SRC), str(_REPO_ROOT), str(_RIGGING), str(_ARTICULATION)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from articulation import ArticulationError, ArticulationState  # noqa: E402
from demo_cylinder import build_cylinder  # noqa: E402


def _cylinder():
    # small enough for fast tests, enough rings to give the falloff room
    return build_cylinder(segments=8, rings=6, radius=0.5, height=3.0)


def _positions(mesh):
    return {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}


# ---------------------------------------------------------------------------
# 2. Pivot + falloff produces a real, spatially-varying deformation
# ---------------------------------------------------------------------------


def test_bend_moves_vertices_near_pivot():
    mesh = _cylinder()
    before = _positions(mesh)
    state = ArticulationState(mesh=mesh, pivot=(0.0, 0.0, 0.0), axis=(1.0, 0.0, 0.0), radius=2.0)
    state.begin()
    state.update(math.radians(45))

    moved = 0
    for vid, rest in before.items():
        now = mesh.vertex_position(vid)
        if now != rest:
            moved += 1
    assert moved > 0, "at least some vertices must move under a 45deg bend"


def test_falloff_attenuates_with_distance_from_pivot():
    mesh = _cylinder()
    before = _positions(mesh)
    # Pivot at mesh center. radius=1.0 > cylinder radius (0.5), so the
    # ring nearest the pivot (whose 3D distance already includes the
    # 0.5 radial offset) still falls inside the falloff.
    state = ArticulationState(mesh=mesh, pivot=(0.0, 0.0, 0.0), axis=(1.0, 0.0, 0.0), radius=1.0)
    state.begin()
    state.update(math.radians(90))

    far_vertex = next(
        vid for vid, pos in before.items() if abs(pos[1]) > 1.4  # near a cap, far from pivot
    )
    near_vertex = min(before, key=lambda vid: abs(before[vid][1]))  # ring closest to pivot
    assert mesh.vertex_position(far_vertex) == before[far_vertex], (
        "vertex well outside the falloff radius must not move"
    )
    assert mesh.vertex_position(near_vertex) != before[near_vertex], (
        "vertex at the pivot must move under a 90deg bend"
    )


def test_update_is_relative_to_rest_not_cumulative():
    """Two update() calls with the same angle must land on the same
    positions — proves update() recomputes from the rest snapshot each
    time rather than compounding rotations."""
    mesh = _cylinder()
    state = ArticulationState(mesh=mesh, pivot=(0.0, 0.0, 0.0), axis=(1.0, 0.0, 0.0), radius=2.0)
    state.begin()
    state.update(math.radians(30))
    first_pass = _positions(mesh)
    state.update(math.radians(60))
    state.update(math.radians(30))
    second_pass = _positions(mesh)
    for vid in first_pass:
        ax, ay, az = first_pass[vid]
        bx, by, bz = second_pass[vid]
        assert math.isclose(ax, bx, abs_tol=1e-9)
        assert math.isclose(ay, by, abs_tol=1e-9)
        assert math.isclose(az, bz, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# 5. restore() returns the EXACT rest pose
# ---------------------------------------------------------------------------


def test_restore_is_exact():
    mesh = _cylinder()
    before = _positions(mesh)
    state = ArticulationState(mesh=mesh, pivot=(0.0, 0.3, 0.0), axis=(0.0, 0.0, 1.0), radius=1.2)
    state.begin()
    state.update(math.radians(73))
    state.update(math.radians(12))  # multiple updates during one drag
    state.restore()
    after = _positions(mesh)
    assert before == after, "restore() must reproduce the exact rest positions"
    assert state.is_bent is False


def test_restore_before_begin_raises():
    mesh = _cylinder()
    state = ArticulationState(mesh=mesh, pivot=(0, 0, 0), axis=(1, 0, 0), radius=1.0)
    with pytest.raises(ArticulationError):
        state.restore()


def test_double_begin_raises():
    mesh = _cylinder()
    state = ArticulationState(mesh=mesh, pivot=(0, 0, 0), axis=(1, 0, 0), radius=1.0)
    state.begin()
    with pytest.raises(ArticulationError):
        state.begin()


def test_zero_radius_rejected():
    mesh = _cylinder()
    state = ArticulationState(mesh=mesh, pivot=(0, 0, 0), axis=(1, 0, 0), radius=0.0)
    with pytest.raises(ArticulationError):
        state.begin()


# ---------------------------------------------------------------------------
# 6 & 7. Topology change after restore, then articulate again
# ---------------------------------------------------------------------------


def test_topology_change_after_restore_then_articulate_again():
    mesh = _cylinder()
    rest_before_bend = _positions(mesh)

    state = ArticulationState(mesh=mesh, pivot=(0.0, 0.0, 0.0), axis=(1.0, 0.0, 0.0), radius=1.5)
    state.begin()
    state.update(math.radians(40))
    state.restore()
    assert _positions(mesh) == rest_before_bend, "must be exactly at rest before editing topology"

    # H01 constraint: topology only changes in the REST state (never while
    # bent). Calling Mesh.split_edge directly here — the same production
    # call playground/topology_ops.py::split_selected_edge wraps with a
    # MeshStateCommand for the real UI path; history wiring is already
    # covered by the existing topology test suite and is not this
    # module's concern.
    some_edge = next(iter(mesh.all_edge_ids()))
    v_before, e_before, f_before = (
        len(mesh.all_vertex_ids()),
        len(mesh.all_edge_ids()),
        len(mesh.all_face_ids()),
    )
    mesh.split_edge(some_edge)
    assert len(mesh.all_vertex_ids()) == v_before + 1
    assert len(mesh.all_edge_ids()) > e_before
    assert len(mesh.all_face_ids()) >= f_before

    # Articulate again after the topology change — new state instance,
    # fresh rest snapshot (includes the new vertex from the split).
    rest_after_split = _positions(mesh)
    state2 = ArticulationState(mesh=mesh, pivot=(0.0, 0.0, 0.0), axis=(1.0, 0.0, 0.0), radius=1.5)
    state2.begin()
    state2.update(math.radians(40))
    moved = sum(1 for vid, rest in rest_after_split.items() if mesh.vertex_position(vid) != rest)
    assert moved > 0, "articulation must work again after a topology edit"
    state2.restore()
    assert _positions(mesh) == rest_after_split, "second restore must also be exact"


def test_cannot_update_without_begin():
    mesh = _cylinder()
    state = ArticulationState(mesh=mesh, pivot=(0, 0, 0), axis=(1, 0, 0), radius=1.0)
    with pytest.raises(ArticulationError):
        state.update(0.1)


def test_zero_axis_rejected_at_update():
    mesh = _cylinder()
    state = ArticulationState(mesh=mesh, pivot=(0, 0, 0), axis=(0.0, 0.0, 0.0), radius=1.0)
    state.begin()
    with pytest.raises(ArticulationError):
        state.update(0.5)


# ---------------------------------------------------------------------------
# demo_cylinder sanity — this is new test infrastructure, verify it directly
# ---------------------------------------------------------------------------


def test_cylinder_is_deterministic():
    a = _cylinder()
    b = _cylinder()
    assert _positions(a) == _positions(b)


def test_cylinder_has_only_two_poles():
    """Confirms the design rationale in demo_cylinder.py: unlike the Head
    Basemesh (52 poles), this body is regular everywhere except the two
    cap centers — so Loop Select / Loop Slide / Connect Edges keep working
    along the whole bendable length."""
    mesh = _cylinder()
    from collections import defaultdict

    valence = defaultdict(int)
    for eid in mesh.all_edge_ids():
        v0, v1 = mesh.edge_vertices(eid)
        valence[v0] += 1
        valence[v1] += 1
    non_regular = [vid for vid, v in valence.items() if v != 4]
    assert len(non_regular) == 2, f"expected exactly 2 poles (caps), found {len(non_regular)}"
