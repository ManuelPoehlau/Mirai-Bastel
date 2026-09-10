"""Input-Mapping-Foundation der Produktions-Application.

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

Gate 6 (Input Config) ergänzt die externe, validierte `keymap.json`:
- `schemaVersion` ist verpflichtend und muss exakt `1` sein
  (`KEYMAP_SCHEMA_VERSION`, kein Migrationsframework),
- die Konfiguration wird an der I/O-Grenze kontrolliert validiert
  (`KeymapConfigError`); Commands bleiben bewusst unvalidierte Strings,
- `command: null` bedeutet explizites Unbind für den jeweiligen Context
  und unterdrückt die Default-Auflösung,
- doppelte Bindings im selben Context: der spätere Eintrag gewinnt.

Bewusst klein und pyglet-frei: Eine spätere Window-/Adapter-Schicht übersetzt
plattform-Events in `Input`-Objekte (die einzige Stelle mit einer Render-/
Fenster-Abhängigkeit).

Context bleibt minimal: Es gibt einen GLOBAL_CONTEXT plus optionale
benannte Kontexte (hier: TOPOLOGY_CONTEXT für die Topology-Lab-Belegung).
Bei der Auflösung gewinnt der spezifische Kontext, sonst greift der
GLOBAL_CONTEXT-Fallback.

(Extrahiert aus dem Viewport-V1-Experiment, `input_binding.py`, unverändert
bis auf den Produktions-Kontext des Modul-Docstrings und die Gate-6-
Erweiterungen um Schema-Version, Validierung und explizites Unbind.)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

GLOBAL_CONTEXT = "global"
TOPOLOGY_CONTEXT = "topology"

KEYMAP_SCHEMA_VERSION = 1

_VALID_KINDS = ("key", "mouse", "wheel")
_VALID_MODIFIERS = ("ctrl", "shift", "alt")
_VALID_CONTEXTS = (GLOBAL_CONTEXT, TOPOLOGY_CONTEXT)


class KeymapConfigError(ValueError):
    """Kontrollierter Fehler für eine ungültige `keymap.json`-Konfiguration.

    Wird an der I/O-Grenze (`BindingSet.from_dict`/`from_json_file`) bei
    allen Schema-/Typ-/Werte-Verstößen geworfen (auch bei ungültigem JSON).
    Aufrufer müssen genau einen Fehlertyp für „Konfiguration ungültig"
    behandeln.
    """


def _parse_input(data: dict[str, Any]) -> Input:
    """Streng validierendes Parsen eines `input`-Objekts aus keymap.json.

    Prüft kind (`key`/`mouse`/`wheel`), value (String) und modifiers
    (`ctrl`/`shift`/`alt`). Wirft bei Verstößen `KeymapConfigError`.
    """
    kind = data.get("kind")
    if not isinstance(kind, str) or kind not in _VALID_KINDS:
        raise KeymapConfigError(
            f"Ungültiges input.kind: {kind!r} (erlaubt: {', '.join(_VALID_KINDS)})"
        )
    value = data.get("value")
    if not isinstance(value, str):
        raise KeymapConfigError(
            f"input.value muss ein String sein, ist {type(value).__name__}: {value!r}"
        )
    modifiers = data.get("modifiers", [])
    if not isinstance(modifiers, list):
        raise KeymapConfigError(
            f"input.modifiers muss eine Liste sein, "
            f"ist {type(modifiers).__name__}: {modifiers!r}"
        )
    for modifier in modifiers:
        if not isinstance(modifier, str) or modifier not in _VALID_MODIFIERS:
            raise KeymapConfigError(
                f"Ungültiger Modifier: {modifier!r} "
                f"(erlaubt: {', '.join(_VALID_MODIFIERS)})"
            )
    return Input(kind=kind, value=value, modifiers=frozenset(modifiers))


@dataclass(frozen=True)
class Input:
    """Physischer Input: kind + value + Modifier-Set.

    Beispiele:
        Input("key", "v")
        Input("key", "z", frozenset({"ctrl"}))
        Input("mouse", "LEFT")
        Input("mouse", "MIDDLE", frozenset({"shift"}))
        Input("wheel", "UP")

    Für das Lesen einer externen `keymap.json` bitte `BindingSet.from_dict`/
    `from_json_file` verwenden — dort validieren kind/value/modifiers streng
    (`KeymapConfigError`). `Input.from_dict` bleibt ein dünner, permissiver
    Serialisierungskonstruktor (Dict-Roundtrip).
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

    Gate 6 (Explicit Unbind): Ein User-Eintrag mit `command=None`
    (`bind(input, None)` bzw. `command: null` in keymap.json) löst für diesen
    Context terminal als „explizit ungebunden" auf — die Default-Auflösung
    (und der Global-Fallback für diesen Context) greift dann bewusst nicht
    mehr. `unbind()` dagegen entfernt nur die User-Bindung und lässt die
    Defaults wieder greifen.
    """

    def __init__(self) -> None:
        self._user: dict[tuple[str, Input], Optional[str]] = {}
        self._defaults: dict[tuple[str, Input], str] = {}

    # -- Ebenen -------------------------------------------------------------

    def set_default(
        self, input: Input, command: str, context: str = GLOBAL_CONTEXT
    ) -> None:
        """Default-Bindung (aus `default_bindings.build_default_bindings()`)."""
        self._defaults[(context, input)] = command

    def bind(
        self, input: Input, command: Optional[str], context: str = GLOBAL_CONTEXT
    ) -> None:
        """User-Bindung; überschreibt die Default-Belegung für denselben Input.

        `command=None` bindet den Input für `context` explizit ab (siehe
        Klassen-Docstring). `unbind()` entfernt dagegen nur die User-Bindung.
        """
        self._user[(context, input)] = command

    def unbind(self, input: Input, context: str = GLOBAL_CONTEXT) -> bool:
        """Entfernt eine User-Bindung; die Default-Belegung gilt dann wieder."""
        return self._user.pop((context, input), None) is not None

    def add_overrides(self, other: "BindingSet") -> None:
        """Übernimmt alle User-Bindungen aus `other` (z.B. aus keymap.json).

        Bei gleicher Input-Kombination im selben Context gewinnt der Eintrag
        aus `other` (innerhalb einer Datei: der später gelesene) —
        deterministisch, keine komplexe Konfliktauflösung.
        """
        self._user.update(other._user)

    # -- Auflösung ----------------------------------------------------------

    def command_for(
        self, input: Input, context: str | None = None
    ) -> Optional[str]:
        """Löst `input` auf ein Command auf (oder None, wenn ungebunden).

        Kontext-Priorität: übergebener Kontext → GLOBAL_CONTEXT. Innerhalb
        jeder Stufe: User-Ebene → Default-Ebene. Ein expliziter User-Eintrag
        (auch `None` = Unbind) beendet die Auflösung für diesen Kontext.
        """
        contexts = (context or GLOBAL_CONTEXT, GLOBAL_CONTEXT)
        for ctx in contexts:
            if (ctx, input) in self._user:
                return self._user[(ctx, input)]
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
        return {"schemaVersion": KEYMAP_SCHEMA_VERSION, "bindings": bindings}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BindingSet":
        """Validiert und lädt eine keymap.json als User-Overlay-Ebene.

        Wirft `KeymapConfigError` bei ungültiger Konfiguration: kein
        JSON-Objekt, fehlende/ungültige `schemaVersion` (muss exakt
        `KEYMAP_SCHEMA_VERSION` sein), `bindings` keine Liste, fehlende
        Pflichtfelder, ungültiges kind/value/modifiers, unbekannter context
        oder `command` weder String noch null. Ein `command: null` wird als
        explizites Unbind übernommen.
        """
        if not isinstance(data, dict):
            raise KeymapConfigError(
                f"keymap.json muss ein JSON-Objekt sein, ist {type(data).__name__}"
            )
        schema_version = data.get("schemaVersion")
        if type(schema_version) is not int or schema_version != KEYMAP_SCHEMA_VERSION:
            raise KeymapConfigError(
                f"Fehlende/ungültige schemaVersion: {schema_version!r} "
                f"(erwartet: {KEYMAP_SCHEMA_VERSION})"
            )
        bindings = data.get("bindings")
        if not isinstance(bindings, list):
            raise KeymapConfigError(
                f"'bindings' muss eine Liste sein, ist {type(bindings).__name__}"
            )
        bs = cls()
        for index, entry in enumerate(bindings):
            context, parsed_input, command = cls._parse_binding(index, entry)
            bs.bind(parsed_input, command, context=context)
        return bs

    @staticmethod
    def _parse_binding(
        index: int, entry: Any
    ) -> tuple[str, Input, Optional[str]]:
        """Validiert einen Bindungs-Eintrag → (context, input, command)."""
        prefix = f"Binding #{index}"
        if not isinstance(entry, dict):
            raise KeymapConfigError(
                f"{prefix} muss ein JSON-Objekt sein: {entry!r}"
            )
        context = entry.get("context", GLOBAL_CONTEXT)
        if not isinstance(context, str) or context not in _VALID_CONTEXTS:
            raise KeymapConfigError(
                f"{prefix}: ungültiger context {context!r} "
                f"(erlaubt: {', '.join(_VALID_CONTEXTS)})"
            )
        input_data = entry.get("input")
        if not isinstance(input_data, dict):
            raise KeymapConfigError(
                f"{prefix}: 'input' fehlt oder ist kein Objekt "
                f"(kind + value erwartet): {input_data!r}"
            )
        try:
            parsed_input = _parse_input(input_data)
        except KeymapConfigError as exc:
            raise KeymapConfigError(f"{prefix}: {exc}") from exc
        if "command" not in entry:
            raise KeymapConfigError(
                f"{prefix}: 'command' fehlt (String oder null erwartet)"
            )
        command = entry["command"]
        if command is not None and not isinstance(command, str):
            raise KeymapConfigError(
                f"{prefix}: 'command' muss ein String oder null sein, "
                f"ist {type(command).__name__}: {command!r}"
            )
        return context, parsed_input, command

    @classmethod
    def from_json_file(cls, path: str | Path) -> "BindingSet":
        """Lädt eine keymap.json als User-Overlay-Ebene (muss nicht existieren).

        Existiert die Datei nicht, wird ein leeres BindingSet zurückgegeben
        (Default-Belegung bleibt unverändert). Vorhandene, ungültige Dateien
        werden kontrolliert als `KeymapConfigError` abgelehnt.
        """
        p = Path(path)
        if not p.is_file():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise KeymapConfigError(
                f"keymap.json ist kein gültiges JSON: {exc}"
            ) from exc
        return cls.from_dict(data)