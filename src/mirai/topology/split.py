"""Split Edge (AD-017 §1.1/§1.3, WP-06 Slice B6).

Promoted from `playground/topology_ops.py::split_selected_edge` (WP-AP-
Enablement-01), unchanged in shape: same manual snapshot-before/mutate/
snapshot-after/push-one-MeshStateCommand composition already verified in
`tests/test_topology_history.py::run_as_command` (Undo/Redo contract incl.
ID continuity). `playground.topology_ops.split_selected_edge` now forwards
here so there is one implementation.
"""

from __future__ import annotations

from core import EdgeId
from core.operations.topology import MeshStateCommand


def split_selected_edge(scene, edge_id: EdgeId, t: float = 0.5) -> tuple:
    """Splits an edge and pushes exactly one MeshStateCommand.

    Pure caller-side composition of already-validated production building
    blocks (Mesh.split_edge, Mesh.export_state/load_state, MeshStateCommand,
    HistoryStack.push) — no new mutation, no new history logic.

    Returns (new_vertex_id, edge_a, edge_b), like Mesh.split_edge().
    Raises the same exception as Mesh.split_edge() on an invalid edge_id
    or out-of-range t (no push in that case, since before/after is never
    compared).
    """
    mesh = scene.mesh
    before = mesh.export_state()
    result = mesh.split_edge(edge_id, t)
    after = mesh.export_state()
    scene.history.push(
        MeshStateCommand(
            mesh=mesh,
            before_state=before,
            after_state=after,
            description="Split Edge",
        )
    )
    return result
