"""AD-037 Phase 1b: the texel -> surface map (`mirai.paint.texel_map`).

Pinned: (1) barycentric parity - a texel's weights interpolate its triangle's corner UVs to the texel centre, its
triangle is the drawn one (`triangulate_mesh_face`), and `face_hit`'s weights (`triangle_origin`) at the texel's surface
point name the same texel; (2) deformation invariance - one map serves any position table with the mesh's ids;
(3) patch == rebuild after random topology / UV sequences, Undo (rollback) included; (4) the ownership rules (overlap:
smaller face id; no texel for zero UV area, unmapped faces, UVs outside 0-1).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from core import FaceId, Mesh, VertexId, scene_from_dict
from core.mesh import MeshError
from mirai.paint.texel_map import TexelMap
from mirai.viewport.picking import triangle_origin
from viewport.derived import triangulate_mesh_face

GOLLUM = Path(__file__).resolve().parents[1] / "scenes" / "Gollum_Head_rigging_test.mirai.json"


def _head() -> Mesh:
    scene = scene_from_dict(json.loads(GOLLUM.read_text(encoding="utf-8")))
    return next(o for o in scene.objects.values() if o.texture and o.eye is None and o.mesh.has_face_uvs()).mesh


def grid(n: int = 4, uv_scale: float = 1.0) -> Mesh:
    """An n x n quad grid in the XY plane with a gentle bump (non-planar quads) and planar UVs."""
    mesh = Mesh()
    vid = {}
    for y in range(n + 1):
        for x in range(n + 1):
            vid[(x, y)] = mesh.add_vertex((float(x), float(y), 0.1 * ((x * 7 + y * 3) % 5)))
    for y in range(n):
        for x in range(n):
            corners = [(x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)]
            mesh.add_face([vid[c] for c in corners], uvs=[(cx / n * uv_scale, cy / n * uv_scale) for cx, cy in corners])
    return mesh


def map_signature(texel_map: TexelMap) -> tuple:
    """Per texel (face, triangle index, w1, w2) as arrays - independent of slot numbering."""
    slots = texel_map.slot
    held = slots >= 0
    face = np.where(held, texel_map.tri_face[np.where(held, slots, 0)], -1)
    index = np.where(held, texel_map.tri_index[np.where(held, slots, 0)], -1)
    return face, index, texel_map.bary.copy()


def assert_same_map(a: TexelMap, b: TexelMap) -> None:
    fa, ia, ba = map_signature(a)
    fb, ib, bb = map_signature(b)
    assert np.array_equal(fa, fb)
    assert np.array_equal(ia, ib)
    assert np.array_equal(ba, bb)


# -- (1) barycentric parity ------------------------------------------------------------------------------------------


def test_weights_interpolate_the_drawn_triangles_uvs_to_the_texel_centre_on_the_gollum_head():
    mesh = _head()
    texel_map = TexelMap(mesh, 512, 512)
    mapped = texel_map.mapped()
    assert mapped.size / (512 * 512) == pytest.approx(0.665, abs=0.005)  # audit §2.2: 66.5 % of the square
    rng = np.random.default_rng(7)
    sample = rng.choice(mapped, size=400, replace=False)
    centres = texel_map.texel_uvs(sample)
    for t, centre, (face, k, w1, w2) in zip(sample, centres, texel_map.owner(sample)):
        tri = triangulate_mesh_face(mesh, face)[k]
        assert tuple(texel_map.tri_vertices[texel_map.slot[t]]) == tri
        uv = [mesh.corner_uv(face, v) for v in tri]
        w0 = 1.0 - w1 - w2
        got = (w0 * uv[0][0] + w1 * uv[1][0] + w2 * uv[2][0], w0 * uv[0][1] + w1 * uv[1][1] + w2 * uv[2][1])
        assert got == pytest.approx(tuple(centre), abs=1e-6)
        assert min(w0, w1, w2) >= -1e-6


def test_the_face_hit_weights_at_a_texels_surface_point_name_the_same_texel():
    """`face_hit` returns `triangle_origin` weights of the hit point (picking.py); interpolating the UVs with them
    lands in the texel the point came from - the paint dab and the cursor agree."""
    mesh = _head()
    texel_map = TexelMap(mesh, 1024, 1024)
    rng = np.random.default_rng(11)
    sample = rng.choice(texel_map.mapped(), size=300, replace=False)
    points = texel_map.surface_points(sample)
    for t, point, (face, k, _w1, _w2) in zip(sample, points, texel_map.owner(sample)):
        tri = triangulate_mesh_face(mesh, face)[k]
        weights = triangle_origin(mesh, tri, tuple(point))
        if len(weights) == 1:
            continue  # a degenerate 3D triangle: its UV triangle is not (UV and surface disagree; no hit possible)
        u = sum(w * mesh.corner_uv(face, v)[0] for v, w in weights)
        v_ = sum(w * mesh.corner_uv(face, v)[1] for v, w in weights)
        assert texel_map.texel_at(u, v_) == t


# -- (2) deformation invariance --------------------------------------------------------------------------------------


class Table:
    def __init__(self, positions: dict) -> None:
        self.positions = positions

    def vertex_position(self, vid):
        return self.positions[vid]


def test_one_map_serves_a_deformed_position_table_without_a_rebuild():
    mesh = _head()
    texel_map = TexelMap(mesh, 256, 256)
    before = map_signature(texel_map)
    rng = np.random.default_rng(3)
    moved = {v: tuple(np.asarray(mesh.vertex_position(v)) + rng.normal(0.0, 0.01, 3)) for v in mesh.all_vertex_ids()}
    sample = rng.choice(texel_map.mapped(), size=200, replace=False)
    got = texel_map.surface_points(sample, Table(moved))
    for t, point in zip(sample, got):
        s = texel_map.slot[t]
        corners = [np.asarray(moved[VertexId(int(v))]) for v in texel_map.tri_vertices[s]]
        w1, w2 = (float(w) for w in texel_map.bary[t])
        assert point == pytest.approx((1 - w1 - w2) * corners[0] + w1 * corners[1] + w2 * corners[2], abs=1e-12)
    for a, b in zip(before, map_signature(texel_map)):
        assert np.array_equal(a, b)


def test_a_position_only_change_on_convex_faces_writes_nothing():
    mesh = grid()
    texel_map = TexelMap(mesh, 64, 64)
    watch = mesh.watch()
    before = map_signature(texel_map)
    for v in mesh.all_vertex_ids():
        p = mesh.vertex_position(v)
        mesh.set_vertex_position(v, (p[0] * 1.5, p[1], p[2] + 0.3))
    assert texel_map.patch(watch.take()) == 0
    for a, b in zip(before, map_signature(texel_map)):
        assert np.array_equal(a, b)


def test_a_move_that_changes_a_concave_faces_triangulation_repatches_it():
    mesh = Mesh()
    pts = [(0, 0), (4, 0), (4, 4), (3, 4), (3, 1), (0, 1)]  # an L: concave at (3, 1)
    ids = [mesh.add_vertex((float(x), float(y), 0.0)) for x, y in pts]
    mesh.add_face(ids, uvs=[(x / 4.0, y / 4.0) for x, y in pts])
    texel_map = TexelMap(mesh, 32, 32)
    watch = mesh.watch()
    mesh.set_vertex_position(ids[4], (1.0, 3.0, 0.0))  # the notch moves: another ear first
    assert texel_map.patch(watch.take()) == 1
    assert_same_map(texel_map, TexelMap(mesh, 32, 32))


# -- (3) patch == rebuild --------------------------------------------------------------------------------------------


def _random_step(mesh: Mesh, rng: random.Random) -> None:
    faces = mesh.all_face_ids()
    kind = rng.choice(["split", "connect", "collapse", "dissolve", "delete", "uvs", "unmap", "move", "add"])
    if kind == "split":
        edges = sorted({e for f in faces for e in mesh.face_edges(f)})
        mesh.split_edge(rng.choice(edges), rng.uniform(0.2, 0.8))
    elif kind == "connect":
        f = rng.choice(faces)
        b = mesh.face_vertices(f)
        if len(b) >= 4:
            i = rng.randrange(len(b))
            mesh.connect_vertices(f, b[i], b[(i + 2) % len(b)])
    elif kind == "collapse":
        f = rng.choice(faces)
        mesh.collapse_edge(rng.choice(mesh.face_edges(f)))
    elif kind == "dissolve":
        f = rng.choice(faces)
        inner = [e for e in mesh.face_edges(f) if len(mesh.edge_faces(e)) == 2]
        if inner:
            mesh.dissolve_edges([rng.choice(inner)], cleanup=True)
    elif kind == "delete" and len(faces) > 4:
        mesh.delete_faces([rng.choice(faces)])
    elif kind == "uvs":  # a face's UVs moved onto another face's area: an overlap
        f = rng.choice(faces)
        n = len(mesh.face_vertices(f))
        du, dv = rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3)
        uvs = mesh.face_uvs(f) or [(rng.random(), rng.random()) for _ in range(n)]
        mesh.set_face_uvs(f, [(u + du, v + dv) for u, v in uvs])
    elif kind == "unmap":
        mesh.set_face_uvs(rng.choice(faces), None)
    elif kind == "move":
        v = rng.choice(mesh.all_vertex_ids())
        p = mesh.vertex_position(v)
        mesh.set_vertex_position(v, (p[0] + rng.uniform(-0.4, 0.4), p[1] + rng.uniform(-0.4, 0.4), p[2]))
    elif kind == "add":
        a, b, c = rng.sample(mesh.all_vertex_ids(), 3)
        mesh.add_face([a, b, c], uvs=[(rng.random(), rng.random()) for _ in range(3)], infer_uvs=False)


@pytest.mark.parametrize("seed", range(12))
def test_patch_equals_rebuild_after_random_topology_and_uv_sequences(seed):
    rng = random.Random(seed)
    mesh = grid(5)
    texel_map = TexelMap(mesh, 48, 48)
    watch = mesh.watch()
    for _ in range(25):
        change = mesh.begin_change()
        try:
            _random_step(mesh, rng)
        except MeshError:
            mesh.rollback_change(change)
        else:
            if rng.random() < 0.2:
                mesh.rollback_change(change)  # Undo of a step: the journal restores it exactly
            else:
                mesh.end_change(change)
        texel_map.patch(watch.take())
        assert_same_map(texel_map, TexelMap(mesh, 48, 48))


def test_a_large_change_rebuilds():
    mesh = grid(10)
    texel_map = TexelMap(mesh, 32, 32)
    watch = mesh.watch()
    for f in mesh.all_face_ids():
        mesh.set_face_uvs(f, [(u * 0.5, v * 0.5) for u, v in mesh.face_uvs(f)])
    assert texel_map.patch(watch.take()) == -1
    assert_same_map(texel_map, TexelMap(mesh, 32, 32))


# -- (4) ownership ---------------------------------------------------------------------------------------------------


def test_an_overlap_goes_to_the_smaller_face_id_and_back_when_it_is_removed():
    mesh = grid(2)
    faces = mesh.all_face_ids()
    first, last = faces[0], faces[-1]
    texel_map = TexelMap(mesh, 32, 32)
    watch = mesh.watch()
    mesh.set_face_uvs(last, mesh.face_uvs(first))  # the last face now lies on the first face's UV area
    texel_map.patch(watch.take())
    owners = {face for face, *_ in texel_map.owner(texel_map.mapped())}
    assert last not in owners and first in owners  # the smaller id keeps every shared texel
    mesh.delete_faces([first])
    texel_map.patch(watch.take())
    owners = {face for face, *_ in texel_map.owner(texel_map.mapped())}
    assert last in owners  # refilled from the remaining face
    assert_same_map(texel_map, TexelMap(mesh, 32, 32))


def test_zero_area_unmapped_and_outside_parts_hold_no_texel():
    mesh = grid(2)
    a, b, c, d = mesh.all_face_ids()
    mesh.set_face_uvs(a, [(0.1, 0.1), (0.4, 0.1), (0.4, 0.1), (0.1, 0.1)])  # a wall: a line in UV
    mesh.set_face_uvs(b, None)
    mesh.set_face_uvs(c, [(u + 0.75, v) for u, v in mesh.face_uvs(c)])  # partly beyond u = 1
    texel_map = TexelMap(mesh, 16, 16)
    owners = [face for face, *_ in texel_map.owner(texel_map.mapped())]
    assert a not in owners and b not in owners
    uvs = texel_map.texel_uvs([t for t, f in zip(texel_map.mapped(), owners) if f == c])
    assert uvs.size and uvs[:, 0].max() < 1.0
    with pytest.raises(ValueError):
        texel_map.surface_points([int(np.nonzero(texel_map.slot < 0)[0][0])])


def test_texel_rows_start_at_v_zero():
    mesh = Mesh()
    ids = [mesh.add_vertex(p) for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0))]
    mesh.add_face(ids, uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 0.5), (0.0, 0.5)])  # the lower half of the image
    texel_map = TexelMap(mesh, 4, 4)
    assert sorted(texel_map.mapped().tolist()) == list(range(8))  # rows 0 and 1: v in [0, 0.5)
    assert texel_map.surface_points([0])[0] == pytest.approx((0.125, 0.25, 0.0))
    assert texel_map.texel_at(0.99, 0.99) == 15 and texel_map.texel_at(1.0, 0.5) == -1
    assert FaceId(texel_map.tri_face[texel_map.slot[0]]) == mesh.all_face_ids()[0]
