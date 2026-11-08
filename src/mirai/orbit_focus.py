"""Dynamic Orbit Focus: the last worked area the viewport orbits around (plan: docs/WP_DYNAMIC_ORBIT_FOCUS.md).

A navigation concern, deliberately separate from the Working Pivot (`mirai.pivot`): nothing here reads or
writes the pivot, and the pivot never moves the focus. The focus is app state, not mesh data: a point in
the space of the object that was worked on (it follows the object's placement, like `WorkingPivot`),
resolved to world only when an orbit gesture starts.

Where it comes from: every committed step the change journal already recorded. `FocusTracker` keeps one
`Mesh.watch()` on the edit mesh; `Application` drains it once per committed step and once per Undo / Redo,
and `worked_area` turns the drained `MeshChange` into the vertices that were actually worked on - O(touched),
never a scan of the mesh, nothing per frame or per orbit step.

Which vertices count (strict tiers, the first non-empty one wins), so a rewritten neighbour face never pulls
the centre away from the edit:
- T1: vertices moved or created; without any, the removed ones (their positions are the journal's records).
- T2: endpoints of edges created or removed (an edge whose only difference is its face list is not a change).
- T3: corners of faces created or removed (a face whose boundary only gained a split vertex is not one).
Nothing in any tier = no geometric work (regions, symmetry, layers, UVs, a cancelled preview): no focus.
Of the tier, the caller's preferred sets win in order (the selection after the step - Extrude's cap, the
Knife path, the selected side, Soft seeds - then the one before it); the centre is the bounding-box centre.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from core import Mesh, ObjectId
from core.ids import VertexId

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class OrbitFocus:
    """The remembered worked area: `position` in the space of `object_id`."""

    object_id: ObjectId
    position: Vec3
    source: str = "work"


class FocusTracker:
    """One `Mesh.watch()` on the mesh being edited; `bind` moves it to another mesh (edit-object switch)."""

    def __init__(self) -> None:
        self.mesh: Optional[Mesh] = None
        self._watch = None

    def bind(self, mesh: Optional[Mesh]) -> None:
        if mesh is self.mesh and self._watch is not None:
            return
        self.close()
        self.mesh = mesh
        self._watch = None if mesh is None else mesh.watch()

    def take(self):
        """The change since the last `take` (None when unbound); recording restarts."""
        return None if self._watch is None else self._watch.take()

    def close(self) -> None:
        if self._watch is not None:
            self._watch.close()
        self._watch = None
        self.mesh = None


def _same(a, b) -> bool:
    return tuple(a) == tuple(b)


def worked_area(change, mesh: Mesh) -> tuple[set, dict]:
    """(vertex ids of the first non-empty tier, positions of those that no longer exist). See module."""
    removed_positions: dict = {}
    moved_or_created: set = set()
    removed: set = set()
    for vid, record in change.vertices.items():
        alive = mesh.is_valid_vertex(vid)
        if record is None:
            if alive:
                moved_or_created.add(vid)
        elif not alive:
            removed.add(vid)
            removed_positions[vid] = tuple(record)
        elif not _same(mesh.vertex_position(vid), record):
            moved_or_created.add(vid)
    if moved_or_created:
        return moved_or_created, {}
    if removed:
        return removed, removed_positions

    def known(vid) -> bool:
        if mesh.is_valid_vertex(vid):
            return True
        record = change.vertices.get(vid)
        if record is None:
            return False
        removed_positions[vid] = tuple(record)
        return True

    edge_ends: set = set()
    for eid, record in change.edges.items():
        alive = mesh.is_valid_edge(eid)
        if record is None and alive:
            edge_ends.update(mesh.edge_vertices(eid))
        elif record is not None and not alive:
            edge_ends.update(vid for vid in record[:2] if known(vid))
    if edge_ends:
        return edge_ends, removed_positions

    corners: set = set()
    for fid, record in change.faces.items():
        alive = mesh.is_valid_face(fid)
        if record is None and alive:
            corners.update(mesh.face_vertices(fid))
        elif record is not None and not alive:
            corners.update(vid for vid in record if known(vid))
    return corners, removed_positions


def bbox_centre(points: Iterable[Vec3]) -> Optional[Vec3]:
    lo = hi = None
    for p in points:
        if lo is None:
            lo, hi = list(p), list(p)
            continue
        for i in range(3):
            if p[i] < lo[i]:
                lo[i] = p[i]
            elif p[i] > hi[i]:
                hi[i] = p[i]
    if lo is None:
        return None
    return ((lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, (lo[2] + hi[2]) / 2.0)


def focus_point(
    change,
    mesh: Mesh,
    query_mesh: Optional[Mesh] = None,
    preferred: Sequence[set] = (),
) -> Optional[Vec3]:
    """The centre of the worked area of `change` in `mesh`'s space, None = no geometric work.

    `query_mesh` = what is on screen with the same ids (the morph mix); live positions are read there.
    `preferred` = vertex-id sets tried in order; the first that meets the tier narrows it."""
    if change is None:
        return None
    tier, removed_positions = worked_area(change, mesh)
    if not tier:
        return None
    chosen = tier
    for wanted in preferred:
        hit = tier & wanted
        if hit:
            chosen = hit
            break
    shown = mesh if query_mesh is None else query_mesh

    def position(vid: VertexId) -> Vec3:
        if vid in removed_positions:
            return removed_positions[vid]
        if shown is not mesh and shown.is_valid_vertex(vid):
            return tuple(shown.vertex_position(vid))  # type: ignore[return-value]
        return tuple(mesh.vertex_position(vid))  # type: ignore[return-value]

    return bbox_centre(position(vid) for vid in chosen)
