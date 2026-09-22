# AD-017 — Additional Artist Semantics (input for review)

**Status:** ARCHIVED INPUT — Artist statement, verbatim. Do not edit to match later decisions (AGENTS.md §6).
**Date:** 2026-09-22
**Author:** Manu (Artist / Project Owner)
**Relates to:** `AD-017-CUT-ENGINE-CONTEXTUAL-C.md` (PROPOSED)

---

AD-017 — Additional Artist Semantics for Independent Review

Purpose

Review the proposed AD-017 independently against the following additional Artist observations.

These are Artist observations / intended interaction semantics, not implementation decisions.

Do not implement anything.
Do not turn open questions into decisions.
Do not assume the proposed "one Cut Engine" architecture is correct merely because the interaction is unified from the Artist's perspective.

The review should determine whether the proposed architecture can support these semantics cleanly without creating a universal operator full of special cases.

---

1. Core Artist Model: C is contextual

The intended UX is inspired by Silo:

| Current context | "C" |
|---|---|
| 1 selected edge | Split edge |
| 2+ selected edges | Connect selected edges |
| 2+ selected vertices | Connect selected vertices |
| Nothing selected | Enter Knife/Cut interaction |

The important Artist concept is:

> One fast contextual key, rather than separate mental tools for every topology operation.

This does not mean that Split, Connect, and Knife must have identical semantics.
It means they may share underlying topology infrastructure.

---

2. Knife is an interactive path operation

The Knife case should be understood as an explicit, step-by-step path.

Example:

1. Enter Knife with no selection.
2. Click Vertex A.
3. A becomes the current Knife start point.
4. Hover over an edge.
5. The viewport previews:
   - the prospective split position on the edge,
   - the new vertex,
   - the connection from A to that point.
6. Click the edge.
7. A new Vertex B is created at the hovered position.
8. B is connected to A.
9. B automatically becomes the new Knife start point.
10. The Artist can continue:
    - B → existing Vertex C
    - B → another Edge D
    - B → another Edge E
11. Each accepted edge hit creates the new point and advances the current start point.

Conceptually:

```text
A → Edge B

becomes:

A ─── B
     ↑
 current Knife start

Then:

B → Edge C

becomes:

A ─── B ─── C
             ↑
         current start
```

This is intentionally different from Vertex Connect.

---

3. Knife Edge hits must not default to midpoint

A Knife edge hit should normally preserve the actual hovered position:

Edge + mouse position → EdgePoint(edge, t)

"t" is therefore a meaningful geometric value.

Midpoint snapping can be a later modifier behavior.

Example future behavior:

- normal Knife: free position along edge
- Shift held: snap preview to edge midpoint

This is only a semantic direction, not a request to implement Shift now.

Review question:

> Does this strengthen the case for a primitive/API capable of representing "split_edge(edge, t)"?

---

4. Edge ↔ Vertex belongs to Knife, not Connect

The Artist's earlier Edge ↔ Vertex idea refers to the Knife interaction.

It should NOT be interpreted as a new "mixed Connect" mode.

Examples:

Vertex → Edge
Edge → Vertex
Edge → Vertex → Edge
Vertex → Edge → Vertex

are all natural Knife paths.

The Knife explicitly expresses the desired topology path, so it does not need Connect to infer that path from a selection.

---

5. Connect Vertices and selection persistence

Artist intent for Vertex Connect:

Select A + B → C

creates:

A ─── B

After the operation:

- A and B remain selected.
- Selection does NOT automatically switch to Edge mode.
- The newly created edge does not replace the vertex selection.

This enables incremental construction.

Example:

A + B → C creates A-B.

Then add C to the existing vertex selection:

A + B + C → C

The existing A-B connection remains.
The system creates the missing local connection(s).

For the simple sequential case this results in:

A ─── B ─── C

This allows the Artist to progressively build topology without repeatedly rebuilding the selection.

---

6. Important distinction: Connect does not express an explicit path

If A, B, and C are selected simultaneously, a purely selection-based Connect may reasonably interpret that as a set of vertices to connect according to its local Connect rules.

The Artist does NOT currently want selection-order semantics to solve this.

For example:

A + B + C

may produce a local triangular connection according to the Connect rules.

If the Artist explicitly wants:

A → B → C

the intended tool is Knife:

Knife: A → B → C

Therefore:

> Do not add ordered vertex selection merely to make Vertex Connect behave like a path tool.

This is an open/future possibility, not a V1 requirement.

---

7. Connect Edges has different post-operation selection semantics

For Edge Connect:

Edge A + Edge B → C

the newly created connecting edge should become selected.

This differs intentionally from Vertex Connect.

The post-operation selection is therefore part of Artist interaction semantics, not an accidental consequence of implementation.

Initial intended behavior:

| C action | Post-operation selection |
|---|---|
| Edge Connect | new connecting edge selected |
| Vertex Connect | original vertices remain selected |
| Knife | newly created point becomes current Knife start |

Split selection behavior is still open.

---

8. Selection is not one universal post-operation policy

Do not assume:

> "Every topology operation selects its newly created geometry."

The Artist wants selection behavior to support the next likely modeling action.

Selection semantics therefore need to be treated as operation/context-specific.

This should be reviewed as part of AD-017 / implementation planning rather than left to implementation accident.

---

9. Proposed conceptual boundary

A useful working hypothesis is:

Connect — Selection expresses the intent.

```text
selected topology
        ↓
local Connect semantics
```

Connect should remain deterministic and selection-based.

Knife — The Artist explicitly expresses the path.

```text
click → preview → click → preview → click
```

Knife should not need increasingly complex inference rules to guess the Artist's intended path.

---

10. Review the "One Cut Engine" proposal against this distinction

The important architectural question is therefore NOT:

> "Can all four operations technically be implemented using the same functions?"

That is already largely demonstrated.

The important question is:

> "Can a shared topology-point / connection engine support these different interaction semantics cleanly, while keeping Split, Connect, and Knife as distinct Artist modes?"

A promising conceptual boundary would be something like:

```text
Artist interaction modes
        │
        ├── Split
        ├── Edge Connect
        ├── Vertex Connect
        └── Knife
                │
                ↓
       shared topology-point /
       split + connect infrastructure
                │
                ↓
              Core
```

The shared layer should remain small and compositional.

Avoid creating a universal "CutEngine" containing numerous context-specific branches.

---

11. Questions for the independent review

1. Does the proposed CutEngine remain a clean shared mechanism, or does it risk becoming a universal topology operator?
2. Does the distinction between Connect (selection-driven) and Knife (explicit path-driven) remain clear?
3. Does the proposed "CutPoint = VertexPoint | EdgePoint(edge, t)" abstraction fit these semantics?
4. Does Knife's arbitrary edge position strengthen the case for "split_edge(edge, t)" in Core?
5. Are the different post-operation selection rules architecturally clean?
6. Is keeping ordered selection out of V1 the correct simplification given that Knife already provides explicit path control?
7. Are there hidden conflicts between the current per-face Connect semantics and the proposed Vertex Connect behavior?
8. What additional edge cases must be tested before AD-017 can become DECIDED?
9. Which parts are genuine Artist/product decisions and which are merely implementation choices?
10. Is "One Cut Engine" actually the right architectural name/concept, or should the shared mechanism be framed more narrowly as topology-point resolution / split-and-connect infrastructure?

---

Review constraints

- Do not implement.
- Do not modify Core.
- Do not modify production behavior.
- Do not convert the above observations into decisions.
- Preserve the existing Playground/Discovery architecture.
- Distinguish clearly between: Artist statement · observed evidence · architectural interpretation · recommendation · unresolved product question

The goal is an independent architecture review before AD-017 is discussed or decided.
