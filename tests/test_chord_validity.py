"""F2 (AD-017 addendum 2026-09-30): the shared face choice for chords is geometry-aware.

Headless. `connect_in_shared_face` (Knife, Vertex Connect) and Edge Connect only create a
chord in a face in which it lies entirely: R3 (chord along the boundary: zero-area child, an
edge in four faces) and R5 (chord leaves a concave face) are refused through all three modes,
the mesh stays unchanged. Valid chords are not affected: the property test below replays the
*old* selection rule on grid, cube and head and demands identical results wherever the old
result was valid.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh, Scene
from mirai.scene_factory import build_core_scene_from_obj, create_cube
from mirai.topology.chord_validity import (
    chord_faces,
    chord_valid_in_face,
    chord_valid_in_polygon,
    chord_valid_to_edge_point,
)
from mirai.topology.connect_per_face import TopologyToolError, connect_selected_edges_per_face
from mirai.topology.connect_vertices_per_face import connect_vertices_per_face
from mirai.topology.knife import KnifeTool
from mirai.topology.topology_points import connect_in_shared_face
from tests.mesh_invariants import assert_mesh_invariants

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
HEAD_ASSET = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))  # the shared OBJ loader (see test_application_obj_scene)


# -- fixtures ------------------------------------------------------------------------------


def build_grid(n: int = 4) -> Mesh:
    """n x n unit quads in z = 0."""
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


def build_l_face() -> Mesh:
    """One concave L-shaped hexagon; the corner (2, 2) is missing."""
    mesh = Mesh()
    vs = [mesh.add_vertex(p) for p in ((0, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0))]
    mesh.add_face(vs)
    return mesh


def vid(mesh, x, y, z=0.0):
    return next(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v) == (x, y, z))


def edge_between(mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def split_between(mesh, p, q, t=0.5):
    """Split the edge between the vertices at p and q; returns the new vertex."""
    return mesh.split_edge(edge_between(mesh, vid(mesh, *p), vid(mesh, *q)), t)[0]


def grid_with_straight_vertices() -> Mesh:
    """R3 setup (the promotion discovery's HD2): two split edges leave a straight-angle
    vertex at (1.5, 1) on the bottom of the quad above and the top of the quad below it."""
    mesh = build_grid()
    split_between(mesh, (1, 1, 0), (2, 1, 0))
    split_between(mesh, (1, 2, 0), (2, 2, 0))
    return mesh


def grid_with_concave_face() -> Mesh:
    """R5 setup (L1): a bent cut (0.5, 0) -> (0.5, 0.5) -> (0, 0.5) in the corner quad leaves a
    concave hexagon next to the cut-off corner."""
    mesh = build_grid()
    m1 = split_between(mesh, (0, 0, 0), (1, 0, 0))
    m2 = split_between(mesh, (0, 0, 0), (0, 1, 0))
    corner = vid(mesh, 0.0, 0.0)
    quad = next(f for f in mesh.all_face_ids() if {corner, m1, m2} <= set(mesh.face_vertices(f)))
    mesh.remove_face(quad)
    c = mesh.add_vertex((0.5, 0.5, 0.0))
    mesh.add_face([corner, m1, c, m2])
    mesh.add_face([m1, vid(mesh, 1.0, 0.0), vid(mesh, 1.0, 1.0), vid(mesh, 0.0, 1.0), m2, c])
    assert_mesh_invariants(mesh, context="concave setup")
    return mesh


def head_mesh() -> Mesh:
    return build_core_scene_from_obj(HEAD_ASSET).mesh


def content(mesh) -> dict:
    """Mesh state without the id allocator counters (they only ever move forward, AD-001)."""
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}


def scene_of(mesh) -> Scene:
    scene = Scene()
    scene.mesh = mesh
    return scene


def new_knife(mesh):
    scene = scene_of(mesh)
    knife = KnifeTool()
    knife.activate()
    knife.begin(mesh=mesh, scene=scene, selection=scene.selection)
    return knife


def assert_no_degenerate_face(mesh):
    for fid in mesh.all_face_ids():
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
        assert _area3(pts) > 1e-9, f"zero-area face {fid!r}"


def _newell(pts):
    nx = ny = nz = 0.0
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    return nx, ny, nz


def _area3(pts) -> float:
    return 0.5 * math.sqrt(sum(c * c for c in _newell(pts)))


# -- predicate -----------------------------------------------------------------------------


def test_predicate_square_diagonals_valid_adjacent_and_identical_not():
    sq = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    assert chord_valid_in_polygon(sq, 0, 2) and chord_valid_in_polygon(sq, 3, 1)
    assert not chord_valid_in_polygon(sq, 0, 1) and not chord_valid_in_polygon(sq, 3, 0)
    assert not chord_valid_in_polygon(sq, 2, 2)


def test_predicate_is_orientation_and_plane_independent():
    sq = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    assert chord_valid_in_polygon(sq[::-1], 0, 2)
    tilted = [(x, y * 0.6, y * 0.8) for x, y, _ in sq]  # same square in a tilted plane
    assert chord_valid_in_polygon(tilted, 0, 2)
    assert chord_valid_in_polygon([(z, x, y) for x, y, z in sq], 1, 3)


def test_predicate_concave_dart_only_the_inner_diagonal_is_valid():
    dart = [(0, 0, 0), (2, 1, 0), (0, 2, 0), (1, 1, 0)]  # reflex corner at index 3
    assert chord_valid_in_polygon(dart, 1, 3)
    assert not chord_valid_in_polygon(dart, 0, 2)  # leaves the dart


def test_predicate_straight_vertex_on_the_chord_refused():
    quad = [(0, 0, 0), (0.5, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]  # straight vertex at index 1
    assert not chord_valid_in_polygon(quad, 0, 2)  # along the bottom: zero-area child
    assert chord_valid_in_polygon(quad, 1, 3)  # an ordinary chord from the straight vertex


def test_predicate_concave_l_face():
    l_face = [(0, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0)]
    assert chord_valid_in_polygon(l_face, 0, 3)  # (0,0) -> reflex corner (1,1): inside
    assert chord_valid_in_polygon(l_face, 0, 2)  # (0,0) -> (2,1): inside
    assert not chord_valid_in_polygon(l_face, 2, 4)  # (2,1) -> (1,2): over the missing corner
    assert not chord_valid_in_polygon(l_face, 1, 5)  # (2,0) -> (0,2): passes exactly through (1,1)


def test_predicate_chord_crossing_the_boundary_refused():
    # A "U": the chord between the two arm tips crosses the gap between the arms
    u = [(0, 0, 0), (3, 0, 0), (3, 2, 0), (2, 2, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0)]
    assert not chord_valid_in_polygon(u, 3, 6)  # (2,2) -> (1,2): over the gap
    assert not chord_valid_in_polygon(u, 2, 7)  # (3,2) -> (0,2): across the gap


def test_predicate_face_without_area_has_no_valid_chord():
    flat = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)]
    assert not chord_valid_in_polygon(flat, 0, 2)


# -- R3: chord along the boundary ----------------------------------------------------------


def test_r3_knife_vertex_chord_along_the_boundary_refused():
    mesh = grid_with_straight_vertices()
    before = content(mesh)
    knife = new_knife(mesh)
    assert knife.click({"kind": "vertex", "vertex_id": vid(mesh, 1.0, 1.0)})
    target = {"kind": "vertex", "vertex_id": vid(mesh, 2.0, 1.0)}
    assert knife.accepts(target) is False
    assert knife.click(target) is False
    assert content(mesh) == before and knife.path_edges == []
    assert_mesh_invariants(mesh, context="R3 knife vertex")


def test_r3_knife_edge_chord_along_the_boundary_refused():
    """The discovery's HD2: vertex (1,1) -> edge point (1.75, 1) on the straight line (1,1)-(2,1)."""
    mesh = grid_with_straight_vertices()
    before = content(mesh)
    knife = new_knife(mesh)
    assert knife.click({"kind": "vertex", "vertex_id": vid(mesh, 1.0, 1.0)})
    edge = edge_between(mesh, vid(mesh, 1.5, 1.0), vid(mesh, 2.0, 1.0))
    target = {"kind": "edge", "edge_id": edge, "t": 0.5}
    assert knife.hover(target)["valid"] is True  # hover stays as loose as documented
    assert knife.accepts(target) is False
    assert knife.click(target) is False
    assert content(mesh) == before and knife.path_edges == []
    assert knife.start == vid(mesh, 1.0, 1.0)
    assert_mesh_invariants(mesh, context="R3 knife edge")
    assert_no_degenerate_face(mesh)


def test_r3_knife_ordinary_chord_from_the_same_vertex_still_works():
    mesh = grid_with_straight_vertices()
    knife = new_knife(mesh)
    assert knife.click({"kind": "vertex", "vertex_id": vid(mesh, 1.0, 1.0)})
    target = {"kind": "vertex", "vertex_id": vid(mesh, 2.0, 2.0)}  # the quad's diagonal
    assert knife.accepts(target) is True and knife.click(target) is True
    assert_mesh_invariants(mesh, context="R3 knife valid chord")
    assert_no_degenerate_face(mesh)


def test_r3_vertex_connect_is_a_noop():
    mesh = grid_with_straight_vertices()
    scene = scene_of(mesh)
    before = mesh.export_state()
    assert connect_vertices_per_face(scene, {vid(mesh, 1.0, 1.0), vid(mesh, 2.0, 1.0)}) == []
    assert mesh.export_state() == before and len(scene.history) == 0
    assert_mesh_invariants(mesh, context="R3 vertex connect")


def test_r3_edge_connect_halves_of_a_split_edge_rejected_and_restored():
    mesh = grid_with_straight_vertices()
    scene = scene_of(mesh)
    mid = vid(mesh, 1.5, 1.0)
    halves = {edge_between(mesh, vid(mesh, 1.0, 1.0), mid), edge_between(mesh, mid, vid(mesh, 2.0, 1.0))}
    before = mesh.export_state()
    with pytest.raises(TopologyToolError):
        connect_selected_edges_per_face(scene, halves)
    assert content(mesh) == content(Mesh.from_state(before)) and len(scene.history) == 0
    assert_mesh_invariants(mesh, context="R3 edge connect")
    assert_no_degenerate_face(mesh)


def test_r3_connect_in_shared_face_returns_none_and_leaves_the_mesh_alone():
    mesh = grid_with_straight_vertices()
    before = mesh.export_state()
    assert connect_in_shared_face(mesh, vid(mesh, 1.0, 1.0), vid(mesh, 2.0, 1.0)) is None
    assert mesh.export_state() == before


# -- R5: chord leaves a concave face -------------------------------------------------------


def test_r5_l_face_knife_across_the_missing_corner_refused():
    mesh = build_l_face()
    before = mesh.export_state()
    knife = new_knife(mesh)
    assert knife.click({"kind": "vertex", "vertex_id": vid(mesh, 2.0, 1.0)})
    target = {"kind": "vertex", "vertex_id": vid(mesh, 1.0, 2.0)}
    assert knife.accepts(target) is False and knife.click(target) is False
    assert mesh.export_state() == before
    # ... while a chord inside the same face is fine
    inner = {"kind": "vertex", "vertex_id": vid(mesh, 0.0, 0.0)}
    assert knife.accepts(inner) is True and knife.click(inner) is True
    assert_mesh_invariants(mesh, context="R5 L knife")


def test_r5_l_face_vertex_connect_is_a_noop():
    mesh = build_l_face()
    scene = scene_of(mesh)
    before = mesh.export_state()
    assert connect_vertices_per_face(scene, {vid(mesh, 2.0, 1.0), vid(mesh, 1.0, 2.0)}) == []
    assert mesh.export_state() == before and len(scene.history) == 0


def test_r5_l_face_edge_connect_across_the_missing_corner_rejected_and_restored():
    """Not probed in the discovery (open point): the midpoints (2, .5) and (1, 1.5) would be joined
    by a chord that leaves the L."""
    mesh = build_l_face()
    scene = scene_of(mesh)
    a = edge_between(mesh, vid(mesh, 2.0, 0.0), vid(mesh, 2.0, 1.0))
    b = edge_between(mesh, vid(mesh, 1.0, 1.0), vid(mesh, 1.0, 2.0))
    before = mesh.export_state()
    with pytest.raises(TopologyToolError):
        connect_selected_edges_per_face(scene, {a, b})
    assert content(mesh) == content(Mesh.from_state(before)) and len(scene.history) == 0
    assert_mesh_invariants(mesh, context="R5 L edge connect")


def test_r5_l_face_edge_connect_inside_the_l_still_works():
    mesh = build_l_face()
    scene = scene_of(mesh)
    a = edge_between(mesh, vid(mesh, 0.0, 0.0), vid(mesh, 2.0, 0.0))
    b = edge_between(mesh, vid(mesh, 1.0, 2.0), vid(mesh, 0.0, 2.0))
    assert len(connect_selected_edges_per_face(scene, {a, b})) == 1
    assert len(scene.history) == 1
    assert_mesh_invariants(mesh, context="R5 L edge connect valid")


def test_r5_concave_grid_face_every_route_refused():
    mesh = grid_with_concave_face()
    m1, m2 = vid(mesh, 0.5, 0.0), vid(mesh, 0.0, 0.5)
    right, top = vid(mesh, 1.0, 0.0), vid(mesh, 0.0, 1.0)
    before = mesh.export_state()
    # (m1, m2) is the diagonal of the cut-off corner quad: a valid chord there, not our case.
    # (1,0) -> (0, .5) and (0,1) -> (.5, 0) run over the cut-off corner, out of the hexagon.
    assert connect_in_shared_face(mesh, right, m2) is None
    assert connect_in_shared_face(mesh, top, m1) is None
    scene = scene_of(mesh)
    assert connect_vertices_per_face(scene, {right, m2}) == []
    assert mesh.export_state() == before

    # The discovery's L1 session 2: edge point (0.8, 0) -> edge point (0, 0.8), also over the corner
    knife = new_knife(mesh)
    first = {"kind": "edge", "edge_id": edge_between(mesh, m1, vid(mesh, 1.0, 0.0)), "t": 0.6}
    assert knife.click(first)  # the split itself is the start
    second = {"kind": "edge", "edge_id": edge_between(mesh, m2, vid(mesh, 0.0, 1.0)), "t": 0.6}
    assert knife.accepts(second) is False and knife.click(second) is False
    knife.undo_step()
    assert content(mesh) == content(Mesh.from_state(before))
    assert_mesh_invariants(mesh, context="R5 concave grid")


# -- no regression: valid chords are unchanged ---------------------------------------------


def _old_connect(mesh, a, b):
    """The selection rule before F2, verbatim: lowest-id face with a, b non-adjacent; no geometry."""
    for fid in sorted(mesh.all_face_ids(), key=int):
        boundary = mesh.face_vertices(fid)
        if a not in boundary or b not in boundary:
            continue
        n = len(boundary)
        dist = (boundary.index(b) - boundary.index(a)) % n
        if dist == 1 or dist == n - 1:
            continue
        try:
            return mesh.connect_vertices(fid, a, b)[0], fid
        except Exception:
            continue
    return None, None


def _old_result_is_valid(mesh, fid, children) -> bool:
    """Non-planar-safe oracle (quads: cube, head), independent of the predicate: both children keep
    the parent's normal direction and have area."""
    parent = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
    pn = _newell(parent)
    parent_area = _area3(parent)
    for child in children:
        cn = _newell(child)
        if sum(x * y for x, y in zip(pn, cn)) <= 0.0 or _area3(child) <= 1e-9 * parent_area:
            return False
    return True


def _inside_polygon(pt, poly) -> bool:
    inside = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > pt[1]) != (y2 > pt[1]) and x1 + (pt[1] - y1) * (x2 - x1) / (y2 - y1) > pt[0]:
            inside = not inside
    return inside


def _dist_to_segment(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    s = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (a[0] + s * dx, a[1] + s * dy))


def _planar_oracle(mesh, fid, a, b) -> bool:
    """Brute-force oracle for meshes in z = 0, independent of the predicate: the chord is valid iff
    sampled points along it lie strictly inside the face polygon (even-odd rule, away from every
    boundary edge) and no other corner of the face sits on the chord."""
    boundary = mesh.face_vertices(fid)
    poly = [mesh.vertex_position(v)[:2] for v in boundary]
    pa, pb = mesh.vertex_position(a)[:2], mesh.vertex_position(b)[:2]
    if any(_dist_to_segment(q, pa, pb) < 1e-9 for v, q in zip(boundary, poly) if v not in (a, b)):
        return False
    for i in range(64):
        t = (i + 0.5) / 64
        pt = (pa[0] + t * (pb[0] - pa[0]), pa[1] + t * (pb[1] - pa[1]))
        if not _inside_polygon(pt, poly):
            return False
        if min(_dist_to_segment(pt, poly[j], poly[(j + 1) % len(poly)]) for j in range(len(poly))) < 1e-9:
            return False
    return True


PLANAR = ("grid", "grid+splits", "L", "concave grid")


def _shared_face_pairs(mesh):
    pairs = set()
    for fid in mesh.all_face_ids():
        vs = mesh.face_vertices(fid)
        for i in range(len(vs)):
            for j in range(i + 1, len(vs)):
                pairs.add(tuple(sorted((vs[i], vs[j]), key=int)))
    return sorted(pairs, key=lambda p: (int(p[0]), int(p[1])))


def _scenes():
    scenes = {
        "grid": build_grid,
        "cube": create_cube,
        "grid+splits": grid_with_straight_vertices,
        "L": build_l_face,
        "concave grid": grid_with_concave_face,
    }
    if HEAD_ASSET.is_file():
        scenes["head"] = head_mesh
    return scenes


@pytest.mark.parametrize("name", list(_scenes()))
def test_every_previously_valid_chord_is_unchanged(name):
    base = _scenes()[name]()
    state = base.export_state()
    checked = changed = 0
    for a, b in _shared_face_pairs(base):
        old_mesh = Mesh.from_state(state)
        faces_before = {f: old_mesh.face_vertices(f) for f in old_mesh.all_face_ids()}
        old_edge, fid = _old_connect(old_mesh, a, b)
        if old_edge is None:
            continue
        if name in PLANAR:
            valid = _planar_oracle(base, fid, a, b)
        else:
            children = [
                [old_mesh.vertex_position(v) for v in old_mesh.face_vertices(f)]
                for f in old_mesh.all_face_ids() if f not in faces_before
            ]
            valid = _old_result_is_valid(base, fid, children)

        new_mesh = Mesh.from_state(state)
        new_edge = connect_in_shared_face(new_mesh, a, b)
        checked += 1
        if valid:
            assert new_edge == old_edge and new_mesh.export_state() == old_mesh.export_state(), (name, a, b)
        else:
            changed += 1
            # Refused, or routed through a later face in which the chord is valid: never broken.
            assert_mesh_invariants(new_mesh, context=f"{name} {a!r}-{b!r}")
            assert_no_degenerate_face(new_mesh)
    assert checked > 0
    if name in ("grid", "cube", "head"):
        assert changed == 0, f"{name}: chords the old rule connected validly must be all there is"


@pytest.mark.parametrize("name", PLANAR)
def test_predicate_agrees_with_the_brute_force_oracle_on_every_face_and_pair(name):
    mesh = _scenes()[name]()
    checked = 0
    for fid in mesh.all_face_ids():
        vs = mesh.face_vertices(fid)
        n = len(vs)
        for i in range(n):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue  # adjacent
                checked += 1
                assert chord_valid_in_face(mesh, fid, vs[i], vs[j]) == _planar_oracle(mesh, fid, vs[i], vs[j]), \
                    (name, fid, vs[i], vs[j])
    assert checked > 0


@pytest.mark.skipif(not HEAD_ASSET.is_file(), reason="head asset not found (examples/meshes/)")
def test_head_loses_no_valid_chord():
    """Head quads are non-planar: every quad diagonal the old rule cut into two properly wound
    children is still offered by the predicate."""
    mesh = head_mesh()
    refused = [
        (f, a, b)
        for f in mesh.all_face_ids()
        for a, b in ((mesh.face_vertices(f)[0], mesh.face_vertices(f)[2]),
                     (mesh.face_vertices(f)[1], mesh.face_vertices(f)[3]))
        if not chord_valid_in_face(mesh, f, a, b)
    ]
    # whatever the predicate refuses, the old rule's result must have been broken there too
    for f, a, b in refused:
        probe = Mesh.from_state(mesh.export_state())
        parent = [probe.vertex_position(v) for v in probe.face_vertices(f)]
        _edge, c1, c2 = probe.connect_vertices(f, a, b)
        children = [[probe.vertex_position(v) for v in probe.face_vertices(c)] for c in (c1, c2)]
        assert not _old_result_is_valid(mesh, f, children), (f, a, b, parent)


# -- determinism, helper contract ----------------------------------------------------------


def test_chord_faces_are_ascending_and_deterministic():
    mesh = grid_with_straight_vertices()
    a, b = vid(mesh, 1.0, 1.0), vid(mesh, 2.0, 2.0)
    first = list(chord_faces(mesh, a, b))
    assert first == list(chord_faces(mesh, a, b)) and first == sorted(first, key=int)
    assert list(chord_faces(mesh, a, a)) == []


def test_connect_in_shared_face_is_deterministic_across_runs():
    states = []
    for _ in range(2):
        mesh = grid_with_straight_vertices()
        connect_in_shared_face(mesh, vid(mesh, 1.0, 1.0), vid(mesh, 2.0, 2.0))
        connect_in_shared_face(mesh, vid(mesh, 1.0, 1.0), vid(mesh, 2.0, 1.0))
        states.append(mesh.export_state())
    assert states[0] == states[1]


def test_chord_valid_in_face_false_when_a_vertex_is_not_on_the_face():
    mesh = build_grid()
    face = sorted(mesh.all_face_ids(), key=int)[0]
    assert not chord_valid_in_face(mesh, face, vid(mesh, 4.0, 4.0), vid(mesh, 0.0, 0.0))


def test_edge_point_predicate_matches_the_split_it_predicts():
    """`chord_valid_to_edge_point` (used by `accepts`) agrees with the real split + chord."""
    for build in (grid_with_straight_vertices, grid_with_concave_face, build_l_face):
        base = build()
        state = base.export_state()
        for start in sorted(base.all_vertex_ids(), key=int):
            for edge in sorted(base.all_edge_ids(), key=int):
                if start in base.edge_vertices(edge):
                    continue
                for t in (0.25, 0.5, 0.8):
                    predicted = any(
                        chord_valid_to_edge_point(base, f, start, edge, t) for f in base.edge_faces(edge)
                    )
                    mesh = Mesh.from_state(state)
                    mid = mesh.split_edge(edge, t)[0]
                    actual = connect_in_shared_face(mesh, start, mid) is not None
                    assert predicted == actual, (build.__name__, start, edge, t)


# -- Knife: accepts == click on every target ----------------------------------------------


@pytest.mark.parametrize("build", [grid_with_straight_vertices, grid_with_concave_face, build_l_face])
def test_knife_accepts_matches_click_on_every_vertex_and_edge_target(build):
    base = build()
    state = base.export_state()
    vertices = sorted(base.all_vertex_ids(), key=int)
    edges = sorted(base.all_edge_ids(), key=int)
    targets = [{"kind": "vertex", "vertex_id": v} for v in vertices]
    targets += [{"kind": "edge", "edge_id": e, "t": t} for e in edges for t in (0.3, 0.5)]
    refused = 0
    for start in vertices:
        for target in targets:
            mesh = Mesh.from_state(state)
            knife = new_knife(mesh)
            assert knife.click({"kind": "vertex", "vertex_id": start})
            expected = knife.accepts(target)
            before = content(mesh)
            clicked = knife.click(target)
            assert clicked is expected, (build.__name__, start, target)
            if not clicked:
                refused += 1
                assert content(mesh) == before
            assert_mesh_invariants(mesh, context=f"{build.__name__} {start!r} {target!r}")
            knife.cancel()
    assert refused > 0
