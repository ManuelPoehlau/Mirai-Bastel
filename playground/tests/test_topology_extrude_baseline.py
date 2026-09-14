"""Headless-Tests für AP-05 Baseline Extrude (kein GL, kein Fenster).

Prüft:
    1. Commit erzeugt genau einen History-Eintrag
    2. Nach Commit ist ausschließlich die neue Result-Face selektiert
    3. Undo stellt Mesh UND Selection exakt wieder her
    4. Redo stellt den Extrude-Zustand exakt wieder her
    5. Cancel stellt Mesh UND Selection exakt wieder her, kein History-Eintrag
    6. begin() remapped die Selection auf die Result-Face (keine toten
       FaceIds — Regression: KeyError im Selection-VBO-Rebuild)
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
_RIGGING = _REPO_ROOT / "experiments" / "rigging-skinning-morphing"
for _p in (str(_REPO_SRC), str(_REPO_ROOT), str(_RIGGING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.selection import SelectionMode  # noqa: E402
from playground.app import PlaygroundApp  # noqa: E402
from playground.topology_tools.extrude import ExtrudeTool  # noqa: E402
from playground.vbo_builder import build_selection_data  # noqa: E402


def _counts(app: PlaygroundApp) -> tuple[int, int, int]:
    mesh = app.scene.mesh
    return (
        len(list(mesh.all_vertex_ids())),
        len(list(mesh.all_edge_ids())),
        len(list(mesh.all_face_ids())),
    )


def _pick_face(app: PlaygroundApp):
    return next(iter(app.scene.mesh.all_face_ids()))


def _do_extrude(app: PlaygroundApp, face_id, distance: float = 0.5):
    """Führt einen vollständigen Extrude-Commit durch (ohne Kamera, distance via Fake-Camera)."""
    tool = ExtrudeTool(app.scene, _FakeCamera(distance))
    tool.activate()
    tool.begin(face_id=face_id)
    tool.update(dx=1.0, dy=0.0, width=100, height=100)
    new_face_id = tool.commit()
    tool.deactivate()
    return new_face_id


class _FakeCamera:
    """Minimale Kamera für Tests: screen_delta_to_world gibt immer +Z-Delta zurück."""

    def __init__(self, distance: float = 0.5) -> None:
        self._distance = distance

    def screen_delta_to_world(self, point, dx, dy, width, height):
        return (0.0, 0.0, self._distance)


# -- Tests -------------------------------------------------------------------

def test_extrude_commit_pushes_exactly_one_history_entry():
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    assert len(app.scene.history) == 0
    _do_extrude(app, face_id)
    assert len(app.scene.history) == 1


def test_extrude_commit_selects_only_new_result_face():
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    new_face_id = _do_extrude(app, face_id)
    sel = app.scene.selection
    assert sel.mode is SelectionMode.FACE
    assert sel.faces == {new_face_id}


def test_extrude_undo_restores_mesh_and_selection():
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    # Selection vor Extrude: Face-Modus, face_id ausgewählt
    app.scene.selection.mode = SelectionMode.FACE
    app.scene.selection.set({face_id})
    before_counts = _counts(app)

    _do_extrude(app, face_id)
    after_counts = _counts(app)
    assert after_counts != before_counts

    app.undo()
    assert _counts(app) == before_counts
    # Nach Undo: face_id ist wieder gültig (load_state stellt IDs exakt wieder her)
    assert app.scene.mesh.is_valid_face(face_id)


def test_extrude_redo_restores_extrude_state():
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    new_face_id = _do_extrude(app, face_id)
    after_counts = _counts(app)

    app.undo()
    app.redo()
    assert _counts(app) == after_counts
    assert app.scene.mesh.is_valid_face(new_face_id)


def test_extrude_cancel_restores_mesh_and_selection_no_history():
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    app.scene.selection.mode = SelectionMode.FACE
    app.scene.selection.set({face_id})
    before_counts = _counts(app)

    tool = ExtrudeTool(app.scene, _FakeCamera(0.5))
    tool.activate()
    tool.begin(face_id=face_id)
    tool.update(dx=1.0, dy=0.0, width=100, height=100)
    tool.cancel()
    tool.deactivate()

    assert _counts(app) == before_counts
    assert len(app.scene.history) == 0
    assert app.scene.mesh.is_valid_face(face_id)


def test_extrude_begin_remaps_selection_to_result_face():
    """Regression (AP-05): begin() entfernt die Original-Face. Die Selection
    darf danach keine tote FaceId mehr enthalten — sonst stürzt der nächste
    Selection-VBO-Rebuild im Window mit KeyError ab (build_selection_data →
    mesh.face_vertices()). Die extrudierte Face wird auf die Result-Face
    gemappt; Cancel stellt die Original-Selektion wieder her."""
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    sel = app.scene.selection
    sel.mode = SelectionMode.FACE
    sel.set({face_id})

    tool = ExtrudeTool(app.scene, _FakeCamera(0.5))
    tool.activate()
    tool.begin(face_id=face_id)
    try:
        mesh = app.scene.mesh
        # Original-Face ist weg ...
        assert not mesh.is_valid_face(face_id)
        # ... die Selection enthält nur noch gültige IDs ...
        assert all(mesh.is_valid_face(fid) for fid in sel.faces)
        # ... und der Selection-VBO-Build (läuft im Window direkt nach
        # begin) crasht nicht mehr.
        build_selection_data(mesh, sel.faces)
        # Die extrudierte Face wurde auf die Result-Face umgemappt.
        assert sel.faces == {tool.new_face_id}
    finally:
        tool.cancel()
        tool.deactivate()

    # Cancel stellt Mesh UND die ursprüngliche Selektion wieder her.
    assert app.scene.mesh.is_valid_face(face_id)
    assert sel.faces == {face_id}


def test_extrude_hover_fallback_cancel_restores_empty_selection():
    """AP-05 Target Resolution: face_id wurde per Hover-Hit-Test ermittelt,
    nicht vorab selektiert. Cancel muss die Selection auf exakt den Zustand
    vor E zurücksetzen — hier: leer."""
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    sel = app.scene.selection
    sel.mode = SelectionMode.FACE
    # Keine Vorauswahl (leere Selection, wie nach Hover-Fallback)

    tool = ExtrudeTool(app.scene, _FakeCamera(0.5))
    tool.activate()
    tool.begin(face_id=face_id)
    tool.update(dx=1.0, dy=0.0, width=100, height=100)
    tool.cancel()
    tool.deactivate()

    assert sel.faces == set()
    assert app.scene.mesh.is_valid_face(face_id)
    assert len(app.scene.history) == 0


def test_extrude_hover_fallback_commit_selects_new_face():
    """AP-05 Target Resolution: Commit mit Hover-Target selektiert die neue
    Result-Face — identisch zum normalen Commit."""
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    sel = app.scene.selection
    sel.mode = SelectionMode.FACE
    # Keine Vorauswahl

    new_face_id = _do_extrude(app, face_id)

    assert sel.mode is SelectionMode.FACE
    assert sel.faces == {new_face_id}
    assert len(app.scene.history) == 1
