"""The point-layer operation gate (AD-025 §4.4, ARCH-02 Phase 2): which operations may run on a mesh
that has point layers (morph targets). Module name and texts `PROVISIONAL`.

Fail-closed, keyed as in AD-SYM-03 D-b: an operation runs on a layered mesh only if it is
classified as not changing a mesh, as changing positions only (the edit rule, §4.3: layers are left
as they are), or declared in `LAYER_SAFE_OPERATIONS` - whose value is the implementation the app
runs (plain and symmetric), so a rename fails loudly and `tests/test_layer_gate.py` runs every entry
against its rule on a plain and a symmetric layered fixture. Everything else is locked with a
status line. The table is H1 (AD-025 §10, `PROVISIONAL` default): allowed are Delete, Dissolve,
Vertex Connect, Cap and every position-only tool; locked until Phase 5 are Split, Edge Connect, Loop
Insert, Knife, Extrude, Collapse and mirror copy; Apply transform is locked until Phase 3 wires the
frame map (`Mesh.map_vector_layers`).

Key space: every `mirai.interaction.commands` constant (`COMMAND_CLASSES`), the resolved `C` context
(`CContext`, checked after `resolve_c_context`) and the public `Application` methods that can change
or copy a mesh (`METHOD_CLASSES`, incl. the `scene_menu.MIRROR_ENTRIES` methods). The enumeration
test lists them from the code; an unclassified one fails. Checked per target mesh: the edit mesh for
component commands, every baked object's mesh for Apply transform, the source for mirror copy. No
layers: no lookup. The Core backstop (`Mesh.add_vertex` without an origin, `split_face` with interior
points) catches what a forgotten declaration would let through on the host path
(`apply_mesh_change`, labs). The module depends on `core`, `mirai.topology` and `mirai.symmetric_ops`,
never on `application`.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from .interaction import commands
from .symmetric_ops import (
    coordinate_cap,
    coordinate_delete,
    coordinate_dissolve,
    coordinate_dissolve_no_cleanup,
    coordinate_vertex_connect,
)
from .topology.border import apply_cap
from .topology.connect_vertices_per_face import apply_connect_vertices
from .topology.contextual_c import CContext
from .topology.delete_dissolve import apply_removal

#: Declared operations (H1 "allowed" topology rows): key -> (plain implementation, symmetric
#: implementation), exactly the functions `Application` runs for that key. Each one creates no vertex
#: (Vertex Connect, Cap) or only removes vertices (Delete, Dissolve; the Core deletes their values).
LAYER_SAFE_OPERATIONS: Mapping[Any, tuple] = MappingProxyType(
    {
        CContext.VERTEX_CONNECT: (apply_connect_vertices, coordinate_vertex_connect),
        commands.DELETE: (apply_removal, coordinate_delete),
        commands.DISSOLVE: (apply_removal, coordinate_dissolve),
        commands.DISSOLVE_NO_CLEANUP: (apply_removal, coordinate_dissolve_no_cleanup),
        commands.CAP: (apply_cap, coordinate_cap),
    }
)

NON_MESH = "non-mesh"
POSITION_ONLY = "position-only"
DECLARED = "declared"
RESOLVED = "resolved"  # gated where the operation is resolved (C: the context)
LOCKED = "locked"

_NON_MESH_COMMANDS = (
    commands.SET_VERTEX_MODE, commands.SET_EDGE_MODE, commands.SET_FACE_MODE, commands.SET_OBJECT_MODE,
    commands.UNDO, commands.REDO, commands.CANCEL, commands.CLEAR_SELECTION,
    commands.SELECT, commands.SELECT_ADD, commands.SELECT_REMOVE, commands.SELECT_TOGGLE,
    commands.SELECT_DRAG, commands.SELECT_DRAG_ADD, commands.LASSO_ARM,
    commands.SELECT_GROW, commands.SELECT_SHRINK, commands.LOOP_GROW, commands.LOOP_SHRINK,
    commands.LOOP_NEXT, commands.LOOP_PREVIOUS, commands.EDGE_LOOP, commands.EDGE_RING, commands.BORDER_SELECT,
    commands.CONSTRAIN_AXIS_X, commands.CONSTRAIN_AXIS_Y, commands.CONSTRAIN_AXIS_Z,
    commands.CONSTRAIN_PLANE_XY, commands.CONSTRAIN_PLANE_XZ, commands.CONSTRAIN_PLANE_YZ,
    commands.TOGGLE_TRANSFORM_SPACE, commands.ORBIT, commands.PAN, commands.ZOOM,
    commands.CYCLE_DISPLAY_MODE, commands.TOGGLE_WIREFRAME_OVERLAY, commands.SET_SHADED,
    commands.SET_FLAT_SHADED, commands.SET_WIREFRAME, commands.TOGGLE_REGION_TINT,
    commands.TOGGLE_REFERENCE_GHOST, commands.CYCLE_LIGHT_PRESET, commands.TOGGLE_LIGHT_SPACE,
    commands.LOOK_ROW_PREV, commands.LOOK_ROW_NEXT, commands.LOOK_VALUE_DEC, commands.LOOK_VALUE_INC,
    commands.LOOK_VALUE_DEC_FINE, commands.LOOK_VALUE_INC_FINE, commands.LIGHT_DRAG, commands.TOGGLE_HUD,
    # object level: placement, state and objects, never a mesh's content (Delete in `4` removes objects)
    commands.CLEAR_TRANSFORM, commands.TOGGLE_REFERENCE,
    # the symmetry definition, mask, hide and saved regions are not layer data
    commands.SYMMETRY_CYCLE, commands.MASK_TOGGLE, commands.MASK_INVERT, commands.MASK_CLEAR,
    commands.GROUP_MASK_TOGGLE, commands.HIDE_SELECTION, commands.ISOLATE_SELECTION, commands.SHOW_ALL,
    commands.REGION_NEXT, commands.REGION_PREV, commands.REGION_NEW, commands.REGION_NAME, commands.REGION_ADD,
    commands.REGION_REMOVE, commands.REGION_SELECT, commands.REGION_SELECT_ADD, commands.REGION_ISOLATE,
    commands.REGION_MASK, commands.REGION_DELETE, commands.REGION_CLICK,
    commands.SOFT_TOGGLE, commands.SOFT_RADIUS_UP, commands.SOFT_RADIUS_DOWN, commands.SOFT_CURVE_CYCLE,
    commands.SOFT_METRIC_CYCLE, commands.SOFT_CURVE_SHAPE_ROUNDER, commands.SOFT_CURVE_SHAPE_SHARPER,
    commands.SOFT_BANDS_TOGGLE, commands.SOFT_VIEW_MODE_CYCLE, commands.SOFT_LOOK_CYCLE,
    commands.SOFT_FLOW_LOOP, commands.SOFT_FLOW_RING,
    commands.SUBD_CYCLE_VIEW, commands.SUBD_LEVEL_1, commands.SUBD_LEVEL_2, commands.SUBD_LEVEL_3,
    commands.SUBD_TOGGLE_CAGE_DEPTH, commands.SUBD_CYCLE_SECONDARY,
)

#: Positions only (AD-025 §4.3 edit rule; contract test: layers bit-identical afterwards). In `4`,
#: W/E/R are the object gesture (placement only).
_POSITION_ONLY_COMMANDS = (
    commands.MOVE, commands.ROTATE, commands.SCALE, commands.TWEAK, commands.LOOP_SLIDE,
    commands.SMOOTH, commands.RELAX, commands.RESYMMETRIZE,
)

#: H1 locked: topology the Core has a rule for but the tool or its symmetric path does not yet
#: (Phase 5), a frame change not yet wired (Apply transform, Phase 3), the Knife session keys (the
#: session itself is locked at `C`), and constants no `Application` path handles (fail-closed).
_LOCKED_COMMANDS = (
    commands.EXTRUDE, commands.COLLAPSE, commands.LOOP_INSERT, commands.APPLY_TRANSFORM,
    commands.SPLIT_EDGE, commands.KNIFE_COMMIT, commands.KNIFE_LIFT, commands.ARTICULATION_RESTORE,
)

#: Commands whose target meshes are not the edit mesh: checked at their own site with every mesh
#: they change (Apply transform bakes every placed object of the selection, F-7), not at dispatch.
PER_TARGET_COMMANDS = frozenset({commands.APPLY_TRANSFORM})

#: Command constant -> class. Declared commands are the command keys of `LAYER_SAFE_OPERATIONS`.
COMMAND_CLASSES: Mapping[str, str] = MappingProxyType(
    {
        **{c: NON_MESH for c in _NON_MESH_COMMANDS},
        **{c: POSITION_ONLY for c in _POSITION_ONLY_COMMANDS},
        **{c: LOCKED for c in _LOCKED_COMMANDS},
        commands.CONNECT: RESOLVED,
        **{c: DECLARED for c in LAYER_SAFE_OPERATIONS if isinstance(c, str)},
    }
)

#: Resolved `C` context -> class (the declared one is in `LAYER_SAFE_OPERATIONS`).
CONTEXT_CLASSES: Mapping[CContext, str] = MappingProxyType(
    {
        CContext.SPLIT: LOCKED,
        CContext.EDGE_CONNECT: LOCKED,
        CContext.KNIFE: LOCKED,
        CContext.VERTEX_CONNECT: DECLARED,
        CContext.NONE: NON_MESH,  # resolves to no operation
    }
)

#: Public `Application` methods that can reach a mesh change or build a mesh from another -> how they
#: are gated. "commands": through the command classes above (key / pointer / dispatch paths);
#: "new mesh": a new ID space without layers, or a file that restores its own layers; "host": the
#: external-host entry, which gets the Core backstop (AD-025 §4.4); "non-mesh": objects / pairs only;
#: LOCKED: refused while its source has layers (mirror copy, Phase 5).
METHOD_CLASSES: Mapping[str, str] = MappingProxyType(
    {
        "dispatch_command": "commands",
        "key_press": "commands",
        "key_release": "commands",
        "pointer_drag": "commands",
        "pointer_motion": "commands",
        "pointer_release": "commands",
        "pointer_scroll": "commands",
        "set_ctrl_held": "commands",
        "add_primitive": "new mesh",
        "add_reference": "new mesh",
        "import_obj": "new mesh",
        "init_scene": "new mesh",
        "load_scene": "new mesh",
        "apply_mesh_change": "host",
        "pair_selected": "non-mesh",
        "break_mirror_pairs": "non-mesh",
        "resync_mirror_pairs": "non-mesh",
        "mirror_copy": LOCKED,
    }
)

#: Status text per locked key (`PROVISIONAL`).
_LABELS: Mapping[Any, str] = MappingProxyType(
    {
        CContext.SPLIT: "Split",
        CContext.EDGE_CONNECT: "Connect Edges",
        CContext.KNIFE: "Knife",
        commands.EXTRUDE: "Extrude",
        commands.COLLAPSE: "Collapse",
        commands.LOOP_INSERT: "Loop Insert",
        commands.APPLY_TRANSFORM: "Apply transform",
        "mirror_copy": "Mirror copy",
    }
)


def layer_refusal(key: Any) -> str | None:
    """The refusal text for `key` (a command constant, a `CContext` or a method name) on a mesh with
    point layers; None = allowed. Unknown keys are refused (fail-closed)."""
    if key in LAYER_SAFE_OPERATIONS:
        return None
    if isinstance(key, CContext):
        cls = CONTEXT_CLASSES.get(key)
    else:
        cls = COMMAND_CLASSES.get(key)
        if cls is None:
            cls = METHOD_CLASSES.get(key)
    if cls in (NON_MESH, POSITION_ONLY, RESOLVED, "commands", "new mesh", "host", "non-mesh"):
        return None
    label = _LABELS.get(key, getattr(key, "name", None) or str(key))
    return f"{label}: locked while this mesh has morph targets"
