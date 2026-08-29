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
# SELECT deckt den bestehenden LMB-Fall ab: Klick toggelt die Selection,
# ein Drag auf der Selection startet die Move-Interaktion (V1-Verhalten).
SELECT = "Select"
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

# --- Topology Lab (Context "topology") ------------------------------------
SPLIT_EDGE = "SplitEdge"
COLLAPSE = "Collapse"
CONNECT_VERTICES = "ConnectVertices"
CONNECT_EDGES = "ConnectEdges"
EDGE_LOOP = "EdgeLoop"
EDGE_RING = "EdgeRing"