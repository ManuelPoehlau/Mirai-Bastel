"""ShadowMap — Depth-Map-Infrastruktur für Self-Shadowing im Artist Playground.

Discovery-Experiment (siehe MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md M5): Ziel ist
NICHT Photorealismus, sondern bessere Formwahrnehmung (Volumen/Topologie
leichter lesbar) beim Modeling. Deshalb bewusst:

- Nur EIN Licht (dasselbe `u_light_dir` wie bisher in window.py) — kein
  Multi-Light-/Studio-Setup.
- Nur Self-Shadowing des Meshes selbst — kein Ground-Plane-Cast-Shadow
  (das wäre ein separates, späteres Increment).
- Klassisches Orthographic Shadow Mapping mit Hardware-PCF
  (sampler2DShadow + GL_LINEAR-Filterung), 3x3-Sample für weichere Kanten,
  keine Cascaded/Variance-Shadow-Maps — das wäre Overengineering für ein
  Einzelobjekt im Playground.
- Kein Model-Matrix-Konzept eingeführt (bestehender Code hat keine — Mesh
  liegt direkt in Weltkoordinaten, siehe _FACE_VERT in window.py).

Status: UNVERIFIED. In dieser Chat-Session ohne GPU/Fenster geschrieben und
nur auf Python-Syntax geprüft (py_compile), NICHT im echten Playground-
Fenster getestet. Vor jedem Artist-Verdikt muss das praktisch im
`playground/window.py`-Fenster verifiziert werden (Rotation, verschiedene
Meshes, Performance) — siehe Integrationshinweise am Dateiende / Chat-Antwort.

Column-major mat4-Konvention konsistent mit `src/mirai/viewport/camera.py`
(dort dieselbe view-Matrix-Bauweise, siehe Kommentar dort).
"""

from __future__ import annotations

import pyglet.gl as gl

from mirai.viewport import vecmath as v
from mirai.viewport.vecmath import Vec3

# -- Shader für den Depth-Only-Pass ------------------------------------------

SHADOW_VERT = """
#version 330 core
in vec3 position;
uniform mat4 u_light_view_proj;
void main() {
    gl_Position = u_light_view_proj * vec4(position, 1.0);
}
"""

SHADOW_FRAG = """
#version 330 core
void main() {
    // Tiefe wird automatisch nach gl_FragDepth geschrieben — kein Farb-Output.
}
"""


class ShadowMap:
    """FBO + Depth-Texture für einen einzelnen Directional-Light-Shadow-Pass.

    Muss NACH einem aktiven GL-Kontext erzeugt werden (analog zur
    PlaygroundPygletStore-Regel in window.py — erst nach
    pyglet.window.Window.__init__()).
    """

    def __init__(self, size: int = 2048) -> None:
        self.size = size

        self.depth_texture = gl.GLuint()
        gl.glGenTextures(1, self.depth_texture)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.depth_texture)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH_COMPONENT24,
            size, size, 0,
            gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, None,
        )
        # GL_LINEAR (nicht GL_NEAREST!) ist Voraussetzung dafür, dass
        # sampler2DShadow im Fragment-Shader automatisch bilinear-gefiltertes
        # PCF liefert (siehe GL_TEXTURE_COMPARE_MODE unten).
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER)
        border_color = (gl.GLfloat * 4)(1.0, 1.0, 1.0, 1.0)
        gl.glTexParameterfv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_BORDER_COLOR, border_color)
        gl.glTexParameteri(
            gl.GL_TEXTURE_2D, gl.GL_TEXTURE_COMPARE_MODE, gl.GL_COMPARE_REF_TO_TEXTURE
        )
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_COMPARE_FUNC, gl.GL_LEQUAL)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

        self.fbo = gl.GLuint()
        gl.glGenFramebuffers(1, self.fbo)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferTexture2D(
            gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_TEXTURE_2D,
            self.depth_texture, 0,
        )
        gl.glDrawBuffer(gl.GL_NONE)
        gl.glReadBuffer(gl.GL_NONE)
        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            # Bewusst kein stiller Fallback — ein kaputtes FBO soll beim
            # ersten Testlauf sofort auffallen, nicht als "Licht ohne Schatten"
            # unbemerkt durchlaufen.
            raise RuntimeError(f"ShadowMap-FBO unvollständig (status={status})")

    def begin(self) -> None:
        """Bindet das Shadow-FBO und setzt den Viewport auf die Map-Größe."""
        gl.glViewport(0, 0, self.size, self.size)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)

    def end(self, window_width: int, window_height: int) -> None:
        """Bindet zurück auf den Default-Framebuffer + Fenster-Viewport."""
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glViewport(0, 0, window_width, window_height)

    def bind_for_sampling(self, texture_unit: int = 0) -> None:
        gl.glActiveTexture(gl.GL_TEXTURE0 + texture_unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.depth_texture)


# -- Light-Space-Matrizen -----------------------------------------------------

def mesh_center_and_radius(mesh) -> tuple[Vec3, float]:
    """Centroid + max. Distanz zu einem Vertex — Basis für das Ortho-Frustum.

    Bewusst eigenständig statt `_mesh_bounding_radius()` aus window.py zu
    importieren (die liefert nur den Radius, hier wird zusätzlich das
    Zentrum gebraucht, und dieses Modul soll ohne window.py-Import auskommen).
    """
    vertex_ids = list(mesh.all_vertex_ids())
    if not vertex_ids:
        return (0.0, 0.0, 0.0), 1.0
    positions = [mesh.vertex_position(vid) for vid in vertex_ids]
    n = len(positions)
    center = (
        sum(p[0] for p in positions) / n,
        sum(p[1] for p in positions) / n,
        sum(p[2] for p in positions) / n,
    )
    radius = max(v.distance(center, p) for p in positions)
    return center, max(radius, 1e-3)


def build_light_view_matrix(light_dir: Vec3, center: Vec3, distance: float) -> list[float]:
    """View-Matrix einer virtuellen Licht-Kamera, die von `center` aus
    entgegen `light_dir` zurückgesetzt ist und auf `center` blickt.

    Gleiche Bauweise wie `OrbitCamera.build_view_matrix()`
    (src/mirai/viewport/camera.py) — column-major, rechtshändig.
    """
    forward = v.normalize(light_dir)  # Richtung, in die das Licht "fällt"
    eye = v.sub(center, v.scale(forward, distance))

    world_up = (0.0, 1.0, 0.0)
    if abs(v.dot(forward, world_up)) > 0.99:
        world_up = (0.0, 0.0, 1.0)  # Licht (fast) senkrecht -> Up-Vektor tauschen
    right = v.normalize(v.cross(forward, world_up))
    up = v.normalize(v.cross(right, forward))

    tx = -v.dot(eye, right)
    ty = -v.dot(eye, up)
    tz = v.dot(eye, forward)
    return [
        right[0], up[0], -forward[0], 0.0,
        right[1], up[1], -forward[1], 0.0,
        right[2], up[2], -forward[2], 0.0,
        tx, ty, tz, 1.0,
    ]


def build_light_ortho_matrix(half_extent: float, near: float, far: float) -> list[float]:
    """Orthographische Projektion fürs Licht-Frustum (column-major)."""
    return [
        1.0 / half_extent, 0.0, 0.0, 0.0,
        0.0, 1.0 / half_extent, 0.0, 0.0,
        0.0, 0.0, -2.0 / (far - near), 0.0,
        0.0, 0.0, -(far + near) / (far - near), 1.0,
    ]


def matmul4(a: list[float], b: list[float]) -> list[float]:
    """4x4-Matrixmultiplikation, column-major (a * b), beide als 16er-Liste."""
    result = [0.0] * 16
    for col in range(4):
        for row in range(4):
            s = 0.0
            for k in range(4):
                s += a[k * 4 + row] * b[col * 4 + k]
            result[col * 4 + row] = s
    return result


def build_light_view_proj_matrix(
    light_dir: Vec3, mesh, margin: float = 1.2
) -> tuple[list[float], Vec3, float]:
    """Komplettes Light-View-Proj für Self-Shadowing eines einzelnen Meshes.

    Rückgabe: (light_view_proj (16 floats), center, radius) — center/radius
    zusätzlich zurückgegeben, falls der Aufrufer sie fürs Debugging braucht.
    """
    center, radius = mesh_center_and_radius(mesh)
    distance = radius * 2.0
    view = build_light_view_matrix(light_dir, center, distance)
    half_extent = radius * margin
    near = 0.01
    far = distance + radius * margin
    proj = build_light_ortho_matrix(half_extent, near, far)
    return matmul4(proj, view), center, radius
