"""AD-SYM-03 Slice 2: `apply_*` / wrapper equivalence and the Application transaction helper.

Behaviour-preserving refactor: every wrapper still pushes exactly one `MeshStateCommand`, every
Application key-press path still produces exactly one Undo step with its old status texts.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from core.mesh import Mesh
from core.scene import Scene
from mirai.application import Application
from mirai.topology.connect_per_face import (
    TopologyToolError,
    apply_connect_edges,
    connect_selected_edges_per_face,
)
from mirai.topology.connect_vertices_per_face import (
    VertexConnectError,
    apply_connect_vertices,
    connect_vertices_per_face,
)
from mirai.topology.delete_dissolve import RemovalRefused, apply_removal, remove_selected
from mirai.topology.split import split_selected_edge


def _grid(n: int = 3) -> Mesh:
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


def _scene() -> Scene:
    scene = Scene()
    scene.mesh.load_state(_grid().export_state())
    return scene


def _topology(mesh) -> dict:
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}


def _vertex(mesh, r, c):
    return next(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (float(c), float(r)))


def _edge(mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def _opposite_edges(mesh):
    f = sorted(mesh.all_face_ids())[0]
    edges = mesh.face_edges(f)
    return {edges[0], edges[2]}


# -- apply / wrapper equivalence -------------------------------------------------------------


def test_edge_connect_apply_matches_wrapper_and_reports_midpoints():
    a, b = _scene(), _scene()
    edges = _opposite_edges(a.mesh)
    result = apply_connect_edges(a.mesh, set(edges))
    created = connect_selected_edges_per_face(b, set(_opposite_edges(b.mesh)))
    assert _topology(a.mesh) == _topology(b.mesh)
    assert result.created == created
    assert len(b.history) == 1 and len(a.history) == 0
    assert set(result.midpoints) == edges
    assert all(a.mesh.is_valid_vertex(v) for v in result.midpoints.values())


def test_edge_connect_refusal_restores_in_wrapper_and_raises_in_apply():
    scene = _scene()
    mesh = scene.mesh
    far = {_edge(mesh, _vertex(mesh, 0, 0), _vertex(mesh, 0, 1)), _edge(mesh, _vertex(mesh, 3, 2), _vertex(mesh, 3, 3))}
    before = mesh.export_state()
    with pytest.raises(TopologyToolError):
        connect_selected_edges_per_face(scene, far)
    assert _topology(mesh) == {k: v for k, v in before.items() if not k.endswith("_id_counter")}
    assert len(scene.history) == 0
    with pytest.raises(TopologyToolError):
        apply_connect_edges(mesh, {next(iter(far))})


def test_vertex_connect_apply_matches_wrapper():
    a, b = _scene(), _scene()
    sel = lambda m: {_vertex(m, 0, 0), _vertex(m, 1, 1)}  # noqa: E731
    created_a = apply_connect_vertices(a.mesh, sel(a.mesh))
    created_b = connect_vertices_per_face(b, sel(b.mesh))
    assert created_a and created_a == created_b
    assert _topology(a.mesh) == _topology(b.mesh)
    assert len(b.history) == 1


def test_vertex_connect_nothing_connectable_signal_and_errors():
    scene = _scene()
    mesh = scene.mesh
    adjacent = {_vertex(mesh, 0, 0), _vertex(mesh, 0, 1)}
    assert apply_connect_vertices(mesh, adjacent) == []
    assert connect_vertices_per_face(scene, adjacent) == []
    assert len(scene.history) == 0
    with pytest.raises(VertexConnectError):
        apply_connect_vertices(mesh, {_vertex(mesh, 0, 0)})


@pytest.mark.parametrize("dissolve", [False, True])
def test_removal_apply_matches_wrapper(dissolve):
    a, b = _scene(), _scene()
    ids = lambda m: {_edge(m, _vertex(m, 1, 1), _vertex(m, 1, 2))}  # noqa: E731
    faces_a = apply_removal(a.mesh, SelectionMode.EDGE, ids(a.mesh), dissolve=dissolve, cleanup=True)
    faces_b = remove_selected(b, SelectionMode.EDGE, ids(b.mesh), dissolve=dissolve, cleanup=True)
    assert _topology(a.mesh) == _topology(b.mesh)
    assert faces_a == faces_b
    assert len(b.history) == 1


def test_removal_refusal_and_noop():
    scene = _scene()
    mesh = scene.mesh
    with pytest.raises(RemovalRefused):
        apply_removal(mesh, SelectionMode.EDGE, {_edge(mesh, _vertex(mesh, 0, 0), _vertex(mesh, 0, 1))},
                      dissolve=True, cleanup=True)
    with pytest.raises(RemovalRefused):
        remove_selected(scene, SelectionMode.EDGE, {_edge(mesh, _vertex(mesh, 0, 0), _vertex(mesh, 0, 1))},
                        dissolve=True, cleanup=True)
    assert len(scene.history) == 0
    assert remove_selected(scene, SelectionMode.FACE, set(), dissolve=False, cleanup=True) is None


def test_split_apply_is_mesh_split_edge():
    a, b = _scene(), _scene()
    ea = _edge(a.mesh, _vertex(a.mesh, 1, 1), _vertex(a.mesh, 1, 2))
    eb = _edge(b.mesh, _vertex(b.mesh, 1, 1), _vertex(b.mesh, 1, 2))
    a.mesh.split_edge(ea)
    split_selected_edge(b, eb)
    assert _topology(a.mesh) == _topology(b.mesh) and len(b.history) == 1


# -- Application: exactly one Undo step per key-press path --------------------------------------


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_grid().export_state())
    app.viewport.on_topology_changed()
    app.frame_scene()
    app.set_viewport_size(800, 600)
    return app


def _select(app, mode, ids):
    app.selection.mode = mode
    app.selection.clear()
    app.selection.add(set(ids))


def _one_undo_step(app, run):
    mesh = app.scene.mesh
    topo, mirror, depth = _topology(mesh), app._selection_snapshot(), len(app.history)
    assert run() is True
    assert len(app.history) == depth + 1
    assert len(app._selection_undo_stack) >= 1
    app.history.undo()
    assert _topology(mesh) == topo
    assert len(app.history) == depth
    return mirror


def test_split_one_step(app):
    m = app.scene.mesh
    _select(app, SelectionMode.EDGE, {_edge(m, _vertex(m, 1, 1), _vertex(m, 1, 2))})
    _one_undo_step(app, app._connect_command)
    assert app.status_message == "Split"


def test_edge_connect_one_step(app):
    m = app.scene.mesh
    _select(app, SelectionMode.EDGE, _opposite_edges(m))
    _one_undo_step(app, app._connect_command)
    assert app.status_message == "Connect Edges"


def test_edge_connect_refusal_text_and_no_entry(app):
    m = app.scene.mesh
    _select(app, SelectionMode.EDGE, {_edge(m, _vertex(m, 0, 0), _vertex(m, 0, 1)),
                                      _edge(m, _vertex(m, 3, 2), _vertex(m, 3, 3))})
    assert app._connect_command() is False
    assert app.status_message == "Keine verbindbaren Kanten: ausgewählte Kanten teilen sich keine Face."
    assert len(app.history) == 0


def test_vertex_connect_one_step_and_noop_text(app):
    m = app.scene.mesh
    _select(app, SelectionMode.VERTEX, {_vertex(m, 0, 0), _vertex(m, 1, 1)})
    _one_undo_step(app, app._connect_command)
    assert app.status_message == "Vertex Connect"
    _select(app, SelectionMode.VERTEX, {_vertex(m, 0, 0), _vertex(m, 0, 1)})
    assert app._connect_command() is False
    assert app.status_message == "Vertex Connect: nothing connectable"
    assert len(app.history) == 0


@pytest.mark.parametrize("command,label", [("delete", "Delete Faces"), ("dissolve", "Dissolve Faces")])
def test_removal_one_step(app, command, label):
    from mirai.interaction import commands as cmd

    m = app.scene.mesh
    faces = sorted(m.all_face_ids())
    f = {faces[4], faces[5]} if command == "dissolve" else {faces[4]}
    name = cmd.DELETE if command == "delete" else cmd.DISSOLVE
    _select(app, SelectionMode.FACE, f)
    _one_undo_step(app, lambda: app._removal_command(name))
    assert app.status_message == label


def test_removal_refusal_and_empty_texts(app):
    from mirai.interaction import commands as cmd

    m = app.scene.mesh
    assert app._removal_command(cmd.DELETE) is False
    assert app.status_message == "Delete: nothing selected"
    _select(app, SelectionMode.EDGE, {_edge(m, _vertex(m, 0, 0), _vertex(m, 0, 1))})
    assert app._removal_command(cmd.DISSOLVE) is False
    assert app.status_message.startswith("Dissolve Edges: ")
    assert len(app.history) == 0

