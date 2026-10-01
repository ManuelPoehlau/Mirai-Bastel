"""Connect Edges — per-face semantics (Wings-3D-style).

Promoted from the Playground Topology Lab (Connect Lab KEEP verdict,
2026-09-21; AD-017 DECIDED 2026-09-22, WP-06 Slice B6). Originated as a
discovery variant for the Artist test prepared in
docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md §6, compared against
the rejected strip-semantics baseline (`playground/topology_tools/
connect_edges.py`, kept unreachable). `TopologyToolError` lives here now;
`connect_edges.py` imports it from here rather than the reverse.

Semantics (understood from the Wings 3D source, not copied):
  1. Drop selected edges whose adjacent faces contain no other selected
     edge — they could never be connected.
  2. Split every remaining edge at its midpoint.
  3. Per ORIGINAL face, collect the new midpoints on its boundary in
     boundary order. 2 midpoints → connect them. >2 → connect consecutive
     midpoints cyclically (inner polygon). Face size does not matter.
     Each pair is connected by `connect_in_shared_face`: the lowest-id face
     in which the chord is non-adjacent *and* lies entirely inside the face
     (F2, 2026-09-30 — no chord along the boundary, none out of a concave
     face). A pair with no such face stays unconnected (see below).

Deliberate choices (open questions D3/D4, not decisions):
  - Nothing connectable → TopologyToolError, same signalling as the
    baseline (Research Map: keep signalling constant across a comparison).
  - A midpoint that would stay unconnected (including one whose only chord
    would leave its face, F2) → the whole operation is rejected and the
    mesh is restored (Wings would dissolve it instead; that needs a
    vertex-dissolve primitive we do not have).

Contract: exactly one MeshStateCommand on success, mesh byte-identical on
any rejection. Only existing Core primitives are used (split_edge,
connect_vertices).
"""

from __future__ import annotations

from core import EdgeId
from core.operations.topology import MeshStateCommand

from .topology_points import connect_in_shared_face


class TopologyToolError(ValueError):
    pass


def _midpoint(mesh, eid) -> tuple:
    a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
    return tuple((x + y) / 2.0 for x, y in zip(a, b))


def _apply(mesh, selected: set) -> list[EdgeId]:
    """Mutates mesh. Caller is responsible for restore on exception."""
    keep = [
        e for e in selected
        if any((set(mesh.face_edges(f)) - {e}) & selected for f in mesh.edge_faces(e))
    ]
    if not keep:
        raise TopologyToolError(
            "Keine verbindbaren Kanten: ausgewählte Kanten teilen sich keine Face."
        )
    keep.sort(key=lambda e: (_midpoint(mesh, e), int(e)))  # deterministic

    original_faces = sorted({f for e in keep for f in mesh.edge_faces(e)}, key=int)

    mids: set = set()
    for e in keep:
        v, _, _ = mesh.split_edge(e)
        mids.add(v)

    pairs = []
    for f in original_faces:
        if not mesh.is_valid_face(f):
            continue
        on_face = [v for v in mesh.face_vertices(f) if v in mids]
        if len(on_face) == 2:
            pairs.append((on_face[0], on_face[1]))
        elif len(on_face) > 2:
            n = len(on_face)
            pairs += [(on_face[i], on_face[(i + 1) % n]) for i in range(n)]

    created: list[EdgeId] = []
    for a, b in pairs:
        e = connect_in_shared_face(mesh, a, b)
        if e is None:
            continue
        created.append(e)

    connected = {v for e in created for v in mesh.edge_vertices(e)}
    if mids - connected:
        raise TopologyToolError(
            "Connect (pro Face) abgebrochen: mindestens ein Mittelpunkt bliebe unverbunden."
        )
    return created


def connect_selected_edges_per_face(scene, edge_ids: set[EdgeId]) -> list[EdgeId]:
    selected = set(edge_ids)
    if len(selected) < 2:
        raise TopologyToolError("Connect Edges benötigt mindestens 2 Edges.")

    mesh = scene.mesh
    for eid in selected:
        if not mesh.is_valid_edge(eid):
            raise TopologyToolError(f"Unbekannte Edge: {eid!r}")
        if len(mesh.edge_faces(eid)) > 2:
            raise TopologyToolError(
                "Non-Manifold-Topologie liegt außerhalb des Connect-Edges-Scope."
            )

    before = mesh.export_state()
    try:
        created = _apply(mesh, selected)
    except TopologyToolError:
        mesh.load_state(before)
        raise
    except Exception as exc:
        mesh.load_state(before)
        raise TopologyToolError(
            f"Connect (pro Face) fehlgeschlagen – Mesh unverändert: {exc}"
        ) from exc

    scene.history.push(
        MeshStateCommand(
            mesh=mesh,
            before_state=before,
            after_state=mesh.export_state(),
            description="Connect Edges (pro Face)",
        )
    )
    return created
