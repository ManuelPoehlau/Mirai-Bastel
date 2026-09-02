"""Minimaler OBJ-Loader für das Rigging/Skinning/Morphing-Experiment.

Bewusst experimentell und bewusst klein: Der Loader ist ein reiner Parser
ohne Abhängigkeit zu Core, Viewport oder pyglet und damit headless testbar.
Die Überführung in das Core-Mesh passiert im Viewport-Adapter
(viewport_adapter.build_scene_from_obj).

Unterstützt (Task-Scope):

- `v`-Zeilen: Vertex-Positionen; die Reihenfolge bleibt exakt erhalten.
- `f`-Zeilen: Face-Boundaries. OBJ-1-basierte Indizes werden auf 0-basierte
  abgebildet; negative Indizes (relativ von hinten, gültiges OBJ) werden
  unterstützt.
- Face-Token-Formen `v`, `v/vt`, `v/vt/vn` und `v//vn` werden toleriert;
  `vt`/`vn` werden verworfen (V1: keine UVs/Normalen im Core-Mesh).
- Kommentare (`#`), Leerzeilen sowie alle übrigen OBJ-Records (mtllib,
  usemtl, o, g, s, l, ...) werden ignoriert.

Bewusst NICHT:

- KEINE Triangulation: Quad- und N-gon-Faces bleiben exakt so erhalten, wie
  sie in der Datei stehen. Die Core-Mesh-Struktur unterstützt Polygone
  direkt (Face-Boundary als geordnete Vertex-Liste, AD-002).
- Keine Edge-Erzeugung: Edges entstehen beim Einbau ins Core-Mesh aus den
  Face-Boundaries (Mesh.add_face erzeugt/wiederverwendet Edges dedupliziert
  über das interne Edge-Lookup).
- Kein Material-/UV-/Normalen-Mapping, keine Achsen-Konvertierung: Die
  Datei-Koordinaten werden 1:1 übernommen.
- V wird vor F erwartet (Standard bei Exportern); Faces, die auf noch nicht
  gelistete Vertices zeigen, sind ein bewusst nicht unterstützter Grenzfall
  und erzeugen einen klaren ObjLoadError statt stiller Datenverluste.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

Position = tuple[float, float, float]


class ObjLoadError(ValueError):
    """Fehler beim Parsen einer OBJ-Datei (mit Zeilenangabe)."""


@dataclass(frozen=True)
class ObjMeshData:
    """Geparster OBJ-Inhalt (0-basiert, Polygone unverändert)."""

    # Vertex-Positionen in der Reihenfolge der `v`-Zeilen der Datei.
    vertices: tuple[Position, ...]
    # Face-Boundaries als 0-basierte Vertex-Indizes in Datei-Reihenfolge.
    faces: tuple[tuple[int, ...], ...]

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def face_count(self) -> int:
        return len(self.faces)

    def face_type_counts(self) -> dict[str, int]:
        """Verteilung Tris / Quads / N-gons über die Face-Boundaries."""
        counts = {"tri": 0, "quad": 0, "ngon": 0}
        for face in self.faces:
            if len(face) == 3:
                counts["tri"] += 1
            elif len(face) == 4:
                counts["quad"] += 1
            else:
                counts["ngon"] += 1
        return counts


def _parse_floats(tokens: list[str], line_no: int, record: str) -> list[float]:
    try:
        return [float(token) for token in tokens]
    except ValueError as exc:
        raise ObjLoadError(
            f"Zeile {line_no}: ungültige Zahl in {record}-Record."
        ) from exc


def _parse_face_index(token: str, vertex_count: int, line_no: int) -> int:
    """Ein Face-Referenz-Token (`v`, `v/vt` oder `v/vt/vn`) → 0-basierter Index.

    OBJ-Indices sind 1-basiert; negative Werte zählen relativ von hinten.
    `vt`/`vn`-Anteile nach dem ersten `/` werden verworfen.
    """
    vertex_part = token.split("/", 1)[0]
    if not vertex_part:
        raise ObjLoadError(
            f"Zeile {line_no}: leere Vertex-Referenz in Face ({token!r})."
        )
    try:
        raw = int(vertex_part)
    except ValueError as exc:
        raise ObjLoadError(
            f"Zeile {line_no}: ungültiger Face-Index {token!r}."
        ) from exc
    if raw == 0:
        raise ObjLoadError(
            f"Zeile {line_no}: Face-Index 0 ist ungültig (OBJ ist 1-basiert)."
        )
    index = vertex_count + raw if raw < 0 else raw - 1
    if not 0 <= index < vertex_count:
        raise ObjLoadError(
            f"Zeile {line_no}: Face-Referenz {token!r} zeigt auf unbekanntes "
            f"Vertex (Index {index} bei {vertex_count} Vertices)."
        )
    return index


def parse_obj(text: str) -> ObjMeshData:
    """Parst OBJ-Text (siehe Modul-Docstring für den unterstützten Umfang)."""
    vertices: list[Position] = []
    faces: list[tuple[int, ...]] = []

    for line_no, line in enumerate(text.splitlines(), start=1):
        tokens = line.split()
        if not tokens or tokens[0].startswith("#"):
            continue
        key, args = tokens[0], tokens[1:]

        if key == "v":
            if len(args) < 3:
                raise ObjLoadError(
                    f"Zeile {line_no}: 'v' benötigt mindestens 3 Koordinaten."
                )
            x, y, z = _parse_floats(args[:3], line_no, "v")
            vertices.append((x, y, z))
        elif key == "f":
            if len(args) < 3:
                raise ObjLoadError(
                    f"Zeile {line_no}: Face mit {len(args)} Referenzen kann im "
                    "Core-Mesh nicht abgebildet werden (mindestens 3 nötig)."
                )
            faces.append(
                tuple(_parse_face_index(token, len(vertices), line_no) for token in args)
            )
        # Alle übrigen Records (vt, vn, mtllib, usemtl, o, g, s, l, ...)
        # werden bewusst ignoriert.

    return ObjMeshData(vertices=tuple(vertices), faces=tuple(faces))


def load_obj(path: str | Path) -> ObjMeshData:
    """Liest eine OBJ-Datei ein und parst sie (siehe parse_obj)."""
    obj_path = Path(path)
    if not obj_path.is_file():
        raise ObjLoadError(f"OBJ-Datei nicht gefunden: {obj_path}")
    return parse_obj(obj_path.read_text(encoding="utf-8"))
