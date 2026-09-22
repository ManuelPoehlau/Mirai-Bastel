"""Connect Edges — per-face semantics (Wings-3D-style). DISCOVERY VARIANT.

Lab override for the Artist test prepared in
docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md §6.
It does NOT replace connect_edges.py (the baseline) and is NOT used by
Loop Insert. Selected at runtime via the "connect" experiment family
(Tab → connect, M → cycle variant). No new key binding.

Semantics (understood from the Wings 3D source, not copied):
  1. Drop selected edges whose adjacent faces contain no other selected
     edge — they could never be connected.
  2. Split every remaining edge at its midpoint.
  3. Per ORIGINAL face, collect the new midpoints on its boundary in
     boundary order. 2 midpoints → connect them. >2 → connect consecutive
     midpoints cyclically (inner polygon). Face size does not matter.

Deliberate choices for the test (open questions D3/D4, not decisions):
  - Nothing connectable → TopologyToolError, same signalling as the
    baseline (Research Map: keep signalling constant across a comparison).
  - A midpoint that would stay unconnected → the whole operation is
    rejected and the mesh is restored (Wings would dissolve it instead;
    that needs a vertex-dissolve primitive we do not have).

Contract identical to connect_selected_edges(): exactly one
MeshStateCommand on success, mesh byte-identical on any rejection.
Only existing Core primitives are used (split_edge, connect_vertices).
"""

from __future__ import annotations

from core import EdgeId
from core.operations.topology import MeshStateCommand

from playground.topology_tools.connect_edges import TopologyToolError


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
        target = None
        for f in sorted(mesh.all_face_ids(), key=int):
            vs = mesh.face_vertices(f)
            if a in vs and b in vs:
                d = (vs.index(a) - vs.index(b)) % len(vs)
                if d not in (1, len(vs) - 1):
                    target = f
                    break
        if target is None:
            continue
        e, _, _ = mesh.connect_vertices(target, a, b)
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
