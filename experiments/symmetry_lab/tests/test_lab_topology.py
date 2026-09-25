"""Topologische Paarung und Seiten (Handoff Slice 5 §2 E11/E12, §7 Charakterisierung).

Ebene X, Seam aus Slice 3 E3. Die Zahlen sind Charakterisierung der heutigen
Assets aus der Untersuchung zum Handoff, keine Capability-Regel.
"""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.symmetry import CorrespondenceState, vertex_correspondence

from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_symmetry import definition_for_axis
from symmetry_lab.lab_topology import topological_pairing, topological_sides, topology_report

ASSETS = [
    # asset, Vertices, capability-PAIRED, Faces je Seite
    ("subd_cube", 26, 18, 12),
    ("head_basemesh", 326, 290, 162),
    ("man_with_shoes_basemesh", 928, 830, 463),
]


def mesh_with_axis(asset: str, axis: str = "X"):
    app = Application()
    load_asset_into(app, asset)
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition_for_axis(mesh, axis)
    return mesh


# -- Charakterisierung (§7) --------------------------------------------------------


@pytest.mark.parametrize("asset,vertices,_paired,_faces", ASSETS)
def test_all_vertices_paired_without_conflicts(asset, vertices, _paired, _faces):
    mesh = mesh_with_axis(asset)
    pairing = topological_pairing(mesh)
    assert len(mesh.all_vertex_ids()) == vertices
    assert len(pairing.partners) == vertices
    assert pairing.conflicts == frozenset()
    assert pairing.face_pair_conflicts == 0


@pytest.mark.parametrize("asset,_vertices,paired,_faces", ASSETS)
def test_agrees_with_capability_where_capability_pairs(asset, _vertices, paired, _faces):
    mesh = mesh_with_axis(asset)
    partners = topological_pairing(mesh).partners
    capability = {
        v: c.partner
        for v, c in vertex_correspondence(mesh).items()
        if c.state is CorrespondenceState.PAIRED
    }
    assert len(capability) == paired
    assert all(partners[v] == p for v, p in capability.items())


def test_the_54_unpaired_of_man_with_shoes_have_a_topological_partner():
    mesh = mesh_with_axis("man_with_shoes_basemesh")
    unpaired = [
        v for v, c in vertex_correspondence(mesh).items()
        if c.state is CorrespondenceState.UNPAIRED
    ]
    partners = topological_pairing(mesh).partners
    assert len(unpaired) == 54
    assert all(v in partners and partners[v] != v for v in unpaired)


@pytest.mark.parametrize("asset,_vertices,_paired,faces", ASSETS)
def test_seam_splits_into_exactly_two_equal_sides(asset, _vertices, _paired, faces):
    sides = topological_sides(mesh_with_axis(asset))
    assert sides.component_count == 2
    assert sides.faces_per_side() == [faces, faces]
    assert sides.mixed == frozenset()


def test_pairing_is_position_independent():
    mesh = mesh_with_axis("head_basemesh")
    before = topological_pairing(mesh)
    capability = vertex_correspondence(mesh)
    moved = sorted(
        (v for v, c in capability.items() if c.state is CorrespondenceState.PAIRED), key=int
    )[:10]
    for k, vid in enumerate(moved):
        x, y, z = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (-x + 0.1 * k, y + 0.3, z - 0.2))
    after = topological_pairing(mesh)
    assert after == before
    assert topological_sides(mesh) == topological_sides(mesh_with_axis("head_basemesh"))


# -- Struktur ----------------------------------------------------------------------


@pytest.mark.parametrize("asset", [a[0] for a in ASSETS])
def test_partners_are_an_involution_across_sides(asset):
    mesh = mesh_with_axis(asset)
    report = topology_report(mesh)
    partners, sides = report.pairing.partners, report.sides
    for v, p in partners.items():
        assert partners[p] == v
        if v in sides.seam_vertices:
            assert p == v  # E11 Schritt 1
        else:
            assert sides.vertex_side[v] != sides.vertex_side[p]


def test_seam_vertices_have_no_side():
    report = topology_report(mesh_with_axis("subd_cube"))
    sides = report.sides
    assert len(sides.seam_vertices) == 8
    assert not (sides.seam_vertices & sides.vertex_side.keys())
    assert len(sides.vertex_side) == 26 - 8


def test_symmetry_off_is_empty():
    app = Application()
    load_asset_into(app, "subd_cube")
    pairing = topological_pairing(app.scene.mesh)
    assert pairing.partners == {}
    assert pairing.conflicts == frozenset()
    assert topological_sides(app.scene.mesh).component_count == 1


def test_axis_without_seam_is_one_component():
    # subd_cube auf Y: 0 Seam-Edges (Slice 3) → nichts trennt die Faces.
    sides = topological_sides(mesh_with_axis("subd_cube", "Y"))
    assert sides.component_count == 1
    assert sides.faces_per_side() == [24]


# -- Künstliche Konflikte ------------------------------------------------------------


def _edge_on_negative_side(mesh):
    seam = mesh.symmetry_definition.seam_edges
    return next(
        e for e in mesh.all_edge_ids()
        if e not in seam and all(mesh.vertex_position(v)[0] < 0 for v in mesh.edge_vertices(e))
    )


def test_split_edge_on_one_side_gives_face_conflict_and_unpaired_vertex():
    mesh = mesh_with_axis("subd_cube")
    new_vertex, _, _ = mesh.split_edge(_edge_on_negative_side(mesh))
    report = topology_report(mesh)
    assert report.pairing.face_pair_conflicts == 2  # die beiden Faces an der Edge
    assert new_vertex not in report.pairing.partners
    assert report.pairing.conflicts == frozenset()
    # alle anderen Vertices bleiben über andere Face-Paare gepaart
    assert len(report.pairing.partners) == 26
    assert report.sides.component_count == 2


def test_collapse_on_one_side_gives_vertex_conflict_not_paired():
    mesh = mesh_with_axis("subd_cube")
    merged = mesh.collapse_edge(_edge_on_negative_side(mesh))
    pairing = topological_pairing(mesh)
    assert pairing.conflicts == frozenset({merged})
    assert merged not in pairing.partners
    # INV-5: die zwei Vertices, die den Konflikt-Vertex als Partner hätten,
    # gelten ebenfalls als nicht gepaart (keine zwei auf dieselbe Position).
    assert merged not in pairing.partners.values()
    assert all(pairing.partners[p] == v for v, p in pairing.partners.items())
