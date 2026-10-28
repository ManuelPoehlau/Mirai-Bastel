# Archive

This directory preserves historical project material that remains useful for understanding how current decisions were reached.

Archived documents are **not** competing current specifications.

Use the canonical documents under `docs/architecture/`, `docs/design/`, `docs/future_ideas/` and the relevant experiment directories for the current state.

## Archive policy

- Preserve important independent reviews and first responses.
- Preserve completed plans when they explain significant engineering decisions.
- Preserve rejected alternatives when their reasoning may be useful later.
- Do not edit an archived independent review to match a later decision.
- When an archived document is referenced from current documentation, explain its historical role rather than treating it as current guidance.

Current archive areas:

- [Core V1](core_v1/README.md)
- [Viewport V1](viewport_v1/README.md)
- [Viewport V02](viewport_v02/README.md)
- [Symmetry Lab](symmetry_lab/README.md)
- [Deformation reviews](deformation/reviews/) — independent review of AD-025 (ARCH-02), CLAUDE-001 (2026-10-27)
- [Early work packages](early_work_packages/) — WP-01A, WP-02, WP-04 (Gates, reports, amendments), moved from the docs root 2026-10-21 (repository slimming)
- [Audits 2026-09](audits_2026-09/) — Ownership/Lifecycle, Repository-wide health, shared-infrastructure, genealogy, WP-03 and Core-reassessment audits, moved from the docs root 2026-10-21
- [Experiments 2026-10](experiments_2026-10/) — READMEs, findings and results of the Playground and the labs removed in the consolidation of 2026-10-24 (code: commit `61ebe77`, list in `experiments/README.md`), plus the Artist Playground design docs (`artist_playground_design/`)
- [Input Truth 2026-10](input_truth_2026-10/README.md) — the Artist Input Truth (`tools/Input_Mapping_Tool/`, `artist_input_truth.json`) and `docs/design/INPUT_WIRING_MAP.md`, archived 2026-10-28 (AD-013 addendum 2026-10-28: the BindingSet with `config/keymap.json` is the input truth)
- [Handoffs 2026-10](handoffs_2026-10/) — finished Claude Code handoffs and plans moved out of `docs/architecture/` on 2026-10-24 (Symmetry slices, WP-SYM-LAB-01/03, WP-06 Stage B kickoff, AD-021 M2, Core V1 review requests and hardening plan); the two 2026-09-19 health checks went to `audits_2026-09/`

**Moved 2026-10-21:** the `docs/WP-04_*`, `docs/Cline - Work Package *`, `docs/Mirai-Bastel — Work Package *` and audit files of the
docs root now live in the two folders above (same file names). Independent reviews under `*/reviews/` were left untouched, so
paths they cite may point at the old docs-root location; look the file name up in the two folders. A duplicate copy of the
Core Architecture Reassessment (`Mirai-Bastel — Core Architecture Reassessment.md`, identical content) was removed; the kept copy is
`audits_2026-09/CORE_ARCHITECTURE_REASSESSMENT.md`. Playground-specific input documents moved to `docs/design/artist_playground/`
(`INPUT_WIRING_MAP.md`, `WP-AP_INPUT_WIRING_REPORT.md`); `sym_praxistests.md` is now `symmetry_lab/sym_praxistests.md`.
