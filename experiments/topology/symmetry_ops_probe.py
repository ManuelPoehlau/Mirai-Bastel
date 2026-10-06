"""Read-only probe: what do the existing Production topology operations do to the
Symmetry state, and what would a coordinating Symmetry layer have to supply?

Discovery instrument for `docs/research/symmetry/SYMMETRY_PRODUCTION_OPERATIONS_DISCOVERY.md`.
Nothing here is a tool, a capability or a proposal for `src/`: every helper below
(`partner_edge`, `partner_face`, `mirror_path`, ...) is a local stand-in written to ask
"is the information derivable at all?". Runs on in-memory meshes loaded from the example
assets; no file is written, no repo state is touched.

Run from the repo root:  python experiments/topology/symmetry_ops_probe.py
(Part E imports `playground.topology_tools.extrude` — Extrude exists only in the Playground.)
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for p in (REPO / "experiments", REPO / "examples", REPO, REPO / "src"):  # src/ first on sys.path
    sys.path.insert(0, str(p))

from core import SelectionMode  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402
from mirai.symmetry import CorrespondenceState as C  # noqa: E402
from mirai.symmetry import symmetry_state, vertex_correspondence  # noqa: E402
from mirai.topology.connect_per_face import connect_selected_edges_per_face  # noqa: E402
from mirai.topology.connect_vertices_per_face import connect_vertices_per_face  # noqa: E402
from mirai.topology.delete_dissolve import RemovalRefused, remove_selected  # noqa: E402
from mirai.topology.knife_resolve import check_commit, resolve_cross_face  # noqa: E402
from mirai.topology.split import split_selected_edge  # noqa: E402
from symmetry_lab.lab_symmetry import definition_for_axis  # noqa: E402
from symmetry_lab.lab_topology import topological_pairing  # noqa: E402

ASSETS = ("subd_cube", "head_basemesh")


# -- helpers ---------------------------------------------------------------------------


def load(asset: str):
    scene = build_core_scene_from_obj(asset_path(asset))
    mesh = scene.mesh
    mesh.symmetry_definition = definition_for_axis(mesh, "X")  # Lab E1/E3: plane x=0, derived seam
    return scene


def summary(mesh) -> str:
    corr = vertex_correspondence(mesh)
    counts = dict(collections.Counter(c.state.value for c in corr.values()))
    seam = mesh.symmetry_definition.seam_edges
    live = sum(1 for e in seam if mesh.is_valid_edge(e))
    # `symmetry_state` is vertex/position-only; the Lab's topological pairing is the independent
    # edge/face-aware check (pairs found / vertex conflicts / face-pair conflicts).
    tp = topological_pairing(mesh)
    # Third check, face-level: faces whose vertex-image is not a face of the mesh (neither of the
    # two checks above notices a one-sided Delete: the vertices stay paired, the pairing walk just ends).
    lonely = sum(1 for f in mesh.all_face_ids() if partner_face(mesh, corr, f) is None)
    return (f"{symmetry_state(mesh).value:9s} verts={counts} "
            f"seam_edges live/declared={live}/{len(seam)} faces={len(mesh.all_face_ids())} "
            f"topo={len(tp.partners)}/{len(tp.conflicts)}/{tp.face_pair_conflicts} faces_w/o_partner={lonely}")


def partner_vertex(corr, v):
    c = corr[v]
    return v if c.state is C.SEAM else c.partner if c.state is C.PAIRED else None


def partner_edge(mesh, corr, e):
    """Edge between the partners of its endpoints (the old Lab Knife's rule)."""
    a, b = mesh.edge_vertices(e)
    pa, pb = partner_vertex(corr, a), partner_vertex(corr, b)
    if pa is None or pb is None:
        return None
    return next((x for x in mesh.vertex_edges(pa) if pb in mesh.edge_vertices(x)), None)


def partner_face(mesh, corr, f):
    """Face whose vertex set is the image of f's vertex set."""
    image = {partner_vertex(corr, v) for v in mesh.face_vertices(f)}
    if None in image:
        return None
    hits = [g for g in mesh.all_face_ids() if set(mesh.face_vertices(g)) == image]
    return hits[0] if len(hits) == 1 else None


def plus_x_face(mesh, touching_seam: bool):
    def xs(f):
        return [mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)]
    if touching_seam:
        return next(f for f in mesh.all_face_ids() if min(xs(f)) == 0 and max(xs(f)) > 0)
    return next(f for f in mesh.all_face_ids() if min(xs(f)) > 0)


def side(label: str, line: str) -> None:
    print(f"  {label:34s} {line}")


# -- A: classification ----------------------------------------------------------------


def part_a(asset: str) -> None:
    s = load(asset); m = s.mesh; corr = vertex_correspondence(m)
    faces = collections.Counter()
    for f in m.all_face_ids():
        xs = [m.vertex_position(v)[0] for v in m.face_vertices(f)]
        faces["+X interior" if min(xs) > 0 else "-X interior" if max(xs) < 0
              else "+X touching seam" if min(xs) == 0 and max(xs) > 0
              else "-X touching seam" if max(xs) == 0 and min(xs) < 0 else "spans/on plane"] += 1
    seam = m.symmetry_definition.seam_edges
    no_partner = sum(1 for e in m.all_edge_ids() if e not in seam and partner_edge(m, corr, e) is None)
    print("A. baseline / partner derivability")
    side("baseline", summary(m))
    side("faces by side", str(dict(faces)))
    side("non-seam edges without vertex-image partner", f"{no_partner}/{len(m.all_edge_ids()) - len(seam)}")


# -- B: one-sided vs. expanded selection through the existing ops ----------------------


def part_b(asset: str) -> None:
    print("B. existing ops, one-sided vs. selection ∪ partners (one call, no op change)")
    s = load(asset); m = s.mesh; corr = vertex_correspondence(m)
    f = plus_x_face(m, touching_seam=False)
    e = m.face_edges(f)[0]
    seam0 = sorted(m.symmetry_definition.seam_edges)[0]
    pair = {m.face_edges(f)[0], m.face_edges(f)[2]}
    vs = m.face_vertices(f); diag = {vs[0], vs[2]}

    def fresh():
        s2 = load(asset); return s2, s2.mesh, vertex_correspondence(s2.mesh)

    s2, m2, c2 = fresh(); split_selected_edge(s2, e); side("split, one-sided", summary(m2))
    s2, m2, c2 = fresh(); pe = partner_edge(m2, c2, e)  # resolved before the first split kills the ids
    split_selected_edge(s2, e); split_selected_edge(s2, pe)
    side("split + partner split t=.5", summary(m2) + f" history={len(s2.history)}")
    s2, m2, c2 = fresh(); pe = partner_edge(m2, c2, e)
    split_selected_edge(s2, e, 0.37); split_selected_edge(s2, pe, 0.37)
    side("split + partner split t=.37 (raw t)", summary(m2))
    s2, m2, c2 = fresh(); split_selected_edge(s2, seam0); side("split a SEAM edge", summary(m2))

    s2, m2, c2 = fresh(); connect_selected_edges_per_face(s2, set(pair)); side("edge connect, one-sided", summary(m2))
    s2, m2, c2 = fresh()
    connect_selected_edges_per_face(s2, pair | {partner_edge(m2, c2, x) for x in pair})
    side("edge connect, expanded", summary(m2) + f" history={len(s2.history)}")
    s2, m2, c2 = fresh(); connect_vertices_per_face(s2, set(diag)); side("vertex connect, one-sided", summary(m2))
    s2, m2, c2 = fresh()
    connect_vertices_per_face(s2, diag | {partner_vertex(c2, v) for v in diag})
    side("vertex connect, expanded", summary(m2))

    def rm(mode, ids, dissolve, label, expand_with=None):
        s2, m2, c2 = fresh()
        ids = set(ids)
        if expand_with is not None:
            ids |= {expand_with(m2, c2, x) for x in ids}
        try:
            remove_selected(s2, mode, ids, dissolve=dissolve, cleanup=True)
            side(label, summary(m2))
        except RemovalRefused as exc:
            side(label, f"refused: {exc}")

    rm(SelectionMode.FACE, {f}, False, "delete face, one-sided")
    rm(SelectionMode.FACE, {f}, False, "delete face, expanded", partner_face)
    g = plus_x_face(m, touching_seam=True)
    rm(SelectionMode.FACE, {g}, False, "delete seam-touching face, 1-sided")
    rm(SelectionMode.FACE, {g}, False, "delete seam-touching face, expanded", partner_face)
    rm(SelectionMode.EDGE, {e}, True, "dissolve edge, one-sided")
    rm(SelectionMode.EDGE, {e}, True, "dissolve edge, expanded", partner_edge)
    rm(SelectionMode.EDGE, {seam0}, True, "dissolve SEAM edge")
    seam_v = next(v for v, c in corr.items() if c.state is C.SEAM)
    rm(SelectionMode.VERTEX, {seam_v}, True, "dissolve SEAM vertex")
    rm(SelectionMode.VERTEX, {seam_v}, False, "delete SEAM vertex")


# -- C: Knife — mirror the virtual path before resolution -----------------------------


def mirror_path(mesh, corr, path, pid_offset=1000):
    out = []
    for p in path:
        q = dict(p); q["pid"] = p["pid"] + pid_offset
        if p["kind"] == "edge":
            a, b = mesh.edge_vertices(p["edge_id"])
            pe = partner_edge(mesh, corr, p["edge_id"])
            same = mesh.edge_vertices(pe) == (partner_vertex(corr, a), partner_vertex(corr, b))
            q["edge_id"], q["t"] = pe, (p["t"] if same else 1.0 - p["t"])
        elif p["kind"] == "vertex":
            q["vertex_id"] = partner_vertex(corr, p["vertex_id"])
        out.append(q)
    return out


def part_c(asset: str) -> None:
    print("C. Knife path mirrored before resolution (one resolve call; mirrored chain after a pen lift)")
    for t0, t1, mirrored in ((0.5, 0.5, False), (0.5, 0.5, True), (0.3, 0.6, True)):
        s = load(asset); m = s.mesh; corr = vertex_correspondence(m)
        fe = m.face_edges(plus_x_face(m, touching_seam=False))
        path = [{"pid": 0, "kind": "edge", "edge_id": fe[0], "t": t0},
                {"pid": 1, "kind": "edge", "edge_id": fe[2], "t": t1}]
        full = path + ([{"kind": "break", "reason": "lift"}] + mirror_path(m, corr, path) if mirrored else [])
        before = m.export_state()
        res = resolve_cross_face(m, full, before)
        ok = check_commit(m, before).after_state is not None
        pr = topological_pairing(m)
        side(f"t=({t0},{t1}) mirrored={mirrored}",
             f"applied={res.applied}/{res.runs} commit_ok={ok} | {summary(m)} | "
             f"topo pairs={len(pr.partners)} conflicts={len(pr.conflicts)}/{pr.face_pair_conflicts}")


# -- D: can the generic transaction wrapper host an op that pushes its own history? ---------


def part_d() -> None:
    from mirai.application import Application

    print("D. Application.apply_mesh_change wrapping split_selected_edge (which pushes its own command)")
    app = Application(); app.init_scene("cube")
    edge = app.scene.mesh.all_edge_ids()[0]

    def mutate():
        split_selected_edge(app.scene, edge)
        return None

    app.apply_mesh_change("probe", mutate)
    side("history entries after one wrapped call", str(len(app.history)))


# -- E: Extrude (Playground only) — selection expanded with the partner faces ----------


class _Cam:
    def __init__(self, delta):
        self.delta = delta

    def screen_delta_to_world(self, anchor, dx, dy, w, h):
        return self.delta


def part_e(asset: str) -> None:
    print("E. Playground ExtrudeTool, begin + one update + commit (stub camera delta (0.05,0,0.1))")
    from playground.topology_tools.extrude import ExtrudeTool

    for touching in (False, True):
        for expand in (False, True):
            s = load(asset); m = s.mesh; corr = vertex_correspondence(m)
            f = plus_x_face(m, touching)
            faces = {f} | ({partner_face(m, corr, f)} if expand else set())
            tool = ExtrudeTool(s, _Cam((0.05, 0.0, 0.1))); tool.activate(); tool.begin(face_ids=faces)
            after_begin = symmetry_state(m).value
            normal = tuple(round(x, 3) for x in tool._normal)
            tool.update(dx=1.0, dy=0.0, width=100, height=100)
            tool.commit(); tool.deactivate()
            side(f"touching_seam={touching!s:5s} expand={expand!s:5s}",
                 f"state after begin={after_begin}; ref-normal={normal}; after update: {summary(m)}; history={len(s.history)}")


def main() -> None:
    part_d()
    for asset in ASSETS:
        print(f"\n=== {asset} (plane x=0, seam derived by Lab E3) ===")
        part_a(asset)
        part_b(asset)
        part_c(asset)
        part_e(asset)


if __name__ == "__main__":
    main()
