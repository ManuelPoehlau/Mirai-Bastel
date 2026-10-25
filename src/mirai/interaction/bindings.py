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
- LMB-Drag        → SelectDrag: Start im leeren Raum = Box, auf dem Mesh = Paint
                    (ersetzt die Auswahl); Shift+LMB-Drag → SelectDragAdd (fügt hinzu)
- Ctrl+LMB-Drag   → Tweak (zuletzt gewähltes W/E/R, Start Move); Ctrl+LMB-Klick bleibt
                    SelectRemove. Alles `PROVISIONAL`, Manu 2026-10-15 (Promotion der
                    Playground-Werkzeuge: Box/Paint "Startpunkt entscheidet", Tweak
                    "Ctrl+LMB, Auswahl weicht")
- RMB/MMB         → bewusst ungebunden (eine Primärbindung pro Funktion,
                    AD-013 Truth-Regel 2)

Display (Artist Input Truth, WP-06 B5a E42: vorher O):
- D              → Display-Modus wechseln (Shaded → Flat Shaded → Wireframe)
- Shift+D        → Wireframe Overlay AN/AUS
- Ctrl+D         → Licht-Preset wechseln (Raitt 2:1 → Softbox → Warm/Kalt → Heute),
                   Ctrl+Shift+D → Licht folgt der Kamera / steht in der Welt
                   (Engineering-Tasten `PROVISIONAL`, keine Artist Input Truth)
- ↑ / ↓          → Look-Zeile wählen (Licht: Bezugsraum, Key Azimut/Höhe/Stärke/Temperatur/Weichheit,
                   Verhältnis, Fill-Kopplung/Azimut/Höhe/Temperatur/Weichheit, Grundhelligkeit),
                   ← / →  Wert eine Stufe kleiner/größer, Ctrl+← / Ctrl+→ fein (Stufen des Shading
                   Lab; AD-024 §8, `PROVISIONAL` bis zur GUI, kein Undo-Schritt); danach die
                   Material-Zeilen (Farbton, Sättigung, Helligkeit, Specular, Glossiness) der
                   ausgewählten Objekte in `4` bzw. des Edit-Objekts in 1/2/3, je ein Undo-Schritt
- L (halten)     → Licht ziehen: Maus bewegen dreht das Key-Licht (dx Azimut, dy Höhe; Manu
                   2026-10-24, AD-024 Q-L2), kein Undo-Schritt
SetShaded/SetFlatShaded/SetWireframe bleiben ohne Taste.
- H              → HUD (Zustandsanzeige) zeigen/verbergen (Artist Input Truth
                   `application.toggle_hud`, GUI Stufe 1; Kontext "window", vom
                   Fenster behandelt, für `Application` ungebunden)

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

Extrude (WP-06 B9, Artist Input Truth `topology.extrude` = T, "for now" - Manu
2026-10-09; PROVISIONAL, hold-key-hover like W/E/R - the "held" activation is an
engineering proposal, not an Artist statement):
- T (halten)      -> Extrude der ausgewaehlten bzw. gehoverten Faces (Face-Modus),
                    Maus bewegen = Distanz, loslassen = Commit
Wie `C` ignoriert, solange W/E/R/T scharf ist (Session Gate). Ersetzt das alte
Topology-Lab-Binding Alt+E (entfernt).

Delete / Dissolve (WP Delete/Dissolve, Artist Input Truth PROVISIONAL,
docs/WP_DELETE_DISSOLVE_PLAN.md §0.2): zwei Tasten statt Menü (3ds Max),
global, auf die Auswahl des aktiven Komponentenmodus:
- Entf             → Delete (destruktiv, Loch) in Vertex/Edge/Face
- Rücktaste        → Dissolve mit Cleanup (Edge/Face); Vertex-Dissolve
- Ctrl+Rücktaste   → Dissolve ohne Cleanup (Edge/Face; Vertex: keine Wirkung)
Wie `C` ignoriert, solange W/E/R scharf ist; während einer Knife-Session
ungebunden (Session Gate).

Symmetrie (AD-SYM-04 Slice A1, Q-1 = E-1, Taste `PROVISIONAL`, AD-013 A5):
- Shift+S          → Symmetrie aus → X → Y → Z → aus, je ein Undo-Schritt
Wie `C` ignoriert, solange W/E/R/T scharf ist; in der Knife-Session ignoriert
(Session Gate, über den GLOBAL-Fallback aufgelöst). Bis 2026-10-14 eine Taste des Symmetry Lab (H2-R1); das Lab nutzt
jetzt diese.

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

Soft Selection (WP-SOFT-01 S2a, AD-020, `PROVISIONAL`, aus per Default; Manu 2026-10-10):
- O                → Soft an/aus (O war bis B5a die Anzeige-Taste, jetzt D)
- Shift+Mausrad    → Radius eine Stufe größer (hoch) / kleiner (runter); zoomt nie
- Shift+O          → Kurve wechseln (smooth → sphere → root → sharp → linear → custom),
                    Ctrl+O → Metrik wechseln
- Ctrl+Mausrad     → Form der Kurve `custom` (hoch = runder, runter = spitzer); schaltet auf
                    `custom`, zoomt nie. Ctrl+Shift+Mausrad ist ungebunden.
- Alt+O            → Influence-Bänder (Farbpunkte) an/aus
Sticky wie X/Y/Z, wirken ab der nächsten Geste; Engineering-Tasten, keine Artist Input Truth.

Loop-Werkzeuge (2026-10-15, Tasten aus der Artist Input Truth, `PROVISIONAL`):
- Shift+L          → Edge Loop zur Auswahl (Edge-Modus; ausgewählte Edges, sonst die gehoverte)
- Shift+R          → Edge Ring zur Auswahl (wie Shift+L)
- I                → Loop Insert: neuer Loop durch den Ring der ausgewählten/gehoverten Edge
- G (halten)       → Loop Slide der ausgewählten Edges, Maus bewegen, loslassen = Commit
Wie `C` ignoriert, solange W/E/R/T/G scharf ist; in der Knife-Session ungebunden.

Die verbleibenden Topology-Lab-Keys (K/L/R) liegen im Kontext "topology"
und gelten nur dort (der GLOBAL_CONTEXT-Fallback greift nicht für sie).

Jede Bindung ist über die optionale `keymap.json` im Experiment-Ordner
überschreibbar (siehe input_binding.BindingSet / load_keymap_overrides).
"""

from __future__ import annotations

from pathlib import Path

from . import commands as cmd
from .input import KNIFE_CONTEXT, BindingSet, Input, TOPOLOGY_CONTEXT, WINDOW_CONTEXT


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


def _drag(value: str, *modifiers: str) -> Input:
    return Input("drag", value, frozenset(modifiers))


def _wheel(direction: str, *modifiers: str) -> Input:
    return Input("wheel", direction, frozenset(modifiers))


def build_default_bindings() -> BindingSet:
    """Erzeugt die Default-Belegung für den Viewport (und das Topology Lab)."""
    bs = BindingSet()

    # --- Selection-Modi (Artist Input Truth: 1/2/3; WP-06 B5b E47 hat die
    # V1-Legacy-Tasten V und F entfernt - F ist für frame_selection reserviert).
    # `4` = Objekt-Modus (V1_SPEC §2, AD-021 M1).
    bs.set_default(_key("1"), cmd.SET_VERTEX_MODE)
    bs.set_default(_key("2"), cmd.SET_EDGE_MODE)
    bs.set_default(_key("3"), cmd.SET_FACE_MODE)
    bs.set_default(_key("4"), cmd.SET_OBJECT_MODE)
    # AD-021 M2-3 (L-3, `PROVISIONAL`, Frage an Manu): Alt+A ist schon "Auswahl leeren".
    bs.set_default(_key("a", "ctrl"), cmd.APPLY_TRANSFORM)
    bs.set_default(_key("a", "alt", "shift"), cmd.CLEAR_TRANSFORM)
    # Q-12 revidiert (Manu 2026-10-16, `PROVISIONAL`): Referenz an/aus der ausgewählten Objekte in `4`;
    # Alt wie `Alt+D` (Referenzen als Ghost).
    bs.set_default(_key("r", "alt"), cmd.TOGGLE_REFERENCE)

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
    # WP-06 B9 (E10, AD-013 A5: a binding is not part of the capability): Extrude on
    # `T`, PROVISIONAL baseline from the Artist Input Truth (`topology.extrude`).
    bs.set_default(_key("t"), cmd.EXTRUDE)
    # WP-06 B4 (E33): Constraints; B4.1: sticky Toggle wie im Playground.
    bs.set_default(_key("x"), cmd.CONSTRAIN_AXIS_X)
    bs.set_default(_key("y"), cmd.CONSTRAIN_AXIS_Y)
    bs.set_default(_key("z"), cmd.CONSTRAIN_AXIS_Z)
    bs.set_default(_key("x", "shift"), cmd.CONSTRAIN_PLANE_YZ)
    bs.set_default(_key("y", "shift"), cmd.CONSTRAIN_PLANE_XZ)
    bs.set_default(_key("z", "shift"), cmd.CONSTRAIN_PLANE_XY)
    # WP Toolbox Gaps C1 (`PROVISIONAL`, "Orientation-Toggle wie im Playground"): K = World <-> Normal.
    bs.set_default(_key("k"), cmd.TOGGLE_TRANSFORM_SPACE)
    # Komplette Deselection zusätzlich zum „Klick ins Leere" (WP-01-BUGS_AND_TODOS).
    bs.set_default(_key("a", "alt"), cmd.CLEAR_SELECTION)
    # WP-06 B6 (AD-017): Contextual C — Split (1 edge) / Edge Connect (2+
    # edges) / Vertex Connect (2+ vertices); empty selection = Knife session
    # (WP-06 B7). Global, not TOPOLOGY_CONTEXT — Artist Input Truth
    # `topology.connect`.
    bs.set_default(_key("c"), cmd.CONNECT)
    # WP Toolbox Gaps B1 (Manu 2026-10-23): Collapse V/E/F on Shift+C; the dead `K` in the
    # TOPOLOGY_CONTEXT is gone. C without a modifier stays Connect.
    bs.set_default(_key("c", "shift"), cmd.COLLAPSE)
    # WP Delete/Dissolve (§0.2 Punkte 1, 2, 5): Delete destruktiv, Backspace
    # räumt auf, Ctrl+Backspace nicht. Umbindbar über keymap.json.
    bs.set_default(_key("delete"), cmd.DELETE)
    bs.set_default(_key("backspace"), cmd.DISSOLVE)
    bs.set_default(_key("backspace", "ctrl"), cmd.DISSOLVE_NO_CLEANUP)

    # AD-SYM-04 Slice A1 (Q-1 = E-1): Shift+S cycles the symmetry definition. The key is
    # PROVISIONAL (AD-013 A5: the Lab's key is not promoted with the capability); it is the
    # key the refusal texts of `symmetric_ops`/`symmetric_knife`/`symmetric_extrude` name.
    bs.set_default(_key("s", "shift"), cmd.SYMMETRY_CYCLE)
    # AD-SYM-04 Slice A3: Re-Symmetrize (preview, again = execute, Esc = cancel). PROVISIONAL key:
    # the Lab's M (Artist A7) is taken in `src/main.py` by the Morph Lab bridge (Manu 2026-10-17),
    # and AD-013 A5 promotes the capability, not the Lab's key.
    bs.set_default(_key("m", "alt"), cmd.RESYMMETRIZE)
    # Mask Geometry (`PROVISIONAL`): Ctrl+M masks / unmasks the selection, Ctrl+Shift+M inverts, Alt+Shift+M clears.
    bs.set_default(_key("m", "ctrl"), cmd.MASK_TOGGLE)
    bs.set_default(_key("m", "ctrl", "shift"), cmd.MASK_INVERT)
    bs.set_default(_key("m", "alt", "shift"), cmd.MASK_CLEAR)
    # Hide / Isolate / Show all (`PROVISIONAL`): Ctrl+H hides the selection, Ctrl+Shift+H isolates it, Alt+H shows all
    # (bare H stays the HUD toggle of the window level).
    bs.set_default(_key("h", "ctrl"), cmd.HIDE_SELECTION)
    bs.set_default(_key("h", "ctrl", "shift"), cmd.ISOLATE_SELECTION)
    bs.set_default(_key("h", "alt"), cmd.SHOW_ALL)
    # Saved regions (`PROVISIONAL`, AD-REGIONS-01): Shift+G / Shift+Alt+G cycle the slot, Ctrl+G assigns the selection,
    # Ctrl+Shift+G adds, Ctrl+Alt+G removes, Alt+G selects the region (Ctrl+Alt+Shift+G adds it to the selection),
    # Ctrl+Alt+H isolates it, Ctrl+Alt+M masks it, Ctrl+Alt+Backspace deletes it (bare G stays Loop Slide).
    bs.set_default(_key("g", "shift"), cmd.REGION_NEXT)
    bs.set_default(_key("g", "shift", "alt"), cmd.REGION_PREV)
    bs.set_default(_key("g", "ctrl"), cmd.REGION_ASSIGN)
    bs.set_default(_key("g", "ctrl", "shift"), cmd.REGION_ADD)
    bs.set_default(_key("g", "ctrl", "alt"), cmd.REGION_REMOVE)
    bs.set_default(_key("g", "alt"), cmd.REGION_SELECT)
    bs.set_default(_key("g", "ctrl", "alt", "shift"), cmd.REGION_SELECT_ADD)
    bs.set_default(_key("h", "ctrl", "alt"), cmd.REGION_ISOLATE)
    bs.set_default(_key("m", "ctrl", "alt"), cmd.REGION_MASK)
    bs.set_default(_key("backspace", "ctrl", "alt"), cmd.REGION_DELETE)

    # Loop tools (2026-10-15, promoted from the Playground; keys = Artist Input Truth
    # `topology.edge_loop_select` / `edge_ring_select` / `loop_insert` / `loop_slide`).
    bs.set_default(_key("l", "shift"), cmd.EDGE_LOOP)
    bs.set_default(_key("r", "shift"), cmd.EDGE_RING)
    bs.set_default(_key("i"), cmd.LOOP_INSERT)
    bs.set_default(_key("g"), cmd.LOOP_SLIDE)
    # WP Toolbox Gaps C2: hold S = Smooth, hold Alt+S = Relax (hold + drag: Manu 2026-10-23; keys PROVISIONAL).
    bs.set_default(_key("s"), cmd.SMOOTH)
    bs.set_default(_key("s", "alt"), cmd.RELAX)
    # Selection steps (WP Toolbox Gaps A1): Shift+arrows = Manu 2026-10-23; Ctrl++ / Ctrl+-
    # (main keys and keypad, both "plus" / "minus") = Blender's Select More / Less, PROVISIONAL.
    bs.set_default(_key("plus", "ctrl"), cmd.SELECT_GROW)
    bs.set_default(_key("minus", "ctrl"), cmd.SELECT_SHRINK)
    bs.set_default(_key("up", "shift"), cmd.LOOP_GROW)
    bs.set_default(_key("down", "shift"), cmd.LOOP_SHRINK)
    bs.set_default(_key("right", "shift"), cmd.LOOP_NEXT)
    bs.set_default(_key("left", "shift"), cmd.LOOP_PREVIOUS)

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
    # AD-021 M2-0 (§7.3 RD-2, Q-11; Taste `PROVISIONAL`, Display-Familie D/Shift+D).
    bs.set_default(_key("d", "alt"), cmd.TOGGLE_REFERENCE_GHOST)
    # Worklight (2026-10-15, Tasten `PROVISIONAL`, Display-Familie D).
    bs.set_default(_key("d", "ctrl"), cmd.CYCLE_LIGHT_PRESET)
    bs.set_default(_key("d", "ctrl", "shift"), cmd.TOGGLE_LIGHT_SPACE)
    # Saved regions: Ctrl+Alt+D shows / hides the regions' face colours.
    bs.set_default(_key("d", "ctrl", "alt"), cmd.TOGGLE_REGION_TINT)
    # Look rows (AD-024 §8, `PROVISIONAL` until the GUI): the Shading Lab's arrows; the fine step is Ctrl,
    # because Shift+arrows are the selection steps (WP Toolbox Gaps A1).
    bs.set_default(_key("up"), cmd.LOOK_ROW_PREV)
    bs.set_default(_key("down"), cmd.LOOK_ROW_NEXT)
    bs.set_default(_key("left"), cmd.LOOK_VALUE_DEC)
    bs.set_default(_key("right"), cmd.LOOK_VALUE_INC)
    bs.set_default(_key("left", "ctrl"), cmd.LOOK_VALUE_DEC_FINE)
    bs.set_default(_key("right", "ctrl"), cmd.LOOK_VALUE_INC_FINE)
    # Light drag (Manu 2026-10-24, AD-024 Q-L2): hold L + move the mouse. Global `l` was free (the
    # TOPOLOGY_CONTEXT `l` = EdgeLoop keeps priority in the Topology Lab); Shift+L stays Edge Loop.
    bs.set_default(_key("l"), cmd.LIGHT_DRAG)
    # GUI Stufe 1 (2026-10-23): H = Artist Input Truth `application.toggle_hud`. Fenster-Command im
    # Kontext "window": `src/main.py` behandelt ihn, `Application` löst diesen Kontext nie auf.
    bs.set_default(_key("h"), cmd.TOGGLE_HUD, context=WINDOW_CONTEXT)

    # --- Maus (WP-06 B2; RMB/MMB bewusst ungebunden) -------------------------
    bs.set_default(_mouse("LEFT"), cmd.SELECT)
    bs.set_default(_mouse("LEFT", "shift"), cmd.SELECT_ADD)
    bs.set_default(_mouse("LEFT", "ctrl"), cmd.SELECT_REMOVE)
    bs.set_default(_mouse("LEFT", "alt"), cmd.SELECT_TOGGLE)
    # Saved regions (Manu 2026-10-25): Shift+Ctrl+click isolates the clicked face's region / inverts / shows all.
    bs.set_default(_mouse("LEFT", "ctrl", "shift"), cmd.REGION_CLICK)
    bs.set_default(_drag("LEFT", "alt"), cmd.ORBIT)
    bs.set_default(_drag("LEFT", "alt", "shift"), cmd.PAN)
    # 2026-10-15 (Manu): Box/Paint und Tweak - siehe Moduldocstring.
    bs.set_default(_drag("LEFT"), cmd.SELECT_DRAG)
    bs.set_default(_drag("LEFT", "shift"), cmd.SELECT_DRAG_ADD)
    bs.set_default(_drag("LEFT", "ctrl"), cmd.TWEAK)
    # 2026-10-21 (Manu): Lasso kommt in die App. Halte-Taste Q (Artist Input Truth
    # `selection.lasso_select` ist leer, Q ist frei; `PROVISIONAL`, keymap.json kann umbinden).
    bs.set_default(_key("q"), cmd.LASSO_ARM)
    bs.set_default(_wheel("UP"), cmd.ZOOM)
    bs.set_default(_wheel("DOWN"), cmd.ZOOM)

    # --- Soft Selection (WP-SOFT-01 S2a, AD-020; PROVISIONAL) -----------------
    # O = on/off ("O passt erstmal", Manu 2026-10-10; O was the old display key,
    # moved to D in B5a). Shift+wheel = radius one step larger / smaller (a wheel
    # notch is one step); Shift+O = curve, Ctrl+O = metric - both "muss ich testen".
    # Engineering keys for the S2 test, not Artist Input Truth (I8): keymap.json can
    # rebind them. The binding carries the direction, the command does not.
    bs.set_default(_key("o"), cmd.SOFT_TOGGLE)
    bs.set_default(_wheel("UP", "shift"), cmd.SOFT_RADIUS_UP)
    bs.set_default(_wheel("DOWN", "shift"), cmd.SOFT_RADIUS_DOWN)
    bs.set_default(_key("o", "shift"), cmd.SOFT_CURVE_CYCLE)
    bs.set_default(_key("o", "ctrl"), cmd.SOFT_METRIC_CYCLE)
    # S2d (S2c verdict, Manu 2026-10-11): Ctrl+wheel = shape of the `custom` curve (up =
    # rounder, as agreed: "ctrl+mausrad ändern Kurve von spitz <> rund"; the direction is an
    # engineering assumption to confirm). Alt+O = bands on/off (proposal; Manu may change it).
    bs.set_default(_wheel("UP", "ctrl"), cmd.SOFT_CURVE_SHAPE_ROUNDER)
    bs.set_default(_wheel("DOWN", "ctrl"), cmd.SOFT_CURVE_SHAPE_SHARPER)
    bs.set_default(_key("o", "alt"), cmd.SOFT_BANDS_TOGGLE)
    # 2026-10-22 (`PROVISIONAL`, engineering key - not an Artist decision): Alt+Shift+O switches the
    # influence display between vertex bands and face shading; Alt+O hides/shows whichever is active.
    # Alt+Shift+O is unbound elsewhere (the other Alt+Shift keys are A and LMB-drag); rebindable.
    bs.set_default(_key("o", "alt", "shift"), cmd.SOFT_VIEW_MODE_CYCLE)
    # 2026-10-22 (`PROVISIONAL`, engineering key for Manu's look test): Ctrl+Shift+O cycles the look of the
    # influence display (mono / tint / color). Ctrl+Shift+O was unbound; rebindable.
    bs.set_default(_key("o", "ctrl", "shift"), cmd.SOFT_LOOK_CYCLE)
    # 2026-10-22 (`PROVISIONAL`, engineering choice for Manu's practical test, AD-020 "Loop / Ring flow"):
    # Ctrl+Shift+wheel = Loop / Ring balance (up = farther along the loops, down = farther across the rings),
    # live during a begun Soft gesture like the radius. Ctrl+Shift+wheel was the one unbound wheel chord the
    # window reports (plain = zoom / live radius, Shift = radius, Ctrl = curve shape; Alt is not reported with
    # the wheel and navigates the camera during a transform); rebindable.
    bs.set_default(_wheel("UP", "ctrl", "shift"), cmd.SOFT_FLOW_LOOP)
    bs.set_default(_wheel("DOWN", "ctrl", "shift"), cmd.SOFT_FLOW_RING)

    # --- Topology Lab (nur im Kontext "topology") ---------------------------
    # WP-06 B6: `s` (SplitEdge) und `c` (Connect, alte Vertex-Mode/Edge-Mode-
    # Zweiteilung) sind hier entfernt — beide durch das globale, kontextuelle
    # `C` oben ersetzt (AD-017). `l`/`r` bleiben unverändert (Legacy,
    # außerhalb des B6-Scopes; siehe Handoff-Report). `alt+e` (Extrude) ist seit
    # WP-06 B9 entfernt: ersetzt durch das globale `T` oben. `k` (Collapse) ist seit
    # WP Toolbox Gaps B1 entfernt: ersetzt durch das globale Shift+C oben.
    bs.set_default(_key("l"), cmd.EDGE_LOOP, context=TOPOLOGY_CONTEXT)
    bs.set_default(_key("r"), cmd.EDGE_RING, context=TOPOLOGY_CONTEXT)

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