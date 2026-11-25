# AD-037 — Texture paint: storage, data model, foundations (Phase 1), the Paint Room (Phase 2), layers and UV transfer (Phase 3)

**Status:** **DECIDED (Manu, 2026-11-18)**: „P-1 ja, P-2 ja, P-3 Go, P-4 ja, P-6 ja“ (the audit's addendum), the additive
Core change and scene format v14 included. **IMPLEMENTED Phase 1 (2026-11-18, container: TESTED)** as built in §2–§6.
**Reference-PC probes P-A … P-F: RUN (Manu, 2026-11-18)** — P-A, P-B, P-C, P-E pass; P-D (2.06 s at 2048²) and P-F
(7.4 / 9.4 s) failed and were worked on the same day (§7.1), the re-run is open (its output has not reached the repo yet).
**Decisions P-7, P-10, P-13: Manu, 2026-11-18** (§1); the P-13 refusals are built (§8). **IMPLEMENTED Phase 2, the Paint
Room (2026-11-18, container: TESTED; reference PC: P-A … P-G pass on the shown surfaces, §10.8e)** as built in §10: SPACE menu row, no key, no keymap entry.
**Phase 3 scope and P-12: Manu, 2026-11-19** (§1). **IMPLEMENTED Phase 3, several layers, Multiply and the UV transfer
(2026-11-19, container: TESTED; reference PC: not run yet)** as built in §11; the P-13 refusal of a GoZ UV change is lifted.
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
  Abgelehnt bei Augen (P-14), ohne UVs, im Bearbeitungsfenster eines Morph-Ziels und **in einer Pose** (P-8 ist für die
  Pose offen). Ein eingeblendeter Morph (z. B. mouth_open, um im Mund zu malen) ist erlaubt (Manu 2026-11-25).
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

Still open: P-8, P-9, P-11, P-14 … P-17.

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
  UVs, another interaction running, a morph target's editing view, and a **posed surface** (P-8 stays open for the pose;
  show the rest pose first). A **morph mix above 0 %** is allowed on entry (Manu 2026-11-25: „Es muss also erlaubt sein,
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
  last sample always (audit §8.1). The falloff: full inside the hardness plateau, then the chosen Soft curve to 0 at the
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
budget (P-11: before-tiles only, compressed, unlimited), painting a posed surface (P-8, refused; a morph mix is allowed since 2026-11-25), eyes (P-14,
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

Painting a posed / morphed surface (P-8) and symmetry in a pose (P-9), Blur / Smudge, face regions / Mask Geometry as
paint masks, the 2D UV view (all audit Phase 3, not chosen for this slice), layer masks, more blend modes, the undo budget
(P-11: the layer steps hold compressed snapshots - 16 MiB raw per layer at 2048², a fraction compressed), a UV transfer
for a later Mirai UV tool (the function takes any old / new UVs of one topology), keys (after "Taste passt").

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
der SubD-Fläche (P-10), Gesicht in Ruhe (P-8 offen: in einer Pose lehnt der Raum ab).

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
