"""scene_factory OBJ-Import (AD-008): generische Schicht + Datei-Convenience.

Zwei Testklassen, passend zur Schichtung des Moduls:

- `PositionsAndFacesTests` — reine Datenstruktur-Ebene, keine Abhängigkeit
  auf `examples/`.
- `BuildCoreSceneFromObjTests` — Datei-Ebene, lädt das echte, geteilte
  Head-Basemesh-Asset (AD-007) über den geteilten Loader; braucht `examples/`
  auf sys.path (lokal hier ergänzt, nicht über tests/_bootstrap.py, damit die
  übrigen `tests/` ohne `examples/`-Abhängigkeit bleiben).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import tests._bootstrap  # noqa: F401

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _REPO_ROOT / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from mirai.scene_factory import (
    build_core_scene_from_obj,
    mesh_from_positions_and_faces,
    scene_from_positions_and_faces,
)
from mirai.mesh_geometry import face_type_counts, mesh_bounds

_HEAD_ASSET = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"

# Ein einzelnes Quad (0,0,0)-(1,0,0)-(1,1,0)-(0,1,0).
_QUAD_VERTICES = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
_QUAD_FACES = [(0, 1, 2, 3)]


class PositionsAndFacesTests(unittest.TestCase):
    def test_mesh_from_positions_and_faces_preserves_vertex_order(self):
        mesh = mesh_from_positions_and_faces(_QUAD_VERTICES, _QUAD_FACES)
        positions = [mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()]
        self.assertEqual(positions, _QUAD_VERTICES)

    def test_mesh_from_positions_and_faces_keeps_quad_as_polygon(self):
        mesh = mesh_from_positions_and_faces(_QUAD_VERTICES, _QUAD_FACES)
        counts = face_type_counts(mesh)
        self.assertEqual(counts, {"tri": 0, "quad": 1, "ngon": 0})

    def test_scene_from_positions_and_faces_has_mesh(self):
        scene = scene_from_positions_and_faces(_QUAD_VERTICES, _QUAD_FACES)
        self.assertEqual(len(scene.mesh.all_vertex_ids()), 4)
        self.assertEqual(len(scene.mesh.all_face_ids()), 1)


@unittest.skipUnless(_HEAD_ASSET.is_file(), "Head-Basemesh-Asset nicht gefunden (examples/meshes/)")
class BuildCoreSceneFromObjTests(unittest.TestCase):
    def test_head_basemesh_loads_into_scene(self):
        scene = build_core_scene_from_obj(_HEAD_ASSET)
        self.assertGreater(len(scene.mesh.all_vertex_ids()), 0)
        self.assertGreater(len(scene.mesh.all_face_ids()), 0)

    def test_head_basemesh_bounds_are_nontrivial(self):
        scene = build_core_scene_from_obj(_HEAD_ASSET)
        lo, hi = mesh_bounds(scene.mesh)
        self.assertNotEqual(lo, hi)


if __name__ == "__main__":
    unittest.main()
