"""Contextual C dispatch — resolve selection context to C operation (AD-017 §1.6)."""

from __future__ import annotations

from enum import Enum, auto

from core.selection import Selection, SelectionMode


class CContext(Enum):
    SPLIT = auto()
    EDGE_CONNECT = auto()
    VERTEX_CONNECT = auto()
    KNIFE = auto()
    NONE = auto()


def resolve_c_context(selection: Selection) -> CContext:
    """Map the current selection to the C operation context.

    Rules (AD-017):
      empty selection (any mode)       → KNIFE
      Edge mode, 1 edge                → SPLIT
      Edge mode, 2+ edges              → EDGE_CONNECT
      Vertex mode, 2+ vertices         → VERTEX_CONNECT
      everything else (1 vertex, etc.) → NONE
    """
    if selection.is_empty():
        return CContext.KNIFE
    if selection.mode is SelectionMode.EDGE:
        n = len(selection.edges)
        if n == 1:
            return CContext.SPLIT
        if n >= 2:
            return CContext.EDGE_CONNECT
    if selection.mode is SelectionMode.VERTEX:
        if len(selection.vertices) >= 2:
            return CContext.VERTEX_CONNECT
    return CContext.NONE
