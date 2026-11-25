"""The LookDev frame's GPU time (AD-040 §4.1, LD-3a): a ring of `GL_TIME_ELAPSED` queries around the meshes of the
LookDev step (`Viewport._render_lookdev`), never around the overlays (no tier reaches them).

- **Never blocking:** a result is read only when `GL_QUERY_RESULT_AVAILABLE` says so, typically 1-2 frames late; a
  synchronous read would add the GPU frame to the CPU frame. When every query of the ring is still pending, the frame
  is not measured.
- **Tags:** `begin(tag)` stores what the frame was drawn as (the room's activity state and tier); `take()` returns
  `[(tag, ms)]` of the frames whose results arrived, oldest first - so Auto feeds a time to the state it belongs to.
- **Nesting:** `GL_TIME_ELAPSED` queries cannot nest; a frame that begins while another timer runs (a probe's own query
  around `Viewport.render`) is not measured.
- Owned by `LookdevPass` (created when the room asks for timing, deleted in its `release()`); never for the Worklight
  (AD-040 Q4).
"""

from __future__ import annotations

RING = 3


class GpuTimer:
    def __init__(self, ring: int = RING) -> None:
        self.ring = int(ring)
        self._queries: list[int] = []
        self._pending: list[tuple[int, object]] = []  # (query, tag) in issue order
        self._active = None  # (query, tag) between begin and end
        self._results: list[tuple[object, float]] = []
        #: Test hook / probe: frames measured, and frames skipped (ring full or another timer running).
        self.measured = 0
        self.skipped = 0

    def _ensure(self) -> None:
        if self._queries:
            return
        import ctypes

        from pyglet import gl

        ids = (gl.GLuint * self.ring)()
        gl.glGenQueries(self.ring, ids)
        self._queries = [int(i) for i in ids]

    def begin(self, tag=None) -> bool:
        """Start timing a frame; False = not measured (no free query, or another timer runs)."""
        import ctypes

        from pyglet import gl

        self._ensure()
        self.poll()
        current = gl.GLint()
        gl.glGetQueryiv(gl.GL_TIME_ELAPSED, gl.GL_CURRENT_QUERY, ctypes.byref(current))
        busy = {q for q, _tag in self._pending}
        free = [q for q in self._queries if q not in busy]
        if current.value or not free or self._active is not None:
            self.skipped += 1
            return False
        query = free[0]
        gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
        self._active = (query, tag)
        return True

    def end(self) -> None:
        if self._active is None:
            return
        from pyglet import gl

        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        self._pending.append(self._active)
        self._active = None

    def poll(self) -> None:
        """Collect every result that is available (in issue order; a later one waits for an earlier one)."""
        if not self._pending:
            return
        import ctypes

        from pyglet import gl

        while self._pending:
            query, tag = self._pending[0]
            available = gl.GLint()
            gl.glGetQueryObjectiv(query, gl.GL_QUERY_RESULT_AVAILABLE, ctypes.byref(available))
            if not available.value:
                break
            elapsed = gl.GLuint64()
            gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(elapsed))
            self._pending.pop(0)
            self._results.append((tag, elapsed.value / 1e6))
            self.measured += 1

    def take(self) -> list[tuple[object, float]]:
        """The results that arrived since the last call: `[(tag, ms)]`, oldest first."""
        self.poll()
        out, self._results = self._results, []
        return out

    def release(self) -> None:
        if not self._queries:
            return
        from pyglet import gl

        if self._active is not None:
            gl.glEndQuery(gl.GL_TIME_ELAPSED)
            self._active = None
        ids = (gl.GLuint * len(self._queries))(*self._queries)
        gl.glDeleteQueries(len(self._queries), ids)
        self._queries, self._pending, self._results = [], [], []
