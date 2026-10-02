"""The lab's input table (AD-013 A1/A2/A4).

`LAB_OVERRIDES` is the single, visible source of every input the lab reacts
to (precedent `viewport_shading_lab/lab_bindings.py`): `run.py` prints it at
start and the README table mirrors it 1:1 (`tests/test_lab_bindings.py`).
The window resolves events only through `resolve_drag()` / `resolve_key()` /
`resolve_scroll()`, so the table cannot drift from the behavior.

Fixed by the Artist Input Truth (`tools/Input_Mapping_Tool/artist_input_truth.json`):
Alt+LMB orbit, Shift+LMB pan, Wheel zoom, H toggle HUD, Esc quit. The lab-local
keys (1/2/3 level, V view, X cage depth, B A/B, F9 bench) are a proposal for
this lab only — not an Artist decision. `Q W E R` (AD-016) and `C` (AD-017)
are reserved and deliberately unused.

This module is pyglet-free — the window translates pyglet button/modifier/
symbol values into the names used here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

ORBIT = "orbit"
PAN = "pan"
ZOOM = "zoom"
DRAG_VERTEX = "drag_vertex"
LEVEL_1 = "level_1"
LEVEL_2 = "level_2"
LEVEL_3 = "level_3"
CYCLE_VIEW = "cycle_view"
TOGGLE_CAGE_DEPTH = "toggle_cage_depth"
TOGGLE_AB = "toggle_ab"
TOGGLE_HUD = "toggle_hud"
BENCH = "bench"
QUIT = "quit"

#: Keys reserved elsewhere (AD-016 QWER, AD-017 C): the lab must never bind them.
RESERVED_KEYS = frozenset({"Q", "W", "E", "R", "C"})

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
        return f"{self.gesture():<24} {self.label:<44} [{self.note}]"

    def gesture(self) -> str:
        if self.kind == "key":
            names = {"ESCAPE": "Esc", "_1": "1", "_2": "2", "_3": "3"}
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
_LAB = "lab-lokal (Vorschlag, keine Artist-Entscheidung)"

LAB_OVERRIDES: tuple[LabBinding, ...] = (
    LabBinding("drag", "LEFT", frozenset({"alt"}), ORBIT, "Orbit", _TRUTH),
    LabBinding("drag", "LEFT", frozenset({"shift"}), PAN, "Pan", _TRUTH),
    LabBinding("wheel", "WHEEL", None, ZOOM, "Zoom", _TRUTH),
    LabBinding("drag", "RIGHT", None, ORBIT, "Orbit", _PROD),
    LabBinding("drag", "MIDDLE", None, PAN, "Pan", _PROD),
    LabBinding("drag", "LEFT", frozenset(), DRAG_VERTEX,
               "Control-Vertex greifen und in der Bildebene ziehen",
               "lab-lokal; Hover = nächster Control-Vertex (14 px)"),
    LabBinding("key", "_1", None, LEVEL_1, "Stufe 1", _LAB),
    LabBinding("key", "_2", None, LEVEL_2, "Stufe 2", _LAB),
    LabBinding("key", "_3", None, LEVEL_3, "Stufe 3", _LAB),
    LabBinding("key", "V", None, CYCLE_VIEW, "Ansicht wechseln (V-CAGE → V-BOTH → V-ISO)", _LAB),
    LabBinding("key", "X", None, TOGGLE_CAGE_DEPTH, "Käfig-Tiefentest an / immer sichtbar (V-BOTH)", _LAB),
    LabBinding("key", "B", None, TOGGLE_AB, "A/B-Vergleich mit der Käfig-Ansicht (Umschalter)",
               "lab-lokal; Toggle, nicht Halten (AD-013 A3 offen)"),
    LabBinding("key", "F9", None, BENCH, "Bench auf diesem PC (Fenster friert ein)", _LAB),
    LabBinding("key", "H", None, TOGGLE_HUD, "HUD an/aus", "= application.toggle_hud"),
    LabBinding("key", "ESCAPE", None, QUIT, "Beenden", "Q bewusst nicht belegt (Artist Truth: Move)"),
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
