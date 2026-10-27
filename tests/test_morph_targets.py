"""AD-025 Phase 3: one persistent morph target in Production (several targets: `test_morph_multi.py`) (`mirai.morph_targets`, `Application`).

Headless (TraceStore). Covers the Definition of Done of the Phase 3 package: target lifecycle with
exact Undo / Redo; offsets bit-exact after save -> load; the editing view beside the base (H4) - a
gesture on it is exactly one Undo step that writes only the touched offsets, topology tools are refused
on it with a status, Undo / Redo follow; Delete / Dissolve on the base keep the survivors' offsets; C-1
(a whole-mesh rotate in 1/2/3 leaves offsets bit-identical); the weight is no history entry and not
saved; the mix display (H7 / H7-E) and its slot; the Morph Lab bridge. Apply transform with targets is
in `test_layer_gate.py` (`test_apply_transform_maps_the_targets`).
"""

from __future__ import annotations

import json

import pytest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from mirai import morph_targets
from mirai.interaction import commands
from mirai.interaction.input import MORPH_CONTEXT, Input
from tests.mesh_invariants import assert_layer_invariants
from tests.test_application_delete_dissolve import _app, _edge, _grid_face, _grid_vertex, _select

V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


CTRL_N, CTRL_SHIFT_N, ALT_SHIFT_N = _key("n", "ctrl"), _key("n", "ctrl", "shift"), _key("n", "alt", "shift")
TAB, N, PLUS, MINUS = _key("tab"), _key("n"), _key("plus"), _key("minus")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")


def _offsets(mesh) -> dict:
    lid = morph_targets.morph_target(mesh)
    return {} if lid is None else dict(mesh.layer_items(lid))


def _drag(app, key: str, steps=((12.0, -7.0), (9.0, 4.0), (5.0, 5.0))) -> None:
    assert app.key_press(_key(key)), app.status_message
    for dx, dy in steps:
        app.pointer_motion(400, 300, dx, dy)
    app.key_release(_key(key))


def _with_target(n: int = 3):
    app = _app(n)
    assert app.key_press(CTRL_N), app.status_message
    return app, app.scene.edit_object


def _sculpt(app, vertices, key: str = "w"):
    """Tab into the view, move `vertices`, Tab back (returns the history length after the move)."""
    assert app.key_press(TAB), app.status_message
    _select(app, V, set(vertices))
    _drag(app, key)
    length = len(app.history)
    assert app.key_press(TAB), app.status_message
    return length


def _view_equals_base_plus_offsets(app) -> None:
    view = app._target_view
    base, lid, mesh = view.base_mesh, view.lid, view.view_mesh
    assert sorted(mesh.all_vertex_ids()) == sorted(base.all_vertex_ids())
    for v in base.all_vertex_ids():
        b, d = base.vertex_position(v), base.layer_value(lid, v)
        assert tuple(mesh.vertex_position(v)) == (b[0] + d[0], b[1] + d[1], b[2] + d[2]), v


# -- keys -----------------------------------------------------------------------------------------


def test_morph_keys_are_free_and_resolve_in_their_context():
    app = _app()
    for entry in morph_targets.MORPH_KEYS:
        assert app.bindings.command_for(entry.input) is None, entry
        assert app.bindings.command_for(entry.input, MORPH_CONTEXT) == entry.command
    assert {e.command for e in morph_targets.MORPH_KEYS} == morph_targets.MORPH_COMMANDS


def test_morph_keys_avoid_the_morph_lab_keys():
    lab_keys = {
        _key("up", "alt"), _key("down", "alt"), _key("up", "alt", "shift"), _key("down", "alt", "shift"),
        _key("up", "ctrl"), _key("down", "ctrl"), _key("m"), _key("b", "alt"), _key("right", "alt"),
        _key("left", "alt"), _key("right", "alt", "shift"), _key("left", "alt", "shift"), _key("j"),
        _key("j", "shift"), _key("comma"), _key("period"),
    }
    assert not lab_keys & {e.input for e in morph_targets.MORPH_KEYS}


# -- lifecycle --------------------------------------------------------------------------------------


def test_create_rename_delete_each_one_exact_undo_step():
    app = _app(3)
    mesh = app.scene.mesh
    start = mesh.export_state()
    states = [start]
    assert app.key_press(CTRL_N)
    assert [mesh.point_layer_info(l).name for l in mesh.point_layer_ids()] == ["Target 1"]
    states.append(mesh.export_state())
    assert app.key_press(CTRL_SHIFT_N)
    assert mesh.point_layer_info(mesh.point_layer_ids()[0]).name == morph_targets.RENAME_CYCLE[0]
    states.append(mesh.export_state())
    lid = mesh.point_layer_ids()[0]
    v = mesh.all_vertex_ids()[3]
    assert app.apply_mesh_change("offset", lambda: mesh.set_layer_value(lid, v, (0.1, 0.2, 0.3)))
    states.append(mesh.export_state())
    assert app.key_press(ALT_SHIFT_N)
    assert mesh.point_layer_ids() == []
    states.append(mesh.export_state())
    assert len(app.history) == 4 and len(app._selection_undo_stack) == 4
    assert all(entry[2] is False for entry in app._selection_undo_stack)  # layer-only: no topology step
    def content(state):  # ID counters only move forward (AD-001), the rest is exact
        return {k: v for k, v in state.items() if not k.endswith("_counter")}

    for state in reversed(states[:-1]):
        assert app.key_press(CTRL_Z)
        assert content(mesh.export_state()) == content(state)
        assert_layer_invariants(mesh)
    for state in states[1:]:
        assert app.key_press(CTRL_Y)
        assert mesh.export_state() == state | {"layer_id_counter": 2}


def test_a_second_target_is_allowed_since_phase4():
    """Phase 3 allowed one target per mesh; Phase 4 lifts the cap (`test_morph_multi.py`)."""
    app, _ = _with_target()
    assert app.key_press(CTRL_N) is True and len(app.scene.mesh.point_layer_ids()) == 2


def test_rename_and_delete_without_a_target_are_refused():
    app = _app(2)
    assert app.key_press(CTRL_SHIFT_N) is False and "no target" in app.status_message
    assert app.key_press(ALT_SHIFT_N) is False and "no target" in app.status_message
    assert app.key_press(TAB) is False and "no target" in app.status_message
    assert app.key_press(PLUS) is False and len(app.history) == 0


def test_rename_takes_any_free_name():
    app, base = _with_target()
    assert app.rename_morph_target("Lächeln") is True
    assert base.mesh.point_layer_info(base.mesh.point_layer_ids()[0]).name == "Lächeln"
    assert app.rename_morph_target("Lächeln") is False


# -- save / load ------------------------------------------------------------------------------------


def test_offsets_are_bit_exact_after_save_and_load(tmp_path):
    app, base = _with_target()
    mesh = base.mesh
    lid = mesh.point_layer_ids()[0]
    values = {v: (0.1 * int(v) + 1e-17, -1.0 / 3.0, 2.0 ** -40) for v in mesh.all_vertex_ids()[::2]}
    app.apply_mesh_change("offsets", lambda: [mesh.set_layer_value(lid, v, d) for v, d in values.items()])
    path = tmp_path / "t.mirai.json"
    assert app.save_scene_file(path)
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 5
    app.load_scene("file", scene_path=path)
    loaded = app.scene.mesh
    assert dict(loaded.layer_items(loaded.point_layer_ids()[0])) == values
    assert loaded.point_layer_info(loaded.point_layer_ids()[0]).name == "Target 1"


def test_saving_while_the_view_is_open_writes_the_base_without_the_view(tmp_path):
    app, base = _with_target()
    v = _grid_vertex(app, 1, 1)
    assert app.key_press(TAB)
    _select(app, V, {v})
    _drag(app, "w")
    offsets = _offsets(base.mesh)
    path = tmp_path / "v.mirai.json"
    assert app.save_scene_file(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert [o["name"] for o in data["objects"]] == [base.name]
    assert app.morph_view_open  # saving changes nothing in the session
    app.load_scene("file", scene_path=path)
    assert not app.morph_view_open and len(app.scene.objects) == 1
    assert _offsets(app.scene.mesh) == offsets


# -- the editing view (H4) --------------------------------------------------------------------------


def test_view_is_beside_the_base_and_equals_base_plus_offsets():
    app, base = _with_target()
    v = _grid_vertex(app, 1, 1)
    app.apply_mesh_change("offset", lambda: base.mesh.set_layer_value(base.mesh.point_layer_ids()[0], v, (0.0, 0.0, 0.5)))
    history, objects = len(app.history), len(app.scene.objects)
    assert app.key_press(TAB)
    view = app.scene.edit_object
    assert view.id != base.id and len(app.scene.objects) == objects + 1
    assert view.transform.translation[0] > base.transform.translation[0]  # beside, along +X
    assert len(app.history) == history  # opening is no Undo step
    _view_equals_base_plus_offsets(app)
    assert view.mesh.point_layer_ids() == []
    assert app.key_press(TAB)
    assert app.scene.edit_object_id == base.id and len(app.scene.objects) == objects
    assert len(app.history) == history


@pytest.mark.parametrize("key", ["w", "e", "r"])
def test_a_gesture_on_the_view_is_one_undo_step_writing_only_touched_offsets(key):
    app, base = _with_target()
    mesh = base.mesh
    lid = mesh.point_layer_ids()[0]
    far = _grid_vertex(app, 3, 3)
    app.apply_mesh_change("far offset", lambda: mesh.set_layer_value(lid, far, (0.0, 0.0, 0.25)))
    touched = {_grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2), _grid_vertex(app, 2, 1)}
    positions = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    assert app.key_press(TAB)
    view_mesh = app.scene.mesh
    untouched_view = {v: view_mesh.vertex_position(v) for v in view_mesh.all_vertex_ids() if v not in touched}
    history, mirror = len(app.history), len(app._selection_undo_stack)
    _select(app, V, touched)
    _drag(app, key)
    assert len(app.history) == history + 1 and len(app._selection_undo_stack) == mirror + 1
    command = app.history._undo_stack[-1]
    assert command.mesh is mesh  # the step lives on the base, not on the transient view
    assert set(command.delta.layer_values[lid]) == touched
    assert not (command.delta.vertices or command.delta.edges or command.delta.faces)
    assert {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()} == positions  # rest shape untouched
    assert mesh.layer_value(lid, far) == (0.0, 0.0, 0.25)
    assert {v: view_mesh.vertex_position(v) for v in untouched_view} == untouched_view
    _view_equals_base_plus_offsets(app)
    assert_layer_invariants(mesh)
    assert app.key_press(CTRL_Z)
    assert set(_offsets(mesh)) == {far}
    _view_equals_base_plus_offsets(app)
    assert app.key_press(CTRL_Y)
    assert set(_offsets(mesh)) == touched | {far}
    _view_equals_base_plus_offsets(app)


def test_tweak_soft_and_smooth_on_the_view_write_offsets():
    app, base = _with_target(4)
    mesh = base.mesh
    centre = _grid_vertex(app, 2, 2)
    for vid in mesh.all_vertex_ids():  # a bumpy base, so Smooth has something to do
        x, y, _ = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (x, y, 0.3 * ((int(vid) * 7) % 3)))
    assert app.key_press(TAB)
    _select(app, V, {centre})
    assert app.key_press(_key("o"))  # Soft on
    for _ in range(12):  # the radius over the one-ring (grid spacing 1)
        app.dispatch_command(commands.SOFT_RADIUS_UP)
    _drag(app, "w")
    soft = set(_offsets(mesh))
    assert centre in soft and len(soft) > 1
    assert app.key_press(_key("o"))  # Soft off
    history = len(app.history)
    _select(app, V, {centre, _grid_vertex_of(base, 1, 1)})
    _drag(app, "s", steps=((30.0, 0.0), (30.0, 0.0)))
    assert len(app.history) == history + 1
    assert app.history._undo_stack[-1].mesh is mesh
    _view_equals_base_plus_offsets(app)
    history = len(app.history)
    _select(app, V, {centre})  # Tweak (Ctrl+LMB drag) moves the selection
    app.pointer_press(Input("mouse", "LEFT", frozenset({"ctrl"})), 400, 300)
    for i in range(1, 4):
        app.pointer_drag(10.0, 0.0, 400 + 10 * i, 300)
    app.pointer_release("LEFT", 430, 300)
    assert len(app.history) == history + 1, app.status_message
    assert app.history._undo_stack[-1].mesh is mesh
    _view_equals_base_plus_offsets(app)


def _grid_vertex_of(obj, r, c):
    mesh = obj.mesh
    return next(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (float(c), float(r)))


def _base_only_cases():
    def split(app, ids):
        _select(app, E, {ids["edge"]})
        return _key("c")

    def connect_vertices(app, ids):
        _select(app, V, {ids["a"], ids["c"]})
        return _key("c")

    def delete(app, ids):
        _select(app, F, {ids["face"]})
        return _key("delete")

    def dissolve(app, ids):
        _select(app, E, {ids["edge"]})
        return _key("backspace")

    def collapse(app, ids):
        _select(app, E, {ids["edge"]})
        return _key("c", "shift")

    def extrude(app, ids):
        _select(app, F, {ids["face"]})
        return _key("t")

    def loop_insert(app, ids):
        _select(app, E, {ids["edge"]})
        return _key("i")

    def cap(app, ids):
        _select(app, E, {ids["edge"]})
        return _key("b", "shift")

    def knife(app, ids):
        app.selection.clear()
        return _key("c")

    def symmetry(app, ids):
        return _key("s", "shift")

    def new_group(app, ids):
        _select(app, F, {ids["face"]})
        return _key("g", "ctrl")

    def object_mode(app, ids):
        return _key("4")

    def new_target(app, ids):
        return CTRL_N

    def delete_target(app, ids):
        return ALT_SHIFT_N

    return {
        "split": split, "vertex_connect": connect_vertices, "delete": delete, "dissolve": dissolve,
        "collapse": collapse, "extrude": extrude, "loop_insert": loop_insert, "cap": cap, "knife": knife,
        "symmetry": symmetry, "new_group": new_group, "object_mode": object_mode,
        "new_target": new_target, "delete_target": delete_target,
    }


@pytest.mark.parametrize("case", list(_base_only_cases()))
def test_topology_and_base_only_commands_are_refused_on_the_view(case):
    app, base = _with_target()
    ids = {
        "a": _grid_vertex(app, 1, 1), "c": _grid_vertex(app, 2, 2), "face": _grid_face(app, 1, 1),
        "edge": _edge(base.mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 2, 1)),
    }
    assert app.key_press(TAB)
    key = _base_only_cases()[case](app, ids)
    view = app.scene.edit_object
    before = (base.mesh.export_state(), view.mesh.export_state(), len(app.history), app.selection.mode)
    assert app.key_press(key) is False
    assert "on the base only" in app.status_message, app.status_message
    assert app.interaction_owner is None and app.scene.edit_object_id == view.id
    assert (base.mesh.export_state(), view.mesh.export_state(), len(app.history), app.selection.mode) == before


def test_add_object_is_refused_on_the_view():
    app, _ = _with_target()
    assert app.key_press(TAB)
    objects = len(app.scene.objects)
    assert app.add_primitive("sphere") is None
    assert "on the base only" in app.status_message and len(app.scene.objects) == objects


def test_the_backstop_reverts_a_topology_change_on_the_view():
    """A host (`apply_mesh_change`) bypasses the key gate: `TargetView.translate` reverts what is not a
    position change and keeps nothing; the selection mirror stays 1:1 with the history."""
    app, base = _with_target()
    assert app.key_press(TAB)
    view = app.scene.mesh
    before = (base.mesh.export_state(), view.export_state(), len(app.history), len(app._selection_undo_stack))
    face = view.all_face_ids()[0]
    assert app.apply_mesh_change("host deletes a face", lambda: view.delete_faces([face])) is True
    assert "topology only on the base" in app.status_message
    assert (base.mesh.export_state(), view.export_state(), len(app.history), len(app._selection_undo_stack)) == before


def test_a_host_position_change_on_the_view_becomes_an_offset():
    app, base = _with_target()
    v = _grid_vertex(app, 1, 1)
    assert app.key_press(TAB)
    view = app.scene.mesh
    x, y, z = view.vertex_position(v)
    assert app.apply_mesh_change("host moves", lambda: view.set_vertex_position(v, (x, y, z + 1.0)) or {v})
    assert _offsets(base.mesh) == {v: (0.0, 0.0, 1.0)}
    assert app.history._undo_stack[-1].mesh is base.mesh


def test_undo_of_an_older_step_closes_the_view_and_returns_to_the_base():
    app, base = _with_target()
    assert app.key_press(TAB)
    assert app.key_press(CTRL_Z)  # the "New morph target" step: the base was its edit object
    assert not app.morph_view_open and app.scene.edit_object_id == base.id
    assert len(app.scene.objects) == 1 and base.mesh.point_layer_ids() == []
    assert app.key_press(CTRL_Y) and base.mesh.point_layer_ids()


def test_undo_of_a_view_step_after_closing_the_view_changes_the_offsets_on_the_base():
    app, base = _with_target()
    v = _grid_vertex(app, 1, 1)
    _sculpt(app, {v})
    assert v in _offsets(base.mesh) and not app.morph_view_open
    assert app.key_press(CTRL_Z)
    assert _offsets(base.mesh) == {} and app.scene.edit_object_id == base.id
    assert app.key_press(CTRL_Y)
    assert v in _offsets(base.mesh)


def test_the_view_cannot_be_opened_in_object_mode_or_during_a_gesture():
    app, _ = _with_target()
    assert app.key_press(_key("4"))
    assert app.key_press(TAB) is False and "1/2/3" in app.status_message
    assert app.key_press(_key("1"))
    _select(app, V, {app.scene.mesh.all_vertex_ids()[0]})
    assert app.key_press(_key("w"))
    assert app.key_press(TAB) is False and not app.morph_view_open
    app.key_release(_key("w"))


# -- base edits with a target -----------------------------------------------------------------------


def test_delete_and_dissolve_on_the_base_keep_the_survivors_offsets():
    app, base = _with_target()
    mesh = base.mesh
    _sculpt(app, set(mesh.all_vertex_ids()))
    before = _offsets(mesh)
    assert len(before) == len(mesh.all_vertex_ids())
    _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 2, 1))})
    assert app.key_press(_key("backspace")), app.status_message
    _select(app, F, {_grid_face(app, 0, 0)})
    assert app.key_press(_key("delete")), app.status_message
    survivors = set(mesh.all_vertex_ids())
    assert survivors < set(before)
    assert _offsets(mesh) == {v: d for v, d in before.items() if v in survivors}
    assert_layer_invariants(mesh)
    assert app.key_press(TAB)  # the view follows the new topology
    _view_equals_base_plus_offsets(app)


def test_c1_whole_mesh_rotate_in_component_mode_leaves_offsets_bit_identical():
    """C-1 (Manu 2026-10-27): rotating / scaling the whole mesh in 1/2/3 is an edit."""
    app, base = _with_target()
    mesh = base.mesh
    _sculpt(app, {_grid_vertex(app, 1, 1), _grid_vertex(app, 2, 2)})
    before = _offsets(mesh)
    positions = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    for key in ("e", "r"):
        _select(app, V, set(mesh.all_vertex_ids()))
        _drag(app, key)
    assert {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()} != positions
    assert _offsets(mesh) == before


# -- weight and display -----------------------------------------------------------------------------


def test_the_weight_is_view_state_no_history_not_saved(tmp_path):
    app, base = _with_target()
    _sculpt(app, {_grid_vertex(app, 1, 1)})
    history, mirror = len(app.history), len(app._selection_undo_stack)
    state = base.mesh.export_state()
    for key in (PLUS, PLUS, _key("plus", "shift"), MINUS, _key("plus", "alt")):
        assert app.key_press(key)
    assert app.morph_weight == 100
    assert app.key_press(_key("minus", "alt")) and app.morph_weight == 0
    assert app.key_press(N) and app.key_release(N) and app.morph_weight == 100  # tap: 0 <-> last
    assert (len(app.history), len(app._selection_undo_stack)) == (history, mirror)
    assert base.mesh.export_state() == state
    path = tmp_path / "w.mirai.json"
    app.save_scene_file(path)
    assert "weight" not in path.read_text(encoding="utf-8").lower()
    app.load_scene("file", scene_path=path)
    assert app.morph_weight == 0


def test_the_weight_drag_follows_the_mouse():
    app, _ = _with_target()
    assert app.key_press(N)
    app.pointer_motion(400, 300, 30 * morph_targets.DRAG_PIXELS_PER_PERCENT, 0.0)
    assert app.morph_weight == 30
    app.pointer_motion(400, 300, -10 * morph_targets.DRAG_PIXELS_PER_PERCENT, 0.0)
    assert app.key_release(N) and app.morph_weight == 20  # a drag is no tap
    assert len(app.history) == 1  # only the "New morph target" step


def test_the_mix_is_shown_on_the_base_and_beside_the_view():
    app, base = _with_target()
    v, w = _grid_vertex(app, 1, 1), _grid_vertex(app, 3, 3)
    _sculpt(app, {v})
    mesh = base.mesh
    lid = mesh.point_layer_ids()[0]
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is None  # 0 %: no surface, the base itself
    app.set_morph_weight(40)
    app.update_viewport(0.0)
    provider = app.morph.provider
    assert app.viewport.surface_provider is provider and app.viewport.surface_render_mesh is not None
    surface = provider.surface_mesh
    b, d = mesh.vertex_position(v), mesh.layer_value(lid, v)
    assert tuple(surface.vertex_position(v)) == tuple(bi + 0.4 * di for bi, di in zip(b, d))
    assert tuple(surface.vertex_position(w)) == mesh.vertex_position(w)  # no offset: exactly the base
    app.set_morph_weight(100)
    app.update_viewport(0.0)
    assert provider.last_changed == 1  # a weight step touches the stored offsets only
    assert tuple(surface.vertex_position(v)) == tuple(bi + di for bi, di in zip(b, d))
    assert app.key_press(TAB)  # H7-E: the base beside the view shows the mix
    app.update_viewport(0.0)
    assert set(provider.entry_surfaces) == {base.id} and base.id in app.viewport.entry_surface_render_meshes
    _select(app, V, {w})
    _drag(app, "w")
    app.update_viewport(0.0)
    entry = provider.entry_surfaces[base.id]
    assert tuple(entry.vertex_position(w)) == tuple(
        bi + di for bi, di in zip(mesh.vertex_position(w), mesh.layer_value(lid, w))
    )
    assert app.key_press(TAB)
    app.set_morph_weight(0)
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is None


def test_the_subd_preview_and_the_mix_show_together_since_phase4():
    """Phase 3: whoever held the H7 slot kept it. Phase 4 (H5b): the stage chain shows SubD of the mix
    (`test_morph_multi.py` pins the values)."""
    app, _ = _with_target()
    assert app.subdivision.set_view("cage")
    app.update_viewport(0.0)
    app.set_morph_weight(50)
    app.update_viewport(0.0)
    assert app.surface_chain.holds(app.morph.provider) and app.surface_chain.holds(app.subdivision.provider)
    assert not app.morph.blocked and "hidden" not in app.morph_status_text()


def test_without_a_target_nothing_takes_the_slot():
    app = _app(3)
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is None and app.morph_status_text() is None


# -- Morph Lab bridge -------------------------------------------------------------------------------


def test_the_bridge_sends_the_base_while_the_view_is_open(tmp_path):
    from morph_bridge import send_to_morph_lab

    app, base = _with_target()
    _sculpt(app, {_grid_vertex(app, 1, 1)})
    assert app.key_press(TAB)
    sent = []
    path = send_to_morph_lab(app, directory=tmp_path, launcher=sent.append)
    assert path is not None and sent == [path]
    data = json.loads(path.read_text(encoding="utf-8"))
    assert [o["name"] for o in data["objects"]] == [base.name]
    assert data["objects"][0]["mesh"]["point_layers"][0]["values"]


def test_the_hud_shows_a_morph_row_only_with_a_target():
    from hud import hud_rows, hud_state, key_hints

    app = _app(2)
    assert "Morph" not in {r.label for r in hud_rows(hud_state(app), key_hints(app.bindings))}
    app.key_press(CTRL_N)
    app.key_press(PLUS)
    row = {r.label: r for r in hud_rows(hud_state(app), key_hints(app.bindings))}["Morph"]
    assert row.value == "Target 1 · 10 % · base" and row.keys == "Ctrl+N/TAB/N"
    app.key_press(TAB)
    row = {r.label: r for r in hud_rows(hud_state(app), key_hints(app.bindings))}["Morph"]
    assert "editing target" in row.value


def test_the_evaluated_surface_equals_the_definition_through_random_edits():
    """`_Surface` patches from the journal; after every step it must equal `blend(b, d, w)` everywhere
    (an oracle over every vertex), through weight steps, base moves, offset writes (per element and
    bulk), deletions, the Phase 5 topology edits (split_edge, split_face with origins, Collapse -
    patched into the surface in place, AD-025 §16) and Undo / Redo."""
    import random

    from core import PointLayerInfo

    app = _app(4)
    mesh = app.scene.mesh
    lid = mesh.add_point_layer(PointLayerInfo("T"))
    provider = morph_targets.MorphSurfaceProvider(lambda: app.scene)
    oid = app.scene.edit_object_id
    rng = random.Random(7)

    def check():
        provider.sync(mesh, app.selection)
        surface = provider.surface_mesh
        w = provider.weight(oid)
        if w == 0:
            assert surface is None
            return
        assert sorted(surface.all_vertex_ids()) == sorted(mesh.all_vertex_ids())
        assert {f: surface.face_vertices(f) for f in surface.all_face_ids()} == {
            f: mesh.face_vertices(f) for f in mesh.all_face_ids()}
        assert {e: (surface.edge_vertices(e), surface.edge_faces(e)) for e in surface.all_edge_ids()} == {
            e: (mesh.edge_vertices(e), mesh.edge_faces(e)) for e in mesh.all_edge_ids()}
        for v in mesh.all_vertex_ids():
            assert tuple(surface.vertex_position(v)) == morph_targets.blend(
                mesh.vertex_position(v), mesh.layer_value(lid, v), w
            ), v

    from core.operations.collapse import collapse_elements

    surfaces = set()
    for step in range(160):
        ids = mesh.all_vertex_ids()
        op = rng.randrange(9)
        if op == 0:
            provider.set_weight(oid, rng.randrange(0, 101))
        elif op == 1:
            v = rng.choice(ids)
            mesh.set_vertex_position(v, tuple(c + rng.uniform(-0.1, 0.1) for c in mesh.vertex_position(v)))
        elif op == 2:
            v = rng.choice(ids)
            d = (0.0, 0.0, 0.0) if rng.random() < 0.3 else tuple(rng.uniform(-1, 1) for _ in range(3))
            mesh.set_layer_value(lid, v, d)
        elif op == 3:
            mesh.map_vector_layers(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
        elif op == 4 and len(mesh.all_face_ids()) > 4:
            face = rng.choice(mesh.all_face_ids())
            app.apply_mesh_change("delete", lambda: mesh.delete_faces([face]))
        elif op == 5 and app.history.can_undo():
            app.dispatch_command(commands.UNDO if rng.random() < 0.6 else commands.REDO)
        elif op == 6:
            edge = rng.choice(mesh.all_edge_ids())
            t = rng.uniform(0.2, 0.8)
            app.apply_mesh_change("split", lambda: mesh.split_edge(edge, t) and None)
        elif op == 7:
            face = rng.choice(mesh.all_face_ids())
            a, b, c = mesh.face_vertices(face)[:3]
            p = tuple(sum(mesh.vertex_position(x)[k] for x in (a, b, c)) / 3.0 for k in range(3))
            app.apply_mesh_change(
                "cut", lambda: mesh.split_face(face, a, c, [p], origins=[((a, 0.25), (b, 0.5), (c, 0.25))]) and None
            )
        elif op == 8:
            edge = rng.choice(mesh.all_edge_ids())
            try:
                app.apply_mesh_change("collapse", lambda: collapse_elements(mesh, mesh.edge_vertices(edge)) and None)
            except Exception:
                pass  # a refused collapse leaves everything as it was
        if provider.weight(oid) == 0 and rng.random() < 0.5:
            provider.set_weight(oid, 50)
        check()
        if provider.surface_mesh is not None:
            surfaces.add(id(provider.surface_mesh))
    assert len(surfaces) <= 3  # patched in place, not rebuilt per topology edit


def test_the_wire_follows_the_mix_while_selection_stays_on_the_rest_shape():
    """Manu 2026-10-27: during the N drag the wireframe must move with the polygons."""
    from viewport import edge_segments

    app, base = _with_target()
    v = _grid_vertex(app, 1, 1)
    _sculpt(app, {v})
    mesh = base.mesh
    app.viewport.show_edges = True
    app.update_viewport(0.0)
    assert app.viewport.edge_segments == edge_segments(mesh)  # 0 %: the rest shape
    for weight in (30, 100):
        app.set_morph_weight(weight)
        app.update_viewport(0.0)
        surface = app.morph.provider.surface_mesh
        assert app.viewport.edge_segments == edge_segments(surface) != edge_segments(mesh)
    _select(app, V, {v})
    app.viewport.on_selection_changed()
    app.update_viewport(0.0)
    assert any(tuple(p) == mesh.vertex_position(v) for layer in app.viewport.point_positions.values() for p in layer)
    app.set_morph_weight(0)
    app.update_viewport(0.0)
    assert app.viewport.edge_segments == edge_segments(mesh)
