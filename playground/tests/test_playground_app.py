"""Headless-Tests für PlaygroundApp (WP-AP-01).

Kein GL, kein Fenster. Prüft:
    1. load_cube() → scene hat Vertices
    2. load_head() → scene hat >100 Vertices
    3. active_experiment default = Experiment("none")
    4. set_experiment() wechselt aktives Experiment
    5. update(0.016) wirft keine Exception
"""

from __future__ import annotations

import sys
from pathlib import Path

# sys.path-Bootstrap: Repo-Root und src/ einbinden,
# damit Production-Pakete (core/viewport/mirai) importierbar sind.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
_RIGGING = _REPO_ROOT / "experiments" / "rigging-skinning-morphing"
for _p in (str(_REPO_SRC), str(_REPO_ROOT), str(_RIGGING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


from playground.app import PlaygroundApp  # noqa: E402
from playground.experiment import Experiment  # noqa: E402


# ---------------------------------------------------------------------------
# 1. load_cube() — scene hat Vertices
# ---------------------------------------------------------------------------

def test_load_cube_creates_vertices():
    app = PlaygroundApp()
    app.load_cube()
    vertex_ids = list(app.scene.mesh.all_vertex_ids())
    assert len(vertex_ids) > 0, "load_cube() muss Vertices erzeugen"
    assert len(vertex_ids) == 8, "Würfel hat 8 Vertices"


def test_load_cube_creates_faces():
    app = PlaygroundApp()
    app.load_cube()
    face_ids = list(app.scene.mesh.all_face_ids())
    assert len(face_ids) == 6, "Würfel hat 6 Faces"


# ---------------------------------------------------------------------------
# 2. load_head() — scene hat >100 Vertices
# ---------------------------------------------------------------------------

def test_load_head_creates_many_vertices():
    app = PlaygroundApp()
    app.load_head()
    vertex_ids = list(app.scene.mesh.all_vertex_ids())
    assert len(vertex_ids) > 100, (
        f"Head-Basemesh muss >100 Vertices haben, hat {len(vertex_ids)}"
    )


def test_load_head_creates_many_faces():
    app = PlaygroundApp()
    app.load_head()
    face_ids = list(app.scene.mesh.all_face_ids())
    assert len(face_ids) > 100, (
        f"Head-Basemesh muss >100 Faces haben, hat {len(face_ids)}"
    )


def test_load_head_viewport_is_bound():
    """Nach load_head() muss ein Viewport gebunden sein."""
    app = PlaygroundApp()
    app.load_head()
    assert app.viewport is not None, "Viewport muss nach load_head() gebunden sein"


# ---------------------------------------------------------------------------
# 3. active_experiment default = Experiment (id="none")
# ---------------------------------------------------------------------------

def test_active_experiment_default_id_is_none():
    app = PlaygroundApp()
    exp = app.active_experiment
    assert isinstance(exp, Experiment)
    assert exp.id == "none"


def test_active_experiment_default_name():
    app = PlaygroundApp()
    assert app.active_experiment.name == "No Experiment"


# ---------------------------------------------------------------------------
# 4. set_experiment() wechselt aktives Experiment
# ---------------------------------------------------------------------------

class _MockExperiment(Experiment):
    id = "mock"
    name = "Mock Experiment"
    variant = "test"

    def __init__(self):
        self.activated = False
        self.deactivated = False

    def activate(self):
        self.activated = True

    def deactivate(self):
        self.deactivated = True


def test_set_experiment_changes_active():
    app = PlaygroundApp()
    mock = _MockExperiment()
    app.set_experiment(mock)
    assert app.active_experiment is mock


def test_set_experiment_calls_activate():
    app = PlaygroundApp()
    mock = _MockExperiment()
    app.set_experiment(mock)
    assert mock.activated, "activate() muss beim Wechsel aufgerufen werden"


def test_set_experiment_calls_deactivate_on_old():
    app = PlaygroundApp()
    first = _MockExperiment()
    second = _MockExperiment()
    app.set_experiment(first)
    app.set_experiment(second)
    assert first.deactivated, "deactivate() muss auf das alte Experiment aufgerufen werden"
    assert second.activated, "activate() muss auf das neue Experiment aufgerufen werden"


def test_set_experiment_same_noop():
    """set_experiment() mit demselben Objekt darf keine Callbacks auslösen."""
    app = PlaygroundApp()
    mock = _MockExperiment()
    app.set_experiment(mock)
    mock.activated = False  # Reset nach dem ersten set_experiment()
    mock.deactivated = False
    app.set_experiment(mock)  # Erneut dasselbe Experiment setzen
    assert not mock.deactivated, "Kein deactivate() bei identischem Experiment"
    assert not mock.activated, "Kein activate() bei identischem Experiment"


# ---------------------------------------------------------------------------
# 5. update(0.016) wirft keine Exception
# ---------------------------------------------------------------------------

def test_update_without_scene_no_exception():
    """update() ohne geladene Szene darf keine Exception werfen."""
    app = PlaygroundApp()
    app.update(0.016)  # kein load_cube/head vorher


def test_update_with_cube_no_exception():
    app = PlaygroundApp()
    app.load_cube()
    app.update(0.016)


def test_update_with_head_no_exception():
    app = PlaygroundApp()
    app.load_head()
    app.update(0.016)


def test_update_calls_experiment_update():
    """update() muss das aktive Experiment ticken."""

    class _TickCounter(Experiment):
        id = "tick"
        name = "Tick Counter"

        def __init__(self):
            self.ticks = 0

        def update(self, dt: float):
            self.ticks += 1

    app = PlaygroundApp()
    counter = _TickCounter()
    app.set_experiment(counter)
    app.update(0.016)
    app.update(0.016)
    assert counter.ticks == 2, f"Erwartet 2 Ticks, erhalten: {counter.ticks}"
