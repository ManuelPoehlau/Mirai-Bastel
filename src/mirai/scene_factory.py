"""Scene-/Mesh-Factories für die Produktions-Application.

Extrahiert aus dem Viewport-V1-Experiment (`viewport/demo_scene.py`,
`build_cube_scene`). Baut ausschließlich über die öffentliche Core-Mutation-
API (`Mesh.add_vertex`/`add_face`), genau wie ein späteres Import-System das
tun würde — deshalb liegt der Factory-Code in `mirai` und nicht im
(gefrorenen) Core.

AD-008 (2026-09-17): OBJ-Import-Konstruktion (`mesh_from_positions_and_faces`
und Konsorten) 1:1 aus `experiments/mirai_bastel_integration_lab/adapters/
obj_to_core.py` portiert und dabei bewusst in zwei Schichten aufgeteilt:

- `mesh_from_positions_and_faces`/`scene_from_positions_and_faces` — generisch,
  keine Abhängigkeit auf einen konkreten Loader oder auf `examples/`.
- `build_core_scene_from_obj` — dünner Convenience-Wrapper für den Fall
  "OBJ-Datei direkt laden"; importiert den geteilten OBJ-Loader
  (`examples/loaders/obj_loader.py`, AD-007) bewusst lokal in der Funktion,
  nicht auf Modulebene, damit `scene_factory` (und alles, was nur die
  generischen Factories braucht) ohne `examples/` auf `sys.path` importierbar
  bleibt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from core import Mesh, Scene


def create_cube(size: float = 2.0) -> Mesh:
    """Erzeugt ein neues Mesh mit einem Würfel (8 Vertices, 6 Faces)."""
    mesh = Mesh()
    s = size / 2.0
    positions = [
        (-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),  # hinten (z-)
        (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s),      # vorne (z+)
    ]
    verts = [mesh.add_vertex(p) for p in positions]

    # CCW von außen betrachtet → Außen-Normale via (b-a)×(c-a).
    faces = [
        (3, 2, 1, 0),  # hinten  → -Z
        (6, 7, 4, 5),  # vorne   → +Z
        (7, 3, 0, 4),  # links   → -X
        (2, 6, 5, 1),  # rechts  → +X
        (7, 6, 2, 3),  # oben    → +Y
        (0, 1, 5, 4),  # unten   → -Y
    ]
    for a, b, c, d in faces:
        mesh.add_face([verts[a], verts[b], verts[c], verts[d]])
    return mesh


def build_cube_scene(size: float = 2.0) -> Scene:
    """Erzeugt eine fertige Scene mit einem Würfel-Mesh."""
    scene = Scene()
    scene.mesh = create_cube(size)
    return scene


# ---------------------------------------------------------------------------
# OBJ-Import (AD-008) — generische Schicht, keine Loader-/examples-Abhängigkeit
# ---------------------------------------------------------------------------

def mesh_from_positions_and_faces(
    vertices: Sequence[tuple[float, float, float]],
    faces: Sequence[Sequence[int]],
) -> Mesh:
    """Baut ein `Mesh` aus rohen Vertex-Positionen + 0-basierten Face-Indizes.

    - Vertex-Reihenfolge bleibt exakt erhalten (`add_vertex` in
      Eingabe-Reihenfolge → deterministische Vertex-IDs).
    - Face-Boundaries bleiben Polygone (Tris/Quads/N-gons) — Triangulierung
      passiert bewusst erst im Core→Render-Adapter, nicht hier.
    """
    mesh = Mesh()
    vertex_ids = [mesh.add_vertex(position) for position in vertices]
    for face in faces:
        mesh.add_face([vertex_ids[index] for index in face])
    return mesh


def scene_from_positions_and_faces(
    vertices: Sequence[tuple[float, float, float]],
    faces: Sequence[Sequence[int]],
) -> Scene:
    """Rohe Vertex-/Face-Daten → Scene mit eigenem Mesh/Selection/History."""
    scene = Scene()
    scene.mesh = mesh_from_positions_and_faces(vertices, faces)
    return scene


def build_core_scene_from_obj(obj_path: str | Path) -> Scene:
    """OBJ-Datei → Scene (lädt über den geteilten Loader, siehe Moduldocstring).

    `examples/` muss dafür auf `sys.path` liegen (Playground/Lab/Rigging
    erledigen das bereits in ihrem jeweiligen `_paths.py`/Bootstrap).
    """
    from loaders.obj_loader import load_obj  # lokal — siehe Moduldocstring

    data = load_obj(obj_path)
    return scene_from_positions_and_faces(data.vertices, data.faces)