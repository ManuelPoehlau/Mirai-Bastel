"""MODELING_ON_DEFORMED_SURFACES §16 (Manu 2026-11-17): picking on the posed surface, for setting weights.

While the rig is posed and the edit mesh is bound, hover, click, Box / Lasso / Paint, the selection / hover overlays,
the wire, the Soft bands and the gizmo pivot act on the drawn, posed surface (the skin stage's, which includes a morph
mix underneath). Position and topology edits stay refused in a pose (AD-028 §7.1); weight commands work on what was
picked. Without a pose everything is as before. Headless: the CPU picker (`TraceStore`). Part A: the n x n grid with
a random bind (with and without a morph target); part B: the Gollum rigging scene with the jaw open, the mouth corner and
the inside of the mouth (`scenes/Gollum_Head_rigging_test.mirai.json`).
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import BoneId, Mesh, SelectionMode
from mirai import skinning
from mirai.interaction.input import Input
from mirai.skinning import BonePose
from mirai.viewport.picking import pick_component
from tests.interaction_trace import HEIGHT, OVERLAYS, WIDTH, Driver, _frame, key
from tests.mesh_invariants import assert_layer_invariants
from tests.test_application_delete_dissolve import _app, _grid_vertex, _select
from tests.test_morph_picking import _anchor, _close, _edge_mid, _mouth
from tests.test_skin_stage import _bind, _bone_pose, _rig

V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE
LMB = Input("mouse", "LEFT")
SCENE = Path(__file__).resolve().parents[1] / "scenes" / "Gollum_Head_rigging_test.mirai.json"


# -- helpers ---------------------------------------------------------------------------------------------


def _camera(app):
    return app._objects.edit_camera


def _screen(app, p):
    return _camera(app).project_to_screen(p, WIDTH, HEIGHT)


def _drawn(app) -> dict:
    """The definition of what is drawn (`skinning.evaluate` of the mix or the rest), independent of the stage."""
    from mirai import morph_mix

    obj = app.scene.edit_object
    weights = app.morph.provider.object_weights(obj.id)
    mix = morph_mix.evaluate(obj.mesh, weights) if weights else None
    return skinning.evaluate(obj.mesh, mix, app.scene.rig, app.skin.provider.pose, skinning.placement_of(obj))


def _rest(app) -> dict:
    mesh = app.scene.mesh
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


def _oracle(app) -> Mesh:
    """An independent mesh at the drawn positions (same IDs and topology), for the picker as the oracle."""
    mesh = app.scene.mesh
    state = mesh.export_state()
    state["point_layers"] = None
    for v, p in _drawn(app).items():
        state["vertices"][int(v)] = list(p)
    return Mesh.from_state(state)


def _hover(app, p):
    sx, sy = _screen(app, p)
    app.pointer_motion(sx, sy)
    return app.selection.hovered


def _posed_grid(n: int = 4, seed: int = 4, morph: int = 0):
    """The n x n grid, bound with random weights, a three-bone rig, a pose that moves points well over the pick radius
    and (optionally) a smooth morph target dialled in underneath."""
    app = _app(n)
    rng = random.Random(seed)
    mesh = app.scene.mesh
    _bind(mesh, rng)
    app.scene.rig = _rig(mesh)
    if morph:
        _mouth(app, morph, scale=0.6)
    app._skeleton.set_pose({BoneId(1): _bone_pose(rng)})
    app.update_viewport(0.0)
    assert app.skin.provider.surface_mesh is not None
    return app


def _set_pose(app, pose) -> None:
    app._skeleton.set_pose(pose)
    app.update_viewport(0.0)


# -- DS-AC1 for the pose: hover and click on the posed surface --------------------------------------------


@pytest.mark.parametrize("morph", [0, 60], ids=["no-morph", "morph-60"])
@pytest.mark.parametrize("mode", [V, E, F], ids=["vertex", "edge", "face"])
def test_hover_hits_the_element_drawn_under_the_cursor_in_a_pose(mode, morph):
    app = _posed_grid(4, morph=morph)
    mesh = app.scene.mesh
    app.selection.mode = mode
    drawn, rest = _drawn(app), _rest(app)
    assert app.viewport.cage_mesh is app.skin.provider.surface_mesh
    assert max(math.dist(drawn[v], rest[v]) for v in drawn) > 0.3  # the pose really moves points
    elements = {V: mesh.all_vertex_ids, E: mesh.all_edge_ids, F: mesh.all_face_ids}[mode]()
    oracle = _oracle(app)
    distinguished = 0
    for element in elements:
        x, y = _screen(app, _anchor(drawn, mesh, element))
        want = pick_component(_camera(app), oracle, mode, x, y, WIDTH, HEIGHT, occlusion=True)
        got = _hover(app, _anchor(drawn, mesh, element))
        assert type(got) is type(want) and got == want
        # at the rest anchor the cursor gets what is drawn there, not the rest element
        x, y = _screen(app, _anchor(rest, mesh, element))
        want = pick_component(_camera(app), oracle, mode, x, y, WIDTH, HEIGHT, occlusion=True)
        got = _hover(app, _anchor(rest, mesh, element))
        assert type(got) is type(want) and got == want
        distinguished += got != element
    assert distinguished >= 1


@pytest.mark.parametrize("mode", [V, E, F], ids=["vertex", "edge", "face"])
def test_a_cursor_sweep_equals_the_picker_on_the_posed_surface_with_occlusion(mode):
    app = _posed_grid(4, morph=40)
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


def test_click_selects_what_is_drawn_and_nothing_is_written():
    app = _posed_grid(4)
    mesh = app.scene.mesh
    state = mesh.export_state()
    app.selection.mode = V
    drawn, rest = _drawn(app), _rest(app)
    v = max(mesh.all_vertex_ids(), key=lambda w: math.dist(drawn[w], rest[w]))
    sx, sy = _screen(app, drawn[v])
    app.pointer_motion(sx, sy)
    app.pointer_press(LMB, sx, sy)
    app.pointer_release("LEFT", sx, sy)
    assert set(app.selection.vertices) == {v}
    assert mesh.export_state() == state  # a pick writes nothing (the cage is a read-only view)


def test_box_lasso_and_paint_select_the_drawn_elements_in_a_pose():
    app = _posed_grid(4)
    mesh = app.scene.mesh
    drawn, rest = _drawn(app), _rest(app)
    app.selection.mode = V
    oracle = _oracle(app)
    visible = [v for v in mesh.all_vertex_ids()
               if pick_component(_camera(app), oracle, V, *_screen(app, drawn[v]), WIDTH, HEIGHT, occlusion=True) == v]
    wanted = set(sorted(visible, key=lambda w: -math.dist(drawn[w], rest[w]))[:4])
    pts = [_screen(app, drawn[v]) for v in wanted]
    x0, y0 = min(p[0] for p in pts) - 4, min(p[1] for p in pts) - 4
    x1, y1 = max(p[0] for p in pts) + 4, max(p[1] for p in pts) + 4

    def at(points):
        return {v for v in mesh.all_vertex_ids()
                if x0 <= _screen(app, points[v])[0] <= x1 and y0 <= _screen(app, points[v])[1] <= y1}

    inside = {v for v in at(drawn) if v in set(visible)}
    assert wanted <= app._elements_in_rect((x0, y0, x1, y1), True) and app._elements_in_rect((x0, y0, x1, y1), True) <= at(drawn)
    assert at(rest) != at(drawn)
    polygon = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    assert app._elements_in_polygon(polygon, True) == app._elements_in_rect((x0, y0, x1, y1), True)
    assert inside <= app._elements_in_rect((x0, y0, x1, y1), True)
    stroke = [_screen(app, drawn[v]) for v in sorted(wanted, key=int)]
    assert {app._pick(x, y) for x, y in stroke} == wanted


# -- DS-AC2 for the pose: overlays on the posed surface ---------------------------------------------------


def test_selection_hover_wire_and_gizmo_sit_on_the_posed_surface_and_follow_the_pose():
    from mirai import object_space
    from viewport import edge_segments

    app = _posed_grid(4)
    app.gizmo_enabled = True
    mesh = app.scene.mesh
    drawn = _drawn(app)
    app.viewport.show_edges = True
    vs = {_grid_vertex(app, 1, 1), _grid_vertex(app, 3, 2)}
    _select(app, V, vs)
    app.viewport.on_selection_changed()
    app.update_viewport(0.0)
    points = [p for layer in app.viewport.point_positions.values() for p in layer]
    assert all(any(_close(p, drawn[v]) for p in points) for v in vs)
    assert all(any(_close(p, drawn[v]) for v in mesh.all_vertex_ids()) for p in points)
    assert app.viewport.edge_segments == edge_segments(app.skin.provider.surface_mesh)
    centre = tuple(sum(drawn[v][k] for v in vs) / len(vs) for k in range(3))
    assert _close(app._gizmo_pivot(), object_space.to_world(app.scene.edit_object, centre))
    # hover and highlights: the lines of a hovered edge and a selected face lie on the drawn corners
    edge = mesh.vertex_edges(_grid_vertex(app, 2, 2))[0]
    app.selection.mode = E
    _hover(app, _edge_mid(drawn, mesh, edge))
    app.update_viewport(0.0)
    segments = [s for layer in app.viewport.line_layers.values() for s in layer]
    assert segments and all(any(_close(p, q) for q in drawn.values()) for s in segments for p in s)
    face = mesh.edge_faces(edge)[0]
    _select(app, F, {face})
    app.viewport.on_selection_changed()
    app.update_viewport(0.0)
    corners = [drawn[v] for v in mesh.face_vertices(face)]
    tris = [t for layer in app.viewport.face_layers.values() for t in layer]
    assert tris and all(any(_close(p, q) for q in corners) for t in tris for p in t)
    # another pose step moves the overlays and the gizmo with it, without a frame in between for the pick
    _select(app, V, vs)
    app.viewport.on_selection_changed()
    _set_pose(app, {BoneId(1): _bone_pose(random.Random(11))})
    drawn = _drawn(app)
    points = [p for layer in app.viewport.point_positions.values() for p in layer]
    assert all(any(_close(p, drawn[v]) for p in points) for v in vs)
    centre = tuple(sum(drawn[v][k] for v in vs) / len(vs) for k in range(3))
    assert _close(app._gizmo_pivot(), object_space.to_world(app.scene.edit_object, centre))


def test_extra_overlays_that_follow_the_cage_get_the_posed_surface():
    """Soft bands and mask points are `follows_cage` overlays: they sit where the pose draws the points."""
    from mirai.mask_display import GLMaskOverlay
    from mirai.soft_selection.gl_bands import GLSoftBandOverlay

    assert GLSoftBandOverlay.follows_cage is True and GLMaskOverlay.follows_cage is True

    class Probe:
        follows_cage = True
        dirty = False

        def __init__(self, follows=True):
            self.follows_cage, self.mesh = follows, None

        def sync(self, mesh, selection):
            self.mesh = mesh

        def draw(self, uniforms):
            pass

    app = _posed_grid(4)
    probe, plain = Probe(), Probe(False)
    app.viewport.add_overlay(probe)
    app.viewport.add_overlay(plain)
    app.update_viewport(0.0)
    assert probe.mesh is app.skin.provider.surface_mesh and plain.mesh is app.scene.mesh
    _set_pose(app, {})
    assert probe.mesh is app.scene.mesh


# -- weights work on what was picked; position and topology stay refused ---------------------------------


def _jaw_pose_scene():
    """The Gollum rigging scene in the scenario driver, the camera in front of the face."""
    d = Driver("cube")
    app = d.app
    app.load_scene("file", scene_path=SCENE, **OVERLAYS)
    app.set_viewport_size(WIDTH, HEIGHT)
    _frame(app)
    app.camera.set_view(0.0, 0.1)
    app.update_viewport(0.0)
    return d


def _open_jaw(app, degrees: float = 30.0) -> None:
    """Bone 2 (the jaw: it holds the lower face) turned about its X axis; positive opens the mouth."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    _set_pose(app, {BoneId(1): BonePose(rotation=((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c)))})


needs_scene = pytest.mark.skipif(not SCENE.exists(), reason="scenes/Gollum_Head_rigging_test.mirai.json is not in this checkout")


@needs_scene
def test_position_and_topology_edits_stay_refused_in_a_pose_after_a_pick_on_the_posed_surface():
    d = _jaw_pose_scene()
    app = d.app
    mesh = app.scene.mesh
    _open_jaw(app)
    state = mesh.export_state()
    history = len(app.history)
    app.selection.mode = V
    v = next(w for w in mesh.all_vertex_ids() if _close(_rest(app)[w], (0.116, 0.224, 0.315), 1e-3))
    _hover(app, _drawn(app)[v])
    assert app.selection.hovered == v
    app.pointer_press(LMB, *_screen(app, _drawn(app)[v]))
    app.pointer_release("LEFT", *_screen(app, _drawn(app)[v]))
    assert set(app.selection.vertices) == {v}
    for letter in ("w", "e", "r", "i"):
        d.key_down(key(letter))
        d.nudge(30, 10)
        d.key_up(letter)
        app.update_viewport(0.0)
        assert mesh.export_state() == state and len(app.history) == history, letter
        assert "posed" in app.status_message, (letter, app.status_message)  # "<operation>: the mesh is posed (6 = rest pose)"


@needs_scene
def test_set_weight_on_a_selection_made_in_the_pose_and_the_next_pick_follows_the_new_surface():
    d = _jaw_pose_scene()
    app = d.app
    mesh = app.scene.mesh
    _open_jaw(app)
    app.selection.mode = V
    corner = next(w for w in mesh.all_vertex_ids() if _close(_rest(app)[w], (0.116, 0.224, 0.315), 1e-3))
    sx, sy = _screen(app, _drawn(app)[corner])
    app.pointer_motion(sx, sy)
    app.pointer_press(LMB, sx, sy)
    app.pointer_release("LEFT", sx, sy)
    assert set(app.selection.vertices) == {corner}
    app._skeleton.current = BoneId(1)
    before = dict(mesh.layer_items(skinning.skin_layer(mesh)))[corner]
    d.key_down(key("8"))
    d.nudge(60, 0)
    d.key_up("8")
    after = dict(mesh.layer_items(skinning.skin_layer(mesh)))[corner]
    assert after != before, app.status_message
    assert_layer_invariants(mesh)
    # no frame in between: the pick right after the weight step reads the new drawn position
    drawn = _drawn(app)
    assert drawn[corner] != _rest(app)[corner]
    assert _close(app.viewport.sync_cage().vertex_position(corner), drawn[corner])
    app.gizmo_enabled = False  # the gizmo handle at the selected point's pivot would win the hover (E3)
    assert _hover(app, drawn[corner]) == corner


# -- without a pose everything is as before -------------------------------------------------------------


def _hover_trace(app, mode):
    app.selection.mode = mode
    out = []
    for i in range(10):
        for j in range(8):
            app.pointer_motion(60 + i * 70, 50 + j * 65)
            out.append((type(app.selection.hovered), app.selection.hovered))
    return out


@pytest.mark.parametrize("mode", [V, E, F], ids=["vertex", "edge", "face"])
def test_without_a_pose_picking_is_the_rest_cage_and_back_from_a_pose_it_is_exact(mode):
    plain = _app(4)
    rng = random.Random(4)
    _bind(plain.scene.mesh, rng)
    plain.scene.rig = _rig(plain.scene.mesh)
    plain.update_viewport(0.0)
    assert plain.viewport.cage_mesh is None and plain._query_mesh() is plain.scene.mesh
    reference = _hover_trace(plain, mode)
    posed = _posed_grid(4)
    assert posed.viewport.cage_mesh is not None
    assert _hover_trace(posed, mode) != _hover_trace(plain, mode)
    _set_pose(posed, {})  # 6 = rest
    assert posed.viewport.cage_mesh is None and posed._query_mesh() is posed.scene.mesh
    assert _hover_trace(posed, mode) == reference


def test_an_unbound_mesh_in_a_pose_keeps_the_rest_cage():
    app = _app(4)
    app.scene.rig = _rig(app.scene.mesh)  # a rig, but no weights layer: nothing is posed on the mesh
    _set_pose(app, {BoneId(1): _bone_pose(random.Random(4))})
    assert app.skin.provider.surface_mesh is None
    assert app.viewport.cage_mesh is None and app._query_mesh() is app.scene.mesh


def test_the_cage_under_subd_is_the_posed_cage_not_the_subd_surface():
    app = _posed_grid(4)
    assert app.subdivision.set_view("cage")
    app.update_viewport(0.0)
    cage = app.viewport.cage_mesh
    assert cage is app.skin.provider.surface_mesh
    drawn = _drawn(app)
    mesh = app.scene.mesh
    app.selection.mode = V
    oracle = _oracle(app)
    for v in mesh.all_vertex_ids():
        want = pick_component(_camera(app), oracle, V, *_screen(app, drawn[v]), WIDTH, HEIGHT, occlusion=True)
        assert _hover(app, drawn[v]) == want


# -- part B: the Gollum scene, jaw open: mouth corner and inside of the mouth ----------------------------


def _mouth_sets(app):
    """(corner, interior) vertex sets of the open jaw: the corner = the jaw holds the point partly and it lies at the
    side of the lips; the interior = visible points behind the lip plane between the lips."""
    mesh = app.scene.mesh
    rest, drawn = _rest(app), _drawn(app)
    lid = skinning.skin_layer(mesh)
    weights = dict(mesh.layer_items(lid))
    oracle = _oracle(app)

    def visible(v):
        return pick_component(_camera(app), oracle, V, *_screen(app, drawn[v]), WIDTH, HEIGHT, occlusion=True) == v

    corner = {v for v, value in weights.items()
              if any(k == BoneId(1) and 0.05 < w < 0.95 for k, w in value)
              and 0.10 < abs(rest[v][0]) < 0.14 and 0.19 < rest[v][1] < 0.27 and rest[v][2] > 0.29 and visible(v)}
    interior = {v for v in mesh.all_vertex_ids()
                if abs(drawn[v][0]) < 0.09 and 0.0 < rest[v][2] < 0.30 and 0.05 < rest[v][1] < 0.21
                and -0.05 < drawn[v][1] < 0.2 and visible(v)}
    return corner, interior


@needs_scene
@pytest.mark.parametrize("degrees", [18.0, 30.0], ids=["18deg", "30deg"])
def test_gollum_open_jaw_hover_hits_mouth_corner_and_inside_of_the_mouth(degrees):
    d = _jaw_pose_scene()
    app = d.app
    mesh = app.scene.mesh
    state = mesh.export_state()
    _open_jaw(app, degrees)
    app.selection.mode = V
    corner, interior = _mouth_sets(app)
    assert len(corner) >= 4 and len(interior) >= 10, (len(corner), len(interior))
    drawn, rest = _drawn(app), _rest(app)
    assert app.viewport.cage_mesh is app.skin.provider.surface_mesh
    missed_at_rest = 0
    for v in sorted(corner | interior, key=int):
        assert _hover(app, drawn[v]) == v  # the drawn element is what the cursor gets
        if math.dist(_screen(app, drawn[v]), _screen(app, rest[v])) > 8.0:
            missed_at_rest += _hover(app, rest[v]) != v
    assert missed_at_rest >= 8  # the rest anchors no longer hit them: the bug that hid the mouth corner and the inside
    assert mesh.export_state() == state


@needs_scene
def test_gollum_open_jaw_edge_face_box_lasso_and_paint_on_the_drawn_surface():
    d = _jaw_pose_scene()
    app = d.app
    mesh = app.scene.mesh
    _open_jaw(app, 30.0)
    corner, interior = _mouth_sets(app)
    drawn, rest = _drawn(app), _rest(app)
    oracle = _oracle(app)
    # edges and faces of the mouth: every cursor at a drawn anchor gets what the picker gets on the drawn mesh
    for mode, elements in ((E, [e for v in sorted(corner | interior, key=int)[:12] for e in mesh.vertex_edges(v)]),
                           (F, [f for v in sorted(corner | interior, key=int)[:12] for e in mesh.vertex_edges(v) for f in mesh.edge_faces(e)])):
        app.selection.mode = mode
        for element in elements:
            x, y = _screen(app, _anchor(drawn, mesh, element))
            want = pick_component(_camera(app), oracle, mode, x, y, WIDTH, HEIGHT, occlusion=True)
            got = _hover(app, _anchor(drawn, mesh, element))
            assert type(got) is type(want) and got == want
    # box / lasso / paint over the inside of the mouth
    app.selection.mode = V
    pts = [_screen(app, drawn[v]) for v in interior]
    x0, y0 = min(p[0] for p in pts) - 3, min(p[1] for p in pts) - 3
    x1, y1 = max(p[0] for p in pts) + 3, max(p[1] for p in pts) + 3
    box = app._elements_in_rect((x0, y0, x1, y1), True)
    assert interior <= box
    assert box == app._elements_in_polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], True)
    rest_box = {v for v in mesh.all_vertex_ids() if x0 <= _screen(app, rest[v])[0] <= x1 and y0 <= _screen(app, rest[v])[1] <= y1}
    assert not interior <= rest_box  # on the rest cage the same box would miss part of the inside
    stroke = [_screen(app, drawn[v]) for v in sorted(corner, key=int)]
    assert {app._pick(x, y) for x, y in stroke} == corner


@needs_scene
def test_gollum_open_jaw_overlays_and_soft_bands_sit_on_the_drawn_surface():
    d = _jaw_pose_scene()
    app = d.app
    mesh = app.scene.mesh
    _open_jaw(app, 30.0)
    corner, _ = _mouth_sets(app)
    drawn = _drawn(app)
    v = max(corner, key=lambda w: (_rest(app)[w][0], int(w)))
    app.selection.mode = V
    app.selection.vertices = {v}
    app.viewport.on_selection_changed()
    d.tap(key("o"))  # Soft on
    app.update_viewport(0.0)
    points = [p for layer in app.viewport.point_positions.values() for p in layer]
    assert any(_close(p, drawn[v]) for p in points)  # the selection point at the drawn corner
    bands = app._soft_overlay
    band_points = [p for layer in __import__("mirai.soft_selection", fromlist=["BAND_LAYERS"]).BAND_LAYERS for p in bands.points(layer)]
    assert band_points, "the Soft bands show points"
    on_drawn = [p for p in band_points if any(_close(p, drawn[w]) for w in mesh.all_vertex_ids())]
    assert len(on_drawn) == len(band_points)  # every band point sits where a point is drawn
    rest = _rest(app)
    assert any(not any(_close(p, rest[w]) for w in mesh.all_vertex_ids()) for p in band_points)  # and not all at rest
