"""Gate G1 of the Production Readiness Audit (2026-11-14, §9 / §13): the Production core `src/mirai/surface_slide/`
against this prototype, on the report's 76 scenarios. Like the Knife oracle, the frozen prototype is the reference
implementation; the Production modules are what is checked.

- With the prototype's tree transport injected, the port reproduces `GeodesicPursuit("transport")` frame by frame
  (positions within 1e-12 h; measured: bit for bit), with the same anchors and the same lagging rows.
- With its own direct transport (audit §3.2) the port keeps every claim of the report (0 region jumps, step ratio
  <= 2, exact closure, on the surface to 1e-12 h, no STUCK / MAXITER) and is no worse than the audit's table:
  edge distortion within 4 points of the tree in every soft scenario, rigid patches as measured there, smaller
  direction jumps between neighbours.
- The chain walker reproduces the seam walker on the Gollum cage.

Scenarios whose prototype setup has no transport (independent probe vertices; the report ran them with the per-vertex
`project` direction, which Production does not have, E9) get the prototype's tree transport from their first vertex.

Run: `python -m pytest experiments/surface_slide/tests/test_production_oracle.py -q` (about 20 s).
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

from surface_slide import algorithms as A
from surface_slide import harness as H
from surface_slide import mirai_io  # noqa: F401  (puts src/ on the path)
from surface_slide import scenarios as S
from surface_slide.fields import EdgeGraph, soft_weights, transport_frames
from surface_slide.seam import SeamCurve

from mirai.surface_slide import (FLAG_CHAIN_END, FLAG_MAXITER, FLAG_STUCK, WALL_FLAGS, EdgeChain,
                                 SlideReference, SurfaceSlide, direct_frames, frame_jumps)

_REFS: dict[int, SlideReference] = {}


def production_reference(ref) -> SlideReference:
    """The prototype's triangles as a Production reference (the same `h`, so the tolerances are the same)."""
    out = _REFS.get(id(ref))
    if out is None:
        out = _REFS[id(ref)] = SlideReference(ref.V, ref.T, edge_scale=ref.mean_edge)
    return out


class Production(A.Candidate):
    """`mirai.surface_slide.SurfaceSlide` behind the prototype's candidate interface, so the harness measures it."""

    def __init__(self, frames: str) -> None:
        super().__init__()
        self.frames = frames
        self.name = f"production[{frames}]"

    def _begin(self) -> None:
        s = self.setup
        assert np.all(s.verts >= 0) and s.nbr is None
        frames = s.transport if self.frames == "tree" else None
        self.slide = SurfaceSlide(production_reference(s.ref), s.verts, s.weights, s.pivot, frames=frames)
        self.flags = []

    def update(self, delta) -> A.SlideResult:
        frame = self.slide.update(delta)
        tri, bary = self.slide.anchors()
        self.flags.append(frame.flags)
        assert not frame.positions.flags.writeable
        return A.SlideResult(np.array(frame.positions), tri, bary, (frame.flags & 0xFF).astype(np.uint8))


def with_transport(scn):
    if scn.setup.transport is not None:
        return scn
    s = scn.setup
    R = transport_frames(s.ref, S.graph_of(s.ref), int(s.verts[s.pivot]), s.verts)
    out = copy.copy(scn)
    out.setup = A.SlideSetup(s.ref, s.tri0, s.bary0, s.p0, s.n0, s.weights, s.verts, s.pivot, R, s.nbr)
    return out


SCENARIOS = {scn.name: scn for scn in S.all_scenarios()}


def test_the_76_scenarios_are_all_here():
    assert len(SCENARIOS) == 76


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_port_matches_the_prototype_frame_by_frame(name):
    scn = with_transport(SCENARIOS[name])
    h = scn.ref.mean_edge
    proto = A.GeodesicPursuit("transport")
    port = Production("tree")
    want = H.run(scn, proto)
    got = H.run(scn, port)
    assert np.abs(got.pos - want.pos).max() <= 1e-12 * h
    assert np.array_equal(got.tri, want.tri)
    # the same lagging rows at the end, the same boundary stops (the prototype has one wall flag)
    assert np.array_equal(port.slide.lagging_mask, proto.lagging)
    assert np.array_equal((got.flags & WALL_FLAGS) > 0, (want.flags & 1) > 0)
    # zero drag after the run: the start, bit for bit
    assert np.array_equal(port.slide.update(np.zeros(3)).positions, scn.setup.p0)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_direct_transport_keeps_the_report_claims(name):
    scn = with_transport(SCENARIOS[name])
    port = Production("direct")
    r = H.run(scn, port)
    m = r.metrics
    assert m["continuity"]["region_jumps"] == 0
    assert m["continuity"]["max_step_ratio"] <= 2.0 + 1e-6
    assert m["dev_tracked_max_over_frames"] <= 1e-12 * scn.ref.mean_edge
    if "wrong_region_any_frame" in m:
        assert m["wrong_region_any_frame"] == 0
    if "closure" in m:
        assert m["closure"]["max"] == 0.0
    for f in port.flags:
        assert not np.any(f & (FLAG_STUCK | FLAG_MAXITER))
    zero = scn.setup.weights == 0.0
    assert np.array_equal(r.pos[:, zero], np.broadcast_to(scn.setup.p0[zero], r.pos[:, zero].shape))


SOFT = [n for n, s in SCENARIOS.items() if s.setup.transport is not None and "loop" not in n]


@pytest.mark.parametrize("name", SOFT)
def test_direct_transport_distorts_no_more_than_the_tree(name):
    """Audit §3.2: soft scenarios within 4 points of the tree (mean relative edge change of the moved edges)."""
    scn = SCENARIOS[name]
    tree = H.run(scn, A.GeodesicPursuit("transport")).metrics["edges"]["mean_abs_rel"]
    direct = H.run(scn, Production("direct")).metrics["edges"]["mean_abs_rel"]
    assert direct <= tree + 0.04


#: Audit §3.2, "direct" column, rigid patches (mean / max relative edge change, + 0.1 point rounding margin)
RIGID_TABLE = {
    "B5_cylinder_rigid_circ": (0.001, 0.001),
    "A5_sphere_rigid_face_3edges": (0.020, 0.081),
    "A5_sphere_rigid_face_8edges": (0.127, 0.418),
    "D_cage_cheek_rigid": (0.080, 0.196),
    "D_cage_forehead_rigid": (0.030, 0.079),
    "D_cage_brow_rigid": (0.138, 0.628),
}


@pytest.mark.parametrize("name", sorted(RIGID_TABLE))
def test_direct_transport_rigid_patches_match_the_audit_table(name):
    edges = H.run(SCENARIOS[name], Production("direct")).metrics["edges_rigid"]
    mean, worst = RIGID_TABLE[name]
    assert edges["mean_abs_rel"] <= mean + 0.001
    assert edges["max_abs_rel"] <= worst + 0.001


def test_direct_transport_jumps_less_than_the_tree_on_the_cage():
    """Audit §3.2 table (radius 0.15, polygon edges): nose tip / lid / lip 68 / 73 / 40 degrees with the tree,
    28 / 49 / 39 direct."""
    _, cage = S.gollum_cage_ref()
    ref = production_reference(cage)
    graph = EdgeGraph(cage.nv, cage.edges, cage.V)
    near_plane = np.flatnonzero(np.abs(cage.V[:, 0]) < 0.03)
    seeds = {"nose_tip": int(near_plane[np.argmax(cage.V[near_plane, 2])])}
    seeds.update({f: S.front_vertex(cage, *S.CAGE_FEATURES[f]) for f in ("brow", "nose_side", "eye_rim_low",
                                                                        "upper_lip")})
    limits = {"nose_tip": 28.0, "eye_rim_low": 49.5, "upper_lip": 39.0}
    for name, v in seeds.items():
        verts, _ = soft_weights(graph, [v], 0.15)
        tree = frame_jumps(ref, v, verts, transport_frames(cage, graph, v, verts), cage.edges).max()
        direct = frame_jumps(ref, v, verts, direct_frames(ref, v, verts), cage.edges).max()
        assert direct <= tree + 0.5, name
        if name in limits:
            assert direct <= limits[name], name


def test_edge_chain_reproduces_the_seam_walker_on_the_cage():
    mesh, cage = S.gollum_cage_ref()
    ref = production_reference(cage)
    proto = SeamCurve(cage, mesh.seam_edges)
    chain = EdgeChain(ref, mesh.seam_edges)
    tangents = [np.array(t) for t in ((0.02, 0.06, -0.03), (0.0, -0.2, 0.05), (0.0, 0.01, 0.3), (0.0, 0.5, 0.0))]
    ended = 0
    for v in mesh.seam_vertices.tolist():
        for t in tangents:
            _, _, want, stopped = proto.slide(v, t)
            arm, length = chain.arm(v, t)
            tri, bary, _, flags = chain.walk(v, arm, length)
            got = ref.point(np.array([tri]), bary[None])[0]
            assert np.abs(got - want).max() <= 1e-15
            assert got[0] == 0.0
            assert bool(flags & FLAG_CHAIN_END) == stopped
            ended += stopped
    assert ended > 0


def test_seam_rows_stay_on_the_plane_in_a_slide():
    """Seam rows in a `SurfaceSlide` with the seam as a chain and a barrier: on the plane exactly, and the driven
    rows of the +x half never reach it (back-off)."""
    mesh, cage = S.gollum_cage_ref()
    ref = SlideReference(cage.V, cage.T, barrier_edges=mesh.seam_edges, edge_scale=cage.mean_edge)
    graph = EdgeGraph(cage.nv, cage.edges, cage.V)
    near_plane = mesh.seam_vertices
    seed = int(near_plane[np.argmax(cage.V[near_plane, 2])])               # the nose tip, on the seam
    verts, w = soft_weights(graph, [seed], 0.12)
    keep = cage.V[verts, 0] >= 0.0                                          # the driven half plus the seam
    verts, w = verts[keep], w[keep]
    pivot = int(np.flatnonzero(verts == seed)[0])
    slide = SurfaceSlide(ref, verts, w, pivot, chains=[EdgeChain(ref, mesh.seam_edges)])
    on_seam = np.isin(verts, mesh.seam_vertices)
    for delta in S.line_path((-0.12, -0.05, 0.02), 24):
        frame = slide.update(delta)
        assert np.all(frame.positions[on_seam, 0] == 0.0)
        assert np.all(frame.positions[~on_seam, 0] > 0.0)
        assert not np.any(frame.flags & (FLAG_STUCK | FLAG_MAXITER))
