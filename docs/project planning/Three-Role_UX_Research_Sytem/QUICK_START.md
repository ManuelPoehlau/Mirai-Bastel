# Quick Start: Three-Role Chat System
**Mirai-Bastel UX/Interaction Language Research**

---

## 5-Minute Setup

### Step 1: Create Three Chats (2 min)

1. Go to claude.ai
2. Create three new chats with these names:
   - 🧪 **UX Researcher: Mirai Interaction Patterns**
   - 🛠️ **Interaction Dev: Mirai Playground**
   - 📋 **Playground Spec: Mirai Validation**

### Step 2: Paste Role Prompts (2 min)

In each new chat, paste **the first message**:

**Chat 1** (Researcher):
Copy everything from `ROLE_UX_RESEARCHER.md` and paste as your first message.

**Chat 2** (Dev):
Copy everything from `ROLE_INTERACTION_DEV.md` and paste as your first message.

**Chat 3** (Playground):
Copy everything from `ROLE_PLAYGROUND_SPEC.md` and paste as your first message.

(Don't send yet — read step 3 first)

### Step 3: Add Context (1 min)

Before you send the role prompts, send **one message per chat** with context:

**To Researcher Chat** (message before the role prompt):
```
Context:
- We're researching the interaction language for Mirai-Bastel (3D modelling tool)
- Start with TWEAK_RESEARCH.md (Artist UX — Research / Idea Space)
- WP-04 Production Foundation is complete (Transform Ops, basic keybindings)
- Goal: Discover principles before locking in shortcuts
- Focus: Phase A (Interaction Grammar) — sticky vs temporary, press vs hold, etc.

Here's your role prompt:

[paste ROLE_UX_RESEARCHER.md]
```

**To Dev Chat**:
```
Context:
- We're implementing interaction patterns for Mirai-Bastel
- Production foundation: src/mirai/ with Application, ToolManager, basic keybindings
- Current bindings: R=Rotate, S=Scale, Alt+R=Ring, Shift+S=Split (no conflicts)
- Testing environment: Python + OpenGL viewport (no React/web)
- Goal: Build patterns that the UX Research discovers

Here's your role prompt:

[paste ROLE_INTERACTION_DEV.md]
```

**To Playground Chat**:
```
Context:
- We're validating interaction patterns for Mirai-Bastel
- Test geometry: Cube (simple) and Head (realistic)
- Goal: Empirical validation of interaction hypotheses
- Playground discipline: small experiments, clear results, no over-generalization
- Current focus: Phase A (Interaction Grammar) experiments

Here's your role prompt:

[paste ROLE_PLAYGROUND_SPEC.md]
```

Now send all three role prompts.

---

## Your First Research Session (30 minutes)

### Timeline

**Min 0-5: Researcher Chat**

```
You: "Let's start with sticky vs temporary distinction. What interaction 
patterns do you see in Wings 3D and Blender that use this principle?"

🧪 Researcher: [Analyzes patterns, formulates hypothesis]

→ Copy the hypothesis somewhere (you'll share it with the other chats)
```

**Min 5-10: Dev Chat**

```
You: "UX Researcher found this hypothesis about sticky vs temporary modes: 
[paste hypothesis]

Can we implement this? What would the architecture look like?"

🛠️ Dev: [Evaluates feasibility, sketches code structure]

→ Copy the architecture notes
```

**Min 10-15: Playground Chat**

```
You: "Researcher discovered sticky/temporary pattern, Dev says we can implement 
it. How should we design an experiment to test whether this is intuitive?

Here's what we're testing: [paste hypothesis]

Proposed code structure: [paste Dev's architecture]"

📋 Spec: [Designs feedback, test plan, success criteria]

→ Copy the test plan
```

**Min 15-30: Feedback Loops**

Back to **Dev Chat**:
```
You: "Playground designed this feedback system for the test: [paste]

Will this work with your proposed architecture, or does it need changes?"

🛠️ Dev: [Refines design based on feedback needs]
```

Then back to **Playground Chat**:
```
You: "Dev refined the architecture. They're ready to build a prototype. 
When you have it, run this test plan: [confirm test]"
```

---

## Common First Conversations

### Conversation 1: Exploring Sticky/Temporary

**Researcher Chat:**
```
You: "Let me understand the sticky vs temporary distinction better. 
In Wings 3D, how does modal interaction work? And how is that different 
from Blender's pie menus?"

Expected output:
- Clear explanation of sticky modes (e.g., press E → extrude mode stays active)
- Clear explanation of temporary overrides (e.g., hold Shift to scale within extrude)
- Principle extraction: "This reduces workflow interruption"
- Question for next research: "Should Mirai use both patterns?"
```

### Conversation 2: Can We Build It?

**Dev Chat:**
```
You: "The Researcher says the sticky/temporary pattern is used in Wings 3D. 
Looking at our current architecture, how would we implement this?

Current state: We have R (Rotate) and S (Scale) as simple tool dispatchers. 
We need them to become sticky modes with temporary overrides."

Expected output:
- Code structure for StickyMode class
- How to integrate with current ToolManager
- What feedback systems need to exist
- Any architectural challenges
```

### Conversation 3: How Do We Test It?

**Playground Chat:**
```
You: "We have a hypothesis about sticky/temporary from research, 
and a proposed implementation from Dev.

Hypothesis: Artists will intuitively understand:
- Press M → Move mode (sticky, stays active)
- While in Move, hold S → Scale (temporary, returns to Move when released)

Question: Is this intuitive? Can an artist understand it in 2-3 interactions?"

Expected output:
- Test plan with steps (M→drag, S+drag, release, M again)
- Feedback design (how to show what's active)
- Success criteria ("Artist predicts behavior on second try")
- Test geometry (cube first, then head)
```

---

## How to Iterate

### After First Test

Let's say **Playground runs the test and discovers**:

```
Result: ITERATE

Issue: Artist paused before pressing S. Wasn't sure whether holding S 
would interrupt the drag or work as a modifier.

Feedback was unclear — we showed "active mode" but not "temporary override".
```

**Next actions:**

1. **Playground → Dev**: "Feedback wasn't clear enough. We need visual 
   distinction between 'sticky mode active' and 'temporary override active'."

2. **Dev → Playground**: "I've updated feedback. Sticky mode is blue, 
   temporary override is orange. New version ready to test."

3. **Playground → test again**: "Testing with new feedback..."

4. **Result**: "KEEP. Artist immediately understood with color distinction."

5. **Researcher**: "Good. Should we apply the same color distinction 
   to Selection operations?"

---

## Red Flags (When to Adjust)

### Red Flag 1: "We don't know what to test"

→ Go back to **Researcher** chat

```
You: "We're stuck. What research question should we be asking right now?"

🧪 Researcher should help you identify the next meaningful hypothesis.
```

### Red Flag 2: "I don't know if we can build this"

→ Go to **Dev** chat

```
You: "Is this implementable, or am I asking for something that's 
too complex for the current architecture?"

🛠️ Dev should give a clear yes/no/maybe with reasoning.
```

### Red Flag 3: "The test is inconclusive"

→ Go to **Playground** chat

```
You: "We ran a test but don't have a clear result. What went wrong?"

📋 Spec should help you identify: was the hypothesis unclear? 
Feedback insufficient? Test design flawed?
```

### Red Flag 4: "These three chats are disagreeing"

→ This is normal and healthy. Resolve with **empirical data**.

```
Researcher: "I think this pattern is elegant."
Dev: "It's hard to implement."
Playground: "It's confusing to artists."

→ Trust Playground's data. Change the pattern.
```

---

## Weekly Workflow Example

### Week 1: Phase A — Interaction Grammar

**Day 1: Researcher**
- "What's the smallest set of interaction principles that could organize all of Mirai?"
- Output: Hypothesis about Grammar (sticky/temporary, press/hold, etc.)

**Day 2-3: Dev + Playground**
- Dev: "I can prototype this. Here's the architecture."
- Playground: "Let's test sticky vs temporary first."
- Playground runs first test.

**Day 4: Iterate**
- If test result is KEEP: Move to next pattern
- If test result is ITERATE: Dev refines, Playground re-tests
- If test result is REJECT: Researcher finds alternative pattern

**Day 5: Synthesis**
- All three look at week's findings
- Document in TWEAK_RESEARCH.md
- Plan next week's focus

### Week 2: Phase B — Transform Family

**Day 1: Researcher**
- "How does the grammar apply to Move/Rotate/Scale specifically?"
- Output: Transform-specific hypotheses

**Day 2-5: Same cycle**
- Test sticky transform tools
- Test temporary overrides in transform
- Test axis constraints
- Test direct manipulation (Tweak)

---

## Documents You'll Reference

### Shared Context

Keep open as you work:

1. **TWEAK_RESEARCH.md** — The shared source of truth
   - Read: Sections 1-11 (current understanding)
   - Write: Update when you find something important

2. **WP-04 Production Foundation**
   - Understand: Current architecture, existing keybindings, tool lifecycle

### Role Documents

One per chat:

1. **ROLE_UX_RESEARCHER.md** — Pasted in Researcher chat
2. **ROLE_INTERACTION_DEV.md** — Pasted in Dev chat
3. **ROLE_PLAYGROUND_SPEC.md** — Pasted in Playground chat

### Coordination

Keep as reference:

1. **ROLES_COORDINATION.md** — How the three chats work together
2. **QUICK_START.md** — This file

---

## Tips for Success

### Do

✅ **Use shared names** — When referring to a pattern, use the name both chats know it by

✅ **Update TWEAK_RESEARCH.md regularly** — This is your institutional memory

✅ **Test hypotheses before declaring them true** — "Seems elegant" ≠ "Works well"

✅ **Bounce between chats** — Each one informs the others

✅ **Record observations, not interpretations** — "Artist paused" vs "Artist was confused"

✅ **Name unknowns** — "We don't know yet" is honest and useful

### Don't

❌ **Assume implementation is free** — Check with Dev first

❌ **Skip feedback design** — If artists can't see the state, the test is broken

❌ **Test five variables at once** — Isolate the one thing you're learning

❌ **Declare victory after one test** — Test multiple times on different geometry

❌ **Skip the Researcher** — Theory matters. It prevents you from going in circles

❌ **Copy shortcuts from other tools** — Copy principles, not key bindings

---

## First Prompt To Send

When you're ready to start, here's what to send to your **Researcher chat**:

```
I'm researching Mirai-Bastel's interaction language. We need to understand 
the principles behind how artist tools work before we lock in individual shortcuts.

Our starting hypothesis from TWEAK_RESEARCH.md is that Mirai should have:
- Sticky modes (press to activate, press again to deactivate)
- Temporary overrides (hold to temporarily switch operation, release to return)

These two ideas together could dramatically reduce shortcut explosion.

The question I want to start with: What interaction principles in other 3D tools 
support this idea? Wings 3D, Blender, Maya, ZBrush — who uses modal interaction 
well, and what's the underlying principle?

Can you research this pattern and help me understand what's working in the tools 
that do it well?
```

Then send the role prompt.

---

## What Success Looks Like

After 2-3 weeks of this workflow, you should see:

- ✅ Clear understanding of 3-4 interaction principles (not just "use sticky modes")
- ✅ Prototyped at least 2-3 patterns
- ✅ Tested patterns on actual geometry (cube + head)
- ✅ Clear KEEP/ITERATE/REJECT decisions with reasoning
- ✅ Updated TWEAK_RESEARCH.md with findings
- ✅ A sense of what Mirai-Bastel's interaction language *should feel like*

After 4-6 weeks:

- ✅ Phase A (Interaction Grammar) mostly validated
- ✅ Phase B (Transform Family) in progress
- ✅ Clear principles that can be formalized for production
- ✅ Confidence that the shortcuts you eventually design won't conflict

---

## Still Have Questions?

### "Should these be separate chats or projects?"

Separate chats, same project. The chats don't need separate projects — they're working on the same problem with different lenses.

If you want to organize them, you could create a project folder:

```
/Mirai-Bastel/
├── TWEAK_RESEARCH.md (shared context)
├── ROLES_COORDINATION.md
├── QUICK_START.md
├── ROLE_UX_RESEARCHER.md
├── ROLE_INTERACTION_DEV.md
├── ROLE_PLAYGROUND_SPEC.md
└── Findings/
    ├── Week 1 — Phase A Findings
    ├── Week 2 — Transform Tests
    └── ...
```

Then reference this folder in each chat: "Our project docs are in [folder]".

### "Can I combine two roles in one chat?"

Technically yes, but not recommended. The roles have different thinking styles and should maintain separation of concern. Keeping them separate helps you:
- **Think more clearly** (each chat has one perspective)
- **Avoid conflicts** (forced to reconcile perspectives explicitly)
- **Iterate faster** (can work on multiple chats simultaneously)

### "What if one chat reaches a dead end?"

Ask the other chats for help:

```
Playground: "We've tested sticky modes 5 times now and keep hitting the same issue: 
artists paused before using temporary overrides."

→ Researcher: "Maybe we're testing the wrong pattern. What if temporary overrides 
should work differently?"

→ Dev: "Or maybe the feedback design is wrong. Let's try a different visual approach."
```

Use problems as signals. They usually point to a misunderstanding in the hypothesis.

---

## You're Ready

You have everything you need. Create the three chats, paste the role prompts, and start asking questions.

The workflow will reveal what Mirai-Bastel's interaction language should be.

Good luck. 🎨

