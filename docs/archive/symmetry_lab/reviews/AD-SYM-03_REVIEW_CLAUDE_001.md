# Independent Review — AD-SYM-03 "Symmetric Topology Coordination" (PROPOSED)

> **Reviewer:** Claude (claude.ai/code, fresh session, no prior chat or plan context)
> **Review ID:** CLAUDE-001
> **Target path:** `docs/archive/symmetry_lab/reviews/AD-SYM-03_REVIEW_CLAUDE_001.md`
> **Repository state reviewed:** `main` @ `276dbe4` (2026-10-07)
> **Subject:** `docs/architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md` (PROPOSED, 2026-10-06)
> **Type / Mode:** Type B (review only) · Discovery · no source, plan or AD edited
> **Status:** Archived first-pass review — preserved verbatim
>
> This document is intentionally preserved as the original independent review. Do not edit it to
> reflect later decisions. Answers to the findings belong in the AD's §9 "Review".

---

## What was read, what was run

Read: AD-SYM-03 (whole file); `AGENTS.md` §1–§7; `src/core/history.py`; `src/core/mesh.py:300-320`
(`split_edge`); `src/mirai/symmetry.py`; `src/mirai/topology/{split,connect_per_face,
connect_vertices_per_face,delete_dissolve,contextual_c}.py`; `src/mirai/topology/knife.py:612-645`
(`_on_commit`); `src/mirai/topology/knife_resolve.py:155-200` (`select_bridge`);
`src/mirai/application.py` (`CommandGate`, `dispatch_command`, `_connect_command`,
`_removal_command`, `key_press`, `_transform_step`, `_undo_redo`/`_apply_undo_redo`,
`apply_mesh_change`, selection mirror stack, `_knife_begin`); `src/mirai/interaction/commands.py`
(constants); AD-013 addendum H2 (§ Limits of G, H2-R1…R6, Review table);
`experiments/symmetry_lab/lab_app.py` (gate rows, `sync_gate`, `lab_key_press`),
`lab_symmetry.py` (`definition_for_axis`, `current_axis`), `lab_topology.py` (`topological_sides`);
`SYMMETRY_DESIGN_BRIEF.md` INV-5…INV-13; both probes (`symmetry_ops_probe.py`,
`symmetry_coordination_probe.py`).
**Not read in full:** the Discovery document (its numbers are taken from the AD as cited),
AD-SYM-01/02 beyond what the AD quotes, AD-017, `WP_DELETE_DISSOLVE_PLAN.md`.

Run:

- `python experiments/topology/symmetry_coordination_probe.py` — reproduces every row of the AD's
  §1.3 tables F, G, H, I on both assets (numbers identical).
- Baseline: `pytest tests --ignore=tests/test_extrude_tool.py` → 1665 passed, 8 skipped;
  `pytest experiments/symmetry_lab/tests` → 311 passed, 4 skipped, 1 failed
  (`test_lab_overlays_are_drawn_before_the_app_point_overlay`, `pyglet` not installed). Same as the
  AD's §1.3 baseline.
- One throwaway review probe (R1–R5, in-memory, code and output in the appendix). Every
  "VERIFIED (probe Rn)" below can be reproduced from it.

Claims not checked in code or by a probe are marked **UNVERIFIED**.

---

## Verdict

**ACCEPT THE DIRECTION, WITH CHANGES BEFORE DECIDED. No architectural blocker.**

The core choices are right and well argued: coordination instead of `SymmetricX` copies (M-a),
the behaviour-preserving `apply_*` split as the transaction seam (T-a), a separate derived
completeness report instead of changing `SymmetryState` (C-b), a declaration that *is* the
coordinator (D-b), a fail-closed BLOCK row, and no `src/core` change. Every code fact in §1.2 that I
checked is correct (table at the end).

What is not ready is the **completeness check that every coordinator relies on (item 5)** and one
**slice dependency**:

- **F1:** the delta rule "every created element is paired" refuses every coordinated op that touches
  an unpaired region. On `man_with_shoes_basemesh` that is 202 of 926 faces (probe R2). The AD says
  this rule "follows INV-10"; it does for asymmetry *elsewhere* in the mesh, not for edits *in* the
  asymmetric region (INV-10, INV-13). This is a product choice and should be named as one.
- **F2:** `sides` as a delta signal refuses legitimate symmetric operations. Deleting a symmetric
  face ring changes it from 2 to 4 with nothing one-sided (probe R3).
- **F3:** "selection ∪ partners in one call" is symmetric, but it is **not** the mirror of the intent
  when the selection and its image meet in one face. Per-face pairing then connects across the plane
  (probe R1: 4 chords, 2 crossing the plane, vs. 2 chords).
- **F4:** slice 5 is listed as "blocked on A1", but item 7 already makes seam cases runtime refusals
  pending A1. Non-seam Delete/Dissolve can therefore land with slice 3, which shrinks owner check O1
  to the seam cases. This changes when A1 must be run.

---

## Answers to the AD's §9 questions

### T-a vs. T-b — is the duck-typing objection strong enough?

**T-a. Yes, but the objection is weaker than the decision needs. Two other reasons carry it.**

- The cited part of the duck-typing objection ("`KnifeTool` also writes the selection it is given")
  is beside the point. The Knife is not in T-b's scope, because §2.2 keeps the Knife's commit
  boundary unchanged. For the selection ops, T-b's contract would hold today: the four wrappers touch
  only `scene.mesh` and `scene.history.push` (VERIFIED, code: `split.py`, `connect_per_face.py`,
  `connect_vertices_per_face.py`, `delete_dissolve.py`).
- The arguments that carry T-a are (1) two commit boundaries per intent (inner fake, outer real),
  which is exactly the ambiguity AGENTS §5 names, and (2) T-a is cheaper than §8 says. Split's
  `apply_*` is `Mesh.split_edge` itself, and Edge Connect already has `_apply`. Only
  `connect_vertices_per_face` and `remove_selected` really need splitting (VERIFIED, code). "Four
  refactors" should read "two refactors plus one return-value change (`_apply` → midpoints)".
- One detail to carry into slice 2: two wrappers signal "nothing happened" by returning a value, not
  by raising. Vertex Connect returns `[]` and `remove_selected` returns `None`. `Application` turns
  these into specific status lines ("Vertex Connect: nothing connectable", "…: nothing to do"). The
  shared helper's "no change → no entry" must not swallow those texts. Existing tests should catch
  this (UNVERIFIED which ones).

### G-4 vs. G-2

**Prefer G-2.** Both need the same H2 amendment and review (both lift the "part of the selection"
Limit of G), so G-4's only advantage is "no `src` gate change". Slice 3 changes `Application`'s
handlers anyway, so that saves little. Against G-4:

1. **It resolves the context twice.** The Lab and `Application` each call `resolve_c_context` on
   `app.selection`. The two results agree today only because events are serialised and the Lab
   resolves immediately before forwarding (VERIFIED, `lab_key_press`). That is a correctness argument
   about timing, not about structure.
2. **It changes what a gate row is.** Today a row is a pure function of Lab state, re-derived after
   each key event (H2-R2), and the table is static and printed at start-up (H2-R3). Under G-4 the row
   for `C` depends on the current selection and is installed per key press.
3. **It leaves a stale row during a Knife session.** When the forwarded `C` starts a Knife session,
   `sync_gate` skips while `interaction_owner == "knife"` (VERIFIED, `lab_app.py:325-338`), so the
   per-press row stays installed for the session. This is harmless, because the gate is not consulted
   inside the Knife, but neither the H2 tests nor the AD anticipate this state.

G-2 as a data field such as `refused_contexts: Mapping[CContext, str]`, checked in `_connect_command`
right after its own `resolve_c_context`, keeps one resolution and keeps the table static and
printable per Lab state. `CContext` is already a public enum (`mirai.topology.contextual_c`).

### The fail-closed row (O1)

**Fail-closed is right.** `commands.py` already declares mutating commands that `Application` does
not handle yet: `SplitEdge`, `Collapse`, `LoopInsert`, `LoopSlide`, `Extrude`, `ArticulationRestore`
(VERIFIED, code). These are exactly the commands a block-list would let run one-sided as soon as they
are wired. Two points for the row:

- The allow-list must contain the click commands (`Select`, `SelectAdd`, `SelectRemove`,
  `SelectToggle`), because `_execute_click` consults the same gate. It must also contain
  `ClearSelection`. Otherwise BLOCK makes selecting impossible. The AD says "selection"; the slice-3
  test should name these commands.
- The "non-operation commands" set is itself a hand list (the D-c pattern). Fail-closed makes an
  omission visible rather than silent, which is the property that matters, so this is acceptable.

On O1 itself, see **F4**: most of the owner check goes away if non-seam Delete/Dissolve is
coordinated by the time the row is installed.

### Is the exact-plane restriction too strict for a planned host?

**No.** The only code that sets a `SymmetryDefinition` outside tests and probes is the Lab
(VERIFIED, grep). The Lab's `current_axis` already raises on any definition that is not E1
(`lab_symmetry.py:74-87`). Production `src/main.py` sets none. The only route to another plane is a
loaded `export_state` (the plane is serialised, `mesh.py:1106`), and a visible refusal is the right
answer there. Two notes:

- The predicate should read "±unit axis normal". `(−1,0,0)` through the origin is exact as well
  (probe R4: 0 failures in 100 000) and is a valid `SymmetryDefinition`.
- Transforms are not refused on non-exact planes. That asymmetry is out of this AD's scope but should
  be listed under §4.

---

## Findings

Severity: **SHOULD** = resolve in the text before DECIDED; **NIT** = wording or slice detail.

### F1 — The delta rule refuses all coordinated work in unpaired regions (SHOULD)

§2.3 and item 5: "nothing complete before is incomplete after; every created element is paired".

**Evidence (probe R2):** `man_with_shoes_basemesh` on X is `partial` with 54 unpaired vertices, and
202 of 926 faces touch at least one of them. I took a quad touching an unpaired vertex, selected two
opposite edges and expanded them (union = 3, because one edge has a partner and one does not), then
ran Edge Connect. It created 2 new vertices, and both are not `PAIRED`. The partner edge was dropped
by Connect's own rule ("drop edges whose faces contain no other selected edge"), so even the midpoint
of the *paired* edge ends up one-sided. The strict rule refuses this.

So with symmetry on, an Artist on this asset cannot Split/Connect/Delete next to any of the 54
vertices. INV-10 ("unpaired elements are allowed … not treated as symmetric") and INV-13 ("break
symmetry without fighting the system") point the other way, and INV-5 ("mirrors correctly *or
recognisably not at all*") allows a visible one-sided result.

**Options to name in §2.3:**

- **(a) strict, as written:** refuse. This is safe and simple, but it blocks modelling in partial
  regions. The way out is to turn symmetry off (Shift+S), which is the same remedy transforms have
  today.
- **(b) source-aware:** created elements whose sources are all paired must be paired. Other created
  elements are allowed and reported visibly ("n elements without a partner — one-sided"). This needs
  provenance per op (N5 for Connect/Split; for Delete there is nothing created).

Either is defensible. The AD should record which one it takes and why, and could add it as Artist
test A3, because it is Product Truth in the same sense as A1/A2. The AD should also say that the
delta is computed **by element id**: surviving ids must not become incomplete, and new ids are
judged by the chosen rule. Split and Connect replace faces, so "complete before" cannot be compared by
count.

### F2 — `sides` gives false refusals as a delta signal (SHOULD)

C-b lists "seam components (`sides`)" and item 5 runs "its delta check".

**Evidence (probe R3):** deleting a horizontal face ring that is closed under the partner map
changes `sides` from 2 to 4 on both assets (8 faces on `subd_cube`, 56 on `head_basemesh`). In both
cases `state` stays `valid` and there are 0 faces without a partner. `topological_sides` counts face
components that do not cross a declared seam edge (`lab_topology.py:186-221`). Any symmetric cut
through a side raises that count, so it measures connectivity, not symmetry.

The case `sides` was brought in for (probe F: Dissolve of a seam edge → 1 component) is already
covered by another field of the same report, the **self-mirrored (plane-spanning) faces**, which go
from 0 to 1 there. **Suggestion:** keep `sides` as a display value if it is useful, but leave it out
of the delta check. Let the delta use self-mirrored faces (new ones refused pending A1) and dead seam
ids.

### F3 — Union call ≠ mirror of the intent when both sides meet in one face (SHOULD)

M-a style (1) passes "selection ∪ partners" to the unchanged op in one call. Disc. §1.7 (a) shows
that this gives a *symmetric* result. INV-6 asks for more: the other side is the **mirror image of
the intent**.

**Evidence (probe R1):** I dissolved one seam edge, which merges two quads into one hexagon spanning
the plane. I then selected two +X edges of that hexagon and ran Edge Connect two ways:

| | chords created | chords crossing the plane | faces w/o partner |
|---|---|---|---|
| (a) one call on selection ∪ partners | 4 (`subd_cube`) / 3 (`head_basemesh`) | 2 / 1 | 0 / 0 |
| (b) op on selection, then op on its mirror | 2 / 2 | 0 / 0 | 0 / 0 |

Both results are symmetric, but they differ. In (a), Connect's per-face cyclic pairing sees four
midpoints on one face and builds an inner polygon across the plane. Vertex Connect pairs per face the
same way (`_pairs_for_face`), so it behaves alike (UNVERIFIED by probe, same code shape).

Today this only arises in faces that span the plane, i.e. after seam consumption (A1 case 2) or on an
asset that has such faces. It is not a reason to abandon M-a, but the AD should:

- state that style (1) equals "intent + mirrored intent" only when no face receives selected elements
  of both a selection and its image (or a self-mirrored face);
- decide what happens otherwise: refuse visibly, or accept the joint result. This belongs with A1/A2,
  because option B of A2 ("literal counting … a face spanning the plane") is exactly this case.

The delta check does not catch this: the result is symmetric, and that is what the check verifies.

### F4 — Slice 5 is not blocked on A1; O1 shrinks (SHOULD)

Item 7 says: "Selection-dependent limits inside a supported operation (seam cases pending A1, …) are
**runtime refusals** of the coordinator". §7 nevertheless lists slice 5 (Delete/Dissolve) as "blocked
on A1".

With item 7, the non-seam Delete/Dissolve coordinator does not depend on A1. Non-seam Delete and
Dissolve are class B, mechanically the simplest (one `apply_remove` on the expanded set; probe F
shows symmetric results with 0 faces without a partner). Seam consumption is detected after the op
(dead seam ids, a new self-mirrored face) and refused with rollback until A1 decides. That includes
the face-pair case in which no seam element was selected. **Suggestion:** move non-seam Delete/Dissolve
into slice 3, or into a slice 3a before the fail-closed row is installed. O1 then only concerns the
seam cases, which change from "runs one-sided" to "refused visibly", and DD-2 can close except for
A1.

**Timing consequence for A1:** A1 is "runnable today" only because Delete/Dissolve run one-sided
(§6). Once a Delete coordinator exists, it runs inside `Application` whenever a definition is set,
in MARK as well as BLOCK (see F5), and the seam cases are refused. A1 must therefore be run (or its
observations recorded) **before** that slice lands.

### F5 — MARK changes meaning for declared ops; state the G-3 distinction (SHOULD)

The coordinators sit in `Application`'s handlers and act whenever `mesh.symmetry_definition` is set.
The Lab's E5 mode is invisible to `Application` (H2-R4: the Lab writes only gate data). After slice 3,
MARK therefore runs declared contexts **coordinated**, and their runtime refusals (seam cases,
non-exact plane) apply in MARK too. MARK can still run *undeclared* ops one-sided, but not declared
ones. That is consistent with how transforms already behave (`Operation.supports_symmetry` mirrors
whenever a definition is set), but two consequences should be written down:

- §2.5 rejects G-3 because it "writes the Lab verdict KEEP-BLOCK into Production behaviour" and
  "removes the Lab's MARK comparison". Item 7's runtime refusals are also `Application` behaviour
  keyed on the definition, and they also remove the MARK comparison for declared ops. The difference
  that justifies one and not the other is real: a refusal that is part of a *supported* op's contract
  (INV-5) differs from KEEP-BLOCK for an *unsupported* op. The AD should state that difference
  instead of leaving the two arguments side by side.
- The Lab's MARK warning (`e5_warning_text`, currently "… läuft einseitig" for `C`) must be derived
  from the declaration mapping too. Otherwise it will warn about one-sided runs that no longer happen.

### F6 — The snap (X-a) is dead code until the Knife slice (NIT)

Item 6 snaps every coordinated mirror vertex to `mirror_position(source)`. In slices 3–5 there is
nothing for it to change:

- C-Split and Edge Connect use `t = 0.5` (`split_selected_edge` default; `_apply` calls
  `split_edge(e)`), which is exact on exact planes (VERIFIED, §1.2 arithmetic; probe G row x=0: 0/4,
  0/2).
- Vertex Connect, Delete and Dissolve create no new positions.
- Non-exact planes are refused (item 6).

Only the Knife (arbitrary `t`) needs the snap. A snap in slices 1–5 could not be exercised by any
coordinated op, and so could not be tested through one. **Suggestion:** build it in slice 6, together
with the pid → vertex report it needs to know which vertex is the source.

Related: "explicit selection wins" (item 2) has no effect on a union expansion (S ∪ partner(S) is
the same either way). It matters only where a source/mirror role is assigned, i.e. the snap and the
Knife. With a two-sided explicit selection that role is undefined. That question also belongs in
slice 6.

### F7 — N5 is a convenience for S1, not a need (NIT)

Item 4: the Edge Connect midpoint report is "needed for seam rule S1 when a seam edge is in a
Connect selection". The AD's own probe applies S1 without it. `maintain_split_seam` captures the dead
seam edge's endpoints before the op and finds the new vertex adjacent to both
(`symmetry_coordination_probe.py`, reproduced). Returning the midpoint map is still cheaper and less
fragile than the search, so keeping it in slice 2 is fine. The wording should say "used by", not
"needed for".

### F8 — Smaller corrections (NIT)

- §1.3 F, Dissolve row: "faces w/o partner **0**" is correct only because the merged face is its own
  vertex image. The AD says this in the next paragraph; the table could mark it with a footnote.
- R5: the full report (correspondence, indexed face check, `sides`) costs 2.2 ms on `head_basemesh`
  and 6.6 ms on `man_with_shoes_basemesh` (this container; probe R5). With two reports per
  coordinated op, the §8 cost "an extra face index per coordinated op" is negligible. This could be
  recorded as evidence.
- §2.6 seam-edge partner: a vertex that lies on the plane but is not an endpoint of a declared seam
  edge is `UNPAIRED`, not its own partner (`vertex_correspondence` excludes the vertex itself from
  the candidates). Edge partner resolution therefore fails for edges through such vertices, e.g. the
  boundary of a plane-spanning face after A1 case 2. This is relevant only once seam consumption is
  decided.

---

## Code facts in §1.2 — checked

| AD claim | Result |
|---|---|
| `HistoryStack` is a plain two-list stack; docstring "kein Merge" | VERIFIED (`history.py`) |
| `apply_mesh_change` records the selection mirror right after the push, before a residue could be set | VERIFIED (`application.py:1401-1406`) |
| `_record_selection_history` at `:1436`, `apply_mesh_change` at `:1369` | VERIFIED |
| `connect_per_face._apply` is a pure mutation and drops `mids` | VERIFIED |
| `split_edge` places at `a*(1-t) + b*t` (`mesh.py:309`) | VERIFIED |
| `mirror_position` is exact negation for an axis normal through the origin | VERIFIED (also for negative normals, probe R4) |
| `resolve_c_context` counts: 1 edge → SPLIT, 2+ edges → EDGE_CONNECT, 2+ vertices → VERTEX_CONNECT, empty → KNIFE | VERIFIED (`contextual_c.py`) |
| Gate refuses by command identity only; preview row is an allow-list | VERIFIED (`CommandGate.refusal`; `lab_app.py` `ROW_PREVIEW`) |
| `SeamConstraintError` caught in `_transform_step` (`:1260`): visible, no history, mesh unchanged | VERIFIED |
| `select_bridge` breaks ties lexicographically by position | VERIFIED (`knife_resolve.py:161-198`; note distances are also rounded to `_TIE_DIGITS`, which turns near-ties into ties) |
| `KnifeTool` begun with `mesh=…, scene=…, selection=…` (`:733-741`) | VERIFIED (`:739`) |
| Knife pushes in `_on_commit` (`knife.py:617-643`) | VERIFIED |
| Lab BLOCK row = `{Connect}` ∪ transforms without `supports_symmetry`; Delete/Dissolve absent | VERIFIED (`unsupported_commands`) |
| §1.3 tables F, G, H, I and the A2 refusal text | VERIFIED (probe re-run; A2 text matches `connect_per_face.py`) |

---

## Appendix — review probe

Throwaway, in-memory. It reuses the helpers of `experiments/topology/symmetry_ops_probe.py`. Run from
the repo root: `python <file>`.

```python
"""Throwaway review probe for AD-SYM-03 (review CLAUDE-001). In-memory only."""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path.cwd()
for p in (REPO / "experiments", REPO / "examples", REPO, REPO / "src"):
    sys.path.insert(0, str(p))

from core import SelectionMode  # noqa: E402
from mirai.symmetry import CorrespondenceState as C  # noqa: E402
from mirai.symmetry import mirror_position, symmetry_state, vertex_correspondence  # noqa: E402
from mirai.topology.connect_per_face import connect_selected_edges_per_face  # noqa: E402
from mirai.topology.delete_dissolve import remove_selected  # noqa: E402
from symmetry_lab.lab_topology import topological_sides  # noqa: E402
from topology.symmetry_ops_probe import load, partner_edge, partner_face, partner_vertex  # noqa: E402


def lonely_faces(mesh) -> int:
    corr = vertex_correspondence(mesh)
    return sum(1 for f in mesh.all_face_ids() if partner_face(mesh, corr, f) is None)


def sides(mesh) -> int:
    return topological_sides(mesh).component_count


def expand_edges(mesh, edges) -> set:
    corr = vertex_correspondence(mesh)
    out = set(edges)
    for e in edges:
        p = partner_edge(mesh, corr, e)
        if p is not None:
            out.add(p)
    return out


def r1(asset: str) -> None:  # plane-spanning face: union call vs. op + mirrored op
    s = load(asset)
    m = s.mesh
    seam = m.symmetry_definition.seam_edges
    se = next(e for e in sorted(seam, key=int)
              if len(m.edge_faces(e)) == 2 and all(len(m.face_vertices(f)) == 4 for f in m.edge_faces(e)))
    (hexa,) = remove_selected(s, SelectionMode.EDGE, {se}, dissolve=True, cleanup=True)
    xs = lambda e: [m.vertex_position(v)[0] for v in m.edge_vertices(e)]  # noqa: E731
    plus = [e for e in m.face_edges(hexa) if min(xs(e)) >= 0 and max(xs(e)) > 0][:2]
    hexa_n = len(m.face_vertices(hexa))
    base = m.export_state()
    union = expand_edges(m, plus)
    created = connect_selected_edges_per_face(s, union)
    res_a = (len(created), sum(1 for e in created if min(xs(e)) < 0 < max(xs(e))), lonely_faces(m))
    m.load_state(base)
    corr = vertex_correspondence(m)
    mirrored = {partner_edge(m, corr, e) for e in plus}
    c = connect_selected_edges_per_face(s, set(plus)) + connect_selected_edges_per_face(s, mirrored)
    res_b = (len(c), sum(1 for e in c if min(xs(e)) < 0 < max(xs(e))), lonely_faces(m))
    print(f"  R1 {asset}: merged face={hexa_n}-gon spanning the plane; selected +X edges={len(plus)}, "
          f"union size={len(union)}")
    print(f"     (a) union call : created chords={res_a[0]}, chords crossing plane={res_a[1]}, "
          f"faces w/o partner={res_a[2]}")
    print(f"     (b) op + mirror: created chords={res_b[0]}, chords crossing plane={res_b[1]}, "
          f"faces w/o partner={res_b[2]}")


def r2() -> None:  # strict delta rule on a partial mesh
    s = load("man_with_shoes_basemesh")
    m = s.mesh
    corr = vertex_correspondence(m)
    unpaired = {v for v, c in corr.items() if c.state is C.UNPAIRED}
    touching = [f for f in m.all_face_ids() if set(m.face_vertices(f)) & unpaired]
    print(f"  R2 man_with_shoes_basemesh: state={symmetry_state(m).value}, unpaired verts={len(unpaired)}, "
          f"faces touching one={len(touching)}/{len(m.all_face_ids())}")
    for f in touching:
        fe = m.face_edges(f)
        if len(fe) != 4:
            continue
        union = expand_edges(m, {fe[0], fe[2]})
        before_v = set(m.all_vertex_ids())
        connect_selected_edges_per_face(s, union)
        corr2 = vertex_correspondence(m)
        new_v = set(m.all_vertex_ids()) - before_v
        bad = [v for v in new_v if corr2[v].state not in (C.PAIRED, C.SEAM)]
        print(f"     Edge Connect on face {int(f)} (2 edges, union {len(union)}): new vertices {len(new_v)}, "
              f"not PAIRED {len(bad)} -> 'every created element is paired' refuses")
        return


def r3(asset: str) -> None:  # a symmetric Delete changes `sides`
    s = load(asset)
    m = s.mesh

    def cy(f):
        vs = m.face_vertices(f)
        return sum(m.vertex_position(v)[1] for v in vs) / len(vs)

    cys = sorted(cy(f) for f in m.all_face_ids())
    mid = cys[len(cys) // 2]
    width = sorted(abs(cy(f) - mid) for f in m.all_face_ids())[len(cys) // 6]
    band = {f for f in m.all_face_ids() if abs(cy(f) - mid) <= width}
    corr = vertex_correspondence(m)
    sym = all(partner_face(m, corr, f) in band for f in band)
    lonely0, sides0, st0 = lonely_faces(m), sides(m), symmetry_state(m).value
    remove_selected(s, SelectionMode.FACE, band, dissolve=False, cleanup=True)
    print(f"  R3 {asset}: delete a horizontal face band ({len(band)} faces, closed under partner: {sym}): "
          f"state {st0}->{symmetry_state(m).value}, faces w/o partner {lonely0}->{lonely_faces(m)}, "
          f"sides {sides0}->{sides(m)}")


def r4() -> None:  # exact-plane predicate, negative axis normal
    import random
    rnd = random.Random(7)
    fails = 0
    for _ in range(100000):
        p = (rnd.uniform(-3, 3), rnd.uniform(-3, 3), rnd.uniform(-3, 3))
        q = mirror_position(p, (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
        if q != (-p[0], p[1], p[2]) or mirror_position(q, (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0)) != p:
            fails += 1
    print(f"  R4 normal (-1,0,0) through origin: non-exact mirrors / involution failures in 100000 = {fails}")


def r5(asset: str) -> None:  # cost of the report (indexed face check)
    s = load(asset)
    m = s.mesh
    t0 = time.perf_counter()
    for _ in range(10):
        corr = vertex_correspondence(m)
        index = {frozenset(m.face_vertices(f)): f for f in m.all_face_ids()}
        lonely = 0
        for f in m.all_face_ids():
            img = []
            for v in m.face_vertices(f):
                pv = partner_vertex(corr, v)
                if pv is None:
                    break
                img.append(pv)
            else:
                if frozenset(img) in index:
                    continue
            lonely += 1
        sides(m)
    dt = (time.perf_counter() - t0) / 10 * 1000
    print(f"  R5 {asset}: correspondence + indexed face check + sides = {dt:.1f} ms per report "
          f"({len(m.all_face_ids())} faces, faces w/o partner {lonely})")


if __name__ == "__main__":
    print("R1 plane-spanning face: one union call vs. op + mirrored op")
    for a in ("subd_cube", "head_basemesh"):
        r1(a)
    print("R2 partial mesh")
    r2()
    print("R3 symmetric delete and `sides`")
    for a in ("subd_cube", "head_basemesh"):
        r3(a)
    print("R4 exact-plane predicate")
    r4()
    print("R5 report cost")
    for a in ("head_basemesh", "man_with_shoes_basemesh"):
        r5(a)
```

Output at `276dbe4`:

```text
R1 plane-spanning face: one union call vs. op + mirrored op
  R1 subd_cube: merged face=6-gon spanning the plane; selected +X edges=2, union size=4
     (a) union call : created chords=4, chords crossing plane=2, faces w/o partner=0
     (b) op + mirror: created chords=2, chords crossing plane=0, faces w/o partner=0
  R1 head_basemesh: merged face=6-gon spanning the plane; selected +X edges=2, union size=4
     (a) union call : created chords=3, chords crossing plane=1, faces w/o partner=0
     (b) op + mirror: created chords=2, chords crossing plane=0, faces w/o partner=0
R2 partial mesh
  R2 man_with_shoes_basemesh: state=partial, unpaired verts=54, faces touching one=202/926
     Edge Connect on face 9 (2 edges, union 3): new vertices 2, not PAIRED 2 -> 'every created element is paired' refuses
R3 symmetric delete and `sides`
  R3 subd_cube: delete a horizontal face band (8 faces, closed under partner: True): state valid->valid, faces w/o partner 0->0, sides 2->4
  R3 head_basemesh: delete a horizontal face band (56 faces, closed under partner: True): state valid->valid, faces w/o partner 0->0, sides 2->4
R4 exact-plane predicate
  R4 normal (-1,0,0) through origin: non-exact mirrors / involution failures in 100000 = 0
R5 report cost
  R5 head_basemesh: correspondence + indexed face check + sides = 2.2 ms per report (324 faces, faces w/o partner 0)
  R5 man_with_shoes_basemesh: correspondence + indexed face check + sides = 6.6 ms per report (926 faces, faces w/o partner 202)
```
