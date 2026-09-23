"""WP-STAB-06: Collapse Edge pushes history like Split does.

Kein GL, kein Fenster — same headless pattern as
`test_topology_enablement.py` (Split's own history tests), mirrored for the
new `collapse_selected_edge()` wrapper added by this WP.

Root cause (pre-fix): the Shift+C handler in `window.py` called
`mesh.collapse_edge(edge_id)` directly — no `MeshStateCommand` was ever
pushed onto `scene.history` for a Collapse, so `Ctrl+Z` after Collapse Edge
was a no-op (or undid whatever the *previous* history entry was), unlike
Split/Connect which already went through the snapshot-command wrapper.

    1. collapse_selected_edge() erzeugt genau einen History-Eintrag
    2. Undo macht den Collapse exakt rückgängig (Vertex-/Edge-/Face-Anzahl
       UND Positionen)
    3. Redo stellt ihn exakt wieder her
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

from playground.app import PlaygroundApp  # noqa: E402
from playground.topology_ops import collapse_selected_edge  # noqa: E402


def _counts(app: PlaygroundApp) -> tuple[int, int, int]:
    mesh = app.scene.mesh
    return (
        len(list(mesh.all_vertex_ids())),
        len(list(mesh.all_edge_ids())),
        len(list(mesh.all_face_ids())),
    )


def _positions(app: PlaygroundApp) -> dict:
    mesh = app.scene.mesh
    return {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}


# ---------------------------------------------------------------------------
# 1. Genau ein History-Eintrag pro Collapse
# ---------------------------------------------------------------------------

def test_collapse_pushes_exactly_one_history_entry():
    app = PlaygroundApp()
    app.load_cube()
    mesh = app.scene.mesh
    edge_id = next(iter(mesh.all_edge_ids()))

    assert len(app.scene.history) == 0
    collapse_selected_edge(app.scene, edge_id)
    assert len(app.scene.history) == 1


# ---------------------------------------------------------------------------
# 2 + 3. Undo/Redo exakt (Counts + Positionen)
# ---------------------------------------------------------------------------

def test_collapse_undo_redo_exact_counts_and_positions():
    app = PlaygroundApp()
    app.load_cube()
    before_counts = _counts(app)
    before_positions = _positions(app)

    edge_id = next(iter(app.scene.mesh.all_edge_ids()))
    collapse_selected_edge(app.scene, edge_id)
    after_counts = _counts(app)
    after_positions = _positions(app)
    assert after_counts != before_counts, "Collapse muss die Topologie sichtbar verändern"
    assert after_counts[0] == before_counts[0] - 1, "Collapse entfernt genau 1 Vertex"

    app.undo()
    assert _counts(app) == before_counts, "Undo muss exakt den Ausgangszustand herstellen (Counts)"
    assert _positions(app) == before_positions, "Undo muss exakt den Ausgangszustand herstellen (Positionen)"

    app.redo()
    assert _counts(app) == after_counts, "Redo muss exakt den Collapse-Zustand herstellen (Counts)"
    assert _positions(app) == after_positions, "Redo muss exakt den Collapse-Zustand herstellen (Positionen)"


def test_collapse_undo_then_new_op_discards_redo_branch():
    """Same HistoryStack contract already exercised for Split (see
    test_multiple_split_undo_redo_cycle_is_consistent): undo, then a new
    mutation discards the redo branch instead of leaving it dangling."""
    app = PlaygroundApp()
    app.load_cube()

    edge_a = next(iter(app.scene.mesh.all_edge_ids()))
    collapse_selected_edge(app.scene, edge_a)
    assert len(app.scene.history) == 1

    app.undo()
    edge_b = next(iter(app.scene.mesh.all_edge_ids()))
    collapse_selected_edge(app.scene, edge_b)
    assert len(app.scene.history) == 1  # redo branch from the first collapse discarded
