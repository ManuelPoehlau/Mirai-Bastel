"""AD-021 M2-3 — Apply / Clear transform (L-3) in mode `4`.

Headless (TraceStore), no pyglet. Apply bakes the placement into the mesh (world positions =
`object_space.to_world` of the old positions, bit for bit), the placement becomes identity and
the pivot moves to its old world position `t + c` (`PROVISIONAL`); one Undo step through the
project's first `CompositeCommand` (E-13). Clear sets the placement to identity, the mesh
stays. Refusals: not in `4`, nothing / only References selected (RF-4), a symmetry definition
the bake would break (`PROVISIONAL`). Bindings `PROVISIONAL`: Ctrl+A, Alt+Shift+A.
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

from core import ObjectState, ObjectTransform, SelectionMode
from core.scene import IDENTITY_TRANSFORM
from mirai import object_space
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.scene_objects import CompositeCommand
from mirai.symmetry import symmetry_state
from mirai.symmetry_axis import current_axis, set_symmetry_axis

WIDTH, HEIGHT = 800, 600
HEAD_OBJ = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


APPLY, CLEAR = _key("a", "ctrl"), _key("a", "alt", "shift")
W, E, R = _key("w"), _key("e"), _key("r")
ONE, FOUR = _key("1"), _key("4")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")


def _app(obj_path=None) -> Application:
    app = Application()
    if obj_path is None:
        app.init_scene("cube")
    else:
        app.init_scene("obj", obj_path=obj_path)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _select(app: Application, *objects) -> None:
    if app.selection.mode is not SelectionMode.OBJECT:
        app.key_press(FOUR)
    app.selection.objects = {obj.id for obj in objects}


def _gesture(app: Application, key: Input, dx: float, dy: float = 0.0, constraint=None) -> None:
    if constraint is not None:
        app.key_press(constraint)
    app.key_press(key)
    app.pointer_motion(400, 300, dx, dy)
    app.key_release(key)
    if constraint is not None:
        app.key_press(constraint)


def _place_by_gestures(app: Application) -> None:
    _gesture(app, W, 40.0, 15.0)
    _gesture(app, E, 55.0)
    _gesture(app, R, 30.0, 10.0)


def _world_positions(obj) -> dict:
    mesh = obj.mesh
    return {v: object_space.to_world(obj, mesh.vertex_position(v)) for v in mesh.all_vertex_ids()}


def _rot_y(degrees: float):
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


# -- bindings --------------------------------------------------------------------------------


def test_bindings_are_ctrl_a_and_alt_shift_a_and_alt_a_stays_clear_selection():
    bindings = build_default_bindings()
    assert bindings.command_for(APPLY) == commands.APPLY_TRANSFORM
    assert bindings.command_for(CLEAR) == commands.CLEAR_TRANSFORM
    assert bindings.command_for(_key("a", "alt")) == commands.CLEAR_SELECTION


# -- Apply ------------------------------------------------------------------------------------


def test_apply_bakes_world_positions_exactly_and_resets_the_placement():
    app = _app()
    cube = app.scene.edit_object
    _select(app, cube)
    _place_by_gestures(app)
    world = _world_positions(cube)
    local = {v: cube.mesh.vertex_position(v) for v in world}
    old_pivot_world = object_space.to_world(cube, cube.pivot)
    model = object_space.model_matrix(cube)
    assert app.key_press(APPLY)
    assert cube.transform is IDENTITY_TRANSFORM
    assert {v: cube.mesh.vertex_position(v) for v in world} == world  # bit-exact (to_world)
    assert cube.pivot == old_pivot_world
    # what the renderer drew with the model matrix agrees too (different float path: 1e-12)
    for v, p in world.items():
        m = [sum(model[c * 4 + r] * q for c, q in enumerate((*local[v], 1.0))) for r in range(3)]
        assert all(abs(m[i] - p[i]) <= 1e-12 for i in range(3))
    assert app.viewport.model_matrix is None
    assert app.status_message.startswith("Object 'cube': transform applied")
    assert isinstance(app.history._undo_stack[-1], CompositeCommand)


def test_undo_restores_mesh_transform_and_pivot_and_redo_bakes_again():
    app = _app()
    cube = app.scene.edit_object
    _select(app, cube)
    _place_by_gestures(app)
    state, placed, pivot = cube.mesh.export_state(), cube.transform, cube.pivot
    app.key_press(APPLY)
    baked_state, baked_pivot = cube.mesh.export_state(), cube.pivot
    assert app.key_press(CTRL_Z)
    assert cube.mesh.export_state() == state
    assert cube.transform is placed and cube.pivot == pivot
    assert app.viewport.model_matrix == object_space.model_matrix(cube)
    assert app.key_press(CTRL_Y)
    assert cube.mesh.export_state() == baked_state
    assert cube.transform is IDENTITY_TRANSFORM and cube.pivot == baked_pivot
    assert app.key_press(CTRL_Z)
    assert app.key_press(CTRL_Z)  # the Scale gesture before it: one step each
    assert cube.transform.scale == 1.0


def test_a_rotate_after_apply_turns_about_the_same_place():
    app = _app()
    cube = app.scene.edit_object
    _select(app, cube)
    _gesture(app, W, 60.0, 20.0)
    pivot_world = object_space.to_world(cube, cube.pivot)
    app.key_press(APPLY)
    _gesture(app, E, 45.0)
    assert object_space.to_world(cube, cube.pivot) == pivot_world
    assert cube.transform.translation == (0.0, 0.0, 0.0)


def test_the_component_selection_stays_valid_after_apply():
    app = _app()
    cube = app.scene.edit_object
    _select(app, cube)
    _place_by_gestures(app)
    app.key_press(ONE)
    vids = set(sorted(cube.mesh.all_vertex_ids())[:3])
    app.selection.vertices = set(vids)
    app.key_press(FOUR)  # clears the components, like every mode key
    app.selection.objects = {cube.id}
    app.key_press(APPLY)
    app.key_press(ONE)
    app.selection.vertices = set(vids)
    world_before = {v: cube.mesh.vertex_position(v) for v in vids}
    expected = app.camera.screen_delta_to_world(world_before[min(vids)], 12.0, 4.0, WIDTH, HEIGHT)
    _gesture(app, W, 12.0, 4.0)
    for v in vids:
        after = cube.mesh.vertex_position(v)
        assert all(abs(after[i] - world_before[v][i] - expected[i]) < 1e-9 for i in range(3))


def test_apply_on_a_non_edit_object_rebuilds_its_entry_and_undo_restores_it():
    app = _app()
    other = app.add_reference("cube", name="other")
    other.state = ObjectState.NORMAL
    app._objects.sync_views()
    _select(app, other)
    _gesture(app, W, 80.0, 0.0, constraint=_key("x"))
    edit_state = app.scene.mesh.export_state()
    other_state = other.mesh.export_state()
    entry = app.viewport.object_entries[other.id]
    app.viewport.sync()
    rev = entry.dirty.topology_rev
    app.key_press(APPLY)
    assert entry.dirty.topology_rev > rev  # the entry rebuilds from the baked positions
    assert app.scene.mesh.export_state() == edit_state  # the edit object is untouched
    assert other.transform is IDENTITY_TRANSFORM
    app.viewport.sync()
    rev = entry.dirty.topology_rev
    app.key_press(CTRL_Z)
    assert other.mesh.export_state() == other_state
    assert entry.dirty.topology_rev > rev
    assert entry.model_matrix == object_space.model_matrix(other)
    # mode-4 picking finds it at its placed position again (its pick cache re-projected)
    center = object_space.to_world(other, (0.0, 0.0, 0.0))
    x, y = app.camera.project_to_screen(center, WIDTH, HEIGHT)
    assert app._objects.pick(x, y) == other.id


def test_apply_several_objects_is_one_undo_step():
    app = _app()
    cube = app.scene.edit_object
    other = app.add_reference("cube", name="other")
    other.state = ObjectState.NORMAL
    _select(app, cube, other)
    _gesture(app, R, 40.0)
    states = (cube.mesh.export_state(), other.mesh.export_state())
    app.key_press(APPLY)
    assert app.status_message.startswith("Objects 'cube', 'other': transform applied")
    app.key_press(CTRL_Z)
    assert (cube.mesh.export_state(), other.mesh.export_state()) == states
    assert cube.transform.scale == other.transform.scale != 1.0


def test_objects_without_a_placement_are_left_alone():
    app = _app()
    cube = app.scene.edit_object
    other = app.add_reference("cube", name="other")
    other.state = ObjectState.NORMAL
    _select(app, other)
    _gesture(app, W, 30.0)
    state = cube.mesh.export_state()
    _select(app, cube, other)
    app.key_press(APPLY)
    assert cube.mesh.export_state() == state and cube.pivot == (0.0, 0.0, 0.0)
    assert app.status_message.startswith("Object 'other': transform applied")


# -- Clear ------------------------------------------------------------------------------------


def test_clear_resets_the_placement_and_keeps_mesh_and_pivot():
    app = _app()
    cube = app.scene.edit_object
    _select(app, cube)
    _place_by_gestures(app)
    state, placed = cube.mesh.export_state(), cube.transform
    assert app.key_press(CLEAR)
    assert cube.transform is IDENTITY_TRANSFORM
    assert cube.mesh.export_state() == state and cube.pivot == (0.0, 0.0, 0.0)
    assert app.status_message == "Object 'cube': transform cleared (object level, mesh unchanged)"
    assert app._selection_undo_stack[-1][2] is False  # an object step
    app.key_press(CTRL_Z)
    assert cube.transform is placed
    app.key_press(CTRL_Y)
    assert cube.transform is IDENTITY_TRANSFORM


# -- Refusals -----------------------------------------------------------------------------------


@pytest.mark.parametrize("key", [APPLY, CLEAR], ids=["apply", "clear"])
def test_refused_outside_object_mode(key):
    app = _app()
    cube = app.scene.edit_object
    _select(app, cube)
    _gesture(app, W, 30.0)
    app.key_press(ONE)
    placed = cube.transform
    assert app.key_press(key) is False
    assert "press 4" in app.status_message
    assert cube.transform is placed


@pytest.mark.parametrize("key", [APPLY, CLEAR], ids=["apply", "clear"])
def test_refused_on_a_reference_and_with_nothing_selected(key):
    app = _app()
    ref = app.add_reference("cube", name="plate")
    ref.transform = ObjectTransform(translation=(2.0, 0.0, 0.0))
    app._objects.placement_changed()
    _select(app, ref)
    state = ref.mesh.export_state()
    assert app.key_press(key) is False
    assert "'plate' is a Reference - locked" in app.status_message
    assert ref.transform.translation == (2.0, 0.0, 0.0) and ref.mesh.export_state() == state
    _select(app)
    assert app.key_press(key) is False
    assert "no object selected" in app.status_message


def test_a_reference_in_a_mixed_selection_is_left_alone():
    app = _app()
    cube = app.scene.edit_object
    ref = app.add_reference("cube", name="plate")
    ref.transform = ObjectTransform(translation=(2.0, 0.0, 0.0))
    _select(app, cube)
    _gesture(app, W, 30.0)
    _select(app, cube, ref)
    app.key_press(APPLY)
    assert ref.transform.translation == (2.0, 0.0, 0.0)
    assert app.status_message.endswith("Reference 'plate' stays (locked)")


def test_refused_while_a_gesture_holds_the_keys():
    app = _app()
    cube = app.scene.edit_object
    _select(app, cube)
    app.key_press(W)
    app.pointer_motion(400, 300, 20.0, 0.0)
    assert app.key_press(APPLY) is False
    assert app.dispatch_command(commands.APPLY_TRANSFORM) is False
    app.key_release(W)


# -- Symmetry (PROVISIONAL rule) ------------------------------------------------------------------


@pytest.mark.skipif(not HEAD_OBJ.is_file(), reason="head_basemesh fehlt (examples/meshes/)")
def test_apply_on_a_symmetric_head_is_refused_when_the_plane_would_leave_an_axis_plane():
    app = _app(obj_path=HEAD_OBJ)
    head = app.scene.edit_object
    set_symmetry_axis(head.mesh, "X")
    _select(app, head)
    _gesture(app, E, 40.0)  # a free turn: not a multiple of 90 degrees
    state = head.mesh.export_state()
    assert app.key_press(APPLY) is False
    assert "not a multiple of 90 degrees" in app.status_message
    assert head.mesh.export_state() == state and head.transform is not IDENTITY_TRANSFORM
    app.key_press(CLEAR)
    _gesture(app, W, 30.0, constraint=_key("x"))  # along the plane normal
    assert app.key_press(APPLY) is False
    assert "off the origin" in app.status_message


@pytest.mark.skipif(not HEAD_OBJ.is_file(), reason="head_basemesh fehlt (examples/meshes/)")
def test_apply_keeps_a_symmetric_head_exactly_symmetric_when_the_plane_maps_onto_an_axis_plane():
    app = _app(obj_path=HEAD_OBJ)
    head = app.scene.edit_object
    set_symmetry_axis(head.mesh, "X")
    seam = head.mesh.symmetry_definition.seam_edges
    _select(app, head)
    _gesture(app, W, 30.0, 20.0, constraint=_key("x", "shift"))  # YZ plane: no X translation
    _gesture(app, R, 25.0)
    assert app.key_press(APPLY), app.status_message
    assert current_axis(head.mesh) == "X"
    assert head.mesh.symmetry_definition.seam_edges == seam
    assert symmetry_state(head.mesh).value == "valid"
    # a quarter turn about Y given exactly: X maps onto Z, the definition follows
    app.key_press(CTRL_Z)
    head.transform = ObjectTransform(rotation=((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)))
    app._objects.placement_changed()
    assert app.key_press(APPLY), app.status_message
    assert current_axis(head.mesh) == "Z"
    assert symmetry_state(head.mesh).value == "valid"
    app.key_press(CTRL_Z)
    assert current_axis(head.mesh) == "X"


def test_composite_undoes_in_reverse_and_redoes_in_order():
    log = []

    class Step:
        def __init__(self, name):
            self.name = name

        def undo(self):
            log.append(f"undo {self.name}")

        def redo(self):
            log.append(f"redo {self.name}")

    composite = CompositeCommand([Step("a"), Step("b"), Step("c")], "three")
    composite.undo()
    composite.redo()
    assert log == ["undo c", "undo b", "undo a", "redo a", "redo b", "redo c"]
    assert composite.description == "three"
