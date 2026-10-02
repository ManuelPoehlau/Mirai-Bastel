"""Two-mesh scene: control mesh + derived surface (handoff §3.2, D1/D3/D6).

Adapted from `experiments/viewport_shading_lab/lab_scene.py` (rebuilt, not
imported) and `experiments/ad018_gl_render_store_verification/run.py`.

- `control_rm`: the loaded asset in a production `RenderMesh` on the
  unmodified `GLRenderStore` ("today's" look). The control mesh is the only
  authoritative mesh (D1).
- one `LevelView` per built level: a lab-owned throw-away `core.Mesh` made by
  `mirai.scene_factory.mesh_from_positions_and_faces` (D3) with its own
  `RenderMesh` on the same production store. It is never inserted into a
  `Scene`, has no history/selection/serialization, and its vertex ids carry
  no meaning beyond "slot i of the level".
- one shared `OrbitCamera`, one `LabLineOverlay` (cage / isolines), one
  `GLPointOverlay` hover dot.

Update model (D6): topology and stencils are built once per level
(`SubdSurface.level`); a vertex drag recomputes only the derived vertices that
reference the moved control vertex (`SubdLevel.apply_local`) and reports only
those to `RenderMesh.mark_vertices_dirty` — never `mark_topology_dirty`. Only
the *displayed* level is updated eagerly; other built levels are marked stale
and refreshed in full when they are shown again.

Known hotspots, measured by `bench.py` and deliberately NOT optimized here
(handoff §5): `RenderMesh._sync_geometry` issues one `store.update` per moved
vertex and runs `derived.recompute_bounds` over all vertices on every sync.

GL needs an active context at the first `allocate()`: build `LabScene` after
the window exists. `resolve_asset_name()` is GL-free so `run.py` can reject a
bad name before any window opens.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from core import Selection
from loaders.assets import asset_names, asset_path
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.scene_factory import build_core_scene_from_obj, mesh_from_positions_and_faces
from mirai.viewport.camera import OrbitCamera
from viewport.gl_point_overlay import GLPointOverlay
from viewport.gl_render_store import GLRenderStore
from viewport.overlay import HOVER_LAYER, SelectionOverlay
from viewport.render_mesh import RenderMesh

from .lab_lines import CAGE_LAYER, ISO_LAYER, LabLineOverlay
from .lab_state import MAX_DERIVED_FACES, VIEW_BOTH, VIEW_CAGE, VIEW_ISO
from .subd import SubdSurface

DEFAULT_ASSET = "head_basemesh"
#: Production clear color (`src/main.py`).
CLEAR_COLOR = (0.05, 0.05, 0.08)


class UnknownAssetError(LookupError):
    """Asset name is not registered in `loaders.assets.asset_names()`."""


class LevelRefusedError(ValueError):
    """The requested level would exceed `MAX_DERIVED_FACES` (defense in depth —
    `LabState.request_level` normally refuses first)."""


def resolve_asset_name(name: str) -> str:
    """Returns `name` or raises `UnknownAssetError` listing all valid names."""
    valid = asset_names()
    if name not in valid:
        raise UnknownAssetError(
            f"Unbekanntes Asset {name!r}. Gültige Namen: {', '.join(valid)}"
        )
    return name


def load_control_mesh(asset_name: str):
    resolve_asset_name(asset_name)
    return build_core_scene_from_obj(str(asset_path(asset_name))).mesh


@dataclass
class LevelView:
    """One built level: derived data + throw-away mesh + its `RenderMesh`."""

    level: int
    derived: object  # subd.SubdLevel
    mesh: object  # core.Mesh (lab-owned, never in a Scene)
    #: derived vertex index -> VertexId of `mesh` (ids are opaque handles)
    vertex_ids: list
    render_mesh: RenderMesh
    positions: list
    #: True once the control mesh moved while this level was not displayed
    stale: bool = False
    timings_ms: dict = field(default_factory=dict)


class LabScene:
    def __init__(
        self,
        asset_name: str,
        aspect: float,
        control_mesh=None,
        camera: Optional[OrbitCamera] = None,
    ) -> None:
        self.asset_name = asset_name
        self.control_mesh = control_mesh if control_mesh is not None else load_control_mesh(asset_name)
        # Validates the topology (raises SubdUnsupportedError with a German message).
        self.surface = SubdSurface(self.control_mesh)
        self.topology = self.surface.topology
        #: control positions, indexed like `topology.vertex_ids`; mirrors the mesh
        self.control_positions = list(self.surface.initial_positions)
        #: bumped by every control-vertex move
        self.version = 0
        self.aspect = aspect

        if camera is None:
            camera = OrbitCamera()
            center, radius = mesh_center_and_radius(self.control_mesh)
            camera.frame_on_bounds(center, radius)
        self.camera = camera

        self.control_rm = self._make_render_mesh(self.control_mesh)
        self.lines = LabLineOverlay()
        self.points = GLPointOverlay()
        self.views: dict[int, LevelView] = {}
        self._hover_index: Optional[int] = None
        self._cage_version = -1
        self._iso_key: Optional[tuple] = None

    # -- construction helpers ------------------------------------------------------------

    def _make_render_mesh(self, mesh) -> RenderMesh:
        rm = RenderMesh(mesh, overlay=SelectionOverlay(Selection()), store_type=GLRenderStore)
        # Lines are drawn over the faces: push the faces back (production behaviour, E40).
        rm.store.set_draw_style(False, True)
        rm.bind_camera(self.camera)
        rm.mark_camera_dirty(aspect=self.aspect)
        rm.sync()
        return rm

    def camera_changed(self, aspect: float) -> None:
        """Camera/aspect change → `camera_uniforms` via the regular dirty path
        (every built mesh; the draw syncs the displayed one)."""
        self.aspect = aspect
        self.control_rm.mark_camera_dirty(aspect=aspect)
        for view in self.views.values():
            view.render_mesh.mark_camera_dirty(aspect=aspect)

    def camera_uniforms(self) -> list[float]:
        return list(self.camera.build_view_matrix()) + list(self.camera.build_projection_matrix(self.aspect))

    # -- levels --------------------------------------------------------------------------------

    def is_level_allowed(self, level: int) -> bool:
        return self.surface.predicted_face_count(level) <= MAX_DERIVED_FACES

    def ensure_level(self, level: int) -> tuple[LevelView, float, bool]:
        """Builds `level` lazily (cached) and refreshes it if the control mesh
        moved since it was last displayed. Returns `(view, ms, did_work)`."""
        if not self.is_level_allowed(level):
            raise LevelRefusedError(
                f"Stufe {level}: {self.surface.predicted_face_count(level)} Flächen > {MAX_DERIVED_FACES}"
            )
        started = time.perf_counter()
        view = self.views.get(level)
        did_work = False
        if view is None:
            view = self._build_view(level)
            self.views[level] = view
            did_work = True
        elif view.stale:
            self.refresh_full(view)
            did_work = True
        return view, (time.perf_counter() - started) * 1000.0, did_work

    def _build_view(self, level: int) -> LevelView:
        t0 = time.perf_counter()
        derived = self.surface.level(level)
        t1 = time.perf_counter()
        positions = derived.apply_full(self.control_positions)
        mesh = mesh_from_positions_and_faces(positions, derived.faces)
        vertex_ids = mesh.all_vertex_ids()
        t2 = time.perf_counter()
        render_mesh = self._make_render_mesh(mesh)
        t3 = time.perf_counter()
        return LevelView(
            level=level, derived=derived, mesh=mesh, vertex_ids=vertex_ids,
            render_mesh=render_mesh, positions=positions,
            timings_ms={
                "subd": (t1 - t0) * 1000.0,
                "mesh": (t2 - t1) * 1000.0,
                "render_mesh": (t3 - t2) * 1000.0,
            },
        )

    def write_positions(self, view: LevelView, indices=None) -> list:
        """Writes `view.positions[i]` into the derived mesh for `indices` (all
        if None); returns the touched VertexIds (for `mark_vertices_dirty`)."""
        positions, mesh, ids = view.positions, view.mesh, view.vertex_ids
        if indices is None:
            indices = range(len(ids))
        touched = []
        for d in indices:
            vid = ids[d]
            mesh.set_vertex_position(vid, positions[d])
            touched.append(vid)
        return touched

    def refresh_full(self, view: LevelView) -> None:
        """All derived positions from the current control positions + full GPU sync."""
        view.positions = view.derived.apply_full(self.control_positions)
        touched = self.write_positions(view)
        view.render_mesh.mark_vertices_dirty(set(touched))
        view.render_mesh.sync()
        view.stale = False

    # -- drag (D6/D9) -------------------------------------------------------------------------------

    def move_control_vertex(self, vertex_id, position, displayed_level: Optional[int]) -> float:
        """Moves one control vertex (D9: plain `Mesh.set_vertex_position`, no
        Operation/History) and updates what is displayed — no structural rebuild.

        `displayed_level`: the level shown now (derived view), or None if the
        control mesh is shown. Returns the elapsed milliseconds of the step."""
        started = time.perf_counter()
        index = self.surface.index_of_vertex(vertex_id)
        position = tuple(position)
        self.control_mesh.set_vertex_position(vertex_id, position)
        self.control_positions[index] = position
        self.version += 1
        self.control_rm.mark_vertices_dirty({vertex_id})

        shown = self.views.get(displayed_level) if displayed_level is not None else None
        for view in self.views.values():
            if view is not shown:
                view.stale = True
        if shown is None:
            self.control_rm.sync()
        elif shown.stale:
            self.refresh_full(shown)  # the shown level was never refreshed after earlier moves
        else:
            changed = shown.derived.apply_local(index, self.control_positions, shown.positions)
            touched = self.write_positions(shown, changed)
            shown.render_mesh.mark_vertices_dirty(set(touched))
            shown.render_mesh.sync()
        self.refresh_lines(displayed_level)
        return (time.perf_counter() - started) * 1000.0

    # -- lines -------------------------------------------------------------------------------------------

    def refresh_lines(self, displayed_level: Optional[int]) -> None:
        """Brings the cage segments (always cheap) and, if a derived level is
        shown, its isolines up to date with the current positions."""
        if self._cage_version != self.version:
            positions = self.control_positions
            self.lines.set_cage([(positions[a], positions[b]) for a, b in self.topology.edges])
            self._cage_version = self.version
        view = self.views.get(displayed_level) if displayed_level is not None else None
        if view is not None and not view.stale:
            key = (displayed_level, self.version)
            if self._iso_key != key:
                positions = view.positions
                self.lines.set_iso([(positions[a], positions[b]) for a, b in view.derived.iso_edges])
                self._iso_key = key

    def set_hover(self, vertex_id) -> None:
        self._hover_index = None if vertex_id is None else self.surface.index_of_vertex(vertex_id)

    # -- draw ----------------------------------------------------------------------------------------------

    def draw(self, view_mode: str, level: int, cage_depth_test: bool = True) -> None:
        """Clears, syncs pending dirty state and draws the mesh(es) + lines +
        hover dot for `view_mode` (no HUD). `level` is ignored for V-CAGE."""
        from pyglet import gl

        gl.glClearColor(*CLEAR_COLOR, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        self.lines.cage_depth_test = cage_depth_test

        if view_mode == VIEW_CAGE:
            self.control_rm.sync()
            self.control_rm.render(self.camera)
            self.refresh_lines(None)
            line_layers = (CAGE_LAYER,)
        else:
            view = self.views.get(level)
            if view is None or view.stale:
                view, _ms, _did = self.ensure_level(level)
            view.render_mesh.sync()
            view.render_mesh.render(self.camera)
            self.refresh_lines(level)
            line_layers = (CAGE_LAYER,) if view_mode == VIEW_BOTH else (ISO_LAYER,)
        uniforms = self.camera_uniforms()
        self.lines.draw(uniforms, layers=line_layers)

        hover = None if self._hover_index is None else self.control_positions[self._hover_index]
        self.points.set_points(HOVER_LAYER, [] if hover is None else [hover])
        self.points.draw(uniforms)

    # -- diagnostics / cleanup -------------------------------------------------------------------------------

    def render_meshes(self) -> list[RenderMesh]:
        return [self.control_rm] + [v.render_mesh for v in self.views.values()]

    def release(self) -> None:
        """Deletes the GPU vertex lists (used by the bench for throw-away scenes)."""
        for rm in self.render_meshes():
            vlist = rm.store.vertex_list()
            if vlist is not None:
                vlist.delete()
        for layer in self.lines.LAYERS:
            vlist = self.lines.vertex_list(layer)
            if vlist is not None:
                vlist.delete()
        self.views.clear()


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
