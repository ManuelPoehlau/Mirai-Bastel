"""Saved regions / polygroups: named, reusable sets of faces (docs/future_ideas/MODELING.md, Priorität 1;
AD-REGIONS-01, `PROVISIONAL`).

The value lives in the Mesh (`Mesh.face_regions`, journaled: Undo, Knife checkpoints and the scene file
come with it). This module holds the pure functions on top of it - the Core knows no region semantics.

- A region stores **faces only**; vertices and edges are derived (`region_vertices`, `region_edges`).
- Dead IDs stay in the stored value and are filtered when read (`live_faces`): an ID is never reused and an
  Undo can bring a face back (AD-001). Nothing here writes a pruned value except an explicit assign.
- **No inheritance yet:** topology operations leave regions as they are; new faces join no region
  (AD-REGIONS-01 §1.6). `lost_count` tells the artist how many faces a region lost since it was assigned.
- A region is **not a selection**: selecting it writes the normal `Selection` of the active mode.
- The app has no text input, so regions are named from `PRESET_NAMES` slots.
"""

from __future__ import annotations

from typing import Iterable

from core import EdgeId, FaceId, FaceRegion, FaceRegions, Mesh, SelectionMode, VertexId

#: The slots the artist cycles through (Shift+G): the face regions of the Character workflow, then spares.
PRESET_NAMES: tuple[str, ...] = (
    "Brow", "Upper Lip", "Lower Lip", "Eyelids", "Jaw", "Region 6", "Region 7", "Region 8", "Region 9",
)


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
