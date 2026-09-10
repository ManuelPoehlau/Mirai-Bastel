"""PlaygroundApp — Orchestrator für das Artist Playground.

Wrapping von src.mirai.application.Application. Lädt Szene (Cube oder
Head-Basemesh via OBJ-Adapter), hält das aktive Experiment und stellt
scene/camera/viewport/active_experiment bereit.

Import-Pfade: Repo-Root muss im sys.path sein (über playground/_paths.py
sichergestellt). core/viewport/mirai werden aus src/ importiert.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap: sys.path setzen, bevor Production-Imports kommen.
from playground._paths import DEFAULT_HEAD_ASSET, ensure_paths

ensure_paths()

from core import Scene  # noqa: E402
from mirai.application import Application  # noqa: E402
from viewport import Viewport  # noqa: E402
from viewport.resource_store import TraceStore  # noqa: E402

from playground.experiment import Experiment  # noqa: E402


class PlaygroundApp:
    """Minimaler Orchestrator für das Artist Playground.

    Wrapping von Application (kein Eingriff in src/mirai/).
    Hält aktives Experiment (default: "none").

    Methoden:
        load_cube()            — Szene mit Würfel laden
        load_head()            — Szene mit Head-Basemesh laden
        set_experiment(exp)    — Aktives Experiment wechseln
        update(dt)             — Per-Frame-Tick
    """

    def __init__(self) -> None:
        self._app = Application()
        self._active_experiment: Experiment = Experiment()

    # -- Properties -----------------------------------------------------------

    @property
    def scene(self) -> Scene:
        return self._app.scene

    @property
    def camera(self):
        return self._app.camera

    @property
    def viewport(self) -> Viewport | None:
        return self._app.viewport

    @property
    def active_experiment(self) -> Experiment:
        return self._active_experiment

    # -- Szene-Loading --------------------------------------------------------

    def load_cube(self) -> None:
        """Würfel-Szene laden (über Application.init_scene)."""
        self._app.init_scene("cube")

    def load_head(self) -> None:
        """Head-Basemesh via OBJ-Adapter laden.

        Lädt `head_basemesh.obj` aus dem Rigging-Experiment-Ordner,
        konvertiert via OBJ→Core-Adapter und bindet den Viewport.
        """
        from loaders.obj_loader import load_obj  # noqa: PLC0415
        from core.mesh import Mesh  # noqa: PLC0415

        data = load_obj(DEFAULT_HEAD_ASSET)
        mesh = Mesh()
        vertex_ids = [mesh.add_vertex(pos) for pos in data.vertices]
        for face in data.faces:
            mesh.add_face([vertex_ids[i] for i in face])

        self._app.scene.mesh = mesh
        # Viewport neu binden (analog Application.init_scene)
        self._app.viewport = Viewport(
            mesh,
            selection=self._app.scene.selection,
            store_type=TraceStore,
        )
        self._app.viewport.bind_camera(self._app.camera)

    # -- Experiment -----------------------------------------------------------

    def set_experiment(self, experiment: Experiment) -> None:
        """Aktives Experiment wechseln. Deaktiviert das alte, aktiviert das neue."""
        if self._active_experiment is not experiment:
            self._active_experiment.deactivate()
            self._active_experiment = experiment
            self._active_experiment.activate()

    # -- Per-Frame-Tick -------------------------------------------------------

    def update(self, dt: float) -> None:
        """Per-Frame-Tick: Viewport-Sync + aktives Experiment."""
        self._app.update_viewport(dt)
        self._active_experiment.update(dt)
