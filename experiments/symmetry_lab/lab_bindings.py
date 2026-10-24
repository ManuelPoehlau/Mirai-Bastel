"""Lab-Kontext und die Lab-Taste (AD-013 I4/I6, Addendum H2-R1, geändert 2026-10-14 und 2026-10-24).

Eine Binding-Autorität: `app.bindings` (das Production-`BindingSet` der
`Application`). Das Lab legt keinen zweiten Resolver an, sondern trägt nur den
einen Eintrag im eigenen Kontext `SYMMETRY_LAB_CONTEXT` ein (`lab_app.install_lab_bindings`,
mit Start-Prüfung). Alles andere fällt über den `global`-Kontext auf die
Production-Bindungen zurück — Navigation, Auswahl, W/E/R, C, Undo/Redo, seit
AD-SYM-04 Slice A1 (2026-10-14) auch Shift+S (`commands.SYMMETRY_CYCLE`, der Symmetrie-
Zyklus der App) und seit Slice A3 (2026-10-24) Re-Symmetrize (`commands.RESYMMETRIZE`,
Default Alt+M; bis dahin hier M → `ReSymmetrize`, Artist A7) sind die der App.

`LAB_OVERRIDES` ist die einzige Quelle der Lab-Tasten; `run.py` listet sie beim
Start (`lab_app.startup_listing`), die README-Tabelle beschreibt dieselben Einträge.
Das Command ist ein Lab-lokaler String, bewusst nicht in `mirai.interaction.commands`.

Bis WP-SYM-LAB-03 Slice 5 standen hier auch die Navigations-, RMB-, MMB- und
C → Knife-Overrides des alten Labs und `apply_lab_bindings`; sie gingen mit dem
alten Dispatcher (H2-R1: keine Pointer-Einträge, Plan §4.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from mirai.interaction.input import Input

SYMMETRY_LAB_CONTEXT = "symmetry_lab"
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


#: Shift+S (Artist A2, 2026-09-24) war bis 2026-10-14 der dritte Eintrag; er ist jetzt die
#: GLOBAL-Taste der App (AD-SYM-04 Q-1 = E-1, AD-013 Addendum 2026-10-14, H2-R1). M → `ReSymmetrize`
#: (Artist A7, 2026-09-25) war bis 2026-10-24 der zweite; Re-Symmetrize ist seit AD-SYM-04 A3 ein
#: App-Command (AD-013 Addendum 2026-10-24).
LAB_OVERRIDES: tuple[LabOverride, ...] = (
    LabOverride(
        Input("key", "b", frozenset({"shift"})),
        SYMMETRY_GATE_MODE,
        "Artist E5 test",
    ),
)
