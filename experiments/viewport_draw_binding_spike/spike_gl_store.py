"""SpikeGLStore — the experimental `ResourceStore` for the draw-binding spike.

Question this answers (see README.md "H1"): can RenderMesh's named
resources (`positions`, `normals`, `indices`, `highlight_flags`,
`camera_uniforms`) be drawn as ONE indexed, multi-attribute pyglet
`VertexList` plus program uniforms, by supplying only a `ResourceStore`
implementation — without changing `src/viewport/`?

The friction point (Known Constraints §6 of the handoff, and
`ResourceStore`'s own docstring "kein allgemeines GPU-Resource-Management"):
`RenderMesh._rebuild_resources()` calls `allocate()`/`update()` **once per
named resource, in isolation** — it has no concept of "these N resources
together form one GPU object". A single indexed VertexList, however, needs
`positions` + `normals` + `indices` (+ optionally `highlight_flags`) all at
once to be constructed.

Resolution implemented here: defer the actual VertexList construction
until the "structural trio" (`positions`, `normals`, `indices`) has each
received a fresh `allocate()` + `update()` call *within the same rebuild
cycle* (tracked via `_trio_ready`, reset whenever a fresh `allocate()`
starts a new cycle for any trio member). `highlight_flags` is treated as
an always-optional, deferred attachment: if it has not arrived yet when
the trio completes, the VertexList is built with a zero-filled
`highlight_flag` attribute and patched in place the moment its own
`update()` call arrives — before or after the trio, either order works.

This relies on empirically observed RenderMesh call order
(`_rebuild_resources`: positions, normals, indices, then optional
highlight_flags/material_uniforms/camera_uniforms — see
`src/viewport/render_mesh.py`), not on anything the `ResourceStore`
contract itself guarantees. That reliance — and what would go wrong if a
future `RenderMesh` change reordered or interleaved these calls — is
exactly the finding this spike reports for AD-018 Option B.

`camera_uniforms` / `material_uniforms` (and any other name not in the
vertex group) are pure CPU-side storage, applied as program uniforms at
draw time via `uniform_data()` — never a GPU resource, matching the
architecture invariant "camera changes never invalidate mesh render data"
directly at the store level (no VertexList access at all).
"""

from __future__ import annotations

from viewport.resource_store import ResourceStore

VERTEX_ATTR_NAMES = {
    "positions": "position",
    "normals": "normal",
    "highlight_flags": "highlight_flag",
}
STRUCTURAL_TRIO = ("positions", "normals", "indices")


class SpikeGLStore(ResourceStore):
    """Real pyglet/OpenGL backend: one indexed VertexList + uniform passthrough.

    Requires an active GL context at first `allocate()` (see module
    docstring in `src/viewport/resource_store.py` and Known Constraints
    §6). The `ShaderProgram` is compiled lazily on first use, not at
    import time, so this module itself has no GL-context ordering
    requirement — only actually calling `allocate()`/`update()` does.
    """

    _program = None  # lazily compiled, shared across instances (one GL context)

    def __init__(self, stats) -> None:
        super().__init__(stats)
        self._cpu: dict[str, list[float]] = {}
        self._vlist = None
        self._pending_rebuild = False
        self._trio_ready: set[str] = set()

    @classmethod
    def program(cls):
        if cls._program is None:
            from shaders import build_program

            cls._program = build_program()
        return cls._program

    # -- ResourceStore contract ----------------------------------------------

    def allocate(self, name: str, nbytes: int) -> None:
        if self.has(name) and self.resource(name).created:
            # Re-allocation of an existing resource is a recreation (new
            # identity), mirrors TraceStore/PygletStore.
            self.destroy(name)
        res = self._ensure(name)
        res.created = True
        self._cpu[name] = []
        if name in STRUCTURAL_TRIO and not self._pending_rebuild:
            self._pending_rebuild = True
            self._trio_ready = set()
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

        if name in STRUCTURAL_TRIO or name in VERTEX_ATTR_NAMES:
            self._after_vertex_group_update(name)

    def destroy(self, name: str) -> None:
        res = self._resources.pop(name, None)
        if res is not None:
            self._cpu.pop(name, None)
            self.stats.count("gpu_resource_destroys")

    # -- vertex-group assembly ------------------------------------------------

    def _after_vertex_group_update(self, name: str) -> None:
        if name in STRUCTURAL_TRIO and self._pending_rebuild:
            self._trio_ready.add(name)
            if set(STRUCTURAL_TRIO) <= self._trio_ready and self._trio_data_consistent():
                self._rebuild_vertex_list()
                self._trio_ready = set()
            return

        if self._vlist is not None and not self._pending_rebuild:
            # Structural trio already assembled: content-only patch into the
            # existing, persistent VertexList — no reallocation (the actual
            # GPU Resource Persistence proof, §7 of the architecture doc).
            attr = VERTEX_ATTR_NAMES[name]
            data = self._cpu[name]
            getattr(self._vlist, attr)[0:len(data)] = data
        # else: highlight_flags arrived before the trio completed (not
        # observed with the real RenderMesh, but handled defensively) — it
        # stays buffered in self._cpu and is picked up by _rebuild_vertex_list.

    def _trio_data_consistent(self) -> bool:
        positions = self._cpu.get("positions", [])
        normals = self._cpu.get("normals", [])
        indices = self._cpu.get("indices", [])
        if not positions or len(positions) % 3 != 0:
            return False
        n_verts = len(positions) // 3
        return len(normals) == n_verts * 3 and len(indices) % 3 == 0

    def _rebuild_vertex_list(self) -> None:
        import pyglet

        n_verts = len(self._cpu["positions"]) // 3
        indices_int = [int(v) for v in self._cpu["indices"]]
        flags = self._cpu.get("highlight_flags")
        if flags is None or len(flags) != n_verts:
            flags = [0.0] * n_verts

        program = self.program()
        old_vlist = self._vlist
        self._vlist = program.vertex_list_indexed(
            n_verts, pyglet.gl.GL_TRIANGLES, indices_int,
            position=("f", tuple(self._cpu["positions"])),
            normal=("f", tuple(self._cpu["normals"])),
            highlight_flag=("f", tuple(flags)),
        )
        if old_vlist is not None:
            old_vlist.delete()
        self._pending_rebuild = False

    # -- draw-time access -------------------------------------------------------

    def vertex_list(self):
        """The current combined VertexList, or None before the trio has ever
        completed (never true for a fully built RenderMesh, since `build()`
        runs the full trio synchronously in `__init__`)."""
        return self._vlist

    def uniform_data(self, name: str) -> list[float]:
        """CPU-side content of a non-vertex-group resource (`camera_uniforms`,
        `material_uniforms`, ...) for application as a program uniform."""
        return list(self._cpu.get(name, []))
