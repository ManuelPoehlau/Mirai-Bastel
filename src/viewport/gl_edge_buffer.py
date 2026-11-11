"""A GL element buffer mirroring `RenderMesh.edge_indices` (AD-022 B2-out, 2026-10-21; shared 2026-11-11).

Two vertex indices per edge slot into the `RenderMesh` VertexList (free and hidden slots are (0, 0), a line without
length that rasterises nothing). Drawn as `GL_LINES` with `glDrawElementsBaseVertex(..., vlist.start)` over the
store's own vertex buffer, so a position change needs no upload here at all: only the slots the mesh's topology or
Hide changed are re-uploaded (`RenderMesh.take_edge_changes`, one change set per buffer). Users: the GPU picker's edge
pass (`gpu_picker.py`) and the wire (`gl_line_overlay.GLLineOverlay.draw_mesh_wire`), each with its own buffer.
"""

from __future__ import annotations

import ctypes

#: Edge slots closer than this are uploaded as one range.
EDGE_MERGE_GAP = 256


def runs(slots, gap: int) -> list[tuple[int, int]]:
    """[lo, hi) slot ranges covering `slots`, joined across gaps below `gap`."""
    ranges: list[tuple[int, int]] = []
    for slot in sorted(slots):
        if ranges and slot <= ranges[-1][1] + gap:
            ranges[-1] = (ranges[-1][0], slot + 1)
        else:
            ranges.append((slot, slot + 1))
    return ranges


class EdgeIndexBuffer:
    """One element buffer, kept equal to the `edge_indices` of the `RenderMesh` last passed to `sync`."""

    def __init__(self) -> None:
        self.name = 0
        self._owner = None  # (id(render_mesh), layout_revision) the buffer holds
        self._length = 0
        #: Full uploads / range uploads so far (tests, diagnostics).
        self.full_uploads = 0
        self.range_uploads = 0

    def sync(self, rm) -> int:
        """Uploads what changed since the last call (everything for another mesh or a new layout); returns the
        GL buffer name. Needs the GL context."""
        from pyglet import gl

        changes = rm.take_edge_changes(self)
        owner = (id(rm), rm.layout_revision)
        data = rm.edge_indices
        if not self.name:
            buffer = gl.GLuint()
            gl.glGenBuffers(1, ctypes.byref(buffer))
            self.name = buffer.value
        gl.glBindBuffer(gl.GL_COPY_WRITE_BUFFER, self.name)
        address = data.buffer_info()[0]
        if changes is None or owner != self._owner or self._length != len(data):
            gl.glBufferData(gl.GL_COPY_WRITE_BUFFER, max(4, len(data) * 4), address if data else None,
                            gl.GL_DYNAMIC_DRAW)
            self.full_uploads += 1
        elif changes:
            for lo, hi in runs(changes, EDGE_MERGE_GAP):
                gl.glBufferSubData(gl.GL_COPY_WRITE_BUFFER, lo * 8, (hi - lo) * 8, address + lo * 8)
            self.range_uploads += 1
        gl.glBindBuffer(gl.GL_COPY_WRITE_BUFFER, 0)
        self._owner = owner
        self._length = len(data)
        return self.name

    def release(self) -> None:
        from pyglet import gl

        if self.name:
            gl.glDeleteBuffers(1, ctypes.byref(gl.GLuint(self.name)))
            self.name = 0
            self._owner = None
