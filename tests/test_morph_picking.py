"""MODELING_ON_DEFORMED_SURFACES §15 (Manu 2026-11-03): picking and tools on the morph mix.

While a target is dialled in on the edit object, hover, click, Box / Lasso / Paint, the Knife, every
selection / tool overlay and the drag mappings act on the drawn mix `b + Σ wᵢ·dᵢ`; edits still change the
base (rest positions). At 0 % and without targets everything is bit-identical to before; in a pose the
rest cage stays (§15 (b), S5). Headless: the CPU picker (`TraceStore`); the GPU ID-buffer path on the mix
is `tests/test_gl_morph_picking.py`.

Acceptance (§15): DS-AC1 (the picked element is the one drawn under the cursor; rest and mix differ by
more than the pick radius), DS-AC2 (overlays on the drawn cage within 1e-9), DS-AC3 through real picks
(Split, Edge Connect, Loop Insert, Collapse, Extrude, Inset, Bevel, the Knife open / closed /
self-crossing; plain and symmetric), DS-AC6 (one Undo step, Undo / Redo exact), 0 % equivalence.
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import BoneId, Mesh, PointLayerInfo, SelectionMode
from mirai import morph_mix
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_component
from tests.mesh_invariants import assert_layer_invariants
from tests.test_application_delete_dissolve import HEIGHT, WIDTH, _app, _edge, _grid_vertex, _select
from tests import test_layer_topology_ops as ops

V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE
LMB = Input("mouse", "LEFT")
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))
CTRL_Z, CTRL_Y = Input("key", "z", frozenset({"ctrl"})), Input("key", "y", frozenset({"ctrl"}))
ENTER = Input("key", "enter")


# -- helpers --------------------------------------------------------------------------------------------


def _mouth(app, weight: int = 100, scale: float = 1.0):
    """A smooth "mouth open" target on the edit mesh (no fold): the lower rows drop and come forward, the
    upper ones rise - every drawn point lies well over the pick radius from its rest position."""
    mesh = app.scene.mesh
    lid = mesh.add_point_layer(PointLayerInfo("Jaw open"))
    xs = [mesh.vertex_position(v)[0] for v in mesh.all_vertex_ids()]
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    for v in mesh.all_vertex_ids():
        x, y, _ = mesh.vertex_position(v)
        dy = (y - cy) * 0.25 + 0.3
        mesh.set_layer_value(lid, v, (scale * (0.35 + 0.05 * (x - cx)), scale * dy, scale * (0.25 + 0.1 * (x - cx))))
    if weight:
        app.set_morph_weight(weight, lid)
    app.update_viewport(0.0)
    return lid


def _camera(app):
    return app._objects.edit_camera


def _screen(app, p):
    return _camera(app).project_to_screen(p, WIDTH, HEIGHT)


def _drawn(app) -> dict:
    """The definition of what is drawn (`morph_mix.evaluate`), independent of the provider's surface."""
    obj = app.scene.edit_object
    weights = app.morph.provider.object_weights(obj.id)
    return morph_mix.evaluate(obj.mesh, weights) if weights else {v: obj.mesh.vertex_position(v) for v in obj.mesh.all_vertex_ids()}


def _oracle(app) -> Mesh:
    """An independent mesh at the drawn positions (same IDs and topology), for the picker as the oracle."""
    mesh = app.scene.mesh
    state = mesh.export_state()
    state["point_layers"] = None
    drawn = _drawn(app)
    for v, p in drawn.items():
        state["vertices"][int(v)] = list(p)
    return Mesh.from_state(state)


def _edge_mid(points, mesh, e):
    a, b = mesh.edge_vertices(e)
    return tuple(points[a][k] * 0.5 + points[b][k] * 0.5 for k in range(3))


def _face_centre(points, mesh, f):
    corners = mesh.face_vertices(f)
    return tuple(sum(points[v][k] for v in corners) / len(corners) for k in range(3))


def _anchor(points, mesh, element):
    """Where to put the cursor to hit `element` at `points`."""
    from core import EdgeId, FaceId

    if isinstance(element, FaceId):
        return _face_centre(points, mesh, element)
    if isinstance(element, EdgeId):
        return _edge_mid(points, mesh, element)
    return points[element]


def _hover(app, p):
    sx, sy = _screen(app, p)
    app.pointer_motion(sx, sy)
    return app.selection.hovered


def _aim(app, element):
    """A cursor where the drawn `element` is what the picker gets (its anchor, else a sample on its visible part:
    the artist aims at what is visible) - checked against an independent mesh at the drawn positions."""
    from core import EdgeId, FaceId

    mesh, points, oracle = app.scene.mesh, _drawn(app), _oracle(app)
    mode = app.selection.mode
    samples = [_anchor(points, mesh, element)]
    if isinstance(element, EdgeId):
        a, b = mesh.edge_vertices(element)
        samples += [tuple(points[a][k] + t * (points[b][k] - points[a][k]) for k in range(3)) for t in (0.3, 0.7, 0.15, 0.85)]
    elif isinstance(element, FaceId):
        c = _face_centre(points, mesh, element)
        samples += [tuple(c[k] * 0.5 + points[v][k] * 0.5 for k in range(3)) for v in mesh.face_vertices(element)]
    for p in samples:
        sx, sy = _screen(app, p)
        if pick_component(_camera(app), oracle, mode, sx, sy, WIDTH, HEIGHT, occlusion=True) == element:
            return sx, sy
    raise AssertionError(f"{element!r} is not visible on the drawn mix")


def _click(app, element, add: bool = False):
    sx, sy = _aim(app, element)
    app.pointer_motion(sx, sy)
    inp = SHIFT_LMB if add else LMB
    app.pointer_press(inp, sx, sy)
    app.pointer_release("LEFT", sx, sy)


def _rest(app) -> dict:
    mesh = app.scene.mesh
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


# -- DS-AC1: hover and click on the drawn mix -------------------------------------------------------------


@pytest.mark.parametrize("weight", [50, 100])
@pytest.mark.parametrize("mode", [V, E, F], ids=["vertex", "edge", "face"])
def test_hover_hits_the_element_drawn_under_the_cursor(mode, weight):
    app = _app(4)
    _mouth(app, weight, scale=2.0)
    mesh = app.scene.mesh
    app.selection.mode = mode
    drawn, rest = _drawn(app), _rest(app)
    assert app.viewport.cage_mesh is app.morph.provider.surface_mesh
    elements = {V: mesh.all_vertex_ids, E: mesh.all_edge_ids, F: mesh.all_face_ids}[mode]()
    oracle = _oracle(app)
    distinguished = 0
    for element in elements:
        assert _hover(app, _anchor(drawn, mesh, element)) == element
        # at the rest anchor the cursor gets what is drawn there - for most elements no longer the element itself
        x, y = _screen(app, _anchor(rest, mesh, element))
        want = pick_component(_camera(app), oracle, mode, x, y, WIDTH, HEIGHT, occlusion=True)
        got = _hover(app, _anchor(rest, mesh, element))
        assert type(got) is type(want) and got == want
        distinguished += got != element
    assert distinguished >= (len(elements) // 3 if mode is V else 1)


@pytest.mark.parametrize("mode", [V, E, F], ids=["vertex", "edge", "face"])
def test_picks_equal_the_picker_on_the_evaluated_mix_with_occlusion(mode):
    """A grid of cursors over the cube: every hover equals the CPU picker on an independent mesh at the drawn
    positions (occlusion by the drawn mix included); some differ from the rest-shape pick."""
    app = _app()
    _mouth(app, 70, scale=1.4)
    app.selection.mode = mode
    oracle, mesh = _oracle(app), app.scene.mesh
    differ = 0
    for i in range(14):
        for j in range(11):
            x, y = 40 + i * 52, 40 + j * 50
            app.pointer_motion(x, y)
            got = app.selection.hovered
            want = pick_component(_camera(app), oracle, mode, x, y, WIDTH, HEIGHT, occlusion=True)
            assert type(got) is type(want) and got == want, (x, y, got, want)
            at_rest = pick_component(_camera(app), mesh, mode, x, y, WIDTH, HEIGHT, occlusion=True)
            differ += at_rest != want
    assert differ >= 3


def test_an_element_hidden_behind_the_drawn_mix_is_not_picked():
    app = _app()
    _mouth(app, 100, scale=1.4)
    app.selection.mode = V
    oracle, mesh = _oracle(app), app.scene.mesh
    drawn = _drawn(app)
    occluded = [v for v in mesh.all_vertex_ids()
                if pick_component(_camera(app), oracle, V, *_screen(app, drawn[v]), WIDTH, HEIGHT, occlusion=True) != v]
    assert occluded  # the cube's back corners
    for v in occluded:
        assert _hover(app, drawn[v]) != v


def test_hidden_vertices_are_not_picked_on_the_mix():
    app = _app(4)
    _mouth(app, 100)
    mesh = app.scene.mesh
    v = _grid_vertex(app, 2, 2)
    app.selection.mode = V
    drawn = _drawn(app)
    assert _hover(app, drawn[v]) == v
    _select(app, V, {v})
    assert app.key_press(Input("key", "h", frozenset({"ctrl"}))), app.status_message
    assert v in app._hidden.vertices()
    app.update_viewport(0.0)
    assert _hover(app, drawn[v]) != v


def test_click_selects_what_is_drawn_and_edits_change_the_base():
    app = _app(4)
    lid = _mouth(app, 100)
    mesh = app.scene.mesh
    v = _grid_vertex(app, 1, 2)
    app.selection.mode = V
    _click(app, v)
    assert set(app.selection.vertices) == {v}
    offsets = dict(mesh.layer_items(lid))
    rest = mesh.vertex_position(v)
    shown_before = _screen(app, _drawn(app)[v])
    # Move (W): the drawn point follows the pointer; the base moves, the offsets stay (reading (a))
    assert app.key_press(Input("key", "w")), app.status_message
    for _ in range(4):
        app.pointer_motion(shown_before[0], shown_before[1], 10.0, -6.0)
    app.key_release(Input("key", "w"))
    assert dict(mesh.layer_items(lid)) == offsets
    assert mesh.vertex_position(v) != rest
    app.update_viewport(0.0)
    shown_after = _screen(app, _drawn(app)[v])
    assert abs(shown_after[0] - shown_before[0] - 40.0) < 0.5 and abs(shown_after[1] - shown_before[1] + 24.0) < 0.5
    assert app.morph.provider.surface_mesh.vertex_position(v) == _drawn(app)[v]


def test_move_maps_pixels_at_the_drawn_depth():
    """With a target that pushes a point towards the camera, the W drag maps the pixels at the drawn depth: the
    drawn point stays under the pointer. At the rest depth it would run ahead or lag."""
    app = _app(4)
    mesh = app.scene.mesh
    lid = mesh.add_point_layer(PointLayerInfo("Forward"))
    v = _grid_vertex(app, 2, 1)
    eye = _camera(app).screen_to_ray(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT)[1]
    mesh.set_layer_value(lid, v, tuple(-1.5 * c for c in eye))  # towards the eye
    app.set_morph_weight(100, lid)
    app.update_viewport(0.0)
    _select(app, V, {v})
    start = _screen(app, _drawn(app)[v])
    assert app.key_press(Input("key", "w")), app.status_message
    for _ in range(5):
        app.pointer_motion(start[0], start[1], 12.0, 8.0)
    app.key_release(Input("key", "w"))
    app.update_viewport(0.0)
    end = _screen(app, _drawn(app)[v])
    assert math.dist(end, (start[0] + 60.0, start[1] + 40.0)) < 0.5


def test_box_lasso_and_paint_select_the_drawn_elements():
    app = _app(4)
    _mouth(app, 100, scale=2.0)
    mesh = app.scene.mesh
    drawn, rest = _drawn(app), _rest(app)
    app.selection.mode = V
    wanted = {_grid_vertex(app, r, c) for r in (1, 2) for c in (1, 2)}
    pts = [_screen(app, drawn[v]) for v in wanted]
    x0, y0 = min(p[0] for p in pts) - 6, min(p[1] for p in pts) - 6
    x1, y1 = max(p[0] for p in pts) + 6, max(p[1] for p in pts) + 6
    inside = {v for v in mesh.all_vertex_ids() if x0 <= _screen(app, drawn[v])[0] <= x1 and y0 <= _screen(app, drawn[v])[1] <= y1}
    assert app._elements_in_rect((x0, y0, x1, y1), True) == inside
    assert wanted <= inside
    rest_inside = {v for v in mesh.all_vertex_ids() if x0 <= _screen(app, rest[v])[0] <= x1 and y0 <= _screen(app, rest[v])[1] <= y1}
    assert rest_inside != inside
    polygon = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    assert app._elements_in_polygon(polygon, True) == inside
    # paint: the hits along a stroke are the drawn elements under it
    stroke = [_screen(app, drawn[v]) for v in sorted(wanted, key=int)]
    assert {app._pick(x, y) for x, y in stroke} == wanted


# -- 0 % and no target: bit-identical ---------------------------------------------------------------------


def _hover_trace(app, mode):
    app.selection.mode = mode
    out = []
    for i in range(10):
        for j in range(8):
            app.pointer_motion(60 + i * 70, 50 + j * 65)
            out.append((type(app.selection.hovered), app.selection.hovered))
    return out


@pytest.mark.parametrize("mode", [V, E, F], ids=["vertex", "edge", "face"])
def test_zero_percent_and_no_target_pick_exactly_as_before(mode):
    plain = _app(4)
    zero = _app(4)
    lid = _mouth(zero, 0)
    back = _app(4)
    lid_back = _mouth(back, 60)
    back.set_morph_weight(0, lid_back)
    back.update_viewport(0.0)
    for app in (zero, back):
        assert app.viewport.cage_mesh is None and app._query_mesh() is app.scene.mesh
    trace = _hover_trace(plain, mode)
    assert _hover_trace(zero, mode) == trace
    assert _hover_trace(back, mode) == trace
    _select(plain, mode, set())
    for app in (plain, zero, back):
        _select(app, V, {_grid_vertex(app, 1, 1), _grid_vertex(app, 2, 3)})
        app.viewport.on_selection_changed()
        app.update_viewport(0.0)
    assert zero.viewport.point_positions == plain.viewport.point_positions == back.viewport.point_positions
    assert zero._gizmo_pivot() == plain._gizmo_pivot() == back._gizmo_pivot()
    assert lid is not None


def test_zero_percent_under_subd_picks_on_the_rest_cage():
    """With SubD on, the mix is kept at 0 % (SubD reads it, AD-025 §17.1); it equals the rest shape, and picking stays
    on the edit mesh itself (not on the kept surface)."""
    plain, zero = _app(4), _app(4)
    lid = _mouth(zero, 50)
    for app in (plain, zero):
        assert app.subdivision.set_view("cage")
        app.update_viewport(0.0)
    zero.set_morph_weight(0, lid)
    zero.update_viewport(0.0)
    assert zero.morph.provider.surface_mesh is not None  # kept for SubD
    assert zero.viewport.cage_mesh is None and zero._query_mesh() is zero.scene.mesh
    for mode in (V, E, F):
        assert _hover_trace(zero, mode) == _hover_trace(plain, mode)


def test_no_target_keeps_the_cage_source_inert():
    app = _app(4)
    app.update_viewport(0.0)
    assert app.viewport.cage_mesh is None
    assert app.viewport.overlay_mesh() is app.scene.mesh
    assert app._query_mesh() is app.scene.mesh


# -- DS-AC2: overlays on the drawn cage -------------------------------------------------------------------


def _close(a, b, tol=1e-9):
    return max(abs(x - y) for x, y in zip(a, b)) <= tol


def test_selection_hover_and_highlights_sit_on_the_mix():
    app = _app(4)
    _mouth(app, 100)
    mesh = app.scene.mesh
    drawn = _drawn(app)
    # vertices
    vs = {_grid_vertex(app, 1, 1), _grid_vertex(app, 3, 2)}
    _select(app, V, vs)
    app.viewport.on_selection_changed()
    app.update_viewport(0.0)
    points = [p for layer in app.viewport.point_positions.values() for p in layer]
    assert points and all(any(_close(p, drawn[v]) for v in mesh.all_vertex_ids()) for p in points)
    assert all(any(_close(p, drawn[v]) for p in points) for v in vs)
    # edges: hover and selection lines at the drawn ends
    e = _edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2))
    _select(app, E, {e})
    _hover(app, _edge_mid(drawn, mesh, _edge(mesh, _grid_vertex(app, 2, 2), _grid_vertex(app, 2, 3))))
    app.update_viewport(0.0)
    segments = [s for layer in app.viewport.line_layers.values() for s in layer]
    assert len(segments) >= 2
    ends = [drawn[v] for v in mesh.all_vertex_ids()]
    assert all(any(_close(p, q) for q in ends) for s in segments for p in s)
    # faces: the highlight triangles lie on the drawn face
    f = next(iter(mesh.vertex_edges(_grid_vertex(app, 2, 2))))
    face = mesh.edge_faces(f)[0]
    _select(app, F, {face})
    app.viewport.on_selection_changed()
    app.update_viewport(0.0)
    tris = [t for layer in app.viewport.face_layers.values() for t in layer]
    corners = [drawn[v] for v in mesh.face_vertices(face)]
    assert tris and all(any(_close(p, q) for q in corners) for t in tris for p in t)


def test_wire_gizmo_pivot_and_symmetry_markers_follow_the_mix():
    from mirai import object_space
    from viewport import edge_segments

    app = _app(4)
    app.gizmo_enabled = True
    _mouth(app, 100)
    mesh = app.scene.mesh
    drawn = _drawn(app)
    app.viewport.show_edges = True
    app.viewport.on_selection_changed()
    app.update_viewport(0.0)
    assert app.viewport.edge_segments == edge_segments(app.morph.provider.surface_mesh)
    vs = {_grid_vertex(app, 1, 1), _grid_vertex(app, 2, 3)}
    _select(app, V, vs)
    app.viewport.on_selection_changed()
    app.update_viewport(0.0)
    centre = tuple(sum(drawn[v][k] for v in vs) / len(vs) for k in range(3))
    assert _close(app._gizmo_pivot(), object_space.to_world(app.scene.edit_object, centre))
    # a weight step moves the gizmo with the drawn selection (the cage revision is part of its cache key)
    app.set_morph_weight(40)
    app.update_viewport(0.0)
    drawn = _drawn(app)
    centre = tuple(sum(drawn[v][k] for v in vs) / len(vs) for k in range(3))
    assert _close(app._gizmo_pivot(), object_space.to_world(app.scene.edit_object, centre))


def test_soft_bands_and_mask_points_sit_on_the_mix():
    from mirai.mask_display import GLMaskOverlay
    from mirai.soft_selection.gl_bands import GLSoftBandOverlay

    for overlay_type in (GLSoftBandOverlay, GLMaskOverlay):
        assert overlay_type.follows_cage is True
    app = _app(4)
    _mouth(app, 100)
    mesh = app.scene.mesh

    class Probe:
        follows_cage = True
        dirty = False

        def __init__(self):
            self.mesh = None

        def sync(self, mesh, selection):
            self.mesh = mesh

        def draw(self, uniforms):
            pass

    probe, plain = Probe(), Probe()
    plain.follows_cage = False
    app.viewport.add_overlay(probe)
    app.viewport.add_overlay(plain)
    app.update_viewport(0.0)
    assert probe.mesh is app.morph.provider.surface_mesh and plain.mesh is mesh
    app.set_morph_weight(0)
    app.update_viewport(0.0)
    assert probe.mesh is mesh


def test_symmetry_markers_sit_on_the_mix():
    from mirai.symmetry_display import SymmetryDisplay

    app = ops.make_app("subd_cube")
    mesh = app.scene.mesh
    lid = _mouth(app, 100)
    sink_calls = {}

    class Sink:
        def set_segments(self, segments):
            pass

        def set_markers(self, seam, unpaired, ambiguous):
            sink_calls["seam"] = seam

        def set_preview(self, *args):
            pass

        def draw(self, uniforms):
            pass

    display = SymmetryDisplay(Sink(), cage=lambda: app.viewport.cage_mesh)
    app.update_viewport(0.0)
    display.sync(mesh, app.selection)
    drawn = _drawn(app)
    seam = sink_calls["seam"]
    assert seam and all(any(_close(p, drawn[v]) for v in mesh.all_vertex_ids()) for p in seam)
    assert any(not any(_close(p, mesh.vertex_position(v)) for v in mesh.all_vertex_ids()) for p in seam)
    assert lid is not None


# -- (b): in a pose the rest cage stays -------------------------------------------------------------------


def test_posed_keeps_picking_on_the_rest_cage():
    from tests.test_skin_stage import _bind, _bone_pose, _rig

    app = _app(4)
    rng = random.Random(4)
    mesh = app.scene.mesh
    _bind(mesh, rng)
    app.scene.rig = _rig(mesh)
    _mouth(app, 100)
    assert app.viewport.cage_mesh is not None
    app.skin.provider.set_pose({BoneId(1): _bone_pose(rng)})
    app.update_viewport(0.0)
    assert app.skin.provider.surface_mesh is not None
    assert app.viewport.cage_mesh is None and app._query_mesh() is mesh
    app.selection.mode = V
    v = _grid_vertex(app, 2, 2)
    assert _hover(app, mesh.vertex_position(v)) == v  # the rest cage, as before (AD-028 §7.1)
    app.skin.provider.set_pose({})
    app.update_viewport(0.0)
    assert app.viewport.cage_mesh is app.morph.provider.surface_mesh


# -- DS-AC3 / DS-AC6: topology operations through real picks on the mix ----------------------------------


def _dial(app, lids, weights=(15, 10)):
    """Dial in two of the layered fixture's three targets (small enough that the mesh does not fold: the
    fixture's offsets reach 1.0, the subd cube is 0.75 wide)."""
    app.set_morph_weight(weights[0], lids[0])
    app.set_morph_weight(weights[1], lids[2])
    app.update_viewport(0.0)


def _select_by_clicks(app, mode, wanted) -> None:
    app.selection.mode = mode
    app.selection.clear()
    for i, element in enumerate(sorted(wanted, key=int)):
        _click(app, element, add=i > 0)
    assert set(_ids(app.selection, mode)) == set(wanted), app.status_message


def _ids(selection, mode):
    return {V: selection.vertices, E: selection.edges, F: selection.faces}[mode]


def _assert_mix_is_definition(app):
    app.update_viewport(0.0)
    surface = app.morph.provider.surface_mesh
    for v, p in _drawn(app).items():
        assert surface.vertex_position(v) == p, v
    assert sorted(surface.all_face_ids()) == sorted(app.scene.mesh.all_face_ids())


@pytest.mark.parametrize("symmetric", [False, True], ids=["plain", "symmetric"])
@pytest.mark.parametrize("key", list(ops.RULE_FIXTURES), ids=str)
def test_topology_operations_through_picks_on_the_mix(key, symmetric):
    plain, sym, rule = ops.RULE_FIXTURES[key]
    app = ops.make_app("subd_cube") if symmetric else _app(3)
    command = (sym if symmetric else plain)(app)
    mode = app.selection.mode
    wanted = set(_ids(app.selection, mode))
    mesh = app.scene.mesh
    lids = ops.add_layers(mesh, seed=sum(map(ord, str(key))))
    _dial(app, lids, (6, 4) if symmetric else (15, 10))
    assert app.viewport.cage_mesh is not None
    _select_by_clicks(app, mode, wanted)
    before = mesh.export_state()
    ref = Mesh.from_state(before)
    info: dict = {}
    ops._run(app, command, info)
    assert rule(ref, mesh, info) >= 1
    if symmetric:
        assert ops._check_mirror(ref, mesh) >= 1
    assert_layer_invariants(mesh)
    _assert_mix_is_definition(app)
    ops._assert_undo_redo_exact(app, before)
    _assert_mix_is_definition(app)


def _knife_clicks(app, points) -> None:
    for p in points:
        sx, sy = _screen(app, p)
        app.pointer_motion(sx, sy)
        app.pointer_press(LMB, sx, sy)
        assert app.pointer_release("LEFT", sx, sy), app.status_message


def _knife_face(app):
    """A grid face near the middle and its drawn corners (bilinear interpolation inside it)."""
    mesh = app.scene.mesh
    v = _grid_vertex(app, 1, 1)
    face = next(f for f in mesh.all_face_ids() if v in mesh.face_vertices(f)
                and all(mesh.vertex_position(c)[0] >= 1.0 and mesh.vertex_position(c)[1] >= 1.0 for c in mesh.face_vertices(f)))
    drawn = _drawn(app)
    pa = [drawn[c] for c in mesh.face_vertices(face)]

    def inside(u, w):
        return tuple(pa[0][k] * (1 - u) * (1 - w) + pa[1][k] * u * (1 - w) + pa[2][k] * u * w + pa[3][k] * (1 - u) * w
                     for k in range(3))

    def on_edge(e, t):
        a, b = mesh.edge_vertices(e)
        return tuple(drawn[a][k] + t * (drawn[b][k] - drawn[a][k]) for k in range(3))

    return face, inside, on_edge


def _assert_preview_on_the_mix(app, clicks) -> None:
    """DS-AC2 for the Knife: every placed point is drawn under the click that placed it (on the drawn mix) and
    lies there: an edge point on the drawn edge, an interior point on the drawn face."""
    from mirai.topology.knife_preview import target_position

    tool = app._knife.tool
    cage = app.viewport.cage_mesh
    assert cage is not None
    data = app._knife.render_data()
    targets = [target_position(cage, p) for p in tool.points if p["kind"] in ("edge", "face", "vertex")]
    assert data.placed_points and all(any(math.dist(p, q) <= 1e-12 for q in targets) for p in data.placed_points)
    screens = [_screen(app, c) for c in clicks]
    for p in tool.points:
        if p["kind"] in ("edge", "face") and not p.get("crossing"):
            s = _screen(app, target_position(cage, p))
            # an interior point is the hit under the cursor; an edge point the drawn edge's point nearest to it
            assert min(math.dist(s, c) for c in screens) < (1e-6 if p["kind"] == "face" else 9.0), (p, s)


def _assert_points_where_aimed(app, ref, aimed) -> None:
    """DS-AC3: every new vertex created for an aimed interior point is drawn exactly where it was aimed."""
    mesh = app.scene.mesh
    drawn = _drawn(app)
    new = [v for v in mesh.all_vertex_ids() if not ref.is_valid_vertex(v)]
    for p in aimed:
        best = min(math.dist(drawn[v], p) for v in new)
        assert best <= 1e-9, (p, best)


@pytest.mark.parametrize("shape", ["open", "closed", "self_crossing"])
def test_knife_on_the_mix_cuts_where_aimed(shape):
    from tests.test_layer_knife import check_values

    app = _app(4)
    mesh = app.scene.mesh
    lids = ops.add_layers(mesh, seed=7)
    _dial(app, lids)
    face, inside, on_edge = _knife_face(app)
    edges = mesh.face_edges(face)
    drawn_corner = _drawn(app).__getitem__
    before = mesh.export_state()
    ref = Mesh.from_state(before)
    app.selection.clear()
    assert app.key_press(Input("key", "c")), app.status_message
    assert app.knife_active
    if shape == "open":
        clicks = [on_edge(edges[0], 0.35), inside(0.45, 0.4), inside(0.6, 0.65), on_edge(edges[2], 0.4)]
    elif shape == "closed":
        a, b, c = inside(0.3, 0.3), inside(0.7, 0.35), inside(0.5, 0.75)
        clicks = [a, b, c, a]
    else:  # the third stretch crosses the first inside the face (as `test_layer_knife`'s self-crossing run)
        corners = mesh.face_vertices(face)
        clicks = [drawn_corner(corners[0]), inside(0.8, 0.4), inside(0.5, 0.8), inside(0.5, 0.18),
                  drawn_corner(corners[1])]
    _knife_clicks(app, clicks)
    tool = app._knife.tool
    _assert_preview_on_the_mix(app, clicks)
    aimed = [tuple(p["position"]) for p in tool.path if p.get("kind") == "face"]
    assert aimed
    rest_path = [dict(p) for p in tool._rest_path(tool.path)]
    history = len(app.history)
    assert app.key_press(ENTER), app.status_message
    assert len(app.history) == history + 1, app.status_message
    counts = check_values(ref, mesh, rest_path)
    assert counts["face"] >= (2 if shape != "self_crossing" else 3)
    _assert_points_where_aimed(app, ref, aimed)
    if shape == "self_crossing":
        assert counts["other"] >= 1  # the crossing point
    assert_layer_invariants(mesh)
    _assert_mix_is_definition(app)
    ops._assert_undo_redo_exact(app, before)
    _assert_mix_is_definition(app)


def test_symmetric_knife_on_the_mix_cuts_where_aimed_and_mirrors():
    app = ops._knife_app(True)
    mesh = app.scene.mesh
    lids = ops.add_layers(mesh, 21)
    _dial(app, lids, (8, 5))
    drawn = _drawn(app)
    face = max(mesh.all_face_ids(), key=lambda f: min(drawn[v][0] for v in mesh.face_vertices(f)))  # +X
    edges = mesh.face_edges(face)
    pa = [drawn[v] for v in mesh.face_vertices(face)]

    def inside(u, w):
        return tuple(pa[0][k] * (1 - u) * (1 - w) + pa[1][k] * u * (1 - w) + pa[2][k] * u * w + pa[3][k] * (1 - u) * w
                     for k in range(3))

    def on_edge(e, t):
        a, b = mesh.edge_vertices(e)
        return tuple(drawn[a][k] + t * (drawn[b][k] - drawn[a][k]) for k in range(3))

    before = mesh.export_state()
    ref = Mesh.from_state(before)
    app.selection.clear()
    assert app.key_press(Input("key", "c")), app.status_message
    _knife_clicks(app, [on_edge(edges[0], 0.35), inside(0.45, 0.4), inside(0.6, 0.65), on_edge(edges[2], 0.4)])
    tool = app._knife.tool
    aimed = [tuple(p["position"]) for p in tool.path if p.get("kind") == "face"]
    assert len(aimed) == 2 and all(p["face_id"] == face for p in tool.path if p.get("kind") == "face")
    rest_path = [dict(p) for p in tool._rest_path(tool.path)]
    assert app.key_press(ENTER), app.status_message
    ops.knife_rule(ref, mesh, {"path": rest_path, "symmetric": True})
    _assert_points_where_aimed(app, ref, aimed)
    assert ops._check_mirror(ref, mesh) >= 4
    assert_layer_invariants(mesh)
    _assert_mix_is_definition(app)
    ops._assert_undo_redo_exact(app, before)
