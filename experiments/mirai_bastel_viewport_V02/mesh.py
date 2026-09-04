"""Kleines Dreiecks-Mesh mit minimaler Adjazenz für das V0.2 Experiment.

Repräsentiert die Core-Geometrie. Der Scope ist bewusst minimal:
- Positionsliste (Vertex-ID = Listenindex)
- Triangulierte Faces
- minimale Adjazenz ``vertex -> incident faces`` (aus der Research-Empfehlung)

Die Render-Seite liegt NICHT hier — das ist die Aufgabe von RenderMesh/
DerivedData. Dies ist nur die reine Geometrie/Struktur, die von außen
verändert werden kann (move/topology).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

Vec3 = tuple[float, float, float]


def make_grid_triangles(quads_u: int = 4, quads_v: int = 4) -> "Mesh":
    """Erzeugt ein planares Quad-Grid-Mesh (UV-Ebene) aus Quads -> 2 Tris/Quad.

    Anzahl Vertices: (quads_u+1) * (quads_v+1)
    Anzahl Triangles: 2 * quads_u * quads_v
    """
    u_count = quads_u + 1
    v_count = quads_v + 1
    positions: list[Vec3] = []
    triangles: list[tuple[int, int, int]] = []

    def vid(ru: int, rv: int) -> int:
        return rv * u_count + ru

    for rv in range(v_count):
        for ru in range(u_count):
            x = ru
            # planare Ebene (z = 0); Face-Normalen sind konstant (0, 0, ±1)
            # und damit non-zero — der Move-Test hebt Vertices dann in +z.
            z = 0.0
            positions.append((float(x), float(rv), z))

    for rv in range(quads_v):
        for ru in range(quads_u):
            a = vid(ru, rv)
            b = vid(ru + 1, rv)
            c = vid(ru + 1, rv + 1)
            d = vid(ru, rv + 1)
            triangles.append((a, b, c))
            triangles.append((a, c, d))

    return Mesh(positions, triangles)


class Mesh:
    def __init__(self, positions: Iterable[Vec3], triangles: Iterable[tuple[int, int, int]]) -> None:
        self.positions: list[Vec3] = [tuple(float(v) for v in p) for p in positions]
        self.triangles: list[tuple[int, int, int]] = [tuple(int(v) for v in t) for t in triangles]
        self.vertex_to_faces: dict[int, list[int]] = defaultdict(list)
        self._rebuild_adjacency()

    def _rebuild_adjacency(self) -> None:
        """Erzeugt die minimale Adjazenz vertex_id -> incident Face-IDs."""
        self.vertex_to_faces.clear()
        for f, tri in enumerate(self.triangles):
            for v in tri:
                self.vertex_to_faces[v].append(f)

    # -- Mutationen ---------------------------------------------------------
    def move_vertex(self, vid: int, new_pos: Vec3) -> None:
        """Setzt die Position einer Vertex-ID. Nur Position, keine Topology."""
        self.positions[vid] = tuple(float(v) for v in new_pos)

    def clear(self) -> None:
        """Entleert das Mesh (wird bei einer Topology-Änderung neu aufgebaut)."""
        self.positions.clear()
        self.triangles.clear()
        self.vertex_to_faces.clear()
