"""Command → Tool-Routing (neutraler Dispatcher).

Vermittelt zwischen Commando-Strings und Tool-Klassen, ohne dass die Tools
oder der Application-Code voneinander abhängen (kein zirkulärer Import).

Nur modale/interaktive Commands brauchen ein Tool. Nicht-interaktive
Commands (Undo, Display-Änderung, ...) bleiben direkte Aktionen in der
Application und liefern hier `None`.

Eine geänderte Input-Bindung (z. B. G statt M → Move) ändert ausschließlich
die Mapping-Schicht (`input.py`/`bindings.py`) — diese Funktion und die
Tools bleiben unverändert.
"""

from __future__ import annotations

from typing import Optional, Type

from . import commands as cmd
from .tool import Tool
from .tools.move import MoveTool
from .tools.rotate import RotateTool
from .tools.scale import ScaleTool

_TOOL_MAPPING: dict[str, Type[Tool]] = {
    cmd.MOVE: MoveTool,
    cmd.ROTATE: RotateTool,
    cmd.SCALE: ScaleTool,
}


def tool_for_command(command: str) -> Optional[Type[Tool]]:
    """Gibt die Tool-Klasse für ein modales Command zurück (oder None)."""
    return _TOOL_MAPPING.get(command)