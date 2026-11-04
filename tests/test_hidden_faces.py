"""Polygon-exact Hide (Manu 2026-11-04, I1 "Hide exactly the selected Polygons"; audit Hide/Show + Region Colours +
Morph, slice 3).

Face mode hides exactly the selected faces: a neighbour that shares a corner or an edge stays whole. An edge or vertex
goes when all faces around it are hidden (and one of them explicitly); vertex and edge mode keep the vertex rule. One
rule (`viewport.hidden_rule`) for the container, the `RenderMesh` (triangles, edge slots, vertex slots), the wire, the
CPU pick cache (vertex / edge / face, box), the SubD surface and its cage lines, loops / rings and topology refusals.
Region Isolate / Invert / Hide act on faces (no interior-vertex workaround)."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

import viewport.render_mesh as render_mesh_module
from core import FaceRegion, FaceRegions, SelectionMode, SymmetryDefinition
from core.mesh import Mesh
from mirai.application import Application
from mirai.hidden import HiddenSet, mirrored_faces, touches_hidden
from mirai.interaction.input import Input
from mirai.topology.loop_ring import edge_loop, edge_ring
from mirai.viewport.box_select import elements_in_rect
from mirai.viewport.picking import pick_face, pick_nearest_edge, pick_nearest_vertex
from mirai.viewport.picking_cache import PickCache
from viewport.hidden_rule import resolve, resolve_indexed
from viewport.render_mesh import RenderMesh
from viewport.resource_store import TraceStore
from viewport.wireframe import edge_segments

WIDTH, HEIGHT = 800, 600
N = 4


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


CTRL_H, CTRL_SHIFT_H, ALT_H = _key("h", "ctrl"), _key("h", "ctrl", "shift"), _key("h", "alt")
SHIFT_L, I_KEY = _key("l", "shift"), _key("i")
K1, K2, K3 = _key("1"), _key("2"), _key("3")


def _grid(n: int = N, size: float = 4.0) -> Mesh:
    """n x n quads over [-size/2, size/2]^2 in z = 0 (1 unit per quad for the defaults)."""
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


def _vertex(mesh, x: float, y: float):
    (vid,) = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (x, y)]
    return vid


def _edge(mesh, a, b):
    (eid,) = [e for e in mesh.vertex_edges(a) if set(mesh.edge_vertices(e)) == {a, b}]
    return eid


def _face_at(mesh, x: float, y: float):
    """The quad whose lower-left corner is (x, y)."""
    corner = _vertex(mesh, x, y)
    (face,) = [
        f for f in mesh.all_face_ids()
        if corner in mesh.face_vertices(f)
        and all(mesh.vertex_position(v)[0] >= x and mesh.vertex_position(v)[1] >= y for v in mesh.face_vertices(f))
    ]
    return face


def _block(mesh) -> set:
    """The 2 x 2 quads around the centre (0, 0)."""
    return {_face_at(mesh, x, y) for x in (-1.0, 0.0) for y in (-1.0, 0.0)}


def _neighbours(mesh, faces) -> set:
    corners = {v for f in faces for v in mesh.face_vertices(f)}
    return {f for f in mesh.all_face_ids() if f not in faces and corners & set(mesh.face_vertices(f))}


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_grid().export_state())
    app.viewport.on_topology_changed()
    app.frame_scene()
    app.camera.yaw = 0.0
    app.camera.pitch = 0.0
    app.camera.camera_revision += 1
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _face_mode(app, faces) -> None:
    app.selection.mode = SelectionMode.FACE
    app.selection.set(set(faces))
    app.viewport.on_selection_changed()


def _screen(app, x: float, y: float):
    return app.camera.project_to_screen((x, y, 0.0), WIDTH, HEIGHT)


# -- the rule --------------------------------------------------------------------------------------------


def test_one_hidden_face_takes_only_itself():
    mesh = _grid()
    face = _face_at(mesh, 0.0, 0.0)
    resolved = resolve(mesh, faces=[face])
    assert resolved.faces == {face}
    assert not resolved.edges and not resolved.vertices  # every edge and corner still has a visible face


def test_a_hidden_block_takes_its_inner_edges_and_vertex_and_keeps_its_border():
    mesh = _grid()
    block = _block(mesh)
    resolved = resolve(mesh, faces=block)
    centre = _vertex(mesh, 0.0, 0.0)
    assert resolved.faces == block
    assert resolved.vertices == {centre}
    assert resolved.edges == set(mesh.vertex_edges(centre))  # the four edges between hidden faces
    hidden = HiddenSet()
    hidden.hide_faces(block)
    assert hidden.is_hidden_vertex(mesh, centre) and not hidden.is_hidden_vertex(mesh, _vertex(mesh, 1.0, 1.0))
    assert all(hidden.is_hidden_edge(mesh, e) == (e in resolved.edges) for e in mesh.all_edge_ids())
    assert all(hidden.is_hidden_face(mesh, f) == (f in block) for f in mesh.all_face_ids())


def test_a_hidden_face_at_the_border_takes_its_border_edge_and_outer_corner():
    mesh = _grid()
    face = _face_at(mesh, -2.0, -2.0)
    resolved = resolve(mesh, faces=[face])
    corner = _vertex(mesh, -2.0, -2.0)
    assert resolved.vertices == {corner}
    assert resolved.edges == set(mesh.vertex_edges(corner))  # the two border edges with no other face


def test_vertex_mode_keeps_the_vertex_rule():
    """Without hidden faces nothing changes: an isolated pair of vertices stays visible as points and wire, although
    every face around it is hidden through its other corners."""
    mesh = _grid()
    a, b = _vertex(mesh, 0.0, 0.0), _vertex(mesh, 1.0, 0.0)
    hidden = HiddenSet()
    hidden.isolate(mesh, {a, b})
    resolved = hidden.resolve(mesh)
    assert resolved.faces == set(mesh.all_face_ids())
    assert a not in resolved.vertices and b not in resolved.vertices
    assert _edge(mesh, a, b) not in resolved.edges
    assert not hidden.hides_everything(mesh)


def test_an_edge_between_a_hidden_face_and_a_face_hidden_by_a_vertex_is_hidden():
    mesh = _grid()
    left, right = _face_at(mesh, -1.0, 0.0), _face_at(mesh, 0.0, 0.0)
    shared = _edge(mesh, _vertex(mesh, 0.0, 0.0), _vertex(mesh, 0.0, 1.0))
    far_corner = _vertex(mesh, 1.0, 0.0)  # a corner of `right` only
    resolved = resolve(mesh, vertices=[far_corner], faces=[left])
    assert {left, right} <= resolved.faces
    assert shared in resolved.edges


def test_the_indexed_rule_agrees_with_the_mesh_rule():
    mesh = _grid()
    vids, eids, fids = mesh.all_vertex_ids(), mesh.all_edge_ids(), mesh.all_face_ids()
    vi = {v: i for i, v in enumerate(vids)}
    corners = [tuple(vi[v] for v in mesh.face_vertices(f)) for f in fids]
    edges = [tuple(vi[v] for v in mesh.edge_vertices(e)) for e in eids]
    block = _block(mesh)
    extra = _vertex(mesh, 2.0, 2.0)
    resolved = resolve(mesh, vertices=[extra], faces=block)
    faces, hidden_edges = resolve_indexed(corners, edges, {vi[extra]}, {fids.index(f) for f in block})
    assert {fids[i] for i in faces} == resolved.faces
    assert {eids[i] for i in hidden_edges} == resolved.edges


@pytest.mark.parametrize("v_share", [0.0, 0.1, 0.9])
@pytest.mark.parametrize("f_share", [0.0, 0.1, 0.9])
@pytest.mark.parametrize("seed", [1, 2])
def test_resolve_agrees_with_the_element_rule_on_every_path(seed, f_share, v_share):
    """Small and large hidden sets (the large ones take the complement walks) give what the per-element rule says."""
    import random

    from viewport.hidden_rule import edge_is_hidden, face_is_hidden, vertex_is_hidden

    rng = random.Random(seed)
    mesh = _grid(6, 6.0)
    loose = mesh.add_vertex((9.0, 9.0, 0.0))
    wire = mesh.add_edge(loose, mesh.all_vertex_ids()[0])
    vids, fids = mesh.all_vertex_ids(), mesh.all_face_ids()
    vertices = {v for v in vids if rng.random() < v_share}
    faces = {f for f in fids if rng.random() < f_share}
    resolved = resolve(mesh, vertices, faces)
    assert resolved.vertices == {v for v in vids if vertex_is_hidden(mesh, v, vertices, faces)}
    assert resolved.edges == {e for e in mesh.all_edge_ids() if edge_is_hidden(mesh, e, vertices, faces)}
    assert resolved.faces == {f for f in fids if face_is_hidden(mesh, f, vertices, faces)}
    assert (wire in resolved.edges) == bool({loose, vids[0]} & vertices)


def test_isolate_faces_hides_every_other_face_and_loose_vertices():
    mesh = _grid()
    loose = mesh.add_vertex((5.0, 5.0, 0.0))
    keep = {_face_at(mesh, 0.0, 0.0)}
    hidden = HiddenSet()
    hidden.isolate_faces(mesh, keep)
    assert hidden.faces() == frozenset(mesh.all_face_ids()) - keep
    assert hidden.vertices() == {loose}
    resolved = hidden.resolve(mesh)
    assert set(mesh.face_vertices(next(iter(keep)))).isdisjoint(resolved.vertices)
    assert set(mesh.face_edges(next(iter(keep)))).isdisjoint(resolved.edges)


# -- RenderMesh, wire --------------------------------------------------------------------------------------


@pytest.mark.parametrize("incremental", [False, True], ids=["compact", "slots"])
def test_render_mesh_hides_the_block_its_inner_edges_and_vertex_then_restores(monkeypatch, incremental):
    monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 0 if incremental else 10**9)
    mesh = _grid()
    rm = RenderMesh(mesh, store_type=TraceStore)
    before = list(rm.store.data("indices"))
    edges_before = list(rm.edge_indices)
    block = _block(mesh)
    centre = _vertex(mesh, 0.0, 0.0)
    inner = set(mesh.vertex_edges(centre))
    rm.set_hidden(faces=block)
    indices = rm.store.data("indices")
    for f, slots in rm._face_triangles.items():
        for t in slots:
            if f in block:
                assert indices[3 * t:3 * t + 3] == [0.0, 0.0, 0.0] and rm.face_of_triangle(t) is None
            else:
                assert indices[3 * t:3 * t + 3] == before[3 * t:3 * t + 3] and rm.face_of_triangle(t) == f
    for e, slot in rm._edge_slot.items():
        dead = tuple(rm.edge_indices[2 * slot:2 * slot + 2]) == (0, 0)
        assert dead == (e in inner) and (rm.edge_of_slot(slot) is None) == (e in inner)
    assert rm.vertex_of_slot(rm.vertex_index_of(centre)) is None
    border = _vertex(mesh, 1.0, 1.0)
    assert rm.vertex_of_slot(rm.vertex_index_of(border)) == border
    assert rm.resolved_hidden.edges == inner
    rm.set_hidden()
    assert list(rm.store.data("indices")) == before
    assert list(rm.edge_indices) == edges_before


def test_render_mesh_topology_patch_and_fresh_build_agree_on_hidden_faces(monkeypatch):
    """A face added beside a hidden border face makes their shared edge visible again; the patch agrees with a build."""
    monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 0)
    mesh = _grid()
    rm = RenderMesh(mesh, store_type=TraceStore)
    face = _face_at(mesh, -2.0, -2.0)
    a, b = _vertex(mesh, -2.0, -2.0), _vertex(mesh, -1.0, -2.0)
    bottom = _edge(mesh, a, b)
    rm.set_hidden(faces=[face])
    assert bottom in rm.resolved_hidden.edges
    c, d = mesh.add_vertex((-1.0, -3.0, 0.0)), mesh.add_vertex((-2.0, -3.0, 0.0))
    mesh.add_face([d, c, b, a])
    rm.mark_topology_dirty()
    rm.sync()
    assert bottom not in rm.resolved_hidden.edges
    fresh = RenderMesh(mesh, store_type=TraceStore)
    fresh.set_hidden(faces=[face])
    assert fresh.resolved_hidden == rm.resolved_hidden
    for e in mesh.all_edge_ids():
        mine = tuple(rm.edge_indices[2 * rm._edge_slot[e]:2 * rm._edge_slot[e] + 2]) == (0, 0)
        theirs = tuple(fresh.edge_indices[2 * fresh._edge_slot[e]:2 * fresh._edge_slot[e] + 2]) == (0, 0)
        assert mine == theirs, e
    fresh._watch.close()


def test_wire_leaves_out_the_resolved_edges():
    mesh = _grid()
    resolved = resolve(mesh, faces=_block(mesh))
    assert len(edge_segments(mesh)) - len(edge_segments(mesh, hidden_edges=resolved.edges)) == 4


# -- CPU picking ----------------------------------------------------------------------------------------------


def test_cpu_picking_skips_hidden_faces_inner_edges_and_the_inner_vertex(app):
    mesh = app.scene.mesh
    camera = app._objects.edit_camera
    block = _block(mesh)
    cache = PickCache()
    cache.set_hidden((), block)
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    centre = _vertex(mesh, 0.0, 0.0)
    assert cache.hidden == {centre} and cache.hidden_faces == block
    assert cache.hidden_edges == set(mesh.vertex_edges(centre))
    sx, sy = _screen(app, 0.0, 0.0)
    assert pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache) != centre
    sx, sy = _screen(app, 0.5, 0.0)  # on an inner edge
    picked = pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache)
    assert picked is None or picked not in cache.hidden_edges
    sx, sy = _screen(app, 0.5, 0.5)
    assert pick_face(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache) is None
    sx, sy = _screen(app, 1.5, 0.5)  # the neighbour stays pickable
    assert pick_face(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache) == _face_at(mesh, 1.0, 0.0)
    border = _vertex(mesh, 1.0, 1.0)
    sx, sy = _screen(app, 1.0, 1.0)
    assert pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache) == border


def test_box_select_skips_hidden_faces_and_edges(app):
    mesh = app.scene.mesh
    camera = app._objects.edit_camera
    block = _block(mesh)
    cache = PickCache()
    cache.set_hidden((), block)
    (x0, y0), (x1, y1) = _screen(app, -2.1, -2.1), _screen(app, 2.1, 2.1)
    rect = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    faces = elements_in_rect(camera, mesh, SelectionMode.FACE, rect, WIDTH, HEIGHT, cache=cache, occlusion=False)
    assert faces == set(mesh.all_face_ids()) - block
    edges = elements_in_rect(camera, mesh, SelectionMode.EDGE, rect, WIDTH, HEIGHT, cache=cache, occlusion=False)
    assert edges == set(mesh.all_edge_ids()) - set(mesh.vertex_edges(_vertex(mesh, 0.0, 0.0)))


# -- the app: Ctrl+H / Ctrl+Shift+H / Alt+H in face mode ---------------------------------------------------------


def test_face_mode_hide_takes_exactly_the_selected_faces(app):
    mesh = app.scene.mesh
    face = _face_at(mesh, 0.0, 0.0)
    _face_mode(app, {face})
    assert app.key_press(CTRL_H), app.status_message
    assert app._hidden.faces() == {face} and not app._hidden.vertices()
    for f in _neighbours(mesh, {face}):
        assert not app._hidden.is_hidden_face(mesh, f)  # the old vertex rule hid all eight neighbours
    rm = app.viewport.render_mesh
    assert rm.hidden_faces == {face}
    app._pick_cache.refresh(app._objects.edit_camera, mesh, WIDTH, HEIGHT)
    assert app._pick_cache.hidden_faces == {face}
    assert not app.selection.faces
    assert "1 faces" in app.status_message
    assert app.key_press(ALT_H)
    assert not app._hidden and not rm.hidden_faces


def test_face_mode_isolate_keeps_exactly_the_selected_faces(app):
    mesh = app.scene.mesh
    keep = {_face_at(mesh, 0.0, 0.0), _face_at(mesh, 1.0, 0.0)}
    _face_mode(app, keep)
    assert app.key_press(CTRL_SHIFT_H), app.status_message
    assert app._hidden.faces() == frozenset(mesh.all_face_ids()) - keep
    resolved = app._hidden.resolve(mesh)
    assert all(not set(mesh.face_vertices(f)) & resolved.vertices for f in keep)
    assert app.selection.faces == keep  # Isolate keeps what it isolated


def test_hiding_every_face_is_refused(app):
    mesh = app.scene.mesh
    _face_mode(app, set(mesh.all_face_ids()))
    assert not app.key_press(CTRL_H)
    assert not app._hidden
    assert "everything" in app.status_message


def test_vertex_mode_isolate_of_two_vertices_still_works(app):
    mesh = app.scene.mesh
    a, b = _vertex(mesh, 0.0, 0.0), _vertex(mesh, 1.0, 0.0)
    app.selection.mode = SelectionMode.VERTEX
    app.selection.set({a, b})
    assert app.key_press(CTRL_SHIFT_H), app.status_message
    assert app._hidden.vertices() == frozenset(mesh.all_vertex_ids()) - {a, b}
    assert app.selection.vertices == {a, b}


def test_symmetry_hides_the_mirror_face_too(app):
    mesh = app.scene.mesh
    seam = frozenset(
        e for e in mesh.all_edge_ids() if all(mesh.vertex_position(v)[0] == 0.0 for v in mesh.edge_vertices(e))
    )
    mesh.symmetry_definition = SymmetryDefinition((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), seam)
    face, partner = _face_at(mesh, 1.0, 0.0), _face_at(mesh, -2.0, 0.0)
    assert mirrored_faces(mesh, {face}) == {partner}
    assert mirrored_faces(mesh, {_face_at(mesh, 0.0, 0.0)}) == {_face_at(mesh, -1.0, 0.0)}  # seam corners
    _face_mode(app, {face})
    assert app.key_press(CTRL_H), app.status_message
    assert app._hidden.faces() == {face, partner}


def test_corners_of_hidden_faces_move_and_fully_hidden_vertices_do_not(app):
    mesh = app.scene.mesh
    block = _block(mesh)
    app._hidden.hide_faces(block)
    app._hidden_push()
    centre, corner = _vertex(mesh, 0.0, 0.0), _vertex(mesh, 1.0, 1.0)
    mask = app._mask_values([corner])
    assert mask.get(centre) == 1.0
    assert mask.get(corner, 0.0) == 0.0


# -- loops, rings, refusals -----------------------------------------------------------------------------------


def test_ring_stops_at_a_hidden_face_and_not_one_quad_early():
    mesh = _grid()
    start = _edge(mesh, _vertex(mesh, -2.0, -2.0), _vertex(mesh, -1.0, -2.0))
    hidden_face = _face_at(mesh, -2.0, 0.0)
    ring = edge_ring(mesh, start, resolve(mesh, faces=[hidden_face]))
    ys = sorted(min(mesh.vertex_position(v)[1] for v in mesh.edge_vertices(e)) for e in ring.edges)
    assert ys == [-2.0, -1.0, 0.0]  # the quads below the hidden one are cut, the hidden one is not
    assert not ring.closed


def test_loop_stops_at_the_corner_of_a_hidden_block():
    mesh = _grid()
    start = _edge(mesh, _vertex(mesh, -2.0, 0.0), _vertex(mesh, -1.0, 0.0))
    assert len(edge_loop(mesh, start).edges) == N
    loop = edge_loop(mesh, start, resolve(mesh, faces=_block(mesh)))
    xs = sorted(min(mesh.vertex_position(v)[0] for v in mesh.edge_vertices(e)) for e in loop.edges)
    assert xs == [-2.0]  # it reaches the block's corner (-1, 0) and does not run on through the hidden inner edge


def test_a_loop_along_a_hidden_face_is_not_cut():
    mesh = _grid()
    start = _edge(mesh, _vertex(mesh, -2.0, 1.0), _vertex(mesh, -1.0, 1.0))
    loop = edge_loop(mesh, start, resolve(mesh, faces=[_face_at(mesh, 0.0, 0.0)]))
    assert len(loop.edges) == N  # every edge of the row borders a visible face


def test_shift_l_and_loop_insert_stop_at_hidden_faces(app):
    mesh = app.scene.mesh
    _face_mode(app, _block(mesh))
    assert app.key_press(CTRL_H)
    app.key_press(K2)
    start = _edge(mesh, _vertex(mesh, -2.0, 0.0), _vertex(mesh, -1.0, 0.0))
    app.selection.set({start})
    assert app.key_press(SHIFT_L), app.status_message
    assert app.selection.edges == {start}
    block = _block(mesh)
    ring_start = _edge(mesh, _vertex(mesh, -1.0, -2.0), _vertex(mesh, 0.0, -2.0))  # its ring runs into the block
    app.selection.set({ring_start})
    faces_before = len(mesh.all_face_ids())
    assert app.key_press(I_KEY), app.status_message
    assert set(mesh.all_face_ids()) >= block  # no hidden quad was cut
    assert len(mesh.all_face_ids()) == faces_before + 1  # only the one visible quad below the block


def test_topology_edit_at_a_corner_of_a_hidden_face_is_refused(app):
    mesh = app.scene.mesh
    face = _face_at(mesh, 0.0, 0.0)
    corner = _vertex(mesh, 1.0, 1.0)
    hidden = HiddenSet()
    hidden.hide_faces({face})
    assert touches_hidden(mesh, hidden, [corner])
    assert not touches_hidden(mesh, hidden, [_vertex(mesh, -2.0, -2.0)])
    _face_mode(app, {face})
    assert app.key_press(CTRL_H)
    app.key_press(K1)
    app.selection.set({corner})
    app.viewport.on_selection_changed()
    faces_before = len(mesh.all_face_ids())
    assert not app.key_press(_key("backspace"))  # Dissolve
    assert len(mesh.all_face_ids()) == faces_before
    assert "hidden geometry" in app.status_message


# -- SubD: the derived faces of exactly the hidden control faces ----------------------------------------------


def test_subd_hides_the_derived_faces_and_cage_edges_of_exactly_the_hidden_faces(app):
    from mirai.subdivision import VIEW_CAGE

    mesh = app.scene.mesh
    while app.subdivision.view != VIEW_CAGE:
        assert app.key_press(_key("v"))
    app.update_viewport(0.0)
    provider = app.subdivision.provider
    _level, _vids, derived = provider.derived_elements()
    per_face = len(derived) // len(mesh.all_face_ids())
    block = _block(mesh)
    _face_mode(app, block)
    assert app.key_press(CTRL_H)
    app.update_viewport(0.0)
    assert len(provider.hidden_surface_faces()) == len(block) * per_face
    edge_ids = provider._surface.topology.edge_ids
    assert {edge_ids[i] for i in provider.hidden_control_edges()} == set(mesh.vertex_edges(_vertex(mesh, 0.0, 0.0)))
    rm = app.viewport.surface_render_mesh
    assert rm is not None and rm.hidden_faces == provider.hidden_surface_faces()


# -- groups: Isolate / Invert / Hide on faces ---------------------------------------------------------------------


def test_a_one_face_group_can_be_inverted_and_hidden(app):
    """The interior-vertex workaround could not hide a group without interior vertices ("has no interior to hide")."""
    mesh = app.scene.mesh
    single = _face_at(mesh, 0.0, 0.0)
    mesh.face_regions = FaceRegions((FaceRegion("Brow", frozenset({single})),))
    click = Input("mouse", "LEFT", frozenset({"ctrl", "shift"}))
    pos = _screen(app, 0.5, 0.5)
    for _ in range(2):  # isolate, then invert
        app.pointer_motion(*pos)
        app.pointer_press(click, *pos)
        app.pointer_release("LEFT", *pos)
    assert app._hidden.faces() == {single} and not app._hidden.vertices()
    assert not any(app._hidden.is_hidden_face(mesh, f) for f in _neighbours(mesh, {single}))
    assert "hidden, the rest is visible" in app.status_message


def test_region_isolate_keeps_exactly_the_group(app):
    """Ctrl+Alt+H on the active group: its faces stay, every other face is hidden - also the neighbours whose corners
    all lie on the group (the vertex isolate showed those too)."""
    mesh = app.scene.mesh
    group = {_face_at(mesh, x, y) for x in (-1.0, 0.0, 1.0) for y in (-1.0, 1.0)}  # two rows, a hole between
    _face_mode(app, group)
    assert app.key_press(_key("g", "ctrl")), app.status_message  # new group of the selection
    between = {_face_at(mesh, x, 0.0) for x in (-1.0, 0.0, 1.0)}  # every corner on the group
    assert app.key_press(_key("h", "ctrl", "alt")), app.status_message
    visible = {f for f in mesh.all_face_ids() if not app._hidden.is_hidden_face(mesh, f)}
    assert visible == group and not visible & between
    assert not app._hidden.vertices()
