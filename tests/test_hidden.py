"""Hide / Isolate / Show all (`mirai.hidden`, docs/future_ideas/MODELING.md, Priorität 1; PROVISIONAL).

Container rules, the `RenderMesh` patch (hidden triangles become degenerate, a later topology patch and a
fresh build agree), CPU picking, and the app path: Ctrl+H / Ctrl+Shift+H / Alt+H write no History, the
selection never keeps a hidden element, transforms skip hidden vertices, topology edits next to hidden
geometry are refused."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401

import viewport.render_mesh as render_mesh_module
from core import SelectionMode
from core.mesh import Mesh
from mirai.application import Application
from mirai.hidden import HiddenSet, touches_hidden
from mirai.interaction.input import Input
from mirai.viewport.picking_cache import PickCache
from viewport.render_mesh import RenderMesh
from viewport.resource_store import TraceStore

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


CTRL_H, CTRL_SHIFT_H, ALT_H = _key("h", "ctrl"), _key("h", "ctrl", "shift"), _key("h", "alt")
W, O = _key("w"), _key("o")


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
    return app


def _select(app, *indices):
    ids = app.scene.mesh.all_vertex_ids()
    chosen = {ids[i] for i in indices}
    app.selection.set(chosen)
    app.viewport.on_selection_changed()
    return chosen


def _positions(app) -> dict:
    mesh = app.scene.mesh
    return {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}


# -- Container ---------------------------------------------------------------------


def test_container_derives_edges_and_faces_from_vertices():
    mesh = _grid(2)
    vids = mesh.all_vertex_ids()
    hidden = HiddenSet()
    hidden.hide([vids[0]])
    edge = next(e for e in mesh.all_edge_ids() if vids[0] in mesh.edge_vertices(e))
    face = next(f for f in mesh.all_face_ids() if vids[0] in mesh.face_vertices(f))
    assert hidden.is_hidden_edge(mesh, edge) and hidden.is_hidden_face(mesh, face)
    far = vids[-1]
    assert not hidden.is_hidden_vertex(far)
    assert touches_hidden(mesh, hidden, [mesh.edge_vertices(edge)[1]])
    assert not touches_hidden(mesh, hidden, [far])
    hidden.show_all()
    assert not hidden


def test_isolate_hides_everything_else():
    mesh = _grid(2)
    keep = set(mesh.all_vertex_ids()[:3])
    hidden = HiddenSet()
    hidden.isolate(mesh, keep)
    assert hidden.vertices() == frozenset(mesh.all_vertex_ids()) - keep


# -- RenderMesh --------------------------------------------------------------------


@pytest.mark.parametrize("incremental", [False, True], ids=["compact", "slots"])
def test_render_mesh_hides_triangles_and_edges_then_restores(monkeypatch, incremental):
    monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 0 if incremental else 10**9)
    mesh = _grid(4)
    rm = RenderMesh(mesh, store_type=TraceStore)
    before = list(rm.store.data("indices"))
    edges_before = list(rm.edge_indices)
    victim = mesh.all_vertex_ids()[6]
    rm.set_hidden([victim])
    indices = rm.store.data("indices")
    for f, slots in rm._face_triangles.items():
        touches = victim in mesh.face_vertices(f)
        for t in slots:
            values = indices[3 * t:3 * t + 3]
            if touches:  # the whole face goes, also the triangle of a quad that lacks the victim
                assert values == [0.0, 0.0, 0.0]
                assert rm.face_of_triangle(t) is None
            else:
                assert values == before[3 * t:3 * t + 3]
    assert rm.vertex_of_slot(rm.vertex_index_of(victim)) is None
    for e, slot in rm._edge_slot.items():
        hidden_edge = victim in mesh.edge_vertices(e)
        assert (tuple(rm.edge_indices[2 * slot:2 * slot + 2]) == (0, 0)) == hidden_edge
        assert (rm.edge_of_slot(slot) is None) == hidden_edge
    revision = rm.content_revision
    rm.set_hidden([victim])  # same set: nothing to do
    assert rm.content_revision == revision
    rm.set_hidden(())
    assert list(rm.store.data("indices")) == before
    assert list(rm.edge_indices) == edges_before


def test_render_mesh_topology_patch_keeps_hidden(monkeypatch):
    monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 0)
    mesh = _grid(4)
    rm = RenderMesh(mesh, store_type=TraceStore)
    hidden = [mesh.all_vertex_ids()[6]]
    rm.set_hidden(hidden)
    rm.mark_topology_dirty()
    face = next(f for f in mesh.all_face_ids() if hidden[0] not in mesh.face_vertices(f))
    mesh.delete_faces([face])
    rm.sync()
    fresh = RenderMesh(mesh, store_type=TraceStore)
    fresh.set_hidden(hidden)
    for f in mesh.all_face_ids():
        mine = [rm.store.data("indices")[3 * t:3 * t + 3] for t in rm._face_triangles[f]]
        theirs = [fresh.store.data("indices")[3 * t:3 * t + 3] for t in fresh._face_triangles[f]]
        # slot numbering differs between a patch and a fresh build, the vertex slots do not
        assert [m == [0.0, 0.0, 0.0] for m in mine] == [t == [0.0, 0.0, 0.0] for t in theirs]
    fresh._watch.close()


def test_render_mesh_hides_whole_faces_without_their_vertices():
    mesh = _grid(3)
    rm = RenderMesh(mesh, store_type=TraceStore)
    face = mesh.all_face_ids()[4]
    rm.set_hidden(faces=[face])
    for t in rm._face_triangles[face]:
        assert rm.store.data("indices")[3 * t:3 * t + 3] == [0.0, 0.0, 0.0]
        assert rm.face_of_triangle(t) is None
    other = mesh.all_face_ids()[0]
    assert all(rm.face_of_triangle(t) == other for t in rm._face_triangles[other])
    assert all(rm.vertex_of_slot(i) is not None for i in range(len(rm._slot_vertex)))


# -- PickCache ----------------------------------------------------------------------


def test_pick_cache_has_no_screen_position_for_hidden_vertices(app):
    mesh = app.scene.mesh
    cache = PickCache()
    victim = mesh.all_vertex_ids()[100]
    cache.set_hidden([victim])
    cache.refresh(app._objects.edit_camera, mesh, WIDTH, HEIGHT)
    assert victim not in cache.vertex_screen
    assert cache.hidden_faces == frozenset(
        f for f in mesh.all_face_ids() if victim in mesh.face_vertices(f)
    )
    cache.set_hidden(())
    cache.refresh(app._objects.edit_camera, mesh, WIDTH, HEIGHT)
    assert victim in cache.vertex_screen and not cache.hidden_faces


# -- App path ------------------------------------------------------------------------


def test_hide_isolate_show_all_write_no_history_and_keep_the_mesh(app):
    chosen = _select(app, 100, 101)
    positions = _positions(app)
    depth = len(app.history.undo_stack) if hasattr(app.history, "undo_stack") else None
    assert app.key_press(CTRL_H)
    assert app._hidden.vertices() >= chosen
    assert not (app.selection.vertices & app._hidden.vertices())
    assert app.viewport.render_mesh.hidden_vertices == app._hidden.vertices()
    assert app.key_press(ALT_H)
    assert not app._hidden and not app.viewport.render_mesh.hidden_vertices
    _select(app, 100, 101)
    assert app.key_press(CTRL_SHIFT_H)
    total = len(app.scene.mesh.all_vertex_ids())
    assert len(app._hidden) == total - len(chosen)
    assert app.selection.vertices == chosen  # Isolate keeps what it isolated
    assert _positions(app) == positions
    if depth is not None:
        assert len(app.history.undo_stack) == depth


def test_hide_everything_is_refused(app):
    ids = app.scene.mesh.all_vertex_ids()
    app.selection.set(set(ids))
    assert not app.key_press(CTRL_H)
    assert not app._hidden


def test_show_all_with_nothing_hidden_does_nothing(app):
    assert not app.key_press(ALT_H)


def test_hidden_vertices_do_not_move_under_soft_selection(app):
    ids = app.scene.mesh.all_vertex_ids()
    seed = ids[100]
    app.selection.set({seed})
    app.viewport.on_selection_changed()
    app.key_press(O)
    before = _positions(app)
    assert app.key_press(W)
    for dx, dy in ((6, 2), (5, 3), (4, -1)):
        app.pointer_motion(300.0, 300.0, float(dx), float(dy))
    assert app.key_release(W)
    neighbours = {v for v, p in _positions(app).items() if p != before[v]} - {seed}
    assert neighbours
    app.key_press(_key("z", "ctrl"))
    app._hidden.hide(neighbours)
    app._hidden_push()
    app.selection.set({seed})
    app.key_press(W)
    for dx, dy in ((6, 2), (5, 3), (4, -1)):
        app.pointer_motion(300.0, 300.0, float(dx), float(dy))
    app.key_release(W)
    after = _positions(app)
    assert all(after[v] == before[v] for v in neighbours)
    assert after[seed] != before[seed]


def test_topology_edit_next_to_hidden_geometry_is_refused(app):
    mesh = app.scene.mesh
    ids = mesh.all_vertex_ids()
    victim = ids[100]
    neighbour = next(
        (set(mesh.edge_vertices(e)) - {victim}).pop() for e in mesh.all_edge_ids()
        if victim in mesh.edge_vertices(e)
    )
    app._hidden.hide([victim])
    app._hidden_push()
    app.selection.set({neighbour})
    app.viewport.on_selection_changed()
    faces_before = len(mesh.all_face_ids())
    assert not app.key_press(_key("backspace"))  # Dissolve
    assert len(mesh.all_face_ids()) == faces_before
    assert "hidden geometry" in app.status_message


def test_scene_load_clears_hidden(app):
    _select(app, 100)
    app.key_press(CTRL_H)
    assert app._hidden
    app.init_scene("cube")
    assert not app._hidden and not app._pick_cache.hidden


def test_each_edit_object_keeps_its_own_hidden_set(app):
    _select(app, 100)
    app.key_press(CTRL_H)
    first = app.scene.edit_object_id
    other = app.add_primitive("cube")
    app._objects.set_edit_object(other.id if hasattr(other, "id") else other)
    assert not app._hidden
    assert not app.viewport.render_mesh.hidden_vertices
    app._objects.set_edit_object(first)
    assert app._hidden and app.viewport.render_mesh.hidden_vertices


# -- SubD surface -----------------------------------------------------------------------


def test_subd_surface_hides_the_derived_faces_of_hidden_cage_faces():
    import tests.subdivision_meshes  # noqa: F401  (examples/ on sys.path)
    from loaders.assets import asset_path
    from mirai.subdivision import VIEW_CAGE

    app = Application()
    app.init_scene("obj", obj_path=asset_path("subd_cube"))
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    while app.subdivision.view != VIEW_CAGE:
        assert app.key_press(_key("v"))
    app.viewport.sync()
    mesh = app.scene.mesh
    provider = app.subdivision.provider
    assert provider.surface_mesh is not None
    assert provider.hidden_surface_faces() == frozenset()

    victim = mesh.all_vertex_ids()[0]
    app.selection.set({victim})
    app.viewport.on_selection_changed()
    assert app.key_press(CTRL_H)
    app.viewport.sync()
    hidden_faces = provider.hidden_surface_faces()
    cage_faces = [f for f in mesh.all_face_ids() if victim in mesh.face_vertices(f)]
    _level, _vertex_ids, derived_face_ids = provider.derived_elements()
    assert hidden_faces and len(hidden_faces) < len(derived_face_ids)
    # every cage face of a cube corner subdivides into the same number of faces
    assert len(hidden_faces) == len(cage_faces) * len(derived_face_ids) // len(mesh.all_face_ids())
    rm = app.viewport.surface_render_mesh
    for f in hidden_faces:
        for t in rm._face_triangles[f]:
            assert rm.store.data("indices")[3 * t:3 * t + 3] == [0.0, 0.0, 0.0]
    assert app.key_press(ALT_H)
    app.viewport.sync()
    assert provider.hidden_surface_faces() == frozenset()
    for f in hidden_faces:
        for t in rm._face_triangles[f]:
            assert rm.store.data("indices")[3 * t:3 * t + 3] != [0.0, 0.0, 0.0]
    # the cage and isoline segments of the hidden corner's edges are gone too
    app.key_press(_key("v"))  # cage -> iso view
    app.viewport.sync()
    lines = app.subdivision.lines
    full_cage, full_iso = len(lines.segments["subd_cage"]), len(lines.segments["subd_iso"])
    app.selection.set({victim})
    app.viewport.on_selection_changed()
    app.key_press(CTRL_H)
    app.viewport.sync()
    assert 0 < len(lines.segments["subd_cage"]) < full_cage
    assert 0 < len(lines.segments["subd_iso"]) < full_iso
    app.key_press(ALT_H)
    app.viewport.sync()
    assert len(lines.segments["subd_cage"]) == full_cage and len(lines.segments["subd_iso"]) == full_iso
