"""ToolManager: Registry + Lifecycle-Verwaltung aktiver Tools.

Der ToolManager hält höchstens EIN aktives Tool. Tools werden über
Commando-Strings registriert (`register(command, tool_class)`) und über
`activate(command, context=None)` aktiviert — der Command→Tool-Import
geschieht über `mirai.interaction.routing.tool_for_command`, nicht hier
(kein zirkulärer Import Tool ↔ ToolManager ↔ Application).

Aktivierungs-Muster (WP-04 Amendment „Flexible Interaction Architecture"):

- Pattern A: `activate(command)` aktiviert das Tool (Zustand ACTIVE,
  wartet). Eine spätere Interaktion startet explizit über
  `begin_current_interaction(context=...)` (z. B. LMB beim ersten Klick).
- Pattern B: `activate(command, context={...})` aktiviert UND startet die
  Interaktion in einem Schritt (`begin(**context)`, z. B. Alt+M direkt auf
  einer Selection).

Der ToolManager erzwingt den Tool-Lifecycle-Vertrag (tool.py): Eine noch
laufende Interaktion (INTERACTING) wird vor dem Wechsel zu einem anderen
Tool sauber gecancelt (z. B. cancel() → exakter Vorzustand, keine History).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type

from .tool import Tool, ToolStateError


class ToolManager:
    """Registry + Lifecycle für genau ein aktives Tool."""

    def __init__(self) -> None:
        self._registry: Dict[str, Type[Tool]] = {}
        self._active: Optional[Tool] = None

    # -- Zustand (öffentlich, lesend) ------------------------------------

    @property
    def registry(self) -> Dict[str, Type[Tool]]:
        """Lese-Zugriff auf die Command→Tool-Registry (Kopie)."""
        return dict(self._registry)

    @property
    def active_tool(self) -> Optional[Tool]:
        return self._active

    @property
    def is_interacting(self) -> bool:
        return self._active is not None and self._active.is_interacting

    # -- Registry -----------------------------------------------------------

    def register(self, command: str, tool_class: Type[Tool]) -> None:
        """Registriert `tool_class` für `command` (Command→Tool-Mapping)."""
        self._registry[command] = tool_class

    # -- Aktivierung ---------------------------------------------------------

    def activate(self, command: str, context: Optional[dict] = None) -> bool:
        """Aktiviert das für `command` registrierte Tool.

        Pattern A: ohne `context` wird das Tool nur aktiviert (wartet).
        Pattern B: mit `context` wird die Interaktion sofort gestartet
        (`begin(**context)`).

        Gibt True zurück, wenn `command` registriert war und das Tool
        aktiviert wurde; sonst False.
        """
        tool_class = self._registry.get(command)
        if tool_class is None:
            return False

        self._end_active()
        tool = tool_class()
        tool.activate()
        self._active = tool

        if context is not None:
            tool.begin(**dict(context))

        return True

    # -- Lifecycle-Weiterleitung (Pattern-A-Fortsetzung) -------------------

    def begin_current_interaction(self, context: Optional[dict] = None) -> None:
        """Startet die Interaktion auf dem aktiven Tool (Pattern A).

        `context` wird als Keyword-Parameter an `begin(**context)`
        durchgereicht (z. B. scene/camera/vertex_ids).
        """
        tool = self._require_active()
        if context is not None:
            tool.begin(**dict(context))
        else:
            tool.begin()

    def update(self, **kwargs: Any) -> None:
        """Dragging-/Pointer-Update während INTERACTING weiterleiten."""
        self._require_active().update(**kwargs)

    def commit(self) -> Any:
        """Committet die laufende Interaktion (History-Grenze im Core)."""
        return self._require_active().commit()

    def cancel(self) -> None:
        """Bricht die laufende Interaktion ab (kein History-Eintrag)."""
        self._require_active().cancel()

    def deactivate(self) -> None:
        """Deaktiviert das aktive Tool (clean, kein stale State)."""
        self._end_active()

    # -- Intern ---------------------------------------------------------------

    def _require_active(self) -> Tool:
        if self._active is None:
            raise ToolStateError("Kein aktives Tool.")
        return self._active

    def _end_active(self) -> None:
        if self._active is None:
            return
        # Tool-Lifecycle-Vertrag: INTERACTING muss erst beendet werden
        # (cancel → exakter Vorzustand, keine History), sonst wirft
        # deactivate() einen ToolStateError (stale Drag-/Tool-State).
        if self._active.is_interacting:
            self._active.cancel()
        self._active.deactivate()
        self._active = None