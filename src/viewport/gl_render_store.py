"""GLRenderStore — production drawable `ResourceStore` (AD-018 §5, Option B).

Ships the real draw path `VIEWPORT_V02_ARCHITECTURE.md` §4.2 specifies
(`RenderMesh.render(camera)` "issue draw call") and Gate 5 deferred as a
scoping choice (`docs/archive/early_work_packages/WP-04_GATE_5_COMPLETION.md`): one real, persistent,
indexed `ShaderProgram.vertex_list_indexed(...)` per `RenderMesh` instance,
built from `RenderMesh`'s declared "mesh" attribute group
(`positions`/`normals`/`highlight_flags` + `indices`, see
`render_mesh.MESH_GROUP_ATTRIBUTES`), with `camera_uniforms`/
`material_uniforms` applied as program uniforms at draw time.

Mechanics (deferred VertexList construction, in-place attribute-slice
patching, uniforms never touching the VertexList) are adapted from the
proven reference `experiments/viewport_draw_binding_spike/spike_gl_store.py`
(H1 CONFIRMED) - not copied wholesale (Promotion Boundary, AGENTS.md §7).
The one structural difference: the spike inferred "the structural trio has
been freshly allocated" from call order; this store is told explicitly, via
`declare_group()`/`begin_rebuild()`/`end_rebuild()` (AD-018 §5), which
resources form the group and when one rebuild cycle starts/ends - no
call-order inference left. `declare_uniform()` replaces the spike's
name-based `VERTEX_ATTR_NAMES`/uniform distinction with an explicit one.

Requires an active GL context at first `allocate()` (same constraint as
`PygletStore`, see its module docstring in `resource_store.py`). The
`ShaderProgram` is compiled lazily on first use (class-level, shared across
instances - one GL context), so importing this module has no GL-context
ordering requirement.

Scope-Grenze (VIEWPORT_V02_ARCHITECTURE.md §1 Non-Goal "kein eigener GPU
Resource Manager", AD-018 §5 binding constraint "not a general GPU
resource manager"): this store only assembles ONE declared group ("mesh")
into ONE combined `VertexList`; it is not a registry for an arbitrary
number of drawable groups, and `draw()` draws exactly that one group. A
future need for more than one drawable per `RenderMesh` is out of scope
here (see AD-018 §5 "Deliberately not decided here").
"""

from __future__ import annotations

from array import array

from .light_rig import PRESET_HEUTE, PRESETS, resolve
from .resource_store import ResourceStore

VERTEX_SRC = """
#version 330 core
in vec3 position;
in vec3 normal;
in float highlight_flag;

uniform mat4 u_view;
uniform mat4 u_proj;
uniform mat4 u_model;

out vec3 v_normal;
out float v_highlight;
out vec3 v_world_pos;

void main() {
    vec4 world = u_model * vec4(position, 1.0);
    gl_Position = u_proj * u_view * world;
    // AD-021 M2-1: rotation + uniform scale only (Q-4), so mat3(u_model) is a valid normal
    // matrix up to length; the fragment shader normalizes.
    v_normal = mat3(u_model) * normal;
    v_highlight = highlight_flag;
    v_world_pos = world.xyz;
}
"""

# WP-06 B2b (AD-018 §7 addendum, E18): the selection face tint is gone
# (Artist REJECT); selection is drawn by `GLPointOverlay`. `v_highlight` stays
# declared because the `highlight_flags` pipeline is kept until its
# documented follow-up cleanup.
#
# Normals (AD-018 addendum 2026-10-15, B5a.1): the fragment looks up its face
# row via `gl_PrimitiveID` (= triangle number in index-buffer order; pyglet
# draws one VertexList with one glDrawElements, so the count starts at 0).
# - Flat: the face's Newell normal - one normal per polygon, no triangulation
#   diagonal (Artist REJECT of per-triangle flat, 2026-09-27).
# - Smooth on a quad: the four corner normals blended bilinearly at the
#   fragment's patch coordinates (u, v), found by intersecting the pixel's
#   view ray with the quad's bilinear patch. The patch does not depend on the
#   triangulation diagonal, and its edges are the mesh's straight edges, so
#   neighbouring quads agree along a shared edge (one plane per quad would
#   not: tried, it leaves seams on bent quads). Where the ray misses the patch
#   the fragment is projected onto the quad's plane instead.
#   Linear interpolation per triangle kinks along the diagonal, which made the
#   triangles visible in Smooth too (Manu, 2026-10-15). Triangles and n-gons
#   keep the interpolated vertex normal.
# Without face data (`u_has_face_data` 0) the old paths remain: flat from the
# screen derivative of the world position (computed outside any branch -
# dFdx/dFdy are undefined in non-uniform control flow; back faces are culled,
# so the cross product faces the camera), smooth from `v_normal`.
#
# Light (`light_rig.resolve`, promoted from the Shading Lab 2026-10-15):
# ambient + key + fill with wrap; preset "Heute" reproduces the old
# `mix(base * 0.35, base, N·L)` exactly. Keep in sync with `light_rig.shade()`.
FRAGMENT_SRC = """
#version 330 core
in vec3 v_normal;
in float v_highlight;
in vec3 v_world_pos;

uniform mat4 u_view;
uniform mat4 u_model;
uniform vec3 u_base_color;
uniform int u_flat;
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

out vec4 out_color;

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
    vec2 uv = ray_patch(eye, normalize(v_world_pos - eye), p0, p1, p2, p3);
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

void main() {
    vec3 screen_flat_n = normalize(cross(dFdx(v_world_pos), dFdy(v_world_pos)));
    vec3 n = normalize(v_normal);
    if (u_has_face_data != 0) {
        int row = int(texelFetch(u_triangle_faces, gl_PrimitiveID).r + 0.5) * ROW_TEXELS;
        vec4 head = texelFetch(u_face_data, row);
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
    vec3 shaded = u_base_color * light;
    out_color = vec4(shaded, u_alpha);
}
"""

DEFAULT_BASE_COLOR = (0.72, 0.75, 0.82)
_IDENTITY_4 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
#: Light of a store nobody configured (labs, tests): "Heute", i.e. the pre-2026-10-15 look.
DEFAULT_LIGHT_UNIFORMS = resolve(PRESETS[PRESET_HEUTE])
LIGHT_UNIFORM_NAMES = tuple(DEFAULT_LIGHT_UNIFORMS)
#: Texture units of the face data; unit 0 stays free for pyglet's own textures (text, HUD).
_FACE_DATA_UNIT = 1
_TRIANGLE_FACES_UNIT = 2
#: Dirty face-data ranges closer than this (floats; 1024 = 4 KiB) are uploaded as one.
_FACE_MERGE_GAP = 1024


def _register_sampler_buffer_uniform() -> None:
    """pyglet (2.1) has no setter for `samplerBuffer` uniforms and raises KeyError while
    introspecting the program. A sampler uniform is an int texture unit like `sampler2D`, so the
    face-data samplers reuse that entry (no-op once pyglet knows the type itself)."""
    from pyglet import gl
    from pyglet.graphics import shader

    shader._uniform_setters.setdefault(
        gl.GL_SAMPLER_BUFFER, shader._uniform_setters[gl.GL_SAMPLER_2D]
    )


def _build_program():
    """Compiles the shared `ShaderProgram`. Requires an active GL context."""
    import pyglet
    from pyglet.graphics.shader import Shader, ShaderProgram

    _register_sampler_buffer_uniform()

    vertex_shader = Shader(VERTEX_SRC, "vertex")
    fragment_shader = Shader(FRAGMENT_SRC, "fragment")
    return ShaderProgram(vertex_shader, fragment_shader)


class GLRenderStore(ResourceStore):
    """Real pyglet/OpenGL backend: one indexed VertexList + uniform passthrough
    + `draw()`, driven by `RenderMesh`'s declared layout (AD-018 §5) instead
    of inferred call order."""

    _program = None  # lazily compiled, shared across instances (one GL context)

    def __init__(self, stats) -> None:
        super().__init__(stats)
        self._cpu: dict[str, list[float]] = {}
        self._groups: dict[str, tuple[dict[str, tuple[str, int]], str]] = {}
        self._uniforms: set[str] = set()
        self._vertex_lists: dict[str, object] = {}
        self._rebuild_active: set[str] = set()
        # WP-06 B5a (E36/E40): vom Viewport gesetzt, wirkt nur in `draw()`.
        self.flat = False
        self.polygon_offset = False
        # AD-021 M2-0 (Ghost, §7.3 RD-1): < 1.0 = durchscheinend, ohne Depth-Write.
        self.alpha = 1.0
        # Licht (light_rig.resolve), vom Viewport pro Frame gesetzt; reiner Draw-Zustand.
        self._light_uniforms: dict = dict(DEFAULT_LIGHT_UNIFORMS)
        # Face-Daten (AD-018 Nachtrag 2026-10-15): Name -> (GL-Formatname, Textur-Einheit,
        # Uniform). CPU-Kopie als `array('f')` in `_face_cpu` (direkt hochladbar, ohne Umwandlung);
        # was sich seit dem letzten Draw geändert hat, steht in `_face_dirty` (Name -> Liste von
        # [lo, hi) in Floats, None = ganz neu hochladen).
        self._face_buffers: dict[str, tuple[str, int, str]] = {}
        self._face_cpu: dict[str, array] = {}
        self._face_dirty: dict[str, list[tuple[int, int]] | None] = {}
        self._face_gl: dict[str, tuple[int, int, int]] = {}  # Name -> (Buffer, Textur, Floats)

    @classmethod
    def program(cls):
        if cls._program is None:
            cls._program = _build_program()
        return cls._program

    # -- Layout-Deklaration (AD-018 §5) --------------------------------------

    def declare_group(
        self, group: str, attributes: dict[str, tuple[str, int]], index: str
    ) -> None:
        self._groups[group] = (dict(attributes), index)

    def declare_uniform(self, name: str) -> None:
        self._uniforms.add(name)

    def declare_face_data(self, data: str, triangle_map: str, row_texels: int) -> None:
        self._face_buffers[data] = ("GL_RGBA32F", _FACE_DATA_UNIT, "u_face_data")
        self._face_buffers[triangle_map] = ("GL_R32F", _TRIANGLE_FACES_UNIT, "u_triangle_faces")

    def begin_rebuild(self, group: str) -> None:
        self._rebuild_active.add(group)

    def end_rebuild(self, group: str) -> None:
        self._rebuild_active.discard(group)
        if group in self._groups:
            self._rebuild_vertex_list(group)

    # -- ResourceStore contract ----------------------------------------------

    def allocate(self, name: str, nbytes: int) -> None:
        if self.has(name) and self.resource(name).created:
            # Re-allocation of an existing resource is a recreation (new
            # identity), mirrors TraceStore/PygletStore.
            self.destroy(name)
        res = self._ensure(name)
        res.created = True
        if name in self._face_buffers:
            self._face_cpu[name] = array("f")
            self._face_dirty[name] = None
        else:
            self._cpu[name] = []
        self.stats.count("gpu_resource_creations")
        self.stats.snapshot_resource(res)

    def update(self, name: str, offset: int, data: list, nbytes: int) -> None:
        res = self._ensure(name)
        res.updates += 1
        res.bytes_uploaded += nbytes
        self.stats.add_upload(nbytes)
        self.stats.snapshot_resource(res)
        if name in self._face_buffers:
            self._update_face_data(name, offset, data)
            return
        buf = self._cpu.setdefault(name, [])
        needed = offset + len(data)
        if len(buf) < needed:
            buf.extend([0.0] * (needed - len(buf)))
        buf[offset:offset + len(data)] = data

        group = self._group_of(name)
        if group is None:
            return  # declared uniform (or undeclared name) - pure CPU storage
        if group in self._rebuild_active:
            return  # buffered only; end_rebuild() assembles the VertexList
        self._patch_attribute(group, name, buf, offset, len(data))

    def destroy(self, name: str) -> None:
        res = self._resources.pop(name, None)
        if res is not None:
            self._cpu.pop(name, None)
            self._face_cpu.pop(name, None)
            self.stats.count("gpu_resource_destroys")
        if name in self._face_buffers:
            self._face_dirty[name] = None

    # -- face data (AD-018 addendum 2026-10-15) -------------------------------------

    def _update_face_data(self, name: str, offset: int, data: list) -> None:
        values = self._face_cpu.setdefault(name, array("f"))
        end = offset + len(data)
        if len(values) < end:
            values.extend(array("f", bytes(4 * (end - len(values)))))
        values[offset:end] = array("f", data)
        if name not in self._face_dirty:
            self._face_dirty[name] = []
        dirty = self._face_dirty[name]
        if dirty is not None:
            dirty.append((offset, end))

    @staticmethod
    def _merged_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Sorted, merged dirty ranges. Rows touched by one move lie scattered over the buffer,
        so one span from the first to the last would re-upload most of it on a dense mesh;
        ranges closer than `_FACE_MERGE_GAP` floats are joined to save calls."""
        merged: list[tuple[int, int]] = []
        for lo, hi in sorted(ranges):
            if merged and lo <= merged[-1][1] + _FACE_MERGE_GAP:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        return merged

    def _flush_face_data(self) -> bool:
        """Uploads pending face data (glBufferData on a new size, else one glBufferSubData per
        merged changed range) and binds the textures. False = no face data to read."""
        import ctypes

        from pyglet import gl

        ready = bool(self._face_buffers)
        for name, (fmt, unit, _uniform) in self._face_buffers.items():
            data = self._face_cpu.get(name)
            if not data:
                ready = False
                continue
            buffer_id, texture_id, size = self._face_gl.get(name, (0, 0, 0))
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            if not buffer_id:
                buffer, texture = gl.GLuint(), gl.GLuint()
                gl.glGenBuffers(1, ctypes.byref(buffer))
                gl.glGenTextures(1, ctypes.byref(texture))
                buffer_id, texture_id = buffer.value, texture.value
                gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, buffer_id)
                gl.glBindTexture(gl.GL_TEXTURE_BUFFER, texture_id)
                gl.glTexBuffer(gl.GL_TEXTURE_BUFFER, getattr(gl, fmt), buffer_id)
                gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, 0)
            dirty = self._face_dirty.pop(name, False)
            if size != len(data):
                dirty = None
            if dirty is not False:
                address = data.buffer_info()[0]
                gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, buffer_id)
                if dirty is None:
                    gl.glBufferData(gl.GL_TEXTURE_BUFFER, len(data) * 4, address, gl.GL_DYNAMIC_DRAW)
                else:
                    for lo, hi in self._merged_ranges(dirty):
                        gl.glBufferSubData(gl.GL_TEXTURE_BUFFER, lo * 4, (hi - lo) * 4, address + lo * 4)
                gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, 0)
            self._face_gl[name] = (buffer_id, texture_id, len(data))
            gl.glBindTexture(gl.GL_TEXTURE_BUFFER, texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        return ready

    def _unbind_face_data(self) -> None:
        from pyglet import gl

        for _fmt, unit, _uniform in self._face_buffers.values():
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            gl.glBindTexture(gl.GL_TEXTURE_BUFFER, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def _release_face_data(self) -> None:
        if self._face_gl:
            import ctypes

            from pyglet import gl

            for buffer_id, texture_id, _size in self._face_gl.values():
                gl.glDeleteTextures(1, ctypes.byref(gl.GLuint(texture_id)))
                gl.glDeleteBuffers(1, ctypes.byref(gl.GLuint(buffer_id)))
        self._face_gl.clear()
        self._face_dirty = {name: None for name in self._face_buffers}

    # -- vertex-group assembly ------------------------------------------------

    def _group_of(self, name: str) -> str | None:
        for group, (attributes, index) in self._groups.items():
            if name in attributes or name == index:
                return group
        return None

    def _patch_attribute(
        self, group: str, name: str, data: list[float], offset: int, count: int
    ) -> None:
        """Content-only patch into the existing, persistent VertexList - no
        reallocation (GPU Resource Persistence, VIEWPORT_V02_ARCHITECTURE.md §7).
        Called for every `update()` outside a `begin_rebuild()`/`end_rebuild()`
        bracket, i.e. exactly the partial-update paths in
        `RenderMesh._sync_geometry()`/`_sync_selection()`/`_patch_topology()`.

        Only the changed slice `[offset, offset + count)` is written (AD-018
        addendum 2026-10-10): the full-buffer copy this replaced cost
        O((moved + ring) x V) per drag move. `data` is the whole CPU copy; the
        slice is taken from it, so the GPU range equals `_cpu` exactly."""
        vlist = self._vertex_lists.get(group)
        if vlist is None:
            return
        attributes, index_name = self._groups[group]
        if name == index_name:
            # Index data patch (AD-023 V1, 2026-10-21): `RenderMesh` rewrites the triangle slots a
            # topology patch touched; pyglet stores indices offset by the VertexList's start.
            start = vlist.start
            vlist.domain.index_buffer.set_region(
                vlist.index_start + offset, count, [int(x) + start for x in data[offset:offset + count]]
            )
            return
        attr_name, _components = attributes[name]
        target = getattr(vlist, attr_name, None)
        if target is None:
            # The driver optimized this attribute out of the program (e.g.
            # `highlight_flag` since the fragment shader no longer reads it,
            # AD-018 §7); pyglet then built the VertexList without it, so
            # there is nothing on the GPU to patch. CPU copy stays in `_cpu`.
            return
        end = offset + count
        target[offset:end] = data[offset:end]

    def _rebuild_vertex_list(self, group: str) -> None:
        import pyglet

        attributes, index_name = self._groups[group]
        counts = [
            len(self._cpu[name]) // components
            for name, (_attr, components) in attributes.items()
            if self._cpu.get(name)
        ]
        if not counts:
            return
        n_verts = max(counts)

        kwargs = {}
        for name, (attr_name, components) in attributes.items():
            data = self._cpu.get(name) or []
            needed = n_verts * components
            if len(data) < needed:
                data = list(data) + [0.0] * (needed - len(data))
            kwargs[attr_name] = ("f", tuple(data[:needed]))

        indices_int = [int(v) for v in self._cpu.get(index_name) or []]

        program = self.program()
        old_vlist = self._vertex_lists.get(group)
        self._vertex_lists[group] = program.vertex_list_indexed(
            n_verts, pyglet.gl.GL_TRIANGLES, indices_int, **kwargs
        )
        if old_vlist is not None:
            old_vlist.delete()

    def release(self) -> None:
        """Deletes the VertexLists (AD-021 M1: a removed object entry, e.g. Undo of "Add
        object", frees its GPU geometry at once instead of at garbage collection)."""
        for vlist in self._vertex_lists.values():
            vlist.delete()
        self._vertex_lists.clear()
        self._release_face_data()

    # -- draw style (WP-06 B5a) -------------------------------------------------

    def set_draw_style(self, flat: bool, polygon_offset: bool, alpha: float = 1.0) -> None:
        """Flat Shading (E37) und Polygon-Offset der Faces (E40: nur wenn
        zusätzlich Edges gezeichnet werden). Reiner Draw-Zustand - keine
        Ressource, kein Rebuild. `alpha` < 1 (AD-021 M2-0, Ghost): geblendet, Depth-Test
        an, Depth-Write aus."""
        self.flat = bool(flat)
        self.polygon_offset = bool(polygon_offset)
        self.alpha = float(alpha)

    def set_light_uniforms(self, uniforms: dict) -> None:
        """Light for the next `draw()` (`light_rig.resolve()`): pure draw state, no resource,
        no upload."""
        missing = [name for name in LIGHT_UNIFORM_NAMES if name not in uniforms]
        if missing:
            raise KeyError(f"missing light uniforms: {missing}")
        self._light_uniforms = {name: uniforms[name] for name in LIGHT_UNIFORM_NAMES}

    def light_uniforms(self) -> dict:
        return dict(self._light_uniforms)

    # -- draw-time access -------------------------------------------------------

    def vertex_list(self, group: str = "mesh"):
        """The current combined VertexList for `group`, or None before its
        rebuild bracket has ever completed."""
        return self._vertex_lists.get(group)

    def uniform_data(self, name: str) -> list[float]:
        """CPU-side content of a declared uniform (`camera_uniforms`,
        `material_uniforms`, ...) - or of any undeclared, non-group name."""
        return list(self._cpu.get(name, []))

    def _apply_camera_uniforms(self, program) -> None:
        data = self.uniform_data("camera_uniforms")
        if len(data) != 32:
            return
        program["u_view"] = tuple(data[0:16])
        program["u_proj"] = tuple(data[16:32])

    def _base_color(self) -> tuple[float, float, float]:
        data = self.uniform_data("material_uniforms")
        if len(data) == 3:
            return (data[0], data[1], data[2])
        return DEFAULT_BASE_COLOR

    def draw(self, group: str = "mesh") -> None:
        """Issues the real draw call for `group` (`RenderMesh.render(camera)`,
        VIEWPORT_V02_ARCHITECTURE.md §4.2). No-op if the group's VertexList
        has not been built yet (never true after a completed `RenderMesh`
        rebuild, since `build()` runs the full bracket synchronously)."""
        from pyglet import gl

        vlist = self._vertex_lists.get(group)
        if vlist is None:
            return

        program = self.program()
        program.use()
        self._apply_camera_uniforms(program)
        for name, value in self._light_uniforms.items():
            program[name] = value
        program["u_base_color"] = self._base_color()
        program["u_flat"] = 1 if self.flat else 0
        model = self.uniform_data("model_uniforms")
        program["u_model"] = tuple(model) if len(model) == 16 else _IDENTITY_4
        program["u_alpha"] = self.alpha
        has_face_data = self._flush_face_data()
        program["u_has_face_data"] = 1 if has_face_data else 0
        for _fmt, unit, uniform in self._face_buffers.values():
            program[uniform] = unit
        ghost = self.alpha < 1.0

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glCullFace(gl.GL_BACK)
        if self.polygon_offset:
            # Faces leicht nach hinten, damit das Linien-Overlay (GL_LEQUAL)
            # nicht mit ihnen z-fightet (Playground-Verhalten, E40).
            gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
            gl.glPolygonOffset(1.0, 1.0)
        if ghost:
            blend_was_enabled = gl.glIsEnabled(gl.GL_BLEND)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDepthMask(gl.GL_FALSE)
        vlist.draw(gl.GL_TRIANGLES)
        if ghost:
            gl.glDepthMask(gl.GL_TRUE)
            if not blend_was_enabled:
                gl.glDisable(gl.GL_BLEND)
        if self.polygon_offset:
            gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_DEPTH_TEST)
        self._unbind_face_data()
