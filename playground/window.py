"""PlaygroundWindow — pyglet-Fenster für das Artist Playground.

Steuerung:
    LMB ziehen      Orbit
    MMB ziehen      Pan
    Mausrad         Zoom
    LMB click       Face Select (AP-03 Phase 1)
    X (gedrückt)    Move (gedrückt halten + ziehen, AP-04)
    R (gedrückt)    Rotate (gedrückt halten + ziehen, AP-04)
    S (gedrückt)    Scale (gedrückt halten + ziehen, AP-04)
    C               load_cube (Szene wechseln)
    H               load_head (Szene wechseln)
    D               Display-Mode cyclen (Shaded → Flat → Wireframe)
    Z               Wireframe-Overlay togglen
    V               Vertex-Darstellung togglen
    M               Selection-Modus cyclen (Replace/Modifier/Toggle)
    Q / ESC         Fenster schließen

Shader:
    _FACE_VERT/_FACE_FRAG    — Phong mit u_use_flat-Uniform (Smooth/Flat).
    _OVERLAY_VERT/_OVERLAY_FRAG — Flat-Color für Edges, Vertices, Selection.

VBO-Struktur:
    _vlist_faces      — GL_TRIANGLES, smooth_normal + flat_normal
    _vlist_edges      — GL_LINES
    _vlist_verts      — GL_POINTS
    _vlist_selection  — GL_TRIANGLES, selektierte Faces (rebuilt on selection change)
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

from mirai.viewport.display import DisplayMode  # noqa: E402
from playground.selector import SelectMode  # noqa: E402
from playground.transformer import (  # noqa: E402
    begin_transform,
    cancel_transform,
    commit_transform,
    update_transform,
)
from playground.app import PlaygroundApp  # noqa: E402
from playground.hud import PlaygroundHUD  # noqa: E402
from playground.input_map import PlaygroundInputMap  # noqa: E402
from playground.renderer import PlaygroundRenderer  # noqa: E402
from playground.selector import CLICK_THRESHOLD, dispatch_face_click  # noqa: E402
from playground.transformer import create_tool_for_type  # noqa: E402
from playground.vbo_builder import (  # noqa: E402
    build_edge_data,
    build_face_data,
    build_selection_data,
    build_vertex_data,
)

# -- Shader-Quellen ----------------------------------------------------------

_FACE_VERT = """
#version 330 core
in vec3 position;
in vec3 smooth_normal;
in vec3 flat_normal;
in vec3 color;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec4 u_base_color;
uniform vec3 u_light_dir;
uniform int u_use_flat;
out vec4 frag_color;
void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    vec3 n = u_use_flat != 0 ? flat_normal : smooth_normal;
    float ndl = max(dot(n, u_light_dir), 0.0);
    vec3 shaded = color * mix(vec3(0.35), vec3(1.0), ndl);
    frag_color = vec4(shaded * u_base_color.rgb, 1.0);
}
"""

_FACE_FRAG = """
#version 330 core
in vec4 frag_color;
out vec4 out_color;
void main() {
    out_color = frag_color;
}
"""

_OVERLAY_VERT = """
#version 330 core
in vec3 position;
uniform mat4 u_view;
uniform mat4 u_proj;
out vec4 frag_color;
uniform vec4 u_color;
void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    frag_color = u_color;
}
"""

_OVERLAY_FRAG = """
#version 330 core
in vec4 frag_color;
out vec4 out_color;
void main() {
    out_color = frag_color;
}
"""

# -- Render-Konstanten -------------------------------------------------------

_DEFAULT_BASE_COLOR = (0.6, 0.7, 0.9, 1.0)
_EDGE_COLOR = (0.15, 0.15, 0.15, 1.0)
_VERTEX_COLOR = (1.0, 0.75, 0.1, 1.0)
_SELECTION_COLOR = (0.95, 0.45, 0.1, 1.0)
_VERTEX_POINT_SIZE = 4.0
_LIGHT_DIR_INV = 1.0 / math.sqrt(3.0)


class PlaygroundWindow(pyglet.window.Window):
    """Leichtgewichtiges pyglet-Fenster für das Artist Playground."""

    def __init__(
        self,
        app: PlaygroundApp,
        input_map: PlaygroundInputMap | None = None,
    ) -> None:
        super().__init__(
            1280, 800,
            caption="Mirai-Bastel — Artist Playground [WP-AP-03]",
            resizable=True,
            vsync=True,
        )
        self.app = app
        self.input_map = input_map if input_map is not None else PlaygroundInputMap()

        self._face_program = shader.ShaderProgram(
            shader.Shader(_FACE_VERT, "vertex"),
            shader.Shader(_FACE_FRAG, "fragment"),
        )
        self._overlay_program = shader.ShaderProgram(
            shader.Shader(_OVERLAY_VERT, "vertex"),
            shader.Shader(_OVERLAY_FRAG, "fragment"),
        )

        if app.viewport is not None:
            self._renderer = PlaygroundRenderer(app.viewport)
        else:
            self._renderer = None

        self._vlist_faces = None
        self._vlist_edges = None
        self._vlist_verts = None
        self._vlist_selection = None
        self._rebuild_vbo()

        self._hud = PlaygroundHUD(x=10, y_bottom=10, width=self.width - 20)
        self._hud.update_layout(self.width, self.height)
        self._update_hud()

        self._drag_button = None
        self._drag_moved = 0.0

        # Transform-State (AP-04)
        self._transform_key_down = None  # 'x', 'r', 's' oder None
        self._transform_started = False

        self.activate()

    # -- VBO-Aufbau -----------------------------------------------------------

    def _rebuild_vbo(self) -> None:
        """Alle Mesh-VBOs (Faces, Edges, Vertices) neu bauen. Selection-VBO separat."""
        for vlist in (self._vlist_faces, self._vlist_edges, self._vlist_verts,
                      self._vlist_selection):
            if vlist is not None:
                vlist.delete()
        self._vlist_faces = None
        self._vlist_edges = None
        self._vlist_verts = None
        self._vlist_selection = None

        if self.app.viewport is None:
            return

        if self.app.viewport is not None:
            self._renderer = PlaygroundRenderer(self.app.viewport)

        mesh = self.app.viewport.render_mesh.mesh
        derived = self.app.viewport.render_mesh.derived

        face_positions, smooth_normals, flat_normals, colors = build_face_data(mesh, derived)
        n_face_verts = len(face_positions) // 3
        if n_face_verts > 0:
            self._vlist_faces = self._face_program.vertex_list(
                n_face_verts,
                gl.GL_TRIANGLES,
                position=("f", face_positions),
                smooth_normal=("f", smooth_normals),
                flat_normal=("f", flat_normals),
                color=("f", colors),
            )

        edge_positions = build_edge_data(mesh)
        n_edge_verts = len(edge_positions) // 3
        if n_edge_verts > 0:
            self._vlist_edges = self._overlay_program.vertex_list(
                n_edge_verts,
                gl.GL_LINES,
                position=("f", edge_positions),
            )

        vert_positions = build_vertex_data(mesh)
        n_verts = len(vert_positions) // 3
        if n_verts > 0:
            self._vlist_verts = self._overlay_program.vertex_list(
                n_verts,
                gl.GL_POINTS,
                position=("f", vert_positions),
            )

    def _rebuild_selection_vbo(self) -> None:
        """Selection-VBO aus den aktuell selektierten Faces neu bauen.

        Wird nach jedem Click aufgerufen (nur selektierte Faces, kleines VBO).
        Triggert keinen Mesh-Rebuild.
        """
        if self._vlist_selection is not None:
            self._vlist_selection.delete()
            self._vlist_selection = None

        if self.app.viewport is None:
            return

        mesh = self.app.viewport.render_mesh.mesh
        selection = self.app.scene.selection
        if not selection.faces:
            return

        positions = build_selection_data(mesh, selection.faces)
        n = len(positions) // 3
        if n > 0:
            self._vlist_selection = self._overlay_program.vertex_list(
                n,
                gl.GL_TRIANGLES,
                position=("f", positions),
            )

    # -- HUD-Update -----------------------------------------------------------

    def _update_hud(self) -> None:
        cam = self.app.camera
        self._hud.update_camera(cam.yaw, cam.pitch, cam.distance)
        mesh = self.app.viewport.render_mesh.mesh if self.app.viewport else None
        if mesh is not None:
            v_count = len(list(mesh.all_vertex_ids()))
            e_count = len(list(mesh.all_edge_ids()))
            f_count = len(list(mesh.all_face_ids()))
            self._hud.update_mesh(v_count, e_count, f_count)
        self._hud.update_experiment(self.app.active_experiment)
        display_label = self.app.display_state.label
        if self.app.show_vertices:
            display_label += " + V"
        self._hud.update_display(display_label)
        sel = self.app.scene.selection if self.app.viewport is not None else None
        n_faces = len(sel.faces) if sel is not None else 0
        mode_label = self.app.select_mode.name.capitalize()
        self._hud.update_selection(n_faces, mode_label)

    # -- Kamera-Push ----------------------------------------------------------

    def _push_camera(self) -> None:
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

        # Transform-Handling (AP-04): wenn X/R/S gedrückt und Tool aktiv
        if (
            self._transform_key_down is not None
            and self.app.active_tool is not None
            and self.app.viewport is not None
        ):
            if not self._transform_started:
                # Erste Drag-Bewegung: Transform starten
                success = begin_transform(
                    self.app.active_tool,
                    self.app.scene,
                    self.app.camera,
                    self.app.scene.selection,
                )
                if success:
                    self._transform_started = True

            if self._transform_started:
                # Update während Drag
                update_transform(
                    self.app.active_tool,
                    float(dx),
                    float(-dy),  # Y umkehren (pyglet y nach oben)
                    self.width,
                    self.height,
                    self.app.camera,
                )
                self._push_camera()
            return pyglet.event.EVENT_HANDLED

        # Normale Kamera-Bedienung
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
        was_click = self._drag_moved < CLICK_THRESHOLD
        self._drag_button = None
        if (
            was_click
            and button == self.input_map.select_button
            and self.app.viewport is not None
        ):
            mesh = self.app.viewport.render_mesh.mesh
            changed = dispatch_face_click(
                self.app.camera, mesh, self.app.scene.selection,
                x, y, self.width, self.height,
                modifiers, self.input_map, self.app.select_mode,
            )
            if changed:
                self._rebuild_selection_vbo()
                self._update_hud()
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
        elif symbol == self.input_map.display_cycle:
            self.app.display_state.cycle()
            self._update_hud()
        elif symbol == self.input_map.wire_overlay:
            self.app.display_state.toggle_wireframe_overlay()
            self._update_hud()
        elif symbol == self.input_map.show_vertices:
            self.app.show_vertices = not self.app.show_vertices
            self._update_hud()
        elif symbol == _key.M:
            # Cycle SelectMode: REPLACE → MODIFIER → TOGGLE → REPLACE
            modes = [SelectMode.REPLACE, SelectMode.MODIFIER, SelectMode.TOGGLE]
            current_idx = modes.index(self.app.select_mode)
            self.app.select_mode = modes[(current_idx + 1) % len(modes)]
            self._update_hud()
        elif symbol == _key.X:
            # X: Move Tool aktivieren
            self._transform_key_down = 'x'
            self.app.active_tool = create_tool_for_type('move')
        elif symbol == _key.R:
            # R: Rotate Tool aktivieren
            self._transform_key_down = 'r'
            self.app.active_tool = create_tool_for_type('rotate')
        elif symbol == _key.S:
            # S: Scale Tool aktivieren
            self._transform_key_down = 's'
            self.app.active_tool = create_tool_for_type('scale')
        elif symbol in (_key.Q, _key.ESCAPE):
            self.close()
        return pyglet.event.EVENT_HANDLED

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        """Handle key release — commit/cancel transform wenn Tool aktiv."""
        if symbol == _key.ESCAPE:
            # ESC während Transform: cancel (unabhängig von _transform_key_down)
            if self._transform_started and self.app.active_tool is not None:
                cancel_transform(self.app.active_tool)
                self._transform_started = False
                self._transform_key_down = None
                self.app.active_tool = None
                self._push_camera()
        elif symbol == _key.X or symbol == _key.R or symbol == _key.S:
            # Transform-Hotkey losgelassen
            if self._transform_key_down is not None and self.app.active_tool is not None:
                if self._transform_started:
                    # Commit the transform — ein History-Eintrag
                    commit_transform(self.app.active_tool)
                    self._transform_started = False
                self._transform_key_down = None
                self.app.active_tool = None
                self._push_camera()
        return pyglet.event.EVENT_HANDLED

    # -- Draw -----------------------------------------------------------------

    def on_draw(self) -> None:
        if self.height == 0:
            return pyglet.event.EVENT_HANDLED

        gl.glClearColor(0.08, 0.08, 0.12, 1.0)
        self.clear()

        display_state = self.app.display_state
        view = self.app.camera.build_view_matrix()
        proj = self.app.camera.build_projection_matrix(self.width / self.height)

        # -- Face-Pass (Shaded / Flat Shaded / Wireframe ohne Faces) ----------
        if display_state.show_faces and self._vlist_faces is not None:
            self._face_program.use()
            self._face_program["u_view"] = view
            self._face_program["u_proj"] = proj
            self._face_program["u_light_dir"] = (
                _LIGHT_DIR_INV, _LIGHT_DIR_INV, _LIGHT_DIR_INV,
            )
            self._face_program["u_base_color"] = list(_DEFAULT_BASE_COLOR)
            self._face_program["u_use_flat"] = (
                1 if display_state.mode is DisplayMode.FLAT_SHADED else 0
            )
            gl.glEnable(gl.GL_DEPTH_TEST)
            # Polygon-Offset pusht Faces leicht nach hinten → Wireframe-Overlay
            # ohne Z-Fighting (nur wenn Edges zusätzlich gezeichnet werden).
            if display_state.show_edges:
                gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
                gl.glPolygonOffset(1.0, 1.0)
            self._vlist_faces.draw(gl.GL_TRIANGLES)
            if display_state.show_edges:
                gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)
            self._face_program.stop()

        # -- Selection-Pass (selektierte Faces, GL_LEQUAL — over face geometry) -
        if self._vlist_selection is not None:
            self._overlay_program.use()
            self._overlay_program["u_view"] = view
            self._overlay_program["u_proj"] = proj
            self._overlay_program["u_color"] = list(_SELECTION_COLOR)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LEQUAL)
            self._vlist_selection.draw(gl.GL_TRIANGLES)
            gl.glDepthFunc(gl.GL_LESS)
            self._overlay_program.stop()

        # -- Edge-Pass (Wireframe / Wireframe-Overlay) ------------------------
        if display_state.show_edges and self._vlist_edges is not None:
            self._overlay_program.use()
            self._overlay_program["u_view"] = view
            self._overlay_program["u_proj"] = proj
            self._overlay_program["u_color"] = list(_EDGE_COLOR)
            gl.glEnable(gl.GL_DEPTH_TEST)
            self._vlist_edges.draw(gl.GL_LINES)
            self._overlay_program.stop()

        # -- Vertex-Pass (GL_POINTS, immer vor HUD) ---------------------------
        if self.app.show_vertices and self._vlist_verts is not None:
            self._overlay_program.use()
            self._overlay_program["u_view"] = view
            self._overlay_program["u_proj"] = proj
            self._overlay_program["u_color"] = list(_VERTEX_COLOR)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glPointSize(_VERTEX_POINT_SIZE)
            self._vlist_verts.draw(gl.GL_POINTS)
            self._overlay_program.stop()

        # -- Experiment-Hook --------------------------------------------------
        self.app.active_experiment.draw()

        # -- HUD (program.stop() vor Label.draw() — Constraint aus WP-IL-01) --
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        self._hud.draw()

        return pyglet.event.EVENT_HANDLED
