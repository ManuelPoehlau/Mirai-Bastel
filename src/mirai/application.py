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

from pathlib import Path
from typing import Optional

from core import HistoryStack, Scene, Selection, SelectionMode, VertexId

from viewport import Viewport  # Gate 7: V0.2 Rendering-Viewport (unabhängig von mirai)
from viewport.resource_store import ResourceStore, TraceStore

from .interaction import BindingSet, Input, ToolManager, commands
from .interaction.bindings import build_default_bindings, load_keymap_overrides
from .interaction.pointer import Click, DragStep, PointerGestures
from .interaction.routing import tool_for_command
from .interaction.tools import resolve_selection_vertices
from .mesh_geometry import mesh_center_and_radius
from .viewport import DisplayMode, DisplayState, OrbitCamera
from .viewport.picking import pick_nearest_vertex


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
        aktuelle `DisplayState` wird sofort an den neuen Viewport gegeben."""
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
        Alles andere → False (bewusst minimal gehalten).
        """
        tool_class = tool_for_command(command)
        if tool_class:
            return self.tool_manager.activate(command, context=context)

        if command == commands.UNDO:
            self.history.undo()
            return True
        if command == commands.REDO:
            self.history.redo()
            return True
        if command in _DISPLAY_COMMANDS:
            return self._display_command(command)

        return False

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
        Viewport kennt kein `DisplayState`)."""
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
        (GLOBAL). True = der Druck hat etwas bewirkt."""
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
            command = self.tool_manager.commit()
            outcome = f"{label} committed" if command is not None else f"{label}: no change"
            self._set_status(outcome + self._constraint_suffix(self._transform_space))
        else:
            self._set_status(f"{label}: tool set (no motion, nothing {participle})")
        self._transform_end()
        self._refresh_hover()
        return True

    def _transform_arm(self, command: str, key: str) -> bool:
        """Transform scharf schalten (E21/E28): Ziel = Selection, sonst der
        gehoverte Vertex, sonst ablehnen. Tool aktiv, `begin()` erst bei
        Bewegung. Ist schon eine Transform-Taste gehalten, wird abgelehnt."""
        if self._transform_key is not None or self.viewport is None:
            return False
        label, verb, _ = _TRANSFORM_COMMANDS[command]
        selection = self.selection
        target = resolve_selection_vertices(self.scene.mesh, selection, selection.mode)
        hovered = selection.hovered
        if not target and isinstance(hovered, VertexId):
            target = {hovered}
        if not target:
            self._set_status(f"{label}: nothing to {verb} (select or hover a vertex)")
            return False
        self.dispatch_command(command)
        self._transform_key = key
        self._transform_command = command
        self._transform_target = frozenset(target)
        self._transform_begun = False
        # Kein Hover-Punkt über den Punkten, die gleich transformiert werden.
        if isinstance(hovered, VertexId) and hovered in self._transform_target:
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
        # statt `on_vertices_moved(ids)`.
        if self.viewport is not None:
            self.viewport.on_topology_changed()
        self._set_status(command)
        self._refresh_hover()
        return True

    def _set_status(self, message: str) -> None:
        self.status_message = message
        self.status_serial += 1

    # -- Pointer / Navigation (WP-06 B2, AD-019) ------------------------------

    def set_viewport_size(self, width: int, height: int) -> None:
        """Setzt die Viewport-Größe (Maus-Koordinaten-Einheit) und meldet den
        neuen Aspect an den Viewport."""
        self.viewport_width = max(int(width), 1)
        self.viewport_height = max(int(height), 1)
        self._camera_changed()

    def pointer_press(self, input: Input) -> None:
        """Maustaste gedrückt (`input.kind == "mouse"`, Modifier beim Press)."""
        self.pointer.press(input)

    def pointer_drag(self, dx: float, dy: float) -> bool:
        """Mausbewegung mit gedrückter Taste. True = ein Command wurde ausgeführt."""
        step = self.pointer.drag(dx, dy)
        return step is not None and self._execute_drag(step)

    def pointer_release(self, button: str, x: float, y: float) -> bool:
        """Maustaste losgelassen. True = ein Klick-Command wurde ausgeführt."""
        self._cursor = (x, y)
        click = self.pointer.release(button, x, y)
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
        Transform, kein Hover (E24). Sonst Vertex-Hover unter dem Cursor
        (B2b). Während einer laufenden Pointer-Geste (Kamera) passiert beides
        nicht — Navigation gewinnt. True = ein Transform-Schritt lief bzw.
        `selection.hovered` hat sich geändert."""
        self._cursor = (x, y)
        if self.pointer.active:
            return False
        if self._transform_key is not None:
            return self._transform_step(dx, dy)
        return self._update_hover(x, y)

    def _refresh_hover(self) -> None:
        """Hover an der letzten Cursor-Position neu picken (nach Zoom bzw.
        wenn sich das Mesh unter dem ruhenden Cursor bewegt hat)."""
        if self._cursor is not None and not self.pointer.active and self._transform_key is None:
            self._update_hover(*self._cursor)

    def pointer_leave(self) -> bool:
        """Cursor hat das Fenster verlassen: Hover löschen."""
        self._cursor = None
        return self._set_hovered(None)

    def _update_hover(self, x: float, y: float) -> bool:
        # Nur Vertex-Mode (B2b); andere Modi haben noch keinen Hover.
        if self.viewport is None or self.selection.mode is not SelectionMode.VERTEX:
            return False
        vid = pick_nearest_vertex(
            self.camera, self.scene.mesh, x, y, self.viewport_width, self.viewport_height
        )
        return self._set_hovered(vid)

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
        # Eine laufende Orbit-/Pan-Geste löscht Hover; er kehrt mit der
        # nächsten Mausbewegung nach dem Release zurück.
        self._set_hovered(None)
        return True

    def _execute_click(self, click: Click) -> bool:
        if click.command in _SELECT_COMMANDS:
            self.select_vertex_at(click.command, click.x, click.y)
            return True
        return False

    def select_vertex_at(self, command: str, x: float, y: float) -> bool:
        """Vertex-Klick-Selektion, Modifier-Variante AP-03 (WP-06 B2, A7/E13).

        Treffer: SELECT ersetzt, SELECT_ADD fügt hinzu, SELECT_REMOVE entfernt,
        SELECT_TOGGLE schaltet um. Klick ins Leere: nur SELECT leert, die
        Modifier-Commands lassen die Auswahl unverändert. Nur Vertex-Mode
        (`Selection.mode` wird nicht angefasst), kein History-Eintrag.
        True = die Auswahl hat sich tatsächlich geändert (nur dann wird der
        Viewport benachrichtigt)."""
        if self.viewport is None:
            return False
        selection = self.selection
        before = _selection_state(selection)
        vid = pick_nearest_vertex(
            self.camera, self.scene.mesh, x, y, self.viewport_width, self.viewport_height
        )
        if vid is None:
            if command == commands.SELECT:
                selection.clear()
        elif command == commands.SELECT:
            selection.set({vid})
        elif command == commands.SELECT_ADD:
            selection.add({vid})
        elif command == commands.SELECT_REMOVE:
            selection.remove({vid})
        elif command == commands.SELECT_TOGGLE:
            selection.toggle(vid)
        if _selection_state(selection) == before:
            return False
        self.viewport.on_selection_changed()
        return True

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
        """Sauberes Herunterfahren: aktives Tool deaktivieren (kein stale State)."""
        self.tool_manager.deactivate()