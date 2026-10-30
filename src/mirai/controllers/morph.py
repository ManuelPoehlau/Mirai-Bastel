"""MorphController (AD-027 §3.4): the morph targets of the edit object (AD-025 Phase 3/4, `mirai.morph_targets`;
keys and texts `PROVISIONAL`) - their lifecycle (new / rename / delete, one Undo step each), the current target and
its weight (view state), the A/B tap, the editing view of a target beside its base with its history translation,
and the weight drag as a hold key (`MorphWeightHold`, N held).

Behaviour as it was inside `Application` (AD-027 M4 moves it, nothing else). The editing view is a **mode**, not a
session: it owns no input, `can_run` stage 3 reads it (`view_refusal`: on a target's editing view only shapes change,
AD-025 §15).
"""

from __future__ import annotations

import dataclasses
from typing import Optional

from core import Mesh, PointLayerInfo, Scene, SceneObject, SelectionMode

from ..interaction import commands
from ..interaction.session import PASS, Motion, Outcome
from ..layer_declarations import view_refusal
from ..morph_targets import (
    DRAG_PIXELS_PER_PERCENT as MORPH_DRAG_PIXELS_PER_PERCENT,
    MAX_TARGETS as MORPH_MAX_TARGETS,
    MAX_WEIGHT as MORPH_MAX_WEIGHT,
    MIN_WEIGHT as MORPH_MIN_WEIGHT,
    WEIGHT_STEPS as MORPH_WEIGHT_STEPS,
    MorphDisplay,
    TargetView,
    TranslatingHistory,
    morph_target_ids,
    new_target_name,
    next_target_name,
    view_placement,
    view_state,
    world_width,
)
from .services import AppServices


class MorphWeightHold:
    """`N` held (a hold key, AD-027 §3.2): mouse motion left/right sets the current target's weight until it is
    let go; a tap without motion toggles 0 % <-> the last weight. View state only. One object per app: its key,
    whether the hold moved and the sub-percent rest survive a second press of a key bound to the same command."""

    command = commands.MORPH_WEIGHT_DRAG

    def __init__(self, controller: "MorphController") -> None:
        self._controller = controller
        self.key: str | None = None
        self.moved = False
        self.rest = 0.0

    def arm(self, key: str) -> bool:
        controller = self._controller
        if controller.current_target is None:
            controller.services.status("Morph weight: this mesh has no target (Ctrl+N makes one)")
            return False
        if self.key is None:
            self.moved = False
            self.rest = 0.0
            controller.services.status(
                f"Morph: move the mouse left/right for the weight ({controller.weight} %), release N"
            )
        self.key = key
        controller.services.interaction.hold(self)
        return True

    def claims(self, event) -> Outcome:
        return PASS

    def background(self, event) -> Outcome:
        if not isinstance(event, Motion):
            return PASS
        total = self.rest + event.dx / MORPH_DRAG_PIXELS_PER_PERCENT
        steps = int(total)
        self.rest = total - steps
        if steps == 0:
            return False
        self.moved = True
        controller = self._controller
        return controller.set_weight(controller.weight + steps)

    def release(self) -> bool:
        self.key = None
        self._controller.services.interaction.unhold(self)
        if not self.moved:
            return self._controller.toggle_ab()
        return True


class MorphController:
    """The morph cluster: `display` (the mix and its provider, public as `Application.morph`), the open editing view
    (`view`, None = none) and the camera shift it was opened with, the weight a tap returns to per
    (ObjectId, LayerId) (`ab`), and the weight drag (`weight_hold`)."""

    def __init__(self, services: AppServices) -> None:
        self.services = services
        # AD-025 Phase 3 (`mirai.morph_targets`): the weight per object and the mix display (view state: no
        # History, not saved).
        self.display = MorphDisplay(lambda: services.scene, services.status)
        self.view: TargetView | None = None
        self.view_shift: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.ab: dict[tuple, int] = {}  # (ObjectId, LayerId) -> the weight a tap returns to
        self.weight_hold = MorphWeightHold(self)

    # -- reads (the public `morph_*` API of `Application`) ---------------------------------------------

    @property
    def document_object(self) -> SceneObject:
        """The object the document means by "the edit object": the base while its target's editing view is open
        (the view is transient: never saved, exported or sent), else the edit object."""
        view = self.view
        return view.base_obj if view is not None else self.services.scene.edit_object

    @property
    def current_target(self):
        """The document edit object's current target (AD-025 Phase 4: the one Tab, N and +/- act on; view state),
        or None."""
        return self.display.provider.current_target(self.document_object.id)

    @property
    def weight(self) -> int:
        """The weight of the document edit object's current target in whole percent (view state)."""
        return self.display.provider.weight(self.document_object.id)

    def status_text(self) -> str | None:
        """The HUD's morph row (the current target): None = the document edit object has no target."""
        obj = self.document_object
        lid = self.current_target
        if lid is None:
            return None
        ids = morph_target_ids(obj.mesh)
        name = obj.mesh.point_layer_info(lid).name
        where = "editing target (beside the base)" if self.view is not None else "base"
        text = f"{name} · {self.weight} % · {where}"
        if len(ids) > 1:
            text += f" · {ids.index(lid) + 1}/{len(ids)}"
        if self.display.blocked:
            text += " · mix hidden (another host holds the surface)"
        return text

    def targets_text(self, limit: int = 8) -> str | None:
        """The HUD's targets row (AD-025 Phase 4, `PROVISIONAL`): every target with its weight in display order,
        the current one in brackets; None with fewer than two targets."""
        obj = self.document_object
        ids = morph_target_ids(obj.mesh)
        if len(ids) < 2:
            return None
        provider, current = self.display.provider, self.current_target
        parts = []
        for lid in ids:
            entry = f"{obj.mesh.point_layer_info(lid).name} {provider.weight(obj.id, lid)}"
            parts.append(f"[{entry}]" if lid == current else entry)
        if len(parts) > limit:
            at = ids.index(current)
            start = max(0, min(at - limit // 2, len(parts) - limit))
            shown = parts[start:start + limit]
            more = len(parts) - limit
            return " · ".join(shown) + f" · +{more} more"
        return " · ".join(parts)

    def document_scene(self) -> Scene:
        """The scene as a file holds it: without a target's editing view, the base as the edit object."""
        view = self.view
        scene = self.services.scene
        if view is None or view.view_obj.id not in scene.objects:
            return scene
        objects = [obj for oid, obj in scene.objects.items() if oid != view.view_obj.id]
        return Scene.from_objects(
            objects,
            edit_object_id=view.base_obj.id,
            object_id_counter=scene.object_id_counter,
            mirror_pairs=scene.mirror_pairs,
        )

    def view_refusal(self, key) -> Optional[str]:
        """`can_run` stage 3, the editing view's part (AD-025 §15): on a target's editing view only shapes change
        (`layer_declarations.view_refusal`); None without a view."""
        return None if self.view is None else view_refusal(key)

    # -- commands --------------------------------------------------------------------------------------

    def command(self, command: str) -> bool:
        if command == commands.MORPH_NEW:
            return self.create_target() is not None
        if command == commands.MORPH_RENAME:
            return self.rename_target()
        if command == commands.MORPH_DELETE:
            return self.delete_target()
        if command == commands.MORPH_EDIT_TOGGLE:
            return self.leave_target() if self.view is not None else self.edit_target()
        if command == commands.MORPH_WEIGHT_DRAG:
            return self.toggle_ab()
        if command in MORPH_WEIGHT_STEPS:
            return self.set_weight(self.weight + MORPH_WEIGHT_STEPS[command])
        if command == commands.MORPH_WEIGHT_FULL:
            return self.set_weight(MORPH_MAX_WEIGHT)
        if command == commands.MORPH_WEIGHT_ZERO:
            return self.set_weight(MORPH_MIN_WEIGHT)
        if command in (commands.MORPH_NEXT, commands.MORPH_PREVIOUS):
            return self.step_target(1 if command == commands.MORPH_NEXT else -1)
        return False

    def _lifecycle_refuses(self, label: str) -> bool:
        """New / rename / delete run on the base, outside every interaction (one Undo step each)."""
        services = self.services
        owner = services.interaction_owner
        if owner is not None:
            services.status(f"{label}: not while the {owner} interaction runs")
            return True
        if self.view is not None:
            services.status(f"{label}: on the base only (Tab returns to it)")
            return True
        return False

    def create_target(self, name: str | None = None):
        """A new target on the edit object's mesh, equal to its current shape (all offsets zero): one Undo step, a
        layer-only mesh transaction; it becomes the current target (view state). At most `MAX_TARGETS` per mesh.
        Returns the new `LayerId` or None (refused, status set)."""
        services = self.services
        label = "New morph target"
        if self._lifecycle_refuses(label):
            return None
        mesh = services.scene.mesh
        if len(morph_target_ids(mesh)) >= MORPH_MAX_TARGETS:
            services.status(f"{label}: this mesh has {MORPH_MAX_TARGETS} targets, the most it can have")
            return None
        name = name or new_target_name(mesh)
        done = services.mesh_transaction(
            f"New morph target {name!r}", lambda m: m.add_point_layer(PointLayerInfo(name)), moved_of=lambda _: set()
        )
        self.display.provider.set_current(services.scene.edit_object_id, done.result)
        count = len(morph_target_ids(mesh))
        services.status(
            f"Morph target {name!r} created (= the current shape, {count} on this mesh). Tab edits it beside the base,"
            " N / +/- set its weight, Shift+N / Alt+N switch targets"
        )
        return done.result

    def rename_target(self, name: str | None = None) -> bool:
        """Renames the edit object's target (one Undo step); without `name` the next name of
        `morph_targets.RENAME_CYCLE` (the app has no text field yet)."""
        services = self.services
        label = "Rename morph target"
        if self._lifecycle_refuses(label):
            return False
        mesh = services.scene.mesh
        lid = self.current_target
        if lid is None:
            services.status(f"{label}: this mesh has no target (Ctrl+N makes one)")
            return False
        info = mesh.point_layer_info(lid)
        new = name or next_target_name(mesh, info.name)
        if not new or new == info.name or new in {mesh.point_layer_info(x).name for x in mesh.point_layer_ids()}:
            services.status(f"{label}: {new!r} is not a free name")
            return False
        services.mesh_transaction(
            f"Rename morph target {info.name!r} {new!r}",
            lambda m: m.set_point_layer_info(lid, dataclasses.replace(info, name=new)),
            moved_of=lambda _: set(),
        )
        services.status(f"Morph target {info.name!r} is now {new!r} (again: next name)")
        return True

    def delete_target(self) -> bool:
        """Deletes the edit object's current target with its offsets (one Undo step; Undo brings it back exactly).
        Its weight goes with it; the next target in the list becomes current."""
        services = self.services
        label = "Delete morph target"
        if self._lifecycle_refuses(label):
            return False
        mesh = services.scene.mesh
        lid = self.current_target
        if lid is None:
            services.status(f"{label}: this mesh has no target")
            return False
        ids = morph_target_ids(mesh)
        at = ids.index(lid)
        neighbour = ids[at + 1] if at + 1 < len(ids) else (ids[at - 1] if at > 0 else None)
        name = mesh.point_layer_info(lid).name
        oid = services.scene.edit_object_id
        provider = self.display.provider
        provider.set_weight(oid, MORPH_MIN_WEIGHT, lid)
        self.ab.pop((oid, lid), None)
        services.mesh_transaction(f"Delete morph target {name!r}", lambda m: m.remove_point_layer(lid), moved_of=lambda _: set())
        if neighbour is not None:
            provider.set_current(oid, neighbour)
        self.display.refresh()
        services.status(f"Morph target {name!r} deleted (Ctrl+Z brings it back)")
        return True

    def step_target(self, step: int) -> bool:
        """AD-025 Phase 4 (keys `PROVISIONAL`): the next / previous target of the document edit object becomes
        current (view state, no Undo step). With the editing view open, the view shows it."""
        services = self.services
        obj = self.document_object
        ids = morph_target_ids(obj.mesh)
        if not ids:
            services.status("Morph targets: this mesh has none (Ctrl+N makes one)")
            return False
        owner = services.interaction_owner
        if owner is not None:
            services.status(f"Morph targets: not while the {owner} interaction runs")
            return False
        if len(ids) == 1:
            services.status(f"Morph: {self.status_text()} (the only target; Ctrl+N makes another)")
            return False
        lid = ids[(ids.index(self.current_target) + step) % len(ids)]
        self.display.provider.set_current(obj.id, lid)
        view = self.view
        if view is not None:
            moved = view.retarget(lid)
            view.view_obj.name = f"{obj.name} · {view.name}"
            if moved and services.viewport is not None:
                services.invalidate_picks()
                services.notify_vertices_moved(moved)
            services.soft_preview_refresh()
            services.refresh_hover()
        services.status(f"Morph: {self.status_text()}")
        return True

    def set_weight(self, weight: int, lid=None) -> bool:
        """The weight of a target of the document edit object (default: the current one); view state: no Undo
        step, not saved."""
        obj = self.document_object
        lid = self.current_target if lid is None else lid
        if lid is None:
            self.services.status("Morph weight: this mesh has no target (Ctrl+N makes one)")
            return False
        weight = self.display.provider.set_weight(obj.id, weight, lid)
        if weight > MORPH_MIN_WEIGHT:
            self.ab[(obj.id, lid)] = weight
        self.display.refresh()
        self.services.status(f"Morph: {self.status_text()}")
        return True

    def toggle_ab(self) -> bool:
        obj = self.document_object
        last = self.ab.get((obj.id, self.current_target), MORPH_MAX_WEIGHT)
        return self.set_weight(last if self.weight == MORPH_MIN_WEIGHT else MORPH_MIN_WEIGHT)

    # -- the editing view (H4, AD-025 §15) -------------------------------------------------------------

    def edit_target(self) -> bool:
        """Tab on the base (H4, AD-025 §15): the target's editing view beside the base becomes the edit object - an
        ID-identical copy at `b + d` (`morph_targets.view_state`), placed beside the base. The component selection
        carries over (same IDs); the camera follows by the same offset, so the shape stays where it was on screen.
        No Undo step (view state, like switching objects)."""
        services = self.services
        label = "Edit morph target"
        owner = services.interaction_owner
        if owner is not None:
            services.status(f"{label}: not while the {owner} interaction runs")
            return False
        if self.view is not None:
            services.status(f"{label}: the target is being edited already (Tab returns to the base)")
            return False
        if services.selection.mode is SelectionMode.OBJECT:
            services.status(f"{label}: works from points/edges/faces - press 1/2/3")
            return False
        scene = services.scene
        base = scene.edit_object
        lid = self.display.provider.current_target(base.id)
        if lid is None:
            services.status(f"{label}: this mesh has no target (Ctrl+N makes one)")
            return False
        name = base.mesh.point_layer_info(lid).name
        view_obj = scene.add_object(
            Mesh.from_state(view_state(base.mesh, lid)), name=f"{base.name} · {name}", texture=base.texture
        )
        view_obj.transform = view_placement(base, world_width(base, base.mesh))
        view_obj.pivot = base.pivot
        view_obj.material = base.material
        self.view = TargetView(base, lid, view_obj)
        services.history.translate = self._translate
        shift = tuple(view_obj.transform.translation[i] - base.transform.translation[i] for i in range(3))
        self.view_shift = shift
        services.set_edit_object(view_obj.id)
        self._pan(shift)
        services.soft_preview_refresh()
        services.refresh_hover()
        services.status(
            f"Editing morph target {name!r} beside the base: W/E/R, Tweak, Soft, Smooth shape it"
            " (topology on the base only) - Tab returns to the base"
        )
        return True

    def leave_target(self) -> bool:
        """Tab on the editing view: the base is the edit object again; the view closes (`close_if_left`) and the
        camera follows back."""
        services = self.services
        view = self.view
        if view is None:
            services.status("Back to the base: no morph target is being edited")
            return False
        owner = services.interaction_owner
        if owner is not None:
            services.status(f"Back to the base: not while the {owner} interaction runs")
            return False
        services.set_edit_object(view.base_obj.id)
        services.soft_preview_refresh()
        services.refresh_hover()
        services.status(f"Base {view.base_obj.name!r} (target {view.name!r} at {self.weight} %)")
        return True

    def _pan(self, shift) -> None:
        services = self.services
        cam = services.camera
        cam.target = tuple(cam.target[i] + shift[i] for i in range(3))
        cam.camera_revision += 1
        if services.viewport is not None:
            width, height = services.viewport_size
            services.viewport.on_camera_changed(width / height)

    def close_if_left(self):
        """Closes the editing view once it is no longer the edit object (Tab, an Undo that brings back another edit
        object, a scene load). Back on its base, the camera follows back. Returns the closed view object's id (the
        app drops its mask and hidden set), None when nothing closed."""
        view = self.view
        scene = self.services.scene
        if view is None or scene.edit_object_id == view.view_obj.id:
            return None
        self.drop_view()
        if view.view_obj.id in scene.objects:
            scene.remove_object(view.view_obj.id)
        if scene.edit_object_id == view.base_obj.id:
            self._pan(tuple(-c for c in self.view_shift))
        return view.view_obj.id

    def drop_view(self) -> None:
        view = self.view
        if view is None:
            return
        view.close()
        self.view = None
        history = self.services.history
        if isinstance(history, TranslatingHistory):
            history.translate = None

    def _translate(self, command):
        """`TranslatingHistory.translate` while the editing view is open (module `morph_targets`)."""
        services = self.services
        kept, refusal, moved = self.view.translate(command)
        if refusal is not None:
            services.status(refusal)
            services.invalidate_picks()
            if services.viewport is not None:
                services.viewport.on_topology_changed()
        elif moved and services.viewport is not None:
            services.invalidate_picks()
            services.notify_vertices_moved(moved)
        return kept

    def after_history(self) -> None:
        """After Undo / Redo: the open view follows its base's offsets (or closes with its target)."""
        services = self.services
        view = self.view
        if view is None:
            return
        if not view.target_alive():
            services.set_edit_object(view.base_obj.id)
            return
        moved = view.sync_from_base()
        if services.viewport is None:
            return
        services.invalidate_picks()
        if moved is None:
            services.viewport.on_topology_changed()
        elif moved:
            services.notify_vertices_moved(moved)
