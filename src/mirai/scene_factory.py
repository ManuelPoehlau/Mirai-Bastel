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

import math
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


# ---------------------------------------------------------------------------
# Add Mesh: Primitive (Track A1, 2026-10-23, `PROVISIONAL`)
#
# Alle über `Mesh.add_vertex`/`add_face`, Y oben (wie der Würfel), Außen-Normale per CCW von außen.
# Echte, geschlossene (Plane: offene) Polygon-Meshes, keine Sonderstruktur - sie sind danach
# gewöhnliche Objekte. Kugel und Zylinder haben die Blender-Defaults (Referenz: "Established software"),
# die Plane ist eine eigene Entscheidung (ein Eintrag, 4x4-Raster).
# ---------------------------------------------------------------------------

#: Plane/Grid: ein Eintrag, ein 4x4-Raster (Loop-/Soft-Werkzeuge haben sofort etwas zu greifen);
#: `segments=1` ergibt das einzelne Quad.
PLANE_SEGMENTS = 4
#: Kugel: 32 Segmente x 16 Ringe (Blender "UV Sphere"), Radius 1 - der Würfel (Kante 2) ist ihr
#: Umwürfel. Pole auf der Y-Achse (Dreiecksfächer, wie dort).
SPHERE_SEGMENTS = 32
SPHERE_RINGS = 16
#: Zylinder: 32 Seiten, Radius 1, Höhe 2 entlang Y, Deckel als N-Gon (Blender-Default).
CYLINDER_VERTICES = 32


def create_plane(size: float = 2.0, segments: int = PLANE_SEGMENTS) -> Mesh:
    """Raster aus `segments` x `segments` Quads in der XZ-Ebene (y = 0), Normale +Y."""
    if segments < 1:
        raise ValueError(f"segments muss >= 1 sein: {segments!r}")
    mesh = Mesh()
    half = size / 2.0
    step = size / segments
    grid = [
        [mesh.add_vertex((-half + i * step, 0.0, -half + j * step)) for j in range(segments + 1)]
        for i in range(segments + 1)
    ]
    for i in range(segments):
        for j in range(segments):
            # (x0,z0) (x0,z1) (x1,z1) (x1,z0): (b-a)x(c-a) zeigt nach +Y.
            mesh.add_face([grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]])
    return mesh


def create_sphere(
    radius: float = 1.0, segments: int = SPHERE_SEGMENTS, rings: int = SPHERE_RINGS
) -> Mesh:
    """UV-Kugel um den Ursprung, Pole (0, +-radius, 0): Dreiecksfächer an den Polen, Quads dazwischen."""
    if segments < 3 or rings < 2:
        raise ValueError(f"UV-Kugel braucht segments >= 3 und rings >= 2: {segments!r}, {rings!r}")
    mesh = Mesh()
    top = mesh.add_vertex((0.0, radius, 0.0))
    bottom = mesh.add_vertex((0.0, -radius, 0.0))
    ring_ids: list[list] = []
    for r in range(1, rings):
        polar = math.pi * r / rings
        y, ring_radius = radius * math.cos(polar), radius * math.sin(polar)
        ring_ids.append(
            [
                mesh.add_vertex(
                    (
                        ring_radius * math.cos(2.0 * math.pi * s / segments),
                        y,
                        ring_radius * math.sin(2.0 * math.pi * s / segments),
                    )
                )
                for s in range(segments)
            ]
        )
    # Winkel läuft von +X nach +Z, von oben (+Y) gesehen also im Uhrzeigersinn: die Reihenfolgen
    # unten sind so gewählt, dass die Außen-Normale (b-a)x(c-a) nach außen zeigt.
    for s in range(segments):
        n = (s + 1) % segments
        mesh.add_face([top, ring_ids[0][n], ring_ids[0][s]])
        mesh.add_face([bottom, ring_ids[-1][s], ring_ids[-1][n]])
    for r in range(rings - 2):
        upper, lower = ring_ids[r], ring_ids[r + 1]
        for s in range(segments):
            n = (s + 1) % segments
            mesh.add_face([upper[s], upper[n], lower[n], lower[s]])
    return mesh


def create_cylinder(
    radius: float = 1.0, depth: float = 2.0, vertices: int = CYLINDER_VERTICES
) -> Mesh:
    """Zylinder um die Y-Achse (y = +-depth/2), Mantel aus Quads, Deckel als je ein N-Gon."""
    if vertices < 3:
        raise ValueError(f"vertices muss >= 3 sein: {vertices!r}")
    mesh = Mesh()
    half = depth / 2.0
    ring = [
        (radius * math.cos(2.0 * math.pi * s / vertices), radius * math.sin(2.0 * math.pi * s / vertices))
        for s in range(vertices)
    ]
    top = [mesh.add_vertex((x, half, z)) for x, z in ring]
    bottom = [mesh.add_vertex((x, -half, z)) for x, z in ring]
    for s in range(vertices):
        n = (s + 1) % vertices
        mesh.add_face([top[s], top[n], bottom[n], bottom[s]])
    mesh.add_face(list(reversed(top)))  # +Y
    mesh.add_face(bottom)               # -Y
    return mesh


#: Name -> Factory der Add-Mesh-Einträge, in Menü-Reihenfolge (Track A1).
PRIMITIVES = {
    "plane": create_plane,
    "cube": create_cube,
    "sphere": create_sphere,
    "cylinder": create_cylinder,
}


def primitive_names() -> tuple[str, ...]:
    return tuple(PRIMITIVES)


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
    face_uvs: Sequence | None = None,
) -> Mesh:
    """Baut ein `Mesh` aus rohen Vertex-Positionen + 0-basierten Face-Indizes.

    - Vertex-Reihenfolge bleibt exakt erhalten (`add_vertex` in
      Eingabe-Reihenfolge → deterministische Vertex-IDs).
    - Face-Boundaries bleiben Polygone (Tris/Quads/N-gons) — Triangulierung
      passiert bewusst erst im Core→Render-Adapter, nicht hier.
    - `face_uvs` (AD-026): parallel zu `faces` je Face ein (u, v) je Ecke oder None; eine Face
      ohne UVs bekommt keine (nichts wird aus Nachbarn abgeleitet).
    """
    mesh = Mesh()
    vertex_ids = [mesh.add_vertex(position) for position in vertices]
    if face_uvs is None:
        for face in faces:
            mesh.add_face([vertex_ids[index] for index in face])
        return mesh
    for face, uvs in zip(faces, face_uvs):
        mesh.add_face([vertex_ids[index] for index in face], uvs, infer_uvs=False)
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
    scene = Scene()
    scene.mesh = mesh_from_obj_data(data)
    return scene


def mesh_from_obj_data(data) -> Mesh:
    """Mesh aus einem geparsten OBJ (`loaders.obj_loader.ObjMeshData`), mit seinen UVs (AD-026)."""
    return mesh_from_positions_and_faces(data.vertices, data.faces, data.face_uvs() if data.has_uvs else None)