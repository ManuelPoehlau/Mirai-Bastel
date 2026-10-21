"""AD-022 B2-out for hover and click: an ID pass outside `GLRenderStore` that draws the store's own VertexList.

No buffers of its own (B1 built ~0.8 s of them per mesh state on the reference PC): the face pass draws the
`RenderMesh` triangles with a second program and writes `gl_PrimitiveID + 1` (the triangle number in index-buffer
order; pyglet draws one VertexList with one `glDrawElements`, so it starts at 0); the triangle maps to its face
through `RenderMesh._triangle_face_rows` and the row table (`render_patch.row_face`). The point pass draws the same
vertex buffer with `glDrawArrays(GL_POINTS)` and writes `gl_VertexID - start + 1` (the vertex slot); dead slots
(`render_patch.DEAD_POSITION`) are clipped in the vertex shader. `position` is bound to the location the store's
program uses (`layout(location = …)`, AD-022 §3 B2: an unused attribute was dropped once on the reference driver).

Only the modes that the Delete path re-picks: **face and vertex**. Edge mode, object mode, the Knife, Box/Paint
and every headless path keep the CPU picker (`pick_component`); so does a viewport without a `GLRenderStore`.

Pick rules (the spike's `ids` variant, AD-022 §3): face = the ID at the cursor's pixel (pixel centre, §4.2);
vertex = among the slots found within 14 px, the one nearest the cursor by exact screen distance; points are
depth-tested against the faces (polygon offset 1, 1 like the production draw) while faces are shown, else not
(Wireframe). No back-face culling (the CPU picker hits back faces too).

Ordering (AD-022 §5 "Hover coalescing does not fit as is"): before it renders, the picker syncs the edit
`RenderMesh` if anything is pending (a delta, a topology / geometry / camera change), so a pick right after a
Delete or an Undo reads the new buffers, never the previous mesh state. The ID render is cached per (buffer
content, camera, model matrix, size, occlusion, mode).
"""

from __future__ import annotations

import ctypes
import math
import time
from array import array
from dataclasses import dataclass

from topology_stage2_delete import render_patch

_VS_FACE = """
#version 330 core
layout(location = {loc}) in vec3 position;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform mat4 u_model;
void main() {{
    vec4 world = u_model * vec4(position, 1.0);  // the production VERTEX_SRC expression, bit for bit
    gl_Position = u_proj * u_view * world;
}}
"""

_FS_FACE = """
#version 330 core
out vec4 frag;
void main() {
    uint id = uint(gl_PrimitiveID) + 1u;
    frag = vec4(float(id & 255u), float((id >> 8u) & 255u), float((id >> 16u) & 255u), 255.0) / 255.0;
}
"""

_VS_POINT = """
#version 330 core
layout(location = {loc}) in vec3 position;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform mat4 u_model;
uniform int u_start;
flat out int v_slot;
void main() {{
    v_slot = gl_VertexID - u_start;
    if (position.x > {dead}) {{
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);  // dead slot: outside the clip volume
    }} else {{
        vec4 world = u_model * vec4(position, 1.0);
        gl_Position = u_proj * u_view * world;
    }}
}}
"""

_FS_POINT = """
#version 330 core
flat in int v_slot;
out vec4 frag;
void main() {
    uint id = uint(v_slot) + 1u;
    frag = vec4(float(id & 255u), float((id >> 8u) & 255u), float((id >> 16u) & 255u), 255.0) / 255.0;
}
"""

FACES, POINTS = 0, 1
VERTEX_RADIUS_PX = 14.0
_IDENTITY_4 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


@dataclass
class Stats:
    picks: int = 0
    renders: int = 0
    syncs_before_pick: int = 0
    cpu_fallbacks: int = 0
    render_ms: float = 0.0
    read_ms: float = 0.0

    def text(self) -> str:
        return (f"GPU picks {self.picks} (ID renders {self.renders}, {self.render_ms:.1f} ms; reads {self.read_ms:.1f} ms; "
                f"syncs before a pick {self.syncs_before_pick}); CPU picker used {self.cpu_fallbacks}x")


STATS = Stats()


def _decode(words) -> list[int]:
    return [(w & 0xFFFFFF) - 1 for w in words]


class GpuPicker:
    """One per `Application` (GL context of the window). `pick(app, x, y)` -> element, None, or `CPU`."""

    CPU = object()

    def __init__(self) -> None:
        self._programs = None
        self._fbo = None
        self._size = (0, 0)
        self._key = None
        self._mode = None

    # -- GL resources -------------------------------------------------------------------------------------

    def _build_programs(self):
        from pyglet.graphics.shader import Shader, ShaderProgram

        from viewport.gl_render_store import GLRenderStore

        loc = GLRenderStore.program().attributes["position"]["location"]
        dead = f"{render_patch.DEAD_COORD * 0.1:.1e}"
        face = ShaderProgram(Shader(_VS_FACE.format(loc=loc), "vertex"), Shader(_FS_FACE, "fragment"))
        point = ShaderProgram(Shader(_VS_POINT.format(loc=loc, dead=dead), "vertex"), Shader(_FS_POINT, "fragment"))
        return face, point

    def _ensure_fbo(self, width: int, height: int) -> None:
        from pyglet import gl

        if self._fbo is not None and self._size == (width, height):
            return
        self.release_fbo()
        fbo = gl.GLuint()
        gl.glGenFramebuffers(1, ctypes.byref(fbo))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        buffers = (gl.GLuint * 3)()
        gl.glGenRenderbuffers(3, buffers)
        for i in range(2):
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, buffers[i])
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_RGBA8, width, height)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0 + i, gl.GL_RENDERBUFFER,
                                         buffers[i])
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, buffers[2])
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, width, height)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, buffers[2])
        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, 0)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"ID framebuffer incomplete (status 0x{status:x})")
        self._fbo, self._renderbuffers, self._size = fbo, buffers, (width, height)
        self._key = None

    def release_fbo(self) -> None:
        if self._fbo is None:
            return
        from pyglet import gl

        gl.glDeleteRenderbuffers(3, self._renderbuffers)
        gl.glDeleteFramebuffers(1, ctypes.byref(self._fbo))
        self._fbo = None

    # -- render -------------------------------------------------------------------------------------------

    def render(self, rm, width: int, height: int, *, points: bool, occlusion: bool) -> None:
        """Draws the face IDs (always: the depth for the points) and, if `points`, the vertex slots."""
        from pyglet import gl

        if self._programs is None:
            self._programs = self._build_programs()
        self._ensure_fbo(width, height)
        vlist = rm.store.vertex_list()
        camera = rm.store.uniform_data("camera_uniforms")
        model = rm.store.uniform_data("model_uniforms")
        model = tuple(model) if len(model) == 16 else _IDENTITY_4
        face_prog, point_prog = self._programs

        old_viewport = (gl.GLint * 4)()
        gl.glGetIntegerv(gl.GL_VIEWPORT, old_viewport)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)
        gl.glViewport(0, 0, width, height)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)

        gl.glDrawBuffers(1, (gl.GLenum * 1)(gl.GL_COLOR_ATTACHMENT0 + FACES))
        gl.glDepthMask(gl.GL_TRUE)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
        gl.glPolygonOffset(1.0, 1.0)
        face_prog.use()
        face_prog["u_view"] = tuple(camera[0:16])
        face_prog["u_proj"] = tuple(camera[16:32])
        face_prog["u_model"] = model
        vlist.draw(gl.GL_TRIANGLES)
        gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)

        if points:
            gl.glDrawBuffers(1, (gl.GLenum * 1)(gl.GL_COLOR_ATTACHMENT0 + POINTS))
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glDepthMask(gl.GL_FALSE)
            gl.glDepthFunc(gl.GL_LEQUAL)
            if not occlusion:
                gl.glDisable(gl.GL_DEPTH_TEST)
            point_prog.use()
            point_prog["u_view"] = tuple(camera[0:16])
            point_prog["u_proj"] = tuple(camera[16:32])
            point_prog["u_model"] = model
            point_prog["u_start"] = int(vlist.start)
            domain = vlist.domain
            domain.vao.bind()
            for buffer, _ in domain.buffer_attributes:
                buffer.commit()
            gl.glDrawArrays(gl.GL_POINTS, vlist.start, vlist.count)

        gl.glDepthMask(gl.GL_TRUE)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glUseProgram(0)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glViewport(*old_viewport)

    def read(self, target: int, x0: int, y0: int, x1: int, y1: int) -> list[int]:
        """Element indices (-1 = nothing) in [x0, x1] x [y0, y1] (inclusive, clamped), row by row."""
        from pyglet import gl

        width, height = self._size
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(width - 1, x1), min(height - 1, y1)
        if x1 < x0 or y1 < y0:
            return []
        w, h = x1 - x0 + 1, y1 - y0 + 1
        buf = (gl.GLubyte * (w * h * 4))()
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._fbo)
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0 + target)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        gl.glReadPixels(x0, y0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, buf)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
        words = array("I")
        words.frombytes(bytes(buf))
        return _decode(words)

    # -- pick ---------------------------------------------------------------------------------------------

    def prepare(self, app, *, points: bool) -> object:
        """Syncs the edit RenderMesh if needed and renders the ID targets if the cached ones are stale.
        Returns the RenderMesh, or `CPU` if this viewport cannot serve a GPU pick."""
        from viewport.gl_render_store import GLRenderStore

        viewport = app.viewport
        rm = viewport.render_mesh if viewport is not None else None
        if rm is None or not isinstance(rm.store, GLRenderStore) or rm.camera is None:
            return self.CPU
        st = render_patch.slots(rm)
        dirty = rm.dirty
        if st.pending or dirty.topology or dirty.geometry or dirty.camera or rm._model_dirty:
            STATS.syncs_before_pick += 1
            rm.sync()
        if rm.store.vertex_list() is None:
            return self.CPU
        width, height = int(app.viewport_width), int(app.viewport_height)
        occlusion = bool(app.display.show_faces)
        key = (st.content_rev, st.layout_rev, tuple(rm.store.uniform_data("camera_uniforms")),
               tuple(rm.store.uniform_data("model_uniforms")), width, height, occlusion, points, id(rm))
        if key != self._key:
            start = time.perf_counter()
            self.render(rm, width, height, points=points, occlusion=occlusion)
            STATS.render_ms += (time.perf_counter() - start) * 1000.0
            STATS.renders += 1
            self._key = key
        return rm

    def pick(self, app, x: float, y: float):
        from core.selection import SelectionMode

        mode = app.selection.mode
        if mode not in (SelectionMode.FACE, SelectionMode.VERTEX):
            STATS.cpu_fallbacks += 1
            return self.CPU
        rm = self.prepare(app, points=mode is SelectionMode.VERTEX)
        if rm is self.CPU:
            STATS.cpu_fallbacks += 1
            return self.CPU
        STATS.picks += 1
        mesh = app.scene.mesh
        start = time.perf_counter()
        try:
            if mode is SelectionMode.FACE:
                px, py = math.floor(x), math.floor(y)
                found = self.read(FACES, px, py, px, py)
                if not found or found[0] < 0:
                    return None
                rows = rm._triangle_face_rows
                t = found[0]
                if t >= len(rows):
                    return None
                face = render_patch.row_face(rm)[rows[t]]
                return face if face is not None and mesh.is_valid_face(face) else None
            r = VERTEX_RADIUS_PX
            found = set(self.read(POINTS, math.floor(x - r), math.floor(y - r), math.floor(x + r), math.floor(y + r)))
            found.discard(-1)
            table = render_patch.slot_vertex(rm)
            project = app._edit_camera.project_to_screen
            width, height = self._size
            best = None
            for slot in found:
                if slot >= len(table):
                    continue
                v = table[slot]
                if v is None or not mesh.is_valid_vertex(v):
                    continue
                p = project(mesh.vertex_position(v), width, height)
                if p is None:
                    continue
                d = math.hypot(p[0] - x, p[1] - y)
                if d < r and (best is None or (d, slot) < best):
                    best = (d, slot)
            return None if best is None else table[best[1]]
        finally:
            STATS.read_ms += (time.perf_counter() - start) * 1000.0


def reset_stats() -> None:
    for name in Stats.__dataclass_fields__:
        setattr(STATS, name, type(getattr(STATS, name))())
