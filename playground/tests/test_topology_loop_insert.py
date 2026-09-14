"""Headless-Tests für AP-05 Loop Insert.

    1. Loop Insert auf Cube → neuer Edge Loop entsteht, Topologie wächst
    2. Genau 1 History-Eintrag
    3. Undo/Redo-Zyklus
    4. Ungültige Edge → LoopInsertError, Mesh unverändert
    5. Einzelne Boundary-Edge (Ring < 2) → LoopInsertError
    6. Determinismus: gleiche Start-Edge → identisches Ergebnis
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from playground.app import PlaygroundApp  # noqa: E402
from playground.topology_tools.loop_insert import loop_insert, LoopInsertError  # noqa: E402


def _counts(app):
    mesh = app.scene.mesh
    return (
        len(list(mesh.all_vertex_ids())),
        len(list(mesh.all_edge_ids())),
        len(list(mesh.all_face_ids())),
    )


# ---------------------------------------------------------------------------
# 1. Loop Insert auf Cube → Topologie wächst
# ---------------------------------------------------------------------------

def test_loop_insert_cube_creates_new_geometry():
    app = PlaygroundApp()
    app.load_cube()
    before = _counts(app)
    start = next(iter(app.scene.mesh.all_edge_ids()))

    result = loop_insert(app.scene, start)

    after = _counts(app)
    assert len(result) >= 1, "Mindestens eine neue Verbindungskante erwartet"
    assert after[0] > before[0], "Split erzeugt neue Vertices"
    assert after[1] > before[1], "Neue Edges erwartet"
    assert after[2] >= before[2], "Face-Anzahl darf nicht sinken"
    for eid in result:
        assert app.scene.mesh.is_valid_edge(eid), "Alle neuen Edges müssen gültig sein"


# ---------------------------------------------------------------------------
# 2. Genau 1 History-Eintrag
# ---------------------------------------------------------------------------

def test_loop_insert_pushes_exactly_one_history_entry():
    app = PlaygroundApp()
    app.load_cube()
    start = next(iter(app.scene.mesh.all_edge_ids()))

    assert len(app.scene.history) == 0
    loop_insert(app.scene, start)
    assert len(app.scene.history) == 1


# ---------------------------------------------------------------------------
# 3. Undo/Redo-Zyklus
# ---------------------------------------------------------------------------

def test_loop_insert_undo_redo():
    app = PlaygroundApp()
    app.load_cube()
    before = _counts(app)
    start = next(iter(app.scene.mesh.all_edge_ids()))

    loop_insert(app.scene, start)
    after_insert = _counts(app)
    assert after_insert != before

    app.undo()
    assert _counts(app) == before, "Undo muss Ausgangszustand herstellen"

    app.redo()
    assert _counts(app) == after_insert, "Redo muss Insert-Zustand herstellen"


# ---------------------------------------------------------------------------
# 4. Ungültige Edge → LoopInsertError, Mesh unverändert
# ---------------------------------------------------------------------------

def test_loop_insert_invalid_edge_raises_and_mesh_unchanged():
    from core.ids import EdgeId
    app = PlaygroundApp()
    app.load_cube()
    before = _counts(app)

    with pytest.raises(LoopInsertError):
        loop_insert(app.scene, EdgeId(9999))

    assert _counts(app) == before
    assert len(app.scene.history) == 0


# ---------------------------------------------------------------------------
# 5. Freie Edge (Ring < 2 Kanten) → LoopInsertError
# ---------------------------------------------------------------------------

def test_loop_insert_free_edge_raises():
    """Eine freie Edge ohne Faces ergibt Ring-Länge 1 → LoopInsertError."""
    from core.mesh import Mesh
    from core.scene import Scene

    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    free_edge = mesh.add_edge(v0, v1)

    app = PlaygroundApp()
    app.load_cube()
    app.scene.mesh = mesh

    with pytest.raises(LoopInsertError):
        loop_insert(app.scene, free_edge)


# ---------------------------------------------------------------------------
# 6. Determinismus: gleiche Start-Edge → identische Topologie
# ---------------------------------------------------------------------------

def test_loop_insert_is_deterministic():
    def _run():
        app = PlaygroundApp()
        app.load_cube()
        start = next(iter(app.scene.mesh.all_edge_ids()))
        loop_insert(app.scene, start)
        return _counts(app)

    assert _run() == _run()
