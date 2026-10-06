"""Application: Delete / Dissolve (WP Delete/Dissolve,
docs/WP_DELETE_DISSOLVE_PLAN.md).

Headless (TraceStore), kein pyglet/Fenster. Pfad: Entf / Rücktaste /
Ctrl+Rücktaste → `Application.key_press` → `dispatch_command(DELETE /
DISSOLVE / DISSOLVE_NO_CLEANUP)` → `_removal_command()` →
`mirai.topology.delete_dissolve.remove_selected` → Core-Primitive.

Analog zu den `C`-Kontext-Tests (`test_application_contextual_c.py`): ein Test
pro Tasten-/Modus-Kombination, je genau ein History-Eintrag pro Erfolg, Mesh
und History unverändert bei Ablehnung/No-op.
"""

from __future__ import annotations

import json

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


DELETE = _key("delete")
BACKSPACE = _key("backspace")
CTRL_BACKSPACE = _key("backspace", "ctrl")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")


def _build_grid(n: int) -> Mesh:
    mesh = Mesh()
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


def _app(n: int | None = None, keymap_path=None) -> Application:
    """Cube app, or an n×n grid loaded into the cube app (as in the C tests)."""
    app = Application(keymap_path=keymap_path)
    app.init_scene("cube")
    if n is not None:
        app.scene.mesh.load_state(_build_grid(n).export_state())
        app.viewport.on_topology_changed()
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


@pytest.fixture
def app() -> Application:
    return _app()


def _grid_vertex(app, r, c):
    mesh = app.scene.mesh
    return next(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (float(c), float(r)))


def _grid_face(app, r, c):
    mesh = app.scene.mesh
    corner = _grid_vertex(app, r, c)
    return next(
        f for f in mesh.all_face_ids()
        if min(mesh.vertex_position(v)[:2] for v in mesh.face_vertices(f)) == (float(c), float(r))
        and corner in mesh.face_vertices(f)
    )


def _edge(mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def _select(app, mode: SelectionMode, ids) -> None:
    sel = app.scene.selection
    sel.mode = mode
    sel.clear()
    sel.add(set(ids))


def _sizes(mesh) -> list[int]:
    return sorted(len(mesh.face_vertices(f)) for f in mesh.all_face_ids())


def _topology(mesh) -> dict:
    """`export_state()` ohne die monotonen ID-Zähler (AD-001)."""
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}


def _assert_untouched(app, inp: Input) -> None:
    mesh = app.scene.mesh
    before_state = mesh.export_state()
    before_hist = len(app.history)
    before_sel = app._selection_snapshot()
    assert app.key_press(inp) is False
    assert mesh.export_state() == before_state
    assert len(app.history) == before_hist
    assert app._selection_snapshot() == before_sel


def _press_succeeds(app, inp: Input) -> None:
    before_hist = len(app.history)
    assert app.key_press(inp) is True
    assert len(app.history) == before_hist + 1
    assert_mesh_invariants(app.scene.mesh)
    app.update_viewport(0.0)  # Render-Pfad verkraftet die entfernten IDs


# ---------------------------------------------------------------------------
# 1. Bindings (Artist Input Truth, PROVISIONAL)
# ---------------------------------------------------------------------------

def test_default_bindings(app):
    assert app.bindings.command_for(DELETE) == cmd.DELETE
    assert app.bindings.command_for(BACKSPACE) == cmd.DISSOLVE
    assert app.bindings.command_for(CTRL_BACKSPACE) == cmd.DISSOLVE_NO_CLEANUP


def test_cleanup_variant_is_pure_binding_config(tmp_path):
    """§0.2.2: welche Variante auf der einfachen Taste liegt, ist reine
    Bindungs-Config - vertauscht über keymap.json, ohne Code-Änderung."""
    path = tmp_path / "keymap.json"
    path.write_text(json.dumps({
        "schemaVersion": 1,
        "bindings": [
            {"context": "global", "input": {"kind": "key", "value": "backspace", "modifiers": []},
             "command": cmd.DISSOLVE_NO_CLEANUP},
            {"context": "global", "input": {"kind": "key", "value": "backspace", "modifiers": ["ctrl"]},
             "command": cmd.DISSOLVE},
        ],
    }), encoding="utf-8")
    app = _app(keymap_path=path)
    mesh = app.scene.mesh
    _select(app, SelectionMode.EDGE, [mesh.all_edge_ids()[0]])
    _press_succeeds(app, BACKSPACE)
    assert len(mesh.all_vertex_ids()) == 8  # ohne Cleanup
    assert app.status_message == "Dissolve Edges (no cleanup)"


# ---------------------------------------------------------------------------
# 2. Delete × Vertex / Edge / Face
# ---------------------------------------------------------------------------

def test_delete_vertex(app):
    mesh = app.scene.mesh
    v = mesh.all_vertex_ids()[0]
    _select(app, SelectionMode.VERTEX, [v])
    _press_succeeds(app, DELETE)
    assert not mesh.is_valid_vertex(v)
    assert len(mesh.all_face_ids()) == 3
    assert app.scene.selection.is_empty()
    assert app.scene.selection.mode is SelectionMode.VERTEX
    assert app.status_message == "Delete Vertices"


def test_delete_edge(app):
    mesh = app.scene.mesh
    e = mesh.all_edge_ids()[0]
    _select(app, SelectionMode.EDGE, [e])
    _press_succeeds(app, DELETE)
    assert not mesh.is_valid_edge(e)
    assert len(mesh.all_face_ids()) == 4
    assert app.status_message == "Delete Edges"


def test_delete_face_single_and_region_on_2x2_grid():
    """Praxis-Szenario 2×2-Grid als Test (Regel präzisiert Manu 2026-10-06):
    face-los gewordene Edges und kantenlose Vertices gehen mit, Edges an einer
    verbleibenden Face bleiben."""
    app = _app(2)
    mesh = app.scene.mesh
    _select(app, SelectionMode.FACE, [_grid_face(app, 0, 0)])
    _press_succeeds(app, DELETE)
    assert (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())) == (8, 10, 3)
    assert app.status_message == "Delete Faces"

    app.key_press(CTRL_Z)
    kept = {
        _edge(mesh, _grid_vertex(app, 1, 0), _grid_vertex(app, 1, 1)),
        _edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2)),
    }
    _select(app, SelectionMode.FACE, [_grid_face(app, 0, 0), _grid_face(app, 0, 1)])
    _press_succeeds(app, DELETE)
    assert (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())) == (6, 7, 2)
    assert kept <= set(mesh.all_edge_ids())
    assert all(mesh.edge_faces(e) for e in mesh.all_edge_ids())


# ---------------------------------------------------------------------------
# 3. Dissolve: Vertex (eine Operation), Edge/Face je beide Varianten
# ---------------------------------------------------------------------------

def test_vertex_dissolve_backspace(app):
    mesh = app.scene.mesh
    v = mesh.all_vertex_ids()[0]
    _select(app, SelectionMode.VERTEX, [v])
    _press_succeeds(app, BACKSPACE)
    assert not mesh.is_valid_vertex(v)
    assert _sizes(mesh) == [4, 4, 4, 6]
    assert app.scene.selection.is_empty()
    assert app.status_message == "Dissolve Vertices"


def test_vertex_dissolve_ctrl_backspace_has_no_effect(app):
    mesh = app.scene.mesh
    _select(app, SelectionMode.VERTEX, [mesh.all_vertex_ids()[0]])
    _assert_untouched(app, CTRL_BACKSPACE)
    assert app.status_message == "Dissolve (no cleanup): no variant in Vertex mode"


def test_vertex_dissolve_several_vertices_one_history_entry():
    app = _app(3)
    mesh = app.scene.mesh
    _select(app, SelectionMode.VERTEX, [_grid_vertex(app, 1, 1), _grid_vertex(app, 2, 2)])
    _press_succeeds(app, BACKSPACE)
    assert len(mesh.all_vertex_ids()) == 14


@pytest.mark.parametrize("inp, vertices, sizes, label", [
    (BACKSPACE, 6, [3, 3, 4, 4, 4], "Dissolve Edges"),
    (CTRL_BACKSPACE, 8, [4, 4, 4, 4, 6], "Dissolve Edges (no cleanup)"),
])
def test_edge_dissolve_both_variants(app, inp, vertices, sizes, label):
    mesh = app.scene.mesh
    _select(app, SelectionMode.EDGE, [mesh.all_edge_ids()[0]])
    _press_succeeds(app, inp)
    assert len(mesh.all_vertex_ids()) == vertices
    assert _sizes(mesh) == sizes
    assert app.scene.selection.is_empty()
    assert app.scene.selection.mode is SelectionMode.EDGE
    assert app.status_message == label


@pytest.mark.parametrize("inp, vertices, sizes, label", [
    (BACKSPACE, 6, [3, 3, 4, 4, 4], "Dissolve Faces"),
    (CTRL_BACKSPACE, 8, [4, 4, 4, 4, 6], "Dissolve Faces (no cleanup)"),
])
def test_face_dissolve_both_variants(app, inp, vertices, sizes, label):
    mesh = app.scene.mesh
    pair = mesh.edge_faces(mesh.all_edge_ids()[0])
    _select(app, SelectionMode.FACE, pair)
    _press_succeeds(app, inp)
    assert len(mesh.all_vertex_ids()) == vertices
    assert _sizes(mesh) == sizes
    # Residue: die verschmolzene Face ist ausgewählt.
    (merged,) = app.scene.selection.faces
    assert mesh.is_valid_face(merged) and merged not in pair
    assert app.status_message == label


def test_edge_dissolve_3x3_loop_one_by_one_gives_pure_quads():
    """Praxis-Szenario Streifen/Loop: Backspace auf jeder Kante eines Loops
    nacheinander → reine Quads."""
    app = _app(3)
    mesh = app.scene.mesh
    for r in range(3):
        e = _edge(mesh, _grid_vertex(app, r, 1), _grid_vertex(app, r + 1, 1))
        _select(app, SelectionMode.EDGE, [e])
        _press_succeeds(app, BACKSPACE)
    assert _sizes(mesh) == [4] * 6
    assert len(app.history) == 3


# ---------------------------------------------------------------------------
# 4. Ablehnung / No-op: Mesh, History und Auswahl unverändert
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("inp", [DELETE, BACKSPACE, CTRL_BACKSPACE])
@pytest.mark.parametrize("mode", [SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE])
def test_empty_selection_is_no_op(app, inp, mode):
    _select(app, mode, [])
    _assert_untouched(app, inp)
    assert app.status_message.endswith("nothing selected")


def test_border_edge_dissolve_is_refused():
    app = _app(2)
    mesh = app.scene.mesh
    border = _edge(mesh, _grid_vertex(app, 0, 0), _grid_vertex(app, 0, 1))
    _select(app, SelectionMode.EDGE, [border])
    _assert_untouched(app, BACKSPACE)
    assert app.status_message.startswith("Dissolve Edges: ")


def test_vertex_dissolve_refusal_in_a_later_step_restores_everything():
    """Mehrschritt-Fall: der zweite Vertex ist nicht auflösbar (Wire-Ende) →
    auch der erste, schon aufgelöste wird zurückgenommen."""
    app = _app(2)
    mesh = app.scene.mesh
    lone = mesh.add_vertex((5.0, 5.0, 0.0))
    mesh.add_edge(_grid_vertex(app, 2, 2), lone)
    _select(app, SelectionMode.VERTEX, [_grid_vertex(app, 1, 1), lone])
    before = _topology(mesh)
    before_hist = len(app.history)
    assert app.key_press(BACKSPACE) is False
    assert _topology(mesh) == before
    assert len(app.history) == before_hist


def test_face_dissolve_of_a_single_face_is_no_op(app):
    mesh = app.scene.mesh
    _select(app, SelectionMode.FACE, [mesh.all_face_ids()[0]])
    _assert_untouched(app, BACKSPACE)
    assert app.status_message == "Dissolve Faces: nothing to do"


@pytest.mark.parametrize("transform_key", ["w", "e", "r"])
@pytest.mark.parametrize("inp", [DELETE, BACKSPACE, CTRL_BACKSPACE])
def test_ignored_while_transform_armed(app, transform_key, inp):
    mesh = app.scene.mesh
    _select(app, SelectionMode.FACE, mesh.edge_faces(mesh.all_edge_ids()[0]))
    assert app.key_press(_key(transform_key)) is True
    before_state = mesh.export_state()
    before_hist = len(app.history)
    assert app.key_press(inp) is False
    assert mesh.export_state() == before_state
    assert len(app.history) == before_hist


@pytest.mark.parametrize("inp", [DELETE, BACKSPACE, CTRL_BACKSPACE])
def test_ignored_during_knife_session(app, inp):
    app.scene.selection.clear()
    assert app.key_press(_key("c")) is True
    assert app.knife_active
    state = app.scene.mesh.export_state()
    assert app.key_press(inp) is False
    assert app.scene.mesh.export_state() == state
    assert app.knife_active


# ---------------------------------------------------------------------------
# 5. Undo / Redo: Mesh und Auswahl
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode, inp", [
    (SelectionMode.VERTEX, DELETE),
    (SelectionMode.EDGE, DELETE),
    (SelectionMode.FACE, DELETE),
    (SelectionMode.VERTEX, BACKSPACE),
    (SelectionMode.EDGE, BACKSPACE),
    (SelectionMode.EDGE, CTRL_BACKSPACE),
    (SelectionMode.FACE, BACKSPACE),
    (SelectionMode.FACE, CTRL_BACKSPACE),
])
def test_undo_redo_restores_mesh_and_selection(app, mode, inp):
    mesh = app.scene.mesh
    ids = {
        SelectionMode.VERTEX: [mesh.all_vertex_ids()[0]],
        SelectionMode.EDGE: [mesh.all_edge_ids()[0]],
        SelectionMode.FACE: mesh.edge_faces(mesh.all_edge_ids()[0]),
    }[mode]
    _select(app, mode, ids)
    sel_before = app._selection_snapshot()
    before = _topology(mesh)

    _press_succeeds(app, inp)
    after = _topology(mesh)
    sel_after = app._selection_snapshot()

    assert app.key_press(CTRL_Z) is True
    assert _topology(mesh) == before
    assert app._selection_snapshot() == sel_before
    app.update_viewport(0.0)

    assert app.key_press(CTRL_Y) is True
    assert _topology(mesh) == after
    assert app._selection_snapshot() == sel_after
    app.update_viewport(0.0)


def test_hovered_element_removed_does_not_crash_the_render_path(app):
    mesh = app.scene.mesh
    face = mesh.all_face_ids()[0]
    _select(app, SelectionMode.FACE, [face])
    app.scene.selection.hovered = face
    _press_succeeds(app, DELETE)
    assert not mesh.is_valid_face(face)
