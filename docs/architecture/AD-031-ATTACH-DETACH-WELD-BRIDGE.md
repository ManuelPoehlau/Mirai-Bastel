# AD-031 — Attach, Detach, Weld, Bridge: assembling, separating and connecting mesh parts

**Status:** DECIDED (Manu, 2026-11-09): D1–D9 and D11 approved as proposed; D10 decided as a world-space threshold
with a **provisional** reference default (§4.1), the numeric value is not artist-approved. **NOT IMPLEMENTED** — each
phase P1–P7 (§11) starts only with its own go. Open points: §10.
**Scope:** `src/mirai` and `src/gui` only. **No Core change, no file-format change, no keymap change** (no keys at all).
**Builds on:** AD-001 (ids), [AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) (objects, L-1 / L-3),
[AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) (journal), [AD-024](AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md),
[AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) (point layers, H1–H5), [AD-026](AD-026-FACE-CORNER-UVS-AND-TEXTURE.md),
[AD-028](AD-028-SKELETON-AND-SKINNING.md), [AD-REGIONS-01](AD-REGIONS-01-FACE-REGIONS-STORAGE.md), AD-SYM-01…05,
[AD-030](AD-030-GUI-FRAMEWORK.md). Basis: `main` @ `f76287f`.
**Evidence:** code reading (§1) and a prototype verification run (§9), kept outside the repository and outside
`tests/` on purpose.

## Kurzfassung für Manu (Deutsch)

- **Attach** (Modus `4`): die ausgewählten Objekte werden Inseln im Mesh des Edit-Objekts. Die Form bleibt in Welt-
  koordinaten, nichts wird verschweißt. Ein Undo-Schritt; beim Undo kommen die Quellobjekte unverändert zurück.
- **Detach** (Flächen): die gewählten Flächen werden ein neues Objekt mit derselben Platzierung (bitgenau). Mit
  Symmetrie wird – wie bei Delete – das Spiegelbild mitgenommen.
- **Weld** (Punkte, Abstand): verschmilzt nur ausgewählte, unverbundene Punkte, exakt auf den Schwerpunkt der Gruppe,
  unabhängig von der Reihenfolge; lehnt alles ab, was unerwartete Topologie ergäbe. Der Abstand ist immer als Zahl
  sichtbar und änderbar; der Startwert (0,001 × Diagonale) ist vorläufig.
- **Bridge** (zwei Ränder gleicher Punktzahl): Quads dazwischen, keine neuen Punkte → Morphs und Gewichte unberührt;
  die neuen Flächen haben keine UVs und keine Gruppe.
- **Nichts wird stillschweigend zusammengelegt oder verworfen:** Morph-Ziele und Gruppen der Quelle kommen mit und
  werden bei Namensgleichheit umbenannt (eine umbenannte Gruppe bekommt dadurch eine andere Farbe). Abweichendes
  Material oder Textur wird abgelehnt oder nur über den ausdrücklichen Menüpunkt „Attach – Look des Ziels übernehmen“
  übernommen.
- **Grenze:** Re-Symmetrize geht nicht, solange angehängte Inseln unverbunden sind, und nicht an abgetrennten Teilen
  ohne Naht (§3.5).
- Offen bei dir: §10.

## 0. Decision in one screen

1. Commands **Attach**, **Attach – take destination look**, **Detach**, **Separate by Islands**, **Select Linked**,
   **Weld**, **Bridge** — command constants without default keys (precedent `OBJECT_MANAGEMENT_COMMANDS`), reachable
   through a "Mesh" menu, the outliner context menu and `dispatch_command`.
2. One shared kernel `src/mirai/mesh_assembly.py` (name `PROVISIONAL`): `append_object(dst, src)` and
   `extract_faces(mesh, faces)` over the public Mesh API. Weld = `Mesh.add_edge` + `core.operations.collapse_elements`
   (`src/mirai/topology/weld.py`); Bridge = `Mesh.add_face` over `topology.border` loops (`src/mirai/topology/bridge.py`).
3. Every operation is **one** `Application._mesh_transaction` (one recording, one `MeshDeltaCommand`) with its object
   commands as the existing `companion`; every check runs before the recording and only reads; a refusal changes
   nothing (fail-closed).
4. **Never merge by name.** Morph targets and regions of a source are carried as separate data; identity across meshes is
   asserted only by a later explicit artist command.
5. Symmetry is never edited implicitly: Attach keeps the destination's definition and refuses a result that makes
   existing points ambiguous; Detach mirrors like Delete and gives the new object the definition Shift+S would derive.

## 1. Verified facts

| # | Fact | Where |
|---|---|---|
| F1 | Material and texture belong to the object (`SceneObject.material`, `.texture`); UVs are per face corner in the Mesh; there is no per-face material; no app command sets or clears a texture | `core/scene.py`, AD-024, AD-026, `interaction/commands.py` |
| F2 | A morph target is a `VECTOR` point layer. Identity = `LayerId` from a per-mesh allocator; metadata `name` (unique per mesh, freely renamable, default `Target N`), `kind`, `new_point`. No cross-mesh identity or link (mirror copy: "no link", AD-025 §16.2) | `core/mesh.py` `PointLayerInfo`, `mirai/morph_targets.py` |
| F3 | Morph runtime state — dial weights, current target, editing view — is view state keyed `(ObjectId, LayerId)` in `MorphSurfaceProvider`, read from the mesh on demand; there is no registration step. The morph panel model reads `Application.morph_target_rows()` | `morph_targets.py:369`, `gui/morph_model.py` |
| F4 | Skin weights: one `WEIGHTS` layer bound per mesh (`skinning.skin_layer`), keys = `BoneId`s of the one scene rig; skinning is invariant under a frame change (`A = T⁻¹ S T`) | AD-028 §3.1–§3.3, `mirai/skinning.py` |
| F5 | Regions: `FaceRegions` = ordered tuple of `FaceRegion(name, frozenset[FaceId])`. **Identity = name** (unique per mesh; there is no region id). The Core allows overlap; the app's group commands keep one group per face. Dead ids stay stored (Undo can revive them). **The tint colour is derived from the name** (`regions.slot_index`) | `core/mesh.py:325`, `mirai/regions.py:50` |
| F6 | Region inheritance (`regions.inherit_into`, run inside `_mesh_transaction`) gives a **created** face the regions of the removed parents found in the journal. A created face without a removed parent (Cap, Bridge, an appended copy) gets nothing from the hook, and the hook never removes memberships the mutation set itself | `regions.candidate_parents`, `inherit_children` |
| F7 | Symmetry correspondence is exact and position-based (no tolerance); seam = the declared edges; coincident points are AMBIGUOUS; symmetric operations refuse unpaired selections | `mirai/symmetry.py`, `mirai/symmetric_ops.py` |
| F8 | Re-Symmetrize pairs topologically from the seam: it refuses without seam edges (`"keine Seam auf der Ebene — nichts zu spiegeln"`) and when the seam does not split the mesh into exactly two face components (`"Seam teilt das Mesh in {n} Teile (nötig: genau 2)"`) | `mirai/resymmetrize.py:114`, `symmetry_topology.topological_sides` |
| F9 | `collapse_elements` computes the centroid and the per-layer group mean (`combine_values(kind, …, "mean")`) from the **original** values before any merge and writes them over the chain's pairwise results | `core/operations/collapse.py:72` |
| F10 | `collapse_edge` on a free edge (no faces) leaves every face's corner UVs as they are | `Mesh._plan_collapse_uvs` |
| F11 | `add_face` without UVs infers each corner from neighbour faces (Cap's rule) — right for one hole, misleading across two UV islands | `Mesh._infer_uvs`, AD-026 §3 |
| F12 | Viewport topology changes are dirty flags processed once per frame; Undo / Redo of a mesh step re-syncs the object views | `viewport/viewport.py:816`, `Application._apply_undo_redo` |
| F13 | A dial value set on a target whose layer an Undo removes is hidden (`object_weights` filters dead layers) but stays stored and **reappears on Redo**; a target deleted through the morph controller loses its value for good | prototype §9, `tests/test_morph_multi.py` |

## 2. Operation contracts

### 2.1 Attach (mode `4`)

- **Destination** = the edit object. **Sources** = the selected objects other than it; a group stands for its leaves.
- **Positions:** `to_object(dst, to_world(src, p))`; verbatim when placement and pivot are equal (bit-exact).
- **Topology:** each source becomes islands with new ids; loose edges are carried; nothing is welded or moved.
- **Data:** §3 (look, layers, regions, UVs, symmetry, mirror pairs).
- **Sources** are removed in the same step (`DeleteObjectsCommand`); pairs containing a source are removed
  (`MirrorPairCommand`). Undo restores the same instances, ids, layers, regions and pairs.
- **Refused before any change:** an interaction is running; no source; a source is a Reference; the morph editing view
  is open; an involved object has a morph dial above 0 %; the rig is posed and a bound mesh is involved; the refusals
  of §3.
- **Afterwards:** mode `4`, the destination selected.
- **Variant "Attach – take destination look"** (D1): as Attach, the sources' look is replaced (§3.1).

### 2.2 Detach (component mode, faces)

- Input: the selected faces; in vertex / edge mode refused with "press 3" (Select Linked helps to pick an island).
- **With a symmetry definition:** the selection is expanded by its partner faces (`symmetry_coordination.expand_faces`,
  as symmetric Delete); an unpaired face refuses with the existing `TEXT_UNPAIRED`. The source deletion runs through
  `symmetric_ops.coordinate_delete`.
- **New object:** built by `extract_faces` without a journal (a fresh instance owned by `AddObjectCommand`): boundary
  vertices are copied, every point layer is copied with name and rule (identity map), UVs and the regions restricted to
  the extracted faces (§3.3); same transform, pivot, material, texture and state; symmetry §3.5.
- **Source:** `Mesh.delete_faces` (or the coordinator) leaves open borders; the Core deletes the layer values of removed
  points.
- One step: `MeshDeltaCommand(source)` + `AddObjectCommand(new)` as the companion. Refused while posed and on the
  morph editing view. Afterwards: per O-8 (§10).

### 2.3 Separate by Islands

Detach of every face-connected component but one (the one that keeps the object: O-12); one deletion call, k meshes
built without a journal, one composite step; the data rules of Detach.

### 2.4 Weld — §4. 2.5 Bridge — §5.

## 3. Data policies

### 3.1 Look: material and texture (D1)

Look = `(material, texture)` with `None == None`. All sources equal to the destination → Attach, UVs carried.
Different → **refused**; the status line names the object and what differs. The explicit variant **"Attach – take
destination look"** gives the sources the destination's look; their UVs stay as mesh data (they now show the
destination's texture); the status line lists the replaced looks; Undo restores the sources with their own look.
Detach copies the look. **Later (own AD):** a per-face material id, region-bound materials, several textures per object.

### 3.2 Point layers (D2, D3)

| Case | Rule |
|---|---|
| A source target, any destination | **New layer**, name `"<source object> · <target>"`, `kind` and `new_point` copied, values mapped by `M = (s_src / s_dst)·R_dstᵀ·R_src` (identity when the placements are equal) |
| Same name on both sides | Not merged (the prefix makes it a different name) |
| Same name, different kind | Not merged; the prefix resolves the clash |
| A destination-only target | The new points get the default (zero offset) |
| Several sources | Each source's targets carry its own (unique) object name |
| Name still taken | `" 2"`, `" 3"` … appended |
| More than `MAX_TARGETS` (64) targets | Refused |
| Skin weights | Merged into the destination's skin layer (created as `"Skin"` if absent), values unchanged (F4); more than one `WEIGHTS` layer on a mesh → refused |
| Unweighted source, bound destination | Allowed; the new points are unbound (they stay at rest in a pose); the status line counts them; no automatic weights |
| A morph dial above 0 % on an involved object, or a posed rig with a bound mesh | Refused (D3) |

**Verified runtime lifecycle of carried targets** (prototype §9, existing app code unchanged):

| Stage | Behaviour |
|---|---|
| Identity / metadata | New `LayerId`s on the destination; names `"Ear · Wiggle"`, `"Ear · Smile"`, `"Ear.001 · Wiggle"`, `"Ear.001 · Smile"` after the destination's own `"Smile"`; kind `VECTOR`, `new_point` copied; the destination's own `LayerId`s unchanged |
| Registration | None needed (F3): `morph_target_rows()` and the morph panel model list them at once |
| Initial dial | 0 % for every carried target; the destination's current target is kept |
| Function | Dialled on the destination, the carried targets reproduce the source's own world-space mix (to 1e-12, rotated, scaled source with pivot) |
| Editing view | Opens (Tab) on a carried target and closes |
| Save / Load | `scene_to_json` → `scene_from_json`: same `LayerId`s, infos and values |
| Undo | The destination loses exactly the carried layers; the sources come back as the same instances with their own layers and `LayerId`s; the mirror pair returns; the panel lists only the destination's own targets |
| Redo | The destination's state equals the post-Attach state exactly (same `LayerId`s, values, regions) |
| Dial state across Undo / Redo (D11) | **Decided:** Undo of Attach removes the runtime dial state of carried targets; Redo recreates them at 0 %. Today's app keeps the hidden value and shows it again on Redo (F13); P2 adds the prune to the morph controller's after-history step (view state only; verified with a prototype prune, §9) |

### 3.3 Regions (D2b)

- **Every source region survives Attach** with the remapped live faces of the source. The copies keep their membership
  explicitly; the inheritance hook adds and removes nothing for them (F6). Order: the destination's regions unchanged,
  then each source's regions in source order (sources in `ObjectId` order).
- **Collision-safe names** (identity = name, F5): a free name is kept; a taken `Group N` is renumbered with
  `regions.new_group_name` over the combined list (it stays an automatic group); any other taken name becomes
  `"<source object> · <name>"`, then `" 2"`, `" 3"` …. Memberships never change.
- **Colour change from renaming (documented consequence):** the tint is a function of the name (`slot_index`: a
  `SET_NAMES` name by its place, `Group N` by `N`, any other name by its characters). A renamed region therefore shows a
  **different colour** than in its source: `"Ear · Brow"` no longer has `Brow`'s colour, a renumbered `Group 2` has the
  colour of number 2. Only the display changes; renaming the region back to a free name restores the colour.
- Dead ids of a source region are not carried (they belong to the source mesh, which Undo restores intact); a region
  without live faces is carried with an empty face set, so no name is lost.
- Faces **created** by an operation (Bridge, Cap) join no region (F6, D9). Weld keeps face ids, so regions stay.
- Detach: the new mesh gets the regions restricted to its faces (names unchanged); the source keeps its regions.

### 3.4 UVs

Attach, Detach, Separate: copied per face (`infer_uvs=False`). Weld: kept per face (F10; a UV seam along the weld stays).
Bridge: none (§5, D8).

### 3.5 Symmetry and mirror pairs (D4, D5)

| | Policy |
|---|---|
| Attach | The destination's definition is never edited (plane, seam). Symmetry state before and after: VALID → VALID ok; → PARTIAL allowed with a status line; a result that makes existing points AMBIGUOUS is refused. Source definitions are dropped. Exact when the destination placement maps its plane exactly onto the pair's world plane (the `applied_symmetry_axis` condition): measured identity and Y-translation VALID, rotated + scaled PARTIAL. |
| Detach | Expansion like symmetric Delete (§2.2). The new object gets `symmetry_axis.definition_for_axis(new_mesh, axis)` — Shift+S's own rule, seam = its edges exactly on the plane — **only if the new mesh's state is VALID**, otherwise no definition (status line). |
| Weld, Bridge | Refused while a definition is set (until P6). |
| Mirror pairs | Pairs containing a source are removed in the Attach step; the destination's pairs stay (they couple placements only); the Detach result is unpaired. |

**Re-Symmetrize limitation for disconnected islands (accepted, D5):** Re-Symmetrize keeps its existing topological
contract (F8) and is therefore unavailable

1. **on the destination while attached islands are not connected to it** — each island is an extra face component, so
   the seam no longer splits the mesh into exactly two parts (refusal `"Seam teilt das Mesh in {n} Teile (nötig:
   genau 2)"`); it is expected to work again once every island is connected to one side (P5 acceptance test, §9.3);
2. **on a detached part without seam edges** — a part away from the plane derives an empty seam (refusal `"keine Seam
   auf der Ebene — nichts zu spiegeln"`).

Everything else symmetric keeps working in both cases (verified, §9.1): position correspondence, mirrored selection,
symmetric Move, the topology coordinators. An empty seam is the correct derived definition for a part away from the
plane. No new symmetry architecture is introduced; a topological correspondence for islands would need its own AD.

## 4. Weld (D6, D7, D10)

### 4.1 Threshold (D10, provisional default)

- The threshold `t` is a **world-space distance**. In object space the operation compares against `t / s` (uniform
  scale, AD-021 Q-4).
- **Provisional reference default:** `0.001 ×` the length of the diagonal of the destination (edit) mesh's **world-space
  axis-aligned bounding box**. This is a documented starting value, **not an artist-approved number**. A zero diagonal
  gives no default; the field then waits for an entry.
- **The actual numeric value is always visible and editable** in the Weld popup (a number field), together with how many
  groups and points it would merge; the status line repeats the value used.

### 4.2 Validity policy

Inputs: the selected, visible vertices; a spatial hash with cell `t / s` (no pairwise O(n²) scan).

| # | Rule |
|---|---|
| W1 | Only selected points take part; the selection order is irrelevant (sets, sorted ids) |
| W2 | Groups = connected components of pairs within `t`; **every** pair inside a group must be within `t` (a clique). A transitive chain whose diameter exceeds `t` → refused |
| W3 | No two members of a group share an edge or a face (that is Collapse) → Weld never removes or degenerates a face |
| W4 | Merged border edges become one manifold edge; duplicate faces and edges with more than two faces → refused (`CollapseRefused`) |
| W5 | No new non-manifold (bowtie) vertex: one face fan around each merged point; checked after the change, exact rollback on failure |
| W6 | Every merged edge is used in opposite directions by its two faces, else refused ("normals disagree"); after the change, rollback |
| W7 | **Group centroid:** position = `Σp / n` of the **original** positions, summed in ascending-`VertexId` order; **point layers = the explicit group mean** `combine_values(kind, [(value, 1/n) …], "mean")` (vectors: the same expression; weights: the convex per-key combination with `math.fsum`); both computed before any merge (F9) — **independent of the merge order** |
| W8 | **Canonical surviving `VertexId`:** the helper edges are created as a star from the group's smallest id (`add_edge(min, v)` for every other member, ascending), so the surviving vertex is **the group's smallest `VertexId`**, for every selection order |
| W9 | UVs per face unchanged (F10); regions unchanged (face ids kept) |
| W10 | A group touching hidden geometry → refused |
| W11 | Status: merged points, the threshold used, and how many points averaged differing layer values (the H3 border effect) |

Plain repeated `collapse_edge` averages pairwise and does **not** give the centroid (verified); W7 holds because the group
rule of `collapse_elements` overwrites the chain's intermediate results. W8 is needed because the surviving id otherwise
depends on the helper-edge order (verified).

## 5. Bridge (D8, D9)

Two closed border loops with equal vertex count (O-11); pairing by minimal summed squared distance over direction and
rotation; `n` quads; winding from the neighbour faces of both loops (refused on conflict); **no new vertices** → point
layers untouched; **no UVs** (`infer_uvs=False`; Cap's inference would stretch across two UV islands, F11; unmapped faces
are drawn in the base colour and exported as `f v`); **no region** (F6, Cap precedent); refused on hidden geometry and
under a symmetry definition (until P6); afterwards the new faces are selected in face mode.

## 6. Transactions, history, performance

- One recording per operation: all sources of an Attach in one `_mesh_transaction`, object commands as its `companion`;
  one viewport notification, one `ObjectController.sync_views`, one selection-history entry. Checks before the
  recording, read-only.
- Detach and Separate build new meshes without a journal; only the source deletion is recorded.
- Avoided: `export_state` / `load_state` copies, per-element notifications, repeated correspondence derivation.
- **Measured** (container, Python 3.13, 22.5k-face source): new mesh without journal 206 ms; append under one recording
  323 ms, with four extra watches 494 ms, with ten layers 431 ms; `delete_faces` 10k / 44k faces 150 / 500 ms; Undo /
  Redo of a 44k-face append 123 / 600 ms. The cost is spread over Core per-element work (`add_face` with edge creation
  and indexing ≈ 70 %, face records at `end_change` ≈ 17 %, journal touches ≈ 7 %); an ear-sized part (≈ 2k faces)
  ≈ 30–45 ms. **No Core change is justified.**

## 7. Gate and classification

- `layer_declarations`: the methods `attach_objects`, `detach_faces`, `separate_islands` and the commands `WELD`, `BRIDGE`
  are DECLARED, each with a rule fixture (plain and, where allowed, symmetric); the enumeration test enforces it.
- The morph editing view gate refuses all of them (topology on the base only); the posed policy counts all of them as
  editing.
- `symmetry_declarations`: Detach uses the removal coordinator; Weld and Bridge stay undeclared and are refused under a
  definition.
- AD-021 receives an addendum with P2: Attach, Detach and Separate are explicit level conversions like Apply transform
  (L-3).

## 8. MVP restrictions

The look must match or be taken over explicitly · targets and regions are never merged · morph dials at 0 % and the rest
pose are required · one `WEIGHTS` layer per mesh, no automatic weights · Attach never edits the symmetry definition and
refuses AMBIGUOUS · Detach works on faces and mirrors under a definition · Weld and Bridge are refused under a symmetry
definition · Weld: selected points, W1–W11 · Bridge: equal loops, no UVs, no region · Re-Symmetrize unavailable while
islands are disconnected and on parts without seam (§3.5) · no Boolean, no remesh, no Core change.

## 9. Verification status

### 9.1 Verified implementation behaviour (existing code, read and exercised)

F1–F13; on a derived definition with an empty seam: position correspondence, mirrored selection, symmetric Move (W drag,
exact mirror), symmetric Collapse, the Delete expansion; both Re-Symmetrize refusals; morph rows, panel model, editing
view and save / load read from mesh state; exact journal restore of layers and regions under Undo / Redo.

### 9.2 Prototype verification (outside the repository)

A throwaway prototype of `append_object`, `extract_faces`, Attach and Detach on the real `Application`
(`_mesh_transaction(companion=…)`, the object commands, the symmetric coordinators, the morph controller), with a pytest
file. It is **not** a regression test and is kept apart from `tests/`; its checks seed the phase tests (§12).
Final run (2026-11-09, `xvfb-run -a python3 -m pytest test_ad031_proto.py -q`, Python 3.13.18, base `f76287f`):
**10 passed, 0 failed.**

| Check | Result |
|---|---|
| Regions survive Attach, collision names (`Ear · Brow`, `Group 2`, `Ear lobe`, `Ear.001 · Brow`, `Group 3`, …), Undo / Redo exact | passed |
| Attach two mirror-copied ears (rotated, scaled, pivot) into `head_basemesh`: VALID, pair removed; Re-Symmetrize refused; Detach with **one** ear's faces expands to both; head VALID, Re-Symmetrize works again; detached pair: empty-seam definition, VALID, mirrored selection, symmetric Move, symmetric Collapse; Re-Symmetrize refused; Undo restores ears and pair | passed |
| Weld 3- and 4-point groups, asymmetric positions, vectors and weights, **all 6 / 24 merge orders**: exact centroid and group mean, no face lost, UVs per face kept | passed (×2) |
| Plain pairwise `collapse_edge` chain is not the centroid | passed |
| Canonical star edges: surviving id = smallest id for every order | passed (×2) |
| Carried morph targets: lifecycle of §3.2 | passed |
| Dial value without D11 reappears on Redo (F13) | passed |
| D11 with a prototype prune: dial state gone after Undo, 0 % after Redo | passed |

Two expectations were corrected before this run: the first version of the weld order test also required the
**surviving id** to be the same for arbitrary helper-edge orders. That is false and led to W8; the values were always
order-independent. The order test now checks the values, and the canonical-edge test checks the id.

### 9.3 Acceptance tests owed by the implementation phases (not yet tested)

| Phase | Acceptance test |
|---|---|
| P2 | Viewport and SubD rebuild after a large Attach (GL, reference hardware); the mixed mesh + object Undo step in the real command path; the D11 prune in the morph controller; skinning invariance under a posed rig (randomized); the look refusal and the explicit variant |
| P3 | A detached part **crossing** the plane derives a usable seam (state VALID, symmetric ops, Re-Symmetrize if the seam splits it in two); Select Linked |
| P4 | W2–W6 refusals (chain, connected members, bowtie, orientation), W10, the threshold field and its default from the bounding-box diagonal |
| P5 | Bridge pairing, winding, refusal on conflicting normals; **Re-Symmetrize works again after the islands are bridged** into the head (component count back to 2) |
| P6 | Symmetric Weld / Bridge, including coincident pre-weld points (AMBIGUOUS correspondence) |
| P7 | Separate by Islands, the kept island (O-12) |

## 10. Decisions

**Decided (Manu, 2026-11-09):** D1 look refusal + explicit variant · D2 targets as `"<object> · <target>"`, never merged
· D2b region naming of §3.3 · D3 refuse with a dial above 0 % or a posed rig · D4 Attach: PARTIAL allowed, AMBIGUOUS
refused · D5 Detach mirrors like Delete, derived definition when VALID; Re-Symmetrize limitation accepted · D6 Weld
strictness · D7 H3 group mean · D8 Bridge without UVs · D9 Bridge without region · D10 world-space threshold, provisional
reference 0.001 × world bounding-box diagonal, always visible and editable · D11 Undo removes the dial state of carried
targets, Redo recreates them at 0 %.

**Open:**

| # | Question | Proposal |
|---|---|---|
| D10-v | The artist-approved default Weld threshold | after the P4 practical test |
| O-1 | Attach destination | the edit object |
| O-2 | Sources after Attach | removed (Undo restores them) |
| O-5 | Unweighted geometry into a bound mesh | allowed with a count in the status line |
| O-7 | Ungrouped source faces join a new region named after the source object | yes |
| O-8 | After Detach: stay in component mode on the source, or mode `4` with the new object selected | stay in component mode |
| O-11 | Bridge MVP only for loops of equal vertex count | yes |
| O-12 | Separate by Islands: which island keeps the object | the one with the most faces |
| O-13 | GUI places: a "Mesh" menu and the outliner context menu | yes |
| P6 | How symmetric Weld handles coincident points (AMBIGUOUS) | decided before P6 |

## 11. Phases

P1 kernel (`append_object`, `extract_faces`, the look / layer / region / symmetry plans) → P2 Attach (+ variant, D11
prune) → P3 Detach (+ Select Linked) → P4 Weld → P5 Bridge → P6 symmetric Weld / Bridge → P7 Separate by Islands. Each
phase: its acceptance tests (§9.3), the doc update in the same commit, a practical test for Manu.
Later: "Combine targets" (explicit identity of two targets), per-face material, Bridge with unequal counts, Target Weld,
weight / morph transfer (AD-025 Phase 7), Boolean (own AD).

## 12. Tests per phase

Production regression tests live in `tests/` and are written per phase from the prototype checks of §9.2 and the
acceptance tests of §9.3: kernel unit tests (positions, `M`, layers, regions and colours, UVs, `assert_mesh_invariants`,
`assert_layer_invariants`, `assert_uv_invariants`); app integration (one step, exact Undo / Redo, refusals change
nothing, pairs); morph lifecycle and skinning invariance; the symmetric Detach scenario; weld order independence and the
canonical survivor; Bridge attributes; the gate enumeration; save / load; a performance probe (script, not CI).

## 13. Risks

| Risk | Level | Guard |
|---|---|---|
| Data merged by name | eliminated | never merged |
| Region or target data lost | eliminated | carried and renamed |
| Look silently replaced | eliminated | refusal or explicit variant |
| Region colour changes after renaming | low, visible | documented (§3.3); renaming back restores it |
| Destination symmetry damaged | low | AMBIGUOUS refused |
| Rounding asymmetry after Attach | medium, visible | PARTIAL + status; precondition documented |
| Re-Symmetrize unavailable with islands | medium, visible | existing refusal texts; works again after bridging (P5 test) |
| Weld topology surprises | low | W2–W6 |
| Border averaging after Weld | medium, visible | W11 status; Bridge preferred for the ear |
| Viewport cost of a large Attach | medium, unmeasured on GL | P2 acceptance |
| Symmetric Weld with coincident points | open | decided before P6 |

## 14. Not in scope

Boolean union, remeshing, automatic weights, transfer between meshes, per-face materials, keys, Core changes.
