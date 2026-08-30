# Cline — Work Package WP-02
## Interaction & Tool Framework

Arbeite an **WP-02 — Interaction & Tool Framework** im Repository `ManuelPoehlau/Mirai-Bastel`, Branch `main`.

Die verbindliche Spezifikation ist:

```text
docs/Mirai-Bastel — Work Package WP-02.md
```

Diese Datei ist nur die operative Delegation. Die Spezifikation ist maßgeblich; bei Widersprüchen hat der aktuelle Repository-Code Vorrang und eine notwendige Architekturabweichung muss dokumentiert werden.

---

## Arbeitsregel

Dies ist ein zusammenhängendes technisches Arbeitspaket.

Arbeite in dieser Reihenfolge:

```text
Repository analysieren
      ↓
Architektur verstehen
      ↓
konkreten Implementierungsplan erstellen
      ↓
Implementierung als zusammenhängenden Block
      ↓
automatische Tests
      ↓
praktischer Viewport-Test
      ↓
Scope-/Architektur-Review
      ↓
Dokumentation
      ↓
Git-Diff prüfen
      ↓
Commit
```

Nicht einfach Datei für Datei ändern, ohne zuerst die bestehende Architektur und die Auswirkungen zu verstehen.

---

## Vor Implementierung lesen

Mindestens:

1. `AGENTS.md`
2. `docs/Mirai-Bastel — Work Package WP-02.md`
3. `docs/architecture/ROADMAP.md`
4. `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md`
5. `docs/architecture/SOURCE_ARCHITECTURE.md`
6. `docs/architecture/CORE_V1_FREEZE.md`
7. `docs/design/WORKFLOW.md`
8. `experiments/mirai_bastel_viewport_V1/README.md`
9. relevanten aktuellen Code unter `src/core/`
10. relevanten aktuellen Viewport-/Command-/Input-/Selection-/Move-Code unter `experiments/mirai_bastel_viewport_V1/`
11. bestehende Tests für Move, Selection, Input und History

Der Repository-Stand auf `main` ist maßgeblich. Keine früheren Chatannahmen ungeprüft übernehmen.

---

## Ziel

Aus der aktuell funktionierenden, aber teilweise impliziten Viewport-Interaktion eine kleine echte Tool-Grenze machen:

```text
Input
  ↓
Command
  ↓
Tool / Interaction
  ↓
Operation
  ↓
History
  ↓
Core
```

**Move ist die einzige konkrete Referenzimplementierung dieses WPs.**

---

## Zentrale Regeln

### Tool

Tool besitzt temporären Interaktionszustand und behandelt:

- Aktivierung
- Beginn der Interaktion
- Input-/Pointer-Interpretation
- Updates/Preview
- Commit
- Cancel
- Deaktivierung

### Operation

Operation bleibt Domain-Logik.

Die bestehende Core-`MoveOperation` ist wiederzuverwenden. Keine zweite Move-Mutationslogik bauen.

### Selection

Selection bleibt vorhandener Core-/Editor-State.

Nicht in ein Tool umwandeln und kein neues Selection-Framework bauen.

### Input

Keine physischen Tasten-/Maustasten-Konstanten in MoveTool oder anderen Modeling-Tools.

Bindings → Commands → Tools.

### History

Commit ist die History-Grenze.

Mehrere Pointer-Updates dürfen nicht mehrere History-Einträge erzeugen.

Cancel darf keinen neuen History-Eintrag erzeugen und muss den Vorzustand wiederherstellen.

---

## Bewusst nicht bauen

Nicht in diesem WP:

- Rotate
- Scale
- Transform Framework
- Pivot
- Local/Global Space
- Gizmo
- Snapping
- Soft Selection
- Object Mode
- Object/Component Model
- Keymap Editor
- Preferences
- Plugin-System
- Command Palette
- neue Renderer-Architektur
- neue Topology-Architektur
- Extrude/Inset/Bevel/Slide/Loop Insert
- Morph/Skin/Rigging/Animation
- vorsorgliche Core-Erweiterungen

Insbesondere keine neuen `src/tools/`- oder `src/viewport/`-Produktionsstrukturen nur für dieses Experiment. Die Produktionsstruktur außerhalb von `src/core/` bleibt eine spätere Architekturentscheidung.

---

## Core Freeze

`src/core/` bleibt unverändert.

Falls eine Core-Erweiterung scheinbar erforderlich wird:

1. konkrete fehlende Fähigkeit identifizieren;
2. prüfen, ob die bestehende öffentliche API ausreicht;
3. Anforderung dokumentieren;
4. nicht opportunistisch Core ändern;
5. bei echter Notwendigkeit anhalten und die Architekturfrage melden.

---

## Tests

Ergänze fokussierte automatische Tests für:

- Tool-State/Lifecycle;
- Active-Tool-Verhalten;
- MoveTool → MoveOperation;
- mehrere Updates;
- Commit → genau eine logische History-Aktion;
- Cancel → exakter Vorzustand, kein neuer History-Eintrag;
- Command.Move → MoveTool;
- Input-Binding-Unabhängigkeit des Tools;
- keine pyglet Input-Konstanten im Tool-Code.

Alle bestehenden Tests müssen weiterhin bestehen.

Die Produktions-Core-Suite muss weiterhin vollständig grün sein.

---

## Praktischer Test

Im echten Viewport:

### Commit

```text
Geometry auswählen
→ Move/Tweak starten
→ sichtbar bewegen
→ mehrere Updates
→ Commit
→ Undo
→ Ausgangszustand
→ Redo
→ Move wiederhergestellt
```

### Cancel

```text
Geometry auswählen
→ Move starten
→ deutlich verschieben
→ Esc
→ exakter Ausgangszustand
→ kein zusätzlicher History-Schritt
```

Danach prüfen:

- kein stale Drag-/Tool-State;
- Selection bleibt kohärent;
- Orbit/Pan/Zoom funktionieren weiter;
- Topology Commands funktionieren weiter;
- Viewport-Aktionen erzeugen keine Model-History.

Wenn die reale UI in der verfügbaren Umgebung nicht bedienbar ist, nicht behaupten, der praktische Test sei bestanden. Den fehlenden Freigabepunkt klar dokumentieren.

---

## Review vor Commit

Prüfe ausdrücklich:

```text
Input
 ↓
Command
 ↓
Tool
 ↓
Operation
 ↓
History/Core
```

und:

- Tool und Operation sind getrennt;
- Tool besitzt transienten Zustand;
- Operation kennt keine UI/Input-Bibliothek;
- Selection ist kein Tool;
- Commit/Cancel sind eindeutig;
- keine History-Flut durch Updates;
- keine unnötige Generalisierung;
- kein Scope Creep;
- `src/core/` unverändert;
- bestehende WP-01A-Funktionalität bleibt erhalten.

---

## Abschluss

Erst wenn Tests, praktischer Test und Review erfolgreich sind:

1. relevante Dokumentation aktualisieren;
2. finalen Diff prüfen;
3. sauberen Commit erstellen;
4. Commit-SHA und Testergebnis ausgeben;
5. kurz auflisten, welche Dateien geändert wurden und warum.

Bei einer grundlegenden Architekturabweichung **nicht selbstständig die Architektur neu definieren**. Problem dokumentieren und anhalten.
