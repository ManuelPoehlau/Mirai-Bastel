"""Lab-Kontext und die drei Lab-Tasten (AD-013 I4/I6, Addendum H2-R1).

Eine Binding-Autorität: `app.bindings` (das Production-`BindingSet` der
`Application`). Das Lab legt keinen zweiten Resolver an, sondern trägt nur die
drei Einträge im eigenen Kontext `SYMMETRY_LAB_CONTEXT` ein (`lab_app.install_lab_bindings`,
mit Start-Prüfung). Alles andere fällt über den `global`-Kontext auf die
Production-Bindungen zurück — Navigation, Auswahl, W/E/R, C, Undo/Redo sind die
der App.

`LAB_OVERRIDES` ist die einzige Quelle der Lab-Tasten; `run.py` listet sie beim
Start (`lab_app.startup_listing`), die README-Tabelle beschreibt dieselben Einträge.
Die Commands sind Lab-lokale Strings, bewusst nicht in `mirai.interaction.commands`.

Bis WP-SYM-LAB-03 Slice 5 standen hier auch die Navigations-, RMB-, MMB- und
C → Knife-Overrides des alten Labs und `apply_lab_bindings`; sie gingen mit dem
alten Dispatcher (H2-R1: keine Pointer-Einträge, Plan §4.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from mirai.interaction.input import Input

SYMMETRY_LAB_CONTEXT = "symmetry_lab"
#: Shift+S: Symmetrie aus → X → Y → Z → aus (Artist A2).
SYMMETRY_CYCLE = "SymmetryCycle"
#: M: Re-Symmetrize-Vorschau öffnen, M erneut: ausführen (Artist A7, Slice 5).
RESYMMETRIZE = "ReSymmetrize"
#: Shift+B: E5-Modus BLOCK ↔ MARK für Tools ohne `supports_symmetry` (WP-SYM-LAB-02 S1).
SYMMETRY_GATE_MODE = "SymmetryGateMode"


@dataclass(frozen=True)
class LabOverride:
    input: Input
    command: str
    reason: str

    def describe(self) -> str:
        mods = "+".join(m.capitalize() for m in sorted(self.input.modifiers))
        label = f"{mods}+{self.input.value}" if mods else self.input.value
        return f"{self.input.kind}:{label} -> {self.command}  [{self.reason}]"


LAB_OVERRIDES: tuple[LabOverride, ...] = (
    LabOverride(
        Input("key", "s", frozenset({"shift"})),
        SYMMETRY_CYCLE,
        "Artist A2 (2026-09-24)",
    ),
    LabOverride(
        Input("key", "m"),
        RESYMMETRIZE,
        "Artist A7 (2026-09-25)",
    ),
    LabOverride(
        Input("key", "b", frozenset({"shift"})),
        SYMMETRY_GATE_MODE,
        "Artist E5 test",
    ),
)
