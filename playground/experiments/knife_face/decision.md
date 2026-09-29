# Knife Face Cut Lab — Artist Verdict

**Status:** Discovery — played, verdicts recorded 2026-09-29 — see the Claude Code handoff (not committed) and
`docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md` (archived first impression, Q1–Q5, §7 Lab
options, §8 prepared Artist test — this file copies and updates that section for the two variants
actually built, B and D; C and A were dropped per the handoff's scope §2).
**Q5 (cross-face segments, 2026-09-29):** a third variant, **Q5**, is built on top of D — see "Q5 — Cross-Face" below
(Artist answers, what was built, lab defaults, adapted test, verdicts). Background:
`docs/research/topology/KNIFE_CROSS_FACE_DISCOVERY.md` (archived, not edited).
**Background:** `docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md`, `docs/architecture/
AD-017_FINAL_DECISIONS_2026-09-22.md` (session model, history, Esc, commit — reused unchanged).
**Controls:** `Tab` until `knife_face` is focused → `M` cycles the variants **B → D → Q5** (HUD: `Setting: … knife_face=…`).
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
  *Clarification (2026-09-29, documentation only):* "reaches a second boundary point" means a cut
  **between the boundary points**. Every interior point *before the first boundary click* is dropped, never
  used as a mid-path point — so `interior → boundary → boundary` cuts boundary-to-boundary as a straight
  connect and the interior click has no effect. Only interior points *between* two boundary clicks bend a
  cut (`boundary → interior → boundary`).
- Task 4: both variants cut inside the cheek quad. Continuing straight into the *neighbouring* quad's
  interior right after that (no line, click rejected, HUD note) is a **known limitation, not a bug** —
  cross-face cutting (seeing the line continue into the neighbour face and having the click cut through
  both, Blender-like) is a required *later* capability (discovery Q5) deliberately left out of this lab so
  it does not confound the Face Cut verdict (Manu, A5, 2026-09-28). A plain vertex/edge click (no interior
  point) *does* still open the neighbour face up for its own, separate interior cut afterwards — only the
  direct "cut → interior click in the next face" jump is blocked.
- Task 4 addendum: watch specifically for the *moment* the neighbour face's interior click gets rejected
  right after finishing the cheek cut — that is the one line/point this lab intentionally never shows,
  per A5.
- Task 5: **D** only (B has no closed-shape support at all — the family doesn't offer it, `M` still only
  toggles between B and D). Produces 3 faces from 1, per the stand-in rule above.

---

## Verdict

### B — Immediate (control)

**Verdict:** **REJECT** (Artist, 2026-09-29)

**Reason:** structurally cannot start inside a face and cannot produce a closed shape — covers only 2 of
the 4 required shapes (bent cut, notch, closed shape, interior start).

### D — Collected (applied at commit)

**Verdict:** **KEEP** (Artist, 2026-09-29)

**Reason:** produces all four required shapes.

**Known, accepted gaps** (not blockers, noted for later):

1. Closing by clicking the start point only works for pure interior shapes (e.g. a triangle), not for
   shapes cut across several edges — `path[0]` must be of kind `face`; the boundary-start case was never
   built.
2. No hover feedback that the cursor is inside the 14 px close zone — a hit zone without preview, not real
   snapping.
3. In-session Undo/Redo acts on the virtual click list, not on real mesh cuts (nothing is applied before
   commit). Deviates from AD-017's "undo = last cut" model; accepted for the Lab.
   *Update 2026-09-29:* now an **Artist requirement for the Production Knife**: visible behaviour as in
   "Artist decisions after Q5" (3) — in-session undo takes back the last cut, one Undo after commit reverts
   the whole session; **implementation open** (real cuts or virtual list). Not an AD-017 change here (AD-017 files are not edited).
4. Bridges instead of a hole for closed shapes (Silo presumably different, see
   `docs/research/topology/FACE_HOLES_DISCOVERY.md`) — **Face Holes set aside (Artist, 2026-09-29); H0 bridges
   for now.** The click-order/direction defect of the bridges is Task A.

---

---

# Q5 — Cross-Face (Variant Q5, built on D)

**Status:** Discovery Lab — built 2026-09-29; first play test 2026-09-29 (tasks 1–5 as expected, task 6 led to the close-and-continue change, see "Artist play-test observations" below). **Verdict: Q5 = KEEP (Artist, 2026-09-29, after `5c777a0`); D = superseded by Q5, not judged separately.** KEEP is a Lab verdict, **not a promotion** — see "Artist decisions after Q5". Follow-ups from those decisions are open: bridges independent of click order/direction (Task A), click on an earlier cut point (Task B).
**Background:** `docs/research/topology/KNIFE_CROSS_FACE_DISCOVERY.md` (archived — §2 planners, §3 camera finding,
§4 cases, §5 closed loops, §6 preview / A5 lock, §8 lab options). No Core change, no Production change: everything
below is Playground-only (`playground/experiments/knife_face/`: `planner.py`, `engine_q5.py`, `variant_q5.py`,
plus the knife_face paths of `playground/window.py`).
**One Knife:** Knife and Knife Face become **one** Production tool later. Q5 is one more variant of the existing
`knife_face` family — no new family, no structure that assumes two tools. D stays the control, B stays in the family
unchanged (REJECT, kept for reference).

## Q5 — Artist answers (2026-09-29)

This is the authoritative home of these answers (the archived discovery is not edited).

| Question | Answer (Manu) | Consequence for the Lab |
|---|---|---|
| A-Q1 — line over hole / border / silhouette / hidden stretch | **Like Blender: the visible part is cut**, the rest skipped | Discovery option Q5-b. Q5-a (refuse) is **not built**. |
| A-Q2 — visible only or cut-through | **Visible only for now.** Cut Through maybe later as an extra option, like Blender | No cut-through. Future idea recorded in `docs/future_ideas/MODELING.md`. |
| A-Q3 — closed shapes across faces | **Yes: snap to the start point, click closes the shape, but you can keep cutting — only commit ends the session.** Correction: the snap always engages near **any** vertex, not only the start point | Close ≠ commit (changes today's D close-on-start in this variant). Snap feedback required. Covers D gaps 1 and 2 in this variant. |
| Assumption (not contradicted) | One segment may cross **any number** of faces | Planner is not limited to the neighbour face. |

*"You can keep cutting" (A-Q3) is read as: the next cut continues from the closing vertex — see "Artist play-test observations (2026-09-29)". An earlier build read it as "a new, independent chain"; that was a spec reading, not an Artist statement.*

## Variants for this test: D (control) and Q5

| | D — Collected (control, unchanged) | Q5 — Cross-Face (D + planner) |
|---|---|---|
| Target outside the last point's faces | rejected — no line, click refused ("Hangeln": click every intermediate edge) | a planner turns it into the visible crossings in between; **one click = one segment across any number of faces** |
| Line that cannot be cut everywhere (hole, mesh border, silhouette, hidden stretch) | — | **visible pieces are cut, the gaps are skipped**, the click is accepted, the HUD names what was skipped; skipped stretch drawn in a distinct "no cut" style (grey-blue) |
| Camera | picking only | crossings fixed **at click time with that click's camera**, stored in the path; orbiting between clicks or before commit never changes them |
| Snap | 14 px zone around the start point only, no feedback | within **14 px of any vertex** (mesh vertex or one of your own clicked points) the point jumps onto it; one cyan highlight for both |
| Close | click on the start (interior start only) **commits**, cuts only part of a cross-face loop | click on the snapped start point (chain ≥ 3 points) **closes** the chain, loop resolved cyclically (no bridges across faces); **session continues**: the new chain is **seeded with the closing vertex**, so the next click draws a segment *from that vertex* (through the planner, like from any last point). The loop and the seeded chain are separated by a break — no run crosses the closed loop. Only commit ends the session |
| A5 lock (no interior click in the neighbour face right after a cut) | active | **off** |
| In-session undo | one step per click | one step per click **including all its crossings**; the closing click is one step **including the seeding** (undo removes close and seed, redo restores both) |
| Preview | line through the stored path + hover point | line through stored crossings + pending segment through its planned crossings, **crossing dots**, skipped stretch, snap highlight |
| Commit | Enter | Enter (unchanged; see "click outside" note in Observations) |

**Controls (Q5):** `Tab` until `knife_face`, `M` until Q5 (HUD names it), `C` with an empty selection. Click vertices, edges,
face interiors (≥ 9 px from every edge, as in D). Yellow dots = planned/stored crossings, cyan square = snap, grey-blue
line = skipped stretch. `Ctrl+Z` / `Ctrl+Y` = in-session undo/redo, `Enter` = commit, `Esc` = cancel.

**Lab defaults (flagged — not decisions; each one is untested and open to change):**

1. **Planner: WALK first, PLANE only when needed.** WALK (walk face to face along the 2D screen line, Wings-like) is used
   whenever it reaches the target without crossing a hidden surface; otherwise PLANE (every edge against the plane through
   eye/A/B, only **visible** hits kept, B8 occlusion test, Blender-like). Where both succeed they cut identically
   (discovery §2.2). Cost on `head` (324 quads, 150 random segments of 40–220 px): with the app's shared pick cache
   **0.44 ms mean / 2.8 ms max** per plan (147 walk, 3 plane); WALK alone 0.14 ms; PLANE alone 1.1 ms mean / 2.9 ms max.
   Without the cache (headless only) 9.7 ms mean / 51 ms max — the per-crossing occlusion test dominates. Hover stays
   responsive with the cache; the window always passes it.
2. **Vertex tolerance 0.5 px** (Blender's constant, discovery §4): a crossing that close to a vertex becomes a vertex hit.
3. **Crossings on an existing edge-collinear stretch are skipped, not refused** (Blender skips them): the click is accepted,
   a "no cut" break is stored, the HUD says "along an existing edge".
4. **Pieces:** the visible crossings form face-connected pieces; every piece is cut; a face that gets only one point from a
   piece is not cut (Blender's "≥ 2 hits" rule); a piece ends at its **last visible crossing** (on curved surfaces this is
   where a piece "ends" next to a gap — open point, see below).
5. **Gaps are path breaks** (`{"kind": "break"}` entries): D's resolver assumes consecutive points share a face, so runs are
   never connected across a gap or across a closed chain. The resolver change is additive: `KnifeFaceCollected` is
   untouched, Q5 subclasses it; D's behaviour on paths without breaks is what the unchanged D tests prove.
6. **Snap:** the nearer of (picked mesh vertex, own clicked point) wins. The chain's **last** point, **crossings** and
   points hidden behind the surface are not snap targets. A snapped earlier point that is **not** the current chain's start
   (an earlier point of this chain, or a point of an already closed chain other than the closing vertex) shows the snap but
   the click is **rejected** with the HUD note "connecting to earlier cut points not supported yet". What that click
   *should* do: Artist decision 2026-09-29 (connect and continue) — **to be built (Task B)**; this rejection is the state before that change. Right after a close the closed chain's start *is* the new chain's seed, i.e. its last point:
   clicking it is rejected as "already the last point"; once the new chain has ≥ 3 clicked points (seed included), a click
   on it closes that chain again.
7. **Closing across a gap:** if the chain or the closing segment contains a skipped stretch, the loop cannot be resolved
   cyclically; the click still ends the chain but its pieces are cut as open pieces (HUD says so). Here the chain's last
   point *is* the start point again (the closing segment ends on it), so "seed from the last point" and "seed from the
   closing vertex" are the same point: the next chain is seeded with it exactly as after a cyclic close.
7a. **Seed after a close (Artist play test 2026-09-29):** the new chain's first point is the closing vertex — stored as the
   *same* path entry again behind the `closed` break (never a copy), so commit resolves loop and continuation to **one**
   vertex (boundary points are resolved once per entry). Per kind of start point:
   - **existing mesh vertex:** the continuation starts at that vertex; no new vertex.
   - **edge crossing:** the edge is split once; the loop and the continuation both attach to that one new vertex — no double
     `split_edge` on the same edge/t, no zero-length edge.
   - **interior (virtual) point:** it has no vertex before commit. The seeded chain is anchored on the vertex that the closed
     chain's own cut creates at that position; that continuation is applied after the closed chain (and after D's
     closed-shape stand-in, when the start belongs to an all-interior loop). If no cut created a vertex there, the
     continuation is dropped with a HUD note. A continuation that stays entirely inside faces (no boundary reached) is
     dropped like any dangling tail.
   - a chain holding nothing but its seed (close, then commit at once) has no cut and no HUD note — identical to before.
8. **Interior-only chains (D parity):** three or more clicks in one face still form D's 2-bridge closed shape — closed by
   clicking the start or (unclosed) at commit. Face Holes stays a separate topic.
9. **Same-face links use no planner** (D parity): D's "no geometric in-face check" (a chord across a concave face's notch is
   accepted) is inherited unchanged.

## Q5 — Artist test (≤ 5 min per variant; adapted from discovery §8)

Start: `python playground/run.py grid` (flat 8×8 quads) and `python playground/run.py head`.
`Tab` until `knife_face` is focused; `M` selects the variant: **D (control)**, **Q5**. `C` with an empty selection starts the
Knife. `Enter` = commit, `Esc` = cancel, `Ctrl+Z` / `Ctrl+Y` = in-session undo / redo (one click = one step, crossings
included). Zoom in so faces are large (interior clicks need ≥ 9 px clearance from every edge).

1. **Grid — straight across:** click an edge of a quad, move the cursor over two more quads (watch line and dots), click the
   far edge of the third. Commit.
2. **Grid — interior through the neighbour:** click an edge, click inside the quad, click inside the *neighbouring* quad,
   finish on an edge of that quad. Commit.
3. **Grid — start inside, cross over:** first click inside a quad, then inside the next quad, then an edge of it. Commit.
4. **Head — across the cheek, then over the nose:** from an edge on one cheek, click 3–4 quads away on the same cheek; then
   aim at the other cheek so the line passes the nose silhouette. Commit.
5. **Head — orbit between clicks:** click a point, orbit ~25° (`Alt`+drag), click the target (the line seen now is the cut).
   Orbit again, commit and compare with what the line showed.
6. **Grid — closed loop over 4 quads:** four interior clicks in the four quads around one vertex, then click the first point
   again (move the cursor near it first: the snap highlight shows). Then **continue cutting from the closing vertex** to an
   edge (one more click; watch the line start at the closing vertex). Commit.

**Expected, not a verdict on the variant:**

- **Task 1:** D refuses the far click (no line) — with D you click every intermediate edge instead. **Q5** cuts all three
  quads in one click, one history entry.
- **Task 2:** D refuses the neighbour-quad click (an interior click must stay in the previous interior point's face). **Q5** cuts both quads (the path is anchored on edges at both ends).
- **Task 3:** D refuses the second click. **Q5**: the first quad is **not** cut — the interior start has no second anchor
  (D's FC5 rule, unchanged); the neighbour quad is cut.
- **Task 4:** D refuses. **Q5** cuts the **visible** part; the HUD names what was skipped ("skipped: over a hole, border or
  hidden part", "N hidden crossing(s) not cut"), the skipped stretch is drawn in the "no cut" style.
- **Task 5:** the cut follows the line seen at the second click, not the view at commit.
- **Task 6:** D cannot place the second point (it lies in another face) — the loop cannot even be built. **Q5**: the click
  on the start **closes** all 4 quads **without bridges** and the session **continues**; the next click draws a segment from
  the closing vertex to the edge (through the planner, crossings included), while nothing runs across the closed loop;
  `Enter` commits everything as one history entry, the closing vertex being one vertex. Also try `Ctrl+Z` right after the
  closing click (one step: close and seed go together) and clicking an earlier point that is not the start (snap shows,
  click rejected with a note).

**Observe:** does line + dots read as "this is what will be cut"? Is cutting the visible part and skipping the rest (the
Blender behaviour Manu asked for) what happens on the nose? Does the snap highlight make closing predictable? Does the
rejected "earlier point" click feel wrong (what should it do)? How many attempts per task, where does frustration appear?

## Q5 — Verdict

### D — control (cross-face test)

**Verdict:** **Superseded by Q5 — not judged separately** (Artist, 2026-09-29: D is "really only the older version of Knife Face"; Q5 = D + planner supersedes it).

**Reason:** Q5 contains D's session and resolver unchanged and adds the planner on top; a separate D verdict would judge the same thing twice. D's earlier verdict (KEEP, "The two variants" above) stands as history.

### Q5 — Cross-Face

**Verdict:** **KEEP** (Artist, 2026-09-29)

**Reason:** tasks 1–5 worked as expected in the first play test; the task 6 deviation (a new cut after a close was not connected to the closing vertex) was fixed in `5c777a0`, and the verdict followed the fix.

**Not a promotion:** KEEP is a **Lab verdict** only. No `src/` change, no Production structure. The one-Knife requirement is unchanged: Knife and Knife Face become **one** Production tool later; Q5 stays a variant of the `knife_face` family until that is decided explicitly (with docs, per the repository workflow).

**Open points (record, do not decide):**

- What a click on a snapped earlier path point (not the chain's start) should do — **Artist decision 2026-09-29: connect to it and continue from it** (see "Artist decisions after Q5"); **to be built (Task B)**. Lab default until then: snap shown, click rejected.
- Whether a shared **interior** start point behaves sensibly when the continued chain cuts the same face again. Seen while
  building (grid, vertex start): a continuation from the closing vertex whose chord crosses the loop's own cut inside one
  face cannot be connected in the already split face — that run is dropped ("N-1/N cut(s) applied"). Untested by the Artist.
- Where exactly a piece "ends" next to a gap on curved surfaces (lab default: last visible crossing).
- Anything in the Blender-like behaviour that feels wrong while playing → Observations below.
- Face Holes: **set aside** (Artist, 2026-09-29); H0 bridges for now. Known defect (click-order dependent winding, `FACE_HOLES_DISCOVERY.md` §6) → Task A.
- Production Knife: real cuts vs. virtual click list is an **implementation choice**; the visible behaviour is fixed by Artist decision (3) below.

---

## Artist decisions after Q5 (2026-09-29)

_Statements 1–3 are Manu's, recorded in meaning. The two interpretations below them are **interpretations** (Context Check) — Manu corrects them only if wrong._

1. **Face Holes: set aside.** For now use the **Blender solution: bridges** (= H0). No H1/H2/H5 work. Problem to fix: depending on click order and/or direction, odd connections appear and the resulting "islands" cannot be edited properly.
2. **A click on an earlier cut point must not be rejected** (before: the snap shows, the click is refused with a HUD note).
3. **Undo:** inside a session it works like the normal Knife — **undo takes back the last cut**. After commit, **one Undo reverts the whole session.**
4. **Verdicts:** Q5 = KEEP (after `5c777a0`); D = no separate verdict (see above).

**Interpretations (not Artist statements):**

- (2): clicking an earlier point **connects the last point to it** (a segment through the planner) and the chain **continues from that point**, same as after a close. Closing on the chain start stays the special case that seals the loop.
- (3): a click that adds a segment (with all its crossings) is one in-session step — Q5 already behaves that way; commit = one history entry, so one Undo after commit reverts the whole session. Whether the Production Knife stores real cuts or a virtual list is an **implementation choice**, not an Artist matter, as long as this visible behaviour holds.

**Not a promotion, one Knife:** KEEP is a Lab verdict. Knife and Knife Face still become one Production tool; nothing here changes `src/`.

---

## Artist play-test observations (2026-09-29)

_(Manu, first Q5 play test — recorded in meaning, not a verdict; the verdicts were given afterwards, see "Q5 — Verdict".)_

- **Tasks 1–5:** "check" — worked as expected.
- **Task 6 (closed loop):** after closing, a new cut is **not connected to the last clicked vertex**. Read as (Context
  Check, Manu corrects only if wrong): after a close the last clicked vertex is the closing vertex (= the chain's start
  point), and the Artist expects the next cut to **continue from that vertex** instead of starting a disconnected chain —
  like continuing a Blender knife line after clicking an existing point.
- **Consequence built:** the closing click seeds the new chain with the closing vertex (lab default 7a). Unchanged: a click on
  the snapped start closes the shape without committing; only commit (`Enter`) ends the session.
- The earlier "independent chain after a close" behaviour was a spec reading of "you can keep cutting", never an Artist
  statement.

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
- **A5's exact mechanism is a build-time choice, not something Manu specified beyond "stays invalid, no
  line":** a face is locked out for a fresh interior click only for the *one* click right after an
  interior-involving cut resolves; any plain (no-interior) vertex/edge click clears the lock again,
  wherever it goes — including back toward the same neighbour face. This was picked so ordinary multi-quad
  chaining (already normal Knife behaviour, unrelated to Face Cut) stays free, while the specific "slide
  straight from one cut into the next face's interior" transition the discovery doc's own §8 flagged for
  the original Variant B ("the neighbour-quad click in task 4 is invalid by design") is blocked. Whether
  this specific unlock rule (one plain click, any direction) matches what Manu would expect is untested —
  flagging it rather than assuming it's obviously right.

### Q5 build-time findings (2026-09-29 — build-time, not Artist-tested)

- **Occluders are visible hits.** With the B8 occlusion filter on, a face that floats in front of the surface hides the
  crossings behind it *and* is itself cut where the line visibly crosses it (its own edges are visible PLANE hits) — the
  Blender-like reading of "visible part is cut". With occlusion off (Wireframe) the WALK follows the mesh's own
  connectivity and ignores unconnected geometry. Whether the in-front face should be cut is exactly what the head silhouette
  task will show.
- **A one-hit piece end still splits its edge.** A piece that ends on an edge (the next face gets no second hit) is not cut
  into that face, but D's resolver splits the run-end edge, so the neighbouring face gains a vertex (a quad becomes a
  pentagon) without being divided. Inherited from D's resolver; may or may not match what Blender leaves behind.
- **"Click outside = commit" is not implemented for `knife_face`.** This file and the Q5 handoff say "Enter or click outside
  = commit", but `window.py` only routes `Enter`; a click on `outside` is rejected by every variant (unchanged). Q5 keeps
  Enter as the only commit.
- **Snap takes precedence over placing a point near an earlier one.** Within 14 px of one of your own clicked points
  (other than the chain's last) every click is a snap — rejected unless it is the chain start. An edge/face point cannot be
  placed that close to an earlier point; this follows directly from "snap always engages".
- **Interior loop + another run through the same face.** A closed all-interior chain and a run that cuts the same face in
  the same commit: runs are applied first, so the loop's face is already gone and the loop is skipped with a HUD note
  (`closed shape skipped — its face was already cut by another run`). Rare; not investigated further.
- **Crossing dots and the "no cut" style were checked in a headless render** (real window under Xvfb, `grid`: yellow
  crossing dots, cyan snap square, orange clicked points, HUD text) — a smoke check that the overlay draws, not a judgement
  of how it feels; the Artist test decides that.
- **Close-and-continue stress (2026-09-29, headless):** 300 random grid sessions (2–8 clicks, several cameras, ~270 closes
  followed by further clicks) committed with mesh invariants intact and no doubled vertex at any seeded start point (a
  compact 60-session version is in `test_knife_face_q5.py`). The same runs show vertices doubled at an *existing* vertex when
  the planner emits an edge crossing at t = 0.0 (a segment passing exactly through a vertex) — present with and without the
  seed, planner territory, not touched here.
- **Head stress (not a test):** 120 random Q5 sessions on `head` (2–5 clicks, three cameras, cache on, some closed) all
  committed with mesh invariants intact.
