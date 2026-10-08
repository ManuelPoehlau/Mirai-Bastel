# AD-SYM-03 — Symmetric Topology Coordination

**Status:** **DECIDED** (Manu, 2026-10-08), as revised after review CLAUDE-001 and with the Artist verdicts A1/A2/A3 (§6, §9).
The AD-013 H2 amendment (G-2), required before Slice 3 (§5, §7), is **DECIDED** (Manu, 2026-10-08; [AD-013, Addendum 2026-10-08](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-08-ad-sym-03-slice-3--h2-amendment-g-2-context-keyed-refusal-for-c-fail-closed-block-row)).
**Date:** 2026-10-06 · revised 2026-10-07 after the independent review CLAUDE-001 (answers in §9) · decided 2026-10-08
**Mode (M5):** Discovery → decision preparation. No implementation, no code change.
**Belongs to:** Symmetry Lab track (WP-SYM-LAB), follow-up of WP-SYM-LAB-03; working milestone
"Symmetry Basic Modeling Parity" (Discovery header)
**Primary input (preserved, not edited):**
[`SYMMETRY_PRODUCTION_OPERATIONS_DISCOVERY.md`](../research/symmetry/SYMMETRY_PRODUCTION_OPERATIONS_DISCOVERY.md)
(cited as **Disc.**; its observations N1–N8, classes A–D and questions Q1–Q7 are used by their numbers)
**Basis (unchanged, only linked):** [AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md),
[AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md) (§2.1–§2.4, §4),
[AD-017](AD-017-CUT-ENGINE-CONTEXTUAL-C.md), [AD-013 addendum H2](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-03-wp-sym-lab-03-h2--experiment-input-hook-in-application),
[`WP_DELETE_DISSOLVE_PLAN.md`](../WP_DELETE_DISSOLVE_PLAN.md) (DD-2),
[`SYMMETRY_DESIGN_BRIEF.md`](../research/symmetry/SYMMETRY_DESIGN_BRIEF.md) (INV-1…13),
[`SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md`](../research/symmetry/SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md) (R2),
[`WP-SYM-LAB-03_REBASE_PLAN.md`](WP-SYM-LAB-03_REBASE_PLAN.md), [`experiments/symmetry_lab/README.md`](../../experiments/symmetry_lab/README.md)
**Probes:** [`experiments/topology/symmetry_ops_probe.py`](../../experiments/topology/symmetry_ops_probe.py) (Disc.)
and, new for this AD, [`experiments/topology/symmetry_coordination_probe.py`](../../experiments/topology/symmetry_coordination_probe.py)
(read-only, in-memory; `python experiments/topology/symmetry_coordination_probe.py`).

**Question:** How does Symmetry *coordinate* the existing topology operations (Split, Edge/Vertex Connect,
Delete/Dissolve, Knife, later Extrude) — instead of growing a `SymmetricX` copy of each — so that the Symmetry
Lab can **support** them under symmetry rather than refuse them?

**Why now (owner intent, Manu, 2026-10-06, as given in the task):** the Lab should support these operations
under symmetry, not refuse them. KEEP-BLOCK (AD-SYM-02 §4, 2026-10-03) stays valid for operations that cannot
mirror; a supported operation leaves the gate through a declaration (N8), not through a hand list.
**Accepted interim state (Manu, 2026-10-06, as given in the task):** until support exists, Delete / Dissolve /
DissolveNoCleanup run one-sided under Symmetry + BLOCK in the Lab. This AD does not change the gate table.

**Evidence rule:** §1 holds observations only (code read, probe run, verdicts as recorded). §2–§7 are
proposals and say so. Every proposal names the observation, probe row, AD or verdict it rests on.

---

## 1. Existing fact / Evidence

### 1.1 From the Discovery (taken over, not re-derived)

- **[Disc. §1.2, probe D]** Every Production topology op is "snapshot → Core primitive(s) → push
  `MeshStateCommand`" **inside** the op function (`split.py`, `connect_per_face.py`,
  `connect_vertices_per_face.py`, `delete_dissolve.py`); the Knife pushes in `KnifeTool._on_commit`
  (`knife.py:617-643`). Wrapping an op in `Application.apply_mesh_change` gives **2** history entries.
- **[Disc. §1.7 (a)]** Selection ∪ partners passed to the **unchanged** op in one call gives one Undo step and a
  symmetric result for Edge Connect, Vertex Connect, Delete, Dissolve and non-seam Extrude (plane x=0).
- **[Disc. §1.7 (b)]** Three checks disagree: `symmetry_state` (vertex/position) missed one-sided Vertex Connect,
  Delete face and (head) Dissolve edge; the Lab's `topological_pairing` missed one-sided Delete; **only the
  face-level check ("faces whose vertex image is not a face") saw every one-sided case.**
- **[Disc. §1.7]** Non-seam edges without a vertex-image partner edge: 0/40 (`subd_cube`), 0/612 (`head_basemesh`).
- **[Disc. §1.7, §1.3 P3]** Raw `t≠0.5` on an orientation-reversed partner edge lands 1e-16 off → `UNPAIRED`.
- **[Disc. §1.7]** Splitting / dissolving / deleting seam elements leaves dead seam ids; `symmetry_state` stays
  `valid` in most of these cases.
- **[Disc. §1.4, AD-017]** Knife is not a chain of Split/Connect; its unit of intent is the virtual path resolved
  at commit by `resolve_cross_face`.
- **[Disc. §1.1]** `Operation.supports_symmetry` exists for Move/Rotate/Scale; topology ops are not `Operation`s
  and have nowhere to declare support. The Lab's BLOCK row (`lab_app.unsupported_commands`) starts from the fixed
  set `{Connect}` plus transform commands whose Operation lacks the declaration; Delete/Dissolve are absent
  (DD-2).
- **[Disc. §4]** Classes: Edge Connect B, Vertex Connect B, Delete/Dissolve (non-seam) B, Split C, Knife C,
  Extrude C (+ not in Production), on/across the seam D.

### 1.2 Code facts this AD adds (read at `bbe9a0f`)

- **[Code]** `HistoryStack` (`src/core/history.py`) is a plain two-list stack: `push`, `undo`, `redo`,
  `can_*`, `__len__`. No group, no merge, no top-of-stack access; its docstring: "Kein Undo-Baum, kein Merge,
  keine Cross-Subsystem-Transaktionen". It is Core (frozen, `CORE_V1_FREEZE.md` §7). AD-SYM-02 §3 item 2:
  "`OperationContext` und `HistoryStack` werden **nicht** geändert."
- **[Code]** `Application` keeps a selection mirror stack 1:1 with every push it triggers
  (`_record_selection_history`, `application.py:1436`); `apply_mesh_change` (`:1369`) takes both snapshots,
  runs `mutate`, restores on raise, records nothing on no change, pushes one `MeshStateCommand`, records the
  mirror entry, invalidates the pick cache, notifies the viewport. It records the selection mirror **right after
  the push**, i.e. before a caller could set a selection residue.
- **[Code]** `connect_per_face._apply(mesh, selected)` is already a pure mutation (no push); it computes the
  midpoint set `mids` and drops it (returns only created edges). `split_selected_edge`,
  `connect_vertices_per_face` and `remove_selected` inline their mutation between snapshot and push.
- **[Code]** `Mesh.split_edge` places the new vertex at `a*(1-t) + b*t` (`mesh.py:309`). For `t=0.5` the
  expression is symmetric in `a, b` (IEEE addition is commutative), so the orientation of the partner edge does
  not matter; for `t≠0.5` it does (`1-(1-t)` need not equal `t`) — the arithmetic cause of P3.
- **[Code]** `mirror_position(p, o, n) = p − 2·((p−o)·n)·n` (`mirai/symmetry.py`). For `n` an axis unit vector
  and `o[axis] == 0` it reduces to exact negation of one coordinate (every other term is an exact `±0`).
  The Lab's planes are exactly these (E1: through the origin, normal `(1,0,0)`/`(0,1,0)`/`(0,0,1)`). AD-SYM-01 /
  `SymmetryDefinition` allow any point + unit normal.
- **[Code]** `resolve_c_context` (`contextual_c.py`) counts selected elements: 1 edge → SPLIT, 2+ edges →
  EDGE_CONNECT, 2+ vertices → VERTEX_CONNECT, empty → KNIFE.
- **[Code]** The command gate refuses by command identity only; "refusals that depend on more than the command
  (click position, part of the selection, mirror side)" are listed under AD-013 H2 "Limits of G" and reopen the
  addendum (H2-R6). The preview row is already an **allow-list** ("every other command, including future ones, is
  refused by default", H2 review F7).
- **[Code]** Runtime-refusal precedent: under symmetry a transform whose seam vertex would leave the plane is
  refused at its first step (`SeamConstraintError`, caught in `Application._transform_step`,
  `application.py:1260`): visible status, no history, mesh unchanged (WP-SYM-LAB-03 H5).
- **[Code]** `knife_resolve.select_bridge` breaks distance ties "by position — first the loop point's, then the
  boundary vertex's, lexicographically" (module docstring and `:161-198`). Lexicographic order on positions is
  not invariant under mirroring.
- **[Code]** `Tool.begin(**params)` takes free keyword params; `KnifeTool` is begun with
  `mesh=…, scene=…, selection=…` (`application.py:733-741`).

### 1.3 New probe results (`symmetry_coordination_probe.py`)

Observations only. Columns as in Disc. §1.7 (`state` = `symmetry_state`; `topo` = Lab pairing pairs/vertex
conflicts/face-pair conflicts; `faces w/o partner` = face-level check; `sides` = Lab `topological_sides`
component count). Plane x=0, Lab E3 seam. Numbers `subd_cube` / `head_basemesh`.

**F — seam edges inside selections (Disc. Q5).** Selection = a seam edge of a +X quad and the opposite edge,
expanded with partners ("explicit wins"; the seam edge's partner is itself, so it is counted once: 3 edges).

| Case | state | seam live/declared | faces w/o partner | sides |
|---|---|---|---|---|
| Edge Connect expanded, raw | partial / partial | 7/8 / 35/36 | 4 / 4 | **1** / 1 |
| … + probe rule "split seam edge → its two halves" | **valid** / valid | 9/9 / 37/37 | 0 / 0 | 2 / 2 |
| Split seam edge + same rule | valid / valid | 9/9 / 37/37 | 0 / 0 | 2 / 2 |
| Delete seam edge (removes both adjacent faces) | valid / valid | 7/8 / 35/36 | 0 / 0 | 2 / 2 |
| Delete {seam, opp} expanded | valid / valid | 7/8 / 35/36 | 0 / 0 | 2 / 2 |
| Delete seam-touching face **pair** (no seam edge selected) | valid / valid | 7/8 / 35/36 | 0 / 0 | 2 / 2 |
| Dissolve {seam, opp} expanded (plane-spanning face) | valid / valid | 7/8 / 35/36 | **0**† / 0† | **1** / 1 |

† The merged face is its own vertex image, so the face-level check counts it as paired.

With a probe rule "drop dead seam ids", every Delete row and the Dissolve row keep their `state`/`sides`
(declared = live afterwards). The plane-spanning face after Dissolve is its own vertex image, so the face-level
check counts it as paired; only `sides` sees it. In the face-pair row the seam edge dies although no seam element
was selected (DD-1 removes the face-less edge).

**G — exactness on planes other than x=0 (Disc. Q7 scope gap).** The asset is rotated about Z and moved along the
rotated X; the plane is carried along. "Rebuild" = every −side vertex set to `mirror_position` of its +side
partner, every seam vertex projected onto the plane (the best a tolerance-free construction can do).

| Plane | after rebuild: state, unpaired, one-way pairs* | Edge Connect expanded: new vertices not PAIRED | Split + partner split t=0.5 | … + snap partner := mirror(source) |
|---|---|---|---|---|
| x=0 (Lab E1) | valid, 0, 0 / valid, 0, 0 | 0/4 / 0/4 | 0/2 / 0/2 | 0/2 / 0/2 |
| x=0.3 (axis, off origin) | partial, 1, 1 / valid, 0, 0 | 2/4 / 1/4 | 1/2 / 1/2 | 0/2 / 0/2 |
| 30° oblique through origin | partial, 8, 8 / **violated**, 84, 84 | 3/4 / 3/4 | 1/2 / 1/2 | **1/2** / 1/2 (partner→source `unpaired`) |
| 30° oblique, offset 0.3 | partial, 4, 4 / violated, 104, 104 | 4/4 / 4/4 | 2/2 / 2/2 | 0/2 / 0/2 |

\* one-way pair: `p → q` is PAIRED but `q`'s own lookup does not return `p` (`mirror_position` is not an exact
involution there). On the oblique head plane 8 resp. 13 projected seam vertices are still not exactly on the plane
(`violated`).

**H — `resolve_cross_face` mirror-equivariance (Disc. Q4).** A closed interior square loop in a +X face and its
mirror in the partner face, one resolve call. On the two assets the first bridge point is not a tie and the result
is symmetric (`valid`, 0 faces w/o partner). **I** (tie): on a synthetic flat grid (x ∈ [−2, 2], square faces) where
the first bridge point is a four-way distance tie, the bridges chosen on the two sides are **not** mirror images
(both loop positions tried): `state` **valid**, unpaired 0 — but **4 faces w/o partner**.

**A2 input — today's `C` with an edge and its own mirror edge selected** (scratch check, both assets, interior and
seam-touching edge): context EDGE_CONNECT, refused with "Keine verbindbaren Kanten: ausgewählte Kanten teilen sich
keine Face." (the two edges share no face).

**Baseline (this container, unchanged by this AD):** `pytest tests --ignore=tests/test_extrude_tool.py` →
1665 passed, 8 skipped. `pytest experiments/symmetry_lab/tests` → 311 passed, 4 skipped, 1 failed (`pyglet` not
installed; same failure as Disc.). `tests/test_extrude_tool.py` is excluded because it imports
`mirai_bastel_core` from a path computed for an old location (`<repo>/../mirai_bastel_core_V1`) and
`viewport.extrude_tool`, which no longer exists anywhere in the repo — a stale test, not a regression.

### 1.4 Review probe results (CLAUDE-001, R1–R5; re-run by the author on `main` @ `1334d8a`, identical)

Observations only; code in the review's appendix.

- **R1 — union call vs. intent + mirrored intent in a plane-spanning face.** One seam edge dissolved (a hexagon
  spanning the plane), two of its +X edges selected, Edge Connect. (a) one call on selection ∪ partners: 4 / 3
  chords, 2 / 1 of them crossing the plane; (b) op on the selection, then op on its mirror: 2 / 2 chords, none
  crossing. Both 0 faces w/o partner (`subd_cube` / `head_basemesh`).
- **R2 — partial mesh.** `man_with_shoes_basemesh` on X: `partial`, 54 unpaired vertices, 202 of 926 faces touch
  one. Edge Connect on two opposite edges of such a quad, expanded (union 3, one edge has no partner): 2 new
  vertices, both not `PAIRED`; the partner edge is dropped by Connect's own "no other selected edge in its faces"
  rule.
- **R3 — symmetric Delete and `sides`.** Deleting a horizontal face band closed under the partner map (8 / 56
  faces): `state` valid → valid, faces w/o partner 0 → 0, **`sides` 2 → 4**.
- **R4 — negative axis normal.** `(−1,0,0)` through the origin: 0 non-exact mirrors / involution failures in
  100 000 random points.
- **R5 — report cost.** Correspondence + indexed face check + `sides`: ~2 ms (`head_basemesh`, 324 faces),
  ~5–7 ms (`man_with_shoes_basemesh`, 926 faces) per report, in a container.

Code facts the review added (checked): `src/mirai/interaction/commands.py` already declares mutating commands
`Application` does not handle yet (`SplitEdge`, `Collapse`, `LoopInsert`, `LoopSlide`, `Extrude`,
`ArticulationRestore`); `_execute_click` consults the same gate as `key_press`; Vertex Connect signals "nothing
happened" by returning `[]` and `remove_selected` by returning `None`, which `Application` turns into specific
status lines; the only code outside tests and probes that sets a `SymmetryDefinition` is the Lab, whose
`current_axis` raises on any non-E1 plane (`lab_symmetry.py:74-87`); while a Knife session runs, the Lab's
`sync_gate` skips (`lab_app.py:325-338`).

### 1.5 Verdicts this AD may rely on (as recorded, nothing more)

- E5 **KEEP-BLOCK** (Manu, 2026-10-03; AD-SYM-02 §4 note; Lab README): a tool that does not mirror is refused
  under symmetry. Recorded as a Lab verdict; Symmetry is not promoted (ROADMAP §7).
- Symmetric W/E/R incl. pivot B: **KEEP** (Manu, 2026-10-03). Re-Symmetrize: **KEEP**.
- The old mirrored Knife (WP-SYM-LAB-01 Slice 6/7) was **never** Artist-checked; its P1–P3 are headless findings
  (Lab README, "Gespiegelter Knife").
- No Artist verdict exists on any symmetric topology operation, on seam consumption, or on `C` with a two-sided
  selection.

---

## 2. Alternatives

### 2.1 Coordination model (scope item 1)

| | Alternative | Assessment |
|---|---|---|
| M-a | **Two styles, as in Disc. §5.1:** (1) *selection expansion* in `Application`'s command handlers **after** context resolution, calling the unchanged op logic; (2) *intent/path mirroring* inside the session tool (Knife) through a `params["symmetry"]`-style context given at `begin`, applied at the tool's commit | Fits AD-SYM-02 §2.4 (same semantics, two mechanics, not unified). Evidence for (1): Disc. §1.7 (a), probe F. Evidence for (2): Disc. §1.7 Knife rows; Rebase plan D2/row 29 ("mirrors the virtual path before resolution") |
| M-b | Expansion **before** `resolve_c_context` | Turns 1 edge into 2 and flips Split into Edge Connect (Disc. §5.1). **Not used because** it changes the meaning of `C`. |
| M-c | One `SymmetricX` per op (old Lab Knife pattern) | **Not used because** it copies op logic and drifts (Rebase plan D2: the Lab Knife was a pre-B7 copy and became unpromotable); INV-9. |
| M-d | A generic "mirror the result afterwards" pass (find new elements, build their mirrors) | **Not used because** it is the nachträgliche Zuordnung that INV-6 / AD-SYM-02 §2.4 rule out, and it cannot reproduce intent such as a Knife path or Connect pairing. |
| M-e | A universal cut/coordination engine shared by Split/Connect/Knife | **Not used because** AD-017 (DECIDED) rules out a universal Cut Engine; coordination stays per mode. |

Revision of M-a from the new evidence: **[probe I]** "mirror the path, resolve once" is not sufficient for the Knife
where `resolve_cross_face` breaks ties by position; style (2) needs a mirror-equivariant resolution or a check
that rejects (§4). **[F]** Style (1) needs seam maintenance as soon as a seam edge is in the selection (Edge
Connect, not only Split). **[R1, review F3]** Style (1) as "one call on selection ∪ partners" equals "intent +
mirrored intent" (INV-6) only when no face receives selected elements of both the selection and its image, and no
self-mirrored face is involved. Otherwise per-face pairing connects across the plane: symmetric, but not the
mirrored intent. With T-a both forms are available inside one transaction (two `apply_*` calls, or one); which one
the Artist means there is open (§4, A1/A2).

### 2.2 Transaction seam — both sides as exactly one Undo step (scope item 2; N3/N4, Disc. Q3)

| | Alternative | Assessment |
|---|---|---|
| T-a | **Behaviour-preserving split** of each topology function into a pure `apply_*(mesh, …) -> result` (mutation only; raises on refusal; caller restores) and the existing wrapper (snapshot → `apply_*` → restore on error → push one `MeshStateCommand`). The coordinator calls `apply_*` inside **one** transaction it owns | No `src/core` change. Edge Connect already has `_apply`. Wrappers keep their signatures and tests (Playground and `tests/` callers unchanged). Makes the commit boundary explicit and single per intent. Cost (review CLAUDE-001): Split's `apply_*` is `Mesh.split_edge` itself and Edge Connect has `_apply`, so two real refactors (`connect_vertices_per_face`, `remove_selected`) plus one return-value change (`_apply` → midpoints) |
| T-b | **History-less scene stand-in:** the coordinator passes a scene-like object whose `history` swallows pushes, calls the unchanged wrappers, then pushes one outer command | Works with zero op change; for the four selection-op wrappers the duck-typing contract ("touch nothing but `scene.mesh` and `scene.history.push`") holds today (review CLAUDE-001; the Knife is not in T-b's scope). **Not used because** it keeps two commit boundaries per intent (inner fake, outer real) — the ambiguity AGENTS §5 asks to avoid —, leaves that contract unwritten and unenforced for future ops, and T-a costs little more |
| T-c | **History-level grouping / merge** of consecutive `MeshStateCommand`s (e.g. `begin_group`/`end_group`, or merging before-of-first with after-of-last) in `HistoryStack` | Needs a `src/core` change. **Not used because** `HistoryStack` is frozen Core whose contract says "kein Merge", AD-SYM-02 §3 item 2 decided `HistoryStack` is not changed, AD-SYM-02 §2.1 forbids the counterpart as a second history entry (a group is two entries glued), and `Application`'s selection mirror stack is 1:1 with pushes and would need group awareness too. The need is solvable above Core (T-a), so the freeze rule's step 2 already fails (CORE_V1_FREEZE §7) |
| T-c′ | Composite `Command` in `src/mirai` holding several `MeshStateCommand`s, pushed once | No Core change (`Command` is a Protocol). **Not used because** the inner ops still push themselves, so it needs T-a or T-b anyway, and then a single `MeshStateCommand` (before of the first, after of the last) already does the job |
| T-d | Let the op push, then amend the pushed command's `after_state` with the coordinator's post-op work (snap, seam update) | **Not used because** `HistoryStack` exposes no top-of-stack access (only a private list of a frozen Core class) and a rejected post-check could not take the entry back without consuming the redo branch |
| T-e | Use `Application.apply_mesh_change` as the outer transaction | Its steps are exactly the needed ones, but it is the external-host entry (H3), raises while an interaction owns the keys, and records the selection mirror before a residue can be set. **Not used as is**; its steps are reused (§3, item 3) |

**Where the commit boundary lives afterwards (AGENTS §5).** Under T-a: for selection ops the boundary moves from
inside the topology function to **the caller that owns the intent** — `Application`'s command handler (one
transaction per key press). The wrappers stay as the boundary for their other callers (Playground, tests). No op
function pushes on behalf of another caller. For the Knife the boundary is unchanged (`KnifeTool._on_commit`).

**No-op signalling (slice 2).** Vertex Connect returns `[]` and `remove_selected` returns `None` for "nothing
happened", and `Application` turns these into specific status lines. The shared transaction helper's "no change →
no entry" must keep those texts; the `apply_*` results carry the information.

**Selection mirror stack.** Preserved by keeping its one invariant: one `_record_selection_history(before)` per
push, with `before` taken before the transaction and the residue set before recording (as `_connect_command`
does today).

### 2.3 Completeness signal (scope item 3; N7, Disc. Q2)

| | Alternative | Assessment |
|---|---|---|
| C-a | `symmetry_state` grows a face-level component (face w/o partner ⇒ `PARTIAL`) | Makes the visible state honest about one-sided topology (Disc. §1.7 (b), probe I). But changes the meaning of `VALID` for every current consumer (Lab HUD/markers, Re-Symmetrize, `tests/test_symmetric_*`, Lab characterisation tables) in the same step that introduces coordination, and still misses dead seam ids and plane-spanning faces (probe F: Dissolve seam edge → faces w/o partner 0, `sides` 1) |
| C-b | **Separate derived report** (no stored state): faces without partner, edges without partner, dead seam ids, self-mirrored (plane-spanning) faces; `sides` only as a display value | Covers every one-sided case seen so far: face-level check for Disc. §1.7 and probe I, dead ids and self-mirrored faces for probe F (the Dissolve case goes 0 → 1 self-mirrored face). `SymmetryState` contract untouched. `sides` is **not** a delta signal: it measures connectivity, and a symmetric face-band delete raises it 2 → 4 (R3, review F2) |
| C-c | Reuse the Lab's `topological_pairing` | **Not used as the completeness check because** it is blind to one-sided Delete (Disc. §1.7) and is a Lab experiment (Lab README: "keine Capability") |

How the coordinator uses it — **absolute vs. delta.** Partial symmetry is legitimate (INV-10). A check "result must
be VALID" would refuse every op on a partial mesh (e.g. `man_with_shoes_basemesh`, 54 unpaired from OBJ rounding,
Lab README E4). A **delta** check is computed **by element id** (Split and Connect replace faces, so counts cannot
be compared): (1) no surviving element that was complete before is incomplete after; (2) no new self-mirrored face
and no new dead seam id (seam cases, pending A1); (3) created elements are judged by one of two rules (review F1):

| | Rule for created elements | Assessment |
|---|---|---|
| D-strict | every created element is paired | Safe and simple. Refuses every coordinated op in an unpaired region: on `man_with_shoes_basemesh` 202 of 926 faces touch an unpaired vertex, and an expanded Edge Connect there creates 2 unpaired vertices (R2). Way out: symmetry off (Shift+S), as for transforms today |
| D-source | created elements whose sources are all paired must be paired; others are allowed and reported visibly ("n elements without a partner — one-sided") | Follows INV-10/INV-13 for edits *in* the asymmetric region, still INV-5 ("recognisably not at all"). Needs provenance per op (N5 for Connect/Split; nothing for Delete) |

Which rule the Artist gets is Product Truth (Artist test A3; answered: D-strict, "for now", §6). INV-10 alone does not decide it: it covers asymmetry
elsewhere in the mesh, not edits inside it.

### 2.4 Exactness (scope item 4; N5, Disc. Q7)

**Correction to Disc. §1.7 / §4 (scope):** the Discovery probed plane x=0 only. "t=0.5 midpoints are exact" (Edge
Connect class B, Knife t=0.5) holds for planes with a ±unit axis normal and `plane_point[axis] == 0` — Lab E1, and the negative normals too (R4) —
because mirroring is then exact negation and `a*0.5 + b*0.5` is orientation-independent (§1.2). On an off-origin
axis plane and on oblique planes it fails (probe G: 1–4 of 4 Edge Connect midpoints not paired), and more
fundamentally `mirror_position` is not an exact involution there: even a mesh rebuilt from one side has one-way
pairs and, oblique, seam vertices that cannot be placed exactly on the plane (G "after rebuild").

| | Alternative | Assessment |
|---|---|---|
| X-a | **Post-op snap:** every coordinated mirror vertex is set to `mirror_position(source)` in the same transaction | One mechanism for all planes and all `t`. On E1 planes: a no-op for `t=0.5`, the fix for `t≠0.5` (P3′, probe G row x=0). On other planes necessary but **not sufficient** (G: oblique snap still leaves partner→source unpaired) |
| X-b | Mirrored parameter (`1−t`) | **Not used because** P3 (Disc. §1.3) and §1.2: orientation-dependent rounding |
| X-c | A tolerance in the correspondence | **Not used here because** AR-1 / Design Brief §7 keep tolerances out of V1 truth and `mirai/symmetry.py` avoids one by design; it is a correspondence decision, not a topology-coordination one |
| X-d | Canonical exact mirror coordinates for general planes (store/derive one side, compute the other) | Out of scope: that is the "derived half" mode, a V1 non-goal (AD-SYM-01 §4) |

### 2.5 Support declaration for non-`Operation` ops (scope item 5; N8)

| | Alternative | Assessment |
|---|---|---|
| D-a | A boolean attribute on each topology module/function (`supports_symmetry = True`) | Mirrors `Operation.supports_symmetry`, but in this model the op is **not** what mirrors — the coordination around it is. The flag could be true while no coordinator exists, or the reverse |
| D-b | **Declaration = "a coordinator exists for this resolved operation"**: one mapping, in the module that holds the coordinators, keyed by resolved operation (C context, removal mode, later Extrude); the entry *is* the implementation. Transforms keep `Operation.supports_symmetry` (there the Operation does mirror) | Each declaration sits at the code that implements the support (the same principle as AD-SYM-02 §2.3) and cannot drift from it. **Proposed** |
| D-c | Keep the Lab's hand-written table and add rows | **Not used because** it is the failure Disc. §3 N8 records (Delete/Dissolve silently missing) |

Two further facts shape the gate side:

- **`C` is one command with four meanings.** Support is per resolved context (Edge Connect may be supported
  while Knife is not). A refusal keyed by command identity cannot express that; it is a "refusal that depends on
  part of the selection" (AD-013 H2 Limits of G). Options:
  - G-1 refuse `C` until all four contexts are supported — **not used because** it blocks the stated intent
    (support Connect before Knife);
  - G-2 a data-only extension of `CommandGate` (e.g. `refused_contexts: Mapping[CContext, str]`; `CContext` is
    a public enum), checked by `Application` in `_connect_command` right after its own `resolve_c_context` —
    small `src` change, still no callback; one resolution, and the gate table stays a static, printable function
    of Lab state (H2-R2/R3);
  - G-3 `Application` itself refuses unsupported contexts whenever a definition is set — **not used because** it
    writes the Lab verdict KEEP-BLOCK into Production behaviour without a promotion (M3; AD-SYM-02 §4 note: "dieses
    Dokument entscheidet dadurch nichts für Production") and removes the Lab's MARK comparison;
  - G-4 the Lab resolves the context itself (pure `resolve_c_context` on `app.selection`, read-only per H2-R4)
    immediately before forwarding `C` and installs the matching row — no `src` change. **Not used because**
    (review CLAUDE-001) it resolves the context twice and is correct only by event timing; it turns a gate row
    from a function of Lab state into one installed per key press (H2-R2/R3); and a row installed for a `C` that
    starts a Knife session stays installed for the session, because `sync_gate` skips while the Knife owns the
    keys. Both G-2 and G-4 lift the same Limit of G, so G-4's one advantage (no `src` gate change) saves little
    where slice 3 changes `_connect_command` anyway.
- **Fail-open vs. fail-closed.** Today's BLOCK row is a block-list (fail-open: a new command runs one-sided until
  someone adds it). The preview row is already an allow-list for exactly this reason (H2 F7). A BLOCK row of the
  form "allowed = non-operation commands (display, selection, mode, undo/redo, cancel, constraints) ∪ operations
  with a declaration" fails closed: an omission is refused visibly, never silently one-sided (INV-8). This
  matters now: `commands.py` already declares `SplitEdge`, `Collapse`, `LoopInsert`, `LoopSlide`, `Extrude`,
  `ArticulationRestore`, which a block-list would let run one-sided once they are wired (§1.4). The allow-list
  must name the click commands `Select`, `SelectAdd`, `SelectRemove`, `SelectToggle` and `ClearSelection`
  (`_execute_click` consults the same gate), or BLOCK makes selecting impossible. The non-operation set is itself a
  hand list, but an omission there fails visibly, which is the property that matters.
- **Runtime refusals are not G-3.** A coordinator that refuses a seam case or a non-exact plane also acts in
  `Application` whenever a definition is set, in MARK as in BLOCK. The difference to G-3: such a refusal is part of
  the contract of a *supported* operation ("mirrors correctly or recognisably not at all", INV-5), while G-3 would
  apply KEEP-BLOCK, the policy for *unsupported* operations, in Production. Consequence: after slice 3, MARK runs
  declared operations **coordinated** (including their refusals) and only undeclared ones one-sided — the same as
  transforms today, which mirror whenever a definition is set. The Lab's MARK warning line (`e5_warning_text`;
  today Knife session and undeclared transforms) must be derived from the same declarations.

### 2.6 Seam maintenance (scope item 6; N6)

**Unambiguous, mechanical:** a seam edge that a coordinated op **splits** is replaced by its two halves in the same
transaction (old Lab Knife P1; probe F: Edge Connect with a seam edge and Split of a seam edge both `valid`, 2
sides, only with this rule). Under T-a the new definition is written inside the transaction, so Undo restores it
through `MeshStateCommand` (the case AD-SYM-01 §1.1 measured). A seam edge's partner is itself, so expansion must
deduplicate (probe F: counted once) — the edge is split once.

**Seam rule S2 (added 2026-10-08 with the Artist's A1 Case 2 refinement, §6; engineering reading of that statement,
mechanical like S1):** if a Dissolve with cleanup removes a seam vertex of valence 2, the two seam edges that met
there are replaced in the definition by the one edge the cleanup created between their outer endpoints, inside the
same transaction (a run of such vertices becomes one edge; `symmetry_coordination.seam_after_cleanup_merge`). It is
derived from ids and incidence before/after, no tolerance; when the merge cannot be derived unambiguously (a dead
seam edge that is not part of such a run, no op-created replacement edge) the definition stays unchanged, the dead
ids remain and the op is refused as before (`TEXT_SEAM_DISSOLVE`). Any new self-mirrored face is refused regardless.

**Not unambiguous (Disc. Q1, class D) — options listed, not decided:**

| Case | Observation | Options |
|---|---|---|
| Delete a seam edge / seam vertex | seam id dead; `state` valid (F, Disc.); `sides` 2 (F, seam edge) | R refuse · D drop the dead ids (declaration follows the mesh; `state`/`sides` unchanged in every probed case) · V keep the dead ids and show the seam as broken. **Delete of a seam edge in Edge mode: allowed (D/M), Artist 2026-10-08** ("one deliberately makes a hole in the mesh"); a seam vertex stays an engineering assumption |
| Delete a symmetric face **pair** at the seam (no seam element selected) | the seam edge between them dies by DD-1 (F) | as above — notable because the user never selected the seam |
| Dissolve a seam edge (+ partners) | plane-spanning face, `sides` 1, face check blind (F, Disc.) | R refuse · V allow, visibly invalid (no seam between the halves any more) · an Artist-declared new seam (Re-declare). **Decided 2026-10-08 (Artist, A1 Case 2 refined): R** — a face without a seam would remain |
| Dissolve an edge **crossing** the seam (one end on it; with cleanup the seam vertex ends with valence 2 and the cleanup merges its two seam edges) | the two seam ids die, no self-mirrored face appears (probe 2026-10-08, `head_basemesh` X: 72/72 refused by the dead-id check, `cleanup=False` no violation) | **Decided 2026-10-08 (Artist, A1 Case 2 refined): allowed**, "two seam edges become one"; implemented as seam rule S2 (above) |
| Extrude touching the seam (Playground only) | old seam edge dies, cap edge undeclared (Disc. §1.6) | R refuse · M move the seam to the cap edge (Wings pattern, R2 §3.2) · V visibly invalid |
| Knife path along / across the seam | old Lab Knife refused seam-to-seam chords (Lab README) | R refuse (old Lab) · a defined self-mirror cut (Design Brief §5 "Connect … genau einmal") |

These are Product Truth questions (what should the Artist get), prepared as Artist test **A1** (§6); the decided
rows are marked with their date.

Note for any rule that leaves on-plane geometry without a declared seam edge (review F8): a vertex on the plane
that is not an endpoint of a live seam edge is `UNPAIRED`, not its own partner (`vertex_correspondence` excludes
the vertex itself), so edge-partner resolution fails for edges through it — e.g. the boundary of a plane-spanning
face after A1 case 2.

---

## 3. Proposed decision

1. **Coordination, not copies.** Symmetry coordinates the unchanged topology logic in two styles (M-a):
   *selection expansion* in `Application`'s command handlers after context resolution (Split, Edge Connect, Vertex
   Connect, Delete/Dissolve, later Extrude), and *intent/path mirroring* in session tools (Knife) through a
   symmetry context given at `begin` and applied at the tool's existing commit. No `SymmetricX`.
2. **Shared services above Core**, a new module beside `src/mirai/symmetry.py` (name is a working name), derived and
   without stored state (INV-3, AR-1), depending only on `core` and `mirai.symmetry`, so both `Application` and
   `mirai.topology` (Knife) may import it:
   - edge and face partner resolution (edge = edge between the endpoint partners; face = face whose vertex set is
     the image; an index instead of the probe's scan);
   - selection expansion per mode, seam self-partners counted once;
   - an exact-plane predicate (±unit axis normal, `plane_point[axis] == 0`);
   - seam rule S1 (split → halves) as a pure function returning a new `SymmetryDefinition`;
   - the completeness report (C-b) and its delta check by element id;
   - later, with the Knife (slice 6): the mirrored-position snap and the source/mirror roles where "explicit
     selection wins" matters (for a union expansion it has no effect, review F6).
   The per-operation coordinators (thin: expand → `apply_*` → seam rule → delta check) and the declaration
   mapping (D-b) live together in one place above `mirai.topology`; the Knife's coordination runs inside
   `KnifeTool._on_commit` and has its entry in the same mapping. Exact module layout is implementation.
3. **Transaction seam: T-a.** The topology functions are split, behaviour-preserving, into `apply_*` + the existing
   wrapper (two real refactors plus Edge Connect's return value). The commit boundary for a key press moves to
   `Application`'s handler, through one private transaction helper that shares its steps with `apply_mesh_change`
   (snapshot, restore on raise, no change → no entry while keeping the ops' no-op status texts, one
   `MeshStateCommand`, mirror entry after the residue, pick cache, viewport, hover). Knife: boundary unchanged.
   `src/core` is not changed; T-b, T-c, T-c′, T-d are not used (reasons in §2.2).
4. **Created-element report (N5), smallest form:** `apply_*` returns what it created tied to its source where a
   coordinator uses it — Split: `(new_vertex, half_a, half_b)` (exists); Edge Connect: source edge → midpoint
   vertex (today dropped in `_apply`); Knife: pid → created vertex (slice 6). Used by seam rule S1 when a seam edge
   is in a Connect selection (probe F; the probe shows it can also be found by adjacency, so this is the cheaper,
   less fragile route, not a strict need) and by D-source if A3 chooses it.
5. **Completeness: C-b.** A separate derived report; coordinators run its delta check (§2.3: by element id; no
   complete element becomes incomplete; no new self-mirrored face or dead seam id pending A1; created elements by
   D-strict, **Artist-confirmed by A3 = S, "for now"**) inside the transaction and roll back with a visible status on failure
   (the `SeamConstraintError` precedent: refused, no history, mesh unchanged). `sides` is display only.
   `SymmetryState` is not changed by this AD.
6. **Exactness:** symmetric topology coordination is claimed exact only on exact planes (predicate in item 2; Lab
   E1). On any other plane a coordinator refuses visibly instead of producing a result the tolerance-free
   correspondence may not confirm (INV-5). On exact planes, every position created in slices 3–5 is exact without
   help (`t = 0.5`, or no new positions); the snap to `mirror_position(source)` (X-a) is the mechanism for
   arbitrary `t` and is built with the Knife (slice 6).
7. **Declaration: D-b,** fail-closed. Undeclared operation ⇒ unsupported ⇒ refused under BLOCK (KEEP-BLOCK
   semantics unchanged). The Lab's BLOCK row becomes derived: allowed = non-operation commands (incl. the click
   commands and `ClearSelection`) ∪ operations whose coordinator exists (plus transforms with
   `Operation.supports_symmetry`). For `C` the refusal is keyed by the **resolved context** through **G-2**
   (data-only `CommandGate` field checked in `_connect_command` after `resolve_c_context`). G-2 lifts one AD-013
   H2 Limit of G and therefore needs a dated H2 amendment and its review (H2-R6) before code. Selection-dependent
   limits inside a supported operation (seam cases pending A1, the both-sides face case of item 9, non-exact
   plane, D-strict) are **runtime refusals** of the coordinator, not gate rows; they apply in MARK as in BLOCK
   (§2.5, "Runtime refusals are not G-3"), and the Lab's MARK warning is derived from the same declarations.
8. **Seam rule S1 (split → halves) is adopted** for every coordinated op that splits a seam edge. All seam-consuming
   cases (§2.6 table) are detected after the op (dead seam id, new self-mirrored face) and refused until A1.
   *(Update 2026-10-08, A1 Case 2 refined: seam rule S2 handles the cleanup merge of two seam edges, §2.6; what is
   still detected and refused is an edge directly on the seam and a face pair across it.)*
9. **Both sides in one face (review F3):** until A1/A2 decide, a coordinator refuses visibly when a face would
   receive selected elements of both the selection and its image, or a self-mirrored face is involved. On exact
   planes with an intact seam this arises only after seam consumption (itself refused, item 8) or on assets that
   already have plane-spanning faces. *(Implementation note 3b, §7: the slice-1 function did not match this remark for seam elements in the selection and was adjusted.)*

---

## 4. Deliberately NOT decided

- **Seam consumption** (Delete/Dissolve/Extrude/Knife on or across the seam; the face-pair delete): Artist test A1,
  answered 2026-10-08 (§6). Still open: the Dissolve of seam *vertices* in Vertex mode (refused, not in scope of the
  Case 2 refinement), Extrude and Knife (slices 6/7); a warning about the consequences of removing seam elements was
  floated by the Artist as a possible later idea, **not decided** (§6).
- **Seam definition (open since A1 Case 2 = UNKNOWN; Case 2 was refined 2026-10-08, §6, the question below stays):** should the seam be defined over plane vertices instead of
  seam edges? To be decided when a second mirror method is planned; it would touch AD-SYM-01 and needs review.
- **`C` with a two-sided explicit selection** — *answered 2026-10-08: A2 = A* (count mirror pairs once;
  coordinators canonicalise to one side before `resolve_c_context`; §6). Not covered: scaling whole horizontal
  loops with both sides selected is a transform case, not decided here.
- **Union call vs. intent + mirrored intent where both sides meet in one face** (R1, review F3): stays refused
  as an engineering interim rule (item 9; assumption, not confirmed by Manu). A2 = A canonicalises the selection
  to one side, which removes the case for `C`; it does not decide the transform case.
- **D-strict vs. D-source for created elements** (review F1): *answered 2026-10-08: A3 = S, "for now",
  revisable* (§6). D-strict is Artist-confirmed behaviour; D-source stays recorded as an alternative.
- **Whether `SymmetryState` later folds in the face-level component** (C-a). The evidence (Disc. §1.7 (b), probe I)
  says the visible state is currently blind to one-sided topology; whether the Lab HUD shows the report next to the
  state is UX.
- **Knife tie-break equivariance:** mirror-aware tie-breaking in `knife_resolve` (a Knife-owned change, AD-017)
  vs. resolving the source and constructing its mirror vs. rejecting through the delta check. Decided in the Knife
  slice, after a wider probe than probe I (only `select_bridge` was exercised; note that `select_bridge` rounds
  distances to `_TIE_DIGITS`, which turns near-ties into ties).
- **Residue under symmetry:** *answered for Edge Connect 2026-10-08* (§6, "3b practical check": ITERATE; created
  edges on the side(s) of the live selection, implemented as the engineering rule recorded there). Vertex Connect
  keeps the live selection (AD-017). **Split stays open** until slice 4 (e.g. only the source vertex or both new
  vertices selected; the AD-017 residue table is one-sided).
- **General (non-exact) planes:** whether they ever get exact coordination (needs a correspondence decision: X-c or
  X-d). No host produces them today; a loaded `export_state` is the only route (the plane is serialised).
  **Asymmetry, out of scope here:** transforms are not refused on non-exact planes, topology coordinators would be.
- **Extrude:** Production port before or after its symmetry work (Disc. Q6, owner priority); `Operation` vs.
  atomic mutation stays open (AD-SYM-02 §4).
- **Owner check O1 — end of the accepted interim, reduced (review F4). Accepted 2026-10-08 as a consequence of
  the A1/A2/A3 verdicts; assumption, no separate explicit O1 confirmation was given by Manu.** *Answered by slice 3c
  (2026-10-08):* non-seam Delete/Dissolve is coordinated (supported, not refused), and the seam cases left "runs
  one-sided": **Delete** is coordinated (the seam follows the mesh, A1 Case 1 = M, extended to a deleted seam edge
  or vertex as an engineering assumption), **Dissolve** (all variants) is refused visibly (Case 2, interim rule R),
  in MARK as in BLOCK. `INTERIM_ONE_SIDED` is gone; nothing runs silently one-sided any more. Manu confirms the
  Dissolve refusal in the practical test (question (b)); until then it stands as the dated, visible interim.
  *Update 2026-10-08 (later, §6):* the Artist refined Case 2 — Dissolve of an edge directly on the seam stays
  refused, Dissolve of an edge crossing the seam is allowed (seam rule S2); Delete of a seam edge stays allowed.
- *Engineering assessment 2026-10-08, not a decision.* Conditions other mirror methods will likely need from the
  seam:
  - modifier-style (model one half, derive the other): a continuous seam line without gaps, all seam vertices
    exactly on the plane;
  - one-shot symmetrize: an unambiguous seam saying where to cut and weld;
  - data mirror (weights, morphs, later rig): seam vertices are their own partner, every other vertex has exactly
    one partner;
  - common to all: an exact plane (Lab planes today: axis planes through the origin).

  Transform symmetry already relies on the seam to keep centre vertices on the plane.
- Module and function names, the report's data shape, the index structure, any key binding, HUD text or overlay.

---

## 5. Coupling with AD-SYM-01 / AD-SYM-02 (and AD-013 H2, AD-017) — checked

| Decision | Coupling | Result |
|---|---|---|
| AD-SYM-01 (definition in the mesh, part of `export_state`) | Seam rule S1 writes a new `SymmetryDefinition` inside the transaction | Undo/Redo carry it through `MeshStateCommand` with no new machinery — the case §1.1 there measured. The mesh still knows no semantics: the rule lives above Core. **No change** |
| AD-SYM-02 §2.1 (one instance, one entry) | Topology analogue: one transaction, one `MeshStateCommand` per intent (T-a) | Upheld; T-c rejected for contradicting it |
| AD-SYM-02 §2.2 (`params` channel) | Knife gets its symmetry context through `begin(**params)` | Same channel idea; `OperationContext` unchanged |
| AD-SYM-02 §2.3 (support statement before `begin`) | Extended to non-`Operation` ops as D-b | Upheld; the form question of §4 there is narrowed: static declaration per resolved operation + runtime refusal for selection-dependent limits |
| AD-SYM-02 §2.4 (two mechanics) | M-a confirms selection expansion vs. intent mirroring | Upheld, with the limit of item 9 for style (1) |
| AD-SYM-02 §4 (seam update vs. degrade) | S1 decides the split case; consumption stays open (A1) | Partly answered, rest open |
| AD-013 H2 (gate by command identity; Limits of G) | Context-keyed refusal for `C` (G-2) and a fail-closed BLOCK row | **Needs a dated H2 amendment + review (H2-R6) before code.** The table stays static per Lab state |
| AD-017 (no universal Cut Engine; Knife session model) | Coordinators are per mode; Knife keeps its virtual path and commit-time resolver | Upheld. A tie-break change, if chosen, is Knife-owned |
| CORE_V1_FREEZE §7 | No option chosen needs `src/core` | Upheld (T-c recorded as rejected) |
| `WP_DELETE_DISSOLVE_PLAN.md` DD-2 | Non-seam mechanics answered (slice 3); seam consumption → A1; gate consequence → O1 | DD-2 closes except for A1 with slice 3 |

**Order:** this AD needs AD-SYM-01/02 as they are; the H2 amendment and the A1 observation (§6) are
preconditions of slice 3.

*Pointer 2026-10-08:* H2 amendment (G-2), see [AD-013, Addendum 2026-10-08](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-08-ad-sym-03-slice-3--h2-amendment-g-2-context-keyed-refusal-for-c-fail-closed-block-row): **DECIDED** (Manu, 2026-10-08), after independent review CLAUDE-001 (ACCEPT WITH CHANGES, no blockers, findings answered). It also fixes the A2 canonicalisation rule for slice 3: canonicalise always when a definition is set, for declared and undeclared contexts (in MARK a mirror edge pair runs as a one-sided Split until slice 4).

---

## 6. Artist tests (prepared, not answered)

All run in the Symmetry Lab: `python experiments/symmetry_lab/run.py <asset>`, then **Shift+S** → `X`.
Answer options as given; `UNKNOWN` is valid.

### A1 — Seam consumption (≤ 5 min) — partly runnable today, **run before slice 3**

*Runnable today* (`head_basemesh`) because Delete/Dissolve are not in the BLOCK row (accepted interim); what is
shown is today's one-sided Core behaviour, not a coordinated operation. **Timing (review F4):** once slice 3 lands,
these seam cases are refused in MARK and BLOCK, and the observation below is no longer reachable in the Lab. A1
should be run (or at least its observations recorded) before slice 3.

1. **3** (Face mode). Click a face that touches a green seam edge, Shift+click the face on the other side of that
   same seam edge. **Entf** (Delete).
   *Expected observation:* both faces are gone, the seam edge between them is gone too (the open hole runs across
   the middle); HUD stays `valid`, no marker changes. **Ctrl+Z.**
2. **2** (Edge mode). Click one green seam edge. **Rücktaste** (Dissolve).
   *Expected observation:* the two faces at that edge become one face spanning the plane; HUD stays `valid`.
   **Ctrl+Z.**
3. (not runnable: Extrude touching the seam — Playground only.)

Question per case (1, 2; 3 by description): what should happen when an operation removes or consumes seam elements?
- **R** refuse (status line, nothing changes);
- **M** maintain: the seam follows the mesh (removed seam ids dropped; for Extrude the cap edge becomes the seam);
- **V** allow, but show the seam as broken (state not `valid`, marker on the gap);
- **UNKNOWN**.

**Verdicts (recorded 2026-10-08).**

*Artist statements (Manu, 2026-10-08):*
- Case 1 (delete a face pair at the seam): **M**. Reason given: the seam disappears only where the adjacent faces
  are gone as well.
- Case 2 (dissolve a seam edge, the merged face stays): **UNKNOWN**. Unsure whether a seam is needed there; it
  depends on the mirror capability.
- Case 3 (Extrude at the seam): **M** (the seam follows the mesh, the cap edge becomes the new seam). Judged by
  description; not runnable in the Lab (Playground-only Extrude).
- Stated view: a live symmetry that only does transforms can do without the seam edge; other mirror methods will
  very likely need a continuous seam line later.

*Engineering, set by planning 2026-10-08 (not an Artist verdict):*
- Interim rule for Case 2: refused visibly (option R: status line, no history entry, mesh unchanged) until the
  Artist decides. Rests on §2.6 (a plane vertex without a live seam edge is `UNPAIRED`) and §3 item 8. Cheapest and
  reversible.
- Assumption, not confirmed by Manu: seam-edge-selected Delete (a seam edge itself selected) is not covered by
  Case 1 and stays refused per §3 item 8.

*Implemented 2026-10-08 (slice 3c).* Case 1 (**M**): Delete drops the seam edge ids that no longer exist from the
definition inside the same transaction (`seam_without_dead_ids`); the state stays `valid`, Undo restores the old
seam. This holds for Delete in every component mode, so a seam edge or a seam vertex that is deleted itself is
maintained the same way (engineering extension, assumption beyond Case 1, not confirmed by Manu); the delta check
stays the guard and refuses if a surviving vertex would lose its seam. Case 2 (**R**, interim rule): any Dissolve
variant that would create a face spanning the plane or consume a seam edge is refused with its own text
(`TEXT_SEAM_DISSOLVE`); mesh, history and selection unchanged. Case 3 (Extrude at the seam): **M** is the Artist
verdict, Extrude is not in Production and not touched.

A2 and A3 were answered the same day (below).

**Verdicts, second round (recorded 2026-10-08; after the 3c practical check).** The interim bullets above stay as
the dated state they describe; where they differ, this block supersedes them.

*Artist statements (Manu, 2026-10-08):*
- Face Dissolve residue (the merged faces are selected on the side(s) of the live selection): **KEEP.**
- Case 2 refined: Dissolve of an edge **directly on the seam** (both endpoints on it) is **refused**, because a face
  without a seam would remain. Dissolve of an edge **crossing the seam** (one endpoint on it) is **allowed**: the seam
  does not disappear, two seam edges become one, comparable to removing a loop that runs across the seam.
- Delete of a seam edge stays **allowed** ("one deliberately makes a hole in the mesh"); Case 1 (face pair at the
  seam) stays **M**.
- Possible later idea, **not decided**: a warning about the consequences of removing seam elements.

*Engineering, set by the handoff 2026-10-08 (not an Artist decision):*
- Seam rule **S2** (§2.6, mechanical like S1; the reading of the Artist's statement): if Dissolve with cleanup removes
  a seam vertex of valence 2, the two dead seam edges are replaced in the definition by the one edge between their
  outer endpoints, inside the same transaction. Any other dead seam id, and any new self-mirrored face, keeps the
  refusal with `TEXT_SEAM_DISSOLVE`.
- A selection that contains crossing edges on both sides (a loop through the seam) is covered by the same rule.

*Implemented 2026-10-08 (S2).* `seam_after_cleanup_merge` in `symmetry_coordination.py`, called in the Dissolve
branch of `coordinate_removal` before the seam-violation check; Dissolve without cleanup (Ctrl+Rücktaste) never
kills a seam id by merging, so its behaviour is unchanged. Details and measurements: §7, "Implementation note S2".
Question to Manu (practical test, `docs/ATELIER.md` B2b): is the vanishing of the green seam point when a crossing
edge is dissolved acceptable — KEEP / ITERATE / UNKNOWN?

### A2 — `C` with a two-sided explicit selection (≤ 5 min) — observation runnable today, comparison after slice 4

1. (`head_basemesh`) **Shift+B** → `E5-Modus: MARK` (under BLOCK `C` is refused). **2** (Edge mode). Click an edge
   on +X, Shift+click its mirror edge on −X (turquoise markers show partners only in Vertex mode; pick by eye). **C**.
   *Expected observation:* status `Keine verbindbaren Kanten: ausgewählte Kanten teilen sich keine Face.`, nothing
   changes (context Edge Connect, the two edges share no face).
2. Vertex analogue: **1**, a vertex and its turquoise partner, **C** → today Vertex Connect, nothing connectable.

Question: with both sides selected and symmetry on, what did you mean?
- **A** count mirror pairs once ("1 edge" → symmetric Split; "1 vertex pair" → no C meaning);
- **B** count literally (2 edges → Edge Connect; it connects only where the two edges share a face, e.g. a face
  spanning the plane — and there it connects across the plane, R1);
- **C** refuse with a hint ("beide Seiten gewählt — eine Seite wählen");
- **UNKNOWN**.

*Not yet runnable:* the A/B comparison as behaviour (needs symmetric Split, slice 4, and a Lab switch between A and
B). Moot after the verdict below; the coordinator still refuses the both-sides face case (item 9).

**Verdict (Manu, 2026-10-08): A.** Count mirror pairs once; one edge plus its mirror edge is one intent, so `C`
splits both. Stated "from gut feeling". Reason: in symmetric editing one usually selects only one side,
especially when cutting into the mesh.
- *Not covered by A2:* Manu noted that scaling whole horizontal loops may involve both sides selected. That is a
  transform case; it is not decided here.
- *Consequence:* coordinators canonicalise the selection to one side **before** `resolve_c_context`. This
  supersedes the interim "expand after the unchanged `resolve_c_context`" wording for the both-sides case.
- *Engineering, not confirmed by Manu:* item 9 (both sides in one face) stays refused as an interim rule.

### A3 — Editing next to unpaired geometry (≤ 5 min) — observation runnable today, comparison after slice 3

1. `run.py man_with_shoes_basemesh`, **Shift+S** → `X`: HUD `partial`, 54 magenta (unpaired) vertices.
   **Shift+B** → MARK. **2** (Edge mode). Pick a quad that touches a magenta vertex; click two opposite edges of it
   (Shift+click). **C**.
   *Expected observation (today, one-sided):* the quad is cut on this side only; the new vertices have no partner
   (more magenta). **Ctrl+Z.**
2. Same on a quad far from any magenta vertex, for comparison (today also one-sided; after slice 3 symmetric).

Question: with symmetry on, what should happen when you edit right next to geometry that has no partner?
- **S** refuse (status line: one side cannot be mirrored here; turn symmetry off to work one-sided);
- **P** do what can be mirrored, leave the rest one-sided and say so ("n elements without a partner");
- **UNKNOWN**.

*Not yet runnable:* S vs. P as behaviour (needs slice 3; S is the rule there, P would need a switch and the
source report).

**Verdict (Manu, 2026-10-08): S, "for now"** (revisable). Refuse with a status line next to unpaired geometry; the
user may turn symmetry off to work one-sided. Reason: P (mirror what can be mirrored, rest one-sided) would likely
become very imprecise.
- *Consequence:* D-strict (§2.3, §3 item 5) is now Artist-confirmed behaviour, not only an interim rule.
  D-source stays recorded as an alternative should the verdict be revisited.

### 3b practical check (Manu, 2026-10-08)

*Artist statements (Manu, 2026-10-08), Symmetry Lab, `head_basemesh` / `man_with_shoes_basemesh`:* all steps of the
slice 3b practical check were "as expected" on his machine:
- Edge Connect and Vertex Connect run symmetric, one Undo step;
- a seam edge in a Connect selection works;
- refusal next to unpaired geometry, symmetric result far from it (`man_with_shoes_basemesh`);
- Split and Knife contexts are refused under BLOCK with their texts;
- Delete/Dissolve still run one-sided (accepted interim, ended by slice 3c).

*Verdict, selection after a symmetric Edge Connect:* **ITERATE.** Wanted: the created edges on the side he worked
on; if he deliberately selected both sides beforehand (his example: two edges on the left, their mirror partners on
the right), the created edges of both sides, so he can continue with both (e.g. scale in X). Reason given: after a
move the other side follows through transform symmetry anyway. The earlier default (created edges of both sides
always) is superseded.

*Engineering, set by the handoff 2026-10-08 (assumption, not confirmed by Manu):* the residue rule that implements
the verdict. Created edges are selected on the side(s) where the **live** selection (before canonicalisation) has
elements; a live selection on the plane only (seam edges) -> the normal's side (+X); a created edge that is its own
mirror (on or spanning the plane) stays selected. Side of an element = sign of its vertices' summed signed distance
to the plane (`element_side`, the rule `canonical_*` use), no tolerance. One shared helper
(`symmetric_ops.residue_sides` / `on_residue_sides`) so the same rule serves the removal residue (slice 3c).

---

## 7. Proposed slice cut for the following Type-A package

Based on Disc. §5.4; changes marked **[Δ]** with their evidence. Each slice keeps `pytest tests`,
`pytest experiments/symmetry_lab/tests` and `pytest playground/tests` green, runs the Symmetry Lab tests for
`application.py` changes (CLAUDE.md), and touches no `src/core`.

| # | Slice | Content | Evidence / note |
|---|---|---|---|
| 1 | **Services, tested, not wired** **Done 2026-10-08** (`src/mirai/symmetry_coordination.py`, `tests/test_symmetry_coordination.py`; `tests` 1665 → 1695 passed / 8 skipped, Lab suite unchanged 311 passed / 4 skipped / 1 failed (pre-existing overlay-order test, not from this slice)). | Edge/face partners (indexed), expansion (seam self once), exact-plane predicate (± normals), seam rule S1, completeness report + delta check by element id (D-strict), detection of the both-sides face case; `src/mirai/`, tests in `tests/` | Disc. §5.4 step 1. **[Δ]** + predicate (G, R4), + dead ids/self-mirrored faces in the report (F), `sides` display only (R3), + id-based delta (review F1), no snap yet (review F6) |
| 2 | **Transaction seam** — **Done 2026-10-08** (`apply_connect_edges`, `apply_connect_vertices`, `apply_removal`, `Application._mesh_transaction`; `tests` 1695 → 1710 passed / 8 skipped; Lab suite unchanged 311 / 4 / 1 failed; playground unchanged 701 passed / 11 failed / 47 errors, pyglet display errors in this container, same before and after). `apply_removal` carries no no-op flag: the transaction compares states | `apply_*` split of `connect_vertices_per_face` and `remove_selected` (Split = `Mesh.split_edge`, Edge Connect = `_apply`); Edge Connect returns edge → midpoint; `Application` handlers use one private transaction helper shared with `apply_mesh_change`, no-op status texts kept. Pure refactor, existing tests unchanged | Disc. step 2; T-a. **[Δ]** + the midpoint report (F, review F7), the shared helper (T-e), no-op texts (review) |
| 3 | **Edge + Vertex Connect through `C`, non-seam Delete/Dissolve (Lab)** — cut in two (handoff 2026-10-08): **3a Done 2026-10-08** (infrastructure: `CommandGate.refused_contexts`, the one-resolution context check with canonicalisation in `_connect_command`, `src/mirai/symmetry_declarations.py` (empty), declaration-derived fail-closed BLOCK row with the named `INTERIM_ONE_SIDED`, MARK warning from the declarations, start-up listing; `tests` 1710 → 1780 passed / 8 skipped, Lab suite 311 → 350 passed / 4 skipped / 1 failed (the same pre-existing pyglet overlay-order test), playground unchanged 701 passed / 11 failed / 47 errors; no coordinator, Lab behaviour unchanged except the MARK canonicalisation consequence and the visible refusal of unlisted commands). **3b Done 2026-10-08** (Edge Connect and Vertex Connect: `src/mirai/symmetric_ops.py` with `coordinate_edge_connect` / `coordinate_vertex_connect`, entered in `symmetry_declarations.C_CONTEXT_COORDINATORS`; `Application._connect_command` runs the coordinator of a declared context inside its one `_mesh_transaction` whenever a definition is set, in MARK as in BLOCK; refusals (non-exact plane, unpaired selection, both-sides face, D-strict delta) post their text, record no history entry and leave mesh and selection unchanged; seam rule S1 is applied inside the mutation; tests `tests/test_symmetric_ops.py`, `experiments/symmetry_lab/tests/test_app_lab_symmetric_connect.py`; `tests` 1780 → 1806 passed / 8 skipped, Lab suite 350 → 363 passed / 4 skipped / 1 failed (the same pre-existing pyglet overlay-order test), playground unchanged 701 passed / 11 failed / 47 errors with `--continue-on-collection-errors` (pyglet missing in this container, same before and after; without that flag collection stops at 8 errors); Delete/Dissolve stay one-sided, `INTERIM_ONE_SIDED` stays until **3c**). **3b practical check by Manu 2026-10-08: all steps as expected (§6); 3a/3b verified.** **3c Done 2026-10-08** (Part A of the 3c handoff: Edge Connect residue on the side(s) of the live selection, `symmetric_ops.residue_sides` / `on_residue_sides`; Part B: `coordinate_removal` and the three per-command coordinators `coordinate_delete` / `coordinate_dissolve` / `coordinate_dissolve_no_cleanup` in `src/mirai/symmetric_ops.py`, entered in `symmetry_declarations.REMOVAL_COORDINATORS`; `Application._removal_command` runs the coordinator of a declared command inside its one `_mesh_transaction` whenever a definition is set, in MARK as in BLOCK, `SymmetryRefusal` posts its text and changes nothing; Delete drops dead seam ids (M), Dissolve refuses seam cases with `TEXT_SEAM_DISSOLVE` (R); `INTERIM_ONE_SIDED` removed from the Lab; tests `tests/test_symmetric_removal.py`, `tests/test_symmetric_ops.py`, `experiments/symmetry_lab/tests/test_app_lab_symmetric_removal.py`; measured in this container after installing `pyglet` (no EGL, so `tests/test_pyglet_input.py` and the GL tests do not run): `tests` 1806 → 1818 (Part A) → 1907 passed / 33 → 39 skipped, Lab suite 365 → 367 → 418 passed / 3 → 7 skipped, playground (under `xvfb-run`) 1235 passed before and after) | Expansion after `resolve_c_context` / on the removal selection, seam edges in a Connect selection via S1, delta check with rollback, seam consumption and both-sides face case refused; G-2 context refusal; declaration-derived, fail-closed BLOCK row; MARK warning from the declarations. Exact planes only | Disc. steps 3 + 5 (non-seam part). **[Δ]** non-seam Delete/Dissolve moved here (review F4), seam edges in Connect here (F); preconditions: AD-013 H2 amendment reviewed, A1 observed; owner check O1 (seam cases only); A3 comparison becomes runnable |
| 4 | **Split** | Source + partner edge in one transaction (seam edge once + S1); residue question prepared; A2 comparison becomes runnable | Disc. step 4 |
| 5 | **Seam cases** | Seam consumption per the A1 verdict (and the both-sides face case per A1/A2); D-source if A3 chooses it; DD-2 fully closed | Disc. step 5 (seam part). A1 answered 2026-10-08 (§6): Case 1 → M and Extrude → M are now Artist-decided inputs; Case 2 stays refused (Engineering interim rule, Artist UNKNOWN) — *refined 2026-10-08 (§6): an edge directly on the seam stays refused, an edge crossing the seam is dissolved via seam rule S2 (see Implementation note S2)*. No longer fully blocked on A1 |
| 6 | **Knife** | Symmetry context at `begin`, mirror records before resolution, pid → vertex report, **snap**, S1, seam-chord rule, mirrored preview (INV-11), **tie-break equivariance** | Disc. step 6. **[Δ]** tie-break is a known defect now (probe I); the snap lives here (review F6) |
| 7 | **Extrude** | After a Production port (owner, Disc. Q6) | Disc. step 7 |

**Unblocked after the 2026-10-08 decision:** slices 1 and 2 now (no gate change, no open verdict). Slice 3 only
after the AD-013 H2 amendment (G-2) is written and reviewed — **done: DECIDED 2026-10-08** (pointer in §5); **3a, 3b and 3c implemented 2026-10-08** (3a/3b verified by Manu the same day; 3c practical test answered in part, §6 second round; S2 awaits its practical test). Slice 4 follows
slice 3. Slice 5 is no longer fully blocked on A1 (see its row); A2 = A and A3 = S are inputs to slices 3–4.

The order of operations is unchanged from the Discovery except that the non-seam part of Delete/Dissolve moves
from slice 5 to slice 3 (it is class B and was only waiting for the gate); the seam part is no longer fully blocked on A1 (see slice 5).

**Implementation note 3b (2026-10-08).** What the code made concrete or had to add; nothing here changes a decision.

- **Refusal order** in a coordinator: non-exact plane first (the partner relation is not trustworthy off an exact
  plane), then unpaired selection, then both-sides face, then, after the op, the delta (D-strict). The handoff listed
  unpaired / both-sides / plane; the order changes only which text a doubly-wrong selection shows.
- **Finding, `both_sides_faces` (slice 1) adjusted (engineering, reported for confirmation).** As written it flagged
  every face that holds a seam element of the selection together with the image of another selected element, i.e. exactly
  probe F (seam edge + opposite edge) and every seam edge that Connect would actually split. With it, seam rule S1 was
  unreachable for Edge Connect and §3 item 9's own remark ("on an intact seam this arises only after seam consumption or
  on plane-spanning assets") did not hold. A seam element is its own image, so on its own it cannot make the union call
  differ from "intent + mirrored intent" (probe F: union call + S1 is `valid`, 0 faces without partner). The function now
  leaves self-partnered elements out of the selection-versus-image comparison and still counts them for the
  self-mirrored-face test. The one slice-1 test that pinned the old result (seam vertex + the image of a second vertex in
  one quad) was changed accordingly and a case with two non-seam vertices on opposite sides keeps the conflict. Also: for
  S1 the halves of a split seam edge are found as the edges from the midpoint vertex to the old endpoints, read before
  the op.
- **Residue under symmetry (superseded 2026-10-08 by the Artist's ITERATE verdict, §6 "3b practical check"):** as
  first built, Edge Connect selected the created edges of both sides (one union call); it now selects those on the
  side(s) of the live selection. Vertex Connect leaves the live selection untouched (AD-017 residue).
- **Fuzz (headless, not a committed test):** every edge pair, three-edge run and vertex pair of every +X face of
  `subd_cube` and `head_basemesh`: 108 + 1458 successes, each report clean, each one Undo step, Undo restores the
  topology; 48 + 648 Vertex Connect no-ops without a history entry; no exception, no refusal. On
  `man_with_shoes_basemesh` (`partial`): 3258 successes that add no incomplete element, 942 unpaired-selection refusals,
  183 D-strict refusals, no exception.
- **Not covered:** two seam vertices that are non-adjacent in one face (Vertex Connect would chord the same pair from
  both sides); no asset in the Lab produces that case.

**Implementation note 3c (2026-10-08).** What the code made concrete or had to add; nothing here changes a decision.

- **One coordinator, three declarations.** `coordinate_removal(mesh, mode, ids, *, dissolve, cleanup)` runs for all
  three component modes; the declarations stay per command (G-9 not used), so no command had to stay undeclared. The
  steps are those of the handoff: exact plane, expansion with partners (a seam self-partner once; an explicit mirror
  pair counts once, so no canonicalisation is needed), unpaired refusal, both-sides faces in vertex and edge mode
  (face mode relies on the delta check), report, one `apply_removal` call on the union, seam rule, report, delta.
- **Seam rule for Delete (`seam_without_dead_ids`).** After the call, seam ids that are no longer valid edges are
  dropped (ids are never reused, AD-001, so "no longer valid" is exact and needs no tolerance). It runs for Delete
  only; for Dissolve the dead ids stay in the definition so the delta check sees them.
- **Dissolve seam text.** The delta result holds strings, so the coordinator compares the two reports directly: a new
  self-mirrored face or a new dead seam id on a Dissolve is `TEXT_SEAM_DISSOLVE`, every other violation the existing
  `TEXT_DELTA`. The delta check can tell an expected dead seam id (Delete, dropped before the report) from a
  violation without a tolerance, so the handoff's stop condition did not trigger.
- **Measured on the assets (headless).** `subd_cube` and `head_basemesh`: Delete of a far element in each mode, of a
  face pair across a seam edge, of a single face of that pair, of every seam edge and every seam vertex, ran
  coordinated with a clean report; Dissolve of a far element ran clean; Dissolve of a seam edge, of a seam vertex and of
  a face pair across the seam gave `TEXT_SEAM_DISSOLVE`. `man_with_shoes_basemesh` (`partial`), every paired `+X` edge /
  face / vertex: Delete 796 / 362 / 415 successes and 108 / 101 / 27 unpaired-selection refusals, no delta refusal;
  Dissolve (edge, vertex) 584 / 258 successes, 170 / 157 delta refusals next to unpaired geometry, 42 (edge) seam
  refusals; no exception.
- **Residue (engineering default, not confirmed by Manu).** Delete and Vertex/Edge Dissolve clear the selection, the
  mode stays (as before). Face Dissolve selects the merged faces on the side(s) of the live selection (same helper as
  the Edge Connect residue), without a definition all merged faces (unchanged).
- **Known behaviour, not a defect.** Delete of a vertex or edge near the seam may drop the ids of seam edges that died
  with a neighbouring face (the seam follows the mesh); a single `+X` face selected at the seam deletes the face pair.

**Implementation note S2 (2026-10-08, A1 Case 2 refined).** Implements an Artist verdict (§6); nothing here is new
insight.

- **Cause verified, as the handoff expected.** Every edge crossing the seam of `head_basemesh` (X, 72) and `subd_cube`
  (16) ends the Dissolve with its seam vertex at valence 2 (before: valence 4 = two seam edges, the crossing edge and
  its mirror); the cleanup removes the vertex and both seam edges, two dead seam ids, no new self-mirrored face. So the
  stop condition of the handoff did not trigger.
- **Rule.** `seam_after_cleanup_merge(definition, seam_ends_before, mesh_after, edges_before)` (pure, next to
  `seam_after_split`): the dead seam edges are grouped into runs through removed vertices; a run is merged only if
  every removed vertex had exactly two dead seam edges in it, the run has two distinct surviving ends, and exactly one
  edge between them exists that the op created. Otherwise the definition is returned unchanged (dead ids stay, the
  existing refusal fires). The coordinator reads the seam edges' endpoints before the op and writes the result inside
  the same mutation, so Undo/Redo restore mesh and definition together and a later refusal rolls it back.
- **Effect measured (headless, bare coordinator, before → after S2, one edge at a time).** Edge Dissolve with cleanup:
  `head_basemesh` crossing 72 refused → 72 run, seam edges 36 refused → 36 refused, other 540 run both times;
  `subd_cube` crossing 16 refused → 16 run, seam 8 / 8 refused, other 24 run. Vertex and Face mode Dissolve with
  cleanup (every vertex / face of both assets): outcomes identical before and after (seam vertices and face pairs
  across the seam still refused). `man_with_shoes_basemesh` (`partial`), every paired `+X` edge (796): 584 ran before
  and after, 170 delta refusals before and after, of the 42 earlier seam refusals 38 now run and 4 are refused by the
  D-strict delta check (a crossing edge next to unpaired geometry). Loops: the straight edge line through each seam
  vertex (both sides selected) ran for every seam vertex of both assets, one merge for a stretch, two for a ring that
  crosses the seam twice.
- **Tests (new).** `tests/test_symmetry_coordination.py::TestSeamRuleS2` (the pure rule incl. runs and the non-derivable
  cases); `tests/test_symmetric_removal.py`: all crossing edges of both assets with Dissolve (symmetric, one Undo step,
  state `valid`, the seam equals the geometric seam edge for edge, degrees of the surviving seam vertices unchanged,
  Undo/Redo restore mesh, definition and selection), the same without cleanup (definition unchanged), loops through the
  seam, two-sided selection counts once, every seam edge still refused (36 / 8), a seam edge plus a crossing edge
  still refused, Delete of every seam edge still allowed, rollback with the transaction, no definition unchanged;
  `experiments/symmetry_lab/tests/test_app_lab_symmetric_removal.py`: crossing-edge Dissolve in BLOCK and MARK with
  HUD `valid`.
- **Counts** (this container, `pyglet` installed, no EGL so `tests/test_pyglet_input.py` is not run): `tests` 1907 →
  1941 passed / 39 skipped; Lab suite 418 → 422 passed / 7 skipped; playground (under `xvfb-run`) 1235 passed before
  and after. `src/core`, `src/main.py`, `playground/` untouched.

---

## 8. Consequences (if decided)

- **Positive:** one commit boundary per intent, visible in one place per path; no Core change; declarations cannot
  drift from implementations; a new mutating command is refused under BLOCK until it is coordinated, never silently
  one-sided; one-sided results are detected even where `symmetry_state` is blind (Disc. §1.7 (b), probe I).
- **Costs:** two refactors and one return-value change in `src/mirai/topology/` (behaviour-preserving), a new
  services module, a small `CommandGate` extension with its AD-013 H2 amendment, and two reports per coordinated op
  (~2–7 ms each on the Lab assets, R5). Coordinated ops are refused on non-exact planes until a correspondence
  decision exists, and (interim D-strict) next to unpaired geometry until A3.
- **Risk:** the fail-closed row and the runtime refusals change what the Lab does in the seam cases, in MARK too
  (O1, §2.5). Mitigated by running A1 first and naming O1 as an owner check at slice 3.

---

## 9. Review

**Archived (2026-10-07):** [review CLAUDE-001](../archive/symmetry_lab/reviews/AD-SYM-03_REVIEW_CLAUDE_001.md)
(fresh session, `main` @ `276dbe4`, preserved verbatim). Verdict: accept the direction with changes before
DECIDED; no architectural blocker; every checked code fact in §1.2 correct. The author re-ran the review probe
R1–R5 on `main` @ `1334d8a` with identical results (R5 timings vary by run), see §1.4.

**The four questions of the first version of this section:**

| Question | Review answer | Taken over |
|---|---|---|
| T-a vs. T-b — is the duck-typing objection strong enough? | T-a, but the duck-typing part is beside the point (the Knife is out of T-b's scope; the four wrappers satisfy the contract today). T-a is carried by "two commit boundaries" and by being cheaper than stated | **Yes.** §2.2 T-a/T-b cells rewritten; cost corrected to two refactors + one return-value change; no-op signalling note added |
| G-4 vs. G-2 | G-2: one resolution, static table, no stale row during a Knife session | **Yes.** §2.5 and item 7 now take G-2; G-4 recorded as "not used because" |
| Fail-closed row (O1) | Fail-closed is right (six declared but unwired mutating commands); allow-list must name the click commands and `ClearSelection` | **Yes.** §2.5, item 7; O1 reduced via F4 |
| Exact-plane restriction too strict? | No host produces another plane; predicate should accept ±normals; list the transform asymmetry | **Yes.** Predicate ±unit axis normal (§2.4, item 2); asymmetry listed in §4 |

**Findings:**

| Finding | Severity | Answer |
|---|---|---|
| F1 — the delta rule refuses all coordinated work in unpaired regions | SHOULD | **Fixed in the text.** §2.3 defines the delta by element id and names the two rules D-strict / D-source as a product choice; D-strict is the interim rule (item 5); new Artist test A3 (§6). The earlier claim that the strict rule "follows INV-10" is withdrawn |
| F2 — `sides` gives false refusals as a delta signal | SHOULD | **Fixed.** `sides` is display only (C-b, item 5); the delta uses self-mirrored faces and dead seam ids, which cover the Dissolve case `sides` was brought in for |
| F3 — union call ≠ mirrored intent when both sides meet in one face | SHOULD | **Fixed in the text.** §2.1 states the limit of style (1); item 9 refuses that case until A1/A2; §4 lists it; A2 option B now names it. T-a makes both forms available, so the later answer needs no new mechanism |
| F4 — slice 5 not blocked on A1; O1 shrinks | SHOULD | **Adopted.** Non-seam Delete/Dissolve moves into slice 3 (§7); O1 now covers the seam cases only (§4); A1 is marked "run before slice 3" (§6) |
| F5 — MARK changes meaning for declared ops; G-3 distinction | SHOULD | **Fixed.** §2.5 "Runtime refusals are not G-3" states the distinction (contract of a supported op vs. policy for unsupported ops) and the MARK consequence; the MARK warning is derived from the declarations (item 7, slice 3). Precision: today's warning line covers the Knife session and undeclared transforms, not an immediate `C` |
| F6 — the snap is dead code until the Knife slice | NIT | **Adopted.** Snap and source/mirror roles move to slice 6 (item 2, item 6, §7) |
| F7 — N5 is a convenience for S1, not a need | NIT | **Fixed.** Item 4 says "used by", with the adjacency alternative named; the midpoint report stays in slice 2 as the cheaper route |
| F8 — smaller corrections | NIT | **Fixed.** Footnote on the Dissolve row (§1.3); R5 cost in §1.4 and §8; the on-plane non-seam vertex note in §2.6 |

**Decision note (2026-10-08).** Manu decided this AD with the revision above and the verdicts A1 (§6, Case 2
UNKNOWN), A2 = A and A3 = S ("for now"); all three are recorded in §6. Owner check O1 (seam cases move from
"runs one-sided" to "refused visibly") was presented as a consequence of the verdicts and is recorded as
accepted, **as an assumption** (no separate explicit O1 confirmation). The AD-013 H2 amendment is **not** done and
remains a precondition of slice 3 (§5). Items 5 and 9 keep their wording; D-strict is now Artist-confirmed.

*Pointer 2026-10-08:* H2 amendment (G-2), see [AD-013, Addendum 2026-10-08](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-08-ad-sym-03-slice-3--h2-amendment-g-2-context-keyed-refusal-for-c-fail-closed-block-row): **DECIDED** (Manu, 2026-10-08), after independent review CLAUDE-001 (ACCEPT WITH CHANGES, no blockers, findings answered). It also fixes the A2 canonicalisation rule for slice 3: canonicalise always when a definition is set, for declared and undeclared contexts (in MARK a mirror edge pair runs as a one-sided Split until slice 4).

*Status line of the 2026-10-07 revision, kept for history:* No decision beyond the review's own proposals was taken, except: the interim choice of D-strict (the safe default
until A3), the visible refusal of the both-sides face case until A1/A2 (item 9), and A3 itself. Status then stayed
**PROPOSED**; open before DECIDED were: the AD-013 H2 amendment for G-2 (its own review), and the owner's confirmation
of this revision. A second review is not required by the findings (no blocker), but the owner may ask for one.
