"""The lab's draw path: one box mesh on the production `src/viewport` path (handoff §2).

Rebuilt after `subdivision_lab/lab_scene.py` (not imported): the mesh in a production
`RenderMesh` on the unmodified `GLRenderStore`, one `OrbitCamera`, a production
`GLLineOverlay` for the wire (`wire` layer) and the hovered Loop/Ring (`hover` layer, the
hover line style), a production `GLPointOverlay` for the seeds (`hover` point style),
the lab's `GLSignedBandOverlay` for the signed influence bands and (Slice 2a E14) the lab's
`GLInfluencePreviewOverlay` for the optional surface preview, drawn right after the mesh so
wire, Loop/Ring line and points stay on top.

The viewport stays passive: the window pushes the target and its weights in
(`set_target`), the overlays only turn them into positions at the mesh's current
positions. Positions changed by a drag step are reported per vertex
(`RenderMesh.mark_vertices_dirty`), never as a topology change; a new box is a new mesh
with a new `RenderMesh` (the old vertex list is deleted).

GL needs an active context at the first `allocate()`: build `LabScene` after the window exists.
"""

from __future__ import annotations

from typing import Iterable, Optional

from core import Mesh, Selection
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.viewport.camera import OrbitCamera
from viewport.gl_line_overlay import WIRE_LAYER, GLLineOverlay
from viewport.gl_point_overlay import GLPointOverlay
from viewport.gl_render_store import GLRenderStore
from viewport.overlay import HOVER_LAYER, SelectionOverlay
from viewport.render_mesh import RenderMesh

from .lab_bands import EMPTY_SIGNED_BANDS, GLSignedBandOverlay, SignedBands
from .lab_preview import GLInfluencePreviewOverlay
from .targets import Target

#: Production clear color (`src/main.py`).
CLEAR_COLOR = (0.05, 0.05, 0.08)


class LabScene:
    def __init__(self, aspect: float, camera: Optional[OrbitCamera] = None) -> None:
        self.aspect = aspect
        self.camera = camera if camera is not None else OrbitCamera()
        self.mesh: Optional[Mesh] = None
        self.render_mesh: Optional[RenderMesh] = None
        self.lines = GLLineOverlay()
        self.points = GLPointOverlay()
        self.bands = GLSignedBandOverlay()
        self.preview = GLInfluencePreviewOverlay()
        self.target: Optional[Target] = None
        #: Radius the camera was last framed on (the creation phase only zooms out).
        self.framed_radius = 0.0
        self._wire_version = -1
        self.version = 0

    # -- mesh ---------------------------------------------------------------------------------

    def show_mesh(self, mesh: Mesh, frame: str = "none") -> None:
        """Replaces the displayed mesh. `frame`: "always" (frame the camera on it), "grow"
        (only zoom out when the mesh outgrew the framed sphere) or "none"."""
        self.release()
        self.mesh = mesh
        rm = RenderMesh(mesh, overlay=SelectionOverlay(Selection()), store_type=GLRenderStore)
        # Lines are drawn over the faces: push the faces back (production behaviour, E40).
        rm.store.set_draw_style(False, True)
        rm.bind_camera(self.camera)
        rm.mark_camera_dirty(aspect=self.aspect)
        rm.sync()
        self.render_mesh = rm
        self.version += 1
        self.set_target(None, {})
        center, radius = mesh_center_and_radius(mesh)
        if frame == "always" or (frame == "grow" and radius > self.framed_radius):
            self.camera.frame_on_bounds(center, radius)
            self.framed_radius = radius
            self.camera_changed(self.aspect)

    def positions_changed(self, vertex_ids: Optional[Iterable] = None) -> None:
        """Positions moved (drag step, Undo/Redo, Nachführen): partial GPU update, no rebuild."""
        if self.render_mesh is None:
            return
        ids = set(self.mesh.all_vertex_ids() if vertex_ids is None else vertex_ids)
        if ids:
            self.render_mesh.mark_vertices_dirty(ids)
        self.version += 1

    def camera_changed(self, aspect: float) -> None:
        self.aspect = aspect
        if self.render_mesh is not None:
            self.render_mesh.mark_camera_dirty(aspect=aspect)

    def camera_uniforms(self) -> list[float]:
        return list(self.camera.build_view_matrix()) + list(self.camera.build_projection_matrix(self.aspect))

    # -- hover target + bands ------------------------------------------------------------------

    def set_target(self, target: Optional[Target], weights: dict) -> None:
        """The hovered (or dragged) target and the weights bands and preview show."""
        self.target = target
        weights = weights if target is not None else {}
        self.bands.set_bands(SignedBands.from_weights(weights) if target is not None else EMPTY_SIGNED_BANDS)
        self.preview.set_weights(weights)

    def _refresh_overlays(self) -> None:
        mesh = self.mesh
        position = mesh.vertex_position
        if self._wire_version != self.version:
            self.lines.set_segments(
                [(position(a), position(b)) for a, b in (mesh.edge_vertices(e) for e in mesh.all_edge_ids())],
                WIRE_LAYER,
            )
            self._wire_version = self.version
        target = self.target
        if target is None:
            self.lines.set_segments([], HOVER_LAYER)
            self.points.set_points(HOVER_LAYER, [])
        else:
            self.lines.set_segments(
                [(position(a), position(b)) for a, b in (mesh.edge_vertices(e) for e in target.edges)],
                HOVER_LAYER,
            )
            self.points.set_points(HOVER_LAYER, [position(v) for v in sorted(target.seeds)])
        self.bands.sync(mesh)
        self.preview.sync(mesh, self.version)

    # -- draw -------------------------------------------------------------------------------------

    def draw(self) -> None:
        """Clears and draws mesh, preview, wire, hovered Loop/Ring, bands and seeds (no 2D)."""
        from pyglet import gl

        gl.glClearColor(*CLEAR_COLOR, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        if self.render_mesh is None:
            return
        self.render_mesh.sync()
        self.render_mesh.render(self.camera)
        self._refresh_overlays()
        uniforms = self.camera_uniforms()
        self.preview.draw(uniforms)
        self.lines.draw(uniforms, layers=(WIRE_LAYER, HOVER_LAYER))
        self.bands.draw(uniforms)
        self.points.draw(uniforms)

    def release(self) -> None:
        """Deletes the GPU vertex list of the current mesh (a new box replaces it)."""
        if self.render_mesh is not None:
            vlist = self.render_mesh.store.vertex_list()
            if vlist is not None:
                vlist.delete()
        self.render_mesh = None
        self.mesh = None


def gl_info_strings() -> tuple[str, str]:
    """`(GL_VERSION, GL_RENDERER)` of the current context (open item in
    `docs/architecture/REFERENCE_HARDWARE.md` §2 — printed/shown only)."""
    import ctypes

    from pyglet import gl

    def read(name: int) -> str:
        try:
            raw = gl.glGetString(name)
            return ctypes.cast(raw, ctypes.c_char_p).value.decode("utf-8", "replace")
        except Exception:  # pragma: no cover - driver specific
            return "unbekannt"

    return read(gl.GL_VERSION), read(gl.GL_RENDERER)
