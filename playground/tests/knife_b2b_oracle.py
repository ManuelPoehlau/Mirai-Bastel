"""FROZEN ORACLE — the Knife Face Lab's B2b face constructions as they were before WP-KNIFE-01 S1.

Verbatim copy (only the imports adapted) of `split_face_path`, `close_loop_with_bridges` and
`close_loop_at_vertex` from `playground/experiments/knife_face/engine.py` at bb07f52 — the
`remove_face` + `add_vertex` + `add_face` stand-ins WP-KNIFE-00 compared `Mesh.split_face` against.
Since S1 the real constructions live in `mirai.topology.knife_resolve` and are built from
`Mesh.split_face`; this file is test data, the reference both are compared with
(`test_split_face_equivalence.py`). Used by no engine. Do not "fix" it.
"""

from __future__ import annotations

from core import EdgeId, FaceId, VertexId
from core.mesh import MeshError

from mirai.topology.face_geometry import FaceFrame, Position, dist3, face_problem, loop_matches_winding, v_dot

_TIE_DIGITS = 9


def _find_edge(mesh, a: VertexId, b: VertexId) -> EdgeId:
    for eid in mesh.vertex_edges(a):
        if set(mesh.edge_vertices(eid)) == {a, b}:
            return eid
    raise MeshError(f"internal: no edge between {a!r} and {b!r} after split")


def _cyclic_walk(seq: list, i: int, j: int, step: int = 1) -> list:
    """Walk `seq` cyclically from index `i` to index `j` (inclusive),
    stepping by `step` (+1 forward / -1 backward), wrapping with `% n`."""
    n = len(seq)
    out = []
    k = i
    while True:
        out.append(seq[k])
        if k == j:
            break
        k = (k + step) % n
    return out


def split_face_path(mesh, face_id: FaceId, a: VertexId, b: VertexId, positions: list[Position]):
    """LAB STAND-IN for a possible Core `split_face` primitive (discovery §3
    "B2c sketch") - split `face_id` along a path a -> positions... -> b, both
    `a` and `b` existing boundary vertices of `face_id` (adjacent allowed,
    unlike `Mesh.connect_vertices` - that is exactly what makes FC3/FC4
    possible here).

    Adapted from `experiments/topology/knife_face_cut_probe.py::split_face_path`
    (same B2b construction: remove_face + add_vertex + add_face): the boundary
    is partitioned into its two arcs a->b and b->a via a cyclic walk (correct
    for every boundary order, including a/b adjacent through the wrap - the
    probe's own index-slice-with-swap turns out to already be a correct,
    equivalent normalization; the cyclic walk here is written out explicitly
    because it is what this file's own reasoning was checked against).

    H7: `Mesh.add_face` does not reject repeated boundary vertices - checked
    here explicitly (both resulting loops, plus the path itself).

    Returns (new_vertex_ids, face_1, face_2, path_edge_ids) - `face_1` is the
    side running a -> b in boundary order (matches the B2c sketch's stated
    convention); `path_edge_ids` are the k+1 new edges a-p0-p1-...-pk-b, in
    that order.
    """
    if a == b:
        raise MeshError("split_face_path: a and b must be distinct vertices")
    boundary = mesh.face_vertices(face_id)
    if a not in boundary or b not in boundary:
        raise MeshError("split_face_path: a, b must be boundary vertices of face_id")

    new_vs = [mesh.add_vertex(p) for p in positions]
    chain = [a] + new_vs + [b]
    if len(set(chain)) != len(chain):
        raise MeshError("split_face_path: cut path revisits a vertex")

    i, j = boundary.index(a), boundary.index(b)
    seg_ab = _cyclic_walk(boundary, i, j)      # a .. b, forward
    seg_ba = _cyclic_walk(boundary, j, i)      # b .. a, forward
    loop1 = seg_ab + list(reversed(new_vs))    # face 1: a -> b along boundary, back through the path
    loop2 = seg_ba + list(new_vs)              # face 2: b -> a along boundary, forward through the path

    for name, loop in (("1", loop1), ("2", loop2)):
        if len(loop) < 3 or len(set(loop)) != len(loop):
            raise MeshError(f"split_face_path: face {name} degenerate ({loop!r})")

    mesh.remove_face(face_id)
    f1 = mesh.add_face(loop1)
    f2 = mesh.add_face(loop2)
    path_edges = [_find_edge(mesh, u, v) for u, v in zip(chain, chain[1:])]
    return new_vs, f1, f2, path_edges


def close_loop_with_bridges(
    mesh, face_id: FaceId, loop_positions: list[Position],
    i1: int, bv1: VertexId, i2: int, bv2: VertexId,
):
    """LAB STAND-IN: close an interior loop (>=3 points) inside `face_id` by
    bridging it to the boundary with 2 edges (spec §2 "closed shape stand-in").

    Splits `face_id` into exactly 3 faces (spec: "3 pieces in a quad"):
      - the loop itself (a pure k-gon, all loop edges);
      - the wing between boundary-arc(bv1->bv2) and the loop arc between the bridge points on
        that side;
      - the wing between boundary-arc(bv2->bv1) and the loop arc on the other side;
    the two bridge edges (bv1-loop[i1], bv2-loop[i2]) each border both wings.

    Winding (Artist decision 2026-09-29, Task A; `FACE_HOLES_DISCOVERY.md` §6): the loop is
    first oriented like the parent face's boundary, whichever way it was clicked, so the inner
    face has the parent's orientation and the wings traverse every loop edge *against* the inner
    face (consistent interior edges) — they cover the ring, never the loop. `i1`/`i2` and the
    returned `loop_vs` / `loop_edges` keep the caller's (click) order; only the faces are built
    in the canonical order.

    This is a genuine 3-way split of one face - not two applications of
    `split_face_path` - because neither wing can be built without the other
    already existing (each bridge edge borders both of them, and the loop's
    own edges border the loop face and exactly one wing each). Written out
    directly (H7 checked per resulting loop) rather than composed.
    """
    k = len(loop_positions)
    if k < 3:
        raise MeshError("close_loop_with_bridges: needs >= 3 interior points")
    if i1 == i2 or bv1 == bv2:
        raise MeshError("close_loop_with_bridges: bridges must be distinct")
    boundary = mesh.face_vertices(face_id)
    if bv1 not in boundary or bv2 not in boundary:
        raise MeshError("close_loop_with_bridges: bridge vertices must be on face_id's boundary")

    reverse = not loop_matches_winding(loop_positions, [mesh.vertex_position(v) for v in boundary])
    loop_vs = [mesh.add_vertex(p) for p in loop_positions]
    order = list(range(k - 1, -1, -1)) if reverse else list(range(k))
    canon = [loop_vs[j] for j in order]                    # loop, wound like the parent
    c1, c2 = order.index(i1), order.index(i2)              # bridge points in canonical indices

    bi, bj = boundary.index(bv1), boundary.index(bv2)
    seg_ab = _cyclic_walk(boundary, bi, bj)                      # bv1 .. bv2, forward
    seg_ba = _cyclic_walk(boundary, bj, bi)                      # bv2 .. bv1, forward
    # Each wing runs its boundary arc forward, crosses to the loop, and comes back along the
    # loop arc *backward* (decreasing canonical index): the loop face walks the same edges
    # forward, so every loop edge is used once in each direction. The two arcs
    # (c2 down to c1, c1 down to c2) are complements of each other.
    arc_a = _cyclic_walk(canon, c2, c1, step=-1)                 # canon[c2] .. canon[c1], backward
    arc_b = _cyclic_walk(canon, c1, c2, step=-1)                 # canon[c1] .. canon[c2], backward

    face_inner = list(canon)
    face_a = seg_ab + arc_a
    face_b = seg_ba + arc_b

    for name, loop in (("inner", face_inner), ("A", face_a), ("B", face_b)):
        if len(loop) < 3 or len(set(loop)) != len(loop):
            raise MeshError(f"close_loop_with_bridges: face {name} degenerate ({loop!r})")

    mesh.remove_face(face_id)
    f_inner = mesh.add_face(face_inner)
    f_a = mesh.add_face(face_a)
    f_b = mesh.add_face(face_b)
    loop_edges = [_find_edge(mesh, loop_vs[idx], loop_vs[(idx + 1) % k]) for idx in range(k)]
    return loop_vs, f_inner, f_a, f_b, loop_edges


def close_loop_at_vertex(mesh, face_id: FaceId, x: VertexId, loop_positions: list[Position],
                         outside: set[VertexId] | None = None):
    """LAB STAND-IN: a loop x -> loop_positions -> x inside `face_id`, touching its boundary at the
    one vertex `x` only (a cut that crosses itself, or leaves a point and comes back to it —
    Artist decision 2026-09-30, option (a)). Built as its own face plus **one** bridge, the same
    H0 idea as the closed-shape stand-in: one boundary list per face cannot visit `x` twice, and
    one bridge from a loop point to another boundary vertex splits the pinched ring into two simple
    faces (a loop that touches nothing needs two, `close_loop_with_bridges`).

    Order- and direction-independent like the closed shape (Task A, 2026-09-29): the loop is wound
    like the parent; the bridge is the shortest one (loop point, boundary vertex other than `x`)
    that leaves every face simple and facing like the parent — ties by position, never by index.
    `outside`: vertices a bridge should go to first — the corners the Artist clicked on, not
    another loop's points (Artist play test 2026-09-30); the rest only if none of those works.

    Returns (loop_vertices, loop_face, ring_faces, loop_edges) — `loop_edges` in `loop_positions`
    order, x -> first ... last -> x. Raises MeshError (mesh possibly changed: the caller restores
    it) when the loop is degenerate or no bridge fits.
    """
    m = len(loop_positions)
    if m < 2:
        raise MeshError("close_loop_at_vertex: a loop needs >= 2 points besides its vertex")
    boundary = mesh.face_vertices(face_id)
    if x not in boundary:
        raise MeshError("close_loop_at_vertex: x must be on face_id's boundary")
    parent_normal = FaceFrame(mesh, face_id).normal
    i = boundary.index(x)
    outer = boundary[i:] + boundary[:i]                          # x, f1 .. f(n-1)
    n = len(outer)
    reverse = not loop_matches_winding([mesh.vertex_position(x)] + list(loop_positions),
                                       [mesh.vertex_position(v) for v in boundary])
    loop_vs = [mesh.add_vertex(p) for p in loop_positions]
    canon = loop_vs[::-1] if reverse else list(loop_vs)          # x, c1 .. cm wound like the parent
    # The ring walks the outer boundary from x round to x, then the loop against its own face
    # (cm .. c1). A bridge c(j) - f(i) splits that walk into two faces holding x once each.
    ring = outer + [x] + canon[::-1]
    mesh.remove_face(face_id)
    f_loop = mesh.add_face([x] + canon)
    candidates = []
    for j, c in enumerate(canon):
        pc = mesh.vertex_position(c)
        for bi in range(1, n):
            pb = mesh.vertex_position(outer[bi])
            first = 0 if outside is None or outer[bi] in outside else 1
            candidates.append((first, round(dist3(pc, pb), _TIE_DIGITS), tuple(pc), tuple(pb), j, bi))
    candidates.sort(key=lambda c: c[:4])
    base = mesh.export_state()
    for *_key, j, bi in candidates:
        ic = n + m - j                                           # canon[j] in `ring`
        face_p = ring[bi:ic + 1]
        face_q = ring[ic:] + ring[:bi + 1]
        if min(len(face_p), len(face_q)) < 3 or any(len(set(f)) != len(f) for f in (face_p, face_q)):
            continue
        try:
            fp, fq = mesh.add_face(face_p), mesh.add_face(face_q)
            ok = all(face_problem(mesh, f) is None and v_dot(FaceFrame(mesh, f).normal, parent_normal) > 0.0
                     for f in (f_loop, fp, fq))
        except MeshError:
            ok = False
        if ok:
            chain = [x] + loop_vs + [x]
            return loop_vs, f_loop, [fp, fq], [_find_edge(mesh, u, v) for u, v in zip(chain, chain[1:])]
        mesh.load_state(base)
    raise MeshError("close_loop_at_vertex: no bridge fits")
