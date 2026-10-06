# Symmetry × Production Operations — Discovery

**Status:** Discovery / Research (M5). **No architecture decision, no implementation, no ADR.**
**Date:** 2026-10-06 · **Repo state:** branch `ccr-d6af6688-w1ojft` @ `b068b37` (WP Delete/Dissolve DD-1)
**Question:** What do the existing Production operations and the Symmetry system need from each other so that
Symmetry *coordinates* them, instead of growing a `SymmetricX` copy of every tool? (Target milestone, working
title: *Symmetry Basic Modeling Parity* — Transform, Split/Connect/Knife, Extrude, Delete/Dissolve.)
**Evidence rule:** §1–§4 are observations (code read, probe run, tests run). §5 onward are recommendations and
open questions and say so. Code refs are `file:line` at this commit.
**Read first:** `AGENTS.md`, `CLAUDE.md`, `AD-SYM-01`, `AD-SYM-02`, `AD-017`, `AD-013` addendum H2,
`WP_DELETE_DISSOLVE_PLAN.md`, `SYMMETRY_DESIGN_BRIEF.md` (INV-1…13), `SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md`,
`WP-SYM-LAB-03_REBASE_PLAN.md`, `ONE_KNIFE_PROMOTION_DISCOVERY.md`.
**Probe:** [`experiments/topology/symmetry_ops_probe.py`](../../../experiments/topology/symmetry_ops_probe.py)
(read-only, in-memory; `python experiments/topology/symmetry_ops_probe.py`). Its partner helpers are local
stand-ins to ask "is it derivable?", not proposed `src/` code.
**Baseline:** `pytest tests --ignore=tests/test_extrude_tool.py` → 1665 passed, 8 skipped.
`pytest experiments/symmetry_lab/tests` → 311 passed, 4 skipped, 1 failed
(`test_lab_overlays_are_drawn_before_the_app_point_overlay`: `ModuleNotFoundError` in
`src/viewport/gl_line_overlay.py:178` — `pyglet` is not installed in this container; unrelated).

---

## 1. Observations

### 1.1 Current Symmetry architecture

| Piece | Where | Fact |
|---|---|---|
| Definition | `Mesh.symmetry_definition` (`src/core/mesh.py:74`) | Plane (point + unit normal) + `seam_edges: frozenset[EdgeId]`. Part of `export_state()`, so `MeshStateCommand` carries it through Undo/Redo (AD-SYM-01). Core mutations never touch it (`mesh.py` comment above `dissolve_vertex`; `split_edge` has no symmetry code). |
| Correspondence | `mirai/symmetry.py:118` `vertex_correspondence(mesh)` | Derived on every call, no cache, exact float equality, **vertex-only**. States `PAIRED` (+partner) / `SEAM` / `UNPAIRED` / `AMBIGUOUS`. There is **no edge or face partner concept anywhere in `src/`**. |
| Seam | `symmetry.py:99` | A vertex is `SEAM` iff it is an endpoint of a **live** declared seam edge; dead edge ids are silently skipped. The Lab derives the declaration once at Shift+S (`lab_symmetry.derive_seam_edges`, E3). |
| State | `symmetry.py:173` `symmetry_state` | `OFF/VALID/PARTIAL/AMBIGUOUS/VIOLATED`, aggregated from vertex states + "seam vertex off the plane". |
| Partner selection | `symmetry.py:194` `mirrored_selection` | Vertex ids only; explicit selection beats inferred partner. |
| Transform integration | `tools/selection_helpers.py:63` `resolve_symmetry`; `tools/move.py:116`, `tools/transform.py:348-378` | The **Tool** resolves selection → affected = selection ∪ partners + `params["symmetry"]` (`plane_normal`, `mirrored_vertex_ids`, `seam_vertex_ids`, `plane_point`). The Core **Operation**'s existing per-vertex loop applies the mirrored intent (`core/operations/move.py`, `transform.py` `_PivotTransformOperation`). `SeamConstraintError` is caught in `Application._transform_step` (`application.py:1238`). |
| Support declaration | `core/operation.py` `Operation.supports_symmetry` (class attr) | `True` for Move/Rotate/Scale only. Topology ops are **not `Operation`s**, so they have nowhere to declare it. |
| Gate | `application.py:236` `CommandGate`, set by the Lab only | Refuses by **command identity** (AD-013 H2 "Limits of G"). |

**Observation:** symmetric transform logic already lives in Production code (`src/mirai/interaction/tools/`,
`src/core/operations/`). It is dormant only because `src/main.py` never sets a definition; "not promoted" means no
UX/host, not no code.

**Lab-only vs. reusable.** Lab-only (`experiments/symmetry_lab/`): axis cycle and E1/E3 (`lab_symmetry`), the
E5 gate table (`lab_app.py:81-210`), overlays/HUD, Re-Symmetrize (`lab_resymmetrize`), and
`lab_topology.topological_pairing` (edge/face-aware BFS from the seam; used only by Re-Symmetrize today).
Reusable infrastructure already in `src/`: Definition, correspondence/state, `mirrored_selection`, the transform
path above, and the host hooks `command_gate`, `hover_suspended`, `interaction_owner`, `set_status`,
`apply_mesh_change` (`application.py:236,1091,1369`).

**E5 gate today** (`lab_app.py:118`, run by the probe): `BLOCK` refuses exactly `{Connect}`. `Delete`, `Dissolve`,
`DissolveNoCleanup` (and the unwired `Extrude`) are **not** in the table, so under Symmetry+BLOCK they run
one-sided. This is DD-2 in `WP_DELETE_DISSOLVE_PLAN.md:271` (explicitly out of scope); recorded, not changed.
A Knife session already running is never gated (`key_press` routes to `_knife_key` first, `application.py:1124`).

### 1.2 Current operation architecture

```
Input (pyglet key/mouse) ─ BindingSet.command_for ─▶ Command ─▶ Application.key_press / dispatch_command
   ├─ W/E/R ─▶ _transform_arm ─▶ ToolManager ─▶ Move/Rotate/ScaleTool ─▶ Core Operation(begin,update*,commit)
   │                                                   [Symmetry enters HERE: Tool resolves partners/seam,
   │                                                    Operation per-vertex loop mirrors the intent]
   ├─ C ─▶ _connect_command ─▶ resolve_c_context(selection) ─▶ Split | Edge Connect | Vertex Connect | Knife
   │        Split/Connect: topology fn(scene, ids) ─▶ Mesh primitives ─▶ MeshStateCommand pushed INSIDE the fn
   │        Knife: _knife_begin ─▶ KnifeTool session (virtual path) ─▶ Enter ─▶ resolve_cross_face ─▶ Mesh primitives
   ├─ Del/Backspace/Ctrl+Backspace ─▶ _removal_command ─▶ remove_selected ─▶ Mesh.delete_*/dissolve_*
   └─ (Extrude: command constant + Alt+E in TOPOLOGY_CONTEXT only; no Application handler, no routing entry)
   after every mutation: Application._record_selection_history(before) ─▶ _notify_topology_changed (pick cache,
   viewport, hover); Undo/Redo = HistoryStack + Application's parallel selection mirror stack
```

| Op | Command / entry | Topology fn → Core primitive | Commit boundary | Selection result | IDs the fn reports | Composed from lower ops? |
|---|---|---|---|---|---|---|
| Move/Rotate/Scale | W/E/R hold-key | `Operation` per-vertex loop → `set_vertex_position` | `Operation.commit` → `VertexTransformCommand` (start/end positions) | unchanged; mirror entry in `key_release` | none | n/a |
| Split | `C`, 1 edge | `split_selected_edge(scene, edge, t=0.5)` → `Mesh.split_edge` | pushed **inside** fn (`split.py`), `MeshStateCommand("Split Edge")` | new vertex, Vertex mode | `(new_v, edge_a, edge_b)` | no (single primitive) |
| Edge Connect | `C`, 2+ edges | `connect_selected_edges_per_face(scene, set)` → `_apply`: `split_edge` per edge (t=0.5) + `connect_in_shared_face` → `Mesh.connect_vertices` | inside fn, rollback on error | new edges | created edges; midpoint vertices dropped | **yes** (split + connect, inside one fn) |
| Vertex Connect | `C`, 2+ vertices | `connect_vertices_per_face` → `connect_in_shared_face` → `connect_vertices` | inside fn; `[]` ⇒ no entry | unchanged | created edges | yes (connect only) |
| Knife | `C`, empty sel. | `KnifeTool` virtual path → `resolve_cross_face` → `Mesh.split_face/split_edge/connect_vertices`; `check_commit` integrity | inside `KnifeTool._on_commit` (`knife.py:617`), one `MeshStateCommand("Knife")` per session | path edges, Edge mode | `path_edges` (+ internal pid→vertex for interior points only) | **no** (see 1.4) |
| Delete / Dissolve / no-cleanup | Del / Bksp / Ctrl+Bksp | `remove_selected(scene, mode, ids, dissolve, cleanup)` → `Mesh.delete_*/dissolve_*` (vertex dissolve = loop of `dissolve_vertex`, snapshot restore on refusal) | inside fn | cleared; face dissolve selects merged faces | dissolve: new faces; delete: nothing (DD-1 removals are implicit) | no |
| Extrude | **Playground only** (`playground/topology_tools/extrude.py`) | `ExtrudeTool.begin(face_ids)` mutates the mesh **immediately** (`add_vertex/add_face/remove_face`, orphan prune via `load_state`); `update` moves the new vertices; `commit` pushes `MeshStateCommand("Extrude")` | tool `_on_commit` | new cap faces, Face mode | `new_face_ids`; keeps `_old_to_new` vertex map internally | no |

**Correction to the task context:** Extrude is *not* a Production operation. `grep -i extrude src` finds only
`commands.EXTRUDE` and the Alt+E binding. Same for `Collapse`/`EdgeLoop`/`EdgeRing` (constants + bindings,
no Application handler).

**Pattern:** every Production topology op is "snapshot → Core primitive(s) → push `MeshStateCommand`" **inside the
op function**; `Application` only adds selection residue and notifications. Probe D: wrapping
`split_selected_edge` in `Application.apply_mesh_change` (the generic one-entry transaction wrapper) yields
**2 history entries**, not 1 — the commit boundary is inside the op, so a coordinator cannot compose two op calls
into one Undo step today.

**Seam where Symmetry enters today:** only the Tool→Operation `params["symmetry"]` channel (AD-SYM-02 §2.2) for
transforms, plus the command gate. No topology op reads `mesh.symmetry_definition`.

### 1.3 Old mirrored Knife (git `171bb63^`, `experiments/symmetry_lab/lab_knife.py`, 564 lines; not restored)

It was a Lab copy of the **pre-B7** `KnifeTool`: incremental — every click really cut the mesh — with session
undo stack, rollback, one `MeshStateCommand` per session.

| Geometry/topology logic (not symmetry) | Symmetry coordination |
|---|---|
| `connect_in_shared_face` copy returning face + boundary; per-click `split_edge`/`connect_vertices`; step snapshot/rollback; in-session undo/redo | **Partner order (E17):** `intent_pairs` (vertices this session created, INV-6) → seam endpoint = itself (INV-4) → `PAIRED` correspondence → else reject (INV-5) |
| | **Mirror edge** = edge between the partners of the endpoints; mirror split position set via `mirror_position(source)`, **not** a mirrored `t` (P3) |
| | **Mirror connect** in the face whose vertex set is the image of the source face; a self-mirror connection runs once |
| | **Seam maintenance:** splitting a seam edge replaced it by its two halves in `symmetry_definition` in the same step (P1) |
| | **Refusals:** seam-to-seam chord, no partner, no mirror edge/face |
| | **Independent per-step validation** (position, topological pairing, seam/sides) → whole step rolled back; `begin` only at `VALID` + 2 sides |

Dependency: the **engine** was headless and independent of the Lab dispatcher/renderer (it needed `Tool`,
`mirai.symmetry`, `lab_topology`); only Slice 7's window wiring (`lab_dispatch`, `lab_knife_pick`, own preview) was
old-architecture. What blocks reuse is the **interaction model** (real cut per click vs. Production's virtual path
resolved at commit, WP-KNIFE-01 S2–S4), as the plan already says (`WP-SYM-LAB-03_REBASE_PLAN.md` D2, row 29).

**Principles that disappeared with the deletion** (no Production counterpart today; probe rows in 1.7):
1. seam maintenance on split (P1); 2. creation-time pairing of new elements (`intent_pairs`); 3. exact mirrored
position instead of arithmetic on `t` (P3); 4. an independent post-step check that is *topology*-aware. The
findings P1–P3 survive as 12 characterisation tests (`experiments/symmetry_lab/tests/test_lab_knife.py`) and in the Lab README history.

### 1.4 What Knife is today

**Not** a chain of the Split and Connect operations. `KnifeTool` (`knife.py`) keeps an ordered path of explicit
records (`vertex` / `edge`+`t` / `face`+position / `space`, pen-lift and gap breaks) and leaves the mesh untouched;
at commit `resolve_cross_face` (`knife_resolve.py:1152`) cuts it. It shares only **Core primitives**
(`split_edge`, `connect_vertices`, `split_face`) with Split/Connect and imports none of their modules
(`split.py`, `connect_per_face.py`, `connect_vertices_per_face.py`, `topology_points.py`; checked by grep). This is the AD-017
decision "four distinct modes … no universal Cut Engine / generic `CutPath`; shared are only small helpers".
Consequence for this question: the Knife's *path* is the natural unit of intent, not a sequence of Split/Connect
calls.

### 1.5 Delete / Dissolve

Core (`mesh.py:595-799`): `delete_*` return `None`; `dissolve_vertex` returns the new face or `None`;
`dissolve_edges/faces` return new faces. IDs removed are not reported (derivable from before/after or
`is_valid_*`). DD-1: after Delete, face-less edges and edge-less vertices are removed. Symmetry is out of scope
(DD-2); nothing in `Application`/`remove_selected` reads the definition.
What a coordinator would observe on seam elements (probe, 1.7): removing a seam edge/vertex leaves a **dead seam
id** (`seam_edges live/declared` 7/8 etc.) and `symmetry_state` still says `valid`.

### 1.6 Extrude (Playground)

Facts from code and probe: boundary-edge rule means edges between two selected faces get no side wall — so a face
**plus its partner face** (selected across the seam) naturally yields no inner wall on the seam; normals are per
connected component and the drag scalar uses one *global* reference normal (Z fallback when ≈0, `extrude.py`
`_on_begin`); `begin()` creates duplicate vertices at the original positions, so `symmetry_state` is `AMBIGUOUS`
between `begin()` and the first `update()`; the original seam edge dies and nothing declares the new cap edge
between the new seam vertices.

### 1.7 Probe results (both assets: `subd_cube`, `head_basemesh`; plane x=0; same qualitative result)

Columns: `state` = `symmetry_state` (vertex/position-only); `topo` = Lab `topological_pairing` conflicts
(vertex / face-pair); `faces w/o partner` = faces whose vertex-image is not a face (local helper, derived from the
same correspondence); `hist` = history entries. "expanded" = selection ∪ partners passed to the **unchanged** op in
one call. Numbers are `subd_cube` unless a second value is given for `head_basemesh`.

| Case | state | topo | faces w/o partner | hist | Note |
|---|---|---|---|---|---|
| Split non-seam edge, one-sided | partial | 0 / 2 | 4 | 1 | |
| Split + partner split, t=0.5, two calls | valid | 0 / 0 | 0 | **2** | the AR-9 shape |
| Split + partner split, **t=0.37 raw** | **partial** | 0 / 0 | 4 | 2 | P3: partner edge is orientation-reversed ⇒ 1e-16 off ⇒ 2 `UNPAIRED` |
| Split **seam** edge | partial | 0 / 0 | 2 | 1 | seam 7/8 live; new on-plane vertex `UNPAIRED` |
| Edge Connect, one-sided | partial | 28 / 40 (head 328 / 644) | 7 | 1 | |
| Edge Connect, expanded | **valid** | 0 / 0 | 0 | **1** | midpoints at t=0.5 are exact |
| Vertex Connect, one-sided | **valid** | 0 / 2 | 3 | 1 | state blind to it |
| Vertex Connect, expanded | valid | 0 / 0 | 0 | 1 | |
| Delete face, one-sided | **valid** | **0 / 0** | **1** | 1 | **neither `state` nor `topo` notices; only the face-level check does** |
| Delete face, expanded | valid | 0 / 0 | 0 | 1 | seam-touching variant: seam 7/8 live (head 35/36) |
| Dissolve edge, one-sided | partial (head **valid**) | 0 / 3 (head 0 / 2) | 5 (head 3) | 1 | head: `state` blind |
| Dissolve edge, expanded | valid | 0 / 0 | 0 | 1 | |
| Dissolve **seam** edge | valid | 0 / 0 | 0 | 1 | seam 7/8 live; a plane-spanning face; no signal anywhere |
| Dissolve / Delete **seam vertex** | valid | 0 / 0 | 0 | 1 | seam edges 6/8 live; seam vertices 7/8 |
| Knife path, one-sided | partial | 28 / 40 | 7 | 1 | |
| Knife path mirrored **before resolution** (one `resolve_cross_face`; mirrored chain appended after a pen lift), t=0.5 | valid | 0 / 0 | 0 | 1 | `applied 2/2`, topology symmetric |
| same, t=(0.3, 0.6) | **partial** (head valid) | 0 / 0 | 6 (head 0) | 1 | P3 again; topology still symmetric |
| Extrude face, one-sided (Playground tool) | partial | 30 / 0 | 6 | 1 | |
| Extrude face ∪ partner, not touching seam | **valid** | 0 / 0 | 0 | 1 | tool unchanged |
| Extrude face ∪ partner, touching seam | **partial** | 0 / 0 | 6 | 1 | 2 `UNPAIRED` new seam vertices; seam 7/8 live (head 35/36) |
| Extrude, `state` between `begin()` and first `update()` | `AMBIGUOUS` | — | — | — | duplicate vertices at the original positions |
| Partner derivation (A) | — | — | — | — | non-seam edges without vertex-image partner: **0/40** (cube), **0/612** (head); no non-seam self-mirror edge; every face has a unique image face at baseline |

Evidence summary: (a) **selection ∪ partners through the unchanged op already gives one Undo step and a symmetric
result** for Edge Connect, Vertex Connect, Delete, Dissolve and (non-seam) Extrude; (b) three independent
**checks disagree**: only a face-level completeness check saw every one-sided case; (c) every failure that remains
is one of: float exactness of mirrored positions, seam bookkeeping, or two-call history.

---

## 2. Architecture map with Symmetry participation (observation + marked integration candidates)

| Layer | Transforms (today) | Split / Edge+Vertex Connect | Knife | Delete / Dissolve | Extrude |
|---|---|---|---|---|---|
| Input / Command | `Move/Rotate/Scale` | contextual `Connect` (context resolved **from the selection**) | `Connect` + empty selection | `Delete`/`Dissolve`/`DissolveNoCleanup` | none in Production |
| Gate (command identity) | via `supports_symmetry` | `Connect` refused under BLOCK | not gated once running | **not in table (DD-2)** | n/a |
| Tool / session | Tool resolves partners ◀ **Symmetry enters** | none | `KnifeTool` path ◀ *candidate: mirror records* | none | `ExtrudeTool` (Playground) |
| Application | arm/step/commit | `_connect_command` ◀ *candidate: expand after context resolution* | `_knife_*` | `_removal_command` ◀ *candidate: expand* | — |
| Topology fn | — | `split_selected_edge`, `connect_*` (push inside) | `resolve_cross_face` | `remove_selected` (push inside) | tool body |
| Core | `Operation` loop mirrors intent | `split_edge`, `connect_vertices` | `split_face/split_edge/connect_vertices` | `delete_*/dissolve_*` | `add_*`, `remove_face` |
| Undo | `VertexTransformCommand` | `MeshStateCommand` per call | one per session | one per call | one per tool |
| Selection | unchanged | residue | path edges | cleared / merged faces | caps |

---

## 3. Common denominator — what Symmetry needs from an operation (derived from the code and probe, not assumed)

| Need | Evidence it is necessary | Exists today? |
|---|---|---|
| **N1** Selected element ids (input) | Expansion works only because ops already take id sets | Yes (all but Split: single `edge_id`) |
| **N2** Partner resolution for **edges and faces** (and vertices) | Needed to expand/mirror; derivable for 100 % of non-seam edges in both assets | Vertex only (`mirrored_selection`); edge/face only as probe helpers |
| **N3** One commit boundary around both sides | Probe D (2 entries when wrapped), probe B (2 calls = 2 entries), INV-7, AR-9 | **No** — the push lives inside each op fn |
| **N4** A mutation entry that does not push/record | Follows from N3 | Partly: `connect_per_face._apply(mesh, set)` exists; `split.py`, `remove_selected`, `connect_vertices_per_face` inline it |
| **N5** Created-element report tied to the intent that created it | Exact mirrored positions (P3) and seam updates need "which new vertex/edge is the image of which"; Core primitives return ids, ops drop them (Edge Connect drops midpoints; Knife exposes only interior pids and path edges); Extrude keeps `_old_to_new` privately | Partial (Split/Dissolve/Extrude/Core primitives yes; Edge Connect, Knife no) |
| **N6** Seam maintenance rule per op | Split-of-seam, Delete/Dissolve of seam elements and seam-touching Extrude all leave dead/undeclared seam ids | **No** (old Lab Knife did it for split; nothing in `src/`) |
| **N7** A topology-aware completeness check after the op | `symmetry_state` blind to Vertex Connect/Delete/Dissolve; `topological_pairing` blind to Delete; face-level check caught all | Partial (`lab_topology`, Lab-only) |
| **N8** Pre-`begin` support declaration for non-`Operation` ops | INV-8; BLOCK table is hand-written and silently misses new commands (Delete/Dissolve) | **No** (only `Operation.supports_symmetry`) |

Not shown to be necessary: a list of **deleted ids** (validity checks and before/after diff suffice), **operation
intent strings** (`description` exists), **geometric positions from the op** (only a mirrored-position snap, which
the coordinator can compute from the source vertex via `mirror_position`). Two coordination **styles** appear and
match AD-SYM-02 §2.4 ("different mechanics, not prematurely unified"): *selection expansion* (Connect, Delete,
Dissolve, Extrude) and *intent/path mirroring* (Knife, Split `t`). The shared part is N2–N8, not the mechanism.

---

## 4. Classification (relative to today's code)

A = structurally compatible now · B = op unchanged, a coordination layer outside it suffices (given N2/N3/N7/N8) ·
C = needs preparation in the op's result/structure first · D = needs a separate design/decision.

| Operation | Class | Why (evidence) |
|---|---|---|
| Move / Rotate / Scale | **A** | Tool→`params["symmetry"]`→Operation loop; tested in `tests/test_symmetric_*.py`, Lab verdicts KEEP |
| Edge Connect | **B** | Expanded call = 1 entry, symmetric (t=0.5 exact). Untested: seam edges in the selection |
| Vertex Connect | **B** | Same; no new vertices |
| Delete / Dissolve / no-cleanup (non-seam) | **B** | Expanded call = 1 entry, symmetric; only gate/decision DD-2 missing |
| Split | **C** | Single-edge API; push inside; mirrored `t` is inexact (P3); seam edge needs seam update; result must report the new vertex |
| Knife | **C** | Path mirroring through the unchanged resolver is symmetric (probe) — but needs pid→created-vertex report (exactness, P3), seam-chord/crossing refusals, a mirrored preview (INV-11), and resolver mirror-equivariance beyond the two probed cases |
| Extrude | **C** (plus: not in Production) | Needs a Production port first (separate question); then seam move to cap edges, per-vertex exact partner positions (`_old_to_new` ⇒ partner of old), global reference normal under mirrored components, `AMBIGUOUS` window after `begin()` |
| Delete/Dissolve/Knife/Extrude **on or across the seam** (plane-spanning face after Dissolve of a seam edge; path along/over the seam) | **D** | The counterpart of the result is the result itself; "what does it mean" is an Artist/architecture decision (Maya: symmetry off; Wings: silently off; INV-4/INV-5 want "survives or visibly invalid") |
| Collapse / Merge / Weld | not assessed | Core `collapse_edge` exists; no Production command/handler; no probe |

---

## 5. Recommendations (not observations)

### 5.1 Likely common integration point
Not a new tool layer. Two seams, both already present: (1) **`Application` command handlers**
(`_connect_command`, `_removal_command`, later an Extrude handler) for selection-expansion ops — expand *after*
`resolve_c_context` (expanding first would turn 1 edge into 2 and flip Split into Edge Connect), then call the
unchanged op once; (2) **`params["symmetry"]`-style context into session tools** (`KnifeTool`) for path mirroring.
Both depend on a shared services module above Core (next to `mirai/symmetry.py`): partner resolution for
edge/face, expansion with the "explicit selection wins" rule, mirrored-position snap, seam maintenance, the
completeness check.

### 5.2 What is missing (N-list above, ordered by how many ops it unblocks)
N3/N4 transaction seam (all ops) → N2 edge/face partners (all) → N7 face-level completeness check (all) → N8
declaration beyond `Operation` (all; today's BLOCK table silently under-refuses) → N6 seam maintenance (Split,
Delete/Dissolve, Extrude, Knife) → N5 created-element report (Split, Knife, Extrude).

### 5.3 Do not change
`src/core/` primitives (Core freeze; every need above is solvable above Core), the E5 BLOCK/MARK semantics,
DD-1/DD-2 behaviour, the Production renderer, Application's gate semantics (command identity), Knife's session
model (virtual path + commit-time resolver) and AD-017 "no universal Cut Engine", the existing symmetric transform
path, `src/main.py` (no promotion). No `SymmetricKnife/Extrude/Delete/Dissolve`.

### 5.4 Smallest sensible next slice (proposal for review, not a decision)
Evidence favours a different order from the suggested validation set:
1. **Services only, tested, no tool wired:** edge/face partner resolution + expansion, face-level completeness
   check, in `src/mirai/` beside `symmetry.py` (derived, no stored state — INV-3/AR-1). Tests in `tests/`.
2. **Transaction seam:** behaviour-preserving split of each topology fn into a pure `apply_*` mutation and the
   existing snapshot+push wrapper (Edge Connect already has `_apply`). Existing tests must stay green unchanged.
3. **Prove with Edge Connect and Vertex Connect through `C`** (cheapest, no new vertices beyond t=0.5 midpoints),
   one Undo step, gate row derived from a declaration instead of a hand list.
4. **Split** (adds N5/N6 in its smallest form: exact mirrored position + seam update for a seam edge).
5. **Delete/Dissolve** — mechanically ready (B), but only after the DD-2/seam-removal question below is answered.
6. **Knife** — as the test of *path/intent* coordination (mirror records → one resolve → exactness snap →
   validation), after 1–4; it is not a Split+Connect chain, so it validates the second style, not a composite of the first.
7. **Extrude** — after a Production port exists; seam move and normals are its own work.

### 5.5 Open questions (owner in brackets)
1. What should happen when Delete/Dissolve/Extrude remove or consume seam elements: refuse, move the seam, or
   degrade to a visibly invalid state? (Artist + architecture; DD-2, INV-4/5, AD-SYM-02 §4 "seam update vs.
   degrade" is explicitly open.)
2. Is `symmetry_state` allowed to grow a topology-aware completeness component, or is it a separate report?
   (Architecture; touches the `SymmetryState` contract.)
3. Is a behaviour-preserving split of the four topology fns into `apply_*`/wrapper acceptable, or should the
   coordinator use a history-less scene stand-in? (Architecture; small, but it changes where the commit boundary
   lives — AGENTS §5.)
4. Mirror-equivariance of `resolve_cross_face` for tie-breaks by position (`knife_resolve` module docstring,
   "ties are broken by position") is untested beyond two edge-to-edge paths. (Probe before Knife.)
5. Edge Connect/Delete selections that contain seam edges: untested (probe used non-seam selections only).
6. Whether Extrude is promoted to Production before or after its symmetry work. (Owner.)
7. Exactness with a **tolerance-free** correspondence (E4, AR-1): every mirrored creation must go through
   `mirror_position`; is a post-op snap acceptable as the standard mechanism? (Architecture.)
