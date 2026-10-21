"""The GL path (needs pyglet + a display; headless: `xvfb-run -a`). llvmpipe, not the reference driver.

- The same steps (Delete in face and vertex mode, Undo, Redo) draw the same image with `none` and with `all`:
  the patched index buffer (degenerate triangles, dead slots) reaches `GLRenderStore` as the full rebuild does.
- B2 vs B1 per pixel (`check_b2.compare`): the face pass names the same face on every pixel, fresh and after
  a V1 Delete and its Undo; the point pass the same vertex.
- Stale-ID test (AD-022 §5 / §9 abort criterion 3): a pick right after a Delete and right after an Undo, with no
  frame in between, never names a dead element, and a face pick agrees with the CPU picker at the pixel centre.
"""

from __future__ import annotations

import ctypes
import math
from pathlib import Path

import pytest

from topology_stage2_delete import check_b2, gpu_pick, stage2

from core import FaceId, VertexId
from mirai.interaction.input import Input

REPO = Path(__file__).resolve().parents[3]
HEAD = REPO / "examples" / "meshes" / "head_basemesh.obj"
W, H = 320, 240


def key(name: str, *mods: str) -> Input:
    return Input("key", name, frozenset(mods))


def make(spec: str, w: int = W, h: int = H):
    import pyglet

    src_main = __import__("main")
    stage2.install(spec)
    from mirai.application import Application

    window = pyglet.window.Window(width=w, height=h, visible=False)
    app = Application()
    app.init_scene("obj", obj_path=HEAD, **src_main.GL_TYPES)
    app.set_viewport_size(w, h)
    app.frame_scene()
    app.viewport.sync()
    return window, app


def snapshot(window, app) -> bytes:
    from pyglet import gl

    window.switch_to()
    gl.glClearColor(0.05, 0.05, 0.08, 1.0)
    window.clear()
    app.update_viewport(1 / 60)
    app.viewport.render()
    gl.glFinish()
    buf = (ctypes.c_ubyte * (W * H * 4))()
    gl.glReadPixels(0, 0, W, H, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, buf)
    return bytes(buf)


def steps(app):
    mesh = app.scene.mesh
    faces = [FaceId(f) for f in mesh.all_face_ids()[100:130]]
    vertex = VertexId(mesh.all_vertex_ids()[50])
    yield "start", lambda: None
    yield "delete faces", lambda: (app.key_press(key("3")), app.selection.set(set(faces)),
                                   app.viewport.on_selection_changed(), app.key_press(key("delete")))
    yield "delete vertex", lambda: (app.key_press(key("1")), app.selection.set({vertex}),
                                    app.viewport.on_selection_changed(), app.key_press(key("delete")))
    yield "flat", lambda: app.viewport.set_display(True, False, True)
    yield "undo", lambda: app.key_press(key("z", "ctrl"))
    yield "undo 2", lambda: app.key_press(key("z", "ctrl"))
    yield "redo", lambda: app.key_press(key("y", "ctrl"))


def images(spec: str) -> list[tuple[str, bytes]]:
    window, app = make(spec)
    try:
        out = []
        for name, step in steps(app):
            step()
            out.append((name, snapshot(window, app)))
        return out
    finally:
        stage2.uninstall()
        window.close()


def test_same_image_as_the_full_rebuild():
    want = images("none")
    got = images("all")
    for (name, a), (_n, b) in zip(want, got):
        assert a == b, f"image differs after '{name}'"


def test_b2_face_and_point_pass_equal_b1_per_pixel(monkeypatch):
    monkeypatch.setattr(check_b2, "W", W)
    monkeypatch.setattr(check_b2, "H", H)
    window, app = make("all")
    try:
        picker = gpu_pick.GpuPicker()
        assert check_b2.compare("fresh", app, picker) == (0, 0)
        mesh = app.scene.mesh
        app.key_press(key("3"))
        app.selection.set({FaceId(f) for f in mesh.all_face_ids()[100:130]})
        app.key_press(key("delete"))
        assert check_b2.compare("after delete", app, picker) == (0, 0)
        app.key_press(key("z", "ctrl"))
        assert check_b2.compare("after undo", app, picker) == (0, 0)
    finally:
        stage2.uninstall()
        window.close()


def _centroid_px(app, f):
    mesh = app.scene.mesh
    pts = [app.camera.project_to_screen(mesh.vertex_position(v), W, H) for v in mesh.face_vertices(f)]
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def test_no_stale_ids_right_after_delete_and_undo():
    from mirai.viewport.picking import pick_component
    from mirai.viewport.picking_cache import PickCache

    window, app = make("all")
    try:
        mesh = app.scene.mesh
        app.key_press(key("3"))
        # Faces facing the camera, so their centroids are on screen and visible.
        targets = [f for f in mesh.all_face_ids()[::7]][:40]
        points = [_centroid_px(app, f) for f in targets]
        app._stage2_gpu = picker = gpu_pick.GpuPicker()
        app.pointer_motion(*points[0])
        app.update_viewport(1 / 60)
        app.selection.set(set(targets))
        app.key_press(key("delete"))  # no frame after this
        def check_faces():
            for x, y in points:
                hit = picker.pick(app, x, y)
                assert hit is None or mesh.is_valid_face(hit)
                cpu = pick_component(app._edit_camera, mesh, app.selection.mode, math.floor(x) + 0.5,
                                     math.floor(y) + 0.5, W, H, cache=PickCache(), occlusion=True)
                assert type(hit) is type(cpu) and hit == cpu

        check_faces()
        app.key_press(key("z", "ctrl"))  # no frame after this either
        check_faces()
        assert any(picker.pick(app, x, y) == f for (x, y), f in zip(points, targets))
        app.key_press(key("1"))
        for x, y in points:
            hit = picker.pick(app, x, y)
            assert hit is None or mesh.is_valid_vertex(hit)
    finally:
        stage2.uninstall()
        window.close()
