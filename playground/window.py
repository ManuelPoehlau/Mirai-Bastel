"""PlaygroundWindow — pyglet-Fenster für das Artist Playground.

Analoges Muster zum Integration Lab (`lab_viewport.py`), aber ohne
feste Szene, ohne Picking-Logik (WP-AP-03) und ohne Selection-Handling.

Steuerung:
    LMB ziehen      Orbit
    MMB ziehen      Pan
    Mausrad         Zoom
    C               load_cube (Szene wechseln)
    H               load_head (Szene wechseln)
    Q / ESC         Fenster schließen

Shader: Gleiche GLSL-Quellen wie das Integration Lab (Phong-Shading,
ohne Back-Face-Culling, weil OBJ-Windings nicht garantiert CCW sind).
"""

from __future__ import annotations

import math

import pyglet
from pyglet import gl
from pyglet.graphics import shader
from pyglet.window import key as _key
from pyglet.window import mouse as _mouse

from playground._paths import ensure_paths

ensure_paths()

from playground.app import PlaygroundApp  # noqa: E402
from playground.hud import PlaygroundHUD  # noqa: E402
from playground.renderer import PlaygroundRenderer  # noqa: E402

# Shader-Quellen (identisch zum Integration Lab, Wiederverwendung aus WP-IL-01).
_VERT_SRC = """
#version 330 core
in vec3 position;
in vec3 normal;
in vec3 color;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec4 u_base_color;
uniform vec3 u_light_dir;
out vec4 frag_color;
void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    float ndl = max(dot(normal, u_light_dir), 0.0);
    vec3 shaded = color * mix(vec3(0.35), vec3(1.0), ndl);
    frag_color = vec4(shaded * u_base_color.rgb, 1.0);
}
"""

_FRAG_SRC = """
#version 330 core
in vec4 frag_color;
out vec4 out_color;
void main() {
    out_color = frag_color;
}
"""

_DEFAULT_BASE_COLOR = (0.6, 0.7, 0.9, 1.0)
_LIGHT_DIR_INV = 1.0 / math.sqrt(3.0)


class PlaygroundWindow(pyglet.window.Window):
    """Leichtgewichtiges pyglet-Fenster für das Artist Playground.

    Orchestriert PlaygroundApp, PlaygroundRenderer und PlaygroundHUD.
    Eigener Shader + VertexList für den Draw (analog Integration Lab,
    da Production Viewport.render() noch kein GL-Backend hat).
    """

    def __init__(self, app: PlaygroundApp) -> None:
        super().__init__(
            1280, 800,
            caption="Mirai-Bastel — Artist Playground [WP-AP-01]",
            resizable=True,
            vsync=True,
        )
        self.app = app
        self.program = shader.ShaderProgram(
            shader.Shader(_VERT_SRC, "vertex"),
            shader.Shader(_FRAG_SRC, "fragment"),
        )

        # Renderer-Adapter (hält Viewport-Notifikations-API)
        if app.viewport is not None:
            self._renderer = PlaygroundRenderer(app.viewport)
        else:
            self._renderer = None

        # Eigene VBO-Daten für den Draw-Pass
        self._vlist = None
        self._rebuild_vbo()

        # HUD
        self._hud = PlaygroundHUD(x=10, y_bottom=10, width=self.width - 20)
        self._hud.update_layout(self.width, self.height)
        self._update_hud()

        # Maus-Drag-State
        self._drag_button = None
        self._drag_moved = 0.0

        self.activate()

    # -- VBO-Aufbau -----------------------------------------------------------

    def _rebuild_vbo(self) -> None:
        """VBO aus dem aktuellen Mesh neu aufbauen."""
        if self._vlist is not None:
            self._vlist.delete()
            self._vlist = None

        if self.app.viewport is None:
            return

        # Renderer-Adapter neu binden (nach Mesh-Wechsel)
        self._renderer = PlaygroundRenderer(self.app.viewport)

        mesh = self.app.scene.mesh
        from viewport.derived import triangulate_face  # noqa: PLC0415

        vertex_ids = list(mesh.all_vertex_ids())
        id_to_index = {vid: i for i, vid in enumerate(vertex_ids)}

        positions: list[float] = []
        for vid in vertex_ids:
            positions.extend(mesh.vertex_position(vid))

        # Normalen aus dem RenderMesh (Production-Ableitung)
        render_mesh = self.app.viewport.render_mesh
        derived = render_mesh.derived
        normals: list[float] = []
        for vid in vertex_ids:
            n = derived.vertex_normals.get(vid, (0.0, 1.0, 0.0))
            normals.extend(n)

        colors: list[float] = [1.0, 1.0, 1.0] * len(vertex_ids)

        indices: list[int] = []
        for fid in mesh.all_face_ids():
            boundary = mesh.face_vertices(fid)
            for a, b, c in triangulate_face(boundary):
                indices.extend([id_to_index[a], id_to_index[b], id_to_index[c]])

        if not indices:
            return

        self._vlist = self.program.vertex_list_indexed(
            len(vertex_ids),
            gl.GL_TRIANGLES,
            indices,
            position=("f", positions),
            normal=("f", normals),
            color=("f", colors),
        )

    # -- HUD-Update -----------------------------------------------------------

    def _update_hud(self) -> None:
        cam = self.app.camera
        self._hud.update_camera(cam.yaw, cam.pitch, cam.distance)
        mesh = self.app.scene.mesh
        v_count = len(list(mesh.all_vertex_ids()))
        e_count = len(list(mesh.all_edge_ids()))
        f_count = len(list(mesh.all_face_ids()))
        self._hud.update_mesh(v_count, e_count, f_count)
        self._hud.update_experiment(self.app.active_experiment)

    # -- Kamera-Push ----------------------------------------------------------

    def _push_camera(self) -> None:
        """Kamera-Zustand in den Production-Viewport übertragen."""
        if self.height == 0:
            return
        aspect = self.width / self.height
        if self._renderer is not None:
            self._renderer.notify_camera_changed(aspect=aspect)
            self._renderer.sync()
        self._update_hud()

    # -- Events ---------------------------------------------------------------

    def on_resize(self, width: int, height: int) -> None:
        if height == 0:
            return pyglet.event.EVENT_HANDLED
        self._hud.update_layout(width, height)
        self._push_camera()
        pyglet.clock.schedule_once(lambda dt: self.flip(), 0)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        self._drag_button = button
        self._drag_moved = 0.0
        self.activate()

    def on_mouse_drag(
        self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int
    ) -> None:
        self._drag_moved += abs(dx) + abs(dy)
        is_pan = self._drag_button == _mouse.MIDDLE or (
            self._drag_button in (_mouse.LEFT, _mouse.RIGHT)
            and modifiers & _key.MOD_SHIFT
        )
        if is_pan:
            self.app.camera.pan(dx, dy, self.width, self.height)
        elif self._drag_button in (_mouse.LEFT, _mouse.RIGHT):
            self.app.camera.orbit(dx * 0.005, dy * 0.005)
        self._push_camera()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        self._drag_button = None
        return pyglet.event.EVENT_HANDLED

    def on_mouse_scroll(
        self, x: int, y: int, scroll_x: int, scroll_y: int
    ) -> None:
        self.app.camera.dolly(0.9 if scroll_y > 0 else 1.1)
        self._push_camera()
        return pyglet.event.EVENT_HANDLED

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == _key.C:
            self.app.load_cube()
            self._rebuild_vbo()
            self._push_camera()
        elif symbol == _key.H:
            self.app.load_head()
            self._rebuild_vbo()
            self._push_camera()
        elif symbol in (_key.Q, _key.ESCAPE):
            self.close()
        return pyglet.event.EVENT_HANDLED

    # -- Draw -----------------------------------------------------------------

    def on_draw(self) -> None:
        if self.height == 0:
            return pyglet.event.EVENT_HANDLED

        gl.glClearColor(0.08, 0.08, 0.12, 1.0)
        self.clear()

        if self._vlist is not None:
            self.program.use()
            self.program["u_view"] = self.app.camera.build_view_matrix()
            self.program["u_proj"] = self.app.camera.build_projection_matrix(
                self.width / self.height
            )
            self.program["u_light_dir"] = (
                _LIGHT_DIR_INV,
                _LIGHT_DIR_INV,
                _LIGHT_DIR_INV,
            )
            self.program["u_base_color"] = list(_DEFAULT_BASE_COLOR)
            gl.glEnable(gl.GL_DEPTH_TEST)
            self._vlist.draw(gl.GL_TRIANGLES)

        # Experiment-Draw (vor HUD)
        self.app.active_experiment.draw()

        # HUD: Depth-Test deaktivieren, Shader stoppen (Constraint aus WP-IL-01)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        self.program.stop()
        self._hud.draw()

        return pyglet.event.EVENT_HANDLED
