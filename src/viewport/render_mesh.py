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
Dreiecke -> Triangulierung über `derived.triangulate_face()`.

Inkrementelle Topologie (AD-023 V1, 2026-10-21): `RenderMesh` beobachtet seine Mesh über
`Mesh.watch()` (Änderungs-Journal). Ein Topology-Sync patcht nur, was das Journal meldet:
neue/entfernte/geänderte Faces und Vertices, dazu die Faces um bewegte Vertices (neu
trianguliert, weil die Triangulierung von den Positionen abhängt). Layout-Regel ("Slots"):
zwischen zwei vollen Rebuilds behält jeder Vertex seinen Buffer-Index, jede Face ihre
Face-Daten-Zeile und ihre Dreiecks-Slots; ein entfernter Vertex bekommt `DEAD_POSITION`, ein
freier Dreiecks-Slot wird degeneriert (`(0, 0, 0)`: kein Fragment, `gl_PrimitiveID` und
`triangle_faces` bleiben für jedes lebende Dreieck gültig). Neue Elemente nehmen freie Slots;
ein voller Rebuild legt `SPARE_FRACTION` Reserve an. Voll neu aufgebaut wird nur beim ersten
Aufbau, wenn die Reserve nicht reicht, bei sehr großen Änderungen (`PATCH_MAX_FRACTION`) und
bei kleinen Meshes (`INCREMENTAL_MIN_ELEMENTS`: dort kostet der Rebuild Mikrosekunden und das
kompakte Layout bleibt, wie es Tests und Werkzeuge lesen). Gleichwertigkeit "Patch == voller
Rebuild" pro Element: `tests/test_render_mesh_incremental.py`.

AD-018 §5 (Option B, additiv): `_rebuild_resources()` deklariert einmalig
(im Konstruktor) über `ResourceStore.declare_group()`/`declare_uniform()`,
welche der vier Kern-Ressourcen (`positions`/`normals`/`highlight_flags` +
`indices`) zusammen EIN drawbares GPU-Objekt bilden, und dass
`camera_uniforms`/`material_uniforms` reine Uniforms sind - statt dass ein
Store das aus der Aufrufreihenfolge in `_rebuild_resources()` erraten muss
(die Fragilität, die der Draw-Binding-Spike als offenen Befund gemeldet
hat, siehe AD-018 §2 Option A). `_rebuild_resources()` klammert die
Vertex-Gruppen-Puts zusätzlich in `begin_rebuild()`/`end_rebuild()` - ein
Store weiß dadurch unzweideutig, wann ein zusammengehöriger Rebuild-Zyklus
beginnt/endet, statt das aus "alle Trio-Mitglieder frisch alloziert" zu
folgern. WAS berechnet wird und WANN `sync()` dispatcht, ist dadurch
unverändert - nur wie der Store über die Ressourcen-Struktur informiert
wird, ist neu.

Face-Daten (AD-018 Nachtrag 2026-10-15, B5a.1 + Smooth ohne Dreiecks-Diagonale): neben der
Gruppe legt `RenderMesh` zwei Daten-Ressourcen an, die der Fragment-Shader über die
Dreiecksnummer (`gl_PrimitiveID`) liest - `triangle_faces` (je Dreieck in Indexbuffer-
Reihenfolge die Zeile seiner Face) und `face_shading` (je Face eine Zeile, `FACE_ROW_FLOATS`:
Newell-Normale + Eckenzahl, vier Eck-Positionen, vier Eck-Normalen). Damit schattiert Flat eine
Normale pro Polygon statt pro Dreieck, und Smooth interpoliert die Normalen über ein Quad
bilinear statt pro Dreieck linear. Die Vertex-Gruppe bleibt unverändert. `triangle_faces` ändert
sich nur strukturell; `face_shading` wird beim Verschieben zeilenweise gepatcht (die Faces um
alle Vertices, deren Normale sich geändert hat).
"""

from __future__ import annotations

from array import array

from core import EdgeId, FaceId, Mesh, VertexId

from .benchmark import BenchmarkCounters
from .category import DirtyState
from .derived import DerivedGeometry, _normalize, face_normal, triangulate_face
from .overlay import SelectionOverlay
from .resource_store import ResourceStore, TraceStore

FLOAT_BYTES = 4
COMPONENTS_PER_VERTEX = 3  # vec3: Position bzw. Normale

# AD-018 §5: Layout-Deklaration für die "mesh"-Attributgruppe. Einmalig an
# den Store übergeben (siehe `RenderMesh.__init__`), damit ein Store, der
# ein drawbares Objekt bauen will (z. B. `GLRenderStore`), nicht mehr aus
# der Aufrufreihenfolge in `_rebuild_resources()` erraten muss, welche
# Ressourcen zusammengehören.
MESH_GROUP = "mesh"
MESH_GROUP_ATTRIBUTES: dict[str, tuple[str, int]] = {
    "positions": ("position", COMPONENTS_PER_VERTEX),
    "normals": ("normal", COMPONENTS_PER_VERTEX),
    "highlight_flags": ("highlight_flag", 1),
}
MESH_GROUP_INDEX = "indices"

FACE_DATA = "face_shading"
TRIANGLE_FACES = "triangle_faces"
#: Texel (vec4) je Face-Zeile: (Normale, Eckenzahl), 4 Eck-Positionen, 4 Eck-Normalen.
FACE_ROW_TEXELS = 9
FACE_ROW_FLOATS = FACE_ROW_TEXELS * 4
#: Ecken, für die der Shader bilinear interpoliert (nur Quads; Dreiecke sind schon linear exakt).
_FACE_ROW_CORNERS = 4

_IDENTITY_4 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)

#: Inkrementeller Topology-Sync erst ab so vielen Vertices + Faces (`PROVISIONAL`); darunter ist der
#: volle Rebuild billiger als jede Buchführung und das Layout bleibt kompakt.
INCREMENTAL_MIN_ELEMENTS = 2048
#: Reserve-Slots je vollem Rebuild (Vertices, Face-Zeilen, Dreiecke) als Anteil der lebenden Anzahl.
SPARE_FRACTION = 0.125
#: Eine Änderung, die mehr als diesen Anteil der Elemente berührt, wird voll neu aufgebaut.
PATCH_MAX_FRACTION = 0.25
#: Position eines freien Vertex-Slots (kein lebendes Dreieck referenziert ihn); endlich in float32.
DEAD_COORD = 1.0e19
DEAD_POSITION = (DEAD_COORD, DEAD_COORD, DEAD_COORD)
_ZERO3 = (0.0, 0.0, 0.0)
_DEAD_TRIANGLE = (0.0, 0.0, 0.0)


def _flatten_vec3(values) -> list[float]:
    out: list[float] = []
    for v in values:
        out.extend(v)
    return out


def _runs(slots) -> list[list[int]]:
    """Aufsteigende Slots in Läufe aufeinanderfolgender Werte (ein Upload je Lauf)."""
    runs: list[list[int]] = []
    for slot in sorted(slots):
        if runs and slot == runs[-1][-1] + 1:
            runs[-1].append(slot)
        else:
            runs.append([slot])
    return runs


class RenderMesh:
    """Persistente GPU-Geometrie + Dirty-State-gesteuertes Sync.

    Grundprinzip (VIEWPORT_V02_ARCHITECTURE.md §2): GPU-Ressourcen einmal
    anlegen, Inhalt patchen. Ressourcen werden nur beim ersten Aufbau und wenn
    ein Topology-Patch nicht möglich ist strukturell neu angelegt
    (`_rebuild_resources`), niemals bei Camera-, Selection-, Material- oder
    reinen Positions-Updates.
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
        self.store.declare_group(MESH_GROUP, MESH_GROUP_ATTRIBUTES, MESH_GROUP_INDEX)
        self.store.declare_uniform("camera_uniforms")
        self.store.declare_uniform("material_uniforms")
        # AD-021 M2-1 (E-9): Objekt -> Welt. Erst beim ersten `set_model_matrix` geschrieben, so
        # dass ein nie platziertes Objekt genau die bisherigen Ressourcen hat.
        self.store.declare_uniform("model_uniforms")
        self.store.declare_face_data(FACE_DATA, TRIANGLE_FACES, FACE_ROW_TEXELS)
        # Änderungs-Journal der Mesh (AD-023 V1): was sich seit dem letzten Sync geändert hat.
        self._watch = mesh.watch()
        self.derived = DerivedGeometry(
            mesh, on_bounds_recomputed=lambda: self.stats.count("bounds_recalculations")
        )
        self.dirty = DirtyState()
        self.overlay = overlay

        self.camera = None  # duck-typed: build_view_matrix()/build_projection_matrix(aspect)
        self.material = None  # duck-typed: uniform_packet()
        self.aspect = 1.0
        # AD-021 M2-1: 4x4 spaltenweise (None = Identität) und ob der Store sie noch braucht.
        self.model_matrix: list[float] | None = None
        self._model_dirty = False

        # Slot-Layout (Modul-Docstring): VertexId -> Buffer-Index und zurück, freie Slots.
        # Positions-Updates dürfen diese Zuordnung NICHT ändern, sonst wären Partial-Updates
        # falsch adressiert.
        self._vertex_index: dict[VertexId, int] = {}
        self._slot_vertex: list[VertexId | None] = []
        self._free_vertex_slots: list[int] = []
        # Je Dreiecks-Slot die drei Vertices (None = frei) und die Face-Zeile.
        self._triangle_indices: list[tuple[VertexId, VertexId, VertexId] | None] = []
        self._triangle_face_rows: list[int] = []
        self._free_triangles: list[int] = []
        # Face-Daten: FaceId -> Zeile (und zurück), Dreiecks-Slots je Face, Boundary bei der
        # letzten Triangulierung.
        self._face_row: dict[FaceId, int] = {}
        self._row_face: list[FaceId | None] = []
        self._free_rows: list[int] = []
        self._face_triangles: dict[FaceId, list[int]] = {}
        self._face_boundary: dict[FaceId, tuple] = {}
        # Vertices, die ein Geometry-Sync seit ihrer letzten Triangulierung bewegt hat: ihre
        # Faces werden beim nächsten Topology-Sync neu trianguliert (ein W-Drag trianguliert nicht).
        self._retriangulate: set[VertexId] = set()
        # Edge-Slots (AD-022 B2, 2026-10-21): je Slot die beiden Vertex-Slots (frei = (0, 0), eine
        # Linie ohne Länge, die nichts rasterisiert). Kein Store-Inhalt: der GPU-Picker
        # (`gpu_picker.py`) lädt sie als eigenen Index-Buffer über die `positions` dieser Mesh;
        # `take_edge_changes()` sagt ihm, welche Slots sich seitdem geändert haben.
        self._edge_slot: dict[EdgeId, int] = {}
        self._slot_edge: list[EdgeId | None] = []
        self._free_edge_slots: list[int] = []
        self.edge_indices = array("I")
        self._edge_dirty: set[int] | None = None
        #: +1 je vollem Rebuild (alle Slots neu vergeben) und je Änderung irgendeines Buffer-Inhalts
        #: (Topology-Patch, Geometry-Sync): Cache-Schlüssel für Konsumenten wie den GPU-Picker.
        self.layout_revision = 0
        self.content_revision = 0

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
        self._watch.take()
        self._full_rebuild()
        self.stats.count("mesh_rebuilds")
        self.stats.count("structural_rebuilds")

    def _incremental(self) -> bool:
        return len(self._vertex_index) + len(self._face_row) >= INCREMENTAL_MIN_ELEMENTS

    def _full_rebuild(self) -> None:
        self.derived.full_recompute(self.mesh)
        self._rebuild_index_mapping()
        self._rebuild_resources()
        self.layout_revision += 1
        self.content_revision += 1

    def _rebuild_edge_slots(self, spare: bool) -> None:
        eids = self.mesh.all_edge_ids()
        edge_vertices = self.mesh.edge_vertices
        index = self._vertex_index
        n = len(eids)
        spare_e = int(n * SPARE_FRACTION) if spare else 0
        self._edge_slot = {eid: i for i, eid in enumerate(eids)}
        self._slot_edge = list(eids) + [None] * spare_e
        self._free_edge_slots = list(range(n + spare_e - 1, n - 1, -1))
        flat = array("I", bytes(4 * 2 * (n + spare_e)))
        i = 0
        for eid in eids:
            a, b = edge_vertices(eid)
            flat[i] = index[a]
            flat[i + 1] = index[b]
            i += 2
        self.edge_indices = flat
        self._edge_dirty = None

    def take_edge_changes(self) -> set[int] | None:
        """Edge-Slots, deren Indizes sich seit dem letzten Aufruf geändert haben; None = alle (neues
        Layout). Genau ein Konsument (der GPU-Picker der Viewport)."""
        dirty, self._edge_dirty = self._edge_dirty, set()
        return dirty

    def edge_of_slot(self, slot: int) -> EdgeId | None:
        return self._slot_edge[slot] if 0 <= slot < len(self._slot_edge) else None

    def vertex_of_slot(self, slot: int) -> VertexId | None:
        return self._slot_vertex[slot] if 0 <= slot < len(self._slot_vertex) else None

    def face_of_triangle(self, triangle: int) -> FaceId | None:
        """Die Face des Dreiecks-Slots `triangle` (= `gl_PrimitiveID` im Draw des Index-Buffers);
        None für einen freien Slot."""
        if not 0 <= triangle < len(self._triangle_indices) or self._triangle_indices[triangle] is None:
            return None
        return self._row_face[self._triangle_face_rows[triangle]]

    def _rebuild_index_mapping(self) -> None:
        """Baut das Slot-Layout neu auf: kompakt in Mesh-Reihenfolge, dahinter die Reserve
        (nur für Meshes, die inkrementell synchronisiert werden)."""
        mesh = self.mesh
        vids = mesh.all_vertex_ids()
        fids = mesh.all_face_ids()
        position = mesh.vertex_position
        face_vertices = mesh.face_vertices
        positions = {v: position(v) for v in vids}
        spare = len(vids) + len(fids) >= INCREMENTAL_MIN_ELEMENTS

        self._vertex_index = {vertex_id: i for i, vertex_id in enumerate(vids)}
        triangles: list = []
        triangle_rows: list[int] = []
        face_row: dict[FaceId, int] = {}
        face_triangles: dict[FaceId, list[int]] = {}
        face_boundary: dict[FaceId, tuple] = {}
        for row, face_id in enumerate(fids):
            face_row[face_id] = row
            boundary = face_vertices(face_id)
            face_boundary[face_id] = tuple(boundary)
            tris = triangulate_face(boundary, positions)
            first = len(triangles)
            triangles.extend(tris)
            triangle_rows.extend([row] * len(tris))
            face_triangles[face_id] = list(range(first, len(triangles)))

        n_v, n_f, n_t = len(vids), len(fids), len(triangles)
        spare_v = int(n_v * SPARE_FRACTION) if spare else 0
        spare_f = int(n_f * SPARE_FRACTION) if spare else 0
        spare_t = int(n_t * SPARE_FRACTION) if spare else 0
        self._slot_vertex = list(vids) + [None] * spare_v
        self._free_vertex_slots = list(range(n_v + spare_v - 1, n_v - 1, -1))
        self._triangle_indices = triangles + [None] * spare_t
        self._triangle_face_rows = triangle_rows + [0] * spare_t
        self._free_triangles = list(range(n_t + spare_t - 1, n_t - 1, -1))
        self._face_row = face_row
        self._row_face = list(fids) + [None] * spare_f
        self._free_rows = list(range(n_f + spare_f - 1, n_f - 1, -1))
        self._face_triangles = face_triangles
        self._face_boundary = face_boundary
        self._retriangulate = set()
        self._rebuild_edge_slots(spare)

    def _positions_flat(self) -> list[float]:
        position = self.mesh.vertex_position
        return [c for v in self._slot_vertex for c in (DEAD_POSITION if v is None else position(v))]

    def _normals_flat(self) -> list[float]:
        normals = self.derived.vertex_normals
        return [c for v in self._slot_vertex for c in (_ZERO3 if v is None else normals[v])]

    def _indices_flat(self) -> list[float]:
        index = self._vertex_index
        return [
            c for tri in self._triangle_indices
            for c in (_DEAD_TRIANGLE if tri is None else (float(index[tri[0]]), float(index[tri[1]]), float(index[tri[2]])))
        ]

    def _face_row_data(self, face_id: FaceId) -> list[float]:
        boundary = self.mesh.face_vertices(face_id)
        corners = boundary[:_FACE_ROW_CORNERS]
        padding = [0.0] * (4 * (_FACE_ROW_CORNERS - len(corners)))
        position = self.mesh.vertex_position
        normals = self.derived.vertex_normals
        nx, ny, nz = self.derived.face_normals[face_id]
        row = [nx, ny, nz, float(len(boundary))]
        for v in corners:
            x, y, z = position(v)
            row += (x, y, z, 0.0)
        row += padding
        for v in corners:
            x, y, z = normals[v]
            row += (x, y, z, 0.0)
        row += padding
        return row

    def _face_data_flat(self) -> list[float]:
        dead = [0.0] * FACE_ROW_FLOATS
        flat: list[float] = []
        for face_id in self._row_face:
            flat += dead if face_id is None else self._face_row_data(face_id)
        return flat

    def _highlight_flags(self) -> list[float]:
        """Highlight-Flags in Slot-Reihenfolge (die Buffer-Position jedes Vertex)."""
        flags = [0.0] * len(self._slot_vertex)
        index = self._vertex_index
        for vertex_id in self.overlay.highlighted_vertices(self.mesh):
            slot = index.get(vertex_id)
            if slot is not None:
                flags[slot] = 1.0
        return flags

    def _rebuild_resources(self) -> None:
        def put(name: str, data: list[float]) -> None:
            had = self.store.has(name)
            nbytes = len(data) * FLOAT_BYTES
            self.store.allocate(name, nbytes)
            self.store.update(name, 0, data, nbytes)
            if had:
                # Structural Recreation einer bereits existierenden Ressource.
                self.stats.count("structural_rebuilds")

        self.store.begin_rebuild(MESH_GROUP)
        put("positions", self._positions_flat())
        put("normals", self._normals_flat())
        put("indices", self._indices_flat())

        if self.overlay is not None:
            put("highlight_flags", self._highlight_flags())
        self.store.end_rebuild(MESH_GROUP)

        put(TRIANGLE_FACES, [float(row) for row in self._triangle_face_rows])
        put(FACE_DATA, self._face_data_flat())

        if self.material is not None:
            put("material_uniforms", self.material.uniform_packet())
        if self.camera is not None:
            put("camera_uniforms", self._camera_uniforms())

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
        (Face/Edge-Mutation über Core-Operationen). Der nächste `sync()` patcht,
        was das Änderungs-Journal meldet, oder baut alle Kern-Ressourcen neu auf
        (kleine Mesh, Reserve erschöpft, sehr große Änderung)."""
        self.dirty.topology = True
        self.dirty.topology_rev += 1
        self.dirty.modified_vertices.clear()

    def mark_selection_dirty(self) -> None:
        self.dirty.selection = True
        self.dirty.selection_rev += 1

    def mark_material_dirty(self) -> None:
        self.dirty.material = True
        self.dirty.material_rev += 1

    def set_model_matrix(self, matrix: list[float] | None) -> None:
        """Objekt -> Welt (AD-021 M2-1, E-9). Die Positionen im Buffer bleiben Objektraum; der
        Shader wendet die Matrix an. None = Identität. Kein Rebuild, nur eine Uniform."""
        matrix = list(matrix) if matrix is not None else None
        if matrix == self.model_matrix:
            return
        self.model_matrix = matrix
        self._model_dirty = True

    def mark_camera_dirty(self, aspect: float | None = None) -> None:
        if aspect is not None:
            self.aspect = aspect
        self.dirty.camera = True
        self.dirty.camera_rev += 1

    # -- Synchronisieren (der eigentliche Incremental-Update-Flow) ----------

    def sync(self) -> None:
        """Verarbeitet alle seit dem letzten `sync()` markierten Kategorien.

        Reihenfolge ist bewusst: Topology zuerst (macht Geometry-Dirty-State
        für denselben Frame obsolet, da der Topology-Sync alle vom Journal
        gemeldeten Positionen mitschreibt), danach Geometry/Selection/Material/
        Camera unabhängig voneinander (Interleaving, siehe `DirtyState`).
        """
        self.stats.start("sync")
        if self.dirty.topology or self.dirty.geometry:
            change = self._watch.take()
            if self.dirty.topology:
                self._sync_topology(change)
                # Eine Topology-Änderung invalidiert etwaige separat markierte
                # Positions-Deltas desselben Frames (sie sind im Topology-Sync
                # bereits enthalten) - nicht doppelt verarbeiten.
                self.dirty.geometry = False
                self.dirty.modified_vertices.clear()
            elif self._structural(change):
                # Gemeldet als reine Positionsänderung, das Journal zeigt aber neue oder
                # entfernte Elemente: als Topology-Änderung behandeln (nie ein falscher Buffer).
                self._sync_topology(change)
                self.dirty.geometry = False
                self.dirty.modified_vertices.clear()
            else:
                self._retriangulate.update(change.vertices)
        if self.dirty.geometry:
            self._sync_geometry()
        if self.dirty.selection:
            self._sync_selection()
        if self.dirty.material:
            self._sync_material()
        if self.dirty.camera:
            self._sync_camera()
        if self._model_dirty:
            self._sync_model()
        self.dirty.reset()
        self.stats.stop("sync")

    def _structural(self, change) -> bool:
        mesh = self.mesh
        if change.faces:
            return True
        index = self._vertex_index
        return any((v in index) != mesh.is_valid_vertex(v) for v in change.vertices)

    # -- Kategorie-Syncs ------------------------------------------------------

    def _sync_topology(self, change=None) -> None:
        self.stats.count("topology_updates")
        if change is not None and self._incremental() and self._patch_topology(change):
            self.stats.count("topology_patches")
            return
        self._full_rebuild()
        self.stats.count("structural_rebuilds")
        self.stats.count("mesh_rebuilds")

    def _patch_topology(self, change) -> bool:
        """Patcht Slot-Layout, Derived Data und Buffer für die vom Journal gemeldete Änderung
        (Modul-Docstring). False = nichts verändert, der Aufrufer baut voll neu auf."""
        mesh = self.mesh
        index = self._vertex_index
        face_row = self._face_row
        face_boundary = self._face_boundary
        face_triangles = self._face_triangles
        is_valid_face, is_valid_vertex = mesh.is_valid_face, mesh.is_valid_vertex
        face_vertices = mesh.face_vertices

        removed_f, added_f, changed_f = [], [], []
        new_boundary: dict[FaceId, list[VertexId]] = {}
        for f in change.faces:
            alive, known = is_valid_face(f), f in face_row
            if known and not alive:
                removed_f.append(f)
            elif alive:
                b = face_vertices(f)
                if not known:
                    added_f.append(f)
                    new_boundary[f] = b
                elif tuple(b) != face_boundary[f]:
                    changed_f.append(f)
                    new_boundary[f] = b
        removed_v, added_v, moved_v = [], [], []
        for v in change.vertices:
            alive, known = is_valid_vertex(v), v in index
            if known and not alive:
                removed_v.append(v)
            elif alive and not known:
                added_v.append(v)
            elif alive:
                moved_v.append(v)

        edge_slot = self._edge_slot
        is_valid_edge = mesh.is_valid_edge
        removed_e, added_e, changed_e = [], [], []
        for e in change.edges:
            alive, known = is_valid_edge(e), e in edge_slot
            if known and not alive:
                removed_e.append(e)
            elif alive and not known:
                added_e.append(e)
            elif alive:
                changed_e.append(e)

        total = len(index) + len(face_row)
        if len(change.faces) + len(change.vertices) > PATCH_MAX_FRACTION * total:
            return False
        if len(added_e) > len(self._free_edge_slots) + len(removed_e):
            return False
        if len(added_v) > len(self._free_vertex_slots) + len(removed_v):
            return False
        if len(added_f) > len(self._free_rows) + len(removed_f):
            return False
        needed = sum(len(b) - 2 for b in new_boundary.values())
        freed = sum(len(face_triangles[f]) for f in removed_f) + sum(len(face_triangles[f]) for f in changed_f)
        if needed > len(self._free_triangles) + freed:
            return False
        if any(len(b) < 3 for b in new_boundary.values()):
            return False

        derived = self.derived
        v2f, fnormals, vnormals = derived.vertex_to_faces, derived.face_normals, derived.vertex_normals
        position = mesh.vertex_position
        dirty_vertices: set[VertexId] = set()
        pos_slots: dict[int, tuple] = {}
        normal_slots: dict[int, tuple] = {}
        tri_slots: dict[int, tuple] = {}
        row_slots: set[int] = set()

        # Adjazenz: alte Boundaries austragen, neue eintragen.
        for f in (*removed_f, *changed_f):
            old = face_boundary[f]
            for v in old:
                faces_of = v2f.get(v)
                if faces_of is not None:
                    faces_of.discard(f)
            dirty_vertices.update(old)
        for f, b in new_boundary.items():
            for v in b:
                faces_of = v2f.get(v)
                if faces_of is None:
                    v2f[v] = {f}
                else:
                    faces_of.add(f)

        def free_triangles(f: FaceId) -> None:
            for t in face_triangles.pop(f):
                self._triangle_indices[t] = None
                self._triangle_face_rows[t] = 0
                self._free_triangles.append(t)
                tri_slots[t] = _DEAD_TRIANGLE

        for f in removed_f:
            free_triangles(f)
            row = face_row.pop(f)
            self._row_face[row] = None
            self._free_rows.append(row)
            row_slots.add(row)
            del face_boundary[f]
            fnormals.pop(f, None)
        for f in changed_f:
            free_triangles(f)
        for v in removed_v:
            slot = index.pop(v)
            self._slot_vertex[slot] = None
            self._free_vertex_slots.append(slot)
            pos_slots[slot] = DEAD_POSITION
            normal_slots[slot] = _ZERO3
            vnormals.pop(v, None)
            if not v2f.get(v, True):
                del v2f[v]
            self._retriangulate.discard(v)
        for v in added_v:
            slot = self._free_vertex_slots.pop()
            index[v] = slot
            self._slot_vertex[slot] = v
            pos_slots[slot] = position(v)
        for v in moved_v:
            pos_slots[index[v]] = position(v)

        edge_indices = self.edge_indices
        edge_dirty = self._edge_dirty
        for e in removed_e:
            slot = edge_slot.pop(e)
            self._slot_edge[slot] = None
            self._free_edge_slots.append(slot)
            edge_indices[2 * slot] = edge_indices[2 * slot + 1] = 0
            if edge_dirty is not None:
                edge_dirty.add(slot)
        edge_vertices = mesh.edge_vertices
        for e in (*added_e, *changed_e):
            slot = edge_slot.get(e)
            if slot is None:
                slot = edge_slot[e] = self._free_edge_slots.pop()
                self._slot_edge[slot] = e
            a, b = edge_vertices(e)
            edge_indices[2 * slot] = index[a]
            edge_indices[2 * slot + 1] = index[b]
            if edge_dirty is not None:
                edge_dirty.add(slot)

        # Neu triangulieren: neue / geänderte Faces und alle Faces um bewegte Vertices.
        retri: set[FaceId] = set(new_boundary)
        for v in (*moved_v, *self._retriangulate):
            faces_of = v2f.get(v)
            if faces_of:
                retri.update(faces_of)
        self._retriangulate = set()
        for f in retri:
            b = new_boundary.get(f) or face_vertices(f)
            positions = {v: position(v) for v in b}
            tris = triangulate_face(b, positions)
            fnormals[f] = face_normal(positions, b)
            face_boundary[f] = tuple(b)
            row = face_row.get(f)
            if row is None:
                row = face_row[f] = self._free_rows.pop()
                self._row_face[row] = f
            slots = face_triangles.get(f)
            if slots is None or len(slots) != len(tris):
                if slots is not None:
                    free_triangles(f)
                slots = [self._free_triangles.pop() for _ in tris]
                face_triangles[f] = slots
            for t, tri in zip(slots, tris):
                self._triangle_indices[t] = tri
                self._triangle_face_rows[t] = row
                tri_slots[t] = (float(index[tri[0]]), float(index[tri[1]]), float(index[tri[2]]))
            row_slots.add(row)
            dirty_vertices.update(b)

        # Vertex-Normalen um alles, was sich geändert hat (wie `full_recompute`: ein Vertex ohne
        # Faces bekommt (0, 0, 0) und keinen Adjazenz-Eintrag); die Face-Zeilen um diese Vertices.
        for v in dirty_vertices:
            slot = index.get(v)
            if slot is None:
                continue
            faces_of = v2f.get(v)
            sx = sy = sz = 0.0
            if faces_of:
                for f in faces_of:
                    n = fnormals[f]
                    sx += n[0]
                    sy += n[1]
                    sz += n[2]
                for f in faces_of:
                    row_slots.add(face_row[f])
            elif faces_of is not None:
                del v2f[v]
            normal = vnormals[v] = _normalize((sx, sy, sz))
            normal_slots[slot] = normal
        for v in added_v:
            if v not in vnormals:
                vnormals[v] = _ZERO3
                normal_slots[index[v]] = _ZERO3
        derived.invalidate_bounds(mesh)

        self._upload_vec3("positions", pos_slots)
        self._upload_vec3("normals", normal_slots)
        self._upload_vec3("indices", tri_slots)
        for run in _runs(tri_slots):
            data = [float(self._triangle_face_rows[t]) for t in run]
            self.store.update(TRIANGLE_FACES, run[0], data, len(data) * FLOAT_BYTES)
        row_face = self._row_face
        dead_row = [0.0] * FACE_ROW_FLOATS
        for run in _runs(row_slots):
            data: list[float] = []
            for row in run:
                face_id = row_face[row]
                data += dead_row if face_id is None else self._face_row_data(face_id)
            self.store.update(FACE_DATA, run[0] * FACE_ROW_FLOATS, data, len(data) * FLOAT_BYTES)
            self.stats.count("face_data_uploads", len(run))
        if self.overlay is not None:
            # Wie der volle Rebuild: die Flags passen zu den (neuen) Slots und zur Auswahl.
            flags = self._highlight_flags()
            self.store.update("highlight_flags", 0, flags, len(flags) * FLOAT_BYTES)
        self.content_revision += 1
        return True

    def _upload_vec3(self, name: str, slot_values: dict[int, tuple]) -> None:
        for run in _runs(slot_values):
            data = [c for slot in run for c in slot_values[slot]]
            self.store.update(name, run[0] * COMPONENTS_PER_VERTEX, data, len(data) * FLOAT_BYTES)
            self.stats.count("partial_updates")

    def _sync_geometry(self) -> None:
        moved = self.dirty.modified_vertices
        if not moved:
            return
        self.content_revision += 1
        self.stats.count("vertex_updates", len(moved))
        self._retriangulate.update(moved)

        affected_faces, affected_vertices = self.derived.affected_neighborhood(
            self.mesh, moved
        )
        self.derived.update_face_normals(self.mesh, affected_faces)
        self.derived.update_vertex_normals(self.mesh, affected_vertices)

        # Bounds sind Derived Data -> kein Structural-Rebuild. WP-VIEW-PERF-01: nur
        # invalidieren; das O(V)-Recalc (`bounds_recalculations`) läuft beim nächsten Lesen.
        self.derived.invalidate_bounds(self.mesh)
        self.stats.count("bounds_invalidations")
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

        # Face-Daten: jede Face, die einen Vertex mit neuer Position oder neuer Normale hat.
        faces: set[FaceId] = set()
        for vertex_id in affected_vertices:
            faces.update(self.derived.vertex_to_faces.get(vertex_id, ()))
        for face_id in faces:
            self.store.update(
                FACE_DATA, self._face_row[face_id] * FACE_ROW_FLOATS,
                self._face_row_data(face_id), FACE_ROW_FLOATS * FLOAT_BYTES,
            )
            self.stats.count("face_data_uploads")

    def _sync_selection(self) -> None:
        if self.overlay is None:
            return
        self.stats.count("selection_updates")
        flags = self._highlight_flags()
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

    def _sync_model(self) -> None:
        data = self.model_matrix if self.model_matrix is not None else list(_IDENTITY_4)
        if not self.store.has("model_uniforms"):
            self.store.allocate("model_uniforms", len(data) * FLOAT_BYTES)
        self.store.update("model_uniforms", 0, data, len(data) * FLOAT_BYTES)
        self._model_dirty = False

    # -- Draw (VIEWPORT_V02_ARCHITECTURE.md §4.2, AD-018 §5 Punkt 3) ---------

    def render(self, camera) -> None:
        """Issue Draw Call ("RenderMesh.render(camera)", VIEWPORT_V02_ARCHITECTURE.md
        §4.2). Mutiert KEINEN Dirty-State selbst - `sync()` muss bereits
        gelaufen sein (Camera-/Geometry-/Selection-/Material-Updates sind
        weiterhin ausschließlich über `mark_*_dirty()` + `sync()` gesteuert,
        siehe Architektur-Invariante "Camera changes never invalidate mesh
        render data"). Der eigentliche Draw-Call ist Store-spezifisch
        (nicht jeder Store ist drawbar, z. B. `TraceStore`/`PygletStore`) -
        Delegation über Duck-Typing an `store.draw()`, sofern vorhanden."""
        if self.camera is None:
            self.bind_camera(camera)
        draw = getattr(self.store, "draw", None)
        if draw is not None:
            draw()

    # -- Zugriff für Rendering/Tests ------------------------------------------

    @property
    def benchmark_counters(self) -> dict:
        return dict(self.stats.counters)

    def resource_ids(self) -> dict[str, int]:
        return self.store.resource_ids()

    def vertex_index_of(self, vertex_id: VertexId) -> int:
        return self._vertex_index[vertex_id]
