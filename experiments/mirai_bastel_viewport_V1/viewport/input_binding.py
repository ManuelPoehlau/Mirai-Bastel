"""Keine Mapping-/Input-Foundation für den Viewport-Praxistest.

Vertrag: INPUT_COMMAND_TOOL_CONTRACT.md

    Input
      ↓
    Context
      ↓
    Binding
      ↓
    Command

Ein `Input` beschreibt, WAS physisch passiert ist (Taste/Maustaste/Wheel +
Modifier), nicht dessen Bedeutung. Ein `BindingSet` bildet Inputs auf
Commands ab. Default-Belegung und User-Belegung (z.B. `keymap.json`) sind
getrennt; eine Bindung kann geändert werden, ohne die Command-/Tool-
Implementierung zu berühren.

Bewusst klein und pyglet-frei: Die Window-Klassen übersetzen pyglet-Events
in `Input`-Objekte (die einzige Stelle mit einer Render-/Fenster-Abhängigkeit).

Context bleibt minimal: Es gibt einen GLOBAL_CONTEXT plus optionale
benannte Kontexte (hier: TOPOLOGY_CONTEXT für die Topology-Lab-Belegung).
Bei der Auflösung gewinnt der spezifische Kontext, sonst greift der
GLOBAL_CONTEXT-Fallback.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GLOBAL_CONTEXT = "global"
TOPOLOGY_CONTEXT = "topology"

_VALID_KINDS = ("key", "mouse", "wheel")


@dataclass(frozen=True)
class Input:
    """Physischer Input: kind + value + Modifier-Set.

    Beispiele:
        Input("key", "v")
        Input("key", "z", frozenset({"ctrl"}))
        Input("mouse", "LEFT")
        Input("mouse", "MIDDLE", frozenset({"shift"}))
        Input("wheel", "UP")
    """

    kind: str
    value: str
    modifiers: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ValueError(f"Unbekannte Input-Kind: {self.kind!r}")

    # -- Serialisierung (für keymap.json) ----------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "modifiers": sorted(self.modifiers),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Input":
        return cls(
            kind=str(data["kind"]),
            value=str(data["value"]),
            modifiers=frozenset(data.get("modifiers", [])),
        )


class BindingSet:
    """Input → Command-Abbildung mit getrennten Default- und User-Ebenen.

    Auflösung (siehe INPUT_COMMAND_TOOL_CONTRACT): `command_for(input, context)`
    prüft zuerst die User-Ebene, dann die Default-Ebene; innerhalb eines
    Kontextes zuerst den spezifischen Kontext, dann `GLOBAL_CONTEXT`.
    """

    def __init__(self) -> None:
        self._user: dict[tuple[str, Input], str] = {}
        self._defaults: dict[tuple[str, Input], str] = {}

    # -- Ebenen -------------------------------------------------------------

    def set_default(
        self, input: Input, command: str, context: str = GLOBAL_CONTEXT
    ) -> None:
        """Default-Bindung (aus `default_bindings.build_default_bindings()`)."""
        self._defaults[(context, input)] = command

    def bind(
        self, input: Input, command: str, context: str = GLOBAL_CONTEXT
    ) -> None:
        """User-Bindung; überschreibt die Default-Belegung für denselben Input."""
        self._user[(context, input)] = command

    def unbind(self, input: Input, context: str = GLOBAL_CONTEXT) -> bool:
        """Entfernt eine User-Bindung; die Default-Belegung gilt dann wieder."""
        return self._user.pop((context, input), None) is not None

    def add_overrides(self, other: "BindingSet") -> None:
        """Übernimmt alle User-Bindungen aus `other` (z.B. aus keymap.json)."""
        self._user.update(other._user)

    # -- Auflösung ----------------------------------------------------------

    def command_for(
        self, input: Input, context: str | None = None
    ) -> str | None:
        """Löst `input` auf ein Command auf (oder None, wenn ungebunden).

        Kontext-Priorität: übergebener Kontext → GLOBAL_CONTEXT. Innerhalb
        jeder Stufe: User-Ebene → Default-Ebene.
        """
        contexts = (context or GLOBAL_CONTEXT, GLOBAL_CONTEXT)
        for ctx in contexts:
            hit = self._user.get((ctx, input))
            if hit is None:
                hit = self._defaults.get((ctx, input))
            if hit is not None:
                return hit
        return None

    # -- Serialisierung (nur User-Ebene = keymap.json-Inhalt) ---------------

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_dict(self) -> dict[str, Any]:
        bindings = []
        for (ctx, input), command in sorted(
            self._user.items(), key=lambda kv: (kv[0][0], kv[0][1].kind, kv[0][1].value)
        ):
            bindings.append(
                {
                    "context": ctx,
                    "input": input.to_dict(),
                    "command": command,
                }
            )
        return {"bindings": bindings}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BindingSet":
        bs = cls()
        for entry in data.get("bindings", []):
            input = Input.from_dict(entry["input"])
            bs.bind(
                input,
                str(entry["command"]),
                context=str(entry.get("context", GLOBAL_CONTEXT)),
            )
        return bs

    @classmethod
    def from_json_file(cls, path: str | Path) -> "BindingSet":
        """Lädt eine keymap.json als User-Overlay-Ebene (muss nicht existieren)."""
        p = Path(path)
        if not p.is_file():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(data)