"""Detach and Select Linked (AD-031 P3, §2.2, §17): the scene-level pieces around the kernel
`mesh_assembly.extract_faces` / `linked_faces`. Names and texts `PROVISIONAL`.

`Application.detach_plan` / `detach_faces` hold the checks that read the controllers (morph dials, the rig, the
editing view, hidden geometry) and run the one `_mesh_transaction`; `Application.select_linked` the selection change.
This module holds what needs only the scene: the plan's shape, the status texts, the new object that joins the mesh
step (`detached_object`) and the element a menu remembers for Select Linked (`LinkedSeed`). It never writes a mesh.
"""

from __future__ import annotations

import dataclasses

from core import EdgeId, FaceId, Mesh, ObjectId, Scene, SceneObject, SelectionMode, VertexId

from .scene_objects import AddObjectCommand, unique_object_name

LABEL = "Detach"
LINKED_LABEL = "Select Linked"


@dataclasses.dataclass(frozen=True)
class DetachPlan:
    """What Detach would do now, read-only (AD-031 §17.3). `refusal`: the first reason it cannot run (None = it can; the
    symmetric deletion's own delta check can still refuse inside the step). `faces`: the faces that leave the source,
    with their mirror partners under a symmetry definition (`mirrored` = how many the expansion added)."""

    source: SceneObject | None
    faces: frozenset[FaceId]
    refusal: str | None
    mirrored: int = 0


@dataclasses.dataclass(frozen=True)
class LinkedSeed:
    """The element under the cursor at one moment (the SPACE menu remembers it when it opens, because the pointer over
    a menu clears the hover): only valid for the same edit object and mode."""

    object_id: ObjectId
    mode: SelectionMode
    element: VertexId | EdgeId | FaceId


def detached_object(scene: Scene, src: SceneObject, mesh: Mesh) -> tuple[SceneObject, AddObjectCommand]:
    """The new object for the detached `mesh`, with `src`'s placement and look (transform, pivot, material, texture,
    state, hidden flag, group) and a free name after `src`'s (`unique_object_name`, as Duplicate); and the not yet
    applied step that adds it (`_mesh_transaction` applies it after the deletion). The scene hands out the id now
    (AD-001: it is never reused, also when the step is refused) and holds the object only once the step runs."""
    obj = scene.add_object(
        mesh, name=unique_object_name(scene, src.name), state=src.state, texture=src.texture, parent=src.parent
    )
    obj.transform, obj.pivot, obj.material, obj.hidden = src.transform, src.pivot, src.material, src.hidden
    scene.remove_object(obj.id)
    return obj, AddObjectCommand(scene, obj)


def description(src: SceneObject, obj: SceneObject, count: int) -> str:
    return f"Detach {count} face(s) of {src.name!r} as {obj.name!r}"


def result_text(src: SceneObject, obj: SceneObject, plan: DetachPlan, axis: str | None) -> str:
    """The status line after a Detach: what left, the mirror side (D5), the new object's symmetry (§3.5: set only when
    VALID, else said here), and where the artist is (O-8, `PROVISIONAL`)."""
    text = f"Detached {len(plan.faces)} face(s) of {src.name!r} as {obj.name!r}"
    if plan.mirrored:
        text += f" (with {plan.mirrored} mirror face(s))"
    if axis is not None:
        definition = obj.mesh.symmetry_definition
        if definition is None:
            text += f" - symmetry off on {obj.name!r} (not symmetric about {axis})"
        elif definition.seam_edges:
            text += f" - symmetry {axis} on {obj.name!r}"
        else:
            text += f" - symmetry {axis} on {obj.name!r}, no seam (Re-Symmetrize not available there)"
    return text + f" - still editing {src.name!r} (4: select {obj.name!r})"
