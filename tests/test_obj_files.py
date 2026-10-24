"""OBJ-Import/-Export im SPACE-Menü (`src/obj_files.py`, `Application.import_obj/export_obj`) und
die Sichtbarkeit der Symmetrie-Anzeige (Shift+Ctrl+S), headless."""

from __future__ import annotations

import sys

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

from mirai.application import Application
from mirai.symmetry_display import SymmetryDisplay
from obj_files import EXPORT_LABEL, IMPORT_LABEL_PREFIX, ObjFiles
from viewport.gl_symmetry_overlay import GLSymmetryOverlay

_EXAMPLES_DIR = _REPO_ROOT / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from viewport.resource_store import TraceStore  # noqa: E402


def _app() -> Application:
    app = Application()
    app.init_scene("cube", store_type=TraceStore, symmetry_overlay_type=GLSymmetryOverlay)
    return app


def test_export_then_import_roundtrip(tmp_path):
    app = _app()
    files = ObjFiles(app, tmp_path)
    assert files.activate(EXPORT_LABEL)
    (path,) = tmp_path.glob("*.obj")
    labels = files.entries()
    assert IMPORT_LABEL_PREFIX + path.stem in labels

    before = len(app.scene.objects)
    assert files.activate(IMPORT_LABEL_PREFIX + path.stem)
    assert len(app.scene.objects) == before + 1
    new = list(app.scene.objects.values())[-1]
    old = app.scene.edit_object
    assert len(new.mesh.all_vertex_ids()) == len(old.mesh.all_vertex_ids()) == 8
    assert len(new.mesh.all_face_ids()) == len(old.mesh.all_face_ids()) == 6


def test_import_failure_is_a_status_line(tmp_path):
    app = _app()
    bad = tmp_path / "bad.obj"
    bad.write_text("f 1 2 3\n")
    files = ObjFiles(app, tmp_path)
    before = len(app.scene.objects)
    assert not files.import_file(bad)
    assert len(app.scene.objects) == before
    assert "failed" in app.status_message


def test_toggle_symmetry_display():
    app = _app()
    display = app.symmetry_display
    assert isinstance(display, SymmetryDisplay) and display.visible
    assert app.toggle_symmetry_display() is False
    assert not display.visible
    assert app.toggle_symmetry_display() is True


def test_toggle_symmetry_display_without_overlay():
    app = Application()
    app.init_scene("cube", store_type=TraceStore)
    assert app.toggle_symmetry_display() is None
