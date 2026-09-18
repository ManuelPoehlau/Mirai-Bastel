"""PlaygroundWindow — pyglet-Fenster für das Artist Playground.

Steuerung:
    LMB ziehen      Orbit
    MMB ziehen      Pan
    Mausrad         Zoom
    LMB click       Select (Verhalten laut SelectMode)
    LMB drag (BOX)  Box Select (wenn SelectMethod = BOX aktiv)
    Alt+LMB drag    Orbit
    X (gedrückt)    Move (gedrückt halten + ziehen, AP-04)
    R (gedrückt)    Rotate (gedrückt halten + ziehen, AP-04)
    S (gedrückt)    Scale (gedrückt halten + ziehen, AP-04)
    C               load_cube (Szene wechseln)
    H               load_head (Szene wechseln)
    Y               load_cylinder (EX-A test body)
    D               Display-Mode cyclen (Shaded → Flat → Wireframe)
    Z               Wireframe-Overlay togglen
    V               Vertex-Darstellung togglen
    M               SelectMode cyclen (Replace → Modifier → Toggle)
    Q               SelectMethod cyclen (Pick → Box → Lasso → Paint)
    1 / 2 / 3       Component-Modus (Vertex / Edge / Face)
    Shift+L         Loop Select (Edge-Modus, 1+ Edges selektiert)
    Shift+R         Ring Select (Edge-Modus, 1+ Edges selektiert)
    I               Loop Insert (Edge-Modus, 1 Edge selektiert)
    G (halten)      Loop Slide (Edge-Modus, 1+ Edges selektiert; Maus = slide, loslassen = commit)
    F               Articulation restore (EX-A: LMB drag to bend, F to restore)
    ESC             Fenster schließen (oder Transform/Articulation canceln)

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
from playground.experiments.tweak.variant_1_hold_key import TweakV1HoldKey  # noqa: E402
from playground.experiments.tweak.variant_2_silo import TweakV2Silo  # noqa: E402
from playground.experiments.tweak.variant_3_hold_click import TweakV3HoldClick  # noqa: E402
from playground.experiments.tweak.variant_4_hold_ctrl import TweakV4HoldCtrl  # noqa: E402
from playground.topology_ops import split_selected_edge  # noqa: E402
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
from playground.experiments.articulation.articulation import ArticulationState  # noqa: E402
from playground.experiments.articulation.variant_articulation import ArticulationVariant  # noqa: E402
from playground.experiments.tweak._target import (  # noqa: E402
    add_temp_target,
    clear_temp_target,
    has_selection as _tweak_has_selection,
    toggle_persistent_mode,
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
    build_selection_data,
    build_selection_edge_data,
    build_selection_vertex_data,
    build_vertex_data,
)

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

# Articulation constants (EX-A / H02)
# 0.01 rad/px: 100px drag ≈ 57° bend, feels responsive without being twitchy.
_ARTICULATION_SENSITIVITY: float = 0.01


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
            VariantEntry(HoldActivationVariant(app)),
            VariantEntry(PressModeVariant(app)),
            VariantEntry(PressDragClickVariant(app)),
        )
        tweak_slot = ExperimentSlot(
            VariantEntry(TweakV1HoldKey(app)),
            VariantEntry(TweakV2Silo(app)),
            VariantEntry(TweakV3HoldClick(app)),
            VariantEntry(TweakV4HoldCtrl(app)),
        )
        topo_slot = ExperimentSlot(
            VariantEntry(ExtrudeBaselineVariant(app)),
            VariantEntry(ExtrudeLmbVariant(app)),
        )
        artic_slot = ExperimentSlot(
            VariantEntry(ArticulationVariant(app)),
        )
        app.register_slot(sel_slot, "selection")
        app.register_slot(pres_slot, "presentation")
        app.register_slot(trans_slot, "transform")
        app.register_slot(tweak_slot, "tweak")
        app.register_slot(topo_slot, "topology")
        app.register_slot(artic_slot, "articulation")
        # Initialzustand anwenden und _active_experiment auf selection setzen,
        # damit M beim ersten Druck die Selection-Family cyclt (nicht id="none").
        pres_slot.active_experiment.activate()
        app.activate_variant("selection", 0)  # setzt _active_experiment + ruft activate() auf

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
        # Persistent mode for V2/V4 (set via V1 mode-toggle or V2/V4 X/R/S press)
        self._tweak_persistent_mode: str | None = None
        self._tweak_ctrl_held: bool = False
        self._tweak_active: bool = False    # currently in a Tweak gesture
        self._tweak_started: bool = False   # begin_transform() was called
        self._tweak_tool = None
        self._tweak_temp_target: bool = False  # temporary target was selected
        # V1: track motion since key-down
        self._tweak_v1_key: str | None = None
        self._tweak_v1_moved: float = 0.0
        # V3: key held + LMB combo
        self._tweak_v3_key: str | None = None
        self._tweak_v3_lmb: bool = False
        self._tweak_v3_tool_type: str | None = None  # resolved at LMB press
        # V2: Ctrl was held when LMB was pressed
        self._tweak_v2_armed: bool = False

        # Extrude-State (AP-05)
        self._extrude_tool: ExtrudeTool | None = None
        # Loop-Slide-State (AP-05)
        self._loop_slide_tool: LoopSlideTool | None = None

        # Articulation state (EX-A / H02)
        self._articulation_state: ArticulationState | None = None
        self._articulation_dragging: bool = False  # True only during the LMB drag that produces the angle
        self._articulation_press_x: int = 0
        self._articulation_press_y: int = 0

        # Box-Select-State (AP-03 Variante C)
        self._box_start: tuple[int, int] | None = None
        self._box_end: tuple[int, int] | None = None

        self.activate()

    # -- Initial-Szene (AD-010: mit echtem GL-Store, nach Kontext) -------------

    def _load_initial_scene(self, initial_mesh: str) -> None:
        """Lädt die Startszene mit `PlaygroundPygletStore` (echtes GL-Backend).

        Einzige Stelle, an der das Live-Fenster eine Szene lädt — Aufrufer
        (run.py, _diag_screenshot.py) übergeben nur noch die gewünschte
        Szene als String, statt selbst `app.load_*()` mit einem Store-Typ
        aufzurufen (der vor Fenster-/Kontext-Erzeugung ohnehin nicht
        GL-fähig wäre).
        """
        if initial_mesh == "head":
            self.app.load_head(store_type=PlaygroundPygletStore)
        elif initial_mesh == "cylinder":
            self.app.load_cylinder(store_type=PlaygroundPygletStore)
        else:
            self.app.load_cube(store_type=PlaygroundPygletStore)

    # -- VBO-Aufbau -----------------------------------------------------------

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
            self.app.scene.selection.hovered = None

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
            self._rebuild_vbo()
            self._rebuild_selection_vbo()
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
            flat_slot = 0
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
            flat_slot = 0
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
            for flat_slot, v in enumerate(mesh.all_vertex_ids()):
                if v == vid:
                    pos_buf.set_region(flat_slot, 1, new_pos)
                    break

        # Selection VBO: single selected vertex highlight (always slot 0 for single-vertex selection).
        if self._vlist_sel_verts is not None:
            pos_buf = self._vlist_sel_verts.domain.attrib_name_buffers["position"]
            pos_buf.set_region(0, 1, new_pos)

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

        self._tweak_tool = create_tool_for_type(tool_type)
        success = begin_transform(self._tweak_tool, self.app.scene, self.app.camera, sel)
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
        self._tweak_v3_lmb = False
        self._tweak_v3_tool_type = None

    # -- Kamera-Push ----------------------------------------------------------

    def _push_camera(self) -> None:
        if self.height == 0:
            return
        aspect = self.width / self.height
        if self._renderer is not None:
            self._renderer.notify_camera_changed(aspect=aspect)
            self._renderer.sync()
        self._update_hud()

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

        # Articulation: LMB press when articulation family is focused starts a bend gesture.
        # Axis: computed per-frame from drag direction — see on_mouse_drag.
        # Radius: full bounding radius — every vertex participates regardless of pivot location.
        if (
            button == _mouse.LEFT
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

        tv = self._active_tweak_variant()
        if button == self.input_map.select_button:
            if tv == "v2" and self._tweak_ctrl_held:
                # V2: Ctrl was held at LMB press → arm Tweak (Ctrl may now be released)
                self._tweak_v2_armed = True
                self.activate()
                return pyglet.event.EVENT_HANDLED
            if tv == "v3" and self._tweak_v3_key is not None:
                # V3: X/R/S key held + LMB → arm Tweak (key may be released mid-drag)
                self._tweak_v3_lmb = True
                self._tweak_v3_tool_type = {
                    "x": "move", "r": "rotate", "s": "scale"
                }[self._tweak_v3_key]
                self.activate()
                return pyglet.event.EVENT_HANDLED

        if (
            self.app.select_method is SelectMethod.BOX
            and button == self.input_map.select_button
            and self._transform_key_down is None
            and not self._transform_mode_on
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
                self._rebuild_selection_vbo()
            return pyglet.event.EVENT_HANDLED

        # Tweak: running gesture update (V2 or V3 — LMB governs)
        if self._tweak_active and self._tweak_started and self._tweak_tool is not None:
            update_transform(self._tweak_tool, float(dx), float(dy), self.width, self.height)
            self._sync_after_transform()
            return pyglet.event.EVENT_HANDLED

        tv = self._active_tweak_variant()

        # V2: first drag after Ctrl+LMB arm → begin Tweak
        if tv == "v2" and self._tweak_v2_armed and self.app.viewport is not None:
            if self._tweak_persistent_mode is not None:
                ok = self._tweak_begin(self._tweak_persistent_mode, x, y)
                if ok and self._tweak_started:
                    update_transform(
                        self._tweak_tool, float(dx), float(dy), self.width, self.height,
                    )
                    self._sync_after_transform()
            return pyglet.event.EVENT_HANDLED

        # V3: first drag after key+LMB arm → begin Tweak
        if tv == "v3" and self._tweak_v3_lmb and self.app.viewport is not None:
            if self._tweak_v3_tool_type is not None:
                ok = self._tweak_begin(self._tweak_v3_tool_type, x, y)
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
                success = begin_transform(
                    self.app.active_tool,
                    self.app.scene,
                    self.app.camera,
                    self.app.scene.selection,
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
        return pyglet.event.EVENT_HANDLED

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        was_click = self._drag_moved < CLICK_THRESHOLD
        self._drag_button = None

        # Articulation drag end — bent state persists, mouse is now free for camera.
        if self._articulation_dragging:
            self._articulation_dragging = False
            self._hud.update_action("Articulation bent — F = restore")
            self._update_hud()
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
            # V3: LMB release = commit
            if tv == "v3" and self._tweak_v3_lmb:
                if self._tweak_active:
                    self._tweak_commit()
                else:
                    self._clear_tweak_gesture()
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
            self._rebuild_vbo()
            self._rebuild_selection_vbo()
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
            self._clear_transform_state()
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

        # Loop Slide: Motion-Update im Hold-Modell (AP-05)
        if self._loop_slide_tool is not None:
            self._loop_slide_tool.update(dx=float(dx), dy=float(dy), width=self.width, height=self.height)
            self._rebuild_vbo()
            return pyglet.event.EVENT_HANDLED

        # Extrude: Motion-Update nur im Hold-Modell (AP-05)
        if self._extrude_tool is not None and self._active_extrude_model() == "hold":
            self._extrude_tool.update(dx=float(dx), dy=float(dy), width=self.width, height=self.height)
            self._rebuild_vbo()
            self._rebuild_selection_vbo()
            return pyglet.event.EVENT_HANDLED

        tv = self._active_tweak_variant()

        # V1: key held + motion → accumulate, start Tweak once past CLICK_THRESHOLD
        if tv == "v1" and self._tweak_v1_key is not None and self.app.viewport is not None:
            self._tweak_v1_moved += abs(dx) + abs(dy)
            if not self._tweak_active and self._tweak_v1_moved >= CLICK_THRESHOLD:
                tool_type = {"x": "move", "r": "rotate", "s": "scale"}[self._tweak_v1_key]
                self._tweak_begin(tool_type, x, y)
            if self._tweak_started and self._tweak_tool is not None:
                update_transform(
                    self._tweak_tool, float(dx), float(dy), self.width, self.height,
                )
                self._sync_after_transform()
            return pyglet.event.EVENT_HANDLED

        # V4: Ctrl held + motion → Tweak with persistent mode (no LMB needed)
        if tv == "v4" and self._tweak_ctrl_held and self.app.viewport is not None:
            if not self._tweak_active and self._tweak_persistent_mode is not None:
                self._tweak_begin(self._tweak_persistent_mode, x, y)
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
                success = begin_transform(
                    self.app.active_tool,
                    self.app.scene,
                    self.app.camera,
                    self.app.scene.selection,
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
            if hit != sel.hovered:
                sel.hovered = hit
                self._rebuild_hover_vbo()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == _key.C:
            self.app.load_cube(store_type=PlaygroundPygletStore)
            self._rebuild_vbo()
            self._push_camera()
        elif symbol == _key.H:
            self.app.load_head(store_type=PlaygroundPygletStore)
            self._rebuild_vbo()
            self._push_camera()
        elif symbol == _key.Y and not (modifiers & _key.MOD_CTRL):
            # Y (bare): load cylinder (EX-A test body). Ctrl+Y remains Redo.
            self.app.load_cylinder(store_type=PlaygroundPygletStore)
            if self._articulation_state is not None:
                self._articulation_state = None
                self._articulation_dragging = False
            self._rebuild_vbo()
            self._rebuild_selection_vbo()
            self._push_camera()
        elif symbol == self.input_map.display_cycle:
            slot = self.app.slots.get("presentation")
            if slot is not None:
                self.app.activate_variant("presentation", (slot.active_index + 1) % slot.variant_count)
            else:
                self.app.display_state.cycle()
            self._update_hud()
        elif symbol == _key.Z and modifiers & _key.MOD_CTRL:
            # Ctrl+Z: Undo (WP-AP-Enablement-01) — dieselbe Bindung wie
            # Production (tests/test_application.py: bindings["ctrl+z"] == UNDO).
            self.app.undo()
            self.app.scene.selection.clear()
            self._rebuild_vbo()
            self._hud.update_action("Undo")
            self._update_hud()
        elif symbol == _key.Y and modifiers & _key.MOD_CTRL:
            # Ctrl+Y: Redo — Production-Bindung (siehe oben).
            self.app.redo()
            self.app.scene.selection.clear()
            self._rebuild_vbo()
            self._hud.update_action("Redo")
            self._update_hud()
        elif symbol == _key.K:
            # K: Split Edge (WP-AP-Enablement-01). Scope: nur Edge-Modus mit
            # genau einer selektierten Edge; kein Aktivierungsvarianten-
            # Research (das ist AP-05) — ein fester, einfachster Trigger.
            sel = self.app.scene.selection
            if sel.mode is SelectionMode.EDGE and len(sel.edges) == 1:
                restored = self._articulation_auto_restore()
                (edge_id,) = sel.edges
                split_selected_edge(self.app.scene, edge_id)
                sel.clear()
                self._rebuild_vbo()
                action = "Split Edge (articulation restored)" if restored else "Split Edge"
                self._hud.update_action(action)
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
                    self._rebuild_vbo()
                    suffix = " (articulation restored)" if restored else ""
                    self._hud.update_action(f"Loop Insert — {len(new_edges)} Edges{suffix}")
                except _LoopInsertError as exc:
                    self._hud.update_action(str(exc))
                self._update_hud()
        elif symbol == _key.J:
            # J: Connect Edges (AP-05). Scope: Edge-Modus, 2+ Edges selektiert.
            # Kein Hover-Fallback — Connect Edges verlangt echte Mehrfachauswahl.
            sel = self.app.scene.selection
            if sel.mode is SelectionMode.EDGE and len(sel.edges) >= 2:
                restored = self._articulation_auto_restore()
                try:
                    new_edges = connect_selected_edges(self.app.scene, set(sel.edges))
                    sel.clear()
                    sel.add(set(new_edges))
                    self._rebuild_vbo()
                    action = "Connect Edges (articulation restored)" if restored else "Connect Edges"
                    self._hud.update_action(action)
                except _ConnectEdgesError as exc:
                    self._hud.update_action(str(exc))
                self._update_hud()
        elif symbol == _key.E:
            # E: Extrude Face (AP-05). Scope: Face-Modus.
            # - 1+ Faces selektiert → diese extrudieren (Multi-Face-Extrude).
            # - Leer → Face unter Cursor per Hit-Test (Hover-Fallback, AP-05).
            sel = self.app.scene.selection
            if (
                sel.mode is SelectionMode.FACE
                and self.app.viewport is not None
                and self._extrude_tool is None
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
                self._rebuild_selection_vbo()
                n = len(face_ids)
                action = f"Extrude ({n} faces)" if n > 1 else "Extrude"
                restore_note = " (articulation restored)" if restored else ""
                self._hud.update_action(f"{action}{restore_note} — move mouse to set distance, release E = commit, ESC = cancel")
                self._update_hud()
        elif symbol == self.input_map.wire_overlay:
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
        elif symbol == _key.M:
            # Cyclt innerhalb der focused_family — nie family-übergreifend.
            active_family = self.app.focused_family
            slot = self.app.slots.get(active_family)
            if slot is not None:
                # Transform-State zurücksetzen wenn Aktivierungsmodell wechselt
                if active_family == "transform" and (self._transform_key_down or self._transform_mode_on):
                    if self._transform_started and self.app.active_tool is not None:
                        cancel_transform(self.app.active_tool)
                        self._sync_after_transform()
                    self._clear_transform_state()
                self.app.activate_variant(active_family, (slot.active_index + 1) % slot.variant_count)
            self._update_hud()
        elif symbol == _key.Q:
            # Cycle SelectMethod (Method): PICK → BOX → LASSO → PAINT → PICK
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
            self._rebuild_selection_vbo()
            self._update_hud()
        elif symbol == _key._2:
            # 2: Edge-Modus
            sel = self.app.scene.selection
            sel.mode = SelectionMode.EDGE
            sel.clear()
            self._rebuild_selection_vbo()
            self._update_hud()
        elif symbol == _key._3:
            # 3: Face-Modus
            sel = self.app.scene.selection
            sel.mode = SelectionMode.FACE
            sel.clear()
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
        elif symbol == _key.R and (modifiers & _key.MOD_SHIFT):
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
        elif symbol in (_key.LCTRL, _key.RCTRL):
            self._tweak_ctrl_held = True
        elif symbol in (_key.X, _key.R, _key.S):
            _key_char = {_key.X: 'x', _key.R: 'r', _key.S: 's'}[symbol]
            _tool_type = {'x': 'move', 'r': 'rotate', 's': 'scale'}[_key_char]
            tv = self._active_tweak_variant()
            if tv == "v1":
                # V1: arm the self-deciding gesture; key-up will decide toggle vs. Tweak
                self._tweak_v1_key = _key_char
                self._tweak_v1_moved = 0.0
                # Does NOT run existing transform handling — V1 owns X/R/S when active
            elif tv == "v3":
                # V3: arm the key side of the key+LMB combo (LMB press completes it)
                self._tweak_v3_key = _key_char
                # Does NOT run existing transform handling — V3 owns X/R/S when active
            else:
                # Existing transform handling (V2, V4, or no tweak)
                model = self._active_transform_model()
                if model == "hold":
                    self._transform_key_down = _key_char
                    self.app.active_tool = create_tool_for_type(_tool_type)
                else:  # press_mode oder press_drag_click
                    if self._transform_mode_on:
                        # Zweiter Druck derselben Taste → Commit (wenn gestartet), Mode verlassen
                        if self._transform_started and self.app.active_tool is not None:
                            commit_transform(self.app.active_tool)
                            self._sync_after_transform()
                        self._clear_transform_state()
                    else:
                        # Erster Druck → Mode aktivieren
                        self._transform_key_down = _key_char
                        self._transform_mode_on = True
                        self.app.active_tool = create_tool_for_type(_tool_type)
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
        elif symbol == _key.ESCAPE:
            if self._articulation_state is not None:
                self._articulation_state.restore()
                self._articulation_state = None
                self._articulation_dragging = False
                self._rebuild_vbo()
                self._hud.update_action("Articulation restored")
                self._update_hud()
            elif self._loop_slide_tool is not None:
                self._loop_slide_tool.cancel()
                self._loop_slide_tool.deactivate()
                self._loop_slide_tool = None
                self._rebuild_vbo()
                self._hud.update_action("Loop Slide cancelled")
                self._update_hud()
            elif self._extrude_tool is not None:
                self._extrude_tool.cancel()
                self._extrude_tool.deactivate()
                self._extrude_tool = None
                self._rebuild_vbo()
                self._rebuild_selection_vbo()
                self._hud.update_action("Extrude cancelled")
                self._update_hud()
            elif self._tweak_active and self._tweak_tool is not None:
                self._tweak_cancel()
            elif self._tweak_v1_key is not None:
                # V1: key held but no Tweak started — ESC cancels the armed state
                self._tweak_v1_key = None
                self._tweak_v1_moved = 0.0
            elif self._tweak_v3_key is not None or self._tweak_v3_lmb:
                # V3: armed but no Tweak started — ESC cancels
                self._tweak_v3_key = None
                self._clear_tweak_gesture()
            elif (self._transform_started or self._transform_mode_on or self._transform_key_down) \
                    and self.app.active_tool is not None:
                if self._transform_started:
                    cancel_transform(self.app.active_tool)
                self._sync_after_transform()
                self._clear_transform_state()
            else:
                self.close()
        return pyglet.event.EVENT_HANDLED

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        """Handle key release — Commit-Verhalten abhängig vom Aktivierungsmodell."""
        if symbol == _key.G and self._loop_slide_tool is not None:
            # G loslassen = Commit (AP-05 Hold-Modell)
            self._loop_slide_tool.commit()
            self._loop_slide_tool.deactivate()
            self._loop_slide_tool = None
            self._rebuild_vbo()
            self._hud.update_action("Loop Slide")
            self._update_hud()
            return pyglet.event.EVENT_HANDLED
        elif symbol == _key.E and self._extrude_tool is not None and self._active_extrude_model() == "hold":
            # E loslassen = Commit (AP-05 Hold-Modell)
            self._extrude_tool.commit()
            self._extrude_tool.deactivate()
            self._extrude_tool = None
            self._rebuild_vbo()
            self._rebuild_selection_vbo()
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
        elif symbol in (_key.X, _key.R, _key.S):
            _key_char = {_key.X: 'x', _key.R: 'r', _key.S: 's'}[symbol]
            tv = self._active_tweak_variant()
            if tv == "v1" and self._tweak_v1_key == _key_char:
                # V1: self-deciding — was it a mode-toggle or a Tweak?
                if self._tweak_v1_moved < CLICK_THRESHOLD:
                    # No significant movement → mode toggle (tap without drag)
                    # [OPEN QUESTION: mode-toggle does NOT fire if a Tweak drag happened.
                    #  This is the simpler/more-predictable choice: a drag "overwrites"
                    #  the press intent entirely. Flag for observation during playtesting.]
                    _tool_type = {"x": "move", "r": "rotate", "s": "scale"}[_key_char]
                    self._tweak_persistent_mode = toggle_persistent_mode(
                        self._tweak_persistent_mode, _tool_type,
                    )
                else:
                    # Drag happened → commit if Tweak was active
                    if self._tweak_active:
                        self._tweak_commit()
                self._tweak_v1_key = None
                self._tweak_v1_moved = 0.0
                self._update_hud()
            elif tv == "v3" and self._tweak_v3_key == _key_char:
                # V3: key released but LMB may still be held → LMB continues to govern
                self._tweak_v3_key = None
                # _tweak_v3_lmb and gesture remain active until LMB release
            elif self._transform_key_down == _key_char:
                model = self._active_transform_model()
                if model == "hold":
                    # Hold: Loslassen = Commit
                    if self._transform_started and self.app.active_tool is not None:
                        commit_transform(self.app.active_tool)
                        self._sync_after_transform()
                    self._clear_transform_state()
                else:
                    # Press-Mode / Press-Drag-Click: Loslassen = kein Commit, Mode bleibt aktiv
                    self._transform_key_down = None  # Taste nicht mehr gehalten, Mode bleibt
        return pyglet.event.EVENT_HANDLED

    # -- Draw -----------------------------------------------------------------

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
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        self._hud.draw()

        return pyglet.event.EVENT_HANDLED
