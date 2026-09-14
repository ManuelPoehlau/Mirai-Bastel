"""Loop Insert (AP-05).

Erkennt den Edge Ring durch eine ausgewählte Start-Edge und verbindet
alle Ring-Kanten via connect_selected_edges() — das erzeugt einen neuen
Edge Loop senkrecht zum Ring.

Semantik:
  loop_insert(scene, start_edge)
      = edge_ring(start_edge)              ← reine Query
      → connect_selected_edges(ring_set)   ← Mutation + 1 History-Eintrag

Scope: reguläre kompatible Quad-Topologie (identisch mit Connect Edges §1).
Wirft LoopInsertError bei ungültiger Eingabe — Mesh bleibt dann unverändert.
"""

from __future__ import annotations

from core import EdgeId
from playground.topology_tools.loop_ring import edge_ring, LoopRingError
from playground.topology_tools.connect_edges import (
    connect_selected_edges,
    TopologyToolError as _ConnectEdgesError,
)


class LoopInsertError(ValueError):
    pass


def loop_insert(scene, start_edge: EdgeId) -> list[EdgeId]:
    """Fügt einen neuen Edge Loop durch den Ring von start_edge ein.

    Gibt die neu erzeugten Verbindungskanten zurück.
    Wirft LoopInsertError wenn kein gültiger Ring erkannt werden kann oder
    Connect Edges die Topologie ablehnt.
    """
    mesh = scene.mesh
    if not mesh.is_valid_edge(start_edge):
        raise LoopInsertError(f"Unbekannte Edge: {start_edge!r}")

    try:
        traversal = edge_ring(mesh, start_edge)
    except LoopRingError as exc:
        raise LoopInsertError(f"Ring-Erkennung fehlgeschlagen: {exc}") from exc

    ring = traversal.as_set()
    if len(ring) < 2:
        raise LoopInsertError(
            "Ring enthält zu wenige Kanten für Loop Insert (mindestens 2 erforderlich)."
        )

    try:
        return connect_selected_edges(scene, ring)
    except _ConnectEdgesError as exc:
        raise LoopInsertError(f"Loop Insert fehlgeschlagen: {exc}") from exc
