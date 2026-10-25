"""Produktions-Application-Orchestrator (window-frei).

Gate 3 (Application Foundation): Erstellt und verbindet die
Core-Strukturen (Scene/Selection/History), die Viewport-State-Komponenten
(OrbitCamera/DisplayState, ohne Rendering), das Tool-Registry/ToolManager-
System und die Default-Input-Bindings.

Architekturpfad:

    Input (physikalisch)
      ↓ BindingSet.command_for(input)      [mirai.interaction.input]
    Command (semantisch)
      ↓ Application.dispatch_command(...)  [dieses Modul]
    Tool-Aktivierung | direkte Aktion      [mirai.interaction.tool_manager]
      ↓
    Operation (Core)                        [src.core]
      ↓
    Mesh / History

Wichtig:
- Kein Fenster, kein pyglet, kein Rendering — der gesamte Zustand ist
  headless testbar.
- Import des Cores erfolgt als top-level Paket `core` (realer Produktions-
  Pfad `src/core/`), nicht als `mirai.core` — der Core bleibt eigenständig
  und frozen (ADR-001 erlaubt nur die dokumentierte Transform-Promotion).
- Gate 5 implementiert den v0.2-Viewport (`src/viewport`) inkl. der
  Render-/GPU-Ressourcen; hier halten wir nur den window-freien State.
- Gate 7 verbindet Application.camera mit dem V0.2-Viewport: `init_scene()`
  erstellt den Viewport und bindet die OrbitCamera (Duck-Typing). Application
  bleibt window-frei; `src/viewport` bleibt unabhängig von `src/mirai`.
"""

from __future__ import annotations

import dataclasses
import math
import os
import time
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional

from core import (
    EdgeId,
    FaceId,
    HistoryStack,
    Mesh,
    MirrorPair,
    ObjectId,
    ObjectMaterial,
    ObjectState,
    ObjectTransform,
    Scene,
    SceneObject,
    Selection,
    SelectionMode,
    VertexId,
)
from core.mesh import MeshChange
from core.operations import CollapseRefused, MeshDeltaCommand, record_mesh_change
from core.scene import IDENTITY_TRANSFORM
from core.serialization import scene_from_json, scene_to_json
from core.operations.transform import SeamConstraintError

from viewport import Viewport  # Gate 7: V0.2 Rendering-Viewport (unabhängig von mirai)
from viewport.overlay import (
    TOOL_ACTIVE_LAYER,
    TOOL_CLIPPED_LAYER,
    TOOL_MIRROR_DIM_LAYER,
    TOOL_MIRROR_LAYER,
    TOOL_MIRROR_PREVIEW_LAYER,
    TOOL_PREVIEW_LAYER,
    TOOL_REFUSED_LAYER,
)
from viewport.gl_render_store import DEFAULT_BASE_COLOR
from viewport.resource_store import ResourceStore, TraceStore

from . import regions as face_regions_api
from .hidden import HiddenSet, touches_hidden, visible
from .mask import (
    VertexMask,
    effective_mask,
    mask_symmetric_influence,
    mask_weights,
    unblocked,
)
from .interaction import BindingSet, Input, ToolManager, commands
from .interaction.bindings import build_default_bindings, load_keymap_overrides
from .interaction.input import KNIFE_CONTEXT, SUBD_CONTEXT
from .interaction.dial import PRECISION_GAIN, DialAngle
from .interaction.pointer import CLICK_THRESHOLD_PX, Click, DragStep, PointerGestures
from .interaction.routing import tool_for_command
from .interaction.tools import resolve_selection_vertices
from .interaction.tools.selection_helpers import selection_pivot
from .interaction.tools.rotate import RotateTool
from .interaction.tools.scale import ScaleTool
from .interaction.tools.transform import _resolve_space
from .mesh_geometry import mesh_center_and_radius
from . import object_space
from .object_space import ObjectSpaceCamera
from .object_mirror import PLANES as MIRROR_PLANES, in_sync, mirror_mesh, mirror_placement, mirror_transform
from .scene_objects import (
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
    replace_scene,
    resync_command,
    selected_color,
    reset_scene,
    unique_object_name,
)
from .soft_selection import (
    EMPTY_BANDS,
    RADIUS_STEPS_PERCENT,
    SoftBands,
    SoftSettings,
    SoftSymmetryRefusal,
    compute_influence,
    has_flow_direction,
    symmetric_influence,
)
from .topology.connect_per_face import EDGE_CONNECT_LABEL, TopologyToolError, apply_connect_edges
from .topology.connect_vertices_per_face import (
    VERTEX_CONNECT_LABEL,
    VertexConnectError,
    apply_connect_vertices,
)
from .symmetry_coordination import (
    SymmetryIndex,
    canonical_edges,
    canonical_faces,
    canonical_vertices,
    expand_faces,
)
from .symmetric_ops import SymmetryRefusal, on_residue_sides, residue_sides
from .symmetry import CorrespondenceState, mirrored_selection, symmetry_state, vertex_correspondence
from .symmetry_axis import current_axis, next_axis, set_symmetry_axis
from .symmetry_display import ReportCache, SymmetryDisplay
from .resymmetrize import (
    ResymmetrizeRejected,
    ResymPlan,
    plan_description,
    plan_resymmetrize,
    plan_summary,
    set_plan_positions,
)
from . import symmetry_declarations
from .topology.contextual_c import CContext, resolve_c_context
from .topology.collapse import COLLAPSE_LABEL, apply_collapse
from .topology.smooth import PX_PER_STEP as SMOOTH_PX_PER_STEP, TAP_AMOUNT as SMOOTH_TAP_AMOUNT
from .topology.smooth import RELAX_LABEL, SMOOTH_LABEL, SmoothPlan, SmoothRefused, plan_smooth
from .topology.delete_dissolve import RemovalRefused, apply_removal, removal_label
from .topology.face_geometry import GEO_EPS
from .topology.knife import CLOSE_NEEDS, EARLIER_INTERIOR, TOO_CLOSE, KnifeTool
from .topology.knife_pick import knife_pick, snap_own_point, space_point
from .topology.knife_preview import KnifeRenderData, build_knife_render_data
from .topology.loop_ring import LoopRingError, edge_loop, edge_ring
from .topology import selection_steps
from .topology.loop_slide import (
    LOOP_SLIDE_LABEL,
    LoopSlideRefused,
    SlidePlan,
    plan_loop_slide,
    slide_positions,
)
from .symmetric_knife import KnifeRefusal, SymmetricKnifeView
from .subdivision import SUBD_COMMANDS, SubdivisionPreview, install_subd_bindings
from .subdivision.preview import key_label
from .viewport import DisplayMode, DisplayState, OrbitCamera
from .viewport.box_select import (
    elements_in_polygon,
    elements_in_rect,
    normalized_rect,
    point_in_polygon,
    polygon_bounds,
    stroke_samples,
)
from .viewport import gizmo as _gizmo
from . import transform_space
from .viewport.look_controls import (
    DRAG_DEGREES_PER_PIXEL,
    LOOK_ROWS,
    MaterialRow,
    LookRow,
    clamp_material_values,
    light_row,
    material_row,
)
from .viewport.gpu_picking import gpu_elements_in_rect, gpu_elements_in_region, gpu_pick_component
from .viewport.picking import pick_component, pick_face, pick_object
from .viewport.picking_cache import PickCache


#: Orbit-Rate (rad/px) und Dolly-Faktoren — aus `src/main.py` (Stage A/B1)
#: hierher verschoben, Werte unverändert (WP-06 B2, E11).
ORBIT_RADIANS_PER_PX = 0.005
DOLLY_IN_FACTOR = 0.9
DOLLY_OUT_FACTOR = 1.1

_SELECT_COMMANDS = (
    commands.SELECT,
    commands.SELECT_ADD,
    commands.SELECT_REMOVE,
    commands.SELECT_TOGGLE,
)


#: WP-06 B4 (E28): die Commands, die über denselben AD-016-hold-key-hover-Pfad
#: scharf geschaltet werden (Move/Rotate/Scale; seit WP-06 B9 auch Extrude, dessen
#: Ziel Faces statt Vertices und dessen Begin-Payload `face_ids` statt `vertex_ids`
#: ist - Zweige dafür in `_transform_arm/_step/key_release/_cancel`). Werte: (Label,
#: Verb, Partizip) für die Statuszeilen (E34, `PROVISIONAL`).
_TRANSFORM_COMMANDS: dict[str, tuple[str, str, str]] = {
    commands.MOVE: ("Move", "move", "moved"),
    commands.ROTATE: ("Rotate", "rotate", "rotated"),
    commands.SCALE: ("Scale", "scale", "scaled"),
    commands.EXTRUDE: ("Extrude", "extrude", "extruded"),
    # 2026-10-15 (loop tools promoted): hold G, the same hold-key family as T.
    commands.LOOP_SLIDE: ("Loop Slide", "slide", "slid"),
    # WP Toolbox Gaps C2: hold S / Alt+S, same family (a tap is one step, see `_smooth_release`).
    commands.SMOOTH: ("Smooth", "smooth", "smoothed"),
    commands.RELAX: ("Relax", "relax", "relaxed"),
}

#: WP Toolbox Gaps C2: the two hold keys of `mirai.topology.smooth`.
_SMOOTH_COMMANDS = (commands.SMOOTH, commands.RELAX)

#: The pseudo key a Tweak gesture (Ctrl+LMB drag) arms the transform with; no key has this
#: value, so `key_release` never ends a Tweak - the LMB release does (`pointer_release`).
TWEAK_KEY = "LMB-tweak"

#: 2026-10-15: the loop commands that run once on a key press (Shift+L, Shift+R, I).
_LOOP_COMMANDS = (commands.EDGE_LOOP, commands.EDGE_RING, commands.LOOP_INSERT)

#: WP Toolbox Gaps A1 (2026-10-23): the selection steps (`_selection_step`), once per press.
_SELECTION_STEP_COMMANDS = (
    commands.SELECT_GROW,
    commands.SELECT_SHRINK,
    commands.LOOP_GROW,
    commands.LOOP_SHRINK,
    commands.LOOP_NEXT,
    commands.LOOP_PREVIOUS,
)

#: The transforms a Tweak can use (`tweak_command`).
_TWEAK_TRANSFORMS = (commands.MOVE, commands.ROTATE, commands.SCALE)

#: WP-06 B9 (E3, PROVISIONAL, agent-set): Extrude mutates the topology in `begin()`,
#: so unlike Move/Rotate/Scale (AD-016: first motion begins) it needs the pointer's net
#: displacement since the arm to reach this many logical pixels first; a tap or a hand
#: tremble below it does nothing at all.
EXTRUDE_BEGIN_PX = 4.0

#: The gizmo's name for the tool a handle drag runs (`Application.tweak_command`, the last W/E/R).
_GIZMO_TOOLS = {commands.MOVE: "move", commands.ROTATE: "rotate", commands.SCALE: "scale"}

#: Pixels the pointer must move before the next Lasso outline point is added (`PROVISIONAL`).
LASSO_POINT_SPACING_PX = 3.0
#: WP-06 B9 (E3, PROVISIONAL, agent-set): at release an Extrude whose |total distance|
#: is below this (world units) counts as cancelled - exact prior state, no history.
EXTRUDE_MIN_DISTANCE = 1e-6

#: WP-06 B4 (E32): Constraint-Command → `space`-String nach AD-012
#: (`transform._resolve_space`). Welche Taste welches Command auslöst
#: (Blender: Shift+Achse schließt diese Achse aus), steht in `bindings.py`.
_CONSTRAINT_SPACES: dict[str, str] = {
    commands.CONSTRAIN_AXIS_X: "x",
    commands.CONSTRAIN_AXIS_Y: "y",
    commands.CONSTRAIN_AXIS_Z: "z",
    commands.CONSTRAIN_PLANE_XY: "xy",
    commands.CONSTRAIN_PLANE_XZ: "xz",
    commands.CONSTRAIN_PLANE_YZ: "yz",
}


#: WP-06 B5a (E42): Display-Commands, alle über die bestehenden
#: `DisplayState`-Übergänge.
_DISPLAY_COMMANDS = (
    commands.CYCLE_DISPLAY_MODE,
    commands.TOGGLE_WIREFRAME_OVERLAY,
    commands.SET_SHADED,
    commands.SET_FLAT_SHADED,
    commands.SET_WIREFRAME,
    commands.TOGGLE_REFERENCE_GHOST,
    commands.CYCLE_LIGHT_PRESET,
    commands.TOGGLE_LIGHT_SPACE,
    commands.TOGGLE_REGION_TINT,
)

#: AD-024 §8 (`PROVISIONAL`): the Look rows - choose a row, step its value. Light rows are view state
#: (no Undo step), allowed at any time like the display keys.
_LOOK_COMMANDS = (
    commands.LOOK_ROW_PREV,
    commands.LOOK_ROW_NEXT,
    commands.LOOK_VALUE_DEC,
    commands.LOOK_VALUE_INC,
    commands.LOOK_VALUE_DEC_FINE,
    commands.LOOK_VALUE_INC_FINE,
)

_SET_DISPLAY_MODES: dict[str, DisplayMode] = {
    commands.SET_SHADED: DisplayMode.SHADED,
    commands.SET_FLAT_SHADED: DisplayMode.FLAT_SHADED,
    commands.SET_WIREFRAME: DisplayMode.WIREFRAME,
}


#: WP-SOFT-01 S2a (AD-020, `PROVISIONAL`): the state commands of Soft Selection. They start
#: no interaction and change no mesh, like the constraints: they set the sticky
#: `SoftSettings`, which the next gesture reads at `begin()`.
_MASK_COMMANDS = (commands.MASK_TOGGLE, commands.MASK_INVERT, commands.MASK_CLEAR)
_HIDE_COMMANDS = (commands.HIDE_SELECTION, commands.ISOLATE_SELECTION, commands.SHOW_ALL)
_REGION_COMMANDS = (
    commands.REGION_NEXT,
    commands.REGION_PREV,
    commands.REGION_NEW,
    commands.REGION_NAME,
    commands.REGION_ADD,
    commands.REGION_REMOVE,
    commands.REGION_SELECT,
    commands.REGION_SELECT_ADD,
    commands.REGION_ISOLATE,
    commands.REGION_MASK,
    commands.REGION_DELETE,
)

#: Commands that rewrite topology next to their selection: with hidden geometry around the selection they are
#: refused instead of silently changing faces the artist cannot see (`Application._hidden_refuses`). Loop Insert is not in
#: the list: its ring ends at hidden faces (`edge_ring(..., blocked)`) and `_edge_connect` guards the rest.
_TOPOLOGY_COMMANDS = frozenset(
    {
        commands.CONNECT,
        commands.COLLAPSE,
        commands.EXTRUDE,
        commands.LOOP_SLIDE,
        commands.RESYMMETRIZE,
        commands.DELETE,
        commands.DISSOLVE,
        commands.DISSOLVE_NO_CLEANUP,
    }
)

_SOFT_COMMANDS = (
    commands.SOFT_TOGGLE,
    commands.SOFT_RADIUS_UP,
    commands.SOFT_RADIUS_DOWN,
    commands.SOFT_CURVE_CYCLE,
    commands.SOFT_METRIC_CYCLE,
    commands.SOFT_CURVE_SHAPE_ROUNDER,
    commands.SOFT_CURVE_SHAPE_SHARPER,
    commands.SOFT_BANDS_TOGGLE,
    commands.SOFT_VIEW_MODE_CYCLE,
    commands.SOFT_LOOK_CYCLE,
    commands.SOFT_FLOW_LOOP,
    commands.SOFT_FLOW_RING,
)

#: `Application._gpu_pick`: the window cannot serve this pick, ask the CPU picker.
_CPU = object()


def symmetry_status_text(mesh: Mesh) -> str:
    """Status line after a symmetry cycle step (AD-SYM-04 Q-2 = S-2, its status part S-1; text
    `PROVISIONAL`): `Symmetrie X (valid)`, `Symmetrie X (partial, 54 ohne Partner)`,
    `Symmetrie aus`."""
    axis = current_axis(mesh)
    if axis is None:
        return "Symmetrie aus"
    states = [c.state for c in vertex_correspondence(mesh).values()]
    details = [symmetry_state(mesh).value]
    unpaired = states.count(CorrespondenceState.UNPAIRED)
    ambiguous = states.count(CorrespondenceState.AMBIGUOUS)
    if unpaired:
        details.append(f"{unpaired} ohne Partner")
    if ambiguous:
        details.append(f"{ambiguous} mehrdeutig")
    return f"Symmetrie {axis} ({', '.join(details)})"


@dataclasses.dataclass(frozen=True)
class _MeshTransaction:
    """Outcome of `Application._mesh_transaction`: whether an entry was pushed, and what the
    mutation returned."""

    changed: bool
    result: Any


#: WP Delete/Dissolve: Command → (dissolve, cleanup) für `remove_selected`.
_REMOVAL_COMMANDS: dict[str, tuple[bool, bool]] = {
    commands.DELETE: (False, False),
    commands.DISSOLVE: (True, True),
    commands.DISSOLVE_NO_CLEANUP: (True, False),
}

#: WP-06 B5b (E43): Component-Modi 1/2/3 (Selection Lab KEEP, `PROMOTED`); AD-021 M1: `4` =
#: Objekt-Modus (V1_SPEC §2).
_MODE_COMMANDS: dict[str, SelectionMode] = {
    commands.SET_VERTEX_MODE: SelectionMode.VERTEX,
    commands.SET_EDGE_MODE: SelectionMode.EDGE,
    commands.SET_FACE_MODE: SelectionMode.FACE,
    commands.SET_OBJECT_MODE: SelectionMode.OBJECT,
}

#: AD-021 M1 (L-1: one gesture writes one level): commands that work on the edit object's
#: components. In mode `4` they are refused with a status line, except the object transforms
#: below; a Reference is locked (RF-4, Q-1). Undo/Redo, display, Soft settings and constraints
#: are state or history, not component work, and stay allowed.
_COMPONENT_COMMANDS = frozenset(
    {
        *_TRANSFORM_COMMANDS,
        commands.CONNECT,
        *_REMOVAL_COMMANDS,
        commands.COLLAPSE,
        commands.SYMMETRY_CYCLE,
        commands.RESYMMETRIZE,
        *_MASK_COMMANDS,
        *_HIDE_COMMANDS,
        *_REGION_COMMANDS,
        *_LOOP_COMMANDS,
        *_SELECTION_STEP_COMMANDS,
    }
)

#: AD-SYM-04 A3: what an open Re-Symmetrize preview answers to every other bound key, click or
#: Soft step (the Lab's text, `PROVISIONAL`); the plan summary follows it so it stays readable.
RESYM_PREVIEW_HINT = "Vorschau aktiv — Befehl ignoriert"

#: AD-021 M2-2 (E-11): in mode `4` W/E/R arm the object gesture (`_object_arm`) instead of a
#: component tool; T (Extrude) stays component work.
_OBJECT_TRANSFORM_COMMANDS = frozenset({commands.MOVE, commands.ROTATE, commands.SCALE})

#: AD-021 M2-3 (L-3): the two explicit level conversions, mode `4` only. Labels for the status
#: line (`PROVISIONAL`).
_PLACEMENT_COMMANDS: dict[str, str] = {
    commands.APPLY_TRANSFORM: "Apply transform",
    commands.CLEAR_TRANSFORM: "Clear transform",
}


@dataclasses.dataclass
class _ObjectGesture:
    """A W/E/R gesture in mode `4` (AD-021 M2-2, E-11): the targets with their start transforms
    (Esc restores exactly these), the References of the selection that stay where they are, the
    selection snapshot for the mirror entry, and what the motion has accumulated so far. Every
    step recomputes each transform from its start, so nothing drifts inside one gesture."""

    targets: list[tuple[SceneObject, ObjectTransform]]
    references: tuple[str, ...]
    selection_before: tuple
    axis: tuple[float, float, float] | None = None
    mask: tuple[float, float, float] | None = None
    move: tuple[float, float, float] = (0.0, 0.0, 0.0)
    pixels: float = 0.0
    angle: float = 0.0  # Rotate: the total angle (rad), from the dial or the dx fallback
    dial: DialAngle | None = None
    # Mirror pairs (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.4): (follower, its start, driver, driver's
    # start, pair). The follower is F(driver) after every step - stateless, nothing accumulates.
    followers: list = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class _DragSelect:
    """A running LMB drag selection (2026-10-15, Manu: "Startpunkt entscheidet"): `box` when
    the press was in empty space, else `paint`; with the Lasso key held (2026-10-21) `lasso`
    whatever the press point. `add` = Shift (adds) instead of replacing.
    `before` is the selection at the start (Esc restores it); `last` the last painted point;
    `points` the lasso outline so far (window pixels). Alt held at the release makes a box or lasso
    select through the mesh (WP Toolbox Gaps A2, Manu 2026-10-23); paint stays visible-only."""

    kind: str
    add: bool
    start: tuple[float, float]
    end: tuple[float, float]
    before: tuple
    last: tuple[float, float]
    cancelled: bool = False
    points: list = dataclasses.field(default_factory=list)


def _element_vertices(mesh, element) -> set[VertexId]:
    """Vertices eines einzelnen Vertex/Edge/Face (Hover-Fallback des Transforms).

    Ein Handle, das `mesh` nicht mehr kennt (Topologie-Mutation seither),
    ergibt eine leere Menge statt eines `KeyError` — dieselbe Regel wie im
    Viewport-Overlay (`viewport/overlay.py`)."""
    if isinstance(element, VertexId):
        return {element} if mesh.is_valid_vertex(element) else set()
    if isinstance(element, EdgeId):
        return set(mesh.edge_vertices(element)) if mesh.is_valid_edge(element) else set()
    if isinstance(element, FaceId):
        return set(mesh.face_vertices(element)) if mesh.is_valid_face(element) else set()
    return set()


def _active_selection_contains(selection: Selection, element) -> bool:
    """Liegt `element` in der Auswahl des aktiven Modus (Playground
    `_sel_contains_hovered`)? Typ mitprüfen - IDs sind int-Subklassen."""
    kind, members = {
        SelectionMode.VERTEX: (VertexId, selection.vertices),
        SelectionMode.EDGE: (EdgeId, selection.edges),
        SelectionMode.FACE: (FaceId, selection.faces),
        SelectionMode.OBJECT: (ObjectId, selection.objects),
    }[selection.mode]
    return isinstance(element, kind) and element in members


def _constraint_label(space: str | None) -> str:
    """Statuszeilen-Text einer Constraint: "X", "YZ plane", "none"."""
    if space is None:
        return "none"
    return space.upper() if len(space) == 1 else f"{space.upper()} plane"


def _selection_state(selection: Selection) -> tuple[frozenset, ...]:
    return (
        frozenset(selection.vertices),
        frozenset(selection.edges),
        frozenset(selection.faces),
        frozenset(selection.objects),
    )


# WP-KNIFE-01 S3 (PROVISIONAL wording, decision.md "One Knife S3"): status for a refused Knife click
# by the tool's reason - the S3 cases are named, every other refusal keeps the S2 text.
_KNIFE_REFUSED = {
    TOO_CLOSE: "Knife: too close to an edge - click on the edge or further inside the face",
    CLOSE_NEEDS: "Knife: closing a shape needs at least 3 points",
    EARLIER_INTERIOR: "Knife: an earlier point inside a face cannot be clicked again (not yet)",
}


# WP-KNIFE-01 UX2 (D7, decision.md "WP-KNIFE-01 UX2"): two Knife clicks this close in time (s) and
# place (px) are a double-click.
KNIFE_DOUBLE_CLICK_S = 0.35
KNIFE_DOUBLE_CLICK_PX = 4.0

# AD-SYM-03 slice 6c (PROVISIONAL, the Artist's call in the 6c practical test, removed or kept in 6d): the three
# looks of the mirror side in a symmetric Knife session, switched inside the session by one provisional key.
# V-a: drawn like the working side's own preview (path lines depth-tested, points through); V-b: always
# visible (no depth test), dimmed; V-c: the mirror's points only. Default V-b: from a side camera every
# mirror point is hidden (KD 2.7), so V-a can show nothing there.
KNIFE_MIRROR_VARIANTS = ("V-a", "V-b", "V-c")
KNIFE_MIRROR_VARIANT_DEFAULT = "V-b"
KNIFE_MIRROR_VARIANT_LABELS = {
    "V-a": "wie die eigene Vorschau, verdeckt",
    "V-b": "immer sichtbar, gedimmt",
    "V-c": "nur Punkte",
}
#: The provisional variant key. A key of the Knife context that no command uses: not bound in `KNIFE_CONTEXT`
#: (nor in GLOBAL), none of the Lab's three keys, and none the Session Gate passes. It is checked here, not
#: through a command, so the command tables (and with them the Lab's gate rows) stay as they are.
KNIFE_MIRROR_VARIANT_KEY = "v"

# The preview builder ends a chain at a "closed" break only; a pen lift is drawn the same way.
_KNIFE_DRAWN_LIFT = {"kind": "break", "reason": "closed", "cyclic": False}


def _knife_notes(res) -> list[str]:
    """What the commit joined or dropped (`KnifeResolution`), for the status line. Nothing of it is
    shown while cutting (Artist, 2026-09-30: the join to the nearest corner is made at commit only)."""
    if res is None:
        return []
    notes = []
    if res.joined:
        notes.append(f"{res.joined} last point(s) inside a face joined to the nearest corner")
    if res.dropped_tail:
        notes.append("a last point inside a face could not be joined to a corner - dropped")
    if res.dropped_lead:
        notes.append("first point(s) inside a face before any edge or vertex dropped")
    rejected = [shape for shape in res.closed_shapes if not shape.built]
    if rejected:
        notes.append(f"{len(rejected)} closed shape(s) could not be built")
    if res.short_shapes:
        notes.append(f"{len(res.short_shapes)} shape(s) inside a face with fewer than 3 points dropped")
    if res.skipped_shapes:
        notes.append(f"{res.skipped_shapes} closed shape(s) skipped - their face was already cut")
    for reason, n in sorted(res.loops_dropped.items()):
        notes.append(f"{n} loop(s) closed at a point dropped ({reason})")
    if res.lost_continuation:
        notes.append("the cut on from an interior start point dropped")
    return notes


def _knife_plan_notes(plan) -> list[str]:
    """What a click's segment across faces left uncut (WP-KNIFE-01 S4, PROVISIONAL wording)."""
    notes = []
    if plan.hidden:
        notes.append(f"{plan.hidden} hidden crossing(s) not cut")
    if "gap" in plan.skipped:
        notes.append("skipped: over a hole, border or hidden part")
    if plan.method and "edge" in plan.skipped:
        notes.append("skipped: along an existing edge")
    return notes

@dataclasses.dataclass(frozen=True)
class CommandGate:
    """Data-only command gate (WP-SYM-LAB-03 H2, AD-013 H2 addendum, proposal G).

    `refused`: command → status text (block-list). `allowed`: allow-list
    (None = no allow-list); a command outside it is refused with
    `not_allowed_text`. `refused_contexts` (H2 amendment G-2, 2026-10-08):
    resolved `C` context → status text; it can only refuse `C` after a gate
    that let `Connect` through (`CContext.NONE` is no operation and may not be
    listed). Immutable: a host replaces `Application.command_gate` as a whole,
    never edits it. `Application` checks it in `key_press` (after the Knife
    routing), for click commands before `select_at`, and for the `C` context in
    `_connect_command`; it calls no host code."""

    refused: Mapping[str, str] = dataclasses.field(default_factory=dict)
    allowed: frozenset[str] | None = None
    not_allowed_text: str = ""
    refused_contexts: Mapping[CContext, str] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if CContext.NONE in self.refused_contexts:
            raise ValueError("CommandGate.refused_contexts may not list CContext.NONE (no operation)")
        object.__setattr__(self, "refused", MappingProxyType(dict(self.refused)))
        object.__setattr__(self, "refused_contexts", MappingProxyType(dict(self.refused_contexts)))
        if self.allowed is not None:
            object.__setattr__(self, "allowed", frozenset(self.allowed))

    def refusal(self, command: str) -> str | None:
        """Status text if `command` is refused, else None."""
        if command in self.refused:
            return self.refused[command]
        if self.allowed is not None and command not in self.allowed:
            return self.not_allowed_text
        return None

    def context_refusal(self, context: CContext) -> str | None:
        """Status text if the resolved `C` context is refused, else None."""
        return self.refused_contexts.get(context)


class Application:
    """Window-unabhängiger Produktions-Orchestrator."""

    def __init__(self, keymap_path: Optional[str | Path] = None) -> None:
        # Core-Strukturen
        self.scene: Scene = Scene()
        self.selection: Selection = self.scene.selection
        self.history: HistoryStack = self.scene.history

        # Viewport-State (kein Rendering in Gate 3)
        self.camera: OrbitCamera = OrbitCamera()
        self.display: DisplayState = DisplayState()
        # AD-024 §6/§8: the Look row the arrow keys edit (index into `look_controls.LOOK_ROWS`).
        self._look_row_index = 0
        # AD-024 Q-L2: the key that holds the light drag (None = not held).
        self._light_drag_key: str | None = None

        # WP-06 B8 (picking speed + occlusion, PROVISIONAL): screen-space pick
        # cache, refreshed lazily per camera/mesh state (`picking_cache.py`).
        # Orbit/zoom/pan invalidate it automatically (keyed on
        # `camera.camera_revision`); every other trigger from the handoff
        # (Move/Rotate/Scale commit, Undo/Redo, Split/Connect, Knife cut,
        # display-mode change) calls `self._pick_cache.invalidate()`
        # explicitly at its existing mutation/notification call site.
        self._pick_cache: PickCache = PickCache()
        # AD-022 B2-out (2026-10-21): hover / click / Paint and Box of vertices, edges and faces pick
        # from the viewport's ID buffers when the window has a GL store; False = always the CPU picker
        # (comparison runs, the probes; `MIRAI_CPU_PICKING=1` in the environment as the escape hatch
        # if a driver draws wrong IDs).
        self.gpu_picking: bool = os.environ.get("MIRAI_CPU_PICKING") != "1"
        # AD-021 M1: pick caches of the objects other than the edit object (mode `4` picking;
        # the edit object shares `_pick_cache`). Pruned with the render entries.
        self._object_pick_caches: dict[ObjectId, PickCache] = {}
        # 2026-10-16: what the selection highlight in mode `4` was last drawn for.
        self._object_highlight_key: tuple | None = None
        # AD-021 M2-1 (E-7): one Objektraum-Kamera per placed object, stable so that a
        # `PickCache` keyed on `id(camera)` keeps working; read live, pruned with the entries.
        self._object_cameras: dict[ObjectId, ObjectSpaceCamera] = {}
        # AD-021 M2-0 (§7.3 RD-2): all References drawn as Ghost (`Alt+D`); display state,
        # not an Undo step, kept across scene loads like `DisplayState`.
        self.reference_ghost: bool = False

        # Gate 7: V0.2 Viewport wird in init_scene() mit dem Mesh gebunden.
        # Bliebt None, bis init_scene() aufgerufen wurde (kein Mesh verfügbar).
        self.viewport: Viewport | None = None

        # Tools
        self.tool_manager: ToolManager = ToolManager()
        self._setup_tools()

        # Input
        # Gate 6 (Input Config): Default → optionales keymap.json → BindingSet.
        # Das Overlay wird genau einmal beim Application-Start geladen; eine
        # vorhandene, ungültige Datei wird kontrolliert abgelehnt
        # (`KeymapConfigError`). Kein Runtime-Hot-Reload.
        self.bindings: BindingSet = build_default_bindings()
        # 2026-10-23: the SubD preview's provisional keys, context "subd" (checked against the
        # defaults here, before a keymap.json may rebind anything).
        install_subd_bindings(self.bindings)
        if keymap_path is not None:
            load_keymap_overrides(self.bindings, keymap_path)

        # WP-06 B2 (AD-019): Pointer-Gesten laufen über dieselben Bindings.
        # Größe in logischen Fenster-Pixeln (gleiche Einheit wie die
        # Maus-Koordinaten); der Entry-Point setzt sie über set_viewport_size().
        self.pointer: PointerGestures = PointerGestures(self.bindings)
        self.viewport_width: int = 1
        self.viewport_height: int = 1
        # WP-06 B2b (E20): letzte bekannte Cursor-Position (None = unbekannt
        # bzw. Cursor außerhalb des Fensters) - für das Hover-Re-Pick nach Zoom.
        self._cursor: tuple[float, float] | None = None
        # WP-VIEW-PERF-01 Slice 2 (option 5, coalescing): with `coalesce_hover` a plain mouse
        # move or a zoom notch only marks the hover stale; the frame tick (`update_viewport`)
        # picks once at the latest cursor, and every input that may read the hover first
        # (`key_press`, `pointer_press`, `dispatch_command`) picks it before (`flush_hover`).
        # The window loop (`src/main.py run`) switches it on; off (default) every move picks
        # at once, as before - the headless tests and hosts without a tick rely on that.
        self.coalesce_hover: bool = False
        self._hover_stale: bool = False

        # WP-06 B3 (E26, `PROVISIONAL` bis ein HUD existiert): letzte
        # Statusmeldung für den Nutzer. `status_serial` zählt jede Meldung,
        # damit der Entry-Point auch eine wiederholte, gleichlautende Meldung
        # (z. B. zweimal "Undo") erkennt.
        self.status_message: str = ""
        self.status_serial: int = 0

        # WP-SYM-LAB-03 H2 (AD-013 H2 addendum): optional `CommandGate` of one
        # host (the Symmetry Lab, H2-R6). None = nothing is refused;
        # `src/main.py` never sets it.
        self.command_gate: CommandGate | None = None
        # H2 (same addendum): pauses the selection hover while a host's modal
        # interaction is open. Backing field, because `viewport` is None until
        # `init_scene()`; see `hover_suspended`. (Its only writer, the Lab's
        # Re-Symmetrize preview, became `_resym_plan` in AD-SYM-04 A3.)
        self._hover_suspended: bool = False
        # AD-SYM-04 A3 (§10 R-a): the open Re-Symmetrize preview - the plan computed once when it
        # opened, executed exactly as shown. None = closed. An `Application` interaction like the
        # Knife session (`interaction_owner` "resymmetrize").
        self._resym_plan: ResymPlan | None = None

        # WP-06 B3 (E21, AD-016 D4 hold-key-hover), generalisiert in B4 (E28)
        # auf Move/Rotate/Scale: `_transform_key` ist die Taste, die scharf
        # geschaltet hat (None = nicht scharf); das Release wird über ihren
        # Wert erkannt, nicht über die Bindings, weil sich die Modifier
        # zwischen Press und Release ändern dürfen (z. B. Alt für Orbit,
        # während W gehalten wird). Das Ziel ist ab dem Press fix; `begin()`
        # läuft erst bei der ersten Mausbewegung. `_transform_space` ist der
        # `space`, mit dem die laufende Geste begonnen hat (None = frei).
        self._transform_key: str | None = None
        self._transform_command: str | None = None
        self._transform_target: frozenset[VertexId] = frozenset()
        self._transform_begun: bool = False
        self._transform_space: str | None = None
        # WP-06 B9 (Extrude, hold T): the faces fixed at the arm, the pointer's net
        # displacement since the arm (until `begin()`, see EXTRUDE_BEGIN_PX) and the
        # selection snapshot taken BEFORE `begin()` - the tool remaps the selection to
        # the caps during `begin()`, so the Undo mirror entry needs the earlier one.
        self._extrude_faces: frozenset[FaceId] = frozenset()
        self._extrude_travel: tuple[float, float] = (0.0, 0.0)
        self._extrude_selection_before: tuple | None = None
        # AD-021 M2-2 (E-11): the object gesture of mode `4` (None = none). It shares
        # `_transform_key`/`_transform_command`/`_transform_begun`/`_transform_space` with the
        # component gestures, so `interaction_owner` reports "transform" and every key gate
        # (mode keys, C, Undo while running, add object) holds for it unchanged.
        self._object_gesture: _ObjectGesture | None = None
        # WP-06 B4.1 (Artist-Entscheidung Manu 2026-09-27, Playground-Verhalten
        # WP-AP-INPUT-FIX-03 1:1): sticky Achsen-Constraint, unabhängig vom
        # scharfen Tool, überlebt Commit/Cancel/neues Scharfschalten und wird
        # bei jedem `begin()` gelesen. None = frei.
        self._axis_constraint: str | None = None
        # WP Toolbox Gaps C1 (`PROVISIONAL`): what the constraints mean - world axes or the
        # selection's normal frame (`mirai.transform_space`). Sticky like the constraint, read at
        # `begin()` and by the gizmo; not in History or scene files.
        self._orientation: str = transform_space.WORLD
        # WP-SOFT-01 S2a (AD-020, `PROVISIONAL`, off by default): sticky Soft Selection
        # settings with the semantics of the axis constraint above - they survive commit,
        # cancel, re-arm and Undo and are read once per gesture at `begin()`. A gesture
        # that is armed but has not begun takes a new value; a running one keeps its own -
        # except the radius and the Loop / Ring balance, which a running Soft gesture takes live
        # (AD-020 "Live radius", "Loop / Ring flow").
        # The radius is held in world units (computed on switch-on, on a step change and
        # on scene load) so that the tool and the later preview read one value.
        self._soft: SoftSettings = SoftSettings()
        # Mask Geometry (`mirai.mask`): protection state, not mesh data - no History, cleared on scene load.
        self._masks: dict[ObjectId, VertexMask] = {}
        self._mask_overlay = None
        # Hide / Isolate (`mirai.hidden`): the same kind of state, per edit object.
        self._hiddens: dict[ObjectId, HiddenSet] = {}
        # Polygroups (AD-REGIONS-01): the groups themselves live in the Mesh; this is the name of the active one.
        self._active_regions: dict[ObjectId, str] = {}
        self._tints_seen: tuple | None = None  # (mesh, face_regions, viewport) the viewport last got colours for
        # The settings the running Soft gesture uses (None = no begun Soft gesture): those read at
        # `begin()`, with only the radius / flow balance replaced by live steps. `_soft_gesture_reference` is
        # the bounding radius its percent steps refer to, fixed for the gesture (the one its start
        # radius was computed from), so the deforming mesh never redefines a step.
        self._soft_gesture: SoftSettings | None = None
        self._soft_gesture_reference: float = 0.0
        # WP-SOFT-01 S2b (AD-020 §5, `PROVISIONAL`): the influence bands shown in the window.
        # `_soft_overlay` is the host-supplied sink (None = headless: no overlay work at all),
        # `_soft_bands` what it currently shows. `_soft_op_running`: the bands are the running
        # op's weights (fixed at `begin()`), so no trigger recomputes them;
        # `_soft_gesture_shown`: a gesture put the bands there (hover arm or op), so its end
        # resumes the preview.
        self._soft_overlay = None
        self._soft_bands: SoftBands = EMPTY_BANDS
        # 2026-10-22: the second display mode (face shading) - its sink and the weights it shows
        # ({} = nothing). View state only: never in the scene file or the history. Exactly one of
        # `_soft_bands` / `_soft_shading` is non-empty at a time.
        self._soft_shading_overlay = None
        self._soft_shading: dict[VertexId, float] = {}
        self._soft_op_running: bool = False
        self._soft_gesture_shown: bool = False
        # AD-SYM-04 A2 (Q-2 = S-2): plane outline and problem markers; None = headless (no
        # `symmetry_overlay_type`, no display work at all).
        self._symmetry_display: SymmetryDisplay | None = None
        # AD-SYM-04 SS3 (`PROVISIONAL`): one symmetry report per geometry, shared by the display
        # and the soft preview, so the preview takes its correspondence from it instead of
        # pairing the mesh per trigger. Keyed by `geometry_signature` (definition, ids,
        # positions, seam), so Undo/Redo, topology, Shift+S and a scene load make it stale by
        # construction; `mirai.symmetry` stays cache-free (AR-1/INV-3) and the tools still pair
        # once per gesture start for the op itself. Fresh per scene (`init_scene`).
        self._symmetry_reports = ReportCache(defer=self._symmetry_display_deferred)

        # WP-06 B6 Follow-up (Artist-Entscheidung Manu 2026-09-28): Undo/Redo
        # stellt jetzt auch die Selection wieder her, nicht nur das Mesh.
        # `HistoryStack` (core, frozen) kennt kein Selection-Konzept und
        # bietet keinen Hook vor/nach push() - deshalb führt Application
        # einen eigenen Stack von (before, after)-Selection-Snapshots parallel
        # zu jedem `history.push()`, den sie selbst auslöst (Split/Edge
        # Connect/Vertex Connect in `_connect_command`, Transform-Commit in
        # `key_release`, Knife-Commit, seit WP-SYM-LAB-03 H3 auch
        # `apply_mesh_change` für Änderungen eines Hosts). `before` =
        # Snapshot unmittelbar vor der Mutation, `after` = Snapshot danach
        # (die von `_connect_command` gesetzte Residue-Auswahl bzw. bei
        # Transformen dieselbe Auswahl, da Move/Rotate/Scale die Selection
        # nicht ändern). Struktur und Semantik spiegeln `HistoryStack`
        # bewusst 1:1 (ein `_record_selection_history()` pro Push, Redo-Stack
        # wird dabei geleert). Ist der Mirror-Stack leer, obwohl History
        # Undo/Redo erlaubt (z. B. künftiger Push-Pfad, der hier noch nicht
        # verdrahtet ist), fällt `_apply_undo_redo()` auf reines Pruning
        # zurück statt zu crashen.
        # AD-021 M1 (§4.6, E-5): an entry is (before, after, mesh_step); `mesh_step` False marks
        # an object step (add object, state change), whose Undo/Redo refreshes the object
        # entries only, not the edit object's render mesh.
        # AD-021 M2-3: a fourth element names the *other* objects whose mesh the step changed
        # (Apply transform on a non-edit object), so their render entries rebuild on Undo/Redo.
        self._selection_undo_stack: list[tuple[tuple, tuple, bool, frozenset]] = []
        self._selection_redo_stack: list[tuple[tuple, tuple, bool, frozenset]] = []
        # AD-021 M2-4: how long the last Q-5 switch of the edit object took (s, `time.perf_counter`;
        # measured, not optimised - the viewport rebuilds the entries of both objects).
        self.last_edit_switch_seconds: float = 0.0
        # Whether the last Undo/Redo touched the edit object's mesh (`_apply_undo_redo`).
        self._last_undo_redo_mesh_step: bool = True

        # SubD preview of the edit mesh (2026-10-23, `mirai.subdivision`): view state only - no
        # document state, no History. Survives scene loads like `DisplayState`; re-attached to every
        # new viewport in `init_scene`.
        self.subdivision: SubdivisionPreview = SubdivisionPreview(set_status=self._set_status)

        # WP-06 B7.1 (AD-017 Knife; click-only = Artist decision Manu 2026-09-28,
        # after the B7 window test: press-slide-release was redundant with the
        # live hover preview): laufende Knife-Session (None = keine). `KnifeTool`
        # hält Mesh-Schritte, Start und Pfad; hier liegt nur der Interaktions-
        # zustand: das gültige prospektive Ziel (None = keins oder ungültig),
        # die hervorgehobene Edge (gehovert) und ob die LMB-Geste des Knife
        # gerade gehalten wird (nur zur Klick-Schwellen-Erkennung).
        # `_knife_selection_before` ist der Snapshot vor der Session für den
        # Selection-Mirror-Stack beim Commit.
        self._knife: KnifeTool | None = None
        self._knife_selection_before: tuple | None = None
        self._knife_target: dict | None = None
        self._knife_highlight_edge: EdgeId | None = None
        self._knife_gesture: bool = False
        self._knife_gesture_moved: float = 0.0
        # WP-KNIFE-01 UX2: the gesture's button (LMB = a point, RMB = pen lift),
        # Shift at the press (midpoint snap; the gesture is fixed at the press,
        # AD-019), and the last LMB click (time, x, y) for the double-click on
        # `knife_clock` (injectable for headless tests).
        self._knife_gesture_button: str = "LEFT"
        self._knife_gesture_midpoint: bool = False
        self._knife_last_click: tuple[float, float, float] | None = None
        self.knife_clock = time.monotonic
        # WP-KNIFE-01 UX2b: any Shift key held, as the window reports it
        # (`set_shift_held`). Only the Knife's hover reads it (the midpoint before
        # the click); a click keeps deciding by its press modifiers (A2, AD-019).
        self._shift_held: bool = False
        # Transform modifiers (2026-10-22, Blender): Shift = precision, Ctrl = snap while a transform runs.
        # A Tweak starts with Ctrl down, so its snap waits until Ctrl was let go once (`_ctrl_snap_ok`).
        self._ctrl_held: bool = False
        self._ctrl_snap_ok: bool = True
        # Alt held during a transform (2026-10-22, `PROVISIONAL`, Manu "Alt halten um zu orbiten"): the motion
        # navigates (Orbit, Alt+Shift Pan) instead of driving the gesture; letting Alt go resumes it.
        self._alt_held: bool = False
        # Where the cursor was when the running transform armed (the dial's press point) and the cursor as the
        # deltas draw it since (`press + sum(dx, dy)`): the dial reads this, not `_cursor`, so the window may warp
        # the pointer across the viewport edge (cursor wrap, 2026-10-22) without a jump in the gesture.
        self._rotate_press: tuple[float, float] | None = None
        self._rotate_virtual: tuple[float, float] | None = None
        # WP-KNIFE-01 S4: where the hovered segment crosses edges (the planner's dots).
        self._knife_hover_crossings: tuple = ()
        # AD-SYM-03 slice 6c: the running session's symmetry view (None = no definition at begin: the Knife
        # as it always was), the hovered target a click is refused for (and the text shown for it), and the
        # provisional mirror preview variant (kept across sessions of this Application).
        self._knife_view: SymmetricKnifeView | None = None
        self._knife_refused: dict | None = None
        self._knife_refused_text: str | None = None
        self.knife_mirror_variant: str = KNIFE_MIRROR_VARIANT_DEFAULT

        # 2026-10-15 (Playground tools promoted, Manu): the press point of the current LMB
        # gesture (Box/Paint/Tweak decide by it), the running drag selection, the transform a
        # Tweak uses (the last W/E/R pressed; Move until then) and whether the current LMB drag
        # gesture (Box/Paint or Tweak) was refused (its further drag steps do nothing until the
        # release).
        self._press_point: tuple[float, float] | None = None
        self._drag_select: _DragSelect | None = None
        # The key that holds the Lasso mode (None = not held); see `commands.LASSO_ARM`.
        self._lasso_held: str | None = None
        # Transform gizmo (2026-10-21, AD-016 D3; promoted from the Playground, Manu). Off unless the host
        # draws it (`src/main.py` sets `gizmo_enabled`): Labs on `Application` get no invisible handles.
        # `_gizmo_gesture` = the handle pressed by the running LMB gesture; `_gizmo_cache` = (key, pivot).
        self.gizmo_enabled: bool = False
        self._gizmo_gesture: str | None = None
        self._gizmo_press_xy: tuple[float, float] | None = None  # cursor at the handle press (Rotate dial)
        self._gizmo_cache: tuple | None = None
        self._gizmo_frame_cache: tuple | None = None  # (pivot cache key, NormalFrame | None), Normal space
        self.tweak_command: str = commands.MOVE
        self._gesture_refused: bool = False
        # Loop Slide (hold G): the plan fixed at the arm, the slide amount, the screen
        # direction of side A (px per unit t; None = fall back to horizontal), and the mesh
        # state at the first motion (Esc and the History entry use it).
        self._slide_plan: SlidePlan | None = None
        self._slide_t: float = 0.0
        self._slide_direction: tuple[float, float] | None = None
        self._slide_before: MeshChange | None = None
        self._slide_selection_before: tuple | None = None
        # WP Toolbox Gaps C2: the held Smooth / Relax (plan at the press, amount in steps, journal).
        self._smooth_plan: SmoothPlan | None = None
        self._smooth_amount: float = 0.0
        self._smooth_before: MeshChange | None = None
        self._smooth_selection_before: tuple | None = None
        self._smooth_seeds: frozenset[VertexId] = frozenset()  # the selection (Soft seeds) at the press

    def _setup_tools(self) -> None:
        """Registriert die Default-Tools (Move/Rotate/Scale/Extrude) im ToolManager."""
        for command, tool_class in (
            (commands.MOVE, tool_for_command(commands.MOVE)),
            (commands.ROTATE, tool_for_command(commands.ROTATE)),
            (commands.SCALE, tool_for_command(commands.SCALE)),
            (commands.EXTRUDE, tool_for_command(commands.EXTRUDE)),
        ):
            if tool_class:
                self.tool_manager.register(command, tool_class)

    def init_scene(
        self,
        geometry_type: str = "cube",
        store_type: type[ResourceStore] = TraceStore,
        obj_path: str | Path | None = None,
        point_overlay_type: type | None = None,
        line_overlay_type: type | None = None,
        face_overlay_type: type | None = None,
        soft_overlay_type: type | None = None,
        soft_shading_overlay_type: type | None = None,
        symmetry_overlay_type: type | None = None,
        scene_path: str | Path | None = None,
        subd_overlay_type: type | None = None,
        mask_overlay_type: type | None = None,
    ) -> None:
        """Initialisiert die Default-Szene (Würfel, OBJ-Import oder Szenendatei).

        `store_type` (Stage A, AD-018 §5/§6): additiv durchgereicht an
        `Viewport(...)`. Default bleibt `TraceStore` (headless, kein GL-
        Kontext nötig) — bestehende Aufrufstellen/Tests bleiben unverändert.
        Ein Entry-Point mit echtem Fenster übergibt hier `GLRenderStore`
        (`src/viewport/gl_render_store.py`), um durch den echten Draw-Pfad
        zu rendern.

        `geometry_type="obj"` (WP-06 Slice B1): lädt `obj_path` über
        `scene_factory.build_core_scene_from_obj` (lazy `examples/`-Import
        dort, siehe dessen Moduldocstring) und übernimmt nur dessen `.mesh`
        — `self.scene` selbst bleibt dieselbe Instanz (Scene-Identität,
        siehe Klassen-/Moduldocstring), damit `Selection`/`HistoryStack`
        an derselben Scene hängen bleiben wie vor `init_scene()`.
        `obj_path` ist bei `geometry_type="obj"` erforderlich.

        AD-021 M1 (§5.2, review R-4): das Laden ist ein Scene-Reset - alle Objekte werden durch
        genau ein neues, bearbeitbares Objekt ersetzt (Name: `cube` bzw. der Dateistamm), das
        Edit-Objekt wird (`scene_objects.reset_scene`); der `scene.mesh`-Setter bedeutet nur
        noch "Mesh dieses Objekts tauschen".

        `geometry_type="file"` (Szenen speichern/laden, Manu 2026-10-15): lädt die Szenendatei
        `scene_path` (`core.serialization`, alle Objekte samt Edit-Objekt) über
        `scene_objects.replace_scene`. Gelesen und geparst wird vor jeder Änderung, ein
        Fehler lässt die Szene also unverändert.

        `point_overlay_type` (WP-06 B2b, E17): gleiches Durchreich-Muster wie
        `store_type`. Default `None` = kein GL-Punkt-Overlay (headless); der
        Entry-Point übergibt `GLPointOverlay`.

        `line_overlay_type` (WP-06 B5a, E38): dasselbe Muster für das
        Edge-Linien-Overlay; der Entry-Point übergibt `GLLineOverlay`. Der
        aktuelle `DisplayState` wird sofort an den neuen Viewport gegeben.

        `face_overlay_type` (WP-06 B5b, E45): dasselbe Muster für selektierte
        bzw. gehoverte Faces; der Entry-Point übergibt `GLTriangleOverlay`.

        `soft_overlay_type` (WP-SOFT-01 S2b, AD-020 §5): dasselbe Muster für die Influence-
        Bänder der Soft Selection; der Entry-Point übergibt `GLSoftBandOverlay`. Es hängt als
        Zusatz-Overlay (`Viewport.add_overlay`, H1) am Viewport, den es nicht kennt. Default
        `None` = keine Band-Arbeit (headless).

        `soft_shading_overlay_type` (2026-10-22): die GL-Senke für den zweiten Anzeige-Modus der
        Soft Selection (Face-Shading, `GLSoftShadingOverlay`); sie hängt wie die Bänder als
        Zusatz-Overlay am Viewport. Es ist immer nur einer der beiden Modi sichtbar. Default `None`.

        `symmetry_overlay_type` (AD-SYM-04 A2, Q-2 = S-2): die GL-Senke für Ebenen-Umriss und
        Problem-Marker; der Entry-Point übergibt `GLSymmetryOverlay`. `Application` hängt sie
        in ihr eigenes `SymmetryDisplay` (`mirai.symmetry_display`), das als Zusatz-Overlay nach
        den Bändern am Viewport hängt und während eines Transforms aufschiebt. Default `None` =
        keine Symmetrie-Anzeige (headless).

        `subd_overlay_type` (2026-10-23): die GL-Senke der SubD-Linien (Käfig / Isolinien,
        `mirai.subdivision.gl_lines.GLSubdLineOverlay`). Die SubD-Vorschau (`self.subdivision`) hängt
        sich an jeden neuen Viewport; ohne Senke rechnet sie headless dieselben Segmente."""
        if geometry_type in ("cube", "obj"):
            reset_scene(self.scene, *self._build_mesh(geometry_type, obj_path))
        elif geometry_type == "file":
            if scene_path is None:
                raise ValueError('geometry_type="file" requires scene_path')
            loaded = scene_from_json(Path(scene_path).read_text(encoding="utf-8"))
            replace_scene(self.scene, loaded)
        self._soft_refresh_radius()  # a scene load is one of the three radius events

        # Gate 7: Produktionsintegration — verbindet Application.camera mit
        # dem V0.2-Viewport. Die dieselbe OrbitCamera-Instanz wird über
        # Duck-Typing an RenderMesh.bind_camera() übergeben (siehe
        # VIEWPORT_V02_ARCHITECTURE.md §9). Es entsteht KEINE zweite
        # Kamera-Repräsentation.
        self.viewport = Viewport(
            self.scene.mesh,
            selection=self.scene.selection,
            store_type=store_type,
            point_overlay_type=point_overlay_type,
            line_overlay_type=line_overlay_type,
            face_overlay_type=face_overlay_type,
        )
        self.viewport.bind_camera(self.camera)
        self._soft_overlay = None
        self._soft_bands = EMPTY_BANDS
        self._soft_shading_overlay = None
        self._soft_shading = {}
        self._symmetry_reports = ReportCache(defer=self._symmetry_display_deferred)
        if soft_overlay_type is not None:
            self._soft_overlay = soft_overlay_type()
            self.viewport.add_overlay(self._soft_overlay)
        if soft_shading_overlay_type is not None:
            self._soft_shading_overlay = soft_shading_overlay_type()
            self.viewport.add_overlay(self._soft_shading_overlay)
        self._masks.clear()  # their IDs belong to the old meshes
        self._hiddens.clear()
        self._active_regions.clear()
        self._pick_cache.set_hidden(())
        self._mask_overlay = None
        if mask_overlay_type is not None:
            self._mask_overlay = mask_overlay_type()
            self.viewport.add_overlay(self._mask_overlay)
        self._soft_apply_look()
        if self._soft_overlay is not None or self._soft_shading_overlay is not None:
            self._soft_preview_refresh()  # a scene load is one of the preview triggers (E3)
        self._symmetry_display = None
        self._resym_plan = None
        if symmetry_overlay_type is not None:
            self._symmetry_display = SymmetryDisplay(
                symmetry_overlay_type(),
                reports=self._symmetry_reports,
                preview=lambda: self._resym_plan,
            )
            self.viewport.add_overlay(self._symmetry_display)
        self.subdivision.attach(
            self.viewport, subd_overlay_type() if subd_overlay_type is not None else None
        )
        self._object_pick_caches = {}
        self._sync_object_views()
        self._apply_display()

    @staticmethod
    def _build_mesh(geometry_type: str, obj_path: str | Path | None) -> tuple[Mesh, str]:
        """Das Mesh einer Szene bzw. eines hinzugefügten Objekts und sein Objektname."""
        from .scene_factory import PRIMITIVES

        if geometry_type in PRIMITIVES:
            return PRIMITIVES[geometry_type](), geometry_type
        if geometry_type == "obj":
            if obj_path is None:
                raise ValueError('geometry_type="obj" requires obj_path')

            from .scene_factory import build_core_scene_from_obj

            return build_core_scene_from_obj(obj_path).mesh, Path(obj_path).stem
        raise ValueError(f"unknown geometry_type {geometry_type!r}")

    # -- Objekte (AD-021 M1) ----------------------------------------------------

    def add_reference(
        self,
        geometry_type: str = "cube",
        obj_path: str | Path | None = None,
        name: str | None = None,
    ) -> SceneObject | None:
        """Fügt ein Objekt als Referenz hinzu, statt die Szene zu ersetzen (AD-021 M1, A-1;
        Q-10: Shift+Klick im `SPACE`-Menü).

        Ein Undo-Schritt (Q-3); die Kamera bleibt stehen (Q-9); Edit-Objekt, Auswahl und das
        Mesh des Edit-Objekts bleiben unberührt. Abgelehnt (Statuszeile, None), solange eine
        Interaktion die Tasten hält. Ein Ladefehler fliegt wie bei `init_scene` (der Aufrufer
        meldet ihn). Gibt das neue Objekt zurück."""
        if self.viewport is None:
            raise RuntimeError("add_reference() before init_scene()")
        owner = self.interaction_owner
        if owner is not None:
            self._set_status(f"Add object: not while the {owner} interaction runs")
            return None
        mesh, default_name = self._build_mesh(geometry_type, obj_path)
        before = self._selection_snapshot()
        obj = self.scene.add_object(
            mesh, name=name or default_name, state=ObjectState.REFERENCE
        )
        self.history.push(AddObjectCommand(self.scene, obj))
        self._record_selection_history(before, mesh_step=False)
        self._sync_object_views()
        self._set_status(f"Added {obj.name!r} as Reference")
        return obj

    def add_primitive(self, kind: str, name: str | None = None) -> SceneObject | None:
        """Add Mesh (Track A1, 2026-10-23, `PROVISIONAL`; `scene_factory.PRIMITIVES`: plane, cube,
        sphere, cylinder): ein neues, **bearbeitbares** Objekt am Ursprung - keine Referenz.

        Wechselwirkung mit Modus und Edit-Objekt: die Application geht in Modus `4`, das neue
        Objekt ist die einzige Objekt-Auswahl (sichtbar hervorgehoben, W/E/R bewegen es sofort) und
        die Komponenten-Auswahl wird geleert; das **Edit-Objekt bleibt** - `1`/`2`/`3` machen das
        neue Objekt über die Q-5-Geste (ein ausgewähltes Normal-Objekt) zum Edit-Objekt. Ein
        Undo-Schritt (`AddObjectCommand` + ein Spiegel-Eintrag): Undo entfernt das Objekt und stellt
        Modus, Auswahl und Edit-Objekt davor wieder her, Redo setzt dieselbe Instanz (gleiche
        ObjectId) wieder ein. Abgelehnt (Statuszeile, None), solange eine Interaktion die Tasten
        hält; ein unbekannter `kind` fliegt als ValueError. Gibt das neue Objekt zurück."""
        if self.viewport is None:
            raise RuntimeError("add_primitive() before init_scene()")
        from .scene_factory import PRIMITIVES

        if kind not in PRIMITIVES:
            raise ValueError(f"unknown primitive {kind!r}")
        return self._add_mesh_object(
            lambda: PRIMITIVES[kind](), name or unique_object_name(self.scene, kind), f"Add {kind}"
        )

    def import_obj(self, path: str | Path) -> SceneObject | None:
        """OBJ import (SPACE menu, `src/obj_files.py`): the file becomes a new editable object like an
        Add-Mesh primitive (same Undo step, selection and status behaviour), named after the file.
        Parse errors fly as exceptions (`ObjLoadError`, OSError) before the scene is touched."""
        from .scene_factory import mesh_from_positions_and_faces

        if self.viewport is None:
            raise RuntimeError("import_obj() before init_scene()")
        path = Path(path)

        def build() -> Mesh:
            from loaders.obj_loader import load_obj  # lazy - `examples/` on sys.path, see scene_factory

            data = load_obj(path)
            return mesh_from_positions_and_faces(data.vertices, data.faces)

        return self._add_mesh_object(build, unique_object_name(self.scene, path.stem), "Import OBJ")

    def export_obj(self, path: str | Path) -> bool:
        """OBJ export (SPACE menu): the edit object in world space (object transform applied), one
        `o` record. True = written. Refused during an interaction like `save_scene_file`."""
        from .obj_export import mesh_to_obj

        owner = self.interaction_owner
        if owner is not None:
            self._set_status(f"Export OBJ: not while the {owner} interaction runs")
            return False
        obj = self.scene.edit_object
        path = Path(path)
        text = mesh_to_obj(obj.mesh, obj.name, lambda p: object_space.to_world(obj, p))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        self._set_status(f"Exported OBJ: {path}")
        return True

    def _add_mesh_object(self, build: Callable[[], Mesh], name: str, label: str) -> SceneObject | None:
        owner = self.interaction_owner
        if owner is not None:
            self._set_status(f"{label}: not while the {owner} interaction runs")
            return None
        mesh = build()
        scene, selection = self.scene, self.selection
        before = self._selection_snapshot()
        obj = scene.add_object(mesh, name=name)
        self.history.push(AddObjectCommand(scene, obj))
        selection.mode = SelectionMode.OBJECT
        selection.clear()
        selection.objects = {obj.id}
        selection.hovered = None
        self._record_selection_history(before, mesh_step=False)
        self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        self._sync_object_views()
        self._refresh_hover()
        self._set_status(
            f"Added {obj.name!r} - selected (Object mode); W/E/R place it, 1/2/3 edit it"
        )
        return obj

    def _delete_objects_command(self) -> bool:
        """`Delete` in mode `4` (Track A2): remove the selected objects - **not** points/edges/
        faces (`_removal_command` is the component Delete and is unchanged). One Undo step
        (`DeleteObjectsCommand` + one mirror entry) however many objects; the same instances come
        back on Undo with their ids, and Undo restores the selection and the edit object of
        before. Deleting the edit object hands the edit role to a surviving Normal object
        (`plan_object_delete`); the last object, or leaving only References, is refused with a
        status line - the scene has no empty state."""
        label = "Delete object"
        owner = self.interaction_owner
        if owner is not None:
            self._set_status(f"{label}: not while the {owner} interaction runs")
            return False
        scene, selection = self.scene, self.selection
        selected = [oid for oid in sorted(selection.objects) if oid in scene.objects]
        if not selected:
            self._set_status(f"{label}: no object selected - click one first")
            return False
        try:
            doomed, edit_after = plan_object_delete(scene, selected)
        except DeleteRefused as exc:
            self._set_status(f"{label}: {exc}")
            return False
        before = self._selection_snapshot()
        edit_before = scene.edit_object_id
        edit_changed = edit_after != edit_before
        # Mirror pairs (proposal §5.5): a pair with a deleted object is broken in the same Undo
        # step - first, so the scene never holds a pair to a missing object; Undo restores both.
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
        self.history.push(delete)
        selection.objects -= {obj.id for obj in doomed}
        if edit_changed:
            selection.clear()  # component ids belong to the deleted edit object's mesh
        selection.hovered = None
        self._record_selection_history(before, mesh_step=edit_changed)
        if edit_changed:
            self._follow_edit_object()
        else:
            self._sync_object_views()
        self._soft_preview_refresh()
        self._refresh_hover()
        names = ", ".join(repr(obj.name) for obj in doomed)
        text = f"Deleted {names}"
        for note in pair_notes:
            text += f" - {note}"
        if edit_changed:
            text += f" - now editing {scene.edit_object.name!r}"
        self._set_status(text)
        return True

    # -- Mirror pairs (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5, 2026-10-23, `PROVISIONAL`) ----------
    #
    # Window-level commands (the Shift+M menu, `src/scene_menu.py`), mode `4` only. Each is one Undo
    # step built from the existing commands; pair state changes only through `MirrorPairCommand`.
    # Planes: X = 0 / Y = 0 / Z = 0 (`object_mirror.PLANES`, proposal §9 decision 7 default).

    def _mirror_selection(self, label: str) -> list[SceneObject] | None:
        owner = self.interaction_owner
        if owner is not None:
            self._set_status(f"{label}: not while the {owner} interaction runs")
            return None
        if self.selection.mode is not SelectionMode.OBJECT:
            self._set_status(f"{label}: works on objects - press 4 and select them")
            return None
        scene = self.scene
        selected = [scene.objects[oid] for oid in sorted(self.selection.objects) if oid in scene.objects]
        if not selected:
            self._set_status(f"{label}: no object selected - click one first")
            return None
        return selected

    def _selected_pairs(self, selected: list[SceneObject]) -> list[MirrorPair]:
        pairs: list[MirrorPair] = []
        for obj in selected:
            pair = self.scene.mirror_pair_of(obj.id)
            if pair is not None and pair not in pairs:
                pairs.append(pair)
        return pairs

    def mirror_copy(self, axis: str = "X") -> SceneObject | None:
        """Mirror copy (proposal §5.5): a new Normal object B with the selected object's mesh
        reflected across the world plane (`object_mirror.mirror_mesh`: positions `H p`, winding
        reversed, no symmetry definition) at `F(A)`, paired with A. One Undo step
        (`AddObjectCommand` + `MirrorPairCommand`); B becomes the object selection (`PROVISIONAL`),
        named by `unique_object_name`. Refused (status line, None) without exactly one selected
        object, for a Reference or an object already in a pair."""
        label = "Mirror copy"
        normal, offset = MIRROR_PLANES[axis]
        selected = self._mirror_selection(label)
        if selected is None:
            return None
        if len(selected) != 1:
            self._set_status(f"{label}: select one object ({len(selected)} are selected)")
            return None
        scene, selection = self.scene, self.selection
        source = selected[0]
        try:
            check_pairable(scene, [source])
        except MirrorRefused as exc:
            self._set_status(f"{label}: {exc}")
            return None
        before = self._selection_snapshot()
        obj = scene.add_object(mirror_mesh(source.mesh, normal), name=unique_object_name(scene, source.name))
        obj.transform, obj.pivot = mirror_placement(source, normal, offset)
        obj.material = source.material  # AD-024 Q-M2: the copy keeps the source's material
        add = AddObjectCommand(scene, obj)
        pair = MirrorPair(source.id, obj.id, normal=normal, offset=offset)
        scene.add_mirror_pair(pair)
        self.history.push(
            CompositeCommand([add, MirrorPairCommand(scene, pair, create=True)], f"Mirror copy {source.name!r}")
        )
        selection.objects = {obj.id}
        selection.hovered = None
        self._record_selection_history(before, mesh_step=False)
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._sync_object_views()
        self._refresh_hover()
        self._set_status(
            f"Mirror copy: {describe_pair(scene, pair)} - paired: moving either moves both mirrored;"
            " the meshes stay independent"
        )
        return obj

    def pair_selected(self, axis: str = "X") -> bool:
        """Pair two selected objects (proposal §5.5): the lower ObjectId drives and stays, the other
        is placed at `F(driver)` (transform, scale and pivot - announced), then the pair. One Undo
        step. The meshes are not inspected. Refused unless exactly two objects are selected, for a
        Reference or an object already in a pair."""
        label = "Mirror pair"
        normal, offset = MIRROR_PLANES[axis]
        selected = self._mirror_selection(label)
        if selected is None:
            return False
        if len(selected) != 2:
            self._set_status(
                f"{label}: select exactly two objects ({len(selected)} are selected) - the first created"
                " stays, the other is placed at its mirror"
            )
            return False
        driver, follower = selected
        before = self._selection_snapshot()
        try:
            command = pair_existing_command(self.scene, driver, follower, normal, offset)
        except MirrorRefused as exc:
            self._set_status(f"{label}: {exc}")
            return False
        self.history.push(command)
        self._record_selection_history(before, mesh_step=False)
        self._placement_changed()
        pair = self.scene.mirror_pair_of(driver.id)
        self._set_status(
            f"{label}: {follower.name!r} is placed at the mirror of {driver.name!r}"
            f" - paired {describe_pair(self.scene, pair)}"
        )
        return True

    def break_mirror_pairs(self) -> bool:
        """Break the pairs of the selected objects (proposal §5.5): both objects stay exactly where
        they are; one Undo step however many pairs."""
        label = "Break pair"
        selected = self._mirror_selection(label)
        if selected is None:
            return False
        pairs = self._selected_pairs(selected)
        if not pairs:
            self._set_status(f"{label}: no selected object is in a mirror pair")
            return False
        scene = self.scene
        names = ", ".join(pair_names(scene, pair) for pair in pairs)
        before = self._selection_snapshot()
        parts = []
        for pair in pairs:
            scene.remove_mirror_pair(pair)
            parts.append(MirrorPairCommand(scene, pair, create=False))
        self.history.push(parts[0] if len(parts) == 1 else CompositeCommand(parts, "Break mirror pairs"))
        self._record_selection_history(before, mesh_step=False)
        self._set_status(f"Mirror pair {names} broken - both stay where they are")
        return True

    def resync_mirror_pairs(self) -> bool:
        """Re-sync the pairs of the selected objects (proposal §5.7): B is placed at `F(A)` again
        (`pair.a` = the driver at creation). One Undo step; nothing for a pair in sync; refused,
        before anything changes, when a B to move is a Reference."""
        label = "Re-sync"
        selected = self._mirror_selection(label)
        if selected is None:
            return False
        pairs = self._selected_pairs(selected)
        if not pairs:
            self._set_status(f"{label}: no selected object is in a mirror pair")
            return False
        scene = self.scene
        todo = [p for p in pairs if not in_sync(scene.objects[p.a], scene.objects[p.b], p)]
        if not todo:
            names = ", ".join(pair_names(scene, pair) for pair in pairs)
            self._set_status(f"{label}: mirror pair {names} is in sync - nothing to do")
            return False
        for pair in todo:
            b = scene.objects[pair.b]
            if b.state is ObjectState.REFERENCE:
                self._set_status(
                    f"{label}: {b.name!r} (mirror partner of {scene.objects[pair.a].name!r}) is a Reference - locked"
                )
                return False
        before = self._selection_snapshot()
        parts = [resync_command(scene, pair) for pair in todo]
        self.history.push(parts[0] if len(parts) == 1 else CompositeCommand(parts, "Re-sync mirror pairs"))
        self._record_selection_history(before, mesh_step=False)
        self._placement_changed()
        moved = ", ".join(repr(scene.objects[pair.b].name) for pair in todo)
        self._set_status(f"{label}: {moved} placed at the mirror of its partner again")
        return True

    def _mirror_followers(
        self, label: str, targets: list[SceneObject]
    ) -> tuple[list[SceneObject], list] | None:
        """The object gesture's drivers and followers (proposal §5.4): a pair is one unit - the
        partner of a driven object follows; with both selected the lower ObjectId drives. None
        (refusal posted) when a partner is a Reference (locked) or a pair is out of sync."""
        scene = self.scene
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
                self._set_status(
                    f"{label}: {partner.name!r} (mirror partner of {obj.name!r}) is a Reference - locked"
                )
                return None
            if not in_sync(scene.objects[pair.a], scene.objects[pair.b], pair):
                self._set_status(f"{label}: {out_of_sync_text(scene, pair)}")
                return None
            drivers.append(obj)
            followers.append((partner, partner.transform, obj, obj.transform, pair))
        return drivers, followers

    @staticmethod
    def _mirror_note(followers: list) -> str:
        if not followers:
            return ""
        names = ", ".join(f"{f.name!r} mirrors {d.name!r}" for f, _, d, _, _ in followers)
        return f" - {names}"

    def _sync_object_views(self) -> None:
        """Gleicht die Render-Einträge und Pick-Caches der Nicht-Edit-Objekte mit
        `scene.objects` ab (AD-021 §4.6 "App consequences"): ein entferntes Objekt verliert
        seinen Eintrag, ein neues bekommt einen, ein Zustandswechsel ändert nur die Farbe.
        Läuft nach jedem Objekt-Schritt, nach Undo/Redo und beim Laden. Das Edit-Objekt
        zeichnet der Viewport selbst, mit den Selection-Overlays (§4.4 "Drawing")."""
        scene = self.scene
        others = {
            oid: obj for oid, obj in scene.objects.items() if oid != scene.edit_object_id
        }
        for oid in [oid for oid in self._object_pick_caches if oid not in others]:
            del self._object_pick_caches[oid]
        for oid in [oid for oid in self._object_cameras if oid not in scene.objects]:
            del self._object_cameras[oid]
        if self.viewport is None:
            return
        # M2-1: the edit object's placement (mesh uniform + `view·model` for its overlays).
        self.viewport.set_model_matrix(object_space.model_matrix(scene.edit_object))
        for key in [key for key in self.viewport.object_entries if key not in others]:
            self.viewport.remove_object_entry(key)
        highlighted = self._highlighted_objects()
        for oid, obj in others.items():
            reference = obj.state is ObjectState.REFERENCE
            self.viewport.set_object_entry(
                oid,
                obj.mesh,
                selected_color(obj, DEFAULT_BASE_COLOR) if oid in highlighted else object_base_color(obj),
                model_matrix=object_space.model_matrix(obj),
                # M2-0 (§7.3): RD-1 Ghost for every Reference on `Alt+D`; RD-3 a Reference is
                # drawn in Wireframe too - a Normal object follows the display mode.
                alpha=REFERENCE_GHOST_ALPHA if reference and self.reference_ghost else 1.0,
                ignores_wireframe=reference,
                finish=object_finish(obj, self.display.surface_finish),
            )
        edit = scene.edit_object
        self.viewport.set_edit_base_color(
            selected_color(edit, DEFAULT_BASE_COLOR) if edit.id in highlighted else object_base_color(edit),
            object_finish(edit, self.display.surface_finish),
        )
        self._object_highlight_key = self._object_highlight_signature()

    def _highlighted_objects(self) -> frozenset:
        """The objects drawn as selected: the object selection, in mode `4` only (2026-10-16, Manu:
        "man kann nicht wirklich sehen, welches Objekt ausgewählt ist"; look `PROVISIONAL`)."""
        if self.selection.mode is not SelectionMode.OBJECT:
            return frozenset()
        return frozenset(oid for oid in self.selection.objects if oid in self.scene.objects)

    def _object_highlight_signature(self) -> tuple:
        scene = self.scene
        return (
            self._highlighted_objects(),
            scene.edit_object_id,
            tuple((oid, obj.state, obj.material) for oid, obj in scene.objects.items()),
        )

    def _sync_object_highlight(self) -> None:
        """Redraws the selection highlight when the object selection, the mode, the edit object or
        a state changed since it was last drawn - every path that changes them (click, box, Undo,
        key `4`, ...) is covered by the per-frame call in `update_viewport`."""
        if self.viewport is not None and self._object_highlight_signature() != self._object_highlight_key:
            self._sync_object_views()

    def _placement_changed(self) -> None:
        """An object's `transform`/`pivot` changed (AD-021 M2-1; the M2-2 object tools and their
        Undo call this). Positions in object space are unchanged, so nothing is rebuilt: the
        matrices go to the viewport, every pick cache re-projects (the edit object's camera
        revision already carries its transform; the explicit invalidation also covers the
        switch between `OrbitCamera` and its adapter), the hover is re-picked. Soft weights and
        symmetry live in object space and stay as they are (§4.8)."""
        self._pick_cache.invalidate()
        for cache in self._object_pick_caches.values():
            cache.invalidate()
        self._sync_object_views()
        self._refresh_hover()

    def _set_edit_object(self, object_id: ObjectId) -> None:
        """AD-021 M2-4 (E-14): **the one place** that changes the edit object. Sets
        `scene.edit_object_id` and moves everything that hangs on the edit object's mesh with
        it: the viewport's overlay entry (`Viewport.set_edit_mesh`; the previous edit object
        becomes an object entry in `_sync_object_views`), the pick caches, the hover and the
        soft radius (the fourth radius event, §4.8). The symmetry report cache is keyed by the
        mesh's geometry and needs nothing. The caller owns the component sets (§4.4: the Q-5
        gesture clears them, Undo/Redo restores the ones of the step), the soft preview that
        follows from them, and the refusals (a running interaction, a Reference - RF-5)."""
        scene = self.scene
        if object_id == scene.edit_object_id:
            return
        scene.edit_object_id = object_id
        self._follow_edit_object()

    def _follow_edit_object(self) -> None:
        """Everything that hangs on the edit object's mesh follows `scene.edit_object_id`. Called
        by `_set_edit_object`, by Delete of the edit object, and by Undo/Redo of a step whose
        command changed the edit object itself (`DeleteObjectsCommand`, `AddObjectCommand`): the
        scene is already switched there, only the view is behind."""
        obj = self.scene.edit_object
        self._pick_cache.invalidate()
        self.selection.hovered = None
        if self.viewport is not None:
            self.viewport.remove_object_entry(obj.id)
            self.viewport.set_edit_mesh(obj.mesh, object_space.model_matrix(obj))
        self._tints_seen = None  # the new RenderMesh has no region colours yet
        self._hidden_push()  # the new edit object keeps its own hidden set and mask
        self._soft_refresh_radius()
        self._sync_object_views()

    def _object_camera(self, obj: SceneObject):
        """The camera as the object's own space sees it (AD-021 M2-1, E-7): the `OrbitCamera`
        itself while the placement is identity (bit-exact as before), else its stable
        `ObjectSpaceCamera`."""
        if object_space.is_identity(obj.transform):
            return self.camera
        adapter = self._object_cameras.get(obj.id)
        if adapter is None or adapter.camera is not self.camera:
            adapter = self._object_cameras[obj.id] = ObjectSpaceCamera(self.camera, obj)
        return adapter

    @property
    def _edit_camera(self):
        """The camera every component path uses (picking, Knife, W/E/R/T): in the edit object's
        space (L-5)."""
        return self._object_camera(self.scene.edit_object)

    def _pick_object(self, x: float, y: float) -> ObjectId | None:
        """Mode `4`: the object whose surface is front-most under the cursor - every object,
        References included (RF-3); none is hidden in M1."""
        candidates = []
        for oid, obj in self.scene.objects.items():
            if oid == self.scene.edit_object_id:
                cache = self._pick_cache
            else:
                cache = self._object_pick_caches.setdefault(oid, PickCache())
            candidates.append(
                (oid, obj.mesh, cache, self._object_camera(obj), obj.transform.scale)
            )
        return pick_object(candidates, x, y, self.viewport_width, self.viewport_height)

    def _select_object_at(self, command: str, x: float, y: float) -> bool:
        """Klick in Modus `4` (AD-021 M1): ändert nur die Objekt-Auswahl (`selection.objects`).
        Ein einfacher Klick wählt genau dieses Objekt (ins Leere: Auswahl leer), Shift/Ctrl/Alt
        wie bei Komponenten. Q-12 revidiert (Manu 2026-10-16: ein Klick, der zugleich auf Referenz
        umschaltet, ist verwirrend): Referenz an/aus ist `Alt+R` (`_reference_command`). True =
        die Auswahl hat sich geändert."""
        if self._transform_key is not None:
            # M2-2: no selection or state change underneath a held W/E/R (its targets are fixed).
            return False
        selection = self.selection
        before = self._selection_snapshot()
        before_state = _selection_state(selection)
        hit = self._pick_object(x, y)
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
        changed = _selection_state(selection) != before_state
        if hit is not None and command == commands.SELECT:
            obj = self.scene.objects[hit]
            if hit == self.scene.edit_object_id:
                self._set_status(f"Object {obj.name!r} selected (being edited)")
            elif obj.state is ObjectState.REFERENCE:
                self._set_status(f"Object {obj.name!r} selected (Reference - Alt+R makes it Normal)")
            else:
                self._set_status(f"Object {obj.name!r} selected - 1/2/3 edits it")
        self._sync_object_highlight()
        return changed

    def _reference_command(self) -> bool:
        """`Alt+R` in mode `4`: switch every selected object except the edit object Normal <->
        Reference, one Undo step (Q-3; Q-12 revised 2026-10-16, key `PROVISIONAL`). The edit object
        never becomes a Reference (RF-2/RF-5)."""
        label = "Reference on/off"
        if self.interaction_owner is not None:
            return False
        if self.selection.mode is not SelectionMode.OBJECT:
            self._set_status(f"{label}: works on objects - press 4 and select them")
            return False
        scene = self.scene
        selected = [scene.objects[oid] for oid in sorted(self.selection.objects) if oid in scene.objects]
        if not selected:
            self._set_status(f"{label}: no object selected - click one first")
            return False
        edit = scene.edit_object
        targets = [obj for obj in selected if obj.id != edit.id]
        if not targets:
            self._set_status(f"Object {edit.name!r} is being edited - it cannot become a Reference")
            return False
        before = self._selection_snapshot()
        if len(targets) == len(selected) == 1:
            return self._switch_object_state(targets[0].id, before)
        steps = []
        for obj in targets:
            old = obj.state
            new = ObjectState.NORMAL if old is ObjectState.REFERENCE else ObjectState.REFERENCE
            obj.state = new
            steps.append(ObjectStateCommand(obj, old, new))
        self.history.push(steps[0] if len(steps) == 1 else CompositeCommand(steps, label))
        self._record_selection_history(before, mesh_step=False)
        self._sync_object_views()
        text = ", ".join(f"{obj.name!r}: {obj.state.name.capitalize()}" for obj in targets)
        if len(targets) < len(selected):
            text += f" ({edit.name!r} is being edited - stays Normal)"
        self._set_status(f"Object {text}")
        return True

    def _switch_object_state(self, object_id: ObjectId, selection_before: tuple) -> bool:
        """Normal <-> Referenz als ein Undo-Schritt (Q-3). Das Edit-Objekt wird nie Referenz
        (RF-2; RF-5 `PROVISIONAL`: in M1 ist es das einzige bearbeitbare Objekt, einen
        Wechsel des Edit-Objekts gibt es erst in M2)."""
        obj = self.scene.objects[object_id]
        if object_id == self.scene.edit_object_id:
            self._set_status(
                f"Object {obj.name!r} is being edited - it cannot become a Reference"
            )
            return False
        before = obj.state
        after = ObjectState.NORMAL if before is ObjectState.REFERENCE else ObjectState.REFERENCE
        obj.state = after
        self.history.push(ObjectStateCommand(obj, before, after))
        self._record_selection_history(selection_before, mesh_step=False)
        self._sync_object_views()
        self._set_status(f"Object {obj.name!r}: {after.name.capitalize()}")
        return True

    def _object_mode_refuses(self, command: str | None) -> bool:
        """AD-021 M1 (L-1, RF-4): True (and the refusal posted) for component work in mode `4`.
        M2-2: W/E/R pass - in `4` they are the object gesture, which refuses on its own
        (`_object_arm`: nothing selected, only References)."""
        if self.selection.mode is not SelectionMode.OBJECT or command not in _COMPONENT_COMMANDS:
            return False
        if command in _OBJECT_TRANSFORM_COMMANDS or command == commands.DELETE:
            return False  # Delete in `4` deletes the selected objects (`_delete_objects_command`)
        self._set_status(
            "Object mode: T, G, S, I, C, Shift+C, Dissolve, Shift+L/R, Shift+S, Alt+M, Shift+arrows and Ctrl+/- work"
            " on points/edges/faces"
            " - press 1/2/3 (Delete removes the selected objects)"
        )
        return True

    # -- Objekt-Geste in Modus `4` (AD-021 M2-2, E-11/E-12) -----------------------------

    def _object_arm(self, command: str, key: str) -> bool:
        """W/E/R in mode `4`: arm the object gesture on the selected objects without the
        References (RF-4, Q-1: locked; in a mixed selection they stay where they are and the
        status line says so, `PROVISIONAL`). Refused with a status line when nothing or only
        References are selected. Nothing moves before the first motion (AD-016, as W/E/R)."""
        label, verb, _ = _TRANSFORM_COMMANDS[command]
        picked = self._object_targets(
            f"Object {label}", f"to {verb} points/edges/faces press 1/2/3"
        )
        if picked is None:
            return False
        targets, references = picked
        paired = self._mirror_followers(f"Object {label}", targets)
        if paired is None:
            return False
        targets, followers = paired
        self._transform_key = key
        self._transform_command = command
        self._transform_target = frozenset()
        self._transform_begun = False
        self._object_gesture = _ObjectGesture(
            [(obj, obj.transform) for obj in targets],
            references,
            self._selection_snapshot(),
            followers=followers,
        )
        if command == commands.SCALE:
            constraint = " (uniform - X/Y/Z do not apply)" if self._axis_constraint else ""
        else:
            constraint = self._constraint_suffix(self._axis_constraint)
        self._set_status(
            f"Object {label}: {', '.join(repr(obj.name) for obj in targets)}{constraint}"
            f"{self._mirror_note(followers)}{self._object_references_note(references)}"
            f" - move the mouse, release {key.upper()} to commit"
        )
        return True

    def _object_targets(
        self, label: str, hint: str
    ) -> tuple[list[SceneObject], tuple[str, ...]] | None:
        """The selected objects an object command works on, and the names of the selected
        References it leaves alone (RF-4, Q-1). None (refusal posted) when nothing or only
        References are selected."""
        scene = self.scene
        selected = [scene.objects[oid] for oid in sorted(self.selection.objects) if oid in scene.objects]
        targets = [obj for obj in selected if obj.state is not ObjectState.REFERENCE]
        references = tuple(obj.name for obj in selected if obj.state is ObjectState.REFERENCE)
        if not selected:
            self._set_status(f"{label}: no object selected - click one first ({hint})")
            return None
        if not targets:
            self._set_status(
                f"Object mode: {references[0]!r} is a Reference - locked (select or switch only)"
            )
            return None
        return targets, references

    def _placement_command(self, command: str) -> bool:
        """Apply / Clear transform (AD-021 M2-3, L-3) on the selected non-Reference objects, mode
        `4` only. Objects without a placement are left alone; one Undo step for all of them."""
        label = _PLACEMENT_COMMANDS[command]
        if self.interaction_owner is not None:
            return False
        if self.selection.mode is not SelectionMode.OBJECT:
            self._set_status(f"{label}: works on objects - press 4 and select them")
            return False
        picked = self._object_targets(label, "press 4 and click the object")
        if picked is None:
            return False
        targets, references = picked
        placed = [obj for obj in targets if not object_space.is_identity(obj.transform)]
        if not placed:
            self._set_status(f"{label}: nothing to do - {self._objects_text(targets)} not placed")
            return False
        paired = [obj for obj in placed if self.scene.mirror_pair_of(obj.id) is not None]
        if paired:
            # PROVISIONAL (proposal §5.7 / §9 decision 4): Apply/Clear would change the placement
            # and the mesh/pivot relation the pair assumes - refused in v1, the way out named.
            self._set_status(f"{label}: {paired[0].name!r} is in a mirror pair - break the pair first (Shift+M)")
            return False
        if command == commands.CLEAR_TRANSFORM:
            return self._clear_transform(placed, references)
        return self._apply_transform(placed, references)

    def _clear_transform(self, placed: list[SceneObject], references: tuple[str, ...]) -> bool:
        """Clear (L-3): placement back to identity, the mesh stays, the object jumps; the pivot
        stays. One `ObjectTransformCommand` (an object step, `mesh_step=False`)."""
        before = self._selection_snapshot()
        changes = [(obj, obj.transform, IDENTITY_TRANSFORM) for obj in placed]
        for obj, _, after in changes:
            obj.transform = after
        self.history.push(ObjectTransformCommand(changes, "Clear transform"))
        self._record_selection_history(before, mesh_step=False)
        self._placement_changed()
        self._set_status(
            f"{self._objects_text(placed)}: transform cleared (object level, mesh unchanged)"
            f"{self._object_references_note(references)}"
        )
        return True

    def _apply_transform(self, placed: list[SceneObject], references: tuple[str, ...]) -> bool:
        """Apply (L-3, Max "Reset XForm"): every mesh position becomes its world position, the
        placement becomes identity, and the pivot moves to its old world position `t + c`
        (`PROVISIONAL`: a later Rotate/Scale turns about the same place as before; the
        alternative, pivot = origin, is a question for Manu). One `CompositeCommand` per press
        (E-13): a `MeshDeltaCommand` per object, then the transforms, then the pivots. Refused
        as a whole, before anything changes, when one object's symmetry definition would not
        survive the bake (`applied_symmetry_axis`)."""
        try:
            axes = [applied_symmetry_axis(obj) for obj in placed]
        except ApplyRefused as exc:
            self._set_status(f"Apply transform: refused - {exc}")
            return False
        before = self._selection_snapshot()
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
        self.history.push(CompositeCommand(parts, "Apply transform"))
        edit_id = self.scene.edit_object_id
        others = frozenset(obj.id for obj in placed if obj.id != edit_id)
        edit_changed = len(others) < len(placed)
        self._record_selection_history(before, mesh_step=edit_changed, object_meshes=others)
        self._object_meshes_changed(others)
        if edit_changed:
            self._notify_topology_changed()
        self._placement_changed()
        self._set_status(
            f"{self._objects_text(placed)}: transform applied (object level -> mesh;"
            f" placement is identity now){self._object_references_note(references)}"
        )
        return True

    def _object_meshes_changed(self, object_ids) -> None:
        """The mesh of these non-edit objects changed (Apply transform, its Undo/Redo): their
        render entries rebuild and their pick caches re-project."""
        for oid in object_ids:
            cache = self._object_pick_caches.get(oid)
            if cache is not None:
                cache.invalidate()
            if self.viewport is not None and oid in self.viewport.object_entries:
                self.viewport.object_entries[oid].mark_topology_dirty()

    @staticmethod
    def _object_references_note(references: tuple[str, ...]) -> str:
        if not references:
            return ""
        names = ", ".join(repr(name) for name in references)
        return f" - Reference {names} stays (locked)"

    def _object_step(self, dx: float, dy: float) -> bool:
        """One motion of the object gesture. The first one fixes the constraint (sticky axis,
        read once as at `begin()`; Q-4: Scale is always uniform) and, for Rotate, the axis:
        the camera's view direction without a constraint, else the world axis or the plane's
        normal. Move: world delta on the camera plane through the first target's pivot, masked
        by the world constraint, `t' = t_start + Σdelta`. Rotate: `R' = Q(axis, angle)·R_start`
        about each object's own pivot (its world position `t + c` does not depend on R and s,
        so no translation is corrected). Scale: `s' = s_start·f`. The factors are the
        component tools' (`RotateTool`, `ScaleTool`)."""
        gesture = self._object_gesture
        command = self._transform_command
        if not self._transform_begun:
            space = None if command == commands.SCALE else self._axis_constraint
            self._transform_space = space
            if command == commands.ROTATE:
                gesture.axis = (
                    self.camera.basis()[0] if space is None else _resolve_space(space, for_rotation=True)
                )
            elif command == commands.MOVE and space is not None:
                gesture.mask = _resolve_space(space, for_rotation=False)
            self._transform_begun = True
        if command == commands.MOVE:
            anchor = gesture.targets[0][0]
            delta = self.camera.screen_delta_to_world(
                object_space.to_world(anchor, anchor.pivot),
                dx, dy, self.viewport_width, self.viewport_height,
            )
            if gesture.mask is not None:
                delta = tuple(d * m for d, m in zip(delta, gesture.mask))
            gesture.move = tuple(gesture.move[i] + delta[i] for i in range(3))
        elif command == commands.ROTATE:
            gesture.pixels += dx
            self._object_rotate_angle(gesture, dx)
        else:
            gesture.pixels += dx + dy
        for obj, start in gesture.targets:
            obj.transform = self._object_transform_from(start)
        for follower, follower_start, driver, driver_start, pair in gesture.followers:
            follower.transform = (
                follower_start
                if driver.transform == driver_start
                else mirror_transform(driver.transform, pair.normal, pair.offset)
            )
        self._placement_changed()
        return True

    def _object_rotate_angle(self, gesture: _ObjectGesture, dx: float) -> None:
        """The Rotate angle of the object gesture: the dial about the first object's pivot when the pointer
        is known (as the mesh Rotate), else the dx fallback."""
        width, height = int(self.viewport_width), int(self.viewport_height)
        if self._rotate_virtual is None:
            gesture.angle += RotateTool.RADIANS_PER_PIXEL * dx * (PRECISION_GAIN if self._shift_held else 1.0)
            return
        if gesture.dial is None:
            anchor = gesture.targets[0][0]
            pivot = object_space.to_world(anchor, anchor.pivot)
            gesture.dial = DialAngle(self.camera, pivot, gesture.axis, self._rotate_press, width, height)
        gesture.angle = gesture.dial.update(*self._rotate_virtual, width, height, self._shift_held, self._snap_held())

    def _object_transform_from(self, start: ObjectTransform) -> ObjectTransform:
        """The transform the running gesture gives an object that started at `start`; exactly
        `start` while the gesture has accumulated nothing."""
        gesture = self._object_gesture
        command = self._transform_command
        if command == commands.MOVE:
            if gesture.move == (0.0, 0.0, 0.0):
                return start
            translation = tuple(start.translation[i] + gesture.move[i] for i in range(3))
            return dataclasses.replace(start, translation=translation)
        if command == commands.ROTATE:
            angle = gesture.angle
            if angle == 0.0:
                return start
            turn = object_space.axis_angle_rotation(gesture.axis, angle)
            rotation = object_space.orthonormalize(object_space.matmul3(turn, start.rotation))
            return dataclasses.replace(start, rotation=rotation)
        factor = max(ScaleTool.MIN_SCALE, 1.0 + ScaleTool.SCALE_PER_PIXEL * gesture.pixels)
        if factor == 1.0:
            return start
        return dataclasses.replace(start, scale=start.scale * factor)

    def _object_release(self) -> None:
        """Release of W/E/R in mode `4`: one `ObjectTransformCommand` for every object that
        changed (Q-3: one Undo step; mirror entry with `mesh_step=False`), status line on the
        level (Q-6); a tap or a gesture that ends where it started records nothing."""
        gesture = self._object_gesture
        label, _, participle = _TRANSFORM_COMMANDS[self._transform_command]
        if not self._transform_begun:
            self._set_status(f"Object {label}: no motion, nothing {participle}")
            return
        starts = gesture.targets + [(f, start) for f, start, _, _, _ in gesture.followers]
        changes = [(obj, start, obj.transform) for obj, start in starts if obj.transform != start]
        if not changes:
            self._set_status(f"Object {label}: no change")
            return
        objects = [obj for obj, _, _ in changes]
        self.history.push(ObjectTransformCommand(changes, f"Object {label.lower()}"))
        self._record_selection_history(gesture.selection_before, mesh_step=False)
        self._set_status(
            f"{self._objects_text(objects)}: {participle} (object level)"
            f"{self._constraint_suffix(self._transform_space)}"
            f"{self._mirror_note(gesture.followers)}"
            f"{self._object_references_note(gesture.references)}"
        )

    def _object_cancel(self) -> None:
        """Esc: every target gets its start transform back - the same instance, exactly."""
        gesture = self._object_gesture
        for obj, start in gesture.targets + [(f, start) for f, start, _, _, _ in gesture.followers]:
            obj.transform = start
        self._placement_changed()

    @staticmethod
    def _objects_text(objects: list[SceneObject]) -> str:
        names = ", ".join(repr(obj.name) for obj in objects)
        return f"Object {names}" if len(objects) == 1 else f"Objects {names}"

    def frame_scene(self) -> None:
        """Richtet die Kamera auf die Bounds des aktuellen Meshs aus (WP-06 B1).

        Reiner View-Effekt (wie `OrbitCamera.frame_on_bounds`): kein Mesh-
        Wechsel, kein History-Eintrag. No-op vor `init_scene()` oder wenn
        das Mesh keine Vertices hat (portiert aus `playground/app.py::
        _frame_camera`, jetzt als Production-API in `Application`)."""
        if self.viewport is None:
            return
        mesh = self.scene.mesh
        if not mesh.all_vertex_ids():
            return
        center, radius = mesh_center_and_radius(mesh)
        # AD-021 M2-1: the edit object's bounds in world.
        center, radius = object_space.world_center_and_radius(
            self.scene.edit_object, center, radius
        )
        self.camera.frame_on_bounds(center, radius)

    def load_scene(
        self,
        geometry_type: str = "cube",
        store_type: type[ResourceStore] = TraceStore,
        obj_path: str | Path | None = None,
        point_overlay_type: type | None = None,
        line_overlay_type: type | None = None,
        face_overlay_type: type | None = None,
        soft_overlay_type: type | None = None,
        soft_shading_overlay_type: type | None = None,
        symmetry_overlay_type: type | None = None,
        scene_path: str | Path | None = None,
        subd_overlay_type: type | None = None,
        mask_overlay_type: type | None = None,
    ) -> None:
        """Lädt eine Szene zur Laufzeit und setzt den mesh-gebundenen Zustand
        zurück (temporärer Scene-Loader `src/scene_menu.py`, PROVISIONAL).

        `init_scene(...)` tauscht Mesh und Viewport, lässt aber Selection,
        History und Hover der *alten* Szene stehen — deren IDs gehören zum
        alten Mesh. Deshalb danach:
        - Auswahl leeren (keine Geister-IDs im neuen Mesh);
        - frische `HistoryStack` für `scene.history` UND `app.history`
          (derselbe Alias wie in `__init__`, `core/history.py` bleibt
          unangetastet) plus die Selection-Mirror-Stacks leeren, damit
          Undo/Redo nach dem Wechsel keine Einträge der alten Szene sieht;
        - Hover löschen und den Pick-Cache invalidieren (der Cache hängt an
          der Application, nicht am Viewport, und die Kamera-Revision bleibt
          nach dem Tausch gleich);
        - Viewport-Größe/Aspect erneut melden (neuer Viewport) und die
          Kamera neu ausrichten;
        - die Soft-Selection-Vorschau neu rechnen: `init_scene` hat sie noch mit
          der *alten* Auswahl gerechnet, die jetzt geleert ist.
        Alle GL-Backends (`*_type`, auch `soft_overlay_type` und `symmetry_overlay_type`) gehen unverändert
        an `init_scene` — dort ist das Wiring die einzige Stelle.
        Kein History-Eintrag, keine Core-Änderung; der Aufrufer setzt bei
        Bedarf selbst einen Namen-Status (`set_status`)."""
        self.init_scene(
            geometry_type,
            store_type=store_type,
            obj_path=obj_path,
            point_overlay_type=point_overlay_type,
            line_overlay_type=line_overlay_type,
            face_overlay_type=face_overlay_type,
            soft_overlay_type=soft_overlay_type,
            soft_shading_overlay_type=soft_shading_overlay_type,
            symmetry_overlay_type=symmetry_overlay_type,
            scene_path=scene_path,
            subd_overlay_type=subd_overlay_type,
            mask_overlay_type=mask_overlay_type,
        )
        self.selection.clear()
        self.selection.clear_objects()
        self.history = HistoryStack()
        self.scene.history = self.history
        self._selection_undo_stack.clear()
        self._selection_redo_stack.clear()
        self._set_hovered(None)
        self._pick_cache.invalidate()
        self._soft_preview_refresh()
        self.set_viewport_size(self.viewport_width, self.viewport_height)
        self.frame_scene()

    def save_scene_file(self, path: str | Path) -> bool:
        """Schreibt die Szene als Szenendatei (`core.serialization`, Manu 2026-10-15; Strg+S
        und das SPACE-Menü, `src/scene_files.py`). True = geschrieben.

        Abgelehnt (Statuszeile, False), solange eine Interaktion die Tasten hält: mitten in
        W/E/R/T oder einer Knife-Session stünde ein halber Zustand im Mesh. Atomar über eine
        Nachbardatei, damit ein Fehler die alte Datei nicht zerstört. Kein History-Eintrag;
        Selection, History und Kamera werden nicht gespeichert (Format, V1_SPEC §12)."""
        owner = self.interaction_owner
        if owner is not None:
            self._set_status(f"Save scene: not while the {owner} interaction runs")
            return False
        path = Path(path)
        text = scene_to_json(self.scene)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        self._set_status(f"Saved scene: {path}")
        return True

    def dispatch_command(
        self, command: str, context: Optional[dict] = None, **params
    ) -> bool:
        """Dispatchet ein Command (True = wurde behandelt).

        Tool-Commands → ToolManager (Pattern A: nur aktivieren; Pattern B:
        mit `context` sofort `begin(**context)`).
        Undo/Redo → History.
        Display-Commands → `DisplayState` + Viewport (WP-06 B5a, E42).
        Modus-Commands → `Selection.mode` (WP-06 B5b, E43).
        Symmetrie-Zyklus → Definition des Meshs (AD-SYM-04 A1, `_symmetry_cycle`).
        Alles andere → False (bewusst minimal gehalten).
        """
        self.flush_hover()
        tool_class = tool_for_command(command)
        if tool_class:
            return self.tool_manager.activate(command, context=context)

        if self._knife is not None and command in (commands.UNDO, commands.REDO):
            # AD-017 history isolation: während einer Knife-Session nie die
            # globale History - auch nicht über den direkten Command-Pfad.
            return self._knife_history_step(command)
        if command in (commands.UNDO, commands.REDO):
            self._apply_undo_redo(command)
            return True
        if command in _DISPLAY_COMMANDS:
            return self._display_command(command)
        if command in _LOOK_COMMANDS:
            return self._look_command(command)
        if command in _SOFT_COMMANDS:
            return self._soft_command(command)
        if command in SUBD_COMMANDS:
            return self._subd_command(command)
        if command in _MODE_COMMANDS:
            return self._set_selection_mode(_MODE_COMMANDS[command])
        if command == commands.TOGGLE_TRANSFORM_SPACE:
            return self._toggle_orientation()
        if self._object_mode_refuses(command):
            return False
        if command in _PLACEMENT_COMMANDS:
            return self._placement_command(command)
        if command == commands.TOGGLE_REFERENCE:
            return self._reference_command()
        if command == commands.CONNECT:
            return self._connect_command()
        if command == commands.DELETE and self.selection.mode is SelectionMode.OBJECT:
            return self._delete_objects_command()
        if command in _REMOVAL_COMMANDS:
            return self._removal_command(command)
        if command == commands.COLLAPSE:
            return self._collapse_command()
        if command == commands.SYMMETRY_CYCLE:
            return self._symmetry_cycle()
        if command in _MASK_COMMANDS:
            return self._mask_command(command)
        if command in _HIDE_COMMANDS:
            return self._hide_command(command)
        if command in _REGION_COMMANDS:
            return self._region_command(command)
        if command == commands.RESYMMETRIZE:
            return self._resymmetrize_open()
        if command in (commands.EDGE_LOOP, commands.EDGE_RING):
            return self._loop_select(command)
        if command == commands.LOOP_INSERT:
            return self._loop_insert()
        if command in _SELECTION_STEP_COMMANDS:
            return self._selection_step(command)

        return False

    # -- Symmetry definition (AD-SYM-04 Slice A1) ---------------------------------

    def _symmetry_cycle(self) -> bool:
        """Shift+S (Q-1 = E-1): off → X → Y → Z → off, one Undo step per press (E2), E1 plane
        and E3 seam from `mirai.symmetry_axis`. Not while an interaction owns the keys (R-4): an
        armed W/E/R/T has resolved its partner set at arm/`begin()`, a Knife session its
        symmetry view at begin, and a changed definition must not slide in underneath them.
        The change is reported to the viewport as a topology change (K-3): a definition-only
        change moves nothing, but every overlay that reads the definition must re-derive, the
        soft bands too (the symmetric field under a definition, AD-SYM-04 D-5) - the same
        notification Undo of it gets."""
        if self.interaction_owner is not None:
            return False
        axis = next_axis(current_axis(self.scene.mesh))
        changed = self._mesh_transaction(
            f"Symmetry {axis or 'off'}", lambda mesh: set_symmetry_axis(mesh, axis)
        ).changed
        self._set_status(symmetry_status_text(self.scene.mesh))
        return changed

    # -- Re-Symmetrize (AD-SYM-04 Slice A3, §10 R-a) -------------------------------

    @property
    def resymmetrize_preview(self) -> ResymPlan | None:
        """The open Re-Symmetrize preview (its plan), None = closed."""
        return self._resym_plan

    def _resymmetrize_summary(self) -> str:
        # The bound key, not a literal (as the HUD hints): a `keymap.json` rebinding shows up here.
        bound = [inp for inp in self.bindings.inputs_for(commands.RESYMMETRIZE) if inp.kind == "key"]
        return plan_summary(self._resym_plan, key_label(bound[0]) if bound else "?")

    def _resymmetrize_open(self) -> bool:
        """Re-Symmetrize key without a preview (the Lab's KEEP behaviour, M / M / Esc): exactly one
        selected vertex is the source; its topological side is mirrored onto the other side and the
        seam laid into the plane (`mirai.resymmetrize`). The plan is computed once here and shown;
        the next press executes exactly it, Esc closes it. Refused with the Lab's reasons."""
        if self.interaction_owner is not None:
            return False
        mesh = self.scene.mesh
        selected = self.selection.vertices
        try:
            if mesh.symmetry_definition is None:
                raise ResymmetrizeRejected("Symmetrie aus")
            if not selected:
                raise ResymmetrizeRejected("keine Auswahl")
            if len(selected) != 1:
                raise ResymmetrizeRejected("genau einen Vertex auswählen")
            plan = plan_resymmetrize(mesh, next(iter(selected)))
        except ResymmetrizeRejected as exc:
            self._set_status(f"Re-Symmetrize: {exc}")
            return False
        self._resym_plan = plan
        # The Lab paused the hover through the gate (`hover_suspended`); here `_update_hover` reads
        # the open preview itself, so the flag stays a host hook.
        self._set_hovered(None)
        self._resymmetrize_display_changed()
        self._set_status(self._resymmetrize_summary())
        return True

    def _resymmetrize_key(self, input: Input) -> bool:
        """Keys while the preview is open: the Re-Symmetrize key executes, Cancel closes, the pure
        display keys pass; every other bound key is ignored with the hint (the Lab's preview row:
        display commands only). Navigation is pointer input and never reaches here."""
        command = self.bindings.command_for(input)
        if command == commands.RESYMMETRIZE:
            return self._resymmetrize_execute()
        if command == commands.CANCEL:
            self._resymmetrize_close()
            self._set_status("Re-Symmetrize abgebrochen")
            return True
        if command in _DISPLAY_COMMANDS:
            return self.dispatch_command(command)
        if command is not None:
            self._resymmetrize_refuse()
        return False

    def _resymmetrize_refuse(self) -> None:
        self._set_status(f"{RESYM_PREVIEW_HINT} | {self._resymmetrize_summary()}")

    def _resymmetrize_execute(self) -> bool:
        """Sets exactly the shown plan: one Undo step (selection kept and restored with it); an
        empty plan records nothing. The preview is closed first, so the transaction's hover
        refresh picks again."""
        plan = self._resym_plan
        self._resymmetrize_close()
        changed = self._mesh_transaction(
            plan_description(plan),
            lambda mesh: set_plan_positions(mesh, plan),
            moved_of=lambda moved: moved,
        ).changed
        if changed:
            self._set_status(f"Re-Symmetrize ausgeführt: {len(plan.changes)} Änderungen")
        else:
            self._set_status("Re-Symmetrize: 0 Änderungen — kein Schritt")
        return True

    def _resymmetrize_close(self) -> None:
        if self._resym_plan is None:
            return
        self._resym_plan = None
        self._resymmetrize_display_changed()
        self._refresh_hover()

    def _resymmetrize_display_changed(self) -> None:
        # Opening and closing change no mesh and tell the viewport nothing: the display re-syncs.
        if self._symmetry_display is not None:
            self._symmetry_display.dirty = True

    @property
    def symmetry_display(self) -> SymmetryDisplay | None:
        """Plane outline and problem markers (AD-SYM-04 A2), None without a
        `symmetry_overlay_type` (headless)."""
        return self._symmetry_display

    def toggle_symmetry_display(self) -> bool | None:
        """Shift+Ctrl+S: show / hide the symmetry plane and the seam / problem markers (display only,
        the symmetry definition is untouched). Returns the new visibility, None without a display."""
        display = self._symmetry_display
        if display is None:
            return None
        display.visible = not display.visible
        self._set_status(f"Symmetry display: {'on' if display.visible else 'off'}")
        return display.visible

    def _symmetry_display_deferred(self) -> bool:
        # Plan A3 of WP-SYM-LAB-03 (`mirai.symmetry_display`): while W/E/R/T is armed or running
        # a pure position change is not re-derived; the markers still follow the moved vertices.
        return self.interaction_owner == "transform"

    # -- Component-Modi (WP-06 B5b) ---------------------------------------------

    def _set_selection_mode(self, mode: SelectionMode) -> bool:
        """1/2/3 wie Playground `window.py`: Modus setzen, Auswahl leeren, Hover
        löschen (R-SEL-2). Auch der bereits aktive Modus leert die Auswahl
        (Playground-Verhalten). Kein History-Eintrag; der Hover kommt mit der
        nächsten Mausbewegung im neuen Modus zurück. `4` (AD-021 M1) genauso; `clear()`
        leert nur die Komponenten, die Objekt-Auswahl bleibt (§4.4).

        AD-021 M2-4 (Q-5): from `4` to `1`/`2`/`3` with exactly one Normal object selected, that
        object becomes the edit object first (E-14; order §4.4: read `objects`, set the edit
        object, clear the components). No Undo step; the next step's mirror snapshot carries it.
        Several objects or a Reference selected: no switch, the status line says why."""
        note = ""
        if mode is not SelectionMode.OBJECT and self.selection.mode is SelectionMode.OBJECT:
            note = self._edit_object_from_selection()
        self.selection.mode = mode
        self.selection.clear()
        self.selection.hovered = None
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        text = f"Mode: {mode.name.capitalize()}{note}"
        edit = self.scene.edit_object
        if mode is not SelectionMode.OBJECT and not object_space.is_identity(edit.transform):
            # AD-021 Q-6 (status line first, L-4): the edit object carries a placement.
            text += f" · object {edit.name!r} is placed (object level)"
        self._set_status(text)
        self._sync_object_highlight()
        return True

    def _edit_object_from_selection(self) -> str:
        """Q-5: switch the edit object to the one Normal object selected in `4` (E-14). Returns
        the status-line note: whom `1`/`2`/`3` now edit, or why the edit object stayed."""
        scene = self.scene
        selected = [scene.objects[oid] for oid in sorted(self.selection.objects) if oid in scene.objects]
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
        owner = self.interaction_owner
        if owner is not None:
            return f" · not while the {owner} interaction runs - still editing {edit.name!r}"
        started = time.perf_counter()
        self._set_edit_object(obj.id)
        self.last_edit_switch_seconds = time.perf_counter() - started
        return f" · editing {obj.name!r}"

    # -- Contextual C: Split / Edge Connect / Vertex Connect (WP-06 B6, AD-017) --

    def _connect_command(self) -> bool:
        """`C`: resolves the selection context (`resolve_c_context`, same
        dispatch as the Playground `window.py`) and applies Split / Edge
        Connect / Vertex Connect through the shared `mirai.topology`
        implementation; an empty selection begins a Knife session (WP-06
        B7, `_knife_begin`). Mutates only through
        `Mesh.split_edge`/`Mesh.connect_vertices` (ARCH-02); exactly one
        `MeshDeltaCommand` per success, mesh and history untouched on
        rejection or no-op. Each success branch reports the topology change
        through `_notify_topology_changed()`, which also re-anchors the hover
        (the hovered edge/face handle can be gone after Split/Connect), and
        records the pre-mutation selection for Undo/Redo restore (WP-06 B6
        follow-up, `_record_selection_history`).

        Whenever a symmetry definition is set, the selection is first
        canonicalised to one side (A2 = A, AD-SYM-03 §6) on a temporary value,
        for every context; that one canonical value is resolved in the one
        `resolve_c_context` call and read by the branches. A host's
        `command_gate.refused_contexts` (H2 amendment G-2) is checked right
        after that call, before any branch: a listed context posts its text and
        returns False with mesh, history and `self.selection` untouched.

        A declared Connect context with a definition set runs its coordinator
        (`_connect_op`) inside the same single transaction; a `SymmetryRefusal`
        restores the mesh, posts its text, records no history entry and leaves
        the selection untouched. Under symmetry Edge Connect selects the created
        edges on the side(s) where the live selection had elements (only the
        plane -> the normal's side; created edges on the plane stay;
        `residue_sides`, Artist ITERATE 2026-10-08), Split (slice 4) the same
        for its new vertices (engineering default, judged in the practical
        test; a seam edge's new vertex lies on the plane and stays); Vertex
        Connect keeps the live selection (AD-017 residue)."""
        selection = self.selection
        effective = self._canonical_c_selection()
        ctx = resolve_c_context(effective)
        if self._context_refuses(ctx):
            return False

        if ctx is CContext.SPLIT:
            mesh = self.scene.mesh
            # Taken from the live selection before the transaction (and before canonicalisation
            # reaches the mesh): the sides the artist worked on.
            sides = (
                residue_sides(mesh, selection.edges, mesh.edge_vertices)
                if self._connect_coordinator(ctx) is not None
                else None
            )

            def split_plain(mesh: Mesh, edge_ids: set) -> list:
                (edge_id,) = edge_ids
                return [mesh.split_edge(edge_id)[0]]

            def residue(created) -> None:
                kept = set(created)
                if sides is not None:
                    kept = on_residue_sides(mesh, kept, sides, lambda v: (v,))
                selection.mode = SelectionMode.VERTEX
                selection.clear()
                selection.add(kept)

            try:
                self._mesh_transaction(
                    "Split Edge",
                    lambda mesh: self._connect_op(ctx, split_plain)(mesh, set(effective.edges)),
                    on_applied=residue,
                )
            except SymmetryRefusal as exc:
                self._set_status(str(exc))
                return False
            self._set_status("Split")
            return True

        if ctx is CContext.EDGE_CONNECT:
            return self._edge_connect(
                selection.edges, effective.edges, EDGE_CONNECT_LABEL, "Connect Edges"
            )

        if ctx is CContext.VERTEX_CONNECT:
            # Residue (AD-017): the original vertices stay selected, Vertex
            # mode unchanged — no `on_applied`, the selection is not touched.
            try:
                outcome = self._mesh_transaction(
                    VERTEX_CONNECT_LABEL,
                    lambda mesh: self._connect_op(ctx, apply_connect_vertices)(
                        mesh, set(effective.vertices)
                    ),
                )
            except (VertexConnectError, SymmetryRefusal) as exc:
                self._set_status(str(exc))
                return False
            if not outcome.changed:
                self._set_status("Vertex Connect: nothing connectable")
                return False
            self._set_status("Vertex Connect")
            return True

        if ctx is CContext.KNIFE:
            return self._knife_begin()

        # CContext.NONE: 1 vertex, Face mode, or another combination with no
        # C meaning (AD-017 §7).
        self._set_status("C: nothing to do here")
        return False

    def _edge_connect(self, live_edges, effective_edges, description: str, status: str) -> bool:
        """Edge Connect of `effective_edges` (canonical under symmetry) as one transaction; the
        created edges become the selection, under symmetry on the sides `live_edges` had
        (`residue_sides`). Shared by `C` (2+ edges) and Loop Insert (`I`, the ring's edges)."""
        ctx = CContext.EDGE_CONNECT
        selection = self.selection
        mesh = self.scene.mesh
        # Taken from the live edges before the transaction (and before canonicalisation
        # reaches the mesh): the sides the artist worked on.
        sides = (
            residue_sides(mesh, set(live_edges), mesh.edge_vertices)
            if self._connect_coordinator(ctx) is not None
            else None
        )

        def residue(result) -> None:
            created = set(result.created)
            if sides is not None:
                created = on_residue_sides(mesh, created, sides, mesh.edge_vertices)
            selection.clear()
            selection.add(created)

        def mutate(mesh):
            result = self._connect_op(ctx, apply_connect_edges)(mesh, set(effective_edges))
            if guarded and not all(mesh.is_valid_face(f) for f in guarded):
                # e.g. a ring that closes around the hidden part (or a mirrored ring) would cut a hidden quad
                raise TopologyToolError(f"{description}: hidden geometry in the way (Alt+H shows all)")
            return result

        hidden = self._hidden
        guarded = (
            [f for f in mesh.all_face_ids() if hidden.is_hidden_face(mesh, f)] if hidden else []
        )
        try:
            self._mesh_transaction(description, mutate, on_applied=residue)
        except (TopologyToolError, SymmetryRefusal) as exc:
            self._set_status(str(exc))
            return False
        self._set_status(status)
        return True

    def _connect_op(self, context: CContext, plain: Callable) -> Callable:
        """The mutation `_connect_command` runs for a declared context: the coordinator
        declared for `context` (`mirai.symmetry_declarations`, AD-SYM-03 slices 3b/4) whenever a
        symmetry definition is set — in MARK as in BLOCK, its refusals are part of a supported
        operation, not a gate (H2 amendment, "Runtime refusals are not G-3") — otherwise the
        unchanged `plain` function. Both run inside the caller's one `_mesh_transaction`."""
        coordinator = self._connect_coordinator(context)
        return plain if coordinator is None else coordinator

    def _connect_coordinator(self, context: CContext) -> Callable | None:
        """The coordinator that runs `context` now: declared and a definition set; else None."""
        if self.scene.mesh.symmetry_definition is None:
            return None
        return symmetry_declarations.C_CONTEXT_COORDINATORS.get(context)

    def _canonical_c_selection(self) -> Selection:
        """The selection `C` reads (AD-SYM-03 §6 A2 = A; AD-013 H2 amendment,
        canonicalisation): without a symmetry definition the live selection;
        with one, a temporary copy in which each mirror pair counts once
        (`canonical_*` keep the normal's side). Never written back: a refused
        or failed `C` leaves `self.selection` (mode and every id set) as it was.
        This is the meaning of `C` under symmetry, not a support policy (G-3)."""
        mesh = self.scene.mesh
        selection = self.selection
        if mesh.symmetry_definition is None:
            return selection
        index = SymmetryIndex(mesh)
        effective = Selection()
        effective.mode = selection.mode
        effective.vertices = canonical_vertices(index, selection.vertices)
        effective.edges = canonical_edges(index, selection.edges)
        effective.faces = canonical_faces(index, selection.faces)
        return effective

    def _context_refuses(self, context: CContext) -> bool:
        """H2 amendment G-2: True (and the refusal posted as status) if
        `command_gate.refused_contexts` lists the resolved `C` context. The
        third gate site, below `dispatch_command`; one `None` test or one
        empty lookup with the defaults."""
        gate = self.command_gate
        if gate is None:
            return False
        text = gate.context_refusal(context)
        if text is None:
            return False
        self._set_status(text)
        return True

    # -- Loop tools (2026-10-15, promoted from the Playground, Manu) ----------------------
    #
    # Shift+L / Shift+R add the edge loops / rings of the selected edges (else of the hovered
    # edge) to the selection; I inserts a loop through the ring of each such edge (the ring's
    # edges through the shared Edge Connect, so the symmetric coordinator of `C` covers it);
    # hold G slides the selected loop(s) (`mirai.topology.loop_slide`). Edge mode only;
    # `PROVISIONAL` (no Artist verdict for the loop tools yet).

    def _loop_seed_edges(self, label: str) -> set[EdgeId] | None:
        """The selected edges, else the hovered edge; None (status posted) outside edge mode
        or without either."""
        selection = self.selection
        mesh = self.scene.mesh
        if selection.mode is not SelectionMode.EDGE:
            self._set_status(f"{label}: edge mode needed (2)")
            return None
        edges = {e for e in selection.edges if mesh.is_valid_edge(e)}
        hovered = selection.hovered
        if not edges and isinstance(hovered, EdgeId) and mesh.is_valid_edge(hovered):
            edges = {hovered}
        if not edges:
            self._set_status(f"{label}: select or hover an edge")
            return None
        return edges

    def _loop_select(self, command: str) -> bool:
        label = "Edge Loop" if command == commands.EDGE_LOOP else "Edge Ring"
        seeds = self._loop_seed_edges(label)
        if seeds is None:
            return False
        walk = edge_loop if command == commands.EDGE_LOOP else edge_ring
        mesh = self.scene.mesh
        blocked = self._hidden.vertices()  # a loop / ring ends at hidden geometry, it does not run through it
        found: set[EdgeId] = set()
        for edge in sorted(seeds):
            if edge in found:
                continue
            try:
                found.update(walk(mesh, edge, blocked).edges)
            except LoopRingError as exc:
                self._set_status(f"{label}: {exc}")
                return False
        selection = self.selection
        before = len(selection.edges)
        selection.add(self._drop_hidden(found))
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        added = len(selection.edges) - before
        self._set_status(f"{label}: {len(selection.edges)} edges selected (+{added})")
        return True

    # -- Selection steps (WP Toolbox Gaps A1, Manu 2026-10-23) ---------------------------
    #
    # Ctrl++ / Ctrl+- grow / shrink the selection in the active mode; Shift+Up / Shift+Down grow
    # / shrink the selected loop pieces at both ends; Shift+Right / Shift+Left move them to the
    # parallel loop on that screen side. Like Shift+L: a selection change, no History step;
    # the loop steps need edge mode. Not mirrored under symmetry (no selection command is);
    # `PROVISIONAL`.

    def _selection_step(self, command: str) -> bool:
        selection = self.selection
        mesh = self.scene.mesh
        mode = selection.mode
        if command in (commands.SELECT_GROW, commands.SELECT_SHRINK):
            label = "Grow" if command == commands.SELECT_GROW else "Shrink"
            current = {
                SelectionMode.VERTEX: selection.vertices,
                SelectionMode.EDGE: selection.edges,
                SelectionMode.FACE: selection.faces,
            }[mode]
            valid = {
                SelectionMode.VERTEX: mesh.is_valid_vertex,
                SelectionMode.EDGE: mesh.is_valid_edge,
                SelectionMode.FACE: mesh.is_valid_face,
            }[mode]
            ids = {i for i in current if valid(i)}
            if not ids:
                self._set_status(f"{label}: nothing selected")
                return False
            step = selection_steps.grow if command == commands.SELECT_GROW else selection_steps.shrink
            return self._apply_selection_step(label, step(mesh, mode, ids))
        labels = {
            commands.LOOP_GROW: "Loop grow",
            commands.LOOP_SHRINK: "Loop shrink",
            commands.LOOP_NEXT: "Next loop",
            commands.LOOP_PREVIOUS: "Previous loop",
        }
        label = labels[command]
        if mode is not SelectionMode.EDGE:
            self._set_status(f"{label}: edge mode needed (2)")
            return False
        edges = {e for e in selection.edges if mesh.is_valid_edge(e)}
        if not edges:
            self._set_status(f"{label}: select edges of a loop")
            return False
        blocked = self._hidden.vertices()
        if command == commands.LOOP_GROW:
            return self._apply_selection_step(label, selection_steps.loop_grow(mesh, edges, blocked))
        if command == commands.LOOP_SHRINK:
            return self._apply_selection_step(label, selection_steps.loop_shrink(mesh, edges, blocked))
        return self._loop_shift(label, edges, rightwards=command == commands.LOOP_NEXT)

    def _drop_hidden(self, ids: set) -> set:
        """`ids` (of the active mode) without the hidden elements: a step or loop never selects what cannot be seen."""
        hidden = self._hidden
        if not hidden or not ids:
            return ids
        mesh = self.scene.mesh
        mode = self.selection.mode
        if mode is SelectionMode.VERTEX:
            return {i for i in ids if not hidden.is_hidden_vertex(i)}
        if mode is SelectionMode.EDGE:
            return {i for i in ids if not hidden.is_hidden_edge(mesh, i)}
        if mode is SelectionMode.FACE:
            return {i for i in ids if not hidden.is_hidden_face(mesh, i)}
        return ids

    def _apply_selection_step(self, label: str, ids: set, note: str = "") -> bool:
        selection = self.selection
        before = _selection_state(selection)
        ids = self._drop_hidden(ids)
        selection.set(ids)
        count = len(ids)
        if _selection_state(selection) == before:
            self._set_status(f"{label}: no change ({count} selected){note}")
            return False
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        self._set_status(f"{label}: {count} selected{note}")
        return True

    def _loop_shift(self, label: str, edges: set[EdgeId], rightwards: bool) -> bool:
        """Each loop piece moves to its parallel piece on the screen side asked for: right
        (Shift+Right) or left; for a piece whose neighbours lie above / below each other on
        screen, up counts as right. A piece without quads on that side stays."""
        mesh = self.scene.mesh
        blocked = self._hidden.vertices()
        out: set[EdgeId] = set()
        stuck = 0
        for piece in selection_steps.loop_pieces(mesh, edges, blocked):
            sides = {
                left: selection_steps.shifted_piece(mesh, piece, left, blocked) for left in (True, False)
            }
            left = self._screen_side(piece.edges, sides, rightwards)
            target = sides[left]
            if target is None:
                stuck += 1
                out.update(piece.edges)
            else:
                out.update(target)
        note = f" - {stuck} piece(s) at a border or non-quad stayed" if stuck else ""
        return self._apply_selection_step(label, out, note)

    def _screen_side(self, piece_edges, sides: dict, rightwards: bool) -> bool:
        """The winding side (`left` key of `sides`) that lies towards screen right / up when
        `rightwards`, else the other one. Without a usable projection: right = the left side."""
        centre = self._edges_screen_centre(piece_edges)
        offsets = {}
        if centre is not None:
            for left, shifted in sides.items():
                if shifted is None:
                    continue
                c = self._edges_screen_centre(shifted)
                if c is not None:
                    offsets[left] = (c[0] - centre[0], c[1] - centre[1])
        if True in offsets and False in offsets:
            dx = offsets[True][0] - offsets[False][0]
            dy = offsets[True][1] - offsets[False][1]
        elif offsets:
            ((left, (dx, dy)),) = offsets.items()
            if not left:
                dx, dy = -dx, -dy
        else:
            dx = dy = 0.0
        # (dx, dy): screen direction from the right-hand to the left-hand winding side.
        along = dx if abs(dx) >= abs(dy) else dy
        if abs(along) < 1e-6:
            return rightwards
        return (along > 0) == rightwards

    def _edges_screen_centre(self, edge_ids) -> tuple[float, float] | None:
        mesh = self.scene.mesh
        vertices = {v for e in edge_ids for v in mesh.edge_vertices(e)}
        if not vertices or self.viewport_width <= 0 or self.viewport_height <= 0:
            return None
        n = len(vertices)
        x = sum(mesh.vertex_position(v)[0] for v in vertices) / n
        y = sum(mesh.vertex_position(v)[1] for v in vertices) / n
        z = sum(mesh.vertex_position(v)[2] for v in vertices) / n
        return self._edit_camera.project_to_screen((x, y, z), self.viewport_width, self.viewport_height)

    def _loop_insert(self) -> bool:
        seeds = self._loop_seed_edges("Loop Insert")
        if seeds is None:
            return False
        mesh = self.scene.mesh
        blocked = self._hidden.vertices()  # the ring ends at hidden geometry (Isolate): only visible quads are cut
        ring: set[EdgeId] = set()
        for edge in sorted(seeds):
            if edge not in ring:
                ring.update(edge_ring(mesh, edge, blocked).edges)
        if len(ring) < 2:
            self._set_status(
                "Loop Insert: no edge ring through this edge (needs visible quads)" if blocked
                else "Loop Insert: no edge ring through this edge (needs quads)"
            )
            return False
        effective = ring
        if mesh.symmetry_definition is not None:
            effective = canonical_edges(SymmetryIndex(mesh), ring)
        return self._edge_connect(ring, effective, "Loop Insert", "Loop Insert")

    def _slide_arm(self, key: str) -> bool:
        """Hold G: plan the slide of the selected (else the hovered) edges now; refusals are
        posted at the press, before anything moves. Nothing moves before the first motion."""
        edges = self._loop_seed_edges(LOOP_SLIDE_LABEL)
        if edges is None:
            return False
        mesh = self.scene.mesh
        try:
            plan = plan_loop_slide(mesh, edges)
        except LoopSlideRefused as exc:
            self._set_status(str(exc))
            return False
        self._transform_key = key
        self._transform_command = commands.LOOP_SLIDE
        self._transform_target = frozenset(plan.vertex_ids)
        self._transform_begun = False
        self._slide_plan = plan
        self._slide_t = 0.0
        self._slide_direction = self._slide_screen_direction(plan)
        self._set_hovered(None)
        count = len(plan.vertex_ids)
        self._set_status(
            f"{LOOP_SLIDE_LABEL}: {count} vertices - move the mouse, release {key.upper()} to commit"
        )
        return True

    def _slide_screen_direction(self, plan: SlidePlan) -> tuple[float, float] | None:
        """Mean screen vector from each driven vertex to its side-A target (px for t = 1)."""
        camera = self._edit_camera
        sx = sy = 0.0
        n = 0
        for orig, side_a, _ in plan.slides.values():
            a = camera.project_to_screen(orig, self.viewport_width, self.viewport_height)
            b = camera.project_to_screen(side_a, self.viewport_width, self.viewport_height)
            if a is None or b is None:
                continue
            sx += b[0] - a[0]
            sy += b[1] - a[1]
            n += 1
        if n == 0 or math.hypot(sx / n, sy / n) < 1.0:
            return None
        return (sx / n, sy / n)

    def _slide_step(self, dx: float, dy: float) -> bool:
        plan = self._slide_plan
        if plan is None:
            return False
        mesh = self.scene.mesh
        if not self._transform_begun:
            self._slide_before = mesh.begin_change()
            self._slide_selection_before = self._selection_snapshot()
            self._transform_begun = True
        direction = self._slide_direction
        if direction is None:
            # Edges seen end-on: the Playground's mapping (horizontal motion).
            self._slide_t += dx / self.viewport_width * 2.0
        else:
            self._slide_t += (dx * direction[0] + dy * direction[1]) / (
                direction[0] ** 2 + direction[1] ** 2
            )
        self._slide_t = max(-1.0, min(1.0, self._slide_t))
        positions = slide_positions(plan, self._slide_t)
        for vid, position in positions.items():
            mesh.set_vertex_position(vid, position)
        self._pick_cache.invalidate()
        self.viewport.on_vertices_moved(set(positions))
        return True

    def _slide_release(self) -> None:
        mesh = self.scene.mesh
        before = self._slide_before
        if not self._transform_begun or before is None:
            self._set_status(f"{LOOP_SLIDE_LABEL}: no change")
            return
        self._slide_before = None
        delta = mesh.end_change(before)
        if delta.empty:
            self._set_status(f"{LOOP_SLIDE_LABEL}: no change")
            return
        self.history.push(MeshDeltaCommand(mesh=mesh, delta=delta, description=LOOP_SLIDE_LABEL))
        self._record_selection_history(self._slide_selection_before)
        self._soft_preview_refresh()
        self._set_status(f"{LOOP_SLIDE_LABEL} committed")

    def _slide_abort(self) -> None:
        before = self._slide_before
        if before is None or self._slide_plan is None:
            return
        self._slide_before = None
        self.scene.mesh.rollback_change(before)
        self._pick_cache.invalidate()
        if self.viewport is not None:
            self.viewport.on_vertices_moved(set(self._slide_plan.vertex_ids))

    # -- Smooth / Relax (WP Toolbox Gaps C2) -----------------------------------------

    def _smooth_arm(self, command: str, key: str) -> bool:
        """Hold S / Alt+S: plan on the resolved selection (else the hovered element) now; refusals are
        posted at the press. Nothing moves before the first motion or the release (tap)."""
        relax = command == commands.RELAX
        mesh = self.scene.mesh
        selection = self.selection
        target = resolve_selection_vertices(mesh, selection, selection.mode)
        if not target and selection.hovered is not None:
            target = _element_vertices(mesh, selection.hovered)
        soft = self._soft if self._soft.enabled else None
        try:
            weights = None if soft is None or not target else self._smooth_soft_weights(target, soft)
            plan = plan_smooth(mesh, target, relax=relax, weights=weights, mask=self._mask_values())
        except (SmoothRefused, SoftSymmetryRefusal) as exc:
            label = RELAX_LABEL if relax else SMOOTH_LABEL
            text = str(exc)
            self._set_status(text if text.startswith(label) else f"{label}: refused — {text}")
            return False
        self._smooth_seeds = frozenset(target)
        self._transform_key = key
        self._transform_command = command
        self._transform_target = plan.movable
        self._transform_begun = False
        self._smooth_plan = plan
        self._smooth_amount = 0.0
        self._set_hovered(None)
        if soft is not None:
            # The same gesture state as a Soft W/E/R: live radius / flow steps go through it.
            self._soft_gesture = soft
            self._soft_gesture_reference = soft.world_radius * 100.0 / soft.radius_percent
            self._smooth_show_weights()
        soft_note = " (Soft: wheel = radius)" if soft is not None else ""
        self._set_status(
            f"{plan.label}: {len(plan.movable)} points{soft_note} - tap for one step, or drag right/left for"
            f" more/less, release {key.upper()} to commit"
        )
        return True

    def _smooth_soft_weights(self, seeds, soft: SoftSettings) -> dict[VertexId, float]:
        """The influence of `seeds` by the same function and arguments as a Soft W/E/R (plain field, or
        under a definition the symmetric field; raises `SoftSymmetryRefusal` like W/E/R at `begin()`)."""
        mesh = self.scene.mesh
        if mesh.symmetry_definition is None:
            return compute_influence(
                mesh, set(seeds), soft.world_radius, metric=soft.metric, curve=soft.curve,
                curve_power=soft.curve_power, flow_ratio=soft.flow_ratio,
            )
        return symmetric_influence(
            mesh, set(seeds), soft.world_radius, metric=soft.metric, curve=soft.curve,
            curve_power=soft.curve_power, correspondence=vertex_correspondence(mesh),
            flow_ratio=soft.flow_ratio,
        ).weights

    def _smooth_show_weights(self) -> None:
        """The display shows the held Smooth / Relax's own weights (as `_soft_show_op_weights` for W/E/R)."""
        if self._soft_overlay is None and self._soft_shading_overlay is None:
            return
        self._soft_op_running = True
        self._soft_gesture_shown = True
        display = self._soft_gesture or self._soft
        weights = self._smooth_plan.weights if display.bands_visible else None
        self._soft_show(weights, display.view_mode)

    def _smooth_soft_live(self) -> bool:
        """A held Smooth / Relax with Soft on (armed or dragging): the wheel steps its radius."""
        return (
            self._transform_command in _SMOOTH_COMMANDS
            and self._smooth_plan is not None
            and self._smooth_plan.weights is not None
            and self._soft_gesture is not None
        )

    def _smooth_reweight(self, gesture: SoftSettings) -> set[VertexId]:
        """New radius / flow for the held Smooth / Relax: back to the press geometry (only the movable
        vertices were written), the influence and plan again from there, the current strength replayed.
        Returns the vertices whose position may have changed."""
        mesh = self.scene.mesh
        old = self._smooth_plan
        if self._transform_begun:
            for vid in old.movable:
                mesh.set_vertex_position(vid, old.start[vid])
        try:
            weights = self._smooth_soft_weights(self._smooth_seeds, gesture)
            plan = plan_smooth(
                mesh, self._smooth_seeds, relax=old.relax, weights=weights, mask=self._mask_values()
            )
        except (SmoothRefused, SoftSymmetryRefusal):
            plan = old  # the seeds did not change: keep the field it had
        self._smooth_plan = plan
        self._transform_target = plan.movable
        if self._transform_begun:
            self._smooth_write(self._smooth_amount)
        return set(old.movable) | set(plan.movable)

    def _smooth_write(self, amount: float) -> set[VertexId]:
        positions = self._smooth_plan.positions(amount)
        mesh = self.scene.mesh
        for vid, position in positions.items():
            mesh.set_vertex_position(vid, position)
        return set(positions)

    def _smooth_step(self, dx: float) -> bool:
        """Every motion recomputes the positions from the press state (no drift): right = more steps,
        left = fewer, down to the start state. Journal from the first motion (as Loop Slide)."""
        plan = self._smooth_plan
        if plan is None or dx == 0:
            return False
        mesh = self.scene.mesh
        if not self._transform_begun:
            self._smooth_before = mesh.begin_change()
            self._smooth_selection_before = self._selection_snapshot()
            self._transform_begun = True
        self._smooth_amount = max(0.0, self._smooth_amount + dx / SMOOTH_PX_PER_STEP)
        moved = self._smooth_write(self._smooth_amount)
        self._pick_cache.invalidate()
        self.viewport.on_vertices_moved(moved)
        self._set_status(f"{plan.label}: strength {self._smooth_amount:.2f} steps")
        return True

    def _smooth_release(self) -> None:
        """Release: a drag commits its journal as one entry; a tap (no motion) is one fixed step
        (`TAP_AMOUNT`) through the one commit boundary."""
        plan = self._smooth_plan
        if plan is None:
            return
        mesh = self.scene.mesh
        if not self._transform_begun:
            changed = self._mesh_transaction(
                plan.label,
                lambda _mesh: self._smooth_write(SMOOTH_TAP_AMOUNT),
                moved_of=lambda moved: moved,
            ).changed
            self._set_status(f"{plan.label}: one step" if changed else f"{plan.label}: no change")
            return
        before, self._smooth_before = self._smooth_before, None
        delta = mesh.end_change(before)
        if delta.empty:
            self._set_status(f"{plan.label}: no change")
            return
        self.history.push(MeshDeltaCommand(mesh=mesh, delta=delta, description=plan.label))
        self._record_selection_history(self._smooth_selection_before)
        self._soft_preview_refresh()
        self._set_status(f"{plan.label} committed ({self._smooth_amount:.2f} steps)")

    def _smooth_abort(self) -> None:
        before, self._smooth_before = self._smooth_before, None
        if before is None or self._smooth_plan is None:
            return
        self.scene.mesh.rollback_change(before)
        self._pick_cache.invalidate()
        if self.viewport is not None:
            self.viewport.on_vertices_moved(set(self._smooth_plan.movable))

    # -- Delete / Dissolve (WP Delete/Dissolve) ----------------------------------

    def _removal_command(self, command: str) -> bool:
        """Entf / Rücktaste / Ctrl+Rücktaste on the selection of the active
        component mode (`mirai.topology.delete_dissolve`). Exactly one
        `MeshDeltaCommand` per success, mesh and history untouched on refusal
        or no-op. Residue (first default, refinement is material for the
        practice check): Face Dissolve selects the merged faces, everything
        else clears the selection; the mode stays.

        With a symmetry definition set and the command declared
        (`symmetry_declarations.REMOVAL_COORDINATORS`, AD-SYM-03 slice 3c) the
        coordinator runs the removal on the selection and its partners inside
        the same single transaction, in MARK as in BLOCK; a `SymmetryRefusal`
        posts its text, records no history entry and leaves mesh and selection
        untouched. Under symmetry Face Dissolve selects the merged faces on the
        side(s) where the live selection had faces (`residue_sides`, engineering
        default). Without a definition the unchanged `apply_removal` runs."""
        selection = self.selection
        mode = selection.mode
        ids = {
            SelectionMode.VERTEX: selection.vertices,
            SelectionMode.EDGE: selection.edges,
            SelectionMode.FACE: selection.faces,
        }.get(mode)
        dissolve, cleanup = _REMOVAL_COMMANDS[command]
        if not ids:
            verb = "Dissolve" if dissolve else "Delete"
            self._set_status(f"{verb}: nothing selected")
            return False
        label = removal_label(mode, dissolve=dissolve, cleanup=cleanup)
        if command == commands.DISSOLVE_NO_CLEANUP and mode is SelectionMode.VERTEX:
            # §0.2.2: Vertex Dissolve has no variant, so this command does nothing.
            self._set_status("Dissolve (no cleanup): no variant in Vertex mode")
            return False

        mesh = self.scene.mesh
        coordinator = (
            symmetry_declarations.REMOVAL_COORDINATORS.get(command)
            if mesh.symmetry_definition is not None
            else None
        )
        sides = (
            residue_sides(mesh, selection.faces, mesh.face_vertices)
            if coordinator is not None and dissolve and mode is SelectionMode.FACE
            else None
        )

        def mutate(mesh) -> list[FaceId]:
            if coordinator is not None:
                return coordinator(mesh, mode, set(ids))
            return apply_removal(mesh, mode, set(ids), dissolve=dissolve, cleanup=cleanup)

        def residue(new_faces) -> None:
            selection.clear()
            if dissolve and mode is SelectionMode.FACE:
                kept = set(new_faces)
                if sides is not None:
                    kept = on_residue_sides(mesh, kept, sides, mesh.face_vertices)
                selection.add(kept)

        try:
            outcome = self._mesh_transaction(label, mutate, on_applied=residue)
        except RemovalRefused as exc:
            self._set_status(f"{label}: {exc}")
            return False
        except SymmetryRefusal as exc:
            self._set_status(str(exc))
            return False
        if not outcome.changed:
            self._set_status(f"{label}: nothing to do")
            return False
        self._set_status(label)
        return True

    # -- Collapse (WP Toolbox Gaps B1) --------------------------------------------

    def _collapse_command(self) -> bool:
        """Shift+C on the selection of the active component mode (`mirai.topology.collapse`):
        each connected group (over selected edges, the edges of selected faces, or in vertex mode
        the edges between two selected vertices) falls into one point at its centroid; a vertex
        without such an edge stays. Exactly one `MeshDeltaCommand` per success, mesh and history
        untouched on refusal or no-op. Residue (P-4, `PROVISIONAL`): the resulting vertices,
        mode switches to Vertex.

        With a symmetry definition set and the command declared
        (`symmetry_declarations.COLLAPSE_COORDINATORS`) the coordinator runs on the selection and
        its partners inside the same single transaction; a `SymmetryRefusal` posts its text and
        changes nothing. Under symmetry the residue keeps the result vertices on the side(s) where
        the live selection was (`residue_sides`, as Split), vertices on the plane always stay."""
        selection = self.selection
        mode = selection.mode
        ids = {
            SelectionMode.VERTEX: selection.vertices,
            SelectionMode.EDGE: selection.edges,
            SelectionMode.FACE: selection.faces,
        }.get(mode)
        if not ids:
            self._set_status(f"{COLLAPSE_LABEL}: nothing selected")
            return False

        mesh = self.scene.mesh
        coordinator = (
            symmetry_declarations.COLLAPSE_COORDINATORS.get(commands.COLLAPSE)
            if mesh.symmetry_definition is not None
            else None
        )
        sides = None
        if coordinator is not None:
            vertices_of = {
                SelectionMode.VERTEX: lambda v: (v,),
                SelectionMode.EDGE: mesh.edge_vertices,
                SelectionMode.FACE: mesh.face_vertices,
            }[mode]
            sides = residue_sides(mesh, ids, vertices_of)

        def mutate(mesh) -> list[VertexId]:
            if coordinator is not None:
                return coordinator(mesh, mode, set(ids))
            return apply_collapse(mesh, mode, set(ids))

        def residue(survivors) -> None:
            kept = {v for v in survivors if mesh.is_valid_vertex(v)}
            if sides is not None:
                kept = on_residue_sides(mesh, kept, sides, lambda v: (v,))
            selection.clear()
            selection.mode = SelectionMode.VERTEX
            selection.add(kept)
            if self.viewport is not None:
                self.viewport.on_selection_changed()

        try:
            outcome = self._mesh_transaction(COLLAPSE_LABEL, mutate, on_applied=residue)
        except CollapseRefused as exc:
            self._set_status(f"{COLLAPSE_LABEL}: {exc}")
            return False
        except SymmetryRefusal as exc:
            self._set_status(str(exc))
            return False
        if not outcome.changed:
            self._set_status(f"{COLLAPSE_LABEL}: nothing to do (no selected edge joins two points)")
            return False
        self._set_status(f"{COLLAPSE_LABEL}: {len(outcome.result)} point(s)")
        return True

    def _notify_topology_changed(self) -> None:
        """Meldet dem Viewport eine Topologie-Änderung und richtet den Hover
        neu aus.

        Grund (WP-06 B6 fix, gefunden im Praxistest `C` → Split): Split und
        Connect entfernen die Edge-IDs, die sie ersetzen. War eine davon
        gehovert (oder selektiert), zeigt `selection.hovered` danach auf ein
        Element, das es nicht mehr gibt — im Praxistest crashte genau das den
        Draw-Loop (`KeyError: EdgeId(11)` in `mesh.edge_vertices`, siehe
        `viewport/overlay.py`). `_refresh_hover()` pickt am ruhenden Cursor im
        dann aktuellen Modus neu — dasselbe Muster wie nach Undo/Redo
        (`_undo_redo`). Ist kein Cursor bekannt, bleibt `selection.hovered`
        bewusst unangetastet; der Viewport überspringt die stale ID beim
        Aufbau der Overlays (AD-001: Gültigkeit wird über
        `mesh.is_valid_*()` geprüft, nie über die ID selbst).
        """
        self._pick_cache.invalidate()
        if self.viewport is not None:
            self.viewport.on_topology_changed()
        self._soft_preview_refresh()
        self._refresh_hover()

    # -- Knife session (WP-06 B7 / B7.1, AD-017) ---------------------------------
    #
    # Click-only interaction (Artist decision Manu 2026-09-28, after the B7
    # window test: press -> slide -> release was redundant with the live hover
    # preview, which already slides along the edge while hovering) = Playground
    # Variant A only: hover preview, a click cuts at the previewed position,
    # start highlight, and a line preview from the start to the prospective
    # point. Session engine, in-session history, commit/cancel and residue are
    # `KnifeTool`'s (AD-017 DECIDED); this section only routes input and builds
    # render data. Blender-style drag cutting (Variant B / F1 edge lock) is a
    # possible Knife V2 idea — not built, not prepared; the Playground's own
    # Variant B (`project_locked_edge` in `mirai.topology.knife_pick`) is
    # unaffected (AD-013 A2, contextual deviation).
    #
    # WP-KNIFE-01 S2 (KEEP 2026-10-01): a click adds a point to the session's
    # virtual path; the mesh is cut at commit (`Enter`). The
    # session is drawn from the path (`knife_render_data`), so neither the
    # mesh nor the pick cache changes while clicking.
    #
    # WP-KNIFE-01 S3 (PROVISIONAL): a click inside a face is a point too
    # (`knife_pick` face hit, the session's own interior points snap); the
    # status line names the S3 refusals and closes, and at commit what the
    # resolver joined or dropped (`_knife_notes`).
    #
    # WP-KNIFE-01 UX2 (PROVISIONAL, Artist 2026-10-02): `E` / an RMB click
    # lift the pen (the chain ends, nothing is committed), a double-click
    # closes the chain and lifts; a click outside the mesh does nothing (S4:
    # it is a point in space now, below); Shift+click on an edge places the
    # point at its midpoint.
    #
    # WP-KNIFE-01 UX2b (PROVISIONAL, Artist 2026-10-02): while Shift is held
    # (`set_shift_held`, from the window) the hover already shows that midpoint.
    #
    # WP-KNIFE-01 S4 (PROVISIONAL): the live camera, viewport size, pick cache and
    # occlusion switch go to the `KnifeTool` at hover and click time, so a far
    # click is planned across faces with the camera of that click (crossing dots
    # while hovering). A click outside the mesh is a point in space and cuts
    # (Manu 2026-10-02, Blender); the hover line runs to the cursor over empty
    # space, after the click only the cuts commit will make are drawn.

    @property
    def knife_active(self) -> bool:
        """A Knife session is running (`C` with an empty selection)."""
        return self._knife is not None

    @property
    def knife_render_data(self) -> KnifeRenderData | None:
        """What the running session shows (headless), None without a session."""
        if self._knife is None:
            return None
        data = build_knife_render_data(
            self.scene.mesh,
            [_KNIFE_DRAWN_LIFT if p.get("reason") == "lift" else p for p in self._knife.path],
            self._knife_target,
            self._knife_highlight_edge,
            self._knife_hover_crossings,
            symmetry=self._knife_view,
            refused=self._knife_refused,
            pen_up=self._knife_view is not None and self._knife.last_point is None,
        )
        if self._knife_view is None and self._knife.last_point is None:
            # After a pen lift no point starts the next segment: no start marker, no rubber band.
            data = dataclasses.replace(data, start_point=None, line_preview=None)
        return data

    def _knife_begin(self) -> bool:
        if self.viewport is None:
            return False
        # AD-SYM-03 slice 6c: whenever a symmetry definition is set the session runs the declared
        # coordinator (`mirai.symmetry_declarations`, D-b - the declaration is the only switch) and
        # gets the session view that previews and refuses with the commit's own rules. A plane the
        # coordinator cannot handle starts no session at all.
        coordinator = self._connect_coordinator(CContext.KNIFE)
        view = None
        if coordinator is not None:
            try:
                view = SymmetricKnifeView(self.scene.mesh)
            except KnifeRefusal as exc:
                self._set_status(str(exc))
                return False
        self._knife_selection_before = self._selection_snapshot()
        knife = KnifeTool()
        knife.activate()
        knife.begin(mesh=self.scene.mesh, scene=self.scene, selection=self.selection,
                    **({} if view is None else {"symmetric_commit": coordinator, "symmetric_view": view}))
        self._knife = knife
        self._knife_view = view
        self._knife_refused = None
        self._knife_refused_text = None
        # R-SEL-2 (as in the Playground): the Knife draws its own preview, the
        # selection hover must not stay drawn underneath it.
        self._set_hovered(None)
        self._refresh_hover()
        self._set_status(
            "Knife: click on vertices, edges, inside faces or outside the mesh to cut - a far click cuts"
            " across faces, Shift+click = edge midpoint, E / right-click = new cut (pen lift),"
            " double-click = close + lift, Enter = commit, Esc = cancel, Ctrl+Z / Ctrl+Y = undo / redo"
            + ("" if view is None else f" - {self._knife_mirror_text()}")
        )
        return True

    def _knife_mirror_text(self) -> str:
        """The symmetric session's note in the status line: the active mirror preview variant and its key."""
        variant = self.knife_mirror_variant
        return (f"Spiegelvorschau {variant} ({KNIFE_MIRROR_VARIANT_LABELS[variant]}), "
                f"Taste {KNIFE_MIRROR_VARIANT_KEY.upper()} wechselt V-a / V-b / V-c")

    def _knife_say(self, message: str) -> None:
        """A Knife status message; a symmetric session names its mirror preview variant in it."""
        if self._knife_view is not None:
            message += f" [Spiegel {self.knife_mirror_variant}]"
        self._set_status(message)

    def _knife_cycle_variant(self) -> bool:
        """The provisional variant key: V-a -> V-b -> V-c -> V-a (symmetric session only)."""
        order = KNIFE_MIRROR_VARIANTS
        self.knife_mirror_variant = order[(order.index(self.knife_mirror_variant) + 1) % len(order)]
        self._knife_sync_overlay()
        self._set_status(f"Knife: {self._knife_mirror_text()}")
        return True

    def _knife_key(self, input: Input) -> bool:
        """Session Gate: only commit, cancel, the pen lift and the in-session
        Undo/Redo pass; every other key (W/R, 1/2/3, D/Shift+D, C, X/Y/Z, ...)
        is ignored."""
        command = self.bindings.command_for(input, KNIFE_CONTEXT)
        self._knife_last_click = None     # a key between two clicks is no double-click
        if (command is None and self._knife_view is not None and input.kind == "key"
                and input.value == KNIFE_MIRROR_VARIANT_KEY and not input.modifiers):
            return self._knife_cycle_variant()
        if command == commands.CANCEL:
            return self._knife_end(commit=False)
        if command == commands.KNIFE_COMMIT:
            return self._knife_end(commit=True)
        if command == commands.KNIFE_LIFT:
            return False if self._knife_gesture else self._knife_lift()
        if command in (commands.UNDO, commands.REDO):
            return self._knife_history_step(command)
        return False

    def _knife_owns_press(self, input: Input) -> bool:
        # The unmodified and the Shift-only LMB (midpoint snap, UX2 D11) are the
        # Knife's, and a button bound to KnifeLift (RMB); Alt+LMB (orbit / pan),
        # Ctrl+LMB and the other buttons keep going through the pointer gestures.
        if input.kind != "mouse" or self.pointer.active or self._knife_gesture:
            return False
        if input.value == "LEFT" and input.modifiers <= {"shift"}:
            return True
        return self.bindings.command_for(input, KNIFE_CONTEXT) == commands.KNIFE_LIFT

    def _knife_press(self, input: Input) -> None:
        """Press: only starts the click-threshold gesture (B7.1); the preview
        is recomputed with the press's own Shift (the click decides by the
        press modifiers, AD-019) - with a held Shift the hover showed the same
        midpoint already (UX2b)."""
        self._knife_gesture = True
        self._knife_gesture_moved = 0.0
        self._knife_gesture_button = input.value
        self._knife_gesture_midpoint = input.value == "LEFT" and "shift" in input.modifiers
        if self._cursor is None or input.value != "LEFT":
            return
        self._knife_set_preview(self._knife_pick(*self._cursor, midpoint=self._knife_gesture_midpoint))

    def _knife_drag(self, dx: float, dy: float) -> bool:
        """LMB held and moved: only tracks distance for the click threshold
        (B7.1, no slide) - a drag past the threshold neither locks nor cuts."""
        self._knife_gesture_moved += abs(dx) + abs(dy)
        return False

    def _knife_release(self, x: float, y: float) -> bool:
        """Release: press+release under the click threshold is a click - LMB
        adds the point at the cursor, the second LMB click of a double-click
        finishes the chain, an RMB click lifts the pen; a press that moved past
        the threshold is not a click and does nothing (Playground click rule,
        B7.1). A click outside the mesh adds a point in space (S4); it never
        commits."""
        moved = self._knife_gesture_moved
        self._knife_gesture = False
        self._knife_gesture_moved = 0.0
        last, self._knife_last_click = self._knife_last_click, None
        if moved >= CLICK_THRESHOLD_PX:
            self._refresh_hover()
            return False
        if self._knife_gesture_button != "LEFT":
            return self._knife_lift()
        now = self.knife_clock()
        if (
            last is not None
            and now - last[0] <= KNIFE_DOUBLE_CLICK_S
            and math.hypot(x - last[1], y - last[2]) <= KNIFE_DOUBLE_CLICK_PX
            and self._knife.plan_lift(close=True).ok
        ):
            return self._knife_lift(finish=True)
        target = self._knife_pick(x, y, midpoint=self._knife_gesture_midpoint)
        self._knife_last_click = (now, x, y)
        if not self._knife.click(target):
            plan = self._knife.last_plan
            # A symmetric refusal (F3 = A) carries its own status text; the click was ignored.
            self._set_status(plan.reason if plan.refused
                             else _KNIFE_REFUSED.get(plan.reason, "Knife: no valid cut target here"))
            self._refresh_hover()
            return False
        # WP-KNIFE-01 S2: a click only adds a point to the session's path - the
        # mesh (and with it the pick cache) is unchanged until commit.
        plan = self._knife.last_plan
        cuts = len(self._knife.cut_segments)
        segments = f"{cuts} path {'segment' if cuts == 1 else 'segments'}"
        crossings = f"{len(plan.crossings)} crossing(s)" if plan.crossings else "the line crosses nothing"
        if plan.start:
            where = " on an earlier point" if plan.earlier else " in space" if target["kind"] == "space" else ""
            status = "Knife: start point set" + where
        elif plan.closing:
            status = f"Knife: shape closed - the next click cuts on from its start ({segments})"
        elif plan.skip:
            status = f"Knife: along an existing edge - nothing to cut ({segments})"
        elif target["kind"] == "space":
            status = f"Knife: point in space - {crossings} ({segments})"
        elif plan.method:
            status = f"Knife: cut across {crossings} ({segments})"
        else:
            status = f"Knife: cut ({segments})"
        self._knife_say("; ".join([status] + _knife_plan_notes(plan)))
        self._refresh_hover()
        return True

    def _knife_lift(self, finish: bool = False) -> bool:
        """Pen lift (`E` / RMB click), or close + lift (`finish`, the double-click): the
        chain ends, nothing is committed, the next click starts a new chain (UX2)."""
        knife = self._knife
        self._knife_set_view()   # the close may run across faces (S4)
        if not (knife.finish_chain() if finish else knife.lift()):
            self._set_status("Knife: nothing to lift")
            return False
        plan = knife.last_plan
        what = "shape closed, pen lifted" if plan.closing or plan.replaces else plan.reason
        self._knife_say(f"Knife: {what} - the next click starts a new cut")
        self._refresh_hover()
        return True

    def _knife_history_step(self, command: str) -> bool:
        """In-session Undo/Redo (AD-017 DECIDED): only the session's own steps,
        never the global history. Ignored while the Knife's LMB is held."""
        if self._knife_gesture:
            return False
        undo = command == commands.UNDO
        done = self._knife.undo_step() if undo else self._knife.redo_step()
        if not done:
            self._set_status(f"Knife: nothing to {'undo' if undo else 'redo'}")
            return False
        self._knife_say("Knife: last cut undone" if undo else "Knife: cut redone")
        self._refresh_hover()
        return True

    def _knife_end(self, commit: bool) -> bool:
        """Enter = commit (exactly one history entry, residue = path edges
        selected, Edge mode); Esc = cancel (mesh, selection and history exactly
        as before the session)."""
        knife = self._knife
        before = self._knife_selection_before
        if commit:
            command = knife.commit()
        else:
            knife.cancel()
            command = None
        knife.deactivate()
        self._knife = None
        self._knife_selection_before = None
        self._knife_gesture = False
        self._knife_gesture_moved = 0.0
        self._knife_last_click = None
        self._knife_target = None
        self._knife_highlight_edge = None
        self._knife_hover_crossings = ()
        self._knife_view = None
        self._knife_refused = None
        self._knife_refused_text = None
        notes = _knife_notes(knife.last_resolution) if commit else []
        if command is not None:
            self._record_selection_history(before)
            count = len(self.selection.edges)
            status = f"Knife committed ({count} path {'edge' if count == 1 else 'edges'} selected)"
            res = knife.last_resolution
            if res is not None and res.applied < res.runs:
                # Valid while clicking, dropped at commit (the run would have
                # left its face) - the Q5 "N-1/N" note (WP-KNIFE-01 S2).
                status += f" - {res.runs - res.applied} of {res.runs} cuts dropped"
            self._set_status("; ".join([status] + notes))
        elif commit and knife.last_problem is not None:
            self._set_status(f"Knife: result taken back ({knife.last_problem}), nothing committed")
        elif commit:
            self._set_status("Knife: no cuts made, nothing committed" + (f" ({'; '.join(notes)})" if notes else ""))
        else:
            self._set_status("Knife cancelled")
        self._pick_cache.invalidate()
        self.viewport.set_tool_overlay()
        self.viewport.on_topology_changed()
        self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        self._refresh_hover()
        return True

    def set_shift_held(self, held: bool) -> bool:
        """The window reports whether any Shift key is held (WP-KNIFE-01 UX2b).
        During a Knife session the hover preview at the known cursor follows it
        at once (the midpoint before the click); without a session, a cursor or
        while a button is held it is only stored. True = the preview changed."""
        held = bool(held)
        if held == self._shift_held:
            return False
        self._shift_held = held
        if self._knife is None or self._knife_gesture or self._cursor is None or self.pointer.active:
            return False
        return self._knife_hover(*self._cursor)

    def _knife_hover(self, x: float, y: float) -> bool:
        return self._knife_set_preview(self._knife_pick(x, y, midpoint=self._shift_held))

    def _knife_pick(self, x: float, y: float, midpoint: bool = False) -> dict:
        """WP-06 B8: same cache/occlusion as `_pick()` - a hidden edge/vertex
        cannot be a Knife target while faces are shown. WP-KNIFE-01 S2: then
        the session's own edge points (`snap_own_point`) - a click on one
        reaches that point again, as the real-cut Knife's split vertex did.
        UX2 `midpoint` (Shift): an edge target moves to t = 0.5 - after the
        own-point snap, which wins - or to an own point already there.
        S4: the knife gets the live view first (the planner plans with the camera
        of this hover / click); outside the mesh the target is a point in space."""
        kwargs = {"cache": self._pick_cache, "occlusion": self.display.show_faces}
        size = (self.viewport_width, self.viewport_height)
        if self.display.show_faces:
            # One Knife pick runs several occlusion tests (vertex, edge, face, own points): build the
            # screen grid at once instead of after `GRID_AFTER_SCANS` whole-mesh scans.
            self._pick_cache.refresh(self._edit_camera, self.scene.mesh, *size)
            self._pick_cache.face_grid(self.scene.mesh, batch=True)
        target = knife_pick(self._edit_camera, self.scene.mesh, x, y, *size, **kwargs)
        if self._knife is None:
            return target
        self._knife_set_view()
        # Also over "outside": the real-cut Knife's split vertex was caught by the
        # 14 px vertex pick just off the silhouette too.
        target = snap_own_point(
            self._edit_camera, self.scene.mesh, x, y, *size, self._knife.snap_points, target, **kwargs
        )
        if target.get("kind") == "outside":
            return {"kind": "space", "position": space_point(self._edit_camera, x, y, *size)}
        if not midpoint or target.get("kind") != "edge":
            return target
        eid = target["edge_id"]
        own = next((p for p in self._knife.snap_points if p["kind"] == "edge" and p["edge_id"] == eid
                    and abs(p["t"] - 0.5) <= GEO_EPS), None)
        return {"kind": "point", "pid": own["pid"]} if own is not None else dict(target, t=0.5)

    def _knife_set_view(self) -> None:
        """The live camera for the planner (S4) - set before every hover / click plan."""
        self._knife.set_view(self._edit_camera, self.viewport_width, self.viewport_height,
                             cache=self._pick_cache, occlusion=self.display.show_faces)

    def _knife_set_preview(self, target: dict) -> bool:
        """Prospective target = `target` only if the click would be accepted
        (`KnifeTool.plan`, the same rules as `accepts`); invalid → no point, no
        line (`PROVISIONAL`); S4: with the segment's planned crossings.
        True = changed."""
        plan = self._knife.plan(target)
        prospective = target if plan.ok else None
        highlight = target["edge_id"] if plan.ok and target.get("kind") == "edge" else None
        crossings = tuple(tuple(c) for c in plan.crossings) if plan.ok else ()
        refused = target if plan.refused else None
        changed = (prospective, highlight, crossings, refused) != (
            self._knife_target, self._knife_highlight_edge, self._knife_hover_crossings, self._knife_refused)
        self._knife_target = prospective
        self._knife_highlight_edge = highlight
        self._knife_hover_crossings = crossings
        self._knife_refused = refused
        self._knife_refusal_status(plan.reason if plan.refused else None)
        self._knife_sync_overlay()
        return changed

    def _knife_refusal_status(self, text: str | None) -> None:
        """Hover refusal (F3 = A): the refused target's reason is shown while it is hovered - once, not on
        every mouse move - and the status returns to the session's note when the hover leaves it."""
        if text == self._knife_refused_text:
            return
        self._knife_refused_text = text
        self._set_status(text if text is not None else f"Knife: {self._knife_mirror_text()}")

    def _knife_clear_preview(self) -> bool:
        changed = (self._knife_target is not None or self._knife_highlight_edge is not None
                   or self._knife_refused is not None)
        self._knife_target = None
        self._knife_highlight_edge = None
        self._knife_hover_crossings = ()
        self._knife_refused = None
        self._knife_refusal_status(None)
        self._knife_sync_overlay()
        return changed

    def _knife_sync_overlay(self) -> None:
        """Knife render data → viewport tool layers: prospective point, target
        edge and line preview in the hover style, the placed points (the start
        among them) and the segments commit will cut in the selected style (no
        new look; WP-KNIFE-01 S2: drawn from the path, the mesh is not cut
        before commit).

        A symmetric session (slice 6c) adds the layers of the mirror, of the part that will not be cut and
        of the refused hover (`knife_render_data`'s fields; the mirror per variant, `KNIFE_MIRROR_VARIANTS`).
        Without a symmetry view only the two layers above are passed, exactly as before."""
        data = self.knife_render_data
        if self.viewport is None or data is None:
            return
        points = {
            TOOL_PREVIEW_LAYER: [p for p in (data.prospective_point,) if p is not None]
            + list(data.prospective_crossings),
            TOOL_ACTIVE_LAYER: list(data.placed_points),
        }
        segments = {
            TOOL_PREVIEW_LAYER: [
                s for s in (data.target_edge, data.line_preview) if s is not None
            ],
            TOOL_ACTIVE_LAYER: list(data.path_segments),
        }
        if self._knife_view is not None:
            mirror_points = list(data.mirror_placed_points)
            mirror_hover_points = [p for p in (data.mirror_prospective_point,) if p is not None] + list(
                data.mirror_prospective_crossings)
            mirror_path = list(data.mirror_path_segments)
            mirror_hover = [s for s in (data.mirror_target_edge, data.mirror_line_preview) if s is not None]
            variant = self.knife_mirror_variant
            if variant == "V-a":       # like the working side's own preview
                points[TOOL_MIRROR_LAYER] = mirror_points
                points[TOOL_MIRROR_PREVIEW_LAYER] = mirror_hover_points
                segments[TOOL_MIRROR_LAYER] = mirror_path
                segments[TOOL_MIRROR_PREVIEW_LAYER] = mirror_hover
            elif variant == "V-b":     # always visible, dimmed
                points[TOOL_MIRROR_DIM_LAYER] = mirror_points + mirror_hover_points
                segments[TOOL_MIRROR_DIM_LAYER] = mirror_path + mirror_hover
            else:                      # V-c: the mirror's points only
                points[TOOL_MIRROR_LAYER] = mirror_points + mirror_hover_points
            points[TOOL_CLIPPED_LAYER] = list(data.clipped_points) + list(data.clipped_hover_points)
            segments[TOOL_CLIPPED_LAYER] = list(data.clipped_segments) + list(data.clipped_hover_segments)
            points[TOOL_REFUSED_LAYER] = list(data.refused_points)
            segments[TOOL_REFUSED_LAYER] = list(data.refused_segments)
        self.viewport.set_tool_overlay(points=points, segments=segments)

    # -- Display (WP-06 B5a) ----------------------------------------------------

    def _display_command(self, command: str) -> bool:
        if command == commands.TOGGLE_REFERENCE_GHOST:
            self.reference_ghost = not self.reference_ghost
            self._sync_object_views()
            self._set_status(f"References: {'ghost' if self.reference_ghost else 'shaded'}")
            return True
        if command == commands.TOGGLE_REGION_TINT:
            self.display.toggle_region_tint()
            self._apply_display()
            self._set_status(f"Region colours: {'on' if self.display.region_tint else 'off'}")
            return True
        if command in (commands.CYCLE_LIGHT_PRESET, commands.TOGGLE_LIGHT_SPACE):
            if command == commands.CYCLE_LIGHT_PRESET:
                self.display.cycle_light_preset()
            else:
                self.display.toggle_light_space()
            self._apply_display()
            self._set_status(f"Light: {self.display.light_label}")
            return True
        if (
            command == commands.TOGGLE_WIREFRAME_OVERLAY
            and self.subdivision.enabled
            and self.display.show_faces
        ):
            # SubD view (Manu 2026-10-23, option A): Shift+D shows / hides the preview's cage or
            # isolines instead of the wire overlay (which the preview replaces while it is on).
            self.subdivision.toggle_lines()
            return True
        if command == commands.CYCLE_DISPLAY_MODE:
            self.display.cycle()
        elif command == commands.TOGGLE_WIREFRAME_OVERLAY:
            self.display.toggle_wireframe_overlay()
        else:
            self.display.set_mode(_SET_DISPLAY_MODES[command])
        self._apply_display()
        self._set_status(f"Display: {self.display.label}")
        return True

    # -- Worklight and Look rows (AD-024 §8, `PROVISIONAL`) ------------------------------

    def set_light(self, **changes) -> bool:
        """The edit path of the Worklight (keys now, the GUI later): any `LightRig` field, clamped to
        the Shading Lab's ranges (`DisplayState.set_light`). View state - no Undo step, not saved. True
        = the light changed; the viewport gets it at once (a uniform update at draw time, AD-018)."""
        before = self.display.light_rig
        if self.display.set_light(**changes) == before:
            return False
        if self.viewport is not None:
            self.viewport.set_light(self.display.light_rig)
        return True

    def step_light(self, row_id: str, direction: int, fine: bool = False) -> bool:
        """One value step of the Look row `row_id` (`look_controls.LIGHT_ROWS`, the Lab's steps);
        `direction` -1 / +1. A row that does not apply (fill off / coupled) is refused with a status
        line. True = the light changed."""
        row = light_row(row_id)
        rig = self.display.light_rig
        if not row.applies(rig):
            self._set_status(f"Light: {row.label} inaktiv - {row.inactive_reason}")
            return False
        stepped = row.step(rig, direction, fine)
        changed = self.set_light(
            **{name: value for name, value in stepped.to_dict().items() if getattr(rig, name) != value}
        )
        suffix = "" if changed else " (Grenze)"
        self._set_status(f"Light: {row.label} {row.format(self.display.light_rig)}{suffix}")
        return changed

    # -- Object material (AD-024 §6/§7, `PROVISIONAL` keys) ----------------------------------

    def _material_preview(self) -> SceneObject | None:
        """The object whose values the Look row shows (no status line): the edit object in `1/2/3`,
        the first selected non-Reference in `4` (None = none)."""
        scene = self.scene
        if self.selection.mode is not SelectionMode.OBJECT:
            return scene.edit_object
        for oid in sorted(self.selection.objects):
            obj = scene.objects.get(oid)
            if obj is not None and obj.state is not ObjectState.REFERENCE:
                return obj
        return None

    def _material_targets(self, label: str) -> tuple[list[SceneObject], tuple[str, ...]] | None:
        """AD-024 §6: the selected objects in `4` (References skipped - locked, Q-M3), the edit object in
        `1/2/3`. None (refusal posted) while an interaction owns the keys or nothing can be edited."""
        owner = self.interaction_owner
        if owner is not None or self._drag_select is not None:
            self._set_status(f"{label}: not while the {owner or 'selection'} interaction runs")
            return None
        if self.selection.mode is SelectionMode.OBJECT:
            return self._object_targets(label, "or press 1/2/3 for the edited object")
        return [self.scene.edit_object], ()

    def _commit_materials(self, changes: list) -> bool:
        """One Undo step for `(obj, before, after)` (unchanged ones dropped) and the view; the caller
        posts the status line. True = something changed."""
        changes = [(obj, before, after) for obj, before, after in changes if before != after]
        if not changes:
            return False
        before = self._selection_snapshot()
        for obj, _, after in changes:
            obj.material = after
        names = ", ".join(repr(obj.name) for obj, _, _ in changes)
        self.history.push(ObjectMaterialCommand(changes, f"Material {names}"))
        self._record_selection_history(before, mesh_step=False)
        self._sync_object_views()
        return True

    def set_object_material(self, **changes) -> bool:
        """The edit path of the object material (keys now, the GUI later): any of `base_color`,
        `specular`, `glossiness`, clamped to [0, 1], set on every target (`_material_targets`); one Undo
        step. True = a material changed. An object without a material starts from the default look."""
        values = clamp_material_values(changes)
        picked = self._material_targets("Material")
        if picked is None:
            return False
        targets, references = picked
        default = self.display.surface_finish
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
        self._set_status(
            ("Material set" if changed else "Material unchanged") + self._object_references_note(references)
        )
        return changed

    def step_object_material(self, row_id: str, direction: int, fine: bool = False) -> bool:
        """One value step of the material row `row_id` on every target, each from its own values
        (`look_controls.MATERIAL_ROWS`); one Undo step. True = a material changed."""
        row = material_row(row_id)
        picked = self._material_targets(row.label)
        if picked is None:
            return False
        targets, references = picked
        default = self.display.surface_finish
        planned = []
        for obj in targets:
            current = editable_material(obj, default)
            if row.applies(current):
                planned.append((obj, obj.material, row.step(current, direction, fine)))
        if not planned:
            self._set_status(f"{row.label} inaktiv - {row.inactive_reason}")
            return False
        changed = self._commit_materials(planned)
        shown = editable_material(planned[0][0], default)
        suffix = "" if changed else " (Grenze)"
        names = ", ".join(repr(obj.name) for obj, _, _ in planned)
        self._set_status(
            f"{row.label} {row.format(shown)}{suffix} - {names}" + self._object_references_note(references)
        )
        return changed

    # -- Look rows (AD-024 §6/§8) ------------------------------------------------------------

    @property
    def look_row(self) -> LookRow | MaterialRow:
        """The row the arrow keys edit."""
        return LOOK_ROWS[self._look_row_index]

    @property
    def look_text(self) -> str:
        """The active row and its value (HUD, status line). A material row shows the object it reads."""
        row = self.look_row
        if isinstance(row, MaterialRow):
            obj = self._material_preview()
            if obj is None:
                return f"{row.label} (kein Objekt gewählt)"
            values = editable_material(obj, self.display.surface_finish)
            text = f"{row.label} {row.format(values)} ({obj.name})"
            return text if row.applies(values) else f"{text} (inaktiv)"
        rig = self.display.light_rig
        text = f"{row.label} {row.format(rig)}"
        return text if row.applies(rig) else f"{text} (inaktiv)"

    def _look_command(self, command: str) -> bool:
        if command in (commands.LOOK_ROW_PREV, commands.LOOK_ROW_NEXT):
            step = -1 if command == commands.LOOK_ROW_PREV else 1
            self._look_row_index = (self._look_row_index + step) % len(LOOK_ROWS)
            self._set_status(f"Look: {self.look_text}")
            return True
        direction = -1 if command in (commands.LOOK_VALUE_DEC, commands.LOOK_VALUE_DEC_FINE) else 1
        fine = command in (commands.LOOK_VALUE_DEC_FINE, commands.LOOK_VALUE_INC_FINE)
        row = self.look_row
        if isinstance(row, MaterialRow):
            return self.step_object_material(row.id, direction, fine)
        return self.step_light(row.id, direction, fine)

    def _subd_command(self, command: str) -> bool:
        """SubD preview keys (2026-10-23, `mirai.subdivision`, `PROVISIONAL`): view state only - no
        mesh change, no History, no Undo step. Refused visibly while an interaction owns the keys
        (W/E/R/T/G, a drag selection, the Knife): a running gesture keeps the view it began with."""
        owner = self.interaction_owner
        if owner is not None or self._drag_select is not None:
            self._set_status(f"SubD: ignoriert — {owner or 'Auswahl'} läuft")
            return False
        return self.subdivision.run(command)

    def _apply_display(self) -> None:
        """E36: `DisplayState` → Grundwerte für `Viewport.set_display` (der
        Viewport kennt kein `DisplayState`). WP-06 B8: the pick cache's
        occlusion pre-filter depends on `show_faces` - invalidated on every
        display-mode change, including the initial one from `init_scene()`."""
        self._pick_cache.invalidate()
        if self.viewport is None:
            return
        self.viewport.set_display(
            show_faces=self.display.show_faces,
            show_edges=self.display.show_edges,
            flat=self.display.mode is DisplayMode.FLAT_SHADED,
        )
        self.viewport.set_region_tint(self.display.region_tint)
        self.viewport.set_light(self.display.light_rig)
        if self.viewport.set_surface_finish(self.display.surface_finish):
            # The global finish resets every entry; the objects' own materials go back on (AD-024 §4).
            self._sync_object_views()
        self.subdivision.set_faces_shown(self.display.show_faces)

    # -- Tasten (WP-06 B3) ------------------------------------------------------

    @property
    def move_armed(self) -> bool:
        """Move-Taste gehalten (scharf oder bereits laufend)."""
        return self._transform_command == commands.MOVE

    @property
    def move_interacting(self) -> bool:
        """Move läuft (erste Mausbewegung nach dem Scharfschalten erfolgt)."""
        return self.move_armed and self._transform_begun

    @property
    def move_target(self) -> frozenset[VertexId]:
        """Beim Scharfschalten fixierte Ziel-Vertices (leer = nicht scharf)."""
        return self._transform_target if self.move_armed else frozenset()

    @property
    def transform_command(self) -> str | None:
        """Scharf geschalteter Hold-Key-Transform (MOVE/ROTATE/SCALE, seit WP-06 B9
        auch EXTRUDE; None = keiner)."""
        return self._transform_command

    @property
    def transform_interacting(self) -> bool:
        """Der scharfe Transform läuft (erste Mausbewegung erfolgt)."""
        return self._transform_begun

    @property
    def transform_target(self) -> frozenset[VertexId]:
        """Beim Scharfschalten fixierte Ziel-Vertices (leer = nicht scharf)."""
        return self._transform_target

    @property
    def transform_space(self) -> str | None:
        """`space` der laufenden Geste, fix ab `begin()` (None = frei bzw.
        keine Geste)."""
        return self._transform_space

    @property
    def transform_orientation(self) -> str:
        """`world` or `normal` (WP Toolbox Gaps C1): the frame the axis constraints and the gizmo use."""
        return self._orientation

    @property
    def axis_constraint(self) -> str | None:
        """Sticky Achsen-/Ebenen-Constraint als `space`-String (None = frei)."""
        return self._axis_constraint

    @property
    def soft_settings(self) -> SoftSettings:
        """The sticky Soft Selection settings (immutable; `enabled` False = off)."""
        return self._soft

    @property
    def interaction_owner(self) -> str | None:
        """Which of `Application`'s own interactions owns the keys right now
        (AD-013 H2 addendum, H2-R2): `"transform"` while W/E/R (and, WP-06 B9, T =
        Extrude - the same hold-key family, no new value) is armed or running,
        `"knife"` during a Knife session, `"resymmetrize"` while the Re-Symmetrize
        preview is open (AD-SYM-04 A3), else None. Camera gestures
        (orbit, pan, zoom) own no keys and are never an owner."""
        if self._transform_command is not None:
            return "transform"
        if self._knife is not None:
            return "knife"
        if self._resym_plan is not None:
            return "resymmetrize"
        return None

    @property
    def hover_suspended(self) -> bool:
        """H2 (AD-013 H2 addendum, review CLAUDE-001 F3): while True the
        selection hover stays cleared on every hover path (motion, zoom, the
        refreshes after Undo/Redo, commit, cancel and `apply_mesh_change`),
        because they all go through `_update_hover`. The cursor is still
        tracked. Default False; `src/main.py` never sets it. The Knife hover
        is not affected. The app's own Re-Symmetrize preview pauses the hover
        without it (`_update_hover`)."""
        return self._hover_suspended

    @hover_suspended.setter
    def hover_suspended(self, value: bool) -> None:
        value = bool(value)
        if value == self._hover_suspended:
            return
        self._hover_suspended = value
        if value:
            self._set_hovered(None)
        else:
            # Re-pick at the last cursor, as after a zoom.
            self._refresh_hover()

    def key_press(self, input: Input) -> bool:
        """Taste gedrückt (`input.kind == "key"`), aufgelöst über die Bindings
        (GLOBAL; während einer Knife-Session zuerst KNIFE_CONTEXT). True = der
        Druck hat etwas bewirkt. Ein von `command_gate` abgelehntes Command
        (H2) postet den Ablehnungstext und gibt False zurück; die Knife-Session
        liegt davor und wird nie gegatet."""
        self.flush_hover()
        if self._knife is not None:
            return self._knife_key(input)
        if self._resym_plan is not None:
            return self._resymmetrize_key(input)
        command = self.bindings.command_for(input)
        if command is None:
            # The SubD keys (context "subd") only where the global context binds nothing.
            subd = self.bindings.command_for(input, SUBD_CONTEXT)
            if subd in SUBD_COMMANDS:
                command = subd
        if self._gate_refuses(command):
            return False
        if command in SUBD_COMMANDS:
            return self.dispatch_command(command)
        if self._object_mode_refuses(command):
            return False
        if command in _TOPOLOGY_COMMANDS and self._hidden_refuses(command):
            return False
        if self._drag_select is not None and command not in (commands.CANCEL, *_DISPLAY_COMMANDS, *_LOOK_COMMANDS):
            # A Box/Paint drag owns the selection until the LMB release (like a gesture).
            return False
        if command == commands.LASSO_ARM:
            return self._lasso_arm(input.value)
        if command == commands.LIGHT_DRAG:
            return self._light_drag_arm(input.value)
        if command in _TWEAK_TRANSFORMS:
            # Tweak (Ctrl+LMB drag) uses the last W/E/R pressed - a tap sets it ("tool set").
            self.tweak_command = command
        if command in _TRANSFORM_COMMANDS:
            return self._transform_arm(command, input.value)
        if command in _CONSTRAINT_SPACES:
            if self._transform_command in (commands.EXTRUDE, commands.LOOP_SLIDE, *_SMOOTH_COMMANDS):
                # Extrude is normal-only, Loop Slide runs along its edges: neither the gesture
                # nor the sticky state changes.
                return False
            return self._constrain(_CONSTRAINT_SPACES[command])
        if command == commands.TOGGLE_TRANSFORM_SPACE:
            return self._toggle_orientation()
        if command == commands.CANCEL:
            return self._cancel()
        if command in _DISPLAY_COMMANDS or command in _LOOK_COMMANDS:
            # Reine Darstellung: auch während eines Transforms erlaubt.
            return self.dispatch_command(command)
        if command in _SOFT_COMMANDS:
            # State only, like the constraints: allowed while W/E/R/T is held. It applies
            # to the next gesture - or to this one if it is armed and has not begun yet
            # (the settings are read at `begin()`, which is also where symmetric Soft
            # refuses the selections it does not define, AD-SYM-04 SS2).
            return self.dispatch_command(command)
        if command in _MODE_COMMANDS:
            # Kein Moduswechsel mitten in einer Geste (Playground Session Gate).
            if self._transform_key is not None:
                return False
            return self.dispatch_command(command)
        if command in _PLACEMENT_COMMANDS or command == commands.TOGGLE_REFERENCE:
            # AD-021 M2-3: not underneath a held W/E/R/T (same gate as C and the mode keys).
            if self._transform_key is not None:
                return False
            return self.dispatch_command(command)
        if (
            command in (commands.CONNECT, commands.COLLAPSE, commands.SYMMETRY_CYCLE, commands.RESYMMETRIZE)
            or command in _MASK_COMMANDS
            or command in _HIDE_COMMANDS
            or command in _REGION_COMMANDS
            or command in _REMOVAL_COMMANDS
            or command in _LOOP_COMMANDS
            or command in _SELECTION_STEP_COMMANDS
        ):
            # Wie die Modus-Tasten (B5b): C, Shift+C, Entf, Rücktaste, Shift+S, Alt+M und die Mask-Tasten werden
            # ignoriert, solange W/E/R scharf ist (Playground Session Gate;
            # Shift+S: AD-SYM-04 R-4, still wie C).
            if self._transform_key is not None:
                return False
            return self.dispatch_command(command)
        if command in (commands.UNDO, commands.REDO):
            # E23: während eines laufenden Transforms ignoriert; nur scharf →
            # erst entschärfen, dann ausführen.
            if self._transform_begun:
                return False
            if self._transform_key is not None:
                self._transform_end()
                self._refresh_hover()
            return self._undo_redo(command)
        return False

    def key_release(self, input: Input) -> bool:
        """Taste losgelassen. True = das Loslassen hat etwas bewirkt.

        Loslassen der Transform-Taste committet, wenn seit dem Scharfschalten
        eine Mausbewegung kam; ein bloßes Antippen entschärft nur (E21). Loslassen der
        Lasso-Taste beendet den Lasso-Modus (ein laufender Lasso-Drag läuft bis zum LMB-Release)."""
        if self._lasso_held is not None and input.value == self._lasso_held:
            self._lasso_held = None
            self._set_status("Lasso off")
            return True
        if self._light_drag_key is not None and input.value == self._light_drag_key:
            self._light_drag_key = None
            self._set_status(f"Light: {self.display.light_label}")
            return True
        if self._transform_key is None or input.value != self._transform_key:
            return False
        self._transform_finish()
        return True

    def _transform_finish(self) -> None:
        """End the armed/running hold gesture: commit after motion, else just disarm. The
        release of its key (`key_release`) or, for a Tweak, of the LMB (`pointer_release`)."""
        label, _, participle = _TRANSFORM_COMMANDS[self._transform_command]
        if self._object_gesture is not None:
            self._object_release()
        elif self._transform_command == commands.EXTRUDE:
            self._extrude_release()
        elif self._transform_command == commands.LOOP_SLIDE:
            self._slide_release()
        elif self._transform_command in _SMOOTH_COMMANDS:
            self._smooth_release()
        elif self._transform_begun:
            before = self._selection_snapshot()
            command = self.tool_manager.commit()
            if command is not None:
                # Move/Rotate/Scale never change the Selection itself, only
                # vertex positions — before and after are the same snapshot.
                self._record_selection_history(before)
            outcome = f"{label} committed" if command is not None else f"{label}: no change"
            self._set_status(outcome + self._constraint_suffix(self._transform_space))
        else:
            self._set_status(f"{label}: tool set (no motion, nothing {participle})")
        self._transform_end()
        self._refresh_hover()

    def _transform_arm(self, command: str, key: str) -> bool:
        """Transform scharf schalten (E21/E28): Ziel = aufgelöste Selection,
        sonst die Vertices des gehoverten Elements (Vertex/Edge/Face, B5b),
        sonst ablehnen. Tool aktiv, `begin()` erst bei Bewegung. Ist schon
        eine Transform-Taste gehalten, wird abgelehnt."""
        if self._transform_key is not None or self.viewport is None:
            return False
        if key == TWEAK_KEY:
            press = self._gizmo_press_xy or self._press_point or self._cursor
        else:
            press = self._cursor
        self._rotate_press = None if press is None else (float(press[0]), float(press[1]))
        self._rotate_virtual = self._rotate_press
        self._ctrl_snap_ok = not (self._ctrl_held and key == TWEAK_KEY and self._gizmo_gesture is None)
        if command == commands.EXTRUDE:
            return self._extrude_arm(key)
        if command == commands.LOOP_SLIDE:
            return self._slide_arm(key)
        if command in _SMOOTH_COMMANDS:
            return self._smooth_arm(command, key)
        if self.selection.mode is SelectionMode.OBJECT:
            return self._object_arm(command, key)
        label, verb, _ = _TRANSFORM_COMMANDS[command]
        selection = self.selection
        target = resolve_selection_vertices(self.scene.mesh, selection, selection.mode)
        hovered = selection.hovered
        from_hover = not target and hovered is not None
        if from_hover:
            target = _element_vertices(self.scene.mesh, hovered)
        if not target:
            noun = selection.mode.name.lower()
            self._set_status(f"{label}: nothing to {verb} (select or hover a {noun})")
            return False
        if not unblocked(target, self._mask_values()):
            self._set_status(f"{label}: all selected points are masked (Ctrl+M unmasks)")
            return False
        self.dispatch_command(command)
        self._transform_key = key
        self._transform_command = command
        self._transform_target = frozenset(target)
        self._transform_begun = False
        # Kein Hover-Highlight über dem, was gleich transformiert wird
        # (Playground WP-STAB-11 clear-on-arm).
        if from_hover or _active_selection_contains(selection, hovered):
            self._set_hovered(None)
        if from_hover:
            # F11: a hover-armed gesture shows its bands once, here (no preview from hover).
            self._soft_preview_refresh(shown_by_gesture=True)
        count = len(self._transform_target)
        noun = "vertex" if count == 1 else "vertices"
        release = "the mouse button" if key == TWEAK_KEY else key.upper()
        self._set_status(
            f"{label}: {count} {noun}{self._constraint_suffix(self._axis_constraint)}"
            f" - move the mouse, release {release} to commit"
        )
        return True

    @staticmethod
    def _constraint_suffix(space: str | None) -> str:
        return "" if space is None else f" (constraint {_constraint_label(space)})"

    def _constrain(self, space: str) -> bool:
        """Constraint-Taste (B4.1, wie Playground `window.py`): dieselbe Taste
        erneut → frei, eine andere ersetzt. Wirkt auch ohne scharfes Tool;
        während einer laufenden Geste ändert sich nur der Zustand — der
        Tool-`space` ist ab `begin()` fix, der neue Wert gilt ab der nächsten
        Geste."""
        self._axis_constraint = None if self._axis_constraint == space else space
        self._set_status(f"Constraint: {_constraint_label(self._axis_constraint)}")
        return True

    def _toggle_orientation(self) -> bool:
        """`K` (WP Toolbox Gaps C1, the Playground's key, `PROVISIONAL`): World <-> Normal. Clears the
        constraint like the Playground: the same letter is another direction in the other frame. Not
        during a begun gesture (its frame is fixed at `begin()`); an armed one takes the new value."""
        if self._transform_begun:
            return False
        self._orientation = (
            transform_space.NORMAL if self._orientation == transform_space.WORLD else transform_space.WORLD
        )
        self._axis_constraint = None
        self._set_status(f"Transform space: {self._orientation.capitalize()} (constraint none)")
        return True

    def _normal_space_context(self) -> tuple[str | None, dict]:
        """(refusal, begin parameters) of a constrained gesture in Normal space: `space="normal"` with the
        constraint as `axis`, and the selection's current normals as `derived_geometry` (the tools' frame is
        the gizmo's frame, `transform_space`)."""
        normals = transform_space.SelectionNormals(self.scene.mesh, self.selection)
        frame = transform_space.normal_frame(self.scene.mesh, self.selection, normals)
        refusal = transform_space.normal_refusal(
            frame, self._transform_space, scale=self._transform_command == commands.SCALE
        )
        context = {"space": transform_space.NORMAL, "axis": self._transform_space, "derived_geometry": normals}
        return refusal, context

    def _transform_step(self, dx: float, dy: float, force: bool = False) -> bool:
        """Eine Mausbewegung, während ein Transform scharf ist. Die erste
        Bewegung startet die Interaktion (keine Schwelle, AD-016); ein
        Nullschritt zählt nicht als Bewegung.

        WP-SYM-LAB-03 H5: lehnt das Tool den Start unter Symmetrie ab
        (`SeamConstraintError`, INV-8 / AD-SYM-02 §2.4: ein Seam-Vertex würde
        die Ebene verlassen), endet der Transform sichtbar, ohne History und
        mit unverändertem Mesh (das Tool bricht selbst exakt ab)."""
        if dx == 0 and dy == 0 and not force:
            return False
        if self._rotate_virtual is not None:
            self._rotate_virtual = (self._rotate_virtual[0] + dx, self._rotate_virtual[1] + dy)
        if not force and self._shift_held and self._transform_command in (commands.MOVE, commands.SCALE):
            dx, dy = dx * PRECISION_GAIN, dy * PRECISION_GAIN  # Shift = precision (Rotate scales its own angle)
        if self._object_gesture is not None:
            return self._object_step(dx, dy)
        if self._transform_command == commands.LOOP_SLIDE:
            return self._slide_step(dx, dy)
        if self._transform_command in _SMOOTH_COMMANDS:
            return self._smooth_step(dx)
        if not self._transform_begun and self._transform_command == commands.EXTRUDE:
            # Net displacement since the arm; the first update gets all of it, so the
            # distance follows the pointer from where T went down.
            px, py = self._extrude_travel
            px, py = px + dx, py + dy
            self._extrude_travel = (px, py)
            if math.hypot(px, py) < EXTRUDE_BEGIN_PX:
                return False
            if not self._extrude_begin():
                return False
            dx, dy = px, py
        elif not self._transform_begun:
            self._transform_space = self._axis_constraint
            soft = self._soft if self._soft.enabled else None
            begin_context = {
                "scene": self.scene,
                "camera": self._edit_camera,
                "vertex_ids": set(self._transform_target),
                "space": self._transform_space,
            }
            if soft is not None:
                begin_context["soft"] = soft  # absent when off: today's payload, unchanged
            mask = self._mask_values()
            if mask:
                begin_context["mask"] = mask  # absent without a mask: today's payload, unchanged
            if self._orientation == transform_space.NORMAL and self._transform_space is not None:
                refusal, normal_context = self._normal_space_context()
                if refusal is not None:
                    label = _TRANSFORM_COMMANDS[self._transform_command][0]
                    self._transform_end()
                    self._set_status(f"{label}: refused — {refusal}")
                    self._refresh_hover()
                    return False
                begin_context.update(normal_context)
            rotate_gizmo = self._rotate_gesture_mode()
            if rotate_gizmo is not None:
                begin_context["gizmo"] = {
                    "mode": rotate_gizmo,
                    "press": self._rotate_press,
                    "size": (int(self.viewport_width), int(self.viewport_height)),
                }
            try:
                self.tool_manager.begin_current_interaction(begin_context)
            except (SeamConstraintError, SoftSymmetryRefusal) as exc:
                # Symmetric Soft (AD-SYM-04 SS2): D-2 and the open O-1 cases refuse here, where
                # the settings are read, before anything moves - like a seam refusal.
                label = _TRANSFORM_COMMANDS[self._transform_command][0]
                self._transform_end()
                # Status text PROVISIONAL, like the other transform status lines.
                self._set_status(f"{label}: refused — {exc}")
                self._refresh_hover()
                return False
            self._transform_begun = True
            if soft is not None:
                self._soft_gesture = soft
                self._soft_gesture_reference = soft.world_radius * 100.0 / soft.radius_percent
                self._soft_show_op_weights()
        update = {"dx": float(dx), "dy": float(dy), "width": self.viewport_width, "height": self.viewport_height}
        if self._transform_command == commands.ROTATE:
            update["precise"], update["snap"] = self._shift_held, self._snap_held()
            if self._rotate_gesture_mode() == "dial":
                update["x"], update["y"] = self._rotate_virtual
        self.tool_manager.update(**update)
        self._pick_cache.invalidate()
        self.viewport.on_vertices_moved(self._active_transform_vertex_ids())
        return True

    def _rotate_gesture_mode(self) -> str | None:
        """How the running Rotate follows the pointer: `trackball` (gizmo centre), `dial` (every other cursor
        gesture: gizmo ring, R/E key, Tweak), None without a command, a cursor or a viewport (dx fallback)."""
        if self._transform_command != commands.ROTATE or self._rotate_press is None:
            return None
        return "trackball" if self._gizmo_gesture == "center" else "dial"

    def _snap_held(self) -> bool:
        return self._ctrl_held and self._ctrl_snap_ok

    @property
    def cursor_wrap_active(self) -> bool:
        """True while the window should warp the pointer across the viewport edge (a running transform;
        a reusable gate for later slider drags)."""
        return self._transform_key is not None

    def cursor_wrapped(self, jump_x: float, jump_y: float) -> None:
        """The window moved the pointer by (jump_x, jump_y) to the opposite edge. Gestures run on deltas (the
        warp's own event is swallowed), so only the stored cursor follows."""
        if self._cursor is not None:
            self._cursor = (self._cursor[0] + jump_x, self._cursor[1] + jump_y)

    def set_alt_held(self, held: bool) -> bool:
        """The window reports whether any Alt key is held. During a transform, motion then navigates
        (`_navigate_during_transform`); during a Box / Lasso drag it switches the release to select
        through the mesh (`selection_through`); otherwise it is only stored. True = the state changed."""
        held = bool(held)
        if held == self._alt_held:
            return False
        self._alt_held = held
        return True

    def set_ctrl_held(self, held: bool) -> bool:
        """The window reports whether any Ctrl key is held. Ctrl = snap in a running transform (a Tweak needs
        Ctrl let go once first); the snap shows at once. True = the transform changed."""
        held = bool(held)
        if held == self._ctrl_held:
            return False
        self._ctrl_held = held
        if not held:
            self._ctrl_snap_ok = True
        if (
            self._transform_key is None
            or not self._transform_begun
            or self._transform_command != commands.ROTATE
            or self._rotate_virtual is None
        ):
            return False
        return self._transform_step(0.0, 0.0, force=True)

    def _active_transform_vertex_ids(self) -> set[VertexId]:
        """Vom laufenden Transform betroffene Vertex-IDs (E29): `MoveTool.moves`
        (inkl. Symmetrie-Partner) bzw. `TransformTool.vertex_ids` - bewusst
        nicht vereinheitlicht, MoveTool erbt nicht von TransformTool."""
        tool = self.tool_manager.active_tool
        moves = getattr(tool, "moves", None)
        return moves if moves is not None else tool.vertex_ids

    def _transform_end(self) -> None:
        """Transform-Tool deaktivieren und den Transform-Zustand löschen."""
        resume_preview = self._soft_gesture_shown
        self._soft_op_running = False
        self._soft_gesture_shown = False
        self._soft_gesture = None
        self.tool_manager.deactivate()
        self._transform_key = None
        self._transform_command = None
        self._transform_target = frozenset()
        self._transform_begun = False
        self._transform_space = None
        self._rotate_press = None
        self._rotate_virtual = None
        self._extrude_faces = frozenset()
        self._extrude_travel = (0.0, 0.0)
        self._extrude_selection_before = None
        self._object_gesture = None
        self._slide_plan = None
        self._slide_t = 0.0
        self._slide_direction = None
        if self._slide_before is not None:
            # A slide that ended without release / abort: stop its recording, keep the mesh.
            self.scene.mesh.release_change(self._slide_before)
        self._slide_before = None
        self._slide_selection_before = None
        self._smooth_plan = None
        self._smooth_amount = 0.0
        if self._smooth_before is not None:
            self.scene.mesh.release_change(self._smooth_before)
        self._smooth_before = None
        self._smooth_selection_before = None
        self._smooth_seeds = frozenset()
        if resume_preview:
            self._soft_preview_refresh()

    # -- Soft Selection settings (WP-SOFT-01 S2a, AD-020, PROVISIONAL) ------------------

    # -- Mask Geometry (`mirai.mask`) ----------------------------------------------

    @property
    def _mask(self) -> VertexMask:
        """The edit object's mask (each object keeps its own: its IDs mean nothing on another mesh)."""
        return self._masks.setdefault(self.scene.edit_object_id, VertexMask())

    @property
    def _hidden(self) -> HiddenSet:
        return self._hiddens.setdefault(self.scene.edit_object_id, HiddenSet())

    def _mask_values(self) -> dict[VertexId, float]:
        """The mask a gesture begins with (stale IDs dropped, symmetric pairs protected alike); `{}` = none.
        Hidden vertices count as fully masked: nothing the artist cannot see is moved."""
        hidden = self._hidden
        if not self._mask and not hidden:
            return {}
        return effective_mask(self.scene.mesh, self._mask, extra_full=hidden.vertices())

    def _mask_changed(self, status: str) -> bool:
        self._mask.prune(self.scene.mesh)
        self._mask_push()
        self._set_status(status)
        return True

    def _mask_push(self) -> None:
        """The mask overlay shows the edit object's mask without its hidden vertices."""
        if self._mask_overlay is None:
            return
        hidden = self._hidden.vertices()
        values = {v: m for v, m in self._mask.values().items() if v not in hidden}
        self._mask_overlay.set_values(values)
        if self.viewport is not None:
            self.viewport.on_vertices_moved(set(values))  # re-syncs the overlay

    # -- Hide / Isolate (`mirai.hidden`) --------------------------------------------

    def _hidden_push(self) -> None:
        """Everything that draws or picks learns the hidden set; the selection never keeps a hidden element."""
        mesh = self.scene.mesh
        hidden = self._hidden
        hidden.prune(mesh)
        vertices = hidden.vertices()
        if self.viewport is not None:
            self.viewport.set_hidden(vertices)
        self._pick_cache.set_hidden(vertices)
        self._prune_hidden_selection()
        self._mask_push()
        self._soft_preview_refresh()

    def _prune_hidden_selection(self) -> None:
        hidden = self._hidden
        if not hidden:
            return
        mesh = self.scene.mesh
        selection = self.selection
        selection.vertices = {v for v in selection.vertices if not hidden.is_hidden_vertex(v)}
        selection.edges = {
            e for e in selection.edges if mesh.is_valid_edge(e) and not hidden.is_hidden_edge(mesh, e)
        }
        selection.faces = {
            f for f in selection.faces if mesh.is_valid_face(f) and not hidden.is_hidden_face(mesh, f)
        }
        h = selection.hovered
        if (
            (isinstance(h, VertexId) and hidden.is_hidden_vertex(h))
            or (isinstance(h, EdgeId) and mesh.is_valid_edge(h) and hidden.is_hidden_edge(mesh, h))
            or (isinstance(h, FaceId) and mesh.is_valid_face(h) and hidden.is_hidden_face(mesh, h))
        ):
            selection.hovered = None

    def _hidden_refuses(self, command: str) -> bool:
        """True (and the reason posted) if `command` would rewrite geometry the artist has hidden: the
        selection (else the hovered element) touches a hidden vertex, or - the Knife, `C` with nothing
        selected - anything is hidden at all. Cheap exit when nothing is hidden."""
        hidden = self._hidden
        if not hidden or self.selection.mode is SelectionMode.OBJECT:
            return False
        mesh = self.scene.mesh
        selection = self.selection
        vertices = set(resolve_selection_vertices(mesh, selection, selection.mode))
        if not vertices and selection.hovered is not None and command != commands.CONNECT:
            vertices = set(_element_vertices(mesh, selection.hovered))
        if not vertices:
            if command != commands.CONNECT:
                return False  # the command's own "nothing selected" refusal speaks
            text = "Knife"
        elif touches_hidden(mesh, hidden, vertices):
            text = "Topology edit"
        else:
            return False
        self._set_status(f"{text}: hidden geometry in the way (Alt+H shows all)")
        return True

    def _hide_command(self, command: str) -> bool:
        """Ctrl+H / Ctrl+Shift+H / Alt+H: hide the selection, isolate it (hide everything else), show all.
        No History, no mesh change; the selection loses what became hidden. Refused during a running gesture."""
        if self._transform_key is not None:
            return False
        mesh = self.scene.mesh
        hidden = self._hidden
        if command == commands.SHOW_ALL:
            if not hidden:
                self._set_status("Nothing is hidden")
                return False
            count = len(hidden)
            hidden.show_all()
            self._hidden_push()
            self._set_status(f"Shown all ({count} points)")
            return True
        selection = self.selection
        target = set(resolve_selection_vertices(mesh, selection, selection.mode))
        if not target:
            self._set_status("Hide: select vertices first (Ctrl+H)")
            return False
        if mesh.symmetry_definition is not None:
            target |= mirrored_selection(mesh, target)  # a pair is hidden together
        return self._hide_vertices(command, target)

    def _hide_vertices(self, command: str, target: set[VertexId]) -> bool:
        """Hide or isolate `target` (the shared body of Ctrl+H / Ctrl+Shift+H and the region isolate)."""
        mesh = self.scene.mesh
        hidden = self._hidden
        if command == commands.ISOLATE_SELECTION:
            hidden.isolate(mesh, target)
            label = f"Isolated {len(target)} points"
        else:
            hidden.hide(target)
            label = f"Hid {len(target)} points"
        if len(hidden) >= len(mesh.all_vertex_ids()):
            hidden.show_all()  # nothing visible is a trap: refuse instead
            self._hidden_push()
            self._set_status("Hide: everything would be hidden")
            return False
        self._hidden_push()  # a hidden element leaves the selection; Isolate keeps what it isolated
        self._set_status(f"{label} ({len(hidden)} hidden, Alt+H shows all)")
        return True

    def _mask_command(self, command: str) -> bool:
        """Ctrl+M / Ctrl+Shift+M / Alt+Shift+M: mask the selection (or unmask it when it is fully masked),
        invert, clear. No History, no selection or mesh change; refused during a running gesture."""
        if self._transform_key is not None:
            return False
        mesh = self.scene.mesh
        if command == commands.MASK_CLEAR:
            self._mask.clear()
            return self._mask_changed("Mask cleared")
        if command == commands.MASK_INVERT:
            self._mask.invert(mesh)
            return self._mask_changed(f"Mask inverted: {len(self._mask.full())} points masked")
        selection = self.selection
        target = set(resolve_selection_vertices(mesh, selection, selection.mode))
        if not target:
            self._set_status("Mask: select vertices first (Ctrl+M)")
            return False
        if mesh.symmetry_definition is not None:
            target |= mirrored_selection(mesh, target)  # a pair is masked together
        return self._mask_vertices(target)

    def _mask_vertices(self, target: set[VertexId]) -> bool:
        """Mask `target`, or unmask it when it is already fully masked (Ctrl+M and the region mask)."""
        if target <= self._mask.full():
            self._mask.set(target, 0.0)
            return self._mask_changed(f"Unmasked {len(target)} points ({len(self._mask.full())} masked)")
        self._mask.set(target)
        return self._mask_changed(f"Masked {len(target)} points ({len(self._mask.full())} masked)")

    # -- Saved regions (`mirai.regions`, AD-REGIONS-01) -----------------------------------

    @property
    def active_region(self) -> str | None:
        """The active group: the one last made, picked or clicked; when that one is gone (Undo, Delete) the last group
        in the list; None without groups."""
        regions = self.scene.mesh.face_regions
        if regions is None:
            return None
        name = self._active_regions.get(self.scene.edit_object_id)
        if name is not None and regions.get(name) is not None:
            return name
        return regions.regions[-1].name

    def _set_active_region(self, name: str) -> None:
        self._active_regions[self.scene.edit_object_id] = name

    @property
    def region_count(self) -> int:
        """How many groups the edit mesh has (read-only, for the HUD)."""
        regions = self.scene.mesh.face_regions
        return 0 if regions is None else len(regions.regions)

    def _push_region_tints(self) -> None:
        """The regions' colours go to the viewport whenever the edit mesh's `face_regions` value (or the mesh, or
        the viewport) changed: assign, Undo / Redo, load and Knife rollback all replace that value."""
        if self.viewport is None:
            return
        mesh = self.scene.mesh
        seen = self._tints_seen
        if seen is not None and seen[0] is mesh and seen[1] is mesh.face_regions and seen[2] is self.viewport:
            return
        self._tints_seen = (mesh, mesh.face_regions, self.viewport)
        self.viewport.set_face_tints(face_regions_api.region_tints(mesh))

    @property
    def active_region_faces(self) -> int:
        """How many faces the active group still has (read-only, for the HUD)."""
        name = self.active_region
        return 0 if name is None else len(face_regions_api.live_faces(self.scene.mesh, name))

    def _region_summary(self, name: str) -> str:
        mesh = self.scene.mesh
        live = len(face_regions_api.live_faces(mesh, name))
        lost = face_regions_api.lost_count(mesh, name)
        text = f"{name}: {live} faces"
        if lost:
            text += f" ({lost} lost to topology edits)"
        return text

    def _region_command(self, command: str) -> bool:
        """Ctrl+G (new group), Shift+G / Shift+Alt+G (active group), Ctrl+Shift+G / Ctrl+Alt+G (add, remove),
        Ctrl+Alt+N (save as named set), Alt+G / Ctrl+Alt+Shift+G (select), Ctrl+Alt+H (isolate), Ctrl+Alt+M (mask),
        Ctrl+Alt+Backspace (delete). Edits of the stored groups are one Undo step (`_mesh_transaction`); select /
        isolate / mask only read them. Refused during a gesture."""
        if self._transform_key is not None:
            return False
        mesh = self.scene.mesh
        if command == commands.REGION_NEW:
            return self._region_edit(command, face_regions_api.new_group_name(mesh.face_regions))
        name = self.active_region
        if name is None:
            self._set_status("No groups yet (select faces, Ctrl+G makes a group)")
            return False
        if command in (commands.REGION_NEXT, commands.REGION_PREV):
            names = [r.name for r in mesh.face_regions.regions]
            step = 1 if command == commands.REGION_NEXT else -1
            name = names[(names.index(name) + step) % len(names)]
            self._set_active_region(name)
            self._set_status(f"Active group {names.index(name) + 1}/{len(names)}: {self._region_summary(name)}")
            return True
        if command in (commands.REGION_ADD, commands.REGION_REMOVE):
            return self._region_edit(command, name)
        if command == commands.REGION_NAME:
            new = face_regions_api.next_name(mesh.face_regions, name)
            if new == name:
                self._set_status(f"{name}: every set name is taken")
                return False
            self._mesh_transaction(
                f"Name {name} {new}",
                lambda m: setattr(m, "face_regions", face_regions_api.renamed(m.face_regions, name, new)),
                moved_of=lambda _: set(),
            )
            self._set_active_region(new)
            self._set_status(f"{name} saved as {new} (Ctrl+Alt+N again: next name)")
            return True
        if command == commands.REGION_DELETE:
            self._mesh_transaction(
                f"Delete {name}",
                lambda m: setattr(m, "face_regions", face_regions_api.deleted(m.face_regions, name)),
                moved_of=lambda _: set(),
            )
            self._set_status(f"{name} deleted")
            return True
        faces = face_regions_api.live_faces(mesh, name)
        if not faces:
            self._set_status(f"{name}: no faces left")
            return False
        vertices = face_regions_api.region_vertices(mesh, faces)
        # Isolate and mask act on the whole group, hidden parts included (Isolate shows them again); only the
        # selection skips what is hidden.
        if command == commands.REGION_ISOLATE:
            return self._hide_vertices(commands.ISOLATE_SELECTION, vertices)
        if command == commands.REGION_MASK:
            return self._mask_vertices(vertices)
        selection = self.selection
        if selection.mode is SelectionMode.OBJECT:
            return False
        hidden = self._hidden
        faces = frozenset(f for f in faces if not hidden.is_hidden_face(mesh, f))
        elements = face_regions_api.elements_of(mesh, selection.mode, faces)
        if command == commands.REGION_SELECT:
            selection.set(elements)
        else:
            selection.add(elements)
        self._prune_hidden_selection()
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        self._set_status(self._region_summary(name) + " selected")
        return True

    def _pick_face_at(self, x: float, y: float):
        """The face under (x, y) whatever the selection mode is (GPU ID buffer, else the CPU picker), else None."""
        face = self._gpu_pick(SelectionMode.FACE, x, y)
        if face is not _CPU:
            return face
        return pick_face(
            self._edit_camera, self.scene.mesh, x, y, self.viewport_width, self.viewport_height,
            cache=self._pick_cache,
        )

    def _region_click(self, x: float, y: float) -> bool:
        """Shift+Ctrl+click (`commands.REGION_CLICK`): a face of region R isolates R; the already isolated R inverts
        the visibility (the rest becomes visible, only R's interior is hidden); empty space shows everything. View
        state only: no History, no selection or mesh change. Ignored in object mode and during a gesture."""
        if self.viewport is None or self._transform_key is not None or self.selection.mode is SelectionMode.OBJECT:
            return False
        mesh = self.scene.mesh
        face = self._pick_face_at(x, y)
        if face is None:
            return self._hide_command(commands.SHOW_ALL)
        name = face_regions_api.region_of_face(mesh, face, prefer=self.active_region)
        if name is None:
            self._set_status("Face has no group (Ctrl+G makes the selection a group)")
            return False
        self._set_active_region(name)
        faces = face_regions_api.live_faces(mesh, name)
        vertices = face_regions_api.region_vertices(mesh, faces)
        hidden = self._hidden
        isolated = hidden.vertices() == frozenset(mesh.all_vertex_ids()) - vertices
        if not isolated:
            return self._hide_vertices(commands.ISOLATE_SELECTION, vertices)
        interior = face_regions_api.interior_vertices(mesh, faces)
        hidden.show_all()
        if interior:
            hidden.hide(interior)
        self._hidden_push()
        self._set_status(
            f"{name} hidden, the rest is visible (Shift+Ctrl+click on empty space shows all)" if interior
            else f"{name} has no interior to hide; everything is visible"
        )
        return True

    def _region_edit(self, command: str, name: str) -> bool:
        """New group `name` from / add to / remove from group `name` the faces of the selection (all corners selected).
        A face is in one group: new and add take it out of its old group."""
        mesh = self.scene.mesh
        selection = self.selection
        if selection.mode is SelectionMode.OBJECT:
            return False
        if selection.mode is SelectionMode.FACE:
            faces = {f for f in selection.faces if mesh.is_valid_face(f)}
        else:
            faces = face_regions_api.faces_from_vertices(
                mesh, resolve_selection_vertices(mesh, selection, selection.mode)
            )
        if not faces:
            self._set_status("Group: select faces first")
            return False
        if mesh.symmetry_definition is not None:
            faces |= set(expand_faces(SymmetryIndex(mesh), faces).union)  # a pair belongs together
        if command == commands.REGION_REMOVE:
            change = lambda regions: face_regions_api.removed(regions, name, faces)  # noqa: E731
            verb = "removed from"
        else:
            add = command == commands.REGION_ADD
            change = lambda regions: face_regions_api.grouped(regions, name, faces, add=add)  # noqa: E731
            verb = "added to" if add else "grouped as"
        done = self._mesh_transaction(
            f"New {name}" if command == commands.REGION_NEW else name,
            lambda m: setattr(m, "face_regions", change(m.face_regions)),
            moved_of=lambda _: set(),
        )
        if not done.changed:
            self._set_status(f"{name}: no change")
            return False
        if command != commands.REGION_REMOVE:
            self._set_active_region(name)
        summary = self._region_summary(name) if face_regions_api.region_named(mesh, name) else f"{name} (now empty, gone)"
        self._set_status(f"{len(faces)} faces {verb} {summary}")
        return True

    def _soft_refresh_radius(self) -> None:
        """Recompute the world radius from the mesh's bounding radius for the current step
        (the one place that does it: switch-on, step change, scene load)."""
        _, bounding_radius = mesh_center_and_radius(self.scene.mesh)
        self._soft = self._soft.with_bounding_radius(bounding_radius)

    def _soft_command(self, command: str) -> bool:
        """O / Shift+wheel / Shift+O / Ctrl+O / Ctrl+wheel / Ctrl+Shift+wheel / Alt+O / Alt+Shift+O: change the sticky settings
        and post the full state. Never touches mesh, selection or history. False only for a
        radius or shape step that is already at the end of the list (clamped, no wrap) and
        changes nothing - the status line is posted anyway, so the end of the list is visible."""
        soft = self._soft
        changed = True
        if command == commands.SOFT_TOGGLE:
            self._soft = soft.toggled()
            if self._soft.enabled:
                self._soft_refresh_radius()
        elif command in (commands.SOFT_RADIUS_UP, commands.SOFT_RADIUS_DOWN) and self._soft_live():
            changed = self._soft_radius_live(1 if command == commands.SOFT_RADIUS_UP else -1)
        elif command in (commands.SOFT_FLOW_LOOP, commands.SOFT_FLOW_RING):
            delta = 1 if command == commands.SOFT_FLOW_LOOP else -1
            if self._soft_live():
                changed = self._soft_flow_live(delta)
            else:
                self._soft = soft.with_flow_step(delta)
                changed = self._soft != soft
        elif command in (commands.SOFT_RADIUS_UP, commands.SOFT_RADIUS_DOWN):
            step = soft.radius_step + (1 if command == commands.SOFT_RADIUS_UP else -1)
            step = max(0, min(step, len(RADIUS_STEPS_PERCENT) - 1))
            changed = step != soft.radius_step
            _, bounding_radius = mesh_center_and_radius(self.scene.mesh)
            self._soft = soft.with_radius_step(step, bounding_radius)
        elif command == commands.SOFT_CURVE_CYCLE:
            self._soft = soft.with_next_curve()
        elif command == commands.SOFT_METRIC_CYCLE:
            self._soft = soft.with_next_metric()
        elif command in (commands.SOFT_CURVE_SHAPE_ROUNDER, commands.SOFT_CURVE_SHAPE_SHARPER):
            # Rounder = smaller exponent = towards the front of the step list.
            delta = -1 if command == commands.SOFT_CURVE_SHAPE_ROUNDER else 1
            self._soft = soft.with_custom_shape_step(delta)
            changed = self._soft != soft
        elif command == commands.SOFT_BANDS_TOGGLE:
            self._soft = soft.with_bands_toggled()
        elif command == commands.SOFT_VIEW_MODE_CYCLE:
            self._soft = soft.with_next_view_mode()
        elif command == commands.SOFT_LOOK_CYCLE:
            # Colours only: applied at once, also mid-gesture (the weights and what is shown stay).
            self._soft = soft.with_next_look()
            self._soft_apply_look()
        if changed:
            self._soft_preview_refresh()
        status = self._soft.status_text()
        if command in (commands.SOFT_FLOW_LOOP, commands.SOFT_FLOW_RING):
            status += self._soft_flow_hint()
        self._set_status(status)
        return changed

    def _soft_flow_hint(self) -> str:
        """Status suffix for a flow step: says when the seeds give no Loop / Ring direction, so the field
        stays round (AD-020 "Loop / Ring flow": one vertex, one quad, a square block ...)."""
        soft = self._soft_gesture or self._soft
        if soft.flow_ratio == 1.0 or soft.metric != "geodesic":
            return ""
        tool = self._soft_live_tool()
        seeds = set(tool.soft_seeds) if tool is not None else self._soft_seeds()
        if not seeds or has_flow_direction(self.scene.mesh, seeds):
            return ""
        return " (no loop/ring direction here: round)"

    def _soft_apply_look(self) -> None:
        """Push the look (`SoftSettings.look`) to the influence sinks that exist."""
        for sink in (self._soft_overlay, self._soft_shading_overlay):
            if sink is not None and hasattr(sink, "set_look"):
                sink.set_look(self._soft.look)

    def _soft_live_tool(self):
        """The tool of a begun Soft Move/Rotate/Scale (key hold, Tweak or gizmo drag), else None: the
        state in which the wheel steps the radius of the running gesture."""
        if self._soft_gesture is None or not self._transform_begun:
            return None
        tool = self.tool_manager.active_tool
        return tool if getattr(tool, "is_soft_gesture", False) else None

    def _soft_live(self) -> bool:
        """A running Soft gesture takes radius / flow steps live: a begun Soft W/E/R, or a held Smooth /
        Relax with Soft on (C2)."""
        return self._soft_live_tool() is not None or self._smooth_soft_live()

    def _soft_radius_live(self, delta: int) -> bool:
        """One radius step for the running Soft gesture (AD-020 "Live radius", `PROVISIONAL`): the gesture
        is re-evaluated from its start geometry with the new influence (`reweight`), the display shows the
        new weights, and the sticky setting takes the same step. Clamped, no wrap; False at the end of
        the list (nothing recomputed). Metric, curve and display stay those of the gesture."""
        gesture = self._soft_gesture
        step = max(0, min(gesture.radius_step + delta, len(RADIUS_STEPS_PERCENT) - 1))
        if step == gesture.radius_step:
            return False
        gesture = gesture.with_radius_step(step, self._soft_gesture_reference)
        self._soft = dataclasses.replace(self._soft, radius_step=step, world_radius=gesture.world_radius)
        self._soft_reweight_live(gesture)
        return True

    def _soft_flow_live(self, delta: int) -> bool:
        """One Loop / Ring balance step for the running Soft gesture (AD-020 "Loop / Ring flow",
        `PROVISIONAL`): the same re-evaluation from the start geometry as a live radius step; the sticky
        setting takes the same step. Clamped, no wrap; False at the end of the list."""
        gesture = self._soft_gesture.with_flow_step(delta)
        if gesture == self._soft_gesture:
            return False
        self._soft = dataclasses.replace(self._soft, flow_step=gesture.flow_step)
        self._soft_reweight_live(gesture)
        return True

    def _soft_reweight_live(self, gesture: SoftSettings) -> None:
        """The running Soft gesture continues with `gesture`'s influence (`reweight`: cancel, begin again
        on the start geometry with the same seeds / pivot, replay the intent), and the display shows it."""
        self._soft_gesture = gesture
        if self._smooth_soft_live():
            touched = self._smooth_reweight(gesture)
            self._pick_cache.invalidate()
            self.viewport.on_vertices_moved(touched)
            self._smooth_show_weights()
            return
        touched = self._soft_live_tool().reweight(gesture)
        self._pick_cache.invalidate()
        self.viewport.on_vertices_moved(touched)
        self._soft_show_op_weights()

    # -- Soft Selection bands (WP-SOFT-01 S2b, AD-020 §5, PROVISIONAL) -------------------
    #
    # The overlays only show; `Application` computes. Influence is computed here at most once
    # per triggering event (selection, mode, settings, scene load, Undo/Redo, topology change,
    # gesture end, and - since 2026-10-22 - a change of the hovered component while there is no
    # explicit selection) - never per mouse move over the same component: during a gesture the
    # display is the op's own weights (fixed at `begin()`), and the overlay merely re-reads the
    # live positions when the viewport syncs after `on_vertices_moved`. Two display modes
    # (vertex bands / face shading, `SoftSettings.view_mode`) are routed from the same weights;
    # only one is ever non-empty.

    @property
    def soft_bands(self) -> SoftBands:
        """The bands the window currently shows (`EMPTY_BANDS` = no band points; also in the
        face-shading mode)."""
        return self._soft_bands

    @property
    def soft_shading(self) -> dict[VertexId, float]:
        """The weights the face shading currently shows ({} = no shading; also in the bands mode)."""
        return dict(self._soft_shading)

    def _soft_show(self, weights: dict[VertexId, float] | None, mode: str | None = None) -> None:
        """Route `weights` (None = nothing to show) to the display mode `mode` (default: the active one)
        and clear the other, so bands and face shading are never visible together. Pushes only what
        changed."""
        mode = self._soft.view_mode if mode is None else mode
        bands = SoftBands.from_weights(weights) if weights and mode == "bands" else EMPTY_BANDS
        shading = dict(weights) if weights and mode == "faces" else {}
        if bands != self._soft_bands:
            self._soft_bands = bands
            if self._soft_overlay is not None:
                self._soft_overlay.set_bands(bands)
        if shading != self._soft_shading:
            self._soft_shading = shading
            if self._soft_shading_overlay is not None:
                self._soft_shading_overlay.set_weights(shading)

    def _soft_selection_seeds(self) -> set[VertexId]:
        selection = self.selection
        return set(resolve_selection_vertices(self.scene.mesh, selection, selection.mode))

    def _soft_seeds(self) -> set[VertexId]:
        """What the next W/E/R would use as the primary selection (`_transform_arm`): the armed
        target while a Move/Rotate/Scale is armed, else the explicit selection, else - with none -
        the vertices of the hovered component. An existing selection is never replaced by the
        hover."""
        if (
            self._transform_key is not None
            and self._transform_command in (commands.MOVE, commands.ROTATE, commands.SCALE)
        ):
            return set(self._transform_target)
        seeds = self._soft_selection_seeds()
        if not seeds and self.selection.hovered is not None:
            seeds = _element_vertices(self.scene.mesh, self.selection.hovered)
        return seeds

    def _soft_hover_changed(self) -> None:
        """The hovered component changed (identity, `_set_hovered`): with Soft on, shown and no
        explicit selection, the hover is the preview target. Not while a transform is armed or
        running (its target owns the display), and never for a pointer move over the same
        component."""
        soft = self._soft
        if not (soft.enabled and soft.bands_visible) or self._transform_key is not None:
            return
        if self._soft_overlay is None and self._soft_shading_overlay is None:
            return
        if self._soft_selection_seeds():
            return  # the explicit selection is the target; hover is only the highlight
        self._soft_preview_refresh()

    def _soft_preview_refresh(self, shown_by_gesture: bool = False) -> None:
        """Recompute the preview (E3). No-op without a sink, and while a running op owns the
        display. Soft off, hidden (`bands_visible` False) or no target (no selection and no hovered
        component) show nothing; under a symmetry definition the preview is the symmetric field
        (AD-SYM-04 D-5, slice SS3). The display mode (`view_mode`) only routes the same weights."""
        if (self._soft_overlay is None and self._soft_shading_overlay is None) or self._soft_op_running:
            return
        soft = self._soft
        # Hidden (S2d E7): no influence work for display, nothing shown.
        shown = soft.enabled and soft.bands_visible
        seeds = self._soft_seeds() if shown else None
        weights = self._soft_preview_weights(seeds) if seeds else None
        self._soft_show(weights)
        if weights is not None:
            self._soft_gesture_shown = self._soft_gesture_shown or shown_by_gesture

    def _soft_preview_weights(self, seeds: set[VertexId]) -> dict[VertexId, float] | None:
        """The weights the next gesture's `begin()` computes for `seeds`, by the same function
        with the same arguments (preview == op weights, F9). Under a definition: the symmetric
        field, its correspondence from the shared report of the current geometry (the tool
        derives its own, equal one at `begin()`). None = nothing shown: a selection symmetric Soft
        refuses (D-2) shows none (`PROVISIONAL`), never plain Soft's field; the refusal itself
        is shown by the gesture, at `begin()`, as before."""
        soft = self._soft
        mesh = self.scene.mesh
        mask = self._mask_values()  # the same mask the tools apply at `begin()` (Mask Geometry, Hide)
        seeds = unblocked(seeds, mask)
        if mesh.symmetry_definition is None:
            weights = compute_influence(
                mesh, seeds, soft.world_radius, metric=soft.metric, curve=soft.curve,
                curve_power=soft.curve_power, flow_ratio=soft.flow_ratio,
            )
            return mask_weights(weights, seeds, mask)
        correspondence = self._symmetry_reports.current(mesh).correspondence
        try:
            field = symmetric_influence(
                mesh, seeds, soft.world_radius, metric=soft.metric, curve=soft.curve,
                curve_power=soft.curve_power, correspondence=correspondence,
                flow_ratio=soft.flow_ratio,
            )
        except SoftSymmetryRefusal:
            return None
        return mask_symmetric_influence(field, mask).weights

    def _soft_show_op_weights(self) -> None:
        """At `begin()`: the display becomes the op's own weights (E4), so the preview and the
        gesture cannot disagree; nothing is computed. Under symmetry the op's weights are the
        symmetric field, both sides (AD-SYM-04 D-5)."""
        if self._soft_overlay is None and self._soft_shading_overlay is None:
            return
        # Also while hidden: the gesture still owns the display (a bands toggle or mode switch
        # mid-gesture takes effect when it ends), it just has nothing to show (S2d E7). Hence the
        # gesture's own display settings (a live radius step calls this again mid-gesture).
        self._soft_op_running = True
        self._soft_gesture_shown = True
        display = self._soft_gesture or self._soft
        if not display.bands_visible:
            self._soft_show(None, display.view_mode)
            return
        self._soft_show(
            self.tool_manager.active_tool.operation.context.params["influence"], display.view_mode
        )

    # -- Extrude (WP-06 B9, hold T) -------------------------------------------------
    #
    # PROVISIONAL baseline. Key T = Artist Input Truth `topology.extrude` ("for now",
    # Manu 2026-10-09). The hold-key-hover activation (E1) and the hover fallback (E2)
    # are engineering proposals, NOT Artist decisions. Same lifecycle as W/E/R
    # (`_transform_*`), with the differences the branches above mark: Face mode only,
    # target = faces, `begin()` mutates the topology (hence EXTRUDE_BEGIN_PX), the
    # viewport is told about a topology change, a zero extrusion is cancelled, and the
    # selection-history `before` is the snapshot taken ahead of `begin()`.

    def _extrude_arm(self, key: str) -> bool:
        """Arm Extrude: Face mode with >= 1 selected face, else the hovered face, else
        refuse with a status line. The tool is active, `begin()` waits for the pointer."""
        selection = self.selection
        mesh = self.scene.mesh
        if selection.mode is not SelectionMode.FACE:
            self._set_status("Extrude: face mode needed")
            return False
        faces = {f for f in selection.faces if mesh.is_valid_face(f)}
        hovered = selection.hovered
        from_hover = not faces and isinstance(hovered, FaceId) and mesh.is_valid_face(hovered)
        if from_hover:
            faces = {hovered}
        if not faces:
            self._set_status("Extrude: select or hover a face")
            return False
        self.dispatch_command(commands.EXTRUDE)
        self._transform_key = key
        self._transform_command = commands.EXTRUDE
        self._transform_target = frozenset(
            vid for f in faces for vid in _element_vertices(mesh, f)
        )
        self._transform_begun = False
        self._extrude_faces = frozenset(faces)
        self._extrude_travel = (0.0, 0.0)
        # Same clear-on-arm as the transforms: no hover highlight on what is extruded.
        if from_hover or _active_selection_contains(selection, hovered):
            self._set_hovered(None)
        count = len(faces)
        self._set_status(
            f"Extrude: {count} {'face' if count == 1 else 'faces'}"
            f" - move the mouse, release {key.upper()} to commit"
        )
        return True

    def _extrude_begin(self) -> bool:
        """Start the Extrude (topology changes here). False = refused, tool disarmed.

        AD-SYM-03 slice 7: whenever a symmetry definition is set the declared planner
        (`symmetry_declarations.EXTRUDE_COORDINATORS`, D-b - the declaration is the only switch) runs
        first, in MARK as in BLOCK (H2 amendment, "Runtime refusals are not G-3"): it refuses before any
        mutation (`SymmetryRefusal`: status text, mesh/history/selection untouched, tool disarmed) or
        returns the plan - selection plus mirror partners as one intent - that the unchanged tool is handed.
        Without a definition the tool runs exactly as in B9."""
        self._extrude_selection_before = self._selection_snapshot()
        faces = set(self._extrude_faces)
        context = {"scene": self.scene, "camera": self._edit_camera}
        planner = (
            symmetry_declarations.EXTRUDE_COORDINATORS.get(commands.EXTRUDE)
            if self.scene.mesh.symmetry_definition is not None
            else None
        )
        if planner is not None:
            try:
                plan = planner(self.scene.mesh, faces)
            except SymmetryRefusal as exc:
                self._transform_end()
                self._set_status(str(exc))
                self._refresh_hover()
                return False
            faces = set(plan.face_ids)
            context["symmetric_plan"] = plan
        context["face_ids"] = faces
        try:
            self.tool_manager.begin_current_interaction(context)
        except TopologyToolError as exc:
            self._transform_end()
            self._set_status(f"Extrude: refused — {exc}")
            self._refresh_hover()
            return False
        self._transform_begun = True
        self._extrude_topology_changed()
        return True

    def _extrude_topology_changed(self) -> None:
        """After begin/commit/cancel: caches, viewport and a dead-ID sweep (B6 lesson:
        a stale hovered/selected ID after a topology change crashed the draw loop)."""
        self._pick_cache.invalidate()
        self._prune_ghost_selection()
        if self.viewport is not None:
            self.viewport.on_topology_changed()
            self.viewport.on_selection_changed()
        self._soft_preview_refresh()

    def _extrude_release(self) -> None:
        """Release of T: commit, or - tap, jitter below EXTRUDE_BEGIN_PX, or a total
        distance below EXTRUDE_MIN_DISTANCE - leave everything exactly as it was."""
        if not self._transform_begun:
            self._set_status("Extrude: no change")
            return
        if abs(self.tool_manager.active_tool.total_distance) < EXTRUDE_MIN_DISTANCE:
            self._extrude_abort()
            self._set_status("Extrude: no change")
            return
        tool = self.tool_manager.active_tool
        self.tool_manager.commit()
        if tool.refusal is not None:
            # A symmetric commit the coordinator refused (delta): the tool has taken everything back, no
            # history entry. Same exact prior state as an abort, with the refusal as the visible status.
            self._restore_selection(self._extrude_selection_before)
            self._extrude_topology_changed()
            self._set_status(tool.refusal)
            return
        self._record_selection_history(self._extrude_selection_before)
        self._extrude_topology_changed()
        self._set_status("Extrude committed")

    def _extrude_abort(self) -> None:
        """Cancel a begun Extrude: exact prior mesh (tool), exact prior selection, no history."""
        self.tool_manager.cancel()
        self._restore_selection(self._extrude_selection_before)
        self._extrude_topology_changed()

    def _cancel(self) -> bool:
        """Esc = nur Abbrechen (B1 A3: kein Quit, E22). Laufender Transform →
        exakter Vorzustand ohne History; nur scharf → entschärfen; idle →
        nichts. Eine Box/Paint-Geste wird verworfen (Auswahl wie vor der Geste)."""
        if self._drag_select is not None:
            return self._drag_select_cancel()
        if self._transform_key is None:
            return False
        if self._transform_key == TWEAK_KEY:
            # The LMB is still down: the rest of this drag must not arm a new Tweak.
            self._gesture_refused = True
        label, _, _ = _TRANSFORM_COMMANDS[self._transform_command]
        if self._object_gesture is not None:
            if self._transform_begun:
                self._object_cancel()
                self._set_status(f"Object {label} cancelled")
            else:
                self._set_status(f"Object {label} disarmed")
        elif self._transform_begun and self._transform_command == commands.EXTRUDE:
            self._extrude_abort()
            self._set_status(f"{label} cancelled")
        elif self._transform_begun and self._transform_command == commands.LOOP_SLIDE:
            self._slide_abort()
            self._set_status(f"{label} cancelled")
        elif self._transform_command in _SMOOTH_COMMANDS:
            # Begun: exact start state back. Not begun: Esc instead of the tap step.
            self._smooth_abort()
            self._set_status(f"{label} cancelled")
        elif self._transform_begun:
            moved = self._active_transform_vertex_ids()
            self.tool_manager.cancel()
            self._pick_cache.invalidate()
            self.viewport.on_vertices_moved(moved)
            self._set_status(f"{label} cancelled")
        else:
            self._set_status(f"{label} disarmed")
        self._transform_end()
        self._refresh_hover()
        return True

    def _undo_redo(self, command: str) -> bool:
        can = self.history.can_undo() if command == commands.UNDO else self.history.can_redo()
        if not can:
            self._set_status(f"{command}: nothing to {command.lower()}")
            return False
        self.dispatch_command(command)
        # E23: `HistoryStack` bietet keinen öffentlichen Zugriff auf das
        # gerade rückgängig gemachte Command (und `core/history.py` ist
        # tabu) - daher der gröbere, aber für jedes Command korrekte Rebuild
        # statt `on_vertices_moved(ids)`. Selection-Restore und Ghost-Pruning
        # laufen bereits in `dispatch_command` (`_apply_undo_redo`), auch für
        # Aufrufer, die `dispatch_command(UNDO/REDO)` direkt statt über
        # `key_press` erreichen.
        if self._last_undo_redo_mesh_step:
            self._pick_cache.invalidate()
            if self.viewport is not None:
                self.viewport.on_topology_changed()
        self._set_status(command)
        self._refresh_hover()
        return True

    def _apply_undo_redo(self, command: str) -> None:
        """Führt `history.undo()`/`redo()` aus und stellt dabei die Selection
        wieder her (WP-06 B6 Follow-up, Artist-Entscheidung Manu 2026-09-28).

        `HistoryStack` (core, frozen) kennt kein Selection-Konzept; Application
        führt deshalb einen eigenen Mirror-Stack aus (before, after)-Snapshots,
        einen pro `history.push()`, den sie selbst über `_record_selection_
        history()` befüllt (Split/Edge Connect/Vertex Connect, Transform-
        Commit, Knife-Commit, Delete/Dissolve, `apply_mesh_change`). Der
        Mirror-Pop läuft in
        derselben Reihenfolge wie `HistoryStack`s eigener Undo-/Redo-Stack
        (LIFO), Undo restauriert den `before`-Snapshot (Auswahl, wie sie vor
        der Mutation war), Redo den `after`-Snapshot (die von der Mutation
        gesetzte Residue-Auswahl). Ist der Mirror-Stack leer, obwohl History
        Undo/Redo erlaubt (Desync, z. B. ein künftiger Push-Pfad, der hier noch
        nicht verdrahtet ist), bleibt es beim reinen Pruning (Fallback, kein
        Crash) - `_prune_ghost_selection()` läuft danach in jedem Fall als
        Sicherheitsnetz, auch nach einem erfolgreichen Restore (dort ein
        No-op, weil der restaurierte Snapshot per Konstruktion gültig ist)."""
        restored = None
        # Without a mirror entry (desync fallback) the step is treated as a mesh step: the
        # full rebuild is correct for every command.
        self._last_undo_redo_mesh_step = True
        object_meshes: frozenset = frozenset()
        if command == commands.UNDO and self._selection_undo_stack:
            entry = self._selection_undo_stack.pop()
            self._selection_redo_stack.append(entry)
            restored = entry[0]
            self._last_undo_redo_mesh_step = entry[2]
            object_meshes = entry[3]
        elif command == commands.REDO and self._selection_redo_stack:
            entry = self._selection_redo_stack.pop()
            self._selection_undo_stack.append(entry)
            restored = entry[1]
            self._last_undo_redo_mesh_step = entry[2]
            object_meshes = entry[3]

        edit_before_step = self.scene.edit_object_id
        if command == commands.UNDO:
            self.history.undo()
        else:
            self.history.redo()
        if self.scene.edit_object_id != edit_before_step:
            # A command that carries the edit object itself (Delete of the edit object, Add with
            # an edit switch) switched the scene; viewport, caches and hover follow.
            self._follow_edit_object()

        if restored is not None:
            self._restore_selection(restored)
            if self.viewport is not None:
                self.viewport.on_selection_changed()  # an object step can change mode / selection
        self._prune_ghost_selection()
        # AD-021 §4.6: refresh the view of the objects an object step touched; an object step
        # may be a placement (M2-2), so the pick caches re-project too (`_placement_changed`).
        self._object_meshes_changed(object_meshes)
        if self._last_undo_redo_mesh_step and not object_meshes:
            self._sync_object_views()
        else:
            self._placement_changed()
        self._soft_preview_refresh()

    def apply_mesh_change(
        self, description: str, mutate: Callable[[], set[VertexId] | None]
    ) -> bool:
        """The one entry for a mesh change made outside `Application`
        (WP-SYM-LAB-03 H3, AD-013 H2 addendum, review CLAUDE-002 N1).

        `mutate()` changes `scene.mesh` through core operations and returns
        the moved vertex IDs (positions only) or None (topology changed).
        Raises `RuntimeError` before anything changes while
        `interaction_owner` is set (D3). If `mutate` raises, the mesh is
        restored exactly and the exception propagates (ID counters
        stay forward, AD-001). An unchanged mesh records nothing
        and returns False. Otherwise: one `MeshDeltaCommand(description)`, the
        selection-mirror entry (so Undo/Redo restores the selection, B6
        follow-up), pick cache invalidated, viewport notified, hover
        re-picked; returns True."""
        owner = self.interaction_owner
        if owner is not None:
            raise RuntimeError(
                f"apply_mesh_change({description!r}) while the {owner} interaction runs"
            )
        return self._mesh_transaction(
            description, lambda _mesh: mutate(), moved_of=lambda moved: moved
        ).changed

    def _mesh_transaction(
        self,
        description: str,
        mutate: Callable[[Mesh], Any],
        *,
        on_applied: Callable[[Any], None] | None = None,
        moved_of: Callable[[Any], set[VertexId] | None] | None = None,
    ) -> "_MeshTransaction":
        """The one commit boundary for a mesh change `Application` makes (AD-SYM-03 §2.2 T-a);
        `apply_mesh_change` is its external-host entry.

        `mutate(mesh)` changes the mesh and returns a result. If it raises, the mesh is restored
        exactly (change journal) and the exception propagates. An unchanged mesh records
        nothing (`changed` False). Otherwise: one `MeshDeltaCommand(description)`,
        `on_applied(result)` (sets the selection residue), then the selection-mirror entry
        taken from the snapshot made before the mutation, pick cache invalidated, viewport
        notified (`moved_of(result)` = moved vertex IDs for a positions-only change, None or no
        `moved_of` = topology changed), hover re-picked."""
        mesh = self.scene.mesh
        selection_before = self._selection_snapshot()
        # Change journal (AD-023 H1): the entry holds only what `mutate` changed; a raising
        # `mutate` is rolled back exactly, an unchanged mesh records nothing.
        # Saved regions: a face this edit creates inherits its parents' regions inside the same recording (Undo restores
        # the mesh and the regions together; a raising `mutate` or hook is rolled back exactly).
        change = mesh.begin_change()
        try:
            result = mutate(mesh)
            face_regions_api.inherit_into(mesh, change)
        except BaseException:
            mesh.rollback_change(change)
            raise
        delta = mesh.end_change(change)
        if delta.empty:
            return _MeshTransaction(False, result)
        self.history.push(MeshDeltaCommand(mesh=mesh, delta=delta, description=description))
        if on_applied is not None:
            on_applied(result)
        self._record_selection_history(selection_before)
        moved = moved_of(result) if moved_of is not None else None
        if moved is None:
            self._notify_topology_changed()
        else:
            self._pick_cache.invalidate()
            if self.viewport is not None:
                self.viewport.on_vertices_moved(set(moved))
            self._soft_preview_refresh()
            self._refresh_hover()
        return _MeshTransaction(True, result)

    def _selection_snapshot(self) -> tuple:
        """Momentaufnahme von Modus + Auswahl (kein Hover - der wird nach
        Undo/Redo ohnehin über `_refresh_hover()` neu am Cursor gepickt,
        nicht wiederhergestellt). AD-021 §4.4/§4.6: dazu die Objekt-Auswahl und das
        Edit-Objekt - die Komponenten-IDs gelten nur zusammen mit ihm."""
        selection = self.selection
        return (
            selection.mode,
            frozenset(selection.vertices),
            frozenset(selection.edges),
            frozenset(selection.faces),
            frozenset(selection.objects),
            self.scene.edit_object_id,
        )

    def _restore_selection(self, snapshot: tuple) -> None:
        mode, vertices, edges, faces, objects, edit_object_id = snapshot
        scene = self.scene
        # An Undo that removed an object drops it from the object selection (§4.6, R-9). Q-8
        # (M2-4): the edit object of the step comes back with the entry, through E-14 so the
        # viewport and the caches follow; RF-5: a Reference never becomes the edit object.
        target = scene.objects.get(edit_object_id)
        if (
            target is not None
            and edit_object_id != scene.edit_object_id
            and target.state is not ObjectState.REFERENCE
        ):
            self._set_edit_object(edit_object_id)
        selection = self.selection
        selection.mode = mode
        selection.vertices = set(vertices)
        selection.edges = set(edges)
        selection.faces = set(faces)
        selection.objects = {oid for oid in objects if oid in scene.objects}

    def _record_selection_history(
        self, before: tuple, mesh_step: bool = True, object_meshes: frozenset = frozenset()
    ) -> None:
        """Von jedem Aufrufer, der gerade `history.push()` ausgelöst hat (bzw.
        gleich auslösen wird - siehe Aufrufstellen), mit dem VOR der Mutation
        genommenen `_selection_snapshot()` aufzurufen. Spiegelt `HistoryStack.
        push()`: ein neuer Eintrag verwirft den Mirror-Redo-Zweig genau wie
        dort den echten. `mesh_step` False = ein Objekt-Schritt (AD-021 M1), dessen
        Undo/Redo das Mesh des Edit-Objekts nicht neu aufbaut. `object_meshes` (M2-3): die
        Nicht-Edit-Objekte, deren Mesh der Schritt geändert hat."""
        after = self._selection_snapshot()
        self._selection_undo_stack.append((before, after, mesh_step, frozenset(object_meshes)))
        self._selection_redo_stack.clear()

    def _prune_ghost_selection(self) -> None:
        """Entfernt jedes Handle, das `mesh` nicht mehr kennt ("ghost
        selection") - Sicherheitsnetz nach `_apply_undo_redo()`.

        Das Mesh-Command stellt das Mesh wieder her; ohne den Selection-
        Restore oben blieben Handles von Elementen, die die Mutation entfernt
        hatte, als tote IDs in `selection` liegen. Der B6-Crash-Fix
        (`_notify_topology_changed`, `_element_vertices`, `resolve_selection_
        vertices`) machte Konsumenten nur tolerant gegenüber solchen IDs; sie
        zählten aber weiter in `len(selection.edges/vertices/faces)`, was z. B.
        `resolve_c_context` in den falschen Kontext auflösen konnte. Dieselbe
        `is_valid_*`-Prüfung wie dort, kein zweiter Mechanismus. Läuft nach
        jedem Undo/Redo, auch nach einem erfolgreichen Restore (dort ein
        No-op) - der einzige Fall, in dem hier tatsächlich noch etwas entfernt
        wird, ist der Mirror-Stack-Desync-Fallback in `_apply_undo_redo()`."""
        mesh = self.scene.mesh
        selection = self.selection
        selection.vertices = {v for v in selection.vertices if mesh.is_valid_vertex(v)}
        selection.edges = {e for e in selection.edges if mesh.is_valid_edge(e)}
        selection.faces = {f for f in selection.faces if mesh.is_valid_face(f)}
        selection.objects = {oid for oid in selection.objects if oid in self.scene.objects}
        hovered = selection.hovered
        if isinstance(hovered, VertexId) and not mesh.is_valid_vertex(hovered):
            selection.hovered = None
        elif isinstance(hovered, EdgeId) and not mesh.is_valid_edge(hovered):
            selection.hovered = None
        elif isinstance(hovered, FaceId) and not mesh.is_valid_face(hovered):
            selection.hovered = None
        elif isinstance(hovered, ObjectId) and hovered not in self.scene.objects:
            selection.hovered = None
        self._prune_hidden_selection()  # an Undo may have brought back what is hidden

    def _set_status(self, message: str) -> None:
        self.status_message = message
        self.status_serial += 1

    def _gate_refuses(self, command: str | None) -> bool:
        """H2: True (and the refusal posted as status) if `command_gate`
        refuses `command`. Unbound input (None) is never refused."""
        gate = self.command_gate
        if gate is None or command is None:
            return False
        text = gate.refusal(command)
        if text is None:
            return False
        self._set_status(text)
        return True

    def set_status(self, message: str) -> None:
        """Public form of `_set_status` (WP-SYM-LAB-03 H4, AD-013 H2 addendum):
        a host posts its own messages and refusals through the same
        `status_message`/`status_serial`, so a repeated text still counts."""
        self._set_status(message)

    # -- Pointer / Navigation (WP-06 B2, AD-019) ------------------------------

    def set_viewport_size(self, width: int, height: int) -> None:
        """Setzt die Viewport-Größe (Maus-Koordinaten-Einheit) und meldet den
        neuen Aspect an den Viewport."""
        self.viewport_width = max(int(width), 1)
        self.viewport_height = max(int(height), 1)
        self._camera_changed()

    def pointer_press(
        self, input: Input, x: float | None = None, y: float | None = None
    ) -> None:
        """Maustaste gedrückt (`input.kind == "mouse"`, Modifier beim Press).
        `x`/`y` (optional, B7): Cursor beim Press - ohne Angabe gilt die
        letzte bekannte Cursor-Position."""
        self.flush_hover()
        if x is not None and y is not None:
            self._cursor = (x, y)
        if self._knife is not None and self._knife_owns_press(input):
            self._knife_press(input)
            return
        if not self.pointer.active:
            self._press_point = self._cursor
            if self._resym_plan is None:
                self._gizmo_press(input)
        self.pointer.press(input)

    def pointer_drag(
        self, dx: float, dy: float, x: float | None = None, y: float | None = None
    ) -> bool:
        """Mausbewegung mit gedrückter Taste. True = ein Command wurde ausgeführt.
        Während einer Knife-Geste (B7.1) zählt nur die Distanz für die
        Klick-Schwelle - `x`/`y` werden nicht für eine Vorschau verwendet."""
        if x is not None and y is not None:
            self._cursor = (x, y)
        if self._knife_gesture:
            return self._knife_drag(dx, dy)
        if self._alt_held and self._transform_key == TWEAK_KEY:
            # A gizmo / Tweak drag: Alt borrows the motion for the camera, the gesture keeps running.
            return self._navigate_during_transform(dx, dy)
        step = self.pointer.drag(dx, dy)
        return step is not None and self._execute_drag(step)

    def pointer_release(self, button: str, x: float, y: float) -> bool:
        """Maustaste losgelassen. True = ein Klick-Command wurde ausgeführt
        bzw. der Knife hat einen Punkt gesetzt / den Stift abgesetzt."""
        self._cursor = (x, y)
        if self._knife_gesture and button == self._knife_gesture_button:
            return self._knife_release(x, y)
        click = self.pointer.release(button, x, y)
        if button == "LEFT" and self._gizmo_gesture is not None:
            return self._gizmo_release(click is not None)
        if button == "LEFT" and self._drag_select is not None:
            return self._drag_select_finish()
        if button == "LEFT" and self._transform_key == TWEAK_KEY:
            self._transform_finish()
            return True
        if button == "LEFT":
            self._gesture_refused = False
        if self._knife is not None:
            # Session Gate (B7): Navigation ist vorbei bzw. ein modifizierter
            # Klick fiel - der Klick selbst tut während der Session nichts
            # (keine Auswahländerung), die Knife-Vorschau pickt neu.
            self._refresh_hover()
            return False
        return click is not None and self._execute_click(click)

    def pointer_scroll(self, input: Input) -> bool:
        """Wheel-Input (`kind == "wheel"`), aufgelöst über die Bindings. Ein Wheel mit
        gehaltener Shift-Taste trägt `{"shift"}` und ist (Default) die Soft-Radius-Stufe, eines
        mit Ctrl `{"ctrl"}` die Form der Soft-Kurve `custom` (S2d); beide zoomen nie
        (WP-SOFT-01 S2a, AD-020). In einer Knife-Session tun sie nichts.

        Live radius (AD-020, `PROVISIONAL`): während einer begonnenen Soft-Geste (Move/Rotate/Scale,
        auch per Gizmo/Tweak) ist das Zoom-Rad die Radius-Stufe dieser Geste und zoomt nicht."""
        command = self.bindings.command_for(input)
        if command == commands.ZOOM and self._soft_live():
            command = commands.SOFT_RADIUS_UP if input.value == "UP" else commands.SOFT_RADIUS_DOWN
        if command in _SOFT_COMMANDS:
            if self._resym_plan is not None:
                self._resymmetrize_refuse()
                return False
            if self._knife is not None or self._gate_refuses(command):
                return False
            return self.dispatch_command(command)
        if command != commands.ZOOM:
            return False
        self.camera.dolly(DOLLY_IN_FACTOR if input.value == "UP" else DOLLY_OUT_FACTOR)
        self._camera_changed()
        # Unter dem ruhenden Cursor liegt nach dem Zoom ggf. ein anderer Vertex.
        if self.coalesce_hover and self._knife is None:
            self._hover_stale = True  # a burst of notches picks once, at the next tick
        else:
            self._refresh_hover()
        return True

    # -- Hover (WP-06 B2b, E20) -------------------------------------------------

    def pointer_motion(self, x: float, y: float, dx: float = 0.0, dy: float = 0.0) -> bool:
        """Mausbewegung ohne gedrückte Taste.

        Transform scharf (W/E/R gehalten, B3/B4): `dx`/`dy` treiben den
        Transform, kein Hover (E24). Sonst Hover unter dem Cursor im aktiven
        Modus (Vertex B2b, Edge/Face B5b). Während einer laufenden
        Pointer-Geste (Kamera) passiert beides nicht — Navigation gewinnt. True = ein Transform-Schritt lief bzw.
        `selection.hovered` hat sich geändert."""
        self._cursor = (x, y)
        if self.pointer.active:
            return False
        if self._knife is not None:
            if self._knife_gesture:
                return False
            return self._knife_hover(x, y)
        if self._transform_key is not None:
            # Relax is held with Alt (Alt+S): for Smooth / Relax Alt never borrows the camera.
            if self._alt_held and self._transform_command not in _SMOOTH_COMMANDS:
                return self._navigate_during_transform(dx, dy)
            return self._transform_step(dx, dy)
        if self._light_drag_key is not None:
            return self._light_drag_step(dx, dy)
        if self.coalesce_hover:
            self._hover_stale = True
            return False
        return self._update_hover(x, y)

    def flush_hover(self) -> bool:
        """Picks a hover that `coalesce_hover` left stale (a mouse move or zoom notch since the
        last pick), at the current cursor - the pick the move would have made, for the state
        that is current now. The frame tick calls it, and every input that may read the hover
        first. True = `selection.hovered` changed."""
        if not self._hover_stale:
            return False
        self._hover_stale = False
        before = self.selection.hovered
        self._refresh_hover()
        after = self.selection.hovered
        return not (type(before) is type(after) and before == after)

    def _refresh_hover(self) -> None:
        """Hover an der letzten Cursor-Position neu picken (nach Zoom bzw.
        wenn sich das Mesh unter dem ruhenden Cursor bewegt hat). Während
        einer Knife-Session statt des Selection-Hovers die Knife-Vorschau."""
        if self._knife is not None:
            if self._knife_gesture:
                return
            if self._cursor is not None and not self.pointer.active:
                self._knife_hover(*self._cursor)
            else:
                self._knife_clear_preview()
            return
        if self._cursor is not None and not self.pointer.active and self._transform_key is None:
            self._update_hover(*self._cursor)

    def pointer_leave(self) -> bool:
        """Cursor hat das Fenster verlassen: Hover (bzw. Knife-Vorschau) löschen."""
        self._cursor = None
        self._hover_stale = False
        if self._knife is not None:
            if self._knife_gesture:
                return False
            return self._knife_clear_preview()
        return self._set_hovered(None)

    def _update_hover(self, x: float, y: float) -> bool:
        # Hover im aktiven Modus: Vertex (B2b), Edge oder Face (B5b).
        if self.viewport is None:
            return False
        if self._hover_suspended or self._resym_plan is not None:
            return self._set_hovered(None)
        if self.selection.mode is SelectionMode.OBJECT:
            # AD-021 M1 (`PROVISIONAL`): no object hover yet - it would have no look, and an
            # object pick per motion costs the full picking of every object (gollum,
            # REFERENCE_HARDWARE §2). Only a click picks in mode `4`.
            return self._set_hovered(None)
        return self._set_hovered(self._pick(x, y))

    def _pick(self, x: float, y: float):
        """E43: Element unter dem Cursor im aktiven Selection-Modus (oder None).
        WP-06 B8: cached (`self._pick_cache`) and occlusion-aware - only
        visible vertices/edges are pickable while faces are shown (Shaded/
        Flat Shaded); Wireframe leaves everything pickable, as before B8.
        AD-021 M1: in mode `4` the ObjectId under the cursor; every other mode looks at the
        edit object's mesh only, so a Reference never blocks it (RF-6)."""
        if self.selection.mode is SelectionMode.OBJECT:
            return self._pick_object(x, y)
        hit = self._gpu_pick(self.selection.mode, x, y)
        if hit is not _CPU:
            return hit
        return pick_component(
            self._edit_camera,
            self.scene.mesh,
            self.selection.mode,
            x,
            y,
            self.viewport_width,
            self.viewport_height,
            cache=self._pick_cache,
            occlusion=self.display.show_faces,
        )

    def _gpu_pick_mesh(self):
        """The edit `RenderMesh` when the window can pick from its ID buffers (AD-022 B2-out), else None
        (headless, `TraceStore`, `gpu_picking` off): the CPU picker then answers."""
        if not self.gpu_picking or self.viewport is None:
            return None
        return self.viewport.gpu_pick_mesh()

    def _gpu_failed(self, exc: BaseException) -> None:
        """A GL error in the ID pass (driver, FBO at resize): the CPU picker takes over for the rest of
        the session (AD-022 §9 abort criterion 4) and the status line says so."""
        self.gpu_picking = False
        self._set_status(f"GPU picking off ({type(exc).__name__}: {exc}) - CPU picker")

    def _gpu_pick(self, mode, x: float, y: float):
        """The GPU pick of `mode` at (x, y), or `_CPU` when the window cannot serve it."""
        rm = self._gpu_pick_mesh()
        if rm is None:
            return _CPU
        try:
            return gpu_pick_component(
                self.viewport.gpu_picker, rm, self._edit_camera, self.scene.mesh, mode,
                x, y, int(self.viewport_width), int(self.viewport_height),
                occlusion=self.display.show_faces, cache=self._pick_cache,
            )
        except Exception as exc:  # noqa: BLE001 - any GL failure falls back, never breaks picking
            self._gpu_failed(exc)
            return _CPU

    def _set_hovered(self, hovered) -> bool:
        """Setzt `selection.hovered` (reiner UI-State, kein History-Eintrag) und
        benachrichtigt den Viewport nur bei einer echten Änderung."""
        current = self.selection.hovered
        # IDs sind int-Subklassen: VertexId(3) == EdgeId(3) - Typ mitvergleichen.
        if type(current) is type(hovered) and current == hovered:
            return False
        self.selection.hovered = hovered
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_hover_changed()
        return True

    def _execute_drag(self, step: DragStep) -> bool:
        if self._resym_plan is not None and step.command in (
            commands.SELECT_DRAG, commands.SELECT_DRAG_ADD, commands.TWEAK
        ):
            # The open preview owns the mesh and the selection; navigation still runs. (A handle
            # pressed before the preview opened would arm a Tweak here.)
            return False
        if self._gizmo_gesture is not None and step.command in (commands.SELECT_DRAG, commands.SELECT_DRAG_ADD):
            return self._gizmo_step(step.dx, step.dy)
        if step.command in (commands.SELECT_DRAG, commands.SELECT_DRAG_ADD):
            return self._drag_select_step(step.command)
        if step.command == commands.TWEAK:
            return self._tweak_step(step.dx, step.dy)
        if not self._navigate(step.command, step.dx, step.dy):
            return False
        # Eine laufende Orbit-/Pan-Geste löscht Hover (während einer Knife-
        # Session die Knife-Vorschau; Start und Pfad bleiben); er kehrt mit
        # der nächsten Mausbewegung nach dem Release zurück.
        if self._knife is not None:
            self._knife_clear_preview()
        else:
            self._set_hovered(None)
        return True

    def _navigate(self, command: str, dx: float, dy: float) -> bool:
        if command == commands.ORBIT:
            self.camera.orbit(-dx * ORBIT_RADIANS_PER_PX, -dy * ORBIT_RADIANS_PER_PX)
        elif command == commands.PAN:
            self.camera.pan(dx, dy, self.viewport_width, self.viewport_height)
        else:
            return False
        self._camera_changed()
        return True

    def _navigate_during_transform(self, dx: float, dy: float) -> bool:
        """Alt held while a transform is armed or runs: Orbit (Alt+Shift: Pan) like Alt+LMB, without a
        button. The gesture is not stepped - Move/Scale continue in the new view (they read the camera per
        step); the Rotate dial keeps its virtual cursor but re-projects its pivot, so its angle can jump."""
        if dx == 0 and dy == 0:
            return False
        return self._navigate(commands.PAN if self._shift_held else commands.ORBIT, dx, dy)

    def _execute_click(self, click: Click) -> bool:
        if click.command == commands.REGION_CLICK:
            if self._resym_plan is not None:
                self._resymmetrize_refuse()
                return False
            if self._gate_refuses(click.command):
                return False
            return self._region_click(click.x, click.y)
        if click.command in _SELECT_COMMANDS:
            if self._resym_plan is not None:
                self._resymmetrize_refuse()
                return False
            if self._gate_refuses(click.command):
                return False
            self.select_at(click.command, click.x, click.y)
            return True
        return False

    def select_at(self, command: str, x: float, y: float) -> bool:
        """Klick-Selektion, Modifier-Variante AP-03 (WP-06 B2, A7/E13), im
        aktiven Modus (Vertex/Edge/Face, B5b E43).

        Treffer: SELECT ersetzt, SELECT_ADD fügt hinzu, SELECT_REMOVE entfernt,
        SELECT_TOGGLE schaltet um. Klick ins Leere: nur SELECT leert, die
        Modifier-Commands lassen die Auswahl unverändert. `Selection.mode`
        wird nicht angefasst, kein History-Eintrag. True = die Auswahl hat
        sich tatsächlich geändert (nur dann wird der Viewport benachrichtigt)."""
        if self.viewport is None:
            return False
        if self.selection.mode is SelectionMode.OBJECT:
            return self._select_object_at(command, x, y)
        selection = self.selection
        before = _selection_state(selection)
        hit = self._pick(x, y)
        if hit is None:
            if command == commands.SELECT:
                selection.clear()
        elif command == commands.SELECT:
            selection.set({hit})
        elif command == commands.SELECT_ADD:
            selection.add({hit})
        elif command == commands.SELECT_REMOVE:
            selection.remove({hit})
        elif command == commands.SELECT_TOGGLE:
            selection.toggle(hit)
        if _selection_state(selection) == before:
            return False
        self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        return True

    #: B2-Name, bleibt als Weiterleitung (E43).
    select_vertex_at = select_at

    # -- Box / Paint Select (2026-10-15, Playground tools promoted, Manu) ------------------
    #
    # Box: Selection Lab KEEP (`playground/experiments/selection/decision.md`). Paint: planned
    # there ("Paint Select"), first built here. Manu 2026-10-15: the press point decides - in
    # empty space a box, on the mesh a paint stroke; no modifier replaces, Shift adds. Ctrl+drag
    # is Tweak ("Auswahl weicht"), so removing works by click only. Like a click, neither is a
    # History step. Not in mode `4` (`PROVISIONAL`).

    @property
    def selection_box(self) -> tuple[float, float, float, float] | None:
        """The rubber band of a running Box Select (min x, min y, max x, max y in window
        pixels), for the window to draw; None otherwise."""
        drag = self._drag_select
        if drag is None or drag.kind != "box" or drag.cancelled:
            return None
        return normalized_rect(drag.start, drag.end)

    @property
    def selection_lasso(self) -> list[tuple[float, float]] | None:
        """The outline of a running Lasso Select (window pixels, in drawing order; the window
        closes it back to the first point), for the window to draw; None otherwise."""
        drag = self._drag_select
        if drag is None or drag.kind != "lasso" or drag.cancelled:
            return None
        return list(drag.points)

    @property
    def selection_through(self) -> bool:
        """True while a running Box / Lasso would select through the mesh if released now: Alt is
        held (WP Toolbox Gaps A2, Manu 2026-10-23: "nach dem Gummiband-Aufziehen Alt gedrückt
        halten"). Alt at the press is still Orbit - by then the drag is no selection. The window
        draws the band in the through colour."""
        drag = self._drag_select
        return drag is not None and drag.kind in ("box", "lasso") and not drag.cancelled and self._alt_held

    def _region_occlusion(self) -> bool:
        """The occlusion rule of a Box / Lasso release: only what is visible while faces are shown,
        unless Alt is held (`selection_through`)."""
        return self.display.show_faces and not self._alt_held

    def _lasso_arm(self, key: str) -> bool:
        """The Lasso key went down: LMB drags make a lasso until it is let go. Not underneath a
        held W/E/R/T/G (the same gate as the mode keys) and not in a Knife session (which has its
        own key map and never gets here)."""
        if self.viewport is None or self._transform_key is not None:
            return False
        if self._lasso_held is None:
            self._set_status("Lasso: drag with LMB (Shift adds, Esc cancels)")
        self._lasso_held = key
        return True

    def _light_drag_arm(self, key: str) -> bool:
        """`L` went down (AD-024 Q-L2): mouse motion turns the key light until it is let go. Not
        underneath a held W/E/R/T/G (the motion belongs to the gesture). View state only."""
        if self._transform_key is not None:
            return False
        if self._light_drag_key is None:
            self._set_status("Light: move the mouse to turn the key light (release L to stop)")
        self._light_drag_key = key
        return True

    def _light_drag_step(self, dx: float, dy: float) -> bool:
        """The Lab's light drag (E13): dx → key azimuth, dy → key elevation, in the light's space."""
        rig = self.display.light_rig
        changed = self.set_light(
            key_azimuth=rig.key_azimuth + dx * DRAG_DEGREES_PER_PIXEL,
            key_elevation=rig.key_elevation + dy * DRAG_DEGREES_PER_PIXEL,
        )
        if changed:
            rig = self.display.light_rig
            self._set_status(f"Light: Key Azimut {rig.key_azimuth:+.1f}° · Höhe {rig.key_elevation:+.1f}°")
        return changed

    def _drag_select_refusal(self) -> str | None:
        """Why a drag selection cannot start now (None = it can). Silent cases return ""."""
        if self.viewport is None or self._knife is not None or self._transform_key is not None:
            return ""
        if self.selection.mode is SelectionMode.OBJECT:
            return "Box/Paint/Lasso: points, edges and faces only - press 1/2/3"
        return None

    def _drag_select_step(self, command: str) -> bool:
        cursor = self._cursor
        if cursor is None:
            return False
        drag = self._drag_select
        if drag is None:
            if self._gesture_refused:
                return False
            refusal = self._drag_select_refusal()
            if refusal is None and self._gate_refuses(command):
                refusal = ""
            if refusal is not None:
                if refusal:
                    self._set_status(refusal)
                self._gesture_refused = True  # silence the rest of this gesture
                return False
            start = self._press_point if self._press_point is not None else cursor
            lasso = self._lasso_held is not None
            gpu_face = None if lasso else self._gpu_pick(SelectionMode.FACE, start[0], start[1])
            on_mesh = False if lasso else gpu_face is not None if gpu_face is not _CPU else (
                pick_face(
                    self._edit_camera,
                    self.scene.mesh,
                    start[0],
                    start[1],
                    self.viewport_width,
                    self.viewport_height,
                    cache=self._pick_cache,
                )
                is not None
            )
            drag = _DragSelect(
                kind="lasso" if lasso else "paint" if on_mesh else "box",
                add=command == commands.SELECT_DRAG_ADD,
                start=start,
                end=cursor,
                before=self._selection_snapshot(),
                last=start,
                points=[start] if lasso else [],
            )
            self._drag_select = drag
            self._set_hovered(None)
            if drag.kind == "paint":
                if not drag.add:
                    self.selection.clear()
                    self.viewport.on_selection_changed()
                self._paint_at([start])
        if drag.cancelled:
            return False
        drag.end = cursor
        if drag.kind == "paint":
            self._paint_at(stroke_samples(drag.last, cursor))
            drag.last = cursor
        elif drag.kind == "lasso":
            last = drag.points[-1]
            if math.hypot(cursor[0] - last[0], cursor[1] - last[1]) >= LASSO_POINT_SPACING_PX:
                drag.points.append(cursor)
        return True

    def _paint_at(self, points) -> None:
        hits = {hit for hit in (self._pick(x, y) for x, y in points) if hit is not None}
        before = len(self._active_selection_ids())
        self.selection.add(hits)
        if len(self._active_selection_ids()) != before:
            self.viewport.on_selection_changed()

    def _active_selection_ids(self) -> set:
        selection = self.selection
        if selection.mode is SelectionMode.VERTEX:
            return selection.vertices
        if selection.mode is SelectionMode.EDGE:
            return selection.edges
        return selection.faces

    def _drag_select_finish(self) -> bool:
        drag = self._drag_select
        self._drag_select = None
        self._gesture_refused = False
        if drag is None or drag.cancelled:
            self._refresh_hover()
            return False
        selection = self.selection
        if drag.kind == "lasso":
            return self._lasso_finish(drag)
        rm = self._gpu_pick_mesh() if drag.kind == "box" else None
        occlusion = self._region_occlusion()
        through = "" if occlusion or not self.display.show_faces else " (through)"
        if rm is not None:
            try:
                found = gpu_elements_in_rect(
                    self.viewport.gpu_picker, rm, self._edit_camera, self.scene.mesh, selection.mode,
                    normalized_rect(drag.start, drag.end), int(self.viewport_width), int(self.viewport_height),
                    cache=self._pick_cache, occlusion=occlusion,
                )
            except Exception as exc:  # noqa: BLE001 - see `_gpu_failed`
                self._gpu_failed(exc)
                rm = None
        if rm is not None:
            if drag.add:
                selection.add(found)
            else:
                selection.set(found)
            label = "Box" + through
        elif drag.kind == "box":
            found = elements_in_rect(
                self._edit_camera,
                self.scene.mesh,
                selection.mode,
                normalized_rect(drag.start, drag.end),
                self.viewport_width,
                self.viewport_height,
                cache=self._pick_cache,
                occlusion=occlusion,
            )
            if drag.add:
                selection.add(found)
            else:
                selection.set(found)
            label = "Box" + through
        else:
            label = "Paint"
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        count = len(self._active_selection_ids())
        noun = selection.mode.name.lower()
        if count != 1:
            noun = "vertices" if noun == "vertex" else noun + "s"
        self._set_status(f"{label}: {count} {noun} selected")
        self._refresh_hover()
        return True

    def _lasso_finish(self, drag: _DragSelect) -> bool:
        """Apply a finished Lasso: the elements whose corners all lie inside the outline (as Box, with
        the same occlusion rule, Alt = through); fewer than three outline points select nothing and change
        nothing."""
        selection = self.selection
        polygon = drag.points
        if len(polygon) < 3:
            self._set_status("Lasso: draw a closed outline")
            self._refresh_hover()
            return True
        width, height = int(self.viewport_width), int(self.viewport_height)
        occlusion = self._region_occlusion()
        through = "" if occlusion or not self.display.show_faces else " (through)"
        found = None
        rm = self._gpu_pick_mesh()
        if rm is not None:
            try:
                found = gpu_elements_in_region(
                    self.viewport.gpu_picker, rm, self._edit_camera, self.scene.mesh, selection.mode,
                    lambda p: point_in_polygon(p, polygon), polygon_bounds(polygon), width, height,
                    cache=self._pick_cache, occlusion=occlusion,
                )
            except Exception as exc:  # noqa: BLE001 - see `_gpu_failed`
                self._gpu_failed(exc)
        if found is None:
            found = elements_in_polygon(
                self._edit_camera, self.scene.mesh, selection.mode, polygon, width, height,
                cache=self._pick_cache, occlusion=occlusion,
            )
        if drag.add:
            selection.add(found)
        else:
            selection.set(found)
        if self.viewport is not None:
            self.viewport.on_selection_changed()
        self._soft_preview_refresh()
        count = len(self._active_selection_ids())
        noun = selection.mode.name.lower()
        if count != 1:
            noun = "vertices" if noun == "vertex" else noun + "s"
        self._set_status(f"Lasso{through}: {count} {noun} selected")
        self._refresh_hover()
        return True

    def _drag_select_cancel(self) -> bool:
        drag = self._drag_select
        if drag is None or drag.cancelled:
            return False
        drag.cancelled = True
        if drag.kind == "paint":
            self._restore_selection(drag.before)
            if self.viewport is not None:
                self.viewport.on_selection_changed()
        self._set_status(f"{drag.kind.capitalize()} cancelled")
        return True

    # -- Transform gizmo (2026-10-21, promoted from the Playground, Manu "Gizmo nach src/") -----
    #
    # AD-016 D3 (Artist verdict 2026-09-21): the gizmo is an entry point. An LMB press on a handle (no
    # modifier) takes priority over the selection click: a click only sets the axis constraint (like X/Y/Z),
    # click + drag also runs the current tool - the last W/E/R, Move until one is pressed, the same state
    # Tweak reads (D2) - along it, the release commits, Esc cancels. A miss falls through unchanged. The
    # drag is the Tweak machinery (`_transform_arm` / `_transform_step` with the selection as the target), so
    # it is one History step, honours Soft Selection and Symmetry, and is refused where W/E/R is.
    # World frame only (normal space is not in the app); shown for point / edge / face selections, also of a
    # placed edit object (2026-10-23: at the selection's world position, in the world camera; the tools turn
    # the world axes into object space, E-8), hidden while any gesture runs. Look and sizes `PROVISIONAL` (`viewport.gizmo`).
    # Object level (2026-10-23): in mode `4` it sits at the centroid of the selected non-Reference objects'
    # world pivots and drives the object gesture (`_object_arm`, the same Tweak path), in the world camera.

    def _gizmo_pivot(self):
        """The selection's centroid (world), cached until the selection or the vertex positions change;
        None when the gizmo is not shown: off, no viewport, Knife session, nothing selected. In
        mode `4` see `_gizmo_object_pivot`. With a placed edit object the centroid is mapped to world
        (`object_space.to_world`, an exact pass-through while the placement is identity); the cache
        holds the object-space centroid, so a placement change needs no invalidation."""
        viewport = self.viewport
        if not self.gizmo_enabled or viewport is None or self._knife is not None:
            return None
        if self.selection.mode is SelectionMode.OBJECT:
            return self._gizmo_object_pivot()
        ids = self._active_selection_ids()
        if not ids:
            return None
        key = (viewport.geometry_revision, id(self.scene.mesh), self.selection.mode, len(ids), hash(frozenset(ids)))
        cache = self._gizmo_cache
        if cache is not None and cache[0] == key:
            pivot = cache[1]
        else:
            mesh = self.scene.mesh
            vertex_ids = resolve_selection_vertices(mesh, self.selection, self.selection.mode)
            pivot = selection_pivot(mesh, vertex_ids) if vertex_ids else None
            self._gizmo_cache = (key, pivot)
        return None if pivot is None else object_space.to_world(self.scene.edit_object, pivot)

    def _gizmo_object_pivot(self):
        """Mode `4`: the centroid of the selected objects' world pivots, References excluded (they are
        locked, `_object_targets`); None when no movable object is selected. Cheap, so not cached."""
        scene = self.scene
        targets = [
            scene.objects[oid]
            for oid in self.selection.objects
            if oid in scene.objects and scene.objects[oid].state is not ObjectState.REFERENCE
        ]
        # A mirror pair is one unit (proposal §5.4): with both selected the gizmo sits on the driver.
        ids = {obj.id for obj in targets}
        followers = set()
        for obj in targets:
            pair = scene.mirror_pair_of(obj.id)
            if pair is not None and pair.other(obj.id) in ids:
                followers.add(max(pair.a, pair.b))
        targets = [obj for obj in targets if obj.id not in followers]
        if not targets:
            return None
        points = [object_space.to_world(obj, obj.pivot) for obj in targets]
        return tuple(sum(p[i] for p in points) / len(points) for i in range(3))

    def _gizmo_frame(self) -> tuple[list, list]:
        """The gizmo's axes and planes in world space: the world axes, or in Normal space (C1) the
        selection's frame (`transform_space.normal_frame`: X/Y/Z for one face, Z only otherwise, nothing
        but the free handles when the selection has no normal). Mode `4` stays on the world axes (the
        object gesture). Cached with the same key as the pivot."""
        if self._orientation == transform_space.WORLD or self.selection.mode is SelectionMode.OBJECT:
            return _gizmo.WORLD_AXES, _gizmo.WORLD_PLANES
        # The pivot is computed first (`_gizmo_pivot`), so its cache key is current here.
        key = self._gizmo_cache[0] if self._gizmo_cache is not None else None
        cache = self._gizmo_frame_cache
        if key is None or cache is None or cache[0] != key:
            frame = transform_space.normal_frame(self.scene.mesh, self.selection)
            self._gizmo_frame_cache = (key, frame)
        else:
            frame = cache[1]
        if frame is None:
            return [], []
        edit = self.scene.edit_object

        def world(v):
            return object_space.axis_to_world(edit, v)

        axes = [(name, world(d)) for name, d in frame.axes()]
        planes = [(name, world(a), world(b)) for name, a, b in frame.planes()]
        return axes, planes

    @property
    def _gizmo_camera(self):
        """The gizmo lives in world space, at both levels: the pivot is a world point and the handles
        are the world axes. (While the edit object is unplaced this is the same camera as before.)"""
        return self.camera

    def gizmo_camera_uniforms(self) -> list[float]:
        """The `view` + `proj` uniforms `draw_gizmo` needs: no model matrix, the items are world points."""
        return self.viewport.world_camera_uniforms()

    def _gizmo_pivot_if_shown(self):
        """`_gizmo_pivot()` while the gizmo is up: not while a transform key is down, any drag gesture runs
        or the Re-Symmetrize preview is open."""
        if self._transform_key is not None or self._drag_select is not None or self._resym_plan is not None:
            return None
        return self._gizmo_pivot()

    @property
    def gizmo_tool(self) -> str:
        """The tool the gizmo shows and a handle drag runs (`move` / `rotate` / `scale`)."""
        return _GIZMO_TOOLS.get(self.tweak_command, "move")

    @property
    def gizmo_constraint(self) -> str | None:
        return self._axis_constraint

    def gizmo_items(self) -> list:
        """What the window draws for the gizmo (`viewport.gizmo.draw_items`), [] while it is not shown.
        The handle under the cursor is highlighted (hover feedback; it never arms anything)."""
        pivot = self._gizmo_pivot_if_shown()
        if pivot is None:
            return []
        camera = self._gizmo_camera
        hover = None
        if self._cursor is not None and not self.pointer.active:
            hover = self._gizmo_handle_at(*self._cursor, pivot=pivot)
        axes, planes = self._gizmo_frame()
        return _gizmo.draw_items(camera, pivot, self.gizmo_tool, self._axis_constraint, hover, axes, planes)

    def _gizmo_handle_at(self, x: float, y: float, pivot=None) -> str | None:
        pivot = self._gizmo_pivot_if_shown() if pivot is None else pivot
        if pivot is None:
            return None
        axes, planes = self._gizmo_frame()
        return _gizmo.pick_handle(
            self._gizmo_camera, pivot, axes, planes, self.gizmo_tool, x, y,
            int(self.viewport_width), int(self.viewport_height),
        )

    def _gizmo_press(self, input: Input) -> None:
        """LMB press without a modifier on a handle: it owns the gesture and sets the constraint now."""
        if not self.gizmo_enabled or input.value != "LEFT" or input.modifiers or self._cursor is None:
            return
        if self._gesture_refused:
            return
        handle = self._gizmo_handle_at(*self._cursor)
        if handle is None:
            return
        self._gizmo_gesture = handle
        self._gizmo_press_xy = tuple(self._cursor)
        # `center` (free Move / Rotate trackball / uniform Scale) and `screen` (Rotate about the view axis)
        # are the unconstrained handles.
        self._axis_constraint = None if handle in ("center", "screen") else handle
        self._set_hovered(None)
        self._set_status(f"Constraint: {_constraint_label(self._axis_constraint)}")

    def _gizmo_step(self, dx: float, dy: float) -> bool:
        """A drag step of a gesture that started on a handle: the first one arms the current tool on the
        selection (a Tweak with the selection as target), every step drives it."""
        if self._gesture_refused:
            return False
        if self._transform_key is None:
            if self.viewport is None or self._knife is not None or self._gate_refuses(commands.TWEAK):
                self._gesture_refused = True
                return False
            if not self._transform_arm(self.tweak_command, TWEAK_KEY):
                self._gesture_refused = True
                return False
        elif self._transform_key != TWEAK_KEY:
            return False
        stepped = self._transform_step(dx, dy)
        if self._transform_key is None:
            self._gesture_refused = True  # refused at begin (seam, symmetric Soft)
        return stepped

    def _gizmo_release(self, clicked: bool) -> bool:
        """LMB released: commit a running handle drag; a plain click on a handle leaves just the constraint."""
        self._gizmo_gesture = None
        self._gizmo_press_xy = None
        self._gesture_refused = False
        if self._transform_key == TWEAK_KEY:
            self._transform_finish()
            return True
        self._refresh_hover()
        return clicked

    # -- Tweak (2026-10-15, Tweak Lab V2 "Silo" KEEP, Manu: "Ctrl+LMB, Auswahl weicht") ------

    def _tweak_step(self, dx: float, dy: float) -> bool:
        """Ctrl+LMB drag: the first step arms `tweak_command` (the last W/E/R, Move by default)
        like holding its key - target = the selection, else the element under the press point
        (Tweak Lab rule; the selection is not changed) - and every step drives it. Ctrl may be
        let go during the drag; the LMB release commits, Esc cancels (`_cancel`)."""
        if self._gesture_refused:
            return False
        if self._transform_key is None:
            if self.viewport is None or self._knife is not None or self._gate_refuses(commands.TWEAK):
                self._gesture_refused = True
                return False
            if self.selection.mode is not SelectionMode.OBJECT:
                press = self._press_point if self._press_point is not None else self._cursor
                if not self._active_selection_ids() and press is not None:
                    self._set_hovered(self._pick(*press))
            if not self._transform_arm(self.tweak_command, TWEAK_KEY):
                self._gesture_refused = True
                return False
        elif self._transform_key != TWEAK_KEY:
            return False
        stepped = self._transform_step(dx, dy)
        if self._transform_key is None:
            # Refused at begin (seam, symmetric Soft): no re-arm until the release.
            self._gesture_refused = True
        return stepped

    def _camera_changed(self) -> None:
        if self.viewport is not None:
            self.viewport.on_camera_changed(self.viewport_width / self.viewport_height)

    def update_viewport(self, delta_t: float) -> None:
        """Viewport-Tick (delta_t in Sekunden).

        Gate 3: bewusst ein No-op (kein Viewport vorhanden). Existiert als
        stabiler Integrationspunkt.
        Gate 7: Ruft `Viewport.sync()` auf, wenn ein Viewport gebunden ist
        (nach `init_scene()`). Dadurch fließen Kamera-/Geometry-/Selection-
        Dirty-States in die GPU-Ressourcen. Ohne gebundenen Viewport
        (z. B. vor `init_scene()`) bleibt es ein No-Op.
        WP-VIEW-PERF-01 Slice 2: picks a hover left stale by `coalesce_hover` first
        (`flush_hover`), once per tick.
        """
        if self.viewport is not None:
            self.flush_hover()
            self._sync_object_highlight()
            self._push_region_tints()
            self.viewport.sync()

    def shutdown(self) -> None:
        """Sauberes Herunterfahren: aktives Tool deaktivieren (kein stale State);
        eine laufende Knife-Session wird verworfen (wie Esc)."""
        if self._knife is not None:
            self._knife_end(commit=False)
        self.tool_manager.deactivate()