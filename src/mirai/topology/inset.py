"""Inset (2026-10-29, Manu: "Inset (Polygons)", Grundfunktion; `PROVISIONAL`).

Hold `I` in face mode and drag: the selected faces get a ring of new faces along their outline and
the region shrinks inwards by the width (Blender Inset, region mode; `I` in edge mode stays Loop
Insert). Faces sharing an edge inset as one region; separate regions each get their own ring.

Topology (once, at the start of the drag): every vertex on the region's outline gets a copy, the
region's faces are rebuilt on the copies (inner vertices stay shared), and each outline edge gets
a wall quad between the old edge and the copied one. An outline edge on the mesh border gets its
wall too. The copy moves along the miter of its two outline edges, so the new inner edges run
parallel to the old ones at the width (`offset_build.miter`).

Refused before any mutation (status line): no face, a region without an outline (a closed shell)
and a region whose outline passes a vertex more than once (two faces touching only at a corner).

UVs (AD-026): the inner faces keep the UVs of their faces, a wall gets its face's UVs at its two
corners (a line in UV, as Extrude walls). Point layers: a copy takes its vertex's values.
"""

from __future__ import annotations

from dataclasses import dataclass

from core import FaceId, Mesh, VertexId

from .offset_build import OffsetBuild, OffsetRefused, collapse_width, face_normal, inward, miter

INSET_LABEL = "Inset"

#: The width stops at this fraction of the first width at which a region edge would shrink to zero
#: length (a quad's copies meeting in its middle; `PROVISIONAL`).
LIMIT_FRACTION = 0.98


class InsetRefused(OffsetRefused):
    """Inset cannot run on these faces; the message is the status line."""


@dataclass(frozen=True)
class InsetPlan:
    """The validated region: its faces and its outline as directed edges `(a, b, face)` in the
    winding of the region face that holds them, and per outline vertex its incoming / outgoing
    outline edge."""

    faces: frozenset[FaceId]
    outline: tuple[tuple[VertexId, VertexId, FaceId], ...]
    corners: dict[VertexId, tuple[tuple[VertexId, FaceId], tuple[VertexId, FaceId]]]


def plan_inset(mesh: Mesh, face_ids) -> InsetPlan:
    """Validate the region of `face_ids`. Pure; raises `InsetRefused`."""
    faces = frozenset(f for f in face_ids if mesh.is_valid_face(f))
    if not faces:
        raise InsetRefused(f"{INSET_LABEL}: select or hover a face (face mode)")
    outline: list[tuple[VertexId, VertexId, FaceId]] = []
    incoming: dict[VertexId, list[tuple[VertexId, FaceId]]] = {}
    outgoing: dict[VertexId, list[tuple[VertexId, FaceId]]] = {}
    for f in sorted(faces):
        boundary = mesh.face_vertices(f)
        n = len(boundary)
        for i, eid in enumerate(mesh.face_edges(f)):
            if sum(1 for g in mesh.edge_faces(eid) if g in faces) != 1:
                continue
            a, b = boundary[i], boundary[(i + 1) % n]
            outline.append((a, b, f))
            outgoing.setdefault(a, []).append((b, f))
            incoming.setdefault(b, []).append((a, f))
    if not outline:
        raise InsetRefused(f"{INSET_LABEL}: the selected faces have no outline (a closed shell)")
    corners = {}
    for v in outgoing.keys() | incoming.keys():
        ins, outs = incoming.get(v, []), outgoing.get(v, [])
        if len(ins) != 1 or len(outs) != 1:
            raise InsetRefused(
                f"{INSET_LABEL}: the selected faces touch at a corner only - select them as one patch or separately"
            )
        corners[v] = (ins[0], outs[0])
    return InsetPlan(faces=faces, outline=tuple(outline), corners=corners)


def build_inset(mesh: Mesh, plan: InsetPlan) -> OffsetBuild:
    """Build the inset topology of `plan` (new vertices at width 0). Returns the move of every copy;
    `faces` = the inner faces (the selection residue)."""
    normals = {f: face_normal(mesh, f) for f in plan.faces}
    pos = mesh.vertex_position

    moves = {}
    directions = {}
    for v, ((u, f_in), (w, f_out)) in plan.corners.items():
        p_in = inward(normals[f_in], pos(u), pos(v))
        p_out = inward(normals[f_out], pos(v), pos(w))
        if p_in is None or p_out is None:
            raise InsetRefused(f"{INSET_LABEL}: a selected face has an edge of zero length")
        directions[v] = miter(p_in, p_out)

    has_uvs = mesh.has_face_uvs()
    boundaries = {f: mesh.face_vertices(f) for f in plan.faces}
    uvs = {f: mesh.face_uvs(f) for f in plan.faces} if has_uvs else {}
    region_edges = {e for f in plan.faces for e in mesh.face_edges(f)}

    copy: dict[VertexId, VertexId] = {}
    keys = {}
    for v in sorted(plan.corners):
        copy[v] = mesh.add_vertex(pos(v), origin=((v, 1.0),))
        moves[copy[v]] = (pos(v), directions[v])
        keys[copy[v]] = (v,)

    for f in sorted(plan.faces):
        mesh.remove_face(f)
    for a, b, f in plan.outline:
        wall_uvs = None
        if uvs.get(f) is not None:
            corner = dict(zip(boundaries[f], uvs[f]))
            wall_uvs = (corner[a], corner[b], corner[b], corner[a])
        mesh.add_face([a, b, copy[b], copy[a]], wall_uvs, infer_uvs=False)
    inner = []
    for f in sorted(plan.faces):
        inner.append(mesh.add_face([copy.get(v, v) for v in boundaries[f]], uvs.get(f), infer_uvs=False))
    orphans = [e for e in region_edges if mesh.is_valid_edge(e) and not mesh.edge_faces(e)]
    if orphans:
        mesh.delete_edges(orphans)
    limit = LIMIT_FRACTION * collapse_width(mesh, {vid: d for vid, (_, d) in moves.items()})
    return OffsetBuild(moves=moves, keys=keys, limit=limit, faces=inner)

