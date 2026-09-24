"""Symmetry V1 — Slice 1: Definition → Seam → Correspondence → State.

Bezug: docs/architecture/AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md,
docs/architecture/AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md,
docs/architecture/SLICE1_CLAUDE_CODE_HANDOFF.md §5.

Kein Feature-Test im Sinne einer Operation - dieser Slice hat keine
Operation, kein Tool, kein Undo/Redo für die Definition selbst (Handoff
§4). Getestet werden: Definition-Speicherung + Roundtrip (AD-SYM-01),
der Regressionsfall aus AD-SYM-01 §1.1 (Seam wird durch eine Topologie-
Mutation ungültig, Undo muss Mesh UND Definition exakt wiederherstellen),
sowie Correspondence-Ableitung und State-Aggregation (mirai.symmetry).

Ausführen mit: pytest tests/test_symmetry.py
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401 — Produktionspfad src/core, src/mirai

from core.mesh import Mesh, SymmetryDefinition
from core.operations.topology import MeshStateCommand
from core.scene import Scene
from mirai.symmetry import (
    CorrespondenceState,
    SymmetryState,
    mirror_position,
    symmetry_state,
    vertex_correspondence,
)

# Gemeinsame Plane für alle Tests: x=0, Normale +X (Einheitsvektor).
PLANE_POINT = (0.0, 0.0, 0.0)
PLANE_NORMAL = (1.0, 0.0, 0.0)


def build_symmetry_test_mesh() -> tuple[Mesh, SymmetryDefinition, dict[str, object]]:
    """Ein kleines Mesh, das alle vier Correspondence-Zustände gleichzeitig
    erzeugt (Handoff §5: "kleines Testmesh reicht, kein Torso nötig").

    - seam0/seam1: Endpunkte der deklarierten Seam-Edge, beide exakt auf
      der Plane -> SEAM.
    - left/right: exaktes Spiegelpaar abseits der Plane -> PAIRED.
    - unpaired: kein Vertex an der gespiegelten Position -> UNPAIRED.
    - amb_source: zwei Vertices (amb_a, amb_b) liegen koinzident an der
      gespiegelten Position -> AMBIGUOUS für amb_source.
    """
    mesh = Mesh()
    seam0 = mesh.add_vertex((0.0, 0.0, 0.0))
    seam1 = mesh.add_vertex((0.0, 1.0, 0.0))
    seam_edge = mesh.add_edge(seam0, seam1)

    left = mesh.add_vertex((-1.0, 0.0, 0.0))
    right = mesh.add_vertex((1.0, 0.0, 0.0))

    unpaired = mesh.add_vertex((-2.0, 5.0, 0.0))

    amb_source = mesh.add_vertex((-3.0, 0.0, 0.0))
    amb_a = mesh.add_vertex((3.0, 0.0, 0.0))
    amb_b = mesh.add_vertex((3.0, 0.0, 0.0))

    definition = SymmetryDefinition(
        plane_point=PLANE_POINT,
        plane_normal=PLANE_NORMAL,
        seam_edges=frozenset({seam_edge}),
    )
    mesh.symmetry_definition = definition

    ids = {
        "seam0": seam0, "seam1": seam1, "seam_edge": seam_edge,
        "left": left, "right": right,
        "unpaired": unpaired,
        "amb_source": amb_source, "amb_a": amb_a, "amb_b": amb_b,
    }
    return mesh, definition, ids


class TestSymmetryDefinitionStorage(unittest.TestCase):
    """AD-SYM-01: Definition lebt im Mesh, Teil von export_state()/load_state()."""

    def test_default_definition_is_none(self) -> None:
        self.assertIsNone(Mesh().symmetry_definition)

    def test_export_state_has_symmetry_none_by_default(self) -> None:
        mesh = Mesh()
        mesh.add_vertex((0.0, 0.0, 0.0))
        self.assertIsNone(mesh.export_state()["symmetry"])

    def test_roundtrip_into_same_instance(self) -> None:
        mesh, definition, _ids = build_symmetry_test_mesh()
        state = mesh.export_state()

        mesh.load_state(state)

        self.assertEqual(mesh.symmetry_definition, definition)

    def test_roundtrip_into_new_instance(self) -> None:
        mesh, definition, _ids = build_symmetry_test_mesh()
        state = mesh.export_state()

        restored = Mesh()
        restored.load_state(state)

        self.assertEqual(restored.symmetry_definition, definition)
        self.assertIsNot(restored, mesh)

    def test_none_definition_roundtrips_as_none(self) -> None:
        mesh = Mesh()
        mesh.add_vertex((0.0, 0.0, 0.0))

        restored = Mesh()
        restored.load_state(mesh.export_state())

        self.assertIsNone(restored.symmetry_definition)

    def test_state_without_symmetry_key_loads_as_none(self) -> None:
        """Additiver, optionaler Schlüssel (siehe export_state()-Docstring):
        ein `state`-Dict ohne "symmetry" (z. B. aus einem hypothetischen
        älteren Export) muss weiterhin ladbar sein, nicht mit KeyError
        abbrechen."""
        mesh = Mesh()
        mesh.add_vertex((0.0, 0.0, 0.0))
        state = mesh.export_state()
        del state["symmetry"]

        restored = Mesh()
        restored.load_state(state)

        self.assertIsNone(restored.symmetry_definition)

    def test_definition_does_not_survive_mesh_replacement(self) -> None:
        """AD-SYM-01 §2 Bedingung 3: ersetzt man die Mesh-Instanz einer
        Scene (wie `Application.init_scene()` es tut), darf die Definition
        NICHT auf dem neuen Mesh weiterleben."""
        scene = Scene()
        mesh, _definition, _ids = build_symmetry_test_mesh()
        scene.mesh = mesh
        self.assertIsNotNone(scene.mesh.symmetry_definition)

        scene.mesh = Mesh()

        self.assertIsNone(scene.mesh.symmetry_definition)

    def test_seam_edges_survive_as_frozenset_of_edge_ids(self) -> None:
        mesh, definition, ids = build_symmetry_test_mesh()
        restored = Mesh()
        restored.load_state(mesh.export_state())

        self.assertEqual(restored.symmetry_definition.seam_edges, frozenset({ids["seam_edge"]}))
        self.assertIsInstance(restored.symmetry_definition.seam_edges, frozenset)


class TestSymmetryDefinitionUndoRegression(unittest.TestCase):
    """AD-SYM-01 §1.1: gemessener Regressionsfall.

    split_edge() auf der Seam invalidiert die deklarierte EdgeId. Dieser
    Slice koppelt die Seam nicht aktiv nach (Not-in-scope, Handoff §4) -
    die Definition bleibt also unverändert stehen und wird dadurch
    "erkennbar ungültig" (mesh.is_valid_edge() liefert False für die
    referenzierte ID), statt still falsch zu werden. Undo über
    MeshStateCommand (unverändert, keine neue History-Maschinerie nötig -
    AD-SYM-01 §3/AD-SYM-02 §5) muss Mesh UND Definition exakt auf den
    Vorher-Zustand zurücksetzen.
    """

    def test_split_edge_on_seam_then_undo_restores_definition_and_mesh(self) -> None:
        mesh = Mesh()
        v0 = mesh.add_vertex((0.0, 0.0, 0.0))
        v1 = mesh.add_vertex((0.0, 2.0, 0.0))
        seam_edge = mesh.add_edge(v0, v1)
        definition = SymmetryDefinition(
            plane_point=PLANE_POINT, plane_normal=PLANE_NORMAL, seam_edges=frozenset({seam_edge})
        )
        mesh.symmetry_definition = definition

        before_state = mesh.export_state()

        mesh.split_edge(seam_edge)

        self.assertFalse(mesh.is_valid_edge(seam_edge))
        self.assertEqual(mesh.symmetry_definition, definition, "Mesh führt die Seam nicht nach - Definition bleibt unverändert stehen")
        stale_seam_edge = next(iter(mesh.symmetry_definition.seam_edges))
        self.assertFalse(mesh.is_valid_edge(stale_seam_edge), "die stale Referenz ist über is_valid_edge() erkennbar, nicht still falsch")

        after_state = mesh.export_state()
        command = MeshStateCommand(mesh=mesh, before_state=before_state, after_state=after_state)
        command.undo()

        self.assertTrue(mesh.is_valid_edge(seam_edge))
        self.assertEqual(mesh.symmetry_definition, definition)
        # Nur Vertices/Edges/Faces/Symmetry müssen exakt zurückkehren - die
        # Allocator-Zählerstände laufen laut AD-001/load_state()-Vertrag nach
        # einem Undo bewusst NICHT rückwärts (siehe Mesh.load_state()-
        # Docstring), deshalb hier kein Vergleich des vollen export_state().
        restored_state = mesh.export_state()
        for key in ("vertices", "edges", "faces", "symmetry"):
            self.assertEqual(restored_state[key], before_state[key], key)

        command.redo()

        self.assertFalse(mesh.is_valid_edge(seam_edge))
        self.assertEqual(mesh.symmetry_definition, definition)


class TestVertexCorrespondence(unittest.TestCase):
    """Vier Correspondence-Zustände (Handoff §3.2, INV-3)."""

    def test_symmetry_off_returns_empty_mapping(self) -> None:
        mesh = Mesh()
        mesh.add_vertex((0.0, 0.0, 0.0))
        self.assertEqual(vertex_correspondence(mesh), {})

    def test_paired(self) -> None:
        mesh, _definition, ids = build_symmetry_test_mesh()
        correspondence = vertex_correspondence(mesh)

        self.assertEqual(correspondence[ids["left"]].state, CorrespondenceState.PAIRED)
        self.assertEqual(correspondence[ids["left"]].partner, ids["right"])
        self.assertEqual(correspondence[ids["right"]].state, CorrespondenceState.PAIRED)
        self.assertEqual(correspondence[ids["right"]].partner, ids["left"])

    def test_seam(self) -> None:
        mesh, _definition, ids = build_symmetry_test_mesh()
        correspondence = vertex_correspondence(mesh)

        self.assertEqual(correspondence[ids["seam0"]].state, CorrespondenceState.SEAM)
        self.assertEqual(correspondence[ids["seam1"]].state, CorrespondenceState.SEAM)
        self.assertIsNone(correspondence[ids["seam0"]].partner)

    def test_unpaired(self) -> None:
        mesh, _definition, ids = build_symmetry_test_mesh()
        correspondence = vertex_correspondence(mesh)

        self.assertEqual(correspondence[ids["unpaired"]].state, CorrespondenceState.UNPAIRED)

    def test_ambiguous(self) -> None:
        mesh, _definition, ids = build_symmetry_test_mesh()
        correspondence = vertex_correspondence(mesh)

        self.assertEqual(correspondence[ids["amb_source"]].state, CorrespondenceState.AMBIGUOUS)

    def test_mirror_position_is_involution(self) -> None:
        """Zweimal spiegeln muss (bei einer achsenausgerichteten Plane
        exakt) die Ursprungsposition zurückgeben."""
        p = (3.0, 4.0, -2.0)
        mirrored = mirror_position(p, PLANE_POINT, PLANE_NORMAL)
        self.assertEqual(mirror_position(mirrored, PLANE_POINT, PLANE_NORMAL), p)
        self.assertEqual(mirrored, (-3.0, 4.0, -2.0))


class TestSymmetryState(unittest.TestCase):
    """Aggregierter Symmetry State (Handoff §3.3)."""

    def test_off_for_mesh_without_definition(self) -> None:
        mesh = Mesh()
        self.assertEqual(symmetry_state(mesh), SymmetryState.OFF)

    def test_off_for_empty_mesh_without_definition(self) -> None:
        self.assertEqual(symmetry_state(Mesh()), SymmetryState.OFF)

    def test_valid_for_fully_symmetric_mesh(self) -> None:
        mesh = Mesh()
        v0 = mesh.add_vertex((0.0, 0.0, 0.0))
        v1 = mesh.add_vertex((0.0, 1.0, 0.0))
        seam_edge = mesh.add_edge(v0, v1)
        mesh.add_vertex((-1.0, 0.0, 0.0))
        mesh.add_vertex((1.0, 0.0, 0.0))
        mesh.symmetry_definition = SymmetryDefinition(
            plane_point=PLANE_POINT, plane_normal=PLANE_NORMAL, seam_edges=frozenset({seam_edge})
        )

        self.assertEqual(symmetry_state(mesh), SymmetryState.VALID)

    def test_partial_for_one_sided_vertex(self) -> None:
        mesh = Mesh()
        v0 = mesh.add_vertex((0.0, 0.0, 0.0))
        v1 = mesh.add_vertex((0.0, 1.0, 0.0))
        seam_edge = mesh.add_edge(v0, v1)
        mesh.add_vertex((-1.0, 0.0, 0.0))
        mesh.add_vertex((1.0, 0.0, 0.0))
        mesh.add_vertex((-5.0, 9.0, 0.0))  # kein Partner
        mesh.symmetry_definition = SymmetryDefinition(
            plane_point=PLANE_POINT, plane_normal=PLANE_NORMAL, seam_edges=frozenset({seam_edge})
        )

        self.assertEqual(symmetry_state(mesh), SymmetryState.PARTIAL)

    def test_ambiguous_for_ambiguous_neighborhood(self) -> None:
        mesh, _definition, _ids = build_symmetry_test_mesh()
        self.assertEqual(symmetry_state(mesh), SymmetryState.AMBIGUOUS)

    def test_violated_for_seam_off_plane(self) -> None:
        mesh = Mesh()
        v0 = mesh.add_vertex((0.0, 0.0, 0.0))       # exakt auf der Plane
        v1 = mesh.add_vertex((0.1, 1.0, 0.0))       # NICHT auf der Plane
        seam_edge = mesh.add_edge(v0, v1)
        mesh.symmetry_definition = SymmetryDefinition(
            plane_point=PLANE_POINT, plane_normal=PLANE_NORMAL, seam_edges=frozenset({seam_edge})
        )

        self.assertEqual(symmetry_state(mesh), SymmetryState.VIOLATED)


if __name__ == "__main__":
    unittest.main()
