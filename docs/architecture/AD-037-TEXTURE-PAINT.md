# AD-037 — Texture paint: storage, data model and foundations (Paint Room Phase 1)

**Status:** **DECIDED (Manu, 2026-11-18)**: „P-1 ja, P-2 ja, P-3 Go, P-4 ja, P-6 ja“ (the audit's addendum), the additive
Core change and scene format v14 included. **IMPLEMENTED Phase 1 (2026-11-18, container: TESTED)** as built in §2–§6.
**Reference-PC probes P-A … P-F: RUN (Manu, 2026-11-18)** — P-A, P-B, P-C, P-E pass; P-D (2.06 s at 2048²) and P-F
(7.4 / 9.4 s) failed and were worked on the same day (§7.1), the re-run is open. **Decisions P-7, P-10, P-13: Manu,
2026-11-18** (§1); the P-13 refusals are built (§8). **No Paint Room yet** (Phase 2): nothing in the app paints, no key,
no keymap entry.
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
- **Deine Entscheidungen P-7 (Welt-Radius), P-10, P-13** sind eingetragen; die P-13-Sperren sind gebaut: Attach eines
  bemalten Objekts ohne dieselbe Bemalung und eine ZBrush-Rückgabe mit neuen UVs auf einem bemalten Objekt werden mit
  Statuszeile abgelehnt.

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
| P-10 | Phase 2 paints **on the cage with SubD shown off** in the room; painting on the SubD surface is Phase 3 | Phase 2 room frame |
| P-13 | Faces without usable UVs (zero area, overlap, unmapped) are shown and skipped with a status line; **Attach is refused** when a painted object and its partner do not share that paint; **a GoZ return that changes a painted object's UVs is refused** until the UV transfer exists | the UV check (§4); the refusals (§8), built now |

Still open: P-5 (resolution; Phase 1 has no default, the caller names the size — 2048² is the audit's proposal; the
reference PC's P-D and P-A speak for 2048² as the default with 1024² as the fast option), P-8, P-9, P-11, P-12, P-14 …
P-17.

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

- **Phase 2** (P-2, P-6, P-7, P-10 decided): the room frame (enter / leave, view state saved and restored), the
  layer-A stroke session, the paint dab (radius, opacity, flow, hardness, curve; stroke buffer; seam padding; mirrored dab),
  cursor circle, Paint / Erase / Pick, the live texture wired to `take_changed`, status-line refusals (no UVs, eye, SubD).
- **P-13 refusals, built 2026-11-18:** `Application.attach_plan` refuses (status line, nothing changed, also with "take
  the destination's look") when the destination or a source is painted and they do not share that paint —
  `PaintStore.same_paint`: equal stacks and, where pixels are in memory, equal pixels (a detached part painted on its own
  has the same stack and other pixels); `apply_goz_return` refuses an in-place return that changes a painted object's UVs
  (`plan.uvs`). Tests: `tests/test_attach.py`, `tests/test_goz_bridge.py`. The "shown and skipped" part of P-13 is the UV
  check (§4) and, in Phase 2, the dab skipping those faces.
- Eyes (P-14), UV transfer (Phase 3), several layers in the UI, blend modes (P-12), undo budget (P-11).

## 9. Tests

`tests/test_paint_format.py` (Core values, v14), `test_paint_texel_map.py` (barycentric parity with the drawn triangles and
with `face_hit`'s `triangle_origin`, deformation invariance, patch == rebuild over 12 random topology / UV / rollback
sequences, ownership), `test_paint_uv_health.py` (each problem kind, islands / seams, density, the Gollum numbers),
`test_paint_store.py` (strokes, Undo / Redo, Esc, composite, copies, save / load round trip, Undo past a save, missing and
wrong-size images), `test_application_uv_check.py`, `test_live_texture.py`, `test_gl_texture.py` (live texture: shows,
box-only upload per policy, same as the file path, path draw unchanged), `test_gui_menus.py` (the SPACE row),
`experiments/drag_cost/tests/test_probe_paint.py`.

Full default run in the container (2026-11-18, `xvfb-run -a python -m pytest`): 7,707 passed, 8 skipped, 1 failed —
`tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring`, which fails the same way on the base commit `25154ac`
(not caused by this change).

## Praxistest für Manu (Deutsch, ca. 5 Minuten, optional)

Phase 1 hat nur einen sichtbaren Teil, die UV-Prüfung:

1. `scenes/Gollum_Head_rigging_test.mirai.json` öffnen, den Kopf zum Edit-Objekt machen.
2. SPACE → **„UV-Prüfung“**. Die Statuszeile nennt 44 Flächen ohne UV-Fläche und 148 überlappende; rot leuchten die
   Extrude-/Inset-Wände (ohne UV-Fläche), orange die Überlappungen.
3. Prüfen: Sind das die Stellen, an denen Du nach dem UV-Erstellen modelliert hast (Wände, Ohr)? Ist die Färbung gut lesbar
   (Farben `PROVISIONAL`)? Noch einmal SPACE → „UV-Prüfung“ schaltet sie aus, die Gruppenfarben kommen zurück.

Kein Undo-Schritt, die Szene bleibt unverändert. Eine Taste dafür nur nach Deinem „Taste passt“.
