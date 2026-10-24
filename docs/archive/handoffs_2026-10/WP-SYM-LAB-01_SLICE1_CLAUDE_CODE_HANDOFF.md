# Handoff: WP-SYM-LAB-01 — Slice 1 (Geteilter pyglet → Input Translator)

**An:** Claude Code
**Modell/Effort:** Sonnet, effort `high`
**Modus (M5):** Production — Architektur ist entschieden, jetzt wird zuverlässig umgesetzt.
**BUILD darf keine neue Erkenntnis behaupten.** Wenn beim Implementieren etwas
unerwartet anders aussieht als hier beschrieben, nicht still weiterbauen — anhalten
und melden (siehe „Bei Widerspruch" am Ende).

**Namenshinweis:** `WP-SYM-01` (Slice 1/2) ist die bereits gemergte Symmetry-*Capability*
(`src/mirai/symmetry.py`, symmetrisches Move). `WP-SYM-LAB-01` ist das separate
**Symmetry Lab** (eigene Interaktionsumgebung). Nicht verwechseln, nicht vermischen.

---

## 1. Kontext (Ergebnis des Binding-Architecture-Checkpoints, 2026-09-24)

- Die Produktions-Binding-Schicht (`src/mirai/interaction/`: `Input`, `BindingSet`,
  `commands`, `routing`, `ToolManager`, Tools) ist bereits kontextfähig und hat
  **keine** Playground-Abhängigkeit. Ein zweiter Interaktionskontext braucht dort
  **keine Änderung**: `set_default`/`bind`/`command_for` akzeptieren beliebige
  Kontext-Strings, Auflösung = spezifischer Kontext → `global`, jeweils User → Default.
- Der Playground nutzt `BindingSet` seit `2477129` (AD-013 I4) **nicht** mehr. Er ist
  eigene, einzige Binding-Autorität für sein Fenster. Das bleibt so.
- Die einzige fehlende Brücke für ein zweites Fenster ist die Übersetzung
  pyglet-Event → `Input`. Diese existiert heute nur in `playground/input_adapter.py`
  (seit `2477129` unverdrahtet, „orphaned"). Das Symmetry Lab darf nicht aus
  `playground/` importieren.
- Entscheidung Artist (2026-09-24): Translator wird in ein **geteiltes Modul**
  außerhalb von `mirai.interaction` überführt. `mirai.interaction` bleibt pyglet-frei
  (siehe Docstring `input.py`: „Eine spätere Window-/Adapter-Schicht übersetzt
  plattform-Events in `Input`-Objekte" — genau diese Schicht entsteht hier).

## 2. Referenzdokumente (gelten, nicht neu verhandeln)

- `docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md` — **DECIDED.**
  I4 (eine Binding-Autorität pro Kontext), I5/I6 (Kontexte überschreiben eine
  Baseline sichtbar), A3 (Gesten-Semantik OFFEN — hier nichts festlegen).
- `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md` — Input beschreibt, *was*
  physisch passiert ist, nicht was es bedeutet.
- `docs/architecture/AD-011-PLAYGROUND-IDENTITY-STATUS-QUO.md` — Playground
  divergiert bewusst von Produktions-Bindings.
- `docs/architecture/CORE_V1_FREEZE.md` — Core wird in diesem Slice nicht berührt.

## 3. Ziel dieses Slices

Ein kleines, geteiltes, policy-freies Modul, das pyglet-Tastatur-, Maus- und
Wheel-Events in Produktions-`Input`-Objekte übersetzt — nutzbar von jedem künftigen
Fenster (zuerst dem Symmetry Lab), ohne Playground-Import. **Kein Fenster, kein
Lab, kein Wiring, keine neuen Commands, keine neuen Bindings.**

## 4. Scope

1. **Neue Datei `src/mirai/pyglet_input.py`** mit drei öffentlichen Funktionen:
   - `key_from_pyglet(symbol: int, modifiers: int) -> Input | None`
   - `mouse_from_pyglet(button: int, modifiers: int) -> Input | None`
   - `wheel_from_pyglet(scroll_y: float) -> Input | None`

2. **Verhalten = Kopie von `playground/input_adapter.py`**
   (`_key_from_pyglet`, `_mouse_from_pyglet`, `_wheel_from_pyglet`, Stand HEAD),
   mit genau diesen dokumentierten Abweichungen:
   - Rückgabetyp korrekt als `Input | None` annotiert (Original behauptet `-> Input`,
     gibt aber `None` zurück).
   - `wheel_from_pyglet(0)` gibt `None` zurück (Original liefert bei `0` fälschlich
     `"DOWN"`). `> 0` → `"UP"`, `< 0` → `"DOWN"` wie bisher.
   - Öffentliche Namen ohne führenden Unterstrich.
   - Die Lookup-Tabellen werden einmal auf Modulebene bzw. einmal lazy gebaut, nicht
     bei jedem Aufruf neu (Original baut das Dict pro Aufruf).

3. **Key-Set 1:1 übernehmen, nichts ergänzen:** A–Z, 0–9, TAB, ESCAPE, SPACE,
   UP/DOWN/LEFT/RIGHT. Weitere Keys (Enter, Delete, …) kommen erst mit dem
   Lab-Slice, der sie tatsächlich bindet — nicht vorsorglich.

4. **Value-Strings exakt wie heute**, weil `build_default_bindings()` sie so erwartet:
   Buchstaben/Ziffern klein (`"q"`, `"1"`), `"ESCAPE"` groß, `"tab"`/`"space"`/
   Pfeile klein, Maus `"LEFT"`/`"MIDDLE"`/`"RIGHT"`, Wheel `"UP"`/`"DOWN"`.
   Die gemischte Schreibweise ist bestehende Konvention — **nicht normalisieren**.
   Modifier: `ctrl`/`shift`/`alt` wie bisher (andere pyglet-Modifier ignorieren).

5. **pyglet-Import und Headless-Tests** — beobachteter Befund (Linux ohne Display):
   `from pyglet.window import key` auf Modulebene wirft
   `NoSuchDisplayException`. Genau daran scheitern die bestehenden
   `playground/tests/test_input_wiring*.py` headless. Mit
   `pyglet.options["headless"] = True` *vor* dem Import funktioniert es (Linux,
   verifiziert; Windows-Verhalten **nicht** verifiziert).
   Anforderung: Das neue Modul und seine Tests müssen in der bestehenden
   Produktions-Suite (`pytest tests`) sowohl headless unter Linux als auch auf
   Manus Windows-Rechner laufen. pyglet im Modul **lazy** importieren (Präzedenz:
   `src/viewport/resource_store.py`). Wie die Tests das Display-Problem lösen, ist
   eure Wahl — dokumentiert die gewählte Lösung im Test-Modul. Wenn es keine
   Lösung gibt, die auf beiden Plattformen ohne Skip läuft: anhalten und melden.

6. **Modul-Docstring** nennt: Herkunft (Kopie aus `playground/input_adapter.py`,
   eingeführt in `54e9840`), Grund (geteilte Adapter-Schicht, AD-013 I4, dieses
   Handoff), die Abweichungen aus Punkt 2, und dass das Modul **keine** Bedeutung
   vergibt (keine Commands, keine Kontexte).

## 5. Not in scope

- Symmetry-Lab-Fenster, Lab-Kontext, Lab-Commands, Lab-Bindings.
- Rendering/Viewport/Kamera/Picking für das Lab (eigene spätere Entscheidung —
  **nicht** aus `playground/` importieren oder kopieren).
- Maus-Drag, Hold, Press/Release-Semantik (AD-013 A3 OFFEN).
- Eine Klasse/Wrapper um `BindingSet` (Äquivalent zu `PlaygroundInputBinding` wird
  nicht gebraucht).
- Export aus `mirai/__init__.py` oder `mirai/interaction/__init__.py`.

## 6. Must NOT change (Diff muss hier leer sein)

- `src/core/**` (Core V1 frozen).
- `src/mirai/interaction/**` — insbesondere `input.py` (inkl. `_VALID_CONTEXTS`),
  `bindings.py` (Defaults, auch dort, wo sie von Artist Truth abweichen),
  `commands.py`, `routing.py`, `tool_manager.py`, Tools.
- `src/mirai/application.py`, `src/mirai/symmetry.py`, `src/viewport/**`.
- `playground/**` — inklusive der orphaned `input_adapter.py`/`command_handler.py`
  und ihrer Tests. Deren Aufräumen ist eine separate, offene Entscheidung.
- `tools/Input_Mapping_Tool/**`, `artist_input_truth.json`, `INPUT_WIRING_MAP.md`.
- Keymap-Schema.

Erwarteter Diff: **nur** `src/mirai/pyglet_input.py` (neu),
`tests/test_pyglet_input.py` (neu) und dieses Handoff-Dokument.

## 7. Erwartete Tests (`tests/test_pyglet_input.py`)

- Buchstaben → Kleinbuchstaben-Value, Ziffern, ESCAPE, TAB, SPACE, Pfeile.
- Modifier einzeln und kombiniert (`ctrl`, `shift`, `alt`, `ctrl+shift`);
  fremde pyglet-Modifier (z. B. NumLock/CapsLock) erscheinen nicht im Input.
- Unbekanntes Key-Symbol → `None`; unbekannter Maus-Button → `None`.
- Maus LEFT/MIDDLE/RIGHT mit und ohne Modifier.
- Wheel: positiv → `UP`, negativ → `DOWN`, `0` → `None`.
- **Integration gegen die echten Defaults** (`build_default_bindings()`):
  Q → `Move`, Ctrl+Z → `Undo`, Ctrl+Y → `Redo`, ESC → `Cancel`, LMB → `Select`.
- **Zweiter Kontext ohne Änderung an `BindingSet`** (belegt den Checkpoint-Befund):
  ein beliebiger Kontext-String (z. B. `"symmetry_lab"`) mit eigener Belegung
  gewinnt dort; ein nicht belegter Input fällt auf `global` zurück; explizites
  Unbind (`bind(input, None, context=...)`) unterdrückt den Fallback.
  Alles über die öffentliche `BindingSet`-API, kein Eingriff in `input.py`.
- **Grenz-Invariante:** Nach `import mirai.interaction` (in einem frischen
  Subprozess) ist `pyglet` **nicht** in `sys.modules`.

## 8. Done-Kriterien

- Neue Tests grün.
- Bestehende Suite unverändert grün
  (`pytest tests --ignore=tests/test_extrude_tool.py`, wie in `ce6f040`).
- `git diff --stat` enthält nur die Dateien aus §6 „Erwarteter Diff".
- Commit-Message-Vorschlag:
  `WP-SYM-LAB-01 Slice 1: shared pyglet→Input translator (src/mirai/pyglet_input.py)`

## 9. Bei Widerspruch

Anhalten und melden, nicht still lösen, insbesondere wenn:

- ein bestehender Test bricht,
- das Headless/Windows-Importproblem (§4.5) nicht ohne Skip lösbar ist,
- sich herausstellt, dass `build_default_bindings()` andere Value-Strings erwartet
  als in §4.4 beschrieben,
- irgendeine Änderung an einer Datei aus §6 nötig erscheint.
