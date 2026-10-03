"""Symmetrisches Rotate/Scale — WP-SYM-LAB-02 S2 (AD-SYM-02 §2.4).

Operation-Ebene: `RotateOperation`/`ScaleOperation` gegen `params["symmetry"]`; Tool-Ebene:
`RotateTool`/`ScaleTool` lösen den Symmetriekontext selbst auf (Pivot pro Seite = Zentroid der
eigenen Auswahl, Artist-Verdikt 2026-10-03; Rückfall auf Auswahl ∪ Partner bei einem Seam-Vertex;
Seam-Ablehnung). Gespiegelte Partner werden als konjugierte Absicht transformiert und müssen
exakt (bitgleich bei achsenparallelen Ebenen) die Spiegelung der Quelle bleiben, weil
`mirai.symmetry` Partner per exakter Positionsgleichheit findet.

Ausführen mit: pytest tests/test_symmetric_transform.py
"""

from __future__ import annotations

import math
import random
import unittest

import tests._bootstrap  # noqa: F401 — Produktionspfad src/core, src/mirai

from core.history import HistoryStack
from core.mesh import Mesh, SymmetryDefinition
from core.operation import OperationContext
from core.operations.transform import (
    RotateOperation,
    ScaleOperation,
    SeamConstraintError,
    mirror_point,
    rotate_around_axis,
)
from core.selection import Selection, SelectionMode
from mirai.interaction import commands as cmd
from mirai.interaction.tools.rotate import RotateTool
from mirai.interaction.tools.scale import ScaleTool
from mirai.interaction.tools.selection_helpers import resolve_symmetry
from mirai.symmetry import CorrespondenceState, mirror_position, vertex_correspondence

ORIGIN = (0.0, 0.0, 0.0)
NX = (1.0, 0.0, 0.0)


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def _close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _mesh(pairs=4, seed=1, plane_point=ORIGIN, normal=NX, seam=False):
    """Mesh mit `pairs` exakt gespiegelten Paaren (+ optional einer Seam-Edge auf der Ebene)."""
    rng = random.Random(seed)
    mesh = Mesh()
    ids = []
    for _ in range(pairs):
        p = (-rng.uniform(0.5, 3.0), rng.uniform(-2, 2), rng.uniform(-2, 2))
        a = mesh.add_vertex(p)
        b = mesh.add_vertex(mirror_position(p, plane_point, normal))
        ids.append((a, b))
    seam_ids = ()
    edges = frozenset()
    if seam:
        s0 = mesh.add_vertex((0.0, 0.0, 0.0))
        s1 = mesh.add_vertex((0.0, 1.0, 0.5))
        edges = frozenset({mesh.add_edge(s0, s1)})
        seam_ids = (s0, s1)
    mesh.symmetry_definition = SymmetryDefinition(plane_point, normal, edges)
    return mesh, ids, seam_ids


def _context(mesh, selected, pivot=None):
    affected, symmetry = resolve_symmetry(mesh, set(selected))
    selection = Selection()
    selection.mode = SelectionMode.VERTEX
    selection.set(affected)
    params = {"pivot": pivot}
    if symmetry is not None:
        params["symmetry"] = symmetry
    return OperationContext(target=mesh, selection=selection, history=HistoryStack(), params=params)


def _signed_angle(before, after, pivot, axis):
    k = _unit(axis)

    def perp(p):
        q = tuple(a - b for a, b in zip(p, pivot))
        d = sum(a * b for a, b in zip(q, k))
        return tuple(a - d * b for a, b in zip(q, k))

    u, v = perp(before), perp(after)
    cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return math.atan2(sum(a * b for a, b in zip(cross, k)), sum(a * b for a, b in zip(u, v)))


class _Scene:
    def __init__(self, mesh):
        self.mesh = mesh
        self.history = HistoryStack()
        self.selection = Selection()


class _Camera:
    def basis(self):
        return ((0.0, 0.0, -1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


def _begin_tool(tool_cls, mesh, vertex_ids, **params):
    scene = _Scene(mesh)
    tool = tool_cls()
    tool.activate()
    tool.begin(scene=scene, camera=_Camera(), vertex_ids=set(vertex_ids), **params)
    return tool, scene


# -- Spiegel-Äquivalenz ---------------------------------------------------------


class MirrorEquivalenceTests(unittest.TestCase):
    def _random_steps(self, op_cls, rng):
        if op_cls is RotateOperation:
            return lambda: {
                "axis": _unit((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))),
                "angle": rng.uniform(-1.0, 1.0),
            }
        return lambda: {"factor": tuple(rng.uniform(0.6, 1.6) for _ in range(3))}

    def _check(self, op_cls, pivot, seed):
        mesh, pairs, _ = _mesh(pairs=5, seed=seed)
        sources = {a for a, _ in pairs}
        op = op_cls(_context(mesh, sources, pivot=pivot))
        op.begin()
        rng = random.Random(seed)
        step = self._random_steps(op_cls, rng)
        for _ in range(60):  # viele inkrementelle Schritte: kein Drift
            op.update(**step())
            for a, b in pairs:
                self.assertEqual(
                    mesh.vertex_position(b),
                    mirror_position(mesh.vertex_position(a), ORIGIN, NX),
                )
        corr = vertex_correspondence(mesh)
        for a, b in pairs:  # Paare bleiben für die Correspondence-Ableitung PAIRED
            self.assertEqual(corr[a].state, CorrespondenceState.PAIRED)
            self.assertEqual(corr[a].partner, b)

    def test_rotate_pivot_on_and_off_plane(self):
        for seed, pivot in enumerate([None, (0.0, 0.3, -0.2), (0.7, 0.3, -0.2)]):
            with self.subTest(pivot=pivot):
                self._check(RotateOperation, pivot, seed)

    def test_scale_pivot_on_and_off_plane(self):
        for seed, pivot in enumerate([None, (0.0, 0.3, -0.2), (0.7, 0.3, -0.2)]):
            with self.subTest(pivot=pivot):
                self._check(ScaleOperation, pivot, seed)

    def test_oblique_plane_stays_mirrored_within_tolerance(self):
        normal = _unit((1.0, 0.4, -0.2))
        point = (0.2, 0.1, 0.0)
        mesh = Mesh()
        a = mesh.add_vertex((-1.0, 0.5, 0.3))
        b = mesh.add_vertex(mirror_point((-1.0, 0.5, 0.3), point, normal))
        mesh.symmetry_definition = SymmetryDefinition(point, normal)
        rng = random.Random(7)
        for cls in (RotateOperation, ScaleOperation):
            op = cls(_context(mesh, {a}, pivot=(0.4, 0.2, 0.1)))
            op.begin()
            step = self._random_steps(cls, rng)
            for _ in range(40):
                op.update(**step())
            self.assertTrue(
                _close(mesh.vertex_position(b), mirror_point(mesh.vertex_position(a), point, normal))
            )
            op.cancel()

    def test_partner_matches_documented_formula(self):
        """spiegel(T(spiegel(p))) == Rotation um spiegel(Pivot), spiegel(Achse), -Winkel (§2.4)."""
        mesh, pairs, _ = _mesh(pairs=1, seed=3)
        a, b = pairs[0]
        pivot = (0.4, 0.2, -0.1)
        axis = _unit((0.3, 0.8, -0.5))
        start = mesh.vertex_position(b)
        op = RotateOperation(_context(mesh, {a}, pivot=pivot))
        op.begin()
        op.update(axis=axis, angle=0.7)
        mirrored_axis = (-axis[0], axis[1], axis[2])
        expected = rotate_around_axis(start, mirror_point(pivot, ORIGIN, NX), mirrored_axis, -0.7)
        self.assertTrue(_close(mesh.vertex_position(b), expected))

    def test_scale_partner_matches_documented_formula(self):
        mesh, pairs, _ = _mesh(pairs=1, seed=4)
        a, b = pairs[0]
        pivot = (0.4, 0.2, -0.1)
        start = mesh.vertex_position(b)
        factor = (1.3, 0.8, 1.1)
        op = ScaleOperation(_context(mesh, {a}, pivot=pivot))
        op.begin()
        op.update(factor=factor)
        # Faktor je Basisachse b_i entlang spiegel(b_i): x-Faktor bleibt auf der x-Achse.
        mp = mirror_point(pivot, ORIGIN, NX)
        q = tuple(s - m for s, m in zip(start, mp))
        expected = tuple(m + f * c for m, f, c in zip(mp, factor, q))
        self.assertTrue(_close(mesh.vertex_position(b), expected))


class RotationSenseTests(unittest.TestCase):
    def _senses(self, axis):
        mesh, pairs, _ = _mesh(pairs=1, seed=5)
        a, b = pairs[0]
        pivot = (0.0, 0.1, 0.2)  # auf der Ebene
        before_a, before_b = mesh.vertex_position(a), mesh.vertex_position(b)
        op = RotateOperation(_context(mesh, {a}, pivot=pivot))
        op.begin()
        op.update(axis=axis, angle=0.4)
        return (
            _signed_angle(before_a, mesh.vertex_position(a), pivot, axis),
            _signed_angle(before_b, mesh.vertex_position(b), pivot, axis),
        )

    def test_normal_axis_pair_rotates_identically(self):
        sa, sb = self._senses(NX)
        self.assertAlmostEqual(sa, 0.4)
        self.assertAlmostEqual(sb, 0.4)

    def test_in_plane_axis_pair_rotates_opposite(self):
        sa, sb = self._senses((0.0, 1.0, 0.0))
        self.assertAlmostEqual(sa, 0.4)
        self.assertAlmostEqual(sb, -0.4)


# -- Einzelvertex, Fehlen von Symmetrie, explizites Paar --------------------------


class ToolBehaviourTests(unittest.TestCase):
    def test_single_vertex_turns_about_itself(self):
        """Pivot pro Seite (Artist-Verdikt 2026-10-03, B): der Zentroid eines einzelnen
        Vertex ist der Vertex selbst - Rotate/Scale ändern nichts, der Partner bleibt
        exakt gespiegelt. (Die frühere Paarmitte bleibt als Idee für ein Pivot-System.)"""
        for tool_cls in (RotateTool, ScaleTool):
            mesh, pairs, _ = _mesh(pairs=1, seed=6)
            a, b = pairs[0]
            start_a, start_b = mesh.vertex_position(a), mesh.vertex_position(b)
            tool, _ = _begin_tool(tool_cls, mesh, {a})
            self.assertEqual(tool.vertex_ids, {a, b})
            self.assertEqual(tool.operation.pivot, start_a)
            tool.update(dx=60, dy=0, width=800, height=600)
            self.assertTrue(_close(mesh.vertex_position(a), start_a))
            self.assertEqual(
                mesh.vertex_position(b), mirror_position(mesh.vertex_position(a), ORIGIN, NX)
            )
            self.assertTrue(_close(mesh.vertex_position(b), start_b))
            tool.cancel()

    def test_one_sided_group_turns_about_its_own_centroid(self):
        """Eine einseitige Gruppe (z. B. eine Augenschleife) dreht/skaliert um ihre eigene
        Mitte; die Partner um die gespiegelte Mitte, exakt gespiegelt."""
        for tool_cls in (RotateTool, ScaleTool):
            mesh, pairs, _ = _mesh(pairs=3, seed=12)
            sources = [a for a, _ in pairs[:2]]
            partners = [b for _, b in pairs[:2]]
            centroid = tuple(
                sum(mesh.vertex_position(v)[k] for v in sources) / 2 for k in range(3)
            )
            tool, _ = _begin_tool(tool_cls, mesh, set(sources), space="y")
            self.assertTrue(_close(tool.operation.pivot, centroid))
            self.assertLess(tool.operation.pivot[0], 0.0)  # nicht auf der Ebene
            before = [mesh.vertex_position(v) for v in sources]
            tool.update(dx=60, dy=0, width=800, height=600)
            after = [mesh.vertex_position(v) for v in sources]
            self.assertNotEqual(after, before)
            # Rotation/Skalierung um den Zentroid lässt ihn an Ort und Stelle.
            moved_centroid = tuple(sum(p[k] for p in after) / 2 for k in range(3))
            self.assertTrue(_close(moved_centroid, centroid))
            for a, b in zip(sources, partners):
                self.assertEqual(
                    mesh.vertex_position(b), mirror_position(mesh.vertex_position(a), ORIGIN, NX)
                )
            tool.cancel()

    def test_seam_vertex_in_selection_falls_back_to_pivot_on_plane(self):
        """Mit einem Seam-Vertex läge der eigene Zentroid neben der Ebene und der
        Seam-Constraint würde jede Rotation ablehnen: Rückfall auf Auswahl ∪ Partner."""
        for tool_cls in (RotateTool, ScaleTool):
            mesh, pairs, seam = _mesh(pairs=1, seed=13, seam=True)
            a, b = pairs[0]
            selected = {a, seam[0]}
            affected = {a, b, seam[0]}
            expected = tuple(
                sum(mesh.vertex_position(v)[k] for v in affected) / 3 for k in range(3)
            )
            tool, _ = _begin_tool(tool_cls, mesh, selected, space="x")
            self.assertTrue(_close(tool.operation.pivot, expected))
            self.assertAlmostEqual(tool.operation.pivot[0], 0.0, places=12)
            tool.update(dx=40, dy=0, width=800, height=600)
            self.assertAlmostEqual(mesh.vertex_position(seam[0])[0], 0.0, places=12)
            tool.cancel()

    def test_without_symmetry_single_vertex_unchanged(self):
        mesh = Mesh()
        a = mesh.add_vertex((-1.0, 2.0, 3.0))
        for tool_cls in (RotateTool, ScaleTool):
            tool, _ = _begin_tool(tool_cls, mesh, {a})
            self.assertEqual(tool.vertex_ids, {a})
            self.assertNotIn("symmetry", tool.operation.context.params)
            tool.update(dx=60, dy=0, width=800, height=600)
            self.assertEqual(mesh.vertex_position(a), (-1.0, 2.0, 3.0))
            tool.cancel()

    def test_explicit_pair_selection_is_a_rigid_group(self):
        mesh, pairs, _ = _mesh(pairs=1, seed=8)
        a, b = pairs[0]
        d0 = math.dist(mesh.vertex_position(a), mesh.vertex_position(b))
        tool, _ = _begin_tool(RotateTool, mesh, {a, b}, space="y")
        self.assertEqual(tool.operation.context.params["symmetry"]["mirrored_vertex_ids"], set())
        before_a, before_b = mesh.vertex_position(a), mesh.vertex_position(b)
        tool.update(dx=80, dy=0, width=800, height=600)
        pivot = tool.operation.pivot
        self.assertAlmostEqual(
            math.dist(mesh.vertex_position(a), mesh.vertex_position(b)), d0, places=9
        )
        # beide drehen im selben Sinn um dieselbe Achse (starre Gruppe, Move-Regel)
        sa = _signed_angle(before_a, mesh.vertex_position(a), pivot, (0, 1, 0))
        sb = _signed_angle(before_b, mesh.vertex_position(b), pivot, (0, 1, 0))
        self.assertAlmostEqual(sa, sb)
        self.assertGreater(abs(sa), 0.1)

    def test_given_pivot_is_used_as_is_and_mirrored_by_operation(self):
        mesh, pairs, _ = _mesh(pairs=1, seed=9)
        a, b = pairs[0]
        pivot = (0.5, 0.2, 0.1)
        tool, _ = _begin_tool(ScaleTool, mesh, {a}, pivot=pivot)
        self.assertEqual(tool.operation.pivot, pivot)

    def test_cancel_no_history_commit_one_undo_step_restores_both_sides(self):
        for tool_cls in (RotateTool, ScaleTool):
            mesh, pairs, _ = _mesh(pairs=2, seed=10)
            a, b = pairs[0]
            # Zwei Vertices einer Seite: ein einzelner dreht/skaliert um sich selbst.
            group = {a, pairs[1][0]}
            before = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
            tool, scene = _begin_tool(tool_cls, mesh, group)
            tool.update(dx=70, dy=0, width=800, height=600)
            tool.update(dx=20, dy=0, width=800, height=600)
            tool.cancel()
            self.assertEqual(len(scene.history), 0)
            self.assertEqual({v: mesh.vertex_position(v) for v in before}, before)

            tool.deactivate()
            tool = tool_cls()
            tool.activate()
            tool.begin(scene=scene, camera=_Camera(), vertex_ids=set(group))
            tool.update(dx=70, dy=0, width=800, height=600)
            tool.update(dx=20, dy=0, width=800, height=600)
            tool.commit()
            self.assertEqual(len(scene.history), 1)
            self.assertNotEqual(mesh.vertex_position(b), before[b])
            scene.history.undo()
            self.assertEqual({v: mesh.vertex_position(v) for v in before}, before)


# -- Seam ---------------------------------------------------------------------------


class SeamTests(unittest.TestCase):
    def _on_plane(self, mesh, ids):
        return all(mesh.vertex_position(v)[0] == 0.0 for v in ids)

    def test_rotate_axis_parallel_to_normal_is_allowed_and_exactly_on_plane(self):
        mesh, _, seam = _mesh(pairs=1, seam=True)
        tool, _ = _begin_tool(RotateTool, mesh, set(seam), space="x")
        for _ in range(30):
            tool.update(dx=13, dy=0, width=800, height=600)
        self.assertTrue(self._on_plane(mesh, seam))
        self.assertNotEqual(mesh.vertex_position(seam[1]), (0.0, 1.0, 0.5))

    def test_rotate_other_axes_are_refused_without_side_effects(self):
        for space in ("y", "z", None):
            mesh, _, seam = _mesh(pairs=1, seam=True)
            before = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
            scene = _Scene(mesh)
            tool = RotateTool()
            tool.activate()
            with self.subTest(space=space):
                with self.assertRaises(SeamConstraintError):
                    tool.begin(
                        scene=scene, camera=_Camera(), vertex_ids=set(seam), space=space
                    )
                self.assertIsNone(tool.operation)
                self.assertEqual(len(scene.history), 0)
                self.assertEqual({v: mesh.vertex_position(v) for v in before}, before)

    def test_scale_world_axis_constraints_and_uniform_stay_exactly_on_plane(self):
        for space in (None, "x", "y", "z", "xy", "yz", "xz"):
            mesh, _, seam = _mesh(pairs=1, seam=True)
            with self.subTest(space=space):
                tool, _ = _begin_tool(ScaleTool, mesh, set(seam), space=space)
                for _ in range(30):
                    tool.update(dx=9, dy=3, width=800, height=600)
                self.assertTrue(self._on_plane(mesh, seam))

    def test_seam_with_off_plane_pivot_is_refused(self):
        for tool_cls in (RotateTool, ScaleTool):
            mesh, _, seam = _mesh(pairs=1, seam=True)
            tool = tool_cls()
            tool.activate()
            with self.assertRaises(SeamConstraintError):
                tool.begin(
                    scene=_Scene(mesh),
                    camera=_Camera(),
                    vertex_ids=set(seam),
                    space="x",
                    pivot=(0.5, 0.0, 0.0),
                )

    def test_pivot_within_tolerance_is_snapped_not_drifting(self):
        mesh, _, seam = _mesh(pairs=1, seam=True)
        tool, _ = _begin_tool(RotateTool, mesh, set(seam), space="x", pivot=(1e-12, 0.1, 0.1))
        for _ in range(20):
            tool.update(dx=11, dy=0, width=800, height=600)
        self.assertTrue(self._on_plane(mesh, seam))

    def test_operation_backstop_raises_before_touching_anything(self):
        mesh, _, seam = _mesh(pairs=1, seam=True)
        before = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
        op = RotateOperation(_context(mesh, set(seam), pivot=ORIGIN))
        op.begin()
        with self.assertRaises(SeamConstraintError):
            op.update(axis=(0.0, 1.0, 0.0), angle=0.3)
        self.assertEqual({v: mesh.vertex_position(v) for v in before}, before)
        sop = ScaleOperation(_context(mesh, set(seam), pivot=ORIGIN))
        sop.begin()
        with self.assertRaises(SeamConstraintError):
            sop.update(factor=(1.5, 1.0, 1.0), basis=(_unit((1, 1, 0)), _unit((-1, 1, 0)), (0, 0, 1)))

    def test_mixed_selection_pair_and_seam(self):
        mesh, pairs, seam = _mesh(pairs=2, seam=True)
        a, b = pairs[0]
        tool, _ = _begin_tool(RotateTool, mesh, {a, seam[0]}, space="x")
        for _ in range(25):
            tool.update(dx=10, dy=0, width=800, height=600)
        self.assertTrue(self._on_plane(mesh, seam))
        self.assertEqual(
            mesh.vertex_position(b), mirror_position(mesh.vertex_position(a), ORIGIN, NX)
        )


# -- Production unverändert ---------------------------------------------------------


class ProductionUnchangedTests(unittest.TestCase):
    def test_production_app_has_no_way_to_switch_symmetry_on(self):
        from mirai.application import Application

        app = Application()
        self.assertIsNone(app.scene.mesh.symmetry_definition)
        names = [n for n in dir(cmd) if not n.startswith("_")]
        self.assertFalse([n for n in names if "symmetr" in n.lower()])
        self.assertFalse(
            [m for m in dir(app) if "symmetr" in m.lower() and not m.startswith("__")]
        )

    def test_rotate_scale_without_symmetry_match_plain_math(self):
        mesh = Mesh()
        a = mesh.add_vertex((1.0, 2.0, 3.0))
        b = mesh.add_vertex((-2.0, 0.5, 1.0))
        op = RotateOperation(_context(mesh, {a, b}, pivot=ORIGIN))
        op.begin()
        axis = _unit((0.2, 1.0, 0.1))
        op.update(axis=axis, angle=0.5)
        self.assertEqual(
            mesh.vertex_position(a), rotate_around_axis((1.0, 2.0, 3.0), ORIGIN, axis, 0.5)
        )


if __name__ == "__main__":
    unittest.main()
