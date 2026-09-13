# Artist Playground — Research Map V1

**Status:** Discovery — conceptual map of research space  
**Date:** 2026-09-13  
**Audience:** UX research team, Interaction Dev, Producer  
**Purpose:** Define the interaction grammar research universe and requirements for the Playground environment

---

## 0. Core Principle: This is a Question Map, Not a Backlog

**The Map is intentionally incomplete.**

- The Map is **not a task list or roadmap**.
- Empty cells are not deficiencies.
- There is no coverage requirement.
- There is no prescribed research order.
- A dimension does not necessarily require its own experiment.
- A research question may span multiple dimensions.
- **The Map itself is a working hypothesis** about the research space and may change through actual Artist Playground use.

Do not introduce status columns or artificial completeness metrics.

---

## 1. The Artist Playground Research Universe

The initial Playground is not merely a collection of isolated Transform/Selection tests.

### Playable Areas (simultaneously active, freely changeable)

- **Navigation** — orbit, pan, zoom, focus
- **Selection** — pick, replace, add, remove, toggle, box, lasso, paint
- **Transformation** — move, rotate, scale; component-level variants
- **Topology / Modelling** — extrude, inset, bevel, connect, loop insert, etc.

### Research Intent

The intended workflow is:

> **Actually model with the program and gradually discover which interaction settings feel most natural and comfortable.**

Multiple active variants exist to support **free artist playing**, not to create a combination-test matrix.

This does not mean systematically testing every combination. It means building a usable workshop where the artist can play naturally while research happens through observation.

---

## 2. Research Dimensions — Universal Questions

These five dimensions apply to every operation in the application, from Select to Extrude to viewport navigation.

### Target Resolution

**What determines what an operation acts upon?**

- Current Selection
- Hover target
- Explicit Pick at gesture time
- select-then-verb / non-modal interaction (Wings/Nendo style)

**Why it matters:** Upstream of almost everything else. Shapes lineage. Determines how Tweak, Extrude, and every family interfaces with selection.

**Current state:** Documented as open question in `UX_RESEARCH.md` §6 and §11. Tweak variants exist but playable status unknown.

### Activation

**What starts an operation?**

Do not reduce to specific key bindings. The researchable question is the activation model:

- Press (one-time commitment)
- Hold (key remains down)
- Drag / implicit start (no explicit press)
- Context menu / select-then-verb

**Why it matters:** The boundary between intentional and accidental operation.

**Current state:** Host §5 documents three Move activation variants (A/B/C). Played, verdict status unknown.

### Termination

**What ends an operation?**

- Release (key release commits)
- Click (explicit click commits)
- Explicit Exit (Escape or mode change)
- Context change (another operation starts)

**Related question:** How do Commit and Cancel relate? Are Hold Activation and Release Termination potentially physically coupled?

**Important:** Do not force all variants into a perfectly separable taxonomy. Host §5's Move variants suggest Activation and Termination may be inseparable for hold-style gestures.

**Current state:** Host §5 Variants A/B/C differ in termination; verdict status unknown.

### Residue

**What survives an operation?**

- Selection (persists unchanged, or changes)
- Active Tool (stays armed or resets)
- Axis constraint (persists or clears)
- Component Mode (persists or resets)
- Hover State (what happens to it)

**Why it matters:** Unresearched but load-bearing. Bad residue silently degrades every Setting, and the artist misattributes it to whatever is currently focal. Affects the feel of repeated operations and transitions between them.

**Current state:** Completely unexamined. Directly observable in whatever variants run.

### Composition

**What can change during an active operation without ending it?**

- Axis (X, Y, Z constraint)
- Transform Type (Move ↔ Rotate ↔ Scale)
- Snapping (on/off or modes)
- Temporary overrides
- Component mode changes

**Hypothesis:** Composition may turn out to be **family-specific rather than universal**. What makes sense for Transform may not make sense for Topology.

**Current state:** Documented in `UX_RESEARCH.md` §3–4 as temporary overrides. Research state unknown.

---

## 3. Cross-Cutting Research Questions

These are not dimensions in the same sense. They are questions that apply globally or properties that affect all observations.

### Signalling

**What does the system communicate before, during, and after an interaction?**

- Target indication (is it clear what will be affected?)
- Mode indication (is the current interaction state obvious?)
- Feedback during operation (is progress visible?)
- Residue indication (what survived?)

**Why it matters:** Signalling can become a confounding variable when comparing variants. If behaviour and feedback change simultaneously, the observation may be difficult to interpret.

**Guard:** Hold signalling constant across a comparison, or vary it deliberately and separately.

### Cancel / Undo Continuity

**Is cancelling during an operation conceptually the same thing for the artist as undoing after a committed operation?**

- Escape during move vs. Undo after move
- State recovery: does Cancel leave the world where the artist expects?
- Safety: how safe does backing out feel?

**Why it matters:** Getting this wrong makes the artist play timidly. An artist unsure how to back out explores less, notices less.

**Current state:** Completely unexamined in UX research. History exists in production (MeshStateCommand). Your workflow examples depend on this working well.

### Component Mode

**How should the artist move between Vertex / Edge / Face contexts?**

- Is it a persistent mode with dedicated keys?
- Is it inferred from what you hover over?
- Is it a temporary override?
- Is it a component-family modifier?

**Why it matters:** Every operation family needs this question answered, but the answer may differ per family.

**Current state:** Mentioned in `ARCHITECTURE_MAP.md` and `UX_RESEARCH.md` §9 as a context layer, but no research question articulated.

---

## 4. Research Method: Focus / Setting / Observation

### Focus

The one interaction question the artist is consciously paying attention to at the moment.

Only one Focus at a time.

### Setting

All other currently active variants and states. The state of the workshop.

**The Setting is NOT itself a research object** and is not something to be systematically tested as a combination.

Change the Setting freely at any moment outside of direct variant comparisons.

### Observation

What actually happens during play.

Every observation has a **subject** — the dimension it is about. Usually the subject equals the Focus. Sometimes it doesn't, and that off-axis case is valuable.

### Focal Evidence

Evidence deliberately gathered while paying attention to the current Focus.

Weight: strong, interpretable.

### Incidental Evidence

Evidence discovered while investigating something else.

Weight: valuable, but confounded by the current Setting.

**Rule:**
> Incidental evidence can raise the priority of a question, but does not automatically close it.

### Research Discipline

When directly comparing two variants of the same Focus, avoid changing the Setting at the same time. This keeps the comparison interpretable.

Outside that direct comparison moment, the artist is free to change settings and play naturally.

---

## 5. Initial Research Attention Areas

These are areas offering high insight-to-work ratio. They are not a ranked schedule; they are candidates for Focus rotation.

### A. Target Resolution — What acts?

**Why now:**
- Upstream of almost everything else
- Determines Windows/Nendo lineage (select-then-verb) vs Blender lineage (direct/modal tools)
- Shapes how Tweak, Extrude, and every operation interfaces with Selection

**What we'd learn:**
- Whether hover-as-target is livable
- Whether artists prefer explicit selection or hover-mediated directness
- The seam between persistent Selection and momentary Hover

**Unlocks:**
- Transform family research
- Any Tweak-like workflow
- The fundamental lineage question

**Requirement:**
- Hover targeting must be visually obvious

---

### B. Residue — What survives?

**Why now:**
- Completely unresearched but load-bearing
- Bad residue silently poisons every Setting
- Unlocks all workflow research

**What we'd learn:**
- Should Selection survive a Transform?
- Should the tool stay armed?
- How does residue affect the feel of repeated operations?

**Unlocks:**
- All workflow research
- Every transition between operations

**Requirement:**
- None; observable in whatever variants run

---

### C. Modifier Semantics — AP-03 Phase 2 Harvest

**Why now:**
- Already built and playable
- May already have observations attached
- Foundation for consistency audit across the grammar

**What we'd learn:**
- Whether modifier-based set semantics (Shift=Add / Ctrl=Remove / Alt=Toggle) beat toggle-only
- How modifier consistency should work across families

**Unlocks:**
- Evidence base for cross-family consistency

**Requirement:**
- Access to Phase 2 verdict records or observations

---

### D. Cancel / Undo Continuity — Can I back out safely?

**Why now:**
- Completely unexamined
- Makes the artist play timidly if wrong
- Foundational for all workflow research

**What we'd learn:**
- Is Escape mid-operation the same concept as Undo after commit?
- What state does Cancel leave?
- How safe does backing out feel?

**Unlocks:**
- Confident play
- Workflow research (your Select → Move → Cancel → Move → Undo scenario depends on this)

**Requirement:**
- Cancel must be reachable in the Playground

---

## 6. Further Research Questions

Important and unexamined, but can defer to later phases:

| Question | Family | Current Status |
|---|---|---|
| **Transition between operations** | Cross-cutting | UNDECIDED |
| **Hover during an active operation** | Target Resolution | UNDECIDED |
| **Empty space interaction** | Select | UNDECIDED |
| **Navigation during modelling** | Navigate + others | UNKNOWN |
| **Failure and impossibility** | Cross-cutting | UNDECIDED |

---

## 7. Work-Like Situations

These are realistic artist-workflow scenarios. When played in the Playground, they naturally expose grammar weaknesses that isolated operations hide.

**Purpose:** Generate new research questions through realistic play.

**Not:** Prescribed test sequences. No coverage requirement.

### Simple continuation

```
Select → Move → Select another → Move
```

Reveals: Residue, transition feel, whether selection and hover interfere.

### Family boundary

```
Select face → Extrude → Move → Extrude again
```

Reveals: Whether the grammar survives family boundaries, residue across Topology/Transform, transition cost.

### Backing out

```
Select → Move → Cancel → Move again → Undo
```

Reveals: Cancel/Undo continuity, whether Cancel leaves the world where the artist expects, residue after cancel.

### Ambiguous target

```
A selected
Hover B (which is inside A's bounds or overlaps A)
Act on B
```

Reveals: Target resolution priority, hover vs. selection precedence, accidental vs. intentional activation.

### Repeated same operation

```
Move → Move → Move (with different selections)
```

Reveals: Residue, whether re-arming is necessary, tool persistence vs. mode switching.

### Navigation during work

```
Select → Move → pan/orbit to see better → continue Move
```

Reveals: Navigation/operation coexistence, whether the workflow is interruptible, whether Navigation and Modelling should share one grammar.

---

## 8. Existing Work Mapped Into the Research Space

| Existing Work | Maps To | Status |
|---|---|---|
| AP-03 Phase 0–1 — baseline selection | Select: Target Resolution | ? (verdict unknown) |
| AP-03 Phase 2 — Shift/Ctrl/Alt vs Toggle | Select: modifier semantics | ? (played, verdict status unverified) |
| Host §5 Variants A/B/C (Move activation) | Transform: Activation × Termination | ? (built, verdict unknown) |
| Current Playground behaviour | Transform: de facto Setting | baseline |
| AP-02.5 Presentation Lab | (outside grammar map) | complete |
| `UX_RESEARCH.md` Tweak variants | Select/Transform: Target Resolution | ? (documented, playable status unknown) |
| `UX_RESEARCH.md` §11 LMB conflict | Select × Transform: Target Resolution × Activation | UNDECIDED (identified but not built) |
| Topology L/R keys, Alt+R | Topology: bindings | (evidence of drift, not a research question) |
| AP-03 Phase 6 (Feedback) | Signalling (cross-cutting) | planned |
| AP-05 Topology Lab | Topology family | deferred |
| Integration Lab input-routing defect | Navigate: coexistence with operations | UNKNOWN (blocking evidence) |

**Key observation:** The distinction between `built`, `documented`, `played`, and `decided` is unclear from the repository. Specific unknowns:

- Have Phase 1 and Phase 2 verdicts been recorded in `decision.md`?
- Were Tweak variants built in the production Playground, or only documented?
- What is the actual playable state of the Host-managed experiments?

---

## 9. Principle: built ≠ decided

A variant may exist, run, be used repeatedly, and be well-understood without having a verdict.

A verdict should emerge from research, not from the existence of an implementation.

**Verdict states:**
- `UNDECIDED` — not decided yet
- `UNKNOWN` — investigated but currently unclear
- `KEEP / ITERATE / REJECT` — actual research verdict  
- `BLOCKED` — investigated, but a specific missing question prevents judgement (includes pointer to blocking question)

---

## 10. Navigation Must Be Part of the Initial Research Universe

Navigation is not a later add-on.

### Open questions

- Can Navigation and Modelling share one coherent interaction grammar?
- Or are two different but internally coherent grammars better?
- What happens when the artist needs to orbit while moving?
- How should RMB/MMB behave if they are also used for modelling?
- What is the input-routing precedence?

### Current state

The Integration Lab has an unresolved input-routing defect where `on_mouse_press` in TopologyWindow returns early and swallows RMB/MMB, preventing orbit/pan while a tool is active.

This is blocking evidence for this research question, not a bug to fix in isolation.

---

## 11. Playground Capability Requirements

Frame these as **research requirements**, not implementation instructions.

The Interaction Dev must determine what the current Host already supports and what actually needs to change.

### Essential for the next research phase

- **Multiple experiments active simultaneously** — the Focus/Setting model requires this
- **Independently switchable variants** — change a variant on the fly, without restarting
- **Setting remains playable across changes** — variants switch during a running session
- **Four families playable together** — Navigation, Selection, Transform, Topology can be used in realistic sequence
- **Setting is technically recoverable** — observations can later be understood in context

### Potentially useful later

- **Focus indicator** — optional, aids recording
- **Observation capture with Setting** — full provenance record
- **Behavioural traces** — what moved, where did the artist pause

### Explicitly not required

- Settings preset system
- Scenario runner
- Cross-experiment dependency system
- Observation database
- Extensive research automation
- Design of Production InputMap

---

## 12. Research Risks

### The Map invites completion

Empty cells read as deficiencies. Coverage is not success.

**Guard:** Explicitly reject any pressure to "fill the map".

### Signalling may confound observations

Feedback changes will be confused with behaviour changes.

**Guard:** Hold signalling constant across a comparison, or vary deliberately and separately.

### Habituation

Whichever variant runs as default will win by familiarity.

**Guard:** Record first-contact observations separately from after-habituation ones.

### Decision by drift

Incidental evidence may silently become a decision.

**Guard:** Every dimension stays UNDECIDED until focal evidence supports a verdict.

### The Map itself may be wrong

Specific hypotheses to test against reality:

- Composition may be family-specific, not universal
- Activation and Termination may be inseparable for hold-style gestures
- Residue may matter more than Activation, making sticky-vs-temporary research secondary
- Lineage question may be answerable only through real play, not research

**Guard:** Revise based on evidence, not intuition.

### Navigation/modelling independence

Whether one grammar should span both, or whether two coherent grammars are better.

**Currently:** Unknown. Only answerable through play.

---

## 13. Handoff to Interaction Dev / Producer

### Research Intent

The Playground should function as an open **Artist Workshop / research environment** where:

- Multiple UX areas (Navigate, Select, Transform, Topology) are simultaneously playable
- The artist can freely change variants while doing real modelling work
- Observations emerge through natural play, not from prescribed tests
- The Focus / Setting / Observation discipline guides research without mechanizing it

### Dev Question

**Does the current Experiment Host already support this research mode?**

If not:

**What is the smallest technical extension required to support it?**

### Dev Process

1. **Inspect** the existing implementation (`playground/experiment.py`, `playground/slot.py`, `playground/app.py`)
2. **Identify** what infrastructure already exists for multiple simultaneous variants
3. **Reuse** validated systems — don't rebuild
4. **Extend minimally** if anything is missing
5. **Verify** that the extended Host can be used for the next research phase

Enforce the project rule:

> **Don't rebuild if it's already validated, documented and working. Nutzen oder adaptieren, nicht neu machen.**

### Relevant References

- `EXPERIMENT_HOST.md` — current Host design
- `playground/experiment.py`, `slot.py`, `app.py` — implementation
- `AGENTS.md` — project discipline
- `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` — collaboration model
- `UX_RESEARCH.md` — thinking space (note: dimensions there are coarser than this map)
- `ROADMAP.md` — current build status

---

## 14. What NOT To Do

Do not modify code.

Do not implement new experiments.

Do not design Production architecture.

Do not redesign the InputMap.

Do not create a complete shortcut/binding list.

Do not define systematic combination tests.

Do not decide Selection, Navigation, Transform, or Topology behaviour prematurely.

Do not force a `decision.md` merely because a variant has been built.

Do not create an Observation Database.

Do not create a Settings preset system.

Do not create a detailed implementation plan for the Host.

---

## Next Steps

This map defines the research space and requirements.

The next role (Interaction Dev / Producer) inspects the actual repository and determines the minimal technical needs.

After that, research can begin: choose one or two Focus areas from §5, gather the existing experiment material, enter the workshop with Focus/Setting/Observation discipline, and let observations point toward the next questions.
