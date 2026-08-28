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
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ids import VertexId, EdgeId, FaceId, IdAllocator

Position = tuple[float, float, float]


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
        self._vertices[vertex_id].position = position

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
        # V1: einfacher Scan. Query-API bleibt stabil, falls dies später
        # durch eine O(1)-Half-Edge-Navigation ersetzt wird.
        return [eid for eid, e in self._edges.items() if vertex_id in (e.v0, e.v1)]

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

    def add_vertex(self, position: Position) -> VertexId:
        """ID-Kontinuität: erzeugt genau eine neue VertexId."""
        vid = self._vertex_alloc.allocate()
        self._vertices[vid] = _VertexData(position=position)
        return vid

    def _get_or_create_edge(self, v_a: VertexId, v_b: VertexId) -> EdgeId:
        key = frozenset((v_a, v_b))
        existing = self._edge_lookup.get(key)
        if existing is not None:
            return existing
        eid = self._edge_alloc.allocate()
        self._edges[eid] = _EdgeData(v0=v_a, v1=v_b)
        self._edge_lookup[key] = eid
        return eid

    def add_edge(self, v_a: VertexId, v_b: VertexId) -> EdgeId:
        """Erzeugt eine freie Edge zwischen zwei bestehenden Vertices.

        Vom Connect-Edges-Experiment entdeckte Kern-Fähigkeit (siehe
        docs/research/topology/CONNECT_EDGES_SPEC.md): Higher-Level-
        Operationen wie Connect Edges müssen Kanten zwischen zwei
        Vertices anlegen koennen, die KEINE gemeinsame Face besitzen
        (z. B. Verbindungskanten zwischen den Mittelpunkten kanten-
        benachbarter Kettenglieder). Ueber die bestehenden Primitiven
        (connect_vertices) ist das nicht abbildbar.

        ID-Kontinuitaet:
        - falls zwischen v_a und v_b bereits eine Edge existiert, wird
          genau diese zurueckgegeben (keine neue EdgeId).
        - sonst entsteht genau eine neue EdgeId; die Edge ist freistehend
          (Face-Liste leer) und referenziert ausschliesslich bestehende
          Vertices.
        - es entstehen keine Vertices und keine Faces.
        """
        return self._get_or_create_edge(v_a, v_b)

    def add_face(self, vertex_ids: list[VertexId]) -> FaceId:
        """Erzeugt eine Face aus einer geordneten Liste bestehender Vertices.

        ID-Kontinuität:
        - alle übergebenen VertexIds bleiben unverändert.
        - für jedes Vertex-Paar entlang der Boundary wird eine bestehende
          Edge wiederverwendet, falls vorhanden, sonst eine neue EdgeId
          erzeugt.
        - es entsteht genau eine neue FaceId.
        """
        if len(vertex_ids) < 3:
            raise MeshError("Eine Face benötigt mindestens 3 Vertices.")
        for v in vertex_ids:
            if not self.is_valid_vertex(v):
                raise MeshError(f"Unbekanntes Vertex: {v!r}")

        fid = self._face_alloc.allocate()
        n = len(vertex_ids)
        for i in range(n):
            v_a, v_b = vertex_ids[i], vertex_ids[(i + 1) % n]
            eid = self._get_or_create_edge(v_a, v_b)
            self._edges[eid].faces.append(fid)

        self._faces[fid] = _FaceData(boundary=list(vertex_ids))
        return fid

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
        face = self._faces.pop(face_id)
        n = len(face.boundary)
        for i in range(n):
            v_a, v_b = face.boundary[i], face.boundary[(i + 1) % n]
            eid = self._edge_lookup[frozenset((v_a, v_b))]
            self._edges[eid].faces.remove(face_id)

    def split_edge(self, edge_id: EdgeId) -> tuple[VertexId, EdgeId, EdgeId]:
        """Teilt eine Edge an ihrem Mittelpunkt.

        ID-Kontinuität:
        - die ursprüngliche EdgeId wird ungültig.
        - beide ursprünglichen Endpunkt-VertexIds bleiben unverändert.
        - es entsteht genau eine neue VertexId (Mittelpunkt) und zwei
          neue EdgeIds.
        - jede angrenzende Face behält ihre FaceId, ihre Boundary-Liste
          wird jedoch aktualisiert (Mittelpunkt wird eingefügt).

        Rückgabe: (neue_vertex_id, neue_edge_id_a, neue_edge_id_b)
        """
        edge = self._edges.pop(edge_id)
        del self._edge_lookup[frozenset((edge.v0, edge.v1))]

        p0 = self.vertex_position(edge.v0)
        p1 = self.vertex_position(edge.v1)
        mid_pos = tuple((a + b) / 2.0 for a, b in zip(p0, p1))
        mid = self.add_vertex(mid_pos)

        eid_a = self._edge_alloc.allocate()
        eid_b = self._edge_alloc.allocate()
        self._edges[eid_a] = _EdgeData(v0=edge.v0, v1=mid, faces=[])
        self._edges[eid_b] = _EdgeData(v0=mid, v1=edge.v1, faces=[])
        self._edge_lookup[frozenset((edge.v0, mid))] = eid_a
        self._edge_lookup[frozenset((mid, edge.v1))] = eid_b

        for fid in edge.faces:
            boundary = self._faces[fid].boundary
            new_boundary = []
            n = len(boundary)
            for i in range(n):
                v_curr, v_next = boundary[i], boundary[(i + 1) % n]
                new_boundary.append(v_curr)
                if frozenset((v_curr, v_next)) == frozenset((edge.v0, edge.v1)):
                    new_boundary.append(mid)
            self._faces[fid].boundary = new_boundary
            self._edges[eid_a].faces.append(fid)
            self._edges[eid_b].faces.append(fid)

        return mid, eid_a, eid_b

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

        Bekannte V1-Einschränkung: keine allgemeine Non-Manifold-Prüfung.
        """
        edge = self._edges.pop(edge_id)
        del self._edge_lookup[frozenset((edge.v0, edge.v1))]
        survivor, removed = edge.v0, edge.v1

        p0 = self.vertex_position(survivor)
        p1 = self.vertex_position(removed)
        self.set_vertex_position(survivor, tuple((a + b) / 2.0 for a, b in zip(p0, p1)))

        # Invariant (fehlte bisher als expliziter Test, siehe tests/test_core.py):
        # nach collapse_edge() darf KEINE Edge mehr auf `removed` verweisen.
        # Jede verbleibende Edge, die `removed` als Endpunkt hatte, wird daher
        # explizit auf `survivor` umgebogen - bei bereits existierender
        # survivor<->other-Edge werden beide zusammengeführt (Face-Referenzen
        # vereinigt, redundante EdgeId verworfen), statt wie zuvor eine neue,
        # doppelte Edge anzulegen und die alte (stale) Edge stehen zu lassen.
        for eid, e in list(self._edges.items()):
            if e.v0 != removed and e.v1 != removed:
                continue
            old_key = frozenset((e.v0, e.v1))
            other = e.v1 if e.v0 == removed else e.v0
            del self._edge_lookup[old_key]
            if other == survivor:
                # Parallele Duplikat-Edge zur bereits kollabierten Kante - verwerfen.
                del self._edges[eid]
                continue
            new_key = frozenset((survivor, other))
            existing_eid = self._edge_lookup.get(new_key)
            if existing_eid is not None and existing_eid != eid:
                existing = self._edges[existing_eid]
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

        affected_faces = list(edge.faces)
        for fid in list(self._faces.keys()):
            boundary = self._faces[fid].boundary
            if removed not in boundary:
                continue
            if fid not in affected_faces:
                affected_faces.append(fid)

        for fid in affected_faces:
            face = self._faces.get(fid)
            if face is None:
                continue
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
                self._remove_face_edges_only(fid)
                del self._faces[fid]
                continue

            self._faces[fid].boundary = deduped

        del self._vertices[removed]
        return survivor

    def _remove_face_edges_only(self, face_id: FaceId) -> None:
        face = self._faces[face_id]
        n = len(face.boundary)
        for i in range(n):
            v_a, v_b = face.boundary[i], face.boundary[(i + 1) % n]
            key = frozenset((v_a, v_b))
            eid = self._edge_lookup.get(key)
            if eid is not None and face_id in self._edges[eid].faces:
                self._edges[eid].faces.remove(face_id)

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

        # alte Face-Referenzen der bestehenden Edges entfernen
        self._remove_face_edges_only(face_id)
        del self._faces[face_id]

        new_face_1 = self.add_face(loop_1)
        new_face_2 = self.add_face(loop_2)
        new_edge = self._edge_lookup[frozenset((v_a, v_b))]

        return new_edge, new_face_1, new_face_2

    # ------------------------------------------------------------------
    # Serialisierung (§8, §12) - bewusst hier statt in serialization.py,
    # weil nur Mesh selbst legitimen Zugriff auf seine internen Container
    # hat (Vertrag aus §15 Punkt 1: keine externe Abhängigkeit von
    # internen Mesh-Containern).
    # ------------------------------------------------------------------

    def export_state(self) -> dict:
        """Reine Datenstruktur, JSON-kompatibel. Enthält auch die
        Allocator-Zählerstände, damit künftig neu erzeugte IDs nach dem
        Laden nicht mit gespeicherten IDs kollidieren (§8)."""
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
        }

    def load_state(self, state: dict) -> None:
        """Ersetzt den kompletten Inhalt dieses Mesh-Objekts in-place.

        Die Mesh-Instanz selbst bleibt erhalten, damit Scene/Selection/
        Viewport weiterhin auf dasselbe Objekt zeigen. Die Allocator-
        Zähler werden wie bei from_state() nur vorwärts bewegt.
        """
        self._vertices.clear()
        self._edges.clear()
        self._faces.clear()
        self._edge_lookup.clear()

        for vid_raw, pos in state["vertices"].items():
            self._vertices[VertexId(int(vid_raw))] = _VertexData(position=tuple(pos))
        for eid_raw, edata in state["edges"].items():
            eid = EdgeId(int(eid_raw))
            v0, v1 = VertexId(edata["v0"]), VertexId(edata["v1"])
            self._edges[eid] = _EdgeData(
                v0=v0, v1=v1, faces=[FaceId(f) for f in edata["faces"]]
            )
            self._edge_lookup[frozenset((v0, v1))] = eid
        for fid_raw, boundary in state["faces"].items():
            fid = FaceId(int(fid_raw))
            self._faces[fid] = _FaceData(boundary=[VertexId(v) for v in boundary])

        self._vertex_alloc.restore_counter(state["vertex_id_counter"])
        self._edge_alloc.restore_counter(state["edge_id_counter"])
        self._face_alloc.restore_counter(state["face_id_counter"])

    @classmethod
    def from_state(cls, state: dict) -> "Mesh":
        mesh = cls()
        mesh.load_state(state)
        return mesh
