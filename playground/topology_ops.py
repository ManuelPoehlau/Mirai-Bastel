"""Modeling Enablement (WP-AP-Enablement-01) — Split Edge / Collapse Edge.

Split Edge was promoted to production in WP-06 Slice B6 (AD-017):
`split_selected_edge` now forwards to `mirai.topology.split`, which is the
single implementation shared with `src/mirai/application.py`. Kept here as
a stable Playground call site (many existing call sites and tests import
it from this module) — see `mirai.topology.split` for the implementation
docstring.

Collapse Edge is unchanged: not part of AD-017/B6 scope, still a Playground-
only adapter against Production-`src/core` (Mesh.collapse_edge), same
manual snapshot-command shape.
"""

from __future__ import annotations

from core import EdgeId
from core.operations.topology import MeshStateCommand
from mirai.topology.split import split_selected_edge  # noqa: F401 — re-exported


def collapse_selected_edge(scene, edge_id: EdgeId):
    """Kollabiert eine Edge und pusht genau einen MeshStateCommand.

    Mirrors `split_selected_edge` exactly in shape (WP-STAB-06): same
    snapshot-before/mutate/snapshot-after/push-one-MeshStateCommand
    composition, so `Ctrl+Z` after Collapse Edge reverts it symmetrically
    with Split/Connect (which already pushed history the same way).

    Gibt die VertexId des überlebenden Vertex zurück, wie Mesh.collapse_edge().
    Wirft dieselbe Exception wie Mesh.collapse_edge() bei ungültiger edge_id
    (kein Push in diesem Fall, da before/after dann nie verglichen wird).
    """
    mesh = scene.mesh
    before = mesh.export_state()
    result = mesh.collapse_edge(edge_id)
    after = mesh.export_state()
    scene.history.push(
        MeshStateCommand(
            mesh=mesh,
            before_state=before,
            after_state=after,
            description="Collapse Edge",
        )
    )
    return result
