"""Minimaler interaktiver V1-Viewport: Praxistest der Core-Pipeline."""

from __future__ import annotations

import pyglet
from pyglet.gl import GL_DEPTH_TEST, GL_LINES, GL_POINTS, GL_TRIANGLES, GL_POLYGON_OFFSET_FILL, glEnable, glDisable, glLineWidth, glPointSize, glPolygonOffset
from pyglet.graphics.shader import Shader, ShaderProgram
from pyglet.math import Mat4, Vec3
from pyglet.window import key, mouse

from mirai_bastel_core import MoveOperation, OperationContext, SelectionMode

from .camera import OrbitCamera
from .demo_scene import build_cube_scene
from .picking import pick_face, pick_nearest_edge, pick_nearest_vertex

_VERTEX_SHADER = """
#version 330 core
in vec3 position;
uniform mat4 mvp;
void main() { gl_Position = mvp * vec4(position, 1.0); }
"""
_FRAGMENT_SHADER = """
#version 330 core
uniform vec3 color;
out vec4 fragColor;
void main() { fragColor = vec4(color, 1.0); }
"""


class ModelerWindow(pyglet.window.Window):
    def __init__(self) -> None:
        super().__init__(width=1024, height=768, caption="Mirai-Bastel V1 - Vertex Mode", resizable=True)
        self.scene = build_cube_scene(size=2.0)
        self.camera = OrbitCamera()
        self.selection_mode = SelectionMode.VERTEX
        self._hovered_id = None

        vert = Shader(_VERTEX_SHADER, "vertex")
        frag = Shader(_FRAGMENT_SHADER, "fragment")
        self.program = ShaderProgram(vert, frag)
        self._drag_mode = None
        self._active_move = None
        glEnable(GL_DEPTH_TEST)
        pyglet.clock.schedule_interval(lambda dt: None, 1 / 60.0)
        self._rebuild_geometry()

    def _set_selection_mode(self, mode):
        if self._active_move is not None:
            self._active_move.cancel(); self._active_move = None
        self._drag_mode = None
        self.selection_mode = mode
        self.scene.selection.mode = mode
        self.scene.selection.clear()
        self._hovered_id = None
        self.scene.selection.hovered = None
        self._update_caption(); self._rebuild_geometry()

    def _update_caption(self):
        names = {SelectionMode.VERTEX: "Vertex", SelectionMode.EDGE: "Edge", SelectionMode.FACE: "Face"}
        self.set_caption(f"Mirai-Bastel V1 - {names[self.selection_mode]} Mode")

    def _pick(self, x, y):
        if self.selection_mode == SelectionMode.VERTEX:
            return pick_nearest_vertex(self.camera, self.scene.mesh, x, y, self.width, self.height)
        if self.selection_mode == SelectionMode.EDGE:
            return pick_nearest_edge(self.camera, self.scene.mesh, x, y, self.width, self.height)
        if self.selection_mode == SelectionMode.FACE:
            return pick_face(self.camera, self.scene.mesh, x, y, self.width, self.height)
        return None

    def _rebuild_geometry(self):
        mesh = self.scene.mesh
        self._vertex_ids_ordered = list(mesh.all_vertex_ids())
        positions = [c for vid in self._vertex_ids_ordered for c in mesh.vertex_position(vid)]
        edge_positions = []
        for eid in mesh.all_edge_ids():
            va, vb = mesh.edge_vertices(eid)
            edge_positions.extend(mesh.vertex_position(va)); edge_positions.extend(mesh.vertex_position(vb))

        def face_positions_for(face_ids):
            result = []
            for fid in face_ids:
                boundary = mesh.face_vertices(fid)
                if len(boundary) < 3: continue
                p0 = mesh.vertex_position(boundary[0])
                for i in range(1, len(boundary) - 1):
                    p1 = mesh.vertex_position(boundary[i]); p2 = mesh.vertex_position(boundary[i + 1])
                    result.extend((*p0, *p1, *p2))
            return result

        self._batch = pyglet.graphics.Batch()
        face_positions = face_positions_for(mesh.all_face_ids())
        self._face_list = self.program.vertex_list(len(face_positions)//3, GL_TRIANGLES, batch=self._batch, position=("f", face_positions)) if face_positions else None
        self._point_list = self.program.vertex_list(len(self._vertex_ids_ordered), GL_POINTS, batch=self._batch, position=("f", positions))
        self._edge_list = self.program.vertex_list(len(edge_positions)//3, GL_LINES, batch=self._batch, position=("f", edge_positions))

        selected_vertex_positions = [c for vid in self.scene.selection.vertices for c in mesh.vertex_position(vid)]
        self._selected_vertex_list = self.program.vertex_list(len(selected_vertex_positions)//3, GL_POINTS, batch=self._batch, position=("f", selected_vertex_positions)) if selected_vertex_positions else None
        selected_edge_positions = []
        for eid in self.scene.selection.edges:
            va, vb = mesh.edge_vertices(eid); selected_edge_positions.extend(mesh.vertex_position(va)); selected_edge_positions.extend(mesh.vertex_position(vb))
        self._selected_edge_list = self.program.vertex_list(len(selected_edge_positions)//3, GL_LINES, batch=self._batch, position=("f", selected_edge_positions)) if selected_edge_positions else None
        selected_face_positions = face_positions_for(self.scene.selection.faces)
        self._selected_face_list = self.program.vertex_list(len(selected_face_positions)//3, GL_TRIANGLES, batch=self._batch, position=("f", selected_face_positions)) if selected_face_positions else None

        hover_vertex_positions = []; hover_edge_positions = []; hover_face_positions = []
        # A selected element wins visually over hover while the cursor remains on it.
        hovered_is_selected = self._hovered_id is not None and (
            (self.selection_mode == SelectionMode.VERTEX and self._hovered_id in self.scene.selection.vertices) or
            (self.selection_mode == SelectionMode.EDGE and self._hovered_id in self.scene.selection.edges) or
            (self.selection_mode == SelectionMode.FACE and self._hovered_id in self.scene.selection.faces)
        )
        if self._hovered_id is not None and not hovered_is_selected:
            if self.selection_mode == SelectionMode.VERTEX:
                hover_vertex_positions.extend(mesh.vertex_position(self._hovered_id))
            elif self.selection_mode == SelectionMode.EDGE:
                va, vb = mesh.edge_vertices(self._hovered_id); hover_edge_positions.extend(mesh.vertex_position(va)); hover_edge_positions.extend(mesh.vertex_position(vb))
            elif self.selection_mode == SelectionMode.FACE:
                hover_face_positions = face_positions_for([self._hovered_id])
        self._hover_vertex_list = self.program.vertex_list(len(hover_vertex_positions)//3, GL_POINTS, batch=self._batch, position=("f", hover_vertex_positions)) if hover_vertex_positions else None
        self._hover_edge_list = self.program.vertex_list(len(hover_edge_positions)//3, GL_LINES, batch=self._batch, position=("f", hover_edge_positions)) if hover_edge_positions else None
        self._hover_face_list = self.program.vertex_list(len(hover_face_positions)//3, GL_TRIANGLES, batch=self._batch, position=("f", hover_face_positions)) if hover_face_positions else None

    def _draw_face_highlight(self, vertex_list, color):
        if vertex_list is None: return
        glEnable(GL_POLYGON_OFFSET_FILL)
        glPolygonOffset(-1.0, -1.0)
        self.program["color"] = color
        vertex_list.draw(GL_TRIANGLES)
        glDisable(GL_POLYGON_OFFSET_FILL)

    def on_draw(self):
        self.clear()
        aspect = self.width / max(1, self.height)
        view = Mat4.look_at(Vec3(*self.camera.eye()), Vec3(*self.camera.target), Vec3(0,1,0))
        proj = Mat4.perspective_projection(aspect, z_near=self.camera.near, z_far=self.camera.far, fov=self.camera.fov_degrees)
        with self.program:
            self.program["mvp"] = proj @ view
            if self._face_list is not None:
                self.program["color"] = (0.62,0.64,0.70); self._face_list.draw(GL_TRIANGLES)
            self.program["color"] = (0.75,0.75,0.8); self._edge_list.draw(GL_LINES)
            glPointSize(6.0); self.program["color"] = (0.9,0.9,0.95); self._point_list.draw(GL_POINTS)
            self._draw_face_highlight(self._hover_face_list, (0.78,0.80,0.88))
            if self._hover_edge_list is not None:
                glLineWidth(4.0); self.program["color"] = (1.0,0.70,0.25); self._hover_edge_list.draw(GL_LINES); glLineWidth(1.0)
            if self._hover_vertex_list is not None:
                glPointSize(12.0); self.program["color"] = (1.0,0.70,0.25); self._hover_vertex_list.draw(GL_POINTS)
            self._draw_face_highlight(self._selected_face_list, (1.0,0.55,0.15))
            if self._selected_edge_list is not None:
                glLineWidth(4.0); self.program["color"] = (1.0,0.55,0.15); self._selected_edge_list.draw(GL_LINES); glLineWidth(1.0)
            if self._selected_vertex_list is not None:
                glPointSize(12.0); self.program["color"] = (1.0,0.55,0.15); self._selected_vertex_list.draw(GL_POINTS)

    def on_mouse_motion(self, x, y, dx, dy):
        hovered = self._pick(x,y)
        if hovered != self._hovered_id:
            self._hovered_id = hovered; self.scene.selection.hovered = hovered; self._rebuild_geometry()

    def on_mouse_press(self, x, y, button, modifiers):
        if button == mouse.LEFT:
            picked = self._pick(x,y)
            if picked is None:
                self.scene.selection.clear(); self._hovered_id = None; self.scene.selection.hovered = None; self._drag_mode = None
            else:
                self.scene.selection.set({picked})
                self._hovered_id = picked
                self.scene.selection.hovered = picked
                if self.selection_mode == SelectionMode.VERTEX: self._begin_move(); self._drag_mode = "move"
                else: self._drag_mode = None
            self._rebuild_geometry()
        elif button == mouse.RIGHT: self._drag_mode = "orbit"

    def on_mouse_drag(self, x,y,dx,dy,buttons,modifiers):
        if self._drag_mode == "orbit":
            self.camera.orbit(-dx*0.005,-dy*0.005); self._hovered_id = self._pick(x,y); self.scene.selection.hovered = self._hovered_id; self._rebuild_geometry()
        elif self._drag_mode == "move" and self._active_move is not None:
            vid = next(iter(self.scene.selection.vertices)); point = self.scene.mesh.vertex_position(vid)
            self._active_move.update(delta=self.camera.screen_delta_to_world(point,dx,dy,self.width,self.height)); self._rebuild_geometry()

    def on_mouse_release(self,x,y,button,modifiers):
        if self._drag_mode == "move" and self._active_move is not None:
            self._active_move.commit(); self._active_move=None; self._rebuild_geometry()
        self._drag_mode=None

    def on_mouse_scroll(self,x,y,scroll_x,scroll_y):
        self.camera.dolly(1.0-scroll_y*0.1); self._hovered_id=self._pick(x,y); self.scene.selection.hovered=self._hovered_id; self._rebuild_geometry()

    def on_key_press(self,symbol,modifiers):
        if symbol in (key.V,key._1): self._set_selection_mode(SelectionMode.VERTEX)
        elif symbol in (key.E,key._2): self._set_selection_mode(SelectionMode.EDGE)
        elif symbol in (key.F,key._3): self._set_selection_mode(SelectionMode.FACE)
        elif symbol == key.Z and modifiers & key.MOD_CTRL: self.scene.history.undo(); self._rebuild_geometry()
        elif symbol == key.Y and modifiers & key.MOD_CTRL: self.scene.history.redo(); self._rebuild_geometry()
        elif symbol == key.ESCAPE and self._active_move is not None: self._active_move.cancel(); self._active_move=None; self._rebuild_geometry()

    def _begin_move(self):
        context = OperationContext(target=self.scene.mesh, selection=self.scene.selection, history=self.scene.history)
        self._active_move = MoveOperation(context); self._active_move.begin()


def main():
    ModelerWindow(); pyglet.app.run()


if __name__ == "__main__": main()
