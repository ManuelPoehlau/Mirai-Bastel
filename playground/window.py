"""PlaygroundWindow — pyglet-Fenster für das Artist Playground.

Steuerung: die aktuelle Key-/Maus-Belegung ist in
tools/Input_Mapping_Tool/artist_input_truth.json gepflegt (Source of Truth) —
nicht hier duplizieren, das driftet sonst auseinander. Siehe auch
docs/design/artist_playground/ für den Kontext der Belegung.

Shader:
    _FACE_VERT/_FACE_FRAG    — Phong mit u_use_flat-Uniform (Smooth/Flat).
    _OVERLAY_VERT/_OVERLAY_FRAG — Flat-Color für Edges, Vertices, Selection.

VBO-Struktur:
    _vlist_faces      — GL_TRIANGLES, smooth_normal + flat_normal
    _vlist_edges      — GL_LINES
    _vlist_verts      — GL_POINTS
    _vlist_selection  — GL_TRIANGLES, selektierte Faces (rebuilt on selection change)
"""

from __future__ import annotations

import math

import pyglet
from pyglet import gl
from pyglet.graphics import shader
from pyglet.window import key as _key
from pyglet.window import mouse as _mouse

from playground._paths import ensure_paths

ensure_paths()

from core.selection import SelectionMode  # noqa: E402
from loaders.assets import asset_names  # noqa: E402  # AD-007: geteilte OBJ-Assets
from mirai.viewport.display import DisplayMode  # noqa: E402
from playground.selector import SelectMethod, SelectMode  # noqa: E402
from playground.transformer import (  # noqa: E402
    begin_transform,
    cancel_transform,
    commit_transform,
    update_transform,
)
from playground.app import PlaygroundApp  # noqa: E402
from playground.hud import PlaygroundHUD  # noqa: E402
from playground.input_map import PlaygroundInputMap  # noqa: E402
# AD-013 I4: input_adapter / command_handler are no longer wired into the
# Playground dispatch (single interaction authority). Imports removed with the
# wiring; the modules themselves are untouched.
from playground.slot import ExperimentSlot, VariantEntry  # noqa: E402
from playground.experiments.selection.variant_replace import FaceSelectReplaceExperiment  # noqa: E402
from playground.experiments.selection.variant_modifier import FaceSelectModifierExperiment  # noqa: E402
from playground.experiments.selection.variant_toggle import FaceSelectToggleExperiment  # noqa: E402
from playground.experiments.presentation.variant_shaded import ShadedVariant  # noqa: E402
from playground.experiments.presentation.variant_flat import FlatVariant  # noqa: E402
from playground.experiments.presentation.variant_wireframe import WireframeVariant  # noqa: E402
from playground.experiments.transform.variant_hold import HoldActivationVariant  # noqa: E402
from playground.experiments.transform.variant_press_mode import PressModeVariant  # noqa: E402
from playground.experiments.transform.variant_press_drag_click import PressDragClickVariant  # noqa: E402
from playground.experiments.transform.variant_hold_key_hover import HoldKeyHoverVariant  # noqa: E402
from playground.experiments.tweak.variant_2_silo import TweakV2Silo  # noqa: E402
from playground.experiments.tweak.variant_4_hold_ctrl import TweakV4HoldCtrl  # noqa: E402
# D5 (AD-016): V1 (variant_1_hold_key) moved into Transform as D4; V3
# (variant_3_hold_click) parked (conflicts with D1). Neither is imported here
# since only V2 and V4 are registered below — the modules themselves are
# untouched and still exercised directly by playground/tests/test_tweak.py.
from playground.topology_ops import collapse_selected_edge, split_selected_edge  # noqa: E402
from playground.topology_tools.connect_edges import (  # noqa: E402
    connect_selected_edges,
    TopologyToolError as _ConnectEdgesError,
)
from playground.topology_tools.loop_ring import (  # noqa: E402
    edge_loop,
    edge_ring,
    LoopRingError as _LoopRingError,
)
from playground.topology_tools.loop_insert import (  # noqa: E402
    loop_insert,
    LoopInsertError as _LoopInsertError,
)
from playground.topology_tools.loop_slide import (  # noqa: E402
    LoopSlideTool,
    LoopSlideError as _LoopSlideError,
)
from playground.topology_tools.extrude import ExtrudeTool  # noqa: E402
from playground.experiments.topology.variant_extrude_baseline import ExtrudeBaselineVariant  # noqa: E402
from playground.experiments.topology.variant_extrude_lmb import ExtrudeLmbVariant  # noqa: E402
from playground.topology_tools.contextual_c import CContext, resolve_c_context  # noqa: E402
from playground.topology_tools.connect_per_face import connect_selected_edges_per_face  # noqa: E402
from playground.topology_tools.connect_vertices_per_face import connect_vertices_per_face, VertexConnectError as _VertexConnectError  # noqa: E402
from playground.topology_tools.knife import KnifeTool  # noqa: E402
from playground.topology_tools.knife_pick import (  # noqa: E402
    knife_pick,
    _edge_t_3d as _knife_edge_t_3d,
    ENDPOINT_THRESHOLD as _KNIFE_ENDPOINT_THRESHOLD,
)
from playground.experiments.knife.variant_a import KnifeVariantA  # noqa: E402
from playground.experiments.knife.variant_b import KnifeVariantB  # noqa: E402
from playground.experiments.articulation.articulation import ArticulationState  # noqa: E402
from playground.experiments.articulation.variant_articulation import ArticulationVariant  # noqa: E402
from playground.experiments.tweak._target import (  # noqa: E402
    add_temp_target,
    clear_temp_target,
    has_selection as _tweak_has_selection,
)
from playground.gl_store import PlaygroundPygletStore  # noqa: E402
from playground.renderer import PlaygroundRenderer  # noqa: E402
from playground.selector import (  # noqa: E402
    CLICK_THRESHOLD,
    dispatch_click,
    handle_box_select,
    pick_component,
)
from mirai.viewport.picking import pick_nearest_vertex  # noqa: E402
from playground.transformer import create_tool_for_type  # noqa: E402
from playground.vbo_builder import (  # noqa: E402
    build_edge_data,
    build_face_data,
    build_knife_preview_point_data,
    build_selection_data,
    build_selection_edge_data,
    build_selection_vertex_data,
    build_vertex_data,
)
from playground.gizmo import (  # noqa: E402
    GIZMO_SCALE,
    WORLD_AXES,
    WORLD_PLANES,
    gizmo_mode,
    pick_gizmo_handle,
    hover_gizmo_handle,
    screen_ring_positions,
    axis_line_positions,
    axis_ring_positions,
    arrow_cap_positions,
    box_cap_positions,
    plane_indicator_positions,
)
from mirai.interaction.tools.selection_helpers import (  # noqa: E402
    resolve_selection_vertices,
    selection_pivot,
    selection_normal,
)
from mirai.interaction.tools.transform import _face_tangent_basis  # noqa: E402

# -- Knife helpers -----------------------------------------------------------

def _knife_project_locked_edge(camera, mesh, x, y, width, height, locked_eid):
    """Project cursor ray onto a locked edge, applying endpoint-threshold snap.

    Returns a target dict identical to knife_pick() output but always referencing
    the locked edge — the cursor may be anywhere on screen.
    """
    origin, direction = camera.screen_to_ray(x, y, width, height)
    va, vb = mesh.edge_vertices(locked_eid)
    p0 = mesh.vertex_position(va)
    p1 = mesh.vertex_position(vb)
    t = _knife_edge_t_3d(origin, direction, p0, p1)
    if t <= _KNIFE_ENDPOINT_THRESHOLD:
        return {"kind": "vertex", "vertex_id": va}
    if t >= 1.0 - _KNIFE_ENDPOINT_THRESHOLD:
        return {"kind": "vertex", "vertex_id": vb}
    return {"kind": "edge", "edge_id": locked_eid, "t": t}


# -- Shader-Quellen ----------------------------------------------------------

_FACE_VERT = """
#version 330 core
in vec3 position;
in vec3 smooth_normal;
in vec3 flat_normal;
in vec3 color;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec4 u_base_color;
uniform vec3 u_light_dir;
uniform int u_use_flat;
out vec4 frag_color;
void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    vec3 n = u_use_flat != 0 ? flat_normal : smooth_normal;
    float ndl = max(dot(n, u_light_dir), 0.0);
    vec3 shaded = color * mix(vec3(0.35), vec3(1.0), ndl);
    frag_color = vec4(shaded * u_base_color.rgb, 1.0);
}
"""

_FACE_FRAG = """
#version 330 core
in vec4 frag_color;
out vec4 out_color;
void main() {
    out_color = frag_color;
}
"""

_OVERLAY_VERT = """
#version 330 core
in vec3 position;
uniform mat4 u_view;
uniform mat4 u_proj;
out vec4 frag_color;
uniform vec4 u_color;
void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    frag_color = u_color;
}
"""

_OVERLAY_FRAG = """
#version 330 core
in vec4 frag_color;
out vec4 out_color;
void main() {
    out_color = frag_color;
}
"""

# -- Render-Konstanten -------------------------------------------------------

_DEFAULT_BASE_COLOR = (0.6, 0.7, 0.9, 1.0)
_EDGE_COLOR = (0.15, 0.15, 0.15, 1.0)
_VERTEX_COLOR = (1.0, 0.75, 0.1, 1.0)
_SELECTION_COLOR = (0.95, 0.45, 0.1, 1.0)
_HOVER_COLOR = (0.95, 0.90, 0.35, 0.55)
_VERTEX_POINT_SIZE = 4.0
_LIGHT_DIR_INV = 1.0 / math.sqrt(3.0)

# Gizmo constants (WP-AP-GIZMO-01) — widths/colors are tunable once on screen
# GIZMO_SCALE is the single source of truth (imported from gizmo.py).
_GIZMO_LINE_WIDTH_DEFAULT: float = 2.0
_GIZMO_LINE_WIDTH_HOVER: float = 3.0
_GIZMO_LINE_WIDTH_ACTIVE: float = 4.0
_GIZMO_COLOR_X = (0.9, 0.15, 0.15, 1.0)
_GIZMO_COLOR_Y = (0.15, 0.85, 0.15, 1.0)
_GIZMO_COLOR_Z = (0.15, 0.35, 0.9, 1.0)
_GIZMO_COLOR_SCREEN = (0.75, 0.75, 0.75, 1.0)
_GIZMO_COLOR_PLANE_XY = (0.75, 0.75, 0.15, 1.0)
_GIZMO_COLOR_PLANE_XZ = (0.75, 0.15, 0.75, 1.0)
_GIZMO_COLOR_PLANE_YZ = (0.15, 0.75, 0.75, 1.0)
_GIZMO_COLOR_CENTER = (0.85, 0.85, 0.85, 1.0)
_GIZMO_CAP_SIZE_RATIO: float = 0.12  # engineering default, needs playtest

# Articulation constants (EX-A / H02)
# 0.01 rad/px: 100px drag ≈ 57° bend, feels responsive without being twitchy.
_ARTICULATION_SENSITIVITY: float = 0.01

# Registry-Namen der geteilten OBJ-Assets (AD-007, `examples/loaders/assets.py`).
# `initial_mesh` darf jeden dieser Namen tragen — z. B. "subd_cube", um statt des
# Default-Würfels direkt mit dem SubD-Cube zu starten; "head" bleibt daneben als
# Alias bestehen.
_OBJ_ASSET_NAMES: frozenset[str] = frozenset(asset_names())


def _mesh_bounding_radius(mesh) -> float:
    """Max distance from centroid to any vertex — used as articulation radius.

    Using the full bounding radius means the falloff reaches every vertex
    from any on-surface pivot, so the whole mesh participates in the bend
    regardless of where the artist clicks.
    """
    vids = list(mesh.all_vertex_ids())
    if not vids:
        return 1.0
    positions = [mesh.vertex_position(v) for v in vids]
    cx = sum(p[0] for p in positions) / len(positions)
    cy = sum(p[1] for p in positions) / len(positions)
    cz = sum(p[2] for p in positions) / len(positions)
    return max(
        math.sqrt((p[0] - cx) ** 2 + (p[1] - cy) ** 2 + (p[2] - cz) ** 2)
        for p in positions
    )


def _sel_contains_hovered(sel) -> bool:
    """True if sel.hovered is an element of the active-mode selection set."""
    h = sel.hovered
    if sel.mode is SelectionMode.VERTEX:
        return h in sel.vertices
    if sel.mode is SelectionMode.EDGE:
        return h in sel.edges
    return h in sel.faces


class PlaygroundWindow(pyglet.window.Window):
    """Leichtgewichtiges pyglet-Fenster für das Artist Playground."""

    def __init__(
        self,
        app: PlaygroundApp,
        input_map: PlaygroundInputMap | None = None,
        initial_mesh: str = "cube",
    ) -> None:
        super().__init__(
            1280, 800,
            caption="Mirai-Bastel — Artist Playground [WP-AP-03]",
            resizable=True,
            vsync=True,
        )
        self.app = app
        self.input_map = input_map if input_map is not None else PlaygroundInputMap()

        # AD-010: Szene-/Viewport-Load bewusst ERST HIER, nach
        # pyglet.window.Window.__init__() oben — PlaygroundPygletStore.
        # allocate() braucht einen aktiven GL-Kontext (analog
        # IntegrationLabWindow._add_object() im Integration Lab). Ersetzt
        # einen von einem Aufrufer ggf. vorab headless geladenen
        # (TraceStore-)Viewport durch das echte GL-Backend — z. B. wenn
        # `_diag_screenshot.py` vor der Fenstererzeugung bereits
        # `app.load_head()` für Diagnose-Ausgaben aufgerufen hat.
        self._load_initial_scene(initial_mesh)

        # -- Per-Family Slot-Registry aufbauen --------------------------------
        sel_slot = ExperimentSlot(
            VariantEntry(FaceSelectReplaceExperiment(app)),
            VariantEntry(FaceSelectModifierExperiment(app)),
            VariantEntry(FaceSelectToggleExperiment(app)),
        )
        pres_slot = ExperimentSlot(
            VariantEntry(ShadedVariant(app)),
            VariantEntry(FlatVariant(app)),
            VariantEntry(WireframeVariant(app)),
        )
        trans_slot = ExperimentSlot(
            VariantEntry(PressDragClickVariant(app)),
            VariantEntry(HoldActivationVariant(app)),
            VariantEntry(PressModeVariant(app)),
            VariantEntry(HoldKeyHoverVariant(app)),   # D4 (AD-016)
        )
        # D5 (AD-016): V1 moved into Transform as D4; V3 parked (conflicts with D1).
        # Only V2 and V4 remain as selectable Tweak variants.
        tweak_slot = ExperimentSlot(
            VariantEntry(TweakV2Silo(app)),
            VariantEntry(TweakV4HoldCtrl(app)),
        )
        topo_slot = ExperimentSlot(
            VariantEntry(ExtrudeBaselineVariant(app)),
            VariantEntry(ExtrudeLmbVariant(app)),
        )
        artic_slot = ExperimentSlot(
            VariantEntry(ArticulationVariant(app)),
        )
        knife_slot = ExperimentSlot(
            VariantEntry(KnifeVariantA(app)),
            VariantEntry(KnifeVariantB(app)),
        )
        app.register_slot(sel_slot, "selection")
        app.register_slot(pres_slot, "presentation")
        app.register_slot(trans_slot, "transform")
        app.register_slot(tweak_slot, "tweak")
        app.register_slot(topo_slot, "topology")
        app.register_slot(artic_slot, "articulation")
        app.register_slot(knife_slot, "knife")
        # AD-017 §1.10: connect slot unregistered — C now uses contextual dispatch.
        # Initialzustand anwenden und _active_experiment auf selection setzen,
        # damit M beim ersten Druck die Selection-Family cyclt (nicht id="none").
        pres_slot.active_experiment.activate()
        app.activate_variant("selection", 0)  # setzt _active_experiment + ruft activate() auf

        # AD-013 I4: no second binding authority is constructed here. The
        # Playground resolves its own input in on_key_press/on_key_release.
        # playground/input_adapter.py and playground/command_handler.py are
        # intentionally left in the tree but UNWIRED — removing them is a
        # separate cleanup decision, not part of this ownership restoration.

        self._face_program = shader.ShaderProgram(
            shader.Shader(_FACE_VERT, "vertex"),
            shader.Shader(_FACE_FRAG, "fragment"),
        )
        self._overlay_program = shader.ShaderProgram(
            shader.Shader(_OVERLAY_VERT, "vertex"),
            shader.Shader(_OVERLAY_FRAG, "fragment"),
        )

        if app.viewport is not None:
            self._renderer = PlaygroundRenderer(app.viewport)
        else:
            self._renderer = None

        self._vlist_faces = None
        self._vlist_edges = None
        self._vlist_verts = None
        self._vlist_selection = None
        self._vlist_sel_verts = None
        self._vlist_sel_edges = None
        self._vlist_hover = None
        # WP-STAB-02 (R-SEL-2): window-local (mode, id) hover key. Kept
        # alongside sel.hovered (a bare id, core.selection is frozen) so
        # on_mouse_motion can tell "vertex 5" from "edge 5" apart and never
        # suppress a hover update on a same-numbered id across modes.
        self._hover_key: tuple | None = None
        self._hud_mesh_counts_dirty: bool = True
        self._rebuild_vbo()

        self._hud = PlaygroundHUD(x=10, y_bottom=10, width=self.width - 20)
        self._hud.update_layout(self.width, self.height)
        self._update_hud()

        self._drag_button = None
        self._drag_moved = 0.0

        # Transform-State (AP-04)
        self._transform_key_down = None   # 'x'/'r'/'s' — welche Taste gedrückt wurde
        self._transform_mode_on = False   # True für Press-Mode/Press-Drag-Click (Taste losgelassen, Mode bleibt)
        self._transform_started = False
        self._last_mouse_x = 0
        self._last_mouse_y = 0

        # Tweak family state
        # D2 (AD-016): shared current-tool state (was _tweak_persistent_mode).
        # Set by Q/W/E press (Transform path). V2/V4 read this to know which tool to begin.
        self._current_tool_type: str | None = None
        self._tweak_ctrl_held: bool = False
        self._tweak_active: bool = False    # currently in a Tweak gesture
        self._tweak_started: bool = False   # begin_transform() was called
        self._tweak_tool = None
        self._tweak_temp_target: bool = False  # temporary target was selected
        # V2: Ctrl was held when LMB was pressed
        self._tweak_v2_armed: bool = False

        # D4 (AD-016): temp target captured at Q/W/E press when no selection exists
        self._transform_temp_target: bool = False

        # D3 (AD-016): Gizmo drag state — armed on handle hit, started on first drag
        self._gizmo_drag_armed: bool = False
        self._gizmo_drag_started: bool = False
        self._gizmo_drag_tool = None
        # GIZMO-04: hover state — handle name under cursor, or None
        self._gizmo_hover: str | None = None

        # WP-AXIS-CONSTRAINT-WIRING: sticky axis/plane constraint (X/Y/Z, Shift+X/Y/Z)
        self._axis_constraint: str | None = None
        # WP-AP-INPUT-FIX-03: coordinate space toggle (K) — "world" or "normal"
        self._transform_space: str = "world"

        # Extrude-State (AP-05)
        self._extrude_tool: ExtrudeTool | None = None
        # Loop-Slide-State (AP-05)
        self._loop_slide_tool: LoopSlideTool | None = None
        # Knife-State (AD-017)
        self._knife_tool: KnifeTool | None = None
        # Knife hover VBOs — separate from sel.hovered/_rebuild_hover_vbo (WP-AP-CUT)
        self._vlist_knife_hover_edge = None      # GL_LINES — edge highlight
        self._vlist_knife_hover_vertex = None    # GL_POINTS — vertex hover point
        self._vlist_knife_preview_point = None   # GL_POINTS — split-point preview
        self._vlist_knife_start = None           # GL_POINTS — persistent start vertex
        self._knife_hover_last_target: dict | None = None
        self._knife_last_start = None            # last drawn start vertex id
        # Variant B slide state
        self._knife_slide_armed: bool = False
        self._knife_slide_edge_id = None         # locked edge id during slide

        # Articulation state (EX-A / H02)
        self._articulation_state: ArticulationState | None = None
        self._articulation_dragging: bool = False  # True only during the LMB drag that produces the angle
        self._articulation_press_x: int = 0
        self._articulation_press_y: int = 0

        # Box-Select-State (AP-03 Variante C)
        self._box_start: tuple[int, int] | None = None
        self._box_end: tuple[int, int] | None = None

        # WP-STAB-03: mouse presses the session gate took away from the running
        # session, per button — "camera" (drag navigates) or "blocked" (swallowed).
        # Per button so e.g. an MMB pan during a Tweak-V2 LMB hold can't swallow
        # the LMB release that commits it.
        self._gated_buttons: dict[int, str] = {}

        self.activate()

    # -- Initial-Szene (AD-010: mit echtem GL-Store, nach Kontext) -------------

    def _load_initial_scene(self, initial_mesh: str) -> None:
        """Lädt die Startszene mit `PlaygroundPygletStore` (echtes GL-Backend).

        Einzige Stelle, an der das Live-Fenster eine Szene lädt — Aufrufer
        (run.py, _diag_screenshot.py) übergeben nur noch die gewünschte
        Szene als String, statt selbst `app.load_*()` mit einem Store-Typ
        aufzurufen (der vor Fenster-/Kontext-Erzeugung ohnehin nicht
        GL-fähig wäre).

        Gültige Werte: `"cube"` (Default), `"head"`, `"cylinder"`, `"grid"`
        sowie jeder Registry-Name der geteilten OBJ-Assets (AD-007,
        `_OBJ_ASSET_NAMES`) — z. B. `"subd_cube"` oder
        `"man_with_shoes_basemesh"`. Alles Unbekannte fällt auf den Würfel
        zurück (bestehendes Verhalten).
        """
        if initial_mesh == "head":
            self.app.load_head(store_type=PlaygroundPygletStore)
        elif initial_mesh in _OBJ_ASSET_NAMES:
            # Geteiltes Asset aus examples/meshes über die Registratur (AD-007).
            self.app.load_asset(initial_mesh, store_type=PlaygroundPygletStore)
        elif initial_mesh == "cylinder":
            self.app.load_cylinder(store_type=PlaygroundPygletStore)
        elif initial_mesh == "grid":
            self.app.load_grid(store_type=PlaygroundPygletStore)
        else:
            self.app.load_cube(store_type=PlaygroundPygletStore)

    # -- VBO-Aufbau -----------------------------------------------------------

    def _clear_hover(self) -> None:
        """Reset hover state (sel.hovered, the window-local hover key, and the
        hover overlay VBO). Call on any component-mode change and on Knife-begin
        (WP-STAB-02 / R-SEL-2) so a stale or wrong-kind hover from before the
        switch never carries into the new mode/session.
        """
        self.app.scene.selection.hovered = None
        self._hover_key = None
        if self._vlist_hover is not None:
            self._vlist_hover.delete()
            self._vlist_hover = None

    def _rebuild_vbo(self) -> None:
        """Alle Mesh-VBOs (Faces, Edges, Vertices) neu bauen. Selection-VBO separat."""
        self._hud_mesh_counts_dirty = True
        for vlist in (self._vlist_faces, self._vlist_edges, self._vlist_verts,
                      self._vlist_selection, self._vlist_hover):
            if vlist is not None:
                vlist.delete()
        self._vlist_faces = None
        self._vlist_edges = None
        self._vlist_verts = None
        self._vlist_selection = None
        self._vlist_hover = None
        if self.app.viewport is not None:
            self._clear_hover()

        if self.app.viewport is None:
            return

        if self.app.viewport is not None:
            self._renderer = PlaygroundRenderer(self.app.viewport)

        mesh = self.app.viewport.render_mesh.mesh
        derived = self.app.viewport.render_mesh.derived

        face_positions, smooth_normals, flat_normals, colors = build_face_data(mesh, derived)
        n_face_verts = len(face_positions) // 3
        if n_face_verts > 0:
            self._vlist_faces = self._face_program.vertex_list(
                n_face_verts,
                gl.GL_TRIANGLES,
                position=("f", face_positions),
                smooth_normal=("f", smooth_normals),
                flat_normal=("f", flat_normals),
                color=("f", colors),
            )

        edge_positions = build_edge_data(mesh)
        n_edge_verts = len(edge_positions) // 3
        if n_edge_verts > 0:
            self._vlist_edges = self._overlay_program.vertex_list(
                n_edge_verts,
                gl.GL_LINES,
                position=("f", edge_positions),
            )

        vert_positions = build_vertex_data(mesh)
        n_verts = len(vert_positions) // 3
        if n_verts > 0:
            self._vlist_verts = self._overlay_program.vertex_list(
                n_verts,
                gl.GL_POINTS,
                position=("f", vert_positions),
            )

        # R-SEL-1 (WP-STAB-01): a mesh-topology rebuild invalidates the old
        # selection overlay VBOs (they reference vertex/edge/face ids from
        # the pre-rebuild mesh) even when they were not explicitly deleted
        # above. Rebuild all three overlays here so they always match the
        # current Selection after split/collapse/undo/loop-insert/loop-slide
        # etc. — callers no longer need a manual follow-up call for this.
        self._rebuild_selection_vbo()

    def _rebuild_selection_vbo(self) -> None:
        """Selection-VBOs für alle Komponenten-Modi neu bauen.

        Wird nach jedem Click und nach Moduswechsel aufgerufen.
        """
        for vlist in (self._vlist_selection, self._vlist_sel_verts, self._vlist_sel_edges):
            if vlist is not None:
                vlist.delete()
        self._vlist_selection = None
        self._vlist_sel_verts = None
        self._vlist_sel_edges = None

        if self.app.viewport is None:
            return

        mesh = self.app.viewport.render_mesh.mesh
        selection = self.app.scene.selection

        if selection.mode is SelectionMode.FACE and selection.faces:
            positions = build_selection_data(mesh, selection.faces)
            n = len(positions) // 3
            if n > 0:
                self._vlist_selection = self._overlay_program.vertex_list(
                    n,
                    gl.GL_TRIANGLES,
                    position=("f", positions),
            )

        elif selection.mode is SelectionMode.VERTEX and selection.vertices:
            positions = build_selection_vertex_data(mesh, selection.vertices)
            n = len(positions) // 3
            if n > 0:
                self._vlist_sel_verts = self._overlay_program.vertex_list(
                    n, gl.GL_POINTS, position=("f", positions),
                )

        elif selection.mode is SelectionMode.EDGE and selection.edges:
            positions = build_selection_edge_data(mesh, selection.edges)
            n = len(positions) // 3
            if n > 0:
                self._vlist_sel_edges = self._overlay_program.vertex_list(
                    n, gl.GL_LINES, position=("f", positions),
                )

    def _rebuild_hover_vbo(self) -> None:
        """Hover-Highlight-VBO für das nächste Element unter dem Cursor."""
        if self._vlist_hover is not None:
            self._vlist_hover.delete()
            self._vlist_hover = None

        if self.app.viewport is None:
            return

        sel = self.app.scene.selection
        hovered = sel.hovered
        if hovered is None:
            return

        mesh = self.app.viewport.render_mesh.mesh
        if sel.mode is SelectionMode.VERTEX:
            positions = build_selection_vertex_data(mesh, {hovered})
            prim = gl.GL_POINTS
        elif sel.mode is SelectionMode.EDGE:
            positions = build_selection_edge_data(mesh, {hovered})
            prim = gl.GL_LINES
        else:
            positions = build_selection_data(mesh, {hovered})
            prim = gl.GL_TRIANGLES

        n = len(positions) // 3
        if n > 0:
            self._vlist_hover = self._overlay_program.vertex_list(
                n, prim, position=("f", positions),
            )

    # -- HUD-Update -----------------------------------------------------------

    def _update_hud(self) -> None:
        cam = self.app.camera
        self._hud.update_camera(cam.yaw, cam.pitch, cam.distance)
        if self._hud_mesh_counts_dirty:
            mesh = self.app.viewport.render_mesh.mesh if self.app.viewport else None
            if mesh is not None:
                v_count = len(list(mesh.all_vertex_ids()))
                e_count = len(list(mesh.all_edge_ids()))
                f_count = len(list(mesh.all_face_ids()))
                self._hud.update_mesh(v_count, e_count, f_count)
            self._hud_mesh_counts_dirty = False
        self._hud.update_setting(self.app.slots)
        focused_slot = self.app.slots.get(self.app.focused_family)
        focused_exp = focused_slot.active_experiment if focused_slot else self.app.active_experiment
        self._hud.update_experiment(focused_exp)
        display_label = self.app.display_state.label
        if self.app.show_vertices:
            display_label += " + V"
        self._hud.update_display(display_label)
        sel = self.app.scene.selection if self.app.viewport is not None else None
        if sel is not None:
            comp = sel.mode
            if comp is SelectionMode.VERTEX:
                n_sel = len(sel.vertices)
            elif comp is SelectionMode.EDGE:
                n_sel = len(sel.edges)
            else:
                n_sel = len(sel.faces)
            comp_label = comp.name.capitalize()
        else:
            n_sel, comp_label = 0, "Face"
        mode_label   = self.app.select_mode.name.capitalize()
        method_label = self.app.select_method.name.capitalize()
        self._hud.update_selection(n_sel, f"{mode_label}/{method_label}", comp_label)

    # -- Transform-Sync -------------------------------------------------------

    def _recompute_derived(self) -> None:
        if self.app.viewport is not None:
            mesh = self.app.viewport.render_mesh.mesh
            derived = self.app.viewport.render_mesh.derived
            derived.full_recompute(mesh)

    def _sync_after_transform(self) -> None:
        """VBOs nach einer Transform-Operation (update oder commit/cancel) neu bauen."""
        sel = self.app.scene.selection
        if (
            self._tweak_started
            and sel.mode is SelectionMode.VERTEX
            and len(sel.vertices) == 1
            and self.app.viewport is not None
        ):
            self._patch_vbo_single_vertex(next(iter(sel.vertices)))
        else:
            self._recompute_derived()
            self._rebuild_vbo()
        self._push_camera()

    def _patch_vbo_single_vertex(self, vid) -> None:
        """In-place VBO patch for a single-vertex Tweak move.

        Patches only the slots affected by moving `vid`: position and normals
        in _vlist_faces; position in _vlist_edges, _vlist_verts, _vlist_sel_verts.
        GPU buffers are updated in-place via set_region() — no VBO reallocation.
        """
        from viewport.derived import triangulate_face  # noqa: E402

        mesh = self.app.viewport.render_mesh.mesh
        derived = self.app.viewport.render_mesh.derived

        # Recompute derived geometry for the affected neighborhood.
        # (update_transform moves the mesh without calling viewport.sync, so
        # derived is stale at this point — same partial-update path as _sync_geometry.)
        affected_faces, affected_vertices = derived.affected_neighborhood(mesh, {vid})
        derived.update_face_normals(mesh, affected_faces)
        derived.update_vertex_normals(mesh, affected_vertices)

        new_pos = list(mesh.vertex_position(vid))
        nbhd_normals = {
            v: list(derived.vertex_normals.get(v, (0.0, 1.0, 0.0)))
            for v in affected_vertices
        }

        # Face VBO: position of vid, smooth_normal of 1-ring, flat_normal of affected faces.
        if self._vlist_faces is not None:
            pos_buf  = self._vlist_faces.domain.attrib_name_buffers["position"]
            snrm_buf = self._vlist_faces.domain.attrib_name_buffers["smooth_normal"]
            fnrm_buf = self._vlist_faces.domain.attrib_name_buffers["flat_normal"]
            flat_slot = self._vlist_faces.start
            for fid in mesh.all_face_ids():
                boundary = mesh.face_vertices(fid)
                is_affected = fid in affected_faces
                face_normal = (
                    list(derived.face_normals.get(fid, (0.0, 1.0, 0.0)))
                    if is_affected else None
                )
                for a, b, c in triangulate_face(boundary):
                    for slot_vid in (a, b, c):
                        if slot_vid == vid:
                            pos_buf.set_region(flat_slot, 1, new_pos)
                        if slot_vid in affected_vertices:
                            snrm_buf.set_region(flat_slot, 1, nbhd_normals[slot_vid])
                        if is_affected:
                            fnrm_buf.set_region(flat_slot, 1, face_normal)
                        flat_slot += 1

        # Edge VBO: position of vid in each incident edge.
        if self._vlist_edges is not None:
            pos_buf = self._vlist_edges.domain.attrib_name_buffers["position"]
            flat_slot = self._vlist_edges.start
            for eid in mesh.all_edge_ids():
                va, vb = mesh.edge_vertices(eid)
                if va == vid:
                    pos_buf.set_region(flat_slot, 1, new_pos)
                if vb == vid:
                    pos_buf.set_region(flat_slot + 1, 1, new_pos)
                flat_slot += 2

        # Vertex VBO: position of vid.
        if self._vlist_verts is not None:
            pos_buf = self._vlist_verts.domain.attrib_name_buffers["position"]
            verts_start = self._vlist_verts.start
            for flat_slot, v in enumerate(mesh.all_vertex_ids()):
                if v == vid:
                    pos_buf.set_region(verts_start + flat_slot, 1, new_pos)
                    break

        # Selection VBO: single selected vertex highlight.
        if self._vlist_sel_verts is not None:
            pos_buf = self._vlist_sel_verts.domain.attrib_name_buffers["position"]
            pos_buf.set_region(self._vlist_sel_verts.start, 1, new_pos)

    def _active_transform_model(self) -> str:
        """Aktivierungsmodell des aktiven Transform-Slots lesen."""
        slot = self.app.slots.get("transform")
        if slot is None:
            return "hold"
        return getattr(slot.active_experiment, "activation", "hold")

    def _clear_transform_state(self) -> None:
        """Alle Transform-State-Flags zurücksetzen (nach Commit, Cancel oder Slot-Wechsel)."""
        self._transform_key_down = None
        self._transform_mode_on = False
        self._transform_started = False
        self.app.active_tool = None
        self._hud.update_action("—")

    def _transform_arm(self, x: int, y: int) -> bool:
        """WP-STAB-04: selection-or-hover fallback shared by all Transform activation
        models, mirroring _tweak_begin()'s rule (selection non-empty → use it as-is;
        empty → hit-test and add a temp target). Unlike Tweak, Transform arms at key
        press but only calls begin_transform() lazily on the first drag/motion, so this
        only resolves *what* will be transformed — not the gesture itself.

        Returns True if there is something to transform (selection or hit under the
        cursor), False if both are empty and the caller must refuse.
        """
        sel = self.app.scene.selection
        if _tweak_has_selection(sel):
            # WP-STAB-11: same clear-on-arm rule as _tweak_begin.
            if sel.hovered is not None and _sel_contains_hovered(sel):
                self._clear_hover()
            return True
        if self.app.viewport is None:
            return False
        mesh = self.app.viewport.render_mesh.mesh
        hit = pick_component(self.app.camera, mesh, sel, x, y, self.width, self.height)
        if hit is None:
            return False
        add_temp_target(sel, hit)
        self._transform_temp_target = True
        self._rebuild_selection_vbo()
        # WP-STAB-11: same clear-on-arm rule as _tweak_begin.
        if sel.hovered is not None and sel.hovered == hit:
            self._clear_hover()
        return True

    def _clear_transform_temp_target(self) -> None:
        """WP-STAB-04: teardown counterpart of _transform_arm(), mirroring the Tweak
        temp-target clear + overlay rebuild fixed for Tweak in WP-STAB-08."""
        if self._transform_temp_target:
            clear_temp_target(self.app.scene.selection)
            self._transform_temp_target = False
            self._rebuild_selection_vbo()

    # -- Session Gate (WP-STAB-03) --------------------------------------------

    def _active_session(self) -> str | None:
        """Which modal session currently owns input, read from the existing flags.

        Articulation counts only while its LMB drag is live: the bent-but-idle
        pose is designed to coexist with other tools (topology handlers
        auto-restore it, the mouse is explicitly "free for camera" afterwards).
        """
        if self._knife_tool is not None:
            return "knife"
        if self._articulation_dragging:
            return "articulation"
        if self._loop_slide_tool is not None:
            return "loop_slide"
        if self._extrude_tool is not None:
            return "extrude"
        if self._tweak_active or self._tweak_v2_armed:
            return "tweak"
        if self._gizmo_drag_armed:
            return "gizmo"
        if self._transform_key_down is not None or self._transform_mode_on:
            return "transform"
        return None

    def _session_owns_key(self, session: str, symbol: int, modifiers: int) -> bool:
        """Q4 (2026-09-23): only the owning session's own keys plus Esc pass the gate.

        Key *releases* are not gated — every release branch already checks its
        own session flag, and with presses gated no foreign session can exist.
        """
        if symbol == _key.ESCAPE:
            return True
        if session == "knife":
            if symbol in (_key.ENTER, _key.NUM_ENTER):
                return True
            # In-session undo/redo (AD-017): Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y.
            return bool(modifiers & _key.MOD_CTRL) and symbol in (_key.Z, _key.Y)
        if session == "articulation":
            return symbol == _key.F
        if session == "tweak":
            # V4 commits on Ctrl release; V2 may see Ctrl re-pressed while LMB is held.
            return symbol in (_key.LCTRL, _key.RCTRL)
        if session == "transform":
            if symbol in (_key.X, _key.Y, _key.Z):
                return not (modifiers & _key.MOD_CTRL)
            if symbol == _key.K:
                return not modifiers
            if symbol in (_key.Q, _key.W, _key.E) and not (modifiers & _key.MOD_SHIFT):
                # Only the key of the tool already running, and only in the press
                # models where a second press is the commit gesture. A different
                # key would swap app.active_tool under a started transform.
                tool = {_key.Q: "move", _key.W: "rotate", _key.E: "scale"}[symbol]
                return (
                    self._active_transform_model() in ("press_mode", "press_drag_click")
                    and tool == self._current_tool_type
                )
        return False

    @staticmethod
    def _is_camera_press(button: int, modifiers: int) -> bool:
        """Same button/modifier classification as the camera fallback in on_mouse_drag."""
        if button == _mouse.MIDDLE:
            return True
        return button in (_mouse.LEFT, _mouse.RIGHT) and bool(
            modifiers & (_key.MOD_ALT | _key.MOD_SHIFT)
        )

    def _session_owns_press(self, session: str, button: int) -> bool:
        """Mouse buttons that are part of a running session's own gesture."""
        if button != _mouse.LEFT:
            return False
        if session == "knife":
            return True
        if session == "extrude":
            return self._active_extrude_model() == "lmb"
        if session == "transform":
            return self._active_transform_model() == "press_drag_click"
        # Tweak V2, Gizmo and Articulation already hold LMB; a second press is foreign.
        return False

    def _camera_navigate(self, dx: int, dy: int, modifiers: int) -> None:
        # Orbit: Alt+LMB (oder Alt+RMB) — Alt freihält LMB für Selection/Tools
        is_orbit = (
            self._drag_button in (_mouse.LEFT, _mouse.RIGHT)
            and modifiers & _key.MOD_ALT
        )
        is_pan = self._drag_button == _mouse.MIDDLE or (
            self._drag_button in (_mouse.LEFT, _mouse.RIGHT)
            and modifiers & _key.MOD_SHIFT
        )
        if is_pan:
            self.app.camera.pan(dx, dy, self.width, self.height)
        elif is_orbit:
            self.app.camera.orbit(-dx * 0.005, -dy * 0.005)
        self._push_camera()

    def _gizmo_handle_at(self, x: int, y: int) -> str | None:
        """Gizmo handle under the cursor for the current selection, or None."""
        if self.app.viewport is None or self.app.scene.selection.is_empty():
            return None
        mesh = self.app.viewport.render_mesh.mesh
        derived = self.app.viewport.render_mesh.derived
        sel = self.app.scene.selection
        vertex_ids = resolve_selection_vertices(mesh, sel, sel.mode)
        if not vertex_ids:
            return None
        pivot = selection_pivot(mesh, vertex_ids)
        mode = gizmo_mode(sel, self._transform_space, self._axis_constraint)
        return pick_gizmo_handle(
            self.app.camera, pivot, mode, self._transform_space,
            sel, mesh, derived, x, y, self.width, self.height,
            current_tool=self._current_tool_type or "move",
        )

    # -- Articulation-Helpers -------------------------------------------------

    def _articulation_auto_restore(self) -> bool:
        """Restore articulation session if active. Returns True if a restore happened.

        Caller is responsible for VBO rebuild and HUD update — this method only
        ends the session so topology operations execute against exact rest geometry.
        """
        if self._articulation_state is not None and self._articulation_state.is_bent:
            self._articulation_state.restore()
            self._articulation_state = None
            self._articulation_dragging = False
            return True
        return False

    # -- Tweak-Helpers --------------------------------------------------------

    def _active_extrude_model(self) -> str:
        """Aktivierungsmodell des aktiven Extrude-Slots ('hold' oder 'lmb')."""
        slot = self.app.slots.get("topology")
        if slot is None:
            return "hold"
        return getattr(slot.active_experiment, "activation", "hold")

    def _active_tweak_variant(self) -> str | None:
        """Aktive Tweak-Variante lesen ('v1'/'v2'/'v3'/'v4' oder None)."""
        slot = self.app.slots.get("tweak")
        if slot is None:
            return None
        return getattr(slot.active_experiment, "tweak_variant", None)

    def _active_knife_model(self) -> str:
        """Aktivierungsmodell des aktiven Knife-Slots lesen."""
        slot = self.app.slots.get("knife")
        if slot is None:
            return "live_preview"
        return getattr(slot.active_experiment, "activation", "live_preview")

    def _clear_knife_hover_vbos(self) -> None:
        """Ephemeral Knife hover VBOs freigeben (per-motion-frame state)."""
        if self._vlist_knife_hover_edge is not None:
            self._vlist_knife_hover_edge.delete()
            self._vlist_knife_hover_edge = None
        if self._vlist_knife_hover_vertex is not None:
            self._vlist_knife_hover_vertex.delete()
            self._vlist_knife_hover_vertex = None
        if self._vlist_knife_preview_point is not None:
            self._vlist_knife_preview_point.delete()
            self._vlist_knife_preview_point = None
        self._knife_hover_last_target = None

    def _clear_knife_start_vbo(self) -> None:
        """Persistent start-vertex VBO freigeben (session end only)."""
        if self._vlist_knife_start is not None:
            self._vlist_knife_start.delete()
            self._vlist_knife_start = None
        self._knife_last_start = None

    def _tweak_begin(self, tool_type: str, x: int, y: int) -> bool:
        """Selection-Fallback auflösen, Tool erstellen und begin_transform() aufrufen.

        Returns True wenn die Geste erfolgreich gestartet wurde.
        """
        if self.app.viewport is None:
            return False
        sel = self.app.scene.selection
        if not _tweak_has_selection(sel):
            mesh = self.app.viewport.render_mesh.mesh
            hit = pick_component(self.app.camera, mesh, sel, x, y, self.width, self.height)
            if hit is None:
                return False
            add_temp_target(sel, hit)
            self._tweak_temp_target = True
            # WP-STAB-08: add_temp_target() mutates sel.vertices/.edges/.faces
            # directly — without this, the highlight overlay VBO (built from
            # the pre-gesture Selection) stays whatever it was before (usually
            # None), so no highlight is drawn for the whole temp-target
            # gesture. _tweak_commit()/_tweak_cancel() already rebuild it on
            # the way out (after clear_temp_target()); this is the missing
            # rebuild on the way in.
            self._rebuild_selection_vbo()

        # WP-STAB-11: once the gesture's target is resolved, hovering and
        # "being the active target" are mutually exclusive — clear the marker.
        if sel.hovered is not None and _sel_contains_hovered(sel):
            self._clear_hover()

        self._tweak_tool = create_tool_for_type(tool_type)
        _space = "normal" if self._transform_space == "normal" else None
        success = begin_transform(
            self._tweak_tool, self.app.scene, self.app.camera, sel,
            axis=self._axis_constraint, space=_space,
            derived_geometry=self.app.viewport.render_mesh.derived,
        )
        if success:
            self._tweak_active = True
            self._tweak_started = True
        else:
            if self._tweak_temp_target:
                clear_temp_target(sel)
                self._tweak_temp_target = False
            self._tweak_tool = None
        return success

    def _tweak_commit(self) -> None:
        """Aktive Tweak-Geste committen."""
        if self._tweak_started and self._tweak_tool is not None:
            commit_transform(self._tweak_tool)
        self._sync_after_transform()
        if self._tweak_temp_target:
            clear_temp_target(self.app.scene.selection)
            self._tweak_temp_target = False
            self._rebuild_selection_vbo()
        self._clear_tweak_gesture()

    def _tweak_cancel(self) -> None:
        """Aktive Tweak-Geste abbrechen."""
        if self._tweak_started and self._tweak_tool is not None:
            cancel_transform(self._tweak_tool)
        self._sync_after_transform()
        if self._tweak_temp_target:
            clear_temp_target(self.app.scene.selection)
            self._tweak_temp_target = False
            self._rebuild_selection_vbo()
        self._clear_tweak_gesture()

    def _clear_tweak_gesture(self) -> None:
        """Tweak-Gesten-Flags zurücksetzen (nicht persistent mode/ctrl/key state)."""
        self._tweak_active = False
        self._tweak_started = False
        self._tweak_tool = None
        self._tweak_v2_armed = False

    # -- Kamera-Push ----------------------------------------------------------

    def _push_camera(self) -> None:
        if self.height == 0:
            return
        aspect = self.width / self.height
        if self._renderer is not None:
            self._renderer.notify_camera_changed(aspect=aspect)
            self._renderer.sync()

    # -- Events ---------------------------------------------------------------

    def on_resize(self, width: int, height: int) -> None:
        if height == 0:
            return pyglet.event.EVENT_HANDLED
        self._hud.update_layout(width, height)
        self._push_camera()
        pyglet.clock.schedule_once(lambda dt: self.flip(), 0)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        self._drag_button = button
        self._drag_moved = 0.0
        self._gated_buttons.pop(button, None)

        # WP-STAB-03 Session Gate: while a session owns input, a press is either
        # camera navigation, the session's own gesture, or swallowed. The
        # Articulation / Gizmo-arm / Tweak-V2-arm / Box-start branches below only
        # run when no session is live — each would otherwise start a second,
        # concurrent session (or rubber band) inside the running one.
        session = self._active_session()
        if session is not None:
            if self._is_camera_press(button, modifiers):
                self._gated_buttons[button] = "camera"
                return pyglet.event.EVENT_HANDLED
            if session == "transform" and button == _mouse.LEFT:
                hit = self._gizmo_handle_at(x, y)
                if hit is not None:
                    # D3 (AD-016): a handle click is the X/Y/Z equivalent, which
                    # the Transform session owns. It must not arm a second tool —
                    # the running Transform executes the drag, and in
                    # Press-Drag-Click the LMB release still commits it.
                    self._axis_constraint = hit
                    self._gizmo_hover = None
                    self._hud.update_constraint(self._axis_constraint)
                    return pyglet.event.EVENT_HANDLED
            if not self._session_owns_press(session, button):
                self._gated_buttons[button] = "blocked"
                return pyglet.event.EVENT_HANDLED

        # Articulation: LMB press when articulation family is focused starts a bend gesture.
        # Axis: computed per-frame from drag direction — see on_mouse_drag.
        # Radius: full bounding radius — every vertex participates regardless of pivot location.
        if (
            session is None
            and button == _mouse.LEFT
            and not (modifiers & _key.MOD_ALT)
            and self.app.focused_family == "articulation"
            and self.app.viewport is not None
        ):
            mesh = self.app.viewport.render_mesh.mesh
            vid = pick_nearest_vertex(self.app.camera, mesh, x, y, self.width, self.height)
            if vid is not None:
                pivot = mesh.vertex_position(vid)
                radius = _mesh_bounding_radius(mesh)
                if self._articulation_state is not None:
                    self._articulation_state.restore()
                # Axis is a placeholder; it is overridden on every drag update before update() is called.
                self._articulation_state = ArticulationState(mesh, pivot, (0.0, 1.0, 0.0), radius)
                self._articulation_state.begin()
                self._articulation_press_x = x
                self._articulation_press_y = y
                self._articulation_dragging = True
                self._rebuild_vbo()
                self._hud.update_action("Articulation — drag to bend, F = restore")
                self._update_hud()
                self.activate()
                return pyglet.event.EVENT_HANDLED

        # Gizmo click/drag: D3 (AD-016) — hit on a handle sets the axis constraint;
        # a subsequent drag executes the current tool along that axis.
        # Works whether or not a transform is currently armed (precondition removed).
        if session is None and button == _mouse.LEFT and not (modifiers & _key.MOD_ALT):
            hit = self._gizmo_handle_at(x, y)
            if hit is not None:
                self._axis_constraint = hit
                self._gizmo_hover = None
                self._hud.update_constraint(self._axis_constraint)
                # Arm gizmo drag: click-only = constraint only; LMB+drag = execute tool
                _gt = self._current_tool_type or "move"
                self._gizmo_drag_tool = create_tool_for_type(_gt)
                self._gizmo_drag_armed = True
                return pyglet.event.EVENT_HANDLED

        tv = self._active_tweak_variant()
        if session is None and button == self.input_map.select_button:
            if tv == "v2" and self._tweak_ctrl_held:
                # V2: Ctrl was held at LMB press → arm Tweak (Ctrl may now be released)
                self._tweak_v2_armed = True
                self.activate()
                return pyglet.event.EVENT_HANDLED

        # Knife Variant B: LMB press on valid edge = arm slide (WP-AP-CUT)
        if (
            button == _mouse.LEFT
            and self._knife_tool is not None
            and self.app.viewport is not None
            and self._active_knife_model() == "press_slide_release"
        ):
            mesh = self.app.viewport.render_mesh.mesh
            target = knife_pick(self.app.camera, mesh, x, y, self.width, self.height)
            hover_result = self._knife_tool.hover(target)
            if target.get("kind") == "edge" and hover_result.get("valid", False):
                self._knife_slide_armed = True
                eid = target["edge_id"]
                self._knife_slide_edge_id = eid
                self._clear_knife_hover_vbos()
                self._knife_hover_last_target = target
                edge_positions = build_selection_edge_data(mesh, {eid})
                if edge_positions:
                    self._vlist_knife_hover_edge = self._overlay_program.vertex_list(
                        len(edge_positions) // 3, gl.GL_LINES,
                        position=("f", edge_positions),
                    )
                t = target["t"]
                va, vb = mesh.edge_vertices(eid)
                p0 = mesh.vertex_position(va)
                p1 = mesh.vertex_position(vb)
                world_pos = (
                    p0[0] + t * (p1[0] - p0[0]),
                    p0[1] + t * (p1[1] - p0[1]),
                    p0[2] + t * (p1[2] - p0[2]),
                )
                pt_positions = build_knife_preview_point_data(world_pos)
                self._vlist_knife_preview_point = self._overlay_program.vertex_list(
                    1, gl.GL_POINTS,
                    position=("f", pt_positions),
                )
                return pyglet.event.EVENT_HANDLED

        if (
            session is None
            and self.app.select_method is SelectMethod.BOX
            and button == self.input_map.select_button
        ):
            self._box_start = (x, y)
            self._box_end = (x, y)
        self.activate()

    def on_mouse_drag(
        self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int
    ) -> None:
        self._last_mouse_x = x
        self._last_mouse_y = y
        self._drag_moved += abs(dx) + abs(dy)

        # WP-STAB-03: camera navigation pressed during a session always reaches
        # the camera — the session drag branches below (Loop Slide, Extrude,
        # Tweak, Transform) consume every drag regardless of modifiers.
        if self._gated_buttons.get(self._drag_button) == "camera":
            self._camera_navigate(dx, dy, modifiers)
            return pyglet.event.EVENT_HANDLED

        # Knife Variant B: LMB drag while slide armed = update preview (WP-AP-CUT)
        if self._knife_slide_armed and self._knife_tool is not None and self.app.viewport is not None:
            if buttons & _mouse.LEFT and self._knife_slide_edge_id is not None:
                mesh = self.app.viewport.render_mesh.mesh
                # Project onto locked edge — cursor may be anywhere on screen
                target = _knife_project_locked_edge(
                    self.app.camera, mesh, x, y, self.width, self.height,
                    self._knife_slide_edge_id,
                )
                hover_result = self._knife_tool.hover(target)
                self._clear_knife_hover_vbos()
                self._knife_hover_last_target = target
                kind = target.get("kind")
                if kind == "edge":
                    eid = target["edge_id"]
                    edge_positions = build_selection_edge_data(mesh, {eid})
                    if edge_positions:
                        self._vlist_knife_hover_edge = self._overlay_program.vertex_list(
                            len(edge_positions) // 3, gl.GL_LINES,
                            position=("f", edge_positions),
                        )
                    t = target["t"]
                    va, vb = mesh.edge_vertices(eid)
                    p0 = mesh.vertex_position(va)
                    p1 = mesh.vertex_position(vb)
                    world_pos = (
                        p0[0] + t * (p1[0] - p0[0]),
                        p0[1] + t * (p1[1] - p0[1]),
                        p0[2] + t * (p1[2] - p0[2]),
                    )
                    pt_positions = build_knife_preview_point_data(world_pos)
                    self._vlist_knife_preview_point = self._overlay_program.vertex_list(
                        1, gl.GL_POINTS,
                        position=("f", pt_positions),
                    )
                elif kind == "vertex":
                    # Endpoint snap — show vertex highlight instead of mid-edge point
                    vid = target["vertex_id"]
                    positions = build_selection_vertex_data(mesh, {vid})
                    if positions:
                        self._vlist_knife_hover_vertex = self._overlay_program.vertex_list(
                            len(positions) // 3, gl.GL_POINTS,
                            position=("f", positions),
                        )
            return pyglet.event.EVENT_HANDLED

        # Articulation: consume the drag while the gesture is active (EX-A / H02).
        # Axis is derived from the total drag vector so the visible bend direction matches
        # the drag direction on screen:
        #   drag right (+dx) → axis = -forward → top moves screen-right
        #   drag up   (+dy) → axis = +right   → top moves away from camera
        # Derivation: for a vertical mesh, v = axis × (top - pivot). We want v ∝ screen_right
        # for a right drag, so axis ∝ -forward. For v ∝ screen_depth for an up drag, axis ∝ right.
        # Combined: axis = normalize(-total_dx * forward + total_dy * right).
        # Once released, _articulation_dragging is False and camera navigation resumes
        # through the normal event path below — no special-casing needed there.
        if self._articulation_dragging and self._articulation_state is not None:
            total_dx = x - self._articulation_press_x
            total_dy = y - self._articulation_press_y
            dist = math.sqrt(total_dx * total_dx + total_dy * total_dy)
            if dist > 0.5:
                forward, right, _ = self.app.camera.basis()
                ax = total_dx * forward[0] - total_dy * right[0]
                ay = total_dx * forward[1] - total_dy * right[1]
                az = total_dx * forward[2] - total_dy * right[2]
                self._articulation_state.axis = (ax / dist, ay / dist, az / dist)
                self._articulation_state.update(dist * _ARTICULATION_SENSITIVITY)
                self._rebuild_vbo()
            return pyglet.event.EVENT_HANDLED

        # Loop Slide: Drag-Update (AP-05)
        if self._loop_slide_tool is not None:
            self._loop_slide_tool.update(dx=float(dx), dy=float(dy), width=self.width, height=self.height)
            self._rebuild_vbo()
            return pyglet.event.EVENT_HANDLED

        # Extrude: Drag-Update (AP-05)
        if self._extrude_tool is not None:
            em = self._active_extrude_model()
            if em == "hold" or (em == "lmb" and buttons & _mouse.LEFT):
                self._extrude_tool.update(dx=float(dx), dy=float(dy), width=self.width, height=self.height)
                self._rebuild_vbo()
            return pyglet.event.EVENT_HANDLED

        # Tweak: running gesture update (V2/V4 — LMB governs)
        if self._tweak_active and self._tweak_started and self._tweak_tool is not None:
            update_transform(self._tweak_tool, float(dx), float(dy), self.width, self.height)
            self._sync_after_transform()
            return pyglet.event.EVENT_HANDLED

        # Gizmo drag: D3 (AD-016) — gizmo handle was hit at press; execute tool on drag
        if self._gizmo_drag_armed and self._gizmo_drag_tool is not None and self.app.viewport is not None:
            if not self._gizmo_drag_started:
                _space = "normal" if self._transform_space == "normal" else None
                success = begin_transform(
                    self._gizmo_drag_tool,
                    self.app.scene,
                    self.app.camera,
                    self.app.scene.selection,
                    axis=self._axis_constraint,
                    space=_space,
                    derived_geometry=self.app.viewport.render_mesh.derived,
                )
                if success:
                    self._gizmo_drag_started = True
            if self._gizmo_drag_started:
                update_transform(
                    self._gizmo_drag_tool, float(dx), float(dy), self.width, self.height,
                )
                self._sync_after_transform()
            return pyglet.event.EVENT_HANDLED

        tv = self._active_tweak_variant()

        # V2: first drag after Ctrl+LMB arm → begin Tweak
        if tv == "v2" and self._tweak_v2_armed and self.app.viewport is not None:
            _tt = self._current_tool_type or "move"
            ok = self._tweak_begin(_tt, x, y)
            if ok and self._tweak_started:
                update_transform(
                    self._tweak_tool, float(dx), float(dy), self.width, self.height,
                )
                self._sync_after_transform()
            return pyglet.event.EVENT_HANDLED

        # Transform-Handling: Hold (key down) oder Press-Mode/Press-Drag-Click (mode on)
        if (
            (self._transform_key_down is not None or self._transform_mode_on)
            and self.app.active_tool is not None
            and self.app.viewport is not None
        ):
            if not self._transform_started:
                # Erste Drag-Bewegung: Transform starten
                _space = "normal" if self._transform_space == "normal" else None
                success = begin_transform(
                    self.app.active_tool,
                    self.app.scene,
                    self.app.camera,
                    self.app.scene.selection,
                    axis=self._axis_constraint,
                    space=_space,
                    derived_geometry=self.app.viewport.render_mesh.derived,
                )
                if success:
                    self._transform_started = True

            if self._transform_started:
                # Update während Drag — VBOs neu bauen für Live-Preview
                update_transform(
                    self.app.active_tool,
                    float(dx),
                    float(dy),
                    self.width,
                    self.height,
                )
                self._sync_after_transform()
            return pyglet.event.EVENT_HANDLED

        # Box-Select: LMB-Drag in BOX-Methode → Gummiband aktualisieren
        if (
            self.app.select_method is SelectMethod.BOX
            and self._drag_button == self.input_map.select_button
            and self._box_start is not None
        ):
            self._box_end = (x, y)
            return pyglet.event.EVENT_HANDLED

        # Normale Kamera-Bedienung
        self._camera_navigate(dx, dy, modifiers)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        was_click = self._drag_moved < CLICK_THRESHOLD
        self._drag_button = None

        # WP-STAB-03: the release of a gated press never reaches a session's
        # commit branch (an Alt-orbit during Extrude-LMB must not commit it).
        # Exception: a camera-modified *click* on the session's own button is
        # still the session's click (e.g. Shift/Alt+click during Knife), as
        # before the gate.
        gate = self._gated_buttons.pop(button, None)
        if gate is not None:
            session = self._active_session()
            if not (
                gate == "camera"
                and was_click
                and session is not None
                and self._session_owns_press(session, button)
            ):
                return pyglet.event.EVENT_HANDLED

        # Articulation drag end — bent state persists, mouse is now free for camera.
        if self._articulation_dragging:
            self._articulation_dragging = False
            self._hud.update_action("Articulation bent — F = restore")
            self._update_hud()
            return pyglet.event.EVENT_HANDLED

        # Gizmo drag commit: D3 (AD-016) — LMB release after gizmo handle press/drag
        if self._gizmo_drag_armed:
            if self._gizmo_drag_started and self._gizmo_drag_tool is not None:
                commit_transform(self._gizmo_drag_tool)
                self._sync_after_transform()
            self._gizmo_drag_armed = False
            self._gizmo_drag_started = False
            self._gizmo_drag_tool = None
            return pyglet.event.EVENT_HANDLED

        tv = self._active_tweak_variant()
        if button == self.input_map.select_button:
            # V2: LMB release = commit (Ctrl may already be released)
            if tv == "v2" and (self._tweak_v2_armed or self._tweak_active):
                if self._tweak_active:
                    self._tweak_commit()
                else:
                    self._clear_tweak_gesture()
                return pyglet.event.EVENT_HANDLED

        # Knife Variant B: LMB release = commit or cancel slide (WP-AP-CUT)
        if (
            button == _mouse.LEFT
            and self._knife_slide_armed
            and self._knife_tool is not None
            and self.app.viewport is not None
        ):
            self._knife_slide_armed = False
            locked_eid = self._knife_slide_edge_id
            self._knife_slide_edge_id = None
            mesh = self.app.viewport.render_mesh.mesh
            if locked_eid is not None:
                target = _knife_project_locked_edge(
                    self.app.camera, mesh, x, y, self.width, self.height, locked_eid,
                )
            else:
                target = {"kind": "outside"}
            hover_result = self._knife_tool.hover(target)
            if target.get("kind") in ("edge", "vertex") and hover_result.get("valid", False):
                accepted = self._knife_tool.click(target)
                if accepted:
                    self._clear_knife_hover_vbos()
                    self._rebuild_vbo()
                    self._update_hud()
            else:
                self._clear_knife_hover_vbos()
            return pyglet.event.EVENT_HANDLED

        # Knife: LMB click = add cut point (AD-017)
        if (
            button == _mouse.LEFT
            and was_click
            and self._knife_tool is not None
            and self.app.viewport is not None
        ):
            mesh = self.app.viewport.render_mesh.mesh
            # Temporary [KNIFE] diagnosis logging (AD-017 edge targeting)
            print(f"[KNIFE] click at ({x},{y})")
            target = knife_pick(self.app.camera, mesh, x, y, self.width, self.height, debug=True)
            kind = target.get("kind")
            if kind == "vertex":
                print(f"[KNIFE] hit=VERTEX id={int(target['vertex_id'])}")
            elif kind == "edge":
                t_hit = target.get("t")
                print(f"[KNIFE] hit=EDGE id={int(target['edge_id'])} t={t_hit:.6f}")
            else:
                print(f"[KNIFE] hit=NONE ({kind})")
            accepted = self._knife_tool.click(target)
            print(f"[KNIFE] click accepted={accepted}")
            if accepted:
                self._clear_knife_hover_vbos()
                self._rebuild_vbo()
                self._update_hud()
            return pyglet.event.EVENT_HANDLED

        # Extrude LMB-Modell: LMB release = Commit (AP-05 Variante 2)
        if (
            button == _mouse.LEFT
            and self._extrude_tool is not None
            and self._active_extrude_model() == "lmb"
        ):
            self._extrude_tool.commit()
            self._extrude_tool.deactivate()
            self._extrude_tool = None
            self._recompute_derived()
            self._rebuild_vbo()
            self._hud.update_action("Extrude")
            self._update_hud()
            return pyglet.event.EVENT_HANDLED

        # Variant C (Press-Drag-Click): Maustaste loslassen = Commit
        if (
            self._active_transform_model() == "press_drag_click"
            and self._transform_mode_on
            and self._transform_started
            and self.app.active_tool is not None
        ):
            commit_transform(self.app.active_tool)
            self._sync_after_transform()
            self._clear_transform_temp_target()
            self._clear_transform_state()
            return pyglet.event.EVENT_HANDLED

        # WP-STAB-03: every session's own release was handled above; a selection
        # click or box-select must not mutate the Selection under a live session
        # (also covers a press that started before the session did).
        if self._active_session() is not None:
            self._box_start = None
            self._box_end = None
            return pyglet.event.EVENT_HANDLED

        if button == self.input_map.select_button and self.app.viewport is not None:
            mesh = self.app.viewport.render_mesh.mesh
            changed = False

            if self.app.select_method is SelectMethod.BOX and self._box_start is not None:
                if was_click:
                    # Kleiner Drag in BOX-Methode → Click-Fallback (SelectMode-Behaviour)
                    changed = dispatch_click(
                        self.app.camera, mesh, self.app.scene.selection,
                        x, y, self.width, self.height,
                        modifiers, self.input_map,
                        self.app.select_mode, SelectMethod.PICK,
                    )
                else:
                    bx1, by1 = self._box_start
                    changed = handle_box_select(
                        self.app.camera, mesh, self.app.scene.selection,
                        bx1, by1, x, y, self.width, self.height,
                        modifiers, self.input_map,
                    )
                self._box_start = None
                self._box_end = None
            elif was_click:
                changed = dispatch_click(
                    self.app.camera, mesh, self.app.scene.selection,
                    x, y, self.width, self.height,
                    modifiers, self.input_map,
                    self.app.select_mode, self.app.select_method,
                )

            if changed:
                self._rebuild_selection_vbo()
                self._update_hud()

        return pyglet.event.EVENT_HANDLED

    def on_mouse_scroll(
        self, x: int, y: int, scroll_x: int, scroll_y: int
    ) -> None:
        self.app.camera.dolly(0.9 if scroll_y > 0 else 1.1)
        self._push_camera()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        """Handle mouse motion (Mausbewegung ohne Klick) für AP-04 Transform."""
        self._last_mouse_x = x
        self._last_mouse_y = y

        # Knife: hover preview (WP-AP-CUT)
        if self._knife_tool is not None and self.app.viewport is not None:
            mesh = self.app.viewport.render_mesh.mesh
            target = knife_pick(self.app.camera, mesh, x, y, self.width, self.height)
            hover_result = self._knife_tool.hover(target)
            kind = target.get("kind")

            # Guard: skip VBO rebuild when target hasn't changed, except for
            # "edge" in live_preview mode (preview point moves continuously).
            live = self._active_knife_model() == "live_preview"
            target_changed = (target != self._knife_hover_last_target)
            if target_changed or (kind == "edge" and live):
                self._knife_hover_last_target = target
                self._clear_knife_hover_vbos()

                if kind == "vertex":
                    vid = target["vertex_id"]
                    positions = build_selection_vertex_data(mesh, {vid})
                    if positions:
                        self._vlist_knife_hover_vertex = self._overlay_program.vertex_list(
                            len(positions) // 3, gl.GL_POINTS,
                            position=("f", positions),
                        )

                elif kind == "edge":
                    eid = target["edge_id"]
                    edge_positions = build_selection_edge_data(mesh, {eid})
                    if edge_positions:
                        self._vlist_knife_hover_edge = self._overlay_program.vertex_list(
                            len(edge_positions) // 3, gl.GL_LINES,
                            position=("f", edge_positions),
                        )
                    # Variant A: live split-point preview at current t
                    if live and hover_result.get("valid", False):
                        t = target["t"]
                        va, vb = mesh.edge_vertices(eid)
                        p0 = mesh.vertex_position(va)
                        p1 = mesh.vertex_position(vb)
                        world_pos = (
                            p0[0] + t * (p1[0] - p0[0]),
                            p0[1] + t * (p1[1] - p0[1]),
                            p0[2] + t * (p1[2] - p0[2]),
                        )
                        pt_positions = build_knife_preview_point_data(world_pos)
                        self._vlist_knife_preview_point = self._overlay_program.vertex_list(
                            1, gl.GL_POINTS,
                            position=("f", pt_positions),
                        )

                # "face" / "outside" → no highlight (no-op, out of scope)

            # Persistent start-vertex highlight: rebuild when start changes
            start_vid = hover_result.get("start")
            if start_vid != self._knife_last_start:
                self._knife_last_start = start_vid
                if self._vlist_knife_start is not None:
                    self._vlist_knife_start.delete()
                    self._vlist_knife_start = None
                if start_vid is not None:
                    start_positions = build_selection_vertex_data(mesh, {start_vid})
                    if start_positions:
                        self._vlist_knife_start = self._overlay_program.vertex_list(
                            len(start_positions) // 3, gl.GL_POINTS,
                            position=("f", start_positions),
                        )

            return pyglet.event.EVENT_HANDLED

        # Loop Slide: Motion-Update im Hold-Modell (AP-05)
        if self._loop_slide_tool is not None:
            self._loop_slide_tool.update(dx=float(dx), dy=float(dy), width=self.width, height=self.height)
            self._rebuild_vbo()
            return pyglet.event.EVENT_HANDLED

        # Extrude: Motion-Update nur im Hold-Modell (AP-05)
        if self._extrude_tool is not None and self._active_extrude_model() == "hold":
            self._extrude_tool.update(dx=float(dx), dy=float(dy), width=self.width, height=self.height)
            self._rebuild_vbo()
            return pyglet.event.EVENT_HANDLED

        tv = self._active_tweak_variant()

        # V4: Ctrl held + motion → Tweak with shared current tool (D2 / AD-016)
        # WP-STAB-03: this branch runs before Transform's, so without the session
        # check a Ctrl held from before Q would start a Tweak inside the Transform.
        if (
            tv == "v4"
            and self._tweak_ctrl_held
            and self.app.viewport is not None
            and self._active_session() in (None, "tweak")
        ):
            if not self._tweak_active:
                self._tweak_begin(self._current_tool_type or "move", x, y)
            if self._tweak_started and self._tweak_tool is not None:
                update_transform(
                    self._tweak_tool, float(dx), float(dy), self.width, self.height,
                )
                self._sync_after_transform()
            return pyglet.event.EVENT_HANDLED

        # Transform: Hold (key down) oder Press-Mode/Press-Drag-Click (mode on)
        if (
            (self._transform_key_down is not None or self._transform_mode_on)
            and self.app.active_tool is not None
            and self.app.viewport is not None
        ):
            if not self._transform_started:
                # Erste Bewegung: Transform starten
                _space = "normal" if self._transform_space == "normal" else None
                success = begin_transform(
                    self.app.active_tool,
                    self.app.scene,
                    self.app.camera,
                    self.app.scene.selection,
                    axis=self._axis_constraint,
                    space=_space,
                    derived_geometry=self.app.viewport.render_mesh.derived,
                )
                if success:
                    self._transform_started = True

            if self._transform_started:
                # Update während Motion — VBOs neu bauen für Live-Preview
                update_transform(
                    self.app.active_tool,
                    float(dx),
                    float(dy),
                    self.width,
                    self.height,
                )
                self._sync_after_transform()
            return pyglet.event.EVENT_HANDLED

        # Hover Highlighting: nächstes Element unter dem Cursor
        if self.app.viewport is not None and self._drag_button is None:
            mesh = self.app.viewport.render_mesh.mesh
            sel = self.app.scene.selection
            hit = pick_component(self.app.camera, mesh, sel, x, y, self.width, self.height)
            # R-SEL-2 (WP-STAB-02): compare as (mode, id), not bare id — sel.mode
            # can only be the current mode here (single-kind hover; the window
            # code never picks against a different kind), but a bare-id compare
            # would still equate e.g. vertex id 5 with edge id 5 across a mode
            # switch if _clear_hover() were ever skipped, silently keeping a
            # stale/wrong-kind hover. TODO: this system only ever hovers one
            # kind at a time; full kind-based hover dispatch for arbitrary
            # (mode, id) pairs (matching Knife's per-kind hover) is a separate,
            # larger follow-up — not implemented here.
            hover_key = (sel.mode, hit) if hit is not None else None
            if hover_key != self._hover_key:
                self._hover_key = hover_key
                sel.hovered = hit
                self._rebuild_hover_vbo()

            # GIZMO-04: gizmo handle hover (display only, never arms a drag)
            if not sel.is_empty() and not self._gizmo_drag_armed:
                vertex_ids = resolve_selection_vertices(mesh, sel, sel.mode)
                if vertex_ids:
                    pivot = selection_pivot(mesh, vertex_ids)
                    gmode = gizmo_mode(sel, self._transform_space, self._axis_constraint)
                    derived = self.app.viewport.render_mesh.derived
                    new_hover = hover_gizmo_handle(
                        self.app.camera, pivot, gmode, self._transform_space,
                        sel, mesh, derived, x, y, self.width, self.height,
                        current_tool=self._current_tool_type or "move",
                    )
                    if new_hover != self._gizmo_hover:
                        self._gizmo_hover = new_hover
                elif self._gizmo_hover is not None:
                    self._gizmo_hover = None

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        # AD-013 I3/I4: the Playground window is the single interaction authority
        # for its own input. Activation and termination are resolved here and in
        # on_key_release against ONE key alphabet. Production BindingSet is NOT
        # consulted: capability is shared (create_tool_for_type), binding and
        # gesture are owned by the Playground (AD-013 "Capability promotion is
        # not UX promotion"). Restores the pre-54e9840 ownership split.

        # WP-STAB-03 Session Gate: while a session owns input, only its own keys
        # and Esc get through. Supersedes the pairwise per-branch guards (AD-015/
        # AD-016 style) as the general mechanism — the branches below, and the
        # independent X/Y/Z and Q/W/E blocks after the chain, never see a key
        # that belongs to no running session.
        session = self._active_session()
        if session is not None and not self._session_owns_key(session, symbol, modifiers):
            return pyglet.event.EVENT_HANDLED

        if symbol == self.input_map.display_cycle and not (modifiers & _key.MOD_SHIFT):
            # Shift+D is the wireframe-overlay toggle further down this chain;
            # without this guard the bare-D branch would swallow it.
            slot = self.app.slots.get("presentation")
            if slot is not None:
                self.app.activate_variant("presentation", (slot.active_index + 1) % slot.variant_count)
            else:
                self.app.display_state.cycle()
            self._update_hud()
        elif symbol == _key.Z and modifiers & _key.MOD_CTRL and not (modifiers & _key.MOD_SHIFT):
            # Ctrl+Z: in-session undo for knife, else global undo (AD-017 / WP-AP-Enablement-01).
            # Shift is excluded so Ctrl+Shift+Z can reach the redo branch below
            # (same guard pattern as the bare-D branch above).
            if self._knife_tool is not None:
                self._knife_tool.undo_step()
                self._rebuild_vbo()
                self._hud.update_action("Knife — undo last cut")
                self._update_hud()
            else:
                self.app.undo()
                self.app.scene.selection.clear()
                self._recompute_derived()
                self._rebuild_vbo()
                self._hud.update_action("Undo")
                self._update_hud()
        elif symbol == _key.Z and modifiers & _key.MOD_CTRL and modifiers & _key.MOD_SHIFT:
            # Ctrl+Shift+Z: alternative redo gesture (DECIDED 2026-09-22); the
            # Ctrl+Z undo branch above excludes Shift, so this is unambiguous.
            # (Ctrl+Y without Shift is the canonical redo gesture below.)
            if self._knife_tool is not None:
                self._knife_tool.redo_step()
                self._rebuild_vbo()
                self._hud.update_action("Knife — redo last cut")
                self._update_hud()
            else:
                self.app.redo()
                self.app.scene.selection.clear()
                self._recompute_derived()
                self._rebuild_vbo()
                self._hud.update_action("Redo")
                self._update_hud()
        elif symbol == _key.Y and modifiers & _key.MOD_CTRL:
            # Ctrl+Y: canonical Redo. While a Knife session is active, undo and
            # redo operate exclusively on the session's own step history — the
            # global stacks are neither mutated nor replayed (AD-017, DECIDED
            # 2026-09-22; otherwise a pre-session global state could destroy the
            # in-session cuts and stale the session baseline).
            if self._knife_tool is not None:
                self._knife_tool.redo_step()
                self._rebuild_vbo()
                self._hud.update_action("Knife — redo last cut")
                self._update_hud()
            else:
                self.app.redo()
                self.app.scene.selection.clear()
                self._recompute_derived()
                self._rebuild_vbo()
                self._hud.update_action("Redo")
                self._update_hud()
        elif symbol == _key.I:
            # I: Loop Insert (AP-05). Scope: Edge-Modus, genau 1 Edge selektiert.
            sel = self.app.scene.selection
            if sel.mode is SelectionMode.EDGE and len(sel.edges) >= 1:
                restored = self._articulation_auto_restore()
                start = next(iter(sel.edges))
                try:
                    new_edges = loop_insert(self.app.scene, start)
                    sel.clear()
                    sel.add(set(new_edges))
                    # WP-STAB-07: derived (adjacency/normal cache) references ids
                    # from before the mutation — stale by now. Recompute before/
                    # alongside the VBO rebuild so the next single-vertex Tweak/
                    # Gizmo update (_patch_vbo_single_vertex -> affected_neighborhood)
                    # never sees a deleted FaceId/VertexId.
                    self._recompute_derived()
                    self._rebuild_vbo()
                    suffix = " (articulation restored)" if restored else ""
                    self._hud.update_action(f"Loop Insert — {len(new_edges)} Edges{suffix}")
                except _LoopInsertError as exc:
                    self._hud.update_action(str(exc))
                self._update_hud()
        elif symbol == _key.R and (modifiers & _key.MOD_SHIFT):
            # WP-AP-INPUT-FIX-02 §2: Shift+R checked first to avoid shadowing by bare R
            # Shift+R: Ring Select (AP-05). Edge-Modus, 1+ Edges selektiert.
            sel = self.app.scene.selection
            if sel.mode is SelectionMode.EDGE and len(sel.edges) >= 1:
                start = next(iter(sel.edges))
                try:
                    traversal = edge_ring(self.app.scene.mesh, start)
                    sel.clear()
                    sel.add(traversal.as_set())
                    self._rebuild_selection_vbo()
                    self._hud.update_action(
                        f"Ring Select — {len(traversal.edges)} Edges"
                        + (" (geschlossen)" if traversal.closed else "")
                    )
                except _LoopRingError as exc:
                    self._hud.update_action(str(exc))
                self._update_hud()
        elif symbol == _key.C and (modifiers & _key.MOD_SHIFT):
            # WP-AP-INPUT-FIX-02 §5: Shift+C checked first to avoid shadowing by bare C
            # Shift+C triggers Collapse Edge (exactly 1 edge selected)
            sel = self.app.scene.selection
            if sel.mode is SelectionMode.EDGE and len(sel.edges) == 1:
                restored = self._articulation_auto_restore()
                (edge_id,) = sel.edges
                try:
                    # WP-STAB-06: history-wrapped, symmetric with Split/Connect
                    # (mirrors split_selected_edge's snapshot-command shape).
                    collapse_selected_edge(self.app.scene, edge_id)
                    sel.clear()
                    # WP-STAB-07: recompute derived before the VBO rebuild — see
                    # the Loop Insert branch above for the invalidation rationale.
                    self._recompute_derived()
                    self._rebuild_vbo()
                    action = "Collapse Edge (articulation restored)" if restored else "Collapse Edge"
                    self._hud.update_action(action)
                except Exception as exc:
                    self._hud.update_action(str(exc))
                self._update_hud()
        elif symbol == _key.C:
            # AD-017: Contextual C dispatch
            sel = self.app.scene.selection
            ctx = resolve_c_context(sel)
            if ctx is CContext.SPLIT:
                # Edge mode, 1 edge — Split; residue: Vertex mode, new vertex selected (D-S, AD-017)
                restored = self._articulation_auto_restore()
                (edge_id,) = sel.edges
                new_vid, _, _ = split_selected_edge(self.app.scene, edge_id)
                sel.mode = SelectionMode.VERTEX
                sel.clear()
                sel.add({new_vid})
                # WP-STAB-07: recompute derived before the VBO rebuild — see
                # the Loop Insert branch above for the invalidation rationale.
                self._recompute_derived()
                self._rebuild_vbo()
                action = "Split (articulation restored)" if restored else "Split"
                self._hud.update_action(action)
                self._update_hud()
            elif ctx is CContext.EDGE_CONNECT:
                # Edge mode, 2+ edges — Connect Edges (per-face semantics)
                restored = self._articulation_auto_restore()
                try:
                    new_edges = connect_selected_edges_per_face(self.app.scene, set(sel.edges))
                    sel.clear()
                    sel.add(set(new_edges))
                    # WP-STAB-07: recompute derived before the VBO rebuild — see
                    # the Loop Insert branch above for the invalidation rationale.
                    self._recompute_derived()
                    self._rebuild_vbo()
                    action = "Connect Edges (articulation restored)" if restored else "Connect Edges"
                    self._hud.update_action(action)
                except _ConnectEdgesError as exc:
                    self._hud.update_action(str(exc))
                self._update_hud()
            elif ctx is CContext.VERTEX_CONNECT:
                # Vertex mode, 2+ vertices — Vertex Connect
                restored = self._articulation_auto_restore()
                try:
                    new_edges = connect_vertices_per_face(self.app.scene, set(sel.vertices))
                    if new_edges:
                        # WP-STAB-07: recompute derived before the VBO rebuild —
                        # see the Loop Insert branch above for the invalidation
                        # rationale.
                        self._recompute_derived()
                        self._rebuild_vbo()
                        action = "Vertex Connect (articulation restored)" if restored else "Vertex Connect"
                        self._hud.update_action(action)
                    else:
                        self._hud.update_action("Vertex Connect — nothing connectable")
                except _VertexConnectError as exc:
                    self._hud.update_action(str(exc))
                self._update_hud()
            elif ctx is CContext.KNIFE:
                # Empty selection — enter Knife mode
                if self._knife_tool is None and self.app.viewport is not None:
                    mesh = self.app.viewport.render_mesh.mesh
                    self._knife_tool = KnifeTool()
                    self._knife_tool.activate()
                    self._knife_tool.begin(
                        mesh=mesh,
                        scene=self.app.scene,
                        selection=self.app.scene.selection,
                    )
                    # R-SEL-2: Knife has its own hover overlay (see the "Knife
                    # hover VBOs" note above) — clear any leftover regular
                    # selection hover so it doesn't stay drawn underneath it.
                    self._clear_hover()
                    self._hud.update_action("Knife — click vertices/edges; Enter=commit, Esc=cancel")
                    self._update_hud()
            elif ctx is CContext.NONE:
                # Nothing applicable — no-op
                pass
        elif symbol == _key.S:
            # WP-AP-INPUT-FIX-02 §5: S triggers Split Edge (exactly 1 edge selected)
            sel = self.app.scene.selection
            if sel.mode is SelectionMode.EDGE and len(sel.edges) == 1:
                restored = self._articulation_auto_restore()
                (edge_id,) = sel.edges
                split_selected_edge(self.app.scene, edge_id)
                sel.clear()
                # WP-STAB-07: recompute derived before the VBO rebuild — see
                # the Loop Insert branch above for the invalidation rationale.
                self._recompute_derived()
                self._rebuild_vbo()
                action = "Split Edge (articulation restored)" if restored else "Split Edge"
                self._hud.update_action(action)
                self._update_hud()
        elif symbol == _key.R:
            # WP-AP-INPUT-FIX-01 §2: R (rebind Extrude from E)
            # R: Extrude Face (AP-05). Scope: Face-Modus.
            # - 1+ Faces selektiert → diese extrudieren (Multi-Face-Extrude).
            # - Leer → Face unter Cursor per Hit-Test (Hover-Fallback, AP-05).
            sel = self.app.scene.selection
            if (
                sel.mode is SelectionMode.FACE
                and self.app.viewport is not None
                and self._extrude_tool is None
                and not (modifiers & _key.MOD_SHIFT)  # Avoid conflict with Shift+R (ring select)
            ):
                restored = self._articulation_auto_restore()
                if len(sel.faces) >= 1:
                    face_ids = set(sel.faces)
                else:
                    mesh = self.app.viewport.render_mesh.mesh
                    hit = pick_component(
                        self.app.camera, mesh, sel,
                        self._last_mouse_x, self._last_mouse_y,
                        self.width, self.height,
                    )
                    if hit is None or sel.mode is not SelectionMode.FACE:
                        return pyglet.event.EVENT_HANDLED
                    face_ids = {hit}
                tool = ExtrudeTool(self.app.scene, self.app.camera)
                tool.activate()
                tool.begin(face_ids=face_ids)
                self._extrude_tool = tool
                self._rebuild_vbo()
                n = len(face_ids)
                action = f"Extrude ({n} faces)" if n > 1 else "Extrude"
                restore_note = " (articulation restored)" if restored else ""
                self._hud.update_action(f"{action}{restore_note} — move mouse to set distance, release R = commit, ESC = cancel")
                self._update_hud()
        elif symbol == _key.D and modifiers & _key.MOD_SHIFT:
            # WP-AP-INPUT-FIX-01 §3: Shift+D only — Z is axis-constraint only
            self.app.display_state.toggle_wireframe_overlay()
            self._update_hud()
        elif symbol == self.input_map.show_vertices:
            self.app.show_vertices = not self.app.show_vertices
            self._update_hud()
        elif symbol == _key.TAB:
            # Tab: cycle focused_family through all registered slot families
            families = list(self.app.slots.keys())
            if families:
                cur = self.app.focused_family
                cur_idx = families.index(cur) if cur in families else 0
                self.app.focused_family = families[(cur_idx + 1) % len(families)]
            self._update_hud()
        elif symbol == _key.M and not (modifiers & _key.MOD_SHIFT):
            # WP-AP-INPUT-FIX-01 §2: Bare M — Cycle transform variants (moved from Q)
            # Cycles within the focused_family — never across families.
            # WP-STAB-03: M is not reachable while any session is live (gate at
            # the top), so the former per-family "cancel Transform/Knife before
            # switching" handling here is gone — a variant can no longer change
            # under a running gesture of any family.
            active_family = self.app.focused_family
            slot = self.app.slots.get(active_family)
            if slot is not None:
                self.app.activate_variant(active_family, (slot.active_index + 1) % slot.variant_count)
            self._update_hud()
        elif symbol == _key.M and (modifiers & _key.MOD_SHIFT):
            # WP-AP-INPUT-FIX-01 §2: Shift+M — Cycle SelectMethod (PICK → BOX → LASSO → PAINT → PICK)
            methods = [SelectMethod.PICK, SelectMethod.BOX, SelectMethod.LASSO, SelectMethod.PAINT]
            current_idx = methods.index(self.app.select_method) if self.app.select_method in methods else 0
            self.app.select_method = methods[(current_idx + 1) % len(methods)]
            self._box_start = None
            self._box_end = None
            self._update_hud()
        elif symbol == _key._1:
            # 1: Vertex-Modus
            sel = self.app.scene.selection
            sel.mode = SelectionMode.VERTEX
            sel.clear()
            self._clear_hover()  # R-SEL-2: no stale hover from the previous mode
            self._rebuild_selection_vbo()
            self._update_hud()
        elif symbol == _key._2:
            # 2: Edge-Modus
            sel = self.app.scene.selection
            sel.mode = SelectionMode.EDGE
            sel.clear()
            self._clear_hover()  # R-SEL-2: no stale hover from the previous mode
            self._rebuild_selection_vbo()
            self._update_hud()
        elif symbol == _key._3:
            # 3: Face-Modus
            sel = self.app.scene.selection
            sel.mode = SelectionMode.FACE
            sel.clear()
            self._clear_hover()  # R-SEL-2: no stale hover from the previous mode
            self._rebuild_selection_vbo()
            self._update_hud()
        elif symbol == _key.G and self._loop_slide_tool is None:
            # G: Loop Slide (AP-05). Edge-Modus, 1+ Edges selektiert.
            sel = self.app.scene.selection
            if sel.mode is SelectionMode.EDGE and len(sel.edges) >= 1:
                restored = self._articulation_auto_restore()
                tool = LoopSlideTool(self.app.scene, self.app.camera)
                try:
                    tool.activate()
                    tool.begin(edge_ids=set(sel.edges))
                    self._loop_slide_tool = tool
                    suffix = " (articulation restored)" if restored else ""
                    self._hud.update_action(f"Loop Slide — Maus ziehen, G loslassen = commit, ESC = cancel{suffix}")
                except _LoopSlideError as exc:
                    tool.deactivate()
                    self._hud.update_action(str(exc))
                self._update_hud()
        elif symbol == _key.L and (modifiers & _key.MOD_SHIFT):
            # Shift+L: Loop Select (AP-05). Edge-Modus, 1+ Edges selektiert.
            sel = self.app.scene.selection
            if sel.mode is SelectionMode.EDGE and len(sel.edges) >= 1:
                start = next(iter(sel.edges))
                try:
                    traversal = edge_loop(self.app.scene.mesh, start)
                    sel.clear()
                    sel.add(traversal.as_set())
                    self._rebuild_selection_vbo()
                    self._hud.update_action(
                        f"Loop Select — {len(traversal.edges)} Edges"
                        + (" (geschlossen)" if traversal.closed else "")
                    )
                except _LoopRingError as exc:
                    self._hud.update_action(str(exc))
                self._update_hud()
        elif symbol in (_key.LCTRL, _key.RCTRL):
            self._tweak_ctrl_held = True
        # WP-AP-INPUT-FIX-03: sticky axis/plane constraint toggle
        # Pressing the active constraint again clears it (toggle off); pressing a different
        # one replaces it. Release does nothing — constraint persists across gestures.
        if symbol in (_key.X, _key.Y, _key.Z) and not (modifiers & _key.MOD_CTRL):
            if not (modifiers & _key.MOD_SHIFT):
                _target = {_key.X: "x", _key.Y: "y", _key.Z: "z"}[symbol]
            else:
                _target = {_key.X: "yz", _key.Y: "xz", _key.Z: "xy"}[symbol]
            self._axis_constraint = None if self._axis_constraint == _target else _target
            self._hud.update_constraint(self._axis_constraint)
            self._update_hud()
        # WP-AP-INPUT-FIX-01 §2: Rebind transform tools to Q/W/E (was X/R/S)
        if symbol in (_key.Q, _key.W, _key.E) and not (modifiers & _key.MOD_SHIFT):
            _key_map = {_key.Q: ('q', 'move'), _key.W: ('w', 'rotate'), _key.E: ('e', 'scale')}
            if symbol in _key_map:
                _key_char, _tool_type = _key_map[symbol]
            else:
                _key_char = None
                _tool_type = None
        else:
            _key_char = None
            _tool_type = None

        if _key_char is not None and _tool_type is not None:
            # D1 (AD-016): Transform is the single owner of Q/W/E. No Tweak dispatch.
            # D2 (AD-016): update the shared current-tool state.
            self._current_tool_type = _tool_type
            model = self._active_transform_model()
            if model == "hold":
                # WP-STAB-04: selection-or-hover fallback, refuse only if both are empty
                if self._transform_arm(self._last_mouse_x, self._last_mouse_y):
                    self._transform_key_down = _key_char
                    self.app.active_tool = create_tool_for_type(_tool_type)
                    self._hud.update_action(f"Transform: {_tool_type.capitalize()}")
                else:
                    self._hud.update_action(f"Nothing to transform ({_tool_type.capitalize()})")
            elif model == "hold_key_hover":
                # D4 (AD-016): like Hold, but tap = set tool only; no-selection → temp
                # target. WP-STAB-04: refuse (don't arm) if there's also nothing under
                # the cursor — previously this always armed active_tool unconditionally.
                if self._transform_arm(self._last_mouse_x, self._last_mouse_y):
                    self._transform_key_down = _key_char
                    self.app.active_tool = create_tool_for_type(_tool_type)
                    self._hud.update_action(f"Transform: {_tool_type.capitalize()}")
                else:
                    self._hud.update_action(f"Nothing to transform ({_tool_type.capitalize()})")
            else:  # press_mode or press_drag_click
                if self._transform_mode_on:
                    # Second press of same key → commit (if started), leave mode
                    if self._transform_started and self.app.active_tool is not None:
                        commit_transform(self.app.active_tool)
                        self._sync_after_transform()
                    self._clear_transform_temp_target()
                    self._clear_transform_state()
                else:
                    # First press → enter mode. WP-STAB-04: selection-or-hover fallback.
                    if self._transform_arm(self._last_mouse_x, self._last_mouse_y):
                        self._transform_key_down = _key_char
                        self._transform_mode_on = True
                        self.app.active_tool = create_tool_for_type(_tool_type)
                        self._hud.update_action(f"Transform: {_tool_type.capitalize()}")
                    else:
                        self._hud.update_action(f"Nothing to transform ({_tool_type.capitalize()})")
                self._update_hud()
        elif symbol == _key.K and not modifiers:
            # K: toggle transform coordinate space World ↔ Normal (WP-AP-INPUT-FIX-03)
            # Clear axis constraint: same letter means a different physical direction per space.
            self._transform_space = "normal" if self._transform_space == "world" else "world"
            self._axis_constraint = None
            self._hud.update_constraint(None)
            self._hud.update_space(self._transform_space)
            self._update_hud()
        elif symbol == _key.F:
            # F: Restore articulation to exact rest pose (EX-A / H02).
            if self._articulation_state is not None:
                self._articulation_state.restore()
                self._articulation_state = None
                self._articulation_dragging = False
                self._rebuild_vbo()
                self._hud.update_action("Articulation restored")
                self._update_hud()
        elif symbol in (_key.ENTER, _key.NUM_ENTER):
            if self._knife_tool is not None:
                cmd = self._knife_tool.commit()
                self._knife_tool.deactivate()
                self._knife_tool = None
                self._knife_slide_armed = False
                self._knife_slide_edge_id = None
                self._clear_knife_hover_vbos()
                self._clear_knife_start_vbo()
                self._recompute_derived()
                self._rebuild_vbo()
                if cmd is not None:
                    self._hud.update_action("Knife committed")
                    print("[KNIFE] session result: committed (1 history entry, residue = connecting-edge path)")
                else:
                    self._hud.update_action("Knife — no cuts made")
                    print("[KNIFE] session result: no cuts made (mesh state unchanged since session begin)")
                self._update_hud()
        elif symbol == _key.ESCAPE:
            # WP-STAB-03: Esc goes to the owning session, not to whichever flag
            # comes first in this chain — a bent-idle Articulation must not
            # absorb the Esc meant for a running Transform, and an armed-but-not-
            # dragged Gizmo / Tweak-V2 must not fall through to close().
            if session == "knife":
                self._knife_tool.cancel()
                self._knife_tool.deactivate()
                self._knife_tool = None
                self._knife_slide_armed = False
                self._knife_slide_edge_id = None
                self._clear_knife_hover_vbos()
                self._clear_knife_start_vbo()
                self._recompute_derived()
                self._rebuild_vbo()
                self._hud.update_action("Knife cancelled")
                self._update_hud()
            elif session == "articulation" or (session is None and self._articulation_state is not None):
                self._articulation_state.restore()
                self._articulation_state = None
                self._articulation_dragging = False
                self._rebuild_vbo()
                self._hud.update_action("Articulation restored")
                self._update_hud()
            elif session == "loop_slide":
                self._loop_slide_tool.cancel()
                self._loop_slide_tool.deactivate()
                self._loop_slide_tool = None
                self._rebuild_vbo()
                self._hud.update_action("Loop Slide cancelled")
                self._update_hud()
            elif session == "extrude":
                self._extrude_tool.cancel()
                self._extrude_tool.deactivate()
                self._extrude_tool = None
                self._recompute_derived()
                self._rebuild_vbo()
                self._hud.update_action("Extrude cancelled")
                self._update_hud()
            elif session == "tweak":
                if self._tweak_active and self._tweak_tool is not None:
                    self._tweak_cancel()
                else:
                    self._clear_tweak_gesture()  # V2 armed, not yet dragged
            elif session == "gizmo":
                if self._gizmo_drag_started and self._gizmo_drag_tool is not None:
                    cancel_transform(self._gizmo_drag_tool)
                    self._sync_after_transform()
                self._gizmo_drag_armed = False
                self._gizmo_drag_started = False
                self._gizmo_drag_tool = None
            elif session == "transform":
                if self._transform_started and self.app.active_tool is not None:
                    cancel_transform(self.app.active_tool)
                self._sync_after_transform()
                self._clear_transform_temp_target()
                self._clear_transform_state()
            else:
                self.close()
            if session is not None and self._drag_button is not None:
                # A button still held for the cancelled gesture (Gizmo, Tweak V2,
                # Articulation, Knife slide) must not turn into a selection click.
                self._gated_buttons.setdefault(self._drag_button, "blocked")
        return pyglet.event.EVENT_HANDLED

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        """Handle key release — Commit-Verhalten abhängig vom Aktivierungsmodell."""
        if symbol == _key.G and self._loop_slide_tool is not None:
            # G loslassen = Commit (AP-05 Hold-Modell)
            self._loop_slide_tool.commit()
            self._loop_slide_tool.deactivate()
            self._loop_slide_tool = None
            # WP-STAB-07: LoopSlideTool.commit() moves vertices but does not
            # touch `derived` itself (checked: no derived/recompute call in
            # topology_tools/loop_slide.py) — recompute here, same as the
            # other topology-mutating handlers above.
            self._recompute_derived()
            self._rebuild_vbo()
            self._hud.update_action("Loop Slide")
            self._update_hud()
            return pyglet.event.EVENT_HANDLED
        elif symbol == _key.R and self._extrude_tool is not None and self._active_extrude_model() == "hold":
            # WP-AP-INPUT-FIX-02 §1: R release = Commit (AP-05 Hold-Modell, Extrude moved from E to R)
            self._extrude_tool.commit()
            self._extrude_tool.deactivate()
            self._extrude_tool = None
            self._recompute_derived()
            self._rebuild_vbo()
            self._hud.update_action("Extrude")
            self._update_hud()
            return pyglet.event.EVENT_HANDLED
        elif symbol in (_key.LCTRL, _key.RCTRL):
            self._tweak_ctrl_held = False
            tv = self._active_tweak_variant()
            if tv == "v4" and self._tweak_active:
                # V4: Ctrl release = commit
                self._tweak_commit()
                self._update_hud()
            # V2: Ctrl release does NOT cancel (LMB governs in V2)
        elif symbol in (_key.Q, _key.W, _key.E):
            _key_map = {_key.Q: 'q', _key.W: 'w', _key.E: 'e'}
            if symbol not in _key_map:
                return pyglet.event.EVENT_HANDLED
            _key_char = _key_map[symbol]
            _tool_type_map = {'q': 'move', 'w': 'rotate', 'e': 'scale'}
            _tool_type = _tool_type_map.get(_key_char)

            if self._transform_key_down == _key_char:
                model = self._active_transform_model()
                if model == "hold":
                    # Hold: release = commit if dragged
                    if self._transform_started and self.app.active_tool is not None:
                        commit_transform(self.app.active_tool)
                        self._sync_after_transform()
                    self._clear_transform_temp_target()
                    self._clear_transform_state()
                elif model == "hold_key_hover":
                    # D4 (AD-016): release = commit if dragged; tap = set current tool only
                    if self._transform_started and self.app.active_tool is not None:
                        commit_transform(self.app.active_tool)
                        self._sync_after_transform()
                    else:
                        # Tap: tool already set at press; update HUD to confirm
                        _tl = {'move': 'Move', 'rotate': 'Rotate', 'scale': 'Scale'}
                        self._hud.update_action(
                            f"Tool: {_tl.get(self._current_tool_type or _tool_type, '?')}"
                        )
                    self._clear_transform_temp_target()
                    self._clear_transform_state()
                    self._update_hud()
                else:
                    # press_mode or press_drag_click: release = no commit, mode stays active
                    self._transform_key_down = None
        return pyglet.event.EVENT_HANDLED

    # -- Draw -----------------------------------------------------------------

    def _draw_gizmo(self, view, proj) -> None:
        """WP-AP-GIZMO-04: tool-specific handle shapes with hover and hit-radius improvements.

        Renders the appropriate visual per current_tool (move/rotate/scale) over all
        geometry without depth testing.  Three visual states: default / hover / active.
        No mouse interaction here.
        """
        if self.app.viewport is None:
            return
        sel = self.app.scene.selection
        if sel.is_empty():
            return

        mesh = self.app.viewport.render_mesh.mesh
        derived = self.app.viewport.render_mesh.derived
        vertex_ids = resolve_selection_vertices(mesh, sel, sel.mode)
        if not vertex_ids:
            return

        pivot = selection_pivot(mesh, vertex_ids)

        cam_eye = self.app.camera.eye()
        dist = math.sqrt(
            (pivot[0] - cam_eye[0]) ** 2
            + (pivot[1] - cam_eye[1]) ** 2
            + (pivot[2] - cam_eye[2]) ** 2
        )
        size = max(dist * GIZMO_SCALE, 1e-6)

        mode = gizmo_mode(sel, self._transform_space, self._axis_constraint)
        constraint = self._axis_constraint
        current_tool = self._current_tool_type or "move"
        hover = self._gizmo_hover
        cap_size = size * _GIZMO_CAP_SIZE_RATIO

        self._overlay_program.use()
        self._overlay_program["u_view"] = view
        self._overlay_program["u_proj"] = proj
        gl.glDisable(gl.GL_DEPTH_TEST)

        def _draw(positions: list[float], color: tuple, prim: int, width: float) -> None:
            n = len(positions) // 3
            if n == 0:
                return
            gl.glLineWidth(width)
            self._overlay_program["u_color"] = list(color)
            vl = self._overlay_program.vertex_list(n, prim, position=("f", positions))
            vl.draw(prim)
            vl.delete()

        def _w(name: str) -> float:
            if constraint == name:
                return _GIZMO_LINE_WIDTH_ACTIVE
            if hover == name:
                return _GIZMO_LINE_WIDTH_HOVER
            return _GIZMO_LINE_WIDTH_DEFAULT

        def _c(base: tuple, name: str) -> tuple:
            if hover == name and constraint != name:
                r, g, b, a = base
                return (min(r * 1.4, 1.0), min(g * 1.4, 1.0), min(b * 1.4, 1.0), a)
            return base

        def _draw_axes(axes_with_colors: list) -> None:
            for name, direction, color in axes_with_colors:
                tip = (
                    pivot[0] + direction[0] * size,
                    pivot[1] + direction[1] * size,
                    pivot[2] + direction[2] * size,
                )
                if current_tool == "rotate":
                    _draw(axis_ring_positions(pivot, direction, size), _c(color, name), gl.GL_LINE_LOOP, _w(name))
                else:
                    _draw(axis_line_positions(pivot, direction, size), _c(color, name), gl.GL_LINES, _w(name))
                    if current_tool == "move":
                        _draw(arrow_cap_positions(tip, direction, cap_size), _c(color, name), gl.GL_LINES, _w(name))
                    elif current_tool == "scale":
                        _draw(box_cap_positions(tip, direction, cap_size), _c(color, name), gl.GL_LINES, _w(name))

        def _draw_center() -> None:
            r = size * 0.07
            _draw(
                [pivot[0]-r, pivot[1], pivot[2], pivot[0]+r, pivot[1], pivot[2],
                 pivot[0], pivot[1]-r, pivot[2], pivot[0], pivot[1]+r, pivot[2],
                 pivot[0], pivot[1], pivot[2]-r, pivot[0], pivot[1], pivot[2]+r],
                _c(_GIZMO_COLOR_CENTER, "center"),
                gl.GL_LINES,
                _w("center"),
            )

        if mode == "screen":
            _, right, up = self.app.camera.basis()
            _draw(
                screen_ring_positions(pivot, right, up, size),
                _GIZMO_COLOR_SCREEN,
                gl.GL_LINE_LOOP,
                _GIZMO_LINE_WIDTH_DEFAULT,
            )

        elif mode == "world":
            _draw_axes([
                ("x", (1.0, 0.0, 0.0), _GIZMO_COLOR_X),
                ("y", (0.0, 1.0, 0.0), _GIZMO_COLOR_Y),
                ("z", (0.0, 0.0, 1.0), _GIZMO_COLOR_Z),
            ])
            if current_tool == "rotate":
                # Unconstrained rotate: screen ring shows camera-axis default
                if constraint is None:
                    _, right, up = self.app.camera.basis()
                    _draw(screen_ring_positions(pivot, right, up, size * 1.1),
                          _c(_GIZMO_COLOR_SCREEN, "screen"), gl.GL_LINE_LOOP, _w("screen"))
            else:
                _PLANE_COLORS = (_GIZMO_COLOR_PLANE_XY, _GIZMO_COLOR_PLANE_XZ, _GIZMO_COLOR_PLANE_YZ)
                for (name, axis_a, axis_b), color in zip(WORLD_PLANES, _PLANE_COLORS):
                    _draw(plane_indicator_positions(pivot, axis_a, axis_b, size),
                          _c(color, name), gl.GL_LINES, _w(name))
                if current_tool == "scale":
                    _draw_center()

        elif mode == "normal_full":
            try:
                normal, tangent_x, tangent_y = _face_tangent_basis(mesh, sel, derived)
            except ValueError:
                pass
            else:
                _draw_axes([
                    ("x", tangent_x, _GIZMO_COLOR_X),
                    ("y", tangent_y, _GIZMO_COLOR_Y),
                    ("z", normal,    _GIZMO_COLOR_Z),
                ])
                if current_tool == "scale":
                    _draw_center()

        elif mode == "normal_z_only":
            normal = selection_normal(derived, mesh, sel, sel.mode)
            if any(v != 0.0 for v in normal):
                _draw_axes([("z", normal, _GIZMO_COLOR_Z)])
                if current_tool == "scale":
                    _draw_center()

        self._overlay_program.stop()
        gl.glLineWidth(1.0)

    def on_draw(self) -> None:
        if self.height == 0:
            return pyglet.event.EVENT_HANDLED

        gl.glClearColor(0.08, 0.08, 0.12, 1.0)
        self.clear()

        display_state = self.app.display_state
        view = self.app.camera.build_view_matrix()
        proj = self.app.camera.build_projection_matrix(self.width / self.height)

        # -- Face-Pass (Shaded / Flat Shaded / Wireframe ohne Faces) ----------
        if display_state.show_faces and self._vlist_faces is not None:
            self._face_program.use()
            self._face_program["u_view"] = view
            self._face_program["u_proj"] = proj
            self._face_program["u_light_dir"] = (
                _LIGHT_DIR_INV, _LIGHT_DIR_INV, _LIGHT_DIR_INV,
            )
            self._face_program["u_base_color"] = list(_DEFAULT_BASE_COLOR)
            self._face_program["u_use_flat"] = (
                1 if display_state.mode is DisplayMode.FLAT_SHADED else 0
            )
            gl.glEnable(gl.GL_DEPTH_TEST)
            # Polygon-Offset pusht Faces leicht nach hinten → Wireframe-Overlay
            # ohne Z-Fighting (nur wenn Edges zusätzlich gezeichnet werden).
            if display_state.show_edges:
                gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
                gl.glPolygonOffset(1.0, 1.0)
            self._vlist_faces.draw(gl.GL_TRIANGLES)
            if display_state.show_edges:
                gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)
            self._face_program.stop()

        # -- Selection-Pass (selektierte Faces, GL_LEQUAL — over face geometry) -
        if self._vlist_selection is not None:
            self._overlay_program.use()
            self._overlay_program["u_view"] = view
            self._overlay_program["u_proj"] = proj
            self._overlay_program["u_color"] = list(_SELECTION_COLOR)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LEQUAL)
            self._vlist_selection.draw(gl.GL_TRIANGLES)
            gl.glDepthFunc(gl.GL_LESS)
            self._overlay_program.stop()

        # -- Hover-Highlight --------------------------------------------------
        if self._vlist_hover is not None:
            sel = self.app.scene.selection
            self._overlay_program.use()
            self._overlay_program["u_view"] = view
            self._overlay_program["u_proj"] = proj
            self._overlay_program["u_color"] = list(_HOVER_COLOR)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LEQUAL)
            if sel.mode is SelectionMode.VERTEX:
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glPointSize(10.0)
                self._vlist_hover.draw(gl.GL_POINTS)
                gl.glPointSize(_VERTEX_POINT_SIZE)
                gl.glEnable(gl.GL_DEPTH_TEST)
            elif sel.mode is SelectionMode.EDGE:
                self._vlist_hover.draw(gl.GL_LINES)
            else:
                self._vlist_hover.draw(gl.GL_TRIANGLES)
            gl.glDepthFunc(gl.GL_LESS)
            self._overlay_program.stop()

        # -- Knife Hover (edge highlight + vertex hover + split-point preview) --
        if self._knife_tool is not None and (
            self._vlist_knife_hover_edge is not None
            or self._vlist_knife_hover_vertex is not None
            or self._vlist_knife_preview_point is not None
        ):
            self._overlay_program.use()
            self._overlay_program["u_view"] = view
            self._overlay_program["u_proj"] = proj
            self._overlay_program["u_color"] = list(_HOVER_COLOR)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LEQUAL)
            if self._vlist_knife_hover_edge is not None:
                self._vlist_knife_hover_edge.draw(gl.GL_LINES)
            if self._vlist_knife_hover_vertex is not None:
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glPointSize(10.0)
                self._vlist_knife_hover_vertex.draw(gl.GL_POINTS)
                gl.glPointSize(_VERTEX_POINT_SIZE)
                gl.glEnable(gl.GL_DEPTH_TEST)
            if self._vlist_knife_preview_point is not None:
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glPointSize(10.0)
                self._vlist_knife_preview_point.draw(gl.GL_POINTS)
                gl.glPointSize(_VERTEX_POINT_SIZE)
                gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LESS)
            self._overlay_program.stop()

        # -- Knife Start-Vertex (persistent selection-style indicator) ---------
        if self._knife_tool is not None and self._vlist_knife_start is not None:
            self._overlay_program.use()
            self._overlay_program["u_view"] = view
            self._overlay_program["u_proj"] = proj
            self._overlay_program["u_color"] = list(_SELECTION_COLOR)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glPointSize(_VERTEX_POINT_SIZE)
            self._vlist_knife_start.draw(gl.GL_POINTS)
            gl.glEnable(gl.GL_DEPTH_TEST)
            self._overlay_program.stop()

        # -- Selected Edges ---------------------------------------------------
        if self._vlist_sel_edges is not None:
            self._overlay_program.use()
            self._overlay_program["u_view"] = view
            self._overlay_program["u_proj"] = proj
            self._overlay_program["u_color"] = list(_SELECTION_COLOR)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LEQUAL)
            self._vlist_sel_edges.draw(gl.GL_LINES)
            gl.glDepthFunc(gl.GL_LESS)
            self._overlay_program.stop()

        # -- Selected Vertices ------------------------------------------------
        if self._vlist_sel_verts is not None:
            self._overlay_program.use()
            self._overlay_program["u_view"] = view
            self._overlay_program["u_proj"] = proj
            self._overlay_program["u_color"] = list(_SELECTION_COLOR)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glPointSize(8.0)
            self._vlist_sel_verts.draw(gl.GL_POINTS)
            gl.glPointSize(_VERTEX_POINT_SIZE)
            self._overlay_program.stop()

        # -- Edge-Pass (Wireframe / Wireframe-Overlay) ------------------------
        if display_state.show_edges and self._vlist_edges is not None:
            self._overlay_program.use()
            self._overlay_program["u_view"] = view
            self._overlay_program["u_proj"] = proj
            self._overlay_program["u_color"] = list(_EDGE_COLOR)
            gl.glEnable(gl.GL_DEPTH_TEST)
            self._vlist_edges.draw(gl.GL_LINES)
            self._overlay_program.stop()

        # -- Vertex-Pass (GL_POINTS, immer vor HUD) ---------------------------
        if self.app.show_vertices and self._vlist_verts is not None:
            self._overlay_program.use()
            self._overlay_program["u_view"] = view
            self._overlay_program["u_proj"] = proj
            self._overlay_program["u_color"] = list(_VERTEX_COLOR)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glPointSize(_VERTEX_POINT_SIZE)
            self._vlist_verts.draw(gl.GL_POINTS)
            self._overlay_program.stop()

        # -- Transform Gizmo (WP-AP-GIZMO-01, Phase 1: draw-only) -------------
        self._draw_gizmo(view, proj)

        # -- Experiment-Hook --------------------------------------------------
        self.app.active_experiment.draw()

        # -- Box-Select Rubber Band (2D, Screen-Space) -----------------------
        if self._box_start is not None and self._box_end is not None:
            x1, y1 = self._box_start
            x2, y2 = self._box_end
            bx = min(x1, x2)
            by = min(y1, y2)
            bw = abs(x2 - x1)
            bh = abs(y2 - y1)
            if bw > 1 and bh > 1:
                import pyglet.shapes as _shapes
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glEnable(gl.GL_BLEND)
                gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
                fill = _shapes.Rectangle(bx, by, bw, bh, color=(100, 160, 255, 35))
                fill.draw()
                for lx1, ly1, lx2, ly2 in (
                    (bx,      by,      bx + bw, by),
                    (bx + bw, by,      bx + bw, by + bh),
                    (bx + bw, by + bh, bx,      by + bh),
                    (bx,      by + bh, bx,      by),
                ):
                    line = _shapes.Line(lx1, ly1, lx2, ly2, color=(100, 160, 255, 200))
                    line.draw()

        # -- HUD (program.stop() vor Label.draw() — Constraint aus WP-IL-01) --
        # _update_hud() hier (per-Frame), nicht in _push_camera() (per-Event) —
        # identisch zum Lab-Pattern: label.text wird nur einmal pro gerendertem
        # Frame gesetzt, nie pro Maus-Event.
        self._update_hud()
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        self._hud.draw()

        return pyglet.event.EVENT_HANDLED
