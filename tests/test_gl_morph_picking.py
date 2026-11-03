"""GPU ID-buffer picking on the drawn morph mix (MODELING_ON_DEFORMED_SURFACES §15, AD-022 B2-out).

While a target is dialled in, the ID pass draws the mix (`Viewport.gpu_pick_mesh` returns the cage's
`RenderMesh`: the replacement surface itself, or under SubD a never drawn one of the mixed cage); the CPU
picker on an independent mesh at the drawn positions is the reference. At 0 % the ID pass draws the edit
mesh as before.

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_morph_picking.py`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Mesh, PointLayerInfo, SelectionMode  # noqa: E402
from mirai import morph_mix  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.viewport.box_select import elements_in_rect  # noqa: E402
from mirai.viewport.picking import pick_component, pick_face  # noqa: E402
from mirai.viewport.picking_cache import PickCache  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402

W, H = 320, 240
HEAD = Path(__file__).resolve().parents[1] / "examples" / "meshes" / "head_basemesh.obj"
V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=W, height=H, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _open_mouth(mesh: Mesh):
    """A smooth "mouth open" target: the lower half of the head drops and comes forward, growing downwards."""
    lid = mesh.add_point_layer(PointLayerInfo("Jaw open"))
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    lo, hi = min(ys), max(ys)
    mid = (lo + hi) / 2.0
    for v in mesh.all_vertex_ids():
        y = mesh.vertex_position(v)[1]
        if y < mid:
            s = (mid - y) / (mid - lo)
            mesh.set_layer_value(lid, v, (0.0, -0.35 * s * (hi - lo), 0.2 * s * (hi - lo)))
    return lid


@pytest.fixture(params=["compact", "slots"])
def app(gl_window, request, monkeypatch) -> Application:
    if request.param == "slots":
        import viewport.render_mesh as render_mesh_module

        monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 0)
    gl_window.switch_to()
    app = Application()
    app.init_scene(
        "obj", obj_path=HEAD, store_type=GLRenderStore, point_overlay_type=GLPointOverlay,
        line_overlay_type=GLLineOverlay, face_overlay_type=GLTriangleOverlay,
    )
    app.set_viewport_size(W, H)
    app.frame_scene()
    app._camera_changed()
    lid = _open_mouth(app.scene.mesh)
    app.set_morph_weight(100, lid)
    app.update_viewport(0.0)
    app.viewport.sync()
    app.lid = lid
    return app


def _oracle(app) -> Mesh:
    mesh = app.scene.mesh
    state = mesh.export_state()
    state["point_layers"] = None
    weights = app.morph.provider.object_weights(app.scene.edit_object_id)
    for v, p in morph_mix.evaluate(mesh, weights).items():
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
        # a pixel centre on a shared edge (the neighbour) or on the silhouette (one of them sees nothing)
        assert gpu is None or cpu is None or set(mesh.face_vertices(gpu)) & set(mesh.face_vertices(cpu)), (x, y)
        border += 1
    assert hits > min_hits
    assert border <= 0.02 * hits
    assert differ >= min_rest_differences  # the ID buffer really shows the mix, not the rest shape


def test_the_id_pass_draws_the_mix(app):
    rm = app._gpu_pick_mesh()
    assert rm is not None and rm.mesh is app.viewport.cage_mesh is app.morph.provider.surface_mesh
    assert rm is app.viewport.surface_render_mesh  # the drawn surface itself: no second set of buffers
    _faces_match(app, _oracle(app))


@pytest.mark.parametrize("mode", [V, E])
def test_vertex_and_edge_hover_agree_with_the_cpu_picker_on_the_mix(app, mode):
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


def test_box_on_the_mix_keeps_the_cpu_rule(app):
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


def test_a_pick_right_after_a_base_edit_sees_the_new_mix(app):
    mesh = app.scene.mesh
    app.selection.mode = F
    shift = {v: (p[0], p[1], p[2] + 0.3) for v in mesh.all_vertex_ids() for p in (mesh.vertex_position(v),)}

    def move():
        for v, p in shift.items():
            mesh.set_vertex_position(v, p)
        return set(shift)

    app.apply_mesh_change("move", move)
    _faces_match(app, _oracle(app), min_rest_differences=0)  # no frame in between


def test_under_subd_the_id_pass_draws_the_mixed_cage(app):
    assert app.subdivision.set_view("cage")
    app.update_viewport(0.0)
    vp = app.viewport
    assert vp.surface_render_mesh is not None and vp.surface_render_mesh.mesh is not vp.cage_mesh
    rm = app._gpu_pick_mesh()
    assert rm is not None and rm.mesh is vp.cage_mesh and rm is not vp.surface_render_mesh
    _faces_match(app, _oracle(app))
    # a weight step: the never drawn cage buffers follow at the next pick
    app.set_morph_weight(40, app.lid)
    app.update_viewport(0.0)
    _faces_match(app, _oracle(app))


def test_at_zero_percent_the_id_pass_draws_the_edit_mesh(app):
    app.set_morph_weight(0, app.lid)
    app.update_viewport(0.0)
    assert app.viewport.cage_mesh is None
    assert app._gpu_pick_mesh() is app.viewport.render_mesh
