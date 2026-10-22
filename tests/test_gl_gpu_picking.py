"""GPU picking in the window (AD-022 B2-out): the ID buffers drawn from the `RenderMesh` buffers against the CPU
picker, the reference.

- Face mapping is exact: at the centre of every pixel the GPU face equals the face whose triangle the CPU ray
  through that pixel centre hits first (CPU `pick_face` at `x + 0.5, y + 0.5`), allowing only cursors on a face
  border (the neighbour of the CPU's face).
- Vertex / edge hover agree with the CPU picker on most non-trivial cursors; every disagreement is another
  visible element at about the same distance (AD-022 §2), never a dead ID.
- No stale buffers: a pick right after a Delete and right after its Undo, with no frame in between, names live
  elements only (AD-022 §5).
- Box with the depth oracle keeps the CPU rule within a few percent (AD-022 §2: 0-6.5 %).

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_gpu_picking.py`).
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import sys
from pathlib import Path

import pytest

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import FaceId, SelectionMode  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.viewport.box_select import elements_in_rect  # noqa: E402
from mirai.viewport.gpu_picking import gpu_elements_in_rect  # noqa: E402
from mirai.viewport.picking import pick_component, pick_face  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402

W, H = 320, 240
HEAD = Path(__file__).resolve().parents[1] / "examples" / "meshes" / "head_basemesh.obj"


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=W, height=H, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


@pytest.fixture(params=["compact", "slots"])
def app(gl_window, request, monkeypatch) -> Application:
    if request.param == "slots":
        # The patch path with spare slots and dead triangles, as on meshes above 2048 elements.
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
    app.viewport.sync()
    return app


def _cpu(app, mode, x, y):
    return pick_component(app._edit_camera, app.scene.mesh, mode, x, y, W, H,
                          cache=app._pick_cache, occlusion=app.display.show_faces)


def _gpu(app, mode, x, y):
    app.selection.mode = mode
    return app._pick(x, y)


def _cursors(step=7):
    return [(x + 0.5, y + 0.5) for y in range(20, H - 20, step) for x in range(20, W - 20, step)]


def test_the_window_uses_the_gpu_path(app):
    assert app._gpu_pick_mesh() is not None


def test_face_ids_are_exact_at_pixel_centres(app):
    mesh = app.scene.mesh
    hits = border = 0
    for x, y in _cursors(5):
        gpu = _gpu(app, SelectionMode.FACE, x, y)
        cpu = pick_face(app._edit_camera, mesh, x, y, W, H, cache=app._pick_cache)
        if gpu == cpu:
            hits += gpu is not None
            continue
        assert gpu is not None and cpu is not None, (x, y, gpu, cpu)
        # A pixel centre on a shared edge: the neighbour is the only allowed difference.
        assert set(mesh.face_vertices(gpu)) & set(mesh.face_vertices(cpu)), (x, y)
        border += 1
    assert hits > 200
    assert border <= 0.02 * hits


@pytest.mark.parametrize("mode", [SelectionMode.VERTEX, SelectionMode.EDGE])
def test_hover_agrees_with_the_cpu_picker(app, mode):
    mesh = app.scene.mesh
    valid = mesh.is_valid_vertex if mode is SelectionMode.VERTEX else mesh.is_valid_edge
    same = differ = 0
    for x, y in _cursors(6):
        gpu = _gpu(app, mode, x, y)
        cpu = _cpu(app, mode, x, y)
        if gpu is None and cpu is None:
            continue
        assert gpu is None or valid(gpu)
        if gpu == cpu:
            same += 1
        else:
            differ += 1
    assert same > 50
    assert differ <= 0.12 * (same + differ), (same, differ)


def test_no_stale_ids_right_after_delete_and_undo(app):
    """A pick with no frame in between must see the new buffers: it names what the CPU ray sees now
    (the face behind the hole, or nothing), not the deleted face and not a stale "nothing"."""
    mesh = app.scene.mesh
    app.key_press(Input("key", "3"))
    cursors = [(W / 2 + 0.5 + dx, H / 2 + 0.5 + dy) for dx in (-30, 0, 30) for dy in (-20, 0, 20)]
    faces = {_gpu(app, SelectionMode.FACE, x, y) for x, y in cursors} - {None}
    assert len(faces) >= 3
    app.selection.set(faces)
    app.viewport.on_selection_changed()
    app.key_press(Input("key", "delete"))
    assert not any(mesh.is_valid_face(f) for f in faces)

    def cpu_face(x, y):
        return pick_face(app._edit_camera, mesh, x, y, W, H, cache=app._pick_cache)

    for x, y in cursors:
        assert app._pick(x, y) == cpu_face(x, y), (x, y)
    app.key_press(Input("key", "z", frozenset({"ctrl"})))
    for x, y in cursors:
        assert app._pick(x, y) == cpu_face(x, y), (x, y)
    assert {app._pick(x, y) for x, y in cursors} - {None} == faces


@pytest.mark.parametrize("mode", [SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE])
def test_box_keeps_the_cpu_rule_within_a_few_percent(app, mode):
    from mirai.viewport.gpu_picking import gpu_elements_in_rect

    rect = (W * 0.3, H * 0.25, W * 0.7, H * 0.75)
    cpu = elements_in_rect(app._edit_camera, app.scene.mesh, mode, rect, W, H,
                           cache=app._pick_cache, occlusion=True)
    gpu = gpu_elements_in_rect(app.viewport.gpu_picker, app._gpu_pick_mesh(), app._edit_camera, app.scene.mesh,
                               mode, rect, W, H, cache=app._pick_cache, occlusion=True)
    assert len(cpu) > 20
    assert len(cpu ^ gpu) <= 0.08 * len(cpu), (len(cpu), len(cpu - gpu), len(gpu - cpu))


def test_a_gl_failure_falls_back_to_the_cpu_picker(app, monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("ID framebuffer incomplete (status 0x8cd6)")

    monkeypatch.setattr(app.viewport.gpu_picker, "prepare", broken)
    x, y = W / 2 + 0.5, H / 2 + 0.5
    expected = _cpu(app, SelectionMode.FACE, x, y)
    assert _gpu(app, SelectionMode.FACE, x, y) == expected
    assert app.gpu_picking is False
    assert "GPU picking off" in app.status_message


def _wavy_ngon_app(gl_window, tmp_path, yaw, pitch) -> Application:
    """One non-planar 12-gon (alternating z): its own triangles lie in front of some of its corners."""
    import math

    n = 12
    rows = [f"v {math.cos(2 * math.pi * i / n):.5f} {math.sin(2 * math.pi * i / n):.5f} {0.35 * (-1) ** i}"
            for i in range(n)]
    rows.append("f " + " ".join(str(i + 1) for i in range(n)))
    obj = tmp_path / "wavy.obj"
    obj.write_text("\n".join(rows) + "\n")
    gl_window.switch_to()
    app = Application()
    app.init_scene(
        "obj", obj_path=obj, store_type=GLRenderStore, point_overlay_type=GLPointOverlay,
        line_overlay_type=GLLineOverlay, face_overlay_type=GLTriangleOverlay,
    )
    app.set_viewport_size(W, H)
    app.frame_scene()
    app._edit_camera.orbit(yaw, pitch)
    app._camera_changed()
    app.viewport.sync()
    return app


@pytest.mark.parametrize("yaw,pitch", [(0.0, 0.0), (0.5, 0.6), (0.3, 1.2)])
def test_corners_and_edges_of_a_non_planar_ngon_stay_pickable(gl_window, tmp_path, yaw, pitch):
    """The ID buffer's depth holds the Ngon's own triangles; the CPU rule excludes the incident faces, so
    the GPU path must too (the corner under the cursor was unpickable, reported 2026-10-22)."""
    app = _wavy_ngon_app(gl_window, tmp_path, yaw, pitch)
    mesh = app.scene.mesh
    camera = app._edit_camera
    for vid in mesh.all_vertex_ids():
        p = camera.project_to_screen(mesh.vertex_position(vid), W, H)
        assert _gpu(app, SelectionMode.VERTEX, p[0], p[1]) == vid, vid
    for eid in mesh.all_edge_ids():
        va, vb = mesh.edge_vertices(eid)
        a = camera.project_to_screen(mesh.vertex_position(va), W, H)
        b = camera.project_to_screen(mesh.vertex_position(vb), W, H)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        assert _gpu(app, SelectionMode.EDGE, mx, my) == _cpu(app, SelectionMode.EDGE, mx, my), eid
    picked = gpu_elements_in_rect(
        app.viewport.gpu_picker, app._gpu_pick_mesh(), camera, mesh, SelectionMode.VERTEX, (0, 0, W, H), W, H,
        cache=app._pick_cache, occlusion=True,
    )
    assert set(picked) == set(mesh.all_vertex_ids())
