"""Saved regions / polygroups: named, reusable sets of faces (docs/future_ideas/MODELING.md, Priorität 1;
AD-REGIONS-01, `PROVISIONAL`).

The value lives in the Mesh (`Mesh.face_regions`, journaled: Undo, Knife checkpoints and the scene file
come with it). This module holds the pure functions on top of it - the Core knows no region semantics.

- A region stores **faces only**; vertices and edges are derived (`region_vertices`, `region_edges`).
- Dead IDs stay in the stored value and are filtered when read (`live_faces`): an ID is never reused and an
  Undo can bring a face back (AD-001). Nothing here writes a pruned value except an explicit assign.
- **Inheritance (Slice 3):** a face a topology edit creates joins a region exactly when *all* of its parent faces were
  in it (`inherit`, one generic rule read from the change journal; Extrude names its parents itself,
  `inherit_children_into`). A face without a parent, or with parents in different regions, joins none - fail
  closed (AD-REGIONS-01 §1.6). `lost_count` tells how many faces a region lost since it was assigned.
- A region is **not a selection**: selecting it writes the normal `Selection` of the active mode.
- The app has no text input, so regions are named from `PRESET_NAMES` slots.
"""

from __future__ import annotations

import colorsys
from collections import defaultdict
from typing import Iterable, Mapping

from core import EdgeId, FaceId, FaceRegion, FaceRegions, Mesh, SelectionMode, VertexId

#: The slots the artist cycles through (Shift+G): the face regions of the Character workflow, then spares.
PRESET_NAMES: tuple[str, ...] = (
    "Brow", "Upper Lip", "Lower Lip", "Eyelids", "Jaw", "Region 6", "Region 7", "Region 8", "Region 9",
)


#: Region colours (Manu 2026-10-25, ZBrush-like): a distinct, desaturated colour per region. The hue steps by the golden
#: angle per slot, so every slot gets a hue no other slot has and neighbouring slots stay far apart; saturation and
#: value are fixed, low and bright. A colour is never (0, 0, 0): the renderer reads black as "no region".
TINT_SATURATION = 0.38
TINT_VALUE = 0.92
_GOLDEN_ANGLE = 0.38196601125010515  # 1 - 1/phi, as a fraction of the colour circle


def region_color(index: int) -> tuple[float, float, float]:
    """The colour of preset slot `index` (also beyond the preset count: the sequence just goes on)."""
    hue = (0.08 + index * _GOLDEN_ANGLE) % 1.0
    return colorsys.hsv_to_rgb(hue, TINT_SATURATION, TINT_VALUE)


def slot_index(name: str) -> int:
    """The slot of a region name: its place in `PRESET_NAMES`, else after them by name order (stable)."""
    if name in PRESET_NAMES:
        return PRESET_NAMES.index(name)
    return len(PRESET_NAMES) + sum(ord(c) for c in name)


def region_tints(mesh: Mesh) -> dict[FaceId, tuple[float, float, float]]:
    """`{face: colour}` of every stored face (dead IDs included: a revived face comes back coloured). Where regions
    overlap, the later region in the list wins."""
    regions = mesh.face_regions
    if regions is None:
        return {}
    tints: dict[FaceId, tuple[float, float, float]] = {}
    for region in regions.regions:
        color = region_color(slot_index(region.name))
        for f in region.faces:
            tints[f] = color
    return tints


def region_named(mesh: Mesh, name: str) -> FaceRegion | None:
    regions = mesh.face_regions
    return None if regions is None else regions.get(name)


def live_faces(mesh: Mesh, name: str) -> frozenset[FaceId]:
    """The faces of region `name` that still exist (empty for an unknown region)."""
    region = region_named(mesh, name)
    if region is None:
        return frozenset()
    return frozenset(f for f in region.faces if mesh.is_valid_face(f))


def lost_count(mesh: Mesh, name: str) -> int:
    """How many stored faces of region `name` no longer exist (topology edits since the assign)."""
    region = region_named(mesh, name)
    return 0 if region is None else sum(1 for f in region.faces if not mesh.is_valid_face(f))


def region_of_face(mesh: Mesh, face: FaceId, prefer: str | None = None) -> str | None:
    """The region a face belongs to: `prefer` (the active slot) if it contains the face, else the first region that
    does (regions may overlap), else None."""
    regions = mesh.face_regions
    if regions is None:
        return None
    if prefer is not None:
        chosen = regions.get(prefer)
        if chosen is not None and face in chosen.faces:
            return prefer
    return next((r.name for r in regions.regions if face in r.faces), None)


def interior_vertices(mesh: Mesh, faces: Iterable[FaceId]) -> set[VertexId]:
    """The vertices of `faces` that no other face touches: hiding them hides exactly `faces` and leaves every
    other face visible (a face is hidden when one of its corners is)."""
    face_set = set(faces)
    border: set[VertexId] = set()
    for f in mesh.all_face_ids():
        if f not in face_set:
            border.update(mesh.face_vertices(f))
    return region_vertices(mesh, face_set) - border


def region_vertices(mesh: Mesh, faces: Iterable[FaceId]) -> set[VertexId]:
    out: set[VertexId] = set()
    for f in faces:
        out.update(mesh.face_vertices(f))
    return out


def region_edges(mesh: Mesh, faces: Iterable[FaceId]) -> set[EdgeId]:
    """The edges that bound one of `faces`."""
    face_set = set(faces)
    out: set[EdgeId] = set()
    for e in mesh.all_edge_ids():
        if any(f in face_set for f in mesh.edge_faces(e)):
            out.add(e)
    return out


def faces_from_vertices(mesh: Mesh, vertices: Iterable[VertexId]) -> set[FaceId]:
    """The faces whose corners are all in `vertices` (what a Vertex / Edge selection means for a region)."""
    chosen = set(vertices)
    if not chosen:
        return set()
    return {f for f in mesh.all_face_ids() if chosen.issuperset(mesh.face_vertices(f))}


def elements_of(mesh: Mesh, mode: SelectionMode, faces: frozenset[FaceId]) -> set:
    """`faces` as the ids of the selection `mode`: faces, their vertices or their edges."""
    if mode is SelectionMode.FACE:
        return set(faces)
    if mode is SelectionMode.EDGE:
        return region_edges(mesh, faces)
    return region_vertices(mesh, faces)


def _replace(regions: FaceRegions | None, name: str, faces: frozenset[FaceId] | None) -> FaceRegions | None:
    """`regions` with region `name` set to `faces` (None removes it). Order: existing regions keep their
    place, a new one goes to the end."""
    kept = tuple(r for r in (regions.regions if regions else ()) if r.name != name)
    if faces is None:
        return FaceRegions(kept) if kept else None
    old = regions.get(name) if regions else None
    new = FaceRegion(name, frozenset(faces))
    if old is None:
        return FaceRegions((*kept, new))
    return FaceRegions(tuple(new if r.name == name else r for r in regions.regions))


def assigned(regions: FaceRegions | None, name: str, faces: Iterable[FaceId]) -> FaceRegions | None:
    """Region `name` becomes exactly `faces` (dead IDs of the old value are gone)."""
    return _replace(regions, name, frozenset(faces))


def added(regions: FaceRegions | None, name: str, faces: Iterable[FaceId]) -> FaceRegions | None:
    old = regions.get(name) if regions else None
    return _replace(regions, name, (old.faces if old else frozenset()) | frozenset(faces))


def removed(regions: FaceRegions | None, name: str, faces: Iterable[FaceId]) -> FaceRegions | None:
    """`faces` leave region `name`; a region that becomes empty stays (an empty named slot is valid)."""
    old = regions.get(name) if regions else None
    if old is None:
        return regions
    return _replace(regions, name, old.faces - frozenset(faces))


def deleted(regions: FaceRegions | None, name: str) -> FaceRegions | None:
    return _replace(regions, name, None)


# -- Inheritance through topology edits (Slice 3, AD-REGIONS-01 §1.6) -------------------------------------


def candidate_parents(mesh: Mesh, change) -> dict[FaceId, set[FaceId]]:
    """For every face the recorded edit created: the faces it may have come from, read from the journal alone.

    `change` is an active `MeshChange` (before-records: a removed face's old boundary, `None` for a created element).
    A removed face is a candidate parent of a created face `c` when either
    - *split*: all of `c`'s corners that existed before the edit lie on the removed face's old boundary (Split,
      Connect, Vertex / Edge Connect, Loop Insert, Knife: the new corners sit on its edges), or
    - *merge*: the removed face's old boundary lies inside `c`'s corners plus the vertices the edit removed, and the
      two share a corner (Dissolve).
    The true parent is always a candidate, so a spurious extra candidate can only make the face join *fewer*
    regions, never one its real parent was not in."""
    created = [f for f, rec in change.faces.items() if rec is None and mesh.is_valid_face(f)]
    if not created:
        return {}
    removed = {
        f: frozenset(rec) for f, rec in change.faces.items() if rec is not None and not mesh.is_valid_face(f)
    }
    if not removed:
        return {}
    gone = {v for v, rec in change.vertices.items() if rec is not None and not mesh.is_valid_vertex(v)}
    by_vertex: dict[VertexId, list[FaceId]] = defaultdict(list)
    for f, boundary in removed.items():
        for v in boundary:
            by_vertex[v].append(f)
    parents: dict[FaceId, set[FaceId]] = {}
    for c in created:
        corners = set(mesh.face_vertices(c))
        old = {v for v in corners if change.vertices.get(v, True) is not None}  # not created by this edit
        touched = {f for v in corners | gone for f in by_vertex.get(v, ())}
        candidates = set()
        for f in touched:
            boundary = removed[f]
            if old and old <= boundary:
                candidates.add(f)
            elif boundary <= (corners | gone) and boundary & corners:
                candidates.add(f)
        if candidates:
            parents[c] = candidates
    return parents


def inherit_children(mesh: Mesh, parents: Mapping[FaceId, Iterable[FaceId]]) -> FaceRegions | None:
    """The regions after every child in `parents` (child -> its parent faces) joined each region that holds ALL of its
    parents; a parent that passed its membership on leaves the region (it is gone). None = nothing changes."""
    regions = mesh.face_regions
    if regions is None or not parents:
        return None
    sets = {r.name: set(r.faces) for r in regions.regions}
    handed_on: dict[str, set[FaceId]] = {r.name: set() for r in regions.regions}
    for child, raw in parents.items():
        ps = tuple(raw)
        if not ps or not mesh.is_valid_face(child):
            continue
        for r in regions.regions:
            if all(p in r.faces for p in ps):
                sets[r.name].add(child)
                handed_on[r.name].update(p for p in ps if not mesh.is_valid_face(p))
    result = FaceRegions(
        tuple(FaceRegion(r.name, frozenset(sets[r.name] - handed_on[r.name])) for r in regions.regions)
    )
    return None if result == regions else result


def inherit(mesh: Mesh, change) -> FaceRegions | None:
    """`inherit_children` with the parents read from the journal (`candidate_parents`). Cheap exit without regions."""
    if mesh.face_regions is None:
        return None
    return inherit_children(mesh, candidate_parents(mesh, change))


def inherit_into(mesh: Mesh, change) -> bool:
    """Write `inherit(mesh, change)` into the mesh *inside* the still active recording `change`, so the new value
    is part of the same Undo step. True = regions changed."""
    result = inherit(mesh, change)
    if result is None:
        return False
    mesh.face_regions = result
    return True


def inherit_children_into(mesh: Mesh, parents: Mapping[FaceId, Iterable[FaceId]]) -> bool:
    """`inherit_children` for a tool that knows its parents (Extrude), written inside its active recording."""
    result = inherit_children(mesh, parents)
    if result is None:
        return False
    mesh.face_regions = result
    return True
