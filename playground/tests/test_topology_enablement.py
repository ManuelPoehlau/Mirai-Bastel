"""Headless-Tests für WP-AP-Enablement-01 (Split Edge + Undo/Redo).

Kein GL, kein Fenster. Prüft ausschließlich das, was im Enablement-Scope
verabschiedet wurde:

    1. split_selected_edge() erzeugt genau einen History-Eintrag
    2. Undo macht den Split exakt rückgängig (Vertex-/Edge-/Face-Anzahl)
    3. Redo stellt ihn exakt wieder her
    4. Mehrfacher Split + mehrfaches Undo/Redo bleibt konsistent
    5. Undo auf leerer History ist ein No-op (kein Crash)
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
from playground.topology_ops import split_selected_edge  # noqa: E402


def _counts(app: PlaygroundApp) -> tuple[int, int, int]:
    mesh = app.scene.mesh
    return (
        len(list(mesh.all_vertex_ids())),
        len(list(mesh.all_edge_ids())),
        len(list(mesh.all_face_ids())),
    )


# ---------------------------------------------------------------------------
# 1. Genau ein History-Eintrag pro Split
# ---------------------------------------------------------------------------

def test_split_pushes_exactly_one_history_entry():
    app = PlaygroundApp()
    app.load_cube()
    mesh = app.scene.mesh
    edge_id = next(iter(mesh.all_edge_ids()))

    assert len(app.scene.history) == 0
    split_selected_edge(app.scene, edge_id)
    assert len(app.scene.history) == 1


# ---------------------------------------------------------------------------
# 2 + 3. Undo/Redo exakt
# ---------------------------------------------------------------------------

def test_split_undo_redo_exact_counts():
    app = PlaygroundApp()
    app.load_cube()
    before = _counts(app)

    edge_id = next(iter(app.scene.mesh.all_edge_ids()))
    split_selected_edge(app.scene, edge_id)
    after_split = _counts(app)
    assert after_split != before, "Split muss die Topologie sichtbar verändern"

    app.undo()
    assert _counts(app) == before, "Undo muss exakt den Ausgangszustand herstellen"

    app.redo()
    assert _counts(app) == after_split, "Redo muss exakt den Split-Zustand herstellen"


# ---------------------------------------------------------------------------
# 4. Mehrfacher Split + mehrfaches Undo/Redo bleibt konsistent
# ---------------------------------------------------------------------------

def test_multiple_split_undo_redo_cycle_is_consistent():
    app = PlaygroundApp()
    app.load_cube()
    states = [_counts(app)]

    for _ in range(3):
        edge_id = next(iter(app.scene.mesh.all_edge_ids()))
        split_selected_edge(app.scene, edge_id)
        states.append(_counts(app))

    assert len(app.scene.history) == 3

    # Alles zurück
    for _ in range(3):
        app.undo()
    assert _counts(app) == states[0]

    # Alles wieder vor
    for _ in range(3):
        app.redo()
    assert _counts(app) == states[-1]

    # Ein Schritt zurück, dann ein neuer Split verwirft den Redo-Zweig
    # (HistoryStack-Contract, siehe core/history.py — kein neues Verhalten)
    app.undo()
    assert _counts(app) == states[-2]
    edge_id = next(iter(app.scene.mesh.all_edge_ids()))
    split_selected_edge(app.scene, edge_id)
    assert len(app.scene.history) == 3  # 2 verbliebene + 1 neuer, Redo-Zweig verworfen


# ---------------------------------------------------------------------------
# 5. Undo auf leerer History ist ein No-op
# ---------------------------------------------------------------------------

def test_undo_on_empty_history_is_noop():
    app = PlaygroundApp()
    app.load_cube()
    before = _counts(app)
    app.undo()  # darf nicht crashen
    assert _counts(app) == before
