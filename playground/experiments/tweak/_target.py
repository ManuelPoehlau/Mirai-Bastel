"""Shared Selection-Fallback rule for all Tweak variants (headless-testable).

Rule (identical across all four variants):
  - Selection non-empty → Tweak transforms the whole selection, no hit-test.
  - Selection empty → hit-test at gesture start; the hit element becomes a
    temporary target, transforms during the drag, deselected on commit/cancel.

Also provides toggle_persistent_mode() for V1/V2/V4 mode persistence.
"""

from __future__ import annotations

from playground._paths import ensure_paths

ensure_paths()

from core.selection import SelectionMode  # noqa: E402


def has_selection(selection) -> bool:
    """True if the current selection (in the active mode) is non-empty."""
    if selection.mode is SelectionMode.FACE:
        return bool(selection.faces)
    elif selection.mode is SelectionMode.VERTEX:
        return bool(selection.vertices)
    else:
        return bool(selection.edges)


def add_temp_target(selection, hit) -> None:
    """Add a single hit element as a temporary selection target."""
    if selection.mode is SelectionMode.FACE:
        selection.faces.add(hit)
    elif selection.mode is SelectionMode.VERTEX:
        selection.vertices.add(hit)
    else:
        selection.edges.add(hit)


def clear_temp_target(selection) -> None:
    """Clear the temporary target (assumes selection was empty before Tweak)."""
    if selection.mode is SelectionMode.FACE:
        selection.faces.clear()
    elif selection.mode is SelectionMode.VERTEX:
        selection.vertices.clear()
    else:
        selection.edges.clear()


def toggle_persistent_mode(current: str | None, key_tool_type: str) -> str | None:
    """Toggle persistent transform mode (for V1 mode-toggle and V2/V4 prerequisite).

    Same key as current mode → turns mode off (returns None).
    Different key → switches to new mode.
    """
    if current == key_tool_type:
        return None
    return key_tool_type
