"""AD-017: Vertex Connect per-face (Wings-style) headless tests.

Covers §1.5 and §4 of WP-AP-CUT_PLAN.md.
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

import pytest  # noqa: E402

from core import Scene  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402
from playground.app import PlaygroundApp  # noqa: E402
from playground.topology_tools.connect_vertices_per_face import (  # noqa: E402
    VertexConnectError,
    connect_vertices_per_face,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _app_with_hexagon():
    """PlaygroundApp with a single hexagonal face."""
    app = PlaygroundApp()
    mesh = app.scene.mesh
    verts = []
    for i in range(6):
        angle = math.pi / 3.0 * i
        verts.append(mesh.add_vertex((math.cos(angle), math.sin(angle), 0.0)))
    mesh.add_face(verts)
    return app, verts


def _app_with_quad():
    """PlaygroundApp with a single quad."""
    app = PlaygroundApp()
    mesh = app.scene.mesh
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    mesh.add_face([v0, v1, v2, v3])
    return app, (v0, v1, v2, v3)


# ---------------------------------------------------------------------------
# 1. Basic connect on a quad
# ---------------------------------------------------------------------------

def test_quad_non_adjacent_vertices_connect():
    app, (v0, v1, v2, v3) = _app_with_quad()
    before_hist = len(app.scene.history._undo_stack)
    created = connect_vertices_per_face(app.scene, {v0, v2})
    assert len(created) == 1
    mesh = app.scene.mesh
    assert mesh.is_valid_edge(created[0])
    assert_mesh_invariants(mesh, context="vertex connect quad diagonal")
    # One history entry pushed
    assert len(app.scene.history._undo_stack) == before_hist + 1


def test_quad_adjacent_vertices_no_op():
    """v0 and v1 are adjacent — nothing connectable."""
    app, (v0, v1, v2, v3) = _app_with_quad()
    before_hist = len(app.scene.history._undo_stack)
    created = connect_vertices_per_face(app.scene, {v0, v1})
    assert created == []
    # No history entry (idempotent no-op)
    assert len(app.scene.history._undo_stack) == before_hist


# ---------------------------------------------------------------------------
# 2. Hexagon cases (from vertex_connect_incremental_probe.py)
# ---------------------------------------------------------------------------

def test_hexagon_alternating_three_vertices():
    """Select every other vertex of a hexagon (v0, v2, v4) — expect 3 edges."""
    app, verts = _app_with_hexagon()
    v0, v1, v2, v3, v4, v5 = verts
    created = connect_vertices_per_face(app.scene, {v0, v2, v4})
    mesh = app.scene.mesh
    assert len(created) == 3
    assert all(mesh.is_valid_edge(e) for e in created)
    assert_mesh_invariants(mesh, context="hexagon alternating three")


def test_hexagon_two_adjacent_vertices_no_op():
    """v0 and v1 are adjacent in the hexagon — no connection possible."""
    app, verts = _app_with_hexagon()
    v0, v1 = verts[0], verts[1]
    created = connect_vertices_per_face(app.scene, {v0, v1})
    assert created == []


def test_hexagon_two_non_adjacent_vertices():
    """v0 and v2 — non-adjacent in hexagon (1 skip), should connect."""
    app, verts = _app_with_hexagon()
    v0, v2 = verts[0], verts[2]
    created = connect_vertices_per_face(app.scene, {v0, v2})
    mesh = app.scene.mesh
    assert len(created) == 1
    assert mesh.is_valid_edge(created[0])
    assert_mesh_invariants(mesh, context="hexagon two non-adjacent")


# ---------------------------------------------------------------------------
# 3. Stray vertex (vertex on no face that qualifies) is silently ignored
# ---------------------------------------------------------------------------

def test_stray_vertex_on_different_face_ignored():
    """One vertex with no partner on any face → ignored; valid pair still connects."""
    app = PlaygroundApp()
    mesh = app.scene.mesh
    # Quad 1
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    mesh.add_face([v0, v1, v2, v3])
    # Isolated vertex not on any face
    stray = mesh.add_vertex((5.0, 5.0, 0.0))
    # Select v0, v2 (diagonal), plus stray
    created = connect_vertices_per_face(app.scene, {v0, v2, stray})
    # Should still create the v0-v2 connection; stray has no partner
    assert len(created) == 1
    assert mesh.is_valid_edge(created[0])
    assert_mesh_invariants(mesh, context="stray vertex ignored")


# ---------------------------------------------------------------------------
# 4. Nothing connectable → no-op, no history
# ---------------------------------------------------------------------------

def test_nothing_connectable_no_history_entry():
    app, (v0, v1, v2, v3) = _app_with_quad()
    before_hist = len(app.scene.history._undo_stack)
    before_state = app.scene.mesh.export_state()
    # All pairs are adjacent in the quad (v0-v1, v1-v2)
    created = connect_vertices_per_face(app.scene, {v0, v1})
    assert created == []
    assert len(app.scene.history._undo_stack) == before_hist
    assert app.scene.mesh.export_state() == before_state


# ---------------------------------------------------------------------------
# 5. Idempotent repeat
# ---------------------------------------------------------------------------

def test_idempotent_repeat():
    """Connecting v0-v2 a second time is a no-op (they become adjacent after first)."""
    app, (v0, v1, v2, v3) = _app_with_quad()
    created1 = connect_vertices_per_face(app.scene, {v0, v2})
    assert len(created1) == 1
    hist_after_first = len(app.scene.history._undo_stack)

    # Second C on same selection — v0 and v2 are now adjacent
    created2 = connect_vertices_per_face(app.scene, {v0, v2})
    assert created2 == []
    assert len(app.scene.history._undo_stack) == hist_after_first


# ---------------------------------------------------------------------------
# 6. Residue unchanged (selection mode and set preserved)
# ---------------------------------------------------------------------------

def test_residue_selection_unchanged():
    """Vertex Connect leaves the selection unchanged (mode stays Vertex, same verts selected)."""
    from core.selection import SelectionMode
    app, (v0, v1, v2, v3) = _app_with_quad()
    sel = app.scene.selection
    sel.mode = SelectionMode.VERTEX
    sel.clear()
    sel.add({v0, v2})
    connect_vertices_per_face(app.scene, {v0, v2})
    # Selection is untouched by the function (window code manages selection)
    assert sel.mode is SelectionMode.VERTEX
    assert sel.vertices == {v0, v2}


# ---------------------------------------------------------------------------
# 7. Input validation errors
# ---------------------------------------------------------------------------

def test_raises_on_fewer_than_two_vertices():
    app, (v0, v1, v2, v3) = _app_with_quad()
    with pytest.raises(VertexConnectError):
        connect_vertices_per_face(app.scene, {v0})


def test_raises_on_invalid_vertex():
    from core import VertexId
    app, (v0, v1, v2, v3) = _app_with_quad()
    fake_id = VertexId(9999)
    with pytest.raises(VertexConnectError):
        connect_vertices_per_face(app.scene, {v0, fake_id})


# ---------------------------------------------------------------------------
# 8. Ngon face — still works
# ---------------------------------------------------------------------------

def test_ngon_pentagon():
    """Pentagon with v0 and v3 non-adjacent (3 apart in 5-gon)."""
    app = PlaygroundApp()
    mesh = app.scene.mesh
    verts = [mesh.add_vertex((math.cos(2*math.pi/5*i), math.sin(2*math.pi/5*i), 0.0))
             for i in range(5)]
    mesh.add_face(verts)
    v0, v1, v2, v3, v4 = verts
    created = connect_vertices_per_face(app.scene, {v0, v3})
    assert len(created) == 1
    assert mesh.is_valid_edge(created[0])
    assert_mesh_invariants(mesh, context="pentagon vertex connect")
