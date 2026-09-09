"""Integrationsgrenze OBJ → Core:

    OBJ-Datei -> ObjMeshData (OBJ-Loader, unverändert) -> src.core.Mesh

Geprüft wird das REALE Head-Basemesh: Vertex-/Face-Zahlen, Face-Typen,
Positionsübertragung und die Core-Entitätsbilanz (Edges aus den Faces).
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parents[1]
for _p in (str(_LAB), str(_LAB.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from adapters.obj_to_core import (  # noqa: E402
    DEFAULT_HEAD_ASSET,
    build_core_scene_from_obj,
    face_type_counts,
    mesh_bounds,
    obj_data_to_core_mesh,
)
from scene.scene_objects import build_cube_scene  # noqa: E402

from loaders.obj_loader import load_obj  # noqa: E402
from core.ids import VertexId  # noqa: E402  (Production-Importpfad)


def test_obj_loader_reused_and_head_parse():
    data = load_obj(DEFAULT_HEAD_ASSET)
    assert data.vertex_count > 300          # reales Asset, kein Dummy
    assert data.face_count > 300
    counts = data.face_type_counts()
    assert counts["quad"] > 0               # das Asset nutzt Quads


def test_obj_to_core_head_counts_match_loader():
    data = load_obj(DEFAULT_HEAD_ASSET)
    mesh = obj_data_to_core_mesh(data)
    assert len(mesh.all_vertex_ids()) == data.vertex_count
    assert len(mesh.all_face_ids()) == data.face_count


def test_obj_to_core_positions_are_identical():
    data = load_obj(DEFAULT_HEAD_ASSET)
    mesh = obj_data_to_core_mesh(data)
    for i, vid in enumerate(mesh.all_vertex_ids()):
        assert mesh.vertex_position(vid) == data.vertices[i]


def test_obj_to_core_edges_derived_from_faces():
    """Jede Face-Boundary-Edge existiert als Core-Edge (AD-002)."""
    mesh = obj_data_to_core_mesh(load_obj(DEFAULT_HEAD_ASSET))
    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        for i in range(len(boundary)):
            v_a, v_b = boundary[i], boundary[(i + 1) % len(boundary)]
            edges = [eid for eid in mesh.vertex_edges(v_a)
                     if v_b in mesh.edge_vertices(eid)]
            assert edges, f"Fehlende Core-Edge {v_a}-{v_b}"


def test_scene_build_from_obj_is_src_core_scene():
    scene = build_core_scene_from_obj(DEFAULT_HEAD_ASSET)
    assert scene.mesh is not None
    assert len(scene.mesh.all_vertex_ids()) > 300
    # src.core-Scene-Struktur vorhanden
    assert hasattr(scene, "selection")
    assert hasattr(scene, "history")


def test_head_bounds_are_non_trivial():
    mesh = obj_data_to_core_mesh(load_obj(DEFAULT_HEAD_ASSET))
    (min_x, min_y, min_z), (max_x, max_y, max_z) = mesh_bounds(mesh)
    # Der Head liegt nicht am Ursprung und hat eine reale Ausdehnung.
    assert max_x - min_x > 1.0
    assert max_y - min_y > 1.0
    assert max_x - min_x < 100.0


def test_cube_is_deterministic_controlled_object():
    scene = build_cube_scene()
    mesh = scene.mesh
    assert len(mesh.all_vertex_ids()) == 8
    assert len(mesh.all_face_ids()) == 6
    counts = face_type_counts(mesh)
    assert counts["quad"] == 6
    for vid in mesh.all_vertex_ids():
        assert isinstance(vid, VertexId)