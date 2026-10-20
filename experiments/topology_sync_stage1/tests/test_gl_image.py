"""The GL path: the same steps with stage 1 on and off must draw the same image (needs pyglet + a display;
headless: `xvfb-run -a`). The headless tests compare buffers; this one checks that the V2 patch path and the
V0 rebuild reach `GLRenderStore` the way the full rebuild does. llvmpipe, not the reference driver."""

from __future__ import annotations

import ctypes
import math
from pathlib import Path

import pytest

from topology_sync_stage1 import stage1

from core import FaceId
from mirai.interaction.input import Input

REPO = Path(__file__).resolve().parents[3]
HEAD = REPO / "examples" / "meshes" / "head_basemesh.obj"
W, H = 320, 240


def key(name: str, *mods: str) -> Input:
    return Input("key", name, frozenset(mods))


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


def images(spec: str) -> list[bytes]:
    import pyglet

    src_main = __import__("main")
    stage1.install(spec)
    window = pyglet.window.Window(width=W, height=H, visible=False)
    try:
        from mirai.application import Application

        app = Application()
        app.init_scene("obj", obj_path=HEAD, **src_main.GL_TYPES)
        app.set_viewport_size(W, H)
        app.frame_scene()
        mesh, cam = app.scene.mesh, app.camera
        def front():
            return min(mesh.all_face_ids(), key=lambda g: math.dist(
                tuple(sum(mesh.vertex_position(v)[i] for v in mesh.face_vertices(g)) / len(mesh.face_vertices(g))
                      for i in range(3)), cam.eye()))

        f = front()
        pts = [cam.project_to_screen(mesh.vertex_position(v), W, H) for v in mesh.face_vertices(f)]
        cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        out = [snapshot(window, app)]

        app.key_press(key("3"))
        app.selection.set({FaceId(f)})
        app.viewport.on_selection_changed()
        app.pointer_motion(cx, cy)
        app.key_press(key("t"))
        app.pointer_motion(cx, cy + 8.0, 0.0, 8.0)
        out.append(snapshot(window, app))
        app.pointer_motion(cx, cy + 30.0, 0.0, 22.0)
        out.append(snapshot(window, app))
        app.key_release(key("t"))
        out.append(snapshot(window, app))
        app.key_press(key("delete"))
        out.append(snapshot(window, app))
        for _ in range(2):
            app.key_press(key("z", "ctrl"))
            out.append(snapshot(window, app))
        app.key_press(key("y", "ctrl"))
        out.append(snapshot(window, app))
        moved = mesh.face_vertices(front())

        def mutate():
            for v in moved:
                x, y, z = mesh.vertex_position(v)
                mesh.set_vertex_position(v, (x, y + 0.3, z + 0.3))
            return set(moved)

        app.apply_mesh_change("move", mutate)  # geometry path
        out.append(snapshot(window, app))
        app.key_press(key("z", "ctrl"))  # positions-only undo: the V2 patch path
        out.append(snapshot(window, app))
        return out
    finally:
        window.close()
        stage1.uninstall()


def test_same_image_with_and_without_stage1():
    pytest.importorskip("pyglet")
    off, on = images("none"), images("all")
    assert len(off) == len(on)
    assert len(set(off)) > 3  # the steps change the picture
    for i, (a, b) in enumerate(zip(off, on)):
        diff = sum(1 for x, y in zip(a, b) if abs(x - y) > 1)
        assert diff == 0, f"step {i}: {diff} channel values differ by more than 1"
