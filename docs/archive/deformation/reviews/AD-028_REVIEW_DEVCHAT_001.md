# Second opinion — AD-028 "Skeleton and skinning: a scene rig, the weights point layer, CPU linear blend skinning" (PROPOSED)

> **Reviewer:** the Development chat (Mirai-Bastel development project), 2026-11-02
> **Review ID:** DEVCHAT-001
> **Subject:** `docs/architecture/AD-028-SKELETON-AND-SKINNING.md` as PROPOSED on `main` @ `4e46aec` (draft commit
> `e355480`, PR #56; baseline `main` @ `0af65eb`)
> **Status:** Archived first-pass review (AGENTS.md §6), preserved verbatim as Manu passed it to Claude Code;
> the answers and the disposition belong in AD-028 ("Review disposition").
>
> This document is intentionally preserved as the original review. Do not edit it to reflect later decisions.

---

Verdict: ACCEPT WITH CHANGES.

P-1 to P-8: agree with the proposed option in each.
 P-1 the H5c rule is Manu's (inherited); the GPU drawing path is its own AD after the reference-PC run.
 P-2 the implicit object share matches unweighted points staying at rest; a root bone stays possible later.
 P-3 agree. Note in §3.4: raise-proportional / lower-to-parent is path dependent across gestures (raise then
     lower back does not restore the old split); acceptable, deterministic within a gesture (press values). Add
     one test that pins the documented behaviour.
 P-4, P-5, P-6, P-8 as proposed for this phase. P-7: four kept by size; more influences = an additive kind later.

Changes:
C1 Remove the verdict table from the practical test section (Development System §7, Manu 2026-10-29: report
   problems instead of ticking lists). Keep one run-through and the reference-PC measurement.
C2 Questions to Manu go in plain German without jargon and only for what is his (Intent, Product Truth,
   Priority, Promotion). Technical defaults are stated, not asked. Apply this to the implementation note and
   the ATELIER line.
C3 Delete the stale branch `claude/jolly-hawking-eqqvmz` (older draft AD-028-SKINNING-RIG-AND-POSE-MODE.md,
   2026-11-01, superseded by this AD).

---

*Delivered in the same message, after the review (Manu's decision, recorded in AD-028's status and §16):*

Artist (Manu, 2026-11-02): Go for AD-028 and the Core change with C1–C3; S1–S8 as recommended.
