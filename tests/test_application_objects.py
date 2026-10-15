"""AD-021 M1 — a second object as Reference in the production `Application`.

Headless (TraceStore), no pyglet. Covers the M1 acceptance rows of AD-021 §6 and the rules
§4.4 (Drawing), §4.6 (App consequences, R-9), §4.7 RF-1…RF-6, §5.2 (scene reset on load, R-4)
and the answers Q-1 (locked), Q-2 (pick through), Q-3 (Undo steps), Q-9 (camera stays),
Q-10 (add instead of load). Nothing from M2 (no transform, no edit-object change).

The second object is either the built-in cube (via `add_reference("cube")`) or a large plate
written as an OBJ between the camera and the edit cube, so a Reference really lies in front.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from core import ObjectId, ObjectState, SelectionMode, VertexId
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.scene_objects import REFERENCE_BASE_COLOR
from mirai.viewport.picking import pick_nearest_vertex
from viewport.gl_render_store import DEFAULT_BASE_COLOR

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


ONE, FOUR = _key("1"), _key("4")
W, C, T = _key("w"), _key("c"), _key("t")
DELETE = _key("delete")
SHIFT_S = _key("s", "shift")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _click(app: Application, x: float, y: float, *modifiers: str) -> None:
    app.pointer_press(Input("mouse", "LEFT", frozenset(modifiers)), x, y)
    app.pointer_release("LEFT", x, y)


def _screen(app: Application, point) -> tuple[float, float]:
    return app.camera.project_to_screen(point, WIDTH, HEIGHT)


def _front_vertex(app: Application) -> VertexId:
    """A vertex of the edit cube that a click on it picks (visible, nearest)."""
    mesh = app.scene.mesh
    for vid in sorted(mesh.all_vertex_ids()):
        x, y = _screen(app, mesh.vertex_position(vid))
        if pick_nearest_vertex(app.camera, mesh, x, y, WIDTH, HEIGHT, occlusion=True) == vid:
            return vid
    raise AssertionError("no visible vertex")


def _plate_obj(app: Application, tmp_path: Path) -> Path:
    """A large quad between the camera and the edit cube, as an OBJ file (M1 has no object
    transform, so "in front" has to be in the plate's own coordinates)."""
    eye = app.camera.eye()
    dist = math.sqrt(sum(c * c for c in eye))
    d = tuple(c / dist for c in eye)
    center = tuple(c * 0.6 for c in eye)
    assert 0.6 * dist > 2.0, "the plate must lie outside the edit cube"
    helper = (0.0, 1.0, 0.0) if abs(d[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = (
        helper[1] * d[2] - helper[2] * d[1],
        helper[2] * d[0] - helper[0] * d[2],
        helper[0] * d[1] - helper[1] * d[0],
    )
    ul = math.sqrt(sum(c * c for c in u))
    u = tuple(c / ul for c in u)
    v = (
        d[1] * u[2] - d[2] * u[1],
        d[2] * u[0] - d[0] * u[2],
        d[0] * u[1] - d[1] * u[0],
    )
    size = 5.0
    corners = [
        tuple(center[i] + su * size * u[i] + sv * size * v[i] for i in range(3))
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
    lines = [f"v {x!r} {y!r} {z!r}" for x, y, z in corners] + ["f 1 2 3 4"]
    path = tmp_path / "plate.obj"
    path.write_text("\n".join(lines) + "\n")
    return path


def _reference_ids(app: Application) -> list[ObjectId]:
    return [oid for oid in app.scene.objects if oid != app.scene.edit_object_id]


# -- §5.2 scene reset on load (R-4) -------------------------------------------------------


def test_init_scene_resets_the_scene_to_one_editable_object():
    app = _app()
    objects = list(app.scene.objects.values())
    assert len(objects) == 1
    (obj,) = objects
    assert obj.id == app.scene.edit_object_id
    assert obj.name == "cube"
    assert obj.state is ObjectState.NORMAL
    assert app.viewport.mesh is obj.mesh
    assert app.viewport.object_entries == {}


def test_loading_a_scene_replaces_every_object_including_references():
    app = _app()
    ref = app.add_reference("cube")
    old_edit = app.scene.edit_object_id
    app.load_scene("cube")
    assert list(app.scene.objects) == [app.scene.edit_object_id]
    assert ref.id not in app.scene.objects and old_edit not in app.scene.objects
    # AD-001: the new object has a fresh id, none is reused.
    assert int(app.scene.edit_object_id) > int(ref.id)
    assert app.viewport.object_entries == {}
    assert not app.history.can_undo()
    assert app.selection.objects == set()


# -- Add as Reference (A-1, Q-3, Q-9, Q-10) -----------------------------------------------


def test_add_reference_adds_a_reference_and_keeps_edit_object_camera_and_selection():
    app = _app()
    edit_id, edit_mesh = app.scene.edit_object_id, app.scene.mesh
    vid = _front_vertex(app)
    _click(app, *_screen(app, edit_mesh.vertex_position(vid)))
    assert app.selection.vertices == {vid}
    camera = (app.camera.eye(), app.camera.camera_revision)
    rebuilds = app.viewport.render_mesh.benchmark_counters.get("topology_updates", 0)

    ref = app.add_reference("cube")

    assert ref.state is ObjectState.REFERENCE and ref.name == "cube"
    assert ref.id in app.scene.objects and ref.id != edit_id
    assert app.scene.edit_object_id == edit_id and app.scene.mesh is edit_mesh
    assert (app.camera.eye(), app.camera.camera_revision) == camera  # Q-9
    assert app.selection.vertices == {vid}
    assert len(app.history) == 1  # Q-3: one Undo step
    assert app.status_message == "Added 'cube' as Reference"
    entry = app.viewport.object_entries[ref.id]
    assert entry.mesh is ref.mesh
    assert entry.material.uniform_packet() == list(REFERENCE_BASE_COLOR)
    # The edit object's render mesh is not touched by adding another object.
    app.viewport.sync()
    assert app.viewport.render_mesh.benchmark_counters.get("topology_updates", 0) == rebuilds


def test_undo_and_redo_of_add_object_remove_and_restore_the_same_instance():
    app = _app()
    ref = app.add_reference("cube")
    app.viewport.sync()
    edit_rebuilds = app.viewport.render_mesh.benchmark_counters.get("topology_updates", 0)

    assert app.key_press(CTRL_Z)
    assert ref.id not in app.scene.objects
    assert ref.id not in app.viewport.object_entries
    assert app.key_press(CTRL_Y)
    assert app.scene.objects[ref.id] is ref  # same instance, same id (AD-001)
    assert app.viewport.object_entries[ref.id].mesh is ref.mesh
    # §4.6: Undo/Redo of an object step refreshes the object, not the edit object's mesh.
    app.viewport.sync()
    assert app.viewport.render_mesh.benchmark_counters.get("topology_updates", 0) == edit_rebuilds


def test_add_reference_is_refused_while_an_interaction_owns_the_keys():
    app = _app()
    vid = _front_vertex(app)
    _click(app, *_screen(app, app.scene.mesh.vertex_position(vid)))
    assert app.key_press(W)
    assert app.add_reference("cube") is None
    assert len(app.scene.objects) == 1
    assert "not while" in app.status_message
    app.key_release(W)


def test_add_reference_before_init_scene_raises():
    with pytest.raises(RuntimeError):
        Application().add_reference("cube")


# -- Mode 4 and object picking (RF-3, A-2) ------------------------------------------------


def test_key_4_switches_to_object_mode_and_clears_components_only():
    app = _app()
    vid = _front_vertex(app)
    _click(app, *_screen(app, app.scene.mesh.vertex_position(vid)))
    app.selection.objects = {app.scene.edit_object_id}
    assert app.key_press(FOUR)
    assert app.selection.mode is SelectionMode.OBJECT
    assert app.selection.vertices == set()
    assert app.selection.objects == {app.scene.edit_object_id}
    assert app.status_message == "Mode: Object"


def test_a_click_on_a_reference_switches_its_state_as_one_undo_step(tmp_path):
    app = _app()
    ref = app.add_reference("obj", obj_path=_plate_obj(app, tmp_path), name="plate")
    app.key_press(FOUR)
    x, y = WIDTH / 2, HEIGHT / 2  # the plate covers the centre of the view
    _click(app, x, y)
    assert app.selection.objects == {ref.id}
    assert ref.state is ObjectState.NORMAL
    assert app.status_message == "Object 'plate': Normal"
    entry = app.viewport.object_entries[ref.id]
    assert entry.material.uniform_packet() == list(DEFAULT_BASE_COLOR)
    assert len(app.history) == 2

    _click(app, x, y)
    assert ref.state is ObjectState.REFERENCE
    assert entry.material.uniform_packet() == list(REFERENCE_BASE_COLOR)

    app.key_press(CTRL_Z)
    assert ref.state is ObjectState.NORMAL
    app.key_press(CTRL_Z)
    assert ref.state is ObjectState.REFERENCE
    assert app.viewport.object_entries[ref.id] is entry  # a colour change, no rebuild
    app.key_press(CTRL_Y)
    assert ref.state is ObjectState.NORMAL


def test_a_click_on_the_edit_object_in_mode_4_never_makes_it_a_reference():
    app = _app()
    app.key_press(FOUR)
    _click(app, WIDTH / 2, HEIGHT / 2)
    edit = app.scene.edit_object
    assert app.selection.objects == {edit.id}
    assert edit.state is ObjectState.NORMAL
    assert "being edited" in app.status_message
    assert not app.history.can_undo()
    _click(app, 2.0, 2.0)  # a plain click into empty space clears the object selection
    assert app.selection.objects == set()


def test_modifier_clicks_in_mode_4_change_only_the_object_selection(tmp_path):
    app = _app()
    ref = app.add_reference("obj", obj_path=_plate_obj(app, tmp_path), name="plate")
    app.key_press(FOUR)
    depth = len(app.history)
    _click(app, WIDTH / 2, HEIGHT / 2, "shift")
    assert app.selection.objects == {ref.id}
    _click(app, WIDTH / 2, HEIGHT / 2, "ctrl")
    assert app.selection.objects == set()
    assert ref.state is ObjectState.REFERENCE
    assert len(app.history) == depth


def test_object_mode_has_no_hover():
    app = _app()
    app.key_press(FOUR)
    assert app.pointer_motion(WIDTH / 2, HEIGHT / 2) is False
    assert app.selection.hovered is None


# -- RF-2 / RF-6 / Q-2: components only ever see the edit object -------------------------


def test_a_reference_in_front_never_blocks_component_picking(tmp_path):
    app = _app()
    app.add_reference("obj", obj_path=_plate_obj(app, tmp_path), name="plate")
    vid = _front_vertex(app)
    point = _screen(app, app.scene.mesh.vertex_position(vid))
    # In mode 4 the plate is the front-most object under that point ...
    app.key_press(FOUR)
    assert app._pick(*point) in _reference_ids(app)
    # ... in mode 1 the click goes through it to the edit object's vertex (Q-2).
    app.key_press(ONE)
    app.pointer_motion(*point)
    assert app.selection.hovered == vid and isinstance(app.selection.hovered, VertexId)
    _click(app, *point)
    assert app.selection.vertices == {vid}


def test_a_reference_never_lights_up_selected_or_hovered_ids():
    """§4.4 Drawing (review R-5): both cubes have VertexId(0..7); only the edit object's
    entry carries the Selection overlay."""
    app = _app()
    ref = app.add_reference("cube")
    vid = _front_vertex(app)
    point = _screen(app, app.scene.mesh.vertex_position(vid))
    _click(app, *point)
    app.pointer_motion(*point)
    assert ref.mesh.is_valid_vertex(vid)  # the same integer id exists in the Reference
    app.viewport.sync()
    entry = app.viewport.object_entries[ref.id]
    assert entry.overlay is None
    assert not entry.store.has("highlight_flags")
    edit_points = [app.scene.mesh.vertex_position(vid)]
    assert app.viewport.point_positions["selected"] == edit_points


# -- Mode 4 refuses component work (L-1, RF-4, Q-1) ---------------------------------------


@pytest.mark.parametrize("key", [W, T, C, DELETE, SHIFT_S], ids=["w", "t", "c", "delete", "shift_s"])
def test_component_work_is_refused_in_object_mode(key):
    app = _app()
    app.key_press(FOUR)
    state = app.scene.mesh.export_state()
    assert app.key_press(key) is False
    assert app.interaction_owner is None
    assert not app.knife_active
    assert app.scene.mesh.export_state() == state
    assert not app.history.can_undo()
    assert "press 1/2/3" in app.status_message


def test_a_transform_with_a_reference_selected_names_the_lock(tmp_path):
    app = _app()
    ref = app.add_reference("obj", obj_path=_plate_obj(app, tmp_path), name="plate")
    app.key_press(FOUR)
    _click(app, WIDTH / 2, HEIGHT / 2, "shift")
    assert app.selection.objects == {ref.id}
    assert app.key_press(W) is False
    assert "'plate' is a Reference - locked" in app.status_message


def test_component_work_via_dispatch_is_refused_in_object_mode_too():
    app = _app()
    app.key_press(FOUR)
    assert app.dispatch_command(commands.CONNECT) is False
    assert not app.knife_active


# -- Mirror entries (R-9) ------------------------------------------------------------------


def test_undo_of_add_object_drops_its_id_from_the_object_selection():
    app = _app()
    ref = app.add_reference("cube")
    app.selection.objects = {ref.id, app.scene.edit_object_id}
    app.key_press(CTRL_Z)
    assert app.selection.objects == set()  # the snapshot from before the add
    app.key_press(CTRL_Y)
    assert app.selection.objects == set()  # the snapshot right after the add
    assert ref.id in app.scene.objects


def test_a_mesh_step_after_an_object_step_still_undoes_in_order(tmp_path):
    """One stack, two objects (AD-021 P-1 in the app): the edit cube's move and the plate's
    state change interleave on `app.history` and undo in reverse order."""
    app = _app()
    ref = app.add_reference("obj", obj_path=_plate_obj(app, tmp_path), name="plate")
    app.key_press(FOUR)
    _click(app, WIDTH / 2, HEIGHT / 2)
    assert ref.state is ObjectState.NORMAL
    app.key_press(ONE)
    mesh = app.scene.mesh
    vid = sorted(mesh.all_vertex_ids())[0]
    before = mesh.vertex_position(vid)

    def bump():
        x, y, z = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (x + 0.25, y, z))
        return {vid}

    assert app.apply_mesh_change("nudge", bump)
    app.key_press(CTRL_Z)
    assert mesh.vertex_position(vid) == before and ref.state is ObjectState.NORMAL
    app.key_press(CTRL_Z)
    assert ref.state is ObjectState.REFERENCE
    assert app.selection.mode is SelectionMode.OBJECT  # the mirror entry's mode
    app.key_press(CTRL_Z)
    assert ref.id not in app.scene.objects
    assert app.scene.mesh is mesh
