"""SelectionOverlay: Highlight-Flags aus core.Selection, isoliert getestet.

Gate 5 (Viewport Production).
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core import Selection, SelectionMode
from mirai.scene_factory import create_cube
from viewport.overlay import SelectionOverlay


class SelectionOverlayTests(unittest.TestCase):
    def setUp(self):
        self.mesh = create_cube()
        self.selection = Selection()
        self.overlay = SelectionOverlay(self.selection)

    def test_no_selection_all_flags_zero(self):
        flags = self.overlay.build_highlight_flags(self.mesh)
        self.assertEqual(set(flags), {0.0})
        self.assertEqual(len(flags), len(self.mesh.all_vertex_ids()))

    def test_vertex_mode_highlights_selected(self):
        vid = self.mesh.all_vertex_ids()[3]
        self.selection.mode = SelectionMode.VERTEX
        self.selection.set({vid})
        flags = self.overlay.build_highlight_flags(self.mesh)
        idx = self.mesh.all_vertex_ids().index(vid)
        self.assertEqual(flags[idx], 1.0)
        self.assertEqual(sum(flags), 1.0)

    def test_edge_mode_highlights_both_endpoints(self):
        eid = self.mesh.all_edge_ids()[0]
        va, vb = self.mesh.edge_vertices(eid)
        self.selection.mode = SelectionMode.EDGE
        self.selection.set({eid})
        flags = self.overlay.build_highlight_flags(self.mesh)
        ids = self.mesh.all_vertex_ids()
        self.assertEqual(flags[ids.index(va)], 1.0)
        self.assertEqual(flags[ids.index(vb)], 1.0)

    def test_face_mode_highlights_all_boundary_vertices(self):
        fid = self.mesh.all_face_ids()[0]
        boundary = self.mesh.face_vertices(fid)
        self.selection.mode = SelectionMode.FACE
        self.selection.set({fid})
        flags = self.overlay.build_highlight_flags(self.mesh)
        ids = self.mesh.all_vertex_ids()
        for v in boundary:
            self.assertEqual(flags[ids.index(v)], 1.0)
        self.assertEqual(sum(flags), float(len(boundary)))

    def test_hover_adds_to_flags_independent_of_mode(self):
        selected = self.mesh.all_vertex_ids()[0]
        hovered_face = self.mesh.all_face_ids()[1]
        self.selection.mode = SelectionMode.VERTEX
        self.selection.set({selected})
        self.selection.hovered = hovered_face

        flags = self.overlay.build_highlight_flags(self.mesh)
        ids = self.mesh.all_vertex_ids()
        self.assertEqual(flags[ids.index(selected)], 1.0)
        for v in self.mesh.face_vertices(hovered_face):
            self.assertEqual(flags[ids.index(v)], 1.0)

    def test_object_mode_returns_no_highlights(self):
        self.selection.mode = SelectionMode.OBJECT
        flags = self.overlay.build_highlight_flags(self.mesh)
        self.assertEqual(set(flags), {0.0})

    def test_does_not_mutate_selection(self):
        vid = self.mesh.all_vertex_ids()[0]
        self.selection.mode = SelectionMode.VERTEX
        self.selection.set({vid})
        before = set(self.selection.vertices)
        self.overlay.build_highlight_flags(self.mesh)
        self.assertEqual(self.selection.vertices, before)

    # -- Stale IDs (WP-06 B6 fix, Praxistest-Bug 2026-09-28) -----------------
    #
    # Eine Topologie-Mutation entfernt IDs aus dem Mesh (AD-001/AD-002):
    # Split/Connect ersetzen die gehoverten/selektierten Edge-IDs, Undo kann
    # sie wieder entfernen, ein Szenenwechsel ersetzt das ganze Mesh. Ein
    # Handle, das `mesh` nicht mehr kennt, darf diese Methode nicht sprengen
    # (vorher: `KeyError` aus `mesh.edge_vertices`, ausgelöst mitten im
    # Draw-Pfad).

    def test_stale_selected_edge_is_skipped(self):
        eid = self.mesh.all_edge_ids()[0]
        self.mesh.split_edge(eid)  # eid wird ungültig
        self.selection.mode = SelectionMode.EDGE
        self.selection.set({eid})

        flags = self.overlay.build_highlight_flags(self.mesh)

        self.assertEqual(set(flags), {0.0})

    def test_stale_selected_face_is_skipped(self):
        fid = self.mesh.all_face_ids()[0]
        self.mesh.remove_face(fid)
        self.selection.mode = SelectionMode.FACE
        self.selection.set({fid})

        flags = self.overlay.build_highlight_flags(self.mesh)

        self.assertEqual(set(flags), {0.0})

    def test_stale_selected_vertex_is_skipped(self):
        eid = self.mesh.all_edge_ids()[0]
        _, vanishing = self.mesh.edge_vertices(eid)
        self.mesh.collapse_edge(eid)  # vanishing wird ungültig
        self.selection.mode = SelectionMode.VERTEX
        self.selection.set({vanishing})

        flags = self.overlay.build_highlight_flags(self.mesh)

        self.assertEqual(set(flags), {0.0})

    def test_stale_hovered_edge_is_skipped(self):
        eid = self.mesh.all_edge_ids()[0]
        self.mesh.split_edge(eid)
        self.selection.mode = SelectionMode.VERTEX
        self.selection.hovered = eid

        flags = self.overlay.build_highlight_flags(self.mesh)

        self.assertEqual(set(flags), {0.0})

    def test_stale_hovered_face_and_vertex_are_skipped(self):
        fid = self.mesh.all_face_ids()[0]
        self.mesh.remove_face(fid)
        eid = self.mesh.all_edge_ids()[0]
        _, vanishing = self.mesh.edge_vertices(eid)
        self.mesh.collapse_edge(eid)

        for hovered in (fid, vanishing):
            with self.subTest(hovered=hovered):
                self.selection.hovered = hovered
                flags = self.overlay.build_highlight_flags(self.mesh)
                self.assertEqual(set(flags), {0.0})

    def test_valid_highlights_survive_a_stale_hover(self):
        """Nur die ungültige ID fällt weg — die gültige Auswahl bleibt."""
        stale = self.mesh.all_edge_ids()[0]
        self.mesh.split_edge(stale)
        fid = self.mesh.all_face_ids()[0]
        boundary = self.mesh.face_vertices(fid)
        self.selection.mode = SelectionMode.FACE
        self.selection.set({fid})
        self.selection.hovered = stale

        flags = self.overlay.build_highlight_flags(self.mesh)

        ids = self.mesh.all_vertex_ids()
        for vertex_id in boundary:
            self.assertEqual(flags[ids.index(vertex_id)], 1.0)
        self.assertEqual(sum(flags), float(len(set(boundary))))


if __name__ == "__main__":
    unittest.main()
