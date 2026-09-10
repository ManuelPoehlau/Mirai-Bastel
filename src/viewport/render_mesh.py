"""RenderMesh — Herzstück des Viewport v0.2 (VIEWPORT_V02_ARCHITECTURE.md §4.2, §7).

Adaptiert aus dem verifizierten Proof-of-Architecture-Experiment
(`experiments/mirai_bastel_viewport_V02/render_mesh.py`, 10/10 Tests +
GPU-Live-Check) auf die reale `src.core.Mesh`-API.

Verbindet Core-Geometrie (`core.Mesh`, read-only), Derived Data
(`DerivedGeometry`) und den Ressourcen-Store (`ResourceStore`) über einen
Dirty-State (`DirtyState`). Enthält die zentrale Entscheidungslogik, welche
Update-Kategorie welche Ressource verändern darf und wann ein Partial-Update
vs. ein Structural-Rebuild nötig ist.

Ressourcen-Zuordnung (Whitebox-Audit, siehe VIEWPORT_V02_ARCHITECTURE.md §7):

    camera    -> camera_uniforms              (nur Matrizen/Uniforms)
    selection -> highlight_flags              (Overlay, getrennt vom Base-Mesh)
    material  -> material_uniforms            (nur Material-Parameter, optional)
    geometry  -> positions, normals           (partial) + Bounds (Derived Data)
    topology  -> positions, normals, indices, highlight_flags (structural)

Wichtiger Architektur-Unterschied zum Experiment: `RenderMesh` MUTIERT die
Core-Mesh NICHT selbst (das Experiment tat dies über `move_vertex()`).
Mutation läuft ausschließlich über Core-Operationen + History, angestoßen
von `src.mirai`. `RenderMesh` wird stattdessen über `mark_vertices_dirty()`
/ `mark_topology_dirty()` von außen informiert, WAS sich geändert hat, und
liest die aktuellen Werte danach selbst aus der (bereits mutierten) Mesh.
Das hält den Viewport vollständig unabhängig von `src.mirai` (siehe
Paket-Docstring in `__init__.py`).

Face-Boundaries in der Core-Mesh sind n-gonal (i. d. R. Quads, siehe
`scene_factory.create_cube`), das GPU-Indexbuffer-Format braucht aber
Dreiecke -> Fan-Triangulierung über `derived.triangulate_face()`, ausgeführt
bei jedem (Re-)Aufbau des Indexbuffers (nur bei Topology-Changes, siehe
`_rebuild_index_buffer`).
"""

from __future__ import annotations

from core import FaceId, Mesh, VertexId

from .benchmark import BenchmarkCounters
from .category import DirtyState
from .derived import DerivedGeometry, triangulate_face
from .overlay import SelectionOverlay
from .resource_store import ResourceStore, TraceStore

FLOAT_BYTES = 4
COMPONENTS_PER_VERTEX = 3  # vec3: Position bzw. Normale


def _flatten_vec3(values) -> list[float]:
    out: list[float] = []
    for v in values:
        out.extend(v)
    return out


class RenderMesh:
    """Persistente GPU-Geometrie + Dirty-State-gesteuertes Sync.

    Grundprinzip (VIEWPORT_V02_ARCHITECTURE.md §2): GPU-Ressourcen einmal
    anlegen, Inhalt patchen. Ressourcen werden NUR bei einer Topology-
    Änderung strukturell neu angelegt (`_rebuild_resources`), niemals bei
    Camera-, Selection-, Material- oder reinen Positions-Updates.
    """

    def __init__(
        self,
        mesh: Mesh,
        overlay: SelectionOverlay | None = None,
        store_type: type[ResourceStore] = TraceStore,
    ) -> None:
        self.mesh = mesh
        self.stats = BenchmarkCounters()
        self.store: ResourceStore = store_type(self.stats)
        self.derived = DerivedGeometry(mesh)
        self.dirty = DirtyState()
        self.overlay = overlay

        self.camera = None  # duck-typed: build_view_matrix()/build_projection_matrix(aspect)
        self.material = None  # duck-typed: uniform_packet()
        self.aspect = 1.0

        # Stabile Buffer-Reihenfolge für diese Session: VertexId -> flacher
        # Index. Wird nur bei Topology-Änderung neu aufgebaut (siehe
        # `_rebuild_resources`) — Positions-Updates dürfen diese Reihenfolge
        # NICHT ändern, sonst wären Partial-Updates falsch adressiert.
        self._vertex_index: dict[VertexId, int] = {}
        self._triangle_indices: list[tuple[VertexId, VertexId, VertexId]] = []

        self.build()

    # -- Konfiguration (zustandsbehaftete Kategorien) -----------------------

    def bind_camera(self, camera) -> None:
        """`camera` muss `build_view_matrix()`/`build_projection_matrix(aspect)`
        bereitstellen (duck-typed, siehe Paket-Docstring)."""
        self.camera = camera

    def bind_material(self, material) -> None:
        self.material = material

    # -- Initialer Aufbau (Test 1 in VIEWPORT_V02_ARCHITECTURE.md §13: erlaubt) --

    def build(self) -> None:
        """Voller initialer Resource-Aufbau + Derived-Data-Recompute."""
        self.derived.full_recompute(self.mesh)
        self._rebuild_index_mapping()
        self._rebuild_resources()
        self.stats.count("mesh_rebuilds")
        self.stats.count("structural_rebuilds")

    def _rebuild_index_mapping(self) -> None:
        """Baut die stabile VertexId -> Flat-Index-Zuordnung + triangulierten
        Indexbuffer neu auf (nur bei Topology-Change/Initial nötig)."""
        self._vertex_index = {
            vertex_id: i for i, vertex_id in enumerate(self.mesh.all_vertex_ids())
        }
        triangles: list[tuple[VertexId, VertexId, VertexId]] = []
        for face_id in self.mesh.all_face_ids():
            boundary = self.mesh.face_vertices(face_id)
            triangles.extend(triangulate_face(boundary))
        self._triangle_indices = triangles

    def _positions_flat(self) -> list[float]:
        ordered = sorted(self._vertex_index.items(), key=lambda kv: kv[1])
        return _flatten_vec3(self.mesh.vertex_position(v) for v, _ in ordered)

    def _normals_flat(self) -> list[float]:
        ordered = sorted(self._vertex_index.items(), key=lambda kv: kv[1])
        return _flatten_vec3(self.derived.vertex_normals[v] for v, _ in ordered)

    def _indices_flat(self) -> list[float]:
        flat: list[float] = []
        for tri in self._triangle_indices:
            flat.extend(float(self._vertex_index[v]) for v in tri)
        return flat

    def _rebuild_resources(self) -> None:
        n_verts = len(self._vertex_index)

        def put(name: str, data: list[float]) -> None:
            had = self.store.has(name)
            nbytes = len(data) * FLOAT_BYTES
            self.store.allocate(name, nbytes)
            self.store.update(name, 0, data, nbytes)
            if had:
                # Structural Recreation einer bereits existierenden Ressource.
                self.stats.count("structural_rebuilds")

        put("positions", self._positions_flat())
        put("normals", self._normals_flat())
        put("indices", self._indices_flat())

        if self.overlay is not None:
            put("highlight_flags", self.overlay.build_highlight_flags(self.mesh))
        if self.material is not None:
            put("material_uniforms", self.material.uniform_packet())
        if self.camera is not None:
            put("camera_uniforms", self._camera_uniforms())

        # Nur echte Neuanlage zählt hier als "n_verts" gebraucht:
        _ = n_verts  # (nur zur Lesbarkeit belassen; kein weiterer Zweck hier)

    def _camera_uniforms(self) -> list[float]:
        view = self.camera.build_view_matrix()
        proj = self.camera.build_projection_matrix(self.aspect)
        return list(view) + list(proj)

    # -- Änderungs-API (markiert NUR Dirty-State; mutiert die Mesh NICHT) ----

    def mark_vertices_dirty(self, vertex_ids: set[VertexId]) -> None:
        """Informiert RenderMesh, dass die gegebenen Vertices in der (bereits
        mutierten) Core-Mesh eine neue Position haben. Die tatsächliche
        Positions-Mutation läuft über Core-Operationen (`src.mirai`),
        NICHT hier."""
        if not vertex_ids:
            return
        self.dirty.geometry = True
        self.dirty.geometry_rev += 1
        self.dirty.modified_vertices.update(vertex_ids)

    def mark_topology_dirty(self) -> None:
        """Informiert RenderMesh, dass sich die Topologie geändert hat
        (Face/Edge-Mutation über Core-Operationen). Erzwingt beim nächsten
        `sync()` einen strukturellen Rebuild aller Kern-Ressourcen."""
        self.dirty.topology = True
        self.dirty.topology_rev += 1
        self.dirty.modified_vertices.clear()

    def mark_selection_dirty(self) -> None:
        self.dirty.selection = True
        self.dirty.selection_rev += 1

    def mark_material_dirty(self) -> None:
        self.dirty.material = True
        self.dirty.material_rev += 1

    def mark_camera_dirty(self, aspect: float | None = None) -> None:
        if aspect is not None:
            self.aspect = aspect
        self.dirty.camera = True
        self.dirty.camera_rev += 1

    # -- Synchronisieren (der eigentliche Incremental-Update-Flow) ----------

    def sync(self) -> None:
        """Verarbeitet alle seit dem letzten `sync()` markierten Kategorien.

        Reihenfolge ist bewusst: Topology zuerst (macht Geometry-Dirty-State
        für denselben Frame obsolet, da `build()`/`_rebuild_resources` schon
        alles aktuelle schreibt), danach Geometry/Selection/Material/Camera
        unabhängig voneinander (Interleaving, siehe `DirtyState`).
        """
        self.stats.start("sync")
        if self.dirty.topology:
            self._sync_topology()
            # Eine Topology-Änderung invalidiert etwaige separat markierte
            # Positions-Deltas desselben Frames (sie sind im Full-Rebuild
            # bereits enthalten) - nicht doppelt verarbeiten.
            self.dirty.geometry = False
            self.dirty.modified_vertices.clear()
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

    # -- Kategorie-Syncs ------------------------------------------------------

    def _sync_topology(self) -> None:
        self.stats.count("topology_updates")
        self.derived.full_recompute(self.mesh)
        self._rebuild_index_mapping()
        self._rebuild_resources()
        self.stats.count("structural_rebuilds")
        self.stats.count("mesh_rebuilds")

    def _sync_geometry(self) -> None:
        moved = self.dirty.modified_vertices
        if not moved:
            return
        self.stats.count("vertex_updates", len(moved))

        affected_faces, affected_vertices = self.derived.affected_neighborhood(
            self.mesh, moved
        )
        self.derived.update_face_normals(self.mesh, affected_faces)
        self.derived.update_vertex_normals(self.mesh, affected_vertices)

        # Bounds sind Derived Data -> kein Structural-Rebuild, nur Recalc.
        self.derived.recompute_bounds(self.mesh)
        self.stats.count("bounds_recalculations")
        self.stats.count("normal_recomputations")

        # Positions-Partial-Upload: NUR die verschobenen Vertices.
        for vertex_id in moved:
            idx = self._vertex_index[vertex_id]
            data = list(self.mesh.vertex_position(vertex_id))
            self.store.update(
                "positions", idx * COMPONENTS_PER_VERTEX, data,
                COMPONENTS_PER_VERTEX * FLOAT_BYTES,
            )
            self.stats.count("geometry_uploads")
            self.stats.count("partial_updates")

        # Normalen-Partial-Upload: NUR die betroffenen Vertices (1-Ring).
        for vertex_id in affected_vertices:
            idx = self._vertex_index[vertex_id]
            data = list(self.derived.vertex_normals[vertex_id])
            self.store.update(
                "normals", idx * COMPONENTS_PER_VERTEX, data,
                COMPONENTS_PER_VERTEX * FLOAT_BYTES,
            )
            self.stats.count("geometry_uploads")
            self.stats.count("partial_updates")

    def _sync_selection(self) -> None:
        if self.overlay is None:
            return
        self.stats.count("selection_updates")
        flags = self.overlay.build_highlight_flags(self.mesh)
        # Nur die Overlay-Ressource - KEIN Base-Mesh-Buffer wird angefasst.
        self.store.update("highlight_flags", 0, flags, len(flags) * FLOAT_BYTES)
        self.stats.count("partial_updates")

    def _sync_material(self) -> None:
        if self.material is None:
            return
        self.stats.count("material_updates")
        packet = self.material.uniform_packet()
        self.store.update(
            "material_uniforms", 0, packet, len(packet) * FLOAT_BYTES
        )
        self.stats.count("partial_updates")

    def _sync_camera(self) -> None:
        if self.camera is None:
            return
        self.stats.count("camera_updates")
        uniforms = self._camera_uniforms()
        if not self.store.has("camera_uniforms"):
            self.store.allocate("camera_uniforms", len(uniforms) * FLOAT_BYTES)
        self.store.update(
            "camera_uniforms", 0, uniforms, len(uniforms) * FLOAT_BYTES
        )
        self.stats.count("partial_updates")

    # -- Zugriff für Rendering/Tests ------------------------------------------

    @property
    def benchmark_counters(self) -> dict:
        return dict(self.stats.counters)

    def resource_ids(self) -> dict[str, int]:
        return self.store.resource_ids()

    def vertex_index_of(self, vertex_id: VertexId) -> int:
        return self._vertex_index[vertex_id]
