"""Headless-Tests für AP-03 Phase 1 — PlaygroundSelector + Selection-VBO.

Kein GL, kein Fenster. Prüft:
    1.  handle_face_click hit → selection.faces enthält genau eine Face
    2.  handle_face_click hit → selection.mode ist FACE
    3.  handle_face_click hit → gibt True zurück
    4.  handle_face_click miss → selection.faces ist leer
    5.  handle_face_click miss nach vorheriger Selektion → selection leer, True
    6.  handle_face_click miss auf leere Selection → False (kein Change)
    7.  zweiter Click → Replace (nur letzte Face selektiert)
    8.  selektierte Face ist Teil des Mesh
    9.  CLICK_THRESHOLD ist ein positiver Float
    10. build_selection_data: leere Auswahl → leere Liste
    11. build_selection_data: eine Face → korrekte Triangle-Anzahl
    12. build_selection_data: alle Positionen sind bekannte Mesh-Positionen
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
from playground.selector import CLICK_THRESHOLD, handle_face_click  # noqa: E402
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
