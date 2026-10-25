"""Saved regions through topology edits (Slice 3, AD-REGIONS-01 §1.6): a created face joins a region iff ALL of its
parents were in it; Extrude names its parents; everything else fails closed. One Undo step restores mesh and regions."""

from __future__ import annotations

import random

import pytest

import tests._bootstrap  # noqa: F401

from core import FaceRegion, FaceRegions, SelectionMode
from core.mesh import Mesh
from core.operations import record_mesh_change
from mirai import regions as api
from mirai.application import Application
from mirai.interaction.input import Input

WIDTH, HEIGHT = 800, 600
N = 4


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


UNDO, REDO = _key("z", "ctrl"), _key("y", "ctrl")
K1, K2, K3 = _key("1"), _key("2"), _key("3")
I, C, T = _key("i"), _key("c"), _key("t")


def _grid(n: int = N, size: float = 4.0) -> Mesh:
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


def _center(mesh, face):
    pts = [mesh.vertex_position(v) for v in mesh.face_vertices(face)]
    return tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))


def _vertex(mesh, x, y):
    (vid,) = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (x, y)]
    return vid


def _edge(mesh, a, b):
    (eid,) = [e for e in mesh.vertex_edges(a) if set(mesh.edge_vertices(e)) == {a, b}]
    return eid


def _live(mesh, name):
    return api.live_faces(mesh, name)


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_grid().export_state())
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    mesh = app.scene.mesh
    left = frozenset(f for f in mesh.all_face_ids() if _center(mesh, f)[0] < 0)
    mesh.face_regions = FaceRegions((FaceRegion("Brow", left),))
    return app


def _regions(app):
    return app.scene.mesh.face_regions


# -- Splits and connects -----------------------------------------------------------------------


def test_loop_insert_cuts_a_region_in_half_and_both_halves_stay_in_it(app):
    mesh = app.scene.mesh
    before = _regions(app)
    row_edge = _edge(mesh, _vertex(mesh, -2.0, -2.0), _vertex(mesh, -2.0, -1.0))  # a vertical edge on the left border
    app.key_press(K2)
    app.selection.set({row_edge})
    app.viewport.on_selection_changed()
    assert app.key_press(I)  # ring across the row: 2 faces in Brow, 2 outside
    live = _live(mesh, "Brow")
    assert len(live) == len(before.get("Brow").faces) - 2 + 4  # two Brow faces became four
    assert api.lost_count(mesh, "Brow") == 0  # the cut parents left the region (they did not "get lost")
    assert all(_center(mesh, f)[0] < 0.0 + 1e-9 for f in live)  # nothing from the right half joined
    assert app.key_press(UNDO)
    assert _regions(app) == before
    assert app.key_press(REDO)
    assert len(_live(mesh, "Brow")) == len(live)


def test_a_face_split_across_two_regions_is_never_in_a_region_one_parent_lacks(app):
    mesh = app.scene.mesh
    face = next(f for f in mesh.all_face_ids() if f in _regions(app).get("Brow").faces)
    a, _b, c, _d = mesh.face_vertices(face)
    change = mesh.begin_change()
    _edge_id, f1, f2 = mesh.connect_vertices(face, a, c)
    assert api.inherit_into(mesh, change)
    mesh.end_change(change)
    brow = _regions(app).get("Brow").faces
    assert {f1, f2} <= brow and face not in brow


def test_random_connects_children_get_exactly_the_parents_regions():
    rng = random.Random(7)
    for _ in range(25):
        mesh = _grid(3)
        faces = mesh.all_face_ids()
        mesh.face_regions = FaceRegions((
            FaceRegion("Brow", frozenset(rng.sample(faces, 4))),
            FaceRegion("Jaw", frozenset(rng.sample(faces, 3))),
        ))
        before = {r.name: set(r.faces) for r in mesh.face_regions.regions}
        face = rng.choice(faces)
        a, b, c, d = mesh.face_vertices(face)
        change = mesh.begin_change()
        _e, f1, f2 = mesh.connect_vertices(face, a, c)
        api.inherit_into(mesh, change)
        mesh.end_change(change)
        for name, members in before.items():
            now = {r.name: set(r.faces) for r in mesh.face_regions.regions}[name]
            assert (f1 in now and f2 in now) == (face in members)
            assert (f1 in now) == (f2 in now)
            assert (face in now) == False  # the parent has left every region it was in (it is gone)
            assert now - {f1, f2} == members - {face}


# -- Dissolve and delete ----------------------------------------------------------------------------


def test_dissolve_inside_a_region_stays_in_it_and_across_the_border_joins_none(app):
    mesh = app.scene.mesh
    brow = _regions(app).get("Brow").faces
    inside = _edge(mesh, _vertex(mesh, -2.0, 0.0), _vertex(mesh, -1.0, 0.0))  # between two Brow faces
    app.key_press(K2)
    app.selection.set({inside})
    app.viewport.on_selection_changed()
    assert app.key_press(_key("backspace"))
    now = _regions(app).get("Brow").faces
    merged = [f for f in mesh.all_face_ids() if f not in {*brow} and f in now]
    assert len(merged) == 1 and len(mesh.face_vertices(merged[0])) >= 4
    assert app.key_press(UNDO)
    assert _regions(app).get("Brow").faces == brow
    across = _edge(mesh, _vertex(mesh, 0.0, 0.0), _vertex(mesh, 0.0, 1.0))  # between a Brow face and the rest
    app.selection.set({across})
    app.viewport.on_selection_changed()
    assert app.key_press(_key("backspace"))
    now = _regions(app).get("Brow").faces
    assert not any(f in now for f in mesh.all_face_ids() if f not in brow)  # the mixed merge joined nothing


def test_deleting_a_face_still_counts_as_lost(app):
    mesh = app.scene.mesh
    face = next(iter(_regions(app).get("Brow").faces))
    app.key_press(K3)
    app.selection.set({face})
    app.viewport.on_selection_changed()
    assert app.key_press(_key("delete"))
    assert api.lost_count(mesh, "Brow") == 1


# -- Extrude ----------------------------------------------------------------------------------------


def test_extrude_caps_and_walls_inherit_from_the_face_they_grew_from(app):
    mesh = app.scene.mesh
    brow = _regions(app).get("Brow").faces
    face = next(f for f in brow if _center(mesh, f)[:2] == (-1.5, -1.5))
    app.key_press(K3)
    app.selection.set({face})
    app.viewport.on_selection_changed()
    faces_before = set(mesh.all_face_ids())
    assert app.key_press(T)
    app.pointer_motion(300.0, 300.0, 10.0, 0.0)
    app.pointer_motion(300.0, 300.0, 10.0, 0.0)
    assert app.key_release(T)
    created = set(mesh.all_face_ids()) - faces_before
    assert len(created) == 1 + 4 - 0 or len(created) >= 2  # cap + walls (borders of the grid have fewer walls)
    now = _regions(app).get("Brow").faces
    assert created <= now and face not in now
    assert app.key_press(UNDO)
    assert _regions(app).get("Brow").faces == brow


def test_extrude_of_a_face_outside_every_region_creates_no_region_members(app):
    mesh = app.scene.mesh
    brow = _regions(app).get("Brow").faces
    face = next(f for f in mesh.all_face_ids() if f not in brow)
    app.key_press(K3)
    app.selection.set({face})
    app.viewport.on_selection_changed()
    faces_before = set(mesh.all_face_ids())
    app.key_press(T)
    app.pointer_motion(300.0, 300.0, 10.0, 0.0)
    app.pointer_motion(300.0, 300.0, 10.0, 0.0)
    app.key_release(T)
    assert not (set(mesh.all_face_ids()) - faces_before) & _regions(app).get("Brow").faces


# -- Fail closed, other plumbing -------------------------------------------------------------------


def test_nothing_changes_without_regions_or_without_new_faces(app):
    mesh = app.scene.mesh
    change = mesh.begin_change()
    assert not api.inherit_into(mesh, change)  # nothing was created
    mesh.end_change(change)
    mesh.face_regions = None
    change = mesh.begin_change()
    mesh.split_edge(mesh.all_edge_ids()[0])
    assert not api.inherit_into(mesh, change)
    mesh.end_change(change)


def test_a_region_edit_is_not_touched_by_the_rule(app):
    mesh = app.scene.mesh
    face = next(f for f in mesh.all_face_ids() if f not in _regions(app).get("Brow").faces)
    app.selection.mode = SelectionMode.FACE
    app.selection.set({face})
    app.viewport.on_selection_changed()
    assert app.key_press(_key("g", "ctrl", "shift"))  # add to Brow
    assert face in _regions(app).get("Brow").faces
    assert app.key_press(UNDO)
    assert face not in _regions(app).get("Brow").faces


def test_split_edge_keeps_every_face_id_and_therefore_the_region(app):
    mesh = app.scene.mesh
    before = _regions(app)
    edge = _edge(mesh, _vertex(mesh, -2.0, -2.0), _vertex(mesh, -1.0, -2.0))
    app.key_press(K2)
    app.selection.set({edge})
    app.viewport.on_selection_changed()
    assert app.key_press(C)  # Split
    assert _regions(app) == before


# -- Knife ----------------------------------------------------------------------------------------


def test_a_knife_cut_through_a_region_face_leaves_both_halves_in_it():
    """One committed Knife session (the cut runs through the front face of the cube): the parent face leaves the region
    and both halves join it, in one Undo step with the cut."""
    from tests.test_application_knife import ENTER, HEIGHT as H, WIDTH as W, _begin, _click, _edge_screen
    from tests.test_application_knife import _history_depths, _v
    from tests.test_application_knife_faces import _front_edge

    app = Application()  # the framed default cube, as the Knife tests' own fixture
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(W, H)
    mesh = app.scene.mesh
    front = next(f for f in mesh.all_face_ids() if {_v(app, i) for i in (4, 5, 6, 7)} == set(mesh.face_vertices(f)))
    other = next(f for f in mesh.all_face_ids() if f != front)
    mesh.face_regions = FaceRegions((FaceRegion("Brow", frozenset({front})), FaceRegion("Jaw", frozenset({other}))))
    before = mesh.face_regions
    _begin(app)
    e56, e47 = _front_edge(app)
    assert _click(app, _edge_screen(app, e56, 0.5))
    assert _click(app, _edge_screen(app, e47, 0.5))
    assert app.key_press(ENTER)
    brow = mesh.face_regions.get("Brow").faces
    assert front not in brow and len([f for f in brow if mesh.is_valid_face(f)]) == 2
    assert mesh.face_regions.get("Jaw").faces == frozenset({other})  # untouched
    assert _history_depths(app) == (1, 0)
    assert app.key_press(UNDO)
    assert mesh.face_regions == before
