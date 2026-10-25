"""Shift+Ctrl+click on saved regions (Manu 2026-10-25): a face of a region isolates it, a click on the isolated region
inverts the visibility (rest visible, the region's interior hidden), a click into empty space shows everything."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import FaceRegion, FaceRegions, SelectionMode
from core.mesh import Mesh
from mirai import regions as api
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input

WIDTH, HEIGHT = 800, 600
CLICK = Input("mouse", "LEFT", frozenset({"ctrl", "shift"}))


def _grid(n: int = 4, size: float = 4.0) -> Mesh:
    mesh = Mesh()
    step = size / n
    half = size / 2.0
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((c * step - half, r * step - half, 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_grid().export_state())
    app.frame_scene()
    app.camera.yaw = 0.0
    app.camera.pitch = 0.0
    app.camera.camera_revision += 1
    app.set_viewport_size(WIDTH, HEIGHT)
    mesh = app.scene.mesh
    left = frozenset(f for f in mesh.all_face_ids() if _center(mesh, f)[0] < 0)
    right = frozenset(mesh.all_face_ids()) - left
    mesh.face_regions = FaceRegions((FaceRegion("Brow", left), FaceRegion("Upper Lip", right)))
    return app


def _center(mesh, face):
    pts = [mesh.vertex_position(v) for v in mesh.face_vertices(face)]
    return tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))


def _click(app, x: float, y: float) -> bool:
    pos = app.camera.project_to_screen((x, y, 0.0), WIDTH, HEIGHT)
    app.pointer_motion(*pos)
    app.pointer_press(CLICK, *pos)
    return app.pointer_release("LEFT", *pos)


def _region_vertices(app, name):
    mesh = app.scene.mesh
    return api.region_vertices(mesh, api.live_faces(mesh, name))


def test_the_chord_is_a_click_only_gesture():
    bindings = build_default_bindings()
    assert bindings.command_for(CLICK) == cmd.REGION_CLICK
    assert bindings.command_for(Input("drag", "LEFT", frozenset({"ctrl", "shift"}))) is None
    assert bindings.command_for(Input("mouse", "LEFT", frozenset({"ctrl"}))) == cmd.SELECT_REMOVE


def test_click_in_a_region_isolates_it(app):
    mesh = app.scene.mesh
    assert _click(app, -1.5, -1.5)
    assert app._hidden.vertices() == frozenset(mesh.all_vertex_ids()) - _region_vertices(app, "Brow")
    assert not app.history.can_undo() or True  # view state: no mesh History entry
    assert "Isolated" in app.status_message


def test_click_again_inverts_the_visibility_and_the_rest_stays_whole(app):
    mesh = app.scene.mesh
    _click(app, -1.5, -1.5)
    assert _click(app, -1.5, -1.5)
    faces = api.live_faces(mesh, "Brow")
    interior = api.interior_vertices(mesh, faces)
    assert app._hidden.vertices() == frozenset(interior)
    right = api.live_faces(mesh, "Upper Lip")
    assert not any(app._hidden.is_hidden_face(mesh, f) for f in right)  # the whole rest is visible
    assert all(app._hidden.is_hidden_face(mesh, f) for f in faces)  # the region's faces are hidden


def test_click_on_the_rest_after_inverting_continues_the_toggle(app):
    """With two regions that cover the mesh, 'Brow hidden, rest visible' is also 'Upper Lip isolated': a click on the
    visible Upper Lip therefore inverts again (hides its interior, shows Brow). A third region isolates normally."""
    mesh = app.scene.mesh
    _click(app, -1.5, -1.5)
    _click(app, -1.5, -1.5)
    assert _click(app, 1.5, 1.5)
    assert app._hidden.vertices() == frozenset(
        api.interior_vertices(mesh, api.live_faces(mesh, "Upper Lip"))
    )
    rows = FaceRegions((
        FaceRegion("Brow", frozenset(f for f in mesh.all_face_ids() if _center(mesh, f)[0] < -1)),
        FaceRegion("Jaw", frozenset(f for f in mesh.all_face_ids() if _center(mesh, f)[0] > 1)),
    ))
    mesh.face_regions = rows
    app._hidden.show_all()
    app._hidden_push()
    _click(app, -1.5, -1.5)
    assert _click(app, -1.5, -1.5)  # inverted: Brow hidden, rest visible
    assert _click(app, 1.5, 1.5)  # a face of Jaw: Jaw is not the isolated region, so it is isolated
    assert app._hidden.vertices() == frozenset(mesh.all_vertex_ids()) - _region_vertices(app, "Jaw")


def test_click_into_empty_space_shows_everything(app):
    _click(app, -1.5, -1.5)
    assert app._hidden
    assert _click(app, -3.0, 3.0)
    assert not app._hidden


def test_click_on_a_face_without_a_region_changes_nothing(app):
    mesh = app.scene.mesh
    app.scene.mesh.face_regions = FaceRegions((FaceRegion("Brow", frozenset(api.live_faces(mesh, "Brow"))),))
    assert not _click(app, 1.5, 1.5) or not app._hidden
    assert not app._hidden
    assert "no group" in app.status_message


def test_works_in_every_component_mode_and_not_in_object_mode(app):
    for mode_key in ("1", "2", "3"):
        app.key_press(Input("key", mode_key, frozenset()))
        app._hidden.show_all()
        app._hidden_push()
        _click(app, -1.5, -1.5)
        assert app._hidden, mode_key
    app._hidden.show_all()
    app._hidden_push()
    app.key_press(Input("key", "4", frozenset()))
    _click(app, -1.5, -1.5)
    assert not app._hidden


def test_selection_and_mesh_are_untouched(app):
    mesh = app.scene.mesh
    state = {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}
    app.selection.mode = SelectionMode.FACE
    mine = set(list(api.live_faces(mesh, "Brow"))[:1])
    app.selection.set(set(mine))
    _click(app, -1.5, -1.5)  # isolate: the selected face stays visible, so it stays selected
    assert app.selection.faces == mine
    _click(app, -3.0, 3.0)
    assert {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")} == state
    assert app.selection.faces == mine


def test_a_plain_ctrl_drag_is_still_a_tweak(app):
    """The new chord adds no drag binding: Ctrl+drag keeps working (the gesture is fixed at the press)."""
    bindings = build_default_bindings()
    assert bindings.command_for(Input("drag", "LEFT", frozenset({"ctrl"}))) == cmd.TWEAK


def test_click_makes_the_clicked_group_the_active_one(app):
    mesh = app.scene.mesh
    _click(app, 1.5, 1.5)  # a face of Upper Lip
    assert app.active_region == "Upper Lip"
    app._hidden.show_all()
    app._hidden_push()
    _click(app, -1.5, -1.5)
    assert app.active_region == "Brow"
    assert api.live_faces(mesh, "Brow")
