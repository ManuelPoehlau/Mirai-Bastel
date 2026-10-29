"""Face-corner UVs in the Core (AD-026): storage, journal, file and the rule of every topology primitive.

The fixture is a 3 x 2 quad grid with planar UVs u = x / 3, v = y / 2 and a **seam** between column 1
and column 2 (the right column is shifted by +1 in u), so every rule is checked both where the UVs are
continuous and where a corner must keep its own value.
"""

from __future__ import annotations

import json
import random

import pytest

import tests._bootstrap  # noqa: F401

from core.corner_uvs import polygon_weights
from core.mesh import Mesh, MeshError
from core.operations.collapse import collapse_elements
from tests.mesh_invariants import assert_mesh_invariants, assert_uv_invariants

SEAM_X = 2.0
SHIFT = 1.0


def planar_uv(p) -> tuple[float, float]:
    return (p[0] / 3.0, p[1] / 2.0)


def grid() -> tuple[Mesh, dict]:
    mesh = Mesh()
    vid = {}
    for y in range(3):
        for x in range(4):
            vid[(x, y)] = mesh.add_vertex((float(x), float(y), 0.0))
    for y in range(2):
        for x in range(3):
            corners = [(x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)]
            uvs = [planar_uv(c) for c in corners]
            if x == 2:
                uvs = [(u + SHIFT, v) for u, v in uvs]
            mesh.add_face([vid[c] for c in corners], uvs=uvs)
    return mesh, vid


def expected(mesh: Mesh, fid, vertex) -> tuple[float, float]:
    """The planar UV a corner should have: its position's, shifted in the right column."""
    u, v = planar_uv(mesh.vertex_position(vertex))
    xs = [mesh.vertex_position(w)[0] for w in mesh.face_vertices(fid)]
    if min(xs) >= SEAM_X - 1e-9:
        u += SHIFT
    return (u, v)


def assert_planar(mesh: Mesh, faces=None) -> None:
    for fid in faces or mesh.all_face_ids():
        uvs = mesh.face_uvs(fid)
        assert uvs is not None, fid
        for v, uv in zip(mesh.face_vertices(fid), uvs):
            assert uv == pytest.approx(expected(mesh, fid, v), abs=1e-12), (fid, v)


def content(mesh: Mesh) -> str:
    """The export without the ID counters (they only move forward, AD-001), as JSON text (ordered)."""
    return json.dumps({k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")})


def edge(mesh: Mesh, a, b):
    for eid in mesh.vertex_edges(a):
        if b in mesh.edge_vertices(eid):
            return eid
    raise KeyError((a, b))


def test_storage_and_validation():
    mesh, vid = grid()
    assert mesh.has_face_uvs()
    fid = mesh.all_face_ids()[0]
    assert mesh.corner_uv(fid, vid[(1, 1)]) == (1 / 3, 0.5)
    with pytest.raises(MeshError):
        mesh.set_face_uvs(fid, [(0, 0)] * 3)
    with pytest.raises(MeshError):
        mesh.set_face_uvs(fid, [(0, float("nan"))] * 4)
    with pytest.raises(MeshError):
        mesh.add_face([vid[(0, 0)], vid[(1, 0)], vid[(1, 1)]], uvs=[(0, 0)])
    assert len(mesh.all_face_ids()) == 6  # the refused add_face changed nothing
    mesh.set_face_uvs(fid, None)
    assert mesh.face_uvs(fid) is None
    assert_uv_invariants(mesh)


def test_mesh_without_uvs_is_unchanged():
    mesh = Mesh()
    vs = [mesh.add_vertex(p) for p in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]]
    fid = mesh.add_face(vs)
    assert not mesh.has_face_uvs() and mesh.face_uvs(fid) is None
    assert mesh.export_state()["face_uvs"] is None
    mesh.split_edge(mesh.face_edges(fid)[0])
    assert not mesh.has_face_uvs()


@pytest.mark.parametrize("t", [0.5, 0.25])
def test_split_edge_keeps_uvs_and_seam(t):
    mesh, vid = grid()
    mesh.split_edge(edge(mesh, vid[(1, 1)], vid[(2, 1)]), t)  # interior edge, continuous
    mesh.split_edge(edge(mesh, vid[(2, 0)], vid[(2, 1)]), t)  # on the seam
    assert_planar(mesh)
    assert_uv_invariants(mesh)


def test_connect_and_split_face():
    mesh, vid = grid()
    left = next(f for f in mesh.all_face_ids() if vid[(0, 0)] in mesh.face_vertices(f))
    mesh.connect_vertices(left, vid[(0, 0)], vid[(1, 1)])
    right = next(f for f in mesh.all_face_ids() if vid[(3, 0)] in mesh.face_vertices(f))
    new, _edges, a, b = mesh.split_face(right, vid[(2, 0)], vid[(3, 1)], [(2.4, 0.3, 0.0), (2.7, 0.8, 0.0)])
    assert_planar(mesh)  # mean value coordinates are exact for an affine map on a planar quad
    assert_uv_invariants(mesh)


def test_split_face_uses_the_origin_when_its_sources_are_corners():
    mesh, vid = grid()
    face = next(f for f in mesh.all_face_ids() if vid[(0, 0)] in mesh.face_vertices(f))
    origin = ((vid[(0, 0)], 0.5), (vid[(1, 0)], 0.25), (vid[(1, 1)], 0.25))
    new, _e, a, _b = mesh.split_face(face, vid[(0, 0)], vid[(1, 1)], [(0.7, 0.2, 0.0)], origins=[origin])
    u = 0.5 * 0 + 0.25 * (1 / 3) + 0.25 * (1 / 3)
    v = 0.25 * 0.5
    assert mesh.corner_uv(a, new[0]) == pytest.approx((u, v))


def test_collapse_edge_moves_continuous_corners_and_keeps_the_seam():
    mesh, vid = grid()
    survivor = mesh.collapse_edge(edge(mesh, vid[(1, 1)], vid[(1, 2)]))
    assert_planar(mesh)
    # on the seam: both sides keep their own value
    survivor = mesh.collapse_edge(edge(mesh, vid[(2, 0)], vid[(2, 1)]))
    sides = {mesh.corner_uv(f, survivor) for f in mesh.all_face_ids() if survivor in mesh.face_vertices(f)}
    assert {round(u, 9) for u, _v in sides} == {round(2 / 3, 9), round(2 / 3 + SHIFT, 9)}
    assert_planar(mesh)
    assert_uv_invariants(mesh)
    assert_mesh_invariants(mesh)


def test_collapse_elements_group():
    mesh, vid = grid()
    collapse_elements(mesh, [vid[(0, 1)], vid[(1, 1)]], [])
    assert_uv_invariants(mesh)
    assert_mesh_invariants(mesh)


def test_dissolve_merges_exactly_and_keeps_seam_values():
    mesh, vid = grid()
    mesh.dissolve_edges([edge(mesh, vid[(1, 0)], vid[(1, 1)])], cleanup=False)
    mesh.dissolve_vertex(vid[(2, 1)])  # merges across the seam: each corner keeps its face's value
    assert_uv_invariants(mesh)
    merged = next(f for f in mesh.all_face_ids() if vid[(3, 1)] in mesh.face_vertices(f) and vid[(1, 1)] in mesh.face_vertices(f))
    assert mesh.corner_uv(merged, vid[(3, 1)]) == pytest.approx((1.0 + SHIFT, 0.5))
    assert mesh.corner_uv(merged, vid[(1, 1)]) == pytest.approx((1 / 3, 0.5))


def test_dissolve_cleanup_drops_chain_corners():
    mesh, vid = grid()
    mid, _a, _b = mesh.split_edge(edge(mesh, vid[(1, 0)], vid[(1, 1)]))
    mesh.dissolve_vertex(mid)
    assert_planar(mesh)
    assert_uv_invariants(mesh)


def test_delete_removes_uvs():
    mesh, vid = grid()
    mesh.delete_vertices([vid[(1, 1)]])
    assert_uv_invariants(mesh)
    assert_planar(mesh)


def test_add_face_infers_from_neighbours():
    mesh, vid = grid()
    hole = next(f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) == {vid[(1, 0)], vid[(2, 0)], vid[(2, 1)], vid[(1, 1)]})
    boundary = mesh.face_vertices(hole)
    mesh.remove_face(hole)
    fid = mesh.add_face(boundary)
    # the corners left of the seam come from the face across their shared edge (continuous there);
    # on the seam the face across the edge is the shifted one - a seam cannot be read off a hole
    assert mesh.corner_uv(fid, vid[(1, 0)]) == pytest.approx((1 / 3, 0.0))
    assert mesh.corner_uv(fid, vid[(1, 1)]) == pytest.approx((1 / 3, 0.5))
    assert mesh.corner_uv(fid, vid[(2, 0)]) == pytest.approx((2 / 3 + SHIFT, 0.0))
    bare = mesh.add_face([vid[(0, 0)], vid[(1, 0)], vid[(2, 1)]], infer_uvs=False)
    assert mesh.face_uvs(bare) is None


def test_unresolved_corner_gets_the_mean_of_the_resolved_ones():
    mesh, vid = grid()
    lone = mesh.add_vertex((5.0, 5.0, 0.0))
    fid = mesh.add_face([vid[(3, 2)], lone, vid[(2, 2)]])
    a, b = mesh.corner_uv(fid, vid[(3, 2)]), mesh.corner_uv(fid, vid[(2, 2)])
    assert mesh.corner_uv(fid, lone) == pytest.approx(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))


def test_add_face_without_any_known_corner_has_no_uvs():
    mesh, _vid = grid()
    vs = [mesh.add_vertex(p) for p in [(9, 9, 0), (10, 9, 0), (10, 10, 0)]]
    fid = mesh.add_face(vs)
    assert mesh.face_uvs(fid) is None


def test_journal_undo_redo_rollback_exact():
    mesh, vid = grid()
    start = content(mesh)
    change = mesh.begin_change()
    mesh.split_edge(edge(mesh, vid[(1, 1)], vid[(2, 1)]), 0.3)
    mesh.collapse_edge(edge(mesh, vid[(0, 0)], vid[(1, 0)]))
    face = next(f for f in mesh.all_face_ids() if vid[(3, 2)] in mesh.face_vertices(f))
    mesh.set_face_uvs(face, [(0.0, 0.0)] * 4)
    after = content(mesh)
    delta = mesh.end_change(change)
    assert delta.face_uvs and not delta.empty
    mesh.apply_delta(delta, reverse=True)
    assert content(mesh) == start
    mesh.apply_delta(delta)
    assert content(mesh) == after
    change = mesh.begin_change()
    mesh.dissolve_vertex(vid[(1, 1)])
    mesh.rollback_change(change)
    assert content(mesh) == after


def test_uv_only_change_is_a_delta_and_wakes_watches():
    mesh, _vid = grid()
    watch = mesh.watch()
    change = mesh.begin_change()
    face = mesh.all_face_ids()[0]
    mesh.set_face_uvs(face, [(0.0, 0.0)] * 4)
    delta = mesh.end_change(change)
    assert not delta.empty and set(delta.face_uvs) == {face}
    assert face in watch.take().face_uvs


def test_file_roundtrip_and_fail_closed_load():
    mesh, _vid = grid()
    text = json.dumps(mesh.export_state())
    assert json.dumps(Mesh.from_state(json.loads(text)).export_state()) == text
    state = json.loads(text)
    fid = next(iter(state["face_uvs"]))
    state["face_uvs"][fid] = [[0, 0]]
    target, _ = grid()
    before = json.dumps(target.export_state())
    with pytest.raises(ValueError):
        target.load_state(state)
    assert json.dumps(target.export_state()) == before
    state = json.loads(text)
    state.pop("face_uvs")  # an old file: no UVs
    assert not Mesh.from_state(state).has_face_uvs()


def test_load_state_under_a_journal_writes_only_what_differs():
    mesh, _vid = grid()
    other, _ = grid()
    face = other.all_face_ids()[1]
    other.set_face_uvs(face, [(0.5, 0.5)] * 4)
    watch = mesh.watch()
    mesh.load_state(other.export_state())
    assert set(watch.take().face_uvs) == {face}
    assert mesh.face_uvs(face) == ((0.5, 0.5),) * 4


def test_polygon_weights_reproduce_affine_functions():
    square = [(0.0, 0.0, 1.0), (2.0, 0.0, 1.0), (2.0, 1.0, 1.0), (0.0, 1.0, 1.0)]
    for p in [(0.3, 0.6, 1.0), (1.9, 0.1, 1.0), (1.0, 0.0, 1.0), (2.0, 1.0, 1.0)]:
        w = polygon_weights(square, p)
        assert sum(w) == pytest.approx(1.0)
        assert sum(wi * q[0] for wi, q in zip(w, square)) == pytest.approx(p[0])
        assert sum(wi * q[1] for wi, q in zip(w, square)) == pytest.approx(p[1])
    concave = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (1, 2, 0), (1, 1, 0), (0, 1, 0)]
    w = polygon_weights(concave, (0.5, 0.5, 0))
    assert sum(wi * q[0] for wi, q in zip(w, concave)) == pytest.approx(0.5)


def test_random_sequences_keep_invariants_and_undo_exactly():
    rng = random.Random(26)
    for _ in range(25):
        mesh, _vid = grid()
        start = content(mesh)
        change = mesh.begin_change()
        for _step in range(8):
            op = rng.choice(["split", "connect", "collapse", "dissolve", "knife"])
            try:
                if op == "split":
                    mesh.split_edge(rng.choice(mesh.all_edge_ids()), rng.uniform(0.1, 0.9))
                elif op == "connect":
                    f = rng.choice(mesh.all_face_ids())
                    b = mesh.face_vertices(f)
                    if len(b) >= 4:
                        # split_face(k = 0) = connect_vertices, but refuses a chord that is already an
                        # edge (connect_vertices would attach it to a third face - not a UV question)
                        mesh.split_face(f, b[0], b[2])
                elif op == "collapse":
                    mesh.collapse_edge(rng.choice(mesh.all_edge_ids()))
                elif op == "dissolve":
                    mesh.dissolve_edges([rng.choice(mesh.all_edge_ids())], cleanup=True)
                else:
                    f = rng.choice(mesh.all_face_ids())
                    b = mesh.face_vertices(f)
                    pts = [mesh.vertex_position(v) for v in b]
                    centre = tuple(sum(c) / len(pts) for c in zip(*pts))
                    mesh.split_face(f, b[0], b[len(b) // 2], [centre])
            except MeshError:
                continue
            assert_mesh_invariants(mesh)
            assert_uv_invariants(mesh)
        delta = mesh.end_change(change)
        mesh.apply_delta(delta, reverse=True)
        assert content(mesh) == start
