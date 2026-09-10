"""Polygon-Triangulierung für die reine Render-Darstellung.

Grundsatz (Integration Lab): Core = Wahrheit, Render-Darstellung = abgeleitet.
Der OBJ Loader und das `src.core.Mesh` arbeiten mit Polygon-Faces (Tris/
Quads/N-gons). Die Render-Schicht (V0.2) braucht Dreiecke. Diese Datei
trianguliert deshalb Polygon-Faces — und zwar ausschließlich an der
Core→Render-Grenze, nicht im Loader und nicht im Core.

Implementierung: konservatives Ear-Clipping für einfache Polygone
(konvex und konkav). Degenerierte/Grenzfälle fallen auf ein Fan-Triangle
zurück, damit die Render-Darstellung deterministisch bleibt.

Keine External-Dependencies (bewusst): Das Lab soll die Integrationsgrenzen
isolieren, nicht eine Polygon-Bibliothek zur Design-Entscheidung machen.
"""

from __future__ import annotations

Vec3 = tuple[float, float, float]


def _project_to_2d(boundary: list[int], positions: list[Vec3]) -> list[tuple[float, float]]:
    """Projiziert die Boundary-Punkte auf ihre Best-Fit-Ebene (2D).

    Normalenrichtung via Newell's Method (orientierungsunabhängig).
    """
    normal_x = 0.0
    normal_y = 0.0
    normal_z = 0.0
    n = len(boundary)
    for i in range(n):
        a = positions[boundary[i]]
        b = positions[boundary[(i + 1) % n]]
        normal_x += (a[1] - b[1]) * (a[2] + b[2])
        normal_y += (a[2] - b[2]) * (a[0] + b[0])
        normal_z += (a[0] - b[0]) * (a[1] + b[1])

    # Dominante Achse der Normalen → eindeutige 2D-Projektion (kein Kollaps).
    dominant = max((abs(normal_x), 0), (abs(normal_y), 1), (abs(normal_z), 2))[1]
    if dominant == 0:
        return [(p[1], p[2]) for p in (positions[i] for i in boundary)]
    if dominant == 1:
        return [(p[0], p[2]) for p in (positions[i] for i in boundary)]
    return [(p[0], p[1]) for p in (positions[i] for i in boundary)]


def _signed_area2(pts: list[tuple[float, float]]) -> float:
    """Vorzeichenbehaftete Fläche (Shoelace) eines 2D-Polygons."""
    area = 0.0
    n = len(pts)
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        area += a[0] * b[1] - b[0] * a[1]
    return 0.5 * area


def _is_inside(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], p: tuple[float, float]) -> bool:
    """Punkt-in-Dreieck-Test (Baryzentrisch via Vorzeichen), CCW-konform."""
    def _sign(u: tuple[float, float], v: tuple[float, float], w: tuple[float, float]) -> float:
        return (u[0] - w[0]) * (v[1] - w[1]) - (v[0] - w[0]) * (u[1] - w[1])

    d1 = _sign(p, a, b)
    d2 = _sign(p, b, c)
    d3 = _sign(p, c, a)
    has_neg = d1 < 0.0 or d2 < 0.0 or d3 < 0.0
    has_pos = d1 > 0.0 or d2 > 0.0 or d3 > 0.0
    return not (has_neg and has_pos)


def triangulate_polygon(
    positions: list[Vec3], boundary: list[int], _debug: bool = False
) -> list[tuple[int, int, int]]:
    """Trianguliert eine Polygon-Face (Indizes in `positions`).

    Liefert `n-2` Dreiecke für ein einfaches n-gon. Degenerierte Polygone
    (kollinear, self-intersecting) liefern ein deterministisches Fan-Fallback
    und NICHT die garantierten n-2 Dreiecke.
    """
    n = len(boundary)
    if n < 3:
        return []
    if n == 3:
        return [(boundary[0], boundary[1], boundary[2])]

    pts2d = _project_to_2d(boundary, positions)
    orientation = 1.0 if _signed_area2(pts2d) >= 0.0 else -1.0

    remaining = list(range(n))
    triangles: list[tuple[int, int, int]] = []

    # Ear-Clipping mit Wächter gegen Nicht-Terminierung bei Degeneration.
    guard = 4 * n * n
    while len(remaining) > 3 and guard > 0:
        guard -= 1
        found = False
        for i in range(len(remaining)):
            i0 = remaining[i - 1]
            i1 = remaining[i]
            i2 = remaining[(i + 1) % len(remaining)]
            a = pts2d[i0]
            b = pts2d[i1]
            c = pts2d[i2]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross * orientation <= 1e-12:
                continue  # reflex/degeneriert → kein Ohr
            # Ohr darf keine anderen Polygon-Punkte enthalten.
            contains = False
            for x in remaining:
                if x in (i0, i1, i2):
                    continue
                if _is_inside(a, b, c, pts2d[x]):
                    contains = True
                    break
            if contains:
                continue
            triangles.append((boundary[i0], boundary[i1], boundary[i2]))
            del remaining[i]
            found = True
            break
        if not found:
            break

    if len(triangles) == n - 2:
        return triangles

    # Fallback (destruktiv, aber deterministisch): Fan ab Boundary[0].
    return [(boundary[0], boundary[i], boundary[i + 1]) for i in range(1, n - 1)]