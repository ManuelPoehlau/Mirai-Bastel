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
  `vn` wird verworfen.
- UVs (AD-026, 2026-10-29): `vt`-Zeilen (u, v; ein drittes w verworfen) und
  die `vt`-Indizes der Faces. Eine Face, deren Tokens nicht alle ein `vt`
  tragen, hat keine UVs (`face_texcoords[i] is None`).
- `mtllib` / `usemtl`: Dateinamen und die benutzten Materialnamen (in
  Reihenfolge der ersten Nutzung); `find_texture()` sucht damit die Textur
  (`map_Kd`) einer OBJ-Datei.
- Kommentare (`#`), Leerzeilen sowie alle übrigen OBJ-Records (o, g, s, l,
  ...) werden ignoriert.

Bewusst NICHT:

- KEINE Triangulation: Quad- und N-gon-Faces bleiben exakt so erhalten, wie
  sie in der Datei stehen. Die Core-Mesh-Struktur unterstützt Polygone
  direkt (Face-Boundary als geordnete Vertex-Liste, AD-002).
- Keine Edge-Erzeugung: Edges entstehen beim Einbau ins Core-Mesh aus den
  Face-Boundaries (Mesh.add_face erzeugt/wiederverwendet Edges dedupliziert
  über das interne Edge-Lookup).
- Keine Normalen, keine Achsen-Konvertierung, keine V-Spiegelung der UVs:
  Die Datei-Koordinaten werden 1:1 übernommen.
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
    # UVs (AD-026): `vt`-Werte (u, v) und je Face die 0-basierten `vt`-Indizes ihrer Ecken
    # (None = die Face hat keine UVs). Leer, wenn die Datei keine `vt` hat.
    texcoords: tuple[tuple[float, float], ...] = ()
    face_texcoords: tuple[tuple[int, ...] | None, ...] = ()
    # `mtllib`-Dateinamen und benutzte Materialnamen (erste Nutzung zuerst).
    mtllibs: tuple[str, ...] = ()
    materials: tuple[str, ...] = ()

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def face_count(self) -> int:
        return len(self.faces)

    @property
    def has_uvs(self) -> bool:
        return any(t is not None for t in self.face_texcoords)

    def face_uvs(self) -> list[tuple[tuple[float, float], ...] | None]:
        """Je Face ihre UVs als (u, v) je Ecke (None = keine), parallel zu `faces`."""
        if not self.face_texcoords:
            return [None] * len(self.faces)
        coords = self.texcoords
        return [None if t is None else tuple(coords[i] for i in t) for t in self.face_texcoords]

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


def _parse_texcoord_index(token: str, texcoord_count: int, line_no: int) -> int | None:
    """Der `vt`-Teil eines Face-Tokens als 0-basierter Index; None ohne `vt` (`v`, `v//vn`)."""
    parts = token.split("/")
    if len(parts) < 2 or not parts[1]:
        return None
    try:
        raw = int(parts[1])
    except ValueError as exc:
        raise ObjLoadError(f"Zeile {line_no}: ungültiger UV-Index {token!r}.") from exc
    index = texcoord_count + raw if raw < 0 else raw - 1
    if raw == 0 or not 0 <= index < texcoord_count:
        raise ObjLoadError(
            f"Zeile {line_no}: Face-Referenz {token!r} zeigt auf unbekannte UV "
            f"(Index {index} bei {texcoord_count} UVs)."
        )
    return index


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
    texcoords: list[tuple[float, float]] = []
    face_texcoords: list[tuple[int, ...] | None] = []
    mtllibs: list[str] = []
    materials: list[str] = []
    current_material: str | None = None
    material_used = False

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
            uv_indices = [_parse_texcoord_index(token, len(texcoords), line_no) for token in args]
            face_texcoords.append(None if None in uv_indices else tuple(uv_indices))
            if current_material is not None and not material_used:
                material_used = True
                if current_material not in materials:
                    materials.append(current_material)
        elif key == "vt":
            if not args:
                raise ObjLoadError(f"Zeile {line_no}: 'vt' benötigt mindestens 1 Koordinate.")
            values = _parse_floats(args[:2], line_no, "vt")
            texcoords.append((values[0], values[1] if len(values) > 1 else 0.0))
        elif key == "mtllib" and args:
            mtllibs.append(line.split(None, 1)[1].strip())
        elif key == "usemtl" and args:
            current_material = line.split(None, 1)[1].strip()
            material_used = False
        # Alle übrigen Records (vn, o, g, s, l, ...) werden bewusst ignoriert.

    if not any(t is not None for t in face_texcoords):
        texcoords, face_texcoords = [], []
    return ObjMeshData(
        vertices=tuple(vertices),
        faces=tuple(faces),
        texcoords=tuple(texcoords),
        face_texcoords=tuple(face_texcoords),
        mtllibs=tuple(mtllibs),
        materials=tuple(materials),
    )


def load_obj(path: str | Path) -> ObjMeshData:
    """Liest eine OBJ-Datei ein und parst sie (siehe parse_obj)."""
    obj_path = Path(path)
    if not obj_path.is_file():
        raise ObjLoadError(f"OBJ-Datei nicht gefunden: {obj_path}")
    return parse_obj(obj_path.read_text(encoding="utf-8"))


#: Bildformate, die `find_texture` neben der OBJ-Datei sucht (Reihenfolge = Vorrang).
TEXTURE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".tga", ".tif", ".tiff")

# map_Kd-Optionen mit ihrer Argumentzahl (MTL-Spezifikation); der Rest der Zeile ist der Dateiname.
_MAP_OPTIONS = {
    "-blendu": 1, "-blendv": 1, "-bm": 1, "-boost": 1, "-cc": 1, "-clamp": 1, "-imfchan": 1,
    "-mm": 2, "-o": 3, "-s": 3, "-t": 3, "-texres": 1, "-type": 1,
}


def _map_file_name(rest: str) -> str:
    tokens = rest.split()
    i = 0
    while i < len(tokens) and tokens[i].lower() in _MAP_OPTIONS:
        count = _MAP_OPTIONS[tokens[i].lower()]
        i += 1
        # -o/-s/-t take 1-3 numbers: skip only the ones that are numbers
        for _ in range(count):
            if i < len(tokens) and (count == 1 or _is_number(tokens[i])):
                i += 1
    return " ".join(tokens[i:])


def _is_number(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


def parse_mtl_textures(text: str) -> dict[str, str]:
    """Material name -> `map_Kd`-Dateiname (wie in der Datei geschrieben) einer MTL-Datei."""
    out: dict[str, str] = {}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, rest = stripped.partition(" ")
        if key == "newmtl":
            current = rest.strip()
        elif key.lower() == "map_kd" and current is not None and current not in out:
            name = _map_file_name(rest)
            if name:
                out[current] = name
    return out


def _resolve(name: str, base: Path) -> Path | None:
    """Ein Dateiname aus einer MTL-Datei: relativ zu `base`, absolut, oder (Pfad eines anderen
    Rechners, z. B. von ZBrush geschrieben) nur sein Dateiname in `base`."""
    candidate = Path(name.replace("\\", "/"))
    for path in (candidate if candidate.is_absolute() else base / candidate, base / candidate.name):
        if path.is_file():
            return path
    return None


def find_texture(obj_path: str | Path, data: ObjMeshData) -> Path | None:
    """Die Textur einer OBJ-Datei (AD-026): `map_Kd` des ersten benutzten Materials (sonst des ersten
    Materials mit einer) aus den `mtllib`-Dateien; ohne Treffer ein Bild gleichen Namens neben der
    OBJ-Datei (`kopf.obj` -> `kopf.png`, ...). None = keine gefunden."""
    obj_path = Path(obj_path)
    base = obj_path.parent
    textures: dict[str, str] = {}
    for lib in data.mtllibs:
        mtl = _resolve(lib, base)
        if mtl is None:
            continue
        try:
            text = mtl.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for material, name in parse_mtl_textures(text).items():
            textures.setdefault(material, name)
    ordered = [textures[m] for m in data.materials if m in textures] + list(textures.values())
    for name in ordered:
        path = _resolve(name, base)
        if path is not None:
            return path
    if base.is_dir():
        by_suffix = {
            p.suffix.lower(): p for p in base.iterdir()
            if p.is_file() and p.stem.lower() == obj_path.stem.lower() and p.suffix.lower() in TEXTURE_SUFFIXES
        }
        for suffix in TEXTURE_SUFFIXES:
            if suffix in by_suffix:
                return by_suffix[suffix]
    return None
