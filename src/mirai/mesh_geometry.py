"""Mesh-Geometrie-Abfragen für die Produktions-Application (AD-008).

Herkunft (History Awareness, AGENTS.md M1): Diese Funktionen sind 1:1 aus
`experiments/mirai_bastel_integration_lab/adapters/obj_to_core.py` portiert
— dort waren sie bereits vollständig gegen `src.core`s öffentliche Query-API
implementiert und über `experiments/mirai_bastel_integration_lab/tests/
test_obj_to_core.py` gegen das echte Head-Basemesh verifiziert. Diese Datei
verändert an der Logik nichts, nur den Ort (Playground und Rigging hatten
sie zuvor unabhängig voneinander dupliziert — siehe
`docs/FINAL_AUDIT _shared_Infrastructure.md` F-3/F-4).

Reine Queries: Nichts hier verändert ein `Mesh`.
"""

from __future__ import annotations

import math

from core import Mesh

Position = tuple[float, float, float]
Bounds = tuple[Position, Position]


def mesh_bounds(mesh: Mesh) -> Bounds:
    """(min_xyz, max_xyz) über alle Vertex-Positionen (nur Query-API)."""
    positions = [mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()]
    if not positions:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    zs = [p[2] for p in positions]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def mesh_center_and_radius(mesh: Mesh) -> tuple[Position, float]:
    """Zentrum der Bounds + Radius der umschließenden Kugel (für Kamera-Framing)."""
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
