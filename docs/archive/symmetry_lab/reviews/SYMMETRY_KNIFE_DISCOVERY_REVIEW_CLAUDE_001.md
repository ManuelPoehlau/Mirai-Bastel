# Independent Review — Symmetric Knife Discovery (AD-SYM-03 slice 6, Type B)

> **Reviewer:** Claude (Claude Code on claude.ai/code, fresh session; the author's session and handoff were not used)
> **Review ID:** CLAUDE-001
> **Model:** see the `Co-Authored-By` trailer of the commit that adds this file (no model identifier is written into
> repository files)
> **Date:** 2026-10-09
> **Repository state reviewed:** `main` @ `5ef5130` (merge of `f611cb4`; the Discovery itself was written at `1aa77c9`)
> **Subject:** `docs/research/symmetry/SYMMETRY_KNIFE_DISCOVERY.md` (cited as **KD**) and
> `experiments/topology/symmetry_knife_probe.py` (the probe)
> **Type / Mode:** Type B · Discovery, independent review (M5) · nothing edited except this file
> **Environment:** Linux x86_64 container (kernel 6.18), 4 CPUs, Python 3.13.16, numpy 2.5.3; `pytest` 9.1.1 installed
> with `pip` for this run (it was not in the container); no `pyglet`
> **Verdict on K-C:** **ACCEPT WITH CHANGES.** K-C is the right mechanism for paths whose resolved mutations stay on
> one side, and it is not the rejected M-d. One **BLOCKER** must be resolved before the addenda are decided: K-C
> refuses a path that reaches the other side **only when an element collides**, not because it reaches the other side.
> Several such paths are committed as a symmetric "union" that changes the Artist's own side (B1).
> **Status:** Archived first-pass review — preserved verbatim
>
> This document is intentionally preserved as the original independent review. Do not edit it to reflect later
> decisions. Answers to the findings belong to the Discovery's author and to the AD addenda.

---

## What was read, what was run

**Read in full:** KD; the probe (all 2299 lines); `src/mirai/topology/knife_resolve.py` (all 1154 lines);
`src/core/mesh.py` `split_edge` (`:281-332`), `split_face` (`:478-576`), `export_state` / `load_state` / `from_state`
(`:1067-1177`); `src/core/ids.py` `IdAllocator`; `src/mirai/symmetry_coordination.py`;
`src/mirai/symmetry.py` (`vertex_correspondence`); `src/mirai/topology/knife.py` (`_on_begin`, `_plan_segment` crossings,
`_apply`, undo/redo, `_on_commit`, `_link`); `src/mirai/application.py` (`_connect_command` Knife branch,
`knife_render_data`, `_knife_begin`); `src/mirai/symmetry_declarations.py`; `experiments/symmetry_lab/lab_app.py`
(`block_row`, Knife warning); `experiments/symmetry_lab/tests/test_app_lab_bindings.py` (T-R1a) and
`test_app_lab_boundary.py` (T-R4a); `playground/tests/knife_golden_driver.py` (what it signs).
**Read for the binding context:** AD-SYM-03 (§1, §2.1, §2.4, §3, §4, §7 incl. implementation notes 3b/4),
AD-SYM-02 §2.1–§2.4, AD-017 (Decision) and the "One Knife S1" addendum in `AD-017_FINAL_DECISIONS_2026-09-22.md`,
AD-013 (Decision, Default Lifecycle, H2-R1…R6), `SYMMETRY_DESIGN_BRIEF.md` INV-1…13, `AGENTS.md` §5–§6,
`MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` M3, the format model `AD-SYM-03_REVIEW_CLAUDE_001.md`.
**Not read in full:** `playground/experiments/knife_face/decision.md` (2067 lines; only through KD's and AD-017's
citations), `SYMMETRY_PRODUCTION_OPERATIONS_DISCOVERY.md`, `knife_planner.py` beyond the cited constants.

**Run (this container):**

| Command | Result | Baseline in the handoff |
|---|---|---|
| `pytest tests --ignore=tests/test_extrude_tool.py` | 1964 passed, 14 skipped (83 s) | 1964 / 14 |
| `pytest experiments/symmetry_lab/tests` | 428 passed, 8 skipped, 1 failed: `test_app_lab_partners.py::test_lab_overlays_are_drawn_before_the_app_point_overlay` (`ModuleNotFoundError: pyglet`) | 428 / 8 / 1 (same test) |
| `python experiments/topology/symmetry_knife_probe.py` (full run, seed 20261008, 500 fuzz paths per asset) | exit 0, 491.2 s | exit 0, ~11 min |
| Scratch probes A–D (appendix; in-memory, they import the probe read-only) | exit 0 | — |

No file other than this review was changed. `git status` was clean before the commit.

---

## Verdict

**ACCEPT WITH CHANGES.**

What holds, and I checked it independently:

- **The numbers.** Every table of KD §1.3 reproduces exactly on `5ef5130` (Q11). Only wall-clock times differ; this
  container is about 20 % faster, and the order of the methods is unchanged.
- **The mechanism.** Mirror ids come from the results of each mirrored call. The two halves of a split are matched by
  set inclusion between exactly the two faces that call returned. This is pairing at creation time, not a search over
  the result. It can refuse; it cannot pick a wrong partner (Q1). K-C is an addendum to AD-SYM-03 §3 item 1 / §7
  row 6, not a reversal of M-d.
- **The log.** Every kept call of the 1176 K10 paths, replayed verbatim on a session-start copy, rebuilds the
  resolved mesh exactly: faces, edges and counts (R3, 1176 / 1176). So the instance-level log is complete and
  correctly truncated on this sample.
- **The seam.** In a seam-biased fuzz (only faces touching the seam, seam targets preferred), K-C passes E-a…E-d on
  879 / 879 valid paths; 823 of them have a record on the seam (R7). Eight hand-built seam-adjacent recipes also pass
  (R5). These include the order "face split first, seam split later", which is the reason for matching halves by
  inclusion, plus a loop closed at a seam vertex and bridges or a tail join to seam corners. No duplicate vertex, no
  seam edge off the plane, no new undeclared on-plane edge in any K-C result (R4).

What does **not** hold as written — **B1 (BLOCKER):** K-C refuses only when a mirrored call meets an element the
source already **killed** (`replay_mirrored` `:788`, `:804`). A path whose kept mutations reach the other side
without such a collision is replayed in both directions, and the result is a symmetric "union":

- one run through a **seam vertex** into a −X face that is not the partner face: committed on 60 / 60 constructed
  paths (tie_grid 4, subd_cube 16, head 40), all `E +-++` (R8);
- a +X chain plus a −X chain after a pen lift: committed `E +-++` (R1);
- one session of KD's own K5 sample (head, side camera, seed 20261008 + 5): committed `E +-++` (R10).

E-a and E-c pass, so the production safety net (the delta check) cannot see these. The Artist's own side gets a cut
they did not draw there. This is exactly the defect KD cites against K-A ("an X that changes the Artist's own side").
KD's K7 c tests only a crossing through a seam **edge**, where the collision happens to fire. Built "in the probe's
shape" (KD §3, 6b), the symmetric Knife would answer F1 itself: refuse for seam-edge crossings, option B for
seam-vertex crossings, gaps and two-chain paths. Which one applies would depend on whether the planner's line
passes within 0.5 px of a seam vertex. The fix is small and keeps K-C: an explicit side rule before the replay (B1).

---

## Answers to the review questions

### Q1 — Rejected-alternative check

**How created ids are mapped** (`replay_mirrored`, probe `:750-823`):

- *Vertices.* `split_edge` → `vmap[v] = v2`, the vertex the mirrored call returned (`:791-795`). `split_face` →
  `vmap.update(zip(nvs, nv2))`. The order is guaranteed by the Core contract "k neue VertexIds, in Pfadreihenfolge
  v_a -> v_b" (`mesh.py:510`), and the mirrored call passes the mirrored positions in the same order (`:807`).
- *Edges.* The halves of a split edge are mapped by endpoint: `first_is_a` tests whether `x1` joins the partner of
  the recorded first end (`:796-797`). This holds because `split_edge` returns `eid_a` on the `v0` side
  (`mesh.py:312-316`, `:332`). Path edges of a `split_face` are mapped in order (`mesh.py:511`).
- *Faces.* The two halves are matched by set inclusion of the partner images of the halves recorded right after the
  source call (`:812-821`). Inclusion and not equality is needed for one case: a source split of a seam edge
  *after* the face split has already put the shared plane vertex into the mirror face (`mesh.py:319-330`: a split
  vertex is inserted into every adjacent face). R5 row 1 builds exactly that order, and it passes.
- *Self-partners.* Seam edges and seam vertices are their own partners and are not split again (`:781-785`).

**Is any step a search that could pick a wrong partner?** No. The only after-the-call choice is between the two faces
that the mirrored call itself returned. If the replay so far is correct, the correct assignment satisfies inclusion
(each recorded half's partner image lies in its mirror half, plus at most shared plane vertices). The crossed
assignment cannot also satisfy it, because at least one half owns a boundary vertex the other lacks. In a notch the
small half is contained in the big one, but the big half is never contained in the small one. When both or neither
satisfy it, the code refuses (`:819-820`). No step scans the mesh, compares positions, or chooses among
candidates that the call did not produce. Matching by call results and session-start partners is the
"Spiegelbild der Absicht" of INV-6 and AD-SYM-02 §2.4, not "nachträgliche Zuordnung". M-d's two reasons ("find new
elements" and "cannot reproduce intent such as a Knife path", AD-SYM-03 `:205`) do not apply.

**Addendum or reversal?** An addendum. AD-SYM-03 §4 lists "resolving the source and constructing its mirror"
explicitly as an open option for Knife tie-break equivariance. §7 is a *proposed* slice cut. §3 item 1 decides only
"symmetry context at `begin`, applied at the tool's existing commit, no `SymmetricX`", which K-C keeps. M-c (no copy
of op logic) and M-e (no universal engine; the replay is Knife-only) are respected.

The addendum must still say four things explicitly:

1. §3 item 1's "intent/path mirroring" becomes "mirroring the *resolved* intent".
2. §3 item 4's Knife report changes from pid → vertex to the kept-call report.
3. §3 item 6's snap (X-a) becomes placement at replay.
4. §7 row 6 "mirror records before resolution" becomes "mirror the kept mutations at the commit".

KD §3 (6b) names 2–4. The M-d argument carries **only for one-sided resolved mutations**. For a two-sided result,
K-C mirrors mutations that are themselves on the mirror side, which is "mirror the result afterwards" in substance.
That is B1; I do not consider it a reason to call K-C a rejected alternative, because the one-sided restriction is
cheap to state and to check.

### Q2 — Is the 100 % real or partly by construction?

- **By construction, for K-C:** E-b. The source resolve in K-C is the same code path as the one-sided reference
  (`Session.__init__` `:863-868` vs `run` `:912-913`). For a one-sided path the replay touches no `+` face: an edge
  shared by a `+` and a `−` face lies on the plane and is a self-partner, which is not split. E-d also passes for every
  method in every row (one `MeshStateCommand`, method-independent) (N4).
- **Genuinely tested:** E-a and E-c, meaning the replay's id mapping, half matching, S1 order and log truncation.
  The identity replay R3 (1176 / 1176) shows independently that the log is complete on that sample.
- **Seam vertices, seam edges, seam-adjacent faces:** covered, not excluded. The K10 seam stratum has 207 / 74 / 123
  paths. My seam-biased fuzz R7 adds 879 valid paths, 823 of them with a record on the seam, all passing. R5 adds
  eight targeted recipes, all passing.
- **Resolver-made vertices on the plane:** not reachable on the three assets for one-sided paths. A `split_edge` in
  `_walk_run` splits a cut of this commit inside a `+` face, so x = 0 would need a cut lying in the plane. A loop
  crossing point is an interior point of a trail inside a `+` face. Both need two non-adjacent plane points in one face
  (KD K7: 0 such faces on the assets). A face record exactly on the plane is dropped by the resolver (R6: "cut
  nothing" at x = 0 and x = 1e-300). On `hexagon_grid` (case e/e′) K-C refuses.
- **The exclusions** (source cuts nothing or rolls back: 127 / 102 / 95) are legitimate. There is nothing to mirror,
  and the Knife rolls such sessions back anyway.
- **Not covered by the 100 %:** every path with a record on −X. K10 clicks only `+` faces (`allowed`, `:1771`,
  `:1799`), and the camera sessions skip targets with x ≤ 0 (`:1199-1201`). The handoff's premise "K-C refuses any
  path whose kept mutations reach the mirror side" does **not** hold (R1, R8, R10; B1). The 100 % is a statement
  about one-sided paths only.

### Q3 — The criterion E-a…E-d

- **E-a** (`:945-950`) is the AD-SYM-03 delta check by element id plus "`symmetry_state` not worse". It is sound for
  completeness. By design it cannot see a symmetric but wrong-intent result (the union of B1).
- **E-b** (`:953-954`, `face_class` `:233-241`): "all x ≥ 0, one > 0" puts a seam-adjacent face with seam vertices
  on `+`, which is right. Faces of class `0` (in the plane) and `span` are not in E-b; E-c and E-a's
  "new self-mirrored face" cover them.
- **E-c** (`:955-959`, `canon_poly` / `mirror_canon` `:244-250`): positions are mirrored exactly and the cycle is
  reversed, so winding is checked, and canonical rotation makes it order-independent. It is exact and sound for
  connectivity, because different topology gives different position cycles. **Blind spot:** two coincident vertices
  are indistinguishable by position. If a pair lies on the plane, `vertex_correspondence` pairs the twins with each
  other (`symmetry.py:141-147`), so E-a would also pass. Not reachable on the probed paths (R4: 0 duplicates in all
  1176 K-C results; R6), but the 6b tests should assert "no coincident vertices" (N4).
- **`conn` / `float` / `geom`** (`max_deviation` `:969-979`): a diagnostic over *created* vertices only. The verdict
  itself is the exact E-c, so the classification cannot let a wrong result pass.
- **E-d** (`:960-966`) is not discriminating (N4).
- **Can a wrong result pass?** For one-sided paths, only through the coincident-vertex blind spot, which was not seen.
  For two-sided paths, yes: E-a + E-c + E-d pass a union. Only E-b catches it, and E-b does not exist in production
  because there is no one-sided reference at commit (B1).

### Q4 — Kept-call log

Every mutation and every state call in `knife_resolve.py` at `5ef5130`. All of them go through the instance
(`mesh.`, `m.`, `self.mesh.`), so the instance wrapper sees them:

| Site | Call | Rollback scope | `KeptLog` behaviour |
|---|---|---|---|
| `_run_end_vertex` `:517` | `split_edge` | inside `_apply_run` | logged |
| `_walk_run` `:726` | `split_edge` (cut of this commit) | inside `_apply_run` | logged |
| `split_face_path` `:155`, `cut_in_face` `:320` | `split_face` | inside `_apply_run` | logged |
| `close_loop_with_bridges` `:228`, `:231` | `split_face` ×2 | `_resolve_closed_loop` | logged |
| `close_loop_at_vertex` `:292`, `:295` | `split_face` ×2 per candidate | own `base` (`:288`) | logged |
| `close_loop_at_vertex` `:288` → `:307` | `export_state` → `load_state(base)` per failed candidate | nested in `_apply_run`'s state (via `_walk_run` → `_build_loops`) | truncated to the mark (LIFO) |
| `_apply_run` `:817` → `:835` | `export_state` → `load_state(state)` on a dropped run, end splits included | per run, tails per corner tried (`join_tails`) | truncated |
| `_resolve_closed_loop` `:851` → `:858` / `:864` | `export_state` → `load_state` on `MeshError` / `face_problem` | per closed shape | truncated |
| `check_commit` `:397` / `:402` | `export_state`; `load_state(before_state)` on an integrity problem | whole session; `before_state` was never exported under the log | log emptied (unknown state ⇒ `keep = 0`, `:478-482`); correct: the whole session is taken back |

The log is complete and correctly truncated in all of them. Ids never come back after a rollback: `load_state` moves
the allocator counters only forward (`mesh.py:1121-1131`, `:1157-1159`; `ids.py:69-74`). So "the mirror id is not valid" is an
exact "killed by the source" test. The resolver never moves a vertex after creating it (no `set_vertex_position` in
the module), so the post-call positions in the log are final. R3 confirms all of this on 1176 / 1176 paths.

**Two gaps for slice 6a, both contract-level (S2):**

- The decided resolver contract permits a **third** primitive. The AD-017 "One Knife S1" addendum says faces are
  built "only through `Mesh.split_face`, `split_edge`, `connect_vertices`", and so does the resolver docstring
  (`knife_resolve.py:14-15`). The probe logs two.
- `replay_mirrored` treats every call that is not `split_edge` as `split_face` (`:799`). A third kind would be
  mis-replayed instead of refused.

**Contract slice 6a should state so the log cannot drift silently:**

1. The resolver mutates the mesh only through two recording helpers. A static test, in the style of the camera-free
   import check of `tests/test_knife_resolve.py`, fails on any other mutating `Mesh` call in the module. AD-017's
   primitive list is narrowed to what is logged (or `connect_vertices` gets logged too).
2. Every `load_state` inside the resolver goes through one checkpoint / rollback helper pair that truncates the log
   to the checkpoint's length, LIFO. No bare `load_state` (static test).
3. Each entry holds op, arguments, results and the created positions. Created vertices are never moved afterwards.
4. The report is void when `check_commit` rolls back.
5. A dynamic guard: replaying the log verbatim on a copy of the session-start state rebuilds the resolved mesh, run
   over the golden net and a fuzz (R3 shows the test passes today).
6. The replay refuses any op kind it does not know (fail-closed).

### Q5 — Replay hazards

- **Winding / position order on the partner face:** correct. `split_face` keeps the parent's winding in both halves
  (`mesh.py:525`). The mirror parent is wound in reverse, so the halves come out as exact mirror images. Mirrored
  positions are passed in path order from `mv(va)` to `mv(vb)` (`:807`).
- **Elements created mid-replay:** only reachable through `vmap` / `emap` / `fmap`. A mirror face that a replayed
  `split_edge` grew in place keeps its id. The later replayed `split_face` then sees the same extra vertex the source
  face had. Correct.
- **Seam split followed by a cut in a seam-adjacent face:** the mirror reuses the same new seam vertex
  (`vmap[v] = v`, `:784`). The source split already inserted it into the mirror face. K7 b / b2 and R5 (rows 1, 2, 7)
  pass in both orders.
- **S1 from kept splits** (`apply_s1` `:485-494`): applied to the source calls in log order. A second split of a
  seam half is recognised because the first S1 step already declared the halves (b2: 10 / 10 seam edges live on the
  cube). A split of an *undeclared* on-plane edge is treated as a self-partner and not declared, so its vertex is
  UNPAIRED and the delta check refuses. That is consistent with implementation note 4's "known behaviour" for Split.
- **Replay applied to an element the source already changed — yes, in two ways:**
  - The seam split of a mirror face's boundary, by design, handled by inclusion.
  - Any mirror element the source changed **in place** or not at all on the other side (B1). The guard detects only
    *killed* ids (`:788`, `:804`). An element the source grew in place (a −X face receiving a vertex from a −X edge
    split), or never touched, is replayed onto. That produces the union of R1 / R8 / R10.
- **Small:** a self-mirrored edge that is not on the plane but crosses it, split at its exact midpoint, maps each
  half to itself (`:784`). The correct mirror swaps them (N5). Unreachable on a manifold mesh, because such an edge
  borders only self-mirrored faces, which K-C refuses.

### Q6 — "Reaches the other side" refusal and F1

**Is the refusal condition well-defined?** As implemented it is well-defined, but it is *collision*, not *side*.
The refusal reasons are:

- an element without a partner;
- a self-partner split off the plane (`:782-783`);
- a mirror edge or face already killed (`:788`, `:804`);
- a self-mirrored face (`:802`);
- `MeshError` / `KeyError` from the mirrored call;
- halves that cannot be told apart.

Elements on the plane are handled consistently: seam vertex and seam edge are self-partners, an undeclared on-plane
edge goes to the delta net, and a seam-adjacent face maps to its partner across the seam. The condition KD states
("kept mutations reach the mirror side", §2.1, §3) is **not** implemented. An explicit side rule is well-defined on
exact planes without tolerance:

- side = sign of the one exact coordinate;
- seam vertices and seam edges belong to both sides;
- a face's side is its `face_class`, with `0` and `span` refused as item 9;
- the source side is the side of the first off-plane record or kept call.

**How often it hits paths the Artist did not mean to cross** (K4 / K5 re-run with KD's seeds; every session clicks
only +X targets and points in space, R2 / R10):

| sample | sessions | with a record on −X | K-C refused (collision) | not refused, kept mutation on −X (union, E-b −) | not refused, the −X run was dropped (harmless) |
|---|---|---|---|---|---|
| K4 front | 59 | 0 | 0 | 0 | 0 |
| K4 3/4 (+X) | 60 | 0 | 0 | 0 | 0 |
| K4 side (+X) | 60 | **9** | 7 | 0 | 2 |
| K5 hole_grid front | 37 | 15 | 15 | 0 | 0 |
| K5 hole_grid 3/4 | 39 | 16 | 16 | 0 | 0 |
| K5 head front | 39 | 26 | 26 | 0 | 0 |
| K5 head 3/4 | 37 | 18 | 18 | 0 | 0 |
| K5 head side | 40 | **14** | 8 | **1** | 5 |

- **Side camera, cross-face runs:** 9 / 60 sessions with only +X clicks reach −X through planner crossings. All of
  these are accidental.
- **Points in space:** K5 picks space points at the left or right screen border with equal probability, so its −X
  share partly reflects the sampling, not Artist behaviour.
- **Click time vs. commit time:** a click-time rule by records (F1 A) would refuse 9 / 60 side-camera sessions; a
  commit-time rule by kept mutations would refuse 7. The two extra sessions cross only in a run the resolver drops
  anyway.

**Is F1 described completely for the Artist?** No (S1).

- F1's situation and options describe only a deliberate crossing ("über die Mittellinie … quer über die Nase").
- Option A's wording "Der Klick auf der anderen Seite wird abgelehnt" does not fit an accidental crossing. There, the
  refused click is on +X, and its planned line runs over −X, often over a side the Artist cannot see from the camera.
- F1 does not say that today's K-C behaviour differs by crossing type: refused through a seam edge, mirrored union
  through a seam vertex, a gap or a separate chain.
- F1 does not ask about a path with separate chains on both sides. F4 C assumes that case arises only "wenn F1 = B".

**Technical feasibility of F1 option C ("cut only to the seam") — feasibility only, no recommendation.** Feasible at
path level, before the resolver, with no resolver change:

- Replace every maximal stretch of −X records by a pen lift. The seam crossing record (edge on a seam edge, or a seam
  vertex) then ends the run on the plane.
- Then run K-C on the clipped path. On all 90 sessions K-C refused in K4 / K5, the clipped path keeps a seam record
  and passes E-a…E-d (R9, 90 / 90).
- **Limits:**
  - A crossing inside a plane-spanning face has no seam record to clip at. No Lab asset has one.
  - The dropped clicks need a preview and in-session undo story.
  - "The part behind the middle" is exactly the part a side camera hides.

### Q7 — Click-time predictor P2

**Is P2 implementable without camera rules on the mirror side?** Yes. P2 reads only:

- the source records, including the planner crossings that a click stores (`knife.py:484-486`);
- the faces those records' segments cut;
- the session-start `SymmetryIndex` (1.46 ms once per session on the head, K11).

No mirror-side projection, pixel rule or occlusion is involved, which is consistent with K6 (b). In the probe P2 is
evaluated after the session. When two faces are shared, `segment_faces` takes the lowest FaceId (`:1752`). At click
time the tool knows the chord's face exactly (`_link`, `knife.py:411`) or the planner's crossings, so a per-click
version can be exact.

**Does P2 refuse a path the Artist sees as fully on one side?** Yes, by design. A3 = S refuses next to unpaired
geometry even when the Artist's path is entirely on +X. The cause is visible: on `man_with_shoes_basemesh` all 101
partner-less +X faces have a magenta (unpaired) vertex (R11). A face whose vertices are all paired but whose image is
not a face would be refused without a magenta vertex; there are 0 such faces there. The hover marker should mark the
face in that case. P2 is conservative: 17 of 201 predicted paths would commit (KD K8, reproduced). P2 says nothing
about B1 crossings or self-mirrored faces; F1's click check is a separate predictor.

### Q8 — Part C / preview placement

Both facts are **VERIFIED**:

- H2-R1 fixes the Lab context at exactly three key entries (`AD-013 …:599-608`; T-R1a at
  `test_app_lab_bindings.py:55`).
- H2-R4 (a) lists `knife_active` but not `knife_render_data` (`AD-013 …:654-657`).
- T-R4a checks only callable non-property members: `_public_methods` excludes `property`
  (`test_app_lab_boundary.py:84-89`). A Lab read of `app.knife_render_data` would pass the test and still break
  H2-R4.

KD's alternative, the mirrored preview drawn by `Application` / viewport (6c), needs no H2 change. H2 governs what Lab
code may touch, not what `Application` draws for its own Knife session.

It is consistent with M3 and AD-013 on the same footing as the earlier symmetric slices: Production code that is
active only when the Lab has set a definition, shipped as an engineering default and judged by the Artist's practical
test (the Edge Connect and Split residue precedents, AD-SYM-03 §4 / §6). The variant (V-a / V-b / V-c) stays the
Artist's (M4). It needs no own AD, but the addendum should say "provisional UX, Artist test before KEEP" rather than
"none expected" (N1). It also changes `src/viewport/` / `application.py`, so CLAUDE.md's Symmetry Lab test run
applies.

### Q9 — Slice cut and AD addenda

**Is 6a behaviour-neutral for the non-symmetric Knife?** Yes, if the report is recorded without changing the call
order or the id allocation:

- The golden driver signs HUD text, counts and position-canonical hashes, not `KnifeResolution` fields
  (`knife_golden_driver.py:10-19`).
- No test constructs or compares a `KnifeResolution` (no `KnifeResolution(` outside `knife_resolve.py`, no
  `asdict`).
- The golden net runs headless (the probe's K-D check: byte-identical, 18.5 s here).

The real 6a risk is a truncation bug, and the identity-replay test (R3) is the guard to add.

**Are two addenda sufficient?** AD-017 + AD-SYM-03 cover it, with these contents:

- **AD-017:** the kept-call report, and the primitive list narrowed or logged (S2).
- **AD-SYM-03:** §3 items 1, 2, 4, 6, §7 row 6 (Q1), the side rule (B1), and the declaration shape. The documented
  shape of `C_CONTEXT_COORDINATORS` is `(mesh, canonical selection ids) -> result`
  (`symmetry_declarations.py:40-41`); a Knife entry adds a second signature. §3 item 2 anticipated "its entry in the
  same mapping" but not the shape. Nothing calls the entry with selection ids, because `_connect_command` returns
  `_knife_begin()` before any lookup (`application.py:690-691`).
- **D-b** holds.
- **The BLOCK row and the MARK warning** derive automatically (`lab_app.py:287-316`, `:721`). The Lab tests that pin
  the Knife refusal and `KNIFE_ONE_SIDED_TEXT` change with the declaration, as in slice 4.
- No AD-013 change.

**The slice order breaks INV-11 (S3):** 6b declares `CContext.KNIFE`, which makes the Knife "supported" under BLOCK
and removes the MARK warning. The mirrored preview and the click-time refusals come only in 6c. In between, a
symmetric Knife counts as symmetric without showing the other side (INV-11) and refuses only at Enter, against KD's
own recommendation in §2.4.

### Q10 — Wording and authority

Inferences presented as observations, or stated beyond what was measured:

- §1.3 K5: "K-C refuses exactly those (the remaining K-C sessions all pass)". For head / side, 8 of 14 sessions with a
  −X record are refused. One of the 6 that are not refused changes the Artist's side; it "passes" only because the K5
  table measures E-a + E-c and not E-b (R2, R10).
- §2.1 K-C row ("refuses a path whose kept mutations touch the mirror side"), §2.6 c, and §3 ("leaves the Artist's
  side bit-identical … E-b by construction"; "a path whose mutations reach the other side … is refused until F1 is
  answered") describe a rule the mechanism does not have (B1).
- §2.1 K-A row: one stated reason against K-A ("a path that reaches the other side becomes an X that changes the
  Artist's own side") applies to K-C as well, through a seam vertex (R8: 60 / 60). The comparison is unfair on this
  point. It does not change the ranking: ties and resolver vertices remain decisive.
- §2.7: "this preview cannot disagree with the result" is not marked as an inference and is overstated. The preview
  shows the path, not the resolved cut (tail joins, bridges, dropped runs). The precise claim is: the mirror side
  differs from its preview exactly where the source side does (N6).
- §1.3 K6 (c) is a tautology (N3). §1.3 K10: "seam stratum: K-A and K-D stay at their overall level" is loose; on
  subd_cube K-A is 82.1 % in the seam stratum vs. 93.4 % off it (N7).

Engineering recommendations presented as Artist decisions: **none found.** Every F-recommendation is labelled
"Empfehlung der Planung". The settled Artist inputs (A2 = A, A3 = S, residue follows the side worked on, KEEP-BLOCK)
are quoted, not reinterpreted.

**The F5 evidence statement** "A funktioniert für jeden einseitigen Schnitt exakt (Probe K10, K4)" goes beyond what
was measured (S4). What was measured: 1176 camera-free fuzz paths plus 179 camera sessions (plus 879 in R7), on three
assets, with the exact Lab X plane. "Einseitig" there means that every kept mutation stays on one side, which is not
what the Artist sees: they see their clicks, and a side-camera line can run over −X. Suggested wording: "für jeden
gemessenen einseitigen Schnitt (3 Assets, exakte X-Ebene, Stichproben)", plus one sentence that "einseitig" is
decided by the kept cuts. The same applies to §6's intro "spiegelt sie immer richtig". That is true by construction
for one-sided paths and should say so.

**Is the K-D / K-E "not used because" fair?** Yes.

- K-D keeps exactly K-A's E-c failures (K10: 0 / 48 / 0, 0 / 38 / 0, 0 / 39 / 0, all resolver-made vertices).
  Removing them would need canonical intersection frames and a snap without pid.
- K-E refuses every centred closed shape, loop and tail on the tie grid (K3) and 10–19 % of the fuzz (K10).

### Q11 — Reproduction

Full run (exit 0, 491.2 s). Every count and percentage below is identical to KD §1.3. Only timings differ.

| Section | KD | Re-run |
|---|---|---|
| K1 | K-A0 fails `-+-+` float 1.1e-16 (cube t = (0.3, 0.6), (0.123…, 0.876…)), 2.2e-16 (grid (0.3, 0.6)); K-A snap 1/2 there; head all `++++` | identical |
| K2 | only head vertex → edge t = 0.3 K-A0 float 1.2e-16 | identical |
| K3 tie grid | ties fired 9 / 9 / 9; K-A 0 / 0 / 0; K-C 9 / 9 / 9; K-D 9 / 9 / 9 | identical |
| K3 cube / head | cube faces 12 / 12 / 12, ties 0 / 6 / 0, K-A 12 / 8 / 12; head 159 (+3 invalid) / 162 / 162, no tie | identical |
| K4 | front 59: 1 / 58 / 0, gaps 133 / 133, K-A (i) 42 (17 float), (ii) 1 (58 float), K-C 59; 3/4 60: 0 / 0 / 60, 63 / 353, 50 (10 float), 0 (60 geom), 60; side 60: 43 / 374, 48 (11 float, 1 geom), 0 (60 geom), K-C 53 (7 refused, 7 with a record on −X) | identical |
| K5 | 37 (40) 36 / 37 36 30 12 22;15 · 39 (45) 50 / 52 26 34 0 23;16 · 39 (54) 64 / 64 39 28 0 13;26 · 37 (46) 27 / 168 3 26 0 19;18 · 40 (59) 23 / 178 2 32 0 32;8 | identical |
| K6 | (a) 1176 / 1176, 1176 / 1176; (b) 23 / 23 · 34: 8 / 12 / 14 · 46: 0 / 0 / 46; (c) 100 / 100 | identical |
| K7 c / d | c: K-A `+-++`, K-B `-+-+` geom, K-C refused; d: cube / grid `++++`, head float 2.5e-16, K-C refused, K-E head refused; d′ float, refused by K-E; d″ `+-++`, K-B geom | identical (b: seam 9 / 9, b2: 10 / 10 live on the cube) |
| K8 | 193 / 0 / 22 / 85; 201 / 0 / 14 / 85; 176 / 17 / 8 / 99; 184 / 17 / 0 / 99; targets 27 / 442, 108 / 948, 101 / 463 | identical |
| K9 | X1 262 / 38, 268 / 32, 239 / 26 / 35; X2 900 / 900; X3 287 / 13, 292 / 8, 296 / 4; X4 237 / 63, 222 / 78, 257 / 43; counters 27 / 269, 1 / 52, 2 / 6, 10 / 1652 | identical |
| K10 | exclusions 127 (119 / 8), 102 (97 / 5), 95 (93 / 2); K-A 87.1 / 90.5 / 80.7; K-B 64.1 / 82.4 / 68.1; K-C 100 / 100 / 100; K-D 87.1 / 90.5 / 90.4; K-E refused 48 / 38 / 78; seam K-B 40.6 / 45.9 / 39.8; origins 114+14 / 100+8 / 118+7 | identical |
| K10 times (median ms) | source / K-A / K-B / K-C / K-D: cube 1.12 / 1.86 / 1.96 / 1.51 / 2.17 | 0.89 / 1.51 / 1.60 / 1.26 / 1.68 (faster machine; K-C cheapest mirroring method again) |
| K11 | 0.036 / 0.18 / 0.70 ms; index 1.36 ms; 8.9e-16; 648 / 648 | 0.036 / 0.166 / 0.637 ms; 1.46 ms; 8.88e-16; 648 / 648 |
| K-D, no plane | golden net byte-identical; `test_knife_parity.py` exit 0 | identical |

---

## Findings

Severity:

- **BLOCKER** = must be resolved in KD / the addendum text and the slice spec before the addenda are decided.
- **SHOULD** = resolve in the text before the addenda.
- **NIT** = wording or slice detail.

| ID | Severity | Finding | Where | Evidence | Required change |
|---|---|---|---|---|---|
| B1 | **BLOCKER** | K-C refuses by collision, not by side. It commits paths whose kept mutations reach −X as a symmetric union that changes the Artist's side. The delta check cannot see it. | KD §1.3 K5, §2.1 (K-C row, K-A row), §2.6 c, §3, §6 F1 / F4 C | R1; R8 60 / 60 `E +-++`; R10 (KD's own K5 sample); `replay_mirrored :788, :804` | An explicit side rule before the replay (Q6), whose outcome F1 decides: refuse, or clip as option C; tests with the R1 / R8 rows. Correct the KD statements listed in Q10. |
| S1 | SHOULD | F1 is incomplete: it covers only the deliberate crossing; the accidental one, the seam-vertex / seam-edge difference and two-chain paths are missing. | KD §6 F1, F4 C | R2 table (K4 side 9 / 60); R8; R9 | Rewrite F1's situation and options for both cases; state what A means for a +X click whose line runs over −X; C is feasible at path level (R9 90 / 90). |
| S2 | SHOULD | The 6a log contract is unstated. AD-017 S1 and the resolver docstring permit `connect_vertices`; the replay treats every non-`split_edge` call as `split_face`. | KD §3 6a; AD-017 S1 addendum; `knife_resolve.py:14-15`; probe `:799` | Q4 map; R3 1176 / 1176 | Contract items 1–6 of Q4 in the AD-017 addendum. |
| S3 | SHOULD | 6b declares the Knife before 6c adds the mirrored preview and the click-time refusals (INV-11, KD §2.4). | KD §3 slice table | `symmetry_declarations.py`, `lab_app.py:287-316`, `:721` | Declare in 6c, or ship 6b + 6c together. |
| S4 | SHOULD | The Artist-facing evidence claims more than was measured, and "einseitig" is undefined for the Artist. | KD §6 F5, §6 intro | Q10 | Scope the claims to the samples; define "einseitig" by the kept cuts. |
| N1 | NIT | 6c "AD: none expected (Production UX, provisional)" is consistent with precedent, but should say "engineering default, Artist test before KEEP; variant is the Artist's". | KD §3 6c | Q8 | Wording. |
| N2 | NIT | 6a also asks for the pid → vertex map, which K-C does not use. | KD §3 6a; AD-SYM-03 §3 item 4 | probe `run` K-C branch `:911-916` | Name its user or drop it; amend item 4 accordingly. |
| N3 | NIT | K6 (c) derives the mirror path twice from the same, unchanged session path and compares the two. | KD §1.3 K6 (c), §2.5 | probe `:1531-1532` | Say that §2.5 holds by construction (the mirror is a pure function of the path). |
| N4 | NIT | E-d passes for every method in every row; E-b is tautological for K-C on one-sided paths; E-a + E-c are blind to coincident on-plane twins. | KD §1.2 | Q3; R4 (0 duplicates) | Name E-a / E-c as the discriminating criteria; add a duplicate-vertex assertion to the 6b tests. |
| N5 | NIT | The halves of a split self-mirrored, off-plane edge are mapped to themselves; the correct mirror swaps them. | probe `:781-785` | Q5 | In 6b, refuse a self-partner that is not on the plane, or map the halves crossed. |
| N6 | NIT | The §2.7 preview claim is overstated and not marked as an inference. | KD §2.7, §3 | Q10 | "The mirror side differs from its preview exactly where the source side does." |
| N7 | NIT | Small facts: rollback `:288/308` should be `:288/307`; on the cube K-A / K-D are below their overall level in the seam stratum (82.1 % vs. 87.1 %); the K5 table measures only E-a + E-c. | KD §1.1, §1.3 K10 / K5 | `knife_resolve.py:307`; K10 table | Wording. |
| N8 | NIT | The 6b contract details are unstated: partners come from the session-start state (as the probe's `Mirror`, `:883` before the resolve); on `SymmetryRefusal` the source mutations are taken back (`load_state(session_before)`, no history); and what the session does after a refused Enter (UX, F3 B). | KD §2.9, §3 6b | probe `run` | State them in the 6b spec. |
| N9 | NIT | The replay is generic at the primitive level. | KD §3 6b | AD-SYM-03 M-e, AD-017 Decision | Keep it scoped to the Knife's commit coordinator, or say under §3 item 2 why it is a shared service. |

### B1 — K-C refuses by collision, not by side (BLOCKER)

**Evidence.**

- **R8.** A single run "edge point in F (+X) → seam vertex s → edge point in H (−X)" with H ≠ partner(F) is accepted
  by the Production click rules (`accepted [True, True, True]`). The source cut is valid. K-C commits on 60 / 60 such
  paths: tie_grid 4, subd_cube 16, head 40. Every one is `E +-++` with `symmetry_state` `valid`. The four cuts meet at
  the seam vertex, which is option B's X. K-A gives the same result on the three examples printed.
- **R1.** A +X chain, a pen lift and a chain in a −X face that is not the partner face gives `E +-++` on tie_grid and
  on the head. A chain drawn entirely on −X is mirrored onto +X, which is fine semantically: the side worked on is −X.
- **R10.** In KD's own K5 sample (head, side camera, session #15), an accidental −X stretch between two gap breaks
  kept 2 `split_edge` and 1 `split_face` on −X. K-C mirrored them onto +X: `E +-++`.
- **Why the delta check cannot see it.** In all of these, every created element has a partner and no complete element
  became incomplete. The result is symmetric. Only E-b, which needs a one-sided reference that production does not
  have, shows that the Artist's side changed.
- **Why K7 c refuses.** K7 c crosses through a seam *edge*. The run then cuts F and its partner F′ (the face across
  the seam edge), so the replay meets a killed id (`:788` / `:804`). That collision is the only reason it refuses.

**Why it is a blocker.**

- KD's proposal and its addendum text rest on "refused until F1 is answered" and "the Artist's side bit-identical (E-b
  by construction)". Neither holds for the paths above.
- Implemented as probed, slice 6b would silently answer F1 = B (the cut and its mirror on both sides; an X at a seam
  vertex) for seam-vertex crossings, gap stretches and two-chain paths, while refusing seam-edge crossings. Whether the
  planner's line passes within `VERTEX_TOL_PX = 0.5` of a seam vertex would decide which.
- That is Product Truth decided by an implementation detail (M4), and invisible to every safety net.

**Not a reason to reject K-C.** With an explicit side rule checked before the replay (Q6), every K-C result again
equals "a one-sided cut plus its exact mirror". Every K10, K3, K4 and R7 result stands. The rule's outcome (refuse,
or clip per option C) is F1's. Until F1 is answered, the interim engineering rule "refuse" can be stated explicitly,
like AD-SYM-03 item 9.

---

## Code facts in KD §1.1 — checked

| KD claim | Result |
|---|---|
| Records carry a click-time pid (`knife.py:573-586`, `:579-580`); planner crossings get their own (`:484-486`) | VERIFIED |
| Mesh untouched until commit; `_on_commit` (`:617-648`): resolve without space records → `check_commit` → one `MeshStateCommand` → cut edges selected | VERIFIED |
| `_on_begin(self, mesh=None, scene=None, selection=None, **_)` (`:207`) swallows extra params | VERIFIED |
| `_connect_command` starts the Knife directly (`application.py:690-691`); `_knife_begin` `:904-921`, begin at `:910` | VERIFIED |
| `CContext.KNIFE` undeclared (`symmetry_declarations.py:40-48`); BLOCK row / MARK warning derived (`lab_app.py:287-316`, `:721`) | VERIFIED |
| Mutations only `split_edge` (`:517`, `:726`) and `split_face` (`:155`, `:228`, `:231`, `:292`, `:295`, `:320`) | VERIFIED (the AD-017 contract also permits `connect_vertices`; not used, S2) |
| Rollbacks `:288/308`, `:817/835`, `:851/858/864`, `check_commit :402` | VERIFIED, with `:308` → `:307` (N7) |
| pid → vertex local to `resolve()` (`resolved`, `_run_end_vertex :484-521`); only interior points reported (`:926`, `:947-956`); no record of kept calls | VERIFIED |
| Tie-break / order sites (`:184-188`, `:286-287`, `:942-943`, `:552`, `:772`, `:87`, `:991`) | VERIFIED |
| Resolver-made points computed in the face frame (`face_geometry.py:94-111`, origin = first boundary vertex); `_walk_run :720-726`, loop crossing `:700-705`; no pid | VERIFIED |
| `split_edge` places at `a*(1-t) + b*t` (`mesh.py:309`) | VERIFIED |
| `KnifeRenderData` is world positions only (`knife_preview.py:45-53`) | VERIFIED |
| Pixel rules: `EDGE_MARGIN_PX` used at `knife.py:317`, `OWN_POINT_SNAP_PX` at `knife_pick.py:254`, `VERTEX_TOL_PX` `knife_planner.py:38`, `ENDPOINT_THRESHOLD` `knife_pick.py:51` | VERIFIED |
| §0.2: H2-R1 three keys (T-R1a `:55`), H2-R4 (a) without `knife_render_data`, T-R4a methods only | VERIFIED (`test_app_lab_boundary.py:84-89`) |
| §0.3: no contradiction of substance between AD-SYM-03 §1, AD-017 and the code | VERIFIED for what I read; `decision.md` read only through citations |

---

## Appendix — scratch probes

Throwaway and in-memory; not committed as files. Each one imports the Discovery probe read-only through `importlib`
and reuses its sessions, methods (`run`), criterion (`evaluate`) and fixtures. Run from the repository root as
`python <file>`. `REPO` is the absolute path of this container's clone; change it to run elsewhere. Times on this
container: A 0.5 s, B 166 s, C 37 s, D 9 s.

### Probe A — R1 two-sided paths, R5 seam-adjacent recipes, R6 a face record on the plane

```python
"""Review CLAUDE-001 scratch probe A (not committed): adversarial K-C cases.

Imports the Discovery probe read-only and reuses its sessions, methods and criterion.
R1  two-sided paths without collision (does K-C refuse a path whose mutations reach -X?)
R5  seam-adjacent recipes (seam split after the face split, loop at a seam vertex, bridge/tail to seam corners)
R6  a face record exactly on the plane inside a seam-adjacent face (bypasses the 9 px rule)
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path("/home/user/Mirai-Bastel")
spec = importlib.util.spec_from_file_location("kp", REPO / "experiments/topology/symmetry_knife_probe.py")
kp = importlib.util.module_from_spec(spec)
sys.modules["kp"] = kp
spec.loader.exec_module(kp)


def grid_face(m, c, r):
    """tie_grid face with lower-left corner (c, r)."""
    want = {(float(c), float(r)), (float(c + 1), float(r)), (float(c + 1), float(r + 1)), (float(c), float(r + 1))}
    for f in m.all_face_ids():
        if {tuple(kp.vpos(m, v)[:2]) for v in m.face_vertices(f)} == want:
            return f
    raise KeyError((c, r))


def edge_at(m, p, q):
    pos = {tuple(kp.vpos(m, v)[:2]): v for v in m.all_vertex_ids()}
    return kp.kr.find_edge(m, pos[p], pos[q])


def vert_at(m, p):
    return next(v for v in m.all_vertex_ids() if tuple(kp.vpos(m, v)[:2]) == p)


def show(label, s, methods=("K-A", "K-C")):
    row = [label, "ok" if s.ref_ok else f"src: {s.ref_problem or 'nothing'}"]
    for meth in methods:
        r = kp.run(meth, s)
        extra = ""
        if r.ok:
            extra = f" V/E/F {len(r.mesh.all_vertex_ids())}/{len(r.mesh.all_edge_ids())}/{len(r.mesh.all_face_ids())}" \
                    f" dup {kp.duplicates(r.mesh)[0]}/{kp.duplicates(r.mesh)[1]} state {r.info.get('state')}"
        row.append(kp.describe(r) + extra)
    print(" | ".join(row))


def r1():
    print("\nR1 - two-sided paths that never touch a partner element (K-C refuses only on collision?)")
    m = kp.fresh("tie_grid")
    # chain 1 in +X square (1,0): left edge -> right edge;  chain 2 in -X square (-3,2) (partner: (2,2))
    e1a, e1b = edge_at(m, (1.0, 0.0), (1.0, 1.0)), edge_at(m, (2.0, 0.0), (2.0, 1.0))
    e2a, e2b = edge_at(m, (-3.0, 2.0), (-3.0, 3.0)), edge_at(m, (-2.0, 2.0), (-2.0, 3.0))
    two = [("click", kp.T_e(e1a, 0.3)), ("click", kp.T_e(e1b, 0.6)), ("lift",),
           ("click", kp.T_e(e2a, 0.4)), ("click", kp.T_e(e2b, 0.7))]
    show("tie_grid: +X chain, lift, -X chain (non-partner face)", kp.session_from("tie_grid", two))
    only_minus = [("click", kp.T_e(e2a, 0.4)), ("click", kp.T_e(e2b, 0.7))]
    show("tie_grid: one chain entirely on -X", kp.session_from("tie_grid", only_minus))
    # head: a +X chain and a -X chain far apart
    h = kp.fresh("head_basemesh")
    mir = kp.Mirror(h)
    plus = kp.plus_faces(h, strict=True)
    fa = plus[0]
    fb = next(f for f in plus[40:] if not set(h.face_vertices(f)) & set(h.face_vertices(fa)))
    gb = mir.fp[fb]
    ea, eb = h.face_edges(fa)[0], h.face_edges(fa)[2]
    ga, gbb = h.face_edges(gb)[0], h.face_edges(gb)[2]
    two_h = [("click", kp.T_e(ea, 0.3)), ("click", kp.T_e(eb, 0.6)), ("lift",),
             ("click", kp.T_e(ga, 0.4)), ("click", kp.T_e(gbb, 0.7))]
    show(f"head: +X chain in f{int(fa)}, lift, -X chain in f{int(gb)} (partner of f{int(fb)})",
         kp.session_from("head_basemesh", two_h))


def r5():
    print("\nR5 - seam-adjacent recipes (tie_grid square (0,1), its seam edge x=0 y in [1,2])")
    for asset in ("tie_grid",):
        m = kp.fresh(asset)
        f = grid_face(m, 0, 1)
        seam = edge_at(m, (0.0, 1.0), (0.0, 2.0))
        top = edge_at(m, (0.0, 2.0), (1.0, 2.0))
        right = edge_at(m, (1.0, 1.0), (1.0, 2.0))
        bottom = edge_at(m, (0.0, 1.0), (1.0, 1.0))
        s_lo, s_hi = vert_at(m, (0.0, 1.0)), vert_at(m, (0.0, 2.0))
        recipes = {
            # two runs in one face: the seam edge is split by the 2nd run, after the 1st run's split_face
            "top -> right -> seam edge (seam split after the face split)":
                [("click", kp.T_e(top, 0.7)), ("click", kp.T_e(right, 0.4)), ("click", kp.T_e(seam, 0.35))],
            "seam edge -> inside -> same seam edge (notch on the seam)":
                [("click", kp.T_e(seam, 0.3)), ("click", kp.T_f(f, (0.4, 1.5, 0.0))), ("click", kp.T_e(seam, 0.7))],
            "loop at a seam vertex (close_loop_at_vertex, x on the plane)":
                [("click", kp.T_v(s_lo)), ("click", kp.T_f(f, (0.6, 1.2, 0.0))), ("click", kp.T_f(f, (0.3, 1.7, 0.0))),
                 ("click", kp.T_v(s_lo))],
            "closed shape hugging the seam (bridges to seam corners)":
                [("click", kp.T_f(f, p)) for p in ((0.05, 1.3, 0.0), (0.3, 1.3, 0.0), (0.3, 1.7, 0.0), (0.05, 1.7, 0.0))]
                + [("click", kp.T_p(0))],
            "tail joined to a seam corner": [("click", kp.T_e(bottom, 0.6)), ("click", kp.T_f(f, (0.05, 1.93, 0.0)))],
            "seam vertex -> inside -> seam vertex (bent chord, both ends on the seam)":
                [("click", kp.T_v(s_lo)), ("click", kp.T_f(f, (0.5, 1.5, 0.0))), ("click", kp.T_v(s_hi))],
            "two seam-edge points in two seam faces, one chain via the shared seam vertex":
                [("click", kp.T_e(seam, 0.5)), ("click", kp.T_f(f, (0.5, 1.5, 0.0))), ("click", kp.T_v(s_hi)),
                 ("click", kp.T_e(edge_at(m, (0.0, 2.0), (0.0, 3.0)), 0.5))],
            "crossing cuts in a seam face (intersection with a cut of this commit)":
                [("click", kp.T_e(seam, 0.5)), ("click", kp.T_e(right, 0.5)), ("lift",),
                 ("click", kp.T_e(bottom, 0.5)), ("click", kp.T_e(top, 0.5))],
        }
        for label, acts in recipes.items():
            show(label, kp.session_from(asset, acts))


def r6():
    print("\nR6 - a face record exactly on the plane inside a seam-adjacent +X face (9 px rule bypassed)")
    m = kp.fresh("tie_grid")
    f = grid_face(m, 0, 1)
    right = edge_at(m, (1.0, 1.0), (1.0, 2.0))
    top = edge_at(m, (0.0, 2.0), (1.0, 2.0))
    acts = [("click", kp.T_e(right, 0.5)), ("click", kp.T_f(f, (0.0, 1.5, 0.0))), ("click", kp.T_e(top, 0.5))]
    s = kp.session_from("tie_grid", acts)
    print("accepted:", s.accepted)
    show("right edge -> face point at x = 0 (on the seam edge line) -> top edge", s)
    acts2 = [("click", kp.T_e(right, 0.5)), ("click", kp.T_f(f, (1e-300, 1.5, 0.0))), ("click", kp.T_e(top, 0.5))]
    show("same, face point at x = 1e-300", kp.session_from("tie_grid", acts2))


if __name__ == "__main__":
    r1()
    r5()
    r6()
```

Output:

```text

R1 - two-sided paths that never touch a partner element (K-C refuses only on collision?)
tie_grid: +X chain, lift, -X chain (non-partner face) | ok | E +-++ snap 0/4 V/E/F 36/57/22 dup 0/0 state valid | E +-++ V/E/F 36/57/22 dup 0/0 state valid
tie_grid: one chain entirely on -X | ok | E +-++ snap 0/2 V/E/F 32/51/20 dup 0/0 state valid | E +-++ V/E/F 32/51/20 dup 0/0 state valid
head: +X chain in f163, lift, -X chain in f56 (partner of f218) | ok | E +-++ snap 0/4 V/E/F 334/660/328 dup 0/0 state valid | E +-++ V/E/F 334/660/328 dup 0/0 state valid

R5 - seam-adjacent recipes (tie_grid square (0,1), its seam edge x=0 y in [1,2])
top -> right -> seam edge (seam split after the face split) | ok | E ++++ snap 0/2 V/E/F 33/54/22 dup 0/0 state valid | E ++++ V/E/F 33/54/22 dup 0/0 state valid
seam edge -> inside -> same seam edge (notch on the seam) | ok | E ++++ snap 0/1 V/E/F 32/51/20 dup 0/0 state valid | E ++++ V/E/F 32/51/20 dup 0/0 state valid
loop at a seam vertex (close_loop_at_vertex, x on the plane) | ok | E ++++ snap 0/2 V/E/F 32/53/22 dup 0/0 state valid | E ++++ V/E/F 32/53/22 dup 0/0 state valid
closed shape hugging the seam (bridges to seam corners) | ok | E ++++ snap 0/5 V/E/F 36/57/22 dup 0/0 state valid | E ++++ V/E/F 36/57/22 dup 0/0 state valid
tail joined to a seam corner | ok | E ++++ snap 0/2 V/E/F 32/51/20 dup 0/0 state valid | E ++++ V/E/F 32/51/20 dup 0/0 state valid
seam vertex -> inside -> seam vertex (bent chord, both ends on the seam) | ok | E ++++ snap 0/1 V/E/F 30/49/20 dup 0/0 state valid | E ++++ V/E/F 30/49/20 dup 0/0 state valid
two seam-edge points in two seam faces, one chain via the shared seam vertex | ok | E ++++ snap 0/1 V/E/F 31/50/20 dup 0/0 state valid | E ++++ V/E/F 31/50/20 dup 0/0 state valid
crossing cuts in a seam face (intersection with a cut of this commit) | ok | E ++++ snap 0/3 V/E/F 37/60/24 dup 0/0 state valid | E ++++ V/E/F 37/60/24 dup 0/0 state valid

R6 - a face record exactly on the plane inside a seam-adjacent +X face (9 px rule bypassed)
accepted: [True, True, True]
right edge -> face point at x = 0 (on the seam edge line) -> top edge | src: nothing | nothing | nothing
same, face point at x = 1e-300 | src: nothing | nothing | nothing

real	0m0.461s
user	0m0.263s
sys	0m0.154s
exit 0
```

### Probe B — R3 identity replay of the kept log, R4 K-C result integrity, R7 seam-biased fuzz, R2 K4 / K5 recount

```python
"""Review CLAUDE-001 scratch probe B (not committed).

R3  identity replay: every kept call of a K10 fuzz session replayed verbatim (ids mapped through call results)
    on a fresh session-start copy rebuilds the resolved mesh position-exactly (log completeness)
R4  the K-C results of K10: duplicate vertices, live seam edges on the plane, seam count = base + kept seam splits
R7  seam-biased fuzz: +X faces touching the seam only, targets biased to seam vertices / seam edges / near-seam
    face points; K-A vs K-C
R2  K4 / K5 recount with the Discovery's seeds: sessions with a record on -X that K-C did NOT refuse, and E-b of
    those; refusal reasons
"""
import collections
import importlib.util
import random
import sys
from pathlib import Path

REPO = Path("/home/user/Mirai-Bastel")
spec = importlib.util.spec_from_file_location("kp", REPO / "experiments/topology/symmetry_knife_probe.py")
kp = importlib.util.module_from_spec(spec)
sys.modules["kp"] = kp
spec.loader.exec_module(kp)
Mesh = kp.Mesh
SEED = 20261008


def identity_replay(state, calls) -> Mesh:
    m = Mesh.from_state(state)
    vmap, emap, fmap = {}, {}, {}
    V = lambda v: vmap.get(v, v)  # noqa: E731
    for c in calls:
        if c[0] == "split_edge":
            _op, eid, (a, b), t, (v, ea, eb), _p = c
            e2 = emap.get(eid, eid)
            ends = m.edge_vertices(e2)
            assert set(ends) == {V(a), V(b)}, "edge ends drifted"
            tt = t if ends[0] == V(a) else 1.0 - t
            v2, x1, x2 = Mesh.split_edge(m, e2, tt)
            vmap[v] = v2
            emap[ea], emap[eb] = (x1, x2) if ends[0] == V(a) else (x2, x1)
        else:
            _op, fid, va, vb, positions, (nvs, nes, f1, f2), _sides = c
            nv2, ne2, g1, g2 = Mesh.split_face(m, fmap.get(fid, fid), V(va), V(vb), positions)
            vmap.update(zip(nvs, nv2))
            emap.update(zip(nes, ne2))
            fmap[f1], fmap[f2] = g1, g2
    return m


def edge_sig(mesh):
    return sorted(tuple(sorted(tuple(kp.vpos(mesh, v)) for v in mesh.edge_vertices(e))) for e in mesh.all_edge_ids())


def r3_r4(fuzz):
    print("\nR3 identity replay of the kept log / R4 K-C result integrity (K10 fuzz, Discovery seed)")
    for asset, sessions in fuzz.items():
        st = collections.Counter()
        for s in sessions:
            if not s.ref_ok:
                continue
            st["n"] += 1
            mesh = Mesh.from_state(s.state)
            with kp.KeptLog(mesh) as log:
                kp.kr.CrossFaceResolver(mesh, s.state).resolve(s.path)
            calls = list(log.calls)
            st["calls"] += len(calls)
            try:
                rep = identity_replay(s.state, calls)
                same_faces = sorted(c for _k, c in kp.canon_faces(rep)) == sorted(c for _k, c in kp.canon_faces(mesh))
                same_edges = edge_sig(rep) == edge_sig(mesh)
                same_counts = (len(rep.all_vertex_ids()), len(rep.all_edge_ids()), len(rep.all_face_ids())) == \
                              (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids()))
                st["identity replay identical"] += same_faces and same_edges and same_counts
            except Exception as exc:  # noqa: BLE001
                st[f"replay exception {type(exc).__name__}"] += 1
            # R4 on the K-C result
            r = kp.run("K-C", s)
            if not r.ok:
                st[f"K-C {r.status[:30]}"] += 1
                continue
            mm = r.mesh
            same, near = kp.duplicates(mm)
            st["K-C dup identical"] += same
            st["K-C dup < 1e-9"] += near
            d = mm.symmetry_definition
            live = [e for e in d.seam_edges if mm.is_valid_edge(e)]
            st["K-C seam edge off plane"] += sum(1 for e in live for v in mm.edge_vertices(e) if kp.vpos(mm, v)[0] != 0.0)
            def undeclared_on_plane(mx):
                dd = mx.symmetry_definition.seam_edges
                return sum(1 for e in mx.all_edge_ids() if e not in dd and
                           all(kp.vpos(mx, v)[0] == 0.0 for v in mx.edge_vertices(e)))
            st["K-C seam all live, no new undeclared on-plane edge"] += (
                len(live) == len(d.seam_edges)
                and undeclared_on_plane(mm) == undeclared_on_plane(Mesh.from_state(s.state)))
            st["K-C state valid"] += r.info.get("state") == "valid"
        print(asset, dict(st))


def seam_fuzz(name, rnd, n):
    mesh0 = kp.fresh(name)
    svs = kp.seam_vertices(mesh0)
    seam = mesh0.symmetry_definition.seam_edges
    faces = [f for f in kp.plus_faces(mesh0) if set(mesh0.face_vertices(f)) & svs]
    allowed = set(kp.plus_faces(mesh0))
    out = []

    def target(mesh, f):
        vs, es = mesh.face_vertices(f), mesh.face_edges(f)
        r = rnd.random()
        if r < 0.3:
            sv = [v for v in vs if v in svs]
            return kp.T_v(rnd.choice(sv) if sv and rnd.random() < 0.7 else rnd.choice(vs))
        if r < 0.75:
            se = [e for e in es if e in seam]
            e = rnd.choice(se) if se and rnd.random() < 0.6 else rnd.choice(es)
            return kp.T_e(e, 0.5 if rnd.random() < 0.3 else rnd.uniform(0.08, 0.92))
        pts = [kp.vpos(mesh, v) for v in vs]
        w = [rnd.uniform(1.0, 3.0) if v in svs else rnd.uniform(0.2, 1.0) for v in vs]
        tot = sum(w)
        return kp.T_f(f, tuple(sum(w[i] * pts[i][k] for i in range(len(pts))) / tot for k in range(3)))

    for _ in range(n):
        mesh = Mesh.from_state(kp.start_state(name))
        knife = kp.new_knife(mesh)
        acts, goal, clicks, tries = [], rnd.randint(2, 8), 0, 0
        while clicks < goal and tries < goal * 10:
            tries += 1
            r = rnd.random()
            act = None
            chain = knife.chain_points
            if chain and len([p for p in chain if not p.get("crossing")]) >= 3 and r < 0.12:
                first = chain[0]
                act = ("click", kp.T_v(first["vertex_id"]) if first["kind"] == "vertex" else kp.T_p(first["pid"]))
            elif knife.last_point is not None and r < 0.18:
                act = ("lift",)
            elif r < 0.22 and knife.snap_points:
                own = [p for p in knife.snap_points if p["kind"] in ("edge", "vertex")]
                if own:
                    p = rnd.choice(own)
                    act = ("click", kp.T_v(p["vertex_id"]) if p["kind"] == "vertex" else kp.T_p(p["pid"]))
            if act is None:
                last = knife.last_point
                cand = [f for f in kp.point_faces(mesh, last) if f in allowed] if last is not None else []
                f = rnd.choice(cand) if cand and rnd.random() < 0.8 else rnd.choice(faces)
                act = ("click", target(mesh, f))
            with kp.quiet():
                ok = knife.click(act[1]) if act[0] == "click" else knife.lift()
            acts.append(act)
            if ok and act[0] == "click":
                clicks += 1
        out.append(kp.Session(name, kp.resolver_path(knife)))
    return out


def r7():
    print("\nR7 seam-biased fuzz (faces touching the seam, seam targets preferred)")
    rnd = random.Random(SEED + 77)
    for asset in ("subd_cube", "head_basemesh", "tie_grid"):
        st = collections.Counter()
        for s in seam_fuzz(asset, rnd, 400):
            if not s.ref_ok:
                st["source invalid"] += 1
                continue
            st["n"] += 1
            st["touches seam"] += kp.touches_seam(kp.fresh(asset), s.path)
            for meth in ("K-A", "K-C"):
                r = kp.run(meth, s)
                if r.ok and r.ea and r.eb and r.ec and r.ed:
                    st[f"{meth} all four"] += 1
                elif r.ok:
                    st[f"{meth} fail {r.flags()} {r.ec_kind}"] += 1
                    if meth == "K-C" and r.ea and not (r.eb and r.ec):
                        st["K-C SILENT"] += 1
                else:
                    st[f"{meth} {r.status[:40]}"] += 1
        print(asset, dict(sorted(st.items())))


def r2():
    print("\nR2 K4 / K5 recount (Discovery seeds): records on -X vs K-C refusal")
    rnd4 = random.Random(SEED + 4)
    rnd5 = random.Random(SEED + 5)
    plan = [("K4", rnd4, "head_basemesh", cam, 60, 0.0) for cam in kp.CAMERAS] + \
           [("K5", rnd5, name, cam, 40, 0.3) for name, cam in
            (("hole_grid", "front"), ("hole_grid", "3/4 (+X)"), ("head_basemesh", "front"),
             ("head_basemesh", "3/4 (+X)"), ("head_basemesh", "side (+X)"))]
    for sec, rnd, name, cam, n, p_space in plan:
        st = collections.Counter()
        for _ in range(n):
            s = kp.camera_session(name, rnd, cam, rnd.randint(2, 6), p_space=p_space)
            if not s.ref_ok:
                continue
            st["sessions"] += 1
            minus = kp.reaches_other_side(s)
            r = kp.run("K-C", s)
            refused = r.status.startswith("refused")
            st["-X record"] += minus
            if minus and not refused:
                st["-X record, K-C NOT refused"] += 1
                st[f"   of those: E {r.flags()}"] += 1
            if refused:
                st[f"refused: {r.status[9:60]}"] += 1
            if refused and not minus:
                st["refused without -X record"] += 1
        print(sec, name, cam, dict(sorted(st.items())))


if __name__ == "__main__":
    rnd = random.Random(SEED)
    fuzz = {a: kp.fuzz_sessions_for(a, rnd, 500) for a in ("subd_cube", "head_basemesh", "tie_grid")}
    r3_r4(fuzz)
    r7()
    r2()
```

Output:

```text

R3 identity replay of the kept log / R4 K-C result integrity (K10 fuzz, Discovery seed)
subd_cube {'n': 373, 'calls': 1665, 'identity replay identical': 373, 'K-C dup identical': 0, 'K-C dup < 1e-9': 0, 'K-C seam edge off plane': 0, 'K-C seam all live, no new undeclared on-plane edge': 373, 'K-C state valid': 373}
head_basemesh {'n': 398, 'calls': 1671, 'identity replay identical': 398, 'K-C dup identical': 0, 'K-C dup < 1e-9': 0, 'K-C seam edge off plane': 0, 'K-C seam all live, no new undeclared on-plane edge': 398, 'K-C state valid': 398}
tie_grid {'n': 405, 'calls': 1833, 'identity replay identical': 405, 'K-C dup identical': 0, 'K-C dup < 1e-9': 0, 'K-C seam edge off plane': 0, 'K-C seam all live, no new undeclared on-plane edge': 405, 'K-C state valid': 405}

R7 seam-biased fuzz (faces touching the seam, seam targets preferred)
subd_cube {'K-A all four': 258, 'K-A fail -+-+ float': 35, 'K-C all four': 293, 'n': 293, 'source invalid': 107, 'touches seam': 274}
head_basemesh {'K-A all four': 249, 'K-A fail -+-+ float': 29, 'K-C all four': 278, 'n': 278, 'source invalid': 122, 'touches seam': 266}
tie_grid {'K-A all four': 269, 'K-A fail -+-+ float': 39, 'K-C all four': 308, 'n': 308, 'source invalid': 92, 'touches seam': 283}

R2 K4 / K5 recount (Discovery seeds): records on -X vs K-C refusal
K4 head_basemesh front {'-X record': 0, 'sessions': 59}
K4 head_basemesh 3/4 (+X) {'-X record': 0, 'sessions': 60}
K4 head_basemesh side (+X) {'   of those: E ++++': 2, '-X record': 9, '-X record, K-C NOT refused': 2, 'refused: mirror edge already cut by the source (the path rea': 4, 'refused: mirror face already cut by the source (the path rea': 3, 'sessions': 60}
K5 hole_grid front {'-X record': 15, 'refused: mirror edge already cut by the source (the path rea': 7, 'refused: mirror face already cut by the source (the path rea': 8, 'sessions': 37}
K5 hole_grid 3/4 (+X) {'-X record': 16, 'refused: mirror edge already cut by the source (the path rea': 6, 'refused: mirror face already cut by the source (the path rea': 10, 'sessions': 39}
K5 head_basemesh front {'-X record': 26, 'refused: mirror edge already cut by the source (the path rea': 13, 'refused: mirror face already cut by the source (the path rea': 13, 'sessions': 39}
K5 head_basemesh 3/4 (+X) {'-X record': 18, 'refused: mirror edge already cut by the source (the path rea': 9, 'refused: mirror face already cut by the source (the path rea': 9, 'sessions': 37}
K5 head_basemesh side (+X) {'   of those: E ++++': 5, '   of those: E +-++': 1, '-X record': 14, '-X record, K-C NOT refused': 6, 'refused: mirror edge already cut by the source (the path rea': 3, 'refused: mirror face already cut by the source (the path rea': 5, 'sessions': 40}

real	2m46.022s
user	2m35.345s
sys	0m9.083s
exit 0
```

### Probe C — R8 one run through a seam vertex into a non-partner face, R9 F1 option C clip

```python
"""Review CLAUDE-001 scratch probe C (not committed).

R8  one run crossing the plane through a SEAM VERTEX into a -X face that is not the partner of the +X face
    (K7 c crosses through a seam EDGE only): does K-C refuse, as KD reports for case c?
R9  F1 option C feasibility, technical only: clip each path at its first record on -X (keep the records up to
    the seam, replace every -X stretch by a pen lift) and run K-C on the clipped path; K4 side camera and K5
    sessions that K-C refused.
"""
import collections
import importlib.util
import random
import sys
from pathlib import Path

REPO = Path("/home/user/Mirai-Bastel")
spec = importlib.util.spec_from_file_location("kp", REPO / "experiments/topology/symmetry_knife_probe.py")
kp = importlib.util.module_from_spec(spec)
sys.modules["kp"] = kp
spec.loader.exec_module(kp)
Mesh = kp.Mesh
SEED = 20261008


def row(label, s):
    out = [label, "ok" if s.ref_ok else f"src: {s.ref_problem or 'nothing'}", f"accepted {s.accepted}"]
    for meth in ("K-A", "K-C"):
        r = kp.run(meth, s)
        extra = f" V/E/F {len(r.mesh.all_vertex_ids())}/{len(r.mesh.all_edge_ids())}/{len(r.mesh.all_face_ids())}" \
                f" state {r.info.get('state')}" if r.ok else ""
        out.append(f"{meth}: {kp.describe(r)}{extra}")
    print(" | ".join(out))


def seam_vertex_crossings(asset, limit=40):
    """Paths edge point in F (+X) -> seam vertex s -> edge point in H (-X), H != partner(F), both edges
    not touching s. One per (s, F, H) until `limit`."""
    m = kp.fresh(asset)
    mir = kp.Mirror(m)
    svs = kp.seam_vertices(m)
    plus, minus = set(kp.plus_faces(m)), set()
    for f in m.all_face_ids():
        xs = [kp.vpos(m, v)[0] for v in m.face_vertices(f)]
        if max(xs) <= 0.0 and min(xs) < 0.0:
            minus.add(f)
    out = []
    for s in sorted(svs):
        around = {f for e in m.vertex_edges(s) for f in m.edge_faces(e)}
        for F in sorted(around & plus):
            for H in sorted(around & minus):
                if mir.fp.get(F) == H:
                    continue
                ef = next((e for e in m.face_edges(F) if s not in m.edge_vertices(e)), None)
                eh = next((e for e in m.face_edges(H) if s not in m.edge_vertices(e)), None)
                if ef is None or eh is None:
                    continue
                out.append((F, H, [("click", kp.T_e(ef, 0.4)), ("click", kp.T_v(s)), ("click", kp.T_e(eh, 0.6))]))
                if len(out) >= limit:
                    return out
    return out


def r8():
    print("\nR8 - one run through a seam VERTEX into a non-partner -X face")
    for asset in ("tie_grid", "subd_cube", "head_basemesh"):
        cases = seam_vertex_crossings(asset)
        st = collections.Counter()
        first = None
        for F, H, acts in cases:
            s = kp.session_from(asset, acts)
            if not s.ref_ok:
                st["source invalid"] += 1
                continue
            st["n"] += 1
            r = kp.run("K-C", s)
            key = r.status if not r.ok else f"committed E {r.flags()} state {r.info.get('state')}"
            st[key] += 1
            if first is None and r.ok:
                first = (F, H, s)
        print(asset, f"{len(cases)} paths:", dict(st))
        if first is not None:
            F, H, s = first
            row(f"  example {asset} F=f{int(F)} -> seam vertex -> H=f{int(H)}", s)


def clip_to_plus(mesh, path):
    """F1 option C, minimal: every maximal stretch of records on -X becomes one pen lift."""
    out, in_minus = [], False
    for p in path:
        if p["kind"] == "break":
            if not in_minus:
                out.append(p)
            continue
        if kp.target_world(mesh, p)[0] < 0.0:
            if not in_minus:
                out.append(dict(kp.LIFT))
            in_minus = True
            continue
        in_minus = False
        out.append(p)
    return out


def r9():
    print("\nR9 - F1 option C (cut only to the seam), technical feasibility on the sessions K-C refused")
    rnd4 = random.Random(SEED + 4)
    rnd5 = random.Random(SEED + 5)
    plan = [("K4", rnd4, "head_basemesh", cam, 60, 0.0) for cam in kp.CAMERAS] + \
           [("K5", rnd5, name, cam, 40, 0.3) for name, cam in
            (("hole_grid", "front"), ("hole_grid", "3/4 (+X)"), ("head_basemesh", "front"),
             ("head_basemesh", "3/4 (+X)"), ("head_basemesh", "side (+X)"))]
    total = collections.Counter()
    for sec, rnd, name, cam, n, p_space in plan:
        st = collections.Counter()
        for _ in range(n):
            s = kp.camera_session(name, rnd, cam, rnd.randint(2, 6), p_space=p_space)
            if not s.ref_ok:
                continue
            r = kp.run("K-C", s)
            if not r.status.startswith("refused"):
                continue
            st["refused"] += 1
            mesh = Mesh.from_state(s.state)
            clipped = clip_to_plus(mesh, s.path)
            st["clipped path keeps a seam record"] += any(
                p["kind"] != "break" and kp.target_world(mesh, p)[0] == 0.0 for p in clipped)
            c = kp.Session(name, clipped, s.state)
            if not c.ref_ok:
                st["clipped: source cuts nothing / rolled back"] += 1
                continue
            rc = kp.run("K-C", c)
            if rc.ok and rc.ea and rc.eb and rc.ec and rc.ed:
                st["clipped: K-C all four"] += 1
            else:
                st[f"clipped: {rc.status[:50] if not rc.ok else 'E ' + rc.flags()}"] += 1
        total.update(st)
        print(sec, name, cam, dict(sorted(st.items())))
    print("total", dict(sorted(total.items())))


if __name__ == "__main__":
    r8()
    r9()
```

Output:

```text

R8 - one run through a seam VERTEX into a non-partner -X face
tie_grid 4 paths: {'n': 4, 'committed E +-++ state valid': 4}
  example tie_grid F=f3 -> seam vertex -> H=f8 | ok | accepted [True, True, True] | K-A: E +-++ snap 0/2 V/E/F 32/53/22 state valid | K-C: E +-++ V/E/F 32/53/22 state valid
subd_cube 16 paths: {'n': 16, 'committed E +-++ state valid': 16}
  example subd_cube F=f0 -> seam vertex -> H=f2 | ok | accepted [True, True, True] | K-A: E +-++ snap 0/2 V/E/F 30/56/28 state valid | K-C: E +-++ V/E/F 30/56/28 state valid
head_basemesh 40 paths: {'n': 40, 'committed E +-++ state valid': 40}
  example head_basemesh F=f162 -> seam vertex -> H=f9 | ok | accepted [True, True, True] | K-A: E +-++ snap 0/2 V/E/F 330/656/328 state valid | K-C: E +-++ V/E/F 330/656/328 state valid

R9 - F1 option C (cut only to the seam), technical feasibility on the sessions K-C refused
K4 head_basemesh front {}
K4 head_basemesh 3/4 (+X) {}
K4 head_basemesh side (+X) {'clipped path keeps a seam record': 7, 'clipped: K-C all four': 7, 'refused': 7}
K5 hole_grid front {'clipped path keeps a seam record': 15, 'clipped: K-C all four': 15, 'refused': 15}
K5 hole_grid 3/4 (+X) {'clipped path keeps a seam record': 16, 'clipped: K-C all four': 16, 'refused': 16}
K5 head_basemesh front {'clipped path keeps a seam record': 26, 'clipped: K-C all four': 26, 'refused': 26}
K5 head_basemesh 3/4 (+X) {'clipped path keeps a seam record': 18, 'clipped: K-C all four': 18, 'refused': 18}
K5 head_basemesh side (+X) {'clipped path keeps a seam record': 8, 'clipped: K-C all four': 8, 'refused': 8}
total {'clipped path keeps a seam record': 90, 'clipped: K-C all four': 90, 'refused': 90}

real	0m36.691s
user	0m36.086s
sys	0m0.174s
exit 0
```

### Probe D — R10 the K5 session committed with a -X record, R11 partner-less faces on man_with_shoes_basemesh

```python
"""Review CLAUDE-001 scratch probe D (not committed).

R10 the K5 head_basemesh side-camera session that K-C committed although a record lies on -X: what it is
R11 man_with_shoes_basemesh: faces without a partner whose vertices all have partners (P2 refuses them
    although no vertex is magenta)
"""
import collections
import importlib.util
import random
import sys
from pathlib import Path

REPO = Path("/home/user/Mirai-Bastel")
spec = importlib.util.spec_from_file_location("kp", REPO / "experiments/topology/symmetry_knife_probe.py")
kp = importlib.util.module_from_spec(spec)
sys.modules["kp"] = kp
spec.loader.exec_module(kp)
Mesh = kp.Mesh
SEED = 20261008


def side(x):
    return "+" if x > 0 else "-" if x < 0 else "0"


def r10():
    print("\nR10 - K5 sessions with a -X record that K-C committed")
    rnd5 = random.Random(SEED + 5)
    for name, cam in (("hole_grid", "front"), ("hole_grid", "3/4 (+X)"), ("head_basemesh", "front"),
                      ("head_basemesh", "3/4 (+X)"), ("head_basemesh", "side (+X)")):
        for i in range(40):
            s = kp.camera_session(name, rnd5, cam, rnd5.randint(2, 6), p_space=0.3)
            if not s.ref_ok or not kp.reaches_other_side(s):
                continue
            r = kp.run("K-C", s)
            if r.status.startswith("refused"):
                continue
            mesh = Mesh.from_state(s.state)
            with kp.KeptLog(mesh) as log:
                kp.kr.CrossFaceResolver(mesh, s.state).resolve(s.path)
            m0 = Mesh.from_state(s.state)
            kept_sides = collections.Counter()
            for c in log.calls:
                if c[0] == "split_edge":
                    kept_sides["split_edge on " + side(c[5][0])] += 1
                else:
                    xs = [kp.vpos(m0, v)[0] for v in m0.face_vertices(c[1])] if m0.is_valid_face(c[1]) else None
                    kept_sides["split_face in " + ("created face" if xs is None else kp.face_class(
                        [(x, 0, 0) for x in xs]))] += 1
            recs = "".join(side(kp.target_world(m0, p)[0]) if p["kind"] != "break" else "|" for p in s.path)
            seam_v = sum(1 for p in s.path if p["kind"] == "vertex" and p["vertex_id"] in kp.seam_vertices(m0))
            print(f"{name} {cam} #{i}: E {r.flags()}  records {recs}  seam-vertex records {seam_v}  kept {dict(kept_sides)}")


def r11():
    print("\nR11 - man_with_shoes_basemesh: +X faces without a partner, by cause")
    m = kp.fresh("man_with_shoes_basemesh")
    idx = kp.SymmetryIndex(m)
    st = collections.Counter()
    for f in kp.plus_faces(m):
        if idx.face_partner(f) is not None:
            continue
        if all(idx.vertex_partner(v) is not None for v in m.face_vertices(f)):
            st["all vertices paired, image is no face"] += 1
        else:
            st["an unpaired vertex"] += 1
    print(dict(st))


if __name__ == "__main__":
    r10()
    r11()
```

Output:

```text

R10 - K5 sessions with a -X record that K-C committed
head_basemesh side (+X) #9: E ++++  records ||-|+++++++++++  seam-vertex records 0  kept {'split_edge on +': 10, 'split_face in +': 10}
head_basemesh side (+X) #15: E +-++  records ++|+++++++++++||--|0++++++|-||0+++++++++++++++++++++++++  seam-vertex records 0  kept {'split_face in +': 34, 'split_edge on +': 40, 'split_edge on -': 2, 'split_face in -': 1, 'split_edge on 0': 2, 'split_face in created face': 11}
head_basemesh side (+X) #18: E ++++  records |-|+++++++++0||-|++++++++++0|  seam-vertex records 0  kept {'split_edge on +': 19, 'split_face in +': 12, 'split_face in created face': 8, 'split_edge on 0': 2}
head_basemesh side (+X) #20: E ++++  records ++++++++++++0||++++++++++|-|  seam-vertex records 1  kept {'split_edge on +': 20, 'split_face in +': 21}
head_basemesh side (+X) #29: E ++++  records ||-|+++  seam-vertex records 0  kept {'split_edge on +': 1, 'split_face in +': 2}
head_basemesh side (+X) #30: E ++++  records ++++++|-|  seam-vertex records 0  kept {'split_edge on +': 5, 'split_face in +': 4}

R11 - man_with_shoes_basemesh: +X faces without a partner, by cause
{'an unpaired vertex': 101}

real	0m9.021s
user	0m8.561s
sys	0m0.363s
exit 0
```
