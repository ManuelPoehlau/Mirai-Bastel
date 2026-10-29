# Second opinion — AD-027 "Interaction layer: one session slot, one `can_run`, feature controllers" (PROPOSED)

> **Reviewer:** the Development chat (Mirai-Bastel development project), 2026-10-29
> **Review ID:** DEVCHAT-001
> **Subject:** `docs/architecture/AD-027-INTERACTION-LAYER-SESSION-SLOT.md` as PROPOSED on branch
> `claude/affectionate-maxwell-8f93sq` @ `841415a` (baseline `main` @ `dfd6e5d`)
> **Status:** Archived first-pass review (AGENTS.md §6), preserved verbatim as Manu passed it to Claude Code;
> the answers and the disposition belong in AD-027 ("Review disposition").
>
> This document is intentionally preserved as the original review. Do not edit it to reflect later decisions.

---

Verdict: ACCEPT WITH CHANGES.

Open points 1-6: agree with the chosen option in each.
 1 hold keys inside the slot: precedence must live in one place.
 2 dispatch_command gated: an ungated public entry is the bug class V8 shows; GUI and future scripts must hit
   the same gate.
 3 controllers/ package: keeps interaction code separate from the model modules (morph_targets.py etc.) and
   makes E5(ii) checkable.
 4 keep V1/V3/V7 (Artist, below).
 5 keep CommandGate as stage 2; retiring it is a separate decision.
 6 HUD data only; greying is the UX project's call.

Changes:
C1 Corpus lifecycle. E1's randomised digest corpus is a migration oracle, not a permanent test: it encodes every
   binding and would break on any intended keymap or behaviour change (UX project, Phase 6). After M8, keep the
   scripted sequences (V1-V7, the listed test-point scenarios) as readable regression tests and remove the
   randomised digest fixtures. State this in §6 and the DoD.
C2 UI in front of the slot. A grabbing session (Knife takes every LMB) would swallow clicks on future GUI panels.
   Do not decide pointer ownership between panels and viewport (Mirai UX project; GUI_STAGE1_HUD Q4). State in
   §3.5 that a window-level UI hit-test may sit in front of InteractionSlot.route, and make sure the slot API does
   not preclude it.
C3 Execution. Implement in fresh sessions with AD-027 as the handoff (suggested split M0-M2, M3-M5, M6-M8;
   Opus 5.5 high). Within M6, run E1/E2 after each gesture kind, not only at the end of the step.

---

*Delivered in the same message, after the review (Manu's decision, recorded in AD-027 §0):*

Artist (Manu, 2026-10-29): Go for AD-027 with C1-C3. V1, V3, V7 stay as they are.
