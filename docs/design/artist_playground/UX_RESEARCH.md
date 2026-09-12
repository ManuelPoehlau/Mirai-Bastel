# Artist UX — Research / Idea Space

**Status:** Open research — no implementation decision  
**Area:** Artist Playground  
**Date:** 2026-09-12

---

## Purpose

This document is the open idea and research space for the **interaction and UX language of Mirai-Bastel**.

It started as research into Tweak, but the first Playground experiments exposed a larger problem:

> **Before we can sensibly assign every function a key, mouse gesture, modifier and combination, we need to understand the interaction system as a whole.**

Otherwise we risk designing hundreds of individual shortcuts independently and discovering much later that they conflict, feel inconsistent, or constantly force the artist out of the current workflow.

This document therefore deliberately moves **one level up**. Tweak remains an important experiment, but it is now treated as one test case for a broader artist interaction language.

This is **not** a production specification and not an implementation plan. It is a place to collect observations, ideas, hypotheses, comparisons and questions before making architectural or UX decisions.

The Artist Playground is the place to build and play with these variants. Findings may later become validated UX decisions, but nothing here automatically becomes Production architecture.

---

# 1. The Problem We Need to Solve First

The initial reaction while experimenting with the Slot system was essentially:

> **"Uff. Where do we even start? This is going to take forever if every function needs to be assigned sensible keys, mouse inputs and combinations individually."**

That is probably the wrong level of attack.

The goal is not to create a giant shortcut table first.

The goal is to discover a **small set of interaction principles** from which many individual functions can derive naturally.

Instead of asking:

```text
Where does function X get its key?
Where does function Y get its modifier?
What does Shift+Alt+LMB do here?
```

we should first ask:

```text
What is the current interaction state?
What does a held key mean?
What does a pressed key mean?
What does a mouse drag mean?
What is temporary?
What is sticky?
What can override what?
How does the artist move between actions without losing flow?
```

If those rules become coherent, individual tools become much easier to map.

---

# 2. Core UX Hypothesis

The working hypothesis is:

> **Mirai should have a small, composable interaction language rather than a huge collection of unrelated shortcuts.**

The artist should learn principles and patterns, not hundreds of exceptions.

A useful mental model may eventually look something like:

```text
                 ARTIST INTERACTION
                         │
          ┌──────────────┼──────────────┐
          │              │              │
        STICKY       TEMPORARY       CONTEXT
         MODE         OVERRIDE       / TARGET
          │              │              │
       Move           Scale            Hover
       Rotate         Rotate           Selection
       Scale          Axis             Component
       ...            ...              ...
```

This is deliberately only a hypothesis. The Playground exists to find out whether such a language actually feels good.

---

# 3. Sticky Modes

A particularly promising idea is the distinction between **press once** and **hold temporarily**.

Example:

```text
M pressed
    ↓
MOVE MODE becomes active / sticky

S held
    ↓
temporarily SCALE

S released
    ↓
back to MOVE
```

The important idea is not the exact letters. It is the interaction pattern:

> **A committed/sticky mode establishes the current workflow; a held input temporarily overrides it.**

Potentially:

```text
MOVE sticky
 ├── S held → temporary Scale
 ├── R held → temporary Rotate
 └── X held → temporary X constraint
```

This could dramatically reduce the need for separate commands for every combination.

### Why this matters

It gives us a potential answer to the shortcut explosion:

```text
Tool × Modifier × Context × Mouse Gesture
```

does not necessarily need a unique binding for every combination.

Instead, the system could have reusable rules such as:

```text
ACTIVE MODE
    + temporary override
    + target/context
    + gesture
```

Again: this is a UX hypothesis, not an architecture decision.

---

# 4. Temporary Overrides

Temporary overrides may be more important than individual tools themselves.

Example:

```text
Active: Move

hold R
    → Rotate temporarily

release R
    → Move again
```

Possible future uses:

- transform type
- axis constraint
- selection mode
- navigation
- snapping
- component mode
- Tweak behavior
- topology operations

The question is whether the same principle can work consistently across very different contexts.

A successful general rule would be much more valuable than another individual shortcut.

---

# 5. Tweak as the First Test Case

Tweak remains an important research subject, but now as **one experiment inside the larger UX system**.

Its core idea is direct manipulation:

> Hover the component I want to affect, then manipulate it directly — without first making it the global selection.

Example:

```text
Selection = A

Cursor → B
Tweak B

→ B changes
→ Selection remains {A}
```

The cursor identifies the target. The current global Selection is not required as the transform source.

### Initial variants

**Keyboard-driven:**

```text
Hover → T + Drag  → Move
Hover → R + Drag  → Rotate
Hover → S + Drag  → Scale
```

**Mouse-driven:**

```text
Hover → LMB + Drag → Move
```

The exact input mapping is deliberately open. The purpose is to discover the underlying interaction pattern, not to lock in letters prematurely.

---

# 6. Selection and Manipulation Are Different Concepts

One important distinction emerging from Tweak:

```text
Selection = persistent global state
Hover     = current cursor target
Tweak     = direct manipulation of target
```

These should not automatically be collapsed into one state.

Example:

```text
A selected
B hovered

Tweak B

Expected:
    B moves
    A stays selected
```

This may become a broader UX principle: **the thing currently being acted upon does not always have to become the global selection.**

Questions:

- When should an action use Selection?
- When should it use Hover/Hit Target?
- Can an operation explicitly choose between them?
- Can the same transform concept support both workflows without confusing semantics?

---

# 7. Sticky vs Direct / Temporary Interaction

We should distinguish at least two different kinds of interaction:

### Persistent workflow

```text
activate Move
    ↓
Move remains active
    ↓
perform several actions
```

### Direct temporary workflow

```text
hover target
    ↓
hold input
    ↓
perform action
    ↓
release
    ↓
return to previous state
```

Tweak may eventually combine both ideas:

```text
Tweak mode active
    ↓
hover B
    ↓
hold Scale
    ↓
scale B
    ↓
release
    ↓
Tweak mode remains active
```

This is precisely the kind of composability that is worth testing before designing dozens of individual bindings.

---

# 8. Mouse and Keyboard as Interaction Layers

Rather than treating keyboard and mouse bindings as completely separate systems, investigate whether they can act as layers over the same interaction state.

For example:

```text
Mode: Move
Target: hovered vertex
Gesture: drag

Keyboard modifier changes operation
Mouse button starts gesture
```

This could allow a relatively small vocabulary to express many operations.

But we must test whether this remains intuitive or becomes "modifier soup".

### Warning sign

If an interaction requires remembering:

```text
Ctrl + Alt + Shift + RMB + Space
```

for ordinary modelling, we have probably failed the UX experiment. 😄

The system should reduce combinations where possible rather than celebrating them.

---

# 9. Context and Target

Inputs may not have one universal meaning independent of context.

Potential context layers:

```text
Current Mode
Current Component Mode
Hovered Target
Current Selection
Current Gesture
Temporary Modifiers
Navigation State
```

The challenge is to make this contextual behavior **predictable**, not magical.

For example:

```text
Hover vertex → vertex operation
Hover edge   → edge operation
Hover face   → face operation
```

The artist should ideally understand why the system chose an action.

---

# 10. Feedback Is Part of the Interaction

A coherent interaction system also needs coherent feedback.

Potential visual states:

```text
Selected
Hovered
Active Target
Active Tool
Temporary Override
Constraint
Dragging
```

If the system changes behavior based on context but does not communicate that context, the result will feel unpredictable.

Therefore UX research should always ask:

> **What does the artist see before, during and after the gesture?**

---

# 11. Tweak-Specific Research Questions

These remain useful, but are now subordinate to the larger UX research.

### Direct manipulation

- Does direct manipulation feel faster than Select → Transform?
- Is hover targeting reliable enough without a click?
- Is the target obvious before movement starts?
- Is accidental manipulation a problem?

### Component scope

- vertex
- edge
- face
- object/element level later

### Transform semantics

- screen/camera-plane movement
- world-axis movement
- surface direction
- normal-based movement
- inferred depth

### Soft influence

Could direct manipulation eventually become a lightweight modelling brush?

This is speculative and should remain separate from the basic interaction question.

### LMB conflict

Mouse Tweak using plain LMB raises an important general UX question:

> Can the same mouse gesture have different meanings based on the current interaction context without becoming ambiguous?

Possible experiments:

- context-sensitive LMB
- temporary modifier
- temporary Tweak mode
- different mouse button
- press/drag timing
- hover changes the meaning of drag
- explicit tool activation

Do not solve this architecturally before testing the interaction.

---

# 12. Inspiration / Comparison

Relevant systems to investigate include:

- Wings 3D
- Mirai / N-World style interaction
- Silo
- 3ds Max
- ZBrush
- Maya
- Blender
- other artist-centric modelling tools

The purpose is **not** to copy shortcut layouts.

Instead ask:

- What interaction principle is behind this behavior?
- Why does it feel fast?
- What state does the application remember?
- What is temporary?
- What is sticky?
- How are conflicts avoided?
- How much does the artist have to remember?

A good finding is therefore something like:

> "This application uses temporary overrides to avoid tool switching."

not:

> "We should copy Ctrl+Shift+something."

---

# 13. What We Should NOT Do Yet

Do **not** begin by creating a complete global shortcut table.

Do **not** attempt to assign every current and future function a final key.

Do **not** freeze the InputMap around today's Playground experiments.

Do **not** create architecture merely because a prototype needs a convenient implementation.

Do **not** optimize individual tool bindings before understanding the interaction grammar.

Instead:

```text
Observe
   ↓
Capture principle
   ↓
Build tiny Playground experiment
   ↓
Play
   ↓
Compare
   ↓
Keep / Iterate / Reject / Unknown
   ↓
Only then formalize
```

---

# 14. Proposed UX Research Order

A sensible top-down research sequence may be:

### A — Interaction Grammar

First determine the basic vocabulary:

- sticky vs temporary
- press vs hold
- mode vs action
- selection vs hover target
- mouse gesture semantics
- modifier semantics
- context
- feedback

### B — Transform Family

Use Move / Rotate / Scale as the first playground for the grammar.

Test:

- sticky tools
- temporary overrides
- axis constraints
- direct manipulation
- selection-based vs hover-based transforms

### C — Selection Family

Then test how the grammar applies to:

- Replace
- Add
- Remove
- Toggle
- Box
- Lasso
- Paint
- component modes

### D — Topology / Modelling Family

Only after the interaction grammar becomes clearer:

- Extrude
- Inset
- Bevel
- Connect
- Cut
- Bridge
- etc.

### E — Navigation / Viewport

Then investigate whether navigation can use the same principles without creating conflicts.

### F — Broader Artist Workflow

Eventually apply the principles across:

- Modelling
- Rigging
- Skinning
- Morphing
- Animation
- Painting

This is not a rigid milestone plan. It is a research direction.

---

# 15. The Bigger Goal

The eventual goal is not:

> "Mirai-Bastel has a really clever shortcut system."

It is:

> **"I understand how this application thinks, so I can operate it almost without thinking about the interface."**

The artist should develop **muscle memory for principles**, not memorization of arbitrary commands.

That is much closer to the original Mirai / Wings / artist-tool spirit we are looking for.

---

# 16. Experiment Discipline

For each UX experiment:

1. Capture the interaction idea.
2. State the hypothesis.
3. Build the smallest possible Playground variant.
4. Play with it on Cube and Head.
5. Compare it against the current baseline.
6. Record what feels good/bad/confusing.
7. Decide: **KEEP / ITERATE / REJECT / UNKNOWN**.
8. Only promote validated findings toward Production later.

The Playground is allowed to be messy.

Production is not.

---

# 17. Current Non-Decisions

Nothing below is currently fixed:

- final shortcut layout
- final mouse layout
- whether Move/Rotate/Scale are sticky
- exact temporary override semantics
- exact meaning of T/R/S/M
- whether Tweak is a tool, mode, interaction layer, or combination
- whether Mouse Tweak uses plain LMB
- whether Hover can act as an operation target without Selection
- exact component-mode behavior
- exact feedback appearance
- exact navigation bindings
- Production input architecture

---

# 18. Current Working Hypothesis

The most important current hypothesis is now broader than Tweak:

> **We should discover Mirai-Bastel's interaction language before attempting to finalize Mirai-Bastel's individual input bindings.**

Tweak is one of the first useful test cases because it exposes several important questions at once:

```text
Hover target
    +
Direct manipulation
    +
Selection independence
    +
Temporary modifiers
    +
Sticky mode potential
    +
Mouse/keyboard interaction
```

That makes it a good Playground experiment — but **not the place where the whole UX system should begin or end**.

---

## Related Documents

- `docs/design/artist_playground/AP-03_PLAN.md` — Selection Lab plan
- `docs/design/artist_playground/ARCHITECTURE_MAP.md` — Playground architecture boundaries
- `docs/design/artist_playground/ROADMAP.md` — broader Playground roadmap
- `AGENTS.md` — repository-wide agent/documentation rules
