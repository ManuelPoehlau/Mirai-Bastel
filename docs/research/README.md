# Research

`docs/research/` is the **research archive** of the project. Here we collect and analyze external sources, historical information, technical reconstructions, experiments, hypotheses and derived findings.

Research is detailed and may investigate individual systems or technical questions deeply.

## Interaction / Input Architecture Research

- [CONTEXT_SENSITIVE_INPUT_ARCHITECTURE_RESEARCH_V1.md](CONTEXT_SENSITIVE_INPUT_ARCHITECTURE_RESEARCH_V1.md) — Discovery zur kontextsensitiven Input-/Hotkey-Auflösung: Global, Application/Room, Component/Selection, Hover, Active Tool und Focus. Untersucht eine mögliche Context-Snapshot-/Binding-Resolver-Schicht ohne eine Architekturentscheidung vorwegzunehmen.

## Character Systems Research

- [CHARACTER_SYSTEMS_RESEARCH.md](CHARACTER_SYSTEMS_RESEARCH.md) — **authoritative artist-side research** on rigging, controls/handles, skinning, weighting, deformation, posing, morphs/blendshapes, correctives and related character workflows.

This document is the canonical home for the artist-side Character Systems research. Technical implementation experiments are kept separately under `experiments/rigging-skinning-morphing/` and should not be treated as a substitute for the research document.

## Edit-Mode Mirror / Symmetry Research

- [symmetry/EDIT_MODE_SYMMETRY_RESEARCH.md](symmetry/EDIT_MODE_SYMMETRY_RESEARCH.md) — Research zu Edit-Mode Mirror/Symmetry-Systemen über mehrere DCCs (3ds Max, Blender, Cinema 4D, Modo, Wings 3D, ZBrush, Houdini, Maya). Vergleicht technische Modelle (abgeleitete Hälfte, Positions-Korrespondenz, topologische Korrespondenz), Stressfälle und Naht-Schutz-Mechanismen. Status: Discovery, keine Architekturentscheidung, keine Empfehlung für Mirai-Bastel.
- [symmetry/SYMMETRY_PRODUCTION_OPERATIONS_DISCOVERY.md](symmetry/SYMMETRY_PRODUCTION_OPERATIONS_DISCOVERY.md) — Discovery (2026-10-06, English): wie Symmetry die bestehenden Production-Operationen (Split, Connect, Knife, Delete/Dissolve, Extrude, Transform) koordinieren könnte statt `SymmetricX`-Kopien; Ist-Architektur, alter gespiegelter Knife, Probe-Ergebnisse (`experiments/topology/symmetry_ops_probe.py`), gemeinsamer Nenner, Klassifikation A–D, Vorschlag für den nächsten Slice. Keine Entscheidung.
  → Entscheidungsvorschlag dazu: [AD-SYM-03](../architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) (PROPOSED).

## Modeling Workflow & Topologie

- [MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md](MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md) — Modeling-Workflow, Topologie-Grammatik, lokale Topologiekontrolle (Discovery, keine Entscheidungen)
- [topology/README.md](topology/README.md) — Connect-, Knife-, Face-Cut- und Face-Holes-Discoveries

## Subdivision Surfaces

- [subdivision/README.md](subdivision/README.md) — Einstieg; [subdivision/SUBDIVISION_SURFACES_RESEARCH.md](subdivision/SUBDIVISION_SURFACES_RESEARCH.md) — Research V1 zu SubD (Intent-Modelle, Catmull-Clark, Creases, OpenSubdiv vs. eigene Implementierung, Performance auf der Referenz-Hardware, Käfig/Picking, DCC-Vergleich). Discovery, keine Entscheidung.

## Viewport Shading

- [viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md](viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md) — Shading/Lighting für Formwahrnehmung (Research, keine Entscheidung)

## Abgrenzung zu `references/`

- `references/` = **kuratierter Wegweiser** zu externen Projekten, Original-Repositories, Dokumentationen und relevanten Bereichen. Kurz: *Was ist interessant und warum?*
- `docs/research/` = **unsere eigentliche Untersuchung**. Quellen auswerten, Fakten von Interpretation/Hypothese trennen, technische Zusammenhänge rekonstruieren und Konsequenzen für Mirai-Bastel festhalten.

Eine Reference-Datei sollte daher nicht die Research-Dokumentation duplizieren. Umgekehrt kann eine Research-Datei auf die passende Reference als Einstieg verweisen.

## Empfohlene Unterbereiche

- `mirai/` – Mirai, N-World, Izware, historische Versionen, Systemarchitektur und Workflow
- `bay-raitt/` – Bay Raitt, Demos, Interviews, Workflow
- `weta/` – Weta Digital, LOTR/Gollum und maßgeschneiderte Systeme
- `modelers/` – Wings 3D, Blender, Silo, Nendo und verwandte Modeler
- `subdivision/` – Catmull-Clark und verwandte Verfahren
- `topology/` – Winged Edge, Half Edge, Mesh-Datenstrukturen, Topologieoperationen
- `deformation/` – Skinning, Weight Maps, Morphs, Vertex Maps, nicht-destruktive Deformation und Attribute
- `viewport/` – Kamera-/Rendering-/OpenGL-Konventionen und Viewport-Untersuchungen
- `papers/` – Papers, Patente und technische Spezifikationen

## Recherche-Regeln

Jede externe Quelle sollte möglichst mit URL, Datum, Quelle/Autor und einer kurzen Einordnung dokumentiert werden.

Wo sinnvoll, unterscheiden wir ausdrücklich zwischen:

- **FACT** – durch Quellen belegt
- **OBSERVED** – direkt beobachtetes Verhalten / getesteter Code
- **INTERPRETATION** – Schlussfolgerung aus den verfügbaren Informationen
- **HYPOTHESIS** – noch nicht ausreichend belegte Annahme

## Ziel

Wir wollen nicht eine einzelne Software kopieren. Wir wollen die **Erfahrungen mehrerer Generationen von 3D-Systemen** untersuchen und daraus fundierte Entscheidungen für Mirai-Bastel ableiten.

```text
Quellen / Referenzen
        ↓
   Research & Analyse
        ↓
 Fakten / Trade-offs / offene Fragen
        ↓
 Mirai-Bastel-Entscheidung
```

Besonders bei Core-, Topologie-, Attribut-, Deformations- und Workflow-Fragen sollen etablierte Lösungen, Randfälle und bekannte Trade-offs berücksichtigt werden, bevor wir eine eigene Lösung entwerfen.
