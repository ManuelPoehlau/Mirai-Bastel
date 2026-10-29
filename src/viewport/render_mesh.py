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

Textur (AD-026, 2026-10-29): hat die Mesh Face-Ecken-UVs und das gebundene Material eine Textur
(`material.texture`), legt `RenderMesh` eine dritte Daten-Ressource an, `triangle_uvs`: je
Dreiecks-Slot die UVs seiner drei Ecken (6 Floats, in der Reihenfolge seiner Indizes; eine Face ohne
UVs, ein freier oder versteckter Slot trägt `UNMAPPED_UV`). Pro Dreieck statt pro Vertex, weil eine
UV-Naht denselben Vertex in zwei Faces verschieden abbildet. Sie folgt den Dreiecks-Slots wie
`triangle_faces` (neu geschrieben, wo ein Topology-Patch Dreiecke schreibt) und ändert sich nicht
beim Verschieben. Ohne Textur gibt es sie nicht - kein Upload, kein Unterschied zu vorher.
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
#: AD-026: je Dreiecks-Slot die UVs seiner drei Ecken (nur mit Textur, Modul-Docstring).
TRIANGLE_UVS = "triangle_uvs"
TRIANGLE_UV_FLOATS = 6
#: u einer Ecke ohne UVs (der Shader zeigt dort die Grundfarbe); endlich in float32.
UNMAPPED_U = -1.0e30
_UNMAPPED_TRIANGLE = (UNMAPPED_U, 0.0) * 3
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
_NO_TINT = (0.0, 0.0, 0.0)


def _flatten_vec3(values) -> list[float]:
    out: list[float] = []
    for v in values:
        out.extend(v)
    return out


#: Slots closer than this are uploaded as one range from the CPU mirror (`PROVISIONAL`).
_UPLOAD_GAP = 32


def _ranges(slots, gap: int) -> list[tuple[int, int]]:
    """[lo, hi) slot ranges covering `slots`, joined across gaps of fewer than `gap` slots."""
    ranges: list[list[int]] = []
    for slot in sorted(slots):
        if ranges and slot < ranges[-1][1] + gap:
            ranges[-1][1] = slot + 1
        else:
            ranges.append([slot, slot + 1])
    return [(lo, hi) for lo, hi in ranges]


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
        declare_uvs = getattr(self.store, "declare_triangle_uvs", None)
        if declare_uvs is not None:
            declare_uvs(TRIANGLE_UVS)
        # AD-026: ob `triangle_uvs` gerade existiert (Mesh mit UVs und Material mit Textur).
        self._uv_active = False
        # Änderungs-Journal der Mesh (AD-023 V1): was sich seit dem letzten Sync geändert hat.
        self._watch = mesh.watch()
        self._mirror: dict[str, array] = {}
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
        # Hide / Isolate (`mirai.hidden`): Vertices, deren Dreiecke und Kanten nicht gezeichnet und
        # nicht gepickt werden. Die Dreiecks-Slots bleiben belegt; hochgeladen wird ein degeneriertes
        # Dreieck (wie ein freier Slot), so dass Shading, Tiefe und Face-ID-Pass dasselbe sehen.
        self._hidden: frozenset[VertexId] = frozenset()
        # Dasselbe für ganze Faces (die abgeleitete SubD-Fläche versteckt die Teilflächen versteckter Käfig-Faces,
        # deren Vertices sie mit sichtbaren teilt).
        self._hidden_faces: frozenset[FaceId] = frozenset()
        # Region colours (`mirai.regions.region_tints`, pushed by the host): FaceId -> rgb, written into the free `.w`
        # slots of texels 1-3 of the face row; (0, 0, 0) = no region, the row stays what it always was.
        self._tints: dict[FaceId, tuple[float, float, float]] = {}

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
        hidden = self._hidden
        n = len(eids)
        spare_e = int(n * SPARE_FRACTION) if spare else 0
        self._edge_slot = {eid: i for i, eid in enumerate(eids)}
        self._slot_edge = list(eids) + [None] * spare_e
        self._free_edge_slots = list(range(n + spare_e - 1, n - 1, -1))
        flat = array("I", bytes(4 * 2 * (n + spare_e)))
        i = 0
        for eid in eids:
            a, b = edge_vertices(eid)
            if a not in hidden and b not in hidden:
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
        if not 0 <= slot < len(self._slot_edge):
            return None
        edge = self._slot_edge[slot]
        if edge is not None and self._hidden and not self._edge_visible(edge):
            return None
        return edge

    def vertex_of_slot(self, slot: int) -> VertexId | None:
        if not 0 <= slot < len(self._slot_vertex):
            return None
        vertex = self._slot_vertex[slot]
        return None if vertex in self._hidden else vertex

    def _edge_visible(self, edge: EdgeId) -> bool:
        a, b = self.mesh.edge_vertices(edge)
        return a not in self._hidden and b not in self._hidden

    @property
    def hidden_vertices(self) -> frozenset[VertexId]:
        return self._hidden

    def _triangle_hidden(self, t: int, tri) -> bool:
        """A face with a hidden corner is hidden whole - also the triangles of its triangulation that do not
        contain that corner."""
        face = self._row_face[self._triangle_face_rows[t]]
        if face in self._hidden_faces:
            return True
        return bool(self._hidden) and not self._hidden.isdisjoint(self._face_boundary.get(face, tri))

    def _triangle_values(self, t: int, tri) -> tuple[float, float, float]:
        """Der hochgeladene Eintrag von Dreiecks-Slot `t`: das tote Dreieck für einen freien Slot und für
        ein Dreieck mit einer versteckten Ecke oder in einer versteckten Face."""
        if tri is None or self._triangle_hidden(t, tri):
            return _DEAD_TRIANGLE
        index = self._vertex_index
        return (float(index[tri[0]]), float(index[tri[1]]), float(index[tri[2]]))

    def set_hidden(self, vertices=(), faces=()) -> None:
        """Versteckt `vertices` (ersetzt die bisherige Menge): ihre Dreiecke und Kanten werden nicht mehr
        gezeichnet und nicht mehr gepickt; `faces` versteckt ganze Faces (ihre Dreiecke), ohne ihre
        Vertices anzufassen. Eine Face mit einer versteckten Ecke ist ganz versteckt. Leere Mengen zeigen alles. Patcht nur die betroffenen Slots (kein Rebuild);
        `content_revision` macht den GPU-Picker-Cache ungültig."""
        hidden, hidden_faces = frozenset(vertices), frozenset(faces)
        pending = self._watch.peek()
        if pending.vertices or pending.edges or pending.faces:
            # The mesh changed since the last sync: the slot layout must catch up before slots are patched.
            self.mark_topology_dirty()
            self.sync()
        changed = self._hidden ^ hidden
        changed_faces = self._hidden_faces ^ hidden_faces
        if not changed and not changed_faces:
            return
        self._hidden, self._hidden_faces = hidden, hidden_faces
        touched = {f for f, boundary in self._face_boundary.items() if not changed.isdisjoint(boundary)}
        touched |= changed_faces & self._face_boundary.keys()
        tri_slots = {
            t: self._triangle_values(t, self._triangle_indices[t])
            for f in touched for t in self._face_triangles[f]
        }
        edge_vertices, index = self.mesh.edge_vertices, self._vertex_index
        for slot, edge in enumerate(self._slot_edge):
            if edge is None or not changed:
                continue
            a, b = edge_vertices(edge)
            if a in changed or b in changed:
                visible = a not in hidden and b not in hidden
                self.edge_indices[2 * slot] = index[a] if visible else 0
                self.edge_indices[2 * slot + 1] = index[b] if visible else 0
                if self._edge_dirty is not None:
                    self._edge_dirty.add(slot)
        self._upload_vec3("indices", tri_slots)
        self.content_revision += 1

    def set_face_tints(self, tints) -> None:
        """Region colours (`{FaceId: (r, g, b)}`, replaces the previous map): only the face rows whose colour changed
        are rewritten, through the same upload as a position patch. Reads of the mesh come first, so pending mesh
        changes are synced before rows are addressed."""
        tints = dict(tints)
        if tints == self._tints:
            return
        pending = self._watch.peek()
        if pending.vertices or pending.edges or pending.faces:
            self.mark_topology_dirty()
            self.sync()
        old, self._tints = self._tints, tints
        changed = {f for f in old.keys() | tints.keys() if old.get(f) != tints.get(f)}
        rows = {self._face_row[f] for f in changed if f in self._face_row}
        if rows:
            self._upload_rows(rows)

    def is_vertex_hidden(self, vertex_id: VertexId) -> bool:
        return vertex_id in self._hidden

    def face_of_triangle(self, triangle: int) -> FaceId | None:
        """Die Face des Dreiecks-Slots `triangle` (= `gl_PrimitiveID` im Draw des Index-Buffers);
        None für einen freien Slot."""
        if not 0 <= triangle < len(self._triangle_indices) or self._triangle_indices[triangle] is None:
            return None
        if self._triangle_hidden(triangle, self._triangle_indices[triangle]):
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
        return [c for t, tri in enumerate(self._triangle_indices) for c in self._triangle_values(t, tri)]

    # -- UVs (AD-026, Modul-Docstring) -------------------------------------------------------

    def _uv_wanted(self) -> bool:
        return getattr(self.material, "texture", None) is not None and self.mesh.has_face_uvs()

    def _triangle_uv_values(self, t: int, tri, corners: dict | None = None) -> tuple:
        if tri is None or self._triangle_hidden(t, tri):
            return _UNMAPPED_TRIANGLE
        face = self._row_face[self._triangle_face_rows[t]]
        if corners is None:
            uvs = self.mesh.face_uvs(face)
            if uvs is None:
                return _UNMAPPED_TRIANGLE
            corners = dict(zip(self._face_boundary[face], uvs))
        a, b, c = corners[tri[0]], corners[tri[1]], corners[tri[2]]
        return (a[0], a[1], b[0], b[1], c[0], c[1])

    def _triangle_uvs_flat(self) -> list[float]:
        face_uvs = self.mesh.face_uvs
        values: list = [_UNMAPPED_TRIANGLE] * len(self._triangle_indices)
        for face, slots in self._face_triangles.items():
            uvs = face_uvs(face)
            if uvs is None:
                continue
            corners = dict(zip(self._face_boundary[face], uvs))
            for t in slots:
                values[t] = self._triangle_uv_values(t, self._triangle_indices[t], corners)
        return [c for v in values for c in v]

    def _upload_triangle_uvs(self, slots) -> None:
        if not self._uv_active or not slots:
            return
        cache: dict = {}
        face_uvs = self.mesh.face_uvs
        for run in _runs(slots):
            data: list[float] = []
            for t in run:
                tri = self._triangle_indices[t]
                if tri is None:
                    data.extend(_UNMAPPED_TRIANGLE)
                    continue
                face = self._row_face[self._triangle_face_rows[t]]
                if face not in cache:
                    uvs = face_uvs(face)
                    cache[face] = None if uvs is None else dict(zip(self._face_boundary[face], uvs))
                corners = cache[face]
                data.extend(_UNMAPPED_TRIANGLE if corners is None else self._triangle_uv_values(t, tri, corners))
            self.store.update(TRIANGLE_UVS, run[0] * TRIANGLE_UV_FLOATS, data, len(data) * FLOAT_BYTES)

    def _sync_uv_resource(self) -> None:
        """Legt `triangle_uvs` an oder gibt sie frei, wenn Textur oder UVs kommen oder gehen."""
        wanted = self._uv_wanted()
        if wanted == self._uv_active:
            return
        self._uv_active = wanted
        if wanted:
            data = self._triangle_uvs_flat()
            self.store.allocate(TRIANGLE_UVS, len(data) * FLOAT_BYTES)
            self.store.update(TRIANGLE_UVS, 0, data, len(data) * FLOAT_BYTES)
        elif self.store.has(TRIANGLE_UVS):
            self.store.destroy(TRIANGLE_UVS)

    def _push_texture(self) -> None:
        set_texture = getattr(self.store, "set_texture", None)
        if set_texture is not None:
            set_texture(getattr(self.material, "texture", None) if self._uv_active else None)

    def _face_row_data(self, face_id: FaceId) -> list[float]:
        return self._face_rows_data((face_id,))

    def _face_rows_data(self, face_ids) -> list[float]:
        """The face-data rows of `face_ids`, concatenated in that order (one call per batch: this
        runs for thousands of faces per W-drag move on a dense mesh)."""
        face_vertices = self.mesh.face_vertices
        position = self.mesh.vertex_position
        normals = self.derived.vertex_normals
        face_normals = self.derived.face_normals
        out: list[float] = []
        append_row = out.extend
        tints = self._tints
        for face_id in face_ids:
            boundary = face_vertices(face_id)
            n = len(boundary)
            nx, ny, nz = face_normals[face_id]
            tr, tg, tb = tints.get(face_id, _NO_TINT) if tints else _NO_TINT
            if n == 4:
                a, b, c, d = boundary
                pa, pb, pc, pd = position(a), position(b), position(c), position(d)
                na, nb, nc, nd = normals[a], normals[b], normals[c], normals[d]
                append_row((
                    nx, ny, nz, 4.0,
                    pa[0], pa[1], pa[2], tr, pb[0], pb[1], pb[2], tg,
                    pc[0], pc[1], pc[2], tb, pd[0], pd[1], pd[2], 0.0,
                    na[0], na[1], na[2], 0.0, nb[0], nb[1], nb[2], 0.0,
                    nc[0], nc[1], nc[2], 0.0, nd[0], nd[1], nd[2], 0.0,
                ))
                continue
            corners = boundary[:_FACE_ROW_CORNERS]
            padding = [0.0] * (4 * (_FACE_ROW_CORNERS - len(corners)))
            row = [nx, ny, nz, float(n)]
            for v in corners:
                x, y, z = position(v)
                row += (x, y, z, 0.0)
            row += padding
            for v in corners:
                x, y, z = normals[v]
                row += (x, y, z, 0.0)
            row += padding
            if tr or tg or tb:
                row[7], row[11], row[15] = tr, tg, tb
            append_row(row)
        return out

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
        positions, normals = self._positions_flat(), self._normals_flat()
        # CPU-Spiegel (2026-10-21): ein Patch schreibt hierhin und lädt wenige zusammengefasste
        # Bereiche hoch statt eines `store.update` je Vertex (W-Drag großer Auswahlen).
        self._mirror = {"positions": array("f", positions), "normals": array("f", normals)}
        put("positions", positions)
        put("normals", normals)
        put("indices", self._indices_flat())

        if self.overlay is not None:
            put("highlight_flags", self._highlight_flags())
        self.store.end_rebuild(MESH_GROUP)

        put(TRIANGLE_FACES, [float(row) for row in self._triangle_face_rows])
        put(FACE_DATA, self._face_data_flat())
        self._uv_active = self._uv_wanted()
        if self._uv_active:
            put(TRIANGLE_UVS, self._triangle_uvs_flat())
        elif self.store.has(TRIANGLE_UVS):
            self.store.destroy(TRIANGLE_UVS)

        if self.material is not None:
            put("material_uniforms", self.material.uniform_packet())
            self._push_texture()
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
        if change.faces or change.face_uvs:
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
        if self._uv_active != self._uv_wanted():
            return False  # the UV map came or went (a load, an Undo of it): the full rebuild decides
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
            visible = a not in self._hidden and b not in self._hidden
            edge_indices[2 * slot] = index[a] if visible else 0
            edge_indices[2 * slot + 1] = index[b] if visible else 0
            if edge_dirty is not None:
                edge_dirty.add(slot)

        # Neu triangulieren: neue / geänderte Faces und alle Faces um bewegte Vertices; dazu Faces mit
        # neuen UVs (AD-026: ihre Dreiecks-Slots bekommen sie beim Schreiben).
        retri: set[FaceId] = set(new_boundary)
        if self._uv_active:
            retri.update(f for f in change.face_uvs if f in face_row and is_valid_face(f))
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
                tri_slots[t] = self._triangle_values(t, tri)
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
        self._upload_triangle_uvs(tri_slots)
        self._upload_rows(row_slots)
        if self.overlay is not None:
            # Wie der volle Rebuild: die Flags passen zu den (neuen) Slots und zur Auswahl.
            flags = self._highlight_flags()
            self.store.update("highlight_flags", 0, flags, len(flags) * FLOAT_BYTES)
        self.content_revision += 1
        return True

    def _upload_vec3(self, name: str, slot_values: dict[int, tuple]) -> None:
        mirror = self._mirror.get(name)
        if mirror is None:
            for run in _runs(slot_values):
                data = [c for slot in run for c in slot_values[slot]]
                self.store.update(name, run[0] * COMPONENTS_PER_VERTEX, data, len(data) * FLOAT_BYTES)
                self.stats.count("partial_updates")
            return
        for slot, value in slot_values.items():
            i = slot * COMPONENTS_PER_VERTEX
            mirror[i:i + COMPONENTS_PER_VERTEX] = array("f", value)
        # Slots closer than `_UPLOAD_GAP` share one upload: the unchanged values in between come from
        # the mirror, so one call replaces many (the per-call cost dominates, not the bytes).
        for lo, hi in _ranges(slot_values, _UPLOAD_GAP):
            data = mirror[lo * COMPONENTS_PER_VERTEX:hi * COMPONENTS_PER_VERTEX].tolist()
            self.store.update(name, lo * COMPONENTS_PER_VERTEX, data, len(data) * FLOAT_BYTES)
            self.stats.count("partial_updates")

    def _upload_rows(self, rows) -> None:
        """Face-data rows, one upload per run of consecutive rows."""
        row_face = self._row_face
        dead_row = [0.0] * FACE_ROW_FLOATS
        for run in _runs(rows):
            faces = [row_face[row] for row in run]
            if None in faces:
                data: list[float] = []
                for face_id in faces:
                    data += dead_row if face_id is None else self._face_row_data(face_id)
            else:
                data = self._face_rows_data(faces)
            self.store.update(FACE_DATA, run[0] * FACE_ROW_FLOATS, data, len(data) * FLOAT_BYTES)
            self.stats.count("face_data_uploads", len(run))

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

        # Positions / Normalen: nur die verschobenen Vertices bzw. ihr 1-Ring, über den CPU-Spiegel in
        # wenigen zusammengefassten Bereichen hochgeladen.
        index = self._vertex_index
        position = self.mesh.vertex_position
        normals = self.derived.vertex_normals
        self._upload_vec3("positions", {index[v]: position(v) for v in moved})
        self._upload_vec3("normals", {index[v]: normals[v] for v in affected_vertices})
        self.stats.count("geometry_uploads", len(moved) + len(affected_vertices))

        # Face-Daten: jede Face, die einen Vertex mit neuer Position oder neuer Normale hat.
        faces: set[FaceId] = set()
        v2f = self.derived.vertex_to_faces
        for vertex_id in affected_vertices:
            faces.update(v2f.get(vertex_id, ()))
        face_row = self._face_row
        self._upload_rows({face_row[face_id] for face_id in faces})

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
        self._sync_uv_resource()
        self._push_texture()

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
