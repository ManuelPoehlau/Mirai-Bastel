"""Inspection & Debugging Layer: BEFORE → OPERATION → AFTER → DIFF.

Provides reproducible state capture and comparison for the Living-Mesh prototype.
Captures: topology, rig (bones), skin (weights), morphs.

Design:
- State is captured as plain data (no references to live objects).
- Diff is computed between two captured states.
- Output is human-readable for debugging.

No semantic judgments: inspection only reports WHAT changed, not whether
the change is "correct".
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Ensure project root is in path for src.core imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.mesh import Mesh
from src.core.ids import VertexId, EdgeId, FaceId


# ---------------------------------------------------------------------------
# State Capture
# ---------------------------------------------------------------------------

@dataclass
class TopologyState:
    """Pure-data snapshot of mesh topology."""
    label: str = ""
    vertex_ids: frozenset[VertexId] = field(default_factory=frozenset)
    edge_ids: frozenset[EdgeId] = field(default_factory=frozenset)
    face_ids: frozenset[FaceId] = field(default_factory=frozenset)
    vertex_positions: dict[VertexId, tuple[float, float, float]] = field(default_factory=dict)
    edge_endpoints: dict[EdgeId, tuple[VertexId, VertexId]] = field(default_factory=dict)
    face_boundaries: dict[FaceId, list[VertexId]] = field(default_factory=dict)


@dataclass
class RigState:
    """Pure-data snapshot of rig (bones + weights + morphs)."""
    label: str = ""
    bones: dict[int, str] = field(default_factory=dict)          # bone_id → name
    bone_parents: dict[int, Optional[int]] = field(default_factory=dict)  # bone_id → parent_id
    weights: dict[VertexId, list[tuple[int, float]]] = field(default_factory=dict)  # vertex → [(bone, weight)]
    morph_targets: dict[str, dict[VertexId, tuple[float, float, float]]] = field(default_factory=dict)
    active_morphs: dict[str, float] = field(default_factory=dict)


@dataclass
class FullState:
    """Combined topology + rig state."""
    label: str = ""
    topology: TopologyState = field(default_factory=TopologyState)
    rig: RigState = field(default_factory=RigState)


# ---------------------------------------------------------------------------
# Capture Functions
# ---------------------------------------------------------------------------

def capture_topology(mesh: Mesh, label: str = "") -> TopologyState:
    """Capture current mesh topology as pure data."""
    vertices = {}
    for vid in mesh.all_vertex_ids():
        vertices[vid] = mesh.vertex_position(vid)

    edges = {}
    for eid in mesh.all_edge_ids():
        v0, v1 = mesh.edge_vertices(eid)
        edges[eid] = (v0, v1)

    faces = {}
    for fid in mesh.all_face_ids():
        faces[fid] = mesh.face_vertices(fid)

    return TopologyState(
        label=label,
        vertex_ids=frozenset(mesh.all_vertex_ids()),
        edge_ids=frozenset(mesh.all_edge_ids()),
        face_ids=frozenset(mesh.all_face_ids()),
        vertex_positions=vertices,
        edge_endpoints=edges,
        face_boundaries=faces,
    )


def capture_rig(rig, label: str = "") -> RigState:
    """Capture current rig state as pure data."""
    from bone import Bone

    bones = {}
    bone_parents = {}
    for bone_id, bone in rig.bones.items():
        bones[bone_id] = bone.name
        bone_parents[bone_id] = bone.parent.bone_id if bone.parent else None

    # Deep-copy weights
    weights = {}
    for vid, wlist in rig.skinning_weights.items():
        weights[vid] = list(wlist)

    # Deep-copy morphs
    morph_targets = {}
    for mname, mdata in rig.morph_targets.items():
        morph_targets[mname] = dict(mdata)

    active_morphs = dict(rig.active_morphs)

    return RigState(
        label=label,
        bones=bones,
        bone_parents=bone_parents,
        weights=weights,
        morph_targets=morph_targets,
        active_morphs=active_morphs,
    )


def capture_full(mesh: Mesh, rig, label: str = "") -> FullState:
    """Capture combined topology + rig state."""
    topo = capture_topology(mesh, label)
    r = capture_rig(rig, label)
    return FullState(label=label, topology=topo, rig=r)


# ---------------------------------------------------------------------------
# Diff Computation
# ---------------------------------------------------------------------------

@dataclass
class TopologyDiff:
    """Difference between two topology states."""
    new_vertices: list[VertexId] = field(default_factory=list)
    deleted_vertices: list[VertexId] = field(default_factory=list)
    new_edges: list[EdgeId] = field(default_factory=list)
    deleted_edges: list[EdgeId] = field(default_factory=list)
    new_faces: list[FaceId] = field(default_factory=list)
    deleted_faces: list[FaceId] = field(default_factory=list)
    position_changes: dict[VertexId, tuple] = field(default_factory=dict)  # vid → (old, new)


@dataclass
class RigDiff:
    """Difference between two rig states."""
    new_bones: list[int] = field(default_factory=list)
    removed_bones: list[int] = field(default_factory=list)
    new_weighted_vertices: list[VertexId] = field(default_factory=list)
    removed_weighted_vertices: list[VertexId] = field(default_factory=list)
    changed_weights: dict[VertexId, tuple] = field(default_factory=dict)  # vid → (old, new)
    new_morphs: list[str] = field(default_factory=list)
    removed_morphs: list[str] = field(default_factory=list)
    changed_active_morphs: dict[str, tuple] = field(default_factory=dict)


def diff_topology(before: TopologyState, after: TopologyState) -> TopologyDiff:
    """Compute topology diff between two states."""
    new_verts = sorted(after.vertex_ids - before.vertex_ids, key=int)
    del_verts = sorted(before.vertex_ids - after.vertex_ids, key=int)
    new_edges = sorted(after.edge_ids - before.edge_ids, key=int)
    del_edges = sorted(before.edge_ids - after.edge_ids, key=int)
    new_faces = sorted(after.face_ids - before.face_ids, key=int)
    del_faces = sorted(before.face_ids - after.face_ids, key=int)

    # Position changes (for vertices that exist in both)
    pos_changes = {}
    for vid in before.vertex_ids & after.vertex_ids:
        if before.vertex_positions.get(vid) != after.vertex_positions.get(vid):
            pos_changes[vid] = (
                before.vertex_positions.get(vid),
                after.vertex_positions.get(vid),
            )

    return TopologyDiff(
        new_vertices=new_verts,
        deleted_vertices=del_verts,
        new_edges=new_edges,
        deleted_edges=del_edges,
        new_faces=new_faces,
        deleted_faces=del_faces,
        position_changes=pos_changes,
    )


def diff_rig(before: RigState, after: RigState) -> RigDiff:
    """Compute rig diff between two states."""
    new_bones = sorted(set(after.bones.keys()) - set(before.bones.keys()))
    removed_bones = sorted(set(before.bones.keys()) - set(after.bones.keys()))

    new_weighted = sorted(set(after.weights.keys()) - set(before.weights.keys()), key=int)
    removed_weighted = sorted(set(before.weights.keys()) - set(after.weights.keys()), key=int)

    changed_weights = {}
    for vid in set(before.weights.keys()) & set(after.weights.keys()):
        if before.weights[vid] != after.weights[vid]:
            changed_weights[vid] = (before.weights[vid], after.weights[vid])

    new_morphs = sorted(set(after.morph_targets.keys()) - set(before.morph_targets.keys()))
    removed_morphs = sorted(set(before.morph_targets.keys()) - set(after.morph_targets.keys()))

    changed_active = {}
    for mname in set(before.active_morphs.keys()) & set(after.active_morphs.keys()):
        if before.active_morphs[mname] != after.active_morphs[mname]:
            changed_active[mname] = (before.active_morphs[mname], after.active_morphs[mname])

    return RigDiff(
        new_bones=new_bones,
        removed_bones=removed_bones,
        new_weighted_vertices=new_weighted,
        removed_weighted_vertices=removed_weighted,
        changed_weights=changed_weights,
        new_morphs=new_morphs,
        removed_morphs=removed_morphs,
        changed_active_morphs=changed_active,
    )


# ---------------------------------------------------------------------------
# Pretty Printing
# ---------------------------------------------------------------------------

def format_topology(state: TopologyState) -> str:
    """Format topology state as readable string."""
    lines = []
    if state.label:
        lines.append(f"  [{state.label}]")
    lines.append(f"  Vertices ({len(state.vertex_ids)}): {sorted(state.vertex_ids, key=int)}")
    lines.append(f"  Edges    ({len(state.edge_ids)}): {sorted(state.edge_ids, key=int)}")
    lines.append(f"  Faces    ({len(state.face_ids)}): {sorted(state.face_ids, key=int)}")
    for vid in sorted(state.vertex_positions.keys(), key=int):
        pos = state.vertex_positions[vid]
        lines.append(f"    v{vid}: ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})")
    return "\n".join(lines)


def format_rig(state: RigState) -> str:
    """Format rig state as readable string."""
    lines = []
    if state.label:
        lines.append(f"  [{state.label}]")
    lines.append(f"  Bones ({len(state.bones)}):")
    for bid in sorted(state.bones.keys()):
        parent = state.bone_parents.get(bid)
        pname = f"parent=b{parent}" if parent is not None else "root"
        lines.append(f"    b{bid}: '{state.bones[bid]}' ({pname})")
    lines.append(f"  Weights ({len(state.weights)}):")
    for vid in sorted(state.weights.keys(), key=int):
        wlist = state.weights[vid]
        wstr = ", ".join(f"b{b}:{w:.2f}" for b, w in wlist)
        lines.append(f"    v{vid}: [{wstr}]")
    lines.append(f"  Morphs ({len(state.morph_targets)}):")
    for mname in sorted(state.morph_targets.keys()):
        mdata = state.morph_targets[mname]
        active = state.active_morphs.get(mname, 0.0)
        lines.append(f"    '{mname}' (active={active:.2f}): {len(mdata)} vertices")
        for vid in sorted(mdata.keys(), key=int):
            off = mdata[vid]
            lines.append(f"      v{vid}: ({off[0]:.3f}, {off[1]:.3f}, {off[2]:.3f})")
    return "\n".join(lines)


def format_topology_diff(diff: TopologyDiff) -> str:
    """Format topology diff as readable string."""
    lines = ["  Topology Changes:"]
    if diff.new_vertices:
        lines.append(f"    + vertices: {diff.new_vertices}")
    if diff.deleted_vertices:
        lines.append(f"    - vertices: {diff.deleted_vertices}")
    if diff.new_edges:
        lines.append(f"    + edges: {diff.new_edges}")
    if diff.deleted_edges:
        lines.append(f"    - edges: {diff.deleted_edges}")
    if diff.new_faces:
        lines.append(f"    + faces: {diff.new_faces}")
    if diff.deleted_faces:
        lines.append(f"    - faces: {diff.deleted_faces}")
    if diff.position_changes:
        for vid, (old, new) in sorted(diff.position_changes.items(), key=lambda x: int(x[0])):
            lines.append(f"    ~ v{vid}: {old} → {new}")
    if not any([diff.new_vertices, diff.deleted_vertices, diff.new_edges,
                diff.deleted_edges, diff.new_faces, diff.deleted_faces,
                diff.position_changes]):
        lines.append("    (no changes)")
    return "\n".join(lines)


def format_rig_diff(diff: RigDiff) -> str:
    """Format rig diff as readable string."""
    lines = ["  Rig Changes:"]
    if diff.new_bones:
        lines.append(f"    + bones: {diff.new_bones}")
    if diff.removed_bones:
        lines.append(f"    - bones: {diff.removed_bones}")
    if diff.new_weighted_vertices:
        lines.append(f"    + weighted vertices: {diff.new_weighted_vertices}")
    if diff.removed_weighted_vertices:
        lines.append(f"    - weighted vertices: {diff.removed_weighted_vertices}")
    if diff.changed_weights:
        for vid, (old, new) in sorted(diff.changed_weights.items(), key=lambda x: int(x[0])):
            lines.append(f"    ~ v{vid}: {old} → {new}")
    if diff.new_morphs:
        lines.append(f"    + morphs: {diff.new_morphs}")
    if diff.removed_morphs:
        lines.append(f"    - morphs: {diff.removed_morphs}")
    if diff.changed_active_morphs:
        for mname, (old, new) in sorted(diff.changed_active_morphs.items()):
            lines.append(f"    ~ '{mname}': {old} → {new}")
    if not any([diff.new_bones, diff.removed_bones, diff.new_weighted_vertices,
                diff.removed_weighted_vertices, diff.changed_weights,
                diff.new_morphs, diff.removed_morphs, diff.changed_active_morphs]):
        lines.append("    (no changes)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# BEFORE → AFTER → DIFF Report
# ---------------------------------------------------------------------------

def print_before_after(before: FullState, after: FullState) -> None:
    """Print a BEFORE → AFTER → DIFF report."""
    print("\n" + "=" * 70)
    print(f"BEFORE: {before.label}")
    print("=" * 70)
    print(format_topology(before.topology))
    print(format_rig(before.rig))

    print("\n" + "=" * 70)
    print(f"AFTER: {after.label}")
    print("=" * 70)
    print(format_topology(after.topology))
    print(format_rig(after.rig))

    print("\n" + "=" * 70)
    print("DIFF")
    print("=" * 70)
    topo_diff = diff_topology(before.topology, after.topology)
    rig_diff = diff_rig(before.rig, after.rig)
    print(format_topology_diff(topo_diff))
    print(format_rig_diff(rig_diff))
