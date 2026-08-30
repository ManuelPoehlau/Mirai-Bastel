"""Minimaler interaktiver V1-Viewport: Praxistest der Core-Pipeline.

WP-01A: Seit diesem Stand läuft Eingabe ausschließlich über die
Input-Mapping-Schicht (input_binding/default_bindings) statt über direkt
hart kodierte Tasten. Die Darstellung wird vom Display-State
(display_state: Shaded / Flat Shaded / Wireframe + Wireframe Overlay)
gesteuert; es entsteht bewusst kein Renderer-/Material-Stack.
"""

from __future__ import annotations

from pathlib import Path

import pyglet
from pyglet.gl import GL_DEPTH_TEST, GL_LINES, GL_POINTS, GL_TRIANGLES, GL_POLYGON_OFFSET_FILL, GL_POLYGON_OFFSET_LINE, glEnable, glDisable, glLineWidth, glPointSize, glPolygonOffset
from pyglet.graphics.shader import Shader, ShaderProgram
from pyglet.math import Mat4, Vec3
from pyglet.window import key, mouse

from mirai_bastel_core import SelectionMode

from . import commands as cmd
from . import vecmath as v
from .camera import OrbitCamera
from .default_bindings import build_default_bindings, load_keymap_overrides
from .demo_scene import build_cube_scene
from .display_state import DisplayMode, DisplayState
from .input_binding import GLOBAL_CONTEXT, Input
from .move_tool import MoveTool, resolve_selection_vertices, tool_for_command
from .picking import pick_face, pick_nearest_edge, pick_nearest_vertex
from .tool import ToolManager

_KEYMAP_PATH = Path(__file__).resolve().parent.parent / "keymap.json"

# Weltraum-Lichtrichtung für die minimale Lambert-Beleuchtung (normalisiert).
_LIGHT_DIR = (0.45, 0.40, 0.85)

_VERTEX_SHADER = """
#version 330 core
in vec3 position;
in vec3 normal;
uniform mat4 mvp;
out vec3 v_normal;
void main() {
    gl_Position = mvp * vec4(position, 1.0);
    v_normal = normal;
}
"""
_FRAGMENT_SHADER = """
#version 330 core
uniform vec3 color;
uniform vec3 light_dir;
in vec3 v_normal;
out vec4 fragColor;
void main() {
    vec3 n = normalize(v_normal);
    if (!gl_FrontFacing) {
        n = -n;
    }
    float light = 0.35 + 0.65 * max(dot(n, normalize(light_dir)), 0.0);
    fragColor = vec4(color * light, 1.0);
}
"""

# ---------------------------------------------------------------------------
# pyglet → Input-Adapter (einzige Stelle mit einer Fenster-/Event-Abhängigkeit;
# das Mapping selbst bleibt in input_binding.py vollständig pyglet-frei)
# ---------------------------------------------------------------------------

_MODIFIER_MASKS = (
    (key.MOD_CTRL, "ctrl"),
    (key.MOD_SHIFT, "shift"),
    (key.MOD_ALT, "alt"),
)

_SPECIAL_KEYS = {
    key.ESCAPE: "ESCAPE",
    key.SPACE: "SPACE",
    key.TAB: "TAB",
    key.ENTER: "ENTER",
    key.BACKSPACE: "BACKSPACE",
    key.DELETE: "DELETE",
    key.UP: "UP",
    key.DOWN: "DOWN",
    key.LEFT: "LEFT",
    key.RIGHT: "RIGHT",
    key.HOME: "HOME",
    key.END: "END",
    key.PAGEUP: "PAGEUP",
    key.PAGEDOWN: "PAGEDOWN",
}

_MOUSE_NAMES = {mouse.LEFT: "LEFT", mouse.MIDDLE: "MIDDLE", mouse.RIGHT: "RIGHT"}


def _modifier_set(modifiers):
    return frozenset(name for mask, name in _MODIFIER_MASKS if modifiers & mask)


def _key_input(symbol, modifiers) -> Input:
    if symbol in _SPECIAL_KEYS:
        value = _SPECIAL_KEYS[symbol]
    elif 32 <= symbol <= 126:
        ch = chr(symbol)
        value = ch.lower() if ch.isalpha() else ch
    else:
        value = f"KEY{symbol}"
    return Input("key", value, _modifier_set(modifiers))


def _mouse_input(button, modifiers) -> Input:
    return Input("mouse", _MOUSE_NAMES.get(button, str(button)), _modifier_set(modifiers))


def _wheel_input(scroll_y) -> Input:
    return Input("wheel", "UP" if scroll_y > 0 else "DOWN")


class ModelerWindow(pyglet.window.Window):
    def __init__(self) -> None:
        super().__init__(width=1024, height=768, caption="Mirai-Bastel V1 - Vertex Mode", resizable=True)
        self.scene = build_cube_scene(size=2.0)
        self.camera = OrbitCamera()
        self.display_state = DisplayState()
        self.bindings = load_keymap_overrides(build_default_bindings(), _KEYMAP_PATH)
        self.selection_mode = SelectionMode.VERTEX
        self._hovered_id = None
        vert = Shader(_VERTEX_SHADER, "vertex")
        frag = Shader(_FRAGMENT_SHADER, "fragment")
        self.program = ShaderProgram(vert, frag)
        # WP-02: Momentane Drag-Art der Maus (orbit/pan/"tool") und das
        # Active-Tool-System für interaktive Modeling-Tools (max. eines).
        self._drag_mode = None
        self._tool_manager = ToolManager()
        self._tweak_tool = False
        glEnable(GL_DEPTH_TEST)
        pyglet.clock.schedule_interval(lambda dt: None, 1 / 60.0)
        self._rebuild_geometry()

    def _set_selection_mode(self, mode):
        self._end_modeling_tool()
        self.selection_mode = mode
        self.scene.selection.mode = mode
        self.scene.selection.clear()
        self._hovered_id = None
        self.scene.selection.hovered = None
        self._update_caption(); self._rebuild_geometry()

    def _update_caption(self):
        names = {SelectionMode.VERTEX: "Vertex", SelectionMode.EDGE: "Edge", SelectionMode.FACE: "Face"}
        self.set_caption(
            f"Mirai-Bastel V1 - {names[self.selection_mode]} Mode | {self.display_state.label}"
        )

    def _binding_context(self) -> str:
        """Aktiver Binding-Kontext (siehe input_binding); Basis: global."""
        return GLOBAL_CONTEXT

    def _pick(self, x, y):
        if self.selection_mode == SelectionMode.VERTEX:
            return pick_nearest_vertex(self.camera, self.scene.mesh, x, y, self.width, self.height)
        if self.selection_mode == SelectionMode.EDGE:
            return pick_nearest_edge(self.camera, self.scene.mesh, x, y, self.width, self.height)
        if self.selection_mode == SelectionMode.FACE:
            return pick_face(self.camera, self.scene.mesh, x, y, self.width, self.height)
        return None

    def _compute_normals(self):
        """Face-Normalen (Flat Shading) und gemittelte Vertex-Normalen (Shaded).

        Minimal und rein aus der aktuellen Mesh-Geometrie abgeleitet — es
        entsteht bewusst kein Cache-/Material-Stack (WP-01A).
        """
        mesh = self.scene.mesh
        face_normals = {}
        for fid in mesh.all_face_ids():
            boundary = mesh.face_vertices(fid)
            if len(boundary) < 3:
                face_normals[fid] = (0.0, 0.0, 1.0)
                continue
            p0 = mesh.vertex_position(boundary[0])
            p1 = mesh.vertex_position(boundary[1])
            p2 = mesh.vertex_position(boundary[2])
            n = v.normalize(v.cross(v.sub(p1, p0), v.sub(p2, p0)))
            face_normals[fid] = n if v.length(n) > 1e-9 else (0.0, 0.0, 1.0)

        vertex_normals = {}
        for vid in mesh.all_vertex_ids():
            acc = (0.0, 0.0, 0.0)
            for fid, n in face_normals.items():
                if vid in mesh.face_vertices(fid):
                    acc = v.add(acc, n)
            vertex_normals[vid] = (
                v.normalize(acc) if v.length(acc) > 1e-9 else (0.0, 0.0, 1.0)
            )
        return face_normals, vertex_normals

    def _face_triangle_arrays(self, face_ids):
        """Positions- und Normalen-Arrays für die Faces (Fan-Triangulation).

        FLAT_SHADED nutzt pro Dreiecksecke die Face-Normale, SHADED die
        gemittelte Vertex-Normale. Im Wireframe-Modus (show_faces == False)
        wird diese Methode nicht aufgerufen.
        """
        mesh = self.scene.mesh
        flat = self.display_state.mode is DisplayMode.FLAT_SHADED
        positions, normals = [], []
        for fid in face_ids:
            boundary = mesh.face_vertices(fid)
            if len(boundary) < 3:
                continue
            p0 = mesh.vertex_position(boundary[0])
            for i in range(1, len(boundary) - 1):
                vids = (boundary[0], boundary[i], boundary[i + 1])
                points = (
                    p0,
                    mesh.vertex_position(boundary[i]),
                    mesh.vertex_position(boundary[i + 1]),
                )
                for vid, pos in zip(vids, points):
                    positions.extend(pos)
                    normals.extend(
                        self._face_normals[fid] if flat else self._vertex_normals[vid]
                    )
        return positions, normals

    @staticmethod
    def _default_normals(point_count: int):
        """Dummy-Normalen für Punkt-/Edge-Primitive (konstante Beleuchtung)."""
        return [0.0, 0.0, 1.0] * point_count

    def _rebuild_geometry(self):
        mesh = self.scene.mesh
        self._vertex_ids_ordered = list(mesh.all_vertex_ids())
        positions = [c for vid in self._vertex_ids_ordered for c in mesh.vertex_position(vid)]
        edge_positions = []
        for eid in mesh.all_edge_ids():
            va, vb = mesh.edge_vertices(eid); edge_positions.extend(mesh.vertex_position(va)); edge_positions.extend(mesh.vertex_position(vb))

        self._face_normals, self._vertex_normals = self._compute_normals()

        self._batch = pyglet.graphics.Batch()
        if self.display_state.show_faces:
            face_positions, face_normals = self._face_triangle_arrays(mesh.all_face_ids())
            self._face_list = self.program.vertex_list(len(face_positions)//3, GL_TRIANGLES, batch=self._batch, position=("f", face_positions), normal=("f", face_normals)) if face_positions else None
        else:
            self._face_list = None
        point_count = len(self._vertex_ids_ordered)
        self._point_list = self.program.vertex_list(point_count, GL_POINTS, batch=self._batch, position=("f", positions), normal=("f", self._default_normals(point_count))) if point_count else None
        edge_count = len(edge_positions)//3
        self._edge_list = self.program.vertex_list(edge_count, GL_LINES, batch=self._batch, position=("f", edge_positions), normal=("f", self._default_normals(edge_count))) if edge_count else None
        selected_vertex_positions = [c for vid in self.scene.selection.vertices for c in mesh.vertex_position(vid)]
        sv_count = len(selected_vertex_positions)//3
        self._selected_vertex_list = self.program.vertex_list(sv_count, GL_POINTS, batch=self._batch, position=("f", selected_vertex_positions), normal=("f", self._default_normals(sv_count))) if sv_count else None
        selected_edge_positions = []
        for eid in self.scene.selection.edges:
            va, vb = mesh.edge_vertices(eid); selected_edge_positions.extend(mesh.vertex_position(va)); selected_edge_positions.extend(mesh.vertex_position(vb))
        se_count = len(selected_edge_positions)//3
        self._selected_edge_list = self.program.vertex_list(se_count, GL_LINES, batch=self._batch, position=("f", selected_edge_positions), normal=("f", self._default_normals(se_count))) if se_count else None
        if self.display_state.show_faces:
            sf_positions, sf_normals = self._face_triangle_arrays(self.scene.selection.faces)
            sf_count = len(sf_positions)//3
            self._selected_face_list = self.program.vertex_list(sf_count, GL_TRIANGLES, batch=self._batch, position=("f", sf_positions), normal=("f", sf_normals)) if sf_count else None
        else:
            self._selected_face_list = None
        hover_vertex_positions = []
        hover_edge_positions = []
        hover_face_ids = []
        if self._hovered_id is not None and self._hovered_id not in self._selected_ids():
            if self.selection_mode == SelectionMode.VERTEX:
                hover_vertex_positions.extend(mesh.vertex_position(self._hovered_id))
            elif self.selection_mode == SelectionMode.EDGE:
                va, vb = mesh.edge_vertices(self._hovered_id); hover_edge_positions.extend(mesh.vertex_position(va)); hover_edge_positions.extend(mesh.vertex_position(vb))
            elif self.selection_mode == SelectionMode.FACE:
                hover_face_ids.append(self._hovered_id)
        hv_count = len(hover_vertex_positions)//3
        self._hover_vertex_list = self.program.vertex_list(hv_count, GL_POINTS, batch=self._batch, position=("f", hover_vertex_positions), normal=("f", self._default_normals(hv_count))) if hv_count else None
        he_count = len(hover_edge_positions)//3
        self._hover_edge_list = self.program.vertex_list(he_count, GL_LINES, batch=self._batch, position=("f", hover_edge_positions), normal=("f", self._default_normals(he_count))) if he_count else None
        if self.display_state.show_faces and hover_face_ids:
            hf_positions, hf_normals = self._face_triangle_arrays(hover_face_ids)
            hf_count = len(hf_positions)//3
            self._hover_face_list = self.program.vertex_list(hf_count, GL_TRIANGLES, batch=self._batch, position=("f", hf_positions), normal=("f", hf_normals)) if hf_count else None
        else:
            self._hover_face_list = None

    def _selected_ids(self):
        if self.selection_mode == SelectionMode.VERTEX: return self.scene.selection.vertices
        if self.selection_mode == SelectionMode.EDGE: return self.scene.selection.edges
        if self.selection_mode == SelectionMode.FACE: return self.scene.selection.faces
        return set()

    # ------------------------------------------------------------------
    # WP-02: Tool-Boundary (Active Tool / MoveTool / ToolManager)
    # ------------------------------------------------------------------

    def _end_modeling_tool(self) -> None:
        """Beendet ein aktives interaktives Modeling-Tool vollständig.

        Eine laufende Interaktion wird gecancelt (exakter Vorzustand, keine
        History), danach wird das Tool deaktiviert. Verhindert stale
        Drag-/Tool-Zustände (WP-02 §8, DoD).
        """
        if self._tool_manager.is_interacting:
            self._tool_manager.cancel()
        if self._tool_manager.active_tool is not None:
            self._tool_manager.deactivate()
        self._drag_mode = None
        self._tweak_tool = False

    def _activate_tool(self, tool_cls) -> None:
        """Aktiviert ein interaktives Tool über den ToolManager.

        Ist genau dieses Tool bereits aktiv, bleibt der (Modal-)Zustand
        bestehen; ein anderes aktives Tool wird sauber ersetzt.
        """
        if isinstance(self._tool_manager.active_tool, tool_cls):
            return
        self._tool_manager.activate(tool_cls(self.scene, self.camera))

    def _cancel_ongoing_tool(self) -> None:
        """Bricht eine laufende Tool-Interaktion ab (z. B. vor Orbit/Pan)."""
        if self._tool_manager.is_interacting:
            self._tool_manager.cancel()
            if self._tweak_tool:
                self._tool_manager.deactivate()
            self._tweak_tool = False
            self._drag_mode = None
            self._rebuild_geometry()

    def _start_move_interaction(self, vertex_ids) -> None:
        """Startet die Tweak-Move-Interaktion über den MoveTool (WP-02).

        Ohne bereits aktives Tool wird MoveTool implizit aktiviert und nach
        Commit/Cancel wieder deaktiviert (Tweak-UX). Ein zuvor explizit
        aktiviertes Move-Tool (Command.Move) bleibt modal bestehen.
        """
        if self._tool_manager.active_tool is None:
            self._tool_manager.activate(MoveTool(self.scene, self.camera))
            self._tweak_tool = True
        else:
            self._tweak_tool = False
        self._tool_manager.begin(vertex_ids=vertex_ids)
        self._drag_mode = "tool"

    def _finish_drag(self) -> None:
        """Räumt nach Commit/Cancel einer Drag-Interaktion auf."""
        if self._tweak_tool:
            self._tool_manager.deactivate()
            self._tweak_tool = False
        self._drag_mode = None
        self._rebuild_geometry()

    def _handle_cancel_command(self) -> None:
        """Esc: laufende Interaktion abbrechen bzw. aktives Tool deaktivieren."""
        if self._tool_manager.is_interacting:
            self._tool_manager.cancel()
            self._tweak_tool = False
            self._finish_drag()
        elif self._tool_manager.active_tool is not None:
            self._tool_manager.deactivate()
            self._tweak_tool = False
            self._drag_mode = None
            self._rebuild_geometry()

    def _draw_edge_highlight(self, vertex_list, color, width):
        """Zeichnet GL_LINES mit Polygon-Offset, damit überlagertes Wireframe/
        Hover/Selection nicht mit den Faces z-fightet (WP-01-BUGS_AND_TODOS).
        """
        if vertex_list is None:
            return
        glEnable(GL_POLYGON_OFFSET_LINE)
        glPolygonOffset(-1.0, -1.0)
        glLineWidth(width)
        self.program["color"] = color
        vertex_list.draw(GL_LINES)
        glLineWidth(1.0)
        glDisable(GL_POLYGON_OFFSET_LINE)

    def _draw_face_highlight(self, vertex_list, color):
        if vertex_list is None: return
        glEnable(GL_POLYGON_OFFSET_FILL); glPolygonOffset(-1.0, -1.0)
        self.program["color"] = color; vertex_list.draw(GL_TRIANGLES)
        glDisable(GL_POLYGON_OFFSET_FILL)

    def on_draw(self):
        self.clear()
        aspect = self.width / max(1, self.height)
        view = Mat4.look_at(Vec3(*self.camera.eye()), Vec3(*self.camera.target), Vec3(0,1,0))
        proj = Mat4.perspective_projection(aspect, z_near=self.camera.near, z_far=self.camera.far, fov=self.camera.fov_degrees)
        with self.program:
            self.program["mvp"] = proj @ view
            self.program["light_dir"] = _LIGHT_DIR
            if self.display_state.show_faces and self._face_list is not None:
                self.program["color"] = (0.62,0.64,0.70); self._face_list.draw(GL_TRIANGLES)
            if self.display_state.show_edges and self._edge_list is not None:
                self._draw_edge_highlight(self._edge_list, (0.75, 0.75, 0.8), 1.0)
            if self._point_list is not None:
                glPointSize(6.0); self.program["color"] = (0.9,0.9,0.95); self._point_list.draw(GL_POINTS)
            if self.display_state.show_faces:
                self._draw_face_highlight(self._hover_face_list, (0.78,0.80,0.88))
            if self._hover_edge_list is not None:
                self._draw_edge_highlight(self._hover_edge_list, (1.0, 0.70, 0.25), 4.0)
            if self._hover_vertex_list is not None:
                glPointSize(12.0); self.program["color"] = (1.0,0.70,0.25); self._hover_vertex_list.draw(GL_POINTS)
            if self.display_state.show_faces:
                self._draw_face_highlight(self._selected_face_list, (1.0,0.55,0.15))
            if self._selected_edge_list is not None:
                self._draw_edge_highlight(self._selected_edge_list, (1.0, 0.55, 0.15), 4.0)
            if self._selected_vertex_list is not None:
                glPointSize(12.0); self.program["color"] = (1.0,0.55,0.15); self._selected_vertex_list.draw(GL_POINTS)

    def on_mouse_motion(self, x, y, dx, dy):
        hovered = self._pick(x,y)
        if hovered != self._hovered_id:
            self._hovered_id = hovered; self.scene.selection.hovered = hovered; self._rebuild_geometry()

    def on_mouse_press(self, x, y, button, modifiers):
        command = self.bindings.command_for(_mouse_input(button, modifiers), self._binding_context())
        if command == cmd.SELECT:
            picked = self._pick(x, y)
            if picked is None:
                self._clear_selection()
            else:
                selected = set(self._selected_ids())
                if picked in selected:
                    selected.remove(picked)
                else:
                    selected.add(picked)
                self.scene.selection.set(selected); self._hovered_id = picked; self.scene.selection.hovered = picked
                if picked in self._selected_ids():
                    move_vertex_ids = resolve_selection_vertices(
                        self.scene.mesh, self.scene.selection, self.selection_mode
                    )
                    if move_vertex_ids:
                        self._start_move_interaction(move_vertex_ids)
                    else:
                        self._drag_mode = None; self._tweak_tool = False
                else:
                    self._drag_mode = None; self._tweak_tool = False
            self._rebuild_geometry()
        elif command == cmd.ORBIT:
            self._cancel_ongoing_tool()
            self._drag_mode = "orbit"
        elif command == cmd.PAN:
            self._cancel_ongoing_tool()
            self._drag_mode = "pan"

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self._drag_mode == "orbit":
            self.camera.orbit(-dx*0.005, -dy*0.005)
            self._refresh_hover(x, y)
        elif self._drag_mode == "pan":
            self.camera.pan(dx, dy, self.width, self.height)
            self._refresh_hover(x, y)
        elif self._drag_mode == "tool" and self._tool_manager.is_interacting:
            self._tool_manager.update(dx=dx, dy=dy, width=self.width, height=self.height)
            self._rebuild_geometry()

    def on_mouse_release(self, x, y, button, modifiers):
        if self._drag_mode == "tool" and self._tool_manager.is_interacting:
            self._tool_manager.commit()
            self._finish_drag()
        else:
            self._drag_mode = None

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        command = self.bindings.command_for(_wheel_input(scroll_y), self._binding_context())
        if command == cmd.ZOOM:
            self.camera.dolly(1.0 - scroll_y*0.1)
            self._refresh_hover(x, y)

    def on_key_press(self, symbol, modifiers):
        command = self.bindings.command_for(_key_input(symbol, modifiers), self._binding_context())
        if command is not None:
            self._dispatch_command(command)

    # ------------------------------------------------------------------
    # Command-Dispatch (Commands sind von konkreten Tasten entkoppelt)
    # ------------------------------------------------------------------

    def _dispatch_command(self, command) -> bool:
        """Führt ein aufgelöstes Command aus; True, wenn es behandelt wurde.

        Subklassen (TopologyWindow) erweitern diese Methode für eigene
        Commands und reichen Unbekanntes an die Basisklasse weiter.
        """
        set_mode = {
            cmd.SET_VERTEX_MODE: SelectionMode.VERTEX,
            cmd.SET_EDGE_MODE: SelectionMode.EDGE,
            cmd.SET_FACE_MODE: SelectionMode.FACE,
        }
        set_display = {
            cmd.SET_SHADED: DisplayMode.SHADED,
            cmd.SET_FLAT_SHADED: DisplayMode.FLAT_SHADED,
            cmd.SET_WIREFRAME: DisplayMode.WIREFRAME,
        }
        if command in set_mode:
            self._set_selection_mode(set_mode[command])
        elif command == cmd.UNDO:
            self._end_modeling_tool(); self.scene.history.undo(); self._rebuild_geometry()
        elif command == cmd.REDO:
            self._end_modeling_tool(); self.scene.history.redo(); self._rebuild_geometry()
        elif command == cmd.CANCEL:
            self._handle_cancel_command()
        elif command == cmd.CLEAR_SELECTION:
            self._clear_selection()
        elif command == cmd.CYCLE_DISPLAY_MODE:
            self.display_state.cycle(); self._rebuild_geometry(); self._update_caption()
        elif command == cmd.TOGGLE_WIREFRAME_OVERLAY:
            self.display_state.toggle_wireframe_overlay(); self._rebuild_geometry(); self._update_caption()
        elif command in set_display:
            self._set_display_mode(set_display[command])
        else:
            # Command → Tool-Routing (WP-02 §4.3): Modale Commands werden an
            # ihr Tool weitergegeben, nicht im Window-Event-Handler verbaut.
            tool_cls = tool_for_command(command)
            if tool_cls is not None:
                self._activate_tool(tool_cls)
            else:
                return False
        return True

    def _set_display_mode(self, mode) -> None:
        self.display_state.set_mode(mode)
        self._rebuild_geometry()
        self._update_caption()

    def _clear_selection(self) -> None:
        """Leert die komplette Selection (Command-ClearSelection).

        Entspricht dem bisherigen Klick-ins-Leere-Verhalten und wird
        zusaetzlich ueber ein Key-Binding erreichbar gemacht.
        """
        self._end_modeling_tool()
        self.scene.selection.clear()
        self._hovered_id = None
        self.scene.selection.hovered = None
        self._rebuild_geometry()

    def _refresh_hover(self, x, y) -> None:
        self._hovered_id = self._pick(x, y)
        self.scene.selection.hovered = self._hovered_id
        self._rebuild_geometry()


def main():
    ModelerWindow(); pyglet.app.run()


if __name__ == "__main__": main()
