"""Edge-Loop-/Edge-Ring-Erkennung (Phase 2 des Topology-Experimentplans).

Bezug: experiments/topology/TOPOLOGY_EXPERIMENT_PLAN.md, Phase 2.

Dieses Modul ist bewusst reine Erkennung (Query), keine Mutation und keine
History-Anbindung. Es liest ausschließlich über die bestehende
Topologie-Query-API des Mesh (face_vertices, face_edges, edge_faces,
edge_vertices, vertex_edges) - siehe mirai_bastel_core.mesh Architekturvertrag
Punkt 2. Keine internen Mesh-Container werden berührt.

Bewusst konservativ (siehe Plan: "Erst wenn die Erkennung ausreichend
zuverlässig ist, werden darauf aufbauende Operationen untersucht."):

- Edge Ring läuft nur durch Quad-Faces (Face-Boundary-Länge 4). Trifft die
  Traversierung auf eine Non-Quad-Face, bricht der Ring auf dieser Seite ab,
  statt zu raten, welche Kante "gegenüber" liegen könnte.
- Edge Loop läuft nur durch Vertices mit Valenz genau 4 UND eindeutigem
  "gegenüberliegendem" Kandidaten (keine Face gemeinsam mit der eingehenden
  Kante). Boundary-Loop-Fortsetzung (Weiterlaufen entlang eines offenen
  Randes) ist bewusst NICHT implementiert - das ist ein bekanntes,
  dokumentiertes Folgethema, kein stiller Best-Effort-Fallback.
- Beide Traversierungen erkennen geschlossene Loops/Ringe (z. B. auf einem
  geschlossenen Streifen) und geben dafür `closed=True` zurück, statt die
  Startkante doppelt aufzunehmen.

Diese Einschränkungen sind Absicht, kein Zwischenstand: eine unzuverlässige
Traversierung soll nicht als Grundlage für spätere Operationen (Loop Insert,
Loop Cut, ...) dienen.
"""

from __future__ import annotations

from dataclasses import dataclass


class LoopRingError(ValueError):
    pass


@dataclass(frozen=True)
class Traversal:
    """Ergebnis einer Loop-/Ring-Traversierung.

    edges: geordnete Liste der gefundenen Kanten, Startkante eingeschlossen.
        Bei geschlossener Traversierung kommt jede Kante genau einmal vor.
    closed: True, wenn die Traversierung zur Startkante zurückgefunden hat
        (z. B. ein Ring auf einem geschlossenen Quad-Streifen).
    """

    edges: list
    closed: bool

    def as_set(self) -> set:
        return set(self.edges)


def _loop_step(mesh, edge_id, from_vertex):
    """Nächste Loop-Kante ab `edge_id`, gesehen von `from_vertex` aus.

    Gibt (naechste_edge, naechster_vertex) zurück, oder None, wenn die
    Traversierung an `from_vertex` konservativ abbricht (Valenz != 4 oder
    kein eindeutiger gegenüberliegender Kandidat).
    """
    incident = mesh.vertex_edges(from_vertex)
    if len(incident) != 4:
        return None

    own_faces = set(mesh.edge_faces(edge_id))
    candidates = [
        e for e in incident
        if e != edge_id and set(mesh.edge_faces(e)).isdisjoint(own_faces)
    ]
    if len(candidates) != 1:
        return None

    next_edge = candidates[0]
    v0, v1 = mesh.edge_vertices(next_edge)
    next_vertex = v1 if v0 == from_vertex else v0
    return next_edge, next_vertex


def edge_loop(mesh, start_edge) -> Traversal:
    """Konservative Edge-Loop-Erkennung ausgehend von `start_edge`.

    Läuft von beiden Endpunkten der Startkante in die jeweils andere
    Richtung weiter, solange an jedem erreichten Vertex Valenz 4 und ein
    eindeutiger "gegenüberliegender" Kandidat vorliegt.
    """
    if not mesh.is_valid_edge(start_edge):
        raise LoopRingError(f"Unbekannte Edge: {start_edge!r}")

    v_a, v_b = mesh.edge_vertices(start_edge)
    visited = {start_edge}

    def walk(current_edge, current_vertex):
        collected = []
        while True:
            step = _loop_step(mesh, current_edge, current_vertex)
            if step is None:
                return collected, False
            next_edge, next_vertex = step
            if next_edge in visited:
                return collected, True
            visited.add(next_edge)
            collected.append(next_edge)
            current_edge, current_vertex = next_edge, next_vertex

    forward, closed_forward = walk(start_edge, v_b)
    if closed_forward:
        return Traversal(edges=[start_edge] + forward, closed=True)

    backward, closed_backward = walk(start_edge, v_a)
    # closed_backward kann bei einem offenen Loop nicht eintreten, ohne dass
    # closed_forward es auch täte (beide Richtungen liegen auf demselben
    # Loop) - Prüfung bleibt trotzdem explizit statt stillschweigend anzunehmen.
    edges = list(reversed(backward)) + [start_edge] + forward
    return Traversal(edges=edges, closed=closed_backward)


def _ring_step(mesh, edge_id, through_face):
    """Nächste Ring-Kante, wenn man `edge_id` durch `through_face` verlässt.

    Gibt (naechste_edge, naechste_face_oder_None) zurück, oder None, wenn
    `through_face` keine Quad-Face ist.
    """
    boundary_edges = mesh.face_edges(through_face)
    if len(boundary_edges) != 4:
        return None
    idx = boundary_edges.index(edge_id)
    opposite_edge = boundary_edges[(idx + 2) % 4]
    other_faces = [f for f in mesh.edge_faces(opposite_edge) if f != through_face]
    next_face = other_faces[0] if other_faces else None
    return opposite_edge, next_face


def edge_ring(mesh, start_edge) -> Traversal:
    """Konservative Edge-Ring-Erkennung ausgehend von `start_edge`.

    Läuft durch jede der (bis zu 2) an `start_edge` angrenzenden Faces,
    solange die jeweils aktuelle Face eine Quad-Face ist.
    """
    if not mesh.is_valid_edge(start_edge):
        raise LoopRingError(f"Unbekannte Edge: {start_edge!r}")

    adjacent_faces = mesh.edge_faces(start_edge)
    visited = {start_edge}

    def walk(through_face):
        collected = []
        current_edge = start_edge
        current_face = through_face
        while current_face is not None:
            step = _ring_step(mesh, current_edge, current_face)
            if step is None:
                return collected, False
            next_edge, next_face = step
            if next_edge in visited:
                return collected, True
            visited.add(next_edge)
            collected.append(next_edge)
            current_edge, current_face = next_edge, next_face
        return collected, False

    if not adjacent_faces:
        return Traversal(edges=[start_edge], closed=False)

    forward, closed_forward = walk(adjacent_faces[0])
    if closed_forward:
        return Traversal(edges=[start_edge] + forward, closed=True)

    if len(adjacent_faces) < 2:
        return Traversal(edges=[start_edge] + forward, closed=False)

    backward, closed_backward = walk(adjacent_faces[1])
    edges = list(reversed(backward)) + [start_edge] + forward
    return Traversal(edges=edges, closed=closed_backward)
