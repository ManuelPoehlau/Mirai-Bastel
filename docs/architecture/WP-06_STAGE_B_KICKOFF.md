# Kickoff: WP-06 — Stage B: Incremental Integration

**Zielpfad:** `docs/architecture/WP-06_STAGE_B_KICKOFF.md`
**An:** frischer Planungs-Chat (Claude), danach Claude Code für die Umsetzung einzelner Slices
**Modus (M5):** Planung / Work-Package-Definition — **noch keine Implementierung**
**Stand:** `main` @ `d4cf93f` (2026-09-26) + aktualisierte `docs/architecture/ROADMAP.md` (V1.1, WP-06 eingetragen)
**Typ (ROADMAP §10):** zunächst Type C (Grundsatzfrage zur Promotion), danach Type-A-Slices

---

## 0. Auftrag an den neuen Chat

1. Dieses Dokument, `docs/architecture/ROADMAP.md` (§2, §7 WP-06, §14) und `AGENTS.md` lesen.
2. Den Repo-Stand gegen §2 unten prüfen (Code und Tests sind Wahrheit, nicht dieses Dokument).
3. Mit Manu die offenen Fragen in §5 klären — **vor** dem ersten Slice.
4. Daraus den Handoff für **Slice 1** schreiben (Format wie `WP-SYM-LAB-01_SLICE*_CLAUDE_CODE_HANDOFF.md`).

Nicht in diesem Chat: neue Lab-Forschung, neue UX-Varianten, Core-Änderungen.

---

## 1. Warum WP-06

Stage A (`src/main.py`) zeigt die Szene durch den echten Production-Draw-Pfad — aber nur lesend. Parallel laufen Symmetry Lab, Shading Lab, Topology/Knife und Tweak Lab. Jedes Lab liefert getestete, teils entschiedene Ergebnisse, aber **es gibt keinen Ort, an dem sie in der eigentlichen App zusammenkommen.**

Hauptgrund (Manu, 2026-09-26): Die meisten Playground-Ergebnisse sind **UX-seitig noch nicht entschieden** — und genau diese Entscheidungen sind die schwierigsten, weil es extrem viele UX-Möglichkeiten gibt.

WP-06 soll das nicht lösen, indem alles auf einmal entschieden wird, sondern indem die App **grob und Stück für Stück** aufgebaut wird. Nicht alles, was gerade getestet wird, muss sofort hinein.

---

## 2. Faktenlage (Repo @ `d4cf93f`, im neuen Chat verifizieren)

### Was die Production-App heute kann

| Datei | Stand |
|---|---|
| `src/main.py` | pyglet-Fenster, Orbit (RMB), Pan (MMB), Zoom (Scroll), Esc/Q schließt. Kamera-Input geht **direkt** an `OrbitCamera`, nicht über `dispatch_command()` (bewusst, siehe Docstring). Kein Key-Dispatch, kein Picking, keine Selection, keine Mutation. Hintergrund fest `(0.05, 0.05, 0.08)`. |
| `src/mirai/application.py` | Window-frei. `init_scene()` nur `"cube"`. `dispatch_command()` kennt Move/Rotate/Scale (Tool-Aktivierung) und Undo/Redo — sonst nichts (keine Selection-, Display- oder Topologie-Commands). |
| `src/mirai/interaction/` | `Tool`-Lifecycle (activate/begin/update/commit/cancel/deactivate), `ToolManager`, `BindingSet` + `keymap.json`-Overrides, Routing. |
| `src/mirai/interaction/tools/move.py` | Production-MoveTool inkl. Achsen/Ebenen/Normal-Constraints und symmetrischem Move (AD-SYM-02). Rotate/Scale analog. |
| `src/mirai/viewport/picking.py` | `pick_nearest_vertex`, `pick_nearest_edge`, `pick_face` — existieren, sind in `main.py` **nicht** verdrahtet. |
| `src/mirai/pyglet_input.py` | pyglet → `Input`-Translator (WP-SYM-LAB-01 Slice 1), für diskrete Tasten/Buttons. |
| `src/viewport/` | `Viewport` nimmt `selection=` entgegen, `highlight_flags` pro Vertex existieren im `GLRenderStore`-Shader. Ob Selection-Highlight im Fenster sichtbar funktioniert, ist **nicht praktisch verifiziert**. |

### Was in Labs/Playground liegt und (teilweise) entschieden ist

| Fähigkeit | Wo | Artist-Verdikt |
|---|---|---|
| Kontextuelles C (Split / Edge Connect / Vertex Connect / Knife) | Playground, `AD-017` | **DECIDED** (AD-017, 2026-09-22); Preview-UX laut §9 bewusst offen |
| Connect Edges „Pro Face" | `playground/experiments/connect/decision.md` | **KEEP** (Baseline REJECT) |
| Symmetrie: Definition, Cycle, symmetrisches Move, Re-Symmetrize | `experiments/symmetry_lab/` | Slices 3, 4, 5 **KEEP** (lab-lokal); Core-Teile über AD-SYM-01/02 bereits in `src/` |
| Gespiegelter Knife | Symmetry Lab Slice 6/7 | offen |
| Selection (Replace/Toggle/Modifier/Box/Face) | Playground AP-03 | **kein** finales Verdikt |
| Transform-Interaktion (Hold / Press-Mode / Press-Drag) | Playground AP-04 | **kein** finales Verdikt |
| Tweak-Varianten | `playground/experiments/tweak/` | **kein** Verdikt (`tweak_decision.md` leer) |
| Loop Insert / Loop Slide / Extrude | Playground AP-05 | Implementierung vorhanden, Verdikte nicht dokumentiert |
| Worklight Key+Fill, Hintergrund-Presets | Shading Lab Slice 1 | offen (gerade gestartet) |

### Die zentrale Spannung

Die Roadmap-Regel für WP-06 lautet: *nur Kandidaten mit KEEP-Verdikt kommen in die App.*
Aber **Selection und Move — also das Minimum, ohne das gar nichts geht — haben kein KEEP-Verdikt.** Streng angewendet blockiert die Regel den allerersten Slice.

Das ist die erste Frage, die der neue Chat mit Manu klären muss (§5, Q1).

---

## 3. Vorschlag: Grundhaltung für WP-06

**„Provisorische Baseline" statt „finale UX".**

Die App bekommt für jede Grundfunktion eine *bewusst einfache, konventionelle* Baseline (z. B. Klick = Replace-Selection, Shift-Klick = Toggle, G/Move mit Maus-Drag, Enter/LMB commit, Esc/RMB cancel). Diese Baseline ist ausdrücklich **keine UX-Entscheidung**, sondern ein Platzhalter, markiert als `PROVISIONAL`.

- Sie wird im Playground **weiter erforscht**; ein späteres KEEP ersetzt die Baseline gezielt.
- Sie muss über `keymap.json`/`BindingSet` austauschbar sein, nicht hart verdrahtet.
- Echte Lab-Ergebnisse mit KEEP/DECIDED (z. B. kontextuelles C, Pro-Face-Connect, symmetrisches Move) werden danach **als echte Promotion** übernommen, mit kurzer Notiz oder AD.

Damit gibt es zwei klar getrennte Wege in die App:

```text
PROVISIONAL-Baseline   → nur für unverzichtbare Grundfunktionen, konventionell, austauschbar
PROMOTED (KEEP/DECIDED) → Lab-Ergebnis, dokumentierte Promotion, gilt als entschieden
```

Diese Grundhaltung ist ein **Vorschlag**, nicht entschieden — Manu entscheidet (Q1).

---

## 4. Skizze der Slice-Reihenfolge (grob, im neuen Chat verfeinern)

Jeder Slice: einzeln lauffähig, revertierbar, mit praktischem Fenstertest durch Manu und KEEP/ITERATE/REJECT am Ende.

| Slice | Inhalt | Art |
|---|---|---|
| **B1** | Vertex-Picking + Selection-Highlight im Production-Fenster (Klick = auswählen, sichtbar hervorgehoben). Klärt nebenbei, ob `highlight_flags` im echten Fenster funktioniert. | PROVISIONAL |
| **B2** | Move über den bestehenden `ToolManager` (Aktivieren, Live-Update, Commit, Cancel) — erste echte Mutation. | PROVISIONAL-Interaktion, Production-Tool |
| **B3** | Undo/Redo im Fenster (`dispatch_command` existiert bereits). | Production |
| **B4** | Rotate/Scale, Achsen-Constraints (bereits im Tool vorhanden, nur verdrahten). | PROVISIONAL-Interaktion |
| **B5** | OBJ-Laden über `Application.init_scene()` (Kopf-Mesh statt Würfel) — ab hier wird die App für echtes Testen brauchbar. | Production |
| **B6+** | Erste echte Promotions: z. B. Symmetrie-Modus, kontextuelles C, Worklight aus dem Shading Lab — jeweils sobald das Verdikt steht. | PROMOTED |

Bewusst **nicht** in den ersten Slices: Edge/Face-Selection, Box-Select, Tweak, Loop-Tools, UI-Panels/HUD.

---

## 5. Offene Fragen für Manu (vor Slice B1 klären)

- **Q1 — Provisorische Baseline:** Einverstanden, dass Grundfunktionen ohne KEEP als markierte `PROVISIONAL`-Baseline in die App dürfen? Oder soll zuerst im Playground für Selection/Move ein Minimal-KEEP gefällt werden?
- **Q2 — Welche Baseline-Konvention?** Näher an Blender (G/R/S modal), an Wings3D/Silo, oder an der aktuell meistgenutzten Playground-Variante? (Nur als Startwert — austauschbar.)
- **Q3 — Reihenfolge:** Passt B1 → B5 so, oder soll das Kopf-Mesh (B5) früher kommen, weil der Würfel zum Beurteilen kaum taugt?
- **Q4 — Verhältnis Playground ↔ App:** Soll der Playground nach einer Promotion die entsprechende Funktion abbauen (schlanker werden), oder bleibt alles parallel bestehen?
- **Q5 — Promotion-Dokumentation:** Pro Promotion ein eigenes kurzes AD, oder eine laufende Liste (z. B. §in ROADMAP oder `docs/architecture/APP_INTEGRATION_LOG.md`)? (Single-Source-of-Truth-Regel aus `AGENTS.md` beachten.)

---

## 6. Regeln (gelten, nicht neu verhandeln)

- `src/core/` bleibt frozen; Änderungen nur per dokumentierter Ausnahme (`CORE_V1_FREEZE.md` §7.1).
- **Kein Import aus `playground/`** in `src/` (AD-010 Addendum). Playground-Code ist technische Referenz, kein Baustein.
- Mutation läuft ausschließlich über den bestehenden `Tool` → `Operation` → `History`-Pfad (WP-02). Keine zweite Move-/Commit-Logik.
- `Application` bleibt window-frei und headless testbar; `main.py` bleibt dünn (nur Verdrahtung).
- Kein generisches Promotion-Framework, bevor mindestens zwei, drei echte Promotions dasselbe Muster zeigen.
- „Don't rebuild if it's already validated, documented, and working."
- Bei Widerspruch zwischen diesem Dokument und dem Code: anhalten und melden, nicht still weiterbauen.

---

## 7. Definition of Done für WP-06 (Gesamtpaket, aus ROADMAP §7)

Mindestens eine Lab-validierte Fähigkeit ist in `src/main.py` über den echten Production-Pfad nutzbar, praktisch verifiziert — und der Weg dorthin ist für den nächsten Kandidaten wiederholbar dokumentiert.
