# AD-017 — Final Artist Decisions (archived input)

**Status:** ARCHIVED INPUT — Artist statement. Do not edit to match later changes (AGENTS.md §6).
**Date:** 2026-09-22
**Author:** Manu (Artist / Project Owner)
**Recorded in:** `AD-017-CUT-ENGINE-CONTEXTUAL-C.md` → "Decision"
**Consistency check + implementation brief:** `docs/design/artist_playground/WP-AP-CUT_PLAN.md`

---

Summary of the Artist's decision document (full wording was given in chat on 2026-09-22; the
decision content below is complete, only the request/meta paragraphs addressed to the reviewer
are omitted):

1. **Contextual C — DECIDED.** 1 edge → Split · 2+ edges → Edge Connect · 2+ vertices → Vertex Connect ·
   no selection → Knife. Distinct Artist modes; they may share small helpers; **no universal
   "Cut Engine" / generic `CutPath`.**
2. **Mode ownership — DECIDED.** Split, Edge Connect, Vertex Connect (selection-driven), Knife
   (explicit interactive path). Edge↔Vertex connection is Knife behaviour, not a mixed Connect mode.
   Connect must not become an increasingly intelligent path/selection interpreter.
3. **Vertex Connect — DECIDED.** Wings-like per-face cyclic pairing. Evidence: in Silo, all six
   vertices of a hexagon + Connect gave a chaotic result, not a useful implicit path. No ordered-path
   inference, no ordered selection in V1, no "extend the last connection" rule. Precise ordered
   chains → Knife. Exact pairing implementation = implementation concern.
4. **Edge Connect — DECIDED.** Wings-like per-face semantics; strip semantics are not revived.
   Afterwards the newly created connecting edge is selected. Selection residue is mode-specific;
   no universal "always select new geometry" rule.
5. **Vertex Connect selection — DECIDED.** The selected vertices remain selected in Vertex mode.
6. **Knife — DECIDED interaction model.** Explicit incremental path: start from a clicked/selected
   vertex; hovering an edge gives a cut target; clicking an edge creates a vertex at the actual hovered
   position; that vertex becomes the current start; continue Vertex→Vertex, Vertex→Edge, Edge→Edge
   via the new vertex. **Open (Artist: probably the most important open question):** component modes /
   face mode — in Silo the knife can cut directly inside a face, and hover highlight and cutting work
   on vertices, edges and faces identically in every component mode.
7. **Knife position `t` — DECIDED.** Not midpoint-restricted; arbitrary position along the edge. A
   future midpoint-snap modifier is not part of the current requirement.
8. **Knife history — DECIDED.** During a session each click creates the next cut; Undo removes only
   the most recent cut; Esc/Cancel discards the whole session and restores the pre-session mesh.
   Commit turns the whole session into **one** history operation; after commit, Undo removes the whole
   session. **Commit via Enter or clicking outside the mesh.**
9. **Knife preview / mouse interaction — OPEN UX.** Hover-only highlight vs. vertex preview timing,
   mouse-down slide, drag-slide, cursor/preview presentation (Silo and 3ds Max are references).
   Expose the capability; do not hardcode an invented final UX.
10. **Split — DECIDED.** After Split the newly created vertex is selected.
11. **Shared technical infrastructure.** Small, mode-agnostic helpers (resolve vertex / edge+t, split at
    t, connect two vertices via a valid shared face, return created elements). Modes own pairing,
    rejection, interaction state, selection residue, knife session state and history semantics.
12. **Core `split_edge(t)`.** Implementation decision: evaluate extending the Core split primitive with
    `t`; preserve Core contracts and provenance requirements.
13. **`add_edge()` — DECIDED.** Do not remove or repurpose it; deprecate or retain per evidence; no
    unrelated cleanup in AD-017.
14. **Scope boundary.** No input-system redesign, no HUD redesign, no invented final Knife UX, no
    ordered selection, no Loop Insert redesign, no silent changes to unrelated tools, no production
    architecture changes beyond the required shared topology support, strip Connect not revived.
    Reuse validated infrastructure.

---

## Addendum — Answers to the brief's open questions (same day, after the implementation brief)

**D-S — Split residue: CONFIRMED.** After Split: switch to Vertex mode, select the newly created vertex.
The literal reading implemented in the brief (§1.3) is correct as-is.

**Knife residue after commit: DECIDED.** After a committed Knife session, the newly created edge path
is selected — i.e. the connecting edges created between consecutive points during the session (not the
leftover halves of split edges, and not the session's vertices). Selection mode switches to Edge, mirroring
Edge Connect's existing residue rule.

All other open questions in the brief (§7) remain open; per the Artist, they surface through testing
rather than being decided in advance.

---

## Addendum 2026-09-30 (Artist: F2) — geometry-aware shared face choice for chords

**2026-09-30 (Artist: F2):** the shared face choice of `connect_in_shared_face` and Edge Connect is
geometry-aware; modes' pairing/rejection rules unchanged; bug fix against decided behaviour, not a new
mode behaviour.

Detail (agent-recorded, not an Artist question):

- **Rule:** a chord is never created through a face in which it does not lie entirely. Among the shared
  faces where the two vertices are non-adjacent, the lowest-id face *in which the chord is valid* is used;
  none qualifies → the helper returns `None`, exactly as it already did for "no shared face".
- **Validity** (`mirai.topology.chord_validity`, one predicate, in the face's best-fit plane): both child
  polygons are simple, have an area above 1e-9 of the parent's and the parent's winding. This covers R3
  (chord along the boundary: zero-area child, an edge in four faces) and R5 (chord leaves a concave face:
  flipped, overlapping or non-simple children).
- **Ownership (AD-017 unchanged):** the helper still knows nothing about pairing, residue or rejection.
  Each mode keeps its own reaction to "no valid face": Vertex Connect skips the pair (nothing created → no-op,
  no history entry); Edge Connect leaves the midpoint unconnected → whole operation rejected, mesh restored,
  `TopologyToolError`; Knife refuses the click (`accepts()` and `click()` agree, the mesh is untouched).
  `KnifeTool.hover()` keeps its documented looseness. Edge Connect's former inline copy of the face search
  is gone — it calls the helper.
- **Not changed:** Core, `Split`, the Knife session model, History behaviour, `playground/` code. The
  Playground Lab keeps its own predicate for now (the One-Knife slice S1 will make the `src` one the single
  implementation).

---

## Addendum 2026-10-01 (Artist: K1) — B2c chosen: `Mesh.split_face`

**2026-10-01 — K1 / B2c chosen (Artist): `Mesh.split_face`; B5 satisfied; K0 not chosen.** Manu chose K1 over the
planned K0 after the comparison in chat (`docs/research/topology/ONE_KNIFE_PROMOTION_DISCOVERY.md` §3). M1 (promote
the KEEP'd Q5 model in slices) stays the migration path; this addendum covers only the Core primitive (WP-KNIFE-00).
The Knife, the Lab and the resolver are the next package (WP-KNIFE-01 S1, which calls `Mesh.split_face` instead of
`remove_face` + `add_vertex` + `add_face`).

- **B5 satisfied:** the cut engine still mutates the mesh only through `split_edge` / `connect_vertices` and — now
  chosen — B2c. No face surgery in the tool layer.
- **K0 not chosen, because** a primitive that knows the parent face, the path and both sides is the natural
  provenance hook (ARCH-02) and keeps AD-017 B5 and the V1_SPEC mutation-layer principle intact, where K0 would
  have amended B5 to allow face surgery in the tool.

**Freeze rule (`CORE_V1_FREEZE.md` §7), step by step:**

| Step | Result |
|---|---|
| 1 Concrete requirement | Q5 face constructions, Artist KEEP (2026-09-30) + the One Knife requirement (one Knife in Production, not two engines). |
| 2 Solvable with the public API? | Yes, via `remove_face` + `add_vertex` + `add_face` (B2b) — but that contradicts AD-017 B5 and the mutation-layer principle (`ONE_KNIFE_PROMOTION_DISCOVERY.md` §3). |
| 3 Problem documented | `ONE_KNIFE_PROMOTION_DISCOVERY.md` §3 and `docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md` §3 (both archived). |
| 4 Smallest extension | One additive primitive, `Mesh.split_face`. `connect_vertices`, `split_edge`, `add_face`, `add_edge` unchanged. |
| 5 Tests / contract | Contract below; contract tests `tests/test_core.py` (`test_split_face_*`); equivalence against the Lab stand-ins `playground/tests/test_split_face_equivalence.py`. |
| 6 Change | After 1–5: commit "Core: Mesh.split_face (WP-KNIFE-00 K1)". |

**Accepted contract** (the B2c sketch of `KNIFE_FACE_CUT_DISCOVERY.md` §3, refined only where marked *pinned*;
the method docstring in `src/core/mesh.py` restates it, this addendum is the decision record):

```text
Mesh.split_face(face_id, v_a, v_b, positions: Sequence[Position] = ())
    -> tuple[list[VertexId], list[EdgeId], FaceId, FaceId]     # (new vertices, new edges, face_1, face_2)
```

- **Preconditions.** Face valid; `v_a != v_b`, both on the face boundary; both resulting faces ≥ 3 vertices. With
  `positions == ()` adjacent ends are rejected (as `connect_vertices`); with ≥ 1 position they are allowed (notch,
  FC3/FC4). *Pinned:* a face whose boundary repeats a vertex is rejected (`add_face` accepts one, H7); every
  position must have 3 coordinates; with `positions == ()`, an existing edge `v_a`–`v_b` that already borders
  another face is rejected — `connect_vertices` would give that edge 3 or 4 faces. Any violation → `MeshError`,
  and the mesh is unchanged, **allocator counters included** (everything is validated before the first mutation).
- **`positions == ()` ≡ `connect_vertices`:** same faces, same boundaries (same start vertex), same ids, same
  `export_state()` — on every input `connect_vertices` accepts, except the rejected edge-already-has-a-face case
  above. An existing *free* edge `v_a`–`v_b` is reused, as `connect_vertices` does (then no new EdgeId).
- **Path.** `positions` are the k interior points in order `v_a → v_b`; k new vertices at exactly these positions.
- **ID continuity (AD-001).** `face_id` invalid; k new VertexIds in path order; k + 1 new EdgeIds in path order
  `v_a → v_b`; two new FaceIds, `face_1` allocated before `face_2`; boundary vertices and all boundary edges keep
  their IDs; no edge is removed; monotonic, no reuse.
- **Face order — *pinned*.** Let `s` be the end with the lower index in `face_vertices(face_id)`, `e` the other.
  `face_1` = boundary `s … e` forward, then back along the path `e → s`; `face_2` = boundary `e … s` forward
  (through the end of the list), then along the path `s → e`. For `v_a` before `v_b` this is the sketch's
  "side running `v_a → v_b` in boundary order"; for `v_b` before `v_a` it is the same swap `connect_vertices`
  makes. Consequence: both faces and their order do not depend on the argument order — only the path's vertex
  and edge ids follow `v_a → v_b`.
- **Winding.** Both faces run like the parent face (each path edge is traversed once in each direction).
- **Edge endpoint order** (`edge_vertices`) is not semantic (as everywhere in `Mesh`); the path edges are
  stored the way `face_1` traverses them, which is what makes `positions == ()` bit-identical.
- **Not included:** geometric checks (path inside the face, self-crossing, flipped children — tool/F2), dangling
  ends, holes, auto-bridging (tool policy), cross-face (the tool composes per face), a closed ring (`v_a == v_b`),
  a new `Operation` class (the Knife uses `MeshStateCommand` snapshots), any change to the existing primitives.
- **Provenance hook only (ARCH-02):** input + return value expose the parent face, the new vertices with their
  creation positions, the path edges and both sides. No registry, no framework.
- **Symmetry:** `symmetry_definition` is not touched; a face split creates no seam edge and removes no edge, so
  seam ids stay valid.

**Open points (recorded, not decided):**

- whether a single call taking two paths, or a closed ring (`v_a == v_b`), is ever worth adding — not now;
- whether a later provenance layer wants the interior vertex's "parent corner data at creation time" passed in —
  hook only;
- the two-call constructions (closed shape, loop at a point) burn one intermediate FaceId compared to the Lab's
  3-way split — expected, not "fixed"; S1's golden net compares position-canonical results.

**Sufficiency result (WP-KNIFE-00, 2026-10-01, agent-recorded):** `playground/tests/test_split_face_equivalence.py`
compares `Mesh.split_face` against the Lab stand-ins as an oracle (position-canonical faces, winding kept) on the
grid, the cube (folds) and the head (non-planar quads: the 6 least planar plus every 40th, 15 in all). FC1–FC4
(incl. reversed arguments) are one call each and allocate exactly the Lab's ids; the closed shape (FC6, 2 bridges;
square either way round, triangle either way round, pentagon) and the loop at a point (every corner, both click
directions) are two calls each and give the Lab's faces with the same vertex and edge ids and **one FaceId more**
(the intermediate face of call 1, burned per AD-001). No case needed more than these calls; the Lab refused none.
Which piece hosts call 2 is the caller's choice, by winding (the inner face runs like the parent) — resolver policy
for S1, not Core. Cost on `head` is negligible (two calls 0.08 ms vs the Lab's 3-way split 0.28 ms, this machine).
No new open question from this check.

---

## Addendum 2026-10-01 (Manu: M1 + K1, "K1 zuerst") — One Knife S1: resolver home

**2026-10-01 / One Knife S1 (M1 + K1):** the Knife-owned resolver lives in `src/mirai/topology/` and builds faces only
through `Mesh.split_face`, `split_edge`, `connect_vertices`; whole-session rollback via `export_state`/`load_state`;
resolver stays Knife-owned (AD-017 #1).

Manu's statement (2026-10-01): "K1 zuerst" — M1 (promote the KEEP'd Q5 model in slices) with K1 (`Mesh.split_face`,
addendum above) first. Work package: WP-KNIFE-01 S1, draft spec in `docs/research/topology/ONE_KNIFE_PROMOTION_DISCOVERY.md`
§6.3; intake line in `docs/architecture/ROADMAP.md` (WP-06 intake log).
