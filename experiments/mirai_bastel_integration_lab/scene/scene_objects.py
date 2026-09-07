"""Testobjekt-Fabriken: Cube (kontrolliert) + reales Head-Basemesh.

Objekt A — Cube: 8 Vertices / 6 Quad-Faces, deterministisch, als
Smoke-/Selection-/Move-/Kamera-/Performance-Vergleichsobjekt.

Objekt B — Head Basemesh: das REALE Asset aus dem Rigging/Skinning/Morphing-
Experiment (`meshes/head_basemesh.obj`), OHNE Dummy-Ersatz. Genau daran soll
sichtbar werden, ob der im alten Viewport beobachtete Lag weiter existiert.
"""

from __future__ import annotations

from pathlib import Path

from _paths import ensure_paths  # noqa: E402

ensure_paths()

from src.core.scene import Scene  # noqa: E402

from adapters.obj_to_core import DEFAULT_HEAD_ASSET, build_core_scene_from_obj  # noqa: E402
from scene.scene import LabObject, LabScene  # noqa: E402

CubePositions = tuple[tuple[float, float, float], ...]

# Bewusst identisch zum Rigging-`demo_mesh`-Boxmuster (8 Vertices, 6 Faces).
CUBE_VERTICES: CubePositions = (
    (-1.0, -1.0, -1.0),  # 0
    (1.0, -1.0, -1.0),   # 1
    (1.0, 1.0, -1.0),    # 2
    (-1.0, 1.0, -1.0),   # 3
    (-1.0, -1.0, 1.0),   # 4
    (1.0, -1.0, 1.0),    # 5
    (1.0, 1.0, 1.0),     # 6
    (-1.0, 1.0, 1.0),    # 7
)

# Faces in CCW-Winding von außen gesehen (rechte-Hand-Normale zeigt nach
# außen) — so stimmt die Beleuchtung über die Core->Render-Normalen.
# (Verifiziert: front-normal +z, back -z, left -x, right +x, top +y, bottom -y)
CUBE_FACES: tuple[tuple[int, int, int, int], ...] = (
    (4, 5, 6, 7),  # front (z+)
    (0, 3, 2, 1),  # back  (z-)
    (0, 4, 7, 3),  # left  (x-)
    (5, 1, 2, 6),  # right (x+)
    (3, 7, 6, 2),  # top   (y+)
    (0, 1, 5, 4),  # bottom(y-)
)


def build_cube_scene() -> Scene:
    """Deterministischer Cube in `src.core` (8 Verts, 6 Quad-Faces)."""
    scene = Scene()
    mesh = scene.mesh
    vertex_ids = [mesh.add_vertex(pos) for pos in CUBE_VERTICES]
    for face in CUBE_FACES:
        mesh.add_face([vertex_ids[i] for i in face])
    return scene


def build_head_scene(obj_path: str | Path = DEFAULT_HEAD_ASSET) -> Scene:
    """Reales Head-Basemesh → `src.core.Scene` (über den OBJ-Loader)."""
    return build_core_scene_from_obj(obj_path)


def build_lab_scene(head_obj_path: str | Path = DEFAULT_HEAD_ASSET) -> LabScene:
    """Die erste Zielszene: Cube + Head Basemesh, unabhängige Selection."""
    lab = LabScene()
    cube = LabObject(
        name="Cube",
        scene=build_cube_scene(),
        base_color=(0.35, 0.55, 0.85, 1.0),
    )
    head = LabObject(
        name="Head Basemesh",
        scene=build_head_scene(head_obj_path),
        asset_path=Path(head_obj_path),
        base_color=(0.72, 0.70, 0.66, 1.0),
    )
    lab.add_object(cube)
    lab.add_object(head)
    lab.select(0)
    return lab