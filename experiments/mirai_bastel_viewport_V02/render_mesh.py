"""RenderMesh — Herzstück des V0.2-Proofs.

Verbindet Core-Geometrie (Mesh), Derived Data (Normalen/Bounds) und den
Ressourcen-Store über einen Dirty-State. Enthält die zentrale
Entscheidungslogik, welche Update-Kategorie welche Ressource verändern darf
und wann ein Partial-Update vs. ein Structural-Rebuild nötig ist.

Ressourcen-Zuordnung (Whitebox-Audit):
    camera   -> camera_uniforms            (nur Matrizen/Uniforms)
    selection-> highlight_flags            (Overlay, getrennt vom Base-Mesh)
    material -> material_uniforms          (nur Material-Parameter)
    geometry -> positions, normals         (partial) + Bounds (Derived Data)
    topology -> positions, normals, indices, highlight_flags (structural)

Die Logik ist Backend-unabhängig: Sie spricht nur das ``ResourceStore``-
Interface an (Trace- oder PygletStore).
"""
from __future__ import annotations

try:
    from .category import DirtyState
    from .derived import DerivedData
    from .mesh import Mesh
    from .renderer import ResourceStore, TraceStore
    from .stats import Stats
except ImportError:  # direkter Skript-Aufruf
    from category import DirtyState
    from derived import DerivedData
    from mesh import Mesh
    from renderer import ResourceStore, TraceStore
    from stats import Stats

FLOAT_BYTES = 4


def _flatten(values, n: int) -> list[float]:
    """Wandelt eine Liste von n-Tupeln in ein flaches float-Array um."""
    out: list[float] = []
    for v in values:
        out.extend(v)
    return out


class RenderMesh:
    def __init__(self, mesh: Mesh, store_type=TraceStore) -> None:
        self.mesh = mesh
        self.stats = Stats()
        self.store = store_type(self.stats)
        self.derived = DerivedData(mesh)
        self.dirty = DirtyState()
        self.camera = None
        self.selection = None
        self.material = None
        self.aspect = 1.0

    # -- Konfiguration (zustandsbehaftete Kategorien) ----------------------
    def bind_camera(self, camera) -> None:
        self.camera = camera

    def bind_selection(self, selection) -> None:
        self.selection = selection

    def bind_material(self, material) -> None:
        self.material = material

    # -- Initialer Aufbau (Test 1: erlaubt) ---------------------------------
    def build(self) -> None:
        """Voller initialer Resource-Aufbau + Derived-Data."""
        self.mesh._rebuild_adjacency()
        self.derived.full_recompute(self.mesh)
        self._rebuild_resources(structural_reason="initial_build")
        self.stats.count("mesh_rebuilds")
        self.stats.count("structural_rebuilds")

    def _rebuild_resources(self, structural_reason: str) -> None:
        n_verts = len(self.mesh.positions)
        n_tris = len(self.mesh.triangles)

        def put(name: str, data: list[float]) -> None:
            nbytes = len(data) * FLOAT_BYTES
            had = name in self.store._resources
            self.store.allocate(name, nbytes)  # structural (ggf. Recreation)
            self.store.update(name, 0, data, nbytes)
            if had:
                # strukturelle Recreation einer bestehenden Ressource
                self.stats.count("structural_rebuilds")

        put("positions", _flatten(self.mesh.positions, 3))
        put("normals", _flatten(self.derived.vertex_normals, 3))
        put("indices", _flatten(self.mesh.triangles, 3))
        if self.selection is not None:
            put("highlight_flags", self.selection.build_highlight_flags(n_verts))
        if self.material is not None:
            put("material_uniforms", self.material.uniform_packet())
        if self.camera is not None:
            put("camera_uniforms", self._camera_uniforms())

    def _camera_uniforms(self) -> list[float]:
        view = self.camera.build_view_matrix()
        proj = self.camera.build_projection_matrix(self.aspect)
        return view + proj

    # -- Änderungs-API (markiert nur Dirty-State) ---------------------------
    def move_vertex(self, vid: int, new_pos) -> None:
        self.mesh.move_vertex(vid, new_pos)
        self.dirty.geometry = True
        self.dirty.geometry_rev += 1
        self.dirty.modified_vertices.add(vid)

    def apply_topology(self, new_mesh: Mesh) -> None:
        self.mesh = new_mesh
        self.mesh._rebuild_adjacency()
        self.dirty.topology = True
        self.dirty.topology_rev += 1
        self.dirty.modified_vertices.clear()

    def apply_selection(self) -> None:
        self.dirty.selection = True
        self.dirty.selection_rev += 1

    def apply_material(self) -> None:
        self.dirty.material = True
        self.dirty.material_rev += 1

    def apply_camera(self, aspect: float | None = None) -> None:
        if aspect is not None:
            self.aspect = aspect
        self.dirty.camera = True
        self.dirty.camera_rev += 1

    # -- Synchronisieren (der eigentliche Incremental-Update-Flow) ----------
    def sync(self) -> None:
        self.stats.start("sync")
        if self.dirty.topology:
            self._sync_topology()
        if self.dirty.geometry:
            self._sync_geometry()
        if self.dirty.selection:
            self._sync_selection()
        if self.dirty.material:
            self._sync_material()
        if self.dirty.camera:
            self._sync_camera()
        self.dirty.reset()
        self.stats.stop("sync")

    # -- Kategorie-Syncs -----------------------------------------------------
    def _sync_topology(self) -> None:
        self.stats.count("topology_updates")
        # Structural rebuild: neue Ressourcen-IDs für die strukturgebenden
        # Ressourcen (positions/normals/indices/highlight_flags).
        self.derived.full_recompute(self.mesh)
        n_verts = len(self.mesh.positions)
        flags = (
            self.selection.build_highlight_flags(n_verts)
            if self.selection is not None
            else [0.0] * n_verts
        )
        self._rebuild_resources(structural_reason="topology")
        self.store.update("highlight_flags", 0, flags, len(flags) * FLOAT_BYTES)
        self.stats.count("structural_rebuilds")
        self.stats.count("mesh_rebuilds")

    def _sync_geometry(self) -> None:
        moved = self.dirty.modified_vertices
        if not moved:
            return
        self.stats.count("vertex_updates", len(moved))
        face_ids, vert_ids = self.derived.affected_neighborhood(self.mesh, moved)
        self.derived.update_face_normals(self.mesh, face_ids)
        self.derived.update_vertex_normals(self.mesh, vert_ids)

        # Bounds sind Derived Data -> kein Structural-Rebuild, nur Recalc
        self.derived.recompute_bounds(self.mesh.positions)
        self.stats.count("bounds_recalculations")

        # Positions-Partial-Upload (nur verschobene Vertices)
        for v in moved:
            data = list(self.mesh.positions[v])
            self.store.update("positions", v * 3, data, 3 * FLOAT_BYTES)
            self.stats.count("geometry_uploads")
            self.stats.count("partial_updates")

        # Normalen-Partial-Upload (nur betroffene Vertices)
        for v in vert_ids:
            data = list(self.derived.vertex_normals[v])
            self.store.update("normals", v * 3, data, 3 * FLOAT_BYTES)
            self.stats.count("geometry_uploads")
            self.stats.count("partial_updates")

    def _sync_selection(self) -> None:
        if self.selection is None:
            return
        self.stats.count("selection_updates")
        flags = self.selection.build_highlight_flags(len(self.mesh.positions))
        # Nur die Overlay-Ressource, kein Base-Mesh-GPU-Buffer
        self.store.update("highlight_flags", 0, flags, len(flags) * FLOAT_BYTES)
        self.stats.count("partial_updates")

    def _sync_material(self) -> None:
        if self.material is None:
            return
        self.stats.count("material_updates")
        pkt = self.material.uniform_packet()
        self.store.update("material_uniforms", 0, pkt, len(pkt) * FLOAT_BYTES)
        self.stats.count("partial_updates")

    def _sync_camera(self) -> None:
        if self.camera is None:
            return
        self.stats.count("camera_updates")
        uniforms = self._camera_uniforms()
        # nur Uniforms-Ressource; kein Mesh-/Geometry-/Topology-Zugriff
        if "camera_uniforms" not in self.store._resources:
            self.store.allocate("camera_uniforms", len(uniforms) * FLOAT_BYTES)
        self.store.update("camera_uniforms", 0, uniforms, len(uniforms) * FLOAT_BYTES)
        self.stats.count("partial_updates")

