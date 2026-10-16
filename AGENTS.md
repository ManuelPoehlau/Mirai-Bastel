# Mirai-Bastel — Agent Guide

This repository is developed by a human project owner together with multiple AI systems. The repository itself is the durable project memory.

## 1. Read context before changing code

Before working in a repository area:

1. Read the nearest `README.md`.
2. Read the relevant plan/specification for that area.
3. Follow links to applicable architecture, design, research and future-idea documents.
4. Check whether the requested information or decision already has an authoritative document.
5. Do not assume experiment code is production architecture.
6. For performance, rendering or GPU-feature questions, read `docs/architecture/REFERENCE_HARDWARE.md` (the developer/test PC).

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

## 4a. Artist overview

`docs/ATELIER.md` is Manu's German index of the current state, open verdicts and next candidates.
When a change alters something artist-relevant (a new verdict, a new open Artist question, a new capability
in `src/main.py`), update `docs/ATELIER.md` with the next commit that touches that area: one sentence plus a link,
never canonical content. Manu records verdicts himself where the practical test asks for them; his commit is the
record. Do not make a separate docs-only commit just to propagate verdicts or status.
A verdict counts only once it is recorded in its authoritative document, not when it appears in a chat or only here.

An **Atelier-Brief** (from the separate Mirai Atelier context, see Development System §8) carries Manu's intent,
references and open questions. It is Discovery input, not a decision and not a spec: apply M1 before acting on it,
and do not read an architecture or a solution into it that the brief does not state.

## 4b. Documentation by reader

- **Manu (German):** how to start, the current practical test, his verdict table — one block per test session.
- **Agents (English, terse):** only assumptions and findings a later agent needs. Prefer code comments and tests for implementation detail; do not enumerate every small engineering choice.
- **Canonical documents (ROADMAP, ADs, SOURCE_ARCHITECTURE) are not logs.** No per-slice or per-fix entries; Git history is the log. Add to an AD only when a decision is made or changes.
- A status fact lives in one place (the area README). Indexes (`docs/ATELIER.md`, `experiments/README.md`) hold one line plus a link.

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

A Lab tests new ideas; it does not rebuild application capabilities (selection, hover, input handling, gizmo, grid, pivot …). If a Lab would need one, stop and report (Development System §5, Haltepunkte) instead of rebuilding it.

## 8. Agent task discipline

An assignment is defined by its outcome, not by its steps:

- **Discovery:** one Artist test session (20–40 min, several points). Build, test and fix internally as often as needed; return with one consolidated practical test. When the direction is unclear, build switchable variants instead of sequential rounds.
- **Production:** run autonomously until the Definition of Done.

Within an assignment, decide in your evidence domain and continue; stop only at the Haltepunkte in Development System §5. Mark agent-set choices `PROVISIONAL`.

An assignment may arrive as Manu's verdicts and notes in plain words, without a handoff. Then apply M1 yourself and state your reading of his notes as assumptions in the new practical test, so he can correct it in one sentence.

For large Production packages and Architecture Gates, establish before starting: the relevant decision documents, scope and not-in-scope, acceptance criteria, expected tests and open questions.

At the end of every finished slice, say in one or two lines whether the next step is better done in the same session or in a fresh one (and why), and name the suggested Claude model and reasoning effort for it (Manu, 2026-10-14). An independent review always goes to a fresh session (Erzeuger ≠ Bewerter, Development System §6).

## 8a. Test strategy (token- and runtime-efficient)

**Principle:** run the smallest test set that gives meaningful evidence for the current change; widen only when a shared dependency, an integration boundary or an observed failure justifies it. The agent selects the suites itself — the Artist is not asked which tests to run.

Test runner: **pytest** (tests bootstrap `src/` onto the path themselves). `pytest.ini` defines `testpaths`, so bare `pytest` collects all three trees, but for targeted runs always pass an explicit path. Setup: `pip install -r requirements-dev.txt`; pyglet needs a display, so headless runs use `xvfb-run -a pytest …`. Without it, pyglet-dependent tests are *skipped*, not green — report "N skipped" as skipped, never as a pass.

**Test trees and what they cover**

| Tree | Covers |
|---|---|
| `tests/` | Production: `src/core`, `src/mirai`, `src/viewport` |
| `playground/tests/` | the Playground host (`playground/`) |
| `experiments/symmetry_lab/tests/` | the Symmetry Lab (`experiments/symmetry_lab/`) running on the `src/mirai/application.py` path |
| `experiments/subdivision_lab/tests/` | the SubD Lab (`experiments/subdivision_lab/`): the GL-free Catmull-Clark core and, since WP-SUBD-LAB-02, the lab on the `Application` path through the Viewport hook H7 (`set_surface_provider`) |
| `experiments/morph_lab/tests/` | the Morph Lab (`experiments/morph_lab/`): the GL-free morph evaluation and provider, and the lab on the `Application` path through H7 (second user) with its own scene file |

**Dependency facts (verify with a quick `grep -rln "<module>" --include=*.py .` if the code may have changed since):** Playground and Symmetry Lab both consume `src/core`, `src/mirai` and `src/viewport`. Playground additionally uses helpers from `experiments/mirai_bastel_integration_lab` and `experiments/rigging-skinning-morphing`. The Lab imports nothing from `playground/`, and nothing imports the Lab; `experiments/symmetry_lab/tests/test_import_boundary.py` enforces the first direction. Playground and Lab therefore share no code with each other — only `src/`.

**1. While implementing — targeted tests only.** Never run a whole tree after each small change. Run the tests that exercise the changed behavior:

```bash
pytest tests/test_<module>.py -q                      # one test file
pytest tests/test_<module>.py::test_name -q           # one test
pytest tests -k "<pattern>" -q                        # pattern match
pytest playground/tests/test_<module>.py -q           # playground/ behavior
pytest experiments/symmetry_lab/tests/test_<x>.py -q  # Lab behavior
```

Add `-x` to stop at the first failure and `--lf` to re-run only the last failures. To find the tests for a changed function, grep the test trees for its name or module (`grep -rln "<name>" tests playground/tests experiments/symmetry_lab/tests`) rather than guessing from filenames.

**2. Choose the scope by what the change can actually affect, not by which file changed:**

- **Docs, comments, AGENTS/CLAUDE.md:** no tests. Check the edit itself (links, commands, diff).
- **Confined to `experiments/symmetry_lab/` (incl. its tests):** Lab tests only — targeted while working; the whole Lab tree once at the end if shared Lab modules (`lab_app`, `lab_scene`, `lab_bindings`, `run`) changed. Playground and `tests/` have no dependency on Lab code, so they provide no evidence here. Exception: the Lab change was made to work around or alter a `src/` behavior — then it is a `src/` change (below).
- **Confined to `playground/` (or the experiments helpers only Playground uses):** `playground/tests`, targeted first and the tree once at the end. Lab and `tests/` are unaffected unless the change also touched `src/`.
- **`src/` (shared code):** first list the consumers of the changed module/function (grep imports across `tests/`, `playground/`, `experiments/symmetry_lab/`). Run `tests/` for the module, then the targeted consumer tests that exercise the changed behavior in each *affected* tree. Whole `playground/tests` or Lab tree only when the changed behavior is reached broadly (e.g. `src/core`, `Application`, command gate, `viewport` drawing/derived data, `scene_factory`); a change in a function only the Playground's knife tools call does not need the Lab tree.
- **`src/core` (frozen V1 baseline) or a public contract of `src/mirai`/`src/viewport`:** `tests/` fully plus the affected consumer trees — such a change affects every consumer, so the broader run is expected.

**3. Final verification — once, after targeted tests are green.** Run the whole tree(s) your scope selection named, a single time:

```bash
pytest tests -q                               # when src/ changed
pytest playground/tests -q                    # when playground/ or a Playground-reached src/ behavior changed
pytest experiments/symmetry_lab/tests -q      # when Lab code or a Lab-reached src/ behavior changed
pytest experiments/subdivision_lab/tests -q   # when SubD Lab code, `viewport` drawing or `Application` keys changed
pytest experiments/morph_lab/tests -q         # when Morph Lab code, `viewport` drawing, `Application` keys or scene files changed
```

Run all three trees only for integration/promotion milestones (an experiment enters `src/`, a shared production path changes, or several trees are demonstrably affected) — not merely because they exist. Widen the run whenever targeted tests fail somewhere outside the expected area.

Do not re-run a tree after each fix; if the final run fails, fix with targeted tests, then repeat only the failing tree once. Report exactly what was run and its result (passed / failed / skipped), and name the suites deliberately not run with the reason.

## 9. Development reality check

Before implementing any non-trivial task, verify the plan against the actual repository state.

- Planning ≠ implementation ≠ verification ≠ integration.
- Never treat “Gate complete”, “completion report”, “approved”, or “ready” as proof that code exists.
- Repository reality has priority: actual code/tests > current decisions/ADRs > plans > historical docs.
- Later architecture decisions, experiments, or UX changes may supersede earlier plans.
- If the intended architecture is unclear or a newer result contradicts the plan, stop and report the discrepancy before coding.

Before coding, briefly verify: current branch/commit, current architecture/ADRs, relevant experiments, possible superseding decisions, and acceptance criteria.

After coding, report only what actually exists, was tested, and passed.

## 10. Artist + AI Development System

This repository follows the development system defined in [`MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md`](MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md).

That document is the authoritative description of how the Artist and AI agents collaborate. In particular, agents must follow its five mechanisms:

- **M1 — History Awareness:** check existing, rejected and validated work before creating or replacing anything.
- **M2 — Context Check:** expose relevant assumptions when entering unfamiliar territory; do not turn this into a routine status ritual.
- **M3 — Promotion Boundary:** experiment code is not automatically product code; agents do not promote or claim Artist validation.
- **M4 — Artist Verdict:** ask the Artist only when Product Truth, Intent, Priority or Promotion cannot be established autonomously; prepare the smallest useful Artist test first.
- **M5 — Discovery ↔ Production:** a production implementation does not silently create new product decisions. Unexpected new findings return to Discovery.

Authority follows the evidence domain. Agents should decide autonomously where technical or other available evidence is sufficient and should not delegate decisions merely for reassurance. The Artist is the authority for Intent, Product Truth, Priority and Promotion.

The core optimization criterion is:

> **So viel autonome AI-Arbeit wie möglich, bei so wenig notwendiger Artist-Aufmerksamkeit wie möglich, ohne Intent und Erkenntnisqualität zu verlieren.**

Do not introduce additional process mechanisms, documentation systems or management layers merely because they seem useful. A new mechanism must solve an actual observed failure.

## 11. Project principle

> **Capture first. Discuss second. Decide third. Implement fourth.**

And:

> **Implement little. Assume much.**

The goal is not to predict the entire final system. The goal is to keep today's implementation small while preventing known future goals from being accidentally made unnecessarily expensive.
