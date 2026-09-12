# Mirai-Bastel Three-Role Chat System — Index
**UX/Interaction Language Research Framework**

---

## Complete File Set

This system consists of 6 documents:

### 1. **QUICK_START.md** ← **START HERE**
   - 5-minute setup guide
   - First session walkthrough
   - Common first conversations
   - Tips for success
   - What to do when stuck

### 2. **ROLE_UX_RESEARCHER.md** → **Chat 1: Researcher**
   - Identity: UX Research Lead
   - Specialization: Principles, patterns, comparisons
   - Outputs: Research docs, hypotheses, experiment plans
   - Paste entire file as first message in Researcher chat

### 3. **ROLE_INTERACTION_DEV.md** → **Chat 2: Dev**
   - Identity: Senior Interaction Developer
   - Specialization: Implementation, feasibility, code
   - Outputs: Prototypes, formalized patterns, architecture
   - Paste entire file as first message in Dev chat

### 4. **ROLE_PLAYGROUND_SPEC.md** → **Chat 3: Playground**
   - Identity: Playground Spec Lead
   - Specialization: Validation, feedback, observation
   - Outputs: Test plans, feedback designs, empirical results
   - Paste entire file as first message in Playground chat

### 5. **ROLES_COORDINATION.md**
   - How the three roles work together
   - Information flow diagrams
   - Cross-chat communication patterns
   - Conflict resolution
   - Decision boundaries
   - Keep as reference while working

### 6. **ROLES_INDEX.md** (this file)
   - Navigation guide
   - File inventory
   - Quick reference

---

## Setup Checklist

- [ ] Read QUICK_START.md (5 minutes)
- [ ] Create three new chats in claude.ai
- [ ] Name them:
  - 🧪 **UX Researcher: Mirai Interaction Patterns**
  - 🛠️ **Interaction Dev: Mirai Playground**
  - 📋 **Playground Spec: Mirai Validation**
- [ ] Paste ROLE_UX_RESEARCHER.md into Chat 1
- [ ] Paste ROLE_INTERACTION_DEV.md into Chat 2
- [ ] Paste ROLE_PLAYGROUND_SPEC.md into Chat 3
- [ ] Send first prompt to Researcher chat (see QUICK_START.md)
- [ ] Keep ROLES_COORDINATION.md open as reference

---

## Quick Navigation

### "I want to research a pattern"
→ Start in **Researcher chat** (ROLE_UX_RESEARCHER.md)

### "I want to understand implementation constraints"
→ Move to **Dev chat** (ROLE_INTERACTION_DEV.md)

### "I want to test a pattern"
→ Move to **Playground chat** (ROLE_PLAYGROUND_SPEC.md)

### "I need to understand how they work together"
→ Read **ROLES_COORDINATION.md**

### "I'm stuck and don't know what to do"
→ Consult **QUICK_START.md** Red Flags section

### "I need to set up from scratch"
→ Follow **QUICK_START.md** 5-Minute Setup

---

## Key Concepts

### The Three Roles

| 🧪 | 🛠️ | 📋 |
|---|---|---|
| **Researcher** | **Dev** | **Playground** |
| Discovers patterns | Implements patterns | Tests patterns |
| Theory, comparison | Architecture, code | Empirical validation |
| "What principles work?" | "How do I build this?" | "Does this feel good?" |

### The Workflow

```
Researcher discovers pattern
        ↓
Dev evaluates feasibility
        ↓
Playground designs feedback
        ↓
Dev builds prototype
        ↓
Playground runs test
        ↓
Results feed back to all three
        ↓
Iterate or move to next pattern
```

### Decision Rule

- **Empirical > Theoretical** — If Playground data contradicts research theory, test data wins
- **Implementation > Speculation** — If Dev finds a constraint, work around it
- **Artist Intuition > Design Elegance** — If patterns feel confusing, they need to change

---

## Shared Context

Keep these open while working:

1. **TWEAK_RESEARCH.md** — Central research document, all findings go here
2. **WP-04 Production Foundation** — Current architecture and existing bindings
3. **This system** — The three role prompts and coordination guide

All three chats reference the same TWEAK_RESEARCH.md. When you find something important, update it there.

---

## First Week Structure

### Day 1-2: Setup + Research

1. Create chats (5 min)
2. Paste role prompts (5 min)
3. First conversation in Researcher chat (15-30 min)
4. Share findings with Dev + Playground chats (15-30 min)

**Deliverable:** Clear hypothesis about sticky/temporary distinction

### Day 3-4: Implementation + Testing

1. Dev builds prototype (1-2 hours)
2. Playground designs test (30 min)
3. Playground runs test (30 min)
4. All three review results (30 min)

**Deliverable:** Test results (KEEP / ITERATE / REJECT / UNKNOWN)

### Day 5: Iteration

1. If KEEP: Move to next pattern
2. If ITERATE: Dev fixes, Playground re-tests
3. If REJECT: Researcher finds alternative
4. Update TWEAK_RESEARCH.md with findings

**Deliverable:** First validated pattern, updated research doc

---

## Success Metrics

### After 1 Week

- ✅ Clear understanding of 2-3 interaction principles
- ✅ At least one prototype tested
- ✅ TWEAK_RESEARCH.md updated with findings
- ✅ No major conflicts between the three perspectives

### After 1 Month

- ✅ Phase A (Interaction Grammar) mostly validated
- ✅ Phase B (Transform Family) started
- ✅ 5-10 patterns prototyped and tested
- ✅ Clear architecture emerging for production
- ✅ Confidence in the direction

### After 2 Months

- ✅ Phase A-B complete and validated
- ✅ Phase C-D planned
- ✅ Formalized patterns ready for production
- ✅ Clear shortcuts/bindings derived from principles
- ✅ Ready to implement Gate 4 (Interaction Wiring)

---

## Troubleshooting

### "The three chats are duplicating work"

Normal. They see the same problem from different angles. The duplication is part of the validation process.

### "One chat went off track"

Bring it back by referencing the research question:

```
You: "We're researching whether sticky/temporary patterns work in Mirai. 
Let's refocus on that question."
```

### "I'm not sure which chat to use"

Use this decision tree:

```
Do I want to... 

→ Compare patterns from other tools? → Researcher
→ Evaluate implementation feasibility? → Dev
→ Design how to test something? → Playground
→ Understand how they connect? → ROLES_COORDINATION.md
→ Get started from zero? → QUICK_START.md
```

### "This is taking too long"

You might be trying to do everything at once. Isolate one variable:

```
Not this: "Design the complete interaction system"
But this: "Test whether sticky vs temporary is intuitive"

Not this: "Build all of Gate 4"
But this: "Build the StickyMode class and test it"
```

---

## When to Reference Each Document

### QUICK_START.md

- Setting up the system
- First session walkthrough
- Running into unexpected problems
- Weekly planning
- "What should I do next?"

### ROLE_UX_RESEARCHER.md

- In Researcher chat (obviously)
- Whenever you want to understand the principles
- To review your research standards
- When you feel like you're going in circles

### ROLE_INTERACTION_DEV.md

- In Dev chat
- Whenever you want to understand implementation strategy
- To review code organization standards
- When a pattern seems hard to implement

### ROLE_PLAYGROUND_SPEC.md

- In Playground chat
- Whenever you want to understand experimental design
- To review the test template and discipline
- When a test feels inconclusive

### ROLES_COORDINATION.md

- As a reference while switching between chats
- To understand how findings flow between chats
- To resolve disagreements between perspectives
- To understand decision boundaries

### TWEAK_RESEARCH.md

- Shared by all three chats
- The central repository for all findings
- Updated regularly as you learn
- Referenced constantly to stay aligned

---

## Example Usage

### Scenario 1: Testing Sticky Modes

```
Session: "Should sticky modes be press-to-toggle or press-and-hold?"

1. Researcher chat: 
   "What interaction principle is at stake here? 
    Wings 3D vs Blender — how do they differ?"

2. Dev chat: 
   "Can we implement both? What's the code difference? 
    Which is compatible with our current architecture?"

3. Playground chat: 
   "Let's test both variants. Here's the test plan..."

4. All three: 
   "Based on test results, here's what we should do..."
```

### Scenario 2: Feedback Design Problem

```
Session: "The test failed because artists couldn't tell what was active"

1. Playground chat: 
   "This is the feedback that didn't work. 
    Why didn't artists understand it?"

2. Dev chat: 
   "What feedback DO we have available? 
    What could we add without architectural changes?"

3. Playground chat: 
   "Let's test this new feedback approach..."

4. All three: 
   "New feedback worked. Pattern is KEEP."
```

---

## Long-term Maintenance

### Monthly

- Update TWEAK_RESEARCH.md with all findings
- Review whether the research sequence (A→B→C→D→E→F) is still valid
- Check if any patterns need re-validation
- Plan next month's focus

### Quarterly

- Synthesis meeting: All three chats review everything learned
- Architecture review: Does the code still match the principles?
- Prioritization: Which patterns matter most for production?
- Gate planning: Ready to move from Playground to production?

---

## Related Documents

In your Mirai-Bastel project, also reference:

- **TWEAK_RESEARCH.md** — Central research document (shared across all roles)
- **docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md** — Production foundation
- **docs/architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md** — Project philosophy
- **src/mirai/application.py** — Current Application orchestrator
- **experiments/mirai_bastel_viewport_V1/** — Playground prototyping location

---

## The Three-Role Philosophy

The three-role system exists because:

1. **Research requires depth** — You can't design interactions without understanding principles
2. **Implementation requires rigor** — You can't code patterns without knowing what you're building
3. **Validation requires discipline** — You can't trust patterns without empirical testing
4. **Complex problems need separation** — One person can't think deeply in all three domains at once

By maintaining three focused perspectives, you stay honest and move faster.

---

## You're Ready to Begin

1. Start with **QUICK_START.md** (5 minutes)
2. Create the three chats
3. Paste the role prompts
4. Send your first question to Researcher chat
5. Let the workflow unfold

The system will guide you toward discovering Mirai-Bastel's interaction language.

---

## File Locations

All files are in `/home/claude/`:

```
QUICK_START.md              ← Start here (5 min setup + first conversation)
ROLE_UX_RESEARCHER.md       ← Paste into Chat 1
ROLE_INTERACTION_DEV.md     ← Paste into Chat 2
ROLE_PLAYGROUND_SPEC.md     ← Paste into Chat 3
ROLES_COORDINATION.md       ← Reference while working
ROLES_INDEX.md              ← This file (navigation guide)
```

Good luck. 🎨

