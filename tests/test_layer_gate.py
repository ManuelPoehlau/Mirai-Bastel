"""AD-025 §4.4 (T-7) and §4.2 consumers (T-9): the point-layer operation gate in `Application`
(`mirai.layer_declarations`) and the consumers of layer-only changes.

Headless. The gate is fail-closed: every command constant, every resolved `C` context and every
public `Application` method that can change or copy a mesh is classified; a declared operation runs
on a plain and a symmetric layered fixture against its rule (no vertex created, survivors keep their
values bit for bit, the Core deletes the values of removed vertices); everything else that changes a
mesh is refused before any mutation, per target mesh. Without layers nothing is looked up.
"""

from __future__ import annotations

import ast
import inspect
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import PointLayerInfo, SelectionMode
from mirai import application as application_module
from mirai import layer_declarations as gate
from mirai import symmetry_declarations
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.topology.contextual_c import CContext
from mirai.topology.knife_resolve import SessionStart
from scene_menu import MIRROR_ENTRIES
from tests.mesh_invariants import assert_layer_invariants
from tests.test_application_delete_dissolve import _app, _edge, _grid_face, _grid_vertex, _select
from tests.test_mirror_pairs import _placed_sphere
from tests.test_symmetric_ops import make_app, plus_x_quad

TEST_KEY = Input("key", "f12")
V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE


def _add_layers(mesh, seed: int = 0) -> list:
    """Two dense vector layers (every vertex has a value), so any lost or invented value shows."""
    rng = random.Random(seed)
    layers = []
    for name in ("Smile", "Blink"):
        lid = mesh.add_point_layer(PointLayerInfo(name))
        for vid in mesh.all_vertex_ids():
            mesh.set_layer_value(lid, vid, (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
        layers.append(lid)
    return layers


def _layers(mesh) -> dict:
    return {lid: dict(mesh.layer_items(lid)) for lid in mesh.point_layer_ids()}


def _state(app) -> tuple:
    return (
        app.scene.mesh.export_state(),
        len(app.history),
        app._selection_snapshot(),
        len(app._selection_undo_stack),
    )


def _press(app, command: str) -> bool:
    app.bindings.bind(TEST_KEY, command)
    return app.key_press(TEST_KEY)


# -- enumeration: commands, contexts and methods --------------------------------------------------


def test_every_command_constant_is_classified():
    constants = {v for n, v in vars(commands).items() if n.isupper() and isinstance(v, str)}
    assert constants - set(gate.COMMAND_CLASSES) == set(), "unclassified command(s)"
    assert set(gate.COMMAND_CLASSES) - constants == set()
    assert set(gate.CONTEXT_CLASSES) == set(CContext)
    for key, cls in gate.COMMAND_CLASSES.items():
        assert (cls == gate.DECLARED) == (key in gate.LAYER_SAFE_OPERATIONS), key


_SINKS = {
    "_mesh_transaction", "record_mesh_change", "begin_change", "mirror_mesh", "from_state", "load_state",
    "apply_placement", "add_object", "apply_delta",
}


def _mutating_public_methods() -> set[str]:
    """Public `Application` methods that (through `self.` calls inside the class) reach a mesh change
    or build a mesh from another - listed from the code, not by hand."""
    tree = ast.parse(inspect.getsource(application_module))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Application")
    names = {}
    for f in cls.body:
        if isinstance(f, ast.FunctionDef):
            names[f.name] = {
                n.attr if isinstance(n, ast.Attribute) else n.id
                for n in ast.walk(f) if isinstance(n, (ast.Attribute, ast.Name))
            }
    reach = {m for m, used in names.items() if used & _SINKS}
    grown = True
    while grown:
        grown = False
        for m, used in names.items():
            if m not in reach and used & reach:
                reach.add(m)
                grown = True
    return {m for m in reach if not m.startswith("_")}


def test_every_mutating_method_and_menu_method_is_classified():
    methods = _mutating_public_methods() | {method for method, _ in MIRROR_ENTRIES.values()}
    assert "mirror_copy" in methods and "apply_mesh_change" in methods  # the scan sees them
    assert methods - set(gate.METHOD_CLASSES) == set(), "unclassified method(s)"
    assert all(hasattr(Application, m) for m in gate.METHOD_CLASSES)


def test_declared_entries_are_the_implementations_the_app_runs():
    ops = gate.LAYER_SAFE_OPERATIONS
    assert ops[CContext.VERTEX_CONNECT] == (
        application_module.apply_connect_vertices,
        symmetry_declarations.C_CONTEXT_COORDINATORS[CContext.VERTEX_CONNECT],
    )
    for command in (commands.DELETE, commands.DISSOLVE, commands.DISSOLVE_NO_CLEANUP):
        assert ops[command] == (application_module.apply_removal, symmetry_declarations.REMOVAL_COORDINATORS[command])
    assert ops[commands.CAP] == (application_module.apply_cap, symmetry_declarations.CAP_COORDINATORS[commands.CAP])


def test_unknown_keys_are_refused():
    assert gate.layer_refusal("SomeNewTool") is not None
    assert gate.layer_refusal("some_new_method") is not None


# -- declared operations: rule fixtures, plain and symmetric -----------------------------------------


def _plain_vertex_connect(app):
    a, c = _grid_vertex(app, 1, 1), _grid_vertex(app, 2, 2)
    _select(app, V, {a, c})


def _plain_delete(app):
    _select(app, F, {_grid_face(app, 1, 1)})


def _plain_dissolve(app):
    mesh = app.scene.mesh
    _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 2, 1))})


def _plain_cap(app):
    mesh = app.scene.mesh
    face = _grid_face(app, 1, 1)
    corners = mesh.face_vertices(face)
    mesh.delete_faces([face])
    _select(app, E, {_edge(mesh, corners[0], corners[1])})


def _sym_quad(app):
    return plus_x_quad(app.scene.mesh, touching_seam=False)


def _sym_vertex_connect(app):
    a, _, c, _ = app.scene.mesh.face_vertices(_sym_quad(app))
    _select(app, V, {a, c})


def _sym_delete(app):
    _select(app, F, {_sym_quad(app)})


def _sym_dissolve(app):
    mesh = app.scene.mesh
    a, b, _, _ = mesh.face_vertices(_sym_quad(app))
    _select(app, E, {_edge(mesh, a, b)})


def _sym_cap(app):
    from mirai.symmetric_ops import coordinate_delete

    mesh = app.scene.mesh
    face = _sym_quad(app)
    corners = mesh.face_vertices(face)
    coordinate_delete(mesh, F, {face})  # a hole on both sides
    _select(app, E, {_edge(mesh, corners[0], corners[1])})


#: Declared key -> (command pressed, plain fixture, symmetric fixture). An entry of
#: `LAYER_SAFE_OPERATIONS` without a row here fails (declaration = tested support).
RULE_FIXTURES = {
    CContext.VERTEX_CONNECT: (commands.CONNECT, _plain_vertex_connect, _sym_vertex_connect),
    commands.DELETE: (commands.DELETE, _plain_delete, _sym_delete),
    commands.DISSOLVE: (commands.DISSOLVE, _plain_dissolve, _sym_dissolve),
    commands.DISSOLVE_NO_CLEANUP: (commands.DISSOLVE_NO_CLEANUP, _plain_dissolve, _sym_dissolve),
    commands.CAP: (commands.CAP, _plain_cap, _sym_cap),
}


def test_every_declared_entry_has_a_rule_fixture():
    assert set(RULE_FIXTURES) == set(gate.LAYER_SAFE_OPERATIONS)


@pytest.mark.parametrize("symmetric", [False, True], ids=["plain", "symmetric"])
@pytest.mark.parametrize("key", list(RULE_FIXTURES), ids=str)
def test_declared_operation_runs_on_a_layered_mesh_by_its_rule(key, symmetric):
    command, plain, sym = RULE_FIXTURES[key]
    app = make_app("subd_cube") if symmetric else _app(3)
    (sym if symmetric else plain)(app)
    mesh = app.scene.mesh
    _add_layers(mesh)
    before_vertices = set(mesh.all_vertex_ids())
    before = _layers(mesh)
    history = len(app.history)
    assert _press(app, command) is True, app.status_message
    assert len(app.history) == history + 1
    after_vertices = set(mesh.all_vertex_ids())
    assert after_vertices <= before_vertices  # none of them creates a vertex
    for lid, values in before.items():
        assert _layers(mesh)[lid] == {v: x for v, x in values.items() if v in after_vertices}
    assert_layer_invariants(mesh)
    assert app.key_press(Input("key", "z", frozenset({"ctrl"})))
    assert set(mesh.all_vertex_ids()) == before_vertices and _layers(mesh) == before


# -- locked operations: refused before any mutation -------------------------------------------------


def _locked_cases():
    def split(app):
        mesh = app.scene.mesh
        _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2))})
        return commands.CONNECT

    def edge_connect(app):
        mesh = app.scene.mesh
        _select(app, E, {
            _edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2)),
            _edge(mesh, _grid_vertex(app, 2, 1), _grid_vertex(app, 2, 2)),
        })
        return commands.CONNECT

    def knife(app):
        app.selection.clear()
        return commands.CONNECT

    def collapse(app):
        _plain_dissolve(app)
        return commands.COLLAPSE

    def extrude(app):
        _plain_delete(app)
        return commands.EXTRUDE

    def loop_insert(app):
        _plain_dissolve(app)
        return commands.LOOP_INSERT

    return {"split": split, "edge_connect": edge_connect, "knife": knife, "collapse": collapse,
            "extrude": extrude, "loop_insert": loop_insert}


@pytest.mark.parametrize("case", list(_locked_cases()))
def test_locked_operation_is_refused_untouched(case):
    app = _app(3)
    command = _locked_cases()[case](app)
    _add_layers(app.scene.mesh)
    before = _state(app)
    assert _press(app, command) is False
    assert "locked while this mesh has morph targets" in app.status_message
    assert app.interaction_owner is None
    assert _state(app) == before


@pytest.mark.parametrize("case", list(_locked_cases()))
def test_locked_operation_runs_without_layers(case):
    app = _app(3)
    command = _locked_cases()[case](app)
    before = app.scene.mesh.export_state()
    _press(app, command)
    if app.interaction_owner == "transform":
        app.pointer_motion(400, 300, 0.0, -30.0)
        app.key_release(TEST_KEY)
    elif app.interaction_owner == "knife":
        assert case == "knife"  # the session starts: the C context was not refused
        app.key_press(Input("key", "escape"))
        return
    assert app.scene.mesh.export_state() != before, (case, app.status_message)


def test_apply_transform_refused_when_one_baked_object_has_layers():
    app = _app()
    plain = app.add_primitive("sphere", name="plain")
    layered = _placed_sphere(app, "layered")
    plain.transform = layered.transform
    _add_layers(layered.mesh)
    app.key_press(Input("key", "4"))
    app.selection.objects = {plain.id, layered.id}
    states = (plain.mesh.export_state(), layered.mesh.export_state(), plain.transform, len(app.history))
    assert app.dispatch_command(commands.APPLY_TRANSFORM) is False
    assert "Apply transform: locked" in app.status_message
    assert (plain.mesh.export_state(), layered.mesh.export_state(), plain.transform, len(app.history)) == states
    app.selection.objects = {plain.id}  # the layered object is not a target: allowed
    assert app.dispatch_command(commands.APPLY_TRANSFORM) is True


def test_apply_transform_of_a_plain_object_is_not_refused_by_a_layered_edit_mesh():
    app = _app()
    plain = _placed_sphere(app, "plain")
    _add_layers(app.scene.mesh)  # the edit object (cube) has layers, it is not baked
    app.key_press(Input("key", "4"))
    app.selection.objects = {plain.id}
    assert app.dispatch_command(commands.APPLY_TRANSFORM) is True, app.status_message


def test_mirror_copy_of_a_layered_source_is_refused():
    app = _app()
    source = _placed_sphere(app)
    _add_layers(source.mesh)
    app.key_press(Input("key", "4"))
    app.selection.objects = {source.id}
    objects, history = dict(app.scene.objects), len(app.history)
    assert app.mirror_copy("X") is None
    assert "Mirror copy: locked" in app.status_message
    assert dict(app.scene.objects) == objects and len(app.history) == history
    source.mesh.remove_point_layer(source.mesh.point_layer_ids()[0])
    source.mesh.remove_point_layer(source.mesh.point_layer_ids()[0])
    assert app.mirror_copy("X") is not None


# -- allowed: position-only commands leave layers bit-identical ---------------------------------------


@pytest.mark.parametrize("command", [commands.MOVE, commands.ROTATE, commands.SCALE, commands.SMOOTH,
                                     commands.RELAX, commands.LOOP_SLIDE])
def test_position_only_commands_keep_layers_bit_identical(command):
    app = _app(3)
    mesh = app.scene.mesh
    if command == commands.LOOP_SLIDE:
        _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 2, 1))})
    else:
        _select(app, V, {_grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2), _grid_vertex(app, 2, 1)})
    for vid in mesh.all_vertex_ids():  # a bumpy grid, so Smooth / Relax have something to do
        x, y, _ = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (x, y, 0.3 * ((int(vid) * 7) % 3)))
    _add_layers(mesh)
    layers = _layers(mesh)
    positions = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    history = len(app.history)
    assert _press(app, command), app.status_message
    for _ in range(3):
        app.pointer_motion(400, 300, 12.0, -9.0)
    app.key_release(TEST_KEY)
    assert len(app.history) == history + 1, app.status_message
    assert {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()} != positions
    assert _layers(mesh) == layers


def test_without_layers_there_is_no_lookup(monkeypatch):
    def boom(key):
        raise AssertionError(f"layer gate consulted for {key!r}")

    monkeypatch.setattr(application_module, "layer_refusal", boom)
    app = _app(3)
    _plain_dissolve(app)
    assert _press(app, commands.COLLAPSE)
    _select(app, E, {app.scene.mesh.all_edge_ids()[0]})
    assert _press(app, commands.CONNECT)


# -- T-9: consumers of layer changes -------------------------------------------------------------


def test_layer_only_transaction_and_its_undo_rebuild_no_topology(monkeypatch):
    app = _app(3)
    mesh = app.scene.mesh
    lid = mesh.add_point_layer(PointLayerInfo("Smile"))
    vid = mesh.all_vertex_ids()[4]
    calls = []
    monkeypatch.setattr(app.viewport, "on_topology_changed", lambda: calls.append("topology"))
    assert app.apply_mesh_change("Edit target", lambda: mesh.set_layer_value(lid, vid, (0.0, 0.2, 0.0)))
    assert mesh.layer_value(lid, vid) == (0.0, 0.2, 0.0)
    assert app._selection_undo_stack[-1][2] is False  # a non-topology mirror entry
    app.key_press(Input("key", "z", frozenset({"ctrl"})))
    assert mesh.layer_value(lid, vid) == (0.0, 0.0, 0.0)
    app.key_press(Input("key", "y", frozenset({"ctrl"})))
    assert mesh.layer_value(lid, vid) == (0.0, 0.2, 0.0)
    assert calls == []


def test_apply_mesh_change_gets_the_core_backstop():
    app = _app(3)
    mesh = app.scene.mesh
    _add_layers(mesh)
    before = _state(app)
    with pytest.raises(Exception):
        app.apply_mesh_change("host adds a point", lambda: mesh.add_vertex((0.0, 0.0, 9.0)))
    assert _state(app) == before


def test_session_start_sees_layer_changes():
    app = _app(2)
    mesh = app.scene.mesh
    lid, _ = _add_layers(mesh)
    start = mesh.export_state()
    session = SessionStart(mesh)
    assert session.unchanged()
    vid = mesh.all_vertex_ids()[0]
    old = mesh.layer_value(lid, vid)
    mesh.set_layer_value(lid, vid, (5.0, 5.0, 5.0))
    assert not session.unchanged()
    assert session.state()["point_layers"] == start["point_layers"]
    mesh.set_layer_value(lid, vid, old)
    assert session.unchanged()
    mesh.map_vector_layers(((2, 0, 0), (0, 2, 0), (0, 0, 2)))
    assert not session.unchanged()
    assert session.state()["point_layers"] == start["point_layers"]
    mesh.remove_point_layer(lid)
    assert session.state()["point_layers"] == start["point_layers"]
    session.abandon()
    assert mesh.export_state() == start
