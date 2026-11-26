# AD-037 — Texture paint: storage, data model, foundations (Phase 1), the Paint Room (Phase 2), layers and UV transfer (Phase 3), alpha tip and stroke queue (Phase 4a), jitter, scatter and spray (Phase 4b), library, presets and picker (Phase 4c)

**Status:** **DECIDED (Manu, 2026-11-18)**: „P-1 ja, P-2 ja, P-3 Go, P-4 ja, P-6 ja“ (the audit's addendum), the additive
Core change and scene format v14 included. **IMPLEMENTED Phase 1 (2026-11-18, container: TESTED)** as built in §2–§6.
**Reference-PC probes P-A … P-F: RUN (Manu, 2026-11-18)** — P-A, P-B, P-C, P-E pass; P-D (2.06 s at 2048²) and P-F
(7.4 / 9.4 s) failed and were worked on the same day (§7.1), the re-run is open (its output has not reached the repo yet).
**Decisions P-7, P-10, P-13: Manu, 2026-11-18** (§1); the P-13 refusals are built (§8). **IMPLEMENTED Phase 2, the Paint
Room (2026-11-18, container: TESTED; reference PC: P-A … P-G pass on the shown surfaces, §10.8e)** as built in §10: SPACE menu row, no key, no keymap entry.
**Phase 3 scope and P-12: Manu, 2026-11-19** (§1). **IMPLEMENTED Phase 3, several layers, Multiply and the UV transfer
(2026-11-19, container: TESTED; reference PC: not run yet)** as built in §11; the P-13 refusal of a GoZ UV change is lifted.
**Phase 4 (alpha brushes, stroke dynamics, brush presets): PROPOSED 2026-11-25, its decisions taken; IMPLEMENTED 4a
(alpha tip, projection with the wrap fallback, world spacing, stamp queue; 2026-11-25, container: TESTED; reference PC:
every 4a gate met after the same day's optimisation, §12.7; **Praxistest passed, Manu 2026-11-25**: „Praxistest gut
bestanden. Läuft flüssiger, als ich erwartet habe. Keine Verzerrungen auch über extreme winkel hinweg.“) as built in §12;
IMPLEMENTED 4b (jitter, scatter, the orientation modes, the spray emitter, counter-based randomness; 2026-11-25,
container: TESTED, every 4b gate met in the container; reference PC and Praxistest: open) as built in §13;
IMPLEMENTED 4c (the library: built-in and user alphas and presets in `~/.mirai_bastel/paint/`, references id → hash →
name with the round-tip fallback, the picker and the import card, the starter-alpha generator with its contact sheets
- the starter alphas not adopted until Manu's check; 2026-11-26, container: TESTED, every 4c gate met in the container;
reference PC, contact-sheet verdict and Praxistest: open) as built in §14** — [`ALPHA_BRUSH_STROKE_SYSTEM_PROPOSAL_2026-11-25.md`](../research/ALPHA_BRUSH_STROKE_SYSTEM_PROPOSAL_2026-11-25.md) (slices 4a–4c; **decisions P-18 … P-28: Manu 2026-11-25, „P-18 bis P-28 zugestimmt“**; user assets in `~/.mirai_bastel/paint/` and the procedural starter set: Manu 2026-11-25).
**Basis:** [`TEXTURE_PAINT_ROOM_ARCHITECTURE_AUDIT_2026-11-18.md`](../research/TEXTURE_PAINT_ROOM_ARCHITECTURE_AUDIT_2026-11-18.md)
(§3 storage, §4 architecture, §5 topology, §8 performance, §10 Phase 1). Implemented on `claude/brave-clarke-40728c` @
`25154ac` (the audit and its decisions addendum).
**Extends:** [AD-026](AD-026-FACE-CORNER-UVS-AND-TEXTURE.md) (face-corner UVs, one texture per object, the textured
program), [AD-024](AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md) §1.2 (data on the object, not in a side table),
AD-026 §7 addendum (scene-relative texture paths, `<scene>_textures/`), [AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md)
(the journal the texel map patches from), [CORE_V1_FREEZE](CORE_V1_FREEZE.md) §7.1.

## Kurzfassung (Deutsch)

Phase 1 legt das Fundament für den Paint Room, ohne dass schon gemalt wird:

- **Core:** ein Objekt kann jetzt Mal-Ebenen tragen (`SceneObject.paint`: Auflösung, Ebenen mit Name, Bilddatei,
  Deckkraft, sichtbar, Mischmodus „normal“). Szenenformat **v14** nur, wenn ein Objekt bemalt ist – jede bisherige Szene
  bleibt Zeichen für Zeichen gleich. Deine ZBrush-Textur bleibt unberührt die unterste Schicht (P-4).
- **UV-Prüfung** (SPACE-Menü „UV-Prüfung“, nur bei Objekten mit UVs, keine Taste): Statuszeile und Färbung der Flächen, die
  sich nicht richtig bemalen lassen – rot ohne UVs / ohne UV-Fläche, orange überlappend, violett außerhalb 0–1. Auf dem
  Gollum-Kopf: 44 Flächen ohne UV-Fläche, 148 Flächen berühren eine Überlappung (3,3 % der benutzten Pixel), 2 UV-Inseln,
  Dichte-Spreizung ×3,4 – wie im Audit.
- **Pixel → Fläche-Verzeichnis** (Texel-Karte): baut sich am Kopf in ~0,55 s (2048²), folgt Topologie- und UV-Änderungen
  über das Journal und braucht für Morph, Pose und Verschieben keinen Neuaufbau.
- **Pixel, Undo, Speichern:** die Pixel liegen im Speicher; ein Pinselstrich wird ein Undo-Schritt, Esc stellt exakt
  zurück; Speichern schreibt geänderte Ebenen als PNG nach `<Szene>_textures/` und ein **zusammengerechnetes PNG**
  (`<Objekt>_paint_flat_….png`) für OBJ/ZBrush.
- **Live-Textur** im Viewport: lädt nur geänderte Kacheln hoch; ohne sie ist die Zeichnung bitgleich die bisherige.
- **Messung auf deinem PC (2026-11-18):** Malen, Hochladen und Anzeigen sind schnell genug (P-A, P-B, P-C, P-E bestanden).
  Zu langsam waren der Kartenaufbau bei 2048² (2,06 s) und das Speichern (7–9 s). Den Kartenaufbau habe ich um ~35 %
  beschleunigt, das Speichern im Container fast halbiert; die 7–9 s auf deinem PC passen aber eher zu den
  Dateischreibvorgängen (z. B. Virenscanner) als zur Rechenzeit – die Sonde zeigt jetzt die Teile einzeln (§7.1). Bitte
  noch einmal laufen lassen.
- **Deine Entscheidungen P-5 (2048² Standard), P-7 (Welt-Radius), P-10 (Malen auf der gezeigten Fläche, mit SubD
  auf der SubD-Fläche, schon in Phase 2) und P-13** sind eingetragen; die P-13-Sperren sind gebaut: Attach eines
  bemalten Objekts ohne dieselbe Bemalung und eine ZBrush-Rückgabe mit neuen UVs auf einem bemalten Objekt werden mit
  Statuszeile abgelehnt.

**Phase 2 – der Paint Room (gebaut 2026-11-18, §10):**

- **Öffnen:** SPACE → „Paint Room öffnen“ (nur mit UVs, kein Auge; keine Taste). Der Raum stellt Shaded + Textur ein,
  schaltet Drahtgitter und Gruppenfarben aus und stellt beim Schließen alles zurück; die Kamera bleibt, wo sie ist.
  Abgelehnt bei Augen (P-14), ohne UVs, im Bearbeitungsfenster eines Morph-Ziels 
  (P-8 entschieden, Manu 2026-11-25: **Pose und eingeblendeter Morph sind erlaubt**, z. B. mouth_open, um im Mund zu malen).
- **Malen:** LMB ziehen malt (P-6, vorläufig, keine Keymap-Zeile), Alt+LMB dreht weiter die Ansicht, Shift+Rad Radius,
  Alt+Rad Deckkraft, das Rad zoomt, Esc nimmt den laufenden Strich exakt zurück. Panel „Paint Room“: Malen / Radieren /
  Pipette, Farbe, Radius (Prozent des Objektradius, P-7), Deckkraft, Fluss, Härte, Kurve (die Soft-Kurven), Spiegeln an der
  Symmetrie-Ebene, Auflösung 2048² / 1024² bis zum ersten Strich (P-5).
- **Gezeigte Fläche (P-10):** mit SubD an malt der Raum auf der SubD-Fläche – Treffer, Pinsel und Kreis liegen dort, ein
  Tupfer ist dort rund (gemessen: Unrundheit 1,04 statt 1,20 vom Käfig aus). Achtung: die SubD-Vorschau zeigt auf dem
  Gollum-Kopf **Stufe 1** (Stufe 2 hätte 36.008 Flächen, die Vorschau begrenzt auf 25.000) – gemalt wird also auf Stufe 1.
- **Ein Strich = ein Undo-Schritt**; der erste Strich legt die Bemalung an (Undo davon lässt das Objekt unbemalt).
  Speichern im Raum geht (Ebene + zusammengerechnetes PNG). Die Bemalung bleibt auch außerhalb des Raums sichtbar.
- **Messung im Container:** Raum öffnen 0,5 s (Käfig) / 0,6 s (SubD 1) / 0,9 s (SubD 2) bei 2048²; ein 3-%-Tupfer mit
  Spiegelung rund 2–3 ms CPU. Dein PC entscheidet (Sonde `probe_paint.py`, jetzt mit dem echten Tupfer und SubD-Zeilen).

**Phase 3 – Ebenen und UV-Transfer (gebaut 2026-11-19, §11):**

- **Mehrere Ebenen** im Panel „Paint Room“ (Abschnitt „Ebenen“, oberste zuerst): Häkchen = sichtbar, Klick auf den Namen
  = auf diese Ebene malen. Für die aktive Ebene: Name, Ebenen-Deckkraft (Vorschau beim Ziehen, ein Undo-Schritt beim
  Loslassen), Mischmodus; Knöpfe Neu, Hoch, Runter, Zusammenführen, Leeren, Löschen. Jede Änderung ist ein Undo-Schritt.
  Höchstens 8 Ebenen. Auf eine ausgeblendete Ebene wird nicht gemalt (Statuszeile).
- **Mischmodi Normal und Multiplizieren** (Deine Entscheidung P-12): Multiplizieren dunkelt die Schichten darunter mit
  der Ebenenfarbe ab, Weiß ändert nichts – für Adern, Flecken, Schatten in der Haut.
- **Zusammenführen** geht in die Ebene darunter, wenn beide sichtbar sind und denselben Mischmodus haben; das Bild bleibt
  dabei gleich (die Deckkräfte werden eingerechnet, das Ergebnis hat 100 %).
- **UV-Transfer:** Kommt aus ZBrush ein bemaltes Objekt mit neuen UVs zurück (UV Master), wird die Bemalung jeder Ebene
  auf die neuen UVs umgerechnet – statt die Rückgabe wie bisher abzulehnen. Ein Undo-Schritt nimmt Rückgabe und
  Umrechnung zusammen zurück. Gemessen auf dem Gollum-Kopf: die Farbe bleibt an ihrer Stelle auf der Fläche
  (Abweichung im Mittel ≤ 2/255).
- **Gespeichert** wird jede Ebene als PNG mit Name, Deckkraft, Sichtbarkeit und Mischmodus; das flache PNG für
  OBJ/ZBrush enthält alle sichtbaren Ebenen.

**Phase 4a – Alpha-Spitze, Projektion, Welt-Abstand, Stempel-Warteschlange (gebaut 2026-11-25, §12):**

- **Spitze** im Panel: „Rund“ (der Pinsel wie bisher, **bitgleich** nachgewiesen) oder eines von sechs Test-Alphas
  (Poren, Ader, Kratzer, Fleck, Punkte, Quadrat). Mit Alpha: „Winkel“ (Drehung gegen die Strichrichtung), „Kreismaske“
  (aus = das Alpha bestimmt seine Form, P-19), Härte/Kurve nur mit Kreismaske. „Abstand“ (für jede Spitze) in % des
  Stempeldurchmessers, gemessen **auf der Fläche** (P-18): rund 12,5 % (wie bisher), Alpha 100 %. Ausrichtung: „Strich
  folgen“ (P-21). Cursor: das gedrehte Rechteck, der Kreis gedimmt.
- **Projektion:** je Stempel eine Tangentialebene (gemittelte Normale der inneren halben Scheibe). Ab **4 % Radius** wickelt
  sich der Stempel dort, wo die Fläche unter der Ebene stark wegkippt, um die Fläche (**Wrap**, automatisch): so malt er
  bei 4–8 % nicht mehr durch die Oberlippe auf die Unterlippe (der runde Tupfer tut das bei 5 %) und wird an Nasenflügel,
  Nasenspitze und Lid nicht verschmiert. Bis 3 % bleibt er eben – dort besteht er alle Prüfungen, malt nirgends durch und
  ist so schnell wie der runde Tupfer. Am Nasenflügel ist er bei 3 % so gestreckt wie heute der runde Tupfer (1,42 / 1,33
  : 1); das kann dort kein treuer Stempel besser (Korrektur 2026-11-25, §12.7). Im Mundwinkel (Falte) bleibt er eben.
- **Schnelle Striche ohne Lücken:** die Stempel kommen in eine Warteschlange, die pro Bild 10 ms arbeitet (mehr, wenn
  > 150 ms Arbeit hinter dem Cursor liegen); die Farbe kann dem Cursor kurz nachlaufen. **Loslassen friert nie ein**: der
  Rest wird über die nächsten Bilder fertig gemalt, dann kommt der Undo-Schritt. Esc nimmt auch dann exakt zurück; Strg+Z,
  ein neuer Klick, SubD-Tasten, Speichern warten auf das Ende (der Rest ist klein) und laufen dann.
- **Kontaktbogen** der acht Prüfstellen: `docs/research/alpha_brush_4a_assets_2026-11-25/`. Dein Lauf auf dem
  Referenz-PC (2026-11-25): erst war die 3 %-Alpha-Platzierung zu langsam (18 / 24 ms statt ≤ 16,7); am selben Tag
  beschleunigt, im zweiten Lauf **14,1 / 16,0 ms – alle 4a-Grenzen eingehalten** (§12.7). **Praxistest bestanden**
  (Manu 2026-11-25: „Läuft flüssiger, als ich erwartet habe. Keine Verzerrungen auch über extreme winkel hinweg.“).

**Phase 4b – Zufall, Streuung, Spray (gebaut 2026-11-25, §13):**

- Im Panel drei **eingeklappte Abschnitte** mit Kurzfassung: **Strich** (Abstand; mit Alpha Ausrichtung – Strich folgen,
  Ansicht, Fläche, Zufall – und Winkel; Einzeln / Spray), **Streuung** (Drehung ±, Größe ±, Fluss ± je Stempel; Streuung
  quer und längs bis 2 Radien), **Spray** (Dichte bis 64 Stempel, Stempelgröße, Intensität). Ohne all das malt der
  Pinsel **bitgleich wie 4a** (zuerst festgenagelt, gegen eine eingefrorene Kopie von 4a).
- **Zufall mit Gedächtnis:** jeder Strich zieht beim Klick einen Startwert; jeder Stempel bekommt seine Werte nur aus
  (Startwert, Platzierung, Stempel). Mausgeschwindigkeit, Bildrate und Warteschlange ändern das Muster nicht; Strg+Z /
  Strg+Y stellen die Pixel her und würfeln nie neu; der **Spiegel** nutzt dieselben Werte gespiegelt.
- **Spray:** ein Klick = ein Stoß, Stillhalten fügt nichts hinzu (P-28); alle Stempel einer Platzierung werden in einem
  Durchgang gerechnet und in **einem** Schreibvorgang aufgetragen. Die Dichte pro Fläche hängt nicht von der
  Strichgeschwindigkeit ab.
- Messung im Container: 3 %-Spray mit 20 Stempeln (+ Spiegel) p95 12,8 / 24,1 ms (Grenze 33), 10-s-Spray-Strich kein
  Bild über 50 ms; die einfache Platzierung ohne Zufall kostet genau wie in 4a. **Offen:** Dein Referenz-PC-Lauf und der
  Praxistest (unten).

**Phase 4c – Bibliothek, Pinsel-Presets, Auswahl, Import, Starter-Sammlung (gebaut 2026-11-26, §14):**

- **Pinsel-Zeile** oben im Panel: Vorschau, Name, Kategorie, „* “ für Favoriten, „– geändert“; „Pinsel …“ öffnet die
  **Auswahl** (Reiter Pinsel / Alphas, Kategorie, Suche, Vorschaubilder, Favoriten zuerst, Rechtsklick: Favorit,
  Duplizieren, Umbenennen, Kategorie, Löschen). Geändert: Speichern (eigene), Speichern als …, Zurücksetzen.
- **Spitze:** Vorschaubild (öffnet die Alphas), mit Alpha „Rund“, Invertieren, Kontrast, Kreismaske. Fehlt ein Alpha,
  malt der Pinsel rund, zeigt „Alpha fehlt: …“ und behält den Verweis (Suche: Kennung → Pixel-Prüfsumme → Name).
- **Presets** speichern Spitze, Radius (P-20, „Größe behalten“ schaltbar), Deckkraft, Fluss, Härte, Kurve und den Strich –
  **nie** Farbe, Werkzeug, Spiegeln, Ebene (P-25). Eingebaute sind schreibgeschützt; Deine liegen in
  `~/.mirai_bastel/paint/` – nirgends sonst wird geschrieben, Szenen speichern nie Alphas. Der Raum startet mit „Runder
  Pinsel“ (= der bisherige Pinsel); sieben eingebaute Presets auf den 4a-Test-Alphas.
- **Import:** Bild wählen → Karte mit Live-Vorschau, Quelle **Alphakanal / Luminanz / Luminanz × Alphakanal** (vorgewählt,
  P-26), Invertieren, Kontrast, Name, Kategorie, Warnung bei hellem Rand; auf 1024 px begrenzt; dasselbe Bild zweimal =
  ein Alpha.
- **Starter-Sammlung:** 22 erzeugte Alphas in den sieben Kategorien von P-22 – **noch nicht übernommen**: erst Dein Blick
  auf die Kontaktbögen `docs/research/alpha_brush_4c_assets_2026-11-26/`, dann je Kategorie
  `python tools/make_starter_alphas.py --adopt …`.
- Messung im Container: Import 1024² ≤ 0,11 s (Grenze 0,5), erstes Öffnen mit 50 Vorschaubildern 88 ms (Grenze 150),
  Alpha-Speicher höchstens 64 MiB. **Offen:** Dein Urteil zu den Kontaktbögen, der Referenz-PC-Lauf, der Praxistest.

## 1. Decisions (Manu, 2026-11-18)

| # | Decision | Where it shows |
|---|---|---|
| P-1 | UV image painting is the one paint storage (no vertex colour, no Ptex, no hybrid) | §2: layers are images in UV space |
| P-2 | The Paint Room is a switchable configuration of the same window (Eye Lab pattern) | Phase 2; nothing here allocates outside a room |
| P-3 | Go for `SceneObject.paint` and scene format v14 | §2, CORE_V1_FREEZE §7.1 2026-11-18 (paint) |
| P-4 | The existing texture stays untouched as the base; paint lies above it; a flattened PNG is written beside the scene | §2.2, §5 |
| P-6 | Inside the Paint Room plain LMB drag paints (concept); keymap entries only after "Taste passt" | Phase 2; no binding here |

**Manu, 2026-11-18 (session chat, verbatim):** „P-7 Welt, P-10 wie vorgeschlagen, P-13 wie vorgeschlagen“.

| # | Decision | Where it shows |
|---|---|---|
| P-7 | The brush radius is a **world** radius (% of the bounding radius, like Soft and Brush O-3) | Phase 2 dab |
| P-10 | ~~Phase 2 paints on the cage with SubD shown off; SubD surface painting in Phase 3~~ — **revised by Manu the same day (§8.1): Phase 2 paints on the surface that is shown — the SubD surface when SubD is on, the cage when it is off** | Phase 2: texel map, hits and cursor on the drawn surface |
| P-13 | Faces without usable UVs (zero area, overlap, unmapped) are shown and skipped with a status line; **Attach is refused** when a painted object and its partner do not share that paint; **a GoZ return that changes a painted object's UVs is refused** until the UV transfer exists | the UV check (§4); the refusals (§8), built now |

**Manu, 2026-11-18 (later):** „P-5 ja“ — **2048² is the default resolution of a new paint stack, 1024² the fast option,
4096² not offered on the reference PC** (the audit's proposal). Phase 1 creates no stack; Phase 2 uses it.

**Manu, 2026-11-18 (later, verbatim):** „P-10 Option 1, SubD-Malen in Phase 2“ (after the measurement in §8.1).

**Manu, 2026-11-19 (session chat, the Phase 3 scope question):** features „Mehrere Ebenen, UV-Transfer“; blend modes
„Normal + Multiply“.

| # | Decision | Where it shows |
|---|---|---|
| P-12 | **Normal and Multiply** (the audit's proposal) | `PAINT_BLEND_MODES` = ("normal", "multiply"), §11.1 |
| Phase 3 | Several layers and the UV transfer first; pose / morph painting (P-8 / P-9), Blur / Smudge, masks and the 2D UV view not in this slice | §11 |
| P-13 (GoZ part) | The refusal "until the UV transfer exists" ends with the transfer: a GoZ return that changes a painted object's UVs moves the paint (the Attach refusal stays) | §11.3 |

Still open: P-9, P-11, P-14 … P-17.

## 2. The data model (Core part)

### 2.1 Values (`src/core/scene.py`)

- **`PaintLayer`** (frozen): `name` (non-empty text, unique in its stack), `image: str | None` (a path like
  `SceneObject.texture`; `None` = a fully transparent layer without a file), `opacity` ∈ [0, 1] (a number, not a bool or
  text), `visible: bool`, `blend` ∈ `PAINT_BLEND_MODES` = `("normal",)` (P-12 open; a new mode later is a new value an older
  build refuses). Defaults: opacity 1, visible, normal.
- **`PaintStack`** (frozen): `width`, `height` (integers 1 … `PAINT_MAX_SIZE` = 8192), `layers` (a non-empty tuple,
  bottom to top). No pixels, no defaults; `to_dict` / `from_dict` with exactly the field names.
- **`SceneObject.paint: PaintStack | None = None`** — one slot, one keyword argument (`TypeError` for anything else).

### 2.2 The base (P-4)

The layers are composited over the object's own `texture` (resampled nearest to the stack size when it differs) or, without
one, over its base colour. The base is never written. The Core does not store the flattened image: it is derived data
(§5).

### 2.3 File (`src/core/serialization.py`)

`"paint": {"width", "height", "layers": [{"name", "image", "opacity", "visible", "blend"}, …]}` on a painted object.
**Version 14** only when an object has paint (else 4–13 as before; a scene without paint is the same text — pinned on the
Gollum scene); read 2–14. Invalid (the file is refused): a `"paint"` key below 14, and every invalid stack.

### 2.4 Freeze rule (§7 of CORE_V1_FREEZE)

(1) requirement — paint layers that travel with the object through Undo / Redo, save / load, Duplicate, mirror copy,
Detach, delete / Undo and the scene reset (audit §4.3); (2) not solvable with the public API: `SceneObject` has
`__slots__`, a side table keyed by `ObjectId` would need a remap on every load and puts the object's data in two places
(AD-024 §1.2, audit D2); pixels in the Mesh / journal were rejected (audit D3); (3) the audit and this AD; (4) smallest
extension, data only — not touched: `Mesh`, `Operation`, `HistoryStack`, `Selection`, `ObjectTransform`, every existing
signature; (5) contract tests `tests/test_paint_format.py` (43).

## 3. The texel → surface map (`mirai.paint.texel_map`, Phase 1b)

Per texel of a `width` × `height` image: the drawn triangle whose UV triangle holds the texel centre and two barycentric
weights (int32 slot + 2 × float32: 48 MiB at 2048²). Rules:

- **Layout:** row 0 = v = 0 (GL / pyglet order); texel `(x, y)` centre `((x + ½)/w, (y + ½)/h)`, flat index `y·w + x`. PNGs
  are flipped once on read / write (§5). UVs outside [0, 1] are not wrapped (the UV check names such faces).
- **Triangles:** each face split exactly as the viewport draws it (`triangulate_face` on the source table's positions),
  so the weights interpolate corner UVs as the rasterizer does; a triangle without UV area holds no texel.
- **Ownership:** where UV triangles overlap (shared edges, UV overlaps) the texel belongs to the smallest key
  `(face id, index in the face's triangulation)` — independent of write order, so a patch gives exactly a rebuild.
- **Positions:** a texel's point = Σ wᵢ·pᵢ from *any* table with the mesh's ids (rest, morph mix, posed surface); a
  position change never rebuilds. **Patching** from a journal change: faces whose boundary or UVs changed, that came or
  went, or whose triangulation a moved vertex changed (only n-gons can); texels a removed triangle owned are refilled from
  every triangle whose texel box touches them. More than 25 % of the faces (and more than 64) rebuilds.
- **Measured [C]** on the Gollum head: build 0.32–0.37 s at 2048² since §7.1 (0.52–0.61 s before; reference PC 2.06 s
  before), 0.21–0.27 s at 1024²; 2,787,212 mapped texels at 2048²
  (66.5 %, the audit's number).

The map is built by whoever needs it (the Paint Room in Phase 2) and lives only there: nothing builds it in the Modeller.

## 4. The UV check (`mirai.paint.uv_health`, `uv_check_display`, Phase 1a)

Read-only. Per face: **unmapped** (the mesh has UVs, the face none), **zero area** (UV polygon area < 1e-9), **overlapping**
(a texel centre strictly inside another face's UV area, on a 1024² raster; a shared UV edge is not an overlap),
**outside** (a corner outside [0, 1]); plus the coverage, the overlap share of used texels, islands and seams, and the
texel density p5 / p50 / p95 (scales linearly with the image size). In the app: `Application.toggle_uv_check` (SPACE menu
row **„UV-Prüfung“**, shown when the edit object has UVs; no key — CLAUDE.md: keymap entries only after Manu's approval):
the status line, and the faces coloured in place of the region colours while it shows (red: no UVs / no UV area; orange:
overlapping; violet: outside 0–1; colours `PROVISIONAL`); it follows topology / UV edits and the edit-object switch; view
state only, no History. On the Gollum head [C]: 44 without UV area (ids from 5419), 148 faces touch an overlap (3.3 % of
used texels; the audit counted 44 by UV centre), 2 islands, 66.5 % of the square, density p50 ≈ 968 px / unit at 2048²,
spread ×3.4; ~0.25–0.3 s.

## 5. Pixels, Undo and files (`mirai.paint.store`, `files`, Phase 1d)

- **`PaintStore`** (`Application.paint`): per object *instance* and layer name one `(h, w, 4)` uint8 RGBA array, loaded
  from the layer's image on first use (`None` = transparent; an unreadable file loads transparent and keeps its path until
  painted). The instance is the key, so delete / Undo keeps the pixels; Duplicate, mirror copy and Detach give the copy the
  source's *current* pixels (`copy_object`; `AppServices.paint` for the controllers); a scene reset clears it. A layer
  that leaves the stack keeps its pixels (an Undo can bring it back); a new stack size starts new pixels.
- **Strokes:** `begin_stroke` → `StrokeRecorder` (captures a 64² tile the first time it is touched, zlib level 1;
  `write_box`, `write_texels`); `commit()` → one `PaintStrokeCommand` (the Core `Command` protocol; it keeps the "before"
  tiles, the first Undo captures the "after" ones — audit §8.4 item 5), `cancel()` restores every touched tile exactly
  (Esc). `PaintStackCommand` sets `SceneObject.paint` (add / remove a stack, a layer property) like
  `ObjectTextureCommand`. `take_changed` hands the changed tiles to whoever shows the composite.
- **Composite:** visible layers, Normal with opacity, over the base, for a box or the whole image (float32, rounded).
- **Save** (`files.prepare_save` in `Application.save_scene_file`, before the JSON; `PaintSave.apply` after it): a dirty
  layer → a PNG in `<stem>_textures/` under its content name (transparent → `image: None`, no file); a loaded unchanged
  layer → the file its pixels came from (so an Undo past a save is written right); a layer never loaded → its path; a
  layer file outside the folder is copied in ("Save as"). Per painted object one **flattened** RGB(A) PNG
  `<object>_paint_flat_<hash>.png` (P-4) when a layer was written or none exists; the status line names it. Paths are
  scene-relative in the file and absolute in memory (`texture_files.to_file` / `resolve`). Nothing is overwritten or
  deleted. No History step (the same pixels).
- **Reading images:** PNGs through the own decoder (`iris_import.decode_png`), other formats through `read_rgba`: pyglet's
  pure-Python PNG path took 1.8 s for the 2048² ZBrush texture in the container, the own one 0.13 s.

## 6. The live texture (`viewport.live_texture`, Phase 1c)

`LiveTexture(rgba, mipmaps)` wraps the host's array (read only) and collects marked boxes; `GLRenderStore` takes it
wherever it takes a texture path (`Material(texture=…)`, `set_texture`): the first draw uploads the whole image, later
draws only the marked boxes (`glTexSubImage2D` with unpack row length / skips), once per frame whoever draws it first.
Mip policy per texture: `"frame"` (after every upload), `"deferred"` (default: at `finish()`, a stroke's end), `"none"`.
`release()` frees the GL name. A path texture, the untextured draw and the shared texture cache are unchanged (pinned:
`tests/test_gl_texture.py`, the same image bytes with and without a live texture elsewhere; the live and file paths draw
the same picture within 1 / 255).

## 7. Measurements and the reference-PC probe (Phase 1e)

`python experiments/drag_cost/probe_paint.py [--size 1024] [--no-gl]` — P-A … P-F of the audit §8.5 on the Gollum head;
P-A uses a probe-only dab (texels of the triangles near the hit within the radius; the Phase 2 dab is not built). Container
results (llvmpipe, Xeon 2.1 GHz, NumPy 2.2.6): [`RESULTS_PAINT_CONTAINER_2026-11-18.md`](../../experiments/drag_cost/RESULTS_PAINT_CONTAINER_2026-11-18.md).
Summary [C], 2048²: room enter 0.61 s (P-D PASS); dab + composite + frame p95 10.3 / 11.7 / 21.1 / 32.5 ms at 1 / 3 / 5 /
10 % (P-A PASS at 3 % and 5 %; the dab itself 1.6 / 3.3 / 5.6 / 22 ms p95); mipmaps per frame cost ~+6 ms per frame on
llvmpipe, "deferred" pays ~5 ms once at the stroke's end (P-B: default "deferred"); live vs file texture orbit +0.66 ms p50
(P-C PASS); Modeller frame bit-identical (P-E PASS); 4-layer save 1.09 s, the second save writes nothing (P-F PASS).
Run-to-run spread in the container is about ±20 % on the frame rows.
**The reference PC decides** (×3 rule of REFERENCE_HARDWARE §4 for the CPU rows; the GPU rows are not comparable).

### 7.1 Reference PC (Manu, 2026-11-18) and the fixes

Run on the committed Phase 1 (`src/` tree `5b4e77b95e`), Core 2 Quad Q9550, GeForce 9800 GTX (GL 3.3), Python 3.12.10,
NumPy 2.2.6 — verbatim in [`RESULTS_PAINT_REFERENCE_PC_2026-11-18.md`](../../experiments/drag_cost/RESULTS_PAINT_REFERENCE_PC_2026-11-18.md).

| Probe | 2048² | 1024² | Verdict |
|---|---|---|---|
| P-D room enter | 2,061 ms | 1,418 ms | **FAIL** at 2048² (bar 2 s) → fixed below |
| P-A total p95, 1 / 3 / 5 / 10 % | 7.2 / 12.0 / 21.6 / 72.5 ms | 6.2 / 7.7 / 10.2 / 20.1 ms | **PASS** (3 % ≤ 16.7, 5 % ≤ 33); 10 % at 2048² too slow (dab 50 ms p50, one 374 ms outlier) |
| P-B mip policy, 3 % frame p50 | frame 4.7 · deferred 4.0 · none 4.1 ms | 4.2 · 3.9 · 3.8 ms | "deferred" stays the default (stroke-end frame 3.6 ms) |
| P-C orbit, live − file p50 | −0.21 ms | +0.20 ms | **PASS** |
| P-E Modeller frame | same image | same image | **PASS** |
| P-F 4-layer save | 9,370 ms | 7,388 ms | **FAIL** (bar 2 s) → worked on below; the second save writes nothing (PASS) |

Reading: the GPU side is not the limit (a frame with the live texture 3–5 ms, uploads per box are cheap on the 9800 GTX);
the CPU rows run 3.0–3.4× the container, as REFERENCE_HARDWARE §4 predicts — **except P-F**, which is 9–24× the container
and almost the same at 1024² and 2048² (half the pixels, 79 % of the time). That pattern does not fit encoding or
compositing; it fits a cost per written file (the file system or a virus scanner checking each new PNG) — **not
verified**: the probe now splits P-F into reading the base, flattening, PNG encoding and the file writes
(`texture_files.store`), so the next run names the part.

Fixes the same day (container numbers, the same probe):

- **P-D:** `raster_triangle` computes the weights as outer differences of a row and a column vector with scalar bounds
  (fewer NumPy calls per triangle), returns its texel box, and the rebuild writes only empty texels (faces come in key
  order, so no key comparison). 2048²: 0.55 → **0.32–0.37 s** (−35 %; by the ×3.4 seen here ≈ 1.2 s on the reference
  PC, within the 2 s bar). A fully vectorized raster over all triangles was tried and was *slower* (1.13 s: it computes
  every candidate texel of the boxes, ~2× the mapped texels) — not kept.
- **P-F:** the paint PNGs use zlib level 1 (`files.PNG_LEVEL`; a textured 2048² image 49 ms instead of 181 ms, ~1.6× the
  bytes) and the composite works only where a layer has alpha (its row / column span). 4-layer save at 2048²: 1.03 →
  **0.57 s** in the container. If the split shows the writes as the cost on the reference PC, the remedy is outside the
  code (a scanner exclusion for the project folder) or fewer files per save (e.g. the flattened image only on export) —
  a decision then, not now.
- The 10 % dab at 2048² (P-A) is the probe's stand-in dab; the Phase 2 dab must cap its rate or restrict its candidate
  search (audit §8.1) — a Phase 2 acceptance row.

## 8. Not in Phase 1 (next)

- **Phase 2 — built 2026-11-18, §10.** The plan as it stood (P-2, P-5, P-6, P-7, P-10 decided): the room frame (enter / leave, view state saved and restored), the
  layer-A stroke session, the paint dab (radius, opacity, flow, hardness, curve; stroke buffer; seam padding; mirrored dab),
  cursor circle, Paint / Erase / Pick, the live texture wired to `take_changed`, status-line refusals (no UVs, eye).
  **Painting on the shown SubD surface (P-10 revised, §8.1)**, which adds: (a) the texel map of the derived mesh (its
  faces and refined UVs; patched when the derived topology changes, re-read for positions only) with a build that meets
  the P-D bar on the reference PC at SubD level 2 (≤ 2 s; today 2.6 s in the container ≈ 9 s there) - a faster raster
  for many small triangles, or the derived map computed from the cage map (with linear UVs every SubD sub-face lies inside
  its cage face's UV polygon); (b) the hit, the dab centre and the cursor circle on the drawn SubD surface, not on the cage
  (AD-022 picks a never-drawn cage); (c) acceptance rows: a dab painted with SubD on stays round on SubD (out-of-round
  near 1.0 as SubD 2 → 3 in §8.1), P-A with SubD 2 on.
- **P-13 refusals, built 2026-11-18:** `Application.attach_plan` refuses (status line, nothing changed, also with "take
  the destination's look") when the destination or a source is painted and they do not share that paint —
  `PaintStore.same_paint`: equal stacks and, where pixels are in memory, equal pixels (a detached part painted on its own
  has the same stack and other pixels); `apply_goz_return` refuses an in-place return that changes a painted object's UVs
  (`plan.uvs`). Tests: `tests/test_attach.py`, `tests/test_goz_bridge.py`. The "shown and skipped" part of P-13 is the UV
  check (§4) and, in Phase 2, the dab skipping those faces.
- Eyes (P-14), undo budget (P-11). UV transfer, several layers in the UI and blend modes (P-12): built in Phase 3, §11.

### 8.1 What P-10 means once SubD is switched on (measured 2026-11-18, Manu's question)

Paint lives in UV space. SubD refines the UVs **linearly** (`refine_face_uvs`, AD-026 §6) while it smooths and moves the
positions, so a UV point painted on the cage lands at a somewhat different place, and a round dab at a somewhat different
shape, on the smooth surface. Measured [C] on the Gollum head (1024² map, the same texels on the cage and on SubD level 2;
script in the session scratchpad, not committed):

| | cage → SubD 2 | SubD 1 → SubD 2 | SubD 2 → SubD 3 |
|---|---|---|---|
| a 3 % dab's size, p50 | 0.996 | 0.998 | 1.000 |
| out-of-round (longest / shortest radius), p50 / p95 | **1.23 / 1.71** | 1.07 / 1.19 | 1.02 / 1.06 |
| point shift, p50 / p95 / max (% of the bounding radius) | 0.37 / 1.39 / 4.6 (≈ 2.6 / 10 / 33 texels at 2048², p50 density) | | |

Reading: painting on the cage with SubD off and looking with SubD on gives **no change in size but a visible
distortion**: a round dab is typically 1.2 : 1 oval, in the worst 5 % 1.7 : 1, and a painted line moves by a few texels,
up to ~10 at p95 (lid rims, lip lines). Painting on SubD level 1 already removes most of it (1.07). The ZBrush texture
shows the same distortion on SubD today (the same mapping). Painting **on the SubD surface** needs the texel map of the
derived mesh: level 2 = 36,008 faces, build 2.6 s at 2048² in the container (≈ 9 s on the reference PC by the ×3.4 seen
in §7.1), level 1 0.8 s — the per-triangle raster must become faster for that (the batched raster tried in §7.1 costs about
the same for many small triangles as for few large ones), and hits / cursor must use the drawn surface instead of the cage
(today picking reads the cage, AD-022). **Decided:** paint on the shown SubD surface in Phase 2 (Manu, „P-10 Option 1“).

## 9. Tests

`tests/test_paint_format.py` (Core values, v14), `test_paint_texel_map.py` (barycentric parity with the drawn triangles and
with `face_hit`'s `triangle_origin`, deformation invariance, patch == rebuild over 12 random topology / UV / rollback
sequences, ownership), `test_paint_uv_health.py` (each problem kind, islands / seams, density, the Gollum numbers),
`test_paint_store.py` (strokes, Undo / Redo, Esc, composite, copies, save / load round trip, Undo past a save, missing and
wrong-size images), `test_application_uv_check.py`, `test_live_texture.py`, `test_gl_texture.py` (live texture: shows,
box-only upload per policy, same as the file path, path draw unchanged), `test_gui_menus.py` (the SPACE row),
`experiments/drag_cost/tests/test_probe_paint.py`. Phase 2 (§10): `test_paint_brush.py` (curves = the Soft curves, falloff,
blend / erase, opacity vs flow, the mirror's shared texels, Esc exact; the hit against brute force on the head, the
footprint against brute force, facing, a dab across a UV seam, seam padding, **the SubD roundness row**),
`test_paint_room.py` (enter / leave restores, refusals, one Undo step with the new stack, Esc, the room's input, Pick, the
mirrored dab, the live texture re-composites only changed tiles, SubD on paints on the SubD surface, saving in the room,
the edit object changing, the panel model / SPACE row), `test_paint_texel_map.py` (+3: batched build == per-face build on
the head's cage and SubD 1, large / concave / unmapped faces), `test_gui_imgui_window.py` (+1: the room in the real
window - panel, a stroke through window events, box uploads of the live texture, GL state as found),
`test_interaction_structure.py` (the new fields and commands registered). Phase 3 (§11): `test_paint_layers.py`
(Multiply arithmetic, merge == the two layers for both blends, every layer step one Undo step with exact Undo / Redo,
refusals, a reused name starts transparent, the active / hidden layer, the slider preview, the display's partial
re-composite == a whole composite with no whole composite made, save / load of three layers with their blends, the panel
model), `test_paint_uv_transfer.py` (unchanged faces bit for bit, swapped UV squares carry their paint exactly, a face
without old UVs gets none, every layer moves and Undo / Redo are exact, a smaller square reads bilinearly and is padded),
`test_goz_bridge.py::test_a_uv_change_on_a_painted_object_moves_its_paint` (UV Master on the Gollum head: one Undo step,
a colour of the surface point stays at that point - median ≤ 2/255, p95 ≤ 8/255 - Undo / Redo exact; replaces the P-13
refusal test), `test_gui_imgui_window.py` (the layer list draws in the real window), `test_paint_format.py` (the blend
values).

Full default run after Phase 3 (2026-11-19, container, `xvfb-run -a python -m pytest`): 7,780 passed, 8 skipped, and
`test_scene_menu_local_tmp.py::test_probe_menu_wiring` failing as on the base commit `cb11ebe` (checked there; not caused
by this change).

Full default run in the container (2026-11-18, `xvfb-run -a python -m pytest`): 7,707 passed, 8 skipped, 1 failed —
`tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring`, which fails the same way on the base commit `25154ac`
(not caused by this change).

## 10. Phase 2 — the Paint Room (built 2026-11-18)

Built on `claude/admiring-curie-5z3s6a` @ `c970d57`. Everything here is `PROVISIONAL` (agent-set) unless a decision of §1
names it; no key and no `config/keymap.json` entry (CLAUDE.md, P-6).

### 10.1 The room frame (P-2) — `Application.open_paint_room` / `close_paint_room`, `controllers.paint_room`

- **Entry:** the SPACE menu row „Paint Room öffnen“ / „… schließen“ (`gui.paint_model.menu_label`: shown with UVs and not on
  an eye), the panel's close box and „Schließen“. **Refused** with a status line (`paint_room_refusal`): an eye (P-14), no
  UVs, another interaction running, a morph target's editing view (P-8 decided 2026-11-25: **a pose and a morph mix are both allowed**).
  A **morph mix above 0 %** is allowed on entry (Manu 2026-11-25: „Es muss also erlaubt sein,
  bei aktiviertem Target in den Paint Room zu wechseln“) - the room already painted on a mix dialled in inside it (the
  texel map reads any `SurfacePositions`), so entering with one is the same state.
- **View state** saved on entry and restored on leaving (`PaintRoomController.saved_view`): display mode → Shaded, wire
  overlay off, textures on, region colours off; the camera, SubD, the light and the UV check stay as they are. A save in the
  room writes the restored values into the scene's `"view"`, not the room's. Nothing is document state: no Undo step.
- **The session:** one exclusive session in the slot (`PaintRoomSession`, `interaction_owner` "paint", like the Knife).
  Its `allows`: Cancel, Undo / Redo, Ortho, display / Look rows, the SubD keys (P-10: the room paints on what is shown;
  `_subd_command` lets them through between strokes), Shift+S (`SymmetryController.cycle` accepts the owner "paint") and
  the Soft radius wheel; everything else is refused silently (W/E/R, modes, topology, Add object ...). While a stroke runs
  also Undo / Redo, Shift+S and the SubD keys are refused. Ctrl+S / SPACE are window commands and work between strokes
  (`save_scene_file` lets the owner "paint" through when no stroke runs).
- **Ends** with its object: a scene reset closes it, and a changed edit object (an Undo that carries it) closes it at the
  next frame with a status line.

### 10.2 Input (P-6 concept; code defaults only)

Plain LMB press / drag / release paints (the session takes the press itself: no binding, so nothing for the keymap yet);
Alt+LMB orbit / Alt+Shift+LMB pan go to the pointer resolver as before; Shift+wheel steps the brush radius (the Soft
radius binding, read by the session); **Alt+wheel** steps the opacity (`commands.PAINT_OPACITY_UP` / `DOWN`, the new
`paint` binding context, free in `config/keymap.json` and every context); the plain wheel zooms; Esc cancels the running
stroke exactly (no History step; the rest of that press paints nothing). The panel (`gui.paint_panel`, left like the Eye
Lab): Malen / Radieren / Pipette, colour (`color_edit3`), radius (steps `brush.RADIUS_STEPS_PERCENT`, 0.5 … 15 %, start
3 %), opacity, flow, hardness, curve (the Soft curves: smooth, sphere, root, sharp, linear), mirror (shown when the mesh has
a symmetry plane), the resolution of a new stack (2048² / 1024², P-5) until the first stroke.

### 10.3 The shown surface (P-10 revised) — `mirai.paint.surface.PaintSurface`

- **Which:** the SubD preview's derived mesh while SubD shows (`SubdivisionPreview.active`; its faces and linearly refined
  UVs), else the edit mesh; built on first use per (mesh, size) and kept while the room is open, so switching SubD in the
  room builds each surface once. **Measured fact:** the preview caps the derived mesh at `MAX_DERIVED_FACES` = 25,000
  (`PROVISIONAL`, SubD README), so on the Gollum head (level 2 = 36,008 faces) it shows **level 1** (9,002 faces) and the
  room paints on level 1; level 2 is measured for the record (§10.7).
- **Hit:** the nearest ray hit (Möller-Trumbore, `_EPS` of `picking._ray_triangle_intersection`) on the drawn triangles -
  every face's triangulation, those without texels included (they occlude), hidden faces left out - culled by boxes over
  runs of 64 triangles (`_Clusters`). The ray is the edit camera's (`edit_camera.screen_to_ray`, object space): the hit,
  the footprint and the cursor circle lie on the drawn surface, not on the cage AD-022 picks (§8 (b)).
- **Footprint** (audit principle 3): the mapped texels whose surface point lies within the world radius, on triangles
  whose normal is within 90° of the hit's (`FACING_MIN` = 0: the other side of a lid or a lip is not painted through). A
  texel's surface point is computed once per triangle at its first dab (float32, reset when positions change), so a dab
  gathers instead of interpolating. A dab crosses UV seams (texels of both islands by their 3D position).
- **Mirror** (audit §5.2): with Mirror on and a symmetry plane on the mesh, a second footprint at the hit reflected across
  the plane (object space; the derived mesh shares it); a texel in both counts once with the larger coverage. The cursor
  shows the mirror's circle dimmed. P-9 (mirror in a pose) does not arise: the room refuses poses (§10.1).
- **Faces without usable UVs** (P-13 "shown and skipped"): they hold no texel, the dab skips them, the status line counts
  them on entry (the Gollum cage: 45; SubD 1: 204 derived faces) and a press on one says so.

### 10.4 The stroke and the dab — `mirai.paint.brush`, `PaintRoomController.begin / step / end`

- Dabs are spaced `SPACING` = 0.25 of the brush radius on screen; at most `MAX_DABS_PER_EVENT` = 24 per drag event, the
  last sample always (audit §8.1). **Replaced in Phase 4a** (§12.3): world arc-length spacing and the stamp queue. The falloff: full inside the hardness plateau, then the chosen Soft curve to 0 at the
  radius.
- **Stroke buffer** (principle 4): per texel `S ← S + (1 − S) · flow · falloff`; the layer shows the stroke's start pixels
  with the colour at `opacity · S` (Normal, straight alpha, 8 bit) - opacity caps one stroke and does not build up inside
  it, flow does. Erase lowers alpha the same way. Phase 2 paints the top layer of the stack.
- **Release:** the seams of the touched tiles are padded (principle 5, `seam_pad`: unmapped texels up to `pad_width` = 4 at
  2048² / 2 at 1024² take the nearest island texel, 8-neighbour dilation, fixed order), then **one History step**. The
  first stroke on an unpainted object also makes the stack (`PaintStackCommand`, one `CompositeCommand` with the stroke):
  Undo leaves the object unpainted (the scene saves as before, v13 or lower), Redo brings the same pixels. A stroke that
  touched nothing makes no stack.
- **Pick:** the composite's colour (base + layers: the albedo, not the lit frame) at the hit's own nearest texel (the UV
  square of a point on an island border can belong to another island); then the previous tool again.

### 10.5 What painted objects show — `mirai.paint.display.PaintDisplay`

Per painted object the composite (base + visible layers, P-4) as a `LiveTexture`, shown by `ObjectsController._shown_texture`
in place of the texture path - in the room and in the Modeller. `Application.update_viewport` re-composites the tiles
`PaintStore.take_changed` reports, once per frame; the live texture uploads only those boxes and regenerates its mipmaps
with each upload ("frame", since Manu's first test, §10.9; P-B had chosen "deferred"). A changed stack value, texture or material re-composites the whole image; an object without paint is
drawn exactly as before (P-E). The highlight signature carries `obj.paint`, so a stack that comes or goes (first stroke,
Undo) reaches the viewport at the next frame.

### 10.6 The texel map build, batched (§8 (a))

`TexelMap.rebuild` no longer loops per triangle: triangles and convex quads are split in arrays (`_convex_quads`: the
same Newell normal, axes and corner test as `triangulate_face`, the same float operations in the same order), every
triangle is rasterized row by row (`_raster_scan`: the inside span of each row solved, widened by one texel, then tested
with `raster_triangle`'s expressions), and every texel goes to its smallest key in one `np.minimum.at` pass over slots
handed out in key order. `raster_triangle` now steps from its box start by integers (`(x0 - ax) + arange`), so both paths
compute bit-identical values; **pinned:** batched == per-face build on the head's cage and SubD 1 (texels, weights,
boxes, triangulations), and the 12 random patch == rebuild sequences of Phase 1 still pass. A batched raster over boxes
(Phase 1's attempt, and a first Phase 2 version) computed 1.8-4× the inside texels; a thread pool over batches was slower
in the container (memory-bound) - neither kept.

### 10.7 Measurements [C] (container: Xeon 2.1 GHz, Python 3.13, NumPy 2.2.6, llvmpipe; best of 3 / the probe)

| Room enter (P-D), 2048² | faces | texel map | + tables = surface | RPC estimate ×3–3.4 [H] |
|---|---:|---:|---:|---|
| cage | 2,234 | 0.40–0.43 s (Phase 1: 0.32–0.37 s per triangle) | 0.51–0.64 s | ≈ 1.6–2.2 s |
| SubD 1 (what the head shows) | 9,002 | 0.47–0.53 s (per triangle: 0.73–0.80 s) | 0.59–0.69 s | ≈ 1.8–2.3 s |
| SubD 2 | 36,008 | 0.73–0.84 s (per triangle: 2.3–2.8 s) | 0.92–1.11 s | ≈ 2.8–3.8 s |

At 1024² every row is 0.15–0.5 s. The batched map is slightly *slower* than Phase 1's per-triangle build on the cage
(few large triangles) and 1.5-3.4× faster on SubD; **P-D on SubD 1 at 2048² is the row the reference PC decides** (bar
2 s; the 1024² option is the fallback, P-5).

The dab (P-A CPU rows, the real Phase 2 dab incl. the hit and the mirror, ~2× the texels of Phase 1's probe dab; 2048²,
p50, [`RESULTS_PAINT_PHASE2_CONTAINER_2026-11-18.md`](../../experiments/drag_cost/RESULTS_PAINT_PHASE2_CONTAINER_2026-11-18.md)):
1 % 1.7–2.4 ms, 3 % 2.6–3.3 ms, 5 % 4.3–5.1 ms, 10 % 11.4–12.6 ms on every surface (the footprint does not depend on the
face count once culled; two optimizations of this slice: the tiles of a write in one NumPy pass, texel points computed
once per triangle); the composite of the touched tiles 0.3–2.9 ms. Frame rows on llvmpipe (6 ms cage, 9–11 ms SubD 1,
22–24 ms SubD 2 for a software rasterizer; they fail the SubD 2 rows here) are not comparable to the 9800 GTX (§7.1:
3–5 ms). P-F 0.50 s; P-C −0.05 ms; P-E same image. **Not measured on
the reference PC yet** — `python experiments/drag_cost/probe_paint.py` (now with `--surfaces cage,subd1,subd2`) is the
run that decides P-A with SubD on (§8 (c)) and P-D on SubD 1.

### 10.8a Manu's first observations (2026-11-18, reference PC) and the fixes

Manu, verbatim: „Erster Tupfer dauert ca 7 Sekunden bis er erscheint bei 2048. Im Panel lässt sich nichts bedienen. Alt+
Scroll funktioniert nicht (zoomt nur). Live(Preview?) malen bevor man die Maustaste wieder loslässt, wird, je steiler der
Winkel ist, weniger sichtbar, erst nachdem loslassen sieht man dann die volle Opazität. Malraum lässt sich nicht
schließen, wahrscheinlich weil die Panel Bedienung nicht funktioniert.“

| Observation | Cause [V] | Fix |
|---|---|---|
| Panel not usable, room cannot be closed | `ImguiLayer._gesture_running` gave the mouse to the app while any interaction owner other than the bone chain ran - the room's session is one, so its panel *and* the SPACE menu got no mouse | `PANEL_USABLE_OWNERS` includes "paint"; a running stroke (`app.paint_stroking`) still keeps the mouse |
| Alt+wheel only zooms | pyglet's scroll event has no modifiers; `main.wheel_input` added Shift and Ctrl only | `wheel_input(..., alt_held)`; outside the room an unbound Alt+wheel is read without Alt (zoom, as before) |
| Paint fades with a steep view until the release | the live texture's mip policy "deferred": minified levels stayed the old image during the stroke | `display.MIPMAPS` = "frame" (P-B on the reference PC: 4.7 against 4.0 ms per frame at 3 %) |
| First dab ~7 s at 2048² | not reproduced: in the container the first stroke costs 0.16 s CPU and 0.31 s for its frame (Gollum, real window); its only file access is reading the ZBrush texture as the base - the pattern of P-F's 7-9 s (a cost per file access, §7.1, unverified) | the base is read and the composite shown **when the room opens** (`PaintDisplay.prepare`); the first stroke makes no whole-image composite (pinned). The status line on entry names the base read and the composite time, so the reference PC shows where the time goes |

### 10.8b The reference-PC run of Phase 2 (Manu, 2026-11-18) and the fixes

Verbatim in [`RESULTS_PAINT_PHASE2_REFERENCE_PC_2026-11-18.md`](../../experiments/drag_cost/RESULTS_PAINT_PHASE2_REFERENCE_PC_2026-11-18.md).

| Probe | Reference PC | Verdict / action |
|---|---|---|
| P-D room enter, 2048² | cage 1.90 s, SubD 1 2.26 s, SubD 2 3.44 s (3.0-3.6× the container) | cage PASS, SubD 1 / 2 FAIL → the footprint table now comes grouped by slot from the build (`TexelMap.slot_order`; no sort of 2.8 M texels): container 0.35 / 0.44 / 0.74 s (was 0.63 / 0.63 / 1.11) ≈ 1.2 / 1.5 / 2.5 s there [H]; re-run open |
| P-A total p95 at 3 % / 5 % | cage 13.3 / 21.2, SubD 1 15.7 / 22.9, SubD 2 21.2 / 28.1 ms | PASS except SubD 2 at 3 % (its frame: 10.5 ms for 72k triangles); SubD 2 is not shown on the head (25,000-face cap) |
| P-B "frame" vs "deferred" | 4.41 vs 4.27 ms p50 | "frame" (§10.8a) costs 0.14 ms per frame |
| P-C / P-E | −0.07 ms / same image | PASS |
| P-F first save | 7.79 s, of it **read base 6.35 s**, file writes 12 ms | the cause of the ~7 s first dab as well: reading the 2048² ZBrush texture (container 0.04 s). Not a per-file write cost (§7.1's guess is ruled out for writes). The decoded image is now cached per session (`files.read_image`), the probe prints the read split (P-G: file read, decode, decoder, the PNG's row filters) |

**Open:** why one read of that PNG takes 6.35 s there. The repo's file is stored without row filters (container decode
0.05 s through the own decoder); 6.35 s fits the system decoder (pyglet's pure-Python PNG path took 1.8 s in the container,
×3.4) or a slow first file read. P-G on the reference PC names which.

### 10.8c The second reference-PC run (Manu, 2026-11-18): the slow read found

P-G names it [V]: the reference PC's `Gollum_cbf9c7702d.png` is **another file than the repo's** of that name (470,628
bytes, RGBA, row filters Sub / Up / **Paeth** on 998 rows; the repo's is 423,554 bytes, RGB, unfiltered), and
`iris_import._unfilter` reconstructs Average / Paeth rows byte by byte in Python: decode 6,510 ms, the file read 1 ms. That
was the ~7 s first dab and P-F's 6.4-9.4 s (also in Phase 1: §7.1's "cost per file" guess is ruled out). **Fix:**
`decode_png(..., slow=False)` refuses such a PNG (`SlowPNG`) and `files.read_image` takes the system decoder first
(`iris_import.read_rgba`: pyglet, WIC on Windows), the own decoder only behind it; the result is cached per session.
Pinned: a Paeth PNG reads the same pixels by either path (`test_paint_store.py`). Whether WIC is fast there: the next P-G.
Where the file came from (Manu, 2026-11-18): „die Datei wurde zwischendurch in Gimp bearbeitet“ - GIMP's PNG export
(libpng, the default settings) chooses a filter per row and keeps the layer's alpha channel; ZBrush had written the
texture unfiltered RGB. Any texture can come that way, so the fast path for filtered PNGs is a permanent need, not a
workaround for one file. The session cache keys on the file's modification time and size, so a texture re-exported under
its name is read again.

P-D: cage 1.65 s PASS, SubD 1 2.02 s (22 ms over the bar), SubD 2 3.51 s. The probe now splits P-D (map split / raster /
ownership, tables; container: 12 / 222 / 123 / 25 ms on the cage) so the next run names the part to work on; 1024² stays
the fast option (P-5). P-A's CPU rows pass on every surface at 3 % and 5 %.

### 10.8d The third reference-PC run (Manu, 2026-11-18): the conversion, and the raster's cache

The system decoder (pyglet, WIC) took 5.09 s too [V]: not the decode - pyglet's `ImageData.get_data("RGBA")` reorders
the decoder's bytes (WIC: BGRA) with a regular expression (container: 0.49 s decode, 1.1 s for that conversion of an RGB
2048² image). **Fix:** `iris_import._rgba_of` takes the pixels in the decoder's own format and pitch and reorders them with
NumPy (0.02 s in the container; pinned for RGBA / BGRA / RGB / BGR / L and both row directions; an image without alpha is
now opaque - pyglet's conversion copied R into alpha, which also made `has_alpha` true for an RGB iris photo read that way).
In the app the session cache worked as intended: „Basisbild gelesen 4.55 s“ at the first opening, 0.00 s at the second.

P-D now passes on the cage (1.72 s) and SubD 1 (1.92 s); SubD 2 3.11 s. The split: the raster ran at 5.5× the container
(1,230 against 222 ms; everything else 3-4×) - its chunks of 1 << 20 candidates (~80 MiB of arrays) far exceed the
Q9550's 6 MiB L2. **Fix:** chunks of 1 << 16 (container: raster 275 → 162 ms on the cage, 269 → 180 ms on SubD 1, the same
texels and weights). Both need the next reference-PC run.

### 10.8e The fourth reference-PC run (Manu, 2026-11-18): every bar of the shown surfaces met

Manu: „öffnet sich jetzt wesentlich schneller, der Raum, auch der erste Strich“. Measured there: P-G 0.99 s (the WIC decode
of the Paeth-filtered texture; was 6.5 s), **P-F 1.76 s PASS** (was 7.8 s), **P-D cage 1.40 s, SubD 1 1.47 s PASS** (raster
0.79 / 0.72 s, was 1.23 s), SubD 2 2.50 s (not shown on the head: the 25,000-face cap), P-A passes everywhere at 3 % and
5 % (total p95 9–11 / 15–17 ms). With the GL rows of the first run (frame 4–6 ms on the cage and SubD 1) every Phase 2 bar
on the surfaces the app shows is met on the reference PC. Open: the 10 % dab (31–32 ms p50, above a frame), SubD 2's room
enter - neither blocks.

### 10.8 Not in Phase 2

Several layers in the UI (only the top layer is painted; the stack format has several), blend modes (P-12), the undo
budget (P-11: before-tiles only, compressed, unlimited), painting a posed / morphed surface (P-8: allowed since 2026-11-25), eyes (P-14,
refused), UV transfer (Phase 3; a GoZ UV change stays refused, P-13), smudge / blur / clone, lazy mouse, pressure (P-15:
none), symmetry in a pose (P-9), a depth window for thin gaps beyond the facing test, a key for the room or the tools
(after Manu's "Taste passt").

## 11. Phase 3 — several layers, Multiply, the UV transfer (built 2026-11-19)

Built on `claude/magical-cray-u17tpf` @ `cb11ebe`. Scope and P-12: Manu, 2026-11-19 (§1). Everything not named by a decision is
`PROVISIONAL` (agent-set); still no key and no keymap entry.

### 11.1 Blend modes (P-12) — `core.scene.PAINT_BLEND_MODES`, `PaintStore.composite`

`PAINT_BLEND_MODES` = ("normal", "multiply") (CORE_V1_FREEZE §7.1, 2026-11-19 addendum: one more allowed value of an
existing field; the format stays v14 - a build that knows only "normal" refuses a file naming "multiply" with the
validation error, as Phase 1 planned). The composite, bottom to top with straight alpha `a` = pixel alpha × layer
opacity: Normal `t + (c − t)·a`, Multiply `t + (t·c/255 − t)·a` (white changes nothing, the base and every layer beneath are
darkened). Colour stays display-referred 8 bit (P-16 open).

### 11.2 Layers — `mirai.paint.layers`, `PaintLayersCommand`, `PaintRoomController.layer_step`, the panel

- **Operations** (each one History step; refused with a status line while a stroke runs, outside the room and before the
  first stroke makes the stack): add a transparent layer above the active one ("Ebene N", the first free N; at most
  `MAX_LAYERS` = 8, `PROVISIONAL`: 16 MiB each at 2048²), delete (not the only layer - "Leeren" clears it), rename (unique,
  non-empty, trimmed), move one place up / down, opacity / visibility / blend, merge down, clear.
- **The step.** A change of values or order is a `PaintStackCommand` (the stack value only). A change of pixels or of
  which layers exist is a `PaintLayersCommand`: the stack value and, per named layer, a compressed snapshot of its pixels
  (or none: the layer's image file / a new transparent layer); Undo and Redo put the snapshots back. The pixels of a
  deleted layer leave the store into the step, so a name used again (a new "Ebene 2" after deleting one) never finds the
  deleted layer's pixels - which the Phase 1 rule "pixels of a layer that left the stack stay" would have shown.
- **Merge down**: into the layer beneath, both visible and with the same blend (Normal into Multiply cannot be one layer;
  refused). The result keeps the lower layer's name and has opacity 1 with both opacities baked in: Normal = Porter-Duff
  "over"; Multiply = the product of the two per-channel factors `1 − a + a·c`, written with the smallest alpha that holds it.
  The composite stays equal up to the 8-bit rounding (pinned ≤ 1-2 / 255). Computed only where either layer has alpha.
- **The active layer** (view state, `PaintRoomController.active`): the strokes paint on it; it falls back to the top
  layer when it leaves the stack (an Undo). A hidden active layer is not painted (status line). Pick still reads the
  composite.
- **The panel** (`gui.paint_panel`, section „Ebenen“, top layer first): visibility checkbox, the name as a selectable row
  (opacity and a non-Normal blend in the label), then for the active layer: name field (applied on Enter / leaving the
  field), "Ebenen-Deckkraft" (previewed while held - `Application.preview_paint_layer`, no step - one step on release from
  the value before the preview; closing the room ends a preview), "Mischmodus", buttons Neu / Hoch / Runter /
  Zusammenführen / Leeren / Löschen (greyed where refused). All labels and the layout `PROVISIONAL`.
- **The display** (`PaintDisplay`): a new stack value of the same size over the same base re-composites only the tiles
  where the composite differed from the base before (`_Entry.nonbase`) or a visible layer has paint now; everything else
  is the base on both sides. Pinned equal to a whole composite after value / order / delete / Undo / Redo steps.
  **The held slider (Manu, 2026-11-19, after the first try: „ja, der Slider ist recht langsam“):** when only one layer's
  opacity, visibility or blend differs, only that layer's painted tiles are re-composited, in one array pass, from a
  cache of what lies beneath it there (base + lower layers, kept while the slider is held; dropped when any pixels
  change) plus the layers above; bit-identical to a whole composite (pinned, both blends). Changed tiles are uploaded as
  one box per run of neighbouring tiles in a row instead of one GL call per tile.
- **Save / load** needed no change: every layer is written as its PNG (a transparent one without a file), `blend` is in
  the stack value, the flattened PNG composites every visible layer with its blend.

### 11.3 The UV transfer — `mirai.paint.uv_transfer`, `Application.apply_goz_return`

When a ZBrush return changes UVs of a painted object (same topology; `plan.uvs`), every layer (hidden ones too) is
re-sampled onto the new UVs before the mesh changes, and the result joins the return's Undo step (a companion of
`_mesh_transaction`, with the texture step when there is one). The texel map of the mesh **as it will be** (new UVs and
positions over the old topology, read through an adapter - nothing is changed for the build) gives every texel of a
changed face its triangle and weights; the same weights over the triangle's old corner UVs give the old UV point. The
topology is the same, so each new UV triangle maps affinely onto its old one (audit §5.3). Texels of faces with unchanged
UVs are copied bit for bit; texels of changed faces are read bilinearly with premultiplied alpha (only reads that touch
paint are computed); a face that had no UVs, or old UVs outside 0-1, gives transparent texels; the result is seam-padded
where it has paint. A transfer that fails refuses the return (status line, nothing changed). The status line names the
moved layers and texels. Attach of differently painted objects stays refused (P-13).

**The object's texture moves too (Manu, 2026-11-19, the first UV Master return on the reference PC: „Neu abgewickeltes Mesh
aus Zbrush zurück in Mirai dauert ca 5-6 Sekunden (gefühlt nicht gemessen). Die Textur wirkt allerdings verschoben“).**
Cause [V]: the object's own texture - the base beneath the paint (P-4) - is laid out for the old UVs, and UV Master does
not re-lay a ZBrush texture map; the paint moved, the base did not, so the composite showed the base shifted under it (an
unpainted textured object showed the same since WP_GOZ_P3). Now a return that changes UVs **and brings no new texture**
re-samples the object's texture onto the new UVs as well (`uv_transfer.transfer_texture`: the same plan, plain bilinear
for the opaque image, texels the new layout does not map keep their old pixels, seam-padded), writes it as a new PNG
beside the old one (`<stem>_uv_<hash>.png`; the old file is never written - P-4 holds for the file) and shows it - an
`ObjectTextureCommand` in the same Undo step. The status line names what moved and the seconds it took.
**Revised the same day** (Manu, after the next try: „ja, komplett verschoben. Ist es nicht so gedacht, dass die alte
Textur auf die neuen UV´s projeziert wird?“): the first rule took a texture the return brings as it is - but ZBrush sends
its own texture map with every return (the tool keeps it), still in the old layout, under another name than the
object's (GIMP-edited) texture, so that rule showed ZBrush's old-layout image. Now, with new UVs, **the texture the object
shows is always projected onto them** and a texture ZBrush sends with the UV change is not taken (status line: "ZBrush's
texture not taken (laid out for the old UVs)"). An object without a texture still takes ZBrush's. Not covered: a texture
made in ZBrush for the new UVs (e.g. from Polypaint after the unwrap) - it would have to be returned without a UV change,
or a choice added; open until Manu needs it.

**The new UVs did not reach the viewport (Manu, 2026-11-19, the third try, verbatim: „das Problem scheint zu sein, dass
die neuen UV´s nicht in Mirai ankommen“; status line „no point moved, UVs changed (UVs: 2492 faces changed) - 2 paint
layers moved to the new UVs (7.3 s) - applied“).** Cause [V], older than Phase 3 (WP_GOZ_P3 P3a): `_mesh_transaction`
called a delta without vertices, edges or faces "layer-only" (AD-025: nothing drawn changed) - it did not look at
`face_uvs` - so a UV-only return told the viewport "these points moved: none" and the drawn UVs stayed the old ones
until the next topology change; its Undo / Redo were recorded as a non-mesh step, too. The paint had moved to the new
UVs and was drawn on the old ones: it looked as if the UVs had not arrived. Fixed: a delta with `face_uvs` is not
layer-only, and a return that changes UVs or groups reports a topology change (`moved_of` → None). Pinned:
`test_goz_bridge.py::test_a_uv_only_return_reaches_the_viewport` (apply and Undo re-read the faces). The 7.3 s on the
reference PC (two layers, no texture) are the transfer; the container measures ≈ 2 s for the same work (§11.4).

**Speed (Manu, 2026-11-19: „ja, beschleunige die Übernahme bitte“).** The same work on `Gollum_Head_05`'s painted object
(2,492 faces, two 2048² layers) takes 0.87 s in the container - the reference PC's 7.3 s are ≈ 8×, not the usual 3×,
the pattern of the texel map's raster before its fix (§10.8d: arrays far larger than the Q9550's 6 MiB L2). The plan's
old-UV points and the bilinear read now run in pieces of `uv_transfer.CHUNK` = 65,536 texels (the raster's step; the
gathered corner UVs alone were ≈ 100 MiB at once) and the read's paint mask and opacity test are made once per layer:
container 0.87 → 0.76 s. The reference PC decides; the status line now names the split ("… (7.3 s: map …, texture …,
layers …)") so the next run shows the part to work on.
Reference PC after that (Manu, verbatim): „… 2 paint layers moved to the new UVs (6.0 s: map 2.6, layers 3.3)“ (7.3 s
before). Container for the same: map 0.24, layers ≈ 0.5 s - map ≈ 11×, layers ≈ 6.6×. Second step: the plan's two
sorts over 2.8 M entries (`np.isin`, `np.unique`) are table lookups now; a layer equal to its file holds no compressed
copy in the step (its Undo reads the file again), and the moved pixels go in uncompressed (`store.LivePixels`), frozen
into a `LayerSnapshot` only by the step's first Undo - the four zlib passes over 16 MiB per two layers are gone from the
return. Container 0.87 → 0.63 s for loaded layers. Pinned: `test_paint_uv_transfer.py::test_a_saved_layer_is_not_copied_and_its_undo_reads_the_file`.
Reference PC after that: „(5.6 s: map 2.2, layers 3.5)“ - little changed, so the guesses stopped and the probe
`experiments/drag_cost/probe_uv_transfer.py` ran there (Manu, 2026-11-19, with ZBrush open and closed - **no
difference**: not memory pressure). Its split per 2048² layer [V]: the bilinear read 0.66-0.76 s (nearest: 0.12 s - the
read is arithmetic, not memory: in source-texel order it is *slower*, 0.88-0.93 s), the seam padding 0.25-0.28 s (one
small window per tile), the plan's Python step per triangle 0.4-0.55 s (more than the texel map, 0.49-0.58 s); 3-5x the
container, the usual ratio - the app's 5.6 s move ≈ 2x the probe's 1-1.3 M texels. Third step, built on these numbers:
the four neighbours and weights of every moved texel are computed once in the plan (`_taps`, int16 / float32) instead
of once per layer, the read gathers a pixel as one 32-bit value and keeps alpha in 0-255 units (`_read`); the seam
padding gets one window per run of tiles in a tile row (`_row_boxes`); the old corner UVs come from one pass over the
faces and a sorted lookup instead of a Python step per triangle; the plan's and the read's pieces run in a thread pool
(`THREADS` = 4; NumPy releases the GIL; the Q9550 has 4 cores). Same pixels (≤ 1/255 rounding). Container, plan + both
layers of `Gollum_Head_05`'s object: 0.52 → 0.34 s (re-unwrap-like layout), 0.72 → 0.44 s (fully transposed layout).
The reference PC decided (Manu, 2026-11-19): the app „(4.2 s: map 2.0, layers 2.2)“ (7.3 → 6.0 → 5.6 → 4.2 s); the probe:
plan 0.82 / 0.95 s, layer 1 0.59 / 0.99 s (read 0.51 / 0.53 s, seam pad 0.25 / 0.29 s), layer 2 0.09 s. **Kept as it is**
(Manu, verbatim): „Etwas besser geworden … Wir lassen das erstmal so. Der PC ist auch einfach uralt, da muss man ein paar
Sekunden Wartezeit in Kauf nehmen. Wichtiger ist, dass es funktioniert“. What is left, should it matter later: the texel
map of the new layout (≈ 0.5 s there) and the seam padding of a large layer (≈ 0.25-0.3 s, still a window per tile row). Pinned:
`test_goz_bridge.py::test_a_uv_change_moves_the_objects_own_texture_too` (a colour of the surface point stays at that
point, median ≤ 2/255; the old file unchanged; Undo / Redo switch the texture) and
`::test_a_uv_change_projects_the_shown_texture_and_not_the_one_zbrush_sends`.

### 11.4 Measurements [C] (container, Gollum head at 2048², paint in 30 % / 15 % of the image; best of 2)

| | container | RPC estimate ×3–3.4 [H] |
|---|---:|---:|
| add a layer (+ show) | 0.13–0.15 s | ≈ 0.5 s |
| opacity preview, one frame - first build (re-composite of every painted tile) | 0.06–0.08 s (first 0.13 s) | ≈ 0.2–0.3 s |
| opacity preview, one frame - after the slider fix (one layer's tiles, cached beneath; paint in 60 % / 25 %) | 7–8 ms (first frame of a hold 28–34 ms; 122 → 19–20 ms in the heavier slider probe) | ≈ 25–70 ms [H] |
| the same as a whole composite (before this slice) | 0.17–0.24 s | ≈ 0.6–0.8 s |
| merge down (+ show) | 0.29–0.32 s (was 0.98 s over every pixel) | ≈ 1 s |
| Undo of the merge / clear (+ show) | 0.12–0.14 s | ≈ 0.4–0.5 s |
| UV transfer, all 2,234 faces new (2.26 M texels): plan / per layer | 0.58–0.82 s / 0.51–0.53 s (was 1.3 s per layer) | ≈ 2–2.8 s / 1.7 s |
| UV transfer with the 2048² texture and 2 layers (paint in 30 % / 10 %), after the float32 read | texture 1.32 s (plan included) + layers 0.67 s ≈ 2.0 s (2.7 s before the float32 read) | ≈ 6–7 s |

Reading: the steps are clicks, not drags, except the opacity slider. Manu found it slow on the reference PC (as
estimated, ≈ 4 frames a second); the slider fix (§11.2, "the held slider") cuts its frame 6× in the container's heavier
probe and ~10× in this table's case. Not re-measured on the reference PC yet.

### 11.5 Not in Phase 3 (this slice)

Symmetry in a pose (P-9), Blur / Smudge, face regions / Mask Geometry as
paint masks, the 2D UV view (all audit Phase 3, not chosen for this slice), layer masks, more blend modes, the undo budget
(P-11: the layer steps hold compressed snapshots - 16 MiB raw per layer at 2048², a fraction compressed), a UV transfer
for a later Mirai UV tool (the function takes any old / new UVs of one topology), keys (after "Taste passt").

## 12. Phase 4a — built (2026-11-25): alpha tip, projection, world spacing, stamp queue

Built on `claude/adoring-cerf-ey4n1n` from `922d964` (the proposal and its decisions). Basis: the
[proposal](../research/ALPHA_BRUSH_STROKE_SYSTEM_PROPOSAL_2026-11-25.md) §1–§5, §8, §9 "4a", §10 (P-18 … P-28 decided,
Manu 2026-11-25). Values marked `PROVISIONAL` are agent-set and tuned against the gates; still no key, no keymap entry,
no scene-format change, no new dependency. The foundations (texel map, store, recorder, live texture, `seam_pad`,
`mirror`, Pick) are unchanged; `PaintSurface.footprint` is the same computation behind a shared `_gather`.

### 12.1 The tip (§4.7) — `mirai.paint.brush.TipSettings`, `mirai.paint.alpha`

- `BrushSettings` gains two frozen sub-objects with "today's round brush" as defaults: `tip: TipSettings` (`alpha`: None =
  the round tip, or an alpha id; `kreismaske`, off by default, P-19) and `dynamics: StrokeDynamics` (`spacing`,
  `orientation` "stroke", `angle`). `with_tip` switches tips; switching between round and alpha sets that kind's default
  spacing (round 12.5 %, alpha 100 %). Single emitter only (spray is 4b).
- `alpha.AlphaImage`: uint8 grey (white = paint), a mip chain (2×2 box halving down to 4 px while the short side keeps
  2 px), `level_for` (the level whose long side is closest to the stamp's diameter in texels, from the gather count), a
  vectorised bilinear `sample` / `sample_local` (one `take` of the four neighbours, float32 only on the gathered texels,
  0 outside the rectangle) and `reach` (the farthest painting pixel from the centre, in stamp radii: the gather's
  radius). The world radius (P-7) is the half-extent of the alpha's long side.
- **Test alphas** (§9 "test-alpha chooser"): six procedural, deterministic images (`TEST_ALPHAS`: Poren, Ader, Kratzer,
  Fleck, Punkte, Quadrat; NumPy, fixed seeds, black border), generated on first use. No library, import, presets or
  thumbnails (4c). An unknown id resolves to the round tip.
- **The round tip through the new pipeline is bit-identical to the Phase 2 dab** — pinned first, before the rebuild,
  against a frozen copy of `_dab` on the Gollum head's cage and SubD 1, mirror on and off, paint and erase
  (`tests/test_paint_alpha.py`).

### 12.2 The projection (§4.1–§4.4) — `mirai.paint.stamp`

- Per placement: gather within `R = r · reach` (where the alpha paints at all; ≤ the rectangle's corners
  `r · |half extents|`, §12.7) on triangles facing the hit's way; the **frame normal** is the
  area-weighted mean of the triangle normals in the inner disc (`INNER_DISC` 0.5 r; `PaintSurface._texel_area` = a
  triangle's world area per texel); the **tangent** is the placement's stroke direction projected into the plane, else
  the view's up (a click without movement), turned by the angle offset; local `(a, β, h)` per texel.
- **Planar** (the default): coverage = alpha × depth window (`|h|` full to 0.35, 0 from 0.5) × facing fade
  (`smoothstep(0.2, 0.5, n · n_tri)`) × [Kreismaske: the round falloff]. Texels with no coverage are not written.
- **Wrap projection — built in 4a (deviation from "planar only"):** the §4.3 validation failed at the **nostril wing**
  (planar aspect 1.43 cage / 1.36 SubD 1 at 3 %, > 1.3; reported before building, as agreed) — see the correction in
  §12.7: a faithful wrap is no rounder there at 3 %; its real gains are from 4 % on. From `WRAP_FROM_PERCENT` = 4 % brush
  radius (below it every placement is planar), where the planar stamp is
  *convexly stressed* (`WRAP_STRESS`: > 8 % of the rectangle's texels below the plane beyond the depth window's full
  part or on triangles the fade dims — counted over the whole rectangle `r · |half extents|`, gathered only when the
  alpha's own reach shows > `PRECHECK` = 2 % at all) and not in a crease (`SADDLE`: ≤ 4 % rising above it), the
  coordinates are **geodesic polar coordinates** (a discrete exponential map, [E] Schmidt et al. 2006, Substance "Tangent | Wrap"): shortest edge paths
  from the centre's triangle (Bellman-Ford rounds over the edges, vectorised), each vertex's 2D coordinate = its parent's
  + the edge projected into the frame turned onto the parent's tangent plane (length kept), summed along the tree by
  pointer jumping (the triangles within 1.1 × the gather's radius), texels interpolating their triangle's corners;
  unreachable triangles get nothing. In the mouth corner
  (a crease) a geodesic disc grows beyond π r² (area 1.47) and the planar stamp is closer to the ideal, hence `SADDLE`.
  Per placement the choice is automatic; the mirror uses the main stamp's projection.
- **Mirror:** the reflected frame (`reflect` of t, b, n: its handedness flips, an asymmetric alpha appears mirrored) at
  the reflected centre; a texel in both counts once with the larger coverage (as the round tip).
- `combine` / `PaintStroke.dab_product`: K stamps in one write as `S ← 1 − (1 − S) · Π(1 − flow_k · c_k)` (pinned equal to
  one-by-one within float tolerance). In 4a every placement is one stamp (plus its mirror), so `dab` is used; the
  product is ready for spray (4b).

### 12.3 Spacing and the stamp queue (§5.2–§5.4, P-18, P-27) — `mirai.paint.dynamics`, the controller

- **World arc length** (P-18): `spacing` in fractions of the stamp diameter (2–300 %), along the polyline of the hits of
  the cursor's rays. Input events only add rays (`StrokeQueue.add_ray`, with a sample count from the screen distance over
  a step of the spacing in pixels clamped to 2–6 px); the sampler hits the shown surface per sample, places stamps every
  `spacing · 2r`, carries the remainder across events, ends a run at a hit gap (a miss, or a jump > max(2 r, 6 sample
  steps): a silhouette). Placements are a pure function of the rays and sample counts (pinned: one run vs a run starved
  to one step per frame give the same placements).
- **"Strich folgen"** (P-21): placement k's tangent = the chord from k−1, smoothed **on the surface** (the previous
  tangent turned by the minimal rotation between the two hit normals, the chord projected into the new plane) with a
  weight per placement `α = 1 − exp(−spacing / 0.5 r)`. **Deviation:** the proposal's fixed α = 0.5 lagged 22–25° behind
  the stroke across the nose at 100 % spacing (stamps 2 r apart need no jitter smoothing); the arc-length weight gives
  α ≈ 0.63 at 25 % spacing (as dense as before) and 0.98 at 100 %. A run's first placement waits for the second (its
  direction); a run that ends earlier takes its partial chord, or none (the view's up).
- **The queue** (`StrokeQueue.run(budget)`, `PaintRoomController.frame()` from `Application.update_viewport` before the
  paint display's update): sampling and evaluating within the frame budget (`frame_budget`: 10 ms; while more than
  `BACKLOG_S` = 150 ms of work — priced from running means on this machine — trails the cursor, the excess at once up to
  22 ms). The sampler runs only when the placement queue is empty: the backlog is the unsampled path, which trails the
  cursor and catches up, never gaps.
- **Release** never evaluates in the event: the stroke is **finishing** (`PaintRoomController.finishing`); the next
  frames drain the rest (30 ms each), then `seam_pad` and one History step (`_commit`). Esc while finishing restores
  exactly (also the first stroke's stack). Ctrl+Z / Ctrl+Y / Shift+S / the SubD keys while finishing: the session takes
  the key, **finishes the stroke** (`settle`, bounded by the backlog) and lets the key run; the same for a new press,
  saving, LookDev and closing the room. **Interpretation:** "warten wie beim Malen" became "wait for the finish, then
  run" for these, because refusing a Ctrl+Z pressed 50 ms after a release would drop it; through the API (`dispatch_command`)
  Undo is still refused while finishing, as while stroking, and `can_run` stays pure (pinned by `test_iv_can_run_is_pure`).
  A brush change during a stroke no longer changes the running stroke's radius (it is taken at the press with the spacing).
- **Cursor:** an alpha tip draws its rectangle, turned by the stroke's last direction (hover: the view's up) and the
  angle, in the preview layer; the circle dimmed; the mirror's rectangle dimmed. The round tip: the circle as before.
- **Panel** (`gui.paint_panel`): "Spitze" (a combo: Rund + the six test alphas), with an alpha "Winkel" and
  "Kreismaske"; "Abstand" (logarithmic slider, every tip); hardness and curve only for the round tip or with the
  Kreismaske. `Application.set_paint_tip`. The layout is `PROVISIONAL` until the 4c picker (P-23).

### 12.4 Curvature validation (§4.3) — `tests/paint_alpha_regions.py`, `tests/test_paint_alpha.py`

Fixed probe placements on the Gollum head (front-view rays): nose tip, nose ridge, nostril wing, lip edge, mouth corner,
cheek, lid, the UV seam on the chin (the head's UV seam runs down the face's midline). A round test disc alpha, the
production projection rule (§12.7: planar below 4 %, chosen per placement from 4 %):

| 2048² | 3 % area / aspect, cage | 3 %, SubD 1 | round dab's aspect at 3 % (cage / SubD 1) | 5 % area / aspect (cage / SubD 1), projection |
|---|---|---|---|---|
| nose tip | 1.06 / 1.03 | 1.03 / 1.01 | 1.03 / 1.01 | 0.95 / 1.04 · 0.96 / 1.02, wrap |
| nose ridge | 1.01 / 1.01 | 1.01 / 1.02 | 1.03 / 1.03 | 1.01 / 1.01 · 1.02 / 1.01, planar |
| nostril wing | 0.76 / **1.42** | 0.88 / **1.33** | **1.42 / 1.33** | 1.13 / 1.11 · 1.13 / 1.23, wrap (planar 1.34 / 1.50) |
| lip edge | 1.03 / 1.01 | 1.03 / 1.01 | 1.02 / 1.02 | 1.01 / 1.04 · 1.00 / 1.05, wrap |
| mouth corner | 1.15 / 1.15 | 1.10 / 1.07 | 1.02 / 1.06 | 1.15 / 1.29 · 1.30 / 1.16, planar |
| cheek | 1.01 / 1.00 | 1.01 / 1.01 | 1.00 / 1.00 | 1.02 / 1.00 · 1.01 / 1.00, planar |
| lid | 1.06 / 1.03 | 1.04 / 1.00 | 1.06 / 1.06 | 1.02 / 1.03 · 1.00 / 1.07, wrap |
| UV seam | 1.07 / 1.06 | 1.01 / 1.01 | 1.03 / 1.01 | 1.08 / 1.03 · 1.03 / 1.01, planar |

- **Stretch at 3 %:** every region within area ±25 % and aspect ≤ 1.3 on both surfaces, **except the nostril wing's
  aspect (1.42 / 1.33), which equals the round dab's there** — the wing is curved about as tightly as a 3 % stamp, and a
  faithful stamp (planar or wrapped, §12.7) cannot be rounder in 3D; the test holds it to "no worse than the round dab".
  At 5 % the wrap rounds it to 1.11 / 1.23. (Tested at 2048², the default.)
- **Leak:** no painted texel on a triangle unconnected to the centre (another sheet) at any region at 3, 4, 5 and 8 %.
  The planar stamp on the lip edge reaches the lower lip from 4 % (cage 88 texels at 4 %, 435 / 315 at 5 %; the round dab
  531 / 385 at 5 %); from 4 % the stressed placement wraps and paints none there (pinned at 4, 5, 8 %).
- **Seam:** a stamp centred on the midline seam paints both islands; across the seam neighbouring texels differ by no
  more than the alpha's own slope allows (a cone alpha; pinned).
- **Frame jump** (scripted strokes at 100 % spacing: across the nose, over the lip, along the ridge, over the wing).
  **Deviation in the metric:** literally (n and t between successive placements) the surface itself turns 45–80° per
  placement on these strokes (2 r apart) — no frame can stay under 15°, a perfect one included. Measured instead is the
  frame's **own** error: the normal jump beyond the turn of a smooth reference (the same inner-disc estimator on SubD 2)
  and the tangent's angle from the stroke's own direction. Result: normal excess ≤ 11° on the cage and ≤ 12° on SubD 1,
  **except at the lips' line on SubD 1: 17.5°** (a disc centred on the crease averages both lips; any point normal
  differs from a disc's mean there) — the test allows 20° for that stroke only; tangent ≤ 13.7° everywhere.
- **Mirror:** the asymmetric "Ader" at the cheek with the head's X plane: the mirror stamp's coverage at each texel
  equals the main stamp's at the reflected point (mean difference < 0.06; the reflected frame is left-handed).
- **Contact sheet** for Manu (`experiments/drag_cost/contact_sheet_paint_4a.py`): Poren, Ader and Kratzer at the eight
  regions, cage and SubD 1, 3 % and 5 %:
  [`docs/research/alpha_brush_4a_assets_2026-11-25/`](../research/alpha_brush_4a_assets_2026-11-25/)
  (`contact_sheet_{cage,subd1}_{3,5}pct.png`). Each label names the projection the middle placement chose.

### 12.5 Measurements [C] (container: Xeon, Python 3.13, NumPy 2.2.6, llvmpipe; `probe_paint.py`, 2048², mirror on)

Verbatim in [`RESULTS_PAINT_PHASE4A_CONTAINER_2026-11-25.md`](../../experiments/drag_cost/RESULTS_PAINT_PHASE4A_CONTAINER_2026-11-25.md).
The frame rows are llvmpipe (5.5–7 ms cage, 10–15 ms SubD 1; the reference PC drew 4–6 ms, §10.8e).

| Row (2048², mirror on) | cage p50 / p95 | SubD 1 p50 / p95 | gate (reference PC) |
|---|---|---|---|
| P-H alpha 3 %: dab + composite (CPU) | 4.1 / 6.4 ms | 4.5 / 7.8 ms | — |
| P-H alpha 3 %: total with the llvmpipe frame | 10.4 / 14.7 ms | 15.7 / 20.8 ms (FAIL here: the frame) | p95 ≤ 16.7 ms |
| P-A round 3 % in the same run (CPU / total) | 3.1 / 4.2 · 8.7 / 10.6 ms | 3.5 / 4.9 · 13.2 / 17.9 ms (FAIL here) | (passed on the RPC: 9–11 ms) |
| P-H alpha 5 %: dab + composite / total | 7.2 / 11.2 · 14.4 / 18.4 ms | 7.0 / 12.7 · 19.5 / 24.9 ms | p95 ≤ 33 ms |
| P-I 2-s stroke, round 12.5 %: frame / release → History / finishing max | 9.5 / 12.8 ms · 8.4 ms · 5.3 ms | 15.1 / 20.7 ms · 12.7 ms · 10.2 ms | ≤ 33 · ≤ 250 · ≤ 50 ms |
| P-I 2-s stroke, Poren 100 % | 6.5 / 10.8 ms · 7.7 ms · 5.3 ms | 13.2 / 17.7 ms · 17.0 ms · 14.0 ms | same |
| P-I flick 0.17 s, round (info) | 112 placements; release → History 186 ms, 5 finishing frames ≤ 40 ms | 109; 299 ms, 7 frames ≤ 48 ms | no gate |

- *(First build; superseded by §12.7)* The alpha placement cost **1.5–1.6×** the round dab on the CPU (the gather of the
  square's corners at `r √2`, the frame, the sampling; 20–25 % of the placements on this stroke wrapped).
- The 2-s stroke keeps up: nothing is left at the release, every 4a stroke gate passes on the container.
- Tests (container): `tests/` 8261 passed, 3 failed — the same 3 fail on `922d964` (the box-paint scenario and its
  `can_run` purity variant, `test_scene_menu_local_tmp::test_probe_menu_wiring`; pre-existing, not 4a), 8 skipped;
  `tests/test_gl_*.py` alone 444 passed; `experiments/drag_cost/tests` 111 and `experiments/morph_lab/tests` 49 passed.

### 12.6 Not in 4a / open

- **Reference PC: done** (second run, §12.7): every 4a gate met. SubD 1 at 3 % is tight - 0.7 ms margin for the alpha,
  0.3 ms for the round dab; 4b's jitter and spray must not add cost to a single-stamp placement.
- **Praxistest passed** (Manu, 2026-11-25, verbatim): „Praxistest gut bestanden. Läuft flüssiger, als ich erwartet habe.
  Keine Verzerrungen auch über extreme winkel hinweg.“ 4a is closed; 4b next.
- **The wrap's radius rule is object-relative:** `WRAP_FROM_PERCENT` is P-7's percent of the object's bounding radius,
  measured on the Gollum head. On a much larger object (a full body) 3 % is large against a face's features and stays
  planar - painting through there as the round dab does today. A curvature-relative rule (stamp radius against the
  local curvature radius, from the gather) is the follow-up if the practical test asks for it.
- 4b: rotation / scale / flow jitter, scatter, the other orientation modes, spray, counter-based RNG (the queue's
  placements are already timing-independent). 4c: library, presets, picker, import, starter set. 4d: colour jitter.
- The flick (the whole path in 0.17 s) leaves a backlog the room drains over the following frames (P-27: catch-up, never
  a freeze); its release → History is not a gate.

### 12.7 The reference-PC run (Manu, 2026-11-25), the correction and the optimisation

**The run** ([`RESULTS_PAINT_PHASE4A_REFERENCE_PC_2026-11-25.md`](../../experiments/drag_cost/RESULTS_PAINT_PHASE4A_REFERENCE_PC_2026-11-25.md), [RPC], at `da2af8a`):

| Row | cage p50 / p95 | SubD 1 p50 / p95 | gate | |
|---|---|---|---|---|
| P-A round 3 % (dab · total) | 5.75 / 7.15 · 11.69 / 13.60 ms | 6.28 / 7.67 · 14.34 / 15.77 ms | ≤ 16.7 | PASS |
| **P-H alpha 3 % (dab · total)** | 8.49 / 13.24 · 14.38 / **18.23** ms | 8.90 / 16.71 · 16.51 / **24.27** ms | ≤ 16.7 | **FAIL** |
| P-H alpha 5 % (total) | 21.34 / 28.01 ms | 23.53 / 31.88 ms | ≤ 33 | PASS |
| P-I 2-s stroke round / Poren: frame p95 · release → History | 18.8 / 16.4 ms · 10.8 / 10.5 ms | 21.1 / 18.8 ms · 13.2 / 11.3 ms | ≤ 33 · ≤ 250 | PASS |
| P-I finishing frame max (all rows, flicks included) | ≤ 43.4 ms | ≤ 46.6 ms | ≤ 50 | PASS |

**Why P-H 3 % failed:** the alpha's dab cost 1.9–2.2× the round dab at p95: a square alpha gathered out to its corners
(`r √2`, twice the round dab's area) whatever it holds, and 20–25 % of the placements on this stroke wrapped - main and
mirror each with its own shortest-path rounds. The round dab leaves 0.9 ms of the 16.7 ms on SubD 1, so the alpha had to
cost about what the round dab costs.

**A correction found on the way (§12.2, §12.4):** restricting the wrap's texels to where the alpha paints showed that the
first build's wrapped wing (aspect 1.29 / 1.19 at 3 %) had painted texels 0.96–1.41 r away in 3D whose wrap coordinate
was below 0.95 r. A faithful geodesic map cannot do that (a geodesic distance is never shorter than the straight one):
the discrete exponential map compressed there, and that compression made the "pass". Painted only where the alpha
reaches, the wrapped wing at 3 % is 1.41 / 1.36 — as stretched as the planar stamp (1.42 / 1.33) and the round dab
(1.42 / 1.33). The §4.3 aspect gate is not reachable at that place by a faithful stamp; at 3 % the wrap bought nothing
anywhere on the probe set, while from 4 % it does (the lip leak, the wing, nose tip and lid at 5 %).

**The optimisation** (`mirai.paint.alpha`, `mirai.paint.stamp`; pixels at 3 % unchanged wherever the projection is the
same; the curvature, leak, seam, frame, mirror and room tests re-run green):
- the gather's radius is the alpha's `reach` (Poren: 0.99 r instead of 1.41 r; exact: beyond it the alpha is 0); the
  wrap decision's statistics still cover the whole rectangle, gathered only when the alpha's own reach shows stress;
- `WRAP_FROM_PERCENT` = 4 %: below it no stamp wraps (the measurements above), from it the decision as before;
- the wrap's triangles end 1.1 × beyond the gather (paths may bend out of it) instead of at `r √2`;
- fewer NumPy calls per stamp: one `take` for the four bilinear neighbours with the affine map folded in
  (`sample_local`), the depth window and the facing fade only where a texel reaches them, the stress statistics only
  where a choice is made, `np.cross` on 3-vectors written out.

**Measured [C]** (container, the probe's stroke, best of 8 runs, evaluate + write per placement, 3 %): round 1.20 / 1.19 ms,
alpha **before 2.04 / 2.24 ms (1.8–1.9×), after 1.38 / 1.39 ms (1.15–1.17×)** (cage / SubD 1); p95 1.80 / 1.71 ms
against the round dab's 1.84 / 1.51 ms. In the probe of the same run (`RESULTS_PAINT_PHASE4A_CONTAINER_2026-11-25.md`,
"after the optimisation"): P-H 3 % dab p50 / p95 2.39 / 3.00 ms (cage) and 2.54 / 3.23 ms (SubD 1) against P-A's round
dab 2.31 / 2.86 and 2.68 / 3.58 ms, 0 % wrapped; P-H 5 % 10–15 % wrapped, total p95 13.5 / 18.1 ms (llvmpipe frame).
**Expectation for the RPC [H]:** the alpha's 3 % row about the round dab's (13.6 / 15.8 ms p95), i.e. passing.

**The second reference-PC run** (Manu, 2026-11-25, at `0ff03c8`; [RPC], verbatim in the results file above):
**every 4a gate met.**

| Row | cage p50 / p95 | SubD 1 p50 / p95 | gate | |
|---|---|---|---|---|
| P-A round 3 % (dab · total) | 5.72 / 7.68 · 11.91 / 15.72 ms | 6.46 / 8.30 · 14.85 / 16.39 ms | ≤ 16.7 | PASS |
| **P-H alpha 3 % (dab · total)**, 0 % wrapped | 6.64 / 7.33 · 12.46 / **14.05** ms | 6.96 / 7.59 · 14.71 / **16.01** ms | ≤ 16.7 | **PASS** (was 18.23 / 24.27) |
| P-H alpha 5 % (total), 15 / 10 % wrapped | 19.05 / 24.84 ms | 21.18 / 28.21 ms | ≤ 33 | PASS |
| P-I 2-s stroke round / Poren: frame p95 · release → History | 18.3 / 14.8 ms · 9.9 / 9.7 ms | 20.0 / 17.3 ms · 12.1 / 10.8 ms | ≤ 33 · ≤ 250 | PASS |
| P-I finishing frame max (all rows, flicks included) | ≤ 42.9 ms | ≤ 44.4 ms | ≤ 50 | PASS |

The alpha's 3 % dab is now the round dab's (p95 7.33 / 7.59 against 7.68 / 8.30 ms; it writes a quarter of the
texels). The flicks (information) drain in ≤ 14 finishing frames. P-A round 1 % on the cage had one stall (max 293 ms,
p95 28 ms in that row only; 9.0 / 12.6 ms in the first run) - the machine, not 4a.

## 13. Phase 4b — built (2026-11-25): jitter, scatter, orientation modes, spray, counter-based randomness

Built on `claude/charming-curie-kckgrg` from `4a49d5b` (4a closed). Basis: the
[proposal](../research/ALPHA_BRUSH_STROKE_SYSTEM_PROPOSAL_2026-11-25.md) §5.1, §5.3, §5.5–§5.7, §5.9, §7 area 4, §8, §9
"4b", §10 (P-18 … P-28 decided). Values marked `PROVISIONAL` are agent-set. No key, no keymap entry, no scene-format
change, no new dependency; the foundations (texel map, store, recorder, live texture, `seam_pad`, `mirror`, Pick, the
queue, the 4a projection and wrap rule) are unchanged - 4b only adds what a placement does with them.

### 13.1 Pinned first: no randomness = 4a, bit for bit

Before the rebuild, `tests/test_paint_dynamics.py` pinned the room's placement path against a **frozen copy of 4a's
`stamp` module** (`tests/paint_stamp_4a_frozen.py`, `4a49d5b`): the round tip (erase, 3 %) and the alpha tip (Poren 3 %
planar, Poren 5 % with wrapped placements, Ader 5 % with angle 30° and the Kreismaske) through the stroke queue on the
Gollum head's cage and SubD 1, mirror on and off - pixels and the stroke buffer identical. It stayed green through the
rebuild. The round tip stays bit-identical to the Phase 2 dab (`tests/test_paint_alpha.py`, unchanged).

### 13.2 The settings - `mirai.paint.dynamics.StrokeDynamics`

| Field | Meaning (proposal §5.1) | Range (`PROVISIONAL`) | Default |
|---|---|---|---|
| `orientation` | Strich folgen / Ansicht / Fläche / Zufall (§5.3) | - | Strich folgen (P-21) |
| `angle` | offset of the stamp's "up", every mode | ±180° | 0 |
| `jitter_rotation` | Zufall: rotation per stamp | ± 0–180° | 0 |
| `jitter_size` | Zufall: size per stamp | ± 0–90 % | 0 |
| `jitter_flow` | Zufall: flow per stamp ("Deckkraft-Streuung (pro Stempel)") | ± 0–100 %, the stamp's flow capped at 1 | 0 |
| `scatter_across`, `scatter_along` | Streuung: offset from the stroke line, two sliders | 0–2 r each, the offset's length capped at 2 r | 0 |
| `emitter` | Einzeln / Spray (§5.5) | - | Einzeln |
| `spray_density` | stamps per placement | 1–64 (K ≤ 64) | 12 |
| `spray_size` | stamp size | 5–50 % of the radius | 20 % |
| `spray_intensity` | the spray stamps' flow | 0–100 % of the brush flow | 100 % |

`StrokeDynamics.with_` clamps (the panel's path; scatter beyond 2 r is capped, pinned), the constructor refuses values
outside. Switching to spray sets the spacing to 50 % (`SPRAY_SPACING`, a burst per radius of path); a tip change keeps a
spray's spacing. Rotation and orientation do not apply to the round tip (§5.9); size, flow, scatter and spray do.

### 13.3 Counter-based randomness (§5.7) - `dynamics.random_values`

- **The seed** is drawn at the press (`controllers.paint_room.new_seed`, 32 bit), held by the controller for the running
  stroke and stored on the stroke's `PaintStrokeCommand` (`seed`; diagnostics and replay). Not in the scene: the scene
  stores pixels. (There is no `StrokeState` class; the controller holds the stroke's state.)
- **Values of placement `i`, stamp `k`** come only from `(seed, i, k)`: a SplitMix64 hash over the counter
  `((i · 65 + k) · 8 + column)`, eight columns per stamp row (rotation, size, flow, across, along, radius, turn,
  orientation), row 64 the placement's own (its scatter). **Deviation:** the proposal named
  `Generator(PCG64(SeedSequence([seed, i, k])))`; building a generator per stamp costs tens of µs (20 stamps: ~1 ms per
  placement), the hash draws a placement's 21 rows in 0.03 ms. The property is the same: a pure function of the counter,
  independent of the density, of other rows and of timing (pinned; mean and correlation checked).
- Placements are arc-length positions (4a), so mouse speed, event rate, queue chunking and frame budget change neither
  where the stamps go nor what they draw. **Undo / Redo** restore the recorded tiles and never draw (pinned with a
  `random_values` that records calls).
- **The mapping** (`stamp_jitter`, `scatter_offset`, `spray_positions`) is pure: rotation within ± `jitter_rotation`
  (plus a full random turn for "Zufall"), size within 1 ± `jitter_size`, flow factor within 1 ± `jitter_flow` (≥ 0),
  scatter within ± each slider with the length capped at 2 r, spray centres area-uniform (`ρ = √u`) in the disc of radius
  `1 − spray_size` (**deviation:** the proposal's `ρ = r √u` lets a stamp stick out of the disc; with `1 − s` the stamps
  stay inside it, as §5.5 asks).

### 13.4 A placement - `mirai.paint.stamp.paint` / `cluster`

- **Without randomness** (`StrokeDynamics.random` False - the orientation modes Ansicht / Fläche included, they only
  choose another tangent, `orientation_tangent`) `paint` is 4a's `evaluate` + `PaintStroke.dab`, unchanged.
- **With randomness** `cluster` returns `(texels, prod(1 − flow_k · c_k))` and the stroke takes **one**
  `PaintStroke.dab_product` per placement (§5.6; `S ← 1 − (1 − S) · P`).
- **Scatter** moves the placement by `(along · t + across · b) · r` in its tangent plane (`t` the path's direction, else
  the view's up) and **puts it back on the surface** with a ray along `−n` from one radius above (`_scattered`).
  **Deviation:** the proposal left a scattered stamp in the tangent plane; on the head's curvature a 2 r offset would
  float 0.2–2 r above the skin (and the depth window would cut it). Off the object, onto a back face or onto another
  sheet farther than 2 r: nothing is painted for that placement.
- **Single:** the alpha tip goes through 4a's `alpha_stamp` at the jittered radius and angle (its inner-disc frame, mip,
  depth window, facing fade; the wrap rule with the jittered radius: `projection_for(radius % · size)`); the round tip
  through 4a's footprint and falloff at the jittered radius.
- **Spray:** **one gather** around the (scattered) centre within the reach of the farthest stamp, **one frame** (4a's
  inner-disc normal, the orientation's tangent), the depth window and facing fade once per texel in that plane; then
  all stamps' bounding squares as one (stamps × texels) boolean mask, each selected (stamp, texel) pair turned into its
  stamp's frame (angle offset + rotation jitter, or a random turn), the alpha read once per mip level (each stamp's level
  from its share of the disc's diameter in texels) - or the round falloff (hardness, curve) for the round tip -, and
  `np.multiply.at` into the cluster's product in stamp order. **Deviation:** the proposal's loop over stamps became one
  vectorised pass (the loop cost ~50 µs of NumPy overhead per stamp; 20 Poren stamps 4.9 → 2.5 ms per placement [C]);
  still no loop per texel. Spray stamps lie in the placement's tangent plane (the proposal's planar approximation): no
  wrap for spray stamps.
- **Mirror:** the reflected cluster at the mirrored centre uses **the same random values** in the reflected frame
  (handedness flipped): every mirror stamp's centre is the reflection of its main stamp's, its direction the reflected
  direction, same radius and flow (pinned on the head), and a randomised stroke on a symmetric plane is mirror-symmetric
  to 4·10⁻⁵ (pinned, spray and single). A texel in both keeps the smaller product (the larger coverage), as 4a merges.
- **A click without movement is one burst** (one placement; pinned: one `dab_product` after 30 still frames); holding
  still adds nothing (P-28: no time-based emission).
- **Surfaces:** like 4a, a cluster reads only the shown surface - its hit, its texel points, its triangle normals and UVs
  (`PaintSurface`) - so the cage, SubD, a morph mix and a pose work alike (the pose and the morph mix are a shown mesh
  like any other; not separately tested in 4b).

### 13.5 Room, cursor, panel

- `PaintRoomController`: the seed per stroke; the queue is `directed` for an alpha tip **or scatter** (the scatter needs
  the path's direction; the plain round tip stays undirected, as 4a). The cursor: an alpha tip draws its rectangle turned
  by the orientation (Strich folgen: the last direction; Ansicht: the view's up; Fläche: the UV-u tangent under the
  cursor); spray and "Zufall" draw the brush circle (§7).
- **Panel** (`gui.paint_panel`, logic in `gui.paint_model`): under the tip, collapsing headers **closed by default**, each
  with a one-line summary while closed (proposal §7 area 4): **Strich** (Abstand; with an alpha Ausrichtung and Winkel;
  Einzeln / Spray), **Streuung** (Drehung ± with an alpha, Größe ±, Fluss ±, Streuung quer, Streuung längs), **Spray**
  (only with spray: Dichte, Stempelgröße, Intensität). The summaries (e.g. „Abstand 50 %, Fläche +30°, Spray“, „Drehung
  ±180°, Größe ±40 %, Fluss ±50 %, quer 0,6 r, längs 0,4 r“, „20 Stempel, Größe 25 %, Intensität 100 %“) and a headless
  draw of every section are pinned. The status line adds „Spray N“ and „Streuung“ when they are on. No presets, no
  library (4c). Layout `PROVISIONAL` until the 4c picker (P-23).

### 13.6 Tests [C]

`tests/test_paint_dynamics.py` (34): the 4a bit identity (16 cases); the randomness a pure function of
`(seed, i, k)`; every jitter / scatter / spray value inside its bounds over 150 seeds × 3 placements and filling them;
scatter capped at 2 r (settings and painted texels); **the same rays and seed give identical pixels for budgets 1 ms,
10 ms and unlimited** (spray Poren with every jitter and scatter, single Ader, round spray; mirror on; a different seed
differs); the mirror reuses the values (head, SubD 1) and a stroke is mirror-symmetric (plane); **spray density per area
independent of the stroke speed** (the same 240 px line in 80 and in 8 events: stamps per arc length, painted area and
coverage within 5 %); a spray cluster in one write equals its stamps one by one (cover within 1·10⁻⁵, pixels ±1); the
orientation modes (view, surface on two UV layouts, random deterministic per placement, the offset for every mode);
the room: one Undo step per stroke with its seed, Undo / Redo exact without drawing, Esc exact, the same seed and input
paint the same stroke (with and without the display's update), a click is one burst; the panel model and a headless draw.
The 4a curvature, leak, seam, frame and mirror tests (`tests/test_paint_alpha.py`) stay green unchanged.
Whole suite (container, xvfb): `tests/` 8295 passed, 3 failed - the same 3 as on `922d964` and in 4a (§12.5: the
box-paint scenario, its `can_run` purity variant, `test_scene_menu_local_tmp::test_probe_menu_wiring`), 8 skipped;
`tests/test_gl_*.py` alone 444 passed; `experiments/drag_cost/tests` and `experiments/morph_lab/tests` 158 passed.

### 13.7 Measurements [C] (container: Xeon, Python 3.13, NumPy 2.2.6, llvmpipe; `probe_paint.py`, 2048², mirror on)

Verbatim in [`RESULTS_PAINT_PHASE4B_CONTAINER_2026-11-25.md`](../../experiments/drag_cost/RESULTS_PAINT_PHASE4B_CONTAINER_2026-11-25.md).

| Row (2048², mirror on, 3 %) | cage p50 / p95 | SubD 1 p50 / p95 | gate (reference PC) |
|---|---|---|---|
| **P-J** Poren spray, 20 stamps (+ mirror): dab (CPU) | 4.16 / 4.80 ms | 4.56 / 6.81 ms | — |
| **P-J** total with the llvmpipe frame | 10.95 / **12.83** ms | 17.36 / **24.05** ms | p95 ≤ 33 ms |
| P-J round spray, 20 stamps (info): total | 10.54 / 13.98 ms | 16.24 / 20.38 ms | — |
| **P-K** 10-s spray stroke (280 / 273 placements of 20 stamps): stroke frame p95 · max of every frame | 14.4 · **22.1** ms | 20.5 · **35.3** ms | no frame > 50 ms |
| P-K release → History | 9.6 ms | 11.6 ms | (≤ 250 ms, 4a's) |
| P-H alpha 3 %, single, no randomness: dab, 4a ↔ 4b A/B (1200 placements each, interleaved) | 1.76 / 2.47 ↔ 1.76 / 2.54 ms | 1.73 / 2.22 ↔ 1.71 / 2.03 ms | **unchanged** (§12.6) |
| P-A round 3 %: dab, 4a ↔ 4b A/B | 1.55 / 2.02 ↔ 1.55 / 2.01 ms | 1.54 / 2.29 ↔ 1.55 / 2.26 ms | unchanged |

- A single placement without jitter, scatter or spray costs what it cost in 4a (it runs 4a's code; `paint` adds one
  property check). The probe's own P-H rows, run alternately at `4a49d5b` and on 4b (`--no-gl`, twice each), scatter
  by ± 0.3 ms both ways - as much as P-A, whose code is untouched.
- Expectation for the reference PC [H]: the CPU there was 2.2–2.6× the container's on the 4a dab (§12.7: 6.6–7.0 ms
  against 2.4–2.5 ms p50); P-J's dab would be ~10–15 ms p50, ~18 ms p95 on SubD 1, plus composite and a 4–6 ms frame:
  **~25–28 ms p95 against the 33 ms gate**. P-K: the queue's budget bounds a frame's work; the largest container frame
  (35 ms on SubD 1, of it llvmpipe's draw) suggests a margin, but it is the RPC run that decides.
- The vectorised spray: 20 Poren stamps 4.9 → 2.5 ms per placement (mirror on, before / after, best of 6 [C]);
  20 round stamps 3.3 → 2.1 ms.

### 13.8 Not in 4b / open

- **Reference-PC run open:** `python experiments/drag_cost/probe_paint.py` (rows P-H, P-J, P-K; P-A / P-I for
  comparison) - the gates P-J p95 ≤ 33 ms and P-K no frame > 50 ms, and P-H 3 % as in §12.7 (14.05 / 16.01 ms p95).
- **Praxistest** below (Manu).
- Colour jitter (§5.8: the stroke colour buffer) stays 4d; presets, the library, the picker and the starter set are 4c.
- Spray stamps never wrap (planar cluster, §13.4); a large spray brush (≥ 8 %) on a strongly curved place (the nose tip)
  fades its outer stamps by the depth window instead of wrapping them. If the practical test asks for it, the cluster
  can wrap as a whole (one geodesic map per cluster, 4a's `_wrap`).
- The scatter's re-hit is one extra ray per placement (≈ 0.1–0.3 ms [C], measured inside the single-jitter row: 2.4 /
  2.7 ms against 1.8 ms plain); on a very large object a 2 r scatter can jump a crease onto the neighbouring sheet within
  2 r (the lip) - allowed by the cap.

## 14. Phase 4c — built (2026-11-26): library, presets, picker, import, starter set

Built on `ccr-f6a3ac5f-ciny94` from `08e208d` (4b built; its reference-PC run and Praxistest are still open). Basis: the
[proposal](../research/ALPHA_BRUSH_STROKE_SYSTEM_PROPOSAL_2026-11-25.md) §6, §7, §8, §9 "4c", §10 (P-20, P-22, P-23,
P-25, P-26 decided, Manu 2026-11-25; user assets in `~/.mirai_bastel/paint/`, the procedural starter set). Values marked
`PROVISIONAL` are agent-set. No key, no keymap entry, no scene-format change, no new dependency; painting itself (the
stamp, the queue, the projection, the randomness) is unchanged - 4c only decides **which** tip and values a stroke gets.

### 14.1 The library - `mirai.paint.library.PaintLibrary`

- **Where** (§6.1): built in and read-only - the six 4a test alphas (in memory), the starter alphas
  `assets/paint/alphas/<category>/<stem>.png` (+ `index.json`: names, hashes; only for categories Manu accepted, §14.5)
  and the presets `assets/paint/brushes/*.json`; the user's in `~/.mirai_bastel/paint/` (`src/main.py`:
  `Application.set_paint_user_dir`): `alphas/<slug>_<hash12>.png` (an 8-bit **grey** PNG, its 64² thumbnail in
  `alphas/thumbs/<hash>.png`), `brushes/<slug>.json`, `library.json` (favourites, the user alphas' names and categories,
  "Größe behalten"). Nothing is written anywhere else (pinned with a fake home: only `paint/` appears, the repo's
  `assets/` and the source image are untouched). Without a user folder (tests, tools) saving and importing are refused
  with a reason, favourites live in memory. A PNG dropped into `alphas/` is picked up by the scan ("Unsortiert", the
  name from the file name, normalised with the suggested source mode - decoded once per file and session).
- **Ids and references** (§6.2): `test/<stem>`, `builtin:<category>/<stem>`, `user:<hash12>` (`alpha.pixel_hash`:
  SHA-256 over the normalised pixels and their shape). `TipSettings` gained `alpha_name` / `alpha_hash` (the brush keeps
  `{id, name, hash}`) and `invert` / `contrast`. `resolve`: **id → hash → name → missing**. **Missing:** the brush paints
  with the round tip - pixel for pixel what the round tip with the same values paints (pinned through the room) - the
  panel says "Alpha fehlt: <name> (malt rund)", the status line too when a preset is chosen, and the reference stays
  (saving keeps it; pinned).
- **Presets** (§6.4): `"format": "mirai.paint.brush/1"`, one JSON per preset, the `eye_presets` rules (a broken, foreign,
  out-of-range, unknown-field or name-taken file is skipped with its reason in `problems`, shown in the picker; names
  slugged; atomic saves). A preset holds the tip (alpha reference, invert, contrast, Kreismaske), the radius (P-20, as
  `radius_percent`, read back to the nearest step), opacity, flow, hardness, curve and the stroke dynamics - **never
  colour, tool, mirror or layer** (P-25; pinned: the file has no such key, applying keeps the room's). Operations:
  choose · "geändert" (`BrushPreset.matches`) · Speichern (user presets) · Speichern als · Duplizieren ("… Kopie",
  "… Kopie 2") · Umbenennen (the file and the favourite follow) · Kategorie · Löschen (user only) · Favorit. Built-ins are
  read-only (save as / duplicate only; pinned). **"Größe behalten"** (P-20) keeps the radius when switching and makes the
  marker ignore it.
- **Deviations from §6.4's example:** the dynamics are stored as the flat `StrokeDynamics` fields (exact, one name per
  value); the import's **source mode is not part of a tip** - a stored alpha is already grey, so the mode is an import
  choice (§6.3); **invert and contrast are** (applied when the alpha is read: `alpha.contrast_lut`, a symmetric S-curve
  around 0.5, `k = 4^contrast`, black stays black - a derived image, cached).
- **Cache** (§6.6): an LRU of decoded alphas (pixels + mips, the shaped variants too) capped at `CACHE_BYTES` = 64 MiB.
  Thumbnails do not go through it.
- **The room** (`PaintRoomController`): `library`, `preset_id` (view state; the room starts on the built-in "Runder
  Pinsel", which equals `BrushSettings()` - pinned), `tip_image()` (what a stroke and the cursor paint with),
  `alpha_missing()`, `select_preset` (status line, "Alpha fehlt" when so). `Application`: `paint_library`,
  `paint_preset`, `paint_brush_changed`, `paint_alpha_missing`, `select_paint_preset`, `reset_paint_preset`,
  `save_paint_preset(_as)`, `duplicate / rename / delete_paint_preset`, `set_paint_preset_category`,
  `set_paint_favourite`, `set_paint_keep_size`, `import_paint_alpha`, `rename / delete_paint_alpha`,
  `set_paint_alpha_category`; `set_paint_tip` takes any library id. Library errors become the status line.

### 14.2 The import (§6.3, P-26) - `library.open_import`, `ImportDraft`, `import_pixels`

PNG through the own decoder, anything else through pyglet's (`read_image_rgba`). The image is box-reduced once to
`IMPORT_MAX` = 1024 px (P-22; luminance and the alpha channel are linear, so reducing first equals reducing the grey up
to rounding). **Source modes** Alphakanal / Luminanz (Rec.709 of the display values, P-16) / Luminanz × Alphakanal,
**preselected** as §6.3 says (no alpha channel → Luminanz; uniform RGB with a varying alpha → Alphakanal; both varying →
both; a bright border → Invertieren suggested), then Invertieren and Kontrast. Refused: smaller than 8 px, or nothing
painted (the reason in the card). **Border warning** when the outermost ring's mean is above 3 % (a square edge). The
same pixels imported twice are one alpha (also against a built-in) - the status says "schon vorhanden".

### 14.3 Picker and panel (§7, P-23) - `gui.brush_picker_model` (headless), `gui.brush_picker`, `gui.paint_panel`

- **Area 1, the brush row:** the brush's 32² preview (opens the picker), its name, category, `*` for a favourite (the
  panel font has no star), "- geändert"; "Pinsel ..." opens the picker; while changed: Speichern (a user preset),
  Speichern als ... (an inline name field), Zurücksetzen. Without a preset ("Eigener Pinsel", after deleting it): Speichern
  als.
- **Area 2, the tip:** "Spitze:" with the tip's thumbnail (opens the Alphas tab) and its name or "Alpha fehlt: ...";
  with an alpha "Rund" (back to the round tip), Invertieren, Kreismaske, Kontrast. Hardness and curve show for the round
  tip, with the Kreismaske, and for a missing alpha (it paints round). The 4a test-alpha combo is gone (the picker
  replaces it).
- **The picker popup** (an ImGui popup, Esc / a click outside closes it; it owns the mouse like a menu,
  `ImguiLayer.popup_open`): tabs **Pinsel** / **Alphas**, a category combo (Alle, Favoriten, the categories present), a
  search over name and category, "Größe behalten" (Pinsel) or "Alpha importieren ..." (Alphas: the file browser, purpose
  `image`); a grid of 64² thumbnails, favourites first, the chosen one framed, a tooltip (name, category, built in /
  own, favourite, missing); right-click: Favorit, Duplizieren (presets), Umbenennen, Kategorie, Löschen (own only;
  disabled and marked "nur lesen" for built-ins). Choosing a preset sets the brush and closes the picker; choosing an
  alpha sets the tip (the brush becomes "geändert").
- **The import card** (its own window - the file browser closes the popup; its rectangle joins the panel rectangles):
  the live preview, the three source modes, Invertieren, Kontrast, name, category, the border warning, Importieren
  (writes it and sets it as the tip) / Abbrechen.
- **Thumbnails** (§6.6): pixels from `PaintLibrary.thumbnail` (a user alpha's 64² file; built-ins made from their image
  once per session, kept in memory), GL textures made within `THUMB_BUDGET_S` = 12 ms per frame (a name button until
  then), kept while the room is open and freed when it closes (`PaintPanel.release`, called by the layer once the room is
  shut; pinned in the real window). **Change found by measuring:** the first build read the full alpha per thumbnail -
  ~57 ms for a 1024² noise alpha [C], 2.5 s for 50 -, hence the thumbnail files.
- Layout `PROVISIONAL` (P-23). Screenshots in the container's real window were checked (panel, both tabs).

### 14.4 Built-in presets (`assets/paint/brushes/`, `PROVISIONAL` values)

Runder Pinsel (= `BrushSettings()`), Poren-Spray, Poren einzeln, Adern folgen, Sommersprossen, Schmutz streuen, Kratzer
- seven, on the six **4a test alphas** (proposal §6.5 named eight, some on starter alphas - "Feine Falten", "Körnung"
need the starter set; they follow once Manu has accepted it, §14.5).

### 14.5 The starter set - `tools/make_starter_alphas.py`, contact sheet first (P-22, review point 6)

- A deterministic generator (fixed seeds, NumPy, our own work; every alpha with a black border, pinned): 22 alphas in
  P-22's seven categories - **Organisch** (Poren fein / grob / gruppiert, Falten kurz, Krähenfüße), **Adern** (verzweigt,
  Kapillaren), **Sprenkel** (Sommersprossen, Punkte gestreut, Sprenkel weich), **Schmutz** (Fleck, Schmutz, Ablagerung),
  **Schaden** (Kratzer, Narbe, Risse), **Oberfläche** (Körnung, Rauschen unregelmäßig), **Formen** (Kreis, Quadrat, Ring
  weich, Linie). Methods as §6.5 (jittered soft dots, branching tapered walks, thresholded fBm, Voronoi edges with width
  noise, noisy polylines, band-limited noise).
- **Contact sheets** (one per category + an overview):
  [`docs/research/alpha_brush_4c_assets_2026-11-26/`](../research/alpha_brush_4c_assets_2026-11-26/) - each alpha, a
  stamped strip (Einzeln, 100 % spacing) and a spray strip (12 stamps, random turn, size and flow jitter: the 4b
  randomness) across a neutral shaded sphere (the tangent-plane stamp with the depth window). Labels need Pillow
  (optional; it is not a dependency, `contact_sheet.md` names the rows).
- **Not adopted yet:** as decided ("starter alphas adopted only after the contact-sheet check"), no starter PNG is
  committed. `python tools/make_starter_alphas.py --adopt <categories>|all` writes the accepted categories into
  `assets/paint/alphas/` with `index.json` and `assets/paint/LICENSES.md` (generator named per file); the library picks
  them up as `builtin:<category>/<stem>` (pinned in a temporary folder).

### 14.6 Tests [C]

`tests/test_paint_library.py` (21: built-in presets load clean and resolve; the default preset is today's brush;
presets carry no colour / tool / mirror; round trip and "Größe behalten"; broken / foreign / out-of-range / unknown-field
/ name-taken files skipped with their reasons; built-ins read-only; save, rename, category, delete, favourites persist;
no user folder refuses; the missing alpha keeps its reference through a save; id → hash → name; the same image twice is
one alpha; **user assets in the user folder only**; source modes and the suggestion; refusals, the 1024 clamp and the
border warning; a 1024² import < 0.5 s; a dropped PNG; the contrast table; shaped alphas; the cache cap),
`tests/test_paint_presets_room.py` (8: the room starts on "Runder Pinsel"; choosing keeps colour, tool, mirror; keep
size; save as / save / built-in refusal / rename / delete; the import sets the tip and finds a second import; **a
missing alpha paints exactly as the round tip** and keeps its reference; a preset with a deleted alpha says so; contrast
changes the pixels), `tests/test_brush_picker_model.py` (8: favourites first, filter, search; the brush row's marker and
saving; "Alpha fehlt"; thumbnails; **50 thumbnails for the first open < 150 ms** without filling the alpha cache;
thumbnail files follow their alphas; the import card's model; a headless draw of the panel and the picker),
`tests/test_paint_starter_alphas.py` (2: deterministic, black borders, P-22's categories; `--adopt` → the library),
`tests/test_gui_imgui_window.py::test_paint_brush_picker_thumbnails_import_card_and_release` (the real window: both
tabs' thumbnails as GL textures, every thumbnail frame < 150 ms, the popup owns the mouse, GL state as found, the import
card's rectangle, an import into the user folder, the textures freed when the room closes). The 4a / 4b tests are
unchanged and green (one assertion on the removed 4a tip combo now reads the panel model's tip label).
Whole suite (container, xvfb, NumPy 2.2.6): `tests/` 8335 passed, 3 failed - the same 3 as on `922d964`, in 4a and in
4b (§12.5: the box-paint scenario, its `can_run` purity variant, `test_scene_menu_local_tmp::test_probe_menu_wiring`),
8 skipped.

### 14.7 Measurements [C] (container: Xeon, Python 3.13, NumPy 2.2.6, llvmpipe; `probe_paint_library.py`)

Verbatim in [`RESULTS_PAINT_PHASE4C_CONTAINER_2026-11-26.md`](../../experiments/drag_cost/RESULTS_PAINT_PHASE4C_CONTAINER_2026-11-26.md).

| Row | container | gate (reference PC) |
|---|---|---|
| **P-L** 1024² import (open + suggestion, preview, files written): smooth / noise / shape on transparency, max | 92 / 106 / 107 ms | ≤ 500 ms |
| P-L 4096² (clamped to 1024; information) | 0.61–0.75 s | — |
| **P-M** picker first open, 50 thumbnails: thumbnails + GL textures (llvmpipe) | 23 + 65 = 88 ms | ≤ 150 ms |
| P-M afterwards (every texture cached) | 0.15 ms per frame | no per-frame cost |
| **P-N** alpha cache, 60 imported 1024² alphas read | 64.0 MiB peak (48 held) | ≤ 64 MiB |

- **Change found by measuring (P-L):** the first build wrote user alphas as RGBA PNGs at zlib level 6: a 1024² noise
  alpha took 298 / 322 ms (p50 / max) - with the reference PC's ×2–3 [H] about the gate. They are 8-bit grey PNGs at
  level 3 now (`library.encode_grey_png`; read back by `decode_png`): 62 ms of writing.
- Expectation for the reference PC [H]: P-L ≤ ~0.3 s, P-M ~0.2 s of CPU for 50 at once **but** spread over frames by
  the 12 ms budget, so no frame of the first open should exceed ~30 ms; the run decides.

### 14.8 Not in 4c / open

- **Manu:** the contact sheets (§14.5) - which categories to adopt (then `--adopt`, the presets "Feine Falten",
  "Körnung" on them); the Praxistest below; the reference-PC run of `probe_paint_library.py` (and 4b's, §13.8).
- 4d (each its own decision): colour jitter (§5.8), the preset export bundle, CC0 alphas with a recorded licence, the
  wrap for spray clusters, lazy mouse.
- The room's last used brush is not remembered across sessions (view state, §6.1 "may"); the room starts on "Runder
  Pinsel".
- No key for the picker or brush cycling (a proposal for Manu's "Taste passt" after the practical test).

## Praxistest für Manu (Deutsch, ca. 5 Minuten, optional)

Phase 1 hat nur einen sichtbaren Teil, die UV-Prüfung:

1. `scenes/Gollum_Head_rigging_test.mirai.json` öffnen, den Kopf zum Edit-Objekt machen.
2. SPACE → **„UV-Prüfung“**. Die Statuszeile nennt 44 Flächen ohne UV-Fläche und 148 überlappende; rot leuchten die
   Extrude-/Inset-Wände (ohne UV-Fläche), orange die Überlappungen.
3. Prüfen: Sind das die Stellen, an denen Du nach dem UV-Erstellen modelliert hast (Wände, Ohr)? Ist die Färbung gut lesbar
   (Farben `PROVISIONAL`)? Noch einmal SPACE → „UV-Prüfung“ schaltet sie aus, die Gruppenfarben kommen zurück.

Kein Undo-Schritt, die Szene bleibt unverändert. Eine Taste dafür nur nach Deinem „Taste passt“.

## Praxistest Paint Room (Phase 2) für Manu (Deutsch, ca. 20 Minuten)

Meine Annahmen aus Deinen Entscheidungen (bitte in einem Satz korrigieren, wenn eine nicht stimmt): Malen = LMB ziehen nur
im Raum (P-6), Radius in Prozent des Objekts (P-7), 2048² als Start (P-5), Malen auf der gezeigten Fläche, mit SubD auf
der SubD-Fläche (P-10), Gesicht in Ruhe (P-8 entschieden 2026-11-25: Pose und Morph sind erlaubt).

1. `Gollum_Head_rigging_test` öffnen, den Kopf zum Edit-Objekt machen, SPACE → **„Paint Room öffnen“**. Die Statuszeile
   nennt die Fläche („malt auf dem Käfig, 2048²“), die Zeit für die Karte und die Flächen ohne malbare UV-Fläche. Ist die
   Wartezeit beim Öffnen in Ordnung?
2. Links das Panel „Paint Room“: Farbe wählen, auf Wange und Nase malen (LMB ziehen). Fühlt sich der Strich flüssig an,
   folgt der Kreis dem Cursor? Ist der Radius-Startwert (3 %) sinnvoll?
3. **Shift+Rad** (Radius), **Alt+Rad** (Deckkraft), Deckkraft 50 % und zweimal über dieselbe Stelle in *einem* Strich:
   bleibt es 50 %? Dann Fluss 30 %: baut es sich im Strich auf? Härte und Kurve ausprobieren.
4. Lippen und Lider: malt der Pinsel durch auf die Innenseite? (Er soll nur die Seite treffen, die Du siehst.)
5. Mit Spiegeln (Symmetrie-Ebene an, Shift+S geht auch im Raum): erscheint der zweite, gedimmte Kreis auf der anderen
   Gesichtshälfte und malt er dort mit? Der Kopf ist leicht asymmetrisch – trifft der Spiegel trotzdem die Haut?
6. Über eine UV-Naht malen (z. B. Mitte Stirn / hinter dem Ohr): Bruch oder Kante sichtbar?
7. **Esc** mitten im Strich: alles wie vorher? **Strg+Z**: ein Strich weg; der erste Strich weg = keine Bemalung mehr.
8. **SubD an** (V) und dort malen: ist der Tupfer auf der glatten Fläche rund? Danach SubD aus: auf dem Käfig ist er
   etwas oval (erwartet, §8.1).
9. **Pipette** im Panel, auf eine bemalte Stelle klicken: wird die Farbe übernommen, bist Du danach wieder bei „Malen“?
10. Strg+S im Raum, Raum schließen: Drahtgitter / Anzeige wie vorher? Die Bemalung bleibt sichtbar; Szene neu laden: ist
    sie wieder da? Im Ordner `<Szene>_textures/` liegt die Ebene und das `…_paint_flat_….png`.

Tasten, die Dir passen, bitte mit „Taste passt“ (für die Keymap); Panel-Aufbau und Werte sind vorläufig.

## Praxistest Ebenen und UV-Transfer (Phase 3) für Manu (Deutsch, ca. 15 Minuten)

1. `Gollum_Head_rigging_test` öffnen, Kopf als Edit-Objekt, SPACE → **„Paint Room öffnen“**, einen Strich malen (legt
   „Ebene 1“ an). Im Panel unten erscheint der Abschnitt **„Ebenen“**.
2. **Neu**: „Ebene 2“ liegt oben und ist aktiv (hervorgehoben). Eine andere Farbe malen. Klick auf „Ebene 1“: malt der
   nächste Strich wieder dort? Häkchen bei „Ebene 2“ weg: verschwindet sie, und lässt sich auf ihr (ausgeblendet) nicht
   malen?
3. „Ebene 2“ aktiv, **Mischmodus → Multiplizieren**, ein mittleres Rot oder Braun über die Wange: dunkelt es die Haut
   ab, statt sie zu überdecken? Passt das für Adern / Flecken?
4. **Ebenen-Deckkraft** ziehen: folgt das Bild beim Ziehen flüssig genug? (Auf einem stark bemalten Bild ist das der
   langsamste Teil, §11.4.) Nach dem Loslassen: **Strg+Z** nimmt die ganze Änderung in einem Schritt zurück?
5. **Hoch / Runter**, **Name** ändern (Enter), **Leeren**, **Löschen**, jeweils Strg+Z: alles wie vorher?
6. Zwei Normal-Ebenen, die obere auf 50 %: **Zusammenführen** – sieht das Bild danach genauso aus? (Mit verschiedenen
   Mischmodi ist der Knopf grau.)
7. Strg+S, Szene neu laden: alle Ebenen mit Deckkraft und Mischmodus wieder da? Das `…_paint_flat_….png` zeigt alle
   sichtbaren Ebenen.
8. **UV-Transfer:** den bemalten Kopf an ZBrush schicken, dort UV Master neu auswickeln, zurück nach Mirai, „Übernehmen“.
   (SPACE-Zeile „ZBrush übernehmen: …“). Die Statuszeile sagt „paint moved to the new UVs“. Liegt die Bemalung an derselben Stelle wie vorher (Lippen, Lider,
   Nähte)? Strg+Z: alte UVs und alte Bemalung zurück? Wie lange hat das Übernehmen gedauert?

Panel-Aufbau, Beschriftungen und die Grenze von 8 Ebenen sind vorläufig.

## Praxistest Alpha-Spitze (Phase 4a) für Manu (Deutsch, ca. 15 Minuten)

Vorher bitte den **Kontaktbogen** ansehen: `docs/research/alpha_brush_4a_assets_2026-11-25/` – je Bild acht Stellen am
Gollum-Kopf (Nasenspitze, Nasenrücken, Nasenflügel, Lippenkante, Mundwinkel, Wange, Lid, UV-Naht am Kinn) mit Poren, Ader
und Kratzer, Käfig und SubD 1, Radius 3 % und 5 %. Die Beschriftung sagt, ob der Stempel **eben** oder **gewickelt**
aufgelegt wurde. Sieht etwas gestreckt, abgeschnitten oder falsch aus?

1. `Gollum_Head_rigging_test` öffnen, Kopf als Edit-Objekt, SPACE → **„Paint Room öffnen“**. Im Panel ist neu
   **„Spitze“**. Erst mit **„Rund“** einen Strich malen: fühlt er sich an wie vorher (er soll gleich aussehen)?
2. **Spitze → Poren**. „Abstand“ springt auf 100 %. Über dem Kopf zeigt der Cursor ein **Rechteck** (gedimmter Kreis
   dazu). Ein paar Striche über die Wange und die Nase: sitzen die Poren auf der Haut, ohne Lücken und ohne Doppelungen?
   Abstand 50 % / 200 % probieren: ändert sich die Dichte auf der Haut, egal wie nah Du herangezoomt bist?
3. **Ader** und **Kratzer**: folgen sie Deiner Strichrichtung („Strich folgen“)? Mit „Winkel“ 90° quer stellen. Wirkt
   die Richtung über die Nase hinweg ruhig, oder dreht sie zu stark nach?
4. **Nasenflügel, Nasenspitze, Lippen, Mundwinkel, Lid** mit Poren und Ader (3 % und 5 %): wird etwas durch die Lippe
   auf die Unterlippe oder in das Nasenloch gemalt? Wirkt ein Stempel am Nasenflügel verzerrt? (Bei 3 % liegt er flach
   auf, ab 4 % wickelt er sich an stark gekrümmten Stellen um die Fläche – sieht man einen Unterschied?)
5. **Über die UV-Naht** (senkrecht durch die Gesichtsmitte, z. B. am Kinn): Bruch sichtbar?
6. **Spiegeln** an: erscheint auf der anderen Seite das gespiegelte Rechteck, und ist die Ader dort spiegelbildlich?
7. **Sehr schnell** quer über das Gesicht wischen und sofort loslassen: friert etwas ein? Läuft die Farbe kurz nach und
   wird dann fertig? Gibt es Lücken?
8. Direkt nach dem Loslassen **Strg+Z**: ist genau dieser Strich weg? Mitten in einem schnellen Strich (noch beim
   Nachlaufen) **Esc**: alles wie vorher?
9. „Kreismaske“ an: wird das Alpha rund abgeschnitten (Härte/Kurve erscheinen)? Für Poren sinnvoll, für Adern nicht?
10. **SubD an** (V), dasselbe nochmal: Unterschied zum Käfig?

Rückmeldung am liebsten mit einem Satz je Punkt. Die Test-Alphas sind nur zum Ausprobieren (die Starter-Sammlung kommt in
4c nach Deinem Blick auf einen eigenen Bildbogen); Panel-Aufbau und Werte sind vorläufig. Keine neue Taste.

## Praxistest Zufall, Streuung, Spray (Phase 4b) für Manu (Deutsch, ca. 15 Minuten)

Neu im Panel unter „Spitze“: drei **eingeklappte Abschnitte** – **Strich**, **Streuung**, **Spray** (Spray nur, wenn
„Spray“ gewählt ist). Eingeklappt zeigt jede Zeile eine Kurzfassung (z. B. „Streuung   Drehung ±180°, Größe ±30 %“). Ohne
Zufall, Streuung und Spray malt alles **bitgleich wie 4a**.

1. `Gollum_Head_rigging_test` öffnen, Kopf als Edit-Objekt, SPACE → **„Paint Room öffnen“**, Spiegeln an. Erst „Rund“
   wie bisher: gleich wie gestern?
2. **Poren-Spray auf Wange und Nase:** Spitze **Poren**, Radius 3 %, „Strich“ aufklappen → **Spray**. Der Abstand springt
   auf 50 %. „Spray“ aufklappen: Dichte 20, Stempelgröße 20 %. „Streuung“: Drehung ±180°, Größe ±30 %, Fluss ±30 %.
   Über Wange und Nasenrücken malen: sieht es wie Hautporen aus (kein Muster, keine Reihen)? Ist der Strich flüssig?
   **Ein Klick ohne Bewegung** = genau ein Sprühstoß; **Maus stillhalten** fügt nichts hinzu (P-28) – passt das?
3. **Sommersprossen:** Spitze **Punkte** (oder Rund) mit Spray, Dichte 5–8, Stempelgröße 30–40 %, Größe ±50 %, Fluss
   ±60 %, Deckkraft ~50 %, Farbe ein helles Braun; zusätzlich „Streuung quer“ 1,0 r. Ein paar Tupfer über Nase und Wangen:
   unregelmäßig genug? Fehlt etwas (z. B. Farbvariation – die kommt erst in 4d)?
4. **Adern mit Zufallsdrehung:** Spitze **Ader**, Einzeln, Abstand ~60 %, „Drehung ±“ 20–40°, Größe ±20 %. Ein Strich an
   der Schläfe / am Hals: wirkt die Ader verzweigter, weniger wie eine Kette gleicher Stempel? „Ausrichtung“ auf **Ansicht**,
   **Fläche** und **Zufall** umschalten: Unterschied sichtbar? (Fläche richtet sich nach der UV-u-Richtung, Ansicht nach
   „oben“ am Bildschirm.)
5. **Spiegel-Symmetrie des Zufalls:** mit Spiegeln einen Spray- und einen Ader-Strich auf eine Wange: ist die andere
   Seite das **Spiegelbild** (gleiche Poren, gespiegelt), nicht ein anderes Zufallsmuster?
6. **Streuung längs/quer** bis 2 r: die Stempel springen neben die Linie, aber nie weiter als 2 Radien; am Rand der Nase
   oder des Kinns fällt ein gestreuter Stempel, der neben das Objekt fiele, weg. Wirkt das natürlich?
7. **Undo:** Strg+Z nimmt genau einen Strich zurück, Strg+Y bringt **dasselbe** Muster wieder (nicht neu gewürfelt).
   Esc mitten im Strich: alles wie vorher?
8. Schneller Spray-Strich quer über das Gesicht und sofort loslassen: friert etwas ein? (Die Farbe darf kurz nachlaufen.)
9. **SubD an** (V) und dasselbe: Unterschied zum Käfig? Wenn Du magst: mit einer Pose / Morph-Mischung (Gesicht verzogen)
   malen – sitzen die Poren auf der verformten Haut?

Rückmeldung am liebsten mit einem Satz je Punkt; Werte, Bereiche und der Panel-Aufbau sind vorläufig (bis zum 4c-Picker).
Keine neue Taste.

## Praxistest Pinsel-Bibliothek (Phase 4c) für Manu (Deutsch, ca. 15 Minuten)

Neu oben im Panel: die **Pinsel-Zeile** (Vorschau, Name, „Pinsel …“) und darunter die **Spitze** mit Vorschaubild. Die
4a-Auswahlliste „Spitze“ ist durch die Auswahl ersetzt. Keine neue Taste.

0. **Kontaktbögen** (vorher, am Bildschirm): `docs/research/alpha_brush_4c_assets_2026-11-26/contact_sheet_*.png` –
   je Kategorie: übernehmen, nachbessern (was?) oder weglassen? Erst danach kommen Starter-Alphas ins Repo.
1. Gollum-Kopf, SPACE → „Paint Room öffnen“. Die Pinsel-Zeile zeigt **„Runder Pinsel (Grundformen)“** – malt er wie
   bisher?
2. **„Pinsel …“**: Reiter **Pinsel** – sieben Vorschaubilder. **„Poren-Spray“** wählen und über die Wange malen. Farbe,
   Werkzeug und Spiegeln bleiben, wie sie waren? Deckkraft ändern → „– geändert“ erscheint; **Zurücksetzen** holt die
   Werte zurück.
3. **Speichern als …**: Namen eintippen, Enter. Danach etwas ändern → **Speichern** überschreibt Deinen Pinsel. Ein
   eingebauter lässt sich nicht überschreiben (nur „Speichern als“) – passt das so?
4. **Größe behalten** (in der Auswahl) an, Radius 6 %, dann andere Pinsel wählen: bleibt 6 %? Aus: jeder Pinsel bringt
   seine Größe mit (P-20).
5. Reiter **Alphas**: ein Alpha anklicken setzt die Spitze des aktuellen Pinsels (der wird „geändert“). Rechtsklick auf
   einen Pinsel / ein Alpha: **Favorit** – steht er danach vorne, mit „* “? Suche („por“) und Kategorie-Filter.
6. **Alpha importieren …** (Reiter Alphas): ein eigenes Graustufen- oder freigestelltes PNG wählen. Stimmt die
   vorgeschlagene **Quelle** (Alphakanal / Luminanz / beides)? Invertieren / Kontrast in der Vorschau; ein Bild mit
   hellem Rand zeigt „Rand nicht schwarz“. **Importieren** → es ist sofort die Spitze. Dasselbe Bild nochmal importieren:
   „schon vorhanden“.
7. **Spitze**-Zeile: Invertieren und Kontrast am Fleck- oder Poren-Alpha ausprobieren – sinnvoll, oder überflüssig?
8. **Fehlendes Alpha:** einen eigenen Pinsel mit Deinem importierten Alpha speichern, dann das Alpha löschen (Rechtsklick
   → Löschen) und den Pinsel wählen: „Alpha fehlt: …“, er malt rund, nichts stürzt ab.
9. Ordner `~/.mirai_bastel/paint/` (Windows: `C:\Users\<Du>\.mirai_bastel\paint\`) ansehen: `alphas/`,
   `brushes/`, `library.json` – sonst nichts Neues, auch nicht neben der Szene.
10. **Referenz-PC:** `python experiments/drag_cost/probe_paint_library.py` (Import, erstes Öffnen, Alpha-Speicher) –
    die Ausgabe bitte ins Repo oder in den Chat.

Rückmeldung am liebsten mit einem Satz je Punkt; Aufbau und Werte sind vorläufig (P-23).
