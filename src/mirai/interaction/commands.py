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
# AD-021 M1: Objekt-Modus (V1_SPEC §2, Taste `4`).
SET_OBJECT_MODE = "SetObjectMode"

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
# SELECT_DRAG* sind Drag-Commands (2026-10-15, Box KEEP + Paint, Manu: "Startpunkt
# entscheidet"): der Press-Punkt entscheidet - im leeren Raum Box, auf dem Mesh Paint.
# SELECT_DRAG ersetzt die Auswahl, SELECT_DRAG_ADD fügt hinzu (Entfernen per Drag gibt es
# nicht: Ctrl+Drag ist Tweak, Manu 2026-10-15 "Auswahl weicht").
SELECT_DRAG = "SelectDrag"
SELECT_DRAG_ADD = "SelectDragAdd"
# LASSO_ARM (2026-10-21, Manu: "Lasso kommt auch in die Production"; Taste `PROVISIONAL`): solange die
# Taste gehalten wird, wird aus dem LMB-Drag (SELECT_DRAG / SELECT_DRAG_ADD) ein Lasso-Polygon statt
# Box/Paint. Wie W/E/R eine Halte-Taste; Shift fügt hinzu, kein Modifier ersetzt.
LASSO_ARM = "LassoArm"
# TWEAK (2026-10-15, Tweak Lab V2 "Silo" KEEP): Ctrl+LMB-Drag transformiert mit dem zuletzt
# gewählten W/E/R (Start: Move) die Auswahl, ohne Auswahl das Element unter dem Press-Punkt.
TWEAK = "Tweak"
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
# AD-021 M2-0 (§7.3 RD-2, `PROVISIONAL`): alle Referenzen schattiert <-> Ghost.
TOGGLE_REFERENCE_GHOST = "ToggleReferenceGhost"
# Worklight (Shading Lab promoted 2026-10-15; Tasten `PROVISIONAL`): Preset wechseln,
# Bezugsraum Kamera <-> Welt.
CYCLE_LIGHT_PRESET = "CycleLightPreset"
TOGGLE_LIGHT_SPACE = "ToggleLightSpace"

# TOGGLE_HUD (GUI Stufe 1, 2026-10-23; Artist Input Truth `application.toggle_hud` = H): die
# Zustandsanzeige des Fensters zeigen/verbergen. Ein Fenster-Command (Kontext `WINDOW_CONTEXT`):
# der Entry-Point (`src/main.py`, `src/hud.py`) löst ihn über die Bindings auf und behandelt ihn
# selbst, `Application` kennt ihn nicht (sie besitzt keinen HUD-Zustand).
TOGGLE_HUD = "ToggleHud"

# --- Objekt-Platzierung (AD-021 M2-3, L-3; Namen und Tasten `PROVISIONAL`) ----
# Apply = Platzierung ins Mesh übernehmen (Max "Reset XForm"); Clear = Platzierung auf
# Identität, das Mesh bleibt, das Objekt springt. Nur in Modus `4`.
APPLY_TRANSFORM = "ApplyTransform"
CLEAR_TRANSFORM = "ClearTransform"
# Referenz an/aus für die in Modus `4` ausgewählten Objekte (Manu 2026-10-16: ein einfacher Klick,
# der umschaltet, ist verwirrend - Q-12 revidiert; Taste `PROVISIONAL`).
TOGGLE_REFERENCE = "ToggleReference"

# CONNECT (WP-06 B6, AD-017 "Contextual C"): global, nicht Topology-Lab —
# 1 Edge selektiert → Split; 2+ Edges → Edge Connect (per-face); 2+ Vertices
# → Vertex Connect (per-face); leere Auswahl → Knife-Session (WP-06 B7).
# Siehe `mirai.topology.contextual_c` /
# `mirai.application.Application._connect_command`.
CONNECT = "Connect"
# KNIFE_COMMIT (WP-06 B7, Artist Input Truth `topology.knife_commit`): schließt
# eine laufende Knife-Session als genau einen History-Eintrag ab. Nur im
# KNIFE_CONTEXT gebunden (Enter). Abbrechen = CANCEL, Undo/Redo des letzten
# Schnitts = UNDO/REDO, während der Session auf die Session-History geroutet.
KNIFE_COMMIT = "KnifeCommit"
# KNIFE_LIFT (WP-KNIFE-01 UX2, Artist Input Truth `topology.knife_lift`, Manu
# 2026-10-02): Stift absetzen — beendet die aktuelle Kette der Knife-Session
# ohne Commit, der nächste Klick beginnt eine neue. Nur im KNIFE_CONTEXT
# gebunden (E und ein RMB-Klick, Blender 2.79 / 3.0+ "New Cut").
KNIFE_LIFT = "KnifeLift"

# DELETE / DISSOLVE / DISSOLVE_NO_CLEANUP (WP Delete/Dissolve, docs/
# WP_DELETE_DISSOLVE_PLAN.md): global, wirken auf die Auswahl des aktiven
# Komponentenmodus. DELETE entfernt destruktiv (Loch). DISSOLVE entfernt
# bewahrend mit Cleanup (Edge/Face: übrig bleibende 2er-Vertices weg) und ist
# im Vertex-Modus die eine Vertex-Dissolve-Operation; DISSOLVE_NO_CLEANUP lässt
# die 2er-Vertices stehen und hat im Vertex-Modus keine Wirkung (keine
# Variante, §0.2.2). Welche Taste welche Variante trägt, entscheidet allein die
# Bindung. Siehe `mirai.topology.delete_dissolve` /
# `mirai.application.Application._removal_command`.
DELETE = "Delete"
DISSOLVE = "Dissolve"
DISSOLVE_NO_CLEANUP = "DissolveNoCleanup"

# SYMMETRY_CYCLE (AD-SYM-04 Slice A1, Q-1 = E-1, Manu 2026-10-14): global; schaltet die
# Symmetrie-Definition des Meshs aus → X → Y → Z → aus (E1-Ebene durch den Ursprung, E3-Seam,
# `mirai.symmetry_axis`), je ein Undo-Schritt. Ignoriert, solange W/E/R/T scharf ist oder eine
# Knife-Session läuft (wie `C`). Siehe `mirai.application.Application._symmetry_cycle`.
SYMMETRY_CYCLE = "SymmetryCycle"

# --- Topology Lab (Context "topology") ------------------------------------
SPLIT_EDGE = "SplitEdge"
# COLLAPSE (WP Toolbox Gaps B1, Manu 2026-10-23): global on Shift+C, no longer a Topology-Lab
# command. Each connected group of the V/E/F selection falls into one point at its centroid
# (`mirai.topology.collapse`, `mirai.application.Application._collapse_command`).
COLLAPSE = "Collapse"
EDGE_LOOP = "EdgeLoop"
EDGE_RING = "EdgeRing"
LOOP_INSERT = "LoopInsert"
LOOP_SLIDE = "LoopSlide"
# EXTRUDE (WP-06 B9): global, hold-key-hover like Move/Rotate/Scale - routed via
# tool_for_command() to `mirai.topology.extrude.ExtrudeTool`; the Topology-Lab
# Alt+E binding is gone. Face mode only.
EXTRUDE = "Extrude"

# SMOOTH / RELAX (WP Toolbox Gaps C2, Manu 2026-10-23): global hold keys like G. A tap = one fixed step,
# hold + drag right/left = more/less strength live, release commits, Esc restores
# (`mirai.topology.smooth`, `Application._smooth_*`). Keys S / Alt+S are `PROVISIONAL`.
SMOOTH = "Smooth"
RELAX = "Relax"

# TOGGLE_TRANSFORM_SPACE (WP Toolbox Gaps C1, the Playground's `K`, `PROVISIONAL`): global, World <->
# Normal for the axis constraints and the gizmo (`mirai.transform_space`); state like a constraint.
TOGGLE_TRANSFORM_SPACE = "ToggleTransformSpace"

# --- Selection steps (WP Toolbox Gaps A1, Manu 2026-10-23; `mirai.topology.selection_steps`) ---
# Global, like Shift+L / Shift+R: no History step (a selection change, like a click).
# SELECT_GROW / SELECT_SHRINK: active mode V/E/F. LOOP_GROW / LOOP_SHRINK (Shift+Up / Shift+Down,
# Manu): the open pieces of selected loop edges at both ends. LOOP_NEXT / LOOP_PREVIOUS
# (Shift+Right / Shift+Left, Manu): the parallel loop on that screen side. Loop steps: edge mode.
SELECT_GROW = "SelectGrow"
SELECT_SHRINK = "SelectShrink"
LOOP_GROW = "LoopGrow"
LOOP_SHRINK = "LoopShrink"
LOOP_NEXT = "LoopNext"
LOOP_PREVIOUS = "LoopPrevious"

# --- Soft Selection (WP-SOFT-01 S2a, AD-020; PROVISIONAL) --------------------------
# State commands like the constraints: they start no interaction and change no mesh;
# they set the sticky soft settings that the next gesture reads at begin(). Which input
# carries which command is the binding's business (the radius direction included).
SOFT_TOGGLE = "SoftToggle"
SOFT_RADIUS_UP = "SoftRadiusUp"
SOFT_RADIUS_DOWN = "SoftRadiusDown"
SOFT_CURVE_CYCLE = "SoftCurveCycle"
SOFT_METRIC_CYCLE = "SoftMetricCycle"
# S2d (S2c verdict, Manu 2026-10-11): Ctrl+wheel shapes the `custom` curve (rounder = smaller
# exponent, sharper = larger; selecting `custom` is part of it); the bands can be switched off.
SOFT_CURVE_SHAPE_ROUNDER = "SoftCurveShapeRounder"
SOFT_CURVE_SHAPE_SHARPER = "SoftCurveShapeSharper"
SOFT_BANDS_TOGGLE = "SoftBandsToggle"
#: 2026-10-22 (`PROVISIONAL`): vertex bands <-> face shading; display only, like SOFT_BANDS_TOGGLE.
SOFT_VIEW_MODE_CYCLE = "SoftViewModeCycle"
#: 2026-10-22 (`PROVISIONAL`): the look of the influence display (mono / tint / color); display only.
SOFT_LOOK_CYCLE = "SoftLookCycle"
#: 2026-10-22 (`PROVISIONAL`, AD-020 "Loop / Ring flow"): the Loop / Ring balance one step towards Loop / Ring;
#: sticky, and taken live by a running Soft gesture like the radius.
SOFT_FLOW_LOOP = "SoftFlowLoop"
SOFT_FLOW_RING = "SoftFlowRing"

# --- SubD preview (2026-10-23, `mirai.subdivision`; keys `PROVISIONAL`, context "subd") ------
#: View state only (no mesh change, no History): off -> smooth + cage -> smooth + isolines.
SUBD_CYCLE_VIEW = "SubdCycleView"
SUBD_LEVEL_1 = "SubdLevel1"
SUBD_LEVEL_2 = "SubdLevel2"
SUBD_LEVEL_3 = "SubdLevel3"
#: The cage hidden by the smooth surface <-> always visible.
SUBD_TOGGLE_CAGE_DEPTH = "SubdToggleCageDepth"
#: The opacity of the secondary line system (the cage in the isoline view), one step.
SUBD_CYCLE_SECONDARY = "SubdCycleSecondary"

# --- Articulation (EX-A / H02) -----------------------------------------------
ARTICULATION_RESTORE = "ArticulationRestore"