"""Saved regions / polygroups (`mirai.regions`, AD-REGIONS-01; PROVISIONAL).

The pure functions, then the app path: Ctrl+G makes the selection a new group (never overwrites one, a face is in
one group), Ctrl+Alt+N saves the group as a named set, Undo / Redo restore the value, Alt+G selects (never hidden
faces), Ctrl+Alt+H / Ctrl+Alt+M isolate / mask the whole group, the status reports what was lost, the value rides
through save/load and object switches."""

from __future__ import annotations

import time

import pytest

import tests._bootstrap  # noqa: F401
from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401

from core import FaceRegion, FaceRegions, SelectionMode
from core.mesh import Mesh
from core.serialization import scene_from_dict, scene_to_dict
from mirai import regions as api
from mirai.application import Application
from mirai.interaction.input import Input

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


NEXT, PREV = _key("g", "shift"), _key("g", "shift", "alt")
NEW, ADD, REMOVE = _key("g", "ctrl"), _key("g", "ctrl", "shift"), _key("g", "ctrl", "alt")
NAME = _key("n", "ctrl", "alt")
SELECT, SELECT_ADD = _key("g", "alt"), _key("g", "ctrl", "alt", "shift")
ISOLATE, MASK, DELETE = _key("h", "ctrl", "alt"), _key("m", "ctrl", "alt"), _key("backspace", "ctrl", "alt")
HIDE, SHOW_ALL = _key("h", "ctrl"), _key("h", "alt")
UNDO, REDO = _key("z", "ctrl"), _key("y", "ctrl")


def _grid(n: int = 4) -> Mesh:
    mesh = Mesh()
    ids = [[mesh.add_vertex((float(x), float(y), 0.0)) for x in range(n + 1)] for y in range(n + 1)]
    for y in range(n):
        for x in range(n):
            mesh.add_face([ids[y][x], ids[y][x + 1], ids[y + 1][x + 1], ids[y + 1][x]])
    return mesh


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("obj", obj_path=HEAD_OBJ)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.selection.mode = SelectionMode.FACE
    return app


def _select_faces(app, count: int = 6, start: int = 100):
    faces = set(app.scene.mesh.all_face_ids()[start:start + count])
    app.selection.set(faces)
    app.viewport.on_selection_changed()
    return faces


def _stored(app, name: str = "Group 1"):
    region = api.region_named(app.scene.mesh, name)
    return None if region is None else region.faces


# -- Pure functions -------------------------------------------------------------------


def test_assign_add_remove_delete_keep_order_and_none_without_regions():
    faces = _grid(2).all_face_ids()
    regions = api.assigned(None, "Brow", faces[:2])
    regions = api.added(regions, "Jaw", faces[2:3])
    assert [r.name for r in regions.regions] == ["Brow", "Jaw"]
    regions = api.added(regions, "Brow", faces[3:])
    assert regions.get("Brow").faces == frozenset(faces[:2]) | frozenset(faces[3:])
    regions = api.removed(regions, "Brow", faces[:1])
    assert faces[0] not in regions.get("Brow").faces
    assert api.removed(regions, "Jaw", faces[2:3]).get("Jaw") is None  # an emptied group is gone
    assert api.removed(None, "Brow", faces) is None
    assert api.deleted(api.deleted(regions, "Brow"), "Jaw") is None
    assert [r.name for r in api.assigned(regions, "Brow", faces[:1]).regions] == ["Brow", "Jaw"]


def test_grouped_takes_faces_from_other_groups_and_drops_emptied_ones():
    faces = _grid(2).all_face_ids()
    regions = api.grouped(None, "Group 1", faces[:2])
    regions = api.grouped(regions, "Group 2", faces[1:3])
    assert regions.get("Group 1").faces == {faces[0]}
    assert regions.get("Group 2").faces == {faces[1], faces[2]}
    regions = api.grouped(regions, "Group 2", faces[:1], add=True)
    assert regions.get("Group 1") is None
    assert regions.get("Group 2").faces == set(faces[:3])
    assert api.grouped(regions, "Group 2", faces[3:]).get("Group 2").faces == {faces[3]}


def test_new_group_names_count_up_and_set_names_cycle():
    faces = _grid(2).all_face_ids()
    assert api.new_group_name(None) == "Group 1"
    regions = api.grouped(api.grouped(None, "Group 1", faces[:1]), "Group 3", faces[1:2])
    assert api.new_group_name(regions) == "Group 4"
    assert api.next_name(regions, "Group 1") == "Brow"
    regions = api.renamed(regions, "Group 1", "Brow")
    assert [r.name for r in regions.regions] == ["Brow", "Group 3"]
    assert api.next_name(regions, "Group 3") == "Upper Lip"  # Brow is taken
    assert api.next_name(regions, "Brow") == "Upper Lip"
    regions = api.renamed(regions, "Group 3", "Jaw")
    assert api.next_name(regions, "Jaw") == "Group 1"  # after the last set name: back to an automatic name
    assert api.renamed(regions, "Brow", "Jaw") is regions  # a taken name is refused
    assert api.slot_index("Brow") != api.slot_index("Group 1") != api.slot_index("Group 2")


def test_live_and_lost_faces_filter_dead_ids_on_read_only():
    mesh = _grid(2)
    faces = mesh.all_face_ids()
    mesh.face_regions = api.assigned(None, "Brow", faces[:3])
    mesh.delete_faces([faces[0]])
    assert api.live_faces(mesh, "Brow") == frozenset(faces[1:3])
    assert api.lost_count(mesh, "Brow") == 1
    assert faces[0] in mesh.face_regions.get("Brow").faces  # the stored value keeps the dead ID
    assert api.live_faces(mesh, "Nope") == frozenset() and api.lost_count(mesh, "Nope") == 0


def test_faces_from_vertices_needs_all_corners_and_elements_convert():
    mesh = _grid(2)
    faces = mesh.all_face_ids()
    corners = set(mesh.face_vertices(faces[0]))
    assert api.faces_from_vertices(mesh, corners) == {faces[0]}
    assert api.faces_from_vertices(mesh, set(list(corners)[:3])) == set()
    assert api.elements_of(mesh, SelectionMode.FACE, frozenset(faces[:1])) == {faces[0]}
    assert api.elements_of(mesh, SelectionMode.VERTEX, frozenset(faces[:1])) == corners
    edges = api.elements_of(mesh, SelectionMode.EDGE, frozenset(faces[:1]))
    assert {v for e in edges for v in mesh.edge_vertices(e)} >= corners and len(edges) == 4


# -- App path ------------------------------------------------------------------------


def test_new_group_is_one_undo_step_and_restores_exactly(app):
    faces = _select_faces(app)
    assert app.key_press(NEW)
    assert _stored(app) == frozenset(faces)
    assert "Group 1" in app.status_message and app.active_region == "Group 1"
    assert app.key_press(UNDO)
    assert app.scene.mesh.face_regions is None and app.active_region is None
    assert app.key_press(REDO)
    assert _stored(app) == frozenset(faces)


def test_ctrl_g_always_makes_a_new_group_and_never_overwrites_one(app):
    """Manu 2026-10-25: a second group must not need a slot switch first, or it overwrites the first one."""
    first = _select_faces(app, 4, 100)
    app.key_press(NEW)
    second = _select_faces(app, 4, 200)
    app.key_press(NEW)
    assert _stored(app, "Group 1") == frozenset(first)
    assert _stored(app, "Group 2") == frozenset(second)
    assert app.active_region == "Group 2"
    assert api.region_named(app.scene.mesh, "Brow") is None  # no set name unless the artist saves one


def test_new_group_takes_its_faces_out_of_the_old_group(app):
    first = sorted(_select_faces(app, 4, 100))
    app.key_press(NEW)
    app.selection.set(set(first[:2]))
    app.key_press(NEW)
    assert _stored(app, "Group 1") == frozenset(first[2:])
    assert _stored(app, "Group 2") == frozenset(first[:2])
    app.selection.set(set(first[2:]))
    app.key_press(NEW)
    assert _stored(app, "Group 1") is None  # emptied, gone
    assert [r.name for r in app.scene.mesh.face_regions.regions] == ["Group 2", "Group 3"]


def test_next_and_prev_cycle_the_existing_groups(app):
    _select_faces(app, 4, 100)
    app.key_press(NEW)
    _select_faces(app, 4, 200)
    app.key_press(NEW)
    assert app.key_press(NEXT) and app.active_region == "Group 1"  # wraps
    assert app.key_press(NEXT) and app.active_region == "Group 2"
    assert app.key_press(PREV) and app.active_region == "Group 1"


def test_name_saves_the_active_group_as_a_set_and_cycles(app):
    faces = _select_faces(app)
    app.key_press(NEW)
    assert app.key_press(NAME)
    assert _stored(app, "Brow") == frozenset(faces) and _stored(app) is None
    assert app.active_region == "Brow" and "saved as Brow" in app.status_message
    assert app.key_press(NAME) and app.active_region == "Upper Lip"
    app.key_press(UNDO)
    assert _stored(app, "Brow") == frozenset(faces)
    app.key_press(UNDO)
    assert _stored(app) == frozenset(faces)


def test_add_and_remove_change_the_active_region(app):
    faces = sorted(_select_faces(app, 4, 100))
    app.key_press(NEW)
    more = _select_faces(app, 2, 300)
    assert app.key_press(ADD)
    assert _stored(app) == frozenset(faces) | frozenset(more)
    app.selection.set(set(faces[:2]))
    assert app.key_press(REMOVE)
    assert _stored(app) == frozenset(faces[2:]) | frozenset(more)


def test_vertex_selection_assigns_the_faces_whose_corners_are_all_selected(app):
    mesh = app.scene.mesh
    face = mesh.all_face_ids()[150]
    app.selection.mode = SelectionMode.VERTEX
    app.selection.set(set(mesh.face_vertices(face)))
    app.viewport.on_selection_changed()
    assert app.key_press(NEW)
    assert face in _stored(app)
    assert all(set(mesh.face_vertices(f)) <= set(mesh.face_vertices(face)) for f in _stored(app))


def test_select_region_writes_the_normal_selection_in_each_mode(app):
    mesh = app.scene.mesh
    faces = _select_faces(app)
    app.key_press(NEW)
    app.selection.clear()
    assert app.key_press(SELECT)
    assert app.selection.faces == faces
    app.selection.mode = SelectionMode.VERTEX
    app.selection.clear()
    assert app.key_press(SELECT)
    assert app.selection.vertices == api.region_vertices(mesh, faces)
    app.selection.mode = SelectionMode.EDGE
    app.selection.clear()
    assert app.key_press(SELECT)
    assert app.selection.edges == api.region_edges(mesh, faces)
    app.selection.mode = SelectionMode.FACE
    app.selection.set(set(mesh.all_face_ids()[:1]))
    assert app.key_press(SELECT_ADD)
    assert faces <= app.selection.faces and len(app.selection.faces) == len(faces) + 1


def test_selecting_a_region_never_selects_hidden_faces(app):
    mesh = app.scene.mesh
    faces = sorted(_select_faces(app))
    app.key_press(NEW)
    victim = mesh.face_vertices(faces[0])[0]
    app._hidden.hide([victim])
    app._hidden_push()
    app.selection.clear()
    assert app.key_press(SELECT)
    assert app.selection.faces
    assert not any(app._hidden.is_hidden_face(mesh, f) for f in app.selection.faces)


def test_isolate_and_mask_act_on_the_whole_group_even_partly_hidden(app):
    mesh = app.scene.mesh
    faces = sorted(_select_faces(app))
    app.key_press(NEW)
    app._hidden.hide([mesh.face_vertices(faces[0])[0]])
    app._hidden_push()
    verts = api.region_vertices(mesh, faces)
    assert app.key_press(MASK)
    assert app._mask.full() == frozenset(verts)
    assert app.key_press(ISOLATE)
    assert app._hidden.vertices() == frozenset(mesh.all_vertex_ids()) - verts


def test_isolate_and_mask_by_region_use_its_vertices_and_write_no_history(app):
    mesh = app.scene.mesh
    faces = _select_faces(app)
    app.key_press(NEW)
    app.selection.clear()
    depth = len(app.history.undo_stack) if hasattr(app.history, "undo_stack") else None
    verts = api.region_vertices(mesh, faces)
    assert app.key_press(MASK)
    assert app._mask.full() == frozenset(verts)
    assert app.key_press(ISOLATE)
    assert app._hidden.vertices() == frozenset(mesh.all_vertex_ids()) - verts
    if depth is not None:
        assert len(app.history.undo_stack) == depth
    assert app.key_press(SHOW_ALL)
    assert not app._hidden


def test_every_region_command_has_its_own_chord():
    from mirai.interaction import commands as cmd
    from mirai.interaction.bindings import build_default_bindings

    bindings = build_default_bindings()
    region_commands = [getattr(cmd, n) for n in dir(cmd) if n.startswith("REGION_")]
    chords = [bindings.inputs_for(c) for c in region_commands]
    assert all(len(c) == 1 for c in chords), chords
    flat = [i for c in chords for i in c]
    assert len(set(flat)) == len(flat)
    for chord in flat:
        assert bindings.command_for(chord) in region_commands


def test_group_commands_without_groups_are_refused_with_a_hint(app):
    assert not app.key_press(SELECT)
    assert "Ctrl+G" in app.status_message
    assert not app.key_press(DELETE)
    assert not app.key_press(NEXT)
    assert not app.key_press(NAME)
    app.selection.clear()
    assert not app.key_press(NEW)


def test_delete_region_is_undoable(app):
    _select_faces(app)
    app.key_press(NEW)
    assert app.key_press(DELETE)
    assert app.scene.mesh.face_regions is None
    app.key_press(UNDO)
    assert _stored(app) is not None


def test_deleting_faces_keeps_the_stored_value_and_undo_makes_the_region_whole(app):
    mesh = app.scene.mesh
    faces = sorted(_select_faces(app, 6))
    app.key_press(NEW)
    app.selection.set({faces[0]})
    assert app.key_press(_key("delete"))
    assert api.lost_count(mesh, "Group 1") == 1
    assert faces[0] in mesh.face_regions.get("Group 1").faces
    app.key_press(NEXT)
    assert "lost" in app.status_message
    app.key_press(UNDO)
    assert api.lost_count(mesh, "Group 1") == 0 and len(api.live_faces(mesh, "Group 1")) == 6


def test_topology_edits_do_not_carry_regions_along_yet(app):
    """AD-REGIONS-01 §1.6: no inheritance in this slice. Pinned so that Slice 3 has to flip it on purpose."""
    mesh = app.scene.mesh
    faces = _select_faces(app, 4)
    app.key_press(NEW)
    before = mesh.face_regions
    edge = next(e for e in mesh.all_edge_ids() if set(mesh.edge_faces(e)) & faces)
    app.selection.mode = SelectionMode.EDGE
    app.selection.set({edge})
    app.viewport.on_selection_changed()
    vertex_count = len(mesh.all_vertex_ids())
    assert app.key_press(_key("c"))  # Split
    assert len(mesh.all_vertex_ids()) == vertex_count + 1  # the topology really changed
    assert mesh.face_regions == before  # and the stored value did not follow


def test_regions_ride_through_save_and_load(app):
    faces = _select_faces(app)
    app.key_press(NEW)
    restored = scene_from_dict(scene_to_dict(app.scene))
    assert restored.mesh.face_regions == app.scene.mesh.face_regions
    assert restored.mesh.face_regions.get("Group 1").faces == frozenset(faces)


def test_each_edit_object_keeps_its_own_regions_and_active_group(app):
    _select_faces(app, 4, 100)
    app.key_press(NEW)
    _select_faces(app, 4, 200)
    app.key_press(NEW)
    app.key_press(NEXT)
    first = app.scene.edit_object_id
    other = app.add_primitive("cube")
    app._objects.set_edit_object(other.id if hasattr(other, "id") else other)
    assert app.scene.mesh.face_regions is None and app.active_region is None
    app._objects.set_edit_object(first)
    assert app.scene.mesh.face_regions is not None and app.active_region == "Group 1"


def test_scene_load_resets_the_active_group(app):
    _select_faces(app)
    app.key_press(NEW)
    app.init_scene("cube")
    assert app.active_region is None and app.scene.mesh.face_regions is None


def test_symmetry_assign_takes_the_mirror_partners(app):
    app.key_press(_key("s", "shift"))  # symmetry on
    mesh = app.scene.mesh
    if mesh.symmetry_definition is None:
        pytest.skip("symmetry did not switch on for this fixture")
    from mirai.symmetry_coordination import SymmetryIndex

    index = SymmetryIndex(mesh)
    face = next(f for f in mesh.all_face_ids() if index.face_partner(f) not in (None, f))
    app.selection.set({face})
    app.viewport.on_selection_changed()
    assert app.key_press(NEW)
    assert {face, index.face_partner(face)} <= _stored(app)


def test_assigning_a_whole_large_mesh_region_is_cheap(app):
    mesh = app.scene.mesh
    app.selection.set(set(mesh.all_face_ids()))
    app.viewport.on_selection_changed()
    started = time.perf_counter()
    assert app.key_press(NEW)
    assert time.perf_counter() - started < 5.0
    assert len(api.live_faces(mesh, "Group 1")) == len(mesh.all_face_ids())
