# Knife Face Cut Lab — Artist Verdict

**Status:** Discovery (built, not yet played) — see the Claude Code handoff (not committed) and
`docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md` (archived first impression, Q1–Q5, §7 Lab
options, §8 prepared Artist test — this file copies and updates that section for the two variants
actually built, B and D; C and A were dropped per the handoff's scope §2).
**Background:** `docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md`, `docs/architecture/
AD-017_FINAL_DECISIONS_2026-09-22.md` (session model, history, Esc, commit — reused unchanged).
**Controls:** `Tab` until `knife_face` is focused → `M` switches the variant (HUD: `Setting: … knife_face=…`).
Empty selection, `C` = start a session. Click vertices, edges, or (this lab only) face interiors.
`Enter` or click outside = commit. `Esc` = cancel (mesh restored, no history entry). `Ctrl+Z` = in-session
undo of the last step (a pending interior point, or a whole cut in Variant B); `Ctrl+Y` / `Ctrl+Shift+Z` =
redo. Zoom in so a face is large on screen — an interior click needs ≥ 9px clearance from every edge of
its face, or it is rejected (too small to place a point).

**Selection after commit (lab default, not a UX decision):** the new/kept edges along the cut are
selected in Edge mode after commit — same residue rule as Production Knife.

Start: `python playground/run.py grid` (flat 8×8-quad grid) or `python playground/run.py head`.

---

## The two variants

| | B — Immediate (control) | D — Collected (applied at commit) |
|---|---|---|
| Interior clicks | pending inside the *current* face; the whole path (start → interior* → boundary) applies the moment it reaches a vertex/edge of that face | never mutate the mesh — every click (vertex, edge, face) only extends a virtual path |
| Interior **start** | not allowed (rejected, HUD note) | allowed |
| Mesh changes | per completed segment, during the session | only at commit (Enter, click outside, or clicking back on the first point) |
| Closed shape (a loop entirely inside one face) | not supported | supported (≥ 3 interior points, no boundary touch) — bridged to the boundary with 2 edges, lab default rule, see below |

**Closed-shape stand-in (D only):** the lab bridges a closed interior loop to the face boundary with
**2 edges** — the loop itself becomes its own face, plus 2 "wing" faces between the loop and the
original boundary (**3 faces from 1**, e.g. a triangle loop in a quad → 3 faces total). Which 2 loop
points bridge to which boundary vertices is a **lab default, not a UX decision**: the 2 loop points
nearest a distinct boundary vertex each (world-space nearest, not screen-space — the engine has no
camera), excluding loop-adjacent pairs when the loop has more than 3 points. This is **not** what Silo
is presumed to do (§1 of the discovery doc: a ring-with-hole, which Mirai's Core cannot represent — one
boundary list per face, no holes) — compare deliberately, this is a different, coarser result.

---

## Tasks (same four as the discovery doc's prepared test, §8 — copied here, B/C's slots below updated
for the two variants actually built; task 5 is new for this lab)

1. **Grid — bent cut through one quad:** click an edge of a quad, click once inside the quad, finish on
   the opposite edge. Commit.
2. **Grid — notch:** from one edge of a quad into the quad and back out through the same edge (a V). Commit.
3. **Grid — start inside:** first click inside a quad, then continue to edges. Commit with `Enter`.
4. **Head — cheek:** from an edge, two points inside one cheek quad, out through another edge of it; then
   try to continue by clicking inside the neighbouring quad. Watch the line while moving over both quads.
5. **Grid — closed shape:** three clicks inside one quad, `Enter` (D) — then compare with what you
   remember from Silo.

**Expected, not a verdict on the variant** (updated for B/D — the discovery doc's own §8 "Expected"
paragraph describes the earlier A/B/C variants, not these):

- Task 1, 2: both variants cut, in one history step.
- Task 3: **B** rejects the first (interior) click outright — no session state changes, HUD explains why.
  **D** accepts the interior click, but "continue to edges" only produces a cut if the path *also* returns
  to close the loop (task 5's shape) or reaches a **second** boundary point after the first — a single
  interior start followed by exactly one edge/vertex click has no second anchor to cut between, so `Enter`
  drops the interior point and leaves the mesh unchanged (same class as a dangling tail, HUD note). This
  was found live (not assumed) while building — see Observations.
- Task 4: both variants cut inside the cheek quad. Continuing into the *neighbouring* quad's interior is
  not blocked by construction (once the cut reaches a shared vertex, that vertex sits on the neighbour's
  boundary too, so a fresh interior click there is a *new* face-local run, not a same-segment crossing —
  Q5 cross-face segments, which are genuinely out of scope, are about one click-to-click segment spanning
  two faces, not this). Whether the line/preview makes this legible, or reads as "it kept going" without
  the Artist expecting it, is exactly what this task asks Manu to notice.
- Task 5: **D** only (B has no closed-shape support at all — the family doesn't offer it, `M` still only
  toggles between B and D). Produces 3 faces from 1, per the stand-in rule above.

---

## Verdict

### B — Immediate (control)

**Verdict:** _KEEP / ITERATE / REJECT / UNKNOWN_

### D — Collected (applied at commit)

**Verdict:** _KEEP / ITERATE / REJECT / UNKNOWN_

---

## Observations outside the question

_(incidental evidence — raises priority of other questions, does not decide them)_

- The lab's own build turned up a case the discovery doc's Q2/§2 table doesn't name explicitly: an
  **interior start that touches only one further boundary point** (D) has no second anchor — `split_face_path`
  needs two distinct boundary vertices, and an interior point can never be one. Handled the same way as a
  dangling tail (dropped, HUD note, mesh unchanged for that part of the path) rather than left to crash or
  silently misbehave — but this is a *build-time* finding, not an Artist-tested one; flagging it here rather
  than deciding quietly it's "obviously" the right call.
- The closed-shape bridge rule (2 edges, "3 faces from 1") is a lab default picked to make *some* result
  exist to react to — not a claim that it is the *right* shape. Compare it explicitly against the Silo
  memory in task 5.
- H3 (discovery doc): a face too small on screen has no room for an interior click (< 9px from every
  edge) — worth noting whether this came up unprompted during the grid tasks (small faces) vs. only on
  the head asset's smaller cheek/eye-area quads.
- H2 (discovery doc, non-planar `head` quads): the lab computes the interior hit on the same
  fan-triangulation `pick_face` already used to select the face — so a hit on a non-planar quad lands
  wherever that triangulation puts it, not necessarily where it visually looks centered. Note whether this
  was visible on the head asset.
