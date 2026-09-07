"""OBJ → src.core: Überführung des OBJ-Loader-Ergebnisses in die Domain-Wahrheit.

Wiederverwendung (KEIN neuer Loader):
    experiments/rigging-skinning-morphing/loaders/obj_loader.py
    wird unverändert importiert (reiner Parser, headless, ohne Abhängigkeit
    zu Core/Viewport/pyglet). Der Loader bleibt bei seiner Aufgabe
    `OBJ -> ObjMeshData`; er bekommt KEINE Rendering-/Core-Verantwortung.

Adaption (KEINE V1-Core-Abhängigkeit):
    Die Umwandlungs-/Framing-Helfer entsprechen in Logik und Namensgebung
    dem alten `viewport_adapter.py` des Rigging-Experiments
    (`build_scene_from_data`, `mesh_bounds`, `mesh_center_and_radius`,
    `face_type_counts`, `frame_camera_on_bounds`), zielen aber auf
    `src.core` statt auf den eingefrorenen V1-Core
    (`mirai_bastel_core`). Der V1-Adapter wird deshalb bewusst NICHT
    importiert — er würde die V1-Abhängigkeit wieder hereintragen.
"""

from __future__ import annotations

import math
from pathlib import Path

from _paths import DEFAULT_HEAD_ASSET, ensure_paths  # noqa: E402

ensure_paths()

from src.core.mesh import Mesh  # noqa: E402
from src.core.scene import Scene  # noqa: E402

from loaders.obj_loader import ObjLoadError, ObjMeshData, load_obj  # noqa: E402

Bounds = tuple[tuple[float, float, float], tuple[float, float, float]]


# --------------------------------------------------------------------------
# OBJ -> ObjMeshData -> src.core
# --------------------------------------------------------------------------

def obj_data_to_core_mesh(data: ObjMeshData) -> Mesh:
    """Überführt bereits geparste OBJ-Daten in ein `src.core.Mesh`.

    - Vertex-Reihenfolge bleibt exakt erhalten (`add_vertex` in
      Datei-Reihenfolge → deterministische Reihenfolge der Vertex-IDs).
    - Face-Boundaries bleiben Polygone (Tris/Quads/N-gons) — die
      Triangulierung passiert bewusst erst im Core→Render-Adapter
      (Render-Darstellung), nicht hier.
    """
    mesh = Mesh()
    vertex_ids = [mesh.add_vertex(position) for position in data.vertices]
    for face in data.faces:
        mesh.add_face([vertex_ids[index] for index in face])
    return mesh


def obj_data_to_core_scene(data: ObjMeshData) -> Scene:
    """ObjektMeshData → Scene mit eigenem Mesh/Selection/History."""
    scene = Scene()
    mesh = obj_data_to_core_mesh(data)
    scene.mesh = mesh
    return scene


def build_core_scene_from_obj(obj_path: str | Path = DEFAULT_HEAD_ASSET) -> Scene:
    """OBJ-Datei → ObjMeshData → src.core.Scene (einschließlich Loader)."""
    return obj_data_to_core_scene(load_obj(obj_path))


# --------------------------------------------------------------------------
# Bounds / Framing / Statistik (Logik adaptiert aus dem V1-viewport_adapter,
# gegen die src.core-Query-API)
# --------------------------------------------------------------------------

def mesh_bounds(mesh: Mesh) -> Bounds:
    """(min_xyz, max_xyz) über alle Vertex-Positionen (nur Query-API)."""
    positions = [mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()]
    if not positions:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    zs = [p[2] for p in positions]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def mesh_center_and_radius(mesh: Mesh) -> tuple[tuple[float, float, float], float]:
    """Zentrum der Bounds + Radius der umschließenden Kugel (für Framing)."""
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


def face_type_counts(mesh: Mesh) -> dict[str, int]:
    """Verteilung Tris / Quads / N-gons über die Face-Boundaries."""
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


def frame_camera_on_bounds(camera, mesh: Mesh, margin: float = 1.25) -> None:
    """Richtet eine duck-typed Orbit-Kamera auf die Mesh-Bounds aus.

    Reiner View-Kontext: Das Mesh wird nicht verändert; die Kamera wird nur
    über `target`/`distance` gesetzt (kompatibel zur V0.2 `OrbitCamera` und
    zur Lab-Kamera; `fov_degrees` optional, Default 50°).
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


def mesh_debug_report(name: str, mesh: Mesh) -> str:
    """Kompakter Asset-/Mesh-Report (für Start-Ausgabe und README)."""
    (min_x, min_y, min_z), (max_x, max_y, max_z) = mesh_bounds(mesh)
    counts = face_type_counts(mesh)
    return (
        f"{name}\n"
        f"  Vertices : {len(mesh.all_vertex_ids())}\n"
        f"  Edges    : {len(mesh.all_edge_ids())}\n"
        f"  Faces    : {len(mesh.all_face_ids())}\n"
        f"  Face-Typen: {counts['tri']} Tris | {counts['quad']} Quads | "
        f"{counts['ngon']} N-gons\n"
        f"  Bounds   : X {min_x:.3f}..{max_x:.3f} | "
        f"Y {min_y:.3f}..{max_y:.3f} | Z {min_z:.3f}..{max_z:.3f}\n"
    )