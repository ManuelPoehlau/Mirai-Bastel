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

from core import EdgeId, SelectionMode, VertexId
from core.mesh import Mesh
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_nearest_edge
from tests.mesh_invariants import assert_mesh_invariants

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


C = _key("c")
W, E, R = _key("w"), _key("e"), _key("r")
CTRL_Z = _key("z", "ctrl")


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


def _centroid(points) -> tuple[float, float, float]:
    points = list(points)
    return tuple(sum(p[i] for p in points) / len(points) for i in range(3))


def _edge_screen(app, eid) -> tuple[float, float]:
    """Bildposition der Kantenmitte (Projektion, wie in B5b-Tests)."""
    mesh = app.scene.mesh
    midpoint = _centroid(mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
    return app.camera.project_to_screen(midpoint, WIDTH, HEIGHT)


def _pickable_edge(app):
    """Eine Edge, die ein Hover/Klick auf ihre Mitte auch trifft."""
    mesh = app.scene.mesh
    for eid in sorted(mesh.all_edge_ids()):
        if pick_nearest_edge(app.camera, mesh, *_edge_screen(app, eid), WIDTH, HEIGHT) == eid:
            return eid
    raise AssertionError("no pickable edge")


def _pickable_connectable_pair(app):
    """`(gehoverte, partner)`-Edge-Paar für den Edge-Connect-Kontext: die
    erste Edge wird unter dem Cursor wirklich gepickt, und beide teilen eine
    Face, ohne benachbart zu sein (Connect Lab / AD-017 §1.4)."""
    mesh = app.scene.mesh
    for a in sorted(mesh.all_edge_ids()):
        if pick_nearest_edge(app.camera, mesh, *_edge_screen(app, a), WIDTH, HEIGHT) != a:
            continue
        va, vb = mesh.edge_vertices(a)
        faces_a = set(mesh.edge_faces(a))
        for b in sorted(mesh.all_edge_ids()):
            vc, vd = mesh.edge_vertices(b)
            if b == a or {vc, vd} & {va, vb}:
                continue  # benachbart → connect_vertices lehnt ab
            if faces_a & set(mesh.edge_faces(b)):
                return a, b
    raise AssertionError("no pickable connectable edge pair")


def _click(app, inp: Input, pos) -> None:
    app.pointer_press(inp)
    app.pointer_release(inp.value, *pos)


def _highlight_flags(app) -> list[float]:
    return list(app.viewport.render_mesh.store.data("highlight_flags"))


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


# ---------------------------------------------------------------------------
# 8. Hover/Selection nach einer Topologie-Mutation (Praxistest-Bug 2026-09-28)
#
# Praxistest: Edge hovern, anklicken, `C` → Split. `selection.hovered` zeigte
# danach weiter auf die gerade entfernte Edge-ID; der nächste Frame crashte
# beim Aufbau der `highlight_flags` (`KeyError: EdgeId(11)` in
# `mesh.edge_vertices`, aufgerufen aus `RenderMesh._rebuild_resources`).
# Zwei unabhängige Absicherungen werden hier geprüft:
# - Production richtet den Hover nach einer Topologie-Änderung neu aus
#   (`_notify_topology_changed` → `_refresh_hover`),
# - der Viewport überspringt ungültige IDs, statt zu werfen (stale Auswahl
#   bleibt möglich, weil Undo die Selection nicht wiederherstellt).
# ---------------------------------------------------------------------------

def test_split_does_not_leave_the_hovered_edge_stale(app):
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    eid = _pickable_edge(app)

    # Wie im Fenster: Hover entsteht durch die Maus, der Klick wählt genau
    # das gehoverte Element.
    app.pointer_motion(*_edge_screen(app, eid))
    assert sel.hovered == eid
    _click(app, _mouse("LEFT"), _edge_screen(app, eid))
    assert sel.edges == {eid}

    assert app.key_press(C) is True
    assert not mesh.is_valid_edge(eid)

    app.update_viewport(0.0)  # war der Crash (Sync → highlight_flags)

    # Kein stale/wrong-kind Hover: Split setzt den Vertex-Modus, also ist der
    # Hover None oder ein gültiger Vertex — nie die entfernte Edge.
    hovered = sel.hovered
    assert hovered != eid
    assert hovered is None or (
        isinstance(hovered, VertexId) and mesh.is_valid_vertex(hovered)
    )


def test_undo_after_edge_connect_does_not_crash_the_render_path(app):
    """Zweiter Crash-Punkt derselben Klasse: Undo nach Edge Connect entfernte
    ursprünglich die neu entstandenen Edges aus dem Mesh, während die Auswahl
    sie behielt (Undo stellte keine Selection wieder her). Seit dem B6-
    Follow-up (Selection-Restore, `_apply_undo_redo`) stellt Undo die Auswahl
    wieder her, wie sie vor Edge Connect war — die ursprünglich selektierten
    Edges, die das Undo wieder gültig gemacht hat, nicht die (jetzt
    ungültigen) neu entstandenen."""
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    v0, v1, v2, v3 = (_vertex_by_position(mesh, i) for i in range(4))
    original = {_edge(mesh, v3, v2), _edge(mesh, v1, v0)}
    sel.add(set(original))

    assert app.key_press(C) is True
    app.update_viewport(0.0)
    new_edges = set(sel.edges)
    assert new_edges and all(mesh.is_valid_edge(e) for e in new_edges)

    assert app.key_press(CTRL_Z) is True
    assert sel.edges == original  # restored, not left as (pruned) ghosts
    assert all(mesh.is_valid_edge(e) for e in sel.edges)

    app.update_viewport(0.0)  # war die zweite Crash-Stelle (kein Crash mehr)

    # Die wiederhergestellten (wieder gültigen) Edges dürfen als selektiert
    # markiert sein - nur kein ungültiges Handle darf den Sync sprengen.
    assert set(_highlight_flags(app)) <= {0.0, 1.0}


def test_transform_arm_after_undo_of_edge_connect_uses_the_restored_selection(app):
    """Zweiter Fund derselben Klasse (Praxistest, 2026-09-28): `C` →
    Edge Connect → `Ctrl+Z` → `W`. Seit dem B6-Follow-up (Selection-Restore)
    ist die Auswahl nach dem Undo wieder die ursprünglich selektierten,
    jetzt wieder gültigen Edges — `W` scharfschalten arbeitet also normal auf
    ihnen, statt (wie mit reinem Pruning) mangels Auswahl abzulehnen. Kein
    `KeyError`, kein stale Handle."""
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    v0, v1, v2, v3 = (_vertex_by_position(mesh, i) for i in range(4))
    original = {_edge(mesh, v3, v2), _edge(mesh, v1, v0)}
    sel.add(set(original))

    assert app.key_press(C) is True
    assert app.key_press(CTRL_Z) is True
    assert sel.edges == original
    assert all(mesh.is_valid_edge(e) for e in sel.edges)

    assert app.key_press(W) is True
    assert app.transform_command == cmd.MOVE
    expected_target = {v for e in original for v in mesh.edge_vertices(e)}
    assert app.move_target == frozenset(expected_target)


# ---------------------------------------------------------------------------
# 9. Selection restore + ghost-selection pruning after Undo/Redo
#    (WP-06 B6 follow-up, 2026-09-28; Artist-Entscheidung Manu: Undo/Redo
#    restores the Selection, not just the mesh.)
# ---------------------------------------------------------------------------

def test_edge_connect_then_undo_restores_the_original_edges_and_second_c_repeats(app):
    """`C` (Edge Connect) → `Ctrl+Z`: the selection is restored to the
    originally selected (now valid again) edges, contains no invalid edges,
    and a second `C` resolves the same Edge Connect context again — not the
    stale/ghost result the old prune-only fix left behind."""
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    v0, v1, v2, v3 = (_vertex_by_position(mesh, i) for i in range(4))
    original = {_edge(mesh, v3, v2), _edge(mesh, v1, v0)}
    sel.add(set(original))

    assert app.key_press(C) is True
    assert app.key_press(CTRL_Z) is True

    assert sel.edges == original
    assert all(mesh.is_valid_edge(e) for e in sel.edges)

    before_hist = len(app.history)
    assert app.key_press(C) is True
    assert app.status_message == "Connect Edges"
    assert len(app.history) == before_hist + 1


def test_split_undo_redo_leaves_no_invalid_handles_and_restores_selection(app):
    """`C` (Split) → `Ctrl+Z` → `Ctrl+Y`: no invalid handles at any step, and
    the selection at each step matches what it was right before/after Split
    (restore, not just prune)."""
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    v0, v1 = _vertex_by_position(mesh, 0), _vertex_by_position(mesh, 1)
    eid = _edge(mesh, v0, v1)
    sel.add({eid})

    assert app.key_press(C) is True
    after_split_vertices = set(sel.vertices)
    assert all(mesh.is_valid_vertex(v) for v in sel.vertices)

    assert app.key_press(CTRL_Z) is True
    assert sel.mode is SelectionMode.EDGE
    assert sel.edges == {eid}
    assert all(mesh.is_valid_vertex(v) for v in sel.vertices)
    assert all(mesh.is_valid_edge(e) for e in sel.edges)
    assert all(mesh.is_valid_face(f) for f in sel.faces)

    assert app.key_press(_key("y", "ctrl")) is True
    assert sel.mode is SelectionMode.VERTEX
    assert sel.vertices == after_split_vertices
    assert all(mesh.is_valid_vertex(v) for v in sel.vertices)
    assert all(mesh.is_valid_edge(e) for e in sel.edges)
    assert all(mesh.is_valid_face(f) for f in sel.faces)


def test_undo_restores_the_selection_as_of_the_undone_command(app):
    """Undo restores the Selection to what it was immediately before the
    undone command ran — a manual selection change made *after* that command
    (and not itself undone) is not what Undo restores to; it goes back with
    the command whose selection state it overwrote. This is the intended
    restore semantics (Artist decision Manu 2026-09-28), not over-pruning:
    the restored elements themselves are always valid."""
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    v0, v1, v2, v3 = (_vertex_by_position(mesh, i) for i in range(4))
    v6, v7 = _vertex_by_position(mesh, 6), _vertex_by_position(mesh, 7)
    original = {_edge(mesh, v3, v2), _edge(mesh, v1, v0)}
    sel.add(set(original))

    assert app.key_press(C) is True

    # A later, unrelated selection change (Vertex mode) made after Edge
    # Connect but before Undo is not part of that command's history entry.
    sel.mode = SelectionMode.VERTEX
    sel.add({v6, v7})
    assert mesh.is_valid_vertex(v6) and mesh.is_valid_vertex(v7)

    assert app.key_press(CTRL_Z) is True

    # Restored to the pre-Edge-Connect state, not the later manual pick.
    assert sel.mode is SelectionMode.EDGE
    assert sel.edges == original
    assert all(mesh.is_valid_edge(e) for e in sel.edges)


def test_undo_falls_back_to_pruning_when_mesh_was_mutated_outside_application(app):
    """Safety net: if the mesh is ever mutated through a path Application's
    selection-history mirror does not know about (e.g. a future push site
    not yet wired into `_record_selection_history`), Undo/Redo must still
    never leave an invalid handle in `selection` — `_prune_ghost_selection()`
    runs unconditionally after every Undo/Redo, even when nothing was
    restored."""
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    v0, v1, v2, v3 = (_vertex_by_position(mesh, i) for i in range(4))
    sel.add({_edge(mesh, v3, v2), _edge(mesh, v1, v0)})

    assert app.key_press(C) is True  # pushes a real history entry + mirror
    new_edges = set(sel.edges)
    assert new_edges and all(mesh.is_valid_edge(e) for e in new_edges)

    # Simulate a desynced mirror (as if some other path had pushed to
    # history without recording a selection snapshot) - Undo can then only
    # fall back to pruning, not restoring.
    app._selection_undo_stack.clear()

    assert app.key_press(CTRL_Z) is True
    assert not any(mesh.is_valid_edge(e) for e in new_edges)
    assert all(mesh.is_valid_vertex(v) for v in sel.vertices)
    assert all(mesh.is_valid_edge(e) for e in sel.edges)
    assert all(mesh.is_valid_face(f) for f in sel.faces)


def test_edge_connect_reanchors_the_hovered_edge(app):
    """Edge Connect ersetzt ebenfalls die selektierten Edges (samt der
    gehoverten) — der Hover muss danach auf ein existierendes Element zeigen.
    Vertex Connect fügt nur Edges hinzu und kann deshalb keinen stale Hover
    erzeugen; nur der Edge-Connect-Zweig wird hier geprüft."""
    mesh = app.scene.mesh
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    hovered_edge, partner = _pickable_connectable_pair(app)

    app.pointer_motion(*_edge_screen(app, hovered_edge))
    assert sel.hovered == hovered_edge
    sel.set({hovered_edge, partner})

    assert app.key_press(C) is True
    assert app.status_message == "Connect Edges"
    assert not mesh.is_valid_edge(hovered_edge)

    app.update_viewport(0.0)

    hovered = sel.hovered
    assert hovered != hovered_edge
    assert hovered is None or (
        isinstance(hovered, EdgeId) and mesh.is_valid_edge(hovered)
    )
