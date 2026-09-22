# AD-017 — Review 001 (Author Review — NOT independent)

**Status:** ARCHIVED REVIEW — do not edit to match later decisions (AGENTS.md §6).
**Date:** 2026-09-22
**Reviewer:** Claude — **the same agent that wrote AD-017.**
**Input:** `AD-017-CUT-ENGINE-CONTEXTUAL-C.md` (PROPOSED), `AD-017_ARTIST_SEMANTICS_2026-09-22.md`
**Code state:** `main` @ `01ea6f9` + Connect Lab changes (not yet merged)

> **Independence notice.** The Development System (§6) requires generation and evaluation to be
> separate where independent judgement is needed. This review is written by the author of the
> proposal and therefore is **not** the independent review AD-017 §9 asks for. It is archived as an
> author review: useful for its evidence and its self-criticism, but likely biased towards the
> proposal's framing. A genuinely independent review should receive AD-017 and the Artist semantics
> document — **not this review**, to avoid anchoring.

Labels: **[ARTIST]** Artist statement · **[EVIDENCE]** observed / tested · **[INTERP]** architectural
interpretation · **[REC]** recommendation · **[OPEN]** unresolved product question.

---

## Summary

1. The proposal's *mechanism* holds; its *framing* does not. "One Cut Engine" with a `CutPath` that is
   "either an ordered list (knife) or per-face groups (connect)" already contains two modes inside one
   operator — the seed of the universal operator the Artist warns against. **[INTERP]**
2. The shared layer should shrink to two helpers — *resolve a point* and *connect two vertices in their
   shared face* — with Split, Edge Connect, Vertex Connect and Knife as separate small modes that own
   their pairing rules, rejection policy and post-operation selection. **[REC]**
3. There is a real conflict between the per-face cyclic pairing rule and incremental Vertex Connect with
   persistent selection: depending on geometry it adds an unintended diagonal. **[EVIDENCE]**
4. The Artist's knife semantics (geometry created *at each click*) contradict the implementation plan's
   assumption "whole cut = one history entry, cancel leaves the mesh unchanged". **[EVIDENCE of conflict]**
5. Arbitrary knife positions strengthen the case for `split_edge(edge, t)` in Core, but do not make it
   functionally necessary. **[INTERP]**

---

## Q1 — Clean shared mechanism or universal operator?

- **[EVIDENCE]** AD-017 §5 defines `CutPath = ordered list of CutPoints (knife) or per-face point groups (connect)`
  and one `apply()`. That is two input models behind one entry point.
- **[ARTIST]** Pairing, rejection and residue differ per mode (semantics §5–§8).
- **[INTERP]** If all of these live in `apply()`, every new rule becomes a branch there. The risk is real,
  and it grows exactly where the Artist is still deciding things.
- **[REC]** Shared layer = only what is genuinely identical in all modes:
  - `resolve(point) → VertexId` — `VertexPoint` returns the vertex; `EdgePoint(edge, t)` splits at t.
  - `connect_in_shared_face(a, b) → EdgeId | None` — find the face containing both, skip adjacent,
    reject degenerate; never touches selection or history.
  - Everything else (which pairs, when to reject, what to select afterwards, history granularity)
    belongs to the mode.

## Q2 — Connect (selection-driven) vs. Knife (path-driven)

- **[INTERP]** The distinction is clear in the Artist semantics and consistent with AD-017 B3
  (cross-face paths → Knife). It is **blurred** in AD-017 §3 ("all four contexts are the same
  operation"). That sentence describes shared *mechanics*, but reads as shared *semantics*.
- **[REC]** Reword AD-017 §3 to "shared infrastructure, distinct modes"; keep B3.

## Q3 — Does `CutPoint = VertexPoint | EdgePoint(edge, t)` fit?

- **[INTERP]** As a *value type* it fits all four modes: Split = one `EdgePoint(t=0.5)`, Edge Connect =
  `EdgePoint(t=0.5)` per selected edge, Vertex Connect = `VertexPoint`s, Knife = click results.
- **[INTERP]** `CutPath` does **not** fit as a shared concept — only the Knife has a path.
- Caveats that must be specified, not assumed:
  - **EdgePoint identity after splitting.** `split_edge` invalidates the original `EdgeId` **[EVIDENCE: Core
    docstring]**. Resolving several `EdgePoint`s on the same edge in one batch breaks unless later points
    are re-mapped onto the halves with renormalised t. Incremental Knife (resolve per click) avoids this;
    any future "multi-cut on one edge" does not.
  - **t direction.** t must be defined against `edge_vertices()[0]`, and picking must compute it against
    the same endpoint.
  - **t near 0 or 1.** Needs an endpoint threshold that turns the hit into a `VertexPoint`, otherwise tiny
    degenerate edges are created.
  - **Perspective.** Screen-space t ≠ 3D t (already noted in WP-AP-CUT Phase 3).

## Q4 — Does the arbitrary knife position strengthen `split_edge(edge, t)`?

- **[EVIDENCE]** Functionally unnecessary: `split_edge` + `set_vertex_position` produces the same topology
  (`experiments/topology/knife_composition_probe.py`).
- **[INTERP]** It strengthens the case in three ways:
  1. With the Knife, non-midpoint splits become the **normal** case, not an exception.
  2. The Core contract of `split_edge` states "splits at the midpoint". After the tool moves the vertex,
     the documented contract no longer describes the result.
  3. The rigging experiment already relies on midpoint matching as a fallback (FINDINGS-3C, 3C-2, MEDIUM
     reliability). With arbitrary t that fallback fails completely; only the operation-context path
     (caller knows edge and t) remains.
- **[REC]** Point 3 is the strongest argument and satisfies the freeze rule's "concrete requirement"
  better than convenience. Still a Core change → **Artist decision** (AD-017 B1).

## Q5 — Are the different post-operation selection rules architecturally clean?

- **[EVIDENCE]** Current playground: Edge Connect clears the selection and selects the new edges
  (`window.py`, Connect branch) — already matches the Artist's intended rule. Split clears the selection.
- **[EVIDENCE]** Technical constraints agree with the Artist's table:
  - Edge Connect: the selected edges are **destroyed** by the split, so keeping them is impossible; a new
    selection is required anyway.
  - Vertex Connect: `connect_vertices` keeps all `VertexId`s **[EVIDENCE: Core docstring]**, so keeping the
    vertices selected is valid.
  - Split: the edge is destroyed; "keep" is impossible — the remaining choices are new vertex, both
    halves, or nothing.
- **[INTERP]** Clean **if** residue is owned by the mode, and the shared helpers only *return* created
  elements. It becomes unclean if the helpers write the selection.
- **[REC]** The Knife's "current start point" should be **knife tool state**, not the Core `Selection`.
- **[OPEN]** Split residue · what is selected when the Knife ends · whether Vertex Connect stays in vertex
  mode even if the Artist was in edge mode before (mode switch rules).

## Q6 — Keep ordered selection out of V1?

- **[EVIDENCE]** `src/core/selection.py` stores sets. Order would be a Core change.
- **[INTERP]** Correct simplification: the Knife provides explicit order. Adding order to Selection to make
  Vertex Connect path-like would duplicate the Knife's job.
- **Caveat:** see Q7 — part of the incremental-construction wish can only be fulfilled with some notion of
  "what was added last", which is order by another name. Keeping order out therefore means accepting the
  Q7 limitation or choosing a different pairing rule.

## Q7 — Hidden conflicts between per-face Connect and the intended Vertex Connect

**Tested** (`experiments/topology/vertex_connect_incremental_probe.py`, hexagon face v0…v5, same per-face
rule as `connect_per_face.py`: cyclic boundary order, adjacent pairs skipped):

| Sequence | New edges | Matches "A─B─C"? |
|---|---|---|
| A=v0 + B=v3 | A-B | ✓ |
| then + C=v5 | B-C | ✓ |
| A=v0 + B=v3, then + C=v4 | **A-C** | ✗ B-C already exists as a boundary edge; the rule adds a diagonal the Artist did not ask for |
| simultaneous A+B+C (v0, v3, v5) | A-B, B-C | chain, not triangle |
| simultaneous A+B+C (v0, v2, v4) | A-B, B-C, A-C | triangle (inner face) |
| repeat A+B after A-B exists | none | ✓ idempotent |

Findings:

1. **Geometry-dependent results.** Whether the result is a chain or a triangle depends on where the
   vertices sit on the face boundary, not on the Artist's intent. **[EVIDENCE]**
2. **Persistent selection amplifies this.** Because the vertices stay selected (Artist rule), each further
   C re-evaluates the *whole* growing selection. Connections among "old" vertices can appear later,
   unasked (row 3). **[INTERP]**
3. **Rejection policy conflict.** `connect_per_face.py` rejects the whole operation if any point would stay
   unconnected. With a growing vertex selection, a single stray vertex would block every further C.
   For Vertex Connect, "ignore unconnectable vertices" (or no-op with a hint) is likely needed — a
   **different** policy from Edge Connect, where points are created and must be used. **[INTERP]**
4. **Coupling risk.** If Edge Connect is implemented *as* "midpoints + Vertex Connect" (the Wings
   structure, AD-017 §3), any change to Vertex Connect's pairing rule for incremental work silently
   changes Edge Connect — which the Artist has just marked KEEP. **[INTERP]**

- **[REC]** Give Edge Connect and Vertex Connect separate pairing functions; share only
  `connect_in_shared_face`.
- **[OPEN]** Which pairing rule Vertex Connect should use:
  - cyclic per face (Wings; triangle possible, row 3 behaviour),
  - pairs only (connect only when exactly 2 selected vertices share a face),
  - open chain in boundary order (no wrap-around),
  - or accept row 3 and use the Knife for precise paths.
  Needs a playable comparison, not a decision in a document.

## Q8 — Edge cases to test before AD-017 can become DECIDED

Mechanics (agent can test headless):
- Knife: first click on an edge (no start yet) → pure split at t, point becomes start.
- Knife: next point on the same edge as the start / on an edge incident to the start vertex → adjacent →
  reject.
- Knife: target shares no face with the start → reject with visible preview state.
- Knife: two vertices sharing two faces (after earlier cuts) → which face is split; must be deterministic.
- Knife: segment through a **concave** face (topologically valid, geometrically outside the face).
- t at 0 / 1 / within threshold of an endpoint; t direction vs. `edge_vertices()` order.
- Several `EdgePoint`s on one edge in a batch (if any mode ever does this).
- Boundary edges (1 face) and non-manifold edges (> 2 faces).
- Vertex Connect: idempotence, stray vertices, growing selection (Q7 rows), vertices sharing no face.
- Contextual dispatch: selection in vertex mode vs. edge mode vs. mixed sets; empty selection in face mode.
- Residue: IDs in the selection are valid after every mode (no stale IDs).
- Undo/redo per mode; history granularity for the Knife (see below).

Interaction (needs the Artist):
- Knife history granularity — see next section.
- Pressing C again while the Knife is active.
- Leaving the Knife: key, click, or mode switch.

## Conflict with the implementation plan (WP-AP-CUT)

- **[ARTIST]** Semantics §2, steps 7–8: clicking an edge *creates* vertex B and *connects* it to A.
- **[EVIDENCE]** WP-AP-CUT Phase 3 assumes "whole cut = one history entry; cancel leaves mesh and history
  unchanged".
- These are different models:
  - (a) each click mutates the mesh and is its own undo step — Ctrl+Z inside the Knife removes the last
    segment naturally;
  - (b) each click mutates live, but the session is grouped into one history entry; cancel reverts all;
  - (c) nothing mutates until finish; clicks only build a preview path.
- **[INTERP]** The Artist's wording fits (a) or (b); (c) contradicts it.
- **[OPEN]** Product decision. The plan must not pre-empt it.

## Q9 — Artist decisions vs. implementation choices

| Question | Owner |
|---|---|
| C meaning per context | **Artist** (stated) |
| Post-operation selection per mode (incl. Split, Knife exit) | **Artist** |
| Vertex Connect pairing rule (Q7) | **Artist**, after a playable comparison |
| Knife history granularity (a/b/c) | **Artist** |
| Knife finish / cancel / remove-last bindings | **Artist** |
| Midpoint snapping modifier (later) | **Artist** |
| Core `split_edge(t)` (B1), interior points (B2), `add_edge()` (B4) | **Artist** (Core boundary) |
| Endpoint threshold for t, perspective-correct t, visibility filtering | Implementation |
| Deterministic face choice when two faces qualify | Implementation (must be documented) |
| Shared helper boundaries, module layout, test fixtures | Implementation |

## Q10 — Is "One Cut Engine" the right concept and name?

- **[INTERP]** No. "Engine" suggests one operator that knows all modes. The mechanism that is actually
  shared is narrow: point resolution plus face-local connection.
- **[REC]** Frame it as **topology-point resolution and face-local connect helpers**, and rename AD-017
  accordingly (for example "Contextual C: distinct topology modes on shared split/connect helpers").
  A rename is a wording change, but it prevents the universal-operator drift the Artist warned about.

---

## Recommended changes to AD-017 before discussion (not applied)

1. Reframe §3 and §5: shared helpers, distinct modes; drop `CutPath` as a shared concept.
2. Add the Artist's residue table as Artist statements; add Split residue as open.
3. Add Q7 as an explicit open question with the tested evidence.
4. Add Knife history granularity as an open product question and remove the assumption from WP-AP-CUT.
5. Strengthen B1 with the Q4 argument (rigging fallback fails for t ≠ 0.5).

These are recommendations only. AD-017's content is left unchanged by this review; only a list of
archived review documents was added to its §9.
