# Character Systems Research

**Status:** Discovery — external research, no decisions
**Date:** 2026-09-15
**Version:** V3 (Condensation and transition to Playground questions; V2 research unchanged)

---

## Scope

This document is the authoritative home for **artist-side research on Character Systems**: rigging, controls/handles, skinning, weighting, deformation, posing, morphing/blendshapes, correctives, facial deformation, procedural/automatic rigging.

It collects **what other people have tried**, and how they thought about it.

### What this document is not

* not a rigging architecture
* not a technical specification
* not a decision list
* not a best-practice collection
* not implementation planning
* not a recommendation for Mirai-Bastel

### Boundary to existing documents

| Document                                                                      | Responsibility                                                       |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `docs/design/artist_playground/UX_RESEARCH.md` + Three-Role UX System         | Interaction Grammar and research methodology                         |
| `experiments/rigging-skinning-morphing/` (RESEARCH, DESIGN, AD-005, FINDINGS) | technical experiments, core behavior, architectural knowledge        |
| **this document**                                                             | external research, concepts, observations, possible experiment ideas |

Cross-references are encouraged. Responsibilities are not mixed. In particular: An observation here is **never** an answer to an open architecture question from AD-005. It may *illuminate* a question, but it cannot decide it.

### Language

German, according to the project convention: research and artist documents in German, technical/architecture/AI exchange documents in English.

---

## Research Principles

**1. Observation instead of recommendation.**
Not: “X is better than Weight Painting.”
But: “X shifts the task from explicit weight editing to …”

**2. Existence is not validation.**
The fact that Maya, Blender, a plugin, or a SIGGRAPH paper does something in a certain way says nothing about whether it is right for Mirai. Market share is not an argument. Age is not an argument.

**3. Evidence vs. assumption is marked.**
Every observation carries an evidence level:

* `[Source]` — supported by a reference below
* `[Experiential Knowledge]` — formulated from general knowledge, not yet cross-checked; verify before reuse
* `[Artist Experience]` — Manu's own practical experience; valid for him, not generalizable (as of V3)
* `[Hypothesis]` — derived from comparison, not observed (as of V3)

**4. The interesting question is the dissatisfaction.**
We are not looking for “the best rigging tools,” but for people who could not work with an established workflow and therefore built something different. The problem that was solved is more valuable than the solution.

**5. Implementation decision ≠ UX idea.**
Many things that look like concepts are merely technical necessities of their time. Every observation therefore asks: What is technology, and what is a different way of thinking?

**6. Contrast before completeness.**
The goal is the number of *different* mental models, not the number of systems collected. Another example of an already-understood model is not included merely because it exists.

### Observation Format

```
O-xx — Name
Problem                — what bothered the author
Conventional Approach  — what was done before
Changed Assumption     — which DCC assumption disappears
Interaction            — what the Artist actually does
Mental Model            — what the Artist thinks in now
Shifted Responsibility — what the Artist no longer does, who does it instead
Observable Advantage
New Problems / Open Questions
Technology or UX Idea?
```

---

## Research Map

Deliberately a repository, not a grid to fill out. Empty areas are normal and remain normal.

| Area                     | collected so far                   |
| ------------------------ | ---------------------------------- |
| Rig / Controls / Handles | O-04, O-05, O-07, O-08, O-10, O-11 |
| Skinning / Weights       | O-01, O-06, O-09, O-13             |
| Deformation              | O-02, O-04, O-12, O-13             |
| Posing                   | O-03, O-07, O-14                   |
| Morphs / Shapes          | O-15                               |
| Correctives              | O-05                               |
| Facial Systems           | O-15, O-16                         |
| Automatic / Procedural   | O-08, O-14                         |
| Alternative Paradigms    | O-03, O-04, O-12, O-14, O-16       |

A system can appear in multiple areas. This is not a problem, but often the interesting part.

---

## Observations

### O-01 — Weight Transfer Across Topology Boundaries (GATOR, copySkinWeights, Data Transfer)

`[Experiential Knowledge]`

**Problem:** Retopology or mesh changes after skinning make the weighting worthless.
**Conventional Approach:** Paint the weights again.
**Changed Assumption:** Weights do not belong to this specific mesh with these specific IDs. They are spatially defined information that can be transferred from one mesh to another.
**Interaction:** Select old and new mesh, trigger transfer.
**Mental Model:** “The weighting lives in space, not in the vertex list.”
**Shifted Responsibility:** The Artist chooses the mapping method; the system performs the spatial search.
**Observable Advantage:** Topology freedom after rigging; modifications survive without ID relationships.
**New Problems:** Proximity systematically gets confused at cavities (lips, armpits, fingers). The old mesh must be retained. It is a batch operation with a before and after — not a living state.
**Technology or UX Idea?** Both. The implementation is geometry search. The idea “rig data is not bound to mesh identity” is a different mental model.

---

### O-02 — Delta Mush / Corrective Smooth

`[Experiential Knowledge]` — Rhythm & Hues, SIGGRAPH 2014 Talk; implemented in Blender as the “Corrective Smooth” modifier

**Problem:** The final 20% of weighting quality costs 80% of the time.
**Conventional Approach:** Polish individual vertices until collapse and spikes disappear.
**Changed Assumption:** Deformation quality does not have to come from the weighting itself.
**Interaction:** Assign roughly, add a deformer, continue working.
**Mental Model:** The deformed result is smoothed; the local detail measured in the rest state is restored afterward. The Artist thinks in “silhouette roughly correct, detail comes back.”
**Shifted Responsibility:** From manual weight editing to a downstream deformation process.
**Observable Advantage:** Rough weights produce usable results; the tolerance for weighting errors increases significantly.
**New Problems:** The Artist can no longer see *why* something looks good. Cost per frame. Intentionally sharp edges are smoothed as well. The precomputation depends on the rest topology — inserting a loop creates the same problem one layer higher.
**Technology or UX Idea?** The smoothing is technology. The idea “generate quality downstream instead of working precisely upfront” is an attitude that could appear elsewhere as well.

---

### O-03 — Poses Without a Rig: Blender Pose Brush

`[Source]` — Dobarro, Blender 2.81/2.82

**Problem:** To *evaluate* deformation, you normally need a finished rig first. Build bones, bind, weight — and only then do you see whether the intention works.
**Conventional Approach:** Rig first, pose afterward.
**Changed Assumption:** The deformation structure does not have to exist before the gesture, nor survive afterward.
**Interaction:** Place the cursor over the forearm, drag — the arm bends. The Brush determines the origin point itself and displays it as a white line in the cursor. IK segments are created automatically; Brush falloff determines how far the rotation propagates through the chain.
**Mental Model:** “I grab the character,” not “I operate a controller.”
**Shifted Responsibility:** Segmentation and pivot determination move completely to the system; the Artist provides only location and direction.
**Observable Advantage:** Deformation intent can be tested before rig data exists. The result is pure geometry — still freely editable topologically.
**New Problems:** Not repeatable, not animatable, no temporal consistency. The origin point is a system estimate; if it is wrong, the Artist has no direct correction mechanism other than the gesture itself.
**Technology or UX Idea?** Clearly a UX idea. What is interesting is not the IK solver (small and well known), but the decision to let the structure emerge **per gesture** and disappear again.

---

### O-04 — One Weight System for Points, Bones, and Cages (Bounded Biharmonic Weights)

`[Source]` — Jacobson, Baran, Popović, Sorkine-Hornung, SIGGRAPH 2011

**Problem:** The authors explicitly identify two burdens of linear blending: you must either paint weights manually or model closed cages around the object.
**Conventional Approach:** One system per deformer type — joints with Weight Painting, clusters with falloff, lattice with cage.
**Changed Assumption:** The handle type does not have to determine which deformation system runs. Points, bones, and cages of arbitrary topology can **simultaneously** and **mixed** control the same object.
**Interaction:** The Artist chooses the handle type that is most convenient for the respective task — bones for rigid parts, cages for large-scale precise control, points for soft areas.
**Mental Model:** “I place influence points” instead of “I build a skeleton and then also a lattice.”
**Shifted Responsibility:** Weight calculation moves into an optimization performed at bind time; the Artist only decides *where* influence sits, not *how strongly where*.
**Observable Advantage:** Tool choice is based on the task, not system architecture. Weight Painting disappears as a mandatory step.
**New Problems:** The authors themselves cite spatial discretization and optimization as disadvantages. Weights are generated at bind time — what happens when topology changes is therefore still unanswered. And: If the Artist no longer paints the weights, how do they correct a location where the automation is wrong?
**Technology or UX Idea?** The weight formula is technology. The statement “the Artist should be free to work with the most convenient combination of handle types” is explicitly formulated as a UX goal and is the interesting part.

---

### O-05 — Smart Bones and Smart Bone Dials (Moho / formerly Anime Studio)

`[Source]`

**Problem:** A bent elbow collapses. In a 3D DCC, the solution would be Pose Space Deformation or Corrective Shape — both terms that a 2D animator does not want to learn.
**Conventional Approach:** Driven Keys, PSD setups, Corrective Blendshape pipelines with their own terminology.
**Changed Assumption:** A correction does not have to be its own system concept. It can be a recorded action tied to a bone angle.
**Interaction:** Define a bone as a Smart Bone, create an action, rotate the bone into the problematic position, and manually adjust the shape there. Moho interpolates between the extended and corrected state.
**Mental Model:** “If this bone is in this position, it should look like this.” No solver terminology, no Shape Editor, no intermediate object.
**Shifted Responsibility:** The entire PSD machinery disappears behind a recording gesture.
**Second, separate observation:** The **Smart Bone Dial** is a bone that is not bound to anything and sits outside the character. It is used only as a control — for head turns, blinking, facial expressions. Technically a Bone, functionally a Slider. The system type says nothing about the role in the rig.
**Observable Advantage:** Correctives become accessible to people who would never have built a PSD setup. A single primitive (bone) covers both deformation *and* control.
**New Problems:** From user forums: naming conventions are critical (the action name must match the bone name exactly), angle ranges and directions are error-prone, and nesting quickly becomes opaque. The simplicity of the gesture is bought with an invisible rule layer.
**Technology or UX Idea?** Both, and both are separately interesting: correction-as-recording, and the repurposed bone as a control.

---

### O-06 — Weights as Layers Instead of a Numeric Field (ngSkinTools)

`[Source]` — Maya plugin, Viktoras Makauskas

**Problem:** Weight Painting is destructive. Every stroke overwrites the previous state; the *intention* behind a weighting can no longer be found afterward. The classic countermeasure is Influence Locking and micromanagement of individual values.
**Conventional Approach:** A flat weight field per vertex, laboriously protected against overwriting.
**Changed Assumption:** Weights do not have to be a flat final state. They can be composited like layers in an image editor, with masks, and only combined into the final result at runtime.
**Interaction:** Paint the spine in one layer, the arms in another; the system combines them in real time into the final skin cluster weights. A lower “safety layer” with 100% guarantees normalization.
**Mental Model:** Photoshop. Explicitly marketed that way: start messy, experiment, refine later.
**Shifted Responsibility:** The compositing; the Artist works in layers of intent rather than final values. Influence Locking was deliberately omitted — with layers, it was considered unnecessary complexity.
**Observable Advantage:** A decision can be undone without destroying neighboring decisions. Symmetry can be enabled per layer instead of as a global operation.
**New Problems:** Two truths in the same document — users are warned not to use Maya's standard tools in parallel because the layers overwrite those changes the next time they are accessed. This is the core tension: An intent layer over a final state is only consistent if nobody touches the final state directly.
**Technology or UX Idea?** A UX idea with a clear architectural consequence. “The Artist edits not the result, but the origin of the result” is a pattern that extends far beyond skinning.

---

### O-07 — ZSpheres and Transpose (ZBrush)

`[Experiential Knowledge]`

**Problem:** Skeleton construction and binding are two separate disciplines before you can even see a pose.
**Conventional Approach:** Place joints, orient them, bind, weight.
**Changed Assumption:** The same primitive chain that describes the structure can also generate or control the geometry. And: posing can be a masking gesture rather than a hierarchy selection.
**Interaction (Transpose):** Mask an area, draw a line, drag/rotate. The “rig” is the mask.
**Mental Model:** The selection *is* the influence zone. No persistent controller.
**Shifted Responsibility:** No binding, no weighting — but the Artist carries full responsibility for mask quality.
**Observable Advantage:** Very short path from “I want to see this” to “I see it.”
**New Problems:** Not animatable; transition areas are only as good as the mask edge; no reusable state.
**Status:** Not cross-checked. Verify before reuse.

---

### O-08 — Rig as Geometry and Graph (Houdini KineFX)

`[Experiential Knowledge]`

**Problem:** Rigging is a one-way street. Once bound, upstream changes are expensive.
**Conventional Approach:** Model → Rig → bound state; afterward the mesh is largely frozen.
**Changed Assumption:** A skeleton does not have to be a special type. It can be geometry with attributes — and therefore be editable with normal geometry tools.
**Interaction:** Rigging takes place as a node chain. A topology change is another node before the deform; afterward it is re-evaluated.
**Mental Model:** “The rig is a recipe, not a state.”
**Shifted Responsibility:** From the Artist to the graph — at the cost of requiring the Artist to think procedurally.
**Observable Advantage:** Exactly the question the existing Mirai experiment is concerned with (topology change after rigging) is resolved structurally instead of repaired afterward.
**New Problems:** Direct manipulation tends to be lost; the procedural overhead is substantial for a small direct modeling tool; weights as attributes require their own generation rules.
**Status:** Not cross-checked. Verify before reuse.

---

### O-09 — The “Weight Hammer” as a Symptom

`[Source]` — user discussion, Maya LT

Small practical observation, not a system: An Artist adds polygons after rigging and cannot paint weights on the new vertices. The common answer is a tool called “Weight Hammer,” which transfers neighboring vertex weights to the new ones.

**Why it is here:** The problem is so normal in established DCCs that it has a tool with its own name and icon — and the standard workflow still causes confusion. This suggests that “topology change after rigging” is not a Mirai-specific edge case, but a persistent industry-wide pain point with many partial solutions.

**Open Question:** How often does this actually happen, and what do Artists do instead — do they simply stop editing? That would be avoidance, not a solution, and it would not appear in any documentation.

---

### O-10 — The Curve as a Deformer (Wires)

`[Source]` — Singh & Fiume, SIGGRAPH 1998

**Problem:** Interactive deformation of complex objects. Lattices/FFDs are cages that formally have nothing to do with the shape they deform.
**Conventional Approach:** A grid around the object whose control points are moved.
**Changed Assumption:** The control structure does not have to lie *around* the object. It can *follow the shape*. The authors explicitly refer to the sculptor's armature: wires that define the shape and shape its deformable features.
**Interaction:** A curve (the “Wire”) lies along a feature — lip line, eyebrow, back line. The Artist pulls the curve; the surface follows. A separate “Domain Curve” determines *where* this influence applies. Wires can be sketched.
**Mental Model:** “I bend a wire that the form follows.” The control structure is a coarse geometric representation of the object itself, not a foreign helper rig.
**Shifted Responsibility:** Two things move into the system. First, the combination of multiple Wires: The authors define them as a *smoothed union* of the individual deformations (following the model of implicit surfaces) and explicitly not as an overlay — so the Artist does not have to resolve overlapping influences manually. Second, resolution independence: It was a design requirement that subdividing one Wire curve into two curves must **not** change the deformation.
**Observable Advantage:** The control structure is readable because it traces the form. Influence region (Domain) and control (Wire) are separate, visible objects.
**New Problems:** They are still two concepts the Artist has to understand. And the curves first have to be placed on the form — the structure is persistent and maintained, not gestural.
**Technology or UX Idea?** Both, but the separately interesting parts are the metaphor (sculptor's armature instead of grid cage) and the explicit requirement that the structure remain independent of its own subdivision.

---

### O-11 — The Transient Influence Radius (Soft Selection / Proportional Editing / Soft Modification)

`[Experiential Knowledge]`

**Problem:** Having to create a deformer object, name it, weight it, and delete it again for a small soft shape change.
**Conventional Approach:** Create a cluster or lattice, set falloff, use it, clean it up.
**Changed Assumption:** Influence does not need an object at all. It can be a property of the ongoing gesture.
**Interaction:** Grab an element, change the radius, drag. After release, nothing exists except the changed geometry.
**Mental Model:** “The mesh is modeling clay with a radius of influence.” There is nothing to manage.
**Shifted Responsibility:** Nothing moves to the system — on the contrary: the Artist specifies the influence anew each time. What disappears is management.
**Observable Advantage:** Zero setup, zero cleanup, works on any topology, no binding state that can become stale.
**New Problems:** Nothing is repeatable, reusable, or animatable. Hitting exactly the same influence twice is luck.
**Why it is here:** This is the extreme opposite of a classic rig on the axis of “how long does the structure live” — and at the same time the only model in this collection already named as a V1 goal in Mirai-Bastel (Soft Selection, Tweak). It therefore serves as a zero point for comparison, not as a proposal.

---

### O-12 — Deformation as Material Response (Regularized Kelvinlets)

`[Source]` — de Goes & James, Pixar, SIGGRAPH 2017; implemented in Blender as the “Elastic Deform” brush, according to user discussions also in Oculus Medium

**Problem:** Classic sculpting brushes are purely geometric — they know nothing about volume. Physically based deformers would be more plausible, but are too slow for interactive work.
**Conventional Approach:** Either geometric falloff (fast, implausible) or simulation (plausible, not interactive).
**Changed Assumption:** Physical plausibility can be achieved without simulation — by using closed-form analytical solutions of linear elasticity as a brush. The patent version states the consequence clearly: The deformation is **free of geometric discretization**.
**Interaction:** Grab, twist, scale, pinch. The material responds volumetrically, not only at the touched vertices.
**Mental Model:** “The object is elastic material; I press into it.” Not “I move points with a falloff curve.”
**Shifted Responsibility:** Falloff design becomes a material property. The Artist no longer sets a curve, but a material response — and gets volume preservation without explicitly asking for it.
**Observable Advantage:** The result feels plausible for organic forms rather than “pulled.” Because the solution is defined in space rather than on the mesh, it is independent of mesh resolution.
**New Problems:** The natural range of such solutions is large; local edits required a separate multiscale trick, and sharp edges later required another extension. No reusable structure is created — this is a sculpting model, not a rig.
**Technology or UX Idea?** Predominantly technology, but with a clear UX consequence: The Artist thinks in material behavior rather than influence weights. That is a different language for the same action.

---

### O-13 — Volume Instead of Weights at Joints (Implicit Skinning)

`[Source]` — Vaillant, Barthe, Guennebaud, Cani, Wyvill, Rohmer, Gourmel, Paulin; SIGGRAPH 2013

**Problem:** The authors state it directly: Geometric skinning (Linear Blend, Dual Quaternion) is fast, but cannot reproduce realistic deformation — elbow collapse, candy-wrapper. Simulation or control volumes would be better, but provide no real-time feedback.
**Conventional Approach:** Fight the joint problem with better weights and Corrective Shapes.
**Changed Assumption:** The skin does not have to know how it should deform. If the limbs have volume, contact and bulging emerge automatically.
**Interaction:** From the Artist's perspective, almost none — the method runs as a post-process over the existing skinning. The result provides skin contact between touching body parts without modeling it.
**Mental Model:** “The character consists of volumes that touch each other” instead of “each vertex belongs proportionally to bones.”
**Shifted Responsibility:** The most difficult weighting zone — the joint area — is removed from the Artist and handed to a volume representation.
**Observable Advantage:** Real-time contact and organic bulging, without collision detection and without loss of detail; fits into existing pipelines as a post-process.
**New Problems:** An implicit surface approximating the mesh must be generated per limb — what happens when topology changes is not answered by this source. And the question from O-04 returns: If contact emerges automatically, how does the Artist direct it where they want something different?
**Technology or UX Idea?** Predominantly technology. The UX-relevant statement is the boundary shift: Part of what has traditionally been called “weighting quality” is actually a volume problem and never belonged in the weights.

---

### O-14 — The Artist States Intent, the System Completes the Pose (Cascadeur)

`[Source]` — Nekki, originally developed for its own games (including Shadow Fight 3)

**Problem:** Full-body keyframing is slow, and the result often looks physically implausible. A game studio initially built the tool for its own production.
**Conventional Approach:** Set every controller individually; plausibility comes from the animator's experience.
**Changed Assumption:** The Artist does not have to specify every degree of freedom. They specify the *physically meaningful* quantities — center of mass, ballistic trajectory, support points (Fulcrum Points) — and move a few control points; a neural network completes the rest of the pose.
**Interaction:** Move a few points, and the rest of the body arranges itself into a natural posture. Physical deviation is displayed and may deliberately be violated.
**Mental Model:** “I say what should be true — the system turns that into a whole body.” The controls are no longer bones, but statements about the character.
**Shifted Responsibility:** Interpolation and plausibility checking; the Artist retains the intent and permission to break it.
**Observable Advantage:** Very fast path to a believable pose; physical errors become visible instead of being silently accepted.
**New Problems:** Two documented, highly instructive ones: (1) AutoPhysics misinterprets stationary animations because sliding feet are not recognized as support points — the system draws the wrong conclusion from an observation and changes the animation accordingly. (2) AutoPosing requires additional control points at elbows and knees to be placed *in a particular way*, otherwise it does not work.
**General observation from this:** Automation is not without consequences for the structure underneath. It sends requirements back down to the rig — convenience at the top creates a constraint at the bottom.
**Technology or UX Idea?** Both. The UX idea is to make the Artist think in statements about the character rather than joint angles.

---

### O-15 — Reversed Control Direction: Direct Manipulation Blendshapes

`[Source]` — Lewis & Anjyo, IEEE CG&A 2010; practical version Anjyo, Todo & Lewis 2012

**Problem:** Direct manipulation has existed for body animation for a long time (IK). For Blendshape faces there was nothing comparable — you operate sliders and watch what happens.
**Conventional Approach:** Dozens of sliders, each with a name, tried in combination.
**Changed Assumption:** The Artist does not have to think in sliders. They may touch the face; the system solves backward for which slider values produce that result.
**Interaction:** Grab and drag a point on the face. The system solves an underdetermined problem — one vertex moves, all the others have to be inferred.
**Mental Model:** “I shape the face” instead of “I set parameters.”
**Shifted Responsibility:** Solving backward. The crucial trick is regularization: The sliders are a *semantic* parameterization, so the solution is chosen that changes the facial expression as little as possible. The Artist's intent therefore remains bound to the existing Shapes rather than arbitrary geometry.
**Observable Advantage:** A single vertex movement can replace multiple slider adjustments. And the method explicitly continues to work *alongside* slider control, so it does not replace it.
**New Problems:** The authors state it themselves, unusually clearly: Direct manipulation is sometimes *less* efficient than setting parameters — and vice versa. There is no superior interaction method here, but two methods that alternate depending on the task.
**Technology or UX Idea?** The regularization is technology. The generalizable idea is the reversal of direction: The Artist edits the result, and the system finds the appropriate control values — the counterpart to O-06, where the Artist edits the origin of the result rather than the result itself.

---

### O-16 — An Artist Builds Their Own Tool: “The Art of Moving Points” and Ozone

`[Source]` — Brian Tindall (Character TD, including Pixar), E-Book 2013; later work in Ozone Rig Studio

**Problem:** Facial articulation is thought of as a collection of Shapes. Tindall's counterargument is that the real question is *how points move* — in arcs, according to a “three-curve principle” — and that topology decisions either support or fight every deformer built later.
**Conventional Approach:** Model, then articulate, then sculpt Shapes — in that order, with the early step determining the later ones.
**Changed Assumption:** According to Tindall himself: Modeling is not finished when articulation begins. What looked like the correct neutral pose before articulating only proves to be wrong once seen in motion.
**Interaction:** He describes his workflow as modeling, articulating, and volume sculpting *without a fixed order* — he continues cutting into the Basemesh while articulation already exists, and the underlying weighting and sculpts follow computationally.
**Mental Model:** Articulation is not a phase after modeling, but a parallel property of the head. And: The Artist thinks in point trajectories, not target shapes.
**Shifted Responsibility:** Maintaining consistency after a mesh change — according to the author, the program's non-destructive articulation handles this.
**Observable Advantage (as described):** The question “model first or rig first” loses its sharpness.
**New Problems / Caution:** The *how* is not publicly documented. The statement comes from the author about his own commercial tool; what is established is the dissatisfaction and claimed effect, not the mechanism. It is also a production tool for film/TV/games — nothing about it says that the same approach is useful for a single Artist working on a head Basemesh.
**Why it is here:** This is the clearest example of the desired kind — an experienced practitioner who considers the standard workflow order wrong and therefore builds their own system. And the dissatisfaction they describe is not “painting weights is annoying,” but “I only know whether it works once I see it in motion.”

---

## Research Thread 1 — One Handle Concept Instead of Bone / Cluster / Lattice / Cage

**Research Question:**

> Does an Artist even need to know which technical deformation structure is behind a manipulation point?

Explicitly **not** assuming that “Handle” is the right answer.

### How the Observations answer

| System                   | Answer to the question                                       | Through what                                                                       |
| ------------------------ | ------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| Classical DCC            | **Yes** — the Artist needs to know                           | Joint, Cluster, Lattice, Wire each have their own creation, UI, and weight concept |
| BBW (O-04)               | **No** — type is a convenience question                      | one weight system carries points, Bones, and Cages mixed                           |
| Pose Brush (O-03)        | **No** — there is no persistent structure at all             | Pivot and segmentation emerge per gesture                                          |
| Smart Bone Dial (O-05)   | **No, but hidden** — a bone that is not a bone               | system type and role are decoupled without the system naming it                    |
| Transpose (O-07)         | **No** — the mask is the structure                           | selection instead of controller                                                    |
| KineFX (O-08)            | **Yes, but differently** — the Artist thinks in data         | skeleton is geometry                                                               |
| Wires (O-10)             | **Yes, but visibly justified**                               | control curve traces the shape; influence region is a separate visible object      |
| Soft Selection (O-11)    | **The question does not arise**                              | there is no structure, only the ongoing gesture                                    |
| Kelvinlets (O-12)        | **No** — the Artist thinks in material                       | the response comes from a material equation, not a structure                       |
| Implicit Skinning (O-13) | **No, invisibly**                                            | volume in the background corrects the result without a control element             |
| Cascadeur (O-14)         | **No** — the Artist thinks in statements about the character | center of mass, trajectory, support point instead of joint                         |
| DMB (O-15)               | **No** — the Artist touches the result                       | the system solves backward to the control values                                   |

### First Ordering: What Does the Artist Believe They Are Manipulating?

The cases can be roughly sorted by the *object of manipulation*:

```
1  a hierarchy                    skeleton, bone chain
2  a geometric helper object     cage, lattice, wire, point handle
3  a region / field               mask, face set, falloff radius
4  the material itself            Kelvinlet, implicit volume
5  the result itself              Direct Manipulation: drag vertex, system solves backward
6  a statement / intent           support point, center of mass, “if it is here, it should look like this”
7  a recipe                       node graph
```

This is a sorting aid derived from 16 cases, not a taxonomy and not an evaluation matrix. Two observations:

**This axis is independent of the lifetime axis from V1.** A geometric helper object can be persistent (Wire) or emerge per gesture (Transpose mask). A region can be transient (Soft Selection) or stored (Face Set).

```
created and discarded per gesture     →  Pose Brush, Transpose, Soft Selection, Kelvinlets
created at bind time, then fixed      →  BBW, Implicit Skinning
persistent and maintained by Artist   →  classic rig, Wires
regenerated on every evaluation       →  KineFX
```

**The further down the list, the more the system has to infer.** And every time it infers, it can be wrong — this is the same open question in different forms in O-03 (estimated pivot), O-04 (automatic weights), O-13 (automatic contact), and O-14 (incorrectly identified support points):

> **How does the Artist correct an automation without abandoning the concept that just removed the work for them?**

Four independent cases name this problem, and none solves it convincingly. This is the most striking recurring finding of this pass.

### Thread Status

The thread now has enough contrast. Additional examples from categories 1–3 would confirm already-understood models. Categories 5 and 6 are thinly represented — only one or two cases so far.

### Not yet investigated in this thread

ARAP / Laplacian Surface Editing (dragging with shape preservation through a solver) · Blender Hook Modifier (arbitrary object becomes a handle) · Cage-based IK · Ziva / deformation as anatomical simulation · Poser magnets · Daz JCM · Spine/Live2D/Rive · automatic riggers (Pinocchio, Mixamo, RigNet, AccuRig) · Houdini handles as manipulators decoupled from the node.

---

## Candidate Playground Experiments

Ideas, not implementation proposals. Whether, when, and in what order anything is built is decided by Manu. Each would be an isolated Artist Playground experiment according to `EXPERIMENT_HOST.md`, not a rigging feature.

**This pass deliberately added no new candidates.** O-10 through O-16 are mental models; translating them into experiment ideas now would be premature.

**CE-1 — Point Handles Only**
Head Basemesh, exclusively point Handles with falloff, no skeleton, no hierarchy. Question: How far does a single Handle concept carry before the Artist starts missing something — and what exactly do they miss first?
Touches: O-04, Research Thread 1.

**CE-2 — Visible vs. Invisible Influence Region**
The same Handle, once with its influence region displayed, once without. Question: Is the influence predictable at all without seeing it? Caution: This varies *Signalling*, which according to Research Map V1 is the greatest confounding risk — here, Signalling is exceptionally the variable itself.

**CE-3 — Gesture-Derived Pivot vs. Set Pivot**
Drag at a location on the mesh; once the system determines the pivot (Pose Brush-like), once the Artist sets it beforehand. Question: Where exactly does convenience become loss of control?
Touches: O-03.

**CE-4 — Correction as Recording**
Bring an element into a position, adjust the shape there, and let the system interpolate. Question: Is “if it is in this position, it should look like this” understandable and controllable without Shape/PSD terminology?
Touches: O-05.

**CE-5 — Intent Layer Instead of Final State**
Edit an arbitrary value (not necessarily weights) in two layers instead of directly. Question: Does “I edit the origin of the result” feel freer or more indirect?
Touches: O-06.

**Not listed as a candidate:** anything that tests topology changes under active deformation. That is the subject of the existing technical experiment (`experiments/rigging-skinning-morphing/`) and should not be duplicated here as a UX experiment.

---

## Open Questions

1. Is “how long does the deformation structure live” actually a structural axis, or an artifact of the collected cases? V2 suggests that it stands independently alongside the question “what does the Artist believe they are manipulating.”
2. **How does the Artist correct an automation without abandoning the concept that removed the work?** Raised in O-03, O-04, O-13, O-14 — convincingly answered nowhere.
3. Are there real examples where the separation between modeling/rigging was completely removed, rather than merely repaired afterward? O-16 is the closest case so far, but the mechanism is not established.
4. What do Artists do if they simply *avoid* topology changes after rigging? This avoidance behavior is invisible in documentation, but probably the most common response.
5. 2D rigging (Moho, Spine, Live2D) has assumptions that do not apply in 3D at all. Which ideas transfer?
6. How much of known DCC rigging complexity exists for film production in large teams — and is simply irrelevant for a single Artist working on a head Basemesh?
7. **When does direct manipulation stop helping?** O-15 is the only case where the authors themselves say that their more direct interaction method is sometimes inferior to the indirect one. If this is generally true, “more direct is better” is not a rule, but a task-dependent statement.
8. **What does an automation demand in return?** O-14 shows that AutoPosing requires certain control points in certain locations. Does every convenience at the top create a constraint at the bottom?
9. Does part of what is currently called “weighting quality” not belong in the weights at all? O-13 shifts it into volume, O-02 into a post-process.

---

## Condensation — From Research to Playground Questions

**Status:** Transition section, Discovery. No decisions, no verdicts, no implementation planning.
**Added:** V3

This section condenses Observations O-01 through O-16 into six tension axes and translates them into small, playable research questions. The Observations themselves remain unchanged; nothing above was retrofitted to fit.

The six axes are **research lenses, not a taxonomy**. They overlap, and the overlap is the useful part — it shows which individual question could expose several tensions at once.

---

### Axis 1 — Automation ↔ Correctability

**Core Question:** If the system generates a deformation itself — can the Artist correct it without abandoning the concept that just removed the work?

**Evidence from V2:** O-03 (estimated pivot, no correction mechanism beyond the gesture), O-04 (weights generated at bind time; the authors do not answer the correction question), O-13 (contact emerges automatically, without a control), O-14 (two documented system failures; additionally, the automation imposes requirements back on the rig), O-02 (the Artist can no longer see why it looks good).

**What the conventional workflow assumes:** Control comes from the Artist setting every value themselves. Automation is convenience that can be switched off if necessary.

**Alternative assumption to test:** Correctability is not an addition to automation, but its prerequisite. An automation whose result can only be influenced by repeating the gesture is not partial control, but no control at all.

**Genuinely unknown:** Whether the Artist even notices a wrong estimate if nobody shows them that a guess was made. Four systems stumble here; none documents what this feels like.

---

### Axis 2 — Direct Manipulation ↔ Parameter Control

**Core Question:** Is touching the form always better than setting a value — and if not, how does the Artist recognize the difference?

**Evidence from V2:** O-15 (the authors explicitly say that both alternate depending on the task and neither is superior), O-05 (the Smart Bone Dial is a *control* that someone built out of a manipulation primitive — movement goes in the opposite direction here), O-07 (Transpose: maximum directness, but no repeatability).

**What the conventional workflow assumes:** Controls are necessary, direct dragging is pleasant. More directness is always progress.

**Alternative assumption to test:** Direct and indirect are two working methods for different tasks, not two quality levels. Precision, repeatability, and symmetry might systematically favor the parameter side.

**Genuinely unknown:** Whether an Artist senses the transition point beforehand or only after direct manipulation has gone wrong.

---

### Axis 3 — Transient ↔ Persistent

**Core Question:** How long should a manipulation structure live — and who decides, the tool or the Artist?

**Evidence from V2:** O-11 (influence exists only during the gesture), O-03 and O-07 (structure emerges per gesture and disappears), O-04 and O-13 (structure is created once at bind time and then fixed), O-10 (Wires are persistent and maintained), O-08 (regenerated on every evaluation).

**What the conventional workflow assumes:** A deformer is an object. It is created, named, maintained, and deleted again. Transient tools are considered sketching tools.

**Alternative assumption to test:** Lifetime could be a property of the action rather than of the tool type — the same gesture could be disposable once and retained another time, without requiring two tools to learn.

**Genuinely unknown:** Whether the Artist even knows at the moment of the gesture whether they want to keep it. The decision may only become necessary afterward, while all systems studied demand it beforehand.

---

### Axis 4 — Result ↔ Origin

**Core Question:** Does the Artist edit what they see, or what produces it?

**Evidence from V2:** O-15 (touch the result, system solves backward to the control values), O-06 (the exact counterpart: the Artist edits layers of intent, never the final state — and the plugin explicitly warns against touching the final state in parallel), O-05 (the correction is recorded as a state, not formulated as a rule).

**What the conventional workflow assumes:** Both can be done simultaneously. You paint weights (origin) and sculpt Correctives (result) on the same character.

**Alternative assumption to test:** Origin and result are only consistent as long as both are not directly editable. O-06 is the only case in the collection that openly acknowledges this tension — and resolves it by forbidding direct access to the result.

**Genuinely unknown:** Whether an Artist still understands what happened in the origin when dragging the result — and whether that bothers or liberates them.

---

### Axis 5 — Geometry ↔ Material ↔ Intent

**Core Question:** In what language does the Artist think when deforming: points and influence regions, material behavior, or statements about the character?

**Evidence from V2:** Geometry — O-04, O-10, O-11 (handles, curves, radii). Material — O-12 (elastic response, defined in space rather than on the mesh), O-13 (volumes that touch). Intent — O-14 (center of mass, support point), O-05 (“if it is in this position, it should look like this”).

**What the conventional workflow assumes:** Deformation is geometry. Material and intent are special cases for simulation or animation.

**Alternative assumption to test:** These are three languages for the same action, and the choice of language changes what the Artist is even able to want. Someone thinking in radii formulates different intentions from someone thinking in volumes.

**Genuinely unknown:** Whether the difference is noticeable at all for small, local shape changes, or only becomes apparent for large deformations.

---

### Axis 6 — Modeling ↔ Articulating: Two Phases or One Process?

This axis gets more space because it is the only one directly connected to Manu's own practice.

**Core Question:** Can articulation be a means of *finding* the geometry — rather than merely consuming already-finished geometry?

**Evidence from V2:** O-16 (Tindall: “my modeling is never finished when I start articulating”; he describes modeling, articulating, and volume sculpting without a fixed order), O-09 (the problem has its own tool with an icon in established DCCs and still causes confusion), O-01 (transfer as repair *after* the break), O-08 (the only case that resolves the order structurally rather than repairing it), O-03 (deformation intent can be tested before rig data exists — and the result remains pure, editable geometry).

**Additional context** `[Artist Experience]`**:** Manu has first-hand experience with Mirai-/Weta-/Bay-Raitt-adjacent head workflows: controlled Basemeshes, planned facial loops, all-quads, deliberate pole placement, topology following expected deformation. The recurring dissatisfaction was not the effort, but the uncertainty — what the *correct* neutral topology is could not be determined with confidence before the first serious articulation.

This is experience, not a finding. It says nothing about whether planned topology is wrong, and nothing about whether older systems were better. It identifies an assumption.

**What the conventional workflow assumes:**

```
Modeling  →  lock topology  →  Rig  →  Deform
```

This chain assumes that the correct neutral form is recognizable *before* deformation. It also assumes that “neutral” is an exceptional state rather than merely the first one.

**Alternative assumption to test** `[Hypothesis]`**:**

```
Modeling  ↔  Articulating  ↔  Deforming  ↔  Revising Geometry
```

Two separate sub-hypotheses that do not stand or fall together:

* **6a (weak, cheap to test):** Articulation makes topology problems *visible* that are invisible on the resting mesh. This only requires the ability to bend — not that anything is preserved.
* **6b (strong, expensive):** Articulation can be part of *finding* the geometry — you change topology in the deformed state and continue working.

**Genuinely unknown:**

* Whether early bending actually produces different decisions or merely creates a reassuring feeling.
* Whether “neutral” is a useful starting state or merely one state among many. None of the 16 Observations asks this question; all assume a rest pose.
* Whether an Artist can actually model well in the deformed state, or whether the distortion corrupts their judgment.
* Whether the dissatisfaction “I only know it in motion” is accidentally the same for two very different practitioners (Tindall, Manu), or points to the same underlying cause.

**Boundary to the existing technical experiment:** V2 explicitly did *not* list topology changes under active deformation as candidates because `experiments/rigging-skinning-morphing/` owns that question. This remains correct for the mechanical question (“does the RigController survive the mutation?”). The question posed here is different: *Does it help the Artist think?* Two responsibilities, one subject. This is a deliberate clarification of the V2 statement, not a silent change.

---

## Playground Questions

Formulated as questions an Artist can answer through play. None assumes a specific implementation.

| #     | Axis | Question                                                                                                                        |
| ----- | ---- | ------------------------------------------------------------------------------------------------------------------------------- |
| PQ-1  | 1    | If the system chooses the pivot itself and gets it wrong — can I correct it without changing tools?                             |
| PQ-2  | 1    | Do I even notice that the system guessed?                                                                                       |
| PQ-3  | 2    | Are there tasks where I would rather set a value than drag the mesh — and do I recognize them beforehand or only afterward?     |
| PQ-4  | 3    | Do I already know at the moment of the gesture whether I want to keep it?                                                       |
| PQ-5  | 3    | Can the same action optionally be transient or persistent without requiring two tools?                                          |
| PQ-6  | 4    | If I drag the result and the system adjusts the cause — do I still understand what I changed?                                   |
| PQ-7  | 4    | Does it bother me if I am *not* allowed to touch the result directly?                                                           |
| PQ-8  | 5    | Does “pressing into material” feel different from “pulling points with a radius” — and at what deformation size do I notice it? |
| PQ-9  | 5    | Can I state an intention (“this point stays where it is”) instead of a movement?                                                |
| PQ-10 | 6a   | Do I see topology problems earlier if I can bend the form at any time?                                                          |
| PQ-11 | 6b   | Can I model meaningfully on the bent state — or does the distortion corrupt my judgment?                                        |
| PQ-12 | 6    | Is “neutral” a useful starting state or merely one of several?                                                                  |

---

## The Smallest Number of Experiments

The goal is not to build twelve questions individually, but to create a few situations in which several tensions occur simultaneously. Four setups cover all six axes.

| Experiment                                    | Axes     | Questions               |
| --------------------------------------------- | -------- | ----------------------- |
| EX-A — Bending Test                           | 6a, 3, 1 | PQ-10, PQ-4, PQ-1, PQ-2 |
| EX-B — Pull or Set                            | 2, 4, 1  | PQ-3, PQ-6, PQ-7        |
| EX-C — Influence as an Object or as a Gesture | 3, 5, 1  | PQ-5, PQ-8, PQ-9        |
| EX-D — Cut in the Bent State                  | 6b, 4, 6 | PQ-11, PQ-12            |

**Relationship to the CE candidates from V2:** EX-A incorporates CE-3, EX-C incorporates CE-1 and CE-2, EX-B touches CE-5. CE-4 remains independent and is unaffected by this condensation. The CE list above remains; it is the finer-grained collection, while the EX list is the bundled version.

---

### EX-A — Bending Test

**Research Question:** Does it change modeling decisions if the form can be bent experimentally at any time?

**Interaction Contrast:** Work on the resting mesh and only check the deformation later — versus: a bending gesture is always available and is discarded again when released.

**Smallest possible setup:** Head Basemesh. One gesture that bends from the click point; the system determines pivot and range itself. After release, the form returns. Nothing else — no storage, no weights, no skeleton.

**Observation:** Does Manu reach for it on his own, or forget that it exists? Does he bend before or after making a topology decision? After bending, does he change anything in the mesh that he otherwise would not have changed? Does the estimated pivot annoy him — and if so, does he try to correct it or merely repeat the gesture differently?

**Unknown afterward:** Everything about repeatability, animation, and retention. And whether the observed benefit comes from the test itself or from the novelty making him want to experiment.

---

### EX-B — Pull or Set

**Research Question:** For which tasks does an Artist reach for direct manipulation and for which for a value — and do they notice the transition point?

**Interaction Contrast:** The same deformation can be reached in two ways. One: touch the surface and drag it; the system determines the underlying values. Two: change a named value and watch.

**Smallest possible setup:** A single deformation with one or two named quantities (e.g. strength and direction). Both interaction methods visible simultaneously, both always allowed, no mode selection.

**Observation:** Which path does he choose first? Does he switch, and why? Does the switch happen during refinement, symmetry work, or repetition? After dragging, can he say which value changed — and does he even care?

**Unknown afterward:** Whether the finding depends on the task or on this particular deformation. And whether the visibility of the values produced the result — if they were invisible, the question would be different.

---

### EX-C — Influence as an Object or as a Gesture

**Research Question:** Is the difference between a persistent influence object and a transient influence radius even a difference for the Artist — and when does it become one?

**Interaction Contrast:** Variant A: a Handle that is placed, remains visible, and can be reused. Variant B: a radius that exists only while dragging. Same shape change, identical feedback.

**Smallest possible setup:** Head Basemesh, one soft displacement, two variants switchable within the same slot. Keep Signalling deliberately identical — otherwise the comparison measures presentation instead of behavior (see Research Map V1, confounding warning).

**Observation:** When does he miss the persistent version? The second time in the same location? During symmetry? Does management overhead accumulate in Variant A, and when does it become annoying? Does he describe the two variants in the same language or in different ones?

**Unknown afterward:** Whether a third possibility exists — turning the gesture into a persistent object only afterward. That would be the genuinely interesting variant and can only be formulated after A and B have been played.

---

### EX-D — Cut in the Bent State

**Research Question:** Can an Artist model meaningfully on the deformed state — and does that help them find the neutral form?

**Interaction Contrast:** Return to the resting state first, cut there, then bend again — versus: cut in the bent state and continue working.

**Smallest possible setup:** The most expensive of the four, necessarily following EX-A. It requires the mechanical side to work, and that belongs to the existing technical experiment, not this setup. The Playground part is only the question of whether working in the deformed state helps or harms judgment.

**Observation:** Where does he make the cut — where the deformation looks bad, or where the topology bothers him in the resting state? Are those the same places? Does he still treat the resting state afterward as “the correct mesh,” or as one state among several?

**Unknown afterward:** Practically the entire 6b axis. This setup can only open the question, not close it.

---

### Current Research → Playground Candidates

Candidates, not decisions. No KEEP / ITERATE / REJECT. Which of them are actually built and in what order is decided by Manu.

1. **Do I see topology problems earlier if I can bend the form at any time?** (PQ-10, EX-A) — the cheapest question with the greatest leverage; also touches transience and automation correction.
2. **Can I correct a system estimate without changing tools?** (PQ-1, EX-A) — the recurring finding from four independent systems, answered nowhere so far.
3. **Do I already know at the moment of the gesture whether I want to keep it?** (PQ-4/PQ-5, EX-A and EX-C) — challenges the assumption of all systems studied that this decision is made beforehand.
4. **When do I reach for the value instead of the form?** (PQ-3, EX-B) — the only axis where a source explicitly says that “more direct” is not consistently better.
5. **Do I still understand what I changed when I drag the result?** (PQ-6, EX-B) — counter-test to O-06, the only case that openly acknowledges the tension.
6. **Is “neutral” a useful starting state or merely one of several?** (PQ-12, EX-D) — the broadest question in the collection and the only one none of the 16 Observations asks at all.

---

## Sources / References

**Supported:**

* Bounded Biharmonic Weights — Jacobson, Baran, Popović, Sorkine-Hornung, SIGGRAPH 2011. https://igl.ethz.ch/projects/bbw/ · Paper PDF: https://igl.ethz.ch/projects/bbw/bounded-biharmonic-weights-siggraph-2011-jacobson-et-al.pdf · CACM version: https://cacm.acm.org/research/bounded-biharmonic-weights-for-real-time-deformation/
* Blender Pose Brush — Manual: https://docs.blender.org/manual/en/latest/sculpt_paint/sculpting/brushes/pose.html · Developer report: https://code.blender.org/2020/02/sculpt-mode-features-update/ · First presentation: https://www.blendernation.com/2019/12/12/preview-sculpt-mode-pose-brush/ · Dobarro on Sculpt Mode: https://pablodp606.artstation.com/blog/1vEn/new-blender-sculpt-mode-introduction
* Moho Smart Bones — Manufacturer: https://moho.lostmarble.com/pages/features · Classification as PSD equivalent: https://lesterbanks.com/2016/11/working-mohos-smart-bone-actions/ · Smart Bone vs. Smart Bone Dial: https://lostmarble.net/forum/viewtopic.php?t=35634
* ngSkinTools — Product: https://www.ngskintools.com/ · Layer concept: https://www.ngskintools.com/documentation/userguide/quickstart/ · Omission of Influence Locking: https://www.ngskintools.com/documentation/userguide/faq/ · Practical experience: https://rigmarolestudio.com/ngskintools-skinning-tips/
* Weight Hammer / Polygons after rigging: https://steamcommunity.com/app/243580/discussions/0/357287935556802103
* Wires — Singh & Fiume, SIGGRAPH 1998. Paper PDF: https://www.dgp.toronto.edu/~elf/.misc/1998-siggraph-wires.pdf · ACM: https://dl.acm.org/doi/10.1145/280814.280946
* Regularized Kelvinlets — de Goes & James, SIGGRAPH 2017. Paper: https://graphics.pixar.com/library/Kelvinlets/paper.pdf · ACM: https://dl.acm.org/doi/10.1145/3072959.3073595 · Blender implementation: https://developer.blender.org/D5634 · Patent version with the statement about discretization freedom: https://patents.google.com/patent/US10586401B2/en
* Implicit Skinning — Vaillant et al., SIGGRAPH 2013. ACM: https://dl.acm.org/doi/10.1145/2461912.2461960 · Author page: http://rodolphe-vaillant.fr/entry/31/implicit-skinning-real-time-skin-deformation-with-contact-modeli · Project page: https://www.irit.fr/~Loic.Barthe/implicitskinning.php
* Cascadeur — Overview and origins: https://www.cgchannel.com/2019/10/check-out-new-physics-based-animation-tool-cascadeur/ · AutoPhysics documentation: https://cascadeur.com/help/tools/physics_tools/autophysics · Documented failure cases and rig requirements: https://teletype.in/@cascadeur/sHa-pJUR3-H
* Direct Manipulation Blendshapes — Lewis & Anjyo, IEEE CG&A 2010. https://dl.acm.org/doi/10.1109/MCG.2010.41 · Author page with context: https://scribblethink.org/Work/DirectManipBlendshapes/directmanip.html
* The Art of Moving Points / Ozone — Book and chapter overview: https://ozone3d.com/products/art-of-moving-points/ · Review: https://lesterbanks.com/2013/04/hippydromes-art-of-moving-points-now-available/ · Tindall's statement on the modeling/articulating order: https://www.linkedin.com/posts/richardhurrey_model-articulate-and-volume-sculpt-in-activity-6879130051825299456-mu6e

**Not yet cross-checked (experiential knowledge, verify before reuse):**

* GATOR (Softimage), Maya `copySkinWeights`, Blender Data Transfer
* Delta Mush (Rhythm & Hues, SIGGRAPH 2014) / Blender Corrective Smooth
* ZBrush ZSpheres and Transpose / Transpose Master
* Houdini KineFX
* Soft Selection / Proportional Editing / Maya Soft Modification

---

## Related Documents

* `AGENTS.md` — repository-wide agent and documentation rules
* `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` — M1–M5, Discovery/Production, Artist Verdict
* `docs/design/artist_playground/UX_RESEARCH.md` — Interaction Grammar (different responsibility)
* `docs/design/artist_playground/EXPERIMENT_HOST.md` — Experiment/Variant/Slot vocabulary
* `experiments/rigging-skinning-morphing/` — technical rigging experiment, AD-005, FINDINGS (different responsibility)

