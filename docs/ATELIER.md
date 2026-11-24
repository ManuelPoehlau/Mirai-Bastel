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
| Surface Slide | `J` halten + Maus: die gewählten (sonst die gezeigten) Punkte gleiten auf der Fläche, mit Soft Selection (Radius im Zug), Symmetrie, Maske und versteckten Flächen als Wand; bei eingeblendetem Morph auf der Ruheform; ein Undo-Schritt, `Esc` stellt exakt wieder her. Taste: deine Entscheidung 2026-11-15; Praxistest (E4, E7, E10) offen | [Surface Slide Audit, §5.1 und §13.5](research/SURFACE_SLIDE_PRODUCTION_READINESS_AUDIT_2026-11-14.md#135-implementation-note--phase-3-done-2026-11-15) |
| Anzeige und Licht | Shaded/Flat/Wireframe (`D`), Licht-Presets, Licht- und Material-Werte pro Objekt, Glanz | [Intake Log](architecture/WP-06_INTAKE_LOG.md) · [AD-024](architecture/AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md) |
| Topologie | `C` (Split, Connect, Knife), Extrude, Inset/Bevel/Vertex Slide, Border/Cap, Collapse, Smooth/Relax, Inflate/Pinch, Loop-Werkzeuge, Delete/Dissolve | [AD-017](architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md) · [Knife](research/topology/KNIFE_FACE_DECISIONS.md) · [WP Inset / Bevel / Slide](WP_INSET_BEVEL_SLIDE.md) · [WP Toolbox-Lücken](WP_TOOLBOX_GAPS_PLAN.md) · [WP Delete/Dissolve](WP_DELETE_DISSOLVE_PLAN.md) |
| Soft Selection | Weiche Transform-Einflüsse mit sichtbarer Zone, Radius im Zug, Fluss entlang Loop/Ring | [AD-020](architecture/AD-020-SOFT-SELECTION-APP-PATH.md) |
| SubD | `V` Käfig/Fläche/Isolinien, `Strg+1/2/3` Stufe | [SubD in Production](../src/mirai/subdivision/README.md) |
| Morph-Ziele | Mehrere Ziele pro Mesh, daneben formen, Gewicht und Mischung, auch mit SubD und Topologie-Werkzeugen; seit 2026-11-03 treffen Hover, Auswahl, Knife und Ziehen bei eingeblendetem Ziel die gemorphte Form (bearbeitet wird die Basis) | [AD-025, Kurzfassung](architecture/AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md#kurzfassung-für-manu-deutsch) · [Praxistest Picking auf dem Morph](design/MODELING_ON_DEFORMED_SURFACES.md#praxistest-für-manu-picking-auf-dem-morph-ca-15-minuten) |
| Knochen und Gewichte | Knochen anlegen (`Strg+J`), Gewichte aus einer Gruppe (`7` halten) und weich korrigieren (`8` halten), im Pose-Modus (`5`) den Kiefer drehen, Ruhe ↔ Pose (`6`); ein Morph fährt mit; seit 2026-11-17 treffen Hover, Auswahl, Box, Lasso und Paint in der Pose die gezeigte Fläche (Mundwinkel, Mundinnenraum; Praxistest offen), Verschieben und Topologie bleiben dort gesperrt, weitermodelliert wird in Ruhe | [AD-028, Praxistest](architecture/AD-028-SKELETON-AND-SKINNING.md#praxistest-für-manu-nach-dem-bau-deutsch-ca-20-minuten) |
| Bone-Werkzeug 01 | Knochen per Klick-Kette setzen (Panel „Bone“, keine Taste): Kopf, dann je Klick eine Spitze, Abzweigen von jedem Knochen, Einrasten am Objekt-Pivot (Augapfelmitte) und an Knochenenden, Knochen nach dem Binden ändern (Ruhe-Pose), Name / Parent / Zahlen / Gewichte im Panel; `Strg+J` bleibt. Seit 2026-11-18: Spitze auf X / Y / Z oder auf der Objekt-Achse (Augen: Blickachse) und „Ausrichten“; die Szene `Gollum_Head_rigging_test` hat die Augen-Knochen. Praxistest offen | [AD-028, Addendum 2026-11-17](architecture/AD-028-SKELETON-AND-SKINNING.md#addendum-2026-11-17-bone-tool-01-chain-click-pivot-snap-rest-edit-bonepanel) · [Praxistest](architecture/AD-028-SKELETON-AND-SKINNING.md#praxistest-bone-werkzeug-01-für-manu-deutsch-ca-20-minuten) |
| Augen, Zähne, Lider am Rig | Seit 2026-11-18: im Bone-Panel „Auswahl folgt <Knochen>“ / „Lösen“ (Modus 4, keine Taste) — Zähne folgen Hals / Kiefer, ein Auge nur seinem Augenknochen; in einer Pose zeigt jedes Objekt die Pose, der Blick dreht dann die Augenknochen (gewichtete Lider gehen mit), in Ruhe nur die Augäpfel. Praxistest offen; E5 (welche Zähne oben / unten) offen | [AD-036, Praxistest](architecture/AD-036-EYES-TEETH-AND-LIDS-ON-THE-RIG.md#praxistest-scheiben-12-für-manu-deutsch-ca-15-minuten) |
| GUI / Zustände | Statusleiste mit Modus inkl. Pose, laufender Geste, Warnmarke „Pose · 6 = rest“, Knochenname im Viewport und XYZ-Achsenkreuz (A1, Praxistest offen; `F3`–`F6` schalten Varianten); Gesten-Feedback ist ein eigenes Paket. UX-Vorschläge sind noch nicht Artist-entschieden | [HUD, Stufe 1b](design/GUI_STAGE1_HUD.md#7-stufe-1b--phase-a1-statusklarheit-und-raumorientierung) · [GUI-Bestandsaufnahme](design/GUI_Bestandsaufnahme.md) |
| Gewichtsansicht | `9` zeigt den Anteil des aktuellen Knochens als Flächenfärbung, ohne zu schreiben, auch in der Pose; die Soft-Vorschau ruht solange (A3, Praxistest offen) | [HUD, Stufe 1c](design/GUI_STAGE1_HUD.md#8-stufe-1c--phase-a3-dauerhafte-gewichtsansicht) |
| Objekte | Mehrere Objekte, Referenzen, Add Mesh, Platzieren, Transform übernehmen, Spiegelpaare | [AD-021](architecture/AD-021-OBJECT-COMPONENT-MODEL.md#kurzfassung-für-manu-deutsch) |
| Attach | Ausgewählte Objekte werden Teil des Edit-Objekts (Menü „Mesh“ und Outliner-Rechtsklick, ohne Taste), ein Undo-Schritt; Praxistest offen | [AD-031, Praxistest P2](architecture/AD-031-ATTACH-DETACH-WELD-BRIDGE.md#16-praxistest-p2-attach-deutsch-ca-15-minuten) |
| Detach und Select Linked | Ausgewählte Flächen werden ein eigenes Objekt an derselben Stelle (Menü „Mesh“, mit Symmetrie samt Spiegelseite), ein Undo-Schritt; Select Linked wählt den Teil unter dem Cursor (SPACE-Menü), beide ohne Taste; Praxistest 2026-11-10: O-8 KEEP, SPACE reicht vorerst | [AD-031, Praxistest P3](architecture/AD-031-ATTACH-DETACH-WELD-BRIDGE.md#18-praxistest-p3-detach-und-select-linked-deutsch-ca-15-minuten) |
| Weld | Ausgewählte, unverbundene Punkte im Abstand verschmelzen auf ihren Schwerpunkt (Menü „Mesh > Weld…“: Abstand als Zahl, Vorschau „n Gruppen, m Punkte“), ganze Naht oder Punkt für Punkt (W5 geändert 2026-11-10), ein Undo-Schritt, ohne Taste; mit Symmetrie seit P6 gespiegelt (auch doppelte Punkte, Praxistest P6 offen); Startwert vorläufig | [AD-031, Praxistest P4](architecture/AD-031-ATTACH-DETACH-WELD-BRIDGE.md#20-praxistest-p4-weld-deutsch-ca-15-minuten), [P6](architecture/AD-031-ATTACH-DETACH-WELD-BRIDGE.md#24-praxistest-p6-weld-und-bridge-mit-symmetrie-deutsch-ca-15-minuten) |
| Bridge | Zwei geschlossene Ränder gleicher Punktzahl mit Quads verbinden (Menü „Mesh > Bridge“, je ein Punkt pro Rand), keine neuen Punkte, keine UVs/Gruppe, ein Undo-Schritt, ohne Taste; mit Symmetrie seit P6 (Spiegelseite mit, oder eine spiegelbildliche Brücke über die Mitte); ungleiche Punktzahl (O-11 CHANGE) folgt; Praxistests offen | [AD-031, Praxistest P5](architecture/AD-031-ATTACH-DETACH-WELD-BRIDGE.md#22-praxistest-p5-bridge-deutsch-ca-10-minuten), [P6](architecture/AD-031-ATTACH-DETACH-WELD-BRIDGE.md#24-praxistest-p6-weld-und-bridge-mit-symmetrie-deutsch-ca-15-minuten) |
| Paint Room | SPACE → „Paint Room öffnen“ (nur mit UVs, kein Auge, keine Taste): LMB ziehen malt auf der gezeigten Fläche (mit SubD auf der SubD-Fläche), Shift+Rad Radius, Alt+Rad Deckkraft, Esc nimmt den Strich zurück; Panel mit Malen / Radieren / Pipette, Farbe, Fluss, Härte, Kurve, Spiegeln; ein Strich = ein Undo-Schritt, gespeichert als Ebene + flaches PNG. In einer Pose / mit Morph abgelehnt (P-8 offen). **Seit 2026-11-19 (Phase 3):** mehrere Ebenen im Panel (sichtbar, aktiv, Deckkraft, Mischmodus Normal / Multiplizieren, Neu / Hoch / Runter / Zusammenführen / Leeren / Löschen, je ein Undo-Schritt); eine ZBrush-Rückgabe mit neuen UVs nimmt die Bemalung mit (UV-Transfer). Praxistest offen | [AD-037 §10–§11, Praxistests](architecture/AD-037-TEXTURE-PAINT.md#praxistest-ebenen-und-uv-transfer-phase-3-für-manu-deutsch-ca-15-minuten) |
| Szenen und OBJ | Szene speichern/laden, `Leertaste`-Menü; OBJ mit UVs und Textur importieren/exportieren | [`src/scene_files.py`](../src/scene_files.py) · [INPUT_WIRING_MAP §10](design/INPUT_WIRING_MAP.md) · [AD-026, Kurzfassung](architecture/AD-026-FACE-CORNER-UVS-AND-TEXTURE.md#kurzfassung-für-manu-deutsch) |
| Symmetrie | Symmetrische Werkzeuge und Soft Selection, Re-Symmetrize auf `Alt+M`, Seam auf Ebene legen auf `Shift+Alt+S` | [AD-SYM-04](architecture/AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md#kurzfassung-für-manu-deutsch) |
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
| D3 | **Messlauf Knochen auf deinem PC**: zeigt, ob das Drehen des Kiefers auf Kopf und Körper flüssig ist und ob ein GPU-Zeichenweg das nächste Thema wird | [AD-028, Praxistest Schritt 9](architecture/AD-028-SKELETON-AND-SKINNING.md#praxistest-für-manu-nach-dem-bau-deutsch-ca-20-minuten) |
| B16 | **Inflate / Pinch** (2026-11-15): Tasten Shift+I / Shift+P / Alt+P bestätigen oder ändern; trifft „Loop“ (quer über die Loops auf die Linie) und „Ring“ (entlang der Loops) deine Absicht an Lippen/Lidern? | [AD-020, Soft Inflate / Pinch](architecture/AD-020-SOFT-SELECTION-APP-PATH.md#soft-inflate--pinch-2026-11-15-provisional) |
| B17 | **Smooth / Relax-Strich** (2026-11-23, gebaut nach deinem „stroke/brush-artiges Verhalten war geplant“): S halten, mit der Maus über die Stelle, LMB drücken und ziehen (Alt+S + LMB = Relax, kein Orbit dabei); Klick = ein Tupfer. Prüfen: Stärke pro Tupfer, Abstand, der Ring am Cursor, Radius = Soft-Radius (Shift+Rad zwischen den Strichen); passt die Taste („Taste passt“ → Eintrag in der Keymap)? Achtung: vor dem LMB nicht ziehen - das ist weiter der Regler (er wird beim LMB verworfen). Messlauf: `python experiments/drag_cost/probe_soft_field.py` | [AD-020, Smooth / Relax stroke](architecture/AD-020-SOFT-SELECTION-APP-PATH.md#smooth--relax-stroke-2026-11-23-provisional) |
| L3 | **LookDev P3, S1 Schattenkarte gebaut** (2026-11-22): Messlauf auf deinem PC (drei Befehle, misst auch das Ziehen mit Schatten) und Praxistest (Schatten an/aus, Weichheit, vier Vorlagen, Pose/Morph ziehen, Zähne); offen bis vor S6: LD-D8 (der Mal-Kanal ist entschieden, S7 gebaut) | [AD-039 §16.4–§16.5](architecture/AD-039-LOOKDEV-P3.md#16-implementation-note--s1-built-2026-11-22) |
| L4 | **LookDev P3, S2 Augen im Schatten des Key gebaut** (2026-11-22): Lider, Brauen, Nase schatten den Augapfel; Schalter „Augen-Schatten“; Messzeile `lookdev +shadow +eyes` im selben Lauf wie S1, Praxistest (Lid-Schatten Portrait/Dramatic, Blick, Key drehen, Weichheit, an/aus, ob `lid_shadow` im Panel „Auge“ jetzt zu stark wirkt) | [AD-039 §17.4–§17.5](architecture/AD-039-LOOKDEV-P3.md#17-implementation-note--s2-built-2026-11-22) |
| L5 | **LookDev P3, S3 Doppel-Glanz gebaut** (2026-11-23): Glanz der Haut aus zwei Anteilen (scharfe Spitze + weicher Saum), Schalter „Doppel-Glanz“; Messzeile `lookdev +dual` im selben Lauf wie S1/S2. Offen für dich: die Glanzlichter werden heller (bis +24…36/255; die AD-Annahme „gleiche Energie“ hielt nur bis Rauheit 0,4) – so lassen, Spitze schwächer oder auf einen Lobe normieren? | [AD-039 §18.2, §18.4–§18.5](architecture/AD-039-LOOKDEV-P3.md#18-implementation-note--s3-built-2026-11-23) |
| L6 | **LookDev P3, S4 Durchleuchtung gebaut** (2026-11-23): der Key scheint durch Ohren und Nasenflügel (aus der Tiefe der Schattenkarte); Schalter „Durchleuchtung“; der rosa Rand-Schimmer aus M1 fällt dafür weg. Offen für dich: die Einheit – `Gollum_Head_05` ist 1,2 Einheiten breit, nicht im 1-cm-Maßstab (AD-033); der Wert 0,05 gilt für die Szene, wie sie ist. Fix 2026-11-24: kein Durchscheinen mehr durch Öffnungen (dein roter Fleck auf der Wange; Loch hinter dem Auge) und keine leuchtende Kontur an ihrem Rand | [AD-039 §19.2, §19.5, §19.6, §19.7](architecture/AD-039-LOOKDEV-P3.md#19-implementation-note--s4-built-2026-11-23) |
| L7 | **LookDev P3, S7 Maps gebaut** (2026-11-24, nach deinem „Map-Pfade“ und „S7 jetzt vorziehen“): Rauheit-, Normal- und Durchscheinen-Map als Bild am Material (Panel Material → „Mehr“ → „Laden …“), Normal-Stärke und „Grün unten (DirectX)“; beim Speichern nach `<Szene>_textures/` kopiert; Szenenformat v16 (nur mit Maps). Praxistest mit einer ZBrush-Normal-Map von Gollum; Messzeile `lookdev +maps` im selben Lauf wie S1–S4. Offen bis vor S6: LD-D8 | [AD-039 §20](architecture/AD-039-LOOKDEV-P3.md#20-implementation-note--s7-built-2026-11-24) |
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
| Hover-/Navigations-Optimierung auf dichten Meshes | flüssigeres Arbeiten auf dichten Meshes | D1c |
| Toolbox-Lücken: Subdivide (B2) | die fehlenden Alltagswerkzeuge | [WP Toolbox-Lücken](WP_TOOLBOX_GAPS_PLAN.md) |
| GUI-Zustandssichtbarkeit | Arbeitsmodus, Morph-Target, Rig-Zustand und Gewichtsanzeige klarer erkennen; Priorität und Vorschläge bleiben offen | [GUI-Bestandsaufnahme](design/GUI_Bestandsaufnahme.md) |

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
