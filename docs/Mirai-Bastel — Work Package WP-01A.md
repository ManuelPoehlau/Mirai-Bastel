# Mirai-Bastel — Work Package WP-01A
## Basic Viewport & Input Foundation

Arbeite an **WP-01A — Basic Viewport & Input Foundation** im Repository `ManuelPoehlau/Mirai-Bastel`, Branch `main`.

## Wichtige Arbeitsregel

Dies ist ein zusammenhängendes technisches Arbeitspaket.

Arbeite nicht nach dem Muster „eine kleine Änderung nach der anderen“, sondern:

**Repository analysieren → Architektur verstehen → Plan erstellen → Implementierung als zusammenhängenden Block → Tests → praktischer Viewport-Test → Review → Dokumentation → Commit.**

### Noch nichts ändern

Beginne zunächst ausschließlich mit einer Analyse des aktuellen Repository-Stands und einem konkreten Implementierungsplan.

Lies dafür insbesondere:

1. `AGENTS.md`
2. `docs/architecture/ROADMAP.md`
3. `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md`
4. `docs/architecture/SOURCE_ARCHITECTURE.md`
5. relevante Core-/V1-Dokumentation
6. vorhandene READMEs
7. relevante Dateien unter `src/`
8. den aktuellen Stand der Viewport-/Selection-/Picking-Experimente unter `experiments/`

Berücksichtige insbesondere die bereits vorhandenen Erfahrungen aus:

- Core V1
- Viewport V1
- Picking
- Selection
- Loop / Ring
- History / Undo / Redo
- Connect Edges

Der aktuelle Repository-Code auf `main` ist maßgeblich. Frühere Chatannahmen dürfen nicht ungeprüft übernommen werden.

---

# Ziel des Arbeitspakets

Der Viewport soll zu einem **angenehmen, schnellen und konfigurierbaren täglichen Testarbeitsplatz** werden.

Der Schwerpunkt liegt nicht auf einem vollständigen UI-System.

Wir wollen zunächst die grundlegenden Dinge sauber etablieren, die wir für die weitere Entwicklung und das praktische Testen von Modeling-/Topology-Funktionen benötigen.

Insbesondere:

- zuverlässige Viewport-Navigation
- klare Maus-/Keyboard-Interaktion
- grundlegende Display Modes
- angenehme Selection-Bedienung
- konfigurierbare Hotkeys
- konfigurierbare Maustasten
- saubere Grundlage für spätere Tools

---

# Architekturvertrag

Der folgende Vertrag ist verbindlich:

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

Nicht jeder Command benötigt alle Ebenen.

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

## Begriffe

### Input

Physische Eingabe:

- Tastaturtaste
- Maustaste
- Mausrad
- Modifier
- Kombinationen

Input beschreibt **was physisch passiert ist**, nicht dessen Bedeutung.

### Command

Benannte Benutzeraktion.

Beispiele:

```text
Move
Extrude
ConnectEdges
Undo
Redo
Orbit
ToggleWireframe
```

Ein Hotkey ist NICHT selbst ein Command.

### Tool

Interaktiver, temporärer Zustand eines Commands.

Beispiel:

```text
Move Command
    ↓
Move Tool
    ↓
Preview
    ↓
Confirm / Cancel
```

### Operation

Domain-Level-Änderung an persistenten Modelldaten.

Operations dürfen nicht von Keyboard, Mouse, Viewport oder UI abhängen.

Beispiel:

```text
MoveTool
    ↓
MoveOperation
    ↓
Mesh
```

### History

Committed model changes werden über die bestehende History-Struktur behandelt.

Transienter Preview-Zustand darf nicht versehentlich zu vielen History-Einträgen führen.

---

# Input Mapping

Bindings dürfen NICHT direkt in einzelnen Tools hard-coded werden.

Nicht:

```text
MoveTool = M
```

sondern konzeptionell:

```text
M → Command.Move
```

und nach einer Benutzeränderung beispielsweise:

```text
G → Command.Move
```

ohne dass MoveTool oder MoveOperation geändert werden müssen.

Das gleiche gilt für Mouse Bindings.

Die Auflösung soll konzeptionell sein:

```text
Input
  ↓
Context
  ↓
Binding
  ↓
Command
```

Das Context-System soll zunächst minimal bleiben.

Kein unnötig komplexes globales Input-/Context-Framework bauen.

---

# Scope

## 1. Viewport Navigation

Untersuche und verbessere, soweit der aktuelle Code dies erlaubt:

- Orbit
- Zoom
- Pan
- ggf. Frame/Fokus auf Selection, falls sinnvoll
- Modifier-Verhalten

Die Bedienung soll konsistent und zuverlässig sein.

---

## 2. Display Modes

Mindestens:

```text
Shaded
Flat Shaded
Wireframe
```

Zusätzlich:

```text
Wireframe Overlay: ON / OFF
```

Damit sollen insbesondere diese Kombinationen sinnvoll möglich sein:

```text
Shaded
Shaded + Wire
Flat Shaded
Flat Shaded + Wire
Wireframe
```

Der wichtigste praktische Anwendungsfall ist:

**Flat Shaded + Wireframe**

weil dieser Modus die Prüfung neuer Topology erheblich erleichtert.

Die Architektur soll Display-Zustände sauber trennen, ohne bereits einen vollständigen Renderer-/Material-Stack zu entwerfen.

---

## 3. Selection Interaction

Behalte das aktuell akzeptierte Verhalten soweit wie möglich bei und untersuche den tatsächlichen Repository-Stand.

Grundsätzlich benötigen wir:

- Vertex Selection
- Edge Selection
- Face Selection
- Toggle Selection
- Multi Selection
- Deselection durch Klick ins Leere
- eindeutiges Hover-/Selection-Feedback

Ändere bestehendes Selection-Verhalten nicht ohne konkreten technischen Grund und dokumentiere notwendige Abweichungen.

---

## 4. Keyboard Bindings

Implementiere eine kleine, saubere Grundlage für konfigurierbare Keyboard-Bindings.

Wichtig:

```text
Key
 ↓
Binding
 ↓
Command
```

Nicht:

```text
Key
 ↓
direkt Tool-Code
```

Die tatsächliche Default-Belegung soll aus dem bestehenden Projekt und der aktuellen Bedienung abgeleitet werden.

Erfinde nicht unnötig viele Hotkeys.

---

## 5. Mouse Bindings

Das gleiche Prinzip gilt für:

- LMB
- MMB
- RMB
- Wheel
- Modifier + Mouse Button

Die konkreten Defaults sollen aus dem bestehenden Viewport-Verhalten abgeleitet werden.

Die Belegung muss grundsätzlich austauschbar sein, ohne die eigentliche Command-/Tool-Implementierung zu ändern.

---

# Nicht im Scope

NICHT bauen:

- vollständige Preferences-Anwendung
- vollständigen Keymap-Editor
- Plugin-System
- Command Palette
- Gizmo Framework
- vollständige UI-Architektur
- Material-System
- vollständige Renderer-Architektur
- Object/Component-System
- Deformation-System
- Rigging
- Animation
- umfangreiche neue Core-Abstraktionen

Insbesondere:

**Keinen großen generischen Input-Framework-Overkill bauen.**

Implementiere nur die Infrastruktur, die für das aktuelle Arbeitspaket und die absehbare Tool-Integration tatsächlich notwendig ist.

---

# Core-Freeze

`src/core/` ist weiterhin geschützt.

Das Arbeitspaket autorisiert **keine automatische Core-Änderung**.

Wenn während der Umsetzung eine fehlende Core-Funktion festgestellt wird:

1. Problem konkret identifizieren.
2. Prüfen, ob es wirklich eine Core-Anforderung ist.
3. Bestehende Experimente berücksichtigen.
4. Keine opportunistische Core-Änderung durchführen.
5. Die Anforderung als Architektur-/Core-Frage dokumentieren.
6. Nur nach expliziter Begründung und Review eine Core-Änderung vornehmen.

Die bestehende Experimentstrategie bleibt erhalten.

---

# Tests

Ergänze sinnvolle automatische Tests.

Mindestens prüfen:

## Input Mapping

- Default Binding
- geändertes Binding
- mehrere Bindings
- Command-Auflösung
- Context-Verhalten, sofern implementiert
- keine direkte Kopplung von Tool-Code an konkrete Tasten

## Display State

- Shaded
- Flat Shaded
- Wireframe
- Wireframe Overlay
- gültige Zustandswechsel

## Regression

Alle vorhandenen Tests müssen weiterhin bestehen.

Keine bestehenden Core-Verträge brechen.

---

# Praktischer Viewport-Test

Der praktische Test ist ein verpflichtender Bestandteil des Arbeitspakets.

Teste im echten laufenden Viewport:

```text
1. Cube/Testszene öffnen

2. Orbit
3. Zoom
4. Pan

4. Vertex auswählen
5. Edge auswählen
6. Face auswählen
7. Multi Selection
8. Toggle Selection
9. Klick ins Leere → Deselection

10. Shaded
11. Flat Shaded
12. Wireframe
13. Wireframe Overlay ON/OFF

14. Hotkey verwenden
15. Binding ändern
16. denselben Command über den neuen Hotkey ausführen

17. Mouse Binding ändern
18. dieselbe Aktion über die neue Mouse Binding ausführen
```

Prüfe dabei insbesondere:

- keine unerwarteten Selection-Verluste
- keine widersprüchlichen Mouse-Modi
- keine schwarzen/unsichtbaren Display-Zustände
- keine Regression beim Picking
- keine unerwarteten History-Einträge durch reine Viewport-Aktionen

---

# Architekturprüfung

Prüfe am Ende ausdrücklich:

```text
Input
 ↓
Command
 ↓
Tool / Action
 ↓
Operation
 ↓
History
```

und stelle sicher:

- Input ist nicht direkt in Modeling-Code verdrahtet.
- Commands sind unabhängig von konkreten Hotkeys.
- Tools enthalten interaktiven Zustand.
- Operations enthalten keine UI-/Input-Logik.
- Viewport-Aktionen erzeugen keine Model-History.
- Core bleibt unabhängig von Viewport/UI.
- keine unnötigen Abhängigkeiten zwischen Editor und Core entstehen.

---

# Dokumentation

Aktualisiere die relevante Dokumentation, wenn sich durch die Implementierung der tatsächliche Architekturstand ändert.

Insbesondere:

- Status des Arbeitspakets in `docs/architecture/ROADMAP.md`
- ggf. `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md`
- relevante Viewport-/Interaction-Dokumentation

Keine redundante Dokumentation erzeugen.

---

# Definition of Done

WP-01A ist erst abgeschlossen, wenn:

- [ ] Viewport-Navigation zuverlässig funktioniert
- [ ] Selection-Interaktion zuverlässig funktioniert
- [ ] Shaded funktioniert
- [ ] Flat Shaded funktioniert
- [ ] Wireframe funktioniert
- [ ] Wireframe Overlay funktioniert
- [ ] Keyboard Bindings über ein Mapping konfigurierbar sind
- [ ] Mouse Bindings über ein Mapping konfigurierbar sind
- [ ] Commands nicht an konkrete physische Inputs gekoppelt sind
- [ ] Tool-/Operation-Grenze eingehalten wird
- [ ] automatisierte Tests vorhanden und grün sind
- [ ] bestehende Regressionstests grün sind
- [ ] praktischer Viewport-Test erfolgreich durchgeführt wurde
- [ ] Architekturgrenzen geprüft wurden
- [ ] Dokumentation aktualisiert wurde
- [ ] Git Diff überprüft wurde
- [ ] ein sauberer Commit erstellt wurde

---

# Arbeitsweise

Arbeite in dieser Reihenfolge:

### Phase 1 — Analyse

Repository vollständig untersuchen.

### Phase 2 — Plan

Konkreten Implementierungsplan mit betroffenen Dateien, Abhängigkeiten und Tests erstellen.

**Noch nichts implementieren, bevor dieser Plan intern konsistent ist.**

### Phase 3 — Implementation

Das Arbeitspaket als zusammenhängenden technischen Block implementieren.

### Phase 4 — Tests

Automatische Tests ausführen und ergänzen.

### Phase 5 — Practical Verification

Den echten Viewport testen.

### Phase 6 — Review

Prüfen:

- Scope eingehalten?
- Core-Freeze eingehalten?
- Architekturvertrag eingehalten?
- keine unnötigen Abstraktionen?
- keine unnötigen Dateien/Änderungen?

### Phase 7 — Documentation

Relevante Dokumentation aktualisieren.

### Phase 8 — Commit

Nach erfolgreicher Verifikation einen klar benannten Commit erstellen.

Commit-Nachricht beispielsweise:

```text
Implement basic viewport and input foundation
```

Verändere keine themenfremden Bereiche.

---

## Wichtig

Wenn du während der Analyse feststellst, dass eine meiner Annahmen nicht zum aktuellen Repository-Code passt, **hat der tatsächliche Repository-Stand Vorrang**.

Dokumentiere die Abweichung und begründe eine notwendige Anpassung des Plans, statt die bestehende Architektur blind an diese Spezifikation anzupassen.

Das Ziel ist eine robuste, kleine Grundlage für die nächsten Modeling-/Topology-Arbeitspakete – kein vorgezogener kompletter Editor.