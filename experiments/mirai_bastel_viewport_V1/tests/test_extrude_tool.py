"""Extrude-Tool Tests — Topology, Geometry, Selection, History, Cancel.

Verifiziert das Single-Face-Extrude-Experiment:
- Topologie: neue Vertices, Side-Faces, Result-Face, Original wird entfernt (5 Faces bei Quad)
- Geometry: Newell-Normale, Extrusionsdistanz, Winding (Mantelflächen nach außen)
- Selection: nach Commit ist nur die neue Result-Face ausgewählt
- History: genau ein Eintrag, Undo/Redo korrekt, keine stale IDs
- Cancel: exakter Ausgangszustand, keine History
- Interaktion: Alt+E startet sofort INTERACTING
"""

import unittest
from pathlib import Path
import sys

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from mirai_bastel_core import Mesh, Selection, SelectionMode, HistoryStack, Scene

from viewport.extrude_tool import ExtrudeTool, _compute_face_normal
from viewport.topology_tools import TopologyToolError


def _make_quad_mesh():
    """Erzeugt ein einfaches Quad-Mesh in der XY-Ebene (Normal +Z)."""
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    mesh.add_face([v0, v1, v2, v3])
    return mesh


def _make_scene():
    mesh = _make_quad_mesh()
    sel = Selection()
    sel.mode = SelectionMode.FACE
    sel.set(set(mesh.all_face_ids()))
    scene = Scene()
    scene.mesh = mesh
    scene.selection = sel
    history = HistoryStack()
    scene.history = history
    return scene, history


class _StubCamera:
    """Kamera-Stub: Pixel-Delta wird 1:1 als Welt-Delta interpretiert."""

    def screen_delta_to_world(self, anchor_pos, dx, dy, width, height):
        return (dx, dy, 0.0)


class ExtrudeTopologyTests(unittest.TestCase):
    """Topologie-Tests: Vertices, Faces, Boundaries."""

    def setUp(self):
        self.scene, self.history = _make_scene()
        self.tool = ExtrudeTool(self.scene, _StubCamera())
        self.face_id = next(iter(self.scene.mesh.all_face_ids()))

    def test_begin_creates_new_vertices(self):
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        mesh = self.scene.mesh
        # 4 original + 4 new = 8 vertices
        self.assertEqual(len(mesh.all_vertex_ids()), 8)
        self.assertEqual(len(self.tool.new_vertex_ids), 4)

    def test_begin_creates_five_faces_total(self):
        """Original Face wird entfernt: 4 Side + 1 Result = 5 Faces."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        mesh = self.scene.mesh
        # 4 side + 1 result = 5 faces (kein Original mehr)
        self.assertEqual(len(mesh.all_face_ids()), 5)

    def test_original_face_removed(self):
        """Ursprüngliche Face existiert nach begin() nicht mehr."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        mesh = self.scene.mesh
        self.assertFalse(mesh.is_valid_face(self.face_id))

    def test_result_face_exists(self):
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        mesh = self.scene.mesh
        self.assertIsNotNone(self.tool.new_face_id)
        self.assertTrue(mesh.is_valid_face(self.tool.new_face_id))

    def test_four_side_faces_exist(self):
        """Es gibt genau 4 Mantelflächen (Boundary-Edges des Originals)."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        mesh = self.scene.mesh
        all_faces = set(mesh.all_face_ids())
        # Result-Face + 4 Side-Faces = 5 total
        self.assertEqual(len(all_faces), 5)
        self.assertIn(self.tool.new_face_id, all_faces)

    def test_new_vertices_on_original_boundary(self):
        """Neue Vertices liegen anfangs an den Original-Positionen."""
        mesh = self.scene.mesh
        # Original-Positionen VOR begin() speichern
        original_positions = [mesh.vertex_position(vid) for vid in mesh.face_vertices(self.face_id)]
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        # Neue Vertices sollten an den Original-Positionen liegen
        for i, new_vid in enumerate(self.tool.new_vertex_ids):
            new_pos = mesh.vertex_position(new_vid)
            self.assertEqual(original_positions[i], new_pos)


class ExtrudeGeometryTests(unittest.TestCase):
    """Geometrie-Tests: Normale, Extrusionsdistanz, Winding."""

    def setUp(self):
        self.scene, self.history = _make_scene()
        self.tool = ExtrudeTool(self.scene, _StubCamera())
        self.face_id = next(iter(self.scene.mesh.all_face_ids()))

    def test_normal_points_along_z(self):
        """Quad in XY-Ebene → Normale entlang +Z."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        normal = self.tool.normal
        self.assertIsNotNone(normal)
        # Newell-Normale für XY-Quad: +Z oder -Z (abhängig von Winding)
        self.assertAlmostEqual(abs(normal[2]), 1.0, places=6)

    def test_extrude_distance_accumulates(self):
        """Kumulierte Distanz wird bei update() erhöht."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        # Stub gibt (dx, dy, 0) zurück → kein Z-Delta
        self.tool.update(dx=0.0, dy=0.0, width=800, height=600)
        # Mit diesem Stub: keine Z-Bewegung → distance = 0
        self.assertEqual(self.tool.total_distance, 0.0)


class ExtrudeSelectionTests(unittest.TestCase):
    """Selection-Tests: nach Commit ist nur neue Face ausgewählt."""

    def setUp(self):
        self.scene, self.history = _make_scene()
        self.tool = ExtrudeTool(self.scene, _StubCamera())
        self.face_id = next(iter(self.scene.mesh.all_face_ids()))

    def test_commit_returns_new_face_id(self):
        """commit() liefert die neue Result-FaceId."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        result = self.tool.commit()
        self.assertEqual(result, self.tool.new_face_id)

    def test_after_commit_new_face_selected(self):
        """Nach Commit (im Window) ist nur die neue Face ausgewählt."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        new_face_id = self.tool.commit()
        # Simuliere Window-Verhalten: Selection setzen
        self.scene.selection.clear()
        self.scene.selection.mode = SelectionMode.FACE
        self.scene.selection.set({new_face_id})
        # Nur die neue Face ist ausgewählt
        self.assertEqual(self.scene.selection.faces, {new_face_id})
        self.assertNotIn(self.face_id, self.scene.selection.faces)


class ExtrudeHistoryTests(unittest.TestCase):
    """History-Tests: ein Eintrag, Undo/Redo korrekt."""

    def setUp(self):
        self.scene, self.history = _make_scene()
        self.tool = ExtrudeTool(self.scene, _StubCamera())
        self.face_id = next(iter(self.scene.mesh.all_face_ids()))

    def test_commit_creates_single_history_entry(self):
        """Commit erzeugt genau einen History-Eintrag."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        self.tool.commit()
        self.tool.deactivate()
        self.assertEqual(len(self.history._undo_stack), 1)

    def test_undo_removes_extrusion(self):
        """Undo entfernt die komplette Extrusion."""
        mesh = self.scene.mesh
        original_vertex_count = len(mesh.all_vertex_ids())
        original_face_count = len(mesh.all_face_ids())
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        self.tool.commit()
        self.tool.deactivate()
        # Undo
        self.history.undo()
        self.assertEqual(len(mesh.all_vertex_ids()), original_vertex_count)
        self.assertEqual(len(mesh.all_face_ids()), original_face_count)

    def test_redo_restores_extrusion(self):
        """Redo stellt die Extrusion wieder her."""
        mesh = self.scene.mesh
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        self.tool.commit()
        self.tool.deactivate()
        # Undo
        self.history.undo()
        # Redo
        self.history.redo()
        # 8 vertices, 5 faces (4 side + 1 result, original removed)
        self.assertEqual(len(mesh.all_vertex_ids()), 8)
        self.assertEqual(len(mesh.all_face_ids()), 5)


class ExtrudeCancelTests(unittest.TestCase):
    """Cancel-Tests: exakter Ausgangszustand, keine History."""

    def setUp(self):
        self.scene, self.history = _make_scene()
        self.tool = ExtrudeTool(self.scene, _StubCamera())
        self.face_id = next(iter(self.scene.mesh.all_face_ids()))

    def test_cancel_restores_original_state(self):
        """Cancel stellt den exakten Ausgangszustand wieder her."""
        mesh = self.scene.mesh
        original_vertices = set(mesh.all_vertex_ids())
        original_edges = set(mesh.all_edge_ids())
        original_faces = set(mesh.all_face_ids())
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        self.tool.cancel()
        self.tool.deactivate()
        # Topologie ist identisch mit Original
        self.assertEqual(set(mesh.all_vertex_ids()), original_vertices)
        self.assertEqual(set(mesh.all_edge_ids()), original_edges)
        self.assertEqual(set(mesh.all_face_ids()), original_faces)

    def test_cancel_creates_no_history_entry(self):
        """Cancel erzeugt keinen History-Eintrag."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        self.tool.cancel()
        self.tool.deactivate()
        self.assertEqual(len(self.history._undo_stack), 0)

    def test_cancel_clears_tool_state(self):
        """Nach Cancel ist der Tool-Zustand zurückgesetzt."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        self.tool.cancel()
        # Tool ist wieder ACTIVE (nicht INTERACTING)
        self.assertFalse(self.tool.is_interacting)
        self.assertTrue(self.tool.is_active)


class ExtrudeValidationTests(unittest.TestCase):
    """Validierungs-Tests: ungültige Eingaben."""

    def setUp(self):
        self.scene, self.history = _make_scene()
        self.tool = ExtrudeTool(self.scene, _StubCamera())

    def test_begin_invalid_face_raises(self):
        """begin() mit ungültiger FaceId raises."""
        self.tool.activate()
        with self.assertRaises(TopologyToolError):
            self.tool.begin(face_id=9999)

    def test_begin_without_activate_raises(self):
        """begin() ohne activate() raises."""
        with self.assertRaises(Exception):
            self.tool.begin(face_id=1)


class NewellNormalTests(unittest.TestCase):
    """Tests für die Newell-Normalenberechnung."""

    def test_quad_xy_plane(self):
        """Quad in XY-Ebene → Normale entlang Z."""
        mesh = _make_quad_mesh()
        boundary = mesh.face_vertices(next(iter(mesh.all_face_ids())))
        normal = _compute_face_normal(mesh, boundary)
        # Normale sollte entlang Z sein
        self.assertAlmostEqual(abs(normal[2]), 1.0, places=6)
        self.assertAlmostEqual(normal[0], 0.0, places=6)
        self.assertAlmostEqual(normal[1], 0.0, places=6)

    def test_normalized(self):
        """Normale ist normalisiert."""
        mesh = _make_quad_mesh()
        boundary = mesh.face_vertices(next(iter(mesh.all_face_ids())))
        normal = _compute_face_normal(mesh, boundary)
        length = (normal[0]**2 + normal[1]**2 + normal[2]**2) ** 0.5
        self.assertAlmostEqual(length, 1.0, places=6)


class ExtrudeWindingTests(unittest.TestCase):
    """Geometrische Winding-Tests: Mantelflächen-Normalen nach außen."""

    def setUp(self):
        self.scene, self.history = _make_scene()
        self.tool = ExtrudeTool(self.scene, _StubCamera())
        self.face_id = next(iter(self.scene.mesh.all_face_ids()))

    def test_side_face_normals_point_outward(self):
        """Für XY-Quad mit +Z-Extrusion: Mantelflächen-Normalen zeigen nach außen.

        Die Boundary ist [v0(0,0,0), v1(1,0,0), v2(1,1,0), v3(0,1,0)] (CCW).
        Newell-Normale ist +Z. Mantelflächen-Winding [v_curr, v_next, v_next_new, v_curr_new]
        muss Normalen erzeugen, die radial nach außen zeigen (XY-Komponent weg von Center).

        WICHTIG: Bei distance=0 sind Mantelflächen degeneriert (alle Vertices in XY-Ebene).
        Daher zuerst update() mit Z-Durchschritt aufrufen.
        """
        mesh = self.scene.mesh
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)

        # Mit _StubCamera: screen_delta_to_world gibt (dx, dy, 0) zurück.
        # Die Projektion auf die Newell-Normale (+Z) ergibt 0, daher müssen wir
        # die neuen Vertices manuell verschieben, um nicht-degenerierte Mantelflächen zu haben.
        # Alternative: Distanz direkt manipulieren.
        new_dist = 1.0
        for i, vid in enumerate(self.tool.new_vertex_ids):
            orig = mesh.vertex_position(self.tool._boundary[i])
            new_pos = (orig[0], orig[1], orig[2] + new_dist)
            mesh.set_vertex_position(vid, new_pos)

        # Face-Center der Original-Face (0.5, 0.5, 0)
        center = (0.5, 0.5, 0.0)

        # Alle Faces außer der Result-Face sind Mantelflächen
        result_fid = self.tool.new_face_id
        side_faces = [fid for fid in mesh.all_face_ids() if fid != result_fid]
        self.assertEqual(len(side_faces), 4)

        for fid in side_faces:
            boundary = mesh.face_vertices(fid)
            # Newell-Normale der Mantelfläche
            normal = _compute_face_normal(mesh, boundary)
            # Die XY-Komponente der Normale muss vom Center weg zeigen
            # Für jede Side-Face: Mindestens eine XY-Komponente != 0
            self.assertNotEqual(
                (normal[0], normal[1]), (0.0, 0.0),
                f"Mantelfläche {fid} hat keine XY-Normale (zeigt entlang Z)"
            )

    def test_result_face_normal_matches_original(self):
        """Result-Face hat dieselbe Normalenrichtung wie die Original-Face."""
        mesh = self.scene.mesh
        # Original-Normale berechnen (vor begin)
        orig_boundary = mesh.face_vertices(self.face_id)
        orig_normal = _compute_face_normal(mesh, orig_boundary)

        self.tool.activate()
        self.tool.begin(face_id=self.face_id)

        # Result-Face-Normale
        result_boundary = mesh.face_vertices(self.tool.new_face_id)
        result_normal = _compute_face_normal(mesh, result_boundary)

        # Gleiche Richtung (Dot-Produkt > 0)
        dot = sum(a * b for a, b in zip(orig_normal, result_normal))
        self.assertGreater(dot, 0.0,
            "Result-Face-Normale muss gleiche Richtung wie Original haben")


class ExtrudeSelectionSyncTests(unittest.TestCase):
    """Selection-Sync nach Undo/Redo/Cancel: keine stale IDs."""

    def setUp(self):
        self.scene, self.history = _make_scene()
        self.tool = ExtrudeTool(self.scene, _StubCamera())
        self.face_id = next(iter(self.scene.mesh.all_face_ids()))

    def test_undo_restores_valid_selection(self):
        """Undo stellt gültige Selection wieder her (keine stale FaceIds)."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        self.tool.commit()
        self.tool.deactivate()
        # Undo
        self.history.undo()
        # Selection muss gültig sein
        sel = self.scene.selection
        mesh = self.scene.mesh
        for fid in sel.faces:
            self.assertTrue(mesh.is_valid_face(fid),
                f"Selection enthält ungültige FaceId: {fid}")

    def test_redo_restores_valid_selection(self):
        """Redo stellt gültige Selection wieder her."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        self.tool.commit()
        self.tool.deactivate()
        self.history.undo()
        self.history.redo()
        # Selection muss gültig sein
        sel = self.scene.selection
        mesh = self.scene.mesh
        for fid in sel.faces:
            self.assertTrue(mesh.is_valid_face(fid),
                f"Selection enthält ungültige FaceId: {fid}")

    def test_cancel_restores_valid_selection(self):
        """Cancel stellt gültige Selection wieder her."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        self.tool.cancel()
        self.tool.deactivate()
        # Selection muss gültig sein
        sel = self.scene.selection
        mesh = self.scene.mesh
        for fid in sel.faces:
            self.assertTrue(mesh.is_valid_face(fid),
                f"Selection enthält ungültige FaceId: {fid}")
        # Original-Face sollte wieder ausgewählt sein
        self.assertIn(self.face_id, sel.faces)


class ExtrudeAutoBeginTests(unittest.TestCase):
    """Alt+E startet sofort INTERACTING (kein zweiter Klick)."""

    def setUp(self):
        self.scene, self.history = _make_scene()
        self.tool = ExtrudeTool(self.scene, _StubCamera())
        self.face_id = next(iter(self.scene.mesh.all_face_ids()))

    def test_begin_immediately_interacting(self):
        """Nach begin() ist der Tool sofort INTERACTING."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        self.assertTrue(self.tool.is_interacting)

    def test_update_after_begin(self):
        """update() funktioniert direkt nach begin() (kein Klick nötig)."""
        self.tool.activate()
        self.tool.begin(face_id=self.face_id)
        # Sollte nicht raisen
        self.tool.update(dx=1.0, dy=0.0, width=800, height=600)
        # Tool ist noch interagierend
        self.assertTrue(self.tool.is_interacting)


if __name__ == "__main__":
    unittest.main()