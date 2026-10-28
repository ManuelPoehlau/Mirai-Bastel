# Mirai-Bastel — Input / Command / Tool / Operation Contract

**Status:** Accepted architectural contract for WP-01A; implementiert und praktisch validiert im Viewport-V1-Experiment (`experiments/mirai_bastel_viewport_V1/`, 2026-08-29)
**Date:** 2026-08-29
**Branch:** `main`

This document defines the basic separation between physical input, user commands, interactive tools and model-changing operations. It is intentionally small and is not a commitment to a large generic input framework.

## 1. Purpose

Mirai-Bastel should support direct, fast modeling interaction while allowing users to configure keyboard and mouse bindings without changing tool or modeling implementation code.

The basic conceptual path is:

```text
Physical Input
      ↓
Input Mapping
      ↓
Command
      ↓
Tool / Action
      ↓
Operation
      ↓
History / Core
```

Not every command requires every layer.

```text
Input
  ↓
Command
  ↓
[optional Tool]
  ↓
[optional Operation]
  ↓
[optional History]
```

## 2. Definitions

### Input

A physical user interaction: key, mouse button, wheel event, modifier combination, or equivalent device event.

Input describes **what happened**, not what that input means in the application.

Examples:

- `M`
- `Ctrl+Z`
- `LMB`
- `MMB drag`
- `Shift+MMB`
- mouse wheel

### Command

A named user action with application meaning.

Examples:

- `Move`
- `Extrude`
- `ConnectEdges`
- `Undo`
- `Redo`
- `Orbit`
- `ToggleWireframe`

A Command is not a hotkey. A hotkey or mouse binding is only one possible way to invoke a Command.

### Tool

An interactive, temporary working state used when a Command requires modal interaction.

A Tool may handle:

- activation;
- interaction/update;
- preview;
- constraints;
- confirmation;
- cancellation.

Example:

```text
Command.Move → MoveTool
```

A Command does not necessarily require a Tool. `Undo` or `ToggleWireframe` may be direct actions.

### Operation

A domain-level change to persistent model data.

Operations must not depend on keyboard, mouse, viewport or UI details. They receive domain-relevant data and perform the corresponding model change.

Example:

```text
MoveTool → MoveOperation → Mesh
```

### History

History records committed model changes according to the existing Core V1 History contract. Interactive preview updates must not accidentally become a separate History entry for every mouse movement.

## 3. Binding and Context

Bindings belong to an input-mapping layer, not to individual Tools.

The conceptual resolution path is:

```text
Input
  ↓
Context
  ↓
Binding
  ↓
Command
```

The implementation should support enough context to distinguish current viewport/editor interactions from global actions, but must not introduce a complex hierarchical context framework without a demonstrated use case.

A binding may be changed without changing the Command, Tool or Operation implementation.

For example:

```text
Default:
M → Move

User-configured:
G → Move
```

Both invoke the same `Move` Command.

The same principle applies to mouse bindings.

## 4. Examples

### Modeling command

```text
M
↓
Input Mapping
↓
Command.Move
↓
MoveTool
↓
MoveOperation
↓
History
```

### Viewport navigation

```text
MMB drag
↓
Input Mapping
↓
Command.Orbit
↓
Viewport / Camera action
```

No Core Operation or History entry is required.

### Display mode

```text
W
↓
Input Mapping
↓
Command.ToggleWireframe
↓
Viewport display action
```

Again, this is not a model edit and does not belong in model History.

## 5. Architectural Rules

1. Physical input must not be hard-coded directly into individual modeling implementations.
2. Bindings map Inputs to Commands.
3. Commands express user intent, not physical input.
4. Tools own temporary interactive/modal state.
5. Operations own persistent model changes.
6. Operations must remain independent of UI/input details.
7. History records committed model changes, not every transient interaction event.
8. Viewport-only actions must not create model History entries.
9. Context handling should remain minimal until real use cases require more.
10. This contract does not require a full Preferences UI; a minimal configurable binding representation/API is sufficient for WP-01A.

## 6. Relationship to the Core Freeze

This contract does not authorize changes to `src/core/`.

If implementation of the input/tool boundary reveals a missing production Core capability, the requirement must be demonstrated and documented first. Any Core change remains an explicit architecture decision under the project's experiment/Core-freeze policy.

## 7. Scope for WP-01A

WP-01A uses this contract to establish:

- basic configurable keyboard bindings;
- basic configurable mouse bindings;
- viewport navigation;
- selection interaction;
- Shaded / Flat Shaded / Wireframe display modes;
- Wireframe Overlay on/off;
- clear user feedback;
- automated mapping/state tests;
- practical viewport verification.

A full keymap editor, plugin system, command palette, sophisticated preferences system and generic framework are explicitly outside this package.

---

## 8. External Input Configuration (keymap.json) — Gate 6

**Status:** Production-Validierung Gate 6 (2026-09-08), `src/mirai/interaction/input.py`. Kein neues Input-Architektur-Konzept — ergänzt §3/§4 um die extern validierte Konfiguration.

Die Default-Belegung (`build_default_bindings()`) kann beim Application-Start durch eine optionale `keymap.json` als User-Overlay ergänzt werden:

```text
Default Bindings          (Engineering, `PROVISIONAL`)
      ↓
config/keymap.json        (Manus Belegung, im Repo)
      ↓
BindingSet                (die einzige Input-Wahrheit)
```

*Aktualisiert 2026-10-28 ([AD-013 Addendum 2026-10-28](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-28-the-active-bindingset-is-the-single-input-truth-manus-keymap-in-the-repo)):*
das aktive BindingSet ist die einzige Input-Wahrheit. Die Ebene sagt die Herkunft: ein Eintrag in `config/keymap.json` =
von Manu gesetzt; nur Code-Default = Engineering, `PROVISIONAL`. Ein späterer In-App-Hotkey-Editor bearbeitet genau diese
Datei. Agenten lesen sie, schreiben sie nie, und prüfen eine neue Default-Taste gegen sie.

### 8.1 Format

```json
{
  "schemaVersion": 1,
  "bindings": [
    {
      "context": "global",
      "input": { "kind": "key", "value": "m", "modifiers": [] },
      "command": "MOVE"
    }
  ]
}
```

- `schemaVersion` ist verpflichtend und muss exakt `1` sein (`KEYMAP_SCHEMA_VERSION`). Es gibt kein Migrationsframework.
- `context`: `"global"`, `"knife"`, `"subd"`, `"morph"`, `"window"` oder `"topology"` (bestehende Kontexte; ein unbekannter Context wird abgelehnt). `"window"` = Tasten, die das Fenster selbst behandelt (`src/main.py`: Leertaste, Shift+A, Shift+M, M, Ctrl+S, Ctrl+Shift+S, H), `Application` löst ihn nie auf. `"topology"` hat seit 2026-10-28 keine Defaults mehr (kein Host löst ihn auf), bleibt aber gültig. *(Seit 2026-10-28; vorher `global`, `topology`, `knife`, `subd`.)*
- `input.kind`: `"key"` | `"mouse"` | `"drag"` | `"wheel"`; `input.value` ein String; `input.modifiers` eine Liste aus `"ctrl"`, `"shift"`, `"alt"`. `mouse` = click, `drag` = press+move ≥ threshold (AD-019).
- `command`: String (Command-Name) oder `null`.
- Optional pro Eintrag: `"set": "YYYY-MM-DD"` — wann Manu die Bindung gesetzt hat (additiv seit 2026-10-28; der Parser ignoriert unbekannte Eintrags-Schlüssel, daher keine neue `schemaVersion`, Präzedenz AD-019).

Die Case-Semantik der bestehenden Auflösung bleibt erhalten (exakter Vergleich, keine pauschale Lowercase-Transformation). `command` wird unverändert als String behandelt.

### 8.2 Validierung an der I/O-Grenze

Ungültige Konfigurationen werden kontrolliert mit `KeymapConfigError` abgelehnt: ungültiges JSON, fehlende/falsche `schemaVersion`, `bindings` keine Liste, fehlende Pflichtfelder eines Bindings, ungültiges `kind`/`value`/`modifiers`, unbekannter `context` oder `command` weder String noch `null`. Commands werden bewusst NICHT gegen ein festes Enum oder eine Registry validiert — der Input-Layer behandelt sie als Strings.

*Seit 2026-10-28 zusätzlich (`mirai.interaction.bindings.check_keymap`):*
- **Halte-Commands nur auf Tasten:** `commands.HOLD_COMMANDS` (Move, Rotate, Scale, Extrude, LoopSlide, Smooth, Relax, LassoArm, LightDrag, MorphWeightDrag) enden mit dem Loslassen ihrer Taste; ein Eintrag mit `kind` ≠ `"key"` macht die Datei ungültig. Ein `null` (Unbind) ist auf jedem Input erlaubt.
- **Unbekannte Command-Namen warnen, lehnen nicht ab:** ein Name, den `mirai.interaction.commands` nicht kennt, wird geladen (er wirkt nicht) und als Warnung gemeldet.

### 8.3 Explicit Unbind

`command: null` ist ein explizites Unbind für den jeweiligen Context und unterdrückt die Default-Auflösung:

```text
Default: M → MOVE
keymap:  M → null
Result:  M → unbound
```

Doppelte Einträge im selben Context: **der spätere gewinnt** (deterministisch). Gleiche Inputs in verschiedenen Contexts sind kein Fehler.

### 8.4 Lifecycle

- Geladen wird beim Application-Start bzw. beim Aufbau der Bindings (`Application(keymap_path=...)`); fehlt die Datei, bleiben die Defaults unverändert.
- Kein Runtime-Hot-Reload, keine Preferences-UI.
- *Seit 2026-10-28:* **Ort** `config/keymap.json` im Repo (`bindings.KEYMAP_PATH`, relativ zur Repo-Wurzel über `pathlib`, gleich auf Windows 10 und Linux). `src/main.py` und jeder Lab-Host auf `Application` (heute das Morph Lab) übergeben diesen Pfad (AD-013 A1); `Application()` ohne Pfad = nur Defaults (Tests, Messsonden).
- *Seit 2026-10-28:* **Ladeverhalten** `bindings.load_keymap` bricht nie ab: eine ungültige Datei wird **ganz** verworfen (keine halbe Übernahme), die Defaults gelten, und das Problem ist laut — `Application.keymap_load.problem` als Statuszeile, eine Zeile auf stderr beim Start (`main.print_input_listing`), die HUD-Zeile „Keymap“. Warnungen (unbekannte Commands) gehen auf stderr. `load_keymap_overrides` bleibt die strenge Variante (wirft `KeymapConfigError`).
- *Seit 2026-10-28:* **Feste Modifier-Grammatik** — Shift fein, Ctrl Raster, Alt Kamera / durch das Mesh wählen während einer Geste, Shift Kantenmitte im Knife, Shift+Klick im Szenen-Menü — liest das Fenster aus den gehaltenen Tasten (`set_shift_held` / `set_ctrl_held` / `set_alt_held`), nicht über das BindingSet; nicht umbelegbar, gelistet in `bindings.FIXED_MODIFIER_RULES` (Start-Listing, HUD-Zeile „Fixed“).
