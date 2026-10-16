"""The SubD Lab on the app path: replacement surface + cage/isoline overlay (GL-free).

WP-SUBD-LAB-02. Contract on the Production side: AD-013 Addendum H7 (`Viewport.set_surface_provider`,
module docstring of `src/viewport/viewport.py`) and H1 (`Viewport.add_overlay`). The app knows no
subdivision: it mutates the control mesh with all its tools and notifies the viewport as always;
the viewport then asks `SubdSurfaceProvider.sync(mesh, selection)` for the derived surface and draws
it in place of the control mesh's faces, with the app's light, Flat/Smooth and placement.

What `sync` does (the control mesh is the only authoritative mesh; nothing is written back):

- topology signature changed (C, Extrude, Delete, Undo over a topology step, loading, another edit
  object): `SubdSurface` is rebuilt and the shown level gets a fresh derived `core.Mesh` (the new
  object tells the viewport to rebuild its `RenderMesh`);
- only positions changed (W/E/R, Tweak, Soft, Undo over a move): the changed control vertices are
  found by comparing with the cached positions; a few go through `apply_local` (only the derived
  vertices whose stencil references them), many through `apply_full`. The returned set is the moved
  derived vertices (H7: an update, no rebuild);
- the control mesh is outside the uniform Catmull-Clark rules (`SubdUnsupportedError`, e.g. a hole
  after Delete): `surface_mesh = None`, so the viewport draws the cage again, and `message` says why
  — never a silently wrong surface.

Level and view are view state (D8 of WP-SUBD-LAB-01): no document state, no Undo (OF-3 stays open).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Optional

from mirai.scene_factory import mesh_from_positions_and_faces

from .lab_lines import CAGE_LAYER, ISO_LAYER
from .lab_state import DEFAULT_LEVEL, LEVELS, MAX_DERIVED_FACES, VIEW_BOTH, VIEW_CAGE, VIEW_ISO, VIEW_ORDER
from .subd import SubdSurface, SubdUnsupportedError

#: Above this share of moved control vertices one `apply_full` is cheaper than many `apply_local`
#: calls (each touches the 2-ring; agent-set, not measured on the reference PC).
FULL_UPDATE_SHARE = 0.125


def topology_signature(mesh) -> tuple:
    """Everything the stencils depend on: vertices, edges and face boundaries (core query API)."""
    return (
        tuple(int(v) for v in mesh.all_vertex_ids()),
        tuple(tuple(int(v) for v in mesh.edge_vertices(e)) for e in mesh.all_edge_ids()),
        tuple(tuple(int(v) for v in mesh.face_vertices(f)) for f in mesh.all_face_ids()),
    )


class SubdSurfaceProvider:
    """H7 provider: `sync(mesh, selection) -> moved`, `surface_mesh`, `dirty` (module docstring)."""

    def __init__(self, level: int = DEFAULT_LEVEL, max_faces: int = MAX_DERIVED_FACES) -> None:
        self.enabled = False
        self.level = level
        self.max_faces = max_faces
        #: the derived mesh the viewport draws (None = the control mesh's own faces)
        self.surface_mesh = None
        self.dirty = False
        #: why there is no surface although it is on (`SubdUnsupportedError`, level refused), or None
        self.message: Optional[str] = None
        #: called with `message` whenever it changes to a new text (the lab posts it as status)
        self.on_message: Optional[Callable[[str], None]] = None
        self.last_build_ms: Optional[float] = None
        self.last_update_ms: Optional[float] = None

        self._mesh = None
        self._signature: Optional[tuple] = None
        #: the refusal for the current topology (survives switching off and on), or None
        self._error: Optional[str] = None
        self._surface: Optional[SubdSurface] = None
        self._control_positions: list = []
        self._derived = None  # subd.SubdLevel of the shown level
        self._derived_ids: list = []
        self._derived_positions: list = []
        #: bumped whenever positions or topology of the shown surface changed (for the overlay)
        self.revision = 0

    # -- view state ----------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        if enabled != self.enabled:
            self.enabled = enabled
            self.dirty = True

    def predicted_faces(self, level: int) -> Optional[int]:
        return None if self._surface is None else self._surface.predicted_face_count(level)

    def set_level(self, level: int) -> Optional[str]:
        """Switches the level; returns a refusal text if it would exceed `max_faces`."""
        if level not in LEVELS:
            return f"Stufe {level} gibt es nicht"
        faces = self.predicted_faces(level)
        if faces is not None and faces > self.max_faces:
            return f"Stufe {level} abgelehnt: {faces} Flächen > {self.max_faces} (Limit provisorisch)"
        if level != self.level:
            self.level = level
            self._derived = None
            self.dirty = True
        return None

    @property
    def derived_counts(self) -> Optional[tuple[int, int]]:
        if self.surface_mesh is None or self._derived is None:
            return None
        return len(self._derived_ids), len(self._derived.faces)

    def control_positions(self) -> list:
        return self._control_positions

    def derived_positions(self) -> list:
        return self._derived_positions if self.surface_mesh is not None else []

    def control_edges(self) -> tuple:
        return () if self._surface is None else self._surface.topology.edges

    def iso_edges(self) -> list:
        return [] if self._derived is None or self.surface_mesh is None else self._derived.iso_edges

    # -- H7 ------------------------------------------------------------------------------

    def sync(self, mesh, selection) -> set:
        self.dirty = False
        if not self.enabled:
            self.surface_mesh = None
            self._derived = None  # rebuilt from the then current positions when switched on again
            self._set_message(None)
            return set()
        signature = topology_signature(mesh)
        if mesh is not self._mesh or signature != self._signature:
            self._rebuild(mesh, signature)
            return set()
        if self._error is not None:
            self._set_message(self._error)  # unsupported topology: nothing to draw until it changes
            return set()
        if self._derived is None:
            self._build_level()
            return set()
        return self._update_positions(mesh)

    def _set_message(self, message: Optional[str]) -> None:
        if message == self.message:
            return
        self.message = message
        if message is not None and self.on_message is not None:
            self.on_message(message)

    def _rebuild(self, mesh, signature: tuple) -> None:
        self._mesh = mesh
        self._signature = signature
        self._derived = None
        self.surface_mesh = None
        self.revision += 1
        self._error = None
        try:
            self._surface = SubdSurface(mesh)
        except SubdUnsupportedError as exc:
            self._surface = None
            self._control_positions = []
            self._error = f"SubD aus: {exc}"
            self._set_message(self._error)
            return
        self._build_level()

    def _build_level(self) -> None:
        started = time.perf_counter()
        mesh = self._mesh
        self._control_positions = [
            tuple(mesh.vertex_position(v)) for v in self._surface.topology.vertex_ids
        ]
        faces = self._surface.predicted_face_count(self.level)
        if faces > self.max_faces:
            # The topology grew past the limit at this level: fall back to the highest allowed one.
            allowed = [n for n in LEVELS if self._surface.predicted_face_count(n) <= self.max_faces]
            if not allowed:
                self.surface_mesh = None
                self._error = f"SubD aus: schon Stufe 1 hätte mehr als {self.max_faces} Flächen"
                self._set_message(self._error)
                return
            self.level = max(allowed)
        derived = self._surface.level(self.level)
        positions = derived.apply_full(self._control_positions)
        surface = mesh_from_positions_and_faces(positions, derived.faces)
        self._derived = derived
        self._derived_ids = surface.all_vertex_ids()
        self._derived_positions = positions
        self.surface_mesh = surface
        self.revision += 1
        self.last_build_ms = (time.perf_counter() - started) * 1000.0
        self._set_message(None)

    def _update_positions(self, mesh) -> set:
        started = time.perf_counter()
        vertex_ids = self._surface.topology.vertex_ids
        cached = self._control_positions
        changed = []
        for i, vid in enumerate(vertex_ids):
            position = tuple(mesh.vertex_position(vid))
            if position != cached[i]:
                cached[i] = position
                changed.append(i)
        if not changed:
            return set()
        derived = self._derived
        if len(changed) > FULL_UPDATE_SHARE * len(vertex_ids):
            self._derived_positions = derived.apply_full(cached)
            touched = range(len(self._derived_ids))
        else:
            touched = set()
            for i in changed:
                touched.update(derived.apply_local(i, cached, self._derived_positions))
        moved = set()
        surface, ids, positions = self.surface_mesh, self._derived_ids, self._derived_positions
        for d in touched:
            surface.set_vertex_position(ids[d], positions[d])
            moved.add(ids[d])
        self.revision += 1
        self.last_update_ms = (time.perf_counter() - started) * 1000.0
        return moved


class SubdLineOverlay:
    """H1 overlay: the cage (V-BOTH) or the isolines (V-ISO) of the provider's current state.

    Runs after the provider in `Viewport.sync()` (H7 syncs before the extra overlays), so it reads
    positions that already match the control mesh. `sink` is the GL side (`LabLineOverlay`) or None
    headless; the segments stay observable in `segments`.
    """

    def __init__(self, provider: SubdSurfaceProvider, sink=None) -> None:
        self.provider = provider
        self.sink = sink
        self.view = VIEW_CAGE
        self.cage_depth_test = True
        self.dirty = True
        self.segments: dict[str, list] = {CAGE_LAYER: [], ISO_LAYER: []}
        self._key: Optional[tuple] = None

    def set_view(self, view: str, cage_depth_test: bool) -> None:
        if view not in VIEW_ORDER:
            raise ValueError(view)
        if (view, cage_depth_test) != (self.view, self.cage_depth_test):
            self.view = view
            self.cage_depth_test = cage_depth_test
            self.dirty = True

    def layer(self) -> Optional[str]:
        if self.provider.surface_mesh is None:
            return None
        return {VIEW_BOTH: CAGE_LAYER, VIEW_ISO: ISO_LAYER}.get(self.view)

    def sync(self, mesh, selection) -> None:
        self.dirty = False
        layer = self.layer()
        key = (layer, self.provider.revision)
        if key == self._key:
            return
        self._key = key
        cage, iso = [], []
        if layer == CAGE_LAYER:
            p = self.provider.control_positions()
            cage = [(p[a], p[b]) for a, b in self.provider.control_edges()]
        elif layer == ISO_LAYER:
            p = self.provider.derived_positions()
            iso = [(p[a], p[b]) for a, b in self.provider.iso_edges()]
        self.segments = {CAGE_LAYER: cage, ISO_LAYER: iso}
        if self.sink is not None:
            self.sink.set_cage(cage)
            self.sink.set_iso(iso)

    def draw(self, camera_uniforms) -> None:
        layer = self.layer()
        if self.sink is None or layer is None:
            return
        self.sink.cage_depth_test = self.cage_depth_test
        self.sink.draw(camera_uniforms, layers=(layer,))
