"""PlaygroundApp — Orchestrator für das Artist Playground.

Wrapping von src.mirai.application.Application. Lädt Szene (Cube, Head-Basemesh
oder ein anderes registriertes geteiltes OBJ-Asset via OBJ-Adapter), hält das
aktive Experiment und stellt scene/camera/viewport/active_experiment bereit.

Import-Pfade: Repo-Root muss im sys.path sein (über playground/_paths.py
sichergestellt). core/viewport/mirai werden aus src/ importiert; Framing- und
Mesh-Helper aus src/mirai/ (scene_factory, mesh_geometry, viewport/camera).
"""

from __future__ import annotations

# Bootstrap: sys.path setzen, bevor Production-Imports kommen.
from playground._paths import DEFAULT_HEAD_ASSET, ensure_paths

ensure_paths()

from core import Scene  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction import commands  # noqa: E402
from viewport import Viewport  # noqa: E402
from viewport.resource_store import ResourceStore, TraceStore  # noqa: E402

from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402

# AD-007: geteilte Assets liegen in `examples/meshes/` (dort liegt auch `examples/`
# auf sys.path) — Namen → Pfad über die Registratur statt eigener Konstanten.
from loaders.assets import asset_path  # noqa: E402

from mirai.viewport.display import DisplayState  # noqa: E402

from playground.camera import PlaygroundCamera  # noqa: E402
from playground.experiment import Experiment  # noqa: E402
from playground.selector import SelectMethod, SelectMode  # noqa: E402
from playground.slot import ExperimentSlot  # noqa: E402


class PlaygroundApp:
    """Minimaler Orchestrator für das Artist Playground.

    Wrapping von Application (kein Eingriff in src/mirai/).
    Hält aktive Experimente pro Family in einem per-Family-Registry.

    Methoden:
        load_cube()                       — Szene mit Würfel laden
        load_head()                       — Szene mit Head-Basemesh laden
        load_asset(name)                  — Szene aus geteiltem OBJ-Asset laden (AD-007)
        register_slot(slot, family_id)    — Slot für eine Family registrieren
        activate_variant(family_id, idx)  — Variante in einer Family wechseln
        set_experiment(exp)               — Aktives Experiment wechseln (Compat)
        undo() / redo()                   — History (WP-AP-Enablement-01)
        update(dt)                        — Per-Frame-Tick
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
        self._slots: dict[str, ExperimentSlot] = {}
        self.display_state: DisplayState = DisplayState()
        self.show_vertices: bool = False
        self.select_mode:   SelectMode   = SelectMode.REPLACE
        self.select_method: SelectMethod = SelectMethod.PICK
        self.active_tool = None  # wird in Experiment-Variante gesetzt (AP-04)
        self.focused_family: str = "selection"  # family Tab cycles / M operates on

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

        Nutzt `mesh_center_and_radius` (mirai.mesh_geometry) und
        `camera.frame_on_bounds()` (mirai.viewport.camera.OrbitCamera) —
        beides Production-API, kein Lab-Import mehr nötig.
        """
        mesh = self._app.scene.mesh
        if not mesh.all_vertex_ids():
            return
        center, radius = mesh_center_and_radius(mesh)
        self._app.camera.frame_on_bounds(center, radius, margin=1.4)

    # -- Szene-Loading --------------------------------------------------------

    def load_cylinder(self, store_type: type[ResourceStore] = TraceStore) -> None:
        """Cylinder scene (EX-A test body) — 12 segments, 6 rings, all-quad sides.

        store_type: Store-Backend für den Viewport (AD-010). Default
        `TraceStore` — headless, deterministisch, Basis der Test-Suite
        (unverändertes Verhalten für alle bestehenden Aufrufer/Tests). Das
        Live-Fenster übergibt explizit `playground.gl_store.
        PlaygroundPygletStore` (echtes GL-Backend, benötigt aktiven Kontext).
        """
        from playground.experiments.articulation.demo_cylinder import build_cylinder
        mesh = build_cylinder()
        self._app.scene.mesh = mesh
        self._app.viewport = Viewport(
            self._app.scene.mesh,
            selection=self._app.scene.selection,
            store_type=store_type,
        )
        self._app.viewport.bind_camera(self._app.camera)
        self._frame_camera()

    def load_grid(self, store_type: type[ResourceStore] = TraceStore) -> None:
        """Flaches 8x8-Quad-Raster (Connect Lab, CONNECT_NONQUAD_DISCOVERY §6).

        store_type: siehe `load_cylinder()`.
        """
        from playground.experiments.connect.demo_grid import build_grid
        self._app.scene.mesh = build_grid()
        self._app.viewport = Viewport(
            self._app.scene.mesh,
            selection=self._app.scene.selection,
            store_type=store_type,
        )
        self._app.viewport.bind_camera(self._app.camera)
        self._frame_camera()

    def load_cube(self, store_type: type[ResourceStore] = TraceStore) -> None:
        """Würfel-Szene laden.

        Baut Mesh + Viewport direkt (statt über `Application.init_scene()`,
        das keinen `store_type`-Parameter kennt) — Production-`Application`
        bleibt dabei bewusst unverändert (Promotion Boundary, AGENTS.md §M3:
        `src/mirai` ist nicht Playground-spezifisch und wird nicht für einen
        Playground-Bedarf angepasst). store_type: siehe `load_cylinder()`.
        """
        from mirai.scene_factory import create_cube
        self._app.scene.mesh = create_cube()
        self._app.viewport = Viewport(
            self._app.scene.mesh,
            selection=self._app.scene.selection,
            store_type=store_type,
        )
        self._app.viewport.bind_camera(self._app.camera)
        self._frame_camera()

    def load_head(self, store_type: type[ResourceStore] = TraceStore) -> None:
        """Head-Basemesh via OBJ-Adapter laden.

        Nutzt `build_core_scene_from_obj` aus `mirai.scene_factory`
        (OBJ → ObjMeshData → src.core.Scene, AD-008). Danach Viewport neu
        binden (analog Application.init_scene) und Kamera rahmen.
        store_type: siehe `load_cylinder()`.
        """
        scene = build_core_scene_from_obj(DEFAULT_HEAD_ASSET)
        self._app.scene.mesh = scene.mesh

        # Viewport neu binden (analog Application.init_scene)
        self._app.viewport = Viewport(
            self._app.scene.mesh,
            selection=self._app.scene.selection,
            store_type=store_type,
        )
        self._app.viewport.bind_camera(self._app.camera)
        self._frame_camera()

    def load_asset(self, name: str, store_type: type[ResourceStore] = TraceStore) -> None:
        """Geteiltes OBJ-Asset per Registry-Namen laden (`examples/loaders/assets.py`).

        Ermöglicht z. B. den Start mit einem anderen Mesh als dem Default-Würfel:
        `python playground/run.py subd_cube`. Gültige Namen: siehe
        `loaders.assets.asset_names()` — aktuell `"head_basemesh"`,
        `"man_with_shoes_basemesh"`, `"subd_cube"`. Unbekannter Name → `KeyError`,
        fehlende Datei → `ObjLoadError` (beides laut statt still).

        Gleicher Weg wie `load_head()` (OBJ → ObjMeshData → src.core.Scene,
        AD-008) inkl. Viewport-Rebind und Kamera-Framing.
        store_type: siehe `load_cylinder()`.
        """
        scene = build_core_scene_from_obj(asset_path(name))
        self._app.scene.mesh = scene.mesh

        # Viewport neu binden (analog Application.init_scene)
        self._app.viewport = Viewport(
            self._app.scene.mesh,
            selection=self._app.scene.selection,
            store_type=store_type,
        )
        self._app.viewport.bind_camera(self._app.camera)
        self._frame_camera()

    # -- Experiment -----------------------------------------------------------

    @property
    def active_slot(self) -> ExperimentSlot | None:
        return self._active_slot

    @property
    def slots(self) -> dict[str, ExperimentSlot]:
        """Per-Family Slot-Registry (family_id → ExperimentSlot)."""
        return self._slots

    def set_experiment(self, experiment: Experiment) -> None:
        """Aktives Experiment wechseln. Deaktiviert das alte, aktiviert das neue."""
        if self._active_experiment is not experiment:
            self._active_experiment.deactivate()
            self._active_experiment = experiment
            self._active_experiment.activate()

    def register_slot(self, slot: ExperimentSlot, family_id: str | None = None) -> None:
        """Slot für eine Research-Family registrieren.

        family_id: explizite Family-ID; falls None, wird experiment.id genutzt.
        """
        fid = family_id if family_id is not None else slot.active_experiment.id
        self._slots[fid] = slot

    def set_slot(self, slot: ExperimentSlot) -> None:
        """Aktiven Experiment-Slot setzen (Backward-Compat für WP-AP-02-Tests).

        Ruft register_slot() und set_experiment() auf, damit alte Tests und der
        Experiment-Line-HUD weiterhin funktionieren.
        """
        self._active_slot = slot
        self.register_slot(slot)
        self.set_experiment(slot.active_experiment)

    def activate_variant(self, family_id: str, index: int) -> None:
        """Variante in einer registrierten Family wechseln.

        Der Slot verwaltet deactivate/activate intern. _active_experiment wird
        auf die zuletzt aktivierte Variante gesetzt (für HUD / draw-Hook).
        """
        if family_id not in self._slots:
            raise KeyError(f"Kein Slot für Family '{family_id}' registriert.")
        slot = self._slots[family_id]
        slot.activate(index)
        self._active_experiment = slot.active_experiment

    # -- History (WP-AP-Enablement-01) -----------------------------------------
    # Dünner Passthrough auf Application.dispatch_command — dieselbe Undo/Redo-
    # Dispatch-Logik, die bereits in tests/test_application.py verifiziert ist
    # (test_dispatch_undo_redo_roundtrip, test_dispatch_undo_on_empty_history_
    # is_true_noop). Kein neues History-Konzept im Playground.

    def undo(self) -> None:
        self._app.dispatch_command(commands.UNDO)

    def redo(self) -> None:
        self._app.dispatch_command(commands.REDO)

    # -- Per-Frame-Tick -------------------------------------------------------

    def update(self, dt: float) -> None:
        """Per-Frame-Tick: Viewport-Sync + alle aktiven Experimente."""
        self._app.update_viewport(dt)
        if self._slots:
            for slot in self._slots.values():
                slot.active_experiment.update(dt)
        else:
            self._active_experiment.update(dt)
