"""Edge-Loop-/Edge-Ring-Erkennung (Enablement-Port, AP-05).

1:1-Logik-Port aus experiments/mirai_bastel_viewport_V1/viewport/loop_ring.py
gegen Production-src/core. Reine Query — keine Mutation, keine History-Anbindung.

Konservative Regeln (Absicht, kein Zwischenstand):
- Edge Ring läuft nur durch Quad-Faces. Non-Quad-Face → Abbruch auf dieser Seite.
- Edge Loop läuft nur durch Vertices mit Valenz 4 und eindeutigem gegenüberliegenden
  Kandidaten. Boundary-Loop-Fortsetzung ist bewusst nicht implementiert.
- Geschlossene Traversierungen werden erkannt (closed=True); die Startkante erscheint
  nicht doppelt.
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
    closed: True, wenn die Traversierung zur Startkante zurückgefunden hat.
    """

    edges: list
    closed: bool

    def as_set(self) -> set:
        return set(self.edges)


def _loop_step(mesh, edge_id, from_vertex):
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
    """Konservative Edge-Loop-Traversierung ausgehend von start_edge."""
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

    backward, _ = walk(start_edge, v_a)
    return Traversal(edges=list(reversed(backward)) + [start_edge] + forward, closed=False)


def _ring_step(mesh, edge_id, through_face):
    boundary_edges = mesh.face_edges(through_face)
    if len(boundary_edges) != 4:
        return None
    idx = boundary_edges.index(edge_id)
    opposite_edge = boundary_edges[(idx + 2) % 4]
    other_faces = [f for f in mesh.edge_faces(opposite_edge) if f != through_face]
    return opposite_edge, (other_faces[0] if other_faces else None)


def edge_ring(mesh, start_edge) -> Traversal:
    """Konservative Edge-Ring-Traversierung ausgehend von start_edge."""
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

    backward, _ = walk(adjacent_faces[1])
    return Traversal(edges=list(reversed(backward)) + [start_edge] + forward, closed=False)
