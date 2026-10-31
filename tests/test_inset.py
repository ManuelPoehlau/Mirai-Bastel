"""Inset (2026-10-29, Manu "Inset (Polygons)"; `PROVISIONAL`): hold I in face mode and drag.

Pinned: a region of faces gets a ring of wall quads along its outline, the region's faces shrink
inwards by the width (inner edges parallel to the old ones), interior vertices stay; one History
entry, Undo / Redo exact, Esc / a tap / a drag back to zero leave the mesh exactly as it was; the
inner faces stay selected; I in edge mode stays Loop Insert; corner-only contact and closed shells
refuse at the press; under symmetry the selection and its mirror inset together and stay exact
mirrors (also across the plane), the seam follows."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh, SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_axis import set_symmetry_axis
from mirai.topology.inset import InsetRefused, build_inset, plan_inset
from tests.mesh_invariants import assert_mesh_invariants

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


I, ESC, CTRL_Z, CTRL_Y = _key("i"), _key("ESCAPE"), _key("z", "ctrl"), _key("y", "ctrl")
K2, K3 = _key("2"), _key("3")


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
    app.set_viewport_size(WIDTH, HEIGHT)
    app.key_press(K3)
    return app


def _face(mesh, x: float, y: float):
    """The grid face whose lower-left corner is (x, y)."""
    for f in mesh.all_face_ids():
        if min((mesh.vertex_position(v)[0], mesh.vertex_position(v)[1]) for v in mesh.face_vertices(f)) == (x, y):
            return f
    raise AssertionError((x, y))


def _state(app) -> dict:
    return {k: v for k, v in app.scene.mesh.export_state().items() if not k.endswith("_id_counter")}


def _drag(app, dx: float, steps: int = 4) -> None:
    for _ in range(steps):
        app.pointer_motion(400.0, 300.0, dx, 0.0)


def _width(app) -> float:
    return app._gestures.session.width


def _corners(mesh, face) -> set:
    return {tuple(round(c, 9) for c in mesh.vertex_position(v)) for v in mesh.face_vertices(face)}


def test_i_in_face_mode_insets_one_face_one_undo_step(app):
    mesh = app.scene.mesh
    face = _face(mesh, 0.0, 0.0)
    app.selection.faces = {face}
    before = _state(app)
    faces_before = len(mesh.all_face_ids())
    assert app.key_press(I) is True
    assert app.interaction_owner == "transform"
    assert app.status_message.startswith("Inset: 1 face")
    _drag(app, 10.0)
    w = _width(app)
    assert 0.0 < w < 0.5
    assert app.key_release(I) is True
    assert app.status_message == "Inset committed"
    assert len(mesh.all_face_ids()) == faces_before + 4
    (inner,) = app.selection.faces
    assert app.selection.mode is SelectionMode.FACE
    assert _corners(mesh, inner) == {
        (round(x, 9), round(y, 9), 0.0) for x in (w, 1.0 - w) for y in (w, 1.0 - w)
    }
    assert_mesh_invariants(mesh)
    assert len(app.history) == 1
    assert app.key_press(CTRL_Z) is True
    assert _state(app) == before
    assert app.selection.faces == {face}
    assert app.key_press(CTRL_Y) is True
    assert len(mesh.all_face_ids()) == faces_before + 4


def test_a_region_insets_as_one_and_keeps_its_interior(app):
    mesh = app.scene.mesh
    region = {_face(mesh, x, y) for x in (-1.0, 0.0) for y in (-1.0, 0.0)}
    centre = next(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v) == (0.0, 0.0, 0.0))
    app.selection.faces = set(region)
    app.key_press(I)
    _drag(app, 10.0)
    app.key_release(I)
    assert len(mesh.all_face_ids()) == 16 + 8  # eight outline edges, eight walls
    assert mesh.is_valid_vertex(centre) and mesh.vertex_position(centre) == (0.0, 0.0, 0.0)
    assert len(app.selection.faces) == 4
    inner = {v for f in app.selection.faces for v in mesh.face_vertices(f)}
    assert centre in inner and len(inner) == 9
    xs = sorted({round(mesh.vertex_position(v)[0], 9) for v in inner})
    assert len(xs) == 3 and xs[0] > -1.0 and xs[1] == 0.0 and xs[2] == -xs[0]
    assert_mesh_invariants(mesh)


def test_esc_tap_and_drag_back_change_nothing(app):
    mesh = app.scene.mesh
    app.selection.faces = {_face(mesh, 0.0, 0.0)}
    before = _state(app)
    app.key_press(I)
    _drag(app, 10.0)
    assert _state(app) != before
    assert app.key_press(ESC) is True
    assert app.status_message == "Inset cancelled"
    assert _state(app) == before
    app.key_press(I)
    assert app.key_release(I) is True
    assert app.status_message == "Inset: no change"
    app.key_press(I)
    _drag(app, 10.0)
    _drag(app, -40.0)
    assert _width(app) == 0.0
    app.key_release(I)
    assert app.status_message == "Inset: no change"
    assert _state(app) == before
    assert not app.history.can_undo()


def test_the_width_stops_before_the_face_collapses(app):
    mesh = app.scene.mesh
    app.selection.faces = {_face(mesh, 0.0, 0.0)}
    app.key_press(I)
    _drag(app, 400.0)
    assert app.status_message.endswith("(limit)")
    assert _width(app) == pytest.approx(0.49)
    app.key_release(I)
    assert_mesh_invariants(mesh)


def test_hovered_face_without_selection_and_edge_mode_stays_loop_insert(app):
    mesh = app.scene.mesh
    app.selection.hovered = _face(mesh, -2.0, -2.0)
    assert app.key_press(I) is True
    _drag(app, 10.0)
    app.key_release(I)
    assert app.status_message == "Inset committed"
    assert len(mesh.all_face_ids()) == 16 + 4 + 0  # a corner face: two walls on the border, two inside
    app.key_press(K2)
    assert app.bindings.command_for(I) == cmd.LOOP_INSERT
    app.selection.edges = {mesh.face_edges(_face(mesh, 0.0, 0.0))[0]}
    assert app.key_press(I) is True
    assert app.status_message == "Loop Insert"


def test_refusals_at_the_press(app):
    mesh = app.scene.mesh
    assert app.key_press(I) is False
    assert "select or hover a face" in app.status_message
    # Two faces meeting only at a corner.
    app.selection.faces = {_face(mesh, -1.0, -1.0), _face(mesh, 0.0, 0.0)}
    before = _state(app)
    assert app.key_press(I) is False
    assert "corner" in app.status_message
    assert _state(app) == before


def test_closed_shell_has_no_outline():
    from mirai.scene_factory import create_cube

    mesh = create_cube()
    with pytest.raises(InsetRefused, match="outline"):
        plan_inset(mesh, mesh.all_face_ids())


def test_inset_keeps_uvs_on_the_inner_face():
    mesh = _grid(1, 1.0)
    (face,) = mesh.all_face_ids()
    mesh.set_face_uvs(face, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))
    result = build_inset(mesh, plan_inset(mesh, {face}))
    (inner,) = result.faces
    assert mesh.face_uvs(inner) == ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    assert all(mesh.face_uvs(f) is not None for f in mesh.all_face_ids())
    assert_mesh_invariants(mesh)


def test_under_symmetry_the_mirror_insets_too(app):
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    app.selection.faces = {_face(mesh, 1.0, 0.0)}  # mirror (-2, 0): a separate region
    app.key_press(I)
    _drag(app, 10.0)
    app.key_release(I)
    assert app.status_message == "Inset committed", app.status_message
    assert len(mesh.all_face_ids()) == 16 + 8
    positions = {mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    assert all((-x, y, z) in positions for x, y, z in positions)
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert len(app.selection.faces) == 1  # the side the selection was on


def test_under_symmetry_a_region_across_the_plane_insets_with_the_seam(app):
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    app.selection.faces = {_face(mesh, 0.0, 0.0), _face(mesh, 0.0, -1.0)}  # mirrors: (-1, 0), (-1, -1)
    app.key_press(I)
    _drag(app, 10.0)
    app.key_release(I)
    assert app.status_message == "Inset committed", app.status_message
    assert len(mesh.all_face_ids()) == 16 + 8
    positions = {mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    assert all((-x, y, z) in positions for x, y, z in positions)
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert_mesh_invariants(mesh)
    assert app.key_press(CTRL_Z) is True
    assert symmetry_state(mesh) is SymmetryState.VALID
