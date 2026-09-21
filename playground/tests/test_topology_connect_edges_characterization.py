"""CHARACTERIZATION tests for Connect Edges (headless, no GL, no window).

These tests pin the CURRENT behavior of
``playground/topology_tools/connect_edges.py`` as of 2026-09-21.
They document limitations found in practice — they are NOT a statement
of desired behavior.

If the Connect semantics are changed deliberately (see
``docs/research/topology/CONNECT_EDGES_SPEC.md`` §11 and
``docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md``), the affected
tests here must be updated in the same change, together with the spec.
A failing test here therefore means "behavior changed" — not
automatically "bug".

Findings pinned here:
  F1  A partial connect ending inside the mesh leaves 2 pentagons.
  F2  Connect refuses any edge adjacent to a non-quad face, so the
      pentagons from F1 block every follow-up connect at that spot.
  F3  Corner connect (two adjacent edges of one face) is rejected.
  F4  A turning path (selection bends by 90°) is rejected.
  F5  Two edges with one quad gap are rejected.
  F6  Boundary-to-boundary / full ring works and yields only quads.
  F7  "kind v" (two collinear edges through a regular vertex) creates a
      free edge that lies geometrically ON TOP of existing edges and
      splits no face.
  F8  Rejections leave mesh and history unchanged.
  F10 All four edges of one quad: the planned "+" cross fails with an
      internal message (second pair targets a face that no longer exists).
  F9  The Core primitives (split_edge + connect_vertices) CAN perform a
      corner cut and resolve a pentagon — the limits above live in the
      playground tool layer, not in src/core.
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
_RIGGING = _REPO_ROOT / "experiments" / "rigging-skinning-morphing"
for _p in (str(_REPO_SRC), str(_REPO_ROOT), str(_RIGGING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from core import Mesh  # noqa: E402
from playground.app import PlaygroundApp  # noqa: E402
from playground.topology_tools.connect_edges import (  # noqa: E402
    connect_selected_edges,
    TopologyToolError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grid(n: int = 4) -> tuple[Mesh, dict]:
    """(n+1)x(n+1) vertex grid in the XY plane -> n*n quads, open boundary."""
    mesh = Mesh()
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh, p


def _edge(mesh: Mesh, a, b):
    for eid in mesh.all_edge_ids():
        if set(mesh.edge_vertices(eid)) == {a, b}:
            return eid
    raise AssertionError(f"no edge between {a!r} and {b!r}")


def _face_sizes(mesh: Mesh) -> dict[int, int]:
    return dict(collections.Counter(len(mesh.face_vertices(f)) for f in mesh.all_face_ids()))


def _free_edges(mesh: Mesh) -> list:
    return [e for e in mesh.all_edge_ids() if len(mesh.edge_faces(e)) == 0]


def _scene_with(mesh: Mesh):
    app = PlaygroundApp()
    app.scene.mesh.load_state(mesh.export_state())
    return app.scene


def _history_len(scene) -> int:
    history = scene.history
    for attr in ("undo_stack", "_undo_stack", "_undo"):
        stack = getattr(history, attr, None)
        if stack is not None:
            return len(stack)
    if hasattr(history, "can_undo"):
        return 1 if history.can_undo() else 0
    pytest.skip("history length not introspectable")


def _setup(edges_fn):
    mesh, p = _grid()
    scene = _scene_with(mesh)
    m = scene.mesh
    return scene, m, edges_fn(m, p), p


# ---------------------------------------------------------------------------
# F1 / F2 — partial connect leaves pentagons that block follow-up work
# ---------------------------------------------------------------------------

def test_f1_partial_connect_leaves_two_pentagons():
    scene, m, edges, _ = _setup(lambda m, p: {
        _edge(m, p[(1, 1)], p[(2, 1)]),
        _edge(m, p[(1, 2)], p[(2, 2)]),
    })
    connect_selected_edges(scene, edges)
    assert _face_sizes(m) == {4: 15, 5: 2}


def test_f2_followup_connect_next_to_pentagon_is_rejected():
    scene, m, edges, p = _setup(lambda m, p: {
        _edge(m, p[(1, 1)], p[(2, 1)]),
        _edge(m, p[(1, 2)], p[(2, 2)]),
    })
    connect_selected_edges(scene, edges)

    # Continue the cut one quad further to the right: one half of the
    # previously split edge + the next vertical edge.
    half = next(
        e for e in m.all_edge_ids()
        if p[(1, 2)] in m.edge_vertices(e)
        and any(abs(m.vertex_position(v)[1] - 1.5) < 1e-9 for v in m.edge_vertices(e))
    )
    nxt = _edge(m, p[(1, 3)], p[(2, 3)])
    before = m.export_state()
    with pytest.raises(TopologyToolError, match="Nicht-Quadrat"):
        connect_selected_edges(scene, {half, nxt})
    assert m.export_state() == before


# ---------------------------------------------------------------------------
# F3 / F4 / F5 — selections the tool cannot interpret
# ---------------------------------------------------------------------------

def test_f3_corner_connect_is_rejected():
    scene, m, edges, _ = _setup(lambda m, p: {
        _edge(m, p[(1, 1)], p[(1, 2)]),
        _edge(m, p[(1, 2)], p[(2, 2)]),
    })
    with pytest.raises(TopologyToolError):
        connect_selected_edges(scene, edges)


def test_f4_turning_path_is_rejected():
    scene, m, edges, _ = _setup(lambda m, p: {
        _edge(m, p[(1, 1)], p[(2, 1)]),
        _edge(m, p[(1, 2)], p[(2, 2)]),
        _edge(m, p[(2, 2)], p[(2, 3)]),
    })
    with pytest.raises(TopologyToolError):
        connect_selected_edges(scene, edges)


def test_f5_gap_of_one_quad_is_rejected():
    scene, m, edges, _ = _setup(lambda m, p: {
        _edge(m, p[(1, 1)], p[(2, 1)]),
        _edge(m, p[(1, 3)], p[(2, 3)]),
    })
    with pytest.raises(TopologyToolError):
        connect_selected_edges(scene, edges)


# ---------------------------------------------------------------------------
# F6 — the case that works: boundary to boundary
# ---------------------------------------------------------------------------

def test_f6_boundary_to_boundary_yields_only_quads():
    scene, m, edges, _ = _setup(lambda m, p: {
        _edge(m, p[(1, c)], p[(2, c)]) for c in range(5)
    })
    new = connect_selected_edges(scene, edges)
    assert len(new) == 4
    assert _face_sizes(m) == {4: 20}
    assert not _free_edges(m)


# ---------------------------------------------------------------------------
# F7 — "kind v" produces a degenerate free edge
# ---------------------------------------------------------------------------

def test_f7_kind_v_free_edge_is_collinear_and_splits_no_face():
    scene, m, edges, p = _setup(lambda m, p: {
        _edge(m, p[(2, 1)], p[(2, 2)]),
        _edge(m, p[(2, 2)], p[(2, 3)]),
    })
    faces_before = len(list(m.all_face_ids()))
    connect_selected_edges(scene, edges)

    free = _free_edges(m)
    assert len(free) == 1
    a, b = (m.vertex_position(v) for v in m.edge_vertices(free[0]))
    # Both endpoints lie on the line y == 2 (the existing edge line) ...
    assert a[1] == pytest.approx(2.0) and b[1] == pytest.approx(2.0)
    # ... and the free edge passes through the shared vertex p(2,2).
    xs = sorted((a[0], b[0]))
    assert xs[0] < m.vertex_position(p[(2, 2)])[0] < xs[1]
    # No face was split; the 4 faces around the two edges became pentagons.
    assert len(list(m.all_face_ids())) == faces_before
    assert _face_sizes(m) == {4: 12, 5: 4}


# ---------------------------------------------------------------------------
# F8 — rejections are atomic
# ---------------------------------------------------------------------------

def test_f8_rejection_leaves_mesh_and_history_unchanged():
    scene, m, edges, _ = _setup(lambda m, p: {
        _edge(m, p[(1, 1)], p[(1, 2)]),
        _edge(m, p[(1, 2)], p[(2, 2)]),
    })
    state = m.export_state()
    hist = _history_len(scene)
    with pytest.raises(TopologyToolError):
        connect_selected_edges(scene, edges)
    assert m.export_state() == state
    assert _history_len(scene) == hist


# ---------------------------------------------------------------------------
# F9 — the Core primitives are capable of what the tool refuses
# ---------------------------------------------------------------------------

def _face_with(m: Mesh, *vs):
    return next(f for f in m.all_face_ids() if all(v in m.face_vertices(f) for v in vs))


def test_f9_core_can_corner_cut():
    m, p = _grid()
    ma, _, _ = m.split_edge(_edge(m, p[(1, 1)], p[(1, 2)]))
    mb, _, _ = m.split_edge(_edge(m, p[(1, 2)], p[(2, 2)]))
    m.connect_vertices(_face_with(m, ma, mb), ma, mb)
    assert _face_sizes(m) == {3: 1, 4: 13, 5: 3}


def test_f9_core_can_resolve_pentagon():
    m, p = _grid()
    a, _, _ = m.split_edge(_edge(m, p[(1, 1)], p[(2, 1)]))
    b, _, _ = m.split_edge(_edge(m, p[(1, 2)], p[(2, 2)]))
    m.connect_vertices(_face_with(m, a, b), a, b)
    pent = next(f for f in m.all_face_ids() if len(m.face_vertices(f)) == 5 and b in m.face_vertices(f))
    vs = m.face_vertices(pent)
    far = vs[(vs.index(b) + 2) % 5]
    m.connect_vertices(pent, b, far)
    assert _face_sizes(m) == {3: 1, 4: 16, 5: 1}


# ---------------------------------------------------------------------------
# F10 — all four edges of one quad: planned "+" cross fails internally
# ---------------------------------------------------------------------------

def test_f10_all_four_edges_of_a_quad_fail_with_internal_message():
    scene, m, edges, _ = _setup(lambda m, p: {
        _edge(m, p[(1, 1)], p[(1, 2)]),
        _edge(m, p[(1, 2)], p[(2, 2)]),
        _edge(m, p[(2, 2)], p[(2, 1)]),
        _edge(m, p[(2, 1)], p[(1, 1)]),
    })
    state = m.export_state()
    with pytest.raises(TopologyToolError, match="Operationsplan nicht auf gültige Topologie abbildbar"):
        connect_selected_edges(scene, edges)
    assert m.export_state() == state
