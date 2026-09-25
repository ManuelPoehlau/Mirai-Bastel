"""GLRenderStore — production drawable `ResourceStore` (AD-018 §5, Option B).

Ships the real draw path `VIEWPORT_V02_ARCHITECTURE.md` §4.2 specifies
(`RenderMesh.render(camera)` "issue draw call") and Gate 5 deferred as a
scoping choice (`docs/WP-04_GATE_5_COMPLETION.md`): one real, persistent,
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

from .resource_store import ResourceStore

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
uniform vec3 u_base_color;

out vec4 out_color;

void main() {
    vec3 n = normalize(v_normal);
    float ndl = max(dot(n, normalize(u_light_dir)), 0.0);
    vec3 shaded = mix(u_base_color * 0.35, u_base_color, ndl);
    vec3 highlighted = mix(shaded, vec3(1.0, 0.82, 0.15), clamp(v_highlight, 0.0, 1.0));
    out_color = vec4(highlighted, 1.0);
}
"""

LIGHT_DIR = (0.4, 0.6, 0.7)
DEFAULT_BASE_COLOR = (0.72, 0.75, 0.82)


def _build_program():
    """Compiles the shared `ShaderProgram`. Requires an active GL context."""
    import pyglet
    from pyglet.graphics.shader import Shader, ShaderProgram

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
        self._cpu[name] = []
        self.stats.count("gpu_resource_creations")
        self.stats.snapshot_resource(res)

    def update(self, name: str, offset: int, data: list, nbytes: int) -> None:
        res = self._ensure(name)
        buf = self._cpu.setdefault(name, [])
        needed = offset + len(data)
        if len(buf) < needed:
            buf.extend([0.0] * (needed - len(buf)))
        buf[offset:offset + len(data)] = data
        res.updates += 1
        res.bytes_uploaded += nbytes
        self.stats.add_upload(nbytes)
        self.stats.snapshot_resource(res)

        group = self._group_of(name)
        if group is None:
            return  # declared uniform (or undeclared name) - pure CPU storage
        if group in self._rebuild_active:
            return  # buffered only; end_rebuild() assembles the VertexList
        self._patch_attribute(group, name, buf)

    def destroy(self, name: str) -> None:
        res = self._resources.pop(name, None)
        if res is not None:
            self._cpu.pop(name, None)
            self.stats.count("gpu_resource_destroys")

    # -- vertex-group assembly ------------------------------------------------

    def _group_of(self, name: str) -> str | None:
        for group, (attributes, index) in self._groups.items():
            if name in attributes or name == index:
                return group
        return None

    def _patch_attribute(self, group: str, name: str, data: list[float]) -> None:
        """Content-only patch into the existing, persistent VertexList - no
        reallocation (GPU Resource Persistence, VIEWPORT_V02_ARCHITECTURE.md §7).
        Called for every `update()` outside a `begin_rebuild()`/`end_rebuild()`
        bracket, i.e. exactly the partial-update paths in
        `RenderMesh._sync_geometry()`/`_sync_selection()`."""
        vlist = self._vertex_lists.get(group)
        if vlist is None:
            return
        attributes, index_name = self._groups[group]
        if name == index_name:
            return  # index buffer only ever changes via a structural rebuild
        attr_name, _components = attributes[name]
        getattr(vlist, attr_name)[0:len(data)] = data

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
        program["u_light_dir"] = LIGHT_DIR
        program["u_base_color"] = self._base_color()

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glCullFace(gl.GL_BACK)
        vlist.draw(gl.GL_TRIANGLES)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_DEPTH_TEST)
