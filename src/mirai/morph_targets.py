"""Morph targets in Production (AD-025 Phases 3 and 4, ARCH-02): several persistent targets per mesh.
Names, keys and texts `PROVISIONAL`.

What a target is: one vector point layer of the base mesh (`core.Mesh` point layers, AD-025 §4.2) —
offsets keyed by `VertexId` (Manu J-3 "relativ": the target follows later base edits). The Core owns
the values, their journal, Undo and the file; this module gives them their meaning:

- **Lifecycle** (`Application.create_morph_target` / `rename_` / `delete_`): one Undo step each, a
  layer-only `_mesh_transaction`. Phase 4: up to `MAX_TARGETS` per mesh; one of them is the
  **current target** (`MorphSurfaceProvider.current`, view state) that Tab, `N` and `+`/`-` act on,
  switched with `MORPH_NEXT` / `MORPH_PREVIOUS`; a new target becomes current.
- **Weight** (`MorphSurfaceProvider.weights`): view state per object and target in whole percent — no
  Undo step, not saved (F-11, Manu 2026-10-17). The viewport shows the additive mix `b + Σ wᵢ·dᵢ`
  (`morph_mix`, the evaluation rule and its drift guard) through the H7 replacement surface: the edit
  object's faces (`surface_mesh`) and, H7-E, object entries (`entry_surfaces`, the base beside the
  editing view). The wire follows the mix (`wire_follows_surface`, Manu 2026-10-27); picking,
  selection, hover and every tool stay on the rest shape (H7: the cage is authoritative; Morph Lab 6a:
  "hilft"). Morph + SubD together (H5b, Phase 4): the provider is the first stage of the app's
  `surface_chain.SurfaceChain`, the SubD preview reads the mixed cage (`MorphDisplay`).
- **Editing view** (H4, the §11 "editing-view mechanics" decided here, AD-025 §15): `TargetView`.
  The target is edited *beside* the base, as in the Morph Lab (J-5): a transient scene object whose
  mesh is an ID-identical copy of the base with positions `b + d`, placed beside the base, becomes
  the edit object. Every app tool runs on it unchanged (W/E/R, Tweak, Soft, Symmetry, Smooth, Relax,
  Loop Slide, Re-Symmetrize). It is never a document: never saved, never in the history. Every
  history push while it is open goes through `TranslatingHistory`: the view's change journal
  (`Mesh.watch`, keys only) names the points the gesture touched, their new offsets `p − b` are
  written into the base's layer in **one** recording, and that `MeshDeltaCommand` on the base mesh is
  what History keeps (F-8: a gesture on the view is not a position write; only touched points are
  written). The view's command itself is dropped — the view already shows its result; the view is
  then re-derived as `b + d` on those points (the definition, exact). Undo / Redo change the base's
  layer and the view follows (`TargetView.sync_from_base`). Anything on the view that is not a
  position change is refused before it runs by the view gate (`layer_declarations.view_refusal`:
  topology only on the base); `translate` is the fail-closed backstop (it reverts such a change).
  The view lives while it is the edit object: an Undo that brings back another edit object, `4`
  (refused), a scene load or the toggle key close it.

The module depends on `core` only (plus `interaction` for the keys); `Application` wires it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from core import HistoryStack, Mesh
from core.mesh import LayerKind
from core.operations import MeshDeltaCommand, record_mesh_change

from .morph_mix import MixSurface, mix_position, offset_keys as _offset_keys, rest_state as _rest_state
from .morph_mix import topology_touched as _topology_touched

from .interaction import commands
from .interaction.input import (
    GLOBAL_CONTEXT,
    KNIFE_CONTEXT,
    MORPH_CONTEXT,
    SUBD_CONTEXT,
    TOPOLOGY_CONTEXT,
    BindingSet,
    Input,
)

#: AD-025 Phase 4: several targets per mesh, capped (`PROVISIONAL`): above the audit's 20-50 per character, under
#: what the HUD and the measured budget (50 targets <= 50 MB at 20k, AD-025 §17) can carry.
MAX_TARGETS = 64
#: New targets are called "Target 1", "Target 2", ... (first free number).
NEW_TARGET_PREFIX = "Target"
#: What MORPH_RENAME cycles through (the app has no text field yet; `rename_morph_target(name)`
#: takes any name for a later one). `PROVISIONAL`.
RENAME_CYCLE = ("Smile", "Blink", "Jaw open", "Brow up", "Frown", "Pucker", "Cheek puff", "Sneer")
#: Weight range and steps in whole percent (Morph Lab F-8: exact at 0 % and 100 %).
MIN_WEIGHT, MAX_WEIGHT = 0, 100
WEIGHT_STEP, WEIGHT_FINE_STEP = 10, 1
#: Hold-key weight drag (Manu J-4 "Schieberegler", without window UI yet): pixels per percent.
DRAG_PIXELS_PER_PERCENT = 3.0
#: Centre distance of the editing view from the base, in widths of the base's world bounds, along +X.
VIEW_SPACING = 1.25

_ZERO = (0.0, 0.0, 0.0)


# -- names and reading ------------------------------------------------------------------------------


def morph_target_ids(mesh: Mesh) -> list:
    """The mesh's morph targets: its vector point layers, in display order."""
    return [lid for lid in mesh.point_layer_ids() if mesh.point_layer_info(lid).kind is LayerKind.VECTOR]


def morph_target(mesh: Mesh):
    """The mesh's first target, or None (the app works with its current one, `MorphSurfaceProvider.current_target`)."""
    ids = morph_target_ids(mesh)
    return ids[0] if ids else None


def target_name(mesh: Mesh, lid) -> str:
    return mesh.point_layer_info(lid).name


def new_target_name(mesh: Mesh) -> str:
    taken = {mesh.point_layer_info(lid).name for lid in mesh.point_layer_ids()}
    n = 1
    while f"{NEW_TARGET_PREFIX} {n}" in taken:
        n += 1
    return f"{NEW_TARGET_PREFIX} {n}"


def next_target_name(mesh: Mesh, current: str) -> Optional[str]:
    """The next free name of `RENAME_CYCLE` after `current` (from the start for any other name)."""
    taken = {mesh.point_layer_info(lid).name for lid in mesh.point_layer_ids()} - {current}
    start = RENAME_CYCLE.index(current) + 1 if current in RENAME_CYCLE else 0
    for i in range(len(RENAME_CYCLE)):
        name = RENAME_CYCLE[(start + i) % len(RENAME_CYCLE)]
        if name not in taken and name != current:
            return name
    return None


def clamp_weight(weight: int) -> int:
    return max(MIN_WEIGHT, min(MAX_WEIGHT, int(weight)))


def blend(b, d, weight: int) -> tuple:
    """One target's evaluated position: `b` at 0 %, exactly `b + d` at 100 %, else `b + w·d` (exact where
    the offset is zero, exactly mirrored for mirrored inputs). Several targets: `morph_mix.mix_position`,
    which equals this for one."""
    if weight <= MIN_WEIGHT:
        return tuple(b)
    return mix_position(b, [(1.0 if weight >= MAX_WEIGHT else weight / 100.0, d)])


# -- keys (context `morph`, PROVISIONAL) -------------------------------------------------------------


@dataclass(frozen=True)
class MorphKey:
    input: Input
    command: str
    label: str


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


#: Engineering keys, not Artist Input Truth. They avoid every app key and every Morph Lab key
#: (`experiments/morph_lab/lab_app.LAB_KEYS`: M, Alt+B, `,` `.`, J, Alt/Ctrl+arrows), so the Lab, which
#: runs this `Application`, still starts.
MORPH_KEYS: tuple[MorphKey, ...] = (
    MorphKey(_key("n", "ctrl"), commands.MORPH_NEW, "Morph-Ziel: neu (aus der Form des Edit-Objekts)"),
    MorphKey(_key("n", "ctrl", "shift"), commands.MORPH_RENAME, "Morph-Ziel: nächster Name"),
    MorphKey(_key("n", "alt", "shift"), commands.MORPH_DELETE, "Morph-Ziel: löschen"),
    MorphKey(_key("tab"), commands.MORPH_EDIT_TOGGLE, "Ziel daneben bearbeiten <-> zurück zur Basis"),
    MorphKey(_key("n"), commands.MORPH_WEIGHT_DRAG, "Gewicht: N halten + Maus links/rechts; antippen = 0 % <-> zuletzt"),
    MorphKey(_key("plus"), commands.MORPH_WEIGHT_UP, f"Gewicht +{WEIGHT_STEP} %"),
    MorphKey(_key("minus"), commands.MORPH_WEIGHT_DOWN, f"Gewicht -{WEIGHT_STEP} %"),
    MorphKey(_key("plus", "shift"), commands.MORPH_WEIGHT_UP_FINE, f"Gewicht +{WEIGHT_FINE_STEP} %"),
    MorphKey(_key("minus", "shift"), commands.MORPH_WEIGHT_DOWN_FINE, f"Gewicht -{WEIGHT_FINE_STEP} %"),
    MorphKey(_key("plus", "alt"), commands.MORPH_WEIGHT_FULL, "Gewicht 100 %"),
    MorphKey(_key("minus", "alt"), commands.MORPH_WEIGHT_ZERO, "Gewicht 0 %"),
    MorphKey(_key("n", "shift"), commands.MORPH_NEXT, "Nächstes Ziel (Tab, N und +/- wirken auf das aktuelle)"),
    MorphKey(_key("n", "alt"), commands.MORPH_PREVIOUS, "Voriges Ziel"),
)
MORPH_COMMANDS = frozenset(entry.command for entry in MORPH_KEYS)
#: Weight commands: view state (ignored under a held W/E/R, like the mode keys).
WEIGHT_COMMANDS = frozenset(
    {
        commands.MORPH_WEIGHT_UP, commands.MORPH_WEIGHT_DOWN, commands.MORPH_WEIGHT_UP_FINE,
        commands.MORPH_WEIGHT_DOWN_FINE, commands.MORPH_WEIGHT_FULL, commands.MORPH_WEIGHT_ZERO,
    }
)
WEIGHT_STEPS = {
    commands.MORPH_WEIGHT_UP: WEIGHT_STEP,
    commands.MORPH_WEIGHT_DOWN: -WEIGHT_STEP,
    commands.MORPH_WEIGHT_UP_FINE: WEIGHT_FINE_STEP,
    commands.MORPH_WEIGHT_DOWN_FINE: -WEIGHT_FINE_STEP,
}

#: Contexts `Application` resolves before this one; a morph key bound there would be unreachable.
_EARLIER_CONTEXTS = (GLOBAL_CONTEXT, KNIFE_CONTEXT, TOPOLOGY_CONTEXT, SUBD_CONTEXT)


class MorphBindingConflict(RuntimeError):
    """A morph default key is already bound in a context the app resolves first."""


def install_morph_bindings(bindings: BindingSet) -> None:
    conflicts = []
    for entry in MORPH_KEYS:
        for context in _EARLIER_CONTEXTS:
            bound = bindings.command_for(entry.input, context)
            if bound is not None:
                conflicts.append(f"{entry.input} is bound to {bound!r} in {context!r}")
    if conflicts:
        raise MorphBindingConflict("Morph keys not free: " + "; ".join(conflicts))
    for entry in MORPH_KEYS:
        bindings.set_default(entry.input, entry.command, context=MORPH_CONTEXT)


# -- history ---------------------------------------------------------------------------------------


class TranslatingHistory(HistoryStack):
    """The app's `HistoryStack` with one hook (Core `history.py` unchanged): while `translate` is set
    (an editing view is open) every pushed command goes through it first; it returns the command to
    keep or None (nothing is kept - `swallowed` tells the caller's selection mirror, which records one
    entry per push, to skip this one)."""

    def __init__(self) -> None:
        super().__init__()
        self.translate: Optional[Callable] = None
        self.swallowed = False

    def push(self, command) -> None:
        self.swallowed = False
        if self.translate is not None:
            command = self.translate(command)
            if command is None:
                self.swallowed = True
                return
        super().push(command)


# -- editing view (H4) -----------------------------------------------------------------------------


def view_state(base: Mesh, lid) -> dict:
    """The editing view's mesh state: the base's topology and IDs, positions `b + d`, no layers."""
    state = _rest_state(base)
    vertices = state["vertices"]
    for vid, d in base.layer_items(lid):
        p = vertices[int(vid)]
        vertices[int(vid)] = [p[0] + d[0], p[1] + d[1], p[2] + d[2]]
    return state


class TargetView:
    """One open editing view: the base object, its target, the transient view object and the two
    change journals (keys only) that connect them (module docstring)."""

    def __init__(self, base_obj, lid, view_obj) -> None:
        self.base_obj = base_obj
        self.lid = lid
        self.view_obj = view_obj
        self._base_watch = base_obj.mesh.watch()
        self._view_watch = view_obj.mesh.watch()
        #: what the last `translate` wrote (points) - for the status line and the tests
        self.last_written = 0

    @property
    def base_mesh(self) -> Mesh:
        return self.base_obj.mesh

    @property
    def view_mesh(self) -> Mesh:
        return self.view_obj.mesh

    @property
    def name(self) -> str:
        return target_name(self.base_mesh, self.lid)

    def close(self) -> None:
        self._base_watch.close()
        self._view_watch.close()

    def target_alive(self) -> bool:
        return self.lid in self.base_mesh.point_layer_ids()

    def retarget(self, lid) -> set:
        """AD-025 Phase 4: the view shows another target of the same base (`b + d` of `lid`): same
        topology and IDs, only positions change. Returns the moved view vertices."""
        self._view_watch.take()
        self._base_watch.take()
        self.lid = lid
        moved = self._rederive(self.base_mesh.all_vertex_ids())
        self._view_watch.take()
        return moved

    def translate(self, command) -> tuple:
        """(command to keep or None, refusal text or None, view vertices re-derived). See module."""
        change = self._view_watch.take()
        if change.is_empty():
            return command, None, set()
        view, base, lid = self.view_mesh, self.base_mesh, self.lid
        if (
            _topology_touched(change, view)
            or change.symmetry_touched
            or change.regions_touched
            or change.layers_touched
            or not self.target_alive()
        ):
            command.undo()  # fail-closed: the view goes back to b + d, nothing is kept
            self._view_watch.take()
            return None, "Target editing: only shapes change on the target - topology only on the base", set()
        touched = sorted(change.vertices)

        def write() -> None:
            for vid in touched:
                p, b = view.vertex_position(vid), base.vertex_position(vid)
                base.set_layer_value(lid, vid, (p[0] - b[0], p[1] - b[1], p[2] - b[2]))

        delta, _ = record_mesh_change(base, write)
        moved = self._rederive(touched)
        self._view_watch.take()
        self._base_watch.take()
        self.last_written = len(delta.layer_values.get(lid, ()))
        if delta.empty:
            return None, None, moved
        description = f"{getattr(command, 'description', 'Edit')} · target {self.name!r}"
        return MeshDeltaCommand(mesh=base, delta=delta, description=description), None, moved

    def _rederive(self, vids) -> set:
        """View position = `b + d` on `vids` (the definition, bit-exact); returns the ones that moved."""
        view, base, lid = self.view_mesh, self.base_mesh, self.lid
        moved = set()
        for vid in vids:
            if not base.is_valid_vertex(vid):
                continue
            b, d = base.vertex_position(vid), base.layer_value(lid, vid)
            exact = (b[0] + d[0], b[1] + d[1], b[2] + d[2])
            if tuple(view.vertex_position(vid)) != exact:
                view.set_vertex_position(vid, exact)
                moved.add(vid)
        return moved

    def sync_from_base(self) -> Optional[set]:
        """Brings the view to `b + d` after the base changed (Undo / Redo of an offset write or of an
        older step). Returns the moved view vertices, or None when the topology was rebuilt."""
        change = self._base_watch.take()
        if change.is_empty() or not self.target_alive():
            return set()
        view, base = self.view_mesh, self.base_mesh
        if _topology_touched(change, base):
            view.load_state(view_state(base, self.lid))
            self._view_watch.take()
            return None
        if change.symmetry_touched:
            view.symmetry_definition = base.symmetry_definition
        if change.regions_touched:
            view.face_regions = base.face_regions
        keys = _offset_keys(change, self.lid)
        vids = set(change.vertices) | (set(base.all_vertex_ids()) if keys is None else keys)
        moved = self._rederive(vids)
        self._view_watch.take()
        return moved


def view_placement(base_obj, world_width: float):
    """The view beside the base: the base's rotation and scale, shifted along world +X."""
    from core import ObjectTransform

    t = base_obj.transform
    dx = VIEW_SPACING * (world_width or 1.0)
    return ObjectTransform(
        translation=(t.translation[0] + dx, t.translation[1], t.translation[2]),
        rotation=t.rotation,
        scale=t.scale,
    )


# -- display (H7 provider) -------------------------------------------------------------------------


class MorphSurfaceProvider:
    """H7 provider (`sync(mesh, selection) -> moved`, `surface_mesh`, `dirty`, H7-E `entry_surfaces` /
    `entry_moved`): the mix `b + Σ wᵢ·dᵢ` (`morph_mix`) of every object with a target above 0 %. Never
    writes a scene mesh. Weights and the current target are view state per object (F-11): no Undo
    step, not saved; a weight belongs to a target and goes with it."""

    def __init__(self, scene_of: Callable) -> None:
        self._scene_of = scene_of
        #: ObjectId -> {LayerId: weight in whole percent} (above 0 only; view state, F-11)
        self.weights: dict = {}
        #: ObjectId -> the current target (AD-025 Phase 4): the one Tab, N and +/- act on
        self.current: dict = {}
        self.surface_mesh: Optional[Mesh] = None
        self.entry_surfaces: dict = {}
        self.entry_moved: dict = {}
        #: H7: the edit object's surface mesh kept its identity but its topology was patched (Phase 5)
        self.surface_topology_changed = False
        #: H7-E: ObjectIds whose entry surface was patched in place the same way
        self.entry_topology_changed: set = set()
        self._surfaces: dict = {}
        self._dirty = False
        #: H7 (viewport): the wire is drawn at the mix, not at the rest shape (Manu 2026-10-27: "das Wireframe geht
        #: nicht mit"); selection, hover and picking stay on the rest shape (Morph Lab 6a "hilft").
        self.wire_follows_surface = True
        #: AD-025 Phase 4 (stage chain): show the edit object's mix even at 0 % while a later stage reads it
        self.keep_edit_surface = False
        self.last_update_ms: Optional[float] = None
        self.last_changed = 0

    def reset(self) -> None:
        """A new scene: the ObjectIds of the old one mean nothing (weights are not saved)."""
        for surface in self._surfaces.values():
            surface.close()
        self._surfaces.clear()
        self.weights.clear()
        self.current.clear()
        self.surface_mesh = None
        self.entry_surfaces, self.entry_moved = {}, {}
        self._dirty = True

    def _mesh_of(self, object_id):
        obj = self._scene_of().objects.get(object_id)
        return None if obj is None else obj.mesh

    def current_target(self, object_id):
        """The object's current target: the one set (while it exists), else its first; None = no target."""
        mesh = self._mesh_of(object_id)
        if mesh is None:
            return None
        ids = morph_target_ids(mesh)
        lid = self.current.get(object_id)
        if lid in ids:
            return lid
        return ids[0] if ids else None

    def set_current(self, object_id, lid) -> None:
        self.current[object_id] = lid

    def weight(self, object_id, lid=None) -> int:
        """The weight of `lid` (default: the current target) in whole percent."""
        lid = self.current_target(object_id) if lid is None else lid
        return self.weights.get(object_id, {}).get(lid, MIN_WEIGHT)

    def object_weights(self, object_id) -> dict:
        """{LayerId: weight} of the object's targets above 0 % (only targets that exist)."""
        mesh = self._mesh_of(object_id)
        if mesh is None:
            return {}
        alive = set(morph_target_ids(mesh))
        return {lid: w for lid, w in self.weights.get(object_id, {}).items() if lid in alive}

    def set_weight(self, object_id, weight: int, lid=None) -> int:
        lid = self.current_target(object_id) if lid is None else lid
        weight = clamp_weight(weight)
        if lid is None:
            return weight
        if weight != self.weight(object_id, lid):
            per = self.weights.setdefault(object_id, {})
            if weight == MIN_WEIGHT:
                per.pop(lid, None)
                if not per:
                    self.weights.pop(object_id, None)
            else:
                per[lid] = weight
            self._dirty = True
        return weight

    def shown(self, edit_mesh=None) -> dict:
        """ObjectId -> (object, {LayerId: weight}) of what is to be shown now (`edit_mesh`: kept at 0 %
        while a later stage of the chain reads its mix, `keep_edit_surface`)."""
        scene = self._scene_of()
        out = {}
        for oid in self.weights:
            obj = scene.objects.get(oid)
            if obj is None:
                continue
            weights = self.object_weights(oid)
            if weights:
                out[oid] = (obj, weights)
        if self.keep_edit_surface and edit_mesh is not None:
            for oid, obj in scene.objects.items():
                if obj.mesh is edit_mesh and oid not in out and morph_target_ids(obj.mesh):
                    out[oid] = (obj, {})
        return out

    def wants_surface(self) -> bool:
        return bool(self.shown())

    @property
    def dirty(self) -> bool:
        return self._dirty or any(s.pending() for s in self._surfaces.values())

    @dirty.setter
    def dirty(self, value: bool) -> None:
        self._dirty = bool(value)

    def sync(self, mesh, selection) -> set:
        started = time.perf_counter()
        self._dirty = False
        shown = self.shown(mesh)
        scene = self._scene_of()
        for oid, surface in list(self._surfaces.items()):
            # Kept at 0 % (a tap back to the last weight costs a patch, not a rebuild); dropped with
            # its object, its mesh or its last target.
            obj = scene.objects.get(oid)
            if obj is None or obj.mesh is not surface.base or not morph_target_ids(obj.mesh):
                self._surfaces.pop(oid).close()
        self.surface_mesh = None
        self.entry_surfaces, self.entry_moved = {}, {}
        self.surface_topology_changed, self.entry_topology_changed = False, set()
        moved_edit: set = set()
        changed_total = 0
        for oid, (obj, weights) in shown.items():
            surface = self._surfaces.get(oid)
            if surface is None:
                surface = self._surfaces[oid] = MixSurface(obj.mesh)
            rebuilt, changed = surface.update(weights)
            changed_total += len(changed)
            if obj.mesh is mesh:
                self.surface_mesh = surface.mesh
                moved_edit = set() if rebuilt else changed
                self.surface_topology_changed = surface.topology_changed
            else:
                self.entry_surfaces[oid] = surface.mesh
                self.entry_moved[oid] = set() if rebuilt else changed
                if surface.topology_changed:
                    self.entry_topology_changed.add(oid)
        if shown:
            self.last_update_ms = (time.perf_counter() - started) * 1000.0
            self.last_changed = changed_total
        return moved_edit


class MorphDisplay:
    """The provider and its stage in the viewport's surface chain (`mirai.surface_chain`, AD-025 Phase 4:
    morph -> SubD, H5b). Without a chain (a host that never set one up) it claims the single H7 slot
    as in Phase 3: taken while something is to be shown and the slot is free, given back at 0 %; a slot
    held by another host is reported once (`blocked`)."""

    def __init__(self, scene_of: Callable, set_status: Callable[[str], None]) -> None:
        self.provider = MorphSurfaceProvider(scene_of)
        self._set_status = set_status
        self.viewport = None
        self.blocked = False
        #: the app's `SurfaceChain` (set by `Application`); None = the Phase 3 single-slot behaviour
        self.chain = None

    def attach(self, viewport) -> None:
        self.viewport = viewport
        self.provider.reset()
        self.blocked = False

    def owns_slot(self) -> bool:
        if self.viewport is None:
            return False
        if self.chain is not None:
            return self.chain.holds(self.provider)
        return self.viewport.surface_provider is self.provider

    def refresh(self) -> None:
        vp = self.viewport
        if vp is None:
            return
        provider = self.provider
        # a later stage (SubD) reads the edit object's mix: keep it at 0 % too, so a weight step patches
        # SubD's positions instead of switching its input mesh (a rebuild)
        provider.keep_edit_surface = self.chain is not None and self.chain.later_stage_wanted(provider)
        wants = provider.wants_surface() or bool(
            provider.keep_edit_surface and vp.mesh is not None and morph_target_ids(vp.mesh)
        )
        if self.chain is not None:
            self.chain.want(self.provider, wants)
        elif wants and vp.surface_provider is None:
            vp.set_surface_provider(self.provider)
        elif not wants and self.owns_slot():
            vp.set_surface_provider(None)
        blocked = wants and not self.owns_slot()
        if blocked and not self.blocked:
            self._set_status("Morph: the mix is not shown while another host holds the viewport's surface")
        self.blocked = blocked


def world_width(obj, mesh: Mesh) -> float:
    """Width of the object's world bounds along X (for the view's distance)."""
    from . import object_space

    xs = [object_space.to_world(obj, mesh.vertex_position(v))[0] for v in mesh.all_vertex_ids()]
    return (max(xs) - min(xs)) if xs else 1.0
