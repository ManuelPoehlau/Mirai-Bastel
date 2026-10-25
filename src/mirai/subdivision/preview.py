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

from core import EdgeId, FaceId, SelectionMode, VertexId

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
        #: H7 addition (inert default False): the host draws the edit mesh's edges itself while the
        #: surface is shown, so the viewport leaves out its wire layer (no second, full-strength cage)
        self.replaces_wire = True

        #: Hide / Isolate (`mirai.hidden`): hidden control vertices. A control face with one of them is
        #: hidden, and with it every derived face born from it (`hidden_surface_faces`).
        self._hidden_control: frozenset = frozenset()
        self._hidden_version = 0

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

    def set_hidden(self, vertex_ids) -> None:
        self._hidden_control = frozenset(vertex_ids)
        self._hidden_version += 1

    @property
    def hidden_key(self) -> tuple:
        """Changes whenever `hidden_surface_faces` may differ (hidden set, topology or level rebuilt)."""
        return (self._hidden_version, self.topology_builds, self.level_builds)

    def surface_face_tints(self, control_tints) -> dict:
        """`{derived face: colour}` for the shown surface from `{control face: colour}` (saved regions): every derived
        face takes the colour of the control face it was born in (`face_parent`), as ZBrush shows a polygroup."""
        if not control_tints or self._surface is None or self._derived is None:
            return {}
        face_ids = self._surface.topology.face_ids
        out = {}
        for i, parent in enumerate(self._derived.face_parent):
            color = control_tints.get(face_ids[parent])
            if color is not None:
                out[self._derived_face_ids[i]] = color
        return out

    def hidden_control_edges(self) -> frozenset:
        """Indices (into `control_edges()`) of the cage edges with a hidden endpoint."""
        if not self._hidden_control or self._surface is None:
            return frozenset()
        topology = self._surface.topology
        hidden = self._hidden_control
        vertex_ids = topology.vertex_ids
        return frozenset(
            i for i, (a, b) in enumerate(topology.edges) if vertex_ids[a] in hidden or vertex_ids[b] in hidden
        )

    def hidden_surface_faces(self) -> frozenset:
        """The shown surface's faces that lie in a hidden control face (by provenance, `face_parent`)."""
        if not self._hidden_control or self._surface is None or self._derived is None:
            return frozenset()
        topology = self._surface.topology
        hidden = self._hidden_control
        vertex_ids = topology.vertex_ids
        hidden_parents = {
            i for i, face in enumerate(topology.faces) if any(vertex_ids[v] in hidden for v in face)
        }
        return frozenset(
            self._derived_face_ids[i] for i, parent in enumerate(self._derived.face_parent)
            if parent in hidden_parents
        )

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

#: Layers of the presentation, in draw order (the GL sink is `gl_lines.GLSubdLineOverlay`).
ISO_LAYER = "subd_iso"
CAGE_LAYER = "subd_cage"
ISO_HOVER_LAYER = "subd_iso_hover"
ISO_SELECTED_LAYER = "subd_iso_selected"
CAGE_HOVER_LAYER = "subd_cage_hover"
CAGE_SELECTED_LAYER = "subd_cage_selected"
LINE_LAYERS = (ISO_LAYER, CAGE_LAYER, ISO_HOVER_LAYER, ISO_SELECTED_LAYER, CAGE_HOVER_LAYER, CAGE_SELECTED_LAYER)

#: Depth modes the sink understands.
DEPTH_LEQUAL = "lequal"    # hidden where the smooth surface (polygon-offset behind its lines) is in front
DEPTH_ALWAYS = "always"    # no depth test: drawn over the surface
DEPTH_GREATER = "greater"  # only where the surface is in front: the hidden part

#: PROVISIONAL (Artist direction 2026-10-23, value agent-set): opacity of the secondary line system
#: (the cage in the iso view). One parameter; Alt+V steps through `SECONDARY_STEPS` (0 = hidden).
DEFAULT_SECONDARY_STRENGTH = 0.35
SECONDARY_STEPS = (0.35, 0.6, 0.0, 0.15)

#: Look (PROVISIONAL): cage = the app's wire grey, isolines = the Lab's cooler slate, highlights = the
#: app's own hover / selection colours (same colour family as the cage edge's highlight).
CAGE_RGB = (0.15, 0.15, 0.15)
ISO_RGB = (0.22, 0.34, 0.52)
HOVER_RGBA = (0.95, 0.90, 0.35, 0.55)   # viewport.gl_point_overlay.HOVER_COLOR
SELECTED_RGBA = (1.0, 0.82, 0.15, 1.0)  # viewport.gl_point_overlay.SELECTED_COLOR


def highlight_edges(selection, mesh) -> tuple[frozenset, frozenset]:
    """(hovered, selected) control edges whose isoline chains are highlighted, by the app's own
    highlight rules: Edge mode = the edges; Face mode = the boundary edges of the faces (their
    outline on the surface). Vertices map to no chain (their points stay on the cage, where they
    are grabbed). Invalid ids are skipped."""
    if selection is None or mesh is None:
        return frozenset(), frozenset()

    def edges_of(element) -> set:
        if isinstance(element, EdgeId):
            return {element} if mesh.is_valid_edge(element) else set()
        if isinstance(element, FaceId):
            return set(mesh.face_edges(element)) if mesh.is_valid_face(element) else set()
        return set()

    hover = frozenset(edges_of(selection.hovered))
    selected: set = set()
    if selection.mode is SelectionMode.EDGE:
        selected = {e for e in selection.edges if mesh.is_valid_edge(e)}
    elif selection.mode is SelectionMode.FACE:
        for f in selection.faces:
            selected |= edges_of(f)
    return hover, frozenset(selected)


class SubdLinePresentation:
    """H1 overlay: the cage, the isolines and the highlighted isoline chains (GL-free).

    Hierarchy (Artist direction 2026-10-23, `PROVISIONAL`): exactly one line system is primary.
    View `cage`: the cage at full strength, no isolines except highlighted chains. View `iso`: the
    isolines at full strength, the cage secondary (`secondary_strength`, blended, no depth write).

    Highlight: a hovered / selected control edge (Face mode: the face's boundary) highlights its
    isoline chain — from the evaluator's provenance (`SubdSurfaceProvider.iso_indices_of`), never
    from proximity — in the app's hover / selection colour. The cage edge itself is highlighted by
    the app's own edge layer, drawn after this overlay (`DRAW_UNDER_HIGHLIGHTS`), so the cage can
    never paint over it. With the cage always visible (`cage_depth_test` False) the part of a
    highlighted cage edge that the surface hides gets its own layer (depth GREATER), so the
    highlight stays the strongest element there too.

    Depth policy: the smooth surface is always polygon-offset (viewport), isolines and chains are
    depth-tested on it (`DEPTH_LEQUAL`); cage lines are depth-tested against the surface (hidden
    cage edges hidden) or, with Shift+V, drawn over it (`DEPTH_ALWAYS`). In Wireframe (no faces)
    the preview draws nothing; the viewport's wire shows the cage as always.

    Cage / isoline segments are rebuilt only when the provider's revision or the view changes; a
    hover or selection change touches the highlight layers alone.
    """

    DRAW_UNDER_HIGHLIGHTS = True

    def __init__(self, provider: SubdSurfaceProvider, sink=None) -> None:
        self.provider = provider
        self.sink = sink
        self.view = VIEW_OFF
        self.cage_depth_test = True
        self.secondary_strength = DEFAULT_SECONDARY_STRENGTH
        self.faces_shown = True
        #: Shift+D in a SubD view (2026-10-23, Manu: option A): the cage / isoline lines on or off;
        #: the highlighted chains stay
        self.lines_shown = True
        self.dirty = True
        self.segments: dict[str, list] = {layer: [] for layer in LINE_LAYERS}
        self._geometry_key: Optional[tuple] = None
        self._highlight_key: Optional[tuple] = None
        self._style_key: Optional[tuple] = None

    def configure(
        self, *, view=None, cage_depth_test=None, secondary_strength=None, faces_shown=None, lines_shown=None
    ) -> None:
        if view is not None and view not in VIEW_ORDER:
            raise ValueError(view)
        changes = {
            "view": view, "cage_depth_test": cage_depth_test,
            "secondary_strength": secondary_strength, "faces_shown": faces_shown,
            "lines_shown": lines_shown,
        }
        for name, value in changes.items():
            if value is not None and getattr(self, name) != value:
                setattr(self, name, value)
                self.dirty = True

    def reset(self) -> None:
        """Forget what was pushed (a new sink / viewport)."""
        self._geometry_key = self._highlight_key = self._style_key = None
        self.dirty = True

    def visible(self) -> bool:
        return self.view != VIEW_OFF and self.faces_shown and self.provider.surface_mesh is not None

    def active_layers(self) -> tuple[str, ...]:
        if not self.visible():
            return ()
        layers = []
        if not self.lines_shown:
            pass  # Shift+D: no cage, no isolines - only the highlighted chains below
        elif self.view == VIEW_ISO:
            layers.append(ISO_LAYER)
            if self.secondary_strength > 0.0:
                layers.append(CAGE_LAYER)
        else:
            layers.append(CAGE_LAYER)
        layers += [ISO_HOVER_LAYER, ISO_SELECTED_LAYER]
        if not self.cage_depth_test and CAGE_LAYER in layers:
            layers += [CAGE_HOVER_LAYER, CAGE_SELECTED_LAYER]
        return tuple(layers)

    def _push(self, layer: str, segments: list) -> None:
        self.segments[layer] = segments
        if self.sink is not None:
            self.sink.set_segments(layer, segments)

    def sync(self, mesh, selection) -> None:
        self.dirty = False
        provider = self.provider
        visible = self.visible()
        geometry_key = (visible, self.view, provider.revision, self.lines_shown, provider.hidden_key)
        if geometry_key != self._geometry_key:
            self._geometry_key = geometry_key
            cage, iso = [], []
            if visible and self.lines_shown:
                p = provider.control_positions()
                gone = provider.hidden_control_edges()  # Hide / Isolate: no line of a hidden edge
                cage = [(p[a], p[b]) for i, (a, b) in enumerate(provider.control_edges()) if i not in gone]
                if self.view == VIEW_ISO:
                    d = provider.derived_positions()
                    owner = provider._derived.iso_control_edge
                    iso = [(d[a], d[b]) for i, (a, b) in enumerate(provider.iso_edges()) if owner[i] not in gone]
            self._push(CAGE_LAYER, cage)
            self._push(ISO_LAYER, iso)
        hover, selected = highlight_edges(selection, mesh) if visible else (frozenset(), frozenset())
        highlight_key = (visible, self.view, provider.revision, hover, selected, self.cage_depth_test, self.lines_shown)
        if highlight_key != self._highlight_key:
            self._highlight_key = highlight_key
            self._push(ISO_HOVER_LAYER, self._chains(hover))
            self._push(ISO_SELECTED_LAYER, self._chains(selected))
            x_ray = visible and self.lines_shown and not self.cage_depth_test
            self._push(CAGE_HOVER_LAYER, self._cage_segments(hover) if x_ray else [])
            self._push(CAGE_SELECTED_LAYER, self._cage_segments(selected) if x_ray else [])
        style_key = (self.view, self.secondary_strength, self.cage_depth_test)
        if style_key != self._style_key and self.sink is not None:
            self._style_key = style_key
            cage_alpha = 1.0 if self.view != VIEW_ISO else self.secondary_strength
            self.sink.set_style(CAGE_LAYER, (*CAGE_RGB, cage_alpha))
            self.sink.set_style(ISO_LAYER, (*ISO_RGB, 1.0))
            for layer, rgba in ((ISO_HOVER_LAYER, HOVER_RGBA), (CAGE_HOVER_LAYER, HOVER_RGBA),
                                (ISO_SELECTED_LAYER, SELECTED_RGBA), (CAGE_SELECTED_LAYER, SELECTED_RGBA)):
                self.sink.set_style(layer, rgba)
            self.sink.set_depth(CAGE_LAYER, DEPTH_LEQUAL if self.cage_depth_test else DEPTH_ALWAYS)
            for layer in (ISO_LAYER, ISO_HOVER_LAYER, ISO_SELECTED_LAYER):
                self.sink.set_depth(layer, DEPTH_LEQUAL)
            for layer in (CAGE_HOVER_LAYER, CAGE_SELECTED_LAYER):
                self.sink.set_depth(layer, DEPTH_GREATER)

    def _chains(self, edges) -> list:
        provider = self.provider
        iso = provider.iso_edges()
        d = provider.derived_positions()
        out = []
        for e in sorted(edges, key=int):
            for i in provider.iso_indices_of(e):
                a, b = iso[i]
                out.append((d[a], d[b]))
        return out

    def _cage_segments(self, edges) -> list:
        mesh = self.provider._mesh
        out = []
        for e in sorted(edges, key=int):
            a, b = mesh.edge_vertices(e)
            out.append((tuple(mesh.vertex_position(a)), tuple(mesh.vertex_position(b))))
        return out

    def draw(self, camera_uniforms) -> None:
        layers = self.active_layers()
        if self.sink is None or not layers:
            return
        self.sink.draw(camera_uniforms, layers=layers)


# -- keys (context `subd`, PROVISIONAL) ----------------------------------------------------------

#: Binding context of the SubD keys (`interaction.input.SUBD_CONTEXT`): resolved by
#: `Application.key_press` only when the global context binds nothing for the input, so they can
#: never shadow an app key; `keymap.json` can rebind them in context "subd".

CYCLE_VIEW = commands.SUBD_CYCLE_VIEW
TOGGLE_CAGE_DEPTH = commands.SUBD_TOGGLE_CAGE_DEPTH
CYCLE_SECONDARY = commands.SUBD_CYCLE_SECONDARY
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
    SubdKey(Input("key", "v", frozenset({"alt"})), CYCLE_SECONDARY, "Käfig in der Isolinien-Ansicht: 35 % → 60 % → aus → 15 %"),
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
        self.secondary_strength = DEFAULT_SECONDARY_STRENGTH
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
        self.lines.reset()
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
        self.lines.configure(
            view=self.view, cage_depth_test=self.cage_depth_test, secondary_strength=self.secondary_strength
        )
        if self.enabled:
            self._claim_slot()
        else:
            self.provider.sync(None, None)  # drop derived data and the journal at once
            self._release_slot()

    def set_faces_shown(self, shown: bool) -> None:
        """The app's display mode: without faces (Wireframe) the preview draws no lines."""
        self.lines.configure(faces_shown=bool(shown))

    @property
    def lines_shown(self) -> bool:
        return self.lines.lines_shown

    def toggle_lines(self) -> bool:
        """Shift+D in a SubD view (Manu 2026-10-23, option A): the preview's cage / isoline lines on
        or off; hover / selection highlights (cage edge and chain) stay. View state, sticky across V."""
        self.lines.configure(lines_shown=not self.lines.lines_shown)
        self._set_status("SubD: Linien " + ("an" if self.lines.lines_shown else "aus (nur Highlights)"))
        return self.lines.lines_shown

    def set_secondary_strength(self, strength: float) -> None:
        """Opacity of the secondary line system (the cage in the iso view), 0 = hidden."""
        self.secondary_strength = max(0.0, min(1.0, float(strength)))
        self._apply()

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
        if command == CYCLE_SECONDARY:
            steps = SECONDARY_STEPS
            i = steps.index(self.secondary_strength) if self.secondary_strength in steps else -1
            self.set_secondary_strength(steps[(i + 1) % len(steps)])
            strength = self.secondary_strength
            self._set_status(
                "SubD: Käfig in der Isolinien-Ansicht " + (f"{round(strength * 100)} %" if strength else "aus")
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
