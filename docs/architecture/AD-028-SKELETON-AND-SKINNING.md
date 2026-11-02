# AD-028 — Skeleton and skinning: a scene rig, the weights point layer, CPU linear blend skinning (AD-025 Phase 6)

**Status:** **PROPOSED (2026-11-02)** — the Architecture Gate (Type C) of AD-025 Phase 6. **Stop point before code:**
Manu takes this draft to the Development chat for a second opinion (handoff, "extra stop point"; the points in §14),
then decides S1–S8 (Kurzfassung) and gives the go for the Core change (§9, CORE_V1_FREEZE §7). No production code in
this commit.
**Mode (M5):** Discovery → decision preparation; Production after the go (§12).
**Baseline:** `main` @ `0af65eb`. Every code fact below was read there (file:line).
**Answers:** AD-025 §11 "Skinning data model" (influence keys, maximum influences, normalization tolerance, bind pose,
where bindings live beyond AD-021 §4.9, the final shape of the weights kind) and AD-021 §4.9 "bind-pose storage".
**References (binding):** [AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) §3, §4.1–§4.4, §7, §10 (H2, H3, H5c),
§11, §17.1, §17.5 · [audit 2026-10-27](../research/deformation/MESH_ARCHITECTURE_AUDIT_2026-10-27.md) §E, §G Phase 6 ·
[AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) §4.3, §4.5, §4.6, §4.9 · [AD-027](AD-027-INTERACTION-LAYER-SESSION-SLOT.md)
§3.1–§3.5 · [CORE_V1_FREEZE](CORE_V1_FREEZE.md) §1, §4, §7 · [REFERENCE_HARDWARE](REFERENCE_HARDWARE.md) §2–§4 ·
[AD-020](AD-020-SOFT-SELECTION-APP-PATH.md) · [AD-REGIONS-01](AD-REGIONS-01-FACE-REGIONS-STORAGE.md) ·
[Morph Lab README, "Kiefer-Pose"](../../experiments/morph_lab/README.md) ·
[CHARACTER_SYSTEMS_RESEARCH](../research/CHARACTER_SYSTEMS_RESEARCH.md) O-06, O-11 · [AD-005](AD-005-RIGGING-INTEGRATION.md)
SUPERSEDED (history only, X-9).
**Tags:** **[V]** verified in code at `0af65eb` · **[C]** measured in the container (Linux, Python 3.13.18; a scratch probe
outside the repository, not kept; it is re-runnable from its description in §5.4) · **[D]** a measurement recorded in a
decided document (named) · **[H]** estimate. No number here is a reference-PC number; Python there runs ≈ 2× slower
(REFERENCE_HARDWARE §2). `PROVISIONAL` marks every agent choice the Artist has not verified.

## Kurzfassung für Manu (Deutsch)

**Was:** Knochen und Gewichte für das Kiefer-Szenario, so gebaut, dass du nach dem Riggen weiter modellieren kannst.
Die Knochen gehören zur Szene (ein Rig kann später Kopf, Augen und Zähne bewegen), die Gewichte gehören zum Mesh — als
Punkt-Layer wie die Morph-Ziele. Dadurch laufen sie ohne Extra-Arbeit durch Undo, Knife, Loop Insert, Collapse, Extrude
und Speichern: ein neuer Punkt bekommt die Gewichte, die zwischen seinen Nachbarn liegen. Ausgewertet wird
Morph → Skin → SubD: ein Lächeln wird am ruhenden Kiefer geformt und fährt mit, wenn du den Kiefer drehst.

**Ablauf (geplant, Tasten `PROVISIONAL`):** Gruppe „Kiefer“ aktiv → Working Pivot (`P`) ins Kiefergelenk (ein Klick
setzt ihn schon heute in die Mitte des Kopfes) → Kiefer-Flächen auswählen → *Knochen anlegen* (vom Pivot zur
Auswahlmitte) → *Gewichte aus Gruppe*: Taste halten, Maus links/rechts = Auslaufbreite, loslassen = ein `Strg+Z` →
Pose-Modus (`5`), Knochen anklicken, `E` dreht → Mundwinkel: Punkte wählen, *Gewicht setzen*: Taste halten + Maus =
Wert, mit Soft (`O`) weich auslaufend → Ausdruck als Morph wie bisher → *Ruhe ↔ Pose* (eine Taste) → Loop am
Mundwinkel → zurück in die Pose → speichern, laden.

**Deine Entscheidungen** (je eine Zeile; „ja“ = Empfehlung):

- **S1 Gewichte:** bis zu 4 Knochen pro Punkt, zusammen 100 %. Was ein Knochen abgibt, geht an seinen Elternknochen;
  ein Knochen ohne Eltern gibt an das Objekt ab (dieser Anteil bleibt stehen). — *ja / anders*
- **S2 Auslauf aus der Gruppe:** wie Soft Selection (geodätisch, Smooth-Kurve, deine Soft-Einstellungen), die Breite
  mit gehaltener Taste + Maus — statt fester Kantenringe wie im Lab. — *ja / Kantenringe*
- **S3 Korrektur:** Punkte wählen, Taste halten + Maus = Gewicht des aktuellen Knochens; mit Soft an läuft die Änderung
  nach außen weich aus (weiter weg = weniger Änderung). — *ja / anders*
- **S4 Pose = Ansicht** wie das Morph-Gewicht: kein `Strg+Z`, nicht gespeichert (nach dem Laden Ruhepose); `Esc`
  während des Drehens bricht ab; eine Taste schaltet Ruhe ↔ letzte Pose. — *ja / Pose speichern und mit `Strg+Z`*
- **S5 Modellieren nur in Ruhe:** In einer Pose lehnt die App Verschieben und Topologie am gebundenen Mesh mit Meldung
  ab (Ruhe ↔ Pose ist ein Tastendruck); Gewichte setzen, Morph-Ziele formen, Auswahl und Undo gehen auch in der Pose.
  — *ja / an der Ruheform weiterarbeiten, während die Pose sichtbar bleibt*
- **S6 Gebundenes Objekt bleibt stehen:** In `4` lässt sich ein Objekt mit Gewichten nicht verschieben, drehen oder
  skalieren (sonst säße es später falsch auf den Knochen); *Transform übernehmen* geht. — *ja / erlauben*
- **S7 Tempo:** flüssig auf Kopf und Körper; auf gollum_20k mit einem Bereich in Kiefergröße „benutzbar, nicht
  flüssig“ (wie bei Morph). 20k flüssig braucht einen GPU-Zeichenweg — eine eigene Entscheidung nach der Messung auf
  deinem PC. — *ja / 20k flüssig ist Pflicht in dieser Phase*
- **S8 Spiegelkopie** eines Meshes mit Gewichten: gesperrt, bis Knochen gespiegelt werden können. — *ja*

**Zur Kenntnis (keine Frage):** Nur das bearbeitete Objekt zeigt die Pose (Zähne als eigenes Objekt folgen in dieser
Phase nicht). Auswahl und Hover liegen wie bei Morph auf der Ruheform.

**Nächster Schritt:** Dieser Entwurf geht als zweite Meinung in den Development-Chat (Punkte in §14), dann dein Go.

---

## 0. Decisions this AD rests on

**Artist (Manu):**

- 2026-10-29: order docs → AD-027 → Phase 6. Acceptance is the jaw scenario: jaw bone + weights, one expression as a
  morph, then a loop inserted at the mouth corner; bones, weights and the morph survive, also through save/load.
- 2026-11-02: weights are created from a face group (polygroup "Kiefer") with an automatic falloff whose width the
  artist adjusts; corrections by selecting points and setting a weight, Soft Selection supplying the soft transition.
  No weight brush in this phase.
- Inherited: AD-025 H2 (a new point interpolates), H3 (a merge averages), H5a (Phase 5 before 6 — built), H5c ("fluid
  on head and body, usable on gollum_20k until the GPU phase"), F-11 (the morph weight is view state: no Undo, not
  saved), Morph Lab 6a (picking on the rest shape "hilft"); AD-021 Q-4 (uniform object scale); AD-020 S2c ("geodesic
  würde ich als Standard nehmen").

**Engineering (handoff), and what this AD does with each:**

| Handoff point | Here |
|---|---|
| Rig on `Scene`, a bone hierarchy, a general data model, only the UI the jaw needs | kept (§3.1, §8) |
| Weights as the WEIGHTS point layer, ≤ 4 influences, normalized, the remainder to the parent bone | kept, with one reading: the object is the parent of every root bone, and its share is implicit (§3.3, §3.4) |
| CPU linear blend skinning (LBS) in the chain morph → skin → SubD; GPU only if a reference-PC profile demands it | kept (§5); **the acceptance "pose step ≤ 16.7 ms at 20k [RPC]" is not reachable on this path at a jaw-sized region** — evidence and a proposed acceptance in §5.4 (P-1) |
| Posing with the transform interaction (E + gizmo) on a bone in a pose mode | kept (§8) |
| Pose persistence and Undo follow the morph-weight rule | kept (§6) |
| Editing the posed mesh: defined by the AD, fail-closed | refused with a one-key rest ↔ pose toggle (§7) |
| Rigid parts (lower teeth as an object) not in this phase | kept; the data model would carry them, the display does not yet (§5.3) |

## 1. Facts (verified at `0af65eb`)

| # | Fact | Where [V] |
|---|---|---|
| F-1 | `LayerKind.WEIGHTS` is reserved: `PointLayerInfo` allows only `new_point="interpolate"` for it, `add_point_layer` and the file refuse the kind | `src/core/mesh.py:99`, `:129`, `:612`, `:2534` |
| F-2 | The per-kind arithmetic sits in four places, all vector-only today: `_origin_values` (`add_vertex(origin=…)`, `split_face(origins=…)`), `_blend_values` (`split_edge`), the inline average in `collapse_edge`, and `_layer_means` in `collapse_elements` (through the public API) | `mesh.py:683`, `:1062`, `:1084`; `core/operations/collapse.py:86`, `:103` |
| F-3 | Packed storage: one append-only `LayerSlots` map per mesh, per layer `PackedValues` = three float64 per slot plus a presence byte | `src/core/layer_storage.py` |
| F-4 | `map_vector_layers` (Apply transform, mirror) skips every non-vector layer | `mesh.py:674` |
| F-5 | `Scene.rig` is `None`; `serialization.py` writes `scene.rig` verbatim and reads `data.get("rig")` back without validation; versions 4 / 5 / 6 are written by content, 2–6 read | `src/core/scene.py:242`; `src/core/serialization.py:76`, `:100` |
| F-6 | The chain is `SurfaceChain((morph.provider, subdivision.provider))`; a stage's input is the edit mesh or the nearest earlier stage's `surface_mesh`, SubD follows its input mesh's journal; H7-E entry surfaces merge in stage order (a later stage wins) | `src/mirai/application.py:511`; `src/mirai/surface_chain.py` docstring, `:79` |
| F-7 | `morph_mix.MixSurface` is the evaluation pattern: one evaluated `core.Mesh` per base, patched in place from `Mesh.watch()` keys, drift guard by recomputing every candidate from its inputs | `src/mirai/morph_mix.py` |
| F-8 | `can_run` stage 7 iterates `Application._mode_policies`, an empty tuple; AD-027 §3.5 reserves it for a pose mode (SkeletonController, bone rotation as a `GestureSession` kind) | `application.py:432`, `:3144` |
| F-9 | The Working Pivot places a point "inside" with one click (the middle of the view ray's entry and exit: "jaw hinge, elbow, knuckle"), snaps to the symmetry plane, lives in object space | `src/mirai/pivot.py` docstring |
| F-10 | Soft field: `compute_influence(mesh, seeds, radius, metric, curve, …)` → `{v: w ∈ (0, 1]}`, seeds exactly 1.0; `symmetric_influence` gives pair-exact fields; defaults geodesic + smooth | `src/mirai/soft_selection/influence.py:191`, `symmetric.py:98`, `settings.py` |
| F-11 | The active polygroup of the edit object: `Application.active_region()` | `application.py:2410` |
| F-12 | Layer consumers: the morph targets list only `LayerKind.VECTOR` layers; `object_mirror.mirror_mesh` copies **every** layer (it would copy a weights layer unchanged) | `src/mirai/morph_targets.py:89`; `src/mirai/object_mirror.py:113` |
| F-13 | The layer gate declares Split, Edge Connect, Loop Insert, Knife, Collapse, Extrude, Inset, Bevel, Delete, Dissolve, Vertex Connect, Cap, mirror copy and Apply transform; every vertex they create or merge gets its values from a Core rule (edge blend, barycentric origins, origin copies, the average) | `src/mirai/layer_declarations.py:74` |
| F-14 | History: `CompositeCommand` makes several commands one entry; `MeshDeltaCommand` carries layer deltas unchanged | `src/mirai/scene_objects.py:353`; `src/core/operations/topology.py:64` |
| F-15 | Morph Lab jaw pose (Discovery, `PROVISIONAL`): rotation about X through a hinge by `angle · weight` (a scaled rotation, not LBS), weight 1 on the group, `1 − ring / 4` over three edge rings; morph first, pose second | `experiments/morph_lab/morph.py:150`, `:187` |
| F-16 | Only the edit object's surface is replaced (plus H7-E entry surfaces, today the morph base beside its editing view); every other object draws its own mesh | AD-013 H7; `surface_chain.py` |

## 2. Decision in one screen

1. **Rig** = an immutable `core.Rig` value on `Scene.rig`: bones with `BoneId`, name, parent and a rest frame (head,
   tail, roll) in world space. Data only in the Core; every behaviour in `src/mirai`.
2. **Bind pose** = the bones' rest frames together with the mesh's rest shape. No bind matrix per object; a bound
   object's placement is locked (Apply transform stays allowed, it keeps the world shape).
3. **Weights** = one WEIGHTS point layer per bound mesh: per vertex 1–4 pairs `(BoneId, w)`, `w > 0`, `Σw ≤ 1`; the
   remainder `1 − Σw` is the object's share (it does not move); the default `()` = unbound.
4. **Core arithmetic per kind:** a convex combination per key, the object's share included → keep the 4 largest →
   renormalize → snap rounding. Every Phase 5 rule applies unchanged (edge blend, barycentric origins, copies, average).
5. **App write rule** (the handoff's remainder rule): raising a bone takes from the vertex's other shares
   proportionally; lowering a bone gives to its parent; a root bone's parent is the object.
6. **Evaluation:** a CPU LBS stage between morph and SubD; object space through the placement; the rest pose is exact by
   construction; the mix's drift guard.
7. **Pose** = view state (no Undo entry, not saved; Esc during a gesture; a rest ↔ last-pose toggle), like morph weights.
8. **Posed and bound:** position and topology edits of the bound edit mesh are refused (the text names the toggle);
   weights, morph layers, rig commands, selection and Undo run.
9. **AD-027:** a SkeletonController with the pose mode as a stage-7 policy, three gesture kinds (bone pose, falloff
   width, weight value), rig commands as History entries.
10. **File:** additive (`"rig"`, layer kind `"weights"`); scene version 7 only with a rig or a weights layer.
11. **Performance:** the evaluation is cheap (0.5–1 µs per point [C]); a pose step costs the viewport's per-vertex patch
    (≈ 11 µs per moved point [C/D]) — fluid on head and body, not on 20k with a jaw-sized region (P-1).

## 3. Data model

### 3.1 The rig on the Scene

`core/rig.py` (new; names `PROVISIONAL`):

- `BoneId(ElementId)` in `core/ids.py` — monotonic, never reused, the counter serialized (AD-001; the `ObjectId` and
  `LayerId` precedent). Validity is checked against `Rig.bones`.
- `Bone` (frozen): `id`, `name` (non-empty, unique in the rig), `parent: BoneId | None`, `head: Vec3`, `tail: Vec3`
  (finite, `|tail − head| > 1e-9`), `roll: float` (radians, finite).
- `Rig` (frozen): `bones` (in `BoneId` order) and `bone_id_counter`. Pure updates return a new value (`with_bone`,
  `without_bone`, `with_name`, …); validation on construction: parents exist, no cycle, every id below the counter.
  `Scene.rig: Rig | None` (the reserved slot; `None` = no rig, as today).
- **Space:** rig space = world space. A rig transform (Blender's armature object) is an additive field later (identity
  = today's behaviour).
- **Rest frame** (`rest_frame(bone, rig) -> (R, h)`, one deterministic rule): `y = unit(tail − head)`;
  `x₀ = unit(X − (X·y)·y)` with `X` the world X axis, or the world Z axis when `|X·y| > 1 − 1e-6`; `x` = `x₀` turned by
  `roll` about `y`; `z = x × y`. `R = [x y z]` (columns), `h = head`, length `|tail − head|`. Roll 0 puts a bone's X
  next to the world X axis: a jaw bone from hinge to chin opens about its own X (the Lab's hinge axis, F-15).
- **One rig per scene** spanning any number of objects (AD-021 §4.9: body, eyes, teeth). The jaw scenario has one
  object; nothing in the model assumes it.

### 3.2 Bind pose (AD-021 §4.9 "bind-pose storage")

- The bind pose is **the bones' rest frames** plus **the bound mesh's rest shape** (the Mesh = rest, AD-021 §4.9). A
  bone's skin matrix is identity exactly when its pose is identity (§5.1); the rest pose shows the rest shape.
- **No bind matrix per (object, bone)** (Maya's `bindPreMatrix`, X-13): it is needed when a skinned object may move
  independently of its rig. Here a **bound object's placement is locked** (§7.2) and Apply transform keeps the world
  result: with `T` the placement, the skinned world point is `T·A·p = S·T·p` (`A = T⁻¹ S T`, §5.1); after Apply the
  mesh holds `T·p` and `T = I`, so the world point is `S·(T·p)` — the same value up to rounding. Weights are unchanged by
  Apply (F-4).
- **Editing a bone's rest frame after binding** (re-binding) is not in this phase: delete the bone and add it again
  (Undo restores). A rest-edit mode is additive (the weights stay; the deformation follows the new rest).

### 3.3 Weights: the WEIGHTS point layer

A bound mesh carries one layer `PointLayerInfo("Skin", LayerKind.WEIGHTS)` (the name `PROVISIONAL`; the Core allows
several WEIGHTS layers, the app binds one per mesh). Its value per vertex (`WeightsValue`):

- **W1** a tuple of 1–4 pairs `(key, w)`: `key` an `int ≥ 0` (the Core treats keys as opaque; the app's `BoneId`),
  keys strictly ascending, `w` a finite float with `0 < w ≤ 1`.
- **W2** `Σw ≤ 1 + 1e-9`. The **object's share** `r = max(0, 1 − Σw)` is implicit: that part of the point stays at
  rest. "Normalized" means `Σw + r = 1` — true by definition; what the Core guards is `Σw ≤ 1`.
- **W3** the default `()` (fully the object's: unbound) is never stored (AD-025 L2), so layer state compares as dicts.
- **W4** canonical form, applied by every Core write: zero weights dropped, keys sorted, `Σw > 1` divided by `Σw`, and
  the snap of §3.5.
- **W5** every combination result satisfies W1–W4 (§3.5); a value written through `set_layer_value` is validated and
  canonicalized; the file accepts only canonical values (fail-closed).
- **Why the object's share and not a mandatory root bone:** a rig with one jaw bone is complete; a vertex in the falloff
  is part jaw, part object. With a head bone as the jaw's parent, the remainder rule (§3.4) writes the head explicitly,
  so the object's share appears only where nothing above the bone is weighted — which is exactly where the point
  should stay. The handoff's "remainder to the parent bone" holds with the object as the parent of every root (P-2).
- **Dead keys:** a key whose bone no longer exists (a file from elsewhere, a missed rewrite) counts as the object's
  share at evaluation — valid or dead, never wrong (AD-021 §4.5). Deleting a bone rewrites its keys (§3.4), so the app
  never produces one.
- **≤ 4:** the common real-time limit (glTF 2.0 stores influences in sets of four joints and weights; general
  knowledge, not verified against the spec text); the jaw needs two or three. A fixed width keeps the packed storage simple (§3.6)
  and a later GPU path direct. More influences would be an additive layer kind, not a change of this one.

### 3.4 The write rule in the app (the handoff's remainder rule)

`src/mirai/skin_weights.py` (`PROVISIONAL`) writes through `Mesh.set_layer_value`; the Core never needs the hierarchy.
Setting bone `b` to `x ∈ [0, 1]` at vertex `v` with value `W` and object share `r`:

- `old = W.get(b, 0)`, `Δ = x − old`; `Δ = 0` changes nothing.
- **Raise (`Δ > 0`):** every other share — the other bones and `r` — is scaled by `(1 − x) / (1 − old)`; `b` gets `x`.
- **Lower (`Δ < 0`):** `b` gets `x`; the freed `−Δ` goes to `parent(b)`, or to the object's share for a root.
- **More than four keys after a write** (a fifth bone raised on a full vertex, or a lowered bone's parent new on one):
  `b` and the three largest other bones stay (ties: the smaller key stays); the dropped shares go to the remaining
  others proportionally (`r` included), `b` stays `x`.
- Then the Core's canonical form (W4).
- **With Soft Selection** (Manu 2026-11-02): the target is `x(v) = old_b(v) + s(v)·(x − old_b(v))` with `s` the Soft
  field of the selection (1 on the selection, falloff outside, F-10); then the rule above. Without Soft `s = 1` on the
  selection.
- **Deleting a bone** = lowering it to 0 everywhere: its share goes to its parent (or the object); children are
  re-parented to its parent with their rest frames unchanged. Never more than four keys (the parent replaces the bone).
- Why this rule and not proportional in both directions (Blender's auto-normalize, general knowledge): lowering a jaw
  share should fall back to what the jaw hangs on, not to an unrelated cheek bone that happens to share the vertex
  (P-3). Raising has no "parent" direction, so it takes proportionally.

### 3.5 Combination in the Core: why interpolation and the H3 average stay normalized

`core/mesh.py` gets one per-kind combiner used by all four places of F-2 (`combine_values(kind, [(value, a), …])`,
exported for `collapse.py`). For WEIGHTS, with affine factors `a_i` (`Σa_i = 1`):

1. **Per key:** `w_k = Σ a_i · w_ik` over the sources (an absent key counts 0), the object's share implicitly
   `r = Σ a_i · r_i`.
2. **Negative factors** (only mean value coordinates could give them; not built, AD-025 §4.1): negative results are
   dropped before step 3. The edge blend `(1 − t, t)` with `t ∈ [0, 1]`, barycentric weights and the average are
   convex, so this never happens on a built path.
3. **Keep four:** the four largest `w_k` stay (ties: the smaller key); with dropped mass `m`, every kept `w_k` is
   divided by `1 − m` (the object's share scales with them, so the survivors keep their proportions).
4. **Snap:** if `Σw ≥ 1 − 1e-12`, every weight is divided by `Σw` (removes rounding residue such as
   `(1 − t)·1 + t·1 = 0.9999999999999999`, so a fully bound vertex stays fully bound); then W4.

**Normalization holds** because a convex combination of vectors that sum to 1 sums to 1 (linearity:
`Σ_k Σ_i a_i w_ik + Σ_i a_i r_i = Σ_i a_i (Σ_k w_ik + r_i) = Σ_i a_i = 1`); rounding is absorbed by step 4 and the
`Σw ≤ 1` guard; step 3 renormalizes explicitly. The **H3 average** is the same combination with `a_i = 1/n` over the
group's **original** values (as for vectors, AD-025 §4.1). Per primitive: `split_edge` → `((v0, 1 − t), (v1, t))`;
`collapse_edge` → `((a, ½), (b, ½))`; `collapse_elements` → the group mean; `add_vertex(origin=…)` and
`split_face(…, origins=…)` → the given origin (a copy `((v, 1.0),)` is bit-exact). The vector arithmetic stays as it is
(bit-identical; the vector branch of the combiner is today's code moved, not rewritten).

### 3.6 Storage, journal and file

- **Packed:** `PackedWeights` in `core/layer_storage.py` over the same `LayerSlots` map: per slot four keys
  (`array('i')`, 32-bit) and four float64 weights plus a count byte (0 = absent) — 49 bytes per slot, ≈ 1.0 MiB at 20k,
  ≈ 4.1 MiB at 87.5k [H, arithmetic]. The same `MutableMapping` semantics as `PackedValues` (values come back as tuples,
  bit-exact float64), copy-on-write unchanged. float32 is not used: the AD-023 exactness contract asks bit-exact Undo
  and file round trips (X-16).
- **Journal:** unchanged — per-element records for writes, whole-layer records for bulk operations, value-free watches
  (AD-025 §4.2). Bone deletion rewrites only the affected values per element (O(affected), µs each).
- **File, mesh:** the layer entry as today with `"kind": "weights"` and `"values": {"<vid>": [[key, w], …]}`;
  `load_state` validates W1–W4 and refuses a non-canonical value (`ValueError`, the mesh unchanged).
- **File, scene:** `"rig": {"bone_id_counter": n, "bones": [{"id", "name", "parent", "head", "tail", "roll"}, …]}`
  (bones in id order) or `null`. `scene_from_dict` validates through `Rig` (an invalid rig makes the file invalid).
- **Version 7** is written only when `scene.rig is not None` or a mesh has a WEIGHTS layer (otherwise 4 / 5 / 6 as
  today); 2–7 are read. An older build then refuses such a file instead of saving it back without the weights (the
  AD-025 m-6 reasoning; an older build would refuse the weights kind anyway, F-1, but would carry the rig opaquely, F-5).

## 4. Operations with a weights layer

Every row runs inside one journal recording as today; "gate" = `layer_declarations` (F-13).

| Operation | Weights rule | Gate |
|---|---|---|
| Split, Edge Connect, Loop Insert | the edge blend (1 − t, t) per key, §3.5 | declared (unchanged) |
| Knife (open cut, closed shape, self-crossing; symmetric replay) | edge points as Split; interior points the barycentric origin over the original face's corners; mirror side through the vertex map (AD-025 §16) — up to 12 keys from three corners, kept to four | declared (unchanged) |
| Extrude, Inset, Bevel | copies `((v, 1.0),)`, bit-exact | declared (unchanged) |
| Collapse V/E/F | the group mean of the original values | declared (unchanged) |
| Delete, Dissolve, Vertex Connect, Cap | no vertex created; values of removed vertices deleted (journaled) | declared (unchanged) |
| Move / Rotate / Scale, Tweak, Soft, Loop / Vertex Slide, Smooth, Relax, Re-Symmetrize | untouched (positions only) | position-only |
| Apply transform | weights unchanged (F-4); the world result of a pose unchanged (§3.2) | declared (unchanged) |
| Object W/E/R in `4`, Clear transform, a mirror partner's follow | **refused while the object is bound** (§7.2) | stage-7 policy |
| Mirror copy of a mesh with a weights layer | **refused** until bones can be mirrored (S8): a copy bound to the same bones would deform mirrored geometry with the source side's bones — deterministic but wrong for any off-centre bone | refused (kind-aware), `mirror_mesh` backstop |
| Morph Lab send (`M`) | the copy carries the layer; the Lab ignores layers | allowed |
| Undo / Redo · load · OBJ export | the delta's records · the file · the rest shape only | — |
| Any position or topology edit **while posed** | refused (§7.1) | stage-7 policy |

With symmetry on, each side's new vertices interpolate their own side's values (the coordinators call a primitive per
side, AD-025 §3) — no bone mapping is needed for propagation. It is needed for *writing* off-centre bones
symmetrically (§8.4).

## 5. Evaluation

### 5.1 Formula and spaces

- **Pose channel** (view state, §6): per bone a local similarity `L_b` (rotation, translation, uniform scale `s > 0`)
  in the bone's rest frame `B_b = (R_b, h_b)`; identity = rest.
- **World skin matrix**, down the hierarchy: `S_root = B·L·B⁻¹`, `S_child = S_parent · (B_c·L_c·B_c⁻¹)`. A bone whose
  own and every ancestor's `L` is identity is flagged and gets `S = I` **exactly** — no product is formed, so the rest
  pose is bit-exact (a computed `R·R⁻¹` is not).
- **Object space:** `A_b = T⁻¹ · S_b · T` with `T` the object's placement (a similarity, AD-021 §4.3); `T = I` skips the
  conjugation.
- **LBS** for a vertex with input position `p` (the morph mix, or the rest position without targets):
  `p' = c·p + Σ_k w_k · A_k·p`, the sum over the vertex's keys whose `A_k ≠ I` in ascending key order (the first term as
  it is, as in `morph_mix`), `c = r + Σ` of the weights of unposed or dead keys. A vertex without a posed key is
  exactly `p`. Morph first, skin second: an expression sculpted at rest rides the pose (the Lab's order, F-15; the
  audit's chain, §E).
- **Normals** stay the viewport's, computed from the evaluated mesh (as for the mix, AD-025 §17.1).
- Dual quaternion skinning is not used (X-4): a hinge of 20–30° does not show LBS's twist collapse; DQS can be a later
  per-rig option on the same data.

### 5.2 The skin stage in the chain

- `src/mirai/skinning.py` (`PROVISIONAL`): `evaluate(base, input_positions, rig, pose, placement)` — the definition,
  the oracle and the SubD reference — and `SkinSurface`: one evaluated `core.Mesh` per bound mesh (same IDs and
  topology), patched in place like `MixSurface` (F-7). Candidates: the input mesh's journal keys (positions, topology:
  SubD's pattern of following its input), the base's weights-layer keys, and on a pose change the points with a key of
  a bone whose `S` changed (an index bone → points, kept in step with the weights journal). Every candidate is recomputed
  from its inputs: the shown surface is a pure function of (input positions, weights, pose, placement) — bit-identical
  whatever the order of pose steps, weight writes and edits.
- **Chain order** morph → skin → SubD (`SurfaceChain((morph, skin, subdivision))`): SubD's stencils run on the skinned
  cage; with no target shown the skin stage reads the edit mesh. The stage is wanted only while the rig is posed and the
  edit mesh has a weights layer; at rest the chain is today's. Like morph's `keep_edit_surface`, the stage keeps its
  surface across a rest ↔ pose toggle while SubD is on, so the toggle patches positions instead of rebuilding SubD.
- **H7-E entry surface:** the morph base beside its editing view shows mix + pose (the skin stage returns an entry
  surface for the base; it wins the merge, F-6). The editing view itself shows the target at rest (it has no layers).
- Picking, selection, hover and every tool stay on the rest-shape cage (Morph Lab 6a, AD-013 H7); the wire follows the
  surface (`wire_follows_surface`, as the mix).

### 5.3 What shows the pose (limits of this phase)

Only the edit object (and the morph base beside its view) shows the pose (F-16). Another bound object — lower teeth
skinned 100 % to the jaw would need no parenting — draws its rest shape until the viewport draws evaluated surfaces per
object. That belongs with rigid parts / objects parented to bones (not in scope); the data model already carries it.

### 5.4 Performance: measured, expected, and the acceptance (P-1)

**Measured [C]** (container, Python 3.13.18; scratch probe: the LBS loop above — 70 % of the region on one bone, 30 % on
two, a rotation about X — plus `set_vertex_position` into an evaluated `Mesh`, 40 steps, median; the region = the
lowest-Y share of the points):

| Mesh | region | points | LBS + writes | morph mix + writes (same points) |
|---|---|---|---|---|
| head_basemesh (326 V) | 100 % | 326 | 0.16 ms | 0.07 ms |
| Man_With_Shoes (928 V) | 100 % | 928 | 0.48 ms | 0.22 ms |
| gollum_20k (21,875 V) | 5 % | 1,093 | 0.58 ms | 0.24 ms |
| | 15 % | 3,281 | 2.37 ms | 0.99 ms |
| | 100 % | 21,875 | 21.4 ms | 7.74 ms |

The evaluation costs 0.5–1.0 µs per point, about twice the mix. **What a step costs is the viewport:** a morph weight
step that moves the same points measured [D: AD-025 §17.3, container] gollum_20k 1 target × 15 %: 36.1 / 55.2 ms p50 /
p95; × 100 %: 252 / 342 ms; Man_With_Shoes 1 × 100 %: 9.16 / 16.6 ms — the per-vertex patch of normals and face rows
(`render_mesh._sync_geometry`) is about three quarters of it (profiled there). That is ≈ 10.7 µs per moved point in the
container, ≈ 21–27 µs on the reference PC (2× [REFERENCE_HARDWARE §2]; the audit's ~27 µs per changed point [RPC]).

**Expected pose step** = the morph step at the same moved points + the LBS difference [H]: head far under the bar in
every case; the body far under it for a jaw-sized region (the sparse morph rows: 1.6 / 2.4 ms [D, container]) and at
the bar only when every body point moves (9.2 / 16.6 ms [D, container], over it on the reference PC); gollum_20k at 5 %
≈ 12 / 18 ms [C] → ≈ 25–35 ms [RPC]; at 15 % ≈ 37 / 57 ms [C] → ≈ 75–115 ms [RPC]. **The 16.7 ms bar on the reference
PC holds while a step moves ≲ 600–800 points.** A jaw on a 20k head moves thousands.

**Consequence.** GPU skinning of positions alone would remove ≈ 5 % of the step. Meeting the bar at 20k needs the
viewport's per-vertex work off the CPU: a GPU drawing path (skinned positions and normals in the vertex shader, the wire
and the flat-shading face rows fed from the same buffers, SubD off because its stencils need the CPU cage — AD-025 §17.1
gives the same three consumers for the mix) — a change of the viewport's H7 contract with its own AD and a
reference-card probe (bone matrices as uniforms or a buffer texture: GL 3.3 allows both; unmeasured). The bulk viewport
patch (§17.1 (b)) is the cheaper shared alternative, but Manu parked large-selection moves ("vorerst so lassen",
2026-10-21, ATELIER D1c), and pure Python is unlikely to gain the needed 5×.

**Proposed acceptance for this phase (P-1, S7):** the H5c rule — pose step ≤ 16.7 ms p95 [RPC] on head_basemesh and
Man_With_Shoes for a jaw-like region (≤ 15 % of the points), with and without one morph target dialled in; gollum_20k
measured and reported ("usable, not fluid" expected); the reference-PC run of the probe decides whether the GPU drawing path is the next AD. **Probe:**
`python experiments/drag_cost/probe_morph_gl.py --only-skin` (built with the phase: pose steps of a jaw-like region of 5 /
15 / 100 % on the three meshes, with a morph target, and with SubD level 2 on head and body; p50 / p95).

## 6. Pose: data, persistence and Undo

- The pose lives in the SkeletonController (`src/mirai`): `BoneId → L_b`, the **current bone**, the **last pose** (for
  the toggle) and the pose-mode flag. View state like the morph weight (F-11): no History entry, not saved; a scene load
  starts at rest; Undo and Redo never touch it.
- A pose gesture's Esc restores the pose before it (the session protocol's exact cancel); its commit pushes nothing
  (AD-027 §3.2: "≤ 1 entry").
- **Rest ↔ pose:** one command swaps the pose with the last non-rest pose (the Lab's `J`, the morph's tap-`N` 0 % ↔
  last). **Reset bone:** the current bone to identity.
- A deleted bone's pose channel goes with it and does not come back on Undo (the bone returns at rest — the precedent of
  a deleted target's weight, AD-025 §17.1).
- Why not document state (X-6): Manu decided this rule for the morph weight, and the next consumer — animation keys
  (`Scene.animation`) — will make pose channels document data deliberately; a pose in History would interleave with
  modelling steps (Ctrl+Z would undo a jaw turn before an edit). S4 asks the confirmation.

## 7. Editing while posed; placement while bound

### 7.1 Posed: position and topology edits refused (fail-closed)

- **"Posed"** = some bone has a non-identity pose. **"Bound"** = the mesh has a WEIGHTS layer with a stored value and
  `Scene.rig` exists.
- While posed, a bound edit mesh refuses every command that changes its positions or topology — the layer gate's
  position-only, declared, resolved (`C`) and locked classes except Apply transform, and the host method
  `apply_mesh_change` — with a status line (`PROVISIONAL`): `"<operation>: the mesh is posed (<toggle key> = rest pose)"`.
- **Allowed while posed:** weight commands (the point of a posed check), morph-layer commands and the editing view (it
  edits offsets at rest on its own unbound copy), rig commands, selection, display, navigation, Undo / Redo, Apply
  transform.
- **Why refuse** rather than edit at rest under the posed display (X-8): picking and the overlays stay on the rest cage
  (5.2), so with the jaw open a click on the visible lip would select the closed lip, and a Loop Insert would appear
  away from where it was aimed — silently confusing. Editing on the posed surface through the inverse blend
  (Blender's crazyspace, the audit's "inverse warping") is Phase 7 (X-7). The toggle makes rest ↔ pose one key each way;
  the edit is carried into the pose by the weights rule (§4).

### 7.2 Bound: placement locked

Object W/E/R in `4`, Clear transform and a mirror partner's follow are refused for a bound object (`"<operation>:
locked while bound to the rig"`, `PROVISIONAL`): with bones in world space a moved object would sit wrongly on its
bones from the next pose on — silently wrong later. Apply transform (world unchanged, §3.2) and deleting the object
(Undo restores) stay. A rig transform that moves rig and objects together is the later remedy (P-6, S6).

## 8. Interaction in the AD-027 structure

### 8.1 Controller and services

`src/mirai/controllers/skeleton.py`: **`SkeletonController`** — rig commands, pose state (§6), pose mode, bone picking
and drawing data, the weight gestures, the stage-7 policies, the HUD text. It reaches the app only through `AppServices`;
new members, each with its reason in its docstring (AD-027 §9 risk): `active_region()` (weights from the group, F-11),
the skin stage (to want / unwant it, as `MorphDisplay` is wired). Its gesture kinds subclass `gestures.GestureSession` —
the second user of the one controller dependency AD-027 §7.1 M7 introduced (objects → gestures), one-way.

### 8.2 Pose mode and the stage-7 policies

- **Pose mode** is controller state (a mode read by `can_run`, AD-027 §3.1), not a `SelectionMode` (no Core change).
  Entered by its command (code default `5`, `PROVISIONAL`); `1`/`2`/`3`/`4` leave it. Refused without a bone.
- `_mode_policies` gets three entries (F-8), all pure: **(1) pose mode** — only pose, rig and view-state commands
  (navigation, display, look, ortho, SubD view, morph weight and switch) and Undo / Redo; component commands refused
  `"Pose mode: bones only (1/2/3 to model)"`; **(2) posed and bound** — §7.1; **(3) bound placement** — §7.2.
- The morph editing view's table (AD-025 §15) gains the rig and weight commands as base-only; pose commands run there.

### 8.3 Commands (all `PROVISIONAL`: names, keys, texts)

| Command | What | History |
|---|---|---|
| `BONE_ADD` (component modes) | head = the Working Pivot (F-9; refused without one: "place the pivot (P) in the joint first"), tail = the centroid of the component selection, both to world; parent = the current bone; name `Bone n`; roll 0; creates `Scene.rig` if absent; the new bone becomes current | one entry (`RigCommand`: rig before / after) |
| `BONE_DELETE` | the current bone; its weights to its parent in every bound mesh (§3.4) | one entry (`CompositeCommand`: the rig + one `MeshDeltaCommand` per mesh) |
| `BONE_RENAME` | cycles a name list (`Jaw`, `Head`, `Neck`, …; unique), as the morph rename | one entry |
| `BONE_NEXT` / `BONE_PREVIOUS` | the current bone | none (view) |
| `POSE_MODE` | enter / leave pose mode | none |
| `POSE_TOGGLE_REST`, `POSE_RESET_BONE` | §6 | none (view) |
| E / W / R in pose mode, the gizmo at the bone head | `BoneGesture` | none (view) |
| `WEIGHTS_FROM_GROUP` (hold) | `FalloffGesture` | one entry on commit |
| `WEIGHT_SET` (hold) | `WeightGesture` | one entry on commit |

Keys are code defaults checked against `config/keymap.json` and free in every context (also the Morph Lab's, which
binds `J` — so the toggle does not take `J`); `config/keymap.json` is not touched.

### 8.4 Sessions (gesture kinds in the slot)

- **`BoneGesture`** (owner `"transform"`): E rotates the current bone about its head (constraint keys X/Y/Z; `K` World /
  bone-local, as for components), W translates, R scales uniformly; motion updates `L_b` and the skin stage; release
  commits (no entry), Esc restores. In pose mode an LMB click picks the nearest bone whose projected head–tail segment
  is within 10 px (CPU, a few bones; `PROVISIONAL`); a press on the gizmo hands over as `GizmoPress` does today.
- **`FalloffGesture`** (hold, mouse left / right = width in % of the mesh's bounding radius, starting at the Soft radius
  step's value): seeds = the vertices of the active group's live faces (refused without one: "make a group (Ctrl+G)");
  the field `f` from the Soft settings' metric and curve (F-10; `symmetric_influence` under symmetry); each step sets
  the current bone to `f(v)` by §3.4 on the field ∪ the vertices that had the bone at the press, **from the values at
  the press** (a pure function of width and start: no drift), inside one open recording (creates the "Skin" layer in it
  if absent). Release = one entry (`end_change` → `MeshDeltaCommand`, a layer-only, non-topology step), tap = the start
  width, Esc = `rollback_change`. It replaces the bone's weights; running it again with another width is the
  adjustment.
- **`WeightGesture`** (hold, mouse left / right = value 0–1, Ctrl snaps to 0.1): the selection's vertices, with Soft on
  the Soft field (the wheel steps its radius live, as in W/E/R); each step applies §3.4 from the press values inside one
  recording; release = one entry, Esc = rollback. Masked vertices are left as they are (mask = protected, as for every
  edit).
- **Symmetry:** both weight gestures write the partners with the same bone when the current bone lies on the symmetry
  plane (head and tail within the seam tolerance) — the jaw; an off-centre bone is refused under symmetry ("needs its
  mirror bone (not yet)"), fail-closed.
- **Weight display:** while a weight gesture runs, the Soft Selection shading overlay shows the current bone's share
  (`soft_selection.shading`, a weight map in, heat colours out), so the width is visible also at rest.

### 8.5 Drawing and HUD

`Application.bone_items()` (line items in world space: a line head → tail per bone in its posed placement, a small
cross at the head, the current bone highlighted, dimmed outside pose mode) joins `gizmo_items() + pivot_marker_items()`
in the window (`src/main.py:670`). HUD row "Rig" (only with a rig): current bone, `n` bones, rest / posed, pose mode.

### 8.6 Gate (AD-025 §4.4)

- A new class `RIG` for the rig, pose and weight commands (they handle the weights layer themselves, like `MORPH`);
  the enumeration test classifies them.
- Mirror copy becomes kind-aware: declared for vector layers only; a source with a WEIGHTS layer is refused at the gate,
  and `mirror_mesh` raises as a backstop (F-12).
- Every declared operation's rule fixture gains a weights layer (plain and symmetric): the result equals §3.5's rule,
  satisfies W1–W4, Undo is exact (DoD).

## 9. Core change (CORE_V1_FREEZE §7)

1. **Requirement:** the jaw scenario (Manu 2026-10-29): bones and weights that survive topology edits, Undo, Knife
   checkpoints, rollback and save / load.
2. **Public API?** *Weights:* no — data outside the Mesh desynchronizes on Undo, Knife checkpoints and rollback, and
   new points would get no values (AD-025 X-1, X-2); the WEIGHTS kind was reserved for exactly this (F-1). *Rig:*
   partly — `Scene.rig` round-trips an opaque value today (F-5), but History needs an immutable typed value and the file
   needs validation, which the Core can only do for a type it knows (it cannot import `src/mirai`; the `MirrorPair` /
   `ObjectMaterial` precedent).
3. **Documented:** this AD.
4. **Smallest extension:** `core/ids.py` — `BoneId`. `core/mesh.py` — the WEIGHTS kind: value validation and canonical
   form (W1–W4), the per-kind combiner used by `_origin_values`, `_blend_values`, `collapse_edge`; `add_point_layer`,
   `set_layer_value`, `layer_value` (default `()`), `export_state` / `load_state` per kind. `core/operations/collapse.py`
   — `_layer_means` through the combiner. `core/layer_storage.py` — `PackedWeights`. `core/rig.py` (new) — `Bone`,
   `Rig`, `rest_frame`, dict round trip. `core/scene.py` — `Scene.rig: Rig | None`. `core/serialization.py` — the rig
   and version 7. `core/__init__` — exports. **Not touched:** `Operation`, `OperationContext`, `HistoryStack`,
   `MeshDeltaCommand`, `MeshStateCommand`, `Selection`, every existing signature, the vector arithmetic (moved into the
   combiner unchanged). **A mesh without a weights layer and a scene without a rig behave byte-identically** (same
   export, same file version).
5. **Contract tests:** §12 T-1, T-2.
6. **Then implement** after Manu's go; the §7.1 entry and the §4 update ("Skin-Weight-Remapping": weights as a layer,
   origins applied; "Rigging / Bones": rest data in the Core, pose and evaluation outside) in the same commit.

## 10. Alternatives

| # | Alternative | Not used, because |
|---|---|---|
| X-1 | One scalar layer per bone (Blender's vertex groups; normalization at evaluation — general knowledge, not verified against Blender's source) | the ≤ 4 limit and the remainder rule become cross-layer operations the per-layer Core arithmetic cannot apply (an interpolated vertex can end with eight groups); packed storage costs 25 bytes per slot per layer whatever its occupancy (AD-025 §17.3): 50 bones × 87.5k ≈ 100 MiB; evaluation would visit every bone layer per point or keep a derived index. Its advantages (bone delete = layer delete, per-bone painting) are covered by one bulk rewrite and the gestures |
| X-2 | Weights outside the Mesh (in the rig, keyed `(ObjectId, VertexId)`) | AD-025 X-2: desync on Undo, Knife checkpoints, rollback; new points get no values |
| X-3 | Normalization with an explicit "rest" key instead of the implicit object share | the same arithmetic with a fifth key that every value carries; W3's empty default would be `((REST, 1.0),)` — no gain |
| X-4 | Dual quaternion skinning | a hinge does not show LBS's twist artefacts; more arithmetic per point; LBS is what every exporter and GPU path support. Possible later per rig on the same data |
| X-5 | GPU skinning now (the audit's "GPU + CPU reference") | positions alone are ≈ 5 % of a pose step (§5.4); SubD, the wire and flat shading read CPU positions (AD-025 §17.1). Its trigger is the reference-PC run (P-1) |
| X-6 | Pose as document state (saved, undoable; Blender) | the morph-weight rule (F-11) is the decided precedent; animation keys will make pose channels document data deliberately; a pose in History interleaves with modelling steps (S4) |
| X-7 | Editing on the posed surface (inverse blend matrices, crazyspace) | needs the inverse per-vertex blend for positions and a mapping of picks back to rest space for topology; Phase 7 ("inverse warping", audit §E) |
| X-8 | Editing at rest while the pose stays visible | picking and overlays on the rest cage under a strongly posed surface: selections and cuts land away from where the artist aims (§7.1) — silently confusing; S5 offers it as the alternative |
| X-9 | Bones on the Mesh with topology listeners (AD-005) | superseded: AD-021 §4.9 puts the rig on the Scene; listener data lives outside the journal (AD-025 X-6) |
| X-10 | Automatic weights (heat diffusion, geodesic voxel binding), envelopes | out of scope (handoff); the group falloff reuses the Soft field instead |
| X-11 | The Lab's ring-count falloff (F-15) | its width depends on the mesh density (a loop insert before weighting narrows it); the geodesic Soft field is in distance units and is Manu's Soft default (S2) |
| X-12 | The Lab's scaled rotation (`angle · weight`) instead of LBS | not a skinning model: no hierarchy, one axis, no blend of several bones; LBS of a single hinge differs from it only in how a half-weighted point moves (the chord instead of the arc) |
| X-13 | A bind matrix per (object, bone) | only needed when a skinned object moves independently of its rig; with the placement locked while bound (§7.2) and Apply transform keeping the world shape (§3.2), the rest frames are the bind |
| X-14 | One rig per object | contradicts AD-021 §4.9 (one rig spans body, eyes, teeth) |
| X-15 | The remainder resolved to "the parent" at evaluation | ambiguous for a vertex with several bones of different parents; resolved at write time instead (§3.4) |
| X-16 | float32 weights | breaks bit-exact Undo and file round trips (AD-023 exactness contract, point 3) |
| X-17 | Pose mode as a Core `SelectionMode` | a Core change for state that owns no data; AD-027 §3.1 models modes as controller state read by `can_run` |

## 11. Effect on decided ADs and documents

| Document | Effect |
|---|---|
| AD-021 §4.9 | "bind-pose storage" answered (§3.2); "a skin binding refers to `(ObjectId, VertexId)`" holds — the binding is the weights layer inside the object's mesh, keyed by `VertexId`, its keys the rig's `BoneId`s |
| AD-025 §4.1 | the normalized-weights combination it specified ahead of the data model is refined: the object's share participates implicitly, four keys are kept by size, the snap (§3.5) |
| AD-025 §11 | the skinning data model is decided here (updated in the implementing commit; a forward link now) |
| AD-025 §4.4 | mirror copy becomes kind-aware; a `RIG` class |
| AD-027 §3.5, §7.1 M7 | pose mode realised as planned (SkeletonController, stage 7, a gesture kind); the controller dependency on `gestures` gets a second user |
| AD-013 H7 | unchanged: the skin stage is an ordinary provider in the chain |
| CORE_V1_FREEZE §4, §7.1 | entries in the implementing commit (§9, point 6) |
| SOURCE_ARCHITECTURE, ATELIER, ROADMAP "Rigging Foundation" | updated with the implementation |

## 12. Implementation plan and Definition of Done

**Slices** (after the go; Production, autonomous to the DoD):

1. **Core:** the WEIGHTS kind, `PackedWeights`, `BoneId`, `core/rig.py`, `Scene.rig`, file version 7, the CORE_V1_FREEZE
   entry. Knife oracle (trigger list: the primitives).
2. **Evaluation:** `skinning.py` (`evaluate`, `SkinSurface`), the skin stage in the chain, `skin_weights.py` (§3.4).
3. **App:** SkeletonController, the commands and gesture kinds, the three policies, the gate changes, bone drawing,
   HUD row.
4. **Acceptance:** the jaw scenario test, the gate contract tests with weights, the probe `--only-skin`, docs.

**Sessions:** two fresh sessions — slices 1–2, then 3–4 — Claude Opus 5.5, effort high (the Core slice may take xhigh).

**Tests:**

| # | Test | Guards |
|---|---|---|
| T-1 | Core weights: W1–W4 validation and canonical form; the combiner (convex per key, keep four with ties, renormalize, snap, negatives dropped) against an independent `math.fsum` oracle; each primitive's rule (`split_edge`, `collapse_edge`, `collapse_elements`, `add_vertex(origin=…)`, `split_face(origins=…)`), refusals with mesh and counters unchanged; the layered random journal sequences (`test_mesh_change_journal.py` T-1) gain a weights layer — L1–L5 and W1–W4 after every step, Undo / Redo against the snapshot oracle; file round trip order-sensitive on the JSON text, non-canonical values refused; `PackedWeights` against a dict oracle; no-weights / no-rig equivalence (export and version unchanged) | §3.3–§3.6 |
| T-2 | Rig: validation (cycle, unknown parent, duplicate name, degenerate bone, ids ≥ counter), `rest_frame` (orthonormal, det +1, roll, the parallel-to-X case), round trip, version 7 rules, versions 2–7 read | §3.1, §3.6 |
| T-3 | Skinning math: `evaluate` against an independent implementation (≤ 1e-12); the rest pose bit-exact; hierarchy (a child follows its parent); object placement conjugation; dead keys = the object's share | §5.1 |
| T-4 | Skin stage: a randomized oracle (pose steps, weight writes, base moves, topology edits, morph weight steps, bone add / delete, Undo / Redo) bit-exact against `evaluate`; order independence; morph → skin → SubD = SubD of the skinned mix from scratch (≤ 1e-12); the entry surface beside the morph view | §5.2 |
| T-5 | Per gated topology operation with a weights layer, plain and symmetric (Split, Edge Connect, Loop Insert, Knife incl. a closed shape and a self-crossing, Collapse, Extrude, Inset, Bevel, Delete, Dissolve, Vertex Connect, Cap): weights == the rule, W1–W4, Undo exact; Apply transform (weights unchanged, posed world result equal ≤ 1e-12); mirror copy refused untouched | §4 |
| T-6 | Through `Application`: bone add / delete / rename with exact Undo (incl. the weights rewrite); both weight gestures (Esc exact, commit = one step, Soft, symmetry on- and off-centre, mask); the three policies (every position and topology command refused untouched while posed and running at rest; pose mode; placement); the toggle; bone picking; keys free in every context; HUD row; `can_run` purity; the E5 structure checks | §6–§8 |
| T-7 | **The jaw scenario** (`tests/test_jaw_scenario.py`, readable named steps in the AD-027 scenario style, headless): group "Kiefer" → pivot → add bone → weights from the group with a width → a Soft correction at the mouth corner → rotate the jaw (E, X) → a morph target shaped beside the base → rest → Loop Insert at the mouth corner → pose again → bones, weights (rule at the new loop, W1–W4), offsets (rule) and the posed surface (= `evaluate`) as stated; Undo to the start and Redo to the end exact; save → load bit-exact (rig, weights, targets; rest pose after the load) | the Artist acceptance |

**Mutation checks by hand** (as in AD-025 §14–§17), each must fail a test: truncation keeping the smallest, the snap
missing, a lowered share going to the object instead of the parent, the identity short-circuit missing (rest not
bit-exact), the placement not conjugated, the chain feeding the edit mesh to the skin stage instead of the mix, a weight
write without the journal, a weight gesture computing from the previous step instead of the press values.

**Runs** (AGENTS.md §8a, a `src/core` change): `pytest tests -q`; the GL tests in their own process;
`experiments/morph_lab/tests`; the Knife oracle; the AD-027 scenario tests are part of `tests/`.
**Done:** all green; the probe built and its container numbers recorded here; reference-PC numbers when Manu runs it;
the CORE_V1_FREEZE §7.1 entry and §4 update; AD-025 §11 updated; an implementation note here; one line in
`docs/ATELIER.md`.

## 13. Risks and guards

| Risk | Guard |
|---|---|
| A primitive still combines weights with the vector arithmetic | one combiner for all four places (F-2); T-1 per primitive and the random journal sequences with a weights layer |
| Rounding lets `Σw` creep over 1 or leaves residue under 1 | W2 guard, the snap, T-1 with an `fsum` oracle |
| The pose display drifts from the definition after many steps | recompute from inputs (drift guard), T-4 order independence |
| A position or topology path bypasses the posed refusal | the policy reads the layer gate's classification (one key space, its enumeration test), the host method in the table, T-6 enumerates every command while posed |
| A bound object moves off its bones | the placement policy (§7.2), T-6 |
| An older build saves a file without the weights | version 7 (§3.6) |
| The 20k bar is expected to fail on the reference PC | stated before the build (§5.4, P-1); the probe measures it |

## 14. Points for the second opinion (Development chat)

1. **P-1 Acceptance at 20k** (§5.4): the CPU path cannot meet "pose step ≤ 16.7 ms at 20k [RPC]" at a jaw-sized region
   (expected 25–115 ms); proposed: the H5c rule for this phase, the GPU drawing path as its own AD after the
   reference-PC run — or keep the bar and plan that AD now.
2. **P-2** The object's implicit share as the parent of every root bone (§3.3) — or a mandatory root bone.
3. **P-3** The write rule: raise proportionally, lower to the parent (§3.4) — or proportional both ways.
4. **P-4** Editing while posed refused with a toggle (§7.1) — or editing at rest under the visible pose (X-8).
5. **P-5** Pose as view state (§6) — or document state with Undo (X-6).
6. **P-6** A bound object's placement locked (§7.2) — or allowed (Blender-like), or bones following the object.
7. **P-7** Four influences, kept by size inside interpolation (§3.5) — or unbounded influences, limited only at a
   future GPU upload.
8. **P-8** Bones in world space without a rig transform (§3.1) — or a rig object now.

## 15. Not in scope

Weight brush; envelopes; automatic weights (heat, geodesic binding); IK, constraints; animation, keys, timeline;
bone-driven morphs or correctives; objects parented to bones and rigid parts; per-object evaluated display beyond the
edit object; GPU skinning or a GPU drawing path; editing on the posed surface; bone rest editing beyond delete + add;
bone mirroring (L/R) and symmetric weights of off-centre bones; GUI panels; `config/keymap.json`; removing the Morph
Lab; transfer between meshes (Phase 7).

---

## Praxistest für Manu nach dem Bau (Deutsch, ca. 20 Minuten)

Am Kopf (`python src/main.py`) oder an Gollum (`python src/main.py examples/meshes/gollum_20k.obj`). Tasten außer `5`
kommen mit dem Bau (`PROVISIONAL`); die Schritte bleiben.

1. **Gruppe.** In `3` die Flächen des Unterkiefers wählen, `Strg+G`, Name „Kiefer“ — oder eine vorhandene Gruppe aktiv
   machen.
2. **Knochen.** `P` halten und ins Kiefergelenk klicken (der Pivot landet in der Kopfmitte), die Kiefer-Flächen gewählt
   lassen, *Knochen anlegen*: eine Linie vom Gelenk zum Kinn erscheint.
3. **Gewichte aus der Gruppe.** Taste halten, Maus links/rechts: die Auslaufbreite (die Färbung zeigt den Anteil des
   Knochens), loslassen. `Strg+Z` nimmt es zurück.
4. **Drehen.** `5` (Pose-Modus), den Knochen anklicken, `E` halten (gern mit `X`) und ziehen: der Kiefer öffnet sich,
   Mundwinkel und Wange laufen weich aus. `Esc` während des Ziehens bricht ab.
5. **Mundwinkel korrigieren.** `1`, Punkte am Mundwinkel wählen, Soft an (`O`), *Gewicht setzen*: Taste halten + Maus,
   die Pose zeigt das Ergebnis sofort; loslassen = ein `Strg+Z`.
6. **Ausdruck als Morph.** `Strg+N`, `Tab`, ein Lächeln formen, `Tab` zurück, `N` halten + Maus: das Lächeln sitzt im
   geöffneten Kiefer.
7. **Loop einfügen.** Versuche `I` in der Pose: die Meldung nennt die Ruhe-Taste. *Ruhe ↔ Pose*, `2`, Kante am
   Mundwinkel, `I`, dann wieder *Ruhe ↔ Pose*: der neue Loop geht mit Kiefer und Lächeln mit, ohne Delle.
8. **Speichern.** `Strg+S`, Fenster schließen, über `Leertaste` laden: Knochen, Gewichte und Morph sind da (Ruhepose,
   Gewicht 0 %).
9. **Messlauf auf deinem PC:** `python experiments/drag_cost/probe_morph_gl.py --only-skin`, die Ausgabe in den Chat
   (die 16,7-ms-Grenze kann nur dein PC bestätigen).

| Punkt | Verdikt (KEEP / ITERATE / REJECT / UNKNOWN) | Notiz |
| --- | --- | --- |
| Knochen anlegen vom Pivot zur Auswahl (2) | | |
| Gewichte aus der Gruppe, Breite ziehen (3) | | |
| Pose-Modus, Knochen anklicken, `E` (4) | | |
| Korrektur mit Soft (5) | | |
| Morph unter der Pose (6) | | |
| Ablehnung in der Pose, Ruhe ↔ Pose, Loop (7) | | |
| Speichern / Laden (8) | | |
