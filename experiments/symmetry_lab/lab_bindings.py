"""Lab-Kontext und sichtbare Lab-Overrides (AD-013 I4/I6).

Eine Binding-Autorität: `app.bindings` (das Production-`BindingSet` der
`Application`). Das Lab legt keinen zweiten Resolver an, sondern ergänzt nur
Einträge im eigenen Kontext `SYMMETRY_LAB_CONTEXT` über die öffentliche API.
Alles, was hier nicht steht, fällt über den `global`-Kontext auf die
Production-Defaults zurück (Wheel → Zoom, LMB → Select; MMB → Pan ist seit
WP-06 B2 ein Lab-Override, weil global ungebunden).

`LAB_OVERRIDES` ist die einzige Quelle der Lab-Abweichungen; `run.py` gibt sie
beim Start aus und die README-Tabelle beschreibt dieselben Einträge.

API-Wahl: Die Orbit-/Pan-Overrides sind Lab-*Defaults* (`set_default`). Das
explizite Abbinden von RMB geht nur über die User-Ebene (`bind(..., None)`),
weil `set_default` kein `None` kennt — daher die gemischte Nutzung.

Slice 3: `SYMMETRY_CYCLE` ist ein Lab-lokaler Command-String (Handoff §4.1),
bewusst nicht in `mirai.interaction.commands`. Q/ESC/Ctrl+Z/Ctrl+Y sind keine
Overrides — sie fallen auf die globalen Defaults `Move`/`Cancel`/`Undo`/`Redo`
zurück.

Slice 5: `RESYMMETRIZE` (Taste M, Artist A7) ist ebenfalls Lab-lokal; M ist in
den globalen Defaults und in `artist_input_truth.json` frei.

Slice 7: `KNIFE` (Taste C, Artist A8) ist Lab-lokal. Die Production-Bindung
von C (`Connect`) liegt in `TOPOLOGY_CONTEXT` und greift für
`SYMMETRY_LAB_CONTEXT` nie (E23). Enter ist bewusst nicht belegt (A13).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mirai.interaction import commands as cmd
from mirai.interaction.input import BindingSet, Input

SYMMETRY_LAB_CONTEXT = "symmetry_lab"
#: Shift+S: Symmetrie aus → X → Y → Z → aus (Artist A2).
SYMMETRY_CYCLE = "SymmetryCycle"
#: M: Re-Symmetrize-Vorschau öffnen, M erneut: ausführen (Artist A7, Slice 5).
RESYMMETRIZE = "ReSymmetrize"
#: C: gespiegelten Knife starten (Artist A8, Slice 7).
KNIFE = "Knife"


@dataclass(frozen=True)
class LabOverride:
    input: Input
    #: `None` = im Lab-Kontext explizit ungebunden.
    command: Optional[str]
    reason: str

    def describe(self) -> str:
        mods = "+".join(m.capitalize() for m in sorted(self.input.modifiers))
        label = f"{mods}+{self.input.value}" if mods else self.input.value
        target = self.command if self.command is not None else "(ungebunden)"
        return f"{self.input.kind}:{label} -> {target}  [{self.reason}]"


LAB_OVERRIDES: tuple[LabOverride, ...] = (
    LabOverride(
        Input("mouse", "LEFT", frozenset({"alt"})),
        cmd.ORBIT,
        "Artist Truth + Playground-Praxis",
    ),
    LabOverride(
        Input("mouse", "LEFT", frozenset({"shift"})),
        cmd.PAN,
        "Artist Truth + Playground-Praxis",
    ),
    LabOverride(
        Input("mouse", "RIGHT"),
        None,
        "eine Primärbindung pro Funktion (Orbit liegt auf Alt+LMB)",
    ),
    LabOverride(
        Input("mouse", "MIDDLE"),
        cmd.PAN,
        "preserve lab MMB pan after WP-06 B2 global change",
    ),
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
        Input("key", "c"),
        KNIFE,
        "Artist A8 (2026-09-25)",
    ),
)


def apply_lab_bindings(bindings: BindingSet) -> None:
    """Trägt `LAB_OVERRIDES` im Lab-Kontext ein; `global` bleibt unverändert."""
    for override in LAB_OVERRIDES:
        if override.command is None:
            bindings.bind(override.input, None, context=SYMMETRY_LAB_CONTEXT)
        else:
            bindings.set_default(
                override.input, override.command, context=SYMMETRY_LAB_CONTEXT
            )
