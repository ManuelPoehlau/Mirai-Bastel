# Mirai-Bastel Three-Role Chat System
**Artist UX/Interaction Language Research Framework**

---

## 📋 What You Have

A complete system for researching and validating Mirai-Bastel's interaction language using **three specialized Claude chats**, each with a distinct expertise:

```
🧪 UX Researcher      — Discover patterns from other tools
🛠️  Interaction Dev    — Implement patterns that work
📋 Playground Spec   — Test patterns and validate
```

All three work in parallel on **shared context** (TWEAK_RESEARCH.md), feeding findings back and forth until Mirai-Bastel's interaction language emerges.

---

## 📁 Files (in /home/claude/)

### Getting Started

| File | Purpose | Read Time |
|------|---------|-----------|
| **QUICK_START.md** | ⭐ **START HERE** — 5-minute setup, first conversation, common workflows | 5 min |
| **ROLES_INDEX.md** | Navigation guide for the complete system | 3 min |

### The Three Role Prompts

| File | For Chat | Read Before Pasting |
|------|----------|-------------------|
| **ROLE_UX_RESEARCHER.md** | 🧪 Researcher chat | Brief intro to get context-setting |
| **ROLE_INTERACTION_DEV.md** | 🛠️ Dev chat | Brief intro to get context-setting |
| **ROLE_PLAYGROUND_SPEC.md** | 📋 Playground chat | Brief intro to get context-setting |

### Coordination & Reference

| File | Purpose | When to Use |
|------|---------|------------|
| **ROLES_COORDINATION.md** | How the three chats work together, information flow, decision boundaries | While switching between chats |
| **README.md** | This file — navigation and overview | First time, or when lost |

---

## 🚀 Quick Start (Copy & Paste)

### Step 1: Create Three Chats
- Go to claude.ai
- Create 3 new chats with these names:
  - 🧪 **UX Researcher: Mirai Interaction Patterns**
  - 🛠️ **Interaction Dev: Mirai Playground**
  - 📋 **Playground Spec: Mirai Validation**

### Step 2: Paste Role Prompts

**In Chat 1 (Researcher):**
1. Send this first message:
```
Context: We're researching the interaction language for Mirai-Bastel. 
We start with TWEAK_RESEARCH.md. Goal: Discover principles before locking 
in shortcuts. Focus: Phase A (Interaction Grammar).

Here's your role:
```

2. Then paste the contents of **ROLE_UX_RESEARCHER.md**

**In Chat 2 (Dev):**
Same format, but paste **ROLE_INTERACTION_DEV.md**

**In Chat 3 (Playground):**
Same format, but paste **ROLE_PLAYGROUND_SPEC.md**

### Step 3: Send Your First Question

To the **Researcher chat**:
```
Let's start with sticky vs temporary distinction. In Wings 3D and Blender, 
what interaction principles do you see that use this idea?
```

Then move to Dev and Playground chats to get their perspectives.

That's it. The system is now active.

---

## 📖 How to Use Each File

### QUICK_START.md
**Read this first.** It gives you:
- 5-minute setup instructions
- Example first conversations
- Common workflows
- Troubleshooting (what to do if stuck)

### ROLE_UX_RESEARCHER.md
**Paste this into Chat 1.** Contains:
- Identity: "I'm the UX Research Lead"
- Research methodology
- What to compare (Wings 3D, Blender, Maya, ZBrush, etc.)
- Interaction patterns you should discover
- Research sequence (Phase A → B → C → etc.)
- Standards for good research output

### ROLE_INTERACTION_DEV.md
**Paste this into Chat 2.** Contains:
- Identity: "I'm the Senior Interaction Developer"
- Code patterns to implement (sticky modes, temporary overrides, etc.)
- Architecture decisions
- Production foundation context (WP-04, existing bindings)
- Code organization guidelines
- Implementation checklist

### ROLE_PLAYGROUND_SPEC.md
**Paste this into Chat 3.** Contains:
- Identity: "I'm the Playground Spec Lead"
- Experiment design methodology
- Feedback design (what the artist must see)
- Test template (how to structure experiments)
- Observation discipline
- KEEP / ITERATE / REJECT / UNKNOWN decision framework

### ROLES_COORDINATION.md
**Keep as reference.** Contains:
- Information flow between the three chats
- Cross-chat communication patterns
- Conflict resolution rules
- What each role owns (decision boundaries)
- How findings get documented
- Example workflows

### README.md
**This file.** Navigation and overview.

---

## 🎯 Typical Workflow (Week 1)

### Day 1: Research Phase (1-2 hours)

**Researcher chat:**
```
You: "What interaction principles do you see in Wings 3D, Blender, and Maya 
for modal interaction?"

Researcher: [Analysis of sticky modes, temporary overrides, tool switching patterns]

→ Capture the findings
```

### Day 2: Implementation Phase (1-2 hours)

**Dev chat:**
```
You: "Based on research, can we implement sticky modes + temporary overrides?"

Dev: [Architecture sketch, code structure, feasibility assessment]

→ Capture the proposed code structure
```

### Day 3: Validation Phase (1-2 hours)

**Playground chat:**
```
You: "Based on research and Dev's architecture, how should we test this?"

Playground: [Test plan, feedback design, success criteria]

→ Test it with prototype code
```

### Day 4-5: Iteration & Documentation

**All three:**
```
Playground: "Test results: KEEP. Artist understood the pattern."

Researcher: "Should we apply this to Selection operations next?"

Dev: "Pattern is solid. Ready to formalize."

→ Update TWEAK_RESEARCH.md
→ Plan next week
```

---

## 🔄 Information Flow

```
SHARED CONTEXT (TWEAK_RESEARCH.md)
         ↓
    (all three chats read/write here)
         ↓
    ┌────┴────┬─────────┬─────────┐
    ↓         ↓         ↓         ↓
 🧪 Researcher 🛠️ Dev 📋 Playground
    │         │         │
    └────┬────┴─────────┴─────────┘
         ↓
   Findings & Learning
    (feeds back to shared context)
```

**Key principle:** Each chat is specialized, but they're not siloed. Findings flow between them constantly.

---

## 📊 Decision Boundaries

| Question | Ask |
|----------|-----|
| "Is this interaction pattern good UX?" | Playground (empirical data) |
| "Can we implement this?" | Dev (feasibility) |
| "Should we test this?" | Researcher (relevance) |
| "Does this feel intuitive?" | Playground (user testing) |
| "What's the architecture impact?" | Dev (complexity, feasibility) |
| "What principle is at work here?" | Researcher (pattern analysis) |

**Rule: Always resolve with empirical data when possible.**

---

## 🎓 Learning Outcomes

After following this system for 2-3 weeks, you will have:

✅ Clear understanding of 3-4 core interaction principles (not just "use sticky modes")  
✅ Tested patterns on real geometry (cube + head)  
✅ KEEP/ITERATE/REJECT decisions with reasoning  
✅ Updated TWEAK_RESEARCH.md with findings  
✅ A sense of what Mirai-Bastel's interaction language should *feel* like  
✅ Confidence that shortcuts won't conflict  

After 4-6 weeks:

✅ Phase A (Interaction Grammar) validated  
✅ Phase B (Transform) in progress or complete  
✅ Clear principles formalized for production  
✅ Ready for Gate 4 (Interaction Wiring) implementation  

---

## 💡 Key Principles

### This System Works Because:

1. **Separation of concern** — Each role owns its expertise, no confusion about who decides what
2. **Parallel workflow** — You don't wait for one role to finish; all three work at once
3. **Empirical grounding** — Playground testing keeps everything honest
4. **Composable patterns** — Research discovers principles, Dev formalizes them, Playground validates
5. **Iterative refinement** — Findings loop back; you learn and improve continuously
6. **Scalable** — Works for small experiments or major initiatives

### This System Avoids:

❌ "Let's design the whole interaction system in one go"  
❌ "I'm guessing shortcuts that might conflict"  
❌ "This pattern seems elegant, but nobody tested it"  
❌ "We discovered a principle, but have no way to validate it"  
❌ "Implementation surprises revealed our architecture is broken"  

---

## 🚨 Red Flags (When to Adjust)

### "We don't know what to test"
→ Go to **Researcher** chat. They should identify the next meaningful hypothesis.

### "I don't know if we can build this"
→ Go to **Dev** chat. They should give clear feasibility assessment.

### "The test result is inconclusive"
→ Go to **Playground** chat. They should help diagnose what went wrong.

### "The three chats are disagreeing"
→ This is healthy. Resolve with **empirical data**. Trust Playground's findings.

### "We're going in circles"
→ Check **TWEAK_RESEARCH.md**. Update it with what you've learned. Reset focus.

---

## 📚 Related Context

While using this system, keep these documents open:

1. **TWEAK_RESEARCH.md** — Central research document (shared by all three chats)
2. **WP-04 Production Foundation** — Current architecture (Transform Ops, keybindings, etc.)
3. **PROJECT_VISION_AND_V1_PRINCIPLE.md** — Project philosophy

All three chats reference these same documents. They're the shared source of truth.

---

## ❓ FAQ

### "Should these be separate chats or separate projects?"
**Separate chats, same project.** They don't need separate projects — they're working on the same problem with different lenses.

### "Can I combine two roles in one chat?"
Technically yes, but not recommended. Keeping them separate helps you think more clearly and avoid conflicts.

### "What if one chat reaches a dead end?"
Ask the other chats for help. Problems usually point to a misunderstanding in the hypothesis.

### "How do I know if I'm doing it right?"
- Research is discovering principles, not guessing shortcuts ✓
- Dev is building reusable patterns, not one-off code ✓
- Playground is running small tests and recording observations ✓
- All three are feeding findings into TWEAK_RESEARCH.md ✓
- You're learning something new every session ✓

### "How much time should I spend on this?"
**Phase A (Interaction Grammar):** 2-3 weeks, ~10-15 hours  
**Phase B (Transform Family):** 2-3 weeks, ~10-15 hours  
**Phase C-F (other families):** Depends on complexity  

After 4-6 weeks of part-time work, you'll have enough validated patterns to move to production.

### "Can I do this solo, or do I need a team?"
**Solo works.** You're running all three chats yourself, switching perspectives. It's actually faster than a team because context-switching is the only overhead.

---

## 🎬 Next Steps

1. **Read QUICK_START.md** (5 minutes)
2. **Create three chats** (5 minutes)
3. **Paste role prompts** (5 minutes)
4. **Send first question to Researcher** (1-2 minutes)
5. **Start your research cycle** (ongoing)

You're ready to begin discovering Mirai-Bastel's interaction language.

---

## 📞 Support

If you get stuck, consult:

| Issue | Consult |
|-------|---------|
| Setup question | QUICK_START.md |
| Unsure which chat to use | ROLES_INDEX.md → Quick Navigation |
| Need to understand role | ROLE_*.md (relevant role file) |
| How roles connect | ROLES_COORDINATION.md |
| General navigation | This README |

---

## 🎯 The Bigger Goal

From TWEAK_RESEARCH.md:

> **"I understand how this application thinks, so I can operate it almost without thinking about the interface."**

Everything in this system is in service of that goal:

- **Researcher** ensures principles are *discoverable* (they come from real patterns)
- **Dev** ensures they're *implementable* (they can be coded without compromise)
- **Playground** ensures they're *intuitive* (they feel good to artists)

Together, they discover Mirai-Bastel's interaction language **before** locking in shortcuts.

---

Good luck. 🎨

Last updated: September 12, 2026
