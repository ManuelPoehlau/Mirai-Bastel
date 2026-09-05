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
"""

from __future__ import annotations

from typing import Optional

from core import HistoryStack, Scene, Selection

from .interaction import BindingSet, ToolManager, commands
from .interaction.bindings import build_default_bindings
from .interaction.routing import tool_for_command
from .viewport import DisplayState, OrbitCamera


class Application:
    """Window-unabhängiger Produktions-Orchestrator."""

    def __init__(self) -> None:
        # Core-Strukturen
        self.scene: Scene = Scene()
        self.selection: Selection = self.scene.selection
        self.history: HistoryStack = self.scene.history

        # Viewport-State (kein Rendering in Gate 3)
        self.camera: OrbitCamera = OrbitCamera()
        self.display: DisplayState = DisplayState()

        # Tools
        self.tool_manager: ToolManager = ToolManager()
        self._setup_tools()

        # Input
        self.bindings: BindingSet = build_default_bindings()

    def _setup_tools(self) -> None:
        """Registriert die Default-Tools (Move/Rotate/Scale) im ToolManager."""
        for command, tool_class in (
            (commands.MOVE, tool_for_command(commands.MOVE)),
            (commands.ROTATE, tool_for_command(commands.ROTATE)),
            (commands.SCALE, tool_for_command(commands.SCALE)),
        ):
            if tool_class:
                self.tool_manager.register(command, tool_class)

    def init_scene(self, geometry_type: str = "cube") -> None:
        """Initialisiert die Default-Szene (aktuell: Würfel)."""
        if geometry_type == "cube":
            from .scene_factory import create_cube

            self.scene.mesh = create_cube()

    def dispatch_command(
        self, command: str, context: Optional[dict] = None, **params
    ) -> bool:
        """Dispatchet ein Command (True = wurde behandelt).

        Tool-Commands → ToolManager (Pattern A: nur aktivieren; Pattern B:
        mit `context` sofort `begin(**context)`).
        Undo/Redo → History.
        Alles andere → False (wird in Gate 4 um Selection-/Display-Commands
        erweitert; bewusst minimal gehalten).
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

        return False

    def update_viewport(self, delta_t: float) -> None:
        """Viewport-Tick (delta_t in Sekunden).

        Gate 3: bewusst ein No-op. Animations-/Preview-Updates kommen mit
        dem v0.2-Viewport (Gate 5). Existiert als stabiler Integrationspunkt.
        """

    def shutdown(self) -> None:
        """Sauberes Herunterfahren: aktives Tool deaktivieren (kein stale State)."""
        self.tool_manager.deactivate()