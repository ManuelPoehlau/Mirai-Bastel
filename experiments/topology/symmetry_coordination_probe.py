"""Read-only probe for the AD-SYM-03 proposal (symmetric topology coordination).

Sibling of `symmetry_ops_probe.py` (Discovery). Answers three follow-up questions of
`docs/research/symmetry/SYMMETRY_PRODUCTION_OPERATIONS_DISCOVERY.md` that the AD needs evidence for:

  F. Seam edges *inside* Edge Connect / Delete / Dissolve selections (Discovery Q5), with and
     without a probe-local seam-maintenance rule (split seam edge -> its halves; dead seam id -> dropped).
  G. Exactness on planes other than x=0 (Discovery Q7 scope gap): a non-origin axis plane and an
     oblique plane. Is `mirror_position` an exact involution there, are t=0.5 midpoints exact, does a
     post-op snap restore pairing?
  H, I. `resolve_cross_face` mirror-equivariance on a tie-break path (Discovery Q4): a closed interior
     loop whose bridge choice is decided by the position tie-break.

Nothing here is a tool, a capability or a proposal for `src/`; helpers are local stand-ins (as in the
Discovery probe). In-memory only; no file is written, no repo state is touched.

Run from the repo root:  python experiments/topology/symmetry_coordination_probe.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for p in (REPO / "experiments", REPO / "examples", REPO, REPO / "src"):  # src/ first on sys.path
    sys.path.insert(0, str(p))

from core import SelectionMode  # noqa: E402
from core.mesh import SymmetryDefinition  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402
from mirai.symmetry import CorrespondenceState as C  # noqa: E402
from mirai.symmetry import mirror_position, symmetry_state, vertex_correspondence  # noqa: E402
from mirai.topology.connect_per_face import connect_selected_edges_per_face  # noqa: E402
from mirai.topology.delete_dissolve import RemovalRefused, remove_selected  # noqa: E402
from mirai.topology.knife_resolve import check_commit, resolve_cross_face  # noqa: E402
from mirai.topology.split import split_selected_edge  # noqa: E402
from symmetry_lab.lab_symmetry import definition_for_axis, derive_seam_edges  # noqa: E402
from symmetry_lab.lab_topology import topological_sides  # noqa: E402
from topology.symmetry_ops_probe import (  # noqa: E402
    load,
    partner_edge,
    partner_face,
    partner_vertex,
    plus_x_face,
    side,
    summary,
)

ASSETS = ("subd_cube", "head_basemesh")


def sides(mesh) -> str:
    return f"sides={topological_sides(mesh).component_count}"


def with_seam(mesh, seam) -> None:
    d = mesh.symmetry_definition
    mesh.symmetry_definition = SymmetryDefinition(d.plane_point, d.plane_normal, frozenset(seam))


def maintain_split_seam(mesh, dead_seam: dict) -> int:
    """Probe stand-in for the old Lab Knife P1 rule: a seam edge that died because it was split is
    replaced by its two halves. `dead_seam` maps a seam edge id to its endpoints captured before
    the op. Returns how many seam edges were replaced."""
    seam = set(mesh.symmetry_definition.seam_edges)
    replaced = 0
    for e, (a, b) in dead_seam.items():
        if mesh.is_valid_edge(e):
            continue
        halves = None
        for m in mesh.all_vertex_ids():
            ea = next((x for x in mesh.vertex_edges(m) if a in mesh.edge_vertices(x)), None)
            eb = next((x for x in mesh.vertex_edges(m) if b in mesh.edge_vertices(x)), None)
            if m not in (a, b) and ea is not None and eb is not None:
                halves = (ea, eb)
                break
        if halves is not None:
            seam.discard(e)
            seam.update(halves)
            replaced += 1
    with_seam(mesh, seam)
    return replaced


def drop_dead_seam(mesh) -> int:
    seam = mesh.symmetry_definition.seam_edges
    live = {e for e in seam if mesh.is_valid_edge(e)}
    with_seam(mesh, live)
    return len(seam) - len(live)


# -- F: seam edges inside selections ----------------------------------------------------


def seam_face_and_edges(mesh):
    """A +X face that has a seam edge, that seam edge, and the face edge opposite to it."""
    seam = mesh.symmetry_definition.seam_edges
    for f in mesh.all_face_ids():
        xs = [mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)]
        if max(xs) <= 0:
            continue
        edges = mesh.face_edges(f)
        for i, e in enumerate(edges):
            if e in seam and len(edges) == 4:
                return f, e, edges[(i + 2) % 4]
    raise LookupError("no +X quad with a seam edge")


def part_f(asset: str) -> None:
    print("F. seam edges inside selections (Discovery Q5)")

    def fresh():
        s = load(asset)
        return s, s.mesh, vertex_correspondence(s.mesh)

    s, m, c = fresh()
    _f, se, opp = seam_face_and_edges(m)
    expanded = {se, opp} | {partner_edge(m, c, x) for x in (se, opp)}
    side("seam edge's own partner", f"partner_edge(seam)==seam: {partner_edge(m, c, se) == se}; "
         f"expanded selection size={len(expanded)} (seam edge counted once)")

    s, m, c = fresh()
    connect_selected_edges_per_face(s, set(expanded))
    side("edge connect {seam, opp} expanded, raw", summary(m) + f" {sides(m)} history={len(s.history)}")

    s, m, c = fresh()
    ends = {se: m.edge_vertices(se)}
    connect_selected_edges_per_face(s, set(expanded))
    n = maintain_split_seam(m, ends)
    side("  + seam rule 'split -> halves'", summary(m) + f" {sides(m)} replaced={n}")

    s, m, c = fresh()
    ends = {se: m.edge_vertices(se)}
    split_selected_edge(s, se)
    n = maintain_split_seam(m, ends)
    side("split SEAM edge + 'split -> halves'", summary(m) + f" {sides(m)} replaced={n}")

    def rm(mode, ids, dissolve, label):
        s, m, c = fresh()
        try:
            remove_selected(s, mode, set(ids), dissolve=dissolve, cleanup=True)
        except RemovalRefused as exc:
            side(label, f"refused: {exc}")
            return
        raw = summary(m) + f" {sides(m)}"
        dropped = drop_dead_seam(m)
        side(label, raw)
        side("  + 'drop dead seam ids'", summary(m) + f" {sides(m)} dropped={dropped}")

    s, m, c = fresh()
    _f, se, opp = seam_face_and_edges(m)
    pe = partner_edge(m, c, opp)
    rm(SelectionMode.EDGE, {se}, False, "delete SEAM edge")
    rm(SelectionMode.EDGE, {se, opp, pe}, False, "delete {seam, opp} expanded")
    rm(SelectionMode.EDGE, {se, opp, pe}, True, "dissolve {seam, opp} expanded")
    g = plus_x_face(m, touching_seam=True)
    rm(SelectionMode.FACE, {g, partner_face(m, c, g)}, False, "delete seam-touching face expanded")


# -- G: exactness on non-origin and oblique planes ----------------------------------------


def transformed(asset: str, angle_deg: float, offset: float):
    """The asset rotated about Z by `angle_deg` and moved by `offset` along the rotated X axis,
    with the plane carried along (point = offset * n, normal = rotated X). The seam is the Lab E3
    seam derived *before* the transform (same edge ids). angle 0 / offset 0 = the Lab's x=0."""
    s = build_core_scene_from_obj(asset_path(asset))
    m = s.mesh
    seam = derive_seam_edges(m, "X")
    a = math.radians(angle_deg)
    ca, sa = (1.0, 0.0) if angle_deg == 0 else (math.cos(a), math.sin(a))
    n = (ca, sa, 0.0)
    for v in m.all_vertex_ids():
        x, y, z = m.vertex_position(v)
        m.set_vertex_position(v, (ca * x - sa * y + offset * ca, sa * x + ca * y + offset * sa, z))
    m.symmetry_definition = SymmetryDefinition((offset * ca, offset * sa, 0.0), n, frozenset(seam))
    return s


def involution_failures(mesh) -> int:
    d = mesh.symmetry_definition
    bad = 0
    for v in mesh.all_vertex_ids():
        p = mesh.vertex_position(v)
        if mirror_position(mirror_position(p, d.plane_point, d.plane_normal), d.plane_point, d.plane_normal) != p:
            bad += 1
    return bad


def resymmetrize_from_plus(mesh, ref_pairs: dict) -> int:
    """Set every -side vertex to mirror_position(partner on the + side) and every seam vertex to its
    projection onto the plane. `ref_pairs` (vertex -> partner, from the untransformed asset) gives
    the pairing, so this is the best a tolerance-free construction can do. Returns how many seam
    vertices are still not exactly on the plane after projection."""
    d = mesh.symmetry_definition
    off_plane = 0
    for v, q in ref_pairs.items():
        p = mesh.vertex_position(v)
        dist = sum((pi - oi) * ni for pi, oi, ni in zip(p, d.plane_point, d.plane_normal))
        if q == v:
            proj = tuple(pi - dist * ni for pi, ni in zip(p, d.plane_normal))
            mesh.set_vertex_position(v, proj)
            if sum((pi - oi) * ni for pi, oi, ni in zip(proj, d.plane_point, d.plane_normal)) != 0.0:
                off_plane += 1
        elif dist > 0:
            mesh.set_vertex_position(q, mirror_position(p, d.plane_point, d.plane_normal))
    return off_plane


def asym_pairs(mesh) -> int:
    """Vertices whose partner does not point back (p -> q but q -/-> p)."""
    corr = vertex_correspondence(mesh)
    return sum(1 for v, cv in corr.items()
               if cv.state is C.PAIRED and corr[cv.partner].partner != v)


def part_g(asset: str) -> None:
    print("G. exactness on other planes (Discovery Q7 scope gap)")
    ref = load(asset).mesh
    rc = vertex_correspondence(ref)
    ref_pairs = {v: partner_vertex(rc, v) for v in ref.all_vertex_ids() if partner_vertex(rc, v) is not None}
    f = plus_x_face(ref, touching_seam=False)
    pair = {ref.face_edges(f)[0], ref.face_edges(f)[2]}
    e = ref.face_edges(f)[0]
    pe = partner_edge(ref, rc, e)
    epair = pair | {partner_edge(ref, rc, x) for x in pair}

    for label, angle, offset in (("x=0 (Lab E1)", 0, 0.0), ("x=0.3 (non-origin axis)", 0, 0.3),
                                 ("oblique 30deg through origin", 30, 0.0), ("oblique 30deg, offset 0.3", 30, 0.3)):
        s = transformed(asset, angle, offset); m = s.mesh
        raw = f"{symmetry_state(m).value}/{involution_failures(m)}"
        off = resymmetrize_from_plus(m, ref_pairs)
        base = (f"raw state/involution-fails={raw}; after +side rebuild: {symmetry_state(m).value} "
                f"unpaired={sum(1 for x in vertex_correspondence(m).values() if x.state is C.UNPAIRED)} "
                f"asym-pairs={asym_pairs(m)} involution-fails={involution_failures(m)} seam-off-plane={off}")
        side(label, base)
        state0 = m.export_state()

        def unpaired_new(before_ids):
            corr = vertex_correspondence(m)
            new = [v for v in m.all_vertex_ids() if v not in before_ids]
            return sum(1 for v in new if corr[v].state is not C.PAIRED), len(new)

        ids0 = set(m.all_vertex_ids())
        connect_selected_edges_per_face(s, set(epair))
        u, n = unpaired_new(ids0)
        side("  edge connect expanded (t=.5 midpoints)", f"new vertices not PAIRED: {u}/{n}")
        m.load_state(state0)

        v1, _, _ = m.split_edge(e, 0.5); v2, _, _ = m.split_edge(pe, 0.5)
        u, n = unpaired_new(ids0)
        side("  split + partner split t=.5", f"new vertices not PAIRED: {u}/{n}")
        d = m.symmetry_definition
        m.set_vertex_position(v2, mirror_position(m.vertex_position(v1), d.plane_point, d.plane_normal))
        u, n = unpaired_new(ids0)
        corr = vertex_correspondence(m)
        side("  ... + snap partner := mirror(source)",
             f"new vertices not PAIRED: {u}/{n}; source->partner={corr[v1].state.value}, "
             f"partner->source={corr[v2].state.value}")
        m.load_state(state0)


# -- H: resolver tie-break equivariance -----------------------------------------------------


def part_h(asset: str) -> None:
    print("H. resolve_cross_face, closed interior loop (bridge chosen by the position tie-break)")
    s = load(asset); m = s.mesh; corr = vertex_correspondence(m)
    d = m.symmetry_definition
    f = plus_x_face(m, touching_seam=False)
    g = partner_face(m, corr, f)
    corners = [m.vertex_position(v) for v in m.face_vertices(f)]
    cen = tuple(sum(c[k] for c in corners) / len(corners) for k in range(3))
    loop = [tuple(cen[k] + 0.25 * (c[k] - cen[k]) for k in range(3)) for c in corners]
    path = [{"pid": i, "kind": "face", "face_id": f, "position": p} for i, p in enumerate(loop)]
    path += [{"kind": "break", "reason": "closed", "cyclic": True}]
    mirrored = [{"pid": 100 + i, "kind": "face", "face_id": g,
                 "position": mirror_position(p, d.plane_point, d.plane_normal)} for i, p in enumerate(loop)]
    mirrored += [{"kind": "break", "reason": "closed", "cyclic": True}]
    before = m.export_state()
    res = resolve_cross_face(m, path + mirrored, before)
    ok = check_commit(m, before).after_state is not None
    side("loop + mirrored loop, one resolve",
         f"applied={res.applied}/{res.runs} loops_built={getattr(res, 'loops_built', '?')} "
         f"closed_shapes={[x.built for x in getattr(res, 'closed_shapes', [])]} commit_ok={ok} | {summary(m)}")


def part_i() -> None:
    """Synthetic flat grid x in [-2, 2], y in [0, 2], plane x=0, seam = the x=0 edges. A square loop
    centred in a square face: all four loop points are equally far from their corners, so the first
    bridge point is decided by the position tie-break alone (`select_bridge`)."""
    from core import Mesh
    from mirai.topology.knife_resolve import select_bridge

    print("I. same, synthetic grid with a decisive four-way distance tie")
    for cx, cy in ((1.5, 0.5), (0.5, 1.5)):
        m, p = Mesh(), {}
        for r in range(3):
            for c in range(-2, 3):
                p[(r, c)] = m.add_vertex((float(c), float(r), 0.0))
        for r in range(2):
            for c in range(-2, 2):
                m.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
        seam = derive_seam_edges(m, "X")
        m.symmetry_definition = SymmetryDefinition((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), seam)
        corr = vertex_correspondence(m)
        f = next(f for f in m.all_face_ids()
                 if sorted({m.vertex_position(v)[0] for v in m.face_vertices(f)}) == [cx - 0.5, cx + 0.5]
                 and sorted({m.vertex_position(v)[1] for v in m.face_vertices(f)}) == [cy - 0.5, cy + 0.5])
        g = partner_face(m, corr, f)
        loop = [(cx + dx, cy + dy, 0.0) for dx, dy in ((-0.25, -0.25), (0.25, -0.25), (0.25, 0.25), (-0.25, 0.25))]
        mloop = [mirror_position(q, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)) for q in loop]
        b_src = select_bridge(m, m.face_vertices(f), loop)
        b_mir = select_bridge(m, m.face_vertices(g), mloop)
        src_pts = {loop[b_src[0]], loop[b_src[2]]}
        mir_pts = {mirror_position(mloop[b_mir[0]], (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
                   mirror_position(mloop[b_mir[2]], (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))}
        path = [{"pid": i, "kind": "face", "face_id": f, "position": q} for i, q in enumerate(loop)]
        path += [{"kind": "break", "reason": "closed", "cyclic": True}]
        path += [{"pid": 100 + i, "kind": "face", "face_id": g, "position": q} for i, q in enumerate(mloop)]
        path += [{"kind": "break", "reason": "closed", "cyclic": True}]
        before = m.export_state()
        res = resolve_cross_face(m, path, before)
        ok = check_commit(m, before).after_state is not None
        after = vertex_correspondence(m)
        lonely = sum(1 for x in m.all_face_ids() if partner_face(m, after, x) is None)
        unp = sum(1 for x in after.values() if x.state is C.UNPAIRED)
        side(f"loop centred ({cx},{cy})",
             f"bridge points mirror-equivariant: {src_pts == mir_pts}; closed_shapes="
             f"{[x.built for x in res.closed_shapes]} commit_ok={ok} | state={symmetry_state(m).value} "
             f"unpaired={unp} faces_w/o_partner={lonely}")


def main() -> None:
    for asset in ASSETS:
        print(f"\n=== {asset} ===")
        part_f(asset)
        part_g(asset)
        part_h(asset)
    print()
    part_i()


if __name__ == "__main__":
    main()
