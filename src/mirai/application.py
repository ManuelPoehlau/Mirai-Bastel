"""Produktions-Application-Orchestrator (window-frei).

Gate 3 (Application Foundation): Erstellt und verbindet die
Core-Strukturen (Scene/Selection/History), die Viewport-State-Komponenten
(OrbitCamera/DisplayState, ohne Rendering), das Tool-Registry/ToolManager-
System und die Default-Input-Bindings.

Architekturpfad:

    Input (physikalisch)
      ↓ BindingSet.command_for(input)      [mirai.interaction.input]
    Command (semantisch)
      ↓ Application.dispatch_command(...)  [dieses Modul]
    Tool-Aktivierung | direkte Aktion      [mirai.interaction.tool_manager]
      ↓
    Operation (Core)                        [src.core]
      ↓
    Mesh / History

Wichtig:
- Kein Fenster, kein pyglet, kein Rendering — der gesamte Zustand ist
  headless testbar.
- Import des Cores erfolgt als top-level Paket `core` (realer Produktions-
  Pfad `src/core/`), nicht als `mirai.core` — der Core bleibt eigenständig
  und frozen (ADR-001 erlaubt nur die dokumentierte Transform-Promotion).
- Gate 5 implementiert den v0.2-Viewport (`src/viewport`) inkl. der
  Render-/GPU-Ressourcen; hier halten wir nur den window-freien State.
- Gate 7 verbindet Application.camera mit dem V0.2-Viewport: `init_scene()`
  erstellt den Viewport und bindet die OrbitCamera (Duck-Typing). Application
  bleibt window-frei; `src/viewport` bleibt unabhängig von `src/mirai`.
"""

from __future__ import annotations

import dataclasses
import math
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Optional

from core import (
    EdgeId,
    FaceId,
    HistoryStack,
    Mesh,
    ObjectId,
    ObjectState,
    Scene,
    SceneObject,
    Selection,
    SelectionMode,
    VertexId,
)
from core.operations import CollapseRefused, MeshDeltaCommand
from core.serialization import scene_from_json, scene_to_json

from viewport import Viewport  # Gate 7: V0.2 Rendering-Viewport (unabhängig von mirai)
from viewport.resource_store import ResourceStore, TraceStore

from . import regions as face_regions_api
from .hidden import HiddenSet, touches_hidden, visible
from .mask import (
    VertexMask,
    effective_mask,
    mask_symmetric_influence,
    mask_weights,
    unblocked,
)
from .interaction import BindingSet, Input, ToolManager, commands
from .interaction.bindings import KNIFE_MIRROR_VARIANT_KEY, KeymapLoad, build_default_bindings, load_keymap
from .interaction.input import MORPH_CONTEXT, SUBD_CONTEXT
from .interaction.pointer import Click, DragStep, PointerGestures
from .interaction.routing import tool_for_command
from .interaction.tools import resolve_selection_vertices
from .interaction.tools.selection_helpers import selection_pivot
from .mesh_geometry import mesh_center_and_radius
from . import object_space
from .pivot import WorkingPivot
from .scene_objects import (
    editable_material,
    replace_scene,
    reset_scene,
    unique_object_name,
)
from .soft_selection import (
    EMPTY_BANDS,
    RADIUS_STEPS_PERCENT,
    SoftBands,
    SoftSettings,
    SoftSymmetryRefusal,
    compute_influence,
    has_flow_direction,
    symmetric_influence,
)
from .topology.connect_per_face import EDGE_CONNECT_LABEL, TopologyToolError, apply_connect_edges
from .topology.connect_vertices_per_face import (
    VERTEX_CONNECT_LABEL,
    VertexConnectError,
    apply_connect_vertices,
)
from .symmetry_coordination import (
    SymmetryIndex,
    canonical_edges,
    canonical_faces,
    canonical_vertices,
    expand_faces,
)
from .symmetric_ops import SymmetryRefusal, on_residue_sides, residue_sides
from .symmetry import mirrored_selection
from .symmetry_display import SymmetryDisplay
from .resymmetrize import ResymPlan
from .controllers.services import AppServices
from .controllers.gestures import (
    CONSTRAINT_ONE_SHOT,
    SMOOTH_COMMANDS,
    TRANSFORM_COMMANDS,
    TWEAK_KEY,
    TWEAK_TRANSFORMS,
    CONSTRAINT_SPACES,
    GestureController,
    GestureSession,
    element_vertices,
    hovered_of_mode,
)
from .controllers.knife import KnifeController
from .controllers.morph import MorphController
from .controllers.objects import PLACEMENT_COMMANDS, ObjectController, selection_state
from .controllers.pointer_tools import PointerToolsController
from .controllers.symmetry import SymmetryController
from .interaction.session import (
    PASS,
    Command,
    Drag,
    Hover,
    InteractionSlot,
    KeyPress,
    KeyRelease,
    Leave,
    Modifiers,
    Motion,
    Press,
    Refusal,
    Release,
    RunContext,
    Wheel,
)
from . import symmetry_declarations
from .layer_declarations import PER_TARGET_COMMANDS, layer_refusal
from .topology.contextual_c import CContext, resolve_c_context
from .topology.border import BORDER_LABEL, CAP_LABEL, CapRefused, apply_cap, border_select
from .topology.collapse import COLLAPSE_LABEL, apply_collapse
from .topology.delete_dissolve import RemovalRefused, apply_removal, removal_label
from .topology.knife_preview import KnifeRenderData
from .topology.loop_ring import LoopRingError, edge_loop, edge_ring
from .topology import selection_steps
from .subdivision import SUBD_COMMANDS, SubdivisionPreview, install_subd_bindings
from .morph_targets import MORPH_COMMANDS, MorphDisplay, TranslatingHistory, install_morph_bindings
from .surface_chain import SurfaceChain
from .viewport import DisplayMode, DisplayState, OrbitCamera
from .viewport.camera import nearest_standard_view
from .viewport.box_select import (
    elements_in_polygon,
    elements_in_rect,
    normalized_rect,
    point_in_polygon,
    polygon_bounds,
)
from .viewport import gizmo as _gizmo
from . import transform_space
from .viewport.look_controls import (
    LOOK_ROWS,
    MaterialRow,
    LookRow,
    light_row,
)
from .viewport.gpu_picking import gpu_elements_in_rect, gpu_elements_in_region, gpu_pick_component
from .viewport.picking import pick_component, pick_face
from .viewport.picking_cache import PickCache


#: Orbit-Rate (rad/px) und Dolly-Faktoren — aus `src/main.py` (Stage A/B1)
#: hierher verschoben, Werte unverändert (WP-06 B2, E11).
ORBIT_RADIANS_PER_PX = 0.005
DOLLY_IN_FACTOR = 0.9
DOLLY_OUT_FACTOR = 1.1

_SELECT_COMMANDS = (
    commands.SELECT,
    commands.SELECT_ADD,
    commands.SELECT_REMOVE,
    commands.SELECT_TOGGLE,
)


#: 2026-10-15: the loop commands that run once on a key press (Shift+L, Shift+R, I).
_LOOP_COMMANDS = commands.LOOP_COMMANDS

#: WP Toolbox Gaps A1 (2026-10-23): the selection steps (`_selection_step`), once per press.
_SELECTION_STEP_COMMANDS = commands.SELECTION_STEP_COMMANDS

#: 2026-10-28 practical-test switches (session only): `Application._session_switch`.
_SESSION_SWITCH_COMMANDS = (commands.CONSTRAINT_MODE_TOGGLE, commands.GIZMO_SIZE_CYCLE)

#: The gizmo's name for the tool a handle drag runs (`Application.tweak_command`, the last W/E/R).
_GIZMO_TOOLS = {commands.MOVE: "move", commands.ROTATE: "rotate", commands.SCALE: "scale"}


#: WP-06 B5a (E42) and AD-024 §8: the display and Look commands (groups in `commands` since AD-027 M3).
_DISPLAY_COMMANDS = commands.DISPLAY_COMMANDS
_LOOK_COMMANDS = commands.LOOK_COMMANDS

_SET_DISPLAY_MODES: dict[str, DisplayMode] = {
    commands.SET_SHADED: DisplayMode.SHADED,
    commands.SET_FLAT_SHADED: DisplayMode.FLAT_SHADED,
    commands.SET_WIREFRAME: DisplayMode.WIREFRAME,
}


#: WP-SOFT-01 S2a (AD-020, `PROVISIONAL`): the state commands of Soft Selection. They start
#: no interaction and change no mesh, like the constraints: they set the sticky
#: `SoftSettings`, which the next gesture reads at `begin()`.
_MASK_COMMANDS = commands.MASK_COMMANDS
_HIDE_COMMANDS = commands.HIDE_COMMANDS
_REGION_COMMANDS = commands.POLYGROUP_COMMANDS

#: Commands that rewrite topology next to their selection: with hidden geometry around the selection they are
#: refused instead of silently changing faces the artist cannot see (`Application._hidden_refusal`). Loop Insert is not in
#: the list: its ring ends at hidden faces (`edge_ring(..., blocked)`) and `_edge_connect` guards the rest.
_TOPOLOGY_COMMANDS = frozenset(
    {
        commands.CONNECT,
        commands.COLLAPSE,
        commands.CAP,
        commands.EXTRUDE,
        commands.LOOP_SLIDE,
        commands.INSET,
        commands.BEVEL,
        commands.RESYMMETRIZE,
        commands.DELETE,
        commands.DISSOLVE,
        commands.DISSOLVE_NO_CLEANUP,
    }
)

_SOFT_COMMANDS = (
    commands.SOFT_TOGGLE,
    commands.SOFT_RADIUS_UP,
    commands.SOFT_RADIUS_DOWN,
    commands.SOFT_CURVE_CYCLE,
    commands.SOFT_METRIC_CYCLE,
    commands.SOFT_CURVE_SHAPE_ROUNDER,
    commands.SOFT_CURVE_SHAPE_SHARPER,
    commands.SOFT_BANDS_TOGGLE,
    commands.SOFT_VIEW_MODE_CYCLE,
    commands.SOFT_LOOK_CYCLE,
    commands.SOFT_FLOW_LOOP,
    commands.SOFT_FLOW_RING,
)

#: `Application._gpu_pick`: the window cannot serve this pick, ask the CPU picker.
_CPU = object()


@dataclasses.dataclass(frozen=True)
class _MeshTransaction:
    """Outcome of `Application._mesh_transaction`: whether an entry was pushed, and what the
    mutation returned."""

    changed: bool
    result: Any


#: WP Delete/Dissolve: Command → (dissolve, cleanup) für `remove_selected`.
_REMOVAL_COMMANDS: dict[str, tuple[bool, bool]] = {
    commands.DELETE: (False, False),
    commands.DISSOLVE: (True, True),
    commands.DISSOLVE_NO_CLEANUP: (True, False),
}

#: WP-06 B5b (E43): Component-Modi 1/2/3 (Selection Lab KEEP, `PROMOTED`); AD-021 M1: `4` =
#: Objekt-Modus (V1_SPEC §2).
_MODE_COMMANDS: dict[str, SelectionMode] = {
    commands.SET_VERTEX_MODE: SelectionMode.VERTEX,
    commands.SET_EDGE_MODE: SelectionMode.EDGE,
    commands.SET_FACE_MODE: SelectionMode.FACE,
    commands.SET_OBJECT_MODE: SelectionMode.OBJECT,
}

#: A command handler of the table (AD-027 §3.4): (command, where it comes from, the API's tool context) -> bool.
Handler = Callable[[str, RunContext, Optional[dict]], bool]
_API = RunContext("api")


@dataclasses.dataclass(frozen=True)
class CommandGate:
    """Data-only command gate (WP-SYM-LAB-03 H2, AD-013 H2 addendum, proposal G).

    `refused`: command → status text (block-list). `allowed`: allow-list
    (None = no allow-list); a command outside it is refused with
    `not_allowed_text`. `refused_contexts` (H2 amendment G-2, 2026-10-08):
    resolved `C` context → status text; it can only refuse `C` after a gate
    that let `Connect` through (`CContext.NONE` is no operation and may not be
    listed). Immutable: a host replaces `Application.command_gate` as a whole,
    never edits it. `Application` checks it in `key_press` (after the Knife
    routing), for click commands before `select_at`, and for the `C` context in
    `_connect_command`; it calls no host code."""

    refused: Mapping[str, str] = dataclasses.field(default_factory=dict)
    allowed: frozenset[str] | None = None
    not_allowed_text: str = ""
    refused_contexts: Mapping[CContext, str] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if CContext.NONE in self.refused_contexts:
            raise ValueError("CommandGate.refused_contexts may not list CContext.NONE (no operation)")
        object.__setattr__(self, "refused", MappingProxyType(dict(self.refused)))
        object.__setattr__(self, "refused_contexts", MappingProxyType(dict(self.refused_contexts)))
        if self.allowed is not None:
            object.__setattr__(self, "allowed", frozenset(self.allowed))

    def refusal(self, command: str) -> str | None:
        """Status text if `command` is refused, else None."""
        if command in self.refused:
            return self.refused[command]
        if self.allowed is not None and command not in self.allowed:
            return self.not_allowed_text
        return None

    def context_refusal(self, context: CContext) -> str | None:
        """Status text if the resolved `C` context is refused, else None."""
        return self.refused_contexts.get(context)


class Application:
    """Window-unabhängiger Produktions-Orchestrator."""

    def __init__(self, keymap_path: Optional[str | Path] = None) -> None:
        # Core-Strukturen
        self.scene: Scene = Scene()
        self.selection: Selection = self.scene.selection
        # AD-025 Phase 3: the app's history translates pushes while a morph target's editing view is
        # open (`morph_targets.TranslatingHistory`; Core `HistoryStack` unchanged).
        self.history: HistoryStack = TranslatingHistory()
        self.scene.history = self.history

        # Viewport-State (kein Rendering in Gate 3)
        self.camera: OrbitCamera = OrbitCamera()
        self.display: DisplayState = DisplayState()
        # AD-024 §6/§8: the Look row the arrow keys edit (index into `look_controls.LOOK_ROWS`).
        self._look_row_index = 0

        # WP-06 B8 (picking speed + occlusion, PROVISIONAL): screen-space pick
        # cache, refreshed lazily per camera/mesh state (`picking_cache.py`).
        # Orbit/zoom/pan invalidate it automatically (keyed on
        # `camera.camera_revision`); every other trigger from the handoff
        # (Move/Rotate/Scale commit, Undo/Redo, Split/Connect, Knife cut,
        # display-mode change) calls `self._pick_cache.invalidate()`
        # explicitly at its existing mutation/notification call site.
        self._pick_cache: PickCache = PickCache()
        # AD-022 B2-out (2026-10-21): hover / click / Paint and Box of vertices, edges and faces pick
        # from the viewport's ID buffers when the window has a GL store; False = always the CPU picker
        # (comparison runs, the probes; `MIRAI_CPU_PICKING=1` in the environment as the escape hatch
        # if a driver draws wrong IDs).
        self.gpu_picking: bool = os.environ.get("MIRAI_CPU_PICKING") != "1"
        # Gate 7: V0.2 Viewport wird in init_scene() mit dem Mesh gebunden.
        # Bliebt None, bis init_scene() aufgerufen wurde (kein Mesh verfügbar).
        self.viewport: Viewport | None = None

        # Tools
        self.tool_manager: ToolManager = ToolManager()
        self._setup_tools()

        # Input
        # Gate 6 (Input Config): Default → optionales keymap.json → BindingSet.
        # Das Overlay wird genau einmal beim Application-Start geladen. Seit dem
        # AD-013-Addendum 2026-10-28 blockiert eine ungültige Datei den Start nicht
        # mehr: sie wird ganz verworfen, die Defaults gelten, `keymap_load` sagt warum
        # (Statuszeile, HUD, Konsole des Hosts). Kein Runtime-Hot-Reload.
        self.bindings: BindingSet = build_default_bindings()
        # 2026-10-23: the SubD preview's provisional keys, context "subd" (checked against the
        # defaults here, before a keymap.json may rebind anything).
        install_subd_bindings(self.bindings)
        # AD-025 Phase 3: the morph-target keys, context "morph" (resolved after global and SubD).
        install_morph_bindings(self.bindings)
        #: What loading `keymap_path` did (None = no path given, defaults only).
        self.keymap_load: KeymapLoad | None = (
            None if keymap_path is None else load_keymap(self.bindings, keymap_path)
        )

        # WP-06 B2 (AD-019): Pointer-Gesten laufen über dieselben Bindings.
        # Größe in logischen Fenster-Pixeln (gleiche Einheit wie die
        # Maus-Koordinaten); der Entry-Point setzt sie über set_viewport_size().
        self.pointer: PointerGestures = PointerGestures(self.bindings)
        self.viewport_width: int = 1
        self.viewport_height: int = 1
        # WP-06 B2b (E20): letzte bekannte Cursor-Position (None = unbekannt
        # bzw. Cursor außerhalb des Fensters) - für das Hover-Re-Pick nach Zoom.
        self._cursor: tuple[float, float] | None = None
        # WP-VIEW-PERF-01 Slice 2 (option 5, coalescing): with `coalesce_hover` a plain mouse
        # move or a zoom notch only marks the hover stale; the frame tick (`update_viewport`)
        # picks once at the latest cursor, and every input that may read the hover first
        # (`key_press`, `pointer_press`, `dispatch_command`) picks it before (`flush_hover`).
        # The window loop (`src/main.py run`) switches it on; off (default) every move picks
        # at once, as before - the headless tests and hosts without a tick rely on that.
        self.coalesce_hover: bool = False
        self._hover_stale: bool = False

        # WP-06 B3 (E26, `PROVISIONAL` bis ein HUD existiert): letzte
        # Statusmeldung für den Nutzer. `status_serial` zählt jede Meldung,
        # damit der Entry-Point auch eine wiederholte, gleichlautende Meldung
        # (z. B. zweimal "Undo") erkennt.
        self.status_message: str = ""
        self.status_serial: int = 0
        if self.keymap_load is not None and self.keymap_load.problem is not None:
            self._set_status(self.keymap_load.problem)

        # WP-SYM-LAB-03 H2 (AD-013 H2 addendum): optional `CommandGate` of one
        # host (the Symmetry Lab, H2-R6). None = nothing is refused;
        # `src/main.py` never sets it.
        self.command_gate: CommandGate | None = None
        # H2 (same addendum): pauses the selection hover while a host's modal
        # interaction is open. Backing field, because `viewport` is None until
        # `init_scene()`; see `hover_suspended`. (Its only writer, the Lab's
        # Re-Symmetrize preview, became an `Application` session in AD-SYM-04 A3, AD-027 M1.)
        self._hover_suspended: bool = False
        # AD-027 §3.2: the slot for the running session (the Re-Symmetrize preview since M1) and the held
        # keys; `_services` is what the controllers get instead of this object (§3.4).
        self.interaction: InteractionSlot = InteractionSlot()
        self._services = AppServices(self)
        # `can_run` stage 7 (AD-027 §3.5): (command, ctx) -> Refusal | None per mode; none yet.
        self._mode_policies: tuple[Callable[[str, RunContext], Refusal | None], ...] = ()

        # The hold-key gestures (W/E/R, T, G, S, I, Ctrl+B; the gizmo / Tweak drag) as sessions in the slot, their
        # constraint settings and Soft live steps (`controllers.gestures` since AD-027 M6).
        self._gestures = GestureController(self._services, self.tool_manager)
        # The objects: add / delete, mirror pairs, Reference, Apply / Clear, material, their views, cameras and pick
        # caches, the edit-object switch, the object click and the object gesture (`controllers.objects`, AD-027 M7).
        self._objects = ObjectController(self._services, self._gestures)
        # WP-SOFT-01 S2a (AD-020, `PROVISIONAL`, off by default): sticky Soft Selection
        # settings with the semantics of the sticky axis constraint above - they survive commit,
        # cancel, re-arm and Undo and are read once per gesture at `begin()`. A gesture
        # that is armed but has not begun takes a new value; a running one keeps its own -
        # except the radius and the Loop / Ring balance, which a running Soft gesture takes live
        # (AD-020 "Live radius", "Loop / Ring flow").
        # The radius is held in world units (computed on switch-on, on a step change and
        # on scene load) so that the tool and the later preview read one value.
        self._soft: SoftSettings = SoftSettings()
        # Mask Geometry (`mirai.mask`): protection state, not mesh data - no History, cleared on scene load.
        self._masks: dict[ObjectId, VertexMask] = {}
        self._mask_overlay = None
        # Hide / Isolate (`mirai.hidden`): the same kind of state, per edit object.
        self._hiddens: dict[ObjectId, HiddenSet] = {}
        # Polygroups (AD-REGIONS-01): the groups themselves live in the Mesh; this is the name of the active one.
        self._active_regions: dict[ObjectId, str] = {}
        #: Mask by Polygroup (Ctrl+Alt+Shift+M, ZBrush-like): gestures only move the groups of what they act on.
        self.group_mask = False
        self._tints_seen: tuple | None = None  # (mesh, face_regions, viewport) the viewport last got colours for
        # WP-SOFT-01 S2b (AD-020 §5, `PROVISIONAL`): the influence bands shown in the window.
        # `_soft_overlay` is the host-supplied sink (None = headless: no overlay work at all),
        # `_soft_bands` what it currently shows. While a gesture shows its own weights it owns them
        # (`GestureSession.soft_op_running` / `soft_shown`).
        self._soft_overlay = None
        self._soft_bands: SoftBands = EMPTY_BANDS
        # 2026-10-22: the second display mode (face shading) - its sink and the weights it shows
        # ({} = nothing). View state only: never in the scene file or the history. Exactly one of
        # `_soft_bands` / `_soft_shading` is non-empty at a time.
        self._soft_shading_overlay = None
        self._soft_shading: dict[VertexId, float] = {}
        # Shift+S, the symmetry display and its report cache, Re-Symmetrize (AD-027 M1, `controllers.symmetry`).
        self._symmetry = SymmetryController(self._services)

        # WP-06 B6 Follow-up (Artist-Entscheidung Manu 2026-09-28): Undo/Redo
        # stellt jetzt auch die Selection wieder her, nicht nur das Mesh.
        # `HistoryStack` (core, frozen) kennt kein Selection-Konzept und
        # bietet keinen Hook vor/nach push() - deshalb führt Application
        # einen eigenen Stack von (before, after)-Selection-Snapshots parallel
        # zu jedem `history.push()`, den sie selbst auslöst (Split/Edge
        # Connect/Vertex Connect in `_connect_command`, Transform-Commit in
        # `key_release`, Knife-Commit, seit WP-SYM-LAB-03 H3 auch
        # `apply_mesh_change` für Änderungen eines Hosts). `before` =
        # Snapshot unmittelbar vor der Mutation, `after` = Snapshot danach
        # (die von `_connect_command` gesetzte Residue-Auswahl bzw. bei
        # Transformen dieselbe Auswahl, da Move/Rotate/Scale die Selection
        # nicht ändern). Struktur und Semantik spiegeln `HistoryStack`
        # bewusst 1:1 (ein `_record_selection_history()` pro Push, Redo-Stack
        # wird dabei geleert). Ist der Mirror-Stack leer, obwohl History
        # Undo/Redo erlaubt (z. B. künftiger Push-Pfad, der hier noch nicht
        # verdrahtet ist), fällt `_apply_undo_redo()` auf reines Pruning
        # zurück statt zu crashen.
        # AD-021 M1 (§4.6, E-5): an entry is (before, after, mesh_step); `mesh_step` False marks
        # an object step (add object, state change), whose Undo/Redo refreshes the object
        # entries only, not the edit object's render mesh.
        # AD-021 M2-3: a fourth element names the *other* objects whose mesh the step changed
        # (Apply transform on a non-edit object), so their render entries rebuild on Undo/Redo.
        self._selection_undo_stack: list[tuple[tuple, tuple, bool, frozenset]] = []
        self._selection_redo_stack: list[tuple[tuple, tuple, bool, frozenset]] = []
        # Whether the last Undo/Redo touched the edit object's mesh (`_apply_undo_redo`).
        self._last_undo_redo_mesh_step: bool = True

        # SubD preview of the edit mesh (2026-10-23, `mirai.subdivision`): view state only - no
        # document state, no History. Survives scene loads like `DisplayState`; re-attached to every
        # new viewport in `init_scene`.
        self.subdivision: SubdivisionPreview = SubdivisionPreview(set_status=self._set_status)
        # AD-025 Phase 3/4 (`controllers.morph` since AD-027 M4): the morph targets, their weights and mix display
        # (`morph`, view state), the editing view and the weight drag.
        self._morph = MorphController(self._services)
        self.morph: MorphDisplay = self._morph.display
        # AD-025 Phase 4 (H5b): the viewport's replacement surface as a chain - the morph mix, then the
        # SubD preview of the mixed cage (`mirai.surface_chain`); either alone sits in the slot itself.
        self.surface_chain = SurfaceChain((self.morph.provider, self.subdivision.provider))
        self.morph.chain = self.surface_chain
        self.subdivision.chain = self.surface_chain

        # The Knife session (AD-017, `controllers.knife` since AD-027 M3): its settings live in the controller.
        self._knife = KnifeController(self._services)
        # WP-KNIFE-01 UX2b: any Shift key held, as the window reports it
        # (`set_shift_held`). Only the Knife's hover reads it (the midpoint before
        # the click); a click keeps deciding by its press modifiers (A2, AD-019).
        self._shift_held: bool = False
        # Transform modifiers (2026-10-22, Blender): Shift = precision, Ctrl = snap while a transform runs.
        self._ctrl_held: bool = False
        # Alt held during a transform (2026-10-22, `PROVISIONAL`, Manu "Alt halten um zu orbiten"): the motion
        # navigates (Orbit, Alt+Shift Pan) instead of driving the gesture; letting Alt go resumes it.
        self._alt_held: bool = False

        # 2026-10-15 (Playground tools promoted, Manu): the press point of the current LMB
        # gesture (Box/Paint/Tweak decide by it) and the transform a Tweak uses (the last W/E/R
        # pressed; Move until then, below).
        self._press_point: tuple[float, float] | None = None
        # The hold keys of the pointer (Working Pivot, Lasso, light drag), the Working Pivot itself and the press
        # sessions of an LMB press (Box / Paint / Lasso, a gizmo handle press, a refused drag gesture)
        # (`controllers.pointer_tools` since AD-027 M4 / M5).
        self._pointer_tools = PointerToolsController(self._services)
        # WP Ortho / Views (V-1/V-2, 2026-10-28): the virtual orbit angles of the running Alt+LMB orbit (None = no
        # orbit gesture), the standard view the camera is snapped to (None = free) and whether its ortho came from
        # the snap (V-2 "Auto Perspective": a free orbit leaves it) rather than the toggle key.
        self._orbit_virtual: tuple[float, float] | None = None
        self._view_name: str | None = None
        self._ortho_auto: bool = False
        # Transform gizmo (2026-10-21, AD-016 D3; promoted from the Playground, Manu). Off unless the host
        # draws it (`src/main.py` sets `gizmo_enabled`): Labs on `Application` get no invisible handles.
        # The handle press itself is a press session (`pointer_tools.GizmoPress`); `_gizmo_cache` = (key, pivot).
        self.gizmo_enabled: bool = False
        self._gizmo_cache: tuple | None = None
        self._gizmo_frame_cache: tuple | None = None  # (pivot cache key, NormalFrame | None), Normal space
        # The session size of the gizmo (2026-10-28, Manu A4, `GIZMO_SIZE_CYCLE`, not saved).
        self.gizmo_size_name: str = _gizmo.GIZMO_SIZE_DEFAULT
        self.tweak_command: str = commands.MOVE
        # AD-027 §3.4: the command table - one handler per command, built once (`_command_table`).
        self._handlers: Mapping[str, Handler] = self._command_table()

    def _setup_tools(self) -> None:
        """Registriert die Default-Tools (Move/Rotate/Scale/Extrude) im ToolManager."""
        for command, tool_class in (
            (commands.MOVE, tool_for_command(commands.MOVE)),
            (commands.ROTATE, tool_for_command(commands.ROTATE)),
            (commands.SCALE, tool_for_command(commands.SCALE)),
            (commands.EXTRUDE, tool_for_command(commands.EXTRUDE)),
        ):
            if tool_class:
                self.tool_manager.register(command, tool_class)

    def init_scene(
        self,
        geometry_type: str = "cube",
        store_type: type[ResourceStore] = TraceStore,
        obj_path: str | Path | None = None,
        point_overlay_type: type | None = None,
        line_overlay_type: type | None = None,
        face_overlay_type: type | None = None,
        soft_overlay_type: type | None = None,
        soft_shading_overlay_type: type | None = None,
        symmetry_overlay_type: type | None = None,
        scene_path: str | Path | None = None,
        subd_overlay_type: type | None = None,
        mask_overlay_type: type | None = None,
    ) -> None:
        """Initialisiert die Default-Szene (Würfel, OBJ-Import oder Szenendatei).

        `store_type` (Stage A, AD-018 §5/§6): additiv durchgereicht an
        `Viewport(...)`. Default bleibt `TraceStore` (headless, kein GL-
        Kontext nötig) — bestehende Aufrufstellen/Tests bleiben unverändert.
        Ein Entry-Point mit echtem Fenster übergibt hier `GLRenderStore`
        (`src/viewport/gl_render_store.py`), um durch den echten Draw-Pfad
        zu rendern.

        `geometry_type="obj"` (WP-06 Slice B1): lädt `obj_path` über
        `scene_factory.build_core_scene_from_obj` (lazy `examples/`-Import
        dort, siehe dessen Moduldocstring) und übernimmt nur dessen `.mesh`
        — `self.scene` selbst bleibt dieselbe Instanz (Scene-Identität,
        siehe Klassen-/Moduldocstring), damit `Selection`/`HistoryStack`
        an derselben Scene hängen bleiben wie vor `init_scene()`.
        `obj_path` ist bei `geometry_type="obj"` erforderlich.

        AD-021 M1 (§5.2, review R-4): das Laden ist ein Scene-Reset - alle Objekte werden durch
        genau ein neues, bearbeitbares Objekt ersetzt (Name: `cube` bzw. der Dateistamm), das
        Edit-Objekt wird (`scene_objects.reset_scene`); der `scene.mesh`-Setter bedeutet nur
        noch "Mesh dieses Objekts tauschen".

        `geometry_type="file"` (Szenen speichern/laden, Manu 2026-10-15): lädt die Szenendatei
        `scene_path` (`core.serialization`, alle Objekte samt Edit-Objekt) über
        `scene_objects.replace_scene`. Gelesen und geparst wird vor jeder Änderung, ein
        Fehler lässt die Szene also unverändert.

        `point_overlay_type` (WP-06 B2b, E17): gleiches Durchreich-Muster wie
        `store_type`. Default `None` = kein GL-Punkt-Overlay (headless); der
        Entry-Point übergibt `GLPointOverlay`.

        `line_overlay_type` (WP-06 B5a, E38): dasselbe Muster für das
        Edge-Linien-Overlay; der Entry-Point übergibt `GLLineOverlay`. Der
        aktuelle `DisplayState` wird sofort an den neuen Viewport gegeben.

        `face_overlay_type` (WP-06 B5b, E45): dasselbe Muster für selektierte
        bzw. gehoverte Faces; der Entry-Point übergibt `GLTriangleOverlay`.

        `soft_overlay_type` (WP-SOFT-01 S2b, AD-020 §5): dasselbe Muster für die Influence-
        Bänder der Soft Selection; der Entry-Point übergibt `GLSoftBandOverlay`. Es hängt als
        Zusatz-Overlay (`Viewport.add_overlay`, H1) am Viewport, den es nicht kennt. Default
        `None` = keine Band-Arbeit (headless).

        `soft_shading_overlay_type` (2026-10-22): die GL-Senke für den zweiten Anzeige-Modus der
        Soft Selection (Face-Shading, `GLSoftShadingOverlay`); sie hängt wie die Bänder als
        Zusatz-Overlay am Viewport. Es ist immer nur einer der beiden Modi sichtbar. Default `None`.

        `symmetry_overlay_type` (AD-SYM-04 A2, Q-2 = S-2): die GL-Senke für Ebenen-Umriss und
        Problem-Marker; der Entry-Point übergibt `GLSymmetryOverlay`. `Application` hängt sie
        in ihr eigenes `SymmetryDisplay` (`mirai.symmetry_display`), das als Zusatz-Overlay nach
        den Bändern am Viewport hängt und während eines Transforms aufschiebt. Default `None` =
        keine Symmetrie-Anzeige (headless).

        `subd_overlay_type` (2026-10-23): die GL-Senke der SubD-Linien (Käfig / Isolinien,
        `mirai.subdivision.gl_lines.GLSubdLineOverlay`). Die SubD-Vorschau (`self.subdivision`) hängt
        sich an jeden neuen Viewport; ohne Senke rechnet sie headless dieselben Segmente."""
        self._morph.drop_view()  # the reset replaces every object, the view included
        if geometry_type in ("cube", "obj"):
            reset_scene(self.scene, *self._build_mesh(geometry_type, obj_path))
        elif geometry_type == "file":
            if scene_path is None:
                raise ValueError('geometry_type="file" requires scene_path')
            loaded = scene_from_json(Path(scene_path).read_text(encoding="utf-8"))
            replace_scene(self.scene, loaded)
        self._soft_refresh_radius()  # a scene load is one of the three radius events

        # Gate 7: Produktionsintegration — verbindet Application.camera mit
        # dem V0.2-Viewport. Die dieselbe OrbitCamera-Instanz wird über
        # Duck-Typing an RenderMesh.bind_camera() übergeben (siehe
        # VIEWPORT_V02_ARCHITECTURE.md §9). Es entsteht KEINE zweite
        # Kamera-Repräsentation.
        self.viewport = Viewport(
            self.scene.mesh,
            selection=self.scene.selection,
            store_type=store_type,
            point_overlay_type=point_overlay_type,
            line_overlay_type=line_overlay_type,
            face_overlay_type=face_overlay_type,
        )
        self.viewport.bind_camera(self.camera)
        self._soft_overlay = None
        self._soft_bands = EMPTY_BANDS
        self._soft_shading_overlay = None
        self._soft_shading = {}
        self._symmetry.reset_reports()
        if soft_overlay_type is not None:
            self._soft_overlay = soft_overlay_type()
            self.viewport.add_overlay(self._soft_overlay)
        if soft_shading_overlay_type is not None:
            self._soft_shading_overlay = soft_shading_overlay_type()
            self.viewport.add_overlay(self._soft_shading_overlay)
        self._masks.clear()  # their IDs belong to the old meshes
        self._hiddens.clear()
        self._active_regions.clear()
        self._pick_cache.set_hidden(())
        self._mask_overlay = None
        if mask_overlay_type is not None:
            self._mask_overlay = mask_overlay_type()
            self.viewport.add_overlay(self._mask_overlay)
        self._soft_apply_look()
        if self._soft_overlay is not None or self._soft_shading_overlay is not None:
            self._soft_preview_refresh()  # a scene load is one of the preview triggers (E3)
        self._symmetry.attach_display(symmetry_overlay_type)
        self.surface_chain.attach(self.viewport)
        self.subdivision.attach(
            self.viewport, subd_overlay_type() if subd_overlay_type is not None else None
        )
        self.morph.attach(self.viewport)
        self._morph.ab.clear()
        self._objects.pick_caches = {}
        self._objects.sync_views()
        self._apply_display()

    @staticmethod
    def _build_mesh(geometry_type: str, obj_path: str | Path | None) -> tuple[Mesh, str, str | None]:
        """Das Mesh einer Szene bzw. eines hinzugefügten Objekts, sein Objektname und seine Textur
        (AD-026: die einer OBJ-Datei, `loaders.obj_loader.find_texture`; sonst None)."""
        from .scene_factory import PRIMITIVES

        if geometry_type in PRIMITIVES:
            return PRIMITIVES[geometry_type](), geometry_type, None
        if geometry_type == "obj":
            if obj_path is None:
                raise ValueError('geometry_type="obj" requires obj_path')
            return Application._load_obj(Path(obj_path))
        raise ValueError(f"unknown geometry_type {geometry_type!r}")

    @staticmethod
    def _load_obj(path: Path) -> tuple[Mesh, str, str | None]:
        from loaders.obj_loader import find_texture, load_obj  # lazy - `examples/` on sys.path, see scene_factory

        from .scene_factory import mesh_from_obj_data

        data = load_obj(path)
        texture = find_texture(path, data) if data.has_uvs else None
        return mesh_from_obj_data(data), path.stem, None if texture is None else str(texture.resolve())

    # -- Objects (AD-021; `controllers.objects` since AD-027 M7) ----------------------------------------

    def add_reference(
        self,
        geometry_type: str = "cube",
        obj_path: str | Path | None = None,
        name: str | None = None,
    ) -> SceneObject | None:
        """Fügt ein Objekt als Referenz hinzu, statt die Szene zu ersetzen (AD-021 M1, A-1;
        Q-10: Shift+Klick im `SPACE`-Menü).

        Ein Undo-Schritt (Q-3); die Kamera bleibt stehen (Q-9); Edit-Objekt, Auswahl und das
        Mesh des Edit-Objekts bleiben unberührt. Abgelehnt (Statuszeile, None), solange eine
        Interaktion die Tasten hält. Ein Ladefehler fliegt wie bei `init_scene` (der Aufrufer
        meldet ihn). Gibt das neue Objekt zurück."""
        if self.viewport is None:
            raise RuntimeError("add_reference() before init_scene()")
        if self._objects.refused_during_interaction("Add object") or self._objects.layer_refused("add_reference", ()):
            return None
        mesh, default_name, texture = self._build_mesh(geometry_type, obj_path)
        return self._objects.add_reference(mesh, name or default_name, texture)

    def add_primitive(self, kind: str, name: str | None = None) -> SceneObject | None:
        """Add Mesh (Track A1, 2026-10-23, `PROVISIONAL`; `scene_factory.PRIMITIVES`: plane, cube,
        sphere, cylinder): ein neues, **bearbeitbares** Objekt am Ursprung - keine Referenz.

        Wechselwirkung mit Modus und Edit-Objekt: die Application geht in Modus `4`, das neue
        Objekt ist die einzige Objekt-Auswahl (sichtbar hervorgehoben, W/E/R bewegen es sofort) und
        die Komponenten-Auswahl wird geleert; das **Edit-Objekt bleibt** - `1`/`2`/`3` machen das
        neue Objekt über die Q-5-Geste (ein ausgewähltes Normal-Objekt) zum Edit-Objekt. Ein
        Undo-Schritt (`AddObjectCommand` + ein Spiegel-Eintrag): Undo entfernt das Objekt und stellt
        Modus, Auswahl und Edit-Objekt davor wieder her, Redo setzt dieselbe Instanz (gleiche
        ObjectId) wieder ein. Abgelehnt (Statuszeile, None), solange eine Interaktion die Tasten
        hält; ein unbekannter `kind` fliegt als ValueError. Gibt das neue Objekt zurück."""
        if self.viewport is None:
            raise RuntimeError("add_primitive() before init_scene()")
        from .scene_factory import PRIMITIVES

        if kind not in PRIMITIVES:
            raise ValueError(f"unknown primitive {kind!r}")
        return self._objects.add_mesh_object(
            lambda: PRIMITIVES[kind](), name or unique_object_name(self.scene, kind), f"Add {kind}"
        )

    def import_obj(self, path: str | Path) -> SceneObject | None:
        """OBJ import (SPACE menu, `src/obj_files.py`): the file becomes a new editable object like an
        Add-Mesh primitive (same Undo step, selection and status behaviour), named after the file.
        Parse errors fly as exceptions (`ObjLoadError`, OSError) before the scene is touched.

        AD-026: the file's UVs come along as the mesh's face-corner UVs, and its texture (`map_Kd` of
        its MTL file, else an image of the same name beside it) becomes the object's texture."""
        if self.viewport is None:
            raise RuntimeError("import_obj() before init_scene()")
        path = Path(path)
        loaded = {}

        def build() -> Mesh:
            mesh, _name, loaded["texture"] = self._load_obj(path)
            return mesh

        obj = self._objects.add_mesh_object(build, unique_object_name(self.scene, path.stem), "Import OBJ")
        if obj is not None and loaded.get("texture"):
            obj.texture = loaded["texture"]
            self._objects.sync_views()
            self._set_status(f"{self.status_message} - texture {Path(obj.texture).name}")
        return obj

    def export_obj(self, path: str | Path) -> bool:
        """OBJ export (SPACE menu): the edit object in world space (object transform applied), one
        `o` record. True = written. Refused during an interaction like `save_scene_file`."""
        return self._objects.export_obj(path)

    def mirror_copy(self, axis: str = "X") -> SceneObject | None:
        """Mirror copy of the one selected object, paired with it (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.5, the
        Shift+M menu): `ObjectController.mirror_copy`."""
        return self._objects.mirror_copy(axis)

    def pair_selected(self, axis: str = "X") -> bool:
        """Pair two selected objects (proposal §5.5): `ObjectController.pair_selected`."""
        return self._objects.pair_selected(axis)

    def break_mirror_pairs(self) -> bool:
        """Break the pairs of the selected objects (proposal §5.5): `ObjectController.break_mirror_pairs`."""
        return self._objects.break_mirror_pairs()

    def resync_mirror_pairs(self) -> bool:
        """Re-sync the pairs of the selected objects (proposal §5.7): `ObjectController.resync_mirror_pairs`."""
        return self._objects.resync_mirror_pairs()

    def toggle_texture_display(self) -> bool:
        """Textures on/off (SPACE menu row, `src/obj_files.py`): pure view state, no Undo step.
        Returns the new state."""
        return self._objects.toggle_texture_display()

    @property
    def reference_ghost(self) -> bool:
        """AD-021 M2-0 (§7.3 RD-2): all References drawn as Ghost (`Alt+D`); display state, not an Undo step,
        kept across scene loads like `DisplayState`."""
        return self._objects.reference_ghost

    @reference_ghost.setter
    def reference_ghost(self, value: bool) -> None:
        self._objects.reference_ghost = value

    @property
    def last_edit_switch_seconds(self) -> float:
        """AD-021 M2-4: how long the last Q-5 switch of the edit object took (s, `time.perf_counter`; measured,
        not optimised - the viewport rebuilds the entries of both objects)."""
        return self._objects.last_edit_switch_seconds

    def _follow_edit_object(self) -> None:
        """Everything that hangs on the edit object's mesh follows `scene.edit_object_id`. Called
        by `ObjectController.set_edit_object`, by Delete of the edit object, and by Undo/Redo of a step whose
        command changed the edit object itself (`DeleteObjectsCommand`, `AddObjectCommand`): the
        scene is already switched there, only the view is behind. A morph target's editing view lives
        while it is the edit object: it closes here when another object became the edit object."""
        closed = self._morph.close_if_left()
        if closed is not None:
            self._masks.pop(closed, None)
            self._hiddens.pop(closed, None)
        obj = self.scene.edit_object
        self._pick_cache.invalidate()
        self.selection.hovered = None
        if self.viewport is not None:
            self.viewport.remove_object_entry(obj.id)
            self.viewport.set_edit_mesh(obj.mesh, object_space.model_matrix(obj))
        self._tints_seen = None  # the new RenderMesh has no region colours yet
        self._hidden_push()  # the new edit object keeps its own hidden set and mask
        self._soft_refresh_radius()
        self._objects.sync_views()

    def frame_scene(self) -> None:
        """Richtet die Kamera auf die Bounds des aktuellen Meshs aus (WP-06 B1).

        Reiner View-Effekt (wie `OrbitCamera.frame_on_bounds`): kein Mesh-
        Wechsel, kein History-Eintrag. No-op vor `init_scene()` oder wenn
        das Mesh keine Vertices hat (portiert aus `playground/app.py::
        _frame_camera`, jetzt als Production-API in `Application`)."""
        if self.viewport is None:
            return
        mesh = self.scene.mesh
        if not mesh.all_vertex_ids():
            return
        center, radius = mesh_center_and_radius(mesh)
        # AD-021 M2-1: the edit object's bounds in world.
        center, radius = object_space.world_center_and_radius(
            self.scene.edit_object, center, radius
        )
        self.camera.frame_on_bounds(center, radius)

    def load_scene(
        self,
        geometry_type: str = "cube",
        store_type: type[ResourceStore] = TraceStore,
        obj_path: str | Path | None = None,
        point_overlay_type: type | None = None,
        line_overlay_type: type | None = None,
        face_overlay_type: type | None = None,
        soft_overlay_type: type | None = None,
        soft_shading_overlay_type: type | None = None,
        symmetry_overlay_type: type | None = None,
        scene_path: str | Path | None = None,
        subd_overlay_type: type | None = None,
        mask_overlay_type: type | None = None,
    ) -> None:
        """Lädt eine Szene zur Laufzeit und setzt den mesh-gebundenen Zustand
        zurück (temporärer Scene-Loader `src/scene_menu.py`, PROVISIONAL).

        `init_scene(...)` tauscht Mesh und Viewport, lässt aber Selection,
        History und Hover der *alten* Szene stehen — deren IDs gehören zum
        alten Mesh. Deshalb danach:
        - Auswahl leeren (keine Geister-IDs im neuen Mesh);
        - frische `HistoryStack` für `scene.history` UND `app.history`
          (derselbe Alias wie in `__init__`, `core/history.py` bleibt
          unangetastet) plus die Selection-Mirror-Stacks leeren, damit
          Undo/Redo nach dem Wechsel keine Einträge der alten Szene sieht;
        - Hover löschen und den Pick-Cache invalidieren (der Cache hängt an
          der Application, nicht am Viewport, und die Kamera-Revision bleibt
          nach dem Tausch gleich);
        - Viewport-Größe/Aspect erneut melden (neuer Viewport) und die
          Kamera neu ausrichten;
        - die Soft-Selection-Vorschau neu rechnen: `init_scene` hat sie noch mit
          der *alten* Auswahl gerechnet, die jetzt geleert ist.
        Alle GL-Backends (`*_type`, auch `soft_overlay_type` und `symmetry_overlay_type`) gehen unverändert
        an `init_scene` — dort ist das Wiring die einzige Stelle.
        Kein History-Eintrag, keine Core-Änderung; der Aufrufer setzt bei
        Bedarf selbst einen Namen-Status (`set_status`)."""
        self.init_scene(
            geometry_type,
            store_type=store_type,
            obj_path=obj_path,
            point_overlay_type=point_overlay_type,
            line_overlay_type=line_overlay_type,
            face_overlay_type=face_overlay_type,
            soft_overlay_type=soft_overlay_type,
            soft_shading_overlay_type=soft_shading_overlay_type,
            symmetry_overlay_type=symmetry_overlay_type,
            scene_path=scene_path,
            subd_overlay_type=subd_overlay_type,
            mask_overlay_type=mask_overlay_type,
        )
        self.selection.clear()
        self.selection.clear_objects()
        self._pointer_tools.working_pivot = None  # its object id belongs to the old scene
        self.history = TranslatingHistory()
        self.scene.history = self.history
        self._selection_undo_stack.clear()
        self._selection_redo_stack.clear()
        self._set_hovered(None)
        self._pick_cache.invalidate()
        self._soft_preview_refresh()
        self.set_viewport_size(self.viewport_width, self.viewport_height)
        self.frame_scene()

    def save_scene_file(self, path: str | Path) -> bool:
        """Schreibt die Szene als Szenendatei (`core.serialization`, Manu 2026-10-15; Strg+S
        und das SPACE-Menü, `src/scene_files.py`). True = geschrieben.

        Abgelehnt (Statuszeile, False), solange eine Interaktion die Tasten hält: mitten in
        W/E/R/T oder einer Knife-Session stünde ein halber Zustand im Mesh. Atomar über eine
        Nachbardatei, damit ein Fehler die alte Datei nicht zerstört. Kein History-Eintrag;
        Selection, History und Kamera werden nicht gespeichert (Format, V1_SPEC §12)."""
        owner = self.interaction_owner
        if owner is not None:
            self._set_status(f"Save scene: not while the {owner} interaction runs")
            return False
        path = Path(path)
        text = scene_to_json(self._morph.document_scene())
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        self._set_status(f"Saved scene: {path}")
        return True

    def dispatch_command(
        self, command: str, context: Optional[dict] = None, **params
    ) -> bool:
        """Dispatchet ein Command (True = wurde behandelt).

        Tool-Commands → ToolManager (Pattern A: nur aktivieren; Pattern B:
        mit `context` sofort `begin(**context)`).
        Undo/Redo → History.
        Display-Commands → `DisplayState` + Viewport (WP-06 B5a, E42).
        Modus-Commands → `Selection.mode` (WP-06 B5b, E43).
        Symmetrie-Zyklus → Definition des Meshs (AD-SYM-04 A1, `SymmetryController.cycle`).
        Alles andere → False (bewusst minimal gehalten).

        AD-027 M2: the gated public entry - `can_run(command, RunContext("api"))` first, with the gates
        the key has (a GUI button, a script); a refusal posts its text and returns False. `Application`'s
        own calls, which run after their gate, use `_execute`.
        """
        self.flush_hover()
        ctx = RunContext("api")
        refusal = self.can_run(command, ctx)
        if refusal is not None:
            return self._refused(refusal)
        # AD-017 history isolation: during a Knife session never the global history - also not through the API.
        grabbed = self.interaction.grab(Command(command, ctx))
        if grabbed is not PASS:
            return grabbed
        return self._execute(command, context, ctx)

    def _execute(self, command: str, context: Optional[dict] = None, ctx: RunContext = _API) -> bool:
        """The command's handler, ungated (AD-027 M2): called after `can_run` (or the gate of the path that
        reached it)."""
        self.flush_hover()
        handler = self._handlers.get(command)
        return False if handler is None else handler(command, ctx, context)

    def _command_table(self) -> Mapping[str, Handler]:
        """AD-027 §3.4: every command `Application` runs, with its one handler `(command, ctx, context) -> bool`
        (`context`: the API's tool context). A static table, not a plugin system: nothing registers at runtime
        (AD-013 H2 alternative E stays rejected). Where key and API differ today both stay, keyed on `ctx.source`
        (§3.3): a gesture key arms its gesture, the API activates its tool; Undo from a key posts its status and
        rebuilds the view; the hold keys, the constraint keys, Cancel and the session switches run from a key only."""
        table: dict[str, Handler] = {}

        def add(names, handler: Handler) -> None:
            for name in names:
                assert name not in table, f"two handlers for {name!r}"
                table[name] = handler

        def key_only(run: Callable[[str, Input], bool]) -> Handler:
            return lambda command, ctx, context: ctx.source == "key" and run(command, ctx.input)

        def plain(run: Callable[[str], bool]) -> Handler:
            return lambda command, ctx, context: run(command)

        objects, gestures, tools = self._objects, self._gestures, self._pointer_tools
        add(MORPH_COMMANDS, self._run_morph)
        add(TRANSFORM_COMMANDS, self._run_gesture)
        add((commands.UNDO, commands.REDO), self._run_undo_redo)
        add(_SESSION_SWITCH_COMMANDS, key_only(lambda command, input: self._session_switch(command)))
        add((commands.LASSO_ARM,), key_only(lambda command, input: tools.lasso.arm(input.value)))
        add((commands.PIVOT_PLACE,), key_only(lambda command, input: tools.pivot.arm(input.value)))
        add((commands.LIGHT_DRAG,), key_only(lambda command, input: tools.light.arm(input.value)))
        add(CONSTRAINT_SPACES, key_only(lambda command, input: gestures.constrain(CONSTRAINT_SPACES[command])))
        add((commands.CANCEL,), key_only(lambda command, input: self._cancel()))
        add((commands.TOGGLE_TRANSFORM_SPACE,), plain(lambda command: gestures.toggle_orientation()))
        add((commands.TOGGLE_ORTHO,), plain(lambda command: self._toggle_ortho()))
        add(_DISPLAY_COMMANDS, plain(self._display_command))
        add(_LOOK_COMMANDS, plain(self._look_command))
        add(_SOFT_COMMANDS, plain(self._soft_command))
        add(SUBD_COMMANDS, plain(self._subd_command))
        add(_MODE_COMMANDS, plain(lambda command: self._set_selection_mode(_MODE_COMMANDS[command])))
        add(PLACEMENT_COMMANDS, plain(objects.placement_command))
        add((commands.TOGGLE_REFERENCE,), plain(lambda command: objects.reference_command()))
        add((commands.CONNECT,), plain(lambda command: self._connect_command()))
        add(_REMOVAL_COMMANDS, plain(self._run_removal))
        add((commands.COLLAPSE,), plain(lambda command: self._collapse_command()))
        add((commands.BORDER_SELECT,), plain(lambda command: self._border_select()))
        add((commands.CAP,), plain(lambda command: self._cap_command()))
        add((commands.SYMMETRY_CYCLE,), plain(lambda command: self._symmetry.cycle()))
        add((commands.RESYMMETRIZE,), plain(lambda command: self._symmetry.open()))
        add(_MASK_COMMANDS, plain(self._mask_command))
        add(_HIDE_COMMANDS, plain(self._hide_command))
        add(_REGION_COMMANDS, plain(self._region_command))
        add((commands.EDGE_LOOP, commands.EDGE_RING), plain(self._loop_select))
        add((commands.LOOP_INSERT,), plain(lambda command: self._loop_insert()))
        add(_SELECTION_STEP_COMMANDS, plain(self._selection_step))
        return MappingProxyType(table)

    def _run_morph(self, command: str, ctx: RunContext, context: Optional[dict]) -> bool:
        """The morph keys (`MorphController.command`); N from a key holds the weight drag."""
        if command == commands.MORPH_WEIGHT_DRAG and ctx.source == "key":
            return self._morph.weight_hold.arm(ctx.input.value)
        return self._morph.command(command)

    def _run_gesture(self, command: str, ctx: RunContext, context: Optional[dict]) -> bool:
        """A hold-key gesture: a key arms it (W/E/R also set the tool the gizmo uses - a tap sets it, "tool set");
        the API activates its tool, with `context` begun at once (Pattern B), as before."""
        if ctx.source == "key":
            if command in TWEAK_TRANSFORMS:
                self.tweak_command = command
            return self._transform_arm(command, ctx.input.value)
        if tool_for_command(command) is None:
            return False
        return self.tool_manager.activate(command, context=context)

    def _run_undo_redo(self, command: str, ctx: RunContext, context: Optional[dict]) -> bool:
        """E23: from a key a gesture that is only armed is disarmed first (a begun one refused it in `can_run`), and
        the step posts its status and rebuilds the view; from the API only the step."""
        if ctx.source != "key":
            self._apply_undo_redo(command)
            return True
        gesture = self._gesture
        if gesture is not None:
            gesture.end()
            self._refresh_hover()
        return self._undo_redo(command)

    def _run_removal(self, command: str) -> bool:
        """Delete / Dissolve; in mode `4` Delete removes the selected objects."""
        if command == commands.DELETE and self.selection.mode is SelectionMode.OBJECT:
            return self._objects.delete_selected()
        return self._removal_command(command)

    # -- Symmetry (AD-SYM-04 A1-A3; `controllers.symmetry` since AD-027 M1) ------------------------

    @property
    def resymmetrize_preview(self) -> ResymPlan | None:
        """The open Re-Symmetrize preview (its plan), None = closed."""
        return self._symmetry.preview_plan()

    @property
    def symmetry_display(self) -> SymmetryDisplay | None:
        """Plane outline and problem markers (AD-SYM-04 A2), None without a
        `symmetry_overlay_type` (headless)."""
        return self._symmetry.display

    def toggle_symmetry_display(self) -> bool | None:
        """Shift+Ctrl+S: show / hide the symmetry plane and the seam / problem markers (display only,
        the symmetry definition is untouched). Returns the new visibility, None without a display."""
        return self._symmetry.toggle_display()

    # -- Component-Modi (WP-06 B5b) ---------------------------------------------

    def _set_selection_mode(self, mode: SelectionMode) -> bool:
        """1/2/3 wie Playground `window.py`: Modus setzen, Auswahl leeren, Hover
        löschen (R-SEL-2). Auch der bereits aktive Modus leert die Auswahl
        (Playground-Verhalten). Kein History-Eintrag; der Hover kommt mit der
        nächsten Mausbewegung im neuen Modus zurück. `4` (AD-021 M1) genauso; `clear()`
        leert nur die Komponenten, die Objekt-Auswahl bleibt (§4.4).

        AD-021 M2-4 (Q-5): from `4` to `1`/`2`/`3` with exactly one Normal object selected, that
        object becomes the edit object first (E-14; order §4.4: read `objects`, set the edit
        object, clear the components). No Undo step; the next step's mirror snapshot carries it.
        Several objects or a Reference selected: no switch, the status line says why."""
        note = ""
        if mode is not SelectionMode.OBJECT and self.selection.mode is SelectionMode.OBJECT:
            note = self._objects.edit_from_selection()
        self.selection.mode = mode
        self.selection.clear()
        self.selection.hovered = None
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        text = f"Mode: {mode.name.capitalize()}{note}"
        edit = self.scene.edit_object
        if mode is not SelectionMode.OBJECT and not object_space.is_identity(edit.transform):
            # AD-021 Q-6 (status line first, L-4): the edit object carries a placement.
            text += f" · object {edit.name!r} is placed (object level)"
        self._set_status(text)
        self._objects.sync_highlight()
        return True

    # -- Contextual C: Split / Edge Connect / Vertex Connect (WP-06 B6, AD-017) --

    def _connect_command(self) -> bool:
        """`C`: resolves the selection context (`resolve_c_context`, same
        dispatch as the Playground `window.py`) and applies Split / Edge
        Connect / Vertex Connect through the shared `mirai.topology`
        implementation; an empty selection begins a Knife session (WP-06
        B7, `KnifeController.begin`). Mutates only through
        `Mesh.split_edge`/`Mesh.connect_vertices` (ARCH-02); exactly one
        `MeshDeltaCommand` per success, mesh and history untouched on
        rejection or no-op. Each success branch reports the topology change
        through `_notify_topology_changed()`, which also re-anchors the hover
        (the hovered edge/face handle can be gone after Split/Connect), and
        records the pre-mutation selection for Undo/Redo restore (WP-06 B6
        follow-up, `_record_selection_history`).

        Whenever a symmetry definition is set, the selection is first
        canonicalised to one side (A2 = A, AD-SYM-03 §6) on a temporary value,
        for every context; that one canonical value is resolved in the one
        `resolve_c_context` call and read by the branches. A host's
        `command_gate.refused_contexts` (H2 amendment G-2) is checked right
        after that call, before any branch: a listed context posts its text and
        returns False with mesh, history and `self.selection` untouched.

        A declared Connect context with a definition set runs its coordinator
        (`_connect_op`) inside the same single transaction; a `SymmetryRefusal`
        restores the mesh, posts its text, records no history entry and leaves
        the selection untouched. Under symmetry Edge Connect selects the created
        edges on the side(s) where the live selection had elements (only the
        plane -> the normal's side; created edges on the plane stay;
        `residue_sides`, Artist ITERATE 2026-10-08), Split (slice 4) the same
        for its new vertices (engineering default, judged in the practical
        test; a seam edge's new vertex lies on the plane and stays); Vertex
        Connect keeps the live selection (AD-017 residue)."""
        selection = self.selection
        effective = self._canonical_c_selection()
        ctx = resolve_c_context(effective)
        if self._context_refuses(ctx) or self._layer_gate_refuses(ctx):
            return False

        if ctx is CContext.SPLIT:
            mesh = self.scene.mesh
            # Taken from the live selection before the transaction (and before canonicalisation
            # reaches the mesh): the sides the artist worked on.
            sides = (
                residue_sides(mesh, selection.edges, mesh.edge_vertices)
                if self._connect_coordinator(ctx) is not None
                else None
            )

            def split_plain(mesh: Mesh, edge_ids: set) -> list:
                (edge_id,) = edge_ids
                return [mesh.split_edge(edge_id)[0]]

            def residue(created) -> None:
                kept = set(created)
                if sides is not None:
                    kept = on_residue_sides(mesh, kept, sides, lambda v: (v,))
                selection.mode = SelectionMode.VERTEX
                selection.clear()
                selection.add(kept)

            try:
                self._mesh_transaction(
                    "Split Edge",
                    lambda mesh: self._connect_op(ctx, split_plain)(mesh, set(effective.edges)),
                    on_applied=residue,
                )
            except SymmetryRefusal as exc:
                self._set_status(str(exc))
                return False
            self._set_status("Split")
            return True

        if ctx is CContext.EDGE_CONNECT:
            return self._edge_connect(
                selection.edges, effective.edges, EDGE_CONNECT_LABEL, "Connect Edges"
            )

        if ctx is CContext.VERTEX_CONNECT:
            # Residue (AD-017): the original vertices stay selected, Vertex
            # mode unchanged — no `on_applied`, the selection is not touched.
            try:
                outcome = self._mesh_transaction(
                    VERTEX_CONNECT_LABEL,
                    lambda mesh: self._connect_op(ctx, apply_connect_vertices)(
                        mesh, set(effective.vertices)
                    ),
                )
            except (VertexConnectError, SymmetryRefusal) as exc:
                self._set_status(str(exc))
                return False
            if not outcome.changed:
                self._set_status("Vertex Connect: nothing connectable")
                return False
            self._set_status("Vertex Connect")
            return True

        if ctx is CContext.KNIFE:
            return self._knife.begin(self._connect_coordinator(ctx))

        # CContext.NONE: 1 vertex, Face mode, or another combination with no
        # C meaning (AD-017 §7).
        self._set_status("C: nothing to do here")
        return False

    def _edge_connect(self, live_edges, effective_edges, description: str, status: str) -> bool:
        """Edge Connect of `effective_edges` (canonical under symmetry) as one transaction; the
        created edges become the selection, under symmetry on the sides `live_edges` had
        (`residue_sides`). Shared by `C` (2+ edges) and Loop Insert (`I`, the ring's edges)."""
        ctx = CContext.EDGE_CONNECT
        selection = self.selection
        mesh = self.scene.mesh
        # Taken from the live edges before the transaction (and before canonicalisation
        # reaches the mesh): the sides the artist worked on.
        sides = (
            residue_sides(mesh, set(live_edges), mesh.edge_vertices)
            if self._connect_coordinator(ctx) is not None
            else None
        )

        def residue(result) -> None:
            created = set(result.created)
            if sides is not None:
                created = on_residue_sides(mesh, created, sides, mesh.edge_vertices)
            selection.clear()
            selection.add(created)

        def mutate(mesh):
            result = self._connect_op(ctx, apply_connect_edges)(mesh, set(effective_edges))
            if guarded and not all(mesh.is_valid_face(f) for f in guarded):
                # e.g. a ring that closes around the hidden part (or a mirrored ring) would cut a hidden quad
                raise TopologyToolError(f"{description}: hidden geometry in the way (Alt+H shows all)")
            return result

        hidden = self._hidden
        guarded = (
            [f for f in mesh.all_face_ids() if hidden.is_hidden_face(mesh, f)] if hidden else []
        )
        try:
            self._mesh_transaction(description, mutate, on_applied=residue)
        except (TopologyToolError, SymmetryRefusal) as exc:
            self._set_status(str(exc))
            return False
        self._set_status(status)
        return True

    def _connect_op(self, context: CContext, plain: Callable) -> Callable:
        """The mutation `_connect_command` runs for a declared context: the coordinator
        declared for `context` (`mirai.symmetry_declarations`, AD-SYM-03 slices 3b/4) whenever a
        symmetry definition is set — in MARK as in BLOCK, its refusals are part of a supported
        operation, not a gate (H2 amendment, "Runtime refusals are not G-3") — otherwise the
        unchanged `plain` function. Both run inside the caller's one `_mesh_transaction`."""
        coordinator = self._connect_coordinator(context)
        return plain if coordinator is None else coordinator

    def _connect_coordinator(self, context: CContext) -> Callable | None:
        """The coordinator that runs `context` now: declared and a definition set; else None."""
        if self.scene.mesh.symmetry_definition is None:
            return None
        return symmetry_declarations.C_CONTEXT_COORDINATORS.get(context)

    def _canonical_c_selection(self) -> Selection:
        """The selection `C` reads (AD-SYM-03 §6 A2 = A; AD-013 H2 amendment,
        canonicalisation): without a symmetry definition the live selection;
        with one, a temporary copy in which each mirror pair counts once
        (`canonical_*` keep the normal's side). Never written back: a refused
        or failed `C` leaves `self.selection` (mode and every id set) as it was.
        This is the meaning of `C` under symmetry, not a support policy (G-3)."""
        mesh = self.scene.mesh
        selection = self.selection
        if mesh.symmetry_definition is None:
            return selection
        index = SymmetryIndex(mesh)
        effective = Selection()
        effective.mode = selection.mode
        effective.vertices = canonical_vertices(index, selection.vertices)
        effective.edges = canonical_edges(index, selection.edges)
        effective.faces = canonical_faces(index, selection.faces)
        return effective

    def _context_refuses(self, context: CContext) -> bool:
        """H2 amendment G-2: True (and the refusal posted as status) if
        `command_gate.refused_contexts` lists the resolved `C` context. The
        third gate site, below `dispatch_command`; one `None` test or one
        empty lookup with the defaults."""
        gate = self.command_gate
        if gate is None:
            return False
        text = gate.context_refusal(context)
        if text is None:
            return False
        self._set_status(text)
        return True

    # -- Loop tools (2026-10-15, promoted from the Playground, Manu) ----------------------
    #
    # Shift+L / Shift+R add the edge loops / rings of the selected edges (else of the hovered
    # edge) to the selection; I inserts a loop through the ring of each such edge (the ring's
    # edges through the shared Edge Connect, so the symmetric coordinator of `C` covers it);
    # hold G slides the selected loop(s) (`mirai.topology.loop_slide`). Edge mode only;
    # `PROVISIONAL` (no Artist verdict for the loop tools yet).

    def _loop_seed_edges(self, label: str) -> set[EdgeId] | None:
        """The selected edges, else the hovered edge; None (status posted) outside edge mode
        or without either."""
        selection = self.selection
        mesh = self.scene.mesh
        if selection.mode is not SelectionMode.EDGE:
            self._set_status(f"{label}: edge mode needed (2)")
            return None
        edges = {e for e in selection.edges if mesh.is_valid_edge(e)}
        hovered = selection.hovered
        if not edges and isinstance(hovered, EdgeId) and mesh.is_valid_edge(hovered):
            edges = {hovered}
        if not edges:
            self._set_status(f"{label}: select or hover an edge")
            return None
        return edges

    def _loop_select(self, command: str) -> bool:
        label = "Edge Loop" if command == commands.EDGE_LOOP else "Edge Ring"
        seeds = self._loop_seed_edges(label)
        if seeds is None:
            return False
        walk = edge_loop if command == commands.EDGE_LOOP else edge_ring
        mesh = self.scene.mesh
        blocked = self._hidden.vertices()  # a loop / ring ends at hidden geometry, it does not run through it
        found: set[EdgeId] = set()
        for edge in sorted(seeds):
            if edge in found:
                continue
            try:
                found.update(walk(mesh, edge, blocked).edges)
            except LoopRingError as exc:
                self._set_status(f"{label}: {exc}")
                return False
        selection = self.selection
        before = len(selection.edges)
        selection.add(self._drop_hidden(found))
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        added = len(selection.edges) - before
        self._set_status(f"{label}: {len(selection.edges)} edges selected (+{added})")
        return True

    # -- Selection steps (WP Toolbox Gaps A1, Manu 2026-10-23) ---------------------------
    #
    # Ctrl++ / Ctrl+- grow / shrink the selection in the active mode; Shift+Up / Shift+Down grow
    # / shrink the selected loop pieces at both ends; Shift+Right / Shift+Left move them to the
    # parallel loop on that screen side. Like Shift+L: a selection change, no History step;
    # the loop steps need edge mode. Not mirrored under symmetry (no selection command is);
    # `PROVISIONAL`.

    def _selection_step(self, command: str) -> bool:
        selection = self.selection
        mesh = self.scene.mesh
        mode = selection.mode
        if command in (commands.SELECT_GROW, commands.SELECT_SHRINK):
            label = "Grow" if command == commands.SELECT_GROW else "Shrink"
            current = {
                SelectionMode.VERTEX: selection.vertices,
                SelectionMode.EDGE: selection.edges,
                SelectionMode.FACE: selection.faces,
            }[mode]
            valid = {
                SelectionMode.VERTEX: mesh.is_valid_vertex,
                SelectionMode.EDGE: mesh.is_valid_edge,
                SelectionMode.FACE: mesh.is_valid_face,
            }[mode]
            ids = {i for i in current if valid(i)}
            if not ids:
                self._set_status(f"{label}: nothing selected")
                return False
            step = selection_steps.grow if command == commands.SELECT_GROW else selection_steps.shrink
            return self._apply_selection_step(label, step(mesh, mode, ids))
        labels = {
            commands.LOOP_GROW: "Loop grow",
            commands.LOOP_SHRINK: "Loop shrink",
            commands.LOOP_NEXT: "Next loop",
            commands.LOOP_PREVIOUS: "Previous loop",
        }
        label = labels[command]
        if mode is not SelectionMode.EDGE:
            self._set_status(f"{label}: edge mode needed (2)")
            return False
        edges = {e for e in selection.edges if mesh.is_valid_edge(e)}
        if not edges:
            self._set_status(f"{label}: select edges of a loop")
            return False
        blocked = self._hidden.vertices()
        if command == commands.LOOP_GROW:
            return self._apply_selection_step(label, selection_steps.loop_grow(mesh, edges, blocked))
        if command == commands.LOOP_SHRINK:
            return self._apply_selection_step(label, selection_steps.loop_shrink(mesh, edges, blocked))
        return self._loop_shift(label, edges, rightwards=command == commands.LOOP_NEXT)

    def _drop_hidden(self, ids: set) -> set:
        """`ids` (of the active mode) without the hidden elements: a step or loop never selects what cannot be seen."""
        hidden = self._hidden
        if not hidden or not ids:
            return ids
        mesh = self.scene.mesh
        mode = self.selection.mode
        if mode is SelectionMode.VERTEX:
            return {i for i in ids if not hidden.is_hidden_vertex(i)}
        if mode is SelectionMode.EDGE:
            return {i for i in ids if not hidden.is_hidden_edge(mesh, i)}
        if mode is SelectionMode.FACE:
            return {i for i in ids if not hidden.is_hidden_face(mesh, i)}
        return ids

    def _apply_selection_step(self, label: str, ids: set, note: str = "") -> bool:
        selection = self.selection
        before = selection_state(selection)
        ids = self._drop_hidden(ids)
        selection.set(ids)
        count = len(ids)
        if selection_state(selection) == before:
            self._set_status(f"{label}: no change ({count} selected){note}")
            return False
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        self._set_status(f"{label}: {count} selected{note}")
        return True

    def _loop_shift(self, label: str, edges: set[EdgeId], rightwards: bool) -> bool:
        """Each loop piece moves to its parallel piece on the screen side asked for: right
        (Shift+Right) or left; for a piece whose neighbours lie above / below each other on
        screen, up counts as right. A piece without quads on that side stays."""
        mesh = self.scene.mesh
        blocked = self._hidden.vertices()
        out: set[EdgeId] = set()
        stuck = 0
        for piece in selection_steps.loop_pieces(mesh, edges, blocked):
            sides = {
                left: selection_steps.shifted_piece(mesh, piece, left, blocked) for left in (True, False)
            }
            left = self._screen_side(piece.edges, sides, rightwards)
            target = sides[left]
            if target is None:
                stuck += 1
                out.update(piece.edges)
            else:
                out.update(target)
        note = f" - {stuck} piece(s) at a border or non-quad stayed" if stuck else ""
        return self._apply_selection_step(label, out, note)

    def _screen_side(self, piece_edges, sides: dict, rightwards: bool) -> bool:
        """The winding side (`left` key of `sides`) that lies towards screen right / up when
        `rightwards`, else the other one. Without a usable projection: right = the left side."""
        centre = self._edges_screen_centre(piece_edges)
        offsets = {}
        if centre is not None:
            for left, shifted in sides.items():
                if shifted is None:
                    continue
                c = self._edges_screen_centre(shifted)
                if c is not None:
                    offsets[left] = (c[0] - centre[0], c[1] - centre[1])
        if True in offsets and False in offsets:
            dx = offsets[True][0] - offsets[False][0]
            dy = offsets[True][1] - offsets[False][1]
        elif offsets:
            ((left, (dx, dy)),) = offsets.items()
            if not left:
                dx, dy = -dx, -dy
        else:
            dx = dy = 0.0
        # (dx, dy): screen direction from the right-hand to the left-hand winding side.
        along = dx if abs(dx) >= abs(dy) else dy
        if abs(along) < 1e-6:
            return rightwards
        return (along > 0) == rightwards

    def _edges_screen_centre(self, edge_ids) -> tuple[float, float] | None:
        mesh = self.scene.mesh
        vertices = {v for e in edge_ids for v in mesh.edge_vertices(e)}
        if not vertices or self.viewport_width <= 0 or self.viewport_height <= 0:
            return None
        n = len(vertices)
        x = sum(mesh.vertex_position(v)[0] for v in vertices) / n
        y = sum(mesh.vertex_position(v)[1] for v in vertices) / n
        z = sum(mesh.vertex_position(v)[2] for v in vertices) / n
        return self._objects.edit_camera.project_to_screen((x, y, z), self.viewport_width, self.viewport_height)

    def _loop_insert(self) -> bool:
        seeds = self._loop_seed_edges("Loop Insert")
        if seeds is None:
            return False
        mesh = self.scene.mesh
        blocked = self._hidden.vertices()  # the ring ends at hidden geometry (Isolate): only visible quads are cut
        ring: set[EdgeId] = set()
        for edge in sorted(seeds):
            if edge not in ring:
                ring.update(edge_ring(mesh, edge, blocked).edges)
        if len(ring) < 2:
            self._set_status(
                "Loop Insert: no edge ring through this edge (needs visible quads)" if blocked
                else "Loop Insert: no edge ring through this edge (needs quads)"
            )
            return False
        effective = ring
        if mesh.symmetry_definition is not None:
            effective = canonical_edges(SymmetryIndex(mesh), ring)
        return self._edge_connect(ring, effective, "Loop Insert", "Loop Insert")

    # -- Delete / Dissolve (WP Delete/Dissolve) ----------------------------------

    def _removal_command(self, command: str) -> bool:
        """Entf / Rücktaste / Ctrl+Rücktaste on the selection of the active
        component mode (`mirai.topology.delete_dissolve`). Exactly one
        `MeshDeltaCommand` per success, mesh and history untouched on refusal
        or no-op. Residue (first default, refinement is material for the
        practice check): Face Dissolve selects the merged faces, everything
        else clears the selection; the mode stays.

        With a symmetry definition set and the command declared
        (`symmetry_declarations.REMOVAL_COORDINATORS`, AD-SYM-03 slice 3c) the
        coordinator runs the removal on the selection and its partners inside
        the same single transaction, in MARK as in BLOCK; a `SymmetryRefusal`
        posts its text, records no history entry and leaves mesh and selection
        untouched. Under symmetry Face Dissolve selects the merged faces on the
        side(s) where the live selection had faces (`residue_sides`, engineering
        default). Without a definition the unchanged `apply_removal` runs."""
        selection = self.selection
        mode = selection.mode
        ids = {
            SelectionMode.VERTEX: selection.vertices,
            SelectionMode.EDGE: selection.edges,
            SelectionMode.FACE: selection.faces,
        }.get(mode)
        dissolve, cleanup = _REMOVAL_COMMANDS[command]
        if not ids:
            verb = "Dissolve" if dissolve else "Delete"
            self._set_status(f"{verb}: nothing selected")
            return False
        label = removal_label(mode, dissolve=dissolve, cleanup=cleanup)
        if command == commands.DISSOLVE_NO_CLEANUP and mode is SelectionMode.VERTEX:
            # §0.2.2: Vertex Dissolve has no variant, so this command does nothing.
            self._set_status("Dissolve (no cleanup): no variant in Vertex mode")
            return False

        mesh = self.scene.mesh
        coordinator = (
            symmetry_declarations.REMOVAL_COORDINATORS.get(command)
            if mesh.symmetry_definition is not None
            else None
        )
        sides = (
            residue_sides(mesh, selection.faces, mesh.face_vertices)
            if coordinator is not None and dissolve and mode is SelectionMode.FACE
            else None
        )

        def mutate(mesh) -> list[FaceId]:
            if coordinator is not None:
                return coordinator(mesh, mode, set(ids))
            return apply_removal(mesh, mode, set(ids), dissolve=dissolve, cleanup=cleanup)

        def residue(new_faces) -> None:
            selection.clear()
            if dissolve and mode is SelectionMode.FACE:
                kept = set(new_faces)
                if sides is not None:
                    kept = on_residue_sides(mesh, kept, sides, mesh.face_vertices)
                selection.add(kept)

        try:
            outcome = self._mesh_transaction(label, mutate, on_applied=residue)
        except RemovalRefused as exc:
            self._set_status(f"{label}: {exc}")
            return False
        except SymmetryRefusal as exc:
            self._set_status(str(exc))
            return False
        if not outcome.changed:
            self._set_status(f"{label}: nothing to do")
            return False
        self._set_status(label)
        return True

    # -- Collapse (WP Toolbox Gaps B1) --------------------------------------------

    def _collapse_command(self) -> bool:
        """Shift+C on the selection of the active component mode (`mirai.topology.collapse`):
        each connected group (over selected edges, the edges of selected faces, or in vertex mode
        the edges between two selected vertices) falls into one point at its centroid; a vertex
        without such an edge stays. Exactly one `MeshDeltaCommand` per success, mesh and history
        untouched on refusal or no-op. Residue (P-4, `PROVISIONAL`): the resulting vertices,
        mode switches to Vertex.

        With a symmetry definition set and the command declared
        (`symmetry_declarations.COLLAPSE_COORDINATORS`) the coordinator runs on the selection and
        its partners inside the same single transaction; a `SymmetryRefusal` posts its text and
        changes nothing. Under symmetry the residue keeps the result vertices on the side(s) where
        the live selection was (`residue_sides`, as Split), vertices on the plane always stay."""
        selection = self.selection
        mode = selection.mode
        ids = {
            SelectionMode.VERTEX: selection.vertices,
            SelectionMode.EDGE: selection.edges,
            SelectionMode.FACE: selection.faces,
        }.get(mode)
        if not ids:
            self._set_status(f"{COLLAPSE_LABEL}: nothing selected")
            return False

        mesh = self.scene.mesh
        coordinator = (
            symmetry_declarations.COLLAPSE_COORDINATORS.get(commands.COLLAPSE)
            if mesh.symmetry_definition is not None
            else None
        )
        sides = None
        if coordinator is not None:
            vertices_of = {
                SelectionMode.VERTEX: lambda v: (v,),
                SelectionMode.EDGE: mesh.edge_vertices,
                SelectionMode.FACE: mesh.face_vertices,
            }[mode]
            sides = residue_sides(mesh, ids, vertices_of)

        def mutate(mesh) -> list[VertexId]:
            if coordinator is not None:
                return coordinator(mesh, mode, set(ids))
            return apply_collapse(mesh, mode, set(ids))

        def residue(survivors) -> None:
            kept = {v for v in survivors if mesh.is_valid_vertex(v)}
            if sides is not None:
                kept = on_residue_sides(mesh, kept, sides, lambda v: (v,))
            selection.clear()
            selection.mode = SelectionMode.VERTEX
            selection.add(kept)
            if self.viewport is not None:
                self.viewport.on_selection_changed()

        try:
            outcome = self._mesh_transaction(COLLAPSE_LABEL, mutate, on_applied=residue)
        except CollapseRefused as exc:
            self._set_status(f"{COLLAPSE_LABEL}: {exc}")
            return False
        except SymmetryRefusal as exc:
            self._set_status(str(exc))
            return False
        if not outcome.changed:
            self._set_status(f"{COLLAPSE_LABEL}: nothing to do (no selected edge joins two points)")
            return False
        self._set_status(f"{COLLAPSE_LABEL}: {len(outcome.result)} point(s)")
        return True

    # -- Border Select / Cap (Manu 2026-10-25, keys PROVISIONAL) -------------------------

    def _border_select(self) -> bool:
        """B (`mirai.topology.border.border_select`): in vertex / edge mode the whole open border(s)
        the selection touches replace it; nothing selected = the border under the cursor, else every
        border of the mesh. In face mode the outline of the selected faces becomes the edge
        selection. A selection change like Shift+L, no History step."""
        selection = self.selection
        mesh = self.scene.mesh
        mode = selection.mode
        current = {
            SelectionMode.VERTEX: selection.vertices,
            SelectionMode.EDGE: selection.edges,
            SelectionMode.FACE: selection.faces,
        }[mode]
        valid = {
            SelectionMode.VERTEX: mesh.is_valid_vertex,
            SelectionMode.EDGE: mesh.is_valid_edge,
            SelectionMode.FACE: mesh.is_valid_face,
        }[mode]
        ids = {i for i in current if valid(i)}
        hovered = self._hovered_of_mode()
        if not ids and mode is not SelectionMode.FACE and hovered is not None:
            ids = {hovered}
            if not border_select(mesh, mode, ids)[1]:
                ids = set()
        if not ids and mode is SelectionMode.FACE:
            self._set_status(f"{BORDER_LABEL}: select faces (outline) or use 1/2 for holes")
            return False
        new_mode, found = border_select(mesh, mode, ids)
        if not found:
            self._set_status(f"{BORDER_LABEL}: no open border here")
            return False
        if new_mode is not mode:
            selection.clear()
            selection.mode = new_mode
        return self._apply_selection_step(BORDER_LABEL, found)

    def _hovered_of_mode(self):
        """The hovered element if it is a valid element of the active component mode, else None."""
        return hovered_of_mode(self.scene.mesh, self.selection)

    def _cap_command(self) -> bool:
        """Shift+B (`mirai.topology.border.apply_cap`): each closed border the selection (else the hovered
        element) touches is closed with one face, wound against its neighbours. One
        `MeshDeltaCommand`; mesh and history untouched on refusal. Residue (`PROVISIONAL`): the new
        faces in face mode, ready for T / W. Under symmetry the coordinator
        (`symmetry_declarations.CAP_COORDINATORS`) caps the mirror border too and splits a hole
        across the plane into two mirror faces along the seam."""
        selection = self.selection
        mesh = self.scene.mesh
        mode = selection.mode
        ids = {
            SelectionMode.VERTEX: selection.vertices,
            SelectionMode.EDGE: selection.edges,
            SelectionMode.FACE: selection.faces,
        }.get(mode)
        if not ids and self._hovered_of_mode() is not None:
            ids = {self._hovered_of_mode()}
        if not ids:
            self._set_status(f"{CAP_LABEL}: select or hover a border edge of the hole")
            return False
        coordinator = (
            symmetry_declarations.CAP_COORDINATORS.get(commands.CAP)
            if mesh.symmetry_definition is not None
            else None
        )
        sides = None
        if coordinator is not None:
            vertices_of = {
                SelectionMode.VERTEX: lambda v: (v,),
                SelectionMode.EDGE: mesh.edge_vertices,
                SelectionMode.FACE: mesh.face_vertices,
            }[mode]
            sides = residue_sides(mesh, ids, vertices_of)

        def mutate(mesh) -> list[FaceId]:
            if coordinator is not None:
                return coordinator(mesh, mode, set(ids))
            return apply_cap(mesh, mode, set(ids))

        def residue(new_faces) -> None:
            kept = {f for f in new_faces if mesh.is_valid_face(f)}
            if sides is not None:
                kept = on_residue_sides(mesh, kept, sides, mesh.face_vertices)
            selection.clear()
            selection.mode = SelectionMode.FACE
            selection.add(kept)
            if self.viewport is not None:
                self.viewport.on_selection_changed()

        try:
            outcome = self._mesh_transaction(CAP_LABEL, mutate, on_applied=residue)
        except CapRefused as exc:
            self._set_status(f"{CAP_LABEL}: {exc}")
            return False
        except SymmetryRefusal as exc:
            self._set_status(str(exc))
            return False
        if not outcome.changed:
            self._set_status(f"{CAP_LABEL}: nothing to do")
            return False
        self._set_status(f"{CAP_LABEL}: {len(outcome.result)} face(s)")
        return True

    def _notify_topology_changed(self) -> None:
        """Meldet dem Viewport eine Topologie-Änderung und richtet den Hover
        neu aus.

        Grund (WP-06 B6 fix, gefunden im Praxistest `C` → Split): Split und
        Connect entfernen die Edge-IDs, die sie ersetzen. War eine davon
        gehovert (oder selektiert), zeigt `selection.hovered` danach auf ein
        Element, das es nicht mehr gibt — im Praxistest crashte genau das den
        Draw-Loop (`KeyError: EdgeId(11)` in `mesh.edge_vertices`, siehe
        `viewport/overlay.py`). `_refresh_hover()` pickt am ruhenden Cursor im
        dann aktuellen Modus neu — dasselbe Muster wie nach Undo/Redo
        (`_undo_redo`). Ist kein Cursor bekannt, bleibt `selection.hovered`
        bewusst unangetastet; der Viewport überspringt die stale ID beim
        Aufbau der Overlays (AD-001: Gültigkeit wird über
        `mesh.is_valid_*()` geprüft, nie über die ID selbst).
        """
        self._pick_cache.invalidate()
        if self.viewport is not None:
            self.viewport.on_topology_changed()
        self._soft_preview_refresh()
        self._refresh_hover()

    # -- Knife session (WP-06 B7 / B7.1, AD-017; `controllers.knife` since AD-027 M3) ----------------------
    #
    # The session, its routing and its render data are `KnifeController` / `KnifeSession`'s; `C` begins it
    # (`_connect_command`), the slot routes its input. What stays here is the public read API.

    @property
    def knife_active(self) -> bool:
        """A Knife session is running (`C` with an empty selection)."""
        return self._knife.session is not None

    @property
    def knife_render_data(self) -> KnifeRenderData | None:
        """What the running session shows (headless), None without a session."""
        return self._knife.render_data()

    @property
    def knife_clock(self) -> Callable[[], float]:
        """The Knife's double-click clock (`time.monotonic`; injectable for headless tests)."""
        return self._knife.clock

    @knife_clock.setter
    def knife_clock(self, clock: Callable[[], float]) -> None:
        self._knife.clock = clock

    @property
    def knife_mirror_variant(self) -> str:
        """The provisional mirror preview variant of a symmetric Knife session (AD-SYM-03 slice 6c), kept across
        sessions of this app."""
        return self._knife.mirror_variant

    @knife_mirror_variant.setter
    def knife_mirror_variant(self, variant: str) -> None:
        self._knife.mirror_variant = variant

    def set_shift_held(self, held: bool) -> bool:
        """The window reports whether any Shift key is held (WP-KNIFE-01 UX2b).
        During a Knife session the hover preview at the known cursor follows it
        at once (the midpoint before the click); without a session, a cursor or
        while a button is held it is only stored. True = the preview changed."""
        held = bool(held)
        if held == self._shift_held:
            return False
        self._shift_held = held
        if self._orbit_virtual is not None:
            # V-1: Shift during a running Alt+LMB orbit snaps (and its release frees) the view at once.
            self._apply_orbit_virtual()
            self._camera_changed()
            return True
        if self._cursor is None or self.pointer.active:
            return False
        grabbed = self.interaction.grab(Modifiers(held, self._ctrl_held, self._alt_held))  # the Knife's preview
        return False if grabbed is PASS else grabbed

    # -- Display (WP-06 B5a) ----------------------------------------------------

    def _display_command(self, command: str) -> bool:
        if command == commands.TOGGLE_REFERENCE_GHOST:
            return self._objects.toggle_reference_ghost()
        if command == commands.TOGGLE_REGION_TINT:
            self.display.toggle_region_tint()
            self._apply_display()
            self._set_status(f"Region colours: {'on' if self.display.region_tint else 'off'}")
            return True
        if command in (commands.CYCLE_LIGHT_PRESET, commands.TOGGLE_LIGHT_SPACE):
            if command == commands.CYCLE_LIGHT_PRESET:
                self.display.cycle_light_preset()
            else:
                self.display.toggle_light_space()
            self._apply_display()
            self._set_status(f"Light: {self.display.light_label}")
            return True
        if (
            command == commands.TOGGLE_WIREFRAME_OVERLAY
            and self.subdivision.enabled
            and self.display.show_faces
        ):
            # SubD view (Manu 2026-10-23, option A): Shift+D shows / hides the preview's cage or
            # isolines instead of the wire overlay (which the preview replaces while it is on).
            self.subdivision.toggle_lines()
            return True
        if command == commands.CYCLE_DISPLAY_MODE:
            self.display.cycle()
        elif command == commands.TOGGLE_WIREFRAME_OVERLAY:
            self.display.toggle_wireframe_overlay()
        else:
            self.display.set_mode(_SET_DISPLAY_MODES[command])
        self._apply_display()
        self._set_status(f"Display: {self.display.label}")
        return True

    # -- Worklight and Look rows (AD-024 §8, `PROVISIONAL`) ------------------------------

    def set_light(self, **changes) -> bool:
        """The edit path of the Worklight (keys now, the GUI later): any `LightRig` field, clamped to
        the Shading Lab's ranges (`DisplayState.set_light`). View state - no Undo step, not saved. True
        = the light changed; the viewport gets it at once (a uniform update at draw time, AD-018)."""
        before = self.display.light_rig
        if self.display.set_light(**changes) == before:
            return False
        if self.viewport is not None:
            self.viewport.set_light(self.display.light_rig)
        return True

    def step_light(self, row_id: str, direction: int, fine: bool = False) -> bool:
        """One value step of the Look row `row_id` (`look_controls.LIGHT_ROWS`, the Lab's steps);
        `direction` -1 / +1. A row that does not apply (fill off / coupled) is refused with a status
        line. True = the light changed."""
        row = light_row(row_id)
        rig = self.display.light_rig
        if not row.applies(rig):
            self._set_status(f"Light: {row.label} inaktiv - {row.inactive_reason}")
            return False
        stepped = row.step(rig, direction, fine)
        changed = self.set_light(
            **{name: value for name, value in stepped.to_dict().items() if getattr(rig, name) != value}
        )
        suffix = "" if changed else " (Grenze)"
        self._set_status(f"Light: {row.label} {row.format(self.display.light_rig)}{suffix}")
        return changed

    # -- Object material (AD-024 §6/§7, `PROVISIONAL` keys; `controllers.objects` since AD-027 M7) --------------

    def set_object_material(self, **changes) -> bool:
        """The edit path of the object material (keys now, the GUI later): any of `base_color`,
        `specular`, `glossiness`, clamped to [0, 1], set on every target (the selected objects in `4`, the edit
        object in `1/2/3`); one Undo step. True = a material changed. An object without a material starts from the
        default look."""
        return self._objects.set_material(**changes)

    def step_object_material(self, row_id: str, direction: int, fine: bool = False) -> bool:
        """One value step of the material row `row_id` on every target, each from its own values
        (`look_controls.MATERIAL_ROWS`); one Undo step. True = a material changed."""
        return self._objects.step_material(row_id, direction, fine)

    # -- Look rows (AD-024 §6/§8) ------------------------------------------------------------

    @property
    def look_row(self) -> LookRow | MaterialRow:
        """The row the arrow keys edit."""
        return LOOK_ROWS[self._look_row_index]

    @property
    def look_text(self) -> str:
        """The active row and its value (HUD, status line). A material row shows the object it reads."""
        row = self.look_row
        if isinstance(row, MaterialRow):
            obj = self._objects.material_preview()
            if obj is None:
                return f"{row.label} (kein Objekt gewählt)"
            values = editable_material(obj, self.display.surface_finish)
            text = f"{row.label} {row.format(values)} ({obj.name})"
            return text if row.applies(values) else f"{text} (inaktiv)"
        rig = self.display.light_rig
        text = f"{row.label} {row.format(rig)}"
        return text if row.applies(rig) else f"{text} (inaktiv)"

    def _look_command(self, command: str) -> bool:
        if command in (commands.LOOK_ROW_PREV, commands.LOOK_ROW_NEXT):
            step = -1 if command == commands.LOOK_ROW_PREV else 1
            self._look_row_index = (self._look_row_index + step) % len(LOOK_ROWS)
            self._set_status(f"Look: {self.look_text}")
            return True
        direction = -1 if command in (commands.LOOK_VALUE_DEC, commands.LOOK_VALUE_DEC_FINE) else 1
        fine = command in (commands.LOOK_VALUE_DEC_FINE, commands.LOOK_VALUE_INC_FINE)
        row = self.look_row
        if isinstance(row, MaterialRow):
            return self.step_object_material(row.id, direction, fine)
        return self.step_light(row.id, direction, fine)

    def _subd_command(self, command: str) -> bool:
        """SubD preview keys (2026-10-23, `mirai.subdivision`, `PROVISIONAL`): view state only - no
        mesh change, no History, no Undo step. Refused visibly while an interaction owns the keys
        (W/E/R/T/G, a drag selection, the Knife): a running gesture keeps the view it began with."""
        owner = self.interaction_owner
        if owner is not None or self._pointer_tools.drag_select is not None:
            self._set_status(f"SubD: ignoriert — {owner or 'Auswahl'} läuft")
            return False
        return self.subdivision.run(command)

    def _apply_display(self) -> None:
        """E36: `DisplayState` → Grundwerte für `Viewport.set_display` (der
        Viewport kennt kein `DisplayState`). WP-06 B8: the pick cache's
        occlusion pre-filter depends on `show_faces` - invalidated on every
        display-mode change, including the initial one from `init_scene()`."""
        self._pick_cache.invalidate()
        if self.viewport is None:
            return
        self.viewport.set_display(
            show_faces=self.display.show_faces,
            show_edges=self.display.show_edges,
            flat=self.display.mode is DisplayMode.FLAT_SHADED,
        )
        self.viewport.set_region_tint(self.display.region_tint)
        self.viewport.set_light(self.display.light_rig)
        if self.viewport.set_surface_finish(self.display.surface_finish):
            # The global finish resets every entry; the objects' own materials go back on (AD-024 §4).
            self._objects.sync_views()
        self.subdivision.set_faces_shown(self.display.show_faces)

    # -- Tasten (WP-06 B3) ------------------------------------------------------

    @property
    def _gesture(self) -> GestureSession | None:
        """The held gesture in the slot (`controllers.gestures`), else None."""
        return self._gestures.session

    @property
    def move_armed(self) -> bool:
        """Move-Taste gehalten (scharf oder bereits laufend)."""
        return self.transform_command == commands.MOVE

    @property
    def move_interacting(self) -> bool:
        """Move läuft (erste Mausbewegung nach dem Scharfschalten erfolgt)."""
        return self.move_armed and self.transform_interacting

    @property
    def move_target(self) -> frozenset[VertexId]:
        """Beim Scharfschalten fixierte Ziel-Vertices (leer = nicht scharf)."""
        return self.transform_target if self.move_armed else frozenset()

    @property
    def transform_command(self) -> str | None:
        """Scharf geschalteter Hold-Key-Transform (MOVE/ROTATE/SCALE, seit WP-06 B9
        auch EXTRUDE; None = keiner)."""
        gesture = self._gesture
        return None if gesture is None else gesture.command

    @property
    def transform_interacting(self) -> bool:
        """Der scharfe Transform läuft (erste Mausbewegung erfolgt)."""
        gesture = self._gesture
        return gesture is not None and gesture.begun

    @property
    def transform_target(self) -> frozenset[VertexId]:
        """Beim Scharfschalten fixierte Ziel-Vertices (leer = nicht scharf)."""
        gesture = self._gesture
        return frozenset() if gesture is None else gesture.target

    @property
    def transform_space(self) -> str | None:
        """`space` der laufenden Geste, fix ab `begin()` (None = frei bzw.
        keine Geste)."""
        gesture = self._gesture
        return None if gesture is None else gesture.space

    @property
    def transform_orientation(self) -> str:
        """`world` or `normal` (WP Toolbox Gaps C1): the frame the axis constraints and the gizmo use."""
        return self._gestures.orientation

    @property
    def axis_constraint(self) -> str | None:
        """Achsen-/Ebenen-Constraint als `space`-String (None = frei); one-shot or sticky (`constraint_mode`)."""
        return self._gestures.axis_constraint

    @property
    def constraint_mode(self) -> str:
        """How long a constraint lives: `gestures.CONSTRAINT_ONE_SHOT` (default) or `CONSTRAINT_STICKY`."""
        return self._gestures.constraint_mode

    @constraint_mode.setter
    def constraint_mode(self, mode: str) -> None:
        self._gestures.constraint_mode = mode

    @property
    def soft_settings(self) -> SoftSettings:
        """The sticky Soft Selection settings (immutable; `enabled` False = off)."""
        return self._soft

    @property
    def interaction_owner(self) -> str | None:
        """Which of `Application`'s own interactions owns the keys right now
        (AD-013 H2 addendum, H2-R2): `"transform"` while W/E/R (and, WP-06 B9, T =
        Extrude - the same hold-key family, no new value) is armed or running,
        `"knife"` during a Knife session, `"resymmetrize"` while the Re-Symmetrize
        preview is open (AD-SYM-04 A3), else None: the slot's session (AD-027 §3.2). Camera gestures
        (orbit, pan, zoom) own no keys and are never an owner."""
        return self.interaction.owner

    @property
    def hover_suspended(self) -> bool:
        """H2 (AD-013 H2 addendum, review CLAUDE-001 F3): while True the
        selection hover stays cleared on every hover path (motion, zoom, the
        refreshes after Undo/Redo, commit, cancel and `apply_mesh_change`),
        because they all go through `_update_hover`. The cursor is still
        tracked. Default False; `src/main.py` never sets it. The Knife hover
        is not affected. The app's own Re-Symmetrize preview pauses the hover
        without it (`_update_hover`)."""
        return self._hover_suspended

    @hover_suspended.setter
    def hover_suspended(self, value: bool) -> None:
        value = bool(value)
        if value == self._hover_suspended:
            return
        self._hover_suspended = value
        if value:
            self._set_hovered(None)
        else:
            # Re-pick at the last cursor, as after a zoom.
            self._refresh_hover()

    def key_press(self, input: Input) -> bool:
        """Taste gedrückt (`input.kind == "key"`), aufgelöst über die Bindings
        (GLOBAL; während einer Knife-Session zuerst KNIFE_CONTEXT). True = der
        Druck hat etwas bewirkt. Ein von `command_gate` abgelehntes Command
        (H2) postet den Ablehnungstext und gibt False zurück; die Knife-Session
        liegt davor und wird nie gegatet."""
        self.flush_hover()
        grabbed = self.interaction.grab(KeyPress(input))  # the Knife, the Re-Symmetrize preview
        if grabbed is not PASS:
            return grabbed
        command = self._resolve_key(input)
        refusal = self.can_run(command, RunContext("key", input))
        if refusal is not None:
            return self._refused(refusal)
        return self._key_command(command, input)

    def _resolve_key(self, input: Input) -> str | None:
        """A key's command: global, then the SubD keys (context "subd") and the morph keys (context "morph")
        only where the global context binds nothing; I is Inset in face mode."""
        command = self.bindings.command_for(input)
        if command is None:
            subd = self.bindings.command_for(input, SUBD_CONTEXT)
            if subd in SUBD_COMMANDS:
                command = subd
            else:
                morph = self.bindings.command_for(input, MORPH_CONTEXT)
                if morph in MORPH_COMMANDS:
                    command = morph
        if command == commands.LOOP_INSERT and self.selection.mode is SelectionMode.FACE:
            command = commands.INSET  # I: Loop Insert in edge mode, Inset in face mode (2026-10-29, Blender)
        return command

    def _key_command(self, command: str | None, input: Input) -> bool:
        """A key's command after `can_run` let it through (AD-027 M2): its handler from the table (§3.4)."""
        handler = self._handlers.get(command)
        return False if handler is None else handler(command, RunContext("key", input), None)

    def key_release(self, input: Input) -> bool:
        """Taste losgelassen. True = das Loslassen hat etwas bewirkt.

        Loslassen der Transform-Taste committet, wenn seit dem Scharfschalten
        eine Mausbewegung kam; ein bloßes Antippen entschärft nur (E21). Loslassen der
        Lasso-Taste beendet den Lasso-Modus (ein laufender Lasso-Drag läuft bis zum LMB-Release)."""
        # The hold keys end on their own key's release (AD-027 §3.2), in this order: two holds may share a key
        # value (other modifiers), the first one here lets go.
        tools = self._pointer_tools
        for hold in (tools.lasso, tools.pivot, self._morph.weight_hold, tools.light):
            if hold.key is not None and input.value == hold.key:
                return hold.release()
        return self.interaction.handle(KeyRelease(input)) is True  # the held gesture's key: its commit

    @property
    def tweak_running(self) -> bool:
        """True while W/E/R is held for a gesture (armed or begun): the user-facing "Tweak" (Manu A2, 2026-10-28) -
        not a gizmo drag (LMB) and not T / G / S."""
        gesture = self._gesture
        return gesture is not None and gesture.key != TWEAK_KEY and gesture.command in TWEAK_TRANSFORMS

    def _transform_arm(self, command: str, key: str) -> bool:
        """Arm a hold-key gesture (E21/E28; `controllers.gestures`). Refused while one is held already."""
        if self._gesture is not None or self.viewport is None:
            return False
        origin = self._gestures.origin(key)
        if command == commands.EXTRUDE:
            return self._gestures.arm_extrude(key, origin)
        if command == commands.LOOP_SLIDE:
            return self._gestures.arm_slide(key, origin)
        if command in SMOOTH_COMMANDS:
            return self._gestures.arm_smooth(command, key, origin)
        if command == commands.INSET:
            return self._gestures.arm_inset(key, origin)
        if command == commands.BEVEL:
            return self._gestures.arm_bevel(key, origin)
        if self.selection.mode is SelectionMode.OBJECT:
            return self._objects.arm_gesture(command, key, origin)
        return self._gestures.arm_transform(command, key, origin)

    def _session_switch(self, command: str) -> bool:
        """The session switches of the 2026-10-28 practical test (not saved, `PROVISIONAL` keys): one-shot <->
        sticky constraints, and the gizmo size S -> M -> L. State only, allowed at any time."""
        if command == commands.CONSTRAINT_MODE_TOGGLE:
            return self._gestures.toggle_constraint_mode()
        names = list(_gizmo.GIZMO_SIZES)
        self.gizmo_size_name = names[(names.index(self.gizmo_size_name) + 1) % len(names)]
        self._set_status(f"Gizmo size: {self.gizmo_size_name} (session setting)")
        self._refresh_hover()
        return True

    @property
    def cursor_wrap_active(self) -> bool:
        """True while the window should warp the pointer across the viewport edge (a running transform;
        a reusable gate for later slider drags)."""
        return self._gesture is not None

    def cursor_wrapped(self, jump_x: float, jump_y: float) -> None:
        """The window moved the pointer by (jump_x, jump_y) to the opposite edge. Gestures run on deltas (the
        warp's own event is swallowed), so only the stored cursor follows."""
        if self._cursor is not None:
            self._cursor = (self._cursor[0] + jump_x, self._cursor[1] + jump_y)

    def set_alt_held(self, held: bool) -> bool:
        """The window reports whether any Alt key is held. During a transform, motion then navigates
        (`_navigate_during_transform`); during a Box / Lasso drag it switches the release to select
        through the mesh (`selection_through`); otherwise it is only stored. True = the state changed."""
        held = bool(held)
        if held == self._alt_held:
            return False
        self._alt_held = held
        return True

    def set_ctrl_held(self, held: bool) -> bool:
        """The window reports whether any Ctrl key is held. Ctrl = snap in a running transform (a Tweak needs
        Ctrl let go once first); the snap shows at once. True = the transform changed."""
        held = bool(held)
        if held == self._ctrl_held:
            return False
        self._ctrl_held = held
        return self._gestures.ctrl_changed(held)

    # -- Soft Selection settings (WP-SOFT-01 S2a, AD-020, PROVISIONAL) ------------------

    # -- Mask Geometry (`mirai.mask`) ----------------------------------------------

    @property
    def _mask(self) -> VertexMask:
        """The edit object's mask (each object keeps its own: its IDs mean nothing on another mesh)."""
        return self._masks.setdefault(self.scene.edit_object_id, VertexMask())

    @property
    def _hidden(self) -> HiddenSet:
        return self._hiddens.setdefault(self.scene.edit_object_id, HiddenSet())

    def _mask_values(self, seeds: Iterable[VertexId] = ()) -> dict[VertexId, float]:
        """The mask a gesture on `seeds` begins with (stale IDs dropped, symmetric pairs protected alike); `{}` = none.
        Hidden vertices count as fully masked: nothing the artist cannot see is moved. With Mask by Polygroup on,
        everything outside the seeds' groups is masked too, for this gesture only (`mirai.regions.group_lock`)."""
        hidden = self._hidden
        mesh = self.scene.mesh
        locked: set[VertexId] = set()
        if self.group_mask and mesh.face_regions is not None:
            seeds = set(seeds)
            if seeds and mesh.symmetry_definition is not None:
                seeds |= mirrored_selection(mesh, seeds)  # the mirror side's group is free as well
            locked = face_regions_api.group_lock(mesh, seeds)
        if not self._mask and not hidden and not locked:
            return {}
        return effective_mask(mesh, self._mask, extra_full=hidden.vertices() | locked)

    def _mask_changed(self, status: str) -> bool:
        self._mask.prune(self.scene.mesh)
        self._mask_push()
        self._set_status(status)
        return True

    def _mask_push(self) -> None:
        """The mask overlay shows the edit object's mask without its hidden vertices."""
        if self._mask_overlay is None:
            return
        hidden = self._hidden.vertices()
        values = {v: m for v, m in self._mask.values().items() if v not in hidden}
        self._mask_overlay.set_values(values)
        if self.viewport is not None:
            self.viewport.on_vertices_moved(set(values))  # re-syncs the overlay

    # -- Hide / Isolate (`mirai.hidden`) --------------------------------------------

    def _hidden_push(self) -> None:
        """Everything that draws or picks learns the hidden set; the selection never keeps a hidden element."""
        mesh = self.scene.mesh
        hidden = self._hidden
        hidden.prune(mesh)
        vertices = hidden.vertices()
        if self.viewport is not None:
            self.viewport.set_hidden(vertices)
        self._pick_cache.set_hidden(vertices)
        self._prune_hidden_selection()
        self._mask_push()
        self._soft_preview_refresh()

    def _prune_hidden_selection(self) -> None:
        hidden = self._hidden
        if not hidden:
            return
        mesh = self.scene.mesh
        selection = self.selection
        selection.vertices = {v for v in selection.vertices if not hidden.is_hidden_vertex(v)}
        selection.edges = {
            e for e in selection.edges if mesh.is_valid_edge(e) and not hidden.is_hidden_edge(mesh, e)
        }
        selection.faces = {
            f for f in selection.faces if mesh.is_valid_face(f) and not hidden.is_hidden_face(mesh, f)
        }
        h = selection.hovered
        if (
            (isinstance(h, VertexId) and hidden.is_hidden_vertex(h))
            or (isinstance(h, EdgeId) and mesh.is_valid_edge(h) and hidden.is_hidden_edge(mesh, h))
            or (isinstance(h, FaceId) and mesh.is_valid_face(h) and hidden.is_hidden_face(mesh, h))
        ):
            selection.hovered = None

    def _hidden_refusal(self, command: str) -> str | None:
        """The refusal text (`can_run` stage 5) if `command` would rewrite geometry the artist has hidden: the
        selection (else the hovered element) touches a hidden vertex, or - the Knife, `C` with nothing
        selected - anything is hidden at all. Cheap exit when nothing is hidden. Pure (reads, never creates,
        the edit object's `HiddenSet`)."""
        hidden = self._hiddens.get(self.scene.edit_object_id)
        if not hidden or self.selection.mode is SelectionMode.OBJECT:
            return None
        mesh = self.scene.mesh
        selection = self.selection
        vertices = set(resolve_selection_vertices(mesh, selection, selection.mode))
        if not vertices and selection.hovered is not None and command != commands.CONNECT:
            vertices = set(element_vertices(mesh, selection.hovered))
        if not vertices:
            if command != commands.CONNECT:
                return None  # the command's own "nothing selected" refusal speaks
            text = "Knife"
        elif touches_hidden(mesh, hidden, vertices):
            text = "Topology edit"
        else:
            return None
        return f"{text}: hidden geometry in the way (Alt+H shows all)"

    def _hide_command(self, command: str) -> bool:
        """Ctrl+H / Ctrl+Shift+H / Alt+H: hide the selection, isolate it (hide everything else), show all.
        No History, no mesh change; the selection loses what became hidden. Refused during a running gesture."""
        if self._gesture is not None:
            return False
        mesh = self.scene.mesh
        hidden = self._hidden
        if command == commands.SHOW_ALL:
            if not hidden:
                self._set_status("Nothing is hidden")
                return False
            count = len(hidden)
            hidden.show_all()
            self._hidden_push()
            self._set_status(f"Shown all ({count} points)")
            return True
        selection = self.selection
        target = set(resolve_selection_vertices(mesh, selection, selection.mode))
        if not target:
            self._set_status("Hide: select vertices first (Ctrl+H)")
            return False
        if mesh.symmetry_definition is not None:
            target |= mirrored_selection(mesh, target)  # a pair is hidden together
        return self._hide_vertices(command, target)

    def _hide_vertices(self, command: str, target: set[VertexId]) -> bool:
        """Hide or isolate `target` (the shared body of Ctrl+H / Ctrl+Shift+H and the region isolate)."""
        mesh = self.scene.mesh
        hidden = self._hidden
        if command == commands.ISOLATE_SELECTION:
            hidden.isolate(mesh, target)
            label = f"Isolated {len(target)} points"
        else:
            hidden.hide(target)
            label = f"Hid {len(target)} points"
        if len(hidden) >= len(mesh.all_vertex_ids()):
            hidden.show_all()  # nothing visible is a trap: refuse instead
            self._hidden_push()
            self._set_status("Hide: everything would be hidden")
            return False
        self._hidden_push()  # a hidden element leaves the selection; Isolate keeps what it isolated
        self._set_status(f"{label} ({len(hidden)} hidden, Alt+H shows all)")
        return True

    def _mask_command(self, command: str) -> bool:
        """Ctrl+M / Ctrl+Shift+M / Alt+Shift+M: mask the selection (or unmask it when it is fully masked),
        invert, clear. No History, no selection or mesh change; refused during a running gesture."""
        if self._gesture is not None:
            return False
        mesh = self.scene.mesh
        if command == commands.MASK_CLEAR:
            self._mask.clear()
            return self._mask_changed("Mask cleared")
        if command == commands.MASK_INVERT:
            self._mask.invert(mesh)
            return self._mask_changed(f"Mask inverted: {len(self._mask.full())} points masked")
        selection = self.selection
        target = set(resolve_selection_vertices(mesh, selection, selection.mode))
        if not target:
            self._set_status("Mask: select vertices first (Ctrl+M)")
            return False
        selected = frozenset(target)
        if mesh.symmetry_definition is not None:
            target |= mirrored_selection(mesh, target)  # a pair is masked together
        return self._mask_vertices(target, decide_by=selected)

    def _mask_vertices(self, target: set[VertexId], decide_by: frozenset[VertexId] | None = None) -> bool:
        """Mask `target`, or unmask it when it is already fully masked (Ctrl+M and the region mask). `decide_by` is
        what the toggle looks at: the selection itself, not its mirror partners - a side masked before symmetry was
        switched on would otherwise make Ctrl+M on a masked selection mask the other side instead of unmasking."""
        if (target if decide_by is None else decide_by) <= self._mask.full():
            self._mask.set(target, 0.0)
            return self._mask_changed(f"Unmasked {len(target)} points ({len(self._mask.full())} masked)")
        self._mask.set(target)
        return self._mask_changed(f"Masked {len(target)} points ({len(self._mask.full())} masked)")

    # -- Saved regions (`mirai.regions`, AD-REGIONS-01) -----------------------------------

    @property
    def active_region(self) -> str | None:
        """The active group: the one last made, picked or clicked; when that one is gone (Undo, Delete) the last group
        in the list; None without groups."""
        regions = self.scene.mesh.face_regions
        if regions is None:
            return None
        name = self._active_regions.get(self.scene.edit_object_id)
        if name is not None and regions.get(name) is not None:
            return name
        return regions.regions[-1].name

    def _set_active_region(self, name: str) -> None:
        self._active_regions[self.scene.edit_object_id] = name

    @property
    def region_count(self) -> int:
        """How many groups the edit mesh has (read-only, for the HUD)."""
        regions = self.scene.mesh.face_regions
        return 0 if regions is None else len(regions.regions)

    def _push_region_tints(self) -> None:
        """The regions' colours go to the viewport whenever the edit mesh's `face_regions` value (or the mesh, or
        the viewport) changed: assign, Undo / Redo, load and Knife rollback all replace that value."""
        if self.viewport is None:
            return
        mesh = self.scene.mesh
        seen = self._tints_seen
        if seen is not None and seen[0] is mesh and seen[1] is mesh.face_regions and seen[2] is self.viewport:
            return
        self._tints_seen = (mesh, mesh.face_regions, self.viewport)
        self.viewport.set_face_tints(face_regions_api.region_tints(mesh))

    @property
    def active_region_faces(self) -> int:
        """How many faces the active group still has (read-only, for the HUD)."""
        name = self.active_region
        return 0 if name is None else len(face_regions_api.live_faces(self.scene.mesh, name))

    def _region_summary(self, name: str) -> str:
        mesh = self.scene.mesh
        live = len(face_regions_api.live_faces(mesh, name))
        lost = face_regions_api.lost_count(mesh, name)
        text = f"{name}: {live} faces"
        if lost:
            text += f" ({lost} lost to topology edits)"
        return text

    def _region_command(self, command: str) -> bool:
        """Ctrl+G (new group), Shift+G / Shift+Alt+G (active group), Ctrl+Shift+G / Ctrl+Alt+G (add, remove),
        Ctrl+Alt+N (save as named set), Alt+G / Ctrl+Alt+Shift+G (select), Ctrl+Alt+H (isolate), Ctrl+Alt+M (mask),
        Ctrl+Alt+Backspace (delete). Edits of the stored groups are one Undo step (`_mesh_transaction`); select /
        isolate / mask only read them. Refused during a gesture."""
        if self._gesture is not None:
            return False
        mesh = self.scene.mesh
        if command == commands.GROUP_MASK_TOGGLE:
            self.group_mask = not self.group_mask
            self._soft_preview_refresh()
            self._set_status(
                "Mask by Polygroup: on (W/E/R, Smooth / Relax only move the groups of the selection or hover)"
                if self.group_mask else "Mask by Polygroup: off"
            )
            return True
        if command == commands.REGION_NEW:
            return self._region_edit(command, face_regions_api.new_group_name(mesh.face_regions))
        name = self.active_region
        if name is None:
            self._set_status("No groups yet (select faces, Ctrl+G makes a group)")
            return False
        if command in (commands.REGION_NEXT, commands.REGION_PREV):
            names = [r.name for r in mesh.face_regions.regions]
            step = 1 if command == commands.REGION_NEXT else -1
            name = names[(names.index(name) + step) % len(names)]
            self._set_active_region(name)
            self._set_status(f"Active group {names.index(name) + 1}/{len(names)}: {self._region_summary(name)}")
            return True
        if command in (commands.REGION_ADD, commands.REGION_REMOVE):
            return self._region_edit(command, name)
        if command == commands.REGION_NAME:
            new = face_regions_api.next_name(mesh.face_regions, name)
            if new == name:
                self._set_status(f"{name}: every set name is taken")
                return False
            self._mesh_transaction(
                f"Name {name} {new}",
                lambda m: setattr(m, "face_regions", face_regions_api.renamed(m.face_regions, name, new)),
                moved_of=lambda _: set(),
            )
            self._set_active_region(new)
            self._set_status(f"{name} saved as {new} (Ctrl+Alt+N again: next name)")
            return True
        if command == commands.REGION_DELETE:
            self._mesh_transaction(
                f"Delete {name}",
                lambda m: setattr(m, "face_regions", face_regions_api.deleted(m.face_regions, name)),
                moved_of=lambda _: set(),
            )
            self._set_status(f"{name} deleted")
            return True
        faces = face_regions_api.live_faces(mesh, name)
        if not faces:
            self._set_status(f"{name}: no faces left")
            return False
        vertices = face_regions_api.region_vertices(mesh, faces)
        # Isolate and mask act on the whole group, hidden parts included (Isolate shows them again); only the
        # selection skips what is hidden.
        if command == commands.REGION_ISOLATE:
            return self._hide_vertices(commands.ISOLATE_SELECTION, vertices)
        if command == commands.REGION_MASK:
            return self._mask_vertices(vertices)
        selection = self.selection
        if selection.mode is SelectionMode.OBJECT:
            return False
        hidden = self._hidden
        faces = frozenset(f for f in faces if not hidden.is_hidden_face(mesh, f))
        elements = face_regions_api.elements_of(mesh, selection.mode, faces)
        if command == commands.REGION_SELECT:
            selection.set(elements)
        else:
            selection.add(elements)
        self._prune_hidden_selection()
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        self._set_status(self._region_summary(name) + " selected")
        return True

    def _pick_face_at(self, x: float, y: float):
        """The face under (x, y) whatever the selection mode is (GPU ID buffer, else the CPU picker), else None."""
        face = self._gpu_pick(SelectionMode.FACE, x, y)
        if face is not _CPU:
            return face
        return pick_face(
            self._objects.edit_camera, self.scene.mesh, x, y, self.viewport_width, self.viewport_height,
            cache=self._pick_cache,
        )

    def _region_click(self, x: float, y: float) -> bool:
        """Shift+Ctrl+click (`commands.REGION_CLICK`, ZBrush-like, Manu 2026-10-25) on the groups G under the cursor:
        every group a hovered vertex or edge touches (a face: its group). Nothing hidden: G is isolated. G is all that
        is visible: the visibility inverts (the rest visible, G hidden). Something else is hidden already: G is hidden
        as well. Empty space shows everything. View state only: no History, no selection or mesh change. Ignored in
        object mode and during a gesture."""
        if self.viewport is None or self._gesture is not None or self.selection.mode is SelectionMode.OBJECT:
            return False
        mesh = self.scene.mesh
        hidden = self._hidden
        touched = face_regions_api.faces_around(mesh, self._pick(x, y))
        if not touched:
            face = self._pick_face_at(x, y)
            if face is None:
                return self._hide_command(commands.SHOW_ALL)
            touched = {face}
        touched = {f for f in touched if not hidden.is_hidden_face(mesh, f)}
        names = face_regions_api.regions_of_faces(mesh, touched, prefer=self.active_region)
        if not names:
            self._set_status("Face has no group (Ctrl+G makes the selection a group)")
            return False
        self._set_active_region(names[0])
        group: set[FaceId] = set()
        for name in names:
            group |= face_regions_api.live_faces(mesh, name)
        label = " + ".join(names)
        vertices = face_regions_api.region_vertices(mesh, group)
        if not hidden:
            hidden.isolate(mesh, vertices)
            self._hidden_push()
            self._set_status(f"{label} isolated (Shift+Ctrl+click again inverts, on empty space shows all)")
            return True
        rest = [f for f in mesh.all_face_ids() if f not in group and not hidden.is_hidden_face(mesh, f)]
        if not rest:
            # G is everything that is visible: invert (the whole rest visible, only G hidden).
            interior = face_regions_api.interior_vertices(mesh, group)
            hidden.show_all()
            if interior:
                hidden.hide(interior)
            self._hidden_push()
            self._set_status(
                f"{label} hidden, the rest is visible (Shift+Ctrl+click on empty space shows all)" if interior
                else f"{label} has no interior to hide; everything is visible"
            )
            return True
        own = vertices - face_regions_api.region_vertices(mesh, rest)  # the corners no face that stays visible needs
        if not own:
            self._set_status(f"{label}: nothing to hide without hiding its neighbours")
            return False
        hidden.hide(own)
        self._hidden_push()
        self._set_status(f"{label} hidden ({len(hidden)} hidden points, Shift+Ctrl+click on empty space shows all)")
        return True

    def _region_edit(self, command: str, name: str) -> bool:
        """New group `name` from / add to / remove from group `name` the faces of the selection (all corners selected).
        A face is in one group: new and add take it out of its old group."""
        mesh = self.scene.mesh
        selection = self.selection
        if selection.mode is SelectionMode.OBJECT:
            return False
        if selection.mode is SelectionMode.FACE:
            faces = {f for f in selection.faces if mesh.is_valid_face(f)}
        else:
            faces = face_regions_api.faces_from_vertices(
                mesh, resolve_selection_vertices(mesh, selection, selection.mode)
            )
        if not faces:
            self._set_status("Group: select faces first")
            return False
        if mesh.symmetry_definition is not None:
            faces |= set(expand_faces(SymmetryIndex(mesh), faces).union)  # a pair belongs together
        if command == commands.REGION_REMOVE:
            change = lambda regions: face_regions_api.removed(regions, name, faces)  # noqa: E731
            verb = "removed from"
        else:
            add = command == commands.REGION_ADD
            change = lambda regions: face_regions_api.grouped(regions, name, faces, add=add)  # noqa: E731
            verb = "added to" if add else "grouped as"
        done = self._mesh_transaction(
            f"New {name}" if command == commands.REGION_NEW else name,
            lambda m: setattr(m, "face_regions", change(m.face_regions)),
            moved_of=lambda _: set(),
        )
        if not done.changed:
            self._set_status(f"{name}: no change")
            return False
        if command != commands.REGION_REMOVE:
            self._set_active_region(name)
        summary = self._region_summary(name) if face_regions_api.region_named(mesh, name) else f"{name} (now empty, gone)"
        self._set_status(f"{len(faces)} faces {verb} {summary}")
        return True

    def _soft_refresh_radius(self) -> None:
        """Recompute the world radius from the mesh's bounding radius for the current step
        (the one place that does it: switch-on, step change, scene load)."""
        _, bounding_radius = mesh_center_and_radius(self.scene.mesh)
        self._soft = self._soft.with_bounding_radius(bounding_radius)

    def _soft_command(self, command: str) -> bool:
        """O / Shift+wheel / Shift+O / Ctrl+O / Ctrl+wheel / Ctrl+Shift+wheel / Alt+O / Alt+Shift+O: change the sticky settings
        and post the full state. Never touches mesh, selection or history. False only for a
        radius or shape step that is already at the end of the list (clamped, no wrap) and
        changes nothing - the status line is posted anyway, so the end of the list is visible."""
        soft = self._soft
        changed = True
        if command == commands.SOFT_TOGGLE:
            self._soft = soft.toggled()
            if self._soft.enabled:
                self._soft_refresh_radius()
        elif command in (commands.SOFT_RADIUS_UP, commands.SOFT_RADIUS_DOWN) and self._gestures.soft_live():
            changed = self._gestures.radius_live(1 if command == commands.SOFT_RADIUS_UP else -1)
        elif command in (commands.SOFT_FLOW_LOOP, commands.SOFT_FLOW_RING):
            delta = 1 if command == commands.SOFT_FLOW_LOOP else -1
            if self._gestures.soft_live():
                changed = self._gestures.flow_live(delta)
            else:
                self._soft = soft.with_flow_step(delta)
                changed = self._soft != soft
        elif command in (commands.SOFT_RADIUS_UP, commands.SOFT_RADIUS_DOWN):
            step = soft.radius_step + (1 if command == commands.SOFT_RADIUS_UP else -1)
            step = max(0, min(step, len(RADIUS_STEPS_PERCENT) - 1))
            changed = step != soft.radius_step
            _, bounding_radius = mesh_center_and_radius(self.scene.mesh)
            self._soft = soft.with_radius_step(step, bounding_radius)
        elif command == commands.SOFT_CURVE_CYCLE:
            self._soft = soft.with_next_curve()
        elif command == commands.SOFT_METRIC_CYCLE:
            self._soft = soft.with_next_metric()
        elif command in (commands.SOFT_CURVE_SHAPE_ROUNDER, commands.SOFT_CURVE_SHAPE_SHARPER):
            # Rounder = smaller exponent = towards the front of the step list.
            delta = -1 if command == commands.SOFT_CURVE_SHAPE_ROUNDER else 1
            self._soft = soft.with_custom_shape_step(delta)
            changed = self._soft != soft
        elif command == commands.SOFT_BANDS_TOGGLE:
            self._soft = soft.with_bands_toggled()
        elif command == commands.SOFT_VIEW_MODE_CYCLE:
            self._soft = soft.with_next_view_mode()
        elif command == commands.SOFT_LOOK_CYCLE:
            # Colours only: applied at once, also mid-gesture (the weights and what is shown stay).
            self._soft = soft.with_next_look()
            self._soft_apply_look()
        if changed:
            self._soft_preview_refresh()
        status = self._soft.status_text()
        if command in (commands.SOFT_FLOW_LOOP, commands.SOFT_FLOW_RING):
            status += self._soft_flow_hint()
        self._set_status(status)
        return changed

    def _soft_flow_hint(self) -> str:
        """Status suffix for a flow step: says when the seeds give no Loop / Ring direction, so the field
        stays round (AD-020 "Loop / Ring flow": one vertex, one quad, a square block ...)."""
        gesture = self._gesture
        soft = (None if gesture is None else gesture.soft) or self._soft
        if soft.flow_ratio == 1.0 or soft.metric != "geodesic":
            return ""
        tool = self._gestures.live_tool()
        seeds = set(tool.soft_seeds) if tool is not None else self._soft_seeds()
        if not seeds or has_flow_direction(self.scene.mesh, seeds):
            return ""
        return " (no loop/ring direction here: round)"

    def _soft_apply_look(self) -> None:
        """Push the look (`SoftSettings.look`) to the influence sinks that exist."""
        for sink in (self._soft_overlay, self._soft_shading_overlay):
            if sink is not None and hasattr(sink, "set_look"):
                sink.set_look(self._soft.look)

    # -- Soft Selection bands (WP-SOFT-01 S2b, AD-020 §5, PROVISIONAL) -------------------
    #
    # The overlays only show; `Application` computes. Influence is computed here at most once
    # per triggering event (selection, mode, settings, scene load, Undo/Redo, topology change,
    # gesture end, and - since 2026-10-22 - a change of the hovered component while there is no
    # explicit selection) - never per mouse move over the same component: during a gesture the
    # display is the op's own weights (fixed at `begin()`), and the overlay merely re-reads the
    # live positions when the viewport syncs after `on_vertices_moved`. Two display modes
    # (vertex bands / face shading, `SoftSettings.view_mode`) are routed from the same weights;
    # only one is ever non-empty.

    @property
    def soft_bands(self) -> SoftBands:
        """The bands the window currently shows (`EMPTY_BANDS` = no band points; also in the
        face-shading mode)."""
        return self._soft_bands

    @property
    def soft_shading(self) -> dict[VertexId, float]:
        """The weights the face shading currently shows ({} = no shading; also in the bands mode)."""
        return dict(self._soft_shading)

    def _soft_show(self, weights: dict[VertexId, float] | None, mode: str | None = None) -> None:
        """Route `weights` (None = nothing to show) to the display mode `mode` (default: the active one)
        and clear the other, so bands and face shading are never visible together. Pushes only what
        changed."""
        mode = self._soft.view_mode if mode is None else mode
        bands = SoftBands.from_weights(weights) if weights and mode == "bands" else EMPTY_BANDS
        shading = dict(weights) if weights and mode == "faces" else {}
        if bands != self._soft_bands:
            self._soft_bands = bands
            if self._soft_overlay is not None:
                self._soft_overlay.set_bands(bands)
        if shading != self._soft_shading:
            self._soft_shading = shading
            if self._soft_shading_overlay is not None:
                self._soft_shading_overlay.set_weights(shading)

    def _soft_selection_seeds(self) -> set[VertexId]:
        selection = self.selection
        return set(resolve_selection_vertices(self.scene.mesh, selection, selection.mode))

    def _soft_seeds(self) -> set[VertexId]:
        """What the next W/E/R would use as the primary selection (`_transform_arm`): the armed
        target while a Move/Rotate/Scale is armed, else the explicit selection, else - with none -
        the vertices of the hovered component. An existing selection is never replaced by the
        hover."""
        gesture = self._gesture
        if gesture is not None and gesture.command in (commands.MOVE, commands.ROTATE, commands.SCALE):
            return set(gesture.target)
        seeds = self._soft_selection_seeds()
        if not seeds and self.selection.hovered is not None:
            seeds = element_vertices(self.scene.mesh, self.selection.hovered)
        return seeds

    def _soft_hover_changed(self) -> None:
        """The hovered component changed (identity, `_set_hovered`): with Soft on, shown and no
        explicit selection, the hover is the preview target. Not while a transform is armed or
        running (its target owns the display), and never for a pointer move over the same
        component."""
        soft = self._soft
        if not (soft.enabled and soft.bands_visible) or self._gesture is not None:
            return
        if self._soft_overlay is None and self._soft_shading_overlay is None:
            return
        if self._soft_selection_seeds():
            return  # the explicit selection is the target; hover is only the highlight
        self._soft_preview_refresh()

    def _soft_preview_refresh(self) -> bool:
        """Recompute the preview (E3). No-op without a sink, and while a running op owns the
        display. Soft off, hidden (`bands_visible` False) or no target (no selection and no hovered
        component) show nothing; under a symmetry definition the preview is the symmetric field
        (AD-SYM-04 D-5, slice SS3). The display mode (`view_mode`) only routes the same weights.
        True = weights are shown now (a hover-armed gesture then owns them, `GestureSession.soft_shown`)."""
        gesture = self._gesture
        if (self._soft_overlay is None and self._soft_shading_overlay is None) or (
            gesture is not None and gesture.soft_op_running
        ):
            return False
        soft = self._soft
        # Hidden (S2d E7): no influence work for display, nothing shown.
        shown = soft.enabled and soft.bands_visible
        seeds = self._soft_seeds() if shown else None
        weights = self._soft_preview_weights(seeds) if seeds else None
        self._soft_show(weights)
        return weights is not None

    def _soft_preview_weights(self, seeds: set[VertexId]) -> dict[VertexId, float] | None:
        """The weights the next gesture's `begin()` computes for `seeds`, by the same function
        with the same arguments (preview == op weights, F9). Under a definition: the symmetric
        field, its correspondence from the shared report of the current geometry (the tool
        derives its own, equal one at `begin()`). None = nothing shown: a selection symmetric Soft
        refuses (D-2) shows none (`PROVISIONAL`), never plain Soft's field; the refusal itself
        is shown by the gesture, at `begin()`, as before."""
        soft = self._soft
        mesh = self.scene.mesh
        mask = self._mask_values(seeds)  # the same mask the tools apply at `begin()` (Mask Geometry, Hide, groups)
        seeds = unblocked(seeds, mask)
        if mesh.symmetry_definition is None:
            weights = compute_influence(
                mesh, seeds, soft.world_radius, metric=soft.metric, curve=soft.curve,
                curve_power=soft.curve_power, flow_ratio=soft.flow_ratio,
            )
            return mask_weights(weights, seeds, mask)
        correspondence = self._symmetry.reports.current(mesh).correspondence
        try:
            field = symmetric_influence(
                mesh, seeds, soft.world_radius, metric=soft.metric, curve=soft.curve,
                curve_power=soft.curve_power, correspondence=correspondence,
                flow_ratio=soft.flow_ratio,
            )
        except SoftSymmetryRefusal:
            return None
        return mask_symmetric_influence(field, mask).weights

    def _cancel(self) -> bool:
        """Esc = nur Abbrechen (B1 A3: kein Quit, E22). Laufender Transform →
        exakter Vorzustand ohne History; nur scharf → entschärfen; idle →
        nichts. Eine Box/Paint-Geste wird verworfen (Auswahl wie vor der Geste)."""
        drag = self._pointer_tools.drag_select  # (a drag selection and a held pivot never coexist)
        if drag is not None:
            return drag.cancel()
        claimed = self.interaction.claim(Command(commands.CANCEL, RunContext("key")))  # the Working Pivot
        if claimed is not PASS:
            return claimed
        gesture = self._gesture
        if gesture is None:
            return False
        if gesture.key == TWEAK_KEY:
            # The LMB is still down: the rest of this drag must not arm a new one.
            self._pointer_tools.swallow()
            gizmo = self._pointer_tools.gizmo_press
            if gizmo is not None and self._gestures.constraint_mode == CONSTRAINT_ONE_SHOT:
                # E2: the handle's axis was for this drag only; Esc keeps what was pending before the press.
                self._gestures.axis_constraint = gizmo.constraint_before
        return gesture.cancel()

    def _undo_redo(self, command: str) -> bool:
        can = self.history.can_undo() if command == commands.UNDO else self.history.can_redo()
        if not can:
            self._set_status(f"{command}: nothing to {command.lower()}")
            return False
        self._execute(command)
        # E23: `HistoryStack` bietet keinen öffentlichen Zugriff auf das
        # gerade rückgängig gemachte Command (und `core/history.py` ist
        # tabu) - daher der gröbere, aber für jedes Command korrekte Rebuild
        # statt `on_vertices_moved(ids)`. Selection-Restore und Ghost-Pruning
        # laufen bereits in `dispatch_command` (`_apply_undo_redo`), auch für
        # Aufrufer, die `dispatch_command(UNDO/REDO)` direkt statt über
        # `key_press` erreichen.
        if self._last_undo_redo_mesh_step:
            self._pick_cache.invalidate()
            if self.viewport is not None:
                self.viewport.on_topology_changed()
        self._set_status(command)
        self._refresh_hover()
        return True

    def _apply_undo_redo(self, command: str) -> None:
        """Führt `history.undo()`/`redo()` aus und stellt dabei die Selection
        wieder her (WP-06 B6 Follow-up, Artist-Entscheidung Manu 2026-09-28).

        `HistoryStack` (core, frozen) kennt kein Selection-Konzept; Application
        führt deshalb einen eigenen Mirror-Stack aus (before, after)-Snapshots,
        einen pro `history.push()`, den sie selbst über `_record_selection_
        history()` befüllt (Split/Edge Connect/Vertex Connect, Transform-
        Commit, Knife-Commit, Delete/Dissolve, `apply_mesh_change`). Der
        Mirror-Pop läuft in
        derselben Reihenfolge wie `HistoryStack`s eigener Undo-/Redo-Stack
        (LIFO), Undo restauriert den `before`-Snapshot (Auswahl, wie sie vor
        der Mutation war), Redo den `after`-Snapshot (die von der Mutation
        gesetzte Residue-Auswahl). Ist der Mirror-Stack leer, obwohl History
        Undo/Redo erlaubt (Desync, z. B. ein künftiger Push-Pfad, der hier noch
        nicht verdrahtet ist), bleibt es beim reinen Pruning (Fallback, kein
        Crash) - `_prune_ghost_selection()` läuft danach in jedem Fall als
        Sicherheitsnetz, auch nach einem erfolgreichen Restore (dort ein
        No-op, weil der restaurierte Snapshot per Konstruktion gültig ist)."""
        restored = None
        # Without a mirror entry (desync fallback) the step is treated as a mesh step: the
        # full rebuild is correct for every command.
        self._last_undo_redo_mesh_step = True
        object_meshes: frozenset = frozenset()
        if command == commands.UNDO and self._selection_undo_stack:
            entry = self._selection_undo_stack.pop()
            self._selection_redo_stack.append(entry)
            restored = entry[0]
            self._last_undo_redo_mesh_step = entry[2]
            object_meshes = entry[3]
        elif command == commands.REDO and self._selection_redo_stack:
            entry = self._selection_redo_stack.pop()
            self._selection_undo_stack.append(entry)
            restored = entry[1]
            self._last_undo_redo_mesh_step = entry[2]
            object_meshes = entry[3]

        edit_before_step = self.scene.edit_object_id
        if command == commands.UNDO:
            self.history.undo()
        else:
            self.history.redo()
        if self.scene.edit_object_id != edit_before_step:
            # A command that carries the edit object itself (Delete of the edit object, Add with
            # an edit switch) switched the scene; viewport, caches and hover follow.
            self._follow_edit_object()

        if restored is not None:
            self._restore_selection(restored)
            if self.viewport is not None:
                self.viewport.on_selection_changed()  # an object step can change mode / selection
        self._morph.after_history()
        self._prune_ghost_selection()
        # AD-021 §4.6: refresh the view of the objects an object step touched; an object step
        # may be a placement (M2-2), so the pick caches re-project too (`ObjectController.placement_changed`).
        self._objects.meshes_changed(object_meshes)
        if self._last_undo_redo_mesh_step and not object_meshes:
            self._objects.sync_views()
        else:
            self._objects.placement_changed()
        self._soft_preview_refresh()

    def apply_mesh_change(
        self, description: str, mutate: Callable[[], set[VertexId] | None]
    ) -> bool:
        """The one entry for a mesh change made outside `Application`
        (WP-SYM-LAB-03 H3, AD-013 H2 addendum, review CLAUDE-002 N1).

        `mutate()` changes `scene.mesh` through core operations and returns
        the moved vertex IDs (positions only) or None (topology changed).
        Raises `RuntimeError` before anything changes while
        `interaction_owner` is set (D3). If `mutate` raises, the mesh is
        restored exactly and the exception propagates (ID counters
        stay forward, AD-001). An unchanged mesh records nothing
        and returns False. Otherwise: one `MeshDeltaCommand(description)`, the
        selection-mirror entry (so Undo/Redo restores the selection, B6
        follow-up), pick cache invalidated, viewport notified, hover
        re-picked; returns True."""
        owner = self.interaction_owner
        if owner is not None:
            raise RuntimeError(
                f"apply_mesh_change({description!r}) while the {owner} interaction runs"
            )
        return self._mesh_transaction(
            description, lambda _mesh: mutate(), moved_of=lambda moved: moved
        ).changed

    def _mesh_transaction(
        self,
        description: str,
        mutate: Callable[[Mesh], Any],
        *,
        on_applied: Callable[[Any], None] | None = None,
        moved_of: Callable[[Any], set[VertexId] | None] | None = None,
    ) -> "_MeshTransaction":
        """The one commit boundary for a mesh change `Application` makes (AD-SYM-03 §2.2 T-a);
        `apply_mesh_change` is its external-host entry.

        `mutate(mesh)` changes the mesh and returns a result. If it raises, the mesh is restored
        exactly (change journal) and the exception propagates. An unchanged mesh records
        nothing (`changed` False). Otherwise: one `MeshDeltaCommand(description)`,
        `on_applied(result)` (sets the selection residue), then the selection-mirror entry
        taken from the snapshot made before the mutation, pick cache invalidated, viewport
        notified (`moved_of(result)` = moved vertex IDs for a positions-only change, None or no
        `moved_of` = topology changed), hover re-picked."""
        mesh = self.scene.mesh
        selection_before = self._selection_snapshot()
        # Change journal (AD-023 H1): the entry holds only what `mutate` changed; a raising
        # `mutate` is rolled back exactly, an unchanged mesh records nothing.
        # Saved regions: a face this edit creates inherits its parents' regions inside the same recording (Undo restores
        # the mesh and the regions together; a raising `mutate` or hook is rolled back exactly).
        change = mesh.begin_change()
        try:
            result = mutate(mesh)
            face_regions_api.inherit_into(mesh, change)
        except BaseException:
            mesh.rollback_change(change)
            raise
        delta = mesh.end_change(change)
        if delta.empty:
            return _MeshTransaction(False, result)
        self.history.push(MeshDeltaCommand(mesh=mesh, delta=delta, description=description))
        if on_applied is not None:
            on_applied(result)
        # AD-025 §4.2: a change of point layers only moves nothing the viewport draws (the rest
        # shape): no topology rebuild now, and none on its Undo / Redo (a non-mesh mirror entry).
        layer_only = not (delta.vertices or delta.edges or delta.faces) and (
            delta.symmetry is None and delta.regions is None
        )
        self._record_selection_history(selection_before, mesh_step=not layer_only)
        moved = set() if layer_only else moved_of(result) if moved_of is not None else None
        if moved is None:
            self._notify_topology_changed()
        else:
            self._pick_cache.invalidate()
            if self.viewport is not None:
                self.viewport.on_vertices_moved(set(moved))
            self._soft_preview_refresh()
            self._refresh_hover()
        return _MeshTransaction(True, result)

    def _selection_snapshot(self) -> tuple:
        """Momentaufnahme von Modus + Auswahl (kein Hover - der wird nach
        Undo/Redo ohnehin über `_refresh_hover()` neu am Cursor gepickt,
        nicht wiederhergestellt). AD-021 §4.4/§4.6: dazu die Objekt-Auswahl und das
        Edit-Objekt - die Komponenten-IDs gelten nur zusammen mit ihm."""
        selection = self.selection
        return (
            selection.mode,
            frozenset(selection.vertices),
            frozenset(selection.edges),
            frozenset(selection.faces),
            frozenset(selection.objects),
            self.scene.edit_object_id,
        )

    def _restore_selection(self, snapshot: tuple) -> None:
        mode, vertices, edges, faces, objects, edit_object_id = snapshot
        scene = self.scene
        # An Undo that removed an object drops it from the object selection (§4.6, R-9). Q-8
        # (M2-4): the edit object of the step comes back with the entry, through E-14 so the
        # viewport and the caches follow; RF-5: a Reference never becomes the edit object.
        target = scene.objects.get(edit_object_id)
        if (
            target is not None
            and edit_object_id != scene.edit_object_id
            and target.state is not ObjectState.REFERENCE
        ):
            self._objects.set_edit_object(edit_object_id)
        selection = self.selection
        selection.mode = mode
        selection.vertices = set(vertices)
        selection.edges = set(edges)
        selection.faces = set(faces)
        selection.objects = {oid for oid in objects if oid in scene.objects}

    def _record_selection_history(
        self, before: tuple, mesh_step: bool = True, object_meshes: frozenset = frozenset()
    ) -> None:
        """Von jedem Aufrufer, der gerade `history.push()` ausgelöst hat (bzw.
        gleich auslösen wird - siehe Aufrufstellen), mit dem VOR der Mutation
        genommenen `_selection_snapshot()` aufzurufen. Spiegelt `HistoryStack.
        push()`: ein neuer Eintrag verwirft den Mirror-Redo-Zweig genau wie
        dort den echten. `mesh_step` False = ein Objekt-Schritt (AD-021 M1), dessen
        Undo/Redo das Mesh des Edit-Objekts nicht neu aufbaut. `object_meshes` (M2-3): die
        Nicht-Edit-Objekte, deren Mesh der Schritt geändert hat."""
        if getattr(self.history, "swallowed", False):
            # The push before this call kept nothing (a morph target's editing view translated it to
            # no change, `TranslatingHistory`): no mirror entry either, the stacks stay 1:1.
            self.history.swallowed = False
            return
        after = self._selection_snapshot()
        self._selection_undo_stack.append((before, after, mesh_step, frozenset(object_meshes)))
        self._selection_redo_stack.clear()

    def _prune_ghost_selection(self) -> None:
        """Entfernt jedes Handle, das `mesh` nicht mehr kennt ("ghost
        selection") - Sicherheitsnetz nach `_apply_undo_redo()`.

        Das Mesh-Command stellt das Mesh wieder her; ohne den Selection-
        Restore oben blieben Handles von Elementen, die die Mutation entfernt
        hatte, als tote IDs in `selection` liegen. Der B6-Crash-Fix
        (`_notify_topology_changed`, `element_vertices`, `resolve_selection_
        vertices`) machte Konsumenten nur tolerant gegenüber solchen IDs; sie
        zählten aber weiter in `len(selection.edges/vertices/faces)`, was z. B.
        `resolve_c_context` in den falschen Kontext auflösen konnte. Dieselbe
        `is_valid_*`-Prüfung wie dort, kein zweiter Mechanismus. Läuft nach
        jedem Undo/Redo, auch nach einem erfolgreichen Restore (dort ein
        No-op) - der einzige Fall, in dem hier tatsächlich noch etwas entfernt
        wird, ist der Mirror-Stack-Desync-Fallback in `_apply_undo_redo()`."""
        mesh = self.scene.mesh
        selection = self.selection
        selection.vertices = {v for v in selection.vertices if mesh.is_valid_vertex(v)}
        selection.edges = {e for e in selection.edges if mesh.is_valid_edge(e)}
        selection.faces = {f for f in selection.faces if mesh.is_valid_face(f)}
        selection.objects = {oid for oid in selection.objects if oid in self.scene.objects}
        hovered = selection.hovered
        if isinstance(hovered, VertexId) and not mesh.is_valid_vertex(hovered):
            selection.hovered = None
        elif isinstance(hovered, EdgeId) and not mesh.is_valid_edge(hovered):
            selection.hovered = None
        elif isinstance(hovered, FaceId) and not mesh.is_valid_face(hovered):
            selection.hovered = None
        elif isinstance(hovered, ObjectId) and hovered not in self.scene.objects:
            selection.hovered = None
        self._prune_hidden_selection()  # an Undo may have brought back what is hidden

    def _set_status(self, message: str) -> None:
        self.status_message = message
        self.status_serial += 1

    # -- can_run (AD-027 §3.3): one availability check for keys, clicks, drags, wheel, API, HUD ---------

    def can_run(self, command: str | None, ctx: RunContext) -> Refusal | None:
        """May `command` run now from `ctx.source`? None = yes; else the `Refusal` (its text None = silent).

        Pure: no status line, no hover flush, no state change. An unbound input (None) is never refused.
        Exactly the checks that ran before the command's first side effect, in the key path's order:

        1. a running session that grabs input (the Knife, the Re-Symmetrize preview): its `allows` alone;
        2. the host's `CommandGate` (AD-013 H2);
        3. the point-layer gate and the morph target's editing view (AD-025 §4.4, §15);
        4. object mode (AD-021 L-1);
        5. hidden geometry next to a topology command (`ctx.operands`: reads selection and hover);
        6. the running session's `allows` (a held gesture, a drag selection);
        7. mode policies (none yet: a pose mode adds its rule here).

        A check that runs after a side effect stays in the command as its outcome (a second W/E/R after it set
        `tweak_command`, every "nothing selected", `C: nothing to do here`)."""
        if command is None:
            return None
        session = self.interaction.session
        if session is not None and session.exclusive:
            return session.allows(command, ctx)
        gate = self.command_gate
        if gate is not None:
            text = gate.refusal(command)
            if text is not None:
                return Refusal(text)
        text = self._layer_refusal(command)
        if text is None:
            text = self._objects.mode_refusal(command)
        if text is None and ctx.operands and command in _TOPOLOGY_COMMANDS:
            text = self._hidden_refusal(command)
        if text is not None:
            return Refusal(text)
        refusal = self._session_refusal(command, ctx)
        if refusal is not None:
            return refusal
        for policy in self._mode_policies:
            refusal = policy(command, ctx)
            if refusal is not None:
                return refusal
        return None

    def _session_refusal(self, command: str, ctx: RunContext) -> Refusal | None:
        """`can_run` stage 6: the slot's sessions (a held gesture refuses its list silently, a drag selection lets
        through only its list)."""
        return self.interaction.allows(command, ctx)

    def _refused(self, refusal: Refusal) -> bool:
        """Posts a refusal's text (unless silent); always False - the event did nothing."""
        if refusal.text is not None:
            self._set_status(refusal.text)
        return False

    def _layer_refusal(self, key, meshes=None) -> str | None:
        """AD-025 §4.4: the refusal text if `key` (a command, a resolved `C` context or a method name) is
        not allowed on a target mesh with point layers (`mirai.layer_declarations`). `meshes`: the meshes the
        operation changes or copies (default: the edit mesh). Without layers there is no lookup. Unbound
        input (None) is never refused. Pure (`can_run` stage 3)."""
        if key is None:
            return None
        if self._morph.view is not None:
            # AD-025 §15: on a target's editing view only shapes change (`MorphController.view_refusal`).
            text = self._morph.view_refusal(key)
            if text is not None:
                return text
            if meshes is None:
                return None
        if meshes is None and key in PER_TARGET_COMMANDS:
            return None
        targets = (self.scene.mesh,) if meshes is None else meshes
        if not any(mesh.has_point_layers() for mesh in targets):
            return None
        return layer_refusal(key)

    def _layer_gate_refuses(self, key, meshes=None) -> bool:
        """`_layer_refusal` at an operation's own site (a method, a `C` context, Apply on several meshes):
        True and the text posted when refused."""
        text = self._layer_refusal(key, meshes)
        if text is None:
            return False
        self._set_status(text)
        return True

    # -- Morph targets (AD-025 Phase 3, `mirai.morph_targets`; keys and texts PROVISIONAL) -------------

    @property
    def morph_view_open(self) -> bool:
        """True while a morph target's editing view is the edit object (H4)."""
        return self._morph.view is not None

    @property
    def morph_document_object(self) -> SceneObject:
        """The object the document means by "the edit object": the base while its target's editing
        view is open (the view is transient: never saved, exported or sent), else the edit object."""
        return self._morph.document_object

    @property
    def morph_current_target(self):
        """The document edit object's current target (AD-025 Phase 4: the one Tab, N and +/- act on;
        view state), or None."""
        return self._morph.current_target

    @property
    def morph_weight(self) -> int:
        """The weight of the document edit object's current target in whole percent (view state)."""
        return self._morph.weight

    def morph_status_text(self) -> str | None:
        """The HUD's morph row (the current target): None = the document edit object has no target."""
        return self._morph.status_text()

    def morph_targets_text(self, limit: int = 8) -> str | None:
        """The HUD's targets row (AD-025 Phase 4, `PROVISIONAL`): every target with its weight in display
        order, the current one in brackets; None with fewer than two targets."""
        return self._morph.targets_text(limit)

    def create_morph_target(self, name: str | None = None):
        """A new target on the edit object's mesh, equal to its current shape: one Undo step; it becomes the
        current target. Returns the new `LayerId` or None (refused, status set)."""
        return self._morph.create_target(name)

    def rename_morph_target(self, name: str | None = None) -> bool:
        """Renames the edit object's target (one Undo step); without `name` the next name of
        `morph_targets.RENAME_CYCLE`."""
        return self._morph.rename_target(name)

    def delete_morph_target(self) -> bool:
        """Deletes the edit object's current target with its offsets (one Undo step)."""
        return self._morph.delete_target()

    def step_morph_target(self, step: int) -> bool:
        """The next / previous target of the document edit object becomes current (view state)."""
        return self._morph.step_target(step)

    def set_morph_weight(self, weight: int, lid=None) -> bool:
        """The weight of a target of the document edit object (default: the current one); view state."""
        return self._morph.set_weight(weight, lid)

    def edit_morph_target(self) -> bool:
        """Tab on the base (H4, AD-025 §15): the target's editing view beside the base becomes the edit object."""
        return self._morph.edit_target()

    def leave_morph_target(self) -> bool:
        """Tab on the editing view: the base is the edit object again; the view closes."""
        return self._morph.leave_target()

    def set_status(self, message: str) -> None:
        """Public form of `_set_status` (WP-SYM-LAB-03 H4, AD-013 H2 addendum):
        a host posts its own messages and refusals through the same
        `status_message`/`status_serial`, so a repeated text still counts."""
        self._set_status(message)

    # -- Pointer / Navigation (WP-06 B2, AD-019) ------------------------------

    def set_viewport_size(self, width: int, height: int) -> None:
        """Setzt die Viewport-Größe (Maus-Koordinaten-Einheit) und meldet den
        neuen Aspect an den Viewport."""
        self.viewport_width = max(int(width), 1)
        self.viewport_height = max(int(height), 1)
        self._camera_changed()

    def pointer_press(
        self, input: Input, x: float | None = None, y: float | None = None
    ) -> None:
        """Maustaste gedrückt (`input.kind == "mouse"`, Modifier beim Press).
        `x`/`y` (optional, B7): Cursor beim Press - ohne Angabe gilt die
        letzte bekannte Cursor-Position."""
        self.flush_hover()
        if x is not None and y is not None:
            self._cursor = (x, y)
        if not self.pointer.active:
            press = Press(input, x, y)
            outcome = self.interaction.grab(press)  # the Knife's point / pen lift
            if outcome is PASS:
                outcome = self.interaction.claim(press)  # the Working Pivot's placement
            if outcome is True:
                return
            self._press_point = self._cursor
            if outcome is PASS:
                outcome = self.interaction.handle(press)  # no gizmo press under the preview or a press session
            if outcome is PASS:
                self._gizmo_press(input)
        self.pointer.press(input)

    def pointer_drag(
        self, dx: float, dy: float, x: float | None = None, y: float | None = None
    ) -> bool:
        """Mausbewegung mit gedrückter Taste. True = ein Command wurde ausgeführt.
        Während einer Knife-Geste (B7.1) zählt nur die Distanz für die
        Klick-Schwelle - `x`/`y` werden nicht für eine Vorschau verwendet."""
        if x is not None and y is not None:
            self._cursor = (x, y)
        raw = Drag(None, dx, dy)
        outcome = self.interaction.grab(raw)  # the Knife's click-threshold gesture
        if outcome is PASS:
            outcome = self.interaction.claim(raw)  # the Working Pivot's LMB placement
        if outcome is not PASS:
            return outcome
        gesture = self._gesture
        if self._alt_held and gesture is not None and gesture.key == TWEAK_KEY:
            # A gizmo / Tweak drag: Alt borrows the motion for the camera, the gesture keeps running.
            return self._navigate_during_transform(dx, dy)
        step = self.pointer.drag(dx, dy)
        return step is not None and self._execute_drag(step)

    def pointer_release(self, button: str, x: float, y: float) -> bool:
        """Maustaste losgelassen. True = ein Klick-Command wurde ausgeführt
        bzw. der Knife hat einen Punkt gesetzt / den Stift abgesetzt."""
        self._cursor = (x, y)
        raw = Release(button, x, y, raw=True)
        outcome = self.interaction.grab(raw)  # the Knife's own press: its click
        if outcome is PASS:
            outcome = self.interaction.claim(raw)  # the end of the Working Pivot's LMB placement
        if outcome is not PASS:
            return outcome
        click = self.pointer.release(button, x, y)
        if not self.pointer.active:
            self._orbit_virtual = None  # the orbit gesture (if any) is over; a snapped view stays
        if button == "LEFT":
            tools = self._pointer_tools
            gizmo = tools.gizmo_press
            if gizmo is not None:
                return self._gizmo_release(gizmo, click is not None)
            drag = tools.drag_select
            if drag is not None:
                return drag.commit()
            gesture = self._gesture
            if gesture is not None and gesture.key == TWEAK_KEY:
                return gesture.commit()
            tools.end_swallowed()
        # The Knife's session gate (every release); the Re-Symmetrize preview refuses the select / region clicks.
        grabbed = self.interaction.grab(Release(button, x, y, None if click is None else click.command))
        if grabbed is not PASS:
            return grabbed
        return click is not None and self._execute_click(click, button)

    def pointer_scroll(self, input: Input) -> bool:
        """Wheel-Input (`kind == "wheel"`), aufgelöst über die Bindings. Ein Wheel mit
        gehaltener Shift-Taste trägt `{"shift"}` und ist (Default) die Soft-Radius-Stufe, eines
        mit Ctrl `{"ctrl"}` die Form der Soft-Kurve `custom` (S2d); beide zoomen nie
        (WP-SOFT-01 S2a, AD-020). In einer Knife-Session tun sie nichts.

        Live radius (AD-020, `PROVISIONAL`): während einer begonnenen Soft-Geste (Move/Rotate/Scale,
        auch per Gizmo/Tweak) ist das Zoom-Rad die Radius-Stufe dieser Geste und zoomt nicht."""
        command = self.bindings.command_for(input)
        if command == commands.ZOOM and self._gestures.soft_live():
            command = commands.SOFT_RADIUS_UP if input.value == "UP" else commands.SOFT_RADIUS_DOWN
        if command in _SOFT_COMMANDS:
            grabbed = self.interaction.grab(Wheel(input, command))
            if grabbed is not PASS:
                return grabbed
            refusal = self.can_run(command, RunContext("wheel", input))
            if refusal is not None:
                return self._refused(refusal)
            return self._execute(command)
        if command != commands.ZOOM:
            return False
        self.camera.dolly(DOLLY_IN_FACTOR if input.value == "UP" else DOLLY_OUT_FACTOR)
        self._camera_changed()
        # Unter dem ruhenden Cursor liegt nach dem Zoom ggf. ein anderer Vertex.
        if self.coalesce_hover and self.interaction.owner != "knife":
            self._hover_stale = True  # a burst of notches picks once, at the next tick
        else:
            self._refresh_hover()
        return True

    # -- Hover (WP-06 B2b, E20) -------------------------------------------------

    def pointer_motion(self, x: float, y: float, dx: float = 0.0, dy: float = 0.0) -> bool:
        """Mausbewegung ohne gedrückte Taste.

        Transform scharf (W/E/R gehalten, B3/B4): `dx`/`dy` treiben den
        Transform, kein Hover (E24). Sonst Hover unter dem Cursor im aktiven
        Modus (Vertex B2b, Edge/Face B5b). Während einer laufenden
        Pointer-Geste (Kamera) passiert beides nicht — Navigation gewinnt. True = ein Transform-Schritt lief bzw.
        `selection.hovered` hat sich geändert."""
        self._cursor = (x, y)
        if self.pointer.active:
            return False
        motion = Motion(x, y, dx, dy)
        grabbed = self.interaction.grab(motion)  # the Knife's preview
        if grabbed is not PASS:
            return grabbed
        gesture = self._gesture
        if gesture is not None and self._alt_held and gesture.command not in SMOOTH_COMMANDS:
            # Relax is held with Alt (Alt+S): for Smooth / Relax Alt never borrows the camera.
            return self._navigate_during_transform(dx, dy)
        outcome = self.interaction.handle(motion)  # the held gesture
        if outcome is not PASS:
            return outcome
        outcome = self.interaction.background(motion)  # the light drag, then the Morph weight
        if outcome is not PASS:
            return outcome
        if self.coalesce_hover:
            self._hover_stale = True
            return False
        return self._update_hover(x, y)

    def flush_hover(self) -> bool:
        """Picks a hover that `coalesce_hover` left stale (a mouse move or zoom notch since the
        last pick), at the current cursor - the pick the move would have made, for the state
        that is current now. The frame tick calls it, and every input that may read the hover
        first. True = `selection.hovered` changed."""
        if not self._hover_stale:
            return False
        self._hover_stale = False
        before = self.selection.hovered
        self._refresh_hover()
        after = self.selection.hovered
        return not (type(before) is type(after) and before == after)

    def _refresh_hover(self) -> None:
        """Hover an der letzten Cursor-Position neu picken (nach Zoom bzw.
        wenn sich das Mesh unter dem ruhenden Cursor bewegt hat). Während
        einer Knife-Session statt des Selection-Hovers die Knife-Vorschau."""
        cursor = None if self.pointer.active else self._cursor
        if self.interaction.grab(Leave() if cursor is None else Hover(*cursor)) is not PASS:
            return  # the Knife's preview (or the Re-Symmetrize preview's paused hover)
        if cursor is not None and self._gesture is None:
            self._update_hover(*cursor)

    def pointer_leave(self) -> bool:
        """Cursor hat das Fenster verlassen: Hover (bzw. Knife-Vorschau) löschen."""
        self._cursor = None
        self._hover_stale = False
        grabbed = self.interaction.grab(Leave())  # the Knife's preview
        if grabbed is not PASS:
            return grabbed
        return self._set_hovered(None)

    def _update_hover(self, x: float, y: float) -> bool:
        # Hover im aktiven Modus: Vertex (B2b), Edge oder Face (B5b).
        if self.viewport is None:
            return False
        if self._hover_suspended:
            return self._set_hovered(None)
        grabbed = self.interaction.grab(Hover(x, y))
        if grabbed is not PASS:
            return grabbed
        claimed = self.interaction.claim(Hover(x, y))  # placing the Working Pivot: its marker preview
        if claimed is not PASS:
            return claimed
        if self._gizmo_handle_at(x, y) is not None:
            # E3 (2026-10-28): inside a handle's pick zone the handle wins - no mesh hover under it, so the
            # highlight never suggests a click would select (the press goes to the handle, `_gizmo_press`).
            return self._set_hovered(None)
        if self.selection.mode is SelectionMode.OBJECT:
            # AD-021 M1 (`PROVISIONAL`): no object hover yet - it would have no look, and an
            # object pick per motion costs the full picking of every object (gollum,
            # REFERENCE_HARDWARE §2). Only a click picks in mode `4`.
            return self._set_hovered(None)
        return self._set_hovered(self._pick(x, y))

    def _pick(self, x: float, y: float):
        """E43: Element unter dem Cursor im aktiven Selection-Modus (oder None).
        WP-06 B8: cached (`self._pick_cache`) and occlusion-aware - only
        visible vertices/edges are pickable while faces are shown (Shaded/
        Flat Shaded); Wireframe leaves everything pickable, as before B8.
        AD-021 M1: in mode `4` the ObjectId under the cursor; every other mode looks at the
        edit object's mesh only, so a Reference never blocks it (RF-6)."""
        if self.selection.mode is SelectionMode.OBJECT:
            return self._objects.pick(x, y)
        hit = self._gpu_pick(self.selection.mode, x, y)
        if hit is not _CPU:
            return hit
        return pick_component(
            self._objects.edit_camera,
            self.scene.mesh,
            self.selection.mode,
            x,
            y,
            self.viewport_width,
            self.viewport_height,
            cache=self._pick_cache,
            occlusion=self.display.show_faces,
        )

    def _gpu_pick_mesh(self):
        """The edit `RenderMesh` when the window can pick from its ID buffers (AD-022 B2-out), else None
        (headless, `TraceStore`, `gpu_picking` off): the CPU picker then answers."""
        if not self.gpu_picking or self.viewport is None:
            return None
        return self.viewport.gpu_pick_mesh()

    def _gpu_failed(self, exc: BaseException) -> None:
        """A GL error in the ID pass (driver, FBO at resize): the CPU picker takes over for the rest of
        the session (AD-022 §9 abort criterion 4) and the status line says so."""
        self.gpu_picking = False
        self._set_status(f"GPU picking off ({type(exc).__name__}: {exc}) - CPU picker")

    def _gpu_pick(self, mode, x: float, y: float):
        """The GPU pick of `mode` at (x, y), or `_CPU` when the window cannot serve it."""
        rm = self._gpu_pick_mesh()
        if rm is None:
            return _CPU
        try:
            return gpu_pick_component(
                self.viewport.gpu_picker, rm, self._objects.edit_camera, self.scene.mesh, mode,
                x, y, int(self.viewport_width), int(self.viewport_height),
                occlusion=self.display.show_faces, cache=self._pick_cache,
            )
        except Exception as exc:  # noqa: BLE001 - any GL failure falls back, never breaks picking
            self._gpu_failed(exc)
            return _CPU

    def _elements_in_rect(self, rect, occlusion: bool) -> set:
        """Box Select's pick: the elements of the active mode inside `rect` (window pixels) - from the GPU ID buffers
        when the window has them (AD-022 B2-out), else (or after a GL failure, `_gpu_failed`) the CPU picker."""
        mode = self.selection.mode
        rm = self._gpu_pick_mesh()
        if rm is not None:
            try:
                return gpu_elements_in_rect(
                    self.viewport.gpu_picker, rm, self._objects.edit_camera, self.scene.mesh, mode,
                    rect, int(self.viewport_width), int(self.viewport_height),
                    cache=self._pick_cache, occlusion=occlusion,
                )
            except Exception as exc:  # noqa: BLE001 - see `_gpu_failed`
                self._gpu_failed(exc)
        return elements_in_rect(
            self._objects.edit_camera,
            self.scene.mesh,
            mode,
            rect,
            self.viewport_width,
            self.viewport_height,
            cache=self._pick_cache,
            occlusion=occlusion,
        )

    def _elements_in_polygon(self, polygon, occlusion: bool) -> set:
        """Lasso Select's pick: the elements of the active mode whose corners all lie inside `polygon` (window
        pixels) - the GPU ID buffers, else the CPU picker (as `_elements_in_rect`)."""
        mode = self.selection.mode
        width, height = int(self.viewport_width), int(self.viewport_height)
        found = None
        rm = self._gpu_pick_mesh()
        if rm is not None:
            try:
                found = gpu_elements_in_region(
                    self.viewport.gpu_picker, rm, self._objects.edit_camera, self.scene.mesh, mode,
                    lambda p: point_in_polygon(p, polygon), polygon_bounds(polygon), width, height,
                    cache=self._pick_cache, occlusion=occlusion,
                )
            except Exception as exc:  # noqa: BLE001 - see `_gpu_failed`
                self._gpu_failed(exc)
        if found is None:
            found = elements_in_polygon(
                self._objects.edit_camera, self.scene.mesh, mode, polygon, width, height,
                cache=self._pick_cache, occlusion=occlusion,
            )
        return found

    def _set_hovered(self, hovered) -> bool:
        """Setzt `selection.hovered` (reiner UI-State, kein History-Eintrag) und
        benachrichtigt den Viewport nur bei einer echten Änderung."""
        current = self.selection.hovered
        # IDs sind int-Subklassen: VertexId(3) == EdgeId(3) - Typ mitvergleichen.
        if type(current) is type(hovered) and current == hovered:
            return False
        self.selection.hovered = hovered
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_hover_changed()
        return True

    def _execute_drag(self, step: DragStep) -> bool:
        drag = Drag(step.command, step.dx, step.dy)
        outcome = self.interaction.grab(drag)
        if outcome is not PASS:
            # The open preview owns the mesh and the selection; navigation still runs. (A handle
            # pressed before the preview opened would arm a Tweak here.)
            return outcome
        outcome = self.interaction.handle(drag)  # a running drag selection; a refused gesture swallows its drags
        if outcome is not PASS:
            return outcome
        gizmo = self._pointer_tools.gizmo_press
        if gizmo is not None and step.command in (commands.SELECT_DRAG, commands.SELECT_DRAG_ADD):
            return self._gizmo_step(gizmo, step.dx, step.dy)
        if step.command in (commands.SELECT_DRAG, commands.SELECT_DRAG_ADD):
            return self._pointer_tools.start_drag_select(step.command)
        if step.command == commands.TWEAK:
            return self._tweak_step(step.dx, step.dy)
        if not self._navigate(step.command, step.dx, step.dy, snap=True):
            return False
        # Eine laufende Orbit-/Pan-Geste löscht Hover (während einer Knife-
        # Session die Knife-Vorschau; Start und Pfad bleiben); er kehrt mit
        # der nächsten Mausbewegung nach dem Release zurück.
        if self.interaction.grab(Leave()) is PASS:
            self._set_hovered(None)
        return True

    def _navigate(self, command: str, dx: float, dy: float, *, snap: bool = False) -> bool:
        """Orbit / Pan one step. `snap` (the pointer ORBIT gesture only, V-1): Shift held snaps the camera to the
        nearest standard view; the transform's Alt-orbit (`_navigate_during_transform`) never snaps."""
        if command == commands.ORBIT:
            self._orbit_step(-dx * ORBIT_RADIANS_PER_PX, -dy * ORBIT_RADIANS_PER_PX, snap)
        elif command == commands.PAN:
            self.camera.pan(dx, dy, self.viewport_width, self.viewport_height)
        else:
            return False
        self._camera_changed()
        return True

    # -- Views: ortho / standard views (WP Ortho / Views, Manu V-1/V-2 2026-10-28) ------------------------

    @property
    def view_name(self) -> str | None:
        """The standard view the camera is snapped to ("Front", ...), None = a free view."""
        return self._view_name

    @property
    def view_text(self) -> str:
        """HUD / status text of the view: "Persp", "Ortho", "Front · Ortho", "Front · Persp"."""
        projection = "Ortho" if self.camera.ortho else "Persp"
        return projection if self._view_name is None else f"{self._view_name} · {projection}"

    def _orbit_step(self, d_yaw: float, d_pitch: float, snap: bool) -> None:
        """One orbit step. In the pointer ORBIT gesture (`snap`) the gesture keeps virtual angles: with Shift held
        the camera shows the nearest standard view of them, orthographic (V-1, V-2); Shift up returns to them.
        A free step from a snapped view leaves the view and, unless ortho was switched on by hand, ortho too."""
        camera = self.camera
        if not snap:
            self._leave_view()
            camera.orbit(d_yaw, d_pitch)
            return
        if self._orbit_virtual is None:
            self._orbit_virtual = (camera.yaw, camera.pitch)
        yaw, pitch = self._orbit_virtual
        max_pitch = math.radians(85)
        self._orbit_virtual = (yaw + d_yaw, max(-max_pitch, min(max_pitch, pitch + d_pitch)))
        self._apply_orbit_virtual()

    def _apply_orbit_virtual(self) -> None:
        """The camera for the running orbit gesture's virtual angles and the held Shift."""
        yaw, pitch = self._orbit_virtual
        if self._shift_held:
            name, snap_yaw, snap_pitch = nearest_standard_view(yaw, pitch)
            if self._view_name is None:
                self._ortho_auto = not self.camera.ortho
            self._view_name = name
            self.camera.set_view(snap_yaw, snap_pitch, ortho=True)
            self._set_status(f"View: {self.view_text}")
        else:
            self._leave_view()
            self.camera.set_view(yaw, pitch)

    def _leave_view(self) -> None:
        """Out of a snapped standard view; its automatic ortho goes with it (V-2)."""
        if self._view_name is None:
            return
        self._view_name = None
        if self._ortho_auto:
            self.camera.set_ortho(False)
        self._ortho_auto = False
        self._set_status(f"View: {self.view_text}")

    def _toggle_ortho(self) -> bool:
        """`TOGGLE_ORTHO` (V-2): Ortho <-> Persp at any time; view state only (no History, not saved). Ortho set by
        hand stays when a free orbit leaves a snapped view."""
        self.camera.set_ortho(not self.camera.ortho)
        self._ortho_auto = False
        self._camera_changed()
        self._set_status(f"View: {self.view_text}")
        self._refresh_hover()
        return True

    def _navigate_during_transform(self, dx: float, dy: float) -> bool:
        """Alt held while a transform is armed or runs: Orbit (Alt+Shift: Pan) like Alt+LMB, without a
        button. The gesture is not stepped - Move/Scale continue in the new view (they read the camera per
        step); the Rotate dial keeps its virtual cursor but re-projects its pivot, so its angle can jump."""
        if dx == 0 and dy == 0:
            return False
        return self._navigate(commands.PAN if self._shift_held else commands.ORBIT, dx, dy)

    def _execute_click(self, click: Click, button: str) -> bool:
        if click.command == commands.REGION_CLICK or click.command in _SELECT_COMMANDS:
            refusal = self.can_run(click.command, RunContext("click"))
            if refusal is not None:
                return self._refused(refusal)
        if click.command == commands.REGION_CLICK:
            return self._region_click(click.x, click.y)
        if click.command in _SELECT_COMMANDS:
            self.select_at(click.command, click.x, click.y)
            return True
        return False

    def select_at(self, command: str, x: float, y: float) -> bool:
        """Klick-Selektion, Modifier-Variante AP-03 (WP-06 B2, A7/E13), im
        aktiven Modus (Vertex/Edge/Face, B5b E43).

        Treffer: SELECT ersetzt, SELECT_ADD fügt hinzu, SELECT_REMOVE entfernt,
        SELECT_TOGGLE schaltet um. Klick ins Leere: nur SELECT leert, die
        Modifier-Commands lassen die Auswahl unverändert. `Selection.mode`
        wird nicht angefasst, kein History-Eintrag. True = die Auswahl hat
        sich tatsächlich geändert (nur dann wird der Viewport benachrichtigt)."""
        if self.viewport is None:
            return False
        if self.selection.mode is SelectionMode.OBJECT:
            return self._objects.select_at(command, x, y)
        selection = self.selection
        before = selection_state(selection)
        hit = self._pick(x, y)
        if hit is None:
            if command == commands.SELECT:
                selection.clear()
        elif command == commands.SELECT:
            selection.set({hit})
        elif command == commands.SELECT_ADD:
            selection.add({hit})
        elif command == commands.SELECT_REMOVE:
            selection.remove({hit})
        elif command == commands.SELECT_TOGGLE:
            selection.toggle(hit)
        if selection_state(selection) == before:
            return False
        self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        return True

    #: B2-Name, bleibt als Weiterleitung (E43).
    select_vertex_at = select_at

    # -- Box / Paint Select (2026-10-15, Playground tools promoted, Manu) ------------------
    #
    # Box: Selection Lab KEEP (`playground/experiments/selection/decision.md`). Paint: planned
    # there ("Paint Select"), first built here. Manu 2026-10-15: the press point decides - in
    # empty space a box, on the mesh a paint stroke; no modifier replaces, Shift adds. Ctrl+drag
    # is Tweak ("Auswahl weicht"), so removing works by click only. Like a click, neither is a
    # History step. Not in mode `4` (`PROVISIONAL`).

    @property
    def selection_box(self) -> tuple[float, float, float, float] | None:
        """The rubber band of a running Box Select (min x, min y, max x, max y in window
        pixels), for the window to draw; None otherwise."""
        drag = self._pointer_tools.drag_select
        if drag is None or drag.kind != "box" or drag.cancelled:
            return None
        return normalized_rect(drag.start, drag.end)

    @property
    def selection_lasso(self) -> list[tuple[float, float]] | None:
        """The outline of a running Lasso Select (window pixels, in drawing order; the window
        closes it back to the first point), for the window to draw; None otherwise."""
        drag = self._pointer_tools.drag_select
        if drag is None or drag.kind != "lasso" or drag.cancelled:
            return None
        return list(drag.points)

    @property
    def selection_through(self) -> bool:
        """True while a running Box / Lasso would select through the mesh if released now: Alt is
        held (WP Toolbox Gaps A2, Manu 2026-10-23: "nach dem Gummiband-Aufziehen Alt gedrückt
        halten"). Alt at the press is still Orbit - by then the drag is no selection. The window
        draws the band in the through colour."""
        drag = self._pointer_tools.drag_select
        return drag is not None and drag.kind in ("box", "lasso") and not drag.cancelled and self._alt_held

    # -- Working Pivot (2026-10-28, Manu U-1..U-4, AD-012 addendum; `mirai.pivot`) ----------------------
    # Hold the key + LMB click places it, a tap switches it off / on (U-1); a click on the mesh lands inside the
    # volume, Shift on a vertex / edge point (U-2); it stays until replaced or off, and is no undo step (U-3); W/E/R
    # keep World axes and turn / scale around it (U-4). Mode `4` keeps the objects' own pivots (AD-021 Q-13). The
    # hold key and the pivot are `controllers.pointer_tools`' since AD-027 M4.

    @property
    def working_pivot(self) -> WorkingPivot | None:
        """The placed Working Pivot (also while off or on another object); None = never placed."""
        return self._pointer_tools.working_pivot

    @property
    def active_pivot(self):
        """The Working Pivot's position (edit-object space) when W/E/R use it - placed, on, of the edit object, not
        in mode `4`; None = the selection centre as before."""
        pivot = self._pointer_tools.working_pivot
        if pivot is None or not pivot.enabled or pivot.object_id != self.scene.edit_object_id:
            return None
        if self.selection.mode is SelectionMode.OBJECT:
            return None
        return pivot.position

    @property
    def pivot_placing(self) -> bool:
        """True while the placement key is held."""
        return self._pointer_tools.pivot.key is not None

    def pivot_marker_items(self) -> list:
        """What the window draws for the Working Pivot (`viewport.gizmo.pivot_marker_items`): the active pivot,
        also during a gesture, and the dimmed preview while placing; [] otherwise."""
        if self.viewport is None or self.knife_active:
            return []
        items = []
        edit = self.scene.edit_object
        pivot = self.active_pivot
        if pivot is not None:
            world = object_space.to_world(edit, pivot)
            items += _gizmo.pivot_marker_items(self.camera, world, scale=self.gizmo_scale)
        hold = self._pointer_tools.pivot
        if hold.key is not None and hold.preview is not None and not hold.dragging:
            world = object_space.to_world(edit, hold.preview)
            items += _gizmo.pivot_marker_items(self.camera, world, scale=self.gizmo_scale, preview=True)
        return items

    # -- Transform gizmo (2026-10-21, promoted from the Playground, Manu "Gizmo nach src/") -----
    #
    # AD-016 D3 (Artist verdict 2026-09-21): the gizmo is an entry point. An LMB press on a handle (no
    # modifier) takes priority over the selection click: a click only sets the axis constraint (like X/Y/Z),
    # click + drag also runs the current tool - the last W/E/R, Move until one is pressed (D2) - along it, the
    # release commits, Esc cancels. A miss falls through unchanged. The drag is the LMB-drag transform
    # (`_transform_arm` / `GestureSession.motion` with `TWEAK_KEY` and the selection as the target), so it is one
    # History step, honours Soft Selection and Symmetry, and is refused where W/E/R is.
    # 2026-10-28 (Manu A1/A4/A5, E2/E3/E5): with one-shot constraints a handle click sets the one-shot constraint
    # (like X) and a handle drag is constrained for that drag only (commit clears, Esc restores what was pending);
    # inside a handle's pick zone the handle wins over the mesh hover; session sizes `gizmo_size_name`.
    # World frame only (normal space is not in the app); shown for point / edge / face selections, also of a
    # placed edit object (2026-10-23: at the selection's world position, in the world camera; the tools turn
    # the world axes into object space, E-8), hidden while any gesture runs. Look and sizes `PROVISIONAL` (`viewport.gizmo`).
    # Object level (2026-10-23): in mode `4` it sits at the centroid of the selected non-Reference objects'
    # world pivots and drives the object gesture (`ObjectController.arm_gesture`, the same Tweak path), in the world camera.

    def _gizmo_pivot(self):
        """The selection's centroid (world), cached until the selection or the vertex positions change;
        None when the gizmo is not shown: off, no viewport, Knife session, nothing selected. In
        mode `4` see `_gizmo_object_pivot`. With a placed edit object the centroid is mapped to world
        (`object_space.to_world`, an exact pass-through while the placement is identity); the cache
        holds the object-space centroid, so a placement change needs no invalidation."""
        viewport = self.viewport
        if not self.gizmo_enabled or viewport is None or self.knife_active:
            return None
        if self.selection.mode is SelectionMode.OBJECT:
            return self._gizmo_object_pivot()
        ids = self._pointer_tools.active_selection_ids()
        if not ids:
            return None
        key = (viewport.geometry_revision, id(self.scene.mesh), self.selection.mode, len(ids), hash(frozenset(ids)))
        cache = self._gizmo_cache
        if cache is not None and cache[0] == key:
            pivot = cache[1]
        else:
            mesh = self.scene.mesh
            vertex_ids = resolve_selection_vertices(mesh, self.selection, self.selection.mode)
            pivot = selection_pivot(mesh, vertex_ids) if vertex_ids else None
            self._gizmo_cache = (key, pivot)  # also with a Working Pivot: `_gizmo_frame` keys on it
        if pivot is not None and self.active_pivot is not None:
            # The gizmo shows where W/E/R turn and scale: the Working Pivot while it is on (U-1).
            pivot = self.active_pivot
        return None if pivot is None else object_space.to_world(self.scene.edit_object, pivot)

    def _gizmo_object_pivot(self):
        """Mode `4`: the centroid of the selected objects' world pivots, References excluded (they are
        locked, `ObjectController.targets`); None when no movable object is selected. Cheap, so not cached."""
        scene = self.scene
        targets = [
            scene.objects[oid]
            for oid in self.selection.objects
            if oid in scene.objects and scene.objects[oid].state is not ObjectState.REFERENCE
        ]
        # A mirror pair is one unit (proposal §5.4): with both selected the gizmo sits on the driver.
        ids = {obj.id for obj in targets}
        followers = set()
        for obj in targets:
            pair = scene.mirror_pair_of(obj.id)
            if pair is not None and pair.other(obj.id) in ids:
                followers.add(max(pair.a, pair.b))
        targets = [obj for obj in targets if obj.id not in followers]
        if not targets:
            return None
        points = [object_space.to_world(obj, obj.pivot) for obj in targets]
        return tuple(sum(p[i] for p in points) / len(points) for i in range(3))

    def _gizmo_frame(self) -> tuple[list, list]:
        """The gizmo's axes and planes in world space: the world axes, or in Normal space (C1) the
        selection's frame (`transform_space.normal_frame`: X/Y/Z for one face, Z only otherwise, nothing
        but the free handles when the selection has no normal). Mode `4` stays on the world axes (the
        object gesture). Cached with the same key as the pivot."""
        if self._gestures.orientation == transform_space.WORLD or self.selection.mode is SelectionMode.OBJECT:
            return _gizmo.WORLD_AXES, _gizmo.WORLD_PLANES
        # The pivot is computed first (`_gizmo_pivot`), so its cache key is current here.
        key = self._gizmo_cache[0] if self._gizmo_cache is not None else None
        cache = self._gizmo_frame_cache
        if key is None or cache is None or cache[0] != key:
            frame = transform_space.normal_frame(self.scene.mesh, self.selection)
            self._gizmo_frame_cache = (key, frame)
        else:
            frame = cache[1]
        if frame is None:
            return [], []
        edit = self.scene.edit_object

        def world(v):
            return object_space.axis_to_world(edit, v)

        axes = [(name, world(d)) for name, d in frame.axes()]
        planes = [(name, world(a), world(b)) for name, a, b in frame.planes()]
        return axes, planes

    @property
    def _gizmo_camera(self):
        """The gizmo lives in world space, at both levels: the pivot is a world point and the handles
        are the world axes. (While the edit object is unplaced this is the same camera as before.)"""
        return self.camera

    def gizmo_camera_uniforms(self) -> list[float]:
        """The `view` + `proj` uniforms `draw_gizmo` needs: no model matrix, the items are world points."""
        return self.viewport.world_camera_uniforms()

    def _gizmo_pivot_if_shown(self):
        """`_gizmo_pivot()` while the gizmo is up: not while a transform key is down, any drag gesture runs
        or the Re-Symmetrize preview is open."""
        if (
            self._gesture is not None
            or self._pointer_tools.drag_select is not None
            or self.resymmetrize_preview is not None
        ):
            return None
        return self._gizmo_pivot()

    @property
    def gizmo_tool(self) -> str:
        """The tool the gizmo shows and a handle drag runs (`move` / `rotate` / `scale`)."""
        return _GIZMO_TOOLS.get(self.tweak_command, "move")

    @property
    def gizmo_constraint(self) -> str | None:
        return self._gestures.axis_constraint

    def gizmo_items(self) -> list:
        """What the window draws for the gizmo (`viewport.gizmo.draw_items`), [] while it is not shown.
        The handle under the cursor is highlighted (hover feedback; it never arms anything)."""
        pivot = self._gizmo_pivot_if_shown()
        if pivot is None:
            return []
        camera = self._gizmo_camera
        hover = None
        if self._cursor is not None and not self.pointer.active:
            hover = self._gizmo_handle_at(*self._cursor, pivot=pivot)
        axes, planes = self._gizmo_frame()
        return _gizmo.draw_items(
            camera, pivot, self.gizmo_tool, self._gestures.axis_constraint, hover, axes, planes, scale=self.gizmo_scale
        )

    @property
    def gizmo_scale(self) -> float:
        """The session size as the gizmo's fraction of the eye distance (`viewport.gizmo.GIZMO_SIZES`)."""
        return _gizmo.GIZMO_SIZES[self.gizmo_size_name]

    def _gizmo_handle_at(self, x: float, y: float, pivot=None) -> str | None:
        pivot = self._gizmo_pivot_if_shown() if pivot is None else pivot
        if pivot is None:
            return None
        axes, planes = self._gizmo_frame()
        return _gizmo.pick_handle(
            self._gizmo_camera, pivot, axes, planes, self.gizmo_tool, x, y,
            int(self.viewport_width), int(self.viewport_height), scale=self.gizmo_scale,
        )

    def _gizmo_press(self, input: Input) -> None:
        """LMB press without a modifier on a handle: it owns the gesture and sets the constraint now."""
        if not self.gizmo_enabled or input.value != "LEFT" or input.modifiers or self._cursor is None:
            return
        handle = self._gizmo_handle_at(*self._cursor)
        if handle is None:
            return
        gestures = self._gestures
        self._pointer_tools.press_gizmo(handle, tuple(self._cursor), gestures.axis_constraint)
        # `center` (free Move / Rotate trackball / uniform Scale) and `screen` (Rotate about the view axis)
        # are the unconstrained handles.
        gestures.axis_constraint = None if handle in ("center", "screen") else handle
        self._set_hovered(None)
        self._set_status(gestures.constraint_status())

    def _gizmo_step(self, gizmo, dx: float, dy: float) -> bool:
        """A drag step of a gesture that started on a handle (`gizmo`, the press session; refused drags it swallowed
        itself): the first one arms the current tool on the selection (an LMB-drag transform with the selection as
        target), every step drives it."""
        gesture = self._gesture
        if gesture is None:
            if self.viewport is None or self._refused_tweak():
                gizmo.refused = True
                return False
            if not self._transform_arm(self.tweak_command, TWEAK_KEY):
                gizmo.refused = True
                return False
            gesture = self._gesture
        elif gesture.key != TWEAK_KEY:
            return False
        stepped = gesture.motion(dx, dy)
        if self._gesture is None:
            gizmo.refused = True  # refused at begin (seam, symmetric Soft)
        return stepped

    def _refused_tweak(self) -> bool:
        """The first step of a gizmo / Tweak drag asks `can_run(TWEAK)` (a Knife session, the host gate)."""
        refusal = self.can_run(commands.TWEAK, RunContext("drag"))
        if refusal is None:
            return False
        self._refused(refusal)
        return True

    def _gizmo_release(self, gizmo, clicked: bool) -> bool:
        """LMB released: commit a running handle drag; a plain click on a handle leaves just the constraint."""
        self.interaction.end_press(gizmo)
        gesture = self._gesture
        if gesture is not None and gesture.key == TWEAK_KEY:
            return gesture.commit()
        self._refresh_hover()
        return clicked

    # -- `Tweak` drag command (2026-10-15, Tweak Lab V2 "Silo" KEEP, Manu: "Ctrl+LMB, Auswahl weicht") ------
    # 2026-10-28 (Manu A3): its Ctrl+LMB-drag binding is removed (keymap.json and the code default); the command
    # stays bindable (E4). "Tweak" in user-facing text now means the hold-key gesture (A2).

    def _tweak_step(self, dx: float, dy: float) -> bool:
        """The `Tweak` drag: the first step arms `tweak_command` (the last W/E/R, Move by default)
        like holding its key - target = the selection, else the element under the press point
        (Tweak Lab rule; the selection is not changed) - and every step drives it. Ctrl may be
        let go during the drag; the LMB release commits, Esc cancels (`_cancel`). A refused drag swallows the rest
        of its steps (`pointer_tools.swallow`)."""
        tools = self._pointer_tools
        gesture = self._gesture
        if gesture is None:
            if self.viewport is None or self._refused_tweak():
                tools.swallow()
                return False
            if self.selection.mode is not SelectionMode.OBJECT:
                press = self._press_point if self._press_point is not None else self._cursor
                if not tools.active_selection_ids() and press is not None:
                    self._set_hovered(self._pick(*press))
            if not self._transform_arm(self.tweak_command, TWEAK_KEY):
                tools.swallow()
                return False
            gesture = self._gesture
        elif gesture.key != TWEAK_KEY:
            return False
        stepped = gesture.motion(dx, dy)
        if self._gesture is None:
            # Refused at begin (seam, symmetric Soft): no re-arm until the release.
            tools.swallow()
        return stepped

    def _camera_changed(self) -> None:
        if self.viewport is not None:
            self.viewport.on_camera_changed(self.viewport_width / self.viewport_height)

    def update_viewport(self, delta_t: float) -> None:
        """Viewport-Tick (delta_t in Sekunden).

        Gate 3: bewusst ein No-op (kein Viewport vorhanden). Existiert als
        stabiler Integrationspunkt.
        Gate 7: Ruft `Viewport.sync()` auf, wenn ein Viewport gebunden ist
        (nach `init_scene()`). Dadurch fließen Kamera-/Geometry-/Selection-
        Dirty-States in die GPU-Ressourcen. Ohne gebundenen Viewport
        (z. B. vor `init_scene()`) bleibt es ein No-Op.
        WP-VIEW-PERF-01 Slice 2: picks a hover left stale by `coalesce_hover` first
        (`flush_hover`), once per tick.
        """
        if self.viewport is not None:
            self.flush_hover()
            self._objects.sync_highlight()
            self._push_region_tints()
            self.morph.refresh()
            self.viewport.sync()

    def shutdown(self) -> None:
        """Sauberes Herunterfahren: aktives Tool deaktivieren (kein stale State);
        eine laufende Knife-Session wird verworfen (wie Esc)."""
        self._knife.shutdown()
        self.tool_manager.deactivate()