"""Topologische Paarung und Seiten — **Lab-Experiment**, keine Capability.

Handoff WP-SYM-LAB-01 Slice 5, §2 E11/E12
(`docs/architecture/WP-SYM-LAB-01_SLICE5_CLAUDE_CODE_HANDOFF.md`). Rein und
GL-frei. Benutzt wird es ausschließlich von Re-Symmetrize
(`lab_resymmetrize.py`); symmetrisches Move und die Anzeige der
gelben/magenta Vertices bleiben bei der exakten Positions-Paarung von
`mirai.symmetry` — unverändert.

Warum topologisch: Die Positions-Paarung findet für einen Vertex, der
(z. B. durch OBJ-Rundung) `1e-6` neben seiner Spiegelposition liegt, keinen
Partner (Slice 3, Befund E4: 54 Vertices bei `man_with_shoes_basemesh`).
Re-Symmetrize soll genau diese Vertices reparieren und braucht deshalb einen
Partner, der nicht von der Position abhängt. Die gespeicherte Seam ist das,
was eine Verformung überlebt (INV-4); von ihr aus lässt sich die Paarung
über die Nachbarschaft der Faces ableiten (INV-3). Sie wird nicht
gespeichert und bei jedem Aufruf neu berechnet.

E11 — Paarung (Breitensuche über Face-Paare, ausgehend von der Seam):

1. Jeder Vertex einer Seam-Edge ist selbst-gepaart.
2. Jede Seam-Edge mit genau zwei Faces liefert ein Face-Paar (Spiegel-Paar)
   mit der Seam-Edge als gemeinsamem Anker (a, b) ↔ (a, b).
3. Ein Face-Paar mit Anker (a, b) ↔ (a', b') wird gleichzeitig umlaufen —
   im einen Face in Richtung a→b, im anderen in Richtung a'→b' — und die
   Vertices werden paarweise zugeordnet. Unterschiedliche Face-Längen oder
   ein Anker, der keine Kante des Face ist → Konflikt für dieses Face-Paar,
   von dort wird nicht weitergelaufen.
4. Über jede Edge des Face-Paars zum jeweils nächsten Face-Paar (je genau
   ein Nachbar-Face auf beiden Seiten); jedes Face-Paar genau einmal.
5. Bekommt ein Vertex zwei verschiedene Partner → Konflikt; dieser Vertex
   gilt als nicht gepaart (INV-5).

Auslegung von Schritt 5 (Lab-Entscheidung, nicht im Handoff ausbuchstabiert):
Ein Vertex, dessen Partner selbst im Konflikt ist, gilt ebenfalls als nicht
gepaart. Sonst könnten zwei Vertices denselben (mehrdeutigen) Partner haben
und Re-Symmetrize legte beide auf dieselbe Spiegelposition — das wäre
„auf einen unbekannten Partner spiegeln" (INV-5). Dadurch ist `partners`
immer eine Involution (`partners[partners[v]] == v`).

E12 — Seiten: Faces werden in Zusammenhangskomponenten zerlegt, ohne
Seam-Edges zu überqueren. Ein Vertex gehört zu der Seite, deren Faces er
berührt; Seam-Vertices gehören zu keiner Seite. Ein Nicht-Seam-Vertex, der
Faces beider Seiten berührt (nur bei nicht-mannigfaltigen Stellen möglich),
gehört ebenfalls zu keiner Seite (`mixed`) — auch hier nicht raten (INV-5).

Grenzen: Die Paarung braucht eine Seam mit mindestens einer Edge, die genau
zwei Faces hat; ohne Seam gibt es nichts zu paaren (leeres Ergebnis).
Faces, die über keine Kette von Face-Paaren von der Seam aus erreichbar sind
(z. B. eine zweite, nicht an die Seam angebundene Mesh-Insel), bleiben
ungepaart.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

from core import EdgeId, FaceId, Mesh, VertexId


@dataclass(frozen=True)
class TopologicalPairing:
    """Ergebnis von E11. `partners` enthält nur konfliktfreie Paare (Involution);
    Seam-Vertices ohne Konflikt sind auf sich selbst abgebildet."""

    partners: dict[VertexId, VertexId]
    #: Vertices mit zwei verschiedenen Partnern (Schritt 5).
    conflicts: frozenset[VertexId]
    #: Face-Paare, die wegen Längen-/Anker-Konflikt nicht zugeordnet wurden (Schritt 3).
    face_pair_conflicts: int


@dataclass(frozen=True)
class TopologicalSides:
    """Ergebnis von E12. Seiten sind die Komponenten-Indizes `0..component_count-1`."""

    component_count: int
    face_side: dict[FaceId, int]
    #: Nicht-Seam-Vertices mit eindeutiger Seite.
    vertex_side: dict[VertexId, int]
    seam_vertices: frozenset[VertexId]
    #: Nicht-Seam-Vertices, die Faces mehrerer Seiten berühren (keine Seite).
    mixed: frozenset[VertexId]

    def faces_per_side(self) -> list[int]:
        counts = [0] * self.component_count
        for side in self.face_side.values():
            counts[side] += 1
        return counts


@dataclass(frozen=True)
class TopologyReport:
    """Partner-Map, Konflikte, Seiten-Zuordnung, Anzahl Komponenten (Handoff §4.1)."""

    pairing: TopologicalPairing
    sides: TopologicalSides


def _valid_seam_edges(mesh: Mesh) -> list[EdgeId]:
    definition = mesh.symmetry_definition
    if definition is None:
        return []
    return [eid for eid in definition.seam_edges if mesh.is_valid_edge(eid)]


def _edge_index(mesh: Mesh) -> dict[frozenset[VertexId], EdgeId]:
    return {frozenset(mesh.edge_vertices(eid)): eid for eid in mesh.all_edge_ids()}


def _walk(boundary: list[VertexId], a: VertexId, b: VertexId) -> Optional[list[VertexId]]:
    """Boundary ab `a` in Richtung `b`; None, wenn (a, b) keine Kante des Face ist."""
    n = len(boundary)
    if a not in boundary:
        return None
    i = boundary.index(a)
    if boundary[(i + 1) % n] == b:
        step = 1
    elif boundary[(i - 1) % n] == b:
        step = -1
    else:
        return None
    return [boundary[(i + step * k) % n] for k in range(n)]


def topological_pairing(mesh: Mesh) -> TopologicalPairing:
    """E11 — siehe Moduldocstring. Leeres Ergebnis, wenn Symmetrie aus ist."""
    seam_edges = _valid_seam_edges(mesh)
    raw: dict[VertexId, VertexId] = {}
    conflicts: set[VertexId] = set()

    def assign(v: VertexId, w: VertexId) -> None:
        for x, y in ((v, w), (w, v)):
            if x in conflicts:
                continue
            known = raw.get(x)
            if known is None:
                raw[x] = y
            elif known != y:
                conflicts.add(x)

    for eid in seam_edges:
        for vid in mesh.edge_vertices(eid):
            assign(vid, vid)

    edges = _edge_index(mesh)
    queue: deque = deque()
    for eid in seam_edges:
        faces = mesh.edge_faces(eid)
        if len(faces) == 2:
            a, b = mesh.edge_vertices(eid)
            queue.append((faces[0], faces[1], (a, b), (a, b)))

    visited: set[frozenset[FaceId]] = set()
    face_pair_conflicts = 0
    while queue:
        f, g, (a, b), (a2, b2) = queue.popleft()
        key = frozenset((f, g))
        if key in visited:
            continue
        visited.add(key)
        walk_f = _walk(mesh.face_vertices(f), a, b)
        walk_g = _walk(mesh.face_vertices(g), a2, b2)
        if walk_f is None or walk_g is None or len(walk_f) != len(walk_g):
            face_pair_conflicts += 1
            continue
        for v, w in zip(walk_f, walk_g):
            assign(v, w)
        n = len(walk_f)
        for k in range(n):
            u, v = walk_f[k], walk_f[(k + 1) % n]
            u2, v2 = walk_g[k], walk_g[(k + 1) % n]
            next_f = [x for x in mesh.edge_faces(edges[frozenset((u, v))]) if x != f]
            next_g = [x for x in mesh.edge_faces(edges[frozenset((u2, v2))]) if x != g]
            if len(next_f) == 1 and len(next_g) == 1:
                queue.append((next_f[0], next_g[0], (u, v), (u2, v2)))

    partners = {
        v: w for v, w in raw.items() if v not in conflicts and w not in conflicts
    }
    return TopologicalPairing(partners, frozenset(conflicts), face_pair_conflicts)


def topological_sides(mesh: Mesh) -> TopologicalSides:
    """E12 — Face-Komponenten ohne Überqueren der Seam; Seiten der Vertices."""
    seam_edges = set(_valid_seam_edges(mesh))
    face_ids = mesh.all_face_ids()
    parent: dict[FaceId, FaceId] = {f: f for f in face_ids}

    def find(f: FaceId) -> FaceId:
        while parent[f] != f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    for eid in mesh.all_edge_ids():
        if eid in seam_edges:
            continue
        faces = mesh.edge_faces(eid)
        for other in faces[1:]:
            ra, rb = find(faces[0]), find(other)
            if ra != rb:
                parent[rb] = ra

    root_index: dict[FaceId, int] = {}
    face_side: dict[FaceId, int] = {}
    for f in face_ids:
        face_side[f] = root_index.setdefault(find(f), len(root_index))

    seam_vertices = frozenset(v for eid in seam_edges for v in mesh.edge_vertices(eid))
    touched: dict[VertexId, set[int]] = {}
    for f in face_ids:
        for vid in mesh.face_vertices(f):
            if vid not in seam_vertices:
                touched.setdefault(vid, set()).add(face_side[f])
    vertex_side = {v: next(iter(s)) for v, s in touched.items() if len(s) == 1}
    mixed = frozenset(v for v, s in touched.items() if len(s) > 1)
    return TopologicalSides(len(root_index), face_side, vertex_side, seam_vertices, mixed)


def topology_report(mesh: Mesh) -> TopologyReport:
    return TopologyReport(topological_pairing(mesh), topological_sides(mesh))
