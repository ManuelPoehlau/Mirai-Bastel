# Handoff — AD-SYM-03: selection residue follow-up (Part A) + slice 3c, symmetric Delete/Dissolve (Part B)

**To:** Claude Code
**Model/effort:** Sonnet 5, effort high. Raise to xhigh if it skips tests or leaves a half-done refactor; Opus 5.5 only
if it fails at understanding despite full context.
**Mode (M5):** Production. Decisions stand (AD-SYM-03 DECIDED, AD-013 H2 amendment G-2 DECIDED). BUILD must not claim
new insight: anything unexpected is reported, not decided.
**Type:** A (Implementation). Two logical commits at least: Part A, then Part B (code + tests; docs in the same commits). Report after each part.
**Baseline:** `main` @ `2e101c5` or later. Measure and record before/after, commands from CLAUDE.md:
`pytest tests --ignore=tests/test_extrude_tool.py`, `pytest experiments/symmetry_lab/tests`, `pytest playground/tests`.
(Reviewer's run after 3b: tests 1893 passed; Lab 376 passed. The 3b commit message says 1806 / 363; reconcile or note why.)

**Goal:** (A) After a coordinated Edge Connect, select the created edges on the side(s) the user had selected. (B) Delete,
Dissolve and Dissolve-no-cleanup run coordinated under symmetry (both sides, one Undo step) with the seam handling decided
in A1, and the accepted one-sided interim ends.

## Reference documents (binding, not to be renegotiated)
- `docs/architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md`: §2.3 (C-b, D-strict), §2.6 (seam table), §3 items 1–9, §4
  (O1, residue), §6 (A1/A2/A3 verdicts), §7 (slices 3, 5)
- `docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md`, H2 amendment 2026-10-08, esp. "Removal" (declarations per
  command, no mode-keyed refusal; G-9) and "Runtime refusals are not G-3"
- `docs/WP_DELETE_DISSOLVE_PLAN.md` (DD-1, DD-2), `src/mirai/topology/delete_dissolve.py` (`apply_removal`, `RemovalRefused`),
  `src/mirai/application.py` (`_removal_command`, `_REMOVAL_COMMANDS`, `_mesh_transaction`), `src/mirai/symmetric_ops.py`,
  `src/mirai/symmetry_coordination.py`, `src/mirai/symmetry_declarations.py`, `experiments/symmetry_lab/lab_app.py`

## Decisions
**Artist (Manu, 2026-10-08):**
- Practical check of slice 3b done, all steps "as expected" on his machine (Edge/Vertex Connect symmetric, one Undo; seam edge
  in a Connect selection; refusal next to unpaired geometry and symmetric result far from it; Split and Knife contexts refused
  under BLOCK with their texts; Delete/Dissolve still one-sided).
- Selection after symmetric Edge Connect: **ITERATE**. Wanted: the created edges on the side he worked on; if he deliberately
  selected both sides beforehand (his example: two edges left, their mirror partners right), the created edges of both sides,
  so he can continue with both (e.g. scale in X). Reason: after a move the other side follows through transform symmetry anyway.
- A1: Case 1 (delete a face pair at the seam) **M**: the seam disappears only where the adjacent faces are gone. Case 3
  (Extrude at the seam) **M** (not in Production, not touched). Case 2 (dissolve a seam edge) **UNKNOWN**.
- A3 = S for now (refuse next to unpaired geometry, D-strict). A2 = A. Accepted interim until now: Delete/Dissolve one-sided.
**Engineering (set in this handoff, not Artist decisions):**
- Residue rule (Part A, assumption, not confirmed by Manu): created edges are selected on the side(s) where the **live**
  selection (before canonicalisation) has elements; only the plane → the normal's side (+X). Created edges that are their own
  mirror stay selected. Side of a created edge = side of its vertices relative to the plane, using existing helpers, no
  tolerance. Implement as one small shared helper (also used in Part B).
- Case 2 interim rule: **R** (refuse visibly, mesh/history/selection unchanged) until Manu decides. Implemented through the
  delta check (new self-mirrored face or new dead seam id on a Dissolve) with its own text.
- Part B seam handling (assumption, not confirmed beyond Case 1 in Face mode): for **Delete** in every component mode, seam
  edge ids that no longer exist after the removal are dropped from the definition inside the same transaction (M); the delta
  check stays the guard (refuses if survivors become incomplete). For **Dissolve** (all variants) any new self-mirrored face
  or dead seam id is refused (R). Part B ends owner check O1 as follows: seam cases move from "one-sided" to "coordinated
  (Delete) / refused (Dissolve)".
- Residue in Part B (assumption): as today (clear), except Face Dissolve, which selects the merged faces on the side(s) of the
  live selection (same helper).

## Scope
**Part A — Edge Connect residue** (`Application._connect_command` / `symmetric_ops`, symmetric path only):
1. Apply the residue rule above. No definition → unchanged (all created edges). Vertex Connect untouched.
2. Selection-mirror invariants unchanged (one entry per push, `before` taken before the transaction).
3. Tests: live selection only +X → only +X created edges; only −X → only −X; both sides → created edges of both sides; only
   plane → +X; seam-edge case; no definition unchanged; Undo restores the previous selection; refused press leaves selection untouched.
4. Docs: AD-SYM-03 §6 dated block "3b practical check (Manu, 2026-10-08)" (observations and verdicts above, as Artist
   statements); §4 "Residue under symmetry" answered for Edge Connect (Split open until slice 4); Lab README residue text.

**Part B — 3c, coordinated removal:**
1. **Coordinator** in `symmetric_ops.py`: `coordinate_removal(mesh, mode, ids, *, dissolve, cleanup)` as a pure mutation raising
   `SymmetryRefusal`. Steps: exact-plane predicate (else refuse); expand `ids` per mode with partners (`expand_vertices/edges/faces`,
   seam self-partners once); refuse if any selected element has no partner (`Expansion.unpaired`); in vertex and edge mode refuse
   if `both_sides_faces(..., mode=...)` is non-empty (face mode: rely on the delta check); `completeness_report` before; call the
   unchanged `apply_removal` once on the union; for Delete drop dead seam ids from the definition (rule above), for Dissolve leave
   them; `completeness_report` after; `delta_check` (D-strict) → refuse. A Dissolve violation about a new self-mirrored face or
   dead seam id gets its own text (seam Dissolve not supported yet); other violations use the existing delta text.
2. **Application wiring:** `_removal_command`: with a definition set and the command declared, run the coordinator inside the
   one `_mesh_transaction`; `RemovalRefused` keeps its existing texts, `SymmetryRefusal` posts its text, returns False, no history,
   mesh and selection unchanged. No definition → unchanged path. Keep the existing "nothing selected" and "no variant in Vertex mode" texts.
3. **Declarations:** fill `REMOVAL_COORDINATORS` for `Delete`, `Dissolve`, `DissolveNoCleanup` (per command, all three modes). If a
   command cannot be coordinated in every component mode: do not declare it, report (amendment "Removal", G-9). Update the module docstring.
4. **Lab:** remove `INTERIM_ONE_SIDED` and everything that prints or tests it; rows derive from declarations as built in 3a. BLOCK
   now allows the three removal commands; MARK unchanged. Start-up listing and Lab README updated.
5. **Tests:** coordinated Delete/Dissolve/DissolveNoCleanup in each mode on `subd_cube` and `head_basemesh`: one Undo step, report
   clean, Undo/Redo restore mesh, definition and selection; Delete of a face pair at the seam (Case 1): dead seam ids dropped,
   state `valid`, Undo restores the old seam; Delete of a seam edge and of a seam vertex (assumption cases) behave as M or are
   refused by the delta check, never silently one-sided; Dissolve of a seam edge refused with the seam text, nothing changed (Case 2);
   unpaired selection refused; next to unpaired geometry (`man_with_shoes_basemesh`) refused, far away symmetric; non-exact
   plane refused; both-sides face refused (build it by dissolving a seam edge programmatically); no definition unchanged; MARK
   runs coordinated like BLOCK; Lab BLOCK row allows removal, `INTERIM_ONE_SIDED` gone; `lab_key_press` end-to-end for each
   command. Adapt existing tests that encoded the interim (they must now expect coordinated behaviour, not one-sided).
6. **Docs (same commit):** AD-SYM-03 §7 (3a/3b verified, 3c done, date, counts), §4 (O1 answered as above), §6 A1 (implemented
   status: Case 1 M implemented for Delete, Case 2 R interim, Case 3 not in Production); AD-013 amendment note (removal
   declarations filled, interim ended); `docs/WP_DELETE_DISSOLVE_PLAN.md` (DD-2 closed); `experiments/symmetry_lab/README.md`
   (what runs symmetric, refusal texts, interim ended); `docs/ATELIER.md` (Delete/Dissolve symmetric in the Lab; open Artist
   questions: A1 Case 2, residue after symmetric Face Dissolve is an engineering default).

## Not in scope
Split (slice 4), Knife and snap X-a (slice 6), Extrude, seam consumption for Dissolve beyond refusing (Case 2 stays UNKNOWN),
D-source, `SymmetryState` changes (C-a), non-exact planes beyond refusing, mode-keyed refusals (G-9), `src/core`, `src/main.py`,
`playground/`, new Markdown files, new key bindings. If something seems to need one of these: stop and report.

## Architecture contracts and constraints
No `SymmetricX` copies; one commit boundary per key press in `Application`; coordinators push nothing; runtime refusals act
in MARK and BLOCK; refusals never read the gate or E5 mode; Lab code may not call `resolve_c_context` or `canonical_*`;
guards T-G3b and T-R4a+ stay green.

## Tests
Suites as in Baseline; counts must not drop; report before/after per suite and per part. `application.py` changes require the Lab tests.

## Practical test for Manu (Deutsch, ca. 15 Minuten, Windows)
Vorher `git pull`, beim Start muss die Regelliste erscheinen und **ohne** `INTERIM_ONE_SIDED` sein.
`python experiments/symmetry_lab/run.py head_basemesh`, **Shift+S** → X, Standardmodus BLOCK.
**Teil A (Auswahl nach Edge Connect):**
1. Edge-Modus (2), auf der rechten Seite ein Quad, zwei gegenüberliegende Kanten, **C**. Nur die neue Kante auf deiner Seite ist ausgewählt, beide Seiten sind geschnitten. **W** halten und ziehen: beide Seiten bewegen sich. **Ctrl+Z** zweimal.
2. Dasselbe links: wieder nur die Kante auf deiner Seite.
3. Bewusst beide Seiten wählen (Partner im Vertex-Modus an den türkisen Punkten prüfen), **C**: neue Kanten beider Seiten ausgewählt.
**Teil B (Löschen und Auflösen):**
4. Face-Modus (3), ein Face auf einer Seite weit weg von der Naht, **Entf**: es verschwindet auf beiden Seiten, HUD `valid`, **Ctrl+Z** = ein Schritt.
5. Edge-Modus (2), eine Kante auf einer Seite, **Rücktaste** (Dissolve): beide Seiten lösen sich auf. **Ctrl+Z.** Dasselbe mit **Ctrl+Rücktaste**. Im Vertex-Modus (1) **Rücktaste**: beide Seiten. **Ctrl+Z.**
6. **Naht, Delete (dein A1 Fall 1):** Face-Modus, ein Face an der Naht und mit Shift+Klick das Face auf der anderen Seite derselben Seam-Kante (zwischen zwei grünen Punkten), **Entf**: beide weg, HUD bleibt `valid`, **Ctrl+Z** stellt die Naht wieder her.
7. **Naht, Dissolve (dein A1 Fall 2, noch UNKNOWN):** Edge-Modus, eine Seam-Kante, **Rücktaste**: wird verweigert mit Hinweis, nichts ändert sich.
8. `man_with_shoes_basemesh`, Shift+S → X: Löschen direkt neben Magenta wird verweigert, weit weg läuft symmetrisch.
9. **Shift+B** (MARK): Schritt 4 wiederholen, gleiches Ergebnis. Symmetrie aus (Shift+S bis aus): Löschen läuft einseitig wie früher.
Fragen an dich: (a) Auswahl nach Face Dissolve (verschmolzene Faces auf deiner Seite) KEEP / ITERATE / UNKNOWN? (b) Fall 2 (Seam-Kante auflösen): bleibt es erst einmal Verweigerung?

## Definition of Done
Part A and Part B implemented and tested as above; interim removed from Lab; declarations filled; refusals leave
mesh/history/selection unchanged; one Undo step per press; named tests present and green; `src/core` and `src/main.py`
untouched; docs updated; counts reported per part.

## On contradiction
If a removal command cannot be coordinated in every mode, the delta check cannot distinguish an expected dead seam id from
a violation without a tolerance, or the docs and code disagree, stop and report in one sentence before continuing.
Report only what exists, was tested and passed.