"""Attach (AD-031 P2, §15): the scene-level pieces of the command around the kernel `mesh_assembly.append_objects`.
Names and texts `PROVISIONAL`.

`Application.attach_plan` / `attach_objects` hold the checks that read the controllers (morph dials, the rig, the
editing view) and run the one `_mesh_transaction`; this module holds what needs only the scene: the plan's shape, the
look and status texts, and the object step that joins the mesh step (`attach_companion`). It never writes a mesh.
"""

from __future__ import annotations

import dataclasses

from core import Scene, SceneObject

from .mesh_assembly import AppendResult, look_of
from .scene_objects import CompositeCommand, DeleteObjectsCommand, MirrorPairCommand, pair_names
from .symmetry import SymmetryState

LABEL = "Attach"
#: The GUI's names for the D1 variant and the O-5 override (the refusal texts name what the artist sees).
TAKE_LOOK_LABEL = "Attach – Look des Ziels übernehmen"
OVERRIDE_LABEL = "Trotzdem anhängen"


@dataclasses.dataclass(frozen=True)
class AttachPlan:
    """What Attach would do now, read-only (AD-031 §15.3). `refusal`: the first reason it cannot run with the given
    choices (None = it can; the symmetry check D4 needs the result and can still refuse). `look_differences`: the
    sources whose look is not the destination's (D1). `unweighted`: incoming points without skin weights;
    `needs_override`: the destination is bound and `unweighted` > 0 (O-5) - when it is the only reason, `refusal` is
    the O-5 text and `override_only` is True, so a prompt can show the count and offer the override."""

    destination: SceneObject | None
    sources: tuple[SceneObject, ...]
    refusal: str | None
    look_differences: tuple[SceneObject, ...] = ()
    unweighted: int = 0
    needs_override: bool = False
    override_only: bool = False


def look_text(dst: SceneObject, src: SceneObject) -> str:
    """What differs between two looks: "material", "texture" or "material and texture"."""
    parts = [name for name, a, b in zip(("material", "texture"), look_of(src), look_of(dst)) if a != b]
    return " and ".join(parts)


def unweighted_text(count: int) -> str:
    return f"{count} point(s) without skin weights - they will not follow the rig"


def override_refusal(count: int) -> str:
    """The O-5 refusal (AD-031 §3.2): the count and the way out."""
    return f"{LABEL}: {unweighted_text(count)}; '{OVERRIDE_LABEL}' keeps them unweighted (no weights are made)"


def attach_companion(scene: Scene, dst: SceneObject, sources: tuple[SceneObject, ...]) -> tuple[CompositeCommand, list]:
    """The object step that joins the mesh step (not applied; `_mesh_transaction` applies it after the append): the
    mirror pairs with a source are broken first (`Scene.remove_object` refuses a paired object), then the sources are
    removed; the edit object stays (`DeleteObjectsCommand` with edit before = after = the destination). Returns it and
    the pair notes for the status line."""
    ids = {src.id for src in sources}
    broken = [pair for pair in scene.mirror_pairs if pair.a in ids or pair.b in ids]
    notes = [f"mirror pair {pair_names(scene, pair)} removed" for pair in broken]
    parts: list = [MirrorPairCommand(scene, pair, create=False) for pair in broken]
    parts.append(DeleteObjectsCommand(scene, list(sources), dst.id, dst.id))
    return CompositeCommand(parts, description(dst, sources)), notes


def description(dst: SceneObject, sources: tuple[SceneObject, ...]) -> str:
    return f"Attach {', '.join(repr(s.name) for s in sources)} to {dst.name!r}"


def result_text(
    dst: SceneObject,
    sources: tuple[SceneObject, ...],
    result: AppendResult,
    replaced_looks: tuple[SceneObject, ...],
    pair_notes: list,
    weights_note: bool,
) -> str:
    """The status line after an Attach: what joined, the replaced looks (D1 variant), the unweighted points (O-5),
    the symmetry state when it is not VALID (D4: PARTIAL is reported), the removed pairs."""
    text = description(dst, sources).replace("Attach ", "Attached ", 1)
    if replaced_looks:
        looks = ", ".join(f"{s.name!r} ({look_text(dst, s)})" for s in replaced_looks)
        text += f" - took {dst.name!r}'s look, replaced: {looks}"
    if weights_note and result.unweighted:
        text += f" - {unweighted_text(result.unweighted)}"
    after = result.symmetry_after
    if after is SymmetryState.PARTIAL:
        text += " - symmetry partial (unpaired points)"
    elif after not in (SymmetryState.OFF, SymmetryState.VALID):
        text += f" - symmetry {after.value}"
    for note in pair_notes:
        text += f" - {note}"
    return text
