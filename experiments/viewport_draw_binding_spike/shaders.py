"""Minimal shader for the draw-binding spike (§4 of the handoff).

Copied inline, not imported, from any prior harness (demonstrator.py,
gl_store.py) — see README "Why not reuse the demonstrator shader": this
spike declares its own attribute set (`position`, `normal`,
`highlight_flag`) matching RenderMesh's actual resource names, which none
of the prior shaders (Playground's default-shader vec3/vec4-only path,
the V02 demonstrator's `color`-attribute shader) do.

Position + normal + a scalar highlight flag, one directional light. No
material uniform (Not in scope — see handoff §5).
"""

from __future__ import annotations

VERTEX_SRC = """
#version 330 core
in vec3 position;
in vec3 normal;
in float highlight_flag;

uniform mat4 u_view;
uniform mat4 u_proj;

out vec3 v_normal;
out float v_highlight;

void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    v_normal = normal;
    v_highlight = highlight_flag;
}
"""

FRAGMENT_SRC = """
#version 330 core
in vec3 v_normal;
in float v_highlight;

uniform vec3 u_light_dir;

out vec4 out_color;

void main() {
    vec3 n = normalize(v_normal);
    float ndl = max(dot(n, normalize(u_light_dir)), 0.0);
    vec3 shaded = mix(vec3(0.30, 0.32, 0.38), vec3(0.85, 0.88, 0.95), ndl);
    vec3 highlighted = mix(shaded, vec3(1.0, 0.82, 0.15), clamp(v_highlight, 0.0, 1.0));
    out_color = vec4(highlighted, 1.0);
}
"""


def build_program():
    """Compiles the spike's ShaderProgram. Requires an active GL context."""
    import pyglet
    from pyglet.graphics.shader import Shader, ShaderProgram

    vertex_shader = Shader(VERTEX_SRC, "vertex")
    fragment_shader = Shader(FRAGMENT_SRC, "fragment")
    return ShaderProgram(vertex_shader, fragment_shader)
