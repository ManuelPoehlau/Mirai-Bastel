# AD-026 — Face-Corner UVs and a Texture per Object (OBJ import, viewport display)

**Status:** DECIDED and IMPLEMENTED (2026-10-29), display and key-free toggle `PROVISIONAL`; Manu's practical test B24
pending.
**Request:** Manu, 2026-10-29 (chat): no UV editor, no texture painting yet — but an OBJ that already has UVs and a
texture (e.g. the gollum mesh taken from Mirai to ZBrush, UVs made and a simple texture painted there, brought back)
should import with its texture visible in the viewport while modelling, preserved as well as possible ("mir ist bewusst,
dass letzteres nur teilweise möglich ist"). One texture per mesh.
**Builds on:** [AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) §4.5 ("Corner-domain data (UVs) would use the
same primitive hook on (face, vertex) corners — not now"; now), [AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md)
(change journal, exactness contract), [AD-018](AD-018-PRODUCTION-DRAW-BINDING.md) (face data by `gl_PrimitiveID`),
[AD-024](AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md) (per-object look), [AD-007](AD-007-SHARED-ASSET-LOADER-OWNERSHIP.md)
(the shared OBJ loader), [CORE_V1_FREEZE](CORE_V1_FREEZE.md) §7 / §7.1. Answers audit question A4
([Audit 2](../research/viewport/ARCHITECTURE_AUDIT_2026-10-20_FUTURE_REQUIREMENTS.md) K2) and the UV line of
[MODELING.md](../future_ideas/MODELING.md) for the display part.

## Kurzfassung für Manu (Deutsch)

- **Was jetzt geht:** Eine OBJ-Datei mit UVs (`vt`) bringt ihre UVs mit; liegt eine Textur dabei, zeigt der Viewport sie
  auf dem Mesh. Die Textur findet Mirai über die MTL-Datei (`map_Kd`) oder, wenn es die nicht gibt, als Bild mit demselben
  Namen wie die OBJ-Datei daneben (`gollum.obj` → `gollum.png`, auch `.jpg`, `.bmp`, `.tga`, `.tif`). Import über das
  `Leertaste`-Menü (Ordner `obj/`) oder `python src/main.py pfad/zu/gollum.obj`.
- **Beim Modellieren:** Verschieben, Drehen, Skalieren, Tweak, Soft, Smooth, Morph — die Textur klebt am Mesh. Split, Loop
  Insert, Knife, Connect, Collapse, Dissolve, Delete, Extrude, Cap und die Spiegelkopie rechnen die UVs der neuen oder
  geänderten Flächen aus ihren Nachbarn mit; UV-Nähte bleiben erhalten. Grenzen: Extrude-Wände bekommen keine eigene
  Fläche in der Textur (ein gestreckter Streifen), ein Cap über ein Loch an einer Naht liest die UVs einer Seite, die
  SubD-Fläche verteilt die Textur linear (minimal anders als ZBrush mit „Smooth UV“).
- **Speichern / Export:** Die Szene speichert UVs und den Pfad der Textur (Szenendatei Version 6; das Bild selbst wird
  nicht kopiert). „OBJ exportieren“ schreibt die UVs mit, ZBrush behält sie also beim nächsten Hin und Her.
- **Anzeigen an/aus:** im `Leertaste`-Menü die Zeile „Textur anzeigen: an/aus“ (erscheint nur, wenn ein Objekt eine Textur
  hat; keine neue Taste). In Modus `4` zeigt ein ausgewähltes Objekt seine gelbe Auswahlfarbe statt der Textur
  (`PROVISIONAL`, damit du siehst, was gewählt ist).
- **ZBrush-Hinweis:** ZBrush speichert Texturen auf dem Kopf. Vor „Texture → Export“ in ZBrush **Flip V** drücken (sonst
  steht die Textur in Mirai verkehrt). In den OBJ-Export-Einstellungen von ZBrush „Mtl“ an und die Textur gleich benennen
  oder neben die OBJ legen — dann findet Mirai sie.
- **Praxistest B24** steht unten (ca. 15–20 Minuten).

## 1. Decision

1. **UVs are Core data of the Mesh, per face corner.** The mesh stores, per face, one `(u, v)` per boundary corner in
   boundary order (`Mesh._face_uvs: dict[FaceId, tuple[UV, ...]]`). A corner is (face, vertex) — unique because no
   boundary repeats a vertex (audit 2026-10-27, C). This is the domain a UV seam needs (one vertex, two UVs) and the one
   OBJ, Blender (`CD_PROP_FLOAT2` on loops) and ZBrush use. One UV map per mesh (Manu: one texture per mesh); a second map
   would be a keyed extension of the same storage.
2. **The Core carries them through every topology primitive** (§3), journaled like boundaries (§4), saved with the mesh
   (§5). Positions-only edits never touch them, so every transform, Tweak, Soft, Smooth, Relax and Morph keeps the
   texture glued to the surface for free.
3. **The texture is an object attribute, not mesh data:** `SceneObject.texture: str | None`, the path of an image. The
   Core stores the path and nothing else; loading and display live in `src/viewport`.
4. **Display:** a second, textured GL program (vertex → geometry → fragment) used only for a store whose mesh has UVs and
   whose material carries a texture; per triangle slot a `triangle_uvs` buffer. Everything else draws exactly as before
   (§6).
5. **No UV editing, no painting, no baking** (Manu: "brauche ich noch nicht"). UVs only come from a file.

Why not a point layer (AD-025): point layers are per vertex — a UV seam is two values at one vertex. Why not outside the
Mesh (app store, Scene): it would desynchronize on Undo, Knife checkpoints, Extrude cancel and nested Collapse rollbacks
unless every commit boundary mirrored the journal (the argument of AD-SYM-01 §1.1, AD-REGIONS-01 §1.2, AD-025 X-2). Why
not infer after the fact from the journal (the regions pattern, AD-025 X-1): the journal holds neither `t` of a split
nor the parent of a Knife point; a geometric re-fit would be the medium-reliability inference AD-025 X-5 rejected.

CORE_V1_FREEZE §7 checklist: (1) requirement — Manu's ZBrush round trip; (2) not solvable with the public API — the Mesh
had no corner domain and nothing outside the journal survives rollbacks; (3) problem — audit K2; (4) smallest extension —
one dict on the Mesh, one write path, one record slot, additive API and file key; (5) contract tests —
`tests/test_core_face_uvs.py`; (6) done in this change.

## 2. Data model and API (names `PROVISIONAL`)

- `Mesh.has_face_uvs()`, `face_uvs(fid) -> tuple[(u, v), ...] | None`, `corner_uv(fid, vid)`,
  `set_face_uvs(fid, uvs | None)` (validated: one finite pair per corner; journaled).
- `Mesh.add_face(vertex_ids, uvs=None, *, infer_uvs=True)`: explicit UVs, else — on a mesh that has UVs — inferred from
  the neighbours (§3), unless `infer_uvs=False`.
- **Invariant U1** (`tests/mesh_invariants.assert_uv_invariants`): UVs only for live faces, exactly one finite pair per
  boundary corner; a face may have none ("unmapped"; drawn in the base colour). The mesh has UVs while any face has.
- `core/corner_uvs.py`: validation and the arithmetic (lerp, mean, mean value coordinates).
- `SceneObject.texture` (`Scene.add_object(..., texture=)`), `viewport.material.Material(color, finish, texture)`.

## 3. Per-operation rule

| Operation (primitive) | UVs of the result |
|---|---|
| Move / Rotate / Scale / Tweak / Soft / Smooth / Relax / Slide / Re-Symmetrize / Morph / Apply transform | unchanged (positions only) |
| `split_edge(e, t)` (Split, Edge Connect, Loop Insert, Knife edge points) | in **each** adjacent face its new corner = (1 − t)·uv(v0) + t·uv(v1) of that face's corners — a seam along the edge stays |
| `connect_vertices`, `split_face` with k = 0 (Vertex Connect, chords) | both faces take the parent's corners |
| `split_face` with interior points (Knife) | boundary corners from the parent; an interior point gets its mean value coordinates over the parent polygon (Hormann & Floater 2006 — exact for an affine map on a planar face; the rule AD-025 §4.1 documents for a caller without a triangle). Always, also when the Knife passes `origins` on a layered mesh: a mesh with morph targets cuts its UVs exactly like one without (`tests/test_layer_knife.py` pins "the cut is the one without layers"); the hit-triangle weights would differ on warped faces |
| `collapse_edge` (Collapse, chained by `collapse_elements`) | in the edge's faces the survivor gets the mean of its two corners; in the other faces around both ends a corner moves to that mean only where its value equals the edge face's (no seam), otherwise it keeps its value |
| Dissolve V/E/F (merge, cleanup) | a merged face takes at each corner the value of the old face that carried the outline edge leaving that corner (exact, seams included); a face that only loses chain vertices keeps its other corners; a region with an unmapped face gives an unmapped result |
| Delete V/E/F, `remove_face` | the faces' UVs go |
| Extrude (tool) | cap = its source face's UVs; a wall = its source face's UVs at its two corners, top and bottom (a line in UV space, Blender's result as well) |
| Cap, symmetric Cap, any `add_face` without UVs | inferred per corner: the UV of that vertex in an existing face sharing an edge of the new boundary, else in any face with that vertex (ascending ids); unresolved corners = mean of the resolved ones; none resolved = unmapped. A hole on a seam cannot know its side — documented limit |
| Mirror copy | values unchanged, following their corners through the reversed winding; the copy keeps the texture |
| Symmetric coordinators | each side through its own primitive call (as AD-025 §3) |
| Undo / Redo / rollback / Knife checkpoints / `load_state` | exact records (§4) |
| OBJ import / export, scene file | §5 |

## 4. Journal (AD-023 exactness contract)

`MeshChange.face_uvs` holds the before-tuple of every face whose UVs were written (`None` = had none), recorded by the
one write path `_write_uvs` for every active log (watches too: tuples are immutable, nothing is copied). `MeshDelta.face_uvs`
is `{fid: (before, after)}` for the ones that differ; `end_change`, `rollback_change`, `revert_change`, `apply_delta`,
`MeshChange.is_empty`, `MeshDelta.empty` and `load_state` under a journal take it into account; `_apply_uv_records` runs
after the element records. Readers outside the Core updated: the Knife's `SessionStart.unchanged()` / `.state()`, the
morph mix's `_topology_delta` (the shown surface follows the base's UVs), the SubD provider (a UV-only change re-patches
the derived surface), `RenderMesh` (a UV-only change re-writes the face's triangle slots). Exactness checked by
`test_journal_undo_redo_rollback_exact` and 25 random sequences (`test_random_sequences_keep_invariants_and_undo_exactly`).

## 5. Files

- **Mesh state:** additive key `"face_uvs"`: `null` or `{"<fid>": [[u, v], ...]}`, face ids ascending; validated whole
  before the first write (missing face, wrong corner count, non-finite value → `ValueError`, mesh unchanged).
- **Scene file version 6:** written when any mesh has UVs or any object a texture (`"texture"` on the object, only then);
  otherwise 4 / 5 exactly as before. An older build refuses a version-6 file instead of dropping UVs on its next save
  (the AD-025 m-6 rule). Read: 2–6. The image is referenced by absolute path, not copied.
- **OBJ import** (`examples/loaders/obj_loader.py`, additive fields): `vt` (u, v; w dropped), the faces' `vt` indices
  (negative indices supported; a face whose tokens do not all carry a `vt` is unmapped), `mtllib` / `usemtl`.
  `find_texture(obj_path, data)`: `map_Kd` of the first used material (options like `-s`, `-bm` skipped; a path from another
  machine, as ZBrush writes it, is tried by its file name beside the OBJ), else an image with the OBJ's name beside it.
  No V flip — OBJ and OpenGL agree (v up). The head basemesh, Man_With_Shoes and SubD_Cube in `examples/meshes` carry
  UVs and now load with them (no texture).
- **OBJ export:** one `vt` per distinct value in first-use order, `f v/vt`; unmapped faces as `f v`.

## 6. Display

- `RenderMesh` creates `triangle_uvs` (6 floats per triangle slot, its three corners in index order;
  `UNMAPPED_U = -1e30` for an unmapped face, a free or a hidden slot) only while `material.texture` is set **and** the mesh
  has UVs. It follows the triangle slots like `triangle_faces` (written wherever a topology patch writes triangles;
  incremental, AD-023), and is never touched by a position drag. Without a texture nothing is allocated or uploaded.
- `GLRenderStore`: `declare_triangle_uvs` (an optional face-data buffer, RG32F, unit 3), `set_texture(path)`; the image
  is loaded once per path, modification time and size (`load_texture`: mipmapped, repeat, linear; re-exporting the image
  under the same name shows at the next draw; a file that cannot be read prints one line and draws untextured). The **textured program** reuses the plain program's attribute locations (as the GPU picker
  does) so it draws the same VertexList; its geometry shader adds per-corner barycentrics and passes `gl_PrimitiveID`
  through, so the fragment shader (`FRAGMENT_SRC` with `TEXTURED`) reads the face data and the triangle UVs by the same
  triangle number. Lighting, Flat / Smooth normals, specular and the region tint (now mixed with the texture colour) are
  the plain program's code. Draws without a texture use the plain program: bit-identical to before
  (`test_without_texture_the_draw_is_the_untextured_one`).
- Per-triangle linear UV interpolation, as every rasterizer does; on a quad that is the triangulation's diagonal, not a
  bilinear patch (the texture is continuous across it; on a strongly non-planar quad a slight kink can show).
- **SubD:** the derived mesh gets face-varying *linear* UVs (`catmull_clark.refine_face_uvs`, OpenSubdiv's
  `FVAR_LINEAR_ALL`): sub-face corners = parent corner, edge midpoints, centre — seams exact, no UV crosses its island.
- **App:** `Application._shown_texture`: an object's texture while `DisplayState.show_texture` (SPACE menu row
  "Textur anzeigen: an/aus", `src/obj_files.py`; no key, so no BindingSet change), not while it is highlighted in mode `4`
  (`PROVISIONAL`). Imported objects, the startup OBJ (`python src/main.py file.obj`), References, mirror copies and the
  morph editing view carry their texture.

## 7. Not in scope / open

- UV editing, unwrapping, texture painting, baking, several UV maps or textures per object, UDIM tiles, normal maps,
  per-corner normals. The data model leaves room (a keyed UV map, a corner domain for split normals).
- Copying the image into the project, relative texture paths, sRGB-correct display (the image's values are used as the
  base colour directly, like the base colour itself).
- Open for Manu (B24): is the selection tint replacing the texture in mode `4` right; is "Textur anzeigen" in the menu
  enough or does it want a key; is the texture's brightness under the Worklight right.

## 8. Verification and measurements

- Tests (all container): `tests/test_core_face_uvs.py` (20: every primitive incl. seams, journal exactness, file,
  random sequences, mean value coordinates), `tests/test_obj_uvs.py` (8: loader, MTL, texture search, import, export
  round trip, scene file), `tests/test_texture_app.py` (8: app plumbing, menu row, Extrude + Undo, mirror copy, SubD),
  `tests/test_gl_texture.py` (5, real GL under xvfb: texture shows on its UVs, a UV change and an unmapped face, no
  texture = the untextured draw, an unreadable image falls back, a re-exported image shows at the next draw);
  plus a visual check of the real app path in the container (head basemesh with its own UVs and a checker image:
  textured, unchanged after 40 edge splits and after random Dissolve / Collapse, textured on the SubD surface).
- Measured in the container (Linux, Python 3.13, llvmpipe; not the reference PC, which runs Python ≈ 2× slower): see
  §8.1.

### 8.1 Measurements

[C] container (Linux, Python 3.13, best of 3; runs vary up to ~1.5× between runs), gollum_20k (21 875 v / f) with
synthetic planar UVs (one per vertex, so no seams), probe script outside the repository:

| | before AD-026 (`305c8e5`) | now, mesh without UVs | now, mesh with UVs (+ texture where it matters) |
|---|---|---|---|
| build the mesh from OBJ data | 207 ms | 227 ms | 318 ms |
| `split_edge` / `collapse_edge` (300 / 100 random, one recording) | 403 / 401 µs | 290 / 306 µs | 306 / 393 µs |
| `end_change` / Undo of those 400 operations | 7.6 / 30.8 ms | 5.0 / 11.9 ms | 3.2 / 12.3 ms |
| `RenderMesh` build (TraceStore) / topology patch after one split | 702 / 0.23 ms | 551 / 0.21 ms | 551 / 0.23 ms (with texture: `triangle_uvs` built and patched) |
| SubD level 1 / level 2 build | 4.2 / 20.5 s | 3.4 / 20.6 s | 3.9 / 23.7 s |

Reading: a mesh without UVs costs what it cost (the "before" / "now" spread is run noise); with UVs the operations and
the viewport patch are unchanged within noise, the import is ≈ 40 % and the SubD build ≈ 12–15 % slower (the derived
surface's UVs). Not measured: the reference PC (≈ 2× slower Python, other GPU) — the textured program adds a geometry
shader, cheap on desktop GPUs but unmeasured there; B24 asks for the feel.

## Praxistest B24 für Manu (Deutsch, ca. 15–20 Minuten)

Vorbereitung in ZBrush: gollum (oder den Kopf) aus Mirai exportieren (`Leertaste` → „OBJ exportieren“, Ordner `obj/`),
in ZBrush UVs erzeugen (z. B. UV Master), eine einfache Textur malen (Polypaint → Texture from Polypaint), **Texture →
Flip V**, Textur als PNG exportieren, das Mesh als OBJ exportieren (Textur gleich benennen wie die OBJ oder MTL an). Beides
in den Ordner `obj/` legen.

1. `python src/main.py`, `Leertaste` → „OBJ importieren: gollum…“. **Erwartung:** das neue Objekt zeigt die Textur;
   die Statuszeile nennt die Textur. Steht sie auf dem Kopf: Flip V in ZBrush vergessen?
2. Ins Objekt wechseln (`4`, Objekt anklicken, `1`). Punkte und Flächen verschieben (`W`/`E`/`R`), Soft (`O`), Smooth
   (`S`), ein Morph-Ziel (`Ctrl+N`): **Erwartung:** die Textur klebt.
3. Topologie: Loop Insert (`I`), Knife (`C` ohne Auswahl) quer über eine UV-Naht, Collapse (`Shift+C`), Dissolve,
   Extrude (`T`), Undo/Redo. **Frage:** bleibt die Textur „gut genug erhalten“? Wo stört es am meisten?
4. SubD (`V`): **Erwartung:** die Textur liegt auf der glatten Fläche.
5. `Leertaste` → „Textur anzeigen: an/aus“; in Modus `4` das Objekt auswählen (gelb statt Textur) — **passt das so?**
6. `Strg+S`, App neu starten, Szene laden: Textur wieder da. „OBJ exportieren“ und in ZBrush öffnen: UVs noch da?

| # | Verdikt (KEEP / ITERATE / REJECT) | Notiz |
|---|---|---|
| 1 Import + Textur sichtbar | | |
| 2 Textur klebt beim Formen | | |
| 3 Topologie-Werkzeuge | | |
| 4 SubD | | |
| 5 An/aus, Auswahl in `4` | | |
| 6 Speichern, Export nach ZBrush | | |
