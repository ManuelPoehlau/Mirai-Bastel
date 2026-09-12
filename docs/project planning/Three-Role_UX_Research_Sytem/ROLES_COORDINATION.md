# Three-Role Chat Coordination Guide
**Mirai-Bastel Artist UX Language Development**

---

## The Three Roles

You are running **three separate Claude chats**, each with a distinct specialization:

| Role | Focus | Thinks About | Outputs |
|------|-------|--------------|---------|
| **🧪 UX Researcher** | Principles, patterns, comparisons | What interaction principles exist? What patterns work elsewhere? | Research docs, hypotheses, experiment plans |
| **🛠️ Interaction Dev** | Implementation, feasibility, code | How do I code this pattern? What's the implementation constraint? | Prototypes, formalized patterns, code architecture |
| **📋 Playground Spec** | Validation, feedback, observation | Does this pattern *feel* good? What should the artist see? | Test plans, feedback designs, empirical results |

---

## Information Flow

```
                    SHARED CONTEXT
                    (TWEAK_RESEARCH.md
                    + WP-04 Production Foundation
                    + Playground Findings)
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
    🧪 RESEARCHER      🛠️ DEV            📋 PLAYGROUND
    
    Discovers         Implements         Tests
    Patterns          Patterns           Patterns
        │                 │                   │
        └────────┬────────┴────────┬─────────┘
                 │                 │
            Questions          Findings
            Feedback           Issues
            Constraints        Data
                 │                 │
                 └────────┬────────┘
                          ▼
                   Synthesis & Learning
```

### Typical Flow for One Hypothesis

```
1. RESEARCHER discovers pattern
   "Wings 3D uses temporary overrides for transform operations"
   → TWEAK_RESEARCH.md updated
   
2. RESEARCHER formulates hypothesis
   "We should test whether sticky modes + temporary overrides work in Mirai"
   → Creates test plan, hands to Playground Spec
   
3. DEV evaluates feasibility
   "Yes, we can build this. Here's the architecture."
   → Creates prototype framework
   
4. PLAYGROUND runs experiment
   "Tested on cube and head. Artist understood the pattern immediately."
   → Records findings: KEEP / ITERATE / REJECT / UNKNOWN
   
5. Findings feed back
   PLAYGROUND → "Results: Artist paused when switching to override. Needs feedback."
   DEV → "OK, I'll add visual feedback for override state."
   RESEARCHER → "Should we test this on Selection operations too?"
   
6. Cycle repeats with refined understanding
```

---

## How to Use the Three Chats

### Setup

1. Create three separate Claude chats in claude.ai
2. Give each chat its own name:
   - 🧪 **UX Researcher: Mirai Interaction Patterns**
   - 🛠️ **Interaction Dev: Mirai Playground**
   - 📋 **Playground Spec: Mirai Validation**

3. In each chat, paste the corresponding role prompt:
   - Chat 1: Contents of **ROLE_UX_RESEARCHER.md**
   - Chat 2: Contents of **ROLE_INTERACTION_DEV.md**
   - Chat 3: Contents of **ROLE_PLAYGROUND_SPEC.md**

### Your Workflow

#### When You Want to Research a Pattern

→ **Start in UX Researcher chat**

```
You: "I'm curious about how Wings 3D handles mode switching. What principle do you 
see there?"

🧪 Researcher: "Wings uses modal interaction where you select a tool and it stays 
active. The principle is: 'sticky mode reduces switching overhead.' But Blender 
uses the opposite — context-sensitive pie menus. The principle there is: 
'visibility-on-demand reduces cognitive load.' We should test both in Mirai."
```

#### When You Want to Understand Implementation Constraints

→ **Move to Interaction Dev chat**

```
You: "Can we implement a system where pressing M enters Move mode (sticky) and 
holding S temporarily scales?"

🛠️ Dev: "Yes. The architecture would be:
1. StickyMode class for press-to-toggle behavior
2. TemporaryOverride class for hold-to-override
3. InputRouter that dispatches to the active mode
This would fit neatly with our current ToolManager. Here's the code structure..."
```

#### When You Want to Test a Pattern

→ **Move to Playground Spec chat**

```
You: "We have a prototype of the sticky/temporary pattern. How should we test 
whether the distinction is intuitive?"

📋 Spec: "Here's a test plan:
1. Hypothesis: Artist intuitively understands sticky vs temporary after seeing it
2. Feedback design: Active mode shown in corner, override shown with color shift
3. Test steps: M→drag, S(hold)→drag, release, M again
4. Success: Artist predicts behavior on second try"
```

#### When You Get Results and Need to Synthesize

→ **Bounce findings between all three chats**

```
📋 Spec (result): "Test complete. Artist understood sticky/temporary immediately. 
No accidental mode switches. **KEEP this pattern.**"

Then feed to:

🧪 Researcher: "Pattern validated. Now, should we test this with Selection operations 
next, or Topology operations?"

🛠️ Dev: "Pattern is solid. I can now formalize it for production foundation."
```

---

## Cross-Chat Communication Patterns

### From Researcher to Dev

> **Researcher**: "I discovered that ZBrush uses 'grab mode' where you hold a key to temporarily enter a grab operation. This is the principle of **modal temporality** — a mode that exists only while holding."

**Dev responds with**: Implementation questions, feasibility assessment, architectural implications

> **Dev**: "We can implement this. The cost is adding a HeldMode class alongside StickyMode. Question: Should held modes support nested temporary overrides (e.g., hold M for grab, then hold R to rotate the grab)?"

### From Dev to Playground

> **Dev**: "I've built a prototype of the sticky/temporary pattern for Transform tools. It's ready to test."

**Playground responds with**: Test plan, feedback design, empirical results

> **Playground**: "Tested. Artist immediately understood press=sticky, hold=temporary. Visual feedback was clear. Ready to promote."

### From Playground to Researcher

> **Playground**: "Test result: Sticky Selection (press Q to enter, press Q to exit) worked great. But temporary override in Selection (Shift+hold for different select mode) was confusing."

**Researcher responds with**: Hypothesis refinement, pattern alternatives

> **Researcher**: "Interesting. Maybe Selection should use different semantics — not override, but *operation stacking*. Let me research how this works in Maya and Blender..."

### Feedback Loops

The three chats are **not sequential**. They run in parallel:

```
Session 1:
- Research discovers sticky/temporary pattern
- Dev starts building prototype
- Playground designs test plan

Session 2:
- Dev shows prototype
- Playground runs tests
- Researcher refines hypothesis based on test results

Session 3:
- Dev iterates on code based on Playground feedback
- Researcher applies findings to Selection operations
- Playground runs next test
```

---

## Shared Context: What Goes in TWEAK_RESEARCH.md

All findings, hypotheses, and decisions that affect the overall strategy live here.

### Researcher Updates

When you discover a new principle, add it to TWEAK_RESEARCH.md in the appropriate section:

```markdown
## 19. [New Finding]: Sticky vs Temporary Distinction

[Description of the pattern, why it matters, where else it appears]

**Principle:** [The underlying rule]

**Test Status:** KEEP / ITERATE / REJECT / UNKNOWN

**Next Question:** [What should we test next?]
```

### Dev Updates

When you formalize a pattern, document it in the Interaction Dev section:

```markdown
## Dev Pattern: [Pattern Name]

**Implementation Status:** Prototyped / In Production Foundation / Promoted

**Code Location:** src/mirai/[module]

**Design Constraints:** [What limits did we hit?]

**Remaining Unknowns:** [What still needs testing?]
```

### Playground Updates

When you complete an experiment, document results:

```markdown
## Playground Result: [Experiment Name]

**Hypothesis:** [What we tested]

**Result:** KEEP / ITERATE / REJECT / UNKNOWN

**Key Observation:** [What surprised us?]

**Feedback Design:** [What worked visually?]

**Next Test:** [What should we try next?]
```

---

## Decision Boundaries

### UX Researcher Does NOT Decide

- Whether a pattern is implementable (ask Dev)
- Whether a pattern *feels* good (ask Playground)
- Production architecture (that's synthesis)

### Interaction Dev Does NOT Decide

- Whether a pattern is good UX (ask Researcher)
- Whether a pattern should exist (ask Researcher + Playground)
- Experiment methodology (ask Playground)

### Playground Spec Does NOT Decide

- Whether a pattern should exist (that's Research + Dev)
- How to implement it (that's Dev)
- Which patterns to prioritize (that's a synthesis decision)

---

## Conflict Resolution

If the three chats disagree:

| Conflict | Resolution |
|----------|-----------|
| "Is this pattern good UX?" | Playground tests it. Empirical data wins. |
| "Can we implement this?" | Dev prototypes. If it works, yes. |
| "Should we test this?" | Researcher says whether it answers a real question. |
| "Is feedback good?" | Playground runs test. Artist intuition wins. |

**Rule: Always resolve with empirical data when possible.**

If Researcher thinks a pattern is elegant but Playground shows it's confusing, the pattern needs to change.

If Dev thinks something is hard to implement but Playground shows it's essential for UX, find a way to implement it.

---

## Session Structure

### Research Session (30-60 minutes)

1. **Researcher** (15 min): "Here's a pattern I found in Wings 3D. Let me explore implications."
   - Output: Hypothesis, comparison to other tools, research questions

2. **Dev** (15 min): "I can build a prototype for this. Here's the architecture."
   - Output: Prototype code, implementation constraints, unknowns

3. **Playground** (15 min): "Here's how we'd test this. Here's the feedback design."
   - Output: Test plan, readiness check

4. **Synthesis** (15 min): "Based on all three perspectives, this is the next step."
   - Output: Priority, timeline, open questions

### Validation Session (30-60 minutes)

1. **Playground** (15 min): "We have a prototype. Let me design the test."
2. **Playground** (20 min): "Running the test now..."
3. **Playground** (10 min): "Results: KEEP / ITERATE / REJECT / UNKNOWN"
4. **All three** (15 min): "What does this mean for the next iteration?"

### Iteration Session (varies)

1. **Playground** (5 min): "Test revealed this issue..."
2. **Researcher** (5 min): "This suggests a different pattern..."
3. **Dev** (10 min): "Let me fix the implementation..."
4. **Playground** (10 min): "Testing the fix..."
5. **Repeat** until KEEP

---

## Communication Norms

### Across Chats

When referring to findings from another chat:

```
Good: "The Playground test showed that artists preferred sticky modes for 
Move/Rotate/Scale. Should we apply the same principle to Selection?"

Bad: "I think we should use sticky modes everywhere."
```

When asking the other roles for input:

```
Good: "Dev says this pattern might be costly to implement. What's the actual 
feasibility?"

Bad: "Dev can't build this, so we can't use it."
```

### Discipline

- **Name the assumption** — "I'm assuming this feels good, but we should test it"
- **Cite the finding** — "Playground showed that...", "Research found that..."
- **Propose, don't declare** — "We could test...", "Should we consider...?"
- **Distinguish data from interpretation** — "Artist paused" vs "Artist was confused"

---

## Tools and Documentation

### Shared Resources

- **TWEAK_RESEARCH.md** — Central research and decision document
- **Playground Experiment Template** (in Playground Spec prompt) — For documenting tests
- **Code Architecture** (in Interaction Dev context) — Production foundation reference
- **Feedback Design Checklist** (in Playground Spec prompt) — For evaluating visibility

### Where Outputs Go

| Output | Chat | Goes To |
|--------|------|---------|
| Research findings | Researcher | TWEAK_RESEARCH.md |
| Code prototypes | Dev | GitHub repo, experiments/ or src/ |
| Test plans | Playground | TWEAK_RESEARCH.md or docs/playground/ |
| Test results | Playground | TWEAK_RESEARCH.md |
| Production decisions | (synthesis outside chats) | ADRs, docs/architecture/ |

---

## Before You Start

### Checklist

- [ ] Three separate Claude chats created
- [ ] Each chat has its role prompt pasted (ROLE_UX_RESEARCHER.md, ROLE_INTERACTION_DEV.md, ROLE_PLAYGROUND_SPEC.md)
- [ ] TWEAK_RESEARCH.md is your shared context (everyone references it)
- [ ] WP-04 production foundation context is shared (everyone knows what exists)
- [ ] You have a clear research question or hypothesis to start with

### First Session

Start in **Researcher chat**:

```
You: "I want to research Mirai-Bastel's interaction language. We have a strong 
hypothesis about sticky modes and temporary overrides. Can you help me understand 
how other tools implement this pattern?"

🧪 Researcher: "Absolutely. Let me start by examining Wings 3D, Blender, Maya, and 
ZBrush to find the underlying principles..."

[Researcher builds case]

Then: → Switch to Dev chat
"Based on the research, Dev — can we implement this pattern?"

[Dev builds architecture]

Then: → Switch to Playground chat
"Based on both perspectives, Playground — how should we test this?"

[Playground designs test]

Then: → Synthesis decision
"Across all three perspectives, here's our next step..."
```

---

## Why This Structure Works

1. **Separation of concern** — Each role owns its expertise
2. **Parallel workflow** — You don't wait for one role to finish before starting another
3. **Empirical grounding** — Playground tests keep everything honest
4. **Composable patterns** — Research discovers principles, Dev formalizes them, Playground validates
5. **Clear decision boundaries** — No ambiguity about who decides what
6. **Scalable** — This structure works for small experiments or major research initiatives
7. **Iterative** — Findings loop back to refine hypotheses without starting over

---

## The Bigger Picture

These three roles are working toward the goal from TWEAK_RESEARCH.md:

> **"I understand how this application thinks, so I can operate it almost without thinking about the interface."**

- **Researcher** ensures the principles are *discoverable* (they come from real patterns)
- **Dev** ensures they're *implementable* (they can be coded without compromise)
- **Playground** ensures they're *intuitive* (they feel good to artists)

Together, they discover Mirai-Bastel's interaction language **before** locking in shortcuts.

---

## Next Steps

1. Create the three chats with their role prompts
2. Start in Researcher chat with your current focus (likely: Phase A Interaction Grammar)
3. Move between chats as needed
4. Update TWEAK_RESEARCH.md as findings accumulate
5. Let the process reveal what Mirai-Bastel's interaction language should be

Good luck. 🎨

