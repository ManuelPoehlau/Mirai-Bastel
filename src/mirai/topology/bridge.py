"""Bridge (AD-031 P5, §5): `n` quads between two closed borders of `n` points each. Texts `PROVISIONAL`.

The kernel over the public Mesh API, without app state; `Application.bridge_plan` / `bridge_borders` add the gates,
hidden geometry and the one `_mesh_transaction`.

- `plan_bridge(mesh, mode, ids)` is read-only: the borders the selection touches (`border.selection_border_loops`,
  Cap's input), exactly two, closed, with the same number of points (O-11, `PROVISIONAL`); each
  loop is put into a canonical order that depends on the mesh only - Cap's winding (against its neighbour faces), started
  at its smallest `VertexId`, the loop with the smaller first id first (two closed borders never share a point: a
  point on a closed border has exactly two border edges) - so the plan is the same for every selection
  that touches the two borders. The pairing is the one with the minimal sum of squared distances over both directions
  and all `n` rotations (ties: the forward direction, then the smaller rotation). Each quad's winding comes from the
  neighbour faces: it must use every border edge against the face already on it; both loops must ask for the same
  winding, else refused ("normals disagree"). A rung that already is an edge with a face is refused (it would get a
  third face).
- `bridge(mesh, plan)` adds the quads with `add_face(…, infer_uvs=False)`: **no new points** (point layers untouched),
  **no UVs** (D8: Cap's inference would stretch across two UV islands, F11), **no region** (D9: a created face without a
  removed parent inherits nothing, F6). Afterwards every border and rung edge must have exactly two faces; otherwise
  `BridgeRefused` and the caller's transaction rolls back exactly.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable

from core import FaceId, Mesh, SelectionMode, VertexId
from core.mesh import MeshError

from .border import BorderLoop, cap_winding, selection_border_loops

LABEL = "Bridge"

Quad = tuple[VertexId, VertexId, VertexId, VertexId]
#: `accept(first, partner)`: whether the pairing `first[i]` ↔ `partner[i]` may be used (P6, symmetric Bridge).
Accept = Callable[[list[VertexId], list[VertexId]], bool]

#: The refusal when `accept` takes no pairing (the symmetric planner replaces it with its own text).
TEXT_NO_PAIRING = f"{LABEL}: no allowed pairing of the two borders"


class BridgeRefused(MeshError):
    """The bridge would leave topology Mirai does not allow; raised inside the step so the caller rolls back."""


@dataclasses.dataclass(frozen=True)
class BridgePlan:
    """What a bridge would add, read-only. `loops`: the two borders in canonical order (see the module text); `quads`:
    the new faces, wound against the neighbour faces, quad `i` between `loops[0][i]`, `loops[0][i+1]` and their
    partners; `refusal`: the first reason it cannot run (None = it can); `reversed_` / `offset`: the chosen pairing
    (`loops[0][i]` ↔ `loops[1][(offset ± i) mod n]`). A symmetric plan (`symmetric_ops.plan_symmetric_bridge`, AD-031
    P6) that mirrors the bridge appends the two mirror borders to `loops` and the mirror quads to `quads`."""

    loops: tuple[tuple[VertexId, ...], ...]
    quads: tuple[Quad, ...]
    refusal: str | None
    reversed_: bool = False
    offset: int = 0

    @property
    def points(self) -> int:
        return len(self.quads)


def plan_bridge(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> BridgePlan:
    """The bridge between the two borders the selection touches, or the first refusal. Read-only."""
    return plan_bridge_loops(mesh, selection_border_loops(mesh, mode, ids))


def plan_bridge_loops(mesh: Mesh, loops: list[BorderLoop], accept: Accept | None = None) -> BridgePlan:
    """The bridge between `loops` (the borders to join; exactly two are needed), or the first refusal. Read-only.
    `accept(first, partner)` (AD-031 P6, the symmetric planner) restricts the pairing to the ones it accepts - the
    closest accepted one is taken; none accepted refuses with `TEXT_NO_PAIRING`."""
    if not loops:
        return _refused(f"{LABEL}: select points or edges of two open borders (B selects a whole border)")
    if len(loops) == 1:
        return _refused(f"{LABEL}: only one border selected - select a point or edge of a second border too")
    if len(loops) > 2:
        return _refused(f"{LABEL}: the selection touches {len(loops)} borders - select exactly two")
    if not all(loop.closed for loop in loops):
        return _refused(f"{LABEL}: a border is not closed (several borders meet at one point)")
    a, b = (len(loop.vertices) for loop in loops)
    if a != b:
        return _refused(f"{LABEL}: the borders have {a} and {b} points - Bridge needs the same number")
    if a < 3:
        return _refused(f"{LABEL}: a border has fewer than three points")
    first, second = sorted((_canonical(mesh, loop) for loop in loops), key=lambda vs: int(vs[0]))
    pairing = _pairing(mesh, first, second, accept)
    if pairing is None:
        return BridgePlan((tuple(first), tuple(second)), (), TEXT_NO_PAIRING)
    reversed_, offset = pairing
    n = len(first)
    partner = [second[(offset - i) % n] if reversed_ else second[(offset + i) % n] for i in range(n)]
    base = [(first[i], first[(i + 1) % n], partner[(i + 1) % n], partner[i]) for i in range(n)]
    flip_first = {_uses_forward(mesh, q[0], q[1]) for q in base}  # the face on a_i-a_i+1 uses it as the quad would
    flip_second = {_uses_forward(mesh, q[2], q[3]) for q in base}
    loops_out = (tuple(first), tuple(second))
    if len(flip_first) != 1 or len(flip_second) != 1:
        return BridgePlan(loops_out, (), f"{LABEL}: the faces along a border are not oriented alike", reversed_, offset)
    if flip_first != flip_second:
        return BridgePlan(
            loops_out, (), f"{LABEL}: the normals of the two sides disagree - flip one part first", reversed_, offset
        )
    flip = flip_first.pop()
    quads = tuple(tuple(reversed(q)) if flip else q for q in base)
    for i in range(n):
        rung = _edge_between(mesh, first[i], partner[i])
        if rung is not None and mesh.edge_faces(rung):
            return BridgePlan(
                loops_out, (), f"{LABEL}: points {int(first[i])} and {int(partner[i])} are already joined by a face",
                reversed_, offset,
            )
    return BridgePlan(loops_out, quads, None, reversed_, offset)  # type: ignore[arg-type]


def bridge(mesh: Mesh, plan: BridgePlan) -> list[FaceId]:
    """Adds the quads of `plan` (made by `plan_bridge` on this mesh, without a refusal) without UVs; returns the new
    faces in quad order. Raises `BridgeRefused` when an edge of the bridge does not end with exactly two faces (the
    caller rolls back). Call it inside a recording (`begin_change`)."""
    if plan.refusal is not None:
        raise BridgeRefused(plan.refusal)
    faces = [mesh.add_face(list(q), infer_uvs=False) for q in plan.quads]
    for q in plan.quads:
        for u, v in zip(q, q[1:] + q[:1]):
            edge = _edge_between(mesh, u, v)
            if edge is None or len(mesh.edge_faces(edge)) != 2:
                raise BridgeRefused(f"{LABEL}: an edge of the bridge would not join exactly two faces - nothing changed")
    return faces


# -- helpers ----------------------------------------------------------------------------------------------------------


def _refused(text: str) -> BridgePlan:
    return BridgePlan((), (), text)


def _canonical(mesh: Mesh, loop: BorderLoop) -> list[VertexId]:
    """Cap's winding (against the neighbour faces), started at the smallest id: independent of the selection."""
    ordered = cap_winding(mesh, loop)
    k = min(range(len(ordered)), key=lambda i: int(ordered[i]))
    return ordered[k:] + ordered[:k]


def _pairing(
    mesh: Mesh, first: list[VertexId], second: list[VertexId], accept: Accept | None = None
) -> tuple[bool, int] | None:
    """(reversed, offset) with the minimal Σ|a_i − b_σ(i)|² over both directions and every rotation (ties: forward,
    then the smaller offset), among the pairings `accept` takes (all without it; None when it takes none). O(n²) for
    loops of `n` points."""
    pa = [mesh.vertex_position(v) for v in first]
    pb = [mesh.vertex_position(v) for v in second]
    n = len(pa)
    best: tuple[float, int, int] | None = None
    for direction in (0, 1):
        for k in range(n):
            if accept is not None and not accept(
                first, [second[(k - i) % n if direction else (k + i) % n] for i in range(n)]
            ):
                continue
            cost = 0.0
            for i in range(n):
                p, q = pa[i], pb[(k - i) % n if direction else (k + i) % n]
                cost += (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
            key = (cost, direction, k)
            if best is None or key < best:
                best = key
    if best is None:
        return None
    return bool(best[1]), best[2]


def _edge_between(mesh: Mesh, u: VertexId, v: VertexId):
    for e in mesh.vertex_edges(u):
        if v in mesh.edge_vertices(e):
            return e
    return None


def _uses_forward(mesh: Mesh, u: VertexId, v: VertexId) -> bool:
    """True when the one face on border edge u-v runs u -> v (the new quad must then run v -> u)."""
    edge = _edge_between(mesh, u, v)
    (face,) = mesh.edge_faces(edge)
    boundary = mesh.face_vertices(face)
    i = boundary.index(u)
    return boundary[(i + 1) % len(boundary)] == v
