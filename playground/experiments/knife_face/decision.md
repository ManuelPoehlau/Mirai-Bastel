# Knife Face Cut Lab — Artist Verdict

**Resolver home (2026-10-01, WP-KNIFE-01 S1):** the commit-time resolver of D and Q5 lives in
`src/mirai/topology/knife_resolve.py` (Knife-owned; faces only through `Mesh.split_face`), the face geometry it uses in
`src/mirai/topology/face_geometry.py`; `engine.py` / `engine_q5.py` keep the click-time Lab part and call it. This file
keeps the Lab / Artist record — see "One Knife S1 — the resolver moves to `src` (2026-10-01)" at the end.
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

**Status:** Discovery Lab — built 2026-09-29; first play test 2026-09-29 (tasks 1–5 as expected, task 6 led to the close-and-continue change, see "Artist play-test observations" below). **Verdict: Q5 = KEEP (Artist, 2026-09-29, after `5c777a0`; again KEEP for the Lab state at `f2d34e8`, Artist, 2026-09-30); D = superseded by Q5, not judged separately.** KEEP is a Lab verdict, **not a promotion** — see "Artist decisions after Q5". Follow-ups from those decisions: bridges independent of click order/direction (Task A, done), click on an earlier cut point (Task B, done for boundary points — an earlier *interior* point is still rejected, see "Task B").
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

**Verdict (2026-09-30):** **KEEP** (Artist, 2026-09-30) for the Lab state at **`f2d34e8`** — after Tasks A/B, the loop
closed at a single point, the bow-tie, bridges to outside corners, the last click joined to the nearest corner and "cutting
back the same way does nothing". Manu's remark, recorded in meaning: further unwanted results may still show up later; they
will be recorded here when they do. Still a Lab verdict — **KEEP ≠ promotion** (see below). The play-test rows further down
that say *(no verdict stated)* stay as they are.

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

*Status 2026-09-30 (F2):* R3/R5 in the Production path (Knife, Vertex Connect, Edge Connect via `connect_in_shared_face`) are fixed — see `docs/architecture/AD-017_FINAL_DECISIONS_2026-09-22.md`, addendum 2026-09-30.

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
  **Artist decision (Manu, 2026-09-30): cutting back along the same way is not a valid operation — it does nothing (dropped).**
  That is the current behaviour, now decided: out to one point and straight back is dropped with the note "out to one point
  and straight back — no area", and a segment retraced over an already cut one merges ("N repeated segment(s) merged", Task B
  2026-09-29) — neither changes the mesh.

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

---

## One Knife S1 — the resolver moves to `src` (2026-10-01)

**Decision basis:** M1 + K1 (Manu, 2026-10-01, "K1 zuerst"); AD-017 addendum 2026-10-01 "One Knife S1"; WP spec draft
`docs/research/topology/ONE_KNIFE_PROMOTION_DISCOVERY.md` §6.3. Production refactoring — **no Artist-visible change
intended**, no verdict slot filled by it; nothing below is a decision.

**Moved (not copied):** run walking, intersection vertices, loops at a single point, closed shapes, tail join, seeds,
merged repeats, dropped-run rollback and the commit check → `knife_resolve.py` (`resolve_collected` = D,
`resolve_cross_face` = Q5, `check_commit`); `FaceFrame`, `face_problem`, `segment_in_face`, winding → `face_geometry.py`
(F2's `chord_validity` now uses the same frame). The constructions are built from `Mesh.split_face` (closed shape, loop at
a point: two calls each, the host chosen by winding as in WP-KNIFE-00). Every path point carries an explicit point id
(`"pid"`, given at click time); nothing is keyed by `id()` any more. **Stays here:** picking (`knife_face_pick`), the
planner, snap, hover, preview, path / chains / undo / redo, `accepts` / `click`, the HUD text (worded from the resolver's
`KnifeResolution`, same strings).

**Evidence `[TEST]`:** golden net `playground/tests/test_knife_resolver_golden.py` (recorded before the move: 345 seeded
runs on grid / cube / head × B / D / Q5 plus Manu's recorded sequences — cube bow-tie `V:13 E:21 F:10`, tail join
`V:14 E:22 F:10` — compared position-canonically) is **byte-identical** after the move; the Lab suites pass unchanged in
meaning (import paths and monkeypatch targets moved; one assertion now ignores the new `"pid"` key); the B2b stand-ins are
frozen as `playground/tests/knife_b2b_oracle.py` and the new constructions equal them on grid, cube and head
(`test_split_face_equivalence.py`). `[PROBE]` integrity fuzz Q5 / D still 0/400 failures, 0 rollbacks, 0 leftover splits;
head fuzz (D + Q5, 230 sessions) 0 failures before and after.

### One Knife S1 — open points (recorded, not decided)

| # | Observation | Pinned by / numbers |
|---|---|---|
| S1-a | **Two simplicity tests.** `face_geometry.polygon_is_simple` (Knife: a crossing counts when both ends lie more than `eps` off the other line; a corner touching = within `eps` of the line *and* the bounding box) and `chord_validity._is_simple` (F2: sign-change crossing; touching = within `eps` *distance*). Same frame, same `eps`; they can differ only inside the `eps` band. Kept both (handoff Task 3.2) until a visible result is shown identical. | `tests/test_chord_validity.py` (F2), the Lab suites + golden net (Knife). F2's predicate itself is unchanged (200 000 random polygons, 0 differences). |
| S1-b | **Boundary start of two-call faces.** With `split_face` every new face starts its boundary list at an end of its call's path, so the inner face / the wing from call 2 (closed shape) and the loop face / one ring piece (loop at a point) start at another vertex than the Lab's 3-way split did — provably unavoidable with two calls. Same faces, same winding; but the render triangulation (fan / ear clipping from the first vertex, `viewport.derived.triangulate_face`) of such a quad can take the other diagonal: identical in flat display, the smooth-shading gradient *inside that face* can differ. On Manu's cube bow-tie and tail join: one quad each. Options (not decided): accept; a triangulation that does not depend on the boundary start (viewport); a primitive that keeps the start (Core). | `knife_integrity_probe.py --shading` P4: dark face-VBO corners 17/54 → 19/54 (`playground/tests/golden/probe_baseline.txt`); all other boundaries keep their start (golden random runs 0/345 differ with the start kept). |
| S1-c | **`split_face(k = 0)` refuses a chord that already borders another face**, where `connect_vertices` went on (the commit check would then have rolled the whole session back; now that run would be dropped, the rest kept). | Never reached: 0 of ~3 000 straight cuts in the golden net + integrity fuzz. |
| S1-d | Error text: a `MeshError` raised inside `split_face` (German) could appear after "closed shape rejected:" where the Lab named a "degenerate" face — only for a face whose boundary repeats a vertex (no tool builds one). | — |
| S1-e | The integrity probe's fuzz (and the Lab's own random tests) draw clicks by id order (`rnd.choice(mesh.all_face_ids())`); id values legitimately change with `split_face`, so their later sessions differ (verdicts unchanged). The golden net draws by position. | `golden/probe_baseline.txt` vs. today's `--variants` / default output. |
| S1-f | `one_knife_parity_probe.py` CORE section does not instrument `split_face` — it now counts the `add_face` calls inside it. | Probe output, CORE section. |
| S1-g | Planner and picking still import private `src` functions (`_edge_point_occluded`, `_point_occluded`, `_vertex_occluded`, `_edge_t_3d`); `_shares_nonadjacent_face` is still a Lab copy of `KnifeTool`'s private helper — known smells, slices S3 / S4. | — |

**Prepared practical test (Manu, 3 minutes, Playground, `knife_face` Q5, default cube):** replay the recorded sequences.
Expected: exactly as before — same counts, same HUD messages, same Undo / Redo. Watch S1-b in `Shaded`: inside one quad of the
loops the gradient may run along the other diagonal.

| Check | Expected | Seen (Manu) |
|---|---|---|
| bow-tie: top/right edge → three clicks inside the top (third segment crossing the first) → the edge point again → `Enter` | `V:13 E:21 F:10`, "1/1 cut(s) applied; 2 loop(s) closed at a single point — own face, 1 bridge each", bridges to outside corners | Passed — Manu's statement 2026-10-01 ("S1 3-minute test passed"; no per-row detail given) |
| tail join: top/right edge → two top clicks (segment 3 crosses segment 1, on over the top/front edge) → a click inside the front → `Enter` | `V:14 E:22 F:10`, "2/2 cut(s) applied; 1 last point(s) inside a face joined to the nearest corner; 1 loop(s) …" | Passed — Manu's statement 2026-10-01 ("S1 3-minute test passed"; no per-row detail given) |
| closed shape, then continue: four clicks inside, click the first again (closes, no commit), one more click on an edge, `Enter`; then `Ctrl+Z` / `Ctrl+Y` | as before; Undo removes the whole session, Redo brings it back | Passed — Manu's statement 2026-10-01 ("S1 3-minute test passed"; no per-row detail given) |

*Recorded 2026-10-01 (WP-KNIFE-01 S2 handoff): Manu's statement — both practical checks passed, the S1 3-minute test above
and the F2 2-minute test (R3/R5 through the Production Knife, Vertex Connect and Edge Connect: clean, the offending click /
pair refused; F2 commit `dce82c4`). A statement that the checks passed, not a verdict on S1 or F2.*

---

## One Knife S2 — Production `KnifeTool` on the virtual path (2026-10-01, PROVISIONAL)

**Decision basis:** M1 + K1 (Manu, 2026-10-01); AD-017 addendum 2026-10-01 "One Knife S2"; slice table
`docs/research/topology/ONE_KNIFE_PROMOTION_DISCOVERY.md` §6.2 (S2 row) and parity matrix §1.2. **PROVISIONAL until Manu's
verdict** — nothing below is Artist-validated.

**Artist decision (Manu, 2026-10-01), AQ1 of the promotion discovery (§6.6):** a click **along an existing edge** — on the
neighbour vertex, or a second point on the same edge — is **accepted, cuts nothing, and the chain continues from there**
(the Q5 behaviour; Production used to refuse it). This is the only intended Artist-visible change of *results* in S2.

**Assumptions stated in the discovery (§6.6, not contradicted — carried as decided-by-silence, correct if wrong):**
a session that cuts nothing leaves the mesh and History untouched (P11/P14: no lone vertex after one edge click + `Enter`);
a click outside the mesh keeps committing (AD-017 #8); the point marker at `t` while hovering an edge stays (G1).


**What changed (build, 2026-10-01; commits "Tests+docs: fix the red B-rollback test …" → "One Knife S2: own-point snap …"):**

- `src/mirai/topology/knife.py` — `KnifeTool` keeps a **virtual path**: points (vertex, or edge point with the click-time
  `t`), each with an explicit `pid`, plus `{"kind": "break", "reason": "edge"}` records before a skipped point. The mesh is
  untouched until commit; commit runs `knife_resolve.resolve_cross_face` (the Q5 entry — the only one that understands skip
  breaks and repeated points; D's `resolve_collected` knows neither), then `check_commit`, then pushes **one**
  `MeshStateCommand` (`"Knife"`) if anything changed; residue = the cut edges, Edge mode (unchanged). Segment rule: shared
  face required; **cut** when the chord is F2-valid in a shared face (`chord_valid_in_polygon`, edge points inserted where
  `split_edge` puts them); **skip** when it runs along an existing edge (AQ1); refused otherwise (cross-face → S4). Same
  point twice in a row refused; a click on an earlier own point reuses its record. In-session Undo/Redo pop/restore one
  click's records; Cancel drops the path. Gone: `_KnifeStep` mesh snapshots, per-click `export_state`, per-click pick-cache
  invalidation, `KnifeTool.start` (now `last_point`, a path record).
- `knife_preview.py` — render data from the path: placed points (once each), the segments commit will cut, start = last
  point, prospective point (vertex / point at `t` / own point), hovered edge, line preview. `KnifeRenderData` gained
  `placed_points`; the overlay layers and GL path are the existing ones.
- `knife_pick.py` — `snap_own_point`: within the vertex pick radius (14 px) of one of the session's own edge points the
  target becomes `{"kind": "point", "pid"}` (nearest wins against a mesh vertex; occlusion like the picks).
- `application.py` — render data from `KnifeTool.path`, own-point snap after `knife_pick`, placed points in the active
  layer, status texts (below), no per-click topology / pick-cache invalidation (invalidated on commit as before). Click
  outside still commits; `Enter` / `Esc` / in-session Undo-Redo routing unchanged.
- `playground/window.py` (`knife` family, B7 shares the tool) — reads `hover()["start"]` as the last path record, draws
  the placed points and cut segments from the same render data, applies the own-point snap. No other change.

**Evidence `[TEST]` / `[PROBE]`:**

- `tests/test_knife_parity.py` (written first, green on the real-cut tool): 26 rows unchanged after S2 (P01–P07, P10
  acceptance, P12, P13, S1–S3, S5, R5, R3 clean, 9 head edge rings P15 — position-canonical face hashes recorded before
  S2); the 10 rows marked expected-to-change (strict xfail) flipped: P08 / P08b / P09 / P09b (AQ1), P10 / P11 / P14
  commit nothing, S4 no History entry, R3 skip, G3 mesh unchanged during the session. Seeded random vertex/edge sessions
  (grid 60 runs, cube 60, head 12 — 259 sessions): `accepts() == click()` on every click, the mesh unchanged during every
  session, at most one History entry, Undo/Redo exact, geometry clean, 0 rollbacks, 0 dropped runs.
- `one_knife_parity_probe.py --parity --session --defects`, Production rows before → after: P08 `+-` → `++`; P09 `+-`,
  V26/E41, History 1 → `++`, V25/E40, History 0; P10 `+-`, History 1 (lone split) → `+-`, History 0; P11 / P14 History 1 →
  0; S4 History 1 (empty entry) → 0; S5 "mesh mutated during the session" True → False; R3 (HD2) `+-`, History 1 → `++`,
  History 0; R5 L1 V29/E45 → V28/E44 (no lone split); everything else unchanged and equal to Q5.
  `knife_integrity_probe.py --production`: HD2 `KnifeTool 1/2 → 2/2 clean`, L1 `1/2 clean` unchanged.
- Golden net `playground/tests/test_knife_resolver_golden.py` unchanged and green. Suites: `tests` 1034 → 1080 passed
  (GL via EGL), `playground/tests` (xvfb) 1038 + 1 red → 1042 passed.

### One Knife S2 — open points (recorded, not decided)

| # | Observation | Pinned by |
|---|---|---|
| S2-a | **A straight run of boundary edges is a skip.** R3 (from (1,1) along the straight line through the straight-angle vertex (1.5,1) to (1.75,1)) is accepted as a skip, nothing cut — Q5's rule (`segment_in_face` = "boundary"), taken as part of "AQ1 = Q5 behaviour". AQ1 itself named only the neighbour vertex and a second point on the same edge; before S2 F2 refused this click. | `test_r3_chord_along_a_straight_run_of_boundary_edges_is_a_skip`, `test_chord_validity.py` R3 tests |
| S2-b | **Retracing the session's own cut is a skip.** A → B then a click on A again: accepted, nothing cut, the chain continues from A (Q5: "cutting back the same way does nothing" + earlier point). Before S2: refused (A and B were neighbours along the new edge), the chain stayed at B. E.g. grid (1,1) → (2,2) → (1,1) → (2,0): before `++--`, after `++++`, two diagonals. | `KnifeTool._link` (session cut retraced) |
| S2-c | **A segment may cross an earlier cut of the same session inside one face** — commit makes one intersection vertex (Q5, Artist decision 2026-09-29 "crossing cuts like Blender"). Before S2 the click was refused unless the two points shared a piece of the already-cut face. E.g. one quad: bottom → top midpoint, then left → right midpoint: before `+++-`, after `++++` with a vertex at the centre. Not a parity row. | — (resolver behaviour, `playground/tests` Q5 suites) |
| S2-d | **A session's own cut line is no target.** Before S2 the cut was a real edge that a later click could split; now that spot is a face target → refused (needs face-interior points, S3, or the planner, S4). | `test_face_target_has_no_preview_and_click_does_nothing` (face case) |
| S2-e | **What the session shows** (G3, the M1 trade-off): placed points and the segments commit will cut in the selected style, the hovered target / edge / line in the hover style; the start is not drawn differently from the other placed points (it is where the line preview starts); a skip along an edge is not drawn. The mesh itself changes at `Enter` / click outside. | `test_render_data_draws_points_once_cut_segments_only_and_own_point_targets`, `test_gl_knife_overlay.py` |
| S2-f | **Status line texts** (`PROVISIONAL`, console): new "Knife: along an existing edge - nothing to cut (N path segments)", "Knife: cut (N path segment(s))" (was "N path edges" — nothing is an edge before commit), "Knife committed (…) - K of M cuts dropped" when a run was dropped at commit, "Knife: result taken back (reason), nothing committed" after a commit-check rollback; the others unchanged. | `test_status_line_names_skips_and_cuts` |
| S2-g | **`hover()` stays looser than `accepts()`** for the Playground `knife` family (F2 addendum); its old exception "edge incident to the start" is gone because AQ1 accepts that click. `Application` previews through `accepts()`. The Playground family now shows the path overlay instead of a cut mesh (G3) and uses the own-point snap. | `test_ad017_knife_keys.py` window tests |
| S2-h | `knife_pick.snap_own_point` imports the private `picking._edge_point_occluded` — same smell as S1-g (planner); public picking helpers are slice S4. | — |
| S2-i | **Preview ≠ result at `Enter`** (discovery §6.4): a run valid while clicking can still be dropped at commit (status "K of M cuts dropped"). Not seen in 259 random vertex/edge sessions. | seeded random test |
| S2-j | Handoff §9, open: whether the status line should show the pending count / what the Artist expects there; whether in-session feedback should show the *predicted* cut result (only after this verdict); P10 (cross-face edge → edge) stays refused until S4 — the first planner slice may start from Q5's `plan()`. | — |
| S2-l | **The preview line is sometimes hidden by a face** (added 2026-10-01, S3b handoff Task 0). Manu, S2 row 1: "je nach Face wird die Vorschaulinie manchmal vom Face verdeckt" — overlay drawn with depth vs on top. Recorded, not decided; not touched. | — |

**Rollback:** S2 is one revertable commit series (`git revert` of the five S2 commits restores the real-cut Knife); M2
(real cuts) is the documented fallback if "the cut appears at `Enter`" feels wrong.

**Prepared practical test (Manu, 5 minutes, `src/main.py`, head scene):** S2 stays **PROVISIONAL** until these slots and
the verdict are filled.

| # | Check | Expected | Seen (Manu) |
|---|---|---|---|
| 1 | Vertex → vertex diagonal, `Enter` | the diagonal cut appears at `Enter`; one Undo step |passed - aber je nach Face wird die Vorschaulinie manchmal vom Face verdeckt |
| 2 | Edge → edge → edge across a strip of quads, `Enter` | while clicking: points and lines, the line follows the cursor; the mesh unchanged; at `Enter` the cut appears, the cut edges selected (Edge mode) |passed |
| 3 | A vertex, then its neighbour **along an edge**, then a vertex across the next quad, `Enter` | the second click is accepted (status "along an existing edge - nothing to cut"), the cut runs from the neighbour (AQ1) |passed |
| 4 | One edge click, `Enter` | nothing happens — no stray vertex on the edge, no Undo step ("no cuts made") |passed |
| 5 | Four clicks, Undo, Redo, Undo ×4, `Enter`; then a new session, a few clicks, `Esc`; then a few clicks and a click outside the mesh | nothing committed after Undo ×4; `Esc` cancels; the click outside commits |passedc |
| 6 | Hover over an edge (before and after the first click) | a point marker sits at the cut position on the edge |passed |

| Verdict (KEEP / ITERATE / REJECT / UNKNOWN) | Manu's words |
|---|---|
| **KEEP** (Manu, 2026-10-01) | *"macht für mich als User keinen Unterschied, ob der echte Schnitt erst nach Enter passiert — ob die Linie eine Vorschau oder der echte Schnitt ist, ändert weder visuell noch den Workflow."* |

*Recorded 2026-10-01 (WP-KNIFE-01 S3 handoff, §0).* The verdict is on S2 as a whole; no per-row "Seen" detail was given, so
the rows above stay as they are. What it settles: M1 / the virtual path (the cut appears at `Enter`) is accepted in practice;
M2 (real cuts per click) stays only as the documented fallback. **S2-e is answered by this statement:** what the session
shows (points and the segments to cut; the mesh changes at `Enter`) makes no visual or workflow difference to the Artist —
no change asked. The other S2 open points (S2-a…d, f…j) stay open; the verdict does not decide them.

**Test robustness (S3 Task 1, 2026-10-01, tests only).** `tests/test_knife_parity.py::test_p15_head_edge_rings[6-0|6-18|10-0|10-18]`
failed in another environment, also on the commit before S2. Cause: Python 3.12 made `sum()` of floats compensated, so the
driver's computed `t` of a clicked edge point differed by one ulp; the head OBJ has 6 decimals, so an edge midpoint sits
exactly half-way between two 6-digit values and the driver's `round(c, 6)` went either way. Reproduced here: those four rows
fail on Python 3.12 / 3.13, pass on 3.11. Fix: `knife_parity_driver._r` rounds to 9 digits first, then to 6 (float noise
cannot flip a digit any more). Grid / cube / L literals unchanged; the nine head literals re-recorded from the pre-S2
real-cut tool (`d323be6`) with the new rounding — identical on 3.11 / 3.12 / 3.13 and equal to today's tool. Before: 3.11
39/39, 3.12 35/39; after: 39/39 on both. The golden driver (`playground/tests/knife_golden_driver.py`) rounds to 9 digits
and is identical on 3.12 — not changed. No production change.

---

## One Knife S3 — face points in the Production `KnifeTool` (2026-10-01, Artist verdict KEEP)

**Status (recorded 2026-10-01, WP-KNIFE-01 S3b handoff, Task 0):** PROVISIONAL → **Artist verdict KEEP (Manu,
2026-10-01, "Weg 1")** — see the verdict row at the end of this section. **KEEP ≠ promotion.** The text below is the
S3 build record as written before the verdict and is not changed by it.

**Decision basis:** M1 (Manu, 2026-10-01); S2 verdict KEEP (above); scope decision of the S3 handoff (the planner stays in
S4): S3 promotes **everything Q5 does inside one face**, a segment across several faces stays refused. Slice table
`docs/research/topology/ONE_KNIFE_PROMOTION_DISCOVERY.md` §6.2 (S3 row). **PROVISIONAL until Manu's verdict** — nothing
below is Artist-validated. The Artist decisions it carries over are the Lab's (not re-asked): closing a shape by clicking its
snapped start closes but does not commit and the next cut continues from the closing vertex; a click on an earlier own
(boundary) point connects to it and continues; a loop closed at a single point becomes its own face with one bridge (also the
bow-tie back to the start, bridges to outside corners); crossing an earlier segment inside one face makes one intersection
vertex; the last click inside a face is joined to the nearest corner at `Enter` (nothing announces it while cutting); snap to
any vertex / own point within 14 px; undo = last click, one Undo after commit takes the whole session back; a commit that
applies nothing leaves mesh and History untouched.

**What changed (commits "Records + test robustness …" → "One Knife S3: Application + preview wiring …"):**

- `src/mirai/viewport/picking.py` (additive): `face_hit_position` and `face_edge_distance_px` — moved from this Lab
  (`face_interior_hit`, `min_edge_distance_px`); the occlusion helpers are public (`point_occluded`, `vertex_occluded`,
  `edge_point_occluded`; the private names stay as aliases). `pick_face` unchanged.
- `src/mirai/topology/knife_pick.py`: a face hit is `{"kind": "face", "face_id", "position", "distance_px"}` (H1);
  `EDGE_MARGIN_PX = 9.0` (H3) lives here; `snap_own_point` covers the session's own interior points; the public occlusion
  helpers replace the private import (S2-h closed; S1-g closed for the occlusion helpers — the planner's `_edge_t_3d`
  import stays, S4). This Lab's `engine.py` keeps its names as imports of the moved code; the planner imports the public
  helpers.
- `src/mirai/topology/knife.py`: path records of kind `face`; `plan(target) → KnifePlan` (accepts / click / status share it;
  `last_plan`) in Q5's order — invalid target ("too close to an edge" below 9 px) → own point or a vertex already on the path
  → new point; closing (≥ 3 points of the chain, a "closed" break, cyclic when nothing was skipped, the start again as the
  seed); earlier boundary point connected; earlier interior point refused; a segment with an interior end is cut when Q5's
  `segment_in_face` puts it inside a shared face, boundary pairs keep the S2 rules; cross-face refused with the S2 reason.
  `cut_segments` = Q5's stored cut segments (a cyclic close's segment included), new `chain_points`; commit always resolves
  (`resolve_cross_face` + `check_commit`), one `MeshStateCommand` ("Knife"), residue unchanged.
- `knife_preview.py`: interior points in `placed_points`, the closing segment drawn, the hovered face point as the
  prospective point. `application.py`: pick order own-point snap > vertex > edge > face > outside (as Q5), status texts
  (S3-f), pick cache unchanged. `playground/window.py` (`knife` family): the face-point hover marker.

**Evidence `[TEST]` / `[PROBE]`:**

- **Differential spec** `playground/tests/test_knife_q5_differential.py` (driver `knife_q5_differential_driver.py`, written
  first: 44 strict xfails on the S2 tool, all flipped): the same world-position clicks through Q5 (no camera, so it refuses
  exactly the segments that need the planner) and the Production tool; compared: accepted clicks and refusal reasons,
  `accepts() == click()`, path records after every step (undo / redo included), mesh untouched in the session, the
  position-canonical mesh, every count and note of the commit's `KnifeResolution`, rollback, History + Undo / Redo, residue.
  **47 passed:** 34 recorded single-face sequences (FC1–FC4, closed shape by `Enter` / by click / both directions / then
  continue / vertex and edge start, loop at a single point both directions, back to the start both directions, bow-tie both
  directions, crossing cut HB1, tail join + tie, out-and-back from the start and from an earlier point, earlier-point connect,
  earlier interior refused, closing needs 3 points, too close to an edge, same point twice, undo / redo incl. the closing
  click), Manu's cube **bow-tie `V:13 E:21 F:10`** and **tail join `V:14 E:22 F:10`** (the planner's top/front crossing
  clicked as an edge point — the as-clicked sequence needs the planner and its 4th click is refused, S4); 3 multi-face
  sequences refused by both; the two documented differences (S3-a, S3-b); a forced rollback; **seeded random single-face
  sessions grid 150 / cube 150 / head 40 runs — 496 sessions, 2 262 clicks, 1 148 of them inside faces, 0 differences, 0
  rollbacks** (28 / 37 / 4 closes; joined tails 65 / 83 / 11; loops at a point built 17 / 31 / 0; closed shapes 17 / 9 / 3).
- `tests/test_knife_face_points.py` (Production only, 12): the rules one by one, and seeded random sessions with interior
  points on grid 80 / cube 80 / head 20 runs — geometry clean, mesh untouched during every session, ≤ 1 History entry, Undo /
  Redo exact, 0 rollbacks. `tests/test_knife_pick_face.py` (10): face hit position / clearance, the edge wins inside the
  margin, cache parity, interior-point snap and occlusion, public aliases, import hygiene (`knife.py`, `knife_pick.py`,
  `knife_preview.py` import nothing from `playground` and no private names). `tests/test_application_knife_faces.py` (7) and
  one Playground `knife`-family window test.
- Unchanged in meaning and green: parity rows P01–P15 / S1–S5 / R3 / R5 and the seeded vertex/edge sessions
  (`tests/test_knife_parity.py`), the golden net (byte-identical), F2 tests, the Lab Q5 / D / B suites. One S2 test renamed,
  same assertions: `test_a_face_the_last_point_does_not_touch_has_no_preview_and_click_does_nothing` (was
  `test_face_target_has_no_preview…` — a face hit is a target now; that face is refused as cross-face, S2-d).
- `[PROBE]` `knife_integrity_probe.py --production` now also runs the fuzz on the Production tool (window path: pick with
  occlusion → own-point snap → click), face points included: **grid 0/400, cube 0/400 runs with an integrity failure**, 0
  rollbacks, 0 leftover edge splits, 0 mesh changes without History (771 sessions each; loops at a point built 2 / 12). The
  Q5 fuzz is unchanged (0/400 each). `one_knife_parity_probe.py` (Production now gets the own-point snap the Application
  applies): every face row of the CORE section equals Q5 (FC1, FC3, closed shape, loop at a point, tail join, HB1 — before:
  refused / nothing); `--parity` / `--session` / `--defects` unchanged.
- **Hover cost on `head`** (`Application.pointer_motion` during a session with two points, occlusion on, 1280 × 800, a 40 × 25
  grid over the head, 5 rounds; this container, not the reference PC; median / min ms per move, three runs each): default
  framing S2 0.90/0.73, 0.76/0.70, 0.88/0.75 → S3 0.82/0.79, 0.80/0.73, 0.84/0.72; zoomed in (26 % face hits) S2 0.98/0.87,
  0.94/0.90, 0.97/0.88 → S3 1.11/0.94, 1.02/0.92, 0.97/0.88. Within run-to-run noise (A/B with face targets short-circuited:
  0.88–0.91 vs 0.88–1.08); the face pick itself is ~1 % of the hover (profile) — no extra cache added.
- Suites: `tests` 1080 → 1109 passed; `playground/tests` (xvfb) 1042 → 1090 passed.

### One Knife S3 — open points (recorded, not decided)

| # | Observation | Pinned by |
|---|---|---|
| S3-a | **Back on the chain start after one other boundary click.** Production keeps the S2 rule — an ordinary earlier-point click (a retrace is a skip, S2-b): e.g. edge A → edge B → A is `+++`. Q5 refuses it ("closing needs at least 3 points"): `++-`. Same mesh either way. With an interior point involved Production follows Q5 (refused) — e.g. "out to one point and straight back" from the start, `++-` in both. | `test_documented_difference_back_to_the_start_after_one_click` |
| S3-b | **Retracing the session's own cut between boundary points** (incl. the closing segment of a closed chain): Production skips it (S2-b, a break), Q5 connects to the earlier point and merges the repeat at commit. Same clicks accepted, same mesh / History / residue; only the record and the notes differ (1 skipped stretch vs "1 repeated segment(s) merged"). | `test_documented_difference_retraced_segment` |
| S3-c | **The chain's last point is a snap target in Production, not in Q5.** Within 14 px of the last point Production snaps to it and refuses the click ("already the last point", no preview); Q5 places a new point next to it (a very short segment). Picking only — the differential driver resolves clicks by position and does not see it. | — |
| S3-d | **A refused click shows nothing while hovering** (S2 rule kept: invalid → no point, no line); Q5 still shows its snap highlight and names the reason in the HUD while hovering ("closing needs at least 3 points" …). Production names the S3 reasons in the status line when the click is made (S3-f). | `test_refusals_name_the_s3_reasons` |
| S3-e | **Lab defaults now Production behaviour** (inherited through `resolve_cross_face`, not new decisions): three or more interior clicks in one face that are not closed by a click still close at `Enter` (the closed-shape stand-in, two bridges — D parity); interior clicks *before* the first edge / vertex click are dropped (FC4: start inside, then two edges = the straight cut between the edges; then one edge = nothing — status "first point(s) inside a face before any edge or vertex dropped"). Watch in the practical test. | recorded sequences "closed shape, Enter", "FC4 …" |
| S3-f | **Status line texts** (PROVISIONAL wording): refusals "Knife: too close to an edge - click on the edge or further inside the face", "Knife: closing a shape needs at least 3 points", "Knife: an earlier point inside a face cannot be clicked again (not yet)" (every other refusal keeps "Knife: no valid cut target here"); a close "Knife: shape closed - the next click cuts on from its start (N path segments)"; after `Enter`, appended with "; ": "N last point(s) inside a face joined to the nearest corner", "a last point inside a face could not be joined to a corner - dropped", "first point(s) inside a face before any edge or vertex dropped", "N closed shape(s) could not be built", "N shape(s) inside a face with fewer than 3 points dropped", "N closed shape(s) skipped - their face was already cut", "N loop(s) closed at a point dropped (reason)", "the cut on from an interior start point dropped"; with nothing committed they follow "no cuts made, nothing committed" in brackets. The session hint now says "click on vertices, edges or inside faces". | `test_application_knife_faces.py` |
| S3-g | **A face point inside the 9 px margin** comes up only where the edge pick did not return the edge (occluded, or off-screen ends); it is refused with "too close to an edge". `KnifeTool` needs the target's `distance_px` (`knife_pick` gives it) — a face target without it is refused too. | `test_an_interior_click_inside_the_edge_margin_is_refused` |
| S3-h | `hover()` (Playground `knife` family) stays looser than `accepts()` (S2-g) — for face points too (a face point inside the margin is "valid" there); the window shows the face marker only when `accepts()`. | — |
| S3-i | Carried, not touched: an earlier **interior** point as a target (Q5 neither); whether vertices created earlier in the same commit are tail-join candidates; where a piece ends next to a gap on curved surfaces (S4); whether hover should show the predicted corner / tail join before `Enter` (only after this verdict); S1-a (two simplicity tests: F2 for boundary pairs, `segment_in_face` with an interior end — 0 differences in 496 random sessions); hover cost relative to the S4 planner (S4 needs the click's camera and visibility per segment). | — |
| S3-j | **Bow-tie / loops at a point fail on non-planar faces** (added 2026-10-01, S3b handoff Task 0). Manu's row 6 below; measured headless (handoff §3, not Artist-tested): on `head` 0 of 324 quads commit the bow-tie recipe, status "the run cuts through its own loop again"; grid quad warped by one corner: works up to 1e-6, fails from 1e-4. Worked on in its own slice before S4 — "One Knife S3b" below. | `tests/test_knife_nonplanar_loops.py` |
| S3-k | **Start inside, then edges (row 4):** Manu, 2026-10-01: "später evtl Überlegen, ob der erste Klick zur nearest Vertex verbinden soll, bleibt noch offen" — whether the dropped first interior click should later be joined to the nearest vertex. Recorded, not decided; not built. | — |

**Rollback:** S3 is one revertable commit series (the four code / test commits after "Records + test robustness …");
reverting restores the S2 tool (vertex / edge targets only).

**Prepared practical test (Manu, 5 minutes, `src/main.py`, cube — `python3 src/main.py cube` — and head):** S3 stays
**PROVISIONAL** until these slots and the verdict are filled. Expected throughout: **exactly what Q5 did**, now in the one
Knife (`C` with an empty selection; `Enter` / click outside = commit, `Esc` = cancel, `Ctrl+Z` / `Ctrl+Y`).

| # | Check | Expected | Seen (Manu) |
|---|---|---|---|
| 1 | Bent cut: an edge of a quad → one click inside the quad → the opposite edge, `Enter` | a marker follows the cursor inside the face, the line bends at the click; the cut appears at `Enter`, one Undo step |passed |
| 2 | Notch: from an edge into the quad and back out through the same edge, `Enter` | a V-shaped cut, the quad split in two |passed |
| 3 | Closed shape: three clicks inside one face, then click the first again (snap) | status "shape closed …", nothing committed yet; `Enter` → the shape is its own face, two bridges (3 faces from 1) |passed |
| 4 | Start inside: first click inside a quad, then two edges of it, `Enter` | the straight cut between the two edges; the first click has no effect (S3-e) | passed - später evtl Überlegen, ob der erste Klick zur nearest Vertex verbinden soll, bleibt noch offen|
| 5 | Close, then keep cutting: close a shape as in 3, then click an edge of the face, `Enter` | the cut goes on from the closing point (one vertex there) |passed |
| 6 | Loop at a single point (cube top): top/right edge → three clicks in the top, the third segment crossing the first → the edge point again, `Enter` | bow-tie `V:13 E:21 F:10`, two loops, each with one bridge to an outside corner | no cuts made, nothing committed (a last point inside a face could not be joined to a corner - dropped; 1 loop(s) closed at a point dropped (the run cuts through its own loop again))|
| 7 | Last click inside a face: an edge point → one click inside the face, `Enter` | status "… 1 last point(s) inside a face joined to the nearest corner"; nothing announced before `Enter` | passed|
| 8 | A click right next to an edge (within ~9 px) | the edge is picked (point on the edge), not a face point |passed |
| 9 | An interior click in the *neighbouring* face right after a cut | refused — cross-face is S4 |no valid cut target here |
| 10 | Undo / Redo / `Esc` / click outside as in S2 | as in S2 |passed |

| Verdict (KEEP / ITERATE / REJECT / UNKNOWN) | Manu's words |
|---|---|
| **KEEP** (Manu, 2026-10-01) | *"Weg 1"* — the option he chose: S3 is KEEP; the head limitation is an open point, fixed in its own small slice before S4. |

*Recorded 2026-10-01 (WP-KNIFE-01 S3b handoff, Task 0).* Context of the answer (chat 2026-10-01, as summarised in the handoff, not Manu's wording): row 6 passes on the cube with the clarified recipe and fails on the head. **KEEP ≠ promotion.** The open points S3-a…k stay open; the verdict does not decide them. S2-a (a straight run of boundary edges is a skip) has still not been commented on by Manu and stays open. The head limitation is S3-j → "One Knife S3b".

---

## One Knife S3b — loops at a point on non-planar faces (2026-10-01, PROVISIONAL)

**Status (recorded 2026-10-01, WP-KNIFE-01 UX1 handoff, Task 0):** worked in Manu's practical test (*"funktioniert jetzt"*,
2026-10-01). This is not a verdict: the verdict slot below stays open and S3b stays **PROVISIONAL**.

**Decision basis:** S3 KEEP (Manu, 2026-10-01, "Weg 1") with the head limitation S3-j as its own slice before S4.
Production (M5): *what* is decided (loops at a single point must work on the head); *how* is technical. Q5 and Production
share the resolver (`knife_resolve`), so the differential tests cannot pin this — the spec is absolute:
`tests/test_knife_nonplanar_loops.py` (written first, strict xfail). **PROVISIONAL until Manu's verdict.**

### Diagnosis (Task 2, 2026-10-01 — measured headless, not Artist-tested)

**Rerun:** `python experiments/topology/knife_integrity_probe.py --nonplanar` — the bow-tie recipe (handoff §3: edge point
E on p1-p2 at t = 0.6, interior points I1..I3 at bilinear (0.2, 0.5), (0.55, 0.1), (0.4, 0.9), E again, `Enter`) on the
grid quad (1,1)-(2,2) with corner (1,2) raised by w, on all 324 `head` quads with the interior clicks **lifted into the
quad's Newell plane** (the handoff recipe) and **on the render triangles** (where a real face hit lands), and on each head
quad laid flat in its own Newell plane. Which gate rejected which loop was read from a throwaway copy of `_build_loops`
that logged each test (not kept); the probe's "refused before any loop / after loop B" lines and the height of X reproduce
it from outside.

**Observation:**

- The recipe makes **two** loops: the crossing of segment 3 with segment 1 closes loop A = X → I1 → I2 → X; the run goes on
  from X to I3 and back into E, closing loop B = E → X → I3 → E. B is built first (at the vertex E); A waits until B has made
  X a vertex ("Bow-tie back to the start").
- **Before (`4631c33`): every head quad is refused before any loop is built**, status "the run cuts through its own loop
  again". The rejecting test is the height gate `FaceFrame(f).height(probe) <= 1e-6 * size` for loop B; its probe is X,
  which lies on the 3D segment E–I1 — and E sits on the quad's 3D edge, off its Newell plane. Height of X / size: min
  7.6e-6, median 4.4e-3, max 2.8e-2 (lifted clicks); 1.7e-5 / 1.1e-2 / 7.1e-2 (on the render triangles) — every one above
  1e-6. Warped grid quad: built for w ≤ 1e-6, refused from 1e-4, same message.
- The handoff's local experiment (gate 0.2 × size): 303 commit; of the 21 left, **4** fail the height gate again for loop
  **A** (I1 measured against a piece of the ring left by loop B — a smaller face with its own tilted plane: 0.20–0.22 ×
  size) and **17** fail loop A's outline test.
- **Without the height term** (only the projected inside test picks the face): **307 / 324** commit (lifted), **309 / 324**
  (on the render triangles). Every remaining refusal (17 / 15) is loop A after loop B was built: **B's bridge** (the nearest
  outside corner, Artist decision 2026-09-30, chosen without regard to the loop that still hangs off B) **runs through loop
  A** in the quad's own frame, so A no longer lies inside one face.
- **15 of these quad shapes fail the same way when laid perfectly flat**, on the unchanged code (309 / 324 flat quads
  build; refused: head quads 17, 60, 62, 81, 83, 127, 167, 168, 221, 229, 230, 270, 271, 289, 310). They were never probed:
  the grid's and the cube's quads give the bridge another corner.
- The `1e-12` position match (`vertex_at`) never rejects: X is created at exactly the position it is looked up by.

**Answers:**

- **(a)** Only the height gate assumes planarity; it rejected all 324 head quads (and the warped grid from 1e-4) at the
  *first* loop, and with a looser threshold it still rejects loop A in a ring piece (the second gate). The outline's
  `segment_in_face` is a projection, not a flatness assumption — on the head it rejects only the bridge cases.
- **(b)** The ~21: 4 are the height gate again (second loop, a sub-face's own Newell plane); 17 are a **genuine refusal of
  the current construction**: loop B's bridge cuts loop A in two. Not a lifted-point artifact (15 of the same kind with the
  clicks on the render triangles), not a point outside the face, and **not a planarity matter** (reproduced on flat quads).
  *Interpretation:* which bridge loop B takes when another loop hangs off it is a behaviour question (bridge placement is
  an Artist decision) → **STOP (§7), recorded as S3b-a, not changed here.** The fix only has to say truthfully why it refuses.
- **(c)** Smallest change: **drop the height term.** Every face the loop is tried in is already filtered to pieces of the
  run's click-time face (`root` — always set once a run has entered a face, which every loop needs), so the probe came from
  that face; on a flat face every such piece passes the height test anyway — the gate never chose between faces there — so
  flat results stay bit-identical. Local experiment with the change: the 496-session differential fuzz gives identical meshes,
  counts and History (one cube session's reason text changes — the bridge case, see below); the integrity probe's default /
  `--production` / `--cases` / `--variants` / `--dropped` output is byte-identical; 1 800 further flat sessions (600 seeded
  random, 1 200 loop-heavy: edge point → 2–5 interior points → back to the start or out through another edge) give
  identical meshes, counts and History. The reason text: the bridge case is reported as "the run cuts through its own loop
  again", which is false there — the run does not cross loop A. It needs its own text (Task 3 b).

*Interpretation:* the height gate was a flatness assumption from the flat Lab scenes (grid, cube), where it never had to
discriminate between faces.

### Fix (Task 3, 2026-10-01)

`knife_resolve.KnifeResolver._build_loops` only (+ one constant, one helper):

- **(a) The height term is gone** from the test that picks the face a loop is built in. Why this and not a relative
  tolerance: a tolerance needs a margin that has to be justified per face (the ring pieces after loop B measured 0.20–0.22 ×
  size), while the root filter already proves the probe came from the run's click-time face; the projected inside test
  (`segment_in_face`, unchanged) picks the piece. Flat faces: unchanged by construction — there every piece passed the
  height test.
- **(b) New reason `LOOP_OFF_FACE` = "the loop does not lie inside one face"** (next to `LOOP_CROSSED`). When a loop does not
  fit one face, `_loop_reason` looks for an edge this run cut (or another of its loops) crossing the loop's outline in the
  loop's own plane: found → "the run cuts through its own loop again" (P5, unchanged); none → the new text (another loop's
  bridge or an earlier run's cut splits it). The status line shows it as "N loop(s) closed at a point dropped (the loop does
  not lie inside one face)". The only status-text change; S3-f wording stays PROVISIONAL.

### Result (Task 4, 2026-10-01 — headless, not Artist-tested)

**What changed:** `src/mirai/topology/knife_resolve.py` only (+26 / −10 lines: the face gate, `LOOP_OFF_FACE`,
`_loop_reason`). `face_geometry.py`, Core, `chord_validity.py`, `knife.py`, `application.py`, picking, Q5: untouched.

**Evidence `[TEST]` / `[PROBE]`:**

- `tests/test_knife_nonplanar_loops.py` (333): grid quad warped by one corner, w ∈ {0, 1e-9, 1e-6, 1e-4, 1e-2, 1e-1} — all
  build V+5 E+9 F+4, 2 loops, nothing dropped, 1 History entry, Undo restores the session-start content, Redo the result,
  geometry clean (before: refused from 1e-4); every head quad that builds (307) — the same checks; the 17 that refuse —
  nothing committed, mesh content unchanged, no History entry, reason "the loop does not lie inside one face", and laid flat
  15 of them refuse the same way (the other two, quads 4 and 135, build flat: there loop B bridges to another corner than on the head); the flat
  quad from head quad 62 — refused with the new reason; P5 — still "the run cuts through its own loop again". The 328
  strict xfails of the spec commit are gone.
- **Head count (exact):** recipe as in the handoff (clicks lifted into the Newell plane) **307 build, 17 refuse**; with the
  clicks on the render triangles **309 build, 15 refuse**. Every refusal: loop B's bridge runs through loop A (probe line
  "B's bridge through loop A: True") — a genuine refusal of the current construction (S3b-a), reason text truthful.
- **Flat faces:** the 496-session differential fuzz — meshes, counts, History, residue identical to `4631c33`; **one** cube
  session (seed 41, session 2) now reads "1 loop(s) closed at a point dropped (the loop does not lie inside one face)"
  instead of "(the run cuts through its own loop again)" — an earlier loop's bridge splits that loop (checked independently:
  the recorded bridge crosses its outline), so the old text was false there; this is the (b) change, the mesh is the same.
  Q5 vs Production: 0 differences (they share the resolver). 1 800 further flat sessions (600 seeded random, 1 200
  loop-heavy): identical meshes, counts and History; the reason text changed in 48, each one an earlier loop's bridge
  crossing the dropped loop (49 such drops), while every "cuts through its own loop again" has an edge of the run crossing it.
- `knife_integrity_probe.py` default / `--production` / `--cases` / `--variants` / `--dropped`: same numbers as `4631c33`
  (Q5 and Production fuzz grid / cube 0/400 integrity failures, 0 rollbacks; P1–P6 unchanged; only the print order of one
  "features in clean sessions" dict varies with the hash seed). `--nonplanar` as above.
- Suites (this container, pyglet + xvfb): `tests` (without `test_extrude_tool`, `test_pyglet_input`) 1075 → 1408 passed
  (+333 new), `tests/run_core_suite.py` PASS before and after, `playground/tests` 1090 → 1090 passed (golden net
  byte-identical, differential 47, Lab Q5 / D / B suites).

### One Knife S3b — open points (recorded, not decided)

| # | Observation | Pinned by |
|---|---|---|
| S3b-a | **A bow-tie whose first loop's bridge runs through the second loop is refused** — on any face, flat ones included: loop B (at the closing edge point) takes the nearest outside corner without regard to loop A that still hangs off its point X; A then lies in two faces. Head 17 / 324 (15 with the clicks on the render triangles), 15 of the same shapes laid flat; seen once in the 496-session fuzz (cube) and in 49 of 1 200 loop-heavy flat sessions. Now said truthfully ("the loop does not lie inside one face"). *Not decided:* a bridge for B that leaves A whole, or A's bridge first — bridge placement is an Artist decision ("Bridges go to outside corners", 2026-09-30), so a play test first. | `test_bowtie_refused_on_a_head_quad_says_why_and_changes_nothing`, `test_a_loop_split_by_another_loops_bridge_does_not_claim_the_run_crossed_it` |
| S3b-b | **Two projections of a warped face.** The resolver checks each face in its Newell plane (`FaceFrame`, `face_problem`); the render's `triangulate_face` projects along the dominant Newell axis (`face_geometry`'s docstring calls them the same — they are not, on a non-planar face). 3 of the 307 head bow-ties (clicks lifted into the Newell plane, up to ~3 % of the face size off the surface) leave one ring face that is simple in its Newell plane but folds in the render's projection — a possible shading artefact on that face; 0 of 309 with the clicks on the render triangles (where real clicks land), 0 for a closed shape on all 324 quads. Not touched (`face_geometry` / render are outside this slice). | `knife_integrity_probe.py --nonplanar` ("faces folded in the render projection") |
| S3b-c | The loop tests stay projections (`segment_in_face`, and `_loop_reason` in the loop's own plane): on a strongly curved face "inside one face" is decided in a plane, as everywhere in the resolver (the 2026-09-29 note "not exact geometry"). | — |

**Rollback:** one revert of "Fix: loops at a point on non-planar faces …" restores the gate (the spec's head tests then fail
— re-add the xfails).

**Prepared practical test (Manu, ≤ 5 minutes, `python3 src/main.py`, head):** S3b stays **PROVISIONAL** until these slots
and the verdict are filled.

| # | Check | Expected | Seen (Manu) |
|---|---|---|---|
| 1 | Zoom so one quad facing the camera fills a good part of the screen; `C` with an empty selection; click one of its edges, three clicks inside so that the last inner segment crosses the first, click the first edge point again (it snaps), `Enter` | two small loops, each with one bridge to an outside corner; the status has no "dropped" text; one `Ctrl+Z` reverts everything |passed |
| 2 | The same on two more quads, one at a **strongly curved** place | as 1 — or, rarely, "1 loop(s) closed at a point dropped (the loop does not lie inside one face)" with nothing cut (S3b-a: the first loop's bridge would cut the second) |passed |
| 3 | Cube regression: the same on the cube top (Top view, recipe from the S3 check) | `V:13 E:21 F:10` |passed |

| Verdict (KEEP / ITERATE / REJECT / UNKNOWN) | KEEP |
|---|---|
| | |

---

## WP-KNIFE-01 UX1 — Knife stays active after commit (Artist request 2026-10-01, PROVISIONAL)
**BACKED OUT (Artist 2026-10-02): code reverted, see below.**

**Artist decisions (Manu, 2026-10-01 — not re-asked):**

1. After a **commit** the Knife is **immediately active again** (a fresh, empty session) — he did not want to press `C`
   again for every cut.
2. **`Ctrl+Z` right after a commit, while the re-armed session is still untouched (no click yet), undoes the last commit;
   the Knife stays active.** His answer to the prepared question: *"Ctrl+Z nimmt den letzten Commit zurück, Knife bleibt
   aktiv"*.

**Defaults of the UX1 handoff (stated, not Artist-decided — Manu corrects only if wrong):**

- **A1** "Commit" = `Enter` **and** a click outside the mesh; both re-arm.
- **A2** `Esc` unchanged: cancels the running session (mesh, selection, History as before the session) **and leaves the
  tool** — `Esc` is the way out; on a fresh empty session it simply leaves.
- **A3** A commit that applies nothing (empty or fully dropped session) still leaves mesh and History untouched and the tool
  **stays active**; `Enter` / click outside on an empty session no longer leave the tool, only `Esc` does. The status says so.
- **A4** `Ctrl+Y` mirrors decision 2 (global redo) under the same narrow condition.
- **A5** "Untouched" = since the session was (re)armed: no accepted click, no in-session undo, no in-session redo. Otherwise
  the AD-017 in-session rule applies unchanged; once a click was made `Ctrl+Z` is the in-session undo, and at an empty
  in-session history it says "nothing to undo" (no fall-through to the global history).
- **A6** Production only (`src/main.py`, `Application`); the Playground families `knife` / `knife_face` are not touched.

AD-017 record: addendum 2026-10-01 "UX1" (append-only). Build record, evidence and open points: below, after the build.

### UX1 — build (2026-10-01, headless, not Artist-tested)

**What changed** (commit "UX1: the Knife stays active after a commit …"; `src/mirai/application.py`, knife section only,
~60 lines; `KnifeTool` unchanged — `begin(selection=…)` takes the residue selection as it is, so the §7 STOP did not apply):

- `_knife_start(rearmed)` — the setup `_knife_begin` had, shared: a fresh `KnifeTool` session on the current mesh and
  selection, preview and overlay refreshed at the cursor. `_knife_end(commit=True)` calls it after the commit's teardown
  (pick cache invalidated, overlay cleared, selection history recorded as before), so the next commit records its own
  selection-history entry with the residue as its "before".
- `_knife_history_step`: on a re-armed, untouched session (`_knife_rearmed` and not `_knife_touched`) → `_knife_global_step`:
  if the History can undo / redo, the session is dropped, `_apply_undo_redo` runs (the same path as global Undo / Redo, the
  selection mirror included), pick cache and viewport are refreshed, and a fresh re-armed session begins on the restored
  mesh; otherwise "Knife: nothing to undo / redo", the session stays. Otherwise the in-session step as before. An accepted
  click and a successful in-session undo / redo set "touched"; every (re)arm resets it. The `dispatch_command` path
  (Undo / Redo during a session) goes through the same method.
- Status (PROVISIONAL wording): after a commit "Knife committed (…)[; notes]; next cut ready - Esc leaves the Knife"; an
  empty commit "Knife: no cuts made, nothing committed[ (notes)] - Knife still active, Esc leaves" (also after a commit-check
  rollback); a global step "Knife: last commit undone - next cut ready, Esc leaves the Knife" / "Knife: commit redone - …";
  session hint "… Enter or click outside = commit (the Knife stays active), Esc = cancel and leave, Ctrl+Z / Ctrl+Y = undo /
  redo cut (right after a commit: the commit)". `src/main.py`'s usage docstring says the same.

**Evidence `[TEST]`:** `tests/test_application_knife_rearm.py` (27, written first with 26 strict xfails, all removed by the
build): Enter and click outside re-arm with the residue selection, render data and an empty path
(`test_commit_keeps_the_knife_active_with_a_fresh_session`); the re-armed session cuts again and records its own selection
history; empty and start-point-only commits keep the Knife and change nothing; Esc leaves a re-armed session with or without
points, mesh / selection / History as before that session; `Ctrl+Z` / `Ctrl+Y` right after a commit undo / redo it, mesh and
selection exact, the Knife active, and the session on the restored mesh cuts again
(`test_ctrl_z_right_after_a_commit_undoes_it_and_ctrl_y_redoes_it_knife_stays`); two commits undone one by one and redone;
after a click `Ctrl+Z` is in-session only and a second one says "nothing to undo" (no fall-through, A5); in-session redo
stays in-session; nothing to undo keeps the session; a session begun with `C` keeps the in-session rule; the session gate in
a re-armed session (11 keys); after every step the preview target exists in the mesh and equals a fresh pick at the cursor,
and the cached pick equals an uncached one on a 9 × 7 screen grid (with and without a cursor); the head OBJ: commit, re-arm,
`Ctrl+Z`, `Ctrl+Y` round trip. `Application` has no grid scene — cube and head instead.

**Changed old tests** (reason for each: "UX1: decided behaviour change (Manu 2026-10-01)"):
`test_application_knife.py::test_commit_pushes_exactly_one_entry_and_selects_the_path[enter|click_outside]` (Knife active
after the commit, status tail), `::test_commit_without_cuts_pushes_nothing` (active after an empty commit, A3; status tail),
`::test_vertex_adjacent_to_start_is_previewed_and_a_skip` (status tail); `test_application_knife_faces.py::
test_a_bent_cut_through_a_face_is_cut_at_enter_only`, `::test_the_last_click_inside_a_face_is_joined_at_enter_and_the_status_says_so`,
`::test_a_lone_interior_click_commits_nothing_and_says_why` (status tails);
`test_application_picking_cache.py::test_knife_cut_makes_the_new_vertex_immediately_hoverable` — outside the handoff's file
list, but the same kind of test ("inactive after commit"): the new vertex is now hovered by the re-armed Knife's cached pick
instead of the selection hover after the session ended; same purpose (the cache is fresh right after the commit), not left
with `Esc` first because that would invalidate the cache itself.

**Unchanged (checked):** `tests` (without `test_extrude_tool`, `test_pyglet_input`, xvfb) 1408 → 1435 passed (+27 new);
`tests/run_core_suite.py` PASS; `playground/tests` 1090 passed (Q5-vs-Production differential and the 496-session fuzz
unchanged — the resolver and `KnifeTool` are untouched); integrity probe default / `--production` / `--cases` unchanged.

### UX1 — open points (recorded, not decided)

| # | Observation | Pinned by |
|---|---|---|
| UX1-a | **The undo walk does not stop at the Knife's own commits.** While the re-armed session stays untouched, every `Ctrl+Z` undoes the next History entry — after the session's commits also whatever came before the Knife (a Split, a Move …); the global History is one stack and the rule (decision 2, A5) names no limit. Not limited here. | `test_two_commits_then_two_ctrl_z_undo_them_one_by_one` (the in-range part) |
| UX1-b | **A session begun with `C` keeps the in-session rule** — decision 2 speaks of "right after a commit"; a fresh `C` session is untouched too, but its `Ctrl+Z` stays "nothing to undo" (AD-017). Interpretation, not decided. | `test_a_session_begun_with_c_keeps_the_in_session_rule` |
| UX1-c | **An empty commit keeps "right after a commit" as it was** (not named by A3/A5): after a real commit the next empty `Enter` still lets `Ctrl+Z` undo that commit; after a `C` start it stays in-session. | — |
| UX1-d | From the handoff: whether a *touched* empty session should also fall through to the global History (A5, deliberately not done). | `test_after_a_click_ctrl_z_is_in_session_only_and_never_falls_through` |
| UX1-e | Status texts above: PROVISIONAL wording. `src/main.py`'s docstring still describes the removed press-slide-release gesture (B7.1) — older text, not touched beyond the commit sentence. | — |

**Prepared practical test (Manu, ≤ 5 minutes, `python3 src/main.py`, cube and head):** UX1 stays **PROVISIONAL** until these
slots and the verdict are filled; remarks on A1–A5 (and UX1-a…c) welcome.

| # | Check | Expected | Seen (Manu) |
|---|---|---|---|
| 1 | `C` with an empty selection, cut (two clicks), `Enter`; cut again, click **outside the mesh** | committed, **the Knife is still active** (status "next cut ready - Esc leaves the Knife") both times | |
| 2 | Right after a commit `Ctrl+Z` once, then `Ctrl+Y` | the last cut is gone, the Knife still active; `Ctrl+Y` brings it back | |
| 3 | One click, then `Ctrl+Z` | only the click is taken back (the commit stays) | |
| 4 | `Enter` on an empty session; then `Esc` | nothing changes, the tool stays ("Knife still active, Esc leaves"); `Esc` leaves the Knife | |
| 5 | Cut twice with `Enter` in between, then `Ctrl+Z` twice | both cuts undone one by one, the Knife active throughout | |

| Verdict (KEEP / ITERATE / REJECT / UNKNOWN) | Manu's words |
|---|---|
| | |

**Status (Manu, 2026-10-02) — UX1 backed out:** UX1 wird nicht verwendet, weil es einen Arbeitsgedanken in viele History-Schritte zerlegt und den Workflow in der Praxis behindert (Manu, 2026-10-02). Its open points UX1-a..e are moot. Replacement: Blender-style pen lift (planned, WP-KNIFE-01 UX2).

---

## WP-KNIFE-01 UX2 — pen lift (Artist 2026-10-02, Artist verdict KEEP)

**Status (recorded 2026-10-02, WP-KNIFE-01 UX2b / S4 handoff, Task 0):** PROVISIONAL → **Artist verdict KEEP (Manu,
2026-10-02)** — see the verdict row at the end of this section. **KEEP ≠ promotion.** The text below is the UX2 record and
build record as written before the verdict and is not changed by it; Manu's practical-test rows 1–7 are untouched. His
remarks on row 4 and row 7 became UX2-k (recorded only) and "WP-KNIFE-01 UX2b" (the live midpoint preview, below).

*Recorded 2026-10-02 (WP-KNIFE-01 UX2 handoff v2, Task 0).* Production only; the Playground families `knife` /
`knife_face` are not touched.

**Artist decisions (Manu, 2026-10-02 — not re-asked):**

1. **UX1 is backed out.** "Knife stays active after a commit" hindered the workflow in practice ("wir bauen es zurück").
   Code revert `f02ec19`; Manu's own record: the status line of "WP-KNIFE-01 UX1" above (`631c47a`).
2. **Pen lift, like Blender (old version):** one session holds **several chains**. A key (Blender 2.79: `E`) ends the
   current chain **without committing anything**; the session stays active; the next click starts a new chain. Commit stays
   `Enter`; `Esc` cancels the whole session.
3. **Double-click** closes / finishes the chain (Blender's double-click, `KNF_MODAL_ADD_CUT_CLOSED`) — "quasi auch wie Stift
   neu ansetzen".
4. **A click outside the mesh no longer commits.** Reason (Manu): the next slice (cross-face cuts, S4) needs the cursor to be
   able to leave the silhouette. The earlier decision "click outside the mesh = commit" (B7, AD-017) is withdrawn.
5. **Right mouse button = New Cut as well** ("sinnvolle zusätzliche Option"): `RMB` does the same as `E`.
6. **Midpoint snap with `Shift`+click** (Blender has it as a held `Ctrl`; Manu chose `Shift`).
7. **Angle constraint stays out for now; the idea is only recorded:** `docs/future_ideas/MODELING.md` ("Knife angle
   constraint").

Unchanged from earlier decisions: close ≠ commit; a click on the chain's own start closes it and the next click continues
from the closing vertex; a click on an earlier own boundary point connects; the last interior click joins the nearest corner
at commit; snap near any vertex (14 px); in-session Undo = last click; one Undo after a commit reverts the whole session; a
commit that applies nothing leaves mesh and History untouched; AQ1 skip; visible-part cutting; KEEP ≠ promotion.

**History (M1): UX1 wird nicht verwendet, weil** es einen Arbeitsgedanken in viele History-Schritte zerlegt und den
Workflow in der Praxis behindert (Manu, 2026-10-02) — see the UX1 status line above; UX1-a…e are moot (UX2-e).

**Other verdicts at this point:** S3b **KEEP** (Manu, recorded by himself in `41a182a`, "One Knife S3b" practical-test rows).
S2-a (a straight run of boundary edges is a skip) has still not been commented on by Manu and stays open.

**Defaults of the UX2 handoff (stated, not Artist-decided — Manu corrects only if wrong):**

- **D1** Keys = `E` (Blender 2.79) **and** `RMB` (Blender 3.0+): one command `KNIFE_LIFT`, two default bindings in the
  `knife` context. `RMB` acts on a **click** (press + release under the click threshold, AD-019 / B7.1); an `RMB` drag is
  not a lift and stays free. Blender 2.79's "RMB = cancel" is not taken over: `Esc` cancels.
- **D2** Double-click = *finish chain*: if the chain (including the point the double-click's first click just added) has
  ≥ 3 points and the closing segment is valid, it is **closed** (as a click on the chain's start would close it) **and the
  pen lifts** (no continuation seed). Otherwise it only lifts and the status says why it did not close. A double-click on
  the chain's start point: the first click closes (as today), the second lifts.
- **D3** After a lift the next click is a fresh start (vertex, edge point or face point). Clicking an earlier own point (a
  record with a point id) as the start begins the chain at that very record (one vertex at commit) — a branch off an earlier
  cut, like Blender's "new snapping points".
- **D4** The lift is its own in-session step: `Ctrl+Z` right after `E` takes the lift back (the chain continues from its last
  point); `Ctrl+Y` redoes it. A double-click's second click (close + lift) is one step; its first click is an ordinary click.
- **D5** `E` with nothing to lift (empty session, or already lifted) is refused with a status text; no state change.
- **D6** A click outside the mesh is a no-op with a status line; no preview target there. It is not a path point (UX2-b).
- **D7** Double-click = two releases within 0.35 s and 4 px, measured on an injectable clock. A constant, no setting.
- **D8** Production only; `knife` / `knife_face` untouched (`knife_face` is retired in S5).
- **D9** Midpoint snap: a `Shift`+`LMB` click whose pick target is an **edge** places the point at `t = 0.5` of that edge. A
  vertex target stays the vertex, a face target is unchanged, an own earlier point wins over the midpoint (own-point snap
  first). The 14 px snap radius is unchanged.
- **D10** Live preview with `Shift` held — only if the window layer can tell `Application` the `Shift` state while the mouse
  only moves without touching window code outside the knife path; otherwise click-only and open point UX2-f.
- **D11** Only the unmodified `LMB` is the Knife's today; it becomes unmodified **or `Shift`-only**. `Alt+LMB`, `Ctrl+…` and
  every other combination keep going through the pointer gestures. A `Shift`+`LMB` drag past the threshold is not a click.
- **D12** Blender's `Shift` (ignore snapping) has no equivalent now; a later "ignore snap" key must not use `Shift` (UX2-d).
- **D13** Double-click detection ignores modifiers; the finishing second click places no point, so `Shift` on it has no
  effect.

### UX2 — open points (recorded, not decided)

| # | Observation | Pinned by |
|---|---|---|
| UX2-b | **Clicks outside the mesh as path points in empty space** (Blender: a cut position can be "in space"). Now a click outside is a no-op (D6); whether it becomes a path point is an S4 question (cross-face, the cursor leaving the silhouette). **Resolved 2026-10-02 (Manu, S4 handoff v2):** a click outside inside a session is a point in space and cuts — AD-017 addendum "S4", "WP-KNIFE-01 S4" below. | — |
| UX2-c | **Freehand `LMB`-drag** (Blender: held and dragged = freehand cut) vs. ours: a drag past the click threshold does nothing (B7.1). | — |
| UX2-d | **The remaining Blender modifiers:** ignore-snap (Blender `Shift`; not on `Shift` here, D12), angle constraint (`docs/future_ideas/MODELING.md`), Cut Through (same file). | — |
| UX2-e | UX1-a…e are moot after the revert (Manu's status line on "WP-KNIFE-01 UX1"). | — |
| UX2-f | **Live midpoint preview** while `Shift` is held — only if D10 falls back to click-only (see the build record). *Being resolved by UX2b (2026-10-02), see "WP-KNIFE-01 UX2b".* | — |

Build record, evidence and the practical test: below, after the build.

### UX2 — build (2026-10-02, headless, not Artist-tested)

**What changed** (commit "UX2: pen lift …"; PROVISIONAL until Manu's verdict):

- `KnifeTool` (`src/mirai/topology/knife.py`): new path record `{"kind": "break", "reason": "lift"}`. `plan_lift(close)`,
  `lift()` and `finish_chain()`: a lift appends the record; right after a close (the chain is only its seed) it takes the
  seed's place, so the closed chain is not continued; `finish_chain()` closes the chain like a click on its start when it has
  ≥ 3 points and the closing segment is valid — the close's records without the seed, then the lift, one step — and
  otherwise only lifts with the reason in the plan ("pen lifted (not closed: …)"). Nothing to lift (empty, last record a lift):
  refused, `NOTHING_TO_LIFT`. `last_point` is None after a lift; `chain_points` / `cut_segments` / the close rule end at the
  lift (`is_chain_end`). A start may be an existing record (D3: an own boundary point, or a vertex already on the path — the
  same record, one vertex at commit); an own interior point as a start is refused (`EARLIER_INTERIOR`, the current rule). An
  in-session step now keeps the records it took away (the replaced seed), so `undo_step` / `redo_step` restore it exactly.
- Resolver (`knife_resolve.py`): only `is_chain_end` — a lift ends a chain like a close that is not continued; the gap
  counter (`res.gaps`, reasons `gap` / `edge`) is unchanged, so a lift is no gap. No other resolver change; the §7 STOP did
  not apply (`split_chains` already handles a chain end without a following seed).
- Bindings: command `KnifeLift`, `E` and an `RMB` click in the `knife` context only (`E` stays Rotate outside a session, `RMB`
  stays unbound globally); `keymap.json` can rebind or unbind both. Artist Input Truth: new entry `topology.knife_lift`
  (`E`, notes name the RMB click and the knife context — the Input Mapping Tool's reporter will list `E` twice, like
  `Ctrl+Z` / `Escape`, AD-013 rule 3 "visible"); the `topology.knife_commit` note no longer says "LMB outside mesh". No Lab
  override touches the `knife` context (Symmetry Lab: its own context; 246 → 246 tests).
- `Application` (knife section and the knife part of the pointer dispatch):
  - Keys: `KnifeLift` → `_knife_lift()` (ignored while the Knife's button is held, as Undo/Redo). Any key resets the
    double-click.
  - Pointer ownership (D11): the plain and the `Shift`-only `LMB`, and a button bound to `KnifeLift` (RMB). `Alt+LMB`,
    `Ctrl+LMB`, `Ctrl+Shift+LMB`, `Alt+Shift+LMB` go through the pointer gestures as before. One gesture records its
    button and whether `Shift` was held at the press (fixed at the press, AD-019).
  - Release under the click threshold: an RMB click lifts; an LMB click within 0.35 s and 4 px (Euclidean) of the previous
    LMB click is the double-click's second click → `finish_chain()`; otherwise a point. A drag past the threshold is no click
    and breaks a double-click; a finished double-click does not arm a third click (a triple click = a double-click + a new
    start). **Interpretation (not in the handoff):** when there is nothing to finish (empty session, already lifted) the second
    click is an ordinary click, not a "nothing to lift" refusal.
  - Click outside the mesh: status "Knife: outside the mesh: nothing to cut here", nothing else (D6).
  - Midpoint (D9): with `Shift` an edge target moves to `t = 0.5` after the own-point snap; if an own point already sits on
    that edge's midpoint, the click reaches that point (no second record at the same place).
  - **D10 → click-only (UX2-f):** `Shift` alone never reaches `Application` — `mirai.pyglet_input`'s key map has no Shift key
    and pyglet's motion events carry no modifiers; adding it would touch window code outside the knife path. The hover shows
    the free position; the **press** of `Shift`+`LMB` already shows the midpoint (preview point and edge highlight) while the
    button is held.
  - Render data: a lift is handed to the preview builder as a non-cyclic chain end (it knows only "closed"), and after a lift
    there is no start marker and no rubber band (`knife_preview.py` unchanged).
  - Status (PROVISIONAL wording): "Knife: pen lifted - the next click starts a new cut", "Knife: shape closed, pen lifted -
    …", "Knife: pen lifted (not closed: closing needs at least 3 points) - …", "Knife: nothing to lift", "Knife: outside the
    mesh: nothing to cut here", "Knife: start point set on an earlier point" (a branch). Start hint: "Knife: click on
    vertices, edges or inside faces to cut - Shift+click = edge midpoint, E / right-click = new cut (pen lift), double-click =
    close + lift, Enter = commit, Esc = cancel, Ctrl+Z / Ctrl+Y = undo / redo".
- `src/main.py`: usage text only.

**Evidence `[TEST]`:** `tests/test_knife_pen_lift.py` (13, grid): `test_lift_ends_the_chain_without_touching_mesh_or_history`,
`test_after_a_lift_the_next_click_is_a_start_and_commit_cuts_both_chains_as_one_entry` (new faces = the union of the two
chains cut alone, 29/46/18, one Undo), `test_two_lifted_chains_crossing_in_one_face_share_one_intersection_vertex`
(30/48/19), `test_a_start_on_an_earlier_own_boundary_point_branches_off_it`,
`test_a_start_on_an_earlier_interior_point_is_refused_as_today`,
`test_a_lifted_chain_ending_inside_a_face_is_still_joined_to_the_nearest_corner`,
`test_lift_with_nothing_to_lift_is_refused_and_changes_nothing`, `test_undo_after_a_lift_removes_the_lift_only_and_redo_restores_it`,
`test_finish_chain_*` (3), `test_a_lift_right_after_a_close_replaces_the_seed_like_finish_chain` (no short-shape / lost-
continuation note), and a regression (a close still continues from its start). `tests/test_application_knife_pen_lift.py`
(43 incl. parametrisations, cube, injected clock): E and RMB lift / two chains in one entry / nothing to lift / Ctrl+Z–Ctrl+Y;
RMB drag; branch off an own point; double-click on a third point, on the start, with < 3 points, outside the window (time
and distance), triple click, a drag is no second click; click outside (with and without points); Enter / Esc / empty
commit; Esc after a lift; a lift-only session commits nothing; bindings in the knife context only, the session gate, the
`keymap.json` rebinding; render data after a lift and after a later cyclic close; Shift+click on an edge / vertex / face /
near an own point / at an own midpoint / along the last point's edge (skip); pointer ownership; Shift drag; the press
preview; the combination Shift start → E/RMB → Shift start → Enter; the start hint. Written first as 50 strict xfails (6
guards held already); all markers removed by the build.

**Changed old tests** (reason: "UX2: decided behaviour change, Manu 2026-10-02"): `test_application_knife.py` — the `app`
fixture gets a clock that puts clicks 10 s apart (the old tests click the same spot quickly; with the real clock that is now
a double-click); `test_commit_pushes_exactly_one_entry_and_selects_the_path` without the `click_outside` variant (decision 4;
the new `test_a_click_outside_the_mesh_does_nothing` pins it); `test_session_gate_ignores_other_keys` without `E` (D1);
`test_modified_click_during_session_neither_cuts_nor_selects` without `Shift` (D11), `Ctrl+Shift` added.
`test_application_knife_faces.py::test_refusals_name_the_s3_reasons` — its `_knife_pick` stub accepts the new `midpoint`
keyword.

**Unchanged (checked, Linux + xvfb):** `tests` (without `test_extrude_tool`, `test_pyglet_input`) 1408 → 1462 passed (−2
removed parametrisations, +56 new); `tests/run_core_suite.py` PASS; `playground/tests` 1090 → 1090 (the Q5-vs-Production
differential and the 496-session fuzz unchanged); `experiments/symmetry_lab/tests` 246 → 246; integrity probe `--production`
and `--cases` identical, the default run identical up to dict key order. `test_pyglet_input.py` errors identically before
and after here (no EGL library).

### UX2 — open points from the build (recorded, not decided)

| # | Observation | Pinned by |
|---|---|---|
| UX2-f | **No live midpoint preview** (D10 fallback): `Shift` alone does not reach `Application`; the midpoint is shown on the press. A live preview needs the window layer to pass Shift press/release (`mirai.pyglet_input` key map) — outside the knife path. *Being resolved by UX2b (2026-10-02, Manu's row 7 remark), see "WP-KNIFE-01 UX2b".* **Resolved by UX2b (2026-10-02):** the window passes the held `Shift` (`Application.set_shift_held`), the hover shows the midpoint before the click — "WP-KNIFE-01 UX2b" below. | `test_the_shift_press_previews_the_midpoint_and_the_plain_hover_the_free_position` |
| UX2-g | **Size over the handoff's ~120-line STOP guide:** executable lines +131 / −34 (net +97); the raw diff is +204 / −56 with docstrings and comments. No feature beyond the handoff; the two small additions are the own-midpoint reuse (D9) and the ordinary-click fallback of an empty double-click (above). Recorded instead of decided silently. | — |
| UX2-h | `Shift`+`LMB` (midpoint) is not listed in the Artist Input Truth (only `topology.knife_lift` was asked for); outside a session `Shift+LMB` stays SelectAdd. | — |
| UX2-i | Dated discovery documents still describe "click outside = commit" as the state of their time (`ONE_KNIFE_PROMOTION_DISCOVERY.md` §B/§F, `KNIFE_CROSS_FACE_DISCOVERY.md`, `KNIFE_FACE_CUT_DISCOVERY.md` §4/§8) — not edited (project memory); the AD-017 addendum "UX2" is the current rule. | — |
| UX2-j | **A start on a vertex that is an earlier chain's seed / start** is the same record (D3) — so a lifted chain that starts on the first chain's start counts as "seeded" in the resolver's bookkeeping; with a boundary start this changes nothing (only interior seeds are anchored, and an interior own point cannot be a start). | `test_a_start_on_an_earlier_own_boundary_point_branches_off_it` (the boundary case) |
| UX2-k | **An earlier own point inside a face cannot be clicked again** (Manu, row 4 below: *"passed, but if the vertex is inside a face: an earlier point inside a face cannot be clicked again (not yet)"*). This is the existing rule (`EARLIER_INTERIOR`, "not supported yet", S3-i), not a UX2 defect. Whether / when an earlier interior point becomes a valid target or start is Manu's priority call (likely together with S4). Recorded only, not built. | `test_a_start_on_an_earlier_interior_point_is_refused_as_today` |

**Prepared practical test (Manu, ≤ 5 minutes, `python3 src/main.py`, cube then head):** UX2 stays **PROVISIONAL** until these
slots and the verdict are filled; remarks only on D1–D13 if something feels wrong.

| # | Check | Expected | Seen (Manu) |
|---|---|---|---|
| 1 | `C` with an empty selection. Cut two clicks, press **`E`**, click somewhere else on the model, two more clicks, **`Enter`** | both cuts appear, one `Ctrl+Z` removes both |passed |
| 2 | `E` then `Ctrl+Z` | the chain continues from its last point (the lift is taken back); `Ctrl+Y` lifts again |passed |
| 3 | Three clicks inside a face and **double-click** the third | the chain closes into a loop and the pen is lifted; the next click starts fresh |passed |
| 4 | Lift, then click on **one of your earlier cut points** (on an edge) and continue from there | the new cut branches off it | passed, but if the vertex is inside a face: an earlier point inside a face cannot be clicked again (not yet)|
| 5 | Click **outside the model** | nothing happens (no commit); `Enter` commits; `Esc` cancels; a second `Enter` on an empty session changes nothing |passed |
| 6 | **Right mouse button** instead of `E`: cut, `RMB`, cut elsewhere, `Enter` | same result as 1; dragging with `RMB` does nothing |passed |
| 7 | **`Shift`+click on an edge** | the point sits exactly in the middle of that edge (the preview shows it only while the button is pressed — click-only, UX2-f); `Shift`+click inside a face or on a vertex behaves like a normal click; `Alt`+`LMB` still orbits |passed - but preview should also show the snap visually befor the LMB ist clicked |

| Verdict (KEEP / ITERATE / REJECT / UNKNOWN) | Manu's words |
|---|---|
| **KEEP** (Manu, 2026-10-02) | *"KEEP"* — chat answer to the prepared question; his rows 1–7 above are all "passed". |

*Recorded 2026-10-02 (WP-KNIFE-01 UX2b / S4 handoff, Task 0).* **KEEP ≠ promotion.** The open points UX2-b…k stay open
unless a later record resolves them; the verdict does not decide them.

---

## WP-KNIFE-01 UX2b — Shift live preview (Artist remark 2026-10-02, PROVISIONAL)

*Recorded 2026-10-02 (WP-KNIFE-01 UX2b handoff, Task 0).* Production only; the Playground families are not touched.

**Artist request (Manu, 2026-10-02, his words on UX2 practical-test row 7):** *"passed - but preview should also show the
snap visually befor the LMB ist clicked"*. So: with **`Shift` held** and the cursor near an edge, the hover preview already
shows the **midpoint** (point + edge highlight) **before** any button is pressed. This resolves UX2-f (the D10 fallback).
What `Shift`+click does is unchanged (D9).

**Defaults of the UX2b handoff (stated, not Artist-decided — Manu corrects only if wrong):**

- **A1** Only the Knife consumes the held-`Shift` state. No other tool, no global "modifier state" feature.
- **A2** The click keeps deciding by the modifiers of the **press** (AD-019, fixed at the press, unchanged). The held state
  only drives the **hover preview**. Invariant: the hover preview with `Shift` held equals the target a `Shift`+click at that
  cursor position produces.
- **A3** Left and right `Shift` both count; the state is "any `Shift` currently held".
- **A4** Losing window focus resets the state (a `Shift` released while another window has focus must not stay stuck).
- **A5** Production only; Playground families untouched.

Not in this slice: `Shift` as a bindable key, Ctrl / Alt state, ignore-snap, a change to what `Shift` does on a click, UX2-k.

Build record, evidence and the practical test: below, after the build.

**History (M1):** the direction is old — `docs/architecture/AD-017_ARTIST_SEMANTICS_2026-09-22.md` §"Knife position"
already sketched "Shift held: snap preview to edge midpoint" (2026-09-22, "not a request to implement Shift now").
Reused: UX2's `_knife_pick(..., midpoint=...)` and `_knife_set_preview`; only the source of the flag is new.

### UX2b — build (2026-10-02, headless + xvfb window smoke test, not Artist-tested)

**What changed** (commit "UX2b: live midpoint preview …"; PROVISIONAL until Manu's verdict):

- `src/mirai/pyglet_input.py`: a pure helper `shift_keys_after(held, symbol, pressed)` — for `LSHIFT` / `RSHIFT` the set of
  Shift keys held after the event (press adds, release removes; key repeat and a release without a press change nothing),
  `None` for every other key. `_key_map`, `key_from_pyglet`, `Input`, bindings, commands and the Artist Input Truth are
  unchanged: `Shift` alone is still no `Input`.
- `src/main.py` (window events only): `on_key_press` / `on_key_release` first update the held Shift keys through the helper
  and call `app.set_shift_held(bool(held))`, then continue exactly as before (the event is not consumed, Shift still yields
  no `Input`). New `on_deactivate`: clears the set and calls `app.set_shift_held(False)` (A4). No `on_activate`: on regaining
  focus the state stays "not held" until the next Shift press (a Shift held through the focus change shows the plain hover
  until it is pressed again — the safe side of A2).
- `src/mirai/application.py` (knife section + the setter): `_shift_held`; `set_shift_held(held)` stores it and, if it changed
  during a session with a known cursor while no button is held, recomputes the hover preview at once
  (`_knife_hover`). `_knife_hover` passes the flag as `midpoint` — so every hover refresh (motion, after a click / lift /
  undo, a session started with Shift held) uses it. The press preview and the click keep using the **press** modifiers
  (A2, AD-019); a Shift change while the Knife's button is held does not touch the press preview. Outside a session the
  flag is only stored. The start hint is unchanged (it never said "on the press").
- Size: production raw diff +77 / −4 (with docstrings and comments); executable lines ≈ 28 — inside the handoff's ~60.

**Platform check (Windows 10, Manu's PC):** pyglet 2.x reports `LSHIFT` / `RSHIFT` on win32 through raw input, deduplicated
(one press per physical press, no repeats) and clears its own Shift state on deactivate without sending releases
(`pyglet/window/win32/__init__.py`, read here for pyglet 2.1.16) — hence `on_deactivate`. On X11 key repeat re-sends the
press: the set makes it a no-op. Not run on Windows here.

**Evidence `[TEST]`:** `tests/test_application_knife_shift_preview.py` (17 incl. parametrisations, cube + head):
`test_holding_shift_over_an_edge_previews_its_midpoint_and_releasing_it_the_free_position`,
`test_moving_with_shift_held_keeps_the_midpoint_preview`, the invariant (A2)
`test_shift_held_preview_equals_the_shift_click_target_on_the_cube[False/True]` (910 positions each; with and without a start
point: 68 / 39 edge, 12 / 9 vertex, 200 / 86 face targets, the rest refused — preview `None` and the click refused) and
`…_on_a_head_patch[False/True]` (256 / 441 positions: 27 / 53 edge, 221 / 139 vertex, 8 / 14 face, 0 / 235 refused) — at
every position the held-Shift preview equals `_knife_pick(midpoint=True)` when accepted, and a `Shift`+click adds exactly the
records that target plans (each click undone again); `test_with_shift_held_an_own_point_near_the_midpoint_wins_in_preview_and_click`,
`test_with_shift_held_a_vertex_and_a_face_target_are_unchanged`,
`test_without_a_session_shift_held_changes_nothing_and_shift_click_still_adds_to_the_selection`,
`test_a_session_started_with_shift_held_shows_the_midpoint_at_once`, `test_without_a_known_cursor_shift_shows_no_preview`,
`test_set_shift_held_is_idempotent` (one overlay sync per change, none on a repeat),
`test_a_plain_click_decides_by_its_press_not_by_the_held_shift[False/True]`,
`test_the_press_preview_stays_fixed_while_the_button_is_held`, `test_double_click_rmb_lift_enter_and_esc_are_unchanged[False/True]`.
`tests/test_pyglet_input.py`: `TestShiftKeysAfter` (10: each Shift key, other keys → `None`, both held / one released →
still held, repeat and a stray release idempotent) and `TestShiftStillNoInput` (2, `key_from_pyglet` unchanged). Written
first as 27 strict xfails (the 2 guards held already); all markers removed by the build.
**`[PROBE]` window smoke test** (xvfb, the real `src/main.py` handlers driven through pyglet's dispatcher, cube): free
`t` 0.105 → `LSHIFT` press 0.5 → `RSHIFT` press + `LSHIFT` release still 0.5 → `on_deactivate` 0.105 / not held →
`Shift`+click lands at `t` 0.5.

**Unchanged (checked, Linux + xvfb, libEGL installed here so `test_pyglet_input.py` runs):** `tests` (without
`test_extrude_tool`) 1496 → 1525 passed (+29 new; 1462 + 34 `test_pyglet_input` before); `tests/run_core_suite.py` PASS;
`playground/tests` 1090 → 1090; `experiments/symmetry_lab/tests` 246 → 246; `knife_integrity_probe.py --production` and
`--cases` byte-identical to `beec01d` (`PYTHONHASHSEED=0`). Every UX2 test unchanged.

### UX2b — open points (recorded, not decided)

| # | Observation | Pinned by |
|---|---|---|
| UX2b-a | **"Any Shift held" ignores the other modifiers:** with `Ctrl`+`Shift` or `Alt`+`Shift` held (before any button) the hover shows the midpoint, although `Ctrl+Shift+LMB` / `Alt+Shift+LMB` are not Knife clicks (D11; pointer gestures). Harmless (no click lands there), but the preview then promises a midpoint no click makes. Tracking Ctrl / Alt was out of scope (A1, §5). | — |
| UX2b-b | **Shift held through a focus change** (Alt+Tab back with Shift still down): the state is "not held" until the next Shift press (no `on_activate` query; pyglet has none for key state). The click is right either way (press modifiers). | — |
| UX2b-c | The UX2 test `test_the_shift_press_previews_the_midpoint_and_the_plain_hover_the_free_position` keeps its D10-fallback docstring ("no live midpoint preview before the press"): it still passes unchanged (without `set_shift_held` the hover is the free position) and was left as written (allowed-files rule); its wording is historical. | — |

**Prepared practical test (Manu, ≤ 3 minutes, `python3 src/main.py`, cube then head):** UX2b stays **PROVISIONAL** until these
slots and the verdict are filled.

| # | Check | Expected | Seen (Manu) |
|---|---|---|---|
| 1 | `C` with an empty selection. Move the cursor onto an edge **without Shift** | the preview point sits where the cursor is |passed |
| 2 | **Hold Shift** (no mouse button), then release it | held: the preview point jumps to the **middle of that edge**, the edge is highlighted; released: back at the cursor |passed |
| 3 | With Shift held, click | the cut point is exactly where the preview showed it | passed|
| 4 | Hold Shift over a **vertex** and over the **inside of a face** | nothing changes compared to without Shift |passed |
| 5 | Hold Shift, `Alt+Tab` to another window, release Shift there, come back | the preview is **not** stuck in midpoint mode |passed |
| 6 | `Alt+LMB` (orbit) and `Shift+Alt+LMB` (pan); outside a Knife session `Shift`+click | still orbit / pan; `Shift`+click still adds to the selection |passed |

| Verdict (KEEP / ITERATE / REJECT / UNKNOWN) | KEEP |
|---|---|
| | |

---

## WP-KNIFE-01 S4 — cross-face planner and points in space (2026-10-02, PROVISIONAL)

*Recorded 2026-10-02 (WP-KNIFE-01 S4 handoff v2, Task B0).* Production only (`src/`); the Lab's Q5 keeps working and its
behaviour stays identical (S5). **PROVISIONAL until Manu's verdict** — nothing below is Artist-validated.

**Decision basis:** slice table `docs/research/topology/ONE_KNIFE_PROMOTION_DISCOVERY.md` §6.2 (S4 row: "planner with the
click's camera, visible part, snap to own points, close/continue, earlier point"); the KEEP'd Lab model Q5-b (walk + plane
planner, the **visible part** is cut: A-Q1; Cut Through not now: A-Q2 — "Q5 — Artist answers" above). Production changes
*where* the code lives, not *what* is cut. Manu (2026-10-02): the Symmetry promotion is re-checked only after S4 is done
**and verdicted** (ROADMAP 2026-10-02) — nothing about Symmetry is decided here.

**Artist decision (Manu, 2026-10-02 — not re-asked), his words:** *"Beim Klick ins Leere innerhalb der Session wird
geschnitten, das heißt, die Vorschaulinie kann über das Mesh hinaus gehen (wie bei Blender). Bei Klick verschwindet die
Vorschaulinie außerhalb des Mesh und man sieht nur noch die Cuts die nach Commit entstehen werden (auch Blender
Verhalten)"*. So: (a) the hover rubber band runs from the last point to the cursor even over empty space; (b) a click there
adds a point, and the segment from the last point to it cuts the visible mesh it crosses; (c) after the click the stretch
outside the mesh is not drawn — only the cuts commit will make. `Enter` commits; a click outside never commits. This
**supersedes UX2 D6** ("a click outside is a no-op") and **resolves UX2-b** — recorded as the AD-017 addendum
"2026-10-02 (Manu: S4)" (append-only; the UX2 addendum is not edited).

**Defaults of the S4 handoff (stated, not Artist-decided — Manu corrects only if wrong):**

- **S1** The cross-face model is exactly the Lab's Q5 (`planner.py` + `engine_q5.py::_plan_segment`), including the camera
  at **click time** and the occlusion switch (`display.show_faces`; wireframe = nothing hidden).
- **S2** A segment between two points that share no face (refused today as `CROSS_FACE`, parity row P10) is planned through
  the planner. Without a camera view (headless, no viewport) it stays refused, as today.
- **S3** Planned crossings are stored **in the path** (records with `crossing=True`, their point id given by the click);
  commit stays camera-free. Orbiting between clicks does not change an already placed cut.
- **S4** **Space points.** A click outside the mesh creates a point at the click's camera ray ∩ the plane through the camera
  `target`, perpendicular to the view direction (Blender 2.79 `knife_start_cut`: the plane through the view offset, normal =
  view z axis; `KnifePosData.is_space`, `[SRC]`). Stored world-space at click time; the chain continues from it.
- **S4a** A start in space is allowed; a chain that never touches the mesh commits nothing.
- **S4b** Space points are no snap targets and no "earlier points"; they take part in undo / redo (one click = one step),
  the pen lift (`E` / `RMB`), `Enter` / `Esc`; `Shift` has no effect on them.
- **S4c** Closing a chain (a click on its start, or the UX2 double-click) works only if the chain's start is a mesh point;
  starting in space, the double-click only lifts and the status says why.
- **S4d** A segment with **both** ends in space is valid and cuts everything visible it crosses; a segment that crosses
  nothing is accepted and cuts nothing (the status says so).
- **S5** The Lab keeps working; its Q5 behaviour stays identical after the move (S1 precedent: move, not copy).

**Parity row P10 flips — an intended change:** "edge → edge, faces share nothing" was "Production refuses" (S2 / S3 parity
matrix, `ONE_KNIFE_PROMOTION_DISCOVERY.md` §1.3); with S4 Production **plans across** like Q5.

### WP-KNIFE-01 S4 — open points (recorded, not decided)

| # | Observation | Pinned by |
|---|---|---|
| S4-a | **Depth of a space point** = the camera-target plane (Blender-like). A different plane (e.g. the depth of the last mesh point) is a later question. | — |
| S4-b | **Closing a chain that starts in space** (S4c default: not possible; the double-click only lifts). | — |
| S4-c | **A space-point segment grazing the silhouette:** which stretch counts as visible (the planner's per-crossing occlusion test decides; a crossing exactly on the silhouette edge may fall either way). | — |

**Inherited Lab limits (recorded, not fixed here):** S3-i (where a piece ends next to a gap on curved surfaces);
projection vs. render on warped faces (S3b-b); a bridge may cut another loop (S3b-a).

Build record, evidence and the practical test: below, after the build.

### S4 — build (2026-10-02, headless + xvfb, not Artist-tested)

**What changed** (commits "Move the Q5 segment planner to src …", "S4: KnifeTool plans …", "S4: Application …";
PROVISIONAL until Manu's verdict):

- **Planner moved, not copied:** `playground/experiments/knife_face/planner.py` → `src/mirai/topology/knife_planner.py`
  (the old path is a one-line re-export shim; `engine_q5.py` imports from `src`); `knife_pick.edge_t_3d` is a public alias,
  so the planner needs no private import. Gate (before any behaviour change): `playground/tests` identical, the S1 golden
  net byte-identical, the new cross-face golden (Lab Q5) identical, the integrity probe identical.
- **`KnifeTool`** (`knife.py`): `set_view(camera, width, height, cache=, occlusion=)`; without a view a segment across faces
  stays refused (`CROSS_FACE`, now worded "no camera view" — it said "not yet"). `_plan_segment`: when no face holds the
  straight line (or an end is in space) the planner gives the visible crossings; `nodes = [last] + crossings + [target]`,
  one entry per stretch — a cut, or a break `edge` / `gap` / `space` — crossings stored as records with `crossing=True`
  (their `pid` given by the click), the target last; one click with k crossings is one in-session step. `KnifePlan` carries
  `crossings` (positions), `lines`, `skipped`, `hidden`, `method`. Closing counts clicked points only (crossings do not
  count, Q5's `_clicked`); a planner crossing on a vertex is no earlier vertex point (Q5's `_vertex_entries`); crossings
  and space points are not own-point targets (`snap_points`).
- **Points in space:** `{"kind": "space", "position"}` (`knife_pick.space_point`: the click's ray ∩ the plane through the
  camera target, normal = view direction). The stretch from or to one is a break with reason `space`; `commit` hands the
  resolver the path **without** the space records, the breaks stay — **`knife_resolve.py` unchanged**. A chain started in
  space cannot be closed: `plan_lift(close=True)` lifts with "not closed: the chain starts in space" (S4c). The planner plans
  a segment with a space end by PLANE alone (a space point lies in no face; the Lab never passes one, so Q5 is unchanged).
- **`knife_preview.py`:** a space record gets no marker and no segment; it can be the start point (the rubber band runs
  from it) and the prospective point; new field `prospective_crossings` (the hover's planned crossings).
- **`Application`** (knife section): `_knife_pick` sets the live view (camera, viewport size, the shared `PickCache`,
  `occlusion = display.show_faces`) on the tool before every hover / click plan, snaps own points over `snap_points`, and
  turns an outside pick into a space target; `_knife_lift` sets it too (a double-click's close may run across faces). The
  hover previews through `KnifeTool.plan`: the rubber band to the cursor (also over empty space) and the planned crossings
  as preview dots. `_knife_release`: the UX2 "outside = no-op" branch is gone. Status (PROVISIONAL wording): "Knife: start
  point set in space", "Knife: point in space - N crossing(s) (M path segments)" / "… - the line crosses nothing …",
  "Knife: cut across N crossing(s) (M path segments)", appended with "; ": "N hidden crossing(s) not cut", "skipped: over a
  hole, border or hidden part", "skipped: along an existing edge". Start hint: "Knife: click on vertices, edges, inside faces
  or outside the mesh to cut - a far click cuts across faces, Shift+click = edge midpoint, E / right-click = new cut (pen
  lift), double-click = close + lift, Enter = commit, Esc = cancel, Ctrl+Z / Ctrl+Y = undo / redo".
- `src/main.py`: usage text only. Viewport / overlay code: **untouched** (no new layer; see S4-d).
- Size: Part B production diff (without the planner move) +222 / −50 raw, ≈ +192 / −49 non-blank code lines — inside ~450.

**Evidence `[TEST]`:**

- **Golden oracle** `playground/tests/golden/knife_cross_face.json` + `knife_cross_face_golden_driver.py` (recorded from the
  Lab's Q5 *before* the move): 48 sequences with fixed cameras — grid (task 1–3, 6 quads, vertex pass-through / no
  over-snap, hole, occluder with occlusion on / off / switched, along an edge, loops over 4 quads from an interior / a
  boundary / a vertex start, continue from the seed, earlier edge / vertex points, retrace, k-crossing undo / redo, the
  plane planner's vertex hit, the concave face, orbits, crossing an earlier cross-face cut), cube (2 and 3 faces, interior
  to interior, Manu's tail join as clicked, a bow-tie across faces, cyclic close across 3 faces and continue, earlier point,
  a hidden back edge, orbit, wireframe) and 14 seeded head sequences (walk and plane, hidden crossings up to 17 per click,
  gaps, orbits, a close). `test_knife_cross_face_golden.py`: the Lab replays every one identically **and Production
  reproduces every one** (written as strict xfail first; 47 needed the planner).
- **Differential** (`knife_q5_differential_driver.py` now takes a view, `("cam", …)` / `("occl", …)` / `"commit"` steps and
  compares the planner's result per click): `test_cross_face_sequences_with_a_view_match_q5` — **0 differences** in all
  48 (every step's path, every planned crossing, mesh, History, residue, resolution). The single-face differential, the
  documented S2 differences and the seeded random sessions are unchanged.
- **Production counterparts** `tests/test_knife_cross_face.py` (47): the Q5 tests `test_far_click_crosses_any_number_of_faces`,
  `test_hole_visible_pieces_cut_gap_skipped_hud_note`, `test_no_run_is_connected_across_a_gap`,
  `test_one_hit_face_at_a_piece_end_is_not_cut_and_the_hidden_crossing_is_counted`,
  `test_without_occlusion_nothing_is_hidden_and_nothing_skipped`, `test_crossing_dots_and_lines_in_hover_plan`,
  `test_cross_face_target_without_a_view_is_rejected`, `test_boundary_start_loop_across_faces_closes_fully`,
  `test_interior_start_loop_over_four_quads_closes_without_bridges`,
  `test_continuing_from_the_seed_does_not_connect_across_the_closed_loop`,
  `test_earlier_point_click_is_one_undo_step_with_its_crossings`,
  `test_click_on_an_earlier_edge_point_across_faces_connects_and_continues`,
  `test_the_last_point_and_planner_crossings_are_not_earlier_points`, `test_one_click_with_k_crossings_undoes_as_one_step`,
  `test_plane_planner_reports_a_vertex_hit_not_an_edge_end`, `test_straight_line_out_of_a_concave_face_is_planned_across_faces`,
  `test_planner_with_pick_cache_gives_the_same_crossings_as_without`; the space-point spec (absolute, no Lab oracle):
  `test_space_point_lies_on_the_click_ray_and_on_the_camera_target_plane` (3 cameras, panned target),
  `test_mesh_start_then_a_click_in_space_cuts_the_visible_faces_up_to_the_last_crossing` (= the same cut by two mesh
  clicks, one History entry, one Undo), `test_both_ends_in_space_cut_every_visible_face_in_between`,
  `test_a_space_segment_that_crosses_nothing_is_accepted_and_commits_nothing`, `test_a_chain_never_touching_the_mesh_commits_nothing`,
  `test_start_in_space_then_a_mesh_point`, `test_orbiting_between_clicks_keeps_the_space_points_world_position`,
  `test_undo_redo_lift_esc_with_space_points`, `test_space_points_are_no_snap_targets_and_no_earlier_points`,
  `test_a_mesh_started_chain_with_a_space_point_closes_but_not_cyclically`,
  `test_a_chain_started_in_space_cannot_close_the_double_click_only_lifts`, `test_wireframe_space_line_cuts_everything_under_it`,
  `test_space_records_never_reach_the_resolver`, `test_random_sessions_mixing_mesh_and_space_clicks_stay_sound` (12 seeds,
  4 cameras, orbit, occlusion on / off, undo, lifts); Production-only: `test_orbit_between_clicks_does_not_change_a_placed_cut`,
  `test_a_pen_lift_between_cross_face_chains_commits_both_as_one_entry`, `test_finish_chain_closes_across_faces`,
  `test_a_midpoint_start_followed_by_a_cross_face_segment`, `test_a_crossing_on_a_vertex_is_not_found_as_an_earlier_vertex_point`.
- **Application** `tests/test_application_knife_cross_face.py` (16): hover over a far target (crossing dots in the preview
  layer = the stored crossings after the click), a face / edge sharing no face with the start, the status naming hidden
  crossings, orbit between clicks, wireframe vs shaded, a double-click closing across faces, a Shift midpoint start then a
  cross-face segment, hover in empty space with and without a last point, the space click (no marker, no outside stretch,
  the cuts stay, the next rubber band starts at the space point), both ends in space + `Enter` + `Ctrl+Z`, "crosses nothing",
  undo / redo / `E` / `RMB` / `Esc` with a space point, the double-click after a space start ("not closed … space"), Shift has
  no effect on a space point, the start hint.
- **`[PROBE]`** `knife_integrity_probe.py --production`, new section "far + space" (the click's camera on the
  Production Knife, a quarter of the clicks anywhere on screen = points in space, occlusion on and off): grid 1/400 each,
  cube **0/400** each, head **0/40** each. The one grid failure (seed 210, a zig-zag of 7 clicks ending in space: a
  zero-area / non-simple face) is **inherited**: the same cut with the space click replaced by a click on its last visible
  crossing fails identically in the Lab's Q5 (the probe now checks that itself, `_q5_twin_fails`). The commit check
  (`check_commit`) does not catch that face class — a resolver matter, not touched (S4-i). On the head the probe ignores
  `tri_area` (the untouched head has 302 such faces: non-planar quads). The first part of `--production`, the default run
  and `--cases` are byte-identical to `beec01d`.
- **Hover cost** (`Application.pointer_motion` on `head` during a session with two points, occlusion on, pick cache on,
  1280 × 800, a 40 × 25 grid over the head's screen bbox incl. empty space around it, 5 rounds; this container, three runs
  each): default framing **before S4** p50 0.62 / 0.69 / 0.64 ms, p95 1.17 / 1.51 / 1.18 ms → **S4** p50 2.79 / 2.79 / 2.61 ms,
  p95 6.50 / 6.44 / 5.89 ms; zoomed (dolly 0.6) before p95 1.42–1.53 ms → S4 p95 6.37–6.51 ms. Under the 8 ms STOP line; the
  pick cache is not rebuilt per hover (one signature change in 5 000 hovers). The cost is the planner: the plane planner's
  per-hit occlusion test, mostly for hovers over empty space (a space end is planned by PLANE).
- Suites (Linux + xvfb, libEGL here): `tests` (without `test_extrude_tool`) 1525 → 1588 passed; `tests/run_core_suite.py`
  PASS; `playground/tests` 1090 → 1235 (+145: the cross-face golden and differential); `experiments/symmetry_lab/tests`
  246 → 246; S1 golden `--check` identical.

**Changed old tests** (reason: "S4: decided behaviour change, Manu 2026-10-02" — AD-017 addendum "S4", the P10 flip):
`test_application_knife.py` — `test_start_and_path_stay_drawn_while_hovering_elsewhere` (hover outside now previews a point
in space), `test_a_face_the_last_point_does_not_touch_is_planned_across_faces` and
`test_edge_sharing_no_face_with_start_is_planned_across_faces` (were "… has no preview and click does nothing"),
`test_outside_hover_previews_a_point_in_space_and_leave_clears_it` (was "… has no preview …");
`test_application_knife_pen_lift.py` — `test_a_click_outside_the_mesh_adds_a_point_in_space_and_never_commits` and
`test_a_click_outside_on_an_empty_session_starts_the_chain_in_space` (were the UX2 no-op tests), the start-hint test (the hint
names outside clicks again, as cut points), the far-edge hover in `test_two_chains_with_a_lift_…` (planned across now);
`test_application_knife_shift_preview.py` — the UX2b sweep also counts space targets (the A2 invariant holds for them);
`test_knife_parity.py::test_p10_…` — docstring only (headless without a view it still refuses);
`playground/tests/test_knife_q5_differential.py` / the driver — the no-view refusal text.

### WP-KNIFE-01 S4 — open points from the build (recorded, not decided)

| # | Observation | Pinned by |
|---|---|---|
| S4-d | **Preview style:** Production has two tool styles (hover / selected). The hover shows the straight rubber band (also over empty space) and the planned crossings as hover dots; it does **not** draw the skipped stretch in a distinct "no cut" style as the Lab does (grey-blue) — that needs a third tool layer (viewport / overlay change, beyond the handoff's minimum). After the click the skipped and outside stretches are simply not drawn; stored crossings are drawn as placed points (selected style; the Lab draws them as yellow dots). | `test_hover_over_a_far_target_previews_its_crossings_and_the_click_stores_them`, `test_a_click_in_space_adds_a_point_and_only_the_cuts_stay_drawn` |
| S4-e | **Hover cost rose ~4×** on the head (p95 ~1.3 → ~6.4 ms here; reference PC not measured). Within the STOP limit; hovers over empty space dominate (PLANE + occlusion per hit). A cheaper space hover (e.g. no plan while the cursor is far from the mesh) would change what the preview shows — not done. | numbers above |
| S4-f | **The space stretch is its own break reason (`space`)**, not `gap`: the commit's "N stretch(es) skipped" counts holes / hidden parts / edges only, so an outside click does not add a "skipped" note at `Enter`. Interpretation of "a gap-type stretch" (handoff). | `test_space_records_never_reach_the_resolver` |
| S4-g | **Closing count:** points in space count as clicked points for "closing needs at least 3 points" (crossings do not, as in Q5). A chain started on the mesh that holds space points closes non-cyclically (a stretch is skipped). | `test_a_mesh_started_chain_with_a_space_point_closes_but_not_cyclically` |
| S4-h | `KnifeTool` keeps the last view between `set_view` calls; `Application` sets the live one before every hover / click / close, so no stale camera is used. The Playground `knife` family sets no view: cross-face stays refused there (families untouched). | — |
| S4-i | **Inherited:** a zig-zag session can leave a zero-area / non-simple face that the commit check does not catch (grid seed 210 of the far-click fuzz; Q5 identical with a mesh click). Resolver / commit-check matter (S3-i family), not touched. | `knife_integrity_probe.py --production` |
| S4-j | Status texts (PROVISIONAL wording) as listed above; the hover itself names nothing (the Lab's HUD names skips while hovering) — the status line speaks at the click. | `test_the_status_names_hidden_crossings_and_skipped_stretches` |
| S4-k | Not run in a real window on the reference PC: the GL overlay test (`test_gl_knife_overlay.py`) passes under xvfb; the hover cost was measured headless in this container. | — |

**Rollback:** S4 is one revertable commit series after "Records: S4 …" (spec, planner move, `KnifeTool`, `Application`,
docs); reverting the two "S4:" code commits restores refusal of cross-face segments and the UX2 outside no-op (re-add the
xfails of the spec commit), reverting the move restores the Lab-only planner.

**Prepared practical test (Manu, ≤ 5 minutes, `python3 src/main.py`, cube — `python3 src/main.py cube` — then head, default
camera):** S4 stays **PROVISIONAL** until these slots and the verdict are filled.

| # | Check | Expected | Seen (Manu) |
|---|---|---|---|
| 1 | `C`; click an edge on the top face, then an edge on the **front** face far away (no clicks in between); `Enter` | the cut runs through every face in between; one `Ctrl+Z` removes it all | passed|
| 2 | The same on the head, from the nose side to the cheek across several faces | while hovering, dots mark the crossings; the status names them after the click |passed |
| 3 | A line that runs over a gap / the silhouette | only the **visible** part is cut; the status says what was skipped / hidden | passed|
| 4 | Click a far point, **orbit the camera**, click the next far point | the first cut stays as placed |passed |
| 5 | Switch to Wireframe (`D` until Wireframe, before `C`), the same far click | it now cuts everything under the line (nothing hidden) |passed |
| 6 | A loop across several faces: click the chain's start again (snaps) | it closes without bridges across faces; the next click continues from the closing vertex; `E` / double-click still work | |
| 7 | Hover over the head | stays smooth |passed - it´s ok, but the circle follows delayed when you mouve the cursor quickly, but still passed, we can optimze that later|
| 7a | **Empty space:** `C`, click an edge on the cube, move the cursor **off the model**, click there | the line follows the cursor over empty space; after the click the part outside **disappears**, only the cut on the model remains (status: "point in space"); `Enter` commits; `Ctrl+Z` reverts it |passed |
| 7b | Click outside **left** of the model, then outside on the **right**; `Enter`. Same on the head. A click outside whose line crosses nothing | the line cuts across the model (visible faces only); "crosses nothing" cuts and commits nothing |passed |
| 7c | Click outside, **orbit**, click on the model; `E` / `RMB`, double-click, `Esc` | the first point stays where you set it; the keys behave as before; a click outside never commits |passed |
| 8 | Replay the recorded Q5 sequences ("One Knife S1" practical test above: bow-tie, tail join as clicked, closed shape then continue) | the results match the Playground Q5 (bow-tie `V:13 E:21 F:10`, tail join `V:14 E:22 F:10`) |passed |

| Verdict (KEEP / ITERATE / REJECT / UNKNOWN) | KEEP |
|---|---|
| | |
