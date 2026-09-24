"""Minimaler Draw-Pfad des Labs: Shader + Vertex-Lists (braucht GL-Kontext).

Shader-Quellen und Draw-Reihenfolge adaptiert (kopiert, nicht importiert —
Handoff Slice 2 §2.1) aus `playground/window.py` (`_FACE_VERT`/`_FACE_FRAG`,
`_OVERLAY_VERT`/`_OVERLAY_FRAG`, Render-Konstanten, `on_draw`), Stand
`47f821b`. Abweichungen: Face-Shader ohne `flat_normal`/`color`/`u_use_flat`
(nur Shaded); selektierter Vertex als eigener, größerer Punkt-Pass.

Voller Rebuild bei jeder Änderung (Handoff §2.3) — kein Patching.

Slice 3: Symmetrie-Overlays (Ebenen-Umriss, Seam/ohne Partner/mehrdeutig)
hängen an Mesh + Definition und werden mit `rebuild_mesh` neu gebaut; die
gespiegelte Vorschau hängt an der Auswahl und kommt mit `rebuild_highlight`.
Farblegende: README.
"""

from __future__ import annotations

import math

from pyglet import gl
from pyglet.graphics import shader

from core import Mesh

from . import lab_draw_data
from .lab_symmetry import SymmetryReport

_FACE_VERT = """
#version 330 core
in vec3 position;
in vec3 normal;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec4 u_base_color;
uniform vec3 u_light_dir;
out vec4 frag_color;
void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    float ndl = max(dot(normal, u_light_dir), 0.0);
    vec3 shaded = mix(vec3(0.35), vec3(1.0), ndl);
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
uniform vec4 u_color;
out vec4 frag_color;
void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    frag_color = u_color;
}
"""

_OVERLAY_FRAG = _FACE_FRAG

BACKGROUND_COLOR = (0.08, 0.08, 0.12, 1.0)
BASE_COLOR = (0.6, 0.7, 0.9, 1.0)
EDGE_COLOR = (0.15, 0.15, 0.15, 1.0)
VERTEX_COLOR = (1.0, 0.75, 0.1, 1.0)
SELECTED_VERTEX_COLOR = (0.95, 0.2, 0.1, 1.0)
MIRRORED_VERTEX_COLOR = (0.1, 0.85, 0.95, 1.0)
SEAM_VERTEX_COLOR = (0.2, 0.9, 0.3, 1.0)
UNPAIRED_VERTEX_COLOR = (0.95, 0.2, 0.85, 1.0)
AMBIGUOUS_VERTEX_COLOR = (1.0, 1.0, 1.0, 1.0)
PLANE_COLOR = (0.4, 0.75, 1.0, 1.0)
VERTEX_POINT_SIZE = 4.0
STATE_POINT_SIZE = 7.0
SELECTED_POINT_SIZE = 10.0
_LIGHT = 1.0 / math.sqrt(3.0)


class LabRenderer:
    def __init__(self) -> None:
        self._face_program = shader.ShaderProgram(
            shader.Shader(_FACE_VERT, "vertex"),
            shader.Shader(_FACE_FRAG, "fragment"),
        )
        self._overlay_program = shader.ShaderProgram(
            shader.Shader(_OVERLAY_VERT, "vertex"),
            shader.Shader(_OVERLAY_FRAG, "fragment"),
        )
        self._faces = None
        self._edges = None
        self._verts = None
        self._plane = None
        #: (Farbe, Vertex-List) für Seam / ohne Partner / mehrdeutig.
        self._state_points: list = []
        self._mirrored = None
        self._highlight = None

    @staticmethod
    def _delete(vlist) -> None:
        if vlist is not None:
            vlist.delete()

    def rebuild_mesh(self, mesh: Mesh, report: SymmetryReport) -> None:
        for vlist in (self._faces, self._edges, self._verts, self._plane):
            self._delete(vlist)
        for _color, vlist in self._state_points:
            self._delete(vlist)
        positions, normals = lab_draw_data.face_data(mesh)
        self._faces = self._face_program.vertex_list(
            len(positions) // 3, gl.GL_TRIANGLES,
            position=("f", positions), normal=("f", normals),
        ) if positions else None
        self._edges = self._overlay_list(lab_draw_data.edge_data(mesh), gl.GL_LINES)
        self._verts = self._overlay_list(lab_draw_data.vertex_data(mesh), gl.GL_POINTS)
        self._plane = self._overlay_list(
            lab_draw_data.plane_outline_data(mesh, report.axis), gl.GL_LINES
        )
        self._state_points = [
            (color, self._overlay_list(lab_draw_data.highlight_data(mesh, vids), gl.GL_POINTS))
            for color, vids in (
                (SEAM_VERTEX_COLOR, report.seam),
                (UNPAIRED_VERTEX_COLOR, report.unpaired),
                (AMBIGUOUS_VERTEX_COLOR, report.ambiguous),
            )
        ]

    def rebuild_highlight(self, mesh: Mesh, selected, mirrored) -> None:
        self._delete(self._highlight)
        self._delete(self._mirrored)
        self._highlight = self._overlay_list(
            lab_draw_data.highlight_data(mesh, selected), gl.GL_POINTS
        )
        self._mirrored = self._overlay_list(
            lab_draw_data.highlight_data(mesh, mirrored), gl.GL_POINTS
        )

    def _overlay_list(self, positions: list[float], mode: int):
        if not positions:
            return None
        return self._overlay_program.vertex_list(
            len(positions) // 3, mode, position=("f", positions)
        )

    def draw(self, view: list[float], proj: list[float]) -> None:
        gl.glClearColor(*BACKGROUND_COLOR)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)

        if self._faces is not None:
            program = self._face_program
            program.use()
            program["u_view"] = view
            program["u_proj"] = proj
            program["u_light_dir"] = (_LIGHT, _LIGHT, _LIGHT)
            program["u_base_color"] = BASE_COLOR
            # Faces leicht nach hinten, damit die Edges nicht z-fighten.
            gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
            gl.glPolygonOffset(1.0, 1.0)
            self._faces.draw(gl.GL_TRIANGLES)
            gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)
            program.stop()

        program = self._overlay_program
        program.use()
        program["u_view"] = view
        program["u_proj"] = proj
        if self._edges is not None:
            program["u_color"] = EDGE_COLOR
            self._edges.draw(gl.GL_LINES)
        if self._plane is not None:
            program["u_color"] = PLANE_COLOR
            self._plane.draw(gl.GL_LINES)
        # Vertex-Punkte ohne Depth-Test wie im Playground: alle Vertices
        # bleiben sichtbar und damit anklickbar (Picking ist ebenfalls
        # verdeckungsfrei, siehe mirai.viewport.picking).
        gl.glDisable(gl.GL_DEPTH_TEST)
        if self._verts is not None:
            program["u_color"] = VERTEX_COLOR
            gl.glPointSize(VERTEX_POINT_SIZE)
            self._verts.draw(gl.GL_POINTS)
        gl.glPointSize(STATE_POINT_SIZE)
        for color, vlist in self._state_points:
            if vlist is not None:
                program["u_color"] = color
                vlist.draw(gl.GL_POINTS)
        # Auswahl zuletzt: sie überdeckt Seam/ohne-Partner-Markierungen.
        gl.glPointSize(SELECTED_POINT_SIZE)
        for color, vlist in (
            (MIRRORED_VERTEX_COLOR, self._mirrored),
            (SELECTED_VERTEX_COLOR, self._highlight),
        ):
            if vlist is not None:
                program["u_color"] = color
                vlist.draw(gl.GL_POINTS)
        gl.glPointSize(VERTEX_POINT_SIZE)
        program.stop()
