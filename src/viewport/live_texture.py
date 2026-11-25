"""A texture whose pixels the host writes while it shows (AD-037 §4.2 principle 1, audit 2026-11-18 Phase 1c).

The Paint Room keeps its pixels on the CPU (`mirai.paint.store`); the GPU gets a copy. A `LiveTexture` wraps the host's
`(height, width, 4)` uint8 RGBA array (row 0 = v = 0, the GL row order) - it is read, never written here - and collects
the boxes the host marked as changed. `GLRenderStore` takes a `LiveTexture` wherever it takes a texture path
(`Material(texture=...)`, `set_texture`): the first draw uploads the whole image, every later draw only the marked boxes
(`glTexSubImage2D`), once per frame however many surfaces show it (the object and its SubD surface).

**Mipmaps** (audit §8.4 item 1, probe P-B decides the default on the reference PC): `"frame"` regenerates them after
every upload, `"deferred"` only when the host calls `finish()` (a stroke's end; while a stroke runs, minified views show
the older levels), `"none"` draws without mipmaps (linear filtering only). The policy is fixed per texture.

Data flows host -> viewport only: nothing here reads the GPU back. `release()` frees the GL texture (needs the context);
a `LiveTexture` that was never drawn holds no GL object.
"""

from __future__ import annotations

MIP_POLICIES = ("frame", "deferred", "none")


class LiveTexture:
    def __init__(self, rgba, mipmaps: str = "deferred") -> None:
        if getattr(rgba, "ndim", 0) != 3 or rgba.shape[2] != 4 or str(rgba.dtype) != "uint8":
            raise ValueError("LiveTexture: expected a (height, width, 4) uint8 array")
        if not rgba.flags["C_CONTIGUOUS"]:
            raise ValueError("LiveTexture: the array must be C-contiguous (it is uploaded as it lies in memory)")
        if mipmaps not in MIP_POLICIES:
            raise ValueError(f"LiveTexture: mipmaps one of {MIP_POLICIES}, got {mipmaps!r}")
        self.rgba = rgba
        self.mipmaps = mipmaps
        self._boxes: list[tuple[int, int, int, int]] = []
        self._full = True  # the first draw uploads everything
        self._mips_due = mipmaps != "none"
        #: GL texture name once drawn (owned by `viewport.gl_render_store`)
        self.gl_name: int | None = None
        #: uploads done (boxes; a full upload counts one) - read by tests and the probes
        self.uploads = 0
        self.uploaded_bytes = 0
        #: AD-040 §3.1: +1 for every change the host marks (`mark`, `mark_all`, a deferred `finish`) - the LookDev frame
        #: signature reads it (the boxes are uploaded on the next draw)
        self.revision = 0

    @property
    def width(self) -> int:
        return int(self.rgba.shape[1])

    @property
    def height(self) -> int:
        return int(self.rgba.shape[0])

    def mark(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Pixels in [x0, x1) x [y0, y1) changed (clipped to the image)."""
        x0, y0 = max(int(x0), 0), max(int(y0), 0)
        x1, y1 = min(int(x1), self.width), min(int(y1), self.height)
        if x1 > x0 and y1 > y0:
            self._boxes.append((x0, y0, x1, y1))
            self.revision += 1
            if self.mipmaps == "frame":
                self._mips_due = True

    def mark_all(self) -> None:
        self._full = True
        self.revision += 1
        if self.mipmaps != "none":
            self._mips_due = True

    def finish(self) -> None:
        """A stroke ended: the next draw regenerates the mipmaps (policy "deferred")."""
        if self.mipmaps == "deferred":
            self._mips_due = True
            self.revision += 1  # the minified levels change with the regeneration

    def take(self) -> tuple[bool, list[tuple[int, int, int, int]], bool]:
        """(upload everything, boxes, regenerate mipmaps) since the last call; for the GL store."""
        full, boxes, mips = self._full, self._boxes, self._mips_due
        self._full, self._boxes, self._mips_due = False, [], False
        return full, ([] if full else boxes), mips

    @property
    def pending(self) -> bool:
        return self._full or bool(self._boxes) or self._mips_due

    def release(self) -> None:
        if self.gl_name is None:
            return
        import ctypes

        from pyglet import gl

        gl.glDeleteTextures(1, ctypes.byref(gl.GLuint(self.gl_name)))
        self.gl_name = None
        self._full = True
