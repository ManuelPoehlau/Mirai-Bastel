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

Slice 3b (Manu's answers 2026-10-13, O12/O13/O15, s2 ITERATE):

- `component_target`: the hover is the single component under the cursor by default (O13);
  with an empty selection the gestures act on its vertices (the app's hover fallback,
  `_element_vertices`). Loop/Ring hover only in the `L` mode.
- `apply_click_elements`: a click in the `L` mode selects the whole hovered Loop/Ring
  (E25 semantics on a set; Toggle: all selected → remove, else add).
- `loop_segment`: Shift+double click on an edge of the same loop as the previous click adds
  the loop section between them (the shorter way round on a closed loop).
- `face_loop`: Shift+double click on a face next to the previous one adds the face loop in
  that direction — the faces the `loop_ring.edge_ring` of their shared edge passes through
  (the Ring's rules: quads only, stops at a non-quad face), no new traversal rule.
- `convert_selection` (O15, "touching"): Shift+`1`/`2`/`3` turn the selection into the
  vertices / edges / faces that touch it.
"""

from __future__ import annotations

from typing import Optional

from core import Mesh, Selection, SelectionMode
from mirai.interaction.commands import SELECT, SELECT_ADD, SELECT_REMOVE, SELECT_TOGGLE
from mirai.interaction.tools.selection_helpers import resolve_selection_vertices

from core import EdgeId, FaceId, VertexId

from .targets import MODE_LOOP, MODE_RING, Target, TargetFinder

CLICK_COMMANDS = (SELECT, SELECT_ADD, SELECT_REMOVE, SELECT_TOGGLE)
#: `Target.mode` of a selection target (not a hover mode: never in `targets.MODES`).
MODE_SELECTION = "selection"
#: `Target.mode` of the single hovered component (Slice 3b, O13).
MODE_COMPONENT = "component"
HANDLE_TYPES = {SelectionMode.VERTEX: VertexId, SelectionMode.EDGE: EdgeId, SelectionMode.FACE: FaceId}
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


# -- Slice 3b ------------------------------------------------------------------------------------------


def active_set(selection: Selection) -> set:
    return {SelectionMode.VERTEX: selection.vertices, SelectionMode.EDGE: selection.edges,
            SelectionMode.FACE: selection.faces}[selection.mode]


def component_target(mesh: Mesh, mode: SelectionMode, hit) -> Optional[Target]:
    """The hovered component as a gesture target (O13): its vertices are the seeds, the Move
    anchor is `min(seeds)` like the app's `MoveTool`; an edge keeps its id (Shift+L/R) and is
    drawn as the hover line."""
    if hit is None or not isinstance(hit, HANDLE_TYPES[mode]):
        return None
    if mode is SelectionMode.VERTEX:
        if not mesh.is_valid_vertex(hit):
            return None
        return Target(MODE_COMPONENT, None, (), False, frozenset({hit}), hit)
    if mode is SelectionMode.EDGE:
        if not mesh.is_valid_edge(hit):
            return None
        seeds = frozenset(mesh.edge_vertices(hit))
        return Target(MODE_COMPONENT, hit, (hit,), False, seeds, min(seeds))
    if not mesh.is_valid_face(hit):
        return None
    seeds = frozenset(mesh.face_vertices(hit))
    return Target(MODE_COMPONENT, None, (), False, seeds, min(seeds))


def loop_elements(selection: Selection, target: Target) -> Optional[set]:
    """What a Loop/Ring target selects in the active mode (as Shift+L/R): edges, or their
    vertices; None in Face mode (no face Loop/Ring rule for a hovered edge)."""
    if selection.mode is SelectionMode.EDGE:
        return set(target.edges)
    if selection.mode is SelectionMode.VERTEX:
        return set(target.seeds)
    return None


def apply_click_elements(selection: Selection, command: str, elements: Optional[set]) -> bool:
    """E25 on a set (the `L` mode click on a whole Loop/Ring). `elements` None or empty =
    empty space. Toggle: all already selected → remove them, otherwise add them."""
    if command not in CLICK_COMMANDS:
        raise ValueError(f"not a click command: {command!r}")
    before = selection_state(selection)
    if not elements:
        if command == SELECT:
            selection.clear()
    elif command == SELECT:
        selection.set(set(elements))
    elif command == SELECT_ADD:
        selection.add(set(elements))
    elif command == SELECT_REMOVE:
        selection.remove(set(elements))
    elif set(elements) <= active_set(selection):
        selection.remove(set(elements))
    else:
        selection.add(set(elements))
    return selection_state(selection) != before


def loop_segment(finder: TargetFinder, anchor, edge) -> Optional[tuple]:
    """The edges of `edge`'s loop from `anchor` to `edge` (both included), the shorter way on a
    closed loop (ties: the traversal direction); None if `anchor` is not on that loop."""
    loop = finder.target(edge, MODE_LOOP)
    edges = loop.edges
    if anchor not in edges:
        return None
    i, j = edges.index(anchor), edges.index(edge)
    if not loop.closed:
        lo, hi = min(i, j), max(i, j)
        return tuple(edges[lo:hi + 1])
    n = len(edges)
    forward = (j - i) % n
    if forward <= n - forward:
        return tuple(edges[(i + k) % n] for k in range(forward + 1))
    return tuple(edges[(i - k) % n] for k in range(n - forward + 1))


def face_loop(finder: TargetFinder, face_a, face_b) -> Optional[tuple]:
    """The face loop through the neighbouring faces `face_a` → `face_b` (O12): the faces the
    Ring of their shared edge passes through. None if they share no edge."""
    index = finder.index
    shared = set(index.edges_of_face.get(face_a, ())) & set(index.edges_of_face.get(face_b, ()))
    if face_a == face_b or len(shared) != 1:
        return None
    ring = finder.target(next(iter(shared)), MODE_RING)
    edges = ring.edges
    pairs = list(zip(edges, edges[1:])) + ([(edges[-1], edges[0])] if ring.closed and len(edges) > 2 else [])
    faces = []
    for e1, e2 in pairs:
        common = set(index.faces_of_edge[e1]) & set(index.faces_of_edge[e2])
        faces.extend(f for f in common if f not in faces)
    return tuple(faces) if face_a in faces and face_b in faces else None


def convert_selection(mesh: Mesh, index, selection: Selection, mode: SelectionMode) -> None:
    """O15 ("touching"): the selection becomes the components of `mode` that touch it, then
    `mode` is active. Vertex → edges/faces with any selected vertex; edge → its vertices / the
    faces at it; face → its vertices / its edges."""
    source = selection.mode
    if source is mode:
        return
    vertices = selection_seeds(mesh, selection)
    if mode is SelectionMode.VERTEX:
        result = set(vertices)
    elif mode is SelectionMode.EDGE:
        if source is SelectionMode.FACE:
            result = {e for f in selection.faces if mesh.is_valid_face(f) for e in index.edges_of_face[f]}
        else:
            result = {e for v in vertices for e in index.edges_of_vertex[v]}
    else:
        if source is SelectionMode.EDGE:
            result = {f for e in selection.edges if mesh.is_valid_edge(e) for f in index.faces_of_edge[e]}
        else:
            result = {f for v in vertices for e in index.edges_of_vertex[v] for f in index.faces_of_edge[e]}
    selection.clear()
    selection.mode = mode
    selection.set(result)
