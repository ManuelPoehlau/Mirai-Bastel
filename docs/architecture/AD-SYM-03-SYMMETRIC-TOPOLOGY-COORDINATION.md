# AD-SYM-03 — Symmetric Topology Coordination

**Status:** **DECIDED** (Manu, 2026-10-08), as revised after review CLAUDE-001 and with the Artist verdicts A1/A2/A3 (§6, §9).
**Addendum §10 (2026-10-09, symmetric Knife, slice 6): DECIDED** (Manu, 2026-10-09: **ACCEPT**) — K-C with side rule and clip; the assumptions of §10.2 are the basis; build order 6a → 6b → 6c (practical test) → 6d. Slices **6a, 6b and 6c are built** (§10.8); **slice 6c as built: KEEP** (Manu, 2026-10-09, practical test; see §10.8 "Artist verdict"). Slice 6d is not needed now. F6 and the choice between the mirror variants V-a / V-b / V-c stay **open** (§10.9).
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
  *Discovery 2026-10-08: see [SYMMETRY_KNIFE_DISCOVERY.md](../research/symmetry/SYMMETRY_KNIFE_DISCOVERY.md) (no decision).*
- **Residue under symmetry:** *answered for Edge Connect 2026-10-08* (§6, "3b practical check": ITERATE; created
  edges on the side(s) of the live selection, implemented as the engineering rule recorded there). Vertex Connect
  keeps the live selection (AD-017). **Split (slice 4, 2026-10-08): engineering default implemented and judged KEEP
  in the slice-4 practical test (Manu, 2026-10-08, §6 "Slice 4 practical check").** Vertex mode, the new vertex/vertices on the side(s) where the **live**
  selection had elements (same helper as Edge Connect: `residue_sides` / `on_residue_sides`); one edge selected -> the
  new vertex of that side only; a mirror pair selected on purpose (A2) -> both new vertices; a seam edge (or only
  elements on the plane) -> the new vertex lies on the plane and stays, the normal's side otherwise; without a
  definition the unchanged one-vertex residue. Artist-confirmed behaviour since the KEEP.
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

*Pointer 2026-10-08:* H2 amendment (G-2), see [AD-013, Addendum 2026-10-08](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-08-ad-sym-03-slice-3--h2-amendment-g-2-context-keyed-refusal-for-c-fail-closed-block-row): **DECIDED** (Manu, 2026-10-08), after independent review CLAUDE-001 (ACCEPT WITH CHANGES, no blockers, findings answered). It also fixes the A2 canonicalisation rule for slice 3: canonicalise always when a definition is set, for declared and undeclared contexts (in MARK a mirror edge pair ran as a one-sided Split until slice 4; it is coordinated since slice 4, 2026-10-08).

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

*Artist verdict (Manu, 2026-10-08, S2 practical test):* the practical test **passed**. Step 1 (the green seam point
vanishes when an edge crossing the seam is dissolved, two seam edges become one): **KEEP.** Steps 2-4 passed as
expected: a loop through the seam runs and the seam stays continuous; an edge with two seam endpoints is refused on
Dissolve and deleted by Delete (hole); two faces at the seam deleted as before. Seam rule S2 is therefore
Artist-confirmed behaviour; the warning idea above stays not decided.

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
B). Moot after the verdict below; the coordinator still refuses the both-sides face case (item 9). *Slice 4
(2026-10-08): symmetric Split exists; with A = canonicalisation a mirror pair is one Split intent and runs coordinated
in MARK and BLOCK (exactly two new vertices, no double split); the B comparison stays not built, the verdict made it moot.*

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

### Slice 4 practical check (Manu, 2026-10-08)

*Artist statement (Manu, 2026-10-08), Symmetry Lab:* "All practical tests passed: Keep." The five steps of the slice 4
handoff (single edge away from the seam, seam edge, deliberate mirror pair, edge without partner on
`man_with_shoes_basemesh`, Knife still refused under BLOCK) were run; no deviation was reported.

*Verdicts:* **(a) selection after a symmetric Split: KEEP** (only the new vertex of the side worked on; both new
vertices when both sides were selected on purpose; a seam edge's new vertex on the plane stays selected). The residue rule
of Implementation note 4 is therefore Artist-confirmed. **(b) Splitting always at t = 0.5:** covered by the same
statement; recorded as the accepted first state, without a separate answer on this point, so a later wish for another
split position (or the Knife snap, slice 6) is not ruled out.

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
| 4 | **Split** — **Done 2026-10-08** (`coordinate_split` in `src/mirai/symmetric_ops.py`, entered in `symmetry_declarations.C_CONTEXT_COORDINATORS` as `CContext.SPLIT`; the Split branch of `Application._connect_command` runs it inside its one `_mesh_transaction` whenever a definition is set, in MARK as in BLOCK; only `CContext.KNIFE` stays undeclared, so the Lab BLOCK row and the named refusals derive automatically (3a); tests `tests/test_symmetric_split.py`, `experiments/symmetry_lab/tests/test_app_lab_symmetric_split.py` plus the adapted 3a/3b gate and Lab fail-closed tests; measured in this container without `pyglet` (no EGL): `tests` 1941 → 1964 passed / 14 skipped, Lab suite 420 → 428 passed / 8 skipped / 1 failed (the same pre-existing pyglet overlay-order test), `playground/tests` not collectable here (pyglet display), `src/core`, `src/main.py` and `playground/` untouched). Slice 4 practical test by Manu 2026-10-08: **passed, KEEP** (§6) | Source + partner edge in one transaction (seam edge once + S1); t = 0.5 only, no snap; residue question prepared (engineering default, §4); A2 comparison becomes runnable | Disc. step 4 |
| 5 | **Seam cases** | Seam consumption per the A1 verdict (and the both-sides face case per A1/A2); D-source if A3 chooses it; DD-2 fully closed | Disc. step 5 (seam part). A1 answered 2026-10-08 (§6): Case 1 → M and Extrude → M are now Artist-decided inputs; Case 2 stays refused (Engineering interim rule, Artist UNKNOWN) — *refined 2026-10-08 (§6): an edge directly on the seam stays refused, an edge crossing the seam is dissolved via seam rule S2 (see Implementation note S2)*. No longer fully blocked on A1 |
| 6 | **Knife** | Symmetry context at `begin`, mirror records before resolution, pid → vertex report, **snap**, S1, seam-chord rule, mirrored preview (INV-11), **tie-break equivariance** | Disc. step 6. **[Δ]** tie-break is a known defect now (probe I); the snap lives here (review F6). *Discovery 2026-10-08: see [SYMMETRY_KNIFE_DISCOVERY.md](../research/symmetry/SYMMETRY_KNIFE_DISCOVERY.md) (no decision).* *Addendum 2026-10-09 (**DECIDED**, Manu 2026-10-09, §10; slice 6a built): K-C with side rule and clip — "mirror the kept mutations at the commit" instead of "mirror records before resolution"; revised slices 6a–6d (§10.8); after the independent review [CLAUDE-001 of the Knife Discovery](../archive/symmetry_lab/reviews/SYMMETRY_KNIFE_DISCOVERY_REVIEW_CLAUDE_001.md) (answered in the Discovery's §7).* |
| 7 | **Extrude** | After a Production port (owner, Disc. Q6) | Disc. step 7. **Done 2026-10-09** (WP-SYM-EXTRUDE-01; `src/mirai/symmetric_extrude.py`, `tests/test_symmetric_extrude.py`, `experiments/symmetry_lab/tests/test_app_lab_symmetric_extrude.py`; `tests` 2145 → 2232 passed / 41 skipped, Lab suite 450 → 466 passed / 4 skipped, in this container with pyglet under xvfb). As built, probe and findings: §11. **Artist verdict pending**; the one Artist statement is the Case 4 refusal (§11.1). |

**Unblocked after the 2026-10-08 decision:** slices 1 and 2 now (no gate change, no open verdict). Slice 3 only
after the AD-013 H2 amendment (G-2) is written and reviewed — **done: DECIDED 2026-10-08** (pointer in §5); **3a, 3b and 3c implemented 2026-10-08** (3a/3b verified by Manu the same day; 3c practical test answered, §6 second round; S2 practical test passed, step 1 KEEP, 2026-10-08). **Slice 4 (Split) implemented 2026-10-08**, practical test passed (KEEP, §6). Slice 5 is no longer fully blocked on A1 (see its row); A2 = A and A3 = S are inputs to slices 3–4.

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

**Implementation note 4 (2026-10-08).** What the code made concrete; nothing here changes a decision.

- **One coordinator, the shared refusals.** `coordinate_split(mesh, edge_ids)` uses `_refuse_before(..., mode="edge")`
  (exact plane, unpaired selection, both-sides face), reports before, calls `Mesh.split_edge(edge, 0.5)` for the source
  and, if distinct, for the partner, writes `seam_after_split` inside the same mutation if a seam edge was split, and runs
  the D-strict delta check. No new refusal text was needed. `Mesh.split_edge` invalidates only the edge it splits, so
  the partner id stays valid after the first split. A seam edge is its own partner and is split once; the new vertex is
  exactly on the plane (both endpoints have a zero coordinate on an exact plane) and, through S1, a seam vertex.
- **Mirror pair (A2 = A).** `_connect_command` canonicalises one edge before resolution, so a selected pair is one
  Split intent (the pair is the one `Expansion`); exactly two new vertices, no double split. This ends the MARK
  consequence recorded in the AD-013 amendment: a mirror pair no longer runs as a one-sided Split.
- **Residue (engineering default, §4).** Vertex mode, the new vertices on the side(s) of the live selection
  (`residue_sides` taken before the transaction, `on_residue_sides` over the created vertices). Without a definition the
  one-vertex residue is unchanged.
- **Measured on the assets (headless, not a committed test).** Every edge as a single selection, `subd_cube` X and Z,
  `head_basemesh` X: all splits succeeded (seam edges 8 / 8 / 36 with one new vertex, all others with two), each report
  clean, each one Undo step, Undo restores topology and history. `man_with_shoes_basemesh` (`partial`, X): 44 seam
  edges (one new vertex) and 1592 edges (two) split with no incomplete element added, 216 unpaired-selection
  refusals, no delta refusal, no exception.
- **Known behaviour, reported not decided.** An edge joining two mirror vertices across the plane without being a seam
  edge is its own partner; Split of it creates a vertex on the plane that is no seam vertex, so the delta check (or, if
  the edge lies in a plane-spanning face, the both-sides-face refusal) refuses it visibly. On the cube fixture of
  `tests/test_command_gate_contexts.py` this is edge 7-6. A Split next to unpaired geometry is refused only when the
  selected edge itself has no partner; a paired edge whose face holds an unpaired vertex splits (the face was
  incomplete before, INV-10).

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

*Pointer 2026-10-08:* H2 amendment (G-2), see [AD-013, Addendum 2026-10-08](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-08-ad-sym-03-slice-3--h2-amendment-g-2-context-keyed-refusal-for-c-fail-closed-block-row): **DECIDED** (Manu, 2026-10-08), after independent review CLAUDE-001 (ACCEPT WITH CHANGES, no blockers, findings answered). It also fixes the A2 canonicalisation rule for slice 3: canonicalise always when a definition is set, for declared and undeclared contexts (in MARK a mirror edge pair ran as a one-sided Split until slice 4; it is coordinated since slice 4, 2026-10-08).

*Status line of the 2026-10-07 revision, kept for history:* No decision beyond the review's own proposals was taken, except: the interim choice of D-strict (the safe default
until A3), the visible refusal of the both-sides face case until A1/A2 (item 9), and A3 itself. Status then stayed
**PROPOSED**; open before DECIDED were: the AD-013 H2 amendment for G-2 (its own review), and the owner's confirmation
of this revision. A second review is not required by the findings (no blocker), but the owner may ask for one.

---

## 10. Addendum (2026-10-09, DECIDED) — symmetric Knife (slice 6): K-C with side rule and clip

**Status:** **DECIDED** (Manu, 2026-10-09): **ACCEPT** — the mechanism (K-C with side rule and clip), the assumptions
of 10.2 as the basis, the build order 6a → 6b → 6c (practical test) → 6d. Text unchanged by the decision; F6 is not part
of it and stays open (10.9). Proposed 2026-10-09 (§ 10.10 "Was Manu entscheidet" kept as asked). Companion addendum:
[AD-017 §13](AD-017-CUT-ENGINE-CONTEXTUAL-C.md) (the Knife's kept-call report, DECIDED the same day), which this one
needs. **Slices 6a, 6b and 6c built** (10.8; 6c as built: **KEEP**, Manu, 2026-10-09, practical test); 6d not needed now.
**Basis:** [Knife Discovery](../research/symmetry/SYMMETRY_KNIFE_DISCOVERY.md) (KD) §1.3, §1.4, §2, §3, §6, §7; the
independent review [CLAUDE-001](../archive/symmetry_lab/reviews/SYMMETRY_KNIFE_DISCOVERY_REVIEW_CLAUDE_001.md) (R;
ACCEPT WITH CHANGES, blocker B1; archived, not edited; answered in KD §7); Manu's answers of 2026-10-09 (KD §6).
**Probe:** [`experiments/topology/symmetry_knife_probe.py`](../../experiments/topology/symmetry_knife_probe.py), section
KC (K-C+clip). **Read at:** `main` @ `fe040f1`.

### 10.1 Problem

§3 item 1 says the Knife mirrors its "intent/path" in the session tool, applied at its existing commit; §7 row 6
planned "mirror records before resolution, pid → vertex report, snap, tie-break equivariance". The Discovery measured
that mirroring records before resolution (K-A) is not exact where the resolver decides by itself — ties broken by
position, vertices the resolver computes in face frames, `t` on orientation-reversed edges (KD §1.3 K1, K3, K10) — and
that **K-C** (resolve the path once, replay its kept mutations mirrored) is exact on every one-sided path measured
(KD §1.3 K10: 1176 / 1176 on E-a…E-d). The review accepted K-C as the mechanism with one blocker (B1): K-C refused a
path that reaches the other side only when a mirrored call met an element the source had killed; through a seam
vertex, a gap or a second chain it committed a symmetric union that changes the Artist's side, which the delta check
cannot see (R8: 60 / 60). Manu answered F1 = C (KD §6): the cut is clipped at the seam.

### 10.2 Artist answers and assumptions (as recorded in KD §6)

*Artist statements (Manu, 2026-10-09):*
- **F1 = C:** „Der Schnitt soll an der Mitte kappen.“ The part beyond the seam is not cut; the mirror of the working
  side's part replaces it.
- **Two separate chains on both sides (R S1, "Fall 3"):** „wenn ich auf der linken Hälfte anfange zu schneiden, wird
  nur dort geschnitten und gespiegelt.“ The side where the cut starts is the working side; only cuts there are
  executed and mirrored.
- **F3 = A:** a target without a mirror partner is shown and refused at hover / click time (Enter still checks, as a
  safety net).
- **F4 = A:** after the symmetric Knife only the cut edges of the working side are selected (as Split / Edge
  Connect); seam edges created by the cut stay selected.
- **Silo reference test:** not possible (trial expired); Silo stays the feel reference from experience. The preview
  feel is tested in the app once the mirrored preview exists (slice 6c).

*Assumptions (planner's readings, stated to Manu, not objected, not confirmed):*
- F1 = C applies to the deliberate and to the accidental crossing (a line planned over the other side from a side
  camera, or towards a point in space).
- Working side = the side of the first record off the plane (exact sign of the plane coordinate; seam vertices and
  seam edges belong to both sides).
- F2 follows from F1: a hand-drawn "mirror" on the other side is clipped and replaced by the exact mirror; no snapping
  tolerance.
- F5 = A: a live coordinated Knife (Silo-like), no separate Knife symmetry capability.

*Engineering refinements of this addendum (not Artist statements):* "record" means a point on the mesh (clicked or a
planner crossing); a point in space does not choose the working side (it is not cut, and its plane coordinate is the
arbitrary depth `space_point` gives it; KD §1.4: in 15 camera sessions a point in space would choose the other side,
and 8 of them would then cut nothing). A crossing of the plane *inside* a face has no seam record to clip at and is
refused (item 9).

*Open (KD §6 F6; Manu 2026-10-09 left it open, 10.9):* a path that starts in space can cross the other side before the first click on the
mesh; then "first record" and "first clicked record" give different working sides (28 of 371 camera sessions,
both readings exact; under "first record" 3 of the 28 cut nothing at all, because the only −X record is one planner
crossing). The rule runs with "first record" until Manu answers.

### 10.3 Evidence (KD §1.3, §1.4)

| Question | Result |
|---|---|
| Is K-C exact on one-sided paths? | Yes on every measured one: KD §1.3 K10 1176 / 1176 E-a…E-d (ties and resolver-made vertices included, K3); R R7 879 / 879 seam-biased paths; the kept log replayed verbatim rebuilds the resolved mesh 1176 / 1176 (R R3) |
| Does K-C+clip close B1? | Yes. The review's union cases now give the clipped working-side cut plus its exact mirror: R8 60 / 60, R1 4 / 4 (both orders), R10 `E ++++`; the 90 sessions K-C refused (R9) 90 / 90; **0 unions** over every re-run table (KD §1.4) |
| Does the clip change one-sided paths? | No: the clip is the identity there; under K-C+clip K10 1176 / 1176 and R7 879 / 879 `E ++++`, the same results as K-C |
| Seam rows (K7)? | c and d / d′ / d″ (refused by K-C) are now `E ++++` on all three meshes, clipped at the seam; a, a′, b, b2, g, h unchanged `E ++++`; the plane-spanning rows e, e′, f, f′, f″ refused (item 9) |
| Camera sessions (K4, K5)? | 371 sessions (K4 179, K5 192): 368 `E ++++`, 3 cut nothing (all three F6 cases, 10.2), 0 refused, 0 unions — K-C had 1 union and 90 refusals on the same sessions |
| Do the nets fire after the clip? | The guard's other-side check and the "already cut by the source" collision check: never; the guard's item-9 check refused only the synthetic plane-spanning rows. Duplicate vertex pairs: 0 in every committed result (N4) |
| Cost | Side rule + clip 0.05–0.20 ms (median per sample) per commit; the commit as a whole costs what K-C cost (KD §1.3 K10 times) |
| Self-partner edge across the plane (N5) | 0 such edges on `subd_cube`, `head_basemesh`, `man_with_shoes_basemesh`, `tie_grid`; every resolver path through one also cuts a self-mirrored face (item 9). Refused (fail-closed) rather than mapped crossed |

### 10.4 Proposal — changes to §3 (mechanism only; nothing decided by the Artist changes)

1. **§3 item 1** — "intent/path mirroring … applied at the tool's existing commit" becomes **mirroring the resolved
   intent**: at the Knife's own commit, its commit coordinator resolves the (clipped, 10.6) path once, unchanged, and
   replays the resolver's kept mutations mirrored (K-C). Unchanged: the symmetry context reaches the tool at `begin`;
   the Knife commits in `KnifeTool._on_commit`; no `SymmetricKnife`; one `MeshStateCommand` (INV-7).
2. **§3 item 2** — the replay is **Knife-only**: it lives with the Knife's commit coordinator (beside
   `symmetric_ops`), not among the shared services (M-e; R N9). It uses the shared services as they are:
   `SymmetryIndex`, the exact-plane predicate, seam rule S1, the completeness report and delta check.
3. **§3 item 4** — the Knife's created-element report is not "pid → created vertex" but the **kept-call report** of
   AD-017 §13 (op, arguments, results, created positions, halves; truncated on rollbacks). No pid → vertex map (R N2).
4. **§3 item 6** — for the Knife, the snap X-a becomes **placement at replay**: every mirror vertex is created by the
   replayed call and placed at `mirror_position(source vertex)` there; no post-op snap. Exact planes only, as decided.
5. **§7 row 6** — "symmetry context at `begin`, mirror records before resolution, pid → vertex report, snap, S1,
   seam-chord rule, mirrored preview, tie-break equivariance" becomes the slices of 10.8. Tie-break equivariance needs
   no resolver change: the mirror side is never resolved.

### 10.5 Side rule (B1)

- **Side of a record:** the exact sign of its plane coordinate on the session-start mesh (AR-1, no tolerance). Zero =
  on the plane: a seam vertex, an edge point on a seam edge — it belongs to both sides.
- **Working side:** the side of the first mesh record off the plane (clicked or a planner crossing; points in space
  excluded, 10.2). It is derived from the current path and never stored: in-session Undo can change it.
- **No mesh record off the plane:** the working side is taken from the first kept call off the plane; if there is
  none, the cut lies only in faces on or spanning the plane, which item 9 refuses (KD §1.3 K7 e: unreachable on the
  Lab assets).
- **Kept-call guard (the net under the clip):** after the resolve, every kept `split_edge` must lie on the working side
  or on the plane and every kept `split_face` in a face of the working side; a face on or spanning the plane is refused
  (item 9). Its other-side check never fired after the clip; its item-9 check refused only the synthetic
  plane-spanning rows (10.3). It stays because it makes "the result is the working-side cut plus its mirror" a checked
  property instead of a consequence of the clip.

### 10.6 Clip (F1 = C), in the commit coordinator, before the resolver

- Every maximal stretch of records on the other side (mesh records and points in space) is replaced by one pen lift;
  the breaks inside it go with it. A record on the plane (seam vertex, seam edge point) ends or starts a run there.
- A cyclic (closed) chain holding such a stretch is first rotated to start right after its last other-side stretch,
  so its closing segment stays a cut. (Probe only: a clipped loop whose interior start the next chain continues would
  lose its seed; it is refused there and occurred 0 times — 6b refuses it with a text.)
- A cut segment from a working-side record straight to an other-side record (no break, no seam record between) crosses
  the plane inside a face: refused (item 9). 0 occurrences on the Lab assets; it occurs on the synthetic plane-spanning
  fixtures (KD §1.3 K7 f / f′ / f″).
- Deliberate and accidental crossings are clipped alike (assumption, 10.2); a second chain on the other side is dropped
  (Manu, two chains); a hand-drawn mirror is dropped and replaced by the exact mirror (F2, assumption).
- The resolver stays unchanged and camera-free (AD-017 #1); the clip needs no camera rule on the mirror side and no
  resolver change — the handoff's stop condition did not trigger.
- Until slice 6c the clip is decided at commit only; from 6c the preview shows the clipped part (INV-11). How it is
  shown is the 6c Artist test, not decided here.

### 10.7 Refusals, residue, contract

**Refusals** (`SymmetryRefusal` with a status text; mesh restored, no history entry; in MARK as in BLOCK, §2.5):

| Refusal | When | Basis |
|---|---|---|
| Non-exact plane | `begin` (no session) | item 6 |
| Target without partner (vertex, edge, face) and cut face without partner (predictor P2) | hover / click — marked, click refused (F3 = A); checked again at Enter | A3 = S; KD §1.3 K8: with K-C, P2 predicted every D-strict refusal |
| Plane crossed inside a face (no seam record to clip at) | click (from 6c) and commit | item 9 |
| Kept cut in a face on / spanning the plane; self-partner edge across the plane (N5) | commit | item 9; R N5 |
| Kept mutation on the other side (guard); unknown kept-call kind | commit | 10.5; AD-017 §13 item 6 |
| Mirror element already cut by the source (collision) | commit | safety net only; never fired after the clip |
| Completeness delta (D-strict) | commit | item 5, A3 = S |

**Residue (F4 = A):** after the commit the cut edges of the working side are selected in Edge mode (the AD-017 Knife
residue: the connecting edges, not split remnants); cut edges lying on the plane stay selected; the mirror side's cut
edges are not selected. Without a definition the residue is unchanged. *Engineering reading (to be confirmed in the 6c
practical test):* Manu's "seam edges created by the cut stay selected" is read as option A's own words ("Kanten auf der
Mittellinie bleiben dabei") — a cut edge on the plane belongs to both sides; the halves of a split seam edge are
remnants and stay unselected, as in the AD-017 residue.

**Contract details (R N8):**
- Partners come from the session-start state (index built before anything is cut); the path refers to session-start
  ids anyway, because the mesh is untouched until commit.
- On a refusal at commit the source's mutations are taken back to `session_before` (`load_state`), no history entry,
  the status line names the reason. Probe: every refusal restored the session-start state (8 / 8).
- After a refused Enter the session ends with that status line, as a taken-back commit does today
  (`application.py:1080-1081`; engineering default, not decided). The alternative — the session stays open with its
  path so the Artist can undo the offending step — is a question for the 6c practical test. With F3 = A most refusals
  arrive at hover / click, before Enter.

**Declaration (R S3):** `CContext.KNIFE` is declared only when the mirrored preview and the click-time refusals exist
(slice 6c). Until then the Knife stayed refused under BLOCK and one-sided with the warning under MARK; slice 6b's
coordinator was not passed by `Application`. **Since slice 6c (2026-10-09) it is declared**: the BLOCK row names no
context any more and the MARK warning line never shows for the real declarations (both derived, 3a; the mechanism and
`KNIFE_ONE_SIDED_TEXT` stay for an undeclared context). The entry is the Knife's commit coordinator
`(mesh, session path, session_before) -> resolution` (raises `SymmetryRefusal`) — a second signature in
`C_CONTEXT_COORDINATORS` beside `(mesh, canonical ids) -> result`; nothing calls it with selection ids, because
`_connect_command` returns `_knife_begin()` before any lookup. D-b holds: the entry is the implementation.

**The Knife without symmetry** is unchanged: no definition → no coordinator; the kept-call report is additive
(AD-017 §13).

### 10.8 Revised slice cut (replaces KD §3's table of 2026-10-08)

Each slice keeps `pytest tests --ignore=tests/test_extrude_tool.py`, `pytest experiments/symmetry_lab/tests` and
`pytest playground/tests` green, runs the Symmetry Lab tests for `application.py` / `src/viewport/` changes (CLAUDE.md),
and touches no `src/core`.

| # | Slice | Content | Tests | AD | Model |
|---|---|---|---|---|---|
| 6a | **Kept-call report** | `resolve_cross_face` records its kept `split_edge` / `split_face` calls through two recording helpers and one checkpoint / rollback helper (AD-017 §13); additive output; no pid → vertex map | static tests (no other mutating `Mesh` call, no bare `load_state` in `knife_resolve.py`); identity replay of the report on a session-start copy over the golden net and a fuzz; golden net byte-identical; `tests/test_knife_parity.py` unchanged | AD-017 §13 | Type A — Sonnet 5, effort high. **Done 2026-10-09** (commit `feat(mirai): the Knife's kept-call report (AD-SYM-03 slice 6a, AD-017 §13)`; `tests/test_knife_kept_calls.py`, `playground/tests/test_knife_kept_calls_golden.py`) |
| 6b | **Symmetric commit coordinator (headless, not wired)** | side rule + clip (10.5, 10.6) → resolve → guard → strict replay (partners at session start, placement at `mirror_position`, halves by inclusion, N5 and unknown kinds refused, collisions as net) → S1 → delta check; `SymmetryRefusal` texts; rollback to `session_before`; residue F4 = A; `KnifeTool.begin(symmetry=…)` and `_on_commit` call it; `Application` does **not** pass it yet; not declared | in the probe's shape: E-a…E-d over a camera-free fuzz and a seam-biased fuzz; **regression rows R1 (two chains, both orders), R8 (seam-vertex crossings), R10 (the K5 side-camera union session)**, K7 a–h and the plane-spanning rows, the clipped closed loop; no duplicate vertices; every refusal restores the session-start state; the Knife without a definition unchanged (golden net, parity) | this addendum | Type A — Sonnet 5, effort high. **Done 2026-10-09** (commit `feat(mirai): the symmetric Knife's commit coordinator (AD-SYM-03 slice 6b)`; `src/mirai/symmetric_knife.py`, `tests/test_symmetric_knife.py`, `tests/symmetric_knife_support.py`, frozen sessions `tests/fixtures/symmetric_knife_sessions.json` with their extraction script `experiments/topology/extract_symmetric_knife_sessions.py`; see the notes below the table) |
| 6c | **Mirrored preview, click-time refusals, wiring, declaration** | `knife_render_data` gains the mirrored fields and the clipped part; hover marker / status for a target or cut face without partner (P2) and for a crossing inside a face; `Application._knife_begin` passes the coordinator whenever a definition is set; `CContext.KNIFE` declared (BLOCK row and MARK warning follow, 3a); Lab tests that pin the Knife refusal and `KNIFE_ONE_SIDED_TEXT` change with the declaration. **Engineering default, Artist test before KEEP; the preview variant is the Artist's** (R N1) | render-data tests (mirror fields, clipped part, 0 cost without a definition); refusal-at-hover tests on `man_with_shoes_basemesh`; Lab BLOCK / MARK tests; practical test for Manu (preview feel incl. the clipped part, refusal at hover, residue, session after a refused Enter) | none expected (Production UX, provisional) | Type A — Sonnet 5, effort high. **Built 2026-10-09** (commit `feat(mirai): the symmetric Knife in the app — mirrored preview, click-time refusals, declaration (AD-SYM-03 slice 6c)`; see "Slice 6c as built" below; **slice 6c as built: Artist verdict KEEP (Manu, 2026-10-09) — see "Artist verdict" below; look, texts, variant defaults keep their provisional / engineering-default labels**) |
| 6d | **Answers after 6c (only if needed) — not needed now (6c KEEP, 2026-10-09)** | F6 (working side for a path that starts in space) once answered; whatever the 6c practical test ITERATEs (preview variant, display of the clipped part, session after a refused Enter) | as the answers require | as answered | Type A — Sonnet 5, effort high |

**Slice 6b as built (2026-10-09; implementation of §10.4 item 2 — no new decision).**
- **Module and injection:** `coordinate_knife(mesh, path, session_before) -> KnifeResolution` lives in `mirai/symmetric_knife.py` beside `symmetric_ops` (imports `symmetric_ops`, `symmetry_coordination`, `symmetry`, `topology.knife_resolve`, `core`; never `application`, never `topology.knife`). `KnifeTool.begin(..., symmetric_commit=coordinate_knife)` injects it; `topology/knife.py` imports nothing from symmetry and recognises a refusal by the marker `commit_refusal` on the exception (`KnifeRefusal`, a `SymmetryRefusal` subclass). Without the callable `_on_commit` is the code it was. `Application` does not pass it; `CContext.KNIFE` stays undeclared (6c).
- **Who restores:** the coordinator takes every mutation back (`load_state(session_before)`) before it raises, also for any other exception; the tool restores once more for a callable it did not write. A refusal pushes no history, leaves the selection alone and sets `last_problem` to the status text (`last_resolution` is `None`). Residue F4 = A is the resolver's `path_edges` of the clipped working-side cut (no mirror edges, no seam halves).
- **Reader detail:** the report names an edge and its halves, not the edge's ends, and Core's orientation of the edges `split_face` creates is not semantic. The replay therefore derives the ends of a split edge from the report and the cut mesh (first end of `half_1`, second end of `half_2`, recursively until an edge that still exists). A shadow of "chain order" as ends was wrong on 2 of the camera sessions and is not used.
- **Cases the rules left to the net (stated, not chosen):** (a) kept calls exist but none lies off the plane and no record chose a side → refused (item 9 text), as §10.5 reads; (b) a source that is broken on its own (the same face point clicked twice cuts two coincident vertices; the one-sided Knife rolls it back) is refused by the completeness delta (ambiguous partners) instead of the integrity text; the session start is restored either way; (c) an empty or malformed `split_face` report is refused fail-closed. No union, E-b failure or duplicate vertex occurred; no non-X plane behaved differently; the resolver, Core, `Application` and the declarations needed no change, so §10.9 gains no question.
- **Evidence (`tests/test_symmetric_knife.py`, 69 tests):** E-a…E-d over seeded camera-free, seam-biased and both-sides fuzz — 300 valid paths per kind on `subd_cube`, `head_basemesh` (both-sides: 150) and the tie grid, 60 per kind on Y+, Z−, tie grid Y− and the head with a negative X normal — every committed result E ++++, 0 duplicate vertices, only the lost-seed loop refused; the 483 frozen sessions (R1 both orders, R8 60/60, R10, the 371 K4/K5 camera sessions incl. the ones the plain K-C refused, K7 a–h, the plane-spanning rows e, e′, f, f′, f″ and N5 refused with the mesh at the session start) reproduce what the probe pinned, and R1/R8/K7/loops/N5 give the same statuses, element counts and mirrored working side on Y, Z and negative-normal copies; every net (other side, unknown kind, N5, collisions, unrepeatable mirror cut, delta) is driven with a forged report. Eleven deliberate breakages of the module (clip off, guard off, no placement, no S1, no delta, halves by equality, no restore, …) are each caught.
- **Cost** (median commit time per path, symmetric vs one-sided Knife on the same camera-free paths, this container, Python 3.13): `subd_cube` 1.05 vs 0.49 ms (×2.1), tie grid 1.01 vs 0.44 ms (×2.3), `head_basemesh` 6.86 vs 2.11 ms (×3.3); p95 head 10.1 vs 5.5 ms. Numbers only, no threshold.
- **One 6a guard narrowed:** `tests/test_knife_kept_calls.py::test_only_the_symmetric_coordinator_reads_the_report` (was `…nothing_in_src_outside_the_resolver_reads_the_report`, `readers == []`) now asserts exactly `src/mirai/symmetric_knife.py` — AD-017 §13 item 8 ("only this coordinator reads `kept_calls`"), which the old test's docstring announced.

**Artist verdict, slice 6c as built (Manu, 2026-10-09, practical test): KEEP.** Manu tested "everything possible"; it works "surprisingly well". During the test a general (non-symmetric) Knife problem was found and fixed (not a symmetry defect; the commit link is unconfirmed). KEEP applies to slice 6c as built; it does not upgrade the look, texts, variant defaults or key below, which keep their provisional / engineering-default labels. Consequences (stated in planning chat, accepted by Manu 2026-10-09): slice 6d is not needed now (it was only for rework after the 6c test); **open, not decided:** the choice between the mirror variants V-a / V-b / V-c (V-b stays the default, V-a and V-c stay switchable, no decision to remove any) and F6 (working side for a path that starts in empty space; Manu: "irrelevant for now"); next in the symmetry track: symmetric Extrude (slice 7), then the symmetry promotion check (separate handoffs).

**Slice 6c as built (2026-10-09; implementation of §10.8 row 6c — no new decision; every look, text and key below is an engineering default; slice 6c as built has the Artist verdict KEEP, see above).**
- **One clip, two readers.** `mirai.symmetric_knife.SymmetricKnifeView(mesh)` is built once at `begin` (one `SymmetryIndex`; the mesh does not change during a session) and holds `clip` (= `clip_path`, the function `coordinate_knife` uses), `mirror`, `side` and `refusal`. `knife_preview.build_knife_render_data(..., symmetry=view, refused=…, pen_up=…)` takes it as an opaque duck-typed argument; `topology/knife.py` and `topology/knife_preview.py` still import nothing from symmetry. The preview therefore cannot show a clip the commit does not do. Without a view the render data is built by the same loop as before and every additive field keeps its default.
- **Render data (additive).** Working-side fields as before, now holding the working side's part only; `mirror_*` (start, prospective, target edge, line, path segments, placed points, crossings — each `mirror_position` of the working-side value); `clipped_points` / `clipped_segments` (the other-side part of the drawn path) and `clipped_hover_points` / `clipped_hover_segments` (a hovered target on the other side with its crossings, edge and line — shown clipped, not refused); `refused_points` / `refused_segments` (the hovered target a click is refused for, its edge and the line from the start); `working_side`. A pen lift removes start and rubber band in the symmetric fields too. A hover with the start in the clipped part draws its whole line clipped (a segment that crosses the plane at a seam record is not split into two pieces — rare; stated, not chosen).
- **Click-time refusals (F3 = A).** `KnifeTool.begin(..., symmetric_commit=…, symmetric_view=…)`; `plan()` asks `view.refusal(path with the click, cut faces)`. The answer is the **front part of the commit**, nothing else: the clip (`TEXT_KNIFE_PLANE_IN_FACE`, `TEXT_KNIFE_SEED_LOST`), the unpaired rule on the clipped path's mesh records (new hover text `TEXT_KNIFE_TARGET_UNPAIRED`; the commit keeps `TEXT_UNPAIRED`), and for every cut stretch that survives the clip the face it lies in — it needs a partner (`TEXT_KNIFE_FACE_UNPAIRED`), must not lie on or across the plane (`TEXT_KNIFE_ON_PLANE`, item 9) and must lie on the working side (`TEXT_KNIFE_OTHER_SIDE`). The face of a stretch is the one the click-time `_link` decided by (`KnifeTool._link_face`: the first shared face by id that holds the cut); `KnifePlan.refused` / `.stretches` carry it, `accepts()`, `click()` and the hover share the one answer, and a refused target never enters the path. A close the view refuses is no close: `plan_lift(close=True)` lifts without it ("not closed: …"). What only the resolve shows (collision, mirror failure, completeness delta) stays a refusal at Enter. **A partnered target on the other side is accepted** and shown clipped; an unpartnered target on the other side is not refused either (it is clipped before the unpaired rule runs, exactly as at the commit) — written down because the handoff's wording could be read otherwise.
- **Viewport.** New tool layers (`overlay.TOOL_SYMMETRY_LAYERS`): `tool_mirror`, `tool_mirror_preview`, `tool_mirror_dim`, `tool_clipped`, `tool_refused`, with colours of their own (blue-violet mirror, grey clipped, magenta refused); line depth: `tool_mirror` and `tool_clipped` depth-tested like the path, `tool_mirror_preview`, `tool_mirror_dim` and `tool_refused` on top like the preview; points ignore depth as always. Existing layers, colours and depth behaviour are unchanged.
- **Variants (provisional, switchable inside the session by `V`).** V-a: mirror like the working side's own preview (path lines depth-tested, hover on top, points through); **V-b (default)**: mirror always visible and dimmed; V-c: mirror points only. `V` is checked in `Application._knife_key` as a plain key — not a command, so `commands.py` and the Lab's gate rows are untouched — only when no command is bound to it in the Knife context and only in a symmetric session; it is none of the Lab's three keys. The active variant is named in the status text (begin, variant change, every click / lift / undo as `[Spiegel V-b]`). The variant is kept across sessions of one `Application`. The key and the losing variants are removed or kept in 6d.
- **Begin / hover / click.** `_knife_begin` passes the declared coordinator and the view whenever a definition is set; a non-exact plane posts `TEXT_NON_EXACT_PLANE` and starts no session. A refused hover shows the refused style and its text once (not per mouse move); leaving it restores the session note. A refused click is ignored and posts the same text. After a refused Enter the session still ends (as 6b; to be tested).
- **Declaration.** `C_CONTEXT_COORDINATORS[CContext.KNIFE] = coordinate_knife` (the second signature, as announced above). The Lab's BLOCK row names no context any more; the allow-list, `NON_OPERATION` and the three Lab keys are unchanged; no H2 change.
- **Tests changed because of the declaration** (each states the old pin): `tests/test_symmetric_knife.py` (the two "undeclared / not passed" tests now pin the declaration and the wiring), `tests/test_symmetric_ops.py` (the declaration table holds the Knife), `tests/test_command_gate_contexts.py` (`UNCOORDINATED_CONTEXTS` = `NONE` only), and in the Lab suite the tests that pinned the Knife refusal under BLOCK / `KNIFE_ONE_SIDED_TEXT` under MARK (`test_app_lab_gate.py`, `_keys.py`, `_fail_closed.py`, `_symmetric_connect.py`, `_symmetric_split.py`, `_bindings.py`) — they now run the same assertions with the Knife undeclared by `_app_lab_support.undeclare_knife` (the derived mechanism stays tested) or assert the new declared state. New: `tests/test_symmetric_knife_preview.py`, `experiments/symmetry_lab/tests/test_app_lab_symmetric_knife.py`, a GL layer test in `tests/test_gl_knife_overlay.py`.
- **Measured** (this container, x86_64, Python 3.13, headless; numbers only, no threshold). *Hover update* (`pointer_motion` in a Knife session: pick + plan + overlay) on `head_basemesh`, 2 placed points, 5 runs: median 1.13–1.15 ms without a definition vs 1.21–1.24 ms with one (≈ +0.1 ms, +6 … 9 %), p95 ≈ 3.0 vs 3.2 ms. It grows with the path, because the click-time question re-clips the session path (O(points), no resolve, no index rebuild): hovering far targets (planner active) with a path of 2 / 44 / 113 recorded points: median 2.8 / 3.0 / 3.4 ms plain vs 3.0 / 3.7 / 4.7 ms symmetric, p95 5.3 / 5.0 / 5.1 vs 5.8 / 6.1 / 6.5 ms. Session start builds one `SymmetryIndex`. The reference-PC reading is the Artist's. *Suites* (without `pyglet`, as the 6b baseline): `tests` 2058 → 2084 passed / 14 skipped; Lab suite 428 passed / 8 skipped / 1 failed → 436 / 8 / 1 (the same pre-existing `pyglet` overlay-order test); with `pyglet` under `xvfb-run`: Lab 441 → 450 passed / 4 skipped, `playground/tests` 1241 → 1241 passed, `tests` (GL tests running, `tests/test_pyglet_input.py` ignored: no EGL here) 2084 passed / 40 skipped.

Order: 6a → 6b → 6c (practical test) → 6d. 6a and 6b change nothing the Artist sees; 6c is the first slice that does.

### 10.9 Not decided here

- F6 (KD §6): "first record" (as run) or "first clicked record" for a path that starts in space. **Manu, 2026-10-09,
  verbatim:** „offen lassen (die Idee ist, später bei Start im leeren Raum ein Slice zu starten, ist jetzt aber erstmal
  irrelevant)“. **Left open.** Not interpreted here; the rule keeps running with "first record" (10.2) until it is
  answered. Idea recorded in [`docs/future_ideas/MODELING.md`](../future_ideas/MODELING.md).
- How the mirrored preview and the clipped part look (6c Artist test; V-a / V-b / V-c of KD §2.7), and whether the
  session stays open after a refused Enter. **Built provisionally in 6c, awaiting the Artist verdict:** the three
  variants (default V-b) and the key `V`, the colours (mirror, clipped grey, refused magenta), the refused-hover
  and status texts, the clipped hover, the session ending after a refused Enter.
- Seam rows in faces on or spanning the plane (KD §1.3 K7 e, e′, f): stay refused (item 9); asked only when an asset
  has such faces.
- Non-exact planes; D-source; module names, texts, colours, keys.
- Whether a second independent review is wanted before the decision (Manu's call; the review's blocker is closed by
  measurement on the review's own cases, KD §1.4, §7).

### 10.10 Was Manu entscheidet (Deutsch)

**Was sich für dich sichtbar ändert** (ab Slice 6c im Symmetry Lab; 6a und 6b ändern nichts Sichtbares):
- Der Knife läuft mit Symmetrie auf beiden Seiten als ein Undo-Schritt, auch unter BLOCK; die orange Warnung
  „Knife läuft einseitig“ verschwindet.
- Die Seite, auf der dein Schnitt beginnt, ist die **Arbeitsseite**. Nur dort wird geschnitten; die andere Seite bekommt
  das exakte Spiegelbild.
- Läuft dein Schnitt über die Mitte — bewusst oder weil die Linie aus der Seitenansicht drüben läuft —, wird er an der
  Mitte **gekappt**; was dahinter liegt, ersetzt das Spiegelbild. Eine zweite Kette auf der anderen Seite fällt weg.
  Zeichnest du die Gegenseite von Hand nach, wird auch das gekappt und durch das exakte Spiegelbild ersetzt.
- Ziele ohne Spiegelpartner werden schon beim Darüberfahren markiert und der Klick abgelehnt; Enter prüft noch einmal.
- Nach Enter sind nur deine Schnittkanten ausgewählt (die auf der Mitte bleiben dabei).
- Eine Linie, die die Mitte *innerhalb* einer Fläche kreuzt, wird abgelehnt (auf deinen Assets gibt es das nicht).

**Was du mit Ja annimmst:**
- den Mechanismus: einmal schneiden, dann genau diese Schnitte gespiegelt wiederholen — statt den Pfad vorher zu
  spiegeln (das war ungenau bei gleich weit entfernten Ecken und bei selbst berechneten Punkten);
- die Annahmen aus 10.2 als Grundlage: Kappen auch beim versehentlichen Überqueren; Arbeitsseite = erster Punkt auf
  dem Mesh abseits der Mitte; Handgezeichnetes drüben wird ersetzt; ein live koordinierter Knife statt einer eigenen
  Fähigkeit. Wenn eine davon nicht stimmt: **CHANGE** und welche;
- die Reihenfolge der Bauschritte: **6a** (Knife schreibt mit, was er schneidet; unsichtbar) → **6b** (die
  symmetrische Übernahme, nur getestet, noch nicht im Lab) → **6c** (Vorschau der Gegenseite, Markierung beim Hover,
  Knife im Lab freigeschaltet; dein Praxistest) → **6d** (nur falls nach dem Praxistest etwas nachzubessern ist).

**Getrennt beantwortbar, nicht Teil des Ja:** F6 — wo beginnt der Schnitt, wenn du im leeren Raum anfängst (KD §6)?
Bis zu deiner Antwort gilt „erster Punkt auf dem Mesh“; der Praxistest in 6c ist ein guter Moment dafür.

**Deine Antwort zu diesem Addendum:** **ACCEPT** · **CHANGE** (was?) · **REJECT** (dann bleibt der Knife unter
Symmetrie blockiert bzw. einseitig wie heute).

**Antwort (Manu, 2026-10-09): ACCEPT.** F6: „offen lassen (die Idee ist, später bei Start im leeren Raum ein Slice zu starten, ist jetzt aber erstmal irrelevant)“.


## 11. Addendum (2026-10-09) — Extrude (slice 7), as built

**Status: implemented; every item below is Engineering / PROVISIONAL except the Artist statements in 11.1. Artist verdict on the
symmetric Extrude: pending** (practical test in `experiments/symmetry_lab/README.md`, "Slice 7"). Nothing in §3, §6 or §10 changes;
no decided item is touched. WP-SYM-EXTRUDE-01, `src/core/` unchanged, no promotion (`src/main.py` never sets a definition).

### 11.1 What the Artist has said (as recorded) and what this addendum does not decide

- **A1 Case 3 = M** (2026-10-08, §6): Extrude at the seam — the seam follows the mesh, the cap edge becomes the new seam.
- **A3 = S, "for now"** (D-strict): a selection or result without a mirror partner is refused visibly.
- 2026-10-09: Extrude (hold `T`, WP-06 B9) KEEP; Knife under symmetry KEEP; the symmetric Extrude comes next. Key `T` unchanged.
- **2026-10-09 (Manu, "Case 4"): an Extrude that touches the seam only at a corner, and plane-spanning faces → refuse visibly,
  for now.** *Scope of this statement: the refusal only.* Whether the proper fix (one cap vertex per component and old vertex) will be
  built is **neither decided nor rejected here**; it stays a Discovery finding (11.5, F-1).

Not an Artist decision, said so in the code and here: the selection after the commit (11.2, X8), all refusal texts, the working-side rule (X5).

### 11.2 As built — X1 … X10 (handoff numbering)

| # | As built | Label |
|---|---|---|
| X1 | Shape of the Knife's session coordinator. `mirai/symmetric_extrude.py` (imports `symmetric_ops`, `symmetry_coordination`, `symmetry`, `topology.extrude` for the Newell normal, `core`; never `application`). `plan_extrude(mesh, faces) -> SymmetricExtrudePlan` runs before any mutation; `Application._extrude_begin` hands the plan to the **unchanged** tool as `begin(..., symmetric_plan=plan)`. `topology/extrude.py` imports nothing from symmetry (a test pins it) and recognises a refusal by the marker `commit_refusal` on the exception (`ExtrudeRefusal`, a `SymmetryRefusal`), like `KnifeTool`. No `SymmetricExtrudeTool` copy. Without a plan the tool's code path is the B9 one (same arithmetic, same order). | Engineering, PROVISIONAL |
| X2 | Declaration (D-b): a third table `EXTRUDE_COORDINATORS = {commands.EXTRUDE: plan_extrude}` and `declared_extrude_commands()` in `symmetry_declarations.py`, in the style of the other two. The Lab derives from it: the BLOCK row allows `Extrude`, `e5_warning_text` warns about an *undeclared* Extrude in MARK (a warning that did not exist before, because `Extrude` is no `TRANSFORM_OPERATIONS` entry; with the real table it never shows). `Application` runs the planner whenever a definition is set, in MARK as in BLOCK. No definition → no planner → the B9 Extrude (B9 suites untouched and green). | Engineering, PROVISIONAL |
| X3 | Refusals before any mutation, in this order: non-exact plane (`TEXT_NON_EXACT_PLANE`), unpaired faces (`TEXT_UNPAIRED`), a face spanning the plane (`TEXT_EXTRUDE_SPANNING`), a plane vertex the extrusion cannot mirror cleanly (`TEXT_EXTRUDE_CORNER`). Union = selected ∪ partners (`expand_faces`), a mirror pair selected together counts once. The two new refusals are the **Artist's Case 4 statement** (11.1); the *texts* are Engineering defaults. "Spanning" = the face is its own mirror **or** has vertices strictly on both sides (a crossing face that is not its own mirror would break the working-side rule). The corner rule is stated at the **plane vertex**: the boundary of the extruded region (edges at the vertex with exactly one union face — the tool's own boundary rule) must pass it exactly twice (one arc through the seam: a pair across a seam edge, or that pair plus neighbours) or not at all (the whole star is extruded). Anything else (two separate seam contacts, or a face touching only at the vertex) gives a wall edge `S–S'` with four faces and a plane vertex without a seam edge. | Case 4 refusal: **Artist statement**; rule, texts: Engineering |
| X4 | Exact by construction, no tolerance. Every update hands the tool's own cap positions to `plan.place`: working-side vertices keep them, a vertex on the plane gets the plane coordinate exactly (`plane_point[axis]`, 0.0 on an exact plane), the other side is `mirror_position` of the partner's. A vertex's side is the exact sign of its plane coordinate; its partner is `SymmetryIndex.vertex_partner`. The "one old vertex in two components, last write wins" corner case of the unchanged tool is covered by the same projection (and, for the plane, by the X3 corner rule). | Engineering, PROVISIONAL |
| X5 | Distance scalar. Working side = the side holding more of the **live** faces (selection, or the hovered face when nothing is selected), tie → the plane normal's side. The reference normal is the sum of the **live faces on the working side** (union faces on that side if none), so mirrored faces no longer cancel. Dragging outward on the face you selected extrudes outward on both sides; the result is the same mirror image whichever side you work on (measured: worst deviation 4.4e-16 on `head_basemesh`, 5.6e-17 on `subd_cube`, three axes — float noise between two *different* gestures; within one result the mirrors are bit-identical). | Engineering, PROVISIONAL (the rule is the proposal, the two properties are the acceptance criteria) |
| X6 | Seam rule S3, 11.3 (cap edge **plus the in-plane wall edges at its ends**, corrected the same day, see 11.3). | Case 3 = M **Artist**; the mechanism Engineering |
| X7 | Delta check at the commit, not per update: `completeness_report` at `plan_extrude`, `delta_check` in `plan.finish` after S3. A violation → `ExtrudeRefusal(TEXT_DELTA)`: the tool restores the exact prior state (`load_state(before)`, selection restored), pushes no history, `tool.refusal` carries the text, `Application._extrude_release` shows it (the B9 abort path with a different status). Any other exception from `finish` also restores the mesh and then propagates. | Engineering, PROVISIONAL |
| X8 | One `MeshStateCommand`, as before; the seam definition travels in the state, so Undo/Redo restore it with the mesh. Selection after the commit = the new cap faces **on the residue sides** (`residue_sides` of the live faces before, `on_residue_sides` after) — **the same Engineering default as Connect/Split (§4), explicitly not an Artist decision for Extrude**. Undo restores the previous selection (B9 mechanism unchanged). | Engineering default, **no Artist decision** |
| X9 | `_gate_refuses` is unchanged and runs before arming. With the declaration Extrude is allowed under BLOCK and MARK; the X3/X7 refusals apply in both modes. | Engineering |
| X10 | Nothing else changed: W/E/R, the Knife, `C`, Delete/Dissolve, the B9 lifecycle without symmetry, `src/main.py`. | — |

### 11.3 Seam rule S3 (`symmetry_coordination.seam_after_extrude`)

A seam edge the extrusion consumed (a face pair across the seam makes it an internal edge; the tool's prune removes it) is dropped, and the
cap edge that joins the new vertices of that edge's two ends becomes a seam edge, **together with the two wall edges that join each surviving
end vertex to its cap copy** (they lie in the plane, carry a mirrored pair of walls, and the Lab's own seam derivation would include them).

*Correction (2026-10-09, after Manu's first Lab run).* The first version of S3 added only the cap edge. That passed the delta after the first
Extrude (the cap vertices are seam vertices through the cap edge) but broke the second one: extruding the selected cap again consumes the cap
edge, the old cap vertices stay in the mesh on the plane with no seam edge left, become unpaired, and the delta refuses ("neue Elemente ohne
Partner", purple seam vertices). The probe and the fuzz had never extruded a result twice. With the wall edges the seam path stays connected
(…–a–a'–a''–b''–b'–b–…); the invariant "every vertex on the plane ends a seam edge" holds after every committed Extrude and is a test. The cap
edge was the Artist's M; the wall edges are the engineering reading of "the seam follows the mesh" and are part of what the practical test shows.
Pure: ids and incidence only (`seam_ends_before`, the mesh
after, the tool's old → new vertex map), no geometry, no tolerance; a consumed edge whose ends have no cap copy or whose cap edge is not found keeps
its dead id, so the delta check (rule 2) refuses instead of S3 guessing. Written inside the same mutation (`mesh.symmetry_definition = …` before
the history state is exported). Surviving seam edges stay. Per consumed edge one seam edge goes out and three come in (cap edge, two wall edges); repeated Extrude of the caps is tested on both assets, three axes, with Undo back through every seam.

### 11.4 Step 0 probe (before any wiring; throw-away scripts, now the tests)

Mesh: `subd_cube`, `head_basemesh` (planes X, Y, Z), plus synthetic `span_grid`, `hexagon_grid` and a valence-5 seam pole (`tests/test_symmetric_extrude.py`).
"Naive" = the unchanged tool on selection ∪ partners, no plan. "Proposed" = X4–X6.

| # | Case | Naive | Proposed (X4–X6) |
|---|---|---|---|
| a | one face + partner | partners resolve; **delta fails** (head: 8 created vertices without partner; cube X/Y: 4; cube Z passes by float luck) | OK on all 24 / 324 faces × 3 axes |
| b | face with an edge on the seam | delta fails; **1 dead seam id** ("seam edge consumed") on every asset and axis | OK, seam definition has no dead id, seam vertices exactly on the plane |
| c | faces touching the plane only at a corner | no such face on either asset (0 faces with exactly one plane vertex). Synthetic pole: fails (1 created vertex without partner; wall edge `S–S'` with **4 faces**) | **cannot be handled by S3** → Artist: refuse visibly (11.1); the probe is why |
| d | both sides selected | fails like (a) | OK, same result as selecting one side |
| e | negative distance | fails on the head, passes on the cube | OK |
| f | self-mirrored face | the assets have none. `span_grid`: delta refuses ("3 new face(s) spanning the plane"); `hexagon_grid`: same unpaired-plane-vertex failure as (c) | refused before any mutation (`TEXT_EXTRUDE_SPANNING`, Artist statement) |
| g | non-X plane | Y and Z behave like X | OK |

Created vertices: bit-identical mirrors, seam vertices exactly on the plane (no tolerance), checked on every committed result. Hypotheses of the
handoff: (i) naive union breaks on (c) — **confirmed, and X4 does not repair it** (the contradiction that stopped the first pass); (ii) dead seam
id on (b) — **confirmed**; (iii) distance scalar misbehaves for left/right faces — **confirmed** (a pure ±X wall pair: the unchanged tool falls back
to Z and the distance of an outward drag is 0.0; with X5 it is the drag); (iv) partner matching fails through non-bit-identical normals —
**confirmed in part** (the head always, the cube depending on the axis). A fuzz over every single face and 240 seeded random selections of 1–6 faces on the two assets found no refusal and no
commit failure.

### 11.5 Findings for Discovery (listed, not acted on)

- **F-1 (the Case 4 root cause).** The unchanged tool creates one cap vertex per *old vertex*. At a plane vertex where the region's boundary passes more
  than twice, that one cap vertex is shared by the caps of both mirror components: it lies on the plane without a seam edge (unpaired), and the edge
  `S–S'` carries four wall faces (non-manifold). The candidate fixes are a cap vertex per component and old vertex, or a seam rule for the wall edge —
  **neither is built, decided or rejected.** The same non-manifold edge exists in B9 without symmetry for two faces touching at an off-plane corner;
  unchanged.
- **F-2.** The shipped assets contain no corner-touching face and no self-mirrored face, so the Case 4 refusals cannot be seen on them; they are tested on
  synthetic meshes. The practical test point 4 therefore cannot be performed on `head_basemesh`.
- **F-3.** The corner rule also refuses two *separate* pairs across two different seam edges at one seam vertex (not only "a corner"); the text says
  "nur an einer Ecke", which is approximate there.
- **F-4.** Before this slice MARK showed no warning for a one-sided Extrude (`Extrude` is not in `TRANSFORM_OPERATIONS`); the derived warning exists now
  but only appears with an undeclared table.
- **F-5.** In the Lab `Shift+S` is an Undo step of its own, so "one Undo step" in Lab tests is counted relative to the history length at the start.
- **F-7.** A fuzz that only extrudes *fresh* meshes cannot see state left behind by the first Extrude; the first pass never extruded a result again and missed the S3 gap (11.3 correction). The repeated-Extrude tests now cover it.
- **F-6.** The delta text for a rejected commit ("neue Elemente ohne Partner") is generic; with the pre-checks it should now only appear for a bug or a
  Core-level surprise.

### 11.6 Tests and existing tests changed

New: `tests/test_symmetric_extrude.py` (87: Step-0 cases × assets × axes, S3 pure, scalar and side properties, fuzz, refusals, delta refusal at the commit,
Undo/Redo/cancel incl. the seam, repeated Extrude of the caps, layering, B9 equivalence without a plan) and `experiments/symmetry_lab/tests/test_app_lab_symmetric_extrude.py` (18: declaration,
BLOCK row, MARK warning mechanism, `T` coordinated in BLOCK and MARK, residue sides, refusals, symmetry off).
Changed because Extrude is now declared (each states the old pin): `test_app_lab_fail_closed.py` (`test_t_fc1_…six_unwired_commands` → five, and the helper
`refused_by_the_row` spares the declared Extrude), `test_app_lab_symmetric_knife.py` (the BLOCK allow-list includes the declared Extrude), and `_app_lab_support.declare`
(an `extrude=` argument; the "nothing declared" state empties the new table too). Two parametrised T-FC1 cases (`[Extrude]`) left the refused set, hence 450 + 18 − 2 = 466.
Full runs, once, at the end: `tests` 2232 passed / 41 skipped / 68 subtests, Lab 466 passed / 4 skipped (baseline on the same container 2145 / 41 and 450 / 4).

### 11.7 Not decided here / Was Manu entscheidet (Deutsch)

- Verdikt über den symmetrischen Extrude (Praxistest im Lab-README, Slice 7): KEEP / ITERATE / REJECT / UNKNOWN. Ist die Mittelkante an der Naht so, wie du sie
  erwartest (M)? Ist die Auswahl danach (Deckel auf der Seite, auf der du gearbeitet hast) so gewünscht? Beides ist eine Arbeitsregel, noch nicht dein Verdikt.
- Case 4 (Ecke an der Mitte, Fläche über der Mitte): **abgelehnt, vorerst** (deine Aussage vom 2026-10-09). Offen bleibt, ob später der Deckel an so einer Ecke einen
  eigenen Punkt pro Komponente bekommen soll (F-1) — nicht entschieden.
- Texte der Ablehnungen, Arbeitsseiten-Regel (Auswahl-Mehrheit, Gleichstand → Seite der Ebenennormalen).
