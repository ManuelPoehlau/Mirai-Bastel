"""GPU ID-buffer picker (spike, not production): faces, edges and vertices drawn with their ID as
colour into an offscreen framebuffer; a pick reads a few pixels back.

One render per camera state (`render`), three colour targets sharing one depth buffer:

- target 0, faces: every triangle carries its face's ID (no back-face culling - the CPU picker
  hits back faces too). Pushed back by `glPolygonOffset(1, 1)` like the production draw, so
  edges and vertices on the surface pass the depth test.
- target 1, edges: 1 px lines, depth-tested (LEQUAL, no depth write) against the faces when
  `occlusion` is on, else drawn without a depth test (Wireframe).
- target 2, vertices: 1 px points, same depth rule.

A pick reads the pixels within the pick radius from the mode's target, decodes the IDs found
there and decides between those few candidates with the same exact screen distance the CPU
picker uses (`camera.project_to_screen` per candidate only). Visibility is therefore "some pixel
of the element survived the depth test", not the CPU's ray test at the nearest point with
`DEPTH_TOLERANCE` - the spike measures where the two disagree.

Variant "depth oracle" (`*_depth` methods): the faces' depth buffer answers "is this point
visible?" for any point - project it, compare its window depth with the buffer at its pixel. The
candidates then come from the CPU as today (every element whose corners lie in the Box; for a
hover the IDs found in the window plus their one-ring neighbours), so a pixel holding only one
ID no longer hides the other elements in it. The polygon offset of the face pass (slope-scaled)
is the tolerance.

IDs ride in a per-vertex attribute (`pick_id`, the element's index in mesh order + 1, flat), so
the face pass needs no `gl_PrimitiveID` (open driver question on the reference PC,
`REFERENCE_HARDWARE.md` §2) at the cost of its own unindexed buffers (3 vertices per triangle,
2 per edge). A production version would draw from the `RenderMesh` buffers (AD-018) instead.
Only an unplaced edit object (identity model matrix) - enough for the measurement.
"""

from __future__ import annotations

import ctypes
import math
from array import array

from viewport.derived import triangulate_mesh_face

ID_VERTEX_SRC = """
#version 330 core
in vec3 position;
in float pick_id;
uniform mat4 u_view;
uniform mat4 u_proj;
flat out float v_id;
void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    v_id = pick_id;
}
"""

ID_FRAGMENT_SRC = """
#version 330 core
flat in float v_id;
out vec4 frag;
void main() {
    uint id = uint(v_id + 0.5);
    frag = vec4(float(id & 255u), float((id >> 8u) & 255u), float((id >> 16u) & 255u), 255.0) / 255.0;
}
"""

FACES, EDGES, VERTICES = 0, 1, 2
#: Largest ID the 24-bit colour encoding (and a float attribute) carries exactly.
MAX_ID = (1 << 24) - 1
#: The CPU picker's radii (`picking.pick_nearest_vertex` / `pick_nearest_edge` defaults).
VERTEX_RADIUS_PX = 14.0
EDGE_RADIUS_PX = 9.0


def encode_id(index: int) -> tuple[int, int, int]:
    """RGB bytes for element `index` (0-based mesh order); (0, 0, 0) = nothing."""
    value = index + 1
    if not 0 < value <= MAX_ID:
        raise ValueError(f"element index {index} does not fit 24 bits")
    return value & 255, (value >> 8) & 255, (value >> 16) & 255


def decode_ids(rgba: bytes) -> set[int]:
    """0-based element indices found in a tightly packed RGBA8 block (little-endian words:
    R | G << 8 | B << 16 | A << 24); background (0) dropped."""
    words = array("I")
    words.frombytes(rgba)
    return {(w & 0xFFFFFF) - 1 for w in set(words) if w & 0xFFFFFF}


def _point_segment_distance(px, py, ax, ay, bx, by) -> float:
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    return math.hypot(px - (ax + t * abx), py - (ay + t * aby))


class GpuIdPicker:
    """ID buffers for one mesh state; `render(camera)` per camera state, then any number of
    picks. Needs a current GL 3.3 context (a pyglet window)."""

    def __init__(self, mesh, width: int, height: int) -> None:
        from pyglet import gl
        from pyglet.graphics.shader import Shader, ShaderProgram

        self._gl = gl
        self.mesh = mesh
        self.width, self.height = int(width), int(height)
        self.vertex_ids = mesh.all_vertex_ids()
        self.edge_ids = mesh.all_edge_ids()
        self.face_ids = mesh.all_face_ids()
        if max(len(self.vertex_ids), len(self.edge_ids), len(self.face_ids)) > MAX_ID:
            raise ValueError("mesh too large for 24-bit IDs")
        self.program = ShaderProgram(Shader(ID_VERTEX_SRC, "vertex"), Shader(ID_FRAGMENT_SRC, "fragment"))
        self._lists = self._build_lists()
        self._fbo, self._renderbuffers = self._build_framebuffer()
        self.occlusion = True
        self._camera = None

    # -- GL resources ---------------------------------------------------------------

    def _build_lists(self) -> dict:
        gl, mesh = self._gl, self.mesh
        position = mesh.vertex_position
        lists = {}

        tri_pos: list[float] = []
        tri_ids: list[float] = []
        for index, fid in enumerate(self.face_ids):
            tag = float(index + 1)
            for tri in triangulate_mesh_face(mesh, fid):
                for vid in tri:
                    tri_pos.extend(position(vid))
                tri_ids += (tag, tag, tag)
        lists[FACES] = (gl.GL_TRIANGLES, self.program.vertex_list(
            len(tri_ids), gl.GL_TRIANGLES, position=("f", tri_pos), pick_id=("f", tri_ids)))

        edge_pos: list[float] = []
        edge_ids: list[float] = []
        for index, eid in enumerate(self.edge_ids):
            a, b = mesh.edge_vertices(eid)
            edge_pos.extend(position(a))
            edge_pos.extend(position(b))
            tag = float(index + 1)
            edge_ids += (tag, tag)
        lists[EDGES] = (gl.GL_LINES, self.program.vertex_list(
            len(edge_ids), gl.GL_LINES, position=("f", edge_pos), pick_id=("f", edge_ids)))

        point_pos: list[float] = []
        for vid in self.vertex_ids:
            point_pos.extend(position(vid))
        point_ids = [float(i + 1) for i in range(len(self.vertex_ids))]
        lists[VERTICES] = (gl.GL_POINTS, self.program.vertex_list(
            len(point_ids), gl.GL_POINTS, position=("f", point_pos), pick_id=("f", point_ids)))
        return lists

    def _build_framebuffer(self):
        gl = self._gl
        fbo = gl.GLuint()
        gl.glGenFramebuffers(1, ctypes.byref(fbo))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        buffers = (gl.GLuint * 4)()
        gl.glGenRenderbuffers(4, buffers)
        for i in range(3):
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, buffers[i])
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_RGBA8, self.width, self.height)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0 + i,
                                         gl.GL_RENDERBUFFER, buffers[i])
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, buffers[3])
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, self.width, self.height)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, buffers[3])
        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, 0)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"ID framebuffer incomplete (status 0x{status:x})")
        return fbo, buffers

    def _neighbours(self) -> dict:
        """vertex index -> indices of the vertices sharing an edge with it (per mesh state)."""
        if getattr(self, "_ring", None) is None:
            index = {vid: i for i, vid in enumerate(self.vertex_ids)}
            ring: dict = {i: [] for i in range(len(self.vertex_ids))}
            for eid in self.edge_ids:
                a, b = self.mesh.edge_vertices(eid)
                ring[index[a]].append(index[b])
                ring[index[b]].append(index[a])
            self._ring = ring
        return self._ring

    def release(self) -> None:
        gl = self._gl
        for _mode, vlist in self._lists.values():
            vlist.delete()
        gl.glDeleteRenderbuffers(4, self._renderbuffers)
        gl.glDeleteFramebuffers(1, ctypes.byref(self._fbo))

    # -- render (once per camera state) -----------------------------------------------

    def render(self, camera, *, occlusion: bool = True) -> None:
        """Draws the three ID targets for `camera` (`build_view_matrix` /
        `build_projection_matrix`, as `RenderMesh` uploads them)."""
        gl = self._gl
        self._camera = camera
        self.occlusion = occlusion
        program = self.program
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)
        gl.glViewport(0, 0, self.width, self.height)
        program.use()
        program["u_view"] = tuple(camera.build_view_matrix())
        program["u_proj"] = tuple(camera.build_projection_matrix(self.width / self.height))
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)

        self._draw_buffer(FACES)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
        gl.glPolygonOffset(1.0, 1.0)
        self._draw(FACES)
        gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)

        gl.glDepthMask(gl.GL_FALSE)
        gl.glDepthFunc(gl.GL_LEQUAL)
        if not occlusion:
            gl.glDisable(gl.GL_DEPTH_TEST)
        for target in (EDGES, VERTICES):
            self._draw_buffer(target)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            self._draw(target)

        gl.glDepthMask(gl.GL_TRUE)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        program.stop()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

    def _draw_buffer(self, target: int) -> None:
        gl = self._gl
        gl.glDrawBuffers(1, (gl.GLenum * 1)(gl.GL_COLOR_ATTACHMENT0 + target))

    def _draw(self, target: int) -> None:
        mode, vlist = self._lists[target]
        vlist.draw(mode)

    # -- read back --------------------------------------------------------------------

    def read_ids(self, target: int, x0: int, y0: int, x1: int, y1: int) -> set[int]:
        """Element indices in the pixel block [x0, x1] x [y0, y1] (inclusive, clamped)."""
        gl = self._gl
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.width - 1, x1), min(self.height - 1, y1)
        if x1 < x0 or y1 < y0:
            return set()
        w, h = x1 - x0 + 1, y1 - y0 + 1
        buf = (gl.GLubyte * (w * h * 4))()
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._fbo)
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0 + target)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        gl.glReadPixels(x0, y0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, buf)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
        return decode_ids(bytes(buf))

    def read_id_block(self, target: int, x0: int, y0: int, x1: int, y1: int):
        """(x0, y0, width, per-pixel element index or -1, row by row) of `target` in
        [x0, x1] x [y0, y1] (clamped), or None if the block is empty."""
        gl = self._gl
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.width - 1, x1), min(self.height - 1, y1)
        if x1 < x0 or y1 < y0:
            return None
        w, h = x1 - x0 + 1, y1 - y0 + 1
        buf = (gl.GLubyte * (w * h * 4))()
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._fbo)
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0 + target)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        gl.glReadPixels(x0, y0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, buf)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
        words = array("I")
        words.frombytes(bytes(buf))
        return x0, y0, w, h, [(word & 0xFFFFFF) - 1 for word in words]

    def read_depth(self, x0: int, y0: int, x1: int, y1: int):
        """(x0, y0, width, depth floats row by row) of the face depth in [x0, x1] x [y0, y1]
        (clamped), or None if the block is empty."""
        gl = self._gl
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.width - 1, x1), min(self.height - 1, y1)
        if x1 < x0 or y1 < y0:
            return None
        w, h = x1 - x0 + 1, y1 - y0 + 1
        buf = (gl.GLfloat * (w * h))()
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._fbo)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        gl.glReadPixels(x0, y0, w, h, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, buf)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
        return x0, y0, w, h, buf

    def _depth_test(self, depth, occlusion: bool):
        """`visible(point, screen)` against a `read_depth` block: the point's window depth
        (same view/projection as the ID pass) at most the buffer's at its pixel."""
        if not occlusion or depth is None:
            return lambda point, screen: True
        x0, y0, w, h, buf = depth
        view = self._camera.build_view_matrix()
        proj = self._camera.build_projection_matrix(self.width / self.height)
        m22, m32 = proj[10], proj[14]

        def visible(point, screen) -> bool:
            px, py = math.floor(screen[0]) - x0, math.floor(screen[1]) - y0
            if not (0 <= px < w and 0 <= py < h):
                return True  # outside the read block: no evidence (the caller reads its region)
            # eye-space z (column-major view matrix), then window depth in [0, 1]
            z_eye = view[2] * point[0] + view[6] * point[1] + view[10] * point[2] + view[14]
            if z_eye >= 0.0:
                return False
            z_window = ((m22 * z_eye + m32) / -z_eye + 1.0) * 0.5
            return z_window <= buf[py * w + px]

        return visible

    def elements_in_rect_depth(self, target: int, rect, *, occlusion: bool = True) -> set:
        """Box Select with the depth oracle: the CPU rule (corners inside; visibility of the
        vertex / edge midpoint / face centroid) with the depth buffer instead of the ray test.
        Candidates come from projecting every vertex (the per-camera O(V) the ID variant
        avoids) - a Box is one gesture, not a per-frame cost."""
        x0, y0, x1, y1 = rect
        mesh = self.mesh
        position = mesh.vertex_position
        project = self._camera.screen_projector(self.width, self.height)
        screen = {}
        for vid in self.vertex_ids:
            p = project(position(vid))
            if p is not None and x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
                screen[vid] = p
        visible = self._depth_test(
            self.read_depth(math.floor(x0), math.floor(y0), math.floor(x1), math.floor(y1)), occlusion)
        if target == VERTICES:
            return {vid for vid, p in screen.items() if visible(position(vid), p)}
        out = set()
        if target == EDGES:
            for eid in self.edge_ids:
                a, b = mesh.edge_vertices(eid)
                if a in screen and b in screen:
                    pa, pb = position(a), position(b)
                    mid = tuple(pa[i] + (pb[i] - pa[i]) * 0.5 for i in range(3))
                    if visible(mid, project(mid)):
                        out.add(eid)
            return out
        # A quad's centroid can lie behind its own (non-planar) triangles; the CPU test excludes
        # the face itself, so here the face's own ID at the centroid's pixel also counts.
        ids = self.read_id_block(FACES, math.floor(x0), math.floor(y0), math.floor(x1), math.floor(y1))
        for index, fid in enumerate(self.face_ids):
            corners = mesh.face_vertices(fid)
            if all(v in screen for v in corners):
                pts = [position(v) for v in corners]
                centroid = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
                at = project(centroid)
                if at is None:
                    continue
                if ids is not None:
                    bx0, by0, w, h, block = ids
                    px, py = math.floor(at[0]) - bx0, math.floor(at[1]) - by0
                    if 0 <= px < w and 0 <= py < h and block[py * w + px] == index:
                        out.add(fid)
                        continue
                if visible(centroid, at):
                    out.add(fid)
        return out

    def pick_vertex_depth(self, sx: float, sy: float, radius: float = VERTEX_RADIUS_PX):
        """Hover with the depth oracle: the vertex IDs in the window plus their one-ring
        neighbours (a vertex sharing a pixel with a found one is its neighbour on a dense mesh),
        each tested exactly (distance) and against the depth buffer (visibility)."""
        bx0, by0 = math.floor(sx - radius), math.floor(sy - radius)
        bx1, by1 = math.floor(sx + radius), math.floor(sy + radius)
        found = self.read_ids(VERTICES, bx0, by0, bx1, by1)
        ring = self._neighbours()
        candidates = set(found)
        for index in found:
            candidates.update(ring[index])
        visible = self._depth_test(self.read_depth(bx0, by0, bx1, by1), self.occlusion)
        best = None
        for index in candidates:
            vid = self.vertex_ids[index]
            point = self.mesh.vertex_position(vid)
            p = self._camera.project_to_screen(point, self.width, self.height)
            if p is None:
                continue
            d = math.hypot(p[0] - sx, p[1] - sy)
            if d < radius and (best is None or (d, index) < best) and visible(point, p):
                best = (d, index)
        return None if best is None else self.vertex_ids[best[1]]

    # -- picks (after `render`) ------------------------------------------------------

    def _project(self, vid):
        return self._camera.project_to_screen(self.mesh.vertex_position(vid), self.width, self.height)

    def pick_vertex(self, sx: float, sy: float, radius: float = VERTEX_RADIUS_PX):
        """Nearest vertex with a visible pixel within `radius` (exact screen distance, ties in
        mesh order as the CPU picker), or None."""
        found = self.read_ids(VERTICES, math.floor(sx - radius), math.floor(sy - radius),
                              math.floor(sx + radius), math.floor(sy + radius))
        best = None
        for index in found:
            p = self._project(self.vertex_ids[index])
            if p is None:
                continue
            d = math.hypot(p[0] - sx, p[1] - sy)
            if d < radius and (best is None or (d, index) < best):
                best = (d, index)
        return None if best is None else self.vertex_ids[best[1]]

    def pick_edge(self, sx: float, sy: float, radius: float = EDGE_RADIUS_PX):
        found = self.read_ids(EDGES, math.floor(sx - radius), math.floor(sy - radius),
                              math.floor(sx + radius), math.floor(sy + radius))
        best = None
        for index in found:
            a, b = self.mesh.edge_vertices(self.edge_ids[index])
            pa, pb = self._project(a), self._project(b)
            if pa is None or pb is None:
                continue
            d = _point_segment_distance(sx, sy, pa[0], pa[1], pb[0], pb[1])
            if d < radius and (best is None or (d, index) < best):
                best = (d, index)
        return None if best is None else self.edge_ids[best[1]]

    def pick_face(self, sx: float, sy: float):
        x, y = math.floor(sx), math.floor(sy)
        found = self.read_ids(FACES, x, y, x, y)
        return self.face_ids[next(iter(found))] if found else None

    def elements_in_rect(self, target: int, rect) -> set:
        """Box Select: elements with a visible pixel in `rect` whose corners all project into it
        (the CPU rule's corner part; visibility = a surviving pixel, not the CPU's midpoint /
        centroid test)."""
        x0, y0, x1, y1 = rect
        found = self.read_ids(target, math.floor(x0), math.floor(y0), math.floor(x1), math.floor(y1))

        def inside(vid) -> bool:
            p = self._project(vid)
            return p is not None and x0 <= p[0] <= x1 and y0 <= p[1] <= y1

        mesh = self.mesh
        if target == VERTICES:
            return {self.vertex_ids[i] for i in found if inside(self.vertex_ids[i])}
        if target == EDGES:
            return {self.edge_ids[i] for i in found
                    if all(inside(v) for v in mesh.edge_vertices(self.edge_ids[i]))}
        return {self.face_ids[i] for i in found
                if all(inside(v) for v in mesh.face_vertices(self.face_ids[i]))}
