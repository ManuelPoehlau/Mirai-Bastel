"""Morph targets in Production (AD-025 Phase 3, ARCH-02): one persistent target per mesh. Names, keys
and texts `PROVISIONAL`.

What a target is: one vector point layer of the base mesh (`core.Mesh` point layers, AD-025 §4.2) —
offsets keyed by `VertexId` (Manu J-3 "relativ": the target follows later base edits). The Core owns
the values, their journal, Undo and the file; this module gives them their meaning:

- **Lifecycle** (`Application.create_morph_target` / `rename_` / `delete_`): one Undo step each, a
  layer-only `_mesh_transaction`. Phase 3 allows one target per mesh (`MAX_TARGETS`).
- **Weight** (`MorphSurfaceProvider.weights`): view state per object in whole percent — no Undo
  step, not saved (F-11, Manu 2026-10-17). The viewport shows the mix `b + w·d` through the H7
  replacement surface (`Viewport.set_surface_provider`): the edit object's faces (`surface_mesh`) and,
  H7-E, object entries (`entry_surfaces`, the base beside the editing view). The wire follows the
  mix (`wire_follows_surface`, Manu 2026-10-27); picking, selection, hover and every tool stay on the rest
  shape (H7: the cage is authoritative; Morph Lab 6a: "hilft"). The
  slot is shared with the SubD preview; morph + SubD together come with Phase 4 (H5b), so whoever
  holds the slot first keeps it and the other says so (`MorphDisplay`).
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

#: Phase 3: one target per mesh; several targets, the stage chain and morph + SubD are Phase 4.
MAX_TARGETS = 1
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
    """The mesh's morph targets: its vector point layers, in display order (in Phase 3 at most one)."""
    return [lid for lid in mesh.point_layer_ids() if mesh.point_layer_info(lid).kind is LayerKind.VECTOR]


def morph_target(mesh: Mesh):
    """The target the app works with (the first one), or None."""
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
    """One evaluated position: `b` at 0 %, exactly `b + d` at 100 %, else `b + w·d` (exact where the
    offset is zero, exactly mirrored for mirrored inputs)."""
    if weight >= MAX_WEIGHT:
        return (b[0] + d[0], b[1] + d[1], b[2] + d[2])
    if weight <= MIN_WEIGHT:
        return tuple(b)
    w = weight / 100.0
    return (b[0] + w * d[0], b[1] + w * d[1], b[2] + w * d[2])


def _rest_state(mesh: Mesh) -> dict:
    """The mesh's state without its point layers (a derived mesh carries none)."""
    state = mesh.export_state()
    state["point_layers"] = None
    return state


def _topology_touched(change, mesh: Mesh) -> bool:
    if change.edges or change.faces:
        return True
    return any(before is None or not mesh.is_valid_vertex(vid) for vid, before in change.vertices.items())


def _offset_keys(change, lid) -> Optional[set]:
    """The vertices whose offset in `lid` may have changed (None = the whole layer)."""
    if lid in change.layer_whole:
        return None
    return set(change.layer_values.get(lid, ()))


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


class _Surface:
    """The evaluated surface of one base mesh at one weight, patched from the base's journal. Keeps
    `(b, d)` of every point with an offset (`_bd`) and what it shows (`_shown`), so a weight step reads
    no mesh and touches only the points with an offset."""

    def __init__(self, base: Mesh) -> None:
        self.base = base
        self._watch = base.watch()
        self.mesh: Optional[Mesh] = None
        self.lid = None
        self.weight: Optional[int] = None
        self._bd: dict = {}
        self._shown: dict = {}

    def close(self) -> None:
        self._watch.close()

    def pending(self) -> bool:
        return not self._watch.peek().is_empty()

    def update(self, lid, weight: int) -> tuple[bool, set]:
        """(rebuilt, changed vertices). Cost: O(stored offsets) for a weight step, O(touched) for an
        edit, O(V) only for a rebuild (first show, topology change, another target)."""
        base = self.base
        change = self._watch.take()
        if self.mesh is None or lid != self.lid or _topology_touched(change, base):
            state = _rest_state(base)
            vertices = state["vertices"]
            self._bd, self._shown = {}, {}
            for vid, d in base.layer_items(lid):
                b = tuple(vertices[int(vid)])
                p = blend(b, d, weight)
                self._bd[vid] = (b, d)
                self._shown[vid] = p
                vertices[int(vid)] = list(p)
            self.mesh = Mesh.from_state(state)
            self.lid, self.weight = lid, weight
            return True, set()
        keys = _offset_keys(change, lid)
        if keys is None:
            keys = set(self._bd) | {vid for vid, _ in base.layer_items(lid)}
        candidates = set(change.vertices) | keys
        bd, shown = self._bd, self._shown
        for vid in candidates:  # refresh (b, d) where the journal says something changed
            if not base.is_valid_vertex(vid):
                bd.pop(vid, None)
                shown.pop(vid, None)
                continue
            d = base.layer_value(lid, vid)
            if d == _ZERO:
                bd.pop(vid, None)
            else:
                bd[vid] = (tuple(base.vertex_position(vid)), d)
        if weight != self.weight:
            candidates |= set(bd)
            self.weight = weight
        surface, changed = self.mesh, set()
        for vid in candidates:
            entry = bd.get(vid)
            if entry is None:
                if not base.is_valid_vertex(vid):
                    continue
                p = tuple(base.vertex_position(vid))
            else:
                p = blend(entry[0], entry[1], weight)
            if shown.get(vid) != p:
                shown[vid] = p
                if entry is None:
                    shown.pop(vid)
                    if tuple(surface.vertex_position(vid)) == p:
                        continue
                surface.set_vertex_position(vid, p)
                changed.add(vid)
        return False, changed


class MorphSurfaceProvider:
    """H7 provider (`sync(mesh, selection) -> moved`, `surface_mesh`, `dirty`, H7-E `entry_surfaces` /
    `entry_moved`): the mix of every object whose weight is above 0. Never writes a scene mesh."""

    def __init__(self, scene_of: Callable) -> None:
        self._scene_of = scene_of
        #: ObjectId -> weight in whole percent (view state, F-11)
        self.weights: dict = {}
        self.surface_mesh: Optional[Mesh] = None
        self.entry_surfaces: dict = {}
        self.entry_moved: dict = {}
        self._surfaces: dict = {}
        self._dirty = False
        #: H7 (viewport): the wire is drawn at the mix, not at the rest shape (Manu 2026-10-27: "das Wireframe geht
        #: nicht mit"); selection, hover and picking stay on the rest shape (Morph Lab 6a "hilft").
        self.wire_follows_surface = True
        self.last_update_ms: Optional[float] = None
        self.last_changed = 0

    def reset(self) -> None:
        """A new scene: the ObjectIds of the old one mean nothing (weights are not saved)."""
        for surface in self._surfaces.values():
            surface.close()
        self._surfaces.clear()
        self.weights.clear()
        self.surface_mesh = None
        self.entry_surfaces, self.entry_moved = {}, {}
        self._dirty = True

    def weight(self, object_id) -> int:
        return self.weights.get(object_id, MIN_WEIGHT)

    def set_weight(self, object_id, weight: int) -> int:
        weight = clamp_weight(weight)
        if weight != self.weight(object_id):
            if weight == MIN_WEIGHT:
                self.weights.pop(object_id, None)
            else:
                self.weights[object_id] = weight
            self._dirty = True
        return weight

    def shown(self) -> dict:
        """ObjectId -> (object, target, weight) of what is to be shown now."""
        scene = self._scene_of()
        out = {}
        for oid, weight in self.weights.items():
            obj = scene.objects.get(oid)
            if obj is None or weight <= MIN_WEIGHT:
                continue
            lid = morph_target(obj.mesh)
            if lid is not None:
                out[oid] = (obj, lid, weight)
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
        shown = self.shown()
        scene = self._scene_of()
        for oid, surface in list(self._surfaces.items()):
            # Kept at 0 % (a tap back to the last weight costs a patch, not a rebuild); dropped with
            # its object, its mesh or its target.
            obj = scene.objects.get(oid)
            if obj is None or obj.mesh is not surface.base or morph_target(obj.mesh) is None:
                self._surfaces.pop(oid).close()
        self.surface_mesh = None
        self.entry_surfaces, self.entry_moved = {}, {}
        moved_edit: set = set()
        changed_total = 0
        for oid, (obj, lid, weight) in shown.items():
            surface = self._surfaces.get(oid)
            if surface is None:
                surface = self._surfaces[oid] = _Surface(obj.mesh)
            rebuilt, changed = surface.update(lid, weight)
            changed_total += len(changed)
            if obj.mesh is mesh:
                self.surface_mesh = surface.mesh
                moved_edit = set() if rebuilt else changed
            else:
                self.entry_surfaces[oid] = surface.mesh
                self.entry_moved[oid] = set() if rebuilt else changed
        if shown:
            self.last_update_ms = (time.perf_counter() - started) * 1000.0
            self.last_changed = changed_total
        return moved_edit


class MorphDisplay:
    """The provider and its claim on the viewport's single H7 slot (shared with the SubD preview,
    `mirai.subdivision.preview`): taken while something is to be shown and the slot is free, given
    back at 0 %. A slot held by another host is reported once (`blocked`)."""

    def __init__(self, scene_of: Callable, set_status: Callable[[str], None]) -> None:
        self.provider = MorphSurfaceProvider(scene_of)
        self._set_status = set_status
        self.viewport = None
        self.blocked = False

    def attach(self, viewport) -> None:
        self.viewport = viewport
        self.provider.reset()
        self.blocked = False

    def owns_slot(self) -> bool:
        return self.viewport is not None and self.viewport.surface_provider is self.provider

    def refresh(self) -> None:
        vp = self.viewport
        if vp is None:
            return
        wants = self.provider.wants_surface()
        if wants and vp.surface_provider is None:
            vp.set_surface_provider(self.provider)
        elif not wants and self.owns_slot():
            vp.set_surface_provider(None)
        blocked = wants and not self.owns_slot()
        if blocked and not self.blocked:
            self._set_status("Morph: the mix is not shown while the SubD preview is on (morph + SubD: Phase 4)")
        self.blocked = blocked


def world_width(obj, mesh: Mesh) -> float:
    """Width of the object's world bounds along X (for the view's distance)."""
    from . import object_space

    xs = [object_space.to_world(obj, mesh.vertex_position(v))[0] for v in mesh.all_vertex_ids()]
    return (max(xs) - min(xs)) if xs else 1.0
