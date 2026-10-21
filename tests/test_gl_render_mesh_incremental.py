"""The incremental topology sync (AD-023 V1) in the real GL path: after topology patches (Delete,
an Extrude-like growth into spare slots, their Undo / Redo) the patched `RenderMesh` draws the
same image as a freshly built one. Exercises the index-buffer patch of `GLRenderStore`
(`_patch_attribute` on the index name) and the degenerate dead triangles.

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_render_mesh_incremental.py`).
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

import viewport.render_mesh as render_mesh_module  # noqa: E402
from core import HistoryStack, Mesh  # noqa: E402
from core.operations import MeshDeltaCommand, record_mesh_change  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.render_mesh import RenderMesh  # noqa: E402

SIZE = 200


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


@pytest.fixture(autouse=True)
def _always_incremental(monkeypatch):
    monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 0)
    monkeypatch.setattr(render_mesh_module, "SPARE_FRACTION", 0.5)


def _grid(n: int) -> Mesh:
    mesh = Mesh()
    ids = [[mesh.add_vertex((x / n * 2 - 1, y / n * 2 - 1, 0.15 * ((x + y) % 2))) for x in range(n + 1)]
           for y in range(n + 1)]
    for y in range(n):
        for x in range(n):
            mesh.add_face([ids[y][x], ids[y][x + 1], ids[y + 1][x + 1], ids[y + 1][x]])
    return mesh


def _camera() -> OrbitCamera:
    return OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.0, yaw=0.3, pitch=0.5)


def _build(gl_window, mesh: Mesh) -> RenderMesh:
    gl_window.switch_to()
    rm = RenderMesh(mesh, store_type=GLRenderStore)
    rm.bind_camera(_camera())
    rm.mark_camera_dirty(aspect=1.0)
    rm.sync()
    return rm


def _draw(gl_window, rm: RenderMesh) -> bytes:
    from pyglet import gl

    gl_window.switch_to()
    gl.glViewport(0, 0, *gl_window.get_framebuffer_size())
    gl.glClearColor(0.0, 0.0, 0.0, 1.0)
    gl_window.clear()
    rm.render(rm.camera)
    gl.glFinish()
    buf = (gl.GLubyte * (SIZE * SIZE * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def _fresh_image(gl_window, mesh: Mesh) -> bytes:
    rm = _build(gl_window, mesh)
    pixels = _draw(gl_window, rm)
    rm.store.release()
    rm._watch.close()
    return pixels


def _extrude_like(mesh: Mesh, face) -> None:
    b = mesh.face_vertices(face)
    top = [mesh.add_vertex((x, y, z + 0.4)) for x, y, z in (mesh.vertex_position(v) for v in b)]
    for i in range(len(b)):
        mesh.add_face([b[i], b[(i + 1) % len(b)], top[(i + 1) % len(b)], top[i]])
    mesh.add_face(top)
    mesh.remove_face(face)


def test_patched_buffers_draw_like_a_fresh_build(gl_window):
    mesh = _grid(8)
    rm = _build(gl_window, mesh)
    history = HistoryStack()
    faces = mesh.all_face_ids()
    steps = [
        lambda: mesh.delete_faces(faces[10:13]),
        lambda: _extrude_like(mesh, faces[30]),
        lambda: mesh.split_edge(mesh.face_edges(faces[40])[0], 0.3),
        lambda: mesh.dissolve_faces([faces[50], faces[51]], cleanup=True),
    ]
    for step in steps:
        delta, _ = record_mesh_change(mesh, step)
        history.push(MeshDeltaCommand(mesh, delta, "op"))
        rm.mark_topology_dirty()
        rm.sync()
        assert _draw(gl_window, rm) == _fresh_image(gl_window, mesh)
    while history.can_undo():
        history.undo()
        rm.mark_topology_dirty()
        rm.sync()
        assert _draw(gl_window, rm) == _fresh_image(gl_window, mesh)
    history.redo()
    history.redo()
    rm.mark_topology_dirty()
    rm.sync()
    assert _draw(gl_window, rm) == _fresh_image(gl_window, mesh)
    assert rm.stats.get("topology_patches") >= len(steps)
    rm.store.release()
