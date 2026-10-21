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
- `src/main.py` — the production app (own window). `playground/` — Artist research host (selection, tweak,
  topology, articulation experiments live inside it as variant families); depends on `src/` plus a
  small number of helpers from `experiments/mirai_bastel_integration_lab` and
  `experiments/rigging-skinning-morphing` (OBJ→Scene loading, camera framing, the head asset).
  Own test tree: `playground/tests/` (run via `pytest playground/tests`).
- Labs under `experiments/<lab>/run.py` start their own windows; see `experiments/README.md`.
- `experiments/` — Research, prototypes, practical validation at the repository level (OK to be
  messy). Not the same thing as `playground/experiments/` (variant families inside the Playground
  host) — see `docs/design/artist_playground/EXPERIMENT_HOST.md` for that distinction.
- `tests/` — pytest suite for Production (`src/`). Bootstrap adds `src/` to path. `pytest.ini` at the
  repo root sets `testpaths` (`tests`, `playground/tests`, `experiments/symmetry_lab/tests`,
  `experiments/subdivision_lab/tests`, `experiments/morph_lab/tests`), so bare
  `pytest` collects cleanly (the old `viewport`/`test_core.py` name collisions with
  `experiments/` came from collecting everything; see
  `docs/Repository_Wide Structural_Codebase_Health_Audit.md` D1).
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
   - Example: Camera was validated in Integration Lab, adapted for Viewport, documented in Architecture. Don't rebuild it without reason.
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
   pytest playground/tests/test_<module>.py -q         # playground/ changes
   ```
   Useful flags: `-x` (stop at first failure), `--lf` (re-run last failures only).

Details:

- Tests live in `tests/test_*.py` and use pytest conventions
- Test bootstrap (`_bootstrap.py`) adds `src/` to path; tests import directly from `src.core` etc.
- Setup: `pip install -r requirements-dev.txt` (pytest, pyglet). pyglet needs a display even on import;
  headless (cloud/CI): prefix with `xvfb-run -a`. Without pyglet/display the repo-root `conftest.py`
  turns exactly those failures into visible *skips* (any other error stays an error) — so
  "N skipped" in playground/ can mean "environment", not "green"; run with xvfb for the real result.
- GL tests (`tests/test_gl_*.py`) are *skipped* inside a combined run when another module has already switched pyglet
  to headless/EGL first (`test_main_wiring.py` and others set `pyglet.options["headless"]`); in a container without
  EGL run them in their own process: `xvfb-run -a python -m pytest tests/test_gl_*.py -q` (observed 2026-10-21).
- `tests/_archive/` holds obsolete tests (e.g. the stale V1 `test_extrude_tool`); `pytest.ini`
  excludes it. Don't re-add `--ignore` workarounds — fix the cause or archive with a date.
- The Symmetry Lab runs on the `src/mirai/application.py` path (start: `python experiments/symmetry_lab/run.py [asset]`,
  WP-SYM-LAB-03), so shared `src/` changes it can reach are checked against its tests (scope rules: AGENTS.md §8a)
- `_measure_coverage.py` is a self-described *temporary* Gate-3 coverage script, not a general tool

## Documentation maintenance

- When code changes a documented decision, update the `docs/` source of truth *in the same commit*
- Keep `docs/README.md` index current; it is the navigation map
- Mark obsolete documents with a date; don't delete them (project memory)
- For completed experiments, write a short result summary and point to next step

## Architecture constraints to respect

- `core/` mesh operations must remain topology-safe (see `tests/mesh_invariants.py`)
- History is decoupled from Mesh internals (see `AD-003` if it exists)
- Viewport is separate from Core (data flows Core → Viewport, never back)
- Future systems (rig, anim, script) must not be blocked by current Core boundaries

## When in doubt

1. Check `docs/` for prior decisions
2. Read the nearest `README.md` in that directory
3. Look at recent git history for context
4. Ask: "Is this a research experiment or a production change?" If unclear, default to `experiments/`

---

**Last revised**: 2026-10-21  
See [AGENTS.md](AGENTS.md) for full collaboration model.
