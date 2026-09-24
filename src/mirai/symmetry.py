"""Symmetry V1 — Correspondence-Ableitung und State-Aggregation (WP-SYM-01 Slice 1).

Bezug: docs/architecture/AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md,
docs/architecture/AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md,
docs/architecture/SLICE1_CLAUDE_CODE_HANDOFF.md.

Modul-Pfad (Handoff §3.2, bewusst offen gelassen - hier entschieden): liegt
in `mirai`, nicht im gefrorenen Core, genau wie `scene_factory.py`
(AD-008) und `mesh_geometry.py` (AD-008) bereits Logik oberhalb des Core
gegen dessen öffentliche Query-API implementieren. Grund: Mesh *besitzt*
die Symmetry Definition, *kennt* aber keine Symmetrie-Semantik
(AD-SYM-01 §3, die ausdrückliche Grenze) - Correspondence und State sind
genau diese Semantik und dürfen deshalb nicht in `src/core/mesh.py` landen.

Kein Cache, keine gespeicherte Tabelle (AR-1, INV-3): jede Funktion hier
leitet bei jedem Aufruf neu aus `mesh.symmetry_definition` + aktuellem
Mesh-Zustand ab.

Toleranz (AR-1, Design Brief §7, "keine Toleranzwerte als Wahrheit
einführen"): Dieses Modul führt bewusst KEINE Toleranz ein, weder für
Correspondence-Matching noch für die VIOLATED-Prüfung. Beide Prüfungen
verwenden exakte Fließkomma-Gleichheit. Das ist keine Lücke, sondern die
Art, wie die Toleranz-Frage hier vermieden statt beantwortet wird -
Toleranz ist laut Evolution-Dokument bewusst nicht V1-Wahrheit, und eine
exakte Prüfung erzwingt keinen Schwellenwert, den niemand entschieden hat.
Für V1-Testmeshes mit sauberen, bewusst gespiegelten Koordinaten (z. B.
achsenausgerichtete Planes) ist das ausreichend (Handoff §3.2: "positions-
basiert ist ausreichend").
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.ids import VertexId
from core.mesh import Mesh, Position, SymmetryDefinition


class CorrespondenceState(Enum):
    """Zustand eines einzelnen Vertex relativ zur Symmetry Definition.

    Vier Zustände (Handoff §3.2, INV-3):
    - PAIRED: genau ein positionsbasierter Partner gefunden.
    - SEAM: Vertex ist Endpunkt einer DEKLARIERTEN Seam-Edge (Identität,
      INV-1) - unabhängig davon, ob er geometrisch exakt auf der Plane
      liegt. Ob er das tut, ist Teil des aggregierten Symmetry State
      (VIOLATED), nicht dieses Correspondence-Zustands.
    - UNPAIRED: kein Partner ableitbar.
    - AMBIGUOUS: mehr als ein Kandidat (z. B. koinzidente Vertices).
    """

    PAIRED = "paired"
    SEAM = "seam"
    UNPAIRED = "unpaired"
    AMBIGUOUS = "ambiguous"


class SymmetryState(Enum):
    """Aggregierter Zustand über alle Vertex-Correspondences (Handoff §3.3).

    Prioritätsreihenfolge bei mehreren gleichzeitig zutreffenden Bedingungen
    (Implementierungsdetail, nicht in den AD-Dokumenten festgelegt): AMBIGUOUS
    vor VIOLATED vor PARTIAL vor VALID - eine mehrdeutige Zuordnung ist der
    am schwersten wiegende Befund, eine Seam-Verletzung wiegt schwerer als
    ein einfach nur unvollständig gepaartes Mesh.
    """

    OFF = "off"
    VALID = "valid"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    VIOLATED = "violated"


@dataclass(frozen=True)
class VertexCorrespondence:
    state: CorrespondenceState
    partner: VertexId | None = None


def mirror_position(position: Position, plane_point: Position, plane_normal: Position) -> Position:
    """Spiegelt `position` an der durch `plane_point`/`plane_normal` definierten Plane.

    Setzt voraus, dass `plane_normal` ein Einheitsvektor ist (Vertrag von
    `SymmetryDefinition`, siehe core/mesh.py).
    """
    distance = _signed_distance(position, plane_point, plane_normal)
    return tuple(p - 2.0 * distance * n for p, n in zip(position, plane_normal))


def _signed_distance(position: Position, plane_point: Position, plane_normal: Position) -> float:
    return sum((p - o) * n for p, o, n in zip(position, plane_point, plane_normal))


def _seam_vertex_ids(mesh: Mesh, definition: SymmetryDefinition) -> set[VertexId]:
    """Vertex-Endpunkte der deklarierten Seam-Edges.

    Überspringt Edge-IDs, die im aktuellen Mesh nicht (mehr) gültig sind,
    statt abzustürzen - das ist der Mechanismus, durch den eine nach einer
    Topologie-Mutation "erkennbar ungültig" gewordene Seam-Referenz sich
    hier zeigt (`mesh.is_valid_edge()` liefert `False`), statt still falsch
    weiterzurechnen (AD-SYM-01 §1.1 / Handoff §5).
    """
    vertex_ids: set[VertexId] = set()
    for edge_id in definition.seam_edges:
        if not mesh.is_valid_edge(edge_id):
            continue
        v0, v1 = mesh.edge_vertices(edge_id)
        vertex_ids.add(v0)
        vertex_ids.add(v1)
    return vertex_ids


def vertex_correspondence(mesh: Mesh) -> dict[VertexId, VertexCorrespondence]:
    """Leitet für jeden Vertex des Mesh den Correspondence-Zustand ab (INV-3).

    Leeres Dict, falls `mesh.symmetry_definition is None` (Symmetrie "aus" -
    es gibt nichts abzuleiten).
    """
    definition = mesh.symmetry_definition
    if definition is None:
        return {}

    seam_vertex_ids = _seam_vertex_ids(mesh, definition)
    positions = {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}

    by_position: dict[Position, list[VertexId]] = {}
    for vid, pos in positions.items():
        by_position.setdefault(pos, []).append(vid)

    result: dict[VertexId, VertexCorrespondence] = {}
    for vid, pos in positions.items():
        if vid in seam_vertex_ids:
            result[vid] = VertexCorrespondence(CorrespondenceState.SEAM)
            continue

        mirrored = mirror_position(pos, definition.plane_point, definition.plane_normal)
        candidates = [w for w in by_position.get(mirrored, ()) if w != vid]

        if not candidates:
            result[vid] = VertexCorrespondence(CorrespondenceState.UNPAIRED)
        elif len(candidates) == 1:
            result[vid] = VertexCorrespondence(CorrespondenceState.PAIRED, candidates[0])
        else:
            result[vid] = VertexCorrespondence(CorrespondenceState.AMBIGUOUS)

    return result


def _seam_violates_plane(mesh: Mesh, definition: SymmetryDefinition) -> bool:
    """VIOLATED-Prüfung (Handoff §3.3): liegt ein deklariertes Seam-Element
    nicht exakt auf der Plane? Ignoriert dabei inzwischen ungültige
    Seam-Edge-IDs (siehe `_seam_vertex_ids`) - eine tote Referenz ist kein
    Verstoß gegen die Plane, sondern ein anderer, hier nicht bewerteter
    Befund.
    """
    for edge_id in definition.seam_edges:
        if not mesh.is_valid_edge(edge_id):
            continue
        for vertex_id in mesh.edge_vertices(edge_id):
            distance = _signed_distance(
                mesh.vertex_position(vertex_id), definition.plane_point, definition.plane_normal
            )
            if distance != 0.0:
                return True
    return False


def symmetry_state(mesh: Mesh) -> SymmetryState:
    """Aggregierter Symmetry State über alle Vertex-Correspondences (Handoff §3.3)."""
    definition = mesh.symmetry_definition
    if definition is None:
        return SymmetryState.OFF

    correspondence = vertex_correspondence(mesh)
    states = {c.state for c in correspondence.values()}

    if CorrespondenceState.AMBIGUOUS in states:
        return SymmetryState.AMBIGUOUS

    if _seam_violates_plane(mesh, definition):
        return SymmetryState.VIOLATED

    if CorrespondenceState.UNPAIRED in states:
        return SymmetryState.PARTIAL

    return SymmetryState.VALID
