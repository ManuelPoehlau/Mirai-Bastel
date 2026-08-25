# Mirai-Bastel — Human + AI Team Workflow

> **Status:** Project working agreement v0.1
>
> This document defines how the human developer and multiple AI systems collaborate on Mirai-Bastel.

## 1. Why this exists

Mirai-Bastel is intentionally developed as a long-lived, research-driven project with a human developer and multiple AI assistants/agents.

The main risks of this workflow are:

- context drift during long conversations
- earlier conclusions being forgotten or subtly changed
- different AIs independently making incompatible assumptions
- valuable first-pass ideas disappearing into chat history
- large agents consuming limited monthly usage on poorly specified tasks
- later discussions accidentally rewriting the historical record

Git is therefore not only the source-code repository. It is also the **project memory and decision record**.

## 2. First-response preservation rule

When an AI is asked for an important architectural, research or design review, its **first substantive response should be preserved verbatim before entering a long follow-up discussion**, whenever practical.

Reason:

> Fresh analysis is an independent perspective. Long conversations can introduce anchoring, context drift, agreement bias and forgotten alternatives.

The original response is an immutable research artifact. Discussion may follow, but must not silently replace it.

Recommended filename:

```text
<topic>_REVIEW_<AI>_001.md
```

Examples:

```text
V1_CORE_REVIEW_CLAUDE_001.md
V1_CORE_REVIEW_CHATGPT_001.md
V1_CORE_REVIEW_CODEX_001.md
```

## 3. Never mix source opinion with our conclusion

An AI review and the team's decision are different artifacts.

### AI review

Contains what the AI originally said, preferably unchanged.

### Team assessment

Contains our interpretation afterwards:

```text
ACCEPT
REJECT
INVESTIGATE
DEFER
```

with reasoning and references to the relevant review.

Do not edit the original review to make it agree with the final architecture.

## 4. Architecture decision flow

For significant decisions use this sequence:

```text
Research / Question
       |
       v
Independent AI review(s)
       |
       v
Archive first responses
       |
       v
Cross-review / discussion
       |
       v
Human + AI assessment
       |
       v
Architecture Decision
       |
       v
Update canonical architecture document
```

The canonical architecture document represents the **current decision**. Archived reviews preserve the reasoning and alternatives that led there.

## 5. Multiple AI roles

Different AI systems should be used for their strengths rather than asked to perform every task identically.

Possible roles include:

- **Research / historical archaeology** — primary source discovery, source comparison, technical reconstruction
- **Architecture review** — challenge assumptions, identify coupling and future dead ends
- **Implementation agents** — execute clearly specified, bounded coding tasks
- **Code review** — independently inspect implementations and tests
- **Documentation** — maintain coherent technical records
- **Alternative design review** — deliberately argue against the current approach

The exact assignment may change over time.

No AI has automatic authority over the architecture merely because it produced a suggestion.

## 6. Fresh-context reviews are valuable

For major decisions, at least one review should ideally be performed from the current canonical documents **without feeding the reviewer the entire preceding conversational debate**.

This gives us an independent opinion and helps detect:

- hidden assumptions
- accumulated context bias
- premature consensus
- ideas that disappeared during discussion

## 7. Agents and limited usage budgets

Large coding agents and agents with limited monthly usage should receive tasks only after the task is sufficiently specified.

Before assigning a large implementation task, we should have:

- relevant architecture document
- explicit scope
- acceptance criteria
- files/components allowed to change
- tests expected
- known constraints
- unresolved questions identified

Avoid spending scarce agent usage on vague prompts such as:

> "Build Mirai."

Prefer:

> "Implement the topology API described in `docs/architecture/DATA_MODEL.md`, including tests. Do not change the public Selection API."

## 8. No silent architecture drift

An implementation must not silently redefine architectural decisions.

If implementation reveals that an architecture decision is wrong:

1. document the problem
2. propose alternatives
3. review the alternatives
4. update the architecture decision
5. then implement the new direction

Small implementation details do not require a formal decision every time. Fundamental boundaries do.

## 9. Historical research is evidence, not authority

Mirai/N-World/S-Geometry behavior should be reconstructed from evidence where possible:

- original documentation
- contemporary articles
- preserved software/distributions
- source code or source fragments
- developer interviews
- patents/papers
- period demonstrations/videos
- later secondary sources

Each source should be classified by confidence where useful.

Historical behavior should inspire the architecture, but a historical implementation detail should not be reproduced merely because it is old.

## 10. AI-generated code is reviewable code

All AI-generated code is treated like code from another developer:

- it must be understandable
- it must fit the architecture
- it must have appropriate tests
- it must not introduce unnecessary dependencies
- it must not silently alter unrelated systems

"The AI wrote it" is never an architectural justification.

## 11. Canonical documents vs. working discussion

The repository should distinguish between:

### Canonical

Current architecture, requirements and accepted decisions.

### Research

Evidence and historical findings.

### Reviews

Independent AI/human critiques.

### Decisions

Why a significant architectural choice was accepted or rejected.

### Code

The implementation of the current decisions.

Chat is a workspace. **Git is the durable memory.**

## 12. Preserve disagreement

A rejected idea can be valuable later.

Do not erase a well-reasoned alternative simply because the team currently rejected it. Record the alternative and why it was rejected.

This is particularly important for a project expected to evolve over years.

## 13. Human remains the final integrator

The human project owner has final authority over:

- project direction
- scope
- architecture acceptance
- external dependencies
- release decisions
- whether an AI suggestion becomes part of the project

AI systems are collaborators, reviewers and implementation tools — not autonomous project owners.

## 14. The core principle

> **Capture first. Discuss second. Decide third. Implement fourth.**

And for important AI reviews:

> **Archive the fresh first answer before the conversation can change it.**

This is a project rule intended to keep Mirai-Bastel coherent even as humans, AI systems, tools and development environments change over time.
