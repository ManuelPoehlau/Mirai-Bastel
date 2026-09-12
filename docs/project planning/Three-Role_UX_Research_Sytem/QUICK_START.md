# Quick Start — Three-Role UX Research System

This is the practical setup for the three-role research workflow.

The important change from the original version is simple:

> **We are not starting with Tweak or with a shortcut table. We are starting with the interaction language itself.**

---

## 1. Create Three Chats

Create three separate Claude chats:

- 🧪 **UX Researcher: Mirai Interaction Patterns**
- 🛠️ **Interaction Dev: Mirai Playground**
- 📋 **Playground Spec: Mirai Validation**

Keep them separate so each chat maintains one clear perspective.

---

## 2. Give Each Chat Its Role

Paste the corresponding role document as the first message/context for that chat:

- Researcher → `ROLE_UX_RESEARCHER.md`
- Dev → `ROLE_INTERACTION_DEV.md`
- Playground → `ROLE_PLAYGROUND_SPEC.md`

Then give each role the same core context:

```text
We are researching Mirai-Bastel's artist interaction language.
The shared research document is:
  docs/design/artist_playground/UX_RESEARCH.md

The goal is to discover interaction principles before finalizing
individual keyboard and mouse bindings.

Start from the current repository reality. Reuse validated systems.
Do not redesign production architecture for a Playground experiment.
```

---

## 3. Start at the Right Level

Do **not** start with:

> "What key should Tweak use?"

or:

> "Let's build StickyMode."

Start with a research question such as:

> **"What interaction grammar could let Mirai express many operations without requiring a separate shortcut for every combination?"**

Useful first topics:

- mode vs action
- sticky vs temporary
- press vs hold
- selection vs hover target
- mouse gesture semantics
- modifier semantics
- context and precedence
- feedback

These are hypotheses to compare, not decisions to adopt.

---

## 4. First Conversation: Researcher

Example prompt:

```text
Let's start at the interaction-grammar level.

Compare how artist tools such as Wings 3D, Mirai/N-World, Silo,
3ds Max, Maya, ZBrush and Blender handle persistent modes,
temporary modifiers, gestures, targets and context.

Don't give me a shortcut table. Extract the underlying principles,
trade-offs and unknowns that could matter for Mirai-Bastel.
```

The Researcher should return **principles and hypotheses**, not a final design.

---

## 5. Bring One Hypothesis to Dev

Example:

```text
The Researcher found this hypothesis:
[insert concise hypothesis]

Can we prototype the smallest version of this in the Artist Playground?
Please first identify what existing systems we can reuse.
Do not redesign production architecture unless the experiment genuinely
requires it.
```

The Dev should tell us:

- what already exists
- what can be wrapped/adapted
- what the smallest experiment is
- which technical constraints could affect the UX result

---

## 6. Bring the Prototype Question to Playground

Example:

```text
We want to test this hypothesis:
[insert hypothesis]

Design the smallest experiment that can tell us something useful.
Define the variable, feedback, test steps and observations to record.
Use the existing Playground infrastructure where possible.
```

Then actually play with it.

Record what happens, not what you hoped would happen.

---

## 7. Use the Four Results

Every meaningful experiment should end as one of:

**KEEP** — the tested pattern is promising as-is.

**ITERATE** — the principle looks useful, but this variant needs work.

**REJECT** — evidence argues against this approach.

**UNKNOWN** — the test did not answer the question clearly.

UNKNOWN is a valid result. Do not force a decision just to keep moving.

---

## 8. Feed the Finding Back

If the finding changes our understanding of Mirai's interaction language, update:

`docs/design/artist_playground/UX_RESEARCH.md`

A useful finding has the form:

```text
Observation:
Artist hesitated before using the held modifier.

Interpretation:
Unknown — feedback and semantics both need investigation.

Hypothesis:
The temporary override may be harder to predict than expected.

Result:
ITERATE / UNKNOWN

Next question:
Can clearer pre-action feedback distinguish the base mode
from the temporary override?
```

Do not turn a single observation into a universal rule.

---

## 9. Tweak Comes Later

Tweak is still an excellent experiment because it exposes several grammar questions at once:

```text
Hover target
    +
Direct manipulation
    +
Selection independence
    +
Mouse/keyboard interaction
    +
Possible temporary overrides
```

But Tweak is **Phase B / Transform-family research**, not the organizational center of the system.

---

## 10. No Artificial Schedule

There is deliberately no "Week 1 = grammar, Week 2 = transforms" requirement.

The research order in `UX_RESEARCH.md` is a useful direction, not a deadline.

If a question is important, we can spend more time on it. If a result makes an earlier assumption questionable, we go back.

The correct unit of progress is:

> **a clearer understanding**, not a completed calendar week.

---

## 11. If You Get Stuck

### "We don't know what to research."

→ Ask the **Researcher** to identify the most important unresolved interaction question.

### "We don't know how to prototype it."

→ Ask the **Dev** to identify the smallest experiment using existing systems.

### "We built it but don't know what it tells us."

→ Ask the **Playground** to isolate the variable and define the observation criteria.

### "The three roles disagree."

→ Separate observations from interpretations and run the smallest experiment that can resolve the disagreement.

### "We are designing hundreds of bindings."

→ Stop. Return to Interaction Grammar.

### "We are rebuilding something that already works."

→ Stop. Find the validated system and adapt/reuse it.

---

## The First Session

A good first session can be as small as:

```text
1. Researcher → compare interaction principles
2. Pick ONE hypothesis
3. Dev → identify reuse + smallest prototype
4. Playground → define one experiment
5. Play
6. Record observations
7. KEEP / ITERATE / REJECT / UNKNOWN
```

That is enough.

No giant UX architecture. No final shortcut map. No production refactor just because an experiment was interesting.

---

## Start Here

Shared research:

`docs/design/artist_playground/UX_RESEARCH.md`

Working method:

`docs/project planning/Three-Role_UX_Research_Sytem/README.md`

Then open the three role prompts and start with **Interaction Grammar**.
