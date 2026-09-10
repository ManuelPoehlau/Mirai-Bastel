"""Headless-Tests für AP-02.5 — Viewport Presentation Lab.

Kein GL, kein Fenster, kein pyglet. Prüft:
    1. PresentationExperiment-Varianten setzen den erwarteten DisplayState
    2. show_vertices-Flag wird korrekt gesetzt
    3. deactivate() verändert den State nicht
    4. Smooth- und Flat-Normalen-Daten sind geometrisch korrekt (Cube)
    5. Edge-VBO-Daten decken alle Mesh-Edges ab
    6. Vertex-VBO-Daten decken alle Mesh-Vertices ab
    7. Flat-Normalen sind je Triangle einheitlich (kein Mischmasch)
    8. Smooth-Normalen unterscheiden sich i.A. von Flat-Normalen (Cube-Ecken)
    9. Face-VBO-Länge ist konsistent (positions / smooth / flat / colors)
    10. DisplayState.cycle()-Reihenfolge ist Shaded → Flat → Wireframe
    11. HUD update_display() setzt display_line korrekt
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
_RIGGING = _REPO_ROOT / "experiments" / "rigging-skinning-morphing"
for _p in (str(_REPO_SRC), str(_REPO_ROOT), str(_RIGGING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import math  # noqa: E402

import pytest  # noqa: E402

from mirai.scene_factory import create_cube  # noqa: E402
from mirai.viewport.display import DisplayMode, DisplayState  # noqa: E402
from playground.app import PlaygroundApp  # noqa: E402
from playground.experiments.presentation.base import PresentationExperiment  # noqa: E402
from playground.experiments.presentation.variant_flat import FlatVariant  # noqa: E402
from playground.experiments.presentation.variant_full import FullVariant  # noqa: E402
from playground.experiments.presentation.variant_shaded import ShadedVariant  # noqa: E402
from playground.experiments.presentation.variant_shaded_vertices import (  # noqa: E402
    ShadedVerticesVariant,
)
from playground.experiments.presentation.variant_shaded_wire import ShadedWireVariant  # noqa: E402
from playground.experiments.presentation.variant_wireframe import WireframeVariant  # noqa: E402
from playground.hud import PlaygroundHUD  # noqa: E402
from playground.vbo_builder import build_edge_data, build_face_data, build_vertex_data  # noqa: E402
from viewport.derived import DerivedGeometry  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app() -> PlaygroundApp:
    return PlaygroundApp()


@pytest.fixture
def cube_mesh():
    return create_cube()


@pytest.fixture
def cube_derived(cube_mesh):
    return DerivedGeometry(cube_mesh)


# ---------------------------------------------------------------------------
# 1–3: Varianten-State
# ---------------------------------------------------------------------------

class TestVariantState:

    def test_shaded_variant_sets_mode(self, app):
        ShadedVariant(app).activate()
        assert app.display_state.mode is DisplayMode.SHADED
        assert app.display_state.wireframe_overlay is False
        assert app.show_vertices is False

    def test_flat_variant_sets_flat_mode(self, app):
        FlatVariant(app).activate()
        assert app.display_state.mode is DisplayMode.FLAT_SHADED
        assert app.display_state.wireframe_overlay is False
        assert app.show_vertices is False

    def test_wireframe_variant(self, app):
        WireframeVariant(app).activate()
        assert app.display_state.mode is DisplayMode.WIREFRAME
        assert app.display_state.wireframe_overlay is False
        assert app.show_vertices is False

    def test_shaded_wire_variant(self, app):
        ShadedWireVariant(app).activate()
        assert app.display_state.mode is DisplayMode.SHADED
        assert app.display_state.wireframe_overlay is True
        assert app.show_vertices is False

    def test_shaded_vertices_variant(self, app):
        ShadedVerticesVariant(app).activate()
        assert app.display_state.mode is DisplayMode.SHADED
        assert app.display_state.wireframe_overlay is False
        assert app.show_vertices is True

    def test_full_variant(self, app):
        FullVariant(app).activate()
        assert app.display_state.mode is DisplayMode.SHADED
        assert app.display_state.wireframe_overlay is True
        assert app.show_vertices is True

    def test_deactivate_does_not_change_state(self, app):
        v = ShadedWireVariant(app)
        v.activate()
        v.deactivate()
        assert app.display_state.mode is DisplayMode.SHADED
        assert app.display_state.wireframe_overlay is True

    def test_variant_switch_overwrites_state(self, app):
        FullVariant(app).activate()
        WireframeVariant(app).activate()
        assert app.display_state.mode is DisplayMode.WIREFRAME
        assert app.display_state.wireframe_overlay is False
        assert app.show_vertices is False


# ---------------------------------------------------------------------------
# 4: Flat-Normalen korrekt (Cube)
# ---------------------------------------------------------------------------

class TestFlatNormals:

    def test_flat_normals_are_unit_length(self, cube_mesh, cube_derived):
        _, _, flat_normals, _ = build_face_data(cube_mesh, cube_derived)
        # flat_normals ist eine flache Liste: [nx0,ny0,nz0, nx1,ny1,nz1, ...]
        for i in range(0, len(flat_normals), 3):
            nx, ny, nz = flat_normals[i], flat_normals[i + 1], flat_normals[i + 2]
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            assert abs(length - 1.0) < 1e-6, f"flat_normal not unit at index {i}"

    def test_flat_normals_same_per_triangle(self, cube_mesh, cube_derived):
        """Alle 3 Vertices eines Dreiecks müssen dieselbe Flat-Normale haben."""
        _, _, flat_normals, _ = build_face_data(cube_mesh, cube_derived)
        for tri_idx in range(len(flat_normals) // 9):
            base = tri_idx * 9
            n0 = flat_normals[base:base + 3]
            n1 = flat_normals[base + 3:base + 6]
            n2 = flat_normals[base + 6:base + 9]
            assert n0 == n1, f"Triangle {tri_idx}: n0 != n1"
            assert n0 == n2, f"Triangle {tri_idx}: n0 != n2"

    def test_flat_normals_are_axis_aligned_for_cube(self, cube_mesh, cube_derived):
        """Cube-Faces haben achsenparallele Normalen (±x, ±y, ±z)."""
        _, _, flat_normals, _ = build_face_data(cube_mesh, cube_derived)
        for i in range(0, len(flat_normals), 3):
            nx, ny, nz = flat_normals[i], flat_normals[i + 1], flat_normals[i + 2]
            # Eine Komponente nahe ±1, die anderen nahe 0
            components = sorted([abs(nx), abs(ny), abs(nz)], reverse=True)
            assert components[0] > 0.9, f"No dominant axis at index {i}"
            assert components[1] < 0.1, f"Unexpected second component at index {i}"


# ---------------------------------------------------------------------------
# 5: Edge-VBO
# ---------------------------------------------------------------------------

class TestEdgeData:

    def test_edge_count_matches_mesh(self, cube_mesh):
        edge_positions = build_edge_data(cube_mesh)
        n_edges = len(list(cube_mesh.all_edge_ids()))
        # 2 Positionen à 3 Floats pro Edge
        assert len(edge_positions) == n_edges * 6

    def test_edge_positions_match_mesh_vertices(self, cube_mesh):
        edge_positions = build_edge_data(cube_mesh)
        # Alle Positionen im Edge-VBO müssen existierenden Vertex-Positionen entsprechen
        known_positions = {
            cube_mesh.vertex_position(vid)
            for vid in cube_mesh.all_vertex_ids()
        }
        for i in range(0, len(edge_positions), 3):
            p = (edge_positions[i], edge_positions[i + 1], edge_positions[i + 2])
            assert p in known_positions, f"Edge position {p} not in mesh vertices"

    def test_cube_has_12_edges(self, cube_mesh):
        n_edges = len(list(cube_mesh.all_edge_ids()))
        assert n_edges == 12


# ---------------------------------------------------------------------------
# 6: Vertex-VBO
# ---------------------------------------------------------------------------

class TestVertexData:

    def test_vertex_count_matches_mesh(self, cube_mesh):
        vert_positions = build_vertex_data(cube_mesh)
        n_verts = len(list(cube_mesh.all_vertex_ids()))
        assert len(vert_positions) == n_verts * 3

    def test_vertex_positions_match_mesh(self, cube_mesh):
        vert_positions = build_vertex_data(cube_mesh)
        known_positions = {
            cube_mesh.vertex_position(vid)
            for vid in cube_mesh.all_vertex_ids()
        }
        for i in range(0, len(vert_positions), 3):
            p = (vert_positions[i], vert_positions[i + 1], vert_positions[i + 2])
            assert p in known_positions


# ---------------------------------------------------------------------------
# 8: Smooth != Flat an Cube-Ecken
# ---------------------------------------------------------------------------

class TestSmoothVsFlat:

    def test_smooth_and_flat_differ_at_corners(self, cube_mesh, cube_derived):
        _, smooth_normals, flat_normals, _ = build_face_data(cube_mesh, cube_derived)
        # An mindestens einem Vertex müssen Smooth und Flat unterschiedlich sein
        # (Cube-Ecken haben gemittelte Smooth-Normalen, keine achsenparallelen)
        differs = any(
            smooth_normals[i] != flat_normals[i]
            for i in range(len(smooth_normals))
        )
        assert differs, "Smooth and flat normals are identical — expected difference at corners"


# ---------------------------------------------------------------------------
# 9: Buffer-Konsistenz
# ---------------------------------------------------------------------------

class TestBufferConsistency:

    def test_face_buffer_lengths_match(self, cube_mesh, cube_derived):
        positions, smooth_normals, flat_normals, colors = build_face_data(
            cube_mesh, cube_derived
        )
        assert len(positions) == len(smooth_normals)
        assert len(positions) == len(flat_normals)
        assert len(positions) == len(colors)

    def test_face_buffer_divisible_by_9(self, cube_mesh, cube_derived):
        positions, _, _, _ = build_face_data(cube_mesh, cube_derived)
        # Expanded Triangles: 3 Vertices à 3 Floats
        assert len(positions) % 9 == 0

    def test_color_buffer_is_white(self, cube_mesh, cube_derived):
        _, _, _, colors = build_face_data(cube_mesh, cube_derived)
        assert all(c == 1.0 for c in colors)


# ---------------------------------------------------------------------------
# 10: DisplayState.cycle() Reihenfolge
# ---------------------------------------------------------------------------

class TestDisplayStateCycle:

    def test_cycle_order(self):
        ds = DisplayState()
        assert ds.mode is DisplayMode.SHADED
        ds.cycle()
        assert ds.mode is DisplayMode.FLAT_SHADED
        ds.cycle()
        assert ds.mode is DisplayMode.WIREFRAME
        ds.cycle()
        assert ds.mode is DisplayMode.SHADED

    def test_wireframe_overlay_toggle(self):
        ds = DisplayState()
        assert ds.wireframe_overlay is False
        ds.toggle_wireframe_overlay()
        assert ds.wireframe_overlay is True
        ds.toggle_wireframe_overlay()
        assert ds.wireframe_overlay is False

    def test_show_faces_false_in_wireframe(self):
        ds = DisplayState(mode=DisplayMode.WIREFRAME)
        assert ds.show_faces is False

    def test_show_edges_true_with_overlay(self):
        ds = DisplayState(mode=DisplayMode.SHADED, wireframe_overlay=True)
        assert ds.show_edges is True


# ---------------------------------------------------------------------------
# 11: HUD display_line
# ---------------------------------------------------------------------------

class TestHudDisplayLine:

    def test_update_display_sets_line(self):
        hud = PlaygroundHUD()
        hud.update_display("Flat Shaded")
        assert hud.display_line == "Display: Flat Shaded"

    def test_default_display_line(self):
        hud = PlaygroundHUD()
        assert hud.display_line == "Display: Shaded"

    def test_display_line_in_full_text(self):
        hud = PlaygroundHUD()
        hud.update_display("Wireframe")
        text = hud._full_text()
        assert "Display: Wireframe" in text
