"""Minimaler interaktiver V1-Viewport: Praxistest der Core-Pipeline

    Scene -> Mesh -> Selection -> Operation -> Commit -> History -> Undo/Redo

Bewusst NICHT enthalten (Scope-Absprache im Chat vor diesem Milestone):
- Rotate/Scale (der Core hat V1 nur MoveOperation - siehe operations/move.py)
- Edge-/Face-Selection-Interaktion (nur Vertex-Picking)
- Soft Selection, Snapping, Ortho-Ansicht, Achsen-Constraints/Gizmo
- interaktive Topologie-Edits (split/collapse/connect bleiben testgetrieben,
  siehe tests/test_core.py im Core-Projekt)

Steuerung:
- Linksklick auf einen Vertex: auswählen
- Links ziehen (auf einem gerade selektierten Vertex begonnen): verschieben
  (begin() beim Drag-Start, update() pro Mausbewegung, commit() beim Loslassen)
- Rechts ziehen: Kamera orbiten
- Mausrad: zoomen
- Strg+Z / Strg+Y: Undo / Redo
- Esc: laufende Move-Operation abbrechen (cancel())

Kein Dirty-Flag/Event-System zwischen Core und Rendering: es wird jeden
Frame neu aus dem Live-Mesh-Zustand gezeichnet (siehe operation.py-
Kommentar: das ist genau die Stelle, an der ein späteres System ein
Dirty-Flag setzen würde - für einen ersten Praxistest reicht "jeden Frame
neu lesen").
"""

from __future__ import annotations

import pyglet
from pyglet.gl import GL_DEPTH_TEST, GL_LINES, GL_POINTS, glEnable, glPointSize
from pyglet.graphics.shader import Shader, ShaderProgram
from pyglet.math import Mat4, Vec3
from pyglet.window import key, mouse

from mirai_bastel_core import MoveOperation, OperationContext

from .camera import OrbitCamera
from .demo_scene import build_cube_scene
from .picking import pick_nearest_vertex

_VERTEX_SHADER = """
#version 330 core
in vec3 position;
uniform mat4 mvp;
void main() {
    gl_Position = mvp * vec4(position, 1.0);
}
"""

_FRAGMENT_SHADER = """
#version 330 core
uniform vec3 color;
out vec4 fragColor;
void main() {
    fragColor = vec4(color, 1.0);
}
"""


class ModelerWindow(pyglet.window.Window):
    def __init__(self) -> None:
        super().__init__(width=1024, height=768, caption="Mirai-Bastel V1 - Viewport-Praxistest", resizable=True)
        self.scene = build_cube_scene(size=2.0)
        self.camera = OrbitCamera()

        vert = Shader(_VERTEX_SHADER, "vertex")
        frag = Shader(_FRAGMENT_SHADER, "fragment")
        self.program = ShaderProgram(vert, frag)

        self._drag_mode: str | None = None  # "orbit" | "move" | None
        self._active_move: MoveOperation | None = None

        glEnable(GL_DEPTH_TEST)
        pyglet.clock.schedule_interval(lambda dt: None, 1 / 60.0)

        self._rebuild_geometry()

    # ------------------------------------------------------------------
    # Geometrie aus dem Live-Mesh-Zustand
    # ------------------------------------------------------------------

    def _rebuild_geometry(self) -> None:
        mesh = self.scene.mesh
        self._vertex_ids_ordered = list(mesh.all_vertex_ids())
        index_of = {vid: i for i, vid in enumerate(self._vertex_ids_ordered)}

        positions: list[float] = []
        for vid in self._vertex_ids_ordered:
            positions.extend(mesh.vertex_position(vid))

        edge_indices: list[int] = []
        for eid in mesh.all_edge_ids():
            va, vb = mesh.edge_vertices(eid)
            edge_indices.extend([index_of[va], index_of[vb]])

        self._batch = pyglet.graphics.Batch()

        n_points = len(self._vertex_ids_ordered)
        self._point_list = self.program.vertex_list(
            n_points, GL_POINTS, batch=self._batch, position=("f", positions)
        )

        edge_positions: list[float] = []
        for idx in edge_indices:
            edge_positions.extend(positions[idx * 3 : idx * 3 + 3])
        n_edge_verts = len(edge_indices)
        self._edge_list = self.program.vertex_list(
            n_edge_verts, GL_LINES, batch=self._batch, position=("f", edge_positions)
        )

        selected_positions: list[float] = []
        for vid in self.scene.selection.vertices:
            selected_positions.extend(mesh.vertex_position(vid))
        self._highlight_list = None
        if selected_positions:
            self._highlight_list = self.program.vertex_list(
                len(selected_positions) // 3,
                GL_POINTS,
                batch=self._batch,
                position=("f", selected_positions),
            )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def on_draw(self) -> None:
        self.clear()
        aspect = self.width / max(1, self.height)
        eye = Vec3(*self.camera.eye())
        target = Vec3(*self.camera.target)
        view = Mat4.look_at(eye, target, Vec3(0, 1, 0))
        proj = Mat4.perspective_projection(
            aspect, z_near=self.camera.near, z_far=self.camera.far, fov=self.camera.fov_degrees
        )

        with self.program:
            self.program["mvp"] = proj @ view

            self.program["color"] = (0.75, 0.75, 0.8)
            self._edge_list.draw(GL_LINES)

            glPointSize(6.0)
            self.program["color"] = (0.9, 0.9, 0.95)
            self._point_list.draw(GL_POINTS)

            if self._highlight_list is not None:
                glPointSize(12.0)
                self.program["color"] = (1.0, 0.55, 0.15)
                self._highlight_list.draw(GL_POINTS)

    # ------------------------------------------------------------------
    # Eingabe -> Core-Aufrufe
    # ------------------------------------------------------------------

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        if button == mouse.LEFT:
            vid = pick_nearest_vertex(self.camera, self.scene.mesh, x, y, self.width, self.height)
            if vid is not None:
                self.scene.selection.set({vid})
                self._begin_move()
                self._drag_mode = "move"
            else:
                self.scene.selection.clear()
                self._drag_mode = None
            self._rebuild_geometry()
        elif button == mouse.RIGHT:
            self._drag_mode = "orbit"

    def on_mouse_drag(
        self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int
    ) -> None:
        if self._drag_mode == "orbit":
            self.camera.orbit(-dx * 0.005, -dy * 0.005)
        elif self._drag_mode == "move" and self._active_move is not None:
            vid = next(iter(self.scene.selection.vertices))
            point = self.scene.mesh.vertex_position(vid)
            world_delta = self.camera.screen_delta_to_world(point, dx, dy, self.width, self.height)
            self._active_move.update(delta=world_delta)
            self._rebuild_geometry()

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        if self._drag_mode == "move" and self._active_move is not None:
            self._active_move.commit()
            self._active_move = None
            self._rebuild_geometry()
        self._drag_mode = None

    def on_mouse_scroll(self, x: int, y: int, scroll_x: float, scroll_y: float) -> None:
        self.camera.dolly(1.0 - scroll_y * 0.1)

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == key.Z and modifiers & key.MOD_CTRL:
            self.scene.history.undo()
            self._rebuild_geometry()
        elif symbol == key.Y and modifiers & key.MOD_CTRL:
            self.scene.history.redo()
            self._rebuild_geometry()
        elif symbol == key.ESCAPE and self._active_move is not None:
            self._active_move.cancel()
            self._active_move = None
            self._rebuild_geometry()

    def _begin_move(self) -> None:
        context = OperationContext(
            target=self.scene.mesh,
            selection=self.scene.selection,
            history=self.scene.history,
        )
        self._active_move = MoveOperation(context)
        self._active_move.begin()


def main() -> None:
    ModelerWindow()
    pyglet.app.run()


if __name__ == "__main__":
    main()
