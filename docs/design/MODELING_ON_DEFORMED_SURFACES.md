# Modeling on deformed surfaces — product requirement

**Status:** **PROPOSED (2026-11-03), pending Manu's review**, except the first slice: **picking and hover on the
morph mix while editing the base, decided by Manu 2026-11-03 (chat), §15**; **built 2026-11-03 (§15 implementation
note), awaiting Manu's practical test**. The rest
is not decided, not an architecture decision, no Artist verdict, no implementation commitment. Every decided rule it touches stays in force until Manu decides otherwise:
AD-028 §7.1 (S5, "Modellieren nur in Ruhe"), AD-025 §15 (H4/J-5, the target edited beside the base), AD-013 H7-R2
(the replacement surface is display only; amended 2026-11-03 for queries on the morph mix, §15), Morph Lab 6a ("Picking
auf der Ruheform hilft"; superseded for base editing above 0 % by §15).
**Mode (M5):** Discovery: requirement and audit (§0–§14, written without code changes). §15: Production (2026-11-03).
The §6 baseline is the state at `34d2ba2`; §15's implementation note says what changed since.
**Baseline:** branch `claude/vibrant-darwin-yn0uz4` @ `34d2ba2` (clean tree). Every code fact below was read there.
**Tags:** **[V]** verified in code or tests at `34d2ba2` · **[C]** measured in the container (Linux, Python 3.13.18;
a scratch probe outside the repository, not kept, re-runnable from its description in §6.2) · **[B]** read in
Blender's source (GitHub mirror `blender/blender`, `main` @ `097c9f3` = 5.4 alpha; each claim cross-checked on
`blender-v4.5-release` @ `e6e8519` = 4.5 LTS) · **[S]** search-result summary only: the primary page could not be
opened from this environment (Autodesk, Maxon/Pixologic and `docs.blender.org` blocked by the network policy). Treat
these as unverified until someone opens the page · **[H]** estimate or hypothesis.
**Reads with:** [AD-025](../architecture/AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) (origins, point layers, gate,
editing view), [AD-028](../architecture/AD-028-SKELETON-AND-SKINNING.md) (rig, weights, posed refusal),
[AD-013 H7](../architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-16-wp-subd-lab-02-h7--replacement-surface-of-the-edit-mesh-in-viewport)
(replacement surface), [AD-022](../architecture/AD-022-GPU-PICKING.md) (GPU picking),
[CHARACTER_SYSTEMS_RESEARCH Axis 6](../research/CHARACTER_SYSTEMS_RESEARCH.md#axis-6--modeling--articulating-two-phases-or-one-process)
(the artist-side origin of the idea).

## Kurzfassung für Manu (Deutsch)

**Worum es geht:** Du sollst an der Form modellieren können, die du gerade siehst: auswählen, Loops einfügen,
schneiden, auch wenn der Mund per Morph oder per Kiefer-Knochen offen ist. Heute geht das nicht. Die App zeigt die
verformte Form, aber Auswahl, Hover, Knife und alle Werkzeuge arbeiten an der Ruheform. In der Pose lehnt die App
deshalb jedes Verschieben und jede Topologie-Änderung ab (`6` = Ruhe; Gewichte setzen geht). Bei einem eingeblendeten Morph lehnt sie nichts ab: Klicks landen
stillschweigend auf der geschlossenen Ruheform.

**Was schon trägt:** Die verformten Flächen haben dieselben Punkt-Nummern wie das Mesh. Was du auf ihnen triffst,
lässt sich also eindeutig dem echten Mesh zuordnen. Neue Punkte bekommen ihre Morph-Abstände und Gewichte schon heute
korrekt (das ist seit Phase 5 / AD-028 gebaut).

**Was schwer ist:** Beim Morph geht die Rechnung exakt auf: ein Loop, den du am offenen Mund schneidest, sitzt in jeder
Mischung genau auf der Fläche. Beim Knochen nicht. Ein neuer Punkt kann **nicht** zugleich in Ruhe und in der Pose
glatt in der Fläche liegen. Bei einem harten Gewichtsübergang (wie er am Mundwinkel vorkommt) und 25° Kieferöffnung
weicht er um etwa ein Zehntel der Kantenlänge ab, je nach Regel in der Pose oder in Ruhe (an einem Teststreifen
gemessen, §6.2). Blender kennt dasselbe
Problem: Loop Cut warnt dort ausdrücklich, dass es auf einem verformten Mesh „nicht gut funktioniert“.

**Deine Entscheidungen** (je eine Zeile genügt; nichts davon ist eine Technikfrage):

1. **Ziel:** Willst du langfristig *in* der verformten Form Topologie ändern? Oder reicht dir: Auswahl und Anzeige
   stimmen immer mit der sichtbaren Form überein, geschnitten wird in Ruhe, ein Tastendruck dazwischen?
2. **Kiefer offen, Loop schneiden:** Soll der Loop genau dort sitzen, wo du in der Pose geschnitten hast (dann steht
   er in Ruhe evtl. leicht aus der Fläche)? Oder soll er in Ruhe glatt liegen (dann sitzt er in der Pose etwas neben
   der Stelle, die Vorschau zeigt wo)?
3. **Punkt verschieben bei eingeblendetem Ausdruck:** Soll das die Ruheform ändern oder den Ausdruck?
4. **Reihenfolge:** zuerst (a) Auswahl/Hover immer auf der sichtbaren Form (hilft auch beim Gewichte-Setzen in der
   Pose), (b) Topologie auf eingeblendeten Morphs, oder (c) Topologie in der Pose?

**Zur Kenntnis:** Am 2026-10-17 hast du gesagt, Auswahl auf der Ruheform „hilft eher“ (Morph Lab 6a). Am 2026-11-02
hast du „Modellieren nur in Ruhe“ bestätigt (AD-028 S5). Beides gilt weiter. Dieser Vorschlag stellt es für das
langfristige Ziel nur zur Wahl, z. B. als umschaltbaren Bezug.

---

## 0. In one screen

- **Requirement (proposed):** an artist models on the surface the viewport currently shows, including under morph
  targets, skeletal posing and both together. That covers queries (pick, hover, box/lasso, previews) and meaningful
  topology operations. Every result stays coherent with the persistent mesh, morph offsets, skin weights, topology
  provenance and history, in every later state.
- **Three distinct problems**, deliberately kept apart: **(Q) query**: which persistent element is under the cursor
  on the visible surface. **(T) topology placement**: where a new point goes, given that the artist aimed on the
  visible surface. **(M) mapping**: which persistent values (rest position, offsets, weights, regions, UVs) make that
  point coherent in every state. A working (Q) proves nothing about (T) or (M).
- **Main architectural finding [V]:** the evaluated surfaces of morph and skin are `core.Mesh` objects with the
  **edit mesh's IDs and topology** (`MixSurface`, `SkinSurface`). (Q) therefore needs no ID-mapping layer for these
  stages. What blocks it is a decided contract: AD-013 H7-R2 says "display only, no picking", and every query path
  reads `scene.mesh`.
- **Main mathematical finding [C]:** for morph targets (per-point translations) the existing AD-025 origin rules
  commute with the deformation. A point created from affine weights chosen on the *visible* edge or triangle lies
  exactly on the visible surface in every mix (error 2e-15). For linear blend skinning they do not commute: no single
  rest position and weight set puts a new point on the flat surface both at rest and in the pose. Measured
  deviations reach 10.8 % of the edge length at a 25° jaw with a hard weight step, and the inverse can be singular
  (§6.2). **(T)/(M) under skinning need a product rule, not just an algorithm.**
- **Inconsistency today [V]:** posed rig edits are refused because picks would land on the rest cage (AD-028 §7.1). A
  dialled-in morph has exactly the same misalignment but refuses nothing and shows no hint.
- **External practice [B]:** Blender's knife cuts on the deformed cage and maps the hit back by applying the same
  barycentric weights to the original triangle (the rule AD-025 already uses). Its loop cut warns on armature- or
  lattice-deformed display. Its transform corrects through per-vertex deform matrices ("crazyspace") only for
  modifiers shown on cage. Topology editing on deformed surfaces is a partially solved problem in established tools,
  not a solved one (§10).

## 1. Motivation and original intention

- **Project vision** ([PROJECT_VISION](../architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md)): "Model → Add rough rig →
  Test deformation → Notice missing geometry → Return to modeling → Modify mesh → Return to rig / animation →
  Continue"; the system "should remain alive and editable". **Note:** the vision asks for *returning* to modeling
  without destroying work. Mirai delivers that today at rest (AD-025 Phase 5, AD-028 §4 and the jaw scenario). It
  does not by itself ask for modeling *in* the deformed state.
- **The stronger hypothesis** is the artist-side research
  ([CHARACTER_SYSTEMS_RESEARCH, Axis 6](../research/CHARACTER_SYSTEMS_RESEARCH.md#axis-6--modeling--articulating-two-phases-or-one-process)):
  6a "articulation makes topology problems visible" (cheap) and **6b "you change topology in the deformed state and
  continue working"** (strong, expensive). PQ-11 asks: "Can I model meaningfully on the bent state, or does the
  distortion corrupt my judgment?" EX-D is the experiment. The research lists as *genuinely unknown* "whether an
  Artist can actually model well in the deformed state". Behind it is Manu's experience that the correct neutral
  topology "could not be determined with confidence before the first serious articulation".
- **Deferred so far, in three places:** AD-028 §7.1 / X-7 (editing on the posed surface: "Phase 7"), the
  [mesh audit](../research/deformation/MESH_ARCHITECTURE_AUDIT_2026-10-27.md) §E / §G Phase 7 ("inverse warping") and
  the [ROADMAP](../architecture/ROADMAP.md#rigging-foundation) Rigging status ("not yet: … editing on the posed
  surface"). AD-025 §11 keeps "editing on a deformed pose" open.
- **This document** turns 6b into an explicit long-term product requirement, so that a later architecture
  investigation has a target and testable criteria. It does not settle 6b's open question. The requirement is only
  worth building if EX-D-style practice shows that modeling in the deformed state helps (§11 R-1).

## 2. Artist workflows

Each workflow: what the artist does, what Mirai does today **[V]**, what the target asks.

### A. Mouth cavity with an open-mouth morph target

*Artist:* dials "Jaw open" to 100 %, selects faces inside the cavity, inserts support loops around the lip line, adds
loops inside the mouth, adjusts them and judges the result in the open shape, without returning to neutral.

*Today:* faces and wire show the mix (`wire_follows_surface`, `src/viewport/viewport.py:757`). Picking, hover and
box/lasso hit the **rest** cage (`src/mirai/application.py:3630–3730`). Selection and hover overlays are drawn at rest
positions (`viewport.py:726`), so a selection made at 0 % is not visible on the open mouth except through the wire.
A Knife ray hits the rest triangles (`src/mirai/controllers/knife.py:567–576`). Loop Insert, Knife, Extrude and
Collapse **run** and propagate every target exactly by the AD-025 rules
(`tests/test_layer_topology_ops.py:527`, `tests/test_morph_multi.py`), but the artist aims on geometry that is not
drawn there. No refusal, no hint (`src/hud.py` has a pose warning only, `:374`). The workaround is tap `N`
(0 % ↔ last). The editing view (`Tab`) refuses topology (`src/mirai/layer_declarations.py:338`).

*Target:* the cavity faces are selectable where they are drawn. The loop preview and the Knife line lie on the open
mouth. New points land where aimed. All targets, weights and regions follow.

### B. Mouth cavity with a posed jaw

*Artist:* opens the jaw in pose mode and does the same as in A. Later moves the jaw, or returns to rest.

*Today:* every position and topology command on the posed, bound edit mesh is refused before it runs:
"`Loop Insert: the mesh is posed (6 = rest pose)`" (`src/mirai/controllers/skeleton.py:1120–1137`,
`src/mirai/application.py:3103`; `tests/test_application_rig.py:426`, `tests/test_jaw_scenario.py:120–129`).
Selection and weight gestures run, on the rest cage. Only the face shading follows the pose
(`set_cage_source`, `src/mirai/soft_selection/gl_shading.py:14–20`, `tests/test_weight_view.py:271`). The supported
path is `6` → cut at rest → `6`. The new loop then follows jaw and smile by the weights rule
(`tests/test_jaw_scenario.py:152`).

*Target:* the same as A, plus a defined placement rule (§5, §11 R-2): the loop must stay coherent when the jaw moves
and at rest.

### C. Eyelids and surrounding face

*Artist:* closes an eyelid by morph or by a lid bone, then adds or adjusts loops along the visible lid line and the
surrounding orbit. Typical traps: upper and lower lid nearly touching (a pick can hit the wrong lid), a thin
fold where a weight step from 0 to 1 sits on one edge ring, and symmetry between the eyes.

*Today:* as A (morph) or B (bone). No lid-specific behaviour exists. Symmetric weights work only for bones on the
plane (AD-028 §8.4); a lid bone is off-centre, so symmetric weight writing is refused ("needs its mirror bone").

*Target:* as A/B. Picking must resolve the visibly front lid. Symmetric operations use a correspondence of the
reference state, not of the current pose (as ZBrush's poseable symmetry does: see
[SYMMETRY_EVOLUTION_RESEARCH](../research/symmetry/SYMMETRY_EVOLUTION_RESEARCH.md), "Symmetrie am posierten Character").

### D. Morph and skeleton together

*Artist:* a smile target dialled in **and** the jaw open; models at the mouth corner.

*Today:* the evaluation order is **morph → skin → SubD** (`src/mirai/surface_chain.py`; AD-028 §5.2): the smile is
sculpted at rest and rides the pose. The posed refusal of B applies. The morph editing view shows the target at
rest, without the pose (AD-028 §5.2: the view has no layers), so a corrective cannot be shaped in the pose.

*Target:* query on the final morph-plus-skin surface. Placement and mapping through both stages. An explicit
statement of *which* persistent layer a position edit changes (§11 R-3).

### E. Continued modeling after topology changes in a deformed state

*Artist:* after cutting in A–D: back to rest, changes morph weights, changes the pose, cuts again, then Undo and Redo
through all of it, save and load.

*Today, for edits made at rest [V]:* the shown surface is a pure function of the persistent data (drift guard;
randomized oracles `tests/test_morph_multi.py`, `tests/test_skin_stage.py`). Undo/Redo and save/load are exact. Pose
and morph weights are view state outside History (F-11, S4). So E holds today for everything that can be done today.

*Target:* the same guarantees for edits made in a deformed state. A new point's look in *every* other state follows
a stated rule, with no dents or jumps beyond that rule.

## 3. The requirement (proposed)

> **An artist can model directly on the currently evaluated, visible surface of the edit object, also while it is
> deformed by morph targets, skeletal posing or both. This covers selection, hover and every spatial query, and
> meaningful topology operations (at least: Split, Edge Connect, Loop Insert, Knife, Extrude, Inset/Bevel, Collapse,
> Delete/Dissolve). Each result is coherent with the persistent rest mesh, every morph target, the skin weights,
> topology provenance, face data (regions, UVs), symmetry and history: in the state it was made in and in every
> other state the artist can reach afterwards. Where no coherent result exists, Mirai refuses visibly and says why.**

**Not part of this requirement:** sculpting correctives as a feature of its own (it shares §11 R-3, but is its own
product question), bone-driven morphs, animation, transfer between different meshes (AD-025 §11), objects
parented to bones (AD-028 §15), picking on the SubD limit surface (§11 R-9 lists it as a dependency question).

## 4. Functional expectations

| # | Expectation |
|---|---|
| DS-F1 | **Query on the visible surface.** Pick, hover, box, lasso, paint select, occlusion, the Knife's vertex/edge/face targets and every snap use the geometry that is drawn, on the GPU path and the CPU fallback alike |
| DS-F2 | **Aligned display.** Selection, hover, wire, tool previews (Knife line and points, loop/ring previews, Soft bands, the gizmo and its pivot, symmetry seam marks, region tints) are drawn where the visible surface is |
| DS-F3 | **Placement where aimed.** A topology operation aimed on the visible surface puts its new points at a position the artist can predict from the preview. If the committed point will not be exactly where aimed (§5), the preview shows where it will be, before commit |
| DS-F4 | **Coherent persistence.** New and merged points get rest positions and values in every point layer (offsets, weights), regions and UVs by a stated rule. The persistent data stays valid (AD-025 L1–L5, AD-028 W1–W4, `tests/mesh_invariants.py`) |
| DS-F5 | **Explicit edit attribution.** A position edit made on a deformed surface changes one stated persistent quantity (rest shape, the current target, …). Which one is visible to the artist before the edit, never inferred silently |
| DS-F6 | **State continuity.** After any such edit: rest, other morph weights, other poses and further modeling show the evaluation of the persistent data, nothing else |
| DS-F7 | **History.** Every edit is one Undo step. Undo/Redo, tool cancel and rollback (Knife checkpoints, Extrude cancel, Collapse groups) and save/load stay exact. Pose and morph weight stay view state unless Manu changes F-11 / S4 |
| DS-F8 | **Fail-closed.** Where a stage has no usable inverse or the rule has no defined result (§6.2: a singular blend), the operation is refused before any mutation, with a message naming the state and the way out (the AD-025 §4.4 / AD-028 §7.1 pattern) |
| DS-F9 | **Symmetry.** Symmetric operations in a deformed state pair elements through a correspondence of the reference state. The mirror side follows the same placement rule |
| DS-F10 | **Speed.** The H5c / S7 rule: fluid on head and body, "usable, not fluid" on gollum_20k, judged on the reference PC |
| DS-F11 | **Reference on demand.** The artist can still see and pick the rest shape when wanted (Morph Lab 6a: "hilft", seeing how far the shape deviates). Whether that is the default or a toggle is Manu's choice |

## 5. Expected behaviour per deformation

| | Morph targets (`b + Σ wᵢ·dᵢ`) | Skeleton (CPU LBS, AD-028 §5.1) | Morph + skeleton (morph → skin) |
|---|---|---|---|
| Identity of visible elements | same IDs and topology as the edit mesh [V] (`morph_mix.MixSurface`) | same IDs and topology [V] (`skinning.SkinSurface`) | same [V] (the skin stage reads the mix) |
| Query (Q) | well-defined, no inverse needed | well-defined, no inverse needed | well-defined |
| Topology placement (T) by affine origin chosen on the visible geometry | **exact in every state**: new rest = Σ oⱼbⱼ and new offsets Σ oⱼdᵢⱼ give the visible point Σ oⱼpⱼ for any weights [C: 2e-15] | **not exact in both states**: rest-authoritative → the posed point leaves the flat posed edge/triangle; pose-authoritative → the rest point leaves the rest surface [C, §6.2] | inherits the skeleton's case |
| Mapping of layer values (M) | the AD-025 rules unchanged | the AD-028 §3.5 weights combination unchanged; only the *rest position* of the new point is in question | both |
| Position edit by Δ on the visible surface | the visible point moves by Δ whatever the attribution (Jacobian = identity); the attribution (rest vs. target vs. several targets) is a product question; target attribution divides by wᵢ and is undefined at 0 % | Δrest = A⁻¹·Δ with A the point's blended linear part: unique when A is invertible, singular for degenerate blends (§6.2); attribution as for morph once morphs are shown | both questions at once |
| Picking edge cases | the mix can fold the surface (a lid through a lid) | LBS collapse at strong twists; candy-wrapper areas are thin and hard to aim at | — |

**Consequence:** morph-only modeling on the visible surface is a query problem plus an origin computed on the visible
geometry. The AD-025 mapping already exists. Skeleton modeling on the visible surface additionally needs a product
decision about which state is authoritative for placement (§11 R-2).

## 6. Current implementation baseline

### 6.1 Classification

| Capability | Status | Evidence |
|---|---|---|
| Evaluated display: morph mix, skin, SubD as one chain; edit object and the morph base beside its view (H7-E) | **Implemented and verified** | `src/mirai/surface_chain.py`, `morph_mix.py`, `skinning.py`; `tests/test_morph_multi.py`, `tests/test_skin_stage.py`, `tests/test_jaw_scenario.py` |
| Wire follows the evaluated surface | **Implemented and verified** | `src/viewport/viewport.py:506–520`, `:757–763`; `tests/test_morph_targets.py:653` |
| Face shading (Soft preview, weight view, weight gestures) on the evaluated surface | **Implemented and verified** (one overlay) | `src/mirai/soft_selection/gl_shading.py:14–20`, `:121`; `src/mirai/application.py:688`, `:2844`; `tests/test_weight_view.py:271` |
| Selection, hover, edge/face highlight overlays on the evaluated surface | **Not implemented** (deliberately on rest; pinned) — *morph: implemented 2026-11-03, §15.1; pose: unchanged* | `src/viewport/viewport.py:726–736`; `tests/test_morph_targets.py:653`, `tests/test_morph_multi.py:487` |
| Picking (CPU, GPU ID buffers, box, lasso) on the evaluated surface | **Not implemented** (rest cage; H7-R2) — *morph: implemented 2026-11-03, §15.1; pose: unchanged* | `src/mirai/application.py:3630–3730`; `src/viewport/viewport.py:840–851` (the ID pass draws the edit `RenderMesh`); `src/mirai/viewport/gpu_picking.py:36–80`; `tests/test_skin_stage.py:335` |
| Tool previews and spatial queries (Knife target and planner, Soft field and bands, gizmo pivot, transform drag projection) | **Not implemented** (rest) — *morph: implemented 2026-11-03, §15.1; pose: unchanged* | `src/mirai/controllers/knife.py:567–576`; `src/mirai/application.py:2948–2974` (Soft field on `scene.mesh`), `:4067` (gizmo pivot = rest centroid; in pose mode the bone's posed head) |
| Topology operations while a morph mix is shown | **Partially implemented**: run and propagate exactly, aim on the rest cage, no hint | AD-025 §16; `src/mirai/layer_declarations.py:75`; `tests/test_layer_topology_ops.py:335`, `:406`, `:527` |
| Topology and position operations while posed and bound | **Not implemented**: refused (decided, S5) | `src/mirai/controllers/skeleton.py:1120–1137`; `src/mirai/layer_declarations.py:298–313`; `src/mirai/application.py:3103–3109`; `tests/test_application_rig.py:426`, `:447` |
| Topology at rest on a mesh with targets and weights, coherent in every later state | **Implemented and verified** | AD-025 §3/§16, AD-028 §4; `tests/test_layer_knife.py`, `tests/test_weights_topology_ops.py:161`, `:303`; `tests/test_jaw_scenario.py:152`, `:171` |
| Editing a target's shape on an evaluated, ID-identical copy (the editing view) | **Implemented and verified**: shape only, one target at 100 %, at rest, beside the base | `src/mirai/morph_targets.py:205–222` (`TranslatingHistory`), `:281–326` (`TargetView.translate`); `tests/test_morph_targets.py` |
| Shaping a target in the pose (corrective in pose) | **Not implemented** | AD-028 §5.2 (the view has no layers); §15 "bone-driven morphs or correctives" out of scope |
| Weight editing while posed | **Partially implemented**: runs; selection on the rest cage, shading on the pose | AD-028 §7.1; GUI_STAGE1_HUD §8 ("Die Auswahlpunkte bleiben bewusst am Ruhe-Mesh") |
| Inverse deformation for position edits (crazyspace / inverse LBS) | **Documented, not implemented** | audit §E "inverse warping"; AD-028 X-7 |
| Topology changes in the deformed state | **Documented, not implemented** | CHARACTER_SYSTEMS_RESEARCH 6b / EX-D; ROADMAP Rigging status |
| Pose and morph weight as view state; Undo never touches them | **Implemented and verified** | AD-025 F-11, AD-028 §6; `tests/test_jaw_scenario.py` |
| Other bound objects (teeth) showing the pose | **Not implemented** | AD-028 §5.3, F-16 |
| Symmetric topology and weights in an asymmetric pose | **Unknown / requires investigation** | AD-028 §8.4 (on-plane bones only); no test in a pose |
| Picking cost on a surface that changes every pose step | **Unknown** (unmeasured) | — |

### 6.2 Measurement: an edge split on a deformed mesh [C]

Probe (scratch, not kept; re-runnable from this description): a vertical strip of 8 quads in front of a hinge at
the origin (x ∈ {0, 0.2}, y from 0 to −1, z = 1), one jaw bone (head at the origin, tail (0, −1, 1)), a rotation about
X; every vertical edge split at t = 0.5 through the real `Mesh.split_edge` (the Core's AD-025/AD-028 rules), the
posed surface from the real `skinning.evaluate`. "Off" = distance of the evaluated new point from the midpoint of
the evaluated edge ends (where the artist aims), relative to the edge length. "Pose-authoritative" = the rest
position M⁻¹(aimed point) under the new point's own blended transform, and its distance from the rest edge. Morph:
one vector target with random offsets at 60 %.

| Case | 10° | 25° | 45° | 90° | 180° |
|---|---|---|---|---|---|
| Morph (any angle irrelevant), new point off the visible midpoint | 2e-15 | | | | |
| Skin, linear falloff over 8 edges: rest-authoritative off in the pose | 0.5 % | 1.4 % | 2.4 % | 4.4 % | 6.2 % |
| … pose-authoritative off the rest edge | 0.5 % | 1.4 % | 2.6 % | 6.2 % | 50 % (near-singular blend) |
| Skin, hard step (weight 0 → 1 across one edge): rest-authoritative off in the pose | 4.4 % | **10.8 %** | 19.1 % | 35.4 % | 50 % |
| … pose-authoritative off the rest edge | 4.4 % | 11.1 % | 20.7 % | 50 % | **singular** (no inverse) |

**Reading.** The algebra is the covariance term Σⱼ oⱼ(Mⱼ − M̄)(bⱼ − b̄): it vanishes when the corners share one
transform (morph: a translation per point, M = I) and grows with the weight difference across the edge and the angle.
A hard falloff at the mouth corner (AD-028 §8.4 lets the artist set exactly that) is the worst realistic case. This
holds for any affine placement rule, so the same holds for Knife interior points and Collapse averages. A Loop Insert
in the pose is therefore always one of: "where aimed in the pose", "flat at rest", or a compromise. That choice
belongs to the artist (§11 R-2).

### 6.3 Where the separation is enforced today [V]

1. **The contract:** AD-013 H7-R2, "the surface is derived and never written back; no picking, no History, no
   document state"; restated in `surface_chain.py` ("the viewport never picks on a replacement surface") and the
   `morph_targets.py` / `skinning.py` docstrings.
2. **Every query reads `scene.mesh`:** `Application._pick`, `_gpu_pick`, `_elements_in_rect`, `_elements_in_polygon`
   (`application.py:3630–3730`). The GPU ID pass renders `Viewport.render_mesh`, the edit mesh
   (`viewport.py:840–851`). The Knife controller's `knife_pick` (`controllers/knife.py:567–576`). Soft fields
   (`application.py:2948–2974`). The gizmo pivot (`:4067`).
3. **Overlays read `Viewport.mesh`:** `_sync_selection_overlays` (`viewport.py:726–736`). Exceptions: the wire
   (`_wire_mesh`, `:757`) and the face-shading sink (`set_cage_source`).
4. **Edits while posed:** stage-7 policy `posed_refusal` over `layer_declarations.edits_positions_or_topology`
   (unknown keys count as editing) and the host entry `apply_mesh_change`.
5. **Edits on the editing view:** `layer_declarations.view_refusal` (topology refused) and the backstop in
   `TargetView.translate` (a non-position change is undone, nothing kept).
6. **Not enforced:** a dialled-in morph mix. Edits run against the rest cage under a deformed display.

## 7. Acceptance criteria (for a later implementation; none is met today unless stated)

Testable headless with the AD-027 scenario driver and the existing oracles, unless marked [RPC] or [Artist].

| # | Criterion |
|---|---|
| DS-AC1 | With a deformation shown, for every component mode and on the GPU and CPU paths, the picked element is the one whose **drawn** geometry is under the cursor, including occlusion by the drawn surface. A pick test on a surface where rest and drawn positions differ by more than the pick radius distinguishes them (today's tests would fail it, by design) |
| DS-AC2 | Every overlay drawn for the edit mesh (selection, hover, edge/face highlight, Knife, loop previews, Soft bands, gizmo pivot, seam marks) lies on the drawn surface: positions equal the shown cage's within 1e-9. Today met for the wire and the face shading only |
| DS-AC3 | **Morph:** Split, Edge Connect, Loop Insert, Knife (open, closed, self-crossing), Extrude, Inset/Bevel and Collapse aimed on a surface with several targets dialled in: each new point lies on the drawn surface where aimed (≤ 1e-9 relative), every target follows the AD-025 rule, and at 0 % the point lies on the rest face it was cut in. Undo/Redo exact. Plain and symmetric |
| DS-AC4 | **Skeleton and combined:** a placement rule chosen by Manu (§11 R-2) holds within 1e-9 in the state it names, and the deviation in the other states is reported. The pre-commit preview shows the post-commit position in the current state (no jump > 1 px). Plain and symmetric (on-plane bones) |
| DS-AC5 | **Continuity:** after any edit of AC3/AC4, through random sequences of rest toggles, morph weight steps, pose steps, further edits and Undo/Redo, the shown surface equals the evaluation of the persistent data bit-exactly (`morph_mix.evaluate`, `skinning.evaluate`), and AD-025 L1–L5 / AD-028 W1–W4 hold after every step |
| DS-AC6 | **History and file:** one Undo step per edit; Undo to the start and Redo to the end exact against the snapshot oracle; tool cancel and rollback exact; save → load bit-exact; pose and weights unchanged by Undo (as long as F-11 / S4 stand) |
| DS-AC7 | **Position attribution:** a position edit on a deformed surface changes exactly the persistent quantity shown as its target (DS-F5) and nothing else (all other layers bit-identical) |
| DS-AC8 | **Fail-closed:** an edit whose rule has no result in the current state (a singular blend, an attribution undefined at 0 %) is refused before any mutation (mesh, history, selection unchanged; status names the state and the way out). Every command the gate classifies as editing is enumerated (the `edits_positions_or_topology` pattern) |
| DS-AC9 | **The jaw scenario in the pose:** the AD-028 T-7 scenario with Loop Insert done *in the pose*: the loop follows the decided rule; jaw, smile and weights stay coherent at rest, in the pose and through save/load |
| DS-AC10 | **Speed [RPC]:** hover pick and a pose or weight step with visible-surface queries meet the H5c/S7 bar (16.7 ms p95) on head_basemesh and Man_With_Shoes; gollum_20k measured and reported |
| DS-AC11 | **Artist [Artist]:** workflows A–E (§2) as practical tests; in particular whether working in the deformed state helps or harms judgment (PQ-11) |

## 8. What can be reused

- **ID-identical evaluated meshes** (`MixSurface`, `SkinSurface`; AD-025 §17.1, AD-028 §5.2): a hit on them is a valid
  persistent `VertexId`/`EdgeId`/`FaceId`. The CPU picking functions are mesh-parametric (`pick_component`,
  `face_hit`, `triangle_origin` take the mesh to test, `src/mirai/viewport/picking.py:297–345`, `:514`). The viewport already
  owns a `RenderMesh` of the surface (`surface_render_mesh`) next to the one the GPU ID pass draws [V]. Whether the ID
  pass can render that surface with its per-element IDs is unverified [H].
- **The cage-source pattern** (`GLSoftShadingOverlay.set_cage_source`, `Application._shown_cage`): topology from the
  edit mesh, positions from the shown cage, a watch for pose steps. It is the precedent for DS-F2 and was itself a
  fix for a found misalignment (GUI_STAGE1_HUD §8: "69 von 69 Overlay-Punkten auf Ruhepositionen").
- **AD-025 origins at the pick:** the Knife already computes barycentric weights on the hit triangle and carries them
  to the camera-free resolver (`picking.face_hit`, AD-025 §16.1). Computed on the visible triangle they give the
  exact morph result of §5. This is the same rule Blender's knife applies from its cage ([B], §10).
- **The editing view's choke point** (`TranslatingHistory.push` → `TargetView.translate`): edits on a derived,
  ID-identical mesh become one journaled write into persistent layers, with a fail-closed backstop. It shows that
  "every tool runs unchanged, one boundary translates the result" is workable in this codebase. Its limits: shape
  only, one target at 100 %, at rest, an exact trivial inverse (`d = p − b`).
- **The journal and the drift guard:** the evaluation is a pure, incrementally patched function of persistent data.
  DS-AC5 can reuse the existing randomized oracles.
- **The gate's classification** (`edits_positions_or_topology`, the command and method enumeration): the list of
  everything a visible-surface mode would have to cover or refuse.
- **SubD's stable provenance keys** (`src/mirai/subdivision/preview.py`), should picking on the SubD surface become
  part of the target (§11 R-9).

## 9. Capabilities any solution must provide (not a design)

1. **Visible → persistent identity** for each stage in the chain, including stages that do not keep IDs (SubD), or a
   stated refusal for them.
2. **Query on what is drawn**: GPU and CPU, occlusion by the drawn surface, folded and self-intersecting surfaces.
3. **A placement rule per stage kind** and its stated error in the other states (§6.2); a preview that shows the
   committed position.
4. **Value propagation** for every per-point and per-corner datum: offsets, weights, regions, UVs, masks, symmetry
   seam. Today's AD-025 / AD-028 rules cover the values. Only the rest position under nonlinear stages is new.
5. **Edit attribution** for position edits: which layer changes, with which inverse, and what happens at weights near
   0 and at singular blends.
6. **Inverse handling** where an inverse is needed: existence, uniqueness, conditioning, and a fail-closed path.
7. **Multi-stage composition**: morph → skin → (SubD), in Mirai's order, and future stages (correctives, deformers).
8. **Alignment** of every overlay and preview, on every trigger the viewport already has (H1 triggers plus pose and
   weight steps).
9. **History exactness** unchanged (AD-023 contract): no new state in History beyond what the edit writes.
10. **Cost** bounded per pose step: pick caches and screen grids that today assume a still cage (`PickCache`) would
    be invalidated by every pose step.

## 10. External DCC comparison

| Application · version · source | What is supported | Limits and exceptions |
|---|---|---|
| **Blender**: shape keys · 5.4 alpha / 4.5 LTS · `bmesh_mesh_convert.cc:18–60` [B] | "Editmode operations when a shape key-block is active edits only that key-block". Editing a Basis "will apply offsets to those shape keys using this as their Basis". New vertices get every key's value by custom-data interpolation (`CD_SHAPEKEY` has `layerInterp_shapekey`, `customdata.cc:1741–1748`) [B]. UI: "Solo Active Shape Key: Only show the active shape key at full value", "Shape Key Edit Mode: Display shape keys in edit mode (for meshes only)" (`rna_object.cc:3714–3724`) [B]. The manual reportedly says the current blend becomes editable with it [S] | **If the edit session created vertices, a Basis edit is not propagated to the other keys at all**: "If there are new vertices in the mesh, we can't propagate the offset … creating a mess when doing e.g. subdivide + translate" (`bmesh_mesh_convert.cc:957–963`; 4.5 LTS `:830`) [B]. Applying a geometry modifier to the mesh data is refused while the mesh has shape keys ("Modifier cannot be applied to a mesh with shape keys", `modifier_apply_obdata`, `object_modifier.cc:1067–1069`; "apply as shape key" is a separate path, `:861`) [B] |
| **Blender**: modifier "On Cage" · same · `rna_modifier.cc:11575–11581`, `modifier.cc:476–526` [B] | "On Cage: Adjust edit cage to modifier result". Edit-mode display and selection use the cage up to the last on-cage modifier. Armature supports edit mode and edit-mode deform matrices (`MOD_armature.cc:251–260`) [B] | The cage stops at the first modifier that does not support mapping (`modifier.cc:519–521`) [B]. That is a general limit for generative modifiers. The on-cage state is per modifier and set by the user |
| **Blender**: crazyspace in transform · same · `transform_convert_mesh.cc:1336–1377`, `crazyspace.cc:225–260` [B] | Only when a modifier is on cage: per-vertex deform matrices from the stack's leading deform-only modifiers, quaternion correction for the rest; the transform maps through the inverse (`invert_m3_m3`). Sculpt mode has its own variant (`BKE_crazyspace_build_sculpt`) [B] | The quaternion correction after modifiers without deform matrices is a rotation between the original and the deformed local triangle frame (`set_crazy_vertex_quat`), not the deformation itself; it is compiled out when no leading modifier supplies matrices: "TODO: fix crazy-space & extrude so it can be enabled for general use" (`:1363`; 4.5 LTS `:1357`) [B]. Off when nothing is on cage |
| **Blender**: knife on a deformed cage · same · `editmesh_knife.cc:111–121`, `:2494`, `:2509`, `:3884` [B] | Rays hit the **cage** triangles (deformed coordinates); every knife vertex keeps `co` (original) and `cageco` (cage); a face hit is mapped back by applying the **same barycentric UV** to the original triangle's corners [B] | This is the rest-authoritative affine rule: under an armature the committed point is not where the cut was drawn on the deformed cage (the effect measured in §6.2). The knife source has no warning for a deformed cage (no `RPT_WARNING` in `editmesh_knife.cc`) [B] |
| **Blender**: loop cut on a deformed display · same · `editmesh_loopcut.cc:138–150`, `:395–399` [B] | The preview ring is drawn at deformed coordinates (`BKE_editmesh_vert_coords_when_deformed`) [B] | Interactive use warns: **"Loop cut does not work well on deformed edit mesh display"** when the object is deformed by a lattice or an armature (4.5 LTS `:390`) [B] |
| **Maya**: Shape Editor and Pose Editor · 2016–2025 docs · [Edit target shapes](https://help.autodesk.com/cloudhelp/2019/ENU/MayaLT-CharacterAnimation/files/GUID-5785515C-0ED6-4FAF-88E2-3C66F21A476E.htm), [Pose Editor](https://help.autodesk.com/cloudhelp/2025/ENU/Maya-CharacterAnimation/files/GUID-2AB6C4C3-75AC-4094-A65C-C232739AFB30.htm) [S] | Shape Editor "Edit" sculpts a target, stored as the difference from the base. Corrective shapes on a posed skin through the Pose Editor; post-deformation targets in Tangent or Transform space keep a corrective correct when the base deforms [S] | Reported: a deformer (e.g. a lattice) cannot modify the base and transfer that edit to a target [S]. Topology changes after skinning: community threads describe duplicate-edit-copy-weights workflows and new vertices without influence ([polycount](https://polycount.com/discussion/comment/2680601), [SimplyMaya](https://simplymaya.com/forum/showthread.php?p=355684)) [S, community, weak] |
| **3ds Max**: Skin modifier and stack · [Skin parameters](https://help.autodesk.com/cloudhelp/2025/ENU/3DSMax-Modifiers/files/GUID-0D847E14-366A-4629-A87A-D24CAF591226.htm) [S] | Moving vertices below Skin is reported to work; "Show End Result" displays the stack result while editing below [S] | Community answers: Skin depends on vertex order, so adding or deleting vertices below Skin breaks the weights; the workaround is a copy plus SkinWrap ([Autodesk forum](https://forums.autodesk.com/t5/3ds-max-modeling-forum/help-with-show-end-result/m-p/6381155), [polycount](https://polycount.com/discussion/comment/1755928)) [S, community, weak] |
| **ZBrush**: Transpose Master, morph targets, layers · forum threads [S] | Posing a merged low-resolution proxy and transferring the pose back (`TPose > SubT`) [S] | Reported: transfer back needs unchanged topology and point order; a topology change prompts "transfer details or delete" ([ZBrushCentral](https://zbrushcentral.com/t/transpose-master-tpose-sub-t-destroys-a-subtool/309743), [ZBrushCentral](https://www.zbrushcentral.com/t/topology-changed-during-transpose-answered/295616)) [S, community, weak]. Poseable symmetry for sculpting in a pose: see [SYMMETRY_EVOLUTION_RESEARCH](../research/symmetry/SYMMETRY_EVOLUTION_RESEARCH.md) |

**Reading.** Blender, the only tool verified at source level here, separates the cases exactly as §0 does.
Query and display on the deformed cage work (on cage). Transforms are corrected through deform matrices (crazyspace).
Topology tools either map back with the rest-authoritative barycentric rule (knife) or warn (loop cut). Shape keys
lose Basis propagation as soon as topology changes in the same session. The verified evidence therefore does not
show an established tool that makes topology editing on a posed surface coherent across states. Mirai's ID-identical
evaluated meshes, its applied origins and its exact journal are a plausible basis for a *more coherent* workflow
(e.g. Basis propagation that survives new vertices, which AD-025's relative targets already give). This is an
opportunity to investigate, not a claim of being first: Maya, 3ds Max and ZBrush were only seen through search
summaries, and other tools were not examined.

## 11. Known limitations, risks and open questions

| # | Question / risk | Why it matters |
|---|---|---|
| R-1 | **Does modeling in the deformed state help at all?** (6b, PQ-11) | The research marks it unknown; distortion may corrupt judgment. A cheaper answer to Manu's underlying need (seeing problems early, 6a) already exists: the one-key rest ↔ pose toggle plus DS-F1/F2 alignment. The requirement is only worth its cost if practice says so |
| R-2 | **Authoritative state for placement under skinning** (rest, pose, or a compromise) | No affine rule lies flat in both (§6.2). Each choice produces a visible artefact in the other state. Product truth: Manu's |
| R-3 | **Attribution of position edits** with several active layers (rest vs. current target vs. a corrective in the pose) | Non-unique by construction. Target attribution divides by the weight (undefined at 0 %). Interacts with H4/J-5 ("daneben") and AD-025 J-3 ("relativ"). A UI state must say what is edited |
| R-4 | **Singular and ill-conditioned inverses** | Half-weighted points under ~180° twists have no inverse [C]; near-singular blends amplify small mouse moves; DS-F8 must refuse them |
| R-5 | **Contradiction with decided verdicts** | Morph Lab 6a (picking on rest "hilft", 2026-10-17), AD-028 S5 (modeling only at rest, 2026-11-02), AD-013 H7-R2 (display only). A long-term change of any of them is Manu's decision and, for H7-R2 and S5, needs its own AD (AGENTS §5) |
| R-6 | **Geometry-dependent tools** | Inset/Bevel widths, Extrude direction, Smooth/Relax, Loop Slide and the Knife planner compute from positions. On a posed surface "the same" width or direction means different rest values. Each needs its own stated rule |
| R-7 | **Today's silent morph case** | A dialled-in mix accepts edits aimed on the rest cage without a hint, the failure AD-028 §7.1 refuses for poses. Worth Manu's attention independently of the long-term target (a hint or refusal would be a small, separate decision) |
| R-8 | **Only the edit object shows the pose** (F-16) | In workflow B, teeth and tongue as separate objects stay at rest. Modeling the cavity against them is misleading until per-object evaluated display exists |
| R-9 | **SubD on top** | With SubD shown, the visible surface is not the cage. Picking the limit surface maps to cage elements only through SubD provenance (not IDs). Is "the visible surface" the cage-on-pose or the smooth surface? |
| R-10 | **Symmetry in an asymmetric pose** | Correspondence must come from the rest state; off-centre bones have no mirror yet (AD-028 §15). Untested |
| R-11 | **Cost** | Visible-surface picking invalidates the pick cache on every pose step; the per-vertex viewport patch is already the bottleneck (AD-025 §17.3, AD-028 §5.4); Loop Insert on gollum_20k costs ≈ 3 s at rest (AD-025 §16.3) |
| R-12 | **Drawn triangulation differs between states** | The viewport ear-clips each face on its own Newell dominant plane (AD-025 F-5); a warped quad can split along the other diagonal in the pose, so a barycentric origin taken in the pose lies on a rest triangle that is not drawn at rest (as already seen for the mirror side, AD-025 §16.2) |

## 12. Dependencies on existing architecture

AD-013 H7 (R2 "display only", R4 one provider, H7-E) · AD-022 (GPU ID buffers draw the edit `RenderMesh`; occlusion) ·
AD-023 (journal, exactness contract) · AD-025 (§4.1 origins, §4.4 gate, §15 editing view H4, §17 chain and drift guard)
· AD-027 (stage-7 policies, gesture sessions) · AD-028 (§3.5 weights combination, §5 evaluation order, §6 pose as view
state, §7.1 S5 refusal, X-7 / X-8) · AD-SYM-03 / AD-SYM-04 (symmetric coordination) · CORE_V1_FREEZE (the Core rules
for values already exist; whether a rest-position rule for nonlinear stages touches the Core is unknown [H]) ·
REFERENCE_HARDWARE (DS-AC10).

## 13. Long-term target and possible delivery stages

The long-term target is §3. Possible stages, each separately useful and each with its own Artist decision. This is
not a plan; the order is Manu's (Kurzfassung question 4):

| Stage | What the artist gets | Covers | Needs first |
|---|---|---|---|
| 0, today | cut at rest, see the pose with one key; values propagate exactly | E at rest | — |
| 1, aligned query | selection, hover and overlays on the visible surface (also for weight setting in the pose); edits still at rest / refused in the pose | DS-F1, F2, F11; AC1, AC2 | a review of H7-R2; Manu on 6a (default or toggle) |
| 2, morph modeling | topology on a dialled-in morph, exact (§5) | A, C (morph); AC3, AC5, AC6 | stage 1; R-3 for position edits |
| 3, posed topology | topology in the pose under a chosen placement rule with an honest preview | B, C (bone), D; AC4, AC9 | stage 1; R-2; a change of S5 (own AD) |
| 4, posed shaping | position edits and correctives in the pose (inverse deformation) | D; AC7, AC8 | R-3, R-4; the audit's Phase 7 |

## 14. Recommended next step

After Manu's answers to the Kurzfassung, and only if question 1 is "yes, in the deformed state", or stage 1 is
prioritised: **a separate architecture investigation, in a fresh session**, scoped to:

1. Whether H7-R2 can be lifted for *queries only* (surfaces stay never written back, never in History). Measure GPU
   ID-pass picking on `surface_render_mesh` versus the edit `RenderMesh`, and the `PickCache` cost per pose step, on
   head, body and gollum_20k (container first, then the reference PC).
2. For stage 2, whether an origin computed on the visible triangle or edge can travel through the existing Knife,
   Split/Connect and Loop Insert paths unchanged, with a T-1-style oracle for DS-AC3.
3. For stage 3, a small probe of placement rules (rest-authoritative, pose-authoritative, a blend) on head_basemesh
   and gollum_20k with real AD-028 falloffs, reporting the §6.2 deviations at the mouth corner and eyelid, as input
   for Manu's R-2 answer.
4. An independent review before any AD that changes H7-R2 or S5 (AGENTS §6: hard to reverse, changes product
   behaviour).

Suggested: Claude Opus, effort high, a fresh session (Erzeuger ≠ Bewerter for the later review).

## 15. Decided first slice: picking on the morph mix (Manu, 2026-11-03)

**Manu (chat, entered by the agent):** „wenn beim Morphing das Hover/Picking direkt auf den gemorphten Zustand wirken
würde, zB BaseEditing Mode aber 50% oder 100% geöffneter Mund, dann würde das ja schon das Problem lösen. Ein
Split/Cut o.ä wird ja sowieso direkt auf dem gemorphtem Zustand sichtbar, auch wenn man eigentlich das Base mesh
editiert. Also würde ich tatsächlich jetzt in einem frischen Session genau dieses Problem beheben, dass wenn zB. 100%
gemorphed ist, man auch in diesem Zustand hovert und selektiert und das richtige trifft.“
This answers Kurzfassung question 4 for the morph case (stage 1 + 2 of §13, morph only). Mode (M5): Production, in a
fresh session with this section as the handoff.

**Reading of the decision** (`PROVISIONAL`, Manu corrects in one sentence):

- (a) **Base editing stays.** Every edit changes the base (rest positions); the offsets stay as they are (AD-025 J-3,
  C-1). Move shows exactly on screen (the morph moves each point by a constant offset). Rotate/Scale turn the rest
  positions while the offsets keep their direction (C-1), so a region with large offsets does not turn rigidly on
  screen. Known, not changed here.
- (b) **Morph only.** In a pose nothing changes: S5 refusal, selection on the rest cage (AD-028 §7.1).
- (c) **No rest-picking toggle.** Tap `N` (0 % ↔ last) is the rest reference. Morph Lab 6a ("Picking auf der Ruheform
  hilft") is superseded for base editing at a weight above 0.
- (d) **SubD on:** picking on the mixed cage (what the cage lines show), not on the SubD surface.
- (e) **The editing view (`Tab`) unchanged:** it already is the edit object at `b + d`.

**Scope.** With a target dialled in on the edit object: hover, click, box, lasso and paint select (GPU and CPU, with
occlusion by the drawn mix), the Knife's targets and its planner, and the overlays (selection, hover, edge/face
highlights, Knife and loop previews, Soft bands, gizmo pivot, symmetry marks) work on the drawn mix. Also every
screen↔world mapping a drag uses (W/E/R, Tweak, Extrude drag plane). A cut, a loop or a selection made at 50 % or 100 %
lands on the element drawn under the cursor. At 0 % and without targets the behaviour is bit-identical to today.
**Not in scope:** the pose, attributing position edits to a target, picking the SubD surface, other objects.

**Verified leads** (facts at `34d2ba2`, not a design; the session chooses the mechanism):

- The drawn mix is `morph.provider.surface_mesh` (`morph_mix.MixSurface`), a `core.Mesh` with the edit mesh's IDs and
  topology, patched in place. `Application._shown_cage` (`application.py:2844`) returns the **skin** surface when posed,
  so it does not fit (b) as it is.
- The CPU pickers take the mesh to test (`mirai/viewport/picking.py`). `PickCache` keys on `id(mesh)` and watches the
  mesh it is given (`picking_cache.py:119–135`, `:286–289`). The GPU ID pass draws `Viewport.render_mesh`, the edit
  mesh (`viewport.py:840–851`). `GpuPicker.can_pick` checks only the store type and camera uniforms
  (`gpu_picker.py:117`), so a surface `RenderMesh` may qualify [H, unverified].
- Overlays read `Viewport.mesh` (`viewport.py:726–736`); the wire already reads `_wire_mesh()` (`:757`).
- Knife: an edge `t` means the same on the mix and on the base (straight edges). An interior point's position must
  reach `split_face` as its **rest** position, Σ oⱼ·bⱼ from its origin; at the hit point Σ oⱼ·pⱼ equals the hit. The
  planner reads mesh positions with the camera (`controllers/knife.py:567–576`). The kept-call report
  (`KeptSplitEdge` / `KeptSplitFace`, `topology/knife_resolve.py:140`, `:155`) and its symmetric replay
  (`symmetric_knife.py:286–371`) already resolve on one side and replay on another.
- Drag depth and pivot read rest positions: `move.py:308` (anchor), `selection_pivot` (`selection_helpers.py:119`),
  `Application._gizmo_pivot` (`application.py:4067`). The Soft field is computed on the rest mesh
  (`application.py:2948`; keeping it intrinsic is fine); its bands are drawn at rest.
- Decided text that changes with this slice, in the same commit (AGENTS §5): AD-013 H7-R2 ("no picking"; an addendum
  allowing queries on a replacement surface with the edit mesh's IDs, never written back), AD-025 §6 / §15.1 item 4,
  the `morph_targets.py` and `surface_chain.py` docstrings. Tests pinning the old behaviour change with it:
  `tests/test_morph_targets.py:653`, `tests/test_morph_multi.py:487` (`tests/test_skin_stage.py:335` stays, (b)).

**Acceptance:** DS-AC1 and DS-AC2 for the morph mix (a test where rest and mix differ by more than the pick radius;
GPU path in the GL tests); DS-AC3 through real picks for Split, Edge Connect, Loop Insert, Knife (open, closed,
self-crossing), Extrude and Collapse, plain and symmetric; DS-AC6; 0 % / no-target equivalence; hover-pick and
weight-step cost measured with the existing probe (container, plus the line for the reference PC). Runs per AGENTS
§8a: `tests/` fully, GL tests in their own process, `experiments/morph_lab/tests`, the Knife oracle. Done also means
an implementation note here, the AD amendments, `docs/ATELIER.md` and a short German practical test for Manu
(head_basemesh, a "mouth open" target at 50 % and 100 %: hover, select, Loop Insert, Knife inside the mouth).

### 15.1 Implementation note (2026-11-03)

Built on `main` @ `2ce1132` (contains this section). Reading (a)–(e) unchanged, `PROVISIONAL` as above.

**Mechanism — one query cage, read only.** `Application._query_cage` names the cage: the edit object's mix
(`MorphSurfaceProvider.mix_of`) while one of its targets is above 0 % and the chain shows the morph stage; None at 0 %
(also when the mix is kept at 0 % for SubD), without targets, while the skin stage shows the edit object posed (b), on
the editing view (e: its mesh has no targets, it already is `b + d`) and while a foreign host holds the slot. The viewport
takes it as its **cage source** (`Viewport.set_cage_source`, the AD-013 H7-R2 addendum): selection / hover / edge / face
overlays, the wire and opt-in extra overlays (`follows_cage`: Soft bands, mask points; the symmetry markers through their
own `cage` callable — the report and the plane stay the base's) read the cage; the GPU ID pass draws it
(`gpu_pick_mesh`: the morph surface's own `RenderMesh`, or under SubD a never drawn `RenderMesh` of the mixed cage, (d));
`sync_cage()` brings provider and cage up to date for a pick between an edit and the next frame. `Application._query_mesh`
(= `AppServices.query_mesh`) is the mesh every query reads: CPU and GPU hover / click, Box, Lasso, Paint, the Box start
decision, the region click, the gizmo pivot, the Knife (pick, own-point snap, planner, preview), Extrude, Move / Tweak,
the Rotate dial, Inset / Bevel width per pixel, Loop / Vertex Slide screen directions. Every write goes to `scene.mesh`.

- **Drag mappings.** A base edit moves a drawn point by its rest delta (the mix adds a constant offset per point), so
  each gesture fixes the rest → drawn shift at its start: Move / Tweak map pixels at the drawn anchor's depth (exact on
  screen; tested), Extrude at the drawn region's centre, the Rotate dial turns about the drawn centroid (the rotation
  itself stays about the rest pivot, reading (a)), Inset / Bevel measure the width per pixel at the drawn anchor, Loop and
  Vertex Slide project the drawn ends. Scale is pixel-based (no mapping). Absent a cage the payloads are unchanged.
- **Knife.** `KnifeTool.set_geometry(cage)` (the controller passes the live query mesh before every hover / click plan):
  every click-time rule (margins, chords, the planner, the preview) reads the drawn positions; topology and IDs are the
  edit mesh's. An edge record's `t` means the same on both meshes; a face record keeps its hit position on the mix and
  its origin (barycentric weights of the drawn hit triangle). At commit (`_rest_path`) each interior point becomes its rest
  position Σ oⱼ·bⱼ (the same copy where a record recurs, e.g. a closed chain's seed), so the Core's origin rule gives it
  offsets whose mix is exactly the aimed point; a self-crossing point is the resolver's blend of its stretch ends (affine
  inside one triangle, AD-025 §16.2). The symmetric session view and the commit coordinator get the rest path.
- **Hide on the mix:** when the morph surface is the cage it gets the edit mesh's hidden set (drawn and picked like the
  edit mesh). Before, hidden faces stayed drawn on the mix (found here).

**Limits (known, not changed):** Rotate / Scale turn rest positions about a rest pivot, so a region with large offsets
does not turn rigidly on screen (C-1, reading (a)); normal-space constraints and Extrude directions are the rest normals;
the Working Pivot is a free point in object space placed and drawn at rest; the symmetric Knife's mirror preview is the
mirror image of the drawn working side (exact for a symmetric target; with an asymmetric one it can lie off the drawn
mirror side — the commit is exact); a warped quad can triangulate along the other diagonal on the mix (R-12); the
Re-Symmetrize preview and the plane outline stay on the base; posed: everything as before (b).

**Tests.** `tests/test_morph_picking.py` (42, headless CPU picker): DS-AC1 — every vertex / edge / face hovered at its
drawn anchor at 50 % and 100 %, the cursor at the rest anchor gets what is drawn there (an independent mesh at
`morph_mix.evaluate` positions as the oracle), a 154-cursor sweep over the cube equals the oracle with occlusion in every
mode, an element hidden behind the drawn mix is not picked, hidden vertices are not picked; Box / Lasso / Paint select the
drawn elements (and not the rest-shape ones); DS-AC2 — selection points, hover / selection lines, face highlights, wire,
gizmo pivot (also after a weight step), Soft / mask overlays (`follows_cage`) and the symmetry markers on the drawn cage
(≤ 1e-9); the Knife's placed points under their clicks on the drawn mix; Move keeps the drawn point under the pointer,
also with a target that pushes it towards the camera; DS-AC3 / DS-AC6 through real clicks on the mix — Split, Edge
Connect, Loop Insert, Collapse, Extrude, Inset, Bevel, plain and symmetric (AD-025 rule, mirror, L1–L5, the shown mix =
the definition before and after Undo / Redo, Undo / Redo exact) and the Knife open, closed and self-crossing, plain and
symmetric (each interior point drawn where aimed ≤ 1e-9, the rule on the rest path); 0 % — a target at 0 % (also back
from 60 %, also under SubD with the mix kept) hovers, draws and places the gizmo bit-identically to no target; posed —
the rest cage, the mix again at rest. `tests/test_gl_morph_picking.py` (14, GL, compact and slot layouts): the ID pass
draws the mix (face IDs at pixel centres = the CPU oracle, ≥ 20 pixels differ from the rest shape), vertex / edge hover
and Box agree with the oracle, a pick right after a base edit with no frame in between, under SubD the never drawn cage
`RenderMesh` (also after a weight step), 0 % draws the edit mesh. Changed with the decision: `test_morph_targets.py`
(the wire *and the selection* follow the mix), `test_morph_multi.py` (morph + SubD: selection on the mixed cage; the
Knife with three targets aims on the mix). `tests/test_skin_stage.py:335` (posed, rest) unchanged and green.
**Mutation checks by hand**, each caught: no cage, the Knife cutting the mix positions into the base, Move mapping at the
rest depth, the cage kept in a pose, overlays at rest, a cage at 0 % under SubD.

**Measured [C]** (container, Linux, Python 3.13, Mesa llvmpipe; `xvfb-run -a python experiments/drag_cost/probe_morph_gl.py
--only-picking`; one target, offsets on 100 % of the points; hover = `pointer_motion` + the frame over 120 cursors, GPU
path; p50 / p95 ms, before = the same probe on `2ce1132`):

| Asset | hover V / E / F at 60 %: before (rest) | after (mix) | weight step, 40 vertices selected: before | after |
|---|---|---|---|---|
| head_basemesh (326 V) | 0.24/0.48 · 0.27/0.51 · 0.18/0.31 | 0.23/0.55 · 0.26/0.73 · 0.21/0.38 | 2.16 / 3.57 | 2.39 / 3.98 |
| Man_With_Shoes (928 V) | 0.22/0.46 · 0.22/0.68 · 0.17/0.37 | 0.26/0.84 · 0.23/0.57 · 0.16/0.31 | 6.87 / 9.39 | 6.35 / 10.08 |
| gollum_20k (21,875 V) | 0.66/3.16 · 0.31/3.19 · 0.20/1.49 | 0.95/5.99 · 0.67/3.76 · 0.24/1.78 | 173 / 238 | 170 / 245 |

**Reading.** Hover on the mix costs what hover on the rest shape costs (the ID pass draws the buffers the mix already has;
within the container's spread). The weight step is unchanged within the spread: the overlays now follow every step, but
the cost is still the viewport's per-vertex patch of the moved points (AD-025 §15.3, §17.3). Under SubD the first pick after
a weight step also patches the never drawn cage buffers (not measured separately; one patch of the moved points).
**Reference PC:** `python experiments/drag_cost/probe_morph_gl.py --only-picking` (Python there ≈ 2× slower).

**Next:** Manu's practical test (below). Same session or fresh: fresh is fine (this note is the handoff); a later
stage (§13: posed picking or position attribution) needs Manu's answers to Kurzfassung 1–3 first.

### Praxistest für Manu: Picking auf dem Morph (ca. 15 Minuten)

Technisch geprüft (Tests oben): Hover, Klick, Box/Lasso/Malen, Knife, Overlays und W/E-Ziehen sitzen auf der
gemischten Form; Schnitte landen genau dort, wo du zielst; bei 0 % ist alles wie vorher. Offen ist nur, wie es sich
anfühlt. **Meine Lesart deiner Entscheidung** (bitte in einem Satz korrigieren, falls falsch): du bearbeitest weiter die
Basis; in der Pose bleibt alles beim Alten; `N` antippen (0 % ↔ zuletzt) ist dein Blick auf die Ruheform; bei SubD
wird auf dem gemischten Käfig gepickt, nicht auf der glatten Fläche; die Zielbearbeitung mit `Tab` bleibt wie sie ist.

Start: `python src\main.py`, `Leertaste` → `head_basemesh`. Ziel anlegen (`Ctrl+N`), mit `Tab` daneben den Mund öffnen
(Kiefer-Punkte nach unten ziehen), `Tab` zurück. Gewicht mit `N` halten + Maus auf **50 %**, dann auf **100 %**.

| # | Schritt | Dein Verdikt |
|---|---|---|
| 1 | Hover in `1` / `2` / `3` über Lippen und Mundinnenraum: leuchtet immer das Element auf, das du *siehst*? | |
| 2 | Klick und Box-/Lasso-Auswahl im offenen Mund: wird genau das Sichtbare ausgewählt? Malen ebenso? | |
| 3 | `W` auf ausgewählten Lippenpunkten: bleibt der Punkt unter der Maus? (Gedreht/Skaliert wird die Basis – große Morph-Abstände drehen nicht starr mit, bekannt.) | |
| 4 | Loop Insert (`I`) an einer Lippenkante bei 100 %: sitzt der neue Loop, wo du ihn siehst? `N` antippen: liegt er auch in Ruhe sauber? | |
| 5 | Knife (`C`) im offenen Mund: Punkte auf Kanten und in Flächen, `Enter`. Sitzt der Schnitt genau, wo du geklickt hast, bei 50 % und bei 100 %? | |
| 6 | `N` antippen (0 %): ist alles wie früher (Hover, Auswahl, Gizmo)? Ist das als Blick auf die Ruheform genug, oder fehlt dir ein Umschalter? | |
| 7 | Mit SubD (falls du es nutzt): Picking auf dem gemischten Käfig – passt das? | |
