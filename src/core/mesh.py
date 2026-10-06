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

from collections.abc import Sequence
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

        # Symmetry Definition (AD-SYM-01): bewusst ein PUBLIC-Attribut statt
        # Getter/Setter-Paar - analog zu Scene.morph_targets/rig/animation
        # (reservierter Subsystem-Platz, direkt settbar), nicht analog zur
        # Topologie-Query-API (AD-002 §15 Punkt 1), die ausschließlich für
        # die Vertex-/Edge-/Face-Container gilt. Default: keine Definition
        # (Symmetrie "aus").
        self.symmetry_definition: SymmetryDefinition | None = None

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
        face = self._faces.pop(face_id)
        n = len(face.boundary)
        for i in range(n):
            v_a, v_b = face.boundary[i], face.boundary[(i + 1) % n]
            eid = self._edge_lookup[frozenset((v_a, v_b))]
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

        Rückgabe: (neue_vertex_id, neue_edge_id_a, neue_edge_id_b)
        """
        if t <= 0.0 or t >= 1.0:
            raise MeshError("split_edge: t must be in (0.0, 1.0)")

        edge = self._edges.pop(edge_id)
        del self._edge_lookup[frozenset((edge.v0, edge.v1))]

        p0 = self.vertex_position(edge.v0)
        p1 = self.vertex_position(edge.v1)
        mid_pos = tuple(a * (1.0 - t) + b * t for a, b in zip(p0, p1))
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

    def split_face(
        self,
        face_id: FaceId,
        v_a: VertexId,
        v_b: VertexId,
        positions: Sequence[Position] = (),
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

        self._remove_face_edges_only(face_id)
        del self._faces[face_id]

        new_vertices = [self.add_vertex(p) for p in positions]
        chain = [v_a, *new_vertices, v_b]
        # Endpunkte jeder Pfad-Edge so, wie face_1 sie durchläuft (e -> s) -
        # bei k = 0 genau die Edge, die connect_vertices über add_face(loop_1)
        # anlegen würde. Die Edge-Richtung selbst ist nicht semantisch.
        new_edges = [
            self._get_or_create_edge(w, u) if a_first else self._get_or_create_edge(u, w)
            for u, w in zip(chain, chain[1:])
        ]
        interior_s_to_e = new_vertices if a_first else new_vertices[::-1]

        face_1 = self.add_face(arc_1 + interior_s_to_e[::-1])
        face_2 = self.add_face(arc_2 + interior_s_to_e)
        return new_vertices, new_edges, face_1, face_2

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
        """Entfernt Faces destruktiv (Loch) samt allem, was nur innerhalb der
        entfernten Region lag (WP Delete/Dissolve §0.2.3).

        Mit entfernt werden die inneren Edges der Region (beide Faces
        entfernt) und Vertices, die dadurch keine Edge mehr haben. Rand-Edges
        der Region bleiben mit unveränderter ID als Lochrand stehen - auch
        eine Edge, die vorher Mesh-Rand war und danach keine Face mehr hat
        (wie remove_face, V1-Entscheidung). Leere Auswahl -> No-op.

        Vorbedingung: jede FaceId gültig (sonst MeshError, Mesh unverändert).

        ID-Kontinuität: die FaceIds, die inneren EdgeIds und die kantenlos
        gewordenen VertexIds werden ungültig; es entstehen keine neuen IDs;
        alle übrigen IDs und alle verbleibenden Face-Boundaries bleiben
        unverändert.
        """
        for fid in face_ids:
            if not self.is_valid_face(fid):
                raise MeshError(f"delete_faces: unbekannte Face {fid!r}")
        self._delete_region(set(face_ids), set(), set())

    def delete_edges(self, edge_ids: Sequence[EdgeId]) -> None:
        """Entfernt Edges destruktiv: die Edge selbst und ihre (bis zu zwei)
        Faces, danach wie delete_faces (innere Edges der entfernten Region und
        kantenlos gewordene Vertices mit). Eine Edge ohne Face wird einfach
        entfernt. Leere Auswahl -> No-op.

        Vorbedingung: jede EdgeId gültig (sonst MeshError, Mesh unverändert).

        ID-Kontinuität: die EdgeIds, die FaceIds ihrer Faces, die inneren
        EdgeIds der Region und die kantenlos gewordenen VertexIds werden
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
        danach wie delete_faces (innere Edges der Region und kantenlos
        gewordene Vertices mit). Die äußeren Edges des 1-Rings bleiben als
        Lochrand stehen. Leere Auswahl -> No-op.

        Vorbedingung: jede VertexId gültig (sonst MeshError, Mesh unverändert).

        ID-Kontinuität: die VertexIds, alle anliegenden EdgeIds und FaceIds,
        die inneren EdgeIds der Region und die kantenlos gewordenen VertexIds
        werden ungültig; keine neuen IDs; alles Übrige unverändert.
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
        """Wendet einen `_plan_dissolve`-Plan an (keine Prüfungen mehr)."""
        for fid in plan["removed_faces"]:
            self._remove_face_edges_only(fid)
            del self._faces[fid]
        for fid, boundary in plan["updated"].items():
            self._faces[fid].boundary = boundary
        for eid in plan["removed_edges"]:
            edge = self._edges.pop(eid)
            del self._edge_lookup[frozenset((edge.v0, edge.v1))]
        for vid in plan["removed_vertices"]:
            del self._vertices[vid]
        new_faces = [self.add_face(boundary) for boundary in plan["merged"]]
        for fid in sorted(plan["updated"], key=int):
            boundary = self._faces[fid].boundary
            n = len(boundary)
            for i in range(n):
                eid = self._get_or_create_edge(boundary[i], boundary[(i + 1) % n])
                if fid not in self._edges[eid].faces:
                    self._edges[eid].faces.append(fid)
        for v_a, v_b in plan["wire_edges"]:
            self._get_or_create_edge(v_a, v_b)
        return new_faces

    def _delete_region(
        self, faces: set[FaceId], edges: set[EdgeId], vertices: set[VertexId]
    ) -> None:
        """Gemeinsamer Delete-Kern: entfernt `faces`, `edges`, `vertices`,
        dazu die inneren Edges der Face-Region und kantenlos gewordene
        Vertices. Aufrufer haben alle IDs bereits geprüft."""
        removed_edges = set(edges)
        for fid in faces:
            for eid in self.face_edges(fid):
                adjacent = self._edges[eid].faces
                if len(adjacent) == 2 and all(f in faces for f in adjacent):
                    removed_edges.add(eid)
        # Ein Durchlauf statt vertex_edges() je Endpunkt (O(E) pro Aufruf).
        touched = {v for e in removed_edges for v in self.edge_vertices(e)}
        keeps_edge = {
            v for eid, e in self._edges.items() if eid not in removed_edges
            for v in (e.v0, e.v1) if v in touched
        }
        removed_vertices = set(vertices) | (touched - keeps_edge)
        for fid in faces:
            self._remove_face_edges_only(fid)
            del self._faces[fid]
        for eid in removed_edges:
            edge = self._edges.pop(eid)
            del self._edge_lookup[frozenset((edge.v0, edge.v1))]
        for vid in removed_vertices:
            del self._vertices[vid]

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
        }

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

        symmetry_raw = state.get("symmetry")
        if symmetry_raw is None:
            self.symmetry_definition = None
        else:
            self.symmetry_definition = SymmetryDefinition(
                plane_point=tuple(symmetry_raw["plane_point"]),
                plane_normal=tuple(symmetry_raw["plane_normal"]),
                seam_edges=frozenset(EdgeId(eid) for eid in symmetry_raw["seam_edges"]),
            )

    @classmethod
    def from_state(cls, state: dict) -> "Mesh":
        mesh = cls()
        mesh.load_state(state)
        return mesh
