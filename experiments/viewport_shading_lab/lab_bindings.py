"""The lab's input table (handoff E13, AD-013 A1/A2/A4).

`LAB_OVERRIDES` is the single, visible source of every input the lab reacts
to (symmetry_lab pattern): `run.py` prints it at start and the README table
mirrors it 1:1. The window resolves events only through `resolve_drag()` /
`resolve_key()` / `resolve_scroll()` below, so the table cannot drift from
the behavior.

The lab does not use `Application` or the production `BindingSet`: raw
pyglet events, as in `src/main.py`. This module is pyglet-free — the window
translates pyglet button/modifier/symbol values into the names used here.

Artist Input Truth (`tools/Input_Mapping_Tool/artist_input_truth.json`):
Alt+LMB orbit, Shift+LMB pan, Wheel zoom, H toggle HUD. Q is deliberately
not used for quit (Truth: move). B is a toggle, not a hold (AD-013 A3 open).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Actions (English ids; German labels live in the table).
ORBIT = "orbit"
PAN = "pan"
ZOOM = "zoom"
DRAG_LIGHT = "drag_light"
ROW_PREV = "row_prev"
ROW_NEXT = "row_next"
VALUE_DEC = "value_dec"
VALUE_INC = "value_inc"
PRESET_1 = "preset_1"
PRESET_2 = "preset_2"
PRESET_3 = "preset_3"
PRESET_4 = "preset_4"
TOGGLE_AB = "toggle_ab"
TOGGLE_HUD = "toggle_hud"
CAPTURE = "capture"
QUIT = "quit"

#: Modifiers the lab distinguishes; others (Caps/Num Lock, ...) are ignored.
KNOWN_MODIFIERS = frozenset({"shift", "ctrl", "alt"})


@dataclass(frozen=True)
class LabBinding:
    #: "drag", "wheel" or "key"
    kind: str
    #: drag: "LEFT"/"RIGHT"/"MIDDLE"; key: pyglet key symbol name; wheel: "WHEEL"
    value: str
    #: exact modifier set required; `None` = modifiers ignored
    modifiers: Optional[frozenset]
    action: str
    label: str
    note: str

    def describe(self) -> str:
        return f"{self.gesture():<24} {self.label:<34} [{self.note}]"

    def gesture(self) -> str:
        if self.kind == "key":
            names = {"UP": "↑", "DOWN": "↓", "LEFT": "←", "RIGHT": "→", "ESCAPE": "Esc"}
        else:
            names = {"LEFT": "LMB", "RIGHT": "RMB", "MIDDLE": "MMB", "WHEEL": "Mausrad"}
        base = names.get(self.value, self.value)
        if self.kind == "drag":
            base += " ziehen"
        if self.modifiers:
            mods = "+".join(m.capitalize() for m in sorted(self.modifiers))
            return f"{mods}+{base}"
        return base


_TRUTH = "Artist Input Truth"
_PROD = "Production-Default wie src/main.py"
_LAB = "lab-lokal"

LAB_OVERRIDES: tuple[LabBinding, ...] = (
    LabBinding("drag", "LEFT", frozenset({"alt"}), ORBIT, "Orbit", _TRUTH),
    LabBinding("drag", "LEFT", frozenset({"shift"}), PAN, "Pan", _TRUTH),
    LabBinding("wheel", "WHEEL", None, ZOOM, "Zoom", _TRUTH),
    LabBinding("drag", "RIGHT", None, ORBIT, "Orbit", _PROD),
    LabBinding("drag", "MIDDLE", None, PAN, "Pan", _PROD),
    LabBinding("drag", "LEFT", frozenset(), DRAG_LIGHT,
               "Key-Licht drehen (dx Azimut, dy Höhe)",
               "Lab-Override „Licht ziehen“; ob das UX wird, entscheidet das UX-System"),
    LabBinding("key", "UP", None, ROW_PREV, "HUD-Zeile hoch", _LAB),
    LabBinding("key", "DOWN", None, ROW_NEXT, "HUD-Zeile runter", _LAB),
    LabBinding("key", "LEFT", None, VALUE_DEC, "Wert kleiner (Shift = fein)", _LAB),
    LabBinding("key", "RIGHT", None, VALUE_INC, "Wert größer (Shift = fein)", _LAB),
    LabBinding("key", "F1", None, PRESET_1, "Preset „Heute“", _LAB),
    LabBinding("key", "F2", None, PRESET_2, "Preset „Raitt 2:1“", _LAB),
    LabBinding("key", "F3", None, PRESET_3, "Preset „Softbox“", _LAB),
    LabBinding("key", "F4", None, PRESET_4, "Preset „Warm/Kalt“", _LAB),
    LabBinding("key", "B", None, TOGGLE_AB, "A/B-Vergleich mit „Heute“ (Umschalter)",
               "lab-lokal; Toggle, nicht Halten (AD-013 A3 offen)"),
    LabBinding("key", "H", None, TOGGLE_HUD, "HUD an/aus", "= application.toggle_hud"),
    LabBinding("key", "P", None, CAPTURE, "Aufnahme (PNG ohne HUD + JSON)", _LAB),
    LabBinding("key", "ESCAPE", None, QUIT, "Beenden",
               "Q bewusst nicht belegt (Artist Truth: Move)"),
)


def _modifiers_match(binding: LabBinding, modifiers: frozenset) -> bool:
    if binding.modifiers is None:
        return True
    return binding.modifiers == (modifiers & KNOWN_MODIFIERS)


def resolve_drag(buttons: frozenset, modifiers: frozenset) -> Optional[str]:
    """Action for a mouse drag with `buttons` held (names "LEFT"/"RIGHT"/"MIDDLE")."""
    for binding in LAB_OVERRIDES:
        if binding.kind == "drag" and binding.value in buttons and _modifiers_match(binding, modifiers):
            return binding.action
    return None


def resolve_key(symbol_name: str, modifiers: frozenset) -> Optional[str]:
    for binding in LAB_OVERRIDES:
        if binding.kind == "key" and binding.value == symbol_name and _modifiers_match(binding, modifiers):
            return binding.action
    return None


def resolve_scroll(modifiers: frozenset) -> Optional[str]:
    for binding in LAB_OVERRIDES:
        if binding.kind == "wheel" and _modifiers_match(binding, modifiers):
            return binding.action
    return None


def overrides_table() -> list[str]:
    """Printable lines of `LAB_OVERRIDES` (printed by `run.py` at start)."""
    return [binding.describe() for binding in LAB_OVERRIDES]
