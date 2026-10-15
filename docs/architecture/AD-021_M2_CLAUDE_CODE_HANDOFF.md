# Handoff: AD-021 — M2 Rest (M2-2 Objekt-Transform, M2-3 Apply/Clear, M2-4 Edit-Objekt wechseln)

**An:** Claude Code (neue Session — dieses Dokument ist der Startpunkt, kein Chat-Kontext nötig)
**Modell/Effort:** Opus, effort `high`
**Modus (M5):** Production-Build in Slices. Die Architektur ist entschieden (AD-021 DECIDED, §4.3 L-1…L-5, §4.6, §4.8),
alle Artist-Gates für diese Slices sind beantwortet. **BUILD darf keine neue Erkenntnis behaupten.** Sieht beim Bauen
etwas anders aus als hier beschrieben: anhalten und melden („Bei Widerspruch", §9).

**Stand:** `main` @ `27f1c8a` — M0 (Core), M1 (Referenz-Objekte, Modus `4`), M2-0 (Referenz-Ghost) und M2-1 (Platzierung
im Zeichnen und in allen Komponentenpfaden, noch ohne Bedienung) sind gemergt. Neuer Branch von `main`.

**Baseline** auf `27f1c8a` (`xvfb-run -a python -m pytest`, mit `libegl1` im Container — ohne EGL werden
`tests/test_main_wiring.py` und Fenster-Proben übersprungen statt ausgeführt):

| Baum | Ergebnis |
|---|---|
| `tests/` | 3356 passed, 6 skipped, **1 failed** — `tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring` (eingecheckte Probe vom 2026-10-12, schlägt auf `main` genauso fehl; nicht anfassen, im Bericht nennen) |
| `playground/tests` | 1241 passed |
| `experiments/symmetry_lab/tests` | 459 passed, 4 skipped |

Setup im Container: `pip install -r requirements-dev.txt`, `apt-get install -y libegl1`.

**Ziel:** Manu kann jedes nicht-gesperrte Objekt in Modus `4` **platzieren** (verschieben, drehen, gleichmäßig
skalieren), die Platzierung ausdrücklich **übernehmen oder löschen**, und **jedes** normale Objekt zum bearbeiteten
machen — und sieht immer, auf welcher Ebene er arbeitet (A-3, A-5).

---

## 0. Was schon gebaut ist — Einstiegspunkte im Code

| Thema | Wo | Was du davon brauchst |
|---|---|---|
| Objekte (M0, Core, eingefroren) | `src/core/scene.py` | `SceneObject.transform: ObjectTransform` (frozen dataclass: `translation`, `rotation` = 3×3 in **Zeilen**, validiert orthonormal/det +1 mit `ROTATION_TOLERANCE = 1e-9`, `scale > 0`), `pivot` (Objektraum), `state`; `Scene.edit_object_id` (Setter prüft nur Existenz), `add_object` / `remove_object` / `restore_object` |
| Objekt-Commands, Reset, Look (M1/M2-0) | `src/mirai/scene_objects.py` | `AddObjectCommand`, `ObjectStateCommand` als Muster für neue App-`Command`s; `REFERENCE_BASE_COLOR`, `REFERENCE_GHOST_ALPHA` |
| Objektraum (M2-1) | `src/mirai/object_space.py` | `world(p) = t + c + s·R·(p − c)` (E-2), `to_world`/`to_object`/`delta_*`/`axis_*`, `model_matrix`, `is_identity` (Identität = exakter Durchgang), `ObjectSpaceCamera` |
| **Daraus folgt für M2-2:** | | Die Welt-Lage des Pivots ist `t + c` — **unabhängig von R und s**. Drehen um den Pivot = `R' = Q·R`, Skalieren = `s' = s·f`, jeweils **ohne** Translations-Korrektur; Verschieben = `t' = t + Δ` |
| App-Objektpfad | `src/mirai/application.py` | `add_reference`, `_sync_object_views` (gleicht Viewport-Einträge, Matrizen, Ghost mit `scene.objects` ab), `_placement_changed()` (**nach jeder Platzierungsänderung und ihrem Undo/Redo aufrufen**), `_object_camera(obj)` / `_edit_camera` (Objektraum-Kamera, `OrbitCamera` bei Identität), `_pick_object`, `_select_object_at`, `_switch_object_state`, `_object_mode_refuses` + `_COMPONENT_COMMANDS` (heute: W/E/R/T/C/Entf/Shift+S in `4` abgelehnt), Mirror-Einträge `(before, after, mesh_step)` mit `objects` + `edit_object_id` im Snapshot, `_apply_undo_redo` / `_undo_redo` (bei `mesh_step=False` kein Rebuild des Edit-Meshes) |
| Hold-Key-Gesten (Komponenten) | `Application._transform_arm` / `_transform_step` / `key_release` / `_cancel` / `_transform_end`, `interaction_owner` | Muster für die Objekt-Geste; `interaction_owner == "transform"` sperrt Space-Menü, Moduswechsel, Undo während der Geste — die Objekt-Geste muss denselben Owner melden |
| Tools: Weltachsen auf platzierten Objekten (E-8) | `src/mirai/interaction/tools/transform.py` (`object_axis`, `world_masked_delta`, `world_axes_basis`) | Komponenten-Constraints sind erledigt; für die Objekt-Geste gelten X/Y/Z direkt als Weltachsen |
| Zeichnen (E-9) | `Viewport.set_model_matrix`, `overlay_camera_uniforms` (`view·model`), `set_object_entry(..., model_matrix=, alpha=, ignores_wireframe=)`, `RenderMesh.set_model_matrix`, `GLRenderStore` (`u_model`, `u_alpha`), AD-018 Addendum 2026-10-15 | Ein Transform ändert nur Uniforms, nie Buffer |
| Tests als Vorlage | `tests/test_object_space.py` (setzt `transform` direkt + `_placement_changed`), `tests/test_application_objects.py`, `tests/test_reference_display.py` | |
| Doku | AD-021 §6.1–§6.3 (Umsetzungsnotizen), §7 (Fragen), Kurzfassung | |

## 1. Referenzdokumente (gelten, nicht neu verhandeln)

[AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) — §2, §4.3 (**L-1…L-5**, Transform-Form), §4.4, §4.6 (Commands,
Composite, App-Konsequenzen), §4.7 RF-1…RF-6, §4.8, §5.4 „M2", §6.1–§6.3, §7. ·
[AD-012](AD-012-TRANSFORM-SPACE.md) · [AD-014](AD-014_Core-Change-Basis-Parameter-for-ScaleOperation.md) ·
[AD-016](AD-016-TRANSFORM-OWNS-QWE-SINGLE-CURRENT-TOOL.md) D4 (Hold-Key) ·
[AD-018](AD-018-PRODUCTION-DRAW-BINDING.md) (Addendum 2026-10-15) ·
[AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md) · [AD-SYM-04](AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md) (E1) ·
[AD-020](AD-020-SOFT-SELECTION-APP-PATH.md) E3 · `AGENTS.md` §8a · `CLAUDE.md` · `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` §5.

## 2. Entscheidungen

### Artist (Manu, alle 2026-10-15) — gelten

| # | Antwort | Wirkung |
|---|---|---|
| Q-1 | Referenz gesperrt | Objekt-Transform, Apply/Clear auf einer Referenz: abgelehnt (RF-4) |
| Q-2 | durch Referenzen hindurch picken | gilt weiter |
| Q-3 | Zustandswechsel / Hinzufügen = je ein Undo-Schritt | ebenso Objekt-Transform, Apply, Clear (§4.6) |
| Q-4 | nur gleichmäßige Skalierung, `s > 0` | `R` in `4` immer gleichmäßig; X/Y/Z wirken bei Objekt-Scale nicht (Statuszeile sagt es) |
| Q-5 | in `4` auswählen, dann `1`/`2`/`3` | Geste für den Edit-Objekt-Wechsel (M2-4) |
| Q-6 | Statuszeile zuerst | Ebenen-Marker = Statuszeile (M2-2/M2-3), besserer Marker erst nach dem Test |
| Q-7 | Symmetrie-Ebene dreht mit dem Objekt | im Code seit M2-1 wahr; **Wortlaut** in AD-SYM-04 (E1) und `src/mirai/symmetry_axis.py` (Docstring) mit M2-2 ändern |
| Q-8 | Undo springt zum Objekt des Schritts zurück | M2-4 |
| Q-9 | Kamera bleibt beim Hinzufügen | unverändert |
| Q-11 / §7.3 | Blau gut; Ghost (`Alt+D`) gebaut; **Ghost hell genug**; normales Objekt im Wireframe wie das Edit-Objekt: **„passt so"** | fertig, nichts zu tun |
| Q-12 | Klick in `4` schaltet Referenz ↔ normal | bleibt |
| Q-13 | **zurückgestellt** — Pivot verschieben kommt später | Pivot = Objekt-Ursprung (M0-Default). **Kein Pivot-Werkzeug bauen.** Drehen/Skalieren in `4` wirkt um den Ursprung der Datei |

### Engineering (`PROVISIONAL`, in diesem Handoff festgelegt)

- **E-11 Objekt-Geste.** Eigener, kleiner Gesten-Pfad in `Application` (nicht die Komponenten-Tools): Arm mit `W`/`E`/`R`
  in `4`, Zielobjekte = `Selection.objects` ohne Referenzen, Start-Transforms merken, erste Mausbewegung beginnt,
  Loslassen committet, `Esc` stellt die Start-Transforms exakt wieder her. `interaction_owner` meldet `"transform"`.
  - **Move:** Welt-Delta = `camera.screen_delta_to_world(pivot_world, dx, dy, w, h)` mit der echten `OrbitCamera`,
    Achsen-/Ebenen-Constraint als Weltmaske; `t' = t_start + Σdelta`.
  - **Rotate:** Winkel aus kumulierter Pixel-Distanz wie `RotateTool` (`RADIANS_PER_PIXEL = π/400`), Achse = Blickrichtung
    der Kamera ohne Constraint, sonst die Weltachse bzw. Ebenen-Normale; `R' = Q(achse, winkel_gesamt)·R_start` (immer vom
    Start aus, keine Drift innerhalb der Geste); vor dem Speichern orthonormalisieren (Gram-Schmidt), damit
    `ObjectTransform` nie an `ROTATION_TOLERANCE` scheitert.
  - **Scale:** Faktor wie `ScaleTool` (`SCALE_PER_PIXEL = 0.005`, `MIN_SCALE = 0.01`), `s' = s_start·f`, gleichmäßig.
  - Mehrere Objekte: jedes um seinen eigenen Pivot, Move mit demselben Delta.
- **E-12 `ObjectTransformCommand`** (in `scene_objects.py`): Liste `(obj, before, after)`; Undo/Redo setzt die
  Transforms. Mirror-Eintrag mit `mesh_step=False`. Nach Commit, Undo und Redo: `_placement_changed()`.
- **E-13 Composite** (M2-3, §4.6, erster Composite des Projekts): kleines App-`Command` mit Liste, Undo rückwärts;
  `HistoryStack` bleibt unverändert.
- **E-14 Edit-Objekt-Wechsel als eine Funktion** (M2-4): genau eine Stelle, die `scene.edit_object_id` setzt *und* den
  Viewport, Caches und Soft umhängt. **Achtung, heute vorhandene Lücke:** `_restore_selection` (Undo/Redo) setzt
  `scene.edit_object_id` direkt, ohne Viewport-Tausch — in M1/M2-1 unschädlich (das Edit-Objekt wechselt nie), ab M2-4
  ein Fehler. `_restore_selection` muss über E-14 gehen.

## 3. Slices

Jeder Slice: eigener Commit, eigene Tests, Doku im selben Commit, GL-Rauchtest mit Screenshot (xvfb), Praxistest-Anleitung
auf Deutsch in der AD-021-Kurzfassung und `docs/ATELIER.md` §2 B. Reihenfolge verbindlich.

### M2-2 — Objekt verschieben/drehen/skalieren in `4`

- E-11, E-12. `_object_mode_refuses` / `_COMPONENT_COMMANDS`: W/E/R in `4` arm jetzt die Objekt-Geste; `T`, `C`,
  `Entf`/Rücktaste und `Shift+S` bleiben abgelehnt (Komponentenarbeit, L-1). Abgelehnt mit Statuszeile: keine Auswahl,
  nur Referenzen ausgewählt (Text nennt die Sperre, RF-4); Referenzen in einer gemischten Auswahl werden **nicht**
  mitbewegt und die Statuszeile sagt das (`PROVISIONAL` — melden, falls es sich falsch anfühlt). Kein Hover in `4`.
- L-1: schreibt nur `transform`, nie ein Mesh; die Mesh-`export_state()` aller Objekte ist nach der Geste bitgleich.
- Q-6: nach jedem Objekt-Commit `Object 'gollum': moved|rotated|scaled (object level)`; beim Wechsel nach `1`/`2`/`3` auf
  einem platzierten Edit-Objekt ein Hinweis wie `Mode: Vertex · object 'head' is placed (object level)`.
- Q-7: Wortlaut AD-SYM-04 E1 und Docstring `symmetry_axis.py` („Ursprung/Achse des Objekts"), im selben Commit.
- Tests: Geste je W/E/R inkl. Constraint X und Ebene, `Esc` exakt, Undo/Redo (Transform zurück, Pick-Cache frisch,
  Matrizen im Viewport), Ablehnungen, zwei Objekte zugleich, Rotation bleibt nach vielen Schritten gültig
  (Orthonormalität), danach am platzierten Edit-Objekt Komponenten bearbeiten (Move/Knife), Symmetrie-Objekt drehen und
  symmetrisch bearbeiten (P-2 gilt weiter), Serialisierungs-Roundtrip eines platzierten Objekts (Stichprobe).
- Praxistest (Vorschlag): `python src/main.py`, Shift+Klick `gollum` im `Leertaste`-Menü, `4`, gollum anklicken
  (→ normal), mit `W` aus dem Kopf herausziehen, mit `E`/`R` drehen/skalieren, `Ctrl+Z`; zurück auf Referenz klicken.

### M2-3 — Apply/Clear Transform + Ebenen-Marker (ohne Pivot-Werkzeug, Q-13)

- **Apply Transform** (L-3, Max „Reset XForm"): für jedes ausgewählte Nicht-Referenz-Objekt Mesh-Positionen = Welt-
  positionen (`MeshStateCommand` auf *dessen* Mesh), Transform = Identität; ein Undo-Schritt (E-13). Pivot danach:
  Vorschlag — Pivot auf die bisherige Welt-Lage des Pivots (`t + c`) setzen, damit ein späteres Drehen am selben Ort
  wirkt; die Alternative (Pivot = Ursprung, wie Q-13 es vorläufig festlegt) ist ebenso vertretbar — wählen, als
  `PROVISIONAL` notieren, Manu fragen.
- **Clear Transform:** Transform = Identität, Mesh unverändert, das Objekt springt; ein Undo-Schritt.
- **Symmetrie:** Apply auf einem Mesh mit Symmetrie-Definition nur, wenn die Abbildung die Symmetrie-Ebene exakt auf eine
  Achsenebene durch den Ursprung abbildet (Rotation achsentreu **und** keine Translation entlang der Ebenennormalen,
  `s` beliebig) — sonst abgelehnt mit Grund in der Statuszeile (`PROVISIONAL`, melden).
- **Bindung:** nicht entschieden. Vorschlag `PROVISIONAL`, z. B. `Ctrl+A` = Apply und `Alt+Shift+A` = Clear in `4`
  (frei prüfen: `Alt+A` ist „Auswahl leeren"); im Bericht als Frage an Manu.
- Ebenen-Marker (Q-6): Statuszeile wie in M2-2, zusätzlich nach Apply/Clear.
- Tests: Weltpositionen vor/nach Apply bitnah gleich (Toleranz nennen), Undo stellt Mesh *und* Transform her, Clear,
  Ablehnungen (Referenz, Symmetrie-Fall), Edit-Objekt-Auswahl bleibt nach Apply gültig (nur Positionen ändern sich).

### M2-4 — Edit-Objekt wechseln (Q-5, Q-8)

- Geste (Q-5): in `4` genau ein normales Objekt ausgewählt, dann `1`/`2`/`3` → es wird Edit-Objekt, der Modus wird
  gesetzt, Komponenten geleert (Reihenfolge §4.4). Mehrere oder nur Referenzen ausgewählt → kein Wechsel, Statuszeile.
  Kein Undo-Schritt, aber im Mirror-Snapshot (seit M1 vorhanden).
- E-14 als einzige Stelle: `scene.edit_object_id`; **Viewport**: das neue Edit-Objekt braucht den Eintrag mit
  `SelectionOverlay` und Overlays, das alte wird Objekt-Eintrag. Der Viewport hat dafür heute **keine API** (der Edit-
  `RenderMesh` entsteht im Konstruktor mit `overlay=`; Einträge haben `overlay=None` und keine `highlight_flags`).
  Kleinste saubere Lösung wählen (z. B. `Viewport.set_edit_mesh(mesh, model_matrix)`, ein Rebuild beider ist erlaubt —
  gollum kostet dabei Sekunden; messen und nennen). Zusatz-Overlays (Soft-Bänder, Symmetrie-Anzeige) bekommen das neue
  Mesh über `Viewport.mesh`.
- App-Zustand am Edit-Mesh: Soft-Radius neu (`_soft_refresh_radius`, vierter Radius-Event, §4.8), Pick-Cache, Symmetrie-
  Report-Cache, Hover, Selection-Overlay; Wechsel während einer Interaktion oder Knife-Session ablehnen.
- Q-8: `_restore_selection` über E-14 — Undo eines Schritts an einem anderen Objekt macht dieses wieder zum Edit-Objekt
  und zeigt es korrekt an. RF-5: eine Referenz wird nie Edit-Objekt; das Edit-Objekt wird nie Referenz (heute so).
- Tests: Wechsel und zurück, Komponentenarbeit am neuen Edit-Objekt (inkl. platziert), Overlays nur am Edit-Objekt
  (gleichlautende IDs im alten leuchten nicht), Undo über einen Wechsel hinweg (Q-8), Ablehnungen, Soft-Radius.

## 4. Nicht im Umfang

Pivot verschieben (Q-13, später), Hierarchie/Parent, Instancing, nicht-gleichmäßige Objekt-Skalierung,
Mehr-Objekt-Komponentenbearbeitung (A-4), Soft über Objektgrenzen, `space="local"`, Speichern/Laden von Szenendateien,
Objekt-Hover in `4`, Objekte löschen/umbenennen, gollum-Performance (messen ja, optimieren nein), Playground und Symmetry
Lab (bleiben bei einem Objekt; das Lab lehnt `4` und `Alt+D` in BLOCK sichtbar ab).

## 5. Core

**Keine Core-Änderung erwartet** (M0 liefert alles; Commands sind App-`Command`s). Wird doch eine nötig: anhalten, in
AD-021 begründen (CORE_V1_FREEZE §7), Manu fragen.

## 6. Tests

Gezielt während der Arbeit (AGENTS.md §8a); vor jedem Push alle drei Bäume einmal:
`xvfb-run -a python -m pytest tests -q`, `… playground/tests -q`, `… experiments/symmetry_lab/tests -q` — **nicht das
nackte `pytest`**. Erwartung: Baseline plus neue Tests, der eine bekannte Fehlschlag bleibt der einzige. Für neue Tests
eine Mutationsprobe (Umrechnung/Commit abschalten → Tests müssen fallen), wie in M2-1.

## 7. Doku (im selben Commit)

AD-021: Decision Record, Umsetzungsnotiz je Slice (§6.4 ff., Muster §6.3), §7, Kurzfassung mit Praxistest.
AD-SYM-04 + `symmetry_axis.py` (Q-7, M2-2). `docs/ATELIER.md` (Fähigkeiten, §2 B, D1d), `ROADMAP.md` ARCH-01,
`docs/architecture/README.md`, `WP-06_INTAKE_LOG.md`, `src/main.py`-Docstring.

## 8. Abnahme

Je Slice Tests + Rauchtest + Doku; danach Manus Praxistest. Kein Agent behauptet Artist-Validierung oder promotet.

## 9. Bei Widerspruch

Anhalten und melden, wenn: eine Core-Änderung nötig wird; ein bestehender Test außerhalb von M1/M2 geändert werden müsste;
die Objektraum-Kamera einen Pfad nicht abdeckt; E-14 sich nicht als eine Stelle bauen lässt; eine `PROVISIONAL`-Ableitung
hier (gemischte Auswahl, Apply-Pivot, Apply-Ablehnung bei Symmetrie, Bindungen) im Rauchtest falsch wirkt.
