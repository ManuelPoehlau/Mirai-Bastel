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
    selection -> (nichts)                     (Auswahl zeichnen die Overlays; seit 2026-11-11 ohne highlight_flags)
    material  -> material_uniforms            (nur Material-Parameter, optional)
    geometry  -> positions, normals           (partial) + Bounds (Derived Data)
    topology  -> positions, normals, indices  (structural)

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
welche der Kern-Ressourcen (`positions`/`normals` + `indices`; bis 2026-11-11 auch
`highlight_flags`) zusammen EIN drawbares GPU-Objekt bilden, und dass
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

Face-Daten (AD-018 Nachtrag 2026-10-15, B5a.1 + Smooth ohne Dreiecks-Diagonale; Layout seit O2, Nachtrag
2026-11-11): neben der Gruppe legt `RenderMesh` drei Daten-Ressourcen an, die der Fragment-Shader über die
Dreiecksnummer (`gl_PrimitiveID`) liest - `triangle_faces` (je Dreieck in Indexbuffer-Reihenfolge die Zeile seiner
Face), `face_normals` (je Face-Zeile ein vec4: Newell-Normale + Eckenzahl) und `face_corners` (je Face-Zeile zwei
vec4: die Vertex-Slots der ersten vier Ecken, die Regionsfarbe). Die Positionen und Normalen der Ecken liest der
Shader aus den Buffern der Vertex-Gruppe selbst (`GLRenderStore`: als Buffer-Texturen), nicht aus Kopien je Face.
Damit schattiert Flat eine Normale pro Polygon statt pro Dreieck, und Smooth interpoliert die Normalen über ein Quad
bilinear statt pro Dreieck linear. Die Vertex-Gruppe bleibt unverändert. `triangle_faces` und `face_corners` ändern
sich nur strukturell (und `face_corners` mit der Regionsfarbe); eine Verformung schreibt nur die `face_normals` der
Faces um bewegte Vertices (4 Floats je Face; bis O2 waren es 36 Floats je Face um jeden Vertex mit neuer Normale:
Normale, vier Eck-Positionen, vier Eck-Normalen - Audit 2026-11-10 §E.3).

Arrays (AD-032, O3 Stufe 1, 2026-11-12): die abgeleiteten Daten - Positionen je Slot, Face- und Vertex-Normalen, die
Nachbarschaft (Ecken je Face-Zeile, Faces je Vertex-Slot) - liegen in `packed` (`packed_geometry.PackedGeometry`,
NumPy-Arrays auf genau diesem Slot-Layout), nicht mehr in Dicts nach ID. Ein Geometry-Sync liest nur die Positionen der
bewegten Vertices (`_read_moved`), rechnet den 1-Ring auf den Arrays (bit-gleich zur Python-Referenz
`derived.DerivedGeometry`) und gibt float32-Bereiche der CPU-Spiegel an den Store; ein Topology-Patch schreibt die
Journal-Änderungen in die Arrays wie in das Slot-Layout. `derived` ist seitdem eine Lese-Sicht nach ID auf die Arrays.

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
from collections.abc import Mapping
from itertools import chain

from core import EdgeId, FaceId, Mesh, VertexId

from .benchmark import BenchmarkCounters
from .category import DirtyState
from .derived import triangulate_face
from .hidden_rule import NOTHING, Resolved, resolve
from .packed_geometry import PackedGeometry, np
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
}
MESH_GROUP_INDEX = "indices"

#: Face data (module docstring): one vec4 per face row (Newell normal, corner count) - the only face data a deformation
#: rewrites - and two vec4 per face row (vertex slots of the first four corners; region tint rgb, 0) - topology and tint.
FACE_NORMALS = "face_normals"
FACE_NORMAL_FLOATS = 4
FACE_CORNERS = "face_corners"
FACE_CORNER_TEXELS = 2
FACE_CORNER_FLOATS = FACE_CORNER_TEXELS * 4
TRIANGLE_FACES = "triangle_faces"
#: AD-026: je Dreiecks-Slot die UVs seiner drei Ecken (nur mit Textur, Modul-Docstring).
TRIANGLE_UVS = "triangle_uvs"
TRIANGLE_UV_FLOATS = 6
#: u einer Ecke ohne UVs (der Shader zeigt dort die Grundfarbe); endlich in float32.
UNMAPPED_U = -1.0e30
_UNMAPPED_TRIANGLE = (UNMAPPED_U, 0.0) * 3
#: Ecken, deren Slots eine Face-Zeile trägt: der Shader interpoliert bilinear nur über Quads (Dreiecke sind schon
#: linear exakt, n-Gone behalten die interpolierte Vertex-Normale).
_FACE_ROW_CORNERS = 4
_DEAD_NORMAL_ROW = (0.0,) * FACE_NORMAL_FLOATS
_DEAD_CORNER_ROW = (0.0,) * FACE_CORNER_FLOATS

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


def _ranges(slots: np.ndarray, gap: int) -> list[tuple[int, int]]:
    """[lo, hi) slot ranges covering the ascending, distinct `slots`, joined across gaps of fewer than `gap` slots."""
    if not len(slots):
        return []
    breaks = np.flatnonzero(np.diff(slots) > gap)
    lows = slots[np.concatenate(((0,), breaks + 1))].tolist()
    highs = (slots[np.concatenate((breaks, (len(slots) - 1,)))] + 1).tolist()
    return list(zip(lows, highs))


def _slot_array(slots) -> np.ndarray:
    """Ascending, distinct slots from a set, a list or an array of ints."""
    if isinstance(slots, np.ndarray):
        return np.unique(slots)
    return np.unique(np.fromiter(slots, dtype=np.intp, count=len(slots)))


def _runs(slots) -> list[list[int]]:
    """Aufsteigende Slots in Läufe aufeinanderfolgender Werte (ein Upload je Lauf)."""
    runs: list[list[int]] = []
    for slot in sorted(slots):
        if runs and slot == runs[-1][-1] + 1:
            runs[-1].append(slot)
        else:
            runs.append([slot])
    return runs


class _ById(Mapping):
    """`{id: value}` over one of `RenderMesh`'s id -> slot / row maps, read from the arrays on access (read-only)."""

    __slots__ = ("_index", "_read", "_has")

    def __init__(self, index: dict, read, has=None) -> None:
        self._index, self._read, self._has = index, read, has

    def __getitem__(self, key):
        slot = self._index[key]
        if self._has is not None and not self._has(slot):
            raise KeyError(key)
        return self._read(slot)

    def __iter__(self):
        has = self._has
        return iter(self._index) if has is None else (k for k, slot in self._index.items() if has(slot))

    def __len__(self) -> int:
        return len(self._index) if self._has is None else sum(1 for _ in self)


class DerivedView:
    """What `RenderMesh.derived` was until O3 stage 1 (a `derived.DerivedGeometry`), as read-only mappings over the
    arrays (AD-032): `vertex_normals` / `face_normals` ({id: (x, y, z)}), `vertex_to_faces` ({VertexId: set of FaceId},
    only vertices with faces, as the reference) and the lazy bounds. For tests, probes and the transform tools' normal
    queries; `RenderMesh` itself computes on the arrays."""

    def __init__(self, render_mesh: "RenderMesh") -> None:
        self._rm = render_mesh
        packed, row_face = render_mesh.packed, render_mesh._row_face
        self.vertex_normals = _ById(render_mesh._vertex_index, lambda slot: tuple(packed.VN[slot].tolist()))
        self.face_normals = _ById(render_mesh._face_row, lambda row: tuple(packed.FN[row].tolist()))
        self.vertex_to_faces = _ById(
            render_mesh._vertex_index, lambda slot: {row_face[r] for r in packed.faces_of(slot)},
            lambda slot: packed.vertex_faces.count[slot] > 0,
        )

    def affected_neighborhood(self, mesh: Mesh, moved_vertices) -> tuple[set[FaceId], set[VertexId]]:
        """(face ids, vertex ids) a move of `moved_vertices` re-normals - `PackedGeometry.neighbourhood` by id
        (`mesh` is accepted for the reference's signature; the view reads its own render mesh)."""
        rm = self._rm
        index = rm._vertex_index
        slots = np.fromiter((index[v] for v in moved_vertices), dtype=np.intp, count=len(moved_vertices))
        rows, ring = rm.packed.neighbourhood(slots)
        return {rm._row_face[r] for r in rows.tolist()}, {rm._slot_vertex[v] for v in ring.tolist()}

    def _bounds(self):
        stats = self._rm.stats
        return self._rm.packed.bounds(lambda: stats.count("bounds_recalculations"))

    @property
    def bounds_min(self):
        return self._bounds()[0]

    @property
    def bounds_max(self):
        return self._bounds()[1]


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
        self.store.declare_face_data(FACE_NORMALS, FACE_CORNERS, TRIANGLE_FACES)
        declare_uvs = getattr(self.store, "declare_triangle_uvs", None)
        if declare_uvs is not None:
            declare_uvs(TRIANGLE_UVS)
        # AD-026: ob `triangle_uvs` gerade existiert (Mesh mit UVs und Material mit Textur).
        self._uv_active = False
        # Änderungs-Journal der Mesh (AD-023 V1): was sich seit dem letzten Sync geändert hat.
        self._watch = mesh.watch()
        # CPU mirrors (float32, one row per slot / face row): what the store last received, patched in place.
        self._mirror: dict[str, np.ndarray] = {}
        #: Positions, face / vertex normals and their adjacency on this layout's slots and rows (AD-032, O3 stage 1).
        self.packed = PackedGeometry()
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
        # (`gpu_picker.py`) und der Wire (`gl_line_overlay.GLLineOverlay.draw_mesh_wire`, 2026-11-11) laden sie
        # je als eigenen Index-Buffer über die `positions` dieser Mesh; `take_edge_changes(consumer)` sagt jedem,
        # welche Slots sich seit seinem letzten Aufruf geändert haben.
        self._edge_slot: dict[EdgeId, int] = {}
        self._slot_edge: list[EdgeId | None] = []
        self._free_edge_slots: list[int] = []
        self.edge_indices = array("I")
        # consumer -> geänderte Slots seit seinem letzten `take_edge_changes`; fehlt er, gilt "alle".
        self._edge_dirty: dict[object, set[int]] = {}
        #: +1 je vollem Rebuild (alle Slots neu vergeben) und je Änderung irgendeines Buffer-Inhalts
        #: (Topology-Patch, Geometry-Sync): Cache-Schlüssel für Konsumenten wie den GPU-Picker.
        self.layout_revision = 0
        self.content_revision = 0
        # Hide / Isolate (`mirai.hidden`): Vertices, deren Dreiecke und Kanten nicht gezeichnet und
        # nicht gepickt werden. Die Dreiecks-Slots bleiben belegt; hochgeladen wird ein degeneriertes
        # Dreieck (wie ein freier Slot), so dass Shading, Tiefe und Face-ID-Pass dasselbe sehen.
        self._hidden: frozenset[VertexId] = frozenset()
        # Dasselbe für ganze Faces (Face-Modus, polygon-exakt; die abgeleitete SubD-Fläche versteckt die Teilflächen
        # versteckter Käfig-Faces, deren Vertices sie mit sichtbaren teilt).
        self._hidden_faces: frozenset[FaceId] = frozenset()
        # Was daraus folgt (`hidden_rule.resolve`): auch eine Kante / ein Vertex, deren Faces alle versteckt sind.
        # Nach jedem Topologie-Sync neu aufgelöst; nur die Differenz wird hochgeladen.
        self._resolved: Resolved = NOTHING
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

    @property
    def derived(self) -> "DerivedView":
        """Read-only view of the derived data by ID (`vertex_normals`, `face_normals`, `vertex_to_faces`, bounds), the
        mapping API of `derived.DerivedGeometry` over the arrays of `packed`."""
        return DerivedView(self)

    def _full_rebuild(self) -> None:
        if self._hidden or self._hidden_faces:
            self._resolved = resolve(self.mesh, self._hidden, self._hidden_faces)
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
        hidden_edges = self._resolved.edges
        for eid in eids:
            a, b = edge_vertices(eid)
            if a not in hidden and b not in hidden and eid not in hidden_edges:
                flat[i] = index[a]
                flat[i + 1] = index[b]
            i += 2
        self.edge_indices = flat
        self._edge_dirty = {}

    def take_edge_changes(self, consumer: object = None) -> set[int] | None:
        """Edge-Slots, deren Indizes sich seit dem letzten Aufruf von `consumer` geändert haben; None = alle (neues
        Layout, oder `consumer` fragt zum ersten Mal). Je Konsument (GPU-Picker, Wire) ein eigener Stand."""
        dirty = self._edge_dirty.get(consumer)
        self._edge_dirty[consumer] = set()
        return dirty

    def _edge_slot_changed(self, slot: int) -> None:
        for dirty in self._edge_dirty.values():
            dirty.add(slot)

    def edge_of_slot(self, slot: int) -> EdgeId | None:
        if not 0 <= slot < len(self._slot_edge):
            return None
        edge = self._slot_edge[slot]
        if edge is not None and (self._hidden or self._resolved) and not self._edge_visible(edge):
            return None
        return edge

    def vertex_of_slot(self, slot: int) -> VertexId | None:
        if not 0 <= slot < len(self._slot_vertex):
            return None
        vertex = self._slot_vertex[slot]
        return None if self.is_vertex_hidden(vertex) else vertex

    def _edge_visible(self, edge: EdgeId) -> bool:
        if edge in self._resolved.edges:
            return False
        a, b = self.mesh.edge_vertices(edge)
        return a not in self._hidden and b not in self._hidden

    @property
    def hidden_vertices(self) -> frozenset[VertexId]:
        """The explicitly hidden vertices (`set_hidden`)."""
        return self._hidden

    @property
    def hidden_faces(self) -> frozenset[FaceId]:
        """The explicitly hidden faces (`set_hidden`)."""
        return self._hidden_faces

    @property
    def resolved_hidden(self) -> Resolved:
        """Every hidden vertex, edge and face (`hidden_rule`), as last synced."""
        return self._resolved

    def _triangle_hidden(self, t: int, tri) -> bool:
        """A face with a hidden corner is hidden whole - also the triangles of its triangulation that do not
        contain that corner."""
        face = self._row_face[self._triangle_face_rows[t]]
        if face in self._hidden_faces or face in self._resolved.faces:
            return True
        return bool(self._hidden) and not self._hidden.isdisjoint(self._face_boundary.get(face, tri))

    def _triangle_values(self, t: int, tri) -> tuple[float, float, float]:
        """Der hochgeladene Eintrag von Dreiecks-Slot `t`: das tote Dreieck für einen freien Slot und für
        ein Dreieck mit einer versteckten Ecke oder in einer versteckten Face."""
        if tri is None or self._triangle_hidden(t, tri):
            return _DEAD_TRIANGLE
        index = self._vertex_index
        return (float(index[tri[0]]), float(index[tri[1]]), float(index[tri[2]]))

    def set_hidden(self, vertices=(), faces=(), resolved: Resolved | None = None) -> None:
        """Versteckt `vertices` und `faces` (ersetzt die bisherigen Mengen; Regel: `hidden_rule`): eine Face mit einer
        versteckten Ecke oder in `faces` ist ganz versteckt, eine Kante / ein Vertex, wenn ein Endpunkt in `vertices`
        liegt oder alle ihre Faces versteckt sind. Leere Mengen zeigen alles. Patcht nur die betroffenen Slots (kein
        Rebuild); `content_revision` macht den GPU-Picker-Cache ungültig. `resolved`: dieselben Mengen, vom Aufrufer
        für genau diese Mesh schon aufgelöst (`hidden_rule.resolve`) - spart die zweite Auflösung."""
        hidden, hidden_faces = frozenset(vertices), frozenset(faces)
        pending = self._watch.peek()
        if pending.vertices or pending.edges or pending.faces:
            # The mesh changed since the last sync: the slot layout must catch up before slots are patched.
            self.mark_topology_dirty()
            self.sync()
        if hidden == self._hidden and hidden_faces == self._hidden_faces:
            return
        self._hidden, self._hidden_faces = hidden, hidden_faces
        self._apply_hidden(resolved)

    def _apply_hidden(self, resolved: Resolved | None = None) -> None:
        """Resolves the hidden sets again (or takes `resolved`) and uploads the triangles and edge slots whose
        visibility changed."""
        old = self._resolved
        if not self._hidden and not self._hidden_faces:
            resolved = NOTHING
        elif resolved is None:
            resolved = resolve(self.mesh, self._hidden, self._hidden_faces)
        new = self._resolved = resolved
        changed_faces = (old.faces ^ new.faces) & self._face_boundary.keys()
        changed_edges = old.edges ^ new.edges
        if not changed_faces and not changed_edges:
            return
        tri_slots = {
            t: self._triangle_values(t, self._triangle_indices[t])
            for f in changed_faces for t in self._face_triangles[f]
        }
        edge_vertices, index, edge_slot = self.mesh.edge_vertices, self._vertex_index, self._edge_slot
        for edge in changed_edges:
            slot = edge_slot.get(edge)
            if slot is None:
                continue
            a, b = edge_vertices(edge)
            visible = edge not in new.edges
            self.edge_indices[2 * slot] = index[a] if visible else 0
            self.edge_indices[2 * slot + 1] = index[b] if visible else 0
            self._edge_slot_changed(slot)
        self._upload_vec3("indices", tri_slots)
        self._upload_triangle_uvs(tri_slots)
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
            self._upload_face_corners(rows)

    def is_vertex_hidden(self, vertex_id: VertexId) -> bool:
        return vertex_id in self._hidden or vertex_id in self._resolved.vertices

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

        # The arrays (AD-032) on exactly this layout: live slots first in mesh order, spare slots dead.
        pos = np.empty((n_v + spare_v, 3))
        pos[n_v:] = DEAD_POSITION
        if n_v:
            pos[:n_v] = np.fromiter(chain.from_iterable(map(positions.__getitem__, vids)), dtype=np.float64,
                                    count=3 * n_v).reshape(n_v, 3)
        live = np.zeros(n_v + spare_v, dtype=bool)
        live[:n_v] = True
        sizes = np.zeros(n_f + spare_f, dtype=np.intp)
        sizes[:n_f] = np.fromiter(map(len, face_boundary.values()), dtype=np.intp, count=n_f)
        index = self._vertex_index
        corners = np.fromiter(map(index.__getitem__, chain.from_iterable(face_boundary.values())), dtype=np.intp,
                              count=int(sizes.sum()))
        face_ids = np.full(n_f + spare_f, -1, dtype=np.int64)
        face_ids[:n_f] = np.fromiter(fids, dtype=np.int64, count=n_f)
        self.packed.build(pos, live, sizes, corners, face_ids)

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

    def _face_corner_values(self, face_ids) -> list[float]:
        """The `face_corners` rows of `face_ids` (vertex slots of the first four corners, unused ones 0; region tint),
        concatenated in that order."""
        index = self._vertex_index
        boundary = self._face_boundary
        tints = self._tints
        out: list[float] = []
        extend = out.extend
        for face_id in face_ids:
            b = boundary[face_id]
            tr, tg, tb = tints.get(face_id, _NO_TINT) if tints else _NO_TINT
            if len(b) >= _FACE_ROW_CORNERS:
                extend((float(index[b[0]]), float(index[b[1]]), float(index[b[2]]), float(index[b[3]]),
                        tr, tg, tb, 0.0))
            else:
                extend((float(index[b[0]]), float(index[b[1]]), float(index[b[2]]), 0.0, tr, tg, tb, 0.0))
        return out

    def _face_rows_flat(self, values, dead) -> list[float]:
        """One face resource over all rows: `values(faces)` for live rows, `dead` for free ones."""
        flat: list[float] = []
        batch: list[FaceId] = []
        for face_id in self._row_face:
            if face_id is None:
                flat += values(batch)
                batch = []
                flat += dead
            else:
                batch.append(face_id)
        flat += values(batch)
        return flat

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
        packed = self.packed
        # CPU-Spiegel (2026-10-21; seit O3 float32-Arrays je Slot): ein Patch schreibt hierhin und lädt wenige
        # zusammengefasste Bereiche hoch statt eines `store.update` je Vertex (W-Drag großer Auswahlen).
        positions, normals = packed.P.astype(np.float32), packed.VN.astype(np.float32)
        self._mirror = {"positions": positions, "normals": normals}
        put("positions", positions.reshape(-1))
        put("normals", normals.reshape(-1))
        put("indices", self._indices_flat())
        self.store.end_rebuild(MESH_GROUP)

        put(TRIANGLE_FACES, [float(row) for row in self._triangle_face_rows])
        # Face rows: Newell normal + corner count; a free row has size 0 and normal (0, 0, 0) = `_DEAD_NORMAL_ROW`.
        face_normals = np.zeros((len(self._row_face), FACE_NORMAL_FLOATS), dtype=np.float32)
        face_normals[:, :3] = packed.FN
        face_normals[:, 3] = packed.corners.count
        self._mirror[FACE_NORMALS] = face_normals
        put(FACE_NORMALS, face_normals.reshape(-1))
        put(FACE_CORNERS, self._face_rows_flat(self._face_corner_values, _DEAD_CORNER_ROW))
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
        vertices = change.vertices
        if vertices.keys() <= index.keys():
            # The usual frame (only moves, every vertex known): structural only if one of them went away. Same answer
            # as the general test below, without a Python-level step per moved vertex (O3 stage 1).
            return not all(map(mesh.is_valid_vertex, vertices))
        return any((v in index) != mesh.is_valid_vertex(v) for v in vertices)

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

        packed = self.packed
        row_face = self._row_face
        position = mesh.vertex_position
        pos_slots: set[int] = set()
        normal_slots: set[int] = set()
        tri_slots: dict[int, tuple] = {}
        # Face rows whose Newell normal (`normal_rows`) or corner slots (`corner_rows`) changed; the corners' positions
        # and normals are read from the vertex buffers (O2), so a face around a moved vertex needs no other row.
        normal_rows: set[int] = set()
        corner_rows: set[int] = set()

        # Adjacency (vertex -> faces): edited here as FaceId sets, read from the arrays before anything moves, written
        # back as rows in ascending FaceId order once every face has its row (AD-032: the fixed summation order).
        faces_around: dict[VertexId, set[FaceId]] = {}

        def adjacency(v: VertexId) -> set[FaceId]:
            got = faces_around.get(v)
            if got is None:
                slot = index.get(v)
                got = faces_around[v] = set() if slot is None else {row_face[r] for r in packed.faces_of(slot)}
            return got

        dirty_vertices: set[VertexId] = set()
        for f in (*removed_f, *changed_f):
            old = face_boundary[f]
            for v in old:
                adjacency(v).discard(f)
            dirty_vertices.update(old)
        for f, b in new_boundary.items():
            for v in b:
                adjacency(v).add(f)

        # Re-triangulated: new / changed faces and every face around a vertex moved since its faces' last
        # triangulation (`_retriangulate`, this patch's moves); dazu Faces mit neuen UVs (AD-026: ihre Dreiecks-Slots
        # bekommen sie beim Schreiben). The faces around those vertices now are their faces before this patch minus the
        # removed ones, plus new / changed faces (already in the set) - read from the arrays before rows are reused.
        retri: set[FaceId] = set(new_boundary)
        if self._uv_active:
            retri.update(f for f in change.face_uvs if f in face_row and is_valid_face(f))
        removed_v_set = set(removed_v)
        around = [index[v] for v in (*moved_v, *self._retriangulate) if v in index and v not in removed_v_set]
        if around:
            rows = packed.rows_around(np.fromiter(around, dtype=np.intp, count=len(around)))
            retri.update(map(row_face.__getitem__, rows.tolist()))
            retri.difference_update(removed_f)
        self._retriangulate = set()

        def free_triangles(f: FaceId) -> None:
            for t in face_triangles.pop(f):
                self._triangle_indices[t] = None
                self._triangle_face_rows[t] = 0
                self._free_triangles.append(t)
                tri_slots[t] = _DEAD_TRIANGLE

        for f in removed_f:
            free_triangles(f)
            row = face_row.pop(f)
            row_face[row] = None
            self._free_rows.append(row)
            normal_rows.add(row)
            corner_rows.add(row)
            del face_boundary[f]
            packed.clear_face(row)
        for f in changed_f:
            free_triangles(f)
        for v in removed_v:
            slot = index.pop(v)
            self._slot_vertex[slot] = None
            self._free_vertex_slots.append(slot)
            packed.clear_vertex(slot, DEAD_POSITION)
            pos_slots.add(slot)
            normal_slots.add(slot)
        for v in added_v:
            slot = self._free_vertex_slots.pop()
            index[v] = slot
            self._slot_vertex[slot] = v
            packed.add_vertex(slot, position(v))
            pos_slots.add(slot)
            normal_slots.add(slot)  # (0, 0, 0) until a face holds it
        P = packed.P
        for v in moved_v:
            slot = index[v]
            P[slot] = position(v)
            pos_slots.add(slot)

        edge_indices = self.edge_indices
        edge_dirty = tuple(self._edge_dirty.values())
        for e in removed_e:
            slot = edge_slot.pop(e)
            self._slot_edge[slot] = None
            self._free_edge_slots.append(slot)
            edge_indices[2 * slot] = edge_indices[2 * slot + 1] = 0
            for dirty in edge_dirty:
                dirty.add(slot)
        edge_vertices = mesh.edge_vertices
        for e in (*added_e, *changed_e):
            slot = edge_slot.get(e)
            if slot is None:
                slot = edge_slot[e] = self._free_edge_slots.pop()
                self._slot_edge[slot] = e
            a, b = edge_vertices(e)
            visible = self._edge_visible(e)
            edge_indices[2 * slot] = index[a] if visible else 0
            edge_indices[2 * slot + 1] = index[b] if visible else 0
            for dirty in edge_dirty:
                dirty.add(slot)

        live_rows: list[int] = []
        for f in retri:
            b = new_boundary.get(f) or face_vertices(f)
            positions = {v: position(v) for v in b}
            tris = triangulate_face(b, positions)
            face_boundary[f] = tuple(b)
            row = face_row.get(f)
            if row is None:
                row = face_row[f] = self._free_rows.pop()
                row_face[row] = f
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
            normal_rows.add(row)
            live_rows.append(row)
            if f in new_boundary:
                corner_rows.add(row)
                packed.set_face(row, [index[v] for v in b])
            dirty_vertices.update(b)
        for v, faces in faces_around.items():
            slot = index.get(v)
            if slot is not None:
                packed.set_faces_of(slot, [face_row[f] for f in sorted(faces)])

        # Normals: the faces re-triangulated here, then the vertices around everything that changed (like the full
        # build: a vertex without faces gets (0, 0, 0)).
        if live_rows:
            packed.update_face_normals(np.unique(np.asarray(live_rows, dtype=np.intp)))
        dirty_slots = [index[v] for v in dirty_vertices if v in index]
        if dirty_slots:
            packed.update_vertex_normals(np.unique(np.asarray(dirty_slots, dtype=np.intp)))
            normal_slots.update(dirty_slots)
        packed.invalidate_bounds()

        self._upload_slots("positions", pos_slots)
        self._upload_slots("normals", normal_slots)
        self._upload_vec3("indices", tri_slots)
        for run in _runs(tri_slots):
            data = [float(self._triangle_face_rows[t]) for t in run]
            self.store.update(TRIANGLE_FACES, run[0], data, len(data) * FLOAT_BYTES)
        self._upload_triangle_uvs(tri_slots)
        self._upload_face_normals(normal_rows)
        self._upload_face_corners(corner_rows)
        self.content_revision += 1
        if self._hidden or self._hidden_faces:
            # A face added or removed beside hidden ones can change whether an edge or corner is hidden.
            self._apply_hidden()
        return True

    def _upload_vec3(self, name: str, slot_values: dict[int, tuple]) -> None:
        """`slot_values` ({slot: 3 values}) of a resource without a CPU mirror (the triangle indices), one upload per
        run of consecutive slots."""
        for run in _runs(slot_values):
            data = [c for slot in run for c in slot_values[slot]]
            self.store.update(name, run[0] * COMPONENTS_PER_VERTEX, data, len(data) * FLOAT_BYTES)
            self.stats.count("partial_updates")

    def _upload_slots(self, name: str, slots) -> None:
        """Positions or vertex normals of `slots` (from `packed`) into the float32 mirror, then to the store in merged
        ranges: slots closer than `_UPLOAD_GAP` share one upload; the unchanged values in between come from the mirror,
        so one call replaces many (the per-call cost dominates, not the bytes)."""
        if not len(slots):
            return
        slots = _slot_array(slots)
        mirror = self._mirror[name]
        mirror[slots] = (self.packed.P if name == "positions" else self.packed.VN)[slots]
        for lo, hi in _ranges(slots, _UPLOAD_GAP):
            data = mirror[lo:hi].reshape(-1)
            self.store.update(name, lo * COMPONENTS_PER_VERTEX, data, len(data) * FLOAT_BYTES)
            self.stats.count("partial_updates")

    def _upload_face_normals(self, rows) -> None:
        """`face_normals` rows (Newell normal, corner count; freed rows zeros) through the CPU mirror, uploaded in
        merged ranges like `_upload_slots`: a deformation rewrites these rows only, and they lie scattered over the
        buffer."""
        if not len(rows):
            return
        rows = _slot_array(rows)
        mirror = self._mirror[FACE_NORMALS]
        mirror[rows, :3] = self.packed.FN[rows]
        mirror[rows, 3] = self.packed.corners.count[rows]
        for lo, hi in _ranges(rows, _UPLOAD_GAP):
            data = mirror[lo:hi].reshape(-1)
            self.store.update(FACE_NORMALS, lo * FACE_NORMAL_FLOATS, data, len(data) * FLOAT_BYTES)
        self.stats.count("face_data_uploads", len(rows))

    def _upload_face_corners(self, rows) -> None:
        """`face_corners` rows (freed rows as zeros), one upload per run of consecutive rows (topology and tint
        changes only)."""
        row_face = self._row_face
        for run in _runs(rows):
            data: list[float] = []
            for row in run:
                face_id = row_face[row]
                data += _DEAD_CORNER_ROW if face_id is None else self._face_corner_values((face_id,))
            self.store.update(FACE_CORNERS, run[0] * FACE_CORNER_FLOATS, data, len(data) * FLOAT_BYTES)
            self.stats.count("face_data_uploads", len(run))

    def _read_moved(self, moved) -> np.ndarray:
        """The slots of the `moved` vertices; their current positions (one `vertex_position` read each, from the mesh or
        a stage's position table) written into `packed.P`. Only the moved vertices are read - nothing per frame is
        read for the whole mesh."""
        n = len(moved)
        slots = np.fromiter(map(self._vertex_index.__getitem__, moved), dtype=np.intp, count=n)
        self.packed.P[slots] = np.fromiter(chain.from_iterable(map(self.mesh.vertex_position, moved)),
                                           dtype=np.float64, count=3 * n).reshape(n, 3)
        return slots

    def _sync_geometry(self) -> None:
        moved = self.dirty.modified_vertices
        if not moved:
            return
        self.content_revision += 1
        self.stats.count("vertex_updates", len(moved))
        self._retriangulate.update(moved)

        # O3 stage 1 (AD-032): the moved positions into the arrays, then the 1-ring on arrays - the faces around the
        # moved vertices get new Newell normals, every vertex of those faces a new vertex normal.
        packed = self.packed
        slots = self._read_moved(moved)
        rows, ring = packed.neighbourhood(slots)
        packed.update_face_normals(rows)
        packed.update_vertex_normals(ring)

        # Bounds sind Derived Data -> kein Structural-Rebuild. WP-VIEW-PERF-01: nur
        # invalidieren; das O(V)-Recalc (`bounds_recalculations`) läuft beim nächsten Lesen.
        packed.invalidate_bounds()
        self.stats.count("bounds_invalidations")
        self.stats.count("normal_recomputations")

        # Positions / Normalen: nur die verschobenen Vertices bzw. ihr 1-Ring, über den CPU-Spiegel in
        # wenigen zusammengefassten Bereichen hochgeladen.
        self._upload_slots("positions", slots)
        self._upload_slots("normals", ring)
        self.stats.count("geometry_uploads", len(moved) + len(ring))

        # Face-Daten (O2): nur die Newell-Normalen der Faces um bewegte Vertices; Positionen und Normalen ihrer Ecken
        # liest der Shader aus den eben hochgeladenen Vertex-Buffern, die Eck-Slots ändern sich nicht.
        self._upload_face_normals(rows)

    def _sync_selection(self) -> None:
        # Nichts im Mesh-Buffer hängt an der Auswahl: Punkte, Kanten und Faces der Auswahl zeichnen die Overlays
        # (AD-018 E18). Bis 2026-11-11 wurde hier ein V-großer `highlight_flags`-Buffer gebaut und hochgeladen, den
        # der Shader seit E18 nicht mehr las (Audit 2026-11-10 §I.3).
        if self.overlay is not None:
            self.stats.count("selection_updates")

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
