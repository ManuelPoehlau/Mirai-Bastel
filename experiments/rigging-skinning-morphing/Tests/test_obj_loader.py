"""Tests für den experimentellen OBJ-Loader (reine Parser-Domäne, headless).

Konvention wie in den vorhandenen Tests dieses Experiments: sys.path-
Bootstrap statt Paket-Imports, Klassen-Gruppierung, pytest.
"""

import sys
from pathlib import Path

# Experiment-Ordner in den Pfad (Konvention wie in den vorhandenen Tests):
_EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENT_DIR))

import pytest

from loaders.obj_loader import ObjLoadError, load_obj, parse_obj

_HEAD_ASSET = _EXPERIMENT_DIR / "meshes" / "head_basemesh.obj"

SIMPLE_QUAD = "\n".join(
    [
        "# Kommentarzeile",
        "",
        "mtllib head_basemesh.mtl",
        "o head_basemesh",
        "v 0.0 0.0 0.0",
        "v 1.0 0.0 0.0",
        "v 1.0 1.0 0.0",
        "v 0.0 1.0 0.0",
        "usemtl gold",
        "f 1/1/1 2/2/2 3/3/3 4/4/4",
    ]
)


# =====================================================================
# Parsing: Reihenfolge, Polygon-Erhalt, Toleranz
# =====================================================================

class TestObjParsing:
    def test_vertices_preserve_file_order(self):
        data = parse_obj(SIMPLE_QUAD)
        assert data.vertices == (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        )

    def test_face_indices_are_zero_based(self):
        data = parse_obj(SIMPLE_QUAD)
        assert data.faces == ((0, 1, 2, 3),)

    def test_faces_stay_polygons_no_triangulation(self):
        text = (
            "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nv 0.5 1.5 0\n"
            "f 1 2 3 4 5"
        )
        data = parse_obj(text)
        assert data.faces == ((0, 1, 2, 3, 4),)

    def test_mixed_face_token_forms(self):
        # v, v/vt, v/vt/vn und v//vn in einer Face; vt/vn werden verworfen.
        text = "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2/1 3/2/3 4//4"
        data = parse_obj(text)
        assert data.faces == ((0, 1, 2, 3),)

    def test_negative_indices_are_relative(self):
        text = "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf -4 -3 -2 -1"
        data = parse_obj(text)
        assert data.faces == ((0, 1, 2, 3),)

    def test_comments_and_non_geometry_records_ignored(self):
        data = parse_obj(SIMPLE_QUAD)
        assert data.vertex_count == 4
        assert data.face_count == 1

    def test_vt_vn_records_are_ignored(self):
        text = (
            "vt 0 0\nvn 0 0 1\n"
            "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
            "f 1/1/1 2/2/2 3/3/3"
        )
        data = parse_obj(text)
        assert data.vertex_count == 3
        assert data.faces == ((0, 1, 2),)

    def test_face_type_counts(self):
        text = (
            "v 0 0 0\nv 1 0 0\nv 0 1 0\nv 2 0 0\nv 2 1 0\n"
            "f 1 2 3\nf 2 4 5 3\nf 1 2 4 5 3"
        )
        data = parse_obj(text)
        assert data.face_type_counts() == {"tri": 1, "quad": 1, "ngon": 1}


# =====================================================================
# Fehlerfälle: laut fehlschlagen statt still Datenverlust
# =====================================================================

class TestObjErrors:
    def test_face_index_out_of_range(self):
        text = "v 0 0 0\nf 1 2 3"
        with pytest.raises(ObjLoadError):
            parse_obj(text)

    def test_face_index_zero_is_invalid(self):
        text = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 0 1 2"
        with pytest.raises(ObjLoadError):
            parse_obj(text)

    def test_face_with_two_references_rejected(self):
        text = "v 0 0 0\nv 1 0 0\nf 1 2"
        with pytest.raises(ObjLoadError):
            parse_obj(text)

    def test_vertex_needs_three_coordinates(self):
        text = "v 0 0"
        with pytest.raises(ObjLoadError):
            parse_obj(text)

    def test_invalid_number_in_vertex(self):
        text = "v 0 abc 0"
        with pytest.raises(ObjLoadError):
            parse_obj(text)

    def test_load_obj_missing_file(self):
        with pytest.raises(ObjLoadError):
            load_obj(_EXPERIMENT_DIR / "meshes" / "gibt_es_nicht.obj")


# =====================================================================
# Echter Asset-Stand (ground truth, separat über PowerShell verifiziert)
# =====================================================================

class TestHeadBasemeshAsset:
    def test_asset_loads(self):
        data = load_obj(_HEAD_ASSET)
        assert data.vertex_count == 326
        assert data.face_count == 324

    def test_asset_is_all_quads(self):
        data = load_obj(_HEAD_ASSET)
        assert data.face_type_counts() == {"tri": 0, "quad": 324, "ngon": 0}

    def test_asset_bounds(self):
        data = load_obj(_HEAD_ASSET)
        xs = [v[0] for v in data.vertices]
        ys = [v[1] for v in data.vertices]
        zs = [v[2] for v in data.vertices]
        assert min(xs) == pytest.approx(-2.605081)
        assert max(xs) == pytest.approx(2.605081)
        assert min(ys) == pytest.approx(0.0)
        assert max(ys) == pytest.approx(4.778098)
        assert min(zs) == pytest.approx(-1.647624)
        assert max(zs) == pytest.approx(1.647624)

    def test_asset_face_token_form_is_v_vt_vn(self):
        # 324 Faces × 4 Referenzen: jede Face-Zeile hat 4 v/vt/vn-Tokens.
        lines = _HEAD_ASSET.read_text(encoding="utf-8").splitlines()
        face_lines = [ln for ln in lines if ln.split() and ln.split()[0] == "f"]
        assert len(face_lines) == 324
        assert all(len(ln.split()) == 5 for ln in face_lines)
        assert all("/" in token for ln in face_lines for token in ln.split()[1:])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
