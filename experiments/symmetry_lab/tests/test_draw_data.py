"""VBO-Daten (Handoff Slice 2 §7) — GL-frei, gegen `subd_cube`."""

from __future__ import annotations

import pytest

from mirai.application import Application

from symmetry_lab import lab_draw_data
from symmetry_lab.lab_scene import load_asset_into


@pytest.fixture
def mesh():
    app = Application()
    load_asset_into(app, "subd_cube")
    return app.scene.mesh


def test_subd_cube_topology_is_as_registered(mesh):
    # Registry: 26 V / 24 Quads, geschlossen → Euler V - E + F = 2 → 48 Edges.
    assert len(mesh.all_vertex_ids()) == 26
    assert len(mesh.all_face_ids()) == 24
    assert len(mesh.all_edge_ids()) == 48
    assert all(len(mesh.face_vertices(f)) == 4 for f in mesh.all_face_ids())


def test_face_data_lengths(mesh):
    positions, normals = lab_draw_data.face_data(mesh)
    # 24 Quads → 48 Dreiecke → 144 Vertices à 3 Floats.
    assert len(positions) == 24 * 2 * 3 * 3
    assert len(normals) == len(positions)


def test_edge_and_vertex_data_lengths(mesh):
    assert len(lab_draw_data.edge_data(mesh)) == 48 * 2 * 3
    assert len(lab_draw_data.vertex_data(mesh)) == 26 * 3


def test_highlight_contains_exactly_the_selected_vertex(mesh):
    vid = sorted(mesh.all_vertex_ids())[7]
    data = lab_draw_data.highlight_data(mesh, {vid})
    assert data == list(mesh.vertex_position(vid))


def test_highlight_empty_without_selection(mesh):
    assert lab_draw_data.highlight_data(mesh, set()) == []
