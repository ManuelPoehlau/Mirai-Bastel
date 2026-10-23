"""Add Mesh primitives (Track A1, 2026-10-23): `scene_factory.PRIMITIVES` - plane, cube, sphere, cylinder.

Topology only, no `Application`: counts, Euler characteristic, consistent face winding (every
interior edge is traversed once in each direction), outward normals, and the documented defaults.
The primitives must be ordinary editable polygon meshes; `assert_mesh_invariants` is the Core's
own catalogue.
"""

from __future__ import annotations

import math
from collections import Counter

import pytest

import tests._bootstrap  # noqa: F401
from tests.mesh_invariants import assert_face_triangulations_sound, assert_mesh_invariants

from mirai import scene_factory
from mirai.scene_factory import (
    CYLINDER_VERTICES,
    PLANE_SEGMENTS,
    PRIMITIVES,
    SPHERE_RINGS,
    SPHERE_SEGMENTS,
    create_cube,
    create_cylinder,
    create_plane,
    create_sphere,
    primitive_names,
)

#: name -> (vertices, faces, closed) of the documented defaults.
_EXPECTED = {
    "plane": ((PLANE_SEGMENTS + 1) ** 2, PLANE_SEGMENTS**2, False),
    "cube": (8, 6, True),
    "sphere": (
        2 + (SPHERE_RINGS - 1) * SPHERE_SEGMENTS,
        SPHERE_SEGMENTS * SPHERE_RINGS,
        True,
    ),
    "cylinder": (2 * CYLINDER_VERTICES, CYLINDER_VERTICES + 2, True),
}


def _directed_edges(mesh) -> Counter:
    counts: Counter = Counter()
    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        for a, b in zip(boundary, boundary[1:] + boundary[:1]):
            counts[(a, b)] += 1
    return counts


def _face_normal(mesh, fid):
    """Newell normal of the (possibly n-gon) face - robust for non-triangles."""
    pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
    nx = ny = nz = 0.0
    for (x0, y0, z0), (x1, y1, z1) in zip(pts, pts[1:] + pts[:1]):
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return nx, ny, nz


def _centroid(points):
    n = len(points)
    return tuple(sum(p[i] for p in points) / n for i in range(3))


def test_menu_order_is_plane_cube_sphere_cylinder():
    assert primitive_names() == ("plane", "cube", "sphere", "cylinder")
    assert tuple(PRIMITIVES) == primitive_names()
    assert PRIMITIVES["cube"] is create_cube  # the existing factory is reused, not copied


@pytest.mark.parametrize("name", list(_EXPECTED))
def test_primitive_is_a_valid_polygon_mesh_with_the_documented_counts(name):
    mesh = PRIMITIVES[name]()
    vertices, faces, closed = _EXPECTED[name]
    assert_mesh_invariants(mesh, context=name)
    assert len(mesh.all_vertex_ids()) == vertices
    assert len(mesh.all_face_ids()) == faces
    euler = len(mesh.all_vertex_ids()) - len(mesh.all_edge_ids()) + len(mesh.all_face_ids())
    assert euler == (2 if closed else 1)  # sphere topology / disc topology
    assert mesh.symmetry_definition is None  # a fresh primitive carries no symmetry definition


@pytest.mark.parametrize("name", list(_EXPECTED))
def test_face_winding_is_consistent(name):
    """Each directed edge is used at most once; a closed mesh has the reverse of every one, an open
    mesh only on its boundary - so no face is flipped against its neighbours."""
    mesh = PRIMITIVES[name]()
    directed = _directed_edges(mesh)
    assert max(directed.values()) == 1
    unmatched = [edge for edge in directed if (edge[1], edge[0]) not in directed]
    if _EXPECTED[name][2]:
        assert unmatched == []
    else:
        assert len(unmatched) == 4 * PLANE_SEGMENTS  # exactly the outline


@pytest.mark.parametrize("name", ["cube", "sphere", "cylinder"])
def test_closed_primitives_face_outward_and_enclose_positive_volume(name):
    mesh = PRIMITIVES[name]()
    centre = _centroid([mesh.vertex_position(v) for v in mesh.all_vertex_ids()])
    for fid in mesh.all_face_ids():
        normal = _face_normal(mesh, fid)
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
        out = tuple(c - o for c, o in zip(_centroid(pts), centre))
        assert sum(n * o for n, o in zip(normal, out)) > 0, f"{name} face {fid!r} points inward"


def test_plane_is_a_flat_grid_facing_plus_y():
    mesh = create_plane()
    assert {mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()} == {0.0}
    xs = sorted({round(mesh.vertex_position(v)[0], 9) for v in mesh.all_vertex_ids()})
    assert xs[0] == -1.0 and xs[-1] == 1.0 and len(xs) == PLANE_SEGMENTS + 1
    for fid in mesh.all_face_ids():
        nx, ny, nz = _face_normal(mesh, fid)
        assert ny > 0 and nx == pytest.approx(0.0) and nz == pytest.approx(0.0)
    single = create_plane(segments=1)
    assert len(single.all_face_ids()) == 1  # the one-quad plane stays available
    with pytest.raises(ValueError):
        create_plane(segments=0)


def test_sphere_has_radius_one_poles_on_y_and_triangle_fans_at_the_poles():
    mesh = create_sphere()
    radii = [math.dist((0.0, 0.0, 0.0), mesh.vertex_position(v)) for v in mesh.all_vertex_ids()]
    assert all(r == pytest.approx(1.0) for r in radii)
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    assert max(ys) == pytest.approx(1.0) and min(ys) == pytest.approx(-1.0)
    sizes = Counter(len(mesh.face_vertices(f)) for f in mesh.all_face_ids())
    assert sizes == {3: 2 * SPHERE_SEGMENTS, 4: SPHERE_SEGMENTS * (SPHERE_RINGS - 2)}
    assert create_sphere(radius=2.5).vertex_position(sorted(mesh.all_vertex_ids())[0])[1] == 2.5
    with pytest.raises(ValueError):
        create_sphere(segments=2)


def test_cylinder_has_n_gon_caps_and_quad_sides_around_y():
    mesh = create_cylinder()
    sizes = Counter(len(mesh.face_vertices(f)) for f in mesh.all_face_ids())
    assert sizes == {4: CYLINDER_VERTICES, CYLINDER_VERTICES: 2}
    ys = {round(mesh.vertex_position(v)[1], 9) for v in mesh.all_vertex_ids()}
    assert ys == {-1.0, 1.0}
    for vid in mesh.all_vertex_ids():
        x, _, z = mesh.vertex_position(vid)
        assert math.hypot(x, z) == pytest.approx(1.0)
    caps = [f for f in mesh.all_face_ids() if len(mesh.face_vertices(f)) == CYLINDER_VERTICES]
    assert sorted(_face_normal(mesh, f)[1] > 0 for f in caps) == [False, True]
    with pytest.raises(ValueError):
        create_cylinder(vertices=2)


@pytest.mark.parametrize("name", list(_EXPECTED))
def test_primitives_triangulate_soundly(name):
    """The render adapter triangulates polygons (n-gon caps, pole fans): the Core's own check."""
    assert_face_triangulations_sound(PRIMITIVES[name](), context=name)


def test_every_primitive_is_a_fresh_independent_mesh():
    a, b = create_sphere(), create_sphere()
    assert a is not b
    vid = sorted(a.all_vertex_ids())[0]
    a.set_vertex_position(vid, (9.0, 9.0, 9.0))
    assert b.vertex_position(vid) != (9.0, 9.0, 9.0)
    assert scene_factory.PRIMITIVES["cube"]().vertex_position(vid) == (-1.0, -1.0, -1.0)
