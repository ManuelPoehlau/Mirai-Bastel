# Mirai-Bastel – Source Architecture

## Purpose

Dieses Dokument beschreibt die derzeit beabsichtigte Produktionsarchitektur
unter `src/`.

Es ist ein **Architekturvertrag**, keine vollständige Implementierungsplanung.
Die Struktur soll Verantwortlichkeiten und Abhängigkeiten festlegen, ohne
bereits Module zu erfinden, deren Bedarf noch nicht durch Experimente oder
echte Anforderungen belegt ist.

Grundprinzip:

> Erst Verantwortungsgrenzen festlegen, dann Produktionscode strukturieren.

Die abgeschlossenen V1-Experimente unter `experiments/` dienen als empirische
Referenz. Sie werden nicht automatisch in `src/` übernommen.

---

## 1. Aktueller Produktionsrahmen

Der Produktionscode liegt unter:

```text
src/
├── core/
├── mirai/
└── viewport/
```

`src/core` ist der etablierte Produktionspfad für die fachliche Domain.
`src/mirai` enthält die window-freie Application-, Interaction- und
Kamera-/Picking-Schicht. `src/viewport` enthält die unabhängige V0.2-
Renderdaten- und Viewport-Schicht.

Diese drei Verzeichnisse sind die heute implementierten
Produktionsverantwortlichkeiten. Sie legen weder ein Production-Fenster,
einen Draw-Call noch spätere Modellierungs-, UI- oder Dokumentgrenzen fest.
Der Viewport-V1-Praxistest bleibt unter `experiments/`.

---

## 2. Verantwortungsbereiche

Die langfristige Anwendung wird zunächst konzeptionell in folgende Bereiche
geteilt:

```text
Application
├── UI
├── Tools
├── Viewport
└── Core
```

Diese Begriffe beschreiben zunächst **Verantwortlichkeiten**, nicht zwingend
die spätere exakte Ordnerstruktur.

### Core

Der Core beschreibt die 3D-Daten und die fachlichen Operationen darauf.

Dazu gehören derzeit unter anderem:

- Scene
- Mesh
- Vertex / Edge / Face
- Selection
- Operations
- History
- Undo / Redo
- Serialization

Später können hier weitere fachliche Systeme entstehen, z. B. Deformation,
Morphs, Rigging oder Animation, sobald deren tatsächliche Anforderungen
konkret genug sind.

Der Core darf keine Abhängigkeit von UI, Fenster-Systemen, Eingabegeräten,
OpenGL oder einer konkreten Viewport-/Render-Bibliothek benötigen.

### Viewport (`src/viewport` und `src/mirai/viewport`)

Der Viewport ist für die visuelle Darstellung und räumliche Interaktion mit
der Scene verantwortlich.

Die Production-Aufteilung ist bewusst zweigeteilt: `src/viewport` besitzt
Renderdaten, Dirty-State, Overlay und Resource-Stores; `src/mirai/viewport`
besitzt die wiederverwendbare Orbit-Kamera, Picking und Display-State. Die
Bindung erfolgt an der Application-Grenze, ohne dass `src/viewport` von
`src/mirai` importiert.

Derzeit implementierte Verantwortlichkeiten sind:

- Kamera
- Projektion
- Rendering
- Picking
- Viewport-bezogene Interaktion

Der Viewport benutzt den Core, um dessen aktuellen Zustand darzustellen und
Operationen anzustoßen. Der Core soll den Viewport nicht kennen.

### Tools (`src/mirai/interaction`)

Tools übersetzen Benutzeraktionen in fachliche Operationen.

Beispiel:

```text
Mausbewegung
    ↓
Move Tool
    ↓
World-Space-Delta
    ↓
MoveOperation
    ↓
Core
```

Ein Tool soll nicht selbst zur dauerhaften Quelle der Modelldaten werden.
Die fachlichen Änderungen bleiben im Core.

### UI

UI umfasst die Benutzeroberfläche außerhalb der eigentlichen 3D-Darstellung,
z. B. Panels, Menüs, Toolbars und Dialoge.

UI ist nicht gleich Viewport und nicht gleich Tool.

### Application (`src/mirai/application.py`) und Controller (`src/mirai/controllers/`)

Die Application-Schicht verbindet und orchestriert die großen Systeme. Seit AD-027
([Interaction Layer](AD-027-INTERACTION-LAYER-SESSION-SLOT.md), 2026-10-30) besteht sie aus drei Teilen:

- **Ein Platz für die laufende Interaktion** (`interaction/session.py`, `InteractionSlot`): höchstens eine
  *Session* (eine gehaltene Geste W/E/R/T/G/S/I/Ctrl+B, die Knife, die Re-Symmetrize-Vorschau, die Objekt-Geste),
  daneben die *Press-Session* eines LMB-Drucks (Box / Paint / Lasso, Gizmo-Griff, verschluckte Geste) und die
  gehaltenen *Hold Keys* (Pivot, Lasso, Licht, Morph-Gewicht) in fester Rangfolge. Die Vorrangregel steht nur in
  `InteractionSlot.route` (grab → hold claims → session → hold background → idle). Modale Zustände liegen nur dort.
- **Eine Frage „darf das jetzt laufen?“** (`Application.can_run(command, RunContext)`), dieselbe für Tasten,
  Klicks, Drags, das Rad, `dispatch_command` (der öffentliche, gegatete Einstieg für GUI und Skripte) und das HUD;
  sieben Stufen (exklusive Session, Host-Gate, Layer/Morph-Ansicht, Objektmodus, verborgene Geometrie, laufende
  Session, Modus-Policies).
- **Controller** (`src/mirai/controllers/`): Knife, Morph, Objekte, Symmetrie, Gesten, Pointer-Tools. Ein
  Controller bekommt `AppServices` (`controllers/services.py`, feste Mitgliederliste), nie die `Application`, und
  importiert nichts aus `mirai.application`. Die einzige Abhängigkeit zwischen Controllern: die Objekt-Geste ist
  eine Gesten-Art (`objects` → `gestures`, einseitig).

`Application` selbst behält Konstruktion und Verdrahtung, den Szenen-Lebenszyklus, die öffentlichen Einstiege
(Eingabe → Slot → `can_run` → Kommandotabelle), `can_run`, History und Auswahl-Spiegel, Hover und Picking,
Navigation und Ansichten, Display und Worklight, Soft-Einstellungen und -Vorschau, Mask / Hide / Regionen und die
Topologie-Commands (`C`, Delete / Dissolve, Collapse, Loops, Auswahlschritte). Die Kommandotabelle
(`Application._command_table`) ist statisch: ein Handler pro Command, zur Laufzeit registriert sich nichts.

Die Application-Schicht soll nicht zum Ersatz für Core, Viewport oder Tools
werden.

---

## 3. Abhängigkeitsrichtung

Die grundlegende Richtung lautet:

```text
UI ──────────┐
             │
Tools ───────┼──► Core
             │
Viewport ────┘
```

Die Application-Schicht orchestriert diese Systeme.

Wichtig:

```text
Core ──X──► Viewport
Core ──X──► UI
Core ──X──► konkrete Eingabe-/Fenster-/Render-Bibliotheken
```

Der Core bleibt damit unabhängig von der Darstellung.

---

## 4. Was aus den V1-Experimenten übernommen wird

### Core V1

Der abgeschlossene Core-V1-Milestone ist die aktuelle fachliche Referenz für
den Produktions-Core.

Seine validierten Konzepte dürfen in `src/core` weiterentwickelt werden.

### Viewport V1

Der abgeschlossene Viewport-V1-Test ist eine Referenz für die **Schnittstelle
zwischen Core und visueller Anwendung**.

Er beweist insbesondere, dass folgende Pipeline praktisch funktioniert:

```text
Scene
  ↓
Mesh
  ↓
Selection
  ↓
Operation
  ↓
Commit
  ↓
History
  ↓
Undo / Redo
  ↓
Viewport
```

Der V1-`app.py` ist jedoch ein Praxistest-Harness und kein unverändert zu
übernehmender Produktions-Viewport.

Insbesondere werden folgende Dinge nicht automatisch übernommen:

- monolithische Event-/Rendering-Logik aus `app.py`
- Demo-Szene
- experimenteller Einstiegspunkt
- V1-spezifische Testverkabelung

Einzelne bewährte Konzepte wie Kamera, Picking und Rendering dürfen später in
eine passendere Produktionsstruktur überführt werden.

---

## 5. Bewusst noch nicht festgelegt

Folgende Fragen bleiben offen, bis weitere Anforderungen oder Experimente
sie ausreichend klären:

- Production-Fenster, Entry-Point und konkrete Draw-Call-Integration
- konkrete Event-/Input-Architektur des Fensters (für `Application` beantwortet AD-027: Slot, `can_run`,
  Kommandotabelle; offen bleibt, welche Klicks ein künftiges Panel vor dem Slot nimmt, GUI_STAGE1_HUD §5 Q4)
- UI-Framework bzw. UI-Architektur
- Dokument-/Projektverwaltung auf Application-Ebene
- genaue Aufteilung zukünftiger Systeme wie Animation, Rigging, Morphs und
  Deformation

Insbesondere werden diese Bereiche **nicht vorsorglich als leere Top-Level-
Ordner angelegt**, nur weil sie irgendwann benötigt werden könnten.

---

---

## 6. Architekturprinzipien

### Kleine, echte Grenzen statt künstlicher Abstraktionen

Neue Abstraktionen werden eingeführt, wenn eine konkrete Verantwortung oder
mehrere reale Implementierungen sie rechtfertigen – nicht nur als Vorsorge.

### Experimente dürfen pragmatisch sein

Ein Experiment darf bewusst einfacher oder stärker gekoppelt sein, wenn das
den Praxistest beschleunigt.

Ein erfolgreicher Experiment-Code wird deshalb nicht automatisch zum
Produktionsdesign erklärt.

### Core bleibt unabhängig

Die fachliche Modell- und Operationslogik soll unabhängig von der konkreten
Darstellung und Bedienoberfläche bleiben.

### Architekturentscheidungen dokumentieren

Wenn eine offene Frage entschieden wird, soll die Entscheidung in der
Architekturdokumentation festgehalten werden, damit sie nicht ausschließlich
im Chat-Kontext existiert.

### Nicht vorschnell skalieren

Bekannte zukünftige Anforderungen werden bei der Architektur berücksichtigt,
aber zukünftige Systeme werden nicht vollständig vorimplementiert.

---

## Status

**Status: aktuelle Produktionsarchitektur, Stand nach Gate 3/5/6/7; Application-Schicht nach AD-027 (2026-10-30).**

Core V1 und Viewport V1 bleiben Referenzen. Die implementierten Grenzen unter
`src/` sind aktuell, während künftige Produktbereiche weiterhin erst aus
validierten Anforderungen abgeleitet werden.
