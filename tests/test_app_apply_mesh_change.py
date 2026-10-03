"""`Application.apply_mesh_change` and `interaction_owner`
(WP-SYM-LAB-03 H3, AD-013 H2 addendum, Application level).

Headless (TraceStore), fixture as `tests/test_application_pointer.py`. The
addendum's tests are run here at `Application` level, calling
`apply_mesh_change` directly (the Lab path follows in Slice 1b):

- T-R2d  `interaction_owner` (H2-R2, F4)
- T-R4c  selection mirror stays aligned (probe P3), and "0 changes = no entry"
- T-R4d  pick cache invalidated: hover and click find the new positions
- T-R4e  raises before `mutate` while a transform or Knife owns the keys;
         a raising `mutate` restores the mesh and records nothing (D3, N1)

Deliberately not named `test_application_*` (that set is re-run by T-R5c).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core.mesh import SymmetryDefinition
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_nearest_vertex

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)

W = Input("key", "w")
C = Input("key", "c")
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
LMB = Input("mouse", "LEFT")
ALT_LMB = Input("mouse", "LEFT", frozenset({"alt"}))
ALT_SHIFT_LMB = Input("mouse", "LEFT", frozenset({"alt", "shift"}))

X_SYMMETRY = SymmetryDefinition(
    plane_point=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0), seam_edges=frozenset()
)


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _screen(app, vid):
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT)


def _visible(app) -> list:
    mesh = app.scene.mesh
    hits = []
    for vid in sorted(mesh.all_vertex_ids()):
        sx, sy = _screen(app, vid)
        if pick_nearest_vertex(app.camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) == vid:
            hits.append(vid)
    assert len(hits) >= 2
    return hits


def _click(app, x, y, inp=LMB):
    app.pointer_press(inp, x, y)
    return app.pointer_release(inp.value, x, y)


def _set_symmetry(app, definition):
    def mutate():
        app.scene.mesh.symmetry_definition = definition
        return set()

    return mutate


def _w_move(app, vid):
    app.pointer_motion(*_screen(app, vid))
    assert app.key_press(W)
    for _ in range(3):
        app.pointer_motion(400, 300, 12.0, 7.0)
    assert app.key_release(W)


def _bookkeeping(app):
    return (
        app.scene.mesh.export_state(),
        list(app.history._undo_stack),
        list(app.history._redo_stack),
        list(app._selection_undo_stack),
        list(app._selection_redo_stack),
    )


# -- T-R2d ----------------------------------------------------------------------


def test_interaction_owner_follows_application_gates(app):
    """T-R2d: non-None exactly where `Application`'s own gates apply (armed,
    running, Knife); None idle and during an orbit or pan."""
    assert app.interaction_owner is None
    vid = _visible(app)[0]
    app.pointer_motion(*_screen(app, vid))
    assert app.key_press(W)
    assert app.interaction_owner == "transform"  # armed
    app.pointer_motion(400, 300, 5.0, 0.0)
    assert app.transform_interacting
    assert app.interaction_owner == "transform"  # running
    app.key_release(W)
    assert app.interaction_owner is None

    for nav in (ALT_LMB, ALT_SHIFT_LMB):  # orbit, pan
        app.pointer_press(nav, 100, 100)
        app.pointer_drag(10.0, 0.0, 110, 100)
        assert app.pointer.active
        assert app.interaction_owner is None
        app.pointer_release(nav.value, 110, 100)

    app.pointer_motion(*MISS)
    app.selection.clear()
    assert app.key_press(C)
    assert app.knife_active
    assert app.interaction_owner == "knife"
    app.key_press(Input("key", "ESCAPE"))
    assert app.interaction_owner is None


# -- T-R4c ----------------------------------------------------------------------


def test_mirror_alignment_probe_p3(app):
    """T-R4c (probe P3, at Application level): select A → W-move → select B →
    external change via `apply_mesh_change` → Ctrl+Z restores {B} and undoes
    the external change; Ctrl+Z again restores {A} and undoes the Move."""
    a, b = _visible(app)[:2]
    _click(app, *_screen(app, a))
    assert app.selection.vertices == {a}
    moved_state = None
    _w_move(app, a)
    moved_state = app.scene.mesh.export_state()
    _click(app, *_screen(app, b))
    assert app.selection.vertices == {b}

    assert app.apply_mesh_change("Symmetry x", _set_symmetry(app, X_SYMMETRY)) is True
    assert app.scene.mesh.symmetry_definition == X_SYMMETRY
    assert app.history._undo_stack[-1].description == "Symmetry x"

    assert app.key_press(CTRL_Z)
    assert app.selection.vertices == {b}
    assert app.scene.mesh.symmetry_definition is None
    assert app.scene.mesh.export_state() == moved_state

    assert app.key_press(CTRL_Z)
    assert app.selection.vertices == {a}
    assert not app.history.can_undo()

    assert app.key_press(Input("key", "y", frozenset({"ctrl"})))
    assert app.key_press(Input("key", "y", frozenset({"ctrl"})))
    assert app.scene.mesh.symmetry_definition == X_SYMMETRY
    assert app.selection.vertices == {b}


def test_no_change_records_nothing(app):
    """T-R4c: a `mutate` that changes nothing returns False, no history entry."""
    before = _bookkeeping(app)
    serial = app.status_serial
    assert app.apply_mesh_change("nothing", lambda: set()) is False
    assert app.apply_mesh_change("nothing", lambda: None) is False
    assert _bookkeeping(app) == before
    assert not app.history.can_undo()
    assert app.status_serial == serial


def test_entry_is_one_mesh_state_command_and_notifies_viewport(app, monkeypatch):
    vid = _visible(app)[0]
    calls = []
    monkeypatch.setattr(app.viewport, "on_vertices_moved", lambda ids: calls.append(("moved", ids)))
    monkeypatch.setattr(app.viewport, "on_topology_changed", lambda: calls.append(("topology",)))
    x, y, z = app.scene.mesh.vertex_position(vid)

    def move():
        app.scene.mesh.set_vertex_position(vid, (x, y + 0.25, z))
        return {vid}

    assert app.apply_mesh_change("Nudge", move) is True
    assert calls == [("moved", {vid})]
    assert len(app.history._undo_stack) == 1
    assert len(app._selection_undo_stack) == 1

    calls.clear()
    assert app.apply_mesh_change("Symmetry x", _set_symmetry(app, X_SYMMETRY)) is True
    assert calls == [("moved", set())]
    calls.clear()

    def topology():
        app.scene.mesh.symmetry_definition = None
        return None

    assert app.apply_mesh_change("Symmetry off", topology) is True
    assert calls == [("topology",)]


# -- T-R4d ----------------------------------------------------------------------


def test_pick_cache_invalidated_hover_and_click_find_new_positions(app):
    """T-R4d: after an external change, hover and a click pick the *new*
    vertex position without any camera change."""
    vid = _visible(app)[0]
    old_xy = _screen(app, vid)
    app.pointer_motion(*old_xy)  # fills the pick cache at the old positions
    assert app.selection.hovered == vid
    revision = app.camera.camera_revision
    x, y, z = app.scene.mesh.vertex_position(vid)

    def pull_out():
        app.scene.mesh.set_vertex_position(vid, (x * 1.6, y * 1.6, z * 1.6))
        return {vid}

    assert app.apply_mesh_change("Pull", pull_out)
    assert app.camera.camera_revision == revision
    new_xy = _screen(app, vid)
    assert abs(new_xy[0] - old_xy[0]) + abs(new_xy[1] - old_xy[1]) > 40
    # The re-pick at the resting cursor (old position) no longer finds it.
    assert app.selection.hovered != vid

    app.pointer_motion(*new_xy)
    assert app.selection.hovered == vid
    _click(app, *new_xy)
    assert app.selection.vertices == {vid}


# -- T-R4e ----------------------------------------------------------------------


def _never_called(calls):
    def mutate():
        calls.append("called")
        return set()

    return mutate


def test_raises_before_mutate_while_transform_armed_or_running(app):
    """T-R4e (D3): raises while a transform is armed or running, `mutate` is
    not called, mesh / history / mirror stacks unchanged."""
    vid = _visible(app)[0]
    app.pointer_motion(*_screen(app, vid))
    assert app.key_press(W)
    calls = []
    before = _bookkeeping(app)
    with pytest.raises(RuntimeError):
        app.apply_mesh_change("x", _never_called(calls))
    assert calls == [] and _bookkeeping(app) == before
    app.pointer_motion(400, 300, 6.0, 0.0)
    running = _bookkeeping(app)
    with pytest.raises(RuntimeError):
        app.apply_mesh_change("x", _never_called(calls))
    assert calls == [] and _bookkeeping(app) == running
    assert app.transform_command == commands.MOVE


def test_raises_before_mutate_during_knife_session(app):
    """T-R4e (D3, N5): same during a Knife session."""
    app.pointer_motion(*MISS)
    assert app.key_press(C)
    assert app.knife_active
    calls = []
    before = _bookkeeping(app)
    with pytest.raises(RuntimeError):
        app.apply_mesh_change("x", _never_called(calls))
    assert calls == [] and _bookkeeping(app) == before
    assert app.knife_active


def test_raising_mutate_restores_mesh_and_records_nothing(app):
    """T-R4e (N1): a `mutate` that raises midway → mesh restored to the
    snapshot, no history entry, the exception propagates."""
    vid = _visible(app)[0]
    before = _bookkeeping(app)

    def half_then_fail():
        app.scene.mesh.symmetry_definition = X_SYMMETRY
        app.scene.mesh.set_vertex_position(vid, (9.0, 9.0, 9.0))
        raise ValueError("midway")

    with pytest.raises(ValueError, match="midway"):
        app.apply_mesh_change("broken", half_then_fail)
    assert _bookkeeping(app) == before
    assert app.scene.mesh.symmetry_definition is None
