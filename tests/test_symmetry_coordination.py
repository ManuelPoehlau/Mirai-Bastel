"""AD-SYM-03 Slice 1: shared coordination services (not wired into Application yet).

Run with: pytest tests/test_symmetry_coordination.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import tests._bootstrap  # noqa: F401 — production path src/core, src/mirai

_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from core import SelectionMode
from core.mesh import Mesh, SymmetryDefinition
from mirai.scene_factory import build_core_scene_from_obj
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.topology.connect_vertices_per_face import connect_vertices_per_face
from mirai.topology.delete_dissolve import remove_selected
from mirai.symmetry_coordination import (
    SymmetryIndex,
    both_sides_faces,
    canonical_edges,
    canonical_faces,
    canonical_vertices,
    completeness_report,
    delta_check,
    expand_edges,
    expand_faces,
    expand_vertices,
    is_exact_plane,
    seam_after_split,
)

ORIGIN = (0.0, 0.0, 0.0)
X = (1.0, 0.0, 0.0)


def grid(skip_vertex: tuple[int, int] | None = None):
    """Quads on x in [-2, 2], y in [0, 2]; plane x=0 with the x=0 edges as seam."""
    mesh, p = Mesh(), {}
    for r in range(3):
        for c in range(-2, 3):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    faces = {}
    for r in range(2):
        for c in range(-2, 2):
            faces[(r, c)] = mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    seam = frozenset(e for e in mesh.all_edge_ids() if all(mesh.vertex_position(v)[0] == 0.0 for v in mesh.edge_vertices(e)))
    mesh.symmetry_definition = SymmetryDefinition(ORIGIN, X, seam)
    return mesh, p, faces


class TestExactPlane(unittest.TestCase):
    def test_axis_planes_through_origin_are_exact(self) -> None:
        for normal in ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)):
            self.assertTrue(is_exact_plane(SymmetryDefinition(ORIGIN, normal)))

    def test_off_origin_and_oblique_are_not(self) -> None:
        self.assertFalse(is_exact_plane(SymmetryDefinition((0.3, 0.0, 0.0), X)))
        self.assertFalse(is_exact_plane(SymmetryDefinition(ORIGIN, (0.6, 0.8, 0.0))))

    def test_off_axis_point_coordinate_is_fine(self) -> None:
        self.assertTrue(is_exact_plane(SymmetryDefinition((0.0, 5.0, -2.0), X)))


class TestPartners(unittest.TestCase):
    def test_vertex_edge_face_partners(self) -> None:
        mesh, p, faces = grid()
        index = SymmetryIndex(mesh)
        self.assertEqual(index.vertex_partner(p[(0, -1)]), p[(0, 1)])
        self.assertEqual(index.vertex_partner(p[(1, 0)]), p[(1, 0)])  # seam: own partner
        left = next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {p[(0, -2)], p[(0, -1)]})
        right = next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {p[(0, 2)], p[(0, 1)]})
        self.assertEqual(index.edge_partner(left), right)
        self.assertEqual(index.face_partner(faces[(0, -2)]), faces[(0, 1)])
        self.assertEqual(index.face_partner(faces[(0, -1)]), faces[(0, 0)])

    def test_seam_edge_is_its_own_partner(self) -> None:
        mesh, _p, _f = grid()
        index = SymmetryIndex(mesh)
        for edge in mesh.symmetry_definition.seam_edges:
            self.assertEqual(index.edge_partner(edge), edge)

    def test_no_partner_when_unpaired(self) -> None:
        mesh, p, faces = grid()
        mesh.set_vertex_position(p[(0, 2)], (2.5, 0.0, 0.0))
        index = SymmetryIndex(mesh)
        self.assertIsNone(index.vertex_partner(p[(0, -2)]))
        self.assertIsNone(index.face_partner(faces[(0, -2)]))


class TestSelection(unittest.TestCase):
    def test_expansion_counts_seam_once_and_explicit_wins(self) -> None:
        mesh, p, _f = grid()
        index = SymmetryIndex(mesh)
        seam_edge = next(iter(mesh.symmetry_definition.seam_edges))
        side = next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {p[(0, 1)], p[(0, 2)]})
        exp = expand_edges(index, {seam_edge, side})
        self.assertEqual(len(exp.union), 3)
        self.assertEqual(exp.unpaired, frozenset())
        both = expand_edges(index, {side, index.edge_partner(side)})
        self.assertEqual(both.partners, frozenset())

    def test_unpaired_is_reported(self) -> None:
        mesh, p, _f = grid()
        mesh.set_vertex_position(p[(0, 2)], (2.5, 0.0, 0.0))
        exp = expand_vertices(SymmetryIndex(mesh), {p[(0, -2)], p[(0, -1)]})
        self.assertEqual(exp.unpaired, frozenset({p[(0, -2)]}))
        self.assertEqual(exp.partners, frozenset({p[(0, 1)]}))

    def test_canonicalisation_keeps_one_side(self) -> None:
        mesh, p, faces = grid()
        index = SymmetryIndex(mesh)
        self.assertEqual(canonical_vertices(index, {p[(0, -1)], p[(0, 1)], p[(1, 0)]}), {p[(0, 1)], p[(1, 0)]})
        a = next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {p[(0, 1)], p[(0, 2)]})
        self.assertEqual(canonical_edges(index, {a, index.edge_partner(a)}), {a})
        self.assertEqual(canonical_faces(index, {faces[(0, -2)], faces[(0, 1)]}), {faces[(0, 1)]})

    def test_canonicalisation_keeps_unpaired_and_self_partnered(self) -> None:
        mesh, p, _f = grid()
        mesh.set_vertex_position(p[(0, 2)], (2.5, 0.0, 0.0))
        index = SymmetryIndex(mesh)
        self.assertEqual(canonical_vertices(index, {p[(0, -2)], p[(0, 1)]}), {p[(0, -2)], p[(0, 1)]})


class TestBothSides(unittest.TestCase):
    def test_none_for_intact_seam(self) -> None:
        mesh, p, _f = grid()
        index = SymmetryIndex(mesh)
        side = next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {p[(0, 1)], p[(0, 2)]})
        self.assertEqual(both_sides_faces(index, expand_edges(index, {side}), mode="edge"), frozenset())

    def test_plane_spanning_face_is_flagged(self) -> None:
        mesh, p, faces = grid()
        mesh.remove_face(faces[(0, -1)])
        mesh.remove_face(faces[(0, 0)])
        v = [p[(0, -1)], p[(0, 1)], p[(1, 1)], p[(1, -1)]]
        spanning = mesh.add_face(v)
        mesh.symmetry_definition = SymmetryDefinition(ORIGIN, X, frozenset(
            e for e in mesh.symmetry_definition.seam_edges if mesh.is_valid_edge(e)))
        index = SymmetryIndex(mesh)
        self.assertEqual(index.face_partner(spanning), spanning)
        edge = mesh.face_edges(spanning)[0]
        exp = expand_edges(index, {edge})
        self.assertIn(spanning, both_sides_faces(index, exp, mode="edge"))

    def test_selection_and_image_sharing_a_face(self) -> None:
        mesh, p, faces = grid()
        index = SymmetryIndex(mesh)
        # vertices of the two quads at the seam: p(0,1) selected, its image p(0,-1) shares no face
        exp = expand_vertices(index, {p[(0, 1)]})
        self.assertEqual(both_sides_faces(index, exp, mode="vertex"), frozenset())
        # the seam vertex p(1,0) and p(0,1)'s image p(0,-1) meet in the quad faces[(0,-1)]: a seam
        # vertex is its own image, so union call and "intent + mirrored intent" agree (3b, probe F)
        exp = expand_vertices(index, {p[(0, 1)], p[(1, 0)]})
        self.assertEqual(both_sides_faces(index, exp, mode="vertex"), frozenset())
        # p(1,-1) is selected on the other side: it meets p(0,1)'s image p(0,-1) in faces[(0,-1)],
        # and p(0,1) meets p(1,-1)'s image p(1,1) in faces[(0,0)]
        exp = expand_vertices(index, {p[(0, 1)], p[(1, -1)]})
        flagged = both_sides_faces(index, exp, mode="vertex")
        self.assertLessEqual({faces[(0, -1)], faces[(0, 0)]}, flagged)

    def test_seam_edge_with_opposite_edge_is_not_a_conflict(self) -> None:
        mesh, p, faces = grid()
        index = SymmetryIndex(mesh)
        seam_edge = next(e for e in mesh.symmetry_definition.seam_edges if set(mesh.edge_vertices(e)) == {p[(0, 0)], p[(1, 0)]})
        opposite = next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {p[(0, 1)], p[(1, 1)]})
        exp = expand_edges(index, {seam_edge, opposite})
        self.assertEqual(len(exp.union), 3)
        self.assertEqual(both_sides_faces(index, exp, mode="edge"), frozenset())

    def test_bad_mode(self) -> None:
        mesh, _p, _f = grid()
        index = SymmetryIndex(mesh)
        with self.assertRaises(ValueError):
            both_sides_faces(index, expand_vertices(index, set()), mode="face")


class TestSeamRule(unittest.TestCase):
    def test_split_seam_edge_becomes_halves(self) -> None:
        mesh, _p, _f = grid()
        seam_edge = sorted(mesh.symmetry_definition.seam_edges)[0]
        before = mesh.symmetry_definition
        _v, h1, h2 = mesh.split_edge(seam_edge)
        after = seam_after_split(before, {seam_edge: (h1, h2)})
        self.assertNotIn(seam_edge, after.seam_edges)
        self.assertTrue({h1, h2} <= after.seam_edges)
        self.assertEqual(len(after.seam_edges), len(before.seam_edges) + 1)
        self.assertEqual(after.plane_normal, before.plane_normal)

    def test_non_seam_edge_ignored(self) -> None:
        mesh, _p, _f = grid()
        d = mesh.symmetry_definition
        other = next(e for e in mesh.all_edge_ids() if e not in d.seam_edges)
        _v, h1, h2 = mesh.split_edge(other)
        self.assertEqual(seam_after_split(d, {other: (h1, h2)}).seam_edges, d.seam_edges)


class TestReportAndDelta(unittest.TestCase):
    def test_clean_mesh_is_complete(self) -> None:
        mesh, _p, _f = grid()
        r = completeness_report(mesh)
        self.assertFalse(r.unpaired_vertices | r.edges_without_partner | r.faces_without_partner)
        self.assertFalse(r.self_mirrored_faces | r.dead_seam_ids)

    def test_requires_definition(self) -> None:
        with self.assertRaises(ValueError):
            completeness_report(Mesh())

    def test_one_sided_delete_is_a_violation(self) -> None:
        mesh, _p, faces = grid()
        before = completeness_report(mesh)
        mesh.remove_face(faces[(0, 1)])
        result = delta_check(before, completeness_report(mesh))
        self.assertFalse(result.ok)

    def test_symmetric_delete_is_fine(self) -> None:
        mesh, _p, faces = grid()
        before = completeness_report(mesh)
        mesh.remove_face(faces[(0, 1)])
        mesh.remove_face(faces[(0, -2)])
        self.assertTrue(delta_check(before, completeness_report(mesh)).ok)

    def test_existing_asymmetry_is_not_a_violation_but_new_unpaired_is(self) -> None:
        mesh, p, _f = grid()
        mesh.set_vertex_position(p[(0, 2)], (2.5, 0.0, 0.0))
        before = completeness_report(mesh)
        self.assertTrue(delta_check(before, completeness_report(mesh)).ok)
        mesh.add_vertex((1.5, 5.0, 0.0))
        result = delta_check(before, completeness_report(mesh))
        self.assertFalse(result.ok)
        self.assertTrue(any("created vertex" in v for v in result.violations))

    def test_symmetric_creation_is_fine(self) -> None:
        mesh, _p, _f = grid()
        before = completeness_report(mesh)
        mesh.add_vertex((1.5, 5.0, 0.0))
        mesh.add_vertex((-1.5, 5.0, 0.0))
        self.assertTrue(delta_check(before, completeness_report(mesh)).ok)

    def test_consumed_seam_is_a_violation(self) -> None:
        mesh, _p, faces = grid()
        before = completeness_report(mesh)
        mesh.delete_faces([faces[(0, -1)], faces[(0, 0)]])
        after = completeness_report(mesh)
        self.assertTrue(after.dead_seam_ids)
        self.assertTrue(any("seam" in v for v in delta_check(before, after).violations))


ASSETS = {"subd_cube": "SubD_Cube.obj", "head_basemesh": "head_basemesh.obj"}


def asset_scene(name: str):
    scene = build_core_scene_from_obj(_EXAMPLES / "meshes" / ASSETS[name])
    mesh = scene.mesh
    seam = frozenset(
        e for e in mesh.all_edge_ids() if all(mesh.vertex_position(v)[0] == 0.0 for v in mesh.edge_vertices(e))
    )
    mesh.symmetry_definition = SymmetryDefinition(ORIGIN, X, seam)
    return scene


def plus_x_face(mesh, *, touching_seam: bool):
    seam_vertices = {v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)}
    for f in mesh.all_face_ids():
        vs = mesh.face_vertices(f)
        if min(mesh.vertex_position(v)[0] for v in vs) < 0 or all(mesh.vertex_position(v)[0] == 0 for v in vs):
            continue
        if bool(seam_vertices & set(vs)) == touching_seam:
            return f
    raise LookupError("no suitable +X face")


class TestOnAssets(unittest.TestCase):
    def each(self):
        for name in ASSETS:
            with self.subTest(asset=name):
                yield asset_scene(name)

    def test_clean_assets_are_complete(self) -> None:
        for scene in self.each():
            r = completeness_report(scene.mesh)
            self.assertEqual(symmetry_state(scene.mesh), SymmetryState.VALID)
            self.assertFalse(r.faces_without_partner | r.edges_without_partner | r.self_mirrored_faces | r.dead_seam_ids)

    def test_seam_edge_counted_once_in_expansion(self) -> None:
        for scene in self.each():
            mesh = scene.mesh
            index = SymmetryIndex(mesh)
            seam = sorted(mesh.symmetry_definition.seam_edges)[:2]
            exp = expand_edges(index, set(seam))
            self.assertEqual(exp.union, frozenset(seam))
            self.assertEqual(exp.partners, frozenset())

    def test_one_sided_delete_is_seen_where_symmetry_state_is_not(self) -> None:
        for scene in self.each():
            mesh = scene.mesh
            before = completeness_report(mesh)
            index = SymmetryIndex(mesh)
            f = plus_x_face(mesh, touching_seam=False)
            remove_selected(scene, SelectionMode.FACE, {f}, dissolve=False, cleanup=True)
            after = completeness_report(mesh)
            self.assertEqual(symmetry_state(mesh), SymmetryState.VALID)  # blind to it (Disc. §1.7)
            self.assertTrue(after.faces_without_partner)
            self.assertFalse(delta_check(before, after).ok)
            # the symmetric delete (face + partner) passes
            scene.history.undo()
            partner = index.face_partner(f)
            remove_selected(scene, SelectionMode.FACE, {f, partner}, dissolve=False, cleanup=True)
            self.assertTrue(delta_check(before, completeness_report(mesh)).ok)

    def test_one_sided_vertex_connect_is_detected(self) -> None:
        for scene in self.each():
            mesh = scene.mesh
            before = completeness_report(mesh)
            f = plus_x_face(mesh, touching_seam=False)
            a, _b, c, _d = mesh.face_vertices(f)[:4]
            created = connect_vertices_per_face(scene, {a, c})
            self.assertTrue(created)
            after = completeness_report(mesh)
            self.assertTrue(after.faces_without_partner)
            self.assertFalse(delta_check(before, after).ok)

    def test_dissolved_seam_edge_makes_a_self_mirrored_face(self) -> None:
        for scene in self.each():
            mesh = scene.mesh
            before = completeness_report(mesh)
            seam_edge = next(e for e in sorted(mesh.symmetry_definition.seam_edges) if len(mesh.edge_faces(e)) == 2)
            remove_selected(scene, SelectionMode.EDGE, {seam_edge}, dissolve=True, cleanup=True)
            after = completeness_report(mesh)
            self.assertTrue(after.self_mirrored_faces)
            self.assertTrue(after.dead_seam_ids)
            self.assertFalse(delta_check(before, after).ok)

    def test_deleted_seam_face_pair_leaves_dead_seam_id(self) -> None:
        for scene in self.each():
            mesh = scene.mesh
            before = completeness_report(mesh)
            index = SymmetryIndex(mesh)
            f = plus_x_face(mesh, touching_seam=True)
            remove_selected(scene, SelectionMode.FACE, {f, index.face_partner(f)}, dissolve=False, cleanup=True)
            after = completeness_report(mesh)
            self.assertTrue(after.dead_seam_ids)  # DD-1 removes the face-less seam edge
            self.assertFalse(delta_check(before, after).ok)

    def test_s1_after_real_seam_split(self) -> None:
        for scene in self.each():
            mesh = scene.mesh
            seam_edge = sorted(mesh.symmetry_definition.seam_edges)[0]
            _v, h1, h2 = mesh.split_edge(seam_edge)
            mesh.symmetry_definition = seam_after_split(mesh.symmetry_definition, {seam_edge: (h1, h2)})
            r = completeness_report(mesh)
            self.assertFalse(r.dead_seam_ids)
            self.assertEqual(symmetry_state(mesh), SymmetryState.VALID)


if __name__ == "__main__":
    unittest.main()
