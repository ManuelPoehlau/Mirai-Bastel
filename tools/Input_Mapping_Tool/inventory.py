"""Default Artist-Truth interaction inventory for Mirai-Bastel.

This module defines the *semantic* interaction vocabulary the Input Binding
Config tool operates on. It is entirely self-owned:

- Every entry has a stable dotted ``id`` (e.g. ``transform.move``) that is
  the tool's own identity, not a reference into any runtime module.
- ``runtime_ref`` is an OPTIONAL, purely informational note pointing at the
  current name in ``src/mirai/interaction/commands.py`` when one happens to
  exist for that function at the time this list was written. It is a plain
  string, never imported from that module. An entry with ``runtime_ref =
  None`` is just as valid as one with a match — the config must stay usable
  even for functions the runtime does not implement yet, and even if the
  runtime vocabulary is renamed or restructured later.

Deliberately excluded (see the implementation proposal / chat record):
- "Transform Interaction Variants" (Tweak V1-V4 etc.) and "Experiment /
  Playground Controls" (KEEP/ITERATE/REJECT, variant cycling). These are
  active Three-Role-UX-System / Playground research surfaces, not stable
  artist-facing product functions, and don't belong in a binding config.

This file contains only the INITIAL seed inventory. Once
``artist_input_truth.json`` exists, it — not this file — is what the tool
reads and writes. Re-running the seed never overwrites an existing config
(see storage.py).
"""

from __future__ import annotations

# Each entry: (id, label, category, runtime_ref)
# `binding` and `notes` are NOT stored here — they live only in the
# artist-owned JSON file, seeded to "" on first run.

DEFAULT_INVENTORY: list[dict[str, str | None]] = [
    # --- Navigation ---------------------------------------------------
    {"id": "navigation.orbit", "label": "Orbit", "category": "Navigation", "runtime_ref": "Orbit"},
    {"id": "navigation.pan", "label": "Pan", "category": "Navigation", "runtime_ref": "Pan"},
    {"id": "navigation.zoom", "label": "Zoom", "category": "Navigation", "runtime_ref": "Zoom"},
    {"id": "navigation.frame_selection", "label": "Frame / Focus Selection", "category": "Navigation", "runtime_ref": None},
    {"id": "navigation.reset_view", "label": "Reset / Home View", "category": "Navigation", "runtime_ref": None},

    # --- Selection Mode -------------------------------------------------
    {"id": "selection.set_vertex_mode", "label": "Vertex Selection Mode", "category": "Selection Mode", "runtime_ref": "SetVertexMode"},
    {"id": "selection.set_edge_mode", "label": "Edge Selection Mode", "category": "Selection Mode", "runtime_ref": "SetEdgeMode"},
    {"id": "selection.set_face_mode", "label": "Face Selection Mode", "category": "Selection Mode", "runtime_ref": "SetFaceMode"},

    # --- Selection Behavior ----------------------------------------------
    {"id": "selection.replace", "label": "Replace Selection", "category": "Selection Behavior", "runtime_ref": None},
    {"id": "selection.toggle", "label": "Toggle Selection", "category": "Selection Behavior", "runtime_ref": None},
    {"id": "selection.modifier", "label": "Modifier Selection", "category": "Selection Behavior", "runtime_ref": None},
    {"id": "selection.box_select", "label": "Box Select", "category": "Selection Behavior", "runtime_ref": None},
    {"id": "selection.lasso_select", "label": "Lasso Select", "category": "Selection Behavior", "runtime_ref": None},
    {"id": "selection.paint_select", "label": "Paint Select", "category": "Selection Behavior", "runtime_ref": None},
    {"id": "selection.face_picking", "label": "Face Picking", "category": "Selection Behavior", "runtime_ref": "Select"},
    {"id": "selection.hover_preview", "label": "Hover / Preview Selection", "category": "Selection Behavior", "runtime_ref": None},
    {"id": "selection.add", "label": "Add to Selection", "category": "Selection Behavior", "runtime_ref": None},
    {"id": "selection.remove", "label": "Remove from Selection", "category": "Selection Behavior", "runtime_ref": None},
    {"id": "selection.clear", "label": "Clear Selection", "category": "Selection Behavior", "runtime_ref": "ClearSelection"},
    {"id": "selection.select_all", "label": "Select All", "category": "Selection Behavior", "runtime_ref": None},
    {"id": "selection.invert", "label": "Invert Selection", "category": "Selection Behavior", "runtime_ref": None},

    # --- Transform ---------------------------------------------------
    {"id": "transform.move", "label": "Move", "category": "Transform", "runtime_ref": "Move"},
    {"id": "transform.rotate", "label": "Rotate", "category": "Transform", "runtime_ref": "Rotate"},
    {"id": "transform.scale", "label": "Scale", "category": "Transform", "runtime_ref": "Scale"},

    # --- Transform Constraints -----------------------------------------
    {"id": "transform.move_axis_x", "label": "Move X Axis", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.move_axis_y", "label": "Move Y Axis", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.move_axis_z", "label": "Move Z Axis", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.move_plane_xy", "label": "Move XY Plane", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.move_plane_xz", "label": "Move XZ Plane", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.move_plane_yz", "label": "Move YZ Plane", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.rotate_axis_x", "label": "Rotate X Axis", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.rotate_axis_y", "label": "Rotate Y Axis", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.rotate_axis_z", "label": "Rotate Z Axis", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.scale_axis_x", "label": "Scale X Axis", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.scale_axis_y", "label": "Scale Y Axis", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.scale_axis_z", "label": "Scale Z Axis", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.scale_plane_xy", "label": "Scale XY Plane", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.scale_plane_xz", "label": "Scale XZ Plane", "category": "Transform Constraints", "runtime_ref": None},
    {"id": "transform.scale_plane_yz", "label": "Scale YZ Plane", "category": "Transform Constraints", "runtime_ref": None},

    # --- Topology ---------------------------------------------------
    {"id": "topology.extrude", "label": "Extrude", "category": "Topology", "runtime_ref": "Extrude"},
    {"id": "topology.connect", "label": "Connect Edges", "category": "Topology", "runtime_ref": "Connect"},
    {"id": "topology.split_edge", "label": "Split Edge", "category": "Topology", "runtime_ref": "SplitEdge"},
    {"id": "topology.collapse", "label": "Collapse", "category": "Topology", "runtime_ref": "Collapse"},
    {"id": "topology.edge_loop_select", "label": "Loop Select", "category": "Topology", "runtime_ref": "EdgeLoop"},
    {"id": "topology.edge_ring_select", "label": "Ring Select", "category": "Topology", "runtime_ref": "EdgeRing"},
    {"id": "topology.loop_insert", "label": "Loop Insert", "category": "Topology", "runtime_ref": "LoopInsert"},
    {"id": "topology.loop_slide", "label": "Loop Slide", "category": "Topology", "runtime_ref": "LoopSlide"},
    {"id": "topology.restore_articulation", "label": "Restore Articulation", "category": "Topology", "runtime_ref": "ArticulationRestore"},
    {"id": "topology.cancel_operation", "label": "Cancel Current Operation", "category": "Topology", "runtime_ref": "Cancel"},
    {"id": "topology.undo", "label": "Undo", "category": "Topology", "runtime_ref": "Undo"},
    {"id": "topology.redo", "label": "Redo", "category": "Topology", "runtime_ref": "Redo"},

    # --- Display / Presentation ------------------------------------------
    {"id": "display.cycle_display_mode", "label": "Cycle Display Mode", "category": "Display", "runtime_ref": "CycleDisplayMode"},
    {"id": "display.toggle_wireframe_overlay", "label": "Toggle Wireframe Overlay", "category": "Display", "runtime_ref": "ToggleWireframeOverlay"},
    {"id": "display.set_shaded", "label": "Set Shaded", "category": "Display", "runtime_ref": "SetShaded"},
    {"id": "display.set_flat_shaded", "label": "Set Flat Shaded", "category": "Display", "runtime_ref": "SetFlatShaded"},
    {"id": "display.set_wireframe", "label": "Set Wireframe", "category": "Display", "runtime_ref": "SetWireframe"},
    {"id": "display.toggle_vertex_display", "label": "Toggle Vertex Display", "category": "Display", "runtime_ref": None},

    # --- Modeling / Component Operations ---------------------------------
    {"id": "modeling.vertex_move", "label": "Vertex Move", "category": "Modeling", "runtime_ref": None},
    {"id": "modeling.edge_move", "label": "Edge Move", "category": "Modeling", "runtime_ref": None},
    {"id": "modeling.face_move", "label": "Face Move", "category": "Modeling", "runtime_ref": None},
    {"id": "modeling.vertex_rotate", "label": "Vertex Rotate", "category": "Modeling", "runtime_ref": None},
    {"id": "modeling.edge_rotate", "label": "Edge Rotate", "category": "Modeling", "runtime_ref": None},
    {"id": "modeling.face_rotate", "label": "Face Rotate", "category": "Modeling", "runtime_ref": None},
    {"id": "modeling.vertex_scale", "label": "Vertex Scale", "category": "Modeling", "runtime_ref": None},
    {"id": "modeling.edge_scale", "label": "Edge Scale", "category": "Modeling", "runtime_ref": None},
    {"id": "modeling.face_scale", "label": "Face Scale", "category": "Modeling", "runtime_ref": None},
    {"id": "modeling.delete_component", "label": "Delete Component", "category": "Modeling", "runtime_ref": None},
    {"id": "modeling.duplicate_component", "label": "Duplicate Component", "category": "Modeling", "runtime_ref": None},
    {"id": "modeling.merge_weld", "label": "Merge / Weld", "category": "Modeling", "runtime_ref": None},

    # --- History ------------------------------------------------------
    {"id": "history.undo", "label": "Undo", "category": "History", "runtime_ref": "Undo"},
    {"id": "history.redo", "label": "Redo", "category": "History", "runtime_ref": "Redo"},

    # --- Application / General -------------------------------------------
    {"id": "application.cancel", "label": "Cancel", "category": "Application", "runtime_ref": "Cancel"},
    {"id": "application.confirm", "label": "Confirm / Commit", "category": "Application", "runtime_ref": None},
    {"id": "application.save", "label": "Save", "category": "Application", "runtime_ref": None},
    {"id": "application.load", "label": "Load", "category": "Application", "runtime_ref": None},
    {"id": "application.quit", "label": "Quit", "category": "Application", "runtime_ref": None},
    {"id": "application.toggle_hud", "label": "Toggle HUD", "category": "Application", "runtime_ref": None},
    {"id": "application.toggle_debug_info", "label": "Toggle Debug Information", "category": "Application", "runtime_ref": None},
]

# Display order for categories (top to bottom in the tool's tree view).
CATEGORY_ORDER: list[str] = [
    "Navigation",
    "Selection Mode",
    "Selection Behavior",
    "Transform",
    "Transform Constraints",
    "Topology",
    "Display",
    "Modeling",
    "History",
    "Application",
]
