"""DirtyState/Update-Kategorien: Flags, Revisionen, Interleaving.

Gate 5 (Viewport Production). `test_active_categories_no_typo` deckt einen
Tippfehler ab, der im Ursprungs-Experiment vorhanden war (`TOPLOGY` statt
`TOPOLOGY`) und hier korrigiert wurde.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core import VertexId
from viewport.category import (
    CAMERA,
    GEOMETRY,
    MATERIAL,
    SELECTION,
    TOPOLOGY,
    DirtyState,
)


class DirtyStateTests(unittest.TestCase):
    def test_defaults_all_clean(self):
        state = DirtyState()
        self.assertFalse(state.camera)
        self.assertFalse(state.geometry)
        self.assertFalse(state.selection)
        self.assertFalse(state.material)
        self.assertFalse(state.topology)
        self.assertEqual(state.modified_vertices, set())

    def test_reset_clears_all_flags_and_vertices(self):
        state = DirtyState()
        state.camera = True
        state.geometry = True
        state.selection = True
        state.material = True
        state.topology = True
        state.modified_vertices.add(VertexId(1))

        state.reset()

        self.assertFalse(state.camera)
        self.assertFalse(state.geometry)
        self.assertFalse(state.selection)
        self.assertFalse(state.material)
        self.assertFalse(state.topology)
        self.assertEqual(state.modified_vertices, set())

    def test_reset_does_not_touch_revisions(self):
        state = DirtyState()
        state.camera_rev = 5
        state.reset()
        self.assertEqual(state.camera_rev, 5)

    def test_is_any_geometry_work_true_for_geometry(self):
        state = DirtyState()
        state.geometry = True
        self.assertTrue(state.is_any_geometry_work())

    def test_is_any_geometry_work_true_for_topology(self):
        state = DirtyState()
        state.topology = True
        self.assertTrue(state.is_any_geometry_work())

    def test_is_any_geometry_work_false_otherwise(self):
        state = DirtyState()
        state.camera = True
        state.selection = True
        self.assertFalse(state.is_any_geometry_work())

    def test_active_categories_no_typo(self):
        """Regression: Experiment hatte 'TOPLOGY' (Tippfehler) statt
        'TOPOLOGY' in active_categories() - hätte bei Aufruf einen
        NameError ausgelöst. Hier muss der Aufruf fehlerfrei funktionieren
        und TOPOLOGY korrekt enthalten, wenn gesetzt."""
        state = DirtyState()
        state.topology = True
        active = state.active_categories()  # darf keinen NameError werfen
        self.assertIn(TOPOLOGY, active)

    def test_active_categories_respects_order_and_selection(self):
        state = DirtyState()
        state.geometry = True
        state.camera = True
        active = state.active_categories()
        self.assertEqual(active, [CAMERA, GEOMETRY])

    def test_active_categories_all_categories(self):
        state = DirtyState()
        state.camera = state.selection = state.material = True
        state.geometry = state.topology = True
        active = state.active_categories()
        self.assertEqual(
            set(active), {CAMERA, SELECTION, MATERIAL, GEOMETRY, TOPOLOGY}
        )

    def test_modified_vertices_deduplicated(self):
        state = DirtyState()
        vid = VertexId(7)
        state.modified_vertices.add(vid)
        state.modified_vertices.add(vid)
        self.assertEqual(len(state.modified_vertices), 1)


if __name__ == "__main__":
    unittest.main()
