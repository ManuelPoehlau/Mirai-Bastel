"""Component selection of the Mehlsack Lab (Slice 3, E23–E27), headless.

The selection is a Core `Selection` (`src/core/selection.py`, read-only use): its mode is
`SelectionMode.VERTEX/EDGE/FACE`, it never enters the modeling history (Core contract), and
this module adds no second selection model — only the three rules the lab needs on top:

- `apply_click` (E25): the click semantics of the app commands
  (`mirai.interaction.commands`, `Application.select_at`): `SELECT` replaces, a click into
  empty space clears; `SELECT_ADD` / `SELECT_REMOVE` / `SELECT_TOGGLE` change only the hit
  element, a click into empty space changes nothing. Re-stated here because the app keeps the
  rule inside a window-bound method; the command names are imported, not copied.
- `selection_target` (E26): with a non-empty selection every gesture acts on it — its seeds
  are `resolve_selection_vertices(mesh, selection, selection.mode)` (the app's resolver), the
  Move anchor is `min(seeds)` like the app's `MoveTool`. The target has no edges: the hover
  Loop/Ring line stays the hover's (E29).
- `add_loop_ring` (E27): Shift+L / Shift+R add the Loop / Ring of the hovered edge — the same
  `TargetFinder` targets as the hover (incl. the E15 rim loop). Edge mode adds the edges,
  Vertex mode their vertices; Face mode is refused: neither `src/` nor `playground/` has a
  face-loop definition (open question, README Slice 3).
"""

from __future__ import annotations

from typing import Optional

from core import Mesh, Selection, SelectionMode
from mirai.interaction.commands import SELECT, SELECT_ADD, SELECT_REMOVE, SELECT_TOGGLE
from mirai.interaction.tools.selection_helpers import resolve_selection_vertices

from .targets import MODE_LOOP, MODE_RING, Target, TargetFinder

CLICK_COMMANDS = (SELECT, SELECT_ADD, SELECT_REMOVE, SELECT_TOGGLE)
#: `Target.mode` of a selection target (not a hover mode: never in `targets.MODES`).
MODE_SELECTION = "selection"
MODE_NAMES = {SelectionMode.VERTEX: "Punkte", SelectionMode.EDGE: "Kanten", SelectionMode.FACE: "Flächen"}


def selection_state(selection: Selection) -> tuple:
    """Comparable snapshot of the selected handles (mode included, hover excluded)."""
    return (selection.mode, frozenset(selection.vertices), frozenset(selection.edges),
            frozenset(selection.faces))


def apply_click(selection: Selection, command: str, hit) -> bool:
    """E25, see module docstring. `hit` is a handle of the active mode or None. Returns True
    if the selection changed."""
    if command not in CLICK_COMMANDS:
        raise ValueError(f"not a click command: {command!r}")
    before = selection_state(selection)
    if hit is None:
        if command == SELECT:
            selection.clear()
    elif command == SELECT:
        selection.set({hit})
    elif command == SELECT_ADD:
        selection.add({hit})
    elif command == SELECT_REMOVE:
        selection.remove({hit})
    else:
        selection.toggle(hit)
    return selection_state(selection) != before


def selection_seeds(mesh: Mesh, selection: Selection) -> frozenset:
    return frozenset(resolve_selection_vertices(mesh, selection, selection.mode))


def selection_target(mesh: Mesh, selection: Selection) -> Optional[Target]:
    """E26: the gesture target of a non-empty selection, None if it resolves to no vertex."""
    seeds = selection_seeds(mesh, selection)
    if not seeds:
        return None
    return Target(MODE_SELECTION, None, (), False, seeds, min(seeds))


def add_loop_ring(selection: Selection, finder: TargetFinder, edge, kind: str) -> tuple[bool, str]:
    """E27: adds the Loop (`kind = MODE_LOOP`) or Ring (`MODE_RING`) of `edge` in the active
    mode. Returns (changed, status note)."""
    if kind not in (MODE_LOOP, MODE_RING):
        raise ValueError(f"unknown kind {kind!r}")
    name = "Loop" if kind == MODE_LOOP else "Ring"
    if selection.mode is SelectionMode.FACE:
        return False, (f"{name} auswählen geht im Flächenmodus nicht (keine Flächen-{name}-Regel in "
                       "src/playground — offene Frage)")
    if edge is None:
        return False, f"{name} auswählen: keine Kante gehovert"
    target = finder.target(edge, kind)
    before = selection_state(selection)
    if selection.mode is SelectionMode.EDGE:
        selection.add(set(target.edges))
        added = f"{len(target.edges)} Kanten"
    else:
        selection.add(set(target.seeds))
        added = f"{len(target.seeds)} Punkte"
    changed = selection_state(selection) != before
    closed = ", geschlossen" if target.closed else ""
    return changed, f"{name} dazu: {added}{closed}" if changed else f"{name} ist schon ausgewählt"
