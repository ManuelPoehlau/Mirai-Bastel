"""Tests der geteilten OBJ-Asset-Registratur (`examples/loaders/assets.py`).

Konvention wie in `test_obj_loader.py` dieses Experiments: sys.path-Bootstrap
statt Paket-Imports, Klassen-Gruppierung, pytest.

`test_obj_loader.py` prüft den Parser und das Kopf-Asset; hier steht die
Registratur selbst plus der Ground-Truth-Stand der am 2026-09-24
hinzugekommenen Assets (`Man_With_Shoes_basemesh.obj`, `SubD_Cube.obj`) —
also die Frage: Lädt der Obj-Loader sie, und was steht wirklich in den Dateien?

Die Zahlen sind nicht geschätzt, sondern aus einem Lauf über die echten
Dateien abgeleitet und hier als Regression festgeschrieben.
"""

import sys
from collections import Counter
from pathlib import Path

# examples/ (geteilter Loader + Assets, AD-007) und Experiment-Ordner in den Pfad:
_EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _EXPERIMENT_DIR.parent.parent / "examples"
for _path in (str(_EXAMPLES_DIR), str(_EXPERIMENT_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import pytest

from loaders.assets import (
    ASSETS_DIR,
    asset_names,
    asset_path,
    get_asset,
    load_asset,
)
from loaders.obj_loader import load_obj


def _edge_valences(faces) -> Counter:
    """Häufigkeit jedes ungerichteten Vertex-Paares über alle Face-Boundaries."""
    counts: Counter = Counter()
    for face in faces:
        for index, vertex in enumerate(face):
            other = face[(index + 1) % len(face)]
            counts[(min(vertex, other), max(vertex, other))] += 1
    return counts


def _bounds(vertices):
    """(min, max) je Achse über alle Vertex-Positionen."""
    axes = [[vertex[axis] for vertex in vertices] for axis in range(3)]
    return tuple((min(axis), max(axis)) for axis in axes)


def _face_lines(asset_name: str) -> list[str]:
    """Alle `f`-Zeilen einer Asset-Datei (für Token-Form-Prüfungen)."""
    lines = asset_path(asset_name).read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line.split() and line.split()[0] == "f"]


# =====================================================================
# Registratur: alles in examples/meshes ist über den Obj-Loader erreichbar
# =====================================================================

class TestAssetRegistry:
    def test_registry_covers_all_shared_meshes(self):
        assert asset_names() == (
            "head_basemesh",
            "man_with_shoes_basemesh",
            "subd_cube",
        )

    def test_every_registered_asset_exists_on_disk(self):
        for name in asset_names():
            assert asset_path(name).is_file(), f"{name} fehlt in examples/meshes/"

    def test_registered_paths_point_into_examples_meshes(self):
        for name in asset_names():
            path = asset_path(name)
            assert path.parent == ASSETS_DIR
            assert path.suffix == ".obj"

    def test_no_unregistered_obj_file_in_examples_meshes(self):
        # Gegenrichtung: eine neue .obj-Datei ohne Registry-Eintrag wäre über
        # den Loader nur per hartkodiertem Pfad erreichbar — genau das soll
        # die Registratur verhindern.
        on_disk = {path.name for path in ASSETS_DIR.glob("*.obj")}
        registered = {asset_path(name).name for name in asset_names()}
        assert on_disk == registered

    def test_every_registered_asset_loads_through_the_obj_loader(self):
        for name in asset_names():
            data = load_asset(name)
            assert data.vertex_count > 0
            assert data.face_count > 0

    def test_load_asset_matches_direct_loader_call(self):
        for name in asset_names():
            asset = get_asset(name)
            assert asset.load() == load_obj(asset.path)

    def test_unknown_asset_name_fails_loudly(self):
        with pytest.raises(KeyError):
            get_asset("gibt_es_nicht")
        with pytest.raises(KeyError):
            load_asset("gibt_es_nicht")

    def test_unknown_asset_message_lists_registered_names(self):
        with pytest.raises(KeyError) as excinfo:
            get_asset("gibt_es_nicht")
        message = str(excinfo.value)
        for name in asset_names():
            assert name in message


# =====================================================================
# Ground truth der neuen Assets (2026-09-24 in examples/meshes/)
# =====================================================================

class TestManWithShoesBasemeshAsset:
    def test_loads_with_expected_counts(self):
        data = load_asset("man_with_shoes_basemesh")
        assert data.vertex_count == 928
        assert data.face_count == 926

    def test_is_all_quads(self):
        data = load_asset("man_with_shoes_basemesh")
        assert data.face_type_counts() == {"tri": 0, "quad": 926, "ngon": 0}

    def test_is_closed_quad_surface(self):
        # Jede Edge wird von genau 2 Faces genutzt; Euler-Charakteristik 2
        # (geschlossene, zusammenhängende Fläche ohne Löcher).
        data = load_asset("man_with_shoes_basemesh")
        valences = _edge_valences(data.faces)
        assert len(valences) == 1852
        assert set(valences.values()) == {2}
        assert data.vertex_count - len(valences) + data.face_count == 2

    def test_uses_every_vertex(self):
        data = load_asset("man_with_shoes_basemesh")
        referenced = {index for face in data.faces for index in face}
        assert len(referenced) == data.vertex_count

    def test_bounds_match_the_file(self):
        bounds = _bounds(load_asset("man_with_shoes_basemesh").vertices)
        assert bounds[0] == pytest.approx((-0.735936, 0.735936))
        assert bounds[1] == pytest.approx((0.0, 1.8796))
        assert bounds[2] == pytest.approx((-0.178026, 0.178026))

    def test_face_tokens_are_v_vt_vn(self):
        face_lines = _face_lines("man_with_shoes_basemesh")
        assert len(face_lines) == 926
        assert all(len(line.split()) == 5 for line in face_lines)
        assert all("/" in token for line in face_lines for token in line.split()[1:])


class TestSubDCubeAsset:
    def test_loads_with_expected_counts(self):
        data = load_asset("subd_cube")
        assert data.vertex_count == 26
        assert data.face_count == 24

    def test_is_all_quads(self):
        data = load_asset("subd_cube")
        assert data.face_type_counts() == {"tri": 0, "quad": 24, "ngon": 0}

    def test_is_closed_quad_surface(self):
        data = load_asset("subd_cube")
        valences = _edge_valences(data.faces)
        assert len(valences) == 48
        assert set(valences.values()) == {2}
        assert data.vertex_count - len(valences) + data.face_count == 2

    def test_control_cube_corners_sit_inside_the_subdivided_surface(self):
        # Unterteilungsmuster (6 Flächen × 4 Quads): die 8 ursprünglichen
        # Würfelecken liegen als innere Vertices bei ±0,277778, außen liegen die
        # Kanten-/Flächenpunkte (±0,5 / 0,0 / 1,0).
        inner = [
            vertex
            for vertex in load_asset("subd_cube").vertices
            if abs(vertex[0]) == pytest.approx(0.277778)
            and abs(vertex[2]) == pytest.approx(0.277778)
            and vertex[1] in (pytest.approx(0.222222), pytest.approx(0.777778))
        ]
        assert len(inner) == 8

    def test_bounds_match_the_file(self):
        bounds = _bounds(load_asset("subd_cube").vertices)
        assert bounds[0] == pytest.approx((-0.5, 0.5))
        assert bounds[1] == pytest.approx((0.0, 1.0))
        assert bounds[2] == pytest.approx((-0.5, 0.5))

    def test_face_tokens_are_v_vt_vn(self):
        face_lines = _face_lines("subd_cube")
        assert len(face_lines) == 24
        assert all(len(line.split()) == 5 for line in face_lines)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
