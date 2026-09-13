# Artist Playground — Experiment Host

**Status:** Canonical documentation
**Date:** 2026-09-13
**Purpose:** Define the Experiment Host, its terminology, and how it connects the Artist Playground with the Three-Role UX Research System.

---

## 1. Why This Document Exists

The Artist Playground is not only a place where experimental code runs. It is the controlled research environment in which Mirai-Bastel's interaction language can be experienced, compared, and evaluated before production decisions are made.

The **Experiment Host** is the small piece of infrastructure that keeps those experiments organized.

It exists to prevent the familiar experimental-project failure mode:

```text
variant_a/
variant_b_final/
variant_b_final2/
new_test/
new_test_REAL/
final_REAL2/
```

Instead, variants live together as explicit alternatives to the same research question, and their results are recorded.

> **An Experiment tests a question. A Variant is one possible answer. An ExperimentSlot is the container that lets us compare those answers.**

This document is the canonical explanation of those concepts.

---

## 2. The Experiment Host in the Three-Role System

The Experiment Host is shared infrastructure for the three research roles. It is not owned by one role.

```text
                 THREE-ROLE UX RESEARCH SYSTEM
                              │
             ┌────────────────┼────────────────┐
             │                │                │
       🧪 UX Researcher   🛠️ Interaction Dev   📋 Playground Spec
             │                │                │
             └────────────────┼────────────────┘
                              ↓
                    ┌──────────────────┐
                    │  EXPERIMENT HOST │
                    └──────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ↓                   ↓
                Variant A            Variant B
                    │                   │
                    └─────────┬─────────┘
                              ↓
                         Artist / User
                              ↓
                         Observations
                              ↓
                 KEEP / ITERATE / REJECT / UNKNOWN
                              ↓
                         UX knowledge
                              ↓
                later: production candidate
```

### Role responsibilities

**🧪 UX Researcher**

- frames the research question
- extracts principles from comparative research
- proposes hypotheses
- identifies meaningful alternatives and unknowns

**🛠️ Interaction Dev**

- identifies existing systems that can be reused
- builds the smallest technically honest variants
- reports technical constraints that may affect the UX result

**📋 Playground Spec Lead**

- turns the question into a playable experiment
- defines the variable, baseline, feedback and observation procedure
- compares variants
- records the result as KEEP / ITERATE / REJECT / UNKNOWN

**Manuel — Director / Synthesis**

- actually experiences the interaction
- provides the artist verdict
- decides what findings deserve further research
- decides when a validated finding is mature enough to become a production candidate

The Host provides the common structure. It does not replace these responsibilities.

---

## 3. Terminology — Keep These Concepts Separate

Terminology is deliberately precise because several of these words are also used in interaction design itself.

| Term | Meaning in the Experiment Host | Example |
|---|---|---|
| **Experiment** | A research object built around one question | `move_interaction` |
| **Variant** | One concrete implementation/answer being compared | Hold-X Move |
| **ExperimentSlot** | Technical container holding variants of an experiment | Move Interaction Slot |
| **Hypothesis** | What we expect before testing | "Hold-to-interact may feel more direct." |
| **Observation** | What actually happened while testing | "I paused before dragging." |
| **Decision** | Current research verdict for a variant | KEEP / ITERATE / REJECT / UNDECIDED |
| **Input** | Concrete input source | X, R, S, LMB |
| **Gesture** | Physical interaction pattern | click, drag, hold |
| **Mode** | An interaction state | Move Mode |
| **Action / Operation** | The thing performed on the scene | Move |
| **Tool** | A reusable interaction/production mechanism | Move Tool |

### Critical distinction

> **ExperimentSlot is a research-infrastructure term. It is not an input slot, action slot, tool slot, or mode.**

Do not use "slot" as a generic synonym for a place where a keyboard shortcut goes.

Likewise:

```text
Experiment ≠ Tool
Variant ≠ Mode
ExperimentSlot ≠ Input Slot
Action ≠ Input
Input ≠ Mode
```

The actual interaction grammar is researched separately. The Host merely gives us a stable place to test it.

---

## 4. What Is an Experiment?

An **Experiment** answers:

> **What are we trying to learn?**

It should be tied to a research question, not merely to a piece of code.

Good:

> How should a selected face enter and leave a Move interaction?

Too vague:

> Test Move.

The experiment may compare several variants. The experiment itself is therefore the research frame, not necessarily one implementation.

An experiment should normally have:

- a question
- a hypothesis or competing hypotheses
- a variable
- a baseline
- playable variants
- observations
- a result
- a next question

The amount of documentation can stay small. The important thing is that we know what the test was intended to teach us.

---

## 5. What Is a Variant?

A **Variant** is one concrete way of answering the experiment's question.

For example, the question might be:

> How should Move be activated?

Possible variants could be:

```text
Variant A
X held + drag
→ Move while dragging
→ release X = commit
```

```text
Variant B
X pressed
→ Move Mode becomes active
→ drag performs Move
→ separate input exits/commits
```

```text
Variant C
X pressed
→ Move Mode becomes active
→ first drag starts interaction
→ click/gesture commits
```

The variants should differ in the variable we are actually researching. If every variant changes several unrelated things, the result becomes difficult to interpret.

A variant is therefore **not automatically a mode**. A variant can contain a mode, a temporary interaction, a different gesture, or another implementation detail depending on the research question.

---

## 6. What Is an ExperimentSlot?

`ExperimentSlot` is the concrete Python container implemented by the Playground.

Its job is deliberately small:

- hold a group of experiment variants
- activate one variant
- deactivate the previous variant
- store a decision and notes for each variant
- generate/write a `decision.md`

It does **not** own a separate Tool System, Input System, or History System.

Conceptually:

```text
ExperimentSlot
│
├── Variant A
│     └── Decision + Notes
│
├── Variant B
│     └── Decision + Notes
│
└── Variant C
      └── Decision + Notes
```

This is intentionally a container, not a new application framework.

### Current implementation

The core implementation lives in:

```text
playground/experiment.py
playground/slot.py
playground/app.py
```

`Experiment` provides the minimal lifecycle hooks:

```python
activate()
deactivate()
update(dt)
draw()
```

`ExperimentSlot` manages the variants and their decisions. `PlaygroundApp` activates the selected variant and integrates it into the running Playground.

The implementation should remain as small as the research workflow requires.

---

## 7. Decision Vocabulary

Every variant starts as:

**UNDECIDED**

After testing, the result can be:

### KEEP

The tested variant is promising and should remain available as a useful reference/candidate for further research.

### ITERATE

The underlying idea is promising, but the tested variant has a weakness that should be investigated or changed.

### REJECT

The evidence argues against this variant under the tested conditions.

### UNKNOWN

The experiment did not answer the question clearly enough.

UNKNOWN is a valid research result. It is better than inventing certainty.

A KEEP decision is **not** an automatic Production decision.

```text
KEEP
  ↓
UX finding / candidate
  ↓
possible further research
  ↓
production review
  ↓
only then: Production
```

---

## 8. Observation Is Not Interpretation

The Host is useful only if the result remains interpretable.

Prefer:

> "I moved the cursor over the face, paused, then held X and dragged."

over:

> "Hold-X Move is intuitive."

The first is an observation. The second is an interpretation.

Both can eventually be useful, but they must not be silently merged.

A good experiment record can therefore contain:

```text
Observation
    ↓
Interpretation
    ↓
Result
    ↓
Next Question
```

This distinction is especially important when the three roles disagree about what an interaction means.

---

## 9. Example: Move Interaction

Suppose the current Playground behavior is:

```text
Click face
    ↓
Face selected
    ↓
Hold X + drag
    ↓
Face moves
    ↓
Release
    ↓
Commit
```

It is tempting to call this simply "Move Mode" or "the Move Action". For research purposes, we should describe the layers separately:

```text
Input      = X
Gesture    = hold + drag
Mode       = possibly a temporary Move interaction/state
Action     = Move
Experiment = how Move should be activated/interacted with
Variant    = this particular activation/gesture model
```

Whether the interaction is actually a persistent mode, temporary state, direct manipulation gesture, or some combination is **a research question** if that distinction matters to the UX.

The Host does not decide that terminology for us. It lets us compare concrete alternatives.

---

## 10. Typical Experiment Lifecycle

```text
1. QUESTION
      ↓
2. HYPOTHESIS / ALTERNATIVES
      ↓
3. DEFINE VARIABLE + BASELINE
      ↓
4. BUILD SMALLEST VARIANTS
      ↓
5. ACTIVATE VARIANT IN HOST
      ↓
6. PLAY / TEST
      ↓
7. RECORD OBSERVATIONS
      ↓
8. KEEP / ITERATE / REJECT / UNKNOWN
      ↓
9. UPDATE SHARED UX KNOWLEDGE IF WARRANTED
      ↓
10. DEFINE NEXT QUESTION
```

The Host supports steps 4–8. The Three-Role system provides the research context around them.

---

## 11. File Organization

Experiment variants live together under the relevant experiment area rather than as unrelated copies.

Current convention:

```text
playground/
  experiments/
    <family>/
      variant_a.py
      variant_b.py
      variant_c.py
      decision.md
```

Examples currently include the transform and selection experiment areas.

The exact filenames are less important than the rule:

> **Variants that answer the same research question belong together.**

The decision record belongs with the experiment so the implementation and the research result do not become disconnected.

---

## 12. What the Experiment Host Does NOT Do

The Host is deliberately **not**:

- a production input manager
- a global shortcut registry
- a final UX architecture
- a ToolManager replacement
- a second Selection system
- a History system
- a production state machine
- a persistence/database framework
- an automatic promotion pipeline
- a place where every possible future interaction must be abstracted in advance

If an experiment needs one of these things, first ask whether an existing validated system can be reused or wrapped.

If the answer is no, keep the new machinery local to the experiment until there is evidence that it deserves a broader abstraction.

---

## 13. Relationship to Production

The Playground follows this boundary:

```text
                  PRODUCTION
              validated systems
                     ↑
                     │
             conscious promotion
                     │
              UX candidate
                     ↑
                     │
              research finding
                     ↑
                     │
             Experiment Host
                     ↑
                     │
              Playground tests
```

The direction matters.

We do **not** build production architecture first and then try to discover what feels good inside it.

The Playground is where interaction hypotheses become playable.

Production is where validated findings are implemented cleanly after architectural review.

---

## 14. Reuse Existing Reality

The Experiment Host does not justify rebuilding systems that already work.

Before implementing an experiment, identify existing validated components such as:

- Camera
- Picking
- Selection
- Transform Operations
- Tool lifecycle
- viewport/runtime pieces
- other proven interaction infrastructure

Use or adapt them where appropriate.

The project rule remains:

> **Don't rebuild if it's already validated, documented and working. Nutzen oder adaptieren, nicht neu machen.**

An experiment may expose a limitation in an existing system. That is useful information. It does not automatically mean the existing system should be replaced.

---

## 15. How the Three Roles Should Use the Host

### UX Researcher → Host

The Researcher should normally hand the other roles something like:

```text
Research question:
How should Move activation behave?

Hypothesis:
A temporary direct-manipulation gesture may reduce mode overhead.

Compare:
A = hold + drag
B = persistent mode

Unknown:
Does temporary interaction remain predictable during repeated use?
```

The Researcher should **not** prescribe the class architecture.

### Interaction Dev → Host

The Dev should translate that into the smallest playable variants:

```text
Find reusable transform / selection / input infrastructure
        ↓
Build Variant A
        ↓
Build Variant B
        ↓
Expose both through the ExperimentSlot
```

The Dev should not turn the experiment into a speculative global interaction framework.

### Playground Spec → Host

The Playground Lead defines:

- what stays constant
- what changes
- what the artist should see
- how to reproduce the test
- what observations matter
- how the decision is recorded

The Host provides the mechanism for switching and recording the variants.

---

## 16. Relationship to Interaction Grammar

The Experiment Host and Interaction Grammar are related but not the same thing.

**Interaction Grammar** asks:

> What principles should Mirai use to express interactions?

Examples:

- mode vs action
- press vs hold
- sticky vs temporary
- target vs selection
- gesture semantics
- context
- precedence
- feedback

**Experiment Host** asks:

> How can we compare concrete answers to those questions without creating experimental chaos?

Therefore:

```text
Interaction Grammar
       ↓
research question
       ↓
Experiment
       ↓
Variants
       ↓
ExperimentSlot
       ↓
Artist test
       ↓
Observation / Decision
```

The Host is the laboratory apparatus. It is not the grammar itself.

---

## 17. Relation to the Artist Playground Manual

For actually running the Playground, see:

`playground/MANUAL.md`

The Manual answers questions such as:

- how to start the Playground
- how to load Cube / Head
- how to navigate
- how to use the currently implemented interactions
- how to change Playground input bindings

This document answers a different question:

> **What does the Experiment Host mean, and how should the research roles use it?**

Keep those two documents separate: the Manual is an operator guide; this document is the canonical Host/experiment model.

---

## 18. Quick Reference

When discussing a Playground test, use this vocabulary:

```text
QUESTION
  What are we trying to learn?

EXPERIMENT
  The research object around that question.

VARIANT
  One concrete answer/implementation being compared.

EXPERIMENT SLOT
  The container that holds those variants.

INPUT
  X / R / S / LMB / etc.

GESTURE
  Click / hold / drag / release / etc.

MODE
  A state of interaction, if the tested UX actually has one.

ACTION / OPERATION
  What happens to the scene.

OBSERVATION
  What actually happened.

DECISION
  KEEP / ITERATE / REJECT / UNKNOWN.

CANDIDATE
  A validated finding that may deserve further production consideration.
```

### One sentence to remember

> **An Experiment tests a question. A Variant is one possible answer. An ExperimentSlot only organizes and compares those answers.**

---

## Related Documents

- [Artist Playground Roadmap](ROADMAP.md)
- [Artist Playground Architecture Map](ARCHITECTURE_MAP.md)
- [Artist Playground Manual](../../../playground/MANUAL.md)
- [AP-03 Selection Lab Plan](AP-03_PLAN.md)
- [Three-Role UX Research System — Coordination](../../project%20planning/Three-Role_UX_Research_Sytem/ROLES_COORDINATION.md)
- [Three-Role UX Research System — Quick Start](../../project%20planning/Three-Role_UX_Research_Sytem/QUICK_START.md)
