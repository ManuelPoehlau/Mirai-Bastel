# Work Package: Inset, Bevel/Chamfer, Vertex Slide (2026-10-29)

> **Status:** **gebaut 2026-10-29** (`PROVISIONAL`, Grundfunktion; Praxistest B25 unten offen).
> **Auftrag (M3, Manu im Chat 2026-10-29):** „In meiner Werkzeugkiste fehlen noch ein paar wichtige Werkzeuge: Inset
> (Polygons), Chamfer/Bevel (Edges, Vertices), Slide (Vertices). Erstmal die Grundfunktion. Ausbauen kann man die dann
> immer noch.“ Keine Prioritäten, alle drei gebraucht.
> **Modus (M5):** Production, kein Lab (Blender-/Maya-bekannte Werkzeuge, AGENTS.md §7a). Grundlage:
> [future_ideas/MODELING.md](future_ideas/MODELING.md), Muster: Extrude (WP-06 B9, AD-SYM-03 Slice 7) und Loop Slide.

## 0. Existenzprüfung (2026-10-29)

Kein Code für Inset, Bevel oder Vertex Slide in `src/`, `experiments/` oder der Git-Historie. Der entfernte
Head-Topology-Walkthrough hat „Inset“ mit Extrude 0 + Scale nachgestellt (keine Inset-Funktion). Die Haken in der
[Einkaufsliste](project%20planning/Mirai-Bastel%20—%20Artist%20Toolbox%20-%20Einkaufsliste.md) §10.1 waren Wunsch,
nicht Bestand.

## 1. Entscheidungen (alle `PROVISIONAL`, Agent)

| # | Frage | Antwort |
|---|---|---|
| T-1 | Tasten | **Inset = `I` im Face-Modus** (Blender), `I` im Edge-Modus bleibt Loop Insert; `INSET` hat keine eigene Taste, ist aber per `keymap.json` bindbar. **Bevel = `Ctrl+B` halten** (Blender; war frei), wirkt je nach Modus. **Vertex Slide = `G` im Vertex-Modus** (dort tat `G` bisher nichts), `G` im Edge-Modus bleibt Loop Slide. Kein Eintrag in `config/keymap.json` (erst nach Manus Freigabe). |
| T-2 | Bedienung | Inset und Bevel wie Extrude (`T`): halten, Maus **nach rechts = breiter**, nach links schmaler bis 0, loslassen = übernehmen, `Esc` = exakt zurück, Antippen = nichts; `Shift` = fein (×0,2), `Alt` = Kamera wie bei T/G. Vertex Slide wie Loop Slide: halten und ziehen, loslassen = übernehmen. |
| T-3 | Was Bevel je Modus tut | Vertex-Modus: Chamfer der Punkte (jede Kante bekommt einen Punkt im Abstand der Breite, ein Deckel schließt das Loch; am Rand bleibt der Schnitt offen). Edge-Modus: Bevel der Kanten. Face-Modus: Bevel der inneren Kanten der Flächen (Blender/Maya). Ein Segment. |
| T-4 | Auswahl danach | Inset: die inneren Flächen (Face-Modus). Bevel: im Vertex-Modus die neuen Punkte, im Edge-Modus die Kanten der neuen Flächen, im Face-Modus die neuen Flächen (Blender). Vertex Slide: unverändert. |
| T-5 | Bevel an Kantenenden | Wie Blender mit einem Segment: endet eine Bevel-Kante an einem Punkt mit drei Kanten, wird die Ecke abgeschnitten; mit vier oder mehr bleibt der Punkt und der Streifen läuft spitz in ihn (eine einzelne Rasterkante wird ein Sechseck). Treffen sich zwei Bevel-Kanten mit mehreren unbevelten dazwischen (L-Ecke), liegt der neue Punkt am Schnitt der Versatzlinien; mit genau einer dazwischen gleitet er auf ihr. Drei oder mehr Bevel-Kanten an einem Punkt bekommen einen Deckel (Würfelecke = Dreieck). |
| T-6 | Vertex Slide: welche Kante | Jeder Punkt nimmt die Kante, deren Richtung auf dem Bildschirm am besten zur Mausbewegung seit dem Drücken passt; zurück zum Startpunkt = exakt der Ausgangszustand; Weg von 0 % bis 100 % (auf dem Nachbarn). Mehrere Punkte gleiten gemeinsam um denselben Anteil. Maskierte Punkte bleiben (teilmaskiert: ein Teil des Wegs), versteckte Nachbarn sind kein Ziel. Unter Symmetrie stoppt der Weg bei 98 % (zwei Punkte an einer Stelle würden die Spiegelpaarung mehrdeutig machen); dieselbe Grenze gilt seit heute für Loop Slide, der das vorher still zuließ. |
| T-7 | Begrenzung | Inset und Bevel stoppen kurz vor dem Punkt, an dem eine Kante auf Länge 0 schrumpfen würde (98 %); die Statuszeile zeigt `(limit)`. |
| T-8 | Symmetrie | Auswahl plus Spiegelbild in einem Schritt, Positionen exakt gespiegelt, neue Kanten auf der Ebene kommen in die Seam, die Vollständigkeitsprüfung (D-strict) ist der Wächter. Inset auch über die Mitte hinweg; Vertex Slide eines Punkts auf der Ebene nur entlang der Seam. **Abgelehnt mit Statuszeile:** Bevel einer Kante oder eines Punkts **auf** der Ebene, Inset einer Fläche über der Mitte; auf nur teilweise symmetrischen Meshes lehnt der Wächter ein Bevel ab, dessen Nachbarflächen keine Spiegelpartner haben. |
| T-9 | Morph-Ziele | Inset und Bevel laufen auf Meshes mit Morph-Zielen: neue Punkte übernehmen die Werte des Punkts, aus dem sie wachsen (wie Extrude). Vertex Slide ändert nur Positionen. |

## 2. Gebaut (2026-10-29)

- **Vertex Slide:** `src/mirai/topology/vertex_slide.py` (Plan + Positionen), `Application._vertex_slide_*`
  (über `G`/`LOOP_SLIDE`, Journal und History wie Loop Slide). Tests `tests/test_vertex_slide.py`.
- **Inset (Region):** `src/mirai/topology/inset.py`. Jeder Umrisspunkt der Region bekommt eine Kopie, die Flächen der
  Region werden auf die Kopien umgebaut (innere Punkte bleiben), jede Umrisskante bekommt eine Wand. Abgelehnt: keine
  Fläche, geschlossene Hülle (kein Umriss), Flächen, die sich nur an einer Ecke berühren. Tests `tests/test_inset.py`.
- **Bevel:** `src/mirai/topology/bevel.py` (Fächer um jeden Punkt, Sektoren zwischen den Bevel-Kanten, Umbau der
  Flächen, Streifen und Deckel gegen die Nachbarn gewunden). Abgelehnt: Bevel-Kante am Rand, Kante ohne Fläche,
  nicht-mannigfaltiger Punkt / gekippte Windung. Tests `tests/test_bevel.py`.
- **Gemeinsam:** `src/mirai/topology/offset_build.py` (`OffsetBuild`: jeder neue Punkt = Ursprung + Breite × Richtung,
  dazu die Begrenzung), `Application._offset_*` (Geste: Planen beim Drücken, Topologie einmal ab 4 px Bewegung, danach
  nur Positionen, ein `MeshDeltaCommand` beim Loslassen), `src/mirai/symmetric_offset.py`
  (`symmetry_declarations.OFFSET_COORDINATORS`), Layer-Gate (`layer_declarations`, Regeltests in
  `tests/test_layer_topology_ops.py`), Tests `tests/test_symmetric_offset.py`.
- UVs (AD-026): Inset-Innenflächen behalten ihre UVs, Wände wie Extrude; Bevel gibt einem neuen Eckpunkt die UV der
  ersetzten Ecke, Streifen und Deckel leiten ihre UVs von den Nachbarn ab. Regionen erben über das Journal.

**Verifiziert (2026-10-29, Container, kein Referenz-PC):** Unit- und App-Tests der drei Werkzeuge (Topologie-Zählungen,
Breite/Abstand, Begrenzung, Esc/Antippen/Breite 0, Undo/Redo exakt, Ablehnungen, Symmetrie inkl. Seam und exakter
Spiegelung, UVs, Morph-Layer-Regel), dazu ein Zufallstest auf `subd_cube`, `head_basemesh` und
`man_with_shoes_basemesh` (je ~150 Gesten mit und ohne Symmetrie): Mesh-Invarianten nach jeder Geste, Undo/Redo
bitgleich, unter Symmetrie keine Verletzung der Vollständigkeit. Nicht gemessen: Geschwindigkeit (keine Aussage);
Gefühl der Breite, Kantenwahl und Tasten braucht Praxistest B25.

## 3. Nicht-Scope (bewusst für später: „Ausbauen kann man die dann immer noch“)

Mehrere Bevel-Segmente und Profil, Inset-Tiefe und „Individual“, Bevel von Randkanten, Bevel/Inset auf der
Symmetrieebene, Vertex Slide über den Nachbarn hinaus (Blender `C`/Alt), Überschneidungen jenseits der Kantenlänge
(Clamp Overlap), UV-Interpolation entlang der Bevel-Kante, Face Slide. Die Maske gilt nur für Vertex Slide.

## 4. Praxistest B25 (für Manu, ca. 15–20 Minuten, `python src/main.py`, Kopf-Mesh oder `Shift+A` → Cube / Plane)

Annahmen, die ich aus deinem Auftrag gelesen habe (ein Satz Korrektur genügt): Grundfunktion heißt ein Segment, eine
Breite per Maus, keine Optionen; die Tasten sind Blender-nah gewählt und vorläufig.

1. **Inset:** `3`, eine Fläche wählen, `I` halten, Maus nach rechts ziehen, loslassen. Dann mehrere zusammenhängende
   Flächen (z. B. Augenpartie) — ein gemeinsamer Ring? Breite fühlt sich richtig an (Geschwindigkeit, rechts = breiter)?
   `Esc` während des Ziehens, `Ctrl+Z` danach.
2. **Inset mit Symmetrie:** `Shift+S`, Flächen auf einer Seite und über die Mitte hinweg (Mund) — Spiegelseite folgt?
3. **Bevel Kanten:** `2`, eine Kante bzw. einen Edge-Loop (`Shift+L`) wählen, `Ctrl+B` halten und ziehen. Würfel:
   eine Kante, eine Ecke (drei Kanten), alle Kanten. Sehen die Enden aus, wie du sie erwartest (T-5)?
4. **Bevel Punkte:** `1`, einen Punkt wählen, `Ctrl+B` — Chamfer wie erwartet? Im Face-Modus `3`: Flächen wählen,
   `Ctrl+B` bevelt ihre Kanten — brauchst du das so?
5. **Vertex Slide:** `1`, einen oder mehrere Punkte wählen, `G` halten und in Richtung einer Kante ziehen — nimmt er die
   Kante, die du meinst? Mit Symmetrie einen Punkt auf der Mitte gleiten lassen.
6. **Auswahl danach** (T-4) und **Tasten** (T-1): passt `I` im Face-Modus, `Ctrl+B`, `G` im Vertex-Modus? Wenn ja,
   „Taste passt“ pro Taste, dann trage ich sie in `config/keymap.json` ein.

| Punkt | Verdikt (KEEP / CHANGE / DROP) | Notiz |
|---|---|---|
| 1 Inset | | |
| 2 Inset + Symmetrie | | |
| 3 Bevel Kanten | | |
| 4 Bevel Punkte / Face-Modus | | |
| 5 Vertex Slide | | |
| 6 Auswahl danach, Tasten | | |
