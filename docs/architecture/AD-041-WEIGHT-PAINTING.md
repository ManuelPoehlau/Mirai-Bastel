# AD-041 — Weight painting: a Weight Room with a weight brush, fill from a selection, L/R bone pairs

**Status:** **ACCEPTED (Manu, 2026-11-26: „W-1 bis W-12 wie empfohlen, AD-041 freigegeben“)**: every W-point of §10 as recommended.
Was PROPOSED the same day. Direction decided by Manu on 2026-11-26 (Development chat):
- „Eigener Weight-Modus“;
- „Regionen entkoppeln, Füllung behalten“;
- brush operations Add / Subtract, Smooth / Blur, Replace and „Aufräumen“ in the first build;
- „Gleich mit L/R-Paaren“.

Slice 1 (the brush arithmetic) is built (2026-11-26, §13); slice 2 (the Weight Room) is next.

**Mode:** Production, in fresh sessions with this AD as the handoff (§11).
**Baseline:** `claude/serene-dirac-9sue6z` @ `3c9c80c`.
**Extends:** [AD-028](AD-028-SKELETON-AND-SKINNING.md). This AD lifts its §0 „No weight brush in this phase“, §8.4's refusal of off-centre bones under symmetry, and two §15 items („Weight brush“; „bone mirroring (L/R) and symmetric weights of off-centre bones“). See the [AD-028 addendum 2026-11-26](AD-028-SKELETON-AND-SKINNING.md#addendum-2026-11-26-weight-painting-ad-041).
**References:**
- [AD-028](AD-028-SKELETON-AND-SKINNING.md) §3.3, §3.4, §7.1, §8.4, §8.6 and the weight-view addendum
- [AD-037](AD-037-TEXTURE-PAINT.md) Phase 2 and 4a (the Paint Room, the stroke buffer, the stroke queue)
- [AD-020](AD-020-SOFT-SELECTION-APP-PATH.md)
- [AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md) and [AD-SYM-04](AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md)
- [AD-REGIONS-01](AD-REGIONS-01-FACE-REGIONS-STORAGE.md)
- [AD-030](AD-030-GUI-FRAMEWORK.md)
- [CORE_V1_FREEZE](CORE_V1_FREEZE.md) §4 and §7
- [Brush research 2026-11-18](../research/BRUSH_SYSTEM_FEASIBILITY_AND_ARCHITECTURE_RESEARCH_2026-11-18.md) §3 and §4.1
- [CHARACTER_SYSTEMS_RESEARCH](../research/CHARACTER_SYSTEMS_RESEARCH.md) O-06
- [GUI_Bestandsaufnahme](../design/GUI_Bestandsaufnahme.md) L10

**Tags:** **[V]** verified in code at the baseline · **[H]** estimate · `PROVISIONAL` = an agent choice the Artist has not verified.

## Kurzfassung für Manu (Deutsch)

**Ausgangslage.** Das Datenmodell der Gewichte ist schon richtig und bleibt unverändert:
- Jedes gebundene Mesh trägt einen Gewichts-Layer mit 1–4 Knochen-Anteilen pro Punkt.
- Der Layer läuft durch Undo, Datei und alle Topologie-Werkzeuge.
- Gefehlt hat nur das Werkzeug, um Gewichte *direkt* zu bearbeiten.

Die Gruppe „Kiefer“ war nur der Startpunkt der Geste „Gewichte aus Gruppe“. **Der Core ändert sich nicht.**

**Was neu kommt:**

1. **Weight Room.** Ein eigener Raum wie der Paint Room. Einstieg über die SPACE-Zeile „Gewichte malen“ und einen Button im Bone-Panel, keine neue Taste.
   - Im Raum malst du mit LMB auf der *gezeigten* Fläche, in Ruhe und in der Pose.
   - In der Pose bewegt sich der Kiefer schon beim Malen mit.
   - Jeder Strich ist ein `Strg+Z`; `Esc` bricht den laufenden Strich exakt ab.
2. **Pinsel.** Add (aufmalen), Subtract (wegnehmen, der Rest geht an den Eltern-Knochen wie bisher), Replace (auf einen Wert malen) und Smooth (glätten).
   - Einstellbar: Radius, Stärke und Härte.
   - Optional „nur zusammenhängend“, damit z. B. die Oberlippe die Unterlippe nicht mitnimmt.
3. **Heatmap.** Der Anteil des aktiven Knochens wird pro Punkt gefärbt und deckend angezeigt, nicht mehr als blasse Flächenfärbung.
   - Die Soft-Zone hat ihre eigene Färbung; die Doppelbelegung aus L10 entfällt.
4. **Füllen aus Auswahl.** Ersetzt „Gewichte aus Gruppe“.
   - Es wirkt auf jede Punkt- oder Flächenauswahl. Eine Gruppe ist nur noch *eine* Art, etwas auszuwählen.
   - Danach malst du nach.
5. **Aufräumen.** Kleine Restanteile unter einer Schwelle werden entfernt (ein `Strg+Z`).
6. **L/R-Knochen.** Knochen, die auf `_Links`/`_Rechts`, `.L`/`.R`, `_L`/`_R` oder `Left`/`Right` enden und gespiegelt liegen, bilden ein Paar.
   - Mit Symmetrie malt ein Strich links auf „Wange_Links“ und rechts gespiegelt auf „Wange_Rechts“.
   - Das neue Bone-Werkzeug „Knochen spiegeln“ legt die Gegenseite einer Kette an.
   - Ein seitlicher Knochen ohne Partner bleibt unter Symmetrie gesperrt, mit einem klaren Hinweis.

**Reihenfolge:**
- Scheibe 1: Pinsel-Rechnung, ohne Fenster testbar.
- Scheibe 2: Raum, Heatmap und Panel.
- Scheibe 3: Füllen aus Auswahl.
- Scheibe 4: L/R-Paare.
- Scheibe 5: Messung und dein Praxistest.

Deine Entscheidungen brauche ich zu W-1 … W-12 in §10. Die Empfehlung steht jeweils dabei.

## 1. Facts (verified at `3c9c80c`)

- **F-1 [V]** Weights already are a per-mesh point layer.
  - `LayerKind.WEIGHTS` (`src/core/mesh.py:99`) holds values `((BoneId, w), …)`: at most `WEIGHTS_WIDTH = 4` pairs, `0 < w`, `Σw ≤ 1`, and the object's share `1 − Σw` is implicit (`_weights_value`, `mesh.py:183`).
  - Storage is `PackedWeights` (`src/core/layer_storage.py:254`).
  - New and merged points combine through `_combine_weights` (`mesh.py:227`); journal and Undo use `MeshChange.layer_values`.
  - The file stores the layer as `point_layers[…]["kind"] == "weights"`.
- **F-2 [V]** The write rule is `set_bone_weight` (`src/mirai/skin_weights.py:40`).
  - Raising scales the other shares; lowering gives the freed share to the parent, or to the object for a root.
  - Above four keys, the smallest are dropped and their mass is redistributed.
- **F-3 [V]** `WeightStroke` (`skin_weights.py:98`) computes each step from the values at the press, so a gesture is path-independent within itself.
  - `step()` iterates *all* pressed vertices on every call.
  - That is fine for a gesture over a fixed set; for a brush stroke the touched set only grows, and each step would cost O(touched).
- **F-4 [V]** Weights come only from two hold gestures.
  - `FalloffGesture` (key 7): its seeds are the active group's live faces (`controllers/skeleton.py:1455-1473`); without a group it refuses with „make a group (Ctrl+G)“.
  - `WeightGesture` (key 8) sets a value on the selection, with Soft.
  - Both run `_WeightsGesture` (`skeleton.py:359-501`): masking, symmetry for bones on the plane only (`_on_plane`), one `MeshDeltaCommand` per gesture, Esc = `rollback_change`.
- **F-5 [V]** The skin stage `SkinSurface` (`src/mirai/skinning.py:265`) patches only what changed.
  - It follows layer writes through `Mesh.watch()` (`change.layer_values`).
  - A weight write while posed therefore shows live, without rebuilding the whole surface.
- **F-6 [V]** Picking, selection and paint already hit the posed surface: `Application._query_cage` / `_shown_cage` (AD-028 addendum 2026-11-17).
  - Weight commands are allowed in pose mode (`POSE_MODE_ALLOWS`, `skeleton.py:99`).
  - Position and topology edits there stay refused (AD-028 §7.1).
- **F-7 [V]** The weight view (key 9) shows the current bone's share.
  - It sends the share as *face* shading through the Soft display sink (`_soft_show(…, "faces")`).
  - Source: `ShareCache` (`skeleton.py:616`) behind a mesh watch.
  - Ramp: `soft_selection/shading.py`, blue → red with alpha 0.12–0.45.
  - `GLSoftShadingOverlay` has a per-vertex RGBA attribute and a cage source for the pose.
- **F-8 [V]** The Paint Room (AD-037) provides:
  - an exclusive session, `PaintRoomSession` (`controllers/paint_room.py:119`);
  - room open/close with display save and restore (`Application.open_paint_room` / `close_paint_room`);
  - a stroke buffer `S ← S + (1−S)·flow·c` with an opacity cap (`paint/brush.py:244`, `PaintStroke`);
  - `falloff(x, hardness, curve)` (`brush.py:211`);
  - `StrokeQueue` (`paint/dynamics.py`: world arc-length spacing and a per-frame budget);
  - a ray hit on the shown surface;
  - panels usable during the session through `PANEL_USABLE_OWNERS` (`src/gui/imgui_layer.py:35`).
- **F-9 [V]** A Soft field over the whole mesh costs about 50–77 ms at 87.5k vertices (brush research §4.1). A geodesic footprint per dab is therefore out.
- **F-10 [V]** Bones have unique names (`core.rig.Bone`, `Rig` validates). Real scenes use German side names: `Gollum_Head_rigging_test` has „Auge_Links“ and „Auge_Rechts“ (AD-028 Praxistest Bone-Werkzeug 01, step 7). The symmetry plane is declared per mesh in mesh-local space (`Mesh.symmetry_definition`, AD-SYM-01); bones live in world space (AD-028 §3.1).

## 2. Decision in one screen

| Topic | Decision (proposed) |
|---|---|
| Data | Unchanged: the WEIGHTS layer, the write rule F-2, no Core change, no new format version |
| Where | A **Weight Room**: an exclusive session like the Paint Room, entered from the SPACE row „Gewichte malen“ and the Bone panel, no new key (W-1) |
| Brush | Add / Subtract / Replace from the press values (a press cache per stroke, only footprint vertices per step); Smooth on the current values (W-2) |
| Footprint | A euclidean sphere on the shown cage around the surface hit, optionally only the part connected to the hit face inside the sphere (W-3) |
| Display | A per-vertex heatmap of the active bone, opaque, in its own look (W-4); the face-shaded weight view (key 9) stays for outside the room |
| Bone choice | Panel list, a click on a bone line, Ctrl+LMB on the surface picks the dominant bone (W-5) |
| Fill | „Füllen aus Auswahl“ replaces „Gewichte aus Gruppe“: the seeds are the selection, and a group is only a way to select (W-6) |
| Clean | „Aufräumen“: shares below a threshold go to 0 by the write rule, all bones, one Undo step (W-9) |
| Pairs | L/R pairs derived from names plus a geometric check, no Core field (W-7); the „Knochen spiegeln“ tool (W-8); mirrored writes for brush, fill, set weight and clean; seam vertices of an off-centre pair written jointly (W-12) |
| Pose | Painting in the pose is allowed: it writes weights only, and AD-028 §7.1 refuses positions and topology, not weights (W-10) |

## 3. The brush arithmetic (`src/mirai/weight_paint.py`, pure)

### 3.1 Footprint

- A dab is a hit point `p` with normal `n` on the **shown** cage (posed and morphed): `Application._query_cage` plus `viewport/picking.face_hit`.
- The candidate vertices are those within world radius `r` of `p`, taken from the shown cage's positions with NumPy. A cluster cull like `PaintSurface`'s can follow if a measurement asks for it.
- **Connected only** (W-3): from the candidates, keep those reachable from the hit face's vertices over edges whose two ends are both candidates. This uses a BFS limited to the candidates, never the whole mesh. It is what separates the upper lip from the lower lip.
- **Front only**: off by default. When on, it drops candidates whose vertex normal faces away from the view (`n_v · view < 0`).
- Coverage per vertex is `c(v) = falloff(|v − p| / r, hardness, curve)` with `paint.brush.falloff`.
- Masked or hidden vertices get `c = 0`. This uses `services.mask_values` and `regions.group_lock`, as `_WeightsGesture._masked` does.
- The radius is a percentage of the edit object's bounding radius, as in the Paint Room (`BrushSettings.radius_step`).

### 3.2 Stroke buffer and operations

- Per stroke there is a coverage buffer `S(v) ∈ [0, opacity]`, updated per dab as `S ← S + (1 − S)·flow·c` and then capped at the opacity. This is the `PaintStroke` semantics: one long stroke never paints past the opacity.
- **Add, Subtract and Replace** are functions of the press value and `S`. With `old` = the bone's share at the press:
  - Add: `x = old + S·(1 − old)`
  - Subtract: `x = old·(1 − S)`
  - Replace: `x = soft_target(old, value, S)`, which is `old + S·(value − old)`

  The new value is `set_bone_weight(press value, bone, x)`. The result depends only on the press values and `S`, not on the order of dabs. Esc restores exactly through `rollback_change`.
- **WeightStroke for a brush.** A variant `BrushWeightStroke`:
  - caches a vertex's press value on its *first* touch;
  - writes only the vertices in the current dab's footprint.

  This is equivalent to F-3 because `S` never decreases outside a footprint, so untouched vertices keep their value. Cost per dab is O(footprint) (F-3).
- **Smooth** works on the *current* values, because smoothing is iterative by nature. Per dab, for each footprint vertex: `x = cur + c·flow·(avg_{u∈N(v)} cur_b(u) − cur)`, followed by `set_bone_weight(current value, bone, x)`.
  - `N(v)` is the edge neighbourhood, built for the footprint only.
  - Smooth is path-dependent within a stroke (`PROVISIONAL`, the usual behaviour). Esc stays exact, because it rolls back the recording.
- **One bone at a time.** Every operation writes the active bone through F-2, so the other shares follow the AD-028 rule. A „normalize across all bones“ mode is not proposed: F-2 already keeps `Σw ≤ 1`, and the object share is meaningful (a vertex can stay on the head).

### 3.3 Clean („Aufräumen“, W-9)

- For every vertex of the edit mesh and every bone with `0 < w < threshold`, the bone is set to 0 through `set_bone_weight`. The share goes to the parent, or to the object for a root.
- The threshold defaults to 0.01 (`PROVISIONAL`).
- The whole operation is one recording and one Undo step, and respects the mask.

### 3.4 Fill from a selection (W-6)

- `FalloffGesture` stays as the mechanism (a Soft field, width by mouse or a panel value, replacing the bone's share). Only its seeds change: the selected vertices (the selected faces' vertices in face mode) instead of the active group's faces.
- An empty selection refuses with „Punkte oder Flächen auswählen“.
- A group is still one click away: select it (Outliner / region click).
- `Application.weights_from_group_value` becomes `fill_weights_value`. `WEIGHTS_FROM_GROUP` becomes `WEIGHTS_FILL`, with the text „Füllen aus Auswahl“. The code default key 7 stays until Manu decides.
- `test_jaw_scenario.py` moves to „select the jaw group → fill“.

## 4. The Weight Room (`src/mirai/controllers/weight_room.py`)

- **Session.** `WeightRoomSession` is modelled on `PaintRoomSession`, with owner `"weight"`.
  - LMB press starts a stroke, drag adds dabs through `StrokeQueue`, release ends it. Esc cancels the running stroke.
  - The wheel and modifier keys work as in `PAINT_CONTEXT`: Alt+wheel for strength, as the Paint Room's opacity; Shift+wheel for radius (`PROVISIONAL`, W-11).
  - Orbit, pan and zoom stay free. The room's cursor is a circle on the surface, as in the Paint Room's `_show_cursor`.
- **Recording.** Each stroke runs `mesh.begin_change()`, then `end_change()`, then one `MeshDeltaCommand` on the history.
  - The „Skin“ layer is created inside the first stroke's recording if absent (`skeleton.py:403`).
  - Without a rig or a current bone the room opens, but painting is refused with the reason in the HUD.
- **Open / close.** `Application.open_weight_room` / `close_weight_room` follow the Paint Room pattern: they save the display state (weight view, Soft preview, overlays) and restore it on close.
  - Open requires a mesh edit object in a component mode.
  - Rule R-1 of AD-038 holds: open and close never reset pose, morph, gaze or SubD.
- **Gate.** The room's commands are class `RIG` in `layer_declarations.py` (the enumeration test enforces this). They join `POSE_MODE_ALLOWS` (W-10).
- **Pose.** The room keeps the pose and the pose-mode toggle (key 6 / panel). While posed, `SkinSurface` patches only the painted vertices (F-5).
- **Symmetry.** The room uses the edit mesh's symmetry toggle as every edit does. §6 gives the write rule.

## 5. Display

- **Heatmap.** In the room, the active bone's share is shown per vertex (no fan-split face colour) through `GLSoftShadingOverlay` with its cage source (F-7), so it follows the pose.
- **Look.** A new look `WEIGHTS` in `soft_selection/shading.py` (W-4):
  - opaque (alpha 0.85, `PROVISIONAL`);
  - a dark neutral grey at exactly 0, so „no share“ reads differently from „a little“;
  - blue → green → yellow → red from > 0 to 1.
- **Updates.** The heatmap is recomputed per dab only for the written vertices, through the `ShareCache` watch (incremental: the watch names the `(layer, vertex)` keys).
- **Outside the room.** Key 9 and the face shading stay as in the AD-028 addendum (unchanged). Whether the weight view also switches to the per-vertex look is W-4b.
- **HUD.** Entry „Weight Room · <Knochen> · <Operation>“ and the reason when painting is refused.

## 6. L/R pairs and mirrored writes (`src/mirai/bone_mirror.py`)

- **Pairing (W-7).**
  - A bone name ends with a side token. Case-insensitive, separator `_`, `.` or space, and the list is fixed in code: `Links`/`Rechts`, `L`/`R`, `Left`/`Right`.
  - The partner is the bone with the same stem and the other token.
  - Geometric check: under the edit mesh's symmetry plane (mapped to world through the object placement), the partner's head and tail lie within `max(seam tolerance, 1 % of the bone length)` (`PROVISIONAL`) of the mirrored head and tail.
  - A name match that fails the check is not a pair, and the HUD names it („Wange_Rechts liegt nicht gespiegelt“).
  - A bone on the plane (AD-028 §8.4 `_on_plane`) is its own partner.
  - This is derived each time from the rig and the mesh (it is cheap: a few bones). No field on `core.rig.Bone` is added, so there is no CORE_V1_FREEZE §7 step and no format change.
- **Mirrored write.** Under symmetry, a write of bone `b` with target `x` at vertex `v` also writes `mirror(b)` with the same `x` at `partner(v)` (`symmetry.vertex_correspondence`). For the brush, „same `x`“ means the partner gets the mirrored coverage: `S(partner(v)) = S(v)`, just as the Paint Room's `mirror()` stamps the mirrored dab. This applies to the brush, fill, set weight and clean.
- **Seam vertices (W-12).**
  - Concerns a vertex that is its own partner and lies in the footprint of an off-centre bone `b` whose partner `b′ ≠ b`.
  - Writing `b` and then `b′` would be asymmetric: the second raise scales the first down.
  - The pair is written jointly instead: the pair's sum is set to `x`, split equally, so `b = b′ = x/2`.
  - Implementation: `set_bone_weight` on a virtual pair key, with the other shares scaled or donated by the same rule.
  - `PROVISIONAL`; the effect is limited to the seam row.
- **Refusal.** An off-centre bone without a partner under symmetry is still refused, now with „braucht Spiegel-Knochen – ‚Knochen spiegeln‘ im Bone-Panel“.
- **„Knochen spiegeln“ (W-8).** A Bone-panel button, at rest only. It mirrors the current bone and its descendants across the edit mesh's symmetry plane, or the world YZ plane when no mesh declares one (`PROVISIONAL`).
  - Names: `Wange_Links` → `Wange_Rechts`. A name without a side token refuses: „Name braucht eine Seite (_Links …)“.
  - Parent: the mirror of the parent if it exists, else the same parent (an on-plane parent like „Hals“).
  - Roll is mirrored so that the bone-local axes mirror.
  - If a partner already exists, it is updated, not duplicated.
  - The operation is one `RigCommand` (one Undo step); no weights are written.
  - Mirroring *weights* of an existing side onto the other is a separate panel action, „Gewichte spiegeln (L → R)“: one recording, the §6 write over the whole mesh for the chosen bones.
- **Out of scope:** pose symmetry (posing L also poses R); AD-028 S8 (a mirror copy of a weighted mesh stays refused); more than one symmetry plane.

## 7. Panel (`src/gui/weight_panel.py`, `weight_model.py`)

- Headless model and drawing panel, as AD-030 requires: the panel reads state and calls `Application`, and holds no document state.
- **Contents:**
  - the bone list with the active bone and the hidden flag;
  - the operation (Add / Subtract / Replace / Smooth) and the Replace value;
  - radius, strength (flow), hardness and opacity;
  - „nur zusammenhängend“ and „nur Vorderseite“;
  - symmetry on/off and the pair status of the active bone;
  - „Füllen aus Auswahl“ with its width;
  - „Aufräumen“ with its threshold;
  - „Gewichte spiegeln“;
  - Ruhe / Pose;
  - „Raum schließen“.
- The owner `"weight"` joins `PANEL_USABLE_OWNERS`. The Bone panel gets „Gewichte malen …“ (opens the room) and „Knochen spiegeln“.
- Brush settings live for the session only, as the Paint Room's do without presets. Presets are not proposed.

## 8. Performance (W-11, to be measured in slice 5)

- **Per dab, the cost is:**
  - the hit (vectorised);
  - the candidate query (O(n) NumPy over the cage positions);
  - the connected BFS (O(footprint));
  - the writes (Python, `set_layer_value` per vertex);
  - the skin patch (F-5);
  - the heatmap patch.
- **Bar (`PROVISIONAL`):** one dab ≤ 16.7 ms on the reference PC at a footprint of 1,000 vertices on the 87.5k body. The container must stay below half of that (REFERENCE_HARDWARE §2: Python there ≈ 2× slower).
- If the per-vertex writes dominate, the first lever is a batch write of one layer for many vertices. That would be a Core API addition and needs its own §7 step.

## 9. Effect on decided documents

- **AD-028:** the addendum 2026-11-26 lifts §0 „No weight brush“, the §8.4 symmetry refusal (now: refused only without a partner), and the §15 items „Weight brush“ and „bone mirroring (L/R) and symmetric weights of off-centre bones“. The rest of AD-028 is unchanged: data model, write rule, evaluation, §7.1.
- **AD-REGIONS-01:** unchanged. Regions are no longer the seed of a weight operation; they remain a selection source.
- **CORE_V1_FREEZE:** no entry; no Core change.
- **ATELIER, ROADMAP (Rigging Foundation), architecture README:** one line each (this commit).
- **`config/keymap.json`:** untouched. Keys only after Manu's word (CLAUDE.md, AD-013 addendum 2026-10-28).

## 10. Decisions for Manu (Entscheidungen, Deutsch)

**Entschieden 2026-11-26 (Manu): „W-1 bis W-12 wie empfohlen“** – jede Zeile gilt mit ihrer Empfehlung. Die Werte bleiben
`PROVISIONAL`, bis der Praxistest (Scheibe 5) sie bestätigt; Tasten erst danach in `config/keymap.json`.

| # | Frage | Empfehlung |
|---|---|---|
| W-1 | Einstieg in den Weight Room | SPACE-Zeile „Gewichte malen“ und Button im Bone-Panel, **keine Taste** (wie Paint Room) |
| W-2 | Pinsel-Rechnung | Add / Subtract / Replace aus den Werten beim Drücken (Strich-Puffer mit Deckkraft-Grenze wie im Paint Room), Smooth auf den aktuellen Werten |
| W-3 | „Nur zusammenhängend“ | **an** als Standard (Lippen, Lider); „nur Vorderseite“ aus |
| W-4 | Heatmap-Farben | deckend; 0 = dunkles Grau, darüber Blau → Grün → Gelb → Rot. W-4b: die Gewichtsansicht `9` außerhalb des Raums bleibt vorerst Flächenfärbung |
| W-5 | Knochen wählen | Liste im Panel, Klick auf die Knochenlinie, **Strg+LMB** auf der Fläche = stärkster Knochen dort |
| W-6 | Füllen | „Füllen aus Auswahl“ ersetzt „Gewichte aus Gruppe“; leere Auswahl wird abgelehnt; Taste `7` bleibt bis zu deinem Wort |
| W-7 | L/R-Namen | Endungen `_Links`/`_Rechts`, `.L`/`.R`, `_L`/`_R`, `Left`/`Right` (groß/klein egal) plus Lageprüfung; kein neues Feld im Core |
| W-8 | „Knochen spiegeln“ | spiegelt Knochen und Kinder, Name braucht eine Seite, Parent wird gespiegelt, wenn vorhanden; vorhandener Partner wird aktualisiert |
| W-9 | Aufräumen | Schwelle 0,01, alle Knochen, ein `Strg+Z` |
| W-10 | Malen in der Pose | ja (nur Gewichte; Verschieben und Topologie bleiben in der Pose gesperrt) |
| W-11 | Rad und Leistung | Shift+Rad = Radius, Alt+Rad = Stärke im Raum; Ziel ≤ 16,7 ms pro Tupfer auf deinem PC |
| W-12 | Punkte auf der Mittelnaht bei L/R-Paaren | das Paar teilt sich den Wert je zur Hälfte (symmetrisch exakt) |

## 11. Implementation plan and Definition of Done

| Slice | Content | Files | Tests |
|---|---|---|---|
| 1 | Brush arithmetic: footprint, connected filter, stroke buffer, Add / Subtract / Replace / Smooth, `BrushWeightStroke`, clean | `src/mirai/weight_paint.py`, `skin_weights.py` | `tests/test_weight_paint.py`: W1–W4 after every op, `Σw ≤ 1`, ≤ 4 keys, parent rule, path-independence of Add / Subtract / Replace, mask, Esc exact, cost per dab O(footprint) |
| 2 | Weight Room: session, open/close, recording per stroke, heatmap look, panel, bone choice, pose | `controllers/weight_room.py`, `application.py`, `soft_selection/shading.py`, `gui/weight_panel.py`, `gui/weight_model.py`, `gui/imgui_layer.py`, `layer_declarations.py`, `controllers/skeleton.py` | `test_weight_room.py` (one Undo per stroke, painting posed shows live, refusals), `test_gui_weight_panel_model.py`, `test_layer_gate.py`, `test_gl_soft_shading.py` (xvfb) |
| 3 | Fill from a selection; the jaw scenario moved | `controllers/skeleton.py`, `gui/bone_model.py`, `gui/bone_panel.py`, `interaction/commands.py` | `test_application_rig.py`, `test_bone_edit.py`, `test_jaw_scenario.py` |
| 4 | L/R pairs, mirrored writes (incl. W-12), „Knochen spiegeln“, „Gewichte spiegeln“ | `src/mirai/bone_mirror.py`, `controllers/skeleton.py`, `controllers/bone_chain.py`, `gui/bone_*.py` | `test_bone_mirror.py`: pairing (German names), geometric check, mirrored brush / fill / set / clean exactly symmetric, seam pair, the tool's Undo |
| 5 | Measurement (§8) on head and body; Praxistest for Manu | — | probe under `experiments/drag_cost/` |

**DoD per slice:**
- the targeted tests are green, plus `test_application_rig.py`, `test_weight_view.py`, `test_skin_weights.py` and `test_layer_gate.py`;
- this AD carries an implementation note;
- ATELIER is updated;
- no change under `src/core/`.

## 12. Not in scope

- automatic weights (heat, geodesic binding), envelopes;
- weight layers (CHARACTER_SYSTEMS O-06);
- more than four influences;
- pose symmetry;
- a mirror copy of weighted meshes (AD-028 S8);
- weight transfer between meshes (AD-025 Phase 7);
- brush presets and alpha tips for weights;
- a GPU skinning path;
- `config/keymap.json` entries before Manu's word.

## 13. Implementation notes

### Slice 1 — the brush arithmetic (2026-11-26)

- **Built:** `src/mirai/weight_paint.py` (pure, headless): `WeightBrushSettings`, `VertexCloud` (the shown cage's
  positions as one array; `refresh()` re-reads a `SurfacePositions`, a rest `Mesh` keeps its rows), `footprint()`
  (§3.1: sphere, `paint.brush.falloff`, connected only by a BFS limited to the candidates, front only by vertex normals
  on the cage) and `BrushWeightStroke` (§3.2: press cache at first touch, stroke buffer, Add / Subtract / Replace,
  Smooth). `skin_weights.clean_weights` / `clean_value` (§3.3). No change under `src/core/`.
- **Stroke buffer, as built:** `C <- C + (1 - C)·flow·c` per dab and `S = opacity·C` - exactly `PaintStroke`'s rule
  (AD-037 Phase 2). §3.2's wording "S capped at the opacity" reads the same at opacity 1 and differs only in how a
  flow below 1 approaches a lower opacity (asymptotically here, a hard stop there); the Paint Room's feel won because
  Manu has tested it. `PROVISIONAL`.
- **Mask:** `S·(1 - m)` (Smooth: `c·flow·(1 - m)`), `m >= 1` keeps the value - the same as `_WeightsGesture._masked`
  for linear targets. Clean protects any vertex with `m > 0` (a threshold cut has no partial form; `PROVISIONAL`).
- **Clean:** the smallest share below the threshold first, repeated per vertex until none is left; a parent that
  receives a small share passes it on up to the object (ends: every step moves mass to a strictly shallower node).
- **Smooth:** Jacobi - every target of a dab comes from the values before it; `N(v)` = edge neighbours on the edit
  mesh (same topology as the cage); opacity does not apply (§3.2's formula).
- **Tests:** `tests/test_weight_paint.py` (25): the footprint (sphere and falloff, two lips, a U bent outside the
  sphere, front only, a moved cage), the formulas, the opacity cap, the parent rule, path-independence over shuffled
  dabs, W1-W4 / Σw <= 1 / <= 4 keys after every dab on random weights, mask, Esc exact, one Undo / Redo step, O(footprint)
  reads and writes after a stroke that touched > 600 vertices, Smooth, Clean. With `test_application_rig.py`,
  `test_weight_view.py`, `test_skin_weights.py` and `test_layer_gate.py`: 131 passed.
- **Early cost [H]** (container, a 296 x 296 grid = 87.6k vertices, footprint 989 vertices, median of 20 dabs; not the
  slice-5 measurement): footprint 3.2 ms, Add dab 5.6 ms, Smooth dab 7.5 ms - about 9 / 11 ms, so slightly above the
  container half-bar of 8.3 ms (§8) before the skin and heatmap patches. The per-vertex `set_bone_weight` +
  `set_layer_value` dominate the dab; §8's first lever (a batch layer write, a Core API addition with its own §7 step)
  stays for slice 5, together with a cluster cull of the candidate query.
- **For slice 2:** the room builds one `VertexCloud` per stroke from `_query_cage()` (or the edit mesh) and calls
  `refresh()` per dab while posed; `footprint(..., hit_face=face_hit's face, toward_viewer=...)`; `dab(fp,
  services.mask_values(fp.vertices))` returns the written vertices for the heatmap patch.

