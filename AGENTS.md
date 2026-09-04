# Mirai-Bastel — Agent Guide

This repository is developed by a human project owner together with multiple AI systems. The repository itself is the durable project memory.

## 1. Read context before changing code

Before working in a repository area:

1. Read the nearest `README.md`.
2. Read the relevant plan/specification for that area.
3. Follow links to applicable architecture, design, research and future-idea documents.
4. Check whether the requested information or decision already has an authoritative document.
5. Do not assume experiment code is production architecture.

When a task crosses boundaries, read the relevant parent-level documentation as well.

## 2. Documentation is part of the engineering system

Documentation is not disposable chat notes. It records the current architecture, requirements, decisions, research and experiment results so that a new human or AI can continue the project without relying on conversation history.

### Single Source of Truth

Each important piece of information should have one authoritative home.

Do not create a second document containing the same canonical information merely because a local task would be convenient. Link to the authoritative document instead.

Before creating a new Markdown file, ask:

- Does an existing document already cover this?
- Should the information be added to an existing document?
- Is this genuinely a new document type or scope?

If an existing document changes role, move/merge/rename it rather than leaving competing versions behind.

## 3. Documentation hierarchy

The intended navigation is:

```text
Root README
    ↓
Docs / Experiments index
    ↓
Local README
    ↓
Plan / Spec / Design / Research / Decision
```

Every substantial experiment area should have a local `README.md` that links to relevant higher-level documents.

### Canonical

Current architecture, requirements and accepted decisions.

### Design / Future Ideas

Interaction principles, UX direction and ideas deliberately not yet implemented.

### Research

Evidence, historical findings and technical investigation.

### Reviews / Archive

Independent reviews, historical plans and superseded material that remains useful as project memory.

### Experiments

Working prototypes and practical investigations. Experiment results may inform production decisions but do not become production architecture automatically.

## 4. Keep documentation current

When code or an experiment changes a documented fact, update the authoritative document in the same logical change whenever practical.

Do not leave a canonical document describing an obsolete state when a newer state is already accepted.

For completed experiments, record the final result and point readers to the next relevant experiment or decision.

## 5. Never silently change architecture

If implementation reveals that a documented architectural decision is wrong:

1. document the problem;
2. propose alternatives;
3. review the alternatives;
4. update the architectural decision;
5. then implement the new direction.

Small implementation details do not require formal architecture decisions. Fundamental boundaries do.

## 6. Preserve independent reviews

Fresh AI reviews can contain information that disappears during later discussion. Important first-pass reviews should therefore be preserved before prolonged discussion whenever practical.

Do not edit an archived independent review to make it agree with the final decision.

The preferred flow is:

```text
Research / Question
      ↓
Independent review(s)
      ↓
Archive fresh responses
      ↓
Discussion / assessment
      ↓
Architecture decision
      ↓
Update canonical documentation
      ↓
Implementation
```

## 7. Scope discipline

`src/` contains production code.

`experiments/` is the research and prototype area. It may be pragmatic, temporary and disposable. Do not copy an experiment's file structure into `src/` without first extracting and validating the actual architectural requirements.

Do not build future systems merely because the vision mentions them. Known future requirements should influence boundaries, but implementation should be driven by real use cases and experiments.

## 8. Agent task discipline

Before assigning or starting a large implementation task, establish:

- relevant architecture/design document;
- explicit scope;
- acceptance criteria;
- allowed files/components;
- expected tests;
- known constraints;
- unresolved questions.

Prefer small, bounded implementation tasks over vague requests.

## 9. Development reality check

Before implementing any non-trivial task, verify the plan against the actual repository state.

- Planning ≠ implementation ≠ verification ≠ integration.
- Never treat “Gate complete”, “completion report”, “approved”, or “ready” as proof that code exists.
- Repository reality has priority: actual code/tests > current decisions/ADRs > plans > historical docs.
- Later architecture decisions, experiments, or UX changes may supersede earlier plans.
- If the intended architecture is unclear or a newer result contradicts the plan, stop and report the discrepancy before coding.

Before coding, briefly verify: current branch/commit, current architecture/ADRs, relevant experiments, possible superseding decisions, and acceptance criteria.

After coding, report only what actually exists, was tested, and passed.

## 10. Project principle

> **Capture first. Discuss second. Decide third. Implement fourth.**

And:

> **Implement little. Assume much.**

The goal is not to predict the entire final system. The goal is to keep today's implementation small while preventing known future goals from being accidentally made unnecessarily expensive.
