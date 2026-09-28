"""Application: Contextual C — Split / Edge Connect / Vertex Connect (WP-06
Slice B6, AD-017).

Headless (TraceStore), kein pyglet/Fenster. Pfad: `C` → `Application.
key_press` → `dispatch_command(CONNECT)` → `_connect_command()` →
`resolve_c_context(selection)` (`mirai.topology.contextual_c`) → Split /
Edge Connect / Vertex Connect (`mirai.topology.split` /
`mirai.topology.connect_per_face` / `mirai.topology.connect_vertices_
per_face`) — dieselbe Implementierung, die auch der Playground importiert
(kein zweiter Codepfad).

Knife (leere Auswahl) ist in B6 nicht gebaut: No-op mit eigener Statuszeile,
siehe `test_empty_selection_is_knife_noop`.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from core.mesh import Mesh
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from tests.mesh_invariants import assert_mesh_invariants

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


C = _key("c")
W, E, R = _key("w"), _key("e"), _key("r")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _edge(mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def _vertex_by_position(mesh, index: int):
    """Cube vertex by `scene_factory.create_cube` construction order (0-7)."""
    return sorted(mesh.all_vertex_ids(), key=int)[index]


def _topology(mesh) -> dict:
    """`mesh.export_state()` without the monotonic ID counters (AD-001: a
    counter only ever moves forward — `IdAllocator.restore_counter` — so it
    legitimately stays higher after Undo than it was pre-op; see
    `playground/tests/test_connect_lab.py::_topology` for the same pattern)."""
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}


# ---------------------------------------------------------------------------
# 1. Split — Edge mode, 1 edge
# ---------------------------------------------------------------------------

def test_split_edge_one_edge(app):
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    v0, v1 = _vertex_by_position(mesh, 0), _vertex_by_position(mesh, 1)
    eid = _edge(mesh, v0, v1)
    sel.clear()
    sel.add({eid})

    before_verts = set(mesh.all_vertex_ids())
    before_hist = len(app.history)

    assert app.key_press(C) is True

    after_verts = set(mesh.all_vertex_ids())
    new_verts = after_verts - before_verts
    assert len(new_verts) == 1
    (new_vid,) = new_verts

    # Residue (AD-017 §1.3, D-S): new vertex selected, mode → Vertex.
    assert sel.mode is SelectionMode.VERTEX
    assert sel.vertices == {new_vid}
    assert app.status_message == "Split"
    assert len(app.history) == before_hist + 1
    assert_mesh_invariants(mesh, context="split via C")


def test_split_undo_redo_roundtrip(app):
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    v0, v1 = _vertex_by_position(mesh, 0), _vertex_by_position(mesh, 1)
    eid = _edge(mesh, v0, v1)
    sel.add({eid})

    before = _topology(mesh)
    app.key_press(C)
    after = _topology(mesh)
    assert after != before

    app.dispatch_command(cmd.UNDO)
    assert _topology(mesh) == before
    assert app.history.can_redo()

    app.dispatch_command(cmd.REDO)
    assert _topology(mesh) == after


# ---------------------------------------------------------------------------
# 2. Edge Connect — Edge mode, 2+ edges
# ---------------------------------------------------------------------------

def test_edge_connect_two_edges_same_face(app):
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    # "hinten" face (3,2,1,0): opposite, non-adjacent edges 3-2 and 1-0.
    v0, v1, v2, v3 = (_vertex_by_position(mesh, i) for i in range(4))
    e_32 = _edge(mesh, v3, v2)
    e_10 = _edge(mesh, v1, v0)
    sel.clear()
    sel.add({e_32, e_10})

    before_hist = len(app.history)
    before_edges = set(mesh.all_edge_ids())

    assert app.key_press(C) is True

    # 2 splits (each 1 old id -> 2 new ids) + 1 connecting edge = 5 new ids;
    # only the connecting edge is the residue (AD-017), not the split remnants.
    new_edges = set(mesh.all_edge_ids()) - before_edges
    assert len(new_edges) == 5
    assert sel.mode is SelectionMode.EDGE
    assert len(sel.edges) == 1
    assert sel.edges <= new_edges
    assert app.status_message == "Connect Edges"
    assert len(app.history) == before_hist + 1
    assert_mesh_invariants(mesh, context="edge connect via C")


def test_edge_connect_undo_redo_roundtrip(app):
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    v0, v1, v2, v3 = (_vertex_by_position(mesh, i) for i in range(4))
    sel.add({_edge(mesh, v3, v2), _edge(mesh, v1, v0)})

    before = _topology(mesh)
    app.key_press(C)
    after = _topology(mesh)

    app.dispatch_command(cmd.UNDO)
    assert _topology(mesh) == before
    app.dispatch_command(cmd.REDO)
    assert _topology(mesh) == after


def test_edge_connect_rejection_leaves_mesh_and_history_untouched(app):
    """Two edges with no shared face at all (AD-017 §1.4/Connect Lab):
    connect_per_face's "keep" filter drops both -> TopologyToolError,
    mesh restored before the exception. C must surface this as a no-op."""
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    v0, v1 = _vertex_by_position(mesh, 0), _vertex_by_position(mesh, 1)
    v6, v7 = _vertex_by_position(mesh, 6), _vertex_by_position(mesh, 7)
    # {0,1} faces = {hinten, unten}; {6,7} faces = {vorne, oben} — disjoint.
    e_01 = _edge(mesh, v0, v1)
    e_67 = _edge(mesh, v6, v7)
    sel.clear()
    sel.add({e_01, e_67})

    before_state = mesh.export_state()
    before_hist = len(app.history)

    assert app.key_press(C) is False

    assert mesh.export_state() == before_state
    assert len(app.history) == before_hist
    assert sel.edges == {e_01, e_67}
    assert app.status_message  # a reason was set


# ---------------------------------------------------------------------------
# 3. Vertex Connect — Vertex mode, 2+ vertices
# ---------------------------------------------------------------------------

def test_vertex_connect_two_non_adjacent_vertices(app):
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.VERTEX
    # "hinten" face (3,2,1,0): v3 and v1 are diagonal (non-adjacent).
    v3, v1 = _vertex_by_position(mesh, 3), _vertex_by_position(mesh, 1)
    sel.clear()
    sel.add({v3, v1})

    before_hist = len(app.history)
    before_edges = set(mesh.all_edge_ids())

    assert app.key_press(C) is True

    new_edges = set(mesh.all_edge_ids()) - before_edges
    assert len(new_edges) == 1
    # Residue (AD-017): original vertices stay selected, Vertex mode unchanged.
    assert sel.mode is SelectionMode.VERTEX
    assert sel.vertices == {v3, v1}
    assert app.status_message == "Vertex Connect"
    assert len(app.history) == before_hist + 1
    assert_mesh_invariants(mesh, context="vertex connect via C")


def test_vertex_connect_undo_redo_roundtrip(app):
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.VERTEX
    v3, v1 = _vertex_by_position(mesh, 3), _vertex_by_position(mesh, 1)
    sel.add({v3, v1})

    before = _topology(mesh)
    app.key_press(C)
    after = _topology(mesh)

    app.dispatch_command(cmd.UNDO)
    assert _topology(mesh) == before
    app.dispatch_command(cmd.REDO)
    assert _topology(mesh) == after


def test_vertex_connect_adjacent_vertices_no_op(app):
    """v3 and v2 are adjacent on the "hinten" face — nothing connectable."""
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.VERTEX
    v3, v2 = _vertex_by_position(mesh, 3), _vertex_by_position(mesh, 2)
    sel.clear()
    sel.add({v3, v2})

    before_state = mesh.export_state()
    before_hist = len(app.history)

    assert app.key_press(C) is False

    assert mesh.export_state() == before_state
    assert len(app.history) == before_hist
    assert sel.vertices == {v3, v2}
    assert app.status_message == "Vertex Connect: nothing connectable"


# ---------------------------------------------------------------------------
# 4. Knife (empty selection) — not in B6 scope: no-op
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", [SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE])
def test_empty_selection_is_knife_noop(app, mode):
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = mode
    sel.clear()

    before_state = mesh.export_state()
    before_hist = len(app.history)

    assert app.key_press(C) is False

    assert mesh.export_state() == before_state
    assert len(app.history) == before_hist
    assert app.status_message == "C: Knife not available yet"


# ---------------------------------------------------------------------------
# 5. No C meaning (1 vertex, Face mode) — no-op
# ---------------------------------------------------------------------------

def test_one_vertex_selected_is_no_op(app):
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.VERTEX
    v0 = _vertex_by_position(mesh, 0)
    sel.clear()
    sel.add({v0})

    before_state = mesh.export_state()
    before_hist = len(app.history)

    assert app.key_press(C) is False

    assert mesh.export_state() == before_state
    assert len(app.history) == before_hist
    assert sel.vertices == {v0}
    assert app.status_message == "C: nothing to do here"


def test_face_mode_is_no_op(app):
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.FACE
    fid = next(iter(mesh.all_face_ids()))
    sel.clear()
    sel.add({fid})

    before_state = mesh.export_state()
    before_hist = len(app.history)

    assert app.key_press(C) is False

    assert mesh.export_state() == before_state
    assert len(app.history) == before_hist
    assert app.status_message == "C: nothing to do here"


# ---------------------------------------------------------------------------
# 6. C ignored while W/E/R armed (same Session Gate as the mode keys, B5b)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("transform_key", [W, E, R])
def test_connect_ignored_while_transform_armed(app, transform_key):
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    v0, v1 = _vertex_by_position(mesh, 0), _vertex_by_position(mesh, 1)
    eid = _edge(mesh, v0, v1)
    sel.add({eid})

    assert app.key_press(transform_key) is True  # arms Move/Rotate/Scale

    before_state = mesh.export_state()
    before_hist = len(app.history)

    assert app.key_press(C) is False

    assert mesh.export_state() == before_state
    assert len(app.history) == before_hist
    assert sel.mode is SelectionMode.EDGE
    assert sel.edges == {eid}


# ---------------------------------------------------------------------------
# 7. Strip semantics unreachable: the characteristic F-case (Connect Lab F2 /
#    AD-017 §5) where strip and per-face differ gives the per-face result.
# ---------------------------------------------------------------------------

def _build_grid(n: int = 4, size: float = 4.0) -> Mesh:
    """4x4 quad grid (playground.experiments.connect.demo_grid::build_grid,
    reproduced locally — tests/ must not depend on playground/)."""
    mesh = Mesh()
    step = size / n
    half = size / 2.0
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((c * step - half, r * step - half, 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


def _grid_app() -> tuple[Application, dict]:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_build_grid().export_state())
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    mesh = app.scene.mesh
    half = 4 / 2.0
    p = {}
    for v in mesh.all_vertex_ids():
        x, y, _ = mesh.vertex_position(v)
        p[(round(y + half), round(x + half))] = v
    return app, p


def test_edge_connect_reaches_per_face_not_strip():
    """Connect Lab characterization F2 (docs/research/topology/
    CONNECT_NONQUAD_DISCOVERY.md, playground/tests/test_connect_lab.py::
    test_per_face_works_on_pentagon_left_by_previous_partial_connect): after
    a first partial cut leaves a pentagon, the rejected strip baseline
    (`connect_edges.py`) refuses to continue the cut into it, while the
    KEPT per-face variant (`connect_per_face.py`, now `mirai.topology.
    connect_per_face`) accepts it. Only one implementation is reachable
    from Production `C` — this proves it is the per-face one: the second
    cut succeeds instead of being rejected."""
    app, p = _grid_app()
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE

    first = {_edge(mesh, p[(1, 1)], p[(2, 1)]), _edge(mesh, p[(1, 2)], p[(2, 2)])}
    sel.clear()
    sel.add(first)
    assert app.key_press(C) is True
    assert app.status_message == "Connect Edges"

    # Corner cut in the pentagon left behind by the first cut — the strip
    # baseline rejects exactly this step (F2); per-face accepts it.
    top = _edge(mesh, p[(1, 2)], p[(1, 3)])
    right = _edge(mesh, p[(1, 3)], p[(2, 3)])
    sel.clear()
    sel.add({top, right})
    assert app.key_press(C) is True
    assert app.status_message == "Connect Edges"

    assert len(app.history) == 2
    assert_mesh_invariants(mesh, context="pentagon continuation via C")
