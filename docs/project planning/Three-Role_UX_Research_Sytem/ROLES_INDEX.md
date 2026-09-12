# Three-Role UX Research System — Index

## What This System Is

Three separate AI conversations provide three different lenses on the same Mirai-Bastel UX research:

```text
🧪 Researcher  → discovers principles and questions
       ↓
🛠️ Dev        → prototypes hypotheses
       ↓
📋 Playground  → tests what actually works
       ↘       ↙
        synthesis
```

The flow is **not strictly sequential**. All three roles can work in parallel and send findings back to the shared research document.

---

## The Six Files

| File | Purpose |
|---|---|
| `README.md` | Overall system and philosophy |
| `QUICK_START.md` | Practical setup and first-session workflow |
| `ROLES_INDEX.md` | This navigation guide |
| `ROLES_COORDINATION.md` | Collaboration, boundaries and handoffs |
| `ROLE_UX_RESEARCHER.md` | Research role prompt |
| `ROLE_INTERACTION_DEV.md` | Development/prototyping role prompt |
| `ROLE_PLAYGROUND_SPEC.md` | Playground/validation role prompt |

Shared UX research lives **outside this folder** in:

`docs/design/artist_playground/UX_RESEARCH.md`

That separation is intentional: this folder describes the working method; `UX_RESEARCH.md` contains the actual UX knowledge.

---

## Quick Navigation

### I want to understand the interaction language
→ Read `UX_RESEARCH.md` and use the **Researcher** role.

### I found an interesting principle in another tool
→ **Researcher**: identify the underlying principle, alternatives and unknowns.

### I want to see whether an idea can be built
→ **Interaction Dev**: prototype the smallest useful version.

### I want to know whether the idea actually feels good
→ **Playground Spec**: design/run an experiment and record observations.

### The roles disagree
→ Check `ROLES_COORDINATION.md`; resolve by evidence, technical reality and explicit synthesis rather than by authority.

### We are tempted to assign keys already
→ Stop and return to the interaction grammar. The shortcut table comes later.

---

## Current Research Order

```text
A  Interaction Grammar
      ↓
B  Transform Family
      ↓
C  Selection Family
      ↓
D  Topology / Modelling
      ↓
E  Navigation / Viewport
      ↓
F  Broader Artist Workflow
```

This is a **research direction**, not a schedule. Results can send us backward or sideways.

### A — Interaction Grammar

- sticky vs temporary
- press vs hold
- mode vs action
- selection vs hover target
- gesture semantics
- modifier semantics
- context / precedence
- feedback / feedforward
- conflict handling

### B — Transform

- Move / Rotate / Scale
- direct manipulation
- axis constraints
- selection-based vs hover-based targeting
- possible temporary overrides

### C — Selection

- Replace / Add / Remove / Toggle
- Pick / Box / Lasso / Paint
- component modes
- relationship between selection and manipulation

### D — Topology

- Extrude / Inset / Bevel / Connect / Cut / Bridge / etc.

### E — Navigation

- viewport gestures
- camera interaction
- conflicts with modelling gestures

### F — Broader Workflow

- Modelling
- Rigging / Skinning
- Morphing
- Animation
- Painting, if/when applicable

---

## Decision Vocabulary

Every experiment should end in one of four states:

- **KEEP** — evidence supports the pattern as tested
- **ITERATE** — useful idea, but interaction needs refinement
- **REJECT** — evidence argues against this variant
- **UNKNOWN** — experiment did not answer the question clearly

These are research results, not automatic production approvals.

---

## Shared Context

Always distinguish:

**Research knowledge**
→ `UX_RESEARCH.md`

**Working method**
→ this Three-Role system

**Experiment implementation**
→ Artist Playground / experiments

**Production truth**
→ current code, tests, ADRs and validated architecture

Never let a role prompt become the source of truth for architecture when the repository itself says otherwise.

---

## One Important Rule

> **Don't rebuild if it's already validated, documented and working. Use or adapt it.**

A Playground experiment should reuse existing Picking, Camera, Selection, Transform Ops, Viewport pieces, etc. where appropriate. Prototype only the missing interaction behavior.
