# Mirai-Bastel — CLAUDE.md

This file is for AI collaborators. Read [AGENTS.md](AGENTS.md) first for project philosophy.

## Quick reference

**Repo**: Python 3.9+, pytest, no virtual env required (direct PYTHONPATH injection in tests).

**Structure**:
- `src/core/` — Production: V1 Core baseline, frozen (don't change without explicit reason)
- `src/viewport/`, `src/mirai/` — In-progress production areas
- `experiments/` — Research, prototypes, practical validation (OK to be messy)
- `tests/` — pytest suite. Bootstrap adds `src/` to path; run via `pytest tests/`
- `docs/` — Architecture, design, research decisions. Hierarchy: `README.md` → index → local docs → plans/specs
- `references/` — External material (historical Mirai docs, etc.)

## Project workflow

```
Research question / Feature idea
    ↓
Create experiment in experiments/
    ↓
Validate with tests/ (if applicable)
    ↓
Document findings in docs/ (research/ or reviews/)
    ↓
Architecture decision (if needed)
    ↓
Move validated code to src/ (only if decision is explicit)
```

**Key rule**: Never graduate an experiment to `src/` without documenting *why* and *what* in `docs/`. Small does not mean unreviewed.

## Before changing or rebuilding code

1. Read the nearest `docs/README.md` or design document
2. **Check the Architecture Map**: Is there an existing, validated solution already documented?
   - Example: Camera was validated in Integration Lab, adapted for Viewport, documented in Architecture. Don't rebuild it without reason.
3. If touching `src/core/`, read any relevant Architecture Decision in `docs/`
4. If working in `experiments/`, you have more freedom, but results still need docs
5. Check git history (`git log --oneline -20 src/`) to understand recent decisions
6. Run relevant tests to verify current state: `pytest tests/test_core.py` (etc.)

**Golden rule**: If a solution exists, is documented, tested and working — use it or adapt it. Don't rebuild it. Rebuilding creates technical debt, orphaned solutions, and regressions on already-solved problems.

## Code conventions

- **Type hints**: Yes, use them (Python 3.9+ supports `list[T]` syntax)
- **Naming**: Classes are `PascalCase`, functions/methods are `snake_case`
- **Comments**: Only for *why*, not *what*. Non-obvious invariants, workarounds, architectural constraints
- **Imports**: Organize as stdlib, third-party, local; prefer relative imports in `src/`

## Testing

- Tests live in `tests/test_*.py` and use pytest conventions
- Test bootstrap (`_bootstrap.py`) adds `src/` to path; tests import directly from `src.core` etc.
- Before submitting, run: `pytest tests/ -v` (or specific file)
- Use `_measure_coverage.py` to check test coverage

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

**Authored**: 2026-09-10  
See [AGENTS.md](AGENTS.md) for full collaboration model.
