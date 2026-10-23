"""SubD preview of the edit mesh: view state, replacement surface (H7) and line presentation (H1).

Production since 2026-10-23 (promoted from `experiments/subdivision_lab/lab_surface.py` / `lab_app.py`,
WP-SUBD-LAB-02). The control mesh stays the only authoritative mesh: every tool, selection, picking
and History run on it unchanged; this module derives a display surface from it and never writes
back. Nothing here is document state: view, level and the line settings are transient (no scene
file, no Undo step; research OF-3 stays open).

Parts:

- `SubdSurfaceProvider` — the Viewport's replacement surface (AD-013 H7, `Viewport.set_surface_provider`).
  It reads the control mesh's change journal (`Mesh.watch()`, AD-023) on every sync:
  * nothing recorded (hover, selection, camera): no work;
  * only positions changed (W/E/R, Tweak, Soft, Undo of a move): the moved control vertices go
    through the stencils (`SubdLevel.apply_local`, many at once through `apply_full`); the returned
    set is the moved derived vertices, so the viewport patches its buffers, no rebuild;
  * edges or faces changed, or vertices appeared / disappeared (Knife, Extrude, Connect, Delete,
    Dissolve, Undo over such a step): topology and stencils are rebuilt (they are global index
    data), but the shown derived `core.Mesh` is **patched**, not replaced: derived faces whose
    stable key (`SubdLevel.face_key`) or corner keys changed are removed and the new ones added,
    kept vertices only get new positions. `surface_topology_changed` tells the viewport, whose
    incremental topology sync (AD-023) then patches the GPU buffers of exactly those faces. A level
    switch, another edit object or the first build make a fresh derived mesh (a new object = the
    viewport rebuilds). A symmetry-definition-only change (Shift+S) rebuilds nothing;
  * the control mesh is outside the Catmull-Clark rules (`SubdUnsupportedError`): no surface
    (`surface_mesh = None`, the viewport draws the cage's own faces again) and `message` says why —
    never a stale or silently wrong surface. The next topology change tries again.
- `SubdLinePresentation` — the cage / isoline overlay (H1 `Viewport.add_overlay`), GL-free; its GL
  sink is `gl_lines.GLSubdLineOverlay` (None headless: the segments stay observable).
- `SubdivisionPreview` — what `Application` owns: view (`off` → `cage` → `iso`), level, the
  provisional keys of the `subd` binding context (`SUBD_KEYS`), attach / detach on a viewport.

The provider is attached to the viewport only while the preview is on (H7-R1: without SubD the
viewport is exactly as before), and never over another host's provider (H7-R4: one provider; a lab
that owns the slot keeps it and the preview reports that it cannot switch on).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from core import EdgeId, SelectionMode, VertexId

from ..interaction import commands
from ..interaction.input import GLOBAL_CONTEXT, KNIFE_CONTEXT, SUBD_CONTEXT, TOPOLOGY_CONTEXT, BindingSet, Input
from ..scene_factory import mesh_from_positions_and_faces
from .catmull_clark import SubdLevel, SubdSurface, SubdUnsupportedError

# -- view state ---------------------------------------------------------------------------------

VIEW_OFF = "off"
#: smooth surface + control cage
VIEW_CAGE = "cage"
#: smooth surface + isolines (the control edges as they lie on the surface)
VIEW_ISO = "iso"
VIEW_ORDER = (VIEW_OFF, VIEW_CAGE, VIEW_ISO)
VIEW_LABELS = {
    VIEW_OFF: "aus (Käfig)",
    VIEW_CAGE: "glatte Fläche + Käfig",
    VIEW_ISO: "glatte Fläche + Isolinien",
}

LEVELS = (1, 2, 3)
#: PROVISIONAL (agent-set): level 2 reads as smooth on the head and ran "sehr flüssig" in Manu's Lab
#: test (2026-10-16); level 3 stays one key away.
DEFAULT_LEVEL = 2
MAX_LEVEL = max(LEVELS)
#: PROVISIONAL, carried over from the Lab: a level that would exceed this many derived faces is
#: refused. head_basemesh: L1 1 296 / L2 5 184 / L3 20 736 (allowed); man_with_shoes_basemesh:
#: L1 3 704 / L2 14 816 / L3 59 264 (refused). Not a measured limit of the reference PC.
MAX_DERIVED_FACES = 25_000

#: Above this share of moved control vertices one `apply_full` is cheaper than many `apply_local`
#: calls (each touches the 2-ring; agent-set, not measured on the reference PC).
FULL_UPDATE_SHARE = 0.125


def topology_signature(mesh) -> tuple:
    """Everything the stencils depend on: vertices, edges and face boundaries (core query API)."""
    return (
        tuple(int(v) for v in mesh.all_vertex_ids()),
        tuple(tuple(int(v) for v in mesh.edge_vertices(e)) for e in mesh.all_edge_ids()),
        tuple(tuple(int(v) for v in mesh.face_vertices(f)) for f in mesh.all_face_ids()),
    )


def _structural(change, mesh, index: dict) -> bool:
    """True when the journal shows more than moved vertices: an edge or face touched, or a vertex
    created / removed since the last sync."""
    if change.edges or change.faces:
        return True
    return any((v in index) != mesh.is_valid_vertex(v) for v in change.vertices)


class SubdSurfaceProvider:
    """H7 provider: `sync(mesh, selection) -> moved`, `surface_mesh`, `dirty` (module docstring)."""

    def __init__(self, level: int = DEFAULT_LEVEL, max_faces: int = MAX_DERIVED_FACES) -> None:
        self.enabled = False
        self.level = level
        self.max_faces = max_faces
        #: the derived mesh the viewport draws (None = the control mesh's own faces)
        self.surface_mesh = None
        self.dirty = False
        #: why there is no surface although the preview is on (unsupported topology, level refused)
        self.message: Optional[str] = None
        #: called with `message` whenever it changes to a new text (the app posts it as status)
        self.on_message: Optional[Callable[[str], None]] = None
        self.last_build_ms: Optional[float] = None
        self.last_update_ms: Optional[float] = None
        #: how often topology + stencils were rebuilt / a level's derived mesh was built (tests, HUD)
        self.topology_builds = 0
        self.level_builds = 0
        #: bumped whenever positions or topology of the shown surface changed (the overlay keys on it)
        self.revision = 0
        #: True right after a sync that patched the topology of the *same* `surface_mesh` object
        #: (H7 addition: the viewport then marks the surface's topology dirty); reset by every sync
        self.surface_topology_changed = False
        #: how many topology rebuilds patched the derived mesh instead of replacing it (tests, probe)
        self.surface_patches = 0

        self._mesh = None
        self._watch = None
        self._signature: Optional[tuple] = None
        self._error: Optional[str] = None
        self._surface: Optional[SubdSurface] = None
        self._control_positions: list = []
        self._derived: Optional[SubdLevel] = None
        self._derived_ids: list = []
        self._derived_face_ids: list = []
        self._derived_positions: list = []
        #: control EdgeId -> indices into the shown level's `iso_edges` (correspondence by provenance)
        self._iso_by_edge: dict[EdgeId, list[int]] = {}

    # -- view state ---------------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        if enabled != self.enabled:
            self.enabled = enabled
            self.dirty = True

    def predicted_faces(self, level: int) -> Optional[int]:
        return None if self._surface is None else self._surface.predicted_face_count(level)

    def set_level(self, level: int) -> Optional[str]:
        """Switches the level; returns a refusal text if it would exceed `max_faces`."""
        if level not in LEVELS:
            return f"SubD: Stufe {level} gibt es nicht"
        faces = self.predicted_faces(level)
        if faces is not None and faces > self.max_faces:
            return f"SubD: Stufe {level} abgelehnt: {faces} Flächen > {self.max_faces} (Limit provisorisch)"
        if level != self.level:
            self.level = level
            self._derived = None
            self.dirty = True
        return None

    @property
    def derived_counts(self) -> Optional[tuple[int, int]]:
        if self.surface_mesh is None or self._derived is None:
            return None
        return len(self._derived_ids), len(self._derived.faces)

    # -- read access for the presentation ------------------------------------------------------

    def control_positions(self) -> list:
        return self._control_positions if self._surface is not None else []

    def control_edges(self) -> tuple:
        return () if self._surface is None else self._surface.topology.edges

    def control_edge_ids(self) -> tuple:
        return () if self._surface is None else self._surface.topology.edge_ids

    def derived_positions(self) -> list:
        return self._derived_positions if self.surface_mesh is not None else []

    def iso_edges(self) -> list:
        return [] if self._derived is None or self.surface_mesh is None else self._derived.iso_edges

    def derived_elements(self) -> Optional[tuple]:
        """(`SubdLevel`, vertex ids by derived index, face ids by derived face index) of the shown
        surface, or None. After a patch the mesh's own id order is not the derived order."""
        if self.surface_mesh is None or self._derived is None:
            return None
        return self._derived, self._derived_ids, self._derived_face_ids

    def iso_indices_of(self, edge_id: EdgeId) -> list[int]:
        """The isoline segments (indices into `iso_edges()`) that lie along control edge `edge_id`
        (from the evaluator's provenance `SubdLevel.iso_control_edge`, never from proximity)."""
        if self.surface_mesh is None:
            return []
        return self._iso_by_edge.get(edge_id, [])

    # -- H7 -------------------------------------------------------------------------------------

    def sync(self, mesh, selection) -> set:
        self.dirty = False
        self.surface_topology_changed = False
        if not self.enabled:
            self._detach()
            self._set_message(None)
            return set()
        if mesh is not self._mesh:
            self._attach(mesh)
            return set()
        change = self._watch.take()
        index = {} if self._surface is None else self._surface._index_of
        if self._surface is None and self._error is None:
            self._rebuild()
            return set()
        if _structural(change, mesh, index):
            signature = topology_signature(mesh)
            if signature != self._signature:
                self._rebuild(signature)
                return set()
        if self._error is not None:
            self._set_message(self._error)  # unsupported topology: nothing to draw until it changes
            return set()
        if self._derived is None:
            self._build_level()
            return set()
        if not change.vertices:
            return set()
        return self._update_positions(mesh, change.vertices)

    def _attach(self, mesh) -> None:
        self._detach()
        self._mesh = mesh
        self._watch = mesh.watch()
        self._rebuild()

    def _detach(self) -> None:
        """Drops everything derived (rebuilt from the then current mesh when switched on again)."""
        if self._watch is not None:
            self._watch.close()
        self._watch = None
        self._mesh = None
        self._signature = None
        self._surface = None
        self._error = None
        self._derived = None
        self._derived_ids = []
        self._derived_face_ids = []
        self._derived_positions = []
        self._iso_by_edge = {}
        self._control_positions = []
        if self.surface_mesh is not None:
            self.surface_mesh = None
            self.revision += 1

    def _set_message(self, message: Optional[str]) -> None:
        if message == self.message:
            return
        self.message = message
        if message is not None and self.on_message is not None:
            self.on_message(message)

    def _rebuild(self, signature: Optional[tuple] = None) -> None:
        mesh = self._mesh
        self._signature = signature if signature is not None else topology_signature(mesh)
        previous = None
        if self.surface_mesh is not None and self._derived is not None:
            previous = (self.surface_mesh, self._derived, self._derived_ids, self._derived_face_ids)
        self._derived = None
        self.surface_mesh = None
        self.revision += 1
        self._error = None
        self.topology_builds += 1
        try:
            self._surface = SubdSurface(mesh)
        except SubdUnsupportedError as exc:
            self._surface = None
            self._control_positions = []
            self._iso_by_edge = {}
            self._error = f"SubD aus: {exc}"
            self._set_message(self._error)
            return
        self._build_level(previous)

    def _build_level(self, previous: Optional[tuple] = None) -> None:
        started = time.perf_counter()
        mesh = self._mesh
        surface = self._surface
        self._control_positions = [tuple(mesh.vertex_position(v)) for v in surface.topology.vertex_ids]
        faces = surface.predicted_face_count(self.level)
        if faces > self.max_faces:
            # The topology grew past the limit at this level: fall back to the highest allowed one.
            allowed = [n for n in LEVELS if surface.predicted_face_count(n) <= self.max_faces]
            if not allowed:
                self.surface_mesh = None
                self._error = f"SubD aus: schon Stufe 1 hätte mehr als {self.max_faces} Flächen"
                self._set_message(self._error)
                return
            self.level = max(allowed)
        derived = surface.level(self.level)
        positions = derived.apply_full(self._control_positions)
        patched = None
        if previous is not None and previous[1].level == derived.level:
            patched = _patch_derived_mesh(previous, derived, positions)
        if patched is not None:
            derived_mesh, vertex_ids, face_ids = patched
            self.surface_topology_changed = True
            self.surface_patches += 1
        else:
            derived_mesh = mesh_from_positions_and_faces(positions, derived.faces)
            vertex_ids, face_ids = derived_mesh.all_vertex_ids(), derived_mesh.all_face_ids()
        edge_ids = surface.topology.edge_ids
        by_edge: dict[EdgeId, list[int]] = {}
        for i, control_edge in enumerate(derived.iso_control_edge):
            by_edge.setdefault(edge_ids[control_edge], []).append(i)
        self._derived = derived
        self._derived_ids = vertex_ids
        self._derived_face_ids = face_ids
        self._derived_positions = positions
        self._iso_by_edge = by_edge
        self.surface_mesh = derived_mesh
        self.revision += 1
        self.level_builds += 1
        self.last_build_ms = (time.perf_counter() - started) * 1000.0
        self._set_message(None)

    def _update_positions(self, mesh, touched_vertices) -> set:
        started = time.perf_counter()
        index = self._surface._index_of
        cached = self._control_positions
        changed = []
        for vid in touched_vertices:
            i = index.get(vid)
            if i is None:
                continue
            position = tuple(mesh.vertex_position(vid))
            if position != cached[i]:
                cached[i] = position
                changed.append(i)
        if not changed:
            return set()
        derived = self._derived
        if len(changed) > FULL_UPDATE_SHARE * len(cached):
            self._derived_positions = derived.apply_full(cached)
            touched = range(len(self._derived_ids))
        else:
            touched = set()
            for i in changed:
                touched.update(derived.apply_local(i, cached, self._derived_positions))
        moved: set[VertexId] = set()
        surface, ids, positions = self.surface_mesh, self._derived_ids, self._derived_positions
        for d in touched:
            surface.set_vertex_position(ids[d], positions[d])
            moved.add(ids[d])
        self.revision += 1
        self.last_update_ms = (time.perf_counter() - started) * 1000.0
        return moved


def _patch_derived_mesh(previous: tuple, derived: SubdLevel, positions: list):
    """Turns the previous derived mesh into `derived` in place (same object): derived faces are
    matched by their stable key *and* corner keys; unmatched old faces go (with the edges and
    vertices only they used), new ones come, kept vertices get their new position. Returns
    `(mesh, vertex ids by derived index, face ids by derived face index)`, or None when the result
    does not match `derived` exactly (then the caller builds a fresh mesh - never a wrong surface)."""
    mesh, old_level, old_vertex_ids, old_face_ids = previous
    old_vkey = old_level.vert_key
    old_faces = {
        key: (old_face_ids[i], tuple(old_vkey[v] for v in face))
        for i, (key, face) in enumerate(zip(old_level.face_key, old_level.faces))
    }
    new_vkey = derived.vert_key
    new_faces = {
        key: tuple(new_vkey[v] for v in face) for key, face in zip(derived.face_key, derived.faces)
    }
    gone = [fid for key, (fid, corners) in old_faces.items() if new_faces.get(key) != corners]
    if gone:
        mesh.delete_faces(gone)
    old_vid = dict(zip(old_vkey, old_vertex_ids))
    vertex_ids = []
    for key, position in zip(new_vkey, positions):
        vid = old_vid.get(key)
        if vid is not None and mesh.is_valid_vertex(vid):
            if mesh.vertex_position(vid) != position:
                mesh.set_vertex_position(vid, position)
        else:
            vid = mesh.add_vertex(position)
        vertex_ids.append(vid)
    face_ids = []
    for key, face in zip(derived.face_key, derived.faces):
        kept = old_faces.get(key)
        if kept is not None and kept[1] == new_faces[key] and mesh.is_valid_face(kept[0]):
            face_ids.append(kept[0])
        else:
            face_ids.append(mesh.add_face([vertex_ids[v] for v in face]))
    if len(mesh.all_vertex_ids()) != len(vertex_ids) or len(mesh.all_face_ids()) != len(face_ids):
        return None
    return mesh, vertex_ids, face_ids


# -- lines --------------------------------------------------------------------------------------

#: Layer names of the presentation (the GL sink draws them in this order).
CAGE_LAYER = "subd_cage"
ISO_LAYER = "subd_iso"


class SubdLinePresentation:
    """H1 overlay: the cage (view `cage`) or the isolines (view `iso`) of the provider's state.

    Runs after the provider in `Viewport.sync()` (H7 syncs before the extra overlays), so it reads
    positions that already match the control mesh. `sink` is the GL side or None headless; the
    segments stay observable in `segments`.
    """

    def __init__(self, provider: SubdSurfaceProvider, sink=None) -> None:
        self.provider = provider
        self.sink = sink
        self.view = VIEW_OFF
        self.cage_depth_test = True
        self.dirty = True
        self.segments: dict[str, list] = {CAGE_LAYER: [], ISO_LAYER: []}
        self._key: Optional[tuple] = None

    def set_view(self, view: str, cage_depth_test: bool) -> None:
        if view not in VIEW_ORDER:
            raise ValueError(view)
        if (view, cage_depth_test) != (self.view, self.cage_depth_test):
            self.view = view
            self.cage_depth_test = cage_depth_test
            self.dirty = True

    def layer(self) -> Optional[str]:
        if self.provider.surface_mesh is None:
            return None
        return {VIEW_CAGE: CAGE_LAYER, VIEW_ISO: ISO_LAYER}.get(self.view)

    def sync(self, mesh, selection) -> None:
        self.dirty = False
        layer = self.layer()
        key = (layer, self.provider.revision)
        if key == self._key:
            return
        self._key = key
        cage, iso = [], []
        if layer == CAGE_LAYER:
            p = self.provider.control_positions()
            cage = [(p[a], p[b]) for a, b in self.provider.control_edges()]
        elif layer == ISO_LAYER:
            p = self.provider.derived_positions()
            iso = [(p[a], p[b]) for a, b in self.provider.iso_edges()]
        self.segments = {CAGE_LAYER: cage, ISO_LAYER: iso}
        if self.sink is not None:
            self.sink.set_segments(CAGE_LAYER, cage)
            self.sink.set_segments(ISO_LAYER, iso)

    def draw(self, camera_uniforms) -> None:
        layer = self.layer()
        if self.sink is None or layer is None:
            return
        self.sink.set_depth_test(CAGE_LAYER, self.cage_depth_test)
        self.sink.draw(camera_uniforms, layers=(layer,))


# -- keys (context `subd`, PROVISIONAL) ----------------------------------------------------------

#: Binding context of the SubD keys (`interaction.input.SUBD_CONTEXT`): resolved by
#: `Application.key_press` only when the global context binds nothing for the input, so they can
#: never shadow an app key; `keymap.json` can rebind them in context "subd".

CYCLE_VIEW = commands.SUBD_CYCLE_VIEW
TOGGLE_CAGE_DEPTH = commands.SUBD_TOGGLE_CAGE_DEPTH
LEVEL_COMMANDS = {commands.SUBD_LEVEL_1: 1, commands.SUBD_LEVEL_2: 2, commands.SUBD_LEVEL_3: 3}


@dataclass(frozen=True)
class SubdKey:
    input: Input
    command: str
    label: str


def key_label(input: Input) -> str:
    mods = "+".join(m.capitalize() for m in sorted(input.modifiers))
    value = input.value.upper()
    return f"{mods}+{value}" if mods else value


#: PROVISIONAL engineering keys (the SubD Lab's proposal, accepted "erstmal" by Manu 2026-10-16;
#: not Artist Input Truth, AD-013 I8). `1`/`2`/`3` are the component modes, so levels are Ctrl+1/2/3.
SUBD_KEYS: tuple[SubdKey, ...] = (
    SubdKey(Input("key", "v"), CYCLE_VIEW, "SubD: aus → glatte Fläche + Käfig → glatte Fläche + Isolinien"),
    *(
        SubdKey(Input("key", str(n), frozenset({"ctrl"})), command, f"SubD-Stufe {n}")
        for command, n in LEVEL_COMMANDS.items()
    ),
    SubdKey(Input("key", "v", frozenset({"shift"})), TOGGLE_CAGE_DEPTH, "Käfig: von der Fläche verdeckt / immer sichtbar"),
)
SUBD_COMMANDS = frozenset(entry.command for entry in SUBD_KEYS)

#: Contexts `Application` resolves keys in; a SubD key bound in any of them would be unreachable.
APP_CONTEXTS = (GLOBAL_CONTEXT, KNIFE_CONTEXT, TOPOLOGY_CONTEXT)


class SubdBindingConflict(RuntimeError):
    """A SubD default key is already bound in a context the app resolves."""


def assert_subd_keys_free(bindings: BindingSet) -> None:
    conflicts = []
    for entry in SUBD_KEYS:
        for context in APP_CONTEXTS:
            bound = bindings.command_for(entry.input, context)
            if bound is not None:
                conflicts.append(f"{key_label(entry.input)} ist im Kontext {context!r} an {bound!r} gebunden")
    if conflicts:
        raise SubdBindingConflict("SubD-Tasten nicht frei: " + "; ".join(conflicts))


def install_subd_bindings(bindings: BindingSet) -> None:
    """Checks the default SubD keys against the app's contexts, then binds them in `SUBD_CONTEXT`."""
    assert_subd_keys_free(bindings)
    for entry in SUBD_KEYS:
        bindings.set_default(entry.input, entry.command, context=SUBD_CONTEXT)


# -- the preview ---------------------------------------------------------------------------------


class SubdivisionPreview:
    """View state + provider + presentation of the edit mesh's SubD preview (module docstring)."""

    def __init__(self, set_status: Optional[Callable[[str], None]] = None) -> None:
        self.view = VIEW_OFF
        self.cage_depth_test = True
        self.provider = SubdSurfaceProvider(level=DEFAULT_LEVEL)
        self.provider.on_message = set_status
        self.lines = SubdLinePresentation(self.provider)
        self._set_status = set_status or (lambda _message: None)
        self.viewport = None
        #: the viewport the presentation was added to as an extra overlay (added on first use)
        self._overlay_viewport = None

    @property
    def level(self) -> int:
        return self.provider.level

    @property
    def enabled(self) -> bool:
        return self.view != VIEW_OFF

    @property
    def active(self) -> bool:
        """On and actually showing a surface (not refused, not unsupported)."""
        return self.enabled and self.provider.surface_mesh is not None

    # -- viewport ---------------------------------------------------------------------------------

    def attach(self, viewport, line_sink=None) -> None:
        """Hooks the preview onto a (new) viewport. Nothing is added to it until the preview is on:
        then the provider takes the H7 slot (only if free) and the presentation becomes an extra
        overlay (once per viewport). Without SubD the viewport stays exactly as before."""
        self.viewport = viewport
        self.lines.sink = line_sink
        self.lines._key = None
        self.lines.dirty = True
        self._overlay_viewport = None
        if self.enabled and not self._claim_slot():
            self._fall_back_off(self._slot_refusal())

    def _owns_slot(self) -> bool:
        return self.viewport is not None and self.viewport.surface_provider is self.provider

    def _slot_refusal(self) -> str:
        return "SubD: nicht verfügbar — die Ersatzfläche des Viewports gehört einem anderen Host"

    def _claim_slot(self) -> bool:
        vp = self.viewport
        if vp is None:
            return True
        if vp.surface_provider is None:
            vp.set_surface_provider(self.provider)
        if vp.surface_provider is not self.provider:
            return False
        if self._overlay_viewport is not vp:
            vp.add_overlay(self.lines)
            self._overlay_viewport = vp
        return True

    def _release_slot(self) -> None:
        if self._owns_slot():
            self.viewport.set_surface_provider(None)

    def _fall_back_off(self, message: str) -> None:
        self.view = VIEW_OFF
        self._apply()
        self._set_status(message)

    def _apply(self) -> None:
        self.provider.set_enabled(self.enabled)
        self.lines.set_view(self.view, self.cage_depth_test)
        if self.enabled:
            self._claim_slot()
        else:
            self.provider.sync(None, None)  # drop derived data and the journal at once
            self._release_slot()

    # -- commands ---------------------------------------------------------------------------------

    def set_view(self, view: str) -> bool:
        if view not in VIEW_ORDER:
            raise ValueError(view)
        if view != VIEW_OFF and self.viewport is not None and not (
            self.viewport.surface_provider is None or self._owns_slot()
        ):
            self._set_status(self._slot_refusal())
            return False
        self.view = view
        self._apply()
        self._set_status(f"SubD: {VIEW_LABELS[view]}" + (f" · Stufe {self.level}" if self.enabled else ""))
        return True

    def run(self, command: str) -> bool:
        """One SubD command (view state only: no mesh change, no History). True = it took effect."""
        if command == CYCLE_VIEW:
            return self.set_view(VIEW_ORDER[(VIEW_ORDER.index(self.view) + 1) % len(VIEW_ORDER)])
        if command == TOGGLE_CAGE_DEPTH:
            self.cage_depth_test = not self.cage_depth_test
            self._apply()
            self._set_status(
                "SubD: Käfig von der Fläche verdeckt" if self.cage_depth_test else "SubD: Käfig immer sichtbar"
            )
            return True
        if command in LEVEL_COMMANDS:
            refusal = self.provider.set_level(LEVEL_COMMANDS[command])
            if refusal is not None:
                self._set_status(refusal)
                return False
            self._set_status(f"SubD: Stufe {self.level}" + ("" if self.enabled else " (Vorschau aus)"))
            return True
        return False

    def status_text(self) -> str:
        if not self.enabled:
            return "SubD aus"
        parts = [f"SubD {VIEW_LABELS[self.view]}", f"Stufe {self.level}"]
        counts = self.provider.derived_counts
        if counts is not None:
            parts.append(f"{counts[1]} Flächen")
        if self.provider.message:
            parts.append(self.provider.message)
        return " · ".join(parts)


def selection_edges(selection, mesh) -> tuple[frozenset, frozenset]:
    """(hovered edges, selected edges) of `selection` that exist in `mesh`; selected edges only in
    Edge mode (the app's own highlight rules, `viewport.overlay.SelectionOverlay.line_layers`)."""
    if selection is None or mesh is None:
        return frozenset(), frozenset()
    hovered = selection.hovered
    hover = frozenset({hovered}) if isinstance(hovered, EdgeId) and mesh.is_valid_edge(hovered) else frozenset()
    selected: frozenset = frozenset()
    if selection.mode is SelectionMode.EDGE:
        selected = frozenset(e for e in selection.edges if mesh.is_valid_edge(e))
    return hover, selected
