# WP-04 Gate 6 — Input Config (keymap.json) — Completion Report

**Status:** ✅ COMPLETE — implementierungsseitig fertig (formeller Abschluss durch Gate 11 Architecture Review)
**Date:** 2026-09-08
**Mode:** Cline
**Branch:** `Integration-Lab-Expriment`
**Vertrag:** `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md` (§8)
**Vorgänger:** `docs/WP-04_GATE_5_COMPLETION.md`
**Auftrag:** Gate 6 — Input Config (Scope exakt laut Auftrag)

---

## 1. Ergebnis

Die bestehende Input-/Binding-Architektur (`src/mirai/interaction/input.py`, `bindings.py`) wurde **minimal** um eine robuste, validierte externe JSON-Konfiguration ergänzt. Keine neue Input-Architektur, keine neuen UX-Konzepte, keine `src/core/`-Änderungen.

### Umgesetzt

- **keymap.json-Format:** Pflicht-`schemaVersion` (exakt `1`, `KEYMAP_SCHEMA_VERSION`), `bindings[]` mit `context`/`input{kind,value,modifiers}`/`command`.
- **Validierung an der I/O-Grenze:** kontrollierter `KeymapConfigError` für ungültiges JSON, fehlende/falsche `schemaVersion`, `bindings`-Non-Liste, fehlende Pflichtfelder, ungültiges `kind`/`value`/`modifiers`, unbekannter `context`, `command` weder String noch `null`. Commands bleiben bewusst unvalidierte Strings (keine Registry, kein Enum).
- **Explicit Unbind:** `command: null` → explizit ungebunden für den jeweiligen Context, unterdrückt die Default-Auflösung — minimale `BindingSet`-Erweiterung (User-Ebene akzeptiert `None`; `command_for` löst vorhandene User-Einträge terminal auf).
- **Override / Duplikate / Context:** `Context > global`, `User > Default` (bestehend, unverändert); späterer identischer Eintrag im selben Context gewinnt (bestehende Dict-Semantik, deterministisch).
- **Laden:** `Application(keymap_path=...)` lädt die optionale `keymap.json` genau einmal beim App-Start über den bestehenden Pfad `load_keymap_overrides` → `BindingSet.from_json_file`. Fehlende Datei = No-op. Kein Hot-Reload.
- **Serialisierung:** `schemaVersion` ist Bestandteil von `to_dict()`/`to_json()`; Dict-/JSON-Roundtrip (inkl. Unbind-Einträgen) getestet.

### Bewusst NICHT geändert (Scope-Disziplin)

- **Case:** keine neue Case-Semantik; `command` (z. B. `"MOVE"`) bleibt unverändert; `kind`/`context`/`modifiers`/`value` verwenden die bestehende exakte Vergleichslogik.
- Keine Command-Registry/Enum-Validierung, kein Migrationsframework, keine komplexe Konfliktauflösung.
- Keine Änderungen an `src/core/`, kein Pyglet/Window/Renderer/Entry-Point, keine Selection-SUX-/Tool-Verdrahtung, keine Preferences-UI, kein Runtime-Hot-Reload.

## 2. Geänderte Dateien

| Datei | Zweck |
|---|---|
| `src/mirai/interaction/input.py` | `KEYMAP_SCHEMA_VERSION`; `KeymapConfigError`; `_VALID_MODIFIERS`/`_VALID_CONTEXTS`; `_parse_input` (strenge Validierung); `BindingSet`: Unbind via `None` + terminale Auflösung in `command_for`, `schemaVersion` in der Serialisierung, validiertes `from_dict`/`from_json_file` |
| `src/mirai/interaction/bindings.py` | `load_keymap_overrides`-Docstring präzisiert (kontrollierte Ablehnung) |
| `src/mirai/interaction/__init__.py` | Export `KeymapConfigError`, `KEYMAP_SCHEMA_VERSION` |
| `src/mirai/application.py` | Optionaler `keymap_path`-Parameter in `Application.__init__` (Laden beim App-Start) |
| `tests/test_input_binding.py` | 33 neue Gate-6-Tests (Override, Unbind, Validation, Context, Duplikate, Serialisierung); bestehendes keymap-Fixture um `schemaVersion` ergänzt |
| `tests/test_application.py` | `ApplicationKeymapTests` (Keymap-Override, Unbind, fehlende Datei, ungültige Datei) |
| `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md` | Neuer Abschnitt §8 „External Input Configuration (keymap.json) — Gate 6“ |
| `docs/WP-04_GATE_PLANNING.md` | Gate-6-Zeile auf `✓ DONE` |

## 3. Tests (headless, ohne Pyglet/Fenster/GPU)

- `python -m unittest tests.test_input_binding tests.test_application -v` → **77/77 OK** (40 bestehende + 37 neue Tests inkl. Gate 6).
- `python -m pytest tests --ignore=tests/test_extrude_tool.py -q` → **338 passed** (Exit 0).
- `python -m tests.run_core_suite` → **PASS** (Core-Standard-Suite unverändert; kein Core-Touch).

## 4. Vorbestehender Befund (nicht Teil von Gate 6)

`tests/test_extrude_tool.py` ist unter `python -m unittest discover -s tests` nicht importierbar: Zeilen 15–17 referenzieren `../mirai_bastel_core_V1` (Repo-Root) statt `experiments/mirai_bastel_core_V1` (letzte Änderung `003370f`). Die Datei ist nicht Teil des Standard-Runners und wurde von Gate 6 nicht angefasst. Empfehlung: separat klären (Importpfad ist seit der Experiment-Restrukturierung „stale“).

## 5. Offene Punkte / Hinweise

- **Decision:** `context` wird an der I/O-Grenze auf `global`/`topology` validiert — abgeleitet aus §1 des Gate-Auftrags („Unterstützte bestehende Kontexte“), nicht explizit in der „Mindestens“-Validierungsliste; konsistent mit „robuste, validierte externe JSON-Konfiguration“. Künftige neue Contexts erfordern eine Erweiterung von `_VALID_CONTEXTS`.
- **Semantik Unbind + Global-Fallback:** Ein explizites `null` im spezifischen Context beendet die Auflösung für diesen Context terminal (kein Global-Fallback mehr), passend zu „Context > global / User > Default“. Ein `null` im `global`-Context blockiert entsprechend nur dortige Fallbacks.
- **Format-Bruch:** Bestehende keymap.json-Dateien ohne `schemaVersion` werden jetzt kontrolliert abgelehnt (vorher stillschweigend als `str(None)`-Bug geladen) — gewollt laut Gate-6-Spezifikation.
- Formeller Gate-Abschluss: Gate 11 (Architecture Review), analog zu den Vor-Gates.