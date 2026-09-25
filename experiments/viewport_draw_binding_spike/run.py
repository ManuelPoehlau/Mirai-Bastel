"""Draw-binding spike window (§4 of the handoff). Throwaway — not a
Production entry point (Q6 stays open, see README "Open questions").

Loads `examples/meshes/head_basemesh.obj` (326V/324Q — see README "Mesh
path discrepancy" for why this is not the path named in the handoff),
builds a `Viewport(mesh, selection, store_type=SpikeGLStore)`, binds the
Production `OrbitCamera`, and draws RenderMesh's own data through ONE real
indexed VertexList (`SpikeGLStore`) — no parallel VBO.

Controls (debug only, no UX meaning — see handoff §4):
    LMB drag         Orbit
    Mouse wheel      Dolly
    M                Move N vertices by a fixed offset (core op + on_vertices_moved)
    E                Split one edge (core op + on_topology_changed)
    R                Reset scene
    Esc / Q          Quit
"""

from __future__ import annotations

import math

import _bootstrap  # noqa: F401 - sys.path setup, must run before src/ imports

import pyglet
from pyglet import gl
from pyglet.window import key as _key
from pyglet.window import mouse as _mouse

from core import Selection
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.scene_factory import build_core_scene_from_obj
from mirai.viewport.camera import OrbitCamera
from viewport.viewport import Viewport

from drawing import draw_frame
from spike_gl_store import SpikeGLStore

HEAD_OBJ = _bootstrap._REPO_ROOT / "examples" / "meshes" / "head_basemesh.obj"
N_MOVE_VERTICES = 5
MOVE_OFFSET = (0.0, 0.0, 0.05)


class SpikeWindow(pyglet.window.Window):
    def __init__(self) -> None:
        super().__init__(960, 720, caption="Draw Binding Spike (throwaway)", resizable=True)
        self._load_scene()
        self._drag_button = None
        self._frame_count = 0

    def _load_scene(self) -> None:
        scene = build_core_scene_from_obj(HEAD_OBJ)
        self.mesh = scene.mesh
        self.selection = Selection()
        self.vp = Viewport(self.mesh, self.selection, store_type=SpikeGLStore)

        self.camera = OrbitCamera()
        center, radius = mesh_center_and_radius(self.mesh)
        self.camera.frame_on_bounds(center, radius)
        self.vp.bind_camera(self.camera)
        self.vp.on_camera_changed(aspect=self.width / max(1, self.height))
        self.vp.sync()

        self.program = SpikeGLStore.program()
        self._all_vertex_ids = list(self.mesh.all_vertex_ids())

    # -- debug actions --------------------------------------------------------

    def _move_vertices(self) -> None:
        moved = set()
        for vid in self._all_vertex_ids[:N_MOVE_VERTICES]:
            px, py, pz = self.mesh.vertex_position(vid)
            self.mesh.set_vertex_position(
                vid, (px + MOVE_OFFSET[0], py + MOVE_OFFSET[1], pz + MOVE_OFFSET[2])
            )
            moved.add(vid)
        self.vp.on_vertices_moved(moved)
        self.vp.sync()

    def _split_edge(self) -> None:
        edge_id = next(iter(self.mesh.all_edge_ids()))
        self.mesh.split_edge(edge_id)
        self.vp.on_topology_changed()
        self.vp.sync()
        self._all_vertex_ids = list(self.mesh.all_vertex_ids())

    def _reset(self) -> None:
        self.close()
        self.__init__()

    # -- pyglet events ----------------------------------------------------------

    def on_resize(self, width: int, height: int) -> None:
        gl.glViewport(0, 0, max(1, width), max(1, height))
        self.vp.on_camera_changed(aspect=width / max(1, height))
        self.vp.sync()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        self._drag_button = button

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        self._drag_button = None

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int,
                      modifiers: int) -> None:  # noqa: PLR0913
        if self._drag_button == _mouse.LEFT:
            self.camera.orbit(dx * 0.005, dy * 0.005)
            self.vp.on_camera_changed()
            self.vp.sync()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        self.camera.dolly(0.9 if scroll_y > 0 else 1.1)
        self.vp.on_camera_changed()
        self.vp.sync()
        return pyglet.event.EVENT_HANDLED

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == _key.M:
            self._move_vertices()
        elif symbol == _key.E:
            self._split_edge()
        elif symbol == _key.R:
            self._reset()
        elif symbol in (_key.ESCAPE, _key.Q):
            self.close()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> None:
        self.clear()
        draw_frame(self.program, self.vp.render_mesh.store)
        self._frame_count += 1
        return pyglet.event.EVENT_HANDLED


def main() -> None:
    win = SpikeWindow()
    pyglet.app.run()


if __name__ == "__main__":
    main()
