"""Startszene des Playground-Fensters: `initial_mesh` → geladenes Mesh.

Prüft genau den Weg, den `python playground/run.py <name>` nimmt: `run.py`
reicht sein Argument an `PlaygroundWindow(initial_mesh=...)` weiter, das Fenster
lädt die Szene selbst (`window._load_initial_scene`, AD-010). Frage hier: Kommt
ein Registry-Name der geteilten OBJ-Assets (AD-007, `examples/loaders/assets.py`)
wirklich als Startszene an — z. B. `subd_cube` statt Default-Würfel?

Muster wie test_gizmo.py / test_ad017_knife_keys.py: echtes (headless) Fenster.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _window(initial_mesh: str):
    from playground.app import PlaygroundApp
    from playground.window import PlaygroundWindow

    app = PlaygroundApp()
    win = PlaygroundWindow(app, initial_mesh=initial_mesh)
    return win, app


def _counts(app):
    """(Vertex-Anzahl, Face-Anzahl) der geladenen Szene."""
    mesh = app.scene.mesh
    return (len(list(mesh.all_vertex_ids())), len(list(mesh.all_face_ids())))


def test_subd_cube_can_be_the_start_scene():
    win, app = _window("subd_cube")
    try:
        assert _counts(app) == (26, 24), "subd_cube muss als Startszene geladen werden"
    finally:
        win.close()


def test_man_with_shoes_can_be_the_start_scene():
    win, app = _window("man_with_shoes_basemesh")
    try:
        assert _counts(app) == (928, 926)
    finally:
        win.close()


def test_head_still_works_as_start_scene():
    win, app = _window("head")
    try:
        assert _counts(app) == (326, 324)
    finally:
        win.close()


def test_unknown_start_scene_falls_back_to_cube():
    """Bestehendes Verhalten bleibt: Unbekanntes → Würfel (8 V / 6 F)."""
    win, app = _window("gibt_es_nicht")
    try:
        assert _counts(app) == (8, 6)
    finally:
        win.close()
