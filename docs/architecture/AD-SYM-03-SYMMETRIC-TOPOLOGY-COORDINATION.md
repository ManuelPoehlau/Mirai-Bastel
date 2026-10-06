# AD-SYM-03 — Symmetric Topology Coordination

**Status:** PROPOSED (not decided; independent review pending, §9)
**Date:** 2026-10-06
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
| Dissolve {seam, opp} expanded (plane-spanning face) | valid / valid | 7/8 / 35/36 | **0** / 0 | **1** / 1 |

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

### 1.4 Verdicts this AD may rely on (as recorded, nothing more)

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
Connect, not only Split).

### 2.2 Transaction seam — both sides as exactly one Undo step (scope item 2; N3/N4, Disc. Q3)

| | Alternative | Assessment |
|---|---|---|
| T-a | **Behaviour-preserving split** of each topology function into a pure `apply_*(mesh, …) -> result` (mutation only; raises on refusal; caller restores) and the existing wrapper (snapshot → `apply_*` → restore on error → push one `MeshStateCommand`). The coordinator calls `apply_*` inside **one** transaction it owns | No `src/core` change. Edge Connect already has `_apply`. Wrappers keep their signatures and tests (Playground and `tests/` callers unchanged). Makes the commit boundary explicit and single per intent. Cost: four small refactors in `src/mirai/topology/` |
| T-b | **History-less scene stand-in:** the coordinator passes a scene-like object whose `history` swallows pushes, calls the unchanged wrappers, then pushes one outer command | Works with zero op change (the wrappers only use `scene.mesh` and `scene.history.push`). **Not used because** it relies on an unwritten duck-typing contract ("op functions touch nothing but `mesh` and `history.push`"; `KnifeTool` also writes the selection it is given), keeps two commit boundaries (inner fake, outer real) — the ambiguity AGENTS §5 asks to avoid — and pays two extra `export_state()` per inner call |
| T-c | **History-level grouping / merge** of consecutive `MeshStateCommand`s (e.g. `begin_group`/`end_group`, or merging before-of-first with after-of-last) in `HistoryStack` | Needs a `src/core` change. **Not used because** `HistoryStack` is frozen Core whose contract says "kein Merge", AD-SYM-02 §3 item 2 decided `HistoryStack` is not changed, AD-SYM-02 §2.1 forbids the counterpart as a second history entry (a group is two entries glued), and `Application`'s selection mirror stack is 1:1 with pushes and would need group awareness too. The need is solvable above Core (T-a), so the freeze rule's step 2 already fails (CORE_V1_FREEZE §7) |
| T-c′ | Composite `Command` in `src/mirai` holding several `MeshStateCommand`s, pushed once | No Core change (`Command` is a Protocol). **Not used because** the inner ops still push themselves, so it needs T-a or T-b anyway, and then a single `MeshStateCommand` (before of the first, after of the last) already does the job |
| T-d | Let the op push, then amend the pushed command's `after_state` with the coordinator's post-op work (snap, seam update) | **Not used because** `HistoryStack` exposes no top-of-stack access (only a private list of a frozen Core class) and a rejected post-check could not take the entry back without consuming the redo branch |
| T-e | Use `Application.apply_mesh_change` as the outer transaction | Its steps are exactly the needed ones, but it is the external-host entry (H3), raises while an interaction owns the keys, and records the selection mirror before a residue can be set. **Not used as is**; its steps are reused (§3, item 3) |

**Where the commit boundary lives afterwards (AGENTS §5).** Under T-a: for selection ops the boundary moves from
inside the topology function to **the caller that owns the intent** — `Application`'s command handler (one
transaction per key press). The wrappers stay as the boundary for their other callers (Playground, tests). No op
function pushes on behalf of another caller. For the Knife the boundary is unchanged (`KnifeTool._on_commit`).

**Selection mirror stack.** Preserved by keeping its one invariant: one `_record_selection_history(before)` per
push, with `before` taken before the transaction and the residue set before recording (as `_connect_command`
does today).

### 2.3 Completeness signal (scope item 3; N7, Disc. Q2)

| | Alternative | Assessment |
|---|---|---|
| C-a | `symmetry_state` grows a face-level component (face w/o partner ⇒ `PARTIAL`) | Makes the visible state honest about one-sided topology (Disc. §1.7 (b), probe I). But changes the meaning of `VALID` for every current consumer (Lab HUD/markers, Re-Symmetrize, `tests/test_symmetric_*`, Lab characterisation tables) in the same step that introduces coordination, and still misses dead seam ids and plane-spanning faces (probe F: Dissolve seam edge → faces w/o partner 0, `sides` 1) |
| C-b | **Separate derived report** (no stored state): faces without partner, edges without partner, dead seam ids, self-mirrored (plane-spanning) faces, seam components (`sides`) | Covers every one-sided case seen so far: face-level check for Disc. §1.7 and probe I, dead ids and `sides` for probe F. `SymmetryState` contract untouched |
| C-c | Reuse the Lab's `topological_pairing` | **Not used as the completeness check because** it is blind to one-sided Delete (Disc. §1.7) and is a Lab experiment (Lab README: "keine Capability") |

How the coordinator uses it — **absolute vs. delta.** Partial symmetry is legitimate (INV-10). A check "result must
be VALID" would refuse every op on a partial mesh (e.g. `man_with_shoes_basemesh`, 54 unpaired from OBJ rounding,
Lab README E4). Only a **delta** check ("nothing complete before is incomplete after; every created element is
paired") follows INV-10 and still catches a one-sided result.

### 2.4 Exactness (scope item 4; N5, Disc. Q7)

**Correction to Disc. §1.7 / §4 (scope):** the Discovery probed plane x=0 only. "t=0.5 midpoints are exact" (Edge
Connect class B, Knife t=0.5) holds for planes with an axis normal and `plane_point[axis] == 0` — exactly Lab E1 —
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
  - G-2 a data-only extension of `CommandGate` (refusal keyed by resolved context), checked by `Application`
    in `_connect_command` after `resolve_c_context` — small `src` change, still no callback;
  - G-3 `Application` itself refuses unsupported contexts whenever a definition is set — **not used because** it
    writes the Lab verdict KEEP-BLOCK into Production behaviour without a promotion (M3; AD-SYM-02 §4 note: "dieses
    Dokument entscheidet dadurch nichts für Production") and removes the Lab's MARK comparison;
  - G-4 the Lab resolves the context itself (pure `resolve_c_context` on `app.selection`, read-only per H2-R4)
    immediately before forwarding `C` and installs the matching row — no `src` change, same pure function on both
    sides.
- **Fail-open vs. fail-closed.** Today's BLOCK row is a block-list (fail-open: a new command runs one-sided until
  someone adds it). The preview row is already an allow-list for exactly this reason (H2 F7). A BLOCK row of the
  form "allowed = non-operation commands (display, selection, mode, undo/redo, cancel, constraints) ∪ operations
  with a declaration" fails closed: an omission is refused visibly, never silently one-sided (INV-8).

### 2.6 Seam maintenance (scope item 6; N6)

**Unambiguous, mechanical:** a seam edge that a coordinated op **splits** is replaced by its two halves in the same
transaction (old Lab Knife P1; probe F: Edge Connect with a seam edge and Split of a seam edge both `valid`, 2
sides, only with this rule). Under T-a the new definition is written inside the transaction, so Undo restores it
through `MeshStateCommand` (the case AD-SYM-01 §1.1 measured). A seam edge's partner is itself, so expansion must
deduplicate (probe F: counted once) — the edge is split once.

**Not unambiguous (Disc. Q1, class D) — options listed, not decided:**

| Case | Observation | Options |
|---|---|---|
| Delete a seam edge / seam vertex | seam id dead; `state` valid (F, Disc.); `sides` 2 (F, seam edge) | R refuse · D drop the dead ids (declaration follows the mesh; `state`/`sides` unchanged in every probed case) · V keep the dead ids and show the seam as broken |
| Delete a symmetric face **pair** at the seam (no seam element selected) | the seam edge between them dies by DD-1 (F) | as above — notable because the user never selected the seam |
| Dissolve a seam edge (+ partners) | plane-spanning face, `sides` 1, face check blind (F, Disc.) | R refuse · V allow, visibly invalid (no seam between the halves any more) · an Artist-declared new seam (Re-declare) |
| Extrude touching the seam (Playground only) | old seam edge dies, cap edge undeclared (Disc. §1.6) | R refuse · M move the seam to the cap edge (Wings pattern, R2 §3.2) · V visibly invalid |
| Knife path along / across the seam | old Lab Knife refused seam-to-seam chords (Lab README) | R refuse (old Lab) · a defined self-mirror cut (Design Brief §5 "Connect … genau einmal") |

These are Product Truth questions (what should the Artist get), prepared as Artist test **A1** (§6).

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
   - selection expansion per mode with "explicit selection wins" (as `mirrored_selection`) and seam
     self-partners counted once;
   - an exact-plane predicate (axis unit normal, `plane_point[axis] == 0`);
   - mirrored-position snap (`mirror_position(source)`);
   - seam rule S1 (split → halves) as a pure function returning a new `SymmetryDefinition`;
   - the completeness report (C-b) and its delta check.
   The per-operation coordinators (thin: expand → `apply_*` → snap → seam rule → delta check) and the declaration
   mapping (D-b) live together in one place above `mirai.topology`; the Knife's coordination runs inside
   `KnifeTool._on_commit` and has its entry in the same mapping. Exact module layout is implementation.
3. **Transaction seam: T-a.** Each topology function is split, behaviour-preserving, into `apply_*` + the existing
   wrapper. The commit boundary for a key press moves to `Application`'s handler, through one private transaction
   helper that shares its steps with `apply_mesh_change` (snapshot, restore on raise, no change → no entry, one
   `MeshStateCommand`, mirror entry after the residue, pick cache, viewport, hover). Knife: boundary unchanged.
   `src/core` is not changed; T-b, T-c, T-c′, T-d are not used (reasons in §2.2).
4. **Created-element report (N5), smallest form:** `apply_*` returns what it created tied to its source where a
   coordinator needs it — Split: `(new_vertex, half_a, half_b)` (exists); Edge Connect: source edge → midpoint
   vertex (today dropped in `_apply`); Knife: pid → created vertex (later, with the Knife slice). Needed for seam
   rule S1 when a seam edge is in a Connect selection (probe F), not for exactness on E1 planes.
5. **Completeness: C-b.** A separate derived report; coordinators run its **delta** check inside the transaction
   and roll back with a visible status on failure (the `SeamConstraintError` precedent: refused, no history, mesh
   unchanged). `SymmetryState` is not changed by this AD.
6. **Exactness:** every coordinated mirror vertex is snapped to `mirror_position(source)` (X-a). Symmetric topology
   coordination is claimed exact only on exact planes (predicate in item 2; Lab E1). On any other plane a coordinator
   refuses visibly instead of producing a result the tolerance-free correspondence may not confirm (INV-5). Edge
   Connect stays class B on exact planes (snap is a no-op there); it would need N5 for the snap on other planes.
7. **Declaration: D-b,** fail-closed. Undeclared operation ⇒ unsupported ⇒ refused under BLOCK (KEEP-BLOCK
   semantics unchanged). The Lab's BLOCK row becomes derived: allowed = non-operation commands ∪ operations whose
   coordinator exists (plus transforms with `Operation.supports_symmetry`). For `C` the row is derived from the
   **resolved context**: proposal **G-4** for the Lab phase (no `src` gate change), which lifts one AD-013 H2 Limit
   of G and therefore needs a dated H2 amendment and its review (H2-R6) before code. G-2 is the fallback if the
   review rejects Lab-side context resolution. Selection-dependent limits inside a supported operation (seam
   cases pending A1, non-exact plane) are **runtime refusals** of the coordinator, not gate rows.
8. **Seam rule S1 (split → halves) is adopted** for every coordinated op that splits a seam edge. All seam-consuming
   cases (§2.6 table) stay undecided until A1.

---

## 4. Deliberately NOT decided

- **Seam consumption** (Delete/Dissolve/Extrude/Knife on or across the seam; the face-pair delete): Artist test A1.
- **`C` with a two-sided explicit selection** — canonicalise to one side first, or keep literal counting: Artist
  test A2. (Missing from the Discovery.) Until decided, coordinators expand after the unchanged
  `resolve_c_context`.
- **Whether `SymmetryState` later folds in the face-level component** (C-a). The evidence (Disc. §1.7 (b), probe I)
  says the visible state is currently blind to one-sided topology; whether the Lab HUD shows the report next to the
  state is UX.
- **Knife tie-break equivariance:** mirror-aware tie-breaking in `knife_resolve` (a Knife-owned change, AD-017)
  vs. resolving the source and constructing its mirror vs. rejecting through the delta check. Decided in the Knife
  slice, after a wider probe than probe I (only `select_bridge` was exercised).
- **Residue under symmetry:** e.g. after a symmetric Split, only the source vertex or both new vertices selected
  (AD-017 residue table is one-sided). Prepared with slice 4.
- **General (non-exact) planes:** whether they ever get exact coordination (needs a correspondence decision: X-c or
  X-d). No host produces them today.
- **Extrude:** Production port before or after its symmetry work (Disc. Q6, owner priority); `Operation` vs.
  atomic mutation stays open (AD-SYM-02 §4).
- **Owner check O1 — end of the accepted interim.** A fail-closed, declaration-derived BLOCK row refuses
  Delete/Dissolve/DissolveNoCleanup under BLOCK as soon as it exists, unless their coordinators exist. That is
  KEEP-BLOCK applied, but it ends the interim state accepted on 2026-10-06 earlier than "support exists". Owner
  chooses at slice 3: accept the refusal (MARK still runs them one-sided) or keep a dated, visible interim
  exception in the row until slice 5.
- Module and function names, the report's data shape, the index structure, any key binding, HUD text or overlay.

---

## 5. Coupling with AD-SYM-01 / AD-SYM-02 (and AD-013 H2, AD-017) — checked

| Decision | Coupling | Result |
|---|---|---|
| AD-SYM-01 (definition in the mesh, part of `export_state`) | Seam rule S1 writes a new `SymmetryDefinition` inside the transaction | Undo/Redo carry it through `MeshStateCommand` with no new machinery — the case §1.1 there measured. The mesh still knows no semantics: the rule lives above Core. **No change** |
| AD-SYM-02 §2.1 (one instance, one entry) | Topology analogue: one transaction, one `MeshStateCommand` per intent (T-a) | Upheld; T-c rejected for contradicting it |
| AD-SYM-02 §2.2 (`params` channel) | Knife gets its symmetry context through `begin(**params)` | Same channel idea; `OperationContext` unchanged |
| AD-SYM-02 §2.3 (support statement before `begin`) | Extended to non-`Operation` ops as D-b | Upheld; the form question of §4 there is narrowed: static declaration per resolved operation + runtime refusal for selection-dependent limits |
| AD-SYM-02 §2.4 (two mechanics) | M-a confirms selection expansion vs. intent mirroring | Upheld |
| AD-SYM-02 §4 (seam update vs. degrade) | S1 decides the split case; consumption stays open (A1) | Partly answered, rest open |
| AD-013 H2 (gate by command identity; Limits of G) | Context-derived row for `C` (G-4) and a fail-closed BLOCK row | **Needs a dated H2 amendment + review (H2-R6) before code.** H2-R4 already allows reading `selection` |
| AD-017 (no universal Cut Engine; Knife session model) | Coordinators are per mode; Knife keeps its virtual path and commit-time resolver | Upheld. A tie-break change, if chosen, is Knife-owned |
| CORE_V1_FREEZE §7 | No option chosen needs `src/core` | Upheld (T-c recorded as rejected) |
| `WP_DELETE_DISSOLVE_PLAN.md` DD-2 | Answers the mechanics (expansion through `remove_selected`'s `apply_*`); seam consumption → A1; gate consequence → O1 | DD-2 stays open until slice 5 |

**Order:** this AD needs AD-SYM-01/02 as they are; the H2 amendment is a precondition of slice 3 only.

---

## 6. Artist tests (prepared, not answered)

Both run in the Symmetry Lab: `python experiments/symmetry_lab/run.py head_basemesh`, then **Shift+S** → `X`.
Answer options as given; `UNKNOWN` is valid.

### A1 — Seam consumption (≤ 5 min) — partly runnable today

*Runnable today* because Delete/Dissolve are not in the BLOCK row (accepted interim); what is shown is today's
one-sided Core behaviour, not a coordinated operation.

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

### A2 — `C` with a two-sided explicit selection (≤ 5 min) — observation runnable today, comparison after slice 4

1. **Shift+B** → `E5-Modus: MARK` (under BLOCK `C` is refused). **2** (Edge mode). Click an edge on +X,
   Shift+click its mirror edge on −X (turquoise markers show partners only in Vertex mode; pick by eye). **C**.
   *Expected observation:* status `Keine verbindbaren Kanten: ausgewählte Kanten teilen sich keine Face.`, nothing
   changes (context Edge Connect, the two edges share no face).
2. Vertex analogue: **1**, a vertex and its turquoise partner, **C** → today Vertex Connect, nothing connectable.

Question: with both sides selected and symmetry on, what did you mean?
- **A** count mirror pairs once ("1 edge" → symmetric Split; "1 vertex pair" → no C meaning);
- **B** count literally (2 edges → Edge Connect; it connects only where the two edges share a face, e.g. a face
  spanning the plane);
- **C** refuse with a hint ("beide Seiten gewählt — eine Seite wählen");
- **UNKNOWN**.

*Not yet runnable:* the A/B comparison as behaviour (needs symmetric Split, slice 4, and a Lab switch between A and
B). Note for B: the only case where literal counting does something today is a face spanning the plane — the
situation A1 case 2 creates.

---

## 7. Proposed slice cut for the following Type-A package

Based on Disc. §5.4; changes marked **[Δ]** with their evidence. Each slice keeps `pytest tests`,
`pytest experiments/symmetry_lab/tests` and `pytest playground/tests` green, runs the Symmetry Lab tests for
`application.py` changes (CLAUDE.md), and touches no `src/core`.

| # | Slice | Content | Evidence / note |
|---|---|---|---|
| 1 | **Services, tested, not wired** | Edge/face partners (indexed), expansion (explicit wins, seam self once), exact-plane predicate, snap, seam rule S1, completeness report + delta check; `src/mirai/`, tests in `tests/` | Disc. §5.4 step 1. **[Δ]** + exact-plane predicate (G), + `sides`/dead ids/self-mirrored faces in the report (F), + delta form (INV-10) |
| 2 | **Transaction seam** | `apply_*` split of Split, Edge Connect, Vertex Connect, `remove_selected`; Edge Connect returns edge → midpoint; `Application` handlers use one private transaction helper shared with `apply_mesh_change`. Pure refactor, existing tests unchanged | Disc. step 2; T-a. **[Δ]** + the N5 midpoint report (F) and the shared helper (T-e) |
| 3 | **Edge + Vertex Connect through `C` (Lab)** | Expansion after `resolve_c_context`, seam edges in the selection via S1, snap, delta check with rollback; declaration-derived, fail-closed BLOCK row with the context-derived `C` row (G-4). Exact planes only | Disc. step 3. **[Δ]** seam edges supported here, not deferred (F); precondition: AD-013 H2 amendment reviewed; owner check O1 |
| 4 | **Split** | Source + partner edge in one transaction (seam edge once + S1), snap; residue question prepared; A2 comparison becomes runnable | Disc. step 4 |
| 5 | **Delete / Dissolve** | Expansion through `apply_remove`; seam consumption per A1 verdict; DD-2 closed | Disc. step 5; blocked on A1 |
| 6 | **Knife** | Symmetry context at `begin`, mirror records before resolution, pid → vertex report, snap, S1, seam-chord rule, mirrored preview (INV-11), **tie-break equivariance** | Disc. step 6. **[Δ]** tie-break is a known defect now (probe I), not only an untested risk |
| 7 | **Extrude** | After a Production port (owner, Disc. Q6) | Disc. step 7 |

The order of operations is unchanged from the Discovery; the changes move work between slices (seam rule into
slice 3, the midpoint report into slice 2) and add preconditions.

---

## 8. Consequences (if decided)

- **Positive:** one commit boundary per intent, visible in one place per path; no Core change; declarations cannot
  drift from implementations; a new mutating command is refused under BLOCK until it is coordinated, never silently
  one-sided; one-sided results are detected even where `symmetry_state` is blind (Disc. §1.7 (b), probe I).
- **Costs:** four refactors in `src/mirai/topology/` (behaviour-preserving), a new services module, an AD-013 H2
  amendment, and an extra face index per coordinated op. Coordinated ops are refused on non-exact planes until a
  correspondence decision exists.
- **Risk:** the fail-closed row changes what the Lab refuses (O1). Mitigated by naming it as an owner check at
  slice 3.

---

## 9. Review

Per AGENTS §6 an independent review should be archived before discussion (e.g.
`docs/archive/symmetry_lab/reviews/AD-SYM-03_REVIEW_CLAUDE_001.md`), then the decision recorded here. None yet.
Points a reviewer should test: T-a vs. T-b (is the duck-typing objection strong enough?), G-4 vs. G-2, the
fail-closed row (O1), and whether the exact-plane restriction is too strict for any planned host.
