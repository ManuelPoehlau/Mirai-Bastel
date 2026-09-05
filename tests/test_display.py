"""DisplayState: Tests für den Viewport-Display-State (window-/GPU-frei).

Prüft `mirai.viewport.display.DisplayState`: Standardmodus, Mode-Cycle,
Wireframe-Overlay, Mode-Validierung und die abgeleiteten show_faces/show_edges-
Flags, die die Viewport-Schicht in Gate 5 anhand dessen lesen wird.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from mirai.viewport import DisplayMode, DisplayState


class DisplayStateTests(unittest.TestCase):
    def test_default_is_shaded_without_overlay(self):
        d = DisplayState()
        self.assertEqual(d.mode, DisplayMode.SHADED)
        self.assertFalse(d.wireframe_overlay)

    def test_default_show_faces_without_edges(self):
        d = DisplayState()
        self.assertTrue(d.show_faces)
        self.assertFalse(d.show_edges)

    def test_cycle_advances_shaded_to_flat_to_wireframe(self):
        d = DisplayState()
        d.cycle()
        self.assertEqual(d.mode, DisplayMode.FLAT_SHADED)
        d.cycle()
        self.assertEqual(d.mode, DisplayMode.WIREFRAME)
        d.cycle()
        self.assertEqual(d.mode, DisplayMode.SHADED)

    def test_toggle_wireframe_overlay(self):
        d = DisplayState()
        d.toggle_wireframe_overlay()
        self.assertTrue(d.wireframe_overlay)
        d.toggle_wireframe_overlay()
        self.assertFalse(d.wireframe_overlay)

    def test_set_mode_changes_mode(self):
        d = DisplayState()
        d.set_mode(DisplayMode.WIREFRAME)
        self.assertEqual(d.mode, DisplayMode.WIREFRAME)
        self.assertFalse(d.show_faces)
        self.assertTrue(d.show_edges)

    def test_set_mode_invalid_raises(self):
        d = DisplayState()
        with self.assertRaises(ValueError):
            d.set_mode("NotAMode")

    def test_set_wireframe_overlay_explicit(self):
        d = DisplayState()
        d.set_wireframe_overlay(True)
        self.assertTrue(d.wireframe_overlay)
        d.set_wireframe_overlay(False)
        self.assertFalse(d.wireframe_overlay)

    def test_wireframe_overlay_combines_with_faces(self):
        d = DisplayState(mode=DisplayMode.SHADED, wireframe_overlay=True)
        self.assertTrue(d.show_faces)
        self.assertTrue(d.show_edges)
        self.assertIn("+ Wire", d.label)

    def test_wireframe_mode_shows_only_edges(self):
        d = DisplayState(mode=DisplayMode.WIREFRAME, wireframe_overlay=True)
        self.assertFalse(d.show_faces)
        self.assertTrue(d.show_edges)
        # In reinem Wireframe-Modus ist overlay semantisch nicht relevant;
        # das Label bleibt "Wireframe".
        self.assertEqual(d.label, "Wireframe")

    def test_flat_shaded_label(self):
        d = DisplayState(mode=DisplayMode.FLAT_SHADED)
        self.assertEqual(d.label, "Flat Shaded")
        self.assertFalse(d.wireframe_overlay)


if __name__ == "__main__":
    unittest.main()
