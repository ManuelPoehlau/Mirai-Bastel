# Independent Review — AD-022 "GPU ID-Buffer Picking" (PROPOSED)

> **Reviewer:** Claude (claude.ai/code, fresh session, no prior chat or plan context)
> **Review ID:** CLAUDE-001
> **Target path:** `docs/archive/viewport_v02/reviews/AD-022_REVIEW_CLAUDE_001.md`
> **Repository state reviewed:** branch `claude/architecture-audit-summary-2026-10-20` @ `f25fe6a`
> (`f25fe6a8cbf3db579d421bfb29cd1d78afce390e`, "docs(intake): record Manu's B5a.1 verdicts (a) and (c) of 2026-10-20").
> **Subject:** `docs/architecture/AD-022-GPU-PICKING.md` (PROPOSED 2026-10-17, status note 2026-10-20)
> **Type / Mode:** independent review of a decision draft · M5 Discovery · no source, test, AD or other doc edited
> **Status:** Archived first-pass review — preserved verbatim; answers belong in AD-022
>
> This document is intentionally preserved as the original independent review. Do not edit it to
> reflect later decisions (AGENTS.md §6).

Evidence tags: **VERIFIED (code)** = read at `f25fe6a`, `file:line`; **VERIFIED (probe Pn)** = a throwaway review
probe, code and output in the appendix; **VERIFIED (raw)** = recomputed from the committed reference-PC raw output
`experiments/gpu_picking_spike/RESULTS_REFERENCE_PC_2026-10-20.md`; **UNVERIFIED** = not checked here; *(reading)* =
my interpretation. **[RPC]** marks reference-PC numbers (Manu's runs). Every number I produced myself is a
**container number** (Linux, Intel Xeon @ 2.80 GHz, Python 3.13.16, Xvfb + Mesa 25.2.8 llvmpipe, GL 4.5 core,
pyglet 2.1.19) — not a reference-PC result (REFERENCE_HARDWARE.md §4). I did not repeat any timing measurement.

---

## What was read, what was run

**Read in full:** AD-022; AD-023; `experiments/gpu_picking_spike/` (`README.md`,
`RESULTS_REFERENCE_PC_2026-10-20.md`, `id_picker.py`, `probe_gpu_picking.py`, `_paths.py`, `tests/`);
`src/mirai/viewport/picking.py`, `picking_cache.py`, `box_select.py`; `REFERENCE_HARDWARE.md`; `AGENTS.md`;
`MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` §4–§6.

**Read in part:** `experiments/drag_cost/README.md` ("Navigation and picking" incl. hypotheses, fix options and
reference-PC result; "Audit at HEAD"; "Result: fix slice 1"; "Result: fix slice 2"; "Topology ops"; "Result:
topology operations, reference PC"; "Haltepunkt"); `VIEWPORT_V02_ARCHITECTURE.md` §1, §4.5, §4.6, §5.1–§5.4, §11,
§12, §14–§16; `VIEWPORT_V02_RESEARCH.md` §12–§13, §21; AD-018 §5 (binding constraints, "not decided") and §7 with
all addenda; AD-021 (grep for picking: RF-2, RF-3, RF-6, RD-4, E-7, E-10, "no object hover"); `CORE_V1_FREEZE.md`
(grep: viewport/picking — nothing applies); `WP-06_INTAKE_LOG.md` entries of 2026-10-20;
`src/mirai/application.py` (pick, hover, coalescing, Box/Paint, Tweak, Knife pick, object pick, topology/undo
notifications, `update_viewport`); `src/mirai/topology/knife_pick.py:100-280`, `knife_planner.py:1-140`;
`src/viewport/viewport.py` (module docstring, H7, `sync`, `render`), `render_mesh.py:1-360`,
`gl_render_store.py` (docstring, shader notes, `_rebuild_vertex_list`, `vertex_list`, `draw`); `src/main.py`
(window, resize, `on_draw`, `run`); `tests/test_picking_equivalence.py:1-60`; `mirai/viewport/camera.py` (docstring,
fields); pyglet 2.1.19 `IndexedVertexDomain.draw_subset`; the format precedent `AD-020_REVIEW_CLAUDE_001.md`.

**Not read (as instructed):** `docs/research/viewport/ARCHITECTURE_AUDIT_2026-10-20*.md`,
`experiments/architecture_audit_probes/`, `docs/ATELIER.md`, `docs/research/README.md`. No content of these was
opened. One repository-wide `grep -rln` (for `PickCache` users) printed file *names* only, truncated at 20 lines;
I did not open any audit file.

**Run (container):** spike tests `xvfb-run -a pytest experiments/gpu_picking_spike/tests` → **18 passed**;
`pytest tests/test_picking_equivalence.py` → **19 passed**. Probes P1 (agreement decomposition, close zoom), P2
(option-B2 mechanism), P3 (Box percentages from the [RPC] raw output) — appendix.

---

## Verdict

**ACCEPT WITH CHANGES — AD-022 is usable as a decision basis after one blocker (F1) and the major findings are
addressed in its text.** This is not a verdict on which option to choose.

What holds up:

- The problem statement is right and, on the reference PC, *stronger* than the AD says: after an orbit the CPU
  picker costs 150–188 ms [RPC] on `gollum_20k`, not "~60–70" (container), and even a hover with a valid cache is
  8–43 ms [RPC]. The camera-dependent `PickCache.refresh` (all V projected, all face bboxes) is the cause
  (VERIFIED (code) `picking_cache.py:80-118`).
- The spike is honest about its scope and its README transcribes the [RPC] raw output correctly (every number I
  checked matched, see "Code and data facts checked").
- The cost case for B is clear on the reference PC: pick after an orbit 150–188 → 2.4–3.8 ms, Box 300 px
  2.4 s → 85–89 ms on 21.9k [RPC].
- Hover/click differences are, for framed views, the neighbour in the same pixel: P1 shows the GPU's pick is at
  most 0.73 px farther from the cursor than the CPU's.

What is not ready:

- **F1 (blocker):** §1, §2, §6 still present the container run as the evidence. The reference-PC run that decides
  the question appears only as a German status note in §8. Several §2 claims are narrowed or contradicted by it.
- The B2 recommendation rests on an unbuilt mechanism and on a visual check that cannot detect small ID errors.
  It also collides with an explicit AD-018 binding constraint and a recorded rejection (F3).
- A stale-buffer ordering hazard is unnamed (F4).
- The options are not compared on equal terms (F5).
- The contract list (F6) and the AD-023 interaction (F7) are incomplete.
- The Artist questions are partly technical, and one cannot be answered yet (F9).
- §9 has no abort criterion (F10).

| Q | Verdict | One line |
|---|---|---|
| 1 Evidence | **partly** | the [RPC] run supports the cost claims, but the AD cites the container run; samples are p50-only, n = 8–15, one window size, two framed cameras (F1, F2, F11) |
| 2 Comparability | **mostly fair, gaps** | the half-pixel classification is fair; ~⅓ of the "same" cursors are trivial misses; Box-depth 0–4 % holds only for the front camera (up to 6.5 % from the back); no close-zoom, scale, resize or in-loop case (F2) |
| 3 Options | **incomplete** | A's advantage (no semantic change) and B1's editing cost (0.8 s per op [RPC]) are not stated; status quo and the earlier NumPy rejection are missing; "B2, else B1" is a preference, not derived (F3, F5) |
| 4 Contracts | **incomplete** | AD-018 binding constraint and §7 rejection; VIEWPORT_V02 §5.2–§5.4, §7, §14–§16; RESEARCH §13/§21; AD-021 RD-4/RF-2/RF-6; H7; AD-020 8 ms bar (B1); app-level tests (F6) |
| 5 Risks | **incomplete** | §6 is stale ("llvmpipe only"); stale ID buffers after ops (F4), mixed GPU-ID / CPU-math paths (F8), attribute locations (F3), tails and in-loop stall (F11) are missing |
| 6 AD-023 | **claim wrong** | "AD-022 does not change this table" is false in both directions (B2 removes 4–13 %, B1 adds ~0.8 s per op [RPC]); the buffer contract must be decided jointly (F7) |
| 7 Slices | **reorder / add criteria** | reversible behind a switch, yes; but there are more call sites than slice 1 names, Paint is implicitly in slice 1, and no abort criterion exists (F10) |
| 8 Artist questions | **revise** | Q1 is partly technical; Q2 asks for a verdict with nothing playable; four Artist-only questions are missing (F9) |
| 9 Readiness | **close** | text changes + one ~1-minute [RPC] check for B1/B2; the rest can follow the decision inside slice 1 with abort criteria (see R9) |

---

## Answers to the review questions

**R1 — Evidence.** The cost claims of §2 are directionally confirmed by [RPC] and in some rows exceeded (pick
after orbit 3.3 ms instead of 11–17). But §2 cites only container numbers, and some claims do not survive the
[RPC] data:

- hover is 0.65–4.1 ms [RPC], not "0.06–0.8";
- the 87.5k ID render is 10.3 ms GPU time [RPC], against an expectation of "~1–3 ms";
- the B1 build is 0.8 / 3.1 s [RPC], not 0.2 / 1.1 s;
- Box-depth is up to 6.5 % off, not "0–4 %";
- the ids-Box loses up to 37 %, not "a third".

Status of each claim:

| Status | Claims |
|---|---|
| [RPC] | everything in the README section "Result: reference PC" |
| Container | AD §1, §2, the README container table, the topology table of AD-023 §1 |
| Hypothesis | B2 works on the 9800 GTX; read-back cost in the real frame loop; Knife/Paint/object/snapping via IDs; per-object ID spaces |

Samples:

- p50 only, n = 15 (n = 8 on 87.5k); Box cost n ≤ 5 (`probe_gpu_picking.py:324`); build n = 1, including the
  shader compile and FBO creation (`:408-410`, `id_picker.py:113-115`).
- One hidden 1024×768 window, two framed cameras (`probe_gpu_picking.py:167`).

This is enough for the direction (the gaps are 40–50×). It is not enough for a frame-budget claim, which needs
tails, or for 87.5k editing (F11).

**R2 — Comparability.**

- *Fair:* the face pick samples the pixel centre (`id_picker.py:431-434`), and the probe counts a difference as
  `half-px` only when the CPU agrees at (x + 0.5, y + 0.5) (`probe_gpu_picking.py:124-130, 196-198`). Same pick
  radii as the CPU (14 / 9 px). No back-face culling in either picker (`id_picker.py:6-8`, `picking.py:256-281`).
- *Inflated denominator:* cursors are drawn from the mesh's screen bbox (`:155-158`) and both-`None` counts as
  "same" (`:141-142`). In P1, 34–47 % of the cursors are trivial misses. On the non-trivial ones, gollum_20k
  agreement is vertex 95.8–97.5 %, edge 91.8–96.2 %, and face 71.2–79.5 % (+ half-px) (VERIFIED (probe P1)). The
  conclusion survives: every "real" difference is ≤ 0.73 px farther on framed views. The percentages shown to
  Manu should use the non-trivial denominator.
- *Silhouette / tolerance:* CPU visibility uses `DEPTH_TOLERANCE = 1e-3` **world units** (`picking.py:69`). The GPU
  uses a slope-scaled polygon offset in depth units. The two scale differently with mesh size and camera distance,
  and the spike tests one scale and two framings *(reading)*. At 4× zoom P1 finds visibility differences, not
  pixel sharing: a vertex 7.2 px farther, an edge 0.97 px *nearer*, and four "one side None" cases. The depth
  oracle removes them.
- *Not covered:* close zoom (beyond P1's one setting); camera near or inside the surface; other mesh scales;
  window sizes other than 1024×768; HiDPI; resize; placed objects; H7 surfaces; B2 itself (the agreement numbers
  are for B1 — P2 shows B1 and B2 pick different winners in ~70 shared vertex pixels per view); Knife; Paint;
  object pick; in-loop timing.

**R3 — Options.** Not complete and not fully fair (F5).

- A has a property no B variant has: the same picks, so no Artist check. The AD does not say so.
- A's "moves cost to editing" applies equally to B1 (795 ms per mesh state [RPC], comparable to A's 0.65 s
  container build).
- Missing alternatives: **status quo** (the cost of doing nothing, per camera change [RPC]) and **NumPy-vectorised
  projection**. NumPy was rejected earlier for a dependency and CPU-baseline reason (drag_cost "Fix options", last
  row); M1 asks for that reason to be recorded here.
- "B2, else B1" is an engineering preference. The evidence only measured B1, and B1's measured cost is what
  argues against it. B2 is not built (F3).

**R4 — Contracts.** §5 is correct as far as it goes, and the Freeze is unaffected: nothing under `src/core`
(VERIFIED (code): GPU picking needs no Core API; staleness is handled through the existing invalidation points).
The full list is in F6.

**R5 — Risks.** §6 names four risks; one of them is stale. Missing:

- stale ID buffers after ops, undo or W commit (F4);
- mixed GPU-ID / CPU-math paths (F8);
- the attribute location of a second program over the store's VertexList (F3);
- the read-back stall in the real loop, and the tails (F11);
- headless tests that never reach the GPU path (F13);
- binding picking to how a thing is drawn (RD-4) (F6);
- the planned hardware upgrade changing the driver landscape (F9).

Under-weighted: Box-depth adds elements (more "+" than "−"), so the visible change is "selects a few % more at
grazing angles". That is the opposite of the "ids" failure.

**R6 — AD-023.** See F7. The topology table *does* change. Decide jointly: the AD-018 buffer contract (B2 and V1
share the index buffer, the triangle → face-row map and a new edge index buffer); B1 vs. B2 (B1's per-op build
conflicts with AD-023's goal); the sync/hover ordering (F4, V2). Independent: history H0–H2; the §4 semantic
checks.

**R7 — Slices.** Reversible behind a switch and testable under Xvfb, yes. But:

- slice 1 implicitly includes Paint (`_paint_at` uses `_pick`, `application.py:3734-3735`), so slice 2's "Paint
  through the depth oracle" is moot as written;
- the Box-start face pick (`:3699-3709`) and the Tweak press pick (`:3814`) are not listed;
- slice 1 needs the ordering fix of F4 first.

Abort criteria: F10.

**R8 — Artist questions.** See F9.

**R9 — Decision readiness.**

*Before deciding the direction (A / B / status quo):*

- F1 (update the evidence);
- F5 (fair option table, including status quo and the NumPy reason);
- F6, F7 (contracts, AD-023);
- F9 (questions).

All four are text only.

*Before choosing B1 vs. B2:*

- one [RPC] read-back check that `gl_PrimitiveID` gives exactly the B1 face IDs per pixel (P2 is that check,
  ~1 minute to run);
- the AD-018 placement decision (F3).

*After the decision, inside slice 1, with abort criteria:*

- in-loop read-back on the reference PC, with p95 / max (F11);
- the ordering fix (F4);
- the call-site inventory (F10);
- a playable switch for Manu's §4 check (F9);
- the tests (F13).

*Slice 3:* the Knife convention (F8).

---

## Findings

Severity: **blocker** = change before the AD is put to Manu; **major** = resolve in the text, or answer, before
DECIDED; **minor** = wording or slice detail.

### F1 — The evidence section is the container run; the decisive reference-PC run is a side note (blocker)

**Evidence.**

- AD §2 heading: "spike, container - llvmpipe, the 'GPU' is the CPU" (`AD-022:39`). All §2 figures are from the
  container table of the README.
- The [RPC] run of 2026-10-20 appears only in §8 (`:137-140`, German), and §6 still says "measured only on
  llvmpipe so far" (`:123-124`).
- §1 uses container numbers (`:27-37`).

[RPC] corrections (VERIFIED (raw)):

| AD claim | [RPC] | Effect |
|---|---|---|
| pick after orbit 42–74 → 11–17 ms (20k) | 150–188 → **2.4–3.8 ms** | B stronger |
| ID render "~1–3 ms expected - not measured" | 1.14 ms GPU / 1.43 wall (20k); **10.3 / 10.8 ms (87.5k)** | 87.5k is about one frame per camera change |
| hover 0.06–0.8 ms "on both sizes" | **0.65–1.96 (20k), 0.65–4.1 (87.5k)** | not sub-millisecond; grows with density |
| B1 build 0.2 / 1.1 s | **795 / 3 087 ms** (n = 1, incl. compile) | B1 ≈ +0.8 s per topology op / undo on 20k (F7) |
| Box 0.87 s → 24 ms; 6.9 s → 78–92 ms | 2 384 → **85–89 ms**; 14 522 → **295–332 ms** | B stronger; 87.5k Box still ~0.3 s |
| §1 "~60–70 ms per frame" | CPU pick after orbit 150–188 ms; hover 8–43 ms | problem understated |
| "loses up to a third" (ids Box) | up to **37 %** (87.5k front 150 px edge) | wording |
| "depth-oracle within 0–4 %" | **up to 6.5 %** (gollum_20k back 300 px face, −0.8 / +5.7 %) (P3) | Artist-visible direction: selects more |

**Change.**

- Rewrite §1/§2 with [RPC] as the primary column and container as the comparison. Tag each number.
- Replace "~1–3 ms expected" with the measurement. Update §6's first risk.
- Move the §8 status into §2 in English (AGENTS.md §4b: canonical docs are English, not logs).
- State in §2 the sample sizes and that only p50 exists.

### F2 — Agreement figures need the non-trivial denominator and the back-camera Box rows (major)

**Evidence.**

- Trivial both-None cursors are counted as agreement (`probe_gpu_picking.py:141-142, 155-158`). P1: 103–140 of
  300 per row on gollum_20k framed.
- The non-trivial agreement is given in R2.
- "Every difference is the neighbouring element in the same pixel" (`AD-022:49-50`): holds for framed views
  (P1: ≤ 0.73 px). It does not hold at close zoom (P1: 7.2 px, the opposite sign, and None-vs-element). On the
  head [RPC] there are 2 "gpu none" cases.
- "Face picks differ only by the half-pixel convention": on the body [RPC], 4 of 600 are real differences.
- Box: see the F1 table.

**Change.**

- Report agreement over non-trivial cursors.
- Qualify the neighbour claim as "framed views".
- Add the close-zoom observation and the depth oracle's fix for it.
- Give the Box-depth range across both cameras, and state that the deviation is mostly *additional* elements.
- Name the untested axes: scale, zoom, window size.

### F3 — B2 is unbuilt, its driver evidence is weak, and its placement collides with AD-018 (major)

**Evidence.**

- *Placement.* AD-018 §5 binding constraint: "Not a general GPU resource manager … no registry, no render graph,
  **no pluggable passes**" (`AD-018:206-209`).
- AD-018 §7 records the rejection of "A second drawable group inside `GLRenderStore` (breaks its stated one-group
  scope)" (`:469-470`). The store's own docstring says the same (`gl_render_store.py:29-35`).
- AD-022 §3/§5 puts "a second program, an FBO and an edge index buffer" in `GLRenderStore`
  (`AD-022:71-75, 110`). That reverses a recorded decision; it is not merely "an addendum".
- A precedent-conform variant exists and is not offered: an ID pass *outside* the store that draws the store's
  public `vertex_list()` (`gl_render_store.py:604-607`), as the overlays do (AD-018 §7).
- *Where the GPU picker lives.* `Application` is window-free (AD-018 §7, "drawing in `src/main.py` rejected"). The
  AD does not say how a GL picker is injected (cf. the `store_type` / `point_overlay_type` pass-through, E17), or
  that picking then flows Viewport → `mirai`, which the drag_cost note calls "a Viewport service for `mirai`".
- *Mechanism.* P2 (llvmpipe only) draws the production VertexList with a second program:
  - face ID = `gl_PrimitiveID` → `RenderMesh._triangle_face_rows` equals the B1 face target on **786 432 / 786 432
    pixels** for both cameras;
  - points via `gl_VertexID` match except ~70 pixels per view (a different winner in shared pixels, from the draw
    order);
  - the attribute location of `position` was 0 in both programs. That is a driver choice, not a contract. On the
    reference driver an unused attribute was already dropped once (AD-018 §7 hotfix), so B2 needs explicit
    `layout(location = …)` in both programs *(reading)*.
- *Driver evidence.* "Flat without spots" is a visual check. An off-by-k `gl_PrimitiveID` would shade a
  neighbouring face's nearly identical normal on a 20k mesh and stay invisible, while picking needs exact IDs
  *(reading)*. The Flat evidence also covers triangles only; B2's edge pass needs `gl_PrimitiveID` on `GL_LINES`
  (or the wire overlay's two-vertices-per-edge buffer with `gl_VertexID / 2`) and the point pass needs
  `gl_VertexID`.

**Change.**

- List the B2 placement as a choice: (B2-in) inside the store, which reverses AD-018 §5/§7; or (B2-out) an ID pass
  outside the store that reads `vertex_list()` and the face data.
- Name the injection point and the data direction.
- Make "B2 if `gl_PrimitiveID` is reliable" concrete: P2 run on the reference PC, a per-pixel equality check.
- Mark the recommendation as unprototyped.

### F4 — "Hover coalescing fits as is" is wrong: picks run before the buffers are synced (major)

**Evidence (VERIFIED (code)).**

- `update_viewport` calls `flush_hover()` **before** `viewport.sync()` (`application.py:3843-3845`).
- After a topology op `_notify_topology_changed` marks the viewport dirty and re-picks at once (`:2045-2049`).
  Undo/redo does the same (`:3153-3171`), and so does a W commit (`:3294-3298`).
- B2 reads `RenderMesh` buffers, which change only in `sync()` (`render_mesh.py:316-353`). B1's own buffers need
  the same trigger.
- A GPU pick at these points reads the previous mesh state. It returns IDs from the old buffer order, which may
  be dead or different elements.
- The project has a precedent: "a stale hovered/selected ID after a topology change crashed the draw loop"
  (`application.py:3079-3080`).

**Change.**

- Add to §5/§6: the GPU pick requires synced buffers. Either the pick path syncs first, or a pick before the sync
  falls back to the CPU picker, or the post-op re-pick is deferred to the tick after the sync.
- Add a test: pick right after an op and after an undo, with no tick in between.

### F5 — The options are not compared on equal terms (major)

**Evidence.**

- §3A: "moves cost from navigation to editing (collides with AD-023)". B1 has the same property at a similar size:
  795 ms per mesh state [RPC] vs. A's 648 ms container build (drag_cost "Audit at HEAD").
- A's main advantage is not stated: the same rules as today, testable for equivalence on the CPU, and none of the
  §4 differences, so no Artist check. Its unmeasured part (the 14-px frustum query for vertex/edge, the refit per
  W drag; drag_cost "Haltepunkt", option 1) is also not stated.
- No status-quo row: on 20k [RPC] every camera change costs 150–188 ms before the first pick, Box 2.4 s.
- NumPy projection was rejected in drag_cost ("not recommended now": new dependency, Core 2 instruction-set
  risk). It is the obvious fourth option; M1 asks for "X wird nicht verwendet, weil Y" in the deciding document.
- §4.1 says the differences "cannot be avoided by any GPU variant". True, but A avoids them.

**Change.**

- Add a comparison table A / B1 / B2 / C / status quo with these columns: [RPC] navigation cost; per-op cost; per-W-move
  cost; semantic change (yes/no); built/measured (yes/no); contracts touched.
- Add the NumPy rejection with its reason.
- Rephrase "B2, else B1" as `PROVISIONAL` engineering preference.

### F6 — The contract list in §5 is incomplete (major)

Verified against the code and docs; missing from §5:

- **AD-018 §5 binding constraint and §7 rejection** (F3); `gl_render_store.py:29-35` docstring.
- **VIEWPORT_V02** beyond §1/§4.6/§11:
  - §5.3 (hover flow: a render pass enters the hover path);
  - §5.2 / §5.4 / §7 (B1: ID buffers patched on move, rebuilt on topology);
  - §14 (stall risk row);
  - §15 ("Hover event time < 5 ms" acceptance);
  - §16 (future-work item becomes current).
- **VIEWPORT_V02_RESEARCH** §13 / §21 (explicit "no `glReadPixels` hover readback"): needs a dated note.
- **AD-021**:
  - RD-4 "what you can click must not depend on how it is drawn" (`AD-021:748`): the ID pass ignores display
    style. That means no culling, although the production draw culls back faces (`gl_render_store.py:655-656`);
    ghosts and Wireframe-ignoring References are opaque in an object pass; the H7 surface does not replace the cage.
  - RF-2 / RF-6 (`:374, 381`): the component ID pass draws the edit object only.
- **H7 contract** (`viewport.py:88-98`: "Picking ist nicht betroffen"). This answers §8's open "interaction with H7
  surfaces" at the contract level: the ID pass draws the cage, `self.render_mesh`, never `drawn = surface`
  (`viewport.py:657-668`). Whether occlusion *should* follow the shown SubD surface is an Artist question (F9).
- **AD-020 §7 8-ms W-drag bar:** B1 adds patch work per move unless it is deferred to gesture end. Hover is off
  during W (`application.py:3486-3503`), so deferral is possible.
- **Tests:** `test_application_hover_coalescing.py` and all Lab trees run `Application` headless, so they never
  reach the GPU path (F13).
- **CORE_V1_FREEZE:** unaffected. Say so explicitly.

**Change.** Complete §5 with these items.

### F7 — AD-023 interaction: "AD-022 does not change this table" is false; name the joint decisions (major)

**Evidence.**

- AD-023 §1 (`:44-45`) states it.
- With B2 the hover re-pick column (144–254 ms, 4–13 % of an op [RPC]) shrinks to one ID render plus a read
  (≈ 3 ms [RPC] *(reading)*), and the "pick cache + `vertex_faces`" row leaves the window path.
- With B1 every op and every undo also pays the ID-buffer build: 795 ms on 20k [RPC], +25–40 % on today's 1.9–3.6 s
  ops.
- AD-023 V1 (patch indices / face rows with spare capacity) changes the buffers B2 reads. Any spare or dead
  triangle must produce no fragment or map to "no face". The new edge index buffer and the vertex → ID map must be
  patched with them.
- AD-023 P (incremental pick cache) is "moot for the window" only if AD-022 is decided.

**Change.**

- Correct AD-023 §1 and add an AD-022 §5 bullet.
- State that the AD-018 buffer contract (B2 pass + V1 patching), B1 vs. B2, and the sync ordering (F4, V2) are
  decided together.
- State that history H0–H2 and the §4 semantics are independent.

### F8 — The pixel convention is a correctness rule for mixed paths, not only an Artist difference (major)

**Evidence.**

- `knife_pick` takes the face, then computes `face_hit_position(…, sx, sy)` on the CPU. If that misses, it
  returns `{"kind": "outside"}` (`knife_pick.py:179-186`), which the Knife treats as a point in space.
- With a GPU face ID sampled at the pixel centre and CPU math at the cursor, the 13–21 % of cursors that sit on a
  face border [RPC] can yield a face the cursor ray misses. The result is an "outside" target, i.e. a cut in
  empty space, instead of a face point *(reading; not built)*.
- The planner's crossings use `PickCache.vertex_screen` and CPU occlusion tests (`knife_planner.py:54-82`), so a
  Knife session keeps the per-camera rebuild that §1 wants gone.

**Change.**

- §4.2 / §6: one sampling convention for every path that combines a GPU ID with CPU math. Either the CPU math
  uses the pixel centre too, or the ID read honours the cursor's sub-pixel position. Add a test.
- Slice 3: include the planner, or state that Knife sessions keep the CPU rebuild.

### F9 — Artist questions: one is technical, one is not playable, four are missing (major)

**Evidence.**

- Q1 "Direction B … confirmed after the reference-PC run?" asks Manu to choose between A and B. That is mostly an
  evidence-domain question (M4 attention filter). His part is priority, intent and the felt differences.
- Q2 asks whether the §4 differences are acceptable "after a practical check". No playable check exists: the
  spike's practical test is a probe run and a Flat-shading look. M4 says "Wer ein Verdikt anfragt, hat die
  Testsituation vorbereitet."

**Missing Artist-only questions** (each answerable without programming detail):

1. Which mesh size must be fluid **for editing**: 20k only, or also the 87.5k mesh? (87.5k is ~1 frame per camera
   change even with B [RPC]; drag_cost lists the editing target size as open.)
2. Is the 9800 GTX the **floor of the product** or only today's test PC (REFERENCE_HARDWARE §3 open; an upgrade is
   planned, §1)? This sets how much a legacy-driver risk weighs.
3. At the silhouette, should a Box rather take **a few too many** (possibly back-side) elements or **a few too
   few**? The depth variant errs towards more.
4. With SubD/Morph shown (H7), should you pick and see through the **displayed surface** or the **cage**?

**Change.**

- Reword Q1 as a priority question. Keep the technical choice with engineering plus this review.
- Move Q2 to after slice 1, behind a switch Manu can toggle in `src/main.py`.
- Add questions 1–4.

### F10 — §9 has no abort criterion and misses call sites (major)

**Evidence (VERIFIED (code)).** Pick call sites in `Application`:

- `_pick`: hover, click, Paint, Tweak press (`:3559-3580`, `:3734-3735`, `:3814`);
- `pick_face` at the Box/Paint decision (`:3699-3709`);
- `elements_in_rect` (`:3758`);
- `_knife_pick` and the planner;
- `_pick_object` (`:998-1010`).

Slice 1 as written switches `_pick` only. Hover and click would then use the GPU convention while the Box-start
face test uses the CPU one. A highlighted face and the "on mesh?" decision could then disagree at borders.

**Change.**

- List every call site per slice.
- Add a debug mode that runs both pickers and logs divergences in the window (cf. AD-023 §4's debug compare).
- Abort or roll back slice 1 if any of these holds on the reference PC:
  1. first pick after a camera change or a zoom notch, in the real loop, p95 > 16.7 ms on gollum_20k, or any
     read-back hitch > 1 frame;
  2. non-trivial agreement below an agreed floor, or any "GPU none / CPU element" on a visible element in framed
     views;
  3. any stale-ID or crash case after op / undo / W commit;
  4. a GL error or incomplete FBO at start or resize (then the CPU path automatically);
  5. Manu rejects the feel in the switchable practical check.

### F11 — Tails and the real loop are unmeasured; risks §6 does not name them (major)

**Evidence.**

- Only p50 exists (n = 15; n = 8 on 87.5k). The read-back runs in a hidden window with nothing else queued
  (`probe_gpu_picking.py:296-310`).
- In the app the tick pick runs between frames (`main.py:493-505`), so `glReadPixels` waits for the GPU to drain
  whatever is queued. On Windows that can mean waiting on a swap *(reading; UNVERIFIED)*.
- `id_picker.render` sets `glViewport` to the FBO size and does not restore it (`id_picker.py:207`). That is
  harmless in a probe, but the main draw relies on it on resize/HiDPI *(reading)*.
- The window is resizable (`main.py:278, 327-328`). Box read-back grows with the box area; a full-screen Box at
  1920×1080 is unmeasured.

**Change.**

- §6: add tails, the in-loop stall, window size and viewport-state restoration.
- §9: measure them in slice 1 with the `loop` scenario of `probe_navigation_gl.py` on the reference PC (abort
  criterion 1 in F10).

### F12 — Smaller corrections (minor)

- §2 "87.5k 210-233": the container README table tops at 227. The container raw output is not committed, so 233
  is untraceable.
- §2 "97-99 % on body and gollum_20k": gollum_20k edge is 96.3 %, Wireframe edge 92.3 % [RPC].
- Header "(Manu's preferred direction)": Manu said "gpu picking bringt wohl den größten Gewinn", a priority
  statement in reply to the agent's own ranking. Quote it as such (Development System §5: never cite an inference
  as an Artist statement).
- "depth oracle for Box **and Paint**" (§3): Paint samples are hover picks (`_pick`), not Box semantics. Say why
  Paint would differ.
- "retopology snapping (face ID + depth = hit position)" (§5): the snap target is a Reference, which the component
  ID pass must not draw (RF-2). Snapping needs its own Reference pass.
- Small meshes: on head/body the GPU hover is slower than the CPU [RPC] (head 0.85 vs. 0.21 ms). Note it, and
  consider a size threshold.
- The ID pass renders all three targets per camera state. Only the active mode's target plus the face depth is
  needed (87.5k: 10.3 ms [RPC]).
- pyglet is unpinned (`requirements-dev.txt`). B2 relies on `IndexedVertexDomain.draw_subset` (one
  `glDrawElements` per list, which is why `gl_PrimitiveID` starts at 0) and on the sampler-buffer workaround.
  Pin it, or test it.

### F13 — The shipped path would be the least-tested path (minor)

**Evidence.**

- All `Application`-level tests and the Lab trees run headless with `TraceStore`, so they exercise the CPU path
  only.
- GL tests need Xvfb. Without it they are *skipped*, not passed (CLAUDE.md; AGENTS.md §8a).
- llvmpipe differs from the reference driver: line rasterisation, polygon-offset units, attribute handling.
- The [RPC] Box-depth rows match the container rows closely (e.g. gollum_20k 300 px edge −91 / +373 vs.
  −91 / +372), which lowers the polygon-offset concern for these framings (VERIFIED (raw)).

**Change.** §5 tests: known-answer GL scenes (the spike's), a non-trivial agreement floor, a stale-buffer test (F4),
and a one-command reference-PC GL check (P2-style) run once per driver or hardware change.

---

## Code and data facts checked

| AD statement | Result |
|---|---|
| §1 camera-change cost is `PickCache.refresh` over V and F | **correct** (`picking_cache.py:80-118`) |
| README [RPC] table and agreement lines vs. raw output | **correct**: every figure matched |
| §2 container figures vs. README container table | **correct**, except "233" (F12) |
| B2: one VertexList = one `glDrawElements`, `gl_PrimitiveID` from 0 | **correct** for pyglet 2.1.19 `draw_subset`; P2 confirms on llvmpipe |
| B2: shared indexed `positions` (point draw possible) | **correct** (`render_mesh.py:176-206`) |
| B2 needs an edge index buffer | **correct**; the wire overlay is a separate 2-vertices-per-edge list, only synced while edges are shown (`viewport.py:637-643`) |
| §5 "coalescing fits as is" | **incorrect** (F4) |
| §5 "`PickCache` remains for the Knife's exact math" | **correct, incomplete**: the planner also needs it per camera (F8) |
| §5 GL 3.3 suffices | **correct** for FBO, `glReadPixels`, timer query (ran without error [RPC]); `gl_PrimitiveID` / `gl_VertexID` are 3.3 core, driver exactness unchecked (F3) |
| AD-023 "AD-022 does not change this table" | **incorrect** (F7) |
| §8 "interaction with H7 open" | **contract answered** (`viewport.py:96-97`); the Artist question remains (F9) |
| CPU picker has no culling, spike neither; production draw culls | **correct** (`gl_render_store.py:655-656`) |

---

## What I could not check

- Anything on the reference PC: driver exactness of `gl_PrimitiveID` / `gl_VertexID` / `GL_LINES` primitive IDs;
  attribute-location assignment on the NVIDIA driver; the in-loop read-back stall; tails; window sizes; HiDPI.
- Smooth-shading appearance on the reference PC: not reported (Intake Log 2026-10-20).
- B2's edge pass, object-ID pass, per-object ID spaces, placed objects (model matrix), resize, Knife/Paint/snapping
  via IDs: none built.
- A's vertex/edge frustum query: not built anywhere.
- The container raw output behind the README container table: not committed.
- Git history of AD-022 and the spike: the clone is shallow (one commit).
- Whether the Slice-2 reference-PC practical test (drag_cost) was run: no result section found.

---

## Appendix — review probes

All probes live outside the repository (scratchpad). They import the spike and production code unchanged, and run
with `xvfb-run -a python3 -I <probe>` from the repo root. Container only.

### P0 — existing tests

```
xvfb-run -a python3 -m pytest experiments/gpu_picking_spike/tests -q   -> 18 passed in 2.52s
xvfb-run -a python3 -m pytest tests/test_picking_equivalence.py -q    -> 19 passed in 68.96s
```

### P1 — agreement decomposition and close zoom (`p1_agreement.py`)

```python
"""Re-uses the spike's GpuIdPicker and the production CPU picker unchanged. Adds: (a) how many agreeing cursors
are trivial (both None), (b) for 'real' differences the screen distance cursor->CPU pick vs cursor->GPU pick,
(c) the same rows on a zoomed-in camera (camera.dolly)."""
import math, sys, statistics
sys.path.insert(0, "/home/user/mirai-bastel/experiments")
from gpu_picking_spike._paths import ensure_paths
ensure_paths()
import pyglet
from core import SelectionMode, VertexId, EdgeId
from mirai.scene_factory import build_core_scene_from_obj
from mirai.viewport.picking import pick_component, _point_segment_distance
from mirai.viewport.picking_cache import PickCache
from gpu_picking_spike import probe_gpu_picking as probe
from gpu_picking_spike.id_picker import GpuIdPicker

W, H = probe.WIDTH, probe.HEIGHT
win = pyglet.window.Window(width=W, height=H, visible=False)
mesh = build_core_scene_from_obj(probe.REPO_ROOT / "examples/meshes/gollum_20k.obj").mesh
gpu = GpuIdPicker(mesh, W, H)
modes = {"vertex": SelectionMode.VERTEX, "edge": SelectionMode.EDGE, "face": SelectionMode.FACE}

def dist(elem, x, y, cam):
    if isinstance(elem, VertexId):
        p = cam.project_to_screen(mesh.vertex_position(elem), W, H); return math.hypot(p[0]-x, p[1]-y)
    if isinstance(elem, EdgeId):
        a, b = mesh.edge_vertices(elem)
        pa = cam.project_to_screen(mesh.vertex_position(a), W, H); pb = cam.project_to_screen(mesh.vertex_position(b), W, H)
        return _point_segment_distance(x, y, pa[0], pa[1], pb[0], pb[1])
    return None

for zoom in (1.0, 0.25):
    for ci, (cname, cam) in enumerate(probe.framed_cameras(mesh)):
        if zoom != 1.0:
            cam.dolly(zoom)
        pts = probe.cursors(cam, mesh, 300, seed=100 + ci)          # the spike's cursors and seeds
        for occl in (True, False):
            gpu.render(cam, occlusion=occl); cache = PickCache()
            for row, mname, meth in (("vertex", "vertex", "pick_vertex"), ("vertex+depth", "vertex", "pick_vertex_depth"),
                                     ("edge", "edge", "pick_edge"), ("face", "face", "pick_face")):
                if mname == "face" and not occl: continue
                same = both_none = half = real = 0; deltas = []; extra = []
                for x, y in pts:
                    c = pick_component(cam, mesh, modes[mname], x, y, W, H, cache=cache, occlusion=occl)
                    g = getattr(gpu, meth)(x, y)
                    if probe._same(c, g):
                        same += 1; both_none += c is None; continue
                    cc = pick_component(cam, mesh, modes[mname], x + .5, y + .5, W, H, cache=cache, occlusion=occl)
                    if probe._same(cc, g): half += 1; continue
                    real += 1
                    dc, dg = (dist(c, x, y, cam) if c is not None else None), (dist(g, x, y, cam) if g is not None else None)
                    if dc is not None and dg is not None: deltas.append(dg - dc)
                    else: extra.append((c, g))
                # prints n, both-None, same (% of all / % of non-trivial), half, real, GPU-farther px p50/max, none-vs-elem
```

Output (gollum_20k, 300 cursors per camera; `z` = dolly factor, 0.25 = camera at a quarter of the framing
distance; "farther" = GPU pick's screen distance minus the CPU pick's):

```
z1    front shaded vertex       both-None=103 same=295 (98.3% all, 97.5% non-trivial) half=0  real=5  | farther p50=0.09 max=0.50
z1    front shaded vertex+depth both-None=103 same=296 (98.7%, 98.0%) half=0  real=4  | farther p50=0.14 max=0.50
z1    front shaded edge         both-None=116 same=285 (95.0%, 91.8%) half=1  real=14 | farther p50=0.02 max=0.33
z1    front shaded face         both-None=140 same=254 (84.7%, 71.2%) half=46 real=0
z1    front wire   vertex       both-None=103 same=293 (97.7%, 96.4%) half=2  real=5  | farther p50=0.12 max=0.58
z1    front wire   vertex+depth both-None=103 same=300 (100%, 100%)   half=0  real=0
z1    front wire   edge         both-None=116 same=275 (91.7%, 86.4%) half=4  real=21 | farther p50=0.06 max=0.46
z1    back  shaded vertex       both-None=108 same=292 (97.3%, 95.8%) half=0  real=8  | farther p50=0.14 max=0.73
z1    back  shaded vertex+depth both-None=108 same=296 (98.7%, 97.9%) half=0  real=4  | farther p50=0.10 max=0.38
z1    back  shaded edge         both-None=117 same=293 (97.7%, 96.2%) half=0  real=7  | farther p50=0.04 max=0.61
z1    back  shaded face         both-None=134 same=266 (88.7%, 79.5%) half=33 real=1  | none-vs-elem 1
z1    back  wire   vertex       both-None=108 same=289 (96.3%, 94.3%) half=1  real=10 | farther p50=0.16 max=0.73
z1    back  wire   vertex+depth both-None=108 same=300 (100%, 100%)   half=0  real=0
z1    back  wire   edge         both-None=117 same=279 (93.0%, 88.5%) half=6  real=15 | farther p50=0.10 max=0.31
z0.25 front shaded vertex       both-None=252 same=299 (99.7%, 97.9%) half=0  real=1  | farther p50=7.19 max=7.19
z0.25 front shaded vertex+depth both-None=252 same=300 (100%, 100%)   half=0  real=0
z0.25 front shaded edge         both-None=202 same=298 (99.3%, 98.0%) half=0  real=2  | farther p50=-0.97 max=-0.52
z0.25 front shaded face         both-None=4   same=296 (98.7%, 98.6%) half=4  real=0
z0.25 front wire   vertex       both-None=8   same=297 (99.0%, 99.0%) half=0  real=3  | farther p50=2.93 max=2.93 | none-vs-elem 2
z0.25 front wire   vertex+depth both-None=8   same=300 (100%, 100%)   half=0  real=0
z0.25 front wire   edge         both-None=4   same=299 (99.7%, 99.7%) half=0  real=1  | farther p50=0.01 max=0.01
z0.25 back  shaded vertex       both-None=80  same=297 (99.0%, 98.6%) half=0  real=3  | farther p50=1.93 max=1.93 | none-vs-elem 2
z0.25 back  shaded vertex+depth both-None=80  same=299 (99.7%, 99.5%) half=0  real=1  | none-vs-elem 1
z0.25 back  shaded edge         both-None=35  same=298 (99.3%, 99.2%) half=0  real=2  | farther p50=-0.42 max=-0.11
z0.25 back  shaded face         both-None=0   same=288 (96.0%, 96.0%) half=12 real=0
z0.25 back  wire   vertex       both-None=28  same=296 (98.7%, 98.5%) half=0  real=4  | farther p50=1.04 max=1.93 | none-vs-elem 2
z0.25 back  wire   vertex+depth both-None=28  same=299 (99.7%, 99.6%) half=0  real=1  | none-vs-elem 1
z0.25 back  wire   edge         both-None=7   same=299 (99.7%, 99.7%) half=0  real=1  | farther p50=0.04 max=0.04
```

The framed rows reproduce the [RPC] agreement within noise: the agreement is geometry, not driver timing.

### P2 — option B2 mechanism on llvmpipe (`p2_b2_mechanism.py`)

```python
"""Option B2 as a mechanism check (llvmpipe; says nothing about the 9800 GTX): a second program draws the
production GLRenderStore VertexList; face ID = gl_PrimitiveID -> RenderMesh._triangle_face_rows; vertex ID =
gl_VertexID via vlist.draw(GL_POINTS). Compared pixel by pixel with the spike's B1 targets (same FBO, camera, depth
state, polygon offset)."""
# setup: hidden 1024x768 window; mesh = gollum_20k; rm = RenderMesh(mesh, overlay=None, store_type=GLRenderStore)
# vlist = rm.store.vertex_list("mesh"); spike = GpuIdPicker(mesh, W, H)
VS = """#version 330 core
in vec3 position; uniform mat4 u_view; uniform mat4 u_proj;
void main() { gl_Position = u_proj * u_view * vec4(position, 1.0); }"""
FS_PRIM = """#version 330 core
out vec4 frag;
void main() { uint id = uint(gl_PrimitiveID) + 1u;
 frag = vec4(float(id & 255u), float((id >> 8u) & 255u), float((id >> 16u) & 255u), 255.0) / 255.0; }"""
# point program: same VS with `flat out int v_id; v_id = gl_VertexID;`, FS encodes v_id + 1
# per camera (probe.framed_cameras): spike.render(cam) -> read FACES / VERTICES targets (B1 reference);
# then into the same FBO: clear colour+depth, depth LESS, polygon offset (1, 1), progB over vlist.draw(GL_TRIANGLES)
# into target 0; depth LEQUAL, no depth write, progP over vlist.draw(GL_POINTS) into target 2; read both back.
# face equality: pixel empty in both, or rows[b2_id] == b1_face_index (RenderMesh rows are in all_face_ids() order).
```

Output:

```
attribute location of 'position': store program 0 | ID program 0 | point program 0
front: face pixels covered 108034, B2 face (gl_PrimitiveID -> row) == B1 face on 786432/786432 px (differ 0); vertex pixels B1 7898, B2(gl_VertexID) == B1 on 786359/786432 px (differ 73)
back: face pixels covered 113735, B2 face (gl_PrimitiveID -> row) == B1 face on 786432/786432 px (differ 0); vertex pixels B1 6052, B2(gl_VertexID) == B1 on 786363/786432 px (differ 69)
```

Reading: the face mapping is exact on llvmpipe. The point differences are shared pixels with a different winner:
an indexed point draw emits each vertex once per triangle corner, in another order than B1's point list. The
equal attribute location is the driver's choice, not a contract (F3). Run on the reference PC, this probe is the
`gl_PrimitiveID` exactness check F3 asks for.

### P3 — Box deviation from the [RPC] raw output

A regex over the `box` lines of `RESULTS_REFERENCE_PC_2026-10-20.md`, for rows with ≥ 50 CPU elements. The
largest symmetric differences (CPU-only + GPU-only) / CPU count:

```
gollum_20k back 300 face   cpu  4256  ids lost  5.4 %  depth 6.5 % (-0.8 +5.7)
gollum     back 300 face   cpu 17157  ids lost 19.0 %  depth 6.3 % (-0.5 +5.8)
gollum     back 150 face   cpu  3687  ids lost 20.0 %  depth 6.2 % (-0.8 +5.5)
gollum     back 150 edge   cpu  7565  ids lost 34.3 %  depth 6.1 % (-0.7 +5.4)
gollum     back 300 edge   cpu 34721  ids lost 35.4 %  depth 5.8 % (-0.6 +5.2)
gollum_20k back 300 edge   cpu  8714  ids lost 14.0 %  depth 5.3 % (-0.9 +4.5)
max ids lost: gollum front 150 edge, cpu 15692, 37.0 %
```

---

## Kurzfassung für Manu (Deutsch)

- **Urteil:** AD-022 taugt als Entscheidungsvorlage, wenn der Text nachgezogen wird (ACCEPT WITH CHANGES). Das ist
  kein Urteil darüber, welche Option du wählst.
- **Was trägt:** Auf deinem PC ist GPU-Picking sehr viel schneller: erster Pick nach dem Drehen auf gollum_20k
  ~150–190 ms → ~3 ms, Box 2,4 s → ~0,09 s. Unterschiede beim Hover sind fast immer das Nachbarelement im selben
  Pixel.
- **Blocker:** Das AD zitiert noch die Container-Zahlen statt deiner Messung. Einige Aussagen stimmen damit nicht
  mehr: Die Box mit Tiefentest nimmt bis zu ~6 % *mehr* mit (an Silhouetten, auch Rückseiten). Option B1 kostet
  ~0,8 s pro Topologie-Operation zusätzlich.
- **Fehlt noch:** Variante B2 ist nicht gebaut, und der Flat-Test beweist nicht exakte IDs (ein Prüflauf von
  ~1 Minute auf deinem PC würde das klären). Ein Hover direkt nach einer Operation könnte veraltete Daten lesen.
  Die Optionen sind nicht gleich fair verglichen.
- **Fragen, die nur du beantworten kannst:**
  1. Welche Mesh-Größe muss beim *Bearbeiten* flüssig sein?
  2. Ist dein jetziger PC die Untergrenze des Produkts oder nur das Testgerät?
  3. Soll die Box an der Silhouette lieber etwas zu viel oder zu wenig nehmen?
  4. Bei SubD/Morph: Pickst du durch die angezeigte Fläche oder durch den Käfig?

  Ob sich die Unterschiede richtig anfühlen, kannst du erst beurteilen, wenn ein Schalter im Fenster existiert.
