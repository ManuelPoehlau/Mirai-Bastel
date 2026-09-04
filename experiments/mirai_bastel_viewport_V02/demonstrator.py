"""Kleiner interaktiver Demonstrator für den Viewport V0.2 Incremental-Update-Proof.

Zeigt live, dass Camera-, Selection-, Material-, Geometry- und Topology-
Änderungen gezielt verarbeitet werden:

    Camera   -> nur Uniforms (kein Mesh-VBO-Zugriff)
    Selection-> nur Overlay-Punkt-VBO (kein Base-Mesh-VBO)
    Material -> nur Uniforms
    Geometry -> echtes Partial-Update auf demselben GPU-Buffer
                (AttributeBufferObject.set_region -> glBufferSubData)
    Topology -> struktureller VBO-Rebuild (erlaubt)

Die Instrumentierung (Zähler + Ressourcen-IDs) wird live im Fenster gezeigt.

Steuerung:
    LMB ziehen        Orbit
    Shift+LMB / MMB   Pan
    Mausrad           Zoom
    LMB-Klick         Vertex auswählen (CPU-Picking)
    M                 ausgewählten Vertex anheben (Geometry-Partial-Update)
    K                 Materialfarbe wechseln (nur Uniforms)
    T                 Topology vergrößern (struktureller Rebuild)
    R                 Zurücksetzen
    Esc / Q           Beenden
"""
from __future__ import annotations

import math

import pyglet
from pyglet import gl
from pyglet.graphics import shader

from camera import OrbitCamera
from material import MaterialState
from mesh import make_grid_triangles
from render_mesh import RenderMesh
from renderer import PygletStore
from selection import SelectionState

START_QUADS = 3

VERT_SRC = """
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

FRAG_SRC = """
#version 330 core
in vec4 frag_color;
out vec4 out_color;
void main() {
    out_color = frag_color;
}
"""


def _flatten(values, n: int) -> list[float]:
    out: list[float] = []
    for v in values:
        out.extend(v)
    return out


class V02Demonstrator(pyglet.window.Window):
    def __init__(self) -> None:
        super().__init__(960, 720, caption="Mirai-Bastel — Viewport V0.2 Proof",
                         resizable=True, vsync=True)
        self.camera = OrbitCamera(distance=8.0, yaw=math.radians(45), pitch=math.radians(30))
        self.selection = SelectionState()
        self.material = MaterialState()
        self.quads = START_QUADS
        self.mesh = make_grid_triangles(self.quads, self.quads)
        self.rm = RenderMesh(self.mesh, store_type=PygletStore)
        self.rm.bind_camera(self.camera)
        self.rm.bind_selection(self.selection)
        self.rm.bind_material(self.material)
        self.rm.aspect = self.width / self.height
        self.rm.build()

        self._drag_button = None
        self._drag_moved = 0.0
        self._picked_vertex: int | None = None

        self._build_program()

    def _build_program(self) -> None:
        vs = shader.Shader(VERT_SRC, "vertex")
        fs = shader.Shader(FRAG_SRC, "fragment")
        self.program = shader.ShaderProgram(vs, fs)
        self._build_mesh_vbo()
        self._hl_vlist = None
        self._refresh_highlight()
        self._status = pyglet.text.Label("", x=10, y=self.height - 16, anchor_y="top",
                                         font_name="Consolas", font_size=12,
                                         color=(220, 230, 240, 255), multiline=True, width=560)
        self._hint = pyglet.text.Label(
            "LMB ziehen=Orbit | Shift+LMB=Pan | Rad=Zoom | Klick=Vertex waehlen\n"
            "M=Move | K=Material | T=Topology | R=Reset | Esc=Ende",
            x=10, y=10, font_name="Consolas", font_size=11, color=(160, 180, 200, 255))

    # -- GPU-Aufbau ---------------------------------------------------------
    def _build_mesh_vbo(self) -> None:
        n = len(self.mesh.positions)
        positions = _flatten(self.mesh.positions, 3)
        normals = _flatten(self.rm.derived.vertex_normals, 3)
        indices = _flatten(self.mesh.triangles, 3)
        colors = [1.0, 1.0, 1.0] * n
        self.vlist = self.program.vertex_list_indexed(
            n, gl.GL_TRIANGLES, indices,
            position=("f", positions), normal=("f", normals), color=("f", colors))

    def _refresh_highlight(self) -> None:
        if self._hl_vlist is not None:
            self._hl_vlist.delete()
            self._hl_vlist = None
        sel = sorted(self.selection.selected_vertices)
        if not sel:
            return
        positions = _flatten([self.mesh.positions[v] for v in sel], 3)
        colors = list(self.material.highlight_color[:3]) * len(sel)
        self._hl_vlist = self.program.vertex_list(
            len(sel), gl.GL_POINTS, position=("f", positions), color=("f", colors))

    # -- Update-Kanal-Aktionen (jede Kategorie separat) ---------------------
    def _apply_camera(self) -> None:
        self.rm.apply_camera(aspect=self.width / self.height)
        self.rm.sync()

    def _apply_material(self) -> None:
        self.rm.apply_material()
        self.rm.sync()

    def _apply_selection(self) -> None:
        self.rm.apply_selection()
        self.rm.sync()
        self._refresh_highlight()

    def _apply_vertex_move(self, vid: int, new_pos) -> None:
        """Geometry-Partial-Update: ändert NUR den betroffenen GPU-Bereich."""
        _, vert_ids = self.rm.derived.affected_neighborhood(self.rm.mesh, {vid})
        self.rm.move_vertex(vid, new_pos)
        self.rm.sync()
        pos_buf = self.vlist.domain.attrib_name_buffers["position"]
        nrm_buf = self.vlist.domain.attrib_name_buffers["normal"]
        pos_buf.set_region(vid, 1, list(self.rm.mesh.positions[vid]))
        for v in vert_ids:
            nrm_buf.set_region(v, 1, list(self.rm.derived.vertex_normals[v]))
        self._refresh_highlight()

    def _apply_topology(self) -> None:
        self.quads += 1
        self.mesh = make_grid_triangles(self.quads, self.quads)
        self.rm.apply_topology(self.mesh)
        self.rm.sync()
        self._build_mesh_vbo()
        self._refresh_highlight()

    def _reset(self) -> None:
        self.close()
        self.__init__()

    # -- Picking (CPU, projektionsbasiert) -----------------------------------
    def _pick_vertex(self, sx: float, sy: float) -> int | None:
        best: int | None = None
        best_d = 1e18
        threshold = 12.0
        for i, p in enumerate(self.mesh.positions):
            proj = self.camera.project_to_screen(p, self.width, self.height)
            if proj is None:
                continue
            px, py = proj
            d = math.hypot(px - sx, py - sy)
            if d < best_d:
                best_d = d
                best = i
        return best if best_d <= threshold else None

    # -- pyglet-Events --------------------------------------------------------
    def on_resize(self, width: int, height: int) -> None:
        gl.glViewport(0, 0, max(1, width), max(1, height))
        self.rm.apply_camera(aspect=width / height)
        self.rm.sync()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        self._drag_button = button
        self._drag_moved = 0.0

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int,
                      modifiers: int) -> None:  # noqa: PLR0913
        self._drag_moved += abs(dx) + abs(dy)
        from pyglet.window import mouse as _m
        if self._drag_button == _m.LEFT and not (modifiers & _m.MOD_SHIFT):
            self.camera.orbit(dx * 0.005, dy * 0.005)
            self._apply_camera()
        elif self._drag_button == _m.MIDDLE or (
                self._drag_button == _m.LEFT and modifiers & _m.MOD_SHIFT):
            wpp = 2.0 * self.camera.distance * math.tan(
                math.radians(self.camera.fov_degrees) / 2.0) / self.height
            self.camera.pan((self.camera.target[0] - dx * wpp,
                             self.camera.target[1] - dy * wpp,
                             self.camera.target[2]))
            self._apply_camera()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        from pyglet.window import mouse as _m
        if button == _m.LEFT and self._drag_moved < 5.0:
            picked = self._pick_vertex(x, y)
            if picked is not None:
                if modifiers & _m.MOD_SHIFT:
                    self.selection.toggle(picked)
                else:
                    self.selection.set({picked})
                self._picked_vertex = picked
            else:
                self.selection.clear()
                self._picked_vertex = None
            self._apply_selection()
        self._drag_button = None
        return pyglet.event.EVENT_HANDLED

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        self.camera.dolly(0.9 if scroll_y > 0 else 1.1)
        self._apply_camera()
        return pyglet.event.EVENT_HANDLED

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        from pyglet.window import key as _k
        if symbol == _k.M:
            if self._picked_vertex is None:
                self._picked_vertex = 0
            v = self._picked_vertex
            px, py, pz = self.mesh.positions[v]
            self._apply_vertex_move(v, (px, py, pz + 0.35))
        elif symbol == _k.K:
            r = (self.material.base_color[0] + 0.4) % 1.0
            self.material.set_base_color((r, 0.7, 0.9, 1.0))
            self._apply_material()
        elif symbol == _k.T:
            self._apply_topology()
        elif symbol == _k.R:
            self._reset()
        elif symbol in (_k.ESCAPE, _k.Q):
            self.close()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> None:
        self.clear()
        self.program.use()
        self.program["u_view"] = self.camera.build_view_matrix()
        self.program["u_proj"] = self.camera.build_projection_matrix(self.width / self.height)
        self.program["u_base_color"] = list(self.material.base_color)
        inv = 1.0 / math.sqrt(3.0)
        self.program["u_light_dir"] = (inv, inv, inv)
        if self.vlist is not None:
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glEnable(gl.GL_CULL_FACE)
            gl.glCullFace(gl.GL_BACK)
            self.vlist.draw(gl.GL_TRIANGLES)
            gl.glDisable(gl.GL_CULL_FACE)
        if self._hl_vlist is not None:
            gl.glPointSize(10.0)
            gl.glDepthMask(gl.GL_FALSE)
            self._hl_vlist.draw(gl.GL_POINTS)
            gl.glPointSize(1.0)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisable(gl.GL_DEPTH_TEST)
        self._draw_status()
        self._hint.draw()
        return pyglet.event.EVENT_HANDLED

    def _draw_status(self) -> None:
        c = self.rm.stats.counters
        names = ("mesh_rebuilds", "structural_rebuilds", "geometry_uploads",
                 "partial_updates", "bounds_recalculations",
                 "camera_updates", "selection_updates", "material_updates",
                 "vertex_updates", "topology_updates",
                 "gpu_resource_creations", "gpu_resource_destroys")
        lines = ["VIEWPORT V0.2 — LEBENDIGE INSTRUMENTIERUNG", ""]
        for n in names:
            lines.append(f"{n:24s} = {c.get(n, 0)}")
        ids = self.rm.store.resource_ids()
        lines.append("")
        lines.append("GPU-Ressourcen-IDs:")
        for name in sorted(ids):
            lines.append(f"  {name:20s} = {ids[name]}")
        self._status.text = "\n".join(lines)
        self._status.draw()


def main() -> None:
    demo = V02Demonstrator()
    pyglet.app.run()


if __name__ == "__main__":
    main()