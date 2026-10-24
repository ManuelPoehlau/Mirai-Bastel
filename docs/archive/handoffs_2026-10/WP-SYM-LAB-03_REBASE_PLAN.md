# WP-SYM-LAB-03 — Rebase the Symmetry Lab onto the Production app (PLAN)

**Type:** B (research / plan) · **Mode (M5):** Discovery · **Date:** 2026-10-03
**Status:** PLAN **accepted** (Manu, 2026-10-03; reviewed by the planning agent in chat),
with the review amendments below. Q1 stays open until the session after Slice 4.
**Slice 1a (`src` hooks H1–H6) done 2026-10-03** (§5); **Slice 1b (the Lab on the app path, `run_app.py`) done 2026-10-03** (§5); **Slice 2 (partner markers, HUD line, drag-cost probe) done 2026-10-03** (§5; A3 **passed on the reference PC**, hover-change cost fixed afterwards, see A3); Slices 3 and 4 done 2026-10-03 (§5); **Slice 5 (swap and delete) done 2026-10-03** (§5). **WP-SYM-LAB-03 done (2026-10-03).** Since Slice 5 the Lab starts with `python experiments/symmetry_lab/run.py [asset]`; `run_app.py` in the rows below is that file under its old name.
**H2 status (2026-10-03):** AD-013 H2 addendum **DECIDED** — data-only command gate (review
proposal G), two independent reviews (CLAUDE-001, CLAUDE-002) archived unedited and answered.
The A1 gate is passed; Slice 1 code may start.
**Base:** `main` @ `f15957c` (WP-SYM-LAB-02 S2).
**Trigger:** Artist (Manu, 2026-10-03): Symmetry need not reach Production fast, but it must
use the Production tools. A Lab with its own renderer makes no sense long-term.
**Code changes in this package (the plan itself):** none; the slices below carry the code.

Related: [Lab README](../../experiments/symmetry_lab/README.md) (current state, verdicts,
colour legend) · handoffs [Slice 2](WP-SYM-LAB-01_SLICE2_CLAUDE_CODE_HANDOFF.md) …
[Slice 7](WP-SYM-LAB-01_SLICE7_CLAUDE_CODE_HANDOFF.md) ·
[AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md) ·
[AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md) ·
[AD-013](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md) ·
[ROADMAP §7, entry 2026-10-02](ROADMAP.md) (Symmetry promotion check) ·
[Symmetry Evolution Research](../research/symmetry/SYMMETRY_EVOLUTION_RESEARCH.md) §12.

---

## 0. Summary

- **The target works.** The Lab can become a thin `experiments/` entry point that builds the
  same `Application` → `Viewport` V02 → `GLRenderStore` path as `src/main.py` and adds only
  symmetry. That needs **four small hooks, one bug guard and one pure refactor in `src/`**
  (§3). It needs **no `src/core` change**, and `src/main.py` behaves exactly as before
  (every hook defaults to "off").
- **Exactly one hook is an architecture boundary:** H2, letting an experiment refuse app
  commands and add its own keys. After review CLAUDE-001 it is a data-only command gate inside
  `Application` plus the Lab's own keys resolved at window level, not a callback (revised AD-013
  addendum). It touches AD-013 I3/I4 (input authority). Per AGENTS.md §5 it needs an AD-013
  addendum before code. That is a technical decision, not an Artist question.
- **Most of the Lab is already in the app or is a stale copy.** Of 34 inventoried Lab
  features: **12 are already in the app (a)**, **13 are symmetry-only and get re-hosted (b)**,
  and **9 are obsolete copies to delete (c)** (§2). Symmetric W/E/R already run in
  `src` (`MoveTool`/`TransformTool` read `mesh.symmetry_definition`), so they work in the
  rebased Lab for free, with the app's constraints.
- **Three findings this plan surfaced** (not in the trigger list):
  1. `Application._transform_step` does not catch `SeamConstraintError`, so E/R on a seam
     vertex would raise out of the event handler once symmetry is on (the Lab catches it
     itself today).
  2. A Lab history entry pushed past `Application` desynchronises the Undo/Redo selection
     mirror.
  3. The app's contextual C and Knife run one-sided under symmetry. This makes the pending
     E5 test real again.
- **Tests:** of 263 Lab tests, about 133 are kept or ported to the `Application` path and
  about 130 are deleted with the copies they test (§4.4).
- **Visible changes that need a new Artist verdict: two** (§4.3). One is a question (Q1,
  shading of `subd_cube`). The other is a single combined re-check session after Slice 4.

---

## Review amendments (2026-10-03)

Accepted together with the plan. They tighten gates; the slices themselves are unchanged.

**A1 — H2 is reviewed independently before any `src` code (Slice 1, step 0).**
The H2 decision is recorded as an
[AD-013 addendum](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-03-wp-sym-lab-03-h2--experiment-input-hook-in-application)
(status PROPOSED), committed before any Slice 1 code. A fresh agent reviews it in a separate
session without access to the plan author's reasoning:

- **Input:** the addendum and the documents and code it cites (AD-013 itself,
  `INPUT_COMMAND_TOOL_CONTRACT.md`, AD-015, AD-016, `src/mirai/application.py`). The
  addendum has to stand on its own; this plan and the chat are not part of the prompt.
- **Questions:** Do the rules hold AD-013 I1/I3/I4/I6? Is there a smaller mechanism? Is a
  call site missing or superfluous? Is each rule testable? Is there any risk to
  `src/main.py`?
- **Output:** archived unedited (AGENTS.md §6) as
  `docs/archive/symmetry_lab/reviews/AD-013_H2_ADDENDUM_REVIEW_CLAUDE_001.md`, the existing
  `docs/archive/<area>/reviews/<SUBJECT>_REVIEW_CLAUDE_<NNN>.md` naming. The new
  `symmetry_lab` archive area gets its README and an entry in `docs/archive/README.md` in
  the same commit.
- **Gate:** Slice 1 code starts only after the review is archived and each finding has an
  answer in the addendum (fixed, or why not). The review itself is never edited.
- **Status (2026-10-03):** review
  [CLAUDE-001](../archive/symmetry_lab/reviews/AD-013_H2_ADDENDUM_REVIEW_CLAUDE_001.md)
  archived (ACCEPT WITH CHANGES, blockers F1/F2). All 15 findings are answered in the
  addendum's Review section. Decision revised: the callback hook F is replaced by the reviewer's
  data-only gate G plus a public external-commit entry (H3), `interaction_owner`, the public
  status setter (H4), a preview allow-list, the exact Lab context (Shift+S, M, Shift+B, asserted
  free in GLOBAL and KNIFE) and a start-up listing of refusals. The revision deviates from G as
  proposed (D1: Esc closes the preview at window level), so a **second independent review is
  required**: same input rules as above, scope D1–D3 and the revised H2-R1..R6, archived as
  `docs/archive/symmetry_lab/reviews/AD-013_H2_ADDENDUM_REVIEW_CLAUDE_002.md`. **Slice 1 code
  starts only after that review is archived and answered** and the addendum is DECIDED.
- **Status (2026-10-03, later):** review
  [CLAUDE-002](../archive/symmetry_lab/reviews/AD-013_H2_ADDENDUM_REVIEW_CLAUDE_002.md)
  archived (ACCEPT WITH CHANGES, no blockers; D1 confirmed by probes). N1–N8 answered in the
  addendum with the reviewer's own changes: H3 becomes `apply_mesh_change(description, mutate)`
  (N1), Lab commands are refused during the preview and the preview row dominates (N2), a D1
  negative-path test (N3), the pyglet-free `lab_key_press` contract (N4), test fixes (N5–N7) and
  a listing line for Esc (N8). The addendum is **DECIDED**; **A1 is passed.**

**A2 — Slice 5 gate: no Lab test is deleted without a named replacement.**
Before Slice 5 deletes anything, this plan gets a table with one row per deleted test: the
deleted test, the named `tests/` (or kept Lab) test that covers the same rule, and the reason
if no replacement exists. A row may not say "the app covers it" without naming the test. A
deleted test without a named replacement is ported instead.

The 11 hover tests (`test_lab_hover.py`) need special care. The move target rule A4/E7/E8
and the hover partner are Lab-specific: the Slice 4 KEEP was given on the Lab. Draft mapping,
to be re-verified against the code when Slice 5 starts:

| Lab test | Rule | Named replacement (draft) | Draft verdict |
|---|---|---|---|
| `test_selection_wins_over_hover` | A4 | `tests/test_application_move.py::test_arming_from_selection_keeps_unrelated_hover` | covered |
| `test_hover_target_moves_when_selection_empty` | A4 + E8 (selection stays empty after the commit) | `test_application_move.py::test_arm_without_selection_uses_hovered_vertex` covers the target only; no named test asserts E8 after a commit | **port** |
| `test_w_rejected_when_selection_and_hover_both_empty` | A4 | `test_application_move.py::test_arm_with_nothing_is_rejected` | covered |
| `test_target_fixed_at_w_press_cursor_over_other_vertex_does_not_retarget` | E7 | `test_application_move.py::test_target_is_fixed_at_press` (selection changed) + `::test_no_hover_recompute_while_armed_or_moving` | covered only in combination → **port** (one test for the Lab's exact case) |
| `test_esc_during_drag_with_hover_target_restores_exactly` | E8 + exact cancel | `test_application_move.py::test_esc_mid_move_restores_exactly_without_history` uses a selection target, not a hover target | **port** |
| `test_hover_does_not_update_during_camera_drag` | E9 freeze | none: the app *clears* the hover during orbit (`test_application_hover.py::test_starting_orbit_or_pan_clears_hover`), a recorded visible change (§4.3) | delete, reason: superseded by an app decision |
| `test_hover_does_not_update_during_move_and_is_repicked_after_commit` | E9 | `test_application_move.py::test_no_hover_recompute_while_armed_or_moving` + `::test_hover_is_repicked_after_commit` | covered |
| `test_arming_from_selection_hides_hover_on_the_target` | clear-on-arm | `test_application_move.py::test_arming_from_selection_clears_overlapping_hover` | covered |
| `test_hover_is_repicked_after_cancel_and_tap` | E9 | `test_application_move.py::test_hover_is_repicked_after_cancel`; tap: none named | **port** (tap part) |
| `test_hover_marks_change_only_when_vertex_id_changes` | E9 | `test_application_hover.py::test_no_notification_when_hovered_id_unchanged` | covered |
| `test_status_shows_move_target_label` | Lab status (`Hover v<id>`) | **ported in Slice 2:** `experiments/symmetry_lab/tests/test_app_lab_hud.py::test_hover_target_when_the_selection_is_empty` (the HUD keeps the label) | covered |

The hover partner (turquoise) had no test; Slice 2 added them
(`experiments/symmetry_lab/tests/test_app_lab_partners.py`). Every
deleted Lab test needs the same row treatment, not only the hover tests.

### A2 table — Slice 5, step 0 (2026-10-03)

Written before any deletion and checked against the code at `fe1b213`. One row per deleted
test function; a parametrised function lists its cases and counts as that many tests. Paths:
`lab/` = `experiments/symmetry_lab/tests/`, `tests/` = the Production suite. **Ported (S5)**
means a test written in Slice 5 under exactly that name; **reason** is used only where the
rule itself is gone (deleted module or an app decision), never "the app covers it". Names
refer to the state after Slice 5. Two renames in Slice 5: `lab/test_run_app.py` →
`lab/test_run.py` (same test names), and in `lab/test_app_lab_cycle.py`
`test_run_app_rejects_unknown_name_before_opening_a_window` /
`test_run_app_help_runs_without_a_window` → `test_run_rejects_unknown_name_before_opening_a_window`
/ `test_run_help_runs_without_a_window`.

**Re-verification of the draft hover mapping (above).** The six "covered" rows hold as
drafted. The four **port** rows are still ports: since Slice 1b only
`lab/test_app_lab_hud.py::test_hover_target_when_the_selection_is_empty` touches one of them
(hover target + empty selection after the commit, E8). It does not check that the partner
moves mirrored or that exactly one history entry is written. `lab/test_app_lab_partners.py::test_esc_during_drag_restores_markers_without_a_report_run`
cancels a *selection* target, not a hover target. So all four go into a new
`lab/test_app_lab_hover.py`. The camera-drag row stays a reason (the app clears the hover
during orbit, §4.3).

**Kept, not in this table** (module stays, test unchanged or only re-pointed at the moved
function): `test_lab_topology.py` 19; `test_lab_resymmetrize.py` 8 (the 7 pure tests plus
`test_preview_draw_data`, made pure: it builds the plan with `plan_resymmetrize` instead of
opening the preview through the dispatcher, and reads `resym_preview_data` from its new home
`lab_resymmetrize`); `test_lab_knife.py` 12 (baseline + P1–P3, helpers inlined);
`test_lab_symmetry.py` 12 (seam derivation, definition, states, the 54 unpaired, report,
foreign definition); `test_lab_scene.py` 2 (`resolve_asset_name`, `load_asset_into` on an
unknown name); `test_import_boundary.py` 1 (module list updated); and
`test_draw_data.py::test_subd_cube_topology_is_as_registered` (moves with its file, see below).
The plan's §4.4 counted 17 pure resymmetrize tests; Slice 3 had already found that 19 of the 26
functions drive the dispatcher (§5 row 3), so 7 pure ones are left.

`test_lab_resymmetrize.py` — dispatcher tests (22), ported in Slice 3:

| Deleted test | Rule | Named replacement / reason |
|---|---|---|
| `test_man_with_shoes_from_either_side_becomes_valid[0,1]` (2) | E13, one undo step | `lab/test_app_lab_resymmetrize.py::test_man_with_shoes_from_either_side_becomes_valid[0,1]` |
| `test_seam_vertex_moved_off_plane_ends_exactly_on_plane` | E13 seam | `lab/test_app_lab_resymmetrize.py::test_seam_vertex_moved_off_plane_ends_exactly_on_plane` |
| `test_rejected_when_symmetry_off` | E15 | `lab/test_app_lab_resymmetrize.py::test_rejected_when_symmetry_off` |
| `test_rejected_without_selection` | E15 | `lab/test_app_lab_resymmetrize.py::test_rejected_without_selection` |
| `test_rejected_for_seam_vertex` | E15 | `lab/test_app_lab_resymmetrize.py::test_rejected_for_seam_vertex` |
| `test_rejected_when_seam_does_not_split_into_two` | E15 | `lab/test_app_lab_resymmetrize.py::test_rejected_when_seam_does_not_split_into_two` |
| `test_rejected_while_move_armed` | E15 | `lab/test_app_lab_resymmetrize.py::test_rejected_while_move_armed_or_dragging[armed]` |
| `test_rejected_while_move_dragging` | E15 | `lab/test_app_lab_resymmetrize.py::test_rejected_while_move_armed_or_dragging[running]` |
| `test_m_esc_leaves_mesh_unchanged_and_no_history` | A7 Esc | `lab/test_app_lab_resymmetrize.py::test_m_esc_leaves_mesh_unchanged_and_no_history` |
| `test_m_m_executes_with_one_history_entry` | A7 execute | `lab/test_app_lab_resymmetrize.py::test_m_m_executes_with_one_history_entry` |
| `test_other_keys_are_ignored_during_preview[Shift+S,W,Ctrl+Z,Ctrl+Y]` (4) | A7 modal | `lab/test_app_lab_resymmetrize.py::test_other_keys_are_ignored_during_preview` (same 4 keys) |
| `test_select_is_ignored_during_preview` | A7 modal | `lab/test_app_lab_resymmetrize.py::test_select_is_ignored_during_preview` |
| `test_click_pressed_before_m_does_not_select_during_preview` | A7 modal | `lab/test_app_lab_resymmetrize.py::test_click_pressed_before_m_does_not_select_during_preview` |
| `test_navigation_allowed_during_preview` | A7 | `lab/test_app_lab_resymmetrize.py::test_navigation_allowed_during_preview` |
| `test_hover_paused_during_preview` | A7 hover | `lab/test_app_lab_preview.py::test_t_h_hover_paused_while_open_and_repicked_after` |
| `test_zero_changes_preview_then_m_creates_no_history_entry` | A5/E15 | `lab/test_app_lab_resymmetrize.py::test_zero_changes_preview_then_m_creates_no_history_entry` |
| `test_status_line_shows_direction_counts_and_keys` | E15 text | `lab/test_app_lab_resymmetrize.py::test_status_line_shows_direction_counts_and_keys` |
| `test_paired_state_unaffected_by_preview` | display stays positional | `lab/test_app_lab_resymmetrize.py::test_paired_state_unaffected_by_preview` |

`test_lab_symmetry.py` — 8 deleted (12 kept):

| Deleted test | Rule | Named replacement / reason |
|---|---|---|
| `test_seam_is_stored_declaration_not_live_check` | E3 | `lab/test_app_lab_cycle.py::test_seam_is_stored_declaration_not_live_check` |
| `test_cycle_off_x_y_z_off_one_history_entry_each` | A2/E2 | `lab/test_app_lab_cycle.py::test_cycle_off_x_y_z_off_one_history_entry_each` |
| `test_cycle_does_not_touch_positions_or_topology` | E2 | `lab/test_app_lab_cycle.py::test_cycle_does_not_touch_positions_or_topology` |
| `test_cycle_keeps_selection` | E2 | `lab/test_app_lab_cycle.py::test_cycle_keeps_selection` |
| `test_plane_outline_off_is_empty` | plane outline | `lab/test_app_lab_cycle.py::test_overlays_empty_while_symmetry_off` |
| `test_plane_outline_lies_in_plane_and_encloses_bounds[X,Y,Z]` (3) | plane outline | `lab/test_app_lab_cycle.py::test_plane_outline_lies_in_plane_and_encloses_bounds[X,Y,Z]` |

`test_lab_scene.py` — 5 deleted (2 kept):

| Deleted test | Rule | Named replacement / reason |
|---|---|---|
| `test_registry_matches_expected_assets` | registry, default asset | `lab/test_app_lab_cycle.py::test_registry_matches_expected_assets` |
| `test_load_by_registry_name[head_basemesh,man_with_shoes_basemesh,subd_cube]` (3) | load + frame + empty vertex selection | `lab/test_app_lab_cycle.py::test_load_by_registry_name_on_the_app_path` (same 3) |
| `test_run_rejects_unknown_name_before_opening_a_window` | exit code 2 before the window | `lab/test_app_lab_cycle.py::test_run_rejects_unknown_name_before_opening_a_window` |

`test_lab_symmetric_transform.py` — 12, ported in Slice 2:

| Deleted test | Rule | Named replacement / reason |
|---|---|---|
| `test_single_vertex_runs_symmetric_one_undo_step[Rotate,Scale]` (2) | S2 | `lab/test_app_lab_transform.py::test_single_vertex_runs_symmetric_one_undo_step` (same 2) |
| `test_cancel_leaves_no_history[E,R]` (2) | S2 cancel | `lab/test_app_lab_transform.py::test_cancel_leaves_no_history` (same 2) |
| `test_constraint_keys_toggle_and_show_in_status` | B4.1 toggle | `lab/test_app_lab_transform.py::test_constraint_keys_toggle_and_show_in_hud` |
| `test_constraints_x_y_z_all_keep_the_pair_mirrored` | S2 | `lab/test_app_lab_transform.py::test_constraints_x_y_z_all_keep_the_pair_mirrored` |
| `test_seam_vertex_rotate_x_allowed` | INV-8 seam | `lab/test_app_lab_transform.py::test_seam_vertex_rotate_x_allowed` |
| `test_seam_vertex_rotate_other_axes_refused_with_message[Y,Z,free]` (3) | INV-8 + H5 | `lab/test_app_lab_transform.py::test_seam_vertex_rotate_other_axes_refused_with_message` (same 3) |
| `test_seam_vertex_scale_allowed_and_on_plane` | INV-8 | `lab/test_app_lab_transform.py::test_seam_vertex_scale_allowed_and_on_plane` |
| `test_move_and_gate_unchanged` | W + constraint (D1) | `lab/test_app_lab_transform.py::test_move_honours_the_constraint_and_stays_mirrored`, `tests/test_application_symmetry.py::test_symmetric_move_with_axis_constraint` |

`test_lab_gate.py` — 13, ported in Slice 4:

| Deleted test | Rule | Named replacement / reason |
|---|---|---|
| `test_symmetry_off_commit_cancel_and_tap[E,R]` (2) | E5 off | `lab/test_app_lab_gate.py::test_symmetry_off_commit_cancel_and_tap` (same 2) |
| `test_symmetry_off_no_target_rejected` | A4 | `lab/test_app_lab_gate.py::test_symmetry_off_no_target_rejected` |
| `test_mark_runs_one_sided_with_message_and_one_undo_step[E,R]` (2) | E5 MARK | `lab/test_app_lab_gate.py::test_mark_runs_with_the_one_sided_warning_and_one_undo_step` (same 2) |
| `test_mark_hides_partner_marker_only_while_armed` | E5 MARK marker | `lab/test_app_lab_gate.py::test_mark_warning_only_while_armed` (Slice 4 deviation 2: the warning line carries the mark) |
| `test_block_refuses_to_arm_and_leaves_no_history[E,R]` (2) | E5 BLOCK | `lab/test_app_lab_gate.py::test_block_refuses_to_arm_and_leaves_no_history` (same 2) |
| `test_block_does_not_apply_with_symmetry_off` | E5 | `lab/test_app_lab_gate.py::test_block_does_not_apply_with_symmetry_off` |
| `test_move_unchanged_in_both_modes[MARK,BLOCK]` (2) | E5 | `lab/test_app_lab_gate.py::test_move_unchanged_in_both_modes` (same 2) |
| `test_mode_switch_is_lab_state_only` | Shift+B | `lab/test_app_lab_gate.py::test_mode_switch_is_lab_state_only` |
| `test_gate_reads_class_attribute` | AD-SYM-02 §2.3 | `lab/test_app_lab_gate.py::test_gate_reads_class_attribute` |

`test_lab_move.py` — 26:

| Deleted test | Rule | Named replacement / reason |
|---|---|---|
| `test_symmetric_move_one_history_entry_and_exact_undo` | S3 KEEP | `lab/test_app_lab_transform.py::test_symmetric_move_one_history_entry_and_exact_undo` |
| `test_move_without_symmetry_moves_only_the_selection` | S3 | `lab/test_app_lab_transform.py::test_move_without_symmetry_moves_only_the_selection` |
| `test_seam_vertex_stays_exactly_on_plane` | S3 seam slide | `lab/test_app_lab_transform.py::test_seam_vertex_stays_exactly_on_plane` |
| `test_undo_takes_back_exactly_one_action_each` | E2 | `lab/test_app_lab_transform.py::test_undo_takes_back_exactly_one_action_each` |
| `test_undo_clears_selection_and_disarms` | Lab Undo rule (D8) | reason: superseded by the app decision B6 follow-up (Undo restores the selection, §4.3). App rules: `tests/test_application_move.py::test_undo_while_armed_disarms_first`, `tests/test_application_contextual_c.py::test_undo_restores_the_selection_as_of_the_undone_command` |
| `test_after_commit_move_is_disarmed` | one-shot (E5 of Slice 3) | `tests/test_application_move.py::test_motion_and_release_commits_one_history_entry` (`_assert_idle` after the release) |
| `test_tap_without_motion_is_a_noop` | B3 tap | `tests/test_application_move.py::test_tap_without_motion_is_a_noop` |
| `test_single_pixel_motion_starts_the_move` | B3 | `tests/test_application_move.py::test_single_pixel_motion_starts_the_move` + `::test_zero_delta_motion_does_not_start_the_move` |
| `test_lmb_while_armed_neither_moves_nor_selects` | Lab click rule | reason: app decision — a click while W is armed selects (`_execute_click` has no transform guard), the target stays fixed: `tests/test_application_move.py::test_target_is_fixed_at_press` |
| `test_release_with_changed_modifiers_still_commits` | B3 | `tests/test_application_move.py::test_release_with_changed_modifiers_still_commits` |
| `test_release_of_other_key_does_not_commit` | B3 | `tests/test_application_move.py::test_release_of_another_key_does_not_commit` |
| `test_second_w_press_while_armed_keeps_target_and_tool` | E7 | `tests/test_application_move.py::test_press_while_armed_is_ignored` + `::test_target_is_fixed_at_press` |
| `test_q_is_unbound_in_the_lab` | Q unbound | `tests/test_application_keys.py::test_q_is_unbound` |
| `test_w_without_selection_does_not_arm` | A4 (nothing to move) | `tests/test_application_move.py::test_arm_with_nothing_is_rejected` |
| `test_navigation_still_works_while_armed` | navigation while armed | `tests/test_application_move.py::test_camera_gesture_wins_while_armed` (Orbit; Shift+LMB Pan is gone, B2 → `tests/test_application_pointer.py::test_alt_shift_lmb_drag_pans`) |
| `test_camera_gesture_during_move_wins` | navigation during the move | `tests/test_application_move.py::test_camera_gesture_wins_while_armed` (MMB Pan gone, B2) |
| `test_esc_during_drag_restores_exactly_without_history` | S3 exact Esc | `lab/test_app_lab_transform.py::test_esc_during_drag_restores_exactly_without_history` |
| `test_esc_while_only_armed_disarms` | Esc armed | `tests/test_application_move.py::test_esc_while_armed_only_disarms` |
| `test_esc_when_idle_is_not_handled` | Lab: Esc closes the window | reason: app decision B1 A3 (Esc never closes): `tests/test_application_keys.py::test_esc_idle_does_nothing`, `tests/test_main_wiring.py::test_escape_is_handled_and_only_cancels` |
| `test_unrelated_keys_are_not_handled` | Lab filtered foreign commands | reason: the Lab no longer filters app commands (H2: everything else goes to `Application`); `f` unbound: `tests/test_input_binding.py::DefaultBindingsTests::test_legacy_mode_keys_v_and_f_are_unbound`, `tests/test_application_component_modes.py::test_legacy_mode_keys_do_nothing` |
| `test_keys_during_drag_are_ignored[Shift+S,Ctrl+Z,Ctrl+Y,W]` (4) | modal move | Shift+S: `lab/test_app_lab_keys.py::test_refusals_are_visible_and_counted[ShiftS_transform_running]`; Ctrl+Z/Ctrl+Y: `tests/test_application_move.py::test_undo_redo_ignored_during_move`; W: `tests/test_application_move.py::test_press_while_armed_is_ignored` |
| `test_move_drag_marks_mesh_changed` | `Change.MESH` | reason: the `Change` flags go with the dispatcher (inventory #32); live redraw: `tests/test_application_move.py::test_live_update_moves_the_point_overlay`, `lab/test_app_lab_partners.py::test_drag_defers_the_report_and_moves_the_markers` |
| `test_status_text_shows_plane_state_unpaired_move_and_selection` | status line | `lab/test_app_lab_transform.py::test_hud_shows_plane_state_unpaired_and_move` |

`test_lab_hover.py` — 11 (draft above, re-verified):

| Deleted test | Rule | Named replacement / reason |
|---|---|---|
| `test_selection_wins_over_hover` | A4 | `tests/test_application_move.py::test_arming_from_selection_keeps_unrelated_hover`; the mirrored selection target: `lab/test_app_lab_transform.py::test_symmetric_move_one_history_entry_and_exact_undo` |
| `test_hover_target_moves_when_selection_empty` | A4 + E8 after the commit | **ported (S5):** `lab/test_app_lab_hover.py::test_hover_target_moves_mirrored_and_leaves_the_selection_empty` |
| `test_w_rejected_when_selection_and_hover_both_empty` | A4 | `tests/test_application_move.py::test_arm_with_nothing_is_rejected` |
| `test_target_fixed_at_w_press_cursor_over_other_vertex_does_not_retarget` | E7 | **ported (S5):** `lab/test_app_lab_hover.py::test_target_fixed_at_w_press_cursor_over_other_vertex_does_not_retarget` |
| `test_esc_during_drag_with_hover_target_restores_exactly` | E8 + exact cancel | **ported (S5):** `lab/test_app_lab_hover.py::test_esc_during_drag_with_hover_target_restores_exactly` |
| `test_hover_does_not_update_during_camera_drag` | E9 freeze | reason: superseded by the app decision B2b (the hover is cleared during orbit, §4.3): `tests/test_application_hover.py::test_starting_orbit_or_pan_clears_hover` |
| `test_hover_does_not_update_during_move_and_is_repicked_after_commit` | E9 | `tests/test_application_move.py::test_no_hover_recompute_while_armed_or_moving` + `::test_hover_is_repicked_after_commit` |
| `test_arming_from_selection_hides_hover_on_the_target` | clear-on-arm | `tests/test_application_move.py::test_arming_from_selection_clears_overlapping_hover` |
| `test_hover_is_repicked_after_cancel_and_tap` | E9 | cancel: `tests/test_application_move.py::test_hover_is_repicked_after_cancel`; tap: **ported (S5):** `lab/test_app_lab_hover.py::test_hover_is_repicked_after_a_tap` |
| `test_hover_marks_change_only_when_vertex_id_changes` | E9 | `tests/test_application_hover.py::test_no_notification_when_hovered_id_unchanged` |
| `test_status_shows_move_target_label` | `Hover v<id>` | `lab/test_app_lab_hud.py::test_hover_target_when_the_selection_is_empty` |

`test_lab_dispatch.py` — 11:

| Deleted test | Rule | Named replacement / reason |
|---|---|---|
| `test_alt_lmb_drag_orbits_until_release` | Orbit | `tests/test_application_pointer.py::test_alt_lmb_drag_orbits` |
| `test_pan_gestures_move_target[Shift+LMB,MMB]` (2) | Lab Pan overrides | reason: overrides dropped, app decision B2 (Pan = Alt+Shift+LMB, MMB unbound; H2-R1: no pointer entries): `tests/test_application_pointer.py::test_alt_shift_lmb_drag_pans`, `::test_other_drags_change_no_camera[MIDDLE]` |
| `test_gesture_holds_command_until_same_button_releases` | gesture fixed at press | `tests/test_pointer_gestures.py::test_foreign_button_press_ignored_while_gesture_runs` + `::test_foreign_button_release_ignored` |
| `test_wheel_zooms` | Zoom | `tests/test_application_pointer.py::test_wheel_dollies` |
| `test_rmb_is_unbound_in_lab` | RMB unbound | `tests/test_application_pointer.py::test_other_drags_change_no_camera[RIGHT]` |
| `test_foreign_commands_are_noops` | Lab filtered foreign commands | reason: the Lab no longer filters app commands (H2); what the gate still refuses: `lab/test_app_lab_keys.py::test_refusals_are_visible_and_counted` |
| `test_click_on_vertex_replaces_selection` | Select | `tests/test_application_pointer.py::test_click_replaces` |
| `test_click_into_empty_space_clears_selection` | Select | `tests/test_application_pointer.py::test_click_on_empty_space_clears` |
| `test_select_runs_on_release_below_threshold` | click threshold | `tests/test_application_pointer.py::test_small_movement_is_still_a_click`, `tests/test_pointer_gestures.py::test_click_only_fires_on_release_below_threshold` |
| `test_lmb_drag_over_threshold_does_not_select` | click threshold | `tests/test_application_pointer.py::test_lmb_drag_selects_nothing` |

`test_lab_bindings.py` — 20:

| Deleted test | Rule | Named replacement / reason |
|---|---|---|
| `test_lab_context_resolution[…]` (15) | Lab context | Shift+S, M and the GLOBAL fall-through of LMB, wheel ×2, W, Esc, Ctrl+Z, Ctrl+Y (9): `lab/test_app_lab_bindings.py::test_lab_context_has_exactly_three_key_entries_and_global_knife_unchanged`. Alt+LMB, Shift+LMB, MMB, RMB, C → Knife, Q (6): reason: Lab overrides dropped (H2-R1, §4.3); the same test asserts these now resolve as in GLOBAL |
| `test_global_context_unchanged` | GLOBAL untouched | `lab/test_app_lab_bindings.py::test_lab_context_has_exactly_three_key_entries_and_global_knife_unchanged` |
| `test_context_defined_in_lab_not_in_mirai_interaction` | Lab-local context | **ported (S5):** `lab/test_app_lab_bindings.py::test_context_defined_in_lab_not_in_mirai_interaction` |
| `test_lab_commands_defined_in_lab_not_in_commands` | Lab-local commands | **ported (S5):** `lab/test_app_lab_bindings.py::test_lab_commands_defined_in_lab_not_in_commands` (Knife replaced by SymmetryGateMode) |
| `test_c_is_connect_in_global_and_lab_knife_in_symmetry_lab_context` | C → Knife override (E23) | reason: override dropped, mirrored Knife not re-hosted; C falls through to GLOBAL `Connect`: `lab/test_app_lab_bindings.py::test_lab_context_has_exactly_three_key_entries_and_global_knife_unchanged` |
| `test_key_overrides_are_shift_s_m_c_and_shift_b` | key entries + listing | `lab/test_app_lab_bindings.py::test_lab_context_has_exactly_three_key_entries_and_global_knife_unchanged` + `::test_startup_listing_names_every_entry_and_every_gate_row` |

`test_input_path.py` — 16 (§4.4 counted 8 functions/cases; the file collects 16 with EGL):

| Deleted test | Rule | Named replacement / reason |
|---|---|---|
| `test_pyglet_press_resolves_to_lab_gesture[…]` (6) | pyglet button → command | translation: `tests/test_pyglet_input.py::TestMouseFromPyglet::test_known_buttons_with_modifier`, lock bits: `::TestKeyFromPyglet::test_foreign_modifiers_ignored`; resolution: `tests/test_input_binding.py::DefaultBindingsTests::test_mouse_bindings` + `::test_drag_bindings`. Shift+LMB/MMB Pan: reason as `test_pan_gestures_move_target` |
| `test_pyglet_scroll_zooms[1.0,-1.0]` (2) | wheel | `tests/test_pyglet_input.py::TestWheelFromPyglet::test_positive_is_up` + `::test_negative_is_down`, `tests/test_main_wiring.py::test_drag_orbits_and_scroll_zooms` |
| `test_pyglet_key_resolves_in_lab_context[…]` (7) | pyglet key → Lab context | Shift+S through real pyglet constants: `lab/test_run.py::test_one_key_event_through_lab_key_press`; W/Esc/Ctrl+Z/Ctrl+Y: `tests/test_pyglet_input.py::TestIntegrationWithDefaultBindings` (`test_w_is_move`, `test_escape_is_cancel`, `test_ctrl_z_is_undo`, `test_ctrl_y_is_redo`); Q: `tests/test_application_keys.py::test_q_is_unbound`; Caps Lock bit: `tests/test_pyglet_input.py::TestKeyFromPyglet::test_foreign_modifiers_ignored` |
| `test_pyglet_keys_drive_cycle_and_move` | pyglet → cycle, W, Esc | `lab/test_run.py::test_one_key_event_through_lab_key_press` (Shift+S, Esc, Ctrl+Z through the window handler); the final "idle Esc closes" assertion: reason as `test_esc_when_idle_is_not_handled` |

`test_draw_data.py` — 8 deleted, the file becomes `test_display_characterization.py`:

| Deleted test | Rule | Named replacement / reason |
|---|---|---|
| `test_face_data_lengths` | Lab VBO builder | reason: the Lab renderer and its VBO data are deleted (inventory #2/#3, class c); the drawn data is Production's: `tests/test_render_mesh.py::InitialBuildTests::test_positions_buffer_matches_mesh` |
| `test_edge_and_vertex_data_lengths` | Lab VBO builder | reason as above; edges: `tests/test_display_modes.py::test_cube_gives_twelve_segments_with_edge_endpoints` |
| `test_highlight_contains_exactly_the_selected_vertex` | selection points | `tests/test_point_overlay.py::test_selected_positions_are_exact_world_positions` |
| `test_highlight_empty_without_selection` | selection points | `tests/test_point_overlay.py::test_empty_selection_gives_no_points` |
| `test_quad_diagonal_characterization[subd_cube-24-24,head_basemesh-324-0]` (2) | E10 finding + Lab split | **ported (S5):** `lab/test_display_characterization.py::test_production_quad_diagonal_characterization` (same 2). It keeps the Q1 evidence (Production's quad split: 24/24 asymmetric on `subd_cube`, 0/324 on the head). The "shorter diagonal → 0" half goes with the E10 split (Q1 = (a)) |
| `test_vertex_normals_mirror_for_paired_vertices[subd_cube,head_basemesh]` (2) | E10 normals | **ported (S5):** `lab/test_display_characterization.py::test_production_vertex_normals_mirror_for_paired_vertices` (same 2), against `viewport.derived.DerivedGeometry` (Newell since `e64de4f`, D6) |

`test_lab_knife.py` — 24 deleted (12 kept). The mirrored Knife engine is not re-hosted
(inventory #29, D2, trigger). Its rules have no counterpart on the app path, and its findings
E16–E22 stay in the README history for a future symmetric One Knife. Reason for every row:
**rule deleted with `lab_knife.py`**.

| Deleted test | Rule |
|---|---|
| `test_mirrored_edge_to_edge_cut_is_valid_and_confirmed[subd_cube,head_basemesh]` (2) | E17/E18/E19 |
| `test_session_of_several_steps_commits_one_history_entry[subd_cube,head_basemesh]` (2) | AD-017 session |
| `test_in_session_undo_and_redo_cover_both_sides` | in-session undo |
| `test_cancel_restores_state_before_session_without_history` | cancel |
| `test_commit_without_change_creates_no_entry` | commit |
| `test_knife_does_not_touch_selection` | E22 |
| `test_cut_onto_seam_edge_tracks_seam[subd_cube,head_basemesh]` (2) | seam tracking (P1 fix) |
| `test_cut_across_the_middle_from_a_seam_vertex[1.0,-1.0]` (2) | seam start |
| `test_clicking_the_existing_mirror_point_after_reaching_the_seam_is_rejected` | Slice 6 observation |
| `test_seam_chord_is_rejected` | seam chord |
| `test_begin_is_rejected_unless_valid_with_two_sides[man_with_shoes_basemesh-X,subd_cube-Y]` (2) | A10/E20 gate |
| `test_one_minus_t_placement_fails_position_and_rolls_back` | A11 rollback |
| `test_unresolvable_partner_rejects_without_mutation` | INV-5 |
| `test_unmirrored_first_click_edge_splits` | unmirrored copy |
| `test_unmirrored_vertex_to_vertex_and_vertex_to_edge` | unmirrored copy |
| `test_unmirrored_rejections` | unmirrored copy |
| `test_unmirrored_undo_redo_cancel_commit` | unmirrored copy |
| `test_connect_in_shared_face_returns_used_face_and_boundary` | E16 copy |
| `test_lab_knife_is_lab_local` | Lab-local engine |

`test_lab_knife_window.py` — 40 deleted. The Slice 7 Knife window is not re-hosted
(§4.2: moot, never verdicted). The app's Knife is `mirai.topology.knife`, and since Slice 4
the Lab gates it (`lab/test_app_lab_gate.py`). Reason for every row: **rule deleted with
`lab_dispatch.py` / `lab_knife_pick.py` / `lab_knife_preview.py` / `lab_draw_data.knife_preview_data`**.

| Deleted test | Rule |
|---|---|
| `test_c_starts_mirrored_knife_on_valid_two_sides[subd_cube,head_basemesh]` (2) | A8 start |
| `test_c_with_symmetry_off_starts_unmirrored_session` | A10 off |
| `test_c_rejected_unless_valid_with_two_sides[man_with_shoes_basemesh-X,subd_cube-Y]` (2) | E20 |
| `test_c_rejected_while_move_armed_or_dragging` | start refusal |
| `test_c_rejected_while_resymmetrize_preview_open` | start refusal |
| `test_c_rejected_when_session_already_runs` | start refusal |
| `test_move_and_resym_are_rejected_during_session` | modal session |
| `test_hover_over_plus_x_edge_previews_exactly_what_the_click_creates[subd_cube,head_basemesh]` (2) | E26/E28 |
| `test_preview_matches_click_for_every_first_edge_target[subd_cube-1,head_basemesh-7]` (2) | E28 |
| `test_preview_matches_click_for_second_targets_around_the_start[subd_cube,head_basemesh]` (2) | E28 |
| `test_hover_over_seam_edge_has_no_mirror_point[subd_cube,head_basemesh]` (2) | seam self-pair |
| `test_seam_chord_is_blocked_before_the_click` | E28 |
| `test_slice6_observation_existing_mirror_point_previews_ok_but_click_rejects` | observation |
| `test_unresolvable_partner_is_blocked_with_reason` | E28 |
| `test_edge_at_start_is_invalid_target` | E28 |
| `test_face_and_outside_have_no_preview` | E27 |
| `test_unmirrored_preview_has_no_mirror_point` | unmirrored |
| `test_click_outside_without_cut_ends_session_without_history` | A8 commit |
| `test_vertex_edge_outside_commits_one_history_entry[subd_cube,head_basemesh]` (2) | A8 commit |
| `test_click_on_face_is_a_no_op` | A12 |
| `test_drag_over_threshold_is_not_a_click` | click threshold |
| `test_esc_restores_mesh_before_c_without_history[subd_cube,head_basemesh]` (2) | cancel |
| `test_esc_while_lmb_held_ends_session_and_release_is_harmless` | cancel |
| `test_rejected_click_shows_failed_validation` | A11 |
| `test_other_commands_are_ignored_with_hint` | modal session |
| `test_enter_has_no_lab_input` | A13 |
| `test_orbit_pan_zoom_work_during_session` | navigation |
| `test_vertex_hover_pauses_and_knife_hover_takes_over` | hover |
| `test_knife_pick_resolves_vertex_edge_face_outside` | E27 pick copy |
| `test_knife_preview_data_markers` | E30 markers |
| `test_knife_preview_data_seam_start_has_no_mirror_marker` | E30 |
| `test_knife_preview_data_unmirrored_start` | E30 |

**Totals.** Old Lab test files at `fe1b213`: 15 files, **271** tests (§4.4 said 263; it
counted `test_input_path.py` as 8). Together with the 253 app-path tests that is the 524 of
the baseline. **Kept 55:** topology 19, resymmetrize 8, knife 12, symmetry 12, scene 2,
import boundary 1, display 1. **Deleted 216, each with a row:** 142 with a named replacement
(ported in Slices 1b–4, or an app test for the same or the superseding rule), 10 whose
replacement is **ported in Slice 5** (hover 4, bindings 2, display 4), and 64 with a reason
only (the mirrored Knife: engine 24, window 40). Expected Lab suite after Slice 5:
524 − 216 + 10 = **318**; actual counts in §5 row 5.

**A3 — Slice 2 acceptance: the cost of a symmetric W drag is measured on the reference PC.**
Slice 2 adds a headless probe (`experiments/symmetry_lab/probe_drag_cost.py`, no window
needed, runs on Windows) that drives a symmetric W drag through `Application` with the
Lab overlay attached. It reports p50/p95/max per mouse move (transform step + overlay sync)
on `head_basemesh` and `man_with_shoes_basemesh`. Agents cannot reach the
[reference PC](REFERENCE_HARDWARE.md): Manu runs the probe there (one command, Slice 2
handoff), and agents add container numbers labelled as such (REFERENCE_HARDWARE.md §4).
Threshold: p95 ≤ 8 ms per move, the bar the Knife hover already uses (WP-KNIFE-01 S4 STOP).
If it is exceeded, the overlay sync is throttled or made incremental (state markers on
commit only, partner markers only for the moved vertices) before Slice 3 starts. The numbers
go into this plan.

*Measured (Slice 2, 2026-10-03).* Command (repo root, Windows and Linux alike):
`python experiments/symmetry_lab/probe_drag_cost.py`. Per mouse move = transform step
(`app.pointer_motion`) + Lab overlay syncs, symmetry X, 6 paired vertices selected by click
(12 moved with partners), 200 moves; ms.

**Container, not the reference PC** (Linux, Intel Xeon @ 2.10 GHz, 4 logical cores,
Python 3.11.15; REFERENCE_HARDWARE.md §4):

| Asset | Overlay sync | p50 | p95 | max | Verdict |
|---|---|---|---|---|---|
| `head_basemesh` (326 V) | first build: change signature only, report on every geometry change | 2.24 | 3.38 | 4.54 | ok |
| `man_with_shoes_basemesh` (928 V) | first build: change signature only | 6.80 | **11.48** | 18.34 | **exceeds 8 ms** → made incremental |
| `head_basemesh` | **as built:** report/plane/partner IDs deferred while the transform runs, marker positions follow | 0.09 | 0.12 | 1.49 | ok |
| `man_with_shoes_basemesh` | **as built** | 0.17 | 0.24 | 4.03 | ok |

Context, also container (not in the threshold): the first `viewport.sync()` after the commit
re-derives what the drag deferred (report + partners): p50 4.2 / 8.6 ms, p95 5.1 / 17.9 ms on
`head_basemesh` / `man_with_shoes_basemesh`, once per drag. A hover change (pick + Lab overlays,
no transform) p50 1.1 / 3.0 ms, p95 1.7 / 3.6 ms (Slice 1b measured 5.1 ms median for the
overlays alone on `man_with_shoes_basemesh`, before the change signature).

**Reference PC (Manu, 2026-10-03)** — Windows 10 (19045), Intel Core 2 Quad Q9550 @ 2.83 GHz
(4 logical cores), Python 3.14.2. Probe output pasted by Manu; per mouse move, ms:

| Asset | p50 | p95 | max | Verdict |
|---|---|---|---|---|
| `head_basemesh` (326 V, 12 moved) | 0.36 | 0.40 | 5.96 | **ok** |
| `man_with_shoes_basemesh` (928 V, 12 moved) | 0.69 | 0.86 | 16.65 | **ok** |

Split (p50 / p95 / max): transform step 0.10 / 0.11 / 5.68 and 0.10 / 0.13 / 15.98 (the max is
the first move, `begin_current_interaction`, once per drag); Lab overlays 0.26 / 0.29 / 0.52 and
0.59 / 0.75 / 0.93. **A3 is passed.**

Outside the threshold, also reference PC: remaining sync (app buffers) p95 1.04 / 1.44; the
commit frame (first sync after the drag) p50 11.6 / 34.2 ms, once per drag; a **hover change**
(pick + Lab overlays, no transform) p50 6.3 / **17.4** ms, p95 7.5 / **18.5** ms. The hover
change exceeded one 60-fps frame on `man_with_shoes_basemesh` while the mouse sweeps the mesh.

*Fix (2026-10-03, after the reference-PC run).* Cause, measured in the container on
`man_with_shoes_basemesh`, symmetry X, median per hover change: pick 0.86 ms, Lab overlays
**2.68 ms**, of which `mirrored_selection` for the hover partner ≈ 2.3 ms — it re-derived
`vertex_correspondence` for the whole mesh on every call. Now `mirrored_selection(mesh, ids,
correspondence=None)` takes an optional, already derived correspondence (`src/mirai/symmetry.py`;
behaviour unchanged without it) and the Lab passes the one its cached `SymmetryReport` already
holds (`SymmetryReport.correspondence`, not part of equality). Container after the fix: Lab
overlays 0.21 ms per hover change; hover change p50 3.47 → **1.04** ms, p95 5.15 → 1.71 ms on
`man_with_shoes_basemesh` (head: p50 1.24 → 0.45 ms). By the container/reference-PC ratio of the
first run (≈ 5×) the reference PC should land near 5 ms.

**Reference PC re-run after the fix (Manu, 2026-10-03), same machine:** per W-drag move p95
0.40 / 0.82 ms (unchanged, ok). Hover change p50 6.30 → **3.67** ms / 17.36 → **9.46** ms,
p95 7.51 → 4.77 / 18.54 → **10.78** ms on `head_basemesh` / `man_with_shoes_basemesh`. Commit
frame p50 11.6 → 6.4 / 34.2 → **18.2** ms (the deferred partner re-derivation now reuses the
report's correspondence too). The estimate of ≈ 5 ms was too optimistic: the remaining hover cost
is mostly the app's own pick, not the Lab. In the container the pick is ≈ 70 % of a hover change
with symmetry on (0.71 of 1.01 ms) and costs the same with symmetry off (0.66 ms), so
`src/main.py` pays it too (inference from the container split; the probe does not split the
hover line). 9.5 ms stays within one 60-fps frame (16.7 ms). **Closed for this WP;** a faster
pick on dense meshes would be a Production topic (B8 pick cache), not Lab work.
Tests: `tests/test_symmetry.py::TestMirroredSelection::test_given_correspondence_is_used_without_deriving`,
`experiments/symmetry_lab/tests/test_app_lab_partners.py::test_hover_and_selection_changes_derive_no_correspondence`
(fails without the Lab change). The commit frame (34 ms once per drag on the reference PC) is
left as is until the Artist finds it noticeable in the window.

---

## 1. Repository reality (verified 2026-10-03)

### 1.1 What the Lab is today

`experiments/symmetry_lab/`: 16 modules, 263 tests (14 files). The Lab builds a Production
`Application` (scene, selection, history, camera, bindings, tool manager). Everything
between the pyglet event and the tool is its own code:

```
pyglet event → mirai.pyglet_input → LabDispatcher (own gestures, own Move arming, own Knife)
            → LabRenderer (own shaders, own VBO data) — no Viewport, no GLRenderStore
```

Test baseline in this container: `pytest experiments/symmetry_lab/tests` → 253 passed. 10 need
EGL, which this container lacks: `test_input_path.py` (8), `test_import_boundary.py` (1) and
`test_lab_knife_window.py::test_enter_has_no_lab_input` (1). This is an environment
limit, not a regression (the same tests run with a display).

### 1.2 Drift evidence

| # | Drift | Where | Effect |
|---|---|---|---|
| D1 | W ignores constraints | `lab_dispatch.py:602` passes `space` only for Rotate/Scale; the app passes it for all three (`application.py:1103`, B4.1) | X/Y/Z does nothing for W in the Lab, but does in the app |
| D2 | Mirrored Knife is a pre-B7 copy | `lab_knife.py` (incremental, real cut per click) vs. `mirai.topology.knife` (virtual path, cut at commit, S1 resolver, S4 planner) | Not promotable; every Knife iteration since B7 is missing |
| D3 | Knife picking is a pre-B7 Playground copy | `lab_knife_pick.py` (83 lines, from `playground/…/knife_pick.py` @ `649fff5`) vs. `mirai.topology.knife_pick` (272 lines) | Lab Knife hover diverges from the app |
| D4 | Renderer and draw data are copies | `lab_render.py` ← `playground/window.py`, `lab_draw_data.py` ← `playground/vbo_builder.py` | No display modes, no occlusion picking, no flat shading |
| D5 | Lab triangulation is behind `src` for n-gons | `lab_draw_data.py:138` falls back to `triangulate_face(boundary)` **without positions** = plain fan; `src` ear-clips concave n-gons (`viewport/derived.py:105`) | Concave faces after a cut draw wrong in the Lab |
| D6 | E10 Newell normals duplicated | `lab_draw_data.face_normals` vs. `viewport.derived.face_normal` (in `src` since `e64de4f`, same scheme: Newell face normal, vertex normal = normalised sum) | Obsolete copy |
| D7 | Input logic re-implemented | `LabDispatcher` (725 lines): gestures, click threshold, hold-key arming, hover, undo; the app has `PointerGestures` (AD-019), `_transform_arm`, hover via `pick_component` + `PickCache` (B8) | Each app fix (UX2b Shift tracking, `on_deactivate`, B8 occlusion) needs a Lab copy |
| D8 | Undo semantics differ | Lab clears the selection after Undo (`lab_dispatch.py:381`); the app restores it (B6 follow-up, Artist 2026-09-28) | Different behaviour for the same keys |
| D9 | Stale record | ROADMAP §7 2026-10-02 (a) says only `MoveOperation` supports symmetry; since S2 (`f15957c`) Rotate/Scale do too (`core/operations/transform.py:323`) | Record only; corrected in ROADMAP §7, entry 2026-10-03 |

### 1.3 Production facts the rebase depends on

- **Symmetric W/E/R already live in `src`.** `MoveTool` (`tools/move.py:193`) and
  `TransformTool` (`tools/transform.py:360`, `resolve_symmetry`) read the definition from the
  mesh. `Application` needs no symmetry knowledge for them.
- **`SeamConstraintError` is not handled by `Application`.**
  `TransformTool.begin` raises it (`tools/transform.py:375–388`). `_transform_step` calls
  `begin_current_interaction` without a guard (`application.py:1103`). This is unreachable
  from `src/main.py` (it never sets a definition) but reachable in any host that does.
- **Selection mirror stack.** `Application` pairs every `history.push()` *it* triggers with a
  selection snapshot (`_record_selection_history`, `application.py:1240`) and pops both
  LIFO on Undo/Redo (`_apply_undo_redo`, `:1183`). A push from outside desynchronises this.
  Concrete case: W commit, then Shift+S (Lab push), then Ctrl+Z undoes the symmetry step but
  restores W's *before*-selection. The docstring anticipates exactly this case ("ein
  künftiger Push-Pfad, der hier noch nicht verdrahtet ist").
- **Topology tools carry no symmetry declaration.** `supports_symmetry` exists only on
  `Operation` (`core/operation.py:88`). Split/Connect/Knife are `MeshStateCommand`
  compositions, not Operations, so they run one-sided under symmetry. A dead seam edge
  degrades visibly, without a crash (`mirai.symmetry._seam_vertex_ids` skips invalid IDs, and
  the new seam vertex shows as `UNPAIRED`). This is the P1/P2 situation from Slice 6.
- **Overlay precedent.** `viewport.overlay.TOOL_LAYERS` plus `Viewport.set_tool_overlay`
  (B7): ready-made positions from the caller; the Viewport knows no Knife.
  `gl_line_overlay.FlatColorLayers` already takes `LAYERS`/`LAYER_STYLES` as class
  attributes (subclassable). `GLPointOverlay` does not (`DRAW_ORDER`/`LAYER_STYLES` are
  module constants, `gl_point_overlay.py:51,58`).
- **Cost of the symmetry report** (container, not reference hardware): `symmetry_report`
  takes 0.2 / 2.0 / 6.3 ms on `subd_cube` / `head_basemesh` / `man_with_shoes_basemesh`;
  `topology_report` takes 0.3 / 3.4 / 9.8 ms. Per frame is too expensive; per change matches
  today's Lab (§3, H1).

---

## 2. Deliverable 1 — Inventory

(a) = already in the app · (b) = symmetry feature, re-host · (c) = obsolete copy, delete.
Verdicts are quoted from the Lab README; none of them changes here.

| # | Lab feature (origin) | Module | Class | Production counterpart / re-host note | Artist verdict |
|---|---|---|---|---|---|
| 1 | Window, event translation (S2) | `lab_window.py` | c | `src/main.py` wiring, made importable (H6) | Slice 2 checked 2026-09-24 |
| 2 | Shaders, mesh draw (S2) | `lab_render.py` | c | `Viewport` → `GLRenderStore`, line/point/triangle overlays | Slice 2 checked |
| 3 | Face/edge/vertex/highlight VBO data (S2) | `lab_draw_data.py` (`face_data`, `edge_data`, `vertex_data`, `highlight_data`) | c | `RenderMesh`, `wireframe.edge_segments`, `SelectionOverlay` | Slice 2 checked |
| 4 | E10 Newell face/vertex normals (S4) | `lab_draw_data.py` (`face_normals`, `vertex_normals`) | c | `viewport.derived.face_normal` since `e64de4f` (same scheme) | part of Slice 4 KEEP |
| 5 | E10 quad split at the shorter diagonal (S4) | `lab_draw_data.triangulate_face_symmetric` | c (open) | `src` keeps the fan for convex quads. Not re-hosted: picking (B8 occlusion) and face overlays use `src` triangulation, so a Lab-only draw split would make the drawn and the picked surface disagree. Visible on `subd_cube` only (24/24 mirrored quads asymmetric; `head_basemesh` 0/324) → **Q1** | Slice 4 KEEP, step 10 |
| 6 | Orbit/Pan/Zoom with Lab overrides Alt+LMB, Shift+LMB, MMB, RMB unbound (S2) | `lab_bindings.py`, `lab_dispatch.py` | a | App bindings (Artist Input Truth, WP-06 B2): Alt+LMB drag, Alt+Shift+LMB drag, wheel | Slice 2 checked |
| 7 | Vertex click select, replace only (S2) | `lab_dispatch.select_at` | a | `Application.select_at` (replace/add/remove/toggle, V/E/F modes) | Slice 2 checked |
| 8 | Asset by registry name, framing (S2) | `lab_scene.py` | a (+ thin b) | `init_scene("obj", obj_path=asset_path(name))` + `frame_scene()`; the registry-name CLI with exit code 2 stays in the Lab | — |
| 9 | Lab binding context, `LAB_OVERRIDES`, console listing (S2–S7) | `lab_bindings.py`, `run.py` | b | Shrinks to Shift+S, M, Shift+B (navigation and C overrides dropped); console listing kept (AD-013 I6) | — |
| 10 | Symmetry cycle Shift+S off→X→Y→Z→off, E1–E3, one undo step each (S3) | `lab_symmetry.cycle_symmetry` | b | Via H2 (Lab key at window level) + H3 (history with selection mirror) | Slice 3 KEEP |
| 11 | Plane outline (S3) | `lab_draw_data.plane_outline_data` | b | Lab line overlay via H1 | Slice 3 KEEP |
| 12 | State markers: seam green, unpaired magenta, ambiguous white; `SymmetryReport` (S3) | `lab_symmetry.symmetry_report`, renderer | b | Lab point overlay via H1 | Slice 3 KEEP |
| 13 | Mirrored partner of the selection, turquoise (S3) | renderer + `mirrored_selection` | b | Lab point overlay via H1 | Slice 3 KEEP |
| 14 | Hover vertex (S4) | `lab_dispatch._update_hover` | a | App hover (B2b, `selection.hovered`, occlusion-aware B8) | Slice 4 KEEP |
| 15 | Mirrored partner of the hover, turquoise (S4) | renderer | b | Lab point overlay via H1, reads `selection.hovered` | Slice 4 KEEP |
| 16 | Move target rule: selection else hover, fixed at key press, hover target leaves the selection empty (S4 A4/E7/E8) | `lab_dispatch._arm_move` | a | `Application._transform_arm` (B3), same rule | Slice 4 KEEP |
| 17 | W hold-key-hover gesture (2026-09-27) | `lab_dispatch` | a | `Application.key_press`/`pointer_motion`/`key_release` (B3, `PROMOTED`) | **pending** → superseded (§4.2) |
| 18 | Symmetric Move semantics (partner mirrored, seam slides in plane) | `src` `MoveTool`/`MoveOperation` | a | Unchanged; the Lab's own arming code goes | Slice 3 KEEP |
| 19 | Symmetric Rotate/Scale + pivot = selection ∪ partners (WP-SYM-LAB-02 S2) | `src` `TransformTool`, `resolve_symmetry` | a | Unchanged | **pending** (S2) |
| 20 | Constraint keys X/Y/Z, Shift+X/Y/Z as a toggle (S2) | `lab_dispatch._toggle_constraint` | a | `Application._constrain` (B4.1); now also applies to W (D1) | (part of S2, pending) |
| 21 | Seam refusal shown before the first motion | `lab_dispatch.py:608` | a after H5 | `Application._transform_step` + H5 | (part of S2, pending) |
| 22 | E5 gate MARK/BLOCK, Shift+B, reads `supports_symmetry` (WP-SYM-LAB-02 S1) | `lab_dispatch._gated`, `_arm_move` | b | Via H2 (command gate, BLOCK row); extended to C (contextual C + Knife), which has no declaration and so counts as unsupported | **pending** (E5) |
| 23 | Re-Symmetrize plan/apply, topological source side (S5) | `lab_resymmetrize.py` | b | Unchanged module; push via H3 | Slice 5 KEEP |
| 24 | Re-Symmetrize preview: modal M/M/Esc, blue/light green/light red + lines, text line, hover paused, other commands ignored with a hint (S5) | `lab_dispatch` preview code, renderer | b | Via H2 (Lab keys M/Esc, preview allow-list for keys and clicks, `hover_suspended`) + H3 + H1 + Lab HUD | Slice 5 KEEP |
| 25 | Topological pairing and sides (S5, E11/E12) | `lab_topology.py` | b | Unchanged module | Slice 5 KEEP |
| 26 | Undo/Redo clears the selection | `lab_dispatch._undo_redo` | a | App restores the selection (B6 follow-up) | — |
| 27 | Status line text, on screen (S3–S7) | `lab_status.py`, `lab_window` labels | b | Lab HUD (pyglet label) = Lab state line + `app.status_message`; writes via H4 | — |
| 28 | Esc closes the window when idle (S2/S3) | `lab_window` | a | App rule: Esc = Cancel only, the X button closes (B1 A3) | Slice 3 KEEP step 8 (covered by app decision) |
| 29 | Mirrored Knife engine, intent pairs, validation E16–E22 (S6) | `lab_knife.py` | c | **Not re-hosted** (pre-B7 copy, D2). A future symmetric One Knife mirrors the virtual path before resolution (separate package). Findings P1–P3 are kept as tests (§4.4) | Slice 6: headless only, never verdicted |
| 30 | Knife picking (S7) | `lab_knife_pick.py` | c | `mirai.topology.knife_pick` | Slice 7 **pending** → moot |
| 31 | Knife hover dry run, Knife markers, Knife status (S7) | `lab_knife_preview.py`, `knife_preview_data`, `knife_text` | c | — | Slice 7 **pending** → moot |
| 32 | `Change` flags, `take_changes`, full VBO rebuild | `lab_dispatch.Change`, `lab_window._sync` | c | Viewport dirty flags; the Lab overlay re-syncs on the Viewport's notifications (H1) | — |
| 33 | No `playground/` import (AD-010 precedent) | `tests/test_import_boundary.py` | b | Kept; the module list shrinks | — |
| 34 | `sys.path` bootstrap | `_paths.py` | b | Kept, minimal | — |

---

## 3. Deliverable 2 — Hook points in `src/`

Smallest set found: H1–H4 are hooks, H5 is a bug guard, H6 is a pure refactor. All six are
off by default, and `src/main.py` uses none of the hooks.

| Hook | What (smallest form) | Needed by | Classification (AGENTS.md §5) |
|---|---|---|---|
| **H1** Extra overlay | `Viewport.add_overlay(o)`. `o.sync(mesh, selection)` runs inside `Viewport.sync()` whenever the Viewport's own selection/geometry/topology dirty flags were set, or when `o.dirty` is set. `o.draw(camera_uniforms)` runs in `render()` **after the tool lines, before the point overlay**. Plus: `GLPointOverlay` takes its layers/styles as class attributes, like `FlatColorLayers`, so the Lab can subclass it | Inventory #11–13, 15, 24 | **Small detail.** Precedents: `TOOL_LAYERS`/`set_tool_overlay` (B7) and `FlatColorLayers`. The Viewport stays symmetry-agnostic, data still flows Core → Viewport, and there are no new colours in `src` |
| **H2** Command gate (revised after review CLAUDE-001) | Data only, no callback (AD-013 addendum, proposal G): `Application.command_gate` (default `None`; `refused: dict[command, status text]`, `allowed: frozenset \| None` allow-list, `not_allowed_text`), checked in `key_press` right after command resolution (`application.py:999`, after the Knife routing) and in `_execute_click` (`:1440`); a refused event posts the text and returns `False`. `Application.hover_suspended` (default `False`), honoured in `_update_hover` (`:1388`). Read-only `Application.interaction_owner` (`None` / `"transform"` / `"knife"`). The Lab's own keys (exactly Shift+S, M, Shift+B in context `symmetry_lab`, asserted free in GLOBAL and KNIFE at start-up) are resolved at window level through the one `app.bindings`; everything else goes to `app.key_press`. Esc closes the preview at window level (D1). While the preview is open, Shift+S/Shift+B are refused and the preview row stays installed (N2). The window step is a pyglet-free `lab_key_press(app, lab, input) -> bool`; the pyglet handler always returns `EVENT_HANDLED` (N4). Preconditions: H3, H4 | #10, 22, 24, Slice 1 C refusal | **Architecture boundary.** Touches AD-013 I3 (one authority owns start and end) and I4 (one binding authority), plus AD-015/AD-016 input ownership. AD-013 addendum **DECIDED** after reviews CLAUDE-001 and CLAUDE-002. Not an Artist question |
| **H3** External mesh change | `Application.apply_mesh_change(description, mutate)` (review CLAUDE-002 N1; replaces the earlier `record_mesh_change(command, selection_before, moved=None)`, whose selection format is private): raises if `interaction_owner` is set (AD-013 H2 D3, before any change); snapshots selection and `mesh.export_state()`; calls `mutate()` (Lab core-operation calls, returns moved vertex IDs or `None` for a topology change); restores the mesh if `mutate` raises; no change → no history entry, returns `False`; else one `MeshStateCommand`, `_record_selection_history`, pick cache invalidate, `viewport.on_vertices_moved(moved)` or `on_topology_changed()`, `_refresh_hover()`. The Lab functions become `mutate` callables instead of building and pushing a `MeshStateCommand` (`lab_symmetry.py:88`, `lab_resymmetrize.py:166`). Lab code never calls `history.push` (H2-R4) | #10, 23 | **Small detail.** Completes the push path the B6 follow-up docstring anticipates; `HistoryStack` and core stay unchanged |
| **H4** Status | `Application.set_status(message)`, the public form of `_set_status` (`:1278`), same `status_serial`. Precondition of H2 (review F10): lands in Slice 1, not Slice 2 | #22, 24, 27 | **Small detail** |
| **H5** Seam refusal guard | `_transform_step`: catch `SeamConstraintError` from `begin_current_interaction`, end the transform, status `"<Rotate/Scale>: refused — <reason>"`, `_refresh_hover()`. No history entry | #21; reachable as soon as Slice 1 sets a definition | **Small detail.** Bug guard for a refusal AD-SYM-02 §2.4 / INV-8 already decided; status text `PROVISIONAL` like the other app status lines |
| **H6** Importable entry wiring | Split `src/main.py` into `create_window()`, `install_handlers(window, app)` and `run(window, app)` (plus the `gl_types` constant); `main()` composes them. Behaviour identical | #1 | **Small detail.** Pure refactor; it also makes the wiring headless-testable for the first time (`tests/test_main_entry_point.py` only covers the draw path) |

The Lab draws its HUD with its own `on_draw` handler pushed on top of the shared one. It
calls the app's draw first and then its label. That is Lab code, not a hook.

### 3.1 Alternatives considered

**Overall approach**

- **Keep the Lab renderer, import instead of copy** (replace D3–D6 with `src` imports, keep
  `LabDispatcher`). *Not used because* the root cause is D7: a second input layer goes on
  drifting from the app (D1 and D8 are input drift, not draw drift).
- **Promote the symmetry UX into `src/main.py` behind a flag.** *Not used because* of M3 and
  AD-013 I7: promotion is the Artist's decision (deferred, ROADMAP 2026-10-02). The trigger
  explicitly keeps `src/main.py` free of symmetry UX.
- **A general plugin/extension system in `Application`** (command registry, overlay
  providers, event bus). *Not used because* of AGENTS.md §7 ("do not build future systems")
  and INPUT_COMMAND_TOOL_CONTRACT §3 ("must not introduce a complex hierarchical context
  framework without a demonstrated use case"). One experiment is one use case, so it gets one
  hook (after review CLAUDE-001: one data-only command gate, no callback) and no registry.

**H2 input hook**

- **Subclass `Application` in the Lab and override `key_press`, `_execute_click`,
  `pointer_motion`.** *Not used because* it couples the experiment to private methods.
  An `Application` refactor would change Lab behaviour without any signal, which is the same
  drift class in disguise and a fork of the interaction authority (AD-013 I1/I3).
- **A facade in front of `Application` at window level.** *Not used because* blocking a
  select click but not an Alt+LMB orbit needs the click-vs-drag decision.
  `PointerGestures` makes that decision inside `Application`, so a facade would have to
  re-implement it, which is the `LabDispatcher` problem again. Keys alone would work this way;
  pointers would not.
- **Fallback-only: Application resolves an "active context" and hands unknown commands to
  the Lab.** *Not used because* it cannot pre-empt anything. The C refusal, the E5 BLOCK and
  the modal Re-Symmetrize preview all have to stop an app command, not just add new ones.
- **One optional hook object (callback), consulted first in `key_press`, `_execute_click` and
  `pointer_motion`** (the first H2 draft). *Not used because* (review CLAUDE-001 F1, F3, F4,
  F9): its precedence over `Application`'s own gates existed only as branch order and was
  stated wrongly (Undo/W ran under the preview during an orbit), its motion call site cannot
  pause hover (zoom re-picks it), and its back-off predicate was undefined. The data-only gate
  sits after `Application`'s routing, so precedence is `Application`'s by construction. The
  argument is recorded in the AD-013 addendum, § Alternatives.

**H1 overlay**

- **Symmetry layer names and colours in `src/viewport`.** *Not used because* the Lab colour
  legend would become Production UX (M3, AD-013 I7).
- **The Lab draws its overlays itself after `viewport.render()`.** *Not used because* of draw
  order: the seam/partner markers would cover the selection and hover points. In the Lab the
  selection is drawn last (README, "Zeichenreihenfolge"); in the app the point overlay is the
  last pass.
- **Recompute the overlays every frame** (no `sync` notification). *Not used because* it costs
  6–10 ms per frame on `man_with_shoes_basemesh` (§1.3). Driving it off the Viewport's
  notifications costs the same as today's Lab (one report per change) and covers app-driven
  changes too (Undo, drag, Knife commit), which `Application` already reports to the Viewport.

**H3 history**

- **The Lab pushes directly and accepts the desync.** *Not used because* Undo would restore a
  wrong selection (§1.3, concrete case).
- **The Lab clears the selection after every Undo, as today.** *Not used because* it fights the
  app's restore (D8) and drops an Artist decision (B6 follow-up).

**H6 entry**

- **Copy the ~100 lines of `src/main.py` handlers into the Lab.** *Not used because* this is the
  drift D4/D7 again. The Shift tracking (UX2b) and `on_deactivate` were added to `main.py` on
  2026-10-02, exactly the kind of change a copy misses.
- **Call `main.main()` with injected hooks.** *Not used because* `main.py` would then have to
  know about experiments.

### 3.2 Not needed

No `src/core` change, no new command in `mirai.interaction.commands` (`SymmetryCycle`,
`ReSymmetrize`, `SymmetryGateMode` stay Lab-local, as the test does today), and no
`_VALID_CONTEXTS` change (`set_default` takes any context string; only `keymap.json` is
restricted, and the Lab does not use it).

---

## 4. Deliverable 3 — Verdict preservation

### 4.1 KEEP behaviours reproduced exactly

| KEEP (date) | Behaviour | Provided by after the rebase | Proven by |
|---|---|---|---|
| S3 (2026-09-25) | Shift+S off→X→Y→Z→off; one undo step each; Ctrl+Z/Ctrl+Y walk the cycle | Lab key via H2 + H3 | ported `test_lab_symmetry` cycle tests + new mirror-alignment test (W commit → Shift+S → Undo ×2 restores the right selection each time) |
| S3 | Plane outline through the origin, bounds + 10 %, light blue | Lab overlay (H1) | kept `plane_outline` tests |
| S3 | Seam green, unpaired magenta, ambiguous white; `Symmetrie: X (valid) \| ohne Partner: N`; `man_with_shoes` X = 54 unpaired | Lab overlay + HUD | kept asset characterisation |
| S3 | Selected vertex shows its mirrored partner in turquoise | Lab overlay | new overlay-data test |
| S3 | W moves vertex and partner mirrored; a seam vertex slides in the plane; one undo step; Esc restores exactly without history | `src` `MoveTool` through `Application` | ported `test_lab_move` symmetric subset |
| S4 | Hover shows the mirrored partner in turquoise without selecting | Lab overlay reading `selection.hovered` | new overlay-data test |
| S4 | Move target rule A4/E7/E8 | `Application._transform_arm` (same rule) | app tests (`test_application_move`, `test_application_hover`) |
| S5 | M preview → M execute (one undo step; 0 changes = no entry) → Esc closes without change | Lab keys M/Esc via H2 (Esc: D1) + H3 | ported dispatcher-level `test_lab_resymmetrize` |
| S5 | Source side is topological (A6); exactly one vertex; the five rejections | `lab_resymmetrize` (unchanged) | kept pure tests |
| S5 | During the preview: navigation works; select, W/E/R, Shift+S, C, Undo/Redo ignored with `Vorschau aktiv — Befehl ignoriert`; hover paused | H2 preview allow-list (key + click) + `hover_suspended` | ported preview tests + AD-013 T-R2c (F1 sequence), T-R2e, T-H |
| S5 | Preview colours blue / light green / light red with lines; text line above the status line | Lab overlay + HUD | kept `test_preview_draw_data` |
| S5 | Selection kept after execute | H3 (selection snapshot) | ported |

### 4.2 Pending verdicts

| Pending | After the rebase |
|---|---|
| W like the app (2026-09-27) | **Superseded, never verdicted.** The Lab *is* the app's W (B3 `PROMOTED`); there is nothing Lab-specific left to judge |
| Slice 7 mirrored Knife in the window | **Moot, never verdicted.** Not re-hosted (trigger). Findings E23–E30, P1–P3 stay in the Lab README as research for the symmetric One Knife |
| WP-SYM-LAB-02 S2 (symmetric Rotate/Scale, pivot) | **Pivot decided: B — per side** (Manu, 2026-10-03, after the joint session): without an explicit `pivot`, the centroid of the explicit selection; the operation mirrors it for the partners; fallback to the centroid over selection ∪ partners when a seam vertex is affected and the own centroid is off the plane (`selection_helpers.symmetric_default_pivot`, used by `TransformTool._on_begin`). A single vertex therefore turns/scales about itself. The pair midpoint (A) stays an idea for a later pivot system (free/temporary pivots). Built 2026-10-03; re-checked in the window: **KEEP** (Manu, 2026-10-03) |
| E5 MARK vs. BLOCK | **KEEP-BLOCK** (Manu, 2026-10-03, joint session, tested with C on the app path): a tool that does not mirror is refused under symmetry. Recorded in AD-SYM-02 §4. Lab consequence: BLOCK becomes the default (Slice 5) |

**Joint session after Slice 4 (Manu, 2026-10-03):** 1 S3–S5 smoke on the new host **KEEP** ·
2 S2 pivot question → decided B, built, **KEEP** · 3 E5 **KEEP-BLOCK** · 4 Q1 **(a)** · 5 preview lines under the
symmetry markers **KEEP**. Details in the Lab README, "Gemeinsame Prüf-Session nach Slice 4".

### 4.3 What visibly changes

**Covered by existing app decisions: no new verdict** (the rebase adopts the app; it decides
nothing new):

| Change | App decision |
|---|---|
| Selection yellow 8 px instead of red 10 px; hover pale translucent yellow; no orange dot per vertex | B2b (A10/A11) |
| Navigation: Alt+Shift+LMB drag = Pan, Shift+click = add to selection, MMB unbound, no RMB rule | B2 (Artist Input Truth); the Lab cannot override pointer input under H2 (AD-013 H2-R1, review F6) |
| Picking is occlusion-aware in Shaded (back-side vertices not pickable); hover cleared during orbit | B8, B2b |
| W honours X/Y/Z (was ignored, D1) | B4.1 |
| Undo/Redo restores the selection instead of clearing it | B6 follow-up |
| Esc never closes the window; the X button does | B1 A3 |
| V/E/F modes, D display modes, contextual C, Knife available | B5a, B5b, B6, B7 |
| C under symmetry: no mirrored cut any more (Slice 1: refused; Slice 4: E5 MARK/BLOCK) | Trigger: the mirrored Knife is not re-hosted |
| Status mixes app English and Lab German texts | Not a product question; Lab strings stay as written |

**Needs a new Artist verdict (short on purpose):**

1. **Q1 — Shading of `subd_cube` under X symmetry** (Slice 4 KEEP, step 10). Without E10's
   diagonal rule the cube shades asymmetrically again; the head does not change. See §6.
2. **One combined re-check session after Slice 4** (old and new Lab side by side, about
   10 minutes): S3–S5 KEEP smoke in the new host + the pending S2 + E5 with C + Q1. This is not
   a new decision on any KEEP. The Artist only confirms "the same as before", which no test
   can prove.

### 4.4 Test porting plan (263 tests)

| File | Tests | Keep | Port to the `Application` path | Delete | Note |
|---|---|---|---|---|---|
| `test_lab_topology.py` | 19 | 19 | – | – | unchanged module |
| `test_lab_symmetry.py` | 20 | 17 | 3 | – | cycle tests via H2/H3; + new mirror-alignment test |
| `test_lab_resymmetrize.py` | 30 | 17 | 13 | – | dispatcher tests → `app.key_press` / `pointer_*` |
| `test_lab_symmetric_transform.py` | 12 | – | 12 | – | through `app.key_press`/`pointer_motion`; + W with constraint under symmetry |
| `test_lab_gate.py` | 13 | – | 13 | – | E5 via H2; + C under MARK/BLOCK |
| `test_lab_scene.py` | 7 | – | 7 | – | `init_scene("obj", asset_path(…))` |
| `test_lab_move.py` | 26 | – | ≈6 | ≈20 | keep: symmetric partner, seam slide, one undo step, exact Esc, no-symmetry case, status; gesture mechanics are app-tested |
| `test_lab_knife.py` | 36 | 12 | – | 24 | keep baseline + P1–P3 (Mesh primitives + `lab_topology`; inline the 2–3 helpers); engine tests go with the engine |
| `test_lab_bindings.py` | 20 | – | ≈8 | ≈12 | Shift+S/M/Shift+B + global fall-through; nav/C overrides gone |
| `test_draw_data.py` | 9 | 1 | 4 | 4 | diagonal characterisation (2) and mirrored normals (2) against `viewport.derived`; VBO lengths deleted |
| `test_import_boundary.py` | 1 | 1 | – | – | module list updated |
| `test_lab_hover.py` | 11 | – | – | 11 | all are app rules (B3/E24); a hover-partner test is new |
| `test_lab_dispatch.py` | 11 | – | – | 11 | navigation/select = app (`test_application_pointer`) |
| `test_input_path.py` | 8 | – | – | 8 | pyglet → `Input` is `tests/test_pyglet_input.py` |
| `test_lab_knife_window.py` | 40 | – | – | 40 | Knife window not re-hosted |
| **Total** | **263** | **67** | **≈66** | **≈130** | |

New tests in `tests/` (Production): H1 (draw order, `sync` on notifications, no-op without
overlays), H2 (the AD-013 addendum's § Required tests: T-R1a..T-R5c and T-H, including the
inert-but-active pass-through run of `tests/test_application_*`), H3 (mirror
alignment), H4, H5 (refusal: no history entry, transform ended, status), H6 (`install_handlers`
headless) and **symmetric Move with an axis constraint**. That combination is untested in
`src` today (`tests/test_symmetric_move.py` has no `space` case) and becomes reachable by D1.
A guard test asserts that `src/main.py` writes no `command_gate`/`hover_suspended`, calls
neither `apply_mesh_change` nor `set_status`, and adds no overlay.

---

## 5. Deliverable 4 — Slice plan

The new host is built **next to** the old Lab, in the same package with a new entry
(`run_app.py`), until the Artist session. That keeps the pending S2/E5 tests playable at every
point and allows an old-vs-new comparison. Each slice is one revertable commit series;
`src` changes come first and are behaviour-neutral for `src/main.py`.

| Slice | Scope | `src` touched | Done when |
|---|---|---|---|
| **1a** `src` hooks — **done 2026-10-03** | Slice 1 split (2026-10-03): 1a = the `src` part only, 1b = the Lab part. Step 0 / gate: AD-013 addendum for H2 DECIDED (A1, passed 2026-10-03). `src`: H6, H1, H4, H3, H2 (`command_gate` with its `key_press` and `_execute_click` checks, `interaction_owner`; not `hover_suspended`), H5 — one commit per hook, each behaviour-neutral for `src/main.py`. **As built:** H6 stays in `src/main.py` (`create_window()`, `install_handlers(window, app)`, `run(window, app)`, `GL_TYPES`; no new `src/app_window.py`). H1: `Viewport.add_overlay(o)` / `extra_overlays`; `o.sync(mesh, selection)` runs when the Viewport's selection/geometry/topology notifications arrived, on the first `sync()` after `add_overlay`, or when `o.dirty` is set (the overlay resets its own flag); `GLPointOverlay.LAYERS`/`LAYER_STYLES` as class attributes (module `DRAW_ORDER`/`LAYER_STYLES` kept). H2: frozen dataclass `CommandGate(refused, allowed, not_allowed_text)` in `mirai.application`; the click check sits inside the select branch, right before `select_at`. `interaction_owner` landed with H3 (its D3 guard reads it). H3 raises `RuntimeError` while `interaction_owner` is set. H5 status `"<Label>: refused — <reason>"`, return `False`. A definition-only change (Shift+S) returns an empty set or `None` from `mutate`; with an empty set the Viewport gets no dirty flag, so the Lab overlay sets its own `dirty` (1b) | `src/main.py` (refactor), `viewport/viewport.py`, `viewport/gl_point_overlay.py`, `mirai/application.py` | **Done:** `pytest tests --ignore=tests/test_extrude_tool.py` 1609 → **1651** passed (+42 new, nothing else changed); `playground/tests` 1235 and `experiments/symmetry_lab/tests` 271 unchanged (container, Xvfb + EGL). AD-013 H2 tests at `Application` level: T-R2d, T-R3 (generic rows: block-list and allow-list, key and click), T-R4c–e (direct `apply_mesh_change` calls), T-R5a, T-R5b (AST guard on `src/main.py`, also `add_overlay`), T-R5c (pass-through of the 389 `tests/test_application_*` tests: inert gate → identical outcomes, gate consulted 574×; empty allow-list → 309 failures). Plus H1 (draw order, sync on notifications, no-op without overlays, subclassable points), H5 (refusal: no history, transform ended, status, hover re-picked), H6 (`install_handlers` headless), symmetric Move with an axis constraint (§4.4). Files: `tests/test_main_wiring.py`, `test_viewport_extra_overlays.py`, `test_app_set_status.py`, `test_app_apply_mesh_change.py`, `test_command_gate.py` (+ `_inert_gate_plugin.py`), `test_application_symmetry.py` |
| **1b** Lab on the app path + cycle + plane/state overlays — **done 2026-10-03** | Lab: `run_app.py` builds the app path with registry assets (reusing H6); window-level step for the three Lab keys with the start-up assert (GLOBAL + KNIFE) and the start-up listing of entries and gate rows; Shift+S via H2/H3; the Lab reads its symmetry state from `mesh.symmetry_definition` and re-derives it (and the gate row) after every forwarded key event, because `Application`'s Undo restores the definition (AD-013 H2-R2; check that no current Lab code caches it — CLAUDE-002 "outside H2"); plane outline + seam/unpaired/ambiguous markers via H1; HUD with the symmetry state. **C is refused while symmetry is on** (gate row `refused: Connect`, text `Symmetrie aktiv — C spiegelt nicht`), because without it C would run one-sided without warning (INV-8); Slice 4 replaces this with the E5 gate. Symmetric W/E/R work from here on through `src`; no Lab code for them. CLAUDE.md gets the Lab test command (§5, below) | — (only if 1b finds a hook gap: then back to 1a's rules) | Lab-side AD-013 H2 tests T-R1a–d, T-R2a/b/f/h, T-R3 (Slice 1 rows through `lab_key_press`), T-R4a/b, T-R4c through the Lab path green; ported cycle/outline/asset tests green; `pytest tests` and `playground/tests` unchanged; old `run.py` and its tests unchanged. **Done:** `experiments/symmetry_lab/tests` 271 → **341** passed (+70 new in `test_app_lab_bindings.py` 17, `test_app_lab_keys.py` 15, `test_app_lab_boundary.py` 9, `test_app_lab_cycle.py` 23, `test_run_app.py` 6; the 271 old tests unchanged); `pytest tests` 1651 and `playground/tests` 1235 unchanged (container, Xvfb + EGL; the new tests also pass headless without a display). No `src` change, no hook gap found. **As built:** new files `run_app.py` (`build_lab(window, asset, src_main, gl_types)`; `load_src_main()` imports `src/main.py` as module `main` and checks its path), `lab_app.py` (pyglet-free: `LAB_KEY_ENTRIES` = the three entries picked from `LAB_OVERRIDES`, `install_lab_bindings` with the start-up check `LabBindingConflict` via `command_for` in GLOBAL and KNIFE, `GATE_ROWS`, `startup_listing()`, `SymmetryAppLab`, `lab_key_press`, `hud_text`), `lab_overlays.py` (`SymmetryPlaneOverlay(FlatColorLayers)`, `SymmetryStateOverlay(GLPointOverlay)`, colours copied from `lab_render.py`), `lab_app_window.py` (pyglet glue). Only change to an old module: `lab_symmetry.set_symmetry_axis`, now shared by `cycle_symmetry` and the app-path `mutate`. **Window step:** `lab_key_press(app, lab, input, *, forward=None)` — the keyword `forward` (default `app.key_press`) lets the pyglet handler forward a non-Lab key through the `on_key_press` of `src/main.py` itself (captured by passing `install_handlers` a recording stand-in of the window), so its side effects (UX2b Shift tracking) stay; a Lab key never reaches that handler, which loses nothing because the Shift tracking reacts only to the Shift symbols. The Lab pushes `on_key_press` and `on_draw` (main draw, then the HUD label; returns `EVENT_HANDLED`). Shift+S status `Shift+S: Symmetrie <X|aus>`; refusals `<Command> abgelehnt — Transform läuft / Knife-Session läuft` and `<Command>: noch nicht verfügbar (Slice 3|4)` (PROVISIONAL). T-R3 covers keys only: no 1b row refuses a click. T-R4b is an autouse fixture in the new Lab test files (`tests/_app_lab_support.py`), scoped to the new modules; the old `LabDispatcher` is not in its scope. **Checked (CLAUDE-002 "outside H2"):** the new path caches no symmetry state; the old `lab_window` caches `symmetry_report` but refreshes it on every `Change.MESH` (the old path, unchanged until Slice 5). **Cost (container, not reference PC):** both overlays recompute per Viewport notification, including hover changes: p50 0.16 / 1.8 / 5.1 ms on `subd_cube` / `head_basemesh` / `man_with_shoes_basemesh` with symmetry X; A3 (Slice 2) decides on throttling |
| **2** Mirrored previews + HUD — **done 2026-10-03** | Partner markers for selection and hover (vertex mode); HUD line as `lab_status` (state, unpaired count, target, constraint); drag-cost probe (A3). (H4 moved to Slice 1, review F10) | — | ported symmetric move/transform tests via `Application`; new W + constraint + symmetry test; drag cost measured on the reference PC (A3). **Done (container):** `experiments/symmetry_lab/tests` 341 → **406** passed (+65: `test_app_lab_partners.py` 23, `test_app_lab_hud.py` 12, `test_app_lab_transform.py` 18 = the 12 `test_lab_symmetric_transform` ports + the 6 `test_lab_move` "keep" ports, `test_probe_drag_cost.py` 4, `test_app_lab_boundary.py` +7, `test_run_app.py` +1; the old Lab tests unchanged); `pytest tests` 1651 and `playground/tests` 1235 unchanged (Xvfb + EGL). No `src` change, no hook gap. Probe on the reference PC: **passed** (A3, 2026-10-03), hover-change fix afterwards (A3). **As built:** partner markers are two more layers of `SymmetryStateOverlay` (seam → unpaired → ambiguous → hover partner → selection partner, turquoise `(0.1, 0.85, 0.95)` from `lab_render.py`, 8 px = the app's selection size), not a third overlay; partners only from `mirrored_selection`, only in vertex mode, hover only if it is a `VertexId` (Edge/Face IDs are ints too). **Overlay cost:** the `Mesh` exposes no change counter, so the overlays compare a Lab-side `geometry_signature(mesh)` (definition, vertex IDs + positions, seam endpoints; 0.05 ms vs. 4 ms for the report on `man_with_shoes_basemesh`): plane and state markers skip hover/selection-only notifications. Signature alone still exceeded A3 (table above), so while `interaction_owner == "transform"` a *positions-only* change is deferred (report, plane, partner IDs from the drag start; marker positions follow); the overlays keep `dirty` set meanwhile because the commit notifies the Viewport of nothing, and the first sync after the end re-derives. A definition/topology/seam change is never deferred (Shift+S directly before W). One `ReportCache` is shared by the state overlay and the HUD (`lab.report`), so the per-frame HUD derives nothing. **HUD:** `hud_text(app, asset_name, report)`; target from `transform_target` (the app clears the hover on arm), `Hover (<n> V)` for an edge/face hover target; label wraps at the window width; no selection list (brief). **`run_app.build_app_lab`** = the window-free half of `build_lab`, used by the probe and the tests' `make_lab`. **T-R4a** additionally checks every `Application` method Lab code touches against H2-R4 (c)–(e), allows the new (f) only in `run_app.py`, and attribute writes only for (b); the probe is in its scope. **Deviations:** the 1b test `test_hud_text_shows_symmetry_and_status` was rewritten for the new `hud_text` signature (it pinned the 1b placeholder line); the HUD reads the public read-only properties `transform_target`, `transform_interacting` and `axis_constraint`, which H2-R4 (a) does not name (read-only like the listed state; the deferral predicate itself uses the listed `interaction_owner`); a Lab-path "W + constraint + symmetry" test exists as the port of `test_move_and_gate_unchanged` (it adds the `lab_key_press` forwarding and a real asset to the Slice 1a `src` test) |
| **3** Re-Symmetrize — **done 2026-10-03** | M preview/execute via the Lab key, Esc via the window step (D1); preview gate row (allow-list: display commands only) and `hover_suspended`; H3 with moved IDs; preview overlay and text line | `application.py` (`hover_suspended` in `_update_hover`) | all 30 resymmetrize tests (kept or ported) green; AD-013 H2 tests T-R2c (F1 sequence), T-R2e (incl. Shift+S/Shift+B refused), T-R2g (fuzz), T-H, T-R3 (preview rows) green. **Done (container, Xvfb + EGL; the Lab tests also without a display):** `pytest tests` 1652 → **1659** (+7 in `test_app_hover_suspended.py`: T-H at `Application` level in Face mode with motion, one wheel step and re-pick, negative control without the flag, refresh after Undo, Knife hover untouched, T-R5a extended — also one assertion added to `test_command_gate.py::test_default_gate_is_none`); T-R5c pass-through unchanged; `playground/tests` 1235 unchanged; `experiments/symmetry_lab/tests` 407 → **481** (+74: `test_app_lab_preview.py` 37 — T-R2c, T-R2e, N2 regression, T-R3 preview rows for 14 keys and 2 clicks, Lab-level T-H, execute through H3, Ctrl+Z restores mesh and selection, overlay layers/order/colours, start-up listing, window close; `test_app_lab_preview_fuzz.py` 13 — T-R2g, 12 fixed seeds × 300 events after a random warm-up, plus a negative control without gate and flag; `test_app_lab_resymmetrize.py` 22 — the dispatcher tests of `test_lab_resymmetrize.py` on the app path; `test_app_lab_preview_window.py` 2 — `EVENT_HANDLED` in every branch, preview label); the 30 old resymmetrize tests unchanged and green; `probe_drag_cost.py` OK, no regression (container p95 per move 0.27 ms on `man_with_shoes_basemesh`, 0.30 before). **As built:** `src`: `Application.hover_suspended` property over `_hover_suspended`; setting True clears `selection.hovered` (viewport notified), `_update_hover` keeps it cleared while set, setting False re-picks via `_refresh_hover`; only a change of the value acts. Lab: `SymmetryAppLab.preview` (the `ResymPlan`, computed once on M), `GateRow` gains the `hover_suspended` column, `ROW_PREVIEW` (allow-list = the five display commands, `Vorschau aktiv — Befehl ignoriert`, hover suspended); `_install_row` is the one writer of both and raises `AssertionError` for any other row while the preview is open; `sync_gate` installs nothing while it is open. `lab_key_press`: Lab command → `run_command` (owner refusal first, then M = open/execute, any other Lab command refused with the preview text while open), then `Cancel` while the preview is open → `cancel_preview` (D1), else forward. Source vertex and the three rejection texts as the old dispatcher (`selection.vertices`, exactly one). Execute: `apply_mesh_change(plan_description(plan), mutate)` with the new shared `lab_resymmetrize.set_plan_positions` (returns the moved IDs; `apply_plan` uses it too, its behaviour unchanged); the empty plan reaches `apply_mesh_change` and records nothing. Opening posts an empty status (the old Lab cleared its message; the blue line carries the text). Overlay: preview *points* are three more layers of `SymmetryStateOverlay` between the state markers and the partners (old draw order), preview *lines* a new `ResymPreviewLineOverlay` (no depth test) attached between the plane and the state overlay, so the lines lie under the state markers (old renderer: above) — the one draw-order deviation; point size 8 px (= the app's selection, like the partners); layers keyed on the plan object (the gate keeps the mesh fixed meanwhile). HUD: `preview_text(lab)` as a second label above the HUD line, colour from the old `lab_window`. Window close: `run_app.run_lab` ends the preview when the event loop returns (no extra `on_close` handler, so pyglet's close is unchanged and the pushed handlers stay `on_key_press`/`on_draw`). **Deviations:** four 1b/2 tests that pinned the earlier state were adjusted, not rewritten: T-R1d (`len(GATE_ROWS) == 3`, one "noch nicht verfügbar"), the T-R3 refusal rows `M_idle`/`M_symmetry_on` (now the old Lab's rejection texts), the `_overlays` helpers in `test_app_lab_cycle.py`/`test_app_lab_partners.py` (three overlays) with the attach-order and layer-order assertions. The ports are 22 tests, not 13: §4.4 counted 13, but 19 of the 26 functions in `test_lab_resymmetrize.py` drive the dispatcher; all of them are ported or covered (mapping table in the new file's docstring), plus one new rejection (two selected vertices) |
| **4** E5 gate — **done 2026-10-03** | Shift+B MARK/BLOCK via H2 (gate rows MARK/BLOCK), now for W/E/R (`supports_symmetry`) **and C** (no declaration = unsupported); replaces the Slice 1 refusal; MARK keeps a persistent HUD line while a one-sided C/Knife session runs | — | ported gate tests + C cases (MARK: one-sided, one history entry, seam degradation visible; BLOCK: nothing, no history). **Then the Artist session (§4.3).** **Done (container, Xvfb + EGL; the Lab tests also without a display):** `experiments/symmetry_lab/tests` 481 → **524** (+43: `test_app_lab_gate.py` 40 — the 13 `test_lab_gate.py` ports, Shift+B (toggle, no history/mesh change, refused during armed/running transform, Knife session and preview, HUD mode only while symmetry is on), C under MARK (Split with a selection: one history entry, one new vertex, unpaired in the report and in the magenta overlay layer, state `partial`; empty selection: Knife session with the warning line, gone after Esc; a one-sided Knife cut + Enter: one history entry, one new edge), C under BLOCK (refused for selection and empty selection: `False`, status, `status_serial` + 1, no history, no session), C with symmetry off in both modes, the BLOCK row derived from the declarations, patched declaration (BLOCK refuses exactly that command, MARK arms it with the "läuft einseitig" line), W/E/R unpatched never refused in BLOCK, Cancel never refused outside the preview (also with every declaration patched off) and Esc still cancels a running Move in BLOCK, T-R3 BLOCK rows (C empty/edge, patched E/R), start-up listing; `test_app_lab_gate_window.py` 2 — Shift+B through the pyglet handler, the orange warning line drawn above the HUD line; T-R2h in `test_app_lab_keys.py` now parametrised over BLOCK and MARK, +1); the old `test_lab_gate.py` (13) unchanged and green; `pytest tests` 1659 and `playground/tests` 1235 unchanged. No `src` change, no hook gap. **As built:** `lab_app.GateMode` (MARK default) as `SymmetryAppLab.gate_mode`, Lab state only; Shift+B → `_toggle_gate_mode` (re-derives the row via `sync_gate`, status `E5-Modus: <MARK\|BLOCK>`, returns `True`; allowed with symmetry off — the row stays "off", the mode applies from the next Shift+S, as in the old Lab). Rows: `ROW_SYMMETRY_OFF` (`None`), `ROW_MARK` (`None`), `block_row()` (refused: `Connect` plus every command of `TRANSFORM_OPERATIONS` — the old Lab's command → Operation pairing — whose Operation class does not declare `supports_symmetry`, read at every derivation; texts `block_text(<Name>)` = the old Lab's `Symmetrie aktiv — <Name> spiegelt nicht (BLOCK: <Name> nicht gestartet)`, C's name is `C`), `ROW_PREVIEW`; `gate_rows()` replaces the constant `GATE_ROWS`, `gate_row_for(axis, mode)`. Because `block_row()` is rebuilt on every derivation, `sync_gate` compares the installed gate with `==` (frozen `CommandGate`, equal declarations → equal row) instead of `is`. HUD: `hud_text(…, gate_mode=None)` adds `E5: <MARK\|BLOCK>` after the transform part while symmetry is on (old status line position; without the argument the Slice 2 line is unchanged); `e5_warning_text(lab)` is the orange line above the HUD line (`WARNING_COLOR`, below an open preview line): `Knife läuft einseitig — Symmetrie aktiv` while `knife_active`, the old Lab's `Symmetrie aktiv — <Name> spiegelt nicht (läuft einseitig)` while a transform whose Operation does not declare `supports_symmetry` is armed or running; the Lab writes no status for either (H2-R2). An immediate C (Split/Connect) under MARK keeps the app's own status; its degradation shows through the existing unpaired marker (no one-shot warning built — see deviations). **Deviations:** (1) the warning line depends on symmetry only, not on MARK — under BLOCK neither case is reachable (the gate starts neither, Shift+S/Shift+B are refused during an interaction), so the observable behaviour is the brief's; (2) the old Lab hid the partner marker while a one-sided transform ran (`test_mark_hides_partner_marker_only_while_armed`); the port asserts the warning line instead and the partner markers stay — the brief asks only for the HUD line; (3) the brief's "new seam vertex shows as unpaired" is tested with the Split of an edge with both ends on +X: a Split vertex is unpaired only when it lies off the plane (an edge lying in the plane would give a green seam vertex, no degradation); (4) the one-sided transform warning is reachable only through a patched declaration, and the `src` tools do not read the declaration, so a patched E/R still mirrors — the line is a Lab promise, as in the old Lab's tests; (5) proposal, not built: a one-shot status after an immediate C under MARK (e.g. `C einseitig — Symmetrie aktiv`) would have to overwrite the app's `Split`/`Connect` status, which the brief rules out. **Tests adapted (pinned the Slice 1b row):** `test_app_lab_keys.py` (T-R2h parametrised over BLOCK/MARK and compared by `==`; T-R3 row `C_under_symmetry` → `C_under_symmetry_block` with the BLOCK text; `ShiftB_idle` "noch nicht verfügbar" → `ShiftB_transform_armed`; `ROW_SYMMETRY_ON` → `ROW_MARK`), `test_app_lab_bindings.py` (T-R1d: four rows via `gate_rows()`, BLOCK text instead of the 1b text, no "noch nicht verfügbar" left), `test_app_lab_preview.py` and `test_app_lab_resymmetrize.py` (closed-preview row via `gate_row_for(axis, mode)` and `==`; `ROW_SYMMETRY_ON` → `ROW_MARK`; the N2 assert test also tries `block_row()`), `test_app_lab_preview_window.py` and `test_run_app.py` (`ROW_SYMMETRY_ON` → `ROW_MARK`; the HUD-label test passes the mode and expects `E5: MARK`). **Then the Artist session:** Lab README „Gemeinsame Prüf-Session nach Slice 4" |
| **5** Swap and delete — **done 2026-10-03** | Gate first: the deleted-test → named-replacement table (A2; **step 0 done 2026-10-03**, § „A2 table — Slice 5, step 0"). `run.py` → app host; delete the (c) modules and their tests (§4.4); README rewritten (manual-test sections as history, new steps); ROADMAP §7 entry; W-like-app and Slice 7 marked superseded/moot | — | Lab tests ≈133 + new; no Lab module imports a deleted one; README legend matches the overlays. **Done (container, Xvfb + EGL; the Lab tests also without a display):** `experiments/symmetry_lab/tests` 524 → **324** = 524 − 216 deleted + 10 ported in Slice 5 (`test_app_lab_hover.py` 4, `test_app_lab_bindings.py` +2, `test_display_characterization.py` 4) + 6 (T-R4a now parametrised over 11 Lab modules instead of 5). Of the 271 old-Lab tests 55 are kept (topology 19, resymmetrize 8, knife P1–P3 12, symmetry 12, scene 2, import boundary 1, display 1), every one of the 216 deleted has its A2 row. `pytest tests --ignore=tests/test_extrude_tool.py` 1661 and `playground/tests` 1235 unchanged; `run.py --help` and `probe_drag_cost.py` OK. **As built:** `git mv run_app.py run.py` (old `run.py` removed, no shim), `tests/test_run_app.py` → `test_run.py`; renamed tests `test_app_lab_cycle::test_run_rejects_unknown_name_before_opening_a_window`, `::test_run_help_runs_without_a_window`, `test_app_lab_boundary::test_setup_calls_are_allowed_only_in_run`, `::test_run_uses_exactly_the_setup_exception`, `::test_lab_modules_cover_every_lab_file` (was `…_cover_every_new_file`). H2-R4 (f) / T-R4a `SETUP_MODULE` = `symmetry_lab.run` (AD-013: dated one-line note). E5: `GateMode` default BLOCK; Shift+B toggles to MARK; start-up listing `Default BLOCK`, the BLOCK row says `(Default; …)`. Moved: `plane_outline_data` → `lab_symmetry`, `ResymPreviewData`/`resym_preview_data` → `lab_resymmetrize`. Deleted modules: `lab_window`, `lab_render`, `lab_dispatch`, `lab_draw_data` (incl. `triangulate_face_symmetric`, Q1 = (a)), `lab_knife`, `lab_knife_pick`, `lab_knife_preview`, `lab_status`; deleted functions only the old path used: `lab_symmetry.cycle_symmetry`, `lab_resymmetrize.apply_plan` (both pushed history themselves, H2-R4), `lab_bindings.apply_lab_bindings` and the Orbit/Pan/RMB/MMB/C → Knife overrides (`LAB_OVERRIDES` = the three keys). Kept: `lab_scene` (`run.py` uses the name check; `load_asset_into` serves the research tests only). T-R4a and T-R4b (`LAB_MODULES` in `tests/_app_lab_support.py`) cover every Lab module, checked by `test_lab_modules_cover_every_lab_file`; `test_import_boundary` names the exact module list and the deleted ones. **Deviations:** (1) the old files held 271 tests, not 263 (`test_input_path.py` 16, not 8); (2) 7 pure resymmetrize tests (+1 made pure), not 17 — Slice 3 had already found that; (3) `test_lab_symmetry.py` keeps 12 pure tests and `test_lab_scene.py` 2, not "port 3 / port 7": their other cases were ported in 1b; (4) `test_app_lab_preview.py::test_preview_colours_are_the_old_renderers` read the colours from `lab_render.py` by AST; it now pins them (values at `065508c`); (5) T-R4a also widened to every module (the brief named T-R4b) — clean, because `cycle_symmetry`/`apply_plan` went. **Tests adapted for the BLOCK default:** `test_app_lab_gate.py` (fixture `symmetric` asserts the BLOCK default and switches to MARK via Shift+B, helper `set_mode`; `test_shift_b_toggles_without_history_or_mesh_change`, `test_hud_shows_the_mode_only_while_symmetry_is_on`, `test_c_with_symmetry_off_runs_in_both_modes`, `test_startup_listing_has_the_e5_rows_and_shift_b`), `test_app_lab_gate_window.py` (both), `test_app_lab_keys.py` (T-R2h, T-R3 row `C_under_symmetry_block`, `test_gate_is_not_reinstalled_while_a_transform_owns_the_keys`), `test_app_lab_preview.py::test_ctrl_z_restores_mesh_and_selection_then_redo`, `test_app_lab_preview_window.py::test_every_branch_returns_event_handled`, `test_app_lab_resymmetrize.py::test_rejected_while_move_armed_or_dragging`, `test_run.py` (`test_one_key_event_through_lab_key_press`, `test_hud_label_text_is_the_full_lab_line`) |

**Not in any slice:** the mirrored Knife (a future symmetric One Knife is its own package:
mirror the virtual path before resolution, ROADMAP 2026-10-02 (b),
`docs/research/topology/ONE_KNIFE_PROMOTION_DISCOVERY.md`), partner previews in edge/face
mode, Extrude/Loop Insert, any Playground change, any new symmetry capability.

**Revert path:** Slices 1–4 add files and default-off hooks; reverting a slice restores the
previous state, and the old `run.py` keeps working until Slice 5. Slice 5 is only deletions
plus docs.

**Test command for later `src` changes:** once Slice 1 lands, changes to `mirai/application.py`
or `src/viewport/` should also run `pytest experiments/symmetry_lab/tests` (proposed CLAUDE.md
addition in Slice 1). The Lab then catches Production changes instead of drifting from them,
which is the point of the rebase.

---

## 6. Deliverable 5 — Open questions for the Artist (M4-filtered)

**Q1 (Product Truth / Priority) — symmetric shading of `subd_cube`.** In the Slice 4 KEEP
(step 10) the Lab split quads at the shorter diagonal, so `subd_cube` shaded the same left and
right. The rebased Lab draws with Production's split, which is asymmetric on `subd_cube` (24
of 24 mirrored quads) and identical on `head_basemesh` (0 of 324). Choose one:
(a) accept it in the Lab for now and raise it again when Symmetry is promoted;
(b) make "shorter diagonal" Production's quad split, a separate small package that changes
the shading of every quad in `src/main.py` (and its picking/face overlays, which use the same
split).
*Agent recommendation:* (a). The head, the main asset, is unaffected.
**Artist answer (Manu, 2026-10-03): (a)** — accepted in the Lab; raised again when Symmetry is promoted.
*Prepared test:* in the session after Slice 4,
`python experiments/symmetry_lab/run.py` vs. `python experiments/symmetry_lab/run_app.py`,
both `subd_cube`, Shift+S → X, orbit to compare the left and right shading.

**Not asked (decided by the agent under the filter):**

- the hook design and the H2 addendum: technical, reviewable;
- building next to the old Lab vs. in place: technical;
- the default asset (`subd_cube` stays, matching the README steps);
- the status language: German Lab texts stay;
- C refused in Slice 1: follows INV-8 (decided);
- E5 now covering C: re-hosting the existing gate onto the real tool set, E5 itself stays the
  Artist's question;
- whether W-like-app and Slice 7 need verdicts: recorded as superseded/moot, not as
  validated (M3: no agent claims validation).

---

## 7. Risks

- **R1 — the hook grows into a plugin system.** Guard: one gate value and one hover flag,
  written by one Lab, no callback into experiment code; documented as experiment-only in the
  AD-013 addendum (H2-R6, governance); a second user needs its own review.
- **R2 — Lab tests break on Production changes.** Intended: that is the signal the drift lacked
  (§5, test command).
- **R3 — cost per change.** `symmetry_report` 6 ms + `topology_report` 10 ms on
  `man_with_shoes` (container). It runs per change, not per frame; `topology_report` runs only
  while the Re-Symmetrize preview is open. This matches today's Lab; to re-measure on the
  reference PC if a drag feels slow.
- **R4 — the Slice 1 C refusal is visible only as a status line.** Accepted until Slice 4;
  the old Lab stays available for comparison.

---

## 8. Docs to update when the slices land

Lab README (structure, controls table, legend, manual-test sections; the old sections stay as
history), this plan (status per slice), AD-013 (addendum, Slice 1),
`src/main.py` docstring (H6), ROADMAP §7 (one dated entry per slice),
CLAUDE.md (Lab test command, Slice 1).
