"""Gespiegelter Schnitt, headless: Charakterisierung P1–P3 (Handoff Slice 6 §7).

Baseline und Befunde P1–P3 (Ebene X, Seam aus Slice 3 E3) mit Mesh-Primitiven
(`split_edge`, `connect_vertices`) und der topologischen Paarung des Labs. Die
Zahlen sind Charakterisierung der heutigen Assets, keine Capability-Regel.
Positionen werden exakt verglichen (A5).

Seit WP-SYM-LAB-03 Slice 5 ohne die Lab-Knife-Engine (`lab_knife.py`, gelöscht —
Kopie vor B7, Plan §2 #29): ihre Engine-Tests gingen mit ihr (Plan A2-Tabelle). Die
Befunde bleiben als Forschung für einen künftigen symmetrischen One Knife (README,
Historie „Gespiegelter Knife"). `edge_between` ist aus `lab_knife` hierher kopiert.
"""

from __future__ import annotations

import pytest

from core import Scene
from mirai.application import Application
from mirai.symmetry import (
    SymmetryState,
    mirror_position,
    symmetry_state,
    vertex_correspondence,
)

from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_symmetry import definition_for_axis
from symmetry_lab.lab_topology import topological_pairing, topological_sides, topology_report

PLANE = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))


# -- Hilfen --------------------------------------------------------------------------


def make_scene(asset: str, axis: str | None = "X") -> Scene:
    app = Application()
    load_asset_into(app, asset)
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition_for_axis(mesh, axis)
    return app.scene


def edge_between(mesh, a, b):
    """Die Edge zwischen zwei Vertices oder `None` (aus dem gelöschten `lab_knife`)."""
    for eid in mesh.vertex_edges(a):
        if b in mesh.edge_vertices(eid):
            return eid
    return None


def plus_quad(mesh):
    """Niedrigste FaceId unter den Quads mit allen Vertices auf +X (subd_cube 12, head 163)."""
    return min(
        (
            f for f in mesh.all_face_ids()
            if len(mesh.face_vertices(f)) == 4
            and all(mesh.vertex_position(v)[0] > 0 for v in mesh.face_vertices(f))
        ),
        key=int,
    )


def quad_edges(mesh, face):
    """Zwei gegenüberliegende Edges der Quad: (v0, v1) und (v2, v3)."""
    vs = mesh.face_vertices(face)
    return edge_between(mesh, vs[0], vs[1]), edge_between(mesh, vs[2], vs[3])


def counts(mesh):
    report = topology_report(mesh)
    return (
        symmetry_state(mesh),
        len(report.pairing.partners),
        len(mesh.all_vertex_ids()),
        report.sides.faces_per_side(),
    )


def mirror(p):
    return mirror_position(p, *PLANE)


# -- Charakterisierung P1–P3 (§7) --------------------------------------------------


BASELINE = [
    # asset, Vertices, Faces je Seite, Seam-Edges
    ("subd_cube", 26, 12, 8),
    ("head_basemesh", 326, 162, 36),
]


@pytest.mark.parametrize("asset,vertices,faces,_seam", BASELINE)
def test_baseline(asset, vertices, faces, _seam):
    mesh = make_scene(asset).mesh
    assert counts(mesh) == (SymmetryState.VALID, vertices, vertices, [faces, faces])


@pytest.mark.parametrize("asset,vertices,_faces,seam", BASELINE)
def test_p1_raw_seam_split_without_tracking_breaks_seam(asset, vertices, _faces, seam):
    mesh = make_scene(asset).mesh
    definition = mesh.symmetry_definition
    new_vertex, _, _ = mesh.split_edge(min(definition.seam_edges, key=int), 0.37)
    assert mesh.vertex_position(new_vertex)[0] == 0.0
    assert symmetry_state(mesh) is SymmetryState.PARTIAL
    assert sum(mesh.is_valid_edge(e) for e in definition.seam_edges) == seam - 1
    assert topological_sides(mesh).component_count == 1


P2 = [
    # asset, Vertices danach, Face-Paar-Konflikte
    ("subd_cube", 28, 40),
    ("head_basemesh", 328, 644),
]


def one_sided_cut(mesh):
    face = plus_quad(mesh)
    e1, e2 = quad_edges(mesh, face)
    a, _, _ = mesh.split_edge(e1, 0.3)
    b, _, _ = mesh.split_edge(e2, 0.6)
    return mesh.connect_vertices(face, a, b)


@pytest.mark.parametrize("asset,vertices,face_pair_conflicts", P2)
def test_p2_one_sided_cut_collapses_topological_pairing(asset, vertices, face_pair_conflicts):
    mesh = make_scene(asset).mesh
    one_sided_cut(mesh)
    pairing = topological_pairing(mesh)
    assert len(mesh.all_vertex_ids()) == vertices
    assert len(pairing.partners) == 0
    assert len(pairing.conflicts) == vertices
    assert pairing.face_pair_conflicts == face_pair_conflicts


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_p2_observation_halves_are_quads_like_their_uncut_mirror(asset):
    """README-Beobachtung zu P2: beide Hälften der geschnittenen Quad sind wieder
    4-Ecke — also gleich lang wie die ungeschnittene Spiegel-Quad — und selbst
    die Seam-Vertices landen im Konflikt."""
    mesh = make_scene(asset).mesh
    mirror_face_vertices = {
        vertex_correspondence(mesh)[v].partner for v in mesh.face_vertices(plus_quad(mesh))
    }
    seam_vertices = {
        v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)
    }
    _, half_1, half_2 = one_sided_cut(mesh)
    mirror_face = next(
        f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) == mirror_face_vertices
    )
    assert [len(mesh.face_vertices(f)) for f in (half_1, half_2, mirror_face)] == [4, 4, 4]
    assert seam_vertices <= topological_pairing(mesh).conflicts


def test_p2_counter_checks_single_operations():
    # einseitiger split_edge allein → topo 326/327 (Slice-5-README)
    mesh = make_scene("head_basemesh").mesh
    mesh.split_edge(quad_edges(mesh, plus_quad(mesh))[0], 0.3)
    assert (len(topological_pairing(mesh).partners), len(mesh.all_vertex_ids())) == (326, 327)
    # einseitiger connect_vertices allein → Position valid, Topologie asymmetrisch
    mesh = make_scene("head_basemesh").mesh
    face = plus_quad(mesh)
    vs = mesh.face_vertices(face)
    mesh.connect_vertices(face, vs[0], vs[2])
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert topological_pairing(mesh).face_pair_conflicts > 0


def mirrored_cut_via_t(mesh, mirror_t):
    """Gespiegelter Schnitt von Hand; `mirror_t(t)` bestimmt die Platzierung auf der Spiegel-Edge."""
    corr = vertex_correspondence(mesh)
    face = plus_quad(mesh)
    vs = mesh.face_vertices(face)
    mirror_face_vertices = {corr[v].partner for v in vs}
    new = []
    offsets = []
    for (x, y), t in (((vs[0], vs[1]), 0.3), ((vs[2], vs[3]), 0.6)):
        e = edge_between(mesh, x, y)
        me = edge_between(mesh, corr[x].partner, corr[y].partner)
        # Charakterisierung: auf beiden Assets sind die Spiegel-Edges umgekehrt orientiert.
        assert mesh.edge_vertices(me)[0] == corr[mesh.edge_vertices(e)[1]].partner
        n, _, _ = mesh.split_edge(e, t)
        n2, _, _ = mesh.split_edge(me, mirror_t(t))
        new.append((n, n2))
        offsets.append(
            max(abs(a - b) for a, b in zip(mirror(mesh.vertex_position(n)), mesh.vertex_position(n2)))
        )
    mirror_face = next(
        f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) >= mirror_face_vertices
        and len(mesh.face_vertices(f)) == 6
    )
    mesh.connect_vertices(face, new[0][0], new[1][0])
    mesh.connect_vertices(mirror_face, new[0][1], new[1][1])
    return new, offsets


def test_p3_mirror_via_one_minus_t_misses_by_one_ulp_on_subd_cube():
    mesh = make_scene("subd_cube").mesh
    _, offsets = mirrored_cut_via_t(mesh, lambda t: 1.0 - t)
    assert sorted(offsets) == [0.0, 1.1102230246251565e-16]
    assert symmetry_state(mesh) is SymmetryState.PARTIAL
    assert (len(topological_pairing(mesh).partners), len(mesh.all_vertex_ids())) == (30, 30)


def test_p3_mirror_via_one_minus_t_is_exact_on_head():
    mesh = make_scene("head_basemesh").mesh
    _, offsets = mirrored_cut_via_t(mesh, lambda t: 1.0 - t)
    assert offsets == [0.0, 0.0]
    assert counts(mesh) == (SymmetryState.VALID, 330, 330, [163, 163])


def test_p3_prime_mirror_position_is_valid_on_subd_cube():
    mesh = make_scene("subd_cube").mesh
    new, _ = mirrored_cut_via_t(mesh, lambda t: 0.5)
    for n, n2 in new:
        mesh.set_vertex_position(n2, mirror(mesh.vertex_position(n)))
    assert counts(mesh) == (SymmetryState.VALID, 30, 30, [13, 13])
