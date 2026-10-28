"""Transform orientation World / Normal in the app (WP Toolbox Gaps C1, `mirai.transform_space`).

Headless. `K` toggles World <-> Normal (the Playground's key, `PROVISIONAL`) and clears the constraint. In
Normal the constraints and the gizmo use the selection's frame: X/Y/Z of one face (first edge, normal ×
first edge, normal), only Z = normal for any other selection. No constraint stays free. Refusals (an axis
the selection has no direction for) leave mesh and History untouched.
"""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh, SelectionMode
from hud import hud_rows, hud_state, key_hints
from mirai import transform_space
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.viewport import gizmo

WIDTH, HEIGHT = 800, 600
TILT = math.radians(30.0)


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


K, W, E, R = _key("k"), _key("w"), _key("e"), _key("r")
X, Y, Z = _key("x"), _key("y"), _key("z")


def _tilted_grid(n: int = 3) -> Mesh:
    """An n×n grid tilted 30° about the world X axis: its normal is (0, -sin 30°, cos 30°)."""
    mesh = Mesh()
    c, s = math.cos(TILT), math.sin(TILT)
    p = {}
    for r in range(n + 1):
        for col in range(n + 1):
            y = float(r) - n / 2.0
            p[(r, col)] = mesh.add_vertex((float(col) - n / 2.0, y * c, y * s))
    for r in range(n):
        for col in range(n):
            mesh.add_face([p[(r, col)], p[(r, col + 1)], p[(r + 1, col + 1)], p[(r + 1, col)]])
    return mesh


NORMAL = (0.0, -math.sin(TILT), math.cos(TILT))


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_tilted_grid().export_state())
    app.viewport.on_topology_changed()
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.gizmo_enabled = True
    return app


def _centre_face(app):
    mesh = app.scene.mesh
    return min(
        mesh.all_face_ids(),
        key=lambda f: sum(abs(c) for v in mesh.face_vertices(f) for c in mesh.vertex_position(v)),
    )


def _select(app, mode, ids) -> None:
    app.selection.mode = mode
    app.selection.clear()
    app.selection.add(set(ids))
    app.viewport.on_selection_changed()


def _positions(app) -> dict:
    mesh = app.scene.mesh
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


def _gesture(app, key: Input, dx: float = 40.0, dy: float = -25.0) -> bool:
    """Hold `key`, move the mouse in a few steps, release; True when the gesture began."""
    app.pointer_motion(400.0, 300.0)
    app.key_press(key)
    began = False
    for i in range(1, 5):
        began = app.pointer_motion(400.0 + dx * i / 4, 300.0 + dy * i / 4, dx / 4, dy / 4) or began
    app.key_release(key)
    return began


def _displacements(before: dict, after: dict) -> list:
    return [
        tuple(a - b for a, b in zip(after[v], before[v]))
        for v in before
        if after[v] != before[v]
    ]


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def _parallel(d, axis) -> bool:
    length = math.sqrt(_dot(d, d))
    return length > 1e-9 and abs(abs(_dot(d, axis)) - length) < 1e-9


# -- the toggle ------------------------------------------------------------------------------------


def test_k_toggles_world_and_normal_and_clears_the_constraint(app):
    assert app.bindings.command_for(K) == cmd.TOGGLE_TRANSFORM_SPACE
    assert app.transform_orientation == "world"
    app.key_press(Z)
    assert app.axis_constraint == "z"
    assert app.key_press(K) is True
    assert app.transform_orientation == "normal"
    assert app.axis_constraint is None
    assert app.status_message == "Transform space: Normal (constraint none)"
    app.key_press(K)
    assert app.transform_orientation == "world"


def test_the_toggle_is_no_history_step_and_works_in_object_mode(app):
    app.key_press(_key("4"))
    assert app.key_press(K) is True
    assert app.transform_orientation == "normal"
    assert not app.history.can_undo()


def test_the_hud_shows_the_space_with_its_key(app):
    rows = {row.label: row for row in hud_rows(hud_state(app), key_hints(app.bindings))}
    assert rows["Space"].value == "World" and rows["Space"].keys == "K" and not rows["Space"].on
    app.key_press(K)
    rows = {row.label: row for row in hud_rows(hud_state(app), key_hints(app.bindings))}
    assert rows["Space"].value == "Normal" and rows["Space"].on


# -- the gizmo frame ---------------------------------------------------------------------------------


def test_world_gizmo_uses_the_world_axes(app):
    _select(app, SelectionMode.FACE, {_centre_face(app)})
    assert app.gizmo_items()
    assert app._gizmo_frame() == (gizmo.WORLD_AXES, gizmo.WORLD_PLANES)


def test_normal_gizmo_on_one_face_is_its_full_frame(app):
    face = _centre_face(app)
    _select(app, SelectionMode.FACE, {face})
    app.key_press(K)
    assert app.gizmo_items()
    axes, planes = app._gizmo_frame()
    named = dict(axes)
    assert sorted(named) == ["x", "y", "z"]
    assert named["z"] == pytest.approx(NORMAL)
    assert named["x"] == pytest.approx((1.0, 0.0, 0.0))  # the face's first edge runs along world X
    assert abs(_dot(named["x"], named["y"])) < 1e-12 and abs(_dot(named["y"], named["z"])) < 1e-12
    assert sorted(name for name, _, _ in planes) == ["xy", "xz", "yz"]


@pytest.mark.parametrize("mode", [SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE])
def test_normal_gizmo_on_any_other_selection_is_the_normal_only(app, mode):
    mesh = app.scene.mesh
    face = _centre_face(app)
    ids = {
        SelectionMode.VERTEX: set(mesh.face_vertices(face)),
        SelectionMode.EDGE: set(mesh.face_edges(face)),
        SelectionMode.FACE: set(mesh.edge_faces(mesh.face_edges(face)[0])),  # two faces
    }[mode]
    _select(app, mode, ids)
    app.key_press(K)
    axes, planes = app._gizmo_frame()
    assert [name for name, _ in axes] == ["z"] and planes == []
    assert axes[0][1] == pytest.approx(NORMAL)


def test_the_normal_frame_follows_a_moved_selection(app):
    face = _centre_face(app)
    _select(app, SelectionMode.FACE, {face})
    app.key_press(K)
    first = dict(app._gizmo_frame()[0])["z"]
    mesh = app.scene.mesh
    v = mesh.face_vertices(face)[0]
    x, y, z = mesh.vertex_position(v)
    app.apply_mesh_change("lift", lambda: mesh.set_vertex_position(v, (x, y, z + 0.5)))
    assert app.gizmo_items()
    assert dict(app._gizmo_frame()[0])["z"] != pytest.approx(first)


# -- gestures ------------------------------------------------------------------------------------------


def test_move_z_in_normal_space_moves_along_the_face_normal(app):
    face = _centre_face(app)
    _select(app, SelectionMode.FACE, {face})
    app.key_press(K)
    app.key_press(Z)
    before = _positions(app)
    assert _gesture(app, W)
    moved = _displacements(before, _positions(app))
    assert len(moved) == 4 and all(_parallel(d, NORMAL) for d in moved)
    app.history.undo()
    assert _positions(app) == before


def test_move_x_in_normal_space_moves_along_the_first_edge(app):
    _select(app, SelectionMode.FACE, {_centre_face(app)})
    app.key_press(K)
    app.key_press(X)
    before = _positions(app)
    assert _gesture(app, W)
    moved = _displacements(before, _positions(app))
    assert moved and all(_parallel(d, (1.0, 0.0, 0.0)) for d in moved)


def test_move_z_on_vertices_uses_their_normal(app):
    mesh = app.scene.mesh
    _select(app, SelectionMode.VERTEX, set(mesh.face_vertices(_centre_face(app))))
    app.key_press(K)
    app.key_press(Z)
    before = _positions(app)
    assert _gesture(app, W)
    moved = _displacements(before, _positions(app))
    assert len(moved) == 4 and all(_parallel(d, NORMAL) for d in moved)


def test_rotate_z_in_normal_space_keeps_the_face_in_its_plane(app):
    face = _centre_face(app)
    _select(app, SelectionMode.FACE, {face})
    app.key_press(K)
    app.key_press(Z)
    before = _positions(app)
    assert _gesture(app, E, 60.0, 0.0)
    after = _positions(app)
    moved = _displacements(before, after)
    assert moved and all(abs(_dot(d, NORMAL)) < 1e-9 for d in moved)


def test_scale_x_in_normal_space_scales_along_the_first_edge(app):
    _select(app, SelectionMode.FACE, {_centre_face(app)})
    app.key_press(K)
    app.key_press(X)
    before = _positions(app)
    assert _gesture(app, R, 60.0, 0.0)
    moved = _displacements(before, _positions(app))
    assert len(moved) == 4 and all(_parallel(d, (1.0, 0.0, 0.0)) for d in moved)


def test_a_drag_on_the_normal_handle_of_the_gizmo_moves_along_the_normal(app):
    face = _centre_face(app)
    _select(app, SelectionMode.FACE, {face})
    app.key_press(K)
    app.pointer_motion(5.0, 5.0)
    assert app.gizmo_items()
    pivot = app._gizmo_pivot()
    size = gizmo.gizmo_size(app.camera, pivot)
    tip = tuple(pivot[i] + NORMAL[i] * size * 0.6 for i in range(3))
    start = app.camera.project_to_screen(tip, WIDTH, HEIGHT)
    before = _positions(app)
    left = Input("mouse", "LEFT")
    app.pointer_motion(*start)
    app.pointer_press(left, *start)
    x, y = start
    for _ in range(6):
        app.pointer_drag(0.0, -8.0, x, y - 8.0)
        y -= 8.0
    app.pointer_release("LEFT", x, y)
    assert app.gizmo_constraint is None  # one-shot (Manu A1 / E2, 2026-10-28): for that drag only
    moved = _displacements(before, _positions(app))
    assert len(moved) == 4 and all(_parallel(d, NORMAL) for d in moved)


@pytest.mark.parametrize(
    "mode_key, constraint_key, text",
    [
        (W, X, "X in Normal space needs exactly one selected face"),
        (W, _key("z", "shift"), "XY plane in Normal space needs exactly one selected face"),
        (R, Z, "Scale along an axis in Normal space needs exactly one selected face"),
    ],
)
def test_an_axis_without_a_direction_is_refused_visibly(app, mode_key, constraint_key, text):
    mesh = app.scene.mesh
    _select(app, SelectionMode.VERTEX, set(mesh.face_vertices(_centre_face(app))))
    app.key_press(K)
    app.key_press(constraint_key)
    before = _positions(app)
    assert _gesture(app, mode_key) is False
    assert text in app.status_message
    assert _positions(app) == before
    assert not app.history.can_undo()
    assert app.transform_command is None


def test_free_stays_free_and_world_z_stays_world(app):
    _select(app, SelectionMode.FACE, {_centre_face(app)})
    app.key_press(Z)
    before = _positions(app)
    assert _gesture(app, W)
    moved = _displacements(before, _positions(app))
    assert moved and all(_parallel(d, (0.0, 0.0, 1.0)) for d in moved)


def test_the_frame_helper_rules():
    mesh = _tilted_grid(1)
    from core import Selection

    sel = Selection()
    sel.mode = SelectionMode.FACE
    sel.add(set(mesh.all_face_ids()))
    frame = transform_space.normal_frame(mesh, sel)
    assert frame.full and transform_space.normal_refusal(frame, "x", scale=True) is None
    sel.mode = SelectionMode.OBJECT
    assert transform_space.normal_frame(mesh, sel) is None
    assert transform_space.normal_refusal(None, "z", scale=False) == "the selection has no normal"
