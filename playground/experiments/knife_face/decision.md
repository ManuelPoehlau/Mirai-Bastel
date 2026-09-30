# Knife Face Cut Lab — Artist Verdict

**Status:** Discovery — played, verdicts recorded 2026-09-29 — see the Claude Code handoff (not committed) and
`docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md` (archived first impression, Q1–Q5, §7 Lab
options, §8 prepared Artist test — this file copies and updates that section for the two variants
actually built, B and D; C and A were dropped per the handoff's scope §2).
**Q5 (cross-face segments, 2026-09-29):** a third variant, **Q5**, is built on top of D — see "Q5 — Cross-Face" below
(Artist answers, what was built, lab defaults, adapted test, verdicts). Background:
`docs/research/topology/KNIFE_CROSS_FACE_DISCOVERY.md` (archived, not edited).
**Integrity (2026-09-29):** faces that "sit under a cut" (Artist report) — probe, root causes and fix in
"Q5 integrity findings (2026-09-29)" below.
**Loop closed at a single point (2026-09-30):** Artist decision (a) — the loop becomes its own face with one bridge; see
"Loop closed at a single point (2026-09-30)" below; dropped runs leave no trace (Task B, same section); the dark shading
after that commit is a zero face normal in `src/viewport/derived.py` — "Dark shading after a commit" under Observations.
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
*Since Task A (2026-09-29):* the rule depends on geometry only — ties are broken by position, never by click
order — and the loop is oriented like the parent face before the faces are built, so the result is the same for every
start point and direction (see "Task A" below).

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

**Status:** Discovery Lab — built 2026-09-29; first play test 2026-09-29 (tasks 1–5 as expected, task 6 led to the close-and-continue change, see "Artist play-test observations" below). **Verdict: Q5 = KEEP (Artist, 2026-09-29, after `5c777a0`); D = superseded by Q5, not judged separately.** KEEP is a Lab verdict, **not a promotion** — see "Artist decisions after Q5". Follow-ups from those decisions: bridges independent of click order/direction (Task A, done), click on an earlier cut point (Task B, done for boundary points — an earlier *interior* point is still rejected, see "Task B").
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
| Q1 (integrity, 2026-09-29) — a segment crosses an earlier segment of the same session inside one face | **Like Blender: an intersection vertex is created and both cuts are fully applied.** Refusing the click is **not** wanted | **Built** — the probe confirmed crossing segments (H-b) as the main cause; see "Q5 integrity findings (2026-09-29)", Fix. |

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
   (an earlier point of this chain, or a point of an already closed chain other than the closing vertex) is **accepted**
   since Task B (Artist decision 2026-09-29): a segment from the last point to it through the planner, the chain continues
   from that point, one in-session undo step including the crossings. This holds for **boundary points** (edge point,
   mesh vertex). An earlier **interior** point is still **rejected** with the HUD note "connecting to an earlier interior
   point is not supported yet" (open question, see "Task B"). Right after a close the closed chain's start *is* the new
   chain's seed, i.e. its last point: clicking it is rejected as "already the last point"; once the new chain has ≥ 3
   clicked points (seed included), a click on it closes that chain again.
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
  closing click (one step: close and seed go together). *Add-on (Task B):* **click an earlier point that is not the
  start** — on an edge point or a mesh vertex of your chain (or of the loop you just closed): the snap shows, the click is
  accepted, a segment from the last point to it appears and the next click continues from that point (`Ctrl+Z` takes back
  that one click). On an interior (face) point of your chain the click is still refused with a note.

**Observe:** does line + dots read as "this is what will be cut"? Is cutting the visible part and skipping the rest (the
Blender behaviour Manu asked for) what happens on the nose? Does the snap highlight make closing predictable? Does
connecting to an earlier point behave as expected (branching from it, retracing a segment, crossing your own line)? Does the
still-refused earlier *interior* point feel wrong? How many attempts per task, where does frustration appear?

## Q5 — Verdict

### D — control (cross-face test)

**Verdict:** **Superseded by Q5 — not judged separately** (Artist, 2026-09-29: D is "really only the older version of Knife Face"; Q5 = D + planner supersedes it).

**Reason:** Q5 contains D's session and resolver unchanged and adds the planner on top; a separate D verdict would judge the same thing twice. D's earlier verdict (KEEP, "The two variants" above) stands as history.

### Q5 — Cross-Face

**Verdict:** **KEEP** (Artist, 2026-09-29)

**Reason:** tasks 1–5 worked as expected in the first play test; the task 6 deviation (a new cut after a close was not connected to the closing vertex) was fixed in `5c777a0`, and the verdict followed the fix.

**Not a promotion:** KEEP is a **Lab verdict** only. No `src/` change, no Production structure. The one-Knife requirement is unchanged: Knife and Knife Face become **one** Production tool later; Q5 stays a variant of the `knife_face` family until that is decided explicitly (with docs, per the repository workflow).

**Open points (record, do not decide):**

- What a click on a snapped earlier path point (not the chain's start) should do — **Artist decision 2026-09-29: connect to it and continue from it** (see "Artist decisions after Q5"); **built for boundary points (Task B)**. Open: earlier **interior** points (still rejected) — needs a resolver that is not a polyline, see "Task B".
- Whether a shared **interior** start point behaves sensibly when the continued chain cuts the same face again. Seen while
  building (grid, vertex start): a continuation from the closing vertex whose chord crosses the loop's own cut inside one
  face cannot be connected in the already split face — that run is dropped ("N-1/N cut(s) applied"). Untested by the Artist.
  *Resolved 2026-09-29 (integrity fix):* the crossing gets an intersection vertex and both cuts apply — see "Q5 integrity findings".
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

## Task A — closed-shape bridges: click order and direction (2026-09-29)

**Trigger:** Artist decision 1 ("depending on click order and/or direction, odd connections appear and the resulting islands cannot
be edited properly"). Known before: `FACE_HOLES_DISCOVERY.md` §6 (winding defect of `close_loop_with_bridges`, never fixed).
Probe: `experiments/topology/knife_bridge_order_probe.py` (drives D's `click` / `commit`; Q5 subclasses D's resolver unchanged).

**Probe `[PROBE]`** — k = 3..8 loop points × every start rotation × both directions; shapes "sym" (regular k-gon, centred), "skew"
(off-centre, unequal radii), "tie" (k = 4, a square loop whose distances to the four corners are exactly equal). Surfaces: a unit
quad on `grid` (140 runs, 13 configurations) and 8 sampled `head` quads (704 runs, 72 configurations, non-planar; k = 3, 4, 5, 8).
Measures: bridge edge set and face partition as position-based (not id-based) sets — the partition includes each face's winding;
per face the Newell normal · the parent's Newell normal; overlap as *sum of |face areas| / parent area* and as coverage of a
41×41 sample grid over the parent's projection onto the plane through its centroid perpendicular to its Newell normal (the projected
measure used for the non-planar `head` quads: every sample must lie in exactly one face); interior edges traversed the same way by
both of their faces; `assert_mesh_invariants`.

| | before (`5c777a0`) grid | before head | after grid | after head |
|---|---|---|---|---|
| runs | 140 | 704 | 140 | 704 |
| configurations with more than one bridge set | 1 (the "tie" square: 2 sets) | 0 | 0 | 0 |
| configurations with more than one partition (topology or winding) | 13 of 13 | 9 of 72 | 0 | 0 |
| runs with a face normal disagreeing with the parent's | 70 | 332 | 0 | 0 |
| runs with overlapping faces (coverage ≠ 1; area sum up to 1.35 × parent) | 70 | 332 | 0 | 0 |
| runs with inconsistent interior winding | 140 | 664 | 0 | 0 |
| invariant failures | 0 | 0 | 0 | 0 |

Reading: the reported defect is the winding defect of `FACE_HOLES_DISCOVERY.md` §6, as described there — clicks in the parent's
direction overlap the inner shape (area sum up to 1.3536 × the parent for k = 8), clicks against it partition cleanly but with a
flipped inner face; in both directions the ring faces and the inner face walk the loop edges the same way (inconsistent winding),
which is what makes the island a poor citizen for select / delete / extrude. Both pass the invariant catalogue, so only this probe
sees it. The bridge *selection* was already click-independent except on exact ties (the "tie" square: 2 different bridge sets by start
point), because the distance ordering fell back to the loop index.

**Fix** (`engine.py`): (1) `close_loop_with_bridges` orients the loop like the parent face's boundary (Newell normals) before building
the faces — the inner face has the parent's orientation, each ring face walks its loop arc *against* the inner face; the caller's
indices and the returned `loop_vs` / `loop_edges` stay in click order; a loop without area (bow-tie) stays as clicked;
(2) `select_bridge` breaks ties by position (loop point, then boundary vertex, lexicographically; distances compared to 9 digits)
and only last by loop index — geometry only. Rule otherwise unchanged (nearest distinct boundary vertices, non-adjacent loop
points); no H5 ring meshing. `[PROBE]` same probe afterwards: the "after" columns above. No D/Q5 test pinned the old winding, so
**no existing assertion was adapted**.

**Observation (not fixed, not Task A) `[PROBE]`:** with the unchanged placement rule (nearest boundary vertex per loop point) a
bridge can pass through the loop: 300 random star-shaped loops (k = 3..8, off-centre, random radii; 191 were valid) on the unit
quad — 3 of 191 configurations produce overlapping faces because one bridge crosses one loop edge. It is **the same for every start
and direction** (0 order-dependent configurations and 0 normal / winding failures among the same 191 × 2k runs), so it is a
placement limitation of the Lab default rule, not the reported symptom. Not changed — the Artist has not seen the fixed bridges yet.

**Open points (record, do not decide):**

- Whether bridge *placement* (nearest vertices) looks right to the Artist once the winding is fixed — only after a play test
  (see the observation above for irregular loops where a bridge crosses the loop).
- Delete-face leaves free bridge edges (`FACE_HOLES_DISCOVERY.md` §6) — Production concern.

---

## Task B — click on an earlier cut point (2026-09-29)

**Artist decision 2 (interpretation, see above):** the click connects the last point to the earlier one and the chain continues
from there; closing on the chain start stays the sealing special case.

**Built** (`engine_q5.py` only; `window.py` unchanged — it already routes snap + click through `plan`/`click`):

- `_plan_existing`: an earlier *boundary* point (vertex or edge point) of the current chain, **or of an already closed chain**
  (case (ii) below the closing break), is accepted. The segment from the last point runs through the planner like any other
  click (crossings fixed with that click's camera); the earlier point goes into the path **again as the very same dict**
  (the trick of `5c777a0`), so commit resolves it to one vertex. Break markers and skipped stretches behave as for any segment.
  In-session undo/redo: one click = one step including its crossings (unchanged mechanism).
- `_merge_repeated_points` (commit): boundary run ends on the same edge point / vertex become one dict, and a straight segment
  between the same two points that is already cut (or from a point to itself) is dropped, with the HUD note "N repeated
  segment(s) merged". Reason: retracing a segment (`B -> C`, later `C -> B`) brings fresh crossing dicts on the same edge/t,
  which resolving separately splits twice (zero-length edge). Interior points and the interior-seed placeholders are untouched.
- A vertex click on a mesh vertex where the planner put a *crossing* is a new click, not an "earlier point" (crossings are not
  snap targets; before, such a click was refused with the earlier-point note).
- The pending-overlay draws a repeated entry once.

**Sub-case (ii), a point of an already closed chain:** done additively. Test: a diamond loop through four edge points of one
quad, closed by clicking its start; then the opposite point (E3) — the segment from the seed E1 to E3 cuts the diamond, the chain
continues from E3 into the quad above, all runs applied, one vertex per point. A point next to the seed (a loop edge already cut)
merges as a repeated segment.

**Sub-case not built — earlier *interior* point (rejected, note "connecting to an earlier interior point is not supported yet"):**
`[PROBE]` (a scratch run with the rejection lifted; not kept as code): grid quad, chain `edge A, interior I, edge B, edge C, I again,
edge D`. The click on `I` was accepted, but at commit `2/3 cut(s) applied` — the run `C, I, D` was dropped and the mesh was left with
the first cut only (no doubled vertex, invariants intact, but the segment the Artist drew is silently missing); with `I` as the
chain's *last* point the connection is dropped as a dangling tail. Why: an interior point is not a vertex before commit; D's resolver
creates one new vertex **per occurrence** in a run (`split_face_path`), and a second run that ends at `I` would have to attach to the
vertex the *first* run creates — i.e. a run that starts/ends at a not-yet-existing vertex, applied after the run that creates it,
with its face found afterwards. Q5 already does this for exactly one case (the seed of a closed chain: placeholder + `_interior_vertices`,
applied last), but generalising it to any repeated interior point means re-splitting runs at every later occurrence, ordering runs by
dependency and re-deriving the face after each split — plus sub-loops closed inside one face (D's bridge stand-in). That is a graph
over the click sequence, not an additive change to a polyline resolver — **not implemented** (handoff: STOP for this). Open
question for the Artist / the Production Knife design: is "click an earlier interior point" needed in the Lab, or does the
Production Knife (real cuts instead of a virtual list, see Artist decision (3)) make it trivial? With real cuts the interior point is
a real vertex the moment it is clicked and the click is an ordinary vertex click.

**Stress `[PROBE]`:** 400 random grid sessions of 3–8 edge-point clicks, about half earlier-point clicks (209 sessions with at least one
accepted earlier click), commit: 0 exceptions, 0 invariant failures, 0 doubled vertices at any clicked position. Doubled vertices
at *original* grid vertices — the planner's t = 0 case already recorded under "Close-and-continue stress" — occur without any earlier-point
click as well (31 of 400 sessions with earlier clicks switched off, 24 of 400 with them); untouched (planner territory). A compact
60-session version is in `test_knife_face_q5.py`.

**Known gaps, not fixed:** *(the first one is resolved since the integrity fix, 2026-09-29: crossing cuts get an intersection
vertex)* a segment that crosses an *earlier cut of the same face* cannot be connected there (the run is dropped,
"N-1/N cut(s) applied" — the open point under "Q5 — Verdict"); connecting to an earlier point makes this easier to hit
(the first scenario tried, `B → E` crossing the `C → D` line inside one quad, lost that run). A segment retraced after orbiting the
camera merges completely on the flat `grid` (probed: same crossings, "2 repeated segment(s) merged", 6/6 applied); on a curved
surface (`head`) the planner's crossings depend on the view, so a retrace under another camera may bring slightly different
crossings that do not merge — **untested**, not assumed either way.

---

## Q5 integrity findings (2026-09-29)

**Trigger:** Artist report (tested at `5c777a0`): on the default cube after several Knife Face sessions a face sometimes seems to
sit *under* a cut, one thin triangle shows dense parallel hatching (overlapping / degenerate triangles), some lines end in the
middle of a face. Nobody knew how it arises, so it had to be reproduced, not guessed.

**Known before?** Only related: `FACE_HOLES_DISCOVERY.md` §6 (concave faces and fan triangulation — fixed in `src`, every
render/pick call now ear-clips; winding defect of the bridges — fixed in `8e4e014`). Neither explains this. **Not covered by
tests:** `assert_mesh_invariants` checks topology only; the Q5 stress tests check invariants and doubled vertices, not geometry.

**Probe** `experiments/topology/knife_integrity_probe.py` (public API only, no Core change). A run = a fresh mesh
(`grid`: 4 × 4 unit quads, the Q5 test fixture; `cube`: `create_cube`), 1–3 committed sessions of 2–9 clicks each, four
cameras, 20 % chance to orbit between clicks. Each click aims a screen position at a random face interior (45 %),
vertex (15 %) or edge point (40 %) of the *current* mesh and then goes the window's way (cameras yaw/pitch: grid 20°/35°,
0°/0° head-on, −30°/60°, 45°/25°; cube 35°/30°, −40°/25°, 130°/−30°, 60°/55°):
`knife_face_pick` (occlusion on) → `set_view` + `snap_target` → `click`; `commit()`. After every commit the mesh is checked for
**geometric integrity** — per face in its best-fit plane: `zero_area`, `non_simple` (boundary edges intersect or touch, or a
spike), `tri_area` (sum of `triangulate_mesh_face` triangle areas ≠ polygon area — the hatching the Artist saw); per mesh:
`winding` (an edge walked the same way by both faces), `dangling` (edge without face), `flipped` / `coverage` (every face lies
in one reference plane — z = 0, or one cube side — with that plane's normal, and each plane adds up to its area: 16 / 4),
plus `assert_mesh_invariants`. The runs are seeded (`random.Random(seed)`); failing sessions are shrunk to the smallest click
list that keeps the defect class (`--minimise`).

**Numbers `[PROBE]`** (400 runs each, before the fix, `8936a1d`; the handoff's own seed file was not attached, so this picker
differs from the one in the report — it makes more clicks and more sessions per run, hence more failures than the 24/400 there.
*Corrected with the fix commit:* the first version of this section used a grid camera at pitch 89°, which looks at the z = 0 grid
edge-on and which the app's orbit (clamped at 85°) never reaches; the grid rows below are re-measured head-on, the cube rows are
unchanged):

| runs with an integrity failure | grid | cube |
|---|---|---|
| Q5 | 75/400 (non_simple 61, tri_area 39, zero_area 25, flipped 25, winding 1, **invariants 1**) | 130/400 (non_simple 112, tri_area 109, flipped 71, coverage 32, zero_area 5, invariants 1) |
| Q5, edge-only sessions (a click the pick resolves to a face interior is skipped) | 40/400 (zero_area 39, non_simple 36) | 21/400 (zero_area 21, non_simple 16) |
| D, same seeds (first session: identical clicks; D keeps the ones it accepts) | 1/400 | 41/400 |
| B, same seeds | 0/400 | 38/400 |

The **invariant** failures (`Edge … an mehr als 2 Faces angehängt`) are real: a degenerate chord (`along`, below) can
connect two vertices that sit on top of each other's edge chain. So even the topology check was not always green.

**Attribution `[PROBE]`.** Every failing session is tagged with *pre-commit* features of its path (D and Q5 do not touch the
mesh before commit, so the session-start mesh is what every click saw). **Every one of the 205 failing Q5 sessions carries at
least one of them** (none is left unexplained; for D, 2 of 41 cube failures carry none — its closed-shape stand-in with a
self-crossing outline, see the fix):

| feature | failing sessions (grid / cube) | clean sessions (grid / cube) |
|---|---|---|
| `cross` — two segments of the session intersect inside one face | 61 / 110 | 288 / 192 |
| `stale` — a run with interior points whose face another segment also cuts, both run ends also on a second face | 33 / 76 | 43 / 101 |
| `along` — a straight segment lies on its shared face's boundary (a straight-angle vertex between its ends) | 27 / 9 | 1 / 1 |
| `tzero` — a planner crossing on an edge at t within 1e-9 of an end | 25 / 0 | 1 / 1 |
| `leave` — a straight segment between two points of a shared face is not inside that face (concave face) | 3 / 16 | 0 / 5 |
| `multi` — a straight segment two shared faces could take, only one of which contains it | 8 / 15 | 17 / 15 |
| `fold` — a run whose interior points lie in more than one face (H-c) | 0 / 0 | 0 / 0 |

`cross` is frequent in *clean* sessions too — because then the crossing run is usually **dropped** instead: sessions with a
dropped run ("N-1/N cut(s) applied") — with `cross` 334/349 (grid), 207/302 (cube); without `cross` 1/358, 6/385. So a crossing
either breaks geometry or silently loses the cut the Artist drew (the "known gap" noted under Task B). `stale` passes when the
lowest face id happens to be the right face.

**Hypotheses** — targeted cases (`--cases`; minimal click lists written as world positions: `e(A→B, t)` = edge point from A
towards B, `f(P)` = face-interior click, `v(P)` = vertex; grid unless noted):

| hypothesis | case (minimal click list) | Q5 | D | B | verdict |
|---|---|---|---|---|---|
| **H-b** a segment crosses an earlier segment of the same session inside one face | **HB1** `e((0,0)→(1,0), .2)`, `f(0.8,0.5)`, `e((0,0)→(1,0), .6)`, `e((0,1)→(1,1), .5)` — the last chord crosses the notch | non_simple | non_simple | non_simple | **confirmed** — the main cause (grid and cube) |
| | **HB2** (head-on camera) `e((0,0)→(0,1), .5)`, `f(0.5,0.8)`, `e((1,0)→(1,1), .5)`, `f(0.2,0.9)`, `e((0,1)→(1,1), .2)` — two bent runs cross | non_simple | click 4 refused (A5 lock) | refused (A5) | confirmed (Q5 only: its A5 lock is off) |
| **H-a** later runs on a face an earlier run of the same commit already changed | **HA1** `e((1,1)→(1,2), .5)`, `e((2,1)→(2,2), .5)`, `e((1,1)→(2,1), .7)`, `f(1.5,1.3)`, `e((1,1)→(2,1), .3)` — the notch's quad is already split; both notch ends also lie on the quad below | flipped | flipped | clean | **confirmed, narrower**: see R2 |
| | **HA2** (cube, camera yaw 35° / pitch 30°) `e((-1,1,1)→(1,1,1), .6)`, `e((1,1,1)→(1,1,-1), .4)`, `f(0.6,1,-0.3)`, `e((1,1,1)→(1,1,-1), .75)` — a notch on the top whose ends lie on the top/right fold edge, after the top was split | flipped, off-plane face | same | clean | confirmed — this is what the cube shows |
| **H-c** interior points on several cube sides joined into one run across a 90° fold | **HC1** (cube) `e(top-front, .5)`, `f(0,1,0)` (top), `f(0,0,1)` (front), `e(bottom-front, .5)` | clean — the planner puts a crossing on the fold edge between the two points | refuses click 3 | refuses | **killed** — no run ever spans a fold (`fold` = 0 in 800 runs); the cube's extra failures come from R2 at fold edges |
| **H-d** one-hit piece end splits an edge / dropped trailing points leave inconsistent runs | **HD1** `e((0,0)→(0,1), .5)`, `f(0.5,0.5)`, Enter | clean (tail dropped, mesh unchanged) | clean | pending only | **killed as a cause** — dropped points never reach the resolver |
| | **HD2** session 1 `e((1,1)→(2,1), .5)`, `e((1,2)→(2,2), .5)`; session 2 `v(1,1)`, `e((1.5,1)→(2,1), .5)` | session 1 clean — the quad below gains a straight-angle vertex; session 2 **zero_area** | same | same | the split edge is clean geometry, but it is the precondition of R3 |
| open point "t = 0" (zero-area faces) | **T0** (head-on camera) `v(3,3)`, `e((1,3)→(2,3), .514)` — a line along a grid row | zero_area + non_simple | refused (no shared face) | refused | **related**: R4 |
| — (found by the probe) | **L1** (head-on camera) session 1 `e((0,0)→(1,0), .5)`, `f(0.5,0.5)`, `e((0,0)→(0,1), .5)` (an L cut); session 2 `e((0.5,0)→(1,0), .6)`, `e((0,0.5)→(0,1), .6)` — straight across the L's missing corner | non_simple | non_simple | non_simple | R5 |

**Root causes** (agent decision — all are defects against the already decided behaviour, none needs an Artist choice):

- **R1 — crossing segments (H-b).** D's resolver (Q5 inherits it) applies the runs of a commit one after another. A later run
  is resolved in "the face that holds both of its ends" (`_live_face_for` for runs with interior points,
  `connect_in_shared_face` for straight runs) — but its cut crosses an earlier run's cut edge inside the click-time face. No
  intersection vertex is created, so the new cut leaves the face it is built in (non-simple, overlapping faces — the
  hatching), or no face holds both ends and the run is dropped.
- **R2 — stale face, wrong face (H-a, narrower).** Once an earlier run of the same commit has split the click-time face,
  `_live_face_for` falls back to the *lowest-id* face holding both run ends. When both ends also lie on another face —
  a notch (both ends on one edge) or, on the cube, both ends on a fold edge — that is often the **neighbour**: the interior
  points are inserted into a face they do not lie in (flipped, off-plane faces — the face "under" a cut).
- **R3 — chord along the boundary.** A straight segment between two boundary points of one face that lie on one straight
  boundary line, non-adjacent only because a straight-angle vertex sits between them (every run end on an edge leaves one in
  the neighbouring face). Q5's `_link` and D's `accepts` only test direct edge membership, so the chord is cut: zero-area
  face; with doubled vertices even an edge with more than 2 faces (grid 1/400, cube 1/400; up to 7/400 under a grazing
  camera). Also reachable on the Production Knife (below).
- **R4 — planner t ≈ 0 (the open point).** `plane_hits` skips the endpoints of the segment's own end edges as vertex hits,
  but not the edges incident to them; a line running along a grid row through such an endpoint gets an *edge* hit at
  t ≈ 1e-15 there, which `split_edge` turns into a second vertex on top of the first (a zero-area sliver). Q5 only. Same
  origin as the "vertices doubled at an existing vertex (t = 0.0)" noted under Task B and the close-and-continue stress.
- **R5 — straight segment not inside its face (concave faces).** A straight segment between two points of a shared face is
  assumed to lie inside it; that holds for convex faces only. After an earlier bent cut the face is concave, the segment
  leaves it (L1), or `connect_in_shared_face` takes a lower-id face that holds both points but not the segment (`multi`).

**Where:** R1, R2, R3, R5 are in the **shared resolver** (D and Q5: `_apply_run`, `_live_face_for`, and the
`connect_in_shared_face` helper from `src`), R4 in Q5's **planner**. The planner's crossings are otherwise correct (the runs it
produces never span a fold, H-c). B shares R1/R3/R5 through `connect_in_shared_face` and has no R2 (it cuts the current mesh
at every click).

**Production Knife (read / probe only, not changed — Core freeze):** `src/mirai/topology/knife.py` connects every straight
segment through `connect_in_shared_face` (lowest face id, no geometric check). `[PROBE]` (`--production`): HD2's second session
played with `KnifeTool` leaves a **zero-area** face, L1's a **non-simple** face. R3 and R5 therefore exist in Production too;
recorded for the one-Knife Production design, not fixed here.

**Agent decisions:** (1) the defect is in the resolver (shared by D and Q5), plus one planner defect (R4); (2) a run has to be
resolved against the *current* faces — walked through them, not looked up by its ends; (3) since H-b is confirmed, the
Artist's crossing decision (Q1: intersection vertex, both cuts applied) is needed to satisfy the integrity requirement and is
built; (4) a post-commit validity check is needed anyway (the resolver works on floats; a check is cheap, a broken face is
not) — rollback of the whole commit on failure.

**Fix (2026-09-29, `engine.py`, `engine_q5.py`, `planner.py`; `window.py` unchanged — it already prints the commit message):**

- **Resolver: runs are walked through the current faces** (`KnifeFaceCollected._walk_run`, shared by D and Q5). A run starts at
  its first vertex, enters the face whose corner there holds its next segment, cuts that face up to the first point where the
  run meets the face's boundary (`cut_in_face`: `connect_vertices` or `split_face_path`) and continues from there. Candidates
  are only the pieces of the run's click-time face (commit-local root map `_face_root`; a straight run keeps to the pieces of
  the face it starts in); where a fold edge borders two sides, the face whose plane holds the target wins. Removes R2 (the
  lookup "lowest-id face holding both ends", `_live_face_for`, is gone) and R5 for D (a run that would leave its click-time
  face through one of its original edges is dropped — restored completely — instead of being built outside it).
- **Crossing cuts (Artist decision Q1, built because H-b is confirmed):** where a run meets a cut of this commit — an edge
  between two pieces of one click-time face — that edge is split: **one intersection vertex, part of both cuts**, and the run
  continues in the other piece. The resolver only ever sees per-face runs, so this applies inside *every* face a cross-face
  segment passes through — crossings of segments across faces need nothing else (two segments meeting *on* a mesh edge are
  not an intersection; both split the edge). Undo/redo is untouched: nothing is resolved before commit, one click stays one
  step (tested).
- **Along the boundary:** a stretch of a run that lies on a boundary edge is walked along, nothing cut (R3 for D).
- **A run that crosses itself inside one face, or leaves a point and comes back to it**, is dropped with its own HUD note
  ("N cut(s) closing a loop at a single point dropped (crossing itself, or back to its start — not supported yet)"): the
  part between the two passes would be a loop touching the rest of the face at one vertex only, which one boundary list per
  face cannot represent without a bridge or a hole — a behaviour question, see open points. The back-to-its-start case was
  dropped before as well (silently). *Superseded 2026-09-30:* built as its own face with one bridge (Artist decision (a)) —
  see "Loop closed at a single point (2026-09-30)".
- **Edge points at t within 1e-9 of an end resolve to that vertex** (`_resolve_boundary_points`) — never a second vertex on
  top of it (R4, second line of defence).
- **Closed-shape stand-in:** if one of its three faces would be broken (an outline that crosses itself, or a bridge through the
  loop — the Task A observation), only that shape is rejected ("closed shape rejected: …"), the rest of the commit stands.
- **Q5 plan (`_link`):** "cut" only if the straight line lies *inside* a shared face (`segment_in_face`); along a straight run
  of boundary edges it is "edge" (skipped, like an existing edge — R3); otherwise the planner is asked (R5: a concave face is
  crossed like any cross-face segment, the visible part cut). Hover and stored preview therefore show what commit does.
- **Planner (`plane_hits`):** an edge hit within t 1e-9 of the edge's end is a hit on that vertex (R4) — the segment's own end
  vertices excepted, as before.
- **Crossing preview (cheap, built):** where the hovered segment crosses a stored cut inside one face, the hover plan adds a
  crossing dot and the HUD says "N intersection(s) with earlier cuts"; the stored-path overlay shows the intersections of the
  stored cuts the same way (pairs of stored cut segments, per shared face — no window change, the window already draws
  `crossings`).
- **Safety net, all three variants** (`_KnifeFaceSession._integrity_problem`, before History): every face the session touched
  (new or boundary changed) must have area and be a simple polygon; across each of its edges at most two faces, walked in
  opposite directions, and not facing against a (nearly) coplanar neighbour (normals' dot < −0.5). On failure the mesh goes
  back to the session start, History gets nothing, the HUD reads "Knife Face — commit rolled back — <reason>; mesh unchanged".
  Cost: only touched faces, O(n²) per face in its vertex count.

**Numbers after the fix `[PROBE]`** (same probe, same seeds and cameras):

| | grid | cube |
|---|---|---|
| Q5 runs with an integrity failure | **0/400** | **0/400** |
| Q5 sessions rolled back by the commit check | 0/771 | 0/771 |
| Q5 sessions with a dropped run | 2/771 (both a loop closed at one point, named in the HUD) | 16/771 (all a loop closed at one point, named in the HUD) |
| Q5 edge-only: failures / rollbacks / dropped | 0/400 / 0 / 0 | 0/400 / 0 / 0 |
| D: failures / rollbacks | 0/400 / 0 | 0/400 / 0 |
| B: failures / rollbacks | 0/400 / 0 | 0/400 / **40/771** — B cuts at every click through `connect_in_shared_face` and is not fixed (REJECTed variant); the commit check takes those sessions back |
| sessions with `cross` that drop a run | 2/372 (before 334/349) | 14/334 (before 207/302) |

All targeted cases (HB1, HB2, HA1, HA2, HC1, HD1, HD2, T0, L1) end clean for Q5 and D; B's HB1 / HD2 / L1 are rolled back
with a reason. **Head** (scratch stress, not a test: 120 runs, 176 sessions of 2–6 clicks, three cameras): runs applied
4007/4007 (before 3939/4009), 0 rollbacks, 0 faces left broken, invariants intact.

**Tests** (`test_knife_face_q5.py`, block "Geometric integrity"): `assert_geometric_integrity` (triangulation area = polygon
area, simple polygons with area, consistent winding, no edge without a face, per-plane coverage on grid and cube, invariants);
the minimal reproductions HB1 (Q5 and D: one intersection vertex with four cut edges, one history entry, undo), HB2, HA1 (Q5
and D), HA2, R3 (Q5 skips, D walks along), R4 (planner reports the vertex; nothing cut), R5 (Q5 cuts across both faces), a run
crossing itself (Q5 and D: dropped with the note, the other run applied); the rollback (B on HB1: mesh unchanged, no history,
reason in the message) and a hand-built flipped notch caught by the commit check; the crossing preview (hover dot + HUD, stored
dot, undo / redo); seeded random sessions like the probe's — 80 Q5 runs and 60 D runs each on grid and cube, no integrity
failure and no rollback. **Adapted existing assertion (one):** `test_d_run_failure_is_dropped_and_rest_stays_one_undoable_step`
forced its Core failure by patching `connect_in_shared_face`, which the resolver no longer calls; it now patches `cut_in_face`
— same intent (an exception inside one run drops only that run), same assertions.

**Open points (record, do not decide):**

- ~~**Artist question — a cut that closes a loop at a single point**~~ — **closed: Artist, 2026-09-30: (a)** (see "Loop
  closed at a single point (2026-09-30)"). Kept for the record: (it crosses itself inside one face, or leaves a point and
  comes back into it): until then dropped at commit with a HUD note. Prepared 5-minute test (grid, Q5): (1) from the right edge of a
  quad click three points inside it so that the third segment crosses the first, then out through the bottom edge, `Enter`;
  (2) from an edge point into a quad and click that same edge point again, `Enter`. Options: **(a)** keep the loop as its own
  face, joined to the rest by a bridge like the closed-shape stand-in (H0); **(b)** refuse the click that closes the loop (the
  line stays, no point); **(c)** drop it at commit with a note (current). Blender makes the loop a face through the crossing
  vertex — here that needs either a hole or a bridge.
- **Production Knife:** R3 and R5 exist there too (`connect_in_shared_face`, `[PROBE]` above) — for the one-Knife Production
  design; nothing in `src/` was changed.
- **Zero-area faces from the planner's t = 0 case** (handoff open point): *related* — it is R4 (PLANE, a line through an end
  vertex of the segment's own end edge), fixed in the planner and guarded in the resolver.
- D reports a straight run that only walks along the boundary as "applied" although nothing was cut (cosmetic, D is
  superseded). *Resolved 2026-09-30 (Task B):* such a run cuts nothing, is not counted as applied and leaves no split.
- `segment_in_face` and the walk work in each face's Newell plane; on the non-planar `head` quads that is a projection — the
  head stress plans exactly as before (same crossings, gaps and "along an edge" breaks), but it is not exact geometry.

## Loop closed at a single point (2026-09-30)

**Artist input (Manu, 2026-09-30, two screenshots, Q5, default cube, camera yaw 39.6 / pitch 24.1 / dist 6.92 per the HUD
in the screenshot):** click 1 on the top/right edge, clicks 2 and 3 inside the top so that segment 3 crosses segment 1
(intersection dot X), segment 3 runs on over the top/front edge, click 4 inside the front. "So sah der **gewollte** Cut vor
Commit aus." Result at `d8e346b`: `0/1 cut(s) applied; trailing interior point(s) dropped (no boundary reached); 1 cut(s)
closing a loop at a single point dropped` — nothing cut, but the mesh went from V8/E12/F6 to **V10/E14/F6** (Task B below)
and the cube turned uniformly dark ("Dark shading after a commit (Task C, 2026-09-30)" under Observations).

**Decision:** option **(a)** of the open point under "Q5 integrity findings" — the loop is kept as its own face, joined to
the surrounding face by a **bridge** (H0 — Face Holes stay set aside). (b) refuse the click and (c) drop at commit are not
wanted. *Interpretation (Context Check — Manu corrects only if wrong):* the small triangle X–click 2–click 3 is the intended
cut; X is one vertex, shared by the loop and the main cut (Blender-like). The trailing segment that ends inside the front
without reaching a boundary keeps today's rule (dropped with the note) — not part of this decision. *Superseded the same day:*
the last click inside a face is joined to the nearest corner — see "Last click inside a face (2026-09-30)".

**Built** (`engine.py`, shared resolver — D and Q5; `window.py` unchanged):

- `KnifeFaceCollected._walk_run` no longer drops these runs. **Form 1 — the run crosses itself inside one face:** the first
  crossing along the new segment gives X (on the crossed segment, in 3D); the points since that segment become a loop
  X → … → X, the run goes on from X (X becomes a vertex of the face's cut). **Form 2 — the run comes back into a vertex it
  left** (the Q5 closing click on an edge point / vertex after ≥ 2 interior points; also `a == b` runs): the loop is
  anchored at that vertex, the run goes on from there. Loops are built **at the end of the run**, in the face at their vertex
  that holds them, so later runs of the same commit see them (their edges are crossable like any cut of this commit).
- `close_loop_at_vertex` (new, next to `close_loop_with_bridges`): the loop face `[x, c1 … cm]` wound like the parent; the
  ring walks the outer boundary from x round to x and the loop backwards; **one** bridge from a loop point to a boundary
  vertex other than x splits it into two faces holding x once each — no face visits a vertex twice. (A loop touching
  nothing needs two bridges, the closed-shape stand-in; touching at x needs one.) Bridge rule = the closed shape's: the
  **shortest** (loop point, boundary vertex) pair, ties by position, never by index — so the result does not depend on
  click order or direction; the first candidate whose three faces are simple and face like the parent wins.
- Not built, dropped with the HUD note and its reason (`N cut(s) closing a loop at a single point dropped (<reason>)`):
  *out to one point and straight back — no area* (vertex → one interior point → the same vertex); *it winds round another
  loop's point* (a second self-crossing whose loop contains the first loop's X); *the run cuts through its own loop again*;
  *no bridge fits*. Built loops add `N loop(s) closed at a single point — own face, 1 bridge`.
- Commit check / rollback, one History entry per commit, in-session undo (one step per click) — unchanged; nothing is
  resolved before commit.
- STOP rule of the handoff (Core change / new face-splitting primitive): **not needed** — built from the public Core API
  (`add_vertex`, `add_face`, `remove_face`, `split_edge`) like `split_face_path` / `close_loop_with_bridges`.

**Probe `[PROBE]`** (`knife_integrity_probe.py`, same seeds as before; new `--cases` P1–P5, fuzz counts loops):

| | grid | cube |
|---|---|---|
| Q5 runs with an integrity failure | 0/400 | 0/400 |
| Q5 sessions rolled back by the commit check | 0/771 | 0/771 |
| Q5 loops at a point built / dropped (before: 0 / 2 grid, 0 / 16 cube) | 2 / 0 | 13 / 3 (2 "no area", 1 "winds round another loop's point") |
| D failures / rollbacks; loops built / dropped | 0/400 / 0; 0 / 2 ("no area") | 0/400 / 0; 3 / 1 ("no area") |
| Q5 edge-only failures | 0/400 | 0/400 |

Cases: **P1** (grid, segment 3 crosses segment 1) and **P1r** (clicked the other way round) — same partition for Q5 and D;
**P2** (edge point → two interior points → the same edge point, the handoff §3 form) — built; **P3** (Manu's sequence on the
cube, trailing front point) and **P3r** (the same top loop clicked from the front edge) — same top-face partition, Q5 and D;
**P4** (a loop hanging off a point on the top/front fold edge — joined to the rest only by its bridge on the top; the front
gains only that edge point); **P5** (the run cuts back through the loop it just closed) — dropped with its reason. B has no
loop support (REJECTed variant): P1/P3/P5 are rolled back by its commit check, as before.

**Tests** (`test_knife_face_q5.py`, block "a loop closed at a single point"): P1 for Q5 and D (one vertex at X with four
edges, the triangle face, exactly one bridge, one history entry, undo); P1 vs. P1r for Q5 and D (identical partition); form
2 in both directions (one in-session step per click, loop face + one bridge, V/F counts, history undo/redo; identical
partition); Manu's cube sequence (the triangle, one vertex at X, only the run's own 5 points new, trailing note); P3 vs. P3r
for Q5 and D (identical top partition); P4; P5 (dropped with its reason). **Adapted existing assertion (one):**
`test_a_run_crossing_itself_is_dropped_with_a_note_and_the_rest_applies` pinned option (c) — it is now
`test_a_run_crossing_itself_before_other_runs_leaves_them_applied` (same click list: "2/2 cut(s) applied" with the loop
built instead of "1/2 … dropped").

**Open points (record, do not decide):**

- **Where the bridge goes** for a loop attached at X — the nearest-vertex rule is the Lab default; look only after a play test.
- **Trailing interior point beyond a boundary crossing** is still dropped (Lab default). *Observation:* Manu's screenshot
  shows the segment over the top/front edge and a last click inside the front — he may want that segment kept up to the
  front's next boundary (or up to the click). Not changed here.
  **Artist input (Manu, 2026-09-30 12:21, screenshot, recorded in meaning):** "I would expect something like this, because
  the last cut (click) was on the front face — but probably the behaviour now is just temporary." The screenshot shows the
  result he expects, made by hand in a second session on top of the first commit (`V:14 E:22 F:10`, "1/1 cut(s) applied"):
  the cut goes on from the top/front crossing through his last click inside the front and on to the front's bottom-left
  corner — the front is divided, not left with a line ending inside it. *Open (Context Check, not decided):* what the tool
  should do on its own when the last click lies inside a face — (i) extend the last segment in its direction to the face's
  boundary, (ii) connect it to the nearest vertex (his screenshot ends on a corner), (iii) keep the chain open and wait for a
  further click that reaches a boundary before `Enter` counts (today `Enter` drops the tail), (iv) keep dropping, but show the
  tail in the "no cut" style so the preview says so. A line that ends inside a face (a dangling edge) cannot be one face's
  boundary without a bridge — the same limit as the loop at a point. **Answered (Artist, 2026-09-30): (ii) connect to the
  nearest corner** — built, see "Last click inside a face (2026-09-30)".
- Nested / overlapping loops in one run (P5, "winds round another loop's point") and the there-and-back case stay dropped —
  seen 3 times in 771 random cube sessions, never on the grid. *Update 2026-09-30:* loops that hang off another loop's point
  (bow-tie) are built now — see "Bow-tie back to the start"; P5 (the run cutting through its own loop) and the there-and-back
  case are still dropped.

**Prepared Artist test (5 minutes, after this commit):** Q5 on the default cube, same camera.
(1) Repeat the sequence above → expected: the triangle is its own face, one bridge from it to a top corner, the main cut
E1–X–(top/front edge) applied, no leftover vertices, normal shading. (2) Edge point → two interior points → the same edge
point again (snap, closing click) → `Enter` → expected: loop face + one bridge. (3) `Ctrl+Z` once after the commit → the
whole session is back.

| Task | Verdict (Manu) | Notes |
|---|---|---|
| (1) Manu's sequence | *(no verdict stated)* | Played 2026-09-30 12:16–12:17 (two screenshots, camera yaw 45 / pitch 25 / dist 8.37). Before `Enter`: "pending: 1 crossing(s); 1 intersection(s) with earlier cuts", X and the top/front crossing shown as dots. After: `V:13 E:20 F:9`, "1/1 cut(s) applied; trailing interior point(s) dropped (no boundary reached); 1 loop(s) closed at a single point — own face, 1 bridge", 5 edges selected. The triangle is its own face; the bridge runs from the loop's left point to the top's left corner (in this view). No leftover vertices, no uniform darkening — same counts and message as the headless replay. |
| (2) back to the same edge point | *(no verdict stated)* | Played 2026-09-30 13:06 with **three** interior clicks, the third segment crossing the first (a bow-tie): "0/1 cut(s) applied; 1 cut(s) closing a loop at a single point dropped (it winds round another loop's point)", mesh unchanged. Manu: "there might be a fix for this" → built, see "Bow-tie back to the start (2026-09-30)" below. |
| (3) Undo | *(no verdict stated)* | After Undo the shading looks fine (Manu, 2026-09-30). |

### Bow-tie back to the start (2026-09-30)

**Artist play test (Manu, 13:06, two screenshots, cube top, camera yaw 41 / pitch 43.7):** edge point on the top/right edge →
three clicks inside the top → the edge point again (closing click); the third segment crosses the first at X (the preview
showed the intersection dot). Commit: "0/1 cut(s) applied; 1 cut(s) closing a loop at a single point dropped (it winds round
another loop's point)" — nothing cut. "There might be a fix for this."

**Cause:** two loops, one hanging off the other: the crossing closes loop A = X → I1 → I2 → X; the run goes on from X to I3
and back into the edge point E, which closes loop B = E → X → I3 → E. X is a point of loop B, and the resolver refused any loop
whose points contained another loop's X (it only knew loops anchored at an existing vertex or at a vertex of the face's cut).

**Fix** (`engine.py`, shared resolver — D and Q5): a loop is anchored at a vertex **or at the position of its crossing X**;
`_build_loops` builds them in dependency order — a loop whose X is not a vertex yet waits until the face's cut or another loop
through X has made it one. So loop B (at E) is built first, then loop A at B's vertex X, in whichever face now holds it (the
ring outside B for a bow-tie, B's own face if A lay inside B). The same covers a run that crosses itself twice with the second
loop around the first X. Result on Manu's figure: **two triangles, each its own face with one bridge**, one vertex at X, the
same for both click directions. HUD: "2 loop(s) closed at a single point — own face, 1 bridge each".

**Numbers `[PROBE]`:** new case **P6** (the bow-tie on the grid) clean; all `--cases` clean; fuzz Q5 grid / cube 0/400 integrity
failures, 0 rollbacks, 0 leftover splits; loops dropped as "winds round another loop's point": **0** (before 1); what is still
dropped: "out to one point and straight back — no area" (Q5 1 grid / 2 cube) and "the run cuts through its own loop again" (1
cube). **Tests:** the bow-tie in both directions (two loop faces, one X, one history entry), direction-independent partition,
and on the cube top like the play test. On that cube case the second loop's shortest bridge runs to a point of the first loop
instead of a cube corner (a third small triangle) — valid, and exactly the open point "where the bridge goes".

**Bridges go to outside corners (Artist, 2026-09-30, play test 13:22–13:24, two screenshots):** Manu replayed the bow-tie
(`V:13 E:21 F:10`, "2 loop(s) … 1 bridge each") and drew what he expects by hand: the edge between the two triangles (the
left triangle's bridge to the right triangle's point) **should not be there — the left triangle should bridge to the nearest
outside corner** instead. **Built** (`close_loop_at_vertex`, parameter `outside`): bridge candidates are ordered first by
"existed before this commit" (the corners the Artist clicked on — the session-start vertices), then by distance and position as
before; vertices this commit created (other loops' points, cut points) are used only if no outside corner gives a valid bridge.
Still order- and direction-independent. `[PROBE]` fuzz Q5 / D / B on grid and cube: 0/400 integrity failures each; all `--cases`
clean. Test: the cube bow-tie — both bridges end at cube corners. This settles the open point "where the bridge goes" for loops
at a point in the direction Manu showed (nearest outside corner); the closed-shape stand-in (a loop touching nothing,
`select_bridge`) already bridges to the face's own corners.

**Artist confirmation (Manu, 2026-09-30 13:39, screenshot `V:13 E:21 F:10`, "2 loop(s) closed at a single point — own face, 1
bridge each"):** "Sehr gut. Jetzt entspricht es dem, was ich erwarte." — the bow-tie with both bridges to outside corners is
the expected result.

### Last click inside a face (2026-09-30)

**Artist decision (Manu, 2026-09-30, answer to the question above):** when the last click of a cut lies inside a face, `Enter`
**joins it to the nearest corner** of that face (option (ii); not (i) extend to the edge, (iii) wait for a boundary click,
(iv) keep dropping). His hand-made screenshot (`V:14 E:22 F:10`) is the expected result of his sequence.

**Built** (`engine_q5.py`; Q5 only — D is superseded and keeps dropping its tail):

- The *tail* of a stretch — its last boundary point and the interior points after it — is no longer dropped: it becomes a run
  `B → I1 … Ik → V`, V a corner of the face Ik was clicked in. **Lab defaults (not decisions):** "nearest" is the world
  distance from Ik to the corners of that face as it was clicked (the session-start mesh — what the Artist saw; vertices
  other runs of the same commit create are not candidates); the tail's own start vertex is no candidate; ties by position.
  If the nearest corner cannot be cut to (the line would leave the face, or the tail would wind round its own loop), the
  next one is tried, each try taken back like a dropped run (Task B). A tail that no corner works for is dropped with the
  note "trailing interior point(s) dropped (no corner of their face could be joined)".
- Tails are applied after the other runs of the commit (seeded ones after the seeded runs). They count in "N/M cut(s)
  applied"; the HUD adds "K last point(s) inside a face joined to the nearest corner".
- ~~**Preview:** the stored-path overlay draws the joining line from the open chain's last interior click to its corner (same
  cut style); the hover message says "Enter joins the last point to the nearest corner" when the hovered point is inside a
  face.~~ *Removed 2026-09-30 (Artist: "the connect to nearest vertex should apply after cut session commit, not while
  cutting"; "nearest in 3D seems the right way"):* while cutting, nothing shows or announces the join — the preview is only
  what was clicked; the join is made at `Enter`. `window.py` unchanged.
- **Bug found while building (fixed):** commit's `resolved` map is keyed by `id(point)`; the corner end points were short-lived
  dicts, and CPython reuses a freed dict's id — the second tail of a commit was answered with the *first* tail's corner (a
  vertex of another face) and dropped. A vertex point is now never looked up in that cache, and the corner dicts stay alive.

**Numbers `[PROBE]`** (fuzz, same seeds): Q5 grid 0/400 and cube 0/400 integrity failures, 0 rollbacks, 0 leftover splits,
0 mesh changes without History; tails joined 157 (grid) / 366 (cube), not joined 0 / 1 (a five-point zig-zag winding round its
own loop — "it winds round another loop's point"). All `--cases` clean; HD1 (edge point → one interior point, `Enter`) now
joins the centre click to the quad's corner (0, 0, 0) (all four equally far — first by position).

**Tests** (`test_knife_face_q5.py`): the nearest corner on the grid (hover message, preview line, the cut's two edges);
ties by position independent of the start edge; the next corner when the nearest is the tail's own start; two tails in one
commit, each to a corner of its own quad; the id-cache invariant (a vertex point resolves to its own vertex whatever the
cache holds — fails without the fix). **Adapted (two, both pinned the dropped tail):** Manu's cube sequence now ends
"2/2 cut(s) applied; 1 last point(s) inside a face joined to the nearest corner; 1 loop(s) …" with I4 joined to the front's
corner (−1, 1, 1) (the nearest for the test's click; Manu's own click lies lower on the front, nearer its bottom-left corner,
as in his screenshot); the Task B test with the top run forced to drop now checks that only the tail is cut and the top run's
split E1 is gone (renamed `test_manus_sequence_dropped_leaves_no_split_of_the_dropped_run`).

**Open points (record, do not decide):** ~~whether "nearest" should be measured on screen instead of in world space~~ —
*closed, Artist 2026-09-30: 3D (world) distance is right;* whether a vertex created earlier in the same commit (e.g. the crossing on an edge) should be
a candidate; the leading-interior rule (a cut *starting* inside a face) is unchanged — still dropped.

**Prepared Artist test (2 minutes):** Q5, default cube. (1) Repeat the original sequence (top/right edge, two top clicks so
segment 3 crosses segment 1, last click inside the front) — watch the stored line from the last click to a front corner
before `Enter` *(superseded: no such line while cutting)*; expected after: `V:14 E:22 F:10`, the front divided as in the
hand-made screenshot. (2) Edge point on the top,
one click in the middle of the top, `Enter` — the click is joined to the nearest top corner.

| Task | Seen (Manu) |
|---|---|
| (1) original sequence, front joined to a corner | |
| (2) one interior click, `Enter` | **Works** (Manu, 2026-09-30: "edge point > one click into the face > enter > joins the nearest corner") |

### Dropped runs leave no trace (Task B, 2026-09-30)

**Found:** handoff reproduction (cube, Q5, edge point → two interior points → the same edge point, commit at `d8e346b`):
"0/1 cut(s) applied … loop dropped", yet V8/E12/F6 → **V9/E13/F6**; Manu's screenshot after his sequence: **V10/E14/F6**
(two splits). Cause: `_resolve_boundary_points` split **every** run end up front, before any run was walked; `_apply_run`
rolled back only its walk, so a dropped run's end splits stayed (on the edge and in the neighbouring face, which gained a
straight-angle vertex).

**Rule (agent decision, engineering — not an Artist question):** a commit that applies nothing does not change the mesh; a
dropped run does not leave its edge splits behind.

**Fix** (`engine.py`, shared resolver — D and Q5):

- **Each run splits its own ends inside its own rollback scope** (`_run_end_vertex`, called by `_apply_run` after the
  snapshot). A point on a click-time edge is placed on the chain of pieces that edge has become, by its t on the original
  edge — so the order in which runs split an edge does not matter (replaces `_resolve_shared_edge_pair` and the up-front
  grouping); a point at the same t as an existing split *is* that vertex. Points shared by two runs are split once and reused;
  a dropped run takes back its own splits only (a shared point used by an applied run stays).
- **A run that cuts nothing** (D: a straight run that only walks along existing edges) is not "applied" and leaves no split
  either (the cosmetic D point in "Q5 integrity findings" is resolved).
- **"Nothing changed" ignores the id counters.** `Mesh.load_state` only moves the id allocators forward (AD-001), so after a
  rollback the mesh equals its old self in everything but them; `_on_commit` compared the whole state and would push an
  empty History entry. It now compares without the counters (`_mesh_content`). The same slip already existed for a closed
  shape rejected after `load_state`.
- **Closed shape rejected by a MeshError** (`close_loop_with_bridges` adds the loop's vertices before its last checks): the
  mesh is restored — before, those vertices stayed isolated.

**Numbers `[PROBE]`** (fuzz, 400 runs each, same seeds; *leftover* = a new vertex with exactly two edges on one line, lying on
a session-start edge — a split no cut uses; *changed without History* compares without the id counters):

| | before (commit A) | after |
|---|---|---|
| Q5 grid / cube: leftover edge splits | 0 / 1 | **0 / 0** |
| D grid / cube: leftover edge splits | 74 / 118 | **0 / 0** |
| Q5, D: sessions without a History entry that changed the mesh | 0 | 0 |
| Q5 / D / Q5 edge-only: integrity failures, rollbacks (grid and cube) | 0, 0 | 0, 0 |
| D grid / cube: sessions reporting "N-1/N" | 2 / 11 | 62 / 115 — the runs that only walk along existing edges (64 / 112 such runs) are no longer counted as applied |
| Q5 loops at a point built / dropped, grid / cube | 2 / 0, 13 / 3 | 2 / 1, 12 / 4 — all dropped ones "no area" |

The later sessions of a fuzz run are drawn on the mesh the earlier ones left, so without the leftover splits they differ
slightly (hence the shifted loop counts). The targeted cases (`--cases`) all end clean.

B (Immediate, REJECTed, not the shared resolver) splits at click time and keeps its leftovers (338 grid / 198 cube) — not
touched.

**Acceptance 8.2 vs. Task A:** the handoff §3 click list is no longer dropped — since Task A it builds the loop (form 2).
The reproduction is therefore kept as a test with the bridge made to fail (the resolver's own reason for dropping it): the
cube stays at **8/12/6**, no History entry. Same for Manu's sequence (two splits before): unchanged mesh.

**Tests** (`test_knife_face_q5.py`, block "dropped runs leave no trace"): §3 reproduction dropped → 8/12/6, identical content,
no History; Manu's sequence dropped → unchanged; one of two runs dropped → the shared point stays, the dropped run's own end
split goes; a closed shape rejected after adding its vertices → unchanged; P5 (the run cuts through its own loop) → unchanged;
the seeded random sessions (Q5 80 + D 60 runs on grid and cube) now also fail on *any* mesh change without a History entry
and on *any* leftover split. `test_knife_face_lab.py::test_d_run_failure_is_dropped_and_rest_stays_one_undoable_step` gains
one assertion (only the applied run's two points are new) — nothing adapted.

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
  (other than the chain's last) every click is a snap — an earlier-point connection (Task B) or the close on the chain start.
  An edge/face point cannot be placed that close to an earlier point; this follows directly from "snap always engages".
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

### Dark shading after a commit (Task C, 2026-09-30)

**Observation (Manu's screenshot after the sequence in "Loop closed at a single point"):** after the commit the whole cube was
shaded uniformly dark (before: normal shading with a gradient). Cause was unknown.

**Reproduced `[PROBE]`, headless and in the real window.** Manu's sequence replayed in a real `PlaygroundWindow` under Xvfb
(camera yaw 39.6 / pitch 24.1 / dist 6.92, `C`, clicks through `on_mouse_release`, `Enter`) at `d8e346b`: the HUD shows exactly
his text and `V:10 E:14 F:6`, and the rendered frame is uniformly dark — the pixels at the centres of the top, front and right
faces are all (54, 62, 80), before the commit (107, 125, 160) / (108, 126, 163) / (96, 113, 145). The same without GL:
`knife_integrity_probe.py --shading` (the window's post-commit path is `_knife_face_teardown` → `_recompute_derived` =
`DerivedGeometry.full_recompute` → `_rebuild_vbo` = `vbo_builder.build_face_data`; the probe runs exactly those two).

**Cause:** `src/viewport/derived.py`, `DerivedGeometry.full_recompute` (and `update_face_normals`) take a face's normal from
the **first triangle** of `triangulate_face` (`triangle_normal(positions, tris[0])`, comment "planare Faces in V1"). A convex
face is fan-triangulated from its first corner, so when its first three corners lie on one line — a straight-angle vertex from
an edge split sitting at boundary index 1 — that triangle has no area and the face normal is **(0, 0, 0)**. Vertex normals are
the normalised sum of the face normals around a vertex: where the visible faces at a corner all have zero normals, only the
hidden faces count, and they point away from the light. The face shader (`n · L`, ambient 0.35) then lights those vertices
with ambient only: uniformly dark. In Manu's session the dropped run left **two** splits (Task B) that put such a vertex on all
three visible faces — hence the *whole* visible cube.

**Hypotheses:**

| | verdict | evidence `[PROBE]` |
|---|---|---|
| H1 incremental refresh with stale ids | **killed** | the window's knife_face commit path uses `full_recompute`, not `update_*`; in every replay the window's derived normals are identical to a fresh `DerivedGeometry(mesh)` |
| H2 bounds / shadow extents | **killed** | bounds stay (−1, −1, −1)..(1, 1, 1); `shadow_map.py` is not used by `window.py` at all (no import, no draw pass) |
| H3 a leftover / degenerate vertex confuses the rebuild | **confirmed, narrower** | not the VBO rebuild — the straight-angle vertex makes the *face normal* zero in `derived.py` |
| H4 only after a dropped run | **no** | a dropped run made it total (its splits changed three visible faces, no new faces), but a plain successful cut does it to the faces next to its ends too |

| `[PROBE]` (`--shading`, cube) | zero face normals | face-VBO vertices lit by ambient only (n · L ≤ 0) |
|---|---|---|
| untouched cube | 0 | 17/36 (the three hidden sides) |
| one edge split at t = 0.5, no cut | a zero normal for 5 of the 12 edges | — |
| Manu's sequence at `d8e346b` (dropped, two splits) | 3 (top, front, right) | **48/48** — all |
| Manu's sequence now (loop built, Tasks A + B) | 2 (front, right: the faces next to the run's ends) | 30/66 |
| P4 at `d8e346b` / now | 2 / 1 | 36/42 / 22/54 |
| a plain successful cut across the top (right edge → front edge), before and now | 2 (front, right) | 34/48 |

In the real window at HEAD the top of Manu's result is lit again (pixel (111, 129, 166)), the front and right faces are darker
than before the commit ((82, 96, 124) and (71, 83, 107)).

**Where, and what was changed:** the cause is in `src/viewport` → **not changed** (handoff §6/§8: record only; no playground
refresh is at fault, so `window.py` / `vbo_builder.py` / `renderer.py` / `shadow_map.py` stay untouched). Tasks A and B remove
the *total* darkening of Manu's session (no more leftover splits; his loop is cut), not the cause: any cut that ends on an
edge — the Production Knife included, since every `split_edge` does it — can still zero the normal of the neighbouring face.
**Proposal for an explicit decision (not built):** take the face normal from the Newell normal of the whole boundary (the same
sum `_polygon_plane_axes` already computes in that file) in `full_recompute` and `update_face_normals`; it is exact for planar
faces and does not depend on which corner comes first.

**Fixed 2026-09-30 (Artist: "yes fix the shading").** `src/viewport/derived.py`: new `face_normal` (Newell normal of the whole
boundary), used by `full_recompute` and `update_face_normals`; the documented decision is amended in place
(`docs/WP-04_GATE_5_COMPLETION.md` §7.2, dated note; module docstring). Regression tests:
`tests/test_derived_geometry.py::FaceNormalStraightAngleVertexTests` (every one of the 12 single cube-edge splits: all face
normals equal the side's outward axis; incremental update equals the full rebuild). `[PROBE]` `--shading` afterwards: 0/12
single splits leave a zero normal; Manu's sequence 0 zero normals (20/72 ambient-only vertices = the hidden sides); the plain
cut 0 (18/48). Real window (Xvfb): after the plain cut the front and right pixels are **identical** to before the cut
((108, 126, 163) / (96, 113, 145)); after Manu's sequence (111, 129, 166) / (101, 118, 152) — lit normally.

**Prepared check for Manu (2 minutes, after these commits):** Q5 on the default cube, same camera, `Shaded`. Click a point on
the top/right edge, then a point on the top/front edge (a plain straight cut across the top), `Enter`. Look at the front and
the right side: expected (headless render) **the shading changes at once** — the right side clearly darker, a dark smudge
towards the corner the two sides share (their face normals are zero now); the top pieces lit normally. `Ctrl+Z` → the front and right sides are lit as before. Then repeat the sequence from "Loop closed at a single
point": the cube must no longer go dark as a whole.

| Check | Seen (Manu) |
|---|---|
| plain cut: right side darker, smudge at the front/right corner after `Enter` | **Yes** — cut across the top close to the front corner (top/left → top/right edge), `V:10 E:15 F:7`, "1/1 cut(s) applied": both visible sides lose their light, the right one most; the top keeps its gradient |
| `Ctrl+Z`: lit as before | **Yes** — `V:8 E:12 F:6`, shading as before the cut |
| Manu's sequence: no uniform darkening | **Yes** (12:17 screenshot) — the top keeps its gradient; both visible sides are darker than before, the known neighbour-face effect of the cut's ends (zero face normals), not the whole cube |

*Recorded from Manu's three screenshots (2026-09-30, 12:11–12:12; camera yaw 45 / pitch 25 / dist 8.37 — another view than the
prepared one, which does not matter for this check).* **Result:** the headless finding holds in the real app on Manu's
machine — a plain, successful cut darkens the faces next to its ends, and Undo restores them. The cause stays where it was
found (`src/viewport/derived.py`, first-triangle face normal); nothing in `src/` was changed. The Newell-normal fix above was
waiting for an explicit decision — *given and built 2026-09-30, see "Fixed 2026-09-30" above.*
