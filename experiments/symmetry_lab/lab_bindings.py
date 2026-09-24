"""Lab-Kontext und sichtbare Lab-Overrides (AD-013 I4/I6).

Eine Binding-Autorität: `app.bindings` (das Production-`BindingSet` der
`Application`). Das Lab legt keinen zweiten Resolver an, sondern ergänzt nur
Einträge im eigenen Kontext `SYMMETRY_LAB_CONTEXT` über die öffentliche API.
Alles, was hier nicht steht, fällt über den `global`-Kontext auf die
Production-Defaults zurück (MMB → Pan, Wheel → Zoom, LMB → Select).

`LAB_OVERRIDES` ist die einzige Quelle der Lab-Abweichungen; `run.py` gibt sie
beim Start aus und die README-Tabelle beschreibt dieselben Einträge.

API-Wahl: Die Orbit-/Pan-Overrides sind Lab-*Defaults* (`set_default`). Das
explizite Abbinden von RMB geht nur über die User-Ebene (`bind(..., None)`),
weil `set_default` kein `None` kennt — daher die gemischte Nutzung.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mirai.interaction import commands as cmd
from mirai.interaction.input import BindingSet, Input

SYMMETRY_LAB_CONTEXT = "symmetry_lab"


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
