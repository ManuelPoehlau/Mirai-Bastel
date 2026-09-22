"""AD-017: Contextual C dispatch, shared helpers, and Split residue tests.

Headless — no GL, no window.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT), str(_REPO_ROOT / "tests"),
           str(_REPO_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from core import Scene  # noqa: E402
from core.selection import Selection, SelectionMode  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402
from playground.app import PlaygroundApp  # noqa: E402
from playground.topology_ops import split_selected_edge  # noqa: E402
from playground.topology_tools.contextual_c import CContext, resolve_c_context  # noqa: E402
from playground.topology_tools.topology_points import (  # noqa: E402
    EdgePoint,
    VertexPoint,
    connect_in_shared_face,
    resolve_point,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _quad_scene():
    """Single quad (v0,v1,v2,v3) with one face."""
    scene = Scene()
    mesh = scene.mesh
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    face = mesh.add_face([v0, v1, v2, v3])
    return scene, (v0, v1, v2, v3), face


def _two_quad_scene():
    """Two quads sharing edge v1-v2.

    v0-v1-v4
    |  |  |
    v3-v2-v5
    """
    scene = Scene()
    mesh = scene.mesh
    v0 = mesh.add_vertex((0.0, 1.0, 0.0))
    v1 = mesh.add_vertex((1.0, 1.0, 0.0))
    v2 = mesh.add_vertex((1.0, 0.0, 0.0))
    v3 = mesh.add_vertex((0.0, 0.0, 0.0))
    v4 = mesh.add_vertex((2.0, 1.0, 0.0))
    v5 = mesh.add_vertex((2.0, 0.0, 0.0))
    f1 = mesh.add_face([v0, v1, v2, v3])
    f2 = mesh.add_face([v1, v4, v5, v2])
    return scene, (v0, v1, v2, v3, v4, v5), (f1, f2)


def _hexagon_scene():
    """One hexagonal face with 6 vertices."""
    import math
    scene = Scene()
    mesh = scene.mesh
    verts = []
    for i in range(6):
        angle = math.pi / 3.0 * i
        verts.append(mesh.add_vertex((math.cos(angle), math.sin(angle), 0.0)))
    face = mesh.add_face(verts)
    return scene, verts, face


# ---------------------------------------------------------------------------
# 1. resolve_c_context dispatch
# ---------------------------------------------------------------------------

class TestResolveCContext:
    def _sel(self, mode: SelectionMode, edge_ids=(), vertex_ids=()):
        sel = Selection()
        sel.mode = mode
        sel.edges = set(edge_ids)
        sel.vertices = set(vertex_ids)
        return sel

    def test_empty_edge_mode_gives_knife(self):
        sel = self._sel(SelectionMode.EDGE)
        assert resolve_c_context(sel) is CContext.KNIFE

    def test_empty_vertex_mode_gives_knife(self):
        sel = self._sel(SelectionMode.VERTEX)
        assert resolve_c_context(sel) is CContext.KNIFE

    def test_empty_face_mode_gives_knife(self):
        sel = self._sel(SelectionMode.FACE)
        assert resolve_c_context(sel) is CContext.KNIFE

    def test_one_edge_gives_split(self):
        sel = self._sel(SelectionMode.EDGE, edge_ids=[object()])
        assert resolve_c_context(sel) is CContext.SPLIT

    def test_two_edges_gives_edge_connect(self):
        sel = self._sel(SelectionMode.EDGE, edge_ids=[object(), object()])
        assert resolve_c_context(sel) is CContext.EDGE_CONNECT

    def test_three_edges_gives_edge_connect(self):
        sel = self._sel(SelectionMode.EDGE, edge_ids=[object(), object(), object()])
        assert resolve_c_context(sel) is CContext.EDGE_CONNECT

    def test_two_vertices_gives_vertex_connect(self):
        sel = self._sel(SelectionMode.VERTEX, vertex_ids=[object(), object()])
        assert resolve_c_context(sel) is CContext.VERTEX_CONNECT

    def test_one_vertex_gives_none(self):
        sel = self._sel(SelectionMode.VERTEX, vertex_ids=[object()])
        assert resolve_c_context(sel) is CContext.NONE

    def test_faces_selected_gives_none(self):
        sel = self._sel(SelectionMode.FACE)
        sel.faces = {object(), object()}
        # is_empty() checks all sets; since faces are not checked by is_empty
        # and mode is FACE but we don't handle it, result is NONE
        # (is_empty checks all three: vertices, edges, faces)
        # After adding faces, is_empty returns False → not KNIFE
        # mode is FACE, not EDGE or VERTEX → NONE
        assert resolve_c_context(sel) is CContext.NONE


# ---------------------------------------------------------------------------
# 2. resolve_point
# ---------------------------------------------------------------------------

class TestResolvePoint:
    def test_vertex_point_returns_vertex_id(self):
        scene, (v0, v1, v2, v3), face = _quad_scene()
        pt = VertexPoint(vertex_id=v0)
        result = resolve_point(scene.mesh, pt)
        assert result == v0

    def test_edge_point_splits_and_returns_new_vertex(self):
        scene, (v0, v1, v2, v3), face = _quad_scene()
        mesh = scene.mesh
        eid = mesh._get_or_create_edge(v0, v1)
        pt = EdgePoint(edge_id=eid, t=0.25)
        new_vid = resolve_point(mesh, pt)
        assert mesh.is_valid_vertex(new_vid)
        p = mesh.vertex_position(new_vid)
        p0 = mesh.vertex_position(v0)
        p1 = mesh.vertex_position(v1)
        expected = tuple(a * 0.75 + b * 0.25 for a, b in zip(p0, p1))
        assert p == expected
        assert_mesh_invariants(mesh, context="resolve_point EdgePoint")


# ---------------------------------------------------------------------------
# 3. connect_in_shared_face
# ---------------------------------------------------------------------------

class TestConnectInSharedFace:
    def test_non_adjacent_in_shared_face_creates_edge(self):
        scene, (v0, v1, v2, v3), face = _quad_scene()
        mesh = scene.mesh
        eid = connect_in_shared_face(mesh, v0, v2)
        assert eid is not None
        assert mesh.is_valid_edge(eid)
        assert_mesh_invariants(mesh, context="connect_in_shared_face basic")

    def test_adjacent_vertices_return_none(self):
        scene, (v0, v1, v2, v3), face = _quad_scene()
        mesh = scene.mesh
        # v0 and v1 are adjacent in the quad
        result = connect_in_shared_face(mesh, v0, v1)
        assert result is None

    def test_no_shared_face_returns_none(self):
        """Two isolated vertices with no shared face."""
        scene = Scene()
        mesh = scene.mesh
        v0 = mesh.add_vertex((0.0, 0.0, 0.0))
        v1 = mesh.add_vertex((1.0, 0.0, 0.0))
        # No face added — they share no face
        result = connect_in_shared_face(mesh, v0, v1)
        assert result is None

    def test_two_qualifying_faces_uses_lowest_face_id(self):
        """When two faces both qualify, the lowest FaceId is used."""
        scene = Scene()
        mesh = scene.mesh
        # Pentagon: v0-v1-v2-v3-v4; v0 and v2 are non-adjacent (dist=2)
        # Then split the pentagon to create a second face also containing v0 and v2
        # Actually, easier: build two separate quads that share v0 and v2 (as inner verts)
        # Build a 6-vertex cross-face structure where v0 and v2 appear in two quads
        # Simpler: build 2 quads where the same two non-adjacent verts appear in both
        #
        # Quad 1: v0, v1, v2, v3   (v0 and v2 non-adjacent, dist=2)
        # Quad 2: v0, v4, v2, v5   (v0 and v2 non-adjacent, dist=2)
        v0 = mesh.add_vertex((0.0, 0.0, 0.0))
        v1 = mesh.add_vertex((1.0, 0.0, 0.0))
        v2 = mesh.add_vertex((1.0, 1.0, 0.0))
        v3 = mesh.add_vertex((0.0, 1.0, 0.0))
        v4 = mesh.add_vertex((2.0, 0.0, 0.0))
        v5 = mesh.add_vertex((2.0, 1.0, 0.0))
        f1 = mesh.add_face([v0, v1, v2, v3])
        f2 = mesh.add_face([v0, v4, v2, v5])
        # Both f1 and f2 contain v0 and v2; v0 and v2 are non-adjacent in both (dist=2)
        # The lowest FaceId should be chosen
        assert int(f1) < int(f2)
        eid = connect_in_shared_face(mesh, v0, v2)
        assert eid is not None
        assert mesh.is_valid_edge(eid)
        # After connecting, f1 (lowest) should be the one that was split
        assert not mesh.is_valid_face(f1)  # f1 was the target, now split
        assert mesh.is_valid_face(f2)       # f2 was untouched
        assert_mesh_invariants(mesh, context="connect_in_shared_face lowest FaceId")


# ---------------------------------------------------------------------------
# 4. Split residue (§1.3, D-S)
# ---------------------------------------------------------------------------

class TestSplitResidue:
    """Verify that split_selected_edge returns the new vertex, and that the
    window wiring would switch to Vertex mode and select it.
    The window logic itself is tested by integration; here we verify the
    return value contract of split_selected_edge."""

    def test_split_returns_new_vertex_id(self):
        app = PlaygroundApp()
        app.load_grid()
        mesh = app.scene.mesh
        sel = app.scene.selection
        sel.mode = SelectionMode.EDGE
        eid = next(iter(mesh.all_edge_ids()))
        before_verts = set(mesh.all_vertex_ids())
        new_vid, ea, eb = split_selected_edge(app.scene, eid)
        after_verts = set(mesh.all_vertex_ids())
        assert new_vid in after_verts - before_verts
        assert mesh.is_valid_vertex(new_vid)
        assert mesh.is_valid_edge(ea)
        assert mesh.is_valid_edge(eb)

    def test_split_residue_applies_vertex_mode_and_selection(self):
        """Simulate what window.py does: switch to Vertex mode, select new vertex."""
        app = PlaygroundApp()
        app.load_grid()
        mesh = app.scene.mesh
        sel = app.scene.selection
        sel.mode = SelectionMode.EDGE
        sel.clear()
        eid = next(iter(mesh.all_edge_ids()))
        sel.add({eid})

        # Simulate the window's C→SPLIT handler
        (edge_id,) = sel.edges
        new_vid, _, _ = split_selected_edge(app.scene, edge_id)
        sel.mode = SelectionMode.VERTEX
        sel.clear()
        sel.add({new_vid})

        assert sel.mode is SelectionMode.VERTEX
        assert sel.vertices == {new_vid}
        assert mesh.is_valid_vertex(new_vid)
