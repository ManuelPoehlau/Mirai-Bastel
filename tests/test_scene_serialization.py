"""Phase E – Serialisierung (Hardening-Plan §17 Phase E).

    Scene -> save -> load -> Zustand vergleichen (inkl. IDs und
    Allocator-Zuständen)

Unterschied zum bestehenden Basis-Roundtrip-Test in test_core.py: dort
wird nur eine unmutierte Quad-Scene gespeichert und nur Vertex-Anzahl /
Face-ID-Menge / eine Position geprüft. Phase E prüft zusätzlich:

- Roundtrip NACH einer Sequenz aus split/collapse/connect (nicht nur auf
  einer frischen Scene) - vollständige Vertex-/Edge-/Face-Beziehungen
  über `full_topology_snapshot()` (aus Phase D wiederverwendet), nicht
  nur einzelne Stichproben.
- Allocator-Zählerstände exakt gleich (nicht nur "keine Kollision").
- Selection/History werden bewusst NICHT mitgespeichert (dokumentierter
  Vertrag in serialization.py) - das wird hier erstmals explizit als
  Regressionsschutz festgeschrieben, nicht nur angenommen.
- dict- und JSON-String-Roundtrip liefern dasselbe Ergebnis.
- unbekannte Format-Version wird abgelehnt.
- ID-Kollisionsfreiheit nach dem Laden gilt für alle drei Elementtypen,
  nicht nur für Vertices.

Vorab-Untersuchung (vor der Testimplementierung, nicht danach): anders
als bei Phase D wurde hier KEINE Core-Lücke gefunden - export_state()/
load_state()/scene_to_dict()/scene_from_dict() decken bereits alles ab,
was Phase E verlangt. Diese Phase ist deshalb reine Testarbeit, keine
Produktionscode-Änderung.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core.mesh import Mesh
from core.scene import Scene
from core.serialization import scene_from_dict, scene_from_json, scene_to_dict, scene_to_json
from tests.mesh_invariants import assert_mesh_invariants
from tests.test_topology_history import full_topology_snapshot


def build_mutated_scene() -> tuple[Scene, tuple]:
    """Szene NACH einer Mutationssequenz (nicht nur die rohe Fixture) -
    genau der Fall, den der bestehende Basis-Test in test_core.py nicht
    abdeckt."""
    scene = Scene()
    mesh = scene.mesh
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    face = mesh.add_face([v0, v1, v2, v3])

    mesh.split_edge(mesh._get_or_create_edge(v0, v1))
    mesh.collapse_edge(mesh._get_or_create_edge(v2, v3))
    v4 = mesh.add_vertex((2.0, 2.0, 0.0))
    mesh.add_face([v1, v4, v2])

    return scene, (v0, v1, v2, v3, v4, face)


class TestSceneSerializationRoundtrip(unittest.TestCase):
    def test_dict_roundtrip_after_mutations_exact_state(self) -> None:
        scene, _ids = build_mutated_scene()
        before = full_topology_snapshot(scene.mesh)

        data = scene_to_dict(scene)
        restored = scene_from_dict(data)

        after = full_topology_snapshot(restored.mesh)
        self.assertEqual(after, before, "Roundtrip muss die vollständige Mesh-Relation exakt erhalten")
        assert_mesh_invariants(restored.mesh, context="scene roundtrip (dict)")

        # restored.mesh ist bewusst eine ANDERE Instanz (scene_from_dict
        # baut eine frische Scene) - kein Aliasing, das einen falschen
        # Testerfolg vortäuschen könnte.
        self.assertIsNot(restored.mesh, scene.mesh)

    def test_json_roundtrip_matches_dict_roundtrip(self) -> None:
        scene, _ids = build_mutated_scene()
        before = full_topology_snapshot(scene.mesh)

        text = scene_to_json(scene)
        restored = scene_from_json(text)

        after = full_topology_snapshot(restored.mesh)
        self.assertEqual(after, before, "JSON-Roundtrip darf sich nicht vom dict-Roundtrip unterscheiden")
        assert_mesh_invariants(restored.mesh, context="scene roundtrip (json)")

    def test_allocator_counters_survive_exactly(self) -> None:
        scene, _ids = build_mutated_scene()
        before_state = scene.mesh.export_state()

        restored = scene_from_dict(scene_to_dict(scene))
        after_state = restored.mesh.export_state()

        for key in ("vertex_id_counter", "edge_id_counter", "face_id_counter"):
            self.assertEqual(
                after_state[key], before_state[key],
                f"{key} muss nach dem Roundtrip exakt gleich sein, nicht nur 'groß genug'",
            )

    def test_new_ids_after_load_never_collide_for_all_element_types(self) -> None:
        scene, (v0, v1, v2, v3, v4, face) = build_mutated_scene()
        old_vertex_ids = set(scene.mesh.all_vertex_ids())
        old_edge_ids = set(scene.mesh.all_edge_ids())
        old_face_ids = set(scene.mesh.all_face_ids())

        restored = scene_from_dict(scene_to_dict(scene))

        new_v = restored.mesh.add_vertex((9.0, 9.0, 9.0))
        self.assertNotIn(new_v, old_vertex_ids)

        # Eine neue Edge/Face entsteht nur über add_face - reicht, um
        # Edge- UND Face-Allocator gleichzeitig zu prüfen.
        other_v = next(iter(restored.mesh.all_vertex_ids()))
        third_v = restored.mesh.add_vertex((8.0, 8.0, 8.0))
        new_face = restored.mesh.add_face([new_v, other_v, third_v])
        new_edges = set(restored.mesh.face_edges(new_face))

        self.assertNotIn(new_face, old_face_ids)
        self.assertEqual(new_edges & old_edge_ids, set(), "keine neu erzeugte Edge darf eine alte ID wiederverwenden")
        assert_mesh_invariants(restored.mesh, context="scene roundtrip + weitere Mutation")

    def test_selection_and_history_are_not_persisted(self) -> None:
        """Dokumentierter Vertrag in serialization.py - hier erstmals als
        Regressionsschutz festgeschrieben statt nur angenommen."""
        scene, (v0, v1, v2, v3, v4, face) = build_mutated_scene()
        scene.selection.set({v1, v2})
        # Ein echter History-Eintrag (nicht nur eine rohe Mesh-Mutation) -
        # falls das Format doch einmal versehentlich History mitspeichert,
        # soll das hier auffallen.
        from core.history import HistoryStack
        from core.operations.topology import MeshStateCommand

        before = scene.mesh.export_state()
        scene.mesh.add_vertex((5.0, 5.0, 5.0))
        after = scene.mesh.export_state()
        scene.history.push(MeshStateCommand(mesh=scene.mesh, before_state=before, after_state=after))

        self.assertTrue(scene.selection.vertices)
        self.assertGreater(len(scene.history), 0)

        restored = scene_from_dict(scene_to_dict(scene))

        self.assertEqual(restored.selection.vertices, set(), "Selection ist transienter UI-Zustand, wird nicht gespeichert")
        self.assertEqual(len(restored.history), 0, "History ist transienter Session-Zustand, wird nicht gespeichert")
        self.assertIsInstance(restored.history, HistoryStack)

    def test_reserved_subsystem_slots_present_and_null_in_v1(self) -> None:
        scene, _ids = build_mutated_scene()
        data = scene_to_dict(scene)
        self.assertTrue({"mesh", "morph_targets", "rig", "animation", "version"}.issubset(data.keys()))
        self.assertIsNone(data["morph_targets"])
        self.assertIsNone(data["rig"])
        self.assertIsNone(data["animation"])

        restored = scene_from_dict(data)
        self.assertIsNone(restored.morph_targets)
        self.assertIsNone(restored.rig)
        self.assertIsNone(restored.animation)

    def test_unknown_format_version_is_rejected(self) -> None:
        scene, _ids = build_mutated_scene()
        data = scene_to_dict(scene)
        data["version"] = 999
        with self.assertRaises(ValueError):
            scene_from_dict(data)


class TestSceneSerializationEmptyScene(unittest.TestCase):
    """Randfall: eine leere Scene (kein einziger Vertex) muss ebenfalls
    verlustfrei roundtriggen - nicht nur mesh-tragende Szenen."""

    def test_empty_scene_roundtrip(self) -> None:
        scene = Scene()
        before = full_topology_snapshot(scene.mesh)

        restored = scene_from_dict(scene_to_dict(scene))

        self.assertEqual(full_topology_snapshot(restored.mesh), before)
        assert_mesh_invariants(restored.mesh, context="empty scene roundtrip")

        # Auf einer aus dem Leeren geladenen Scene muss die allererste neu
        # erzeugte ID bei 0 beginnen (kein Off-by-one durch den leeren
        # Roundtrip).
        new_v = restored.mesh.add_vertex((0.0, 0.0, 0.0))
        self.assertEqual(int(new_v), 0)


if __name__ == "__main__":
    unittest.main()
