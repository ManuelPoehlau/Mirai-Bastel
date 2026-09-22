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
