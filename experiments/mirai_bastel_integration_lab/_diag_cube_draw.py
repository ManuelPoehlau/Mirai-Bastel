"""Minimaler Cube-Render-Trace: Datenfluss von Matrix-State bis glDraw*.

Kein Kamera-Input, keine HUD-Elemente. Einzige Bewegung: zeitbasierte
Y-Rotation der View-Matrix (0.3 rad/s). Vor jedem Draw werden die
tatsaechlich an OpenGL uebergebenen Matrizenwerte ausgegeben.

Fragen die dieser Test beantwortet:
  1) Aendert sich u_view[0] (cos-Term der Y-Rotation) zwischen Frames?
  2) Wird glDrawElements tatsaechlich aufgerufen?
  3) Liegt das Problem im Shader-Uniform-Pfad oder im VAO/Draw-Pfad?

Aufruf:
    python experiments/mirai_bastel_integration_lab/_diag_cube_draw.py
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import pyglet
from pyglet import gl
from pyglet.graphics import shader

_THIS_DIR = Path(__file__).resolve().parent
_REPO = _THIS_DIR.parent.parent
for _p in (str(_THIS_DIR), str(_REPO), str(_REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Shader (identisch zum Lab)
# ---------------------------------------------------------------------------
_VERT = """
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

_FRAG = """
#version 330 core
in vec4 frag_color;
out vec4 out_color;
void main() { out_color = frag_color; }
"""

# ---------------------------------------------------------------------------
# Cube-Geometrie (identisch zu scene_objects.py)
# ---------------------------------------------------------------------------
_VERTS = [
    (-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
    (-1,-1, 1),(1,-1, 1),(1,1, 1),(-1,1, 1),
]
_FACES_QUAD = [
    (4,5,6,7),(0,3,2,1),(0,4,7,3),(5,1,2,6),(3,7,6,2),(0,1,5,4),
]

def _build_buffers(program):
    """Trianguliert Quads und baut Position/Normal/Index-Listen."""
    positions, normals, indices = [], [], []
    idx = 0
    for face in _FACES_QUAD:
        verts = [_VERTS[i] for i in face]
        # Flaechennormale (CCW)
        v0 = [verts[1][k]-verts[0][k] for k in range(3)]
        v1 = [verts[3][k]-verts[0][k] for k in range(3)]
        nx = v0[1]*v1[2] - v0[2]*v1[1]
        ny = v0[2]*v1[0] - v0[0]*v1[2]
        nz = v0[0]*v1[1] - v0[1]*v1[0]
        ln = max(math.sqrt(nx*nx+ny*ny+nz*nz), 1e-9)
        n = (nx/ln, ny/ln, nz/ln)
        for v in verts:
            positions += list(v)
            normals += list(n)
        # Zwei Dreiecke pro Quad
        indices += [idx, idx+1, idx+2, idx, idx+2, idx+3]
        idx += 4

    colors = [1.0, 1.0, 1.0] * (len(positions) // 3)
    vlist = program.vertex_list_indexed(
        len(positions) // 3, gl.GL_TRIANGLES, indices,
        position=("f", positions),
        normal=("f", normals),
        color=("f", colors),
    )
    return vlist


def _proj(aspect, fovy_deg=45.0, near=0.1, far=100.0):
    """Minimale Perspective-Projektionsmatrix (column-major fuer OpenGL)."""
    f = 1.0 / math.tan(math.radians(fovy_deg) * 0.5)
    a = aspect
    nf = 1.0 / (near - far)
    return [
        f/a, 0,  0,               0,
        0,   f,  0,               0,
        0,   0, (far+near)*nf,   -1,
        0,   0, (2*far*near)*nf,  0,
    ]


def _view_y_rot(t, dist=8.0):
    """Y-Rotation + Translation entlang -Z."""
    c, s = math.cos(t), math.sin(t)
    return [
         c,  0, s, 0,
         0,  1, 0, 0,
        -s,  0, c, 0,
         0,  0,-dist, 1,
    ]


# ---------------------------------------------------------------------------
# Diagnose-Fenster
# ---------------------------------------------------------------------------
class _DiagWindow(pyglet.window.Window):
    def __init__(self):
        super().__init__(
            640, 480,
            caption="Cube-Draw-Trace (Esc=Ende)",
            resizable=False,
            vsync=True,
        )
        self.program = shader.ShaderProgram(
            shader.Shader(_VERT, "vertex"),
            shader.Shader(_FRAG, "fragment"),
        )
        self.vlist = _build_buffers(self.program)
        self._t0 = time.perf_counter()
        self._frame = 0
        print("[diag] Cube-Trace start — Cube rotiert zeitbasiert", flush=True)

    def on_draw(self):
        t = time.perf_counter() - self._t0
        self._frame += 1
        log = (self._frame % 20 == 1)  # alle 20 Frames ausgeben

        # --- View-Matrix (zeitbasierte Y-Rotation) --------------------------
        view = _view_y_rot(t * 0.3)
        proj = _proj(self.width / self.height)

        if log:
            print(
                f"\n[Frame {self._frame:4d}] t={t:.2f}s",
                flush=True,
            )
            print(
                f"  u_view[0] (cos-Term) = {view[0]:.4f}  "
                f"u_view[2] (sin-Term) = {view[2]:.4f}",
                flush=True,
            )

        # --- GL-State setzen ------------------------------------------------
        gl.glClearColor(0.08, 0.08, 0.12, 1.0)
        self.clear()
        gl.glEnable(gl.GL_DEPTH_TEST)

        self.program.use()

        # Uniforms setzen
        self.program["u_view"] = view
        self.program["u_proj"] = proj
        inv = 1.0 / math.sqrt(3.0)
        self.program["u_light_dir"] = (inv, inv, inv)
        self.program["u_base_color"] = [0.35, 0.55, 0.85, 1.0]

        if log:
            # u_view[0] nach dem Setzen per glGetUniform verifizieren
            from pyglet.gl import GLfloat
            import ctypes
            mat = (GLfloat * 16)()
            gl.glGetUniformfv(
                self.program.id,
                gl.glGetUniformLocation(self.program.id, b"u_view"),
                mat,
            )
            print(
                f"  glGetUniformfv u_view[0]={mat[0]:.4f} "
                f"(soll == {view[0]:.4f}, gleich={abs(mat[0]-view[0])<1e-5})",
                flush=True,
            )

        # Draw
        self.vlist.draw(gl.GL_TRIANGLES)

        if log:
            err = gl.glGetError()
            print(
                f"  glGetError nach Draw = {err} (0=kein Fehler)",
                flush=True,
            )

        self.program.stop()
        return pyglet.event.EVENT_HANDLED

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.ESCAPE:
            self.close()
        return pyglet.event.EVENT_HANDLED


def main():
    win = _DiagWindow()
    win.set_visible(True)
    pyglet.app.run()
    print(f"[diag] Ende — {win._frame} Frames gerendert", flush=True)


if __name__ == "__main__":
    main()
