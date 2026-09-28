"""Benannte User-Commands für den Viewport-Praxistest.

Vertrag: INPUT_COMMAND_TOOL_CONTRACT.md — ein Command ist eine benannte
Benutzeraktion, KEIN Hotkey und KEIN physischer Input. Ein Hotkey/Mouse-
Binding ist nur eine von mehreren möglichen Möglichkeiten, ein Command
aufzurufen.

Diese Konstanten sind bewusst schlichte Strings (kein Framework). Sie
werden von `input_binding.BindingSet` und den Window-Klassen verwendet.
"""

from __future__ import annotations

# --- Selection Modes -----------------------------------------------------
SET_VERTEX_MODE = "SetVertexMode"
SET_EDGE_MODE = "SetEdgeMode"
SET_FACE_MODE = "SetFaceMode"

# --- History --------------------------------------------------------------
UNDO = "Undo"
REDO = "Redo"

# --- Interaktion ----------------------------------------------------------
# SELECT* sind Klick-Commands (WP-06 B2, Selection-Modifier-Variante AP-03):
# SELECT ersetzt die Auswahl durch das getroffene Element (Klick ins Leere
# leert sie); ADD/REMOVE/TOGGLE ändern nur das getroffene Element, ein Klick
# ins Leere lässt die Auswahl unverändert.
SELECT = "Select"
SELECT_ADD = "SelectAdd"
SELECT_REMOVE = "SelectRemove"
SELECT_TOGGLE = "SelectToggle"
# MOVE ist das explizite modale Move-Command (WP-02): Es wird über die
# Mapping-Schicht auf das MoveTool geroutet — Bindings (z. B. M oder G)
# verändern das Tool nicht.
MOVE = "Move"
# ROTATE/SCALE sind die modalen Transform-Commands (WP-03): Routing über
# tool_for_command() auf RotateTool/ScaleTool, gleiche Lifecycle-Verträge.
ROTATE = "Rotate"
SCALE = "Scale"
# CONSTRAIN_* schalten einen sticky Achsen-/Ebenen-Constraint um (WP-06 B4,
# Modell seit B4.1 wie im Playground: Toggle, gilt für jede folgende Transform-
# Geste, auch ohne gehaltenes Tool). Die Ebenen-Commands benennen die Ebene;
# welche Taste sie auslöst (Blender: Shift+Achse schließt diese Achse aus),
# entscheidet allein die Bindung.
CONSTRAIN_AXIS_X = "ConstrainAxisX"
CONSTRAIN_AXIS_Y = "ConstrainAxisY"
CONSTRAIN_AXIS_Z = "ConstrainAxisZ"
CONSTRAIN_PLANE_XY = "ConstrainPlaneXY"
CONSTRAIN_PLANE_XZ = "ConstrainPlaneXZ"
CONSTRAIN_PLANE_YZ = "ConstrainPlaneYZ"
CLEAR_SELECTION = "ClearSelection"
CANCEL = "Cancel"

# --- Navigation (Viewport-only, keine Model-Operation) --------------------
ORBIT = "Orbit"
PAN = "Pan"
ZOOM = "Zoom"

# --- Display Modes / Viewport-Anzeige (Viewport-only) ---------------------
CYCLE_DISPLAY_MODE = "CycleDisplayMode"
TOGGLE_WIREFRAME_OVERLAY = "ToggleWireframeOverlay"
SET_SHADED = "SetShaded"
SET_FLAT_SHADED = "SetFlatShaded"
SET_WIREFRAME = "SetWireframe"

# CONNECT (WP-06 B6, AD-017 "Contextual C"): global, nicht Topology-Lab —
# 1 Edge selektiert → Split; 2+ Edges → Edge Connect (per-face); 2+ Vertices
# → Vertex Connect (per-face); leere Auswahl → Knife (in Production noch
# nicht implementiert, No-op). Siehe `mirai.topology.contextual_c` /
# `mirai.application.Application._connect_command`.
CONNECT = "Connect"

# --- Topology Lab (Context "topology") ------------------------------------
SPLIT_EDGE = "SplitEdge"
COLLAPSE = "Collapse"
EDGE_LOOP = "EdgeLoop"
EDGE_RING = "EdgeRing"
LOOP_INSERT = "LoopInsert"
LOOP_SLIDE = "LoopSlide"
EXTRUDE = "Extrude"

# --- Articulation (EX-A / H02) -----------------------------------------------
ARTICULATION_RESTORE = "ArticulationRestore"