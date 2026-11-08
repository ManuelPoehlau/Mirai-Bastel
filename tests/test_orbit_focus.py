"""Dynamic Orbit Focus, pure part (`mirai.orbit_focus`): which vertices a recorded change actually worked
on (strict tiers), the geometric gate, the preferred narrowing and the bounding-box centre. The app-level
paths (Extrude, Knife, Soft, morph view, undo) are in tests/test_application_orbit_focus.py."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh, PointLayerInfo
from mirai.orbit_focus import FocusTracker, bbox_centre, focus_point, worked_area
from mirai.scene_factory import create_plane


def _plane(segments: int = 4) -> Mesh:
    return create_plane(size=4.0, segments=segments)  # step 1.0, x/z in [-2, 2]


def _vertex_at(mesh: Mesh, x: float, z: float):
    return next(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v) == (x, 0.0, z))


def _edge(mesh: Mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def _watched(mesh: Mesh) -> FocusTracker:
    tracker = FocusTracker()
    tracker.bind(mesh)
    return tracker


def test_moved_vertices_are_the_worked_area():
    mesh = _plane()
    tracker = _watched(mesh)
    a, b = _vertex_at(mesh, 1.0, 1.0), _vertex_at(mesh, 2.0, 1.0)
    mesh.set_vertex_position(a, (1.0, 1.0, 1.0))
    mesh.set_vertex_position(b, (2.0, 3.0, 1.0))
    assert focus_point(tracker.take(), mesh) == (1.5, 2.0, 1.0)


def test_split_edge_counts_the_new_vertex_not_the_rewritten_faces():
    mesh = _plane()
    tracker = _watched(mesh)
    edge = _edge(mesh, _vertex_at(mesh, -2.0, -2.0), _vertex_at(mesh, -1.0, -2.0))
    new_vertex, _, _ = mesh.split_edge(edge, 0.5)
    tier, _ = worked_area(tracker.take(), mesh)
    assert tier == {new_vertex}


def test_vertex_connect_uses_the_created_edge():
    mesh = _plane(1)
    tracker = _watched(mesh)
    face = mesh.all_face_ids()[0]
    a, _, c, _ = mesh.face_vertices(face)
    mesh.connect_vertices(face, a, c)
    change = tracker.take()
    tier, _ = worked_area(change, mesh)
    assert tier == {a, c}
    assert focus_point(change, mesh) == (0.0, 0.0, 0.0)


def test_edge_dissolve_uses_the_removed_edge():
    mesh = _plane()
    a, b = _vertex_at(mesh, 0.0, -1.0), _vertex_at(mesh, 0.0, 0.0)
    edge = _edge(mesh, a, b)
    tracker = _watched(mesh)
    mesh.dissolve_edges([edge], cleanup=False)
    assert focus_point(tracker.take(), mesh) == (0.0, 0.0, -0.5)


def test_deleted_vertices_keep_their_positions():
    mesh = _plane()
    victim = _vertex_at(mesh, 0.0, 0.0)
    mesh.set_vertex_position(victim, (0.0, 0.5, 0.0))
    tracker = _watched(mesh)
    mesh.delete_vertices([victim])
    change = tracker.take()
    tier, removed = worked_area(change, mesh)
    assert tier == {victim} and removed == {victim: (0.0, 0.5, 0.0)}
    assert focus_point(change, mesh) == (0.0, 0.5, 0.0)


def test_cap_uses_the_corners_of_the_new_face():
    mesh = _plane()
    face = next(f for f in mesh.all_face_ids()
                if all(0.0 <= mesh.vertex_position(v)[0] <= 1.0 and 0.0 <= mesh.vertex_position(v)[2] <= 1.0
                       for v in mesh.face_vertices(f)))
    boundary = mesh.face_vertices(face)
    mesh.delete_faces([face])
    tracker = _watched(mesh)
    mesh.add_face(boundary)
    assert focus_point(tracker.take(), mesh) == (0.5, 0.0, 0.5)


def test_preferred_sets_narrow_the_tier_in_order():
    mesh = _plane()
    tracker = _watched(mesh)
    a, b = _vertex_at(mesh, -2.0, 0.0), _vertex_at(mesh, 2.0, 0.0)
    mesh.set_vertex_position(a, (-2.0, 1.0, 0.0))
    mesh.set_vertex_position(b, (2.0, 1.0, 0.0))
    change = tracker.take()
    assert focus_point(change, mesh, preferred=[{a}]) == (-2.0, 1.0, 0.0)
    assert focus_point(change, mesh, preferred=[set(), {b}]) == (2.0, 1.0, 0.0)
    assert focus_point(change, mesh, preferred=[{_vertex_at(mesh, 0.0, 0.0)}]) == (0.0, 1.0, 0.0)


def test_live_positions_come_from_the_shown_mesh():
    mesh = _plane()
    shown = Mesh.from_state(mesh.export_state())
    tracker = _watched(mesh)
    v = _vertex_at(mesh, 0.0, 0.0)
    mesh.set_vertex_position(v, (0.0, 1.0, 0.0))
    shown.set_vertex_position(v, (0.0, 5.0, 0.0))
    assert focus_point(tracker.take(), mesh, query_mesh=shown) == (0.0, 5.0, 0.0)


def test_no_geometric_work_gives_no_focus():
    mesh = _plane()
    tracker = _watched(mesh)
    v = _vertex_at(mesh, 0.0, 0.0)
    # A cancelled preview: rolled back exactly.
    change = mesh.begin_change()
    mesh.set_vertex_position(v, (0.0, 2.0, 0.0))
    mesh.rollback_change(change)
    assert focus_point(tracker.take(), mesh) is None
    # Layer only (morph target / weights).
    lid = mesh.add_point_layer(PointLayerInfo("T"))
    mesh.set_layer_value(lid, v, (0.0, 1.0, 0.0))
    assert focus_point(tracker.take(), mesh) is None
    # Moved and moved back within one window.
    mesh.set_vertex_position(v, (0.0, 2.0, 0.0))
    mesh.set_vertex_position(v, (0.0, 0.0, 0.0))
    assert focus_point(tracker.take(), mesh) is None
    assert focus_point(None, mesh) is None


def test_cost_is_bounded_by_the_touched_elements(monkeypatch):
    mesh = _plane(8)
    tracker = _watched(mesh)
    v = _vertex_at(mesh, 0.0, 0.0)
    mesh.set_vertex_position(v, (0.0, 1.0, 0.0))
    for name in ("all_vertex_ids", "all_edge_ids", "all_face_ids", "export_state"):
        monkeypatch.setattr(mesh, name, lambda *a, **k: pytest.fail("the focus scanned the mesh"))
    assert focus_point(tracker.take(), mesh) == (0.0, 1.0, 0.0)


def test_tracker_rebinds_and_closes():
    a, b = _plane(), _plane()
    tracker = FocusTracker()
    assert tracker.take() is None
    tracker.bind(a)
    tracker.bind(b)
    va = _vertex_at(a, 0.0, 0.0)
    a.set_vertex_position(va, (0.0, 1.0, 0.0))
    assert not tracker.take().vertices  # a is no longer watched
    logs = len(b._logs)
    tracker.close()
    assert len(b._logs) == logs - 1 and tracker.take() is None


def test_bbox_centre():
    assert bbox_centre([]) is None
    assert bbox_centre([(0.0, 0.0, 0.0), (2.0, -4.0, 1.0), (1.0, 0.0, 0.0)]) == (1.0, -2.0, 0.5)
