"""Modeling Enablement (WP-AP-Enablement-01) — Split Edge.

Kein neues History-Konzept: dieselbe manuelle Snapshot-Command-Bauweise,
die bereits produktiv in tests/test_topology_history.py::run_as_command
verifiziert ist (Undo/Redo-Contract inkl. ID-Kontinuität). Adaptiert aus
dem V1-Experiment (experiments/mirai_bastel_viewport_V1/viewport/
topology_tools.py::split_selected_edge), aber gegen Production-`src/core`
statt gegen den V1-Core-Fork — die V1-Tool-Lifecycle-Basisklasse und die
V1-eigene `_SnapshotCommand` werden bewusst NICHT übernommen, weil
`core.operations.topology.MeshStateCommand` bereits dasselbe leistet.

Scope: ausschließlich Split Edge. Kein Collapse/Connect/Extrude, keine
Aktivierungs-/Terminierungsvarianten (das ist AP-05-Forschung). Kein
Eingriff in src/core oder src/viewport — nur Aufrufer-seitiger Adapter.
"""

from __future__ import annotations

from core import EdgeId
from core.operations.topology import MeshStateCommand


def split_selected_edge(scene, edge_id: EdgeId) -> tuple:
    """Splittet eine Edge und pusht genau einen MeshStateCommand.

    Reine Aufrufer-seitige Komposition aus bereits validierten
    Production-Bausteinen (Mesh.split_edge, Mesh.export_state/load_state,
    MeshStateCommand, HistoryStack.push) — keine neue Mutation, keine
    neue History-Logik.

    Gibt (new_vertex_id, edge_a, edge_b) zurück, wie Mesh.split_edge().
    Wirft dieselbe Exception wie Mesh.split_edge() bei ungültiger edge_id
    (kein Push in diesem Fall, da before/after dann nie verglichen wird).
    """
    mesh = scene.mesh
    before = mesh.export_state()
    result = mesh.split_edge(edge_id)
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
