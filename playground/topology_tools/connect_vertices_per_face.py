"""Vertex Connect mode — Wings-style per-face cyclic pairing (AD-017 §1.5).

Context: Vertex mode, 2+ vertices selected.
Pairing: for each face (snapshot at start, ascending FaceId) with ≥ 2 selected
vertices: collect selected vertices in boundary order, form cyclic consecutive
pairs, skip adjacent pairs. Connect each pair via the lowest shared face where
they are non-adjacent (connect_in_shared_face). Vertices without a partner are
ignored. Nothing connectable → no-op, no history entry.
Residue: selection and mode unchanged.
"""

from __future__ import annotations

from core import VertexId
from core.operations.topology import MeshStateCommand

from playground.topology_tools.topology_points import connect_in_shared_face


class VertexConnectError(Exception):
    pass


def _pairs_for_face(mesh, face_id, selected: set[VertexId]) -> list[tuple[VertexId, VertexId]]:
    """Return cyclic consecutive pairs of selected vertices in boundary order, adjacent skipped."""
    boundary = mesh.face_vertices(face_id)
    on_face = [v for v in boundary if v in selected]
    if len(on_face) < 2:
        return []
    n_on = len(on_face)
    m_b = len(boundary)
    pairs = []
    for i in range(n_on):
        a = on_face[i]
        b = on_face[(i + 1) % n_on]
        ia = boundary.index(a)
        ib = boundary.index(b)
        dist = (ib - ia) % m_b
        if dist == 1 or dist == m_b - 1:
            continue  # adjacent — skip per AD-017
        pairs.append((a, b))
    return pairs


def connect_vertices_per_face(scene, vertex_ids: set[VertexId]) -> list:
    """Connect selected vertices using per-face Wings-style cyclic pairing.

    Returns list of created EdgeIds. Returns [] if nothing connectable
    (no history entry in that case).

    Raises VertexConnectError on invalid input.
    """
    selected = set(vertex_ids)
    if len(selected) < 2:
        raise VertexConnectError("Vertex Connect benötigt mindestens 2 Vertices.")

    mesh = scene.mesh
    for vid in selected:
        if not mesh.is_valid_vertex(vid):
            raise VertexConnectError(f"Unbekannter Vertex: {vid!r}")

    before = mesh.export_state()
    snapshot_faces = sorted(mesh.all_face_ids(), key=int)

    created = []
    for fid in snapshot_faces:
        if not mesh.is_valid_face(fid):
            continue
        pairs = _pairs_for_face(mesh, fid, selected)
        for a, b in pairs:
            if not mesh.is_valid_vertex(a) or not mesh.is_valid_vertex(b):
                continue
            eid = connect_in_shared_face(mesh, a, b)
            if eid is not None:
                created.append(eid)

    if not created:
        # No geometry created — idempotent no-op, no history entry
        mesh.load_state(before)
        return []

    scene.history.push(
        MeshStateCommand(
            mesh=mesh,
            before_state=before,
            after_state=mesh.export_state(),
            description="Vertex Connect",
        )
    )
    return created
