"""Default-Key- und Mouse-Bindings für den Viewport-Praxistest.

Abgeleitet aus dem bisherigen V1-Verhalten (siehe README/SELECTION_MODES):
- 1, 2, 3        → Vertex-/Edge-/Face-Modus (Artist Input Truth; die Legacy-
                   Tasten V/F sind seit WP-06 B5b entfernt, E47)
- Ctrl+Z / Ctrl+Y → Undo / Redo
- Esc             → laufende Interaktion abbrechen
- Wheel           → Zoom (Dolly)

Maus (WP-06 B2, Artist Input Truth + Selection-Modifier-Variante AP-03):
`mouse` = Klick, `drag` = Press + Bewegung ≥ Schwelle (AD-019). Dieselbe
physische Taste kann beides tragen; `pointer.PointerGestures` entscheidet.
- LMB-Klick       → Select (Replace; Klick ins Leere leert)
- Shift+LMB-Klick → SelectAdd, Ctrl+LMB-Klick → SelectRemove
- Alt+LMB-Klick   → SelectToggle
- Alt+LMB-Drag    → Orbit, Alt+Shift+LMB-Drag → Pan
- RMB/MMB         → bewusst ungebunden (eine Primärbindung pro Funktion,
                    AD-013 Truth-Regel 2)

Display (Artist Input Truth, WP-06 B5a E42: vorher O):
- D              → Display-Modus wechseln (Shaded → Flat Shaded → Wireframe)
- Shift+D        → Wireframe Overlay AN/AUS
SetShaded/SetFlatShaded/SetWireframe bleiben ohne Taste.

Transform (WP-06 B3, Artist Input Truth / AD-013 Addendum 2026-09-26):
- W              → Move (MoveTool)
- E              → Rotate (RotateTool)
- R              → Scale (ScaleTool)
Q ist unbelegt. Achsen-Constraints (WP-06 B4, Blender-Konvention
„Shift+Achse schließt diese Achse aus", Manu 2026-09-27):
- X / Y / Z      → nur entlang dieser Achse
- Shift+X        → YZ-Ebene, Shift+Y → XZ-Ebene, Shift+Z → XY-Ebene
  (B4.1: sticky Toggle — dieselbe Taste erneut hebt auf, bleibt über Gesten)
Ctrl+Z / Ctrl+Y (Undo/Redo) sind ein anderes Modifier-Set und bleiben
unberührt. Im Topology-Lab behält das kontextspezifische R-Binding
(EdgeRing) Vorrang vor dieser globalen Bindung (Kontext-Priorität in
input_binding.BindingSet.command_for).

Contextual C (WP-06 B6, AD-017): `C` ist GLOBAL, nicht Topology-Lab —
Split (Edge-Modus, 1 Edge) / Edge Connect (Edge-Modus, 2+ Edges) / Vertex
Connect (Vertex-Modus, 2+ Vertices); leere Auswahl = Knife-Session (WP-06
B7). Ignoriert, solange W/E/R scharf ist (`Application.key_press`, wie die
Modus-Tasten). Ersetzt die alten Topology-Lab-Tasten `s` (SplitEdge) und
`c` (Connect); siehe `mirai.topology`.

Knife-Session (WP-06 B7, AD-017; Kontext "knife", nur während einer
Session aufgelöst, sonst ungebunden):
- Enter           → KnifeCommit (genau ein History-Eintrag)
- E / RMB-Klick   → KnifeLift (Stift absetzen: Kette beenden ohne Commit,
                    WP-KNIFE-01 UX2, Manu 2026-10-02; nur in diesem Kontext,
                    global bleibt E = Rotate und RMB ungebunden)
- Ctrl+Shift+Z    → Redo (alternative Geste, AD-017 DECIDED 2026-09-22)
Esc (Cancel), Ctrl+Z (Undo) und Ctrl+Y (Redo) kommen über den GLOBAL-
Fallback; `Application` routet sie während der Session auf die Knife-
Session-History. LMB und Shift+LMB (Mittelpunkt-Snap, UX2) gehören während
der Session dem Knife (kein Binding — `Application.pointer_press`),
Alt+LMB-Drag/Alt+Shift+LMB-Drag/Wheel navigieren weiter.

Die verbleibenden Topology-Lab-Keys (K/L/R) liegen im Kontext "topology"
und gelten nur dort (der GLOBAL_CONTEXT-Fallback greift nicht für sie).

Jede Bindung ist über die optionale `keymap.json` im Experiment-Ordner
überschreibbar (siehe input_binding.BindingSet / load_keymap_overrides).
"""

from __future__ import annotations

from pathlib import Path

from . import commands as cmd
from .input import KNIFE_CONTEXT, BindingSet, Input, TOPOLOGY_CONTEXT


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


def _drag(value: str, *modifiers: str) -> Input:
    return Input("drag", value, frozenset(modifiers))


def _wheel(direction: str) -> Input:
    return Input("wheel", direction)


def build_default_bindings() -> BindingSet:
    """Erzeugt die Default-Belegung für den Viewport (und das Topology Lab)."""
    bs = BindingSet()

    # --- Selection-Modi (Artist Input Truth: nur 1/2/3; WP-06 B5b E47 hat die
    # V1-Legacy-Tasten V und F entfernt - F ist für frame_selection reserviert).
    bs.set_default(_key("1"), cmd.SET_VERTEX_MODE)
    bs.set_default(_key("2"), cmd.SET_EDGE_MODE)
    bs.set_default(_key("3"), cmd.SET_FACE_MODE)

    # --- History / Interaktion ---------------------------------------------
    bs.set_default(_key("z", "ctrl"), cmd.UNDO)
    bs.set_default(_key("y", "ctrl"), cmd.REDO)
    bs.set_default(_key("ESCAPE"), cmd.CANCEL)
    # WP-06 B3 (E27): Transform-Tasten nach Artist Input Truth (AD-013
    # Addendum 2026-09-26): W/E/R, Q ist unbelegt. Austauschbar über
    # keymap.json — die Tool-Implementierungen bleiben unberührt.
    bs.set_default(_key("w"), cmd.MOVE)
    bs.set_default(_key("e"), cmd.ROTATE)
    bs.set_default(_key("r"), cmd.SCALE)
    # WP-06 B4 (E33): Constraints; B4.1: sticky Toggle wie im Playground.
    bs.set_default(_key("x"), cmd.CONSTRAIN_AXIS_X)
    bs.set_default(_key("y"), cmd.CONSTRAIN_AXIS_Y)
    bs.set_default(_key("z"), cmd.CONSTRAIN_AXIS_Z)
    bs.set_default(_key("x", "shift"), cmd.CONSTRAIN_PLANE_YZ)
    bs.set_default(_key("y", "shift"), cmd.CONSTRAIN_PLANE_XZ)
    bs.set_default(_key("z", "shift"), cmd.CONSTRAIN_PLANE_XY)
    # Komplette Deselection zusätzlich zum „Klick ins Leere" (WP-01-BUGS_AND_TODOS).
    bs.set_default(_key("a", "alt"), cmd.CLEAR_SELECTION)
    # WP-06 B6 (AD-017): Contextual C — Split (1 edge) / Edge Connect (2+
    # edges) / Vertex Connect (2+ vertices); empty selection = Knife session
    # (WP-06 B7). Global, not TOPOLOGY_CONTEXT — Artist Input Truth
    # `topology.connect`.
    bs.set_default(_key("c"), cmd.CONNECT)

    # --- Knife session (WP-06 B7, AD-017; context "knife") ------------------
    # Artist Input Truth `topology.knife_commit` (Enter); Ctrl+Shift+Z is the
    # alternative in-session Redo gesture (AD-017 DECIDED 2026-09-22). Bound
    # only in this context, so neither key does anything outside a session.
    bs.set_default(_key("enter"), cmd.KNIFE_COMMIT, context=KNIFE_CONTEXT)
    # WP-KNIFE-01 UX2 (Manu 2026-10-02): pen lift on E and on an RMB click.
    bs.set_default(_key("e"), cmd.KNIFE_LIFT, context=KNIFE_CONTEXT)
    bs.set_default(_mouse("RIGHT"), cmd.KNIFE_LIFT, context=KNIFE_CONTEXT)
    bs.set_default(_key("z", "ctrl", "shift"), cmd.REDO, context=KNIFE_CONTEXT)

    # --- Display ------------------------------------------------------------
    bs.set_default(_key("d"), cmd.CYCLE_DISPLAY_MODE)
    bs.set_default(_key("d", "shift"), cmd.TOGGLE_WIREFRAME_OVERLAY)

    # --- Maus (WP-06 B2; RMB/MMB bewusst ungebunden) -------------------------
    bs.set_default(_mouse("LEFT"), cmd.SELECT)
    bs.set_default(_mouse("LEFT", "shift"), cmd.SELECT_ADD)
    bs.set_default(_mouse("LEFT", "ctrl"), cmd.SELECT_REMOVE)
    bs.set_default(_mouse("LEFT", "alt"), cmd.SELECT_TOGGLE)
    bs.set_default(_drag("LEFT", "alt"), cmd.ORBIT)
    bs.set_default(_drag("LEFT", "alt", "shift"), cmd.PAN)
    bs.set_default(_wheel("UP"), cmd.ZOOM)
    bs.set_default(_wheel("DOWN"), cmd.ZOOM)

    # --- Topology Lab (nur im Kontext "topology") ---------------------------
    # WP-06 B6: `s` (SplitEdge) und `c` (Connect, alte Vertex-Mode/Edge-Mode-
    # Zweiteilung) sind hier entfernt — beide durch das globale, kontextuelle
    # `C` oben ersetzt (AD-017). `k`/`l`/`r`/`alt+e` bleiben unverändert
    # (Legacy, außerhalb des B6-Scopes; siehe Handoff-Report).
    bs.set_default(_key("k"), cmd.COLLAPSE, context=TOPOLOGY_CONTEXT)
    bs.set_default(_key("l"), cmd.EDGE_LOOP, context=TOPOLOGY_CONTEXT)
    bs.set_default(_key("r"), cmd.EDGE_RING, context=TOPOLOGY_CONTEXT)
    # Alt+E: Single-Face-Extrude (Experiment, Topology-Lab)
    bs.set_default(_key("e", "alt"), cmd.EXTRUDE, context=TOPOLOGY_CONTEXT)

    return bs


def load_keymap_overrides(
    bindings: BindingSet, path: str | Path
) -> BindingSet:
    """Wendet eine optionale `keymap.json` als User-Overlay an.

    Existiert die Datei nicht, bleibt die Default-Belegung unverändert.
    Eine vorhandene, ungültige Datei wird kontrolliert abgelehnt
    (`KeymapConfigError`, siehe `BindingSet.from_json_file`).
    """
    overlay = BindingSet.from_json_file(path)
    bindings.add_overrides(overlay)
    return bindings