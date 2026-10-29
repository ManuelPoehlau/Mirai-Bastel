# Mirai Atelier — Lagebild für den Artist

> **Status:** Artist-Übersicht (Index) (redaktionell abgeglichen am 2026-10-29; nicht Artist-validiert).
> **Zweck:** Manus Überblick in Artist-Sprache. Diese Seite ist ein **Index**, keine Wahrheit:
> Jede Zeile ist ein kurzer Satz plus Link. Was wirklich gilt, steht im verlinkten Dokument.
> Bei Widerspruch gewinnt immer das verlinkte Dokument, und diese Seite wird korrigiert.

---

## 1. Was Mirai heute kann

### In der Production-App (`python src/main.py [asset]`)

Alle Tasten sind `PROVISIONAL` (Wahl des Agenten), solange sie nicht in `config/keymap.json` stehen; die Testschritte
stehen im jeweiligen Dokument, nicht hier.

| Bereich | Was geht | Wo es steht |
|---|---|---|
| Navigation | Orbit, Pan, Zoom; Shift im Orbit rastet auf Standardansichten (ortho), `U` Ortho ↔ Persp, Pivot rastet auf die Symmetrieebene | [WP Ortho / Views](WP_ORTHO_VIEWS_PLAN.md) |
| Hotkeys | Eine Taste gilt erst mit Manus ausdrücklichem Wort als festgelegt (`config/keymap.json`) | [AD-013, Addendum 2026-10-28](architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-28-the-active-bindingset-is-the-single-input-truth-manus-keymap-in-the-repo) |
| Auswahl | Vertex/Edge/Face (`1`/`2`/`3`), Klick, Box, Malen, Lasso, Wachsen/Schrumpfen, Loop/Ring-Schritte | [ROADMAP, WP-06](architecture/ROADMAP.md) · [WP Playground-Werkzeuge](WP_PLAYGROUND_TOOLS_PROMOTION.md) · [WP Toolbox-Lücken, A](WP_TOOLBOX_GAPS_PLAN.md) |
| Transform | Tweak (`W`/`E`/`R` halten + Maus), Achsen-Sperre für einen Zug, World ↔ Normal (`K`), Gizmo, Working Pivot (`P`) | [ROADMAP, WP-06 B3/B4](architecture/ROADMAP.md) · [AD-012](architecture/AD-012-TRANSFORM-SPACE.md) · [WP Playground-Werkzeuge, Nachtrag 2026-10-28](WP_PLAYGROUND_TOOLS_PROMOTION.md#nachtrag-2026-10-28-achse-einmalig-tweak--halte-geste-gizmo-kleiner-manu) |
| Anzeige und Licht | Shaded/Flat/Wireframe (`D`), Licht-Presets, Licht- und Material-Werte pro Objekt, Glanz | [Intake Log](architecture/WP-06_INTAKE_LOG.md) · [AD-024](architecture/AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md) |
| Topologie | `C` (Split, Connect, Knife), Extrude, Inset/Bevel/Vertex Slide, Border/Cap, Collapse, Smooth/Relax, Loop-Werkzeuge, Delete/Dissolve | [AD-017](architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md) · [Knife](research/topology/KNIFE_FACE_DECISIONS.md) · [WP Inset / Bevel / Slide](WP_INSET_BEVEL_SLIDE.md) · [WP Toolbox-Lücken](WP_TOOLBOX_GAPS_PLAN.md) · [WP Delete/Dissolve](WP_DELETE_DISSOLVE_PLAN.md) |
| Soft Selection | Weiche Transform-Einflüsse mit sichtbarer Zone, Radius im Zug, Fluss entlang Loop/Ring | [AD-020](architecture/AD-020-SOFT-SELECTION-APP-PATH.md) |
| SubD | `V` Käfig/Fläche/Isolinien, `Strg+1/2/3` Stufe | [SubD in Production](../src/mirai/subdivision/README.md) |
| Morph-Ziele | Mehrere Ziele pro Mesh, daneben formen, Gewicht und Mischung, auch mit SubD und Topologie-Werkzeugen | [AD-025, Kurzfassung](architecture/AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md#kurzfassung-für-manu-deutsch) |
| Objekte | Mehrere Objekte, Referenzen, Add Mesh, Platzieren, Transform übernehmen, Spiegelpaare | [AD-021](architecture/AD-021-OBJECT-COMPONENT-MODEL.md#kurzfassung-für-manu-deutsch) |
| Szenen und OBJ | Szene speichern/laden, `Leertaste`-Menü; OBJ mit UVs und Textur importieren/exportieren | [`src/scene_files.py`](../src/scene_files.py) · [INPUT_WIRING_MAP §10](design/INPUT_WIRING_MAP.md) · [AD-026, Kurzfassung](architecture/AD-026-FACE-CORNER-UVS-AND-TEXTURE.md#kurzfassung-für-manu-deutsch) |
| Symmetrie | Symmetrische Werkzeuge und Soft Selection, Re-Symmetrize auf `Alt+M` | [AD-SYM-04](architecture/AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md#kurzfassung-für-manu-deutsch) |
| Undo/Redo | `Strg+Z` / `Strg+Y`, jede Operation ein Schritt | [AD-023 §9](architecture/AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) |

### Nur in Labs (nicht Produkt)

| Lab | Was man dort ausprobiert | Start | Doku |
|---|---|---|---|
| Morph Lab | Ein Morph-Ziel neben der Basis formen, Gewicht schieben, speichern | `python experiments/morph_lab/run.py` | [README](../experiments/morph_lab/README.md) |
| Mehlsack Lab | Box, Loop/Ring ziehen, Einflusskurve — **geparkt** (Code bleibt, kein offener Test) | `python experiments/mehlsack_lab/run.py` | [README](../experiments/mehlsack_lab/README.md) |

Aufgeräumt am 2026-10-24 (deine Entscheidung): [entfernte Labs](../experiments/README.md#entfernt-am-2026-10-24-konsolidierung-manus-entscheidung).

---

## 2. Wartet auf dich

Nur, was einen nächsten Schritt blockiert. Praxistests sind keine Warteschlange: du meldest dich, wenn etwas Probleme
macht (Manu, 2026-10-29, [Development System §7](../MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md)); ihre Schritte stehen in den
Bereichsdokumenten.

| # | Was | Wo |
|---|---|---|
| B2d | **Symmetrischer Knife**: Wahl zwischen den Spiegel-Varianten V-a / V-b / V-c (V-b bleibt Start) und F6 (Schnittstart im leeren Raum) | [AD-SYM-03 §10.8](architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) |
| D1c | **Viewport-Performance**: Stufe 2 und GPU-Picking sind in der App; offen ist Move/Rotate/Scale großer Auswahlen, vor allem mit Soft Selection (dein Verdikt 2026-10-21: vorerst so lassen) | [AD-022 §11](architecture/AD-022-GPU-PICKING.md) · [AD-023 §9](architecture/AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) |
| D1f | **Symmetrie + Soft Selection auf dem Körper**: über dem 8-ms-Wert ab 15 % Radius; ob die Viewport-Aufgabe vor J kommt | [AD-SYM-04, Addendum 2026-10-15](architecture/AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md#addendum-2026-10-15-reference-pc-run-d-4) |
| D2 | **Priorität**: was als Nächstes (Abschnitt 3) | — |

### Bewusst geparkt (kein Handlungsbedarf, nur damit es nicht verloren geht)

Flächen mit Loch (Face Holes; vorerst Bridges wie in Blender) · Hover-Kreis folgt auf dem Head leicht verzögert ·
Knife-Kleinigkeiten UX2-k, S4-d, S2-a ([Knife-Entscheidungen](research/topology/KNIFE_FACE_DECISIONS.md)) ·
Extrude-Erweiterungen ([ROADMAP, WP-06 B9](architecture/ROADMAP.md)) · Objekt-Pivot Q-13 ([AD-021](architecture/AD-021-OBJECT-COMPONENT-MODEL.md)) ·
Soft Selection symmetrisch im Core ([AD-020](architecture/AD-020-SOFT-SELECTION-APP-PATH.md)) ·
Head-Topologie-Walkthrough ([README](archive/experiments_2026-10/head_topology_walkthrough/README.md)) ·
Mehlsack Lab (oben).

---

## 3. Als Nächstes möglich (die Priorität entscheidest du)

| Kandidat | Was es dir bringt | Wo |
|---|---|---|
| Symmetrie-Spur J: symmetrische Soft Selection fertig, Re-Symmetrize prüfen | Symmetrie als durchgehender Werkzeugfluss | [AD-SYM-04](architecture/AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md#kurzfassung-für-manu-deutsch) · [AD-SYM-05](architecture/AD-SYM-05-WEIGHTED-TRANSFORMS-IN-CORE.md) |
| Phase 6 (Skinning, nach Morph) | Rig-Grundlage auf der Mesh-Architektur | [AD-025 §17.5](architecture/AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) |
| Hover-/Navigations-Optimierung auf dichten Meshes | flüssigeres Arbeiten auf dichten Meshes | D1c |
| Toolbox-Lücken: Subdivide (B2) | die fehlenden Alltagswerkzeuge | [WP Toolbox-Lücken](WP_TOOLBOX_GAPS_PLAN.md) |

---

## 4. Wörterbuch

| Begriff | Bedeutung | 3D-Vergleich |
|---|---|---|
| `src/` vs. `experiments/` | Produkt vs. Spielwiese | Hauptszene vs. Testszene |
| Core (`src/core/`) | Grundlage aller Mesh-Daten, Schnittstellen eingefroren | das Basemesh, auf dem alles aufbaut |
| PROVISIONAL | eingebaut, Wahl des Agenten, nicht vom Artist geprüft | Platzhalter-Material |
| KEEP ≠ Promotion | „fühlt sich richtig an“ heißt noch nicht „gehört fest ins Produkt“ | ein guter Testrender ist noch kein finaler Shot |
| PROMOTED | von dir freigegeben, dauerhaft Produktverhalten | Asset in die Hauptszene übernommen |
| AD (Architecture Decision) | festgeschriebene Bauregel, nur ergänzt, nie still geändert | die Rig-Konventionen eines Projekts |
| Tweak | `W`/`E`/`R` halten + Maus ziehen, loslassen = fertig | Tweak in Silo/Wings, nur auf der Taste |
| Discovery / Production | herausfinden, was richtig ist / umsetzen, was entschieden ist | Look-Dev / Produktion |

---

## 5. Pflegeregeln für diese Seite

- Nur Index: ein Satz plus Link, keine Details, keine eigene Wahrheit.
- Ändert ein Paket einen Artist-relevanten Stand (neues Verdikt, neue offene Artist-Frage, neue Fähigkeit in der App),
  wird diese Seite **im selben Commit** aktualisiert (siehe `AGENTS.md`).
- Ein Verdikt gilt erst, wenn es im verlinkten Dokument steht. Steht es nur hier oder nur im Chat, gilt es als offen.
- Erledigte Punkte aus Abschnitt 2 werden gestrichen, nicht abgehakt. Die Geschichte steht in den verlinkten Dokumenten.
- Abschnitt 2 führt nur, was einen nächsten Schritt blockiert; Praxistests stehen dort nicht (Development System §7).
- Ziel: höchstens zwei Bildschirmseiten. Wird es länger, wird gekürzt, nicht erweitert.
