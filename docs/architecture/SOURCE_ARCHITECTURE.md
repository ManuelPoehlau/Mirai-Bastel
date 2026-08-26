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
└── core/
```

`src/core` ist der bisher etablierte Produktionspfad für den Core. Die
endgültige Gesamtstruktur von `src/` ist bewusst noch nicht vollständig
festgelegt.

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

### Viewport

Der Viewport ist für die visuelle Darstellung und räumliche Interaktion mit
der Scene verantwortlich.

Aus dem V1-Praxistest sind derzeit folgende Verantwortlichkeiten bekannt:

- Kamera
- Projektion
- Rendering
- Picking
- Viewport-bezogene Interaktion

Der Viewport benutzt den Core, um dessen aktuellen Zustand darzustellen und
Operationen anzustoßen. Der Core soll den Viewport nicht kennen.

### Tools

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

### Application

Die Application-Schicht verbindet und orchestriert die großen Systeme.

Mögliche spätere Aufgaben:

- aktives Dokument / Scene verwalten
- aktiven Viewport verwalten
- aktives Tool verwalten
- globale Commands und Shortcuts routen
- Anwendungseinstellungen verwalten

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

- genaue Unterteilung von `viewport/`
- genaue Unterteilung von `tools/`
- Position und Form eines späteren Renderer-Moduls
- konkrete Event-/Input-Architektur
- Command-System und dessen genaue Grenzen
- UI-Framework bzw. UI-Architektur
- Dokument-/Projektverwaltung auf Application-Ebene
- genaue Aufteilung zukünftiger Systeme wie Animation, Rigging, Morphs und
  Deformation

Insbesondere werden diese Bereiche **nicht vorsorglich als leere Top-Level-
Ordner angelegt**, nur weil sie irgendwann benötigt werden könnten.

---

## 6. Vorläufige Zielstruktur

Wenn die Anforderungen ausreichend konkret sind, kann sich daraus ungefähr
folgende Struktur entwickeln:

```text
src/
└── mirai/
    ├── core/
    ├── viewport/
    ├── tools/
    ├── application/
    └── ui/
```

Das ist eine **Zielvorstellung, keine aktuelle Verpflichtung**.

Weitere fachliche Unterteilungen entstehen erst dann, wenn sie durch die
tatsächliche Komplexität gerechtfertigt sind.

---

## 7. Architekturprinzipien

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

**Status: Arbeitsgrundlage für die Produktionsarchitektur.**

Core V1 und Viewport V1 sind abgeschlossen und dienen als Referenz. Die
nächste Entwicklungsphase kann auf dieser Grundlage die tatsächliche
`src/`-Struktur schrittweise aufbauen.
