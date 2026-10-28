# Mirai-Bastel — CLAUDE.md

This file is for AI collaborators. Read [AGENTS.md](AGENTS.md) first for project philosophy.

## Quick reference

**Repo**: Python 3.9+, pytest, no virtual env required (direct PYTHONPATH injection in tests).

**Structure**:
- `src/core/` — Production: V1 Core baseline, contract-frozen: interfaces, IDs and data integrity are protected
  by contract tests; internals may change when profiling or established techniques justify it
  (CORE_V1_FREEZE §7, Manu 2026-10-21). Since 2026-10-21 every `Mesh` mutation records into a change journal
  (`begin_change` / `end_change` / `rollback_change`, `MeshDeltaCommand`, `Mesh.watch()`): use it for history,
  rollback and derived data instead of `export_state()` / `load_state()` snapshots.
- `src/viewport/`, `src/mirai/` — In-progress production areas
- `src/main.py` — the production app (own window); it is the product.
- `experiments/` — the few active research tools (index: `experiments/README.md`): `morph_lab` (Morph is not in
  `src/`; the app starts it through `src/morph_bridge.py`), `mehlsack_lab` (open Artist verdicts), `drag_cost`
  (GL cost probe) and `knife_oracle` (frozen engines; regression coverage for the Production Knife). Labs start
  their own windows via `experiments/<lab>/run.py`. Removed labs and the Playground (2026-10-24) are listed with
  their last commit in `experiments/README.md`; their docs are in `docs/archive/experiments_2026-10/`.
- `tests/` — pytest suite for Production (`src/`). Bootstrap adds `src/` to path. Bare `pytest` runs `tests/` and
  `experiments/morph_lab/tests` (`pytest.ini`); every other tree only when named (AGENTS.md §8a).
- `docs/` — Architecture, design, research decisions. Hierarchy: `README.md` → index → local docs → plans/specs
- `references/` — External material (historical Mirai docs, etc.)

## Project workflow

See `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` (§5 Haltepunkte, §7 Wer macht was) and AGENTS.md §7–§8.
Key rule: never move experiment code to `src/` without an explicit, documented decision. Working philosophy
(Manu, 2026-10-21): solve rather than re-study, experiments only for material uncertainties, technical
verification is the agent's job, shared bottlenecks first, larger coherent steps — AGENTS.md §7a.

## Before changing or rebuilding code

0. If the task is technical (performance, correctness), the default outcome is an implemented, tested,
   measured change — not a plan or another probe (AGENTS.md §7a)
1. Read the nearest `docs/README.md` or design document
2. **Check the Architecture Map**: Is there an existing, validated solution already documented?
   - Example: Symmetry, SubD and Soft Selection were validated in Labs and now live in `src/`; extend them there.
3. If touching `src/core/`, read any relevant Architecture Decision in `docs/`
4. If working in `experiments/`, you have more freedom, but results still need docs
5. Check git history (`git log --oneline -20 src/`) to understand recent decisions
6. Run tests only as AGENTS.md §8a describes (targeted, scoped).

**Golden rule**: If a solution exists, is documented, tested and working — use it or adapt it. Don't rebuild it. Rebuilding creates technical debt, orphaned solutions, and regressions on already-solved problems.

## Code conventions

- **Type hints**: Yes, use them (Python 3.9+ supports `list[T]` syntax)
- **Naming**: Classes are `PascalCase`, functions/methods are `snake_case`
- **Comments**: Only for *why*, not *what*. Non-obvious invariants, workarounds, architectural constraints
- **Imports**: Organize as stdlib, third-party, local; prefer relative imports in `src/`

## Testing

**Test strategy and scope rules: AGENTS.md §8a (single source).** Targeted commands:

   ```bash
   pytest tests/test_<module>.py -q                    # one test file
   pytest tests/test_<module>.py::test_name -q         # one test
   pytest tests -k "<pattern>" -q   # pattern match
   ```
   Useful flags: `-x` (stop at first failure), `--lf` (re-run last failures only).

Details:

- Tests live in `tests/test_*.py` and use pytest conventions
- Test bootstrap (`_bootstrap.py`) adds `src/` to path; tests import directly from `src.core` etc.
- Setup: `pip install -r requirements-dev.txt` (pytest, pyglet). pyglet needs a display even on import;
  headless (cloud/CI): prefix with `xvfb-run -a`. Without pyglet/display the repo-root `conftest.py`
  turns exactly those failures into visible *skips* (any other error stays an error) — so
  "N skipped" in a GL/pyglet test can mean "environment", not "green"; run with xvfb for the real result.
- GL tests (`tests/test_gl_*.py`) are *skipped* inside a combined run when another module has already switched pyglet
  to headless/EGL first (`test_main_wiring.py` and others set `pyglet.options["headless"]`); in a container without
  EGL run them in their own process: `xvfb-run -a python -m pytest tests/test_gl_*.py -q` (observed 2026-10-21).
- `tests/_archive/` holds obsolete tests (e.g. the stale V1 `test_extrude_tool`); `pytest.ini`
  excludes it. Don't re-add `--ignore` workarounds — fix the cause or archive with a date.

## Documentation maintenance

- When code changes a documented decision, update the `docs/` source of truth *in the same commit*
- Keep `docs/README.md` index current; it is the navigation map
- Mark obsolete documents with a date and move finished plans/handoffs to `docs/archive/` (project memory,
  outside the default reading path)
- For completed experiments, write a short result summary and point to next step

## Architecture constraints to respect

- `core/` mesh operations must remain topology-safe (see `tests/mesh_invariants.py`)
- History is decoupled from Mesh internals (see `AD-003` if it exists)
- Viewport is separate from Core (data flows Core → Viewport, never back)
- Input: the active `BindingSet` is the only input truth (AD-013 addendum 2026-10-28). `config/keymap.json` is
  Manu's — read it, never write it; check a new default key against it (AGENTS.md §7)
- Future systems (rig, anim, script) must not be blocked by current Core boundaries

## When in doubt

1. Check `docs/` for prior decisions
2. Read the nearest `README.md` in that directory
3. Look at recent git history for context
4. Ask: "Is this a research experiment or a production change?" Default to Production; a separate experiment
   only for a material uncertainty (AGENTS.md §7a)

---

**Last revised**: 2026-10-24  
See [AGENTS.md](AGENTS.md) for full collaboration model.
