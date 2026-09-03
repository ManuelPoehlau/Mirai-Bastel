"""Headless-Strukturtest: OBJ → Mesh (mirai_bastel_core) → Scene (Viewport V1).

Getestet wird die Datenstrecke, die der Launcher run_viewport.py benutzt,
plus das duck-typed-API-Subset, das ModelerWindow/TopologyWindow an einer
Scene verwenden (selection.mode, Mesh-Query-API). Das tatsächliche Fenster
bewusst NICHT: Fenster-Erzeugung bleibt ein manueller Starttest
(python run_viewport.py). Kamera-Framing wird mit einer Dummy-Kamera
geprüft (OrbitCamera ist ein simpler dataclass-Vertrag).
"""

import math
import sys
from pathlib import Path

# Experiment-Ordner in den Pfad (Konvention wie in den vorhandenen Tests):
_EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENT_DIR))

import pytest

# WICHTIG: viewport_adapter zuerst importieren — sein Bootstrap setzt
# experiments/mirai_bastel_core_V1 auf sys.path, sodass der direkte
# mirai_bastel_core-Import (daher noqa: E402) darunter funktioniert.
from viewport_adapter import (  # noqa: E402
    DEFAULT_HEAD_ASSET,
    build_scene_from_data,
    build_scene_from_obj,
    face_type_counts,
    format_debug_report,
    frame_camera_on_bounds,
    mesh_bounds,
    mesh_center_and_radius,
)
from mirai_bastel_core import Scene, SelectionMode  # noqa: E402
from loaders.obj_loader import load_obj  # noqa: E402


def _unique_edges_from_faces(mesh) -> set[frozenset]:
    edges: set[frozenset] = set()
    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        for i in range(len(boundary)):
            edges.add(frozenset((boundary[i], boundary[(i + 1) % len(boundary)])))
    return edges


class _DummyOrbitCamera:
    """Minimaler OrbitCamera-Ersatz (dataclass-Attribut-Vertrag)."""

    target = (0.0, 0.0, 0.0)
    distance = 6.0
    fov_degrees = 50.0


# =====================================================================
# OBJ → Mesh → Scene
# =====================================================================

class TestObjToSceneIntegration:
    def test_scene_is_viewport_core_scene(self):
        scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
        assert isinstance(scene, Scene)

    def test_mesh_counts_match_asset(self):
        scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
        mesh = scene.mesh
        assert len(mesh.all_vertex_ids()) == 326
        assert len(mesh.all_edge_ids()) == 648
        assert len(mesh.all_face_ids()) == 324

    def test_edges_are_deduplicated(self):
        # add_face muss Edges wiederverwenden: eindeutige Vertex-Paare aus
        # allen Face-Boundaries == Anzahl der Edge-IDs im Mesh.
        scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
        mesh = scene.mesh
        unique = _unique_edges_from_faces(mesh)
        assert len(unique) == len(mesh.all_edge_ids()) == 648

    def test_mesh_is_closed_manifold(self):
        # Ground truth des Assets: jede Edge wird von genau 2 Faces genutzt.
        scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
        mesh = scene.mesh
        for eid in mesh.all_edge_ids():
            assert len(mesh.edge_faces(eid)) == 2

    def test_vertex_order_preserved(self):
        data = load_obj(DEFAULT_HEAD_ASSET)
        scene = build_scene_from_data(data)
        mesh = scene.mesh
        vids = sorted(mesh.all_vertex_ids(), key=int)
        for i, vid in enumerate(vids):
            assert mesh.vertex_position(vid) == data.vertices[i]

    def test_faces_are_all_quads(self):
        scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
        assert face_type_counts(scene.mesh) == {"tri": 0, "quad": 324, "ngon": 0}

    def test_bounds_match_asset(self):
        scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
        (min_x, min_y, min_z), (max_x, max_y, max_z) = mesh_bounds(scene.mesh)
        assert (min_x, max_x) == pytest.approx((-2.605081, 2.605081))
        assert (min_y, max_y) == pytest.approx((0.0, 4.778098))
        assert (min_z, max_z) == pytest.approx((-1.647624, 1.647624))

    def test_scene_surface_expected_by_window(self):
        """API-Subset, das TopologyWindow/ModelerWindow an einer Scene nutzen."""
        scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
        scene.selection.mode = SelectionMode.VERTEX
        scene.selection.clear()
        scene.selection.set({next(iter(scene.mesh.all_vertex_ids()))})
        assert scene.selection.vertices
        boundary = scene.mesh.face_vertices(next(iter(scene.mesh.all_face_ids())))
        assert len(boundary) == 4


# =====================================================================
# Kamera-Framing + Debug-Report (Adapter-Helfer)
# =====================================================================

class TestAdapterHelpers:
    def test_frames_camera_on_head(self):
        scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
        center, radius = mesh_center_and_radius(scene.mesh)
        assert center == pytest.approx((0.0, 2.389049, 0.0), abs=1e-6)
        assert radius == pytest.approx(3.3716871, rel=1e-5)

        camera = _DummyOrbitCamera()
        frame_camera_on_bounds(camera, scene.mesh)
        assert camera.target == pytest.approx(center)
        expected_distance = (radius / math.tan(math.radians(25.0))) * 1.25
        assert camera.distance == pytest.approx(expected_distance)
        assert 0.5 <= camera.distance <= 200.0  # innerhalb des Dolly-Bereichs

    def test_report_contains_key_facts(self):
        scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
        report = format_debug_report("head_basemesh.obj", scene.mesh)
        assert "Living Mesh Research" in report
        assert "Asset: head_basemesh.obj" in report
        assert "Vertices: 326" in report
        assert "Edges:    648" in report
        assert "Faces:    324" in report
        assert "324 Quads" in report
        assert "X: -2.605081 .. 2.605081" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
