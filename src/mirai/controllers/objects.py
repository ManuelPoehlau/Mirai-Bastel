"""ObjectController (AD-027 §3.4): the scene's objects - add / import / export / delete, mirror pairs, Reference on / off,
Apply / Clear transform, per-object material and texture display (AD-024, AD-026), the objects' views (render entries,
highlight, cameras, pick caches), the edit-object switch (AD-021 M2-4, E-14), the object click and the object gesture
of mode `4` (`ObjectGesture`, a gesture kind) - and `can_run` stage 4, the object-mode refusal (AD-021 L-1).

Behaviour as it was inside `Application` (AD-027 M7 moves it, nothing else). The object gesture is a gesture kind:
it subclasses `gestures.GestureSession` and the controller gets the `GestureController` at construction (the axis
constraint, the one-shot commit) - the one dependency between controllers, one-way (AD-027 §7.1, M7). Everything an
edit-object switch moves outside the objects (mask, hidden set, region tints, Soft radius, the morph editing view) stays
with `Application`, which `services.follow_edit_object()` reaches.
"""

from __future__ import annotations

import dataclasses
import os
import time
from pathlib import Path
from typing import Callable

from core import (
    Mesh,
    MirrorPair,
    ObjectId,
    ObjectMaterial,
    ObjectState,
    ObjectTransform,
    SceneObject,
    Selection,
    SelectionMode,
)
from core.operations import MeshDeltaCommand, record_mesh_change
from core.scene import IDENTITY_TRANSFORM

from viewport.gl_render_store import DEFAULT_BASE_COLOR

from .. import object_space
from ..interaction import commands
from ..interaction.dial import PRECISION_GAIN, DialAngle
from ..interaction.tools.rotate import RotateTool
from ..interaction.tools.scale import ScaleTool
from ..interaction.tools.transform import _resolve_space
from ..object_mirror import PLANES as MIRROR_PLANES, in_sync, mirror_mesh, mirror_placement, mirror_transform
from ..object_space import ObjectSpaceCamera
from ..scene_objects import (
    REFERENCE_GHOST_ALPHA,
    AddObjectCommand,
    ApplyRefused,
    CompositeCommand,
    DeleteObjectsCommand,
    DeleteRefused,
    MirrorPairCommand,
    MirrorRefused,
    ObjectMaterialCommand,
    ObjectPivotCommand,
    ObjectStateCommand,
    ObjectTransformCommand,
    applied_symmetry_axis,
    apply_placement,
    check_pairable,
    describe_pair,
    editable_material,
    object_base_color,
    object_finish,
    out_of_sync_text,
    pair_existing_command,
    pair_names,
    plan_object_delete,
    resync_command,
    selected_color,
    unique_object_name,
)
from ..viewport.look_controls import clamp_material_values, material_row
from ..viewport.picking import pick_object
from ..viewport.picking_cache import PickCache
from .gestures import TRANSFORM_COMMANDS, GestureController, GestureSession, commit_hint, constraint_suffix
from .services import AppServices

#: AD-021 M2-2 (E-11): in mode `4` W/E/R arm the object gesture instead of a component tool; T (Extrude) stays
#: component work.
OBJECT_TRANSFORM_COMMANDS = frozenset({commands.MOVE, commands.ROTATE, commands.SCALE})

#: AD-021 M2-3 (L-3): the two explicit level conversions, mode `4` only. Labels for the status line (`PROVISIONAL`).
PLACEMENT_COMMANDS: dict[str, str] = {
    commands.APPLY_TRANSFORM: "Apply transform",
    commands.CLEAR_TRANSFORM: "Clear transform",
}

#: AD-021 M1 (L-1: one gesture writes one level): commands that work on the edit object's components. In mode `4`
#: they are refused with a status line, except the object transforms; a Reference is locked (RF-4, Q-1). Undo/Redo,
#: display, Soft settings and constraints are state or history, not component work, and stay allowed.
COMPONENT_COMMANDS = frozenset(
    {
        *TRANSFORM_COMMANDS,
        commands.CONNECT,
        *commands.REMOVAL_COMMANDS,
        commands.COLLAPSE,
        commands.BORDER_SELECT,
        commands.CAP,
        commands.SYMMETRY_CYCLE,
        commands.RESYMMETRIZE,
        *commands.MASK_COMMANDS,
        *commands.HIDE_COMMANDS,
        *commands.POLYGROUP_COMMANDS,
        *commands.LOOP_COMMANDS,
        *commands.SELECTION_STEP_COMMANDS,
    }
)


def selection_state(selection: Selection) -> tuple[frozenset, ...]:
    return (
        frozenset(selection.vertices),
        frozenset(selection.edges),
        frozenset(selection.faces),
        frozenset(selection.objects),
    )


def objects_text(objects: list[SceneObject]) -> str:
    names = ", ".join(repr(obj.name) for obj in objects)
    return f"Object {names}" if len(objects) == 1 else f"Objects {names}"


def references_note(references: tuple[str, ...]) -> str:
    if not references:
        return ""
    names = ", ".join(repr(name) for name in references)
    return f" - Reference {names} stays (locked)"


def mirror_note(followers: list) -> str:
    if not followers:
        return ""
    names = ", ".join(f"{f.name!r} mirrors {d.name!r}" for f, _, d, _, _ in followers)
    return f" - {names}"


class ObjectGesture(GestureSession):
    """A W/E/R gesture in mode `4` (AD-021 M2-2, E-11): the targets with their start transforms (Esc restores exactly
    these), the References of the selection that stay where they are, the selection snapshot for the mirror entry,
    and what the motion has accumulated so far. Every step recomputes each transform from its start, so nothing
    drifts inside one gesture. Mirror pairs (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.4): `followers` = (follower, its
    start, driver, driver's start, pair); the follower is F(driver) after every step - stateless."""

    def __init__(self, controller: "ObjectController", command: str, key: str, origin, targets, references,
                 followers) -> None:
        super().__init__(controller.gestures, command, key, (), origin)
        self._objects = controller
        self.targets: list[tuple[SceneObject, ObjectTransform]] = [(obj, obj.transform) for obj in targets]
        self.references: tuple[str, ...] = references
        self.selection_before = self.services.selection_snapshot()
        self.followers: list = followers
        self.axis: tuple[float, float, float] | None = None
        self.mask: tuple[float, float, float] | None = None
        self.move: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.pixels = 0.0
        self.angle = 0.0  # Rotate: the total angle (rad), from the dial or the dx fallback
        self.dial: DialAngle | None = None

    @property
    def label(self) -> str:
        return f"Object {super().label}"

    def step(self, dx: float, dy: float) -> bool:
        """One motion. The first one fixes the constraint (sticky axis, read once as at `begin()`; Q-4: Scale is always
        uniform) and, for Rotate, the axis: the camera's view direction without a constraint, else the world axis or
        the plane's normal. Move: world delta on the camera plane through the first target's pivot, masked by the
        world constraint, `t' = t_start + Σdelta`. Rotate: `R' = Q(axis, angle)·R_start` about each object's own
        pivot (its world position `t + c` does not depend on R and s, so no translation is corrected). Scale:
        `s' = s_start·f`. The factors are the component tools' (`RotateTool`, `ScaleTool`)."""
        services = self.services
        camera = services.camera
        command = self.command
        if not self.begun:
            space = None if command == commands.SCALE else self._controller.axis_constraint
            self.space = space
            if command == commands.ROTATE:
                self.axis = camera.basis()[0] if space is None else _resolve_space(space, for_rotation=True)
            elif command == commands.MOVE and space is not None:
                self.mask = _resolve_space(space, for_rotation=False)
            self.begun = True
        if command == commands.MOVE:
            anchor = self.targets[0][0]
            width, height = services.viewport_size
            delta = camera.screen_delta_to_world(object_space.to_world(anchor, anchor.pivot), dx, dy, width, height)
            if self.mask is not None:
                delta = tuple(d * m for d, m in zip(delta, self.mask))
            self.move = tuple(self.move[i] + delta[i] for i in range(3))
        elif command == commands.ROTATE:
            self.pixels += dx
            self._rotate_angle(dx)
        else:
            self.pixels += dx + dy
        for obj, start in self.targets:
            obj.transform = self._transform_from(start)
        for follower, follower_start, driver, driver_start, pair in self.followers:
            follower.transform = (
                follower_start
                if driver.transform == driver_start
                else mirror_transform(driver.transform, pair.normal, pair.offset)
            )
        self._objects.placement_changed()
        return True

    def _rotate_angle(self, dx: float) -> None:
        """The Rotate angle: the dial about the first object's pivot when the pointer is known (as the mesh Rotate),
        else the dx fallback."""
        services = self.services
        width, height = (int(v) for v in services.viewport_size)
        shift = services.modifiers[0]
        if self.rotate_virtual is None:
            self.angle += RotateTool.RADIANS_PER_PIXEL * dx * (PRECISION_GAIN if shift else 1.0)
            return
        if self.dial is None:
            anchor = self.targets[0][0]
            pivot = object_space.to_world(anchor, anchor.pivot)
            self.dial = DialAngle(services.camera, pivot, self.axis, self.rotate_press, width, height)
        self.angle = self.dial.update(*self.rotate_virtual, width, height, shift, self.snap_held())

    def _transform_from(self, start: ObjectTransform) -> ObjectTransform:
        """The transform the running gesture gives an object that started at `start`; exactly `start` while the
        gesture has accumulated nothing."""
        command = self.command
        if command == commands.MOVE:
            if self.move == (0.0, 0.0, 0.0):
                return start
            translation = tuple(start.translation[i] + self.move[i] for i in range(3))
            return dataclasses.replace(start, translation=translation)
        if command == commands.ROTATE:
            angle = self.angle
            if angle == 0.0:
                return start
            turn = object_space.axis_angle_rotation(self.axis, angle)
            rotation = object_space.orthonormalize(object_space.matmul3(turn, start.rotation))
            return dataclasses.replace(start, rotation=rotation)
        factor = max(ScaleTool.MIN_SCALE, 1.0 + ScaleTool.SCALE_PER_PIXEL * self.pixels)
        if factor == 1.0:
            return start
        return dataclasses.replace(start, scale=start.scale * factor)

    def release(self) -> None:
        """One `ObjectTransformCommand` for every object that changed (Q-3: one Undo step; mirror entry with
        `mesh_step=False`), status line on the level (Q-6); a tap or a gesture that ends where it started records
        nothing."""
        services = self.services
        label, _, participle = TRANSFORM_COMMANDS[self.command]
        if not self.begun:
            services.status(f"Object {label}: no motion, nothing {participle}")
            return
        starts = self.targets + [(f, start) for f, start, _, _, _ in self.followers]
        changes = [(obj, start, obj.transform) for obj, start in starts if obj.transform != start]
        if not changes:
            services.status(f"Object {label}: no change")
            return
        objects = [obj for obj, _, _ in changes]
        services.history.push(ObjectTransformCommand(changes, f"Object {label.lower()}"))
        services.record_selection_history(self.selection_before, mesh_step=False)
        services.status(
            f"{objects_text(objects)}: {participle} (object level)"
            f"{constraint_suffix(self.space)}"
            f"{mirror_note(self.followers)}"
            f"{references_note(self.references)}"
        )

    def abort(self) -> None:
        """Esc: every target gets its start transform back - the same instance, exactly."""
        for obj, start in self.targets + [(f, start) for f, start, _, _, _ in self.followers]:
            obj.transform = start
        self._objects.placement_changed()


class ObjectController:
    """The objects of the scene and their views. `pick_caches` = the pick caches of the objects other than the edit
    object (mode `4` picking; the edit object shares the app's cache), `cameras` = one object-space camera per
    placed object (stable, so that a `PickCache` keyed on `id(camera)` keeps working), `highlight_key` = what the
    selection highlight in mode `4` was last drawn for, `reference_ghost` = all References drawn as Ghost (`Alt+D`;
    display state, kept across scene loads), `last_edit_switch_seconds` = how long the last Q-5 switch took."""

    def __init__(self, services: AppServices, gestures: GestureController) -> None:
        self.services = services
        self.gestures = gestures
        self.pick_caches: dict[ObjectId, PickCache] = {}
        self.highlight_key: tuple | None = None
        self.cameras: dict[ObjectId, ObjectSpaceCamera] = {}
        self.reference_ghost: bool = False
        self.last_edit_switch_seconds: float = 0.0

    # -- adding, importing, exporting, deleting (AD-021 M1, Track A1/A2) -----------------------------

    def add_reference(self, mesh: Mesh, name: str, texture: str | None) -> SceneObject:
        """A built mesh as a new Reference (A-1, Q-10): one Undo step; the camera stays (Q-9); edit object, selection
        and the edit object's mesh are untouched."""
        services = self.services
        before = services.selection_snapshot()
        obj = services.scene.add_object(mesh, name=name, state=ObjectState.REFERENCE, texture=texture)
        services.history.push(AddObjectCommand(services.scene, obj))
        services.record_selection_history(before, mesh_step=False)
        self.sync_views()
        services.status(f"Added {obj.name!r} as Reference")
        return obj

    def refused_during_interaction(self, label: str) -> bool:
        """True (status posted) while an interaction holds the keys."""
        owner = self.services.interaction_owner
        if owner is None:
            return False
        self.services.status(f"{label}: not while the {owner} interaction runs")
        return True

    def layer_refused(self, key, meshes) -> bool:
        """AD-025 §4.4 at an operation's own site: True and the text posted when refused."""
        text = self.services.layer_refusal(key, meshes)
        if text is None:
            return False
        self.services.status(text)
        return True

    def add_mesh_object(self, build: Callable[[], Mesh], name: str, label: str) -> SceneObject | None:
        """A new editable object (Add Mesh, Import OBJ): mode `4`, the new object is the only object selection, the
        components are cleared, the edit object stays. One Undo step."""
        if self.refused_during_interaction(label):
            return None
        if self.layer_refused("add_primitive", ()):
            return None
        services = self.services
        mesh = build()
        scene, selection = services.scene, services.selection
        before = services.selection_snapshot()
        obj = scene.add_object(mesh, name=name)
        services.history.push(AddObjectCommand(scene, obj))
        selection.mode = SelectionMode.OBJECT
        selection.clear()
        selection.objects = {obj.id}
        selection.hovered = None
        services.record_selection_history(before, mesh_step=False)
        services.viewport.on_selection_changed()
        services.soft_preview_refresh()
        self.sync_views()
        services.refresh_hover()
        services.status(f"Added {obj.name!r} - selected (Object mode); W/E/R place it, 1/2/3 edit it")
        return obj

    def export_obj(self, path: str | Path) -> bool:
        """The edit object in world space (object transform applied), one `o` record. True = written."""
        from ..obj_export import mesh_to_obj

        if self.refused_during_interaction("Export OBJ"):
            return False
        services = self.services
        obj = services.document_object  # the rest shape of the base, never the editing view
        path = Path(path)
        text = mesh_to_obj(obj.mesh, obj.name, lambda p: object_space.to_world(obj, p))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        services.status(f"Exported OBJ: {path}")
        return True

    def delete_selected(self) -> bool:
        """`Delete` in mode `4` (Track A2): remove the selected objects - **not** points/edges/faces (the component
        Delete is unchanged). One Undo step (`DeleteObjectsCommand` + one mirror entry) however many objects; the same
        instances come back on Undo with their ids, and Undo restores the selection and the edit object of before.
        Deleting the edit object hands the edit role to a surviving Normal object (`plan_object_delete`); the last
        object, or leaving only References, is refused with a status line - the scene has no empty state."""
        label = "Delete object"
        if self.refused_during_interaction(label):
            return False
        services = self.services
        scene, selection = services.scene, services.selection
        selected = [oid for oid in sorted(selection.objects) if oid in scene.objects]
        if not selected:
            services.status(f"{label}: no object selected - click one first")
            return False
        try:
            doomed, edit_after = plan_object_delete(scene, selected)
        except DeleteRefused as exc:
            services.status(f"{label}: {exc}")
            return False
        before = services.selection_snapshot()
        edit_before = scene.edit_object_id
        edit_changed = edit_after != edit_before
        # Mirror pairs (proposal §5.5): a pair with a deleted object is broken in the same Undo step - first, so
        # the scene never holds a pair to a missing object; Undo restores both.
        doomed_ids = {obj.id for obj in doomed}
        broken = [pair for pair in scene.mirror_pairs if pair.a in doomed_ids or pair.b in doomed_ids]
        pair_notes = []
        for pair in broken:
            survivors = [scene.objects[oid] for oid in (pair.a, pair.b) if oid not in doomed_ids]
            if survivors:
                pair_notes.append(f"mirror pair with {survivors[0].name!r} broken")
            else:
                pair_notes.append(f"mirror pair {pair_names(scene, pair)} removed")
            scene.remove_mirror_pair(pair)
        scene.edit_object_id = edit_after
        for obj in doomed:
            scene.remove_object(obj.id)
        delete = DeleteObjectsCommand(scene, doomed, edit_before, edit_after)
        if broken:
            delete = CompositeCommand(
                [MirrorPairCommand(scene, pair, create=False) for pair in broken] + [delete],
                delete.description,
            )
        services.history.push(delete)
        selection.objects -= {obj.id for obj in doomed}
        if edit_changed:
            selection.clear()  # component ids belong to the deleted edit object's mesh
        selection.hovered = None
        services.record_selection_history(before, mesh_step=edit_changed)
        if edit_changed:
            services.follow_edit_object()
        else:
            self.sync_views()
        services.soft_preview_refresh()
        services.refresh_hover()
        names = ", ".join(repr(obj.name) for obj in doomed)
        text = f"Deleted {names}"
        for note in pair_notes:
            text += f" - {note}"
        if edit_changed:
            text += f" - now editing {scene.edit_object.name!r}"
        services.status(text)
        return True

    # -- Mirror pairs (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5, 2026-10-23, `PROVISIONAL`) ----------------
    #
    # Window-level commands (the Shift+M menu, `src/scene_menu.py`), mode `4` only. Each is one Undo step built from
    # the existing commands; pair state changes only through `MirrorPairCommand`. Planes: X = 0 / Y = 0 / Z = 0
    # (`object_mirror.PLANES`, proposal §9 decision 7 default).

    def _mirror_selection(self, label: str) -> list[SceneObject] | None:
        if self.refused_during_interaction(label):
            return None
        services = self.services
        if services.selection.mode is not SelectionMode.OBJECT:
            services.status(f"{label}: works on objects - press 4 and select them")
            return None
        scene = services.scene
        selected = [scene.objects[oid] for oid in sorted(services.selection.objects) if oid in scene.objects]
        if not selected:
            services.status(f"{label}: no object selected - click one first")
            return None
        return selected

    def _selected_pairs(self, selected: list[SceneObject]) -> list[MirrorPair]:
        pairs: list[MirrorPair] = []
        for obj in selected:
            pair = self.services.scene.mirror_pair_of(obj.id)
            if pair is not None and pair not in pairs:
                pairs.append(pair)
        return pairs

    def mirror_copy(self, axis: str = "X") -> SceneObject | None:
        """Mirror copy (proposal §5.5): a new Normal object B with the selected object's mesh reflected across the
        world plane (`object_mirror.mirror_mesh`: positions `H p`, winding reversed, no symmetry definition) at
        `F(A)`, paired with A. One Undo step (`AddObjectCommand` + `MirrorPairCommand`); B becomes the object
        selection (`PROVISIONAL`), named by `unique_object_name`. Refused (status line, None) without exactly one
        selected object, for a Reference or an object already in a pair."""
        label = "Mirror copy"
        normal, offset = MIRROR_PLANES[axis]
        selected = self._mirror_selection(label)
        if selected is None:
            return None
        services = self.services
        if len(selected) != 1:
            services.status(f"{label}: select one object ({len(selected)} are selected)")
            return None
        scene, selection = services.scene, services.selection
        source = selected[0]
        if self.layer_refused("mirror_copy", [source.mesh]):
            return None
        try:
            check_pairable(scene, [source])
        except MirrorRefused as exc:
            services.status(f"{label}: {exc}")
            return None
        before = services.selection_snapshot()
        obj = scene.add_object(mirror_mesh(source.mesh, normal), name=unique_object_name(scene, source.name))
        obj.transform, obj.pivot = mirror_placement(source, normal, offset)
        obj.material = source.material  # AD-024 Q-M2: the copy keeps the source's material
        obj.texture = source.texture  # AD-026: and its texture (the UVs come with the mesh)
        add = AddObjectCommand(scene, obj)
        pair = MirrorPair(source.id, obj.id, normal=normal, offset=offset)
        scene.add_mirror_pair(pair)
        services.history.push(
            CompositeCommand([add, MirrorPairCommand(scene, pair, create=True)], f"Mirror copy {source.name!r}")
        )
        selection.objects = {obj.id}
        selection.hovered = None
        services.record_selection_history(before, mesh_step=False)
        if services.viewport is not None:
            services.viewport.on_selection_changed()
        self.sync_views()
        services.refresh_hover()
        services.status(
            f"Mirror copy: {describe_pair(scene, pair)} - paired: moving either moves both mirrored;"
            " the meshes stay independent"
        )
        return obj

    def pair_selected(self, axis: str = "X") -> bool:
        """Pair two selected objects (proposal §5.5): the lower ObjectId drives and stays, the other is placed at
        `F(driver)` (transform, scale and pivot - announced), then the pair. One Undo step. The meshes are not
        inspected. Refused unless exactly two objects are selected, for a Reference or an object already in a pair."""
        label = "Mirror pair"
        normal, offset = MIRROR_PLANES[axis]
        selected = self._mirror_selection(label)
        if selected is None:
            return False
        services = self.services
        if len(selected) != 2:
            services.status(
                f"{label}: select exactly two objects ({len(selected)} are selected) - the first created"
                " stays, the other is placed at its mirror"
            )
            return False
        driver, follower = selected
        before = services.selection_snapshot()
        try:
            command = pair_existing_command(services.scene, driver, follower, normal, offset)
        except MirrorRefused as exc:
            services.status(f"{label}: {exc}")
            return False
        services.history.push(command)
        services.record_selection_history(before, mesh_step=False)
        self.placement_changed()
        pair = services.scene.mirror_pair_of(driver.id)
        services.status(
            f"{label}: {follower.name!r} is placed at the mirror of {driver.name!r}"
            f" - paired {describe_pair(services.scene, pair)}"
        )
        return True

    def break_mirror_pairs(self) -> bool:
        """Break the pairs of the selected objects (proposal §5.5): both objects stay exactly where they are; one Undo
        step however many pairs."""
        label = "Break pair"
        selected = self._mirror_selection(label)
        if selected is None:
            return False
        services = self.services
        pairs = self._selected_pairs(selected)
        if not pairs:
            services.status(f"{label}: no selected object is in a mirror pair")
            return False
        scene = services.scene
        names = ", ".join(pair_names(scene, pair) for pair in pairs)
        before = services.selection_snapshot()
        parts = []
        for pair in pairs:
            scene.remove_mirror_pair(pair)
            parts.append(MirrorPairCommand(scene, pair, create=False))
        services.history.push(parts[0] if len(parts) == 1 else CompositeCommand(parts, "Break mirror pairs"))
        services.record_selection_history(before, mesh_step=False)
        services.status(f"Mirror pair {names} broken - both stay where they are")
        return True

    def resync_mirror_pairs(self) -> bool:
        """Re-sync the pairs of the selected objects (proposal §5.7): B is placed at `F(A)` again (`pair.a` = the
        driver at creation). One Undo step; nothing for a pair in sync; refused, before anything changes, when a B to
        move is a Reference."""
        label = "Re-sync"
        selected = self._mirror_selection(label)
        if selected is None:
            return False
        services = self.services
        pairs = self._selected_pairs(selected)
        if not pairs:
            services.status(f"{label}: no selected object is in a mirror pair")
            return False
        scene = services.scene
        todo = [p for p in pairs if not in_sync(scene.objects[p.a], scene.objects[p.b], p)]
        if not todo:
            names = ", ".join(pair_names(scene, pair) for pair in pairs)
            services.status(f"{label}: mirror pair {names} is in sync - nothing to do")
            return False
        for pair in todo:
            b = scene.objects[pair.b]
            if b.state is ObjectState.REFERENCE:
                services.status(
                    f"{label}: {b.name!r} (mirror partner of {scene.objects[pair.a].name!r}) is a Reference - locked"
                )
                return False
        before = services.selection_snapshot()
        parts = [resync_command(scene, pair) for pair in todo]
        services.history.push(parts[0] if len(parts) == 1 else CompositeCommand(parts, "Re-sync mirror pairs"))
        services.record_selection_history(before, mesh_step=False)
        self.placement_changed()
        moved = ", ".join(repr(scene.objects[pair.b].name) for pair in todo)
        services.status(f"{label}: {moved} placed at the mirror of its partner again")
        return True

    def _mirror_followers(self, label: str, targets: list[SceneObject]) -> tuple[list[SceneObject], list] | None:
        """The object gesture's drivers and followers (proposal §5.4): a pair is one unit - the partner of a driven
        object follows; with both selected the lower ObjectId drives. None (refusal posted) when a partner is a
        Reference (locked) or a pair is out of sync."""
        services = self.services
        scene = services.scene
        ids = {obj.id for obj in targets}
        drivers: list[SceneObject] = []
        followers: list = []
        for obj in targets:
            pair = scene.mirror_pair_of(obj.id)
            if pair is None:
                drivers.append(obj)
                continue
            partner = scene.objects[pair.other(obj.id)]
            if partner.id in ids and partner.id < obj.id:
                continue  # the partner drives this one
            if partner.state is ObjectState.REFERENCE:
                services.status(f"{label}: {partner.name!r} (mirror partner of {obj.name!r}) is a Reference - locked")
                return None
            if not in_sync(scene.objects[pair.a], scene.objects[pair.b], pair):
                services.status(f"{label}: {out_of_sync_text(scene, pair)}")
                return None
            drivers.append(obj)
            followers.append((partner, partner.transform, obj, obj.transform, pair))
        return drivers, followers

    # -- the objects' views (AD-021 §4.6) ------------------------------------------------------------

    def sync_views(self) -> None:
        """Match the render entries and pick caches of the non-edit objects with `scene.objects` (AD-021 §4.6 "App
        consequences"): a removed object loses its entry, a new one gets one, a state change only changes the colour.
        Runs after every object step, after Undo/Redo and on loading. The viewport draws the edit object itself, with
        the selection overlays (§4.4 "Drawing")."""
        services = self.services
        scene = services.scene
        others = {oid: obj for oid, obj in scene.objects.items() if oid != scene.edit_object_id}
        for oid in [oid for oid in self.pick_caches if oid not in others]:
            del self.pick_caches[oid]
        for oid in [oid for oid in self.cameras if oid not in scene.objects]:
            del self.cameras[oid]
        viewport = services.viewport
        if viewport is None:
            return
        display = services.display
        # M2-1: the edit object's placement (mesh uniform + `view·model` for its overlays).
        viewport.set_model_matrix(object_space.model_matrix(scene.edit_object))
        for key in [key for key in viewport.object_entries if key not in others]:
            viewport.remove_object_entry(key)
        highlighted = self.highlighted()
        for oid, obj in others.items():
            reference = obj.state is ObjectState.REFERENCE
            viewport.set_object_entry(
                oid,
                obj.mesh,
                selected_color(obj, DEFAULT_BASE_COLOR) if oid in highlighted else object_base_color(obj),
                model_matrix=object_space.model_matrix(obj),
                # M2-0 (§7.3): RD-1 Ghost for every Reference on `Alt+D`; RD-3 a Reference is drawn in Wireframe too -
                # a Normal object follows the display mode.
                alpha=REFERENCE_GHOST_ALPHA if reference and self.reference_ghost else 1.0,
                ignores_wireframe=reference,
                finish=object_finish(obj, display.surface_finish),
                texture=self._shown_texture(obj, oid in highlighted),
            )
        edit = scene.edit_object
        viewport.set_edit_base_color(
            selected_color(edit, DEFAULT_BASE_COLOR) if edit.id in highlighted else object_base_color(edit),
            object_finish(edit, display.surface_finish),
            self._shown_texture(edit, edit.id in highlighted),
        )
        self.highlight_key = self._highlight_signature()

    def _shown_texture(self, obj: SceneObject, highlighted: bool) -> str | None:
        """The texture the viewport draws for `obj` (AD-026): its own while textures are shown
        (`DisplayState.show_texture`); a highlighted object (mode `4` selection) shows its selection tint instead,
        so the selection stays visible on a textured object (`PROVISIONAL`)."""
        if obj.texture is None or highlighted or not self.services.display.show_texture:
            return None
        return obj.texture

    def toggle_texture_display(self) -> bool:
        """Textures on/off: pure view state, no Undo step. Returns the new state."""
        display = self.services.display
        display.show_texture = not display.show_texture
        self.sync_views()
        self.services.status(f"Textures: {'on' if display.show_texture else 'off'}")
        return display.show_texture

    def toggle_reference_ghost(self) -> bool:
        self.reference_ghost = not self.reference_ghost
        self.sync_views()
        self.services.status(f"References: {'ghost' if self.reference_ghost else 'shaded'}")
        return True

    def highlighted(self) -> frozenset:
        """The objects drawn as selected: the object selection, in mode `4` only (2026-10-16, Manu: "man kann nicht
        wirklich sehen, welches Objekt ausgewählt ist"; look `PROVISIONAL`)."""
        services = self.services
        if services.selection.mode is not SelectionMode.OBJECT:
            return frozenset()
        return frozenset(oid for oid in services.selection.objects if oid in services.scene.objects)

    def _highlight_signature(self) -> tuple:
        scene = self.services.scene
        return (
            self.highlighted(),
            scene.edit_object_id,
            tuple((oid, obj.state, obj.material, obj.texture) for oid, obj in scene.objects.items()),
        )

    def sync_highlight(self) -> None:
        """Redraws the selection highlight when the object selection, the mode, the edit object or a state changed
        since it was last drawn - every path that changes them (click, box, Undo, key `4`, ...) is covered by the
        per-frame call in `Application.update_viewport`."""
        if self.services.viewport is not None and self._highlight_signature() != self.highlight_key:
            self.sync_views()

    def placement_changed(self) -> None:
        """An object's `transform` / `pivot` changed (AD-021 M2-1; the object gesture and its Undo call this).
        Positions in object space are unchanged, so nothing is rebuilt: the matrices go to the viewport, every pick
        cache re-projects (the edit object's camera revision already carries its transform; the explicit invalidation
        also covers the switch between `OrbitCamera` and its adapter), the hover is re-picked. Soft weights and
        symmetry live in object space and stay as they are (§4.8)."""
        self.services.invalidate_picks()
        for cache in self.pick_caches.values():
            cache.invalidate()
        self.sync_views()
        self.services.refresh_hover()

    def meshes_changed(self, object_ids) -> None:
        """The mesh of these non-edit objects changed (Apply transform, its Undo/Redo): their render entries rebuild
        and their pick caches re-project."""
        viewport = self.services.viewport
        for oid in object_ids:
            cache = self.pick_caches.get(oid)
            if cache is not None:
                cache.invalidate()
            if viewport is not None and oid in viewport.object_entries:
                viewport.object_entries[oid].mark_topology_dirty()

    # -- the edit object (AD-021 M2-4, E-14) ---------------------------------------------------------

    def set_edit_object(self, object_id: ObjectId) -> None:
        """**The one place** that changes the edit object. Sets `scene.edit_object_id` and moves everything that hangs
        on the edit object's mesh with it (`services.follow_edit_object`: the viewport's overlay entry, the pick
        caches, the hover, the soft radius - the fourth radius event, §4.8 - and these views). The symmetry report
        cache is keyed by the mesh's geometry and needs nothing. The caller owns the component sets (§4.4: the Q-5
        gesture clears them, Undo/Redo restores the ones of the step), the soft preview that follows from them, and
        the refusals (a running interaction, a Reference - RF-5)."""
        scene = self.services.scene
        if object_id == scene.edit_object_id:
            return
        scene.edit_object_id = object_id
        self.services.follow_edit_object()

    def edit_from_selection(self) -> str:
        """Q-5: switch the edit object to the one Normal object selected in `4` (E-14). Returns the status-line note:
        whom `1`/`2`/`3` now edit, or why the edit object stayed."""
        services = self.services
        scene = services.scene
        selected = [scene.objects[oid] for oid in sorted(services.selection.objects) if oid in scene.objects]
        edit = scene.edit_object
        if not selected:
            return ""
        if len(selected) > 1:
            return f" · {len(selected)} objects selected - still editing {edit.name!r}"
        (obj,) = selected
        if obj.state is ObjectState.REFERENCE:
            return f" · {obj.name!r} is a Reference - still editing {edit.name!r}"
        if obj.id == edit.id:
            return f" · editing {edit.name!r}"
        owner = services.interaction_owner
        if owner is not None:
            return f" · not while the {owner} interaction runs - still editing {edit.name!r}"
        started = time.perf_counter()
        self.set_edit_object(obj.id)
        self.last_edit_switch_seconds = time.perf_counter() - started
        return f" · editing {obj.name!r}"

    def camera_for(self, obj: SceneObject):
        """The camera as the object's own space sees it (AD-021 M2-1, E-7): the `OrbitCamera` itself while the
        placement is identity (bit-exact as before), else its stable `ObjectSpaceCamera`."""
        camera = self.services.camera
        if object_space.is_identity(obj.transform):
            return camera
        adapter = self.cameras.get(obj.id)
        if adapter is None or adapter.camera is not camera:
            adapter = self.cameras[obj.id] = ObjectSpaceCamera(camera, obj)
        return adapter

    @property
    def edit_camera(self):
        """The camera every component path uses (picking, Knife, W/E/R/T): in the edit object's space (L-5)."""
        return self.camera_for(self.services.scene.edit_object)

    # -- picking and clicking in mode `4` (AD-021 M1) ------------------------------------------------

    def pick(self, x: float, y: float) -> ObjectId | None:
        """The object whose surface is front-most under the cursor - every object, References included (RF-3)."""
        services = self.services
        scene = services.scene
        candidates = []
        for oid, obj in scene.objects.items():
            if oid == scene.edit_object_id:
                cache = services.pick_cache
            else:
                cache = self.pick_caches.setdefault(oid, PickCache())
            candidates.append((oid, obj.mesh, cache, self.camera_for(obj), obj.transform.scale))
        width, height = services.viewport_size
        return pick_object(candidates, x, y, width, height)

    def select_at(self, command: str, x: float, y: float) -> bool:
        """A click in mode `4` (AD-021 M1): changes only the object selection. A plain click selects exactly this
        object (into empty space: none), Shift / Ctrl / Alt as for components. Q-12 revised (Manu 2026-10-16): Reference
        on / off is `Alt+R`. True = the selection changed."""
        services = self.services
        if self.gestures.session is not None:
            # M2-2: no selection or state change underneath a held W/E/R (its targets are fixed).
            return False
        selection = services.selection
        before_state = selection_state(selection)
        hit = self.pick(x, y)
        if hit is None:
            if command == commands.SELECT:
                selection.clear_objects()
        elif command == commands.SELECT:
            selection.set({hit})
        elif command == commands.SELECT_ADD:
            selection.add({hit})
        elif command == commands.SELECT_REMOVE:
            selection.remove({hit})
        elif command == commands.SELECT_TOGGLE:
            selection.toggle(hit)
        changed = selection_state(selection) != before_state
        if hit is not None and command == commands.SELECT:
            scene = services.scene
            obj = scene.objects[hit]
            if hit == scene.edit_object_id:
                services.status(f"Object {obj.name!r} selected (being edited)")
            elif obj.state is ObjectState.REFERENCE:
                services.status(f"Object {obj.name!r} selected (Reference - Alt+R makes it Normal)")
            else:
                services.status(f"Object {obj.name!r} selected - 1/2/3 edits it")
        self.sync_highlight()
        return changed

    # -- Reference on / off, Apply / Clear (AD-021 M1, M2-3) -----------------------------------------

    def reference_command(self) -> bool:
        """`Alt+R` in mode `4`: switch every selected object except the edit object Normal <-> Reference, one Undo step
        (Q-3; Q-12 revised 2026-10-16, key `PROVISIONAL`). The edit object never becomes a Reference (RF-2/RF-5)."""
        label = "Reference on/off"
        services = self.services
        if services.interaction_owner is not None:
            return False
        if services.selection.mode is not SelectionMode.OBJECT:
            services.status(f"{label}: works on objects - press 4 and select them")
            return False
        scene = services.scene
        selected = [scene.objects[oid] for oid in sorted(services.selection.objects) if oid in scene.objects]
        if not selected:
            services.status(f"{label}: no object selected - click one first")
            return False
        edit = scene.edit_object
        targets = [obj for obj in selected if obj.id != edit.id]
        if not targets:
            services.status(f"Object {edit.name!r} is being edited - it cannot become a Reference")
            return False
        before = services.selection_snapshot()
        if len(targets) == len(selected) == 1:
            return self.switch_state(targets[0].id, before)
        steps = []
        for obj in targets:
            old = obj.state
            new = ObjectState.NORMAL if old is ObjectState.REFERENCE else ObjectState.REFERENCE
            obj.state = new
            steps.append(ObjectStateCommand(obj, old, new))
        services.history.push(steps[0] if len(steps) == 1 else CompositeCommand(steps, label))
        services.record_selection_history(before, mesh_step=False)
        self.sync_views()
        text = ", ".join(f"{obj.name!r}: {obj.state.name.capitalize()}" for obj in targets)
        if len(targets) < len(selected):
            text += f" ({edit.name!r} is being edited - stays Normal)"
        services.status(f"Object {text}")
        return True

    def switch_state(self, object_id: ObjectId, selection_before: tuple) -> bool:
        """Normal <-> Reference as one Undo step (Q-3). The edit object never becomes a Reference (RF-2, RF-5)."""
        services = self.services
        obj = services.scene.objects[object_id]
        if object_id == services.scene.edit_object_id:
            services.status(f"Object {obj.name!r} is being edited - it cannot become a Reference")
            return False
        before = obj.state
        after = ObjectState.NORMAL if before is ObjectState.REFERENCE else ObjectState.REFERENCE
        obj.state = after
        services.history.push(ObjectStateCommand(obj, before, after))
        services.record_selection_history(selection_before, mesh_step=False)
        self.sync_views()
        services.status(f"Object {obj.name!r}: {after.name.capitalize()}")
        return True

    def mode_refusal(self, command: str | None) -> str | None:
        """`can_run` stage 4 (AD-021 M1, L-1, RF-4): the refusal text for component work in mode `4`. M2-2: W/E/R
        pass - in `4` they are the object gesture, which refuses on its own (`arm_gesture`: nothing selected, only
        References)."""
        if self.services.selection.mode is not SelectionMode.OBJECT or command not in COMPONENT_COMMANDS:
            return None
        if command in OBJECT_TRANSFORM_COMMANDS or command == commands.DELETE:
            return None  # Delete in `4` deletes the selected objects (`delete_selected`)
        return (
            "Object mode: T, G, S, I, Ctrl+B, C, Shift+C, Dissolve, Shift+L/R, Shift+S, Alt+M, Shift+arrows and Ctrl+/- work"
            " on points/edges/faces"
            " - press 1/2/3 (Delete removes the selected objects)"
        )

    def targets(self, label: str, hint: str) -> tuple[list[SceneObject], tuple[str, ...]] | None:
        """The selected objects an object command works on, and the names of the selected References it leaves alone
        (RF-4, Q-1). None (refusal posted) when nothing or only References are selected."""
        services = self.services
        scene = services.scene
        selected = [scene.objects[oid] for oid in sorted(services.selection.objects) if oid in scene.objects]
        targets = [obj for obj in selected if obj.state is not ObjectState.REFERENCE]
        references = tuple(obj.name for obj in selected if obj.state is ObjectState.REFERENCE)
        if not selected:
            services.status(f"{label}: no object selected - click one first ({hint})")
            return None
        if not targets:
            services.status(f"Object mode: {references[0]!r} is a Reference - locked (select or switch only)")
            return None
        return targets, references

    def placement_command(self, command: str) -> bool:
        """Apply / Clear transform (AD-021 M2-3, L-3) on the selected non-Reference objects, mode `4` only. Objects
        without a placement are left alone; one Undo step for all of them."""
        label = PLACEMENT_COMMANDS[command]
        services = self.services
        if services.interaction_owner is not None:
            return False
        if services.selection.mode is not SelectionMode.OBJECT:
            services.status(f"{label}: works on objects - press 4 and select them")
            return False
        picked = self.targets(label, "press 4 and click the object")
        if picked is None:
            return False
        targets, references = picked
        placed = [obj for obj in targets if not object_space.is_identity(obj.transform)]
        if not placed:
            services.status(f"{label}: nothing to do - {objects_text(targets)} not placed")
            return False
        paired = [obj for obj in placed if services.scene.mirror_pair_of(obj.id) is not None]
        if paired:
            # PROVISIONAL (proposal §5.7 / §9 decision 4): Apply/Clear would change the placement and the mesh/pivot
            # relation the pair assumes - refused in v1, the way out named.
            services.status(f"{label}: {paired[0].name!r} is in a mirror pair - break the pair first (Shift+M)")
            return False
        if command == commands.CLEAR_TRANSFORM:
            return self._clear_transform(placed, references)
        return self._apply_transform(placed, references)

    def _clear_transform(self, placed: list[SceneObject], references: tuple[str, ...]) -> bool:
        """Clear (L-3): placement back to identity, the mesh stays, the object jumps; the pivot stays. One
        `ObjectTransformCommand` (an object step, `mesh_step=False`)."""
        services = self.services
        before = services.selection_snapshot()
        changes = [(obj, obj.transform, IDENTITY_TRANSFORM) for obj in placed]
        for obj, _, after in changes:
            obj.transform = after
        services.history.push(ObjectTransformCommand(changes, "Clear transform"))
        services.record_selection_history(before, mesh_step=False)
        self.placement_changed()
        services.status(
            f"{objects_text(placed)}: transform cleared (object level, mesh unchanged){references_note(references)}"
        )
        return True

    def _apply_transform(self, placed: list[SceneObject], references: tuple[str, ...]) -> bool:
        """Apply (L-3, Max "Reset XForm"): every mesh position becomes its world position, the placement becomes
        identity, and the pivot moves to its old world position `t + c` (`PROVISIONAL`: a later Rotate/Scale turns
        about the same place as before; the alternative, pivot = origin, is a question for Manu). One
        `CompositeCommand` per press (E-13): a `MeshDeltaCommand` per object, then the transforms, then the pivots.
        Refused as a whole, before anything changes, when one object's symmetry definition would not survive the bake
        (`applied_symmetry_axis`), or when one object's mesh has point layers (AD-025 §4.4)."""
        if self.layer_refused(commands.APPLY_TRANSFORM, [obj.mesh for obj in placed]):
            return False
        services = self.services
        try:
            axes = [applied_symmetry_axis(obj) for obj in placed]
        except ApplyRefused as exc:
            services.status(f"Apply transform: refused - {exc}")
            return False
        before = services.selection_snapshot()
        parts: list = []
        transforms, pivots = [], []
        for obj, axis in zip(placed, axes):
            mesh = obj.mesh
            delta, _ = record_mesh_change(mesh, lambda obj=obj, axis=axis: apply_placement(obj, axis))
            parts.append(MeshDeltaCommand(mesh=mesh, delta=delta, description=f"Apply transform {obj.name!r}"))
            pivots.append((obj, obj.pivot, object_space.to_world(obj, obj.pivot)))
            transforms.append((obj, obj.transform, IDENTITY_TRANSFORM))
        for obj, _, after in transforms:
            obj.transform = after
        for obj, _, after in pivots:
            obj.pivot = after
        parts += [ObjectTransformCommand(transforms, "Apply transform"), ObjectPivotCommand(pivots)]
        services.history.push(CompositeCommand(parts, "Apply transform"))
        edit_id = services.scene.edit_object_id
        others = frozenset(obj.id for obj in placed if obj.id != edit_id)
        edit_changed = len(others) < len(placed)
        services.record_selection_history(before, mesh_step=edit_changed, object_meshes=others)
        self.meshes_changed(others)
        if edit_changed:
            services.notify_topology_changed()
        self.placement_changed()
        services.status(
            f"{objects_text(placed)}: transform applied (object level -> mesh;"
            f" placement is identity now){references_note(references)}"
        )
        return True

    # -- the object gesture (AD-021 M2-2, E-11/E-12) -------------------------------------------------

    def arm_gesture(self, command: str, key: str, origin) -> bool:
        """W/E/R in mode `4`: arm the object gesture on the selected objects without the References (RF-4, Q-1: locked;
        in a mixed selection they stay where they are and the status line says so, `PROVISIONAL`). Refused with a
        status line when nothing or only References are selected. Nothing moves before the first motion (AD-016)."""
        services = self.services
        label, verb, _ = TRANSFORM_COMMANDS[command]
        picked = self.targets(f"Object {label}", f"to {verb} points/edges/faces press 1/2/3")
        if picked is None:
            return False
        targets, references = picked
        paired = self._mirror_followers(f"Object {label}", targets)
        if paired is None:
            return False
        targets, followers = paired
        services.interaction.start(ObjectGesture(self, command, key, origin, targets, references, followers))
        constraint = self.gestures.axis_constraint
        if command == commands.SCALE:
            suffix = " (uniform - X/Y/Z do not apply)" if constraint else ""
        else:
            suffix = constraint_suffix(constraint)
        services.status(
            f"Object {label}: {', '.join(repr(obj.name) for obj in targets)}{suffix}"
            f"{mirror_note(followers)}{references_note(references)}{commit_hint(key)}"
        )
        return True

    # -- object material (AD-024 §6/§7, `PROVISIONAL` keys) ------------------------------------------

    def material_preview(self) -> SceneObject | None:
        """The object whose values the Look row shows (no status line): the edit object in `1/2/3`, the first selected
        non-Reference in `4` (None = none)."""
        services = self.services
        scene = services.scene
        if services.selection.mode is not SelectionMode.OBJECT:
            return scene.edit_object
        for oid in sorted(services.selection.objects):
            obj = scene.objects.get(oid)
            if obj is not None and obj.state is not ObjectState.REFERENCE:
                return obj
        return None

    def _material_targets(self, label: str) -> tuple[list[SceneObject], tuple[str, ...]] | None:
        """AD-024 §6: the selected objects in `4` (References skipped - locked, Q-M3), the edit object in `1/2/3`. None
        (refusal posted) while an interaction owns the keys or nothing can be edited."""
        services = self.services
        owner = services.interaction_owner
        if owner is not None or services.drag_select is not None:
            services.status(f"{label}: not while the {owner or 'selection'} interaction runs")
            return None
        if services.selection.mode is SelectionMode.OBJECT:
            return self.targets(label, "or press 1/2/3 for the edited object")
        return [services.scene.edit_object], ()

    def _commit_materials(self, changes: list) -> bool:
        """One Undo step for `(obj, before, after)` (unchanged ones dropped) and the view; the caller posts the status
        line. True = something changed."""
        changes = [(obj, before, after) for obj, before, after in changes if before != after]
        if not changes:
            return False
        services = self.services
        before = services.selection_snapshot()
        for obj, _, after in changes:
            obj.material = after
        names = ", ".join(repr(obj.name) for obj, _, _ in changes)
        services.history.push(ObjectMaterialCommand(changes, f"Material {names}"))
        services.record_selection_history(before, mesh_step=False)
        self.sync_views()
        return True

    def set_material(self, **changes) -> bool:
        """Any of `base_color`, `specular`, `glossiness`, clamped to [0, 1], set on every target; one Undo step. True =
        a material changed. An object without a material starts from the default look."""
        values = clamp_material_values(changes)
        picked = self._material_targets("Material")
        if picked is None:
            return False
        targets, references = picked
        default = self.services.display.surface_finish
        planned = []
        for obj in targets:
            current = editable_material(obj, default)
            after = ObjectMaterial(
                values.get("base_color", current.base_color),
                specular=values.get("specular", current.specular),
                glossiness=values.get("glossiness", current.glossiness),
            )
            planned.append((obj, obj.material, after))
        changed = self._commit_materials(planned)
        self.services.status(("Material set" if changed else "Material unchanged") + references_note(references))
        return changed

    def step_material(self, row_id: str, direction: int, fine: bool = False) -> bool:
        """One value step of the material row `row_id` on every target, each from its own values
        (`look_controls.MATERIAL_ROWS`); one Undo step. True = a material changed."""
        row = material_row(row_id)
        picked = self._material_targets(row.label)
        if picked is None:
            return False
        services = self.services
        targets, references = picked
        default = services.display.surface_finish
        planned = []
        for obj in targets:
            current = editable_material(obj, default)
            if row.applies(current):
                planned.append((obj, obj.material, row.step(current, direction, fine)))
        if not planned:
            services.status(f"{row.label} inaktiv - {row.inactive_reason}")
            return False
        changed = self._commit_materials(planned)
        shown = editable_material(planned[0][0], default)
        suffix = "" if changed else " (Grenze)"
        names = ", ".join(repr(obj.name) for obj, _, _ in planned)
        services.status(f"{row.label} {row.format(shown)}{suffix} - {names}" + references_note(references))
        return changed
