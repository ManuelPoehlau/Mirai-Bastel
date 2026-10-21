"""Split Edge (AD-017 §1.1/§1.3, WP-06 Slice B6).

Promoted from `playground/topology_ops.py::split_selected_edge` (WP-AP-
Enablement-01), unchanged in shape: record/mutate/push-one-command
(since 2026-10-21 a `MeshDeltaCommand` from the change journal instead of
two snapshots; Undo/Redo contract incl. ID continuity in
`tests/test_topology_history.py::run_as_command`). `playground.topology_ops.split_selected_edge` now forwards
here so there is one implementation.
"""

from __future__ import annotations

from core import EdgeId
from core.operations.topology import MeshDeltaCommand, record_mesh_change


def split_selected_edge(scene, edge_id: EdgeId, t: float = 0.5) -> tuple:
    """Splits an edge and pushes exactly one MeshDeltaCommand.

    Pure caller-side composition of already-validated production building
    blocks (Mesh.split_edge, the change journal, MeshDeltaCommand,
    HistoryStack.push) — no new mutation, no new history logic.

    Returns (new_vertex_id, edge_a, edge_b), like Mesh.split_edge().
    Raises the same exception as Mesh.split_edge() on an invalid edge_id
    or out-of-range t (no push in that case, since before/after is never
    compared).
    """
    mesh = scene.mesh
    delta, result = record_mesh_change(mesh, lambda: mesh.split_edge(edge_id, t))
    scene.history.push(MeshDeltaCommand(mesh=mesh, delta=delta, description="Split Edge"))
    return result
