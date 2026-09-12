# Three-Role UX Research System — Coordination

The three roles are **separate lenses on one problem**: discovering Mirai-Bastel's interaction language.

They are not a waterfall and they are not three authorities voting on UX.

---

## Roles

| Role | Owns | Does not own |
|---|---|---|
| 🧪 UX Researcher | comparative research, principles, hypotheses, unknowns | code, final bindings, production architecture |
| 🛠️ Interaction Dev | feasibility, tiny prototypes, technical constraints | deciding whether UX is good |
| 📋 Playground Spec | experiment design, observation, feedback, KEEP/ITERATE/REJECT/UNKNOWN | production architecture, inventing UX without a question |

The user remains the **director / synthesis point**. Findings from the three roles are inputs to a decision, not automatic commands.

---

## Shared Context

The common UX knowledge lives in:

`docs/design/artist_playground/UX_RESEARCH.md`

All three roles should also respect:

- existing Artist Playground architecture
- existing validated Production systems
- current code and tests
- `AGENTS.md`

Do not create parallel "truth" documents inside the role system.

---

## Information Flow

```text
                 UX_RESEARCH.md
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
   🧪 Researcher   🛠️ Dev       📋 Playground
        │              │              │
        │ hypotheses  │ prototypes    │ observations
        └──────────────┼──────────────┘
                       ↓
                  SYNTHESIS
                       ↓
             next experiment / later
             validated production idea
```

The arrows are not a fixed sequence. A Playground observation may trigger new research; a technical constraint may change an experiment; a research comparison may suggest a completely different prototype.

---

## The Normal Cycle

### 1. Capture the question

Example:

> "If we have a sticky Move mode, does holding another input as a temporary override improve flow or create confusion?"

### 2. Researcher frames it

The Researcher identifies:

- comparable interaction patterns
- underlying principles
- alternative explanations
- unknowns
- a testable hypothesis

### 3. Dev checks reality

The Dev asks:

- What already exists that we can reuse?
- What is the smallest adapter/prototype needed?
- What technical constraint could distort the experiment?

**Do not redesign the production architecture just to make a prototype convenient.**

### 4. Playground tests it

The Playground:

- isolates the variable
- makes feedback visible
- plays with Cube / Head or another appropriate test scene
- records observations before interpreting them

### 5. Synthesis

We classify the result:

- KEEP
- ITERATE
- REJECT
- UNKNOWN

Then decide what deserves the next experiment.

Only validated findings are candidates for later production formalization.

---

## Interaction Grammar Comes First

The current overarching research question is:

> **What small set of interaction principles can organize many Mirai functions without creating shortcut and modifier chaos?**

Important candidate concepts include:

- mode vs action
- sticky vs temporary
- press vs hold
- target vs selection
- context
- gesture
- modifier
- feedback
- precedence / conflict resolution

None is fixed merely because it appears in this list.

---

## Example: Sticky + Temporary

This is a good research hypothesis, not a requirement:

```text
Move active
    ↓
S held
    ↓
temporary Scale
    ↓
S released
    ↓
back to Move
```

The question is whether this principle is useful, understandable and scalable — not whether we can invent a `StickyMode` class quickly.

The same distinction applies to Tweak:

```text
Selection = persistent global state
Hover     = current target
Tweak     = possible direct manipulation
```

We should test those semantics before freezing an architecture around them.

---

## Conflict Resolution

### Researcher says it is elegant; Playground says it is confusing

→ Treat that as meaningful evidence. Revisit the hypothesis or test another variant.

### Dev says it is difficult; UX evidence says it is valuable

→ Do not simply discard it. Ask what the smallest technically honest prototype is and what constraint is real.

### Playground result is inconclusive

→ Do not call it KEEP or REJECT. Mark UNKNOWN and improve the experiment.

### Roles produce different interpretations of the same observation

→ Separate **observation** from **interpretation**.

Example:

- Observation: "I paused before pressing S."
- Interpretation A: "The override was unclear."
- Interpretation B: "The feedback was insufficient."

Research the cause instead of pretending the interpretation is a fact.

---

## Documentation Rules

### Research findings

Go to `UX_RESEARCH.md` when a finding affects the broader interaction-language understanding.

### Experiment details

Keep experiment-specific implementation/spec material with the Playground experiment when practical.

### Production decisions

Validated decisions belong in the appropriate production design / ADR documentation, not in this role guide.

### Role-system changes

Change these documents only when the **working method itself** changes.

This prevents the role system from becoming a second project-management system.

---

## What the Roles Should Say to Each Other

Good:

> "Playground observed repeated hesitation when switching from sticky mode to a held override. Let's test whether feedback or the interaction semantics are responsible."

Bad:

> "Sticky mode is bad."

Good:

> "The existing Picker can provide the hover target, so the prototype only needs a direct-manipulation adapter."

Bad:

> "We need a new picking system for Tweak."

Good:

> "The current experiment needs a temporary override; let's prototype it without changing `src/core`."

Bad:

> "Let's redesign the InputMap now so future tools can use this."

---

## Stop Conditions

Pause and reassess when:

- a role starts inventing final shortcut layouts
- a prototype requires broad production refactoring before the hypothesis can be tested
- the same experiment changes several variables at once
- observations are being replaced by assumptions
- a research finding is being treated as an architecture decision
- an already validated system is being rebuilt instead of reused

These are signals to step back, not reasons to push harder.

---

## The Goal

The three-role system succeeds when it helps us answer increasingly precise questions about how Mirai should feel to use.

It is a **research and validation tool**, not the final UX architecture.
