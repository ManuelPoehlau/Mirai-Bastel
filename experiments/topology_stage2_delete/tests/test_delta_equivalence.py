"""H1 (delta history for Delete) against whole-mesh snapshots, headless.

Oracle: the AD-023 §2 H1 exactness contract. After a Delete the mesh must equal what the unchanged op makes on a
copy (so the declared neighbourhood was complete); Undo must give back the `export_state()` of before, Redo the one
of after - compared with `==` **and** with the key order of every container, the `edge.faces` order, the symmetry
definition and the ID counters. Randomised sequences (seeded) in vertex, edge and face mode, several entries deep,
undone to the start and redone to the end.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from topology_stage2_delete import delta as delta_mod
from topology_stage2_delete import stage2

from core import EdgeId, FaceId, Mesh, VertexId
from core.selection import SelectionMode
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.topology.delete_dissolve import apply_removal

REPO = Path(__file__).resolve().parents[3]
HEAD = REPO / "examples" / "meshes" / "head_basemesh.obj"
MODES = {SelectionMode.VERTEX: ("1", VertexId), SelectionMode.EDGE: ("2", EdgeId), SelectionMode.FACE: ("3", FaceId)}


def key(name: str, *mods: str) -> Input:
    return Input("key", name, frozenset(mods))


DELETE, CTRL_Z, CTRL_Y = key("delete"), key("z", "ctrl"), key("y", "ctrl")


@pytest.fixture(params=["H1", "all"])
def app(request):
    stage2.install(request.param)
    a = Application()
    a.init_scene("obj", obj_path=HEAD)
    a.set_viewport_size(800, 600)
    a.frame_scene()
    a.viewport.sync()
    yield a
    stage2.uninstall()


def full(mesh: Mesh) -> tuple:
    """`export_state()` plus everything `==` on dicts does not see: key order and the edge face-list order."""
    state = mesh.export_state()
    return (state, [list(state[k]) for k in ("vertices", "edges", "faces")],
            [tuple(e["faces"]) for e in state["edges"].values()])


def ids_of(mesh: Mesh, mode: SelectionMode) -> list:
    return {SelectionMode.VERTEX: mesh.all_vertex_ids, SelectionMode.EDGE: mesh.all_edge_ids,
            SelectionMode.FACE: mesh.all_face_ids}[mode]()


def delete(app: Application, mode: SelectionMode, ids) -> None:
    app.key_press(key(MODES[mode][0]))
    app.selection.set(set(ids))
    app.viewport.on_selection_changed()
    assert app.key_press(DELETE), app.status_message
    app.viewport.sync()


def expected_after(state: dict, mode: SelectionMode, ids) -> tuple:
    copy = Mesh.from_state(state)
    apply_removal(copy, mode, set(ids), dissolve=False, cleanup=False)
    return full(copy)


@pytest.mark.parametrize("seed", range(6))
def test_random_sequences_undo_redo_exact(app, seed):
    rng = random.Random(seed)
    mesh = app.scene.mesh
    states = [full(mesh)]
    for _step in range(5):
        mode = rng.choice(list(MODES))
        pool = ids_of(mesh, mode)
        chosen = rng.sample(pool, rng.randint(1, 25))
        want = expected_after(states[-1][0], mode, chosen)
        delete(app, mode, chosen)
        got = full(mesh)
        assert got == want, "Delete through the delta path differs from the unchanged op"
        states.append(got)
    for state in reversed(states[:-1]):
        assert app.key_press(CTRL_Z) is not False
        app.viewport.sync()
        assert full(mesh) == state
    for state in states[1:]:
        assert app.key_press(CTRL_Y) is not False
        app.viewport.sync()
        assert full(mesh) == state


def test_history_entry_is_a_delta_and_counters_stay_forward(app):
    mesh = app.scene.mesh
    counters = [mesh.export_state()[k] for k in ("vertex_id_counter", "edge_id_counter", "face_id_counter")]
    delete(app, SelectionMode.FACE, mesh.all_face_ids()[10:14])
    command = app.history._undo_stack[-1]
    assert isinstance(command, delta_mod.DeltaCommand)
    assert len(command.delta.faces) == 4 and command.delta.edge_faces
    app.key_press(CTRL_Z)
    state = mesh.export_state()
    assert [state[k] for k in ("vertex_id_counter", "edge_id_counter", "face_id_counter")] == counters
    # A new element after the Undo gets a fresh ID (AD-001): the counter was never lowered.
    assert int(mesh.add_vertex((0.0, 0.0, 0.0))) == counters[0]


def test_selection_restored_by_undo_and_redo(app):
    mesh = app.scene.mesh
    faces = set(mesh.all_face_ids()[30:33])
    delete(app, SelectionMode.FACE, faces)
    assert app.selection.faces == set()
    app.key_press(CTRL_Z)
    assert app.selection.faces == faces
    app.key_press(CTRL_Y)
    assert app.selection.faces == set()


def test_container_not_ascending_uses_recorded_positions(app):
    mesh = app.scene.mesh
    state = mesh.export_state()
    shuffled = dict(state)
    for name in ("vertices", "edges", "faces"):
        items = list(state[name].items())
        random.Random(name).shuffle(items)
        shuffled[name] = dict(items)
    mesh.load_state(shuffled)
    app.viewport.on_topology_changed()
    app.viewport.sync()
    before = full(mesh)
    delete(app, SelectionMode.FACE, mesh.all_face_ids()[5:9])
    command = app.history._undo_stack[-1]
    assert command.delta.positions["_faces"] is not None  # positional path, not bisection
    app.key_press(CTRL_Z)
    assert full(mesh) == before


def test_symmetry_definition_takes_the_unchanged_path(app, monkeypatch):
    from core.mesh import SymmetryDefinition

    calls = []
    original = stage2._originals["_removal_command"]
    monkeypatch.setitem(stage2._originals, "_removal_command",
                        lambda self, command: calls.append(command) or original(self, command))
    mesh = app.scene.mesh
    mesh.symmetry_definition = SymmetryDefinition((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    app.key_press(key("3"))
    app.selection.set({mesh.all_face_ids()[0]})
    app.key_press(DELETE)
    assert len(calls) == 1
    assert not any(isinstance(c, delta_mod.DeltaCommand) for c in app.history._undo_stack)


def test_invalid_id_refuses_without_change(app):
    mesh = app.scene.mesh
    before = full(mesh)
    app.key_press(key("3"))
    app.selection.set({FaceId(10**6)})
    assert app.key_press(DELETE) is False
    assert full(mesh) == before
    assert not app.history.can_undo()
