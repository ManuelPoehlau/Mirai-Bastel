# AD-031 — Attach, Detach, Weld, Bridge: assembling, separating and connecting mesh parts

**Status:** DECIDED (Manu, 2026-11-09): D1–D9 and D11 approved as proposed; D10 decided as a world-space threshold
with a **provisional** reference default (§4.1), the numeric value is not artist-approved. **P1 BUILT (2026-11-10):** the
assembly kernel `src/mirai/mesh_assembly.py` (`append_objects`, `extract_faces`, `look_differences`,
`derived_symmetry`), tests `tests/test_mesh_assembly.py`. **P2 readiness pass (2026-11-10):** O-1, O-2, O-5, O-7
decided and D4 made precise (Manu, 2026-11-10; §10); P1 → P2 boundary verified, P2 specification §15. **P2 BUILT
(2026-11-10, O-13 "ja"):** Attach — `Application.attach_objects` / `attach_plan`, `src/mirai/attach.py`, kernel K1 / K2,
the D11 prune, commands `Attach` / `AttachTakeLook` without keys, the "Mesh" menu and the outliner context menu with the
O-5 prompt; practical test §16, pending. **P3 BUILT (2026-11-10):** Detach and Select Linked —
`Application.detach_faces` / `detach_plan` / `select_linked` / `linked_seed`, `src/mirai/detach.py`, the kernel's
`linked_faces`, commands `Detach` / `SelectLinked` without keys, "Mesh" > Detach and SPACE > Select Linked;
specification as built §17, practical test §18 (Manu, 2026-11-10: **O-8 KEEP**, **O-14** "SPACE reicht vorerst (später
Sub-Object Mode)"; one finding fixed, §17.11). **P4 BUILT (2026-11-10):** Weld — `Application.weld_plan` /
`weld_vertices` / `weld_default_threshold`, the kernel `src/mirai/topology/weld.py` (W1–W11), command `Weld` without a
key, "Mesh" > "Weld…" with the threshold field and the preview; refused under a symmetry definition until P6;
specification as built §19, practical test §20 (W5 changed by Manu on 2026-11-10: single pairs allowed and reported,
§19.10; D10-v open). P5–P7 (§11) are **not implemented**, each starts
only with its own go.
Open points: §10.
**Scope:** `src/mirai` and `src/gui` only. **No Core change, no file-format change, no keymap change** (no keys at all).
**Builds on:** AD-001 (ids), [AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) (objects, L-1 / L-3),
[AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) (journal), [AD-024](AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md),
[AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) (point layers, H1–H5), [AD-026](AD-026-FACE-CORNER-UVS-AND-TEXTURE.md),
[AD-028](AD-028-SKELETON-AND-SKINNING.md), [AD-REGIONS-01](AD-REGIONS-01-FACE-REGIONS-STORAGE.md), AD-SYM-01…05,
[AD-030](AD-030-GUI-FRAMEWORK.md). Basis: `main` @ `f76287f`.
**Evidence:** code reading (§1) and a prototype verification run (§9), kept outside the repository and outside
`tests/` on purpose.

## Kurzfassung für Manu (Deutsch)

- **Attach** (Modus `4`, Menü „Mesh“ oder Rechtsklick im Outliner; gebaut 2026-11-10): die ausgewählten Objekte werden
  Inseln im Mesh des Edit-Objekts. Die Form bleibt in Weltkoordinaten, nichts wird verschweißt. Ein Undo-Schritt; beim
  Undo kommen die Quellobjekte unverändert zurück. Praxistest: §16.
- **Detach** (Modus `3`, Menü „Mesh“; gebaut 2026-11-10): die gewählten Flächen werden ein neues Objekt mit derselben
  Platzierung (bitgenau), demselben Look, allen Morph-Zielen, Gewichten, UVs und Gruppen. Mit Symmetrie wird – wie bei
  Delete – das Spiegelbild mitgenommen; das neue Objekt bekommt die Symmetrie, die `Shift+S` ableiten würde, nur wenn
  sie gültig ist. Ein Undo-Schritt. Danach bleibst du in Modus `3` am selben Objekt (O-8, von dir bestätigt: KEEP). Praxistest: §18.
- **Select Linked** (Modus `1`/`2`/`3`, SPACE-Menü am Teil; gebaut 2026-11-10): wählt den zusammenhängenden Teil unter
  dem Cursor dazu – z. B. ein ganzes Ohr vor dem Detach. Im Menü „Mesh“ steht es nur als Hinweis: über der Menüleiste
  gibt es keinen Cursor mehr am Mesh (§17.2; O-14: „SPACE reicht vorerst (später Sub-Object Mode)“).
- **Weld** (Modus `1`, Menü „Mesh > Weld…“; gebaut 2026-11-10): verschmilzt nur ausgewählte, unverbundene Punkte,
  exakt auf den Schwerpunkt der Gruppe, unabhängig von der Reihenfolge; lehnt ab, was unerwartete Topologie ergäbe
  (Kette, verbundene Punkte, gegenläufige Normalen, verdeckte Geometrie). Eine Naht geht auf einmal oder Punkt für
  Punkt (dein „Change W5“): ein einzelnes Paar zweier Teile wird verschweißt, die Teile hängen dann nur an diesem
  Punkt, bis die Nachbarn folgen – Fenster und Statuszeile sagen es. Das Fenster zeigt den Abstand
  als Zahl (Weltkoordinaten, änderbar) und die Vorschau „n Gruppen, m Punkte“; der Startwert (0,001 × Diagonale) ist
  vorläufig. Mit Symmetrie noch abgelehnt (bis P6). Ein Undo-Schritt. Praxistest: §20.
- **Bridge** (zwei Ränder gleicher Punktzahl): Quads dazwischen, keine neuen Punkte → Morphs und Gewichte unberührt;
  die neuen Flächen haben keine UVs und keine Gruppe.
- **Attach und Gewichte (O-5):** Geometrie ohne Skin-Gewichte in ein gebundenes Mesh wird abgelehnt; nur über die
  ausdrückliche Übersteuerung, die vorher die Anzahl der betroffenen Punkte zeigt. Es werden keine Gewichte erzeugt;
  diese Punkte folgen dem Rig nicht. Vorhandene Gewichte der Quelle bleiben unverändert.
- **Attach und Gruppen (O-7):** Flächen der Quelle ohne Gruppe kommen in eine neue Gruppe mit dem Namen des Quellobjekts.
- **Attach und Symmetrie (D4):** kein neuer und kein verschärfter AMBIGUOUS-Fall; PARTIAL ist erlaubt und wird gemeldet.
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
2. One shared kernel `src/mirai/mesh_assembly.py` (name `PROVISIONAL`): `append_objects(dst, sources)` and
   `extract_faces(mesh, faces)` over the public Mesh API. Weld = `Mesh.add_edge` + `core.operations.collapse_elements`
   (`src/mirai/topology/weld.py`); Bridge = `Mesh.add_face` over `topology.border` loops (`src/mirai/topology/bridge.py`).
3. Every operation is **one** `Application._mesh_transaction` (one recording, one `MeshDeltaCommand`) with its object
   commands as the existing `companion`; every check runs before the recording and only reads; a refusal changes
   nothing (fail-closed).
4. **Never merge by name.** Morph targets and regions of a source are carried as separate data; identity across meshes is
   asserted only by a later explicit artist command.
5. Symmetry is never edited implicitly: Attach keeps the destination's definition and refuses any new or worsened
   AMBIGUOUS correspondence (D4, §3.5); Detach mirrors like Delete and gives the new object the definition Shift+S would
   derive.

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

- **Destination** = the edit object (O-1). **Sources** = the selected objects other than it; a group stands for its
  leaves (`scene_objects.group_leaves`: the visible leaves; the group objects themselves are not sources and stay).
- **Positions:** `to_object(dst, to_world(src, p))`; verbatim when placement and pivot are equal (bit-exact).
- **Topology:** each source becomes islands with new ids; loose edges are carried; nothing is welded or moved.
- **Data:** §3 (look, layers, regions, UVs, symmetry, mirror pairs).
- **Sources** are removed after a successful append, in the same step (`DeleteObjectsCommand`, O-2); pairs containing a
  source are removed (`MirrorPairCommand`). Undo restores the same instances, ids, layers, regions and pairs and the
  destination's mesh; the whole Attach is one Undo step.
- **Refused before any change:** an interaction is running; no source; a source is a Reference; the morph editing view
  is open; an involved object has a morph dial above 0 %; the rig is posed and a bound mesh is involved; unweighted
  geometry into a bound destination without the explicit override (O-5, §3.2); the refusals of §3.
- **Afterwards:** mode `4`, the destination selected.
- **Variant "Attach – take destination look"** (D1): as Attach, the sources' look is replaced (§3.1).

### 2.2 Detach (component mode, faces)

- Input: the selected faces; in vertex / edge mode refused with "press 3" (Select Linked helps to pick an island).
  As built: §17.
- **With a symmetry definition:** the selection is expanded by its partner faces (`symmetry_coordination.expand_faces`,
  as symmetric Delete); an unpaired face refuses with the existing `TEXT_UNPAIRED`. The source deletion runs through
  `symmetric_ops.coordinate_delete`.
- **New object:** built by `extract_faces` without a journal (a fresh instance owned by `AddObjectCommand`): boundary
  vertices are copied, every point layer is copied with name and rule (identity map), UVs and the regions restricted to
  the extracted faces (§3.3); same transform, pivot, material, texture and state; symmetry §3.5.
- **Source:** `Mesh.delete_faces` (or the coordinator) leaves open borders; the Core deletes the layer values of removed
  points.
- One step: `MeshDeltaCommand(source)` + `AddObjectCommand(new)` as the companion. Refused while posed and on the
  morph editing view. Afterwards: per O-8 (§10, decided KEEP; §17.6).

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
| Unweighted geometry, bound destination (O-5) | **Refused by default.** Only the explicit override attaches it; the number of affected points is shown before the override is confirmed. No weights are generated or assigned; the accepted points stay unweighted and do not follow the rig (in a pose they keep their rest position under the object placement). Weights of incoming points are kept unchanged; no redistribution or normalisation beyond the Core's existing canonical form |
| A morph dial above 0 % on an involved object, or a posed rig with a bound mesh | Refused (D3) |

**O-5 terms (verified against P1 and the skinning code, 2026-11-10):**

- *Bound destination* = AD-028 §7.1 "bound" of the destination **before** the Attach: a rig exists and its mesh has a
  weights layer with at least one stored value (`SkeletonController.bound`). Not "has a weights layer", and not
  `AppendResult.unweighted > 0`.
- *Unweighted point* = an incoming point whose weights value is the empty default `()`: every point of a source without
  a weights layer, and every point of a weighted source without a stored value. **Missing and zero weights are the same
  stored value:** the Core drops zero weights when it canonicalises a value (`core.mesh._weights_value`), so an
  all-zero value is stored as `()`; there is no separate "zero weights" state to count. A *partial* value
  (0 < Σw < 1) is weighted: the remainder 1 − Σw is the object's implicit share (AD-028 W2) and stays as it is.
- The count is `AppendResult.unweighted` (appended points with `()` in the destination's weights layer afterwards; the
  destination's own points are never counted). For a bound destination it equals the read-only pre-count over the
  sources, so the refusal and the override prompt can show it before anything changes (§15.7).
- Keys are not re-validated: the scene has one rig and bone deletion rewrites weights (`skin_weights.delete_bone_weights`),
  so a stored key names a live bone.

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
- **Ungrouped source faces (O-7, Manu 2026-11-10):** a source's live faces that belong to no region of that source
  become one **new region named after the source object**, placed after that source's carried regions; a source without
  such faces gets none. The name follows the collision rule above, applied to the object name (free → kept; a taken
  `Group N` → renumbered; any other taken name → `"<source object> · <source object>"`, then `" 2"` …). Existing
  assignments of the source and of the destination are preserved; no region is overwritten or merged. Its tint follows
  its name like every region: when a collision renames it, it gets a different tint (the colour consequence above).
- Faces **created** by an operation (Bridge, Cap) join no region (F6, D9). Weld keeps face ids, so regions stay.
- Detach: the new mesh gets the regions restricted to its faces (names unchanged); the source keeps its regions.

### 3.4 UVs

Attach, Detach, Separate: copied per face (`infer_uvs=False`). Weld: kept per face (F10; a UV seam along the weld stays).
Bridge: none (§5, D8).

### 3.5 Symmetry and mirror pairs (D4, D5)

| | Policy |
|---|---|
| Attach | The destination's definition is never edited (plane, seam). **D4 (made precise, Manu 2026-11-10):** Attach must not introduce any new AMBIGUOUS vertex correspondence — not for an existing point, not for an attached point, and not between attached points (of one source or of several) — and must not worsen an existing one (an already AMBIGUOUS point must not gain a further candidate). Existing AMBIGUOUS correspondences that Attach neither introduces nor worsens may remain; an unrelated pre-existing AMBIGUOUS point is no reason to refuse. PARTIAL is allowed and reported in the status line. Source definitions are dropped. Exact when the destination placement maps its plane exactly onto the pair's world plane (the `applied_symmetry_axis` condition): measured identity and Y-translation VALID, rotated + scaled PARTIAL. P1 implements all of this except the "worsen" case (§15.1); P2 closes it. |
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
| W5 | ~~No new non-manifold (bowtie) vertex: refused~~ — **changed (Manu, 2026-11-10, practical test P4: "Change W5", "Brauchen also beide Möglichkeiten")**: a merged point whose faces form more than one fan (two parts touching at that point only) is **allowed and reported** (preview and status line), so a seam can be welded point by point; the later Target Weld (§11) needs the same. §19.10 |
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
pose are required · one `WEIGHTS` layer per mesh, no automatic weights, unweighted geometry into a bound mesh only by
explicit override · Attach never edits the symmetry definition and refuses a new or worsened AMBIGUOUS correspondence ·
Detach works on faces and mirrors under a definition · Weld and Bridge are refused under a symmetry
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
| P2 (tested 2026-11-10 except the reference-PC timing, §15.14) | Viewport and SubD rebuild after a large Attach (GL, reference hardware); the mixed mesh + object Undo step in the real command path; the D11 prune in the morph controller; skinning invariance under a posed rig (randomized); the look refusal and the explicit variant; the O-5 refusal and override; O-7; the D4 "worsen" case — full list §15.12 |
| P3 (tested 2026-11-10, §17.9) | A detached part **crossing** the plane derives a usable seam (state VALID, symmetric ops, Re-Symmetrize if the seam splits it in two); Select Linked |
| P4 (tested 2026-11-10, §19.8) | W2–W4 / W6 refusals (chain, connected members, coinciding faces, orientation), W5 allowed and reported (changed, §19.10), W10, the threshold field and its default from the bounding-box diagonal |
| P5 | Bridge pairing, winding, refusal on conflicting normals; **Re-Symmetrize works again after the islands are bridged** into the head (component count back to 2) |
| P6 | Symmetric Weld / Bridge, including coincident pre-weld points (AMBIGUOUS correspondence) |
| P7 | Separate by Islands, the kept island (O-12) |

## 10. Decisions

**Decided (Manu, 2026-11-09):** D1 look refusal + explicit variant · D2 targets as `"<object> · <target>"`, never merged
· D2b region naming of §3.3 · D3 refuse with a dial above 0 % or a posed rig · D4 Attach: PARTIAL allowed, AMBIGUOUS
refused · D5 Detach mirrors like Delete, derived definition when VALID; Re-Symmetrize limitation accepted · D6 Weld
strictness (W5 changed by Manu on 2026-11-10, §19.10) · D7 H3 group mean · D8 Bridge without UVs · D9 Bridge without region · D10 world-space threshold, provisional
reference 0.001 × world bounding-box diagonal, always visible and editable · D11 Undo removes the dial state of carried
targets, Redo recreates them at 0 %.

**Decided (Manu, 2026-11-10, P2 readiness pass):**

- **D4 made precise:** no new and no worsened AMBIGUOUS correspondence (including between attached points); existing
  ones may remain when Attach neither introduces nor worsens them; PARTIAL allowed and reported (§3.5). P1's stricter
  rule (refusing ambiguity between new points) is approved.
- **O-1:** the destination is the active edit object. **O-2:** the selected source objects are appended to its mesh and
  removed after a successful Attach; Undo restores the sources and the destination; the whole Attach is one Undo step.
  No further object-selection or transform behaviour (§2.1, §15).
- **O-5:** unweighted geometry into a bound destination is refused by default; an explicit override attaches it after
  showing the number of affected points; no automatic weights; accepted points stay unweighted and do not follow the
  rig; incoming weights are kept; no redistribution or normalisation beyond the Core's canonical form (§3.2).
- **O-7:** source region assignments are preserved; ungrouped source faces get a new region named after the source
  object, under the collision-safe naming rule; nothing is overwritten or merged; a renamed region has another tint
  (§3.3).
- **O-13** ("O-13 ja", Manu 2026-11-10): the GUI places are a "Mesh" menu in the menu bar and the outliner context
  menu.

**Decided (Manu, 2026-11-10, before P4):** the Weld GUI place — "Weld-Fenster passt so": "Mesh > Weld…" opens a small
window with the threshold as a number field (D10: always visible and editable, the provisional default prefilled), a
preview of what it would merge ("n Gruppen, m Punkte") and "Weld" / "Abbrechen"; no key, no keymap change. D10-v (the
approved default value) stays open until the P4 practical test.

**Decided (Manu, 2026-11-10, practical test P4):** **W5 changed** — "Change W5, brauchen wir auch, wenn Target Weld
hinzukommt … Brauchen also Beide Möglichkeiten": a weld that joins two parts at one point only (a bowtie) is allowed and
reported; a seam can be welded at once or point by point (§4.2, §19.10).

**Open (classified for P2 on 2026-11-10; none blocks P2):**

| # | Question | Proposal | P2 |
|---|---|---|---|
| D10-v | The artist-approved default Weld threshold | after the P4 practical test (§20) | not relevant (P4); P4 built with the provisional 0.001 × diagonal |
| O-8 | After Detach: stay in component mode on the source, or mode `4` with the new object selected | stay in component mode | **Decided (Manu, 2026-11-10, practical test P3): "O-8 KEEP"** — mode `3`, the source stays the edit object, no component selection, the new object neither selected nor edited (§17.6) |
| O-14 | Select Linked "under the cursor" from a menu: the pointer over the menu bar has no hover (§17.2) | the SPACE menu remembers the element under the cursor when it opens; the "Mesh" menu shows a disabled hint; a key only by Manu's keymap decision | **Decided (Manu, 2026-11-10): "SPACE reicht vorerst (später Sub-Object Mode)"** — no key now; a later Sub-Object Mode is the place to revisit it |
| O-11 | Bridge MVP only for loops of equal vertex count | yes | not relevant (P5) |
| O-12 | Separate by Islands: which island keeps the object | the one with the most faces | not relevant (P7) |
| P6 | How symmetric Weld handles coincident points (AMBIGUOUS) | decided before P6 | not relevant (P6) |
| O-5b | An **unbound** destination receives weights from a weighted source: §3.2 (decided) creates the `"Skin"` layer, so the destination's own points (and points of other unweighted sources) end up unweighted in a mesh that is now bound. O-5 covers only a destination bound before the Attach | none — new, found in this pass | not blocking: P2 implements the decided rules literally (no O-5 refusal, since the destination was not bound; the status line states the count); Manu may decide otherwise after the practical test |

Literal readings P2 applies without a new decision (`PROVISIONAL`, checked in the P2 practical test): a group whose
visible leaves are all attached stays as an (empty) group object, because only the leaves are sources (§2.1); an O-7
region whose object name is taken gets `"<object> · <object>"` by the §3.3 rule.

## 11. Phases

P1 kernel (`append_objects`, `extract_faces`, the look / layer / region / symmetry plans; built 2026-11-10) → P2 Attach (+ variant, D11
prune; built 2026-11-10) → P3 Detach (+ Select Linked; built 2026-11-10) → P4 Weld (built 2026-11-10, §19) → P5 Bridge → P6 symmetric Weld / Bridge → P7 Separate by Islands. Each
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
| Destination symmetry damaged | low | new or worsened AMBIGUOUS refused (the "worsen" check is P2, §15.1) |
| Unweighted points stay at rest in a pose | medium, visible | refused by default; explicit override with the count (O-5) |
| Rounding asymmetry after Attach | medium, visible | PARTIAL + status; precondition documented |
| Re-Symmetrize unavailable with islands | medium, visible | existing refusal texts; works again after bridging (P5 test) |
| Weld topology surprises | low | W2–W4, W6; a bowtie point (W5, allowed since 2026-11-10) is reported |
| Border averaging after Weld | medium, visible | W11 status; Bridge preferred for the ear |
| Viewport cost of a large Attach | medium, unmeasured on GL | P2 acceptance |
| Symmetric Weld with coincident points | open | decided before P6 |

## 14. Not in scope

Boolean union, remeshing, automatic weights, transfer between meshes, per-face materials, keys, Core changes.

## 15. P2 — Attach: implementation specification (readiness pass 2026-11-10)

Basis: branch `claude/wizardly-turing-ldtt42` @ `e4b770d` (contains P1 `d5a7e5f`); `tests/test_mesh_assembly.py` 31 passed.

### 15.1 P1 → P2 boundary (verified)

- `append_objects(dst, sources)` is the production data operation. It writes only `dst.mesh`; sources are only read; it
  touches no scene, object, selection, history, viewport or morph view state. Source lifecycle, look (D1), D3, O-5,
  O-7, D11, mode and selection belong to the P2 command; the kernel decides none of them.
- `AppendResult` carries what P2 needs: per-source vertex / face / layer maps (O-7 uses `face_maps`; D11 uses the
  `layer_maps` values other than the weights layer = the carried targets), `region_names`, `unweighted` (O-5),
  `symmetry_before` / `_after` (D4 status). Nothing else is needed.
- **Atomicity:** all static refusals (no source, self, duplicate, shared mesh, more than one weights layer,
  `MAX_TARGETS`, unsupported layer kind) run before the first write; the writes run in a nested recording that is
  rolled back exactly on any failure, also inside a caller's recording (the outer delta stays exact or empty — tests
  `test_inside_a_caller_recording_…`, `test_a_failure_during_the_writes_…`). This composes with
  `Application._mesh_transaction`. The D4 check needs the result, so it is the one check inside the recording; a
  refusal there is rolled back exactly, only the id counters stay forward (AD-001; observed +3 vertex ids).
- **Data per AD-031:** positions and morph values mapped by the placements; targets as new `"<object> · <target>"`
  layers, never merged; weights merged unchanged into the one weights layer; corner UVs copied, never inferred;
  regions carried with collision-safe names; the destination's symmetry definition never edited, source definitions
  dropped; deterministic order.
- **D4:** the check compares the set of AMBIGUOUS vertices before and after. Verified (scratch probe, outside the
  repository): new points ambiguous among themselves (one source, and two sources together) → refused; an unrelated
  pre-existing AMBIGUOUS point → accepted (test). **Gap:** an attached point placed at the mirror position of an
  already AMBIGUOUS point adds a candidate (2 → 3) while the attached point itself is PAIRED; P1 **accepts** it. Under
  D4 this worsens an existing ambiguity → P2 closes it (K1).
- **Not in P1, by design:** O-7 (ungrouped faces), the O-5 decision (P1 only counts), D11, every scene-level step.

### 15.2 Scope

In P2: `src/mirai` (kernel K1/K2, `ObjectController` command, `Application.attach_objects` / `attach_plan`, morph
controller D11 prune, `layer_declarations` entry), tests in `tests/`, this AD, the AD-021 addendum of §7, a
`docs/ATELIER.md` line. The GUI entry (Attach, the D1 variant, the O-5 override prompt) only once O-13 is answered.
Not in P2: Detach, Weld, Bridge, Separate by Islands, Select Linked, keys or `config/keymap.json`, Core or file-format
changes, any change to unrelated application, morph or history code.

**Kernel changes (P2, `mesh_assembly.py`):**

- **K1 (D4 "worsen"):** additionally refuse when a vertex that was AMBIGUOUS before has more candidates afterwards
  (equivalently: an attached point lies exactly at the mirror position of a pre-existing AMBIGUOUS point). Same
  rollback path and refusal text family.
- **K2 (O-7):** an explicit option (e.g. `ungrouped_region: bool`, default off so the kernel stays policy-free) that
  plans, before the first write and with the same naming function, one region per source named after the source
  object for its live faces in no source region (§3.3).

### 15.3 Command and its responsibilities

`Application.attach_objects(*, take_destination_look=False, accept_unweighted=False) -> bool` (the method name of §7),
delegating to `ObjectController` like `delete_selected` / `placement_command`; `Application.attach_plan()` is the
read-only plan the GUI prompt reads (sources, refusal text or None, look differences, unweighted count). Reached from the
API (`dispatch_command` / the method); command constants without default keys only together with the GUI entry (§0.1,
O-13). Order of the read-only checks, each a status line, `False`, nothing changed:

1. an interaction runs (`refused_during_interaction`); not mode `4` → "press 4 and select them" (as `placement_command`);
2. the morph editing view is open;
3. destination = `scene.edit_object` (O-1); sources = `group_leaves(scene, selection.objects)` without the destination;
   none → refused; a source is a Reference → refused, naming it (unlike `ObjectController.targets`, which skips them);
4. D3: a dial above 0 % on the destination or a source (`MorphSurfaceProvider.object_weights`); the rig is posed
   (`SkeletonController.posed`) and the destination or a source is bound (`SkeletonController.bound`) — checked here,
   because the `can_run` posed stage skips mode `4` and reads only the edit mesh;
5. the point-layer gate: `layer_refused("attach_objects", [dst.mesh, *source meshes])` (DECLARED, §7);
6. D1: `look_differences` non-empty without `take_destination_look`;
7. O-5: destination bound and the pre-count > 0 without `accept_unweighted` (§15.7);
8. the kernel's static refusals (`AssemblyRefused` before any write).

Then **one** `_mesh_transaction("Attach …", mutate, companion=…, on_applied=…)` with `mutate = append_objects(dst,
sources, ungrouped_region=True)` on `scene.mesh is dst.mesh`. The companion, built before and not applied:
`CompositeCommand([MirrorPairCommand(pair, create=False) for each pair with a source] + [DeleteObjectsCommand(scene,
sources, dst.id, dst.id)])` — the `delete_selected` order (`Scene.remove_object` refuses a paired object). The
transaction applies the companion **after** `end_change`, so everything its `redo` needs is checked before (sources
present, not groups, not the edit object). `on_applied`: mode `4`, `selection.objects = {dst.id}` (§2.1), D11
registration. Afterwards `ObjectController.sync_views()` and the status line. The edit object never changes, so
`_follow_edit_object` is not involved.

### 15.4 Undo / Redo

One history entry: `CompositeCommand([MeshDeltaCommand(dst.mesh), companion])` plus one selection-mirror entry
(`mesh_step=True`). Undo: pairs and the same source instances return (ids, meshes, layers, regions, look, symmetry
definitions, placement), then the destination's mesh is restored exactly; the selection of before returns. Redo: the
exact post-Attach state (same ids, `LayerId`s, values, regions). The existing `_apply_undo_redo` path (topology
rebuild, `sync_views`, `MorphController.after_history`) is reused unchanged except for the D11 prune.

### 15.5 Morph targets and dial state (D2, D3, D11)

Carried targets are new `LayerId`s, listed at once (`morph_target_rows`), at 0 % (D3 guarantees every involved dial
was 0 %); the destination's current target is kept. **D11:** the Attach hands `(dst.id, carried LayerIds)` to the morph
controller; its after-history step drops the dial weights of exactly those layers when an Undo has removed them, so a
Redo shows them at 0 %. Scope: carried targets only — a generic prune of every dead layer would change F13 for other
operations and is not decided. An editing view opened on a carried target closes on Undo through the existing
`target_alive` path; the current-target fallback is unchanged.

### 15.6 Look (D1)

All looks equal → Attach. Different → refused, naming the object and what differs (material, texture). The variant
(`take_destination_look=True`) changes no object: the sources are removed in the same step and Undo restores them with
their own look, so no material or texture command is needed; the attached faces show the destination's look with their
own UVs; the status line lists the replaced looks.

### 15.7 Skin weights (O-5)

Pre-count, read-only before the recording: per source, all points if it has no weights layer, else its points with the
value `()`. Destination bound (§3.2 terms) and pre-count > 0: refused without the override; the refusal text and
`attach_plan()` give the count, so the prompt shows it before the artist confirms. With `accept_unweighted=True`: the
append runs unchanged — no weights generated, incoming weights unchanged; P2 asserts `AppendResult.unweighted` equals
the pre-count, and the status line repeats it. Destination not bound (O-5b): no refusal; when the result has a weights
layer, the status line states `AppendResult.unweighted`.

### 15.8 Regions (O-7)

Source regions carried as §3.3; ungrouped source faces via K2. The destination's own regions and assignments are
unchanged. The region-inheritance hook in `_mesh_transaction` adds nothing (appended faces have no removed parent, F6).

### 15.9 Symmetry (D4)

Refusal (K1 included) → status, nothing changed. `symmetry_after` PARTIAL → the status line says so (e.g. "symmetry
partial — unpaired points"); a pre-existing AMBIGUOUS or VIOLATED state is reported as it is, not refused. Source
definitions and the Re-Symmetrize limitation follow §3.5.

### 15.10 Rest pose and dials (D3)

Refused with a dial above 0 % on any involved object, and while the rig is posed with any involved mesh bound (§15.3
step 4). No automatic dial reset or rest-pose switch.

### 15.11 Failure behaviour

Every refusal before the recording reads only. An `AssemblyRefused` or any exception inside `mutate` is rolled back
exactly by the kernel and by `_mesh_transaction`; no history entry, no object or pair changed, selection and mode
unchanged; `AssemblyRefused` becomes a status line, any other exception propagates.

### 15.12 Permanent production tests (`tests/`)

- `test_mesh_assembly.py`: K1 (the "worsen" case refused and rolled back exactly; an unrelated existing AMBIGUOUS point
  still accepted); K2 (no source regions, partly grouped, name collision incl. `Group N`, several sources, a source
  without faces, existing assignments unchanged).
- New `test_attach.py` (headless, real `Application`): one history step; exact Undo / Redo of the mesh, the sources
  (same instances), pairs, edit object, selection and mode; every refusal of §15.3 leaves mesh, scene, pairs, history
  and selection unchanged; D1 refusal and variant; O-5 refusal with the count in the text, the override, incoming
  weights unchanged, pre-count = `AppendResult.unweighted`, O-5b; O-7 end to end; D4 refusal and PARTIAL status; D11
  (dial on a carried target, Undo, Redo → 0 %; another operation's F13 behaviour unchanged); morph rows and the
  editing view on a carried target; skinning invariance: attach at rest, then a randomized pose, world positions equal
  the sources' own skinning; group leaves as sources; save / load round trip after Attach.
- `test_layer_gate.py`: `attach_objects` classified DECLARED with its rule fixture (the enumeration test enforces it).
- GL (`xvfb-run`, own process): viewport and SubD rebuild after a large Attach and its Undo. Timing on the reference PC
  is a measurement, not a CI test.

### 15.13 Acceptance criteria

1. Attach of one or more visible, non-Reference objects into the edit object is one Undo step; Undo / Redo exact.
2. The world shape, targets (D2), weights, UVs and regions (D2b, O-7) of every source survive in the destination;
   nothing is merged by name; the destination's own data is unchanged.
3. Each refusal (§15.3, D4 incl. "worsen", the kernel's) changes nothing and names its reason; PARTIAL is reported.
4. O-5: refused by default with the count; the override attaches without generating weights.
5. D11: carried targets at 0 % after Attach and after Redo.
6. The tests of §15.12 pass; `tests/` runs green apart from known, unrelated failures; GL tests green under xvfb.
7. AD-031 status, the AD-021 addendum and `docs/ATELIER.md` updated in the same change; a practical test for Manu once
   the GUI entry (O-13) exists.

### 15.14 As built (2026-11-10)

- **Kernel:** K1 (`_ambiguity`: candidate counts; a new or a grown count refuses), K2 (`append_objects(…,
  ungrouped_region=True)`, `AppendResult.ungrouped_regions`), and two read-only plans: `incoming_unweighted` (the O-5
  pre-count) and `check_append` (the static refusals, so the plan can name them before any prompt).
- **Command:** the controller-reading checks and the transaction sit in `Application.attach_plan` / `attach_objects`
  (they read the morph controller, the skeleton controller and the object selection, which no single controller owns);
  `src/mirai/attach.py` holds the plan type, the texts and the object step. Commands `Attach` / `AttachTakeLook`
  (`commands.ATTACH_COMMANDS`, no default key) run `attach_objects`; layer gate: DECLARED for both commands and the
  method, `attach_plan` "non-mesh", `PER_TARGET_COMMANDS`; held gestures refuse them (`GESTURE_REFUSES`).
- **D11:** `MorphController.note_attached` / `_prune_attached` in `after_history` (scoped to carried targets; cleared
  on a scene load).
- **GUI:** menu bar "Mesh" > "Attach" / "Attach – Look des Ziels übernehmen"; the same two entries in the outliner
  context menu (enabled on a selected row that is not the edit object; they act on the selection); the O-5 dialog
  "Attach – ohne Gewichte" with the count, "Trotzdem anhängen" / "Abbrechen" (`gui.menus.attach_request`).
- **Edge:** a source without mesh data changes no destination data; `_mesh_transaction` then pushes the object step
  alone, and the command still sets the selection to the destination.
- **Tests:** `tests/test_mesh_assembly.py` (+8: K1, K2, the pre-count), `tests/test_attach.py` (23, the app path of
  §15.12), `tests/test_layer_topology_ops.py` and `tests/test_weights_topology_ops.py` (the Attach rule fixtures with morph
  targets and with weights, plain and symmetric, all three entries),
  `tests/test_gl_attach.py` (GL frames before / after / Undo / Redo with SubD level 2), `tests/test_gui_menus.py`
  (`attach_request`, the O-5 dialog in the window).
- **Measured** (container, Python 3.13, headless trace store — not the reference PC): Attach of the head basemesh
  (324 faces) 12 ms, Undo 10 ms, Redo 4 ms; of the man basemesh (926 faces) 25 / 28 / 10 ms. The GL rebuild and SubD
  cost of a large Attach on the reference PC is still unmeasured (§13).

## 16. Praxistest P2: Attach (Deutsch, ca. 15 Minuten)

Start: `python src/main.py`. Attach hat **keine Taste**; es steht im Menü **Mesh** und im Rechtsklick-Menü einer
ausgewählten Outliner-Zeile. Es wirkt auf die in Modus `4` ausgewählten Objekte und hängt sie an das Edit-Objekt.

1. Leertaste > Add + > einen Würfel und eine Kugel hinzufügen, mit `W` neben den Kopf / Würfel schieben. Modus `4`, beide
   auswählen, **Mesh > Attach**. Erwartet: beide sind Teil des Edit-Objekts, an derselben Stelle; im Outliner weg.
2. `Strg+Z`: beide Objekte kommen zurück, wie vorher. `Strg+Y`: wieder angehängt.
3. Einem Objekt eine andere Farbe geben (Material) und Attach: abgelehnt mit Hinweis. Dann **Mesh > Attach – Look des
   Ziels übernehmen**: angehängt, mit dem Look des Ziels.
4. Gruppen: die angehängten Teile haben je eine Gruppe mit ihrem Objektnamen (Gruppenfarben einschalten). Hatte ein Teil schon
   Gruppen, bleiben sie; bei gleichem Namen wird umbenannt (dann andere Farbe).
5. Morph: ein Teil zum Edit-Objekt machen (in `4` anklicken, dann `1`), `Strg+N` gibt ihm ein Ziel; dann das
   eigentliche Ziel-Objekt wieder zum Edit-Objekt machen, das Teil auswählen, anhängen. Im Morph-Panel steht es als
   „<Objekt> · <Ziel>“ auf 0 %. Hochdrehen, `Strg+Z`, `Strg+Y`: das Ziel ist wieder da, auf 0 %.
6. Symmetrie (`Shift+S` am Ziel an): ein Teil nur auf einer Seite anhängen → angehängt, Statuszeile „symmetry partial“.
   Ein Teil genau auf vorhandene Punkte legen → abgelehnt („ambiguous“), nichts geändert.
7. Rig (falls zur Hand, z. B. der Kopf aus dem AD-028-Praxistest mit Gewichten): einen ungewichteten Würfel anhängen →
   Dialog „Attach – ohne Gewichte“ mit der Anzahl. „Abbrechen“: nichts passiert. „Trotzdem anhängen“: angehängt; in der
   Pose (`6`) bleibt der Würfel stehen (er folgt dem Rig nicht).

| # | Verdikt (KEEP / CHANGE / DROP) | Notiz |
|---|---|---|
| 1–2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |

Offen für dich (keine Blockade): **O-5b** (§10) — ein gewichtetes Teil an ein *ungebundenes* Ziel: heute ohne Rückfrage,
die eigenen Punkte des Ziels sind danach ungewichtet. Und: eine Gruppe, deren Teile alle angehängt wurden, bleibt als
leere Gruppe im Outliner (§10, wörtliche Lesart).

## 17. P3 — Detach and Select Linked: specification as built (2026-11-10)

Basis: `main` @ `eb04a3f` (P2). Scope as §11: Detach and Select Linked in `src/mirai` and `src/gui`; no Core,
file-format or keymap change, no key.

### 17.1 Commands and places

- `commands.DETACH = "Detach"` and `commands.SELECT_LINKED = "SelectLinked"`, **no default key** (§0.1); handlers in the
  command table run `Application.detach_faces()` / `select_linked()`; a held gesture refuses both (`GESTURE_REFUSES`).
- GUI (`gui/menus.py`): menu bar **Mesh** = Attach · Attach – Look des Ziels übernehmen · — · **Detach** · **Select
  Linked** (disabled, hint „SPACE-Menü am Teil“, §17.2); the **SPACE** menu has **Select Linked**.
- Menu enablement: Detach stays enabled like Attach. `detach_plan()` is the one source of its preconditions and the
  status line names the refusal; a disabled entry would hide the reason, and a second check in the GUI could drift.

### 17.2 Select Linked under the cursor — verified limitation of the menu bar

The documented behaviour (`docs/future_ideas/SELECTION.md`: "the connected component under the cursor") needs the
hovered element. Verified in the code and in the window test: the pointer entering the menu bar (any panel) calls
`Application.pointer_leave()` (`gui/imgui_layer.py` `on_mouse_motion`), which clears the cursor and
`selection.hovered`; on its way to the bar the cursor crosses other geometry, so "the last hover before the menu" is
whatever lies at the viewport's top edge, not the part the artist pointed at. **A "Mesh" menu entry cannot act under
the cursor reliably.** It is not replaced by another selection model (e.g. "linked to the selection"). Instead:

- the command works on the hovered element **now** — from `dispatch_command` and from a key, once Manu binds one;
- the **SPACE** menu opens at the cursor and is modal (it keeps every key and the mouse): when it opens it remembers
  the element under the cursor (`Application.linked_seed()` → `detach.LinkedSeed(edit object, mode, element)`), and
  its entry selects that element's part; a seed whose edit object or mode changed since is refused;
- the "Mesh" menu shows the entry disabled with the hint. **O-14** decided (Manu, 2026-11-10): "SPACE reicht vorerst
  (später Sub-Object Mode)".

### 17.3 Detach: read-only checks (`Application.detach_plan`, in this order)

Each refusal is a status line, `False`, and nothing changes (mesh, scene, history, selection, mode):

1. an interaction runs; 2. not face mode → "press 3, select the faces (Select Linked picks a whole part)" (vertex,
edge and object mode); 3. the morph editing view is open ("on the base only"); 4. no valid selected face; 5. D3: a dial
above 0 % on the edit object (`MorphSurfaceProvider.object_weights`), or the rig posed with the mesh bound
(`SkeletonController.posed` / `bound`, the Attach checks; no automatic dial reset or rest pose); 6. the point-layer
gate `layer_refusal("detach_faces", [mesh])`; 7. hidden geometry at the selection (`_hidden_refusal`, Delete's
check; `Detach` is in `_TOPOLOGY_COMMANDS`, so the key path runs it at `can_run` stage 5 too); 8. with a definition:
an inexact plane → `TEXT_NON_EXACT_PLANE`; `expand_faces(SymmetryIndex(mesh), faces)` with an unpaired face →
`TEXT_UNPAIRED` (never half a symmetric selection); otherwise the union replaces the selection; 9. the union is every
face of the mesh → refused ("nothing would stay"; `PROVISIONAL`: an object without faces has no use, Duplicate does
that job).

### 17.4 The step (one Undo step)

`extract_faces(mesh, faces)` first (read-only, before the deletion); the derived definition (§17.5); the new object
from `detach.detached_object` (`Scene.add_object`, the placement and look copied, then removed again: the id is handed
out now — AD-001, never reused, also when the step is refused afterwards — and the not yet applied `AddObjectCommand`
is the companion). Then **one** `_mesh_transaction("Detach n face(s) of 'A' as 'A.001'", mutate, companion=…)` whose
`mutate` is Delete's own path: `apply_removal(mesh, FACE, faces)` without a definition, `symmetry_declarations.
REMOVAL_COORDINATORS[DELETE]` (= `coordinate_delete`, with its seam update and delta check) with one. History: one
`CompositeCommand([MeshDeltaCommand(source), AddObjectCommand(new)])` plus one selection-mirror entry
(`mesh_step=True`). Undo: the object leaves the scene, the source mesh is restored exactly, the selected faces and
the mode return; Redo: the **same instance and id**, both meshes exactly as after the Detach. A refusal inside the
recording (the coordinator's delta check, a `RemovalRefused`) is rolled back exactly: no object, no history entry,
selection unchanged; only the id stays consumed. Views: `ObjectController.sync_views()` after the step; Undo / Redo
through `_apply_undo_redo` (object views synced for a mesh step). GL: the frame after Ctrl+Z equals the frame before
the Detach pixel for pixel, Ctrl+Y the frame after, with SubD level 2 (`tests/test_gl_detach.py`). **Measured**
(container, Python 3.13, headless trace store, key-path Undo / Redo — not the reference PC): half of the head basemesh
(162 of 324 faces) 12 ms, Undo 1 ms, Redo 5 ms; half of the man basemesh (463 of 926) 23 / 7 / 12 ms.

### 17.5 The new object

- **Name** `unique_object_name(scene, source)` (Duplicate's rule: `cube` → `cube.001`); **transform, pivot,
  material, texture, state, hidden flag and group** copied — the world position is unchanged (same object space,
  bit-identical positions).
- **Mesh** = `extract_faces`: every point layer with the same info and the values of the copied points (morph targets
  and skin weights unchanged), corner UVs copied with `infer_uvs=False`, the regions restricted to the extracted faces
  with their names; loose edges are not carried (Detach works on faces).
- **Symmetry:** without a source definition none. With one: `derived_symmetry(new_mesh, current_axis(source))` —
  Shift+S's rule, set **only when VALID**. Status: "symmetry X on 'A.001'", or "…, no seam (Re-Symmetrize not
  available there)" for a derived empty seam, or "symmetry off on 'A.001' (not symmetric about X)"; never an invalid
  definition. No mirror pair (§3.5).
- Morph dials of the new targets start at 0 % (new `(ObjectId, LayerId)` keys); with a rig the new object is bound at
  rest like its source.

### 17.6 After Detach — O-8, decided KEEP (Manu, 2026-11-10)

Mode `3` stays; the source stays the edit object (no automatic switch); the component selection is cleared (the
extracted ids no longer exist; no stale ids remain); the object selection is unchanged — the new object is neither
selected nor the edit object; the status line ends with "still editing 'A' (4: select 'A.001')". Built as the proposal
of §10 and confirmed in the practical test: **"O-8 KEEP"** (Manu, 2026-11-10).

### 17.7 Select Linked

- **Island** = `mesh_assembly.linked_faces(mesh, seeds)`: faces joined across shared edges; a face touching the part
  only at a vertex is another island. Same definition as the face components of `symmetry_topology.topological_sides`
  (Re-Symmetrize's "parts", without the seam) and the one Separate by Islands (P7) will use.
- **Seed** = the hovered element (or the SPACE menu's `LinkedSeed`): a face itself, an edge its faces, a vertex the
  faces around it.
- **Result** by the active mode: faces (`3`), edges (`2`) or points (`1`) of the island, **added** to the selection
  (like Shift+L), hidden elements left out, no Undo step; **not mirrored** under symmetry (no selection command is —
  Detach's expansion takes the mirror side).
- **Refusals** (status, nothing changed): an interaction runs; mode `4`; nothing under the cursor; a loose point or
  edge (no face); a stale seed.

### 17.8 Gate and classification

`layer_declarations`: `Detach` and `detach_faces` **DECLARED** with `extract_faces` (identity of infos and values; the
Core deletes the source values of removed points), rule fixtures plain and symmetric with morph targets
(`test_layer_topology_ops.test_detach_carries_the_layers_by_identity`) and with weights
(`test_weights_topology_ops.test_detach_keeps_the_weights_unchanged`); the editing view refuses `Detach` (base only);
the posed policy counts it as editing. `SelectLinked` and the methods `detach_plan`, `linked_seed`, `select_linked`
are non-mesh. `symmetry_declarations`: no new entry — the source deletion **is** Delete's coordinator; the fail-closed
guard (`tests/test_symmetry_fail_closed_guard.py`) presses `Detach` on its symmetric fixtures like every command.

### 17.9 Tests (production, `tests/`)

- `tests/test_detach.py` (26): one step, exact Undo / Redo (same instance and id, mode, selection), several faces,
  `detach_faces` = the command, world placement and look, targets / weights / UVs (never inferred) / regions
  (restricted, the source keeps its own), the symmetric expansion through Delete's coordinator, the crossing-plane part
  (VALID, seam, two components, a symmetric Delete on it, Re-Symmetrize through `Alt+M` - preview, execution, one
  Undo step - mirroring a moved point back), the
  part without seam (empty seam, Re-Symmetrize refused "keine Seam"), no definition unless VALID, `TEXT_UNPAIRED`,
  no mirror pair, seven refusals changing nothing (vertex / object mode, nothing, every face, dial, editing view,
  hidden), the posed rig, a refusal inside the step rolled back, save / load; Select Linked: the island under the
  real cursor (other islands untouched), then Detach of it, vertex / edge mode, no hover / mode `4`, the remembered and
  the stale seed, symmetry (not mirrored; Detach takes the mirror island).
- `tests/test_mesh_assembly.py` (+1): `linked_faces` (shared edges only, corner contact = two islands, read-only,
  invalid seeds ignored).
- `tests/test_layer_topology_ops.py` / `tests/test_weights_topology_ops.py` (+4 each): the gate's rule fixtures (both
  entries, plain and symmetric).
- `tests/test_gl_detach.py`: GL frames before / after / Ctrl+Z / Ctrl+Y with SubD level 2 on the symmetric subd_cube.
- `tests/test_gui_menus.py` (+3): `Menus.detach` / `select_linked` / the seed taken by `open_space`; in the window,
  SPACE over a face remembers it and Select Linked works after the hover is gone; the "Mesh" menu draws Detach
  (enabled) and Select Linked (disabled, with the hint).
- The P1 extract tests (`test_extract_*`, `test_derived_symmetry_*`) are reused, not duplicated.

### 17.10 Limitations (stated)

- Re-Symmetrize is unavailable on a detached part without seam edges (§3.5, expected; tested).
- Select Linked acts under the cursor only through the SPACE menu or the API (§17.2; O-14: "SPACE reicht vorerst
  (später Sub-Object Mode)").
- Detach of every face is refused (§17.3 item 9, `PROVISIONAL`).
- A refusal inside the step leaves the new object's id consumed (AD-001, like Attach's D4 refusal).
- Hidden faces of an island are not selected by Select Linked, so they are not detached; a selection touching hidden
  geometry refuses Detach as it refuses Delete.
- Observed, pre-existing, not changed: Undo through `dispatch_command(UNDO)` (API) runs the step without the edit
  view's rebuild that the key path (Ctrl+Z) adds (E23, `_undo_redo`) — the same for Delete; the artist's keys are
  exact (§17.4).

### 17.11 Practical-test finding (Manu, 2026-11-10): loading a scene after Detach in a group

Log: "Scene file 'Gollum_Head_01_Asym.mirai.json' failed: Objekt 21 hat Mitglieder - erst diese entfernen oder
umhängen". Cause: `scene_objects.replace_scene` / `reset_scene` removed the old objects in id order, and
`Scene.remove_object` refuses a group that still has members. Detach keeps the source's group (§17.5), as Duplicate
does, so the group gets a member with a higher id than itself and came first. The same failure existed on P2 with
Duplicate in a group (verified on `eb04a3f`). Fixed: members are removed before their groups
(`scene_objects._remove_objects`, the depth order of `delete_selected`); test
`test_detach.test_a_scene_with_a_group_member_newer_than_its_group_can_be_replaced` (Detach and Duplicate, a primitive
and a file). **Not changed, stated:** a load that fails inside `replace_scene` is not atomic (the new objects are
already added, so the old scene is not left unchanged as `SceneFiles.load` promises); with the ordering fixed, no known
input reaches that path.

## 18. Praxistest P3: Detach und Select Linked (Deutsch, ca. 15 Minuten)

Start: `python src/main.py`. Detach und Select Linked haben **keine Taste**. Detach steht im Menü **Mesh**; Select
Linked im **SPACE**-Menü: SPACE über dem Teil drücken, dann „Select Linked“ – es nimmt den Teil, über dem der Cursor
beim Drücken von SPACE war.

1. Einen Würfel hinzufügen (Leertaste > Add + > Cube), mit `W` neben den Kopf schieben, in Modus `4` beide auswählen,
   **Mesh > Attach** (P2). Jetzt hat das Edit-Objekt zwei Teile.
2. Modus `3`, Cursor auf den Würfel, SPACE > **Select Linked**: alle Würfelflächen sind ausgewählt, der Kopf nicht.
   Ohne Fläche unter dem Cursor: Statuszeile „nothing under the cursor“.
3. **Mesh > Detach**: der Würfel ist ein eigenes Objekt („….001“), an derselben Stelle, mit demselben Look. Du bleibst
   in Modus `3` am Kopf (O-8). `4` drücken: den Würfel anklicken und mit `W` wegziehen.
4. `Strg+Z`: der Würfel ist wieder Teil des Kopfes, die Flächen sind wieder ausgewählt. `Strg+Y`: wieder getrennt.
5. Modus `1` oder `2`, Detach: abgelehnt „press 3“. Mit eingedrehtem Morph-Ziel: abgelehnt „set it to 0 % first“.
6. Symmetrie (`Shift+S` am Kopf an): ein Ohr bzw. eine Fläche nur auf einer Seite auswählen, Detach: beide Seiten
   gehen mit (Statuszeile „with … mirror face(s)“); das neue Objekt hat Symmetrie („symmetry X on …“). Ein Teil, das
   über die Mitte geht (z. B. ein Streifen über die Nase), bekommt eine Naht: das neue Objekt zum Edit-Objekt machen
   (in `4` anklicken, dann `1`), einen Punkt einer Seite wählen, `Alt+M` – Re-Symmetrize geht darauf. Zwei Ohren ohne
   Mitte: „no seam (Re-Symmetrize not available there)“ – erwartet.
7. Morph / Gruppen: ein Teil mit Morph-Ziel und Gruppen abtrennen – das neue Objekt hat dieselben Ziele (auf 0 %) und
   die Gruppen seiner Flächen.

| # | Verdikt (KEEP / CHANGE / DROP) | Notiz |
|---|---|---|
| 1–2 | | |
| 3 (O-8: bleiben in `3` am Quellobjekt?) | KEEP (Manu, 2026-11-10) | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |

Entschieden (Manu, 2026-11-10): **O-8** „KEEP“; **O-14** „SPACE reicht vorerst (später Sub-Object Mode)“. Die Fragen
waren: **O-8** – soll es nach Detach so bleiben (Modus `3`, Quelle bleibt Edit-Objekt, das
neue Objekt nicht ausgewählt), oder lieber Modus `4` mit dem neuen Objekt ausgewählt? **O-14** – Select Linked hat
keine Taste; im Menü „Mesh“ geht „unter dem Cursor“ nicht (der Cursor ist dann auf dem Menü). Reicht das SPACE-Menü,
oder möchtest du eine Taste (dann sagst du welche, und sie kommt in `config/keymap.json`)? Detach aller Flächen wird
abgelehnt (vorläufig).

## 19. P4 — Weld: specification as built (2026-11-10)

Basis: `main` @ `b66ae84` (P3 and the Weld window decision, §10). Scope as §11: Weld in `src/mirai` and `src/gui`; no
Core, file-format or keymap change, no key.

### 19.1 Command and places

- `commands.WELD = "Weld"`, **no default key** (§0.1); the handler runs `Application.weld_vertices()` with the
  provisional default distance; a held gesture refuses it (`GESTURE_REFUSES`).
- GUI (`gui/menus.py`, decided "Weld-Fenster passt so", §10): menu bar **Mesh** > **Weld…** opens the modal window
  "Weld": the distance as a number field in world units (`input_double`, format `%.6g`; D10: always visible and
  editable, the provisional default prefilled), the preview from `Application.weld_plan` ("n Gruppen, m Punkte", or the
  refusal in amber), the note "Startwert: 0,001 × Diagonale (vorläufig)", **Weld** (disabled while the preview refuses)
  and **Abbrechen** / Esc. The preview is recomputed only when the field changes (the window is modal, so selection and
  mesh cannot change while it is open). Without a default (an empty or point-sized mesh) the field shows 0 and the
  preview asks for a distance.

### 19.2 The kernel `src/mirai/topology/weld.py`

- `plan_weld(mesh, vertices, distance)` (read-only, object space): valid ids, sorted (W1); pairs through a spatial hash
  with cell `distance` (each point checks the 27 cells around it; "within" = `|p − q| ≤ distance`); groups = connected
  components of size ≥ 2, each sorted by id, ordered by their first id; then per group W2 (every pair within the
  distance) and W3 (no shared edge or face); then W4 and W6 **predicted** on the face boundaries around the welded
  points with every member replaced by its group's smallest id: two faces on the same corners or an edge with more than
  two faces (W4), a *merged* edge (two original edges landing on one pair) used twice in the same direction (W6); and
  the survivors whose faces would form more than one fan (W5, `bowties`: reported, not refused since §19.10). Returns
  `WeldPlan(groups, refusal, merged_edges, threshold, bowties)`.
- `weld(mesh, plan)` (inside a recording): per group `add_edge(min, v)` for the other members in ascending order (W8),
  then one `core.operations.collapse_elements(mesh, members, helpers)`: its group rule writes the centroid of the
  original positions (summed in ascending-id order) and the per-layer group mean over the chain's pairwise results (W7,
  F9). The survivors must be the groups' smallest ids, and W4 / W6 are checked again on the real boundaries around the
  survivors (the same function as the prediction); a failure raises `WeldRefused` and the caller's transaction rolls
  back exactly.
- `differing_points(mesh, groups)` (W11) and `world_threshold_default(diagonal)` (D10: `0.001 × diagonal`, None for 0).

### 19.3 Read-only checks (`Application.weld_plan(threshold)`, in this order)

Each refusal is a status line, `False`, and nothing changes: 1. an interaction runs; 2. not point mode → "press 1,
select the points to weld" (edge, face and object mode; `PROVISIONAL`); 3. the morph editing view ("on the base only");
4. a symmetry definition → "not with symmetry on yet - turn it off first (Shift+S)" (until P6); 5. no distance: the
default is used, and without one "enter a distance"; 6. no valid selected point; 7. the rig posed with the mesh bound;
8. the point-layer gate (`weld_vertices` is DECLARED); 9. the kernel with `t / s` (uniform scale, AD-021 Q-4) — a
distance not above 0 is refused there; 10. no group → "no two selected points within t - nothing to weld"; 11. a group
touching hidden geometry (W10: `hidden.touches_hidden` per group — a selected point outside every group does not
block); 12. the kernel's W2–W4 / W6.

### 19.4 The step (one Undo step)

**One** `_mesh_transaction("Weld n points into k", weld)`; history: one `MeshDeltaCommand` and one selection-mirror
entry. Afterwards point mode stays, and the previously selected points that still exist stay selected (the survivors
among them; `PROVISIONAL`). Status: "Weld: n points into k (distance t)" plus " - m point(s) averaged differing target
/ weight values" when W11 counts any, and " - k point(s) join parts at that point only (weld the neighbours to close
the seam)" for W5 (§19.10). Undo restores the mesh and the selection exactly; Redo the welded state. A
failure inside the step (W4 / W6 after the change, an unexpected survivor, a `CollapseRefused`) is rolled back: no
history entry, selection unchanged. W9: face ids stay, so corner UVs per face (F10) and regions stay unchanged.

### 19.5 Threshold (D10)

World space; compared in object space as `t / s`. The default is `0.001 ×` the diagonal of the edit object's
world-space axis-aligned bounding box (`Application.weld_default_threshold`, every point through `object_space.to_world`),
**provisional, not artist-approved (D10-v open)**; the status line repeats the value used; `dispatch_command(WELD)`
uses the default.

### 19.6 Gate and classification

`layer_declarations`: `Weld` and `weld_vertices` **DECLARED** as `(weld, None)` — the symmetric entry is None because
Weld is refused under a definition until P6; rule fixtures with morph targets
(`test_layer_topology_ops.test_weld_merges_the_layers_by_the_group_mean`, plain, and the symmetric refusal) and with
weights (`test_weights_topology_ops.test_weld_averages_the_weights_by_the_group_mean`); `weld_plan` and
`weld_default_threshold` are non-mesh. The editing view refuses `Weld`; the posed policy counts it as editing.
`symmetry_declarations`: no entry (undeclared → refused under a definition); the fail-closed guard presses `Weld` on
its symmetric fixtures. `Weld` is **not** in `_TOPOLOGY_COMMANDS`: that `can_run` stage would refuse when *any*
selected point touches hidden geometry, W10 asks per group, so `weld_plan` checks it itself.

### 19.7 Literal readings and `PROVISIONAL` choices

Point mode only (the selection of edges or faces is not converted); "within" includes the distance itself; W6 checks merged edges
only (an unrelated flipped face elsewhere is not Weld's business); "nothing to weld" is a refusal (no step); the
selection afterwards; all texts.

### 19.8 Tests (production, `tests/`)

- `tests/test_weld.py` (45 after §19.10): the group centroid and layer means for all 6 / 24 helper-edge orders of `collapse_elements`
  (bit-exact, vector and weights layers) and the survivor varying with them (W8's reason), Weld's survivor = smallest
  id for every input order; the soup of four quads welds into the shared grid (invariants, UVs); selection only, any
  order; the spatial hash across cell borders and at the distance; a distance not above 0; W2, W3 (edge, face), W4
  (twin faces, three faces on an edge), W6 predicted read-only and refused in the app with nothing changed; W5 (§19.10):
  a single pair of two parts welds and is reported, a seam welded pair by pair equals the seam welded at once (export
  identical), a flipped part welded pair by pair is refused at its first merged edge, the status line; W9 UVs
  and regions; W11; the default formula; one step with exact Undo / Redo; the command with the default; world-space
  threshold on a rotated, scaled, moved object and the default from its world box; no pair within the distance; five
  refusals changing nothing (edge / object mode, nothing selected, editing view, W10 hidden); symmetry until P6; the
  posed rig; a failure after the change rolled back exactly; the W11 status; save / load; the artist's case — a column
  of a plane detached, attached back and welded with the default gives the plane's counts again.
- `tests/test_layer_topology_ops.py` / `tests/test_weights_topology_ops.py` (+2 each): the gate's rule fixtures (both
  entries).
- `tests/test_gui_menus.py` (+2): the window's default, preview and field without a window; in the window "Mesh" shows
  "Weld…", the modal opens with the preview, Esc changes nothing, "Weld" welds with the field's value; the preview
  names a W5 point ("1 nur an einem Punkt verbunden").
- `tests/test_gl_weld.py`: GL frames before / after / Ctrl+Z / Ctrl+Y with SubD level 2 (subd_cube, the +X half
  detached and attached back, the seam welded shut); one pair welded alone (a W5 point) draws with SubD level 2 without a
  GL error and Ctrl+Z draws the frame of before.

**Measured** (container, Python 3.13, headless trace store, not the reference PC): the head basemesh with its +X half
detached and attached back (36 seam pairs = 72 points welded, all 362 points selected): default 0.4 ms, plan 5.5 ms,
Weld 9.7 ms (incl. its plan), Undo 0.8 ms, Redo 0.5 ms; the man basemesh (44 pairs, 972 points selected): 1.0 / 11.0 /
9.8 / 0.8 / 0.5 ms.

### 19.9 Limitations (stated)

- Refused under a symmetry definition (P6); D10-v (the approved default) is open until the practical test.
- Weld merges selected points only: unselected points within the distance stay, and there is no "Target Weld" (§11).
- Border values of point layers are averaged (H3); the status line counts the points (W11). A UV seam along the weld
  stays (F10).

### 19.10 W5 changed (Manu, 2026-11-10, practical test P4)

Finding: one point at the open hole of the head and one at the open border of the ear → "point 916 would join 2
separate fans of faces (a bowtie)". Decision (Manu): **"Change W5, brauchen wir auch, wenn Target Weld hinzukommt (ein
Punkt auf einen Targetpunkt ziehen der dort automatisch mit dem Targetpunkt verschmilzt für Punkt für Punkt Weld.
Brauchen also Beide Möglichkeiten"**. As built:

- W5 is no refusal any more: `plan_weld` reports the survivors whose faces form more than one fan (`WeldPlan.bowties`);
  the window's preview adds ", k nur an einem Punkt verbunden", the status line " - k point(s) join parts at that point
  only (weld the neighbours to close the seam)". Both ways work: a whole seam at once, or pair by pair — the second
  pair merges the edge between the two and the parts form one fan again; the end result is identical (tested).
- W6 needs an edge both sides use, so a part with flipped normals is refused at the **second** pair of a point-by-point
  seam, not at the first (tested). W2–W4, W7–W11 are unchanged.
- **Behaviour at a W5 point until the seam is closed** (probed in the app, 2026-11-10): Border select (`B`), SubD
  level 2 (also GL), Soft, Select Linked (the two parts count as separate islands — they share no edge), Detach and a
  further Weld work; **Dissolve** of that point is refused by the Core ("anliegende Faces bilden keinen einzelnen Fan",
  nothing changes); a border walk stops there, so Cap of a border through that point acts on what the walk finds. The
  Core invariants (`tests/mesh_invariants.py`) allow such a point.
- Target Weld itself (drag a point onto a target point) stays later (§11); it will use this rule.

## 20. Praxistest P4: Weld (Deutsch, ca. 15 Minuten)

Start: `python src/main.py`. Weld hat **keine Taste**; es steht im Menü **Mesh > Weld…**. Es wirkt auf die in Modus `1`
ausgewählten Punkte des Edit-Objekts.

1. Vorbereiten: Leertaste > Add + > **Basehead** (oder der Kopf aus einer Szene), Symmetrie aus (`Shift+S`, bis die
   Statuszeile „off“ zeigt). Modus `3`, die Flächen einer Hälfte auswählen (Rahmen ziehen), **Mesh > Detach**; Modus
   `4`, das neue Objekt („….001“) anklicken, **Mesh > Attach**. Jetzt ist der Kopf wieder ganz, aber die Mitte ist
   offen: die Punkte der Naht gibt es doppelt (SubD `Strg+2` zeigt den Riss).
2. Modus `1`, nichts ausgewählt, Cursor **neben** das Modell (nicht darauf), `B`: alle Ränder sind ausgewählt (über
   der Naht nähme `B` nur den Rand einer Seite). **Mesh > Weld…**: das Fenster
   zeigt den Abstand (Startwert) und „n Gruppen, m Punkte“ – erwartet: so viele Gruppen wie Punkte auf der Naht, doppelt
   so viele Punkte. Ränder ohne Partner (z. B. der Hals) zählen nicht mit.
3. Den Abstand sehr klein machen (z. B. `0.000001`): die Vorschau sagt „nothing to weld“, der Knopf **Weld** ist grau.
   Zurück zum Startwert oder größer, **Weld**: die Naht ist geschlossen (mit SubD kein Riss), die Statuszeile nennt
   „Weld: … (distance …)“.
4. `Strg+Z`: die Naht ist wieder offen, die Auswahl wie vorher. `Strg+Y`: wieder geschlossen.
5. Ablehnungen (nichts ändert sich, die Statuszeile sagt warum): zwei Punkte derselben Kante auswählen und den Abstand
   größer als die Kante setzen → „share an edge – that is Collapse“; Modus `2` oder `3` → „press 1“; Symmetrie an
   (`Shift+S`) → „not with symmetry on yet“.
6. Punkt für Punkt (dein „Change W5“): nach `Strg+Z` (Naht offen) nur **ein** Paar der Naht auswählen (zwei Punkte
   übereinander, ggf. Rahmen um die Stelle), **Mesh > Weld…**: Vorschau „1 Gruppen, 2 Punkte, 1 nur an einem Punkt
   verbunden“; **Weld** – die Statuszeile sagt „join parts at that point only“. Das nächste Paar daneben verschweißen:
   jetzt ist zwischen beiden eine Kante geschlossen, der Hinweis verschwindet. Ebenso das Ohr an das Loch: Paar für
   Paar, oder beide Ränder mit `B` und alles auf einmal.
7. Morph (optional): vor Schritt 1 dem Kopf ein Ziel geben (`Strg+N`, etwas formen, auf 0 % zurück). Nach dem Weld
   sitzt das Ziel an der Naht gemittelt; die Statuszeile zählt die Punkte mit unterschiedlichen Werten („averaged
   differing target / weight values“).

| # | Verdikt (KEEP / CHANGE / DROP) | Notiz |
|---|---|---|
| 1–2 | | |
| 3 (D10-v: passt der Startwert 0,001 × Diagonale?) | | |
| 4 | | |
| 5 | | |
| 6 (W5) | CHANGE → gebaut: einzelne Paare erlaubt (Manu, 2026-11-10) | §19.10 |
| 7 | | |

Offen bei dir: **D10-v** – passt der vorläufige Startwert (0,001 × Diagonale der Bounding Box), oder soll er größer /
kleiner sein? Und: nach dem Weld bleiben die übrigen ausgewählten Punkte ausgewählt (vorläufig).
