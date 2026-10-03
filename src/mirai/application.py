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
import time
from pathlib import Path
from typing import Optional

from core import EdgeId, FaceId, HistoryStack, Scene, Selection, SelectionMode, VertexId

from viewport import Viewport  # Gate 7: V0.2 Rendering-Viewport (unabhängig von mirai)
from viewport.overlay import TOOL_ACTIVE_LAYER, TOOL_PREVIEW_LAYER
from viewport.resource_store import ResourceStore, TraceStore

from .interaction import BindingSet, Input, ToolManager, commands
from .interaction.bindings import build_default_bindings, load_keymap_overrides
from .interaction.input import KNIFE_CONTEXT
from .interaction.pointer import CLICK_THRESHOLD_PX, Click, DragStep, PointerGestures
from .interaction.routing import tool_for_command
from .interaction.tools import resolve_selection_vertices
from .mesh_geometry import mesh_center_and_radius
from .topology.connect_per_face import TopologyToolError, connect_selected_edges_per_face
from .topology.connect_vertices_per_face import VertexConnectError, connect_vertices_per_face
from .topology.contextual_c import CContext, resolve_c_context
from .topology.face_geometry import GEO_EPS
from .topology.knife import CLOSE_NEEDS, EARLIER_INTERIOR, TOO_CLOSE, KnifeTool
from .topology.knife_pick import knife_pick, snap_own_point, space_point
from .topology.knife_preview import KnifeRenderData, build_knife_render_data
from .topology.split import split_selected_edge
from .viewport import DisplayMode, DisplayState, OrbitCamera
from .viewport.picking import pick_component
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


#: WP-06 B4 (E28): die drei Transform-Commands, die über denselben AD-016-
#: hold-key-hover-Pfad scharf geschaltet werden. Werte: (Label, Verb, Partizip)
#: für die Statuszeilen (E34, `PROVISIONAL`).
_TRANSFORM_COMMANDS: dict[str, tuple[str, str, str]] = {
    commands.MOVE: ("Move", "move", "moved"),
    commands.ROTATE: ("Rotate", "rotate", "rotated"),
    commands.SCALE: ("Scale", "scale", "scaled"),
}

#: WP-06 B4 (E32): Constraint-Command → `space`-String nach AD-012
#: (`transform._resolve_space`). Welche Taste welches Command auslöst
#: (Blender: Shift+Achse schließt diese Achse aus), steht in `bindings.py`.
_CONSTRAINT_SPACES: dict[str, str] = {
    commands.CONSTRAIN_AXIS_X: "x",
    commands.CONSTRAIN_AXIS_Y: "y",
    commands.CONSTRAIN_AXIS_Z: "z",
    commands.CONSTRAIN_PLANE_XY: "xy",
    commands.CONSTRAIN_PLANE_XZ: "xz",
    commands.CONSTRAIN_PLANE_YZ: "yz",
}


#: WP-06 B5a (E42): Display-Commands, alle über die bestehenden
#: `DisplayState`-Übergänge.
_DISPLAY_COMMANDS = (
    commands.CYCLE_DISPLAY_MODE,
    commands.TOGGLE_WIREFRAME_OVERLAY,
    commands.SET_SHADED,
    commands.SET_FLAT_SHADED,
    commands.SET_WIREFRAME,
)

_SET_DISPLAY_MODES: dict[str, DisplayMode] = {
    commands.SET_SHADED: DisplayMode.SHADED,
    commands.SET_FLAT_SHADED: DisplayMode.FLAT_SHADED,
    commands.SET_WIREFRAME: DisplayMode.WIREFRAME,
}


#: WP-06 B5b (E43): Component-Modi 1/2/3 (Selection Lab KEEP, `PROMOTED`).
_MODE_COMMANDS: dict[str, SelectionMode] = {
    commands.SET_VERTEX_MODE: SelectionMode.VERTEX,
    commands.SET_EDGE_MODE: SelectionMode.EDGE,
    commands.SET_FACE_MODE: SelectionMode.FACE,
}


def _element_vertices(mesh, element) -> set[VertexId]:
    """Vertices eines einzelnen Vertex/Edge/Face (Hover-Fallback des Transforms).

    Ein Handle, das `mesh` nicht mehr kennt (Topologie-Mutation seither),
    ergibt eine leere Menge statt eines `KeyError` — dieselbe Regel wie im
    Viewport-Overlay (`viewport/overlay.py`)."""
    if isinstance(element, VertexId):
        return {element} if mesh.is_valid_vertex(element) else set()
    if isinstance(element, EdgeId):
        return set(mesh.edge_vertices(element)) if mesh.is_valid_edge(element) else set()
    if isinstance(element, FaceId):
        return set(mesh.face_vertices(element)) if mesh.is_valid_face(element) else set()
    return set()


def _active_selection_contains(selection: Selection, element) -> bool:
    """Liegt `element` in der Auswahl des aktiven Modus (Playground
    `_sel_contains_hovered`)? Typ mitprüfen - IDs sind int-Subklassen."""
    kind, members = {
        SelectionMode.VERTEX: (VertexId, selection.vertices),
        SelectionMode.EDGE: (EdgeId, selection.edges),
        SelectionMode.FACE: (FaceId, selection.faces),
    }[selection.mode]
    return isinstance(element, kind) and element in members


def _constraint_label(space: str | None) -> str:
    """Statuszeilen-Text einer Constraint: "X", "YZ plane", "none"."""
    if space is None:
        return "none"
    return space.upper() if len(space) == 1 else f"{space.upper()} plane"


def _selection_state(selection: Selection) -> tuple[frozenset, frozenset, frozenset]:
    return (
        frozenset(selection.vertices),
        frozenset(selection.edges),
        frozenset(selection.faces),
    )


# WP-KNIFE-01 S3 (PROVISIONAL wording, decision.md "One Knife S3"): status for a refused Knife click
# by the tool's reason - the S3 cases are named, every other refusal keeps the S2 text.
_KNIFE_REFUSED = {
    TOO_CLOSE: "Knife: too close to an edge - click on the edge or further inside the face",
    CLOSE_NEEDS: "Knife: closing a shape needs at least 3 points",
    EARLIER_INTERIOR: "Knife: an earlier point inside a face cannot be clicked again (not yet)",
}


# WP-KNIFE-01 UX2 (D7, decision.md "WP-KNIFE-01 UX2"): two Knife clicks this close in time (s) and
# place (px) are a double-click.
KNIFE_DOUBLE_CLICK_S = 0.35
KNIFE_DOUBLE_CLICK_PX = 4.0

# The preview builder ends a chain at a "closed" break only; a pen lift is drawn the same way.
_KNIFE_DRAWN_LIFT = {"kind": "break", "reason": "closed", "cyclic": False}


def _knife_notes(res) -> list[str]:
    """What the commit joined or dropped (`KnifeResolution`), for the status line. Nothing of it is
    shown while cutting (Artist, 2026-09-30: the join to the nearest corner is made at commit only)."""
    if res is None:
        return []
    notes = []
    if res.joined:
        notes.append(f"{res.joined} last point(s) inside a face joined to the nearest corner")
    if res.dropped_tail:
        notes.append("a last point inside a face could not be joined to a corner - dropped")
    if res.dropped_lead:
        notes.append("first point(s) inside a face before any edge or vertex dropped")
    rejected = [shape for shape in res.closed_shapes if not shape.built]
    if rejected:
        notes.append(f"{len(rejected)} closed shape(s) could not be built")
    if res.short_shapes:
        notes.append(f"{len(res.short_shapes)} shape(s) inside a face with fewer than 3 points dropped")
    if res.skipped_shapes:
        notes.append(f"{res.skipped_shapes} closed shape(s) skipped - their face was already cut")
    for reason, n in sorted(res.loops_dropped.items()):
        notes.append(f"{n} loop(s) closed at a point dropped ({reason})")
    if res.lost_continuation:
        notes.append("the cut on from an interior start point dropped")
    return notes


def _knife_plan_notes(plan) -> list[str]:
    """What a click's segment across faces left uncut (WP-KNIFE-01 S4, PROVISIONAL wording)."""
    notes = []
    if plan.hidden:
        notes.append(f"{plan.hidden} hidden crossing(s) not cut")
    if "gap" in plan.skipped:
        notes.append("skipped: over a hole, border or hidden part")
    if plan.method and "edge" in plan.skipped:
        notes.append("skipped: along an existing edge")
    return notes

class Application:
    """Window-unabhängiger Produktions-Orchestrator."""

    def __init__(self, keymap_path: Optional[str | Path] = None) -> None:
        # Core-Strukturen
        self.scene: Scene = Scene()
        self.selection: Selection = self.scene.selection
        self.history: HistoryStack = self.scene.history

        # Viewport-State (kein Rendering in Gate 3)
        self.camera: OrbitCamera = OrbitCamera()
        self.display: DisplayState = DisplayState()

        # WP-06 B8 (picking speed + occlusion, PROVISIONAL): screen-space pick
        # cache, refreshed lazily per camera/mesh state (`picking_cache.py`).
        # Orbit/zoom/pan invalidate it automatically (keyed on
        # `camera.camera_revision`); every other trigger from the handoff
        # (Move/Rotate/Scale commit, Undo/Redo, Split/Connect, Knife cut,
        # display-mode change) calls `self._pick_cache.invalidate()`
        # explicitly at its existing mutation/notification call site.
        self._pick_cache: PickCache = PickCache()

        # Gate 7: V0.2 Viewport wird in init_scene() mit dem Mesh gebunden.
        # Bliebt None, bis init_scene() aufgerufen wurde (kein Mesh verfügbar).
        self.viewport: Viewport | None = None

        # Tools
        self.tool_manager: ToolManager = ToolManager()
        self._setup_tools()

        # Input
        # Gate 6 (Input Config): Default → optionales keymap.json → BindingSet.
        # Das Overlay wird genau einmal beim Application-Start geladen; eine
        # vorhandene, ungültige Datei wird kontrolliert abgelehnt
        # (`KeymapConfigError`). Kein Runtime-Hot-Reload.
        self.bindings: BindingSet = build_default_bindings()
        if keymap_path is not None:
            load_keymap_overrides(self.bindings, keymap_path)

        # WP-06 B2 (AD-019): Pointer-Gesten laufen über dieselben Bindings.
        # Größe in logischen Fenster-Pixeln (gleiche Einheit wie die
        # Maus-Koordinaten); der Entry-Point setzt sie über set_viewport_size().
        self.pointer: PointerGestures = PointerGestures(self.bindings)
        self.viewport_width: int = 1
        self.viewport_height: int = 1
        # WP-06 B2b (E20): letzte bekannte Cursor-Position (None = unbekannt
        # bzw. Cursor außerhalb des Fensters) - für das Hover-Re-Pick nach Zoom.
        self._cursor: tuple[float, float] | None = None

        # WP-06 B3 (E26, `PROVISIONAL` bis ein HUD existiert): letzte
        # Statusmeldung für den Nutzer. `status_serial` zählt jede Meldung,
        # damit der Entry-Point auch eine wiederholte, gleichlautende Meldung
        # (z. B. zweimal "Undo") erkennt.
        self.status_message: str = ""
        self.status_serial: int = 0

        # WP-06 B3 (E21, AD-016 D4 hold-key-hover), generalisiert in B4 (E28)
        # auf Move/Rotate/Scale: `_transform_key` ist die Taste, die scharf
        # geschaltet hat (None = nicht scharf); das Release wird über ihren
        # Wert erkannt, nicht über die Bindings, weil sich die Modifier
        # zwischen Press und Release ändern dürfen (z. B. Alt für Orbit,
        # während W gehalten wird). Das Ziel ist ab dem Press fix; `begin()`
        # läuft erst bei der ersten Mausbewegung. `_transform_space` ist der
        # `space`, mit dem die laufende Geste begonnen hat (None = frei).
        self._transform_key: str | None = None
        self._transform_command: str | None = None
        self._transform_target: frozenset[VertexId] = frozenset()
        self._transform_begun: bool = False
        self._transform_space: str | None = None
        # WP-06 B4.1 (Artist-Entscheidung Manu 2026-09-27, Playground-Verhalten
        # WP-AP-INPUT-FIX-03 1:1): sticky Achsen-Constraint, unabhängig vom
        # scharfen Tool, überlebt Commit/Cancel/neues Scharfschalten und wird
        # bei jedem `begin()` gelesen. None = frei.
        self._axis_constraint: str | None = None

        # WP-06 B6 Follow-up (Artist-Entscheidung Manu 2026-09-28): Undo/Redo
        # stellt jetzt auch die Selection wieder her, nicht nur das Mesh.
        # `HistoryStack` (core, frozen) kennt kein Selection-Konzept und
        # bietet keinen Hook vor/nach push() - deshalb führt Application
        # einen eigenen Stack von (before, after)-Selection-Snapshots parallel
        # zu jedem `history.push()`, den sie selbst auslöst (Split/Edge
        # Connect/Vertex Connect in `_connect_command`, Transform-Commit in
        # `key_release`; das sind aktuell die einzigen Aufrufer). `before` =
        # Snapshot unmittelbar vor der Mutation, `after` = Snapshot danach
        # (die von `_connect_command` gesetzte Residue-Auswahl bzw. bei
        # Transformen dieselbe Auswahl, da Move/Rotate/Scale die Selection
        # nicht ändern). Struktur und Semantik spiegeln `HistoryStack`
        # bewusst 1:1 (ein `_record_selection_history()` pro Push, Redo-Stack
        # wird dabei geleert). Ist der Mirror-Stack leer, obwohl History
        # Undo/Redo erlaubt (z. B. künftiger Push-Pfad, der hier noch nicht
        # verdrahtet ist), fällt `_apply_undo_redo()` auf reines Pruning
        # zurück statt zu crashen.
        self._selection_undo_stack: list[tuple[tuple, tuple]] = []
        self._selection_redo_stack: list[tuple[tuple, tuple]] = []

        # WP-06 B7.1 (AD-017 Knife; click-only = Artist decision Manu 2026-09-28,
        # after the B7 window test: press-slide-release was redundant with the
        # live hover preview): laufende Knife-Session (None = keine). `KnifeTool`
        # hält Mesh-Schritte, Start und Pfad; hier liegt nur der Interaktions-
        # zustand: das gültige prospektive Ziel (None = keins oder ungültig),
        # die hervorgehobene Edge (gehovert) und ob die LMB-Geste des Knife
        # gerade gehalten wird (nur zur Klick-Schwellen-Erkennung).
        # `_knife_selection_before` ist der Snapshot vor der Session für den
        # Selection-Mirror-Stack beim Commit.
        self._knife: KnifeTool | None = None
        self._knife_selection_before: tuple | None = None
        self._knife_target: dict | None = None
        self._knife_highlight_edge: EdgeId | None = None
        self._knife_gesture: bool = False
        self._knife_gesture_moved: float = 0.0
        # WP-KNIFE-01 UX2: the gesture's button (LMB = a point, RMB = pen lift),
        # Shift at the press (midpoint snap; the gesture is fixed at the press,
        # AD-019), and the last LMB click (time, x, y) for the double-click on
        # `knife_clock` (injectable for headless tests).
        self._knife_gesture_button: str = "LEFT"
        self._knife_gesture_midpoint: bool = False
        self._knife_last_click: tuple[float, float, float] | None = None
        self.knife_clock = time.monotonic
        # WP-KNIFE-01 UX2b: any Shift key held, as the window reports it
        # (`set_shift_held`). Only the Knife's hover reads it (the midpoint before
        # the click); a click keeps deciding by its press modifiers (A2, AD-019).
        self._shift_held: bool = False
        # WP-KNIFE-01 S4: where the hovered segment crosses edges (the planner's dots).
        self._knife_hover_crossings: tuple = ()

    def _setup_tools(self) -> None:
        """Registriert die Default-Tools (Move/Rotate/Scale) im ToolManager."""
        for command, tool_class in (
            (commands.MOVE, tool_for_command(commands.MOVE)),
            (commands.ROTATE, tool_for_command(commands.ROTATE)),
            (commands.SCALE, tool_for_command(commands.SCALE)),
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
    ) -> None:
        """Initialisiert die Default-Szene (Würfel oder OBJ-Import).

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

        `point_overlay_type` (WP-06 B2b, E17): gleiches Durchreich-Muster wie
        `store_type`. Default `None` = kein GL-Punkt-Overlay (headless); der
        Entry-Point übergibt `GLPointOverlay`.

        `line_overlay_type` (WP-06 B5a, E38): dasselbe Muster für das
        Edge-Linien-Overlay; der Entry-Point übergibt `GLLineOverlay`. Der
        aktuelle `DisplayState` wird sofort an den neuen Viewport gegeben.

        `face_overlay_type` (WP-06 B5b, E45): dasselbe Muster für selektierte
        bzw. gehoverte Faces; der Entry-Point übergibt `GLTriangleOverlay`."""
        if geometry_type == "cube":
            from .scene_factory import create_cube

            self.scene.mesh = create_cube()
        elif geometry_type == "obj":
            if obj_path is None:
                raise ValueError('geometry_type="obj" requires obj_path')

            from .scene_factory import build_core_scene_from_obj

            self.scene.mesh = build_core_scene_from_obj(obj_path).mesh

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
        self._apply_display()

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
        self.camera.frame_on_bounds(center, radius)

    def dispatch_command(
        self, command: str, context: Optional[dict] = None, **params
    ) -> bool:
        """Dispatchet ein Command (True = wurde behandelt).

        Tool-Commands → ToolManager (Pattern A: nur aktivieren; Pattern B:
        mit `context` sofort `begin(**context)`).
        Undo/Redo → History.
        Display-Commands → `DisplayState` + Viewport (WP-06 B5a, E42).
        Modus-Commands → `Selection.mode` (WP-06 B5b, E43).
        Alles andere → False (bewusst minimal gehalten).
        """
        tool_class = tool_for_command(command)
        if tool_class:
            return self.tool_manager.activate(command, context=context)

        if self._knife is not None and command in (commands.UNDO, commands.REDO):
            # AD-017 history isolation: während einer Knife-Session nie die
            # globale History - auch nicht über den direkten Command-Pfad.
            return self._knife_history_step(command)
        if command in (commands.UNDO, commands.REDO):
            self._apply_undo_redo(command)
            return True
        if command in _DISPLAY_COMMANDS:
            return self._display_command(command)
        if command in _MODE_COMMANDS:
            return self._set_selection_mode(_MODE_COMMANDS[command])
        if command == commands.CONNECT:
            return self._connect_command()

        return False

    # -- Component-Modi (WP-06 B5b) ---------------------------------------------

    def _set_selection_mode(self, mode: SelectionMode) -> bool:
        """1/2/3 wie Playground `window.py`: Modus setzen, Auswahl leeren, Hover
        löschen (R-SEL-2). Auch der bereits aktive Modus leert die Auswahl
        (Playground-Verhalten). Kein History-Eintrag; der Hover kommt mit der
        nächsten Mausbewegung im neuen Modus zurück."""
        self.selection.mode = mode
        self.selection.clear()
        self.selection.hovered = None
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._set_status(f"Mode: {mode.name.capitalize()}")
        return True

    # -- Contextual C: Split / Edge Connect / Vertex Connect (WP-06 B6, AD-017) --

    def _connect_command(self) -> bool:
        """`C`: resolves the selection context (`resolve_c_context`, same
        dispatch as the Playground `window.py`) and applies Split / Edge
        Connect / Vertex Connect through the shared `mirai.topology`
        implementation; an empty selection begins a Knife session (WP-06
        B7, `_knife_begin`). Mutates only through
        `Mesh.split_edge`/`Mesh.connect_vertices` (ARCH-02); exactly one
        `MeshStateCommand` per success, mesh and history untouched on
        rejection or no-op. Each success branch reports the topology change
        through `_notify_topology_changed()`, which also re-anchors the hover
        (the hovered edge/face handle can be gone after Split/Connect), and
        records the pre-mutation selection for Undo/Redo restore (WP-06 B6
        follow-up, `_record_selection_history`)."""
        selection = self.selection
        ctx = resolve_c_context(selection)
        before = self._selection_snapshot()

        if ctx is CContext.SPLIT:
            (edge_id,) = selection.edges
            new_vid, _, _ = split_selected_edge(self.scene, edge_id)
            selection.mode = SelectionMode.VERTEX
            selection.clear()
            selection.add({new_vid})
            self._record_selection_history(before)
            self._notify_topology_changed()
            self._set_status("Split")
            return True

        if ctx is CContext.EDGE_CONNECT:
            try:
                new_edges = connect_selected_edges_per_face(self.scene, set(selection.edges))
            except TopologyToolError as exc:
                self._set_status(str(exc))
                return False
            selection.clear()
            selection.add(set(new_edges))
            self._record_selection_history(before)
            self._notify_topology_changed()
            self._set_status("Connect Edges")
            return True

        if ctx is CContext.VERTEX_CONNECT:
            try:
                new_edges = connect_vertices_per_face(self.scene, set(selection.vertices))
            except VertexConnectError as exc:
                self._set_status(str(exc))
                return False
            if not new_edges:
                self._set_status("Vertex Connect: nothing connectable")
                return False
            # Residue (AD-017): the original vertices stay selected, Vertex
            # mode unchanged — connect_vertices_per_face never touches
            # `selection` itself.
            self._record_selection_history(before)
            self._notify_topology_changed()
            self._set_status("Vertex Connect")
            return True

        if ctx is CContext.KNIFE:
            return self._knife_begin()

        # CContext.NONE: 1 vertex, Face mode, or another combination with no
        # C meaning (AD-017 §7).
        self._set_status("C: nothing to do here")
        return False

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
        self._refresh_hover()

    # -- Knife session (WP-06 B7 / B7.1, AD-017) ---------------------------------
    #
    # Click-only interaction (Artist decision Manu 2026-09-28, after the B7
    # window test: press -> slide -> release was redundant with the live hover
    # preview, which already slides along the edge while hovering) = Playground
    # Variant A only: hover preview, a click cuts at the previewed position,
    # start highlight, and a line preview from the start to the prospective
    # point. Session engine, in-session history, commit/cancel and residue are
    # `KnifeTool`'s (AD-017 DECIDED); this section only routes input and builds
    # render data. Blender-style drag cutting (Variant B / F1 edge lock) is a
    # possible Knife V2 idea — not built, not prepared; the Playground's own
    # Variant B (`project_locked_edge` in `mirai.topology.knife_pick`) is
    # unaffected (AD-013 A2, contextual deviation).
    #
    # WP-KNIFE-01 S2 (KEEP 2026-10-01): a click adds a point to the session's
    # virtual path; the mesh is cut at commit (`Enter`). The
    # session is drawn from the path (`knife_render_data`), so neither the
    # mesh nor the pick cache changes while clicking.
    #
    # WP-KNIFE-01 S3 (PROVISIONAL): a click inside a face is a point too
    # (`knife_pick` face hit, the session's own interior points snap); the
    # status line names the S3 refusals and closes, and at commit what the
    # resolver joined or dropped (`_knife_notes`).
    #
    # WP-KNIFE-01 UX2 (PROVISIONAL, Artist 2026-10-02): `E` / an RMB click
    # lift the pen (the chain ends, nothing is committed), a double-click
    # closes the chain and lifts; a click outside the mesh does nothing (S4:
    # it is a point in space now, below); Shift+click on an edge places the
    # point at its midpoint.
    #
    # WP-KNIFE-01 UX2b (PROVISIONAL, Artist 2026-10-02): while Shift is held
    # (`set_shift_held`, from the window) the hover already shows that midpoint.
    #
    # WP-KNIFE-01 S4 (PROVISIONAL): the live camera, viewport size, pick cache and
    # occlusion switch go to the `KnifeTool` at hover and click time, so a far
    # click is planned across faces with the camera of that click (crossing dots
    # while hovering). A click outside the mesh is a point in space and cuts
    # (Manu 2026-10-02, Blender); the hover line runs to the cursor over empty
    # space, after the click only the cuts commit will make are drawn.

    @property
    def knife_active(self) -> bool:
        """A Knife session is running (`C` with an empty selection)."""
        return self._knife is not None

    @property
    def knife_render_data(self) -> KnifeRenderData | None:
        """What the running session shows (headless), None without a session."""
        if self._knife is None:
            return None
        data = build_knife_render_data(
            self.scene.mesh,
            [_KNIFE_DRAWN_LIFT if p.get("reason") == "lift" else p for p in self._knife.path],
            self._knife_target,
            self._knife_highlight_edge,
            self._knife_hover_crossings,
        )
        if self._knife.last_point is None:
            # After a pen lift no point starts the next segment: no start marker, no rubber band.
            data = dataclasses.replace(data, start_point=None, line_preview=None)
        return data

    def _knife_begin(self) -> bool:
        if self.viewport is None:
            return False
        self._knife_selection_before = self._selection_snapshot()
        knife = KnifeTool()
        knife.activate()
        knife.begin(mesh=self.scene.mesh, scene=self.scene, selection=self.selection)
        self._knife = knife
        # R-SEL-2 (as in the Playground): the Knife draws its own preview, the
        # selection hover must not stay drawn underneath it.
        self._set_hovered(None)
        self._refresh_hover()
        self._set_status(
            "Knife: click on vertices, edges, inside faces or outside the mesh to cut - a far click cuts"
            " across faces, Shift+click = edge midpoint, E / right-click = new cut (pen lift),"
            " double-click = close + lift, Enter = commit, Esc = cancel, Ctrl+Z / Ctrl+Y = undo / redo"
        )
        return True

    def _knife_key(self, input: Input) -> bool:
        """Session Gate: only commit, cancel, the pen lift and the in-session
        Undo/Redo pass; every other key (W/R, 1/2/3, D/Shift+D, C, X/Y/Z, ...)
        is ignored."""
        command = self.bindings.command_for(input, KNIFE_CONTEXT)
        self._knife_last_click = None     # a key between two clicks is no double-click
        if command == commands.CANCEL:
            return self._knife_end(commit=False)
        if command == commands.KNIFE_COMMIT:
            return self._knife_end(commit=True)
        if command == commands.KNIFE_LIFT:
            return False if self._knife_gesture else self._knife_lift()
        if command in (commands.UNDO, commands.REDO):
            return self._knife_history_step(command)
        return False

    def _knife_owns_press(self, input: Input) -> bool:
        # The unmodified and the Shift-only LMB (midpoint snap, UX2 D11) are the
        # Knife's, and a button bound to KnifeLift (RMB); Alt+LMB (orbit / pan),
        # Ctrl+LMB and the other buttons keep going through the pointer gestures.
        if input.kind != "mouse" or self.pointer.active or self._knife_gesture:
            return False
        if input.value == "LEFT" and input.modifiers <= {"shift"}:
            return True
        return self.bindings.command_for(input, KNIFE_CONTEXT) == commands.KNIFE_LIFT

    def _knife_press(self, input: Input) -> None:
        """Press: only starts the click-threshold gesture (B7.1); the preview
        is recomputed with the press's own Shift (the click decides by the
        press modifiers, AD-019) - with a held Shift the hover showed the same
        midpoint already (UX2b)."""
        self._knife_gesture = True
        self._knife_gesture_moved = 0.0
        self._knife_gesture_button = input.value
        self._knife_gesture_midpoint = input.value == "LEFT" and "shift" in input.modifiers
        if self._cursor is None or input.value != "LEFT":
            return
        self._knife_set_preview(self._knife_pick(*self._cursor, midpoint=self._knife_gesture_midpoint))

    def _knife_drag(self, dx: float, dy: float) -> bool:
        """LMB held and moved: only tracks distance for the click threshold
        (B7.1, no slide) - a drag past the threshold neither locks nor cuts."""
        self._knife_gesture_moved += abs(dx) + abs(dy)
        return False

    def _knife_release(self, x: float, y: float) -> bool:
        """Release: press+release under the click threshold is a click - LMB
        adds the point at the cursor, the second LMB click of a double-click
        finishes the chain, an RMB click lifts the pen; a press that moved past
        the threshold is not a click and does nothing (Playground click rule,
        B7.1). A click outside the mesh adds a point in space (S4); it never
        commits."""
        moved = self._knife_gesture_moved
        self._knife_gesture = False
        self._knife_gesture_moved = 0.0
        last, self._knife_last_click = self._knife_last_click, None
        if moved >= CLICK_THRESHOLD_PX:
            self._refresh_hover()
            return False
        if self._knife_gesture_button != "LEFT":
            return self._knife_lift()
        now = self.knife_clock()
        if (
            last is not None
            and now - last[0] <= KNIFE_DOUBLE_CLICK_S
            and math.hypot(x - last[1], y - last[2]) <= KNIFE_DOUBLE_CLICK_PX
            and self._knife.plan_lift(close=True).ok
        ):
            return self._knife_lift(finish=True)
        target = self._knife_pick(x, y, midpoint=self._knife_gesture_midpoint)
        self._knife_last_click = (now, x, y)
        if not self._knife.click(target):
            self._set_status(_KNIFE_REFUSED.get(self._knife.last_plan.reason, "Knife: no valid cut target here"))
            self._refresh_hover()
            return False
        # WP-KNIFE-01 S2: a click only adds a point to the session's path - the
        # mesh (and with it the pick cache) is unchanged until commit.
        plan = self._knife.last_plan
        cuts = len(self._knife.cut_segments)
        segments = f"{cuts} path {'segment' if cuts == 1 else 'segments'}"
        crossings = f"{len(plan.crossings)} crossing(s)" if plan.crossings else "the line crosses nothing"
        if plan.start:
            where = " on an earlier point" if plan.earlier else " in space" if target["kind"] == "space" else ""
            status = "Knife: start point set" + where
        elif plan.closing:
            status = f"Knife: shape closed - the next click cuts on from its start ({segments})"
        elif plan.skip:
            status = f"Knife: along an existing edge - nothing to cut ({segments})"
        elif target["kind"] == "space":
            status = f"Knife: point in space - {crossings} ({segments})"
        elif plan.method:
            status = f"Knife: cut across {crossings} ({segments})"
        else:
            status = f"Knife: cut ({segments})"
        self._set_status("; ".join([status] + _knife_plan_notes(plan)))
        self._refresh_hover()
        return True

    def _knife_lift(self, finish: bool = False) -> bool:
        """Pen lift (`E` / RMB click), or close + lift (`finish`, the double-click): the
        chain ends, nothing is committed, the next click starts a new chain (UX2)."""
        knife = self._knife
        self._knife_set_view()   # the close may run across faces (S4)
        if not (knife.finish_chain() if finish else knife.lift()):
            self._set_status("Knife: nothing to lift")
            return False
        plan = knife.last_plan
        what = "shape closed, pen lifted" if plan.closing or plan.replaces else plan.reason
        self._set_status(f"Knife: {what} - the next click starts a new cut")
        self._refresh_hover()
        return True

    def _knife_history_step(self, command: str) -> bool:
        """In-session Undo/Redo (AD-017 DECIDED): only the session's own steps,
        never the global history. Ignored while the Knife's LMB is held."""
        if self._knife_gesture:
            return False
        undo = command == commands.UNDO
        done = self._knife.undo_step() if undo else self._knife.redo_step()
        if not done:
            self._set_status(f"Knife: nothing to {'undo' if undo else 'redo'}")
            return False
        self._set_status("Knife: last cut undone" if undo else "Knife: cut redone")
        self._refresh_hover()
        return True

    def _knife_end(self, commit: bool) -> bool:
        """Enter = commit (exactly one history entry, residue = path edges
        selected, Edge mode); Esc = cancel (mesh, selection and history exactly
        as before the session)."""
        knife = self._knife
        before = self._knife_selection_before
        if commit:
            command = knife.commit()
        else:
            knife.cancel()
            command = None
        knife.deactivate()
        self._knife = None
        self._knife_selection_before = None
        self._knife_gesture = False
        self._knife_gesture_moved = 0.0
        self._knife_last_click = None
        self._knife_target = None
        self._knife_highlight_edge = None
        self._knife_hover_crossings = ()
        notes = _knife_notes(knife.last_resolution) if commit else []
        if command is not None:
            self._record_selection_history(before)
            count = len(self.selection.edges)
            status = f"Knife committed ({count} path {'edge' if count == 1 else 'edges'} selected)"
            res = knife.last_resolution
            if res is not None and res.applied < res.runs:
                # Valid while clicking, dropped at commit (the run would have
                # left its face) - the Q5 "N-1/N" note (WP-KNIFE-01 S2).
                status += f" - {res.runs - res.applied} of {res.runs} cuts dropped"
            self._set_status("; ".join([status] + notes))
        elif commit and knife.last_problem is not None:
            self._set_status(f"Knife: result taken back ({knife.last_problem}), nothing committed")
        elif commit:
            self._set_status("Knife: no cuts made, nothing committed" + (f" ({'; '.join(notes)})" if notes else ""))
        else:
            self._set_status("Knife cancelled")
        self._pick_cache.invalidate()
        self.viewport.set_tool_overlay()
        self.viewport.on_topology_changed()
        self.viewport.on_selection_changed()
        self._refresh_hover()
        return True

    def set_shift_held(self, held: bool) -> bool:
        """The window reports whether any Shift key is held (WP-KNIFE-01 UX2b).
        During a Knife session the hover preview at the known cursor follows it
        at once (the midpoint before the click); without a session, a cursor or
        while a button is held it is only stored. True = the preview changed."""
        held = bool(held)
        if held == self._shift_held:
            return False
        self._shift_held = held
        if self._knife is None or self._knife_gesture or self._cursor is None or self.pointer.active:
            return False
        return self._knife_hover(*self._cursor)

    def _knife_hover(self, x: float, y: float) -> bool:
        return self._knife_set_preview(self._knife_pick(x, y, midpoint=self._shift_held))

    def _knife_pick(self, x: float, y: float, midpoint: bool = False) -> dict:
        """WP-06 B8: same cache/occlusion as `_pick()` - a hidden edge/vertex
        cannot be a Knife target while faces are shown. WP-KNIFE-01 S2: then
        the session's own edge points (`snap_own_point`) - a click on one
        reaches that point again, as the real-cut Knife's split vertex did.
        UX2 `midpoint` (Shift): an edge target moves to t = 0.5 - after the
        own-point snap, which wins - or to an own point already there.
        S4: the knife gets the live view first (the planner plans with the camera
        of this hover / click); outside the mesh the target is a point in space."""
        kwargs = {"cache": self._pick_cache, "occlusion": self.display.show_faces}
        size = (self.viewport_width, self.viewport_height)
        target = knife_pick(self.camera, self.scene.mesh, x, y, *size, **kwargs)
        if self._knife is None:
            return target
        self._knife_set_view()
        # Also over "outside": the real-cut Knife's split vertex was caught by the
        # 14 px vertex pick just off the silhouette too.
        target = snap_own_point(
            self.camera, self.scene.mesh, x, y, *size, self._knife.snap_points, target, **kwargs
        )
        if target.get("kind") == "outside":
            return {"kind": "space", "position": space_point(self.camera, x, y, *size)}
        if not midpoint or target.get("kind") != "edge":
            return target
        eid = target["edge_id"]
        own = next((p for p in self._knife.snap_points if p["kind"] == "edge" and p["edge_id"] == eid
                    and abs(p["t"] - 0.5) <= GEO_EPS), None)
        return {"kind": "point", "pid": own["pid"]} if own is not None else dict(target, t=0.5)

    def _knife_set_view(self) -> None:
        """The live camera for the planner (S4) - set before every hover / click plan."""
        self._knife.set_view(self.camera, self.viewport_width, self.viewport_height,
                             cache=self._pick_cache, occlusion=self.display.show_faces)

    def _knife_set_preview(self, target: dict) -> bool:
        """Prospective target = `target` only if the click would be accepted
        (`KnifeTool.plan`, the same rules as `accepts`); invalid → no point, no
        line (`PROVISIONAL`); S4: with the segment's planned crossings.
        True = changed."""
        plan = self._knife.plan(target)
        prospective = target if plan.ok else None
        highlight = target["edge_id"] if plan.ok and target.get("kind") == "edge" else None
        crossings = tuple(tuple(c) for c in plan.crossings) if plan.ok else ()
        changed = (prospective, highlight, crossings) != (
            self._knife_target, self._knife_highlight_edge, self._knife_hover_crossings)
        self._knife_target = prospective
        self._knife_highlight_edge = highlight
        self._knife_hover_crossings = crossings
        self._knife_sync_overlay()
        return changed

    def _knife_clear_preview(self) -> bool:
        changed = self._knife_target is not None or self._knife_highlight_edge is not None
        self._knife_target = None
        self._knife_highlight_edge = None
        self._knife_hover_crossings = ()
        self._knife_sync_overlay()
        return changed

    def _knife_sync_overlay(self) -> None:
        """Knife render data → viewport tool layers: prospective point, target
        edge and line preview in the hover style, the placed points (the start
        among them) and the segments commit will cut in the selected style (no
        new look; WP-KNIFE-01 S2: drawn from the path, the mesh is not cut
        before commit)."""
        data = self.knife_render_data
        if self.viewport is None or data is None:
            return
        self.viewport.set_tool_overlay(
            points={
                TOOL_PREVIEW_LAYER: [p for p in (data.prospective_point,) if p is not None]
                + list(data.prospective_crossings),
                TOOL_ACTIVE_LAYER: list(data.placed_points),
            },
            segments={
                TOOL_PREVIEW_LAYER: [
                    s for s in (data.target_edge, data.line_preview) if s is not None
                ],
                TOOL_ACTIVE_LAYER: list(data.path_segments),
            },
        )

    # -- Display (WP-06 B5a) ----------------------------------------------------

    def _display_command(self, command: str) -> bool:
        if command == commands.CYCLE_DISPLAY_MODE:
            self.display.cycle()
        elif command == commands.TOGGLE_WIREFRAME_OVERLAY:
            self.display.toggle_wireframe_overlay()
        else:
            self.display.set_mode(_SET_DISPLAY_MODES[command])
        self._apply_display()
        self._set_status(f"Display: {self.display.label}")
        return True

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

    # -- Tasten (WP-06 B3) ------------------------------------------------------

    @property
    def move_armed(self) -> bool:
        """Move-Taste gehalten (scharf oder bereits laufend)."""
        return self._transform_command == commands.MOVE

    @property
    def move_interacting(self) -> bool:
        """Move läuft (erste Mausbewegung nach dem Scharfschalten erfolgt)."""
        return self.move_armed and self._transform_begun

    @property
    def move_target(self) -> frozenset[VertexId]:
        """Beim Scharfschalten fixierte Ziel-Vertices (leer = nicht scharf)."""
        return self._transform_target if self.move_armed else frozenset()

    @property
    def transform_command(self) -> str | None:
        """Scharf geschalteter Transform (MOVE/ROTATE/SCALE, None = keiner)."""
        return self._transform_command

    @property
    def transform_interacting(self) -> bool:
        """Der scharfe Transform läuft (erste Mausbewegung erfolgt)."""
        return self._transform_begun

    @property
    def transform_target(self) -> frozenset[VertexId]:
        """Beim Scharfschalten fixierte Ziel-Vertices (leer = nicht scharf)."""
        return self._transform_target

    @property
    def transform_space(self) -> str | None:
        """`space` der laufenden Geste, fix ab `begin()` (None = frei bzw.
        keine Geste)."""
        return self._transform_space

    @property
    def axis_constraint(self) -> str | None:
        """Sticky Achsen-/Ebenen-Constraint als `space`-String (None = frei)."""
        return self._axis_constraint

    def key_press(self, input: Input) -> bool:
        """Taste gedrückt (`input.kind == "key"`), aufgelöst über die Bindings
        (GLOBAL; während einer Knife-Session zuerst KNIFE_CONTEXT). True = der
        Druck hat etwas bewirkt."""
        if self._knife is not None:
            return self._knife_key(input)
        command = self.bindings.command_for(input)
        if command in _TRANSFORM_COMMANDS:
            return self._transform_arm(command, input.value)
        if command in _CONSTRAINT_SPACES:
            return self._constrain(_CONSTRAINT_SPACES[command])
        if command == commands.CANCEL:
            return self._cancel()
        if command in _DISPLAY_COMMANDS:
            # Reine Darstellung: auch während eines Transforms erlaubt.
            return self.dispatch_command(command)
        if command in _MODE_COMMANDS:
            # Kein Moduswechsel mitten in einer Geste (Playground Session Gate).
            if self._transform_key is not None:
                return False
            return self.dispatch_command(command)
        if command == commands.CONNECT:
            # Wie die Modus-Tasten (B5b): C wird ignoriert, solange W/E/R
            # scharf ist (Playground Session Gate).
            if self._transform_key is not None:
                return False
            return self.dispatch_command(command)
        if command in (commands.UNDO, commands.REDO):
            # E23: während eines laufenden Transforms ignoriert; nur scharf →
            # erst entschärfen, dann ausführen.
            if self._transform_begun:
                return False
            if self._transform_key is not None:
                self._transform_end()
                self._refresh_hover()
            return self._undo_redo(command)
        return False

    def key_release(self, input: Input) -> bool:
        """Taste losgelassen. True = das Loslassen hat etwas bewirkt.

        Loslassen der Transform-Taste committet, wenn seit dem Scharfschalten
        eine Mausbewegung kam; ein bloßes Antippen entschärft nur (E21)."""
        if self._transform_key is None or input.value != self._transform_key:
            return False
        label, _, participle = _TRANSFORM_COMMANDS[self._transform_command]
        if self._transform_begun:
            before = self._selection_snapshot()
            command = self.tool_manager.commit()
            if command is not None:
                # Move/Rotate/Scale never change the Selection itself, only
                # vertex positions — before and after are the same snapshot.
                self._record_selection_history(before)
            outcome = f"{label} committed" if command is not None else f"{label}: no change"
            self._set_status(outcome + self._constraint_suffix(self._transform_space))
        else:
            self._set_status(f"{label}: tool set (no motion, nothing {participle})")
        self._transform_end()
        self._refresh_hover()
        return True

    def _transform_arm(self, command: str, key: str) -> bool:
        """Transform scharf schalten (E21/E28): Ziel = aufgelöste Selection,
        sonst die Vertices des gehoverten Elements (Vertex/Edge/Face, B5b),
        sonst ablehnen. Tool aktiv, `begin()` erst bei Bewegung. Ist schon
        eine Transform-Taste gehalten, wird abgelehnt."""
        if self._transform_key is not None or self.viewport is None:
            return False
        label, verb, _ = _TRANSFORM_COMMANDS[command]
        selection = self.selection
        target = resolve_selection_vertices(self.scene.mesh, selection, selection.mode)
        hovered = selection.hovered
        from_hover = not target and hovered is not None
        if from_hover:
            target = _element_vertices(self.scene.mesh, hovered)
        if not target:
            noun = selection.mode.name.lower()
            self._set_status(f"{label}: nothing to {verb} (select or hover a {noun})")
            return False
        self.dispatch_command(command)
        self._transform_key = key
        self._transform_command = command
        self._transform_target = frozenset(target)
        self._transform_begun = False
        # Kein Hover-Highlight über dem, was gleich transformiert wird
        # (Playground WP-STAB-11 clear-on-arm).
        if from_hover or _active_selection_contains(selection, hovered):
            self._set_hovered(None)
        count = len(self._transform_target)
        noun = "vertex" if count == 1 else "vertices"
        self._set_status(
            f"{label}: {count} {noun}{self._constraint_suffix(self._axis_constraint)}"
            f" - move the mouse, release {key.upper()} to commit"
        )
        return True

    @staticmethod
    def _constraint_suffix(space: str | None) -> str:
        return "" if space is None else f" (constraint {_constraint_label(space)})"

    def _constrain(self, space: str) -> bool:
        """Constraint-Taste (B4.1, wie Playground `window.py`): dieselbe Taste
        erneut → frei, eine andere ersetzt. Wirkt auch ohne scharfes Tool;
        während einer laufenden Geste ändert sich nur der Zustand — der
        Tool-`space` ist ab `begin()` fix, der neue Wert gilt ab der nächsten
        Geste."""
        self._axis_constraint = None if self._axis_constraint == space else space
        self._set_status(f"Constraint: {_constraint_label(self._axis_constraint)}")
        return True

    def _transform_step(self, dx: float, dy: float) -> bool:
        """Eine Mausbewegung, während ein Transform scharf ist. Die erste
        Bewegung startet die Interaktion (keine Schwelle, AD-016); ein
        Nullschritt zählt nicht als Bewegung."""
        if dx == 0 and dy == 0:
            return False
        if not self._transform_begun:
            self._transform_space = self._axis_constraint
            self.tool_manager.begin_current_interaction(
                {
                    "scene": self.scene,
                    "camera": self.camera,
                    "vertex_ids": set(self._transform_target),
                    "space": self._transform_space,
                }
            )
            self._transform_begun = True
        self.tool_manager.update(
            dx=float(dx), dy=float(dy), width=self.viewport_width, height=self.viewport_height
        )
        self._pick_cache.invalidate()
        self.viewport.on_vertices_moved(self._active_transform_vertex_ids())
        return True

    def _active_transform_vertex_ids(self) -> set[VertexId]:
        """Vom laufenden Transform betroffene Vertex-IDs (E29): `MoveTool.moves`
        (inkl. Symmetrie-Partner) bzw. `TransformTool.vertex_ids` - bewusst
        nicht vereinheitlicht, MoveTool erbt nicht von TransformTool."""
        tool = self.tool_manager.active_tool
        moves = getattr(tool, "moves", None)
        return moves if moves is not None else tool.vertex_ids

    def _transform_end(self) -> None:
        """Transform-Tool deaktivieren und den Transform-Zustand löschen."""
        self.tool_manager.deactivate()
        self._transform_key = None
        self._transform_command = None
        self._transform_target = frozenset()
        self._transform_begun = False
        self._transform_space = None

    def _cancel(self) -> bool:
        """Esc = nur Abbrechen (B1 A3: kein Quit, E22). Laufender Transform →
        exakter Vorzustand ohne History; nur scharf → entschärfen; idle →
        nichts."""
        if self._transform_key is None:
            return False
        label, _, _ = _TRANSFORM_COMMANDS[self._transform_command]
        if self._transform_begun:
            moved = self._active_transform_vertex_ids()
            self.tool_manager.cancel()
            self._pick_cache.invalidate()
            self.viewport.on_vertices_moved(moved)
            self._set_status(f"{label} cancelled")
        else:
            self._set_status(f"{label} disarmed")
        self._transform_end()
        self._refresh_hover()
        return True

    def _undo_redo(self, command: str) -> bool:
        can = self.history.can_undo() if command == commands.UNDO else self.history.can_redo()
        if not can:
            self._set_status(f"{command}: nothing to {command.lower()}")
            return False
        self.dispatch_command(command)
        # E23: `HistoryStack` bietet keinen öffentlichen Zugriff auf das
        # gerade rückgängig gemachte Command (und `core/history.py` ist
        # tabu) - daher der gröbere, aber für jedes Command korrekte Rebuild
        # statt `on_vertices_moved(ids)`. Selection-Restore und Ghost-Pruning
        # laufen bereits in `dispatch_command` (`_apply_undo_redo`), auch für
        # Aufrufer, die `dispatch_command(UNDO/REDO)` direkt statt über
        # `key_press` erreichen.
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
        Commit — aktuell die einzigen Push-Aufrufer). Der Mirror-Pop läuft in
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
        if command == commands.UNDO and self._selection_undo_stack:
            entry = self._selection_undo_stack.pop()
            self._selection_redo_stack.append(entry)
            restored = entry[0]
        elif command == commands.REDO and self._selection_redo_stack:
            entry = self._selection_redo_stack.pop()
            self._selection_undo_stack.append(entry)
            restored = entry[1]

        if command == commands.UNDO:
            self.history.undo()
        else:
            self.history.redo()

        if restored is not None:
            self._restore_selection(restored)
        self._prune_ghost_selection()

    def _selection_snapshot(self) -> tuple:
        """Momentaufnahme von Modus + Auswahl (kein Hover - der wird nach
        Undo/Redo ohnehin über `_refresh_hover()` neu am Cursor gepickt,
        nicht wiederhergestellt)."""
        selection = self.selection
        return (
            selection.mode,
            frozenset(selection.vertices),
            frozenset(selection.edges),
            frozenset(selection.faces),
        )

    def _restore_selection(self, snapshot: tuple) -> None:
        mode, vertices, edges, faces = snapshot
        selection = self.selection
        selection.mode = mode
        selection.vertices = set(vertices)
        selection.edges = set(edges)
        selection.faces = set(faces)

    def _record_selection_history(self, before: tuple) -> None:
        """Von jedem Aufrufer, der gerade `history.push()` ausgelöst hat (bzw.
        gleich auslösen wird - siehe Aufrufstellen), mit dem VOR der Mutation
        genommenen `_selection_snapshot()` aufzurufen. Spiegelt `HistoryStack.
        push()`: ein neuer Eintrag verwirft den Mirror-Redo-Zweig genau wie
        dort den echten."""
        after = self._selection_snapshot()
        self._selection_undo_stack.append((before, after))
        self._selection_redo_stack.clear()

    def _prune_ghost_selection(self) -> None:
        """Entfernt jedes Handle, das `mesh` nicht mehr kennt ("ghost
        selection") - Sicherheitsnetz nach `_apply_undo_redo()`.

        `MeshStateCommand` stellt das Mesh wieder her; ohne den Selection-
        Restore oben blieben Handles von Elementen, die die Mutation entfernt
        hatte, als tote IDs in `selection` liegen. Der B6-Crash-Fix
        (`_notify_topology_changed`, `_element_vertices`, `resolve_selection_
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
        hovered = selection.hovered
        if isinstance(hovered, VertexId) and not mesh.is_valid_vertex(hovered):
            selection.hovered = None
        elif isinstance(hovered, EdgeId) and not mesh.is_valid_edge(hovered):
            selection.hovered = None
        elif isinstance(hovered, FaceId) and not mesh.is_valid_face(hovered):
            selection.hovered = None

    def _set_status(self, message: str) -> None:
        self.status_message = message
        self.status_serial += 1

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
        if x is not None and y is not None:
            self._cursor = (x, y)
        if self._knife is not None and self._knife_owns_press(input):
            self._knife_press(input)
            return
        self.pointer.press(input)

    def pointer_drag(
        self, dx: float, dy: float, x: float | None = None, y: float | None = None
    ) -> bool:
        """Mausbewegung mit gedrückter Taste. True = ein Command wurde ausgeführt.
        Während einer Knife-Geste (B7.1) zählt nur die Distanz für die
        Klick-Schwelle - `x`/`y` werden nicht für eine Vorschau verwendet."""
        if x is not None and y is not None:
            self._cursor = (x, y)
        if self._knife_gesture:
            return self._knife_drag(dx, dy)
        step = self.pointer.drag(dx, dy)
        return step is not None and self._execute_drag(step)

    def pointer_release(self, button: str, x: float, y: float) -> bool:
        """Maustaste losgelassen. True = ein Klick-Command wurde ausgeführt
        bzw. der Knife hat einen Punkt gesetzt / den Stift abgesetzt."""
        self._cursor = (x, y)
        if self._knife_gesture and button == self._knife_gesture_button:
            return self._knife_release(x, y)
        click = self.pointer.release(button, x, y)
        if self._knife is not None:
            # Session Gate (B7): Navigation ist vorbei bzw. ein modifizierter
            # Klick fiel - der Klick selbst tut während der Session nichts
            # (keine Auswahländerung), die Knife-Vorschau pickt neu.
            self._refresh_hover()
            return False
        return click is not None and self._execute_click(click)

    def pointer_scroll(self, input: Input) -> bool:
        """Wheel-Input (`kind == "wheel"`), aufgelöst über die Bindings."""
        command = self.bindings.command_for(input)
        if command != commands.ZOOM:
            return False
        self.camera.dolly(DOLLY_IN_FACTOR if input.value == "UP" else DOLLY_OUT_FACTOR)
        self._camera_changed()
        # Unter dem ruhenden Cursor liegt nach dem Zoom ggf. ein anderer Vertex.
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
        if self._knife is not None:
            if self._knife_gesture:
                return False
            return self._knife_hover(x, y)
        if self._transform_key is not None:
            return self._transform_step(dx, dy)
        return self._update_hover(x, y)

    def _refresh_hover(self) -> None:
        """Hover an der letzten Cursor-Position neu picken (nach Zoom bzw.
        wenn sich das Mesh unter dem ruhenden Cursor bewegt hat). Während
        einer Knife-Session statt des Selection-Hovers die Knife-Vorschau."""
        if self._knife is not None:
            if self._knife_gesture:
                return
            if self._cursor is not None and not self.pointer.active:
                self._knife_hover(*self._cursor)
            else:
                self._knife_clear_preview()
            return
        if self._cursor is not None and not self.pointer.active and self._transform_key is None:
            self._update_hover(*self._cursor)

    def pointer_leave(self) -> bool:
        """Cursor hat das Fenster verlassen: Hover (bzw. Knife-Vorschau) löschen."""
        self._cursor = None
        if self._knife is not None:
            if self._knife_gesture:
                return False
            return self._knife_clear_preview()
        return self._set_hovered(None)

    def _update_hover(self, x: float, y: float) -> bool:
        # Hover im aktiven Modus: Vertex (B2b), Edge oder Face (B5b).
        if self.viewport is None:
            return False
        return self._set_hovered(self._pick(x, y))

    def _pick(self, x: float, y: float):
        """E43: Element unter dem Cursor im aktiven Selection-Modus (oder None).
        WP-06 B8: cached (`self._pick_cache`) and occlusion-aware - only
        visible vertices/edges are pickable while faces are shown (Shaded/
        Flat Shaded); Wireframe leaves everything pickable, as before B8."""
        return pick_component(
            self.camera,
            self.scene.mesh,
            self.selection.mode,
            x,
            y,
            self.viewport_width,
            self.viewport_height,
            cache=self._pick_cache,
            occlusion=self.display.show_faces,
        )

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
        return True

    def _execute_drag(self, step: DragStep) -> bool:
        if step.command == commands.ORBIT:
            self.camera.orbit(-step.dx * ORBIT_RADIANS_PER_PX, -step.dy * ORBIT_RADIANS_PER_PX)
        elif step.command == commands.PAN:
            self.camera.pan(step.dx, step.dy, self.viewport_width, self.viewport_height)
        else:
            return False
        self._camera_changed()
        # Eine laufende Orbit-/Pan-Geste löscht Hover (während einer Knife-
        # Session die Knife-Vorschau; Start und Pfad bleiben); er kehrt mit
        # der nächsten Mausbewegung nach dem Release zurück.
        if self._knife is not None:
            self._knife_clear_preview()
        else:
            self._set_hovered(None)
        return True

    def _execute_click(self, click: Click) -> bool:
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
        selection = self.selection
        before = _selection_state(selection)
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
        if _selection_state(selection) == before:
            return False
        self.viewport.on_selection_changed()
        return True

    #: B2-Name, bleibt als Weiterleitung (E43).
    select_vertex_at = select_at

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
        """
        if self.viewport is not None:
            self.viewport.sync()

    def shutdown(self) -> None:
        """Sauberes Herunterfahren: aktives Tool deaktivieren (kein stale State);
        eine laufende Knife-Session wird verworfen (wie Esc)."""
        if self._knife is not None:
            self._knife_end(commit=False)
        self.tool_manager.deactivate()