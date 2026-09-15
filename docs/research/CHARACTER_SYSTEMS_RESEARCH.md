# Character Systems Research

**Status:** Discovery — external research, no decisions
**Date:** 2026-09-15
**Version:** V1 (initial draft)

---

## Scope

This document is the authoritative home for **artist-side research on Character Systems**: rigging, controls/handles, skinning, weighting, deformation, posing, morphing/blendshapes, correctives, facial deformation, procedural/automatic rigging.

It collects **what other people have tried**, and how they thought about it.

### What this document is not

* not a rigging architecture
* not a technical specification
* not a decision list
* not a best-practice collection
* not an implementation plan
* not a recommendation for Mirai-Bastel

### Boundary to existing documents

| Document                                                                      | Responsibility                                                        |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `docs/design/artist_playground/UX_RESEARCH.md` + Three-Role UX System         | Interaction Grammar and research methodology                          |
| `experiments/rigging-skinning-morphing/` (RESEARCH, DESIGN, AD-005, FINDINGS) | technical experiments, core behavior, architectural knowledge         |
| **this document**                                                             | external research, concepts, observations, potential experiment ideas |

Cross-references are encouraged. Responsibilities must not be mixed. In particular: an observation here is **never** an answer to an open architectural question from AD-005. It may *inform* a question, but it cannot decide it.

### Language

This document is written in English because it is intended as an agent-/research-facing document. The English-language design/agent documents remain unchanged in their responsibility and structure.

---

## Research Principles

**1. Observation instead of recommendation.**
Not: “X is better than Weight Painting.”
Instead: “X shifts the task from explicit weight editing to …”

**2. Existence is not validation.**
The fact that Maya, Blender, a plugin, or a SIGGRAPH paper does something in a particular way says nothing about whether it is right for Mirai-Bastel. Market share is not an argument. Age is not an argument.

**3. Evidence vs. assumption is explicitly marked.**
Every observation carries an evidence level:

* `[Source]` — supported by a reference below
* `[Experience Knowledge]` — formulated from general knowledge, not yet cross-checked; verify before further use

**4. The interesting question is dissatisfaction.**
We are not looking for “the best rigging tools,” but for people who could not work effectively with an established workflow and therefore built something different. The problem being solved is more valuable than the solution.

**5. Implementation decision ≠ UX idea.**
Many things that look like concepts are merely technical necessities from their time. Each observation therefore asks: Which part is technology, and which part is a different way of thinking?

### Observation Format

```text
O-xx — Name
Problem                   — what bothered the author
Conventional Approach     — what was done before
Changed Assumption        — which DCC convention is removed
Interaction               — what the Artist actually does
Mental Model              — what the Artist thinks in terms of now
Shifted Responsibility    — what the Artist no longer does, who does it instead
Observable Benefit
New Problems / Open Questions
Technology or UX Idea?
```

---

## Research Map

Intentionally a filing structure, not a grid to fill out. Empty areas are normal and should remain normal.

| Area                     | collected so far       |
| ------------------------ | ---------------------- |
| Rig / Controls / Handles | O-04, O-05, O-07, O-08 |
| Skinning / Weights       | O-01, O-06, O-09       |
| Deformation              | O-02, O-04             |
| Posing                   | O-03, O-07             |
| Morphs / Shapes          | —                      |
| Correctives              | O-05                   |
| Facial Systems           | —                      |
| Automatic / Procedural   | O-08                   |
| Alternative Paradigms    | O-03, O-04             |

A system can appear in multiple areas. This is not an error; it is often the interesting part.

---

## Observations

### O-01 — Weight Transfer Across Topology Boundaries (GATOR, copySkinWeights, Data Transfer)

`[Experience Knowledge]`

**Problem:** Retopology or mesh changes after skinning make the weighting useless.
**Conventional Approach:** Paint the weights again.
**Changed Assumption:** Weights do not belong to this specific mesh with these specific IDs. They are spatially defined information that can be transferred from one mesh to another.
**Interaction:** Select old and new mesh, trigger transfer.
**Mental Model:** “The weighting exists in space, not in the vertex list.”
**Shifted Responsibility:** The Artist chooses the mapping method; the system performs the spatial search.
**Observable Benefit:** Topology freedom after rigging; structural changes can survive without ID correspondence.
**New Problems:** Proximity systematically gets things wrong around narrow regions (lips, armpits, fingers). The old mesh must be preserved. It is a batch operation with a before and after — not a living state.
**Technology or UX Idea?** Both. The implementation is geometry search. The idea that “rig data is not bound to mesh identity” is a different mental model.

---

### O-02 — Delta Mush / Corrective Smooth

`[Experience Knowledge]` — Rhythm & Hues, SIGGRAPH 2014 talk; available in Blender as the “Corrective Smooth” modifier

**Problem:** The last 20% of weighting quality costs 80% of the time.
**Conventional Approach:** Polish individual vertices until collapses and spikes disappear.
**Changed Assumption:** Deformation quality does not have to come from the weights themselves.
**Interaction:** Assign rough weights, add a deformer, continue working.
**Mental Model:** The deformed result is smoothed; local detail measured in the rest state is reapplied. The Artist thinks in terms of “silhouette roughly right, detail comes back.”
**Shifted Responsibility:** From manual weight editing to a downstream deformation process.
**Observable Benefit:** Rough weights produce usable results; weighting becomes significantly more tolerant of errors.
**New Problems:** The Artist can no longer see *why* something looks good. Per-frame cost. Intentionally sharp features are also smoothed. The precomputation depends on the rest topology — loop insertion creates the same problem one layer higher.
**Technology or UX Idea?** The smoothing itself is technology. The idea of “generating quality downstream instead of working precisely upfront” is a mindset that could appear elsewhere as well.

---

### O-03 — Posing Without a Rig: Blender Pose Brush

`[Source]` — Dobarro, Blender 2.81/2.82

**Problem:** To *evaluate* deformation, you normally need a finished rig first. Build bones, bind, weight — and only then do you see whether the intended result works.
**Conventional Approach:** Rig first, pose afterward.
**Changed Assumption:** The deformation structure does not have to exist before the gesture and does not have to survive afterward.
**Interaction:** Place the cursor on the forearm and drag — the arm bends. The Brush determines the origin point automatically and displays it as a white line in the cursor. IK segments are generated automatically; brush falloff determines how far the rotation propagates through the chain.
**Mental Model:** “I grab the character,” not “I operate a controller.”
**Shifted Responsibility:** Segmentation and pivot determination move entirely to the system; the Artist provides only location and direction.
**Observable Benefit:** Deformation intent can be tested before rig data exists. The result is pure geometry and remains topologically editable.
**New Problems:** Not repeatable, not animatable, no temporal consistency. The origin point is a system estimate; when it is wrong, the Artist has no direct correction mechanism other than the gesture itself.
**Technology or UX Idea?** Clearly a UX idea. The interesting part is not the IK solver (small and well-known), but the decision to create and discard the structure **per gesture**.

---

### O-04 — One Weight System for Points, Bones, and Cages (Bounded Biharmonic Weights)

`[Source]` — Jacobson, Baran, Popović, Sorkine-Hornung, SIGGRAPH 2011

**Problem:** The authors explicitly identify two burdens of linear blending: you either have to paint weights manually or model closed cages around the object.
**Conventional Approach:** A separate system for each deformer type — joints with weight painting, clusters with falloff, lattice with a cage.
**Changed Assumption:** The handle type does not have to determine which deformation system runs. Points, bones, and cages of arbitrary topology can **simultaneously** and **in combination** control the same object.
**Interaction:** The Artist chooses whichever handle type is most convenient for the specific task — bones for rigid parts, cages for precise large-scale control, points for soft areas.
**Mental Model:** “I place influence points” instead of “I build a skeleton and then a lattice as well.”
**Shifted Responsibility:** Weight computation moves into an optimization performed at bind time; the Artist decides only *where* influence exists, not *how much* influence exists where.
**Observable Benefit:** Tool choice follows the task rather than the system architecture. Weight Painting is no longer mandatory.
**New Problems:** The authors themselves identify spatial discretization and optimization as disadvantages. Weights are generated at bind time — what happens when topology changes is therefore not answered. And: if the Artist no longer paints the weights, how do they correct a location where the automation is wrong?
**Technology or UX Idea?** The weight formula is technology. The statement that “the Artist should be free to use the most convenient combination of handle types” is explicitly formulated as a UX goal and is the interesting part.

---

### O-05 — Smart Bones and Smart Bone Dials (Moho / formerly Anime Studio)

`[Source]`

**Problem:** A bent elbow collapses. In a 3D DCC, the solution would be called Pose Space Deformation or Corrective Shape — concepts a 2D animator should not have to learn.
**Conventional Approach:** Driven Keys, PSD setups, corrective blendshape pipelines with their own terminology.
**Changed Assumption:** A correction does not need to be its own system concept. It can be a recorded action tied to a bone angle.
**Interaction:** Assign a bone as a Smart Bone, create an action, rotate the bone into the problematic position, and manually reshape the form there. Moho interpolates between the straight and corrected state.
**Mental Model:** “When this bone is in this position, it should look like this.” No solver terminology, no Shape Editor, no intermediate object.
**Shifted Responsibility:** The entire PSD machinery disappears behind a recording gesture.
**Second, separate observation:** The **Smart Bone Dial** is a bone that is not bound to anything and sits outside the character. It is used only as a control — for head rotations, blinking, facial expressions. Technically a Bone, functionally a Slider. The system type says nothing about its role in the rig.
**Observable Benefit:** Correctives become accessible to people who would never have built a PSD setup. A single primitive (bone) covers both deformation *and* control.
**New Problems:** User forums indicate that naming conventions are critical (the action name must exactly match the bone name), angle ranges and directions are error-prone, and nesting quickly becomes opaque. The simplicity of the gesture is paid for with an invisible rule layer.
**Technology or UX Idea?** Both, and both are separately interesting: correction-as-recording, and the repurposed bone as a control.

---

### O-06 — Weights as Layers Instead of a Numeric Field (ngSkinTools)

`[Source]` — Maya plugin, Viktoras Makauskas

**Problem:** Weight Painting is destructive. Every stroke overwrites the previous state; the *intent* behind a weighting decision can no longer be recovered afterward. The classic countermeasure is Influence Locking and micromanagement of individual values.
**Conventional Approach:** A flat weight field per vertex, painstakingly protected against overwriting.
**Changed Assumption:** Weights do not have to be a flat final state. They can be composed like layers with masks in an image editor and combined only at runtime.
**Interaction:** Paint the spine on one layer, arms on another; the system combines them in real time into the final skin-cluster weights. A lower “safety layer” with 100% guarantees normalization.
**Mental Model:** Photoshop. Explicitly marketed this way: start messy, experiment, refine later.
**Shifted Responsibility:** The combination/calculation; the Artist works in layers of intent instead of final values. Influence Locking was deliberately omitted because layers make it unnecessary complexity.
**Observable Benefit:** A decision can be undone without destroying neighboring decisions. Symmetry can be enabled per layer instead of as a global operation.
**New Problems:** Two truths exist in the same document — users are warned not to use Maya's standard tools in parallel because the layers overwrite those changes on the next access. This is the core tension: an intent layer above a final state is only consistent if nobody directly edits the final state.
**Technology or UX Idea?** UX idea with a clear architectural consequence. “The Artist edits the source of the result rather than the result itself” is a pattern that extends far beyond skinning.

---

### O-07 — ZSpheres and Transpose (ZBrush)

`[Experience Knowledge]`

**Problem:** Skeleton construction and binding are two separate disciplines before you can even see a pose.
**Conventional Approach:** Place joints, orient them, bind, weight.
**Changed Assumption:** The same primitive chain that describes the structure can also generate or control the geometry. And: posing can be a masking gesture rather than a hierarchy selection.
**Interaction (Transpose):** Mask an area, draw a line, then translate/rotate. The “rig” is the mask.
**Mental Model:** The selection *is* the influence zone. No persistent controller.
**Shifted Responsibility:** No binding, no weighting — but the Artist bears full responsibility for mask quality.
**Observable Benefit:** A very short path from “I want to see this” to “I see it.”
**New Problems:** Not animatable; transition areas are only as good as the mask edge; no reusable state.
**Status:** Not cross-checked. Verify before further use.

---

### O-08 — Rig as Geometry and Graph (Houdini KineFX)

`[Experience Knowledge]`

**Problem:** Rigging is a one-way street. Once bound, upstream changes become expensive.
**Conventional Approach:** Model → Rig → bound state; afterward, the mesh is largely frozen.
**Changed Assumption:** A skeleton does not have to be a special type. It can be geometry with attributes — and therefore be editable with normal geometry tools.
**Interaction:** Rigging happens as a node chain. A topology change is simply another node before the deform; the result is then re-evaluated.
**Mental Model:** “The rig is a recipe, not a state.”
**Shifted Responsibility:** From the Artist to the graph — at the cost of requiring the Artist to think procedurally.
**Observable Benefit:** This structurally addresses exactly the problem the existing Mirai experiment is concerned with (topology changes after rigging), rather than repairing it afterward.
**New Problems:** Direct manipulation tends to be lost; the procedural overhead is substantial for a small direct-modeling tool; weights as attributes require their own generation rules.
**Status:** Not cross-checked. Verify before further use.

---

### O-09 — The “Weight Hammer” as a Symptom

`[Source]` — user discussion, Maya LT

A small practical observation, not a system: An Artist adds polygons after rigging and cannot paint weights onto the new vertices. The common answer is a tool called “Weight Hammer,” which transfers neighboring vertices' weights to the new ones.

**Why it is here:** The problem is so normal in established DCCs that it has a tool with its own name and icon — and yet the standard workflow still causes confusion. This suggests that “topology changes after rigging” is not a Mirai-specific edge case but a persistent industry-wide pain point with many partial solutions.

**Open Question:** How often does this actually happen, and what do Artists do instead — do they simply stop editing the topology? That would be an avoidance strategy, not a solution, and would not appear in any documentation.

---

## Research Thread 1 — One Handle Concept Instead of Bone / Cluster / Lattice / Cage

**Research Question:**

> Does an Artist actually need to know which technical deformation structure is behind a manipulation point?

It is explicitly **not** assumed that “Handle” is the right answer. The question is what answers real systems provide.

### How the current observations answer it

| System                 | Answer to the question                                                   | Through                                                                                   |
| ---------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| Classical DCC          | **Yes** — the Artist has to know                                         | Joint, Cluster, Lattice, Wire each have their own creation method, UI, and weight concept |
| BBW (O-04)             | **No** — type is a convenience question                                  | one weighting system supports points, bones, and cages in combination                     |
| Pose Brush (O-03)      | **No** — there is no persistent structure at all                         | pivot and segmentation are created per gesture and discarded again                        |
| Smart Bone Dial (O-05) | **No, but hidden** — it is a bone that is not a bone                     | system type and role are decoupled without the system explicitly naming this              |
| Transpose (O-07)       | **No** — the mask is the structure                                       | selection instead of controller                                                           |
| KineFX (O-08)          | **Yes, but differently** — the Artist thinks in data, not deformer types | skeleton is geometry                                                                      |

### What stands out in this comparison

The interesting axis may not actually be “one type vs. many types,” but **how long the structure lives**:

```text
created and discarded per gesture       → Pose Brush, Transpose
created at bind time, then fixed        → BBW
persistent and maintained by Artist     → classical rig
regenerated on every evaluation         → KineFX
```

This is a hypothesis from the comparison, not a finding. It needs more cases.

### Not yet investigated in this thread

Implicit Skinning (contact and bulge instead of weight polishing) · Wires (Singh/Fiume 1998, curve as deformer) · Blender Hook Modifier (arbitrary object becomes a handle) · Houdini handles as manipulators decoupled from nodes · Cage-based IK · Direct Manipulation Blendshapes · Poser magnets · Daz JCM · Cascadeur AutoPosing · Spine/Live2D/Rive (2D rigging with very different underlying assumptions) · Ziva (deformation as anatomical simulation) · automatic riggers (Pinocchio, Mixamo, RigNet).

---

## Candidate Playground Experiments

Ideas, not implementation proposals. Whether, when, and in what order anything is built is decided by Manu. Each would be an isolated Artist Playground experiment according to `EXPERIMENT_HOST.md`, not a rigging feature.

**CE-1 — Point Handles Only**
Head base mesh, exclusively point handles with falloff, no skeleton, no hierarchy. Question: How far does a single handle concept carry before the Artist starts missing something — and what exactly is missing first?
Touches: O-04, Research Thread 1.

**CE-2 — Visible vs. Invisible Influence Region**
The same handle, once with its influence region displayed and once without. Question: Is the influence predictable without seeing it? Note: This varies *signalling*, which according to Research Map V1 is the largest confounding risk — here, signalling is deliberately the variable itself.

**CE-3 — Gesture-Derived Pivot vs. Explicit Pivot**
Drag at a location on the mesh; in one version the system determines the pivot (Pose Brush-like), in the other the Artist sets it beforehand. Question: Where exactly does convenience turn into loss of control?
Touches: O-03.

**CE-4 — Correction as Recording**
Move an element into a pose, reshape the form there, and let the system interpolate. Question: Is “when it is in this position, it should look like this” understandable and controllable without Shape/PSD terminology?
Touches: O-05.

**CE-5 — Intent Layer Instead of Final State**
Edit an arbitrary value (not necessarily weights) in two layers instead of directly. Question: Does “I am editing the source of the result” feel freer or more indirect?
Touches: O-06.

**Not listed as a candidate:** anything that tests topology changes under active deformation. That is the subject of the existing technical experiment (`experiments/rigging-skinning-morphing/`) and should not be duplicated here as a UX experiment.

---

## Open Questions

1. Is “how long the deformation structure lives” actually the fundamental axis, or an artifact of the six cases collected so far?
2. If automation determines the weights (O-04), how does the Artist correct a location where the automation is wrong without abandoning the entire concept?
3. Are there real examples where the separation between modeling and rigging has been completely removed, rather than merely repaired afterward?
4. What do Artists do when they simply *avoid* topology changes after rigging? This avoidance behavior is invisible in documentation, but may be the most common approach.
5. 2D rigging (Moho, Spine, Live2D) has assumptions that do not apply in 3D at all. Which ideas are transferable, and which work only because the medium is 2D?
6. How much of the known DCC rigging complexity exists because of large-team film production — and is therefore simply irrelevant to a single Artist working on a head base mesh?

---

## Sources / References

**Supported:**

* Bounded Biharmonic Weights — Jacobson, Baran, Popović, Sorkine-Hornung, SIGGRAPH 2011. https://igl.ethz.ch/projects/bbw/ · Paper PDF: https://igl.ethz.ch/projects/bbw/bounded-biharmonic-weights-siggraph-2011-jacobson-et-al.pdf · CACM version: https://cacm.acm.org/research/bounded-biharmonic-weights-for-real-time-deformation/
* Blender Pose Brush — Manual: https://docs.blender.org/manual/en/latest/sculpt_paint/sculpting/brushes/pose.html · Developer report: https://code.blender.org/2020/02/sculpt-mode-features-update/ · First presentation: https://www.blendernation.com/2019/12/12/preview-sculpt-mode-pose-brush/ · Dobarro on Sculpt Mode generally: https://pablodp606.artstation.com/blog/1vEn/new-blender-sculpt-mode-introduction
* Moho Smart Bones — Manufacturer description: https://moho.lostmarble.com/pages/features · Corrective/PSD equivalent context: https://lesterbanks.com/2016/11/working-mohos-smart-bone-actions/ · Smart Bone vs. Smart Bone Dial (user forum): https://lostmarble.net/forum/viewtopic.php?t=35634
* ngSkinTools — Product description: https://www.ngskintools.com/ · Layer concept: https://www.ngskintools.com/documentation/userguide/quickstart/ · deliberate omission of Influence Locking: https://www.ngskintools.com/documentation/userguide/faq/ · practical experiences including conflict with Maya standard tools: https://rigmarolestudio.com/ngskintools-skinning-tips/
* Weight Hammer / polygons after rigging: https://steamcommunity.com/app/243580/discussions/0/357287935556802103

**Not yet cross-checked (Experience Knowledge, verify before further use):**

* GATOR (Softimage), Maya `copySkinWeights`, Blender Data Transfer
* Delta Mush (Rhythm & Hues, SIGGRAPH 2014) / Blender Corrective Smooth
* ZBrush ZSpheres and Transpose / Transpose Master
* Houdini KineFX

---

## Related Documents

* `AGENTS.md` — repository-wide agent and documentation rules
* `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` — M1–M5, Discovery/Production, Artist Verdict
* `docs/design/artist_playground/UX_RESEARCH.md` — Interaction Grammar (different responsibility)
* `docs/design/artist_playground/EXPERIMENT_HOST.md` — experiment/variant/slot vocabulary for future experiments
* `experiments/rigging-skinning-morphing/` — technical rigging experiment, AD-005, FINDINGS (different responsibility)
