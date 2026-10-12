# Reusable Software Development Prompts

A small, project-independent collection of prompts for recurring software-development work with AI coding assistants.

The prompts are written in English for portability and token efficiency. Copy one into the chat or coding session for the project you are working on, then fill in any placeholders that matter.

These are **task templates**, not permanent project instructions. Project-specific rules, architecture decisions, repository conventions and validation requirements take precedence. In a repository, read its agent instructions first (for example, `AGENTS.md`, `CLAUDE.md` or the equivalent).

## How to use this collection

1. Choose the smallest prompt that fits the task.
2. Replace bracketed placeholders such as `[FEATURE]` only where needed.
3. Let the agent inspect the existing project before proposing or changing anything.
4. Keep planning, implementation, verification and manual acceptance distinct.
5. Add a prompt here only when a workflow recurs often enough to justify maintaining it.

For Claude Code, a stable workflow may later become a custom Skill or slash command. Keep the general template here; put project-specific instructions in that project's own configuration or skill.

---

## 01 — Project Status Audit

**Use when:** returning to a project after a break, orienting a new AI session, or deciding what to do next.

```text
Read the repository's agent instructions first.

Audit the current project state using the repository itself, not conversation history alone.

1. Inspect the current branch and working-tree state where available.
2. Read the relevant project overview and authoritative planning/architecture documents.
3. Verify important status claims against the current code and tests.
4. Identify completed work, genuinely open work, stale documentation, contradictions, and unresolved decisions.
5. Distinguish implemented, automated-tested, integrated, and manually/user-validated capabilities.
6. Recommend the smallest useful next step and explain why it has priority.

Do not modify files, run unrelated tests, or claim validation that is not evidenced.

Report:
- Current verified state
- Important gaps or contradictions
- Open decisions requiring the project owner's input
- Recommended next step
- Sources inspected
```

## 02 — Prepare the Next Task

**Use when:** turning an idea or broad goal into a bounded implementation task.

```text
Read the repository's agent instructions first. Inspect the relevant code, tests, documentation and prior decisions before proposing a solution.

Prepare a small, implementation-ready task for: [TASK / FEATURE].

Include:
1. The user-visible goal and explicit non-goals.
2. Existing code or validated work that should be reused.
3. Relevant files, modules and architectural boundaries.
4. Acceptance criteria that can be checked objectively.
5. The smallest meaningful test plan, including what does not need to be tested and why.
6. Risks, dependencies and unresolved questions.

Do not implement yet. Do not assume that a plan or previous completion report proves the feature exists. If repository evidence conflicts with the request or intended architecture, explain the discrepancy before proceeding.

Prefer adapting validated work over rebuilding it. Keep the task small enough to review.
```

## 03 — Documentation Consistency Check

**Use when:** after a substantial task, at the end of a work session, or during a periodic project review.

```text
Read the repository's agent instructions first.

Compare the current repository state and recent changes with the relevant documentation, including the root README, roadmap, project overview and local authoritative documents where applicable.

1. Find only the documentation affected by the current changes or by a clear inconsistency.
2. Correct stale status statements, contradictions, outdated links and misleading claims.
3. Keep each important fact in its authoritative home; link to it rather than copying canonical content.
4. Update summaries and indexes only when the underlying state actually changed.
5. Preserve the existing documentation architecture. Do not rewrite unrelated files or create a parallel tracking system.
6. Clearly distinguish implementation, automated test results, integration and manual/user validation.

Make the smallest justified documentation changes. Do not change code or run unrelated tests.

Report:
- Files changed and the reason for each change
- Inconsistencies corrected
- Anything still uncertain or requiring the project owner's decision
- If no changes were needed, say so
```

## 04 — Critical Architecture and Code Review

**Use when:** evaluating a proposed design, reviewing a plan, or checking an implementation for unnecessary complexity.

```text
Read the repository's agent instructions and relevant authoritative architecture documents first.

Independently review this proposal or change: [PROPOSAL / CHANGE].

Look specifically for:
1. Existing validated code or prior work that should be reused.
2. Duplicate implementations, unnecessary abstraction, overengineering or premature generalization.
3. Violations of documented architecture and dependency boundaries.
4. Incorrect assumptions, hidden coupling, edge cases and failure/recovery behavior.
5. Missing tests or claims that are stronger than the available evidence.
6. A simpler solution that satisfies the same requirements.

Separate evidence-based findings from hypotheses. For each significant finding, give the consequence and a concrete recommendation. Do not agree merely to be supportive.

Do not edit files or implement a replacement unless explicitly asked. Do not treat experimental code as production-ready without checking the project's promotion/acceptance rules.

Finish with:
- Blocking issues
- Important non-blocking concerns
- What is already sound and should be preserved
- Recommended next action
```

## 05 — Task Completion and Handover

**Use when:** implementation or a bounded task is finished and the work needs to be left in a reliable state.

```text
Read the repository's agent instructions and follow its test and documentation rules.

Review the changes made for this task: [TASK].

1. Inspect the final diff and confirm the changes remain within scope.
2. Run the smallest meaningful final verification required by the repository's rules. Do not rerun unrelated suites.
3. Update the authoritative documentation and relevant project indexes if the verified state changed.
4. Check for accidental files, stale claims, missing links and unfinished TODOs introduced by this task.
5. Do not commit, push, merge or change branches unless explicitly authorized.

Report accurately:
- What changed
- Tests/checks actually run and their exact outcomes, including skipped tests
- What was not tested and why
- Documentation updated
- Remaining limitations or follow-up work
- Whether manual/user acceptance is still needed

Never describe a feature as working, integrated or user-validated unless the available evidence supports that exact claim.
```

---

## General guardrails

These principles apply to all templates:

- **Repository evidence wins:** inspect the actual code, tests and current decisions; do not rely on chat history or old task reports alone.
- **Preserve validated work:** reuse or adapt existing solutions unless there is evidence they are unsuitable.
- **Smallest useful scope:** avoid unrelated refactors, broad test runs and documentation rewrites.
- **Respect project boundaries:** experiments, prototypes and production code may have different acceptance rules.
- **Be precise about evidence:** planned, implemented, tested, integrated and manually accepted are different states.
- **Keep ownership explicit:** ask the project owner when a product, UX or architectural decision is genuinely theirs to make.
- **No surprise side effects:** do not commit, push, merge, delete or make unrelated changes without authorization.

## Future additions

Add another template only when a recurring task is not adequately covered above. Potential candidates include release preparation, bug investigation, test-failure triage and preparing a practical/manual acceptance test. Prefer a small set of dependable prompts over a large catalogue of near-duplicates.
