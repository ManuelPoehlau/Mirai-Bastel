# AD-028 — Skinning, rig and pose mode (AD-025 Phase 6, the jaw scenario)

**Status:** **PROPOSED (2026-11-01) — Architecture Gate, waiting for Manu's answers to P1–P4** (Development System §5,
Haltepunkte: behaviour the artist has to feel, not derivable from existing verdicts). Nothing in `src/` is changed by
this document. Everything not listed under P1–P4 is an agent decision and marked `PROVISIONAL`.
**Mode (M5):** Production. No lab, no promotion (no experiment code moves; the Morph Lab's jaw pose is read as
evidence, not copied — M3).
**Baseline:** `main` @ `0af65eb` (AD-027 M0–M8 merged, PR #55). Code facts below were read there.
**Builds on:** [AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) §4.1 (the weights combination, "specified here,
built with skinning"), §4.2 (point layers, `LayerKind.WEIGHTS` reserved), §7 ("the weights kind is built with Phase
6"), §11, §16 (Phase 5 rules), §17.1 (the stage chain; "skinning slots in between as its own stage");
[AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) §4.9 (Mesh = rest shape; ID-keyed deformation data with the Mesh; the rig
on the Scene); [AD-027](AD-027-INTERACTION-LAYER-SESSION-SLOT.md) §3.3 stage 7, §3.5 (pose mode = a controller, a
stage-7 policy, bone rotation as a `GestureSession` kind); [audit 2026-10-27](../research/deformation/MESH_ARCHITECTURE_AUDIT_2026-10-27.md)
§E, §G Phase 6; [CORE_V1_FREEZE](CORE_V1_FREEZE.md) §7. Historical only: [AD-005](AD-005-RIGGING-INTEGRATION.md)
(SUPERSEDED), [rigging archive](../archive/experiments_2026-10/rigging-skinning-morphing/) (its "Option C" put bones
on the Mesh and copied a parent's weights — both rejected by AD-025 X-6), the Morph Lab's jaw pose
([README](../../experiments/morph_lab/README.md#kiefer-pose-zusammen-mit-morphs-provisional-übergang-bis-zum-rig-2026-10-25):
hard weight 1 in a polygroup, linear falloff over 3 edge rings, one hinge, rotation about X, view state, picking on
the rest shape).
**Tags:** **[V]** verified in code at `0af65eb` · **[C]** measured in the container (Python 3.13; throwaway probe, not
kept) · **[H]** estimate.

## Kurzfassung für Manu (Deutsch)

**Ziel (deins, 2026-10-29):** ein Kieferknochen mit Gewichten, ein Ausdruck als Morph, danach ein Loop am Mundwinkel.
Pose, Gewichte und Morph überleben das, auch Speichern und Laden.

**Was schon feststeht** (AD-025, AD-021, AD-027, Audit): Gewichte sind ein Punkt-Layer im Mesh — sie laufen dadurch
automatisch durch Split, Loop, Knife, Collapse, Extrude, Spiegelkopie, Undo und Datei, wie die Morph-Ziele. Das Rig
liegt auf der Szene, nicht im Mesh. Die Kette ist Morph → Skin → SubD. Der Pose-Modus dockt an den neuen
Interaktions-Platz an, ohne dass `Application` wächst.

**Was ich selbst entscheide (`PROVISIONAL`, ein Satz von dir reicht zum Ändern):**

- Ein Punkt hat höchstens 4 Knochen-Einflüsse; was zu 100 % fehlt, bleibt in Ruhe („hängt an nichts“). Ein neuer Punkt
  zwischen Kiefer und Wange bekommt also z. B. halb Kiefer, halb Ruhe — er reißt nicht.
- Knochen liegen im Weltraum; ein Knochen hat Kopf (Drehpunkt), Ruhe-Ausrichtung, Elternknochen und Länge (nur zum
  Zeichnen). Die Pose ist pro Knochen eine Drehung um seinen Kopf.
- **Knochen anlegen** (minimal): Punkte am Kiefergelenk auswählen, eine Taste → Knochen mit dem Kopf in der Mitte der
  Auswahl, Achsen = Weltachsen (wie das Scharnier im Morph Lab). Eine zweite Taste setzt die Spitze auf die Mitte
  einer Auswahl (z. B. Kinn), nur fürs Zeichnen.
- **Gewichte zuweisen** (minimal, kein Pinsel): Kieferflächen auswählen, mit Soft Selection (`O`) den Übergang
  einstellen, eine Taste → der aktuelle Knochen bekommt die Auswahl, der Soft-Verlauf blendet zur Wange aus. Eine
  zweite Taste nimmt Gewicht weg. Mit Symmetrie wirkt es auf beiden Seiten. Im Pose-Modus zeigt die Fläche die Gewichte
  des gewählten Knochens farbig (die vorhandene Soft-Einfärbung).
- Skinning auf der CPU (gemessen: die Rechnung kostet beim Kopf 0,3 ms, beim Körper 0,9 ms, bei gollum_20k 21 ms, wenn
  jeder Punkt gewichtet ist); kein GPU-Pfad, solange keine Messung ihn verlangt.
- OBJ-Export und das Morph Lab bekommen weiter die Ruheform. Das Formen eines Morph-Ziels daneben (`Tab`) zeigt die
  Ruhepose; ein Korrektur-Morph auf dem gestellten Kiefer (Inverse Warping) kommt nicht in Phase 6.
- Tasten: alle neu, nur Engineering-Vorschläge, nichts in `config/keymap.json` (Vorschlag in §2.5).

**Deine Fragen (je eine Zeile, Empfehlung zuerst):**

- **P1 — Pose speichern?** Die Pose ist Dokument: sie wird gespeichert, und jede Knochen-Drehung ist ein Undo-Schritt
  in derselben Liste wie das Modellieren. **Empfehlung: ja** (dein Ziel sagt „Pose überlebt Speichern und Laden“;
  Blender/Maya machen es so). Alternative: Ansicht wie das Morph-Gewicht (kein Undo, nicht gespeichert, wie die
  Kiefer-Pose im Morph Lab).
- **P2 — Morph-Gewichte dann auch speichern?** **Empfehlung: nein, vorerst bleibt das Gewicht Ansicht** (deine
  Entscheidung vom 2026-10-17 bleibt; nach dem Laden steht der Ausdruck auf 0 %, der Kiefer aber in seiner Pose).
  Alternative: das Gewicht wird mit der Pose Dokument (gespeichert, Undo-Schritt pro Änderung).
- **P3 — Modellieren bei gestelltem Kiefer:** Die Fläche zeigt Morph + Pose, Auswahl, Hover und Werkzeuge liegen auf
  der Ruheform — wie beim Morph-Gewicht (dein „hilft“, 6a). **Empfehlung: ja.** Alternative: außerhalb des
  Pose-Modus wird die Ruhepose gezeigt (die Pose erscheint nur in `5`).
- **P4 — Pose-Modus als fünfter Modus** (`5`, Vorschlag): darin sind nur Knochen klickbar, `E` halten dreht den
  gewählten Knochen (mit `X`/`Y`/`Z`), das Mesh ist dort nicht editierbar; `1`–`4` verlassen ihn. **Empfehlung: ja**
  (wie Blenders Pose-Modus). Alternative: Knochen in Modus `4` mitdrehen, ohne eigenen Modus.

Nach deinem Go baue ich in fünf einzeln grünen Schritten (§5) und schreibe am Ende den Praxistest (20–40 min).

---

## 1. What is decided and what is open

| Topic | State | Source |
|---|---|---|
| Weights live on the Mesh as a point layer (kind `WEIGHTS`, `new_point = "interpolate"` only), keyed by `VertexId`, journaled, saved | decided | AD-021 §4.9, AD-025 §4.2, §7 |
| Combination of weights for a new / merged point: sparse Σ wᵢ·vᵢ over influence keys, negatives dropped, renormalized | decided, details open | AD-025 §4.1 |
| The topology rules (Split, Edge Connect, Loop Insert, Knife incl. symmetric, Collapse, Extrude, mirror copy) apply to every layer; Apply transform maps only vector layers ("weights unchanged") | decided and built for vectors | AD-025 §3, §16 |
| Rig on the Scene (`Scene.rig`, reserved, `null` in every file); one rig spans several objects; a binding is valid or dead, never wrong | decided | AD-021 §4.9, `src/core/scene.py:242` [V] |
| Chain morph → skin → SubD; picking on the rest-shape cage; evaluated geometry never saved, never in History | decided | AD-021 §4.9, AD-025 §17.1, audit §E |
| LBS with a CPU reference; a GPU path only on a measured need | decided (assignment) | audit §G, AD-025 §17.1 |
| Pose mode = SkeletonController, a stage-7 policy in `can_run`, bone rotation as a `GestureSession` kind; no new field or branch in `Application` | decided | AD-027 §3.5 |
| Max influences, normalization tolerance, the "no bone" remainder, storage of the weights kind | **open → agent (§2.1)** | AD-025 §11 |
| Data shape of the rig: bones, hierarchy, rest and pose transform, IDs, file | **open → agent (§2.2)** | AD-021 §4.9 "not decided: bind-pose storage" |
| How bones and weights are created in the jaw scenario | **open → agent, minimal (§2.5)** | assignment |
| Pose: document or view state; its Undo | **open → P1** | AD-025 §11 ("weights as document state"), Morph Lab jaw = view |
| Morph weight next to a saved pose | **open → P2** | F-11, J-decisions 2026-10-17 |
| What modelling shows while posed | **open → P3** | 6a "hilft" (morph only) |
| Pose mode as its own mode and its entry | **open → P4** (mechanics decided, product shape not) | AD-027 §3.5 |
| Editing on a deformed pose, correctives, inverse warping | **out of Phase 6** (§6) | AD-021 §4.9, audit §E |

## 2. Decision (proposed)

### 2.1 The weights kind in the Core (`PROVISIONAL` names)

- **Value:** `tuple[tuple[int, float], ...]` — up to **4** `(influence key, weight)` pairs, keys ascending and unique,
  every weight finite and in (0, 1], **Σ ≤ 1 + 1e-9**. The **remainder 1 − Σ stays at rest** (bound to nothing). The
  default is `()` ("all at rest"), never stored (AD-025 L2). Influence keys are opaque positive integers to the Core —
  in the app they are `BoneId`s of `Scene.rig` (the AD-SYM-01 pattern: the Core stores and combines, `src/mirai`
  interprets).
- **Why a remainder instead of "Σ = 1 over bones":** a point created between a bound and an unbound point must get half
  the bone, not all of it; with Σ = 1 and `()` as "unbound", AD-025 §4.1's renormalization would turn `0.5·{jaw: 1} +
  0.5·()` into `{jaw: 1}` — the corner of the mouth would follow the jaw completely. With the remainder the
  combination stays affine and needs no renormalization in the normal case; no root bone is needed for the jaw.
  This is AD-025 §4.1 made concrete (the remainder counts as one implicit influence), not a change to it.
- **Combination** (`add_vertex(origin=…)`, `split_edge`, `split_face(origins=…)`, `collapse_edge`, the
  `collapse_elements` group mean): per key Σ wᵢ·vᵢ, in ascending key order; drop weights ≤ 1e-6 (negatives from a
  future MVC caller included, AD-025 §4.1); keep the 4 largest (ties: the smaller key); if Σ > 1 divide by Σ. A copy
  `((v, 1.0),)` is bit-exact (the vector kind's first-term rule). Split, Collapse, Knife, Extrude: no tool change —
  they already pass origins for every layer.
- **Frame change:** `map_vector_layers` skips weights (already coded: it maps only `VECTOR` [V] `mesh.py:674`);
  mirror copy copies weights unchanged through the index map (keys are not mirrored: right for a centre bone such as
  the jaw; paired left/right bones are §6).
- **Storage:** a separate packed form beside `PackedValues` (4 int32 keys + 4 float64 weights + count per slot, on the
  shared `LayerSlots` map) or a dict per layer — chosen in step S1 by the AD-025 §17.3 memory probe; behind the
  unchanged layer API either way (CORE_V1_FREEZE §7: internals change when measurement justifies it). One weights
  layer per mesh is an app rule (name `"Skin"`), not a Core rule.
- **Write API:** `set_layer_value` validates per kind (vector or weights); a new journaled bulk helper is not needed —
  weight assignment is a per-element write on the touched points (one `record_mesh_change`, one `MeshDeltaCommand`).
- **File:** `"point_layers"` entries with `"kind": "weights"` and values `{"<vid>": [[key, w], …]}`; an invalid value
  (count > 4, Σ > 1, a key ≤ 0, unsorted) makes the file invalid (fail-closed, AD-025 §4.2).

### 2.2 The rig on the Scene (Core data, `PROVISIONAL` names)

- `BoneId(ElementId)` in `core/ids.py` (never reused, AD-001). `core/rig.py` (new, pure data like `MirrorPair`):
  `Bone(id, name, parent: BoneId | None, head: Vec3, rest_rotation: Mat3, length: float)` — **world space**, frozen,
  validated like `ObjectTransform` (orthonormal, det +1). `Rig(bones, pose, bone_id_counter)`, frozen; `pose:
  Mapping[BoneId, Mat3]` = each bone's rotation relative to its rest frame, about its head; identity is not stored.
  Invariants: unique names, parents exist, no cycle, pose keys are live bones.
- **One rig per scene**, `Scene.rig: Rig | None`. An object is skinned when its mesh has a weights layer; the rig is
  the scene's. Changes replace the whole `Rig` value (a few dozen bones: whole-value is cheap), so Undo is a value swap:
  `RigCommand(scene, before, after)` in `src/mirai` on the existing `HistoryStack` (its docstring already names "eine
  Rig-Pose-Änderung" [V] `core/history.py:8`).
- **Forward kinematics:** world pose of a bone G_b = G_parent · (rest relative to the parent) · pose_b; skin matrix
  S_b = G_b(pose) · G_b(rest)⁻¹. At rest every S_b is the identity — so moving a skinned object in `4` or Apply
  transform changes nothing visible at rest; while posed, the object moves against the rig (the rig does not follow;
  moving the whole character is a root bone's pose, later).
- **Deleting a bone** strips its key from every weights layer in the same composite command (its share goes to the
  remainder) — files never hold a dead key; a file with a key the rig does not have is invalid.
- **File:** `"rig": null | {"bone_id_counter", "bones": [{"id", "name", "parent", "head", "rest_rotation", "length"}],
  "pose": {"<bone id>": rotation}}`; **scene file version 7**, written only when the scene has a rig or a weights layer
  (an older build refuses the file instead of dropping the rig — the AD-025 v5 rule), versions 2–7 read. If P1 is
  answered "view state", `"pose"` is not written and the pose moves to the SkeletonController.

### 2.3 The skin stage in the chain

- `src/mirai/skinning.py`: `skin(points, weights, matrices) -> points` — the CPU reference, p' = (1 − Σw)·p +
  Σ wᵦ·(S_b·p) in world coordinates (object space → world through the object's placement → skin → back), the
  `morph_mix` style: a pure function, in ascending key order, so the result is bit-identical whatever the order of pose
  steps (drift guard by construction, AD-025 §17.1).
- `SkinSurface`, an H7 stage in `surface_chain` **between morph and SubD**: its input is the morph stage's
  `surface_mesh` (or the edit mesh), its output an evaluated mesh with the same IDs, patched in place: a pose step
  recomputes only the points with a weight on a bone whose S_b changed; a base edit only the points its journal names
  (the `MixSurface` pattern). Every other skinned object gets its surface as an H7-E entry surface (a rig spans
  several objects), the way the morph mix shows the base beside the editing view. Nothing is drawn on a skinned mesh
  at rest pose (the stage stays out of the chain, so every existing behaviour is unchanged without a pose).
- **Measured [C]** (throwaway probe, the inner loop only, 4 influences per weighted point): p50 0.29 ms head (326 V),
  0.88 ms Man_With_Shoes (928 V), 21 ms gollum_20k (21,875 V) with every point weighted; 15 % weighted: 0.04 / 0.13 /
  3.1 ms. The arithmetic is not the cost; as with the morph mix the frame cost will be the viewport's per-vertex patch
  (AD-025 §15.3, §17.3). **No GPU path** unless the S3 probe shows a head or body pose step over the bar on the
  reference PC (its trigger and alternatives as AD-025 §17.1).

### 2.4 Pose mode (AD-027 §3.5)

- `src/mirai/controllers/skeleton.py`: the **SkeletonController** — rig commands (create bone, set tail, delete,
  rename), the current bone (view state, like the current morph target), bone pick (screen distance to the drawn
  segments), weight assignment, the bone overlay, the weight display (the soft shading overlay fed with the current
  bone's weights), and the HUD text.
- **The mode is the controller's state** (not a fifth `SelectionMode` in the Core): `can_run` stage 7 gets the
  controller's policy — in pose mode only bone commands, navigation, display, Undo/Redo, save and the mode keys run;
  everything else is refused silently or with `"<command>: not in pose mode (1-4 leave it)"`. Entering pose mode
  keeps the component selection; leaving it restores the previous mode. No Undo step (like `1`–`4`).
- **Bone rotation** is a `GestureSession` kind (`BoneGesture`): `E` held, mouse moves, release = one `RigCommand`, Esc
  = exact prior pose; `X`/`Y`/`Z` constrain to the bone's local axes (`K` world ↔ local, the existing toggle).
  `_transform_arm` gets no `if pose` branch: arming goes through the same per-mode lookup the stage-7 policy uses
  (one table entry, AD-027 §3.5 "its handlers in the table").
- Exactly what AD-027 §3.5 lists: build the controller, one entry in the policy tuple, its handlers in the command
  table. The structure test of AD-027 E5 pins "no new `Application` field or entry-point branch".

### 2.5 Creating bones and weights in the jaw scenario (minimal, `PROVISIONAL`)

Engineering keys, checked free against `config/keymap.json`, the code defaults, `MORPH_KEYS` and the Morph Lab's
`LAB_KEYS` (which uses `J`, `Shift+J`, `M`, `,` `.`, `Alt+B`, Alt/Ctrl+arrows) — checked again in S4 by the existing
"keys free in every context" test pattern:

| Key (proposal) | Where | Does |
|---|---|---|
| `5` | everywhere | pose mode on / off |
| `Ctrl+J` | `1`/`2`/`3` | new bone, head = centre of the selection (the Working Pivot if one is placed), axes = world, parent = the current bone (none for the first), becomes current |
| `Ctrl+Shift+J` | `1`/`2`/`3` | the current bone's tail = centre of the selection (display length only) |
| `Ctrl+Alt+J` | `1`/`2`/`3` | assign: every point with Soft influence s (selected = 1): w ← (1 − s)·w + s·{current: 1} |
| `Ctrl+Alt+Shift+J` | `1`/`2`/`3` | remove: w ← w with the current bone's share scaled by (1 − s), the rest goes to rest |
| LMB | `5` | pick a bone (current bone) |
| `E` hold | `5` | rotate the current bone |
| `Alt+E` | `5` | reset the current bone's pose |
| `J`, `Shift+J` | — | left free (the Morph Lab's jaw keys; the Lab runs this `Application`) |

Assignment and removal are one `record_mesh_change` each (one Undo step), symmetric through the existing symmetric Soft
influence when symmetry is on. The first assignment on a mesh adds its weights layer in the same step.

### 2.6 Behaviour of existing features with a rig

| Feature | With weights / a pose |
|---|---|
| Split, Edge Connect, Loop Insert, Knife (plain, symmetric), Collapse, Extrude | the §2.1 combination through the existing origins; the gate entries already exist (AD-025 §16) — S1 adds weights fixtures to every declared entry (declaration = tested support) |
| Delete / Dissolve | the survivors keep their weights (AD-025 §3) |
| Apply transform | weights unchanged; at rest nothing changes; posed, see §2.2 |
| Mirror copy | weights copied, keys unchanged (§2.1) |
| Morph targets | the chain morph → skin: a target is sculpted at rest (the `Tab` view shows rest pose) and rides every pose; the base beside shows morph + pose |
| SubD | runs on the skinned cage (chain) |
| Save / load | weights in the mesh state, the rig (and, P1, the pose) in `"rig"`, version 7 |
| OBJ export, Morph Lab `M` | rest shape (AD-025 §3) |
| Undo across a topology step with a pose | the skin surface follows the journal (S3 test) |

## 3. Alternatives

| # | Alternative | Not used, because |
|---|---|---|
| R-1 | Weights outside the Mesh (`Scene.rig` holds `(ObjectId, VertexId) → weights`) | desynchronizes on Undo, Knife checkpoints, rollback and topology edits (AD-025 X-2); the Phase 5 rules would have to be rebuilt for a second store |
| R-2 | One scalar layer per bone (Blender vertex groups) | normalization would be a cross-layer invariant the Core cannot keep per primitive; 4-influence pruning needs all bones of a point at once; N layers per bone count |
| R-3 | Σ = 1 over bones with a mandatory root bone, `()` = unbound | a point between a bound and an unbound point renormalizes to the full bone (§2.1); every mesh would need a root weight on every point |
| R-4 | Bones in object space of the skinned mesh | a rig spans several objects (AD-021 §4.9: body, eyes, teeth) |
| R-5 | Pose and weights as a GPU-only path | SubD, the wire and the flat shading read positions on the CPU (AD-025 §17.1); the CPU arithmetic measures far below the bar (§2.3) |
| R-6 | Bones on the Mesh, listener-copied weights (AD-005, archive "Option C") | AD-025 X-6: one parent is wrong for a blend; listener data lives outside the journal; contradicts AD-021 §4.9 |
| R-7 | Pose mode as a fifth `SelectionMode` in the Core | a Core change with no Core reason; AD-027 §3.1 puts modes into `can_run` |
| R-8 | Copy the Morph Lab's jaw pose (polygroup + rings) | M3; a polygroup is a face-region inference, not weights; the falloff over rings is what Soft Selection already gives, with the radius the artist sets |
| R-9 | Dual-quaternion skinning | the audit names LBS; DQS is an additive mode later if a twist bone shows candy-wrapping |

## 4. Questions to Manu

P1–P4 in the Kurzfassung; each answer is a parameter, none changes the Core design: P1 decides whether `"pose"` is
in the file and whether a rotation is a `RigCommand` (else view state in the controller); P2 whether the morph weight
moves into the file (then also an Undo step per change — a change to the 2026-10-17 decision); P3 whether the skin
stage is in the chain outside mode `5`; P4 the mode's shape (the controller and stage-7 policy are built either way;
"no own mode" would put the bone gesture under `4`).

## 5. Build plan (after the go; each step green on its own)

| Step | Content | Tests (AGENTS.md §8a) |
|---|---|---|
| S1 | Core weights kind (§2.1): validation, combination, canonical form, storage choice by the memory probe, file; weights fixtures for every declared operation (plain and symmetric), mirror copy, Apply transform | `tests/test_point_layers.py`, `test_mesh_change_journal.py` (T-1 oracle with a weights layer), `test_layer_storage.py`, `test_layer_knife.py`, `test_layer_topology_ops.py`, `test_layer_gate.py`; Knife oracle |
| S2 | `BoneId`, `core/rig.py`, `Scene.rig`, version 7, `RigCommand` | new `tests/test_rig.py` (invariants, FK, file round trip bit-exact, old files, invalid files, Undo/Redo); `test_serialization*` |
| S3 | `skinning.py` + `SkinSurface` in the chain (morph → skin → SubD), entry surfaces for other skinned objects; probe rows in `experiments/drag_cost` | new `tests/test_skinning.py` (CPU reference vs. independent `fsum`, order independence, the randomized oracle over pose steps, base edits, topology edits and Undo/Redo, chain = SubD of the skinned mixed cage) |
| S4 | SkeletonController, stage-7 policy, `BoneGesture`, the keys, bone overlay, weight display, HUD row | `tests/test_pose_mode.py`; AD-027 structure checks (E5); keys-free test; the existing scenario suite unchanged |
| S5 | The jaw scenario as acceptance: bone, weights with Soft falloff, one target, pose, Loop Insert at the mouth corner, save → load; automated and as a scripted scenario in `tests/test_interaction_scenarios.py` | the scenario; at the end `pytest tests -q`, GL tests in their own process, `experiments/morph_lab/tests`, `experiments/knife_oracle/tests` |

Documentation in the same commits: AD-025 (Phase 6 implementation note), this AD, CORE_V1_FREEZE §7.1 entries (S1,
S2) and §4, SOURCE_ARCHITECTURE, the ATELIER line. Measurements named as container numbers; the reference-PC run of
the S3 probe stays open for Manu.

## 6. Not in Phase 6

Weight painting brush · editing on a posed mesh and corrective morphs (inverse warping, audit §E) · IK, constraints,
animation (`Scene.animation` stays `null`) · paired left/right bones and mirrored keys · bone rest editing beyond
create / tail / delete · several rigs per scene · DQS · a GPU skinning path (trigger: §2.3) · weights on the morph
editing view · weight transfer between meshes (AD-025 Phase 7).
