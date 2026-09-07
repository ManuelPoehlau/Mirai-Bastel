"""Integrations-Viewport: pyglet-Fenster, das alle Lab-Objekte darstellt.

Reiner Harness-Code des Integration Labs — KEIN Production-Viewport. Er
nutzt die V0.2-Render-Klassik (RenderMesh + PygletStore + ShaderProgram mit
gleichen Shader-Quellen wie der V0.2-Demonstrator) und verbindet sie über
`CoreRenderBinding` mit den `src.core`-Objekten der Lab-Szene.

Interaktion (Ziel: End-to-End-Test aus der Task):
    LMB ziehen        Orbit          (Camera-Kanal: nur Uniforms)
    Shift+LMB / MMB   Pan
    Mausrad           Zoom
    LMB-Klick         Vertex auswählen (nur Selection-/Highlight-Kanal)
    M                 selektierten Vertex bewegen
                      → ZUERST src.core.Mesh, dann Render-Partial-Update
    1 / 2             Objekt auswählen (Cube <-> Head Basemesh) + Frame
    R                 Kamera auf aktives Objekt rahmen
    S                 Report/Statistik (aktueller Stand)
    Esc / Q           Beenden
"""

from __future__ import annotations

import math
import time

import pyglet
from pyglet import gl
from pyglet.graphics import shader
from pyglet.window import key as _key

from _paths import ensure_paths  # noqa: E402

ensure_paths()

from adapters.core_to_render import CoreRenderBinding, flatten_render_mesh  # noqa: E402
from adapters.obj_to_core import frame_camera_on_bounds  # noqa: E402
from adapters.picking import pick_vertex  # noqa: E402
from lab_camera import LabOrbitCamera  # noqa: E402
from scene.scene import LabObject, LabScene  # noqa: E402

from experiments.mirai_bastel_viewport_V02.renderer import PygletStore  # noqa: E402

# Shader-Quellen identisch zum V0.2-Demonstrator (Wiederverwendung).
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


def _flatten(values, width: int) -> list[float]:
    out: list[float] = []
    for v in values:
        out.extend(v)
    return out


class _ObjectView:
    """Render-Ansicht eines Lab-Objekts: Binding + GPU-Buffer + Overlay."""

    def __init__(self, name: str, binding: CoreRenderBinding) -> None:
        self.name = name
        self.binding = binding
        self.vlist = None
        self.hl_vlist = None

    @property
    def rm(self):
        return self.binding.render


class IntegrationLabWindow(pyglet.window.Window):
    def __init__(self, lab_scene: LabScene) -> None:
        # pyglet 2.1 auf Windows erstellt ohne explizite Config keinen Depth-Puffer.
        # Das fuehrt zu unsichtbaren Flächen trotz glEnable(GL_DEPTH_TEST).
        # Dieser Fix ist additiv im Integration-Lab - V0.2 bleibt unberührt.
        from pyglet import gl
        config = gl.Config(depth_size=24, stencil_size=8)
        super().__init__(
            1280, 800,
            caption="Mirai-Bastel — Integration Lab / Test Studio",
            resizable=True, vsync=True,
            config=config,
        )
        self.lab = lab_scene
        self.camera = LabOrbitCamera(
            distance=8.0, yaw=math.radians(45.0), pitch=math.radians(28.0)
        )
        self.program = shader.ShaderProgram(
            shader.Shader(_VERT_SRC, "vertex"), shader.Shader(_FRAG_SRC, "fragment")
        )

        self.objects: list[_ObjectView] = []
        self._obj_by_name = {}
        for obj in self.lab.objects:
            self._add_object(obj)
        self._focus_camera(self.lab.active.name)

        self._drag_button = None
        self._drag_moved = 0.0
        self._picked_vertex = None

        self._frame_t0 = time.perf_counter()
        self._fps_ema = 0.0
        self._fps = 0.0

        self._build_labels()

    # -- Aufbau --------------------------------------------------------------
    def _add_object(self, obj: LabObject) -> None:
        binding = CoreRenderBinding(
            obj.scene.mesh, store_type=PygletStore, camera=self.camera
        )
        binding.render.aspect = self.width / self.height
        binding.material.set_base_color(obj.base_color)
        view = _ObjectView(obj.name, binding)
        self._build_mesh_vbo(view)
        self.objects.append(view)
        self._obj_by_name[obj.name] = obj

    def _build_mesh_vbo(self, view: _ObjectView) -> None:
        buf = flatten_render_mesh(view.binding)
        colors = [1.0, 1.0, 1.0] * buf["n"]
        view.vlist = self.program.vertex_list_indexed(
            buf["n"], gl.GL_TRIANGLES, buf["indices"],
            position=("f", buf["positions"]),
            normal=("f", buf["normals"]),
            color=("f", colors),
        )

    @staticmethod
    def _highlight_color(name: str) -> tuple[float, float, float]:
        if name == "Cube":
            return (1.0, 0.35, 0.35)
        return (1.0, 0.55, 0.25)

    def _refresh_highlight(self, view: _ObjectView) -> None:
        if view.hl_vlist is not None:
            view.hl_vlist.delete()
            view.hl_vlist = None
        sel = sorted(view.binding.selection.selected_vertices)
        if not sel:
            return
        positions = _flatten([view.binding.render_mesh.positions[v] for v in sel], 3)
        rgb = self._highlight_color(view.name)
        view.hl_vlist = self.program.vertex_list(
            len(sel), gl.GL_POINTS,
            position=("f", positions), color=("f", list(rgb) * len(sel)),
        )

    def _build_labels(self) -> None:
        self._status = pyglet.text.Label(
            "", x=10, y=self.height - 16, anchor_y="top",
            font_name="Consolas", font_size=12, color=(220, 230, 240, 255),
            multiline=True, width=620,
        )
        self._hint = pyglet.text.Label(
            "LMB ziehen=Orbit  Shift+LMB/MMB=Pan  Rad=Zoom  Klick=Vertex\n"
            "M=Move(+Y)  1/2=Objekt+Frame  R=Frame  S=Report  Esc=Ende",
            x=10, y=6, font_name="Consolas", font_size=11,
            color=(160, 180, 200, 255),
        )

    def active_view(self) -> _ObjectView:
        return self.objects[self.lab.active_index]

    def _focus_camera(self, name: str) -> None:
        obj = self.lab.select_by_name(name)
        frame_camera_on_bounds(self.camera, obj.mesh, margin=1.4)
        self._push_camera()

    def _push_camera(self) -> None:
        if self.height == 0:
            return  # pyglet 2.1 Windows: transientes on_resize mit height=0 beim Start
        aspect = self.width / self.height
        for view in self.objects:
            view.binding.apply_camera(aspect)

    # -- Events --------------------------------------------------------------
    def on_resize(self, width: int, height: int) -> None:
        gl.glViewport(0, 0, max(1, width), max(1, height))
        if height == 0:
            return pyglet.event.EVENT_HANDLED  # pyglet 2.1: transientes Resize während Init
        self._push_camera()
        return pyglet.event.EVENT_HANDLED
        self._push_camera()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        self._drag_button = button
        self._drag_moved = 0.0

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int,
                      modifiers: int) -> None:  # noqa: PLR0913
        self._drag_moved += abs(dx) + abs(dy)
        from pyglet.window import mouse as _m
        if self._drag_button == _m.LEFT and not (modifiers & _key.MOD_SHIFT):
            self.camera.orbit(dx * 0.005, dy * 0.005)
            self._push_camera()
        elif self._drag_button == _m.MIDDLE or (
                self._drag_button == _m.LEFT and modifiers & _key.MOD_SHIFT):
            self.camera.pan_px(dx, dy, self.width, self.height)
            self._push_camera()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        from pyglet.window import mouse as _m
        if button == _m.LEFT and self._drag_moved < 5.0:
            self._handle_click_selection(x, y, modifiers)
        self._drag_button = None
        return pyglet.event.EVENT_HANDLED

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        self.camera.dolly(0.9 if scroll_y > 0 else 1.1)
        self._push_camera()
        return pyglet.event.EVENT_HANDLED

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        from pyglet.window import key as _k
        if symbol == _k._1:
            self._focus_camera(self.lab.objects[0].name)
        elif symbol == _k._2:
            self._focus_camera(self.lab.objects[1].name)
        elif symbol in (_k.F, _k.R):
            self._focus_camera(self.lab.active.name)
        elif symbol == _k.M:
            self._move_picked_vertex()
        elif symbol == _k.S:
            self._report()
        elif symbol in (_k.ESCAPE, _k.Q):
            self.close()
        return pyglet.event.EVENT_HANDLED

    # -- Selection / Move (Kern des End-to-End-Tests) -------------------------
    def _handle_click_selection(self, x: int, y: int, modifiers: int) -> None:
        from pyglet.window import mouse as _m
        active = self.lab.active
        view = self.active_view()
        picked = pick_vertex(
            self.camera, active.mesh, view.binding.index_map,
            x, y, self.width, self.height,
        )
        if picked is not None:
            index = view.binding.index_map.index(picked)
            if modifiers & _key.MOD_SHIFT:
                if view.binding.selection.is_selected(index):
                    active.scene.selection.vertices.discard(picked)
                    view.binding.selection.selected_vertices.discard(index)
                else:
                    active.scene.selection.vertices.add(picked)
                    view.binding.selection.add(index)
            else:
                active.scene.selection.set({picked})
                view.binding.selection.set({index})
            self._picked_vertex = picked
        else:
            active.scene.selection.clear()
            view.binding.selection.clear()
            self._picked_vertex = None
        view.binding.render.apply_selection()
        view.binding.render.sync()
        self._refresh_highlight(view)

    def _move_picked_vertex(self) -> None:
        """Move: ZUERST src.core.Mesh verändern, dann Render-Partial-Update."""
        view = self.active_view()
        if self._picked_vertex is None:
            return
        vid = self._picked_vertex
        if not view.binding.core_mesh.is_valid_vertex(vid):
            self._picked_vertex = None
            return
        index = view.binding.index_map.index(vid)
        _, vert_ids = view.rm.derived.affected_neighborhood(
            view.rm.mesh, {index}
        )
        view.binding.move_vertex_by(vid, (0.0, 0.35, 0.0))
        pos_buf = view.vlist.domain.attrib_name_buffers["position"]
        nrm_buf = view.vlist.domain.attrib_name_buffers["normal"]
        pos_buf.set_region(index, 1, list(view.binding.render_mesh.positions[index]))
        for v in vert_ids:
            nrm_buf.set_region(v, 1, list(view.rm.derived.vertex_normals[v]))
        self._refresh_highlight(view)
# -- Zeichnung ------------------------------------------------------------
    def on_draw(self) -> None:
        now = time.perf_counter()
        dt = now - self._frame_t0
        self._frame_t0 = now
        if dt > 0.0:
            inst = 1.0 / dt
            self._fps_ema = self._fps_ema * 0.9 + inst * 0.1
            self._fps = self._fps_ema

        self.clear()
        self.program.use()
        self.program["u_view"] = self.camera.build_view_matrix()
        self.program["u_proj"] = self.camera.build_projection_matrix(
            self.width / self.height
        )
        inv = 1.0 / math.sqrt(3.0)
        self.program["u_light_dir"] = (inv, inv, inv)
        for view in self.objects:
            obj = self._obj_by_name[view.name]
            self.program["u_base_color"] = list(obj.base_color)
            if view.vlist is not None:
                gl.glEnable(gl.GL_DEPTH_TEST)
                # Bewusst KEIN Back-Face-Culling: Die OBJ-/Cube-Face-Windings
                # sind nicht einheitlich CCW; Culling würde Teile (oder alles)
                # ausblenden (V1-Viewport rendert ebenfalls ohne Culling).
                view.vlist.draw(gl.GL_TRIANGLES)
            if view.hl_vlist is not None:
                gl.glPointSize(10.0)
                gl.glDepthMask(gl.GL_FALSE)
                view.hl_vlist.draw(gl.GL_POINTS)
                gl.glPointSize(1.0)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glDisable(gl.GL_DEPTH_TEST)
        self._draw_status()
        self._hint.draw()
        return pyglet.event.EVENT_HANDLED

    def _draw_status(self) -> None:
        view = self.active_view()
        counters = dict(view.rm.stats.counters)
        ids = view.rm.store.resource_ids()
        names = (
            "mesh_rebuilds", "structural_rebuilds", "partial_updates",
            "vertex_updates", "geometry_uploads", "bounds_recalculations",
            "camera_updates", "selection_updates", "topology_updates",
            "gpu_resource_creations",
        )
        markers = [
            f"{'[' if i == self.lab.active_index else ' '} {o} "
            f"{']' if i == self.lab.active_index else ' '}"
            for i, o in enumerate(self.lab.names())
        ]
        lines = [
            f"INTEGRATION LAB — LIVE-INSTRUMENTIERUNG (aktiv: {view.name})",
            f"FPS ~ {self._fps:5.1f} | Vertices "
            f"{len(view.binding.render_mesh.positions)} | Triangles "
            f"{len(view.binding.render_mesh.triangles)}",
            "",
        ]
        for n in names:
            lines.append(f"{n:24s} = {counters.get(n, 0)}")
        lines.append("")
        lines.append("Ressourcen-IDs:")
        for name in sorted(ids):
            lines.append(f"  {name:20s} = {ids[name]}")
        lines.append("")
        lines.append("Objekte: " + " | ".join(markers))
        self._status.text = "\n".join(lines)
        self._status.draw()

    def _report(self) -> None:
        view = self.active_view()
        print("=" * 70)
        print(f"INTEGRATION LAB REPORT — {view.name}")
        print("=" * 70)
        print(f"FPS ~ {self._fps:.1f}")
        print(f"Vertex: {len(view.binding.render_mesh.positions)}  "
              f"Triangles: {len(view.binding.render_mesh.triangles)}")
        print("Counter:", dict(view.rm.stats.counters))
        print("Resources:", view.rm.store.resource_ids())


def main() -> None:
    from scene.scene_objects import build_lab_scene
    lab = build_lab_scene()
    IntegrationLabWindow(lab)
    pyglet.app.run()