"""VBO-Daten (Handoff Slice 2 §7) — GL-frei, gegen `subd_cube`.

Slice 4 §7 (E10): Charakterisierung der symmetrischen Anzeige-Triangulierung
und -Normalen — Befund, keine Capability-Regel (nur `lab_draw_data.py`).
"""

from __future__ import annotations

import pytest

from core import SymmetryDefinition
from mirai.application import Application
from mirai.symmetry import CorrespondenceState, mirror_position, vertex_correspondence

from symmetry_lab import lab_draw_data
from symmetry_lab.lab_scene import load_asset_into


@pytest.fixture
def mesh():
    app = Application()
    load_asset_into(app, "subd_cube")
    return app.scene.mesh


def test_subd_cube_topology_is_as_registered(mesh):
    # Registry: 26 V / 24 Quads, geschlossen → Euler V - E + F = 2 → 48 Edges.
    assert len(mesh.all_vertex_ids()) == 26
    assert len(mesh.all_face_ids()) == 24
    assert len(mesh.all_edge_ids()) == 48
    assert all(len(mesh.face_vertices(f)) == 4 for f in mesh.all_face_ids())


def test_face_data_lengths(mesh):
    positions, normals = lab_draw_data.face_data(mesh)
    # 24 Quads → 48 Dreiecke → 144 Vertices à 3 Floats.
    assert len(positions) == 24 * 2 * 3 * 3
    assert len(normals) == len(positions)


def test_edge_and_vertex_data_lengths(mesh):
    assert len(lab_draw_data.edge_data(mesh)) == 48 * 2 * 3
    assert len(lab_draw_data.vertex_data(mesh)) == 26 * 3


def test_highlight_contains_exactly_the_selected_vertex(mesh):
    vid = sorted(mesh.all_vertex_ids())[7]
    data = lab_draw_data.highlight_data(mesh, {vid})
    assert data == list(mesh.vertex_position(vid))


def test_highlight_empty_without_selection(mesh):
    assert lab_draw_data.highlight_data(mesh, set()) == []


# -- E10: symmetrische Anzeige-Triangulierung + Normalen (Charakterisierung) -----


def _mesh_with_x_symmetry(asset: str):
    app = Application()
    load_asset_into(app, asset)
    mesh = app.scene.mesh
    mesh.symmetry_definition = SymmetryDefinition(
        plane_point=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0), seam_edges=frozenset()
    )
    return mesh


def _geometric_mirror_lookup(mesh, plane_normal=(1.0, 0.0, 0.0)):
    """Vertex → gespiegelte Vertex-ID rein über Position (E10-Befund, unabhängig
    von `vertex_correspondence`-Zuständen): Vertices exakt auf der Ebene bilden
    sich auf sich selbst ab, sonst eindeutige Positions-Übereinstimmung."""
    positions = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    by_position: dict[tuple, list] = {}
    for v, p in positions.items():
        by_position.setdefault(p, []).append(v)
    lookup = {}
    for v, p in positions.items():
        mirrored = mirror_position(p, (0.0, 0.0, 0.0), plane_normal)
        if p == mirrored:
            lookup[v] = v
            continue
        candidates = by_position.get(mirrored, [])
        if len(candidates) == 1:
            lookup[v] = candidates[0]
    return lookup


def _mirrored_quad_pairs(mesh, lookup):
    """Jede Quad-Face, deren gespiegelte Vertex-Menge einer anderen Face
    entspricht → (face, gespiegelte Face). Gerichtet (jede der zwei Seiten
    zählt eigenständig), wie im Handoff-Befund ("24 gespiegelte Quad-Paare")."""
    vids_to_face = {frozenset(mesh.face_vertices(f)): f for f in mesh.all_face_ids()}
    pairs = {}
    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        if len(boundary) != 4:
            continue
        try:
            mirrored_boundary = frozenset(lookup[v] for v in boundary)
        except KeyError:
            continue
        mirror_fid = vids_to_face.get(mirrored_boundary)
        if mirror_fid is not None:
            pairs[fid] = mirror_fid
    return pairs


def _count_asymmetric_diagonals(mesh, pairs, lookup, diagonal_of):
    count = 0
    for fid, mirror_fid in pairs.items():
        diagonal = diagonal_of(mesh, fid)
        mirrored_diagonal = frozenset(lookup[v] for v in diagonal)
        if mirrored_diagonal != diagonal_of(mesh, mirror_fid):
            count += 1
    return count


def _fan_diagonal(mesh, face_id):
    v0, _v1, v2, _v3 = mesh.face_vertices(face_id)
    return frozenset((v0, v2))


def _symmetric_diagonal(mesh, face_id):
    a, b = lab_draw_data.triangulate_face_symmetric(mesh, face_id)
    return frozenset(a) & frozenset(b)


@pytest.mark.parametrize(
    "asset,expected_pairs,expected_asymmetric_fan",
    [("subd_cube", 24, 24), ("head_basemesh", 324, 0)],
)
def test_quad_diagonal_characterization(asset, expected_pairs, expected_asymmetric_fan):
    mesh = _mesh_with_x_symmetry(asset)
    lookup = _geometric_mirror_lookup(mesh)
    pairs = _mirrored_quad_pairs(mesh, lookup)
    assert len(pairs) == expected_pairs

    asym_fan = _count_asymmetric_diagonals(mesh, pairs, lookup, _fan_diagonal)
    asym_symmetric = _count_asymmetric_diagonals(mesh, pairs, lookup, _symmetric_diagonal)
    assert asym_fan == expected_asymmetric_fan
    assert asym_symmetric == 0


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_vertex_normals_mirror_for_paired_vertices(asset):
    mesh = _mesh_with_x_symmetry(asset)
    corr = vertex_correspondence(mesh)
    normals = lab_draw_data.vertex_normals(mesh)
    checked = 0
    for vid, c in corr.items():
        if c.state is not CorrespondenceState.PAIRED:
            continue
        checked += 1
        mirrored = mirror_position(normals[vid], (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        partner_normal = normals[c.partner]
        assert all(abs(a - b) < 1e-9 for a, b in zip(mirrored, partner_normal))
    assert checked > 0  # sonst wäre der Test wirkungslos
