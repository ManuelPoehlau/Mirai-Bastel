"""PlaygroundApp — Orchestrator für das Artist Playground.

Wrapping von src.mirai.application.Application. Lädt Szene (Cube oder
Head-Basemesh via OBJ-Adapter), hält das aktive Experiment und stellt
scene/camera/viewport/active_experiment bereit.

Import-Pfade: Repo-Root muss im sys.path sein (über playground/_paths.py
sichergestellt). core/viewport/mirai werden aus src/ importiert; Framing- und
Mesh-Helper aus dem Integration Lab (adapters/obj_to_core.py, _paths.py).
"""

from __future__ import annotations

# Bootstrap: sys.path setzen, bevor Production-Imports kommen.
from playground._paths import DEFAULT_HEAD_ASSET, ensure_paths

ensure_paths()

from core import Scene  # noqa: E402
from mirai.application import Application  # noqa: E402
from viewport import Viewport  # noqa: E402
from viewport.resource_store import TraceStore  # noqa: E402

# Framing-/Mesh-Helper direkt aus dem Integration Lab (Wiederverwendung statt
# Duplikat — identischer Startpfad zu lab_viewport.py, siehe _paths.py).
from adapters.obj_to_core import (  # noqa: E402 (Integration Lab)
    build_core_scene_from_obj,
    frame_camera_on_bounds,
)

from mirai.viewport.display import DisplayState  # noqa: E402

from playground.camera import PlaygroundCamera  # noqa: E402
from playground.experiment import Experiment  # noqa: E402
from playground.slot import ExperimentSlot  # noqa: E402


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
        # GL-Grenze: Production-Kamera liefert eine +forward-View-Matrix, die
        # mit der GL-Projektion (clip.w = -view.z) alles vor der Kamera clippt
        # (dokumentierter Befund, Audit §A.1). PlaygroundCamera überschreibt
        # NUR build_view_matrix() (gluLookAt-Konvention) — Picking-/Kamera-Math
        # bleibt Production-unverändert. Keine Änderung an src/mirai.
        self._app.camera = PlaygroundCamera()
        self._active_experiment: Experiment = Experiment()
        self._active_slot: ExperimentSlot | None = None
        self.display_state: DisplayState = DisplayState()
        self.show_vertices: bool = False

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

    # -- Kamera-Framing -------------------------------------------------------

    def _frame_camera(self) -> None:
        """Kamera auf die Mesh-Bounds ausrichten (margin=1.4).

        Wiederverwendung des Integration-Lab-Helfers `frame_camera_on_bounds`
        (adapters/obj_to_core.py) statt einer duplizierten Formel — damit ist
        der Startpfad 1:1 identisch zu lab_viewport.py::_focus_camera
        (target = Bounds-Zentrum, distance = radius/tan(fov/2) * margin).
        """
        mesh = self._app.scene.mesh
        if not mesh.all_vertex_ids():
            return
        frame_camera_on_bounds(self._app.camera, mesh, margin=1.4)

    # -- Szene-Loading --------------------------------------------------------

    def load_cube(self) -> None:
        """Würfel-Szene laden (über Application.init_scene)."""
        self._app.init_scene("cube")
        self._frame_camera()

    def load_head(self) -> None:
        """Head-Basemesh via OBJ-Adapter laden (identisch zum Integration Lab).

        Nutzt den Lab-Adapter `build_core_scene_from_obj` (OBJ → ObjMeshData →
        src.core.Scene) — exakt dieselbe Mesh-Erzeugung wie
        scene/scene_objects.py::build_head_scene im Integration Lab. Danach
        Viewport neu binden (analog Application.init_scene) und Kamera rahmen.
        """
        scene = build_core_scene_from_obj(DEFAULT_HEAD_ASSET)
        self._app.scene.mesh = scene.mesh

        # Viewport neu binden (analog Application.init_scene)
        self._app.viewport = Viewport(
            self._app.scene.mesh,
            selection=self._app.scene.selection,
            store_type=TraceStore,
        )
        self._app.viewport.bind_camera(self._app.camera)
        self._frame_camera()

    # -- Experiment -----------------------------------------------------------

    @property
    def active_slot(self) -> ExperimentSlot | None:
        return self._active_slot

    def set_experiment(self, experiment: Experiment) -> None:
        """Aktives Experiment wechseln. Deaktiviert das alte, aktiviert das neue."""
        if self._active_experiment is not experiment:
            self._active_experiment.deactivate()
            self._active_experiment = experiment
            self._active_experiment.activate()

    def set_slot(self, slot: ExperimentSlot) -> None:
        """Aktiven Experiment-Slot setzen und erste Variante aktivieren (WP-AP-02)."""
        self._active_slot = slot
        self.set_experiment(slot.active_experiment)

    def activate_variant(self, index: int) -> None:
        """Variante im aktiven Slot wechseln (WP-AP-02)."""
        if self._active_slot is None:
            raise RuntimeError("Kein aktiver ExperimentSlot. Erst set_slot() aufrufen.")
        self._active_slot.activate(index)
        self.set_experiment(self._active_slot.active_experiment)

    # -- Per-Frame-Tick -------------------------------------------------------

    def update(self, dt: float) -> None:
        """Per-Frame-Tick: Viewport-Sync + aktives Experiment."""
        self._app.update_viewport(dt)
        self._active_experiment.update(dt)
