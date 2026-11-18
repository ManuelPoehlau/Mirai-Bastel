# Texture Paint Room — Architecture Research and Feasibility Audit (2026-11-18)

**Status:** research and recommendation, English with a German summary. **No decision, no production code changed, no
keybinding changed, no dependency added, no existing research document modified.** First-pass record (AGENTS.md §6:
later changes go into dated addenda).
**State audited:** `bb46e73` on `claude/quirky-wozniak-w6lyuh` (clean working tree; it contains the Brush System
research `9f44bc3` and AD-036 slice 2 `af444e4`).
**Question:** can a dedicated 3D Texture Painting workspace ("Paint Room") become a natural part of Mirai without
compromising modelling, topology, symmetry, morph and rigging — and if so, on which storage, with which architecture, in
which order?
**Depends on:** [BRUSH_SYSTEM_FEASIBILITY_AND_ARCHITECTURE_RESEARCH_2026-11-18.md](BRUSH_SYSTEM_FEASIBILITY_AND_ARCHITECTURE_RESEARCH_2026-11-18.md)
(the shared stroke layer, §6 there), [AD-026](../architecture/AD-026-FACE-CORNER-UVS-AND-TEXTURE.md) (face-corner UVs,
one texture per object), [AD-024](../architecture/AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md) (per-object
material), [AD-023](../architecture/AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) (change journal),
[AD-025](../architecture/AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) / [AD-028](../architecture/AD-028-SKELETON-AND-SKINNING.md)
(point layers, morph, skin), [AD-031](../architecture/AD-031-ATTACH-DETACH-WELD-BRIDGE.md), [AD-033](../architecture/AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md)
§16 (Eye Lab window), [REFERENCE_HARDWARE](../architecture/REFERENCE_HARDWARE.md).

**Labels.** **[V]** verified in the code at `bb46e73` (file:line given) · **[C]** measured for this report in a cloud
container (Intel Xeon 2.1 GHz, 4 cores, Python 3.13.18, NumPy 2.5.3 — *not* the pinned 2.2.6; throwaway scripts in the
session scratchpad, not committed; they read the scene file and call only `mirai.iris_import`'s PNG codec) · **[RPC]**
reference PC (Core 2 Quad Q9550, GeForce 9800 GTX, 512 MiB VRAM, GL 3.3), taken from the repository's result files ·
**[H]** assumption or estimate, never a measurement (reference-PC estimates = [C] × 3, the factor REFERENCE_HARDWARE §4
records for NumPy code) · **[O]** an Artist decision for Manu · **[E]** external knowledge from general DCC practice,
not verified in this session.
**Fixture:** the Gollum head of `scenes/Gollum_Head_rigging_test.mirai.json` (the current rigging scene: 2,234 faces,
2,278 vertices, UVs and the ZBrush texture `Gollum_Head_01_Ear_Attached_textures/Gollum_cbf9c7702d.png`, 2048² RGB,
skin weights and four morph targets).

---

## Kurzfassung für Manu (Deutsch)

- **Empfehlung: Malen auf eine UV-Textur (Bild), keine Vertex-Farben, kein Ptex, keine Mischform.** Mirai hat die
  wichtigste Grundlage schon: UVs pro Flächenecke im Mesh, die jede Topologie-Operation mitführt, mit exaktem Undo, und
  eine Textur pro Objekt, die der Viewport zeigt (AD-026). Dein Gollum-Kopf hat UVs und eine 2048²-Textur aus ZBrush.
- **Warum keine Vertex-Farben:** Der Kopf hat 2.278 Punkte. Eine 2048²-Textur hat auf demselben Kopf 2,8 Millionen
  benutzte Pixel – etwa 1.200-mal mehr. Eine mittlere Kante ist 26 Pixel lang. Lippen, Lidränder, feine Übergänge gehen
  mit Punktfarben auf diesem Käfig nicht.
- **Die Bemalung klebt automatisch am Modell**, auch beim Morph, in der Pose und beim Verschieben: Malen ändert nur das
  Bild, Morph und Pose ändern nur Positionen, die UVs bleiben gleich. Malen in der Pose (z. B. Lachfalten im Lächeln)
  wird damit möglich, ohne dass sich am Mesh etwas ändert.
- **Die eigentliche Schwachstelle sind neue Flächen, nicht das Malen:** Auf deinem Kopf haben 44 Flächen keine
  UV-Fläche (Extrude-/Inset-Wände: in UV eine Linie) und 44 Flächen liegen in UV-Überlappungen (3,4 % der benutzten
  Pixel; Malen dort malt an zwei Stellen). Das kam durch Modellieren nach dem UV-Erstellen. Darum: zuerst eine
  **UV-Prüfung**, die solche Flächen zeigt, und später ein „Bemalung auf neue UVs übertragen“ (z. B. nach UV Master in
  ZBrush).
- **Leistung:** Ein Pinseltupfer kostet im Container mit einem vorberechneten „Pixel → Fläche“-Verzeichnis 2,5–7 ms
  (Radius 1–5 %, 2048²), auf deinem PC geschätzt 7–21 ms; bei 1024² etwa ein Drittel. Der naive Weg (jedes Dreieck
  einzeln rastern) ist 3–4× langsamer und auf deinem PC zu langsam. Deine Grafikkarte hat 512 MB: 2048² mit ein paar
  Ebenen passt, 4096² mit Ebenen nicht.
- **Brush-System:** Der Paint Room braucht genau die kleine „Strich-Schicht“ aus der Brush-Recherche (Abtasten des
  Mauswegs, Treffer auf der Fläche, Cursor-Kreis, ein Undo pro Strich, Esc exakt). Das Malen selbst (Farbe, Deckkraft,
  Fluss, Radierer, Pipette) bleibt eigener Code. Malen braucht die Soft-Selection-Gewichte **nicht** – es ist deshalb
  nicht von deren Leistungsproblem abhängig.
- **Was ich von Dir brauche** (Details §11): **P-1** UV-Bild als einzige Malspeicherung? **P-2** Paint Room als
  umschaltbare Ansicht im selben Fenster (wie das Eye Lab)? **P-3** Go für eine kleine Core-Erweiterung
  (`SceneObject.paint`, Szenenformat v14)? **P-4** Deine ZBrush-Textur bleibt unberührt als unterste Ebene, gemalt wird
  darüber? **P-6** Im Paint Room malt die linke Maustaste (statt Box/Malen-Auswahl)?

---

## 1. Executive summary and verdict

| Question | Verdict |
|---|---|
| Is a Paint Room feasible on Mirai's architecture? | **Yes, conditionally.** The storage foundation (corner UVs carried by every primitive, journaled, saved, exported; one textured GL program) exists [V]. Missing: a live paint texture, a texel ↔ surface map, a paint data model, the stroke layer, the room frame. |
| Storage | **A. UV image painting** as the one storage. B (vertex colour) fails on resolution by three orders of magnitude on the actual Gollum cage [C]; C (Ptex) couples texel data to every topology primitive and has no interop path in Manu's pipeline; D (hybrid) doubles every path without simplifying anything. Triplanar: later, only as a *fill source* baked into a layer, never as storage. |
| Biggest risk | **Not topology on painted areas** (UVs carry them exactly [V]) but **UV quality of geometry created after the UVs**: measured on the Gollum head, 44 zero-area faces and 3.4 % overlapping texels [C]. Phase 1 needs a read-only UV health check; Phase 3 a UV-transfer (re-bake on new UVs). |
| Deformation | **Attached by construction:** morph, pose and transforms change positions only and never UVs [V: AD-026 §1.2, `set_vertex_position`]. Painting on the posed / mixed surface writes no mesh data — it is allowed where position edits are refused (AD-028 §7.1). |
| Brush engine | Paint is the **first unconditional consumer** of the Brush research's stroke layer A (sampling, hit, cursor, lifecycle). Dab semantics are paint-specific. Paint does not use the Soft field, so the field-performance blocker of the Brush research does not block paint. |
| Performance | Feasible at 2048² with a cached **texel → (triangle, barycentric) map** and CPU-authoritative pixels with tile uploads: dab 2.5–7.0 ms [C] at 1–5 % radius ≈ 7–21 ms [H, RPC]. Unmeasured and decisive: tile upload + mip regeneration and the textured draw on the 9800 GTX (§8.4). |
| Modeller safety | The room allocates nothing until entered; outside it the draw is the AD-026 draw. A Core change is needed only for persistence (`SceneObject.paint`, format v14) and needs Manu's Go (CORE_V1_FREEZE §7). |

**Alternative that exists today (baseline).** Manu can already paint in ZBrush (Polypaint → *Texture from Polypaint*)
and bring the texture back through GoZ (P3b, `src/interop/goz/texture.py`; WP_GOZ_P3_PLAN). The Paint Room is justified
only by what that round trip cannot do: painting the **posed / morphed** character, refining without leaving Mirai,
layers that survive the next modelling change. That is the question behind **P-1**.

---

## 2. Current-state findings

### 2.1 Subsystem inventory

| Area | State at `bb46e73` | Evidence |
|---|---|---|
| Rooms / workspaces | **No room concept in code.** Selection modes `1/2/3/4`, Pose mode, binding contexts (`global`, `window`, `knife`, lab contexts). Closest precedent: the **Eye Lab window**, a view-state configuration that saves camera, isolation and quality tier on open and restores them on close; Manu I-1: "a window in the app (a room later)" | `grep -rniE "\broom\|workspace" src` (only prose hits); `mirai/viewport/display.py:87` `DisplayState.eye_lab`; AD-033 §16; Audit 2026-10-20 §6 ("a workspace is a configuration over a shared core, not its own renderer"), open question A6 |
| Mesh attributes | Positions; topology with never-reused IDs; symmetry definition; face regions (polygroups); **point layers** `LayerKind.VECTOR` (morph offsets) and `WEIGHTS` (skin); **face-corner UVs** (one map) | `core/mesh.py:99` `LayerKind`, `:879` `face_uvs`, `:891` `set_face_uvs`; `core/layer_storage.py`; AD-025, AD-026, AD-028 |
| Colour storage | **None.** No vertex colours, no polypaint storage; a colour as a VECTOR layer would be read as a morph target | `mirai/morph_targets.py:99` (`morph_target_ids` = every VECTOR layer); `future_ideas/ZBRUSH_BRIDGE_AUDIT.md` §2.7 ("Polypaint: no storage") |
| UVs through topology | Every primitive has a UV rule (split = lerp per face, Knife interior = mean value coordinates, collapse = mean where no seam, dissolve exact, extrude/inset walls = a line in UV, bridge = **no UVs**, attach/detach copy per face, weld keeps per face); journaled; invariant U1 | AD-026 §3; `core/corner_uvs.py`; `mirai/topology/extrude.py:243–272`, `inset.py:96–118`, `bevel.py:32`, `bridge.py:16,122`, `mesh_assembly.py:375`; `tests/test_core_face_uvs.py` |
| Material / texture | `SceneObject.material: ObjectMaterial` (base colour, specular, glossiness; Undo via `ObjectMaterialCommand`); `SceneObject.texture: str` = **a path**, not journaled; for an eye object the same field is the iris image | `core/scene.py:444–485`; AD-024 §2, §7; WP_GOZ_P3_PLAN §1 ("a path, not journaled today"); AD-033 |
| Texture display | A second, textured GL program; per triangle slot a `triangle_uvs` buffer texture; the image **replaces** the base colour (`albedo = texture(...)`); images loaded once per `(path, mtime, size)`, mipmapped, linear, repeat; no sRGB decode | `viewport/gl_render_store.py:309–318`, `:480` `load_texture`, `:564` cache, `:601` `set_texture`; `viewport/material.py` `Material(texture=)`; AD-026 §6, §7 |
| Texture shown per object | `ObjectController._shown_texture`: the object's texture while `show_texture`, not while highlighted in mode `4` | `mirai/controllers/objects.py:1539`; `mirai/viewport/display.py` (`show_texture`) |
| Surface hit | CPU `face_hit` returns position **and barycentric weights** of the hit triangle; the **same triangulation** as the draw (`triangulate_mesh_face`), so hit-triangle barycentrics interpolate UVs exactly as the rasterizer does | `mirai/viewport/picking.py:300`; `viewport/derived.py:182` (one function for picking, overlays and draw) |
| GPU picking | ID buffers with depth; `face_at`, a depth window `visibility(x0, y0, x1, y1)`; under SubD it picks a never-drawn cage `RenderMesh` | `viewport/gpu_picker.py:280`, `:366`; AD-022; MODELING_ON_DEFORMED_SURFACES §16 (d) |
| Deformed surfaces | Hover / picks read the drawn cage: the posed surface, else the morph mix — a `SurfacePositions` with the edit mesh's IDs and topology; writes always go to the rest mesh, and position/topology edits are refused while posed | `mirai/application.py:4986` `_query_cage`; AD-028 §7.1; MODELING_ON_DEFORMED_SURFACES §15–§16 |
| SubD | The derived surface gets face-varying **linear** UVs and shows the texture; picking stays on the cage | `mirai/subdivision/catmull_clark.py:479` `refine_face_uvs`; `subdivision/preview.py:376`; AD-026 §6 |
| Symmetry | `SymmetryDefinition` (plane point + normal + seam edges) owned by the Mesh; correspondence and driver rule for positions | `core/mesh.py` `SymmetryDefinition`; AD-SYM-01..05 |
| History | Linear `HistoryStack` of a minimal `Command` protocol (`undo` / `redo`), deliberately subsystem-free; **no size limit, no merge** | `core/history.py`; AD-003 |
| Gestures | `GestureSession` kinds in one slot (arm → drag → release = one entry, Esc = rollback); no positional stroke that edits anything but the selection | `mirai/controllers/gestures.py:293`; Brush research §2.2 |
| Stroke sampling | `stroke_samples(start, end, spacing)` (Paint Select) | `mirai/viewport/box_select.py:176` |
| Layer gate | Fail-closed classes; a command that writes no mesh is `NON_MESH` | `mirai/layer_declarations.py:129` |
| Input | `BindingSet` is the only input truth; contexts exist (`knife` resolves only in a session); plain LMB drag = `SelectDrag` (Manu 2026-10-15) | `mirai/interaction/bindings.py:359–414`; `config/keymap.json` |
| GUI | Dear ImGui panels that read state and call `Application`; a colour editor is already used (`imgui.color_edit3`) | `gui/imgui_layer.py`; `gui/eye_panel.py:41`; AD-030 |
| Image I/O | Stdlib + NumPy PNG encoder / decoder (no Pillow); content-hashed, never-overwriting copies beside the scene; scene-relative paths | `mirai/iris_import.py:95` `encode_png`, `:148` `decode_png`; `mirai/texture_files.py` (`store`, `copy_into`, `scene_texture_dir`) |
| Persistence | Scene format versions 4–13; each feature bumps a version only when used; older builds refuse newer files | `core/serialization.py:109–156` |
| Export | OBJ export writes UVs (`vt`), no MTL and no image; GoZ sends UVs, returns UVs and a texture copy; **sending a texture to ZBrush has no known safe path** | AD-026 §5; WP_GOZ_P3_PLAN §1 ("`-tmap` … never on a mesh send") |
| Hardware | GL 3.3 at the ceiling, 512 MiB VRAM, no tablet, NumPy pinned to 2.2.6 (Penryn, no x86-64-v2); a 2048² RGBA8 texture with mips = 21.3 MiB | REFERENCE_HARDWARE §1–§4; `mirai/sclera_map.py` (`MAX_SIZE` comment); `requirements.txt` |
| Design hypotheses | GUI Bestandsaufnahme (non-normative [H]): "keine Werkzeugleiste mit Icons, keine Eigenschaftsfenster, kein eigener Weight-Paint-Modus" | `docs/design/GUI_Bestandsaufnahme.md` §4 |

### 2.2 The Gollum head's UV layout [C]

Measured from the scene file (script outside the repository, NumPy rasterisation of the stored corner UVs at 512² for
coverage):

| Measure | Value |
|---|---|
| Faces / vertices / mapped faces | 2,234 / 2,278 / 2,234 (all mapped) |
| UV islands (connected by shared corner values) | 2 — one of 2,231 faces, one of 3 |
| Seam edges / border edges | 64 / 20 |
| Share of the unit square used | 66.5 % |
| **Overlapping texels** (covered more than once) | **3.4 % of used texels**; 44 faces have their UV centre in an overlap (ids 1642 … 1694, 2829 … 3078, 4533 …) |
| **Faces with zero UV area** | **44** (ids from 5419 up — the newest ids, consistent with Extrude / Inset walls, AD-026 §3) |
| Texel density at 2048² (px per scene unit, p5 / p50 / p95) | 515 / 973 / 1,745 — a 3.4× spread |
| Median edge | 3.57 % of the bounding radius (0.743) = **26 texels** at 2048² |
| A 1 % / 5 % brush (radius in % of the bounding radius, the Soft unit) | 7 / 36 texels at p50 density |

Reading: the texture survived months of modelling as far as AD-026 promises (it "sticks"); the layout did not stay
clean. The overlap cause is **not determined** here (candidates: the attached ear's own UVs, AD-031 "destination look";
corner rules of Collapse / Dissolve; ZBrush's layout). For painting, an overlap is a correctness bug (one stroke writes
two places), a zero-area face is unpaintable.

---

## 3. Texture storage approaches

### 3.1 Comparison

| Criterion | A. UV image | B. Vertex / corner colour | C. Ptex (per-face textures) | D. Hybrid (B broad + A detail) |
|---|---|---|---|---|
| Implementation complexity [H] | Medium: texel map, live texture, layers, persistence — no Core topology work (UVs exist) | Low for storage (a new `LayerKind.COLOR`, Core change), medium for display (per-vertex colour buffer) | **High**: per-face texel blocks resampled in every primitive (split, collapse, dissolve, knife, extrude), journaled, plus adjacency filtering | High: both A and B, two brushes, two undo kinds, a composite of both |
| Detail on the Gollum cage | 2.79 M used texels at 2048² [C] | 2,278 values (≈ 1:1,200) [C]; one colour per 26-texel edge — lips, lid rims impossible | per-face resolution free; same detail as A at equal memory [E] | A's detail; B adds nothing A cannot do with a large soft brush |
| Memory | 16 MiB per RGBA8 layer at 2048² (+33 % mips on GPU) | negligible | comparable to A at equal texel count, plus borders [E] | A + B |
| Viewport cost | the existing textured program (one sampler) | one vertex attribute (needs a new buffer / shader path) | needs an atlas or texture array plus per-face addressing, filtering across faces — a new draw program [E] | A's program plus B's attribute |
| Topology compatibility | painted pixels exact through every primitive that carries UVs [V]; weak on **new** faces (walls, bridge) | interpolation rules exist for point layers (AD-025 combine rules); corner seams would need a corner domain | every primitive must resample texels; a merge (collapse, dissolve) loses or averages texels | worst of both |
| Deformation (morph, pose) | attached by construction [V] | attached by construction | attached | attached |
| Persistence | PNG files beside the scene (code exists) [V] | inside the mesh state (JSON) — large for dense meshes | own container format | both |
| Export | OBJ + image is universal; ZBrush imports it [E] | no OBJ standard; GoZ polypaint block exists (`B9 88`) [V doc] | not supported by Manu's tools (ZBrush, Blender) [E] | partial |
| Long-term maintainability | one data path, standard everywhere | simple but a dead end for detail | a second geometry-coupled data system inside the Core | two systems |
| UV prerequisite | **yes** — no UVs, no paint | none | none | partial |

### 3.2 Triplanar projection

Triplanar sampling needs no UVs and no storage, but it is a *projection*, not paint: it swims on deformation unless it is
evaluated on rest positions (an extra vertex attribute the draw does not have today [V: the textured program reads only
`triangle_uvs`]), it blends visibly on diagonal surfaces, and it cannot hold hand-painted strokes. **Use later only as a
fill source**: project a tileable skin image triplanar in rest space and *bake* it into a paint layer once (Phase 4).

### 3.3 Recommendation

**A. UV image painting, one storage.** It is the only option that (1) reaches lip-and-eyelid detail on the cage Manu
actually models, (2) needs no new topology rule in the Core, (3) is already persisted, displayed and exported, and (4) is
what ZBrush hands back today. Its one real cost — dependence on a clean UV layout — is addressed explicitly (§5.3, Phase
1a and Phase 3). Vertex colour stays a possible *interop* feature (GoZ polypaint import, ZBRUSH_BRIDGE_AUDIT D7), not a
paint storage. **[O] P-1.**

---

## 4. Recommended architecture

### 4.1 Layers

```
 Paint Room frame (view + input configuration)      Paint data (document)
 ─────────────────────────────────────────────      ─────────────────────────────────────────
 DisplayState.paint_room (like eye_lab):            SceneObject.paint: PaintStack | None  [Core field, P-3]
   camera / display / overlays saved and restored     · layers: (name, image ref, opacity, visible, blend)
   binding context "paint" active                     · resolution, base = SceneObject.texture (P-4)
   panels: brush · colour · layers                    PaintStore (src/mirai): pixels per object instance
                                                        · NumPy RGBA8 per layer, dirty tiles, composite
 Stroke layer (Brush research layer A)              Texel–surface map (src/mirai, derived)
 ─────────────────────────────────────              ─────────────────────────────────────────
 StrokeSession (a GestureSession kind)               per texel: triangle slot + 2 barycentrics
   · stroke_samples, surface hit, cursor               built from topology + UVs (journal-patched)
   · one History entry, Esc exact                      positions from ANY table: rest / mix / pose
        │ per dab                                            ▲
        ▼                                                    │
 Paint dab (paint-specific)                          GPU display (src/viewport)
 ─────────────────────────────                       ─────────────────────────────────────────
 footprint: texels within radius of the hit          one live GL texture = the composite
   (+ facing, + depth occlusion window)                glTexSubImage2D of dirty tiles
 stroke buffer (max-accumulated alpha)               the AD-026 textured program, unchanged
 brush op: paint / erase / (later smudge, blur)      mips: policy measured in Phase 1
 symmetry: mirrored dab across the plane
```

### 4.2 Principles

1. **CPU-authoritative pixels, GPU as a display cache.** Pixels live in NumPy arrays; the GPU gets tile uploads. This
   keeps Mirai's direction "data flows Core → Viewport, never back" (CLAUDE.md), makes every paint result testable
   headless (as `light_rig.shade` mirrors the GLSL term), needs no readback for undo or save, and keeps the existing
   textured program. A GPU paint pass (render into the layer texture in UV space) is the documented fallback only if the
   CPU dab misses its budget on the RPC [H].
2. **The texel–surface map is derived data**, like the pick cache: built once per (topology, UVs) on entering the room
   [C: 513 ms at 2048², 229 ms at 1024², unoptimised], patched per changed face from the journal (`Mesh.watch`, AD-023),
   **never rebuilt for a position change**. A texel's 3D point = Σ wᵢ · pᵢ over its triangle's corners from whichever
   position table the window draws — rest, morph mix or posed surface share IDs and topology [V: `_query_cage`]; measured:
   the same map serves a deformed copy [C].
3. **The dab is texel-space, the footprint is surface-space.** A dab selects the texels whose surface point lies within
   the brush radius of the hit (plus a facing test against the view and, for thin gaps like lids and lips, a depth test
   against the GPU picker's depth window [V: `gpu_picker.visibility`]). Because the footprint is evaluated on the
   surface, **a stroke crosses UV seams without a visible break**: texels on both islands are selected by their 3D
   position [C: texel counts include both sides].
4. **Stroke buffer.** Within one stroke, coverage is max-accumulated in a per-stroke alpha buffer and composited live
   with the stroke's opacity; at release it is baked into the layer. Consequences: opacity does not build up within one
   stroke (artist expectation: "opacity vs flow"), **Esc is exact by dropping the buffer**, and the History entry is the
   before/after of the touched tiles.
5. **Seam padding.** After each bake, texels within a few pixels outside an island take their nearest island texel
   (indices precomputed with the map), so bilinear filtering and mip levels do not show the background at seams [E:
   standard "dilation"]. Mirai's own tests decide the width [H: 4–8 px at 2048²].
6. **Composite.** CPU composite of the dirty tiles over the base image [C: 3.9 ms for a 256² region with 4 layers;
   358 ms for a whole 2048² — so never whole-image per dab], then a tile upload into the one live texture. A GPU
   multi-layer shader is not needed for 1–8 layers [H].

### 4.3 Data ownership — the one Core question (P-3)

| Option | Verdict |
|---|---|
| **D1. `SceneObject.paint: PaintStack | None`** (frozen dataclass: layer metadata + image file references, no pixels), scene format **v14** written only when used; pixels as PNG in `<scene>_textures/` through `texture_files.store` (content-hashed, never overwritten) | **Recommended.** Same reasoning and shape as `ObjectMaterial` (AD-024 §1.2) and `EyeSpec.sclera_texture` (AD-035): data of the object, travels with Attach / Detach / mirror copy / delete-undo because the command holds the instance. Additive; CORE_V1_FREEZE §7 checklist applies. |
| D2. A side table in `src/mirai` keyed by `ObjectId`, own file | Rejected — the AD-024 §1.2 argument: ID remap on every load, the object's data in two places. |
| D3. Pixels in the Mesh / journal | Rejected — images are not mesh data (AD-026 §1.3), and the journal would carry megabytes per stroke. |

- **Base layer (P-4):** the existing `SceneObject.texture` (e.g. the ZBrush texture) stays untouched as the bottom
  layer; paint layers lie above it. Painting is then non-destructive towards everything Manu brought from ZBrush.
- **Pixel undo** is a `src/mirai` command implementing the Core `Command` protocol (`PaintStrokeCommand(obj, layer,
  tiles)`), no Core History change [V: `core/history.py` contract]. Layer property edits (opacity, visibility, order,
  rename) are commands shaped like `ObjectMaterialCommand`.
- **Flattened output:** OBJ export, GoZ and any external use read one flattened PNG written on save (or on export).
  Whether `SceneObject.texture` is then repointed to it or stays the base is part of P-4.

---

## 5. Topology compatibility assessment

### 5.1 Per operation (painted pixels are in UV space; the question is what the UVs do) [V for the UV rule, H for the visual effect]

| Operation | UV rule (AD-026 §3, code) | Effect on painted pixels |
|---|---|---|
| Move / Rotate / Scale / Tweak / Soft / Smooth / Relax / Slide / Surface Slide / Inflate / Morph / Apply transform | unchanged | **exact**; the paint stretches with the surface |
| Split, Edge Connect, Loop Insert, Knife (edge points) | lerp per adjacent face; seams kept | exact (same UVs on the same surface); a changed triangulation of a non-planar quad can shift the image by a fraction of a texel line |
| Knife interior points, Vertex Connect, chords | mean value coordinates / parent corners | as above |
| Collapse | survivor = mean of the two corners where no seam | small local remap in the collapsed fan; painted detail around the vertex is pulled |
| Dissolve | merged face takes the outline corners exactly | outline exact; inside, the n-gon's triangulation now spans the old faces' UV area — mild distortion on curved regions |
| Delete V/E/F | UVs go with the faces | pixels stay in the image (orphaned, harmless); Undo brings the faces and their mapping back |
| **Extrude / Inset walls** | the source face's two corners, top and bottom → **a line in UV** | **unpaintable**; the wall shows a streak of the boundary colour (observed: 44 faces on the Gollum head, §2.2) |
| Extrude cap, Inset inner faces, Bevel rebuilt faces | source UVs / replaced corner's UV | the cap / inner face takes over its source face's UV area (the source face is replaced), so the paint moves with it; around it the walls / strips carry the problem above. Where an operation keeps the source face *and* adds a face with the same UVs, the result is an overlap [H: not traced per tool here] |
| Cap (fill hole) | inferred from neighbours | usually fine; across a seam it reads one side (documented limit) |
| **Bridge** | **no UVs** (`infer_uvs=False`, D8) | **unmapped** — draws the base colour, cannot be painted |
| Weld | corners kept per face | a seam along the weld stays; paint continuous |
| Attach | sources take the **destination's look**; their UVs stay | a painted source's paint stack would no longer show → needs a rule (§5.4) |
| Detach / Separate / mirror copy | look and UVs copied | the paint stack is copied (shared immutable files) |
| GoZ return with new UVs (UV Master) | corner UVs replaced in one step | **every painted pixel is now mis-mapped** → needs UV transfer (§5.3) or a refusal |
| SubD | derived face-varying linear UVs | the texture shows on the smooth surface; painting there needs its own map (§5.2) |

### 5.2 Undo, morph, pose, SubD, symmetry

- **Undo / Redo.** Geometry and UVs are restored by the journal (`test_journal_undo_redo_rollback_exact`, 25 random
  sequences) [V]; pixels by tile commands [H until built]. The two are independent: no topology operation touches pixels,
  no paint touches the mesh, so any interleaving undoes exactly. Re-patching the texel map on Undo comes from the same
  journal notification the viewport already uses.
- **Morph targets.** Paint is position-free, so it is the same under every mix weight and in the target's editing view
  (`Tab`) — UVs are not layer data [V: AD-026 §2 "positions-only edits never touch them"]. The layer gate classifies paint
  commands `NON_MESH` [V class exists].
- **Pose.** Painting writes no mesh data, so it is allowed while posed (the refusal of AD-028 §7.1 is about position and
  topology edits). Hits and footprints use the posed surface positions through the same map.
- **SubD on.** The drawn surface is the derived mesh, the pick surface is the cage [V]. Painting with a cage hit while
  SubD is shown would place paint off the cursor by the cage-to-limit distance [H]. Phase 2: painting refuses or uses
  the cage with SubD shown off (P-10); Phase 3: a texel map of the derived surface (its faces + refined UVs; rebuilt only
  when the derived topology changes).
- **Symmetry.** A mirrored dab across the mesh's `SymmetryDefinition` plane, evaluated on rest positions (where the plane
  is defined): no vertex correspondence is needed because paint footprints are positional. On an asymmetric mesh
  (`Gollum_Head_01_Asym`) the mirrored footprint lands on the nearest surface [H]; in a pose the mirror is taken in rest
  space and mapped through the map (P-9). Painting stays asymmetric by default when symmetry is off — the head's halves
  have separate UV space [C: 3.4 % overlap only].

### 5.3 The UV problem and its solution path

1. **Phase 1a — UV health check** (read-only): unmapped faces, zero-area faces, overlapping faces, texel-density spread;
   a viewport overlay and a status line on entering the room. §2.2 is its prototype.
2. **Paint rule:** texels shared by an overlap are painted once per dab at the first footprint hit [H]; zero-area and
   unmapped faces are skipped and named in the status line.
3. **Phase 3 — UV transfer.** When an object's UVs change (GoZ UV Master, a later UV tool), re-sample every layer from
   the old UVs to the new ones **per triangle** — the topology is the same, so each new UV triangle maps affinely onto its
   old UV triangle; no ray casting [H]. With it a ZBrush re-unwrap is non-destructive to Mirai's paint.
4. **No UV editor before that.** Minimal later needs: a 2D UV layout view (read-only), per-face "needs UVs" marking, and
   possibly a planar re-projection for small new regions (walls). A full unwrapper is a separate decision (it would
   likely need a dependency or a large own implementation).

### 5.4 Multiple objects and materials

One texture per object (AD-026) → **one paint stack per object**. Eyes are excluded (their `texture` is the iris, they
draw in the eye pass, AD-033/035; P-14). Teeth without UVs cannot be painted until they have UVs. Attach of a painted
source into another object cannot merge two images into one without repacking UVs → recommended: refuse Attach when a
source carries a paint stack and the looks differ, with a status line (P-13).

---

## 6. Brush engine integration

### 6.1 Shared with the Brush research (layer A and around it)

| Property | Shared? | How |
|---|---|---|
| Stroke sampling / spacing | **shared** | `stroke_samples`, spacing as a fraction of the screen radius (Brush §7.3) |
| Surface hit | **shared** | `face_hit` on the drawn cage (CPU) / GPU `face_at`; barycentrics already returned |
| Cursor display | **shared** | the screen circle that the Brush research proposes (§4.2 there), drawn once for both |
| Stroke lifecycle, one History entry, Esc exact, focus loss | **shared** | a `GestureSession` kind in the AD-027 slot |
| Radius | **shared semantics** | world radius in % of the bounding radius with the Soft steps and Shift+wheel (Brush O-3) — proposal P-7 |
| Falloff curve | **shared functions, not the field** | the Soft curve functions (`soft_selection/influence.py:81`, `CURVES`) applied to texel distances; the geodesic Soft field itself is not used |
| Symmetry | **shared definition, not the algorithm** | the plane of `SymmetryDefinition`; positions use the driver rule, paint uses a mirrored footprint |
| Presets | **later, shared format** | if presets come, one small file format for both (no preset system in Phase 2) |
| Stroke interpolation / smoothing (lazy mouse) | later, shared | layer A |

### 6.2 Paint-specific (not in the shared layer)

Colour, opacity (per stroke, via the stroke buffer), flow (per dab), hardness (the falloff's inner plateau), erase
(reduces layer alpha), eyedropper (samples the **composite albedo** at the hit through the map — not the lit framebuffer
colour), later smudge / blur (neighbourhood ops in texel space; seam-aware only through the map), clone / stamp,
stencil / image projection.

### 6.3 What this changes in the Brush research's plan

The Brush research made layer A conditional on O-1 (a positional deformation stroke). **Paint needs layer A
unconditionally.** Recommended: build layer A for Paint first, keep its interface operation-agnostic (it never computes
pixels or positions), so a later Smooth / Inflate stroke plugs into it. Paint does **not** depend on the Brush
research's phase 1 (the Soft-field adjacency fix): paint uses no Soft weights. No universal brush abstraction beyond
layer A.

---

## 7. Layers and material channels

- **Layer model (Phase 3; Phase 2 has exactly one paint layer):** an ordered list per object; each layer = RGBA8 image at
  the stack's resolution, name, visibility, opacity, blend mode (Normal first; Multiply is the most useful second mode for
  skin variation [H] — P-12), plus the base (P-4). Basic management: add, delete, rename, reorder, merge down, clear.
  Every change is one Undo step; pixel strokes one per stroke.
- **Non-destructive:** the base image is never written; layers are only written by strokes; Undo restores tiles.
- **Bit depth:** 8 bit per channel per layer, one quantisation per stroke bake (the stroke buffer is float) [H: enough for
  skin; banding check in the practical test]. 16-bit layers are an upgrade path (double memory).
- **Channels:** Phase 2–3 = **Base Colour only**. Later, in this order: a roughness / specular map (Mirai's finish is per
  object today — `specular`, `glossiness` uniforms — so a map is a shader change and a Lookdev decision); masks (a layer
  mask, or face regions / Mask Geometry as a paint mask — both exist [V]); normal / bump (needs tangents, which Mirai does
  not have — large). No PBR authoring system.
- **Colour management:** today image values are used as the base colour directly (no sRGB decode, AD-026 §7). The Paint
  Room keeps that until the Lookdev work decides colour management (P-16), so painted colours look the same everywhere
  Mirai shows them.

---

## 8. Performance and hardware

### 8.1 Measured [C] on the Gollum head (×3 for an RPC estimate [H])

| Step | 1 % | 3 % | 5 % | 10 % | Note |
|---|---:|---:|---:|---:|---|
| Texels per dab at 2048² | 502 | 3,197 | 9,817 | 52,914 | both sides of a seam counted |
| Naive dab (rasterise each near triangle per dab), 2048², p50 | 8.4 ms | 10.0 ms | 25.2 ms | 56.9 ms | per-triangle Python loop — **not viable on the RPC** |
| **Texel-map dab, 2048²**, p50 / p95 | **2.5 / 4.0 ms** | **4.0 / 6.3 ms** | **7.0 / 8.7 ms** | 15.5 / 18.8 ms | gather + blend in NumPy, unoptimised |
| Texel-map dab, 1024², p50 | 0.75 ms | 1.1 ms | 1.85 ms | 3.5 ms | |
| 64² tiles touched by a 40-dab stroke | 11 | 16 | 24 | 44 | = 176–704 KiB RGBA8 "before" per stroke |

| One-off / per save | Value |
|---|---|
| Texel map build, 2048² / 1024² | 513 ms / 229 ms; 69 MiB / 17 MiB (int32 + float32 full-size arrays, unoptimised) |
| Composite of 4 layers, whole 2048² / one 256² region | 358 ms / 3.9 ms |
| `encode_png` 2048² with texture content / a mostly empty layer | 173 ms, 0.49 MB / 62 ms, 21 kB |
| `decode_png` of Mirai's own file / of the ZBrush-made PNG | 45 ms / 38 ms |

RPC reading [H]: a 1–5 % dab ≈ 7–21 ms at 2048², ≈ 2–6 ms at 1024²; a 10 % dab at 2048² ≈ 45 ms (too slow → cap the
dab rate, never drop the last sample). Entering the room on 2048² ≈ 1.5 s once.

### 8.2 GPU memory (512 MiB card)

| Item | 1024² | 2048² | 4096² |
|---|---:|---:|---:|
| One RGBA8 texture with mips (the live composite) | 5.3 MiB | 21.3 MiB | 85 MiB |
| Layers if they were also on the GPU (4 × RGBA8, no mips) | 16 MiB | 64 MiB | 256 MiB |

With CPU-authoritative layers only the composite is on the GPU → 2048² costs what one ZBrush texture costs today.
**4096² is not recommended on the RPC** (CPU memory per layer 64 MiB, texel map ≈ 280 MiB unoptimised, dabs ×4). P-5.

### 8.3 CPU / GPU split

CPU: map, dab, stroke buffer, composite of dirty tiles, undo tiles, PNG. GPU: one `glTexSubImage2D` per dirty tile per
frame, the existing textured draw. The Modeller is unaffected: nothing is allocated until the room opens, and a draw
without a paint stack is the AD-026 draw (to be pinned by a test like `test_without_texture_the_draw_is_the_untextured_one`).

### 8.4 Likely bottlenecks (unmeasured, measure first)

1. **Tile upload + mipmap regeneration on the 9800 GTX.** `glGenerateMipmap` on 2048² per frame during a stroke may cost
   more than the dab [H]. Options to measure: regenerate at stroke end only (minified view slightly stale mid-stroke),
   or no mips while the room is open.
2. **The driver's buffer-texture slowdown.** The RPC driver makes texel fetches slow in frames where a buffer texture was
   updated (O2 results, hypothesis (a), `RESULTS_O2_REFERENCE_PC_2026-11-11.md`). Paint updates a 2D texture, not a
   buffer texture — whether the same penalty appears is unknown [H].
3. **The textured program's geometry shader** has never been measured on the RPC (AD-026 §8.1).
4. **Hit cost after nothing changed geometrically.** Paint does not move vertices, so the GPU pick cache stays valid
   between dabs (cheaper than the Brush research's case, where every dab invalidates it) [H].
5. **Undo memory.** `HistoryStack` has no limit [V]. 700 KiB raw per stroke → ≈ 0.7 GB after 1,000 large strokes [H].
   Mitigation without a Core change: store only "before" tiles (capture "after" at undo time), zlib-compress tiles;
   then decide a budget (P-11).

### 8.5 Proposed measurable tests (reference PC)

| Probe | Acceptance (proposal) |
|---|---|
| P-A dab + composite + upload per frame, Gollum head, 2048², radius 3 % / 5 % | p95 ≤ 16.7 ms at 3 %, ≤ 33 ms at 5 % (the D3 bars) |
| P-B mip policy: per frame vs stroke end vs none | pick the cheapest that shows no seam or shimmer in the practical test |
| P-C orbit frame with a live 2048² texture vs the file texture | no regression > 1 ms p50 |
| P-D room enter (map build) on the head at 2048² | ≤ 2 s, once per object and topology |
| P-E Modeller frame with the Paint Room never opened | bit-identical draw, same frame time |
| P-F save of a 4-layer stack | ≤ 2 s; unchanged layers not re-encoded (content names) |

---

## 9. UX recommendations

### 9.1 Room frame (P-2)

A room is a **named configuration of the same window** (Audit 2026-10-20 §6; the Eye Lab pattern): entering saves the
camera, display mode, overlays, Soft / wire state and activates the `paint` binding context and the paint panels;
leaving restores them. The document (mesh, morphs, rig, paint stack) is never copied — "return to Model Room without
exporting" is automatic. Proposed entry: a SPACE-menu row and a key after Manu's "Taste passt" (no keymap entry before
that, CLAUDE.md). Entering refuses with a status line on an object without UVs or an eye, and shows the UV health
(§5.3).

### 9.2 Layout (all `PROVISIONAL`)

- **Viewport** large and central; Textured + smooth shading forced on, wireframe and selection overlays off by default,
  the Worklight unchanged (paint under the same light Manu models in).
- **Compact brush shelf** (Paint, Erase, Pick; later Smudge, Blur): a short row of text buttons or an ImGui strip — this
  touches the GUI Bestandsaufnahme hypothesis "keine Werkzeugleiste mit Icons" → **P-17**.
- **Brush settings** in context: radius, opacity, flow, hardness, falloff curve — only for the active brush.
- **Colour:** one swatch + `imgui.color_edit3` (exists, `gui/eye_panel.py:41`), primary / secondary colour, a short
  recent-colour row; eyedropper on a held key.
- **Layer panel** (Phase 3): list with visibility, opacity, blend mode, add / delete / reorder; in Phase 2 a single row.
- **Texture settings:** resolution at creation, the base image's name, UV health summary.

### 9.3 Keyboard-first (proposals for P-6 only)

| Action | Proposal | Reason |
|---|---|---|
| Paint stroke | plain LMB drag **in the `paint` context only** | the most direct; overrides `SelectDrag` only inside the room (selection has no role there) |
| Radius | Shift+wheel | the same chord that steps the Soft radius today |
| Opacity / flow | Alt+wheel is free in code and keymap (Brush §2.3) | one more chord, no new key |
| Eyedropper | hold a key + click | the hold-key grammar of Mirai |
| Erase | hold a modifier while stroking, or a brush switch | decide in the practical test |
| Symmetry | the existing `Shift+S` cycle | no second symmetry toggle |
| Undo / Redo | unchanged | one per stroke |

No pressure sensitivity: the RPC has no tablet (REFERENCE_HARDWARE §1) — P-15.

### 9.4 Minimum UV capabilities Mirai eventually needs

Read-only first: UV health overlay (Phase 1), a 2D UV layout view with the painted image (Phase 3). Editing later and
only on demand: mark faces that need UVs, planar re-projection of a small selection, UV transfer after a re-unwrap
(Phase 3). Unwrapping itself stays in ZBrush (UV Master) until Manu asks otherwise.

---

## 10. Phased roadmap

| Phase | Content | Prerequisites | Decision | Size |
|---|---|---|---|---|
| **0** — decisions (no code) | Manu answers P-1 … P-6; optional 10-min reflection: which Gollum painting tasks are blocked by the ZBrush round trip today? | — | Manu | — |
| **1** — foundations | **1a** UV health check (read-only diagnostic + overlay). **1b** texel–surface map module with journal patching; tests: barycentric parity with `face_hit`, deformation invariance, patch == rebuild after random topology sequences. **1c** live texture source in `GLRenderStore` (tile uploads; a draw without it bit-identical). **1d** paint data model: `SceneObject.paint` + format v14 + PNG persistence + `PaintStrokeCommand` (after P-3 Go). **1e** RPC probes P-A … P-F | P-3 for 1d; nothing for 1a–1c | agent (technical) + Manu (P-3) | M–L |
| **2** — first usable Paint Room | Room frame (enter / leave, restore); layer A stroke session; one paint layer above the base; Paint / Erase / Pick; radius, opacity, flow, hardness, curve; stroke buffer; seam padding; mirrored dab; cursor circle; one Undo per stroke, Esc exact; save / load; flattened PNG for export; status-line refusals (no UVs, eye, SubD per P-10). Practical test on the Gollum head (lips, lids, nose, cheeks) | Phase 1; P-2, P-4, P-6, P-7 | Manu: keys, room entry | L |
| **3** — workflow expansion | Several layers (visibility, opacity, order, merge down, Multiply); Blur / Smudge; face regions and Mask Geometry as paint masks; painting on the SubD surface (derived map); **UV transfer** on UV change (GoZ UV Master); 2D UV view; paint while posed with symmetry in rest space | Phase 2 practical test | Manu per feature | M each |
| **4** — advanced | Roughness / specular map (Lookdev + shader decision); layer masks; clone / stamp; image / photo projection (stencil); triplanar fill sources; 16-bit layers; vertex-colour / polypaint interop with GoZ | Phase 3; Lookdev colour management | Manu | — |

**Dependencies.** 1b is the core of everything; 1c is needed before anything is visible; 1d needs the Core Go; Phase 2
needs layer A (built here first, shared with the Brush research later); Phase 3's SubD painting needs 1b on the derived
mesh; UV transfer needs only the old and new UVs of the same topology. **Never in the first version:** several material
channels, a UV editor, brush presets, a GPU paint engine, Ptex, vertex colours.

---

## 11. Open questions and decisions for Manu

| # | Question | Proposal |
|---|---|---|
| **P-1** | Paint storage: UV image only? (Vertex colour and Ptex not as storage.) Is the ZBrush Polypaint round trip enough instead? | UV image; build the Paint Room only if painting the posed / morphed character inside Mirai is wanted |
| **P-2** | Room form: a switchable configuration of the same window (like the Eye Lab) or a separate window? | Same window, view state saved and restored (answers audit A6 for Paint) |
| **P-3** | Go for the Core field `SceneObject.paint` + scene format v14 (CORE_V1_FREEZE §7)? | Yes, additive, written only when used |
| **P-4** | The existing texture (ZBrush) stays untouched as the base layer; paint above it? Where does the flattened result go on export? | Yes; flattened PNG written on save / export beside the scene |
| **P-5** | Default resolution | 2048² (= the ZBrush texture), 1024² as the fast option, 4096² not on the reference PC |
| **P-6** | Paint input: plain LMB drag inside the room only? Radius Shift+wheel, opacity Alt+wheel? | Yes; no keymap entry before "Taste passt" |
| **P-7** | Brush radius in world (% of the bounding radius, like Soft) or in screen pixels? | World (consistent with Soft and Brush O-3) |
| **P-8** | Paint while posed / with a morph mix > 0 %? | Allowed (writes no mesh data); footprint on the drawn surface |
| **P-9** | Symmetric paint: mirror in rest space across the mesh's plane, also in a pose? | Yes |
| **P-10** | SubD shown while painting (Phase 2) | Paint on the cage with SubD shown off in the room; SubD surface painting in Phase 3 |
| **P-11** | Paint undo memory budget (History has no limit) | Before-tiles only, compressed; budget decided after the RPC probe |
| **P-12** | Initial blend modes | Normal; Multiply in Phase 3 |
| **P-13** | Faces without usable UVs (zero area, overlap, unmapped) and Attach of painted objects | Shown and skipped with a status line; Attach refused when looks differ; GoZ UV change refused until UV transfer exists |
| **P-14** | Eyes excluded from painting (iris / sclera keep their own maps)? | Yes |
| **P-15** | No pressure / tablet input | Yes (no tablet on the reference PC) |
| **P-16** | Colour stays display-referred 8 bit (no sRGB-linear) until Lookdev decides | Yes |
| **P-17** | Does the GUI Bestandsaufnahme's "no icon toolbar / no own paint mode" hypothesis apply to a Paint Room? | A compact text strip in the room only |

---

## 12. What this report did not verify

- No reference-PC numbers: every [C] row needs P-A … P-F (§8.5) on the RPC; the ×3 factor is REFERENCE_HARDWARE's NumPy
  factor, not a paint measurement. Container NumPy was 2.5.3, not the pinned 2.2.6.
- No GL code ran: upload, mip regeneration, the textured draw with a live texture and the driver penalty (§8.4) are
  hypotheses.
- The cause of the Gollum head's UV overlaps (§2.2) was not traced to an operation.
- The probes rasterised fan triangles of the stored faces; for concave faces the draw uses ear clipping
  (`viewport/derived.py`) — a real map must use `triangulate_mesh_face`.
- External DCC behaviour ([E]: Ptex support, dilation practice) was not re-checked against current product docs.
- No test suite was run: no code changed (AGENTS.md §8a).

## Sources (code and docs)

`src/core/mesh.py`, `corner_uvs.py`, `layer_storage.py`, `scene.py`, `serialization.py`, `history.py` ·
`src/viewport/gl_render_store.py`, `material.py`, `derived.py`, `gpu_picker.py`, `render_mesh.py` ·
`src/mirai/application.py`, `controllers/objects.py`, `controllers/gestures.py`, `viewport/display.py`,
`viewport/picking.py`, `viewport/box_select.py`, `texture_files.py`, `iris_import.py`, `sclera_map.py`,
`morph_targets.py`, `layer_declarations.py`, `interaction/bindings.py`, `soft_selection/influence.py`,
`subdivision/catmull_clark.py`, `subdivision/preview.py`, `topology/extrude.py`, `inset.py`, `bevel.py`, `bridge.py`,
`mesh_assembly.py` · `src/interop/goz/texture.py` · `src/gui/imgui_layer.py`, `eye_panel.py` · `config/keymap.json`,
`requirements.txt` · `scenes/Gollum_Head_rigging_test.mirai.json` and its texture. Docs: AD-003, AD-022, AD-023,
AD-024, AD-025, AD-026, AD-027, AD-028 §7.1, AD-030, AD-031, AD-033 §16, AD-035, CORE_V1_FREEZE §7,
REFERENCE_HARDWARE, `docs/design/GUI_Bestandsaufnahme.md`, `MODELING_ON_DEFORMED_SURFACES.md` §15–§16,
`docs/research/BRUSH_SYSTEM_FEASIBILITY_AND_ARCHITECTURE_RESEARCH_2026-11-18.md`,
`CONTEXT_SENSITIVE_INPUT_ARCHITECTURE_RESEARCH_V1.md` §6 B, `viewport/ARCHITECTURE_AUDIT_2026-10-20_VIEWPORT_MESH_WORKSPACES.md`
§6, `future_ideas/ZBRUSH_BRIDGE_AUDIT.md` §2.7, `future_ideas/MODELING.md` (UVs), `WP_GOZ_P3_PLAN.md`,
`experiments/drag_cost/RESULTS_O2_REFERENCE_PC_2026-11-11.md`.
