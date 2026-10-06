"""Delete / Dissolve (WP Delete/Dissolve, `docs/WP_DELETE_DISSOLVE_PLAN.md`).

Production-first, no Lab (plan header, M5). Caller-side composition of the
Core primitives `Mesh.delete_vertices/delete_edges/delete_faces` and
`Mesh.dissolve_vertex/dissolve_edges/dissolve_faces`, with the same
snapshot-before / mutate / snapshot-after / push-one-`MeshStateCommand` shape
as `split.py`.

Contract: exactly one `MeshStateCommand` per change; a refusal (`MeshError`
from Core) or a no-op leaves mesh and history untouched. Vertex Dissolve is
the only multi-step case (one `dissolve_vertex` per selected vertex, in ID
order); a refusal in a later step restores the snapshot (ID counters stay
forward, AD-001 - same as `Application.apply_mesh_change`).
"""

from __future__ import annotations

from core import FaceId, SelectionMode
from core.mesh import MeshError
from core.operations.topology import MeshStateCommand

_NOUNS = {
    SelectionMode.VERTEX: "Vertices",
    SelectionMode.EDGE: "Edges",
    SelectionMode.FACE: "Faces",
}


class RemovalRefused(ValueError):
    """Core refused the removal; mesh and history are unchanged."""


def removal_label(mode: SelectionMode, *, dissolve: bool, cleanup: bool) -> str:
    """History description / status label, e.g. "Dissolve Edges (no cleanup)"."""
    label = f"{'Dissolve' if dissolve else 'Delete'} {_NOUNS[mode]}"
    if dissolve and not cleanup and mode is not SelectionMode.VERTEX:
        label += " (no cleanup)"
    return label


def remove_selected(
    scene, mode: SelectionMode, ids, *, dissolve: bool, cleanup: bool
) -> list[FaceId] | None:
    """Deletes or dissolves `ids` (elements of `mode`) and pushes one
    `MeshStateCommand`.

    `cleanup` only matters for Edge/Face Dissolve (§0.2.2); Vertex Dissolve has
    no variant and ignores it. Returns the new faces (Dissolve; empty for
    Delete and Vertex Dissolve without a merge), or None if nothing changed
    (no history entry). Raises `RemovalRefused` with the Core message.
    """
    mesh = scene.mesh
    ordered = sorted(ids, key=int)
    before = mesh.export_state()
    new_faces: list[FaceId] = []
    try:
        if not dissolve:
            {
                SelectionMode.VERTEX: mesh.delete_vertices,
                SelectionMode.EDGE: mesh.delete_edges,
                SelectionMode.FACE: mesh.delete_faces,
            }[mode](ordered)
        elif mode is SelectionMode.VERTEX:
            for vid in ordered:
                face = mesh.dissolve_vertex(vid)
                if face is not None:
                    new_faces.append(face)
        elif mode is SelectionMode.EDGE:
            new_faces = mesh.dissolve_edges(ordered, cleanup=cleanup)
        else:
            new_faces = mesh.dissolve_faces(ordered, cleanup=cleanup)
    except MeshError as exc:
        mesh.load_state(before)
        raise RemovalRefused(str(exc)) from exc
    after = mesh.export_state()
    if after == before:
        return None
    scene.history.push(
        MeshStateCommand(
            mesh=mesh,
            before_state=before,
            after_state=after,
            description=removal_label(mode, dissolve=dissolve, cleanup=cleanup),
        )
    )
    # A later vertex dissolve can merge a face an earlier one created.
    return [f for f in new_faces if mesh.is_valid_face(f)]
