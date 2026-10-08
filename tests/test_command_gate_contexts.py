"""`CommandGate.refused_contexts` and the context check in `Application._connect_command`
(AD-013 H2 amendment G-2, 2026-10-08; AD-SYM-03 slice 3a).

Headless, fixture as `tests/test_application_pointer.py`. The named tests of the amendment's
§ Required tests that live in `src`:

- T-G2a  four operation contexts x (listed / not listed); a refusal changes nothing
- T-G2b  exactly one `resolve_c_context` call per `C` press, with and without a definition
- T-G2c  order: identity gate and armed-transform check run before the context check
- T-G2d  `CContext.NONE` cannot be listed
- T-G2e  a Knife session is not touched by a gate that lists every context
- T-G2f  `CommandGate()` defaults, `==`, read-only mapping
- T-R5a+ a default gate changes nothing on any of the five contexts
- T-G3a  no gate + definition: undeclared contexts (Split, Knife) behave as without a definition
         (Edge/Vertex Connect are declared since slice 3b: `tests/test_symmetric_ops.py`)
- T-G3b  AST guard: `src/main.py` sets no symmetry definition and calls no symmetry code

Deliberately not named `test_application_*` (that set is what T-R5c re-runs). T-R5c+ is in
`tests/test_command_gate.py`.

The cube (x = +-1, no seam) is the mesh: with `SymmetryDefinition` X every vertex is paired.
Top face (y = 1) `[7, 6, 2, 3]`: edges 6-2 / 7-3 are a mirror pair, 7-6 / 3-2 are self-mirrored.
"""

from __future__ import annotations

import ast
import dataclasses

import pytest

import tests._bootstrap  # noqa: F401

from tests._bootstrap import _SRC

import mirai.application as application_module
from core import EdgeId, SelectionMode, VertexId
from core.mesh import SymmetryDefinition
from mirai.application import Application, CommandGate
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.topology.contextual_c import CContext, resolve_c_context

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)

C = Input("key", "c")
W = Input("key", "w")
E = Input("key", "e")
ENTER = Input("key", "enter")
ESC = Input("key", "ESCAPE")
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
LMB = Input("mouse", "LEFT")

OPERATION_CONTEXTS = (
    CContext.SPLIT,
    CContext.EDGE_CONNECT,
    CContext.VERTEX_CONNECT,
    CContext.KNIFE,
)
ALL_CONTEXTS = OPERATION_CONTEXTS + (CContext.NONE,)
#: Contexts without a coordinator (`mirai.symmetry_declarations`, slice 3b): Split and Knife, plus
#: `NONE`, which is no operation. T-G3a pins that a definition changes nothing for them.
UNCOORDINATED_CONTEXTS = (CContext.SPLIT, CContext.KNIFE, CContext.NONE)
TEXTS = {ctx: f"refused {ctx.name}" for ctx in OPERATION_CONTEXTS}
EXACT_X = SymmetryDefinition((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), frozenset())


def make_app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.pointer_motion(*MISS)
    return app


@pytest.fixture
def app() -> Application:
    return make_app()


def _edge(app, a: int, b: int) -> EdgeId:
    mesh = app.scene.mesh
    return next(e for e in mesh.all_edge_ids() if {int(v) for v in mesh.edge_vertices(e)} == {a, b})


def _vertex(app, index: int) -> VertexId:
    return next(v for v in app.scene.mesh.all_vertex_ids() if int(v) == index)


def select_for(app: Application, ctx: CContext) -> None:
    """A selection that resolves to `ctx` literally, and that is its own canonical form under X
    (no mirror pair in it)."""
    selection = app.selection
    selection.clear()
    if ctx is CContext.SPLIT:
        selection.mode = SelectionMode.EDGE
        selection.edges = {_edge(app, 7, 6)}
    elif ctx is CContext.EDGE_CONNECT:
        selection.mode = SelectionMode.EDGE
        selection.edges = {_edge(app, 7, 6), _edge(app, 3, 2)}
    elif ctx is CContext.VERTEX_CONNECT:
        selection.mode = SelectionMode.VERTEX
        selection.vertices = {_vertex(app, 7), _vertex(app, 2)}
    elif ctx is CContext.NONE:
        selection.mode = SelectionMode.VERTEX
        selection.vertices = {_vertex(app, 7)}
    else:
        selection.mode = SelectionMode.VERTEX
    assert resolve_c_context(selection) is ctx


def select_mirror_edge_pair(app: Application) -> None:
    selection = app.selection
    selection.clear()
    selection.mode = SelectionMode.EDGE
    selection.edges = {_edge(app, 6, 2), _edge(app, 7, 3)}


def selection_state(app: Application) -> tuple:
    s = app.selection
    return (s.mode, frozenset(s.vertices), frozenset(s.edges), frozenset(s.faces))


def mesh_state(app: Application) -> dict:
    return app.scene.mesh.export_state()


def outcome(app: Application, result: bool) -> tuple:
    """Everything a `C` press may change, for twin comparisons."""
    return (
        result,
        app.status_message,
        app.status_serial,
        app.knife_active,
        len(app.history),
        mesh_state(app),
        selection_state(app),
    )


def gate_with(contexts, **kwargs) -> CommandGate:
    return CommandGate(refused_contexts={ctx: TEXTS[ctx] for ctx in contexts}, **kwargs)


# -- T-G2a -----------------------------------------------------------------------------------


@pytest.mark.parametrize("with_definition", [False, True], ids=["no_definition", "definition"])
@pytest.mark.parametrize("ctx", OPERATION_CONTEXTS, ids=lambda c: c.name)
def test_t_g2a_listed_context_is_refused_and_changes_nothing(app, ctx, with_definition):
    if with_definition:
        app.scene.mesh.symmetry_definition = EXACT_X
    select_for(app, ctx)
    app.command_gate = gate_with([ctx])
    before = (mesh_state(app), len(app.history), selection_state(app))
    serial = app.status_serial
    for n in (1, 2):  # twice the same refusal -> two increments
        assert app.key_press(C) is False
        assert app.status_serial == serial + n
        assert app.status_message == TEXTS[ctx]
    assert (mesh_state(app), len(app.history), selection_state(app)) == before
    assert app.knife_active is False
    assert app.interaction_owner is None
    assert app.command_gate == gate_with([ctx])


@pytest.mark.parametrize("with_definition", [False, True], ids=["no_definition", "definition"])
@pytest.mark.parametrize("ctx", OPERATION_CONTEXTS, ids=lambda c: c.name)
def test_t_g2a_unlisted_context_runs_as_without_a_gate(ctx, with_definition):
    """A gate that lists the *other* three contexts leaves this one as if no gate was set."""
    others = [c for c in OPERATION_CONTEXTS if c is not ctx]
    runs = []
    for gate in (None, gate_with(others)):
        app = make_app()
        if with_definition:
            app.scene.mesh.symmetry_definition = EXACT_X
        select_for(app, ctx)
        app.command_gate = gate
        runs.append(outcome(app, app.key_press(C)))
    assert runs[0] == runs[1]
    assert runs[0][3] is (ctx is CContext.KNIFE)  # the Knife session started, the rest mutated


def test_t_g2a_mirror_pair_refusal_keeps_both_sides_selected(app):
    """A definition is set and the selection is a mirror pair: canonicalised to one edge, resolved
    as Split. A refusal leaves `selection` holding both sides (canonicalisation works on a value)."""
    app.scene.mesh.symmetry_definition = EXACT_X
    select_mirror_edge_pair(app)
    assert resolve_c_context(app.selection) is CContext.EDGE_CONNECT  # literally
    app.command_gate = gate_with([CContext.SPLIT])
    before = (mesh_state(app), len(app.history), selection_state(app))
    assert app.key_press(C) is False
    assert app.status_message == TEXTS[CContext.SPLIT]
    assert (mesh_state(app), len(app.history), selection_state(app)) == before
    assert len(app.selection.edges) == 2


# -- T-G2b -----------------------------------------------------------------------------------


@pytest.fixture
def resolve_calls(monkeypatch):
    calls = []

    def counting(selection):
        calls.append(selection)
        return resolve_c_context(selection)

    monkeypatch.setattr(application_module, "resolve_c_context", counting)
    return calls


@pytest.mark.parametrize("with_definition", [False, True], ids=["no_definition", "definition"])
@pytest.mark.parametrize("gate", ["none", "listed", "unlisted"])
@pytest.mark.parametrize("ctx", ALL_CONTEXTS, ids=lambda c: c.name)
def test_t_g2b_exactly_one_resolution_per_press(resolve_calls, ctx, gate, with_definition):
    app = make_app()
    if with_definition:
        app.scene.mesh.symmetry_definition = EXACT_X
    select_for(app, ctx)
    resolve_calls.clear()
    if gate == "listed":
        app.command_gate = gate_with(OPERATION_CONTEXTS)
    elif gate == "unlisted":
        app.command_gate = gate_with([])
    app.key_press(C)
    assert len(resolve_calls) == 1


def test_t_g2b_the_resolved_value_is_the_canonical_selection(resolve_calls, app):
    """With a definition the one call receives the temporary canonical value, not the live
    selection."""
    app.scene.mesh.symmetry_definition = EXACT_X
    select_mirror_edge_pair(app)
    app.key_press(C)
    (seen,) = resolve_calls
    assert seen is not app.selection
    assert len(seen.edges) == 1


# -- T-G2c -----------------------------------------------------------------------------------


def test_t_g2c_identity_text_wins_over_a_listed_context(resolve_calls, app):
    select_for(app, CONTEXT_SPLIT := CContext.SPLIT)
    app.command_gate = CommandGate(
        refused={commands.CONNECT: "C by identity"}, refused_contexts={CONTEXT_SPLIT: "by context"}
    )
    serial = app.status_serial
    assert app.key_press(C) is False
    assert (app.status_serial, app.status_message) == (serial + 1, "C by identity")
    assert resolve_calls == []


def test_t_g2c_outside_the_allow_list_uses_not_allowed_text(resolve_calls, app):
    select_for(app, CContext.SPLIT)
    app.command_gate = CommandGate(
        allowed=frozenset({commands.UNDO}),
        not_allowed_text="not allowed",
        refused_contexts={CContext.SPLIT: "by context"},
    )
    serial = app.status_serial
    assert app.key_press(C) is False
    assert (app.status_serial, app.status_message) == (serial + 1, "not allowed")
    assert resolve_calls == []


def test_t_g2c_armed_transform_wins_over_the_context_check(resolve_calls, app):
    """W armed, then C: `key_press` returns False from the armed check; no context status."""
    select_for(app, CContext.NONE)  # one vertex: W arms on the selection
    app.command_gate = gate_with(OPERATION_CONTEXTS)
    assert app.key_press(W) is True
    assert app.transform_command == commands.MOVE
    status = (app.status_message, app.status_serial)
    assert app.key_press(C) is False
    assert (app.status_message, app.status_serial) == status
    assert resolve_calls == []


# -- T-G2d -----------------------------------------------------------------------------------


def test_t_g2d_none_cannot_be_listed():
    with pytest.raises(ValueError):
        CommandGate(refused_contexts={CContext.NONE: "nothing"})
    with pytest.raises(ValueError):
        CommandGate(refused_contexts={CContext.SPLIT: "split", CContext.NONE: "nothing"})


def test_t_g2d_none_keeps_the_applications_own_text(app):
    select_for(app, CContext.NONE)
    app.command_gate = gate_with(OPERATION_CONTEXTS)
    serial = app.status_serial
    assert app.key_press(C) is False
    assert (app.status_serial, app.status_message) == (serial + 1, "C: nothing to do here")


# -- T-G2e -----------------------------------------------------------------------------------


def test_t_g2e_knife_session_is_untouched_by_a_gate_listing_every_context():
    """The session starts without a gate; installing a gate that lists all four contexts changes
    nothing inside it (keys are routed to the session before the gate, clicks never reach
    `_execute_click`)."""
    runs = []
    for gate in (None, gate_with(OPERATION_CONTEXTS)):
        app = make_app()
        assert app.key_press(C) is True and app.knife_active
        app.command_gate = gate
        sx, sy = app.camera.project_to_screen(
            app.scene.mesh.vertex_position(_vertex(app, 6)), WIDTH, HEIGHT
        )
        steps = []
        for step in (
            lambda: app.key_press(E),
            lambda: app.key_press(CTRL_Z),
            lambda: (app.pointer_motion(sx, sy), app.pointer_press(LMB, sx, sy), app.pointer_release("LEFT", sx, sy))[-1],
            lambda: app.key_press(ENTER),
        ):
            result = step()
            steps.append((result, app.status_message, app.knife_active, len(app.history)))
        runs.append(steps)
    assert runs[0] == runs[1]
    # Outside the session the gate applies again.
    assert not app.knife_active
    serial = app.status_serial
    assert app.key_press(C) is False
    assert (app.status_serial, app.status_message) == (serial + 1, TEXTS[CContext.KNIFE])


# -- T-G2f -----------------------------------------------------------------------------------


def test_t_g2f_defaults_equality_and_read_only_mapping():
    gate = CommandGate()
    assert dict(gate.refused_contexts) == {}
    assert gate == CommandGate()
    data = {CContext.SPLIT: "split", CContext.KNIFE: "knife"}
    first, second = CommandGate(refused_contexts=data), CommandGate(refused_contexts=dict(data))
    assert first == second
    assert first != CommandGate(refused_contexts={CContext.SPLIT: "split"})
    assert first != CommandGate()
    with pytest.raises(TypeError):
        first.refused_contexts[CContext.SPLIT] = "other"  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.refused_contexts = {}  # type: ignore[misc]
    data[CContext.SPLIT] = "changed afterwards"
    assert first.refused_contexts[CContext.SPLIT] == "split"  # copied at construction


# -- T-R5a+ ----------------------------------------------------------------------------------


def test_t_r5a_plus_default_application_has_no_gate():
    assert Application().command_gate is None


@pytest.mark.parametrize("ctx", ALL_CONTEXTS, ids=lambda c: c.name)
def test_t_r5a_plus_default_gate_changes_nothing_on_any_context(ctx):
    runs = []
    for gate in (None, CommandGate()):
        app = make_app()
        select_for(app, ctx)
        app.command_gate = gate
        runs.append(outcome(app, app.key_press(C)))
    assert runs[0] == runs[1]


# -- T-G3a -----------------------------------------------------------------------------------


def _without_symmetry(state: dict) -> dict:
    return {k: v for k, v in state.items() if k != "symmetry"}


@pytest.mark.parametrize("ctx", UNCOORDINATED_CONTEXTS, ids=lambda c: c.name)
def test_t_g3a_no_gate_a_definition_changes_nothing_for_one_sided_selections(ctx):
    """G-3 boundary from the Production side: no gate + an exact X definition. For a context
    without a coordinator (Split, Knife) a selection without a mirror pair behaves as without a
    definition (return value, status, mesh result); nothing refuses. Edge and Vertex Connect run
    their coordinator whenever a definition is set, in MARK as in BLOCK (slice 3b)."""
    runs = []
    for definition in (None, EXACT_X):
        app = make_app()
        app.scene.mesh.symmetry_definition = definition
        select_for(app, ctx)
        result = app.key_press(C)
        runs.append(
            (
                result,
                app.status_message,
                app.knife_active,
                len(app.history),
                _without_symmetry(mesh_state(app)),
                selection_state(app),
            )
        )
    assert runs[0] == runs[1]


def test_t_g3a_mirror_pair_follows_the_canonicalisation_rule(app):
    """Probe P5 of the amendment review: a mirror edge pair is one intent. With a definition and
    no gate it runs as a one-sided Split of the edge on the normal's side (x > 0); without a
    definition the same selection is a literal Edge Connect (on the cube both edges lie in the
    top face, so it connects across the plane)."""
    mesh = app.scene.mesh
    select_mirror_edge_pair(app)
    twin = make_app()
    select_mirror_edge_pair(twin)
    assert twin.key_press(C) is True  # literal: Edge Connect
    assert twin.status_message == "Connect Edges"

    mesh.symmetry_definition = EXACT_X
    vertices = len(mesh.all_vertex_ids())
    assert app.key_press(C) is True
    assert app.status_message == "Split"
    assert len(mesh.all_vertex_ids()) == vertices + 1
    assert len(app.history) == 1
    (new_vertex,) = app.selection.vertices  # the split residue
    assert mesh.vertex_position(new_vertex)[0] > 0.0


def test_t_g3a_mirror_vertex_pair_counts_once(app):
    """A2 = A: "1 vertex pair -> no C meaning"."""
    app.scene.mesh.symmetry_definition = EXACT_X
    app.selection.mode = SelectionMode.VERTEX
    app.selection.vertices = {_vertex(app, 6), _vertex(app, 7)}
    before = (mesh_state(app), selection_state(app))
    assert app.key_press(C) is False
    assert app.status_message == "C: nothing to do here"
    assert (mesh_state(app), selection_state(app)) == before


# -- T-G3b -----------------------------------------------------------------------------------

_SYMMETRY_CALLS = {
    "set_symmetry_axis",
    "vertex_correspondence",
    "symmetry_state",
    "build_index",
    "SymmetryIndex",
    "canonical_vertices",
    "canonical_edges",
    "canonical_faces",
    "expand_vertices",
    "expand_edges",
    "expand_faces",
    "completeness_report",
    "delta_check",
    "seam_after_split",
}


def _main_symmetry_violations(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        for target in targets:
            for sub in ast.walk(target):
                if isinstance(sub, ast.Attribute) and sub.attr == "symmetry_definition":
                    found.append("assigns symmetry_definition")
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in _SYMMETRY_CALLS:
                found.append(f"calls {name}")
            if name == "setattr" and len(node.args) >= 2:
                arg = node.args[1]
                if isinstance(arg, ast.Constant) and arg.value == "symmetry_definition":
                    found.append("setattr symmetry_definition")
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if "symmetry" in module:
                found.append(f"imports {module}")
            found.extend(f"imports {a.name}" for a in node.names if "symmetry" in a.name)
        if isinstance(node, ast.Import):
            found.extend(f"imports {a.name}" for a in node.names if "symmetry" in a.name)
    return found


def test_t_g3b_main_py_sets_no_definition_and_calls_no_symmetry_code():
    """H2-R5, S3: after slice 3 `_connect_command` changes when a definition is set; this keeps
    "no Production host sets one" true."""
    source = (_SRC / "main.py").read_text(encoding="utf-8")
    assert _main_symmetry_violations(source) == []


def test_t_g3b_guard_detects_violations():
    bad = (
        "mesh.symmetry_definition = d\n"
        "setattr(mesh, 'symmetry_definition', d)\n"
        "from mirai.symmetry import vertex_correspondence\n"
        "from mirai.symmetry_coordination import canonical_edges\n"
        "import mirai.symmetry_declarations\n"
        "vertex_correspondence(mesh)\n"
        "canonical_edges(index, ids)\n"
    )
    assert len(_main_symmetry_violations(bad)) >= 7
