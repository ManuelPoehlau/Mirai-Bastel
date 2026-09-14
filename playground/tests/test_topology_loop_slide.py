"""Headless-Tests für AP-05 Loop Slide.

    1. Positionen ändern sich nach update (t != 0)
    2. update mit dx=0 → Positionen unverändert (t bleibt 0)
    3. Commit → 1 History-Eintrag
    4. Undo/Redo-Zyklus
    5. Cancel → Ausgangszustand wiederhergestellt
    6. Ungültige Edge → LoopSlideError
    7. Valenz-3-Vertex (open-loop-Ende) → LoopSlideError
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
from playground.topology_tools.loop_insert import loop_insert  # noqa: E402
from playground.topology_tools.loop_slide import LoopSlideTool, LoopSlideError  # noqa: E402


def _insert_and_get_loop(app):
    """Cube laden, Loop Insert, neue Loop-Edges zurückgeben."""
    app.load_cube()
    start = next(iter(app.scene.mesh.all_edge_ids()))
    new_edges = loop_insert(app.scene, start)
    return set(new_edges)


def _vertex_positions(mesh, edge_ids):
    verts = set()
    for eid in edge_ids:
        v0, v1 = mesh.edge_vertices(eid)
        verts.update([v0, v1])
    return {vid: mesh.vertex_position(vid) for vid in verts}


# ---------------------------------------------------------------------------
# 1. Positionen ändern sich nach update (t != 0)
# ---------------------------------------------------------------------------

def test_slide_moves_vertices():
    app = PlaygroundApp()
    loop_edges = _insert_and_get_loop(app)
    mesh = app.scene.mesh

    before_pos = _vertex_positions(mesh, loop_edges)

    tool = LoopSlideTool(app.scene, app.camera)
    tool.activate()
    tool.begin(edge_ids=loop_edges)
    tool.update(dx=100.0, dy=0.0, width=800, height=600)

    after_pos = _vertex_positions(mesh, loop_edges)
    assert before_pos != after_pos, "Positionen müssen sich nach update ändern"
    tool.cancel()
    tool.deactivate()


# ---------------------------------------------------------------------------
# 2. update mit dx=0 → Positionen unverändert
# ---------------------------------------------------------------------------

def test_slide_zero_delta_no_change():
    app = PlaygroundApp()
    loop_edges = _insert_and_get_loop(app)
    mesh = app.scene.mesh
    before_pos = _vertex_positions(mesh, loop_edges)

    tool = LoopSlideTool(app.scene, app.camera)
    tool.activate()
    tool.begin(edge_ids=loop_edges)
    tool.update(dx=0.0, dy=0.0, width=800, height=600)

    assert _vertex_positions(mesh, loop_edges) == before_pos
    tool.cancel()
    tool.deactivate()


# ---------------------------------------------------------------------------
# 3. Commit → 1 History-Eintrag
# ---------------------------------------------------------------------------

def test_slide_commit_pushes_one_history_entry():
    app = PlaygroundApp()
    loop_edges = _insert_and_get_loop(app)
    history_before = len(app.scene.history)

    tool = LoopSlideTool(app.scene, app.camera)
    tool.activate()
    tool.begin(edge_ids=loop_edges)
    tool.update(dx=100.0, dy=0.0, width=800, height=600)
    tool.commit()
    tool.deactivate()

    assert len(app.scene.history) == history_before + 1


# ---------------------------------------------------------------------------
# 4. Undo/Redo-Zyklus
# ---------------------------------------------------------------------------

def test_slide_undo_redo():
    app = PlaygroundApp()
    loop_edges = _insert_and_get_loop(app)
    mesh = app.scene.mesh

    before_pos = _vertex_positions(mesh, loop_edges)

    tool = LoopSlideTool(app.scene, app.camera)
    tool.activate()
    tool.begin(edge_ids=loop_edges)
    tool.update(dx=100.0, dy=0.0, width=800, height=600)
    tool.commit()
    tool.deactivate()

    after_pos = _vertex_positions(mesh, loop_edges)
    assert after_pos != before_pos

    app.undo()
    assert _vertex_positions(mesh, loop_edges) == before_pos, "Undo muss Ausgangspositionen herstellen"

    app.redo()
    assert _vertex_positions(mesh, loop_edges) == after_pos, "Redo muss Slide-Positionen herstellen"


# ---------------------------------------------------------------------------
# 5. Cancel → Ausgangszustand
# ---------------------------------------------------------------------------

def test_slide_cancel_restores_positions():
    app = PlaygroundApp()
    loop_edges = _insert_and_get_loop(app)
    mesh = app.scene.mesh
    before_pos = _vertex_positions(mesh, loop_edges)

    tool = LoopSlideTool(app.scene, app.camera)
    tool.activate()
    tool.begin(edge_ids=loop_edges)
    tool.update(dx=200.0, dy=0.0, width=800, height=600)
    tool.cancel()
    tool.deactivate()

    assert _vertex_positions(mesh, loop_edges) == before_pos, "Cancel muss Positionen zurücksetzen"
    assert len(app.scene.history) == 1, "Cancel darf keinen History-Eintrag hinterlassen"


# ---------------------------------------------------------------------------
# 6. Ungültige Edge → LoopSlideError
# ---------------------------------------------------------------------------

def test_slide_invalid_edge_raises():
    from core.ids import EdgeId
    app = PlaygroundApp()
    app.load_cube()
    tool = LoopSlideTool(app.scene, app.camera)
    tool.activate()
    with pytest.raises(LoopSlideError):
        tool.begin(edge_ids={EdgeId(9999), EdgeId(9998)})
    tool.deactivate()


# ---------------------------------------------------------------------------
# 7. Valenz-3-Vertex (Cube-Edge direkt) → LoopSlideError
# ---------------------------------------------------------------------------

def test_slide_valence3_vertex_raises():
    """Cube-Edges haben Valenz-3-Vertices → LoopSlideError (kein geschlossener Loop)."""
    app = PlaygroundApp()
    app.load_cube()
    mesh = app.scene.mesh

    # Nimm zwei benachbarte Cube-Edges — die teilen einen Valenz-3-Vertex
    edges = list(mesh.all_edge_ids())[:2]
    tool = LoopSlideTool(app.scene, app.camera)
    tool.activate()
    with pytest.raises(LoopSlideError):
        tool.begin(edge_ids=set(edges))
    tool.deactivate()
