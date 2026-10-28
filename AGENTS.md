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

If implementation reveals that a documented architectural decision is wrong, record the problem and the chosen
direction in the decision document **in the same change** that implements it. Proposing alternatives and an
independent review are for genuinely open, consequential choices (competing architectures, a changed product
behaviour, an unknown risk) — not for every adaptation of a documented direction.

Small implementation details do not require formal architecture decisions. Fundamental boundaries do.
"Silently" is the failure: an undocumented change. A documented, tested change in one step is not.

## 6. Preserve independent reviews

Fresh AI reviews can contain information that disappears during later discussion. When a review is made, archive
the first-pass response before prolonged discussion. Do not edit an archived independent review to make it agree
with the final decision.

A review is a tool for a consequential open decision, not a mandatory stage: request one when the choice is hard
to reverse, changes product behaviour, or the evidence is contested. Do not order a review merely to reconfirm a
direction that measurements, tests and established implementations already support.

## 7. Scope discipline

`src/` contains production code.

`experiments/` is the research and prototype area. It may be pragmatic, temporary and disposable. Do not copy an experiment's file structure into `src/` without first extracting and validating the actual architectural requirements.

Do not build future systems merely because the vision mentions them. Known future requirements should influence boundaries, but implementation should be driven by real use cases and experiments.

A Lab tests new ideas; it does not rebuild application capabilities (selection, hover, input handling, gizmo, grid, pivot …). If a Lab would need one, stop and report (Development System §5, Haltepunkte) instead of rebuilding it.

**Input truth (AD-013 addendum 2026-10-28):** every key resolves through the one `BindingSet`. Code defaults
(`src/mirai/interaction/bindings.py`) are engineering, `PROVISIONAL`, until Manu explicitly approves the particular
binding. Manu's accepted bindings are recorded in repo-tracked `config/keymap.json`, loaded by `src/main.py` and
every Lab host using `Application`. Agents read the file and may add/update an entry only after Manu explicitly says
that key is right (e.g. “Taste passt” or KEEP for that key in a practical test); include `"set": "YYYY-MM-DD"` using
the decision date and preserve Manu's wording in the commit message. Never add or move entries on an agent's own
judgment. Before adding a code default, check its key against the file. No key literal in a window or host; only the
fixed modifier grammar (`bindings.FIXED_MODIFIER_RULES`) is read from held keys.

## 7a. Engineering velocity (Manu, 2026-10-21)

Own the engineering. Use the available evidence. Learn from established software. Automate technical verification.
Ask the Artist to judge the things that genuinely require an Artist.

- **Solve, don't re-study.** Read the instructions, the existing code, tests, measurements and decisions; establish
  what is known and what is genuinely uncertain; then implement when the evidence is sufficient. Do not repeat
  audits, probes or experiments that only reconfirm established findings, and do not deliver another plan when
  the next useful step is implementation and no material decision is blocked.
- **Experiments are optional tools, not stages.** Build a separate experiment only for a concrete, material
  uncertainty (competing architectures, an unknown API constraint, a risk the codebase cannot assess). A technique
  already validated in an experiment, a benchmark, an upstream project (Blender, other mature open-source tools) or
  a related subsystem goes straight into the production path: known bottleneck → established solution →
  production implementation → automated verification → measurement.
- **Established software is the reference.** Look at how Blender and other mature tools solve mesh operations,
  picking, selection, spatial acceleration, topology updates, undo and drawing; adapt the algorithm and data
  structure to Mirai's architecture rather than reinventing it. Respect licenses; do not copy GPL code into the
  repository.
- **Technical validation is the agent's job.** Correctness is established by tests (contract, regression,
  equivalence against an oracle, randomised sequences), invariant checks and reproducible benchmarks — not by
  Manu acting as a test runner. Ask for his practical check only for feel, usability, visual quality, workflow,
  or behaviour that depends on his reference PC. Always say which result is test-verified, which is measured on
  which hardware, and which still needs the reference PC; never claim an unmeasured speed-up.
- **Shared causes first.** When several operations are slow, find the common bottleneck (history, derived data,
  buffers, picking, selection) and fix it once for all of them. Consider the whole user-visible operation
  (input, pick, mesh update, buffers, history, frame). Do not rewrite working subsystems for neatness alone.
- **Larger coherent steps.** Group changes that share a bottleneck into one reviewable, verified unit. Do not stop
  after an audit or a plan unless the task is discovery-only, a real blocker exists, or an open decision prevents
  implementation. Keep docs in sync with meaningful changes; documentation does not replace implementation.
- **Report** what changed, what was verified (and how), what the measurements actually show, and what remains open.

## 8. Agent task discipline

An assignment is defined by its outcome, not by its steps:

- **Discovery:** one Artist test session (20–40 min, several points). Build, test and fix internally as often as needed; return with one consolidated practical test. When the direction is unclear, build switchable variants instead of sequential rounds.
- **Production:** run autonomously until the Definition of Done.

Within an assignment, decide in your evidence domain and continue; stop only at the Haltepunkte in Development System §5. Mark agent-set choices `PROVISIONAL`. Do not ask Manu to choose between technical approaches when evidence and engineering judgement suffice; choose a sound default and state the trade-off.

An assignment may arrive as Manu's verdicts and notes in plain words, without a handoff. Then apply M1 yourself and state your reading of his notes as assumptions in the new practical test, so he can correct it in one sentence.

For large Production packages, establish before starting: the relevant decision documents, scope and not-in-scope, acceptance criteria and expected tests — briefly, as working notes, not as a separate deliverable.

At the end of every finished slice, say in one or two lines whether the next step is better done in the same session or in a fresh one (and why), and name the suggested Claude model and reasoning effort for it (Manu, 2026-10-14). An independent review always goes to a fresh session (Erzeuger ≠ Bewerter, Development System §6).

## 8a. Test strategy (token- and runtime-efficient)

**Principle:** run the smallest test set that gives meaningful evidence for the current change; widen only when a shared dependency, an integration boundary or an observed failure justifies it. The agent selects the suites itself — the Artist is not asked which tests to run.

Test runner: **pytest** (tests bootstrap `src/` onto the path themselves). Bare `pytest` runs the default trees from `pytest.ini` (`tests/` and `experiments/morph_lab/tests`); for targeted runs always pass an explicit path. Setup: `pip install -r requirements-dev.txt`; pyglet needs a display, so headless runs use `xvfb-run -a pytest …`. Without it, pyglet-dependent tests are *skipped*, not green — report "N skipped" as skipped, never as a pass.

**Test trees**

| Tree | Covers | Runs |
|---|---|---|
| `tests/` | Production: `src/core`, `src/mirai`, `src/viewport`, `src/main.py` | default |
| `experiments/morph_lab/tests/` | the Morph Lab (started by the app through `src/morph_bridge.py`), on the `Application` path through H7 | default |
| `experiments/knife_oracle/tests/` | frozen Knife Face Lab engines + golden / differential / `split_face` equivalence tests for the Production Knife | trigger list below |
| `experiments/mehlsack_lab/`, `experiments/drag_cost/` | the lab itself / the GL cost probe | only when that folder changed |

Nothing in `src/` or `tests/` imports from `experiments/` (verified 2026-10-24; check with `grep -rn "experiments" --include=*.py src tests` before relying on it). Morph and Mehlsack Lab pin with their own import-boundary tests that they load only `src/`.

**1. While implementing — targeted tests only.** Never run a whole tree after each small change. Run the tests that exercise the changed behavior:

```bash
pytest tests/test_<module>.py -q                      # one test file
pytest tests/test_<module>.py::test_name -q           # one test
pytest tests -k "<pattern>" -q                        # pattern match
```

Add `-x` to stop at the first failure and `--lf` to re-run only the last failures. To find the tests for a changed function, grep for its name or module (`grep -rln "<name>" tests experiments`) rather than guessing from filenames.

**2. Choose the scope by what the change can actually affect, not by which file changed:**

- **Docs, comments, AGENTS/CLAUDE.md:** no tests. Check the edit itself (links, commands, diff).
- **Confined to one lab folder:** that lab's tests — targeted while working, the folder once at the end.
- **`src/` (shared code):** run `tests/` for the module plus the targeted tests of its consumers (grep `tests/` and `experiments/morph_lab`). Run `experiments/morph_lab/tests` when `viewport` drawing, `Application` keys or scene files changed; the Knife oracle on its trigger list.
- **`src/core` (frozen V1 baseline) or a public contract of `src/mirai`/`src/viewport`:** `tests/` fully plus the affected consumer trees.

**3. Final verification — once, after targeted tests are green.** Run the tree(s) your scope selection named, a single time:

```bash
pytest tests -q                               # when src/ changed
xvfb-run -a python -m pytest tests/test_gl_*.py -q   # GL tests in their own process (see CLAUDE.md, Testing)
pytest experiments/morph_lab/tests -q         # when Morph Lab code, `viewport` drawing, `Application` keys or scene files changed
xvfb-run -a pytest experiments/knife_oracle/tests -q   # Knife trigger list below
```

**Knife oracle** (`experiments/knife_oracle/tests`, 351 tests, ≈ 64 s measured 2026-10-24): run it once at the end when a change touches `src/mirai/topology/knife*.py`, `face_geometry.py`, `topology_points.py`, `connect_per_face.py`, `connect_vertices_per_face.py`, or the `src/core` topology mutators and change journal (`split_face`, `add_face`, `remove_face`, `begin_change`…). The engines are frozen on purpose (change one only to keep it running, never to follow Production).

Run all trees only for integration/promotion milestones (an experiment enters `src/`, a shared production path changes, or several trees are demonstrably affected) — not merely because they exist. Widen the run whenever targeted tests fail somewhere outside the expected area.

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

> **Capture first. Decide on evidence. Implement. Verify automatically. Ask the Artist about what only an Artist can judge.**

The goal is not to predict the entire final system. The goal is to deliver useful capability now while preventing
known future goals from being made unnecessarily expensive. Discussion is for genuinely open decisions; where the
evidence suffices, the next step is implementation (§7a).
