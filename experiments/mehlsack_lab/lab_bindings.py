"""The lab's input table (AD-013 A1/A2/A4) — every input the lab reacts to.

`LAB_OVERRIDES` is the single, visible source (precedent `subdivision_lab/lab_bindings.py`):
`run.py` prints it at start, the README table mirrors it 1:1 (`tests/test_lab_bindings.py`),
and the window resolves events only through `resolve_*()`, so table and behaviour
cannot drift.

Two phases: `create` (the box is built with the wheel) and `edit` (Loop/Ring drag). A
binding with `phase=None` applies in both.

LMB in the edit phase carries two bindings (Slice 3 E24, AD-019): a click (`kind="click"`,
below `CLICK_THRESHOLD_PX`) selects, a drag moves; `lab_pointer.PointerPress` decides.

Fixed by the Artist Input Truth (`artist_input_truth.json`, archived 2026-10-28 under
`docs/archive/input_truth_2026-10/`):
Alt+LMB orbit, Alt+Shift+LMB pan, wheel zoom (edit phase only — in the creation phase
the wheel belongs to the box), X/Y/Z sticky axis, Shift+X/Y/Z sticky plane (Blender
exclude-axis: Shift+X = YZ, Shift+Y = XZ, Shift+Z = XY), W/E/R = Move/Rotate/Scale held
(AD-016 hold-key-hover; Slice 2b E16 — kind "hold"; since Slice 3 on the selection when there
is one, E26), Ctrl+Z / Ctrl+Y, and since Slice 3 the selection inputs: LMB click = replace,
Shift / Ctrl / Alt + LMB click = add / remove / toggle (the click actions are the app's
command names), `1`/`2`/`3` = Vertex/Edge/Face mode, Shift+L / Shift+R = Loop / Ring select
(here: add, E27). Slice 3b adds Manu's lab inputs of 2026-10-13: `L` = Loop/Ring mode on/off
(O13), Shift+`1`/`2`/`3` = convert the selection (O15), double click on an edge = its loop,
Shift+double click = loop section / face loop (s2, O12). Everything else is a lab-local engineering proposal (`PROVISIONAL`), not an
Artist decision. `Q` (AD-016) and `C` (AD-017) stay reserved and are never bound.

pyglet-free: the window translates pyglet button/modifier/symbol values into the names
used here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mirai.interaction import commands as _commands

PHASE_CREATE = "create"
PHASE_EDIT = "edit"
PHASE_LABELS = {PHASE_CREATE: "Box", PHASE_EDIT: "Bearbeiten", None: "beide"}

# actions
ORBIT = "orbit"
PAN = "pan"
ZOOM = "zoom"
DRAG_TARGET = "drag_target"
CURVE_POINT = "curve_point"
CURVE_BREAK = "curve_break"
CURVE_RESET = "curve_reset"
CANCEL_PRESS = "cancel_press"
BOX_HEIGHT = "box_height"
BOX_WIDTH = "box_width"
BOX_DEPTH = "box_depth"
HOLD_MOVE = "hold_move"
HOLD_ROTATE = "hold_rotate"
HOLD_SCALE = "hold_scale"
PLANE_YZ = "plane_yz"
PLANE_XZ = "plane_xz"
PLANE_XY = "plane_xy"
SCALE_FORMULA = "scale_formula"
BOX_LOOPS = "box_loops"
BOX_AROUND = "box_around"
COMMIT_BOX = "commit_box"
RADIUS = "radius"
TOGGLE_MODE = "toggle_mode"
AXIS_X = "axis_x"
AXIS_Y = "axis_y"
AXIS_Z = "axis_z"
METRIC = "metric"
BANDS = "bands"
PREVIEW = "preview"
NACHFUEHREN = "nachfuehren"
PRESET_1 = "preset_1"
PRESET_2 = "preset_2"
UNDO = "undo"
REDO = "redo"
NEW_BOX = "new_box"
HELP = "help"
ESCAPE = "escape"
# Slice 3: selection (click actions = the app's command names, E25)
SELECT = _commands.SELECT
SELECT_ADD = _commands.SELECT_ADD
SELECT_REMOVE = _commands.SELECT_REMOVE
SELECT_TOGGLE = _commands.SELECT_TOGGLE
MODE_VERTEX = "mode_vertex"
MODE_EDGE = "mode_edge"
MODE_FACE = "mode_face"
LOOP_SELECT = "loop_select"
RING_SELECT = "ring_select"
# Slice 3b
LOOP_MODE = "loop_mode"
CONVERT_VERTEX = "convert_vertex"
CONVERT_EDGE = "convert_edge"
CONVERT_FACE = "convert_face"
DOUBLE_LOOP = "double_loop"
DOUBLE_PART = "double_part"

#: Keys reserved elsewhere (AD-016 Q, AD-017 C): the lab must never bind them. W/E/R are bound
#: since Slice 2b with exactly their AD-016 meaning (hold = Move/Rotate/Scale).
RESERVED_KEYS = frozenset({"Q", "C"})
#: Hold keys and the gesture each arms (E16).
HOLD_KINDS = {HOLD_MOVE: "move", HOLD_ROTATE: "rotate", HOLD_SCALE: "scale"}
#: Modifiers the lab distinguishes; others (Caps/Num Lock, ...) are ignored.
KNOWN_MODIFIERS = frozenset({"shift", "ctrl", "alt"})
#: pyglet symbol names treated as the same key.
KEY_ALIASES = {"ENTER": "RETURN", "NUM_ENTER": "RETURN"}


@dataclass(frozen=True)
class LabBinding:
    #: "drag", "click", "press", "double", "wheel", "key" or "hold" (a key held while the mouse
    #: moves)
    kind: str
    #: drag/click/press: "LEFT"/"RIGHT"/"MIDDLE" ("PANEL" = LMB inside the curve panel);
    #: double: "PANEL" (a double click on a curve knot) or "LEFT" (on the mesh, Slice 3b);
    #: key: pyglet key symbol name; wheel: "WHEEL"
    value: str
    #: exact modifier set required; `None` = modifiers ignored
    modifiers: Optional[frozenset]
    #: PHASE_CREATE, PHASE_EDIT or None (both)
    phase: Optional[str]
    action: str
    label: str
    note: str

    def describe(self) -> str:
        return f"{self.gesture():<28} {PHASE_LABELS[self.phase]:<11} {self.label:<58} [{self.note}]"

    def gesture(self) -> str:
        names = {
            "LEFT": "LMB", "RIGHT": "RMB", "MIDDLE": "MMB", "PANEL": "LMB im Kurvenfeld",
            "WHEEL": "Mausrad", "ESCAPE": "Esc", "RETURN": "Enter", "TAB": "Tab",
            "_1": "1", "_2": "2", "_3": "3",
        }
        base = names.get(self.value, self.value)
        if self.kind == "double":
            base = "Doppelklick auf Kurvenpunkt" if self.value == "PANEL" else "Doppelklick"
        elif self.kind == "hold":
            base += " halten"
        elif self.kind == "drag":
            base += " ziehen"
        elif self.kind == "click":
            base += " Klick"
        elif self.kind == "press":
            base += " (während Zug)"
        if self.modifiers:
            mods = "+".join(m.capitalize() for m in sorted(self.modifiers))
            return f"{mods}+{base}"
        return base


_TRUTH = "Artist Input Truth"
_PROD = "Production-Default wie src/main.py"
_APP = "wie App (AD-020), PROVISIONAL"
_LAB = "lab-lokal (Vorschlag, keine Artist-Entscheidung)"
_2A = "lab-lokal (Slice 2a, Vorschlag, keine Artist-Entscheidung)"
_2B = "lab-lokal (Slice 2b, Vorschlag, keine Artist-Entscheidung)"
_3 = "lab-lokal (Slice 3, Vorschlag, keine Artist-Entscheidung)"
_HOLD = "Artist Input Truth (W/E/R); halten wie AD-016; Ziel-Regel Slice 3 E26 (PROVISIONAL)"
_SEL = "Artist Input Truth"
_MODE = "Artist Input Truth; leert die Auswahl wie die App"
_LOOPSEL = "Artist Input Truth; hinzufügen = Slice 3 E27, Manu O16"
_3B = "Manu 2026-10-13 (Slice 3b), lab-lokal"
_NONE = frozenset()

LAB_OVERRIDES: tuple[LabBinding, ...] = (
    # navigation (both phases)
    LabBinding("drag", "LEFT", frozenset({"alt"}), None, ORBIT, "Orbit", _TRUTH),
    LabBinding("drag", "LEFT", frozenset({"alt", "shift"}), None, PAN, "Pan", _TRUTH),
    LabBinding("drag", "RIGHT", None, None, ORBIT, "Orbit", _PROD),
    LabBinding("drag", "MIDDLE", None, None, PAN, "Pan", _PROD),
    LabBinding("wheel", "WHEEL", _NONE, PHASE_EDIT, ZOOM, "Zoom", _TRUTH),
    # creation phase
    LabBinding("wheel", "WHEEL", _NONE, PHASE_CREATE, BOX_HEIGHT, "Höhe ±1 Schritt",
               "lab-lokal (Brief); Mausrad zoomt hier nicht"),
    LabBinding("wheel", "WHEEL", frozenset({"alt"}), PHASE_CREATE, BOX_WIDTH,
               "Breite ±1 Schritt", "lab-lokal (Brief)"),
    LabBinding("wheel", "WHEEL", frozenset({"alt", "shift"}), PHASE_CREATE, BOX_DEPTH,
               "Tiefe ±1 Schritt", "lab-lokal (Slice 2a, Annahme A5)"),
    LabBinding("wheel", "WHEEL", frozenset({"shift"}), PHASE_CREATE, BOX_LOOPS,
               "horizontale Loops ±1", "lab-lokal (Brief)"),
    LabBinding("wheel", "WHEEL", frozenset({"ctrl"}), PHASE_CREATE, BOX_AROUND,
               "Unterteilung rundum ±1", "lab-lokal (Brief)"),
    LabBinding("key", "RETURN", None, PHASE_CREATE, COMMIT_BOX, "Box übernehmen → Bearbeiten",
               "lab-lokal (Brief)"),
    # edit phase
    LabBinding("drag", "LEFT", _NONE, PHASE_EDIT, DRAG_TARGET,
               "Auswahl ziehen (Move); ohne Auswahl das Gehoverte (Element, im L-Modus Loop/Ring)",
               "lab-lokal; Ziel-Regel Slice 3 E26 (PROVISIONAL)"),
    LabBinding("click", "LEFT", _NONE, PHASE_EDIT, SELECT,
               "Auswahl ersetzen (L-Modus: ganzer Loop/Ring; ins Leere = leeren)", _SEL),
    LabBinding("click", "LEFT", frozenset({"shift"}), PHASE_EDIT, SELECT_ADD, "zur Auswahl hinzufügen", _SEL),
    LabBinding("click", "LEFT", frozenset({"ctrl"}), PHASE_EDIT, SELECT_REMOVE, "aus der Auswahl entfernen", _SEL),
    LabBinding("click", "LEFT", frozenset({"alt"}), PHASE_EDIT, SELECT_TOGGLE,
               "Auswahl umschalten (Alt+LMB ziehen = Orbit)", _SEL),
    LabBinding("drag", "PANEL", _NONE, PHASE_EDIT, CURVE_POINT,
               "Kurvenpunkt oder Handle ziehen (Handles bleiben in Linie)", _2A),
    LabBinding("drag", "PANEL", frozenset({"alt"}), PHASE_EDIT, CURVE_BREAK,
               "Handle allein ziehen = Knick (Punkt wie ohne Alt)", _2A),
    LabBinding("double", "PANEL", _NONE, PHASE_EDIT, CURVE_RESET,
               "Handles des Punkts wieder weich (automatisch)", _2A),
    LabBinding("hold", "W", _NONE, PHASE_EDIT, HOLD_MOVE,
               "Move der Auswahl, sonst des Gehoverten (loslassen = fertig)", _HOLD),
    LabBinding("hold", "E", _NONE, PHASE_EDIT, HOLD_ROTATE,
               "Rotate der Auswahl, sonst des Gehoverten (waagrecht bewegen)", _HOLD),
    LabBinding("hold", "R", _NONE, PHASE_EDIT, HOLD_SCALE,
               "Scale der Auswahl, sonst des Gehoverten (rechts/oben = größer)", _HOLD),
    LabBinding("key", "_1", _NONE, PHASE_EDIT, MODE_VERTEX, "Auswahlmodus Punkte", _MODE),
    LabBinding("key", "_2", _NONE, PHASE_EDIT, MODE_EDGE, "Auswahlmodus Kanten", _MODE),
    LabBinding("key", "_3", _NONE, PHASE_EDIT, MODE_FACE, "Auswahlmodus Flächen", _MODE),
    LabBinding("key", "_1", frozenset({"shift"}), PHASE_EDIT, CONVERT_VERTEX,
               "Auswahl in Punkte umrechnen (berührend)", _3B),
    LabBinding("key", "_2", frozenset({"shift"}), PHASE_EDIT, CONVERT_EDGE,
               "Auswahl in Kanten umrechnen (berührend)", _3B),
    LabBinding("key", "_3", frozenset({"shift"}), PHASE_EDIT, CONVERT_FACE,
               "Auswahl in Flächen umrechnen (berührend)", _3B),
    LabBinding("key", "L", _NONE, PHASE_EDIT, LOOP_MODE,
               "L-Modus an/aus: Hover/Klick auf ganze Loops/Ringe (Flächen: Flächen des Rings)", _3B + " + 3c"),
    LabBinding("double", "LEFT", _NONE, PHASE_EDIT, DOUBLE_LOOP,
               "Kanten: ganzer Edge Loop; Punkte: Loop der Kante zur Cursor-Seite (ersetzt)",
               _3B + " + 3c; ersetzen PROVISIONAL"),
    LabBinding("double", "LEFT", frozenset({"shift"}), PHASE_EDIT, DOUBLE_PART,
               "dazu — Kanten: Ring (Nachbarkante), Teilstück (selber Loop), sonst Loop; Flächen: Face Loop / Teilstück",
               _3B + " + 3c"),
    LabBinding("key", "L", frozenset({"shift"}), PHASE_EDIT, LOOP_SELECT,
               "Loop der gehoverten Kante zur Auswahl (Punkt-/Kantenmodus)", _LOOPSEL),
    LabBinding("key", "R", frozenset({"shift"}), PHASE_EDIT, RING_SELECT,
               "Ring der gehoverten Kante zur Auswahl (Punkt-/Kantenmodus)", _LOOPSEL),
    LabBinding("press", "RIGHT", None, PHASE_EDIT, CANCEL_PRESS, "Zug abbrechen (exakt zurück)", _LAB),
    LabBinding("key", "TAB", _NONE, PHASE_EDIT, TOGGLE_MODE, "Loop ↔ Ring im L-Modus (bleibt)", _LAB),
    LabBinding("key", "X", _NONE, PHASE_EDIT, AXIS_X, "Achse X an/aus (bleibt)", _TRUTH),
    LabBinding("key", "Y", _NONE, PHASE_EDIT, AXIS_Y, "Achse Y an/aus (bleibt)", _TRUTH),
    LabBinding("key", "Z", _NONE, PHASE_EDIT, AXIS_Z, "Achse Z an/aus (bleibt)", _TRUTH),
    LabBinding("key", "X", frozenset({"shift"}), PHASE_EDIT, PLANE_YZ, "Ebene YZ (ohne X) an/aus (bleibt)", _TRUTH),
    LabBinding("key", "Y", frozenset({"shift"}), PHASE_EDIT, PLANE_XZ,
               "Ebene XZ (ohne Y, z. B. Taille) an/aus (bleibt)", _TRUTH),
    LabBinding("key", "Z", frozenset({"shift"}), PHASE_EDIT, PLANE_XY, "Ebene XY (ohne Z) an/aus (bleibt)", _TRUTH),
    LabBinding("wheel", "WHEEL", frozenset({"shift"}), PHASE_EDIT, RADIUS,
               "Einflussradius ±1 Stufe", _APP),
    LabBinding("key", "O", frozenset({"ctrl"}), PHASE_EDIT, METRIC, "Metrik geodesic ↔ euclidean", _APP),
    LabBinding("key", "O", frozenset({"alt"}), PHASE_EDIT, BANDS, "Einfluss-Punkte an/aus", _APP),
    LabBinding("key", "P", _NONE, PHASE_EDIT, PREVIEW,
               "Flächen-Vorschau an/aus (orange = mit, blau = entgegen)", _2A),
    LabBinding("key", "N", _NONE, PHASE_EDIT, NACHFUEHREN, "Nachführen an/aus", _LAB),
    LabBinding("key", "M", _NONE, PHASE_EDIT, SCALE_FORMULA,
               "Scale-Formel linear ↔ power (bleibt; Nachführen)", _2B),
    LabBinding("key", "K", _NONE, PHASE_EDIT, PRESET_1, "Kurve: Smooth", _3),
    LabBinding("key", "K", frozenset({"shift"}), PHASE_EDIT, PRESET_2, "Kurve: Mexican Hat (mit Senke)", _3),
    LabBinding("key", "Z", frozenset({"ctrl"}), PHASE_EDIT, UNDO, "Undo", _TRUTH),
    LabBinding("key", "Y", frozenset({"ctrl"}), PHASE_EDIT, REDO, "Redo", _TRUTH),
    LabBinding("key", "B", _NONE, PHASE_EDIT, NEW_BOX, "neue Box (2× B; löscht die History)", _LAB),
    # both phases
    LabBinding("key", "H", None, None, HELP, "Tastenhilfe an/aus",
               "lab-lokal; Artist Truth: H = HUD"),
    LabBinding("key", "ESCAPE", None, None, ESCAPE, "Zug/Rückfrage abbrechen, sonst Beenden",
               "lab-lokal; Q bewusst nicht belegt"),
)


def _modifiers_match(binding: LabBinding, modifiers: frozenset) -> bool:
    if binding.modifiers is None:
        return True
    return binding.modifiers == (frozenset(modifiers) & KNOWN_MODIFIERS)


def _phase_match(binding: LabBinding, phase: str) -> bool:
    return binding.phase is None or binding.phase == phase


def resolve_drag(phase: str, buttons: frozenset, modifiers: frozenset, in_panel: bool = False) -> Optional[str]:
    """Action for a mouse drag/press with `buttons` held ("LEFT"/"RIGHT"/"MIDDLE"). A plain or
    Alt-held LMB inside the curve panel in the edit phase is the panel ("PANEL"), never the
    mesh and never an orbit (Alt+drag on a handle breaks it, E12); Alt+Shift+LMB still pans."""
    buttons = frozenset(buttons)
    if in_panel and phase == PHASE_EDIT and "LEFT" in buttons:
        mods = frozenset(modifiers) & KNOWN_MODIFIERS
        if mods in (frozenset(), frozenset({"alt"})):
            buttons = buttons - {"LEFT"} | {"PANEL"}
    for binding in LAB_OVERRIDES:
        if (binding.kind == "drag" and binding.value in buttons and _phase_match(binding, phase)
                and _modifiers_match(binding, modifiers)):
            return binding.action
    return None


def resolve_click(phase: str, button: str, modifiers: frozenset) -> Optional[str]:
    """Click action of a press of `button` ("LEFT", never inside the curve panel), or None."""
    for binding in LAB_OVERRIDES:
        if (binding.kind == "click" and binding.value == button and _phase_match(binding, phase)
                and _modifiers_match(binding, modifiers)):
            return binding.action
    return None


def resolve_hold_release(phase: str, symbol_name: str) -> Optional[str]:
    """The hold action a released key ends (modifiers ignored: Shift may have been added)."""
    for binding in LAB_OVERRIDES:
        if binding.kind == "hold" and binding.value == symbol_name and _phase_match(binding, phase):
            return binding.action
    return None


def resolve_double_click(phase: str, modifiers: frozenset, in_panel: bool) -> Optional[str]:
    """Action for an LMB double click: on a curve knot (panel) or on the mesh (Slice 3b)."""
    value = "PANEL" if in_panel else "LEFT"
    for binding in LAB_OVERRIDES:
        if (binding.kind == "double" and binding.value == value and _phase_match(binding, phase)
                and _modifiers_match(binding, modifiers)):
            return binding.action
    return None


def resolve_press_during_drag(phase: str, button: str) -> Optional[str]:
    for binding in LAB_OVERRIDES:
        if binding.kind == "press" and binding.value == button and _phase_match(binding, phase):
            return binding.action
    return None


def resolve_key(phase: str, symbol_name: str, modifiers: frozenset) -> Optional[str]:
    symbol_name = KEY_ALIASES.get(symbol_name, symbol_name)
    for binding in LAB_OVERRIDES:
        if (binding.kind in ("key", "hold") and binding.value == symbol_name and _phase_match(binding, phase)
                and _modifiers_match(binding, modifiers)):
            return binding.action
    return None


def resolve_wheel(phase: str, modifiers: frozenset) -> Optional[str]:
    for binding in LAB_OVERRIDES:
        if binding.kind == "wheel" and _phase_match(binding, phase) and _modifiers_match(binding, modifiers):
            return binding.action
    return None


def wheel_steps(scroll_x: float, scroll_y: float, modifiers: frozenset) -> int:
    """+1 / -1 / 0 for one scroll event (one notch = one step, like the app).

    The rule of `src/main.py` `wheel_input` (AD-020 E5), copied, not imported: some
    Windows drivers report Shift+wheel (and other modifier+wheel) as a horizontal scroll —
    with a modifier held and `scroll_y == 0`, `scroll_x` is read instead (its sign is not
    confirmed on the reference PC)."""
    if (frozenset(modifiers) & KNOWN_MODIFIERS) and scroll_y == 0:
        scroll_y = scroll_x
    if scroll_y > 0:
        return 1
    if scroll_y < 0:
        return -1
    return 0


def overrides_table(phase: Optional[str] = "all") -> list[str]:
    """Printable lines of `LAB_OVERRIDES` (all, or those active in `phase`)."""
    return [
        b.describe() for b in LAB_OVERRIDES
        if phase == "all" or b.phase is None or b.phase == phase
    ]
