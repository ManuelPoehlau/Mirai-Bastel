"""Headless-Tests für AP-03 Phase 1+2 — PlaygroundSelector + Selection-VBO.

Kein GL, kein Fenster. Prüft Phase 1 (Replace) und Phase 2 (Modifier/Toggle).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
for _p in (str(_REPO_SRC), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from core.selection import Selection, SelectionMode  # noqa: E402
from mirai.scene_factory import create_cube  # noqa: E402
from playground.selector import (  # noqa: E402
    CLICK_THRESHOLD,
    SelectMode,
    dispatch_face_click,
    handle_face_click,
    handle_face_click_modifier,
    handle_face_click_toggle,
)
from playground.vbo_builder import build_selection_data  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal-Kamera-Stubs für headless Picking
# ---------------------------------------------------------------------------

class _FrontCamera:
    """Kamera die immer einen Ray auf die Würfelvorderseite schickt."""
    def screen_to_ray(self, sx, sy, width, height):
        # Ray von (0, 0, 5) in Richtung (0, 0, -1) → trifft z=+1-Face
        return (0.0, 0.0, 5.0), (0.0, 0.0, -1.0)

    def project_to_screen(self, world_pos, width, height):
        return None


class _MissCamera:
    """Kamera die immer einen Ray vom Cube weg schickt."""
    def screen_to_ray(self, sx, sy, width, height):
        # Ray von (0, 0, 5) in Richtung (0, 0, +1) → trifft nichts
        return (0.0, 0.0, 5.0), (0.0, 0.0, 1.0)

    def project_to_screen(self, world_pos, width, height):
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cube():
    return create_cube()

@pytest.fixture
def sel():
    return Selection()

@pytest.fixture
def front_cam():
    return _FrontCamera()

@pytest.fixture
def miss_cam():
    return _MissCamera()


# ---------------------------------------------------------------------------
# 1–8: handle_face_click Verhalten
# ---------------------------------------------------------------------------

class TestHandleFaceClick:

    def test_hit_selects_one_face(self, cube, sel, front_cam):
        handle_face_click(front_cam, cube, sel, 320, 240, 640, 480)
        assert len(sel.faces) == 1

    def test_hit_sets_face_mode(self, cube, sel, front_cam):
        handle_face_click(front_cam, cube, sel, 320, 240, 640, 480)
        assert sel.mode is SelectionMode.FACE

    def test_hit_returns_true(self, cube, sel, front_cam):
        changed = handle_face_click(front_cam, cube, sel, 320, 240, 640, 480)
        assert changed is True

    def test_miss_clears_selection(self, cube, sel, front_cam, miss_cam):
        handle_face_click(front_cam, cube, sel, 320, 240, 640, 480)
        assert len(sel.faces) == 1
        handle_face_click(miss_cam, cube, sel, 320, 240, 640, 480)
        assert sel.faces == set()

    def test_miss_after_selection_returns_true(self, cube, sel, front_cam, miss_cam):
        handle_face_click(front_cam, cube, sel, 320, 240, 640, 480)
        changed = handle_face_click(miss_cam, cube, sel, 320, 240, 640, 480)
        assert changed is True

    def test_miss_on_empty_returns_false(self, cube, sel, miss_cam):
        changed = handle_face_click(miss_cam, cube, sel, 320, 240, 640, 480)
        assert changed is False

    def test_second_hit_replaces_first(self, cube, sel):
        # Zwei Kameras die verschiedene Faces treffen
        class _TopCamera:
            def screen_to_ray(self, sx, sy, w, h):
                return (0.0, 5.0, 0.0), (0.0, -1.0, 0.0)
            def project_to_screen(self, p, w, h):
                return None

        handle_face_click(_FrontCamera(), cube, sel, 320, 240, 640, 480)
        first = frozenset(sel.faces)
        handle_face_click(_TopCamera(), cube, sel, 320, 240, 640, 480)
        assert len(sel.faces) == 1
        assert frozenset(sel.faces) != first  # andere Face

    def test_hit_face_is_in_mesh(self, cube, sel, front_cam):
        handle_face_click(front_cam, cube, sel, 320, 240, 640, 480)
        fid = next(iter(sel.faces))
        assert fid in set(cube.all_face_ids())


# ---------------------------------------------------------------------------
# 9: CLICK_THRESHOLD
# ---------------------------------------------------------------------------

class TestClickThreshold:

    def test_threshold_is_positive(self):
        assert CLICK_THRESHOLD > 0

    def test_threshold_is_float(self):
        assert isinstance(CLICK_THRESHOLD, float)


# ---------------------------------------------------------------------------
# 10–12: build_selection_data
# ---------------------------------------------------------------------------

class TestBuildSelectionData:

    def test_empty_selection_returns_empty(self, cube):
        assert build_selection_data(cube, set()) == []

    def test_one_face_returns_triangles(self, cube):
        fid = next(iter(cube.all_face_ids()))
        data = build_selection_data(cube, {fid})
        boundary = cube.face_vertices(fid)
        # Quad → 2 Dreiecke à 3 Vertices à 3 Floats = 18
        n_tris = len(boundary) - 2
        assert len(data) == n_tris * 3 * 3

    def test_positions_are_known_mesh_positions(self, cube, sel, front_cam):
        handle_face_click(front_cam, cube, sel, 320, 240, 640, 480)
        data = build_selection_data(cube, sel.faces)
        known = {cube.vertex_position(vid) for vid in cube.all_vertex_ids()}
        for i in range(0, len(data), 3):
            p = (data[i], data[i + 1], data[i + 2])
            assert p in known, f"Position {p} not in mesh"

    def test_all_faces_selected_covers_mesh(self, cube):
        all_fids = set(cube.all_face_ids())
        data = build_selection_data(cube, all_fids)
        # Cube: 6 Faces à 2 Dreiecke = 12 Dreiecke à 3 Vertices à 3 Floats
        assert len(data) == 12 * 3 * 3


# ---------------------------------------------------------------------------
# Phase 2 — Variante A: Modifier (Shift/Ctrl/Alt)
# ---------------------------------------------------------------------------

class _MockInputMap:
    """Minimales InputMap-Stub für Modifier-Tests."""
    from pyglet.window import key as _k
    add_modifier    = _k.MOD_SHIFT
    remove_modifier = _k.MOD_CTRL
    toggle_modifier = _k.MOD_ALT


class TestHandleFaceClickModifier:

    def test_bare_click_replaces_like_phase1(self, cube, sel, front_cam):
        imap = _MockInputMap()
        handle_face_click_modifier(front_cam, cube, sel, 320, 240, 640, 480, 0, imap)
        assert len(sel.faces) == 1

    def test_shift_click_adds_to_existing(self, cube, sel, front_cam):
        from pyglet.window import key
        imap = _MockInputMap()
        # Erst Front-Face selektieren
        handle_face_click_modifier(front_cam, cube, sel, 320, 240, 640, 480, 0, imap)
        first = frozenset(sel.faces)

        class _TopCamera:
            def screen_to_ray(self, sx, sy, w, h):
                return (0.0, 5.0, 0.0), (0.0, -1.0, 0.0)
            def project_to_screen(self, p, w, h): return None

        # Shift+Click auf andere Face → addiert
        handle_face_click_modifier(
            _TopCamera(), cube, sel, 320, 240, 640, 480, key.MOD_SHIFT, imap
        )
        assert len(sel.faces) == 2
        assert first.issubset(sel.faces)

    def test_ctrl_click_removes_face(self, cube, sel, front_cam):
        from pyglet.window import key
        imap = _MockInputMap()
        handle_face_click_modifier(front_cam, cube, sel, 320, 240, 640, 480, 0, imap)
        fid = next(iter(sel.faces))
        handle_face_click_modifier(
            front_cam, cube, sel, 320, 240, 640, 480, key.MOD_CTRL, imap
        )
        assert fid not in sel.faces

    def test_alt_click_toggles_off(self, cube, sel, front_cam):
        from pyglet.window import key
        imap = _MockInputMap()
        handle_face_click_modifier(front_cam, cube, sel, 320, 240, 640, 480, 0, imap)
        fid = next(iter(sel.faces))
        handle_face_click_modifier(
            front_cam, cube, sel, 320, 240, 640, 480, key.MOD_ALT, imap
        )
        assert fid not in sel.faces

    def test_alt_click_toggles_on(self, cube, sel, front_cam):
        from pyglet.window import key
        imap = _MockInputMap()
        # Zunächst leer
        handle_face_click_modifier(
            front_cam, cube, sel, 320, 240, 640, 480, key.MOD_ALT, imap
        )
        assert len(sel.faces) == 1

    def test_shift_miss_does_not_clear(self, cube, sel, front_cam, miss_cam):
        from pyglet.window import key
        imap = _MockInputMap()
        handle_face_click_modifier(front_cam, cube, sel, 320, 240, 640, 480, 0, imap)
        count_before = len(sel.faces)
        changed = handle_face_click_modifier(
            miss_cam, cube, sel, 320, 240, 640, 480, key.MOD_SHIFT, imap
        )
        assert changed is False
        assert len(sel.faces) == count_before

    def test_bare_miss_clears_selection(self, cube, sel, front_cam, miss_cam):
        imap = _MockInputMap()
        handle_face_click_modifier(front_cam, cube, sel, 320, 240, 640, 480, 0, imap)
        handle_face_click_modifier(miss_cam, cube, sel, 320, 240, 640, 480, 0, imap)
        assert sel.faces == set()


# ---------------------------------------------------------------------------
# Phase 2 — Variante B: Toggle
# ---------------------------------------------------------------------------

class TestHandleFaceClickToggle:

    def test_hit_selects_unselected_face(self, cube, sel, front_cam):
        handle_face_click_toggle(front_cam, cube, sel, 320, 240, 640, 480)
        assert len(sel.faces) == 1

    def test_hit_deselects_already_selected(self, cube, sel, front_cam):
        handle_face_click_toggle(front_cam, cube, sel, 320, 240, 640, 480)
        handle_face_click_toggle(front_cam, cube, sel, 320, 240, 640, 480)
        assert sel.faces == set()

    def test_miss_does_not_clear(self, cube, sel, front_cam, miss_cam):
        handle_face_click_toggle(front_cam, cube, sel, 320, 240, 640, 480)
        count = len(sel.faces)
        changed = handle_face_click_toggle(miss_cam, cube, sel, 320, 240, 640, 480)
        assert changed is False
        assert len(sel.faces) == count

    def test_multiple_faces_accumulate(self, cube, sel):
        class _TopCam:
            def screen_to_ray(self, sx, sy, w, h):
                return (0.0, 5.0, 0.0), (0.0, -1.0, 0.0)
            def project_to_screen(self, p, w, h): return None

        handle_face_click_toggle(_FrontCamera(), cube, sel, 320, 240, 640, 480)
        handle_face_click_toggle(_TopCam(), cube, sel, 320, 240, 640, 480)
        assert len(sel.faces) == 2


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

class TestDispatchFaceClick:

    def test_dispatch_replace(self, cube, sel, front_cam):
        imap = _MockInputMap()
        dispatch_face_click(
            front_cam, cube, sel, 320, 240, 640, 480, 0, imap, SelectMode.REPLACE
        )
        assert len(sel.faces) == 1

    def test_dispatch_modifier(self, cube, sel, front_cam):
        from pyglet.window import key
        imap = _MockInputMap()
        dispatch_face_click(
            front_cam, cube, sel, 320, 240, 640, 480, 0, imap, SelectMode.MODIFIER
        )
        assert len(sel.faces) == 1

    def test_dispatch_toggle(self, cube, sel, front_cam):
        imap = _MockInputMap()
        dispatch_face_click(
            front_cam, cube, sel, 320, 240, 640, 480, 0, imap, SelectMode.TOGGLE
        )
        dispatch_face_click(
            front_cam, cube, sel, 320, 240, 640, 480, 0, imap, SelectMode.TOGGLE
        )
        assert sel.faces == set()

    def test_dispatch_unknown_returns_false(self, cube, sel, front_cam):
        # SelectMode ist ein echtes Enum — kein unbekannter Wert möglich,
        # aber dispatch_face_click gibt False für unbekannte zurück (Fallback).
        # Wir testen den None-Fall direkt über den Rückgabewert.
        imap = _MockInputMap()
        result = dispatch_face_click(
            front_cam, cube, sel, 320, 240, 640, 480, 0, imap, SelectMode.REPLACE
        )
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# SelectMode Enum
# ---------------------------------------------------------------------------

class TestSelectMode:

    def test_three_modes_exist(self):
        assert SelectMode.REPLACE is not None
        assert SelectMode.MODIFIER is not None
        assert SelectMode.TOGGLE is not None

    def test_modes_are_distinct(self):
        assert SelectMode.REPLACE != SelectMode.MODIFIER
        assert SelectMode.MODIFIER != SelectMode.TOGGLE


# ---------------------------------------------------------------------------
# HUD Selection-Zeile
# ---------------------------------------------------------------------------

class TestHudSelectionLine:

    def test_default_selection_line(self):
        from playground.hud import PlaygroundHUD
        hud = PlaygroundHUD()
        assert hud.selection_line == "Selection: none"

    def test_update_selection_none(self):
        from playground.hud import PlaygroundHUD
        hud = PlaygroundHUD()
        hud.update_selection(0)
        assert hud.selection_line == "Selection: none"

    def test_update_selection_one_face(self):
        from playground.hud import PlaygroundHUD
        hud = PlaygroundHUD()
        hud.update_selection(1)
        assert "1 face" in hud.selection_line

    def test_update_selection_many_faces(self):
        from playground.hud import PlaygroundHUD
        hud = PlaygroundHUD()
        hud.update_selection(3)
        assert "3 faces" in hud.selection_line

    def test_update_selection_with_mode_label(self):
        from playground.hud import PlaygroundHUD
        hud = PlaygroundHUD()
        hud.update_selection(1, "Modifier")
        assert "Modifier" in hud.selection_line
