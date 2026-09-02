"""Viewport-Adapter: die einzige Brücke zwischen Rigging-Experiment und Viewport V1.

Architektur (Task 'Viewport V1 Integration + OBJ Asset'):

    Rigging-Experiment (Asset + Loader)  →  Mesh  →  Viewport V1

- Der Viewport sieht ausschließlich eine reguläre Scene/Mesh des Cores, den
  auch der Viewport selbst benutzt (`mirai_bastel_core` aus
  experiments/mirai_bastel_core_V1 — der gefrorene Core-V1-Referenzstand des
  Viewport-Experiments). Er weiß nicht, dass es ein Rigging-Experiment ist.
- Es wird KEIN Viewport-Code kopiert oder verändert. Dieses Modul baut die
  Szene und stellt Bounds-/Statistik-/Framing-Helfer bereit; die winzige
  Fenster-Unterklasse (Scene-Tausch + Caption-Titel) lebt im Launcher
  run_viewport.py.
- Bewusst pyglet-frei: Dieses Modul ist headless testbar.

Warum `mirai_bastel_core` und nicht `src.core`? Der Viewport V1 ist an
`mirai_bastel_core` gebunden (siehe run_all_tools.py des Viewport-Experiments).
Damit Szene, Selection, History und Tools garantiert dieselben Klassen
verwenden, baut auch dieser Adapter die Szene mit diesem Core. Die übrigen
Rigging-Module (bone/deformation/rig_controller, src.core) bleiben unberührt;
ein Angleich ist eine spätere, bewusste Entscheidung.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Bootstrap (gleiches Muster wie run_all_tools.py): Der Adapter ist aus jedem
# Kontext importierbar, ohne dass der Aufrufer sys.path setzen muss.
_EXPERIMENT_DIR = Path(__file__).resolve().parent
_EXPERIMENTS_DIR = _EXPERIMENT_DIR.parent
_REPO_ROOT = _EXPERIMENTS_DIR.parent
for _path in (
    str(_EXPERIMENT_DIR),                            # loaders/ Paket
    str(_EXPERIMENTS_DIR / "mirai_bastel_core_V1"),  # mirai_bastel_core
):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from mirai_bastel_core import Scene  # noqa: E402

from loaders.obj_loader import ObjMeshData, load_obj  # noqa: E402

# Repository-relativer Standardpfad zum Head-Basemesh-Asset.
DEFAULT_HEAD_ASSET = _EXPERIMENT_DIR / "meshes" / "head_basemesh.obj"

Bounds = tuple[tuple[float, float, float], tuple[float, float, float]]


def build_scene_from_obj(obj_path: str | Path = DEFAULT_HEAD_ASSET) -> Scene:
    """OBJ → Core-Mesh → Scene (kompatibel zum Viewport V1).

    - Vertex-Reihenfolge bleibt exakt erhalten (add_vertex in Datei-Reihenfolge).
    - Face-Boundaries bleiben Polygone (keine Triangulation); Mesh.add_face
      erzeugt/wiederverwendet Edges dedupliziert.
    """
    return build_scene_from_data(load_obj(obj_path))


def build_scene_from_data(data: ObjMeshData) -> Scene:
    """Überführt bereits geparste OBJ-Daten in eine Scene."""
    scene = Scene()
    mesh = scene.mesh
    vertex_ids = [mesh.add_vertex(position) for position in data.vertices]
    for face in data.faces:
        mesh.add_face([vertex_ids[index] for index in face])
    return scene


def mesh_bounds(mesh) -> Bounds:
    """(min_xyz, max_xyz) über alle Vertex-Positionen (nur Query-API)."""
    positions = [mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()]
    if not positions:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    zs = [p[2] for p in positions]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def mesh_center_and_radius(mesh) -> tuple[tuple[float, float, float], float]:
    """Zentrum der Bounds und Radius der umschließenden Kugel (für Framing)."""
    (min_x, min_y, min_z), (max_x, max_y, max_z) = mesh_bounds(mesh)
    center = (
        (min_x + max_x) / 2.0,
        (min_y + max_y) / 2.0,
        (min_z + max_z) / 2.0,
    )
    radius = 0.0
    for vid in mesh.all_vertex_ids():
        radius = max(radius, math.dist(mesh.vertex_position(vid), center))
    return center, radius


def face_type_counts(mesh) -> dict[str, int]:
    """Verteilung Tris / Quads / N-gons über die Face-Boundaries des Meshes."""
    counts = {"tri": 0, "quad": 0, "ngon": 0}
    for fid in mesh.all_face_ids():
        n = len(mesh.face_vertices(fid))
        if n == 3:
            counts["tri"] += 1
        elif n == 4:
            counts["quad"] += 1
        else:
            counts["ngon"] += 1
    return counts


def frame_camera_on_bounds(camera, mesh, margin: float = 1.25) -> None:
    """Richtet eine Orbit-Kamera duck-typed auf die Mesh-Bounds aus.

    Reiner View-Koncern: Das Mesh wird nicht verändert; die Kamera wird nur
    über die vorhandenen Attribute target/distance gesetzt (kompatibel zu
    viewport.camera.OrbitCamera; fov_degrees optional, Default 50°).
    Notwendig, weil der Head nicht um den Ursprung zentriert ist und die
    Viewport-Standardkamera auf (0, 0, 0) zielt.
    """
    center, radius = mesh_center_and_radius(mesh)
    fov_degrees = float(getattr(camera, "fov_degrees", 50.0))
    half_height = math.tan(math.radians(fov_degrees / 2.0))
    if half_height <= 0.0:
        distance = max(radius * 2.0, 0.5)
    else:
        distance = max((radius / half_height) * margin, 0.5)
    camera.target = center
    camera.distance = distance


def format_debug_report(asset_name: str, mesh) -> str:
    """Start-Report für den Launcher (Task §8: Asset- und Mesh-Information)."""
    (min_x, min_y, min_z), (max_x, max_y, max_z) = mesh_bounds(mesh)
    counts = face_type_counts(mesh)
    return (
        "Living Mesh Research\n"
        "--------------------\n"
        f"Asset: {asset_name}\n"
        "\n"
        f"Vertices: {len(mesh.all_vertex_ids())}\n"
        f"Edges:    {len(mesh.all_edge_ids())}\n"
        f"Faces:    {len(mesh.all_face_ids())}\n"
        f"Face types: {counts['quad']} Quads | {counts['tri']} Tris | "
        f"{counts['ngon']} N-gons\n"
        "\n"
        "Bounds:\n"
        f"X: {min_x:.6f} .. {max_x:.6f}\n"
        f"Y: {min_y:.6f} .. {max_y:.6f}\n"
        f"Z: {min_z:.6f} .. {max_z:.6f}\n"
    )
