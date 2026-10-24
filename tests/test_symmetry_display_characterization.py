"""Display under symmetry, characterised on Production (GL-free; finding, not a capability rule).

Ported 2026-10-24 from the Symmetry Lab (`experiments/symmetry_lab/tests/test_display_characterization.py`,
removed with the Lab; last state in commit `61ebe77`):

- `subd_cube` topology as registered;
- the E10 finding on the quad diagonal against the triangulation the app draws and picks with
  (`viewport.derived.triangulate_mesh_face`): `subd_cube` shades asymmetrically under X, `head_basemesh` does not
  (basis of the Symmetry Lab's Q1 = (a));
- mirrored vertex normals for paired vertices (`viewport.derived.DerivedGeometry`, Newell face normal).
"""

from __future__ import annotations

import sys

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

_EXAMPLES = _REPO_ROOT / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from core import SymmetryDefinition  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.symmetry import CorrespondenceState, mirror_position, vertex_correspondence  # noqa: E402
from viewport.derived import DerivedGeometry, triangulate_mesh_face  # noqa: E402


def load_asset_into(app: Application, name: str) -> None:
    app.init_scene("obj", obj_path=asset_path(name))


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


# -- E10-Befund an Production (Q1) ------------------------------------------------


def _mesh_with_x_symmetry(asset: str):
    app = Application()
    load_asset_into(app, asset)
    mesh = app.scene.mesh
    mesh.symmetry_definition = SymmetryDefinition(
        plane_point=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0), seam_edges=frozenset()
    )
    return mesh


def _geometric_mirror_lookup(mesh, plane_normal=(1.0, 0.0, 0.0)):
    """Vertex → gespiegelte Vertex-ID rein über Position (unabhängig von
    `vertex_correspondence`-Zuständen): Vertices exakt auf der Ebene bilden sich
    auf sich selbst ab, sonst eindeutige Positions-Übereinstimmung."""
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
    zählt eigenständig), wie im Handoff-Befund („24 gespiegelte Quad-Paare")."""
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


def _production_diagonal(mesh, face_id):
    a, b = triangulate_mesh_face(mesh, face_id)
    return frozenset(a) & frozenset(b)


@pytest.mark.parametrize(
    "asset,expected_pairs,expected_asymmetric",
    [("subd_cube", 24, 24), ("head_basemesh", 324, 0)],
)
def test_production_quad_diagonal_characterization(asset, expected_pairs, expected_asymmetric):
    mesh = _mesh_with_x_symmetry(asset)
    lookup = _geometric_mirror_lookup(mesh)
    pairs = _mirrored_quad_pairs(mesh, lookup)
    assert len(pairs) == expected_pairs
    asymmetric = sum(
        frozenset(lookup[v] for v in _production_diagonal(mesh, fid))
        != _production_diagonal(mesh, mirror_fid)
        for fid, mirror_fid in pairs.items()
    )
    assert asymmetric == expected_asymmetric


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_production_vertex_normals_mirror_for_paired_vertices(asset):
    mesh = _mesh_with_x_symmetry(asset)
    corr = vertex_correspondence(mesh)
    normals = DerivedGeometry(mesh).vertex_normals
    checked = 0
    for vid, c in corr.items():
        if c.state is not CorrespondenceState.PAIRED:
            continue
        checked += 1
        mirrored = mirror_position(normals[vid], (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        partner_normal = normals[c.partner]
        assert all(abs(a - b) < 1e-9 for a, b in zip(mirrored, partner_normal))
    assert checked > 0  # sonst wäre der Test wirkungslos
