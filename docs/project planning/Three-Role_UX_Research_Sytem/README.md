# Mirai-Bastel — Three-Role UX Research System

**Purpose:** A three-role working system for discovering, prototyping and validating Mirai-Bastel's artist interaction language.

The system is deliberately **research-first**. We do not begin by assigning every function a shortcut. We first discover a small, coherent interaction grammar from which concrete bindings can later emerge.

---

## The Three Roles

| Role | Main question | Primary output |
|---|---|---|
| 🧪 **UX Researcher** | *What interaction principles are worth investigating?* | Comparisons, principles, hypotheses, research questions |
| 🛠️ **Interaction Dev** | *Can we prototype this cleanly?* | Small Playground prototypes, feasibility notes, implementation observations |
| 📋 **Playground Spec** | *Does it actually work when we play with it?* | Experiments, observations, KEEP / ITERATE / REJECT / UNKNOWN |

The roles are **different lenses, not a hierarchy**. They work in parallel and challenge one another.

The empirical Playground result is especially important, but it is not a replacement for research or technical reality.

---

## Shared Source of Truth

The central research document is:

**`docs/design/artist_playground/UX_RESEARCH.md`**

It is the shared idea/research space for the interaction language. Tweak is one research subject inside it, not the organizing principle of the whole system.

Supporting context includes:

- `docs/design/artist_playground/AP-03_PLAN.md`
- `docs/design/artist_playground/ARCHITECTURE_MAP.md`
- `docs/design/artist_playground/ROADMAP.md`
- relevant Production / WP-04 documentation
- actual current code and tests

The repository's durable rules in `AGENTS.md` always apply.

---

## The Starting Point

The current problem is bigger than Tweak:

> **Before we sensibly assign every function a key, mouse gesture, modifier and combination, we need to understand how the interaction system itself works.**

Otherwise the Slot/Input system can turn into a giant collection of individually reasonable bindings that collectively feel inconsistent.

So the first research question is not:

> "What key should Extrude use?"

It is:

> **"What rules should govern modes, actions, targets, gestures, modifiers and feedback?"**

---

## Current Research Direction

The broad research order in `UX_RESEARCH.md` is:

1. **Interaction Grammar**
2. **Transform Family**
3. **Selection Family**
4. **Topology / Modelling Family**
5. **Navigation / Viewport**
6. **Broader Artist Workflow**

This is a **direction, not a schedule or gate sequence**. We can jump back, compare alternatives or investigate an unexpected result whenever the evidence calls for it.

### Interaction Grammar questions

Examples include:

- sticky vs temporary
- press vs hold
- mode vs action
- selection vs hover target
- mouse gesture semantics
- modifier semantics
- context and precedence
- feedback / feedforward
- conflict handling

These are hypotheses to investigate, not decisions already made.

---

## The Working Loop

```text
OBSERVE
   ↓
CAPTURE PRINCIPLE / QUESTION
   ↓
FORMULATE HYPOTHESIS
   ↓
BUILD SMALLEST PLAYGROUND EXPERIMENT
   ↓
PLAY / TEST
   ↓
RECORD OBSERVATIONS
   ↓
KEEP / ITERATE / REJECT / UNKNOWN
   ↓
SYNTHESIZE
   ↓
ONLY THEN CONSIDER PRODUCTION
```

This is intentionally lightweight. The Playground is allowed to be messy. Production is not.

---

## Important Boundary

The three-role system does **not** replace the existing architecture or production workflow.

- Playground experiments may reuse existing production systems.
- Playground experiments may use adapters or deliberately ugly code.
- A successful experiment does **not** automatically become production architecture.
- Validated findings may later inform production design and ADRs.
- Existing validated systems should be reused or adapted rather than rebuilt.

In short:

> **Experiment freely. Promote carefully. Don't rebuild what already works.**

---

## Where to Start

### 🧪 Researcher
Read `ROLE_UX_RESEARCHER.md`, then open `UX_RESEARCH.md` and start with the **Interaction Grammar** questions.

### 🛠️ Dev
Read `ROLE_INTERACTION_DEV.md`. Do not invent a full interaction architecture before a research question exists. Prototype the smallest useful hypothesis.

### 📋 Playground
Read `ROLE_PLAYGROUND_SPEC.md`. Turn one hypothesis into a concrete, observable experiment using the existing Playground / Cube / Head reality where appropriate.

---

## What We Are Explicitly Not Doing Yet

- no final global shortcut table
- no final mouse layout
- no commitment that Move/Rotate/Scale must be sticky
- no commitment that temporary overrides must exist everywhere
- no commitment that Tweak is a tool, mode or interaction layer
- no premature production InputMap redesign
- no architecture freeze based on one prototype
- no artificial "Week 1 / Week 2" deadline for research

The goal is to **discover the language before formalizing the bindings**.

---

## Success

Success is not "we finished the shortcut table."

Success looks more like:

> **"I understand how Mirai thinks, so I can operate it almost without thinking about the interface."**

That means the artist learns reusable interaction principles instead of memorizing hundreds of arbitrary exceptions.

---

## Document Set

- `QUICK_START.md` — how to start and run the three-role workflow
- `ROLES_INDEX.md` — navigation and role overview
- `ROLES_COORDINATION.md` — collaboration and decision boundaries
- `ROLE_UX_RESEARCHER.md` — research role prompt
- `ROLE_INTERACTION_DEV.md` — implementation/prototyping role prompt
- `ROLE_PLAYGROUND_SPEC.md` — experiment/validation role prompt
- `docs/design/artist_playground/UX_RESEARCH.md` — shared UX research / idea space

**Last aligned:** 2026-09-12
