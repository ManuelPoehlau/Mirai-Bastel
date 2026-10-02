"""A8: unsupported input raises `SubdUnsupportedError` with a German message."""

from __future__ import annotations

import pytest
from mirai.scene_factory import mesh_from_positions_and_faces

from subdivision_lab.subd import SubdSurface, SubdUnsupportedError


def test_a8_edge_with_three_faces():
    # three triangles sharing the edge 0-1
    mesh = mesh_from_positions_and_faces(
        [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1)],
        [[0, 1, 2], [1, 0, 3], [0, 1, 4]],
    )
    with pytest.raises(SubdUnsupportedError) as info:
        SubdSurface(mesh)
    message = str(info.value)
    assert "Kante" in message and "3 Flächen" in message and "nicht-manifold" in message


def test_a8_boundary_vertex_with_four_boundary_edges():
    # two triangles touching only at vertex 0 (bow tie): vertex 0 has 4 boundary edges
    mesh = mesh_from_positions_and_faces(
        [(0, 0, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)],
        [[0, 1, 2], [0, 3, 4]],
    )
    with pytest.raises(SubdUnsupportedError) as info:
        SubdSurface(mesh)
    message = str(info.value)
    assert "Randvertex" in message and "4 Randkanten" in message


def test_a8_vertex_without_face():
    mesh = mesh_from_positions_and_faces([(0, 0, 0), (1, 0, 0), (0, 1, 0), (5, 5, 5)], [[0, 1, 2]])
    with pytest.raises(SubdUnsupportedError) as info:
        SubdSurface(mesh)
    assert "keiner Fläche" in str(info.value)


def test_a8_is_a_value_error_not_a_crash_on_valid_input():
    from .meshes import single_quad_mesh

    SubdSurface(single_quad_mesh()).level(2)  # valid boundary mesh: no exception
    assert issubclass(SubdUnsupportedError, ValueError)
