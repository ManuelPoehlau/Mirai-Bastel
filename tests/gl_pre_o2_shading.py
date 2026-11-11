"""The face-data path as it was before O2 - a frozen test oracle (AD-018 addendum 2026-11-11).

O2 (audit `ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md` §G.3, §H step 4) stopped copying every corner's position and
normal into a 36-float row per face; the shader now reads them from the vertex buffers through the corner slots. The
image must not change. This module keeps the old path to compare against, on whatever driver the GL tests run on (the
reference PC included): `PRE_O2_FRAGMENT_SRC` is `FRAGMENT_SRC` of `src/viewport/gl_render_store.py` at `bc0f0b2`
verbatim; `pre_o2_rows` builds the rows as `RenderMesh._face_rows_data` / `_face_data_flat` did at that commit;
`PreO2Store` draws a `RenderMesh` with both, through the unchanged `GLRenderStore.draw` (same uniforms, same GL state).

Frozen on purpose: change it only to keep it running, never to follow the production shader.
"""

from __future__ import annotations

import ctypes
from array import array

from viewport.gl_render_store import VERTEX_SRC, GLRenderStore

#: Texel (vec4) per pre-O2 face row: (normal, corner count), 4 corner positions, 4 corner normals.
ROW_TEXELS = 9
ROW_FLOATS = ROW_TEXELS * 4
_ROW_CORNERS = 4
_NO_TINT = (0.0, 0.0, 0.0)
_FACE_DATA_UNIT = 1
_TRIANGLE_FACES_UNIT = 2

PRE_O2_FRAGMENT_SRC = """
#version 330 core
in vec3 v_normal;
in vec3 v_world_pos;

uniform mat4 u_view;
uniform mat4 u_proj;
uniform mat4 u_model;
uniform vec3 u_base_color;
uniform int u_flat;
uniform int u_region_tint;
uniform float u_alpha;
uniform int u_has_face_data;
uniform samplerBuffer u_face_data;
uniform samplerBuffer u_triangle_faces;

uniform vec3 u_key_dir;
uniform vec3 u_key_color;
uniform float u_key_wrap;
uniform vec3 u_fill_dir;
uniform vec3 u_fill_color;
uniform float u_fill_wrap;
uniform float u_ambient;
uniform float u_specular;
uniform float u_spec_exponent;
uniform float u_fill_specular;

#ifdef TEXTURED
// AD-026: the textured program (`TEXTURED_*_SRC`) - barycentrics from the geometry shader, the
// triangle's corner UVs by `gl_PrimitiveID` (3 texels per triangle), the image on its own unit.
in vec3 g_bary;
uniform sampler2D u_texture;
uniform samplerBuffer u_triangle_uvs;
#endif

out vec4 out_color;

const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);

const int ROW_TEXELS = 9;

float cross2(vec2 a, vec2 b) { return a.x * b.y - a.y * b.x; }

float bilinear_u(vec2 h, vec2 e, vec2 f, vec2 g, float v) {
    vec2 den = e + g * v;
    return abs(den.x) > abs(den.y) ? (h.x - f.x * v) / den.x : (h.y - f.y * v) / den.y;
}

bool inside(vec2 uv) {
    return uv.x > -0.05 && uv.x < 1.05 && uv.y > -0.05 && uv.y < 1.05;
}

// (u, v) with p = a + u (b - a) + v (d - a) + u v (a - b + c - d), after Quilez; (-1, -1) if none.
vec2 inv_bilinear(vec2 p, vec2 a, vec2 b, vec2 c, vec2 d) {
    vec2 e = b - a;
    vec2 f = d - a;
    vec2 g = a - b + c - d;
    vec2 h = p - a;
    float k2 = cross2(g, f);
    float k1 = cross2(e, f) + cross2(h, g);
    float k0 = cross2(h, e);
    if (abs(k2) <= 1e-4 * abs(k1)) {
        if (k1 == 0.0) return vec2(-1.0);
        float v = -k0 / k1;
        return vec2(bilinear_u(h, e, f, g, v), v);
    }
    float w = k1 * k1 - 4.0 * k0 * k2;
    if (w < 0.0) return vec2(-1.0);
    w = sqrt(w);
    float v = (-k1 - w) * (0.5 / k2);
    vec2 uv = vec2(bilinear_u(h, e, f, g, v), v);
    if (inside(uv)) return uv;
    v = (-k1 + w) * (0.5 / k2);
    return vec2(bilinear_u(h, e, f, g, v), v);
}

vec3 face_corner(int row, int k) { return (u_model * vec4(texelFetch(u_face_data, row + k).xyz, 1.0)).xyz; }

// Ray / bilinear patch P(u, v) = mix(mix(q00, q10, u), mix(q01, q11, u), v), after Reshetov,
// "Cool Patches" (Ray Tracing Gems II, ch. 8). Nearest hit with (u, v) in the patch (small
// tolerance), else (-1, -1).
vec2 ray_patch(vec3 o, vec3 d, vec3 q00, vec3 q10, vec3 q11, vec3 q01) {
    vec3 e10 = q10 - q00;
    vec3 e11 = q11 - q10;
    vec3 e00 = q01 - q00;
    vec3 qn = cross(e10, q01 - q11);
    q00 -= o;
    q10 -= o;
    float a = dot(cross(q00, d), e00);
    float c = dot(qn, d);
    float b = dot(cross(q10, d), e11) - (a + c);
    float det = b * b - 4.0 * a * c;
    if (det < 0.0) return vec2(-1.0);
    det = sqrt(det);
    float u1;
    float u2;
    if (abs(c) < 1e-12 * max(abs(a), abs(b))) {
        if (b == 0.0) return vec2(-1.0);
        u1 = -a / b;
        u2 = -1.0;
    } else {
        u1 = 0.5 * (-b - (b < 0.0 ? -det : det));
        u2 = a / u1;
        u1 /= c;
    }
    float best_t = 3.4e38;
    vec2 best = vec2(-1.0);
    for (int i = 0; i < 2; ++i) {
        float u = i == 0 ? u1 : u2;
        if (u < -1e-3 || u > 1.0 + 1e-3) continue;
        vec3 pa = mix(q00, q10, u);
        vec3 pb = mix(e00, e11, u);
        vec3 n = cross(d, pb);
        float nn = dot(n, n);
        if (nn <= 0.0) continue;
        n = cross(n, pa);
        float t = dot(n, pb) / nn;
        float v = dot(n, d) / nn;
        if (t > 0.0 && t < best_t && v > -1e-3 && v < 1.0 + 1e-3) {
            best_t = t;
            best = vec2(u, v);
        }
    }
    return best;
}

// Fallback where the ray misses the patch (grazing views of strongly bent quads): the fragment
// projected onto the quad's plane, mapped back with the inverse bilinear map. The projection is
// affine, so it stays continuous across the quad's edges and its diagonal.
vec2 projected_uv(vec3 n, vec3 p0, vec3 p1, vec3 p2, vec3 p3) {
    vec3 ax = (p1 - p0) + (p2 - p3);
    ax -= n * dot(ax, n);
    if (dot(ax, ax) < 1e-20) return vec2(-1.0);
    ax = normalize(ax);
    vec3 ay = cross(n, ax);
    vec3 p = v_world_pos - p0;
    return inv_bilinear(
        vec2(dot(p, ax), dot(p, ay)), vec2(0.0),
        vec2(dot(p1 - p0, ax), dot(p1 - p0, ay)),
        vec2(dot(p2 - p0, ax), dot(p2 - p0, ay)),
        vec2(dot(p3 - p0, ax), dot(p3 - p0, ay)));
}

vec3 quad_normal(int row, vec3 face_n, vec3 fallback) {
    vec3 p0 = face_corner(row, 1);
    vec3 p1 = face_corner(row, 2);
    vec3 p2 = face_corner(row, 3);
    vec3 p3 = face_corner(row, 4);
    vec3 eye = -transpose(mat3(u_view)) * u_view[3].xyz;
    vec3 ray_o = eye;
    vec3 ray_d = normalize(v_world_pos - eye);
    if (u_proj[3][3] == 1.0) {
        // Ortho (WP Ortho / Views): parallel rays along the view direction; the origin is the
        // fragment pushed back in front of the patch (any point on the ray serves the patch test).
        ray_d = normalize(transpose(mat3(u_view)) * vec3(0.0, 0.0, -1.0));
        ray_o = v_world_pos - ray_d * (length(p2 - p0) + length(p3 - p1) + 1.0);
    }
    vec2 uv = ray_patch(ray_o, ray_d, p0, p1, p2, p3);
    if (uv.x < 0.0 && uv.y < 0.0) {
        uv = projected_uv(normalize(mat3(u_model) * face_n), p0, p1, p2, p3);
        if (!inside(uv)) return fallback;
    }
    uv = clamp(uv, 0.0, 1.0);
    vec3 n0 = texelFetch(u_face_data, row + 5).xyz;
    vec3 n1 = texelFetch(u_face_data, row + 6).xyz;
    vec3 n2 = texelFetch(u_face_data, row + 7).xyz;
    vec3 n3 = texelFetch(u_face_data, row + 8).xyz;
    vec3 n = mix(mix(n0, n1, uv.x), mix(n3, n2, uv.x), uv.y);
    if (dot(n, n) < 1e-20) return fallback;
    return normalize(mat3(u_model) * n);
}

float wrap_light(float ndl, float w) { return max((ndl + w) / (1.0 + w), 0.0); }

// `material.specular_term`: no highlight on the side facing away from the light.
float blinn_phong(vec3 n, vec3 l, vec3 v, float e) {
    if (dot(n, l) <= 0.0) return 0.0;
    return pow(max(dot(n, normalize(l + v)), 0.0), e);
}

void main() {
    vec3 screen_flat_n = normalize(cross(dFdx(v_world_pos), dFdy(v_world_pos)));
    vec3 n = normalize(v_normal);
    vec3 albedo = u_base_color;
#ifdef TEXTURED
    {
        int t = gl_PrimitiveID * 3;
        vec2 a = texelFetch(u_triangle_uvs, t).xy;
        if (a.x > -1.0e29) {
            vec2 uv = a * g_bary.x + texelFetch(u_triangle_uvs, t + 1).xy * g_bary.y
                    + texelFetch(u_triangle_uvs, t + 2).xy * g_bary.z;
            albedo = texture(u_texture, uv).rgb;
        }
    }
#endif
    if (u_has_face_data != 0) {
        int row = int(texelFetch(u_triangle_faces, gl_PrimitiveID).r + 0.5) * ROW_TEXELS;
        vec4 head = texelFetch(u_face_data, row);
        if (u_region_tint != 0) {
            // Saved regions: the colour rides in the free .w of corner texels 1-3; black = no region.
            vec3 tint = vec3(texelFetch(u_face_data, row + 1).w, texelFetch(u_face_data, row + 2).w,
                             texelFetch(u_face_data, row + 3).w);
            if (dot(tint, tint) > 0.0) albedo = mix(albedo, tint, 0.85);
        }
        vec3 face_n = normalize(head.xyz);
        if (u_flat != 0) {
            n = normalize(mat3(u_model) * face_n);
        } else if (head.w == 4.0) {
            n = quad_normal(row, face_n, n);
        }
    } else if (u_flat != 0) {
        n = screen_flat_n;
    }
    vec3 light = vec3(u_ambient)
               + u_key_color  * wrap_light(dot(n, u_key_dir),  u_key_wrap)
               + u_fill_color * wrap_light(dot(n, u_fill_dir), u_fill_wrap);
    vec3 shaded = albedo * light;
    if (u_specular > 0.0 || u_fill_specular > 0.0) {
        // Non-local viewer (the fixed-function default): V = the camera's view axis, so a Flat
        // polygon stays one colour and the highlight depends on the normal only.
        vec3 v = normalize(transpose(mat3(u_view)) * vec3(0.0, 0.0, 1.0));
        float spec = u_specular * dot(u_key_color, LUMA) * blinn_phong(n, u_key_dir, v, u_spec_exponent)
                   + u_fill_specular * dot(u_fill_color, LUMA) * blinn_phong(n, u_fill_dir, v, u_spec_exponent);
        shaded += vec3(spec);
    }
    out_color = vec4(shaded, u_alpha);
}
"""


def pre_o2_rows(rm) -> array:
    """The pre-O2 `face_shading` rows of `rm` (one per face row; free rows zero), from its mesh, derived data and tints."""
    mesh = rm.mesh
    face_vertices, position = mesh.face_vertices, mesh.vertex_position
    normals, face_normals, tints = rm.derived.vertex_normals, rm.derived.face_normals, rm._tints
    out: list[float] = []
    for face_id in rm._row_face:
        if face_id is None:
            out += [0.0] * ROW_FLOATS
            continue
        boundary = face_vertices(face_id)
        n = len(boundary)
        nx, ny, nz = face_normals[face_id]
        tr, tg, tb = tints.get(face_id, _NO_TINT) if tints else _NO_TINT
        corners = boundary[:_ROW_CORNERS]
        padding = [0.0] * (4 * (_ROW_CORNERS - len(corners)))
        row = [nx, ny, nz, float(n)]
        for v in corners:
            x, y, z = position(v)
            row += (x, y, z, 0.0)
        row += padding
        for v in corners:
            x, y, z = normals[v]
            row += (x, y, z, 0.0)
        row += padding
        if tr or tg or tb:
            row[7], row[11], row[15] = tr, tg, tb
        out += row
    return array("f", out)


class PreO2Store(GLRenderStore):
    """`GLRenderStore` drawing with the pre-O2 shader and rows. Set `source` to the `RenderMesh` it belongs to; the rows
    are rebuilt from it at every draw. Plain (untextured) draws only."""

    _program = None
    _textured_program = None

    def __init__(self, stats) -> None:
        super().__init__(stats)
        self.source = None
        self._rows_gl: tuple[int, int] | None = None

    @classmethod
    def program(cls):
        if cls._program is None:
            from pyglet.graphics.shader import Shader, ShaderProgram

            from viewport.gl_render_store import _register_sampler_buffer_uniform

            _register_sampler_buffer_uniform()
            cls._program = ShaderProgram(Shader(VERTEX_SRC, "vertex"), Shader(PRE_O2_FRAGMENT_SRC, "fragment"))
        return cls._program

    @classmethod
    def textured_program(cls):
        raise NotImplementedError("the pre-O2 oracle draws untextured only")

    def _flush_face_data(self) -> bool:
        from pyglet import gl

        ready = super()._flush_face_data()  # binds `triangle_faces` on unit 2 (unchanged by O2)
        rows = pre_o2_rows(self.source)
        if self._rows_gl is None:
            buffer, texture = gl.GLuint(), gl.GLuint()
            gl.glGenBuffers(1, ctypes.byref(buffer))
            gl.glGenTextures(1, ctypes.byref(texture))
            self._rows_gl = (buffer.value, texture.value)
            gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, buffer.value)
            gl.glBindTexture(gl.GL_TEXTURE_BUFFER, texture.value)
            gl.glTexBuffer(gl.GL_TEXTURE_BUFFER, gl.GL_RGBA32F, buffer.value)
        buffer_id, texture_id = self._rows_gl
        gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, buffer_id)
        gl.glBufferData(gl.GL_TEXTURE_BUFFER, len(rows) * 4, rows.buffer_info()[0], gl.GL_DYNAMIC_DRAW)
        gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0 + _FACE_DATA_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_BUFFER, texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        return ready and len(rows) > 0

    def _bind_vertex_textures(self, vlist) -> bool:
        return True  # the old shader reads no vertex buffer

    def _set_face_samplers(self, program, textured: bool, vlist) -> None:
        program["u_face_data"] = _FACE_DATA_UNIT
        program["u_triangle_faces"] = _TRIANGLE_FACES_UNIT

    def release(self) -> None:
        super().release()
        if self._rows_gl is not None:
            from pyglet import gl

            buffer_id, texture_id = self._rows_gl
            gl.glDeleteTextures(1, ctypes.byref(gl.GLuint(texture_id)))
            gl.glDeleteBuffers(1, ctypes.byref(gl.GLuint(buffer_id)))
            self._rows_gl = None
