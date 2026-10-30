"""AD-021 M2-1 — object placement in the draw and component paths (no UI yet).

Headless (TraceStore), no pyglet. The placement is set directly on `SceneObject.transform`
(the M2-2 object tools do not exist yet) and announced with `Application._placement_changed`.
Checks E-2 (formula), E-7 (Objektraum-Kamera), E-8 (world-axis constraints), E-9 (model
matrix), E-10 (object picking), §4.8 (symmetry and soft in object space; Probe P-2 as a test)
and that an unplaced object stays bit-exact as before.
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

from core import EdgeId, FaceId, ObjectTransform, SceneObject, SelectionMode, VertexId
from mirai import object_space
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.object_space import ObjectSpaceCamera
from mirai.scene_factory import create_cube
from mirai.symmetry import symmetry_state, vertex_correspondence
from mirai.symmetry_axis import set_symmetry_axis
from mirai.viewport import OrbitCamera
from mirai.viewport.picking import pick_nearest_vertex
from core.ids import ObjectId

WIDTH, HEIGHT = 800, 600
HEAD_OBJ = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"


def _rot_y(degrees: float):
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


PLACEMENT = ObjectTransform(translation=(0.7, 0.3, -0.4), rotation=_rot_y(30.0), scale=1.5)
PIVOT = (0.2, 0.0, 0.1)


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _app(placed: bool = True, obj_path=None) -> Application:
    app = Application()
    if obj_path is None:
        app.init_scene("cube")
    else:
        app.init_scene("obj", obj_path=obj_path)
    if placed:
        _place(app, app.scene.edit_object)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _place(app: Application, obj: SceneObject, transform=PLACEMENT, pivot=PIVOT) -> None:
    obj.transform = transform
    obj.pivot = pivot
    app._placement_changed()


def _close(a, b, tol=1e-9) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _screen_of(app: Application, p_obj) -> tuple[float, float]:
    world = object_space.to_world(app.scene.edit_object, p_obj)
    return app.camera.project_to_screen(world, WIDTH, HEIGHT)


def _centroid(points):
    points = list(points)
    return tuple(sum(p[i] for p in points) / len(points) for i in range(3))


def _visible_vertex(app: Application) -> VertexId:
    mesh, cam = app.scene.mesh, app._edit_camera
    for vid in sorted(mesh.all_vertex_ids()):
        x, y = cam.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
        if pick_nearest_vertex(cam, mesh, x, y, WIDTH, HEIGHT, occlusion=True) == vid:
            return vid
    raise AssertionError("no visible vertex")


def _click(app: Application, x: float, y: float, *modifiers: str) -> None:
    app.pointer_press(Input("mouse", "LEFT", frozenset(modifiers)), x, y)
    app.pointer_release("LEFT", x, y)


# -- E-2 / E-6: the math -----------------------------------------------------------------


def test_to_world_and_back_and_the_model_matrix_agree():
    obj = SceneObject(ObjectId(0), create_cube(), transform=PLACEMENT, pivot=PIVOT)
    p = (0.3, -0.8, 0.45)
    w = object_space.to_world(obj, p)
    # world(p) = t + c + s·R·(p − c), R in rows.
    rel = tuple(p[i] - PIVOT[i] for i in range(3))
    rp = tuple(sum(PLACEMENT.rotation[i][j] * rel[j] for j in range(3)) for i in range(3))
    expected = tuple(PLACEMENT.translation[i] + PIVOT[i] + 1.5 * rp[i] for i in range(3))
    assert _close(w, expected)
    assert _close(object_space.to_object(obj, w), p)
    m = object_space.model_matrix(obj)
    via_matrix = tuple(sum(m[col * 4 + row] * (list(p) + [1.0])[col] for col in range(4)) for row in range(3))
    assert _close(via_matrix, w)
    d = (0.1, 0.2, -0.3)
    assert _close(object_space.delta_to_object(obj, object_space.delta_to_world(obj, d)), d)
    a = object_space.axis_to_object(obj, (1.0, 0.0, 0.0))
    assert abs(math.sqrt(sum(c * c for c in a)) - 1.0) < 1e-12


def test_identity_is_an_exact_pass_through_whatever_the_pivot():
    obj = SceneObject(ObjectId(0), create_cube(), pivot=(0.1, 0.2, 0.3))
    p = (0.3, 0.7, -0.9)
    assert object_space.to_world(obj, p) == p
    assert object_space.to_object(obj, p) == p
    assert object_space.model_matrix(obj) is None


# -- E-7: the Objektraum-Kamera --------------------------------------------------------------


def test_object_space_camera_projects_and_casts_rays_through_the_placement():
    obj = SceneObject(ObjectId(0), create_cube(), transform=PLACEMENT, pivot=PIVOT)
    camera = OrbitCamera()
    camera.frame_on_bounds((0.7, 0.3, -0.4), 3.0)
    cam = ObjectSpaceCamera(camera, obj)
    p = (0.5, 0.5, -0.5)
    assert cam.project_to_screen(p, WIDTH, HEIGHT) == camera.project_to_screen(
        object_space.to_world(obj, p), WIDTH, HEIGHT
    )
    sx, sy = cam.project_to_screen(p, WIDTH, HEIGHT)
    origin, direction = cam.screen_to_ray(sx, sy, WIDTH, HEIGHT)
    to_p = tuple(p[i] - origin[i] for i in range(3))
    t = sum(to_p[i] * direction[i] for i in range(3))
    assert _close(tuple(origin[i] + t * direction[i] for i in range(3)), p, 1e-9)
    assert _close(cam.eye(), object_space.to_object(obj, camera.eye()))
    revision = cam.camera_revision
    obj.transform = ObjectTransform(translation=(1.0, 0.0, 0.0))
    assert cam.camera_revision != revision


# -- unplaced: bit-exact as before -----------------------------------------------------------


def test_an_unplaced_edit_object_uses_the_orbit_camera_and_no_model_uniform():
    app = _app(placed=False)
    assert app._edit_camera is app.camera
    app.viewport.sync()
    assert not app.viewport.render_mesh.store.has("model_uniforms")
    assert app.viewport.overlay_camera_uniforms() == app.viewport.render_mesh._camera_uniforms()


# -- E-9: drawing ------------------------------------------------------------------------------


def test_the_model_matrix_reaches_the_mesh_and_the_overlay_uniforms():
    app = _app()
    m = object_space.model_matrix(app.scene.edit_object)
    app.viewport.sync()
    assert app.viewport.render_mesh.store.data("model_uniforms") == m
    view_proj = app.viewport.render_mesh._camera_uniforms()
    overlay = app.viewport.overlay_camera_uniforms()
    assert overlay[16:] == view_proj[16:]
    # view·model applied to an object point = view applied to its world point.
    p = [0.4, -0.2, 0.9, 1.0]
    w = list(object_space.to_world(app.scene.edit_object, p[:3])) + [1.0]
    via_overlay = [sum(overlay[c * 4 + r] * p[c] for c in range(4)) for r in range(4)]
    via_view = [sum(view_proj[c * 4 + r] * w[c] for c in range(4)) for r in range(4)]
    assert _close(via_overlay, via_view, 1e-9)
    # Buffer positions stay object space: nothing was rebuilt for the placement.
    assert app.viewport.render_mesh.benchmark_counters.get("topology_updates", 0) == 0


def test_frame_scene_frames_the_world_bounds_of_the_edit_object():
    app = _app()
    assert _close(app.camera.target, object_space.to_world(app.scene.edit_object, (0.0, 0.0, 0.0)))


def test_a_placed_reference_entry_carries_its_own_matrix():
    app = _app(placed=False)
    ref = app.add_reference("cube")
    _place(app, ref)
    app.viewport.sync()
    entry = app.viewport.object_entries[ref.id]
    assert entry.store.data("model_uniforms") == object_space.model_matrix(ref)
    assert not app.viewport.render_mesh.store.has("model_uniforms")


# -- component picking through the placement (L-5) ------------------------------------------


@pytest.mark.parametrize("mode", ["1", "2", "3"])
def test_hover_and_click_hit_the_element_at_its_placed_screen_position(mode):
    app = _app()
    app.key_press(_key(mode))
    mesh = app.scene.mesh
    if mode == "1":
        element = _visible_vertex(app)
        point = mesh.vertex_position(element)
    elif mode == "2":
        cam = app._edit_camera
        element = next(
            e for e in sorted(mesh.all_edge_ids())
            if app._pick(*cam.project_to_screen(
                _centroid(mesh.vertex_position(v) for v in mesh.edge_vertices(e)), WIDTH, HEIGHT
            )) == e
        )
        point = _centroid(mesh.vertex_position(v) for v in mesh.edge_vertices(element))
    else:
        cam = app._edit_camera
        element = next(
            f for f in sorted(mesh.all_face_ids())
            if app._pick(*cam.project_to_screen(
                _centroid(mesh.vertex_position(v) for v in mesh.face_vertices(f)), WIDTH, HEIGHT
            )) == f
        )
        point = _centroid(mesh.vertex_position(v) for v in mesh.face_vertices(element))
    x, y = _screen_of(app, point)
    app.pointer_motion(x, y)
    assert app.selection.hovered == element and type(app.selection.hovered) is type(element)
    _click(app, x, y)
    active = {"1": app.selection.vertices, "2": app.selection.edges, "3": app.selection.faces}[mode]
    assert active == {element}


def test_a_placed_reference_in_front_never_blocks_component_picking_and_wins_in_mode_4():
    """RF-6 and E-10 with placements: a Reference cube scaled 3x around the edit cube."""
    app = _app()
    ref = app.add_reference("cube")
    big = ObjectTransform(
        translation=PLACEMENT.translation, rotation=PLACEMENT.rotation, scale=3 * PLACEMENT.scale
    )
    _place(app, ref, transform=big, pivot=PIVOT)
    vid = _visible_vertex(app)
    x, y = _screen_of(app, app.scene.mesh.vertex_position(vid))
    _click(app, x, y)
    assert app.selection.vertices == {vid}
    app.key_press(_key("4"))
    assert app._pick(x, y) == ref.id


# -- W/E/R/T and constraints through the placement (E-7, E-8) -------------------------------


def _select_visible_vertex(app: Application) -> VertexId:
    vid = _visible_vertex(app)
    _click(app, *_screen_of(app, app.scene.mesh.vertex_position(vid)))
    assert app.selection.vertices == {vid}
    return vid


def _world(app, vid):
    return object_space.to_world(app.scene.edit_object, app.scene.mesh.vertex_position(vid))


def _gesture(app, key, dx=24.0, dy=9.0, constraint=None):
    if constraint is not None:
        app.key_press(constraint)
    app.key_press(key)
    app.pointer_motion(400, 300, dx, dy)
    app.key_release(key)
    if constraint is not None:
        app.key_press(constraint)  # sticky toggle back off


def test_free_move_follows_the_screen_plane_in_world():
    app = _app()
    vid = _select_visible_vertex(app)
    before = _world(app, vid)
    expected = app.camera.screen_delta_to_world(before, 24.0, 9.0, WIDTH, HEIGHT)
    _gesture(app, _key("w"))
    after = _world(app, vid)
    assert _close(tuple(after[i] - before[i] for i in range(3)), expected, 1e-9)


def test_move_constrained_to_x_moves_along_world_x_only():
    app = _app()
    vid = _select_visible_vertex(app)
    before = _world(app, vid)
    _gesture(app, _key("w"), constraint=_key("x"))
    after = _world(app, vid)
    assert abs(after[0] - before[0]) > 1e-3
    assert _close(after[1:], before[1:], 1e-9)


def test_rotate_about_world_z_keeps_world_z():
    app = _app()
    _select_visible_vertex(app)
    app.key_press(_key("3"))
    face = next(iter(app.scene.mesh.all_face_ids()))
    app.selection.faces = {face}
    verts = app.scene.mesh.face_vertices(face)
    before = {v: _world(app, v) for v in verts}
    _gesture(app, _key("e"), constraint=_key("z"))
    moved = False
    for v in verts:
        after = _world(app, v)
        assert abs(after[2] - before[v][2]) < 1e-9
        moved = moved or not _close(after, before[v], 1e-6)
    assert moved


def test_scale_along_world_x_keeps_world_y_and_z():
    app = _app()
    app.key_press(_key("3"))
    face = next(iter(app.scene.mesh.all_face_ids()))
    app.selection.faces = {face}
    verts = app.scene.mesh.face_vertices(face)
    before = {v: _world(app, v) for v in verts}
    _gesture(app, _key("r"), constraint=_key("x"))
    changed = False
    for v in verts:
        after = _world(app, v)
        assert _close(after[1:], before[v][1:], 1e-9)
        changed = changed or abs(after[0] - before[v][0]) > 1e-6
    assert changed


def test_extrude_on_a_placed_object_moves_along_the_object_normal():
    app = _app()
    app.key_press(_key("3"))
    mesh = app.scene.mesh
    face = next(iter(mesh.all_face_ids()))
    app.selection.faces = {face}
    faces_before = len(mesh.all_face_ids())
    app.key_press(_key("t"))
    app.pointer_motion(400, 300, 0.0, 40.0)
    app.pointer_motion(400, 300, 0.0, 40.0)
    app.key_release(_key("t"))
    assert len(mesh.all_face_ids()) > faces_before
    assert app.history.can_undo()


def test_the_knife_picks_the_edge_at_its_placed_screen_position():
    app = _app()
    mesh = app.scene.mesh
    vid = _visible_vertex(app)
    cam = app._edit_camera
    for eid in sorted(mesh.all_edge_ids()):
        if vid not in mesh.edge_vertices(eid):
            continue
        mid = _centroid(mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
        target = app._knife.pick(*cam.project_to_screen(mid, WIDTH, HEIGHT))
        if target.get("kind") == "edge" and target["edge_id"] == eid:
            assert app.key_press(_key("c"))
            assert app.knife_active
            hit = app._knife.pick(*_screen_of(app, mid))
            assert hit.get("kind") == "edge" and hit["edge_id"] == eid
            return
    raise AssertionError("no edge of the visible vertex is knife-pickable")


def test_soft_weights_are_the_same_placed_or_not():
    plain, placed = _app(placed=False), _app()
    seeds = {sorted(plain.scene.mesh.all_vertex_ids())[0]}
    for app in (plain, placed):
        app.key_press(_key("o"))
    assert plain._soft_preview_weights(seeds) == placed._soft_preview_weights(seeds)


# -- §4.8, Probe P-2 as a test -----------------------------------------------------------------


@pytest.mark.skipif(not HEAD_OBJ.is_file(), reason="head_basemesh fehlt (examples/meshes/)")
def test_p2_a_rotated_symmetric_head_stays_exactly_symmetric_under_a_symmetric_move():
    app = _app(placed=False, obj_path=HEAD_OBJ)
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    _place(app, app.scene.edit_object, transform=ObjectTransform(rotation=_rot_y(30.0)), pivot=(0.0, 0.0, 0.0))
    app.frame_scene()
    assert symmetry_state(mesh).value == "valid"
    vid = next(
        v for v in sorted(mesh.all_vertex_ids())
        if mesh.vertex_position(v)[0] > 0.1
        and app._pick(*app._edit_camera.project_to_screen(mesh.vertex_position(v), WIDTH, HEIGHT)) == v
    )
    _click(app, *_screen_of(app, mesh.vertex_position(vid)))
    _gesture(app, _key("w"), dx=17.0, dy=-11.0)
    assert app.history.can_undo()
    corr = vertex_correspondence(mesh)
    partner = corr[vid].partner
    a, b = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert (b[0], b[1], b[2]) == (-a[0], a[1], a[2])  # bit-exact in object space
    assert symmetry_state(mesh).value == "valid"
