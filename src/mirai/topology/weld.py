"""Weld (AD-031 P4, §4): selected, unconnected points that lie within a distance fall into one point per group.

The kernel over the public Mesh API, without app state; `Application.weld_plan` / `weld_vertices` add the threshold
in world space, hidden geometry (W10), the gates and the one `_mesh_transaction`. Texts `PROVISIONAL`.

- `plan_weld(mesh, vertices, distance)` is read-only: the groups (W1, W2: connected components of pairs within
  `distance` found through a spatial hash, every pair of a group within it - a clique), the first refusal by W2-W4
  and W6, predicted on the face boundaries the weld touches before anything changes, and the survivors where separate
  fans of faces would meet (W5, reported: Manu 2026-11-10 "Change W5" - a seam may be welded point by point).
- `weld(mesh, plan)` changes the mesh: per group the helper edges as a star from the group's smallest id (W8:
  `add_edge(min, v)`, ascending), then **one** `core.operations.collapse_elements` over all groups - its group rule
  writes the centroid of the original positions (summed in ascending-id order) and the per-layer group mean
  (`combine_values(kind, …, "mean")`) over the chain's pairwise results (W7, F9), so the result does not depend on the
  merge order. Afterwards W4 and the orientation of the merged edges are checked again on the real topology (W6); a
  failure raises `WeldRefused`, and the caller's transaction rolls the mesh back exactly.

Distances are compared in the mesh's own (object) space: the caller converts the world threshold (`t / s`, uniform
scale, AD-021 Q-4). A pair is "within" the distance when `|p - q| <= distance`.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable

from core import EdgeId, FaceId, Mesh, VertexId
from core.mesh import MeshError
from core.operations.collapse import collapse_elements

LABEL = "Weld"


class WeldRefused(MeshError):
    """The weld would leave topology Mirai does not allow (W4, W6); raised inside the step so the caller's transaction
    rolls the mesh back exactly. `str(exc)` says why."""


@dataclasses.dataclass(frozen=True)
class WeldPlan:
    """What a weld would merge, read-only. `groups`: each sorted by id (the first is the survivor, W8), at least two
    points, ordered by their first id; points within the distance of no other selected point are in none. `refusal`:
    the first reason it cannot run (None = it can). `merged_edges`: the vertex pairs (after the weld) where two
    original edges become one (W4, W6). `bowties`: the survivors where separate fans of faces would meet after the weld
    (W5: allowed and reported - the parts touch at that point only until the neighbouring points are welded too).
    `threshold`: the world-space distance the caller planned with (the kernel itself compares in object space; None
    when the kernel was called directly)."""

    groups: tuple[tuple[VertexId, ...], ...]
    refusal: str | None
    merged_edges: frozenset[frozenset[VertexId]] = frozenset()
    threshold: float | None = None
    bowties: tuple[VertexId, ...] = ()

    @property
    def points(self) -> int:
        return sum(len(g) for g in self.groups)


def plan_weld(mesh: Mesh, vertices: Iterable[VertexId], distance: float) -> WeldPlan:
    """The groups of `vertices` (invalid ids ignored; the order of `vertices` does not matter, W1) within `distance`
    (object space), the first refusal by W2-W4 / W6 and the W5 survivors. Read-only. A spatial hash with cell `distance` finds the pairs (each
    point looks at the 27 cells around it; no O(n²) scan over the selection)."""
    if not (isinstance(distance, (int, float)) and math.isfinite(distance) and distance > 0.0):
        return WeldPlan((), f"{LABEL}: the distance must be a number above 0")
    ids = sorted({v for v in vertices if mesh.is_valid_vertex(v)}, key=int)
    limit = distance * distance
    pos = {v: mesh.vertex_position(v) for v in ids}
    cells: dict[tuple[int, int, int], list[VertexId]] = {}
    parent = {v: v for v in ids}

    def find(v: VertexId) -> VertexId:
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for v in ids:
        p = pos[v]
        key = tuple(math.floor(c / distance) for c in p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for w in cells.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        if _dist2(p, pos[w]) <= limit:
                            a, b = find(v), find(w)
                            if a != b:
                                parent[max(a, b, key=int)] = min(a, b, key=int)
        cells.setdefault(key, []).append(v)  # type: ignore[arg-type]

    members: dict[VertexId, list[VertexId]] = {}
    for v in ids:
        members.setdefault(find(v), []).append(v)
    groups = tuple(sorted((tuple(g) for g in members.values() if len(g) > 1), key=lambda g: int(g[0])))
    if not groups:
        return WeldPlan((), None)
    for group in groups:
        text = _chain_refusal(group, pos, limit) or _connected_refusal(mesh, group)
        if text is not None:
            return WeldPlan(groups, text)
    rep = {v: g[0] for g in groups for v in g}
    cycles, merged = _predicted_cycles(mesh, rep)
    survivors = {g[0] for g in groups}
    text = _result_refusal(cycles, survivors, merged, duplicates=True)
    return WeldPlan(groups, text, merged, bowties=_bowties(cycles, survivors))


def weld(mesh: Mesh, plan: WeldPlan) -> list[VertexId]:
    """Welds the groups of `plan` (made by `plan_weld` on this mesh, without a refusal); returns the survivors in group
    order - each the group's smallest id (W8). Raises `WeldRefused` (or `CollapseRefused`) when the result breaks W4 or
    W6; the caller rolls back. Call it inside a recording (`begin_change`)."""
    if plan.refusal is not None:
        raise WeldRefused(plan.refusal)
    groups = plan.groups
    if not groups:
        return []
    helpers: list[EdgeId] = []
    for group in groups:
        first = group[0]
        helpers.extend(mesh.add_edge(first, v) for v in group[1:])  # W8: the star from the smallest id, ascending
    members = [v for g in groups for v in g]
    survivors = collapse_elements(mesh, members, helpers)
    if survivors != [g[0] for g in groups]:
        raise WeldRefused(f"{LABEL}: unexpected survivor - nothing changed")
    cycles = {
        f: list(mesh.face_vertices(f))
        for s in survivors for e in mesh.vertex_edges(s) for f in mesh.edge_faces(e)
    }
    text = _result_refusal(cycles, set(survivors), plan.merged_edges, duplicates=False)
    if text is not None:
        raise WeldRefused(text)
    return survivors


def differing_points(mesh: Mesh, groups: Iterable[tuple[VertexId, ...]]) -> int:
    """W11: how many points of `groups` are averaged with a differing value of some point layer (the H3 border effect:
    a target or weight that differs across the seam is averaged at the merged point). Read-only, before the weld."""
    lids = list(mesh.point_layer_ids())
    if not lids:
        return 0
    count = 0
    for group in groups:
        if any(len({_hashable(mesh.layer_value(lid, v)) for v in group}) > 1 for lid in lids):
            count += len(group)
    return count


def world_threshold_default(diagonal: float) -> float | None:
    """D10 (provisional reference, AD-031 §4.1): 0.001 × the world bounding-box diagonal of the edit mesh; None for a
    zero (or non-finite) diagonal - the field then waits for an entry. Not an artist-approved value (D10-v)."""
    if not math.isfinite(diagonal) or diagonal <= 0.0:
        return None
    return 0.001 * diagonal


# -- the checks ------------------------------------------------------------------------------------------------------


def _dist2(p, q) -> float:
    return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2


def _chain_refusal(group, pos, limit: float) -> str | None:
    """W2: every pair of a group within the distance; a chain whose ends are further apart is refused."""
    for i, a in enumerate(group):
        for b in group[i + 1:]:
            if _dist2(pos[a], pos[b]) > limit:
                return (
                    f"{LABEL}: points {int(a)} and {int(b)} are linked through a chain but further apart than the"
                    f" distance - lower it or select fewer points"
                )
    return None


def _connected_refusal(mesh: Mesh, group) -> str | None:
    """W3: no two points of a group share an edge or a face (merging those is Collapse)."""
    inside = set(group)
    for v in group:
        for e in mesh.vertex_edges(v):
            a, b = mesh.edge_vertices(e)
            if (b if a == v else a) in inside:
                return f"{LABEL}: points {int(a)} and {int(b)} share an edge - that is Collapse, not Weld"
            for f in mesh.edge_faces(e):
                others = inside.intersection(mesh.face_vertices(f)) - {v}
                if others:
                    return (
                        f"{LABEL}: points {int(v)} and {int(min(others, key=int))} share a face - that is Collapse,"
                        f" not Weld"
                    )
    return None


def _predicted_cycles(
    mesh: Mesh, rep: dict[VertexId, VertexId]
) -> tuple[dict[FaceId, list[VertexId]], frozenset[frozenset[VertexId]]]:
    """The boundaries of the faces around the welded points after the weld (W3 holds: no face holds two points of a
    group, so no boundary shrinks) and the pairs where two original edges become one."""
    touched = {f for v in rep for e in mesh.vertex_edges(v) for f in mesh.edge_faces(e)}
    cycles = {f: [rep.get(v, v) for v in mesh.face_vertices(f)] for f in touched}
    # Every edge that lands on a pair with a survivor has a welded point as an end, so the edges at the welded points
    # are all the sources.
    sources: dict[frozenset[VertexId], set[EdgeId]] = {}
    for v in rep:
        for e in mesh.vertex_edges(v):
            a, b = mesh.edge_vertices(e)
            sources.setdefault(frozenset((rep.get(a, a), rep.get(b, b))), set()).add(e)
    merged = frozenset(k for k, edges in sources.items() if len(edges) > 1)
    return cycles, merged


def _result_refusal(
    cycles: dict[FaceId, list[VertexId]],
    survivors: set[VertexId],
    merged: frozenset[frozenset[VertexId]],
    *,
    duplicates: bool,
) -> str | None:
    """W4 and W6 on the face boundaries around the survivors (predicted before, or read after the weld): no two faces on
    the same corners and no edge with more than two faces (W4), and every merged edge used in opposite directions by
    its two faces (W6). W5 (separate fans at a survivor) is not a refusal any more (`_bowties`)."""
    if duplicates:
        seen: set[frozenset[VertexId]] = set()
        for f in sorted(cycles, key=int):
            key = frozenset(cycles[f])
            if key in seen:
                return f"{LABEL}: two faces would fall onto the same points"
            seen.add(key)
    uses: dict[frozenset[VertexId], list[tuple[VertexId, VertexId]]] = {}
    for f in cycles:
        cycle = cycles[f]
        for a, b in zip(cycle, cycle[1:] + cycle[:1]):
            if a in survivors or b in survivors:
                uses.setdefault(frozenset((a, b)), []).append((a, b))
    for key, directed in uses.items():
        if len(directed) > 2:
            return f"{LABEL}: an edge would join more than two faces"
        if key in merged and len(directed) == 2 and directed[0] == directed[1]:
            return f"{LABEL}: the normals of the two sides disagree - flip one part first"
    return None


def _bowties(cycles: dict[FaceId, list[VertexId]], survivors: set[VertexId]) -> tuple[VertexId, ...]:
    """W5 (Manu 2026-11-10, "Change W5"): the survivors around which the faces form more than one fan after the weld - the
    parts touch there at one point only (a bowtie) until a neighbouring pair is welded too. Allowed, reported."""
    return tuple(
        s for s in sorted(survivors, key=int) if _fan_count(s, [cycles[f] for f in cycles if s in cycles[f]]) > 1
    )


def _fan_count(s: VertexId, cycles: list[list[VertexId]]) -> int:
    """How many fans the faces around `s` form: two faces are in one fan when they share an edge at `s`."""
    if len(cycles) < 2:
        return len(cycles)
    parent = list(range(len(cycles)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_neighbour: dict[VertexId, int] = {}
    for i, cycle in enumerate(cycles):
        k = cycle.index(s)
        for n in (cycle[k - 1], cycle[(k + 1) % len(cycle)]):
            j = by_neighbour.setdefault(n, i)
            a, b = find(i), find(j)
            if a != b:
                parent[a] = b
    return len({find(i) for i in range(len(cycles))})


def _hashable(value):
    if isinstance(value, (list, tuple)):
        return tuple(_hashable(x) for x in value)
    return value
