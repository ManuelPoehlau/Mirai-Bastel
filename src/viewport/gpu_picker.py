"""GPU ID-buffer picking from the `RenderMesh` buffers (AD-022 B2-out, 2026-10-21).

Promoted from the stage-2 prototype (`experiments/topology_stage2_delete/gpu_pick.py`, `gl_PrimitiveID` exact on
the reference driver) and the spike's depth oracle (`experiments/gpu_picking_spike/id_picker.py`), adapted to the
production slot layout of `RenderMesh` (AD-023 §9). Outside `GLRenderStore` (AD-018 §5/§7: the store keeps its one
drawable group); it draws the store's public VertexList with its own programs, like the overlays do.

Passes into one offscreen framebuffer (three RGBA8 colour targets, one depth buffer), each rendered only when a pick
needs it and cached per (buffer content, camera, model matrix, size, occlusion):

- **faces** (always, it also writes the depth): the `RenderMesh` triangles; colour = `gl_PrimitiveID + 1`, i.e. the
  triangle slot (pyglet issues one `glDrawElements` per VertexList, so the count starts at 0); free slots are
  degenerate and draw nothing. Pushed back by `glPolygonOffset(1, 1)` like the production draw. No back-face culling
  (the CPU picker hits back faces too).
- **edges**: the edge slots of `RenderMesh.edge_indices` as `GL_LINES` from an own element buffer over the same
  vertex buffer (`glDrawElementsBaseVertex`); colour = `gl_PrimitiveID + 1` = edge slot. Free slots are zero-length
  lines (no fragments).
- **points**: every vertex slot as a 1 px point (`glDrawArrays`), colour = `gl_VertexID - start + 1`; free slots hold
  `DEAD_POSITION` and are moved outside the clip volume.

Edges and points are depth-tested (LEQUAL, no depth write) against the faces when `occlusion` is on, else drawn
without a depth test (Wireframe: everything pickable). Every program binds `position` at the location the store's
program uses (`layout(location = …)`, AD-022 §3: an unused attribute was dropped once on the reference driver).

Reads: `face_at` (the pixel under the cursor, centre convention), `vertices_near` / `edges_near` (the IDs in a square
window), `visibility` (the depth oracle for Box: a point is visible when its window depth is at most the buffer's).
The exact decision among the candidates (screen distance) stays with the caller (`mirai.viewport.gpu_picking`).
"""

from __future__ import annotations

import ctypes
import math
from array import array

from .render_mesh import DEAD_COORD

FACES, EDGES, POINTS = 0, 1, 2
_IDENTITY_4 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
#: Edge slots closer than this are uploaded as one range.
_EDGE_MERGE_GAP = 256

_VS = """
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
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);  // free slot: outside the clip volume
    }} else {{
        vec4 world = u_model * vec4(position, 1.0);  // the production VERTEX_SRC expression, bit for bit
        gl_Position = u_proj * u_view * world;
    }}
}}
"""

_FS_PRIMITIVE = """
#version 330 core
out vec4 frag;
void main() {
    uint id = uint(gl_PrimitiveID) + 1u;
    frag = vec4(float(id & 255u), float((id >> 8u) & 255u), float((id >> 16u) & 255u), 255.0) / 255.0;
}
"""

_FS_VERTEX = """
#version 330 core
flat in int v_slot;
out vec4 frag;
void main() {
    uint id = uint(v_slot) + 1u;
    frag = vec4(float(id & 255u), float((id >> 8u) & 255u), float((id >> 16u) & 255u), 255.0) / 255.0;
}
"""


def _decode(raw: bytes) -> list[int]:
    words = array("I")
    words.frombytes(raw)
    return [(w & 0xFFFFFF) - 1 for w in words]


def _runs(slots, gap: int) -> list[tuple[int, int]]:
    """[lo, hi) slot ranges covering `slots`, joined across gaps below `gap`."""
    ranges: list[tuple[int, int]] = []
    for slot in sorted(slots):
        if ranges and slot <= ranges[-1][1] + gap:
            ranges[-1] = (ranges[-1][0], slot + 1)
        else:
            ranges.append((slot, slot + 1))
    return ranges


class GpuPicker:
    """One per window (GL context). Needs a `RenderMesh` with a `GLRenderStore` whose VertexList exists."""

    def __init__(self) -> None:
        self._programs = None
        self._fbo = None
        self._renderbuffers = None
        self._size = (0, 0)
        self._state = None
        self._done: set[int] = set()
        self._edge_ebo = 0
        self._edge_owner = None  # (id(render_mesh), layout_revision) the element buffer holds
        self._edge_floats = 0
        self.renders = 0

    # -- availability -------------------------------------------------------------------------------

    @staticmethod
    def can_pick(render_mesh) -> bool:
        from .gl_render_store import GLRenderStore

        store = render_mesh.store
        return (
            isinstance(store, GLRenderStore)
            and store.vertex_list() is not None
            and len(store.uniform_data("camera_uniforms")) == 32
        )

    # -- GL resources -------------------------------------------------------------------------------

    def _build_programs(self):
        from pyglet.graphics.shader import Shader, ShaderProgram

        from .gl_render_store import GLRenderStore

        loc = GLRenderStore.program().attributes["position"]["location"]
        vs = _VS.format(loc=loc, dead=f"{DEAD_COORD * 0.1:.1e}")
        primitive = ShaderProgram(Shader(vs, "vertex"), Shader(_FS_PRIMITIVE, "fragment"))
        vertex = ShaderProgram(Shader(vs, "vertex"), Shader(_FS_VERTEX, "fragment"))
        return primitive, vertex

    def _ensure_fbo(self, width: int, height: int) -> None:
        from pyglet import gl

        if self._fbo is not None and self._size == (width, height):
            return
        self._release_fbo()
        fbo = gl.GLuint()
        gl.glGenFramebuffers(1, ctypes.byref(fbo))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        buffers = (gl.GLuint * 4)()
        gl.glGenRenderbuffers(4, buffers)
        for i in range(3):
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, buffers[i])
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_RGBA8, width, height)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0 + i, gl.GL_RENDERBUFFER, buffers[i])
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, buffers[3])
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, width, height)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, buffers[3])
        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, 0)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"ID framebuffer incomplete (status 0x{status:x})")
        self._fbo, self._renderbuffers, self._size = fbo, buffers, (width, height)
        self._state = None

    def _release_fbo(self) -> None:
        if self._fbo is None:
            return
        from pyglet import gl

        gl.glDeleteRenderbuffers(4, self._renderbuffers)
        gl.glDeleteFramebuffers(1, ctypes.byref(self._fbo))
        self._fbo = None

    def release(self) -> None:
        from pyglet import gl

        self._release_fbo()
        if self._edge_ebo:
            gl.glDeleteBuffers(1, ctypes.byref(gl.GLuint(self._edge_ebo)))
            self._edge_ebo = 0
            self._edge_owner = None

    def _sync_edge_buffer(self, rm) -> None:
        """Uploads the edge slots `RenderMesh` changed since the last upload (all of them for a new
        mesh or a new layout)."""
        from pyglet import gl

        changes = rm.take_edge_changes()
        owner = (id(rm), rm.layout_revision)
        data = rm.edge_indices
        if not self._edge_ebo:
            buffer = gl.GLuint()
            gl.glGenBuffers(1, ctypes.byref(buffer))
            self._edge_ebo = buffer.value
        gl.glBindBuffer(gl.GL_COPY_WRITE_BUFFER, self._edge_ebo)
        address = data.buffer_info()[0]
        if changes is None or owner != self._edge_owner or self._edge_floats != len(data):
            gl.glBufferData(gl.GL_COPY_WRITE_BUFFER, max(4, len(data) * 4), address if data else None,
                            gl.GL_DYNAMIC_DRAW)
        else:
            for lo, hi in _runs(changes, _EDGE_MERGE_GAP):
                gl.glBufferSubData(gl.GL_COPY_WRITE_BUFFER, lo * 8, (hi - lo) * 8, address + lo * 8)
        gl.glBindBuffer(gl.GL_COPY_WRITE_BUFFER, 0)
        self._edge_owner = owner
        self._edge_floats = len(data)

    # -- render -------------------------------------------------------------------------------------

    def prepare(self, rm, width: int, height: int, *, occlusion: bool, target: int) -> None:
        """Makes `target` (and the faces / depth) current for this mesh state and view."""
        store = rm.store
        camera = tuple(store.uniform_data("camera_uniforms"))
        model = store.uniform_data("model_uniforms")
        model = tuple(model) if len(model) == 16 else _IDENTITY_4
        state = (id(rm), rm.content_revision, rm.layout_revision, camera, model, width, height, occlusion)
        self._ensure_fbo(width, height)
        if state != self._state:
            self._state = state
            self._done = set()
        if FACES not in self._done:
            self._render(rm, width, height, FACES, occlusion, camera, model)
            self._done.add(FACES)
        if target != FACES and target not in self._done:
            self._render(rm, width, height, target, occlusion, camera, model)
            self._done.add(target)

    def _render(self, rm, width: int, height: int, target: int, occlusion: bool, camera, model) -> None:
        from pyglet import gl

        if self._programs is None:
            self._programs = self._build_programs()
        primitive, vertex = self._programs
        vlist = rm.store.vertex_list()
        if target == EDGES:
            self._sync_edge_buffer(rm)
        self.renders += 1

        old_viewport = (gl.GLint * 4)()
        gl.glGetIntegerv(gl.GL_VIEWPORT, old_viewport)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)
        gl.glViewport(0, 0, width, height)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glDrawBuffers(1, (gl.GLenum * 1)(gl.GL_COLOR_ATTACHMENT0 + target))
        program = vertex if target == POINTS else primitive
        program.use()
        program["u_view"] = camera[0:16]
        program["u_proj"] = camera[16:32]
        program["u_model"] = model
        if target == POINTS:
            program["u_start"] = int(vlist.start)
        domain = vlist.domain
        try:
            if target == FACES:
                gl.glDepthMask(gl.GL_TRUE)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthFunc(gl.GL_LESS)
                gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
                gl.glPolygonOffset(1.0, 1.0)
                vlist.draw(gl.GL_TRIANGLES)
                gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)
            else:
                gl.glClear(gl.GL_COLOR_BUFFER_BIT)
                gl.glDepthMask(gl.GL_FALSE)
                if occlusion:
                    gl.glEnable(gl.GL_DEPTH_TEST)
                    gl.glDepthFunc(gl.GL_LEQUAL)
                else:
                    gl.glDisable(gl.GL_DEPTH_TEST)
                domain.vao.bind()
                for buffer, _ in domain.buffer_attributes:
                    buffer.commit()
                if target == POINTS:
                    gl.glDrawArrays(gl.GL_POINTS, vlist.start, vlist.count)
                else:
                    gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self._edge_ebo)
                    gl.glDrawElementsBaseVertex(
                        gl.GL_LINES, len(rm.edge_indices), gl.GL_UNSIGNED_INT, None, vlist.start
                    )
                    # The element binding is VAO state: give pyglet its index buffer back.
                    domain.index_buffer.bind_to_index_buffer()
                domain.vao.unbind()
        finally:
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDepthFunc(gl.GL_LESS)
            gl.glDisable(gl.GL_DEPTH_TEST)
            program.stop()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            gl.glViewport(*old_viewport)

    # -- reads --------------------------------------------------------------------------------------

    def _read(self, target: int, x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int, list[int]] | None:
        from pyglet import gl

        width, height = self._size
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(width - 1, x1), min(height - 1, y1)
        if x1 < x0 or y1 < y0:
            return None
        w, h = x1 - x0 + 1, y1 - y0 + 1
        buf = (gl.GLubyte * (w * h * 4))()
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._fbo)
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0 + target)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        gl.glReadPixels(x0, y0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, buf)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
        return x0, y0, w, h, _decode(bytes(buf))

    def ids_in(self, target: int, x0: int, y0: int, x1: int, y1: int) -> set[int]:
        """Slots (triangle / edge / vertex) with a pixel in [x0, x1] x [y0, y1] (inclusive, clamped)."""
        block = self._read(target, x0, y0, x1, y1)
        if block is None:
            return set()
        found = set(block[4])
        found.discard(-1)
        return found

    def face_at(self, rm, x: float, y: float):
        """The face whose triangle covers the pixel of (x, y), or None."""
        px, py = math.floor(x), math.floor(y)
        found = self._read(FACES, px, py, px, py)
        if found is None or found[4][0] < 0:
            return None
        return rm.face_of_triangle(found[4][0])

    def vertices_near(self, rm, x: float, y: float, radius: float) -> set:
        found = self.ids_in(POINTS, math.floor(x - radius), math.floor(y - radius),
                            math.floor(x + radius), math.floor(y + radius))
        return {v for v in map(rm.vertex_of_slot, found) if v is not None}

    def edges_near(self, rm, x: float, y: float, radius: float) -> set:
        found = self.ids_in(EDGES, math.floor(x - radius), math.floor(y - radius),
                            math.floor(x + radius), math.floor(y + radius))
        return {e for e in map(rm.edge_of_slot, found) if e is not None}

    def faces_in(self, rm, x0: float, y0: float, x1: float, y1: float) -> set:
        """Faces with a visible pixel in the rectangle."""
        found = self.ids_in(FACES, math.floor(x0), math.floor(y0), math.floor(x1), math.floor(y1))
        return {f for f in map(rm.face_of_triangle, found) if f is not None}

    def _block(self, x0: float, y0: float, x1: float, y1: float):
        width, height = self._size
        bx0, by0 = max(0, math.floor(x0)), max(0, math.floor(y0))
        bx1, by1 = min(width - 1, math.floor(x1)), min(height - 1, math.floor(y1))
        if bx1 < bx0 or by1 < by0:
            return None
        return bx0, by0, bx1 - bx0 + 1, by1 - by0 + 1

    def _pixel_of(self, block):
        """`pixel(point)` -> (index into the block, window depth) of an object-space point, with the
        matrices of the face pass; None if it is clipped (behind the eye, outside the depth range) or
        outside the block."""
        width, height = self._size
        bx0, by0, w, h = block
        camera, model = self._state[3], self._state[4]
        m = _mat_mul(_mat_mul(camera[16:32], camera[0:16]), model)

        def pixel(point):
            x, y, z = point
            cw = m[3] * x + m[7] * y + m[11] * z + m[15]
            if cw <= 0.0:
                return None
            cx = m[0] * x + m[4] * y + m[8] * z + m[12]
            cy = m[1] * x + m[5] * y + m[9] * z + m[13]
            cz = m[2] * x + m[6] * y + m[10] * z + m[14]
            if cz < -cw or cz > cw:
                # Outside the depth range (clipped, no depth-buffer pixel). In ortho `cw` is always 1,
                # so this is the only test that rejects a point behind the ray origins (WP Ortho / Views).
                return None
            px = math.floor((cx / cw + 1.0) * 0.5 * width) - bx0
            py = math.floor((cy / cw + 1.0) * 0.5 * height) - by0
            if not (0 <= px < w and 0 <= py < h):
                return None
            return py * w + px, (cz / cw + 1.0) * 0.5

        return pixel

    def visibility(self, x0: float, y0: float, x1: float, y1: float):
        """Depth oracle over the rectangle: `visible(point)` for an object-space point - its window
        depth (same matrices as the face pass) at most the face depth at its pixel. A point behind
        the eye or outside the read rectangle counts as not visible."""
        from pyglet import gl

        block = self._block(x0, y0, x1, y1)
        if block is None:
            return lambda point: False
        bx0, by0, w, h = block
        buf = (gl.GLfloat * (w * h))()
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._fbo)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        gl.glReadPixels(bx0, by0, w, h, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, buf)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
        pixel = self._pixel_of(block)

        def visible(point) -> bool:
            hit = pixel(point)
            return hit is not None and hit[1] <= buf[hit[0]]

        return visible

    def face_lookup(self, rm, x0: float, y0: float, x1: float, y1: float):
        """`face_under(point)`: the face drawn at an object-space point's pixel (None if none or
        outside the rectangle)."""
        block = self._block(x0, y0, x1, y1)
        if block is None:
            return lambda point: None
        bx0, by0, w, h = block
        ids = self._read(FACES, bx0, by0, bx0 + w - 1, by0 + h - 1)[4]
        pixel = self._pixel_of(block)

        def face_under(point):
            hit = pixel(point)
            if hit is None or ids[hit[0]] < 0:
                return None
            return rm.face_of_triangle(ids[hit[0]])

        return face_under


def _mat_mul(a, b) -> list[float]:
    """Column-major 4x4 product a·b."""
    out = [0.0] * 16
    for col in range(4):
        for row in range(4):
            out[col * 4 + row] = sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
    return out
