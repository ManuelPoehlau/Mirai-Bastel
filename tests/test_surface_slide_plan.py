"""Surface Slide, Phase 2 (audit 2026-11-14 §13.2): planning, region capture, symmetry - gate G2.

On the Gollum cage (`scenes/Gollum_Head_01.mirai.json`, declared X symmetry, the neck opening as an open boundary that
crosses the plane) and `examples/meshes/head_basemesh.obj` (closed, X definition derived as Shift+S does), every
written frame of a gesture is checked: mirror pairs bitwise exact, seam coordinate exactly 0, no `AMBIGUOUS`
(also after barrier stops), every driven vertex on the *drawn* triangle of its polygon (<= 1e-12 h),
`tests/mesh_invariants.py`, and the region capture equal to the full capture bit for bit. Plus the refusals.
"""

from __future__ import annotations

import functools
import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401
from tests.mesh_invariants import assert_mesh_invariants
from tests.surface_slide_fixtures import point_triangle_distance

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "examples") not in sys.path:
    sys.path.insert(0, str(_REPO / "examples"))

from viewport.derived import triangulate_mesh_face  # noqa: E402
from viewport.packed_geometry import np  # noqa: E402

from core import Mesh  # noqa: E402
from core.mesh import SymmetryDefinition  # noqa: E402
from core.serialization import scene_from_json  # noqa: E402
from mirai.scene_factory import mesh_from_positions_and_faces  # noqa: E402
from mirai.soft_selection import SoftSettings  # noqa: E402
from mirai.surface_slide import (FLAG_BARRIER, FLAG_CHAIN_END, EdgeChain, SlideReference, SlideSession,  # noqa: E402
                                 SurfaceSlideRefused, plan_surface_slide)
from mirai.symmetry import CorrespondenceState, mirror_position, vertex_correspondence  # noqa: E402
from mirai.symmetry_axis import definition_for_axis  # noqa: E402

GOLLUM = _REPO / "scenes" / "Gollum_Head_01.mirai.json"
HEAD = _REPO / "examples" / "meshes" / "head_basemesh.obj"


@functools.lru_cache(maxsize=None)
def _gollum_text() -> str:
    return GOLLUM.read_text(encoding="utf-8")


def gollum() -> Mesh:
    return scene_from_json(_gollum_text()).mesh


@functools.lru_cache(maxsize=None)
def _head_data():
    from loaders.obj_loader import load_obj
    return load_obj(HEAD)


def head(symmetric: bool = True) -> Mesh:
    data = _head_data()
    mesh = mesh_from_positions_and_faces(data.vertices, data.faces)
    if symmetric:
        mesh.symmetry_definition = definition_for_axis(mesh, "X")
    return mesh


def near(mesh: Mesh, point, *, seam: bool | None = None, boundary: bool = False):
    """The vertex nearest to `point`; `seam` True / False restricts to x == 0 / x != 0, `boundary` to open-boundary
    vertices."""
    cand = mesh.all_vertex_ids()
    if seam is not None:
        cand = [v for v in cand if (mesh.vertex_position(v)[0] == 0.0) == seam]
    if boundary:
        cand = [v for v in cand if any(len(mesh.edge_faces(e)) == 1 for e in mesh.vertex_edges(v))]
    return min(cand, key=lambda v: sum((a - b) ** 2 for a, b in zip(mesh.vertex_position(v), point)))


def soft(radius: float) -> SoftSettings:
    return SoftSettings(enabled=True, world_radius=radius)


def bits(p) -> bytes:
    return np.array(p, dtype=np.float64).tobytes()


# -- the gesture driver: every check of gate G2 on every written frame ------------------------------------------------

def drive(mesh: Mesh, plan, deltas, *, margin=None, hidden=frozenset()):
    """Run `deltas` with a region session and a full session side by side, write the region frames into the mesh in
    one journal change and check every frame; zero drag and the rollback restore the press state exactly. Returns
    `(region session, union of flags, region captures, positions of the last frame before the zero drag)`."""
    before = mesh.export_state()
    drawn = {f: set(triangulate_mesh_face(mesh, f)) for f in mesh.all_face_ids()}
    press = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    seam_vertices = set()
    definition = mesh.symmetry_definition
    pairs_before = {}
    if definition is not None:
        seam_vertices = {v for e in definition.seam_edges for v in mesh.edge_vertices(e)}
        pairs_before = {v: c.partner for v, c in vertex_correspondence(mesh).items()
                        if c.state is CorrespondenceState.PAIRED}
    region = SlideSession(mesh, plan, margin=margin)
    full = SlideSession(mesh, plan, full_capture=True)
    assert full.capture.complete
    h = plan.edge_scale
    flags = 0
    last = {}
    change = mesh.begin_change()
    for delta in deltas:
        a = region.update(delta)
        b = full.update(delta)
        # region capture == full capture, bit for bit
        assert a.positions.keys() == b.positions.keys() == plan.origins.keys()
        assert all(bits(a.positions[v]) == bits(b.positions[v]) for v in a.positions)
        assert np.array_equal(a.flags, b.flags) and a.lagging == b.lagging
        flags |= int(np.bitwise_or.reduce(a.flags))
        last = a.positions
        for v, p in a.positions.items():
            mesh.set_vertex_position(v, p)
        assert_mesh_invariants(mesh, context="surface slide frame")
        # every driven vertex on a drawn triangle of its polygon at the press
        cap, slide = region.capture, region.slide
        tri, bary = slide.anchors()
        assert np.all(bary >= 0.0)
        corners = np.array(cap.vertex_ids, dtype=object)[cap.reference.T[tri]]
        for t, vs, v in zip(tri.tolist(), corners.tolist(), plan.vertex_ids):
            assert tuple(vs) in drawn[cap.triangle_face[t]]
            assert cap.triangle_face[t] not in hidden
        P = np.array([a.positions[v] for v in plan.vertex_ids])
        if plan.seam_vertex_ids:     # pinned to the plane: compare the rest with the anchor
            seam_rows = [i for i, v in enumerate(plan.vertex_ids) if v in plan.seam_vertex_ids]
            P[seam_rows, 0] = 0.0
        A, B, C = (np.array([[press[c[k]] for c in corners.tolist()]]).reshape(-1, 3) for k in range(3))
        assert point_triangle_distance(P, A, B, C).max(initial=0.0) <= 1e-12 * h
        if definition is not None:
            point, normal = definition.plane_point, definition.plane_normal
            for w, d in plan.mirrors.items():     # mirror pairs bitwise exact
                assert bits(mesh.vertex_position(w)) == bits(mirror_position(mesh.vertex_position(d), point, normal))
            for v in seam_vertices:               # seam coordinate exactly 0
                assert mesh.vertex_position(v)[0] == 0.0
            for v in plan.vertex_ids:             # driven vertices stay on the driven half or on the seam
                assert v in seam_vertices or np.sign(mesh.vertex_position(v)[0]) == plan.side
            corr = vertex_correspondence(mesh)    # no AMBIGUOUS, no pair lost
            assert not any(c.state is CorrespondenceState.AMBIGUOUS for c in corr.values())
            assert all(corr[v].state is CorrespondenceState.PAIRED and corr[v].partner == p
                       for v, p in pairs_before.items())
    zero = region.update((0.0, 0.0, 0.0))
    assert all(bits(zero.positions[v]) == bits(plan.origins[v]) for v in plan.origins)
    mesh.rollback_change(change)
    assert mesh.export_state() == before
    return region, flags, region.captures, last


def straight(direction, h, steps: int, step: float = 0.5):
    d = np.asarray(direction, dtype=np.float64)
    return [d * h * step * k for k in range(1, steps + 1)]


# -- gate G2 on the two meshes -----------------------------------------------------------------------------------------

def test_cage_cheek_soft_drag_into_the_seam_stops_short_of_it():
    mesh = gollum()
    seed = near(mesh, (0.12, 0.25, 0.32), seam=False)
    plan = plan_surface_slide(mesh, [seed], influence=soft(0.15))
    assert plan.side == 1 and plan.mirrors and not plan.seam_vertex_ids
    region, flags, captures, _ = drive(mesh, plan, straight((-1.0, 0.2, 0.0), plan.edge_scale, 30))
    assert flags & FLAG_BARRIER                       # vertices reached the seam barrier and backed off


def test_cage_seam_vertex_slides_along_the_seam_with_its_soft_falloff():
    mesh = gollum()
    seed = near(mesh, (0.0, 0.55, 0.3), seam=True)
    plan = plan_surface_slide(mesh, [seed], influence=soft(0.12))
    assert seed in plan.seam_vertex_ids and plan.pivot == seed
    deltas = straight((0.3, 1.0, -0.4), plan.edge_scale, 16) + straight((1.0, -0.5, 0.2), plan.edge_scale, 16)
    region, flags, _, last = drive(mesh, plan, deltas)
    assert region.capture.chains and region.capture.chains[0].on_chain[region.capture.row_of[seed]]


def test_cage_neck_rim_slides_along_the_boundary_and_stops_short_of_the_seam():
    mesh = gollum()
    seed = near(mesh, (0.04, -0.2, -0.11), seam=False, boundary=True)
    plan = plan_surface_slide(mesh, [seed], influence=soft(0.06))
    h = plan.edge_scale
    region, flags, _, last = drive(mesh, plan, straight((-1.0, 0.0, 0.0), h, 24) + straight((1.0, 0.0, 0.3), h, 24))
    assert flags & FLAG_CHAIN_END
    # the rim vertex walked its rim (strictly on the driven side: `drive` checks the sign every frame)
    row = region.capture.row_of[seed]
    assert region.capture.chains[-1].on_chain[row] and row not in region.capture.seam_rows
    assert last[seed] != plan.origins[seed]


def test_cage_seeds_on_both_halves_drive_the_pivots_half_only():
    mesh = gollum()
    a = near(mesh, (0.2, 0.1, 0.3), seam=False)
    b = near(mesh, (-0.15, 0.35, 0.3), seam=False)
    plan = plan_surface_slide(mesh, [a, b], pivot=b, influence=soft(0.08))
    corr = vertex_correspondence(mesh)
    assert plan.side == -1 and b in plan.vertex_ids and a in plan.mirrors
    assert plan.mirrors[a] == corr[a].partner
    assert all(mesh.vertex_position(v)[0] <= 0.0 for v in plan.vertex_ids)   # K-near does not decide (B3)
    drive(mesh, plan, straight((0.6, 0.6, 0.0), plan.edge_scale, 20))


def test_cage_hidden_polygons_are_walls():
    mesh = gollum()
    seed = near(mesh, (0.2, 0.2, 0.3), seam=False)
    p = np.array(mesh.vertex_position(seed))
    hidden = frozenset(f for f in mesh.all_face_ids()
                       if all(0.02 < (np.array(mesh.vertex_position(v)) - p)[1] < 0.12
                              for v in mesh.face_vertices(f))
                       and all(mesh.vertex_position(v)[0] > 0.05 for v in mesh.face_vertices(f)))
    assert hidden
    plan = plan_surface_slide(mesh, [seed], influence=soft(0.05), hidden_faces=hidden)
    _, flags, _, _ = drive(mesh, plan, straight((0.0, 1.0, 0.0), plan.edge_scale, 30), hidden=hidden)
    assert flags & FLAG_BARRIER


def test_head_cheek_and_seam_and_no_symmetry():
    mesh = head()
    cheek = near(mesh, (1.2, 2.5, 1.3), seam=False)
    plan = plan_surface_slide(mesh, [cheek], influence=soft(1.0))
    _, flags, _, _ = drive(mesh, plan, straight((-1.0, 0.3, 0.0), plan.edge_scale, 30))
    assert flags & FLAG_BARRIER
    seam = near(mesh, (0.0, 3.0, 1.6), seam=True)
    plan = plan_surface_slide(mesh, [seam], influence=soft(0.8))
    drive(mesh, plan, straight((0.5, 1.0, 0.0), plan.edge_scale, 20))
    plain = head(symmetric=False)
    v = near(plain, (0.4, 2.5, 1.6))
    plan = plan_surface_slide(plain, [v], influence=soft(0.8))
    assert plan.plane is None and not plan.mirrors
    _, flags, _, last = drive(plain, plan, straight((-1.0, 0.0, 0.0), plan.edge_scale, 20))
    assert last[v][0] < 0.0 and not flags & FLAG_BARRIER     # without symmetry x = 0 is no wall


def test_region_growth_replays_to_the_full_result():
    mesh = gollum()
    seed = near(mesh, (0.25, 0.2, 0.25), seam=False)
    plan = plan_surface_slide(mesh, [seed], influence=soft(0.06))
    deltas = straight((0.2, 1.0, 0.1), plan.edge_scale, 30) + straight((1.0, 0.0, -0.5), plan.edge_scale, 10)
    region, _, captures, _ = drive(mesh, plan, deltas, margin=plan.edge_scale)
    assert captures >= 3                               # grown at least twice, each time replayed
    assert len(region.capture.face_ids) < len(SlideSession(mesh, plan, full_capture=True).capture.face_ids)


def test_capture_is_the_drawn_half_with_its_walls():
    mesh = gollum()
    seed = near(mesh, (0.0, 0.3, 0.38), seam=True)
    plan = plan_surface_slide(mesh, [seed], influence=soft(0.1))
    cap = SlideSession(mesh, plan).capture
    ref = cap.reference
    assert cap.reference.V.flags.writeable is False
    assert list(cap.vertex_ids) == sorted(cap.vertex_ids) and list(cap.face_ids) == sorted(cap.face_ids)
    assert all(all(mesh.vertex_position(v)[0] >= 0.0 for v in mesh.face_vertices(f)) for f in cap.face_ids)
    # every declared seam edge in the capture is a barrier and a chain edge; the seam normals lie in the plane
    seam_chain = cap.chains[0]
    assert seam_chain.n_edges > 0 and np.all(ref.VN[list(cap.seam_rows), 0] == 0.0)
    assert not cap.complete and np.any(ref.nbr == -3)
    full = SlideSession(mesh, plan, full_capture=True).capture
    assert full.complete and len(full.face_ids) == sum(
        1 for f in mesh.all_face_ids() if all(mesh.vertex_position(v)[0] >= 0.0 for v in mesh.face_vertices(f)))


def test_mask_and_weights():
    mesh = gollum()
    seed = near(mesh, (0.2, 0.2, 0.3), seam=False)
    free = plan_surface_slide(mesh, [seed], influence=soft(0.1))
    other = next(v for v in free.vertex_ids if v != seed)
    partner = vertex_correspondence(mesh)[other].partner
    mask = {other: 1.0, partner: 1.0}
    half = next(v for v in free.vertex_ids if v not in (seed, other))
    mask.update({half: 0.5, vertex_correspondence(mesh)[half].partner: 0.5})
    plan = plan_surface_slide(mesh, [seed], influence=soft(0.1), mask=mask)
    w = dict(zip(plan.vertex_ids, plan.weights))
    assert other not in w and partner not in plan.mirrors
    assert w[half] == dict(zip(free.vertex_ids, free.weights))[half] * 0.5
    assert w[seed] == 1.0


# -- refusals ----------------------------------------------------------------------------------------------------------

def test_refusals():
    mesh = gollum()
    seed = near(mesh, (0.2, 0.2, 0.3), seam=False)
    with pytest.raises(SurfaceSlideRefused, match="select or hover"):
        plan_surface_slide(mesh, [])
    with pytest.raises(SurfaceSlideRefused, match="masked"):
        plan_surface_slide(mesh, [seed], mask={seed: 1.0})
    with pytest.raises(ValueError):
        plan_surface_slide(mesh, [seed], pivot=near(mesh, (-0.2, 0.2, 0.3)))
    # a vertex the falloff reaches has lost its partner
    lonely = next(v for v in plan_surface_slide(mesh, [seed], influence=soft(0.1)).vertex_ids if v != seed)
    x, y, z = mesh.vertex_position(lonely)
    mesh.set_vertex_position(lonely, (x, y + 1e-4, z))
    with pytest.raises(SurfaceSlideRefused, match="no mirror partner"):
        plan_surface_slide(mesh, [seed], influence=soft(0.1))
    with pytest.raises(SurfaceSlideRefused, match="Spiegelpartner|mirror partner"):
        plan_surface_slide(mesh, [lonely])
    # a plane that is not an exact axis plane
    mesh = gollum()
    d = mesh.symmetry_definition
    mesh.symmetry_definition = SymmetryDefinition((0.1, 0.0, 0.0), d.plane_normal, d.seam_edges)
    with pytest.raises(SurfaceSlideRefused, match="exact axis plane"):
        plan_surface_slide(mesh, [seed])
    # a seam vertex whose polygons are all hidden cannot move
    mesh = gollum()
    s = near(mesh, (0.0, 0.55, 0.3), seam=True)
    hidden = {f for e in mesh.vertex_edges(s) for f in mesh.edge_faces(e)}
    with pytest.raises(SurfaceSlideRefused, match="cannot slide"):
        plan_surface_slide(mesh, [s], hidden_faces=hidden)


def test_refuses_straddling_polygons_and_bowties():
    # a strip of quads across x = 0 without a vertex on the plane: the middle quad straddles it
    xs = (-1.5, -0.5, 0.5, 1.5)
    V = [(x, y, 0.0) for y in (0.0, 1.0) for x in xs]
    F = [(i, i + 1, i + 5, i + 4) for i in range(3)]
    mesh = mesh_from_positions_and_faces(V, F)
    mesh.symmetry_definition = SymmetryDefinition((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), frozenset())
    ids = mesh.all_vertex_ids()
    with pytest.raises(SurfaceSlideRefused, match="crosses the mirror plane"):
        plan_surface_slide(mesh, [ids[2]])
    plan_surface_slide(mesh, [ids[3]])           # the outer vertex touches no straddling polygon
    # two triangles sharing only a corner
    V = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)]
    mesh = mesh_from_positions_and_faces(V, [(0, 1, 2), (0, 3, 4)])
    with pytest.raises(SurfaceSlideRefused, match="bowtie"):
        plan_surface_slide(mesh, [mesh.all_vertex_ids()[0]])


# -- EdgeChain.stop_short (E3 for open-boundary rows) -------------------------------------------------------------------

def test_edge_chain_stops_short_of_listed_vertices():
    V = np.array([(float(i), 0.0, 0.0) for i in range(4)] + [(float(i), 1.0, 0.0) for i in range(4)])
    T = np.array([(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6)])
    ref = SlideReference(V, T)
    edges = [(0, 1), (1, 2), (2, 3)]
    plain = EdgeChain(ref, edges)
    short = EdgeChain(ref, edges, stop_short=[3])
    _, _, travelled, flags = plain.walk(1, 2, 5.0)
    assert travelled == 2.0 and flags == FLAG_CHAIN_END
    # at most 98 % of the own path to the stop vertex: rows from 1 and from 0 stop at different points, in order
    tri, bary, travelled, flags = short.walk(1, 2, 5.0)
    assert travelled == pytest.approx(1.96) and flags == FLAG_CHAIN_END
    x1 = ref.point(np.array([tri]), bary[None])[0][0]
    tri, bary, travelled, flags = short.walk(0, 1, 5.0)
    x0 = ref.point(np.array([tri]), bary[None])[0][0]
    assert x1 == pytest.approx(2.96) and x0 == pytest.approx(2.94) and x0 < x1 < 3.0
    _, _, travelled, flags = short.walk(1, 2, 1.5)
    assert travelled == 1.5 and flags == 0
    _, _, travelled, flags = short.walk(2, 1, 5.0)       # away from the stop vertex: the plain chain end
    assert travelled == 2.0 and flags == FLAG_CHAIN_END
    assert short.ends() == [0, 3]
