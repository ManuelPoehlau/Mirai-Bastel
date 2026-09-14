"""Headless-Tests für AP-05 Extrude (kein GL, kein Fenster).

Baseline (Single-Face-Regression):
    1. Commit erzeugt genau einen History-Eintrag
    2. Nach Commit ist ausschließlich die neue Result-Face selektiert
    3. Undo stellt Mesh UND Selection exakt wieder her
    4. Redo stellt den Extrude-Zustand exakt wieder her
    5. Cancel stellt Mesh UND Selection exakt wieder her, kein History-Eintrag
    6. begin() remapped die Selection auf die Result-Face (keine toten
       FaceIds — Regression: KeyError im Selection-VBO-Rebuild)
    7. Hover-Fallback-Cancel stellt leere Selection wieder her
    8. Hover-Fallback-Commit selektiert neue Result-Face

Multi-Face-Extrude:
    9.  2 benachbarte Faces: genau 1 History-Eintrag, 2 Caps selektiert,
        geteilte Edge bekommt keine Seitenwand
    10. 2 nicht-benachbarte Faces: jede bekommt vollständige Seitenwand-Kontur
    11. Cancel bei 2+ Faces stellt Mesh + Multi-Selection exakt wieder her
    12. Undo/Redo-Zyklus für Multi-Face-Extrude
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


def _do_extrude(app: PlaygroundApp, face_ids: set, distance: float = 0.5) -> frozenset:
    """Führt einen vollständigen Extrude-Commit durch (ohne Kamera, distance via Fake-Camera)."""
    tool = ExtrudeTool(app.scene, _FakeCamera(distance))
    tool.activate()
    tool.begin(face_ids=face_ids)
    tool.update(dx=1.0, dy=0.0, width=100, height=100)
    new_face_ids = tool.commit()
    tool.deactivate()
    return new_face_ids


def _make_adjacent_faces(app: PlaygroundApp) -> tuple:
    """Zwei Faces, die genau eine Edge teilen."""
    mesh = app.scene.mesh
    all_faces = list(mesh.all_face_ids())
    for i, f1 in enumerate(all_faces):
        edges1 = set(mesh.face_edges(f1))
        for f2 in all_faces[i + 1:]:
            if edges1 & set(mesh.face_edges(f2)):
                return f1, f2
    raise ValueError("Keine benachbarten Faces gefunden")


def _make_non_adjacent_faces(app: PlaygroundApp) -> tuple:
    """Zwei Faces ohne gemeinsame Edge."""
    mesh = app.scene.mesh
    all_faces = list(mesh.all_face_ids())
    for i, f1 in enumerate(all_faces):
        edges1 = set(mesh.face_edges(f1))
        for f2 in all_faces[i + 1:]:
            if not (edges1 & set(mesh.face_edges(f2))):
                return f1, f2
    raise ValueError("Keine nicht-benachbarten Faces gefunden")


def _count_boundary_edges(mesh, face_ids: set) -> int:
    """Anzahl der Edges mit genau 1 angrenzender Face aus face_ids."""
    seen = set()
    count = 0
    for fid in face_ids:
        for eid in mesh.face_edges(fid):
            if eid in seen:
                continue
            seen.add(eid)
            in_sel = sum(1 for f in mesh.edge_faces(eid) if f in face_ids)
            if in_sel == 1:
                count += 1
    return count


class _FakeCamera:
    """Minimale Kamera für Tests: screen_delta_to_world gibt immer +Z-Delta zurück."""

    def __init__(self, distance: float = 0.5) -> None:
        self._distance = distance

    def screen_delta_to_world(self, point, dx, dy, width, height):
        return (0.0, 0.0, self._distance)


# -- Baseline-Tests (Single-Face-Regression) ---------------------------------

def test_extrude_commit_pushes_exactly_one_history_entry():
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    assert len(app.scene.history) == 0
    _do_extrude(app, {face_id})
    assert len(app.scene.history) == 1


def test_extrude_commit_selects_only_new_result_face():
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    new_face_ids = _do_extrude(app, {face_id})
    sel = app.scene.selection
    assert sel.mode is SelectionMode.FACE
    assert sel.faces == set(new_face_ids)


def test_extrude_undo_restores_mesh_and_selection():
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    app.scene.selection.mode = SelectionMode.FACE
    app.scene.selection.set({face_id})
    before_counts = _counts(app)

    _do_extrude(app, {face_id})
    after_counts = _counts(app)
    assert after_counts != before_counts

    app.undo()
    assert _counts(app) == before_counts
    assert app.scene.mesh.is_valid_face(face_id)


def test_extrude_redo_restores_extrude_state():
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    new_face_ids = _do_extrude(app, {face_id})
    after_counts = _counts(app)

    app.undo()
    app.redo()
    assert _counts(app) == after_counts
    assert all(app.scene.mesh.is_valid_face(fid) for fid in new_face_ids)


def test_extrude_cancel_restores_mesh_and_selection_no_history():
    app = PlaygroundApp()
    app.load_cube()
    face_id = _pick_face(app)
    app.scene.selection.mode = SelectionMode.FACE
    app.scene.selection.set({face_id})
    before_counts = _counts(app)

    tool = ExtrudeTool(app.scene, _FakeCamera(0.5))
    tool.activate()
    tool.begin(face_ids={face_id})
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
    tool.begin(face_ids={face_id})
    try:
        mesh = app.scene.mesh
        assert not mesh.is_valid_face(face_id)
        assert all(mesh.is_valid_face(fid) for fid in sel.faces)
        build_selection_data(mesh, sel.faces)
        assert sel.faces == set(tool.new_face_ids)
    finally:
        tool.cancel()
        tool.deactivate()

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

    tool = ExtrudeTool(app.scene, _FakeCamera(0.5))
    tool.activate()
    tool.begin(face_ids={face_id})
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

    new_face_ids = _do_extrude(app, {face_id})

    assert sel.mode is SelectionMode.FACE
    assert sel.faces == set(new_face_ids)
    assert len(app.scene.history) == 1


# -- Multi-Face-Tests --------------------------------------------------------

def test_multiface_adjacent_extrude_commit_and_no_wall_on_shared_edge():
    """2 benachbarte Faces: 1 History-Eintrag, 2 neue Caps, geteilte Edge
    bekommt keine Seitenwand (Anzahl neuer Faces = boundary_edge_count)."""
    app = PlaygroundApp()
    app.load_cube()
    f1, f2 = _make_adjacent_faces(app)
    face_ids = {f1, f2}

    mesh = app.scene.mesh
    before_face_count = len(list(mesh.all_face_ids()))
    boundary_count = _count_boundary_edges(mesh, face_ids)

    new_face_ids = _do_extrude(app, face_ids)

    assert len(app.scene.history) == 1
    assert len(new_face_ids) == 2
    assert app.scene.selection.faces == set(new_face_ids)
    after_face_count = len(list(app.scene.mesh.all_face_ids()))
    # Netto neue Faces = boundary_count (walls) + 2 (caps) - 2 (originals removed)
    assert after_face_count - before_face_count == boundary_count


def test_multiface_non_adjacent_extrude_full_sidewalls():
    """2 nicht-benachbarte Faces: jede bekommt ihre vollständige Seitenwand-
    Kontur (alle Edges sind Boundary, da keine Face geteilt wird)."""
    app = PlaygroundApp()
    app.load_cube()
    f1, f2 = _make_non_adjacent_faces(app)
    face_ids = {f1, f2}

    mesh = app.scene.mesh
    before_face_count = len(list(mesh.all_face_ids()))
    boundary_count = _count_boundary_edges(mesh, face_ids)
    # Für nicht-benachbarte Faces: alle Edges beider Faces sind Boundary
    edges1 = len(mesh.face_edges(f1))
    edges2 = len(mesh.face_edges(f2))
    assert boundary_count == edges1 + edges2

    new_face_ids = _do_extrude(app, face_ids)

    assert len(new_face_ids) == 2
    after_face_count = len(list(app.scene.mesh.all_face_ids()))
    assert after_face_count - before_face_count == boundary_count


def test_multiface_cancel_restores_mesh_and_full_selection():
    """Cancel bei 2+ Faces stellt Mesh UND komplette ursprüngliche
    Multi-Selection exakt wieder her."""
    app = PlaygroundApp()
    app.load_cube()
    f1, f2 = _make_adjacent_faces(app)
    face_ids = {f1, f2}

    sel = app.scene.selection
    sel.mode = SelectionMode.FACE
    sel.set(face_ids)
    before_counts = _counts(app)

    tool = ExtrudeTool(app.scene, _FakeCamera(0.5))
    tool.activate()
    tool.begin(face_ids=face_ids)
    tool.update(dx=1.0, dy=0.0, width=100, height=100)
    tool.cancel()
    tool.deactivate()

    assert _counts(app) == before_counts
    assert len(app.scene.history) == 0
    assert all(app.scene.mesh.is_valid_face(fid) for fid in face_ids)
    assert sel.faces == face_ids


def test_multiface_undo_redo_cycle():
    """Undo/Redo-Zyklus für eine Multi-Face-Extrude-Operation."""
    app = PlaygroundApp()
    app.load_cube()
    f1, f2 = _make_adjacent_faces(app)
    face_ids = {f1, f2}
    before_counts = _counts(app)

    new_face_ids = _do_extrude(app, face_ids)
    after_counts = _counts(app)

    assert after_counts != before_counts
    assert len(app.scene.history) == 1

    app.undo()
    assert _counts(app) == before_counts
    assert all(app.scene.mesh.is_valid_face(fid) for fid in face_ids)

    app.redo()
    assert _counts(app) == after_counts
    assert all(app.scene.mesh.is_valid_face(fid) for fid in new_face_ids)
