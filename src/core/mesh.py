"""Mesh: Topologie-Domain-Modell.

Bezug: V1_SPEC.md §7 ("Topologie-Grenze"), §8 (Stable IDs), §9 (Position),
Architecture Decisions AD-001 und AD-002.

Architekturvertrag:

1. Face-Boundaries sind geordnete Listen von VertexIds (kein Half-Edge-
   Objekt in V1 - siehe AD-002). Das lässt eine spätere interne Umstellung
   auf Half-Edge-Navigation zu, ohne die Query-API zu brechen.
2. Zugriff auf Topologie erfolgt ausschließlich über die Query-Funktionen
   (face_vertices, face_edges, edge_faces, vertex_edges). Kein Aufrufer
   außerhalb dieser Klasse darf auf interne Container zugreifen.
3. Positionszugriff läuft über vertex_position()/set_vertex_position(),
   nie über ein rohes Attribut - das hält Raum für eine spätere
   Deformation-Kette offen (Base Mesh -> Morph -> Skin -> Subdivision),
   ohne dass V1 diese Kette bereits implementiert (§9).
4. Jede Mutationsfunktion dokumentiert ihren ID-Kontinuitäts-Vertrag:
   welche IDs erhalten bleiben, welche ungültig werden, welche neu
   entstehen. Das ist die Grundlage für spätere Skin-Weight-/Morph-
   Remapping-Systeme (§8) - ein solches System selbst ist NICHT Teil
   von V1.

Bewusst NICHT enthalten: volle Winged-/Half-Edge-Struktur, Non-Manifold-
Multi-Shell-Support, Genus-Tracking. Die Implementierung geht von einem
einfachen (meist manifold) Mesh aus, wie es für einen V1-Modeler
ausreicht.

Symmetry Definition (AD-SYM-01, WP-SYM-01 Slice 1): Mesh trägt zusätzlich
eine optionale `SymmetryDefinition` (Plane + deklarierte Seam-Edges) als
öffentliches Attribut `symmetry_definition`, nimmt an `export_state()`/
`load_state()` teil und damit ohne weitere Maschinerie auch an
`MeshStateCommand`-Undo/Redo. Mesh speichert diese Deklaration nur - jede
Symmetrie-*Logik* (Correspondence, State) lebt in `mirai.symmetry`.
"""

from __future__ import annotations

import enum
import math
import weakref
from collections.abc import Sequence
from dataclasses import dataclass, field

from .corner_uvs import (
    UV, FaceUVs, lerp_uv, mean_uv, polygon_weights, same_uv, uv_tuple, weighted_uv,
)
from .ids import VertexId, EdgeId, FaceId, IdAllocator, LayerId
from .layer_storage import LayerSlots, PackedValues

Position = tuple[float, float, float]
#: Value of a vector point layer (AD-025 §4.2): three finite floats, default (0, 0, 0).
LayerValue = tuple[float, float, float]
#: Origin of a new vertex (AD-025 §4.1): live source vertices with weights summing to 1; () = no source.
VertexOrigin = tuple[tuple[VertexId, float], ...]

#: Element records of the change journal (AD-023 H1). None = the element does not exist.
VertexRecord = Position
EdgeRecord = tuple  # (v0, v1, tuple of FaceIds) - endpoint order and face order as stored
FaceRecord = tuple  # boundary, as stored

_UNSET = object()


@dataclass
class _VertexData:
    position: Position


@dataclass
class _EdgeData:
    # Endpunkte, als sortiertes Paar gespeichert (Reihenfolge nicht
    # semantisch relevant - Richtung lebt in der Face-Boundary, nicht
    # in der Edge selbst).
    v0: VertexId
    v1: VertexId
    # Angrenzende Faces: 0 (frei), 1 (Rand) oder 2 (intern, manifold).
    faces: list[FaceId] = field(default_factory=list)


@dataclass
class _FaceData:
    # Geordnete Boundary - der zentrale AD-002-Vertrag.
    boundary: list[VertexId]


class MeshError(ValueError):
    """Verletzung eines Topologie-Invarianten."""


# ----------------------------------------------------------------------
# Point layers (AD-025 §4.2, CORE_V1_FREEZE §7.1 2026-10-27): per-vertex data owned by the Mesh
# (a morph target is one vector layer of offsets keyed by VertexId). The Core stores the values,
# journals them like positions and applies their per-kind arithmetic (origin combination, frame
# map, the new-point rule); what a layer *means* lives in `src/mirai`. Names PROVISIONAL.
# ----------------------------------------------------------------------


class LayerKind(enum.Enum):
    VECTOR = "vector"
    #: Reserved for skinning weights (AD-025 §4.1, built with Phase 6); `add_point_layer` refuses it.
    WEIGHTS = "weights"


#: H2 (AD-025 §10): what a new point gets in an existing layer.
NEW_POINT_RULES = ("interpolate", "zero")

_VECTOR_DEFAULT: LayerValue = (0.0, 0.0, 0.0)
_ORIGIN_SUM_TOLERANCE = 1e-9


@dataclass(frozen=True)
class PointLayerInfo:
    """Description of one point layer: a non-empty name (unique per mesh), its kind (never changes)
    and the new-point rule (H2): `"interpolate"` = a vertex created with an origin gets the weighted
    combination of its sources' values, `"zero"` = it gets the default. Merges always average (H3)."""

    name: str
    kind: LayerKind = LayerKind.VECTOR
    new_point: str = "interpolate"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise MeshError("Ein Punkt-Layer braucht einen nicht leeren Namen.")
        if not isinstance(self.kind, LayerKind):
            raise MeshError(f"Unbekannte Layer-Art: {self.kind!r}")
        if self.new_point not in NEW_POINT_RULES:
            raise MeshError(f"Unbekannte Neupunkt-Regel: {self.new_point!r}")
        if self.kind is LayerKind.WEIGHTS and self.new_point != "interpolate":
            # an unweighted new vertex would be unbound (AD-025 §4.1)
            raise MeshError("Ein Gewichts-Layer erlaubt nur new_point='interpolate'.")


def _vector_value(value) -> LayerValue:
    # Fast path for the common case (a tuple of three floats); x - x is 0.0 exactly for a finite x
    # and NaN for NaN / inf.
    if type(value) is tuple and len(value) == 3:
        x, y, z = value
        if type(x) is float and type(y) is float and type(z) is float:
            if (x - x) + (y - y) + (z - z) == 0.0:
                return value
            raise MeshError(f"Ein Vektorwert muss endlich sein: {value!r}")
    try:
        x, y, z = (float(c) for c in value)
    except (TypeError, ValueError):
        raise MeshError(f"Ein Vektorwert braucht genau drei Zahlen: {value!r}") from None
    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
        raise MeshError(f"Ein Vektorwert muss endlich sein: {value!r}")
    return (x, y, z)


@dataclass(frozen=True)
class SymmetryDefinition:
    """Symmetrie-Deklaration: Plane + deklarierte Seam-Edges (AD-SYM-01).

    Das Mesh *besitzt* diese Deklaration (speichert, serialisiert, trägt sie
    durch `load_state()` mit), *kennt* aber keine Symmetrie-Semantik
    (AD-SYM-01 §3) - Correspondence-Ableitung und State-Aggregation leben
    oberhalb des Core (siehe `mirai.symmetry`), nicht hier.

    Plane-Repräsentation (AD-SYM-01 §4, bewusst offen gelassen -
    hier entschieden): Punkt + Normale. Die Normale wird als Einheitsvektor
    vorausgesetzt (Aufrufer-Vertrag, hier NICHT normalisiert) - eine
    automatische Normalisierung würde eine zusätzliche Rundungsentscheidung
    einführen, die niemand verlangt hat.

    Seam-Repräsentation (AD-SYM-01 §4, ebenfalls offen gelassen - hier
    entschieden): Menge von EdgeIds, analog Maya Seam-Edge (Research R1
    §3.8). Vertex-IDs wären ebenso möglich gewesen (Wings-Muster); Edge-IDs
    sind gewählt, weil eine Seam als zusammenhängender Kantenzug zwischen
    zwei Mesh-Hälften natürlicher beschrieben wird als eine lose
    Vertex-Menge.
    """

    plane_point: Position
    plane_normal: Position
    seam_edges: frozenset[EdgeId] = field(default_factory=frozenset)


@dataclass(frozen=True)
class FaceRegion:
    """Eine benannte Menge von Faces (Saved Regions / Polygroups, AD-REGIONS-01).

    Das Mesh *besitzt* die Regionen (speichert, serialisiert, journalisiert sie), *kennt* aber keine
    Semantik: wofür eine Region steht und wie sie bei Topologieänderungen nachgeführt wird, lebt oberhalb
    des Core (`mirai.regions`). IDs toter Faces bleiben enthalten - eine ID wird nie wiederverwendet
    (AD-001), ein Undo kann sie wieder lebendig machen; Leser filtern mit `is_valid_face`.
    """

    name: str
    faces: frozenset[FaceId] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise MeshError("Eine Region braucht einen nicht leeren Namen.")
        if not all(isinstance(f, FaceId) for f in self.faces):
            raise MeshError("Eine Region enthält nur FaceIds.")


@dataclass(frozen=True)
class FaceRegions:
    """Die Regionen eines Meshes: eindeutige Namen, Reihenfolge = Anzeigereihenfolge. Regionen dürfen
    sich überlappen. Ein Mesh ohne Regionen hat `None`, nie eine leere Instanz."""

    regions: tuple[FaceRegion, ...] = ()

    def __post_init__(self) -> None:
        names = [r.name for r in self.regions]
        if len(set(names)) != len(names):
            raise MeshError("Regionsnamen müssen eindeutig sein.")

    def get(self, name: str) -> FaceRegion | None:
        return next((r for r in self.regions if r.name == name), None)


# ----------------------------------------------------------------------
# Change journal (AD-023 H1, CORE_V1_FREEZE §7.1 2026-10-21)
#
# Every mutation below records, on first touch, the before-record of each element it changes in
# every active `MeshChange`. That gives three consumers one exact source of "what changed" without
# per-operation declarations: the history (`MeshDelta` / `MeshDeltaCommand` instead of two
# whole-mesh snapshots), rollback (`rollback_change` instead of `load_state(before)`) and derived
# data (the viewport and the pick cache patch only what a `MeshWatch` reports). A new mutation
# method must call the `_touch_*` helpers before it writes, like the existing ones.
# ----------------------------------------------------------------------


class MeshChange:
    """Before-records of every element touched since recording started (`Mesh.begin_change`,
    `MeshWatch`). An element that did not exist is recorded as None. Touched is not changed: an
    element may be back to its record (`Mesh.end_change` drops those)."""

    __slots__ = (
        "vertices", "edges", "faces", "symmetry", "regions",
        "layer_meta", "layer_values", "layer_whole", "keys_only", "face_uvs",
    )

    def __init__(self, keys_only: bool = False) -> None:
        self.vertices: dict[VertexId, VertexRecord | None] = {}
        self.edges: dict[EdgeId, EdgeRecord | None] = {}
        self.faces: dict[FaceId, FaceRecord | None] = {}
        self.symmetry = _UNSET
        self.regions = _UNSET
        # Point layers (AD-025 §4.2), two record shapes. Per element: the before-value of each
        # touched (layer, vertex), None = absent. Whole layer (bulk operations): the layer's value
        # dict at the bulk write (None = the layer did not exist) plus this recording's per-element
        # records of it made before that write (the overlay; old dict + overlay = the state at the
        # start). A layer with a whole record takes no further per-element records.
        self.layer_meta = _UNSET
        self.layer_values: dict[LayerId, dict[VertexId, LayerValue | None]] = {}
        self.layer_whole: dict[LayerId, tuple] = {}
        # A watch records which layer values changed, never their before-values (all None there).
        self.keys_only = keys_only
        # Face-corner UVs (AD-026): the before-tuple of every face whose UVs were written, None =
        # the face had none. Tuples are immutable, so a watch keeps them too (no copy cost).
        self.face_uvs: dict[FaceId, FaceUVs | None] = {}

    @property
    def symmetry_touched(self) -> bool:
        return self.symmetry is not _UNSET

    @property
    def regions_touched(self) -> bool:
        return self.regions is not _UNSET

    @property
    def layers_touched(self) -> bool:
        return bool(self.layer_values or self.layer_whole) or self.layer_meta is not _UNSET

    def is_empty(self) -> bool:
        return (
            not (self.vertices or self.edges or self.faces)
            and self.symmetry is _UNSET
            and self.regions is _UNSET
            and not self.layers_touched
            and not self.face_uvs
        )


@dataclass(frozen=True)
class MeshDelta:
    """Net change of one recorded mutation: per changed element `(before, after)` records, and
    the symmetry definition if it changed. Exact by construction (AD-023 H1 exactness contract):
    ID counters are never part of it (they only move forward, AD-001), records keep boundary
    rotation and `edge.faces` order, and `Mesh.apply_delta` keeps the containers in ascending ID
    order - the order `export_state()` / `load_state()` round trips produce."""

    vertices: dict
    edges: dict
    faces: dict
    symmetry: tuple | None = None
    #: `(before, after)` of the face regions if they changed (either side may be None = no regions)
    regions: tuple | None = None
    #: `(before, after)` of the point-layer meta (AD-025 §4.2) if it changed
    layer_meta: tuple | None = None
    #: point layers changed per element: {LayerId: {VertexId: (before, after)}}, None = absent
    layer_values: dict = field(default_factory=dict)
    #: point layers changed as a whole: {LayerId: (before dict | None, after dict | None)}. Both
    #: dicts are shared (copy-on-write, never mutated); None = the layer does not exist.
    layer_whole: dict = field(default_factory=dict)
    #: face-corner UVs (AD-026) that changed: {FaceId: (before, after)}, None = no UVs
    face_uvs: dict = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return (
            not (self.vertices or self.edges or self.faces)
            and self.symmetry is None
            and self.regions is None
            and self.layer_meta is None
            and not self.layer_values
            and not self.layer_whole
            and not self.face_uvs
        )


class MeshWatch:
    """A persistent journal for a consumer of derived data (viewport, pick cache): it records
    every change of the mesh until `take()` hands the accumulated `MeshChange` over and starts a
    new one. Stops recording on `close()` or when the watch is garbage-collected, so a consumer
    that is dropped does not leave a journal behind."""

    def __init__(self, mesh: "Mesh") -> None:
        self.mesh = mesh
        self._box = [MeshChange(keys_only=True)]
        mesh._logs.append(self._box[0])
        self._finalizer = weakref.finalize(self, _detach_log, mesh._logs, self._box)

    def take(self) -> MeshChange:
        box, logs = self._box, self.mesh._logs
        old, new = box[0], MeshChange(keys_only=True)
        for i, log in enumerate(logs):
            if log is old:
                logs[i] = new
                break
        else:
            return old  # closed
        box[0] = new
        return old

    def peek(self) -> MeshChange:
        return self._box[0]

    def close(self) -> None:
        self._finalizer()


def _detach_log(logs: list, box: list) -> None:
    for i, log in enumerate(logs):
        if log is box[0]:
            del logs[i]
            return


class Mesh:
    def __init__(self) -> None:
        self._vertex_alloc = IdAllocator(VertexId)
        self._edge_alloc = IdAllocator(EdgeId)
        self._face_alloc = IdAllocator(FaceId)

        self._vertices: dict[VertexId, _VertexData] = {}
        self._edges: dict[EdgeId, _EdgeData] = {}
        self._faces: dict[FaceId, _FaceData] = {}

        # Interner Lookup-Index (Implementierungsdetail, kein öffentlicher
        # Vertrag): ungeordnetes Vertex-Paar -> existierende EdgeId.
        self._edge_lookup: dict[frozenset[VertexId], EdgeId] = {}
        # Interner Index (2026-10-21): Vertex -> anliegende Edges. Ersetzt den O(E)-Scan in
        # vertex_edges() und in Delete/Dissolve; die Reihenfolge der Rückgabe bleibt die der
        # Edge-Tabelle, weil diese aufsteigend nach ID geordnet ist (Invariante, s. u.).
        self._vertex_edges: dict[VertexId, set[EdgeId]] = {}
        # Aktive Änderungs-Journale (MeshChange), siehe begin_change() / MeshWatch.
        self._logs: list[MeshChange] = []

        # Invariante (2026-10-21): alle drei Element-Tabellen iterieren in aufsteigender ID-
        # Reihenfolge. IDs werden monoton vergeben und neu immer hinten angefügt; load_state()
        # und apply_delta() stellen die Reihenfolge her. Damit ist die Reihenfolge von
        # all_*_ids() unabhängig davon, ob ein Zustand über Snapshot oder Delta entstand.

        # Symmetry Definition (AD-SYM-01): bewusst ein PUBLIC-Attribut statt
        # Getter/Setter-Paar - analog zu Scene.morph_targets/rig/animation
        # (reservierter Subsystem-Platz, direkt settbar), nicht analog zur
        # Topologie-Query-API (AD-002 §15 Punkt 1), die ausschließlich für
        # die Vertex-/Edge-/Face-Container gilt. Default: keine Definition
        # (Symmetrie "aus"). Seit 2026-10-21 eine Property, damit das Journal das Setzen sieht;
        # Lesen und Setzen bleiben unverändert `mesh.symmetry_definition`.
        self._symmetry_definition: SymmetryDefinition | None = None
        # Saved Regions (AD-REGIONS-01): wie die Symmetry Definition ein vom Mesh besessener Wert, den das
        # Journal beim Setzen sieht; Lesen und Setzen als `mesh.face_regions`.
        self._face_regions: FaceRegions | None = None
        # Point layers (AD-025 §4.2). Meta in display order; one value mapping per layer (L2: a value
        # equal to the default is never stored), packed since Phase 4 (`layer_storage`: float64
        # arrays over one append-only slot map per mesh). Copy-on-write: a value mapping that a
        # record or a delta references is never mutated - `_layer_shared` names the layers whose
        # live mapping is such a shared one, the first write copies it.
        self._layer_alloc = IdAllocator(LayerId, start=1)
        self._layer_meta: tuple[tuple[LayerId, PointLayerInfo], ...] = ()
        self._layer_slots = LayerSlots()
        self._layer_values: dict[LayerId, PackedValues] = {}
        self._layer_shared: set[LayerId] = set()
        # Face-corner UVs (AD-026): per face one (u, v) per boundary corner, in boundary order
        # (invariant U1: keys are live faces, one pair per corner). Faces without UVs have no entry;
        # the mesh "has UVs" while any face has. Every write goes through `_write_uvs` (journal).
        self._face_uvs: dict[FaceId, FaceUVs] = {}

    @property
    def face_regions(self) -> FaceRegions | None:
        return self._face_regions

    @face_regions.setter
    def face_regions(self, regions: FaceRegions | None) -> None:
        if regions is not None and not isinstance(regions, FaceRegions):
            raise MeshError("face_regions erwartet FaceRegions oder None.")
        if regions is not None and not regions.regions:
            regions = None  # no regions is always None, never an empty instance
        for log in self._logs:
            if log.regions is _UNSET:
                log.regions = self._face_regions
        self._face_regions = regions

    @property
    def symmetry_definition(self) -> SymmetryDefinition | None:
        return self._symmetry_definition

    @symmetry_definition.setter
    def symmetry_definition(self, definition: SymmetryDefinition | None) -> None:
        for log in self._logs:
            if log.symmetry is _UNSET:
                log.symmetry = self._symmetry_definition
        self._symmetry_definition = definition

    # ------------------------------------------------------------------
    # Journal-Helfer: vor jedem Schreibzugriff aufzurufen (siehe MeshChange)
    # ------------------------------------------------------------------

    def _touch_v(self, vid: VertexId) -> None:
        for log in self._logs:
            if vid not in log.vertices:
                data = self._vertices.get(vid)
                log.vertices[vid] = None if data is None else data.position

    def _touch_e(self, eid: EdgeId) -> None:
        for log in self._logs:
            if eid not in log.edges:
                data = self._edges.get(eid)
                log.edges[eid] = None if data is None else (data.v0, data.v1, tuple(data.faces))

    def _touch_f(self, fid: FaceId) -> None:
        for log in self._logs:
            if fid not in log.faces:
                data = self._faces.get(fid)
                log.faces[fid] = None if data is None else tuple(data.boundary)

    def _touch_l(self, lid: LayerId, vid: VertexId) -> None:
        values = self._layer_values[lid]
        for log in self._logs:
            if lid in log.layer_whole:
                continue
            records = log.layer_values.get(lid)
            if records is None:
                records = log.layer_values[lid] = {}
            if vid not in records:
                records[vid] = None if log.keys_only else values.get(vid)

    def _write_value(self, lid: LayerId, vid: VertexId, value: LayerValue | None) -> None:
        """The one per-element write path: journal, copy-on-write, canonical form (L2)."""
        if value is not None and value == _VECTOR_DEFAULT:
            value = None
        values = self._layer_values[lid]
        if values.get(vid) == value:
            return
        if self._logs:
            self._touch_l(lid, vid)
        if lid in self._layer_shared:
            values = self._layer_values[lid] = values.copy()
            self._layer_shared.discard(lid)
        if value is None:
            del values[vid]
        else:
            values[vid] = value

    def _bulk_set(self, lid: LayerId, values: dict | None, *, shared: bool) -> None:
        """The one whole-layer write path (AD-025 §4.2): `values` replaces the layer's dict
        (None = the layer's values go away). The old dict is never mutated; it becomes the
        before-record of every recording that has none for this layer yet (O(1) per log)."""
        old = self._layer_values.get(lid)
        for log in self._logs:
            if lid not in log.layer_whole:
                overlay = log.layer_values.pop(lid, {})
                log.layer_whole[lid] = (None, None) if log.keys_only else (old, overlay)
        if values is None:
            self._layer_values.pop(lid, None)
            self._layer_shared.discard(lid)
        else:
            self._layer_values[lid] = self._packed(values)
            if shared:
                self._layer_shared.add(lid)
            else:
                self._layer_shared.discard(lid)

    def _packed(self, values) -> PackedValues:
        """`values` as this mesh's packed form: itself when it is one already (a record's or a
        delta's, shared as it is), else a packed copy (a plain dict, another mesh's values)."""
        if isinstance(values, PackedValues) and values.slots is self._layer_slots:
            return values
        return PackedValues(self._layer_slots, values)

    def _set_layer_meta(self, meta: tuple) -> None:
        for log in self._logs:
            if log.layer_meta is _UNSET:
                log.layer_meta = self._layer_meta
        self._layer_meta = meta

    def _index_edge(self, eid: EdgeId, v0: VertexId, v1: VertexId) -> None:
        index = self._vertex_edges
        for v in (v0, v1):
            edges = index.get(v)
            if edges is None:
                index[v] = {eid}
            else:
                edges.add(eid)

    def _unindex_edge(self, eid: EdgeId, v0: VertexId, v1: VertexId) -> None:
        index = self._vertex_edges
        for v in (v0, v1):
            edges = index.get(v)
            if edges is not None:
                edges.discard(eid)
                if not edges:
                    del index[v]

    def _pop_edge(self, eid: EdgeId) -> _EdgeData:
        """Entfernt eine Edge samt Lookup- und Index-Eintrag (Journal: Aufrufer hat sie berührt)."""
        edge = self._edges.pop(eid)
        del self._edge_lookup[frozenset((edge.v0, edge.v1))]
        self._unindex_edge(eid, edge.v0, edge.v1)
        return edge

    # ------------------------------------------------------------------
    # Gültigkeitsprüfung (AD-001)
    # ------------------------------------------------------------------

    def is_valid_vertex(self, vertex_id: VertexId) -> bool:
        return vertex_id in self._vertices

    def is_valid_edge(self, edge_id: EdgeId) -> bool:
        return edge_id in self._edges

    def is_valid_face(self, face_id: FaceId) -> bool:
        return face_id in self._faces

    # ------------------------------------------------------------------
    # Position (§9 - Indirektion für spätere Deformation-Kette)
    # ------------------------------------------------------------------

    def vertex_position(self, vertex_id: VertexId) -> Position:
        return self._vertices[vertex_id].position

    def set_vertex_position(self, vertex_id: VertexId, position: Position) -> None:
        """Setzt die Basis-Position (V1: identisch zur finalen Position).

        Späteren Systemen (Morph/Skin/Subdivision) steht frei, die
        angezeigte Position abweichend von der Basis-Position zu berechnen,
        solange sie ebenfalls über eine Query-Funktion statt eines rohen
        Attributs gehen.
        """
        data = self._vertices[vertex_id]
        if self._logs:
            self._touch_v(vertex_id)
        data.position = position

    # ------------------------------------------------------------------
    # Point layers (AD-025 §4.2) - API names PROVISIONAL
    # ------------------------------------------------------------------

    def point_layer_ids(self) -> list[LayerId]:
        """Layer IDs in display order."""
        return [lid for lid, _ in self._layer_meta]

    def has_point_layers(self) -> bool:
        return bool(self._layer_meta)

    def point_layer_info(self, layer_id: LayerId) -> PointLayerInfo:
        for lid, info in self._layer_meta:
            if lid == layer_id:
                return info
        raise MeshError(f"Unbekannter Punkt-Layer {layer_id!r}")

    def layer_value(self, layer_id: LayerId, vertex_id: VertexId) -> LayerValue:
        """The value of a vertex in a layer; the kind's default when none is stored."""
        values = self._layer_values.get(layer_id)
        if values is None:
            raise MeshError(f"Unbekannter Punkt-Layer {layer_id!r}")
        return values.get(vertex_id, _VECTOR_DEFAULT)

    def layer_items(self, layer_id: LayerId) -> list[tuple[VertexId, LayerValue]]:
        """The stored (non-default) values of a layer, ascending VertexId."""
        values = self._layer_values.get(layer_id)
        if values is None:
            raise MeshError(f"Unbekannter Punkt-Layer {layer_id!r}")
        return sorted(values.items())

    def layer_storage_bytes(self) -> int:
        """Bytes held by the live layer value buffers plus the shared slot map's entries (an
        estimate for the memory probe; records and deltas may share or hold older buffers)."""
        return sum(v.nbytes() for v in self._layer_values.values()) + 100 * len(self._layer_slots)

    def add_point_layer(self, info: PointLayerInfo) -> LayerId:
        """Appends an empty layer. ID continuity: exactly one new LayerId (never reused, AD-001)."""
        if not isinstance(info, PointLayerInfo):
            raise MeshError("add_point_layer erwartet PointLayerInfo.")
        if info.kind is not LayerKind.VECTOR:
            raise MeshError(f"Layer-Art {info.kind.value!r} ist noch nicht gebaut (AD-025 §4.1).")
        if any(other.name == info.name for _, other in self._layer_meta):
            raise MeshError(f"Punkt-Layer-Name schon vergeben: {info.name!r}")
        lid = self._layer_alloc.allocate()
        self._set_layer_meta(self._layer_meta + ((lid, info),))
        self._bulk_set(lid, {}, shared=False)
        return lid

    def remove_point_layer(self, layer_id: LayerId) -> None:
        """Removes a layer with its values (a whole-layer record, O(1) journal memory)."""
        self.point_layer_info(layer_id)
        self._bulk_set(layer_id, None, shared=False)
        self._set_layer_meta(tuple(entry for entry in self._layer_meta if entry[0] != layer_id))

    def set_point_layer_info(self, layer_id: LayerId, info: PointLayerInfo) -> None:
        """Renames a layer or changes its new-point rule; the kind never changes (L4)."""
        old = self.point_layer_info(layer_id)
        if not isinstance(info, PointLayerInfo):
            raise MeshError("set_point_layer_info erwartet PointLayerInfo.")
        if info.kind is not old.kind:
            raise MeshError("Die Art eines Punkt-Layers ändert sich nie.")
        if any(lid != layer_id and other.name == info.name for lid, other in self._layer_meta):
            raise MeshError(f"Punkt-Layer-Name schon vergeben: {info.name!r}")
        if info != old:
            self._set_layer_meta(
                tuple((lid, info if lid == layer_id else other) for lid, other in self._layer_meta)
            )

    def set_point_layer_order(self, layer_ids: Sequence[LayerId]) -> None:
        """Sets the display order; `layer_ids` is a permutation of `point_layer_ids()`."""
        order = list(layer_ids)
        current = self.point_layer_ids()
        if sorted(order) != sorted(current) or len(set(order)) != len(order):
            raise MeshError("set_point_layer_order erwartet eine Permutation der Layer-IDs.")
        if order != current:
            infos = dict(self._layer_meta)
            self._set_layer_meta(tuple((lid, infos[lid]) for lid in order))

    def set_layer_value(self, layer_id: LayerId, vertex_id: VertexId, value) -> None:
        """Sets one value (journaled per element); the default removes the stored value (L2)."""
        if layer_id not in self._layer_values:
            raise MeshError(f"Unbekannter Punkt-Layer {layer_id!r}")
        if vertex_id not in self._vertices:
            raise MeshError(f"Unbekannter Vertex {vertex_id!r}")
        self._write_value(layer_id, vertex_id, _vector_value(value))

    def map_vector_layers(self, matrix: Sequence[Sequence[float]]) -> None:
        """Frame change (AD-025 §4.3): every vector value v -> M·v, M the linear part of the point
        map (Apply transform: s·R; a mirror: H). A bulk operation: each layer gets a new dict, the
        old one becomes the whole-layer record. The identity records nothing."""
        try:
            m = tuple(tuple(float(c) for c in row) for row in matrix)
        except (TypeError, ValueError):
            raise MeshError("map_vector_layers erwartet eine 3x3-Matrix.") from None
        if len(m) != 3 or any(len(row) != 3 for row in m) or not all(map(math.isfinite, sum(m, ()))):
            raise MeshError("map_vector_layers erwartet eine endliche 3x3-Matrix.")
        if m == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
            return
        mapped: dict[LayerId, PackedValues] = {}
        for lid, info in self._layer_meta:
            values = self._layer_values[lid]
            if info.kind is not LayerKind.VECTOR or not values:
                continue
            try:
                mapped[lid] = self._packed(values).mapped(m)
            except ValueError:
                raise MeshError("map_vector_layers: Ergebnis nicht endlich.") from None
        for lid, new in mapped.items():
            self._bulk_set(lid, new, shared=False)

    def _origin_values(self, origin: VertexOrigin) -> list[tuple[LayerId, LayerValue]]:
        """Validates `origin` and combines its sources' values per layer (AD-025 §4.1), before
        any mutation. Vector: sum of w_i·v_i per component, the first term not added to 0.0 so a
        copy ((v, 1.0),) is bit-exact (also for -0.0)."""
        try:
            pairs = [(src, float(w)) for src, w in origin]
        except (TypeError, ValueError):
            raise MeshError(f"Ungültige Herkunft: {origin!r}") from None
        for src, w in pairs:
            if src not in self._vertices:
                raise MeshError(f"Herkunft nennt einen unbekannten Vertex {src!r}")
            if not math.isfinite(w):
                raise MeshError(f"Herkunftsgewicht nicht endlich: {w!r}")
        if pairs and abs(sum(w for _, w in pairs) - 1.0) > _ORIGIN_SUM_TOLERANCE:
            raise MeshError("Herkunftsgewichte müssen sich zu 1 summieren.")
        out = []
        if not pairs:
            return out
        for lid, info in self._layer_meta:
            if info.new_point != "interpolate":
                continue
            values = self._layer_values[lid]
            total = None
            for src, w in pairs:
                v = values.get(src, _VECTOR_DEFAULT)
                term = (w * v[0], w * v[1], w * v[2])
                total = term if total is None else (total[0] + term[0], total[1] + term[1], total[2] + term[2])
            if total != _VECTOR_DEFAULT:
                out.append((lid, total))
        if not all(math.isfinite(c) for _, value in out for c in value):
            raise MeshError("Herkunft ergibt keinen endlichen Wert.")
        return out

    # ------------------------------------------------------------------
    # Face-corner UVs (AD-026, CORE_V1_FREEZE §7.1 2026-10-29): one UV map per mesh, stored per
    # face as one (u, v) per boundary corner. The Core stores, journals and carries them through its
    # topology primitives (each documents its rule); what they show (a texture) lives above.
    # ------------------------------------------------------------------

    def has_face_uvs(self) -> bool:
        return bool(self._face_uvs)

    def face_uvs(self, face_id: FaceId) -> FaceUVs | None:
        """The face's UVs in boundary order (one pair per `face_vertices` entry), None = none."""
        if face_id not in self._faces:
            raise MeshError(f"Unbekannte Face: {face_id!r}")
        return self._face_uvs.get(face_id)

    def corner_uv(self, face_id: FaceId, vertex_id: VertexId) -> UV | None:
        uvs = self._face_uvs.get(face_id)
        if uvs is None:
            return None
        return uvs[self._faces[face_id].boundary.index(vertex_id)]

    def set_face_uvs(self, face_id: FaceId, uvs) -> None:
        """Sets (or with None removes) the face's UVs; one pair per boundary corner, finite. Journaled."""
        face = self._faces.get(face_id)
        if face is None:
            raise MeshError(f"Unbekannte Face: {face_id!r}")
        if uvs is not None:
            try:
                uvs = uv_tuple(uvs, len(face.boundary))
            except ValueError as exc:
                raise MeshError(str(exc)) from None
        self._write_uvs(face_id, uvs)

    def _write_uvs(self, fid: FaceId, uvs: FaceUVs | None) -> None:
        """The one write path of the UVs (journal; no validation - callers pass valid tuples)."""
        old = self._face_uvs.get(fid)
        if old == uvs:
            return
        for log in self._logs:
            if fid not in log.face_uvs:
                log.face_uvs[fid] = old
        if uvs is None:
            del self._face_uvs[fid]
        else:
            self._face_uvs[fid] = uvs

    def _corner_map(self, fid: FaceId) -> dict[VertexId, UV] | None:
        uvs = self._face_uvs.get(fid)
        if uvs is None:
            return None
        return dict(zip(self._faces[fid].boundary, uvs))

    def _infer_uvs(self, boundary: Sequence[VertexId]) -> FaceUVs | None:
        """UVs for a new face nobody gave UVs to (Cap, symmetric Cap, a tool's `add_face`), read from
        the existing faces around each corner before the face exists: a face that shares an edge of
        the new boundary at that corner wins, else any face with that corner (ascending ids, so the
        result is deterministic). Unresolved corners get the mean of the resolved ones; no resolved
        corner = no UVs."""
        uvs = self._face_uvs
        n = len(boundary)
        out: list[UV | None] = []
        for i, v in enumerate(boundary):
            neighbours = (boundary[i - 1], boundary[(i + 1) % n])
            shared = fallback = None
            for eid in sorted(self._vertex_edges.get(v, ()), key=int):
                e = self._edges[eid]
                other = e.v1 if e.v0 == v else e.v0
                for f in e.faces:
                    fu = uvs.get(f)
                    if fu is None:
                        continue
                    if other in neighbours:
                        shared = fu[self._faces[f].boundary.index(v)]
                        break
                    if fallback is None:
                        fallback = fu[self._faces[f].boundary.index(v)]
                if shared is not None:
                    break
            out.append(shared if shared is not None else fallback)
        known = [uv for uv in out if uv is not None]
        if not known:
            return None
        if len(known) < n:
            centre = mean_uv(known)
            out = [centre if uv is None else uv for uv in out]
        return tuple(out)

    # ------------------------------------------------------------------
    # Topologie-Query-API (AD-002) - einziger erlaubter Lesezugriff
    # ------------------------------------------------------------------

    def face_vertices(self, face_id: FaceId) -> list[VertexId]:
        return list(self._faces[face_id].boundary)

    def face_edges(self, face_id: FaceId) -> list[EdgeId]:
        boundary = self._faces[face_id].boundary
        n = len(boundary)
        edges = []
        for i in range(n):
            v_a, v_b = boundary[i], boundary[(i + 1) % n]
            edge_id = self._edge_lookup.get(frozenset((v_a, v_b)))
            if edge_id is None:  # pragma: no cover - Invariante verletzt
                raise MeshError(f"Fehlende Edge zwischen {v_a!r} und {v_b!r}")
            edges.append(edge_id)
        return edges

    def edge_faces(self, edge_id: EdgeId) -> list[FaceId]:
        return list(self._edges[edge_id].faces)

    def edge_vertices(self, edge_id: EdgeId) -> tuple[VertexId, VertexId]:
        e = self._edges[edge_id]
        return (e.v0, e.v1)

    def vertex_edges(self, vertex_id: VertexId) -> list[EdgeId]:
        # Aufsteigend nach ID = Reihenfolge der Edge-Tabelle (Invariante, siehe __init__) -
        # dieselbe Liste wie der frühere O(E)-Scan.
        edges = self._vertex_edges.get(vertex_id)
        return sorted(edges) if edges else []

    def all_vertex_ids(self) -> list[VertexId]:
        return list(self._vertices.keys())

    def all_edge_ids(self) -> list[EdgeId]:
        return list(self._edges.keys())

    def all_face_ids(self) -> list[FaceId]:
        return list(self._faces.keys())

    # ------------------------------------------------------------------
    # Mutation-Layer (§7 "Topologie-Grenze") - einziger erlaubter
    # Schreibzugriff auf Topologie. Jede Funktion dokumentiert ihren
    # ID-Kontinuitäts-Vertrag (§8 / AD-001).
    # ------------------------------------------------------------------

    def add_vertex(self, position: Position, origin: VertexOrigin | None = None) -> VertexId:
        """ID-Kontinuität: erzeugt genau eine neue VertexId.

        Point layers (AD-025 §4.1): without layers `origin` is ignored. With layers the caller
        must say where the vertex comes from - `((v, 1.0),)` for a copy of v, any affine
        combination of live vertices, or `()` for "no source" (defaults); `None` raises MeshError
        before any mutation (the Core backstop against a tool that forgot its origin)."""
        if self._layer_meta:
            if origin is None:
                raise MeshError(
                    "add_vertex: dieses Mesh hat Punkt-Layer - der neue Vertex braucht eine Herkunft (origin)."
                )
            values = self._origin_values(origin)
            vid = self._new_vertex(position)
            for lid, value in values:
                self._write_value(lid, vid, value)
            return vid
        return self._new_vertex(position)

    def _new_vertex(self, position: Position) -> VertexId:
        vid = self._vertex_alloc.allocate()
        if self._logs:
            self._touch_v(vid)
        self._vertices[vid] = _VertexData(position=position)
        return vid

    def _get_or_create_edge(self, v_a: VertexId, v_b: VertexId) -> EdgeId:
        key = frozenset((v_a, v_b))
        existing = self._edge_lookup.get(key)
        if existing is not None:
            return existing
        eid = self._edge_alloc.allocate()
        if self._logs:
            self._touch_e(eid)
        self._edges[eid] = _EdgeData(v0=v_a, v1=v_b)
        self._edge_lookup[key] = eid
        self._index_edge(eid, v_a, v_b)
        return eid

    def add_face(self, vertex_ids: list[VertexId], uvs=None, *, infer_uvs: bool = True) -> FaceId:
        """Erzeugt eine Face aus einer geordneten Liste bestehender Vertices.

        ID-Kontinuität:
        - alle übergebenen VertexIds bleiben unverändert.
        - für jedes Vertex-Paar entlang der Boundary wird eine bestehende
          Edge wiederverwendet, falls vorhanden, sonst eine neue EdgeId
          erzeugt.
        - es entsteht genau eine neue FaceId.

        UVs (AD-026): `uvs` = ein (u, v) je Ecke (geprüft vor der ersten Mutation). Ohne `uvs` auf
        einem Mesh mit UVs werden sie aus den Nachbar-Faces der Ecken abgeleitet (`_infer_uvs`),
        außer mit `infer_uvs=False` (die Face bleibt ohne UVs).
        """
        if len(vertex_ids) < 3:
            raise MeshError("Eine Face benötigt mindestens 3 Vertices.")
        for v in vertex_ids:
            if not self.is_valid_vertex(v):
                raise MeshError(f"Unbekanntes Vertex: {v!r}")
        if uvs is not None:
            try:
                uvs = uv_tuple(uvs, len(vertex_ids))
            except ValueError as exc:
                raise MeshError(str(exc)) from None
        elif infer_uvs and self._face_uvs:
            uvs = self._infer_uvs(vertex_ids)

        fid = self._face_alloc.allocate()
        logged = bool(self._logs)
        if logged:
            self._touch_f(fid)
        n = len(vertex_ids)
        for i in range(n):
            v_a, v_b = vertex_ids[i], vertex_ids[(i + 1) % n]
            eid = self._get_or_create_edge(v_a, v_b)
            if logged:
                self._touch_e(eid)
            self._edges[eid].faces.append(fid)

        self._faces[fid] = _FaceData(boundary=list(vertex_ids))
        if uvs is not None:
            self._write_uvs(fid, uvs)
        return fid

    def add_edge(self, v_a: VertexId, v_b: VertexId) -> EdgeId:
        """Erzeugt eine freie Edge zwischen zwei bestehenden Vertices, ohne
        Face-Zugehörigkeit.

        ID-Kontinuität:
        - beide übergebenen VertexIds bleiben unverändert.
        - erzeugt genau eine neue EdgeId, falls zwischen v_a und v_b noch
          keine Edge existiert.
        - existiert zwischen v_a und v_b bereits eine Edge (frei oder mit
          Face(s)), wird deren bestehende EdgeId zurückgegeben, keine neue
          Edge erzeugt (identisches Verhalten zu _get_or_create_edge, das
          diese Methode direkt aufruft).

        Additiv: verändert keinen bestehenden AD-001/AD-002/AD-003-Vertrag.
        """
        if not self.is_valid_vertex(v_a) or not self.is_valid_vertex(v_b):
            raise MeshError("add_edge benötigt zwei bestehende Vertices.")
        if v_a == v_b:
            raise MeshError("add_edge benötigt zwei unterschiedliche Vertices.")
        return self._get_or_create_edge(v_a, v_b)

    def remove_face(self, face_id: FaceId) -> None:
        """Entfernt eine Face.

        ID-Kontinuität:
        - die FaceId wird ungültig.
        - Vertices bleiben unverändert.
        - Edges, die nur an dieser Face hingen, bleiben als freie
          (Rand-)Edges mit unveränderter ID erhalten - sie werden NICHT
          automatisch gelöscht. Das ist eine bewusste V1-Entscheidung:
          explizites Edge-Löschen ist Aufgabe des Aufrufers/einer
          Higher-Level-Operation, nicht dieser Primitive.
        """
        logged = bool(self._logs)
        if logged and face_id in self._faces:
            self._touch_f(face_id)
        if face_id in self._face_uvs:
            self._write_uvs(face_id, None)
        face = self._faces.pop(face_id)
        n = len(face.boundary)
        for i in range(n):
            v_a, v_b = face.boundary[i], face.boundary[(i + 1) % n]
            eid = self._edge_lookup[frozenset((v_a, v_b))]
            if logged:
                self._touch_e(eid)
            self._edges[eid].faces.remove(face_id)

    def split_edge(self, edge_id: EdgeId, t: float = 0.5) -> tuple[VertexId, EdgeId, EdgeId]:
        """Teilt eine Edge an der durch t parametrisierten Position.

        t ist der Interpolationsparameter: 0.0 entspricht edge.v0,
        1.0 entspricht edge.v1. Der Standardwert t=0.5 entspricht
        bit-identisch dem bisherigen Mittelpunkt-Verhalten.

        Vorbedingung: t muss im offenen Intervall (0.0, 1.0) liegen.
        Liegt t außerhalb dieses Bereichs, wird MeshError ausgelöst,
        bevor der Mesh-Zustand verändert wird.

        ID-Kontinuität:
        - die ursprüngliche EdgeId wird ungültig.
        - beide ursprünglichen Endpunkt-VertexIds bleiben unverändert.
        - es entsteht genau eine neue VertexId und zwei neue EdgeIds.
        - jede angrenzende Face behält ihre FaceId, ihre Boundary-Liste
          wird jedoch aktualisiert (neuer Vertex wird eingefügt).

        UVs (AD-026): in jeder angrenzenden Face mit UVs bekommt die neue Ecke
        (1-t)·uv(v0) + t·uv(v1) der Ecken dieser Face - pro Face, also bleibt
        eine UV-Naht entlang der Edge erhalten.

        Rückgabe: (neue_vertex_id, neue_edge_id_a, neue_edge_id_b)
        """
        if t <= 0.0 or t >= 1.0:
            raise MeshError("split_edge: t must be in (0.0, 1.0)")

        logged = bool(self._logs)
        if logged and edge_id in self._edges:
            self._touch_e(edge_id)
        edge = self._edges[edge_id]
        # Point layers (AD-025 §4.1): origin ((v0, 1-t), (v1, t)) with the stored ends, the value
        # in the position's own expression - computed before the first mutation.
        layer_values = self._blend_values(edge.v0, edge.v1, t) if self._layer_meta else ()
        self._pop_edge(edge_id)

        p0 = self.vertex_position(edge.v0)
        p1 = self.vertex_position(edge.v1)
        mid_pos = tuple(a * (1.0 - t) + b * t for a, b in zip(p0, p1))
        mid = self._new_vertex(mid_pos)
        for lid, value in layer_values:
            self._write_value(lid, mid, value)

        eid_a = self._edge_alloc.allocate()
        eid_b = self._edge_alloc.allocate()
        if logged:
            self._touch_e(eid_a)
            self._touch_e(eid_b)
        self._edges[eid_a] = _EdgeData(v0=edge.v0, v1=mid, faces=[])
        self._edges[eid_b] = _EdgeData(v0=mid, v1=edge.v1, faces=[])
        self._edge_lookup[frozenset((edge.v0, mid))] = eid_a
        self._edge_lookup[frozenset((mid, edge.v1))] = eid_b
        self._index_edge(eid_a, edge.v0, mid)
        self._index_edge(eid_b, mid, edge.v1)

        for fid in edge.faces:
            if logged:
                self._touch_f(fid)
            boundary = self._faces[fid].boundary
            uvs = self._face_uvs.get(fid)
            new_boundary = []
            new_uvs = []
            n = len(boundary)
            for i in range(n):
                v_curr, v_next = boundary[i], boundary[(i + 1) % n]
                new_boundary.append(v_curr)
                if uvs is not None:
                    new_uvs.append(uvs[i])
                if frozenset((v_curr, v_next)) == frozenset((edge.v0, edge.v1)):
                    new_boundary.append(mid)
                    if uvs is not None:
                        j = (i + 1) % n
                        a, b = (uvs[i], uvs[j]) if v_curr == edge.v0 else (uvs[j], uvs[i])
                        new_uvs.append(lerp_uv(a, b, t))
            self._faces[fid].boundary = new_boundary
            if uvs is not None:
                self._write_uvs(fid, tuple(new_uvs))
            self._edges[eid_a].faces.append(fid)
            self._edges[eid_b].faces.append(fid)

        return mid, eid_a, eid_b

    def _blend_values(self, v0: VertexId, v1: VertexId, t: float) -> list[tuple[LayerId, LayerValue]]:
        out = []
        layer_values = self._layer_values
        s = 1.0 - t
        for lid, info in self._layer_meta:
            if info.new_point != "interpolate":
                continue
            values = layer_values[lid]
            a = values.get(v0)
            b = values.get(v1)
            if a is None:
                if b is None:
                    continue
                a = _VECTOR_DEFAULT
            elif b is None:
                b = _VECTOR_DEFAULT
            # the position's own expression, a·(1 - t) + b·t per component
            value = (a[0] * s + b[0] * t, a[1] * s + b[1] * t, a[2] * s + b[2] * t)
            if value != _VECTOR_DEFAULT:
                out.append((lid, value))
        return out

    def collapse_edge(self, edge_id: EdgeId) -> VertexId:
        """Zieht eine Edge zu einem einzelnen Vertex zusammen.

        ID-Kontinuität:
        - die EdgeId wird ungültig.
        - der erste Endpunkt (v0) "gewinnt" und behält seine VertexId;
          seine Position wird auf den Mittelpunkt beider ursprünglichen
          Positionen gesetzt.
        - der zweite Endpunkt (v1) wird ungültig; alle Faces, die v1
          referenzierten, referenzieren danach stattdessen v0.
        - angrenzende Faces behalten ihre FaceId. Wird eine Face dadurch
          degeneriert (< 3 eindeutige Vertices), wird sie entfernt (ihre
          FaceId wird dabei ungültig - das ist eine Nebenwirkung, kein
          impliziter Vertrag für den Regelfall).

        Invariante (explizit getestet, siehe test_ad002_collapse_edge_no_stale_edges):
        - nach Rückkehr aus dieser Funktion referenziert KEINE verbleibende
          Edge mehr `removed` als Endpunkt. Jede Edge, die vor dem Collapse
          zusätzlich zur kollabierten Kante an `removed` hing, wird auf
          `survivor` umgebogen; existiert dafür bereits eine survivor<->other-
          Edge, werden beide zusammengeführt (Face-Referenzen vereinigt), statt
          eine zweite, stale Edge stehen zu lassen.

        UVs (AD-026): in den Faces der Edge bekommt die Survivor-Ecke den Mittelwert ihrer beiden
        Ecken. In den übrigen Faces um beide Endpunkte rückt eine Ecke mit, wenn ihr Wert dem einer
        Edge-Face gleicht (keine Naht dort); an einer Naht behält sie ihren Wert.

        Bekannte V1-Einschränkung: keine allgemeine Non-Manifold-Prüfung.
        """
        logged = bool(self._logs)
        if logged and edge_id in self._edges:
            self._touch_e(edge_id)
        edge = self._edges[edge_id]
        uv_plan = self._plan_collapse_uvs(edge.v0, edge.v1, edge.faces) if self._face_uvs else None
        self._pop_edge(edge_id)
        survivor, removed = edge.v0, edge.v1

        p0 = self.vertex_position(survivor)
        p1 = self.vertex_position(removed)
        self.set_vertex_position(survivor, tuple((a + b) / 2.0 for a, b in zip(p0, p1)))
        # Point layers (AD-025 §4.1, H3): the survivor gets the average, the position's expression
        # (every layer - the new-point rule is about new points); `removed`'s values go with it.
        for lid in self._layer_values:
            values = self._layer_values[lid]
            a, b = values.get(survivor), values.get(removed)
            if a is not None or b is not None:
                a, b = a or _VECTOR_DEFAULT, b or _VECTOR_DEFAULT
                self._write_value(lid, survivor, tuple((x + y) / 2.0 for x, y in zip(a, b)))

        # Jede Face, die `removed` in ihrer Boundary hat, hängt an einer Edge von `removed` (eine Face
        # steht in den Face-Listen aller Edges ihrer Boundary) - vor dem Umbiegen unten einsammeln,
        # statt alle Faces des Meshes zu durchsuchen.
        removed_faces = {f for eid in self.vertex_edges(removed) for f in self._edges[eid].faces}

        # Invariant (fehlte bisher als expliziter Test, siehe tests/test_core.py):
        # nach collapse_edge() darf KEINE Edge mehr auf `removed` verweisen.
        # Jede verbleibende Edge, die `removed` als Endpunkt hatte, wird daher
        # explizit auf `survivor` umgebogen - bei bereits existierender
        # survivor<->other-Edge werden beide zusammengeführt (Face-Referenzen
        # vereinigt, redundante EdgeId verworfen), statt wie zuvor eine neue,
        # doppelte Edge anzulegen und die alte (stale) Edge stehen zu lassen.
        # Aufsteigend nach ID = Reihenfolge des früheren Scans über die Edge-Tabelle.
        for eid in self.vertex_edges(removed):
            e = self._edges[eid]
            if logged:
                self._touch_e(eid)
            old_key = frozenset((e.v0, e.v1))
            other = e.v1 if e.v0 == removed else e.v0
            del self._edge_lookup[old_key]
            self._unindex_edge(eid, e.v0, e.v1)
            if other == survivor:
                # Parallele Duplikat-Edge zur bereits kollabierten Kante - verwerfen.
                del self._edges[eid]
                continue
            new_key = frozenset((survivor, other))
            existing_eid = self._edge_lookup.get(new_key)
            if existing_eid is not None and existing_eid != eid:
                existing = self._edges[existing_eid]
                if logged:
                    self._touch_e(existing_eid)
                for fid in e.faces:
                    if fid not in existing.faces:
                        existing.faces.append(fid)
                del self._edges[eid]
            else:
                if e.v0 == removed:
                    e.v0 = survivor
                else:
                    e.v1 = survivor
                self._edge_lookup[new_key] = eid
                self._index_edge(eid, e.v0, e.v1)

        # Reihenfolge wie beim früheren Scan: die Faces der Edge, dann aufsteigend nach ID (= Tabellenreihenfolge).
        affected_faces = list(edge.faces)
        affected_faces += sorted(
            (
                f for f in removed_faces
                if f not in affected_faces and f in self._faces and removed in self._faces[f].boundary
            ),
            key=int,
        )

        for fid in affected_faces:
            face = self._faces.get(fid)
            if face is None:
                continue
            if logged:
                self._touch_f(fid)
            new_boundary = [survivor if v == removed else v for v in face.boundary]
            # Doppelte, direkt aufeinanderfolgende Vertices entfernen
            # (entsteht z. B. wenn survivor und removed direkt benachbart waren).
            deduped: list[VertexId] = []
            for v in new_boundary:
                if not deduped or deduped[-1] != v:
                    deduped.append(v)
            if len(deduped) >= 2 and deduped[0] == deduped[-1]:
                deduped.pop()

            if len(deduped) < 3:
                self._delete_face(fid)
                continue

            self._faces[fid].boundary = deduped

        if uv_plan:
            for fid, corners in uv_plan.items():
                face = self._faces.get(fid)
                if face is not None:
                    self._write_uvs(fid, tuple(corners[v] for v in face.boundary))
        self._delete_vertex(removed)
        return survivor

    def _plan_collapse_uvs(self, survivor: VertexId, removed: VertexId, edge_faces) -> dict:
        """The corner maps every face around `survivor` / `removed` has after `collapse_edge`
        (its docstring), read before the first mutation."""
        mids = []
        for f in edge_faces:
            corners = self._corner_map(f)
            if corners is not None:
                a, b = corners[survivor], corners[removed]
                mids.append((f, a, b, ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)))
        mid_of = {f: m for f, _a, _b, m in mids}
        faces = {
            f for x in (survivor, removed) for eid in self._vertex_edges.get(x, ()) for f in self._edges[eid].faces
        }
        plan = {}
        for f in faces:
            corners = self._corner_map(f)
            if corners is None:
                continue
            if f in mid_of:
                corners[survivor] = mid_of[f]
            else:
                key = removed if removed in corners else survivor
                uv = corners[key]
                for _f, a, b, m in mids:
                    if same_uv(uv, b if key == removed else a):
                        uv = m
                        break
                corners[survivor] = uv
            corners.pop(removed, None)
            plan[f] = corners
        return plan

    def _remove_face_edges_only(self, face_id: FaceId) -> None:
        face = self._faces[face_id]
        logged = bool(self._logs)
        n = len(face.boundary)
        for i in range(n):
            v_a, v_b = face.boundary[i], face.boundary[(i + 1) % n]
            key = frozenset((v_a, v_b))
            eid = self._edge_lookup.get(key)
            if eid is not None and face_id in self._edges[eid].faces:
                if logged:
                    self._touch_e(eid)
                self._edges[eid].faces.remove(face_id)

    def _delete_face(self, face_id: FaceId) -> None:
        """Entfernt eine Face und ihre Einträge in den Edge-Face-Listen; Edges bleiben."""
        if self._logs:
            self._touch_f(face_id)
        if face_id in self._face_uvs:
            self._write_uvs(face_id, None)
        self._remove_face_edges_only(face_id)
        del self._faces[face_id]

    def _delete_vertex(self, vertex_id: VertexId) -> None:
        """Entfernt einen Vertex, an dem keine Edge mehr hängt (samt seinen Layer-Werten, L1)."""
        if self._logs:
            self._touch_v(vertex_id)
        del self._vertices[vertex_id]
        self._vertex_edges.pop(vertex_id, None)
        for lid, values in self._layer_values.items():
            if vertex_id in values:
                self._write_value(lid, vertex_id, None)

    def connect_vertices(self, face_id: FaceId, v_a: VertexId, v_b: VertexId) -> tuple[EdgeId, FaceId, FaceId]:
        """Teilt eine Face entlang zweier ihrer Boundary-Vertices.

        ID-Kontinuität:
        - die ursprüngliche FaceId wird ungültig.
        - es entstehen zwei neue FaceIds und eine neue EdgeId.
        - alle beteiligten VertexIds bleiben unverändert.
        - alle unberührten Edges der ursprünglichen Face bleiben gültig.
        """
        face = self._faces[face_id]
        boundary = face.boundary
        if v_a not in boundary or v_b not in boundary:
            raise MeshError("Beide Vertices müssen auf der Face-Boundary liegen.")
        if v_a == v_b:
            raise MeshError("connect_vertices benötigt zwei unterschiedliche Vertices.")

        i_a = boundary.index(v_a)
        i_b = boundary.index(v_b)
        if i_a > i_b:
            i_a, i_b = i_b, i_a

        loop_1 = boundary[i_a:i_b + 1]
        loop_2 = boundary[i_b:] + boundary[:i_a + 1]

        if len(loop_1) < 3 or len(loop_2) < 3:
            raise MeshError("connect_vertices würde eine degenerierte Face erzeugen.")
        # UVs (AD-026): beide Teil-Faces übernehmen die Ecken der Parent-Face.
        corners = self._corner_map(face_id)

        # alte Face-Referenzen der bestehenden Edges entfernen
        self._delete_face(face_id)

        uvs_1 = None if corners is None else [corners[v] for v in loop_1]
        uvs_2 = None if corners is None else [corners[v] for v in loop_2]
        new_face_1 = self.add_face(loop_1, uvs_1, infer_uvs=False)
        new_face_2 = self.add_face(loop_2, uvs_2, infer_uvs=False)
        new_edge = self._edge_lookup[frozenset((v_a, v_b))]

        return new_edge, new_face_1, new_face_2

    def split_face(
        self,
        face_id: FaceId,
        v_a: VertexId,
        v_b: VertexId,
        positions: Sequence[Position] = (),
        origins: Sequence[VertexOrigin] | None = None,
    ) -> tuple[list[VertexId], list[EdgeId], FaceId, FaceId]:
        """Teilt eine Face entlang eines Pfads v_a -> positions... -> v_b
        (AD-017 B2c / K1, Addendum 2026-10-01 in
        AD-017_FINAL_DECISIONS_2026-09-22.md - dort der akzeptierte Vertrag).

        `positions` sind die k inneren Pfadpunkte in Reihenfolge v_a -> v_b;
        für jeden entsteht ein neuer Vertex an genau dieser Position. Keine
        Geometrieprüfung (wie connect_vertices): ob der Pfad in der Face liegt,
        sich kreuzt oder die Teil-Faces flippt, ist Sache des Aufrufers.

        Vorbedingungen (jede Verletzung -> MeshError, Mesh inkl. Allocator-
        Zählerständen unverändert - alles wird vor der ersten Mutation geprüft):
        - face_id gültig, Boundary ohne doppelte Vertices.
        - v_a != v_b, beide auf der Boundary von face_id.
        - beide entstehenden Faces haben >= 3 Vertices. Bei k = 0 heißt das wie
          bei connect_vertices: benachbarte Enden werden abgelehnt; ab k >= 1
          sind benachbarte Enden erlaubt (Notch).
        - jede Position ist ein 3-Tupel.
        - `origins` (AD-025 §4.1, Phase 5): None oder genau eine `VertexOrigin` pro Position, in
          derselben Reihenfolge (Quellen: lebende Vertices, z. B. die Ecken der Parent-Face, die
          split_face nie löscht). Auf einem Mesh mit Punkt-Layern ist sie für k >= 1 Pflicht; jede
          Herkunft wird wie bei add_vertex geprüft und auf jeden Layer angewendet. Ohne Layer wird
          sie nur auf ihre Länge geprüft und sonst ignoriert.
        - k = 0 und v_a-v_b ist bereits Edge einer anderen Face: abgelehnt
          (das Ergebnis hätte eine Edge mit mehr als zwei Faces). Das ist der
          einzige Fall, in dem split_face(k = 0) ablehnt, wo connect_vertices
          weiterlaufen würde; in allen anderen Fällen ist positions == ()
          bit-identisch zu connect_vertices (gleiche Faces, gleiche IDs).

        ID-Kontinuität (AD-001):
        - face_id wird ungültig.
        - k neue VertexIds, in Pfadreihenfolge v_a -> v_b.
        - k + 1 neue EdgeIds, in Pfadreihenfolge v_a -> v_b. Einzige Ausnahme
          (wie connect_vertices): bei k = 0 wird eine bereits bestehende freie
          Edge v_a-v_b wiederverwendet statt neu erzeugt.
        - zwei neue FaceIds, face_1 vor face_2. Sei s das Ende mit dem
          kleineren Index in face_vertices(face_id), e das andere:
          face_1 = Boundary s .. e vorwärts, zurück über den Pfad e -> s;
          face_2 = Boundary e .. s vorwärts (über das Listenende), weiter über
          den Pfad s -> e. Für v_a vor v_b ist face_1 also die Seite, die
          v_a -> v_b in Boundary-Reihenfolge läuft; für v_b vor v_a dieselbe
          Vertauschung wie in connect_vertices. Damit hängen die beiden Faces
          (und ihre Reihenfolge) nicht von der Argumentreihenfolge ab, nur die
          Vertex-/Edge-IDs des Pfads folgen v_a -> v_b.
        - alle Boundary-Vertices und alle Boundary-Edges behalten ihre IDs;
          es wird keine Edge entfernt.
        - Winding: beide Faces laufen wie die Parent-Face.

        Provenance-Hook (ARCH-02), kein Register: Eingabe + Rückgabe enthalten
        Parent-Face, die neuen Vertices mit ihren Erzeugungspositionen, die
        Pfad-Edges und beide Seiten. Eine spätere Provenance-Schicht kann
        daraus lesen: jeder neue Vertex ist ein Innenpunkt von face_id (nicht
        Teil einer Edge), jede Pfad-Edge trennt face_1 von face_2, und jede
        Boundary-Edge von face_id gehört danach zu genau einer der beiden.

        UVs (AD-026): beide Faces übernehmen die Ecken der Parent-Face; ein Innenpunkt bekommt
        die UVs seiner Mean-Value-Koordinaten über die Parent-Face (`corner_uvs.polygon_weights`) -
        immer, auch mit `origins`, damit ein Mesh mit Punkt-Layern genauso schneidet wie eins ohne.

        Rückgabe: (neue_vertex_ids, neue_edge_ids, face_1, face_2)
        """
        face = self._faces.get(face_id)
        if face is None:
            raise MeshError(f"split_face: unbekannte Face {face_id!r}")
        boundary = face.boundary
        if len(set(boundary)) != len(boundary):
            raise MeshError("split_face: Face-Boundary enthält doppelte Vertices.")
        if v_a == v_b:
            raise MeshError("split_face benötigt zwei unterschiedliche Vertices.")
        if v_a not in boundary or v_b not in boundary:
            raise MeshError("Beide Vertices müssen auf der Face-Boundary liegen.")
        try:
            positions = [tuple(p) for p in positions]
        except TypeError:
            raise MeshError("split_face: positions muss eine Folge von 3-Tupeln sein.") from None
        if any(len(p) != 3 for p in positions):
            raise MeshError("split_face: jede Position braucht genau 3 Koordinaten.")
        k = len(positions)

        i_a = boundary.index(v_a)
        i_b = boundary.index(v_b)
        a_first = i_a < i_b
        i_s, i_e = (i_a, i_b) if a_first else (i_b, i_a)
        arc_1 = boundary[i_s:i_e + 1]
        arc_2 = boundary[i_e:] + boundary[:i_s + 1]
        if len(arc_1) + k < 3 or len(arc_2) + k < 3:
            raise MeshError("split_face würde eine degenerierte Face erzeugen.")
        if k == 0:
            existing = self._edge_lookup.get(frozenset((v_a, v_b)))
            if existing is not None and self._edges[existing].faces:
                raise MeshError("split_face: v_a-v_b ist bereits Edge einer anderen Face.")
        if origins is not None:
            origins = list(origins)
            if len(origins) != k:
                raise MeshError("split_face: origins braucht genau eine Herkunft pro Position.")
        layer_values = None
        if k and self._layer_meta:
            # AD-025 §4.1 (Phase 5): the Knife passes each interior point's origin (barycentric weights
            # of its hit triangle over the original face's corners); validated and combined before the
            # first mutation, so a refusal leaves the mesh and the counters unchanged.
            if origins is None:
                raise MeshError("split_face: Innenpunkte auf einem Mesh mit Punkt-Layern brauchen eine Herkunft (origins).")
            layer_values = [self._origin_values(o) for o in origins]
        corners = self._corner_map(face_id)
        if corners is not None and k:
            interior_uvs = self._interior_uvs(boundary, corners, positions)

        self._delete_face(face_id)

        new_vertices = [self._new_vertex(p) for p in positions]
        if layer_values is not None:
            for vid, values in zip(new_vertices, layer_values):
                for lid, value in values:
                    self._write_value(lid, vid, value)
        chain = [v_a, *new_vertices, v_b]
        # Endpunkte jeder Pfad-Edge so, wie face_1 sie durchläuft (e -> s) -
        # bei k = 0 genau die Edge, die connect_vertices über add_face(loop_1)
        # anlegen würde. Die Edge-Richtung selbst ist nicht semantisch.
        new_edges = [
            self._get_or_create_edge(w, u) if a_first else self._get_or_create_edge(u, w)
            for u, w in zip(chain, chain[1:])
        ]
        interior_s_to_e = new_vertices if a_first else new_vertices[::-1]

        boundary_1 = arc_1 + interior_s_to_e[::-1]
        boundary_2 = arc_2 + interior_s_to_e
        uvs_1 = uvs_2 = None
        if corners is not None:
            if k:
                corners.update(zip(new_vertices, interior_uvs))
            uvs_1 = [corners[v] for v in boundary_1]
            uvs_2 = [corners[v] for v in boundary_2]
        face_1 = self.add_face(boundary_1, uvs_1, infer_uvs=False)
        face_2 = self.add_face(boundary_2, uvs_2, infer_uvs=False)
        return new_vertices, new_edges, face_1, face_2

    def _interior_uvs(self, boundary, corners: dict, positions) -> list[UV]:
        """UVs of `split_face`'s interior points (its docstring), before the first mutation."""
        corner_positions = [self._vertices[v].position for v in boundary]
        corner_uvs = [corners[v] for v in boundary]
        return [weighted_uv(polygon_weights(corner_positions, p), corner_uvs) for p in positions]

    # ------------------------------------------------------------------
    # Entfernen: Dissolve (bewahrend) und Delete (destruktiv) -
    # WP Delete/Dissolve (docs/WP_DELETE_DISSOLVE_PLAN.md). Gemeinsamer
    # Vertrag aller fünf Methoden: jede Vorbedingung wird vor der ersten
    # Mutation geprüft; bei MeshError bleibt das Mesh inkl. Allocator-
    # Zählerständen unverändert. Die Symmetry Definition wird nicht
    # angefasst (wie bei split_edge; Symmetrie-Verhalten ist nicht Teil
    # dieses Pakets).
    # ------------------------------------------------------------------

    def dissolve_vertex(self, vertex_id: VertexId) -> FaceId | None:
        """Entfernt einen Vertex, ohne ein Loch zu hinterlassen.

        Eine Operation, keine Cleanup-Variante (WP Delete/Dissolve §0.2.2).
        Zwei Fälle, nach Anzahl der anliegenden Edges (Valenz):
        - Valenz 2 (2er-Vertex, z. B. nach split_edge): der Vertex wird aus
          jeder anliegenden Face entfernt, seine beiden Edges a-v, v-b werden
          durch eine Edge a-b ersetzt; die Faces bleiben getrennt (Umkehrung
          von split_edge, bis auf die neue EdgeId). Rückgabe None.
        - Valenz >= 3: alle anliegenden Faces verschmelzen zu einer Face
          (N-Gon), alle Spoke-Edges verschwinden. Liegt der Vertex auf einem
          offenen Rand (offener Fan), werden die beiden Rand-Spokes a-v, v-b
          durch eine Rand-Edge a-b ersetzt. Rückgabe: die neue Face.

        Vorbedingungen (Verletzung -> MeshError):
        - vertex_id gültig, Valenz >= 2.
        - bei Valenz >= 3: jede anliegende Edge hat mindestens eine Face, und
          die anliegenden Faces bilden einen einzigen Fan (kein Bowtie).
        - die Ersatz-Edge a-b existiert noch nicht, und keine Face fällt unter
          3 Vertices (z. B. 2er-Vertex eines Dreiecks).

        ID-Kontinuität (AD-001):
        - vertex_id wird ungültig, ebenso alle anliegenden Edges.
        - Valenz 2: eine neue EdgeId (a-b); anliegende Faces behalten ihre
          FaceId, ihre Boundary verliert den Vertex.
        - Valenz >= 3: alle anliegenden FaceIds werden ungültig, genau eine
          neue FaceId entsteht; bei offenem Fan zusätzlich eine neue EdgeId
          (a-b). Die äußeren Edges des Fans behalten ihre IDs.
        - alle übrigen IDs bleiben unverändert. Nachbar-Vertices, die dadurch
          selbst zu 2er-Vertices werden (Würfel-Ecke), bleiben stehen.
        """
        if not self.is_valid_vertex(vertex_id):
            raise MeshError(f"dissolve_vertex: unbekannter Vertex {vertex_id!r}")
        edges = self.vertex_edges(vertex_id)
        if len(edges) < 2:
            raise MeshError(
                "dissolve_vertex: Vertex hat weniger als zwei Edges - nichts zu verschmelzen."
            )
        if len(edges) == 2:
            plan = self._plan_dissolve([], cleanup=False, forced=(vertex_id,))
            self._apply_dissolve(plan)
            return None
        if any(not self._edges[e].faces for e in edges):
            raise MeshError("dissolve_vertex: Vertex hat eine Edge ohne Face (Wire).")
        fan = {f for e in edges for f in self._edges[e].faces}
        if len(self._components(fan, set(edges))) != 1:
            raise MeshError("dissolve_vertex: anliegende Faces bilden keinen einzelnen Fan.")
        plan = self._plan_dissolve([fan], cleanup=False, forced=(vertex_id,))
        (face,) = self._apply_dissolve(plan)
        return face

    def dissolve_edges(self, edge_ids: Sequence[EdgeId], *, cleanup: bool) -> list[FaceId]:
        """Entfernt Edges, ohne ein Loch zu hinterlassen: die beiden Faces an
        jeder Edge verschmelzen.

        Faces, die über ausgewählte Edges zusammenhängen, bilden eine Region
        und verschmelzen gemeinsam zu einer Face (eine Edge: genau ihre beiden
        Faces). Atomar über die ganze Auswahl, weil der Cleanup einer
        einzelnen Edge Endpunkte entfernen kann, an denen die nächste
        ausgewählte Edge hängt (zwei Edges an einer Würfel-Ecke).

        Mit verschwinden alle Edges, deren beide Faces in derselben Region
        liegen (z. B. eine Kette über einen 2er-Vertex zwischen denselben zwei
        Faces - sonst entstünde eine Face mit doppeltem Vertex), und Vertices,
        die dadurch keine Edge mehr haben.

        `cleanup` (keyword-only, bewusst ohne Default - die Wahl ist eine
        Bindungs-, keine Core-Entscheidung, WP Delete/Dissolve §0.2.2):
        - True: jeder Endpunkt einer aufgelösten Edge, der danach genau zwei
          Edges hat, wird entfernt (seine beiden Edges werden zu einer).
          Ausgenommen bleibt eine 2er-Kette, deren Ersatz-Edge schon existiert
          oder deren Entfernen eine Face unter 3 Vertices drücken würde - sie
          bleibt stehen, ohne Fehler.
        - False: solche 2er-Vertices bleiben stehen.

        Vorbedingungen (Verletzung -> MeshError): jede Edge gültig und an
        genau zwei Faces; jede Region hat genau einen einfachen Rand (kein
        Loch, keine Selbstberührung in einem Vertex) und konsistente
        Orientierung. Leere Auswahl -> No-op, Rückgabe [].

        ID-Kontinuität (AD-001):
        - die Faces jeder Region werden ungültig; pro Region entsteht genau
          eine neue FaceId (Rückgabe, Regionen nach kleinster FaceId geordnet).
        - aufgelöste Edges und dadurch kantenlose Vertices werden ungültig.
        - cleanup=True: jeder entfernte 2er-Vertex und seine beiden Edges
          werden ungültig; pro entfernter Kette entsteht eine neue EdgeId;
          die Nachbar-Face an der Kette behält ihre FaceId, ihre Boundary
          verliert die Vertices.
        - alle übrigen IDs bleiben unverändert; die Rand-Edges einer Region
          behalten ihre IDs.
        - Winding: die neue Face läuft wie die Faces der Region.
        """
        selected = set(edge_ids)
        for eid in selected:
            if not self.is_valid_edge(eid):
                raise MeshError(f"dissolve_edges: unbekannte Edge {eid!r}")
            if len(self._edges[eid].faces) != 2:
                raise MeshError(
                    "dissolve_edges: Edge liegt nicht zwischen zwei Faces - nichts zu verschmelzen."
                )
        faces = {f for e in selected for f in self._edges[e].faces}
        regions = self._components(faces, selected)
        plan = self._plan_dissolve(regions, cleanup=cleanup)
        return self._apply_dissolve(plan)

    def dissolve_faces(self, face_ids: Sequence[FaceId], *, cleanup: bool) -> list[FaceId]:
        """Verschmilzt zusammenhängende Faces zu je einer Face (Innenkanten weg).

        Zusammenhang über gemeinsame Edges; jede Zusammenhangskomponente mit
        mindestens zwei Faces verschmilzt für sich. Eine Face ohne Nachbarn in
        der Auswahl bleibt unverändert (kein Fehler); besteht die Auswahl nur
        aus solchen (oder ist leer), ist der Aufruf ein No-op (Rückgabe []).

        Innenkanten = Edges, deren beide Faces in derselben Komponente liegen;
        sie verschwinden, ebenso Vertices, die dadurch keine Edge mehr haben.
        `cleanup` wie bei dissolve_edges (keyword-only, ohne Default):
        Endpunkte der Innenkanten, die danach genau zwei Edges haben, werden
        entfernt (True) oder bleiben stehen (False).

        Vorbedingungen (Verletzung -> MeshError): jede FaceId gültig; jede
        verschmelzende Komponente hat genau einen einfachen Rand (kein Loch,
        keine Selbstberührung in einem Vertex) und konsistente Orientierung.

        ID-Kontinuität: wie dissolve_edges - die Faces jeder verschmelzenden
        Komponente werden ungültig, pro Komponente eine neue FaceId (Rückgabe,
        nach kleinster FaceId geordnet); Innenkanten und kantenlose Vertices
        ungültig; Cleanup wie dort; alle übrigen IDs unverändert.
        """
        selected = set(face_ids)
        for fid in selected:
            if not self.is_valid_face(fid):
                raise MeshError(f"dissolve_faces: unbekannte Face {fid!r}")
        shared = {
            e for f in selected for e in self.face_edges(f)
            if len(self._edges[e].faces) == 2 and set(self._edges[e].faces) <= selected
        }
        regions = [c for c in self._components(selected, shared) if len(c) >= 2]
        plan = self._plan_dissolve(regions, cleanup=cleanup)
        return self._apply_dissolve(plan)

    def delete_faces(self, face_ids: Sequence[FaceId]) -> None:
        """Entfernt Faces destruktiv (Loch) samt allem, was danach frei in der
        Luft hinge (WP Delete/Dissolve §0.2.3, präzisiert Manu 2026-10-06).

        Mit entfernt wird jede Edge der entfernten Faces, an der danach keine
        Face mehr hängt - innere Edges der Region ebenso wie frühere Mesh-
        Rand-Edges -, und jeder Vertex, der dadurch keine Edge mehr hat. Edges,
        die noch von einer verbleibenden Face genutzt werden, bleiben mit
        unveränderter ID als Lochrand stehen. Anders als remove_face, das
        Edges bewusst stehen lässt (V1-Primitive, unverändert). Leere Auswahl
        -> No-op.

        Vorbedingung: jede FaceId gültig (sonst MeshError, Mesh unverändert).

        ID-Kontinuität: die FaceIds, die face-los gewordenen EdgeIds und die
        kantenlos gewordenen VertexIds werden ungültig; es entstehen keine
        neuen IDs; alle übrigen IDs und alle verbleibenden Face-Boundaries
        bleiben unverändert.
        """
        for fid in face_ids:
            if not self.is_valid_face(fid):
                raise MeshError(f"delete_faces: unbekannte Face {fid!r}")
        self._delete_region(set(face_ids), set(), set())

    def delete_edges(self, edge_ids: Sequence[EdgeId]) -> None:
        """Entfernt Edges destruktiv: die Edge selbst und ihre (bis zu zwei)
        Faces, danach wie delete_faces (face-los gewordene Edges und kantenlos
        gewordene Vertices mit). Eine Edge ohne Face wird einfach entfernt.
        Leere Auswahl -> No-op.

        Vorbedingung: jede EdgeId gültig (sonst MeshError, Mesh unverändert).

        ID-Kontinuität: die EdgeIds, die FaceIds ihrer Faces, die face-los
        gewordenen EdgeIds und die kantenlos gewordenen VertexIds werden
        ungültig; keine neuen IDs; alles Übrige unverändert.
        """
        for eid in edge_ids:
            if not self.is_valid_edge(eid):
                raise MeshError(f"delete_edges: unbekannte Edge {eid!r}")
        edges = set(edge_ids)
        self._delete_region({f for e in edges for f in self._edges[e].faces}, edges, set())

    def delete_vertices(self, vertex_ids: Sequence[VertexId]) -> None:
        """Entfernt Vertices destruktiv: den Vertex, zwingend alle anliegenden
        Edges und Faces (eine Edge kann nicht mit einem Endpunkt existieren),
        danach wie delete_faces (face-los gewordene Edges und kantenlos
        gewordene Vertices mit). Äußere Edges des 1-Rings bleiben nur, wenn
        sie noch an einer anderen Face hängen. Leere Auswahl -> No-op.

        Vorbedingung: jede VertexId gültig (sonst MeshError, Mesh unverändert).

        ID-Kontinuität: die VertexIds, alle anliegenden EdgeIds und FaceIds,
        die face-los gewordenen EdgeIds und die kantenlos gewordenen
        VertexIds werden ungültig; keine neuen IDs; alles Übrige unverändert.
        """
        for vid in vertex_ids:
            if not self.is_valid_vertex(vid):
                raise MeshError(f"delete_vertices: unbekannter Vertex {vid!r}")
        vertices = set(vertex_ids)
        edges = {e for v in vertices for e in self.vertex_edges(v)}
        faces = {f for e in edges for f in self._edges[e].faces}
        self._delete_region(faces, edges, vertices)

    # -- interne Bausteine für Dissolve/Delete -------------------------------

    def _components(self, faces: set[FaceId], via: set[EdgeId]) -> list[set[FaceId]]:
        """Zusammenhangskomponenten von `faces`, verbunden über Edges aus
        `via`, geordnet nach kleinster FaceId."""
        remaining = set(faces)
        components = []
        while remaining:
            start = min(remaining, key=int)
            remaining.discard(start)
            component, stack = {start}, [start]
            while stack:
                fid = stack.pop()
                for eid in self.face_edges(fid):
                    if eid not in via:
                        continue
                    for other in self._edges[eid].faces:
                        if other in remaining:
                            remaining.discard(other)
                            component.add(other)
                            stack.append(other)
            components.append(component)
        return components

    def _region_outline(
        self, region: set[FaceId]
    ) -> tuple[list[VertexId], set[EdgeId], set[VertexId]]:
        """Rand einer Face-Region als eine geordnete Boundary, plus Innenkanten
        und Innen-Vertices. Rein lesend; MeshError, wenn die Region keine
        einfache Scheibe ist."""
        directions: dict[EdgeId, set[tuple[VertexId, VertexId]]] = {}
        interior: set[EdgeId] = set()
        step: dict[VertexId, VertexId] = {}
        starts: list[VertexId] = []
        region_vertices: set[VertexId] = set()
        for fid in sorted(region, key=int):
            boundary = self._faces[fid].boundary
            region_vertices.update(boundary)
            n = len(boundary)
            for i in range(n):
                u, w = boundary[i], boundary[(i + 1) % n]
                eid = self._edge_lookup[frozenset((u, w))]
                adjacent = self._edges[eid].faces
                if len(adjacent) == 2 and all(f in region for f in adjacent):
                    interior.add(eid)
                    directions.setdefault(eid, set()).add((u, w))
                    continue
                if u in step:
                    raise MeshError("Region berührt sich selbst in einem Vertex.")
                step[u] = w
                starts.append(u)
        for eid in interior:
            if len(directions[eid]) != 2:
                raise MeshError("Region ist nicht konsistent orientiert.")
        if not starts:
            raise MeshError("Region hat keinen Rand.")
        outline = [starts[0]]
        current = step[starts[0]]
        while current != starts[0]:
            if current not in step or len(outline) > len(step):
                raise MeshError("Region-Rand ist nicht geschlossen.")
            outline.append(current)
            current = step[current]
        if len(outline) != len(step):
            raise MeshError("Region hat mehr als einen Rand (Loch).")
        if len(outline) < 3:
            raise MeshError("Region würde eine degenerierte Face ergeben.")
        inner_vertices = region_vertices - set(outline)
        for vid in inner_vertices:
            if any(e not in interior for e in self.vertex_edges(vid)):
                raise MeshError("Innen-Vertex der Region hat eine Edge nach außen.")
        return outline, interior, inner_vertices

    def _plan_dissolve(
        self,
        regions: list[set[FaceId]],
        *,
        cleanup: bool,
        forced: Sequence[VertexId] = (),
    ) -> dict:
        """Berechnet das Ergebnis eines Dissolve rein lesend: jede Region
        verschmilzt zu einer Face; danach werden 2er-Vertices entfernt -
        `forced` zwingend (MeshError, wenn nicht möglich), bei `cleanup` die
        Endpunkte der aufgelösten Edges, soweit möglich."""
        removed_faces = [f for region in regions for f in sorted(region, key=int)]
        removed_edges: set[EdgeId] = set()
        removed_vertices: set[VertexId] = set()
        merged: list[list[VertexId]] = []
        for region in regions:
            outline, interior, inner_vertices = self._region_outline(region)
            merged.append(outline)
            removed_edges |= interior
            removed_vertices |= inner_vertices

        candidates = set(forced)
        if cleanup:
            candidates |= {v for e in removed_edges for v in self.edge_vertices(e)}
        candidates -= removed_vertices
        removed_face_set = set(removed_faces)

        def remaining_edges(vid: VertexId) -> list[EdgeId]:
            return [e for e in self.vertex_edges(vid) if e not in removed_edges]

        chain = {v for v in candidates if len(remaining_edges(v)) == 2}
        for vid in forced:
            if vid not in removed_vertices and vid not in chain:
                raise MeshError("Vertex hätte danach nicht genau zwei Edges.")

        # Faces nach dem Verschmelzen: neue (Index in `merged`) und bestehende.
        boundaries: dict[object, list[VertexId]] = {("new", i): b for i, b in enumerate(merged)}
        for vid in chain:
            for eid in remaining_edges(vid):
                for fid in self._edges[eid].faces:
                    if fid not in removed_face_set:
                        boundaries[fid] = self._faces[fid].boundary

        wire_edges: list[tuple[VertexId, VertexId]] = []
        while True:
            dropped: set[VertexId] = set()
            # Ersatz-Edge -> (Faces, die sie tragen würden; Ketten-Vertices).
            new_pairs: dict[frozenset, tuple[set, set[VertexId]]] = {}
            for key, boundary in boundaries.items():
                hits = [v for v in boundary if v in chain]
                if not hits:
                    continue
                if len(boundary) - len(hits) < 3:
                    dropped |= set(hits)
                    continue
                for pair, run in self._chain_runs(boundary, chain):
                    if pair[0] == pair[1] or self._pair_exists(pair, removed_edges):
                        dropped |= run
                        continue
                    owners, runs = new_pairs.setdefault(frozenset(pair), (set(), set()))
                    owners.add(key)
                    runs |= run
            for owners, runs in new_pairs.values():
                if len(owners) > 2:
                    dropped |= runs
            # 2er-Vertex ohne Face (Wire-Kette, nur über `forced` erreichbar).
            wire_edges = []
            for vid in sorted(chain - dropped, key=int):
                ends = [self._other_end(e, vid) for e in remaining_edges(vid)]
                in_face = any(
                    f not in removed_face_set
                    for e in remaining_edges(vid) for f in self._edges[e].faces
                ) or any(vid in b for b in merged)
                if in_face:
                    continue
                pair = (ends[0], ends[1])
                if ends[0] == ends[1] or ends[0] in chain or ends[1] in chain \
                        or self._pair_exists(pair, removed_edges):
                    dropped.add(vid)
                else:
                    wire_edges.append(pair)
            if not dropped:
                break
            if dropped & set(forced):
                raise MeshError(
                    "Vertex lässt sich nicht entfernen (Ersatz-Edge existiert schon oder "
                    "eine Face fiele unter 3 Vertices)."
                )
            chain -= dropped

        for vid in chain:
            removed_edges |= set(remaining_edges(vid))
        removed_vertices |= chain
        updated = {
            key: [v for v in b if v not in chain]
            for key, b in boundaries.items() if any(v in chain for v in b)
        }
        return {
            "removed_faces": removed_faces,
            "removed_edges": removed_edges,
            "removed_vertices": removed_vertices,
            "merged": [updated.get(("new", i), b) for i, b in enumerate(merged)],
            "outlines": merged,
            "updated": {k: b for k, b in updated.items() if not isinstance(k, tuple)},
            "wire_edges": wire_edges,
        }

    @staticmethod
    def _chain_runs(
        boundary: list[VertexId], chain: set[VertexId]
    ) -> list[tuple[tuple[VertexId, VertexId], set[VertexId]]]:
        """Läufe aufeinanderfolgender `chain`-Vertices einer zyklischen
        Boundary als ((Vorgänger, Nachfolger), Lauf). Setzt voraus, dass
        mindestens ein Vertex nicht in `chain` liegt."""
        n = len(boundary)
        first = next(i for i, v in enumerate(boundary) if v not in chain)
        rotated = boundary[first:] + boundary[:first]
        runs = []
        i = 0
        while i < n:
            if rotated[i] in chain:
                j = i
                while rotated[j % n] in chain:
                    j += 1
                runs.append(((rotated[i - 1], rotated[j % n]), set(rotated[i:j])))
                i = j
            else:
                i += 1
        return runs

    def _pair_exists(self, pair: tuple[VertexId, VertexId], removed: set[EdgeId]) -> bool:
        eid = self._edge_lookup.get(frozenset(pair))
        return eid is not None and eid not in removed

    def _other_end(self, edge_id: EdgeId, vertex_id: VertexId) -> VertexId:
        e = self._edges[edge_id]
        return e.v1 if e.v0 == vertex_id else e.v0

    def _apply_dissolve(self, plan: dict) -> list[FaceId]:
        """Wendet einen `_plan_dissolve`-Plan an (keine Prüfungen mehr).

        UVs (AD-026): eine verschmolzene Face nimmt an jeder Ecke den Wert der alten Face, die die
        Rand-Edge ab dieser Ecke trug (exakt, auch an Nähten); eine Face, die nur Ketten-Vertices
        verliert, behält die Werte ihrer übrigen Ecken."""
        merged_uvs = updated_uvs = None
        if self._face_uvs:
            merged_uvs, updated_uvs = self._plan_dissolve_uvs(plan)
        for fid in plan["removed_faces"]:
            self._delete_face(fid)
        logged = bool(self._logs)
        for fid, boundary in plan["updated"].items():
            if logged:
                self._touch_f(fid)
            self._faces[fid].boundary = boundary
            if updated_uvs is not None and fid in updated_uvs:
                self._write_uvs(fid, updated_uvs[fid])
        for eid in plan["removed_edges"]:
            if logged:
                self._touch_e(eid)
            self._pop_edge(eid)
        for vid in plan["removed_vertices"]:
            self._delete_vertex(vid)
        if merged_uvs is None:
            new_faces = [self.add_face(boundary) for boundary in plan["merged"]]
        else:
            new_faces = [
                self.add_face(boundary, uvs, infer_uvs=False)
                for boundary, uvs in zip(plan["merged"], merged_uvs)
            ]
        for fid in sorted(plan["updated"], key=int):
            boundary = self._faces[fid].boundary
            n = len(boundary)
            for i in range(n):
                eid = self._get_or_create_edge(boundary[i], boundary[(i + 1) % n])
                if fid not in self._edges[eid].faces:
                    if logged:
                        self._touch_e(eid)
                    self._edges[eid].faces.append(fid)
        for v_a, v_b in plan["wire_edges"]:
            self._get_or_create_edge(v_a, v_b)
        return new_faces

    def _plan_dissolve_uvs(self, plan: dict) -> tuple[list, dict]:
        """The UVs of `_apply_dissolve`'s merged and updated faces, read before the first mutation."""
        directed: dict[tuple[VertexId, VertexId], UV] = {}
        for fid in plan["removed_faces"]:
            uvs = self._face_uvs.get(fid)
            if uvs is None:
                continue
            boundary = self._faces[fid].boundary
            n = len(boundary)
            for i in range(n):
                directed[(boundary[i], boundary[(i + 1) % n])] = uvs[i]
        merged_uvs = []
        for outline, boundary in zip(plan["outlines"], plan["merged"]):
            n = len(outline)
            corners = {}
            for i in range(n):
                uv = directed.get((outline[i], outline[(i + 1) % n]))
                if uv is not None:
                    corners[outline[i]] = uv
            if len(corners) == n:
                merged_uvs.append(tuple(corners[v] for v in boundary))
            else:
                merged_uvs.append(None)  # a face of the region had no UVs: the merged face has none
        updated_uvs = {}
        for fid, boundary in plan["updated"].items():
            corners = self._corner_map(fid)
            if corners is not None:
                updated_uvs[fid] = tuple(corners[v] for v in boundary)
        return merged_uvs, updated_uvs

    def _delete_region(
        self, faces: set[FaceId], edges: set[EdgeId], vertices: set[VertexId]
    ) -> None:
        """Gemeinsamer Delete-Kern: entfernt `faces`, `edges`, `vertices`,
        dazu jede Edge der entfernten Faces, an der danach keine Face mehr
        hängt, und kantenlos gewordene Vertices. Aufrufer haben alle IDs
        bereits geprüft."""
        removed_edges = set(edges)
        for fid in faces:
            for eid in self.face_edges(fid):
                if all(f in faces for f in self._edges[eid].faces):
                    removed_edges.add(eid)
        touched = {v for e in removed_edges for v in self.edge_vertices(e)}
        index = self._vertex_edges
        keeps_edge = {
            v for v in touched if not removed_edges.issuperset(index.get(v, ()))
        }
        removed_vertices = set(vertices) | (touched - keeps_edge)
        for fid in faces:
            self._delete_face(fid)
        logged = bool(self._logs)
        for eid in removed_edges:
            if logged:
                self._touch_e(eid)
            self._pop_edge(eid)
        for vid in removed_vertices:
            self._delete_vertex(vid)

    # ------------------------------------------------------------------
    # Serialisierung (§8, §12) - bewusst hier statt in serialization.py,
    # weil nur Mesh selbst legitimen Zugriff auf seine internen Container
    # hat (Vertrag aus §15 Punkt 1: keine externe Abhängigkeit von
    # internen Mesh-Containern).
    # ------------------------------------------------------------------

    def export_state(self) -> dict:
        """Reine Datenstruktur, JSON-kompatibel. Enthält auch die
        Allocator-Zählerstände, damit künftig neu erzeugte IDs nach dem
        Laden nicht mit gespeicherten IDs kollidieren (§8).

        `"symmetry"` (AD-SYM-01): additiver, optionaler Schlüssel statt
        eines Formatversionssprungs - `None`, solange keine Symmetry
        Definition gesetzt ist (Default-Zustand). Dadurch bleibt
        `serialization.py`/`FORMAT_VERSION` unverändert: `scene_to_dict()`
        ruft bereits `mesh.export_state()` auf, der neue Schlüssel reist
        also ohne jede Änderung an der Scene-Hülle mit.
        """
        return {
            "vertex_id_counter": self._vertex_alloc.peek_next(),
            "edge_id_counter": self._edge_alloc.peek_next(),
            "face_id_counter": self._face_alloc.peek_next(),
            "vertices": {
                int(vid): list(data.position) for vid, data in self._vertices.items()
            },
            "edges": {
                int(eid): {
                    "v0": int(data.v0),
                    "v1": int(data.v1),
                    "faces": [int(f) for f in data.faces],
                }
                for eid, data in self._edges.items()
            },
            "faces": {
                int(fid): [int(v) for v in data.boundary]
                for fid, data in self._faces.items()
            },
            "symmetry": self._export_symmetry_definition(),
            "face_regions": self._export_face_regions(),
            "layer_id_counter": self._layer_alloc.peek_next(),
            "point_layers": self._export_point_layers(),
            "face_uvs": self._export_face_uvs(),
        }

    def _export_face_uvs(self) -> dict | None:
        """Additive key `"face_uvs"` (AD-026): None without UVs, else `{"<fid>": [[u, v], ...]}` in
        boundary order, face ids ascending (deterministic JSON text)."""
        if not self._face_uvs:
            return None
        return {int(fid): [list(uv) for uv in self._face_uvs[fid]] for fid in sorted(self._face_uvs)}

    def _export_point_layers(self, meta: tuple | None = None, values_of=None) -> list | None:
        """Additive key `"point_layers"` (AD-025 §4.2): None without layers (L5), else one entry
        per layer in display order, vertex IDs ascending (deterministic JSON text)."""
        meta = self._layer_meta if meta is None else meta
        if not meta:
            return None
        values_of = values_of or self._layer_values.__getitem__
        return [
            {
                "id": int(lid),
                "name": info.name,
                "kind": info.kind.value,
                "new_point": info.new_point,
                "values": {int(vid): list(value) for vid, value in sorted(values_of(lid).items())},
            }
            for lid, info in meta
        ]

    def _layers_at_start(self, change: MeshChange) -> list | None:
        """The `"point_layers"` export as it was at `begin_change` of the active `change` (for
        readers of a running recording, e.g. the Knife's `SessionStart.state()`)."""
        meta = self._layer_meta if change.layer_meta is _UNSET else change.layer_meta

        def values_of(lid):
            if lid in change.layer_whole:
                return _with_overlay(*change.layer_whole[lid]) or {}
            return _with_overlay(self._layer_values.get(lid, {}), change.layer_values.get(lid, {})) or {}

        return self._export_point_layers(meta, values_of)

    def _layers_unchanged_since(self, change: MeshChange) -> bool:
        """True when the layers are back to their state at `begin_change` of `change`."""
        if change.layer_meta is not _UNSET and change.layer_meta != self._layer_meta:
            return False
        for lid, records in change.layer_values.items():
            current = self._layer_values.get(lid, {})
            if any(current.get(vid) != before for vid, before in records.items()):
                return False
        return all(
            _with_overlay(old, overlay) == self._layer_values.get(lid)
            for lid, (old, overlay) in change.layer_whole.items()
        )

    def _export_face_regions(self) -> list | None:
        """Additiver Schlüssel `"face_regions"` (AD-REGIONS-01) wie `"symmetry"`: `None` ohne Regionen,
        sonst eine Liste `{"name", "faces"}` in Anzeigereihenfolge, FaceIds aufsteigend."""
        regions = self._face_regions
        if regions is None:
            return None
        return [
            {"name": r.name, "faces": [int(f) for f in sorted(r.faces)]} for r in regions.regions
        ]

    def _export_symmetry_definition(self) -> dict | None:
        definition = self.symmetry_definition
        if definition is None:
            return None
        return {
            "plane_point": list(definition.plane_point),
            "plane_normal": list(definition.plane_normal),
            "seam_edges": [int(eid) for eid in sorted(definition.seam_edges)],
        }

    def load_state(self, state: dict) -> None:
        """Ersetzt den kompletten Inhalt DIESES Mesh-Objekts durch `state`
        (wie von export_state() erzeugt) - IN-PLACE, im Unterschied zu
        from_state() (Classmethod), das ein NEUES Mesh-Objekt erzeugt.

        Grund für die In-Place-Variante: Scene/Selection/Viewport halten
        eine Referenz auf genau diese Mesh-Instanz. Ein Austausch des
        ganzen Objekts (wie from_state es tut) würde diese Referenzen
        ungültig machen. Wird für Undo/Redo von Topologie-Mutationen
        gebraucht (siehe MeshStateCommand in operations/topology.py,
        Hardening-Plan §17 Phase D).

        ID-Kontinuität (AD-001): Die Allocator-Zählerstände werden - wie
        bei from_state() - nur VORWÄRTS gesetzt (restore_counter()), NIE
        zurückgedreht. Das ist beim Undo bewusst so: eine einmal vergebene
        ID darf laut AD-001 innerhalb der Session nie wieder ausgegeben
        werden, auch nicht, nachdem ihr Element durch ein Undo wieder
        verschwunden ist. restore_counter() setzt den Zähler ohnehin nur
        vorwärts (siehe ids.py) - beim Undo (Zielzustand hat einen
        niedrigeren gespeicherten Zählerstand als aktuell) bleibt der
        Zähler deshalb unverändert auf dem höheren, aktuellen Wert.

        Symmetry Definition (AD-SYM-01): nimmt am selben In-Place-Vertrag
        teil wie Vertices/Edges/Faces - `state.get("symmetry")` statt
        `state["symmetry"]`, damit ein `state`-Dict ohne diesen Schlüssel
        (additiv, siehe export_state()) ebenfalls ladbar bleibt, statt mit
        KeyError abzubrechen.
        """
        vertex_records = {
            VertexId(int(vid_raw)): tuple(pos) for vid_raw, pos in state["vertices"].items()
        }
        # Validated whole before the first write: an invalid file leaves the mesh unchanged.
        layer_meta, layer_values = _parse_point_layers(state.get("point_layers"), vertex_records)
        edge_records = {
            EdgeId(int(eid_raw)): (
                VertexId(edata["v0"]), VertexId(edata["v1"]), tuple(FaceId(f) for f in edata["faces"])
            )
            for eid_raw, edata in state["edges"].items()
        }
        face_records = {
            FaceId(int(fid_raw)): tuple(VertexId(v) for v in boundary)
            for fid_raw, boundary in state["faces"].items()
        }
        face_uvs = _parse_face_uvs(state.get("face_uvs"), face_records)
        if self._logs:
            # Ein Journal läuft (Rollback eines Checkpoints, Undo, ein Viewport beobachtet):
            # nur die Elemente schreiben, die sich unterscheiden, damit es genau diese sieht.
            self._apply_records(
                self._differing(self._vertices, vertex_records, self._vertex_record),
                self._differing(self._edges, edge_records, self._edge_record),
                self._differing(self._faces, face_records, self._face_record),
            )
        else:
            self._vertices.clear()
            self._edges.clear()
            self._faces.clear()
            self._edge_lookup.clear()
            self._vertex_edges.clear()
            # Aufsteigend nach ID (Invariante, siehe __init__).
            for vid in sorted(vertex_records):
                self._vertices[vid] = _VertexData(position=vertex_records[vid])
            for eid in sorted(edge_records):
                v0, v1, faces = edge_records[eid]
                self._edges[eid] = _EdgeData(v0=v0, v1=v1, faces=list(faces))
                self._edge_lookup[frozenset((v0, v1))] = eid
                self._index_edge(eid, v0, v1)
            for fid in sorted(face_records):
                self._faces[fid] = _FaceData(boundary=list(face_records[fid]))

        self._vertex_alloc.restore_counter(state["vertex_id_counter"])
        self._edge_alloc.restore_counter(state["edge_id_counter"])
        self._face_alloc.restore_counter(state["face_id_counter"])
        self._layer_alloc.restore_counter(int(state.get("layer_id_counter", 1)))
        self._layer_alloc.restore_counter(max((int(lid) + 1 for lid, _ in layer_meta), default=1))
        self._load_point_layers(layer_meta, layer_values)
        if self._logs:
            self._apply_uv_records(
                {fid: uvs for fid, uvs in face_uvs.items() if self._face_uvs.get(fid) != uvs}
                | {fid: None for fid in self._face_uvs if fid not in face_uvs}
            )
        else:
            self._face_uvs = face_uvs

        symmetry_raw = state.get("symmetry")
        if symmetry_raw is None:
            definition = None
        else:
            definition = SymmetryDefinition(
                plane_point=tuple(symmetry_raw["plane_point"]),
                plane_normal=tuple(symmetry_raw["plane_normal"]),
                seam_edges=frozenset(EdgeId(eid) for eid in symmetry_raw["seam_edges"]),
            )
        if definition != self._symmetry_definition:
            self.symmetry_definition = definition

        regions_raw = state.get("face_regions")
        regions = None if not regions_raw else FaceRegions(
            tuple(
                FaceRegion(r["name"], frozenset(FaceId(f) for f in r["faces"])) for r in regions_raw
            )
        )
        if regions != self._face_regions:
            self.face_regions = regions

    def _load_point_layers(self, meta: tuple, values: dict) -> None:
        if not self._logs:
            self._layer_meta = meta
            self._layer_values = {lid: self._packed(v) for lid, v in values.items()}
            self._layer_shared = set()
            return
        # Under a journal: only what differs (whole-layer records for layers that appear or go).
        for lid in [lid for lid in self._layer_values if lid not in values]:
            self._bulk_set(lid, None, shared=False)
        if meta != self._layer_meta:
            self._set_layer_meta(meta)
        for lid, new in values.items():
            old = self._layer_values.get(lid)
            if old is None:
                self._bulk_set(lid, new, shared=False)
                continue
            for vid in [vid for vid in old if vid not in new]:
                self._write_value(lid, vid, None)
            for vid, value in new.items():
                if old.get(vid) != value:
                    self._write_value(lid, vid, value)

    # ------------------------------------------------------------------
    # Änderungs-Journal (AD-023 H1, CORE_V1_FREEZE §7.1 2026-10-21): Delta statt Snapshot
    # ------------------------------------------------------------------

    def begin_change(self) -> MeshChange:
        """Startet die Aufzeichnung einer Mutation. Abschluss mit genau einem von
        `end_change(change)` (-> MeshDelta) oder `rollback_change(change)`. Aufzeichnungen
        dürfen sich verschachteln (z. B. ein Knife-Checkpoint innerhalb der Knife-Session)."""
        change = MeshChange()
        self._logs.append(change)
        return change

    def end_change(self, change: MeshChange) -> MeshDelta:
        """Beendet die Aufzeichnung und liefert die Netto-Änderung: jedes berührte Element,
        dessen Record sich unterscheidet, als (vorher, nachher). Leer = nichts geändert."""
        self._stop(change)
        vertices = {}
        for vid, before in change.vertices.items():
            after = self._vertex_record(vid)
            if after != before:
                vertices[vid] = (before, after)
        edges = {}
        for eid, before in change.edges.items():
            after = self._edge_record(eid)
            if after != before:
                edges[eid] = (before, after)
        faces = {}
        for fid, before in change.faces.items():
            after = self._face_record(fid)
            if after != before:
                faces[fid] = (before, after)
        symmetry = None
        if change.symmetry is not _UNSET and change.symmetry != self._symmetry_definition:
            symmetry = (change.symmetry, self._symmetry_definition)
        regions = None
        if change.regions is not _UNSET and change.regions != self._face_regions:
            regions = (change.regions, self._face_regions)
        face_uvs = {}
        for fid, before in change.face_uvs.items():
            after = self._face_uvs.get(fid)
            if after != before:
                face_uvs[fid] = (before, after)
        if not change.layers_touched:
            return MeshDelta(vertices, edges, faces, symmetry, regions, face_uvs=face_uvs)
        layer_meta = None
        if change.layer_meta is not _UNSET and change.layer_meta != self._layer_meta:
            layer_meta = (change.layer_meta, self._layer_meta)
        layer_values = {}
        for lid, records in change.layer_values.items():
            current = self._layer_values.get(lid, {})
            pairs = {
                vid: (before, current.get(vid))
                for vid, before in records.items()
                if current.get(vid) != before
            }
            if pairs:
                layer_values[lid] = pairs
        layer_whole = {}
        for lid, (old, overlay) in change.layer_whole.items():
            before = _with_overlay(old, overlay)
            after = self._layer_values.get(lid)
            if before != after:
                layer_whole[lid] = (before, after)
                if after is not None:
                    self._layer_shared.add(lid)  # the delta holds the live dict now
        return MeshDelta(
            vertices, edges, faces, symmetry, regions, layer_meta, layer_values, layer_whole, face_uvs
        )

    def rollback_change(self, change: MeshChange) -> None:
        """Stellt den Zustand bei `begin_change()` exakt wieder her (Element-Records,
        Reihenfolge, Symmetry Definition) und beendet die Aufzeichnung. ID-Zähler bleiben
        vorwärts (AD-001), wie bei load_state()."""
        self._stop(change)
        self._apply_records(change.vertices, change.edges, change.faces)
        if change.symmetry is not _UNSET:
            self.symmetry_definition = change.symmetry
        if change.regions is not _UNSET:
            self.face_regions = change.regions
        if change.layers_touched:
            self._restore_layers(change)
        if change.face_uvs:
            self._apply_uv_records(change.face_uvs)

    def revert_change(self, change: MeshChange) -> None:
        """Wie `rollback_change`, aber die Aufzeichnung läuft weiter (leer, ab dem wieder
        hergestellten Zustand): für einen Checkpoint, zu dem mehrfach zurückgekehrt wird."""
        for log in self._logs:
            if log is change:
                break
        else:
            raise MeshError("Änderungs-Aufzeichnung ist nicht aktiv.")
        self._apply_records(change.vertices, change.edges, change.faces)
        if change.symmetry is not _UNSET:
            self.symmetry_definition = change.symmetry
        if change.regions is not _UNSET:
            self.face_regions = change.regions
        if change.layers_touched:
            self._restore_layers(change)
        if change.face_uvs:
            self._apply_uv_records(dict(change.face_uvs))
        change.vertices, change.edges, change.faces = {}, {}, {}
        change.face_uvs = {}
        change.symmetry = _UNSET
        change.regions = _UNSET
        change.layer_meta = _UNSET
        change.layer_values, change.layer_whole = {}, {}

    def release_change(self, change: MeshChange) -> None:
        """Beendet eine Aufzeichnung ohne Delta: die Änderungen bleiben (ein Checkpoint, zu dem
        nicht zurückgekehrt wurde)."""
        self._stop(change)

    def apply_delta(self, delta: MeshDelta, *, reverse: bool = False) -> None:
        """Wendet ein `MeshDelta` an: vorwärts (Redo, der Mesh steht im Vorher-Zustand) oder
        rückwärts (Undo, der Mesh steht im Nachher-Zustand)."""
        side = 0 if reverse else 1
        self._apply_records(
            {vid: pair[side] for vid, pair in delta.vertices.items()},
            {eid: pair[side] for eid, pair in delta.edges.items()},
            {fid: pair[side] for fid, pair in delta.faces.items()},
        )
        if delta.symmetry is not None:
            self.symmetry_definition = delta.symmetry[side]
        if delta.regions is not None:
            self.face_regions = delta.regions[side]
        if delta.layer_meta is not None or delta.layer_values or delta.layer_whole:
            self._apply_layer_records(
                _UNSET if delta.layer_meta is None else delta.layer_meta[side],
                {lid: {vid: pair[side] for vid, pair in pairs.items()} for lid, pairs in delta.layer_values.items()},
                {lid: pair[side] for lid, pair in delta.layer_whole.items()},
            )
        if delta.face_uvs:
            self._apply_uv_records({fid: pair[side] for fid, pair in delta.face_uvs.items()})

    def _apply_uv_records(self, records: dict) -> None:
        """Sets each named face's UVs to its record (None = none). Runs after the element records,
        so every named face with UVs exists. The dict's order is not semantic (`_export_face_uvs`
        sorts)."""
        for fid in sorted(records, key=int):
            self._write_uvs(fid, records[fid])

    def _restore_layers(self, change: MeshChange) -> None:
        """Rollback / revert of the point layers to the state at `begin_change`."""
        self._apply_layer_records(
            change.layer_meta,
            {lid: dict(records) for lid, records in change.layer_values.items()},
            {lid: _with_overlay(old, overlay) for lid, (old, overlay) in list(change.layer_whole.items())},
        )

    def _apply_layer_records(self, meta, per_element: dict, whole: dict) -> None:
        """Sets the layers to the given records (the layer part of `_apply_records`). Order
        (AD-025 §4.2): whole-layer dicts first (they create, replace or drop a layer's values),
        then per-element values, then the meta - L1 holds afterwards. Installed dicts come from a
        record or a delta, so they are shared (copy-on-write)."""
        for lid, values in whole.items():
            if values is not self._layer_values.get(lid):
                self._bulk_set(lid, values, shared=True)
        for lid, records in per_element.items():
            for vid, value in records.items():
                self._write_value(lid, vid, value)
        if meta is not _UNSET and meta != self._layer_meta:
            self._set_layer_meta(meta)

    def watch(self) -> MeshWatch:
        """Dauerhaftes Journal für abgeleitete Daten (Viewport, Pick-Cache), siehe MeshWatch."""
        return MeshWatch(self)

    def _stop(self, change: MeshChange) -> None:
        for i, log in enumerate(self._logs):
            if log is change:
                del self._logs[i]
                return
        raise MeshError("Änderungs-Aufzeichnung ist nicht aktiv.")

    def _vertex_record(self, vid: VertexId) -> VertexRecord | None:
        data = self._vertices.get(vid)
        return None if data is None else data.position

    def _edge_record(self, eid: EdgeId) -> EdgeRecord | None:
        data = self._edges.get(eid)
        return None if data is None else (data.v0, data.v1, tuple(data.faces))

    def _face_record(self, fid: FaceId) -> FaceRecord | None:
        data = self._faces.get(fid)
        return None if data is None else tuple(data.boundary)

    @staticmethod
    def _differing(container: dict, records: dict, record_of) -> dict:
        out = {key: rec for key, rec in records.items() if record_of(key) != rec}
        for key in container:
            if key not in records:
                out[key] = None
        return out

    def _apply_records(self, vertices: dict, edges: dict, faces: dict) -> None:
        """Setzt jedes genannte Element auf seinen Record (None = entfernen) - der eine
        Schreibpfad für Rollback, Undo/Redo eines Deltas und load_state() unter einem Journal.
        Die Records müssen zusammen mit den nicht genannten Elementen einen gültigen Mesh
        ergeben (das garantieren Journal und Delta). Neu eingefügte IDs landen am Ende ihrer
        Tabelle; liegt eine davon unter der größten vorhandenen, wird die Tabelle neu sortiert
        (Invariante: aufsteigende Reihenfolge)."""
        logged = bool(self._logs)
        resort_v = resort_e = resort_f = False
        for fid, rec in faces.items():
            if logged:
                self._touch_f(fid)
            data = self._faces.get(fid)
            if rec is None:
                if data is not None:
                    del self._faces[fid]
            elif data is not None:
                data.boundary = list(rec)
            else:
                resort_f = resort_f or (bool(self._faces) and fid < next(reversed(self._faces)))
                self._faces[fid] = _FaceData(boundary=list(rec))
        lookup = self._edge_lookup
        for eid in edges:
            data = self._edges.get(eid)
            if data is not None:
                key = frozenset((data.v0, data.v1))
                if lookup.get(key) == eid:
                    del lookup[key]
                self._unindex_edge(eid, data.v0, data.v1)
        for eid, rec in edges.items():
            if logged:
                self._touch_e(eid)
            data = self._edges.get(eid)
            if rec is None:
                if data is not None:
                    del self._edges[eid]
                continue
            v0, v1, face_ids = rec
            if data is not None:
                data.v0, data.v1, data.faces = v0, v1, list(face_ids)
            else:
                resort_e = resort_e or (bool(self._edges) and eid < next(reversed(self._edges)))
                self._edges[eid] = _EdgeData(v0=v0, v1=v1, faces=list(face_ids))
            lookup[frozenset((v0, v1))] = eid
            self._index_edge(eid, v0, v1)
        for vid, rec in vertices.items():
            if logged:
                self._touch_v(vid)
            data = self._vertices.get(vid)
            if rec is None:
                if data is not None:
                    del self._vertices[vid]
            elif data is not None:
                data.position = rec
            else:
                resort_v = resort_v or (bool(self._vertices) and vid < next(reversed(self._vertices)))
                self._vertices[vid] = _VertexData(position=rec)
        for resort, container in (
            (resort_v, self._vertices), (resort_e, self._edges), (resort_f, self._faces)
        ):
            if resort:
                # Ohne Tupel pro Eintrag (kein Anlass für einen GC-Lauf über den ganzen Mesh).
                ordered = {key: container[key] for key in sorted(container)}
                container.clear()
                container.update(ordered)

    @classmethod
    def from_state(cls, state: dict) -> "Mesh":
        mesh = cls()
        mesh.load_state(state)
        return mesh


def _with_overlay(old: dict | None, overlay: dict) -> dict | None:
    """A whole-layer record's state at `begin_change`: the old dict with this recording's earlier
    per-element before-records applied (a new dict; the old one stays untouched)."""
    if not overlay:
        return old
    out = old.copy() if old is not None else {}
    for vid, value in overlay.items():
        if value is None:
            out.pop(vid, None)
        else:
            out[vid] = value
    return out


def _parse_point_layers(raw, vertex_records: dict) -> tuple[tuple, dict]:
    """The `"point_layers"` value of a state dict, validated whole (AD-025 §4.2 File): an unknown
    kind or rule, a duplicate name or id, a value for a missing vertex or an invalid value raises
    ValueError (MeshError) before anything is written."""
    if not raw:
        return (), {}
    meta = []
    values: dict[LayerId, dict[VertexId, LayerValue]] = {}
    names = set()
    try:
        for entry in raw:
            lid = LayerId(int(entry["id"]))
            try:
                kind = LayerKind(entry["kind"])
            except ValueError:
                raise MeshError(f"Unbekannte Layer-Art: {entry['kind']!r}") from None
            if kind is not LayerKind.VECTOR:
                raise MeshError(f"Layer-Art {kind.value!r} ist noch nicht gebaut.")
            info = PointLayerInfo(entry["name"], kind, entry["new_point"])
            if info.name in names or lid in values:
                raise MeshError(f"Doppelter Punkt-Layer: {info.name!r} / {int(lid)}")
            names.add(info.name)
            layer = {}
            for vid_raw, value in entry["values"].items():
                vid = VertexId(int(vid_raw))
                if vid not in vertex_records:
                    raise MeshError(f"Layer {info.name!r}: Wert für fehlenden Vertex {int(vid)}")
                if type(value) is list and len(value) == 3:
                    value = tuple(value)  # JSON gives lists; the fast path takes tuples of floats
                value = _vector_value(value)
                if value != _VECTOR_DEFAULT:
                    layer[vid] = value
            meta.append((lid, info))
            values[lid] = dict(sorted(layer.items()))
    except (KeyError, TypeError, AttributeError) as exc:
        raise MeshError(f"Ungültige point_layers: {exc!r}") from None
    return tuple(meta), values


def _parse_face_uvs(raw, face_records: dict) -> dict[FaceId, FaceUVs]:
    """The `"face_uvs"` value of a state dict, validated whole (AD-026): UVs for a missing face, a
    wrong corner count or a non-finite value raise MeshError before anything is written."""
    if not raw:
        return {}
    out: dict[FaceId, FaceUVs] = {}
    try:
        for fid_raw, uvs in raw.items():
            fid = FaceId(int(fid_raw))
            boundary = face_records.get(fid)
            if boundary is None:
                raise MeshError(f"face_uvs: UVs für fehlende Face {int(fid)}")
            out[fid] = uv_tuple(uvs, len(boundary))
    except (TypeError, AttributeError, ValueError) as exc:
        if isinstance(exc, MeshError):
            raise
        raise MeshError(f"Ungültige face_uvs: {exc}") from None
    return dict(sorted(out.items()))
