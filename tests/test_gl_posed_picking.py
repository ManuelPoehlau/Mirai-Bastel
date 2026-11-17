"""GPU ID-buffer picking on the posed surface (MODELING_ON_DEFORMED_SURFACES §16, AD-022 B2-out).

While the rig is posed and the edit mesh is bound, the ID pass draws the posed surface (`Viewport.gpu_pick_mesh`
returns the cage's `RenderMesh`: the skin stage's replacement surface itself, or under SubD a never drawn one of the
posed cage); the CPU picker on an independent mesh at the drawn positions (`skinning.evaluate`) is the reference.
Without a pose the ID pass draws the edit mesh as before. Part 2: the Gollum rigging scene, jaw open (mouth corner and
inside of the mouth).

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_posed_picking.py`).
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

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import BoneId, Mesh, PointLayerInfo, SelectionMode  # noqa: E402
from core.mesh import LayerKind  # noqa: E402
from mirai import morph_mix, skinning  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.skinning import BonePose  # noqa: E402
from mirai.viewport.box_select import elements_in_rect  # noqa: E402
from mirai.viewport.picking import pick_component, pick_face  # noqa: E402
from mirai.viewport.picking_cache import PickCache  # noqa: E402
from tests.test_skin_stage import _rig  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402

W, H = 320, 240
HEAD = Path(__file__).resolve().parents[1] / "examples" / "meshes" / "head_basemesh.obj"
SCENE = Path(__file__).resolve().parents[1] / "scenes" / "Gollum_Head_rigging_test.mirai.json"
V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE
_GL = dict(store_type=GLRenderStore, point_overlay_type=GLPointOverlay, line_overlay_type=GLLineOverlay,
           face_overlay_type=GLTriangleOverlay)


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=W, height=H, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _smooth_bind(mesh: Mesh) -> None:
    """The lower half of the head to the jaw (bone 1) with a smooth ramp around the middle, the rest to bone 0: a
    pose of the jaw opens the mouth without folding the surface (the ID buffer and the CPU picker then agree)."""
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    lo, hi = min(ys), max(ys)
    mid, half = lo + 0.45 * (hi - lo), 0.12 * (hi - lo)
    for v in mesh.all_vertex_ids():
        t = min(1.0, max(0.0, (mid + half - mesh.vertex_position(v)[1]) / (2.0 * half)))
        mesh.set_layer_value(lid, v, [(0, 1.0 - t), (1, t)] if 0.0 < t < 1.0 else [(1, 1.0)] if t >= 1.0 else [(0, 1.0)])


def _jaw(app, degrees: float) -> None:
    """The jaw (bone 1) turned about X by `degrees` (the rig's hinge at the head's middle)."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    app._skeleton.set_pose({BoneId(1): BonePose(rotation=((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c)))})


def _oracle(app) -> Mesh:
    """An independent mesh at the drawn (posed) positions, same IDs and topology."""
    obj = app.scene.edit_object
    weights = app.morph.provider.object_weights(obj.id)
    mix = morph_mix.evaluate(obj.mesh, weights) if weights else None
    drawn = skinning.evaluate(obj.mesh, mix, app.scene.rig, app.skin.provider.pose, skinning.placement_of(obj))
    state = obj.mesh.export_state()
    state["point_layers"] = None
    for v, p in drawn.items():
        state["vertices"][int(v)] = list(p)
    return Mesh.from_state(state)


def _cursors(step=7):
    return [(x + 0.5, y + 0.5) for y in range(20, H - 20, step) for x in range(20, W - 20, step)]


def _faces_match(app, oracle, *, min_hits=150, min_rest_differences=20):
    mesh = app.scene.mesh
    app.selection.mode = F
    hits = border = differ = 0
    camera = app._objects.edit_camera
    for x, y in _cursors(5):
        gpu = app._pick(x, y)
        cpu = pick_face(camera, oracle, x, y, W, H)
        differ += pick_face(camera, mesh, x, y, W, H) != cpu
        if gpu == cpu:
            hits += gpu is not None
            continue
        assert gpu is None or cpu is None or set(mesh.face_vertices(gpu)) & set(mesh.face_vertices(cpu)), (x, y)
        border += 1
    assert hits > min_hits
    assert border <= 0.02 * hits
    assert differ >= min_rest_differences  # the ID buffer really shows the pose, not the rest shape


@pytest.fixture(params=["compact", "slots"])
def app(gl_window, request, monkeypatch) -> Application:
    if request.param == "slots":
        import viewport.render_mesh as render_mesh_module

        monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 0)
    gl_window.switch_to()
    app = Application()
    app.init_scene("obj", obj_path=HEAD, **_GL)
    app.set_viewport_size(W, H)
    app.frame_scene()
    app._camera_changed()
    _smooth_bind(app.scene.mesh)
    app.scene.rig = _rig(app.scene.mesh)
    _jaw(app, 28.0)
    app.update_viewport(0.0)
    app.viewport.sync()
    return app


def test_the_id_pass_draws_the_posed_surface(app):
    rm = app._gpu_pick_mesh()
    assert rm is not None and rm.mesh is app.viewport.cage_mesh is app.skin.provider.surface_mesh
    assert rm is app.viewport.surface_render_mesh  # the drawn surface itself: no second set of buffers
    _faces_match(app, _oracle(app))


@pytest.mark.parametrize("mode", [V, E])
def test_vertex_and_edge_hover_agree_with_the_cpu_picker_on_the_posed_surface(app, mode):
    oracle = _oracle(app)
    valid = oracle.is_valid_vertex if mode is V else oracle.is_valid_edge
    same = differ = 0
    app.selection.mode = mode
    for x, y in _cursors(6):
        gpu = app._pick(x, y)
        cpu = pick_component(app._objects.edit_camera, oracle, mode, x, y, W, H, occlusion=True)
        if gpu is None and cpu is None:
            continue
        assert gpu is None or valid(gpu)
        same += gpu == cpu
        differ += gpu != cpu
    assert same > 50
    assert differ <= 0.12 * (same + differ), (same, differ)


def test_box_on_the_posed_surface_keeps_the_cpu_rule(app):
    oracle = _oracle(app)
    rect = (W * 0.3, H * 0.35, W * 0.7, H * 0.85)
    for mode in (V, E, F):
        app.selection.mode = mode
        cpu = elements_in_rect(app._objects.edit_camera, oracle, mode, rect, W, H, cache=PickCache(), occlusion=True)
        gpu = app._elements_in_rect(rect, True)
        rest = elements_in_rect(app._objects.edit_camera, app.scene.mesh, mode, rect, W, H, cache=PickCache(),
                                occlusion=True)
        assert len(cpu) > 15
        assert len(cpu ^ gpu) <= 0.08 * len(cpu), (mode, len(cpu), len(cpu - gpu), len(gpu - cpu))
        assert rest != cpu


def test_a_pick_right_after_a_pose_step_sees_the_new_pose(app):
    _jaw(app, -20.0)  # no frame in between
    _faces_match(app, _oracle(app), min_rest_differences=0)


def test_under_subd_the_id_pass_draws_the_posed_cage(app):
    assert app.subdivision.set_view("cage")
    app.update_viewport(0.0)
    vp = app.viewport
    assert vp.surface_render_mesh is not None and vp.surface_render_mesh.mesh is not vp.cage_mesh
    rm = app._gpu_pick_mesh()
    assert rm is not None and rm.mesh is vp.cage_mesh is app.skin.provider.surface_mesh
    assert rm is not vp.surface_render_mesh
    _faces_match(app, _oracle(app))
    _jaw(app, 18.0)  # the never drawn cage buffers follow
    app.update_viewport(0.0)
    _faces_match(app, _oracle(app), min_rest_differences=0)


def test_at_rest_the_id_pass_draws_the_edit_mesh(app):
    app._skeleton.set_pose({})
    app.update_viewport(0.0)
    assert app.viewport.cage_mesh is None
    assert app._gpu_pick_mesh() is app.viewport.render_mesh


# -- Gollum, jaw open --------------------------------------------------------------------------------------


@pytest.mark.skipif(not SCENE.exists(), reason="scenes/Gollum_Head_rigging_test.mirai.json is not in this checkout")
def test_gollum_open_jaw_the_gpu_hover_hits_mouth_corner_and_inside_of_the_mouth(gl_window):
    gl_window.switch_to()
    app = Application()
    app.init_scene("cube", **_GL)
    app.load_scene("file", scene_path=SCENE, **_GL)
    app.set_viewport_size(W, H)
    app.frame_scene()
    app.camera.set_view(0.0, 0.1)
    app._camera_changed()
    c, s = math.cos(math.radians(30.0)), math.sin(math.radians(30.0))
    app._skeleton.set_pose({BoneId(1): BonePose(rotation=((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c)))})
    app.update_viewport(0.0)
    app.viewport.sync()
    mesh = app.scene.mesh
    rm = app._gpu_pick_mesh()
    assert rm is not None and rm.mesh is app.skin.provider.surface_mesh
    oracle = _oracle(app)
    camera = app._objects.edit_camera
    rest = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    drawn = {v: oracle.vertex_position(v) for v in mesh.all_vertex_ids()}
    # the mouth: faces whose drawn centre is at the mouth (|x| < 0.14, low, in front) agree with the CPU picker
    app.selection.mode = V
    mouth = [v for v in mesh.all_vertex_ids()
             if abs(rest[v][0]) < 0.14 and 0.09 < rest[v][1] < 0.27 and rest[v][2] > 0.15
             and pick_component(camera, oracle, V, *camera.project_to_screen(drawn[v], W, H), W, H, occlusion=True) == v]
    moved = [v for v in mouth if math.dist(camera.project_to_screen(drawn[v], W, H), camera.project_to_screen(rest[v], W, H)) > 3.0]
    assert len(moved) >= 10, (len(mouth), len(moved))
    agree = sum(app._pick(*camera.project_to_screen(drawn[v], W, H)) == v for v in moved)
    assert agree >= 0.8 * len(moved), (agree, len(moved))  # the ID buffer has the pixel under the drawn point
    at_rest = sum(app._pick(*camera.project_to_screen(rest[v], W, H)) == v for v in moved)
    assert at_rest <= 0.4 * len(moved)  # ... and no longer the rest anchor
